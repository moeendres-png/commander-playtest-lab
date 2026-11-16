"""In-process cache of derived Studio figures, valid exactly as long as the store is unchanged.

A request opens its own connection, so a result cannot be kept on the connection. A cached
value is keyed by the store file's *stamp* — its path, SQLite's file change counter (bumped by
every committed write transaction), size and modification time — plus the caller's own key, so
any import, profile write or mark change that commits makes the next request recompute. An
open transaction (uncommitted changes of this very connection) and an in-memory store bypass
the cache: nothing stale can be served. ``invalidate`` drops everything explicitly (used after
profile writes, where the stamp would catch it anyway).

Concurrent identical requests share one computation: per key one caller computes while the
others wait for it (``_KeyLock``), so a page that fires two routes needing the same figure
pays for it once. A failed computation caches nothing; the next waiter computes itself.
"""

from __future__ import annotations

import os
import threading
from collections import OrderedDict
from collections.abc import Callable, Hashable
from pathlib import Path
from typing import cast

from . import memo
from .store import StudioStore

MAX_ENTRIES = 48
_lock = threading.Lock()
_entries: OrderedDict[tuple[Hashable, ...], object] = OrderedDict()


class _KeyLock:
    """The lock of one key in flight and how many callers hold or wait for it."""

    __slots__ = ("lock", "users")

    def __init__(self) -> None:
        self.lock = threading.RLock()  # re-entrant: a computation may ask for its own key
        self.users = 0


_flights: dict[tuple[Hashable, ...], _KeyLock] = {}


def store_stamp(store: StudioStore) -> tuple[str, int, int, int, int, int] | None:
    """Identity of the committed state of the store file, or ``None`` when it cannot be
    vouched for (in-memory store, open transaction, unreadable file)."""
    path = store.path
    if path is None or store.connection.in_transaction:
        return None
    try:
        with Path(path).open("rb") as handle:
            header = handle.read(100)
        counter = int.from_bytes(header[24:28], "big")
        stat = os.stat(path)
        wal = Path(f"{path}-wal")
        try:
            wal_stat = wal.stat()
            wal_size, wal_mtime = wal_stat.st_size, wal_stat.st_mtime_ns
        except OSError:
            wal_size, wal_mtime = 0, 0
    except OSError:
        return None
    return (str(path), counter, stat.st_size, stat.st_mtime_ns, wal_size, wal_mtime)


def cached[T](store: StudioStore, key: tuple[Hashable, ...], compute: Callable[[], T]) -> T:
    """``compute()``, remembered per store state and ``key``. The caller must treat the
    returned value as read-only. Concurrent calls for the same state and key wait for the
    first computation instead of repeating it."""
    stamp = store_stamp(store)
    if stamp is None:
        return compute()
    full = (stamp, *key)
    with _lock:
        if full in _entries:
            _entries.move_to_end(full)
            return cast("T", _entries[full])
        flight = _flights.get(full)
        if flight is None:
            flight = _flights[full] = _KeyLock()
        flight.users += 1
    try:
        with flight.lock:
            with _lock:
                if full in _entries:  # the caller we waited for has filled it
                    _entries.move_to_end(full)
                    return cast("T", _entries[full])
            value = compute()
            # The state may have changed while computing; remember only if it is still the same.
            if store_stamp(store) == stamp:
                with _lock:
                    _entries[full] = value
                    while len(_entries) > MAX_ENTRIES:
                        _entries.popitem(last=False)
            return value
    finally:
        with _lock:
            flight.users -= 1
            if flight.users == 0 and _flights.get(full) is flight:
                del _flights[full]


def invalidate() -> None:
    """Forget every cached figure, this module's and the data-epoch memo's (``memo.py``)."""
    with _lock:
        _entries.clear()
    memo.clear()


__all__ = ["cached", "invalidate", "store_stamp"]
