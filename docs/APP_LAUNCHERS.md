# Configurable Desktop launchers

App launching is a generic `app_launcher` action. Applications are not built-in
features or required dependencies. Default Desktop Home has clock, weather and
laundry in the top row and three unconfigured APP slots in the bottom row.

Each item in `desktop.items` (or a page's `items`) supports:

| Setting | Meaning |
|---|---|
| `cell` | Row-major LCD index, 0 through 5 |
| `type` | `app_launcher` |
| `label` | Visible name; APP if omitted |
| `target` | Executable, shortcut, file or URI chosen by the user |
| `icon_path` | Optional user-owned local image file |
| `icon_only` | Hide the label when a valid custom icon is shown; default false |

An empty/missing target shows an unconfigured launcher and pressing it only
displays a setup prompt. There is no implicit Steam fallback. Failed launches
show local feedback and can be retried. Rapid duplicate presses are debounced.
Windows dispatch uses `os.startfile`, without composing a shell command.
Only configure trusted launch targets: this action intentionally executes them.
Absolute file/shortcut paths are recommended because host working directories vary.
Environment variables and home-directory markers are expanded locally.

Without a custom image, an original generic application pictogram is drawn.
Missing/unreadable images fall back to that pictogram. Logos, app binaries and
personal launch paths are not distributed. Supplying a custom icon does not grant
rights to redistribute the icon. No application is opened during render/startup.

See `examples/desktop.example.json` for blank slots and
`examples/launchers.example.json` for optional Steam/Notepad/website examples.
For LINE or Codex, select a working local executable or shortcut for your own
installation and optionally provide your own permitted icon. Store those actual
paths in runtime `config.json`, never in source or an issue attachment.

Configuration is currently file-based; there is no app-picker/settings GUI yet.
Edit while the plugin is stopped, preserve other configuration sections, then
restart only the relevant plugin. Explicit existing Steam/Codex/LINE settings
remain compatible and take precedence over defaults. Unconfigured APP slots may
temporarily show Desktop volume feedback; configured app buttons are preserved.
