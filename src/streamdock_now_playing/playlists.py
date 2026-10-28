"""Three-column playlist preview with a one-item sliding viewport."""
import asyncio,time
from collections import OrderedDict
from .desktop import panel
from .queue_artwork import QueueArtwork

class PlaylistBrowser:
    def __init__(self,client):
        self.client=client;self.page=0;self.total=None;self.items=[];self.loaded=None
        self.cache=OrderedDict();self.task=None;self.retry_at=0;self.message='Loading…'
        self.artwork=QueueArtwork();self.artwork_task=None;self.cover_key=None
    def move(self,delta):
        if self.total is None:return
        target=max(0,min(max(0,self.total-3),self.page+delta))
        if target!=self.page:self.page=target;self.loaded=None;self.items=[];self.message='Loading…'
    def item(self,index):
        data=self.cache.get(index//6*6)
        if data is None:return None
        items=data.get('items') or []
        return items[index%6] if index%6<len(items) else {}
    def request(self):
        if self.loaded==self.page:return
        end=min(self.page+3,self.total) if self.total is not None else self.page+3
        missing=next((i for i in range(self.page,end) if self.item(i) is None),None)
        if self.total is not None and missing is None:
            self.items=[self.item(i) or {} for i in range(self.page,end)];self.loaded=self.page
            self.message='' if self.items else 'No playlists';self.request_covers();return
        if self.task and not self.task.done() or time.monotonic()<self.retry_at:return
        offset=(missing or self.page)//6*6
        self.task=asyncio.create_task(self.refresh(offset))
    async def refresh(self,offset):
        try:
            data=await asyncio.to_thread(self.client.playlists,offset)
            data['items']=[i if isinstance(i,dict) else {} for i in data.get('items',[])]
            self.cache[offset]=data;self.total=int(data.get('total') or 0)
            while len(self.cache)>32:self.cache.popitem(last=False)
            self.page=max(0,min(self.page,max(0,self.total-3)))
            end=min(self.page+3,self.total)
            if all(self.item(i) is not None for i in range(self.page,end)):
                self.items=[self.item(i) or {} for i in range(self.page,end)];self.loaded=self.page
                self.message='' if self.items else 'No playlists';self.request_covers()
        except asyncio.CancelledError:raise
        except Exception as error:
            self.message='Reconnect Spotify' if 'permission' in str(error).lower() else 'Spotify unavailable'
            self.retry_at=time.monotonic()+max(30,getattr(error,'retry_after',0))
    def request_covers(self):
        key=tuple(id(i) for i in self.items)
        if key==self.cover_key:return
        self.cover_key=key
        if self.artwork_task and not self.artwork_task.done():self.artwork_task.cancel()
        self.artwork_task=asyncio.create_task(self.load_covers(list(self.items)))
    async def load_covers(self,items):
        async def load(item):
            images=item.get('images') or []
            url=next((i.get('url') for i in images if isinstance(i,dict) and i.get('url')),'')
            image=await asyncio.to_thread(self.artwork.load,url)
            if image:item['cover']=image
        await asyncio.gather(*(load(i) for i in items))
    def selected(self,cell):
        if not 0<=cell<6:return None
        column=cell%3
        if self.loaded!=self.page or column>=len(self.items):return None
        return self.items[column].get('uri')
    def render(self):
        top=[];bottom=[]
        for column in range(3):
            item=self.items[column] if self.loaded==self.page and column<len(self.items) else None
            if item:
                text=str(item.get('name') or 'Unavailable');lines=[]
                while text and len(lines)<3:
                    cut=min(9,len(text));lines.append(text[:cut]);text=text[cut:]
                if text:lines[-1]=lines[-1][:-1]+'…'
                entries=[(line,23,6+i*27,'white') for i,line in enumerate(lines)]
                entries.append((self.message or f'{self.page+column+1}/{self.total}',15,105,'#b9d8ef'))
            else:entries=[(self.message if column==0 else '',18,38,'white')]
            top.append(panel(entries))
            if item and item.get('liked'):item['cover']=panel([('♥',78,14,'#c9a5ff')])
            bottom.append(item.get('cover') if item and item.get('cover') else panel([('NO COVER' if item else '',18,48,'#b9d8ef')]))
        return top+bottom
    async def close(self):
        tasks=[t for t in (self.task,self.artwork_task) if t and not t.done()]
        for task in tasks:task.cancel()
        if tasks:await asyncio.gather(*tasks,return_exceptions=True)
