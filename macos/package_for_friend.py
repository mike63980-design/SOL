"""Package a successfully built native app into a Mac installer for sharing."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def run(command: list[str]) -> None:
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, check=True)


def checksum(path: Path) -> None:
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    path.with_suffix(path.suffix + ".sha256").write_text(
        f"{digest}  {path.name}\n", encoding="utf-8"
    )


def select_output(requested: Path | None) -> Path:
    if requested:
        output = requested.resolve()
    else:
        candidates = sorted(
            path.parent for path in (ROOT / "dist").glob("*/BUILD_PROVENANCE.json")
            if path.parent.name.startswith(platform.machine() + "-")
        )
        if not candidates:
            raise SystemExit("Build the native Mac app first with build_mac.py.")
        output = candidates[-1]
    if not output.is_relative_to(ROOT / "dist"):
        raise SystemExit("Choose a build output inside this package's dist directory.")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-output", type=Path)
    parser.add_argument("--dmg-only", action="store_true", help="Create a single disk-image download.")
    args = parser.parse_args()
    if sys.platform != "darwin":
        raise SystemExit("A finished Mac installer must be packaged on macOS.")
    output = select_output(args.build_output)
    provenance = json.loads((output / "BUILD_PROVENANCE.json").read_text(encoding="utf-8"))
    if provenance["architecture"] != platform.machine():
        raise SystemExit("The app architecture differs from the native packaging host.")
    for filename in ("SOURCE_SMOKE_TEST.json", "BUNDLE_SMOKE_TEST.json"):
        report = json.loads((output / filename).read_text(encoding="utf-8"))
        if report.get("result") != "PASS" or not report.get("mac_integration", {}).get("native_macos_verified"):
            raise SystemExit(f"Native application verification did not pass: {filename}")
    app = output / "SOL.01.app"
    if not (app / "Contents" / "MacOS" / "SOL.01").is_file():
        raise SystemExit("The self-contained SOL.01.app is missing.")
    run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)])
    run(["/usr/bin/lipo", str(app / "Contents" / "MacOS" / "SOL.01"), "-verify_arch", provenance["architecture"]])

    chip = "Apple M4 / Apple Silicon" if provenance["architecture"] == "arm64" else "Intel"
    market = provenance.get("market_data")
    historical_start = (
        f"The app includes {market['file_count']} NQ historical data files. First launch\n"
        "prepares them in ~/Library/Application Support/SOL.01/data/nq_ticks/\n"
        "2025-2026 Year/. This may take a little time. Click Load File to choose\n"
        "a day from that folder, then use Play for historical replay.\n"
    ) if market else "Load your tick CSV or Databento DBN/DBN.ZST files with Load File.\n"
    instructions = (
        "SOL.01 — Manual Historical Replay\n\n"
        f"Requires macOS {provenance['minimum_macos']} or later on {chip}.\n\n"
        "INSTALL\n"
        "1. Open the SOL.01 disk image (.dmg).\n"
        "2. Drag SOL.01.app to the Applications shortcut.\n"
        "3. Open SOL.01 from Applications, then eject the disk image.\n"
        + ("\n" if args.dmg_only else "For the ZIP download, extract it and drag SOL.01.app to Applications.\n\n")
        +
        "Python and the app's libraries are already included. No programming,\n"
        "Python installation, broker login, or online setup is needed.\n\n"
        "FIRST OPEN\n"
        "This personal build has not been notarized by Apple. If macOS blocks it\n"
        "because the developer cannot be verified, follow Apple's instructions\n"
        "for an app you trust: System Settings > Privacy & Security > Open Anyway.\n"
        "https://support.apple.com/en-us/102445\n\n"
        "START\n"
        "Open the Instructions tab for the full guide.\n"
        + historical_start +
        "An optional synthetic demo is in\n"
        "~/Library/Application Support/SOL.01/demo/SYNTHETIC_DEMO.csv.\n"
        "Use Play, BUY MKT, SELL MKT and FLATTEN for historical replay and simulated\n"
        "trading.\n"
        "Command + scroll zooms chart prices.\n\n"
        "SAVED TRADES\n"
        "Settings and trades are stored in:\n"
        "~/Library/Application Support/SOL.01/data/manual/\n"
        "Back up this folder when replacing the app.\n\n"
        "The app uses local simulation and does not place real broker orders.\n"
    )
    (output / "INSTALL.txt").write_text(instructions, encoding="utf-8")
    stage = ROOT / ".build" / provenance["build_id"] / "friend-installer"
    if stage.exists():
        raise SystemExit("This build was already staged. Use a fresh build output to avoid replacing files.")
    stage.mkdir(parents=True)
    run(["/usr/bin/ditto", str(app), str(stage / app.name)])
    (stage / "Applications").symlink_to("/Applications", target_is_directory=True)
    (stage / "INSTALL.txt").write_text(instructions, encoding="utf-8")
    # Zip and DMG contain the finished .app and instructions, without build sources.
    label = "Apple-M4-with-NQ-Data" if market and provenance["architecture"] == "arm64" else provenance["architecture"]
    name = f"SOL.01-macOS-{label}-{provenance['version']}"
    dmg = output / (name + ".dmg")
    run(["/usr/bin/hdiutil", "create", "-volname", "SOL.01", "-srcfolder", str(stage), "-format", "UDZO", str(dmg)])
    run(["/usr/bin/hdiutil", "verify", str(dmg)])
    checksum(dmg)
    files = [dmg.name, "INSTALL.txt"]
    if not args.dmg_only:
        download = output / (name + "-Ready-to-Run.zip")
        run(["/usr/bin/ditto", "-c", "-k", "--sequesterRsrc", str(stage), str(download)])
        checksum(download)
        files.append(download.name)
    (output / "DOWNLOADS.json").write_text(json.dumps({
        "application": "SOL.01", "version": provenance["version"],
        "architecture": provenance["architecture"],
        "minimum_macos": provenance["minimum_macos"],
        "self_contained": True, "python_installation_required": False,
        "native_smoke_tests_passed": True,
        "notarized": False, "files": files, "market_data": market,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Finished Mac installer:\n{dmg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
