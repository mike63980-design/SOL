# Build through build_mac.py so notices and provenance are generated first.
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys

from PyInstaller.utils.hooks import collect_data_files, copy_metadata

ROOT = Path(SPECPATH).resolve()
sys.path.insert(0, str(ROOT))
from market_data import MANIFEST_NAME, file_sha256, payload_files, verify_payload
SOURCE = ROOT / "source"
MAGIC = bytes.fromhex("2b0e0d0a")
if sys.platform != "darwin" or sys.version_info[:2] != (3, 14):
    raise SystemExit("SOL.01.app must be built on macOS with CPython 3.14.")
if importlib.util.MAGIC_NUMBER != MAGIC:
    raise SystemExit("This Python build does not match the recovered SOL.01 bytecode magic (2b0e0d0a).")
ARCH = platform.machine()
if ARCH not in {"arm64", "x86_64"}:
    raise SystemExit(f"Unsupported native macOS architecture: {ARCH}")
if os.environ.get("SOL_TARGET_ARCH", ARCH) != ARCH:
    raise SystemExit("Use a native Python environment for each architecture; cross-architecture builds are disabled.")

resources_value = os.environ.get("SOL_BUILD_RESOURCES")
if not resources_value:
    raise SystemExit("Run build_mac.py; SOL_BUILD_RESOURCES is required.")
RESOURCES = Path(resources_value).resolve()
if not RESOURCES.is_relative_to(ROOT / ".build"):
    raise SystemExit("Build resources must be inside this kit's .build directory.")
for required in (RESOURCES / "THIRD_PARTY_LICENSES", RESOURCES / "BUILD_PROVENANCE.json", ROOT / "demo" / "SYNTHETIC_DEMO.csv"):
    if not required.exists():
        raise SystemExit(f"Missing build resource: {required}")
build_provenance = json.loads((RESOURCES / "BUILD_PROVENANCE.json").read_text(encoding="utf-8"))
package_version = build_provenance["version"]

# Bytecode files are importable in their legacy sourceless layout. Explicitly
# analyze every recovered module so dynamic imports and the normal Qt hooks work.
hiddenimports = []
for filename in sorted(SOURCE.rglob("*.pyc")):
    relative = filename.relative_to(SOURCE).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    if parts:
        hiddenimports.append(".".join(parts))
if "idle_trader.manual_app" not in hiddenimports or "sol_manual_entry" not in hiddenimports:
    raise SystemExit("Recovered SOL.01 application modules are missing from source/.")
hiddenimports.extend(["PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets", "tzdata"])

datas = [
    (str(ROOT / "demo"), "demo"),
    (str(RESOURCES / "THIRD_PARTY_LICENSES"), "THIRD_PARTY_LICENSES"),
    (str(RESOURCES / "BUILD_PROVENANCE.json"), "."),
    (str(RESOURCES / "requirements-resolved.txt"), "."),
    (str(SOURCE / "BYTECODE_MANIFEST.json"), "."),
]
if (ROOT / "PROVENANCE.json").is_file():
    datas.append((str(ROOT / "PROVENANCE.json"), "."))
try:
    market_manifest = verify_payload(ROOT / "market_data", required=os.environ.get("SOL_REQUIRE_MARKET_DATA") == "1")
except (ValueError, OSError) as error:
    raise SystemExit(f"Market-data verification failed: {error}") from error
if market_manifest is not None:
    market_path = ROOT / "market_data" / MANIFEST_NAME
    recorded = build_provenance.get("market_data") or {}
    if recorded.get("manifest_sha256") != file_sha256(market_path) or not recorded.get("fully_verified_before_build"):
        raise SystemExit("Market-data provenance is missing or differs from the verified dataset.")
    datas.append((str(market_path), "market_data"))
    for relative, filename in payload_files(ROOT / "market_data", market_manifest):
        destination = Path("market_data") / market_manifest["folder"] / Path(relative).parent
        datas.append((str(filename), destination.as_posix()))
datas += collect_data_files("tzdata")
# Preserve package version/metadata lookups in the recovered application and SDK.
for distribution in ("PySide6", "numpy", "pandas", "pyarrow", "databento", "databento-dbn", "holidays", "python-dotenv", "requests", "zstandard", "tzdata"):
    datas += copy_metadata(distribution, recursive=True)

a = Analysis(
    [str(ROOT / "launch.py")],
    pathex=[str(ROOT), str(SOURCE)],
    binaries=[],
    datas=datas,
    hiddenimports=sorted(set(hiddenimports)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt5", "PyQt6", "PySide2", "pip_system_certs", "win32ctypes"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SOL.01",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=ARCH,
    codesign_identity=os.environ.get("SOL_CODESIGN_IDENTITY") or None,
    entitlements_file=os.environ.get("SOL_ENTITLEMENTS_FILE") or None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="SOL.01")
app = BUNDLE(
    coll,
    name="SOL.01.app",
    bundle_identifier="org.sol.manual",
    info_plist={
        "CFBundleName": "SOL.01",
        "CFBundleDisplayName": "SOL.01",
        "CFBundleShortVersionString": package_version,
        "CFBundleVersion": package_version,
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": os.environ.get("SOL_MIN_MACOS", "13.0"),
    },
)
