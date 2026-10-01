"""Validate and install the optional, manifest-listed historical data payload."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile

MANIFEST_NAME = "MARKET_DATA_MANIFEST.json"
YEAR_FOLDER = "2025-2026 Year"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _relative_path(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value or ":" in value or "\x00" in value:
        raise ValueError(f"Invalid dataset relative path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in value.split("/")):
        raise ValueError(f"Unsafe dataset relative path: {value!r}")
    return path.as_posix()


def load_manifest(payload: Path) -> dict | None:
    """Read the optional manifest, rejecting unsafe or inconsistent entries."""
    payload = payload.resolve()
    path = payload / MANIFEST_NAME
    if not path.is_file():
        if payload.exists():
            raise ValueError(f"Market data is present without {MANIFEST_NAME}: {payload}")
        return None
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("Unsupported market-data manifest schema; expected schema_version 1.")
    if not isinstance(manifest.get("dataset_id"), str) or not manifest["dataset_id"].strip():
        raise ValueError("The market-data manifest requires a dataset_id.")
    if manifest.get("folder") != YEAR_FOLDER:
        raise ValueError(f"The dataset folder must be {YEAR_FOLDER!r}.")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("The market-data manifest has no files.")
    canonical = set()
    total_bytes = 0
    for relative, record in files.items():
        _relative_path(relative)
        lowered = relative.casefold()
        if lowered in canonical:
            raise ValueError(f"Case-insensitive filename collision in market data: {relative}")
        canonical.add(lowered)
        if not isinstance(record, dict) or not isinstance(record.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", record["sha256"]):
            raise ValueError(f"Invalid SHA256 record: {relative}")
        if type(record.get("size")) is not int or record["size"] < 0:
            raise ValueError(f"Invalid size record: {relative}")
        total_bytes += record["size"]
    for relative in canonical:
        for parent in PurePosixPath(relative).parents:
            if parent.as_posix() != "." and parent.as_posix() in canonical:
                raise ValueError(f"File/directory conflict in dataset: {relative}")
    if manifest.get("file_count") != len(files) or manifest.get("total_bytes") != total_bytes:
        raise ValueError("Market-data manifest file_count or total_bytes is inconsistent.")
    return manifest


def payload_files(payload: Path, manifest: dict) -> list[tuple[str, Path]]:
    payload = payload.resolve()
    directory = payload / manifest["folder"]
    paths = []
    for relative in sorted(manifest["files"]):
        path = directory.joinpath(*PurePosixPath(relative).parts)
        if not path.resolve().is_relative_to(payload):
            raise ValueError(f"Dataset path resolves outside its payload: {relative}")
        paths.append((relative, path))
    return paths


def verify_payload(payload: Path, *, required: bool = False) -> dict | None:
    """Fully verify all packaged bytes before a native release build."""
    manifest = load_manifest(payload)
    if manifest is None:
        if required:
            raise ValueError(f"This full-data release requires {payload / MANIFEST_NAME}.")
        return None
    for relative, path in payload_files(payload, manifest):
        record = manifest["files"][relative]
        if not path.is_file() or path.stat().st_size != record["size"] or file_sha256(path) != record["sha256"]:
            raise ValueError(f"Market-data file is missing or differs from its manifest: {relative}")
    return manifest


@dataclass(frozen=True)
class InstallResult:
    folder: Path
    dataset_id: str
    file_count: int
    total_bytes: int
    copied: int
    preserved: int
    already_installed: bool


def _ensure_local_directory(directory: Path, root: Path) -> None:
    """Do not follow existing user symlinks while installing into support data."""
    if not directory.is_relative_to(root):
        raise ValueError("The market-data destination escaped Application Support.")
    current = root
    for part in directory.relative_to(root).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"Market-data installation cannot write through a symlink: {current}")
        if current.exists() and not current.is_dir():
            raise ValueError(f"A file occupies the market-data installation directory: {current}")
        current.mkdir(exist_ok=True)


def _copy_verified_once(source: Path, destination: Path, record: dict) -> bool:
    """Publish a verified complete copy atomically, without replacing any user file."""
    if destination.exists() or destination.is_symlink():
        return False
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".sol01-data-", dir=destination.parent, delete=False) as output:
            temporary = Path(output.name)
            digest = hashlib.sha256()
            size = 0
            with source.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
                    size += len(block)
                    output.write(block)
        if size != record["size"] or digest.hexdigest() != record["sha256"]:
            raise ValueError(f"Bundled market data differs from its manifest: {source.name}")
        try:
            os.link(temporary, destination)
        except FileExistsError:
            return False
        return True
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def install_payload(payload: Path, support: Path) -> InstallResult | None:
    """Copy a dataset once outside the app; preserve all existing destination files."""
    manifest = load_manifest(payload)
    if manifest is None:
        return None
    support = support.resolve()
    support.mkdir(parents=True, exist_ok=True)
    parent = support / "data" / "nq_ticks"
    folder = parent / manifest["folder"]
    manifest_hash = file_sha256(payload / MANIFEST_NAME)
    receipt = parent / ".sol01-market-data" / (manifest_hash + ".json")
    folder_existed = folder.is_dir()
    _ensure_local_directory(parent, support)
    _ensure_local_directory(folder, support)
    if folder_existed and receipt.is_file() and not receipt.is_symlink():
        try:
            previous = json.loads(receipt.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            previous = {}
        if isinstance(previous, dict) and previous.get("manifest_sha256") == manifest_hash and previous.get("dataset_id") == manifest["dataset_id"]:
            return InstallResult(folder, manifest["dataset_id"], manifest["file_count"], manifest["total_bytes"], 0, manifest["file_count"], True)
    copied = preserved = 0
    # Preflight every destination parent before making any file copies.
    sources = payload_files(payload, manifest)
    for relative, source in sources:
        destination = folder.joinpath(*PurePosixPath(relative).parts)
        _ensure_local_directory(destination.parent, support)
    for relative, source in sources:
        destination = folder.joinpath(*PurePosixPath(relative).parts)
        if _copy_verified_once(source, destination, manifest["files"][relative]):
            copied += 1
        else:
            preserved += 1
    _ensure_local_directory(receipt.parent, support)
    summary = {
        "dataset_id": manifest["dataset_id"], "manifest_sha256": manifest_hash,
        "folder": str(folder), "file_count": manifest["file_count"],
        "total_bytes": manifest["total_bytes"], "copied": copied, "preserved": preserved,
    }
    # The receipt is installer bookkeeping. Do not overwrite an existing path.
    try:
        with receipt.open("x", encoding="utf-8") as output:
            json.dump(summary, output, indent=2)
            output.write("\n")
    except FileExistsError:
        pass
    return InstallResult(folder, manifest["dataset_id"], manifest["file_count"], manifest["total_bytes"], copied, preserved, False)


def set_default_data_folder(settings: Path, support: Path, resources: Path, folder: Path) -> bool:
    """Redirect default/demo/invalid selections while retaining valid custom folders."""
    if not settings.is_file():
        return False  # Original prepare_manual_settings creates the complete defaults.
    try:
        raw = json.loads(settings.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return False
    if not isinstance(raw, dict):
        return False
    selected = raw.get("data_folder")
    choice = Path(selected).expanduser() if isinstance(selected, str) and selected.strip() else None
    defaults = {(support / "data" / "nq_ticks").resolve(), (support / "demo").resolve(), (resources / "demo").resolve()}
    if choice is not None and choice.is_dir() and choice.resolve() not in defaults:
        return False
    raw["data_folder"] = str(folder)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", prefix=".sol01-settings-", dir=settings.parent, delete=False) as output:
            temporary = Path(output.name)
            json.dump(raw, output, indent=2)
            output.write("\n")
        os.replace(temporary, settings)
        return True
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
