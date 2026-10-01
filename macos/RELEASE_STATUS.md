# Mac release status

**The finished, self-contained SOL.01 0.1.0 manual edition DMG for Apple M4 is available in
[`../SOL.01-macOS-Downloads/`](../SOL.01-macOS-Downloads/).** The friend can install
the app directly; Python, programming tools, and a build step are not required.

Download [SOL.01-macOS-Apple-M4-0.1.0.dmg](https://github.com/mike63980-design/SOL/releases/download/v0.1.0-macos-m4/SOL.01-macOS-Apple-M4-0.1.0.dmg).
It contains the native Apple Silicon ARM64 application and requires macOS 15.7
or later. This is the only installer in the current delivery.

The DMG contains `SOL.01.app`, an Applications shortcut, and installation
instructions. The delivery folder also contains separate instructions, SHA-256
checksum files, and the release verification record. Open the DMG, drag the app
to Applications, and open it from there.

The permanent public release is available at
[v0.1.0-macos-m4](https://github.com/mike63980-design/SOL/releases/tag/v0.1.0-macos-m4).
The repository is public, and the installer downloads without a GitHub login.
Release ID `401361625` contains one Apple M4 DMG and its optional checksum file.
The publisher [workflow run 36927325227](https://github.com/mike63980-design/SOL/actions/runs/36927325227)
completed successfully. An anonymous request returned HTTP 200 with the expected
114,915,789-byte installer. The installer is the verified Apple Silicon build with
an Apple M4 filename; its bytes and SHA-256 are unchanged:
`cee634483bcb6799e3c7e704de193f163aa0114f003616ef33fabd5fb1231c06`.

## Completed native verification

Both native jobs in [GitHub Actions run 36920122088](https://github.com/mike63980-design/SOL/actions/runs/36920122088)
passed on October 1, 2026, from commit
`f688fcb732680806b75d31da78b2d371cf628abe` on `macos-release` in the then-private
`mike63980-design/SOL` repository. The repository's original `main` branch was
preserved separately. The two architecture jobs are historical verification;
only the Apple Silicon app is included in the current Apple M4 delivery.

The builds used macOS 15.7.9 and standard CPython 3.14.7, and both record macOS
15.7 as their minimum system. Original application checks passed against the
recovered modules and the finished native executable: startup, instructions,
CSV/DBN and compressed DBN decoding, replay, simulated BUY/SELL entry and exit,
SQLite persistence, saved results, and chart rendering. The build jobs also
verified native architecture, ad hoc app signatures, and DMG integrity.

These automated app tests used Qt's offscreen platform. Interactive Finder/Cocoa
launch, trackpad gestures, and Gatekeeper behavior have not been tested, including
on M4 hardware. The delivered build is ad hoc signed and **not Apple notarized**.
A recipient may need Apple's
one-time [Open Anyway](https://support.apple.com/en-us/102445) procedure for an app
they trust.

See [`RELEASE_VERIFICATION.json`](../SOL.01-macOS-Downloads/RELEASE_VERIFICATION.json)
and the delivery folder's `verification/` reports for exact build IDs, hashes,
and test results. The retained delivery consists of one Apple M4 DMG. Ready-to-run ZIPs were
also created on the build machines but were not retained as downloads; the
original per-build `DOWNLOADS.json` records what was produced there.

## Windows preservation and maintainer files

All 1,761 files listed in the packaged Windows release manifest still match
their original SHA-256 checksums. The Mac app uses the same 28 recovered
application bytecode modules, with separate Mac libraries, paths, and packaging.
It ships the synthetic demo and no personal settings, saved trades, or market
archives.

This `SOL.01-macOS/` folder contains the maintained build inputs. Its README
separates recipient installation from maintainer rebuilding. The earlier
`SOL.01-macOS-Build-Kit.zip` is a maintainer build kit, not an installer to send
to the friend. The finished Apple M4 DMG is in the separate delivery folder above.
The public GitHub release is published. Only Apple Silicon native CI artifacts
are retained; the earlier Intel artifacts were removed from the native build run.
