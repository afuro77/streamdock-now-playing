# Automatic Spotify Connect volume

DEV-only enhancement. Normal 4+2 rendering, Queue selection/return and all
non-volume controls retain their existing behavior. Windows AudioSessions and
the GSMTC media controller are unchanged. No new runtime packages are required.

## Routing

For Spotify encoder rotation with the optional API enabled, the volume router
reads fresh Playback State, complements it with Available Devices (cached up to
30 seconds), and decides automatically:

- This Windows computer: existing Spotify.exe Audio Session adjustment.
- External device with supports_volume=true, is_restricted=false, a valid ID and
  volume_percent: PUT /me/player/volume, pinned to that device ID.
- Unsupported, restricted, ambiguous, absent or unreachable device: no volume
  write; display status. Never change PC audio as a fallback for a remote device.

The local computer is identified from the Windows computer name/hostname and
learned device IDs from matching Computer entries. Computer type alone is not
sufficient. Unknown/renamed computers are treated as ambiguous; a custom Spotify
Connect device name may prevent local automatic identification. Google Home is
reported as CastAudio on this installation.

When API auto-volume is enabled and the route cannot be established, the router
fails closed rather than trusting stale local-device data. Other GSMTC controls
remain available. Explicitly disabling spotify.auto_volume restores the previous
local-only volume behavior; do not use that to control an external speaker.

## Encoder and feedback

Each encoder tick still contributes two percentage points. Adjacent ticks merge
over 80ms; subsequent batches run serially with fresh target detection. This
reduces request volume without losing the accumulated signed delta. Targets clamp
to 0..100. A short-lived per-device target avoids losing ticks when remote reports
lag. Old queued deltas are not pinned to a previous target across batches.

After a remote PUT, the device is read back (up to two checks). VOL xx% shows an
observed device value. If no change is confirmed yet, VOL PENDING is shown instead
of a fabricated success percentage. Target changes and API errors have distinct
feedback. Spotify's API acknowledges command submission, not guaranteed hardware
completion; network/device latency still affects response time. Remote volume
work runs outside the host event loop; HOME and the other knobs stay responsive.

## Authorization

Add user-modify-playback-state to the existing read scopes using the same PKCE
helper and Client ID. No Client Secret or Dashboard URI change is needed. Existing
read-only credentials continue to support Queue; remote volume requests detect
missing permission and request reconnect. Refreshing credentials preserves scopes.
Tokens remain in the current user's DPAPI-encrypted runtime store. Reauthorization
replaces that local credential after consent; tokens are not written into source,
logs or backups. A successful HTTP 204 is handled without attempting JSON parsing.

## Physical verification after consent

1. PC active: one detent changes Spotify.exe Audio Session volume by two points.
2. Google Home active: one detent changes its volume by two points and leaves the
   PC Spotify.exe Audio Session untouched.
3. Switch PC -> Google Home -> PC in Spotify; the next knob batch redetects target.
4. Compare displayed VOL xx% to the active target. Turn multiple detents in both
   directions, including near 0 and 100.
5. Retest normal artwork/info expansion, Queue jump, BACK return and play/pause.

Official references:
- https://developer.spotify.com/documentation/web-api/reference/set-volume-for-users-playback
- https://developer.spotify.com/documentation/web-api/reference/get-information-about-the-users-current-playback
- https://developer.spotify.com/documentation/web-api/reference/get-a-users-available-devices
