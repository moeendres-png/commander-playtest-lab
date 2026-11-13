"""Unit tests for TopDeck conversion calculation (Refs #1205).

Tests the normative definitions from docs/TOPDECK.md §6:
  - Minimum sample size threshold: < 10 -> NULL, >= 10 -> computed float.
  - NULL discipline: 0 hits below threshold is NULL, not 0.
  - Sum check: Appearances across cards match deck frequencies.
  - Chulane edge case: 6 decks (< 10) -> all conversions are NULL.
  - Fail-closed: Tournaments without cut / unknown bracket stay out of denominator.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest
from scripts.compute_topdeck_conversion import (
    CardConversionStat,
    TournamentDeck,
    compute_conversions_for_decks,
    export_conversions_csv,
)


def _make_deck(
    tournament: str,
    player: str,
    cards: list[str],
    commander: str = "Test Commander",
    top_cut: int | None = 4,
    wins_bracket: int | None = 1,
    losses_bracket: int | None = 0,
) -> TournamentDeck:
    """Helper to construct a TournamentDeck record."""
    return TournamentDeck(
        tournament_name=tournament,
        date_str="2026-11-12",
        player_name=player,
        wins=2,
        draws=1,
        losses=1,
        commander_name=commander,
        card_names=frozenset([*cards, commander]),
        top_cut=top_cut,
        wins_bracket=wins_bracket,
        losses_bracket=losses_bracket,
    )


def test_min_sample_threshold_boundary() -> None:
    """Test min-n boundary: 9 decks -> NULL, 10 decks -> calculated float."""
    # 9 decks: 3 reach cut, 6 do not
    decks_9: list[TournamentDeck] = []
    for i in range(9):
        # First 3 reach cut (WB=1), remaining 6 do not (WB=0, LB=0)
        wb = 1 if i < 3 else 0
        decks_9.append(_make_deck(f"T{i}", f"Player{i}", ["Sol Ring"], wins_bracket=wb))

    stats_9 = compute_conversions_for_decks("Test Commander", decks_9, min_sample=10)
    sol_ring_stat_9 = next(s for s in stats_9 if s.card_name == "Sol Ring")
    assert sol_ring_stat_9.appearances == 9
    assert sol_ring_stat_9.sample_size_base == 9
    assert sol_ring_stat_9.conversions == 3
    assert sol_ring_stat_9.conversion_rate is None
    assert sol_ring_stat_9.to_row()[4] == "NULL"

    # 10 decks: 4 reach cut, 6 do not
    decks_10 = list(decks_9)
    decks_10.append(_make_deck("T9", "Player9", ["Sol Ring"], wins_bracket=1))

    stats_10 = compute_conversions_for_decks("Test Commander", decks_10, min_sample=10)
    sol_ring_stat_10 = next(s for s in stats_10 if s.card_name == "Sol Ring")
    assert sol_ring_stat_10.appearances == 10
    assert sol_ring_stat_10.sample_size_base == 10
    assert sol_ring_stat_10.conversions == 4
    assert sol_ring_stat_10.conversion_rate == pytest.approx(0.4)
    assert sol_ring_stat_10.to_row()[4] == "0.400000"


def test_null_discipline_under_threshold() -> None:
    """Test NULL discipline: under threshold, rate stays NULL even if conversions == 0."""
    decks_5: list[TournamentDeck] = []
    for i in range(5):
        decks_5.append(
            _make_deck(
                f"T{i}", f"Player{i}", ["Mana Crypt"], wins_bracket=0, losses_bracket=0
            )
        )

    stats = compute_conversions_for_decks("Test Commander", decks_5, min_sample=10)
    stat = next(s for s in stats if s.card_name == "Mana Crypt")
    assert stat.appearances == 5
    assert stat.conversions == 0
    assert stat.sample_size_base == 5
    assert stat.conversion_rate is None
    row = stat.to_row()
    assert row[4] == "NULL"
    assert row[4] != "0"
    assert row[4] != "0.0"


def test_appearances_and_sum_check() -> None:
    """Test sum check and appearance counting across diverse card distributions."""
    decks: list[TournamentDeck] = [
        _make_deck("T1", "P1", ["CardA", "CardB", "CardC"]),
        _make_deck("T2", "P2", ["CardA", "CardB"]),
        _make_deck("T3", "P3", ["CardA", "CardC"]),
        _make_deck("T4", "P4", ["CardA"]),
    ]

    stats = compute_conversions_for_decks("Test Commander", decks, min_sample=10)
    stat_map = {s.card_name: s for s in stats}

    # Commander appears in all 4
    assert stat_map["Test Commander"].appearances == 4
    # CardA in 4
    assert stat_map["CardA"].appearances == 4
    # CardB in 2
    assert stat_map["CardB"].appearances == 2
    # CardC in 2
    assert stat_map["CardC"].appearances == 2

    # Appearance count never exceeds deck total
    for s in stats:
        assert 1 <= s.appearances <= len(decks)


def test_chulane_edge_case() -> None:
    """Chulane edge case: exactly 6 decks in corpus (< 10) -> all conversions NULL."""
    decks: list[TournamentDeck] = []
    for i in range(6):
        wb = 1 if i == 0 else 0
        decks.append(
            _make_deck(
                f"T{i}",
                f"Player{i}",
                ["Birds of Paradise", "Noble Hierarch", "Lotus Cobra"],
                commander="Chulane, Teller of Tales",
                wins_bracket=wb,
            )
        )

    stats = compute_conversions_for_decks(
        "Chulane, Teller of Tales", decks, min_sample=10
    )
    assert len(decks) == 6
    assert all(s.conversion_rate is None for s in stats)
    assert all(s.to_row()[4] == "NULL" for s in stats)


def test_fail_closed_unknown_bracket_and_no_cut() -> None:
    """Test that tournaments without cut or with unknown bracket stay out of denominator."""
    decks = [
        # Tournament with no cut (top_cut=0)
        _make_deck(
            "T1", "P1", ["CardX"], top_cut=0, wins_bracket=None, losses_bracket=None
        ),
        # Tournament with cut=4 but unknown bracket
        _make_deck(
            "T2", "P2", ["CardX"], top_cut=4, wins_bracket=None, losses_bracket=None
        ),
        # Tournament with cut=4 and known bracket (reached)
        _make_deck("T3", "P3", ["CardX"], top_cut=4, wins_bracket=1, losses_bracket=0),
    ]

    stats = compute_conversions_for_decks("Test Commander", decks, min_sample=1)
    stat = next(s for s in stats if s.card_name == "CardX")

    # Appearances count all 3
    assert stat.appearances == 3
    # Only T3 has top_cut > 0 and known bracket -> denominator is 1
    assert stat.sample_size_base == 1
    # T3 reached cut (WB=1) -> numerator is 1
    assert stat.conversions == 1
    assert stat.conversion_rate == pytest.approx(1.0)


def test_export_conversions_csv(tmp_path: Path) -> None:
    """Test exporting conversions to CSV."""
    stats = [
        CardConversionStat(
            "Gitrog",
            "Dakmor Salvage",
            appearances=100,
            conversions=25,
            conversion_rate=0.25,
            sample_size_base=100,
        ),
        CardConversionStat(
            "Chulane",
            "Birds of Paradise",
            appearances=6,
            conversions=1,
            conversion_rate=None,
            sample_size_base=6,
        ),
    ]
    out_file = tmp_path / "test_conversions.csv"
    export_conversions_csv(stats, out_file)

    assert out_file.is_file()
    with out_file.open(encoding="utf-8") as fp:
        rows = list(csv.reader(fp))

    assert rows[0] == [
        "commander",
        "card_name",
        "appearances",
        "conversions",
        "conversion_rate",
        "sample_size_base",
    ]
    assert rows[1] == ["Gitrog", "Dakmor Salvage", "100", "25", "0.250000", "100"]
    assert rows[2] == ["Chulane", "Birds of Paradise", "6", "1", "NULL", "6"]
