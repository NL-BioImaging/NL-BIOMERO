"""Isolated processor tests: no running OMERO server or cluster required."""
import ast
import contextlib
import logging
from pathlib import Path
import sys
from threading import Event, Lock, Thread
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest


def processor_namespace():
    source = Path(__file__).parents[1] / 'processor.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    names = {'WorkflowSupervisor', 'MaintenanceWorker'}
    nodes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name in names]
    namespace = dict(Thread=Thread, Event=Event, Lock=Lock, logging=logging,
                     WorkflowWorker=Thread)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), namespace)
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
    with patch.dict(sys.modules, biomero=SimpleNamespace(maintenance=maintenance)), \
            patch.dict(namespace, MaintenanceWorker=factory):
        supervisor.spawn_maintenance()
        supervisor.spawn_maintenance()
    assert factory.call_count == 1
    worker.start.assert_called_once()
    assert supervisor.active_workers == {}
    assert supervisor.maintenance_cursor == 7


@pytest.mark.parametrize('admin,fail,terminal', [(True, False, False), (False, False, False),
                                               (True, True, False), (True, False, True)])
def test_worker_checks_admin_and_records_terminal_outcome(admin, fail, terminal):
    namespace = processor_namespace()
    request = Mock(user=1, group=2, options={'workers': 1, 'view_version': 'v0'})
    request.status = 'DONE' if terminal else 'QUEUED'
    tracker = Mock()
    tracker.repository.get.return_value = request
    context = Mock(__enter__=Mock(return_value=tracker), __exit__=Mock(return_value=False))
    core = SimpleNamespace(WorkflowTracker=Mock(return_value=context))
    script = Mock()
    script.refresh_all_metadata.return_value = {'counts': {'updated': 2, 'failed': 0},
                                               'results': [{'big': 'not persisted'}], 'discovered': 2}
    if fail:
        script.refresh_all_metadata.side_effect = RuntimeError('lost connection')
    conn = Mock()
    conn.isAdmin.return_value = admin
    supervisor = Mock()
    with patch.dict(sys.modules, biomero=core), \
            patch.dict(namespace, load_metadata_script=Mock(return_value=script)):
        worker = namespace['MaintenanceWorker'](uuid4(), supervisor)
        worker.user_connection = Mock(return_value=contextlib.nullcontext(conn))
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
        assert request.finished.call_args.args[0] == {'counts': {'updated': 2, 'failed': 0},
                                                     'discovered': 2}
        assert script.refresh_all_metadata.call_args.kwargs['dry_run'] is False
    supervisor.remove_maintenance_worker.assert_called_once()
