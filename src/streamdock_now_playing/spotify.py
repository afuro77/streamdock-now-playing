import re
"""Optional Spotify API integration. No dependency on GSMTC or audio."""
import asyncio
import base64
import ctypes
from ctypes import wintypes
import hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from pathlib import Path
import secrets
import threading
import time
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit, parse_qs
from urllib.request import Request, urlopen
import webbrowser

SCOPES = 'user-read-currently-playing user-read-playback-state user-modify-playback-state playlist-read-private user-library-read'
REDIRECT_URI = 'http://127.0.0.1:8765/callback'


class SpotifyError(Exception):
    def __init__(self, message, retry_after=0, status=None):
        super().__init__(message)
        self.retry_after = retry_after
        self.status = status


def http_json(method, url, data=None, headers=None):
    request = Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urlopen(request, timeout=6) as response:
            body = response.read()
            return json.loads(body) if body else {}
    except HTTPError as error:
        if error.code == 429:
            try: delay = max(1, min(86400, float(error.headers.get('Retry-After', 60))))
            except (TypeError, ValueError): delay = 60
            raise SpotifyError('Rate limited (429)', delay) from None
        messages = {400: 'Spotify request rejected (400)', 404: 'No active Spotify device (404)', 401: 'Authorization expired; reconnect',
                    403: 'Access denied (403): check Premium / allowed users / scopes'}
        raise SpotifyError(messages.get(error.code, 'Spotify error ('+str(error.code)+')'), status=error.code) from None
    except (OSError, ValueError):
        raise SpotifyError('Spotify unavailable; try later', 30) from None


def protect(data, decrypt=False):
    """Windows DPAPI, current-user scope; token data never stored in plain text."""
    class Blob(ctypes.Structure):
        _fields_ = [('length', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    # All pointer parameters are passed explicitly; DPAPI allocates target data.
    if decrypt:
        ok = crypt.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target))
    else:
        ok = crypt.CryptProtectData(ctypes.byref(source), 'Streamdock Spotify', None, None, None, 1, ctypes.byref(target))
    if not ok:
        raise SpotifyError('Cannot access local credentials; reconnect')
    try: return ctypes.string_at(target.data, target.length)
    finally: kernel.LocalFree(ctypes.cast(target.data, ctypes.c_void_p))


class CredentialStore:
    def __init__(self, directory):
        self.path = Path(directory)/'spotify-credentials.bin'

    def load(self):
        if not self.path.exists(): return {}
        try: return json.loads(protect(self.path.read_bytes(), decrypt=True))
        except Exception: raise SpotifyError('Cannot read credentials; reconnect') from None

    def save(self, value):
        data = protect(json.dumps(value).encode())
        temporary = self.path.with_suffix('.tmp')
        temporary.write_bytes(data)
        temporary.replace(self.path)


def pkce_pair():
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()).rstrip(b'=').decode('ascii')
    return verifier, challenge


