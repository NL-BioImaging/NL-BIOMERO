#!/usr/bin/env python3
"""Reproduce a silent channel-open outage on a private connection to one supplied job.

Does not submit/cancel jobs or alter service configuration. This is the shared
monitoring boundary, not a complete inline/detached workflow acceptance run.
"""
import argparse
import threading
import time

from private_ssh import close_owned, common_arguments, finish, proxy_client, validate_common


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    common_arguments(parser)
    parser.add_argument('--job-id', type=int, required=True, help='One owned test allocation, normally completed')
    parser.add_argument('--recovery-window', type=int, default=3)
    parser.add_argument('--detection-timeout', type=float, default=.5, help='Native channel establishment timeout on this proxy only')
    parser.add_argument('--observe-seconds', type=float, default=15)
    args = parser.parse_args()
    validate_common(parser, args)
    if args.job_id <= 0 or args.recovery_window <= 0 or args.detection_timeout <= 0:
        parser.error('Job ID, recovery window and detection timeout must be positive')
    if args.observe_seconds <= args.recovery_window + args.detection_timeout + 2:
        parser.error('Observation must exceed detection plus recovery window and retry overhead')

    def probe(report):
        from biomero import SlurmClient, ssh_recovery
        original = SlurmClient.from_config(configfile=args.config_file, config_only=True)
        relay = proxy = worker = None
        result = {}
        heartbeats = []
        try:
            relay, proxy = proxy_client(original, args.recovery_window, args.detection_timeout)
            baseline = proxy.check_job_status([args.job_id])[0][args.job_id]
            report['baseline_known'] = baseline in {'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', 'PENDING'}

            def monitor():
                try:
                    with ssh_recovery.scope(proxy, heartbeat=lambda: heartbeats.append(time.monotonic())):
                        proxy.check_job_status([args.job_id])
                    result['outcome'] = 'returned'
                except Exception as error:
                    result.update(outcome='raised', error_type=type(error).__name__)

            relay.pause.set()
            began = time.monotonic()
            worker = threading.Thread(target=monitor, daemon=True)
            worker.start()
            worker.join(args.observe_seconds)
            report.update(elapsed_seconds=time.monotonic() - began,
                          still_running_at_boundary=worker.is_alive(),
                          heartbeat_count=len(heartbeats), outcome=dict(result))
            assert not worker.is_alive(), 'monitor_exceeded_observation'
            assert result.get('error_type') == 'SSHRecoveryTimeout', 'expected_terminal_recovery_timeout'
            assert len(heartbeats) > 1, 'heartbeat_not_responsive'
        finally:
            report['cleanup_errors'] = close_owned(relay, proxy, original)
            if worker is not None:
                worker.join(5)
                report['monitor_cleaned_up'] = not worker.is_alive()
            assert not report['cleanup_errors']

    return finish(args, {'phase': 'silent-monitor', 'job_id': args.job_id,
                         'recovery_window': args.recovery_window,
                         'detection_timeout': args.detection_timeout}, probe)


if __name__ == '__main__':
    raise SystemExit(main())
