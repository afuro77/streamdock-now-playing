import tempfile
import unittest
from unittest.mock import patch
from streamdock_now_playing.streamdock import Plugin
from test_behavior import FakeMedia

class TimelineTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.p=Plugin(provider=FakeMedia(),data_dir=self.directory.name,config={})
        self.s={'key':'song','source':'player','position':10,'duration':100,'playing':True}
    def update(self,s,now):
        with patch('streamdock_now_playing.streamdock.time.monotonic',return_value=now):
            self.p.update_timeline(s);self.p.snapshot=s
    def position(self,now):
        with patch('streamdock_now_playing.streamdock.time.monotonic',return_value=now):
            return self.p.display_snapshot()['position']
    def test_stale_reports_do_not_freeze_seconds(self):
        self.update(self.s,0);self.update(self.s,2)
        self.assertEqual(self.position(3),13)
        self.assertEqual(self.p.snapshot['position'],10)
    def test_pause_and_seek_resync(self):
        self.update(self.s,0);self.update({**self.s,'position':13,'playing':False},3)
        self.assertEqual(self.position(9),13)
        self.update({**self.s,'position':50},10)
        self.assertEqual(self.position(11),51)
    def test_track_change_and_duration_clamp(self):
        self.update(self.s,0);self.update({**self.s,'key':'other','position':0},5)
        self.assertEqual(self.position(6),1)
        self.assertEqual(self.position(200),100)
