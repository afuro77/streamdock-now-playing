"""Reach the selected queue URI using confirmed, sequential GSMTC Next calls."""
import asyncio
import time


class QueueSelectionError(Exception): pass


class QueueNavigator:
    def __init__(self, client, command, poll_interval=.2, timeout=5):
        self.client=client;self.command=command
        self.poll_interval=poll_interval;self.timeout=timeout

    async def select(self, target_uri, on_step=None):
        if not target_uri: raise QueueSelectionError('REFRESH QUEUE')
        fresh=await asyncio.to_thread(self.client.queue)
        index=next((i for i,item in enumerate(fresh) if item.get('uri')==target_uri),None)
        if index is None: raise QueueSelectionError('QUEUE CHANGED')
        current=await asyncio.to_thread(self.client.playback)
        current_uri=(current.get('item') or {}).get('uri')
        device_id=(current.get('device') or {}).get('id')
        if not current_uri: raise QueueSelectionError('PLAYER UNKNOWN')
        path=[item.get('uri') for item in fresh[:index+1]]
        # A repeated identical URI cannot be confirmed from a track change.
        if any(not uri for uri in path) or len(set([current_uri]+path))!=len(path)+1:
            raise QueueSelectionError('QUEUE AMBIGUOUS')
        steps=0
        for expected in path:
            result=await asyncio.wait_for(self.command('next',1),5)
            if str(result).upper()!='NEXT':raise QueueSelectionError(str(result))
            steps+=1
            if on_step:on_step(steps)
            deadline=time.monotonic()+self.timeout
            while True:
                await asyncio.sleep(self.poll_interval)
                state=await asyncio.to_thread(self.client.playback)
                active=(state.get('device') or {}).get('id')
                if device_id and active and device_id!=active:
                    raise QueueSelectionError('PLAYER CHANGED')
                actual=(state.get('item') or {}).get('uri')
                if actual==expected:break
                if time.monotonic()>=deadline:
                    raise QueueSelectionError('QUEUE CHANGED' if actual and actual!=current_uri else 'SKIP NOT CONFIRMED')
            current_uri=expected
        return steps
