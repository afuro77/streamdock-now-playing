import asyncio
import tempfile
import unittest
from unittest.mock import Mock, patch
from streamdock_now_playing.desktop import DesktopHome, WeatherWidget, AppLauncherAction
from streamdock_now_playing.laundry import assess_laundry as evaluate
from datetime import datetime, timedelta

def assess_laundry(data):return evaluate(data,now=datetime(2026,10,19,10))
from streamdock_now_playing.streamdock import Plugin
from test_behavior import FakeMedia, FakeWS


def forecast():
    return {'current':{'temperature_2m':22,'weather_code':0,'is_day':1},'hourly':{'time':[(datetime(2026,10,19)+timedelta(hours=i)).isoformat() for i in range(48)],
        'precipitation_probability':[10]*48,'precipitation':[0]*48,
        'relative_humidity_2m':[48]*48,'wind_speed_10m':[11.52]*48,
        'temperature_2m':[22]*48,'sunshine_duration':[3000]*48}}


class LaundryTests(unittest.TestCase):
    def test_good_weather(self):
        result=assess_laundry(forecast());self.assertEqual(result.grade,'◎');self.assertAlmostEqual(result.wind_ms,3.2)
    def test_rain_overrides_good(self):
        d=forecast();d['hourly']['precipitation_probability'][12]=60
        self.assertEqual(assess_laundry(d).grade,'×')
    def test_precipitation_overrides_probability(self):
        d=forecast();d['hourly']['precipitation'][12]=.2
        self.assertEqual(assess_laundry(d).grade,'×')
    def test_wind(self):
        d=forecast();d['hourly']['wind_speed_10m'][12]=40
        self.assertEqual(assess_laundry(d).grade,'×')
    def test_humidity_temperature_night(self):
        for key,value in [('relative_humidity_2m',90),('temperature_2m',5)]:
            d=forecast();d['hourly'][key]=[value]*48;self.assertEqual(assess_laundry(d).grade,'△')
        d=forecast();d['current']['is_day']=0;self.assertEqual(assess_laundry(d).grade,'◎')
    def test_sunshine_affects_grade(self):
        d=forecast();d['hourly']['sunshine_duration']=[0]*48
        self.assertEqual(assess_laundry(d).grade,'○')
    def test_missing_forecast_is_unknown(self):
        self.assertEqual(assess_laundry({}).grade,'?')
        d=forecast();d['hourly']['temperature_2m'][12]=None
        self.assertEqual(assess_laundry(d).grade,'?')


class DesktopTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        clock_patch=patch('streamdock_now_playing.desktop.datetime');fake_clock=clock_patch.start();fake_clock.now.return_value=datetime(2026,10,19,10);self.addCleanup(clock_patch.stop)
        self.p=Plugin(provider=FakeMedia(),data_dir=self.temp.name,config={});self.p.ws=FakeWS()
        for role in ('mode','player','back','volume','tracks','seek'):
            self.p.contexts[role]={'role':role,'settings':{}}
        for i in range(6):self.p.contexts[str(i)]={'role':'tile','settings':{'tile':i}}
    async def press(self,key,event='keyDown',payload=None):
        await self.p.event({'event':event,'context':key,'payload':payload or {}})
    async def test_layout_has_three_information_widgets_and_three_configurable_apps(self):
        home=DesktopHome();self.assertEqual(set(home.widgets),set(range(6)))
        self.assertEqual(len(home.render()),6)
        for cell in (3,4,5):
            self.assertIsInstance(home.widgets[cell],AppLauncherAction)
            self.assertFalse(home.widgets[cell].configured)
    async def test_desktop_never_sends_media_commands(self):
        await self.press('mode')
        for role in ('volume','tracks','seek'):
            await self.press(role,'dialRotate',{'ticks':1});await self.press(role,'dialDown')
        await self.press('player');await self.press('back');await self.press('5')
        self.assertEqual(self.p.provider.calls,[]);self.assertEqual(self.p.modes.active,'desktop')
    async def test_key_up_does_not_toggle(self):
        await self.press('mode');await self.press('mode','keyUp')
        self.assertEqual(self.p.modes.active,'desktop')
    async def test_spotify_completion_cannot_replace_desktop(self):
        await self.press('mode');await self.p.render();before=list(self.p.images)
        self.p.view_mode='queue';self.p.nav_feedback='RETURNED';self.p.nav_feedback_until=1e20
        self.p.overlay='VOL 42%';self.p.until=1e20
        self.p.snapshot={'title':'Changed track'}
        await self.p.volume_feedback(42);await self.p.render()
        self.assertEqual(self.p.images,before)
        await self.press('mode');self.assertEqual(self.p.view_mode,'normal')
    async def test_actual_queue_task_completes_in_desktop(self):
        entered=asyncio.Event();release=asyncio.Event()
        async def select(*args):entered.set();await release.wait()
        with patch('streamdock_now_playing.streamdock.QueueNavigator.select',side_effect=select):
            task=asyncio.create_task(self.p.skip_queue(1,'spotify:track:x'))
            await entered.wait();await self.press('mode');before=list(self.p.images)
            release.set();await task
        self.assertEqual(self.p.modes.active,'desktop');self.assertEqual(self.p.images,before)
    async def test_weather_failure_and_retry(self):
        w=WeatherWidget({'latitude':35.72,'longitude':139.93},fetcher=Mock(side_effect=OSError()))
        await w.refresh();self.assertTrue(w.failed);self.assertIsNone(w.data)
        w.fetcher=lambda config:forecast();await w.refresh()
        self.assertFalse(w.failed);self.assertIsNotNone(w.data);self.assertTrue(w.render().startswith('data:'))
    async def test_weather_request_nonblocking(self):
        w=WeatherWidget({'latitude':35,'longitude':139},fetcher=lambda config:forecast())
        w.request();first=w.task;w.request();self.assertIs(w.task,first)
        await first;await w.close()
    async def test_launcher_opens_only_on_press(self):
        opener=Mock();widget=AppLauncherAction({'target':'steam://open/main'},opener)
        widget.render();opener.assert_not_called()
        await widget.press();opener.assert_called_once_with('steam://open/main')
        await widget.press();opener.assert_called_once()
    async def test_invalid_or_duplicate_slots(self):
        for items in ([{'cell':6,'type':'clock'}],[{'cell':0,'type':'unknown'}],
                      [{'cell':0,'type':'clock'},{'cell':0,'type':'clock'}]):
            with self.assertRaises(ValueError):DesktopHome({'items':items})


