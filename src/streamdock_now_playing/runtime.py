"""Runtime data lives outside the source checkout and installed plugin."""
import json
import os
from pathlib import Path


def data_directory():
    base = Path(os.environ.get('LOCALAPPDATA', Path.home() / '.local' / 'share'))
    directory = Path(os.environ['STREAMDOCK_NOW_PLAYING_DATA_DIR']) if os.environ.get('STREAMDOCK_NOW_PLAYING_DATA_DIR') else base / 'streamdock-now-playing'
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def read_config(directory):
    path = directory / 'config.json'
    if not path.exists():
        return {}
    config = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(config, dict):
        raise ValueError('Configuration must be an object')
    if not isinstance(config.get('preferred_source', ''), str):
        raise ValueError('preferred_source must be a string')
    mappings = config.get('audio_mappings', [])
    if not isinstance(mappings, list):
        raise ValueError('audio_mappings must be a list')
    for item in mappings:
        if (not isinstance(item, dict) or
            not all(isinstance(item.get(k), str) and item[k] for k in ('source_contains', 'process_name'))):
            raise ValueError('Invalid audio mapping')
    return config

def load_startup_config(directory,required=False,retry_seconds=5,sleeper=None):
    """An installed launcher must not silently boot an unconfigured instance."""
    import time
    sleeper=sleeper or time.sleep
    deadline=time.monotonic()+retry_seconds
    while required and not (directory/'config.json').is_file():
        if time.monotonic()>=deadline:raise FileNotFoundError('Required runtime config.json is missing: '+repr(str(directory))+'; env='+repr(__import__('os').environ.get('STREAMDOCK_NOW_PLAYING_DATA_DIR')))
        sleeper(min(.25,max(0,deadline-time.monotonic())))
    return read_config(directory)
