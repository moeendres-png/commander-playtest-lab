from __future__ import annotations

import json
from pathlib import Path

import pytest

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


def test_rules_loader_accepts_wrapped_opponent_profile(tmp_path: Path) -> None:
    path = tmp_path / "opponent.json"
    path.write_text(
        json.dumps(
            {
                "profile_id": "opponent/example-precon",
                "name": "Example opponent",
                "deck": {
                    "deck_id": "opponent/example-precon",
                    "name": "Example precon",
                    "commander": {"commanders": ["Commander"]},
                    "cards": [
                        {"oracle_name": "Commander", "zone": "commander"},
                        {"oracle_name": "Plains", "zone": "main", "quantity": 99},
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    deck = load_rules_deck_snapshot(path)

    assert deck.deck_id == "opponent/example-precon"
    assert deck.commander_names == ("Commander",)
    assert len(deck.mainboard) == 99
    assert deck.source_path == str(path)


def test_rules_loader_accepts_legacy_string_commander(tmp_path: Path) -> None:
    path = tmp_path / "legacy-string.json"
    path.write_text(
        json.dumps(
            {
                "deck_id": "legacy/string-commander",
                "name": "Legacy string commander",
                "commander": "Commander",
                "cards": [
                    {"oracle_name": "Commander", "zone": "commander"},
                    {"oracle_name": "Mountain", "zone": "main", "quantity": 99},
                ],
                "deck_hash": "b" * 64,
            }
        ),
        encoding="utf-8",
    )

    deck = load_rules_deck_snapshot(path)

    assert deck.commander_names == ("Commander",)
    assert len(deck.mainboard) == 99
    assert deck.deck_hash == "b" * 64


def test_rules_loader_rejects_wrapped_profile_id_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "bad-opponent.json"
    path.write_text(
        json.dumps(
            {
                "profile_id": "opponent/profile-a",
                "deck": {
                    "deck_id": "opponent/profile-b",
                    "name": "Bad",
                    "commander": {"commanders": ["Commander"]},
                    "cards": [
                        {"oracle_name": "Commander", "zone": "commander"},
                        {"oracle_name": "Plains", "zone": "main", "quantity": 99},
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    try:
        load_rules_deck_snapshot(path)
    except ValueError as exc:
        assert "wrapped opponent profile deck ID mismatch" in str(exc)
    else:
        raise AssertionError("wrapped profile/deck ID mismatch must fail closed")


@pytest.mark.parametrize("bad_name", [None, 7, {}, "", "   "])
def test_rules_loader_rejects_invalid_commander_names(
    tmp_path: Path,
    bad_name: object,
) -> None:
    path = tmp_path / "bad-commander.json"
    path.write_text(
        json.dumps(
            {
                "deck_id": "invalid/commander-name",
                "name": "Invalid commander name",
                "commander": {"commanders": [bad_name]},
                "cards": [
                    {"oracle_name": "Plains", "zone": "main", "quantity": 99},
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="commander name at index 0 must be a non-empty string",
    ):
        load_rules_deck_snapshot(path)

