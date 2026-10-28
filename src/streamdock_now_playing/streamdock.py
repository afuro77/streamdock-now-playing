"""Stream Dock host protocol adapter; see THIRD_PARTY_NOTICES.md."""
import argparse, asyncio, io, json, logging, time
from pathlib import Path
from logging.handlers import RotatingFileHandler
from PIL import Image, ImageOps
from websockets.asyncio.client import connect
from .renderer import encode, tiles, card, LayoutRenderer, operation_feedback
from .media import GSMTCMedia
from .audio import AudioSessions
from .controller import MediaService
from .runtime import data_directory, read_config, load_startup_config
from .spotify import SpotifyClient, QueueState
from .queue_renderer import QueueRenderer
from .volume_router import AutoVolume
from .queue_navigation import QueueNavigator, QueueSelectionError
from .desktop import ModeManager, DesktopHome
from .master_audio import MasterAudio
from .track_details import TrackDetails
from .detail_renderer import DetailRenderer
from .playlists import PlaylistBrowser
from .devices import DeviceBrowser
from .liked_songs import LikedFirst, SavedTracks
from .bookmarks import BookmarkPlaylists
from .artist_tracks import ArtistBrowser, resolve_artist, playback_uris
from .youtube import YouTubeMode

class Plugin:
 def __init__(self, provider=None, data_dir=None, config=None):
  self.data_dir=Path(data_dir) if data_dir else data_directory()
  config=config if config is not None else read_config(self.data_dir)
  logging.info('Configuration loaded directory=%s exists=%s desktop_configured=%s',self.data_dir,(self.data_dir/'config.json').is_file(),bool(config.get('desktop')))
  self.preferred_source=config.get('preferred_source','')
  self.artist_aliases=config.get('artist_aliases',{})
  if not isinstance(self.artist_aliases,dict) or not all(isinstance(k,str) and isinstance(v,str) and k and v for k,v in self.artist_aliases.items()):raise ValueError('artist_aliases must map nonempty names to names')
  self.provider=provider if provider is not None else MediaService(GSMTCMedia(preferred=self.preferred_source),AudioSessions(config.get('audio_mappings',[])));self.contexts={};self.images=tiles(None);self.sent={};self.key=object();self.overlay='';self.until=0;self.mode='art';self.snapshot={};self.ws=None;self.image_retry=0
  self.layout=LayoutRenderer(config.get('display',{}));self.artwork_images=self.layout.artwork(None)
  self.last_input=time.monotonic();self.render_lock=asyncio.Lock();self.titled=set();self.control_cards={}
  self.nav_feedback='';self.nav_feedback_until=0
  self.timeline_anchor=None
  self.queue_state=QueueState(SpotifyClient(config.get('spotify',{}),self.data_dir))
  self.track_details=TrackDetails(self.queue_state.client);self.detail_renderer=DetailRenderer();self.detail_page=0;self.detail_with_artwork=False
  self.playlists=PlaylistBrowser(LikedFirst(BookmarkPlaylists(self.queue_state.client,config.get('playlist_bookmarks',[]),include_library=not config.get('playlist_bookmarks_only',False))));self.playlist_play_task=None;self.artist_browser=ArtistBrowser();self.artist_play_task=None;self.artist_resolve_task=None
  self.liked=PlaylistBrowser(SavedTracks(self.queue_state.client))
  self.devices=DeviceBrowser(self.queue_state.client);self.device_switch_task=None;self.status_hold_task=None;self.status_pressed=None;self.status_long=False
  self.volume_router=AutoVolume(self.queue_state.client,self.local_volume,self.volume_feedback)
  self.queue_renderer=QueueRenderer();self.navigation=[];self.queue_skip_task=None;self.return_steps=0
  self.master_audio=MasterAudio();self.knob_guard_until=0
  self.home_hold_task=None;self.home_hold_seconds=.7;self.home_pressed=None;self.home_long=False;self.mode_generation=0
  self.modes=ModeManager(self.data_dir/'mode.json',modes=('spotify','desktop','youtube') if config.get('youtube',{}).get('enabled',False) else ('spotify','desktop'))
  self.youtube=YouTubeMode(config.get('youtube',{}))
  logging.info('Mode restored: %s',self.modes.active)
  try:self.desktop=DesktopHome(config.get('desktop',{}))
  except Exception:
   logging.exception('Invalid desktop configuration; using defaults')
   self.desktop=DesktopHome()
  logging.info('Desktop initialized cells=%s weather_location=%s',list(self.desktop.widgets),config.get('desktop',{}).get('weather',{}).get('location'))
  self.view_mode='normal';self.expanded_artwork_images=self.layout.expanded_artwork(None)
 async def open_queue(self):
  if self.queue_skip_task and not self.queue_skip_task.done():self.queue_skip_task.cancel()
  if self.view_mode!='queue':self.navigation.append(self.view_mode);self.queue_state.offset=0
  self.view_mode='queue';self.queue_state.request()
  self.overlay='';self.until=0;self.nav_feedback='QUEUE';self.nav_feedback_until=time.monotonic()+1
  await self.render()
 async def open_playlists(self):
  if self.view_mode!='playlists':self.navigation.append(self.view_mode)
  self.view_mode='playlists';self.nav_feedback='';self.playlists.request()
  await self.render()
 async def select_playlist(self,uri,generation):
  if uri=='local:liked-songs':
   self.navigation.append(self.view_mode);self.view_mode='liked';self.liked.request();await self.render();return
  try:
   self.playlists.message='STARTING'
   logging.info('Playlist start requested: %s',uri)
   await asyncio.to_thread(self.queue_state.client.play_playlist,uri)
   logging.info('Playlist start accepted: %s',uri)
   self.key=object();self.queue_state.updated=0
   if self.mode_generation==generation and self.modes.active=='spotify' and self.view_mode=='playlists':
    self.view_mode='normal';self.navigation.clear();self.overlay='';self.until=0
  except asyncio.CancelledError:raise
  except Exception as error:
   status=getattr(error,'status',None)
   self.playlists.message=('PLAY '+str(status)) if status else 'PLAY FAILED'
   logging.warning('Playlist start failed status=%s type=%s',status,type(error).__name__)
  finally:
   if self.playlists.message=='STARTING':self.playlists.message=''
  await self.render()
 async def open_artist_tracks(self):
  people=(self.track_details.data or {}).get('artists') or []
  index=int(time.monotonic()/8)%len(people) if people and self.detail_page==1 else 0
  artist_id=people[index].get('id') if people else None
  if artist_id:
   await self.show_artist_tracks(artist_id);return True
  if not self.queue_state.client.settings.get('enabled'):return False
  if self.artist_resolve_task and not self.artist_resolve_task.done():return True
  self.nav_feedback='LOADING';self.nav_feedback_until=time.monotonic()+3
  self.artist_resolve_task=asyncio.create_task(self.resolve_artist_entry(dict(self.snapshot),self.mode_generation,self.view_mode))
  await self.render();return True
 async def show_artist_tracks(self,artist_id):
  self.artist_browser.open(artist_id);self.navigation.append(self.view_mode)
  self.view_mode='artist_tracks';self.overlay='';self.until=0;self.nav_feedback=''
  await self.render()
 async def resolve_artist_entry(self,snapshot,generation,view):
  try:
   lookup=dict(snapshot);lookup['artist']=self.artist_aliases.get(snapshot.get('artist'),snapshot.get('artist',''))
   artist_id=await asyncio.to_thread(resolve_artist,self.queue_state.client,lookup)
   current=lambda: (self.mode_generation==generation and self.modes.active=='spotify' and self.view_mode==view and self.snapshot.get('artist')==snapshot.get('artist') and self.snapshot.get('title')==snapshot.get('title'))
   if not current():return
   if artist_id:await self.show_artist_tracks(artist_id)
   else:
    self.nav_feedback='NO ARTIST';self.nav_feedback_until=time.monotonic()+3;await self.render()
  except asyncio.CancelledError:raise
  except Exception as error:
   logging.warning('Artist lookup failed type=%s status=%s',type(error).__name__,getattr(error,'status',None))
   if self.mode_generation==generation and self.modes.active=='spotify' and self.view_mode==view:
    self.nav_feedback='ARTIST ERROR';self.nav_feedback_until=time.monotonic()+3;await self.render()
 async def select_artist_track(self,uri,generation,browser):
  try:
   browser.message='STARTING'
   uris=playback_uris(browser.client.rows,uri)
   await asyncio.to_thread(self.queue_state.client.play_tracks,uris)
   self.queue_state.updated=0;self.key=object()
   if self.mode_generation==generation and self.modes.active=='spotify' and self.view_mode=='artist_tracks' and self.artist_browser.browser is browser:
    self.view_mode='normal';self.navigation.clear();self.overlay='';self.until=0
  except asyncio.CancelledError:raise
  except Exception as error:browser.message='PLAY '+str(getattr(error,'status',None) or 'FAILED')
  finally:
   if browser.message=='STARTING':browser.message=''
  await self.render()
 async def select_liked(self,uri,index,generation):
  try:
   self.liked.message='STARTING'
   await asyncio.to_thread(self.queue_state.client.play_saved_selection,uri,index)
   self.queue_state.updated=0;self.key=object()
   if generation==self.mode_generation and self.modes.active=='spotify' and self.view_mode=='liked':
    self.view_mode='normal';self.navigation.clear()
  except asyncio.CancelledError:raise
  except Exception as error:self.liked.message='Reconnect Spotify' if 'permission' in str(error).lower() else 'PLAY FAILED'
  finally:
   if self.liked.message=='STARTING':self.liked.message=''
  await self.render()
 async def open_devices(self):
  if self.view_mode!='devices':self.navigation.append(self.view_mode)
  self.view_mode='devices';self.nav_feedback='';self.devices.page=0;self.devices.request(force=True)
  await self.render()
 async def status_hold(self,generation):
  await asyncio.sleep(.7)
  if generation==self.mode_generation and self.modes.active=='spotify' and self.view_mode=='normal' and self.status_pressed is not None:
   self.status_long=True;await self.open_devices()
 async def status_release(self):
  if self.status_pressed is None:return
  held=time.monotonic()-self.status_pressed;generation=self.status_generation
  self.status_pressed=None
  if self.status_hold_task and not self.status_hold_task.done():self.status_hold_task.cancel()
  if generation!=self.mode_generation or self.modes.active!='spotify' or self.status_long:return
  if self.view_mode!='normal':return
  if held>=.7:await self.open_devices();return
  try:self.overlay=operation_feedback('play',await asyncio.wait_for(self.provider.command('play',1),5),self.snapshot)
  except Exception:self.overlay='Operation failed'
  self.until=time.monotonic()+self.layout.settings.feedback_seconds;await self.render()
 async def switch_device(self,device_id,generation):
  success=await self.devices.transfer(device_id)
  if success:
   self.volume_router.devices_updated=-float('inf');self.queue_state.updated=0;self.key=object()
   if generation==self.mode_generation and self.modes.active=='spotify' and self.view_mode=='devices':
    self.view_mode='normal';self.navigation.clear();self.nav_feedback='CONNECTED';self.nav_feedback_until=time.monotonic()+1.5
  await self.render()
 async def home_hold(self,generation,mode):
  await asyncio.sleep(self.home_hold_seconds)
  if generation!=self.mode_generation or self.home_pressed is None:return
  self.home_long=True
  if mode=='spotify':await self.open_playlists()
 async def go_home(self):
  if self.modes.active=='youtube':self.youtube.home()
  elif self.modes.active=='desktop':self.desktop.home()
  else:
   if self.queue_skip_task and not self.queue_skip_task.done():self.queue_skip_task.cancel()
   self.view_mode='normal';self.navigation.clear();self.overlay='';self.until=0
  await self.render()
 async def local_volume(self,amount):
  return await self.provider.command('volume',amount)
 async def volume_feedback(self,result):
  if self.modes.active=='spotify' and self.view_mode=='normal':
   self.overlay=operation_feedback('volume',result,self.snapshot)
   self.until=time.monotonic()+self.layout.settings.feedback_seconds
   await self.render()

 async def skip_queue(self,count,target_uri=None):
  self.return_steps=0
  self.queue_state.items=[];self.queue_state.message='Skipping '+str(count)+'...'
  try:
   navigator=QueueNavigator(self.queue_state.client,self.provider.command)
   def accepted(steps):self.return_steps=steps
   await navigator.select(target_uri,accepted)
   self.queue_state.updated=0
   self.key=object();self.image_retry=0
   self.view_mode='normal';self.navigation.clear();self.overlay='';self.until=0
   self.sent.clear()  # Replace all six Queue tiles with the normal layout.
   await self.render()
  except asyncio.CancelledError:
   self.queue_state.updated=0;raise
  except Exception as error:
   self.queue_state.message=str(error) if isinstance(error,QueueSelectionError) else 'SKIP FAILED'
   self.queue_state.updated=time.monotonic()
   self.nav_feedback=self.queue_state.message;self.nav_feedback_until=time.monotonic()+2

 async def return_from_queue(self):
  self.overlay='RETURNING';self.until=time.monotonic()+60
  try:
   while self.return_steps>0:
    result=await asyncio.wait_for(self.provider.command('seek',-1_000_000_000),5)
    text=str(result).upper()
    if not (text=='SEEK' or text.startswith('SEEK -')):
     self.overlay='RETURN UNSUPPORTED';return
    await asyncio.sleep(.15)
    result=await asyncio.wait_for(self.provider.command('previous',1),5)
    if str(result).upper()!='PREVIOUS':
     self.overlay='RETURN FAILED';return
    self.return_steps-=1
    if self.return_steps:await asyncio.sleep(.35)
   self.overlay='RETURNED'
  except asyncio.CancelledError:
   self.overlay='';raise
  except Exception:
   self.overlay='RETURN FAILED'
  finally:
   self.until=time.monotonic()+self.layout.settings.feedback_seconds
   self.key=object();self.image_retry=0;self.queue_state.updated=0

 def display_snapshot(self):
  # GSMTC players may publish their position only every several seconds.
  # Extrapolate for display only; never feed this value into media commands.
  snapshot=dict(self.snapshot)
  artist=snapshot.get('artist')
  if artist in self.artist_aliases:snapshot['artist']=self.artist_aliases[artist]
  anchor=self.timeline_anchor
  if anchor and snapshot.get('playing') is True:
   value=anchor['position']+max(0,time.monotonic()-anchor['time'])
   duration=snapshot.get('duration') or 0
   snapshot['position']=min(value,duration) if duration>0 else value
  return snapshot
 def update_timeline(self,snapshot):
  now=time.monotonic();position=snapshot.get('position',0)
  old=self.timeline_anchor
  identity=(snapshot.get('source'),snapshot.get('key'))
  if (old is None or old['identity']!=identity or
      old['reported']!=position or old['playing']!=snapshot.get('playing')):
   self.timeline_anchor=dict(identity=identity,position=position,reported=position,
                             playing=snapshot.get('playing'),time=now)
 async def send(self,event,context,payload):
  await self.ws.send(json.dumps(dict(event=event,context=context,payload=payload)))
 async def render(self):
  async with self.render_lock:
   await self.render_frame()
 def animation_interval(self):
  if self.modes.active=='youtube' and self.youtube.view=='artwork':
   return 1/(self.youtube.capture.target_fps if self.youtube.capture else 12)
  return .1
 async def animation(self):
  # Bound device traffic and use deadlines rather than adding rendering time
  # to every frame. Polling/events must not inject extra animation frames.
  self.animation_running=True
  deadline=time.monotonic()
  while True:
   if self.modes.active in ('desktop','youtube') or self.view_mode!='normal' or self.nav_feedback:
    try:await self.render()
    except Exception:logging.exception('animation')
   interval=self.animation_interval()
   deadline+=interval
   now=time.monotonic()
   if deadline<now:deadline=now+interval
   await asyncio.sleep(max(0,deadline-now))
 async def render_frame(self):
  if self.view_mode in ('artwork','metadata') and time.monotonic()-self.last_input>=self.layout.settings.expanded_timeout_seconds:
   self.view_mode='normal';self.overlay='';self.until=0
  active=self.overlay if time.monotonic()<self.until else ''
  if self.modes.active=='youtube':
   self.images=self.youtube.frame()
  elif self.modes.active=='desktop':
   self.images=self.desktop.frame()
  elif self.view_mode=='liked':
   self.liked.request();self.images=self.liked.render()
  elif self.view_mode=='devices':
   self.devices.request();self.images=self.devices.render()
  elif self.view_mode=='artist_tracks':
   browser=self.artist_browser.browser;browser.request();self.images=browser.render()
  elif self.view_mode=='playlists':
   self.playlists.request();self.images=self.playlists.render()
  elif self.view_mode=='queue':
   if not self.queue_skip_task or self.queue_skip_task.done():self.queue_state.request()
   self.images=self.queue_renderer.render(self.queue_state.visible(),self.queue_state.message,self.queue_state.offset)
  elif self.view_mode=='artwork':self.images=self.expanded_artwork_images
  elif self.view_mode=='metadata':
   self.track_details.request(self.snapshot)
   if self.detail_page==0:self.images=self.layout.expanded_metadata(self.display_snapshot())
   elif self.detail_page==1:self.images=self.detail_renderer.artist(self.track_details.data,self.display_snapshot(),self.track_details.message)
   else:self.images=self.detail_renderer.album(self.track_details.data,self.display_snapshot(),self.layout,self.track_details.message)
  else:self.images=self.layout.compose(self.artwork_images,self.display_snapshot(),active,self.mode=='info')
  if self.modes.active=='spotify' and self.nav_feedback and time.monotonic()<self.nav_feedback_until:
   self.images=list(self.images);self.images[5]=self.layout.status(self.display_snapshot(),self.nav_feedback)
  else:self.nav_feedback=''
  for ctx,a in list(self.contexts.items()):
   role=a['role'];settings=a['settings']
   if role=='tile':
    n=int(settings.get('tile',0));n=max(0,min(5,n))
    img=self.images[n]
   else:
    if role in self.control_cards:img=self.control_cards[role]
    else:
     img=card({'volume':'VOLUME\nPlay / Pause','tracks':'PREV / NEXT','seek':'SEEK 5s\nShuffle','mode':'MODE /\nSPOTIFY DESKTOP','player':'QUEUE /\nDESKTOP HOME','back':'BACK'}.get(role,role));self.control_cards[role]=img
   if self.sent.get(ctx)!=img:
    if ctx not in self.titled:
     await self.send('setTitle',ctx,{'title':'','target':0});self.titled.add(ctx)
    await self.send('setImage',ctx,{'image':img,'target':0});self.sent[ctx]=img
 async def polling(self):
  while True:
   try:
    if self.modes.active=='youtube':
     try:await asyncio.wait_for(self.youtube.poll(),5)
     except Exception:logging.exception('YouTube poll')
    s=await asyncio.wait_for(self.provider.snapshot(),5)
    key=s.get('key')
    if key!=self.key or time.monotonic()>self.image_retry:
     b=await asyncio.wait_for(self.provider.artwork(s),5)
     self.artwork_images=self.layout.artwork(b);self.expanded_artwork_images=self.layout.expanded_artwork(b);self.full=bool(b)
     self.key=key;self.image_retry=time.monotonic()+(30 if b else 3)
     logging.info('Artwork refreshed, bytes=%s',len(b or b''))
    # Publish metadata only after its matching artwork is ready. Animation
    # must never observe new text alongside the previous track's cover.
    self.update_timeline(s);self.snapshot=s
    if self.view_mode=='normal' or not getattr(self,'animation_running',False):await self.render()
    status={'connected':True,'active_mode':self.modes.active,'view_mode':self.view_mode,'contexts':{k:{'role':v['role'],'settings':v['settings']} for k,v in self.contexts.items()},'source':s.get('source'),'playing':s.get('playing'),'artwork':bool(getattr(self,'full',None)),'updated':time.time()}
    if self.modes.active=='youtube':
     status.update(source=self.youtube.snapshot.get('source'),playing=self.youtube.snapshot.get('playing'),artwork=bool(self.youtube.image),view_mode=self.youtube.view)
     status['youtube_catalog']=self.youtube.browser.diagnostics()
     if self.youtube.capture:status.update(video_frames_received=self.youtube.capture.count,video_fresh=bool(self.youtube.capture.latest()),video_diagnostics=self.youtube.capture.diagnostics())
    tmp=self.data_dir/'status.tmp';tmp.write_text(json.dumps(status,ensure_ascii=False),encoding='utf-8');tmp.replace(self.data_dir/'status.json')
   except Exception:logging.exception('poll')
   await asyncio.sleep(.5)
 async def event(self,d):
  event=d.get('event');ctx=d.get('context');p=d.get('payload',{});action=d.get('action','')
  if event in ('keyDown','keyUp','dialDown','dialUp','dialRotate'):
   control=self.contexts.get(ctx,{})
   logging.info('Input event=%s role=%s tile=%s ticks=%s pressed=%s context=%s',event,control.get('role'),control.get('settings',{}).get('tile'),p.get('ticks'),p.get('pressed'),ctx)
  if event=='willAppear':
   self.contexts[ctx]={'role':action.rsplit('.',1)[-1],'settings':p.get('settings',{}),'device':d.get('device')};logging.debug('Control appeared');self.sent.pop(ctx,None);self.titled.discard(ctx)
  elif event=='willDisappear':self.contexts.pop(ctx,None);self.sent.pop(ctx,None);self.titled.discard(ctx)
  elif event=='didReceiveSettings' and ctx in self.contexts:self.contexts[ctx]['settings']=p.get('settings',{});self.sent.pop(ctx,None);self.titled.discard(ctx)
  elif event=='keyUp' and ctx in self.contexts and self.contexts[ctx]['role']=='tile' and self.contexts[ctx]['settings'].get('tile')==5 and self.status_pressed is not None:
   await self.status_release();return
  elif event=='keyUp' and ctx in self.contexts and self.contexts[ctx]['role']=='player':
   if self.home_pressed is None:return
   held=time.monotonic()-self.home_pressed
   generation=self.home_pressed_generation
   mode=self.home_pressed_mode
   if self.home_hold_task and not self.home_hold_task.done():self.home_hold_task.cancel()
   if generation==self.mode_generation:
    if not self.home_long and held>=self.home_hold_seconds:
     if mode=='spotify':await self.open_playlists()
    elif not self.home_long:
     if mode=='spotify':await self.open_queue()
     elif mode=='youtube':self.youtube.open_browser();await self.render()
     else:await self.go_home()
   self.home_pressed=None;return
  elif event in ('keyDown','dialDown','dialRotate') and ctx in self.contexts:
   a=self.contexts[ctx];role=a['role'];ticks=max(-20,min(20,int(p.get('ticks',0))))
   self.last_input=time.monotonic()
   logging.debug('Control input: %s',event)
   if (role in ('back','mode','player') or (role=='seek' and event=='dialRotate')) and self.artist_resolve_task and not self.artist_resolve_task.done():
    self.artist_resolve_task.cancel()
   if role in ('back','mode','player') or (role=='tile' and a['settings'].get('tile')!=5):
    self.status_pressed=None
    if self.status_hold_task and not self.status_hold_task.done():self.status_hold_task.cancel()
   if role=='player' and event=='keyDown':
    if self.home_pressed is None:
     self.home_pressed=time.monotonic();self.home_pressed_mode=self.modes.active;self.home_pressed_generation=self.mode_generation;self.home_long=False
     self.home_hold_task=asyncio.create_task(self.home_hold(self.mode_generation,self.modes.active))
    return
   if role=='mode' and event=='keyDown':
    self.mode_generation+=1;self.home_pressed=None
    if self.home_hold_task and not self.home_hold_task.done():self.home_hold_task.cancel()
    previous=self.modes.active
    self.modes.toggle()
    self.desktop.home()
    self.youtube.home()
    if self.youtube.capture:self.youtube.capture.clear()
    self.knob_guard_until=time.monotonic()+.25
    logging.info('Mode key: %s -> %s',previous,self.modes.active)
    self.view_mode='normal';self.navigation.clear()
    self.overlay='';self.until=0;self.nav_feedback='';self.nav_feedback_until=0
    self.sent.clear()
    if self.modes.active=='youtube':self.youtube.enter()
    await self.render();return
   if event in ('dialDown','dialRotate') and time.monotonic()<self.knob_guard_until:return
   if self.modes.active=='youtube':
    try:await asyncio.wait_for(self.youtube.input(role,event,ticks,int(a['settings'].get('tile',0))),5)
    except Exception:
     logging.exception('YouTube command');self.youtube.feedback='Operation failed';self.youtube.until=time.monotonic()+2.5
    await self.render();return
   if self.modes.active=='desktop':
    if role=='player' and event=='keyDown':
     self.desktop.home();await self.render();return
    if role=='volume' and event in ('dialDown','dialRotate'):
     try:result=self.master_audio.command(ticks*2 if event=='dialRotate' else None)
     except Exception:logging.exception('Master volume');result='AUDIO ERROR'
     self.desktop.show_feedback(result);await self.render();return
    if role=='tracks' and event=='dialRotate':
     self.desktop.page(ticks);await self.render();return
    if role=='back' and event=='keyDown':
     self.desktop.back();await self.render();return
    if role=='tile' and event=='keyDown':
     await self.desktop.press(int(a['settings'].get('tile',0)))
     await self.render()
    return
   if self.view_mode=='liked' and role=='seek' and event=='dialRotate':
    self.liked.move(ticks);await self.render();return
   if self.view_mode=='liked' and role=='tile':
    if event=='keyDown' and (self.playlist_play_task is None or self.playlist_play_task.done()):
     tile=int(a['settings'].get('tile',0));uri=self.liked.selected(tile)
     if uri:self.playlist_play_task=asyncio.create_task(self.select_liked(uri,self.liked.page+tile%3,self.mode_generation))
    return
   if self.view_mode=='devices' and role=='seek' and event=='dialRotate':
    self.devices.move(ticks);await self.render();return
   if self.view_mode=='devices' and role=='tile':
    if event=='keyDown' and (self.device_switch_task is None or self.device_switch_task.done()):
     device_id=self.devices.selected(int(a['settings'].get('tile',0)))
     if device_id:self.device_switch_task=asyncio.create_task(self.switch_device(device_id,self.mode_generation))
    return
   if self.devices.switching and role=='volume':return
   if self.view_mode=='artist_tracks' and role=='seek' and event=='dialRotate':
    self.artist_browser.browser.move(ticks);await self.render();return
   if self.view_mode=='artist_tracks' and role=='tile':
    if event=='keyDown' and (self.artist_play_task is None or self.artist_play_task.done()):
     browser=self.artist_browser.browser;uri=browser.selected(int(a['settings'].get('tile',0)))
     if uri:self.artist_play_task=asyncio.create_task(self.select_artist_track(uri,self.mode_generation,browser))
    return
   if self.view_mode=='metadata' and role=='tile' and event=='keyDown':
    tile=int(a['settings'].get('tile',0))
    if self.detail_page==1 or (self.detail_page==0 and tile>=3):
     if await self.open_artist_tracks():return
   if self.view_mode=='playlists' and role=='seek' and event=='dialRotate':
    self.playlists.move(ticks);await self.render();return
   if self.view_mode=='playlists' and role=='tile':
    if event=='keyDown' and (self.playlist_play_task is None or self.playlist_play_task.done()):
     uri=self.playlists.selected(int(a['settings'].get('tile',0)))
     if uri:self.playlist_play_task=asyncio.create_task(self.select_playlist(uri,self.mode_generation))
    return
   if self.view_mode in ('metadata','artwork') and role=='seek' and event=='dialRotate':
    if ticks:
     if self.detail_with_artwork or self.view_mode=='artwork':
      self.detail_with_artwork=True
      page=0 if self.view_mode=='artwork' else self.detail_page+1
      page=(page+ticks)%4
      self.view_mode='artwork' if page==0 else 'metadata'
      if page:self.detail_page=page-1
     else:self.detail_page=(self.detail_page+ticks)%3
     self.layout.reset_metadata_scroll()
    await self.render();return
   if role=='back' and event=='keyDown':
    if self.view_mode=='normal' and not self.navigation:return
    if self.queue_skip_task and not self.queue_skip_task.done():self.queue_skip_task.cancel()
    if self.view_mode in ('metadata','artwork'):self.navigation.clear();self.view_mode='normal'
    else:self.view_mode=self.navigation.pop() if self.navigation else 'normal'
    self.overlay='';self.until=0;self.nav_feedback='BACK';self.nav_feedback_until=time.monotonic()+1
    await self.render();return
   if self.view_mode=='queue' and role=='seek' and event=='dialRotate':
    if not self.queue_skip_task or self.queue_skip_task.done():self.queue_state.move(ticks)
    await self.render();return
   if self.view_mode=='queue' and role=='tile':
    tile=int(a['settings'].get('tile',0));column=tile%3+self.queue_state.offset
    busy=self.queue_skip_task and not self.queue_skip_task.done()
    fetching=self.queue_state.task and not self.queue_state.task.done()
    if event=='keyDown' and 0<=tile<6 and not busy and not fetching and column<len(self.queue_state.items):
     self.queue_skip_task=asyncio.create_task(self.skip_queue(column+1,self.queue_state.items[column].get('uri')))
    return
   # Reuse the big-knob play command only for normal bottom-right LCD.
   if event=='keyDown' and role=='tile' and self.view_mode=='normal' and int(a['settings'].get('tile',0))==5:
    if self.status_pressed is None:
     self.status_pressed=time.monotonic();self.status_generation=self.mode_generation;self.status_long=False
     self.status_hold_task=asyncio.create_task(self.status_hold(self.mode_generation))
    return
   if event=='keyDown' and role=='tile':
    tile=int(a['settings'].get('tile',0))
    if self.view_mode!='normal':self.view_mode='normal'
    elif tile in (0,1,3,4):self.view_mode='artwork';self.detail_with_artwork=True
    elif tile==2:self.view_mode='metadata';self.detail_with_artwork=True;self.detail_page=0;self.layout.reset_metadata_scroll()
    else:return
    self.overlay='';self.until=0
    await self.render();return
   cmd=None;amount=1
   if event=='dialRotate':
    if role=='volume':cmd,amount='volume',ticks*4
    elif role=='tracks' and ticks:cmd='next' if ticks>0 else 'previous'
    elif role=='seek':cmd,amount='seek',ticks*5
   elif role=='volume':cmd='play'
   elif role=='tracks':return  # v1: left small knob press is unassigned.
   elif role=='seek':cmd='shuffle'

   if cmd=='volume' and self.volume_router.handles(self.snapshot.get('source') or self.preferred_source):
    self.volume_router.submit(amount)
    return
   if cmd:
    if cmd in ('next','previous'):self.return_steps=0
    try:self.overlay=operation_feedback(cmd,await asyncio.wait_for(self.provider.command(cmd,amount),5),self.snapshot)
    except Exception:logging.exception('command');self.overlay='Operation failed'
    self.until=time.monotonic()+self.layout.settings.feedback_seconds
    if self.view_mode!='normal':self.overlay='';self.until=0
  await self.render()
 async def run(self,args):
  # The host owns lifecycle/relaunch. Exit on host disconnect so old launch
  # arguments cannot reconnect alongside the replacement plugin process.
  for attempt in range(5):
   try:
    async with connect(f'ws://127.0.0.1:{args.port}',max_size=4*1024*1024) as ws:
     self.ws=ws
     await ws.send(json.dumps({'event':args.registerEvent,'uuid':args.pluginUUID}));logging.info('registered')
     tasks=[asyncio.create_task(self.polling()),asyncio.create_task(self.animation())]
     try:
      async for raw in ws:
       try:await self.event(json.loads(raw))
       except Exception:logging.exception('event')
     finally:
      if self.volume_router.task:tasks.append(self.volume_router.task)
      if self.queue_skip_task:tasks.append(self.queue_skip_task)
      if self.queue_state.artwork_task:tasks.append(self.queue_state.artwork_task)
      if self.queue_state.task:tasks.append(self.queue_state.task)
      if self.home_hold_task:tasks.append(self.home_hold_task)
      if self.playlist_play_task:tasks.append(self.playlist_play_task)
      if self.artist_play_task:tasks.append(self.artist_play_task)
      if self.artist_resolve_task:tasks.append(self.artist_resolve_task)
      if self.status_hold_task:tasks.append(self.status_hold_task)
      if self.device_switch_task:tasks.append(self.device_switch_task)
      await self.liked.close()
      await self.devices.close()
      await self.artist_browser.close()
      await self.playlists.close()
      await self.track_details.close()
      await self.desktop.close()
      await self.youtube.browser.close()
      for task in tasks:task.cancel()
      await asyncio.gather(*tasks,return_exceptions=True)
      (self.data_dir/'status.json').write_text(json.dumps({'connected':False,'updated':time.time()}),encoding='utf-8')
     return
   except OSError:
    logging.warning('Host unavailable at launch, attempt %s',attempt+1)
    await asyncio.sleep(1)
   except Exception:
    logging.info('Host disconnected; exiting')
    return

