# Contributing

Start with the README, installation guide and service limitations. This is a
Windows hardware source preview; fixtures cannot replace a physical device test.

Keep GSMTC controls usable when optional services fail. Keep new UI work separate
from media/audio adapters, and add regression tests before changing input mapping,
navigation or asynchronous rendering. Do not overwrite an existing host profile.

Run the Python unittest suite and the four JavaScript test scripts documented in
the README. Describe the device, host version, mode, expected result and actual
result in a pull request. Never attach tokens, runtime folders, local pairing URLs,
personal launch paths, browser profiles or media screenshots without permission.

Only contribute code and assets you have permission to license. Document new
dependencies and service conditions. Application logos and proprietary SDK/host
binaries must not be bundled. Contributions to own source use the MIT license.
