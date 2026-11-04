import unittest
from streamdock_now_playing.youtube import YouTubeMode
from streamdock_now_playing.youtube_browser import YouTubeBrowser


class SpeedTests(unittest.IsolatedAsyncioTestCase):
    def test_rate_telemetry_freshness_source_and_validation(self):
        browser=self.browser()
        self.assertIsNone(browser.playback_rate())
        browser.register({'tab':4,'page':'https://www.youtube.com/watch?v=abcdefghijk','rate':1.75})
        self.assertEqual(browser.playback_rate(),1.75)
        browser.clock=lambda:16
        self.assertIsNone(browser.playback_rate())
        browser.register({'tab':4,'page':'https://www.youtube.com/','rate':1.5})
        self.assertIsNone(browser.playback_rate())
        browser.register({'tab':4,'page':'https://www.youtube.com/watch?v=abcdefghijk','rate':float('nan')})
        self.assertIsNone(browser.playback_rate())

    def test_badge_changes_only_status_tile_and_keeps_input_immutable(self):
        from streamdock_now_playing.renderer import LayoutRenderer,speed_badge,playback_rate_text
        layout=LayoutRenderer();tiles=layout.expanded_artwork(None);original=list(tiles)
        result=speed_badge(tiles,1.5)
        self.assertEqual(tiles,original);self.assertEqual(result[:5],tiles[:5])
        self.assertNotEqual(result[5],tiles[5])
        self.assertEqual(playback_rate_text(None),'--x')
        self.assertEqual(playback_rate_text(1.25),'1.25x')
        snapshot={'playing':True,'position':12,'duration':100}
        self.assertNotEqual(layout.status(snapshot),layout.status({**snapshot,'playback_rate':1.5}))
        self.assertEqual(layout.status(snapshot,'VOL 40%'),layout.status({**snapshot,'playback_rate':1.5},'VOL 40%'))

    def browser(self):
        browser=YouTubeBrowser(lambda:10)
        browser.register({'tab':4,'page':'https://www.youtube.com/watch?v=abcdefghijk'})
        return browser

    def test_speed_command_without_browse_and_ack_is_not_selection(self):
        browser=self.browser()
        self.assertTrue(browser.cycle_speed())
        command=browser.state()['command']
        self.assertEqual(command['kind'],'speed')
        self.assertFalse(browser.cycle_speed())
        self.assertFalse(browser.acknowledge({'id':'stale','ok':True,'rate':2}))
        self.assertTrue(browser.acknowledge({'id':command['id'],'ok':True,'rate':1.25}))
        self.assertEqual(browser.take_speed_result(),'SPEED 1.25x')
        self.assertFalse(browser.take_success())

    def test_failure_and_invalid_rate(self):
        for result in ({'ok':False},{'ok':True,'rate':float('nan')},{'ok':True,'rate':True}):
            browser=self.browser();browser.cycle_speed()
            browser.acknowledge({'id':browser.state()['command']['id'],**result})
            self.assertEqual(browser.take_speed_result(),'SPEED ERROR')

    def test_missing_home_and_stale_tab(self):
        browser=YouTubeBrowser(lambda:10)
        self.assertFalse(browser.cycle_speed())
        browser.register({'tab':4,'page':'https://www.youtube.com/'})
        self.assertFalse(browser.cycle_speed())
        browser=self.browser();browser.clock=lambda:30
        self.assertFalse(browser.cycle_speed())

    def test_timeout(self):
        browser=self.browser();browser.cycle_speed();browser.clock=lambda:30
        self.assertEqual(browser.take_speed_result(),'SPEED ERROR')
        self.assertIsNone(browser.state()['command'])

    async def test_right_press_only_outside_list_preserves_view(self):
        mode=YouTubeMode(clock=lambda:10);mode.browser=self.browser()
        for view in ('normal','metadata','artwork'):
            mode.view=view
            await mode.input('seek','dialDown')
            self.assertEqual(mode.view,view)
            self.assertIsNone(mode.browser.state()['command'])
            self.assertEqual(mode.speed_adjust_until,15)
            await mode.input('seek','dialRotate',ticks=1)
            self.assertEqual(mode.browser.state()['command']['steps'],1)
            mode.browser.acknowledge({'id':mode.browser.state()['command']['id'],'ok':True,'rate':1.5})
        mode.browser.take_speed_result();mode.view='browser'
        await mode.input('seek','dialDown')
        self.assertIsNone(mode.browser.state()['command'])

    async def test_adjustment_expires_and_rotation_returns_to_seek(self):
        from test_youtube_mode import FakeService
        now=[10];service=FakeService();mode=YouTubeMode(service=service,clock=lambda:now[0]);mode.browser=self.browser()
        await mode.input('seek','dialDown')
        before=mode.frame();now[0]=16
        self.assertNotEqual(mode.frame()[5],before[5])
        await mode.input('seek','dialRotate',ticks=-1)
        self.assertEqual(service.calls,[('seek',-5)])
        self.assertIsNone(mode.browser.state()['command'])

    def test_fast_rotation_is_queued_after_ack(self):
        browser=self.browser();browser.adjust_speed(1)
        first=browser.state()['command'];browser.adjust_speed(-2);browser.adjust_speed(1)
        browser.acknowledge({'id':first['id'],'ok':True,'rate':1.25})
        second=browser.state()['command']
        self.assertNotEqual(first['id'],second['id']);self.assertEqual(second['steps'],-1)
        browser.acknowledge({'id':second['id'],'ok':True,'rate':1})
        self.assertIsNone(browser.state()['command'])

    async def test_full_video_badge_only_during_adjustment(self):
        now=[10];mode=YouTubeMode(clock=lambda:now[0]);mode.view='artwork'
        before=mode.frame();await mode.input('seek','dialDown');during=mode.frame()
        self.assertEqual(before[:5],during[:5]);self.assertNotEqual(before[5],during[5])
        now[0]=16;self.assertEqual(mode.frame(),before)
