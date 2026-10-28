import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamdock_now_playing.runtime import data_directory


class DevelopmentIsolationTests(unittest.TestCase):
    def test_runtime_override_is_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            target = str(Path(directory) / 'only-development')
            with patch.dict('os.environ', {'STREAMDOCK_NOW_PLAYING_DATA_DIR': target}):
                self.assertEqual(data_directory(), Path(target))

    def test_deployment_preserves_stable_files_and_inputs(self):
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location('deploy_development', root / 'tools/deploy_development.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            host = Path(directory) / 'host'
            stable_plugin = host / 'plugins/local.ajazz.media.sdPlugin'
            stable_plugin.mkdir(parents=True)
            (stable_plugin / 'manifest.json').write_text('stable sentinel')
            template = Path(directory) / 'stable.json'
            source = {'Name': 'Spotify Media', 'Actions': {
                '0,0': {'UUID': 'local.ajazz.media.tile', 'Settings': {'tile': 0}, 'ActionID': 'old'},
                '3,1': {'UUID': 'local.ajazz.media.tracks', 'Settings': {}, 'ActionID': 'old-knob'}}}
            template.write_text(json.dumps(source))
            python = Path(directory) / 'pythonw.exe'; python.write_bytes(b'not executed')
            receipt = module.deploy(host, template, python, Path(directory) / 'runtime')
            self.assertEqual((stable_plugin / 'manifest.json').read_text(), 'stable sentinel')
            self.assertEqual(json.loads(template.read_text()), source)
            created = json.loads((Path(receipt['profile_dir']) / 'manifest.json').read_text())
            self.assertEqual(created['Actions']['0,0']['Settings'], {'tile': 0})
            self.assertEqual(created['Actions']['3,1']['UUID'], 'org.streamdock.nowplaying.public.tracks')
            self.assertNotEqual(created['Actions']['3,1']['ActionID'], 'old-knob')
            with self.assertRaises(FileExistsError):
                module.deploy(host, template, python, Path(directory) / 'runtime')
