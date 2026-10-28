# YouTube Mode (DEV)

MODE cycles Spotify → Desktop → YouTube → Spotify when the optional
`youtube.enabled` setting is true. Existing two-mode installations remain unchanged
unless enabled. Each entry returns to the destination Home.

| Control | YouTube action |
| --- | --- |
| Center physical button | Open video list on short release; long press unassigned |
| Right physical button | BACK to normal view; no action at Home |
| Large knob | Browser app volume ±4 percentage points per tick; press Play/Pause |
| Left small knob | Previous/Next video; press unassigned |
| Right small knob | Seek ±5 seconds per tick; press unassigned |
| Four artwork LCDs | Expand thumbnail with aspect ratio preserved |
| Upper right LCD | Expand video title/channel |
| Lower right LCD | Play/Pause on press (no device-list long press) |
| Any LCD in expanded view | Return to normal view |

Normal view uses four thumbnail cells and two title/status cells. Operation feedback
replaces only the lower-right cell and expires after 2.5 seconds. Expanded metadata
returns after 30 seconds. Full video stays open until manual input and is not
replaced by operation messages.
MODE has the existing 250 ms knob guard. Mode selection persists in mode.json.

Configuration (DEV runtime config.json):

```json
"youtube": {"enabled": true, "source": "Chrome", "process_name": "chrome.exe"}
```

Optional `youtube.open_on_enter: true` opens https://www.youtube.com/ in the
installed Chrome on the first explicit MODE transition into YouTube per DEV
process if no recently registered YouTube tab exists. With extension 0.3.0, an
existing registered tab is activated instead, without changing its URL or adding
a tab. Existing browser media also suppresses opening another Home tab. Repeated
MODE cycles do not keep adding tabs. Startup mode restoration
alone does not open the browser. This launches the website; it does not start a
video, select an extension capture target, or grant browser permissions. Launch
failure leaves all mode controls available and can retry on the next entry.

Use `msedge` and `msedge.exe` to target Edge instead. This mode uses GSMTC and
Windows application audio sessions, with no YouTube OAuth or Spotify API calls.
It does not change Windows master volume.

## Limitations and verification

- GSMTC exposes the browser's published media session, not a verifiable YouTube
  origin or individual tab. Other media in that browser may become the target.
- Volume affects matching browser audio sessions, including other tabs.
- Previous/Next depends on the website/player/playlist. An advertised capability
  is not evidence that the desired playlist navigation succeeds.
- A closed browser or missing media session displays a prompt; no fallback to
  Spotify or Windows master audio is performed.
- Multiple published sessions from the same browser are not selectable yet.
- Spotify API completions cannot draw over this mode. The Spotify service and
  YouTube service retain separate snapshots, artwork, controls and feedback.

Verification: all 273 tests passed (265 existing plus 8 additional tests). The live
Chrome session supplied metadata and a 30,200-byte thumbnail, and six LCD frames
rendered successfully. No live playback/seek/volume command was sent by the probe;
physical controls and navigation still require user verification.

## Experimental live video (2026-10-28)

Enable `youtube.video_enabled` in the DEV runtime to start a loopback-only receiver
on port 8766 (`youtube.video_port` can change it). The current session URL is written
to `video-capture-session.json` in the runtime; it contains a random, per-process
capability token. Open that URL in Chrome. Click **タブを共有**, select the YouTube
browser tab, and leave the helper page open. Only browser-tab capture is accepted.
Audio is not captured. A new plugin process requires reopening the new session URL
and choosing the tab again; screen-share permission is never bypassed.

Switch the AKP03J to YouTube Mode and press an artwork LCD. The six LCDs display
the latest frame, fitted into 384×256 with black padding. On the helper preview,
drag a rectangle around the video player to exclude page controls; theater mode
usually makes this easier. Capture initially covers the entire selected tab.

- Target: approximately 2 JPEG frames/second, quality 0.65. Background browser
  throttling or device transfer speed may reduce the actual rate.
- Six LCD updates are sequential: seams/tearing are possible. This is an
  experiment, not smooth or synchronized video playback.
- No frame queue or recording: only the latest tiled frame is retained in memory.
- Frames older than two seconds are marked stale. Full video retains its last
  received frame during a capture outage; it never exits due to time or pause.
  Returning Home, BACK or an LCD press leaves full video explicitly. Changing
  videos clears the retained old frame to avoid showing the wrong video.
- In another mode or normal view, the helper waits and does not upload frames.
  Press **停止** or use Chrome's sharing control to end capture entirely.
- The HTTP receiver binds only 127.0.0.1, checks Host and a random token, accepts
  only bounded 384×256 JPEGs, and uses no cross-origin permission headers.
