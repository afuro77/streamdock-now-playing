# Migration and rollback

The public source preview uses `org.streamdock.nowplaying.public`, a separate
plugin directory and newly generated profile. Never rename a live stable or DEV
plugin folder to migrate it. Keep the original `Spotify Media` profile available.

1. Preserve existing plugin/profile/runtime folders locally without publishing them.
2. Install the public source preview into a separate checkout/environment/runtime.
3. Review config options and manually carry over only intended settings: source/audio
   mappings, display sizes, weather location and trusted app actions. Generic APP
   defaults do not overwrite explicit Steam/Codex/LINE entries.
4. Reauthenticate optional Spotify in the public runtime. Do not move DPAPI token
   files between users/PCs or distribute them as examples.
5. Install/pair the public Chrome extension separately if its experimental use is
   permitted. Running two capture receivers on port 8766 is not supported; keep
   only the chosen receiver active or configure separate ports deliberately.
6. Validate mode restoration, artwork, all twelve controls, app icons, weather,
   authorization and login startup. The public namespace/clean install still needs
   this hardware checklist; automated tests do not replace it.

Rollback: select the original stable/DEV profile and stop/remove the public plugin
using its deployment receipt. Do not reset the host or delete its entire data tree.
Public source updates do not update private DEV automatically.
