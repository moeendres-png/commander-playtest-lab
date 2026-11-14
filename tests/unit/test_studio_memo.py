"""The in-process memo of derived figures: fresh after an import of changed data, the data
epoch read from the tables only when the store file changed, a size limit per kind."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from commander_lab.studio import builder, importers, memo
from commander_lab.studio.store import StudioStore
from tests.unit.test_studio_builder import _fill
from tests.unit.test_studio_store import _card_row, _write_csv

COMMANDER = ["Test Commander"]


@pytest.fixture(autouse=True)
def _fresh_memo() -> None:
    memo.clear()


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    store.close()
    return tmp_path / "studio"


def _counted(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    calls: list[int] = []
    real = StudioStore.data_epoch

    def counting(self: StudioStore) -> tuple[object, ...]:
        calls.append(1)
        return real(self)

    monkeypatch.setattr(StudioStore, "data_epoch", counting)
    return calls


def test_an_import_of_changed_data_gives_a_fresh_result(
    folder: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same second, same number of rows: the import still changes the epoch, because the
    changed file is a new source row."""
    monkeypatch.setattr(memo, "_STAT_GUARD_NS", 0)
    store = StudioStore.open(folder)
    before = builder._corpus_hits(store, COMMANDER)
    assert "Forest" in before
    assert builder._corpus_hits(store, COMMANDER) is before  # memoized
    store.close()
    store = StudioStore.open(folder)
    # the same file again with one changed row: as many rows as before, in the same second
    rows = [
        {**_card_row("d1", "Forest", 30), "oracle_id": "oracle-forest"},
        {**_card_row("d1", "Swarm Rat"), "oracle_id": "oracle-swarm-rat"},
        {**_card_row("d2", "Swarm Rat"), "oracle_id": "oracle-swarm-rat"},
        {**_card_row("d3", "Swarm Rat"), "oracle_id": "oracle-swarm-rat"},
        {**_card_row("d3", "Unknown Card"), "oracle_id": ""},
        {**_card_row("d4", "Swarm Rat"), "oracle_id": "oracle-swarm-rat"},
    ]
    importers.import_corpus_cards(store, _write_csv(tmp_path / "cards.csv", rows))
    store.close()
    store = StudioStore.open(folder)
    after = builder._corpus_hits(store, COMMANDER)
    assert after is not before
    assert sum(after["Swarm Rat"].values()) > sum(before["Swarm Rat"].values())
    assert sum(after["Forest"].values()) < sum(before["Forest"].values())
    store.close()


def test_the_epoch_is_read_from_the_tables_only_when_the_file_changed(
    folder: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(memo, "_STAT_GUARD_NS", 0)
    calls = _counted(monkeypatch)
    for _ in range(3):  # three requests, each with its own connection
        store = StudioStore.open(folder)
        memo.cached(store, "probe", (), lambda: 1)
        store.close()
    assert len(calls) == 1
    # another connection writes a mark: the file changed, the epoch is read again (and is
    # the same, so the entry is still served)
    other = sqlite3.connect(folder / "studio.sqlite3")
    other.execute(
        "INSERT INTO card_mark(card_id, favorite, excluded, note, updated_at) "
        "VALUES ('card:project:0007', 1, 0, '', '2026-11-14T00:00:00Z')"
    )
    other.commit()
    other.close()
    store = StudioStore.open(folder)
    computed: list[int] = []
    assert memo.cached(store, "probe", (), lambda: computed.append(1) or 2) == 1
    store.close()
    assert (len(calls), computed) == (2, [])


def test_a_file_written_a_moment_ago_is_not_trusted(
    folder: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = _counted(monkeypatch)  # the guard keeps its two seconds: the file is brand new
    for _ in range(2):
        store = StudioStore.open(folder)
        memo.cached(store, "probe", (), lambda: 1)
        store.close()
    assert len(calls) == 2


def test_a_connection_that_wrote_reads_its_own_epoch(
    folder: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(memo, "_STAT_GUARD_NS", 0)
    store = StudioStore.open(folder)
    assert memo.cached(store, "probe", (), lambda: "old") == "old"
    store.close()
    store = StudioStore.open(folder)
    # uncommitted import rows of this connection: the file on disk has not changed yet
    store.connection.execute(
        "INSERT INTO card_signal SELECT * FROM card_signal WHERE 0"
    )  # no row, no change
    assert memo.cached(store, "probe", (), lambda: "new") == "old"
    store.connection.execute("DELETE FROM corpus_cohort")
    assert store.connection.in_transaction
    assert memo.cached(store, "probe", (), lambda: "new") == "new"
    store.connection.rollback()
    store.close()


def test_one_kind_keeps_a_limited_number_of_entries(
    folder: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(memo, "_STAT_GUARD_NS", 0)
    assert memo._MAX_PER_NAME["universe_decks"] == 8
    store = StudioStore.open(folder)
    for number in range(12):
        memo.cached(store, "universe_decks", number, lambda number=number: number)
        memo.cached(store, "other", number, lambda number=number: number)
    kept = [key[3] for key in memo._cache if key[2] == "universe_decks"]
    assert kept == [4, 5, 6, 7, 8, 9, 10, 11]  # the oldest went first
    assert len([key for key in memo._cache if key[2] == "other"]) == 12
    recomputed: list[int] = []
    memo.cached(store, "universe_decks", 0, lambda: recomputed.append(1) or 0)
    assert recomputed == [1]
    store.close()


def test_a_store_without_a_file_is_never_memoized() -> None:
    store = StudioStore.in_memory()
    seen: list[int] = []
    for _ in range(2):
        memo.cached(store, "probe", (), lambda: seen.append(1))
    assert seen == [1, 1]


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


def test_an_in_place_change_of_a_card_gives_fresh_deck_counts(folder: Path) -> None:
    """A relink changes a card row in place: no new row, no new source. The deck counts per
    card depend on the card names, so they must not be served from before the change."""
    store = StudioStore.open(folder)
    before = builder._corpus_hits(store, COMMANDER)
    assert builder._corpus_hits(store, COMMANDER) is before
    row = store.db.execute("SELECT card_id, oracle_id FROM card LIMIT 1").fetchone()
    store.db.execute("UPDATE card SET oracle_id = ? WHERE card_id = ?", (row[1], row[0]))
    store.db.commit()
    assert builder._corpus_hits(store, COMMANDER) is not before
    store.close()
