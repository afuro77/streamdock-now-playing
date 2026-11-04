# YouTube playback speed (DEV)

Press the right small knob in YouTube playback, full-video or title-detail view
to enter speed adjustment for five seconds. Pressing alone does not change speed.
During adjustment, rotate right/left to increase/decrease by 0.25, bounded at
0.25–2 times. Each rotation renews the five-second window. After expiry, rotation
returns to seek. The timeout is configurable with youtube.speed_adjust_seconds.
Pressing in a list does nothing; rotation continues list scrolling. Spotify and
Desktop controls are unchanged.

Speed is displayed only during the adjustment window: normal view uses the status
feedback cell, and full-video/title-detail views use a bottom-right SPEED badge.
There is no permanent speed display. Missing/stale telemetry shows --x rather than
an assumed speed. Browser-side changes are read every two seconds. Rapid rotations
are combined while awaiting acknowledgement; they never leak into seek commands.
Requests do not navigate or open new tabs.
Missing/stale tabs, changed videos and live streams are rejected. Speed is not
forced across new videos; YouTube may reset it. This controls playback speed, not
the LCD frame rate. Browser extension 0.4.10 must be reloaded, followed by reloading
the YouTube tab. No extra browser permission is added.
