"""Regression for importing a source-deck corpus across multiple CSV partitions.

All records are synthetic; no private collection data is committed.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from commander_lab.studio import StudioStore, importers


def _write(path: Path, rows: list[dict[str, object]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _deck(deck_id: str) -> dict[str, object]:
    return {
        "deck_id": deck_id,
        "source_cohort": "TEST",
        "original_url": "",
        "source_platform": "fixture",
        "group": "community",
        "date": "",
        "source_archetype_tags": "",
        "fingerprint_scryfall_oracle": f"fingerprint-{deck_id}",
        "exact_duplicate_of": "",
        "current_legality_name_audit": "",
    }


def _card(deck_id: str, name: str, quantity: int) -> dict[str, object]:
    return {
        "source": "TEST",
        "deck_id": deck_id,
        "raw_card_name": name,
        "canonical_name": name,
        "oracle_id": f"oracle-{name.lower()}",
        "quantity": quantity,
        "section": "mainboard",
        "normalization_status": "exact",
    }


def test_corpus_parts_accumulate_without_erasing_previous_parts(tmp_path: Path) -> None:
    store = StudioStore.in_memory()
    try:
        register = _write(tmp_path / "register.csv", [_deck(x) for x in ("d1", "d2", "d3", "d4")])
        part_1 = _write(
            tmp_path / "part1.csv",
            [
                _card("d1", "Forest", 2),
                _card("d1", "Island", 1),
                _card("d1", "Forest", 3),
                _card("d2", "Plains", 1),
            ],
        )
        part_2 = _write(
            tmp_path / "part2.csv",
            [
                _card("d3", "Mountain", 1),
                _card("d4", "Swamp", 2),
            ],
        )
        importers.import_corpus_register(store, register)
        # Scryfall was loaded before deck cards in the common import order.
        source_id = store.connection.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0]
        for name in ("Forest", "Island", "Plains", "Mountain", "Swamp"):
            store.connection.execute(
                "INSERT INTO scryfall_card(oracle_id, scryfall_id, name, front_name, layout, "
                "color_identity, commander_legality, keywords, produced_mana, type_line, "
                "source_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    f"oracle-{name.lower()}",
                    f"printing-{name.lower()}",
                    name,
                    name,
                    "normal",
                    "",
                    "legal",
                    "[]",
                    "",
                    f"Basic Land — {name}",
                    source_id,
                ),
            )
        store.connection.commit()
        assert importers.import_corpus_cards(store, part_1) == {
            "rows": 3,
            "rows_without_registered_deck": 0,
        }
        assert store.count("corpus_deck_card") == 3
        assert store.count("corpus_deck_stat") == 2
        assert importers.import_corpus_cards(store, part_2) == {
            "rows": 2,
            "rows_without_registered_deck": 0,
        }
        assert store.count("corpus_deck_card") == 5
        assert store.count("corpus_deck_stat") == 4

        # Repeating a partition must not double the quantities or erase other partitions.
        importers.import_corpus_cards(store, part_1)
        assert store.count("corpus_deck_card") == 5
        observed = {
            (row["deck_id"], row["card_name"]): row["quantity"]
            for row in store.connection.execute(
                "SELECT deck_id, card_name, quantity FROM corpus_deck_card"
            )
        }
        assert observed == {
            ("d1", "Forest"): 5,
            ("d1", "Island"): 1,
            ("d2", "Plains"): 1,
            ("d3", "Mountain"): 1,
            ("d4", "Swamp"): 2,
        }

        # Replacing one deck's rows must leave a different partition untouched.
        _write(part_1, [_card("d1", "Forest", 9), _card("d2", "Plains", 1)])
        importers.import_corpus_cards(store, part_1)
        assert store.count("corpus_deck_card") == 4
        assert (
            store.connection.execute(
                "SELECT quantity FROM corpus_deck_card WHERE deck_id='d1' AND card_name='Forest'"
            ).fetchone()[0]
            == 9
        )
        assert (
            store.connection.execute(
                "SELECT quantity FROM corpus_deck_card WHERE deck_id='d3' AND card_name='Mountain'"
            ).fetchone()[0]
            == 1
        )
    finally:
        store.close()


def _store_with_register(tmp_path: Path, decks: tuple[str, ...]) -> StudioStore:
    store = StudioStore.in_memory()
    register = _write(tmp_path / "register.csv", [_deck(deck) for deck in decks])
    importers.import_corpus_register(store, register)
    return store


def _state(store: StudioStore) -> dict[str, list[tuple[object, ...]]]:
    return {
        table: sorted(
            (tuple(row) for row in store.connection.execute(f"SELECT * FROM {table}")), key=repr
        )
        for table in ("source", "corpus_deck_card", "corpus_deck_part")
    }


def _healthy(store: StudioStore) -> bool:
    integrity = store.connection.execute("PRAGMA integrity_check").fetchone()[0]
    return integrity == "ok" and not store.connection.execute("PRAGMA foreign_key_check").fetchall()


def test_a_deck_in_two_files_of_one_batch_is_rejected_before_anything_is_written(
    tmp_path: Path,
) -> None:
    store = _store_with_register(tmp_path, ("d1", "d2", "d3"))
    try:
        one = _write(tmp_path / "one.csv", [_card("d1", "Forest", 40), _card("d2", "Plains", 1)])
        two = _write(tmp_path / "two.csv", [_card("d1", "Island", 59), _card("d3", "Swamp", 1)])
        before = _state(store)
        with pytest.raises(ValueError, match=r"1 deck\(s\) appear in more than one") as raised:
            importers.import_corpus_card_parts(store, [one, two])
        assert "d1" in str(raised.value)
        assert "nothing was imported" in str(raised.value)
        assert _state(store) == before
        assert _healthy(store)
    finally:
        store.close()


def test_a_deck_that_another_part_already_holds_needs_an_explicit_move(tmp_path: Path) -> None:
    store = _store_with_register(tmp_path, ("d1", "d2"))
    try:
        part_1 = _write(
            tmp_path / "part1.csv", [_card("d1", "Forest", 99), _card("d2", "Plains", 1)]
        )
        importers.import_corpus_cards(store, part_1)
        later = _write(tmp_path / "part2.csv", [_card("d1", "Island", 3)])
        before = _state(store)
        with pytest.raises(ValueError, match="another file name") as raised:
            importers.import_corpus_cards(store, later)
        assert "--allow-deck-move" in str(raised.value)
        assert _state(store) == before  # the deck keeps its 99 cards
        moved = importers.import_corpus_card_parts(store, [later], allow_deck_move=True)
        assert moved["decks_moved_from_another_part"] == 1
        parts = dict(store.connection.execute("SELECT deck_id, part_name FROM corpus_deck_part"))
        assert parts == {"d1": "part2.csv", "d2": "part1.csv"}
        assert (
            store.connection.execute(
                "SELECT SUM(quantity) FROM corpus_deck_card WHERE deck_id = 'd1'"
            ).fetchone()[0]
            == 3
        )
        assert _healthy(store)
    finally:
        store.close()


def test_a_renamed_part_is_refused_and_the_same_part_may_change(tmp_path: Path) -> None:
    store = _store_with_register(tmp_path, ("d1", "d2"))
    try:
        rows = [_card("d1", "Forest", 99), _card("d2", "Plains", 1)]
        original = _write(tmp_path / "part1.csv", rows)
        importers.import_corpus_cards(store, original)
        copy = _write(tmp_path / "part1_new_export.csv", rows)
        with pytest.raises(ValueError, match="another file name"):
            importers.import_corpus_cards(store, copy)
        original = _write(tmp_path / "part1.csv", [_card("d1", "Forest", 98), *rows[1:]])
        importers.import_corpus_cards(store, original)
        total = store.connection.execute(
            "SELECT SUM(quantity) FROM corpus_deck_card WHERE deck_id = 'd1'"
        ).fetchone()[0]
        assert total == 98
    finally:
        store.close()


def test_decks_from_an_older_program_version_have_no_part_and_are_accepted(
    tmp_path: Path,
) -> None:
    store = _store_with_register(tmp_path, ("d1",))
    try:
        part = _write(tmp_path / "part1.csv", [_card("d1", "Forest", 99)])
        importers.import_corpus_cards(store, part)
        store.connection.execute("DELETE FROM corpus_deck_part")
        store.connection.commit()
        other = _write(tmp_path / "other_name.csv", [_card("d1", "Forest", 99)])
        importers.import_corpus_cards(store, other)
        parts = dict(store.connection.execute("SELECT deck_id, part_name FROM corpus_deck_part"))
        assert parts == {"d1": "other_name.csv"}
    finally:
        store.close()


def test_a_batch_is_one_transaction_and_a_bad_row_imports_nothing(tmp_path: Path) -> None:
    store = _store_with_register(tmp_path, ("d1", "d2"))
    try:
        good = _write(tmp_path / "good.csv", [_card("d1", "Forest", 99)])
        broken = _write(tmp_path / "broken.csv", [{**_card("d2", "Plains", 1), "quantity": "x"}])
        before = _state(store)
        with pytest.raises(ValueError, match="invalid literal"):
            importers.import_corpus_card_parts(store, [good, broken])
        assert _state(store) == before
        result = importers.import_corpus_card_parts(
            store, [good, _write(tmp_path / "fine.csv", [_card("d2", "Plains", 99)])]
        )
        assert result["decks"] == 2
        assert result["decks_moved_from_another_part"] == 0
        assert _healthy(store)
    finally:
        store.close()


def test_two_files_with_the_same_name_are_refused(tmp_path: Path) -> None:
    store = _store_with_register(tmp_path, ("d1", "d2"))
    try:
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        first = _write(tmp_path / "a" / "part.csv", [_card("d1", "Forest", 99)])
        second = _write(tmp_path / "b" / "part.csv", [_card("d2", "Plains", 99)])
        with pytest.raises(ValueError, match="same name"):
            importers.import_corpus_card_parts(store, [first, second])
    finally:
        store.close()
