from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from commander_lab.storage.atomic import atomic_write_text

DEFAULT_LOG_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_LOG_BACKUP_COUNT = 3


def rotate_runtime_log(
    path: str | Path,
    *,
    max_bytes: int = DEFAULT_LOG_MAX_BYTES,
    backup_count: int = DEFAULT_LOG_BACKUP_COUNT,
) -> None:
    target = Path(path)
    if max_bytes < 1 or backup_count < 1:
        raise ValueError("max_bytes and backup_count must be positive")
    if not target.exists() or target.stat().st_size < max_bytes:
        return

    oldest = target.with_name(f"{target.name}.{backup_count}")
    oldest.unlink(missing_ok=True)
    for index in range(backup_count - 1, 0, -1):
        source = target.with_name(f"{target.name}.{index}")
        if source.exists():
            source.replace(target.with_name(f"{target.name}.{index + 1}"))
    target.replace(target.with_name(f"{target.name}.1"))


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_runtime_attestation(
    *,
    provider: str,
    engine_version: str,
    protocol_version: str,
    pid: int,
    runtime_kind: str,
    start_executable: str,
) -> dict[str, Any]:
    executable = Path(start_executable)
    executable_sha256 = _file_sha256(executable) if executable.is_file() else None
    return {
        "provider": provider,
        "engine_version": engine_version,
        "protocol_version": protocol_version,
        "pid": pid,
        "runtime_kind": runtime_kind,
        "start_executable": start_executable,
        "start_executable_sha256": executable_sha256,
        "observed_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "semantic_validation_granted": False,
        "note": (
            "Runtime attestation proves the observed process identity only; it does not "
            "grant external rules-engine semantic validation."
        ),
    }


def write_runtime_attestation(path: str | Path, value: dict[str, Any]) -> Path:
    target = Path(path)
    payload = json.dumps(value, indent=2, sort_keys=True) + "\n"
    atomic_write_text(target, payload)
    return target


__all__ = [
    "DEFAULT_LOG_BACKUP_COUNT",
    "DEFAULT_LOG_MAX_BYTES",
    "build_runtime_attestation",
    "rotate_runtime_log",
    "write_runtime_attestation",
]
