# Third-party notices

The project license does not replace any dependency license, service agreement,
content rights or trademark rights. No third-party runtime/wheel, host installer,
driver, font, copyrighted media or app-logo asset is bundled in this source tree.

| Dependency | Version used | License | Notice |
|---|---|---|---|
| Pillow | 13.0.0 | MIT-CMU | licenses/pillow.txt |
| websockets | 17.2 | BSD-3-Clause | licenses/websockets.txt |
| pycaw | 20260927 | MIT | licenses/pycaw.txt |
| comtypes | 1.4.17 | MIT | licenses/comtypes.txt |
| psutil | 7.2.2 | BSD-3-Clause | licenses/psutil.txt |
| typing_extensions | 4.16.0 | PSF-2.0 | licenses/typing_extensions.txt |
| PyWinRT runtime and Windows.Foundation, Foundation.Collections, Media.Control, Storage.Streams projections | 3.2.1 | MIT | licenses/pywinrt.txt |

Metadata and available license texts were checked against the installed packages.
PyWinRT's notice was obtained from its [official source](https://github.com/pywinrt/pywinrt/blob/main/LICENSE).
These permissive source dependencies are compatible with MIT own-source licensing;
binary redistribution requires a fresh inventory of bundled native dependencies.
Python and Node.js are separately installed tools, not redistributed here.

## SDK / protocol reference

The WebSocket host protocol was studied using
[MiraboxSpace/StreamDock-Plugin-SDK](https://github.com/MiraboxSpace/StreamDock-Plugin-SDK),
commit `a3fb38490a36f507a09af8b78bdddac49c10668f`. Its root MIT notice is retained in
`licenses/streamdock-sdk.txt`. This source does not include the SDK implementation
or its binaries. The upstream C++ subtree has a separate Corsair MIT notice; it
is not incorporated here. SDK permission does not cover redistribution of the
Stream Dock AJAZZ application, drivers or arbitrary vendor assets.

[Zebaro24/AJAZZ-Plugin](https://github.com/Zebaro24/AJAZZ-Plugin), commit
`459f88e829236be4006ef441a4c0eace9f76d85e`, was investigated as a reference. No
explicit license was found in that checkout, so its source was not intentionally
copied. Similarity checks found no qualifying six-line code blocks; see the
publication review for method and limitations. This is not a license grant from
that project and it is not a runtime dependency.

## Assets and services

The SVG and Python-drawn generic pictograms are own-source assets. Windows fonts
are loaded from the user's OS, not distributed. Steam/LINE/Codex/Spotify/YouTube
logos and artwork remain their owners' property. Users supply any permitted
custom icon. Do not include actual album art, screenshots or video frames in releases.

Weather data: [Open-Meteo](https://open-meteo.com/),
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Laundry guidance is a
local heuristic derived from that data, not an official Open-Meteo forecast product.
Free API service limits and commercial-use conditions still apply; see
[Open-Meteo terms](https://open-meteo.com/en/terms).
Spotify and YouTube content is not relicensed under MIT; see [service notes](docs/SERVICES.md).
