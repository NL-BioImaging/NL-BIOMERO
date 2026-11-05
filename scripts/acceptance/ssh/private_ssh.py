"""Private TCP relay and bounded, allowlisted evidence for SSH integration tests."""
import contextlib
import importlib.metadata
import json
import logging
import os
from pathlib import Path
import select
import socket
import threading
import time


class Relay:
    """Pause only sockets accepted by this loopback listener; never the SSH service."""

    def __init__(self, upstream):
        self.upstream = upstream
        self.pause = threading.Event()
        self.stop = threading.Event()
        self.sockets = []
        self.forwarders = []
        self.listener = socket.socket()
        self.listener.bind(('127.0.0.1', 0))
        self.listener.listen()
        self.listener.settimeout(.2)
        self.port = self.listener.getsockname()[1]
        self.thread = threading.Thread(target=self.accept, daemon=True)
        self.thread.start()

    def accept(self):
        while not self.stop.is_set():
            try:
                local, _ = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            try:
                remote = socket.create_connection(self.upstream, timeout=5)
                remote.settimeout(None)
            except OSError:
                local.close()
                continue
            self.sockets.extend((local, remote))
            thread = threading.Thread(target=self.forward, args=(local, remote), daemon=True)
            self.forwarders.append(thread)
            thread.start()

    def forward(self, local, remote):
        try:
            while not self.stop.is_set():
                if self.pause.is_set():
                    self.stop.wait(.05)
                    continue
                readable, _, _ = select.select([local, remote], [], [], .1)
                for source in readable:
                    data = source.recv(65536)
                    if not data:
                        return
                    (remote if source is local else local).sendall(data)
        except OSError:
            pass
        finally:
            local.close()
            remote.close()

    def close(self):
        self.stop.set()
        self.pause.clear()
        self.listener.close()
        self.thread.join(6)
        for endpoint in self.sockets:
            try:
                endpoint.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            endpoint.close()
        deadline = time.monotonic() + 2
        for thread in self.forwarders:
            thread.join(max(0, deadline - time.monotonic()))


def require_known_host(connection):
    """Load existing user known_hosts before enforcing native strict policy."""
    import paramiko
    connection.client.load_system_host_keys()
    connection.client.set_missing_host_key_policy(paramiko.RejectPolicy())


def proxy_client(original, recovery_window, detection_timeout):
    """Reuse existing authentication and a verified host key without exposing them."""
    from biomero import SlurmClient
    import paramiko
    if not original.is_connected:
        require_known_host(original)
        original.open()
    if original.gateway is not None:
        raise ValueError('gateway_adapter_required')
    key = original.client.get_transport().get_remote_server_key()
    connect = dict(original.connect_kwargs)
    connect['channel_timeout'] = detection_timeout
    if 'key_filename' not in connect and original.ssh_config.get('identityfile'):
        connect['key_filename'] = [os.path.expanduser(p) for p in original.ssh_config['identityfile']]
    relay = Relay((original.host, original.port))
    proxy = None
    try:
        proxy = SlurmClient(host='127.0.0.1', port=relay.port, user=original.user,
                            connect_kwargs=connect, config_only=True,
                            slurm_model_repos={}, slurm_model_images={},
                            ssh_recovery_timeout=recovery_window)
        proxy.client.get_host_keys().add('[127.0.0.1]:' + str(relay.port), key.get_name(), key)
        proxy.client.set_missing_host_key_policy(paramiko.RejectPolicy())
        proxy.open()
        return relay, proxy
    except BaseException:
        relay.close()
        if proxy is not None:
            proxy.close()
        raise


@contextlib.contextmanager
def quiet_dependencies():
    """Standalone probes emit structured evidence, never captured commands/errors."""
    previous = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        with open(os.devnull, 'w') as sink:
            with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                yield
    finally:
        logging.disable(previous)


def write_report(path, report):
    path = Path(path)
    temporary = path.with_suffix('.new')
    temporary.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    temporary.chmod(0o600)
    temporary.replace(path)


def version():
    return importlib.metadata.version('biomero')


def close_owned(*resources):
    errors = []
    for resource in resources:
        if resource is not None:
            try:
                resource.close()
            except Exception as error:
                errors.append(type(error).__name__)
    return errors


def common_arguments(parser):
    parser.add_argument('--enable-faults', action='store_true', help='Explicitly allow this scoped integration fault')
    parser.add_argument('--dry-run', action='store_true', help='Validate arguments only; no SSH connection or mutation')
    parser.add_argument('--config-file', default='', help='Existing BIOMERO config; authoritative config env still takes precedence')
    parser.add_argument('--output', type=Path, required=True, help='New local JSON evidence file (no raw logs)')


def validate_common(parser, args, *, require_faults=True):
    if not __debug__ and not args.dry_run:
        parser.error('Live acceptance requires assertions; remove -O and PYTHONOPTIMIZE')
    if require_faults and not args.dry_run and not args.enable_faults:
        parser.error('Live probes require --enable-faults')
    if args.output.exists() or not args.output.parent.is_dir():
        parser.error('Output must be a new file in an existing private directory')


def finish(args, report, operation):
    """Never serialize an exception message, command, config, host or local path."""
    os.umask(0o077)
    if args.dry_run:
        print(json.dumps({'status': 'DRY_RUN', 'phase': report['phase']}))
        return 0
    if not __debug__:
        print(json.dumps({'status': 'REFUSED', 'error_type': 'AssertionsDisabled'}))
        return 2
    code = 2
    try:
        with quiet_dependencies():
            report['biomero'] = version()
            operation(report)
        report['status'] = 'PASS'
        code = 0
    except KeyboardInterrupt:
        report.update(status='INTERRUPTED', error_type='KeyboardInterrupt')
        code = 130
    except Exception as error:
        report.update(status='FAIL', error_type=type(error).__name__)
    try:
        write_report(args.output, report)
    except OSError as error:
        print(json.dumps({'status': 'REPORT_WRITE_FAILED', 'error_type': type(error).__name__}))
        return 2
    print(json.dumps(report, sort_keys=True))
    return code
