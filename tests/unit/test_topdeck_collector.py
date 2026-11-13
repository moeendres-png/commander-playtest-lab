"""Unit tests for TopDeck tournament collector (#1205)."""

from __future__ import annotations

import csv
from pathlib import Path

from scripts.collect_topdeck_decks import (
    DEFAULT_107_COMMANDERS,
    anonymize_player_labels,
    export_results,
    extract_cards_from_section,
    parse_decklist_text,
    player_initials,
    process_tournaments,
    to_safe_slug,
)


def test_to_safe_slug() -> None:
    assert to_safe_slug("Korvold, Fae-Cursed King") == "korvold_fae-cursed_king"
    assert to_safe_slug("The Gitrog Monster") == "the_gitrog_monster"
    assert to_safe_slug("Kykar, Wind's Fury") == "kykar_winds_fury"
    assert (
        to_safe_slug("Brigid, Clachan's Heart // Brigid, Doun's Mind")
        == "brigid_clachans_heart_brigid_douns_mind"
    )


def test_extract_cards_from_section() -> None:
    # Dict format with nested count
    dict_nested = {
        "Sol Ring": {"id": "123", "count": 1},
        "Forest": {"id": "456", "count": 3},
    }
    extracted = extract_cards_from_section(dict_nested)
    assert extracted == [("Sol Ring", 1), ("Forest", 3)]

    # Dict format with int
    dict_simple = {"Swords to Plowshares": 1}
    assert extract_cards_from_section(dict_simple) == [("Swords to Plowshares", 1)]

    # List format
    list_format = [{"name": "Birds of Paradise", "count": 1}]
    assert extract_cards_from_section(list_format) == [("Birds of Paradise", 1)]


def test_parse_decklist_text() -> None:
    sample_text = """
    ~~Commanders~~
    1 The Gitrog Monster

    ~~Mainboard~~
    1 Sol Ring
    1 Command Tower
    2 Swamp
    """
    cmd, mb = parse_decklist_text(sample_text)
    assert cmd == [("The Gitrog Monster", 1)]
    assert mb == [("Sol Ring", 1), ("Command Tower", 1), ("Swamp", 2)]


def test_process_tournaments_and_completeness(tmp_path: Path) -> None:
    mock_tournaments = [
        {
            "TID": "tourney_1",
            "tournamentName": "Spring Invitational",
            "startDate": 1780000000,
            "standings": [
                {
                    "name": "Alice",
                    "leader": "The Gitrog Monster",
                    "wins": 3,
                    "draws": 0,
                    "losses": 1,
                    "deckObj": {
                        "Commanders": {"The Gitrog Monster": {"count": 1}},
                        # 99 mainboard cards
                        "Mainboard": {f"Card {i}": {"count": 1} for i in range(1, 100)},
                    },
                },
                {
                    "name": "Bob",
                    "leader": "The Gitrog Monster",
                    "wins": 1,
                    "draws": 0,
                    "losses": 2,
                    "deckObj": {
                        "Commanders": {"The Gitrog Monster": {"count": 1}},
                        # Only 50 cards (incomplete)
                        "Mainboard": {f"Card {i}": {"count": 1} for i in range(1, 51)},
                    },
                },
                {
                    "name": "Charlie",
                    "leader": "Unknown Commander XYZ",
                    "wins": 0,
                    "draws": 0,
                    "losses": 3,
                },
            ],
        },
        # Duplicate tournament with same TID
        {
            "TID": "tourney_1",
            "tournamentName": "Spring Invitational",
            "startDate": 1780000000,
            "standings": [],
        },
    ]

    stats, decks = process_tournaments(mock_tournaments, DEFAULT_107_COMMANDERS)

    assert stats["unique_tournaments"] == 1
    assert stats["standings_total_90d"] == 3
    assert stats["standings_with_leader_90d"] == 3
    assert stats["presence_counts"]["The Gitrog Monster"] == 2
    assert stats["presence_counts"]["Korvold, Fae-Cursed King"] == 0

    gitrog_decks = decks["The Gitrog Monster"]
    assert len(gitrog_decks) == 2
    complete = [d for d in gitrog_decks if d.is_complete]
    incomplete = [d for d in gitrog_decks if not d.is_complete]
    assert len(complete) == 1
    assert len(incomplete) == 1

    # Verify export
    out_dir = tmp_path / "topdeck_out"
    summary = export_results(stats, decks, out_dir, DEFAULT_107_COMMANDERS)

    assert summary["exported_commanders_count"] == 1
    assert summary["total_exported_decks"] == 1
    assert summary["total_incomplete_decks"] == 1

    presence_file = out_dir / "topdeck_commander_presence.csv"
    assert presence_file.is_file()
    with presence_file.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = {r["commander_name"]: int(r["topdeck_entries_90d"]) for r in reader}
        assert rows["The Gitrog Monster"] == 2
        assert rows["Korvold, Fae-Cursed King"] == 0

    deck_file = out_dir / "topdeck_the_gitrog_monster_decks.csv"
    assert deck_file.is_file()
    with deck_file.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        # 1 commander + 99 mainboard = 100 rows
        assert len(rows) == 100
        assert rows[0]["section"] == "commander"
        assert rows[0]["card_name"] == "The Gitrog Monster"
        assert rows[1]["section"] == "main"
        assert rows[0]["player"] == "A"
        assert rows[0]["wins"] == "3"
        assert "top_cut" in rows[0]
        assert "wins_bracket" in rows[0]
        assert "losses_bracket" in rows[0]

    readme_file = out_dir / "README.md"
    assert readme_file.is_file()
    readme_text = readme_file.read_text(encoding="utf-8")
    assert "Data provided by TopDeck.gg (https://topdeck.gg)" in readme_text
    assert "The Gitrog Monster" in readme_text


