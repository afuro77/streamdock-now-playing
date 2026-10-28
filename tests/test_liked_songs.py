import unittest
from unittest.mock import Mock
from streamdock_now_playing.liked_songs import LikedFirst,SavedTracks
from streamdock_now_playing.spotify import SpotifyClient,SpotifyError
class LikedTests(unittest.TestCase):
 def test_first_entry_and_shifted_pagination(self):
  source=Mock();source.playlists.side_effect=lambda offset:{'items':[{'name':str(n)} for n in range(offset,offset+6)],'total':12}
  p=LikedFirst(source);first=p.playlists(0);second=p.playlists(6)
  self.assertEqual(first['items'][0]['uri'],'local:liked-songs');self.assertEqual(first['items'][-1]['name'],'4');self.assertEqual(second['items'][0]['name'],'5');self.assertEqual(first['total'],13)
 def test_liked_entry_survives_source_error(self):
  source=Mock();source.playlists.side_effect=OSError();self.assertEqual(LikedFirst(source).playlists()['items'][0]['uri'],'local:liked-songs')
 def test_saved_tracks_normalized(self):
  c=Mock();c.saved_tracks.return_value={'total':1,'items':[{'track':{'name':'Song','uri':'spotify:track:x','album':{'images':[{'url':'url'}]}}}]};p=SavedTracks(c).playlists(6);self.assertEqual(p['items'][0]['name'],'Song');c.saved_tracks.assert_called_once_with(6,6)
 def test_required_read_scope(self):
  c=SpotifyClient({},'.');c.request=Mock(return_value={});c.saved_tracks();self.assertEqual(c.request.call_args.args[2],'user-library-read')
 def test_saved_selection_keeps_following_tracks(self):
  c=SpotifyClient({},'.');c.saved_tracks=Mock(return_value={'items':[{'track':{'uri':'first'}},{'track':{'uri':'second'}}]});c.play_tracks=Mock();c.play_saved_selection('first',10);c.play_tracks.assert_called_once_with(['first','second']);c.saved_tracks.assert_called_once_with(10,50)
 def test_changed_library_does_not_play_wrong_track(self):
  c=SpotifyClient({},'.');c.saved_tracks=Mock(return_value={'items':[{'track':{'uri':'different'}}]});c.play_tracks=Mock()
  with self.assertRaises(SpotifyError):c.play_saved_selection('selected',0)
  c.play_tracks.assert_not_called()

class RecommendationPreservationTests(unittest.TestCase):
 def test_source_failure_keeps_registered_recommendations_after_liked(self):
  source=Mock();source.entries=[{'id':str(i),'name':'Mix '+str(i)} for i in range(8)];source.playlists.side_effect=OSError()
  wrapper=LikedFirst(source);first=wrapper.playlists(0);next_page=wrapper.playlists(6)
  self.assertEqual(first['total'],9);self.assertEqual(first['items'][0]['uri'],'local:liked-songs');self.assertEqual(first['items'][1]['name'],'Mix 0');self.assertEqual(next_page['items'][0]['name'],'Mix 5')
