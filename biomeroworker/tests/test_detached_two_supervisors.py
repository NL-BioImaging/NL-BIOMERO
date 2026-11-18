# -*- coding: utf-8 -*-
# Copyright (c) 2026 Torec Luik, Amsterdam UMC. All rights reserved.
# Use is subject to the BSD 2-Clause License in the LICENSE file at the root
# of this repository.
"""Two supervisors on one tracking database run a workflow once.

Uses the real biomero tracker and its atomic claim; only the worker thread is
replaced, so nothing needs OMERO or a cluster.
"""
import ast
import contextlib
import logging
import os
from pathlib import Path
import sys
from threading import Event, Lock, Thread
from types import SimpleNamespace
from typing import Any, Callable, Dict, Iterator, NoReturn
import typing
from unittest.mock import Mock, patch
import uuid

import pytest

SOURCE = Path(__file__).parents[1] / "processor.py"
HOST_NAME = "host"
OLD_AGE_SECONDS = 1000
MAX_ACTIVE_WORKFLOWS = 4
# The values the processor ships, executed from its source.
SHIPPED_CONSTANTS = {
    "CLAIM_RENEW_SECONDS", "WORKER_RESTART_DELAY_SECONDS",
    "IGNORE_MIN_AGE_SECONDS", "CHILD_POLL_SECONDS",
    "SUPERVISOR_STOP_TIMEOUT_SECONDS"}


def core_unavailable(reason: str) -> NoReturn:
    """Fail on CI, skip locally, when the installed biomero is unsuitable.

    Args:
        reason (str): What the installed biomero lacks.
    """
    if os.environ.get("CI"):
        pytest.fail(f"{reason}: the biomero pinned in .env must provide the "
                    f"detached claim", pytrace=False)
    pytest.skip(reason, allow_module_level=True)


try:
    from biomero import constants
    from biomero.database import EngineManager
    from biomero.eventsourcing import WorkflowTracker
except ImportError:
    core_unavailable("biomero is not installed")
if not hasattr(WorkflowTracker, "claim_launcher_task"):
    core_unavailable("Installed biomero has no launcher claim")
import biomero.eventsourcing as _core_events  # noqa: E402
if not hasattr(_core_events, "WorkflowInterrupted"):
    core_unavailable("Installed biomero has no WorkflowInterrupted")


@pytest.fixture
def database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch
             ) -> Iterator[None]:
    """Point the biomero tracker at a temporary SQLite database.

    Args:
        tmp_path (Path): Directory that holds the database file.
        monkeypatch (pytest.MonkeyPatch): Sets the tracker's environment.

    Yields:
        None: While the database is open.
    """
    database_path = (tmp_path / "wf.db").as_posix()
    monkeypatch.setenv("PERSISTENCE_MODULE", "eventsourcing_sqlalchemy")
    monkeypatch.setenv("SQLALCHEMY_URL", f"sqlite:///{database_path}")
    EngineManager.create_scoped_session()
    yield
    EngineManager.close_engine()


def executed_processor(class_names: typing.Collection[str],
                       **names: Any) -> Dict[str, Any]:
    """Execute classes and shipped constants of the processor from source.

    Args:
        class_names (typing.Collection[str]): The classes to execute.
        **names (Any): Names the executed code needs from its module.

    Returns:
        Dict[str, Any]: The namespace holding the executed definitions.
    """
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    nodes = [node for node in tree.body if isinstance(node, ast.Assign)
             and isinstance(node.targets[0], ast.Name)
             and node.targets[0].id in SHIPPED_CONSTANTS]
    nodes += [node for node in tree.body
              if isinstance(node, ast.ClassDef) and node.name in class_names]
    namespace = {name: getattr(typing, name) for name in typing.__all__}
    namespace.update(
        Thread=Thread, Event=Event, Lock=Lock, logging=logging, uuid=uuid,
        LAUNCHER_CLAIM_LEASE_SECONDS=constants.LAUNCHER_CLAIM_LEASE_SECONDS,
        **names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE),
                 "exec"), namespace)
    return namespace


def supervisor_for(tracker: WorkflowTracker, workflow_id: uuid.UUID,
                   factory: Callable[..., Any]) -> Any:
    """Build a supervisor that finds one workflow unfinished.

    Args:
        tracker (WorkflowTracker): The real tracker the supervisor claims with.
        workflow_id (uuid.UUID): The workflow it finds unfinished.
        factory (Callable[..., Any]): Stands in for the worker class.

    Returns:
        Any: The supervisor, as executed from the processor's source.
    """
    namespace = executed_processor(
        ["WorkflowSupervisor"],
        socket=SimpleNamespace(gethostname=lambda: HOST_NAME),
        time=__import__("time"), MAX_ACTIVE_WORKFLOWS=MAX_ACTIVE_WORKFLOWS)
    namespace["WorkflowWorker"] = factory
    instance = namespace["WorkflowSupervisor"]()
    instance.tracker = tracker
    instance.unfinished_workflows = Mock(
        return_value=[(workflow_id, OLD_AGE_SECONDS)])
    return instance


