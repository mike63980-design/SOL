"""Restore the unchanged SOL.01 bytecode from verified, text-only build inputs.

This script copies data only; build_mac.py verifies CPython 3.14 before using it.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

ROOT = Path(__file__).resolve().parent
EXPECTED_ARCHIVE_SHA256 = "e6f86b9462462c8964d89acfc365d2a95b961a8e8c383d25b2505d15c8ce9f50"
EXPECTED_ARCHIVE_SIZE = 515056
EXPECTED_BYTECODE_MANIFEST_SHA256 = "fc3bcd84def531eef042c97c2c97e4351ca9e6cf26c0e9c820cf1f313ddd8ca2"
EXPECTED_DEMO_SHA256 = "1a2428b6495c029cdde8d6c44206ca8b56ef36b4b863a4fcd52cb4d0ec4fe007"
EXPECTED_MAGIC = bytes.fromhex("2b0e0d0a")
EXPECTED_MODULE_COUNT = 28
MAX_UNPACKED_BYTES = 16 * 1024 * 1024
HASH_PATTERN = re.compile(r"[0-9a-f]{64}\Z")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_relative(name: str) -> PurePosixPath:
    if not isinstance(name, str) or not name or "\\" in name or ":" in name or "\x00" in name:
        raise ValueError(f"Unsafe payload path: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or path.as_posix() != name or any(part in {".", "..", "__pycache__"} for part in path.parts):
        raise ValueError(f"Unsafe payload path: {name!r}")
    return path


def checked_file(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Expected a regular payload file: {path}")
    return path.read_bytes()


def decode_archive(payload_root: Path) -> bytes:
    manifest = json.loads(checked_file(payload_root / "MANIFEST.json"))
    expected = {
        "format_version": 1,
        "archive_sha256": EXPECTED_ARCHIVE_SHA256,
        "archive_size": EXPECTED_ARCHIVE_SIZE,
        "bytecode_manifest_sha256": EXPECTED_BYTECODE_MANIFEST_SHA256,
        "synthetic_demo_sha256": EXPECTED_DEMO_SHA256,
        "pyc_magic_hex": EXPECTED_MAGIC.hex(),
        "application_module_count": EXPECTED_MODULE_COUNT,
        "restore_script_sha256": digest(Path(__file__).read_bytes()),
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise ValueError(f"Payload manifest does not match the pinned build input: {key}")
    chunks = manifest.get("chunks")
    if not isinstance(chunks, list) or not chunks or len(chunks) > 1024:
        raise ValueError("Payload manifest has no valid chunk list")
    archive_parts = []
    total_size = 0
    for index, chunk in enumerate(chunks, 1):
        expected_name = f"part-{index:04d}.b64"
        if not isinstance(chunk, dict) or chunk.get("name") != expected_name:
            raise ValueError("Payload chunks must be uniquely numbered in order")
        content = checked_file(payload_root / expected_name)
        if digest(content) != chunk.get("text_sha256"):
            raise ValueError(f"Payload text checksum mismatch: {expected_name}")
        try:
            decoded = base64.b64decode(content.strip(), validate=True)
        except (ValueError, binascii.Error) as error:
            raise ValueError(f"Invalid Base64 payload: {expected_name}") from error
        if len(decoded) != chunk.get("size") or digest(decoded) != chunk.get("sha256"):
            raise ValueError(f"Payload chunk checksum mismatch: {expected_name}")
        total_size += len(decoded)
        if total_size > EXPECTED_ARCHIVE_SIZE:
            raise ValueError("Payload archive is larger than the pinned build input")
        archive_parts.append(decoded)
    archive = b"".join(archive_parts)
    if len(archive) != EXPECTED_ARCHIVE_SIZE or digest(archive) != EXPECTED_ARCHIVE_SHA256:
        raise ValueError("Payload archive does not match the pinned build input")
    return archive


def verified_members(archive: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        entries = bundle.infolist()
        names = [entry.filename for entry in entries]
        if len(names) != len(set(names)) or len(names) != EXPECTED_MODULE_COUNT + 2:
            raise ValueError("Bytecode archive has duplicate or unexpected members")
        total_size = 0
        for entry in entries:
            safe_relative(entry.filename)
            if entry.is_dir() or entry.flag_bits & 1 or not stat.S_ISREG(entry.external_attr >> 16):
                raise ValueError(f"Bytecode archive member is not a regular file: {entry.filename}")
            total_size += entry.file_size
            if total_size > MAX_UNPACKED_BYTES:
                raise ValueError("Bytecode archive exceeds the extraction size limit")
        manifest_name = "source/BYTECODE_MANIFEST.json"
        if manifest_name not in names:
            raise ValueError("Original bytecode manifest is missing from the archive")
        manifest_bytes = bundle.read(manifest_name)
        if digest(manifest_bytes) != EXPECTED_BYTECODE_MANIFEST_SHA256:
            raise ValueError("Original bytecode manifest checksum mismatch")
        manifest = json.loads(manifest_bytes)
        files = manifest.get("files")
        if not isinstance(files, dict) or len(files) != EXPECTED_MODULE_COUNT or manifest.get("application_module_count") != EXPECTED_MODULE_COUNT:
            raise ValueError("Original bytecode manifest has an unexpected module list")
        if manifest.get("pyc_magic_hex") != EXPECTED_MAGIC.hex():
            raise ValueError("Original bytecode manifest magic does not match CPython 3.14")
        demo_name = "demo/SYNTHETIC_DEMO.csv"
        expected_names = {manifest_name, demo_name}
        for filename, checksum in files.items():
            relative = safe_relative(filename)
            if relative.suffix != ".pyc" or not isinstance(checksum, str) or not HASH_PATTERN.fullmatch(checksum):
                raise ValueError(f"Invalid original bytecode manifest member: {filename}")
            expected_names.add("source/" + filename)
        if set(names) != expected_names:
            raise ValueError("Bytecode archive does not match the original manifest allowlist")
        demo_bytes = bundle.read(demo_name)
        if digest(demo_bytes) != EXPECTED_DEMO_SHA256:
            raise ValueError("Included synthetic demo checksum mismatch")
        members = {manifest_name: manifest_bytes, demo_name: demo_bytes}
        for filename, checksum in files.items():
            name = "source/" + filename
            content = bundle.read(name)
            if len(content) < 16 or content[:4] != EXPECTED_MAGIC:
                raise ValueError(f"CPython 3.14 bytecode magic mismatch: {filename}")
            if digest(content) != checksum:
                raise ValueError(f"Original bytecode checksum mismatch: {filename}")
            members[name] = content
        return members


def destination(root: Path, name: str) -> Path:
    relative = safe_relative(name)
    path = root.joinpath(*relative.parts)
    current = root
    for index, part in enumerate(relative.parts):
        current = current / part
        if current.is_symlink():
            raise ValueError(f"Refusing to restore through a symlink: {current}")
        if index < len(relative.parts) - 1 and current.exists() and not current.is_dir():
            raise ValueError(f"Restore parent is not a directory: {current}")
    if not path.resolve().is_relative_to(root):
        raise ValueError(f"Restore destination escapes the package root: {path}")
    return path


def restore(root: Path = ROOT, *, payload_root: Path | None = None) -> dict[str, int | str]:
    """Restore only absent files, preserving any identical existing files."""
    requested_root = Path(root)
    if requested_root.is_symlink():
        raise ValueError("Restore package root cannot be a symlink")
    root = requested_root.resolve()
    if root.exists() and not root.is_dir():
        raise ValueError("Restore package root must be a directory")
    payload_root = Path(payload_root) if payload_root is not None else root / "bytecode_payload"
    if payload_root.is_symlink():
        raise ValueError("Bytecode payload directory cannot be a symlink")
    members = verified_members(decode_archive(payload_root))
    pending = []
    # Check all destinations before writing; a differing file never gets replaced.
    for name, content in sorted(members.items()):
        target = destination(root, name)
        if target.exists():
            if not target.is_file() or target.read_bytes() != content:
                raise ValueError(f"Refusing to replace a different existing file: {target}")
        else:
            pending.append((target, content))
    for target, content in pending:
        target.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation also prevents replacing a file created during restore.
        with target.open("xb") as stream:
            stream.write(content)
        if target.read_bytes() != content:
            raise ValueError(f"Restored file verification failed: {target}")
    return {
        "restored_files": len(pending),
        "verified_files": len(members),
        "application_modules": EXPECTED_MODULE_COUNT,
        "archive_sha256": EXPECTED_ARCHIVE_SHA256,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Explicit Mac package destination; defaults to this script's directory.")
    args = parser.parse_args()
    try:
        result = restore(args.root)
    except (ValueError, OSError, zipfile.BadZipFile, json.JSONDecodeError) as error:
        raise SystemExit(f"Bytecode restoration stopped: {error}") from error
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
