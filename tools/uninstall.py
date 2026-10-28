"""Remove only a marked generated plugin; never remove host profiles or settings."""
import argparse
import json
import os
import shutil
from pathlib import Path


def remove_plugin(path, apply=False):
    path = Path(path).resolve()
    if path.name != 'org.streamdock.nowplaying.public.sdPlugin':
        raise ValueError('Unexpected plugin directory name')
    marker = path / 'installation.json'
    if not marker.is_file() or json.loads(marker.read_text('utf-8')).get('project') != 'streamdock-now-playing':
        raise ValueError('Unmarked plugin retained; use the legacy manual instructions')
    if apply:
        import psutil
        if any((p.info['name'] or '').lower() == 'stream dock ajazz.exe'
               for p in psutil.process_iter(['name'])):
            raise RuntimeError('Exit the host before uninstalling')
        shutil.rmtree(path)
    return str(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Actually remove the marked plugin')
    args = parser.parse_args()
    if os.name != 'nt': parser.error('Host uninstall is Windows-only')
    path = Path(os.environ['APPDATA']) / 'HotSpot' / 'StreamDock' / 'plugins' / 'org.streamdock.nowplaying.public.sdPlugin'
    print(('Removed: ' if args.apply else 'Would remove: ') + remove_plugin(path, args.apply))


if __name__ == '__main__': main()
