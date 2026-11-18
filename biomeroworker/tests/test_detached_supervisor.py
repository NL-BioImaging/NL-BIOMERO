# -*- coding: utf-8 -*-
# Copyright (c) 2022 Torec Luik, Amsterdam UMC. All rights reserved.
# Use is subject to the BSD 2-Clause License in the LICENSE file at the root
# of this repository.
"""Isolated tests for detached claiming, restart pacing and cancellation.

The processor imports OMERO, so these run its classes and functions from
source with the biomero core stubbed: no running OMERO server or cluster
required.
"""
import ast
import contextlib
import logging
import os
from pathlib import Path
import sys
from threading import Event, Lock, Thread
from types import SimpleNamespace
from typing import Any, Dict, Iterator, List, Optional, Tuple
import typing
from unittest.mock import Mock, patch
import uuid
from uuid import uuid4

import pytest

SOURCE = Path(__file__).parents[1] / "processor.py"
CLASSES = {"WorkflowSupervisor", "WorkflowWorker", "ClaimLost",
           "RecordedInputsClient"}
FUNCTIONS = {"polling_script_runner", "latest_progress_position",
             "pump_progress_listener", "cancel_process_if_stopped"}
LAUNCHER_TASK_NAME = "SLURM_Run_Workflow.py"
BATCHED_LAUNCHER_TASK_NAME = "SLURM_Run_Workflow_Batched.py"
CORE_LEASE_SECONDS = 300
HOST_NAME = "host"
CLOCK_START = 1000.0
OLD_AGE_SECONDS = 10 ** 6
YOUNG_AGE_SECONDS = 5
SCRIPT_ID = 42


try:
    from biomero.eventsourcing import WorkflowCancelled, WorkflowInterrupted
except ImportError:  # isolated run without biomero: same class relationship
    class WorkflowInterrupted(Exception):
        """Stand-in for biomero.eventsourcing.WorkflowInterrupted."""

    class WorkflowCancelled(WorkflowInterrupted):
        """Stand-in for biomero.eventsourcing.WorkflowCancelled."""


class LocalException(Exception):
    """Stand-in for Ice.LocalException."""


CORE = SimpleNamespace(eventsourcing=SimpleNamespace(
    WorkflowCancelled=WorkflowCancelled,
    WorkflowInterrupted=WorkflowInterrupted))

# The values the processor ships, executed from its source.
SHIPPED_CONSTANTS = {
    "CLAIM_RENEW_SECONDS", "WORKER_RESTART_DELAY_SECONDS",
    "CANCEL_CHECK_SECONDS", "IGNORE_MIN_AGE_SECONDS", "SCRIPT_POLL_SECONDS",
    "SCRIPT_POLL_FAILURE_LIMIT", "CHILD_POLL_SECONDS",
    "WORKFLOW_TRACKER_APPLICATION"}


def processor_namespace(**overrides: Any) -> Dict[str, Any]:
    """Execute the processor's detached classes and functions from source.

    Args:
        **overrides (Any): Names to replace after the source ran, so that a
            test can stand in for a class or function the source defines.

    Returns:
        Dict[str, Any]: The namespace holding the executed definitions.
    """
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    nodes = [node for node in tree.body
             if (isinstance(node, ast.ClassDef) and node.name in CLASSES)
             or (isinstance(node, ast.FunctionDef)
                 and node.name in FUNCTIONS)]
    constants = [node for node in tree.body
                 if isinstance(node, ast.Assign)
                 and isinstance(node.targets[0], ast.Name)
                 and node.targets[0].id in SHIPPED_CONSTANTS]
    namespace = {name: getattr(typing, name) for name in typing.__all__}
    namespace.update(
        Thread=Thread, Event=Event, Lock=Lock, logging=logging,
        WorkflowInterrupted=WorkflowInterrupted,
        LAUNCHER_CLAIM_LEASE_SECONDS=CORE_LEASE_SECONDS,
        MAX_ACTIVE_WORKFLOWS=4,
        contextlib=contextlib, os=os, uuid=uuid,
        socket=SimpleNamespace(gethostname=lambda: HOST_NAME),
        time=SimpleNamespace(
            monotonic=Mock(return_value=CLOCK_START), sleep=Mock()),
        Ice=SimpleNamespace(LocalException=LocalException),
        start_script=Mock())
    exec(compile(ast.Module(body=constants + nodes, type_ignores=[]),
                 str(SOURCE), "exec"), namespace)
    # After the exec, so that a test can stand in for a class the source
    # defines.
    namespace.update(overrides)
    return namespace


