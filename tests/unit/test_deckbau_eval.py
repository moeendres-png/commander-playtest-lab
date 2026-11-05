"""Tests for the deckbau handoff and fixed-pod telemetry (no bridge required)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from commander_lab.deck_readiness import main as readiness_main
from commander_lab.engine.rules.project import load_rules_deck_snapshot

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/deckbau_eval.py"
spec = importlib.util.spec_from_file_location("deckbau_eval", SCRIPT)
assert spec is not None and spec.loader is not None
deckbau = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deckbau)


def test_pods_have_three_distinct_public_opponents() -> None:
    assert set(deckbau.PODS) == {"precon", "mixed", "optimized"}
    for pod in deckbau.PODS.values():
        assert len(pod) == len(set(pod)) == 3
        for source in pod:
            assert (ROOT / source).is_file()
            deck = load_rules_deck_snapshot(ROOT / source)
            assert len(deck.mainboard) + len(deck.commander_names) == 100


def test_seed_validation() -> None:
    assert deckbau.seed_list("1-3,8") == [1, 2, 3, 8]
    for bad in ("", "1,1", "-1", "4-2"):
        with pytest.raises(ValueError):
            deckbau.seed_list(bad)


def test_module_readiness_accepts_normalized_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    payload = {
        "deck_id": "deckbau/test",
        "name": "Test",
        "commander": "Ishai, Ojutai Dragonspeaker",
        "cards": [
            {"oracle_name": "Plains", "quantity": 99, "zone": "main"},
        ],
    }
    path = tmp_path / "deck.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert readiness_main([str(path), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["ready"] is True
    assert report["decks"][0]["counts"]["NO_CARD_FACTS"] == 0


def test_candidate_metrics_are_seat_scoped_and_do_not_fabricate_measurements() -> None:
    games: list[dict[str, Any]] = [
        {
            "status": "ok",
            "winners": [1],
            "rounds": 8,
            "by_seat": {
                "1": {"own_turns": 8, "spells_cast": 12, "mana_payments_cancelled": 2},
                "2": {"own_turns": 8, "spells_cast": 70},
            },
            "per_card": [
                {"seat": 1, "card": "Arcane Signet", "offered_castable": 4, "cast": 0},
                {"seat": 2, "card": "Sol Ring", "offered_castable": 7, "cast": 7},
            ],
        },
        {
            "status": "ok",
            "winners": [2],
            "rounds": 6,
            "by_seat": {"1": {"own_turns": 6, "spells_cast": 6}},
        },
    ]
    result = deckbau.summarize_candidate(games)
    assert result["win_rate_completed_games"] == 0.5
    assert result["games_completed"] == 2
    assert result["mana_efficiency"]["status"] == "NOT_MEASURED"
    assert result["mana_efficiency"]["spells_cast_per_own_turn_proxy"] == 1.286
    assert result["mana_efficiency"]["cancelled_mana_payments"] == 2
    assert result["hand_residence_turns"]["status"] == "NOT_MEASURED"
    names = [row["card"] for row in result["hand_residence_turns"]["per_card_cast_opportunities"]]
    assert "Sol Ring" not in names
    assert "Arcane Signet" in names


def test_failed_game_is_not_a_win() -> None:
    result = deckbau.summarize_candidate([{"status": "failed", "error": "bridge exited"}])
    assert result["status"] == "failed"
    assert result["games_completed"] == 0
    assert result["win_rate_completed_games"] is None
