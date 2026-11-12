"""Isolated tests for detached claiming, restart pacing and cancellation.

The processor imports OMERO, so these run its classes and functions from source
with the biomero core stubbed: no running OMERO server or cluster required.
"""
import ast
import contextlib
import logging
import os
from pathlib import Path
import sys
from threading import Event, Lock, Thread
from types import SimpleNamespace
from unittest.mock import Mock, patch
import uuid
from uuid import uuid4

import pytest

SOURCE = Path(__file__).parents[1] / 'processor.py'
CLASSES = {'WorkflowSupervisor', 'WorkflowWorker', 'ClaimLost',
           'RecordedInputsClient'}
FUNCTIONS = {'polling_script_runner'}


class WorkflowCancelled(InterruptedError):
    """Stand-in for biomero.eventsourcing.WorkflowCancelled."""


class LocalException(Exception):
    """Stand-in for Ice.LocalException."""


CORE = SimpleNamespace(eventsourcing=SimpleNamespace(
    WorkflowCancelled=WorkflowCancelled))


def processor_namespace(**overrides):
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    nodes = [node for node in tree.body
             if (isinstance(node, ast.ClassDef) and node.name in CLASSES)
             or (isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS)]
    namespace = dict(
        Thread=Thread, Event=Event, Lock=Lock, logging=logging,
        contextlib=contextlib, os=os, uuid=uuid,
        socket=SimpleNamespace(gethostname=lambda: 'host'),
        time=SimpleNamespace(
            monotonic=Mock(return_value=1000.0), sleep=Mock()),
        Ice=SimpleNamespace(LocalException=LocalException),
        MAX_ACTIVE_WORKFLOWS=4, IGNORE_MIN_AGE_SECONDS=300,
        CLAIM_RENEW_SECONDS=100, WORKER_RESTART_DELAY_SECONDS=60,
        CANCEL_CHECK_SECONDS=10, SCRIPT_POLL_SECONDS=2,
        SCRIPT_POLL_FAILURE_LIMIT=5, CHILD_POLL_SECONDS=15,
        start_script=Mock())
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), 'exec'),
         namespace)
    # After the exec, so that a test can stand in for a class the source defines.
    namespace.update(overrides)
    return namespace


def supervisor_with(tracker, unfinished, worker_factory=None):
    namespace = processor_namespace(
        WorkflowWorker=worker_factory or Mock())
    supervisor = namespace['WorkflowSupervisor']()
    supervisor.tracker = tracker
    supervisor.unfinished_workflows = Mock(return_value=unfinished)
    return supervisor


def launcher(task_name='SLURM_Run_Workflow.py'):
    return SimpleNamespace(id=uuid4(), task_name=task_name)


@pytest.fixture
def core():
    constants = SimpleNamespace(RUN_WF_BATCHED_SCRIPT='SLURM_Run_Workflow_Batched.py')
    with patch.dict(sys.modules, {
            'biomero': SimpleNamespace(constants=constants),
            'biomero.constants': constants,
            'biomero.eventsourcing': CORE.eventsourcing}):
        yield


# ------------------------------- the claim ------------------------------- #

def test_workflow_is_claimed_by_this_supervisor_before_a_worker_starts(core):
    workflow_id, queued = uuid4(), launcher()
    tracker = Mock()
    tracker.find_launcher_task.return_value = queued
    tracker.claim_launcher_task.return_value = True
    factory = Mock()
    supervisor = supervisor_with(tracker, [(workflow_id, 1000)], factory)

    supervisor.spawn_workers()

    tracker.claim_launcher_task.assert_called_once_with(
        queued.id, supervisor.owner)
    factory.assert_called_once_with(workflow_id, queued.id, False, supervisor)
    factory.return_value.start.assert_called_once()
    assert supervisor.active_workers == {workflow_id: factory.return_value}


