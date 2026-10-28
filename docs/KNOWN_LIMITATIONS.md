# Known limitations

- This is a full-feature source preview. Public namespace deployment, fresh-PC
  installation and login restoration are not newly hardware-certified. It is not
  an exact backup of the development PC. The author does not provide accounts,
  media, logos, host software, drivers or a signed installer.
- Only the AJAZZ AKP03J layout/Windows 11 development setup is verified. Similar
  model names and Stream Deck branding do not establish protocol compatibility.
- GSMTC controls and metadata depend on the player. A browser session identifies
  the browser, not reliably a particular origin/tab. Multiple tabs can conflict.
- Spotify API functions depend on Premium/account/allowlist/scope/device support,
  quota and current platform restrictions. Google Home/device volume can be
  unsupported. Network/API errors must not redirect external-device volume to PC
  application volume. Returned queues may change before a selection is executed.
- The artist popular-track fallback parses Spotify embed HTML; it is undocumented,
  may fail, and is not an official replacement for a restricted endpoint.
- Recommended playlists are configured links, not the user's live Spotify Home feed.
  Daily Mix/Discover Weekly access is account/platform-dependent.
- YouTube rendered catalogs may be partial. Ordinary-list lazy loading and channel
  continuation are experimental; advancing past received results is not guaranteed.
  A total memory bound of 1,000 is not a promise of 1,000 available videos.
- YouTube video is canvas-read JPEG transmission to six LCDs, not native decoding
  on the device. It can be blocked by the browser/content restrictions. Do not
  bypass those restrictions. Website access/pixel handling has unresolved service
  conditions; source publication does not grant permission.
- Targets through 120 fps are software request rates. Receiver measurement counts
  accepted JPEGs (including duplicates), not physical LCD refreshes or unique video
  frames. High values can waste resources; use actual responsiveness to compare.
- Chrome focus can still be limited by Windows, background-only processes, missing
  extension registration and tab state. A source launch request is not proof that
  a page loaded or a video began playing.
- Weather is third-party forecast data with no availability/accuracy guarantee.
  Laundry grades are local heuristics for daytime outdoor drying, not safety advice.
- App actions execute trusted user settings via Windows. There is no app-picker GUI
  yet; packaged apps may need a user-created shortcut/URI. Relative paths depend
  on host working directory. Icons are supplied by the user, not bundled.
- Some feature documents retain historical incremental behavior. For deployment,
  this README, INSTALL, MIGRATION and SERVICES take precedence over old v1.1 notes.
- MIT covers own source only. Service policies, third-party content and trademarks
  are separate; a disclaimer, opt-in or private use is not an automatic exemption.