def supervisor_with(tracker: Mock, unfinished: List[Tuple[uuid.UUID, float]],
                    worker_factory: Optional[Mock] = None) -> Any:
    """Build a supervisor whose tracker and unfinished workflows are stubbed.

    Args:
        tracker (Mock): Stands in for the workflow tracker.
        unfinished (List[Tuple[uuid.UUID, float]]): The ``(workflow_id,
            age_in_seconds)`` pairs the supervisor finds unfinished.
        worker_factory (Optional[Mock]): Stands in for the worker class.

    Returns:
        Any: The supervisor, as executed from the processor's source.
    """
    namespace = processor_namespace(
        WorkflowWorker=worker_factory or Mock())
    supervisor = namespace["WorkflowSupervisor"]()
    supervisor.tracker = tracker
    supervisor.unfinished_workflows = Mock(return_value=unfinished)
    return supervisor


def launcher(task_name: str = LAUNCHER_TASK_NAME) -> SimpleNamespace:
    """Make a launcher task as the tracker returns it.

    Args:
        task_name (str): The script the launcher task queued.

    Returns:
        SimpleNamespace: A launcher task with a fresh ID.
    """
    return SimpleNamespace(id=uuid4(), task_name=task_name)


@pytest.fixture
def core() -> Iterator[None]:
    """Stub the biomero modules the processor imports while it runs.

    Yields:
        None: While the stubs are in ``sys.modules``.
    """
    constants = SimpleNamespace(
        RUN_WF_BATCHED_SCRIPT=BATCHED_LAUNCHER_TASK_NAME,
        RUN_WF_SCRIPT=LAUNCHER_TASK_NAME,
        transfer=SimpleNamespace(IDS="IDs", DATA_TYPE="Data_Type"),
        workflow=SimpleNamespace(OUTPUT_DUPLICATES="dup"))
    with patch.dict(sys.modules, {
            "biomero": SimpleNamespace(constants=constants),
            "biomero.constants": constants,
            "biomero.eventsourcing": CORE.eventsourcing}):
        yield


# ------------------------------- the claim ------------------------------- #

def test_workflow_is_claimed_by_this_supervisor_before_a_worker_starts(
        core: None) -> None:
    """A queued workflow is claimed with the supervisor's own name, then run.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    workflow_id, queued = uuid4(), launcher()
    tracker = Mock()
    tracker.find_launcher_task.return_value = queued
    tracker.claim_launcher_task.return_value = True
    factory = Mock()
    supervisor = supervisor_with(
        tracker, [(workflow_id, OLD_AGE_SECONDS)], factory)

    supervisor.spawn_workers()

    tracker.claim_launcher_task.assert_called_once_with(
        queued.id, supervisor.owner)
    factory.assert_called_once_with(workflow_id, queued.id, False, supervisor)
    factory.return_value.start.assert_called_once()
    assert supervisor.active_workers == {workflow_id: factory.return_value}


def test_batched_launcher_starts_a_batched_worker(core: None) -> None:
    """A batched launcher task starts a worker that runs a batched parent.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    workflow_id = uuid4()
    tracker = Mock()
    tracker.find_launcher_task.return_value = launcher(
        BATCHED_LAUNCHER_TASK_NAME)
    tracker.claim_launcher_task.return_value = True
    factory = Mock()

    supervisor = supervisor_with(
        tracker, [(workflow_id, OLD_AGE_SECONDS)], factory)
    supervisor.spawn_workers()

    assert factory.call_args.args[2] is True


def test_workflow_claimed_by_another_supervisor_gets_no_worker(
        core: None, caplog: pytest.LogCaptureFixture) -> None:
    """A workflow whose claim another supervisor holds gets no worker.

    Args:
        core (None): Stubs the biomero modules the processor imports.
        caplog (pytest.LogCaptureFixture): Captures the log records.
    """
    workflow_id = uuid4()
    tracker = Mock()
    tracker.find_launcher_task.return_value = launcher()
    tracker.claim_launcher_task.return_value = False
    factory = Mock()
    supervisor = supervisor_with(
        tracker, [(workflow_id, OLD_AGE_SECONDS)], factory)

    with caplog.at_level(logging.DEBUG, logger="biomero.detached.supervisor"):
        supervisor.spawn_workers()

    factory.assert_not_called()
    assert supervisor.active_workers == {}
    assert workflow_id not in supervisor.ignored
    assert any(record.levelno == logging.DEBUG
               and "claimed by another supervisor" in record.getMessage()
               for record in caplog.records)


