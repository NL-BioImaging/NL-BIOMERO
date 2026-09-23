"""Isolated tests for detached OMERO sub-script polling."""
import ast
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


class LocalException(Exception):
    """Stand-in for Ice.LocalException without requiring an OMERO install."""


def runner_namespace():
    source = Path(__file__).parents[1] / 'processor.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    nodes = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == 'polling_script_runner'
    ]
    namespace = {
        'Ice': SimpleNamespace(LocalException=LocalException),
        'SCRIPT_POLL_FAILURE_LIMIT': 5,
        'SCRIPT_POLL_SECONDS': 2,
        'logging': logging,
        'start_script': Mock(),
        'time': Mock(),
    }
    exec(
        compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'),
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
