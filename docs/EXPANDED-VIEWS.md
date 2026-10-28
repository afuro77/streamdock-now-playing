# LCD expanded views — development build

Normal layout remains four artwork panes plus title/artist and playback panes.

| LCD press | Normal view | Either expanded view |
|---|---|---|
| Left four (indices 0, 1, 3, 4) | Open full-cover view | Return to normal |
| Top-right (index 2) | Open expanded title/artist | Return to normal |
| Bottom-right (index 5) | No action | Return to normal |

LCD presses never send Play/Pause. The large knob press still does. Other knob
commands and lower-button bindings are retained; the lower-right artwork reset
also returns to normal if expanded. The lower-left information-mode toggle remains
independent of the expanded-view state.

## Artwork

The virtual canvas is 384×256, divided into three columns and two rows. Images are
contained without cropping or distortion. A square cover occupies the full 256px
height and has 64px side margins. Because physical height is unchanged, a complete
square cover has the same maximum image height as the normal 2×2 artwork region;
this mode uses all six LCDs but cannot make a square larger without cropping.

## Information

The title uses up to three lines and a configurable maximum 96px bold font,
reducing as necessary to fit. The artist uses a smaller font (40px by default)
anchored in the bottom row. Long text is pixel-measured and truncated with the
configured overflow policy. No small labels or album information are drawn.

`display.expanded_title_font_size` and `display.expanded_artist_font_size` are
available in the development runtime config. The right panes in normal view keep
their existing independently configured font sizes.

## Feedback and track changes

Normal view retains the 2.5-second feedback on the bottom-right LCD only.
Expanded views suppress control messages, while knob commands still execute.
Entering or leaving expansion clears pending feedback so it cannot reappear.
Current track artwork and metadata continue to refresh through the existing poller.

## Tests and trial

The earlier tests remain (none deleted). The host registration/input regression
now presses the large knob rather than a LCD, because LCD Play/Pause was explicitly
removed. Twelve new tests cover pixel-preserving full-cover rendering, title/artist
size hierarchy, all entry/exit keys, no-op bottom-right, release events, retained
knob/lower-button behavior, feedback isolation and real poller-driven track changes.
Total: 44 tests.

Only the isolated DEV process is restarted. Stable v1, stable plugin/profile and
the stable backup repository are not modified. Device readability and navigation
remain pending user confirmation.


## Readable information rows

The upper three LCDs form one continuous 384px title viewport; the lower three
form an independent artist viewport. Full strings are drawn once and then split
into physical tiles, without word or character packing at LCD seams.

Default title/artist sizes are 48/36px. Strings that fit are centered and static.
Overflow starts at the beginning, moves immediately right to left at
36 pixels per second, with a 64px gap containing a ｜ separator between repeated copies. The next copy enters from
the right before the previous copy has completely exited, without pauses.
Each row has its own clock, reset when its text changes or the view is reopened.
The animation checks at 10Hz; only changed images are transmitted.

Expansion returns to normal after 30 seconds without device input. Media updates
do not reset this timer. Normal layout, artwork and media/audio controls are unchanged.

Settings under `display`: `expanded_title_font_size`, `expanded_artist_font_size`,
`expanded_scroll_pixels_per_second`, `expanded_scroll_pause_seconds`, and
`expanded_timeout_seconds`. Restart DEV after changes. The older
`expanded_scroll_step_seconds` key is accepted for compatibility but is unused.

Normal bottom-right LCD press toggles Play/Pause using the existing big-knob command. In expanded views it only returns to normal.

Expanded artist names now use two balanced lines at word boundaries within the bottom row. Each overflowing line scrolls without truncation. Single-word names remain centered on one line.


## Artist display aliases

Optional top-level `artist_aliases` in config.json maps exact incoming artist
names to preferred display names, for both normal and expanded views. For example:

```json
{"artist_aliases": {"レッド・ホット・チリ・ペッパーズ": "Red Hot Chili Peppers"}}
```

Unlisted names remain unchanged. This is a local display override, not an automatic
original-name lookup. Metadata keys and control selection remain unchanged.
Edit the DEV runtime config and restart DEV to add mappings. No authentication
or network lookup is required.

Artist names that fit within the 372px content width stay centered on one line. Only overflowing names use the two-line layout.
