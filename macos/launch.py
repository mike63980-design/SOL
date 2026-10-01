"""Native macOS launcher; original SOL.01 logic lives in source/*.pyc."""

from __future__ import annotations

import argparse
import gc
import json
import multiprocessing
from pathlib import Path
import sys
import tempfile
import traceback
from types import SimpleNamespace

from mac_compat import check_python, configure, resource_root
from market_data import MANIFEST_NAME, YEAR_FOLDER, file_sha256, install_payload, load_manifest


def verify_installed_market_data(root: Path, manifest: dict) -> dict:
    """Check installed bytes and replay a bounded sample using original app code."""
    from idle_trader.data import load_tick_file
    from idle_trader.replay import ReplayController
    import math

    folder = root / "data" / "nq_ticks" / manifest["folder"]
    if folder.resolve().is_relative_to(resource_root().resolve()):
        raise RuntimeError("Historical data was installed inside the application bundle")
    expected = set(manifest["files"])
    installed = {path.relative_to(folder).as_posix() for path in folder.rglob("*") if path.is_file()}
    if installed != expected:
        raise RuntimeError("Installed historical-data files differ from the bundled manifest")
    for relative, record in manifest["files"].items():
        path = folder / relative
        if path.stat().st_size != record["size"] or file_sha256(path) != record["sha256"]:
            raise RuntimeError(f"Installed historical-data integrity check failed: {relative}")
    if manifest["file_count"] != 284 or manifest["total_bytes"] != 1498349959:
        raise RuntimeError("The full-data release does not contain the expected 284-file historical library")
    if any(Path(name).name.startswith("[USED] ") or name.endswith(".USED") for name in installed):
        raise RuntimeError("Legacy used flags remain in the installed historical library")
    repeated = install_payload(resource_root() / "market_data", root)
    if repeated is None or not repeated.already_installed or repeated.copied != 0:
        raise RuntimeError("Historical data was copied again after its first installation")

    # Christmas is a small actual DBN (37 KB). An explicit contract avoids any
    # continuous-contract lookup of surrounding days or whole-year loading.
    sample_name = "glbx-mdp3-20251225.trades.dbn.zst"
    if sample_name not in expected:
        raise RuntimeError("The bounded historical-data verification sample is missing")
    sample = folder / sample_name
    if sample.stat().st_size > 1024 * 1024:
        raise RuntimeError("The historical replay verification sample exceeds its size bound")
    data = load_tick_file(sample, contract="NQH6")
    if len(data) != 2192 or data.source_symbol != "NQH6":
        raise RuntimeError("The original DBN loader did not resolve the expected NQH6 historical sample")
    count = 32
    replay = ReplayController(data, start=0, end=count)
    ticks = replay.step(count)
    if len(ticks) != count or replay.index != count or not replay.done or replay.step(1):
        raise RuntimeError("The original replay controller did not honor the 32-tick verification bound")
    if any(not math.isfinite(tick.price) or tick.price <= 0 or tick.contract != "NQH6" for tick in ticks):
        raise RuntimeError("The historical replay produced an invalid price or contract")
    if any(ticks[index].ts > ticks[index + 1].ts for index in range(count - 1)):
        raise RuntimeError("The historical replay timestamps are not ordered")
    return {
        "dataset_id": manifest["dataset_id"], "manifest_sha256": file_sha256(resource_root() / "market_data" / MANIFEST_NAME),
        "included_files": manifest["file_count"], "included_bytes": manifest["total_bytes"],
        "installed_files": len(installed), "installed_files_sha256_verified": True,
        "installed_folder": str(folder), "installed_outside_bundle": True,
        "default_load_file_folder": str(folder), "default_folder_verified_in_window": True,
        "auto_load_data": False, "copy_once_verified": True,
        "legacy_used_flags_removed": True, "retained_bad_files": sum(name.startswith("bad/") for name in installed),
        "actual_dbn_replay": {
            "filename": sample_name, "compressed_bytes": sample.stat().st_size,
            "contract": data.source_symbol, "loaded_ticks": len(data), "replayed_ticks": len(ticks),
            "bounded_replay_complete": replay.done, "first_timestamp_utc": ticks[0].ts.isoformat(),
            "last_replayed_timestamp_utc": ticks[-1].ts.isoformat(),
        },
    }


def smoke_test(report: Path) -> int:
    """Exercise original release tests against isolated data, never user trades."""
    import os

    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    report = report.resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="sol-mac-smoke-") as temporary:
            root = configure(Path(temporary))
            market_manifest = load_manifest(resource_root() / "market_data")
            import idle_trader.manual_app as manual
            import sol_manual_entry as entry

            # The original smoke runner looks beside sys.executable for its demo.
            # Replace its private global reference, leaving the actual sys module
            # and PyInstaller/multiprocessing executable path untouched.
            entry.sys = SimpleNamespace(
                executable=str(root / "SOL.01"),
                frozen=bool(getattr(sys, "frozen", False)),
                argv=sys.argv,
            )
            original_grab = manual.ManualWindow.grab

            def capture(window, *args, **kwargs):
                assert window.project_dir == root
                assert window.storage.path == root / "data" / "manual" / "manual.sqlite"
                assert "Command + scroll" in window.instructions.toPlainText()
                if market_manifest is not None:
                    year_folder = root / "data" / "nq_ticks" / YEAR_FOLDER
                    assert window._data_folder().resolve() == year_folder.resolve()
                    assert not window.sol_settings.auto_load_data
                    assert str(year_folder) in window.instructions.toPlainText()
                pixmap = original_grab(window, *args, **kwargs)
                if not pixmap.save(str(report.with_suffix(".png"))):
                    raise RuntimeError("Could not save smoke-test window capture")
                return pixmap

            manual.ManualWindow.grab = capture
            try:
                result = entry.smoke_test(report)
            finally:
                manual.ManualWindow.grab = original_grab
                # sqlite3's context manager commits without closing a connection.
                # Release cycles left by the original test before deleting its DB.
                gc.collect()
            details = json.loads(report.read_text(encoding="utf-8"))
            if result != 0 or details.get("result") != "PASS":
                raise RuntimeError("Original application smoke tests did not pass")
            if market_manifest is not None:
                details["market_data"] = verify_installed_market_data(root, market_manifest)
            provenance_path = resource_root() / "BUILD_PROVENANCE.json"
            details["package_version"] = json.loads(provenance_path.read_text(encoding="utf-8"))["version"] if provenance_path.is_file() else "0.1.1"
            details["mac_integration"] = {
                "writable_data_outside_bundle": True,
                "isolated_test_database": True,
                "command_key_guide": True,
                "window_capture": report.with_suffix(".png").name,
                "test_host": sys.platform,
                "native_macos_verified": sys.platform == "darwin",
            }
            report.write_text(json.dumps(details, indent=2), encoding="utf-8")
            return 0
    except Exception:
        report.write_text(
            json.dumps({"result": "FAIL", "error": traceback.format_exc()}, indent=2),
            encoding="utf-8",
        )
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="SOL.01 for macOS")
    parser.add_argument("--smoke-test", type=Path, metavar="REPORT.json")
    args = parser.parse_args()
    check_python()
    if not getattr(sys, "frozen", False):
        sys.path.insert(0, str(resource_root() / "source"))
    if args.smoke_test:
        return smoke_test(args.smoke_test)
    if sys.platform != "darwin":
        parser.error("This launcher targets macOS. Use --smoke-test for Windows verification.")
    configure()
    from idle_trader.manual_app import main as original_main

    return original_main()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