class SpotifyClient:
    def __init__(self, settings, directory, store=None, transport=None):
        self.settings = settings if isinstance(settings, dict) else {}
        self.store = store or CredentialStore(directory)
        self.transport = transport or http_json
        self.lock = threading.Lock()
        self.retry_at = 0

    def token_request(self, parameters):
        return self.transport('POST', 'https://accounts.spotify.com/api/token',
                              urlencode(parameters).encode(), {'Content-Type': 'application/x-www-form-urlencoded'})

    def save_response(self, response, old=None):
        value = dict(response)
        value['refresh_token'] = value.get('refresh_token') or (old or {}).get('refresh_token')
        if not value.get('access_token') or not value.get('refresh_token'):
            raise SpotifyError('Incomplete authorization; reconnect')
        value['expires_at'] = time.time()+float(value.get('expires_in', 3600))
        value['client_id'] = self.settings.get('client_id')
        value['scope'] = value.get('scope') or (old or {}).get('scope', '')
        self.store.save(value)
        return value

    def request(self, method, path, required_scope=None, body=None):
        with self.lock:
            if not self.settings.get('enabled'):
                raise SpotifyError('Spotify API disabled')
            if not self.settings.get('client_id'):
                raise SpotifyError('Spotify setup required')
            if time.monotonic() < self.retry_at:
                raise SpotifyError('Waiting before retry', self.retry_at-time.monotonic())
            try:
                credentials = self.store.load()
                if credentials.get('client_id') != self.settings['client_id'] or not credentials.get('refresh_token'):
                    raise SpotifyError('Spotify sign-in required')
                if required_scope and required_scope not in credentials.get('scope', '').split():
                    raise SpotifyError('Spotify permission: reconnect')
                if credentials.get('expires_at', 0) <= time.time()+60:
                    credentials = self.save_response(self.token_request({
                        'grant_type': 'refresh_token', 'refresh_token': credentials['refresh_token'],
                        'client_id': self.settings['client_id']}), credentials)
                try:
                    return self.transport(method, 'https://api.spotify.com/v1'+path,
                                          json.dumps(body).encode() if body is not None else None,
                                          {'Authorization': 'Bearer '+credentials['access_token'], **({'Content-Type':'application/json'} if body is not None else {})})
                except SpotifyError as error:
                    if error.status != 401: raise
                    credentials = self.save_response(self.token_request({
                        'grant_type': 'refresh_token', 'refresh_token': credentials['refresh_token'],
                        'client_id': self.settings['client_id']}), credentials)
                    return self.transport(method, 'https://api.spotify.com/v1'+path,
                                          json.dumps(body).encode() if body is not None else None,
                                          {'Authorization': 'Bearer '+credentials['access_token'], **({'Content-Type':'application/json'} if body is not None else {})})
            except SpotifyError as error:
                # Missing write permission must not disrupt read-only Queue.
                if required_scope and 'permission' in str(error): raise
                self.retry_at = time.monotonic()+max(15, error.retry_after)
                raise

    def playlists(self, offset=0):
        return self.request('GET','/me/playlists?'+urlencode({'limit':6,'offset':offset}),'playlist-read-private') or {}

    def saved_tracks(self,offset=0,limit=6):
        return self.request('GET','/me/tracks?'+urlencode({'limit':limit,'offset':offset}),'user-library-read') or {}

    def play_saved_selection(self,uri,offset):
        data=self.saved_tracks(offset,50);tracks=[x.get('track') or {} for x in data.get('items') or []]
        if not tracks or tracks[0].get('uri')!=uri:raise SpotifyError('Selection changed; reopen library')
        uris=[t.get('uri') for t in tracks if t.get('is_playable') is not False and t.get('uri')]
        if not uris or uris[0]!=uri:raise SpotifyError('Track unavailable')
        return self.play_tracks(uris)

    def play_playlist(self, uri):
        if not isinstance(uri,str) or not re.fullmatch(r'spotify:playlist:[A-Za-z0-9]+',uri):
            raise SpotifyError('Invalid playlist')
        return self.request('PUT','/me/player/play','user-modify-playback-state',body={'context_uri':uri})

    def play_tracks(self,uris):
        if not isinstance(uris,list) or not 1<=len(uris)<=100 or not all(isinstance(uri,str) and re.fullmatch(r'spotify:track:[A-Za-z0-9]{22}',uri) for uri in uris):raise SpotifyError('Invalid track list')
        return self.request('PUT','/me/player/play','user-modify-playback-state',body={'uris':uris})

    def play_track(self,uri):
        if not re.fullmatch(r'spotify:track:[A-Za-z0-9]{22}',uri):raise SpotifyError('Invalid track')
        return self.request('PUT','/me/player/play','user-modify-playback-state',body={'uris':[uri]})

    def queue(self):
        data = self.request('GET', '/me/player/queue')
        entries = []
        for item in (data.get('queue') or []):
            if not isinstance(item, dict): continue
            artists = item.get('artists') or []
            images = (item.get('album') or {}).get('images') or item.get('images') or []
            images = [i for i in images if isinstance(i,dict) and isinstance(i.get('url'),str)]
            image = min(images,key=lambda i: ((i.get('width') or 640)<128,abs((i.get('width') or 640)-128))) if images else {}
            entries.append({'title': str(item.get('name') or 'Unknown'),
                            'artist': ', '.join(a.get('name', '') for a in artists if isinstance(a, dict))
                                      or (item.get('show') or {}).get('name', ''),
                            'uri': item.get('uri', ''), 'image_url': image.get('url','')})
        return entries

    def playback(self):
        return self.request('GET', '/me/player')

    def devices(self):
        return self.request('GET', '/me/player/devices').get('devices') or []

    def transfer_playback(self,device_id):
        if not isinstance(device_id,str) or not device_id or len(device_id)>512:raise SpotifyError('Invalid device')
        return self.request('PUT','/me/player','user-modify-playback-state',body={'device_ids':[device_id]})

    def set_volume(self, device_id, volume):
        if not device_id or type(volume) is not int or not 0 <= volume <= 100:
            raise SpotifyError('Invalid volume target')
        path = '/me/player/volume?'+urlencode({'volume_percent': volume, 'device_id': device_id})
        self.request('PUT', path, 'user-modify-playback-state')



