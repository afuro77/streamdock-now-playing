"""Stage a plugin; installing is explicit and refuses to overwrite existing plugins."""
import argparse
import json
import os
import shutil
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_FOLDER = 'org.streamdock.nowplaying.public.sdPlugin'  # Stable v1 action namespace.


def stage(destination, python):
    python = Path(python).resolve()
    if not python.is_file():
        raise ValueError('The requested Python executable does not exist')
    if any(char in str(python) for char in '\r\n%"'):
        raise ValueError('The executable path cannot be safely represented in a batch launcher')
    destination = Path(destination).resolve()
    if destination.exists():
        raise FileExistsError('Staging destination exists; use a new directory')
    destination.mkdir(parents=True)
    shutil.copy2(ROOT / 'plugin' / 'manifest.json', destination / 'manifest.json')
    # Original geometric icon. No album artwork, logos or font files.
    image = Image.new('RGB', (128, 128), '#10261f')
    draw = ImageDraw.Draw(image)
    for x in range(3):
        for y in range(2):
            draw.rounded_rectangle((10 + x*30, 20 + y*32, 34 + x*30, 44 + y*32), radius=4, fill='#55caa2')
    draw.ellipse((103, 44, 120, 61), fill='#55caa2')
    image.save(destination / 'icon.png')
    (destination / 'launch.bat').write_text(
        f'@echo off\n"{python}" -m streamdock_now_playing %*\n', encoding='utf-8')
    # Generated paths stay only in ignored staging / installed files.
    marker = {'project': 'streamdock-now-playing', 'format': 1}
    (destination / 'installation.json').write_text(json.dumps(marker), encoding='utf-8')
    shutil.copy2(ROOT / 'LICENSE', destination / 'LICENSE')
    shutil.copytree(ROOT / 'licenses', destination / 'licenses')
    shutil.copy2(ROOT / 'THIRD_PARTY_NOTICES.md', destination / 'THIRD_PARTY_NOTICES.md')
    return destination


def install(staged, destination):
    import psutil
    if any((p.info['name'] or '').lower() == 'stream dock ajazz.exe'
           for p in psutil.process_iter(['name'])):
        raise RuntimeError('Exit the host before installation')
    destination = Path(destination).resolve()
    if destination.exists():
        raise FileExistsError('Existing plugin retained. Follow docs/MIGRATION.md')
    shutil.copytree(staged, destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--install', action='store_true')
    args = parser.parse_args()
    staged = stage(args.stage, args.python)
    if args.install:
        if os.name != 'nt':
            parser.error('Host installation is Windows-only')
        install(staged, Path(os.environ['APPDATA']) / 'HotSpot' / 'StreamDock' / 'plugins' / PLUGIN_FOLDER)
    print('Plugin staged. No profiles or startup registrations were changed.')


if __name__ == '__main__': main()
