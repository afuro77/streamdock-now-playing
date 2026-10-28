# Playlist browser (DEV)

Spotify center key: short press (on release) opens Queue; hold 700ms opens Playlists. A completed long hold never also opens Queue on release. Desktop center behavior stays HOME. MODE invalidates pending holds.

Playlist view uses six LCD selection buttons, with name and page number. Left small dial moves previous/next page; its press does nothing in this view. BACK returns to the prior screen. Selecting a playlist starts that context on the currently active Spotify device and returns to Now Playing after API success. No active device, restricted device, non-Premium or API errors leave the browser available; playback is not transferred automatically. Other media controls remain available. Async completion cannot replace Desktop or a screen the user has already left.

Read endpoint: GET /me/playlists?limit=6&offset=N with playlist-read-private. It enumerates playlists owned/followed by the account; no fixed three-item limit. Pages load on demand, with 32 pages retained in process memory (not a limit on accessible playlist count). Spotify's endpoint caps offset at 100000. Six returned slots map to six LCDs; null/deleted items are not silently shifted into a different slot.

Play endpoint: PUT /me/player/play with JSON context_uri and existing user-modify-playback-state. No Client Secret. PKCE reauthorization is needed to grant playlist-read-private while preserving previous playback scopes. Until then Playlist view asks to reconnect; GSMTC, Queue and volume remain available. API read/play calls run in worker threads. Errors back off; repeated key presses cannot create duplicate playback tasks.

This is NOT Spotify's Home recommendation feed. Spotify does not provide an unrestricted endpoint for that feed; algorithmic/editorial playlists have access limitations. Saved/followed playlist metadata returned by /me/playlists is shown, but recommended playlist availability and playback are not guaranteed. No scraping or unofficial APIs are used.

Official references:
- https://developer.spotify.com/documentation/web-api/reference/get-a-list-of-current-users-playlists
- https://developer.spotify.com/documentation/web-api/reference/start-a-users-playback
- https://developer.spotify.com/blog/2024-11-27-changes-to-the-web-api
- https://developer.spotify.com/documentation/web-api/references/changes/february-2026

Validation before consent: 192 tests passed, including short/long input, pagination beyond three playlists, stale-page rejection, caches, missing scope/403/429/network handling, JSON playback request, media isolation, and mode-switch races. Real library retrieval and playback require the user's consent and hardware verification.

## Queue right-knob sliding
Queue preview now retains the full list returned by Spotify rather than truncating to three. The three-column text/cover layout remains. Right small dial rotation slides one track per tick: NEXT 1/2/3 → NEXT 2/3/4 → NEXT 3/4/5. Ends clamp; no extra queue entries are invented beyond the API response. Left small dial remains Previous/Next playback, and normal right-dial Seek stays unchanged. Selection uses the visible absolute index and URI; the existing fresh-queue recheck and confirmed sequential Next behavior remains. Covers are requested only for the three visible entries. API refresh/shrink clamps the viewport. No new scopes.

List knob consistency fix: Spotify Queue and Playlist browser both use RIGHT small dial for browsing. Queue slides one track per tick; Playlist advances one six-item page per tick. LEFT small dial retains Previous/Next playback in both screens. This supersedes the earlier playlist left-dial mapping.

## Three-playlist visual viewport
Latest layout: upper three LCDs show three playlist names; lower three show their corresponding full-aspect thumbnails. Press either text or image in a column to play that playlist. Right small dial slides by one playlist (1/2/3 → 2/3/4); left small dial retains Previous/Next playback. API still fetches six entries per request and reuses adjacent cached entries across viewport movement; 32 API chunks retained, no three-playlist library cap. Visible image downloads run off the event loop with bounded QueueArtwork cache and trusted hosts; missing images display NO COVER without disabling selection. Live library check returned 40 total, three visible, two thumbnail downloads succeeded in the first viewport. No playback was changed by verification. 202 tests passed.

## Local recommended-playlist bookmark
Runtime config playlist_bookmarks is a list of {id,name,image_url}. The registered Discover Weekly ID is stored only in local configuration. Local bookmarks are prepended to the existing library list without following or saving them on Spotify. Spotify official oEmbed supplies title/thumbnail in a worker, cached for an hour; fallback configured values keep the entry usable if metadata fails. Image downloader additionally allows the exact official pickasso.spotifycdn.com host (HTTPS only). Playback uses the existing Web API context_uri with offset.position=0 and position_ms=0 to explicitly start the playlist. Failures show PLAY plus HTTP status and are logged without credentials. Some playlists may be restricted independently of metadata availability; no unauthorized retrieval or scraping is attempted.

Live verification: Discover Weekly appears first, image downloads successfully, combined total is 41 (1 local bookmark + 40 library playlists). Starting the selected URI was accepted and playback context was confirmed to match. This does not establish that every other playlist can be played. The previously reported hardware-selection failure cannot be retrospectively diagnosed from logs that did not record API results.

## CastAudio playlist start fix
Live reproduction on CastAudio (not restricted, correct write scope) showed PUT /me/player/play with context_uri + offset.position=0 + position_ms=0 returned 403 "Player command failed: Restriction violated". An otherwise identical request containing ONLY context_uri returned 204. Removed forced initial offset/position; this supersedes the earlier first-position workaround. Do not infer missing Premium/scopes from every 403. Exact playback start position is now delegated to Spotify/device behavior. No device transfer or library writes performed.

Recommended bookmarks only: DEV runtime playlist_bookmarks_only=true. Playlist browser shows ONLY registered local recommended-playlist bookmarks; does not call /me/playlists and does not merge the user's library. Currently one registered entry (Discover Weekly). More entries require links; no automatic Home recommendation discovery is implied. Saved Spotify playlists are untouched. Empty local bookmarks yield an empty list, not a library fallback.
