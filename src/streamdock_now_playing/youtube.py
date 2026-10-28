"""Browser GSMTC mode; no Spotify API or master-volume dependency.

GSMTC identifies a browser, not an origin or tab. The configured browser's
published media session is used; dedicate that browser to YouTube if needed.
"""
import time
from .media import GSMTCMedia
from .controller import MediaService
from .audio import AudioSessions
from .renderer import LayoutRenderer, operation_feedback
from .browser_launcher import BrowserLauncher
from .youtube_browser import YouTubeBrowser


class YouTubeMode:
    def __init__(self, settings=None, service=None, clock=time.monotonic):
        settings=settings or {}
        browser=settings.get('source','Chrome')
        process=settings.get('process_name','chrome.exe')
        self.service=service or MediaService(GSMTCMedia(preferred=browser),
            AudioSessions([{'source_contains':browser,'process_name':process}]))
        self.clock=clock
        self.layout=LayoutRenderer(settings.get('display',{}))
        self.snapshot={};self.image=None;self.key=object();self.retry=0
        self.view='normal';self.feedback='';self.until=0;self.anchor=0
        self.artwork=self.layout.artwork(None);self.expanded=self.layout.expanded_artwork(None)
        self.last_input=self.clock()
        self.capture=None
        self.launcher=BrowserLauncher(enabled=bool(settings.get('open_on_enter',False)))
        self.browser=YouTubeBrowser(clock)
        self.browser_return='normal'
        self.held_video=None
        self.initial_view_pending=True

    def enter(self):
        self.home()
        self.initial_view_pending=False
        if not self.has_video():self.open_browser()
        import logging
        try:
            running=self.launcher.running()
            if not running and self.view=='normal':self.open_browser()
            if running and self.browser.reuse():
                logging.info('YouTube entry: reuse registered tab');return
            if running and self.snapshot.get('source') and self.snapshot.get('key'):
                self.browser.request_foreground()
                logging.info('YouTube entry: retain existing browser media');return
            launched=self.launcher.enter()
            if launched or (not running and self.launcher.opened):self.browser.request_foreground(forget=True)
            logging.info('YouTube entry: chrome_running=%s launched=%s',running,launched)
        except OSError:
            logging.exception('Could not launch YouTube in Chrome')
            self.feedback='CHROME ERROR';self.until=self.clock()+2.5
            if self.browser.active:
                with self.browser.lock:self.browser.message='CHROME ERROR'

    def home(self):
        self.view='normal';self.feedback='';self.until=0
        self.held_video=None
        self.browser.close_view()
        self.browser_return='normal'

    def open_browser(self):
        self.browser.open();self.view='browser';self.browser_return='normal';self.last_input=self.clock()

    def has_video(self):
        watch=self.browser.has_watch_page()
        return watch if watch is not None else bool(self.snapshot.get('source') and self.snapshot.get('key'))

    async def poll(self):
        s=await self.service.snapshot()
        key=s.get('key')
        if key!=self.snapshot.get('key'):self.held_video=None
        if key!=self.key or self.clock()>=self.retry:
            image=await self.service.artwork(s)
            artwork=self.layout.artwork(image);expanded=self.layout.expanded_artwork(image)
            self.artwork=artwork;self.expanded=expanded
            self.image=image;self.key=key;self.retry=self.clock()+(30 if image else 3)
        old=self.snapshot
        if (s.get('key'),s.get('position'),s.get('playing')) != (old.get('key'),old.get('position'),old.get('playing')):
            self.anchor=self.clock()
        self.snapshot=s
        if self.initial_view_pending:
            self.initial_view_pending=False
            if self.view=='normal' and not self.has_video():self.open_browser()
        if self.view=='browser' and self.browser.take_success():self.home()

    def frame(self):
        video=self.capture.latest() if self.capture else None
        # Full video is a latched view. A stalled capture must not exit it.
        if self.view=='metadata' and self.clock()-self.last_input>=self.layout.settings.expanded_timeout_seconds:self.home()
        if self.view=='browser':return self.browser.frame()
        s=dict(self.snapshot)
        if not s.get('source'):
            s.update(title='YouTube',artist='Play in browser')
        if s.get('playing'):
            s['position']=min(s.get('duration',0),s.get('position',0)+self.clock()-self.anchor)
        if self.view=='artwork':
            if video:self.held_video=video
            return self.held_video if self.held_video else self.expanded
        if self.view=='metadata':return self.layout.expanded_metadata(s)
        return self.layout.compose(self.artwork,s,
            self.feedback if self.clock()<self.until else '')

    async def input(self,role,event,ticks=0,tile=0):
        self.last_input=self.clock()
        if role=='back' and event=='keyDown':
            if self.view=='browser' and self.browser_return=='metadata':
                self.browser.close_view();self.view='metadata';self.browser_return='normal';return
            self.home();return
        if self.view=='browser':
            if role=='seek' and event=='dialRotate':self.browser.move(ticks);return
            if role=='tile' and event=='keyDown':self.browser.select(tile);return
        if role=='tile' and event=='keyDown':
            if self.view=='metadata' and tile>=3:
                self.browser.open_current_channel(str(self.snapshot.get('title') or ''))
                self.view='browser';self.browser_return='metadata';return
            if self.view!='normal':self.home();return
            if tile in (0,1,3,4):self.view='artwork';return
            if tile==2:self.view='metadata';self.layout.reset_metadata_scroll();return
        command=None;amount=1
        if event=='dialRotate':
            if not ticks:return
            if role=='volume':command,amount='volume',ticks*4
            elif role=='tracks':command='next' if ticks>0 else 'previous'
            elif role=='seek':command,amount='seek',ticks*5
        elif (role=='volume' and event=='dialDown') or (role=='tile' and event=='keyDown' and tile==5):command='play'
        if command:
            result=await self.service.command(command,amount)
            self.feedback=operation_feedback(command,result,self.snapshot)
            self.until=self.clock()+self.layout.settings.feedback_seconds