def test_batched_launcher_starts_a_batched_worker(core):
    workflow_id = uuid4()
    tracker = Mock()
    tracker.find_launcher_task.return_value = launcher(
        'SLURM_Run_Workflow_Batched.py')
    tracker.claim_launcher_task.return_value = True
    factory = Mock()

    supervisor_with(tracker, [(workflow_id, 1000)], factory).spawn_workers()

    assert factory.call_args.args[2] is True


def test_workflow_claimed_by_another_supervisor_gets_no_worker(core, caplog):
    workflow_id = uuid4()
    tracker = Mock()
    tracker.find_launcher_task.return_value = launcher()
    tracker.claim_launcher_task.return_value = False
    factory = Mock()
    supervisor = supervisor_with(tracker, [(workflow_id, 1000)], factory)

    with caplog.at_level(logging.DEBUG, logger='biomero.detached.supervisor'):
        supervisor.spawn_workers()

    factory.assert_not_called()
    assert supervisor.active_workers == {}
    assert workflow_id not in supervisor.ignored
    assert any(record.levelno == logging.DEBUG
               and 'claimed by another supervisor' in record.getMessage()
               for record in caplog.records)


def test_each_supervisor_has_its_own_owner_name(core):
    first = supervisor_with(Mock(), [])
    second = supervisor_with(Mock(), [])
    assert first.owner != second.owner
    assert first.owner.startswith('supervisor-host-')


def test_unreadable_workflow_is_retried_not_ignored(core, caplog):
    workflow_id = uuid4()
    tracker = Mock()
    tracker.find_launcher_task.side_effect = RuntimeError('database down')
    factory = Mock()
    supervisor = supervisor_with(tracker, [(workflow_id, 10 ** 6)], factory)

    with caplog.at_level(logging.WARNING, logger='biomero.detached.supervisor'):
        supervisor.spawn_workers()

    factory.assert_not_called()
    tracker.claim_launcher_task.assert_not_called()
    assert workflow_id not in supervisor.ignored
    assert any(record.levelno == logging.WARNING
               and 'database down' in record.getMessage()
               for record in caplog.records)


def test_old_workflow_without_launcher_is_ignored(core):
    workflow_id = uuid4()
    tracker = Mock()
    tracker.find_launcher_task.return_value = None
    supervisor = supervisor_with(tracker, [(workflow_id, 10 ** 6)])

    supervisor.spawn_workers()

    assert workflow_id in supervisor.ignored
    tracker.claim_launcher_task.assert_not_called()


def test_young_workflow_without_launcher_is_looked_at_again(core):
    workflow_id = uuid4()
    tracker = Mock()
    tracker.find_launcher_task.return_value = None
    supervisor = supervisor_with(tracker, [(workflow_id, 5)])

    supervisor.spawn_workers()

    assert workflow_id not in supervisor.ignored


# ---------------------------- renew and release ---------------------------- #

def running_worker(supervisor, workflow_id=None):
    worker = SimpleNamespace(workflow_id=workflow_id or uuid4(),
                             launcher_task_id=uuid4(), holds_slot=True,
                             claim_lost=Event())
    supervisor.active_workers[worker.workflow_id] = worker
    return worker


def test_claims_of_running_workflows_are_renewed_on_a_schedule(core):
    tracker = Mock()
    tracker.claim_launcher_task.return_value = True
    supervisor = supervisor_with(tracker, [])
    worker = running_worker(supervisor)

    supervisor.renew_claims()
    supervisor.renew_claims()  # within the renewal interval

    tracker.claim_launcher_task.assert_called_once_with(
        worker.launcher_task_id, supervisor.owner)


def test_claim_is_renewed_again_after_the_interval(core):
    tracker = Mock()
    tracker.claim_launcher_task.return_value = True
    clock = Mock(return_value=1000.0)
    namespace = processor_namespace(
        time=SimpleNamespace(monotonic=clock, sleep=Mock()))
    supervisor = namespace['WorkflowSupervisor']()
    supervisor.tracker = tracker
    running_worker(supervisor)

    supervisor.renew_claims()
    clock.return_value = 1000.0 + 101
    supervisor.renew_claims()

    assert tracker.claim_launcher_task.call_count == 2


