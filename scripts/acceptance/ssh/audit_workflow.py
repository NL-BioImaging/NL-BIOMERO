#!/usr/bin/env python3
"""Compare supplied workflow/task/job identity with Slurm accounting.

Does not establish import count, provenance completeness, workflow mode or restart
recovery. Combine with the normal site acceptance evidence for those assertions.
Normal configured tracking initialization may create missing tables; it never
resets them. Run against the existing isolated acceptance event store.
"""
import argparse
from contextlib import contextmanager
import datetime
from pathlib import Path
import shlex
from uuid import UUID

from private_ssh import finish, validate_common


@contextmanager
def configured_client(config_file):
    from biomero import SlurmClient, NoOpWorkflowTracker
    with SlurmClient.from_config(configfile=config_file, init_slurm=False, config_only=False) as client:
        if isinstance(client.workflowTracker, NoOpWorkflowTracker):
            raise ValueError('workflow_tracking_required')
        yield client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config-file', default='')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--workflow-id', type=UUID, required=True)
    parser.add_argument('--task-id', type=UUID, required=True)
    parser.add_argument('--job-id', type=int, required=True)
    parser.add_argument('--accounting-since', type=datetime.date.fromisoformat,
                        default=datetime.date.today() - datetime.timedelta(days=1))
    args = parser.parse_args()
    validate_common(parser, args, require_faults=False)
    if args.job_id <= 0:
        parser.error('Job ID must be positive')

    def audit(report):
        import paramiko
        with configured_client(args.config_file) as client:
            client.client.set_missing_host_key_policy(paramiko.RejectPolicy())
            workflow = client.workflowTracker.repository.get(args.workflow_id)
            task = client.workflowTracker.repository.get(args.task_id)
            assert args.task_id in workflow.tasks
            assert list(map(int, task.job_ids)) == [args.job_id]
            name = 'biomero-' + str(args.task_id)
            result = client.run_read_only(
                'sacct -n -X --starttime=' + args.accounting_since.isoformat() +
                ' --name=' + shlex.quote(name) + ' --format=JobIDRaw,JobName%100 -P', hide=True)
            ids = {int(fields[0]) for line in result.stdout.splitlines()
                   if len(fields := line.split('|')) >= 2 and fields[1].strip() == name}
            assert ids == {args.job_id}
            report.update(recorded_job_ids=[args.job_id], accounting_job_ids=sorted(ids))
        report['client_context_closed'] = True

    return finish(args, {'phase': 'identity-audit', 'workflow_id': str(args.workflow_id),
                         'task_id': str(args.task_id), 'job_id': args.job_id}, audit)


if __name__ == '__main__':
    raise SystemExit(main())
