import tempfile
import unittest
from streamdock_now_playing.streamdock import Plugin
from test_behavior import FakeMedia


class ArtistAliasTests(unittest.TestCase):
    def test_exact_display_override_preserves_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Plugin(provider=FakeMedia(), data_dir=directory, config={
                'artist_aliases': {'レッド・ホット・チリ・ペッパーズ': 'Red Hot Chili Peppers'}})
            p.snapshot = {'artist': 'レッド・ホット・チリ・ペッパーズ', 'key': 'original', 'title': 'Song'}
            shown = p.display_snapshot()
            self.assertEqual(shown['artist'], 'Red Hot Chili Peppers')
            self.assertEqual(shown['key'], 'original')
            self.assertEqual(p.snapshot['artist'], 'レッド・ホット・チリ・ペッパーズ')
            p.snapshot['artist'] = 'Unknown'
            self.assertEqual(p.display_snapshot()['artist'], 'Unknown')

    def test_invalid_mapping_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for aliases in ([], {'Artist': None}, {'Artist': ''}):
                with self.assertRaises(ValueError):
                    Plugin(provider=FakeMedia(), data_dir=directory, config={'artist_aliases': aliases})
