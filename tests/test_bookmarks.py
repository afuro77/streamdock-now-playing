import unittest
from unittest.mock import Mock
from streamdock_now_playing.bookmarks import BookmarkPlaylists

class BookmarkTests(unittest.TestCase):
 def source(self,fetch=None):
  self.client=Mock()
  self.client.playlists.side_effect=lambda offset:{'total':20,'items':[{'name':str(i)} for i in range(offset,offset+6)]}
  return BookmarkPlaylists(self.client,[{'id':'37i9dQZEVXcSn0mXuALPw4','name':'Fallback'}],fetch or (lambda pid:{'title':'Discover Weekly','thumbnail_url':'https://pickasso.spotifycdn.com/image/x'}))
 def test_prepends_without_skipping_remote_items(self):
  s=self.source();first=s.playlists(0);second=s.playlists(6)
  self.assertEqual(first['items'][0]['name'],'Discover Weekly');self.assertEqual(first['items'][-1]['name'],'4')
  self.assertEqual(second['items'][0]['name'],'5');self.assertEqual(first['total'],21)
 def test_metadata_cached(self):
  fetch=Mock(return_value={'title':'Test'});s=self.source(fetch);s.playlists();s.playlists();fetch.assert_called_once()
 def test_metadata_failure_keeps_bookmark(self):
  s=self.source(Mock(side_effect=OSError()));self.assertEqual(s.playlists()['items'][0]['name'],'Fallback')
 def test_library_error_still_allows_bookmark(self):
  s=self.source();self.client.playlists.side_effect=OSError()
  self.assertEqual(s.playlists()['items'][0]['uri'],'spotify:playlist:37i9dQZEVXcSn0mXuALPw4')
 def test_rejects_arbitrary_target(self):
  with self.assertRaises(ValueError):BookmarkPlaylists(Mock(),[{'id':'https://example.org'}])

class RecommendationsOnlyTests(unittest.TestCase):
 def test_library_never_requested_in_bookmark_only_mode(self):
  client=Mock();source=BookmarkPlaylists(client,[{'id':'37i9dQZEVXcSn0mXuALPw4','name':'Discover Weekly'}],fetcher=lambda pid:{},include_library=False)
  page=source.playlists();self.assertEqual(page['total'],1);self.assertEqual(len(page['items']),1)
  client.playlists.assert_not_called()
 def test_empty_bookmarks_do_not_fall_back_to_library(self):
  client=Mock();source=BookmarkPlaylists(client,[],include_library=False)
  self.assertEqual(source.playlists()['total'],0);client.playlists.assert_not_called()
