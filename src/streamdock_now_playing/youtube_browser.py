"""Bounded YouTube catalog, with optional website channel continuation."""
import asyncio
import re
import secrets
import threading
import time
import unicodedata
from urllib.parse import urlsplit,parse_qs
from .queue_artwork import QueueArtwork
from .queue_renderer import QueueRenderer


def video_url(value):
    if not isinstance(value,str):raise ValueError('Invalid video URL')
    u=urlsplit(value)
    identity=parse_qs(u.query).get('v',[''])[0]
    if u.scheme!='https' or u.netloc!='www.youtube.com' or u.path!='/watch' or not re.fullmatch(r'[\w-]{11}',identity,flags=re.ASCII):raise ValueError('Invalid video URL')
    return 'https://www.youtube.com/watch?v='+identity


def channel_url(value):
    if not isinstance(value,str):raise ValueError('Invalid channel URL')
    u=urlsplit(value)
    match=re.fullmatch(r'(/@[^/\s?#\\]+|/(?:channel|c|user)/[^/\s?#\\]+)(?:/(?:videos|featured|shorts|streams))?/?',u.path)
    if u.scheme!='https' or u.netloc!='www.youtube.com' or not match or len(u.path)>512 or re.search(r'%2f|%5c',u.path,re.I):raise ValueError('Invalid channel URL')
    return 'https://www.youtube.com'+match[1]+'/videos'


