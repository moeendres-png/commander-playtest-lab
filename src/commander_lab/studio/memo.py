"""A small in-process memo for read-only derivations over the imported source data.

The expensive figures of the builder and the tier list (corpus counts per card, the decks
behind every card name) depend only on the imported data, not on marks, drafts or saved decks.
A request opens a fresh store each time, so without a memo every call repeated minutes of
counting over the whole corpus. The key is the store file plus its *data epoch*: a fingerprint
of the import tables, so a re-import, a relink or an edited universe profile changes it and the
entry is recomputed. Marks, notes, drafts and decks are not part of it (a favourite must not
cost seconds). A store without a file (in memory) is never memoized.

The epoch itself costs a pass over the largest tables (about 55 ms on the full Chulane store,
measured 2026-11-14), and every request opens a new connection. It is therefore remembered per
store file for as long as the file and its write-ahead log are unchanged (modification time
and size). A file written less than ``_STAT_GUARD_NS`` ago is never trusted (coarse file
clocks), nor is a connection that has written itself: both read the epoch from the tables.

What the epoch can and cannot see: every import registers its file as a source row bound to
the content hash, so an import of changed data always adds a source row and changes the
epoch. A change made to existing import rows by hand (plain SQL, no importer) can keep counts
and row ids as they were and is not seen; ``clear()`` or a restart drops the memo.

The file check relies on a local data folder (the default). On a network or synced folder a
file's time and size can be reported late, and an import made from another machine is then
seen late as well.

Size: at most ``_MAX_ENTRIES`` entries in total and at most ``_MAX_PER_NAME`` entries of one
kind. The large kind is ``universe_decks`` (the decks behind every card name of one universe:
7.5 MB serialized for the 2,823 Chulane decks, measured 2026-11-14, and a few times that in
memory), so it is held for 8 universes at most.

Cached values are shared between callers and must be treated as read-only."""

from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Hashable

from .store import StudioStore

_MAX_ENTRIES = 64
_MAX_PER_NAME: dict[str, int] = {"universe_decks": 8}
_STAT_GUARD_NS = 2_000_000_000
_cache: OrderedDict[tuple[str, object, str, Hashable], object] = OrderedDict()
_epochs: dict[str, tuple[tuple[object, ...], tuple[object, ...]]] = {}
_lock = threading.Lock()


def clear() -> None:
    with _lock:
        _cache.clear()
        _epochs.clear()


def _signature(path: str) -> tuple[object, ...] | None:
    """Modification time and size of the store file and its write-ahead log, or ``None``
    while the newest of them is too fresh to be trusted."""
    parts: list[tuple[int, int] | None] = []
    newest = 0
    for suffix in ("", "-wal", "-journal"):
        try:
            found = os.stat(path + suffix)
        except OSError:
            parts.append(None)
            continue
        parts.append((found.st_mtime_ns, found.st_size))
        newest = max(newest, found.st_mtime_ns)
    if time.time_ns() - newest < _STAT_GUARD_NS:
        return None
    return tuple(parts)


def _epoch(store: StudioStore) -> tuple[object, ...]:
    """The data epoch of ``store``, read from the tables only when the file changed."""
    path = str(store.path)
    wrote = store.connection.in_transaction or store.connection.total_changes > 0
    signature = None if wrote else _signature(path)
    if signature is not None:
        with _lock:
            known = _epochs.get(path)
        if known is not None and known[0] == signature:
            return known[1]
    epoch = store.data_epoch()
    if signature is not None:
        with _lock:
            _epochs[path] = (signature, epoch)
    return epoch


def cached[T](store: StudioStore, name: str, args: Hashable, compute: Callable[[], T]) -> T:
    """``compute()`` once per (store file, data epoch, name, args)."""
    if store.path is None:
        return compute()
    key = (str(store.path), _epoch(store), name, args)
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]  # type: ignore[return-value]
    value = compute()
    with _lock:
        _cache[key] = value
        limit = _MAX_PER_NAME.get(name)
        if limit is not None:
            same = [item for item in _cache if item[2] == name]
            for old in same[: max(0, len(same) - limit)]:
                del _cache[old]
        while len(_cache) > _MAX_ENTRIES:
            _cache.popitem(last=False)
    return value
