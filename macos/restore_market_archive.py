"""Restore the pinned public NQ data archive into this separate Mac package."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
import zipfile

from market_data import MANIFEST_NAME, YEAR_FOLDER, file_sha256

ROOT = Path(__file__).resolve().parent
ARCHIVE_SIZE = 1498451395
ARCHIVE_SHA256 = "e4dac3ab0baf321ac05f0a9b924506aebbeef8a03ca7f6dc192dd4c8532ffc2c"
MANIFEST_SHA256 = "56317f933f19217d41392d3d29c8e9e347be86182d2072100f09fd7da7477046"
DATASET_ID = "nq-2025-2026-9765e9acc27cbf03"
DATA_FILE_COUNT = 284
DATA_TOTAL_BYTES = 1498349959
MANIFEST_MEMBER = "market_data/" + MANIFEST_NAME


def safe_path(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value or "\x00" in value:
        raise ValueError(f"Invalid archive path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or any(part in {".", "..", ""} for part in value.split("/")):
        raise ValueError(f"Unsafe archive path: {value!r}")
    return path


def target_path(root: Path, name: str) -> Path:
    path = safe_path(name)
    if path.parts[0] != "market_data":
        raise ValueError("Archive can restore only market_data/")
    target = root.joinpath(*path.parts)
    current = root
    for index, part in enumerate(path.parts):
        current = current / part
        if current.is_symlink():
            raise ValueError(f"Refusing to restore through a symlink: {current}")
        if index < len(path.parts) - 1 and current.exists() and not current.is_dir():
            raise ValueError(f"Archive destination parent is not a directory: {current}")
    if not target.resolve().is_relative_to(root):
        raise ValueError("Archive destination escapes the package root")
    return target


def restore_archive(
    archive: Path, root: Path = ROOT, *,
    expected_size: int = ARCHIVE_SIZE, expected_sha256: str = ARCHIVE_SHA256,
    expected_manifest_sha256: str = MANIFEST_SHA256, expected_dataset_id: str = DATASET_ID,
    expected_file_count: int = DATA_FILE_COUNT, expected_total_bytes: int = DATA_TOTAL_BYTES,
) -> dict:
    """Validate all inputs, stage verified absent files, and never overwrite files."""
    archive = Path(archive)
    requested_root = Path(root)
    if archive.is_symlink() or not archive.is_file():
        raise ValueError("Data archive must be a regular file")
    if requested_root.is_symlink():
        raise ValueError("Mac package root cannot be a symlink")
    root = requested_root.resolve()
    if archive.stat().st_size != expected_size or file_sha256(archive) != expected_sha256:
        raise ValueError("Public data archive size or SHA256 differs from the pinned release asset")
    if root.exists() and not root.is_dir():
        raise ValueError("Mac package root must be a directory")
    with zipfile.ZipFile(archive) as bundle:
        entries = bundle.infolist()
        names = [entry.filename for entry in entries]
        if len(names) != len(set(name.casefold() for name in names)) or MANIFEST_MEMBER not in names:
            raise ValueError("Data archive has duplicate names or no market-data manifest")
        for entry in entries:
            safe_path(entry.filename)
            mode = entry.external_attr >> 16
            if entry.is_dir() or entry.flag_bits & 1 or (stat.S_IFMT(mode) and not stat.S_ISREG(mode)):
                raise ValueError("Data archive members must be unencrypted regular files")
            if entry.filename.partition("/")[0] != "market_data":
                raise ValueError("Data archive can contain only market_data/ members")
        manifest_entry = bundle.getinfo(MANIFEST_MEMBER)
        if manifest_entry.file_size > 1024 * 1024:
            raise ValueError("Market-data manifest exceeds the expected size limit")
        manifest_bytes = bundle.read(manifest_entry)
        if hashlib.sha256(manifest_bytes).hexdigest() != expected_manifest_sha256:
            raise ValueError("Market-data manifest SHA256 differs from the pinned input")
        manifest = json.loads(manifest_bytes)
        if not isinstance(manifest, dict) or manifest.get("schema_version") != 1 or manifest.get("folder") != YEAR_FOLDER or manifest.get("dataset_id") != expected_dataset_id:
            raise ValueError("Market-data manifest identity or schema differs from the pinned dataset")
        files = manifest.get("files")
        if not isinstance(files, dict) or len(files) != expected_file_count or manifest.get("file_count") != expected_file_count:
            raise ValueError("Market-data manifest file count differs from the pinned dataset")
        members = {MANIFEST_MEMBER: {"size": len(manifest_bytes), "sha256": expected_manifest_sha256}}
        total_bytes = 0
        for relative, record in files.items():
            safe_path(relative)
            if not isinstance(record, dict) or type(record.get("size")) is not int or record["size"] < 0 or not isinstance(record.get("sha256"), str) or not re.fullmatch("[0-9a-f]{64}", record["sha256"]):
                raise ValueError("Market-data manifest has an invalid file checksum record")
            name = "market_data/" + YEAR_FOLDER + "/" + relative
            members[name] = record
            total_bytes += record["size"]
        if total_bytes != expected_total_bytes or manifest.get("total_bytes") != expected_total_bytes:
            raise ValueError("Market-data byte count differs from the pinned dataset")
        if set(names) != set(members):
            raise ValueError("Data archive contains missing or unexpected members")
        lowered_names = {name.casefold() for name in names}
        for name in names:
            for parent in PurePosixPath(name).parents:
                if parent.as_posix().casefold() in lowered_names:
                    raise ValueError("Data archive has a file/directory name conflict")
        pending = []
        for name, record in sorted(members.items()):
            entry = bundle.getinfo(name)
            if entry.file_size != record["size"]:
                raise ValueError(f"Data archive member size differs from the manifest: {name}")
            target = target_path(root, name)
            if target.exists():
                if not target.is_file() or target.stat().st_size != record["size"] or file_sha256(target) != record["sha256"]:
                    raise ValueError(f"Refusing to replace a different existing data file: {name}")
            else:
                pending.append((name, target, record))
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".market-data-stage-", dir=root) as temporary:
            stage = Path(temporary).resolve()
            if not stage.is_relative_to(root):
                raise ValueError("Temporary extraction directory escaped the package root")
            # Verify extracted bytes in staging before publishing any destination.
            for name, target, record in pending:
                staged = stage.joinpath(*PurePosixPath(name).parts)
                staged.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                size = 0
                with bundle.open(name) as source, staged.open("xb") as output:
                    for block in iter(lambda: source.read(1024 * 1024), b""):
                        size += len(block)
                        digest.update(block)
                        output.write(block)
                if size != record["size"] or digest.hexdigest() != record["sha256"]:
                    raise ValueError(f"Extracted data checksum differs from the manifest: {name}")
            for name, target, record in pending:
                target = target_path(root, name)
                target.parent.mkdir(parents=True, exist_ok=True)
                # Atomic exclusive publication within one filesystem preserves files.
                os.link(stage.joinpath(*PurePosixPath(name).parts), target)
    return {
        "result": "PASS", "archive_sha256": expected_sha256, "archive_size": expected_size,
        "dataset_id": expected_dataset_id, "folder": YEAR_FOLDER,
        "file_count": expected_file_count, "total_bytes": expected_total_bytes,
        "restored_files": len(pending), "existing_identical_files": len(members) - len(pending),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        result = restore_archive(args.archive, args.root)
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        raise SystemExit(f"Market-data archive restoration stopped: {error}") from error
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
