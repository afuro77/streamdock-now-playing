# Direct video prototype — no tab sharing

This extension reads the YouTube HTML video element into a 384×256 canvas and
uploads JPEG frames to the existing DEV loopback receiver. It does not use
getDisplayMedia, tabCapture, screen capture, debugger access, internal YouTube APIs,
or media downloads. No third-party extension code was copied.

**Status: code/protocol tests only; actual YouTube pixel access is unverified.**
If the browser blocks canvas readback (SecurityError), the extension stops and
shows ERR. It does not bypass restrictions or switch to tab sharing. Protected
video may be unreadable or black. Background-tab throttling may reduce frame rate.

## Install and test

1. In Chrome, open `chrome://extensions` and enable Developer mode.
2. Choose **Load unpacked** and select this directory (the one containing manifest.json).
3. Reload the YouTube tab. Pin this extension using Chrome's extensions menu.
4. On the YouTube tab, click the extension button once. ON means it is armed.
5. On AKP03J, enter YouTube Mode and press one of the thumbnail LCDs.
6. Confirm actual changing video frames. Click the extension button again to stop.

No tab-share chooser is needed. The frame includes only the video element, with
aspect ratio preserved and black padding. Target upload rate is about 2 fps.
Only the selected YouTube tab is enabled. No audio is captured. Returning to normal
view or another device mode prevents frame uploads. The existing receiver drops
stale images after two seconds.

DEV pairing is in ignored `pairing.local.json`, prepared locally for this trial.
The extension keeps the token in its background context; the webpage/content
script never receives it. If DEV restarts and rotates the token, this prototype
requires updating pairing.local.json or pasting the fresh runtime session URL in
the extension's options page. This trial does not yet solve automatic re-pairing.
No session URL belongs in Git. To uninstall, remove the extension in Chrome;
no Windows/Stream Dock startup settings are changed.

## Permissions

- YouTube: inject the video-element reader on www.youtube.com only.
- 127.0.0.1: communicate with the local DEV receiver; no remote upload.
- storage: store selected tab/session settings. Browser restart requires pressing
  the extension button again; it never starts arbitrary tabs silently.

Extension installation and the actual YouTube test must be performed by the user.
ERR's tooltip states the reason. Success can also be checked through DEV
status.json's video_frames_received and video_fresh fields.

## Official references

- [Extension cross-origin requests](https://developer.chrome.com/docs/extensions/develop/concepts/network-requests)
- [Canvas readback restrictions](https://developer.mozilla.org/en-US/docs/Web/HTML/How_to/CORS_enabled_image)
- [tabCapture requires extension invocation](https://developer.chrome.com/docs/extensions/reference/api/tabCapture)
