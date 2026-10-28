# v1.2 stage 1: optional Spotify queue

Normal 4+2 rendering and all three knobs retain their v1.1 behavior.
Physical buttons now navigate: left HOME, middle BROWSE (Queue), right BACK.
The internal host action IDs remain `mode`, `player`, and `back` for profile
compatibility. BACK uses a navigation stack; HOME clears it. Queue LCD presses skip ahead through the existing GSMTC Next command: column
1 sends one Next, column 2 two, and column 3 three. Either tile in a column selects
that entry. Commands are sent sequentially with 350ms between accepted skips.
Duplicate presses are ignored while skipping; HOME/BACK cancels unsent skips.
A rejection stops the sequence. The queue is refreshed after playback settles.
No Spotify write API, extra OAuth scope, queue editing, or library API is used.

Queue: top LCDs show next 1/2/3 titles and artists; lower LCDs show corresponding full artwork.
The Spotify API connection remains read-only; selection uses local Next controls. Repeated queue entries are preserved. Empty queue and
sign-in/API errors are shown explicitly. HOME always restores Now Playing.

## Optional configuration

Add to the DEV runtime config, never the source checkout:

```json
{"spotify": {
  "enabled": true,
  "client_id": "YOUR_CLIENT_ID",
  "redirect_uri": "http://127.0.0.1:8765/callback"
}}
```

The example configuration disables Web API by default. Disabling it does not
prevent GSMTC/audio controls or navigation. Core media/audio modules are unchanged.

Register that exact redirect URI in the Spotify Dashboard, enable Web API, and
use an account permitted by the app's Development Mode allowlist. The app owner
needs Premium. No Client Secret is used or requested.

## Sign in

With the DEV Python environment, source on PYTHONPATH, and
STREAMDOCK_NOW_PLAYING_DATA_DIR pointing at the DEV runtime directory, run:

```
python -m streamdock_now_playing.spotify
```

A loopback-only HTTP callback listener opens first, then the browser opens the
Spotify authorization screen. Log in and approve the read-only permissions.
Do not open the callback URI manually. The helper waits up to five minutes.
Read `spotify-auth-status.json` in the runtime directory for the result; rerun
sign-in after a timeout or denial. It never writes codes, tokens, or auth URLs
to logs. Only these scopes are requested:

- user-read-currently-playing
- user-read-playback-state

PKCE uses S256, a fresh verifier and a validated random state. Tokens are stored
in `spotify-credentials.bin`, encrypted with Windows DPAPI for the current user.
Client ID resides only in local runtime config; no secret is needed. Credentials
are not portable to another Windows user. To disconnect, disable `spotify.enabled`,
restart DEV, remove the runtime credential file, and optionally revoke the app
in Spotify account settings. Stable v1 is independent.

## Isolation and retries

Queue HTTP and credential work runs in a worker thread, with six-second HTTP
timeouts, separate from the device event loop. At most one queue request runs at
a time. While Queue is open, data refreshes no faster than once every ten seconds;
HOME causes no further refresh requests. Entering BROWSE may reuse recent data.
Expired access tokens refresh automatically; a 401 causes one refresh/retry.
Invalid/revoked refresh credentials require signing in again. 403 is reported;
429 honors Retry-After and applies backoff. Errors clear the displayed queue so
old entries are not represented as current. API outages do not change the GSMTC
provider or affect Windows Audio Session controls. In-flight requests may finish
after returning HOME, but cannot change the active screen.

References:
- https://developer.spotify.com/documentation/web-api/tutorials/code-pkce-flow
- https://developer.spotify.com/documentation/web-api/reference/get-queue
- https://developer.spotify.com/documentation/web-api/concepts/redirect_uri

Selection assumes the displayed queue still matches the local Spotify player. Queue changes on another device or between refreshes can change which track is reached.

After all requested Next commands succeed, the device immediately returns to Now Playing, clears navigation/feedback and resends all six normal tiles. Metadata is published only once matching artwork has been fetched, preventing mixed old-cover/new-title frames. Playback polling then tracks the final song.



## Fixed navigation

Physical left=HOME, middle=BROWSE, right=BACK in every screen. BACK restores the previous screen inside BROWSE. On normal Now Playing,
BACK reverses the last Queue jump using Seek-to-start then Previous for each
accepted step, returning to the original track beginning. Each physical navigation press shows its name for
one second on the bottom-right LCD only; no permanent footer is displayed.
See OPERATION-MAP.ja.md for the current operation map.

## Confirmed Queue selection

The selected track URI is captured at press time. The latest Queue is fetched
again before sending commands, so a stale column number cannot select a different
track. If the selected URI is still present, the required number of Next commands
is recomputed. Each Next must be confirmed by Playback State reaching the expected
track URI before another Next is sent. Disappeared targets, unconfirmed switches,
unexpected songs, device changes and ambiguous repeated URIs stop selection;
there is no fallback to blind repeated Next commands. On success return to HOME.
HOME/BACK can cancel remaining commands. No Spotify playback write API is used.
Optional Connect volume is documented in CONNECT-VOLUME.md.

Queue covers load asynchronously from Spotify image URLs into a bounded memory cache. Missing artwork uses a placeholder; images never block selection or HOME.
