#!/usr/bin/env python3
"""Compare explicit workflow source histories and terminal projections before Init.

Normal client initialization may create missing tables. This tool does not fail,
repair, replay or rebuild workflows, or request Slurm initialization.
"""
import argparse
from pathlib import Path
from uuid import UUID

from audit_workflow import configured_client
from private_ssh import finish, validate_common


def terminal_record(client, workflow_id):
    from biomero.database import EngineManager, WorkflowProgressView
    from biomero.eventsourcing import is_launcher_task
    events = list(client.workflowTracker.events.get(workflow_id))
    workflow = client.workflowTracker.repository.get(workflow_id)
    tasks = [client.workflowTracker.repository.get(task) for task in workflow.tasks]
    session = EngineManager.get_session()
    with session.no_autoflush:
        row = session.query(WorkflowProgressView).filter_by(workflow_id=workflow_id).first()
        projected = row.status if row else None
    terminals = [event for event in events if type(event).__name__ in ('WorkflowCompleted', 'WorkflowFailed')]
    durable = ({'WorkflowCompleted': 'DONE', 'WorkflowFailed': 'FAILED'}[type(terminals[-1]).__name__]
               if terminals else None)
    consistent = (projected == durable) if projected in ('DONE', 'FAILED') or durable else None
    return {
        'workflow_id': str(workflow_id), 'projected_status': projected,
        'source_terminal_status': durable, 'terminal_consistent': consistent,
        'source_terminal_count': len(terminals),
        'source_history': [{'version': event.originator_version, 'type': type(event).__name__} for event in events],
        'detached_launcher': any(is_launcher_task(task) for task in tasks),
        'job_ids': sorted({int(job) for task in tasks for job in task.job_ids})}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workflow_ids', nargs='+', type=UUID)
    parser.add_argument('--expect', choices=('FAILED', 'DONE'))
    parser.add_argument('--config-file', default='')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    validate_common(parser, args, require_faults=False)

    def audit(report):
        with configured_client(args.config_file) as client:
            report['workflows'] = [terminal_record(client, workflow_id) for workflow_id in args.workflow_ids]
        report['client_context_closed'] = True
        assert all(row['terminal_consistent'] is not False for row in report['workflows'])
        if args.expect:
            assert all(row['terminal_consistent'] is True and row['source_terminal_status'] == args.expect
                       and row['source_terminal_count'] == 1 for row in report['workflows'])

    return finish(args, {'phase': 'terminal-history-audit'}, audit)


if __name__ == '__main__':
    raise SystemExit(main())
