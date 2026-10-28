"""Desktop widgets: independent data updates, rendering and actions."""
import asyncio
import json
import os
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
from PIL import Image, ImageDraw, ImageFont
from .renderer import encode
from .laundry import assess_laundry, laundry_window
from .desktop_icons import icon_panel
from .desktop_navigation import DesktopNavigation
from .launcher import LauncherSettings,open_target,expand_target


def panel(lines):
    image = Image.new('RGB', (128, 128), '#10212e')
    draw = ImageDraw.Draw(image)
    for text, size, y, color in lines:
        font_path = str(Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / 'meiryo.ttc')
        try:
            font = ImageFont.truetype(font_path, size)
        except OSError:
            font = ImageFont.load_default()
        while draw.textlength(text, font=font) > 122 and size > 10:
            size -= 1
            try: font = ImageFont.truetype(font_path, size)
            except OSError: break
        draw.text(((128-draw.textlength(text, font=font))/2, y), text, font=font, fill=color)
    return encode(image)


class ModeManager:
    def __init__(self, path=None, modes=('spotify','desktop')):
        self.modes=tuple(modes)
        self.path=Path(path) if path else None
        self.active='spotify'
        if self.path:
            try:
                saved=json.loads(self.path.read_text(encoding='utf-8')).get('active_mode')
                if saved in self.modes:self.active=saved
            except (OSError,ValueError,AttributeError):pass
    def toggle(self):
        self.active=self.modes[(self.modes.index(self.active)+1)%len(self.modes)]
        if self.path:
            try:
                tmp=self.path.with_suffix('.tmp')
                tmp.write_text(json.dumps({'active_mode':self.active}),encoding='utf-8')
                tmp.replace(self.path)
            except OSError:
                import logging
                logging.exception('Could not persist selected mode')
        return self.active


class Widget:
    def __init__(self, config): self.config = config
    def render(self): return panel([])
    def request(self): pass
    async def press(self): pass
    async def close(self): pass


class ClockWidget(Widget):
    def render(self):
        now = datetime.now()
        day = '月火水木金土日'[now.weekday()]
        return panel([(now.strftime('%H:%M') if now.second%2==0 else now.strftime('%H %M'), 36, 13, 'white'),
                      (now.strftime('%m/%d')+' '+day, 23, 65, '#b9d8ef')])


def fetch_weather(config):
    query = urlencode(dict(latitude=config['latitude'], longitude=config['longitude'],
        current='temperature_2m,weather_code,is_day',
        hourly='precipitation_probability,precipitation,relative_humidity_2m,wind_speed_10m,temperature_2m,sunshine_duration,weather_code',
        forecast_days=3, timezone='auto', wind_speed_unit='kmh'))
    with urlopen('https://api.open-meteo.com/v1/forecast?'+query, timeout=8) as response:
        return json.load(response)


class WeatherWidget(Widget):
    def __init__(self, config, fetcher=fetch_weather):
        super().__init__(config)
        self.fetcher=fetcher; self.data=None; self.task=None; self.next_update=0; self.fetched=0; self.failed=False
    def request(self):
        if 'latitude' not in self.config or 'longitude' not in self.config: return
        if time.monotonic() >= self.next_update and (self.task is None or self.task.done()):
            self.task=asyncio.create_task(self.refresh())
    async def refresh(self):
        try:
            data=await asyncio.to_thread(self.fetcher, self.config)
            float(data['current']['temperature_2m']); int(data['current']['weather_code'])
            self.data=data; self.fetched=time.monotonic(); self.failed=False
            self.next_update=time.monotonic()+max(60, self.config.get('refresh_seconds', 900))
        except asyncio.CancelledError: raise
        except Exception:
            self.failed=True; self.next_update=time.monotonic()+60
    def render(self):
        label=self.config.get('location','天気')
        if self.data is None:
            state='取得失敗' if self.failed else '取得中…' if 'latitude' in self.config else '地域未設定'
            return panel([(label,22,3,'#b9d8ef'),(state,22,58,'white')])
        c=self.data['current'];code=int(c['weather_code'])
        kind='sun' if code==0 else 'partly' if code<=2 else 'cloud' if code<=48 else 'snow' if code in (71,73,75,77,85,86) else 'rain'
        stale=self.failed or time.monotonic()-self.fetched>1800
        return icon_panel([('*' if stale else '',14,0,'#b9d8ef'),
            (f"{c['temperature_2m']:.0f}℃",30,80,'white')],kind)
    async def close(self):
        if self.task and not self.task.done():
            self.task.cancel(); await asyncio.gather(self.task,return_exceptions=True)


class LaundryWidget(Widget):
    def __init__(self,config,weather=None):
        super().__init__(config);self.weather=weather
    def render(self):
        w=self.weather
        result=assess_laundry(w.data,w.config.get('laundry',{})) if w and w.data else None
        target=result.target if result else laundry_window(datetime.now())[0]
        grade='?' if w is None or w.data is None or w.failed or time.monotonic()-w.fetched>1800 else result.grade
        return icon_panel([(target+' '+grade,27,85,'#ffe29b')],'laundry')


