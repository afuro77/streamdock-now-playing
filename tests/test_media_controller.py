import unittest
from datetime import timedelta
from types import SimpleNamespace as NS

from streamdock_now_playing.audio import AudioSessions
from streamdock_now_playing.controller import MediaController
from streamdock_now_playing.media import GSMTCMedia


class Session:
    source_app_user_model_id = 'Example.Player!App'

    def __init__(self):
        self.calls = []
        self.controls = NS(is_next_enabled=True, is_previous_enabled=True,
                           is_playback_position_enabled=True, is_shuffle_enabled=True)

    def get_playback_info(self):
        return NS(controls=self.controls, is_shuffle_active=False, playback_status=4)

    def get_timeline_properties(self):
        return NS(start_time=timedelta(), end_time=timedelta(seconds=60), position=timedelta(seconds=10))

    async def try_get_media_properties_async(self):
        return NS(title='Example', artist='Artist', album_title='Album', thumbnail=None)

    async def try_toggle_play_pause_async(self): self.calls.append(('play',)); return True
    async def try_skip_next_async(self): self.calls.append(('next',)); return True
    async def try_skip_previous_async(self): self.calls.append(('previous',)); return True
    async def try_change_playback_position_async(self, value): self.calls.append(('seek', value)); return True
    async def try_change_shuffle_active_async(self, value): self.calls.append(('shuffle', value)); return True


class MediaTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.session = Session()
        self.manager = NS(get_sessions=lambda: [self.session], get_current_session=lambda: self.session)
        self.provider = GSMTCMedia(manager=self.manager)
        self.controller = MediaController(self.provider, AudioSessions())

    async def test_active_and_preferred_selection(self):
        self.assertIs(await self.provider.refresh(), self.session)
        self.provider.preferred = 'not-running'
        self.assertIsNone(await self.provider.refresh())
        self.provider.fallback = True
        self.assertIs(await self.provider.refresh(), self.session)

    async def test_snapshot_and_no_artwork(self):
        snap = await self.provider.snapshot()
        self.assertEqual(snap['key'], ('Example.Player!App', 'Example', 'Artist', 'Album'))
        self.assertTrue(snap['playing'])
        self.assertEqual(snap['duration'], 60)
        self.assertIsNone(await self.provider.artwork(snap))

    async def test_missing_session(self):
        self.manager.get_sessions = lambda: []
        self.manager.get_current_session = lambda: None
        self.assertIsNone((await self.provider.snapshot())['key'])
        self.assertEqual(await self.controller.command('play'), 'Media unavailable')

    async def test_controls_and_seek_clamp(self):
        for command in ('play', 'next', 'previous', 'shuffle'):
            await self.controller.command(command)
        await self.controller.command('seek', 1000)
        await self.controller.command('seek', -1000)
        self.assertEqual(self.session.calls, [('play',), ('next',), ('previous',), ('shuffle', True), ('seek', 600000000), ('seek', 0)])

    async def test_unsupported_controls_are_not_called(self):
        for name in vars(self.session.controls): setattr(self.session.controls, name, False)
        for command in ('next', 'previous', 'seek', 'shuffle'):
            await self.controller.command(command)
        self.assertEqual(self.session.calls, [])
        self.assertEqual(await self.controller.command('save'), 'Unsupported')

    async def test_rejected_command_not_reported_as_success(self):
        async def rejected(): return False
        self.session.try_toggle_play_pause_async = rejected
        self.assertEqual(await self.controller.command('play'), 'play rejected')


class AudioTests(unittest.TestCase):
    def test_explicit_mapping_and_packaged_source(self):
        audio = AudioSessions([{'source_contains': 'Example.Player!', 'process_name': 'example.exe'}])
        self.assertEqual(audio.process_for('Example.Player!App'), 'example.exe')
        self.assertEqual(audio.process_for('player.exe'), 'player.exe')
        self.assertEqual(audio.process_for('browser'), 'browser.exe')
        self.assertIsNone(audio.process_for('Other.Package!App'))

    def test_adjust_only_matching_sessions_and_clamp(self):
        changed = []
        def session(name, value):
            return NS(Process=NS(name=lambda: name), SimpleAudioVolume=NS(
                GetMasterVolume=lambda: value, SetMasterVolume=lambda value, _: changed.append((name, value))))
        sessions = [session('player.exe', .99), session('unrelated.exe', .5)]
        audio = AudioSessions(enumerate_sessions=lambda: sessions)
        self.assertEqual(audio.adjust('player.exe', 10), 'Volume 100%')
        self.assertEqual(changed, [('player.exe', 1)])
        changed.clear()
        self.assertEqual(audio.adjust('player.exe', -200), 'Volume 0%')
        self.assertEqual(changed, [('player.exe', 0)])

    def test_no_mapping_never_enumerates_audio(self):
        def forbidden(): raise AssertionError('Must not touch audio')
        audio = AudioSessions(enumerate_sessions=forbidden)
        self.assertEqual(audio.adjust('Other.Package!App', 2), 'Configure app audio mapping')
