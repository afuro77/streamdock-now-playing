import unittest,sys,asyncio,json,base64,io,tempfile
from pathlib import Path
from PIL import Image
from streamdock_now_playing.streamdock import Plugin
from streamdock_now_playing.renderer import tiles
class FakeWS:
 def __init__(self):self.messages=[]
 async def send(self,s):self.messages.append(json.loads(s))
class FakeMedia:
 def __init__(self):self.calls=[];self.fallback=False;self.preferred='spotify'
 async def command(self,name,amount=1):self.calls.append((name,amount));return name
class Tests(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.directory=temp.name
 def test_tile_order_and_shape(self):
  im=Image.new('RGB',(384,256)); colors=['red','green','blue','yellow','cyan','magenta']
  for n,c in enumerate(colors):im.paste(c,(n%3*128,n//3*128,(n%3+1)*128,(n//3+1)*128))
  b=io.BytesIO();im.save(b,'PNG');result=tiles(b.getvalue());self.assertEqual(len(result),6)
  for n,encoded in enumerate(result):
   tile=Image.open(io.BytesIO(base64.b64decode(encoded.split(',')[1])))
   self.assertEqual(tile.size,(128,128));self.assertEqual(tile.getpixel((64,64)),im.getpixel((n%3*128+64,n//3*128+64)))
 async def test_host_events_and_restore(self):
  p=Plugin(provider=FakeMedia(),data_dir=self.directory,config={});p.ws=FakeWS();p.provider=FakeMedia()
  for n in range(6):await p.event(dict(event='willAppear',context=str(n),action='local.ajazz.media.tile',payload={'settings':{'tile':n}}))
  self.assertEqual(len([m for m in p.ws.messages if m['event']=='setImage']),6)
  before=len(p.ws.messages);await p.render();self.assertEqual(len(p.ws.messages),before)
  for role in ['volume','tracks','seek','mode','back']:
   await p.event(dict(event='willAppear',context=role,action='local.ajazz.media.'+role,payload={}))
  for role,event,payload in [('volume','dialDown',{}),('volume','dialRotate',{'ticks':-2}),('tracks','dialRotate',{'ticks':1}),('tracks','dialRotate',{'ticks':-1}),('tracks','dialDown',{}),('seek','dialRotate',{'ticks':2}),('seek','dialDown',{})]:
   await p.event(dict(event=event,context=role,payload=payload))
  self.assertEqual(p.provider.calls,[('play',1),('volume',-8),('next',1),('previous',1),('seek',10),('shuffle',1)])
  before=(len(p.ws.messages),list(p.provider.calls),p.overlay,p.until)
  await p.event(dict(event='dialDown',context='tracks',payload={}))
  self.assertEqual((len(p.ws.messages),p.provider.calls,p.overlay,p.until),before)
  self.assertGreater(p.until,0);p.until=0;await p.render()
  img=[m for m in p.ws.messages if m['event']=='setImage' and m['context']=='0'][-1]
  self.assertEqual(img['payload']['image'],p.images[0])
  await p.event(dict(event='willDisappear',context='0'));self.assertNotIn('0',p.contexts)
if __name__=='__main__':unittest.main()