def test_each_supervisor_has_its_own_owner_name(core: None) -> None:
    """Two supervisors never share the name they claim workflows under.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    first = supervisor_with(Mock(), [])
    second = supervisor_with(Mock(), [])
    assert first.owner != second.owner
    assert first.owner.startswith(f"supervisor-{HOST_NAME}-")


def test_unreadable_workflow_is_retried_not_ignored(
        core: None, caplog: pytest.LogCaptureFixture) -> None:
    """A workflow that cannot be read is retried, not remembered as foreign.

    Args:
        core (None): Stubs the biomero modules the processor imports.
        caplog (pytest.LogCaptureFixture): Captures the log records.
    """
    workflow_id = uuid4()
    tracker = Mock()
    tracker.find_launcher_task.side_effect = RuntimeError("database down")
    factory = Mock()
    supervisor = supervisor_with(
        tracker, [(workflow_id, OLD_AGE_SECONDS)], factory)

    with caplog.at_level(logging.WARNING,
                         logger="biomero.detached.supervisor"):
        supervisor.spawn_workers()

    factory.assert_not_called()
    tracker.claim_launcher_task.assert_not_called()
    assert workflow_id not in supervisor.ignored
    assert any(record.levelno == logging.WARNING
               and "database down" in record.getMessage()
               for record in caplog.records)


def test_old_workflow_without_launcher_is_ignored(core: None) -> None:
    """An old workflow without a launcher task is left alone from then on.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    workflow_id = uuid4()
    tracker = Mock()
    tracker.find_launcher_task.return_value = None
    supervisor = supervisor_with(tracker, [(workflow_id, OLD_AGE_SECONDS)])

    supervisor.spawn_workers()

    assert workflow_id in supervisor.ignored
    tracker.claim_launcher_task.assert_not_called()


def test_young_workflow_without_launcher_is_looked_at_again(
        core: None) -> None:
    """A young workflow without a launcher task may still be set up.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    workflow_id = uuid4()
    tracker = Mock()
    tracker.find_launcher_task.return_value = None
    supervisor = supervisor_with(tracker, [(workflow_id, YOUNG_AGE_SECONDS)])

    supervisor.spawn_workers()

    assert workflow_id not in supervisor.ignored


# ---------------------------- renew and release ---------------------------- #

def running_worker(supervisor: Any,
                   workflow_id: Optional[uuid.UUID] = None) -> SimpleNamespace:
    """Register a running worker with a supervisor.

    Args:
        supervisor (Any): The supervisor that runs the worker.
        workflow_id (Optional[uuid.UUID]): The workflow it runs; a new ID
            when omitted.

    Returns:
        SimpleNamespace: The worker, with its own launcher task ID.
    """
    worker = SimpleNamespace(workflow_id=workflow_id or uuid4(),
                             launcher_task_id=uuid4(), holds_slot=True,
                             claim_lost=Event())
    supervisor.active_workers[worker.workflow_id] = worker
    return worker


def test_claims_of_running_workflows_are_renewed_on_a_schedule(
        core: None) -> None:
    """Claims are renewed once per renewal interval, not on every poll.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    tracker = Mock()
    tracker.claim_launcher_task.return_value = True
    supervisor = supervisor_with(tracker, [])
    worker = running_worker(supervisor)

    supervisor.renew_claims()
    supervisor.renew_claims()  # within the renewal interval

    tracker.claim_launcher_task.assert_called_once_with(
        worker.launcher_task_id, supervisor.owner)


def test_claim_is_renewed_again_after_the_interval(core: None) -> None:
    """A claim is renewed again once the renewal interval has passed.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    tracker = Mock()
    tracker.claim_launcher_task.return_value = True
    clock = Mock(return_value=CLOCK_START)
    namespace = processor_namespace(
        time=SimpleNamespace(monotonic=clock, sleep=Mock()))
    supervisor = namespace["WorkflowSupervisor"]()
    supervisor.tracker = tracker
    running_worker(supervisor)

    supervisor.renew_claims()
    clock.return_value = CLOCK_START + CORE_LEASE_SECONDS // 3 + 1
    supervisor.renew_claims()

    assert tracker.claim_launcher_task.call_count == 2


def test_lost_claim_is_an_error(
        core: None, caplog: pytest.LogCaptureFixture) -> None:
    """A claim taken by another supervisor is logged as an error.

    Args:
        core (None): Stubs the biomero modules the processor imports.
        caplog (pytest.LogCaptureFixture): Captures the log records.
    """
    tracker = Mock()
    tracker.claim_launcher_task.return_value = False
    supervisor = supervisor_with(tracker, [])
    tracker.repository.get.return_value = SimpleNamespace(
        claimed_by="another-supervisor")
    worker = running_worker(supervisor)

    with caplog.at_level(logging.ERROR, logger="biomero.detached.supervisor"):
        supervisor.renew_claims()

    assert any(record.levelno == logging.ERROR
               and "Lost the claim" in record.getMessage()
               for record in caplog.records)
    assert worker.claim_lost.is_set()


def test_clean_shutdown_releases_the_claims(core: None) -> None:
    """A clean shutdown releases the claim of every running workflow.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    tracker = Mock()
    supervisor = supervisor_with(tracker, [])
    first, second = running_worker(supervisor), running_worker(supervisor)

    supervisor.release_claims()

    released = {call.args for call
                in tracker.release_launcher_task.call_args_list}
    assert released == {
        (first.launcher_task_id, supervisor.owner),
        (second.launcher_task_id, supervisor.owner)}


