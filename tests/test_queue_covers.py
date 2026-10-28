import asyncio
import io
import time
import unittest
from unittest.mock import patch
from PIL import Image
from streamdock_now_playing.queue_artwork import QueueArtwork
from streamdock_now_playing.queue_renderer import QueueRenderer
from streamdock_now_playing.spotify import QueueState
from streamdock_now_playing.renderer import encode
from test_layout_v11 import decode


class QueueCoverTests(unittest.TestCase):
    def test_compact_youtube_card_fits_more_title_without_changing_cover(self):
        cover=encode(Image.new('RGB',(128,128),'red'))
        item={'title':'長い動画タイトルの表示内容をこれまでより多く読めるように余白と行数を調整する','artist':'Example channel','cover':cover}
        displayed=[]
        for renderer in (QueueRenderer(),QueueRenderer(label='VIDEO',compact=True)):
            with patch('streamdock_now_playing.queue_renderer.ImageDraw.Draw') as draw:
                images=renderer.render([item],'')
            displayed.append(''.join(call.args[1] for call in draw.return_value.text.call_args_list if call.kwargs.get('fill')=='white'))
            self.assertEqual(images[3],cover)
        self.assertGreater(len(displayed[1]),len(displayed[0]))

    def test_compact_renderer_cache_and_empty_cards_stay_renderable(self):
        renderer=QueueRenderer(label='VIDEO',compact=True)
        images=renderer.render([],'Loading YouTube',20)
        self.assertEqual(len(images),6)
        self.assertIs(renderer.render([],'Loading YouTube',20),images)
        for image in images:self.assertEqual(decode(image).size,(128,128))

    def test_bottom_row_matches_each_column_cover(self):
        covers=[encode(Image.new('RGB',(128,128),color)) for color in ('red','green','blue')]
        images=QueueRenderer().render([{'title':'Song '+str(i),'artist':'Artist','cover':cover} for i,cover in enumerate(covers)],'')
        self.assertEqual(images[3:],covers)
        self.assertTrue(all(images[i]!=covers[i] for i in range(3)))

    def test_missing_cover_keeps_six_renderable_tiles(self):
        images=QueueRenderer().render([{'title':'Song','artist':'Artist'}],'')
        self.assertEqual(len(images),6)
        for image in images:self.assertEqual(decode(image).size,(128,128))

    def test_cover_loader_contains_full_image_and_caches(self):
        buffer=io.BytesIO();Image.new('RGB',(256,128),'red').save(buffer,'PNG')
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def geturl(self):return 'https://i.scdn.co/image/example'
            def read(self,limit):return buffer.getvalue()
        loader=QueueArtwork()
        with patch('streamdock_now_playing.queue_artwork.urlopen',return_value=Response()) as request:
            cover=loader.load('https://i.scdn.co/image/example')
            self.assertEqual(cover,loader.load('https://i.scdn.co/image/example'))
            self.assertEqual(request.call_count,1)
        image=decode(cover)
        self.assertEqual(image.getpixel((64,64)),(255,0,0))
        self.assertEqual(image.getpixel((64,0)),(16,38,31))

    def test_untrusted_or_missing_image_urls_make_no_request(self):
        loader=QueueArtwork()
        with patch('streamdock_now_playing.queue_artwork.urlopen') as request:
            for url in ('','http://i.scdn.co/image/x','https://example.org/image/x'):
                self.assertIsNone(loader.load(url))
            request.assert_not_called()


class AsyncQueueCoverTests(unittest.IsolatedAsyncioTestCase):
    async def test_queue_metadata_ready_before_slow_covers(self):
        class Client:
            def queue(self):return [{'title':'Song','uri':'track:1','image_url':'https://i.scdn.co/image/test'}]
        state=QueueState(Client())
        def slow(url):time.sleep(.15);return 'test-cover'
        state.artwork.load=slow
        await state.refresh()
        self.assertEqual(state.items[0]['title'],'Song')
        self.assertNotIn('cover',state.items[0])
        await state.artwork_task
        self.assertEqual(state.items[0]['cover'],'test-cover')