def test_player_initials() -> None:
    assert player_initials("Moritz") == "M"
    assert player_initials("Toni Romero") == "T R"
    # First alphabetic character per token; "[INTIM]" contributes "I"
    assert player_initials("Void of Emperor [INTIM]") == "V O E I"
    # Tokens without any letter are skipped
    assert player_initials("Team 2 Cool") == "T C"
    assert player_initials("NatHall98") == "N"


def test_anonymize_player_labels() -> None:
    labels = anonymize_player_labels(
        ["Max Mustermann", "Maria Muster", "Max Mustermann", "Moritz Meyer"]
    )
    # First-appearance order; repeats keep their label; collisions get suffixes
    assert labels == {
        "Max Mustermann": "M M",
        "Maria Muster": "M M 2",
        "Moritz Meyer": "M M 3",
    }


def test_export_anonymizes_players_with_collisions(tmp_path: Path) -> None:
    def complete_deck(player: str) -> dict[str, object]:
        return {
            "name": player,
            "leader": "The Gitrog Monster",
            "wins": 3,
            "draws": 0,
            "losses": 1,
            "deckObj": {
                "Commanders": {"The Gitrog Monster": {"count": 1}},
                "Mainboard": {f"Card {i}": {"count": 1} for i in range(1, 100)},
            },
        }

    mock_tournaments = [
        {
            "TID": "tourney_anon",
            "tournamentName": "Anon Cup",
            "startDate": 1780000000,
            "standings": [complete_deck("Ann Alpha"), complete_deck("Aaron Albers")],
        }
    ]
    stats, decks = process_tournaments(mock_tournaments, DEFAULT_107_COMMANDERS)
    out_dir = tmp_path / "topdeck_out"
    export_results(stats, decks, out_dir, DEFAULT_107_COMMANDERS)

    deck_file = out_dir / "topdeck_the_gitrog_monster_decks.csv"
    text = deck_file.read_text(encoding="utf-8")
    assert "Ann Alpha" not in text
    assert "Aaron Albers" not in text
    with deck_file.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 200
    assert {r["player"] for r in rows[:100]} == {"A A"}
    assert {r["player"] for r in rows[100:]} == {"A A 2"}


def test_get_api_key(monkeypatch) -> None:
    import pytest
    from scripts.collect_topdeck_decks import get_api_key

    monkeypatch.setenv("TOPDECK_API_KEY", "test-key-12345")
    assert get_api_key() == "test-key-12345"

    monkeypatch.delenv("TOPDECK_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="TOPDECK_API_KEY environment variable"):
        get_api_key()