def test_worker_that_ends_during_shutdown_hands_its_workflow_back(
        core: None) -> None:
    """A worker that ends while shutting down releases its claim.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    tracker = Mock()
    supervisor = supervisor_with(tracker, [])
    worker = running_worker(supervisor)
    supervisor.shutdown_event.set()

    supervisor.remove_worker(worker.workflow_id, worker.launcher_task_id)

    assert supervisor.active_workers == {}
    tracker.release_launcher_task.assert_called_once_with(
        worker.launcher_task_id, supervisor.owner)


def test_worker_that_ends_normally_keeps_its_claim(core: None) -> None:
    """A worker that ends outside a shutdown keeps its claim.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    tracker = Mock()
    supervisor = supervisor_with(tracker, [])
    worker = running_worker(supervisor)

    supervisor.remove_worker(worker.workflow_id, worker.launcher_task_id)

    tracker.release_launcher_task.assert_not_called()


# --------------------------- restart pacing --------------------------- #

def test_workflow_whose_worker_just_ended_waits_before_running_again(
        core: None) -> None:
    """A workflow is run again only after the restart delay.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    workflow_id = uuid4()
    tracker = Mock()
    tracker.find_launcher_task.return_value = launcher()
    tracker.claim_launcher_task.return_value = True
    clock = Mock(return_value=CLOCK_START)
    factory = Mock()
    namespace = processor_namespace(
        WorkflowWorker=factory,
        time=SimpleNamespace(monotonic=clock, sleep=Mock()))
    supervisor = namespace["WorkflowSupervisor"]()
    supervisor.tracker = tracker
    supervisor.unfinished_workflows = Mock(
        return_value=[(workflow_id, OLD_AGE_SECONDS)])
    supervisor.remove_worker(workflow_id, uuid4())

    delay = namespace["WORKER_RESTART_DELAY_SECONDS"]
    clock.return_value = CLOCK_START + delay - 1
    supervisor.spawn_workers()
    factory.assert_not_called()
    tracker.claim_launcher_task.assert_not_called()

    clock.return_value = CLOCK_START + delay + 1
    supervisor.spawn_workers()
    factory.assert_called_once()


# ----------------------------- cancellation ----------------------------- #

def runner_client(raise_if_stopped: Mock) -> SimpleNamespace:
    """Make the stand-in client that polling_script_runner reads.

    Args:
        raise_if_stopped (Mock): The workflow's stop check.

    Returns:
        SimpleNamespace: A client without a connection.
    """
    return SimpleNamespace(conn=None, raise_if_stopped=raise_if_stopped)


def test_sub_script_is_cancelled_when_its_workflow_is_cancelled(
        core: None) -> None:
    """A cancel request stops the running sub-script's process.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    process = Mock()
    process.poll.return_value = None
    namespace = processor_namespace()
    namespace["start_script"].return_value = process
    check = Mock(side_effect=WorkflowCancelled("asked"))

    with pytest.raises(WorkflowCancelled):
        namespace["polling_script_runner"](
            runner_client(check), Mock(), SCRIPT_ID, {})

    process.cancel.assert_called_once_with()
    process.close.assert_called_once_with(False)
    process.getResults.assert_not_called()


def test_sub_script_runs_on_while_its_workflow_is_not_cancelled(
        core: None) -> None:
    """A sub-script runs to its end while no cancel is requested.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    process = Mock()
    process.poll.side_effect = [None, 0]
    process.getResults.return_value = {"Message": "ok"}
    process.getJob.return_value = "job"
    namespace = processor_namespace()
    namespace["start_script"].return_value = process
    check = Mock()

    result = namespace["polling_script_runner"](
        runner_client(check), Mock(), SCRIPT_ID, {})

    assert result == ({"Message": "ok"}, "job")
    check.assert_called_once_with()
    process.cancel.assert_not_called()


def test_cancel_check_is_throttled(core: None) -> None:
    """The cancel check runs once per interval, not on every poll.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    clock = SimpleNamespace(now=CLOCK_START)
    process = Mock()
    process.poll.side_effect = [None] * 6 + [0]
    process.getResults.return_value = {}
    namespace = processor_namespace(time=SimpleNamespace(
        monotonic=lambda: clock.now,
        sleep=lambda seconds: setattr(clock, "now", clock.now + seconds)))
    namespace["start_script"].return_value = process
    check = Mock()

    namespace["polling_script_runner"](
        runner_client(check), Mock(), SCRIPT_ID, {})

    # polled every 2s for 10s, checked at the start and once 10s later
    assert check.call_count == 2


def children_session(statuses: Dict[uuid.UUID, str]) -> Mock:
    """Make a database session context that reports child workflow statuses.

    Args:
        statuses (Dict[uuid.UUID, str]): The status of each child workflow.

    Returns:
        Mock: A context manager yielding the session.
    """
    session = Mock()
    session.query.return_value.filter.return_value.all.return_value = [
        SimpleNamespace(workflow_id=workflow_id, status=status)
        for workflow_id, status in statuses.items()]
    return Mock(__enter__=Mock(return_value=session),
                __exit__=Mock(return_value=False))


