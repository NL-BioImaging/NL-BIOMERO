"""Isolated processor tests: no running OMERO server or cluster required."""
import ast
import contextlib
import logging
from pathlib import Path
import sys
from threading import Event, Lock, Thread, current_thread
from types import SimpleNamespace
import typing
from typing import Any, Dict
from unittest.mock import Mock, patch
import uuid
from uuid import uuid4

import pytest

HOST_NAME = "host"


def processor_namespace() -> Dict[str, Any]:
    """Execute the processor's supervisor and maintenance worker from source.

    Returns:
        Dict[str, Any]: The namespace holding the executed classes.
    """
    source = Path(__file__).parents[1] / "processor.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    names = {"WorkflowSupervisor", "MaintenanceWorker"}
    nodes = [n for n in tree.body
             if isinstance(n, ast.ClassDef) and n.name in names]
    namespace = {name: getattr(typing, name) for name in typing.__all__}
    namespace.update(
        Thread=Thread, Event=Event, Lock=Lock, logging=logging,
        WorkflowWorker=Thread, uuid=uuid, SUPERVISOR_STOP_TIMEOUT_SECONDS=30,
        current_thread=current_thread,
        socket=SimpleNamespace(gethostname=lambda: HOST_NAME))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source),
                 "exec"), namespace)
    return namespace


def test_maintenance_uses_its_own_bounded_lane_not_analysis_slots():
    namespace = processor_namespace()
    supervisor = namespace['WorkflowSupervisor']()
    first, second = uuid4(), uuid4()
    reader = Mock(return_value=(7, {first, second}))
    maintenance = SimpleNamespace(pending_metadata_refreshes=reader)
    worker = Mock()
    worker.is_alive.return_value = True
    factory = Mock(return_value=worker)
    modules = {"biomero": SimpleNamespace(maintenance=maintenance)}
    with patch.dict(sys.modules, modules), patch.dict(
            namespace, MaintenanceWorker=factory):
        supervisor.spawn_maintenance()
        supervisor.spawn_maintenance()
    assert factory.call_count == 1
    worker.start.assert_called_once()
    assert supervisor.active_workers == {}
    assert supervisor.maintenance_cursor == 7


@pytest.mark.parametrize(
    "admin,fail,terminal",
    [(True, False, False), (False, False, False),
     (True, True, False), (True, False, True)])
def test_worker_checks_admin_and_records_terminal_outcome(
        admin: bool, fail: bool, terminal: bool) -> None:
    """A refresh needs an administrator and ends with a recorded outcome.

    Args:
        admin (bool): Whether the request's user is an administrator.
        fail (bool): Whether the sweep raises.
        terminal (bool): Whether the request already reached a final state.
    """
    namespace = processor_namespace()
    request = Mock(user=1, group=2,
                   options={"workers": 1, "view_version": "v0"})
    request.status = "DONE" if terminal else "QUEUED"
    tracker = Mock()
    tracker.repository.get.return_value = request
    context = Mock(__enter__=Mock(return_value=tracker),
                   __exit__=Mock(return_value=False))
    core = SimpleNamespace(WorkflowTracker=Mock(return_value=context))
    report = {"counts": {"updated": 2, "failed": 0},
              "results": [{"big": "not persisted"}], "discovered": 2}
    script = Mock()
    script.refresh_all_metadata.return_value = report
    if fail:
        script.refresh_all_metadata.side_effect = RuntimeError(
            "lost connection")
    conn = Mock()
    conn.isAdmin.return_value = admin
    supervisor = Mock()
    constants = SimpleNamespace(metadata_refresh_status=SimpleNamespace(
        QUEUED="QUEUED", RUNNING="RUNNING", ACTIVE=("QUEUED", "RUNNING")))
    modules = {"biomero": core, "biomero.constants": constants}
    with patch.dict(sys.modules, modules), patch.dict(
            namespace, load_metadata_script=Mock(return_value=script)):
        worker = namespace["MaintenanceWorker"](uuid4(), supervisor)
        worker.user_connection = Mock(
            return_value=contextlib.nullcontext(conn))
        worker.run()
    if terminal:
        script.refresh_all_metadata.assert_not_called()
        request.started.assert_not_called()
        request.finished.assert_not_called()
    elif not admin or fail:
        request.finished.assert_called_once()
        assert request.finished.call_args.args[1]
    else:
        request.finished.assert_called_once()
        assert request.finished.call_args.args[0] == {
            "counts": {"updated": 2, "failed": 0}, "discovered": 2}
        assert script.refresh_all_metadata.call_args.kwargs["dry_run"] is False
    supervisor.remove_maintenance_worker.assert_called_once()
    tracker.release_database_connections.assert_called_once()
