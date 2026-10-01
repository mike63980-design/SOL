"""Build a native SOL.01.app from the recovered CPython 3.14 modules."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import subprocess
import sys
import sysconfig
import os
import venv

ROOT = Path(__file__).resolve().parent
MAGIC = bytes.fromhex("2b0e0d0a")
APP_VERSION = "0.1.0"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(command: list[str], *, env: dict[str, str] | None = None, capture: bool = False) -> subprocess.CompletedProcess:
    print("+ " + " ".join(command), flush=True)
    return subprocess.run(command, cwd=ROOT, env=env, check=True, text=True, capture_output=capture)


def validate_host() -> str:
    if sys.platform != "darwin":
        raise SystemExit("Build SOL.01.app on a Mac. Windows cannot build the native macOS libraries or app bundle.")
    if sys.implementation.name != "cpython" or sys.version_info[:2] != (3, 14):
        raise SystemExit("Use CPython 3.14 (python3.14). The recovered program is Python 3.14 bytecode.")
    if importlib.util.MAGIC_NUMBER != MAGIC:
        raise SystemExit(f"Python bytecode magic {importlib.util.MAGIC_NUMBER.hex()} differs from SOL.01's required 2b0e0d0a.")
    if sysconfig.get_config_var("Py_GIL_DISABLED"):
        raise SystemExit("Use standard CPython 3.14, not the experimental free-threaded Python build.")
    arch = platform.machine()
    if arch not in {"arm64", "x86_64"}:
        raise SystemExit(f"Unsupported architecture: {arch}. Use native arm64 or x86_64 Python.")
    # Rosetta reports x86_64 even on Apple Silicon. Keep each build genuinely native.
    translated = subprocess.run(["/usr/sbin/sysctl", "-in", "sysctl.proc_translated"], text=True, capture_output=True)
    if translated.returncode == 0 and translated.stdout.strip() == "1":
        raise SystemExit("This Python process is running under Rosetta. Use native arm64 Python on Apple Silicon; build Intel on an Intel Mac.")
    version = platform.mac_ver()[0]
    minimum_version = (13, 0)
    if tuple(int(part) for part in version.split(".")[:2]) < minimum_version:
        raise SystemExit(f"The pinned Qt runtime requires macOS {minimum_version[0]} or newer on {arch}. Use a supported build Mac.")
    return arch


def validate_payload() -> dict[str, str]:
    files = sorted((ROOT / "source").rglob("*.pyc"))
    if not files:
        raise SystemExit("Recovered bytecode is missing from source/.")
    for path in files:
        if path.read_bytes()[:4] != MAGIC:
            raise SystemExit(f"Bytecode magic mismatch: {path}")
    manifest_path = ROOT / "source" / "BYTECODE_MANIFEST.json"
    if not manifest_path.is_file():
        raise SystemExit("The recovered bytecode manifest is missing from source/.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_hashes = manifest.get("files", {})
    actual_hashes = {path.relative_to(ROOT / "source").as_posix(): sha256(path) for path in files}
    if manifest.get("pyc_magic_hex") != MAGIC.hex() or expected_hashes != actual_hashes:
        raise SystemExit("Recovered bytecode does not match source/BYTECODE_MANIFEST.json. Restore the unchanged build kit.")
    license_files = [ROOT / "LICENSE_TEXTS" / "GPL-3.0.txt", ROOT / "LICENSE_TEXTS" / "LGPL-3.0.txt", ROOT / "LICENSE_TEXTS" / "QT_NOTICE.md"]
    for path in (ROOT / "source" / "idle_trader" / "__init__.pyc", ROOT / "source" / "sol_manual_entry.pyc", ROOT / "launch.py", ROOT / "mac_compat.py", ROOT / "demo" / "SYNTHETIC_DEMO.csv", *license_files):
        if not path.is_file():
            raise SystemExit(f"Required build input is missing: {path}")
    inputs = files + license_files + [manifest_path, ROOT / "launch.py", ROOT / "mac_compat.py", ROOT / "build_mac.py", ROOT / "build_mac.command", ROOT / "SOL.01.spec", ROOT / "requirements-macos.txt", ROOT / "requirements-build.txt", ROOT / "demo" / "SYNTHETIC_DEMO.csv"]
    return {path.relative_to(ROOT).as_posix(): sha256(path) for path in inputs}


def collect_notices(destination: Path) -> None:
    """Use RECORD entries from this build's installed native distributions."""
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("GPL-3.0.txt", "LGPL-3.0.txt", "QT_NOTICE.md"):
        shutil.copy2(ROOT / "LICENSE_TEXTS" / name, destination / name)
    summaries = []
    for distribution in sorted(importlib.metadata.distributions(), key=lambda item: item.metadata.get("Name", "").lower()):
        name = distribution.metadata.get("Name", "unknown")
        directory = destination / re.sub(r"[^A-Za-z0-9_.-]", "_", name)
        directory.mkdir(exist_ok=True)
        metadata = distribution.read_text("METADATA")
        if metadata:
            (directory / "METADATA.txt").write_text(metadata, encoding="utf-8")
        copied = []
        for relative in distribution.files or []:
            parts = PurePosixPath(str(relative)).parts
            if not parts or ".." in parts or PurePosixPath(str(relative)).is_absolute():
                continue
            lower = [part.lower() for part in parts]
            basename = lower[-1]
            if "__pycache__" in lower or Path(basename).suffix in {".py", ".pyi", ".pyc", ".pyo", ".so", ".dylib", ".pyd"}:
                continue
            is_notice = any(part in {"licenses", "licences"} for part in lower) or basename.startswith(("license", "licence", "copying", "notice", "copyright", "authors"))
            if not is_notice:
                continue
            original = Path(distribution.locate_file(relative))
            if not original.is_file():
                continue
            target = directory.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, target)
            copied.append(str(relative))
        summaries.append({"name": name, "version": distribution.version, "license_expression": distribution.metadata.get("License-Expression"), "license_files": copied})
    (destination / "INDEX.json").write_text(json.dumps(summaries, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codesign-identity", help="Optional installed Developer ID Application certificate name.")
    parser.add_argument("--entitlements", type=Path, help="Optional entitlements plist for that signing identity.")
    parser.add_argument("--_collect-notices", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    arch = validate_host()
    if args._collect_notices:
        if sys.prefix == sys.base_prefix:
            raise SystemExit("Collect notices using the isolated build virtual environment.")
        collect_notices(args._collect_notices.resolve())
        return 0
    source_hashes = validate_payload()
    if args.entitlements and not args.codesign_identity:
        parser.error("--entitlements requires --codesign-identity.")
    if args.entitlements and not args.entitlements.resolve().is_file():
        parser.error("The entitlements file does not exist.")

    environment_path = ROOT / ".venv"
    python = environment_path / "bin" / "python"
    if not environment_path.exists():
        print(f"Creating isolated Python environment: {environment_path}", flush=True)
        venv.EnvBuilder(with_pip=True).create(environment_path)
    if not python.is_file():
        raise SystemExit(".venv is not a macOS Python environment. Move it aside and rerun on this Mac.")
    probe = run([str(python), "-I", "-c", "import sys,platform,importlib.util,json; print(json.dumps([sys.version_info[:2],platform.machine(),importlib.util.MAGIC_NUMBER.hex(),sys.platform]))"], capture=True)
    if json.loads(probe.stdout) != [[3, 14], arch, MAGIC.hex(), "darwin"]:
        raise SystemExit(".venv belongs to a different Python version or architecture. Move it aside and rebuild it on this Mac.")

    run([str(python), "-m", "pip", "--isolated", "install", "--only-binary=:all:", "-r", str(ROOT / "requirements-build.txt"), "-r", str(ROOT / "requirements-macos.txt")])
    run([str(python), "-m", "pip", "check"])
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    build_id = f"{arch}-{stamp}"
    work = ROOT / ".build" / build_id
    resources = work / "resources"
    output = ROOT / "dist" / build_id
    resources.mkdir(parents=True)
    output.mkdir(parents=True)
    run([str(python), str(ROOT / "build_mac.py"), "--_collect-notices", str(resources / "THIRD_PARTY_LICENSES")])
    freeze = run([str(python), "-m", "pip", "freeze", "--all"], capture=True).stdout
    (resources / "requirements-resolved.txt").write_text(freeze, encoding="utf-8")
    version_code = "import importlib.metadata,json; print(json.dumps({d.metadata['Name']:d.version for d in importlib.metadata.distributions()}))"
    dependencies = json.loads(run([str(python), "-I", "-c", version_code], capture=True).stdout)
    minimum_macos = ".".join(platform.mac_ver()[0].split(".")[:2])
    provenance = {
        "name": "SOL.01", "version": APP_VERSION, "edition": "manual",
        "platform": "macOS", "architecture": arch, "build_id": build_id,
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "bytecode_magic": MAGIC.hex(),
        "build_macos": platform.mac_ver()[0], "minimum_macos": minimum_macos,
        "bundle_identifier": "org.sol.manual", "dependencies": dependencies,
        "input_sha256": source_hashes, "codesigning": "Developer ID" if args.codesign_identity else "ad-hoc",
        "notarized": False,
    }
    (resources / "BUILD_PROVENANCE.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    env = os.environ.copy()
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)
    env.update({"SOL_TARGET_ARCH": arch, "SOL_BUILD_RESOURCES": str(resources), "SOL_MIN_MACOS": minimum_macos})
    if args.codesign_identity:
        env["SOL_CODESIGN_IDENTITY"] = args.codesign_identity
    else:
        env.pop("SOL_CODESIGN_IDENTITY", None)
    if args.entitlements:
        env["SOL_ENTITLEMENTS_FILE"] = str(args.entitlements.resolve())
    else:
        env.pop("SOL_ENTITLEMENTS_FILE", None)
    smoke_env = env | {"QT_QPA_PLATFORM": "offscreen"}
    run([str(python), str(ROOT / "launch.py"), "--smoke-test", str(output / "SOURCE_SMOKE_TEST.json")], env=smoke_env)
    run([str(python), "-m", "PyInstaller", "--noconfirm", "--distpath", str(output), "--workpath", str(work / "pyinstaller"), str(ROOT / "SOL.01.spec")], env=env)
    app = output / "SOL.01.app"
    executable = app / "Contents" / "MacOS" / "SOL.01"
    if not executable.is_file():
        raise SystemExit(f"PyInstaller did not produce the expected executable: {executable}")
    if not any(app.rglob("libqcocoa.dylib")):
        raise SystemExit("The macOS Qt platform plugin libqcocoa.dylib is missing from the application bundle.")
    run([str(executable), "--smoke-test", str(output / "BUNDLE_SMOKE_TEST.json")], env=smoke_env)
    run(["/usr/bin/codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app)])
    run(["/usr/bin/lipo", "-verify_arch", arch, str(executable)])
    shutil.copy2(resources / "BUILD_PROVENANCE.json", output / "BUILD_PROVENANCE.json")
    shutil.copy2(resources / "requirements-resolved.txt", output / "requirements-resolved.txt")
    archive = output / f"SOL.01-macOS-{arch}-{APP_VERSION}.zip"
    run(["/usr/bin/ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(app), str(archive)])
    checksum = sha256(archive)
    (archive.with_suffix(".zip.sha256")).write_text(f"{checksum}  {archive.name}\n", encoding="utf-8")
    print(f"\nCreated {app}\nCreated {archive}\nSHA256 {checksum}\nSmoke tests and bundle signature verification passed. Test Finder launch before distribution.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        if error.stdout:
            print(error.stdout, file=sys.stderr)
        if error.stderr:
            print(error.stderr, file=sys.stderr)
        raise SystemExit(f"Build stopped: command returned exit code {error.returncode}. No successful release is reported.")
