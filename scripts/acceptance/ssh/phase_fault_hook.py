"""Scoped acceptance instrumentation: lost submission ACK and partial SFTP ZIP.

Dormant unless an exact workflow is armed. No global network/config changes.
Only the matched pipeline's native connection is closed; native retry code owns
all recovery. Remove its separate .pth and restart the worker after the test.
"""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shlex
import time
from uuid import UUID
import zipfile

from private_ssh import write_report


def install(directory):
    if not __debug__:
        raise RuntimeError('Acceptance fault hooks require normal Python assertion checks')
    from biomero import ssh_recovery
    from biomero.slurm_client import SlurmClient
    import importlib.metadata
    directory = Path(directory)
    # Core submits through SlurmClient.submit_job_once and downloads through
    # ssh_recovery.atomic_get (also reachable as ssh_recovery.download).
    native_submit = SlurmClient.submit_job_once
    native_download = ssh_recovery.atomic_get
    if getattr(native_submit, '_acceptance_phase_hook', False):
        return

    def control():
        try:
            value = json.loads((directory / 'control.json').read_text())
            if not isinstance(value, dict):
                return None
            if value.get('armed') is not True:
                return None
            value['workflow_id'] = str(UUID(value['workflow_id']))
            value['case_id'] = str(UUID(value['case_id']))
            assert value['mode'] in ('inline', 'detached')
            assert set(value['phases']) <= {'submit', 'zip'}
            assert PurePosixPath(value['remote_parent']).is_absolute()
            assert '..' not in PurePosixPath(value['remote_parent']).parts
            assert value['remote_parent'] != '/'
            return value
        except (OSError, ValueError, KeyError, AssertionError, TypeError):
            return None

    def save(c, phase, report):
        target = directory / (c['case_id'] + '-' + phase + '.json')
        write_report(target, report)

    def claim(c, phase):
        try:
            with (directory / (c['case_id'] + '-' + phase + '.claimed')).open('x'):
                pass
            return True
        except FileExistsError:
            return False

    def identity(client, c, task_id):
        workflow = client.workflowTracker.repository.get(UUID(c['workflow_id']))
        task = client.workflowTracker.repository.get(task_id)
        assert task_id in workflow.tasks
        assert str(task.workflow_id) == c['workflow_id']
        assert task.task_name == c['task_name']
        matches = [t for t in workflow.tasks
                   if client.workflowTracker.repository.get(t).task_name == c['task_name']]
        assert matches == [task_id], 'Require one exact analysis task in the armed workflow'
        return task

    def submit(client, sbatch_command, state_prefix, *, job_name, **options):
        def native():
            return native_submit(client, sbatch_command, state_prefix,
                                 job_name=job_name, **options)

        c = control()
        try:
            # Only analysis tasks are named biomero-<task uuid>; helper jobs
            # such as biomero-shallower-<uuid> are never faulted.
            task_id = UUID(job_name.removeprefix('biomero-'))
        except ValueError:
            return native()
        if c is None or 'submit' not in c['phases']:
            return native()
        task = client.workflowTracker.repository.get(task_id)
        if str(task.workflow_id) != c['workflow_id'] or task.task_name != c['task_name']:
            return native()
        identity(client, c, task_id)
        if not claim(c, 'submit'):
            return native()
        original_run = client.run_commands
        report = {'phase':'submit','workflow_id':c['workflow_id'],'task_id':str(task_id),
                  'mode':c['mode'],'core':importlib.metadata.version('biomero'),
                  'attempts':0,'faults':0,'accepted_job_ids':[],'status':'STARTED'}
        marker = '--job-name=biomero-' + str(task_id)

        def interrupted(commands, *args, **kwargs):
            result = original_run(commands, *args, **kwargs)
            if marker not in '\n'.join(commands):
                return result
            report['attempts'] += 1
            ids = [int(v) for v in re.findall(r'Submitted batch job (\d+)', result.stdout)]
            if result.ok and ids:
                report['accepted_job_ids'].extend(ids)
                if report['faults'] == 0:
                    report.update(faults=1, fault_monotonic=time.monotonic())
                    save(c,'submit',report)
                    client.client.get_transport().close()
                    raise EOFError('Owned acceptance fault: real accepted submission acknowledgement lost')
            return result

        client.run_commands = interrupted
        try:
            result = native()
            assert report['faults'] == 1 and report['attempts'] >= 2
            assert len(set(report['accepted_job_ids'])) == 1
            report.update(status='RECOVERED', finished_monotonic=time.monotonic())
            return result
        except BaseException as error:
            report.update(status='RAISED',error_type=type(error).__name__)
            raise
        finally:
            client.run_commands = original_run
            save(c,'submit',report)

    def download(client, remote, destination_directory):
        c = control()
        if c is None or 'zip' not in c['phases'] or not str(remote).endswith('.zip'):
            return native_download(client,remote,destination_directory)
        path = PurePosixPath(remote)
        expected_directory = PurePosixPath(c['remote_parent']) / ('biomero_' + c['workflow_id'])
        if '..' in path.parts or not path.is_relative_to(expected_directory):
            return native_download(client,remote,destination_directory)
        workflow = client.workflowTracker.repository.get(UUID(c['workflow_id']))
        tasks = [client.workflowTracker.repository.get(t) for t in workflow.tasks]
        analyses = [t for t in tasks if t.task_name == c['task_name']]
        assert len(analyses) == 1 and len(analyses[0].job_ids) == 1
        task = identity(client,c,analyses[0].id)
        job_id = int(task.job_ids[0])
        if PurePosixPath(remote).name != str(job_id)+'_out.zip':
            return native_download(client,remote,destination_directory)
        size = int(client.run_read_only('wc -c < '+shlex.quote(remote),hide=True).stdout.strip())
        if size <= 65536:
            save(c,'zip',{'phase':'zip','status':'REFUSED','reason':'fixture_not_larger_than_two_SFTP_chunks',
                          'workflow_id':c['workflow_id'],'bytes':size})
            return native_download(client,remote,destination_directory)
        if not claim(c,'zip'):
            return native_download(client,remote,destination_directory)
        original_get = client.get
        expected_hash = client.run_read_only('sha256sum -- '+shlex.quote(remote),hide=True).stdout.split()[0]
        if re.fullmatch(r'[0-9a-f]{64}', expected_hash) is None:
            raise ValueError('Expected a SHA256 digest')
        temporary_paths = []
        report = {'phase':'zip','workflow_id':c['workflow_id'],'task_id':str(task.id),'job_id':job_id,
                  'mode':c['mode'],'core':importlib.metadata.version('biomero'),
                  'attempts':[],'faults':0,'status':'STARTED','expected_sha256':expected_hash}

        def interrupted_get(*args, **kwargs):
            target = Path(kwargs['local'])
            temporary_paths.append(target)
            report['attempts'].append({'temporary_name':target.name,'initial_bytes':target.stat().st_size})
            assert target.stat().st_size == 0
            sftp = client.sftp()
            original_sftp_get = sftp.get

            def get_with_callback(remotepath, localpath, callback=None, *a, **kw):
                def progress(transferred,total):
                    if report['faults'] == 0 and 0 < transferred < total:
                        report.update(faults=1, partial_bytes=transferred,total_bytes=total,
                                      fault_monotonic=time.monotonic())
                        save(c,'zip',report)
                        client.client.get_transport().close()
                        raise EOFError('Owned acceptance fault: partial native SFTP ZIP interrupted')
                    if callback:
                        callback(transferred,total)
                return original_sftp_get(remotepath,localpath,progress,*a,**kw)
            sftp.get = get_with_callback
            try:
                return original_get(*args,**kwargs)
            finally:
                sftp.get = original_sftp_get

        client.get = interrupted_get
        try:
            result = native_download(client,remote,destination_directory)
            assert report['faults'] == 1 and len(report['attempts']) >= 2
            path = Path(result.local)
            with path.open('rb') as stream:
                assert hashlib.file_digest(stream, 'sha256').hexdigest() == expected_hash
            with zipfile.ZipFile(path) as archive:
                assert archive.testzip() is None
            assert all(not path.exists() for path in temporary_paths)
            report.update(status='RECOVERED',final_sha256=expected_hash,zip_crc_valid=True,
                          temporary_files_removed=True,finished_monotonic=time.monotonic())
            return result
        except BaseException as error:
            report.update(status='RAISED',error_type=type(error).__name__)
            raise
        finally:
            client.get = original_get
            save(c,'zip',report)

    submit._acceptance_phase_hook = True
    SlurmClient.submit_job_once = submit
    ssh_recovery.atomic_get = ssh_recovery.download = download
