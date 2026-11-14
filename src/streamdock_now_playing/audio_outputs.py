"""Choose active Windows playback endpoints; never change communications or inputs."""
import logging
import time


def _devices():
    from pycaw.pycaw import AudioUtilities
    from pycaw.constants import DEVICE_STATE, EDataFlow, ERole
    devices = AudioUtilities.GetAllDevices(EDataFlow.eRender.value, DEVICE_STATE.ACTIVE.value)
    enumerator = AudioUtilities.GetDeviceEnumerator()
    active = enumerator.GetDefaultAudioEndpoint(EDataFlow.eRender.value, ERole.eMultimedia.value)
    return [(d.id, d.FriendlyName or 'Audio output') for d in devices], active.GetId()


def _switch(device_id):
    from pycaw.pycaw import AudioUtilities
    from pycaw.constants import ERole
    AudioUtilities.SetDefaultDevice(device_id, [ERole.eConsole, ERole.eMultimedia])


class AudioOutputs:
    def __init__(self, devices=_devices, switch=_switch, clock=time.monotonic):
        self.devices, self.switch, self.clock = devices, switch, clock
        self.items = []
        self.selected = self.active = None
        self.updated = float('-inf')
        self.message = ''

    def refresh(self, initial=False):
        self.updated = self.clock()
        try:
            items, self.active = self.devices()
            self.items = sorted(items, key=lambda item: (item[1].casefold(), item[0]))
            if initial:
                self.selected = self.active if self.active else (self.items[0][0] if self.items else None)
        except Exception:
            logging.exception('Read Windows audio outputs')
            self.items = []
            self.message = '出力取得エラー'

    def _index(self):
        return next((i for i, item in enumerate(self.items) if item[0] == self.selected), 0)

    def visible(self):
        start = self._index() // 6 * 6
        return self.items[start:start + 6]

    def select(self, cell):
        items = self.visible()
        if 0 <= cell < len(items):
            self.selected = items[cell][0]
            self.message = ''

    def move(self, ticks):
        if ticks and self.items:
            self.selected = self.items[max(0, min(len(self.items)-1, self._index()+ticks))][0]
            self.message = ''

    def apply(self):
        self.message = ''
        self.refresh()
        if self.message:
            return
        if self.selected not in {key for key, _ in self.items}:
            self.message = '選び直してください'
            return
        try:
            self.switch(self.selected)
            self.refresh()
            if not self.message:
                self.message = '切替完了' if self.active == self.selected else '切替を確認できません'
        except Exception:
            logging.exception('Switch Windows audio output')
            self.message = '切替エラー'
