# Source installation and removal

This is an experimental Windows source deployment. The public namespace/profile
has not been verified by installing onto a clean PC; do not replace a working
profile. First read [limitations](KNOWN_LIMITATIONS.md) and [service conditions](SERVICES.md).

## Requirements

- Windows 11, Python 3.12+ and a separately installed Stream Dock AJAZZ host.
- A supported physical layout (development tested on AKP03J).
- Git or a downloaded source archive. Keep the checkout in a permanent writable
  directory; generated launchers refer to it. No host/driver/Python binaries are bundled.
- Node.js only if running the extension tests.

From the repository directory in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
```

The install creates a local environment; it does not modify your device/profile.
Keep it separate from any existing installation's environment.

## Create an isolated plugin/profile

Exit the Stream Dock host yourself before writing its data directories. Do not
force-kill the host. Back up existing host settings locally first.

```powershell
.\.venv\Scripts\python.exe tools/deploy_development.py --python "$PWD\.venv\Scripts\pythonw.exe" --runtime-dir "$env:USERPROFILE\StreamDockNowPlayingData"
```

The historical script name is retained, but this public tree creates only:

- `org.streamdock.nowplaying.public.sdPlugin` under the selected host's plugins directory;
- a newly generated `.sdProfile` named `Now Playing OSS Preview`;
- the explicitly selected runtime directory, initially containing example config.

It refuses to overwrite an existing plugin. Default host data is
`%APPDATA%\HotSpot\StreamDock`; `--host-data` can override it. A twelve-action
AKP03J profile template is supplied without device serial/UUID or actual images.
The host may need manual device assignment. For another compatible profile, pass
`--template-profile` explicitly. Only use a profile with the expected six LCD,
three encoder and three lower-key action layout, not an arbitrary system profile.

Restart the host and select **Now Playing OSS Preview**. Retain your original
profile for rollback. The host owns plugin lifecycle and relaunch at login; it
must itself be configured to start at Windows login. This project does not add a
scheduled task, service, registry autorun entry or automatic host startup.

## Configure

Stop the public plugin/host before editing runtime `config.json`. Never place the
actual file in the repository. The launcher sets an explicit data directory and
the runtime refuses silently starting without its required config.

- `preferred_source`: GSMTC source substring, empty for the system current session.
- `audio_mappings`: source substring to process executable name (for example Spotify
  or Chrome). Volume is not automatically the physical output device volume.
- `desktop`: weather location/coordinates and widget/action items. The example
  location is Ichikawa, Japan; change it as desired. See [app actions](APP_LAUNCHERS.md).
- `display`: font, scroll, timeout and overlay options.

Keep the top-level config sections together; do not replace the entire file with
an app-action snippet. Restart the public plugin after changes.

### Optional Spotify

Read [service notes](SERVICES.md) and [privacy](../PRIVACY.md). Register your own
eligible Spotify developer app, add `http://127.0.0.1:8765/callback`, then set
`spotify.enabled=true` and your own `client_id` in runtime config. No Client Secret
is used. With the same runtime environment selected, run:

```powershell
$env:STREAMDOCK_NOW_PLAYING_DATA_DIR = "$env:USERPROFILE\StreamDockNowPlayingData"
.\.venv\Scripts\python.exe -m streamdock_now_playing.spotify
```

Complete authorization personally in the browser. Tokens are stored using Windows
DPAPI; they are not portable login backups. Scope and current Development Mode
limits are documented in SERVICES.md. Do not distribute your Client ID as shared
access or copy another user's token. API failures must not block local GSMTC.

### Optional experimental YouTube

Review the unresolved website/content conditions in SERVICES.md before use.
The source is included for inspection; this is not an official API integration
or a claim that use is authorized. The default config has it disabled.

If permitted for your use, set `youtube.enabled=true` and `video_enabled=true`.
Use a dedicated Chrome profile/tab if possible. Start the plugin, then load the
unpacked `extensions/youtube-lcd` folder from Chrome's extensions page personally.
Do not disable browser security or bypass canvas restrictions. The plugin creates
an ignored `pairing.local.json` for this machine. Never publish it or its URL.

If pairing is stale, use the local `video-capture-session.json` URL in extension
options on your own machine. Treat its fragment as a local control capability.
YouTube Mode opens/reuses Chrome. With no selected video, the LCD list opens;
right small knob scrolls and a column press selects. In Now Playing, an artwork
LCD opens full six-LCD video. This is the display required for options measurement;
Chrome itself does not need fullscreen. Reload extension/page after extension updates.

## Uninstall

1. Exit the host and keep its local settings backup.
2. Read the public runtime `deployment.json` receipt to identify the exact generated
   plugin/profile directories. Do not share that receipt without redaction.
3. Remove **only** the `org.streamdock.nowplaying.public.sdPlugin` directory and
   the generated `Now Playing OSS Preview` profile, through the host or file manager.
   Do not remove the whole host data directory or any stable/DEV profile.
4. Remove the unpacked Chrome extension if installed. Revoke optional Spotify access
   via the Spotify account Apps page; delete the public runtime credentials/caches
   when no longer needed. See PRIVACY.md.
5. Optionally remove this checkout, its virtual environment and the public runtime.
   Deleting a runtime removes its settings; it does not uninstall external apps.

`tools/uninstall.py` is an advanced dry-run helper for *marked staged* public
plugins created by `tools/install.py`; it does not remove profiles and is not the
recommended inverse for source deployment. The receipt-based procedure above is
the supported removal guidance for `deploy_development.py`.
