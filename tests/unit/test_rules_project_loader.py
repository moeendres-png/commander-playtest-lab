from __future__ import annotations

import json
from pathlib import Path

from commander_lab.engine.rules.project import load_rules_deck_snapshot


def test_rules_loader_accepts_compact_current_snapshot_without_main_zone(tmp_path: Path) -> None:
    path = tmp_path / "deck.json"
    path.write_text(
        json.dumps(
            {
                "deck_id": "example/current",
                "name": "Example",
                "commander": {"commanders": ["Commander A", "Commander B"]},
                "cards": [
                    {"oracle_name": "Commander A", "zone": "commander"},
                    {"oracle_name": "Commander B", "zone": "commander"},
                    {"oracle_name": "Island", "quantity": 97},
                    {"oracle_name": "Sol Ring"},
                    {"oracle_name": "Wish", "zone": "sideboard", "quantity": 2},
                ],
                "deck_hash": "a" * 64,
            }
        ),
        encoding="utf-8",
    )

    deck = load_rules_deck_snapshot(path)

    assert deck.commander_names == ("Commander A", "Commander B")
    assert len(deck.mainboard) == 98
    assert deck.mainboard.count("Island") == 97
    assert deck.mainboard.count("Sol Ring") == 1
    assert deck.sideboard == ("Wish", "Wish")
    assert deck.deck_hash == "a" * 64


def test_rules_loader_preserves_explicit_legacy_main_zone(tmp_path: Path) -> None:
    path = tmp_path / "deck.json"
    path.write_text(
        json.dumps(
            {
                "deck_id": "legacy/current",
                "name": "Legacy",
                "commander": {"commanders": ["Commander"]},
                "cards": [
                    {"oracle_name": "Commander", "zone": "commander", "quantity": 1},
                    {"oracle_name": "Mountain", "zone": "main", "quantity": 99},
                ],
            }
        ),
        encoding="utf-8",
    )

    deck = load_rules_deck_snapshot(path)

    assert len(deck.mainboard) == 99
    assert set(deck.mainboard) == {"Mountain"}
    assert deck.sideboard == ()
