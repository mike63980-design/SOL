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


def smoke_test(report: Path) -> int:
    """Exercise original release tests against isolated data, never user trades."""
    import os

    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    report = report.resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix="sol-mac-smoke-") as temporary:
            root = configure(Path(temporary))
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
