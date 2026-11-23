"""Isolated tests for detached OMERO sub-script polling."""
import ast
import itertools
import logging
from pathlib import Path
from types import SimpleNamespace
import typing
from typing import Any, Dict
from unittest.mock import Mock

import pytest

RUNNER_FUNCTIONS = {
    "polling_script_runner", "latest_progress_position",
    "pump_progress_listener", "cancel_process_if_stopped",
    "wait_for_cancelled_process"}


class LocalException(Exception):
    """Stand-in for Ice.LocalException without requiring an OMERO install."""


class WorkflowInterrupted(Exception):
    """Stand-in for the processor's WorkflowInterrupted."""


def runner_namespace() -> Dict[str, Any]:
    """Execute the processor's sub-script runner from source.

    Returns:
        Dict[str, Any]: The namespace holding the executed runner and the
            helpers it calls.
    """
    source = Path(__file__).parents[1] / "processor.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    nodes = [
        node for node in tree.body
        if (isinstance(node, ast.FunctionDef)
            and node.name in RUNNER_FUNCTIONS)
        or (isinstance(node, ast.ClassDef)
            and node.name == "RecordedInputsClient")
    ]
    namespace = {name: getattr(typing, name) for name in typing.__all__}
    namespace.update({
        "Ice": SimpleNamespace(LocalException=LocalException),
        "SCRIPT_POLL_FAILURE_LIMIT": 5,
        "SCRIPT_POLL_SECONDS": 2,
        "CANCEL_CHECK_SECONDS": 10,
        "SCRIPT_CANCEL_WAIT_SECONDS": 30,
        "WorkflowInterrupted": WorkflowInterrupted,
        "logging": logging,
        "start_script": Mock(),
        "time": Mock(),
    })
    exec(
        compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"),
        namespace,
    )
    return namespace


def test_transient_ice_poll_failure_does_not_kill_child():
    namespace = runner_namespace()
    process = Mock()
    process.poll.side_effect = [LocalException('memory limit'), None, 0]
    process.getResults.return_value = {'Message': 'normal export retained'}
    process.getJob.return_value = 'job'
    namespace['start_script'].return_value = process

    result = namespace['polling_script_runner'](
        SimpleNamespace(conn=None), Mock(), 42, {})

    assert result == ({'Message': 'normal export retained'}, 'job')
    assert process.poll.call_count == 3
    process.getResults.assert_called_once_with(0)
    process.close.assert_called_once_with(False)


def test_repeated_ice_poll_failures_remain_bounded():
    namespace = runner_namespace()
    process = Mock()
    process.poll.side_effect = LocalException('connection unavailable')
    namespace['start_script'].return_value = process

    with pytest.raises(LocalException, match='connection unavailable'):
        namespace['polling_script_runner'](
            SimpleNamespace(conn=None), Mock(), 42, {})

    assert process.poll.call_count == 5
    process.getResults.assert_not_called()
    process.close.assert_called_once_with(False)


def test_non_ice_poll_failure_is_not_hidden():
    namespace = runner_namespace()
    process = Mock()
    process.poll.side_effect = RuntimeError('bad runner state')
    namespace['start_script'].return_value = process

    with pytest.raises(RuntimeError, match='bad runner state'):
        namespace['polling_script_runner'](
            SimpleNamespace(conn=None), Mock(), 42, {})

    process.close.assert_called_once_with(False)


def stopping_client() -> SimpleNamespace:
    """Build a client whose workflow stop check asks to stop at once."""
    def raise_if_stopped():
        raise WorkflowInterrupted("cancel requested")
    return SimpleNamespace(conn=None, raise_if_stopped=raise_if_stopped)


def test_cancel_waits_for_process_to_end_before_close():
    namespace = runner_namespace()
    namespace['time'].monotonic.side_effect = itertools.count()
    calls = []
    process = Mock()
    process.cancel.side_effect = lambda: calls.append("cancel") or False
    polls = iter([None, None, 143])

    def poll():
        calls.append("poll")
        return next(polls)

    process.poll.side_effect = poll
    process.close.side_effect = lambda *a: calls.append("close")
    namespace['start_script'].return_value = process

    with pytest.raises(WorkflowInterrupted, match='cancel requested'):
        namespace['polling_script_runner'](
            stopping_client(), Mock(), 42, {})

    # The first poll is the runner's own; the next two wait for the end.
    assert calls == ["poll", "cancel", "poll", "poll", "close"]
    process.kill.assert_not_called()


def test_cancel_kills_process_that_does_not_end():
    namespace = runner_namespace()
    namespace['time'].monotonic.side_effect = itertools.count()
    process = Mock()
    process.poll.return_value = None
    namespace['start_script'].return_value = process

    with pytest.raises(WorkflowInterrupted, match='cancel requested'):
        namespace['polling_script_runner'](
            stopping_client(), Mock(), 42, {})

    process.cancel.assert_called_once_with()
    process.kill.assert_called_once_with()
    process.close.assert_called_once_with(False)


def test_cancel_wait_ice_errors_do_not_hide_the_interrupt():
    namespace = runner_namespace()
    namespace['time'].monotonic.side_effect = itertools.count()
    process = Mock()
    process.poll.side_effect = [None, LocalException('gone')]
    namespace['start_script'].return_value = process

    with pytest.raises(WorkflowInterrupted, match='cancel requested'):
        namespace['polling_script_runner'](
            stopping_client(), Mock(), 42, {})

    process.close.assert_called_once_with(False)