def test_lost_claim_is_an_error(core, caplog):
    tracker = Mock()
    tracker.claim_launcher_task.return_value = False
    supervisor = supervisor_with(tracker, [])
    tracker.repository.get.return_value = SimpleNamespace(
        claimed_by='another-supervisor')
    worker = running_worker(supervisor)

    with caplog.at_level(logging.ERROR, logger='biomero.detached.supervisor'):
        supervisor.renew_claims()

    assert any(record.levelno == logging.ERROR
               and 'Lost the claim' in record.getMessage()
               for record in caplog.records)
    assert worker.claim_lost.is_set()


def test_clean_shutdown_releases_the_claims(core):
    tracker = Mock()
    supervisor = supervisor_with(tracker, [])
    first, second = running_worker(supervisor), running_worker(supervisor)

    supervisor.release_claims()

    assert {call.args for call in tracker.release_launcher_task.call_args_list} == {
        (first.launcher_task_id, supervisor.owner),
        (second.launcher_task_id, supervisor.owner)}


def test_worker_that_ends_during_shutdown_hands_its_workflow_back(core):
    tracker = Mock()
    supervisor = supervisor_with(tracker, [])
    worker = running_worker(supervisor)
    supervisor.shutdown_event.set()

    supervisor.remove_worker(worker.workflow_id, worker.launcher_task_id)

    assert supervisor.active_workers == {}
    tracker.release_launcher_task.assert_called_once_with(
        worker.launcher_task_id, supervisor.owner)


def test_worker_that_ends_normally_keeps_its_claim(core):
    tracker = Mock()
    supervisor = supervisor_with(tracker, [])
    worker = running_worker(supervisor)

    supervisor.remove_worker(worker.workflow_id, worker.launcher_task_id)

    tracker.release_launcher_task.assert_not_called()


# --------------------------- restart pacing --------------------------- #

def test_workflow_whose_worker_just_ended_waits_before_running_again(core):
    workflow_id = uuid4()
    tracker = Mock()
    tracker.find_launcher_task.return_value = launcher()
    tracker.claim_launcher_task.return_value = True
    clock = Mock(return_value=1000.0)
    factory = Mock()
    namespace = processor_namespace(
        WorkflowWorker=factory,
        time=SimpleNamespace(monotonic=clock, sleep=Mock()))
    supervisor = namespace['WorkflowSupervisor']()
    supervisor.tracker = tracker
    supervisor.unfinished_workflows = Mock(return_value=[(workflow_id, 1000)])
    supervisor.remove_worker(workflow_id, uuid4())

    clock.return_value = 1030.0
    supervisor.spawn_workers()
    factory.assert_not_called()
    tracker.claim_launcher_task.assert_not_called()

    clock.return_value = 1061.0
    supervisor.spawn_workers()
    factory.assert_called_once()


# ----------------------------- cancellation ----------------------------- #

def runner_client(raise_if_cancelled):
    return SimpleNamespace(conn=None, raise_if_cancelled=raise_if_cancelled)


def test_sub_script_is_cancelled_when_its_workflow_is_cancelled(core):
    process = Mock()
    process.poll.return_value = None
    namespace = processor_namespace()
    namespace['start_script'].return_value = process
    check = Mock(side_effect=WorkflowCancelled('asked'))

    with pytest.raises(WorkflowCancelled):
        namespace['polling_script_runner'](
            runner_client(check), Mock(), 42, {})

    process.cancel.assert_called_once_with()
    process.close.assert_called_once_with(False)
    process.getResults.assert_not_called()


def test_sub_script_runs_on_while_its_workflow_is_not_cancelled(core):
    process = Mock()
    process.poll.side_effect = [None, 0]
    process.getResults.return_value = {'Message': 'ok'}
    process.getJob.return_value = 'job'
    namespace = processor_namespace()
    namespace['start_script'].return_value = process
    check = Mock()

    result = namespace['polling_script_runner'](
        runner_client(check), Mock(), 42, {})

    assert result == ({'Message': 'ok'}, 'job')
    check.assert_called_once_with()
    process.cancel.assert_not_called()


