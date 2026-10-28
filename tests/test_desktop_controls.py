import asyncio,tempfile,time,unittest
from unittest.mock import Mock,patch
from streamdock_now_playing.streamdock import Plugin
from streamdock_now_playing.desktop import DesktopHome
from streamdock_now_playing.master_audio import MasterAudio
from test_behavior import FakeMedia,FakeWS

class MasterTests(unittest.TestCase):
    def endpoint(self,value=.42,mute=False):
        endpoint=Mock();endpoint.GetMasterVolumeLevelScalar.return_value=value;endpoint.GetMute.return_value=mute
        return endpoint
    def test_step_and_clamp(self):
        for value,delta,expected in [(.42,2,.44),(.42,-2,.40),(.99,2,1),(.01,-2,0)]:
            endpoint=self.endpoint(value);MasterAudio(lambda:endpoint).command(delta)
            endpoint.SetMasterVolumeLevelScalar.assert_called_once()
            self.assertAlmostEqual(endpoint.SetMasterVolumeLevelScalar.call_args.args[0],expected)
    def test_mute_toggles(self):
        for mute in (True,False):
            endpoint=self.endpoint(mute=mute);MasterAudio(lambda:endpoint).command()
            endpoint.SetMute.assert_called_once_with(not mute,None)

class NavigationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.p=Plugin(provider=FakeMedia(),data_dir=self.temp.name,config={});self.p.ws=FakeWS()
        for role in ('mode','player','back','volume','tracks','seek'):self.p.contexts[role]={'role':role,'settings':{}}
        self.p.queue_state.request=Mock();self.p.playlists.request=Mock();self.p.master_audio=Mock();self.p.master_audio.command.return_value='VOL 42%'
    async def event(self,role,event='keyDown',ticks=0):await self.p.event({'event':event,'context':role,'payload':{'ticks':ticks}})
    async def tap_home(self):await self.event('player');await self.event('player','keyUp')
    async def test_short_press_opens_spotify_queue(self):
        self.p.view_mode='metadata';await self.tap_home()
        self.assertEqual(self.p.view_mode,'queue');self.p.queue_state.request.assert_called()
    async def test_long_playlist_release_never_fires_queue(self):
        self.p.home_hold_seconds=.01;await self.event('player');await self.p.home_hold_task
        self.assertEqual(self.p.view_mode,'playlists');await self.event('player','keyUp')
        self.assertEqual(self.p.view_mode,'playlists')
    async def test_desktop_long_home_unassigned(self):
        self.p.modes.active='desktop';await self.p.desktop.press(1)
        self.p.home_hold_seconds=.01;await self.event('player');await self.p.home_hold_task;await self.event('player','keyUp')
        self.assertEqual(self.p.desktop.detail,1)
        self.p.home_hold_seconds=.7
        await self.tap_home();self.assertIsNone(self.p.desktop.detail)
    async def test_mode_cancels_pending_home(self):
        self.p.modes.active='desktop'
        await self.event('player');task=self.p.home_hold_task
        await self.event('mode');await self.event('player','keyUp');await asyncio.gather(task,return_exceptions=True)
        self.assertEqual(self.p.modes.active,'spotify');self.p.queue_state.request.assert_not_called()
    async def test_guard_blocks_both_directions(self):
        for _ in range(2):
            await self.event('mode');await self.event('volume','dialRotate',1);await self.event('volume','dialDown')
        self.assertEqual(self.p.provider.calls,[]);self.p.master_audio.command.assert_not_called()
    async def test_desktop_master_only(self):
        self.p.modes.active='desktop'
        await self.event('volume','dialRotate',1);await self.event('volume','dialDown')
        self.assertEqual(self.p.master_audio.command.call_args_list[0].args,(2,))
        self.assertEqual(self.p.master_audio.command.call_args_list[1].args,(None,))
        self.assertEqual(self.p.provider.calls,[]);self.assertEqual(self.p.desktop.feedback,'VOL 42%')
    async def test_master_error_cannot_fall_into_spotify(self):
        self.p.modes.active='desktop';self.p.master_audio.command.side_effect=OSError()
        with self.assertLogs(level='ERROR'):await self.event('volume','dialRotate',1)
        self.assertEqual(self.p.provider.calls,[]);self.assertEqual(self.p.desktop.feedback,'AUDIO ERROR')
    async def test_reserved_knobs_and_single_page(self):
        self.p.modes.active='desktop'
        for role,event in [('tracks','dialRotate'),('tracks','dialDown'),('seek','dialRotate'),('seek','dialDown')]:await self.event(role,event,1)
        self.assertEqual(self.p.desktop.nav.page,0);self.assertEqual(self.p.provider.calls,[])
    async def test_two_pages_detail_back_home(self):
        h=DesktopHome({'pages':[{'items':[{'cell':1,'type':'weather'}]},{'items':[{'cell':2,'type':'clock'}]}]})
        h.page(1);self.assertEqual(set(h.widgets),{2});h.page(-1);await h.press(1)
        h.page(1);self.assertEqual(h.nav.page,0);h.back();self.assertIsNone(h.detail)
        h.page(1);h.home();self.assertEqual(h.nav.page,0);h.back();self.assertEqual(h.nav.page,0)
    async def test_feedback_only_empty_cell_expires(self):
        # The clock blinks each second; freeze it while testing feedback isolation.
        from datetime import datetime
        with patch('streamdock_now_playing.desktop.datetime') as clock:
            clock.now.return_value=datetime(2026,10,29,12,0,0)
            h=DesktopHome();before=h.frame()
            h.show_feedback('VOL 42%');after=h.frame();self.assertEqual(after[:5],before[:5]);self.assertNotEqual(after[5],before[5])
            h.feedback_until=0;self.assertEqual(h.frame(),before)
    async def test_home_back_never_return_original_track(self):
        self.p.return_steps=3;await self.event('back');await self.tap_home()
        self.assertEqual(self.p.provider.calls,[])
