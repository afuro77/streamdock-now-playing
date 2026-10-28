# Privacy and local data

There is no project analytics or telemetry service. Optional adapters communicate
with Spotify, Open-Meteo and YouTube/Chrome as described in docs/SERVICES.md;
those providers have their own privacy policies and terms.

Runtime files may contain app launch paths, location coordinates, selected mode,
service caches, diagnostics and browser pairing capabilities. Keep the runtime
directory outside source control. Weather requests disclose configured coordinates
to the weather provider. Browser integration reads supported YouTube page metadata
and, when enabled, video frames for transfer to the local receiver.

Spotify uses Authorization Code with PKCE, without a Client Secret. Its local token
storage uses Windows DPAPI, tied to the Windows user. Do not copy encrypted token
files into backups intended for sharing. Authentication is optional; basic GSMTC
controls should remain usable without it.

To disconnect, disable the relevant optional adapter, revoke the application in
Spotify account settings, and remove its local credential files while the plugin
is stopped. Remove the Chrome extension and local pairing file to disconnect
browser integration. Uninstallation steps are in docs/INSTALL.md. The project
does not receive or store a central copy of your account data.
