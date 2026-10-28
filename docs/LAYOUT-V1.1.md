# v1.1 development layout

This layout is a private development build, separate from stable v1.

| Left column | Middle column | Right column |
|---|---|---|
| Artwork top-left | Artwork top-right | Large title / smaller artist |
| Artwork bottom-left | Artwork bottom-right | Playback / time / progress; temporary control feedback |

Square artwork is shown in full across the left 2×2 area. Non-square artwork is
letterboxed, never cropped or stretched. A new song updates its own artwork and
metadata normally. Operation messages never replace artwork or metadata.

Only the bottom-right LCD displays operation messages, for 2.5 seconds by default.
Afterward it automatically returns to the latest playback status, elapsed time
and optional progress bar. PLAY/PAUSE feedback describes the requested successful
toggle using the latest known pre-operation state; normal status comes from GSMTC.
No command is changed or added. Left small knob press remains unassigned.

The lower-left button retains its information-mode toggle in the input handler.
Both modes now use the same simplified title/artist pane; album detail is hidden.
The lower-middle session selector and lower-right reset retain their assignments.

## Adjustments

The isolated development runtime reads `config.json` under
`%LOCALAPPDATA%\streamdock-now-playing-dev`. See
`examples/v11-development.example.json` for the complete display configuration.

- Title uses bold 32px, reducing only to 28–32px when three lines are needed.
  Artist uses 20px and one line. Header and album are not drawn.
- State and elapsed time use 32px as their starting sizes. No total time or header.
- Feedback starts at 40px, reducing only to fit at most two lines, e.g. `VOL` / `42%`.
  Previous-track feedback is shortened to `PREV`.
- Font sizes and title line counts are configurable. The title minimum must not
  exceed its maximum. Larger text deliberately trades information for distance readability.
- `text_overflow`: `ellipsis` (default) or `clip`. Text is measured in pixels and
  wrapped before truncation. Scrolling is intentionally deferred until readability is checked.
- `show_progress`: enable the progress bar. The older album settings are retained
  for config compatibility but not rendered in this readability revision.
- `feedback_seconds`: control-message duration.

Restart the development plugin/host after editing configuration. Progress currently
uses the existing GSMTC position samples; no new timeline interpolation is added.

## Device trial and stable fallback

`tools/deploy_development.py` creates a **new** plugin namespace
`local.streamdock.nowplaying.dev` and a **new** `Now Playing v1.1 DEV` profile.
Its launcher and runtime files are generated locally and never committed.
The original `local.ajazz.media` plugin, `Spotify Media` profile, stable source and
stable backup remain unchanged. Select `Spotify Media` in the host to return to v1.
Only one profile can occupy the physical device at a time; selecting DEV is not a
replacement of the stable installation.

## Hardware confirmation requested

1. The complete square cover spans the left four LCDs in the correct order.
2. Top-right title/artist are readable, including long Japanese and Latin names.
3. Bottom-right shows playback/time, and only that LCD changes for knob feedback.
4. Feedback expires around 2.5 seconds, returning to playback/time/progress.
5. All original controls work, and left small knob press does nothing.

Stop after this trial request and adjust only after user feedback.
