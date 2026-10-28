"""Session discovery, metadata and artwork; no player-specific API."""
import sys
from typing import Protocol


class MediaSessionProvider(Protocol):
    preferred: str
    fallback: bool

    async def refresh(self): ...
    async def snapshot(self) -> dict: ...
    async def artwork(self, snapshot: dict) -> bytes | None: ...


class GSMTCMedia:
    def __init__(self, preferred="", fallback=False, manager=None):
        # COM must be MTA before pycaw/comtypes is imported.
        sys.coinit_flags = 0
        self.preferred, self.fallback = preferred, fallback
        self.manager = manager
        self.session = None

    async def refresh(self):
        if self.manager is None:
            from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
            self.manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
        sessions = list(self.manager.get_sessions())
        self.session = next((s for s in sessions if self.preferred.lower() in s.source_app_user_model_id.lower()), None) if self.preferred else self.manager.get_current_session()
        if self.session is None and self.fallback:
            self.session = self.manager.get_current_session()
        return self.session

    async def snapshot(self):
        s = await self.refresh()
        if not s:
            return {"title": "Start a media player", "artist": "", "key": None, "image": None}
        p = await s.try_get_media_properties_async()
        i = s.get_playback_info()
        t = s.get_timeline_properties()
        return dict(title=p.title, artist=p.artist, album=p.album_title,
                    key=(s.source_app_user_model_id, p.title, p.artist, p.album_title),
                    thumbnail=p.thumbnail, playing=int(i.playback_status) == 4,
                    shuffle=i.is_shuffle_active, position=t.position.total_seconds(),
                    duration=t.end_time.total_seconds(), source=s.source_app_user_model_id,
                    controls={n: getattr(i.controls, n) for n in dir(i.controls) if n.startswith("is_")})

    async def artwork(self, snapshot):
        ref = snapshot.get("thumbnail")
        if ref is None:
            return None
        from winrt.windows.storage.streams import DataReader
        stream = await ref.open_read_async()
        reader = DataReader(stream)
        try:
            if stream.size > 10 * 1024 * 1024:
                return None
            await reader.load_async(stream.size)
            data = bytearray(stream.size)
            reader.read_bytes(data)
            return bytes(data)
        finally:
            reader.close()
            stream.close()
