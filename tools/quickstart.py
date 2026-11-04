"""Prepare the isolated public preview; --check performs no installation."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
NAMESPACE = 'org.streamdock.nowplaying.public.sdPlugin'


def host_running():
    result = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], check=True,
                            capture_output=True, text=True)
    names = {'stream dock ajazz.exe', 'stream dock.exe', 'streamdock.exe'}
    return any(row and row[0].lower() in names for row in csv.reader(result.stdout.splitlines()))


def preflight(root, host_data, runtime, running):
    root, host_data, runtime = map(Path, (root, host_data, runtime))
    if not host_data.is_dir():
        raise ValueError('Stream Dock data directory not found. Install and run the host first; or use --host-data.')
    if running:
        raise ValueError('Exit Stream Dock from its tray menu before installation. It will not be stopped automatically.')
    if (host_data / 'plugins' / NAMESPACE).exists():
        raise ValueError('Public plugin already exists; no files were changed. See docs/MIGRATION.md.')
    if runtime.exists() and (not runtime.is_dir() or any(runtime.iterdir())):
        raise ValueError('Runtime directory is not empty. Select a new directory with --runtime-dir.')
    if (root / '.venv').exists():
        raise ValueError('.venv already exists. Use the manual installation guide or a fresh source folder.')
    for path in (root.resolve(), runtime.resolve()):
        if any(c in str(path) for c in '\r\n%"'):
            raise ValueError('Source/runtime path cannot be represented safely by the host launcher.')
    return root / '.venv' / 'Scripts' / 'python.exe'


def setup(root, host_data, runtime, *, check=False, running=False, run=subprocess.run):
    python = preflight(root, host_data, runtime, running)
    commands = [
        [sys.executable, '-m', 'venv', str(Path(root) / '.venv')],
        [str(python), '-m', 'pip', 'install', '-r', str(Path(root) / 'requirements.txt')],
        [str(python), '-m', 'pip', 'install', '--no-deps', '-e', str(root)],
        [str(python), str(Path(root) / 'tools' / 'deploy_development.py'),
         '--host-data', str(host_data), '--runtime-dir', str(runtime),
         '--python', str(python.with_name('pythonw.exe'))],
    ]
    if not check:
        for command in commands:
            run(command, check=True, cwd=root)
    return {'check_only': check, 'profile': 'Now Playing OSS Preview',
            'runtime': str(runtime), 'commands': commands}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--install', action='store_true')
    parser.add_argument('--host-data', type=Path)
    parser.add_argument('--runtime-dir', type=Path)
    args = parser.parse_args()
    if os.name != 'nt' or sys.version_info < (3, 12):
        parser.error('Windows with Python 3.12 or newer is required.')
    host = args.host_data or Path(os.environ['APPDATA']) / 'HotSpot' / 'StreamDock'
    runtime = args.runtime_dir or Path(os.environ['LOCALAPPDATA']) / 'streamdock-now-playing-public'
    try:
        receipt = setup(ROOT, host.resolve(), runtime.resolve(), check=args.check, running=host_running())
    except (ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'{error}\nSetup stopped. Existing host profiles are retained. See docs/QUICKSTART.md.\n')
    print(json.dumps(receipt, indent=2))
    print('Checks passed; nothing installed.' if args.check else
          'Start Stream Dock and select Now Playing OSS Preview. Keep this source folder in place.')


if __name__ == '__main__':
    main()
