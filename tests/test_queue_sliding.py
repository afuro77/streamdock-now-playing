import asyncio,tempfile,unittest
from unittest.mock import Mock
from streamdock_now_playing.spotify import QueueState
from streamdock_now_playing.streamdock import Plugin
from test_behavior import FakeMedia,FakeWS

def items():return [{'title':str(i),'artist':'Artist','uri':'track:'+str(i)} for i in range(1,9)]

class SlidingQueueTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.p=Plugin(provider=FakeMedia(),data_dir=self.temp.name,config={});self.p.ws=FakeWS();self.p.view_mode='queue'
  self.p.queue_state.items=items();self.p.queue_state.request=Mock()
  for role in ('seek','tracks','tile'):
   self.p.contexts[role]={'role':role,'settings':{'tile':1}}
 async def event(self,role,event='dialRotate',ticks=1):await self.p.event({'event':event,'context':role,'payload':{'ticks':ticks}})
 async def asyncTearDown(self):
  if self.p.queue_state.artwork_task:await self.p.queue_state.artwork_task
 async def test_right_dial_slides_one_at_a_time_without_seek(self):
  await self.event('seek');self.assertEqual([i['title'] for i in self.p.queue_state.visible()],['2','3','4'])
  await self.event('seek');self.assertEqual([i['title'] for i in self.p.queue_state.visible()],['3','4','5'])
  await self.event('seek',ticks=-1);self.assertEqual(self.p.queue_state.offset,1)
  self.assertEqual(self.p.provider.calls,[])
 async def test_left_dial_still_next_previous(self):
  await self.event('tracks');await self.event('tracks',ticks=-1)
  self.assertEqual(self.p.provider.calls,[('next',1),('previous',1)])
 async def test_selection_uses_absolute_visible_uri(self):
  self.p.queue_state.offset=3
  seen=[]
  async def skip(count,uri):seen.append((count,uri))
  self.p.skip_queue=skip
  await self.event('tile','keyDown');await self.p.queue_skip_task
  self.assertEqual(seen,[(5,'track:5')])
 async def test_boundaries_and_shrinking_queue(self):
  self.p.queue_state.move(100);self.assertEqual(self.p.queue_state.offset,5)
  self.p.queue_state.items=items()[:2];self.assertEqual(len(self.p.queue_state.visible()),2);self.assertEqual(self.p.queue_state.offset,0)
 async def test_display_changes_absolute_numbers(self):
  r=self.p.queue_renderer
  self.assertNotEqual(r.render(items()[:3],'',0),r.render(items()[:3],'',3))
