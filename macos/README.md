# SOL.01 for Apple M4 — includes NQ data

**[Download SOL.01 for Apple M4 with 2025–2026 NQ data](https://github.com/mike63980-design/SOL/releases/download/v0.1.1-macos-m4/SOL.01-macOS-Apple-M4-with-NQ-Data-0.1.1.dmg)**

SOL.01 manual historical replay for an Apple M4 MacBook. Requires **macOS 15.7 or later**. The app, Python, libraries, and all **284 supplied NQ data files** are included in one download.

1. Download and open the `.dmg` above.
2. Drag **SOL.01.app** to **Applications**.
3. Open SOL.01 from Applications, then eject the disk image.
4. Click **Load File**, choose a day from **2025-2026 Year**, and use **Play**.

First launch prepares the included data in `~/Library/Application Support/SOL.01/data/nq_ticks/2025-2026 Year/`. It may take a little time. Later launches reuse that copy. Existing files and custom data-folder settings are preserved. The supplied data covers August 2025 through July 2026; filenames have no USED markings. The original three files in the `bad` subfolder are retained.

This personal build has not been notarized by Apple. If macOS blocks first launch, follow [Apple's Open Anyway instructions](https://support.apple.com/en-us/102445).

Open **Instructions** for the controls. Settings and saved trades are stored in `~/Library/Application Support/SOL.01/data/manual/`. This app uses local simulation. The original Windows program remains unchanged; personal settings and saved trades are not included.

The package retains the original SOL.01 0.1.0 manual application logic. Package version 0.1.1 adds the supplied historical data and Mac data-folder setup. Native automated tests cover the source and bundled app, real included DBN loading and replay, data integrity, signatures, and disk-image integrity. Interactive Finder launch and M4 hardware were not tested.

[Release page and optional checksum](https://github.com/mike63980-design/SOL/releases/tag/v0.1.1-macos-m4)

## Maintainer build inputs

This folder maintains the separate Mac package. The original 28 recovered application bytecode files are unchanged. Use native standard CPython 3.14 on Apple Silicon with macOS 15.7 or later:

```sh
python restore_bytecode.py
python -m unittest discover -s tests -v
python build_mac.py --require-market-data --skip-archive
python package_for_friend.py --dmg-only
```

The workflow downloads the pinned data archive, validates its size, checksum, manifest, and all member hashes, then builds the native app and tests its source and bundled executable. Publication runs only after successful app checks, signature validation, architecture validation, and DMG integrity validation. Build reports are retained separately from the public installer.

Keep `~/Library/Application Support/SOL.01/data/manual/` backed up to preserve settings and trades. No mutable data is written into the signed app bundle. For isolated development, `SOL_DATA_HOME` can specify an absolute support directory. Smoke tests use temporary directories.

The synthetic demo is also included at `~/Library/Application Support/SOL.01/demo/SYNTHETIC_DEMO.csv`. CSV and Databento DBN/DBN.ZST loading, replay, buy/sell/flatten, charts, results, and persistence use the original application code.
