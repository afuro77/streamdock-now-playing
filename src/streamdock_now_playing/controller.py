"""Commands depend on a media provider and an audio adapter, not a player."""
from .media import MediaSessionProvider


class MediaController:
    def __init__(self, provider: MediaSessionProvider, audio):
        self.provider, self.audio = provider, audio

    async def command(self, name, amount=1):
        s = await self.provider.refresh()
        if not s:
            return 'Media unavailable'
        c = s.get_playback_info().controls
        if name == 'play':
            ok = await s.try_toggle_play_pause_async()
        elif name in ('next', 'previous'):
            if not getattr(c, 'is_' + name + '_enabled'):
                return 'Unsupported'
            ok = await getattr(s, 'try_skip_' + name + '_async')()
        elif name == 'seek':
            if not c.is_playback_position_enabled:
                return 'Seek unsupported'
            t = s.get_timeline_properties()
            pos = max(t.start_time.total_seconds(), min(t.end_time.total_seconds(), t.position.total_seconds() + amount))
            ok = await s.try_change_playback_position_async(int(pos * 10_000_000))
        elif name == 'shuffle':
            if not c.is_shuffle_enabled:
                return 'Shuffle unsupported'
            info = s.get_playback_info()
            requested = not info.is_shuffle_active
            ok = await s.try_change_shuffle_active_async(requested)
        elif name == 'volume':
            return self.audio.adjust(s.source_app_user_model_id, amount)
        else:
            return 'Unsupported'
        if not ok:
            return name + ' rejected'
        if name == 'shuffle':
            return 'Shuffle ' + ('ON' if requested else 'OFF')
        if name == 'seek':
            return f'Seek {amount:+d}s'
        return 'Play / Pause' if name == 'play' else name.upper()


class MediaService:
    """Compatibility facade preserving the proven host adapter interface."""
    def __init__(self, provider, audio):
        self.media = provider
        self.controller = MediaController(provider, audio)

    @property
    def preferred(self): return self.media.preferred
    @preferred.setter
    def preferred(self, value): self.media.preferred = value
    @property
    def fallback(self): return self.media.fallback
    @fallback.setter
    def fallback(self, value): self.media.fallback = value
    async def snapshot(self): return await self.media.snapshot()
    async def artwork(self, snapshot): return await self.media.artwork(snapshot)
    async def command(self, name, amount=1): return await self.controller.command(name, amount)
