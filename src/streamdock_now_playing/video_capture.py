"""Opt-in, loopback-only browser screen-share receiver. Latest frame only."""
import io
import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from PIL import Image
from .renderer import LayoutRenderer

PAGE = r'''<!doctype html><meta charset="utf-8"><title>AKP03J Video</title>
<style>body{background:#14212b;color:white;font:18px sans-serif;max-width:900px;margin:32px auto}button{padding:14px;font-size:20px}canvas{width:100%;cursor:crosshair;border:1px solid #789;touch-action:none}small{color:#bcd}</style>
<h1>AKP03J 動画表示（試験版）</h1>
<p>① YouTubeをシアターモードにする → ②「タブを共有」でYouTubeタブを選ぶ → ③ 下のプレビューで動画部分をドラッグ。</p>
<button id="start">タブを共有</button> <button id="stop">停止</button> <button id="reset">切り抜き解除</button>
<p id="status">共有していません</p><canvas id="preview" width="768" height="432"></canvas>
<p><small>YouTube Modeで画像LCDを押すと6枚に動画表示。毎秒約2コマ・音声転送なし。枠をドラッグして動画だけ切り抜けます。共有中はこのタブを開いたままにしてください。選択した映像はこのPC内だけで処理し、ファイル保存しません。</small></p>
<video id="source" autoplay muted playsinline hidden></video>
<script>
const token=location.hash.slice(1);history.replaceState(null,'',location.pathname);
const headers={'X-Capture-Token':token};
const v=document.querySelector('#source'),p=document.querySelector('#preview'),pc=p.getContext('2d');
const out=document.createElement('canvas');out.width=384;out.height=256;const ctx=out.getContext('2d');
const label=document.querySelector('#status');let stream=null,timer=null,crop=null,point=null,busy=false;
function xy(e){const r=p.getBoundingClientRect();return [Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)),Math.max(0,Math.min(1,(e.clientY-r.top)/r.height))]}
p.onpointerdown=e=>{point=xy(e);p.setPointerCapture(e.pointerId)};
p.onpointerup=e=>{if(!point)return;const end=xy(e);let x=Math.min(point[0],end[0]),y=Math.min(point[1],end[1]),w=Math.abs(end[0]-point[0]),h=Math.abs(end[1]-point[1]);if(w>.02&&h>.02)crop=[x,y,w,h];point=null};
document.querySelector('#reset').onclick=()=>crop=null;
async function stop(){clearInterval(timer);timer=null;if(stream)stream.getTracks().forEach(t=>t.stop());stream=null;v.srcObject=null;await fetch('/stop',{method:'POST',headers}).catch(()=>{});label.textContent='停止しました'}
document.querySelector('#stop').onclick=stop;
document.querySelector('#start').onclick=async()=>{try{
 await stop();stream=await navigator.mediaDevices.getDisplayMedia({video:{frameRate:2},audio:false,selfBrowserSurface:'exclude',surfaceSwitching:'exclude'});
 const track=stream.getVideoTracks()[0];if(track.getSettings().displaySurface!=='browser'){await stop();label.textContent='画面やウィンドウではなく、Chromeタブを選んでください';return}
 track.onended=stop;v.srcObject=stream;await v.play();timer=setInterval(tick,500);await tick();
}catch(e){label.textContent='共有開始できません: '+e.name}};
async function tick(){if(busy||!stream||!v.videoWidth)return;busy=true;try{
 pc.drawImage(v,0,0,p.width,p.height);if(crop){pc.strokeStyle='#00ffb0';pc.lineWidth=3;pc.strokeRect(crop[0]*p.width,crop[1]*p.height,crop[2]*p.width,crop[3]*p.height)}
 const state=await fetch('/state',{headers}).then(r=>{if(!r.ok)throw Error('接続を開き直してください');return r.json()});
 if(!state.enabled){label.textContent='待機中：YouTube Modeで画像LCDを押してください';return}
 const c=crop||[0,0,1,1],sw=c[2]*v.videoWidth,sh=c[3]*v.videoHeight;
 const scale=Math.min(384/sw,256/sh),w=sw*scale,h=sh*scale;
 ctx.fillStyle='black';ctx.fillRect(0,0,384,256);ctx.drawImage(v,c[0]*v.videoWidth,c[1]*v.videoHeight,sw,sh,(384-w)/2,(256-h)/2,w,h);
 const blob=await new Promise(resolve=>out.toBlob(resolve,'image/jpeg',.65));
 const response=await fetch('/frame',{method:'POST',headers:{...headers,'Content-Type':'image/jpeg'},body:blob});
 label.textContent=response.ok?'LCDに動画転送中（約2 fps）':'待機中';
}catch(e){label.textContent='転送エラー: '+e.message}finally{busy=false}}
addEventListener('pagehide',()=>{if(stream)stream.getTracks().forEach(t=>t.stop())});
</script>'''


