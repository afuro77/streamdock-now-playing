# Artist popular tracks (DEV)

Open Track Detail and press its lower artist row, or press the ARTIST photo page. The first artist is used on TRACK; ARTIST uses the currently rotating artist. The browser shows three tracks at a time, names above covers. Turn the right small knob to slide; press either tile in a column to play that track. BACK returns to the original detail page. Successful playback returns to Now Playing. Existing volume/previous/next controls remain unchanged.

The source reads the public Spotify artist embed HTML, validates the artist URI, and preserves its trackList order. This is an undocumented page schema, not the unavailable Development Mode Top Tracks API. Changes to the page can break fetching; no internal API endpoints or cookies are used. Images come from public oEmbed. On failure the browser shows an error and existing GSMTC controls continue to work. Track playback uses the existing user-modify-playback-state scope and a single track URI; the previous queue/context may be replaced.

Cached artist browsers expire after 15 minutes, with at most 16 artists. Network and image work run off the device event loop. Completion draws the currently active mode, not the requesting screen. Missing artist metadata retains the previous exit behavior. No OAuth changes required.

Validation: 222 unit tests (209 existing + 13 new), covering page parsing, identity/URI checks, failure fallback, caching, entry/BACK, playback request body and Desktop completion. Live Garbage source and images also checked. Actual LCD selection/playback awaits user verification.

Playback update: artist selection now submits the complete loaded popular-track list, rotated so the selected track is first (e.g. ranks 3..10,1,2). Sending a single URI caused Next to reach the end and pause on Google Home; this was reproduced and fixed. GSMTC next/previous remains unchanged. A live Google Home sequence verified two Next operations and one Previous operation with matching track URIs and continued playback. Current suite: 240 tests passing.
