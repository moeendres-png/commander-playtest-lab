"""rounds_own_turns: game length in own turns, not wall-clock rounds (#907).

rounds = max_turn / players counts every player's turns. When a seat is
eliminated, the remaining seats play more own turns than rounds suggests.
rounds_own_turns = max over own_turn_count (per-seat own turn counter).

Hand-made recorded-decision fixtures; no JVM, no games are played.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "pilot_decision_report.py"
spec = importlib.util.spec_from_file_location("pilot_decision_report_own_turns", SCRIPT)
assert spec and spec.loader
pdr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pdr)

# Reuse the _record helper from the seat figures test
sys.path.insert(0, str(ROOT / "tests" / "unit"))
from test_pilot_decision_report_seat_figures import _record  # noqa: E402


def _game_with_elimination() -> list[dict[str, Any]]:
    """4 seats play 3 full rounds, then seat 4 is eliminated.
    Seats 1-3 play 2 more rounds. Total: 5 rounds, but seats 1-3
    have 5 own turns each, seat 4 has 3.
    """
    records = []
    # Rounds 1-3: all 4 seats play (turns 1-12)
    for rnd in range(3):
        for seat in range(4):
            turn = rnd * 4 + seat + 1
            records.append(_record(seat=seat, turn=turn, own_turn=True))
    # Rounds 4-5: only seats 1-3 play (turns 13-18, but seats count own turns)
    # Seat 4 is eliminated, so turns 13,14,15 are seats 0,1,2; 16,17,18 are seats 0,1,2
    for rnd in range(2):
        for seat in range(3):
            # Turn numbers keep incrementing globally
            turn = 12 + rnd * 3 + seat + 1
            records.append(_record(seat=seat, turn=turn, own_turn=True))
    return records


def _game_no_elimination() -> list[dict[str, Any]]:
    """4 seats play 3 full rounds, no elimination."""
    records = []
    for rnd in range(3):
        for seat in range(4):
            turn = rnd * 4 + seat + 1
            records.append(_record(seat=seat, turn=turn, own_turn=True))
    return records


def test_rounds_own_turns_exceeds_rounds_after_elimination() -> None:
    """After elimination, rounds_own_turns > rounds."""
    records = _game_with_elimination()
    summary = pdr.summarize(records, players=4)

    # rounds = max_turn / players = 18 / 4 = 4.5
    # rounds_own_turns = max own turns = 5 (seats 0,1,2)
    assert summary["rounds"] < summary["rounds_own_turns"]
    assert summary["rounds_own_turns"] == 5


def test_rounds_own_turns_equals_seat_own_turns() -> None:
    """rounds_own_turns equals the max own turn count."""
    records = _game_with_elimination()
    summary = pdr.summarize(records, players=4)

    # Seat 0 played 5 own turns (3 + 2)
    assert summary["rounds_own_turns"] == 5


def test_rounds_own_turns_equals_rounds_without_elimination() -> None:
    """Without elimination, both are equal."""
    records = _game_no_elimination()
    summary = pdr.summarize(records, players=4)

    # 3 rounds, each seat has 3 own turns
    assert summary["rounds"] == summary["rounds_own_turns"] == 3.0


def test_totals_includes_mean_rounds_own_turns() -> None:
    """totals() computes mean_rounds_own_turns alongside mean_rounds."""
    records = _game_with_elimination()
    summary = pdr.summarize(records, players=4)
    summary["status"] = "ok"

    report = {"games": [summary]}
    result = pdr.totals(report)

    assert "mean_rounds_own_turns" in result
    assert result["mean_rounds_own_turns"] == 5.0
    # mean_rounds still there and unchanged
    assert "mean_rounds" in result


def test_totals_skips_games_without_rounds_own_turns() -> None:
    """Games without the field (old reports, batched) are left out."""
    records = _game_with_elimination()
    summary = pdr.summarize(records, players=4)
    summary["status"] = "ok"

    old_game = {"status": "ok", "rounds": 3.0}  # no rounds_own_turns

    report = {"games": [summary, old_game]}
    result = pdr.totals(report)

    # Only the new game counts for mean_rounds_own_turns
    assert result["mean_rounds_own_turns"] == 5.0
