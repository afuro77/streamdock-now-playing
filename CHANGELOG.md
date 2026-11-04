# Changelog

## Unreleased

- YouTube: press the right small knob to adjust playback speed with rotation in
  0.25 steps (0.25–2x). Speed appears only during adjustment; five seconds after
  the last operation, the knob returns to seek. Extension 0.4.10 is required.

- Make Japanese artist-wrapping regression tests independent of installed fonts.
  Windows CI runners without Meiryo use different fallback glyph widths; tests
  now supply known metrics and also check the one-row width boundary. Rendering
  behavior and device controls are unchanged.

## 1.2.0.dev1 — source preview, 2026-10-29

- Windows GSMTC metadata and controls, application/master audio adapters.
- Six-LCD Now Playing layouts, artwork/detail views and operation overlays.
- Optional Spotify PKCE, queue/library/detail and Connect integration.
- Extensible Desktop widgets, weather/laundry and configurable app launchers.
- Experimental Chrome YouTube browsing/control and direct-frame display.
- Public deployment namespace and sanitized profile template, separate from DEV.
- Generic APP 1–3 defaults; existing explicit launcher settings remain compatible.

This is the first public source baseline. Public installation on a clean machine
is not yet hardware-verified. External service and policy limitations remain;
see docs/KNOWN_LIMITATIONS.md and docs/SERVICES.md.