def test_only_one_of_two_supervisors_starts_a_worker(database: None) -> None:
    """Of two supervisors on one database, only one starts a worker.

    Args:
        database (None): Points the biomero tracker at a temporary database.
    """
    writer = WorkflowTracker()
    workflow_id = writer.initiate_workflow("wf", "", user=1, group=2)
    writer.add_launcher_task(
        workflow_id, constants.RUN_WF_SCRIPT, "v1", [], {})
    first_factory, second_factory = Mock(), Mock()
    first = supervisor_for(WorkflowTracker(), workflow_id, first_factory)
    second = supervisor_for(WorkflowTracker(), workflow_id, second_factory)

    with patch.dict(sys.modules, {}):
        first.spawn_workers()
        second.spawn_workers()

    assert first_factory.call_count + second_factory.call_count == 1
    assert first_factory.call_count == 1  # the first to ask holds the claim


def test_a_crashed_supervisors_workflow_is_taken_over_after_its_lease(
        database: None) -> None:
    """A crashed supervisor's workflow is taken over after its lease.

    Args:
        database (None): Points the biomero tracker at a temporary database.
    """
    from datetime import datetime, timedelta, timezone
    writer = WorkflowTracker()
    workflow_id = writer.initiate_workflow("wf", "", user=1, group=2)
    launcher = writer.add_launcher_task(
        workflow_id, constants.RUN_WF_SCRIPT, "v1", [], {})
    assert writer.claim_launcher_task(launcher, "crashed-supervisor")
    factory = Mock()
    replacement = supervisor_for(WorkflowTracker(), workflow_id, factory)

    replacement.spawn_workers()
    factory.assert_not_called()  # the lease of the crashed one still runs

    after_lease = datetime.now(timezone.utc) + timedelta(
        seconds=constants.LAUNCHER_CLAIM_LEASE_SECONDS + 1)
    with patch("biomero.eventsourcing.datetime") as clock:
        clock.now.return_value = after_lease
        replacement.spawn_workers()
    factory.assert_called_once()
    assert WorkflowTracker().repository.get(launcher).claimed_by == (
        replacement.owner)


def worker_namespace() -> Dict[str, Any]:
    """Execute the processor's worker classes from source.

    Returns:
        Dict[str, Any]: The namespace holding the executed definitions.
    """
    return executed_processor(
        ["RecordedInputsClient", "WorkflowWorker", "ClaimLost"],
        contextlib=contextlib, os=os,
        WorkflowInterrupted=_core_events.WorkflowInterrupted,
        time=SimpleNamespace(sleep=lambda seconds: None))


def test_worker_stop_check_on_a_real_tracker(database: None) -> None:
    """A lost claim wins over a cancel, and a cancel is not a lost claim.

    Args:
        database (None): Points the biomero tracker at a temporary database.
    """
    from biomero.eventsourcing import WorkflowCancelled
    tracker = WorkflowTracker()
    workflow_id = tracker.initiate_workflow("wf", "", user=1, group=2)
    namespace = worker_namespace()
    worker = namespace["WorkflowWorker"](
        workflow_id, uuid.uuid4(), False, Mock(shutdown_event=Event()))

    worker.raise_if_stopped(tracker)  # nothing wrong

    tracker.request_workflow_cancel(workflow_id, "user asked")
    with pytest.raises(WorkflowCancelled):
        worker.raise_if_stopped(tracker)

    worker.claim_lost.set()
    with pytest.raises(namespace["ClaimLost"]) as lost:
        worker.raise_if_stopped(tracker)
    assert not isinstance(lost.value, WorkflowCancelled)


def test_parent_that_loses_its_claim_while_annotating_writes_no_more(
        database: None) -> None:
    """A parent that loses its claim while annotating writes no more.

    The claim flips inside the annotate stub of the first batch.

    Args:
        database (None): Points the biomero tracker at a temporary database.
    """
    from biomero.constants import workflow_status
    tracker = WorkflowTracker()
    parent_id = tracker.initiate_workflow("parent", "", user=1, group=2)
    children = {}
    for index in range(2):
        child_wf = tracker.initiate_workflow(f"child {index}", "", 1, 2)
        batch_task = tracker.add_task_to_workflow(
            parent_id, constants.RUN_WF_SCRIPT, "v1", [index],
            {"batch_index": index, "child_workflow_id": str(child_wf)})
        tracker.start_task(batch_task)
        children[index] = (batch_task, child_wf)
    namespace = worker_namespace()
    worker = namespace["WorkflowWorker"](
        parent_id, uuid.uuid4(), True, Mock(shutdown_event=Event()))
    batched_script = Mock()
    batched_script.add_batch_supervisor_metadata_for_batch.side_effect = (
        lambda *args: worker.claim_lost.set())
    rows = [SimpleNamespace(workflow_id=child, status=workflow_status.DONE)
            for _, child in children.values()]
    session = Mock()
    session.query.return_value.filter.return_value.all.return_value = rows
    context = Mock(__enter__=Mock(return_value=session),
                   __exit__=Mock(return_value=False))

    with patch.object(EngineManager, "get_session", return_value=context):
        with pytest.raises(namespace["ClaimLost"]):
            worker.await_children(
                SimpleNamespace(workflowTracker=tracker), Mock(),
                batched_script, dict(children), [[0], [1]], {}, None)

    completed = [tracker.repository.get(task).completed
                 for task, _ in children.values()]
    assert completed == [True, False]  # the second batch is not written
    assert not tracker.is_workflow_finished(parent_id)
