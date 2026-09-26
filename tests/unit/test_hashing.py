from __future__ import annotations

from pathlib import Path

from commander_lab.models import CommanderConfiguration, Deck, DeckEntry, DeckZone
from commander_lab.storage import compute_data_snapshot_hash, compute_deck_hash


def test_deck_hash_ignores_entry_order_and_grouping() -> None:
    common = {
        "deck_id": "x",
        "name": "x",
        "commander": CommanderConfiguration(commanders=("Korvold, Fae-Cursed King",)),
    }
    deck_a = Deck(
        **common,
        cards=[
            DeckEntry(oracle_name="Korvold, Fae-Cursed King", zone=DeckZone.COMMANDER),
            DeckEntry(oracle_name="Forest", quantity=98),
            DeckEntry(oracle_name="Sol Ring"),
        ],
    )
    deck_b = Deck(
        **common,
        cards=[
            DeckEntry(oracle_name="Sol Ring"),
            DeckEntry(oracle_name="Forest", quantity=40),
            DeckEntry(oracle_name="Korvold, Fae-Cursed King", zone=DeckZone.COMMANDER),
            DeckEntry(oracle_name="Forest", quantity=58),
        ],
    )
    assert compute_deck_hash(deck_a) == compute_deck_hash(deck_b)


def test_data_snapshot_hash_changes_with_file_content(tmp_path: Path) -> None:
    path = tmp_path / "data.txt"
    path.write_text("a", encoding="utf-8")
    first = compute_data_snapshot_hash([path], root=tmp_path)
    path.write_text("b", encoding="utf-8")
    second = compute_data_snapshot_hash([path], root=tmp_path)
    assert first != second
