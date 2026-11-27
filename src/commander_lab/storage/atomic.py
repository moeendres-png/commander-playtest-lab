from __future__ import annotations

import json
import os
import tempfile
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

_WINDOWS_SHARING_WINERRORS = frozenset({5, 32})


def replace_file_atomic(
    source: str | Path,
    target: str | Path,
    *,
    max_attempts: int = 20,
    base_delay_seconds: float = 0.005,
) -> None:
    """Atomically replace ``target`` with ``source``, retrying transient Windows sharing errors.

    On Windows, ``os.replace`` raises ``PermissionError`` (WinError 5 / 32) when
    another thread or process briefly holds a read handle on ``target``. Bounded
    retries with short backoff absorb transient reader overlap while failing closed
    on persistent permission errors.
    """
    attempts = max(1, max_attempts) if os.name == "nt" else 1
    for attempt in range(attempts):
        try:
            os.replace(source, target)
            return
        except PermissionError as exc:
            winerror = getattr(exc, "winerror", None)
            if (
                os.name != "nt"
                or attempt + 1 >= attempts
                or (winerror is not None and winerror not in _WINDOWS_SHARING_WINERRORS)
            ):
                raise
            time.sleep(base_delay_seconds * (attempt + 1))


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_write_bytes(path: str | Path, data: bytes, *, mode: int = 0o600) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        dir=target.parent,
    )
    temp_path = Path(temp_name)
    descriptor_open = True

    try:
        fchmod = getattr(os, "fchmod", None)
        if fchmod is not None:
            fchmod(descriptor, mode)

        with os.fdopen(descriptor, "wb") as handle:
            descriptor_open = False
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())

        replace_file_atomic(temp_path, target)
        _fsync_directory(target.parent)
        return target

    except BaseException:
        if descriptor_open:
            with suppress(OSError):
                os.close(descriptor)

        try:
            temp_path.unlink(missing_ok=True)
        finally:
            raise


def atomic_write_text(
    path: str | Path,
    text: str,
    *,
    encoding: str = "utf-8",
    mode: int = 0o600,
) -> Path:
    return atomic_write_bytes(path, text.encode(encoding), mode=mode)


def atomic_write_json(path: str | Path, value: Any, *, mode: int = 0o600) -> Path:
    payload = json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    return atomic_write_text(path, payload, mode=mode)