class AppLauncherAction(Widget):
    def __init__(self, config, opener=None):
        super().__init__(config);self.settings=LauncherSettings.from_config(config)
        self.opener=opener or open_target;self.message='';self.until=0
    @property
    def configured(self):return self.settings.configured
    def render(self):
        text=self.message if time.monotonic()<self.until else '▶' if self.configured else '未設定'
        icon=self.settings.icon_path
        if icon:
            lines=[] if text=='▶' and self.settings.icon_only else [(self.settings.label if text=='▶' else text,23,88,'white')]
            return icon_panel(lines,'app_only' if not lines else 'app',expand_target(icon))
        return icon_panel([(self.settings.label,20,86,'white'),(text,14,111,'#b9d8ef')],'launcher')
    async def press(self):
        if time.monotonic()<self.until: return
        if not self.configured:
            self.message='起動先を設定';self.until=time.monotonic()+2;return
        try:
            await asyncio.to_thread(self.opener,expand_target(self.settings.target))
            self.message='起動しました'
        except Exception: self.message='起動できません'
        self.until=time.monotonic()+2


REGISTRY={'clock':ClockWidget,'weather':WeatherWidget,'laundry':LaundryWidget,'app_launcher':AppLauncherAction}
DEFAULT_ITEMS=[{'cell':0,'type':'clock'}, {'cell':1,'type':'weather'},
               {'cell':2,'type':'laundry'},
               *[{'cell':cell,'type':'app_launcher','label':'APP '+str(cell-2),'target':''} for cell in (3,4,5)]]


class DesktopHome:
    def __init__(self, config=None, registry=None):
        config=config or {}; registry=registry or REGISTRY; self.widgets={}; self.last_refresh=0; self.cached=None; self.detail_input=0; self.feedback="";self.feedback_until=0; self.nav=DesktopNavigation()
        page_configs=config.get('pages',[{'items':config.get('items',DEFAULT_ITEMS)}])
        if not isinstance(page_configs,list) or not page_configs:raise ValueError('Desktop requires at least one page')
        self.nav.pages=max(1,len(page_configs));self.page_widgets=[]
        for page in page_configs:
            self.widgets={}
            for item in page.get('items',[]):
                cell=item['cell']
                if type(cell) is not int or not 0<=cell<6 or cell in self.widgets:raise ValueError('Invalid or duplicate desktop cell')
                kind=item['type']
                if kind not in registry:raise ValueError('Unknown desktop widget: '+kind)
                values=dict(config.get(kind,{}));values.update(item)
                self.widgets[cell]=registry[kind](values)
            weather=next((w for w in self.widgets.values() if isinstance(w,WeatherWidget)),None)
            for widget in self.widgets.values():
                if isinstance(widget,LaundryWidget):widget.weather=weather
            self.page_widgets.append(self.widgets)
        self.widgets=self.page_widgets[0]
        self.blank=panel([])
    @property
    def detail(self):return self.nav.screen
    def home(self):
        self.nav.home();self.widgets=self.page_widgets[self.nav.page];self.cached=None
    def page(self,delta):
        self.nav.move(delta);self.widgets=self.page_widgets[self.nav.page];self.cached=None
    def show_feedback(self,text):
        self.feedback=text;self.feedback_until=time.monotonic()+2.5;self.cached=None
    def frame(self):
        images=list(self.render())
        if self.detail is None and self.feedback and time.monotonic()<self.feedback_until:
            cell=next((i for i in reversed(range(6)) if i not in self.widgets or
                       isinstance(self.widgets[i],AppLauncherAction) and not self.widgets[i].configured),None)
            if cell is not None:images[cell]=panel([(self.feedback,32,40,'white')])
        return images
    def render(self):
        if self.detail is not None and time.monotonic()-self.detail_input>=30:self.back()
        if self.cached is not None and time.monotonic()-self.last_refresh<1: return self.cached
        if self.detail is not None:
            from .desktop_details import detail_cards
            widget=self.widgets[self.detail]
            weather=widget.weather if isinstance(widget,LaundryWidget) else widget
            if weather:weather.request()
            try:result=detail_cards(weather,'laundry' if isinstance(widget,LaundryWidget) else 'weather')
            except Exception:result=[panel([('予報取得待ち',20,45,'white')])]*6
            self.cached=result;self.last_refresh=time.monotonic();return result
        result=[self.blank]*6
        for cell,widget in self.widgets.items():
            try: widget.request();result[cell]=widget.render()
            except Exception: result[cell]=panel([('表示エラー',20,45,'white')])
        self.cached=result;self.last_refresh=time.monotonic()
        return result
    def back(self):
        self.nav.back();self.widgets=self.page_widgets[self.nav.page];self.cached=None
    async def press(self,cell):
        if self.detail is not None:
            self.back();return
        widget=self.widgets.get(cell)
        if isinstance(widget,(WeatherWidget,LaundryWidget)):
            self.nav.open(cell);self.detail_input=time.monotonic()
        elif widget:await widget.press()
        self.cached=None
    async def close(self):
        for page in self.page_widgets:
            for widget in page.values():await widget.close()