class LaundryWindowTests(unittest.TestCase):
    def test_evening_uses_tomorrow_not_tonight(self):
        d=forecast();d['hourly']['precipitation_probability'][20]=90
        r=evaluate(d,now=datetime(2026,10,19,20))
        self.assertEqual((r.target,r.grade),('明日','◎'))
    def test_tomorrow_rain_overrides_dry_tonight(self):
        d=forecast();d['hourly']['precipitation_probability'][34]=80
        r=evaluate(d,now=datetime(2026,10,19,19))
        self.assertEqual((r.target,r.grade),('明日','×'))
    def test_morning_ignores_past_rain(self):
        d=forecast();d['hourly']['precipitation_probability'][2]=90
        self.assertEqual(evaluate(d,now=datetime(2026,10,19,10)).grade,'◎')
    def test_cutoff_and_early_morning(self):
        for hour,target in [(0,'今日'),(7,'今日'),(13,'今日'),(14,'明日'),(23,'明日')]:
            self.assertEqual(evaluate(forecast(),now=datetime(2026,10,19,hour)).target,target)
    def test_missing_tomorrow_never_uses_today(self):
        d=forecast();d['hourly']['time']=d['hourly']['time'][:24]
        self.assertEqual(evaluate(d,now=datetime(2026,10,19,20)).grade,'?')

class ClockUpdateTests(unittest.TestCase):
    def test_time_and_blink_refresh(self):
        from streamdock_now_playing.desktop import ClockWidget
        clock=ClockWidget({})
        with patch('streamdock_now_playing.desktop.datetime') as dt:
            dt.now.return_value=datetime(2026,10,19,16,40,0);a=clock.render()
            dt.now.return_value=datetime(2026,10,19,16,40,1);b=clock.render()
            dt.now.return_value=datetime(2026,10,19,16,41,0);c=clock.render()
        self.assertNotEqual(a,b);self.assertNotEqual(a,c)

class ModePersistenceTests(unittest.TestCase):
    def test_restart_restores_selected_mode(self):
        from pathlib import Path
        from streamdock_now_playing.desktop import ModeManager
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'mode.json'
            first=ModeManager(path);self.assertEqual(first.active,'spotify')
            first.toggle();self.assertEqual(ModeManager(path).active,'desktop')
            first.toggle();self.assertEqual(ModeManager(path).active,'spotify')
    def test_invalid_saved_mode_falls_back(self):
        from pathlib import Path
        from streamdock_now_playing.desktop import ModeManager
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'mode.json'
            for content in ('broken','[]','{"active_mode":"other"}'):
                path.write_text(content,encoding='utf-8')
                self.assertEqual(ModeManager(path).active,'spotify')

class DetailViewTests(unittest.IsolatedAsyncioTestCase):
    async def test_weather_and_laundry_open_and_any_key_returns(self):
        home=DesktopHome()
        for cell in (1,2):
            await home.press(cell);self.assertEqual(home.detail,cell)
            self.assertEqual(len(home.render()),6)
            await home.press(3);self.assertIsNone(home.detail)
    async def test_thirty_second_timeout(self):
        home=DesktopHome()
        with patch('streamdock_now_playing.desktop.time.monotonic',return_value=100):await home.press(1)
        with patch('streamdock_now_playing.desktop.time.monotonic',return_value=131):home.render()
        self.assertIsNone(home.detail)
    async def test_real_data_detail_render_and_night_periods(self):
        from streamdock_now_playing.desktop_details import detail_cards
        home=DesktopHome();w=home.widgets[1];w.data=forecast();w.fetched=__import__("time").monotonic()
        w.data['hourly']['weather_code']=[0]*48
        for kind in ('weather','laundry'):
            images=detail_cards(w,kind,datetime(2026,10,19,20))
            self.assertEqual(len(images),6);self.assertTrue(all(i.startswith('data:') for i in images))
    async def test_missing_period_and_error_render_without_media(self):
        from streamdock_now_playing.desktop_details import detail_cards
        home=DesktopHome();w=home.widgets[1]
        for data in (None,forecast()):
            w.data=data;w.failed=True
            self.assertEqual(len(detail_cards(w,'weather')),6)
