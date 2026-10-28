import tempfile
import unittest
from unittest.mock import patch, Mock
from streamdock_now_playing.streamdock import Plugin
from test_behavior import FakeMedia, FakeWS
from test_layout_v11 import SNAPSHOT


class FixedNavigationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.p=Plugin(provider=FakeMedia(),data_dir=self.directory.name,config={})
        self.p.snapshot=dict(SNAPSHOT);self.p.ws=FakeWS()
        self.p.queue_state.request=Mock()
        for role in ('mode','player','back'):
            self.p.contexts[role]={'role':role,'settings':{}}
        for tile in range(6):self.p.contexts[str(tile)]={'role':'tile','settings':{'tile':tile}}
    async def press(self,role):
        p=self.p
        await p.event({'event':'keyDown','context':role})
        if role=='player':
            await p.event({'event':'keyUp','context':role})


    async def test_mode_toggle_global_and_return_normal_without_playback(self):
        for mode in ('normal','artwork','metadata','queue'):
            self.p.view_mode=mode;self.p.navigation=['metadata'];self.p.return_steps=2
            await self.press('mode')
            self.assertEqual(self.p.modes.active,'desktop')
            await self.press('mode')
            self.assertEqual(self.p.modes.active,'spotify')
            self.assertEqual(self.p.view_mode,'normal');self.assertEqual(self.p.navigation,[])
        self.assertEqual(self.p.provider.calls,[])

    async def test_browse_always_queue_and_back_restores_previous_screen(self):
        for mode in ('normal','artwork','metadata'):
            self.p.view_mode=mode;self.p.navigation=[];self.p.return_steps=2
            await self.press('player');await self.press('player')
            self.assertEqual(self.p.view_mode,'queue');self.assertEqual(self.p.navigation,[mode])
            self.assertEqual(self.p.nav_feedback,'QUEUE')
            await self.press('back')
            self.assertEqual(self.p.view_mode,mode);self.assertEqual(self.p.nav_feedback,'BACK')
        self.assertEqual(self.p.provider.calls,[])

    async def test_back_without_history_is_harmless_in_all_modes(self):
        for mode in ('normal','artwork','metadata','queue'):
            self.p.view_mode=mode;self.p.navigation=[];self.p.return_steps=0
            await self.press('back');self.assertEqual(self.p.view_mode,'normal')
        self.assertEqual(self.p.provider.calls,[])

    async def test_one_second_feedback_changes_only_bottom_right_and_disappears(self):
        with patch('streamdock_now_playing.streamdock.time.monotonic',return_value=100):
            await self.p.render();before=list(self.p.images)
            self.p.nav_feedback='HOME';self.p.nav_feedback_until=101;await self.p.render()
        self.assertEqual(self.p.images[:5],before[:5]);self.assertNotEqual(self.p.images[5],before[5])
        with patch('streamdock_now_playing.streamdock.time.monotonic',return_value=100.99):
            await self.p.render();self.assertEqual(self.p.nav_feedback,'HOME')
        with patch('streamdock_now_playing.streamdock.time.monotonic',return_value=101):
            await self.p.render()
        self.assertEqual(self.p.images,before);self.assertEqual(self.p.nav_feedback,'')

    async def test_queue_feedback_preserves_other_five_tiles(self):
        self.p.view_mode='queue'
        await self.p.render();before=list(self.p.images)
        await self.press('player')
        self.assertEqual(self.p.images[:5],before[:5]);self.assertNotEqual(self.p.images[5],before[5])

    async def test_key_release_does_not_navigate_again(self):
        await self.press('player')
        await self.p.event({'event':'keyUp','context':'back'})
        self.assertEqual(self.p.view_mode,'queue')
