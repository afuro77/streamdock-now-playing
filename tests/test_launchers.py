import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from PIL import Image
from streamdock_now_playing.launcher import LauncherSettings,expand_target
from streamdock_now_playing.desktop import AppLauncherAction,DesktopHome
from streamdock_now_playing.desktop_icons import icon_panel


class LauncherTests(unittest.IsolatedAsyncioTestCase):
    async def test_unconfigured_slots_never_invoke_the_opener(self):
        for target in (None,'','   '):
            opener=Mock();widget=AppLauncherAction({'target':target},opener)
            self.assertFalse(widget.configured)
            await widget.press();opener.assert_not_called()
            self.assertEqual(widget.message,'起動先を設定')
            self.assertTrue(widget.render().startswith('data:image/png;base64,'))

    async def test_arbitrary_app_shortcut_and_url_use_the_configured_target(self):
        for target in ('notepad.exe','example.lnk','https://example.org/','steam://open/main'):
            opener=Mock();widget=AppLauncherAction({'label':'Example','target':target},opener)
            widget.render();opener.assert_not_called()
            await widget.press();opener.assert_called_once_with(target)
            self.assertEqual(widget.message,'起動しました')
            await widget.press();opener.assert_called_once()

    async def test_failure_is_local_feedback_and_can_retry(self):
        opener=Mock(side_effect=OSError('missing'));widget=AppLauncherAction({'target':'missing.lnk'},opener)
        await widget.press();self.assertEqual(widget.message,'起動できません')
        widget.until=0;opener.side_effect=None;await widget.press()
        self.assertEqual(widget.message,'起動しました')

    def test_existing_labels_targets_and_icon_only_rendering_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'icon.png';Image.new('RGBA',(80,80),'green').save(path)
            for label,target in (('STEAM','steam://open/main'),('CODEX','example-codex.lnk'),('LINE','example-line.lnk')):
                config={'label':label,'target':target,'icon_path':str(path),'icon_only':True}
                widget=AppLauncherAction(config,Mock())
                self.assertEqual(widget.settings.label,label);self.assertEqual(widget.settings.target,target)
                self.assertEqual(widget.render(),icon_panel([],'app_only',str(path)))
                self.assertEqual(widget.config,config)

    def test_missing_icon_uses_generic_launcher_pictogram(self):
        widget=AppLauncherAction({'label':'Example','target':'example.exe','icon_path':'missing-file.png'},Mock())
        expected=icon_panel([('Example',23,88,'white')],'launcher')
        self.assertEqual(widget.render(),expected)

    def test_settings_validation_and_environment_expansion(self):
        self.assertEqual(LauncherSettings.from_config({}).label,'APP')
        self.assertIsNone(LauncherSettings.from_config({'target':'  '}).target)
        for key in ('label','target','icon_path'):
            with self.assertRaises(ValueError):LauncherSettings.from_config({key:42})
        with self.assertRaises(ValueError):LauncherSettings.from_config({'icon_only':'yes'})
        with patch.dict('os.environ',{'AKP03J_TEST_APP':'notepad.exe'}):
            self.assertEqual(expand_target('$AKP03J_TEST_APP'),'notepad.exe')

    async def test_default_home_has_no_app_specific_target(self):
        home=DesktopHome()
        for cell in (3,4,5):
            widget=home.widgets[cell];widget.opener=Mock()
            await home.press(cell);widget.opener.assert_not_called()
            self.assertFalse(widget.configured)
        self.assertEqual(len(home.frame()),6)
        await home.close()