class YouTubeBrowser:
    def __init__(self,clock=time.monotonic):
        self.clock=clock;self.lock=threading.Lock();self.active=False
        self.items=[];self.offset=0;self.source_tab=None;self.updated=0
        self.pending=None;self.completed=None;self.message='Open YouTube';self.task=None
        self.covers={};self.loader=QueueArtwork(allowed_host=lambda host:host=='i.ytimg.com')
        self.renderer=QueueRenderer(label='VIDEO',compact=True)
        self.page_url=None;self.expected_page=None
        self.has_more=False;self.catalog_limit=1000;self.empty_pages=0
        self.known_tab=None;self.current_channel=None
        self.foreground_until=None
        self.focus_uri=None;self.focus_pending=False;self.focus_status='none';self.current_position=None;self.channel_reason='none'

    def register(self,data):
        page=data.get('page');tab=data.get('tab')
        if type(tab) is not int or tab<0 or not isinstance(page,str):raise ValueError('Invalid tab')
        u=urlsplit(page)
        if u.scheme!='https' or u.netloc!='www.youtube.com' or len(page)>2048:raise ValueError('Invalid tab page')
        with self.lock:
            old=self.known_tab
            priority=2 if data.get('selected') is True else 1 if data.get('active') is True else 0
            if old is None or old['tab']==tab or self.clock()-old['seen']>15 or priority>old.get('priority',0):
                self.known_tab={'tab':tab,'url':page,'seen':self.clock(),'priority':priority}
            if self.foreground_until is not None:
                if self.clock()>self.foreground_until:self.foreground_until=None
                elif self.known_tab['tab']==tab and not self.pending:
                    self.pending={'id':secrets.token_hex(8),'kind':'focus','url':page,'tab':tab,'time':self.clock()}
                    self.foreground_until=None
                    import logging
                    logging.info('YouTube entry: registered tab; foreground requested')
        return True

    def request_foreground(self,forget=False):
        with self.lock:
            self.foreground_until=self.clock()+15
            if forget:self.known_tab=None;self.current_channel=None

    def register_channel(self,data):
        page=video_url(data.get('page'));channel=channel_url(data.get('channel_url'))
        if type(data.get('tab')) is not int or data['tab']<0:raise ValueError('Invalid tab')
        with self.lock:
            if self.known_tab and data['tab']!=self.known_tab['tab']:return False
            self.current_channel={'tab':data['tab'],'page':page,'url':channel,'title':str(data.get('title') or '')[:240],'seen':self.clock()}
        return True

    def reuse(self):
        with self.lock:
            if not self.known_tab or self.clock()-self.known_tab['seen']>15:return False
            self.pending={'id':secrets.token_hex(8),'kind':'focus','url':self.known_tab['url'],'tab':self.known_tab['tab'],'time':self.clock()}
            return True

    def has_watch_page(self):
        """None means unknown; a fresh Home page overrides stale media metadata."""
        with self.lock:
            if not self.known_tab or self.clock()-self.known_tab['seen']>15:return None
            try:video_url(self.known_tab['url'])
            except ValueError:return False
            return True

    def open_current_channel(self,title):
        self.open()
        with self.lock:
            info=self.current_channel
            normalize=lambda text:' '.join(unicodedata.normalize('NFKC',text).split())
            self.channel_reason='missing' if not info else 'stale' if self.clock()-info['seen']>15 else 'title_mismatch' if info['title'] and normalize(info['title'])!=normalize(title) else 'ready'
            if self.channel_reason!='ready':
                import logging
                logging.warning('YouTube channel unavailable: %s',self.channel_reason)
                self.message='CHANNEL UNAVAILABLE';return False
            self.source_tab=info['tab'];self.expected_page=info['url']
            self.focus_uri=info['page'];self.focus_pending=True;self.focus_status='waiting'
            self.pending={'id':secrets.token_hex(8),'kind':'channel','url':info['url'],'tab':info['tab'],'time':self.clock()}
            self.message='OPEN CHANNEL';return True

    def open(self):
        with self.lock:
            self.active=True;self.pending=None;self.completed=None
            self.source_tab=self.known_tab['tab'] if self.known_tab and self.clock()-self.known_tab['seen']<=15 else None
            self.items=[];self.offset=0;self.message='Loading YouTube'
            self.page_url=None;self.expected_page=None
            self.has_more=False;self.empty_pages=0
            self.focus_uri=None;self.focus_pending=False;self.focus_status='none';self.current_position=None

    def close_view(self):
        with self.lock:self.active=False;self.pending=None;self.completed=None;self.expected_page=None;self.focus_pending=False;self.foreground_until=None

    def diagnostics(self):
        with self.lock:return {'active':self.active,'count':len(self.items),'has_more':self.has_more,'missing_titles':sum(i['title'] in ('YouTube','Title unavailable') for i in self.items),'offset':self.offset,'pending':bool(self.pending),'message':self.message,'initial_focus':self.focus_status,'current_position':self.current_position,'channel_reason':self.channel_reason,'has_channel_info':self.current_channel is not None,'channel_info_age':round(self.clock()-self.current_channel['seen'],1) if self.current_channel else None}

    def state(self):
        with self.lock:
            if self.pending and self.clock()-self.pending['time']>15:
                kind=self.pending.get('kind','play');self.pending=None;self.message='LOAD TIMEOUT' if kind in ('channel','channel-more','list-more') else 'PLAY TIMEOUT'
            return {'browse':self.active,'command':{k:v for k,v in self.pending.items() if k!='time'} if self.pending and (self.active or self.pending.get('kind')=='focus') else None}

    def publish(self,data):
        if not isinstance(data,dict) or type(data.get('tab')) is not int or data['tab']<0 or not isinstance(data.get('items'),list) or len(data['items'])>100:raise ValueError('Invalid catalog')
        items=[];seen=set()
        for item in data['items']:
            if not isinstance(item,dict):continue
            try:uri=video_url(item.get('url'))
            except ValueError:continue
            if uri in seen:continue
            seen.add(uri);image=item.get('image','')
            if not isinstance(image,str) or urlsplit(image).scheme!='https' or urlsplit(image).netloc!='i.ytimg.com':image=''
            try:channel=channel_url(item.get('channel_url'))
            except ValueError:channel=''
            items.append({'uri':uri,'title':str(item.get('title') or '').strip()[:240] or 'Title unavailable','artist':str(item.get('channel') or '')[:120],'image':image[:1024],'channel_url':channel})
        with self.lock:
            if not self.active or (self.source_tab is not None and data['tab']!=self.source_tab):return False
            is_more=False
            page=data.get('page')
            if self.expected_page and page!=self.expected_page:return False
            if data.get('request_id') is not None:
                if not self.pending or data['request_id']!=self.pending['id']:return False
                self.has_more=data.get('has_more') is True
                if self.pending.get('kind') in ('channel-more','list-more'):is_more=True;self.pending=None;self.message=''
            elif not self.expected_page and self.empty_pages<3:
                self.has_more=True
            if self.pending and self.pending.get('kind')=='channel' and page==self.expected_page:
                self.items=[];self.offset=0;self.pending=None;self.message=''
            if isinstance(page,str) and page.startswith('https://www.youtube.com/'):self.page_url=page[:2048]
            if not items:
                if is_more and not self.expected_page:
                    self.empty_pages+=1
                    if self.empty_pages>=3:self.has_more=False
                if not self.items:self.message='No loaded videos'
                return False
            self.source_tab=data['tab'];existing={i['uri'] for i in self.items}
            incoming={i['uri']:i for i in items}
            for current in self.items:
                update=incoming.get(current['uri'])
                if update and update['title'] not in ('YouTube','Title unavailable'):
                    current.update(update)
            added=[i for i in items if i['uri'] not in existing]
            self.items=(self.items+added)[:self.catalog_limit]
            if is_more and not self.expected_page:
                self.empty_pages=0 if added else self.empty_pages+1
                if self.empty_pages>=3:self.has_more=False
            if len(self.items)>=self.catalog_limit:self.has_more=False
            self.updated=self.clock()
            self.offset=min(self.offset,max(0,len(self.items)-3))
            if not self.pending:self.message=''
            if self.focus_pending:
                index=next((i for i,item in enumerate(self.items) if item['uri']==self.focus_uri),None)
                if index is not None:
                    self.offset=min(index,max(0,len(self.items)-3));self.current_position=index+1
                    self.focus_pending=False;self.focus_status='found'
                else:
                    self.focus_status='not_in_loaded_list';self.message='CURRENT NOT LOADED'
        return True

    def move(self,ticks):
        with self.lock:
            if not self.pending or self.pending.get('kind') in ('channel-more','list-more'):
                if ticks:self.focus_pending=False;self.message=''
                self.offset=max(0,min(max(0,len(self.items)-3),self.offset+ticks))
                if ticks>0 and self.active and self.has_more and not self.pending and self.offset>=max(0,len(self.items)-6):
                    self.pending={'id':secrets.token_hex(8),'kind':'channel-more' if self.expected_page else 'list-more','url':self.expected_page or self.page_url,'tab':self.source_tab,'time':self.clock()}
                    self.message='LOADING MORE'

    def select(self,tile):
        with self.lock:
            index=self.offset+tile%3
            if not self.active or not 0<=tile<6 or (self.pending and self.pending.get('kind') not in ('channel-more','list-more')) or index>=len(self.items):return
            self.focus_pending=False
            self.pending={'id':secrets.token_hex(8),'kind':'play','url':self.items[index]['uri'],'tab':self.source_tab,'time':self.clock()}
            self.message='STARTING';self.completed=None

    def acknowledge(self,data):
        if type(data.get('ok')) is not bool:raise ValueError('Expected playback result')
        with self.lock:
            if not self.pending or data.get('id')!=self.pending['id'] or (not self.active and self.pending.get('kind')!='focus'):return False
            if self.pending.get('kind')=='focus':self.pending=None;return True
            if self.pending.get('kind') in ('channel','channel-more','list-more'):
                if data['ok']:return True
                self.pending=None;self.message='CHANNEL FAILED';return True
            self.completed=bool(data.get('ok'));self.pending=None
            self.message='' if self.completed else 'PLAY FAILED'
        return True

    def take_success(self):
        with self.lock:
            success=self.completed is True;self.completed=None
            return success

    async def load_covers(self,urls):
        async def load(url):
            image=await asyncio.to_thread(self.loader.load,url)
            if image:self.covers[url]=image
        await asyncio.gather(*(load(url) for url in urls))
        while len(self.covers)>64:self.covers.pop(next(iter(self.covers)))

    def frame(self):
        self.state()
        with self.lock:
            rows=[dict(i) for i in self.items[self.offset:self.offset+3]];offset=self.offset;message=self.message
        urls=[i['image'] for i in rows if i['image'] and i['image'] not in self.covers]
        if urls and (self.task is None or self.task.done()):self.task=asyncio.create_task(self.load_covers(urls))
        for item in rows:item['cover']=self.covers.get(item['image'])
        if rows and message:rows[0]['artist']=message
        return self.renderer.render(rows,message,offset)

    async def close(self):
        self.close_view()
        if self.task and not self.task.done():self.task.cancel();await asyncio.gather(self.task,return_exceptions=True)
