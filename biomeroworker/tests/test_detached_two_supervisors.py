"""Two supervisors on one tracking database run a workflow once.

Uses the real biomero tracker and its atomic claim; only the worker thread is
replaced, so nothing needs OMERO or a cluster.
"""
import ast
import logging
import os
from pathlib import Path
from threading import Event, Lock, Thread
from types import SimpleNamespace
import sys
from unittest.mock import Mock, patch
import uuid

import pytest

SOURCE = Path(__file__).parents[1] / 'processor.py'


def core_unavailable(reason):
    if os.environ.get('CI'):
        pytest.fail(f'{reason}: the biomero pinned in .env must provide the '
                    f'detached claim', pytrace=False)
    pytest.skip(reason, allow_module_level=True)


try:
    from biomero import constants
    from biomero.database import EngineManager
    from biomero.eventsourcing import WorkflowTracker
except ImportError:
    core_unavailable('biomero is not installed')
if not hasattr(WorkflowTracker, 'claim_launcher_task'):
    core_unavailable('Installed biomero has no launcher claim')
import biomero.eventsourcing as _core_events  # noqa: E402
if not hasattr(_core_events, 'WorkflowInterrupted'):
    core_unavailable('Installed biomero has no WorkflowInterrupted')


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setenv('PERSISTENCE_MODULE', 'eventsourcing_sqlalchemy')
    monkeypatch.setenv('SQLALCHEMY_URL',
                       f"sqlite:///{(tmp_path / 'wf.db').as_posix()}")
    EngineManager.create_scoped_session()
    yield
    EngineManager.close_engine()


def supervisor(tracker, workflow_id, factory):
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    nodes = [n for n in tree.body
             if isinstance(n, ast.ClassDef) and n.name == 'WorkflowSupervisor']
    namespace = dict(
        Thread=Thread, Event=Event, Lock=Lock, logging=logging, uuid=uuid,
        socket=SimpleNamespace(gethostname=lambda: 'host'),
        time=__import__('time'), MAX_ACTIVE_WORKFLOWS=4,
        IGNORE_MIN_AGE_SECONDS=300, CLAIM_RENEW_SECONDS=100,
        WORKER_RESTART_DELAY_SECONDS=60)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), 'exec'),
         namespace)
    namespace['WorkflowWorker'] = factory
    instance = namespace['WorkflowSupervisor']()
    instance.tracker = tracker
    instance.unfinished_workflows = Mock(return_value=[(workflow_id, 1000)])
    return instance


def test_only_one_of_two_supervisors_starts_a_worker(database):
    writer = WorkflowTracker()
    workflow_id = writer.initiate_workflow('wf', '', user=1, group=2)
    writer.add_launcher_task(workflow_id, constants.RUN_WF_SCRIPT, 'v1', [], {})
    first_factory, second_factory = Mock(), Mock()
    first = supervisor(WorkflowTracker(), workflow_id, first_factory)
    second = supervisor(WorkflowTracker(), workflow_id, second_factory)

    with patch.dict(sys.modules, {}):
        first.spawn_workers()
        second.spawn_workers()

    assert first_factory.call_count + second_factory.call_count == 1
    assert first_factory.call_count == 1  # the first to ask holds the claim


def test_a_crashed_supervisors_workflow_is_taken_over_after_its_lease(database):
    from datetime import datetime, timedelta, timezone
    writer = WorkflowTracker()
    workflow_id = writer.initiate_workflow('wf', '', user=1, group=2)
    launcher = writer.add_launcher_task(
        workflow_id, constants.RUN_WF_SCRIPT, 'v1', [], {})
    assert writer.claim_launcher_task(launcher, 'crashed-supervisor')
    factory = Mock()
    replacement = supervisor(WorkflowTracker(), workflow_id, factory)

    replacement.spawn_workers()
    factory.assert_not_called()  # the lease of the crashed one still runs

    after_lease = datetime.now(timezone.utc) + timedelta(
        seconds=constants.LAUNCHER_CLAIM_LEASE_SECONDS + 1)
    with patch('biomero.eventsourcing.datetime') as clock:
        clock.now.return_value = after_lease
        replacement.spawn_workers()
    factory.assert_called_once()
    assert WorkflowTracker().repository.get(launcher).claimed_by == (
        replacement.owner)


def worker_namespace():
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    nodes = [n for n in tree.body if isinstance(n, ast.ClassDef)
             and n.name in ('WorkflowWorker', 'ClaimLost')]
    from biomero.eventsourcing import WorkflowInterrupted
    namespace = dict(Thread=Thread, Event=Event, logging=logging,
                     contextlib=__import__('contextlib'), os=os, uuid=uuid,
                     WorkflowInterrupted=WorkflowInterrupted)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), 'exec'),
         namespace)
    return namespace


def test_worker_stop_check_on_a_real_tracker(database):
    """A lost claim stops the worker before a cancel is even looked at, and a
    cancel raises the real WorkflowCancelled, which is not a ClaimLost."""
    from biomero.eventsourcing import WorkflowCancelled
    tracker = WorkflowTracker()
    workflow_id = tracker.initiate_workflow('wf', '', user=1, group=2)
    namespace = worker_namespace()
    worker = namespace['WorkflowWorker'](
        workflow_id, uuid.uuid4(), False, Mock(shutdown_event=Event()))

    worker.raise_if_stopped(tracker)  # nothing wrong

    tracker.request_workflow_cancel(workflow_id, 'user asked')
    with pytest.raises(WorkflowCancelled):
        worker.raise_if_stopped(tracker)

    worker.claim_lost.set()
    with pytest.raises(namespace['ClaimLost']) as lost:
        worker.raise_if_stopped(tracker)
    assert not isinstance(lost.value, WorkflowCancelled)
