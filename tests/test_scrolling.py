import asyncio
import tempfile
import unittest
from unittest.mock import patch
from streamdock_now_playing.renderer import LayoutRenderer, DisplaySettings
from streamdock_now_playing.streamdock import Plugin
from test_behavior import FakeMedia, FakeWS


class ScrollTests(unittest.TestCase):
    def test_artist_two_lines_preserve_full_name_and_title(self):
        r = LayoutRenderer()
        lines = r.artist_lines('Red Hot Chili Peppers Live Extended')
        self.assertTrue(all(lines))
        self.assertEqual(' '.join(lines), 'Red Hot Chili Peppers Live Extended')
        first = r.expanded_metadata({'title': 'Song', 'artist': 'Red Hot Chili Peppers'}, now=0)
        second = r.expanded_metadata({'title': 'Song', 'artist': 'Another Artist'}, now=0)
        self.assertEqual(first[:3], second[:3])
        self.assertEqual(r.artist_lines('Prince'), ['Prince', ''])

    def test_japanese_artist_without_spaces_uses_two_lines(self):
        r = LayoutRenderer()
        for name in ('レッド・ホット・チリ・ペッパーズ', '日本語のとても長いアーティスト名'):
            lines = r.artist_lines(name)
            self.assertTrue(all(lines))
            self.assertEqual(''.join(lines), name)

    def test_artist_fitting_one_row_is_not_split(self):
        r = LayoutRenderer()
        for name in ('Adrian Belew', 'Prince', '短い名前'):
            self.assertEqual(r.artist_lines(name), [name, ''])

    def test_short_text_static_and_large(self):
        r = LayoutRenderer()
        self.assertEqual(r.expanded_metadata({'title': 'Hi', 'artist': 'RHCP'}, now=0),
                         r.expanded_metadata({'title': 'Hi', 'artist': 'RHCP'}, now=20))
        self.assertEqual(r.text_row('Hi', 64, True, 0, 0)[0].size, 64)

    def test_continuous_text_moves_right_to_left_without_truncation(self):
        r = LayoutRenderer()
        for row, text, size in ((0, "Road Trippin'", 48), (1, 'Red Hot Chili Peppers', 36)):
            font, head = r.text_row(text, size, row == 0, row, 0)
            self.assertEqual(head[0][0], text)
            self.assertEqual(font.size, size)
            later = r.text_row(text, size, row == 0, row, 2)[1]
            if r._scroll_rows[row]['width'] > 372:
                self.assertLess(later[0][1], head[0][1])
            else:
                self.assertEqual(later, head)

    def test_next_copy_enters_before_previous_copy_disappears(self):
        r = LayoutRenderer(); text = 'Desecration Smile'
        r.text_row(text, 48, True, 0, 0)
        width = r._scroll_rows[0]['width']
        speed = r.settings.expanded_scroll_pixels_per_second
        moment = (6+width+64-350)/speed
        _, copies = r.text_row(text, 48, True, 0, moment)
        self.assertEqual(len(copies), 3)
        self.assertEqual(copies[1][0], "｜")
        self.assertAlmostEqual(copies[2][1], 350)
        self.assertGreater(copies[0][1]+width, 0)
        self.assertAlmostEqual(copies[2][1]-(copies[0][1]+width), 64)
        _, repeat = r.text_row(text, 48, True, 0, moment+(width+64)/speed)
        self.assertAlmostEqual(copies[0][1], repeat[0][1])

    def test_no_pause_moves_immediately_at_constant_speed(self):
        r = LayoutRenderer(); text = 'Desecration Smile'
        start = r.text_row(text, 48, True, 0, 0)[1][0][1]
        x1 = r.text_row(text, 48, True, 0, .1)[1][0][1]
        x2 = r.text_row(text, 48, True, 0, .2)[1][0][1]
        self.assertAlmostEqual(start-x1, 3.6)
        self.assertAlmostEqual(x1-x2, 3.6)

    def test_short_text_is_centered(self):
        r = LayoutRenderer(); font, parts = r.text_row('Hi', 48, True, 0, 0)
        self.assertAlmostEqual(parts[0][1], (384-r._scroll_rows[0]['width'])/2)
        self.assertEqual(parts, r.text_row('Hi', 48, True, 0, 99)[1])

    def test_rows_independent_and_new_title_resets_only_title(self):
        r = LayoutRenderer(); s = {'title': 'Desecration Smile', 'artist': 'Red Hot Chili Peppers Live Extended Concert Recording Performance'}
        first = r.expanded_metadata(s, now=0)
        later = r.expanded_metadata(s, now=3)
        self.assertNotEqual(first[:3], later[:3]); self.assertNotEqual(first[3:], later[3:])
        changed = r.expanded_metadata({**s, 'title': 'New title'}, now=3)
        self.assertEqual(changed[3:], later[3:])
        self.assertEqual(r._scroll_rows[0]['start'], 3)
        self.assertEqual(r._scroll_rows[1]['start'], 0)

    def test_timing_validation(self):
        for field in ('expanded_timeout_seconds', 'expanded_scroll_pixels_per_second', 'expanded_scroll_pause_seconds'):
            for value in ((-1, float('nan'), True) if field == 'expanded_scroll_pause_seconds' else (0, float('nan'), True)):
                with self.assertRaises(ValueError): DisplaySettings.from_config({field: value})


class TimeoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_both_expansions_return_after_inactivity(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Plugin(provider=FakeMedia(), data_dir=directory, config={}); p.ws = FakeWS()
            for mode in ('artwork', 'metadata'):
                p.view_mode = mode; p.last_input = 100
                with patch('streamdock_now_playing.streamdock.time.monotonic', return_value=129.9):
                    await p.render(); self.assertEqual(p.view_mode, mode)
                with patch('streamdock_now_playing.streamdock.time.monotonic', return_value=130):
                    await p.render(); self.assertEqual(p.view_mode, 'normal')

    async def test_knob_renews_timeout_without_replacing_expansion(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Plugin(provider=FakeMedia(), data_dir=directory, config={}); p.ws = FakeWS()
            p.contexts['volume'] = {'role': 'volume', 'settings': {}}
            p.view_mode = 'metadata'; p.last_input = 100
            with patch('streamdock_now_playing.streamdock.time.monotonic', return_value=129):
                await p.event({'event': 'dialRotate', 'context': 'volume', 'payload': {'ticks': 1}})
            with patch('streamdock_now_playing.streamdock.time.monotonic', return_value=140):
                await p.render()
            self.assertEqual(p.view_mode, 'metadata'); self.assertEqual(p.last_input, 129)
            self.assertEqual(p.overlay, '')

