import asyncio
import io
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

from streamdock_now_playing.renderer import LayoutRenderer
from streamdock_now_playing.streamdock import Plugin
from test_behavior import FakeMedia, FakeWS
from test_layout_v11 import SNAPSHOT, decode


def image_bytes(color):
    buffer = io.BytesIO()
    Image.new('RGB', (256, 256), color).save(buffer, 'PNG')
    return buffer.getvalue()


class ExpandedRenderingTests(unittest.TestCase):
    def test_short_latin_word_is_not_split_into_orphan_letters(self):
        with patch('streamdock_now_playing.renderer.ImageDraw.Draw') as draw:
            LayoutRenderer().expanded_metadata({**SNAPSHOT, 'title': 'Porcelain'})
        self.assertEqual(''.join(c.args[1] for c in draw.return_value.text.call_args_list if c.args[0][1] < 128), 'Porcelain')

    def test_square_cover_keeps_aspect_and_every_pixel(self):
        source = Image.new('RGB', (256, 256), 'red')
        source.paste('green', (0, 0, 128, 128))
        source.paste('blue', (128, 128, 256, 256))
        buffer = io.BytesIO(); source.save(buffer, 'PNG')
        tiles = LayoutRenderer().expanded_artwork(buffer.getvalue())
        canvas = Image.new('RGB', (384, 256))
        for index, tile in enumerate(tiles):
            canvas.paste(decode(tile), (index % 3*128, index // 3*128))
        self.assertEqual(canvas.crop((64, 0, 320, 256)).tobytes(), source.tobytes())
        self.assertEqual(canvas.getpixel((0, 128)), (20, 43, 37))
        self.assertEqual(canvas.getpixel((383, 128)), (20, 43, 37))

    def test_expanded_information_has_large_title_and_smaller_artist(self):
        with patch('streamdock_now_playing.renderer.ImageDraw.Draw') as draw:
            result = LayoutRenderer().expanded_metadata(SNAPSHOT)
        self.assertEqual(len(result), 6)
        calls = draw.return_value.text.call_args_list
        self.assertGreater(calls[0].kwargs['font'].size, calls[-1].kwargs['font'].size)
        self.assertGreaterEqual(calls[0].kwargs['font'].size, 48)
        self.assertFalse(any('NOW PLAYING' in call.args[1] for call in calls))


class ExpandedInputTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.plugin = Plugin(provider=FakeMedia(), data_dir=temp.name, config={})
        self.plugin.snapshot = dict(SNAPSHOT); self.plugin.ws = FakeWS()
        for tile in range(6):
            await self.plugin.event({'event': 'willAppear', 'context': str(tile), 'action': 'local.streamdock.nowplaying.dev.tile', 'payload': {'settings': {'tile': tile}}})
        for role in ('volume', 'tracks', 'seek', 'mode', 'player', 'back'):
            await self.plugin.event({'event': 'willAppear', 'context': role, 'action': 'local.streamdock.nowplaying.dev.'+role, 'payload': {}})
        self.plugin.ws.messages.clear()

    async def press(self, tile):
        await self.plugin.event({'event': 'keyDown', 'context': str(tile), 'payload': {}})
        await self.plugin.event({'event': 'keyUp', 'context': str(tile), 'payload': {}})

    async def test_each_artwork_key_opens_cover_without_play_pause(self):
        for tile in (0, 1, 3, 4):
            await self.press(tile)
            self.assertEqual(self.plugin.view_mode, 'artwork')
            await self.press(tile)
            self.assertEqual(self.plugin.view_mode, 'normal')
        self.assertEqual(self.plugin.provider.calls, [])

    async def test_top_right_opens_information(self):
        await self.press(2)
        self.assertEqual(self.plugin.view_mode, 'metadata')
        self.assertEqual(self.plugin.images, self.plugin.layout.expanded_metadata(SNAPSHOT))
        self.assertEqual(self.plugin.provider.calls, [])

    async def test_bottom_right_toggles_play_once_in_normal_mode(self):
        before = list(self.plugin.images)
        await self.press(5)
        self.assertEqual(self.plugin.view_mode, 'normal')
        self.assertEqual(self.plugin.images[:5], before[:5])
        self.assertEqual(self.plugin.provider.calls, [('play', 1)])
        await self.plugin.event({'event': 'keyUp', 'context': '5', 'payload': {}})
        self.assertEqual(self.plugin.provider.calls, [('play', 1)])

    async def test_every_key_returns_from_both_expanded_modes(self):
        for entry in (0, 2):
            for exit_key in range(6):
                await self.press(entry)
                self.assertNotEqual(self.plugin.view_mode, 'normal')
                await self.press(exit_key)
                self.assertEqual(self.plugin.view_mode, 'normal')
        self.assertEqual(self.plugin.provider.calls, [])

    async def test_key_release_does_not_toggle_again(self):
        await self.press(0)
        await self.plugin.event({'event': 'keyUp', 'context': '0', 'payload': {}})
        self.assertEqual(self.plugin.view_mode, 'artwork')

    async def test_volume_never_replaces_expansion_or_leaks_on_return(self):
        for entry in (0, 2):
            await self.press(entry)
            before = list(self.plugin.images)
            self.plugin.ws.messages.clear()
            await self.plugin.event({'event': 'dialRotate', 'context': 'volume', 'payload': {'ticks': 1}})
            self.assertEqual(self.plugin.images, before)
            self.assertEqual(self.plugin.until, 0)
            self.assertEqual(self.plugin.ws.messages, [])
            await self.press(5)
            self.assertEqual(self.plugin.images[5], self.plugin.layout.status(SNAPSHOT))
        self.assertEqual(self.plugin.provider.calls, [('volume', 4), ('volume', 4)])

    async def test_entering_expansion_clears_prior_normal_feedback(self):
        await self.plugin.event({'event': 'dialRotate', 'context': 'volume', 'payload': {'ticks': 1}})
        self.assertGreater(self.plugin.until, 0)
        await self.press(0)
        self.assertEqual(self.plugin.until, 0)
        await self.press(5)
        self.assertEqual(self.plugin.images[5], self.plugin.layout.status(SNAPSHOT))

    async def test_knobs_and_lower_buttons_keep_their_commands(self):
        await self.press(0)
        for event, role, payload in [('dialDown', 'volume', {}), ('dialRotate', 'tracks', {'ticks': 1}),
                                     ('dialRotate', 'tracks', {'ticks': -1}), ('dialRotate', 'seek', {'ticks': 1}),
                                     ('dialDown', 'seek', {}), ('dialDown', 'tracks', {})]:
            await self.plugin.event({'event': event, 'context': role, 'payload': payload})
        self.assertEqual(self.plugin.provider.calls, [('play', 1), ('next', 1), ('previous', 1), ('shuffle', 1)])
        await self.plugin.event({'event': 'keyDown', 'context': 'mode', 'payload': {}})
        self.assertEqual(self.plugin.view_mode, 'normal')
        self.assertEqual(self.plugin.modes.active, 'desktop')
        await self.plugin.event({'event': 'keyDown', 'context': 'mode', 'payload': {}})
        await self.plugin.event({'event': 'keyDown', 'context': 'player', 'payload': {}})
        await self.plugin.event({'event':'keyUp','context':'player'})
        self.assertEqual(self.plugin.view_mode, 'queue')
        self.assertFalse(self.plugin.provider.fallback)
        await self.plugin.event({'event': 'keyDown', 'context': 'back', 'payload': {}})
        self.assertEqual(self.plugin.mode, 'art')
        self.assertEqual(self.plugin.view_mode, 'normal')

    async def test_polling_updates_new_song_in_both_expanded_modes(self):
        for mode in ('artwork', 'metadata'):
            with self.subTest(mode=mode):
                plugin = self.plugin; plugin.view_mode = mode; plugin.key = object()
                seen = []; done = asyncio.Event(); state = {'index': 0}
                async def snapshot():
                    state['index'] += 1
                    return {**SNAPSHOT, 'key': state['index'], 'title': 'Song '+str(state['index'])}
                async def artwork(s): return image_bytes('red' if s['key'] == 1 else 'blue')
                plugin.provider.snapshot = snapshot; plugin.provider.artwork = artwork
                original = plugin.render
                async def render():
                    await original()
                    seen.append(list(plugin.images))
                    if len(seen) == 2: done.set()
                plugin.render = render
                task = asyncio.create_task(plugin.polling())
                try:
                    await asyncio.wait_for(done.wait(), 3)
                    self.assertNotEqual(seen[0], seen[1])
                    self.assertEqual(plugin.view_mode, mode)
                finally:
                    task.cancel(); await asyncio.gather(task, return_exceptions=True)
                    plugin.render = original
