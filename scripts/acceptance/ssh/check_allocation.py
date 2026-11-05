#!/usr/bin/env python3
"""Submit one bounded fixture allocation; recover a private SSH outage and retrieve its result.

Only the generated allocation may be cancelled during cleanup. Remote result
and accounting evidence are retained in a newly created child of --remote-parent.
This is core allocation continuity, not OMERO import or workflow-mode acceptance.
"""
import argparse
import datetime
from pathlib import Path, PurePosixPath
import shlex
import tempfile
import threading
import time
from uuid import uuid4

from private_ssh import close_owned, common_arguments, finish, proxy_client, validate_common


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    common_arguments(parser)
    parser.add_argument('--remote-parent', required=True, help='Existing writable private test directory on Slurm')
    parser.add_argument('--job-seconds', type=int, default=30, help='Fixture sleep, capped at 300 seconds')
    parser.add_argument('--queue-seconds', type=int, default=120)
    parser.add_argument('--recovery-window', type=int, default=10)
    parser.add_argument('--pause-seconds', type=float, default=2)
    parser.add_argument('--detection-timeout', type=float, default=.5)
    args = parser.parse_args()
    validate_common(parser, args)
    parent = PurePosixPath(args.remote_parent)
    if not parent.is_absolute() or str(parent) == '/' or '..' in parent.parts:
        parser.error('Remote parent must be an absolute private test directory, not the filesystem root')
    if not (0 < args.detection_timeout < args.pause_seconds < args.recovery_window <= 120):
        parser.error('Require 0 < detection timeout < pause < recovery window <= 120')
    if not (args.recovery_window + 5 < args.job_seconds <= 300 and 0 < args.queue_seconds <= 600):
        parser.error('Fixture duration must exceed recovery window + 5, max 300; queue wait must be 1..600')
    run_id = uuid4().hex

    def probe(report):
        from biomero import SlurmClient, ssh_recovery
        import paramiko
        client = SlurmClient.from_config(configfile=args.config_file, config_only=True)
        relay = proxy = timer = None
        job_id = None
        completed = False
        name = 'biomero-acceptance-' + run_id
        directory = str(parent / name)
        remote = directory + '/result.txt'
        quote = shlex.quote

        def wait_for(observer, expected, seconds):
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                state = observer.check_job_status([job_id])[0].get(job_id)
                if state == expected:
                    return
                if state in {'FAILED', 'CANCELLED', 'TIMEOUT', 'OUT_OF_MEMORY', 'NODE_FAIL'}:
                    raise AssertionError('fixture_failed')
                time.sleep(.5)
            raise AssertionError('fixture_state_deadline')

        try:
            client.client.set_missing_host_key_policy(paramiko.RejectPolicy())
            client.open()
            if client.gateway is not None:
                raise ValueError('gateway_adapter_required')
            # mkdir without -p refuses an existing directory; no shared paths change.
            client.run('mkdir -- ' + quote(directory), hide=True)
            body = 'sleep ' + str(args.job_seconds) + '; printf %s ' + quote(run_id) + ' > ' + quote(remote)
            command = ('sbatch --parsable --job-name=' + quote(name) + ' --output=' +
                       quote(directory + '/job.log') + ' --wrap=' + quote(body))
            result = client.run(command, hide=True)
            job_id = int(result.stdout.strip().split(';')[0])
            report.update(job_id=job_id, submission_calls=1, retained_remote_evidence=True)
            wait_for(client, 'RUNNING', args.queue_seconds)
            report['running_before_fault'] = True
            relay, proxy = proxy_client(client, args.recovery_window, args.detection_timeout)
            assert proxy.check_job_status([job_id])[0][job_id] == 'RUNNING'
            transport = proxy.transport
            relay.pause.set()
            timer = threading.Timer(args.pause_seconds, relay.pause.clear)
            timer.start()
            heartbeats = []
            began = time.monotonic()
            with ssh_recovery.scope(proxy, heartbeat=lambda: heartbeats.append(time.monotonic())):
                states, _ = proxy.check_job_status([job_id])
            report.update(recovery_elapsed=time.monotonic() - began,
                          heartbeat_count=len(heartbeats),
                          reconnected=proxy.transport is not transport)
            assert report['reconnected'] and len(heartbeats) > 1
            assert states[job_id] in {'RUNNING', 'COMPLETED'}
            wait_for(proxy, 'COMPLETED', args.job_seconds + 30)
            completed = True
            with tempfile.TemporaryDirectory() as local:
                downloaded = ssh_recovery.download(proxy, remote, local)
                assert Path(downloaded.local).read_text() == run_id
            report['original_result_verified'] = True
            since = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
            accounting = client.run_read_only(
                'sacct -n -X --starttime=' + since + ' --name=' + quote(name) +
                ' --format=JobIDRaw,JobName%100 -P', hide=True).stdout
            ids = {int(fields[0]) for line in accounting.splitlines()
                   if len(fields := line.split('|')) >= 2 and fields[1].strip() == name}
            assert ids == {job_id}
            report['accounting_job_ids'] = sorted(ids)
        finally:
            if timer is not None:
                timer.cancel()
                timer.join()
            report['cleanup_errors'] = close_owned(relay, proxy)
            try:
                if job_id is not None and not completed:
                    # Never cancel by user, name pattern, queue, or service.
                    client.run('scancel -- ' + str(job_id), hide=True, warn=True)
                    report['owned_fixture_cancel_requested'] = True
            finally:
                report['cleanup_errors'].extend(close_owned(client))
            assert not report['cleanup_errors']

    return finish(args, {'phase': 'original-allocation', 'run_id': run_id,
                         'fixture_sleep_seconds': args.job_seconds,
                         'recovery_window': args.recovery_window,
                         'detection_timeout': args.detection_timeout,
                         'pause_seconds': args.pause_seconds}, probe)


if __name__ == '__main__':
    raise SystemExit(main())
