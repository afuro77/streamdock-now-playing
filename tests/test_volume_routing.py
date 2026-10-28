import asyncio
import copy
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit

from streamdock_now_playing.spotify import SpotifyClient, SpotifyError, http_json, SCOPES
from streamdock_now_playing.volume_router import AutoVolume
from streamdock_now_playing.streamdock import Plugin
from test_behavior import FakeMedia, FakeWS
from test_spotify_queue import Store


def remote(volume=25, **changes):
    return dict(id='speaker-id', name='Living room', type='CastAudio', is_active=True,
                supports_volume=True, is_restricted=False, volume_percent=volume, **changes)


def computer():
    return dict(id='pc-id', name='WORKPC', type='Computer', is_active=True,
                supports_volume=True, is_restricted=False, volume_percent=100)


class Client:
    settings={'enabled':True}
    def __init__(self, device):self.device=device;self.writes=[];self.fail=None;self.apply=True
    def playback(self):return {'device':copy.deepcopy(self.device)} if self.device else {}
    def devices(self):return [computer(),copy.deepcopy(self.device)] if self.device else []
    def set_volume(self,device_id,value):
        if self.fail:raise self.fail
        self.writes.append((device_id,value))
        if self.apply:self.device['volume_percent']=value


class VolumeRoutingTests(unittest.IsolatedAsyncioTestCase):
    def setup_router(self,device):
        self.client=Client(device);self.local=AsyncMock(return_value='Volume 42%')
        self.feedback=AsyncMock();self.router=AutoVolume(self.client,self.local,self.feedback,hostname='WORKPC')
        return self.router

    async def test_pc_retains_audio_session_even_without_web_volume_support(self):
        d=computer();d['supports_volume']=False;d['is_restricted']=True
        r=self.setup_router(d)
        self.assertEqual(await r.adjust(2),'Volume 42%')
        self.local.assert_awaited_once_with(2);self.assertEqual(self.client.writes,[])

    async def test_external_plus_minus_two_and_feedback_matches_readback(self):
        r=self.setup_router(remote())
        self.assertEqual(await r.adjust(2),'Volume 27%')
        self.assertEqual(await r.adjust(-2),'Volume 25%')
        self.assertEqual(self.client.writes,[('speaker-id',27),('speaker-id',25)])
        self.local.assert_not_awaited()

    async def test_transfers_are_detected_each_adjustment(self):
        r=self.setup_router(computer())
        await r.adjust(2)
        self.client.device=remote(40)
        self.assertEqual(await r.adjust(2),'Volume 42%')
        self.client.device=computer()
        await r.adjust(-2)
        self.assertEqual(self.local.await_args_list[0].args,(2,))
        self.assertEqual(self.local.await_args_list[1].args,(-2,))
        self.assertEqual(self.client.writes,[('speaker-id',42)])

    async def test_unsupported_restricted_unknown_or_null_volume_never_change_pc(self):
        variants=[]
        for field,value in (('supports_volume',False),('is_restricted',True),('volume_percent',None),('id',None)):
            d=remote();d[field]=value;variants.append(d)
        d=computer();d['name']='Other computer';d['id']='other-pc-id';variants.append(d)
        variants.append(None)
        for device in variants:
            r=self.setup_router(device);await r.adjust(2)
            self.local.assert_not_awaited();self.assertEqual(self.client.writes,[])

    async def test_api_failure_after_external_detection_never_falls_back_to_pc(self):
        for code in (401,403,404,429):
            r=self.setup_router(remote());self.client.fail=SpotifyError(str(code),status=code)
            self.assertNotIn('%',await r.adjust(2))
            self.local.assert_not_awaited()

    async def test_network_failure_cannot_reuse_stale_local_routing(self):
        r=self.setup_router(computer());await r.adjust(2);self.local.reset_mock()
        self.client.playback=lambda: (_ for _ in ()).throw(SpotifyError('Offline'))
        self.assertEqual(await r.adjust(2),'Volume unavailable');self.local.assert_not_awaited()

    async def test_zero_and_hundred_are_clamped(self):
        r=self.setup_router(remote(99));self.assertEqual(await r.adjust(2),'Volume 100%')
        self.client.device=remote(1);self.assertEqual(await r.adjust(-2),'Volume 0%')

    async def test_pending_volume_is_not_reported_as_confirmed(self):
        r=self.setup_router(remote());self.client.apply=False
        self.assertEqual(await r.adjust(2),'Volume pending')
        self.local.assert_not_awaited()

    async def test_new_active_device_during_confirmation_is_not_misreported(self):
        r=self.setup_router(remote())
        def changed(device_id,value):self.client.device=computer()
        self.client.set_volume=changed
        self.assertEqual(await r.adjust(2),'Volume target changed');self.local.assert_not_awaited()

    async def test_encoder_ticks_are_coalesced_without_losing_steps(self):
        r=self.setup_router(remote())
        for amount in (2,2,2,-2):r.submit(amount)
        await r.task
        self.assertEqual(self.client.writes,[('speaker-id',29)])
        self.feedback.assert_awaited_once_with('Volume 29%')

    async def test_non_spotify_and_disabled_api_keep_existing_route(self):
        r=self.setup_router(remote())
        self.assertFalse(r.handles('example.exe'))
        self.assertTrue(r.handles('SpotifyAB.SpotifyMusic!Spotify'))
        self.client.settings={'enabled':False}
        self.assertFalse(r.handles('Spotify.exe'))


