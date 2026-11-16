"""list_rows must not leave a transaction open: the per-state cache would stand aside."""

from __future__ import annotations

from pathlib import Path

from commander_lab.studio import StudioStore, cache
from commander_lab.studio.decks import RevisionCard, list_rows


def _store(tmp_path: Path) -> StudioStore:
    from tests.unit.test_studio_builder import _fill

    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    return store


def test_list_rows_closes_its_temp_transaction_so_the_cache_serves(tmp_path: Path) -> None:
    store = _store(tmp_path)
    rows = list_rows(store, [RevisionCard("card:project:0001", 1, "commander")])
    assert [row["card_id"] for row in rows] == ["card:project:0001"]
    assert store.connection.in_transaction is False
    calls: list[int] = []

    def compute() -> int:
        calls.append(1)
        return 7

    assert cache.cached(store, ("list-rows-test",), compute) == 7
    list_rows(store, [RevisionCard("card:project:0001", 1, "commander")])
    assert cache.cached(store, ("list-rows-test",), compute) == 7
    assert calls == [1]


def test_list_rows_inside_an_open_transaction_commits_nothing(tmp_path: Path) -> None:
    store = _store(tmp_path)
    db = store.connection
    db.execute("UPDATE inventory SET reserved = reserved WHERE card_id = 'card:project:0001'")
    db.execute("INSERT INTO meta(key, value) VALUES ('pending-test', 'x')")
    assert db.in_transaction is True
    list_rows(store, [RevisionCard("card:project:0001", 1, "commander")])
    assert db.in_transaction is True
    db.rollback()
    assert db.execute("SELECT 1 FROM meta WHERE key = 'pending-test'").fetchone() is None
