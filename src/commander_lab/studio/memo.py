"""A small in-process memo for read-only derivations over the imported source data.

The expensive figures of the builder and the tier list (corpus counts per card, the decks
behind every card name) depend only on the imported data, not on marks, drafts or saved decks.
A request opens a fresh store each time, so without a memo every call repeated minutes of
counting over the whole corpus. The key is the store file plus its *data epoch*: a fingerprint
of the import tables, so a re-import, a relink or an edited universe profile changes it and the
entry is recomputed. Marks, notes, drafts and decks are not part of it (a favourite must not
cost seconds). A store without a file (in memory) is never memoized.

Cached values are shared between callers and must be treated as read-only."""

from __future__ import annotations

import threading
from collections import OrderedDict
from collections.abc import Callable, Hashable

from .store import StudioStore

_MAX_ENTRIES = 64
_cache: OrderedDict[Hashable, object] = OrderedDict()
_lock = threading.Lock()


def clear() -> None:
    with _lock:
        _cache.clear()


def cached[T](store: StudioStore, name: str, args: Hashable, compute: Callable[[], T]) -> T:
    """``compute()`` once per (store file, data epoch, name, args)."""
    if store.path is None:
        return compute()
    key = (str(store.path), store.data_epoch(), name, args)
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]  # type: ignore[return-value]
    value = compute()
    with _lock:
        _cache[key] = value
        while len(_cache) > _MAX_ENTRIES:
            _cache.popitem(last=False)
    return value
