from __future__ import annotations

import json
import os
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Any


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

        os.replace(temp_path, target)
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
