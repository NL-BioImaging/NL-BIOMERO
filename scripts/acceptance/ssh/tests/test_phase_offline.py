"""Scope and CLI checks only; live Slurm/SFTP acceptance is separate."""
import json
import hashlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
import zipfile
from unittest.mock import Mock, patch
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import phase_fault_hook
from private_ssh import write_report


class PhaseOfflineTests(unittest.TestCase):
    def test_cli_help_dry_run_and_errors_do_not_import_runtime_or_create_files(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            (directory / 'biomero.py').write_text("raise RuntimeError('runtime must not import')")
            env = dict(os.environ, PYTHONPATH=str(directory))
            cases = {
                'phase_fault_cli.py': ['arm', '--dry-run', '--control-dir', str(directory / 'control'),
                    '--workflow-id', str(UUID(int=1)), '--mode', 'inline', '--phase', 'zip',
                    '--task-name', 'fixture', '--remote-parent', '/private-fixture'],
                'audit_terminal_history.py': [str(UUID(int=1)), '--dry-run', '--output', str(directory / 'audit.json')],
            }
            for script, arguments in cases.items():
                subprocess.run([sys.executable, str(ROOT / script), '--help'], env=env, capture_output=True, check=True)
                result = subprocess.run([sys.executable, str(ROOT / script), *arguments], env=env,
                                        capture_output=True, check=True, text=True)
                self.assertEqual(json.loads(result.stdout)['status'], 'DRY_RUN')
            self.assertFalse((directory / 'control').exists())
            self.assertFalse((directory / 'audit.json').exists())
            result = subprocess.run([sys.executable, str(ROOT / 'phase_fault_cli.py'), 'status',
                '--control-dir', str(directory / 'PRIVATE_SENTINEL')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn('PRIVATE_SENTINEL', result.stdout + result.stderr)

    def test_submit_faults_once_and_restores_only_target_clients_method(self):
        workflow_id, task_id, other_id = UUID(int=1), UUID(int=2), UUID(int=3)
        task = types.SimpleNamespace(id=task_id, workflow_id=workflow_id, task_name='fixture', job_ids=[])
        other = types.SimpleNamespace(id=other_id, workflow_id=UUID(int=9), task_name='fixture', job_ids=[])
        workflow = types.SimpleNamespace(tasks=[task_id])
        repository = types.SimpleNamespace(get=lambda value: {workflow_id: workflow, task_id: task, other_id: other}[value])
        transport = types.SimpleNamespace(close=Mock())
        native_run = Mock(return_value=types.SimpleNamespace(ok=True, stdout='Submitted batch job 42\n'))
        client = types.SimpleNamespace(workflowTracker=types.SimpleNamespace(repository=repository),
            run_commands=native_run, client=types.SimpleNamespace(get_transport=lambda: transport))

        def native_submit(client, sbatch_command, state_prefix, *, job_name, **options):
            try:
                return client.run_commands([sbatch_command])
            except EOFError:
                return client.run_commands([sbatch_command])

        from biomero.slurm_client import SlurmClient
        recovery = types.SimpleNamespace(atomic_get=Mock(), download=Mock())
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            control = {'armed': True, 'case_id': str(UUID(int=4)), 'workflow_id': str(workflow_id),
                       'task_name': 'fixture', 'phases': ['submit'], 'mode': 'inline', 'remote_parent': '/private-fixture'}
            write_report(directory / 'control.json', control)
            def submit(client, task):
                return SlurmClient.submit_job_once(
                    client, 'sbatch --job-name=biomero-' + str(task), '/state/' + str(task),
                    job_name='biomero-' + str(task))

            with patch.object(SlurmClient, 'submit_job_once', native_submit), \
                    patch.dict(sys.modules, {'biomero': types.SimpleNamespace(ssh_recovery=recovery)}), \
                    patch('importlib.metadata.version', return_value='test'):
                phase_fault_hook.install(directory)
                submit(client, other_id)
                transport.close.assert_not_called()
                submit(client, task_id)
                transport.close.assert_called_once()
                self.assertIs(client.run_commands, native_run)
                report = json.loads((directory / (control['case_id'] + '-submit.json')).read_text())
                self.assertEqual(report['status'], 'RECOVERED')
                self.assertEqual(report['faults'], 1)
                self.assertEqual(report['attempts'], 2)
                self.assertEqual(set(report['accepted_job_ids']), {42})
                submit(client, task_id)
                transport.close.assert_called_once()

    def test_helper_job_names_are_never_faulted(self):
        """biomero-shallower-<uuid> is not an analysis task: pass through."""
        from biomero.slurm_client import SlurmClient
        calls = []

        def native_submit(client, sbatch_command, state_prefix, *, job_name, **options):
            calls.append(job_name)
            return 'native'

        transport = types.SimpleNamespace(close=Mock())
        client = types.SimpleNamespace(client=types.SimpleNamespace(get_transport=lambda: transport))
        recovery = types.SimpleNamespace(atomic_get=Mock(), download=Mock())
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            control = {'armed': True, 'case_id': str(UUID(int=4)), 'workflow_id': str(UUID(int=1)),
                       'task_name': 'fixture', 'phases': ['submit'], 'mode': 'inline', 'remote_parent': '/private-fixture'}
            write_report(directory / 'control.json', control)
            with patch.object(SlurmClient, 'submit_job_once', native_submit), \
                    patch.dict(sys.modules, {'biomero': types.SimpleNamespace(ssh_recovery=recovery)}):
                phase_fault_hook.install(directory)
                for job_name in ('biomero-shallower-' + str(UUID(int=2)), 'biomero-recovery-' + str(UUID(int=2)),
                                 'conversion', 'biomero-not-a-uuid'):
                    self.assertEqual(SlurmClient.submit_job_once(
                        client, 'sbatch x', '/state', job_name=job_name), 'native')
            self.assertEqual(len(calls), 4)
            transport.close.assert_not_called()
            self.assertFalse(list(directory.glob('*.claimed')))

    def test_hook_over_the_real_submit_job_once_recovers_with_one_job(self):
        """Real submit_job_once and recovery; only the cluster answers are fake."""
        from fabric import Result
        from biomero import ssh_recovery
        from biomero.slurm_client import SlurmClient
        workflow_id, task_id = UUID(int=1), UUID(int=2)
        task = types.SimpleNamespace(id=task_id, workflow_id=workflow_id, task_name='fixture', job_ids=[])
        workflow = types.SimpleNamespace(tasks=[task_id])
        repository = types.SimpleNamespace(get=lambda value: {workflow_id: workflow, task_id: task}[value])
        transport = types.SimpleNamespace(close=Mock())
        client = SlurmClient(config_only=True, ssh_recovery_timeout=5, slurm_data_path='/data')
        client.workflowTracker = types.SimpleNamespace(repository=repository)
        client.client = types.SimpleNamespace(get_transport=lambda: transport)
        client.close = Mock()
        answers = []

        def cluster(commands, **kwargs):
            answers.append(commands)
            return Result(connection=None, exited=0, stdout='Submitted batch job 42\n')

        client.run_commands = cluster
        original_submit = SlurmClient.submit_job_once
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            control = {'armed': True, 'case_id': str(UUID(int=4)), 'workflow_id': str(workflow_id),
                       'task_name': 'fixture', 'phases': ['submit'], 'mode': 'inline', 'remote_parent': '/private-fixture'}
            write_report(directory / 'control.json', control)
            with patch.object(SlurmClient, 'submit_job_once', original_submit), \
                    patch.dict(sys.modules, {'biomero': types.SimpleNamespace(ssh_recovery=ssh_recovery)}), \
                    patch.object(ssh_recovery.time, 'sleep'), \
                    patch('importlib.metadata.version', return_value='test'):
                phase_fault_hook.install(directory)
                job_name = SlurmClient.get_submission_job_name(task_id)
                result = SlurmClient.submit_job_once(
                    client, 'sbatch --job-name=' + job_name + ' j.sh',
                    client.get_submission_state_prefix(task_id), job_name=job_name)
            self.assertEqual(client.extract_job_id(result), 42)
            transport.close.assert_called_once()
            report = json.loads((directory / (control['case_id'] + '-submit.json')).read_text())
            self.assertEqual(report['status'], 'RECOVERED')
            self.assertEqual(report['attempts'], 2)
            self.assertEqual(len(answers), 2)

    def test_zip_wrong_workflow_and_small_fixture_never_fault(self):
        workflow_id, task_id = UUID(int=1), UUID(int=2)
        task = types.SimpleNamespace(id=task_id, workflow_id=workflow_id, task_name='fixture', job_ids=[42])
        workflow = types.SimpleNamespace(tasks=[task_id])
        repository = types.SimpleNamespace(get=lambda value: {workflow_id: workflow, task_id: task}[value])
        native_download = Mock(return_value='untouched')
        recovery = types.SimpleNamespace(atomic_get=native_download, download=native_download)
        client = types.SimpleNamespace(workflowTracker=types.SimpleNamespace(repository=repository),
                                       run_read_only=Mock(return_value=types.SimpleNamespace(stdout='4096')))
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            control = {'armed': True, 'case_id': str(UUID(int=4)), 'workflow_id': str(workflow_id),
                       'task_name': 'fixture', 'phases': ['zip'], 'mode': 'inline', 'remote_parent': '/private-fixture'}
            write_report(directory / 'control.json', control)
            with patch.dict(sys.modules, {'biomero': types.SimpleNamespace(ssh_recovery=recovery)}):
                phase_fault_hook.install(directory)
                wrong = '/private-fixture/not-' + str(workflow_id) + '/42_out.zip'
                self.assertEqual(recovery.download(client, wrong, name), 'untouched')
                client.run_read_only.assert_not_called()
                correct = '/private-fixture/biomero_' + str(workflow_id) + '/42_out.zip'
                self.assertEqual(recovery.download(client, correct, name), 'untouched')
                report = json.loads((directory / (control['case_id'] + '-zip.json')).read_text())
                self.assertEqual(report['status'], 'REFUSED')
                self.assertFalse(list(directory.glob('*.claimed')))

    def test_fabric_keyword_download_fault_retries_and_cleans_native_partials(self):
        """Real Fabric transfer and BIOMERO recovery; only the SFTP peer is fake."""
        from fabric.transfer import Transfer
        from biomero import ssh_recovery
        workflow_id, task_id = UUID(int=1), UUID(int=2)
        task = types.SimpleNamespace(id=task_id, workflow_id=workflow_id,
                                     task_name='fixture', job_ids=[42])
        workflow = types.SimpleNamespace(tasks=[task_id])
        repository = types.SimpleNamespace(get=lambda value: {workflow_id: workflow, task_id: task}[value])
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED) as writer:
            writer.writestr('fixture.bin', bytes(range(256)) * 512)
        payload = archive.getvalue()
        digest = hashlib.sha256(payload).hexdigest()
        channel = types.SimpleNamespace(gettimeout=lambda: None, settimeout=Mock())
        transfer_calls = []

        def peer_get(remotepath, localpath, callback=None, **kwargs):
            transfer_calls.append((remotepath, localpath))
            with open(localpath, 'wb') as output:
                for offset in range(0, len(payload), 32768):
                    output.write(payload[offset:offset + 32768])
                    output.flush()
                    if callback:
                        callback(min(offset + 32768, len(payload)), len(payload))

        peer = types.SimpleNamespace(get=peer_get, getcwd=lambda: '/', get_channel=lambda: channel,
            stat=lambda path: types.SimpleNamespace(st_size=len(payload), st_mtime=1, st_mode=0o100600))
        transport = types.SimpleNamespace(close=Mock())
        client = types.SimpleNamespace(workflowTracker=types.SimpleNamespace(repository=repository),
            host='localhost', user='fixture', port=22, ssh_recovery_timeout=5, close=Mock(),
            sftp=lambda: peer, client=types.SimpleNamespace(get_transport=lambda: transport),
            run_read_only=lambda command, **kw: types.SimpleNamespace(
                stdout=str(len(payload)) if command.startswith('wc ') else digest))
        original_get = Transfer(client).get
        client.get = original_get
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            destination = directory / 'downloads'
            destination.mkdir()
            control = {'armed': True, 'case_id': str(UUID(int=4)), 'workflow_id': str(workflow_id),
                       'task_name': 'fixture', 'phases': ['zip'], 'mode': 'inline', 'remote_parent': '/private-fixture'}
            write_report(directory / 'control.json', control)
            # Restore the real module functions after instrumentation, including on failure.
            from biomero.slurm_client import SlurmClient
            with patch.object(SlurmClient, 'submit_job_once', SlurmClient.submit_job_once), \
                    patch.object(ssh_recovery, 'atomic_get', ssh_recovery.atomic_get), \
                    patch.object(ssh_recovery, 'download', ssh_recovery.download):
                phase_fault_hook.install(directory)
                result = ssh_recovery.download(client,
                    '/private-fixture/biomero_' + str(workflow_id) + '/42_out.zip', str(destination))
            self.assertEqual(Path(result.local).read_bytes(), payload)
            self.assertEqual(len(transfer_calls), 2)
            self.assertNotEqual(transfer_calls[0][1], transfer_calls[1][1])
            transport.close.assert_called_once()
            client.close.assert_called_once()
            self.assertIs(client.get, original_get)
            self.assertIs(peer.get, peer_get)
            self.assertFalse(list(destination.glob('*.part')))
            report = json.loads((directory / (control['case_id'] + '-zip.json')).read_text())
            self.assertEqual(report['status'], 'RECOVERED')
            self.assertEqual(report['faults'], 1)
            self.assertEqual([attempt['initial_bytes'] for attempt in report['attempts']], [0, 0])
            self.assertTrue(0 < report['partial_bytes'] < report['total_bytes'])
            self.assertTrue(report['temporary_files_removed'])


if __name__ == '__main__':
    unittest.main()