def test_cancel_check_is_throttled(core):
    clock = SimpleNamespace(now=1000.0)
    process = Mock()
    process.poll.side_effect = [None] * 6 + [0]
    process.getResults.return_value = {}
    namespace = processor_namespace(time=SimpleNamespace(
        monotonic=lambda: clock.now,
        sleep=lambda seconds: setattr(clock, 'now', clock.now + seconds)))
    namespace['start_script'].return_value = process
    check = Mock()

    namespace['polling_script_runner'](runner_client(check), Mock(), 42, {})

    # polled every 2s for 10s, checked at the start and once 10s later
    assert check.call_count == 2


def children_session(statuses):
    session = Mock()
    session.query.return_value.filter.return_value.all.return_value = [
        SimpleNamespace(workflow_id=workflow_id, status=status)
        for workflow_id, status in statuses.items()]
    return Mock(__enter__=Mock(return_value=session),
                __exit__=Mock(return_value=False))


def test_cancelled_batched_parent_cancels_its_unfinished_children(core):
    parent_id, child_a, child_b = uuid4(), uuid4(), uuid4()
    tracker = Mock()
    tracker.is_workflow_cancel_requested.return_value = True
    statuses = {child_a: 'RUNNING', child_b: 'RUNNING'}
    sessions = iter([children_session(statuses),
                     children_session({child_a: 'FAILED', child_b: 'FAILED'})])
    engine_manager = SimpleNamespace(get_session=lambda: next(sessions))
    database = SimpleNamespace(EngineManager=engine_manager,
                               WorkflowProgressView=SimpleNamespace(
                                   workflow_id=Mock()))
    constants = SimpleNamespace(workflow_status=SimpleNamespace(
        DONE='DONE', FAILED='FAILED'))
    namespace = processor_namespace(
        time=SimpleNamespace(monotonic=Mock(), sleep=Mock()))
    supervisor = Mock(shutdown_event=Event())
    worker = namespace['WorkflowWorker'](parent_id, uuid4(), True, supervisor)
    slurm_client = SimpleNamespace(workflowTracker=tracker)
    conn = Mock()
    children = {0: (uuid4(), child_a), 1: (uuid4(), child_b)}

    with patch.dict(sys.modules, {'biomero.database': database,
                                  'biomero.constants': constants}):
        failed, pending = worker.await_children(
            slurm_client, conn, Mock(), children, [[1], [2]], {}, None)

    assert {call.args[0] for call in
            tracker.request_workflow_cancel.call_args_list} == {child_a, child_b}
    # asked once, not on every poll
    assert tracker.request_workflow_cancel.call_count == 2
    assert (failed, pending) == (2, {})


# ------------------- lost claim, renewal errors, wiring ------------------- #

def test_conflicting_renewal_that_is_still_ours_does_not_stop_the_worker(core):
    tracker = Mock()
    tracker.claim_launcher_task.return_value = False
    supervisor = supervisor_with(tracker, [])
    tracker.repository.get.return_value = SimpleNamespace(
        claimed_by=supervisor.owner)
    worker = running_worker(supervisor)

    supervisor.renew_claims()

    assert not worker.claim_lost.is_set()


def test_one_unreadable_claim_does_not_skip_the_other_renewals(core, caplog):
    tracker = Mock()
    tracker.claim_launcher_task.side_effect = [RuntimeError('db'), True]
    supervisor = supervisor_with(tracker, [])
    running_worker(supervisor)
    second = running_worker(supervisor)

    with caplog.at_level(logging.WARNING, logger='biomero.detached.supervisor'):
        supervisor.renew_claims()

    assert tracker.claim_launcher_task.call_count == 2
    assert tracker.claim_launcher_task.call_args.args[0] == (
        second.launcher_task_id)
    assert any(r.levelno == logging.WARNING and 'trying again' in r.getMessage()
               for r in caplog.records)


