#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) 2022 Torec Luik, Amsterdam UMC. All rights reserved.
# Use is subject to the BSD 2-Clause License in the LICENSE file at the root
# of this repository.
"""Compare explicit workflow source histories and terminal projections before Init.

Normal client initialization may create missing tables. This tool does not fail,
repair, replay or rebuild workflows, or request Slurm initialization.
"""
import argparse
from pathlib import Path
from typing import Any, Dict
from uuid import UUID

from audit_workflow import configured_client
from private_ssh import finish, validate_common

# The terminal event of a workflow, and the projected status it ends up as.
TERMINAL_STATUS_BY_EVENT = {"WorkflowCompleted": "DONE",
                            "WorkflowFailed": "FAILED"}


def terminal_record(client: Any, workflow_id: UUID) -> Dict[str, Any]:
    """Compare a workflow's source history with its terminal projection.

    Args:
        client (Any): The configured SLURM client, whose workflow tracker
            holds the workflow.
        workflow_id (UUID): The workflow to inspect.

    Returns:
        Dict[str, Any]: The projected and the durable terminal status, whether
            they agree, the event history, whether a detached launcher task
            exists, and the Slurm job IDs of the workflow's tasks.
    """
    from biomero.database import EngineManager, WorkflowProgressView
    from biomero.eventsourcing import is_launcher_task
    tracker = client.workflowTracker
    events = list(tracker.events.get(workflow_id))
    workflow = tracker.repository.get(workflow_id)
    tasks = [tracker.repository.get(task_id) for task_id in workflow.tasks]
    session = EngineManager.get_session()
    with session.no_autoflush:
        row = session.query(WorkflowProgressView).filter_by(
            workflow_id=workflow_id).first()
        projected_status = row.status if row else None
    terminal_events = [event for event in events
                       if type(event).__name__ in TERMINAL_STATUS_BY_EVENT]
    durable_status = None
    if terminal_events:
        durable_status = TERMINAL_STATUS_BY_EVENT[
            type(terminal_events[-1]).__name__]
    terminal_consistent = None
    if projected_status in TERMINAL_STATUS_BY_EVENT.values() or durable_status:
        terminal_consistent = projected_status == durable_status
    return {
        "workflow_id": str(workflow_id),
        "projected_status": projected_status,
        "source_terminal_status": durable_status,
        "terminal_consistent": terminal_consistent,
        "source_terminal_count": len(terminal_events),
        "source_history": [{"version": event.originator_version,
                            "type": type(event).__name__}
                           for event in events],
        "detached_launcher": any(is_launcher_task(task) for task in tasks),
        "job_ids": sorted({int(job) for task in tasks
                           for job in task.job_ids})}


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