class QueueState:
    """Network runs off the device event loop. A single request at a time."""
    def __init__(self, client):
        self.client = client
        from .queue_artwork import QueueArtwork
        self.artwork = QueueArtwork(); self.artwork_task = None
        self.items = []
        self.offset=0
        self.message = 'Open Queue to load queue'
        self.updated = 0
        self.task = None

    def visible(self):
        self.offset=max(0,min(self.offset,max(0,len(self.items)-3)))
        return self.items[self.offset:self.offset+3]

    def move(self,delta):
        previous=self.offset
        self.offset=max(0,min(self.offset+delta,max(0,len(self.items)-3)))
        if self.offset!=previous:
            if self.artwork_task and not self.artwork_task.done():self.artwork_task.cancel()
            self.artwork_task=asyncio.create_task(self.load_covers(self.visible()))

    def request(self):
        if self.task and not self.task.done(): return
        if time.monotonic()-self.updated < 10: return
        self.task = asyncio.create_task(self.refresh())

    async def refresh(self):
        self.message = 'Loading queue...'
        try:
            self.items = await asyncio.to_thread(self.client.queue)
            self.message = '' if self.items else 'Queue is empty'
            if self.artwork_task and not self.artwork_task.done():self.artwork_task.cancel()
            self.artwork_task=asyncio.create_task(self.load_covers(self.visible()))
        except SpotifyError as error:
            self.items = []; self.message = str(error)
        except Exception:
            self.items = []; self.message = 'Spotify unavailable; try later'
        self.updated = time.monotonic()

    async def load_covers(self, items):
        async def load(item):
            cover=await asyncio.to_thread(self.artwork.load,item.get('image_url',''))
            if cover:item['cover']=cover
        await asyncio.gather(*(load(item) for item in items))



def parse_callback(path, state):
    parsed = urlsplit(path)
    parameters = parse_qs(parsed.query)
    states = parameters.get('state', [])
    if parsed.path != '/callback' or len(states) != 1 or not secrets.compare_digest(states[0], state):
        return None
    if parameters.get('error'): return {'error': True}
    codes = parameters.get('code', [])
    return {'code': codes[0]} if len(codes) == 1 and codes[0] else None


def authorize(settings, directory, opener=webbrowser.open):
    """Interactive PKCE helper; no token/code/URL is written to logs."""
    redirect = settings.get('redirect_uri', REDIRECT_URI)
    if redirect != REDIRECT_URI:
        raise SpotifyError('Register redirect URI '+REDIRECT_URI)
    if not settings.get('client_id'): raise SpotifyError('Client ID required')
    verifier, challenge = pkce_pair()
    state = secrets.token_urlsafe(32)
    result = {}
    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            received = parse_callback(self.path, state)
            if received is None:
                self.send_response(400); self.end_headers(); return
            result.update(received)
            self.send_response(200); self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Cache-Control', 'no-store'); self.end_headers()
            self.wfile.write(b'Response received. You can return to Codex to check the result.')
    with HTTPServer(('127.0.0.1', 8765), Callback) as server:
        server.timeout = .5
        url = 'https://accounts.spotify.com/authorize?'+urlencode({
            'client_id': settings['client_id'], 'response_type': 'code', 'redirect_uri': redirect,
            'scope': SCOPES, 'show_dialog': 'true', 'state': state, 'code_challenge_method': 'S256', 'code_challenge': challenge})
        opener(url)
        deadline = time.monotonic()+300
        while not result and time.monotonic() < deadline: server.handle_request()
    if result.get('error'): raise SpotifyError('Spotify authorization declined')
    if not result.get('code'): raise SpotifyError('Authorization timed out; run sign-in again')
    client = SpotifyClient(settings, directory)
    client.save_response(client.token_request({'client_id': settings['client_id'],
        'grant_type': 'authorization_code', 'code': result['code'], 'redirect_uri': redirect,
        'code_verifier': verifier}))


def main():
    from .runtime import data_directory, read_config
    directory = data_directory()
    result = {'ok': False, 'message': 'Awaiting Spotify authorization'}
    status = directory/'spotify-auth-status.json'
    status.write_text(json.dumps(result), encoding='utf-8')
    try:
        authorize(read_config(directory).get('spotify', {}), directory)
        result = {'ok': True, 'message': 'Spotify authorized'}
    except Exception as error:
        result = {'ok': False, 'message': str(error) if isinstance(error, SpotifyError) else 'Sign-in failed; check callback port and connection'}
    status.write_text(json.dumps(result), encoding='utf-8')


if __name__ == '__main__': main()
