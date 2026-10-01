# SOL.01 for Apple M4

**[Download SOL.01 for Apple M4](https://github.com/mike63980-design/SOL/releases/download/v0.1.0-macos-m4/SOL.01-macOS-Apple-M4-0.1.0.dmg)**

SOL.01 0.1.0 manual historical replay, packaged for an Apple Silicon MacBook with an **M4 chip**. Requires **macOS 15.7 or later**. Python and all required libraries are included.

1. Download and open the `.dmg` above.
2. Drag **SOL.01.app** to **Applications**.
3. Open SOL.01 from Applications, then eject the disk image.

This personal build has not been notarized by Apple. If the first launch is blocked because the developer cannot be verified, try opening the app, then choose **System Settings > Privacy & Security > Open Anyway**. [Apple's instructions](https://support.apple.com/en-us/102445).

Open the app's **Instructions** tab for the controls. The included synthetic demo is copied to `~/Library/Application Support/SOL.01/demo/SYNTHETIC_DEMO.csv`. Settings and saved trades are stored in `~/Library/Application Support/SOL.01/data/manual/`.

Native Mac automated tests passed for startup, CSV/DBN loading, replay, manual buy/sell, saved trades, and chart rendering. The native app signature and disk image were verified. Interactive first launch, trackpad gestures, and Gatekeeper were not tested.

The supplied Windows program remains unchanged. Personal settings, saved trades, and market archives are not included in this Mac download.

[Release page and checksum](https://github.com/mike63980-design/SOL/releases/tag/v0.1.0-macos-m4)
