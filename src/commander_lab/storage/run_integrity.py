from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import stat
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath
from typing import Any

from .atomic import atomic_write_json


@dataclass(frozen=True)
class RunVerification:
    valid: bool
    status: str
    errors: tuple[str, ...]
    checked_files: int


_MANIFEST_NAME = "run-manifest.json"
_STATUSES = {"completed", "failed", "aborted", "incomplete"}


def _artifact_paths(root: Path) -> dict[str, Path]:
    """Inventory regular artifacts in a quiescent tree, without following links."""
    files: dict[str, Path] = {}

    def unreadable(error: OSError) -> None:
        raise error

    for directory, directories, names in os.walk(root, onerror=unreadable, followlinks=False):
        directories[:] = sorted(name for name in directories if name != ".quarantine")
        for name in directories:
            child = Path(directory) / name
            if child.is_symlink() or child.is_junction():
                raise ValueError("run contains a linked directory")
        for name in sorted(names):
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            if relative == _MANIFEST_NAME or name == ".quarantine":
                continue
            if not stat.S_ISREG(path.lstat().st_mode):
                raise ValueError("run contains a non-regular artifact")
            files[relative] = path
    return files


def _identity(info: os.stat_result) -> tuple[int, ...]:
    identity = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
    # Windows Python 3.12 path stat and descriptor stat can expose different
    # ctime values for the same unchanged file. Keep file ID/size/mtime there;
    # POSIX ctime additionally detects observed metadata changes.
    return identity if os.name == "nt" else (*identity, info.st_ctime_ns)


def _snapshot(path: Path) -> tuple[int, str]:
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("artifact must be a regular file")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(path, flags), "rb") as handle:
        opened = os.fstat(handle.fileno())
        if not stat.S_ISREG(opened.st_mode) or _identity(before) != _identity(opened):
            raise ValueError("artifact changed before reading")
        digest = hashlib.sha256()
        size = 0
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            size += len(chunk)
            digest.update(chunk)
        if (
            size != opened.st_size
            or _identity(opened) != _identity(os.fstat(handle.fileno()))
            or _identity(opened) != _identity(path.lstat())
        ):
            raise ValueError("artifact changed while reading")
    return size, digest.hexdigest()


def sha256_file(path: Path) -> str:
    return _snapshot(path)[1]


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON member")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError("non-finite JSON value")


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("non-finite JSON value")
    return parsed


def _validate_manifest(manifest: Any) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    if type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
        raise ValueError("unsupported manifest schema_version")
    if not isinstance(manifest.get("run_id"), str) or not manifest["run_id"].strip():
        raise ValueError("manifest run_id must be nonempty text")
    status = manifest.get("status")
    if not isinstance(status, str) or status not in _STATUSES:
        raise ValueError("unknown manifest status")
    if not isinstance(manifest.get("metadata"), dict):
        raise ValueError("manifest metadata must be an object")
    created_at = manifest.get("created_at")
    if not isinstance(created_at, str) or datetime.fromisoformat(created_at).tzinfo is None:
        raise ValueError("manifest created_at must be a timezone-aware timestamp")
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise ValueError("manifest files must be an object")
    for relative, record in files.items():
        if (
            not isinstance(relative, str)
            or "\\" in relative
            or "\x00" in relative
            or PureWindowsPath(relative).drive
            or any(part in {"", ".", "..", ".quarantine"} for part in relative.split("/"))
            or relative == _MANIFEST_NAME
        ):
            raise ValueError("manifest path must be a canonical relative artifact path")
        if not isinstance(record, dict):
            raise ValueError("manifest file record must be an object")
        size, digest = record.get("size"), record.get("sha256")
        if type(size) is not int or size < 0:
            raise ValueError("manifest file size must be a nonnegative integer")
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError("manifest file hash must be a SHA-256 hex digest")
    return files


def create_run_manifest(
    run_directory: str | Path,
    *,
    run_id: str,
    status: str,
    metadata: dict[str, Any],
) -> Path:
    root = Path(run_directory).resolve()
    root.mkdir(parents=True, exist_ok=True)
    files: dict[str, dict[str, Any]] = {}
    inventory = _artifact_paths(root)
    for relative, path in sorted(inventory.items()):
        size, digest = _snapshot(path)
        files[relative] = {"sha256": digest, "size": size}
    if inventory != _artifact_paths(root):
        raise ValueError("artifact inventory changed while sealing")
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "status": status,
        "created_at": datetime.now(UTC).isoformat(),
        "metadata": metadata,
        "files": files,
    }
    _validate_manifest(manifest)
    # Refuse non-JSON/non-finite metadata before replacing an existing seal.
    json.loads(json.dumps(manifest, allow_nan=False), object_pairs_hook=_unique_object)
    return atomic_write_json(root / _MANIFEST_NAME, manifest)


def verify_run(run_directory: str | Path) -> RunVerification:
    checked = 0
    try:
        root = Path(run_directory).resolve()
        manifest_path = root / _MANIFEST_NAME
        try:
            manifest_stat = manifest_path.lstat()
        except FileNotFoundError:
            return RunVerification(False, "incomplete", ("run-manifest.json is missing",), 0)
        if not stat.S_ISREG(manifest_stat.st_mode):
            raise ValueError("manifest must be a regular file")
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_invalid_constant,
            parse_float=_finite_float,
        )
        files = _validate_manifest(manifest)
        inventory = _artifact_paths(root)
        errors = [f"unlisted file: {name}" for name in sorted(inventory.keys() - files.keys())]
        errors.extend(f"missing file: {name}" for name in sorted(files.keys() - inventory.keys()))
        for relative in sorted(files.keys() & inventory.keys()):
            size, digest = _snapshot(inventory[relative])
            checked += 1
            if size != files[relative]["size"]:
                errors.append(f"size mismatch: {relative}")
            if digest != files[relative]["sha256"]:
                errors.append(f"hash mismatch: {relative}")
        if inventory != _artifact_paths(root) or _identity(manifest_stat) != _identity(
            manifest_path.lstat()
        ):
            errors.append("run inventory or manifest changed during verification")
    except (OSError, ValueError, UnicodeError, RecursionError):
        # Never leak raw artifact contents, decoder snippets or external paths.
        return RunVerification(
            False, "corrupt", ("invalid or unreadable run manifest/artifacts",), checked
        )
    valid = not errors and manifest.get("status") == "completed"
    status = (
        "valid"
        if valid
        else ("incomplete" if manifest.get("status") == "incomplete" else "corrupt")
    )
    return RunVerification(valid, status, tuple(errors), checked)


def quarantine_run(run_directory: str | Path, quarantine_root: str | Path) -> Path:
    source = Path(run_directory).resolve()
    destination_root = Path(quarantine_root).resolve()
    destination_root.mkdir(parents=True, exist_ok=True)
    destination = destination_root / source.name
    suffix = 1
    while destination.exists():
        suffix += 1
        destination = destination_root / f"{source.name}-{suffix}"
    shutil.move(str(source), str(destination))
    return destination
