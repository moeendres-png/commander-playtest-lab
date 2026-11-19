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
from collections.abc import Callable, Hashable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import cast

from . import memo
from .store import StudioStore

MAX_ENTRIES = 64
# Limits of one kind of entry (the first element of the caller's key): at most so many entries
# and, for ``bytes`` values, so many bytes in total. ``answer``: the remembered JSON answers of
# the read routes (``answer_cache``), whose parameters can vary freely (a search query); they
# push out older answers, not the warm figures. The total limit was raised from 48 by the 16
# answer entries, so the figures keep the room they had.
KIND_LIMITS: dict[str, tuple[int, int]] = {"answer": (16, 48 * 1024 * 1024)}
_lock = threading.Lock()
_entries: OrderedDict[tuple[Hashable, ...], object] = OrderedDict()


class _KeyLock:
    """The lock of one key in flight and how many callers hold or wait for it."""

    __slots__ = ("lock", "users")

    def __init__(self) -> None:
        self.lock = threading.RLock()  # re-entrant: a computation may ask for its own key
        self.users = 0


_flights: dict[tuple[Hashable, ...], _KeyLock] = {}
_local = threading.local()


@contextmanager
def read_only() -> Iterator[None]:
    """Within this block of the calling thread ``cached`` still serves what is remembered, but
    remembers nothing new. For one-off sweeps (the data report counts every commander of the
    store) whose many entries would push the warm figures of the working commander out of the
    size limit."""
    before = getattr(_local, "read_only", False)
    _local.read_only = True
    try:
        yield
    finally:
        _local.read_only = before


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
    first computation instead of repeating it.

    Lock order: a computation may ask for other keys (lower levels) but must never be asked for
    back by those (no callback to a higher level), so the key locks form a strict hierarchy and
    two calls cannot wait for each other. Today: ``strength``/``layer_overview``/package sets
    call ``corpus_hits``/``corpus_deck_sets``/``cohort_shapes``, never the other way round."""
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
            if getattr(_local, "read_only", False):
                return value
            # The state may have changed while computing; remember only if it is still the same.
            if store_stamp(store) == stamp:
                with _lock:
                    # Entries of another state of this very file are not served for the
                    # current one: drop them now instead of letting large values wait for
                    # the size limit.
                    for old in [
                        k
                        for k in _entries
                        if isinstance(k[0], tuple) and k[0][:1] == stamp[:1] and k[0] != stamp
                    ]:
                        del _entries[old]
                    _entries[full] = value
                    _apply_kind_limit(full)
                    while len(_entries) > MAX_ENTRIES:
                        _entries.popitem(last=False)
            return value
    finally:
        with _lock:
            flight.users -= 1
            if flight.users == 0 and _flights.get(full) is flight:
                del _flights[full]


def _apply_kind_limit(full: tuple[Hashable, ...]) -> None:
    """Drop the oldest entries of ``full``'s kind beyond its ``KIND_LIMITS`` (never ``full``
    itself). Called with ``_lock`` held."""
    kind = full[1] if len(full) > 1 else None
    if not isinstance(kind, str) or kind not in KIND_LIMITS:
        return
    max_count, max_bytes = KIND_LIMITS[kind]
    same = [k for k in _entries if len(k) > 1 and k[1] == kind]
    total = sum(len(v) for k in same if isinstance(v := _entries[k], bytes))
    for old in same[:-1]:
        if len(same) <= max_count and total <= max_bytes:
            break
        value = _entries.pop(old)
        same.remove(old)
        if isinstance(value, bytes):
            total -= len(value)


def invalidate() -> None:
    """Forget every cached figure, this module's and the data-epoch memo's (``memo.py``)."""
    with _lock:
        _entries.clear()
    memo.clear()


__all__ = ["cached", "invalidate", "store_stamp"]