class VolumeApiTests(unittest.TestCase):
    def test_put_requires_new_scope_and_targets_explicit_device(self):
        store=Store();calls=[]
        client=SpotifyClient({'enabled':True,'client_id':'test'},'.',store,
                             lambda *args:calls.append(args) or {})
        with self.assertRaises(SpotifyError):client.set_volume('speaker-id',27)
        self.assertEqual(calls,[])
        self.assertEqual(client.queue(),[])  # Missing write scope does not break Queue.
        store.value['scope']='user-modify-playback-state'
        client.set_volume('speaker-id',27)
        method,url,body,headers=calls[-1]
        self.assertEqual(method,'PUT');self.assertIsNone(body)
        self.assertEqual(parse_qs(urlsplit(url).query),{'device_id':['speaker-id'],'volume_percent':['27']})
        self.assertIn('user-modify-playback-state',SCOPES.split())

    def test_empty_204_is_success_not_json_failure(self):
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):return b''
        with patch('streamdock_now_playing.spotify.urlopen',return_value=Response()):
            self.assertEqual(http_json('PUT','https://api.spotify.com/v1/me/player/volume'),{})

    def test_refresh_preserves_granted_scopes(self):
        store=Store();store.value['scope']='user-modify-playback-state'
        client=SpotifyClient({'client_id':'test'},'.',store)
        client.save_response({'access_token':'new'},store.load())
        self.assertEqual(store.value['scope'],'user-modify-playback-state')


class VolumeHostTests(unittest.IsolatedAsyncioTestCase):
    async def test_slow_web_volume_does_not_block_home_and_feedback_uses_remote(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Plugin(provider=FakeMedia(),data_dir=directory,config={'spotify':{'enabled':True}})
            p.ws=FakeWS();p.snapshot={'source':'Spotify.exe'}
            p.contexts={'volume':{'role':'volume','settings':{}},'mode':{'role':'mode','settings':{}}}
            client=Client(remote());p.volume_router.client=client
            original=client.playback
            def slow():time.sleep(.1);return original()
            client.playback=slow
            await asyncio.wait_for(p.event({'event':'dialRotate','context':'volume','payload':{'ticks':1}}),.1)
            await asyncio.wait_for(p.event({'event':'keyDown','context':'mode'}),.1)
            await asyncio.wait_for(p.event({'event':'keyDown','context':'mode'}),.1)
            await p.volume_router.task
            self.assertEqual(p.overlay,'VOL 29%')
            self.assertEqual(p.provider.calls,[])
            self.assertEqual(p.view_mode,'normal')
