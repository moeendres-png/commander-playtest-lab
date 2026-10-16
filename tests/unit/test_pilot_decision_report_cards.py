"""Per-card cast rate and rotting cards in scripts/pilot_decision_report.py (#836).

Tests use hand-made recorded-decision fixtures; no JVM, no games are played.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "pilot_decision_report.py"
spec = importlib.util.spec_from_file_location("pilot_decision_report_under_test", SCRIPT)
assert spec and spec.loader
pdr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pdr)


def _option(
    option_id: str,
    *,
    option_type: str = "cast_spell",
    ability_type: str = "spell",
    source_name: str = "",
) -> dict[str, Any]:
    return {
        "option_id": option_id,
        "option_type": option_type,
        "metadata": {"ability_type": ability_type, "source_name": source_name},
    }


def _pass_option(option_id: str = "pass") -> dict[str, Any]:
    return {"option_id": option_id, "option_type": "pass_priority", "metadata": {}}


def _priority_record(
    *,
    turn: int = 5,
    seat: int = 0,
    actor_id: str = "p1",
    active_player_id: str = "p1",
    phase: str = "main1",
    options: list[dict[str, Any]] | None = None,
    picked_id: str | None = None,
) -> dict[str, Any]:
    if options is None:
        options = [_pass_option()]
    return {
        "request": {
            "decision_class": "priority",
            "legal_options": options,
            "pilot_state": {
                "phase": phase,
                "step": "main",
                "turn_number": turn,
                "seat": seat,
                "actor_id": actor_id,
                "active_player_id": active_player_id,
                "stack": [],
            },
        },
        "answer": {"selected_option_ids": [picked_id] if picked_id else []},
        "pilot_s": 0.01,
    }


def test_cast_rate_quarter_when_offered_four_times_cast_once() -> None:
    records = [
        _priority_record(
            options=[
                _option("bolt", source_name="Lightning Bolt"),
                _pass_option(),
            ],
            picked_id="bolt" if i == 0 else "pass",
        )
        for i in range(4)
    ]
    summary = pdr.summarize(records, players=4)
    per_card = {(e["seat"], e["card"]): e for e in summary["per_card"]}
    entry = per_card[(1, "Lightning Bolt")]
    assert entry["offered_castable"] == 4
    assert entry["cast"] == 1
    assert entry["first_cast_round"] is not None

    report = {"games": [dict(summary, status="ok", pod="p", seed=1, players=4)]}
    cards = pdr.aggregate_cards(report)
    bolt = next(c for c in cards["cards"] if c["card"] == "Lightning Bolt")
    assert bolt["offered_castable"] == 4
    assert bolt["cast"] == 1
    assert bolt["cast_rate"] == pytest.approx(0.25)
    assert bolt["games_seen"] == 1


def test_land_play_is_not_counted_as_cast() -> None:
    records = [
        _priority_record(
            options=[
                _option(
                    "land", option_type="play_land", ability_type="play_land", source_name="Island"
                ),
                _pass_option(),
            ],
            picked_id="land",
        )
    ]
    summary = pdr.summarize(records, players=4)
    assert summary["per_card"] == []
    # The spell counters are untouched by a land play.
    assert summary["spells_cast"] == 0


def test_opponent_turn_window_not_attributed() -> None:
    # Opponent's main phase: the actor may still get priority (instants), but
    # offered_castable only counts own main-phase windows.
    records = [
        _priority_record(
            active_player_id="p2",  # not the actor's turn
            options=[
                _option("bolt", source_name="Lightning Bolt"),
                _pass_option(),
            ],
            picked_id="pass",
        )
    ]
    summary = pdr.summarize(records, players=4)
    assert summary["per_card"] == []


def test_rotting_list_ranks_by_frequency() -> None:
    def game_with(seed: int, cards: list[tuple[str, int]]) -> dict[str, Any]:
        # cards: (name, offered_windows); never cast.
        per_card = [
            {
                "seat": 1,
                "card": name,
                "offered_castable": n,
                "cast": 0,
                "first_cast_round": None,
            }
            for name, n in cards
        ]
        return {
            "status": "ok",
            "pod": "p",
            "seed": seed,
            "players": 4,
            "per_card": per_card,
            "rounds": 10.0,
        }

    report = {
        "games": [
            game_with(1, [("A", 5), ("B", 4)]),
            game_with(2, [("A", 3), ("C", 2)]),  # C below the 3-window threshold
            game_with(3, [("B", 6)]),
        ]
    }
    cards = pdr.aggregate_cards(report)
    rotting = [(e["card"], e["games_rotted"]) for e in cards["rotting"]]
    # A rotted in games 1+2, B in games 1+3; C never (only 2 windows in game 2).
    assert rotting == [("A", 2), ("B", 2)]
    names = [c["card"] for c in cards["cards"]]
    assert "C" in names  # still listed in per-card figures


def test_totals_unchanged_for_existing_fixture() -> None:
    # Rows without per_card (old reports) aggregate cleanly and totals are
    # unaffected by the new section.
    rows = [
        {
            "pod": "real",
            "seed": seed,
            "players": 4,
            "status": "ok",
            "rounds": 10.0,
            "spells_cast": 40.0,
            "turns": 40,
        }
        for seed in (1, 2)
    ]
    report: dict[str, Any] = {"jar": "bridge.jar", "games": rows}
    out = pdr.totals(report)
    assert out["spells_cast"] == 80.0
    assert out["games_ok"] == 2
    cards = pdr.aggregate_cards(report)
    assert cards["cards"] == []
    assert cards["rotting"] == []
    assert pdr.format_rotting(cards) == [
        "most rotting cards (offered castable, never cast):",
        "  (none)",
    ]


def test_run_prints_top_ten_rotting(capsys: Any) -> None:
    per_card = [
        {
            "seat": 1,
            "card": f"Card{i:02d}",
            "offered_castable": 5,
            "cast": 0,
            "first_cast_round": None,
        }
        for i in range(12)
    ]
    game = {
        "status": "ok",
        "pod": "p",
        "seed": 1,
        "players": 4,
        "per_card": per_card,
        "rounds": 10.0,
    }
    cards = pdr.aggregate_cards({"games": [game]})
    lines = pdr.format_rotting(cards)
    # Header + 10 cards (limit), the 11th and 12th are cut off.
    assert len(lines) == 11
    assert lines[0].startswith("most rotting cards")
