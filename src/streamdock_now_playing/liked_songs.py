"""Liked Songs entry and paginated library track adapter."""
class LikedFirst:
    def __init__(self,source):self.source=source
    def playlists(self,offset=0):
        try:data=self.source.playlists(max(0,offset-1))
        except Exception:
            # Network/metadata failure must not hide locally registered recommendations.
            entries=getattr(self.source,'entries',None)
            if isinstance(entries,list):
                rows=[{'name':e.get('name') or 'Playlist','uri':'spotify:playlist:'+e['id'],'images':[{'url':e['image_url']}] if e.get('image_url') else []} for e in entries]
                start=max(0,offset-1);data={'items':rows[start:start+6],'total':len(rows)}
            else:
                if offset:raise
                data={'items':[],'total':0}
        items=data.get('items') or []
        if offset==0:items=[{'name':'お気に入りの曲','uri':'local:liked-songs','liked':True,'images':[]}]+items
        return {'items':items[:6],'total':int(data.get('total') or 0)+1,'offset':offset}
class SavedTracks:
    def __init__(self,client):self.client=client
    def playlists(self,offset=0):
        data=self.client.saved_tracks(offset,6);items=[]
        for raw in data.get('items') or []:
            t=raw.get('track') or {};items.append({'name':t.get('name') or 'Unavailable','uri':t.get('uri') if t.get('is_playable') is not False else None,'images':(t.get('album') or {}).get('images') or []})
        return {'items':items,'total':data.get('total',0),'offset':offset}