def main():
 import os
 p=argparse.ArgumentParser();p.add_argument('-port',required=True,type=int);p.add_argument('-pluginUUID',required=True);p.add_argument('-registerEvent',required=True);p.add_argument('-info',default='{}');p.add_argument('--data-dir');args=p.parse_args()
 directory=Path(args.data_dir) if args.data_dir else data_directory()
 directory.mkdir(parents=True,exist_ok=True)
 h=RotatingFileHandler(directory/'plugin.log',maxBytes=1_000_000,backupCount=2,encoding='utf-8');logging.basicConfig(level=logging.INFO,handlers=[h],format='%(asctime)s %(levelname)s %(message)s',force=True)
 logging.info('Startup explicit_data_dir=%s resolved_directory=%r',bool(args.data_dir),str(directory))
 config=load_startup_config(directory,required=bool(args.data_dir or os.environ.get('STREAMDOCK_NOW_PLAYING_DATA_DIR')))
 audit={'started':time.time(),'config_exists':(directory/'config.json').is_file(),'spotify_enabled':bool(config.get('spotify',{}).get('enabled')),'recommendations':len(config.get('playlist_bookmarks',[])),'desktop_items':len(config.get('desktop',{}).get('items',[])),'location':config.get('desktop',{}).get('weather',{}).get('location')}
 (directory/'boot.json').write_text(json.dumps(audit,ensure_ascii=False),encoding='utf-8')
 logging.info('Startup configuration summary: %s',audit)
 plugin=Plugin(data_dir=directory,config=config)
 capture=None
 if config.get('youtube',{}).get('enabled') and config.get('youtube',{}).get('video_enabled'):
  from .video_capture import VideoCapture
  capture=VideoCapture(lambda:plugin.modes.active=='youtube' and plugin.youtube.view=='artwork',port=int(config['youtube'].get('video_port',8766)),browser=plugin.youtube.browser)
  try:
   url=capture.start();plugin.youtube.capture=capture
   (directory/'video-capture-session.json').write_text(json.dumps({'url':url}),encoding='utf-8')
   pairing=Path(__file__).resolve().parents[2]/'extensions'/'youtube-lcd'/'pairing.local.json'
   if pairing.parent.is_dir():
    try:pairing.write_text(json.dumps({'url':url}),encoding='utf-8')
    except OSError:logging.warning('Could not refresh local extension pairing')
   logging.info('Video capture receiver listening on loopback port %s',capture.port)
  except OSError:
   logging.exception('Video capture receiver unavailable; thumbnail mode remains available');capture=None
 try:asyncio.run(plugin.run(args))
 finally:
  if capture:capture.close()
if __name__=='__main__':main()
