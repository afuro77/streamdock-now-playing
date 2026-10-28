# External services and experimental paths

Checked against official documents on 2026-10-28/29. This records technical
dependencies and unresolved questions; it does not grant permission or assert
legal/service compliance. Check current terms before use or redistribution.

## Spotify

- Official API integration uses Authorization Code + PKCE with no Client Secret.
  Scopes: `user-read-currently-playing`, `user-read-playback-state`,
  `user-modify-playback-state`, `playlist-read-private`, `user-library-read`.
- [Development Mode migration guide](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide): new apps have one Client ID per developer and five users per app,
  with stated grandfathering rules. Premium and restricted endpoint/device rules
  can limit availability. Own app credentials do not exempt anyone from terms.
- [Developer Policy](https://developer.spotify.com/policy) and
  [Developer Terms](https://developer.spotify.com/terms) govern content, attribution,
  link-back, data handling, naming and other-service integration. The small LCD UI
  does not yet provide a complete reviewed attribution/link-back UX. Separate modes
  alone do not prove compliance with cross-service restrictions.
- `artist_tracks.py` fetches public embed HTML for popular tracks and oEmbed for
  thumbnails. The former is undocumented website parsing, not the official artist
  top-tracks endpoint. Its compatibility and terms status remain unresolved.
- No Spotify images, audio, user data, identifiers or credentials are bundled.
  Code MIT licensing does not license content. Default API settings are disabled.
  Disconnect/revocation and deletion instructions are in PRIVACY.md.

## YouTube / Chrome extension

- This is not an official YouTube Data API or embedded-player integration.
  It reads rendered DOM / embedded page JSON, uses the undocumented website browse
  continuation endpoint, and attempts to read the playing video via canvas.
- [YouTube terms](https://www.youtube.com/static?template=terms) restrict automated
  access and reproduction/transmission/use of content except as authorized. Being
  technically readable in a browser does not establish permission. The current
  experiment has **not** been established as compliant. Do not use it without the
  required permission; do not bypass authentication, DRM, age or security controls.
- [Official API services terms](https://developers.google.com/youtube/terms/api-services-terms-of-service)
  do not make a website endpoint an approved public API. A future official redesign
  must be reviewed separately. No API key is bundled or requested by this prototype.
- Extension permissions are storage/scripting and the YouTube/loopback host origins.
  Frames and catalogs are sent only to the configured 127.0.0.1 receiver. No tab
  sharing, cookie extraction, internal-account token extraction or media-file
  downloading is used in the direct path. The old optional share helper remains
  source history, not the recommended path. The capture receiver is disabled by
  default. No frames, thumbnails, user channel lists or browser profiles are shipped.

## Weather

Forecast data is provided by [Open-Meteo](https://open-meteo.com/) under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Laundry guidance is a
derived local heuristic. [Free API terms](https://open-meteo.com/en/terms) specify
non-commercial use and limits below 10,000/day, 5,000/hour and 600/minute. Commercial
users need appropriate service arrangements. Location/coordinates are configurable;
the default example is Ichikawa, Japan, not the user's detected location.

## Apps and marks

Windows, Chrome, Spotify, Stream Dock AJAZZ, Steam, LINE and Codex are separately
installed products. Names describe compatibility/settings only. No endorsement or
trademark permission is implied. Users provide their own permitted icons and
launch paths. Do not add proprietary app/SDK binaries or copied logos to a PR.
