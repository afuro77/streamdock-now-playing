# Public source review — 2026-10-29

The public tree is a fresh export, not a visibility change of the private DEV
repository. Private runtime folders and private Git history are excluded.

## Provenance

Implementation references included Zebaro24/AJAZZ-Plugin and the Mirabox SDK.
No SDK library or AJAZZ plugin is bundled. A comparison of six consecutive
nonblank, noncomment source lines (at least 160 characters) found no matching
blocks between implementation/extension source and the reviewed checkouts:

- AJAZZ-Plugin: `459f88e829236be4006ef441a4c0eace9f76d85e`
- StreamDock-Plugin-SDK: `a3fb38490a36f507a09af8b78bdddac49c10668f`

This mechanical check is not proof of independent provenance or legal clearance.
AJAZZ-Plugin had no license in the reviewed checkout; its code must not be copied.
Own source is offered under MIT. Dependency notices are in THIRD_PARTY_NOTICES.md.
The Mirabox root SDK MIT license is retained as a reference notice; host binaries,
drivers, SDK samples and proprietary software are not redistributed.

## Exclusions and defaults

No private OAuth values, DPAPI data, runtime logs, backups, downloaded media,
application logos, Windows fonts or machine-specific launch settings are included.
Public profile actions use a separate namespace and newly generated identifiers.
The profile template retains only generic model/layout information, not a device
serial or device UUID. Launcher defaults are unconfigured APP 1–3 slots.
Optional Spotify and browser integrations are disabled by default.

## Unresolved limitations

Source availability does not grant permission to use third-party services.
Unofficial YouTube page/frame extraction and Spotify embed parsing remain
experimental and require policy review before wider distribution or deployment.
Weather attribution exists in documentation; in-device attribution needs further
review. Public profile installation has not been physically tested on a clean PC.
No certification, official affiliation or service-policy compliance is claimed.

Test and scan results must be recorded separately from hardware acceptance.
