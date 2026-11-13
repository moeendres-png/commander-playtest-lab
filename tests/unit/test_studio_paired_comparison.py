"""Paired deck comparison on Studio logs (#1267): pairing, stop rule, censoring.

All data is synthetic. The scripted player writes a real Studio game log per game
and reads its exposure back from the log, exactly as the recorded-game player
does, so the tests cover the whole log path without an engine.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from commander_lab.qualification.current_boundary.bridge_launcher import (
    canonical_xmage_engine_pin,
)
from commander_lab.studio import paired_comparison
from commander_lab.studio.card_outcomes import game_exposures
from commander_lab.studio.paired_comparison import (
    PlayedGame,
    compare_logs,
    run_comparison_series,
)

COMMIT = "a" * 40
BASE = "deck/base"
VARIANT = "deck/variant"
OPP1 = "deck/opp1"
OPP2 = "deck/opp2"
OPPONENTS = (OPP1, OPP2)


def _write_log(
    folder: Path,
    game_id: str,
    *,
    decks: list[str],
    winners: list[int],
    seed: int,
    commit: str = COMMIT,
    status: str | None = "finished",
) -> Path:
    header = {
        "kind": "header",
        "schema": "studio-game-log-1",
        "game_id": game_id,
        "seed": seed,
        "engine_commit": commit,
        "pilot": "Pilot 1.0.0",
        "decision_policy": "policy-1",
        "seats": [
            {"seat": seat, "deck_id": deck, "commanders": [f"Cmd {seat}"]}
            for seat, deck in enumerate(decks)
        ],
    }
    lines: list[dict[str, object]] = [header]
    if status is not None:
        lines.append({"kind": "result", "status": status, "winner_seats": winners})
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{game_id}.jsonl"
    path.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
    return path


def _table(arm: str, seat: int) -> list[str]:
    """Seat-ordered decks of one comparison game: the contender in ``seat``."""
    order = [BASE if arm == "base" else VARIANT, OPP1, OPP2]
    return [order[(index - seat) % 3] for index in range(3)]


class _ScriptedPlayer:
    """A PairPlayer: ``winner(arm, seed, seat)`` names the winning seat of a game."""

    def __init__(
        self,
        folder: Path,
        winner: Callable[[str, int, int], int],
        fail: Callable[[str, int, int], str | None] | None = None,
    ) -> None:
        self.folder = folder
        self.winner = winner
        self.fail = fail or (lambda arm, seed, seat: None)
        self.calls: list[tuple[str, int, int]] = []

    def __call__(self, arm: str, seed: int, seat: int) -> PlayedGame:
        self.calls.append((arm, seed, seat))
        failure = self.fail(arm, seed, seat)
        if failure is not None:
            return {"exposure": None, "failure_class": failure}
        path = _write_log(
            self.folder,
            f"{arm}-s{seed}-t{seat}",
            decks=_table(arm, seat),
            winners=[self.winner(arm, seed, seat)],
            seed=seed,
        )
        return {"exposure": game_exposures(path), "failure_class": None}


def _variant_sweeps(arm: str, seed: int, seat: int) -> int:
    """The variant wins every game, the base loses every game."""
    return seat if arm == "variant" else (seat + 1) % 3


# --- pairing over logs -------------------------------------------------------------------


def test_pairing_needs_same_seed_seat_and_table(tmp_path: Path) -> None:
    _write_log(tmp_path, "b7", decks=[BASE, OPP1, OPP2], winners=[0], seed=7)
    _write_log(tmp_path, "v7", decks=[VARIANT, OPP1, OPP2], winners=[1], seed=7)
    _write_log(tmp_path, "v8", decks=[VARIANT, OPP1, OPP2], winners=[0], seed=8)
    _write_log(tmp_path, "b9", decks=[BASE, OPP1, "deck/opp3"], winners=[0], seed=9)
    _write_log(tmp_path, "v9", decks=[VARIANT, OPP1, OPP2], winners=[0], seed=9)
    result = compare_logs(tmp_path, base_deck_id=BASE, variant_deck_id=VARIANT)
    assert result["pairs_completed"] == 1
    pair = result["pairs"][0]
    assert (pair["seed"], pair["seat"]) == (7, 0)
    assert pair["base_credit"] == 1.0 and pair["variant_credit"] == 0.0
    assert result["difference_pp"] == -100.0
    # seed 8 has no base game; seed 9 sits at different tables: nothing pairs silently
    assert result["unpaired_base"] == 1 and result["unpaired_variant"] == 2


def test_duplicate_keys_pair_off_in_game_id_order(tmp_path: Path) -> None:
    _write_log(tmp_path, "b2", decks=[BASE, OPP1, OPP2], winners=[0], seed=5)
    _write_log(tmp_path, "b1", decks=[BASE, OPP1, OPP2], winners=[1], seed=5)
    _write_log(tmp_path, "v1", decks=[VARIANT, OPP1, OPP2], winners=[0], seed=5)
    result = compare_logs(tmp_path, base_deck_id=BASE, variant_deck_id=VARIANT)
    assert result["pairs_completed"] == 1
    assert result["pairs"][0]["base_game_id"] == "b1"
    assert result["unpaired_base"] == 1


def test_no_pairs_is_reported_not_scored(tmp_path: Path) -> None:
    _write_log(tmp_path, "b1", decks=[BASE, OPP1, OPP2], winners=[0], seed=1)
    result = compare_logs(tmp_path, base_deck_id=BASE, variant_deck_id=VARIANT)
    assert result["status"] == "NO_PAIRS" and result["stop_reason"] == "NO_PAIRS"
    assert result["difference_pp"] is None and result["sign_test_p_value"] is None
    assert result["unpaired_base"] == 1


def test_paired_statistics_match_hand_computed_values(tmp_path: Path) -> None:
    # 10 pairs at seat 0: the variant wins 7, the base wins 3, no ties.
    for seed in range(1, 11):
        variant_won = seed <= 7
        _write_log(
            tmp_path,
            f"b{seed}",
            decks=[BASE, OPP1, OPP2],
            winners=[1] if variant_won else [0],
            seed=seed,
        )
        _write_log(
            tmp_path,
            f"v{seed}",
            decks=[VARIANT, OPP1, OPP2],
            winners=[0] if variant_won else [1],
            seed=seed,
        )
    result = compare_logs(tmp_path, base_deck_id=BASE, variant_deck_id=VARIANT)
    assert result["pairs_completed"] == 10
    assert result["base_rate"] == 0.3 and result["variant_rate"] == 0.7
    assert result["difference_pp"] == 40.0
    assert result["variant_only_wins"] == 7 and result["baseline_only_wins"] == 3
    assert result["tied_pairs"] == 0
    # exact sign test: 2 * (1 + 10 + 45 + 120) / 1024
    assert result["sign_test_p_value"] == 0.34375
    ci = result["difference_ci95_pp"]
    assert ci is not None and ci[0] < 0.0 < ci[1]
    assert result["detectable_difference_pp"] is not None
    assert result["status"] == "NOT_DECIDED" and result["stop_reason"] == "SINGLE_LOOK"
    assert result["pods"] == [{"opponents": [OPP1, OPP2], "pairs": 10}]


def test_mixed_engine_commits_are_refused_unless_allowed(tmp_path: Path) -> None:
    _write_log(tmp_path, "b1", decks=[BASE, OPP1, OPP2], winners=[0], seed=1)
    _write_log(tmp_path, "v1", decks=[VARIANT, OPP1, OPP2], winners=[0], seed=1, commit="b" * 40)
    with pytest.raises(ValueError, match="mixed engine commits"):
        compare_logs(tmp_path, base_deck_id=BASE, variant_deck_id=VARIANT)
    pooled = compare_logs(tmp_path, base_deck_id=BASE, variant_deck_id=VARIANT, allow_mixed=True)
    assert len(pooled["engine_commits"]) == 2
    assert any("mixed engine commits" in w for w in pooled["warnings"])


# --- the series that stops by itself -----------------------------------------------------


def test_clear_sweep_stops_at_the_second_look(tmp_path: Path) -> None:
    player = _ScriptedPlayer(tmp_path, _variant_sweeps)
    result = run_comparison_series(
        base_deck_id=BASE,
        variant_deck_id=VARIANT,
        seeds=list(range(1, 41)),
        tested_seats=[0],
        budget_pairs=40,
        look_every_pairs=10,
        play=player,
        execution={"series_id": "test-sweep"},
    )
    # The first look (10 pairs, O'Brien-Fleming level ~0.0001) cannot decide even a
    # sweep (sign test 2/2**10 = 0.002); the second look (20 pairs, level ~0.0055)
    # decides it. The remaining 20 pairs are never played.
    assert result["status"] == "DECIDED" and result["answer"] == "ABOVE"
    assert result["stop_reason"] == "DECIDED_ABOVE"
    assert result["looks_used"] == 2 and result["looks_planned"] == 4
    assert result["pairs_played"] == 20 and result["pairs_completed"] == 20
    assert len(player.calls) == 40
    assert result["difference_pp"] == 100.0
    assert result["seeds"] == list(range(1, 21))


def test_even_series_runs_to_the_budget_and_reports_not_decided(tmp_path: Path) -> None:
    def winner(arm: str, seed: int, seat: int) -> int:
        variant_won = seed % 2 == 0
        return seat if (arm == "variant") == variant_won else (seat + 1) % 3

    player = _ScriptedPlayer(tmp_path, winner)
    result = run_comparison_series(
        base_deck_id=BASE,
        variant_deck_id=VARIANT,
        seeds=list(range(1, 21)),
        tested_seats=[0],
        budget_pairs=20,
        look_every_pairs=10,
        play=player,
    )
    assert result["status"] == "NOT_DECIDED"
    assert result["stop_reason"] == "BUDGET_EXHAUSTED"
    assert result["pairs_played"] == 20 and result["pairs_completed"] == 20
    assert result["difference_pp"] == 0.0
    assert len(player.calls) == 40


def test_failed_game_censors_its_pair_and_is_never_a_loss(tmp_path: Path) -> None:
    player = _ScriptedPlayer(
        tmp_path,
        _variant_sweeps,
        fail=lambda arm, seed, seat: "EngineError" if (arm, seed) == ("variant", 3) else None,
    )
    result = run_comparison_series(
        base_deck_id=BASE,
        variant_deck_id=VARIANT,
        seeds=list(range(1, 11)),
        tested_seats=[0],
        budget_pairs=10,
        look_every_pairs=5,
        play=player,
    )
    assert result["pairs_completed"] == 9 and result["pairs_censored"] == 1
    assert result["games_failed_variant"] == 1 and result["games_failed_base"] == 0
    assert result["failure_classes"]["variant"] == {"EngineError": 1}
    # the finished base game of seed 3 is in no pair: it scores nowhere
    assert all(pair["seed"] != 3 for pair in result["pairs"])
    assert result["base_rate"] == 0.0 and result["variant_rate"] == 1.0
    assert result["status"] == "DECIDED" and result["pairs_played"] == 10


def _thirty_wins_ten_ties(arm: str, seed: int, seat: int) -> int:
    """Difference +1 on seeds 1..30, a tie (both lose) on seeds 31..40."""
    if seed <= 30:
        return seat if arm == "variant" else (seat + 1) % 3
    return (seat + 1) % 3


def test_threshold_above_is_decided(tmp_path: Path) -> None:
    player = _ScriptedPlayer(tmp_path, _thirty_wins_ten_ties)
    result = run_comparison_series(
        base_deck_id=BASE,
        variant_deck_id=VARIANT,
        seeds=list(range(1, 41)),
        tested_seats=[0],
        budget_pairs=40,
        look_every_pairs=40,
        threshold_pp=55.0,
        play=player,
    )
    # mean difference 75 pp, interval about [61, 89]: entirely above 55
    assert result["difference_pp"] == 75.0
    assert result["status"] == "DECIDED" and result["answer"] == "ABOVE"


def test_threshold_not_above_is_decided(tmp_path: Path) -> None:
    player = _ScriptedPlayer(tmp_path, _thirty_wins_ten_ties)
    result = run_comparison_series(
        base_deck_id=BASE,
        variant_deck_id=VARIANT,
        seeds=list(range(1, 41)),
        tested_seats=[0],
        budget_pairs=40,
        look_every_pairs=40,
        threshold_pp=95.0,
        play=player,
    )
    # the same interval [61, 89] lies entirely at or below 95: not greater
    assert result["status"] == "DECIDED" and result["answer"] == "NOT_ABOVE"
    assert result["stop_reason"] == "DECIDED_NOT_ABOVE"


def test_seat_rotation_pairs_every_seat(tmp_path: Path) -> None:
    def winner(arm: str, seed: int, seat: int) -> int:
        variant_won = seed == 1
        return seat if (arm == "variant") == variant_won else (seat + 1) % 3

    player = _ScriptedPlayer(tmp_path, winner)
    result = run_comparison_series(
        base_deck_id=BASE,
        variant_deck_id=VARIANT,
        seeds=[1, 2],
        tested_seats=[0, 1, 2],
        budget_pairs=6,
        look_every_pairs=6,
        play=player,
        execution={"series_id": "test-rotation", "rotate_seats": True},
    )
    assert {seat for _, _, seat in player.calls} == {0, 1, 2}
    assert result["pairs_completed"] == 6
    assert result["tested_seats"] == [0, 1, 2]
    assert all(pair["seat"] in (0, 1, 2) for pair in result["pairs"])
    assert result["status"] == "NOT_DECIDED"


def test_result_names_provenance_and_execution(tmp_path: Path) -> None:
    player = _ScriptedPlayer(tmp_path, _variant_sweeps)
    result = run_comparison_series(
        base_deck_id=BASE,
        variant_deck_id=VARIANT,
        seeds=list(range(1, 41)),
        tested_seats=[0],
        budget_pairs=40,
        look_every_pairs=10,
        play=player,
        execution={"series_id": "test-prov"},
    )
    assert result["data_class"] == "SIMULATED_RESULT"
    assert result["engine_pin"] == canonical_xmage_engine_pin()
    assert result["engine_commits"] == [COMMIT]
    assert result["pilots"] == ["Pilot 1.0.0"]
    assert result["decision_policies"] == ["policy-1"]
    assert result["pods"] == [{"opponents": [OPP1, OPP2], "pairs": 20}]
    assert result["execution"]["mode"] == "series"
    assert result["execution"]["series_id"] == "test-prov"
    assert "cluster_difference_stats" in result["question"]["method"]
    text = paired_comparison.format_comparison(result)
    assert "DECIDED_ABOVE" in text and "pairs 20" in text


def test_series_configuration_is_refused_before_any_game() -> None:
    def forbidden(arm: str, seed: int, seat: int) -> PlayedGame:
        raise AssertionError("no game may be played for an invalid configuration")

    with pytest.raises(ValueError, match="different decks"):
        run_comparison_series(
            base_deck_id=BASE,
            variant_deck_id=BASE,
            seeds=[1, 2],
            tested_seats=[0],
            budget_pairs=2,
            look_every_pairs=1,
            play=forbidden,
        )
    with pytest.raises(ValueError, match="planned units"):
        run_comparison_series(
            base_deck_id=BASE,
            variant_deck_id=VARIANT,
            seeds=[1, 2],
            tested_seats=[0],
            budget_pairs=3,
            look_every_pairs=1,
            play=forbidden,
        )
    with pytest.raises(ValueError, match="at least"):
        run_comparison_series(
            base_deck_id=BASE,
            variant_deck_id=VARIANT,
            seeds=[1, 2],
            tested_seats=[0],
            budget_pairs=1,
            look_every_pairs=1,
            play=forbidden,
        )
