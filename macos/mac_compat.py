"""macOS integration for SOL.01's recovered, unmodified application modules."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import sys

BYTECODE_MAGIC = bytes.fromhex("2b0e0d0a")


def check_python() -> None:
    if sys.version_info[:2] != (3, 14) or importlib.util.MAGIC_NUMBER != BYTECODE_MAGIC:
        raise RuntimeError(
            "SOL.01 contains Python 3.14 bytecode. Use standard CPython 3.14 "
            "with bytecode magic 2b0e0d0a to run or build this edition."
        )


def resource_root() -> Path:
    # __file__ resolves inside the bundle when frozen, and beside launch.py otherwise.
    return Path(__file__).resolve().parent


def support_root() -> Path:
    override = os.environ.get("SOL_DATA_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / "Library" / "Application Support" / "SOL.01"


def configure(root: Path | None = None) -> Path:
    """Keep all app writes outside the .app; preserve replay/trading code verbatim."""
    check_python()
    root = (root or support_root()).resolve()
    (root / "data" / "manual").mkdir(parents=True, exist_ok=True)
    (root / "data" / "cache").mkdir(parents=True, exist_ok=True)
    (root / "data" / "nq_ticks").mkdir(parents=True, exist_ok=True)
    (root / "demo").mkdir(parents=True, exist_ok=True)
    demo = root / "demo" / "SYNTHETIC_DEMO.csv"
    if not demo.exists():
        shutil.copyfile(resource_root() / "demo" / demo.name, demo)
    os.environ["SOL_SETTINGS_PATH"] = str(root / "data" / "manual" / "app_settings.json")
    os.environ["IDLE_TRADER_DB"] = str(root / "data" / "manual" / "manual.sqlite")

    import idle_trader.gui as gui
    import idle_trader.manual_app as manual

    # These two modules derive project_dir from __file__.parents[2]. Redirect only
    # their resource-root globals; import specs and executable code stay intact.
    # Do not create or write into a signed application bundle, even on first launch.
    gui.__file__ = str(root / "source" / "idle_trader" / "gui.py")
    manual.__file__ = str(root / "source" / "idle_trader" / "manual_app.py")

    if not getattr(manual.ManualWindow, "_sol_mac_guide", False):
        original_build = manual.ManualWindow._build

        def build_with_mac_guide(window):
            original_build(window)
            guide = window.instructions.toHtml().replace("Ctrl + scroll", "Command + scroll")
            # Qt's ControlModifier maps to Command on macOS, so no event remapping
            # is needed. Expose the demo location and native persistent-data path.
            from html import escape

            guide += (
                "<p><b>Included demo:</b> Use Load File to open "
                + escape(str(window.project_dir / "demo" / "SYNTHETIC_DEMO.csv"))
                + ".</p><p><b>Saved data:</b> "
                + escape(str(window.project_dir / "data" / "manual"))
                + "</p>"
            )
            window.instructions.setHtml(guide)

        manual.ManualWindow._build = build_with_mac_guide
        manual.ManualWindow._sol_mac_guide = True
    return root
