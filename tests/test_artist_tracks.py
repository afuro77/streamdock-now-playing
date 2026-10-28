import json,unittest,asyncio
from unittest.mock import Mock,AsyncMock
from streamdock_now_playing.artist_tracks import parse_tracks,ArtistTracksSource,ArtistBrowser
from streamdock_now_playing.spotify import SpotifyClient,SpotifyError
import test_track_details as detail
A='6S0GHTqz5sxK5f9HtLXn9q';T='23Llyuevgg4Dt5vNdZcEEf'
def page(rows=None,artist=A):
 data={'props':{'pageProps':{'state':{'data':{'entity':{'uri':'spotify:artist:'+artist,'trackList':rows if rows is not None else [{'uri':'spotify:track:'+T,'title':'Song'}]}}}}}}
 return '<script id="__NEXT_DATA__" type="application/json">'+json.dumps(data)+'</script>'
class SourceTests(unittest.TestCase):
 def test_parse_order_and_uri(self):self.assertEqual(parse_tracks(page(),A)[0]['uri'],'spotify:track:'+T)
 def test_wrong_artist_rejected(self):
  with self.assertRaises(ValueError):parse_tracks(page(artist=T),A)
 def test_invalid_structure_rejected(self):
  with self.assertRaises(Exception):parse_tracks('<html>changed</html>',A)
 def test_unplayable_and_invalid_skipped(self):self.assertEqual(parse_tracks(page([{'uri':'bad'},{'uri':'spotify:track:'+T,'isPlayable':False}]),A),[])
 def test_cache_page_and_image(self):
  fetch=Mock(return_value=page());images=Mock(return_value='https://i.scdn.co/image/x');s=ArtistTracksSource(A,fetch,images)
  s.playlists();s.playlists();fetch.assert_called_once();images.assert_called_once()
 def test_image_failure_preserves_selection(self):
  s=ArtistTracksSource(A,lambda _:page(),Mock(side_effect=OSError()))
  self.assertEqual(s.playlists()['items'][0]['uri'],'spotify:track:'+T)
 def test_network_failure_not_cached(self):
  s=ArtistTracksSource(A,Mock(side_effect=OSError()),lambda _:None)
  with self.assertRaises(OSError):s.playlists()
  self.assertIsNone(s.rows)
 def test_track_play_body(self):
  c=SpotifyClient({},'.');c.request=Mock();c.play_track('spotify:track:'+T)
  self.assertEqual(c.request.call_args.kwargs['body'],{'uris':['spotify:track:'+T]})
  with self.assertRaises(SpotifyError):c.play_track('spotify:artist:'+A)
class InputTests(unittest.IsolatedAsyncioTestCase):
 asyncSetUp=detail.DetailInputTests.asyncSetUp
 event=detail.DetailInputTests.event
 async def asyncTearDown(self):
  await self.p.artist_browser.close();await self.p.track_details.close()
 async def test_artist_press_opens_and_back_restores_detail(self):
  self.p.track_details.data={'artists':[{'id':A,'name':'Garbage'}]}
  self.p.view_mode='metadata';self.p.detail_page=1
  self.p.render=AsyncMock()
  await self.event('tile');self.assertEqual(self.p.view_mode,'artist_tracks')
  await self.event('back');self.assertEqual(self.p.view_mode,'metadata');self.assertEqual(self.p.detail_page,1)
 async def test_track_artist_row_opens(self):
  self.p.track_details.data={'artists':[{'id':A}]};self.p.view_mode='metadata';self.p.detail_page=0
  self.p.contexts['tile']['settings']['tile']=4;self.p.render=AsyncMock()
  await self.event('tile');self.assertEqual(self.p.view_mode,'artist_tracks')
 async def test_missing_artist_keeps_detail(self):
  self.p.view_mode='metadata';self.p.detail_page=1;await self.event('tile')
  self.assertEqual(self.p.view_mode,'normal')
 async def test_success_does_not_leave_desktop(self):
  browser=Mock();browser.client.rows=[{'uri':'spotify:track:'+T}];self.p.render=AsyncMock();self.p.queue_state.client.play_tracks=Mock()
  self.p.modes.active='desktop'
  await self.p.select_artist_track('spotify:track:'+T,self.p.mode_generation,browser)
  self.assertEqual(self.p.modes.active,'desktop')
 async def test_cache_same_artist(self):
  b=ArtistBrowser();b.open(A);first=b.browser;b.open(A);self.assertIs(b.browser,first);await b.close()