class VideoCapture:
    def __init__(self, enabled, port=8766, clock=time.monotonic,browser=None):
        self.enabled=enabled;self.port=port;self.clock=clock
        self.browser=browser
        self.token=secrets.token_urlsafe(32);self.server=None;self.thread=None
        self.lock=threading.Lock();self.frames=None;self.received=0;self.count=0
        self.target_fps=12
        self.measurement_instance=secrets.token_hex(8)
        self.sources={'share':0,'extension':0};self.stage='not-seen';self.last_error=''

    def diagnostics(self):
        with self.lock:
            now=self.clock();enabled=bool(self.enabled())
            return {'sources':dict(self.sources),'extension_stage':self.stage,'last_error':self.last_error,'target_fps':self.target_fps,
                    'sample_time':now,'instance':self.measurement_instance,'enabled':enabled,
                    'fresh':enabled and self.frames is not None and now-self.received<2}

    def diagnose(self,stage):
        allowed=('not-selected','waiting-view','ready','no-video','read-error','sent','send-error')
        if stage not in allowed:raise ValueError('Unknown diagnostic stage')
        with self.lock:
            self.stage=stage
            if stage in ('read-error','send-error'):self.last_error=stage

    def clear(self):
        with self.lock:self.frames=None;self.received=0

    def latest(self):
        with self.lock:
            return self.frames if self.enabled() and self.clock()-self.received<2 else None

    def accept(self,data,source='share',target_fps=None):
        if source not in self.sources:raise ValueError('Unknown frame source')
        if target_fps is not None and (type(target_fps) is not int or target_fps not in (4,6,8,10,12,15,20,24,30,40,45,50,60,75,90,120)):raise ValueError('Invalid target frame rate')
        if not self.enabled():return False
        if len(data)>200_000:raise ValueError('Frame too large')
        with Image.open(io.BytesIO(data)) as image:
            if image.format!='JPEG' or image.size!=(384,256):raise ValueError('Expected 384x256 JPEG')
            image.load()
        frames=LayoutRenderer().expanded_artwork(data)
        with self.lock:
            if not self.enabled():return False
            self.frames=frames;self.received=self.clock();self.count+=1
            if source=='extension' and target_fps is not None:self.target_fps=target_fps
            self.sources[source]+=1
        return True

    def start(self):
        receiver=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def reply(self,status,data=b'',kind='text/plain; charset=utf-8'):
                self.send_response(status);self.send_header('Content-Type',kind)
                self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer')
                self.send_header('X-Frame-Options','DENY');self.send_header('Content-Length',str(len(data)));self.end_headers()
                self.wfile.write(data)
            def authorized(self):
                return secrets.compare_digest(self.headers.get('X-Capture-Token',''),receiver.token)
            def do_GET(self):
                if self.headers.get('Host')!=f'127.0.0.1:{receiver.port}':self.reply(403);return
                if self.path=='/':self.reply(200,PAGE.encode(),'text/html; charset=utf-8')
                elif self.path=='/state' and self.authorized():self.reply(200,json.dumps({'enabled':bool(receiver.enabled()),**(receiver.browser.state() if receiver.browser else {})}).encode(),'application/json')
                elif self.path=='/diagnostics' and self.authorized():self.reply(200,json.dumps(receiver.diagnostics()).encode(),'application/json')
                else:self.reply(403)
            def do_POST(self):
                if not self.authorized() or self.headers.get('Host')!=f'127.0.0.1:{receiver.port}':self.reply(403);return
                if self.path=='/stop':receiver.clear();self.reply(204);return
                if self.path in ('/browser/catalog','/browser/ack','/browser/register','/browser/current') and receiver.browser:
                    try:
                        length=int(self.headers.get('Content-Length','0'))
                        if not 0<length<=160000:self.reply(413);return
                        self.connection.settimeout(2);data=json.loads(self.rfile.read(length))
                        if not isinstance(data,dict):raise ValueError('Expected object')
                        methods={'/browser/catalog':receiver.browser.publish,'/browser/ack':receiver.browser.acknowledge,'/browser/register':receiver.browser.register,'/browser/current':receiver.browser.register_channel}
                        ok=methods[self.path](data)
                        self.reply(204 if ok else 409)
                    except (ValueError,OSError,AttributeError):self.reply(400)
                    return
                if self.path=='/diagnostic':
                    try:
                        length=int(self.headers.get('Content-Length','0'))
                        if not 0<length<=512:self.reply(413);return
                        self.connection.settimeout(2)
                        receiver.diagnose(json.loads(self.rfile.read(length)).get('stage'));self.reply(204)
                    except (ValueError,OSError,AttributeError):self.reply(400)
                    return
                if self.path!='/frame':self.reply(404);return
                try:
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<length<=200_000:self.reply(413);return
                    self.connection.settimeout(2)
                    fps=self.headers.get('X-Target-Fps')
                    ok=receiver.accept(self.rfile.read(length),self.headers.get('X-Frame-Source','share'),int(fps) if fps is not None else None);self.reply(204 if ok else 409)
                except (ValueError,OSError):self.reply(400)
        self.server=ThreadingHTTPServer(('127.0.0.1',self.port),Handler)
        self.server.daemon_threads=True;self.port=self.server.server_port
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        return f'http://127.0.0.1:{self.port}/#{self.token}'

    def close(self):
        self.clear()
        if self.server:self.server.shutdown();self.server.server_close();self.server=None
