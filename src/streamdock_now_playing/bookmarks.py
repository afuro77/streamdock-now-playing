"""Local-only playlist bookmarks. No Spotify library write endpoints."""
import json,re,time
from urllib.parse import urlencode
from urllib.request import urlopen


def oembed(playlist_id):
    url='https://open.spotify.com/oembed?'+urlencode({'url':'https://open.spotify.com/playlist/'+playlist_id})
    with urlopen(url,timeout=6) as response:
        raw=response.read(512*1024+1)
    if len(raw)>512*1024:raise ValueError('Metadata too large')
    return json.loads(raw)


class BookmarkPlaylists:
    def __init__(self,client,entries,fetcher=oembed,include_library=True):
        self.client=client;self.fetcher=fetcher;self.entries=[];self.cache={};self.include_library=include_library
        for entry in entries:
            pid=entry.get('id','')
            if not re.fullmatch(r'[A-Za-z0-9]{22}',pid):raise ValueError('Invalid bookmark playlist id')
            self.entries.append(dict(entry))
    def bookmark(self,entry):
        pid=entry['id'];cached=self.cache.get(pid)
        if cached and time.monotonic()-cached[0]<3600:return cached[1]
        name=entry.get('name') or 'Playlist';url=entry.get('image_url','')
        try:
            data=self.fetcher(pid);name=data.get('title') or name;url=data.get('thumbnail_url') or url
        except Exception:pass
        item={'id':pid,'name':name,'uri':'spotify:playlist:'+pid,'images':[{'url':url}] if url else [],'local_bookmark':True}
        self.cache[pid]=(time.monotonic(),item);return item
    def playlists(self,offset=0):
        count=len(self.entries);local=[self.bookmark(e) for e in self.entries[offset:offset+6]] if offset<count else []
        if not self.include_library:return {'items':local,'total':count,'offset':offset}
        try:
            data=self.client.playlists(max(0,offset-count))
            remote=data.get('items') or [];total=int(data.get('total') or 0)
        except Exception:
            if not local:raise
            remote=[];total=0
        return {'items':(local+remote)[:6],'total':count+total,'offset':offset}