def test_cancelled_batched_parent_cancels_its_unfinished_children(
        core: None) -> None:
    """A cancelled parent asks each unfinished child to cancel, once.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    parent_id, child_a, child_b = uuid4(), uuid4(), uuid4()
    tracker = Mock()
    tracker.repository.get.return_value = SimpleNamespace(
        completed=False, failed=False)
    tracker.is_workflow_cancel_requested.return_value = True
    statuses = {child_a: "RUNNING", child_b: "RUNNING"}
    sessions = iter([children_session(statuses),
                     children_session({child_a: "FAILED", child_b: "FAILED"})])
    engine_manager = SimpleNamespace(get_session=lambda: next(sessions))
    database = SimpleNamespace(EngineManager=engine_manager,
                               WorkflowProgressView=SimpleNamespace(
                                   workflow_id=Mock()))
    constants = SimpleNamespace(workflow_status=SimpleNamespace(
        DONE="DONE", FAILED="FAILED"))
    namespace = processor_namespace(
        time=SimpleNamespace(monotonic=Mock(), sleep=Mock()))
    supervisor = Mock(shutdown_event=Event())
    worker = namespace["WorkflowWorker"](parent_id, uuid4(), True, supervisor)
    slurm_client = SimpleNamespace(workflowTracker=tracker)
    conn = Mock()
    children = {0: (uuid4(), child_a), 1: (uuid4(), child_b)}

    with patch.dict(sys.modules, {"biomero.database": database,
                                  "biomero.constants": constants}):
        failed, pending = worker.await_children(
            slurm_client, conn, Mock(), children, [[1], [2]], {}, None)

    cancelled = {call.args[0] for call
                 in tracker.request_workflow_cancel.call_args_list}
    assert cancelled == {child_a, child_b}
    # asked once, not on every poll
    assert tracker.request_workflow_cancel.call_count == 2
    assert (failed, pending) == (2, {})


# ------------------- lost claim, renewal errors, wiring ------------------- #

def test_conflicting_renewal_that_is_still_ours_does_not_stop_the_worker(
        core: None) -> None:
    """A renewal that conflicted with another write keeps the worker.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    tracker = Mock()
    tracker.claim_launcher_task.return_value = False
    supervisor = supervisor_with(tracker, [])
    tracker.repository.get.return_value = SimpleNamespace(
        claimed_by=supervisor.owner)
    worker = running_worker(supervisor)

    supervisor.renew_claims()

    assert not worker.claim_lost.is_set()


def test_one_unreadable_claim_does_not_skip_the_other_renewals(
        core: None, caplog: pytest.LogCaptureFixture) -> None:
    """One claim that cannot be renewed does not skip the other claims.

    Args:
        core (None): Stubs the biomero modules the processor imports.
        caplog (pytest.LogCaptureFixture): Captures the log records.
    """
    tracker = Mock()
    tracker.claim_launcher_task.side_effect = [RuntimeError("db"), True]
    supervisor = supervisor_with(tracker, [])
    running_worker(supervisor)
    second = running_worker(supervisor)

    with caplog.at_level(logging.WARNING,
                         logger="biomero.detached.supervisor"):
        supervisor.renew_claims()

    assert tracker.claim_launcher_task.call_count == 2
    assert tracker.claim_launcher_task.call_args.args[0] == (
        second.launcher_task_id)
    assert any(record.levelno == logging.WARNING
               and "trying again" in record.getMessage()
               for record in caplog.records)


