import asyncio
import tempfile
import unittest
from pathlib import Path
from streamdock_now_playing.youtube import YouTubeMode
from streamdock_now_playing.desktop import ModeManager
from streamdock_now_playing.streamdock import Plugin
from streamdock_now_playing.browser_launcher import BrowserLauncher


class FakeService:
    def __init__(self):
        self.calls=[];self.s={'key':'one','source':'Chrome','title':'Video','artist':'Channel','position':10,'duration':60,'playing':True}
    async def snapshot(self):return dict(self.s)
    async def artwork(self,s):return None
    async def command(self,name,amount=1):self.calls.append((name,amount));return 'Volume 42%' if name=='volume' else 'OK'


class YouTubeTests(unittest.IsolatedAsyncioTestCase):
    def test_home_page_opens_list_even_with_cached_media(self):
        mode=YouTubeMode();mode.launcher.running=lambda:True
        mode.snapshot={'source':'Chrome','key':'stale','playing':False}
        mode.browser.register({'tab':3,'page':'https://www.youtube.com/','active':True})
        mode.enter();self.assertEqual(mode.view,'browser');self.assertTrue(mode.browser.active)
        self.assertEqual(mode.browser.state()['command']['kind'],'focus')

    def test_paused_watch_page_retains_now_playing(self):
        mode=YouTubeMode();mode.launcher.running=lambda:True
        mode.snapshot={'source':'Chrome','key':'video','playing':False}
        mode.browser.register({'tab':3,'page':'https://www.youtube.com/watch?v=abcdefghijk','active':True})
        mode.enter();self.assertEqual(mode.view,'normal');self.assertFalse(mode.browser.active)

    def test_unstarted_browser_opens_list_with_startup_focus_pending(self):
        mode=YouTubeMode({'open_on_enter':True});mode.launcher.running=lambda:False
        mode.launcher.opener=lambda:None;mode.enter()
        self.assertEqual(mode.view,'browser');self.assertTrue(mode.browser.active)
        mode.browser.register({'tab':3,'page':'https://www.youtube.com/'})
        self.assertEqual(mode.browser.state()['command']['kind'],'focus')

    async def test_restored_mode_without_video_shows_list_but_home_stays_home(self):
        service=FakeService();service.s={};mode=YouTubeMode(service=service)
        await mode.poll();self.assertEqual(mode.view,'browser')
        mode.home();await mode.poll();self.assertEqual(mode.view,'normal')

    async def test_automatic_list_selection_returns_to_playback(self):
        mode=YouTubeMode();mode.launcher.running=lambda:True;mode.enter()
        mode.browser.publish({'tab':3,'page':'https://www.youtube.com/','items':[{'url':'https://www.youtube.com/watch?v=abcdefghijk','title':'Example'}]})
        mode.browser.select(0);command=mode.browser.state()['command']
        mode.browser.acknowledge({'id':command['id'],'ok':True})
        mode.service=FakeService();await mode.poll()
        self.assertEqual(mode.view,'normal');self.assertFalse(mode.browser.active)

    def test_twelve_fps_only_for_full_video(self):
        with tempfile.TemporaryDirectory() as directory:
            plugin=Plugin(data_dir=directory,config={'youtube':{'enabled':True}})
            plugin.modes.active='youtube';plugin.youtube.view='artwork'
            self.assertAlmostEqual(plugin.animation_interval(),1/12)
            for view in ('normal','metadata','browser'):
                plugin.youtube.view=view;self.assertEqual(plugin.animation_interval(),.1)

    def test_other_modes_keep_animation_rate(self):
        with tempfile.TemporaryDirectory() as directory:
            plugin=Plugin(data_dir=directory,config={'youtube':{'enabled':True}})
            plugin.youtube.view='artwork'
            for mode in ('spotify','desktop'):
                plugin.modes.active=mode;self.assertEqual(plugin.animation_interval(),.1)

    def test_full_video_interval_tracks_received_selection(self):
        from streamdock_now_playing.video_capture import VideoCapture
        with tempfile.TemporaryDirectory() as directory:
            plugin=Plugin(data_dir=directory,config={'youtube':{'enabled':True}})
            plugin.modes.active='youtube';plugin.youtube.view='artwork'
            plugin.youtube.capture=VideoCapture(lambda:True)
            for fps in (4,6,8,10,12,15,20,24,30,40,45,50,60,75,90,120):
                plugin.youtube.capture.target_fps=fps
                self.assertAlmostEqual(plugin.animation_interval(),1/fps)

    async def test_mode_button_launches_only_youtube_and_only_once(self):
        with tempfile.TemporaryDirectory() as directory:
            plugin=Plugin(data_dir=directory,config={'youtube':{'enabled':True,'open_on_enter':True}})
            calls=[];plugin.youtube.launcher.opener=lambda:calls.append('open')
            plugin.contexts={'mode-key':{'role':'mode','settings':{}}}
            async def render():pass
            plugin.render=render
            event={'event':'keyDown','context':'mode-key','payload':{}}
            await plugin.event(event);self.assertEqual(plugin.modes.active,'desktop');self.assertEqual(calls,[])
            await plugin.event(event);self.assertEqual(plugin.modes.active,'youtube');self.assertEqual(calls,['open'])
            for _ in range(3):await plugin.event(event)
            self.assertEqual(plugin.modes.active,'youtube');self.assertEqual(calls,['open'])

    async def test_controls_are_browser_only(self):
        service=FakeService();mode=YouTubeMode(service=service)
        for role,event,ticks in [('volume','dialRotate',2),('volume','dialDown',0),('tracks','dialRotate',-1),('tracks','dialRotate',1),('seek','dialRotate',2),('seek','dialDown',0),('tracks','dialDown',0)]:
            await mode.input(role,event,ticks)
        self.assertEqual(service.calls,[('volume',8),('play',1),('previous',1),('next',1),('seek',10)])

    async def test_expansion_home_and_status_press(self):
        service=FakeService();mode=YouTubeMode(service=service)
        await mode.poll()
        for tile,view in [(0,'artwork'),(2,'metadata')]:
            await mode.input('tile','keyDown',tile=tile)
            self.assertEqual(mode.view,view);self.assertEqual(len(mode.frame()),6)
            await mode.input('back','keyDown');self.assertEqual(mode.view,'normal')
        await mode.input('tile','keyDown',tile=5)
        self.assertEqual(service.calls,[('play',1)])

    async def test_new_track_and_missing_session(self):
        service=FakeService();mode=YouTubeMode(service=service)
        await mode.poll();service.s.update(key='two',title='New video')
        await mode.poll();self.assertEqual(mode.snapshot['title'],'New video')
        service.s={};await mode.poll();self.assertEqual(len(mode.frame()),6)

    async def test_timeline_interpolation(self):
        now=[0];mode=YouTubeMode(service=FakeService(),clock=lambda:now[0])
        await mode.poll();now[0]=2;await mode.poll()
        self.assertEqual(mode.anchor,0)

    async def test_timeout_and_feedback_expiry(self):
        now=[0];mode=YouTubeMode(service=FakeService(),clock=lambda:now[0])
        await mode.poll();await mode.input('tile','keyDown',tile=0)
        now[0]=31;mode.frame();self.assertEqual(mode.view,'artwork')
        await mode.input('back','keyDown');await mode.input('tile','keyDown',tile=2)
        now[0]+=31;mode.frame();self.assertEqual(mode.view,'normal')
        await mode.input('volume','dialRotate',1)
        self.assertTrue(mode.feedback);now[0]+=3
        self.assertLess(mode.until,now[0]);self.assertEqual(len(mode.frame()),6)

    async def test_full_video_stays_on_capture_loss_or_pause_until_back(self):
        now=[0];mode=YouTubeMode(service=FakeService(),clock=lambda:now[0])
        class LostCapture:
            def latest(self):return None
        mode.capture=LostCapture();await mode.poll()
        await mode.input('tile','keyDown',tile=0)
        mode.service.s['playing']=False;await mode.poll()
        now[0]=3600;self.assertEqual(len(mode.frame()),6);self.assertEqual(mode.view,'artwork')
        await mode.input('back','keyDown');self.assertEqual(mode.view,'normal')

    async def test_last_video_frame_is_held_without_using_old_track_frame(self):
        mode=YouTubeMode(service=FakeService());await mode.poll()
        class Capture:
            frame=['frame']*6
            def latest(self):return self.frame
        capture=Capture();mode.capture=capture
        await mode.input('tile','keyDown',tile=0)
        self.assertEqual(mode.frame(),['frame']*6)
        capture.frame=None;self.assertEqual(mode.frame(),['frame']*6)
        mode.service.s.update(key='new-video',title='New')
        await mode.poll();self.assertIsNone(mode.held_video)
        await mode.input('back','keyDown');self.assertIsNone(mode.held_video)

    async def test_plugin_routes_and_guards_mode_switch(self):
        with tempfile.TemporaryDirectory() as directory:
            plugin=Plugin(data_dir=directory,config={})
            service=FakeService();plugin.youtube=YouTubeMode(service=service)
            plugin.modes.active='youtube';plugin.knob_guard_until=0
            plugin.contexts={'knob':{'role':'tracks','settings':{}}}
            async def render():pass
            plugin.render=render
            await plugin.event({'event':'dialRotate','context':'knob','payload':{'ticks':1}})
            self.assertEqual(service.calls,[('next',1)])
            plugin.knob_guard_until=float('inf')
            await plugin.event({'event':'dialRotate','context':'knob','payload':{'ticks':1}})
            self.assertEqual(len(service.calls),1)

    async def test_spotify_completion_does_not_replace_youtube_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            plugin=Plugin(data_dir=directory,config={});plugin.modes.active='youtube'
            plugin.youtube.frame=lambda:['youtube']*6
            await plugin.volume_feedback('Volume 80%')
            await plugin.render_frame()
            self.assertEqual(plugin.images,['youtube']*6)


