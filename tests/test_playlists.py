import asyncio,json,tempfile,time,threading,unittest
from unittest.mock import Mock
from urllib.parse import parse_qs,urlsplit
from streamdock_now_playing.playlists import PlaylistBrowser
from streamdock_now_playing.spotify import SpotifyClient,SpotifyError,SCOPES
from streamdock_now_playing.streamdock import Plugin
from test_spotify_queue import Store
from test_behavior import FakeMedia,FakeWS

class Client:
 def __init__(self):self.calls=[];self.error=None
 def playlists(self,offset):
  self.calls.append(offset)
  if self.error:raise self.error
  return {'items':[{'name':str(i),'uri':'spotify:playlist:p'+str(i)} for i in range(offset,min(19,offset+6))],'total':19}

class BrowserTests(unittest.IsolatedAsyncioTestCase):
 async def load(self,b):
  for _ in range(3):
   b.request()
   if b.task:await b.task
   if b.loaded==b.page:break
 async def test_more_than_three_and_multiple_pages(self):
  c=Client();b=PlaylistBrowser(c);await self.load(b)
  self.assertEqual(len(b.items),3)
  for index in (1,2,3):b.move(1);await self.load(b);self.assertEqual(b.page,index)
  self.assertEqual(b.items[0]['name'],'3')
  b.move(100);await self.load(b);self.assertEqual(b.page,16)
  self.assertEqual(b.items[-1]['name'],'18');b.move(-100);await self.load(b)
  self.assertEqual(b.selected(5),'spotify:playlist:p2')
 async def test_loading_or_empty_cell_not_selectable(self):
  b=PlaylistBrowser(Client());self.assertIsNone(b.selected(0));await self.load(b)
  b.move(12);self.assertIsNone(b.selected(0));await self.load(b)
  self.assertEqual(b.selected(0),'spotify:playlist:p12')
  self.assertIsNone(b.selected(6))
 async def test_errors_backoff_and_no_stale_selection(self):
  for e in (SpotifyError('permission'),SpotifyError('429',90,status=429),OSError()):
   c=Client();c.error=e;b=PlaylistBrowser(c);await self.load(b)
   self.assertIsNone(b.selected(0));self.assertGreater(b.retry_at,time.monotonic())
   b.request();self.assertEqual(len(c.calls),1)
 async def test_late_response_does_not_publish_old_page(self):
  c=Client();b=PlaylistBrowser(c);await self.load(b)
  original=c.playlists;entered=threading.Event();release=threading.Event()
  def slow(offset):entered.set();release.wait(2);return original(offset)
  c.playlists=slow;b.move(6);b.request();await asyncio.to_thread(entered.wait,1)
  b.move(6);release.set();await b.task
  self.assertIsNone(b.loaded);await self.load(b);self.assertEqual(b.items[0]['name'],'12')
 async def test_six_cards_and_empty_browser(self):
  b=PlaylistBrowser(Client());self.assertEqual(len(b.render()),6);await self.load(b)
  self.assertEqual(len(b.render()),6)
  self.assertEqual(b.render()[3],b.render()[4])

class ApiTests(unittest.TestCase):
 def client(self):
  self.store=Store();self.store.value['scope']=SCOPES;self.calls=[]
  return SpotifyClient({'enabled':True,'client_id':'test'},'.',self.store,lambda *args:self.calls.append(args) or {})
 def test_page_limit_offset_scope(self):
  c=self.client();c.playlists(12)
  self.assertEqual(parse_qs(urlsplit(self.calls[-1][1]).query),{'limit':['6'],'offset':['12']})
  self.assertIn('playlist-read-private',SCOPES.split())
 def test_play_context_json(self):
  c=self.client();c.play_playlist('spotify:playlist:abc123')
  method,url,body,headers=self.calls[-1]
  self.assertEqual((method,url),('PUT','https://api.spotify.com/v1/me/player/play'))
  self.assertEqual(json.loads(body),{'context_uri':'spotify:playlist:abc123'})
  self.assertEqual(headers['Content-Type'],'application/json')
 def test_invalid_uri_rejected_without_request(self):
  c=self.client()
  with self.assertRaises(SpotifyError):c.play_playlist('https://other')
  self.assertEqual(self.calls,[])
 def test_missing_read_scope_does_not_block_queue(self):
  c=self.client();self.store.value['scope']='user-read-playback-state'
  with self.assertRaises(SpotifyError):c.playlists()
  c.queue();self.assertEqual(len(self.calls),1)

class IntegrationTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.p=Plugin(provider=FakeMedia(),data_dir=self.temp.name,config={});self.p.ws=FakeWS()
  self.p.queue_state.request=Mock();self.p.playlists.request=Mock()
  for r in ('player','mode','tracks','seek','back','0'):self.p.contexts[r]={'role':r if r!='0' else 'tile','settings':{'tile':0}}
 async def event(self,role,event='keyDown',ticks=0):await self.p.event({'event':event,'context':role,'payload':{'ticks':ticks}})
 async def test_short_queue_long_playlists_release_once(self):
  await self.event('player');await self.event('player','keyUp');self.assertEqual(self.p.view_mode,'queue')
  self.p.home_hold_seconds=.01;await self.event('player');await self.p.home_hold_task
  self.assertEqual(self.p.view_mode,'playlists');await self.event('player','keyUp');self.assertEqual(self.p.view_mode,'playlists')
 async def test_knob_pages_never_skips_tracks(self):
  self.p.view_mode='playlists';self.p.playlists.total=100
  await self.event('seek','dialRotate',2);self.assertEqual(self.p.playlists.page,2)
  self.assertEqual(self.p.provider.calls,[])
 async def test_left_knob_keeps_playback_in_playlist_view(self):
  self.p.view_mode='playlists'
  await self.event('tracks','dialRotate',1)
  self.assertEqual(self.p.provider.calls,[('next',1)])
 async def test_selection_completion_cannot_override_desktop(self):
  entered=threading.Event();release=threading.Event()
  def play(uri):entered.set();release.wait(2)
  self.p.queue_state.client.play_playlist=play;self.p.view_mode='playlists'
  task=asyncio.create_task(self.p.select_playlist('spotify:playlist:abc',self.p.mode_generation))
  await asyncio.to_thread(entered.wait,1);await self.event('mode');before=list(self.p.images)
  release.set();await task
  self.assertEqual(self.p.modes.active,'desktop');self.assertEqual(self.p.images,before)
 async def test_back_restores_previous_screen(self):
  self.p.view_mode='metadata';await self.p.open_playlists();await self.event('back')
  self.assertEqual(self.p.view_mode,'metadata')
 async def test_failed_play_does_not_leave_browser(self):
  self.p.view_mode='playlists';self.p.queue_state.client.play_playlist=Mock(side_effect=SpotifyError('403',status=403))
  await self.p.select_playlist('spotify:playlist:abc',self.p.mode_generation)
  self.assertEqual(self.p.view_mode,'playlists');self.assertEqual(self.p.playlists.message,'PLAY 403')

class PlaylistCoverTests(unittest.IsolatedAsyncioTestCase):
 async def test_text_and_image_select_same_column(self):
  b=PlaylistBrowser(Client());b.request();await b.task
  self.assertEqual(b.selected(0),b.selected(3));self.assertEqual(b.selected(1),b.selected(4))
  await b.close()
 async def test_visible_images_and_cache_reuse(self):
  c=Client();b=PlaylistBrowser(c);b.artwork.load=Mock(return_value='cached-cover')
  b.request();await b.task;await b.artwork_task
  self.assertEqual(b.render()[3:],['cached-cover']*3)
  b.move(1);b.request();await b.artwork_task
  self.assertEqual(c.calls,[0]);self.assertEqual([i['name'] for i in b.items],['1','2','3'])
  await b.close()
 async def test_cross_chunk_slide_loads_only_missing_chunk(self):
  c=Client();b=PlaylistBrowser(c);b.request();await b.task
  b.move(4);b.request();await b.task
  self.assertEqual(c.calls,[0,6]);self.assertEqual([i['name'] for i in b.items],['4','5','6'])
  await b.close()
 async def test_missing_images_still_selectable(self):
  b=PlaylistBrowser(Client());b.request();await b.task;await b.artwork_task
  self.assertEqual(len(b.render()),6);self.assertEqual(b.selected(3),'spotify:playlist:p0')
  await b.close()


