import asyncio
import hashlib
import base64
import tempfile
import time
import unittest
from urllib.parse import parse_qs
from unittest.mock import patch
from streamdock_now_playing.spotify import SpotifyClient, SpotifyError, QueueState, CredentialStore, pkce_pair, parse_callback
from streamdock_now_playing.streamdock import Plugin
from streamdock_now_playing.queue_renderer import QueueRenderer
from test_behavior import FakeMedia, FakeWS


class Store:
    def __init__(self):
        self.value = {'client_id':'test', 'access_token':'access', 'refresh_token':'refresh', 'expires_at':time.time()+3600}
    def load(self): return dict(self.value)
    def save(self,value): self.value=dict(value)


class SpotifyTests(unittest.TestCase):
    def test_callback_rejects_wrong_state_path_and_duplicates(self):
        for path in ('/callback?code=c&state=wrong', '/other?code=c&state=expected',
                     '/callback?code=c', '/callback?state=expected&code=a&code=b',
                     '/callback?state=expected&state=wrong&code=c'):
            self.assertIsNone(parse_callback(path, 'expected'))
        self.assertEqual(parse_callback('/callback?state=expected&code=c','expected'), {'code':'c'})
        self.assertEqual(parse_callback('/callback?state=expected&error=access_denied','expected'), {'error':True})

    def test_pkce_s256(self):
        verifier, challenge=pkce_pair()
        self.assertTrue(43<=len(verifier)<=128)
        self.assertEqual(challenge,base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode())
        self.assertNotEqual(pkce_pair()[0],verifier)

    def test_dpapi_roundtrip_no_plaintext(self):
        with tempfile.TemporaryDirectory() as directory:
            store=CredentialStore(directory);store.save({'refresh_token':'private-test-value'})
            self.assertNotIn(b'private-test-value',store.path.read_bytes())
            self.assertEqual(store.load(),{'refresh_token':'private-test-value'})

    def test_keep_full_queue_and_preserve_repeated_tracks(self):
        def transport(*args):
            return {'queue':[{'name':'Song','artists':[{'name':'Artist'}]}]*5}
        client=SpotifyClient({'enabled':True,'client_id':'test'},'.',Store(),transport)
        result=client.queue()
        self.assertEqual(len(result),5);self.assertEqual(result[0],result[1])
        self.assertEqual(result[0]['artist'],'Artist')

    def test_disabled_and_missing_auth_do_not_call_network(self):
        for settings,store in (({},Store()),({'enabled':True,'client_id':'test'},Store())):
            if settings: store.value={}
            with self.subTest(settings=settings), patch('streamdock_now_playing.spotify.http_json') as network:
                with self.assertRaises(SpotifyError):SpotifyClient(settings,'.',store).queue()
                network.assert_not_called()

    def test_refresh_without_client_secret_and_keep_refresh_token(self):
        store=Store();store.value['expires_at']=0;calls=[]
        def transport(method,url,data,headers):
            calls.append((method,url,data,headers))
            return {'access_token':'new','expires_in':3600} if method=='POST' else {'queue':[]}
        client=SpotifyClient({'enabled':True,'client_id':'test'},'.',store,transport)
        self.assertEqual(client.queue(),[])
        body=parse_qs(calls[0][2].decode())
        self.assertNotIn('client_secret',body);self.assertEqual(body['grant_type'],['refresh_token'])
        self.assertEqual(store.value['refresh_token'],'refresh')
        self.assertEqual(calls[1][3]['Authorization'],'Bearer new')

    def test_401_refreshes_once(self):
        calls=[]
        def transport(method,url,data,headers):
            calls.append(method)
            if len(calls)==1:raise SpotifyError('Unauthorized',status=401)
            return {'access_token':'new'} if method=='POST' else {'queue':[]}
        client=SpotifyClient({'enabled':True,'client_id':'test'},'.',Store(),transport)
        self.assertEqual(client.queue(),[]);self.assertEqual(calls,['GET','POST','GET'])

    def test_403_429_backoff(self):
        for code in (403,429):
            calls=[]
            def transport(*args):calls.append(1);raise SpotifyError(str(code),60,status=code)
            client=SpotifyClient({'enabled':True,'client_id':'test'},'.',Store(),transport)
            for attempt in range(2):
                with self.assertRaises(SpotifyError):client.queue()
            self.assertEqual(len(calls),1)

    def test_queue_renderer_six_tiles_cache(self):
        renderer=QueueRenderer();items=[{'title':'Track','artist':'Artist'}]
        images=renderer.render(items,'');self.assertEqual(len(images),6)
        self.assertIs(images,renderer.render(items,''))
        self.assertNotEqual(images,renderer.render([],'Sign-in required'))


class QueueIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.plugin=Plugin(provider=FakeMedia(),data_dir=self.temp.name,config={});self.plugin.ws=FakeWS()
        for role in ('mode','player','back','volume'):
            self.plugin.contexts[role]={'role':role,'settings':{}}
        for tile in range(6):self.plugin.contexts[str(tile)]={'role':'tile','settings':{'tile':tile}}
    def setup_selection(self):
        p=self.plugin
        tracks=[{'title':str(i),'uri':'track:'+str(i+1)} for i in range(3)]
        p.queue_state.items=list(tracks)
        p.queue_state.client.queue=lambda:list(tracks)
        p.queue_state.client.playback=lambda:{'item':{'uri':'track:'+str(len([c for c in p.provider.calls if c[0]=='next']))}}
    async def asyncTearDown(self):
        task=self.plugin.queue_state.task
        if task:await task
    async def press(self,role):
        p=self.plugin
        await p.event({'event':'keyDown','context':role})
        if role=='player':
            await p.event({'event':'keyUp','context':role})


    async def test_navigation_readonly_and_home(self):
        p=self.plugin;await self.press('player');self.assertEqual(p.view_mode,'queue')
        for tile in range(6):await self.press(str(tile))
        self.assertEqual(p.view_mode,'queue');self.assertEqual(p.provider.calls,[])
        await self.press('back');self.assertEqual(p.view_mode,'normal')
        await self.press('player');await self.press('mode')
        self.assertEqual(p.view_mode,'normal');self.assertEqual(p.navigation,[])

    async def test_api_failure_leaves_controls_available(self):
        p=self.plugin
        def fail():raise SpotifyError('Access denied (403)')
        p.queue_state.client.queue=fail
        await self.press('player');await p.queue_state.task
        self.assertIn('403',p.queue_state.message)
        await p.event({'event':'dialDown','context':'volume'})
        self.assertEqual(p.provider.calls,[('play',1)])
        self.assertEqual(p.view_mode,'queue');await self.press('mode')
        self.assertEqual(p.view_mode,'normal')

    async def test_slow_network_does_not_block_home_or_knob(self):
        p=self.plugin
        def slow():time.sleep(.2);return []
        p.queue_state.client.queue=slow
        await self.press('player')
        await asyncio.wait_for(self.press('mode'),.1)
        self.assertEqual(p.modes.active,'desktop')
        await asyncio.wait_for(self.press('mode'),.1)
        p.knob_guard_until=0
        await asyncio.wait_for(p.event({'event':'dialDown','context':'volume'}),.1)
        self.assertEqual(p.provider.calls,[('play',1)])
        self.assertEqual(p.view_mode,'normal')

    async def test_duplicate_refresh_requests_coalesce(self):
        calls=[]
        def slow():calls.append(1);time.sleep(.05);return []
        state=QueueState(type('Client',(),{'queue':staticmethod(slow)})())
        state.request();state.request();await state.task
        state.request();self.assertEqual(calls,[1])
    async def test_queue_columns_send_one_two_three_next_commands(self):
        p=self.plugin;p.view_mode='queue'
        self.setup_selection()
        for column in range(3):
            p.view_mode='queue'
            p.queue_state.items=[{'title':str(i),'uri':'track:'+str(i+1)} for i in range(3)]
            p.provider.calls.clear()
            await self.press(str(column))
            await p.queue_skip_task
            if p.queue_state.task:await p.queue_state.task
            self.assertEqual(p.provider.calls,[('next',1)]*(column+1))
            self.assertEqual(p.view_mode,'normal')
            self.assertEqual(p.navigation,[])

    async def test_bottom_row_selects_same_column_and_release_does_nothing(self):
        from unittest.mock import AsyncMock
        p=self.plugin;p.view_mode='queue'
        p.queue_state.items=[{'title':str(i),'uri':'track:'+str(i+1)} for i in range(3)]
        p.skip_queue=AsyncMock()
        for column in range(3):
            await self.press(str(column+3));await p.queue_skip_task
            p.skip_queue.assert_awaited_with(column+1,'track:'+str(column+1))
        await p.event({'event':'keyUp','context':'5'})
        self.assertEqual(p.skip_queue.await_count,3)

    async def test_rejection_stops_skipping_and_duplicate_presses_ignored(self):
        p=self.plugin;p.view_mode='queue';p.queue_state.items=[{'title':str(i),'uri':'track:'+str(i+1)} for i in range(3)]
        self.setup_selection()
        calls=[]
        async def rejected(name,amount):calls.append(name);await asyncio.sleep(.02);return 'Unsupported'
        p.provider.command=rejected
        await self.press('2');await self.press('2');await p.queue_skip_task
        self.assertEqual(calls,['next']);self.assertEqual(p.queue_state.message,'Unsupported')

    async def test_back_cancels_remaining_skips(self):
        p=self.plugin;p.view_mode='queue';p.queue_state.items=[{'title':str(i),'uri':'track:'+str(i+1)} for i in range(3)]
        self.setup_selection()
        await self.press('2')
        async def first_step():
            while not p.provider.calls:await asyncio.sleep(.001)
        await asyncio.wait_for(first_step(),1)
        await self.press('back');await asyncio.gather(p.queue_skip_task,return_exceptions=True)
        self.assertEqual(p.view_mode,'normal');self.assertEqual(p.provider.calls,[('next',1)])
    async def test_new_title_is_not_published_before_matching_artwork(self):
        p=self.plugin;p.snapshot={'key':'old','title':'Old'}
        started=asyncio.Event();release=asyncio.Event()
        async def snapshot():return {'key':'new','title':'New'}
        async def artwork(value):started.set();await release.wait();return None
        p.provider.snapshot=snapshot;p.provider.artwork=artwork
        task=asyncio.create_task(p.polling())
        try:
            await asyncio.wait_for(started.wait(),1)
            self.assertEqual(p.snapshot['title'],'Old')
            release.set()
            for attempt in range(20):
                if p.snapshot.get('title')=='New':break
                await asyncio.sleep(.01)
            self.assertEqual(p.snapshot['title'],'New')
            self.assertEqual(p.key,'new')
        finally:
            task.cancel();await asyncio.gather(task,return_exceptions=True)
    async def test_back_in_normal_is_navigation_only(self):
        p=self.plugin;p.view_mode='normal';p.return_steps=2
        await self.press('back')
        self.assertEqual(p.provider.calls,[])
        self.assertEqual(p.view_mode,'normal')

    async def test_back_from_queue_only_navigates_and_does_not_undo(self):
        p=self.plugin;p.view_mode='queue';p.return_steps=2;p.navigation=['normal']
        await self.press('back')
        self.assertEqual(p.view_mode,'normal');self.assertEqual(p.return_steps,2)
        self.assertEqual(p.provider.calls,[])

    async def test_return_stops_if_seek_is_unsupported(self):
        p=self.plugin;p.return_steps=2
        async def unsupported(name,amount):p.provider.calls.append((name,amount));return 'Seek unsupported'
        p.provider.command=unsupported
        await p.return_from_queue()
        self.assertEqual(p.provider.calls,[('seek',-1_000_000_000)])
        self.assertEqual(p.return_steps,2);self.assertEqual(p.overlay,'RETURN UNSUPPORTED')

    async def test_repeated_back_does_not_duplicate_track_return(self):
        p=self.plugin;p.return_steps=1
        await self.press('back');await self.press('back')
        self.assertEqual(p.provider.calls,[])
        self.assertIsNone(p.queue_skip_task)

    async def test_manual_track_navigation_discards_old_return_history(self):
        p=self.plugin;p.return_steps=2
        p.contexts['tracks']={'role':'tracks','settings':{}}
        await p.event({'event':'dialRotate','context':'tracks','payload':{'ticks':1}})
        self.assertEqual(p.return_steps,0)
