#!/usr/bin/env python3
"""Opt-in instrumentation for one exact workflow/task/RUNNING allocation.

Install only in an isolated acceptance worker. The wrapper is dormant until
armed and never changes deployment mode, recovery settings, or submission code.
"""
import argparse
import json
import os
from pathlib import Path
import sysconfig
import threading
import time
from uuid import UUID, uuid4

from private_ssh import close_owned, proxy_client, version, write_report

PTH_NAME = 'zz_biomero_ssh_acceptance.pth'


def record_heartbeat(callback, report, lock, target):
    """Observe keepAlive's False result without changing pipeline behavior."""
    result = callback()
    with lock:
        key = 'heartbeat_failures' if result is False else 'heartbeats'
        report[key].append(time.monotonic())
        write_report(target, report)
    return result


def load_control(directory):
    try:
        value = json.loads((directory / 'control.json').read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def install(directory):
    """Called by .pth before IDs exist; reload control at each monitor call."""
    from biomero import SlurmClient
    directory = Path(directory)
    original = SlurmClient.check_job_status
    if getattr(original, '_biomero_acceptance_hook', False):
        return

    def monitored(self, job_ids, *args, **kwargs):
        control = load_control(directory)
        if not control.get('armed') or list(job_ids) != [control.get('job_id')]:
            return original(self, job_ids, *args, **kwargs)
        state = self.__dict__.get('_ssh_recovery_state')
        outage_active = state is not None and any(
            window.outage_deadline is not None for window in state.windows)
        if state is None or not state.heartbeats or outage_active:
            return original(self, job_ids, *args, **kwargs)
        target = directory / (str(UUID(control['case_id'])) + '.json')
        report = {key: control[key] for key in ('case_id', 'mode', 'workflow_id', 'task_id', 'job_id',
                                               'pause_seconds', 'detection_timeout', 'expect')}
        report.update(status='WAITING', phase='workflow-monitor', heartbeats=[], heartbeat_failures=[], events=[])
        try:
            workflow = self.workflowTracker.repository.get(UUID(control['workflow_id']))
            task_id = UUID(control['task_id'])
            task = self.workflowTracker.repository.get(task_id)
            if task_id not in workflow.tasks or list(map(int, task.job_ids)) != [control['job_id']]:
                raise ValueError('identity_mismatch')
            if state.timeout <= 0:
                raise ValueError('positive_recovery_required')
            if control['expect'] == 'recovered' and control['pause_seconds'] >= state.timeout:
                raise ValueError('pause_exceeds_recovery_window')
            if control['expect'] == 'timeout' and control['pause_seconds'] <= state.timeout + control['detection_timeout'] + 2:
                raise ValueError('pause_too_short_for_timeout')
        except Exception as error:
            report.update(status='REFUSED', error_type=type(error).__name__)
            write_report(target, report)
            return original(self, job_ids, *args, **kwargs)
        # A completed allocation is not evidence of running-job continuity.
        baseline = original(self, job_ids, *args, **kwargs)
        if baseline[0].get(control['job_id']) != 'RUNNING':
            return baseline
        try:
            with (directory / (control['case_id'] + '.claimed')).open('x'):
                pass
        except FileExistsError:
            return original(self, job_ids, *args, **kwargs)

        relay = proxy = timer = None
        traced_callbacks = []
        callbacks = list(state.heartbeats)
        lock = threading.Lock()
        report.update(status='IN_PROGRESS', running_before_fault=True, biomero=version(),
                      recovery_window=state.timeout, registered_heartbeats=len(callbacks))

        def event(name):
            with lock:
                report['events'].append({'event': name, 'monotonic': time.monotonic()})
                write_report(target, report)

        try:
            relay, proxy = proxy_client(self, state.timeout, control['detection_timeout'])
            # Preserve the actual pipeline's budget and OMERO callbacks.
            proxy.__dict__['_ssh_recovery_state'] = state
            proxy.ssh_recovery_cancel = self.ssh_recovery_cancel
            private_baseline = original(proxy, job_ids, *args, **kwargs)
            if private_baseline[0].get(control['job_id']) != 'RUNNING':
                report['status'] = 'NOT_INJECTED_JOB_NO_LONGER_RUNNING'
                return private_baseline
            traced_callbacks = []
            for index, callback in enumerate(callbacks):
                def traced(callback=callback):
                    return record_heartbeat(callback, report, lock, target)
                traced_callbacks.append((traced, callback))
                state.heartbeats[index] = traced
            relay.pause.set()
            event('private_connection_paused')

            def restore():
                relay.pause.clear()
                event('private_connection_restored')

            timer = threading.Timer(control['pause_seconds'], restore)
            timer.start()
            began = time.monotonic()
            result = original(proxy, job_ids, *args, **kwargs)
            report.update(status='MONITOR_RETURNED', elapsed=time.monotonic() - began)
            event('monitor_returned')
            return result
        except Exception as error:
            report.update(status='MONITOR_RAISED', error_type=type(error).__name__)
            event('monitor_raised')
            # Preserve production exception classification and terminal semantics.
            raise
        finally:
            if timer is not None:
                timer.cancel()
                timer.join()
            # Put each original back where its tracer still is (by identity).
            for traced, callback in traced_callbacks:
                for index, current in enumerate(state.heartbeats):
                    if current is traced:
                        state.heartbeats[index] = callback
            if proxy is not None:
                proxy.__dict__.pop('_ssh_recovery_state', None)
            report['cleanup_errors'] = close_owned(relay, proxy)
            event('private_connection_cleaned_up')

    monitored._biomero_acceptance_hook = True
    SlurmClient.check_job_status = monitored


def pth_content(directory):
    bundle = str(Path(__file__).resolve().parent)
    return (f'import sys; sys.path.insert(0, {bundle!r}); import workflow_hook; '
            f'workflow_hook.install({str(directory)!r})\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('install', 'arm', 'status', 'disarm', 'uninstall'))
    parser.add_argument('--control-dir', type=Path, required=True, help='Private worker-writable directory; runtime configuration, never publish it')
    parser.add_argument('--enable-faults', action='store_true')
    parser.add_argument('--ack-isolated-worker', action='store_true')
    parser.add_argument('--dry-run', action='store_true', help='Validate only; no files, imports or connections changed')
    parser.add_argument('--owner-uid', type=int, help='Install only: owner of the new private control directory')
    parser.add_argument('--owner-gid', type=int)
    parser.add_argument('--mode', choices=('inline', 'detached'), help='Mode selected by the deployment adapter; verify against workflow evidence')
    parser.add_argument('--workflow-id', type=UUID)
    parser.add_argument('--task-id', type=UUID)
    parser.add_argument('--job-id', type=int)
    parser.add_argument('--pause-seconds', type=float, default=2)
    parser.add_argument('--detection-timeout', type=float, default=.5)
    parser.add_argument('--expect', choices=('recovered', 'timeout'), default='recovered')
    args = parser.parse_args()
    directory = args.control_dir.absolute()
    if directory == Path(directory.anchor):
        parser.error('Choose a dedicated private control directory')
    if args.action in {'install', 'arm'} and not args.dry_run and not (args.enable_faults and args.ack_isolated_worker):
        parser.error('Install/arm require --enable-faults --ack-isolated-worker')
    if (args.owner_uid is None) != (args.owner_gid is None):
        parser.error('Supply both owner IDs or neither')
    if args.action == 'arm':
        if not all((args.mode, args.workflow_id, args.task_id, args.job_id)) or args.job_id <= 0:
            parser.error('Arm requires mode and exact workflow/task/job IDs')
        if not (0 < args.detection_timeout < args.pause_seconds <= 300):
            parser.error('Require 0 < detection timeout < pause <= 300 seconds')
    if args.dry_run:
        print(json.dumps({'status': 'DRY_RUN', 'action': args.action}))
        return 0
    os.umask(0o077)
    try:
        pth = Path(sysconfig.get_paths()['purelib']) / PTH_NAME
        if args.action == 'install':
            if pth.exists() or directory.exists():
                raise FileExistsError('refuse_existing_installation')
            directory.mkdir(mode=0o700)
            if args.owner_uid is not None:
                os.chown(directory, args.owner_uid, args.owner_gid)
            with pth.open('x', encoding='utf-8') as stream:
                stream.write(pth_content(directory))
            pth.chmod(0o644)
        elif args.action == 'arm':
            control = load_control(directory)
            if control.get('armed'):
                raise ValueError('disarm_previous_case_first')
            write_report(directory / 'control.json', {
                'armed': True, 'case_id': str(uuid4()), 'mode': args.mode,
                'workflow_id': str(args.workflow_id), 'task_id': str(args.task_id), 'job_id': args.job_id,
                'pause_seconds': args.pause_seconds, 'detection_timeout': args.detection_timeout,
                'expect': args.expect})
        elif args.action in {'disarm', 'uninstall'}:
            control = load_control(directory)
            if control:
                control['armed'] = False
                write_report(directory / 'control.json', control)
            if args.action == 'uninstall' and pth.exists():
                if pth.read_text(encoding='utf-8') != pth_content(directory):
                    raise ValueError('refuse_foreign_hook')
                pth.unlink()
        else:
            control = load_control(directory)
            if not control.get('case_id'):
                print(json.dumps({'status': 'NOT_ARMED'}))
                return 3
            path = directory / (str(UUID(control['case_id'])) + '.json')
            if not path.exists():
                print(json.dumps({'status': 'WAITING_FOR_EXACT_RUNNING_ALLOCATION'}))
                return 3
            report = json.loads(path.read_text(encoding='utf-8'))
            recovered = report['status'] == 'MONITOR_RETURNED' and report['expect'] == 'recovered'
            timed_out = (report['status'] == 'MONITOR_RAISED' and report['expect'] == 'timeout'
                         and report.get('error_type') == 'SSHRecoveryTimeout')
            report['phase_check_passed'] = (bool(recovered or timed_out)
                                             and len(report.get('heartbeats', [])) > 1
                                             and not report.get('heartbeat_failures')
                                             and not report.get('cleanup_errors')
                                             and any(e['event'] == 'private_connection_cleaned_up'
                                                     for e in report.get('events', [])))
            print(json.dumps(report, sort_keys=True))
            return 0 if report['phase_check_passed'] else 2
        print(json.dumps({'status': 'OK', 'action': args.action}))
        return 0
    except Exception as error:
        print(json.dumps({'status': 'FAIL', 'error_type': type(error).__name__}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
