"""Regression for importing a source-deck corpus across multiple CSV partitions.

All records are synthetic; no private collection data is committed.
"""

from __future__ import annotations

import csv
from pathlib import Path

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
                    f"oracle-{name.lower()}", f"printing-{name.lower()}", name, name,
                    "normal", "", "legal", "[]", "", f"Basic Land — {name}", source_id,
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
