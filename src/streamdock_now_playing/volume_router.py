"""Automatic local/Spotify Connect volume routing, isolated from media controls."""
import asyncio
import os
import socket
import time
from .spotify import SpotifyError


class AutoVolume:
    def __init__(self, client, local_adjust, feedback, hostname=None):
        self.client = client
        self.local_adjust = local_adjust
        self.feedback = feedback
        names = [hostname] if hostname else [os.environ.get('COMPUTERNAME'), socket.gethostname()]
        self.local_names = {name.casefold() for name in names if name}
        self.local_ids = set()
        self.device_cache = []
        self.devices_updated = -float('inf')
        self.pending = 0
        self.task = None
        self.last_target = None
        self.last_device = None
        self.last_reported = None
        self.last_write = 0

    def handles(self, source):
        settings = self.client.settings
        return (bool(settings.get('enabled')) and settings.get('auto_volume', True)
                and 'spotify' in str(source or '').casefold())

    def active_device(self):
        playback = self.client.playback()
        primary = playback.get('device') or {}
        now = time.monotonic()
        if now-self.devices_updated >= 30 or not primary.get('id'):
            self.device_cache = self.client.devices()
            self.devices_updated = now
            for device in self.device_cache:
                if (str(device.get('type', '')).casefold() == 'computer'
                        and str(device.get('name', '')).casefold() in self.local_names
                        and device.get('id')):
                    self.local_ids.add(device['id'])
        if primary.get('id') and primary.get('is_active') is True:
            # Playback State is authoritative; cached listing only fills fields
            # missing from that fresh response, never replaces current volume.
            match = next((d for d in self.device_cache if d.get('id') == primary['id']), {})
            return {**match, **primary}
        # No current playback is not evidence that a cached device is active.
        fresh = self.client.devices()
        active = [d for d in fresh if d.get('is_active') is True]
        return active[0] if len(active) == 1 else None

    def classify(self, device):
        if not device or not device.get('id'): return 'unknown'
        kind = str(device.get('type', '')).casefold()
        name = str(device.get('name', '')).casefold()
        if kind == 'computer':
            if device['id'] in self.local_ids or name in self.local_names:
                self.local_ids.add(device['id'])
                return 'local'
            return 'unknown'  # A different/renamed computer is ambiguous.
        return 'remote' if kind else 'unknown'

    async def adjust(self, amount):
        try:
            device = await asyncio.to_thread(self.active_device)
            kind = self.classify(device)
            if kind == 'local':
                self.last_device = None
                # Keep pycaw/COM on its existing event-loop thread.
                return await self.local_adjust(amount)
            if kind == 'unknown': return 'Volume target unknown'
            # Once remote is established, NEVER fall back to Windows volume.
            if device.get('is_restricted') is not False or device.get('supports_volume') is not True:
                return 'Volume unsupported'
            reported = device.get('volume_percent')
            if type(reported) is not int or not 0 <= reported <= 100:
                return 'Volume unavailable'
            base = reported
            if (self.last_device == device['id'] and self.last_reported == reported
                    and self.last_target is not None and time.monotonic()-self.last_write < 2):
                base = self.last_target
            target = max(0, min(100, base+amount))
            await asyncio.to_thread(self.client.set_volume, device['id'], target)
            self.last_device = device['id']; self.last_target = target
            self.last_reported = reported; self.last_write = time.monotonic()
            # Confirm the displayed value, not merely a successful HTTP 204.
            for delay in (.15, .3):
                await asyncio.sleep(delay)
                current = await asyncio.to_thread(self.client.playback)
                actual = current.get('device') or {}
                if actual.get('id') != device['id']:
                    self.last_device = None
                    return 'Volume target changed'
                value = actual.get('volume_percent')
                if type(value) is int and 0 <= value <= 100 and (value != reported or value == target):
                    self.last_target = value
                    return 'Volume '+str(value)+'%'
            return 'Volume pending'
        except SpotifyError as error:
            text = str(error)
            if 'permission' in text or 'sign-in' in text: return 'Volume reconnect'
            if '429' in text or 'retry' in text: return 'Volume retry later'
            return 'Volume unavailable'
        except Exception:
            return 'Volume unavailable'

    def submit(self, amount):
        self.pending += amount
        if not self.task or self.task.done(): self.task = asyncio.create_task(self.run())

    async def run(self):
        await asyncio.sleep(.08)  # Merge adjacent encoder ticks, preserving ±2/tick.
        while self.pending:
            amount, self.pending = self.pending, 0
            result = await self.adjust(amount)
            await self.feedback(result)
            if self.pending: await asyncio.sleep(.12)
