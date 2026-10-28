"""Bounded in-memory queue artwork cache; no API credentials sent to image URLs."""
from collections import OrderedDict
import io
import threading
from urllib.parse import urlsplit
from urllib.request import urlopen
from PIL import Image, ImageOps
from .renderer import encode


def trusted_image_host(host):
    return (host or '').endswith('.scdn.co') or host in {'pickasso.spotifycdn.com','image-cdn-ak.spotifycdn.com','image-cdn-fa.spotifycdn.com'}


class QueueArtwork:
    def __init__(self,allowed_host=None):self.cache=OrderedDict();self.lock=threading.Lock();self.allowed_host=allowed_host or trusted_image_host

    def load(self,url):
        if not url:return None
        parsed=urlsplit(url)
        if parsed.scheme!='https' or not self.allowed_host(parsed.hostname):return None
        with self.lock:
            if url in self.cache:
                self.cache.move_to_end(url);return self.cache[url]
        try:
            with urlopen(url,timeout=4) as response:
                if not self.allowed_host(urlsplit(response.geturl()).hostname) or urlsplit(response.geturl()).scheme!='https':return None
                data=response.read(2*1024*1024+1)
            if len(data)>2*1024*1024:return None
            with Image.open(io.BytesIO(data)) as source:
                if source.width*source.height>16_000_000:return None
                picture=ImageOps.contain(source.convert('RGB'),(128,128),method=Image.Resampling.LANCZOS)
            canvas=Image.new('RGB',(128,128),'#10261f')
            canvas.paste(picture,((128-picture.width)//2,(128-picture.height)//2))
            result=encode(canvas)
            with self.lock:
                self.cache[url]=result;self.cache.move_to_end(url)
                while len(self.cache)>32:self.cache.popitem(last=False)
            return result
        except Exception:return None
