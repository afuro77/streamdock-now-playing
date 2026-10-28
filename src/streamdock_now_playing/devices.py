"""Optional Spotify Connect device selection; all network work is asynchronous."""
import asyncio,time
from .desktop import panel

class DeviceBrowser:
    def __init__(self,client):
        self.client=client;self.items=[];self.page=0;self.message='Loading…';self.task=None;self.updated=0;self.retry_at=0;self.switching=False;self.cached=None;self.key=None
    def request(self,force=False):
        if self.switching or (self.task and not self.task.done()) or time.monotonic()<self.retry_at:return
        if not force and self.updated and time.monotonic()-self.updated<10:return
        self.task=asyncio.create_task(self.refresh())
    async def refresh(self):
        try:
            rows=await asyncio.to_thread(self.client.devices)
            self.items=[dict(x) for x in rows if isinstance(x,dict)]
            self.items.sort(key=lambda x:not x.get('is_active'))
            self.updated=time.monotonic();self.page=min(self.page,max(0,(len(self.items)-1)//6));self.message='' if self.items else 'No devices'
        except asyncio.CancelledError:raise
        except Exception as error:
            self.items=[];self.message='API '+str(getattr(error,'status',None) or 'ERROR');self.retry_at=time.monotonic()+max(15,getattr(error,'retry_after',0))
    def move(self,ticks):self.page=max(0,min(max(0,(len(self.items)-1)//6),self.page+ticks))
    def selected(self,cell):
        i=self.page*6+cell
        if not 0<=cell<6 or i>=len(self.items) or self.switching:return None
        row=self.items[i]
        return row.get('id') if not row.get('is_restricted') else None
    def render(self):
        key=repr((self.items,self.page,self.message))
        if key==self.key:return self.cached
        result=[]
        for cell in range(6):
            i=self.page*6+cell
            if i>=len(self.items):result.append(panel([(self.message if cell==0 else '',20,45,'white')]));continue
            d=self.items[i];name=str(d.get('name') or 'Device');lines=[name[i:i+10] for i in range(0,min(len(name),30),10)]
            if len(name)>30:lines[-1]=lines[-1][:-1]+'…'
            tag='ACTIVE' if d.get('is_active') else 'LOCKED' if d.get('is_restricted') or not d.get('id') else str(d.get('type') or 'DEVICE').upper()
            entries=[(tag,16,2,'#73d8cb' if d.get('is_active') else '#b9d8ef')]+[(s,24,28+n*25,'white') for n,s in enumerate(lines)]
            entries.append((self.message if cell==0 and self.message else f'{i+1}/{len(self.items)}',14,108,'#b9d8ef'))
            result.append(panel(entries))
        self.key=key;self.cached=result;return result
    async def transfer(self,device_id):
        if self.switching:return False
        self.switching=True;self.message='SWITCHING'
        try:
            if self.task and not self.task.done():await self.task
            devices=await asyncio.to_thread(self.client.devices)
            target=next((d for d in devices if d.get('id')==device_id),None)
            if not target or target.get('is_restricted'):
                self.message='Unavailable';return False
            if not target.get('is_active'):await asyncio.to_thread(self.client.transfer_playback,device_id)
            deadline=time.monotonic()+10
            while True:
                state=await asyncio.to_thread(self.client.playback) or {}
                if (state.get('device') or {}).get('id')==device_id:
                    self.items=await asyncio.to_thread(self.client.devices);self.updated=time.monotonic();self.message='CONNECTED';return True
                if time.monotonic()>=deadline:self.message='Not confirmed';return False
                await asyncio.sleep(.7)
        except asyncio.CancelledError:raise
        except Exception as error:
            self.message='API '+str(getattr(error,'status',None) or 'ERROR');self.retry_at=time.monotonic()+max(15,getattr(error,'retry_after',0));return False
        finally:self.switching=False
    async def close(self):
        if self.task and not self.task.done():self.task.cancel();await asyncio.gather(self.task,return_exceptions=True)
