import asyncio,unittest,tempfile,time
from unittest.mock import Mock,AsyncMock
from streamdock_now_playing.devices import DeviceBrowser
from streamdock_now_playing.spotify import SpotifyClient,SpotifyError
from streamdock_now_playing.streamdock import Plugin
from test_behavior import FakeMedia,FakeWS
class DeviceTests(unittest.IsolatedAsyncioTestCase):
 async def test_refresh_and_active_first(self):
  c=Mock();c.devices.return_value=[{'id':'b'},{'id':'a','is_active':True}];b=DeviceBrowser(c);await b.refresh();self.assertEqual(b.selected(0),'a');self.assertEqual(len(b.render()),6)
 async def test_restricted_and_missing_id_not_selectable(self):
  c=Mock();c.devices.return_value=[{'id':'a','is_restricted':True},{}];b=DeviceBrowser(c);await b.refresh();self.assertIsNone(b.selected(0));self.assertIsNone(b.selected(1))
 async def test_pagination_clamped(self):
  c=Mock();c.devices.return_value=[{'id':str(i)} for i in range(8)];b=DeviceBrowser(c);await b.refresh();b.move(10);self.assertEqual(b.page,1);self.assertEqual(b.selected(1),'7');self.assertIsNone(b.selected(2));b.move(-10);self.assertEqual(b.page,0)
 async def test_transfer_refetch_and_confirmation(self):
  c=Mock();c.devices.return_value=[{'id':'a'}];c.playback.return_value={'device':{'id':'a'}};b=DeviceBrowser(c);self.assertTrue(await b.transfer('a'));c.transfer_playback.assert_called_once_with('a')
 async def test_missing_device_never_transferred(self):
  c=Mock();c.devices.return_value=[];b=DeviceBrowser(c);self.assertFalse(await b.transfer('a'));c.transfer_playback.assert_not_called()
 async def test_restricted_device_never_transferred(self):
  c=Mock();c.devices.return_value=[{'id':'a','is_restricted':True}];b=DeviceBrowser(c);self.assertFalse(await b.transfer('a'));c.transfer_playback.assert_not_called()
 async def test_transfer_failure_keeps_message(self):
  c=Mock();c.devices.return_value=[{'id':'a'}];c.transfer_playback.side_effect=SpotifyError('403',status=403);b=DeviceBrowser(c);self.assertFalse(await b.transfer('a'));self.assertEqual(b.message,'API 403');self.assertFalse(b.switching)
 async def test_refresh_error_discards_stale(self):
  c=Mock();c.devices.side_effect=OSError();b=DeviceBrowser(c);b.items=[{'id':'old'}];await b.refresh();self.assertEqual(b.items,[])
 def test_transfer_body_keeps_playback_state(self):
  c=SpotifyClient({},'.');c.request=Mock();c.transfer_playback('a');self.assertEqual(c.request.call_args.kwargs['body'],{'device_ids':['a']})
class DeviceInputTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.p=Plugin(provider=FakeMedia(),data_dir=self.tmp.name,config={});self.p.ws=FakeWS();self.p.contexts={'status':{'role':'tile','settings':{'tile':5}},'mode':{'role':'mode','settings':{}},'back':{'role':'back','settings':{}},'volume':{'role':'volume','settings':{}}};self.p.devices.client=Mock();self.p.devices.client.devices.return_value=[]
 async def event(self,event='keyDown',ctx='status'):await self.p.event({'event':event,'context':ctx,'payload':{}})
 async def asyncTearDown(self):
  if self.p.status_hold_task:
   self.p.status_hold_task.cancel();await asyncio.gather(self.p.status_hold_task,return_exceptions=True)
  await self.p.devices.close();await self.p.desktop.close()
 async def test_short_press_toggles_on_release_only(self):
  await self.event();self.assertEqual(self.p.provider.calls,[]);await self.event('keyUp');self.assertEqual(self.p.provider.calls,[('play',1)]);await self.event('keyUp');self.assertEqual(len(self.p.provider.calls),1)
 async def test_hold_then_release_does_not_toggle(self):
  await self.event();self.p.status_pressed-=1
  await self.event('keyUp');self.assertEqual(self.p.view_mode,'devices');self.assertEqual(self.p.provider.calls,[])
 async def test_timer_opens_before_release(self):
  await self.event();await asyncio.sleep(.75);self.assertEqual(self.p.view_mode,'devices');await self.event('keyUp');self.assertEqual(self.p.provider.calls,[])
 async def test_mode_cancels_hold(self):
  await self.event();await self.event(ctx='mode');await asyncio.sleep(.75);await self.event('keyUp');self.assertEqual(self.p.modes.active,'desktop');self.assertEqual(self.p.provider.calls,[])
 async def test_back_returns_home(self):
  await self.p.open_devices();await self.event(ctx='back');self.assertEqual(self.p.view_mode,'normal')
 async def test_late_transfer_completion_keeps_desktop(self):
  self.p.devices.transfer=AsyncMock(return_value=True);self.p.modes.active='desktop';await self.p.switch_device('a',self.p.mode_generation);self.assertEqual(self.p.modes.active,'desktop')
