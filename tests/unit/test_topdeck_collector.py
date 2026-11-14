"""Unit tests for TopDeck tournament collector (#1205)."""

from __future__ import annotations

import csv
import re
from pathlib import Path

from scripts.collect_topdeck_decks import (
    DEFAULT_107_COMMANDERS,
    export_results,
    extract_cards_from_section,
    neutral_player_labels,
    parse_decklist_text,
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
        assert rows[0]["player"] == "Liste 1"
        assert rows[0]["wins"] == "3"
        assert "top_cut" in rows[0]
        assert "wins_bracket" in rows[0]
        assert "losses_bracket" in rows[0]

    readme_file = out_dir / "README.md"
    assert readme_file.is_file()
    readme_text = readme_file.read_text(encoding="utf-8")
    assert "Data provided by TopDeck.gg (https://topdeck.gg)" in readme_text
    assert "The Gitrog Monster" in readme_text


def test_neutral_player_labels() -> None:
    labels = neutral_player_labels(
        ["Max Mustermann", "Maria Muster", "Max Mustermann", "Paul Meyer"]
    )
    # First-appearance order per file; repeats keep their label; no part of
    # any name (not even initials) leaks into a label (#1263).
    assert labels == {
        "Max Mustermann": "Liste 1",
        "Maria Muster": "Liste 2",
        "Paul Meyer": "Liste 3",
    }
    assert neutral_player_labels([]) == {}


def _complete_deck(player: str) -> dict[str, object]:
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


def test_export_fixture_two_players_only_liste_labels(tmp_path: Path) -> None:
    # Issue #1263, task 2: a fixture with two names yields only "Liste 1"
    # and "Liste 2". Both names share the same initials on purpose, so an
    # initials-based label would collide; neutral labels must not.
    mock_tournaments = [
        {
            "TID": "tourney_anon",
            "tournamentName": "Anon Cup",
            "startDate": 1780000000,
            "standings": [_complete_deck("Ann Alpha"), _complete_deck("Aaron Albers")],
        }
    ]
    stats, decks = process_tournaments(mock_tournaments, DEFAULT_107_COMMANDERS)
    out_dir = tmp_path / "topdeck_out"
    export_results(stats, decks, out_dir, DEFAULT_107_COMMANDERS)

    deck_file = out_dir / "topdeck_the_gitrog_monster_decks.csv"
    text = deck_file.read_text(encoding="utf-8")
    assert "Ann Alpha" not in text
    assert "Aaron Albers" not in text
    assert "A A" not in text
    with deck_file.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 200
    assert {r["player"] for r in rows[:100]} == {"Liste 1"}
    assert {r["player"] for r in rows[100:]} == {"Liste 2"}


def test_export_same_player_keeps_label_across_tournaments(tmp_path: Path) -> None:
    # Issue #1263, task 1: the same player in several tournaments of one
    # export file keeps the same number.
    mock_tournaments = [
        {
            "TID": "tourney_a",
            "tournamentName": "Cup A",
            "startDate": 1780000000,
            "standings": [_complete_deck("Ann Alpha"), _complete_deck("Bob Beta")],
        },
        {
            "TID": "tourney_b",
            "tournamentName": "Cup B",
            "startDate": 1780100000,
            "standings": [_complete_deck("Ann Alpha")],
        },
    ]
    stats, decks = process_tournaments(mock_tournaments, DEFAULT_107_COMMANDERS)
    out_dir = tmp_path / "topdeck_out"
    export_results(stats, decks, out_dir, DEFAULT_107_COMMANDERS)

    deck_file = out_dir / "topdeck_the_gitrog_monster_decks.csv"
    with deck_file.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 300
    assert {r["player"] for r in rows[:100]} == {"Liste 1"}
    assert {r["player"] for r in rows[100:200]} == {"Liste 2"}
    assert {r["player"] for r in rows[200:]} == {"Liste 1"}


def test_committed_topdeck_deck_csvs_use_neutral_player_labels() -> None:
    # Issue #1263, task 3 (guard): every committed tournament deck CSV
    # carries only neutral "Liste N" labels in its player column.
    files = sorted(Path("data/research").rglob("topdeck_*_decks.csv"))
    assert files, "expected committed topdeck deck CSVs under data/research"
    label_re = re.compile(r"^Liste \d+$")
    for path in files:
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames is not None and "player" in reader.fieldnames, (
                f"{path} has no player column"
            )
            rows = list(reader)
        assert rows, f"{path} has no data rows"
        for row in rows:
            value = row["player"] or ""
            assert label_re.match(value), (
                f"{path}: player cell {value!r} is not a neutral 'Liste N' label"
            )


def test_get_api_key(monkeypatch) -> None:
    import pytest
    from scripts.collect_topdeck_decks import get_api_key

    monkeypatch.setenv("TOPDECK_API_KEY", "test-key-12345")
    assert get_api_key() == "test-key-12345"

    monkeypatch.delenv("TOPDECK_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="TOPDECK_API_KEY environment variable"):
        get_api_key()


def test_split_commander_parts_assign_commander_wide_liste_labels(tmp_path: Path) -> None:
    # Issue #1309, item 9: split files (_decks_1.csv, _decks_2.csv) must keep
    # one commander-wide Liste N sequence so part 2 never restarts at Liste 1.
    mock_tournaments = [
        {
            "TID": "t1",
            "tournamentName": "Split Cup",
            "startDate": 1780000000,
            "standings": [
                _complete_deck("Alice"),
                _complete_deck("Bob"),
                _complete_deck("Carol"),
                _complete_deck("Alice"),
            ],
        }
    ]
    stats, decks = process_tournaments(mock_tournaments, DEFAULT_107_COMMANDERS)
    out_dir = tmp_path / "split_out"
    summary = export_results(
        stats,
        decks,
        out_dir,
        DEFAULT_107_COMMANDERS,
        max_decks_per_file=2,
    )
    assert summary["exported_files"] == [
        "topdeck_commander_presence.csv",
        "topdeck_the_gitrog_monster_decks_1.csv",
        "topdeck_the_gitrog_monster_decks_2.csv",
    ]
    part1 = list(csv.DictReader((out_dir / "topdeck_the_gitrog_monster_decks_1.csv").open()))
    part2 = list(csv.DictReader((out_dir / "topdeck_the_gitrog_monster_decks_2.csv").open()))
    assert [r["player"] for r in part1[::100]] == ["Liste 1", "Liste 2"]
    assert [r["player"] for r in part2[::100]] == ["Liste 3", "Liste 1"]
