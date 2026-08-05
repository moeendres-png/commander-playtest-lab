from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .atomic import atomic_write_json


@dataclass(frozen=True)
class RunVerification:
    valid: bool
    status: str
    errors: tuple[str, ...]
    checked_files: int


def _safe_relative(path: Path, root: Path) -> str:
    resolved = path.resolve()
    root_resolved = root.resolve()
    try:
        return resolved.relative_to(root_resolved).as_posix()
    except ValueError as exc:
        raise ValueError(f"path escapes run directory: {path}") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "run-manifest.json" or ".quarantine" in path.parts:
            continue
        relative = _safe_relative(path, root)
        files[relative] = {"sha256": sha256_file(path), "size": path.stat().st_size}
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "status": status,
        "created_at": datetime.now(UTC).isoformat(),
        "metadata": metadata,
        "files": files,
    }
    return atomic_write_json(root / "run-manifest.json", manifest)


def verify_run(run_directory: str | Path) -> RunVerification:
    root = Path(run_directory).resolve()
    manifest_path = root / "run-manifest.json"
    errors: list[str] = []
    if not manifest_path.is_file():
        return RunVerification(False, "incomplete", ("run-manifest.json is missing",), 0)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return RunVerification(False, "corrupt", (f"invalid manifest: {exc}",), 0)
    if manifest.get("status") not in {"completed", "failed", "aborted", "incomplete"}:
        errors.append("unknown manifest status")
    files = manifest.get("files")
    if not isinstance(files, dict):
        return RunVerification(False, "corrupt", ("manifest files must be an object",), 0)
    checked = 0
    for relative, expected in files.items():
        path = (root / relative).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            errors.append(f"manifest path escapes run directory: {relative}")
            continue
        if not path.is_file():
            errors.append(f"missing file: {relative}")
            continue
        checked += 1
        if path.stat().st_size != expected.get("size"):
            errors.append(f"size mismatch: {relative}")
        if sha256_file(path) != expected.get("sha256"):
            errors.append(f"hash mismatch: {relative}")
    valid = not errors and manifest.get("status") == "completed"
    status = "valid" if valid else ("incomplete" if manifest.get("status") == "incomplete" else "corrupt")
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