def test_renewal_interval_is_a_third_of_the_core_lease():
    constants_line = [line for line in SOURCE.read_text(
        encoding='utf-8').splitlines()
        if line.startswith('CLAIM_RENEW_SECONDS')]
    assert constants_line == [
        'CLAIM_RENEW_SECONDS = LAUNCHER_CLAIM_LEASE_SECONDS // 3']


def make_worker(namespace, supervisor=None):
    return namespace['WorkflowWorker'](
        uuid4(), uuid4(), False, supervisor or Mock(shutdown_event=Event()))


def test_worker_stops_at_its_next_check_after_the_claim_is_lost(core):
    namespace = processor_namespace()
    worker = make_worker(namespace)
    tracker = Mock()
    cancel_check = tracker.raise_if_cancel_requested
    worker.stop_when_claim_lost(tracker)

    tracker.raise_if_cancel_requested('wf')  # claim held: the cancel check runs
    cancel_check.assert_called_once_with('wf')
    worker.claim_lost.set()
    with pytest.raises(namespace['ClaimLost']):
        tracker.raise_if_cancel_requested('wf')
    cancel_check.assert_called_once()  # the stop came first


def test_worker_that_lost_its_claim_does_not_fail_the_workflow(core):
    namespace = processor_namespace()
    worker = make_worker(namespace)
    worker.fail_workflow = Mock()
    worker.claim_lost.set()
    worker.execute = Mock(side_effect=namespace['ClaimLost']('lost'))

    worker.run()

    worker.fail_workflow.assert_not_called()
    worker.supervisor.remove_worker.assert_called_once()


def test_worker_that_failed_normally_fails_its_workflow(core):
    namespace = processor_namespace()
    worker = make_worker(namespace)
    worker.fail_workflow = Mock()
    worker.execute = Mock(side_effect=RuntimeError('broke'))

    worker.run()

    worker.fail_workflow.assert_called_once_with('broke')


def test_cancel_check_is_wired_into_the_inputs_the_pipeline_reads(core):
    """execute() hands the pipeline a client whose check uses the tracker."""
    namespace = processor_namespace()
    worker = make_worker(namespace)
    tracker = Mock()
    launcher_task = SimpleNamespace(id=worker.launcher_task_id, params={'a': 1})
    tracker.repository.get.side_effect = [launcher_task, SimpleNamespace(
        user=1, group=2)]
    original_check = tracker.raise_if_cancel_requested
    slurm = SimpleNamespace(workflowTracker=tracker)
    slurm_context = Mock(__enter__=Mock(return_value=slurm),
                         __exit__=Mock(return_value=False))
    modules = {
        'biomero.eventsourcing': SimpleNamespace(
            WorkflowCancelled=WorkflowCancelled,
            is_launcher_task=lambda task: True),
        'biomero.database': SimpleNamespace(EngineManager=Mock()),
        'biomero.slurm_client': SimpleNamespace(
            SlurmClient=SimpleNamespace(from_config=lambda: slurm_context))}
    seen = []
    worker.run_single = lambda script, slurm_client, client, conn, params: (
        seen.append(client))
    worker.user_connection = lambda workflow: contextlib.nullcontext('conn')
    with patch.dict(sys.modules, modules), patch.dict(
            namespace, load_biomero_scripts=Mock(
                return_value=(Mock(), Mock()))):
        worker.execute()

    client = seen[0]
    assert client.conn == 'conn'
    client.raise_if_cancelled()
    original_check.assert_called_once_with(worker.workflow_id)
    worker.claim_lost.set()
    with pytest.raises(namespace['ClaimLost']):
        client.raise_if_cancelled()


