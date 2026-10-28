"""Explicit Chrome launch; no shell, system-default browser or media commands."""
import os
import subprocess
import time
from pathlib import Path


def open_youtube():
    candidates=[Path(os.environ.get(name,''))/'Google/Chrome/Application/chrome.exe'
                for name in ('PROGRAMFILES','PROGRAMFILES(X86)','LOCALAPPDATA') if os.environ.get(name)]
    executable=next((p for p in candidates if p.is_file()),None)
    if executable is None:raise FileNotFoundError('Chrome installation not found')
    subprocess.Popen([str(executable),'https://www.youtube.com/'],shell=False)


def chrome_running():
    import psutil
    for process in psutil.process_iter(['name']):
        if (process.info.get('name') or '').lower()=='chrome.exe':return True
    return False


class BrowserLauncher:
    def __init__(self,enabled=False,opener=None,running=None,clock=time.monotonic):
        self.enabled=enabled;self.opened=False;self.opener=opener or open_youtube
        self.running=running or chrome_running;self.clock=clock;self.last_open=None

    def enter(self):
        if not self.enabled:return False
        if self.opened and ((self.last_open is not None and self.clock()-self.last_open<5) or self.running()):return False
        self.opener()
        self.opened=True;self.last_open=self.clock()
        return True
