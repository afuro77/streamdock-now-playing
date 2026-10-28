"""Optional Spotify enrichment; never owns navigation or draws to the device."""
import asyncio,io,time
from collections import OrderedDict
from urllib.parse import urlsplit
from urllib.request import urlopen
from PIL import Image
from .spotify import SpotifyError


def load_artist_image(url):
    parsed=urlsplit(url)
    if parsed.scheme!='https' or not (parsed.hostname or '').endswith('.scdn.co'):return None
    try:
        with urlopen(url,timeout=5) as response:
            final=urlsplit(response.geturl())
            if final.scheme!='https' or not (final.hostname or '').endswith('.scdn.co'):return None
            data=response.read(4*1024*1024+1)
        if len(data)>4*1024*1024:return None
        with Image.open(io.BytesIO(data)) as image:
            if image.width*image.height>16_000_000:return None
            image.verify()
        return data
    except Exception:return None


def identity(snapshot):return tuple(str(snapshot.get(k) or '') for k in ('source','title','artist','album'))


def matches(snapshot,item):
    title=' '.join(str(snapshot.get('title') or '').casefold().split())
    name=' '.join(str(item.get('name') or '').casefold().split())
    if not title or title!=name:return False
    duration=snapshot.get('duration') or 0
    return not duration or abs(duration-(item.get('duration_ms') or 0)/1000)<4


class TrackDetails:
    def __init__(self,client,image_loader=load_artist_image):
        self.client=client;self.image_loader=image_loader
        self.tracks=OrderedDict();self.artists=OrderedDict();self.images=OrderedDict()
        self.key=None;self.data=None;self.task=None;self.retry_at=0;self.message='Loading…';self.updated=0
    @staticmethod
    def put(cache,key,value,limit):
        cache[key]=value;cache.move_to_end(key)
        while len(cache)>limit:cache.popitem(last=False)
    def request(self,snapshot):
        key=identity(snapshot)
        if key!=self.key:
            self.key=key;self.data=None;self.message='Loading…';self.retry_at=0
        if not self.client.settings.get('enabled') or 'spotify' not in snapshot.get('source','').casefold():
            self.message='Spotify API unavailable';return
        if (self.data is not None and time.monotonic()-self.updated<15) or time.monotonic()<self.retry_at:return
        if self.task and not self.task.done():return
        self.task=asyncio.create_task(self.refresh(dict(snapshot),key))
    async def refresh(self,snapshot,key):
        try:
            result=await asyncio.to_thread(self.fetch,snapshot)
            if key==self.key:
                self.data=result;self.updated=time.monotonic();self.message='' if result else 'Waiting for matching track'
                if result is None:self.retry_at=time.monotonic()+5
        except asyncio.CancelledError:raise
        except Exception as error:
            if key==self.key:self.message='Spotify info unavailable'
            self.retry_at=time.monotonic()+max(30,getattr(error,'retry_after',0))
    def fetch(self,snapshot):
        playback=self.client.playback() or {};item=playback.get('item') or {}
        if item.get('type')!='track' or not item.get('id') or not matches(snapshot,item):return None
        tid=item['id']
        if tid not in self.tracks:self.put(self.tracks,tid,self.client.request('GET','/tracks/'+tid),64)
        track=self.tracks[tid];self.tracks.move_to_end(tid)
        if not isinstance(track,dict) or not matches(snapshot,track):return None
        people=[]
        for artist in track.get('artists') or []:
            aid=artist.get('id');person=dict(artist);picture=None
            if aid:
                try:
                    if aid not in self.artists:self.put(self.artists,aid,self.client.request('GET','/artists/'+aid),32)
                    details=self.artists[aid] or {};self.artists.move_to_end(aid)
                    person.update(details)
                    if aid not in self.images:
                        images=details.get('images') or []
                        url=next((x.get('url') for x in images if x.get('url')),None)
                        if url:
                            picture=self.image_loader(url)
                            if picture:self.put(self.images,aid,picture,24)
                    else:picture=self.images[aid];self.images.move_to_end(aid)
                except SpotifyError as error:
                    if error.status==429:raise
                except Exception:pass
            people.append({'id':aid,'name':person.get('name') or artist.get('name',''),'image':picture})
        return {'id':tid,'track':track,'artists':people}
    async def close(self):
        if self.task and not self.task.done():
            self.task.cancel();await asyncio.gather(self.task,return_exceptions=True)
