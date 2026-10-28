import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from websockets.asyncio.server import serve
from streamdock_now_playing.streamdock import Plugin
from streamdock_now_playing.runtime import read_config


class FakeProvider:
    preferred = ''
    fallback = False
    def __init__(self): self.calls = []
    async def snapshot(self): return {'key': None, 'title': 'Test', 'artist': '', 'source': 'example.exe'}
    async def artwork(self, snapshot): return None
    async def command(self, name, amount=1): self.calls.append((name, amount)); return name


class HostTests(unittest.IsolatedAsyncioTestCase):
    async def test_registration_input_and_disconnect_cleanup(self):
        provider = FakeProvider()
        registered = []
        async def host(ws):
            registered.append(json.loads(await ws.recv()))
            await ws.send(json.dumps({'event': 'willAppear', 'context': 'key', 'action': 'local.ajazz.media.volume', 'payload': {}}))
            # Wait for the actual host image protocol before issuing input.
            while json.loads(await ws.recv())['event'] != 'setImage': pass
            await ws.send(json.dumps({'event': 'dialDown', 'context': 'key', 'payload': {}}))
            while not provider.calls: await asyncio.sleep(.01)
            await ws.close()
        with tempfile.TemporaryDirectory() as directory:
            plugin = Plugin(provider=provider, data_dir=directory, config={})
            async with serve(host, '127.0.0.1', 0) as server:
                port = server.sockets[0].getsockname()[1]
                await asyncio.wait_for(plugin.run(SimpleNamespace(port=port, pluginUUID='test-id', registerEvent='registerPlugin')), 5)
            self.assertEqual(registered, [{'event': 'registerPlugin', 'uuid': 'test-id'}])
            self.assertEqual(provider.calls, [('play', 1)])
            self.assertFalse(json.loads((Path(directory) / 'status.json').read_text())['connected'])

    async def test_config_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(read_config(root), {})
            (root / 'config.json').write_text('{"audio_mappings": [null]}')
            with self.assertRaises(ValueError): read_config(root)