def test_renewal_interval_is_a_third_of_the_core_lease() -> None:
    """The renewal interval is a third of the core's claim lease."""
    assert processor_namespace()["CLAIM_RENEW_SECONDS"] == (
        CORE_LEASE_SECONDS // 3)


def make_worker(namespace: Dict[str, Any],
                supervisor: Optional[Mock] = None) -> Any:
    """Make a worker for a single (not batched) workflow.

    Args:
        namespace (Dict[str, Any]): The executed processor definitions.
        supervisor (Optional[Mock]): The worker's supervisor; a stub that is
            not shutting down when omitted.

    Returns:
        Any: The worker.
    """
    return namespace["WorkflowWorker"](
        uuid4(), uuid4(), False, supervisor or Mock(shutdown_event=Event()))


def test_worker_stops_at_its_next_check_after_the_claim_is_lost(
        core: None) -> None:
    """A worker stops at its next check once its claim is lost.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    namespace = processor_namespace()
    worker = make_worker(namespace)
    tracker = Mock()

    worker.raise_if_stopped(tracker)  # claim held: only the cancel check runs
    tracker.raise_if_cancel_requested.assert_called_once_with(
        worker.workflow_id)
    worker.claim_lost.set()
    with pytest.raises(namespace["ClaimLost"]):
        worker.raise_if_stopped(tracker)
    # the stop came first
    tracker.raise_if_cancel_requested.assert_called_once()


def test_claim_lost_is_an_interruption_not_a_cancel(core: None) -> None:
    """ClaimLost is an interruption, but neither a cancel nor an OSError.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    namespace = processor_namespace()
    assert issubclass(namespace["ClaimLost"], WorkflowInterrupted)
    assert not issubclass(namespace["ClaimLost"], WorkflowCancelled)
    assert not issubclass(namespace["ClaimLost"], OSError)


def test_worker_that_lost_its_claim_does_not_fail_the_workflow(
        core: None) -> None:
    """A worker that lost its claim leaves the workflow's outcome alone.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    namespace = processor_namespace()
    worker = make_worker(namespace)
    worker.fail_workflow = Mock()
    worker.claim_lost.set()
    worker.execute = Mock(side_effect=namespace["ClaimLost"]("lost"))

    worker.run()

    worker.fail_workflow.assert_not_called()
    worker.supervisor.remove_worker.assert_called_once()


def test_worker_that_failed_normally_fails_its_workflow(core: None) -> None:
    """A worker that failed while it held the claim fails the workflow.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    namespace = processor_namespace()
    worker = make_worker(namespace)
    worker.fail_workflow = Mock()
    worker.execute = Mock(side_effect=RuntimeError("broke"))

    worker.run()

    worker.fail_workflow.assert_called_once_with("broke")


def test_pipeline_gets_the_stop_check_and_the_sub_scripts_the_same_check(
        core: None) -> None:
    """execute() gives the pipeline and the client their stop checks.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    namespace = processor_namespace()
    worker = make_worker(namespace)
    tracker = Mock()
    launcher_task = SimpleNamespace(id=worker.launcher_task_id,
                                    params={"a": 1})
    tracker.repository.get.side_effect = [launcher_task, SimpleNamespace(
        user=1, group=2)]
    slurm = SimpleNamespace(workflowTracker=tracker)
    slurm_context = Mock(__enter__=Mock(return_value=slurm),
                         __exit__=Mock(return_value=False))
    modules = {
        "biomero.eventsourcing": SimpleNamespace(
            WorkflowCancelled=WorkflowCancelled,
            is_launcher_task=lambda task: True),
        "biomero.database": SimpleNamespace(EngineManager=Mock()),
        "biomero.slurm_client": SimpleNamespace(
            SlurmClient=SimpleNamespace(from_config=lambda: slurm_context))}
    script = Mock()
    script.resolve_pipeline_inputs.return_value = {"workflows": ["a"]}
    script.execute_workflow_pipeline.return_value = "done"
    worker.user_connection = lambda workflow: contextlib.nullcontext("conn")
    with patch.dict(sys.modules, modules), patch.dict(
            namespace, load_biomero_scripts=Mock(
                return_value=(script, Mock()))):
        worker.execute()

    pipeline_call = script.execute_workflow_pipeline.call_args
    stop_check = pipeline_call.kwargs["stop_check"]
    stop_check()  # claim held
    worker.claim_lost.set()
    with pytest.raises(namespace["ClaimLost"]):
        stop_check()
    client = pipeline_call.args[0]
    assert client.conn == "conn"
    with pytest.raises(namespace["ClaimLost"]):
        client.raise_if_stopped()  # sub-scripts stop on a lost claim too
    worker.claim_lost.clear()
    client.raise_if_stopped()
    tracker.raise_if_cancel_requested.assert_called_with(worker.workflow_id)


def test_cancelled_batched_parent_is_failed_when_its_children_ended(
        core: None) -> None:
    """A cancelled parent is failed once its children have ended.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    parent_id, child_id, task_id = uuid4(), uuid4(), uuid4()
    namespace = processor_namespace()
    worker = namespace["WorkflowWorker"](
        parent_id, uuid4(), True, Mock(shutdown_event=Event()))
    tracker = Mock()
    tracker.repository.get.return_value = SimpleNamespace(params={
        "batch_index": 0, "child_workflow_id": str(child_id)})
    tracker.is_workflow_cancel_requested.return_value = True
    worker.await_children = Mock(return_value=(1, {}))
    workflow = SimpleNamespace(tasks=[task_id], name="wf", description="",
                               user=1, group=2)

    worker.run_batches(
        Mock(), Mock(), SimpleNamespace(workflowTracker=tracker), Mock(),
        Mock(), workflow, {"batches": [[1]]})

    tracker.fail_workflow.assert_called_once()
    assert tracker.fail_workflow.call_args.args[1].startswith("Cancelled")
    tracker.complete_workflow.assert_not_called()


def parent_with_finished_children(
        namespace: Dict[str, Any],
        failed: int) -> Tuple[Any, Mock, SimpleNamespace]:
    """Make a batched parent whose one child has already ended.

    Args:
        namespace (Dict[str, Any]): The executed processor definitions.
        failed (int): How many batches ``await_children`` reports as failed.

    Returns:
        Tuple[Any, Mock, SimpleNamespace]: The worker, its tracker and the
            parent workflow.
    """
    worker = namespace["WorkflowWorker"](
        uuid4(), uuid4(), True, Mock(shutdown_event=Event()))
    tracker = Mock()
    tracker.repository.get.return_value = SimpleNamespace(params={
        "batch_index": 0, "child_workflow_id": str(uuid4())})
    worker.await_children = Mock(return_value=(failed, {}))
    workflow = SimpleNamespace(tasks=[uuid4()], name="wf", description="",
                               user=1, group=2)
    return worker, tracker, workflow


def test_late_cancel_does_not_fail_a_parent_whose_children_all_completed(
        core: None) -> None:
    """A cancel that came too late does not fail a completed parent.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    namespace = processor_namespace()
    worker, tracker, workflow = parent_with_finished_children(namespace, 0)
    tracker.is_workflow_cancel_requested.return_value = True

    worker.run_batches(
        Mock(), Mock(), SimpleNamespace(workflowTracker=tracker), Mock(),
        Mock(), workflow, {"batches": [[1]]})

    tracker.complete_workflow.assert_called_once()
    tracker.fail_workflow.assert_not_called()


def test_parent_that_lost_its_claim_writes_no_outcome(core: None) -> None:
    """A parent that lost its claim writes neither completion nor failure.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    namespace = processor_namespace()
    worker, tracker, workflow = parent_with_finished_children(namespace, 0)
    worker.claim_lost.set()

    with pytest.raises(namespace["ClaimLost"]):
        worker.run_batches(
            Mock(), Mock(), SimpleNamespace(workflowTracker=tracker), Mock(),
            Mock(), workflow, {"batches": [[1]]})

    tracker.complete_workflow.assert_not_called()
    tracker.fail_workflow.assert_not_called()


def test_parent_that_loses_its_claim_while_waiting_touches_no_child(
        core: None) -> None:
    """A parent that loses its claim while waiting writes no child state.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    namespace = processor_namespace()
    worker = namespace["WorkflowWorker"](
        uuid4(), uuid4(), True, Mock(shutdown_event=Event()))
    worker.claim_lost.set()
    tracker = Mock()
    database = SimpleNamespace(EngineManager=Mock(),
                               WorkflowProgressView=Mock())
    constants = SimpleNamespace(workflow_status=SimpleNamespace(
        DONE="DONE", FAILED="FAILED"))
    child = (uuid4(), uuid4())

    with patch.dict(sys.modules, {"biomero.database": database,
                                  "biomero.constants": constants}):
        with pytest.raises(namespace["ClaimLost"]):
            worker.await_children(
                SimpleNamespace(workflowTracker=tracker), Mock(), Mock(),
                {0: child}, [[1]], {}, None)

    tracker.complete_task.assert_not_called()
    tracker.fail_task.assert_not_called()
    tracker.request_workflow_cancel.assert_not_called()


def test_cancel_while_queuing_stops_queuing_and_waits_for_the_children(
        core: None) -> None:
    """A cancel while queuing stops queuing and waits for queued children.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    namespace = processor_namespace()
    worker = namespace["WorkflowWorker"](
        uuid4(), uuid4(), True, Mock(shutdown_event=Event()))
    tracker = Mock()
    tracker.raise_if_cancel_requested.side_effect = [
        None, WorkflowCancelled("asked")]
    tracker.is_workflow_cancel_requested.return_value = True
    tracker.repository.get.return_value = SimpleNamespace(
        completed=False, failed=False)
    first_child = uuid4()
    tracker.initiate_workflow.return_value = first_child
    worker.await_children = Mock(return_value=(0, {}))
    workflow = SimpleNamespace(tasks=[], name="wf", description="", user=1,
                               group=2)

    worker.run_batches(Mock(VERSION="v"), Mock(),
                       SimpleNamespace(workflowTracker=tracker), Mock(),
                       Mock(), workflow, {"batches": [[1], [2]]})

    assert tracker.initiate_workflow.call_count == 1  # none for the 2nd batch
    tracker.request_workflow_cancel.assert_called_once()
    assert tracker.request_workflow_cancel.call_args.args[0] == first_child
    worker.await_children.assert_called_once()  # waits for the queued child
    # an unqueued batch means the parent did not complete
    tracker.fail_workflow.assert_called_once()
    assert tracker.fail_workflow.call_args.args[1].startswith("Cancelled")
    tracker.complete_workflow.assert_not_called()


def test_children_that_already_completed_are_not_told_to_cancel(
        core: None) -> None:
    """Only children that have not ended are told to cancel.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    namespace = processor_namespace()
    worker = namespace["WorkflowWorker"](
        uuid4(), uuid4(), True, Mock(shutdown_event=Event()))
    done_task, open_task, done_child, open_child = (uuid4() for _ in range(4))
    tracker = Mock()
    tracker.repository.get.side_effect = lambda task_id: SimpleNamespace(
        completed=task_id == done_task, failed=False)

    worker.cancel_children(tracker, [(done_task, done_child),
                                     (open_task, open_child)])

    tracker.request_workflow_cancel.assert_called_once()
    assert tracker.request_workflow_cancel.call_args.args[0] == open_child


def test_claim_is_checked_before_each_write_that_creates_a_child(
        core: None) -> None:
    """A parent without its claim creates no child workflow or task.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    namespace = processor_namespace()
    worker = namespace["WorkflowWorker"](
        uuid4(), uuid4(), True, Mock(shutdown_event=Event()))
    worker.claim_lost.set()
    tracker = Mock()
    workflow = SimpleNamespace(tasks=[], name="wf", description="", user=1,
                               group=2)

    with pytest.raises(namespace["ClaimLost"]):
        worker.run_batches(Mock(VERSION="v"), Mock(),
                           SimpleNamespace(workflowTracker=tracker), Mock(),
                           Mock(), workflow, {"batches": [[1], [2]]})

    tracker.initiate_workflow.assert_not_called()
    tracker.add_task_to_workflow.assert_not_called()


def test_released_claim_is_logged_at_info_and_stops_the_worker(
        core: None, caplog: pytest.LogCaptureFixture) -> None:
    """A released claim stops the worker and is logged at INFO.

    Args:
        core (None): Stubs the biomero modules the processor imports.
        caplog (pytest.LogCaptureFixture): Captures the log records.
    """
    tracker = Mock()
    tracker.claim_launcher_task.return_value = False
    tracker.repository.get.return_value = SimpleNamespace(claimed_by=None)
    supervisor = supervisor_with(tracker, [])
    worker = running_worker(supervisor)

    with caplog.at_level(logging.INFO, logger="biomero.detached.supervisor"):
        supervisor.renew_claims()

    assert worker.claim_lost.is_set()
    assert [r.levelno for r in caplog.records
            if "released" in r.getMessage()] == [logging.INFO]
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


def test_sub_script_survives_a_failing_cancel_check(
        core: None, caplog: pytest.LogCaptureFixture) -> None:
    """A failing cancel check is logged and the sub-script runs on.

    Args:
        core (None): Stubs the biomero modules the processor imports.
        caplog (pytest.LogCaptureFixture): Captures the log records.
    """
    process = Mock()
    process.poll.side_effect = [None, 0]
    process.getResults.return_value = {}
    namespace = processor_namespace()
    namespace["start_script"].return_value = process
    check = Mock(side_effect=RuntimeError("database down"))

    with caplog.at_level(logging.WARNING, logger="biomero.detached.script"):
        namespace["polling_script_runner"](
            runner_client(check), Mock(), SCRIPT_ID, {})

    process.cancel.assert_not_called()
    assert any(record.levelno == logging.WARNING
               and "database down" in record.getMessage()
               for record in caplog.records)


def test_sub_script_is_cancelled_when_the_claim_is_lost(core: None) -> None:
    """A lost claim stops the running sub-script's process.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    process = Mock()
    process.poll.return_value = None
    namespace = processor_namespace()
    namespace["start_script"].return_value = process
    check = Mock(side_effect=namespace["ClaimLost"]("lost"))

    with pytest.raises(namespace["ClaimLost"]):
        namespace["polling_script_runner"](
            runner_client(check), Mock(), SCRIPT_ID, {})

    process.cancel.assert_called_once_with()


def test_supervisor_loop_releases_the_claims_on_the_way_out(
        core: None) -> None:
    """The supervisor loop releases its claims when it ends.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    namespace = processor_namespace(
        load_biomero_scripts=Mock(return_value=(SimpleNamespace(), Mock())),
        SUPERVISOR_STARTUP_GRACE_SECONDS=0, SUPERVISOR_POLL_SECONDS=0,
        IGNORE_CACHE_POLLS=90, polling_script_runner=Mock())
    supervisor = namespace["WorkflowSupervisor"]()
    supervisor.prune_workers = Mock()
    supervisor.spawn_maintenance = Mock()
    supervisor.spawn_workers = Mock(
        side_effect=lambda: supervisor.shutdown_event.set())
    supervisor.release_claims = Mock()
    modules = {"biomero": SimpleNamespace(WorkflowTracker=Mock()),
               "biomero.database": SimpleNamespace(EngineManager=Mock())}

    with patch.dict(sys.modules, modules):
        supervisor.run()

    supervisor.release_claims.assert_called_once()


def test_ended_workers_are_forgotten_after_the_restart_delay(
        core: None) -> None:
    """Endings older than the restart delay are forgotten.

    Args:
        core (None): Stubs the biomero modules the processor imports.
    """
    clock = Mock(return_value=CLOCK_START)
    namespace = processor_namespace(
        time=SimpleNamespace(monotonic=clock, sleep=Mock()))
    supervisor = namespace["WorkflowSupervisor"]()
    supervisor.tracker = Mock()
    supervisor.remove_worker(uuid4(), uuid4())
    restart_delay = namespace["WORKER_RESTART_DELAY_SECONDS"]
    clock.return_value = CLOCK_START + restart_delay + 1

    supervisor.prune_workers()

    assert supervisor.ended_at == {}