class ModeTests(unittest.TestCase):
    def test_launch_once_and_disabled_by_default(self):
        calls=[];launcher=BrowserLauncher(opener=lambda:calls.append('open'))
        self.assertFalse(launcher.enter());self.assertEqual(calls,[])
        launcher.enabled=True
        self.assertTrue(launcher.enter());self.assertFalse(launcher.enter())
        self.assertEqual(calls,['open'])

    def test_launch_failure_can_retry_without_breaking_home(self):
        mode=YouTubeMode({'open_on_enter':True})
        mode.launcher.running=lambda:False
        def fail():raise OSError('No Chrome')
        mode.launcher.opener=fail;mode.view='metadata';mode.enter()
        self.assertEqual(mode.view,'browser');self.assertFalse(mode.launcher.opened)
        self.assertEqual(mode.feedback,'CHROME ERROR')
        self.assertEqual(mode.browser.message,'CHROME ERROR')
        mode.launcher.opener=lambda:None;mode.enter();self.assertTrue(mode.launcher.opened)

    def test_closed_chrome_can_reopen_but_rapid_switches_do_not_duplicate(self):
        now=[0];running=[False];calls=[]
        launcher=BrowserLauncher(enabled=True,opener=lambda:calls.append('open'),running=lambda:running[0],clock=lambda:now[0])
        self.assertTrue(launcher.enter());self.assertFalse(launcher.enter())
        now[0]=6;running[0]=True;self.assertFalse(launcher.enter())
        running[0]=False;self.assertTrue(launcher.enter());self.assertEqual(calls,['open','open'])

    def test_cached_media_and_recent_tab_do_not_block_closed_chrome(self):
        mode=YouTubeMode({'open_on_enter':True});calls=[]
        mode.launcher.running=lambda:False;mode.launcher.opener=lambda:calls.append('open')
        mode.launcher.opened=True
        mode.snapshot={'source':'Chrome','key':'stale'}
        mode.browser.register({'tab':3,'page':'https://www.youtube.com/','active':True})
        mode.enter();self.assertEqual(calls,['open'])
        self.assertIsNone(mode.browser.state()['command'])
        mode.browser.register({'tab':4,'page':'https://www.youtube.com/','active':True})
        command=mode.browser.state()['command']
        self.assertEqual(command['kind'],'focus');self.assertEqual(command['tab'],4)

    def test_running_media_does_not_add_a_new_tab(self):
        mode=YouTubeMode({'open_on_enter':True})
        mode.launcher.running=lambda:True
        mode.launcher.opener=lambda:self.fail('Must retain existing media')
        mode.snapshot={'source':'Chrome','key':'current'}
        mode.enter();self.assertFalse(mode.launcher.opened)

    def test_three_modes_persist_and_old_two_mode_default_remains(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'mode.json';modes=('spotify','desktop','youtube')
            mode=ModeManager(path,modes)
            self.assertEqual(mode.toggle(),'desktop');self.assertEqual(mode.toggle(),'youtube')
            self.assertEqual(ModeManager(path,modes).active,'youtube')
            self.assertEqual(mode.toggle(),'spotify')
        mode=ModeManager();self.assertEqual(mode.toggle(),'desktop');self.assertEqual(mode.toggle(),'spotify')
