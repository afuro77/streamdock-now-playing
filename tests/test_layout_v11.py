import base64
import io
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from streamdock_now_playing.renderer import LayoutRenderer, DisplaySettings, fit_lines, _font, clock_text, operation_feedback
from streamdock_now_playing.streamdock import Plugin
from test_behavior import FakeMedia, FakeWS


def decode(value):
    return Image.open(io.BytesIO(base64.b64decode(value.split(',', 1)[1]))).convert('RGB')


SNAPSHOT = {'title': 'Current title', 'artist': 'Current artist', 'album': 'Current album',
            'playing': True, 'position': 64, 'duration': 240, 'source': 'example.exe'}


class RendererTests(unittest.TestCase):
    def test_square_cover_keeps_all_four_corners(self):
        source = Image.new('RGB', (256, 256))
        colors = ['red', 'green', 'blue', 'yellow']
        for index, color in enumerate(colors):
            x, y = index % 2 * 128, index // 2 * 128
            source.paste(color, (x, y, x+128, y+128))
        buffer = io.BytesIO(); source.save(buffer, 'PNG')
        result = LayoutRenderer().artwork(buffer.getvalue())
        self.assertEqual(len(result), 4)
        restored = Image.new('RGB', source.size)
        for index, tile in enumerate(result):
            restored.paste(decode(tile), (index % 2 * 128, index // 2 * 128))
        self.assertEqual(restored.tobytes(), source.tobytes())

    def test_non_square_art_is_letterboxed_not_cropped(self):
        image = Image.new('RGB', (256, 128), 'red')
        buffer = io.BytesIO(); image.save(buffer, 'PNG')
        tiles = LayoutRenderer().artwork(buffer.getvalue())
        top = decode(tiles[0])
        self.assertEqual(top.getpixel((64, 0)), (20, 43, 37))
        self.assertEqual(top.getpixel((64, 127)), (255, 0, 0))

    def test_row_major_mapping(self):
        renderer = LayoutRenderer()
        result = renderer.compose(['TL', 'TR', 'BL', 'BR'], SNAPSHOT)
        self.assertEqual([result[n] for n in (0, 1, 3, 4)], ['TL', 'TR', 'BL', 'BR'])
        self.assertEqual(result[2], renderer.metadata(SNAPSHOT))
        self.assertEqual(result[5], renderer.status(SNAPSHOT))

    def test_feedback_changes_only_bottom_right(self):
        renderer = LayoutRenderer(); art = renderer.artwork(None)
        normal = renderer.compose(art, SNAPSHOT)
        active = renderer.compose(art, SNAPSHOT, 'VOLUME 42%')
        self.assertEqual(normal[:5], active[:5])
        self.assertNotEqual(normal[5], active[5])

    def test_metadata_and_status_are_independent(self):
        renderer = LayoutRenderer(); art = renderer.artwork(None)
        normal = renderer.compose(art, SNAPSHOT)
        progress = renderer.compose(art, {**SNAPSHOT, 'position': 90})
        title = renderer.compose(art, {**SNAPSHOT, 'title': 'A different title'})
        self.assertEqual([i for i in range(6) if normal[i] != progress[i]], [5])
        self.assertEqual([i for i in range(6) if normal[i] != title[i]], [2])

    def test_long_text_fits_and_has_ellipsis(self):
        font = _font(16)
        for text in ['Very long song title ' * 20, 'とても長い日本語の曲名' * 20]:
            result = fit_lines(text, font, 116, 2)
            self.assertLessEqual(len(result), 2)
            self.assertTrue(result[-1].endswith('…'))
            self.assertTrue(all(font.getlength(line) <= 116 for line in result))

    def test_missing_and_invalid_times_do_not_crash(self):
        renderer = LayoutRenderer()
        for value in (None, -1, float('nan'), float('inf')):
            self.assertEqual(clock_text(value), '0:00')
            self.assertEqual(decode(renderer.status({'position': value})).size, (128, 128))
        self.assertEqual(clock_text(3661), '1:01:01')

    def test_progress_can_be_disabled(self):
        shown = decode(LayoutRenderer().status(SNAPSHOT))
        hidden = decode(LayoutRenderer({'show_progress': False}).status(SNAPSHOT))
        self.assertNotEqual(shown.getpixel((10, 111)), hidden.getpixel((10, 111)))

    def test_feedback_format_preserves_errors(self):
        self.assertEqual(operation_feedback('play', 'Play / Pause', {'playing': True}), 'PAUSE')
        self.assertEqual(operation_feedback('play', 'Play / Pause', {'playing': False}), 'PLAY')
        self.assertEqual(operation_feedback('play', 'play rejected', SNAPSHOT), 'PLAY REJECTED')
        self.assertEqual(operation_feedback('volume', 'Volume 42%', SNAPSHOT), 'VOL 42%')
        self.assertEqual(operation_feedback('previous', 'PREVIOUS', SNAPSHOT), 'PREV')

    def test_display_settings_validation(self):
        self.assertEqual(DisplaySettings.from_config({'feedback_seconds': 4}).feedback_seconds, 4)
        for invalid in ({'feedback_seconds': -1}, {'title_font_size': 2}, {'show_progress': 'yes'}, {'text_overflow': 'invalid'}):
            with self.assertRaises(ValueError): DisplaySettings.from_config(invalid)

    def test_large_metadata_has_no_header_or_album(self):
        with patch('streamdock_now_playing.renderer.ImageDraw.Draw') as draw:
            LayoutRenderer().metadata({**SNAPSHOT, 'album': 'ALBUM MUST NOT APPEAR'})
        calls = draw.return_value.text.call_args_list
        texts = [call.args[1] for call in calls]
        self.assertFalse(any('NOW PLAYING' in text or 'ALBUM' in text for text in texts))
        self.assertTrue(any('Current' in text for text in texts))
        self.assertGreaterEqual(calls[0].kwargs['font'].size, 28)
        self.assertEqual(calls[-1].kwargs['font'].size, 20)

    def test_large_status_has_only_state_and_elapsed(self):
        with patch('streamdock_now_playing.renderer.ImageDraw.Draw') as draw:
            LayoutRenderer().status(SNAPSHOT)
        calls = draw.return_value.text.call_args_list
        self.assertEqual([call.args[1] for call in calls], ['PLAY', '1:04'])
        self.assertTrue(all(call.kwargs['font'].size >= 28 for call in calls))

    def test_large_feedback_stays_within_two_lines(self):
        for text in ('VOL 42%', 'NEXT', 'PREV', 'SEEK +5s', 'SHUFFLE ON', 'PLAY', 'PAUSE'):
            with self.subTest(text=text), patch('streamdock_now_playing.renderer.ImageDraw.Draw') as draw:
                LayoutRenderer().status(SNAPSHOT, text)
                calls = draw.return_value.text.call_args_list
                self.assertLessEqual(len(calls), 2)
                self.assertTrue(all(call.kwargs['font'].size >= 20 for call in calls))
                self.assertTrue(all(call.kwargs['font'].getlength(call.args[1]) <= 120 for call in calls))


class LayoutHostTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.plugin = Plugin(provider=FakeMedia(), data_dir=temp.name, config={})
        self.plugin.ws = FakeWS(); self.plugin.snapshot = dict(SNAPSHOT)
        for index in range(6):
            await self.plugin.event({'event': 'willAppear', 'context': str(index), 'action': 'local.streamdock.nowplaying.dev.tile', 'payload': {'settings': {'tile': index}}})
        for role in ('volume', 'tracks', 'seek', 'mode', 'player', 'back'):
            await self.plugin.event({'event': 'willAppear', 'context': role, 'action': 'local.streamdock.nowplaying.dev.'+role, 'payload': {}})
        self.plugin.ws.messages.clear()

    def changed_images(self):
        return [message['context'] for message in self.plugin.ws.messages if message['event'] == 'setImage']

    async def test_operation_and_expiry_update_only_bottom_right(self):
        with patch('streamdock_now_playing.streamdock.time.monotonic', return_value=100):
            await self.plugin.event({'event': 'dialRotate', 'context': 'volume', 'payload': {'ticks': 1}})
        self.assertEqual(self.changed_images(), ['5'])
        self.assertEqual(self.plugin.until, 102.5)
        self.plugin.ws.messages.clear()
        with patch('streamdock_now_playing.streamdock.time.monotonic', return_value=102.49):
            await self.plugin.render()
        self.assertEqual(self.changed_images(), [])
        with patch('streamdock_now_playing.streamdock.time.monotonic', return_value=102.5):
            await self.plugin.render()
        self.assertEqual(self.changed_images(), ['5'])

    async def test_mode_round_trip_restores_spotify_artwork(self):
        before = list(self.plugin.images)
        await self.plugin.event({'event': 'keyDown', 'context': 'mode', 'payload': {}})
        self.assertEqual(self.plugin.view_mode, 'normal')
        self.assertEqual(self.plugin.modes.active, 'desktop')
        await self.plugin.event({'event': 'keyDown', 'context': 'mode', 'payload': {}})
        self.assertEqual(self.plugin.modes.active, 'spotify')
        self.assertEqual([self.plugin.images[i] for i in (0, 1, 3, 4)], [before[i] for i in (0, 1, 3, 4)])

    async def test_configurable_feedback_duration(self):
        self.plugin.layout = LayoutRenderer({'feedback_seconds': 4})
        with patch('streamdock_now_playing.streamdock.time.monotonic', return_value=100):
            await self.plugin.event({'event': 'dialDown', 'context': 'seek', 'payload': {}})
        self.assertEqual(self.plugin.until, 104)

    async def test_unassigned_press_keeps_all_six_images(self):
        await self.plugin.event({'event': 'dialDown', 'context': 'tracks', 'payload': {}})
        self.assertEqual(self.changed_images(), [])
        self.assertEqual(self.plugin.provider.calls, [])