def test_cancelled_batched_parent_is_failed_when_its_children_ended(core):
    parent_id, child_id, task_id = uuid4(), uuid4(), uuid4()
    namespace = processor_namespace()
    worker = namespace['WorkflowWorker'](
        parent_id, uuid4(), True, Mock(shutdown_event=Event()))
    tracker = Mock()
    tracker.repository.get.return_value = SimpleNamespace(params={
        'batch_index': 0, 'child_workflow_id': str(child_id)})
    tracker.is_workflow_cancel_requested.return_value = True
    worker.await_children = Mock(return_value=(1, {}))
    workflow = SimpleNamespace(tasks=[task_id], name='wf', description='',
                               user=1, group=2)

    worker.run_batches(Mock(), Mock(), SimpleNamespace(workflowTracker=tracker),
                       Mock(), Mock(), workflow, {'batches': [[1]]})

    tracker.fail_workflow.assert_called_once()
    assert tracker.fail_workflow.call_args.args[1].startswith('Cancelled')
    tracker.complete_workflow.assert_not_called()


def test_no_batch_child_is_created_for_a_cancelled_parent(core):
    namespace = processor_namespace()
    worker = namespace['WorkflowWorker'](
        uuid4(), uuid4(), True, Mock(shutdown_event=Event()))
    tracker = Mock()
    tracker.raise_if_cancel_requested.side_effect = WorkflowCancelled('asked')
    workflow = SimpleNamespace(tasks=[], name='wf', description='', user=1,
                               group=2)

    with pytest.raises(WorkflowCancelled):
        worker.run_batches(Mock(), Mock(),
                           SimpleNamespace(workflowTracker=tracker), Mock(),
                           Mock(), workflow, {'batches': [[1], [2]]})

    tracker.initiate_workflow.assert_not_called()


def test_sub_script_survives_a_failing_cancel_check(core, caplog):
    process = Mock()
    process.poll.side_effect = [None, 0]
    process.getResults.return_value = {}
    namespace = processor_namespace()
    namespace['start_script'].return_value = process
    check = Mock(side_effect=RuntimeError('database down'))

    with caplog.at_level(logging.WARNING, logger='biomero.detached.script'):
        namespace['polling_script_runner'](runner_client(check), Mock(), 42, {})

    process.cancel.assert_not_called()
    assert any(r.levelno == logging.WARNING and 'database down' in r.getMessage()
               for r in caplog.records)


def test_sub_script_is_cancelled_when_the_claim_is_lost(core):
    process = Mock()
    process.poll.return_value = None
    namespace = processor_namespace()
    namespace['start_script'].return_value = process
    check = Mock(side_effect=namespace['ClaimLost']('lost'))

    with pytest.raises(namespace['ClaimLost']):
        namespace['polling_script_runner'](runner_client(check), Mock(), 42, {})

    process.cancel.assert_called_once_with()


def test_supervisor_loop_releases_the_claims_on_the_way_out(core):
    namespace = processor_namespace(
        load_biomero_scripts=Mock(return_value=(SimpleNamespace(), Mock())),
        SUPERVISOR_STARTUP_GRACE_SECONDS=0, SUPERVISOR_POLL_SECONDS=0,
        IGNORE_CACHE_POLLS=90, polling_script_runner=Mock())
    supervisor = namespace['WorkflowSupervisor']()
    supervisor.prune_workers = Mock()
    supervisor.spawn_maintenance = Mock()
    supervisor.spawn_workers = Mock(
        side_effect=lambda: supervisor.shutdown_event.set())
    supervisor.release_claims = Mock()
    modules = {'biomero': SimpleNamespace(WorkflowTracker=Mock()),
               'biomero.database': SimpleNamespace(EngineManager=Mock())}

    with patch.dict(sys.modules, modules):
        supervisor.run()

    supervisor.release_claims.assert_called_once()


def test_ended_workers_are_forgotten_after_the_restart_delay(core):
    clock = Mock(return_value=1000.0)
    namespace = processor_namespace(
        time=SimpleNamespace(monotonic=clock, sleep=Mock()))
    supervisor = namespace['WorkflowSupervisor']()
    supervisor.tracker = Mock()
    supervisor.remove_worker(uuid4(), uuid4())
    clock.return_value = 1061.0

    supervisor.prune_workers()

    assert supervisor.ended_at == {}
