"""Scope and CLI checks only; live Slurm/SFTP acceptance is separate."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import phase_fault_hook
from private_ssh import write_report


class PhaseOfflineTests(unittest.TestCase):
    def test_cli_help_dry_run_and_errors_do_not_import_runtime_or_create_files(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            (directory / 'biomero.py').write_text("raise RuntimeError('runtime must not import')")
            env = dict(os.environ, PYTHONPATH=str(directory))
            cases = {
                'phase_fault_cli.py': ['arm', '--dry-run', '--control-dir', str(directory / 'control'),
                    '--workflow-id', str(UUID(int=1)), '--mode', 'inline', '--phase', 'zip',
                    '--task-name', 'fixture', '--remote-parent', '/private-fixture'],
                'audit_terminal_history.py': [str(UUID(int=1)), '--dry-run', '--output', str(directory / 'audit.json')],
            }
            for script, arguments in cases.items():
                subprocess.run([sys.executable, str(ROOT / script), '--help'], env=env, capture_output=True, check=True)
                result = subprocess.run([sys.executable, str(ROOT / script), *arguments], env=env,
                                        capture_output=True, check=True, text=True)
                self.assertEqual(json.loads(result.stdout)['status'], 'DRY_RUN')
            self.assertFalse((directory / 'control').exists())
            self.assertFalse((directory / 'audit.json').exists())
            result = subprocess.run([sys.executable, str(ROOT / 'phase_fault_cli.py'), 'status',
                '--control-dir', str(directory / 'PRIVATE_SENTINEL')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn('PRIVATE_SENTINEL', result.stdout + result.stderr)

    def test_submit_faults_once_and_restores_only_target_clients_method(self):
        workflow_id, task_id, other_id = UUID(int=1), UUID(int=2), UUID(int=3)
        task = types.SimpleNamespace(id=task_id, workflow_id=workflow_id, task_name='fixture', job_ids=[])
        other = types.SimpleNamespace(id=other_id, workflow_id=UUID(int=9), task_name='fixture', job_ids=[])
        workflow = types.SimpleNamespace(tasks=[task_id])
        repository = types.SimpleNamespace(get=lambda value: {workflow_id: workflow, task_id: task, other_id: other}[value])
        transport = types.SimpleNamespace(close=Mock())
        native_run = Mock(return_value=types.SimpleNamespace(ok=True, stdout='Submitted batch job 42\n'))
        client = types.SimpleNamespace(workflowTracker=types.SimpleNamespace(repository=repository),
            run_commands=native_run, client=types.SimpleNamespace(get_transport=lambda: transport))

        def native_submit(client, command, env, task_id):
            try:
                return client.run_commands([command])
            except EOFError:
                return client.run_commands([command])

        recovery = types.SimpleNamespace(submit=native_submit, download=Mock())
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            control = {'armed': True, 'case_id': str(UUID(int=4)), 'workflow_id': str(workflow_id),
                       'task_name': 'fixture', 'phases': ['submit'], 'mode': 'inline', 'remote_parent': '/private-fixture'}
            write_report(directory / 'control.json', control)
            with patch.dict(sys.modules, {'biomero': types.SimpleNamespace(ssh_recovery=recovery)}), \
                    patch('importlib.metadata.version', return_value='test'):
                phase_fault_hook.install(directory)
                recovery.submit(client, 'sbatch --job-name=biomero-' + str(other_id), {}, other_id)
                transport.close.assert_not_called()
                recovery.submit(client, 'sbatch --job-name=biomero-' + str(task_id), {}, task_id)
                transport.close.assert_called_once()
                self.assertIs(client.run_commands, native_run)
                report = json.loads((directory / (control['case_id'] + '-submit.json')).read_text())
                self.assertEqual(report['status'], 'RECOVERED')
                self.assertEqual(report['faults'], 1)
                self.assertEqual(report['attempts'], 2)
                self.assertEqual(set(report['accepted_job_ids']), {42})
                recovery.submit(client, 'sbatch --job-name=biomero-' + str(task_id), {}, task_id)
                transport.close.assert_called_once()

    def test_zip_wrong_workflow_and_small_fixture_never_fault(self):
        workflow_id, task_id = UUID(int=1), UUID(int=2)
        task = types.SimpleNamespace(id=task_id, workflow_id=workflow_id, task_name='fixture', job_ids=[42])
        workflow = types.SimpleNamespace(tasks=[task_id])
        repository = types.SimpleNamespace(get=lambda value: {workflow_id: workflow, task_id: task}[value])
        native_download = Mock(return_value='untouched')
        recovery = types.SimpleNamespace(submit=lambda *a, **kw: None, download=native_download)
        client = types.SimpleNamespace(workflowTracker=types.SimpleNamespace(repository=repository),
                                       run_read_only=Mock(return_value=types.SimpleNamespace(stdout='4096')))
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            control = {'armed': True, 'case_id': str(UUID(int=4)), 'workflow_id': str(workflow_id),
                       'task_name': 'fixture', 'phases': ['zip'], 'mode': 'inline', 'remote_parent': '/private-fixture'}
            write_report(directory / 'control.json', control)
            with patch.dict(sys.modules, {'biomero': types.SimpleNamespace(ssh_recovery=recovery)}):
                phase_fault_hook.install(directory)
                wrong = '/private-fixture/not-' + str(workflow_id) + '/42_out.zip'
                self.assertEqual(recovery.download(client, wrong, name), 'untouched')
                client.run_read_only.assert_not_called()
                correct = '/private-fixture/biomero_' + str(workflow_id) + '/42_out.zip'
                self.assertEqual(recovery.download(client, correct, name), 'untouched')
                report = json.loads((directory / (control['case_id'] + '-zip.json')).read_text())
                self.assertEqual(report['status'], 'REFUSED')
                self.assertFalse(list(directory.glob('*.claimed')))


if __name__ == '__main__':
    unittest.main()
