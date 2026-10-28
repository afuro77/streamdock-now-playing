"""Add an isolated v1.1 development plugin/profile without replacing stable files."""
import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from PIL import Image, ImageDraw

NAMESPACE = 'org.streamdock.nowplaying.public'
PROFILE_NAME = 'Now Playing OSS Preview'
ROOT = Path(__file__).resolve().parents[1]


def deploy(host_data, template_profile, python, runtime_dir):
    host_data, template_profile, python, runtime_dir = map(Path, (host_data, template_profile, python, runtime_dir))
    plugin_dir = host_data / 'plugins' / (NAMESPACE + '.sdPlugin')
    if plugin_dir.exists():
        raise FileExistsError('Development plugin already exists; stable files are never overwritten')
    if not python.is_file():
        raise ValueError('Python executable does not exist')
    for path in (ROOT / 'src', python, runtime_dir):
        if any(c in str(path) for c in '\r\n%"'):
            raise ValueError('Path cannot be safely represented in a batch launcher')
    profile = json.loads(template_profile.read_text(encoding='utf-8-sig'))
    manifest = json.loads((ROOT / 'plugin' / 'manifest.json').read_text(encoding='utf-8'))
    for action in manifest['Actions']:
        action['UUID'] = NAMESPACE + '.' + action['UUID'].rsplit('.', 1)[-1]
    manifest.update(Name=PROFILE_NAME, Category=PROFILE_NAME, Version='1.2.0', Description='Isolated development layout: four artwork tiles and two information tiles')
    profile_id = str(uuid.uuid4()).upper() + '.sdProfile'
    profile['Name'] = PROFILE_NAME
    profile['Pages'] = {'Current': profile_id, 'Pages': [profile_id]}
    for action in profile['Actions'].values():
        action['UUID'] = NAMESPACE + '.' + action['UUID'].rsplit('.', 1)[-1]
        action['ActionID'] = str(uuid.uuid4())
    profile_dir = host_data / 'profiles' / profile_id
    if profile_dir.exists():
        raise FileExistsError('New profile directory unexpectedly exists')
    runtime_dir.mkdir(parents=True, exist_ok=True)
    config_path = runtime_dir / 'config.json'
    if not config_path.exists():
        config_path.write_text((ROOT / 'examples' / 'config.example.json').read_text('utf-8'), encoding='utf-8')
    plugin_dir.mkdir(parents=True)
    (plugin_dir / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    (plugin_dir / 'launch.bat').write_text(
        '@echo off\nsetlocal DisableDelayedExpansion\n'
        f'set "PYTHONPATH={ROOT / "src"}"\n'
        f'set "STREAMDOCK_NOW_PLAYING_DATA_DIR={runtime_dir}"\n'
        f'"{python}" -m streamdock_now_playing %* --data-dir "{runtime_dir}"\n', encoding='utf-8')
    image = Image.new('RGB', (128, 128), '#10261f')
    draw = ImageDraw.Draw(image)
    for x in range(3):
        for y in range(2):
            draw.rounded_rectangle((8+x*38, 22+y*40, 40+x*38, 54+y*40), radius=4,
                                   fill='#55caa2' if x < 2 else '#e6c369')
    image.save(plugin_dir / 'icon.png')
    profile_dir.mkdir(parents=True)
    (profile_dir / 'manifest.json').write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding='utf-8')
    receipt = {'plugin_dir': str(plugin_dir), 'profile_dir': str(profile_dir), 'profile_name': PROFILE_NAME,
               'runtime_dir': str(runtime_dir), 'stable_files_modified': False}
    (runtime_dir / 'deployment.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template-profile', default=ROOT / 'examples/akp03j.profile.template.json', type=Path)
    parser.add_argument('--host-data', type=Path, default=Path(os.environ['APPDATA']) / 'HotSpot' / 'StreamDock')
    parser.add_argument('--python', type=Path, default=Path(sys.executable).with_name('pythonw.exe'))
    parser.add_argument('--runtime-dir', type=Path, default=Path(os.environ['LOCALAPPDATA']) / 'streamdock-now-playing-public')
    args = parser.parse_args()
    print(json.dumps(deploy(args.host_data, args.template_profile, args.python, args.runtime_dir), indent=2))


if __name__ == '__main__':
    main()
