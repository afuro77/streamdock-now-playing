"""Optional artist popular tracks from public embed HTML (unstable schema)."""
import json,re,time,unicodedata
from html.parser import HTMLParser
from urllib.request import urlopen
from urllib.parse import urlencode
from .playlists import PlaylistBrowser

class PageData(HTMLParser):
    def __init__(self):super().__init__();self.capture=False;self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag=='script':self.capture=dict(attrs).get('id')=='__NEXT_DATA__'
    def handle_endtag(self,tag):
        if tag=='script':self.capture=False
    def handle_data(self,data):
        if self.capture:self.parts.append(data)

def parse_tracks(html,artist_id):
    parser=PageData();parser.feed(html)
    entity=json.loads(''.join(parser.parts))['props']['pageProps']['state']['data']['entity']
    if entity.get('uri')!='spotify:artist:'+artist_id:raise ValueError('Artist mismatch')
    result=[]
    for row in entity.get('trackList') or []:
        uri=row.get('uri','')
        if not re.fullmatch(r'spotify:track:[A-Za-z0-9]{22}',uri) or row.get('isPlayable') is False:continue
        result.append({'name':str(row.get('title') or 'Track'),'uri':uri,'images':[]})
    return result

def public_page(artist_id):
    with urlopen('https://open.spotify.com/embed/artist/'+artist_id,timeout=8) as r:
        if not r.geturl().startswith('https://open.spotify.com/'):raise ValueError('Unexpected redirect')
        raw=r.read(2*1024*1024+1)
    if len(raw)>2*1024*1024:raise ValueError('Page too large')
    return raw.decode('utf-8')

def track_image(uri):
    url='https://open.spotify.com/oembed?'+urlencode({'url':'https://open.spotify.com/track/'+uri.rsplit(':',1)[1]})
    with urlopen(url,timeout=5) as r:data=json.loads(r.read(512*1024))
    return data.get('thumbnail_url','')

class ArtistTracksSource:
    def __init__(self,artist_id,fetcher=public_page,image_fetcher=track_image):
        if not re.fullmatch(r'[A-Za-z0-9]{22}',artist_id):raise ValueError('Invalid artist')
        self.artist_id=artist_id;self.fetcher=fetcher;self.image_fetcher=image_fetcher;self.rows=None
    def playlists(self,offset=0):
        if self.rows is None:self.rows=parse_tracks(self.fetcher(self.artist_id),self.artist_id)
        rows=self.rows[offset:offset+6]
        for row in rows:
            if 'image_checked' not in row:
                try:
                    url=self.image_fetcher(row['uri']);row['images']=[{'url':url}] if url else []
                except Exception:pass
                row['image_checked']=True
        return {'items':rows,'total':len(self.rows),'offset':offset}

class ArtistBrowser:
    def __init__(self):self.cache={};self.browser=None;self.artist_id=None
    def open(self,artist_id):
        cached=self.cache.get(artist_id)
        if cached and time.monotonic()-cached[0]<900:self.browser=cached[1]
        else:
            self.browser=PlaylistBrowser(ArtistTracksSource(artist_id))
            if len(self.cache)>=16:self.cache.pop(next(iter(self.cache)))
            self.cache[artist_id]=(time.monotonic(),self.browser)
        self.artist_id=artist_id;self.browser.page=0;self.browser.loaded=None
    async def close(self):
        for _,browser in self.cache.values():await browser.close()

def resolve_artist(client,snapshot):
    """Resolve an exact GSMTC artist name when current playback is absent."""
    name=str(snapshot.get('artist') or '').strip()
    if not name:return None
    def normalized(value):return ' '.join(unicodedata.normalize('NFKC',value).casefold().split())
    data=client.request('GET','/search?'+urlencode({'q':name,'type':'artist','limit':10}))
    candidates=(data.get('artists') or {}).get('items') or []
    matches={a['id']:a for a in candidates if isinstance(a,dict) and re.fullmatch(r'[A-Za-z0-9]{22}',str(a.get('id') or '')) and normalized(str(a.get('name') or ''))==normalized(name)}
    if len(matches)==1:return next(iter(matches))
    # Localized GSMTC artist names may differ from catalogue artist names.
    # Resolve only when exact title and duration identify one artist group.
    title=str(snapshot.get('title') or '').strip();duration=snapshot.get('duration') or 0
    if not title or not duration:return None
    data=client.request('GET','/search?'+urlencode({'q':'track:'+title,'type':'track','limit':10}))
    groups=set()
    for track in (data.get('tracks') or {}).get('items') or []:
        if normalized(str(track.get('name') or ''))!=normalized(title):continue
        if abs((track.get('duration_ms') or 0)/1000-duration)>=4:continue
        ids=tuple(a.get('id') for a in track.get('artists') or [] if re.fullmatch(r'[A-Za-z0-9]{22}',str(a.get('id') or '')))
        if ids:groups.add(ids)
    return next(iter(groups))[0] if len(groups)==1 else None

def playback_uris(rows,selected):
    """Start at the selected entry and retain the entire popular-track list."""
    if not isinstance(rows,list):raise ValueError('Artist list is not ready')
    uris=[r.get('uri') for r in rows if isinstance(r,dict)]
    if selected not in uris:raise ValueError('Selection is no longer available')
    index=uris.index(selected)
    return uris[index:]+uris[:index]
