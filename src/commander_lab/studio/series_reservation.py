"""An id of a series is claimed with an exclusive file, so two processes never share one (#1707).

A series id carries the start second (``batch-<second>-<deck>``, ``cmp-<second>``). Two processes
on one Studio data folder (the server and a CLI ``simulate``/``compare-decks``, which have no
shared manager and no shared lock) can start in the same second. A running series holds no run
row and no record file until it ends, so neither could see the other's id. The id is therefore
claimed by creating ``<id>.reserve`` in the games folder with ``O_CREAT | O_EXCL``: the operating
system lets exactly one creator win, on POSIX and on Windows alike (no ``fcntl``).

The file is removed when the series ends, however it ends. A process that is killed leaves it
behind; that blocks only this one id (never an unrelated one: ids carry their start second, so a
later series gets another id) and the file is reaped once it is older than
``STALE_AFTER_SECONDS``. A reservation is never overwritten: a taken id means ``False``.
"""

from __future__ import annotations

import contextlib
import json
import os
import time
from collections.abc import Callable
from pathlib import Path

RESERVATION_SUFFIX = ".reserve"
#: A reservation older than this is a leftover of a killed process. The id it names holds a start
#: second that is long past, so no new series can ask for it again; reaping only tidies the folder.
STALE_AFTER_SECONDS = 24 * 3600.0


def reservation_path(folder: Path, series_id: str) -> Path:
    return folder / f"{series_id}{RESERVATION_SUFFIX}"


def try_reserve(folder: Path, series_id: str, *, clock: Callable[[], float] = time.time) -> bool:
    """Claim ``series_id`` in ``folder``: True when this caller now owns it, False when taken."""
    path = reservation_path(folder, series_id)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        return False
    except PermissionError:
        if path.exists():  # Windows reports an existing or just-deleted file as a denied create
            return False
        raise
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump({"pid": os.getpid(), "created_epoch": clock()}, handle)
    return True


def release(folder: Path, series_id: str) -> None:
    """Give the claim back; a missing file is fine (already released or reaped)."""
    with contextlib.suppress(OSError):
        reservation_path(folder, series_id).unlink()


def reap_stale(
    folder: Path,
    *,
    clock: Callable[[], float] = time.time,
    stale_after: float = STALE_AFTER_SECONDS,
) -> list[str]:
    """Remove reservations older than ``stale_after`` seconds; the ids that were reaped."""
    reaped: list[str] = []
    for path in folder.glob(f"*{RESERVATION_SUFFIX}"):
        try:
            age = clock() - path.stat().st_mtime
        except OSError:
            continue
        if age <= stale_after:
            continue
        try:
            path.unlink()
        except OSError:
            continue
        reaped.append(path.name[: -len(RESERVATION_SUFFIX)])
    return sorted(reaped)
