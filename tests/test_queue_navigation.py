import asyncio
import unittest
from streamdock_now_playing.queue_navigation import QueueNavigator, QueueSelectionError


class Client:
    def __init__(self,tracks=('one','two','three'),lag=1):
        self.tracks=list(tracks);self.current='original';self.pending=None
        self.polls=0;self.lag=lag;self.calls=[];self.device='device'
    def queue(self):return [{'uri':uri,'title':uri} for uri in self.tracks]
    def playback(self):
        if self.pending:
            self.polls+=1
            if self.polls>=self.lag:self.current=self.pending;self.pending=None
        return {'item':{'uri':self.current},'device':{'id':self.device}}
    async def command(self,name,amount):
        if self.pending:raise AssertionError('Next arrived before prior track switch')
        self.calls.append(name);self.pending=self.tracks.pop(0);self.polls=0
        return 'NEXT'


class ConfirmedSelectionTests(unittest.IsolatedAsyncioTestCase):
    async def test_third_song_waits_for_each_delayed_switch(self):
        c=Client(lag=3);nav=QueueNavigator(c,c.command,poll_interval=.001,timeout=.2)
        self.assertEqual(await nav.select('three'),3)
        self.assertEqual(c.current,'three');self.assertEqual(c.calls,['next']*3)

    async def test_refreshed_queue_uses_selected_id_not_old_column_number(self):
        c=Client(('three',));nav=QueueNavigator(c,c.command,poll_interval=.001)
        self.assertEqual(await nav.select('three'),1)
        self.assertEqual(c.current,'three');self.assertEqual(c.calls,['next'])

    async def test_removed_selection_does_not_skip_other_tracks(self):
        c=Client(('other',));nav=QueueNavigator(c,c.command)
        with self.assertRaisesRegex(QueueSelectionError,'QUEUE CHANGED'):await nav.select('three')
        self.assertEqual(c.calls,[])

    async def test_unconfirmed_first_step_never_sends_second_or_third(self):
        c=Client(lag=1000);nav=QueueNavigator(c,c.command,poll_interval=.001,timeout=.01)
        with self.assertRaisesRegex(QueueSelectionError,'SKIP NOT CONFIRMED'):await nav.select('three')
        self.assertEqual(c.calls,['next'])

    async def test_unexpected_song_never_causes_more_blind_skips(self):
        c=Client()
        async def wrong(name,amount):c.calls.append(name);c.current='unexpected';return 'NEXT'
        nav=QueueNavigator(c,wrong,poll_interval=.001,timeout=.01)
        with self.assertRaisesRegex(QueueSelectionError,'QUEUE CHANGED'):await nav.select('three')
        self.assertEqual(c.calls,['next'])

    async def test_identical_repeated_tracks_are_not_blindly_counted(self):
        c=Client(('one','one','three'));nav=QueueNavigator(c,c.command)
        with self.assertRaisesRegex(QueueSelectionError,'AMBIGUOUS'):await nav.select('three')
        self.assertEqual(c.calls,[])

    async def test_device_change_aborts_selection(self):
        c=Client()
        async def changed(name,amount):c.calls.append(name);c.device='different';return 'NEXT'
        nav=QueueNavigator(c,changed,poll_interval=.001)
        with self.assertRaisesRegex(QueueSelectionError,'PLAYER CHANGED'):await nav.select('three')
        self.assertEqual(c.calls,['next'])
