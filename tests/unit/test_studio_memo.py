"""The data-epoch memo: derived corpus figures are computed once per import state."""

from __future__ import annotations

from pathlib import Path

from commander_lab.studio import memo
from commander_lab.studio.store import StudioStore


def test_memo_computes_once_and_follows_the_data_epoch(tmp_path: Path) -> None:
    memo.clear()
    store = StudioStore.open(tmp_path)
    store.connection.execute("PRAGMA foreign_keys=OFF")
    calls: list[int] = []

    def compute() -> int:
        calls.append(1)
        return len(calls)

    assert memo.cached(store, "x", ("a",), compute) == 1
    assert memo.cached(store, "x", ("a",), compute) == 1
    assert memo.cached(store, "x", ("b",), compute) == 2
    # a mark is not import data: the entry stays
    store.connection.execute(
        "INSERT INTO card_mark(card_id, favorite, excluded, note, updated_at) "
        "VALUES ('c', 1, 0, '', 't')"
    )
    store.connection.commit()
    assert memo.cached(store, "x", ("a",), compute) == 1
    # an imported source row changes the epoch: recomputed
    store.connection.execute(
        "INSERT INTO source(source_id, data_class, title, sha256, imported_at) "
        "VALUES ('s', 'UNKNOWN', 't', 'h', '2026-01-01T00:00:00Z')"
    )
    store.connection.commit()
    assert memo.cached(store, "x", ("a",), compute) == 3
    store.close()


def test_memo_is_off_for_an_in_memory_store() -> None:
    memo.clear()
    store = StudioStore.in_memory()
    calls: list[int] = []

    def compute() -> int:
        calls.append(1)
        return len(calls)

    assert memo.cached(store, "x", None, compute) == 1
    assert memo.cached(store, "x", None, compute) == 2