- Tests cover frame replacement, stale/disabled fallback, input validation,
  expanded-only rendering, authenticated upload/stop and request rejection.

The browser requires a user gesture and an explicit share selection:
[MDN Screen Capture API](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getDisplayMedia).

## Video selection from AKP03J — extension 0.2.0

The direct-video extension also sends the rendered page's loaded video cards to
DEV. It does not use the YouTube Data API, API keys, cookies extracted outside the
browser, or internal recommendation endpoints. Page HTML selectors are not a
guaranteed API and may need maintenance when YouTube changes its UI.

1. Reload the unpacked extension (version 0.2.0), then reload the YouTube page once.
2. Enter YouTube Mode. Press the center physical key briefly for the video list.
3. Three columns show video titles/channel names above and thumbnails below.
4. Rotate the right small knob to move by one video; press either cell in a column
   to select it. The left small knob retains Previous/Next playback controls.
5. The extension navigates the source YouTube tab, selects it for LCD capture, and
   attempts video.play(). Only its successful playback acknowledgement returns
   the LCD to normal view. An autoplay rejection, closed tab or timeout leaves an
   error in the list. BACK returns to normal view and cancels pending requests.
6. Press an artwork LCD for moving video. Tab sharing is not required.

On the Home page this lists loaded recommendations; on a watch page it lists
loaded related videos. The first page with nonempty cards is the catalog source
until the list is reopened. Entries are deduplicated and capped at 100. Existing
entry order stays fixed while browsing; newly loaded cards append. Reopening
refreshes the snapshot. No infinite scroll, search, subscriptions or playlist
editing are implemented in this initial version.

Navigation targets are canonical HTTPS www.youtube.com/watch video URLs. A local
authenticated bridge carries only validated cards and user-initiated selection
commands. Commands expire after 15 seconds. Leaving the screen/mode cancels pending
commands; late acknowledgements do not move the Desktop or another screen.
Thumbnails load only from i.ytimg.com through a separate host allowlist and bounded
cache; Spotify's existing image allowlist is unchanged.

Tests cover sliding selection, stable order, cancellation, navigation failures,
timeouts, HTTP authentication, DOM extraction, simultaneous command polling,
playback acknowledgement, and preserving Spotify/Desktop routing. Actual page
selectors and playback still require the user's browser/device confirmation.

## Channel entry and tab reuse — extension 0.3.0

The channel entry matches Spotify's detail interaction, **not** the browse-card
thumbnail interaction:

- Normal upper-right LCD → full title/channel detail.
- Detail upper row → normal view (existing behavior).
- Detail lower row → the currently displayed video's channel uploads (`/videos`).
- Channel list: right knob slides; either the title or thumbnail plays that video.
- BACK from the channel list → title/channel detail; BACK again → normal view.
- Normal browse list thumbnails still play videos; they do not open channels.

The owner link/title comes from the current watch page DOM. Missing, stale or
mismatched owner information displays CHANNEL UNAVAILABLE rather than navigating
to a guessed channel. The receiver waits for a catalog from the requested channel
page, rejecting old-page cards and late results after leaving the screen. Channel
redirects or YouTube layout changes may still require adjustment during testing.

### 0.3.1 playback-preserving channel browsing

Channel browsing no longer navigates the watch tab. The content script fetches
the requested same-origin channel `/videos` HTML in the background and reads its
embedded ytInitialData JSON without executing scripts. Legacy videoRenderer and
modern lockupViewModel cards are supported. This page format is undocumented and
may change. Failure shows an error while preserving playback; it never falls back
to navigating the watch tab. Only selecting a video navigates the existing tab.
No additional browser permissions or DEV process restart are needed for this
extension-only update. Reload the extension and YouTube page once to update scripts.

### 0.3.2 frame-rate tuning

Direct video targets 4 fps (250 ms capture interval) rather than 2 fps. Diagnostic
reports are coalesced per stage for five seconds and identical toolbar badge
updates are skipped, reducing non-video work. Only one capture/upload runs at a
time; slow frames are dropped instead of queued. JPEG input remains 384×256 at
quality 0.65. Browser background throttling and hardware transfer limits can still
reduce the achieved rate. No DEV restart or Spotify/Desktop changes are required.

### 0.4.0 frame-rate comparison

The default target is now 6 fps. Options provides 4/6/8/10 fps and an apply button.
Changing this setting updates existing reader timers through storage.onChanged;
it does not reload the video, restart DEV, or add a tab. The latest-frame-only
receiver and single in-flight upload guard remain. The host's 100 ms animation
cycle is a nominal 10 fps ceiling, not a guarantee of 10 complete hardware frames
per second. Compare responsiveness and latency as well as visual smoothness.

### 0.4.1 channel continuation (2026-10-28)

