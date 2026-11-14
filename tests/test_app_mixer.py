import unittest
from unittest.mock import Mock

from streamdock_now_playing.app_mixer import AppMixer
from streamdock_now_playing.audio_outputs import AudioOutputs
from test_behavior import FakeMedia,FakeWS
from streamdock_now_playing.streamdock import Plugin
import tempfile


def session(name, level=.5, muted=False, state=1):
    s=Mock(State=state)
    s.Process.name.return_value=name
    s.SimpleAudioVolume.GetMasterVolume.return_value=level
    s.SimpleAudioVolume.GetMute.return_value=muted
    return s


class MixerTests(unittest.TestCase):
    def test_only_selected_app_adjusts_all_its_sessions(self):
        a,b,c=session('chrome.exe',.99),session('Chrome.exe',.4,True),session('Spotify.exe')
        expired=session('Gone.exe',state=2)
        mixer=AppMixer(lambda:[a,b,c,expired]);mixer.refresh()
        self.assertEqual([app.name for app in mixer.apps],['chrome.exe','spotify.exe'])
        self.assertTrue(mixer.apps[0].mixed)
        mixer.select(0)
        mixer.adjust(2)
        a.SimpleAudioVolume.SetMasterVolume.assert_called_once_with(1,None)
        self.assertAlmostEqual(b.SimpleAudioVolume.SetMasterVolume.call_args.args[0],.42)
        c.SimpleAudioVolume.SetMasterVolume.assert_not_called()
        mixer.adjust(None)
        a.SimpleAudioVolume.SetMute.assert_called_once_with(True,None)
        b.SimpleAudioVolume.SetMute.assert_called_once_with(True,None)
        c.SimpleAudioVolume.SetMute.assert_not_called()

    def test_disappeared_app_does_not_adjust_another(self):
        a,b=session('First.exe'),session('Second.exe')
        sessions=[a,b]
        mixer=AppMixer(lambda:sessions);mixer.refresh();mixer.select(0)
        sessions.remove(a);mixer.adjust(2)
        b.SimpleAudioVolume.SetMasterVolume.assert_not_called()

    def test_output_switch_requires_current_valid_selection(self):
        items=[('a','Speakers'),('b','Headphones')]
        active=['a']
        switch=Mock(side_effect=lambda key:active.__setitem__(0,key))
        outputs=AudioOutputs(lambda:(items,active[0]),switch);outputs.refresh(initial=True)
        outputs.select(0)
        switch.assert_not_called()
        outputs.apply();switch.assert_called_once_with('b')
        self.assertEqual(outputs.message,'切替完了')
        items.pop();outputs.apply();self.assertEqual(switch.call_count,1)


class KnobRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_desktop_mixer_and_output_keep_master_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Plugin(provider=FakeMedia(),data_dir=directory,config={})
            p.ws=FakeWS();p.modes.active='desktop';p.master_audio=Mock()
            p.master_audio.command.return_value='VOL 50%'
            a=session('Spotify.exe')
            p.desktop.mixer=AppMixer(lambda:[a])
            switch=Mock()
            p.desktop.outputs=AudioOutputs(lambda:([('a','Speakers')],'a'),switch)
            for role in ('seek','volume','tracks','back'):
                p.contexts[role]={'role':role,'settings':{}}
            async def event(role,name,ticks=0):
                await p.event({'event':name,'context':role,'payload':{'ticks':ticks}})
            await event('seek','dialDown');self.assertTrue(p.desktop.mixing)
            await event('volume','dialRotate',1)
            a.SimpleAudioVolume.SetMasterVolume.assert_called_once_with(.52,None)
            p.master_audio.command.assert_not_called()
            await event('tracks','dialDown');self.assertTrue(p.desktop.choosing_output)
            await event('seek','dialDown');switch.assert_called_once_with('a')
            await event('back','keyDown');self.assertTrue(p.desktop.mixing)
            await event('seek','dialDown');self.assertFalse(p.desktop.mixing)
            await event('volume','dialRotate',1)
            p.master_audio.command.assert_called_once_with(2)