class ArtistResolutionTests(unittest.TestCase):
 def test_exact_artist(self):
  from streamdock_now_playing.artist_tracks import resolve_artist
  c=Mock();c.request.return_value={'artists':{'items':[{'id':A,'name':'Garbage'}]}}
  self.assertEqual(resolve_artist(c,{'artist':'GARBAGE'}),A)
 def test_localized_artist_uses_matching_track(self):
  from streamdock_now_playing.artist_tracks import resolve_artist
  c=Mock();c.request.side_effect=[{'artists':{'items':[]}},{'tracks':{'items':[{'name':'Song','duration_ms':180000,'artists':[{'id':A}]}]}}]
  self.assertEqual(resolve_artist(c,{'artist':'Localized','title':'Song','duration':180}),A)
 def test_ambiguous_track_artist_rejected(self):
  from streamdock_now_playing.artist_tracks import resolve_artist
  c=Mock();c.request.side_effect=[{}, {'tracks':{'items':[{'name':'Song','duration_ms':180000,'artists':[{'id':aid}]} for aid in (A,T)]}}]
  self.assertIsNone(resolve_artist(c,{'artist':'Unknown','title':'Song','duration':180}))
 def test_wrong_duration_rejected(self):
  from streamdock_now_playing.artist_tracks import resolve_artist
  c=Mock();c.request.side_effect=[{}, {'tracks':{'items':[{'name':'Song','duration_ms':100000,'artists':[{'id':A}]}]}}]
  self.assertIsNone(resolve_artist(c,{'artist':'Unknown','title':'Song','duration':180}))

class ResolveInputTests(unittest.IsolatedAsyncioTestCase):
 asyncSetUp=detail.DetailInputTests.asyncSetUp
 event=detail.DetailInputTests.event
 async def asyncTearDown(self):
  if self.p.artist_resolve_task:await self.p.artist_resolve_task
  await self.p.artist_browser.close();await self.p.track_details.close()
 async def test_missing_metadata_stays_and_resolves_in_background(self):
  from unittest.mock import patch
  self.p.queue_state.client.settings={'enabled':True};self.p.view_mode='metadata';self.p.detail_page=1;self.p.render=AsyncMock()
  with patch('streamdock_now_playing.streamdock.resolve_artist',return_value=A):
   await self.event('tile');self.assertEqual(self.p.view_mode,'metadata')
   await self.p.artist_resolve_task
  self.assertEqual(self.p.view_mode,'artist_tracks')
 async def test_late_resolution_does_not_leave_desktop(self):
  from unittest.mock import patch
  self.p.render=AsyncMock();snapshot=dict(self.p.snapshot);self.p.modes.active='desktop'
  with patch('streamdock_now_playing.streamdock.resolve_artist',return_value=A):
   await self.p.resolve_artist_entry(snapshot,self.p.mode_generation,'metadata')
  self.assertEqual(self.p.modes.active,'desktop');self.assertIsNone(self.p.artist_browser.browser)

class ArtistImageHostTests(unittest.TestCase):
 def test_observed_oembed_hosts_accepted(self):
  from streamdock_now_playing.queue_artwork import trusted_image_host
  for host in ('image-cdn-ak.spotifycdn.com','image-cdn-fa.spotifycdn.com'):
   self.assertTrue(trusted_image_host(host))
 def test_unrelated_or_suffix_spoof_hosts_rejected(self):
  from streamdock_now_playing.queue_artwork import trusted_image_host
  for host in ('evil.spotifycdn.com','image-cdn-ak.spotifycdn.com.example.org',None):
   self.assertFalse(trusted_image_host(host))

