# SOL.01 for macOS — Apple M4 edition

**The finished SOL.01 0.1.0 manual edition installer for Apple M4 is available in
[`../SOL.01-macOS-Downloads/`](../SOL.01-macOS-Downloads/).** The app includes
Python and its native Mac libraries. The recipient does not need Python,
programming tools, or a build step.

This folder contains the maintained Mac build inputs; the separate delivery
folder contains the finished Apple M4 application. The original Windows release was
preserved: all 1,761 manifest files still match their original checksums.

## Recipient: download and install

Download [SOL.01-macOS-Apple-M4-0.1.0.dmg](https://github.com/mike63980-design/SOL/releases/download/v0.1.0-macos-m4/SOL.01-macOS-Apple-M4-0.1.0.dmg).
This Apple M4 edition requires **macOS 15.7 or later** and contains the native
Apple Silicon ARM64 application.

The permanent public release is available at
[v0.1.0-macos-m4](https://github.com/mike63980-design/SOL/releases/tag/v0.1.0-macos-m4).
The download works without a GitHub login. A local copy is also available in
[`../SOL.01-macOS-Downloads/`](../SOL.01-macOS-Downloads/).

1. Download or receive the Apple M4 DMG and open it.
2. Drag `SOL.01.app` to the Applications shortcut inside the disk image.
3. Open SOL.01 from Applications, then eject the disk image.

This personal build is ad hoc signed and has not been notarized by Apple.
If macOS blocks first launch because the developer cannot be verified, follow
Apple's [Open Anyway instructions](https://support.apple.com/en-us/102445) for an
app you trust. The same instructions are included in the DMG and in the delivery
folder's Apple M4 installation guide.

The earlier `SOL.01-macOS-Build-Kit.zip` is a maintainer build kit. Send the
finished DMG to the friend. Ready-to-run ZIPs were produced on the build machines
but were not retained as downloads. The current delivery contains one Apple M4 DMG.

## Use the app

Open **Instructions** for the controls. Use **Load File** to select tick CSV or
Databento DBN/DBN.ZST data. A copy of the included synthetic demo is available at:

```text
~/Library/Application Support/SOL.01/demo/SYNTHETIC_DEMO.csv
```

**Play** advances replay. Set **Qty**, **SL pts**, and **TP pts**, then use
**BUY MKT**, **SELL MKT**, and **FLATTEN**. Drag SL/TP lines to adjust brackets.
Scroll zooms time; **Command + scroll** zooms price on Mac. Right-drag pans price.
**Results** shows current trades, saved trades, the log, and CSV export.

This edition uses local simulation and does not submit broker orders. Futures
data and trading behavior are the same as the supplied Windows manual edition.
No personal settings, saved trades, or licensed market files are shipped.

## Persistent data and migration

Settings and trades are stored outside the application bundle:

```text
~/Library/Application Support/SOL.01/data/manual/app_settings.json
~/Library/Application Support/SOL.01/data/manual/manual.sqlite
```

Back up the entire `data/manual` folder. To migrate from Windows, close both apps,
back up the Mac folder if present, and copy the Windows release's `data/manual`
folder into `~/Library/Application Support/SOL.01/data/`. Copying the whole folder
preserves any SQLite companion files. Historical data-file paths saved on Windows
must be selected again on Mac using **Load File**. Do not copy Windows `_internal`
libraries into the Mac app.

For a separate development data directory, set `SOL_DATA_HOME` to an absolute
folder path before launching. Smoke tests always use a separate temporary folder
and never add their synthetic trades to your real saved-trade database.

## Completed verification

The build smoke tests exercise startup, both tabs, CSV loading, synthetic DBN and
compressed DBN decoding, replay, BUY/SELL entry and flattening, SQLite persistence,
saved-trade results, volume and chart rendering. They also check that data writes
are outside the bundle. Each test emits JSON and a window screenshot.

Both native Apple Silicon and Intel build jobs passed in
[GitHub Actions run 36920122088](https://github.com/mike63980-design/SOL/actions/runs/36920122088)
on October 1, 2026, from commit
`f688fcb732680806b75d31da78b2d371cf628abe`. The builds used macOS 15.7.9 and
standard CPython 3.14.7. Source and frozen executable tests passed on both native
architectures, and the jobs verified architecture, app signatures, and DMG
integrity. This is historical build verification; the current delivery contains
only the Apple Silicon application labelled for Apple M4. Its unchanged DMG
SHA-256 is `cee634483bcb6799e3c7e704de193f163aa0114f003616ef33fabd5fb1231c06`.

The automated app tests used Qt's offscreen platform. Interactive Finder/Cocoa
launch, trackpad gestures, and Gatekeeper behavior have not been tested, and no
interactive test on an M4 Mac has been performed. The
delivery folder's [`RELEASE_VERIFICATION.json`](../SOL.01-macOS-Downloads/RELEASE_VERIFICATION.json)
and `verification/` folder contain the build provenance, test reports,
screenshots, and Windows preservation check. This folder's `verification/`
contains the earlier Windows preparation checks.

The original application source project was not included in the Windows release.
Its 28 recovered bytecode modules preserve the original application logic;
`source/BYTECODE_MANIFEST.json` records their origin and checksums. The readable
Mac integration lives in `launch.py` and `mac_compat.py`. Native Mac libraries,
third-party notices, and provenance are bundled separately from Windows files.

## Maintainer: rebuild on a Mac

These steps are for maintaining a new release. The recipient installs the
finished DMG above and does not perform them.

Use a native Apple Silicon Mac running macOS 13 or later, standard
**CPython 3.14**, and an internet connection for dependency downloads. The build
checks Python's bytecode magic (`2b0e0d0a`) and rejects free-threaded builds and
Rosetta. Python 3.12, 3.13, and 3.15 cannot run the recovered modules.

1. Copy this complete maintained folder into a writable folder on the build Mac.
2. Install standard Python 3.14 from [python.org](https://www.python.org/downloads/macos/).
3. Open Terminal in the folder and run:

   ```sh
   python3.14 restore_bytecode.py
   bash build_mac.command
   python3.14 package_for_friend.py
   ```

The restoration verifies the text payload and recovered module hashes. The build
creates an isolated virtual environment, installs native dependencies, runs the
source smoke tests, builds `SOL.01.app`, and repeats the tests against the bundled
executable. The packaging script requires a verified native build, then creates
the DMG, a ready-to-run ZIP, installation instructions, and checksums under
`dist/`.

Each build records its build machine's macOS major/minor version as the minimum
system. The delivered Apple M4 build requires macOS 15.7; older-system support
needs a separate build and verification on that system. Use native ARM64 Python
for this edition.

The [SOL repository](https://github.com/mike63980-design/SOL) keeps these
inputs in `macos/` on `macos-release`, with the workflow at
`.github/workflows/build-macos.yml`; its original `main` branch is preserved
separately. The repository is public. Native CI creates installers and
verification artifacts, and the published `v0.1.0-macos-m4` release retains the
Apple M4 DMG as a permanent download. The publisher workflow completed
successfully in [run 36927325227](https://github.com/mike63980-design/SOL/actions/runs/36927325227).

Before claiming interactive Mac verification for a later release, test Finder
launch, demo loading, play/pause/seek, bracket dragging, CSV export, closing and
reopening, and saved trades on the target Macs. A second Mac should test the
downloaded installer and first-launch behavior. Developer ID signing and Apple
notarization can be added to remove the unverified-developer first-launch flow.

## Implementation references

- [PyInstaller platform and bundle options](https://pyinstaller.org/en/stable/usage.html)
- [PyInstaller macOS architecture and signing](https://pyinstaller.org/en/stable/feature-notes.html)
- [Python sourceless bytecode loaders](https://docs.python.org/3.14/library/importlib.html#importlib.machinery.SourcelessFileLoader)
- [Qt keyboard modifiers on macOS](https://doc.qt.io/qtforpython-6/PySide6/QtCore/Qt.html)

When the original Python sources become available, replace the recovered
bytecode with those sources and move the small path/guide adaptations into the
application itself. Until then, the recovered code requires the Python 3.14
bytecode format recorded in its manifest.
