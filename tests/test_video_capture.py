import io
import json
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from PIL import Image
from streamdock_now_playing.video_capture import VideoCapture
from streamdock_now_playing.youtube import YouTubeMode


def jpeg(size=(384,256),color='red'):
    data=io.BytesIO();Image.new('RGB',size,color).save(data,format='JPEG');return data.getvalue()


class FrameTests(unittest.TestCase):
    def test_measurement_samples_use_receiver_clock_and_restart_identity(self):
        now=[20];receiver=VideoCapture(lambda:True,clock=lambda:now[0])
        self.assertFalse(receiver.diagnostics()['fresh'])
        receiver.accept(jpeg(),'extension',60);first=receiver.diagnostics()
        now[0]=21;receiver.accept(jpeg(),'extension',60);last=receiver.diagnostics()
        self.assertEqual(last['sample_time']-first['sample_time'],1)
        self.assertEqual(last['sources']['extension']-first['sources']['extension'],1)
        self.assertTrue(last['enabled']);self.assertTrue(last['fresh'])
        self.assertEqual(first['instance'],last['instance'])
        self.assertNotEqual(first['instance'],VideoCapture(lambda:True).diagnostics()['instance'])
        now[0]=24;self.assertFalse(receiver.diagnostics()['fresh'])

    def test_frame_rate_metadata_validated_and_only_applied_to_accepted_extension(self):
        receiver=VideoCapture(lambda:True)
        for fps in (4,6,8,10,12,15,20,24,30,40,45,50,60,75,90,120):
            self.assertTrue(receiver.accept(jpeg(),'extension',fps))
            self.assertEqual(receiver.diagnostics()['target_fps'],fps)
        for fps in (0,61,121,-1,True,'60',60.0):
            with self.assertRaises(ValueError):receiver.accept(jpeg(),'extension',fps)
        receiver.accept(jpeg(),'share',4);self.assertEqual(receiver.target_fps,120)
        receiver.enabled=lambda:False
        self.assertFalse(receiver.accept(jpeg(),'extension',4));self.assertEqual(receiver.target_fps,120)

    def setUp(self):
        self.enabled=True;self.now=10
        self.receiver=VideoCapture(lambda:self.enabled,clock=lambda:self.now)

    def test_latest_frame_replaces_instead_of_queueing(self):
        self.assertTrue(self.receiver.accept(jpeg()))
        first=self.receiver.latest();self.assertEqual(len(first),6)
        self.receiver.accept(jpeg(color='blue'))
        self.assertNotEqual(first,self.receiver.latest());self.assertEqual(self.receiver.count,2)

    def test_stale_disabled_and_clear_fall_back(self):
        self.receiver.accept(jpeg());self.now+=3;self.assertIsNone(self.receiver.latest())
        self.now=10;self.enabled=False
        self.assertFalse(self.receiver.accept(jpeg()));self.assertIsNone(self.receiver.latest())
        self.enabled=True;self.receiver.clear();self.assertIsNone(self.receiver.latest())

    def test_source_attribution_and_diagnostic_errors(self):
        self.receiver.accept(jpeg(),'extension');self.receiver.accept(jpeg(),'share')
        self.receiver.diagnose('read-error');self.receiver.diagnose('not-selected')
        state=self.receiver.diagnostics()
        self.assertEqual(state['sources'],{'extension':1,'share':1})
        self.assertEqual(state['last_error'],'read-error')
        with self.assertRaises(ValueError):self.receiver.diagnose('arbitrary personal information')
        with self.assertRaises(ValueError):self.receiver.accept(jpeg(),'unknown')

    def test_reject_bad_frames(self):
        for data in (b'not an image',jpeg((1920,1080)),b'x'*200001):
            with self.assertRaises((ValueError,OSError)):self.receiver.accept(data)

    def test_only_expanded_youtube_uses_video(self):
        mode=YouTubeMode();mode.capture=self.receiver
        self.receiver.enabled=lambda:mode.view=='artwork'
        mode.view='artwork';self.receiver.accept(jpeg())
        self.assertEqual(mode.frame(),self.receiver.latest())
        mode.home();self.assertIsNone(self.receiver.latest())
        self.assertEqual(len(mode.frame()),6)


class ReceiverTests(unittest.TestCase):
    def test_authenticated_loopback_protocol(self):
        receiver=VideoCapture(lambda:True,port=0)
        url=receiver.start();base=url.split('#')[0]
        try:
            self.assertEqual(receiver.server.server_address[0],'127.0.0.1')
            with urlopen(base) as r:self.assertIn(b'getDisplayMedia',r.read())
            with self.assertRaises(HTTPError) as error:urlopen(base+'state')
            self.assertEqual(error.exception.code,403)
            headers={'X-Capture-Token':receiver.token}
            with urlopen(Request(base+'state',headers=headers)) as r:self.assertTrue(json.load(r)['enabled'])
            with urlopen(Request(base+'diagnostic',data=b'{"stage":"no-video"}',headers=headers)) as r:self.assertEqual(r.status,204)
            with urlopen(Request(base+'diagnostics',headers=headers)) as r:self.assertEqual(json.load(r)['extension_stage'],'no-video')
            with urlopen(Request(base+'frame',data=jpeg(),headers=headers)) as r:self.assertEqual(r.status,204)
            with urlopen(Request(base+'frame',data=jpeg(),headers={**headers,'X-Frame-Source':'extension','X-Target-Fps':'24'})) as r:self.assertEqual(r.status,204)
            self.assertEqual(receiver.target_fps,24)
            with urlopen(Request(base+'frame',data=jpeg(),headers={**headers,'X-Frame-Source':'extension','X-Target-Fps':'60'})) as r:self.assertEqual(r.status,204)
            self.assertEqual(receiver.target_fps,60)
            with self.assertRaises(HTTPError) as invalid:urlopen(Request(base+'frame',data=jpeg(),headers={**headers,'X-Target-Fps':'300'}))
            self.assertEqual(invalid.exception.code,400)
            self.assertIsNotNone(receiver.latest())
            with urlopen(Request(base+'stop',data=b'',headers=headers)) as r:self.assertEqual(r.status,204)
            self.assertIsNone(receiver.latest())
        finally:receiver.close()

    def test_reject_wrong_host_and_oversized_payload(self):
        receiver=VideoCapture(lambda:True,port=0);base=receiver.start().split('#')[0]
        try:
            for headers,data,code in [({'Host':'evil.example'},None,403),({'X-Capture-Token':receiver.token},b'x'*200001,413)]:
                with self.assertRaises(HTTPError) as error:urlopen(Request(base+('frame' if data else ''),data=data,headers=headers))
                self.assertEqual(error.exception.code,code)
        finally:receiver.close()
