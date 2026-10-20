"""card_synergy_report.py and threat_report.py read the report ``pilot_decision_report`` writes.

The fixtures come out of the real producer (``summarize``) so a renamed key in the report breaks
these tests; no JVM, no games are played.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(f"{name}_under_test", SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pdr = _load("pilot_decision_report")
synergy = _load("card_synergy_report")
threat = _load("threat_report")


def _record(seat: int, card: str, *, cast: bool) -> dict[str, Any]:
    return {
        "request": {
            "decision_class": "priority",
            "legal_options": [
                {
                    "option_id": "play",
                    "option_type": "cast_spell",
                    "metadata": {"ability_type": "spell", "source_name": card},
                },
                {"option_id": "pass", "option_type": "pass_priority", "metadata": {}},
            ],
            "pilot_state": {
                "phase": "main1",
                "step": "main",
                "turn_number": 5,
                "seat": seat,
                "actor_id": f"p{seat}",
                "active_player_id": f"p{seat}",
                "stack": [],
            },
        },
        "answer": {"selected_option_ids": ["play" if cast else "pass"]},
        "pilot_s": 0.01,
    }


def _game(
    winners: list[int], casts: dict[int, list[str]], offered: dict[int, list[str]] | None = None
):
    """A report row built by the real ``summarize``; ``casts`` is keyed by 1-based seat."""
    records = [
        _record(seat - 1, card, cast=True) for seat, cards in casts.items() for card in cards
    ]
    records += [
        _record(seat - 1, card, cast=False)
        for seat, cards in (offered or {}).items()
        for card in cards
    ]
    row = {"pod": "real", "seed": 1, "players": 4, "status": "ok", "winners": winners}
    return row | pdr.summarize(records, players=4)


def test_real_report_rows_carry_the_keys_the_analyses_read() -> None:
    row = _game([2], {1: ["Wrath of God"]})
    assert row["winners"] == [2]
    assert {"seat", "card", "cast"} <= set(row["per_card"][0])
    assert row["per_card"][0]["seat"] == 1  # seats are 1-based in the report


def test_offered_but_uncast_cards_are_not_played() -> None:
    (game,) = list(
        threat.ok_games({"games": [_game([1], {1: ["Bolt"]}, offered={2: ["Wrath of God"]})]})
    )
    assert game["cards_by_seat"][1] == {"Bolt"}
    assert game["cards_by_seat"][2] == set()


def test_threat_counts_cards_of_the_seats_that_beat_the_pilot() -> None:
    report = {
        "games": [
            _game([2], {1: ["Grizzly Bears"], 2: ["Wrath of God"]}),
            _game([2], {2: ["Wrath of God"]}),
            _game([1], {1: ["Grizzly Bears"]}),
        ]
    }
    games = threat.extract_threats(report)  # default pilot seat is 1
    assert [g["pilot_lost"] for g in games] == [True, True, False]
    (name, lift, appearances, loss_rate), *_ = threat.calculate_threats(games, min_games=1)
    assert name == "Wrath of God"
    assert appearances == 2 and loss_rate == 1.0
    assert lift > 1.0


def test_synergy_is_a_win_rate_of_the_seats_that_cast_both_cards() -> None:
    both = {1: ["Bolt", "Guide"]}
    report = {
        "games": [
            _game([1], both),
            _game([1], both),
            _game([1], both),
            _game([2], both),  # seat 1 cast both and lost: not every pair is a win
        ]
    }
    samples = synergy.extract_seat_samples(report)
    assert len(samples) == 16 and sum(s["won"] for s in samples) == 4  # one winner per game
    ((pair, lift, count, win_rate),) = synergy.calculate_synergies(samples, min_games=1)
    assert pair == ("Bolt", "Guide")
    assert count == 4 and win_rate == 0.75
    assert lift == 0.75 / 0.25


def test_synergy_ignores_low_count_and_failed_games() -> None:
    report = {"games": [_game([1], {1: ["Bolt", "Guide"]}), {"status": "failed", "error": "x"}]}
    samples = synergy.extract_seat_samples(report)
    assert synergy.calculate_synergies(samples, min_games=5) == []


def _run(script: str, report: dict[str, Any], tmp_path: Path, *args: str):
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), str(path), *args],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_cli_reads_a_real_shaped_report(tmp_path: Path) -> None:
    report = {"games": [_game([2], {1: ["Grizzly Bears"], 2: ["Wrath of God"]})]}
    threat_run = _run("threat_report.py", report, tmp_path, "--min-games", "1")
    assert threat_run.returncode == 0, threat_run.stderr
    assert "Wrath of God" in threat_run.stdout
    synergy_run = _run("card_synergy_report.py", report, tmp_path, "--min-games", "1")
    assert synergy_run.returncode == 0, synergy_run.stderr
    assert "Analyzed 4 seat samples" in synergy_run.stdout


def test_cli_rejects_a_report_without_finished_games(tmp_path: Path) -> None:
    for script in ("threat_report.py", "card_synergy_report.py"):
        result = _run(script, {"games": []}, tmp_path)
        assert result.returncode == 1
        assert "No valid games" in result.stderr
