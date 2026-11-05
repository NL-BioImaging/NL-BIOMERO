#!/usr/bin/env python3
"""Install, arm or remove scoped phase hooks; never launch a workflow."""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import sysconfig
from uuid import UUID, uuid4

from private_ssh import write_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('install', 'arm', 'disarm', 'uninstall', 'status'))
    parser.add_argument('--control-dir', type=Path, required=True)
    parser.add_argument('--workflow-id', type=UUID)
    parser.add_argument('--mode', choices=('inline', 'detached'))
    parser.add_argument('--phase', action='append', choices=('submit', 'zip'))
    parser.add_argument('--task-name', help='Exact analysis task name in the supplied workflow')
    parser.add_argument('--remote-parent', help='Private Slurm data parent containing biomero_<workflow UUID>')
    parser.add_argument('--owner-uid', type=int)
    parser.add_argument('--owner-gid', type=int)
    parser.add_argument('--enable-faults', action='store_true')
    parser.add_argument('--ack-isolated-worker', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    directory = args.control_dir.absolute()
    if directory == Path(directory.anchor):
        parser.error('Choose a dedicated private control directory')
    if not __debug__ and not args.dry_run:
        parser.error('Live acceptance requires assertions; remove -O and PYTHONOPTIMIZE')
    if args.action in ('install', 'arm') and not args.dry_run:
        if not (args.enable_faults and args.ack_isolated_worker):
            parser.error('Install/arm require --enable-faults --ack-isolated-worker')
    if args.action == 'install' and (args.owner_uid is None or args.owner_gid is None):
        parser.error('Install requires the actual worker owner UID and GID')
    if args.action == 'arm':
        if not all((args.workflow_id, args.mode, args.phase, args.task_name, args.remote_parent)):
            parser.error('Arm requires workflow, mode, phase, task name and private remote parent')
        remote = PurePosixPath(args.remote_parent)
        if not remote.is_absolute() or '..' in remote.parts or str(remote) == '/':
            parser.error('Remote parent must be a private absolute directory, not root')
    if args.dry_run:
        print(json.dumps({'status': 'DRY_RUN', 'action': args.action}))
        return 0
    os.umask(0o077)
    try:
        pth = Path(sysconfig.get_paths()['purelib']) / 'zz_biomero_phase_acceptance.pth'
        bundle = str(Path(__file__).resolve().parent)
        content = (f'import sys; sys.path.insert(0, {bundle!r}); import phase_fault_hook; '
                   f'phase_fault_hook.install({str(directory)!r})\n')
        if args.action == 'install':
            if directory.exists() or pth.exists():
                raise FileExistsError('Refuse existing installation')
            directory.mkdir(mode=0o700)
            os.chown(directory, args.owner_uid, args.owner_gid)
            with pth.open('x', encoding='utf-8') as stream:
                stream.write(content)
            pth.chmod(0o644)
        elif args.action == 'arm':
            if directory.stat().st_uid != os.getuid():
                raise PermissionError('Arm as the actual worker user')
            old = json.loads((directory / 'control.json').read_text()) if (directory / 'control.json').exists() else {}
            if old.get('armed'):
                raise ValueError('Disarm previous case first')
            write_report(directory / 'control.json', {
                'armed': True, 'case_id': str(uuid4()), 'workflow_id': str(args.workflow_id),
                'mode': args.mode, 'phases': args.phase, 'task_name': args.task_name,
                'remote_parent': str(remote)})
        elif args.action in ('disarm', 'uninstall'):
            if (directory / 'control.json').exists():
                value = json.loads((directory / 'control.json').read_text())
                value['armed'] = False
                write_report(directory / 'control.json', value)
            if args.action == 'uninstall' and pth.exists():
                if pth.read_text(encoding='utf-8') != content:
                    raise ValueError('Refuse foreign hook removal')
                pth.unlink()
        else:
            control = json.loads((directory / 'control.json').read_text())
            reports = []
            for phase in control['phases']:
                if phase not in ('submit', 'zip'):
                    raise ValueError('Unknown phase')
                path = directory / (str(UUID(control['case_id'])) + '-' + phase + '.json')
                reports.append(json.loads(path.read_text()) if path.exists() else {'phase': phase, 'status': 'WAITING'})
            print(json.dumps({'reports': reports}, indent=2))
            return 0 if reports and all(r['status'] == 'RECOVERED' for r in reports) else 2
        print(json.dumps({'action': args.action, 'status': 'OK'}))
        return 0
    except Exception as error:
        print(json.dumps({'status': 'FAIL', 'error_type': type(error).__name__}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
