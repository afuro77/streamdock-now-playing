"""Explicit GSMTC-source to Windows Audio Session mapping; never master audio."""
import re


class AudioSessions:
    def __init__(self, mappings=(), enumerate_sessions=None):
        self.mappings = list(mappings)
        self.enumerate_sessions = enumerate_sessions

    def process_for(self, source):
        for mapping in self.mappings:
            if mapping['source_contains'].lower() in source.lower():
                return mapping['process_name'].lower()
        # Packaged AUMIDs cannot reliably be resolved to process names.
        if re.fullmatch(r'[\w.-]+', source, flags=re.ASCII):
            return source.lower() if source.lower().endswith('.exe') else source.lower() + '.exe'
        return None

    def adjust(self, source, amount):
        target_process = self.process_for(source)
        if target_process is None:
            return 'Configure app audio mapping'
        enumerate_sessions = self.enumerate_sessions
        if enumerate_sessions is None:
            from pycaw.pycaw import AudioUtilities
            enumerate_sessions = AudioUtilities.GetAllSessions
        found = []
        # Refresh handles on every adjustment to survive process restarts.
        for session in enumerate_sessions():
            if session.Process and session.Process.name().lower() == target_process:
                volume = session.SimpleAudioVolume
                target = max(0, min(1, volume.GetMasterVolume() + amount / 100))
                volume.SetMasterVolume(target, None)
                found.append(round(target * 100))
        return f'Volume {found[0]}%' if found else 'App audio unavailable'
