import unittest,tempfile,json
from pathlib import Path
from streamdock_now_playing.runtime import load_startup_config
class StartupConfigTests(unittest.TestCase):
 def test_required_config_never_silently_defaults(self):
  with tempfile.TemporaryDirectory() as tmp:
   with self.assertRaises(FileNotFoundError):load_startup_config(Path(tmp),True,0)
 def test_loads_existing_saved_settings(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);cfg={'spotify':{'enabled':True},'playlist_bookmarks':[{'id':'x'}],'desktop':{'weather':{'location':'Ichikawa'}}};(p/'config.json').write_text(json.dumps(cfg),encoding='utf-8');self.assertEqual(load_startup_config(p,True),cfg)
 def test_delayed_config_availability_retried(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)
   def appeared(_):(p/'config.json').write_text('{"spotify":{"enabled":true}}',encoding='utf-8')
   self.assertTrue(load_startup_config(p,True,1,appeared)['spotify']['enabled'])