Turning the right knob towards the last six loaded channel videos requests the
next page. Pages append in order with duplicate video IDs removed; the viewport
does not jump. Existing videos remain selectable during loading. BACK, HOME,
mode changes and video selection invalidate late responses using command IDs.
Failures preserve the list; another forward turn retries. End-of-list stops
requests. The catalog is capped at 1,000 unique videos per entry, with at most
100 items accepted per response. Ordinary Home/related-video lists are unchanged.

This uses the channel page's continuation token and public WEB client version
with YouTube's undocumented, same-origin website browse endpoint. It is **not**
the official YouTube Data API and can break if the website changes. No cookies
or authentication headers are extracted or stored; the browser performs the
same-origin request. No navigation, new tab, pause, or playback request is made
when fetching pages. Permissions are unchanged. The direct-video reader is
unchanged. Reload extension version 0.4.1 and the YouTube page once to enable it.

Validation: 305 Python tests and all three JavaScript test scripts passed.
Tests cover append/deduplication, scrolling while loading, failure/retry,
empty/end responses, late-response rejection, bounds, website parsing and
unchanged watch-tab navigation. Live YouTube continuation and LCD verification
remain pending; automated tests use fixtures, not a live channel response.

### Channel list initial position

Opening the current video's channel positions the three-card viewport at that
video's canonical URL, while preserving channel order. Near the end it clamps
the viewport so the current video remains visible. This happens once per entry;
manual scrolling is never overridden by subsequent catalog refreshes. If the
video is absent from the fetched page, CURRENT NOT LOADED is displayed; there is
no guessed match, automatic playback, or reorder. The initial channel-page result
is bounded and does not necessarily include older uploads beyond its loaded range.

The extension registers existing tab IDs. MODE activation focuses the registered
tab; video and channel choices use tabs.update on that same ID. There is no
tabs.create or window.open path. Tabs already opened by earlier versions are not
automatically closed. Reloading the updated extension and YouTube page is required
once. This change does not modify Spotify or Desktop navigation.

### 0.4.2 ordinary rendered-list continuation

The reported 41-item stop occurred in the ordinary rendered-page list, not the
channel list. Forward scrolling near the end now asks the existing YouTube page
to lazy-load more cards by scrolling its last card into view, waits 1.5 seconds,
and appends up to 100 trailing cards. The browser page may visibly scroll. It
does not navigate, open another tab or call pause/play. Three consecutive
responses with no new video IDs stop further requests until the list is reopened.
The total bound is 1,000 unique videos; this is not a guarantee that YouTube
provides 1,000 results. Channel continuation remains a separate path.

307 Python tests and all three JavaScript scripts pass. Actual lazy loading
beyond the reported 41 videos still needs hardware/browser confirmation.

### 0.4.3 twelve-fps trial

Add 12 fps to the 4/6/8/10 selector and use it as the default for an unset or
invalid setting. Existing saved targets are respected: explicitly select 12 fps
in extension options for this trial. Live changes still replace a single timer.
Only full-video mode uses a 1/12-second host animation deadline; Spotify,
Desktop and other YouTube views retain 100 ms. Image size, JPEG quality,
single in-flight upload and latest-frame-only storage are unchanged.

Before the change, 284 frames arrived over 47.77 seconds (approximately 5.9 fps)
while full video was active. This measures receiver throughput, not complete
physical LCD refreshes. The new 12 fps target still requires a live measurement.
309 Python tests and all three JavaScript scripts pass. Reload extension 0.4.3
and the YouTube page once, apply 12 fps, and reopen full video after DEV restart.

### 0.4.4 extended frame-rate choices

Options now offers 4/6/8/10/12/15/20/24/30 fps. The default remains 12 and saved
values remain intact. The content reader includes its selected target on frames;
the worker allowlists it and sends X-Target-Fps to the authenticated receiver.
Only a valid, accepted extension frame updates the receiver's target, which is
included in diagnostics. Full-video host scheduling follows that value; other
views/modes retain their previous timing. Changes apply live after this one-time
extension reload and DEV restart. Higher targets do not guarantee hardware fps.
JPEG size/quality and latest-only/single-in-flight behavior are unchanged.

311 Python tests and all three JS scripts pass, including rate propagation,
invalid values, HTTP metadata validation and mode-isolated scheduling. Actual
15/20/24/30 fps throughput remains to be measured on the device.

### 0.4.5 targets up to 60 fps

Add 40/45/50/60 to the existing choices. Keep default 12 and all saved choices,
including 30. Reader, options, worker and receiver validate the same set; the
existing full-video scheduler follows accepted frame metadata up to 60. Other
modes, image quality and latest-frame/single-in-flight behavior are unchanged.
The user reported no visible issues at target 30; this is not measured LCD fps.
All 311 Python tests and three JS scripts pass, including 60-fps HTTP propagation,
single-timer scheduling and rejection of targets above the supported range.
Reload extension 0.4.5 and the YouTube page once, then choose/apply a target.