class ArtistPendingNavigationTests(unittest.IsolatedAsyncioTestCase):
 asyncSetUp=detail.DetailInputTests.asyncSetUp
 event=detail.DetailInputTests.event
 async def asyncTearDown(self):
  if self.p.artist_resolve_task:
   self.p.artist_resolve_task.cancel();await asyncio.gather(self.p.artist_resolve_task,return_exceptions=True)
  await self.p.artist_browser.close();await self.p.track_details.close()
 async def test_back_cancels_pending_lookup(self):
  self.p.view_mode='metadata';self.p.artist_resolve_task=asyncio.create_task(asyncio.sleep(100));self.p.render=AsyncMock()
  await self.event('back');await asyncio.sleep(0)
  self.assertTrue(self.p.artist_resolve_task.cancelled());self.assertEqual(self.p.view_mode,'normal')
 async def test_mode_cancels_pending_lookup(self):
  self.p.artist_resolve_task=asyncio.create_task(asyncio.sleep(100));self.p.render=AsyncMock()
  await self.event('mode');await asyncio.sleep(0)
  self.assertTrue(self.p.artist_resolve_task.cancelled());self.assertEqual(self.p.modes.active,'desktop')
 async def test_page_change_cancels_pending_lookup(self):
  self.p.view_mode='metadata';self.p.artist_resolve_task=asyncio.create_task(asyncio.sleep(100));self.p.render=AsyncMock()
  await self.event('seek','dialRotate',1);await asyncio.sleep(0)
  self.assertTrue(self.p.artist_resolve_task.cancelled())
 async def test_failed_play_keeps_browser(self):
  self.p.view_mode='artist_tracks';self.p.queue_state.client.play_tracks=Mock(side_effect=SpotifyError('403',status=403));self.p.render=AsyncMock();browser=Mock();browser.client.rows=[{'uri':'spotify:track:'+T}]
  await self.p.select_artist_track('spotify:track:'+T,self.p.mode_generation,browser)
  self.assertEqual(self.p.view_mode,'artist_tracks');self.assertEqual(browser.message,'PLAY 403')
 async def test_stale_resolution_after_track_change_ignored(self):
  from unittest.mock import patch
  self.p.view_mode='metadata';self.p.render=AsyncMock();old=dict(self.p.snapshot);self.p.snapshot=dict(old,title='Different')
  with patch('streamdock_now_playing.streamdock.resolve_artist',return_value=A):await self.p.resolve_artist_entry(old,self.p.mode_generation,'metadata')
  self.assertIsNone(self.p.artist_browser.browser)

class ArtistPlaybackSequenceTests(unittest.TestCase):
 def test_selected_entry_keeps_next_tracks_and_wraps_remaining(self):
  from streamdock_now_playing.artist_tracks import playback_uris
  rows=[{'uri':'a'},{'uri':'b'},{'uri':'c'}]
  self.assertEqual(playback_uris(rows,'b'),['b','c','a'])
 def test_last_entry_still_has_following_tracks(self):
  from streamdock_now_playing.artist_tracks import playback_uris
  self.assertEqual(playback_uris([{'uri':'a'},{'uri':'b'}],'b'),['b','a'])
 def test_invalid_selection_rejected(self):
  from streamdock_now_playing.artist_tracks import playback_uris
  with self.assertRaises(ValueError):playback_uris([{'uri':'a'}],'missing')
 def test_player_receives_multiple_tracks(self):
  c=SpotifyClient({},'.');c.request=Mock();uris=['spotify:track:'+T,'spotify:track:'+A];c.play_tracks(uris)
  self.assertEqual(c.request.call_args.kwargs['body'],{'uris':uris})
 def test_invalid_track_lists_rejected(self):
  c=SpotifyClient({},'.');c.request=Mock()
  for rows in ([],['bad'],['spotify:artist:'+A],None):
   with self.assertRaises(SpotifyError):c.play_tracks(rows)
  c.request.assert_not_called()
