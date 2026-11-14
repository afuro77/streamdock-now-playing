"""Application volume on the default Windows output, separate from master volume."""
from dataclasses import dataclass
import logging
import time
from psutil import Error as ProcessError
try:
    from _ctypes import COMError
except ImportError:
    COMError = OSError


@dataclass(frozen=True)
class AppLevel:
    name: str
    percent: int
    muted: bool
    mixed: bool


class AppMixer:
    def __init__(self, enumerate_sessions=None, clock=time.monotonic):
        self.enumerate_sessions = enumerate_sessions
        self.clock = clock
        self.apps = []
        self.selected = None
        self.updated = float('-inf')
        self.error = False

    def _groups(self):
        enumerate_sessions = self.enumerate_sessions
        if enumerate_sessions is None:
            from pycaw.pycaw import AudioUtilities
            enumerate_sessions = AudioUtilities.GetAllSessions
        groups = {}
        for session in enumerate_sessions():
            try:
                process = session.Process
                if process is None or session.State == 2:
                    continue
                name = process.name().lower()
                volume = session.SimpleAudioVolume
                entry = (volume, volume.GetMasterVolume(), bool(volume.GetMute()))
                groups.setdefault(name, []).append(entry)
            except (OSError, RuntimeError, ProcessError, COMError) as exc:
                logging.debug('Skipping unavailable audio session: %s', type(exc).__name__)
        return groups

    def refresh(self):
        self.updated = self.clock()
        try:
            self._update(self._groups())
            self.error = False
        except Exception:
            logging.exception('Application mixer refresh')
            self.apps = []
            self.error = True

    def _update(self, groups):
        self.apps = []
        for name, entries in sorted(groups.items()):
            levels = {(round(level * 100), mute) for _, level, mute in entries}
            percent = max(level for level, _ in levels)
            self.apps.append(AppLevel(name, percent, all(m for _, m in levels), len(levels) > 1))
    def visible(self):
        index = next((i for i, app in enumerate(self.apps) if app.name == self.selected), 0)
        start = index // 6 * 6
        return self.apps[start:start + 6]

    def select(self, cell):
        visible = self.visible()
        if 0 <= cell < len(visible):
            self.selected = visible[cell].name

    def move(self, steps):
        if steps and self.apps:
            index = next((i for i, app in enumerate(self.apps) if app.name == self.selected), -1 if steps > 0 else len(self.apps))
            self.selected = self.apps[max(0, min(len(self.apps) - 1, index + steps))].name

    def adjust(self, amount, *, app=None):
        target = self.selected if app is None else app
        if target is None or amount == 0:
            return
        try:
            entries = self._groups().get(target, [])
            mute = not all(muted for _, _, muted in entries)
            for volume, level, _ in entries:
                if amount is None:
                    volume.SetMute(mute, None)
                else:
                    volume.SetMasterVolume(max(0., min(1., level + amount / 100)), None)
        except Exception:
            logging.exception('Application mixer adjustment')
            self.error = True
            self.apps = []
            self.updated = self.clock()
        else:
            self.refresh()
