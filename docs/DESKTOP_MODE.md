# Desktop Mode (DEV)

Left physical key toggles Spotify / Desktop globally. Returning to Spotify opens Now Playing. The previous HOME assignment is replaced. BROWSE and BACK retain their Spotify behavior; Desktop currently ignores them. Desktop knobs are unassigned; playback continues.

Initial layout (row-major cells 0..5): Clock (time/date), Weather, Steam; three blank cells. Press Steam to launch the installed Steam client. Other Desktop cells currently have no press action. Weather details are reserved for later work.

Merge `examples/desktop.example.json` into the DEV runtime config.json and restart DEV to change layout/location. `desktop.weather.location`, `latitude`, `longitude` select the weather location; changing the label alone does not change coordinates. Values shown are approximate central Ichikawa coordinates. `items` assigns registered types to cells 0..5. Add a Widget subclass to REGISTRY for future features. No arbitrary plugin loader is used.

Weather: Open-Meteo https://open-meteo.com/ (CC BY 4.0 data attribution). Non-commercial free API; https://open-meteo.com/en/pricing . No key required. Refresh every 900 seconds; retry after 60 seconds on failure. Cached data is marked with *, and laundry becomes ? on failure or stale data. Network work runs outside the render/event loop. Forecasts are model estimates, not local observations.

Laundry is an independent pure function in laundry.py; Weather only displays its grade. It uses six hourly forecast slots starting with the current hour: rain probability/amount, humidity, wind, temperature and sunshine. Default rain threshold >=30% or precipitation >=0.1 mm gives ×; wind >=8 m/s gives ×; night, temperature <10 C or mean humidity >=80% gives △. Dry, <=10% rain, <=60% humidity, >=18 C, 1..5 m/s wind and >=2 hours sunshine gives ◎; otherwise ○. Missing forecast gives ?. This is a simple heuristic, not an official laundry index or drying guarantee. Detailed metrics/reason are returned for a future details view. `desktop.weather.laundry` can override rain_probability and strong_wind_ms thresholds.

Spotify media metadata continues updating while Desktop is visible. Async Spotify operations cannot select the top-level mode or draw over Desktop. An already accepted Queue selection can finish in the background. A restart defaults to Spotify Now Playing.

Testing: full unittest discovery with PYTHONPATH=src. No dependency additions. Steam actual launch and hardware display require user verification.

## Icon layout update
Cells: 0 Clock, 1 Weather (icon and temperature only), 2 Laundry (shirt icon and grade), 3 Steam, 4/5 blank. Weather and Laundry share one weather fetcher/cache. Weather and shirt drawings are original code-native artwork in desktop_icons.py. The Steam icon is extracted from the locally installed Steam executable to the DEV runtime directory, referenced by app_launcher.icon_path, and is not bundled in the repository. Steam artwork belongs to Valve. Configure icon_path to a local image for other launcher icons. Open-Meteo attribution: https://open-meteo.com/ (CC BY 4.0).

## Daytime laundry revision
Laundry now evaluates the next useful daytime drying window, not the next six hours. Before 14:00, use today from max(08:00, current hour) to 16:00; from 14:00 onward, use tomorrow 08:00–16:00. The tile explicitly shows 今日 / 明日 and the grade. Forecast retrieval covers three calendar days. Missing target-day data shows ? and never falls back to tonight. Thresholds remain simple heuristic estimates. Configure desktop.weather.laundry.start_hour (8), end_hour (16), tomorrow_from_hour (14). Current nighttime status no longer downgrades tomorrow's grade. Clock colon blinks each second; time remains HH:MM.

Mode persistence fix: selected top-level mode is saved in runtime mode.json and restored on plugin restart, including DEV reload. Spotify subview returns to Now Playing. First-ever startup or invalid saved state defaults to Spotify. Timestamped mode restore and physical-key transitions are recorded in plugin.log. This supersedes the earlier restart-always-Spotify behavior.

## Weather / laundry details
Press Weather or Laundry to show six detail cards. Each LCD has an independent text block to avoid physical seam clipping. Weather columns: current, tonight (remaining hours from 18:00–24:00), tomorrow 08:00–16:00. Displays forecast temperature range and maximum precipitation probability per window. Laundry shows target day/window, heuristic grade/reason, maximum rain probability/wind and mean humidity/temperature. No guaranteed drying deadline is claimed. Failed or stale weather shows update pending. Any LCD or physical BACK returns Home; 30 seconds idle also returns Home. Mode switch closes details. No extra home cells, media commands or OAuth scopes added.

Visual details update: weather top row has current/tonight/tomorrow pictograms and temperatures, bottom row corresponding maximum rain probabilities. Laundry has a large colored grade, evaluated time window, rain/humidity/wind/temperature icons with large numbers. Explanatory paragraphs are removed. Forecast windows, calculations and navigation are unchanged; the time window is labeled as evaluated time, not a promise of safe outdoor drying. Icons are original Pillow drawings.

## Navigation and knobs (current)
Physical keys: left MODE toggles modes; center HOME short press returns to current mode Home; right BACK navigates one screen back and does nothing at Home. Spotify center hold >=700 ms opens Queue; releasing a completed hold never fires HOME. Desktop center hold is reserved/no action. Mode change invalidates pending holds and ignores dial events for 250 ms afterward. SDK events have no reliable hardware timestamp, so this guard covers immediate transition input rather than arbitrarily delayed events.

Desktop big dial: Windows default multimedia render endpoint master volume, 2 percentage points per tick; press toggles master mute. A separate MasterAudio adapter never uses Spotify audio sessions or Spotify Web API. Endpoint is resolved for each command to follow default output changes. Feedback appears in the highest-numbered empty Home cell for 2.5 seconds; detail cards are not replaced. If no Home cell is empty, no overlay is drawn. Errors do not fall back to Spotify. Spotify big dial remains unchanged.

Desktop left small dial: previous/next page, clamped at ends; press unused. Right small dial rotation/press reserved, no action. Configure desktop.pages as a nonempty list of {items:[...]} to add pages; old desktop.items remains supported for a single page. Each page has independent widget instances. DesktopNavigation manages page/screen history; HOME resets to page 1 and clears history, BACK pops screen history; no history is a no-op. Detail timeout remains 30 seconds.

The previous BACK-to-original-track binding has been removed in favor of navigation-only BACK. Queue selection itself and Spotify LCD assignments remain unchanged. DEV Home now has Clock/Weather/Laundry/Steam and two blank cells, per the current layout request; the prior Codex/LINE launch settings are retained in the local work backup rather than deleted from the system.

Latest user preference: Spotify center physical key opens Queue immediately on ordinary press; long press is no longer required. Release does not fire HOME. Desktop center HOME behavior remains unchanged. This supersedes Spotify short HOME / long Queue.
