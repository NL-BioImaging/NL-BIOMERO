"""No site credentials, services, Slurm jobs or external network are used here."""
import contextlib
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import private_ssh
import workflow_hook


class OfflineTests(unittest.TestCase):
    def test_private_relay_pause_restore_and_cleanup(self):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen()

        def echo():
            endpoint, _ = listener.accept()
            with endpoint:
                while data := endpoint.recv(1024):
                    endpoint.sendall(data)

        echo_thread = threading.Thread(target=echo, daemon=True)
        echo_thread.start()
        relay = private_ssh.Relay(listener.getsockname())
        try:
            with socket.create_connection(('127.0.0.1', relay.port)) as client:
                client.settimeout(2)
                client.sendall(b'before')
                self.assertEqual(client.recv(100), b'before')
                relay.pause.set()
                time.sleep(.2)
                client.sendall(b'after')
                client.settimeout(.2)
                with self.assertRaises(socket.timeout):
                    client.recv(100)
                relay.pause.clear()
                client.settimeout(2)
                self.assertEqual(client.recv(100), b'after')
        finally:
            relay.close()
            listener.close()
            echo_thread.join(2)
        self.assertFalse(relay.thread.is_alive())
        self.assertFalse(any(thread.is_alive() for thread in relay.forwarders))

    def test_exception_and_subprocess_output_are_not_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            args = types.SimpleNamespace(dry_run=False, output=Path(directory) / 'report.json')
            def fail(report):
                print('PRIVATE_STDOUT_SENTINEL')
                raise subprocess.CalledProcessError(1, ['PRIVATE_COMMAND_SENTINEL'],
                                                    output='PRIVATE_OUTPUT_SENTINEL',
                                                    stderr='PRIVATE_ERROR_SENTINEL')
            output = io.StringIO()
            with patch.object(private_ssh, 'version', return_value='test'), contextlib.redirect_stdout(output):
                self.assertEqual(private_ssh.finish(args, {'phase': 'test'}, fail), 2)
            self.assertNotIn('PRIVATE_', output.getvalue() + args.output.read_text())
            self.assertEqual(json.loads(args.output.read_text())['error_type'], 'CalledProcessError')

    def test_help_and_dry_run_never_import_runtime_or_write_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / 'biomero.py').write_text("raise AssertionError('runtime imported during dry run')")
            env = dict(os.environ, PYTHONPATH=str(directory))
            shared = ['--dry-run', '--output', str(directory / 'report.json')]
            cases = {
                'check_monitor.py': shared + ['--job-id', '1'],
                'check_allocation.py': shared + ['--remote-parent', '/private-test-scratch'],
                'audit_workflow.py': shared + ['--workflow-id', str(UUID(int=1)), '--task-id', str(UUID(int=2)), '--job-id', '1'],
                'workflow_hook.py': ['arm', '--dry-run', '--control-dir', str(directory / 'control'),
                                     '--mode', 'inline', '--workflow-id', str(UUID(int=1)),
                                     '--task-id', str(UUID(int=2)), '--job-id', '1'],
            }
            for script, args in cases.items():
                with self.subTest(script=script):
                    subprocess.run([sys.executable, str(ROOT / script), '--help'], env=env,
                                   check=True, capture_output=True)
                    result = subprocess.run([sys.executable, str(ROOT / script), *args], env=env,
                                            check=True, capture_output=True, text=True)
                    self.assertEqual(json.loads(result.stdout)['status'], 'DRY_RUN')
            self.assertFalse((directory / 'report.json').exists())
            self.assertFalse((directory / 'control').exists())

    def test_hook_never_faults_unarmed_wrong_job_or_completed_job(self):
        class Client:
            def check_job_status(self, ids, *args, **kwargs):
                return {ids[0]: 'COMPLETED'}, None

        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            with patch.dict(sys.modules, {'biomero': types.SimpleNamespace(SlurmClient=Client)}):
                workflow_hook.install(directory)
            client = Client()
            client._ssh_recovery_state = types.SimpleNamespace(heartbeats={1: lambda: None}, deadline=None, timeout=10)
            client.workflowTracker = types.SimpleNamespace(repository=types.SimpleNamespace(
                get=lambda value: types.SimpleNamespace(tasks=[UUID(int=2)], job_ids=[1])))
            with patch.object(workflow_hook, 'proxy_client', side_effect=AssertionError('must not fault')):
                self.assertEqual(client.check_job_status([1])[0][1], 'COMPLETED')
                control = dict(armed=True, case_id=str(UUID(int=3)), mode='inline', workflow_id=str(UUID(int=1)),
                               task_id=str(UUID(int=2)), job_id=1, pause_seconds=2,
                               detection_timeout=.5, expect='recovered')
                private_ssh.write_report(directory / 'control.json', control)
                self.assertEqual(client.check_job_status([2])[0][2], 'COMPLETED')
                self.assertEqual(client.check_job_status([1])[0][1], 'COMPLETED')
            self.assertFalse(list(directory.glob('*.claimed')))

    def test_optimized_python_refuses_live_probe_before_runtime_import(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / 'biomero.py').write_text("raise RuntimeError('must not import runtime')")
            result = subprocess.run(
                [sys.executable, '-O', str(ROOT / 'check_monitor.py'), '--enable-faults',
                 '--job-id', '1', '--output', str(directory / 'report.json')],
                env=dict(os.environ, PYTHONPATH=str(directory)), capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn('Live acceptance requires assertions', result.stderr)
            self.assertNotIn('must not import runtime', result.stderr)
            self.assertFalse((directory / 'report.json').exists())

    def test_status_rejects_unexpected_errors_and_missing_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            case_id = str(UUID(int=4))
            private_ssh.write_report(directory / 'control.json', {'case_id': case_id})
            report = dict(status='MONITOR_RAISED', expect='timeout', error_type='ValueError',
                          heartbeats=[1, 2], cleanup_errors=[],
                          events=[{'event': 'private_connection_cleaned_up'}])
            for error_type, events, expected in (
                ('ValueError', report['events'], 2),
                ('SSHRecoveryTimeout', [], 2),
                ('SSHRecoveryTimeout', report['events'], 0),
            ):
                report.update(error_type=error_type, events=events)
                private_ssh.write_report(directory / (case_id + '.json'), report)
                result = subprocess.run([sys.executable, str(ROOT / 'workflow_hook.py'), 'status',
                                         '--control-dir', str(directory)], capture_output=True, text=True)
                self.assertEqual(result.returncode, expected)
                self.assertEqual(json.loads(result.stdout)['phase_check_passed'], expected == 0)


class TrackingRuntimeTest(unittest.TestCase):
    def test_real_configured_tracker_initializes_without_reset_and_replays(self):
        """Requires installed core; only SSH/descriptor fetch are replaced."""
        from biomero import SlurmClient, EngineManager
        from audit_workflow import configured_client
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            url = 'sqlite:///' + str(directory / 'events.sqlite').replace('\\', '/')
            config = directory / 'config.ini'
            config.write_text('[SSH]\nhost=localhost\n[ANALYTICS]\ntrack_workflows=true\n'
                              'enable_job_accounting=false\nenable_job_progress=false\n'
                              'enable_workflow_analytics=false\nsqlalchemy_url=' + url + '\n')
            env = {'BIOMERO_SLURM_CONFIG_FILE': str(config), 'SQLALCHEMY_URL': url,
                   'PERSISTENCE_MODULE': 'eventsourcing_sqlalchemy'}
            EngineManager.close_engine()
            try:
                with patch.dict(os.environ, env), patch.object(SlurmClient, 'validate'), \
                     patch.object(SlurmClient, 'init_workflows'):
                    with configured_client(str(config)) as client:
                        identity = client.workflowTracker.initiate_workflow('fixture', '', 0, 0)
                    with configured_client(str(config)) as second:
                        self.assertEqual(second.workflowTracker.repository.get(identity).id, identity)
            finally:
                EngineManager.close_engine()


if __name__ == '__main__':
    unittest.main()
