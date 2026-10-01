# SOL.01 for macOS — build package

This package prepares the supplied SOL.01 0.1.0 manual historical replay app for
macOS. The original editable source project was not included in the Windows
release. Its 28 Python application modules were recovered as bytecode, preserving
the original interface, chart, CSV/DBN loading, replay engine, simulated orders,
and saved-trade database. `source/BYTECODE_MANIFEST.json` records their origin and
checksums. The readable Mac integration lives in `launch.py` and `mac_compat.py`.

**This is a build package, not a prebuilt Mac application.** A native `.app` must
be built and verified on a Mac. Windows DLLs and the Windows executable are not
included. Native Mac compilation and interactive Mac testing have not been
performed on this Windows computer.

## Build on a Mac

Use macOS 13 or later, standard
**CPython 3.14**, and an internet connection for
the initial dependency download. Python 3.12, 3.13, and 3.15 cannot run the
recovered bytecode. The script checks the Python version and bytecode format
before building. Use a native ARM Python on Apple Silicon or an Intel Python on
an Intel Mac. Each build targets the architecture of its Python interpreter.

1. Copy this entire folder to a writable folder on the Mac and extract it.
2. Install Python 3.14 from [python.org](https://www.python.org/downloads/macos/).
3. Open Terminal in this folder and run:

   ```sh
   bash build_mac.command
   ```

The script creates an isolated Python environment, installs Mac dependencies,
runs the original app's smoke tests, builds `SOL.01.app`, then repeats the smoke
tests against the bundled executable. It creates a distributable ZIP with a
SHA-256 checksum under `dist`. The build output names and exact location are
printed when it finishes. Copy the resulting `.app` into Applications and open
it. The resulting application bundles Python; other users do not need to install
Python to run it.

Each build records the build Mac's OS version as its minimum supported system.
Build on the oldest supported Mac OS you intend to distribute to; a build made
on a newer system does not claim compatibility with older systems.

Build separately on Apple Silicon and Intel to produce both editions. This kit
does not combine native libraries into a universal application.

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

## Verification and distribution

The build smoke tests exercise startup, both tabs, CSV loading, synthetic DBN and
compressed DBN decoding, replay, BUY/SELL entry and flattening, SQLite persistence,
saved-trade results, volume and chart rendering. They also check that data writes
are outside the bundle. Each test emits JSON and a window screenshot.

The `verification` folder contains any checks performed while preparing the kit.
A Windows-hosted integration check does not verify Mac Cocoa windows, trackpad
gestures, Mac frameworks, native packaging, or Gatekeeper behavior. Before sharing
the final Mac build, open the app on its target architecture, load the demo, test
play/pause/seek, drag brackets, export CSV, close and reopen it, and confirm that
saved trades remain available. A second Mac should also test the distribution ZIP.

PyInstaller applies ad hoc signing unless a Developer ID is supplied. Ad hoc
signing is not Apple notarization. For normal distribution, use your Apple
Developer ID to sign the app and notarize it with Apple's tools. No Apple
credentials are included or requested by this package. Installed Mac dependency
notices and build provenance are collected during each build.

## Implementation references

- [PyInstaller platform and bundle options](https://pyinstaller.org/en/stable/usage.html)
- [PyInstaller macOS architecture and signing](https://pyinstaller.org/en/stable/feature-notes.html)
- [Python sourceless bytecode loaders](https://docs.python.org/3.14/library/importlib.html#importlib.machinery.SourcelessFileLoader)
- [Qt keyboard modifiers on macOS](https://doc.qt.io/qtforpython-6/PySide6/QtCore/Qt.html)

When the original Python sources become available, replace the recovered
bytecode with those sources and move the small path/guide adaptations into the
application itself. Until then, the recovered code requires the Python 3.14
bytecode format recorded in its manifest.