### 2026-10-29 closed-Chrome relaunch fix

The launcher previously treated a successful launch as permanent for the whole
DEV process. Cached GSMTC metadata or a recent extension tab heartbeat could
also suppress reopening after Chrome exited. Mode entry now checks live Chrome
process presence before trusting those hints. The launcher allows reopening
after process exit, with a five-second startup debounce. A running registered
YouTube tab is reused; existing browser media still prevents duplicate Home tabs.
This addresses fully closed Chrome, not every case of background-only Chrome
or a closed YouTube tab while other Chrome tabs remain open.

314 Python tests passed. A real launch test started from zero Chrome processes
and observed 16 Chrome processes after requesting the YouTube URL. Page loading
and physical MODE-key behavior still require user confirmation. No extension
reload is needed specifically for this Python-only fix. Stable v1 was unchanged.

### 0.4.6 startup foreground and minimized-window restoration

Launching Chrome now arms a one-shot 15-second foreground request. The first
registered YouTube tab receives the existing focus command (no URL navigation).
Stale tab IDs from an exited Chrome process are discarded. Mode exit/HOME cancels
the request and late registration cannot steal focus after expiration. Existing
browser media without a fresh tab also arms this bounded request rather than
creating another Home tab. Reused tabs continue to use the original focus path.

The extension checks the target window state and restores a minimized window to
normal before requesting focus; maximized/fullscreen windows are not resized.
This uses the Chrome windows API, without new permissions or native input hacks.
316 Python tests and all three JS scripts pass. Actual Windows foreground behavior
is pending manual verification; OS focus restrictions may still affect the result.
Reload extension 0.4.6 and YouTube once to enable window restoration.

### 2026-10-29 automatic list entry without a selected video

Entering YouTube Mode opens the video list automatically if no video is known.
A fresh registered Home/channel page takes precedence over stale GSMTC metadata.
A watch page, including paused playback, keeps Now Playing. Closed Chrome enters
the list while starting the browser; startup foreground still uses the existing
one-shot focus request. First polling after DEV startup also opens the list if
the restored YouTube mode has no media. This is a one-time entry decision: HOME
and BACK are not undone by recurring polling. Successful video selection returns
to Now Playing as before. A failed Chrome launch displays CHROME ERROR in the list.

321 Python tests and all three JS scripts pass. This is Python-only; extension
0.4.6 does not need another reload. Real LCD entry/selection remains to be checked.

### 0.4.7 on-demand measurement and higher targets

Options has a "measure current setting" button. It does not change the applied
target. It reads authenticated receiver counters twice per second and computes
accepted extension JPEGs / receiver monotonic elapsed seconds for approximately
five seconds. Progress and the final target, measured rate, frame count, elapsed
time and local completion time are shown. The latest ten completed results are
held only in the options page's memory, with a clear button; closing/reloading
the page discards them. No storage history, file export or automatic target
comparison is created. The earlier static benchmark memo was replaced.

Samples require full video and fresh frames. Instance changes (DEV restart),
counter/time regression, target changes or a target not yet applied abort the
run without recording a valid result. Other local option controls are temporarily
disabled; cancellation remains available. Measurement messages are accepted only
from this extension's options page, and return no pairing token or video content.
Results count received JPEGs, including duplicates, not hardware LCD refreshes.
The conditions on the page state 384x256, JPEG quality 65%, full six-LCD video,
and the short measurement duration; video/CPU load can affect the result.

75/90/120 fps are additional experimental targets. The 60fps ceiling was a
software allowlist, not a measured hardware specification. Existing saved values
and the default 12 remain. Reader, UI, worker, receiver and host scheduling accept
the expanded set; no queued frames are introduced. Reload extension 0.4.7 and
the YouTube page once after the DEV update. Python322 tests and four JS scripts
pass, including real options handlers with a fake sample clock and interruption,
history bounds, memory-only behavior, protocol authorization and higher targets.
Live options-page measurement remains to be confirmed by the user.

### 2026-10-29 denser list titles

YouTube lists use an optional compact QueueRenderer layout: a small position
number replaces VIDEO, margins shrink from 5px to 3px, and titles use up to four
20px lines instead of two 25px lines. A single 14px channel-name line remains
below. Long titles still ellipsize after the fourth line. Cover images and input
selection/scroll behavior are unchanged. The default renderer used by Spotify
does not enable this layout. 324 Python tests pass, including actual title-capacity,
cover preservation and six-tile rendering checks. This Python-only update needs
no extension reload; physical readability remains to be checked.
