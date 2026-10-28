import asyncio
import json
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.request import Request,urlopen
from streamdock_now_playing.youtube_browser import YouTubeBrowser,video_url,channel_url
from streamdock_now_playing.video_capture import VideoCapture
from streamdock_now_playing.youtube import YouTubeMode
from streamdock_now_playing.streamdock import Plugin


def rows(count=8):
    return [{'url':'https://www.youtube.com/watch?v='+str(i).zfill(11),'title':'Video '+str(i),'channel':'Channel','image':''} for i in range(count)]


class BrowserTests(unittest.IsolatedAsyncioTestCase):
    def test_launch_registration_foregrounds_once_without_navigation(self):
        browser=YouTubeBrowser();browser.request_foreground(forget=True)
        browser.register({'tab':3,'page':'https://www.youtube.com/','active':True})
        command=browser.state()['command'];self.assertEqual(command['kind'],'focus')
        browser.register({'tab':3,'page':'https://www.youtube.com/','active':True})
        self.assertEqual(browser.state()['command']['id'],command['id'])
        browser.acknowledge({'id':command['id'],'ok':True})
        browser.register({'tab':3,'page':'https://www.youtube.com/','active':True})
        self.assertIsNone(browser.state()['command'])

    def test_late_foreground_cancelled_by_mode_exit_or_timeout(self):
        now=[0];browser=YouTubeBrowser(clock=lambda:now[0])
        browser.request_foreground();browser.close_view()
        browser.register({'tab':3,'page':'https://www.youtube.com/'})
        self.assertIsNone(browser.state()['command'])
        browser.request_foreground();now[0]=16
        browser.register({'tab':3,'page':'https://www.youtube.com/'})
        self.assertIsNone(browser.state()['command'])

    def test_normal_list_loads_more_and_preserves_selection(self):
        browser=YouTubeBrowser();browser.open();page='https://www.youtube.com/'
        browser.publish({'tab':3,'page':page,'items':rows(41)})
        browser.move(38);command=browser.state()['command']
        self.assertEqual(command['kind'],'list-more')
        browser.publish({'tab':3,'page':page,'items':rows(70)[30:],'request_id':command['id'],'has_more':True})
        self.assertEqual(len(browser.items),70);self.assertEqual(browser.offset,38)
        browser.select(0);self.assertEqual(browser.state()['command']['url'],rows(70)[38]['url'])

    def test_normal_list_stops_after_three_no_growth_requests(self):
        browser=YouTubeBrowser();browser.open();page='https://www.youtube.com/'
        browser.publish({'tab':3,'page':page,'items':rows(20)})
        for _ in range(3):
            browser.move(100);command=browser.state()['command']
            browser.publish({'tab':3,'page':page,'items':rows(20),'request_id':command['id'],'has_more':True})
        browser.publish({'tab':3,'page':page,'items':rows(20)})
        browser.move(1);self.assertFalse(browser.has_more);self.assertIsNone(browser.state()['command'])

    def paged_browser(self):
        browser,target=self.channel_browser(0)
        command=browser.state()['command']
        browser.publish({'tab':3,'page':target,'items':rows(20),'request_id':command['id'],'has_more':True})
        return browser,target

    def test_continuation_appends_without_reorder_or_position_change(self):
        browser,target=self.paged_browser();browser.move(15)
        command=browser.state()['command'];self.assertEqual(command['kind'],'channel-more')
        browser.move(-1);self.assertEqual(browser.offset,14)
        self.assertEqual(browser.state()['command']['id'],command['id'])
        browser.publish({'tab':3,'page':target,'items':rows(40)[19:],'request_id':command['id'],'has_more':True})
        self.assertEqual(len(browser.items),40);self.assertEqual(browser.offset,14)
        self.assertEqual([i['uri'] for i in browser.items],[i['url'] for i in rows(40)])
        browser.move(20);self.assertEqual(browser.state()['command']['kind'],'channel-more')

    def test_continuation_failure_can_retry_without_losing_catalog(self):
        browser,target=self.paged_browser();browser.move(17);command=browser.state()['command']
        browser.acknowledge({'id':command['id'],'ok':False})
        self.assertEqual(len(browser.items),20);self.assertEqual(browser.message,'CHANNEL FAILED')
        browser.move(1);self.assertEqual(browser.state()['command']['kind'],'channel-more')

    def test_continuation_exhausted_or_empty_stops_requests(self):
        browser,target=self.paged_browser();browser.move(17);command=browser.state()['command']
        browser.publish({'tab':3,'page':target,'items':[],'request_id':command['id'],'has_more':False})
        browser.move(1);self.assertIsNone(browser.state()['command']);self.assertEqual(len(browser.items),20)

    def test_late_continuation_cannot_replace_play_or_new_view(self):
        browser,target=self.paged_browser();browser.move(17);command=browser.state()['command']
        browser.select(0);self.assertEqual(browser.state()['command']['kind'],'play')
        self.assertFalse(browser.publish({'tab':3,'page':target,'items':rows(40),'request_id':command['id'],'has_more':True}))
        self.assertEqual(len(browser.items),20)
        browser.open()
        self.assertFalse(browser.publish({'tab':3,'page':target,'items':rows(40),'request_id':command['id'],'has_more':True}))
        self.assertEqual(len(browser.items),0)

    def test_continuation_catalog_is_bounded(self):
        browser,target=self.paged_browser();browser.catalog_limit=25;browser.move(17);command=browser.state()['command']
        browser.publish({'tab':3,'page':target,'items':rows(40)[20:],'request_id':command['id'],'has_more':True})
        self.assertEqual(len(browser.items),25);self.assertFalse(browser.has_more)

    def channel_browser(self,current_index):
        browser=YouTubeBrowser();target='https://www.youtube.com/@Example/videos'
        browser.register_channel({'tab':3,'page':rows(20)[current_index]['url'],'channel_url':target,'title':'Current'})
        self.assertTrue(browser.open_current_channel('Current'))
        return browser,target

    def test_channel_initial_position_tracks_current_video_without_reordering(self):
        browser,target=self.channel_browser(5)
        browser.publish({'tab':3,'page':target,'items':rows(12)})
        self.assertEqual(browser.offset,5);self.assertEqual(browser.diagnostics()['current_position'],6)
        self.assertEqual([i['uri'] for i in browser.items],[i['url'] for i in rows(12)])
        browser.select(0);self.assertEqual(browser.state()['command']['url'],rows(12)[5]['url'])

    def test_initial_position_keeps_last_video_visible(self):
        browser,target=self.channel_browser(11);browser.publish({'tab':3,'page':target,'items':rows(12)})
        self.assertEqual(browser.offset,9);self.assertEqual(browser.diagnostics()['current_position'],12)

    def test_do_not_snap_back_after_manual_browsing(self):
        browser,target=self.channel_browser(5);browser.publish({'tab':3,'page':target,'items':rows(12)})
        browser.move(-2);self.assertEqual(browser.offset,3)
        browser.publish({'tab':3,'page':target,'items':rows(13)});self.assertEqual(browser.offset,3)

    def test_missing_current_video_and_late_loading(self):
        browser,target=self.channel_browser(9);browser.publish({'tab':3,'page':target,'items':rows(5)})
        self.assertEqual(browser.offset,0);self.assertEqual(browser.diagnostics()['initial_focus'],'not_in_loaded_list')
        browser.publish({'tab':3,'page':target,'items':rows(12)});self.assertEqual(browser.offset,9)
        browser2,target=self.channel_browser(9);browser2.publish({'tab':3,'page':target,'items':rows(5)});browser2.move(1)
        browser2.publish({'tab':3,'page':target,'items':rows(12)});self.assertEqual(browser2.offset,1)
    async def test_channel_entry_is_metadata_bottom_not_list_bottom(self):
        mode=YouTubeMode();mode.snapshot={'title':'Current video'}
        page=rows()[0]['url'];target='https://www.youtube.com/@Example/videos'
        mode.browser.register({'tab':3,'page':page,'active':True})
        mode.browser.register_channel({'tab':3,'page':page,'channel_url':target,'title':'Current video'})
        mode.view='metadata'
        await mode.input('tile','keyDown',tile=4)
        command=mode.browser.state()['command'];self.assertEqual(command['kind'],'channel');self.assertEqual(command['url'],target)
        mode.browser.acknowledge({'id':command['id'],'ok':True});self.assertFalse(mode.browser.take_success())
        self.assertFalse(mode.browser.publish({'tab':3,'page':page,'items':rows()}))
        self.assertTrue(mode.browser.publish({'tab':3,'page':target,'items':rows()}))
        self.assertEqual(mode.view,'browser');self.assertIsNone(mode.browser.state()['command'])
        await mode.input('tile','keyDown',tile=3)
        self.assertEqual(mode.browser.state()['command']['kind'],'play')
        await mode.input('back','keyDown');self.assertEqual(mode.view,'metadata')
        self.assertIsNone(mode.browser.state()['command'])

    def test_reuse_existing_tab_does_not_request_new_url(self):
        mode=YouTubeMode({'open_on_enter':True});calls=[];mode.launcher.opener=lambda:calls.append('launch')
        mode.launcher.running=lambda:True
        mode.browser.register({'tab':3,'page':'https://www.youtube.com/','active':True})
        mode.enter();self.assertEqual(calls,[])
        command=mode.browser.state()['command'];self.assertEqual(command['kind'],'focus');self.assertEqual(command['tab'],3)
        mode.browser.acknowledge({'id':command['id'],'ok':True});self.assertFalse(mode.browser.take_success())
        mode.home();self.assertIsNone(mode.browser.state()['command'])

    def test_channel_url_missing_and_wrong_track(self):
        self.assertEqual(channel_url('https://www.youtube.com/@Example'),'https://www.youtube.com/@Example/videos')
        for url in ['https://evil.example/@Example','https://www.youtube.com/watch?v=abcdefghijk','https://www.youtube.com/@Example%2fother']:
            with self.assertRaises(ValueError):channel_url(url)
        browser=YouTubeBrowser();self.assertFalse(browser.open_current_channel('Unknown'))
        browser.register_channel({'tab':3,'page':rows()[0]['url'],'channel_url':'https://www.youtube.com/@Example','title':'A different video'})
        self.assertFalse(browser.open_current_channel('Current video'));self.assertIsNone(browser.state()['command'])

    def test_url_and_catalog_boundaries(self):
        self.assertEqual(video_url('https://www.youtube.com/watch?v=abcdefghijk&list=abc'),'https://www.youtube.com/watch?v=abcdefghijk')
        for value in ('http://www.youtube.com/watch?v=abcdefghijk','https://evil.example/watch?v=abcdefghijk','https://www.youtube.com/watch?v=bad','javascript:alert(1)'):
            with self.assertRaises(ValueError):video_url(value)
        browser=YouTubeBrowser();browser.open()
        with self.assertRaises(ValueError):browser.publish({'tab':3,'items':rows(101)})
        browser.publish({'tab':3,'items':[{'url':rows()[0]['url'],'image':'https://evil.example/image'}]})
        self.assertEqual(browser.items[0]['image'],'')

    def test_sliding_selection_same_column_and_stable_order(self):
        browser=YouTubeBrowser();browser.open();browser.publish({'tab':3,'items':rows()})
        browser.move(2);self.assertEqual(browser.offset,2)
        browser.select(4);command=browser.state()['command'];self.assertEqual(command['url'],rows()[3]['url'])
        self.assertFalse(browser.acknowledge({'id':'wrong','ok':True}))
        browser.acknowledge({'id':command['id'],'ok':True});self.assertTrue(browser.take_success())
        browser.publish({'tab':3,'items':list(reversed(rows(9)))})
        self.assertEqual(browser.items[3]['uri'],rows()[3]['url'])
        self.assertEqual(len(browser.items),9)
        browser.move(100);self.assertEqual(browser.offset,6)
        browser.move(-100);self.assertEqual(browser.offset,0)

    def test_wrong_source_and_navigation_cancel(self):
        browser=YouTubeBrowser();browser.open();browser.publish({'tab':3,'items':rows()})
        self.assertFalse(browser.publish({'tab':4,'items':rows(9)}))
        browser.select(0);command=browser.state()['command'];browser.close_view()
        self.assertIsNone(browser.state()['command'])
        self.assertFalse(browser.acknowledge({'id':command['id'],'ok':True}))
        self.assertFalse(browser.take_success())

    def test_title_can_be_filled_in_without_moving_selection(self):
        browser=YouTubeBrowser();browser.open()
        first=rows();first[0]['title']='   '
        browser.publish({'tab':3,'items':first});self.assertEqual(browser.diagnostics()['missing_titles'],1)
        browser.move(1);before=[i['uri'] for i in browser.items]
        browser.publish({'tab':3,'items':list(reversed(rows()))})
        self.assertEqual(browser.items[0]['title'],'Video 0')
        self.assertEqual([i['uri'] for i in browser.items],before);self.assertEqual(browser.offset,1)
        self.assertEqual(browser.diagnostics()['missing_titles'],0)

    def test_timeout_and_playback_failure(self):
        now=[0];browser=YouTubeBrowser(clock=lambda:now[0]);browser.open();browser.publish({'tab':3,'items':rows()})
        browser.select(0);now[0]=16;self.assertIsNone(browser.state()['command']);self.assertEqual(browser.message,'PLAY TIMEOUT')
        browser.select(0);command=browser.state()['command']
        browser.acknowledge({'id':command['id'],'ok':False});self.assertEqual(browser.message,'PLAY FAILED')
        self.assertFalse(browser.take_success())

    async def test_browser_input_and_back(self):
        mode=YouTubeMode();mode.open_browser();mode.browser.publish({'tab':3,'items':rows()})
        await mode.input('seek','dialRotate',2);self.assertEqual(mode.browser.offset,2)
        self.assertEqual(len(mode.frame()),6)
        await mode.input('tile','keyDown',tile=4);self.assertIsNotNone(mode.browser.state()['command'])
        await mode.input('back','keyDown');self.assertEqual(mode.view,'normal');self.assertIsNone(mode.browser.state()['command'])

    async def test_center_short_opens_list_in_youtube_only(self):
        with tempfile.TemporaryDirectory() as directory:
            plugin=Plugin(data_dir=directory,config={'youtube':{'enabled':True}});plugin.modes.active='youtube'
            plugin.contexts={'home':{'role':'player','settings':{}}}
            async def render():pass
            plugin.render=render
            await plugin.event({'event':'keyDown','context':'home'})
            await plugin.event({'event':'keyUp','context':'home'})
            self.assertEqual(plugin.youtube.view,'browser');self.assertTrue(plugin.youtube.browser.active)
            await plugin.go_home();self.assertFalse(plugin.youtube.browser.active)

    def test_authenticated_bridge_without_video_capture(self):
        browser=YouTubeBrowser();browser.open();receiver=VideoCapture(lambda:False,port=0,browser=browser)
        base=receiver.start().split('#')[0];headers={'X-Capture-Token':receiver.token}
        try:
            with urlopen(Request(base+'state',headers=headers)) as r:
                state=json.load(r);self.assertTrue(state['browse']);self.assertFalse(state['enabled'])
            with urlopen(Request(base+'browser/catalog',data=json.dumps({'tab':3,'items':rows()}).encode(),headers=headers)) as r:self.assertEqual(r.status,204)
            browser.select(0);command=browser.state()['command']
            with urlopen(Request(base+'browser/ack',data=json.dumps({'id':command['id'],'ok':True}).encode(),headers=headers)) as r:self.assertEqual(r.status,204)
            self.assertTrue(browser.take_success())
            with self.assertRaises(HTTPError):urlopen(Request(base+'browser/catalog',data=b'{}'))
        finally:receiver.close()
