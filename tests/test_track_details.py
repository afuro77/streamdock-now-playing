import asyncio,io,tempfile,threading,time,unittest
from unittest.mock import Mock,patch
from PIL import Image
from streamdock_now_playing.track_details import TrackDetails,identity
from streamdock_now_playing.spotify import SpotifyError
from streamdock_now_playing.streamdock import Plugin
from streamdock_now_playing.detail_renderer import DetailRenderer
from test_behavior import FakeMedia,FakeWS

SNAP={'source':'Spotify.exe','title':'Song','artist':'Artist','album':'Album','duration':120}
def track(tid='t',title='Song',artists=None):
 return {'id':tid,'type':'track','name':title,'duration_ms':120000,'artists':artists or [{'id':'a','name':'Artist'}],
 'album':{'name':'Album','release_date':'2002-01-01','total_tracks':12},'track_number':3}
def picture():
 im=Image.new('RGB',(200,100),'red');b=io.BytesIO();im.save(b,'PNG');return b.getvalue()
class Client:
 def __init__(self):self.settings={'enabled':True};self.item=track();self.calls=[];self.error=None
 def playback(self):
  self.calls.append('playback')
  if self.error:raise self.error
  return {'item':self.item}
 def request(self,method,path):
  self.calls.append(path)
  if path.startswith('/tracks/'):return dict(self.item)
  return {'id':path.split('/')[-1],'name':'Artist','images':[{'url':'https://i.scdn.co/test'}]}

class EnrichmentTests(unittest.IsolatedAsyncioTestCase):
 async def load(self,s,snapshot=None):
  s.request(snapshot or SNAP)
  if s.task:await s.task
 async def test_cache_shared_artist_between_tracks(self):
  c=Client();loader=Mock(return_value=picture());s=TrackDetails(c,loader)
  await self.load(s);c.item=track('t2','Other');await self.load(s,dict(SNAP,title='Other'))
  self.assertEqual(c.calls.count('/artists/a'),1);loader.assert_called_once()
  c.item=track();await self.load(s)
  self.assertEqual(c.calls.count('/tracks/t'),1)
 async def test_multiple_artist_structure_and_independent_cache(self):
  c=Client();c.item=track(artists=[{'id':'a','name':'One'},{'id':'b','name':'Two'}]);s=TrackDetails(c,lambda url:picture())
  await self.load(s);self.assertEqual([a['id'] for a in s.data['artists']],['a','b'])
  self.assertIn('/artists/b',c.calls)
 async def test_missing_images_is_valid_fallback(self):
  c=Client();original=c.request
  c.request=lambda method,path:({'images':[],'name':'No photo'} if path.startswith('/artists') else original(method,path))
  loader=Mock();s=TrackDetails(c,loader);await self.load(s)
  self.assertIsNone(s.data['artists'][0]['image']);loader.assert_not_called()
  self.assertEqual(len(DetailRenderer().artist(s.data,SNAP,'')),6)
 async def test_bad_image_falls_back(self):
  data={'artists':[{'name':'Name','image':b'bad'}]}
  self.assertEqual(len(DetailRenderer().artist(data,SNAP,'')),6)
 async def test_429_and_network_errors_back_off(self):
  for error in (SpotifyError('429',retry_after=90,status=429),OSError('offline')):
   c=Client();c.error=error;s=TrackDetails(c)
   await self.load(s);self.assertIsNone(s.data);old=len(c.calls);s.request(SNAP)
   self.assertEqual(len(c.calls),old);self.assertGreater(s.retry_at,time.monotonic())
 async def test_unauthenticated_does_not_start(self):
  c=Client();c.settings={};s=TrackDetails(c);await self.load(s)
  self.assertEqual(c.calls,[]);self.assertIsNone(s.data)
 async def test_mismatched_track_never_published(self):
  c=Client();c.item=track(title='Wrong');s=TrackDetails(c);await self.load(s)
  self.assertIsNone(s.data);self.assertNotIn('/tracks/t',c.calls)
 async def test_old_inflight_result_ignored_after_song_change(self):
  c=Client();s=TrackDetails(c);entered=threading.Event();release=threading.Event()
  def fetch(snapshot):entered.set();release.wait(2);return {'id':'old'}
  s.fetch=fetch;s.request(SNAP)
  await asyncio.to_thread(entered.wait,1)
  s.request(dict(SNAP,title='New'));release.set();await s.task
  self.assertIsNone(s.data);self.assertEqual(s.key,identity(dict(SNAP,title='New')))
 async def test_song_change_clears_cached_display_immediately(self):
  c=Client();s=TrackDetails(c);await self.load(s)
  self.assertIsNotNone(s.data);c.settings={};s.request(dict(SNAP,title='New'))
  self.assertIsNone(s.data)
 async def test_artist_api_failure_preserves_track_album(self):
  c=Client();original=c.request
  def request(method,path):
   if path.startswith('/artists'):raise SpotifyError('403',status=403)
   return original(method,path)
  c.request=request;s=TrackDetails(c);await self.load(s)
  self.assertEqual(s.data['id'],'t');self.assertIsNone(s.data['artists'][0]['image'])
 def test_bounded_cache(self):
  from collections import OrderedDict
  cache=OrderedDict()
  for i in range(100):TrackDetails.put(cache,i,i,32)
  self.assertEqual(len(cache),32)

class DetailInputTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.p=Plugin(provider=FakeMedia(),data_dir=self.temp.name,config={});self.p.ws=FakeWS();self.p.snapshot=dict(SNAP)
  self.p.contexts={'tile':{'role':'tile','settings':{'tile':2}},'seek':{'role':'seek','settings':{}},'back':{'role':'back','settings':{}},'mode':{'role':'mode','settings':{}}}
 async def event(self,role,event='keyDown',ticks=0):await self.p.event({'event':event,'context':role,'payload':{'ticks':ticks}})
 async def test_page_cycle_both_directions_no_seek(self):
  await self.event('tile')
  for view,page in [('metadata',1),('metadata',2),('artwork',2),('metadata',0)]:
   await self.event('seek','dialRotate',1)
   self.assertEqual((self.p.view_mode,self.p.detail_page),(view,page))
  await self.event('seek','dialRotate',-1);self.assertEqual(self.p.view_mode,'artwork')
  self.assertEqual(self.p.provider.calls,[])
 async def test_back_from_each_page_returns_normal(self):
  for page in range(3):
   self.p.view_mode='metadata';self.p.detail_page=page;await self.event('back')
   self.assertEqual(self.p.view_mode,'normal')
 async def test_track_page_keeps_existing_scroller(self):
  await self.event('tile');self.assertEqual(self.p.images,self.p.layout.expanded_metadata(self.p.display_snapshot()))
 async def test_artist_and_album_work_without_api(self):
  self.p.view_mode='metadata'
  for page in (1,2):self.p.detail_page=page;await self.p.render();self.assertEqual(len(self.p.images),6)
 async def test_async_completion_after_desktop_cannot_draw(self):
  c=Client();self.p.track_details=TrackDetails(c,lambda url:picture())
  await self.event('tile');task=self.p.track_details.task
  await self.event('mode');before=list(self.p.images)
  await task;await self.p.render()
  self.assertEqual(self.p.modes.active,'desktop');self.assertEqual(self.p.images,before)
 async def test_normal_seek_remains_unchanged(self):
  await self.event('seek','dialRotate',1)
  self.assertEqual(self.p.provider.calls,[('seek',5)])
 async def asyncTearDown(self):await self.p.track_details.close()

class ArtworkDetailTests(unittest.IsolatedAsyncioTestCase):
 asyncSetUp=DetailInputTests.asyncSetUp
 asyncTearDown=DetailInputTests.asyncTearDown
 event=DetailInputTests.event
 async def test_cover_entry_cycles_four_pages(self):
  self.p.contexts['tile']['settings']['tile']=0
  await self.event('tile');self.assertEqual(self.p.view_mode,'artwork')
  for view,page in [('metadata',0),('metadata',1),('metadata',2),('artwork',2)]:
   await self.event('seek','dialRotate',1)
   self.assertEqual((self.p.view_mode,self.p.detail_page),(view,page))
  self.assertEqual(self.p.provider.calls,[])
 async def test_reverse_from_cover_opens_album(self):
  self.p.view_mode='artwork';await self.event('seek','dialRotate',-1)
  self.assertEqual((self.p.view_mode,self.p.detail_page),('metadata',2))
 async def test_top_right_enters_track_in_shared_four_page_set(self):
  self.p.detail_with_artwork=True
  await self.event('tile');self.assertTrue(self.p.detail_with_artwork)
  await self.event('seek','dialRotate',-1)
  self.assertEqual(self.p.view_mode,'artwork')
