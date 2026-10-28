# Stream Dock Now Playing

[日本語](README.ja.md)

A Windows **Now Playing / Media Controller** for Stream Dock compatible devices.
Built around Windows GSMTC, application audio sessions, six LCD keys and rotary
encoders. Developed on an AJAZZ AKP03J, reported as `AJAZZ AKP03E_3220` by the host.

**Experimental source preview (`1.2.0.dev1`).** This repository includes the full
feature source, not a polished installer or a guarantee that every integration
works for every account/device. No host software, credentials, copyrighted media,
brand icons or private runtime configuration are included.

## Three modes

| Mode | Features | Status |
|---|---|---|
| Spotify / Media | GSMTC metadata, artwork, playback and per-app volume; optional PKCE Queue, Liked Songs, playlist links, Track/Artist/Album details and Connect control | Local functions tested; API features depend on account, scopes and platform limits |
| Desktop | Clock/date, weather, outdoor laundry guidance, configurable app/shortcut/URL actions, master volume, page/navigation structure | Tested on the development device |
| YouTube | Browser media controls, rendered-page/channel lists, direct six-LCD video frames, configurable targets and receiver-rate measurement | **Unofficial browser experiment; see restrictions below** |

Normal media layout is four artwork LCDs plus track information and playback
status. Artwork/details expand on press. YouTube lists show three selectable
columns: text above, thumbnail below. Desktop's default bottom row contains three
unconfigured app actions; Steam/LINE/Codex are user settings, not required apps.

### External services are separate from the code license

The MIT license applies to this project's source, **not** Spotify/YouTube content,
logos, service access or third-party software. Spotify embed-page parsing and
YouTube DOM/HTML/website-continuation/canvas paths are undocumented experiments.
Their policy compatibility is unresolved; publishing their source is not a claim
that their use is authorized. A warning or opt-in does not override service terms.
Do not use them where you lack permission. See [service notes](docs/SERVICES.md).
Spotify API and YouTube integrations are disabled in the supplied default config.

## Start here

1. Read [installation, configuration and removal](docs/INSTALL.md).
2. Install Windows dependencies and the Stream Dock AJAZZ host separately.
3. Create an isolated profile/plugin using the supplied template and source deployer.
4. Start with GSMTC. Configure optional features only after reading their conditions.

The deployment namespace is `org.streamdock.nowplaying.public`. It is distinct
from stable v1 and the private DEV installation; existing profiles are not edited.
Profile import/device assignment and clean-machine installation remain experimental.
Keep a working profile and use the [migration/rollback guide](docs/MIGRATION.md).

## Compatibility

| Device / host | Evidence |
|---|---|
| AJAZZ AKP03J / AKP03E_3220, 6 LCD + 3 encoders + 3 lower keys | Development-device operation verified |
| Stream Dock AJAZZ on Windows 11 | Development host verified |
| Other Stream Dock compatible hardware / Windows 10 | Not verified; layout/events may differ |
| Elgato Stream Deck | Not verified or claimed compatible |

| Player / route | Evidence / limits |
|---|---|
| Spotify desktop | GSMTC playback/artwork and app-volume operation verified |
| Spotify Connect / Google Home | API device/volume path; depends on device capabilities and authorization |
| Chrome / YouTube | Browser GSMTC + experimental extension; multiple tabs can complicate session selection |
| Other GSMTC players | Provider interface supports them; actual control flags/artwork vary, not individually verified |

## Development checks

Python 3.12+ on Windows; Node.js is used only for extension tests.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:PYTHONPATH = (Join-Path $PWD 'src')
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
node tests/youtube-extension.test.mjs
node tests/youtube-browser-extension.test.mjs
node tests/youtube-channel-extension.test.mjs
node tests/youtube-measurement.test.mjs
```

The source preview retains the development regression suite. Fixture-based tests
do not prove hardware reliability, external endpoint availability or terms compliance.
See [known limits](docs/KNOWN_LIMITATIONS.md), [privacy](PRIVACY.md),
[contributing](CONTRIBUTING.md), [security](SECURITY.md) and [changelog](CHANGELOG.md).

## Module boundaries

| Responsibility | Modules |
|---|---|
| Media metadata/artwork | `media.py` (GSMTC) |
| App/master volume | `audio.py`, `master_audio.py`, `volume_router.py` |
| Media commands | `controller.py` |
| LCD layouts, overlays and lists | `renderer.py`, `queue_renderer.py`, detail renderers |
| Host transport/lifecycle | `streamdock.py` |
| Desktop widgets/actions | `desktop.py`, `launcher.py`, `desktop_navigation.py` |
| Optional service adapters | `spotify.py`, queue/library/detail modules, `youtube.py`, browser bridge and Chrome extension |

Host orchestration is still large and will be separated incrementally. No official
affiliation with AJAZZ, Mirabox, Spotify, Google, Valve, LINE or OpenAI is implied.

## License

[MIT](LICENSE) for own source. Dependency and SDK reference notices are listed in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). OS fonts and application icons are
not redistributed. The [publication review](docs/PUBLICATION_REVIEW.md) records
provenance checks, exclusions and unresolved service questions.
