# First try: album artwork and Play/Pause

[日本語](QUICKSTART.ja.md) · [Full installation guide](INSTALL.md)

Start with local playback and a separate public profile. Queue, Connect and
YouTube are optional later steps. This preview still needs Python and the host;
it is not a standalone installer. Clean-PC hardware acceptance is still pending.
Your normal Spotify desktop login is needed; the first test does not require
the additional developer-app authorization used by the optional Spotify API.

The device is an AJAZZ AKP03J. See [actual product photos at the official store](https://store.shopping.yahoo.co.jp/ajazz/akp03j.html).
Stream Dock AJAZZ is its separate host application. This project adds a plugin
to that application; a profile groups the button assignments and screen layout.

## 1. Prepare

- Windows 11, AJAZZ AKP03J/AKP03E_3220 and the installed Stream Dock AJAZZ host.
- Python 3.12 or newer from [python.org](https://www.python.org/downloads/windows/).
- Download the repository via **Code → Download ZIP**, extract it into a permanent
  folder, then open PowerShell in the extracted folder containing `pyproject.toml`.
  Git is optional; Node.js is not needed for normal use.
- Keep a backup of host settings. Exit Stream Dock from its system-tray menu;
  closing its window may leave it running. The helper never stops it for you.

## 2. Check, then install

```powershell
python tools/quickstart.py --check
python tools/quickstart.py --install
```

If `python` is unavailable or opens the Store, try `py -3.12` in place of `python`.
`--check` makes no file changes. `--install` creates a local `.venv`, installs
dependencies from the configured pip index, and creates only the public plugin,
new profile and runtime. It does not install drivers/host software or register
Windows startup. Keep the source folder in place after installation.

Defaults: host `%APPDATA%\HotSpot\StreamDock`; runtime
`%LOCALAPPDATA%\streamdock-now-playing-public`. Override with `--host-data` and
`--runtime-dir` if your host uses another location. The helper refuses existing
public plugins, nonempty runtime folders and existing `.venv` directories. Use the
[manual guide](INSTALL.md) for recovery or an existing environment. It is a
first-install helper, not an updater; never remove an existing installation just
to satisfy a check. A failed pip command may leave `.venv` behind.

## 3. Try the device

Start Stream Dock, select **Now Playing OSS Preview**, and assign the profile to
your device if requested. Play a local Spotify desktop track. Keep PC audio as
the output for this initial test.

| Try | Expected |
|---|---|
| Wait for the current track | Left four LCDs show artwork; right LCDs show track/state |
| Press the large knob | Play/Pause toggles |
| Rotate the left small knob | Previous/next, if supported by the media session |
| Press an artwork LCD | Expanded artwork; press a LCD again to return |

No Spotify OAuth, Client ID, secret, YouTube extension or API key is needed for
this first test. GSMTC capabilities vary by player. Application volume needs an
`audio_mappings` entry; its initial list is empty, so do not use volume as the
first installation check. Queue/playlist/artist/Connect pages need optional
Spotify authorization. This is expected, not an installation failure.

## If it does not work

| Symptom | Next step |
|---|---|
| Host data not found | Run the AJAZZ host once; verify its data location and `--host-data` |
| Host still running | Exit from its tray menu and repeat `--check` |
| Profile absent/device unassigned | Check host profile selection and device assignment; do not replace your old profile |
| No track information | Play in Spotify desktop, return to the media mode, verify Windows exposes a media session |
| Existing plugin/runtime/environment | Stop; follow the manual/migration guide instead of overwriting |
| Command fails | Copy the error text with private paths redacted into a bug report; do not upload runtime files |

For rollback, switch to your original host profile. To remove this installation,
exit the host and follow [exact-path removal](INSTALL.md#uninstall), using its local
`deployment.json` receipt. Never delete the whole host directory.

Once this works: [app actions](APP_LAUNCHERS.md), [full configuration](INSTALL.md),
[optional service conditions](SERVICES.md), [YouTube speed controls](YOUTUBE_SPEED.md).
