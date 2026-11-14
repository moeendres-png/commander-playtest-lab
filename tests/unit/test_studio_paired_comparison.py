"""Paired deck comparison on Studio logs (#1267): pairing, stop rule, censoring.

All data is synthetic. The scripted player writes a real Studio game log per game
and reads its exposure back from the log, exactly as the recorded-game player
does, so the tests cover the whole log path without an engine.
"""

from __future__ import annotations

import ast
import json
import math
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

from commander_lab.engine.rules.full_game_comparison import cluster_difference_stats
from commander_lab.qualification.current_boundary.bridge_launcher import (
    canonical_xmage_engine_pin,
)
from commander_lab.studio import __main__ as studio_cli
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
    seed: int | None,
    commit: str = COMMIT,
    status: str | None = "finished",
) -> Path:
    header: dict[str, object] = {
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
        max_censored_share=0.2,
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


# --- regression tests from the #1296 review ----------------------------------------------


def test_logs_mode_reports_failed_games_seeds_and_pin(tmp_path: Path) -> None:
    _write_log(tmp_path, "b1", decks=[BASE, OPP1, OPP2], winners=[0], seed=7)
    _write_log(tmp_path, "v1", decks=[VARIANT, OPP1, OPP2], winners=[0], seed=7)
    # a base game that never finished: no result record, so the loader skips
    # it — but it names the base deck and must not vanish from the result
    _write_log(tmp_path, "b-failed", decks=[BASE, OPP1, OPP2], winners=[0], seed=8, status=None)
    result = compare_logs(tmp_path, base_deck_id=BASE, variant_deck_id=VARIANT)
    assert result["pairs_completed"] == 1
    assert result["games_failed_base"] == 1 and result["games_failed_variant"] == 0
    # in logs mode the failed game belongs to no pair: censored stays 0 and a
    # warning says why, instead of the counters claiming a clean zero
    assert result["pairs_censored"] == 0
    assert any("failed or unfinished" in w for w in result["warnings"])
    # seeds names the completed seeds in logs mode; engine_pin is the current
    # canonical pin, and a warning keeps it from posing as the games' own pin
    assert result["seeds"] == [7] and result["seeds_completed"] == [7]
    assert any("engine_pin" in w for w in result["warnings"])


def test_seedless_games_warn_and_never_pair(tmp_path: Path) -> None:
    _write_log(tmp_path, "b7", decks=[BASE, OPP1, OPP2], winners=[0], seed=7)
    _write_log(tmp_path, "v7", decks=[VARIANT, OPP1, OPP2], winners=[0], seed=7)
    _write_log(tmp_path, "b-noseed", decks=[BASE, OPP1, OPP2], winners=[0], seed=None)
    result = compare_logs(tmp_path, base_deck_id=BASE, variant_deck_id=VARIANT)
    assert result["pairs_completed"] == 1
    assert any("carry no seed" in w for w in result["warnings"])


def test_zero_spread_rotation_counts_seeds_not_pairs(tmp_path: Path) -> None:
    player = _ScriptedPlayer(tmp_path, _variant_sweeps)
    result = run_comparison_series(
        base_deck_id=BASE,
        variant_deck_id=VARIANT,
        seeds=[1, 2, 3, 4, 5],
        tested_seats=[0, 1, 2],
        budget_pairs=15,
        look_every_pairs=5,
        play=player,
    )
    # Every pair difference is +1 (zero spread), so the sign test over the
    # seeds is the only evidence: at the second look the pairs come from only
    # 4 seeds (2/2**4 = 0.125, above the look level ~0.0157), and even all 5
    # seeds (2/2**5 = 0.0625) stay above the last level (~0.0336). Counting
    # pairs instead would decide at the second look (2/2**10 = 0.002) on
    # fewer independent shuffles than the count claims.
    assert result["status"] == "NOT_DECIDED"
    assert result["stop_reason"] == "BUDGET_EXHAUSTED"
    assert result["pairs_played"] == 15 and result["pairs_completed"] == 15
    assert result["difference_pp"] == 100.0
    assert len(player.calls) == 30


def test_zero_spread_sweep_decides_at_the_full_budget_on_seeds(tmp_path: Path) -> None:
    player = _ScriptedPlayer(tmp_path, _variant_sweeps)
    result = run_comparison_series(
        base_deck_id=BASE,
        variant_deck_id=VARIANT,
        seeds=list(range(1, 9)),
        tested_seats=[0, 1],
        budget_pairs=16,
        look_every_pairs=4,
        play=player,
    )
    # 8 seeds x 2 seats, every difference +1. The seed sign test reaches
    # 2/2**8 = 0.0078 only at the last look (level ~0.0264); at the third
    # look 6 seeds give 2/2**6 = 0.03125 > ~0.0181, so nothing may decide
    # before the full budget. Counting pairs would decide at the third look
    # (2/2**12 = 0.0005): the stop look proves the seeds are the unit, and
    # the sweep still decides once enough seeds lean one way.
    assert result["status"] == "DECIDED" and result["answer"] == "ABOVE"
    assert result["looks_used"] == 4 and result["looks_planned"] == 4
    assert result["pairs_played"] == 16 and result["pairs_completed"] == 16


def test_misseated_game_censors_its_pair(tmp_path: Path) -> None:
    def play(arm: str, seed: int, seat: int) -> PlayedGame:
        if arm == "variant" and seed == 2:
            # the game finished, but the variant sits at seat 1, not the tested seat
            path = _write_log(
                tmp_path, "v2-misseated", decks=[OPP1, VARIANT, OPP2], winners=[1], seed=seed
            )
        else:
            path = _write_log(
                tmp_path,
                f"{arm}-s{seed}-t{seat}",
                decks=_table(arm, seat),
                winners=[seat],
                seed=seed,
            )
        return {"exposure": game_exposures(path), "failure_class": None}

    result = run_comparison_series(
        base_deck_id=BASE,
        variant_deck_id=VARIANT,
        seeds=[1, 2],
        tested_seats=[0],
        budget_pairs=2,
        look_every_pairs=2,
        play=play,
    )
    assert result["pairs_completed"] == 1 and result["pairs_censored"] == 1
    assert result["games_failed_variant"] == 1 and result["games_failed_base"] == 0
    assert result["failure_classes"]["variant"] == {"Misseated": 1}
    assert any("did not seat" in w for w in result["warnings"])


def test_series_mixed_engine_commits_are_refused(tmp_path: Path) -> None:
    def play(arm: str, seed: int, seat: int) -> PlayedGame:
        path = _write_log(
            tmp_path,
            f"{arm}-s{seed}-t{seat}",
            decks=_table(arm, seat),
            winners=[seat],
            seed=seed,
            commit=COMMIT if arm == "base" else "b" * 40,
        )
        return {"exposure": game_exposures(path), "failure_class": None}

    with pytest.raises(ValueError, match="mixed engine commits"):
        run_comparison_series(
            base_deck_id=BASE,
            variant_deck_id=VARIANT,
            seeds=[1, 2],
            tested_seats=[0],
            budget_pairs=2,
            look_every_pairs=2,
            play=play,
        )


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


# --- regression tests from the #1309 review ----------------------------------------------


def test_censoring_above_threshold_stays_not_decided_with_reason(tmp_path: Path) -> None:
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
    assert result["status"] == "NOT_DECIDED"
    assert result["answer"] is None
    assert result["stop_reason"] == "CENSORING_LIMIT"
    assert any("max_censored_share" in w for w in result["warnings"])


def test_asymmetric_censoring_blocks_decision_even_below_share_limit(tmp_path: Path) -> None:
    # 3 failures in 80 pairs = 3.75% (below 5%), yet all 3 strike the variant arm (p = 0.25).
    player = _ScriptedPlayer(
        tmp_path,
        _variant_sweeps,
        fail=lambda arm, seed, seat: (
            "EngineError" if arm == "variant" and seed in (1, 2, 3) else None
        ),
    )
    result = run_comparison_series(
        base_deck_id=BASE,
        variant_deck_id=VARIANT,
        seeds=list(range(1, 81)),
        tested_seats=[0],
        budget_pairs=80,
        look_every_pairs=40,
        play=player,
    )
    assert result["pairs_censored"] == 3
    assert result["games_failed_base"] == 0 and result["games_failed_variant"] == 3
    assert result["status"] == "NOT_DECIDED"
    assert result["answer"] is None
    assert result["stop_reason"] == "ASYMMETRIC_CENSORING"
    assert any("one-sided censoring" in w for w in result["warnings"])


def test_minor_balanced_censoring_within_limit_still_decides(tmp_path: Path) -> None:
    # 1 censored pair in 40 (2.5% <= 5%, p = 1.0) is within the censoring guard.
    player = _ScriptedPlayer(
        tmp_path,
        _variant_sweeps,
        fail=lambda arm, seed, seat: "EngineError" if (arm, seed) == ("variant", 5) else None,
    )
    result = run_comparison_series(
        base_deck_id=BASE,
        variant_deck_id=VARIANT,
        seeds=list(range(1, 41)),
        tested_seats=[0],
        budget_pairs=40,
        look_every_pairs=40,
        play=player,
    )
    assert result["pairs_censored"] == 1
    assert result["status"] == "DECIDED" and result["answer"] == "ABOVE"


def test_decision_ci_uses_look_alpha_and_formats_distinct_label(tmp_path: Path) -> None:
    player = _ScriptedPlayer(tmp_path, _thirty_wins_ten_ties)
    # 95% CI is ~[60.98, 89.02] (contains 62.0); at significance_level=0.10 the 90%
    # decision CI is ~[63.32, 86.68] (strictly above 62.0), so the result decides ABOVE.
    result = run_comparison_series(
        base_deck_id=BASE,
        variant_deck_id=VARIANT,
        seeds=list(range(1, 41)),
        tested_seats=[0],
        budget_pairs=40,
        look_every_pairs=40,
        threshold_pp=62.0,
        significance_level=0.10,
        play=player,
    )
    assert result["status"] == "DECIDED" and result["answer"] == "ABOVE"
    assert result["decision_alpha"] == 0.1
    assert result["decision_level_pct"] == 90.0
    ci95 = result["difference_ci95_pp"]
    dci = result["decision_ci_pp"]
    assert ci95 is not None and dci is not None
    assert ci95[0] < 62.0 < dci[0]
    text = paired_comparison.format_comparison(result)
    assert "95% CI" in text
    assert "90% decision CI (alpha 0.1)" in text


def test_series_stops_on_first_mixed_game_before_playing_more(tmp_path: Path) -> None:
    calls: list[tuple[str, int, int]] = []

    def play(arm: str, seed: int, seat: int) -> PlayedGame:
        calls.append((arm, seed, seat))
        commit = COMMIT if arm == "base" else "b" * 40
        path = _write_log(
            tmp_path,
            f"{arm}-s{seed}-t{seat}",
            decks=_table(arm, seat),
            winners=[seat],
            seed=seed,
            commit=commit,
        )
        return {"exposure": game_exposures(path), "failure_class": None}

    with pytest.raises(ValueError, match="mixed engine commits"):
        run_comparison_series(
            base_deck_id=BASE,
            variant_deck_id=VARIANT,
            seeds=list(range(1, 21)),
            tested_seats=[0],
            budget_pairs=20,
            look_every_pairs=10,
            play=play,
        )
    # Stopped right after pair 1 variant; never played pairs 2..20.
    assert len(calls) == 2


def test_compare_decks_cli_validates_bounds_and_seats_before_loading_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = [str(tmp_path / f"missing-{i}.json") for i in range(8)]
    # Too many opponents (6 -> 7 seats > 6 max) fails before reading any file.
    args_too_many_opponents = [
        "compare-decks",
        "--base-deck",
        missing[0],
        "--variant-deck",
        missing[1],
        *[item for path in missing[2:] for item in ("--opponent", path)],
    ]
    assert studio_cli.main(args_too_many_opponents) == 2
    assert "1 to 5 opponents" in capsys.readouterr().err

    # Out-of-bounds --pairs fails before reading any file.
    for bad_pairs in ("1", "1001"):
        code = studio_cli.main(
            [
                "compare-decks",
                "--base-deck",
                missing[0],
                "--variant-deck",
                missing[1],
                "--opponent",
                missing[2],
                "--pairs",
                bad_pairs,
            ]
        )
        assert code == 2
        assert "pairs must be between" in capsys.readouterr().err

    # --seat 4 on a 4-seat table (3 opponents) must be rejected (formerly len(decks)==5 allowed it).
    code = studio_cli.main(
        [
            "compare-decks",
            "--base-deck",
            missing[0],
            "--variant-deck",
            missing[1],
            "--opponent",
            missing[2],
            "--opponent",
            missing[3],
            "--opponent",
            missing[4],
            "--seat",
            "4",
        ]
    )
    assert code == 2
    assert "0..3" in capsys.readouterr().err

    # --rotate-seats rotates only across table_size = 1 + len(opponents), not len(decks).
    seen_tested_seats: list[int] = []
    monkeypatch.setattr(
        "commander_lab.engine.rules.project.load_rules_deck_snapshot",
        lambda path: SimpleNamespace(deck_id=Path(path).stem),
    )
    monkeypatch.setattr(
        paired_comparison,
        "recorded_game_player",
        lambda *args, **kwargs: lambda arm, seed, seat: {"exposure": None, "failure_class": None},
    )

    def fake_run(**kwargs: object) -> dict[str, object]:
        seen_tested_seats.extend(list(kwargs["tested_seats"]))  # type: ignore[call-overload]
        return {
            "base_deck_id": BASE,
            "variant_deck_id": VARIANT,
            "data_class": "SIMULATED_RESULT",
            "status": "NO_PAIRS",
            "answer": None,
            "stop_reason": "NO_PAIRS",
            "question": {"threshold_pp": 0.0, "significance_level": 0.05, "method": "m"},
            "pairs_completed": 0,
            "pairs_censored": 0,
            "unpaired_base": 0,
            "unpaired_variant": 0,
            "games_failed_base": 0,
            "games_failed_variant": 0,
            "looks_used": 0,
            "looks_planned": 1,
            "difference_pp": None,
            "seeds_completed": [],
            "pods": [],
            "tested_seats": list(kwargs["tested_seats"]),  # type: ignore[call-overload]
            "engine_commits": [],
            "engine_pin": "0" * 40,
            "pilots": [],
            "warnings": [],
        }

    monkeypatch.setattr(paired_comparison, "run_comparison_series", fake_run)
    rotate_code = studio_cli.main(
        [
            "--data",
            str(tmp_path),
            "compare-decks",
            "--base-deck",
            str(tmp_path / "base.json"),
            "--variant-deck",
            str(tmp_path / "var.json"),
            "--opponent",
            str(tmp_path / "o1.json"),
            "--opponent",
            str(tmp_path / "o2.json"),
            "--opponent",
            str(tmp_path / "o3.json"),
            "--pairs",
            "8",
            "--look-every",
            "4",
            "--rotate-seats",
        ]
    )
    assert rotate_code == 0
    assert seen_tested_seats == [0, 1, 2, 3]


def test_arm_index_uses_lowest_seat_when_deck_is_seated_twice(tmp_path: Path) -> None:
    path = _write_log(
        tmp_path,
        "dup-seat",
        decks=[OPP1, BASE, BASE, OPP2],
        winners=[2],
        seed=9,
    )
    exposure = game_exposures(path)
    assert exposure is not None
    # Seat 2 won (win_credit=1.0) while lowest seat 1 lost (win_credit=0.0): seat 1 governs.
    index, seedless = paired_comparison._arm_index([exposure], BASE)
    assert seedless == 0
    assert index == {(9, 1, (OPP1, BASE, OPP2)): [("dup-seat", 0.0)]}


def test_equal_threshold_decides_not_above_zero_spread_and_positive_se(tmp_path: Path) -> None:
    # Zero spread: difference == 100.0 pp == threshold_pp must yield NOT_ABOVE (not ABOVE).
    sweep_player = _ScriptedPlayer(tmp_path / "sweep", _variant_sweeps)
    zero_spread = run_comparison_series(
        base_deck_id=BASE,
        variant_deck_id=VARIANT,
        seeds=list(range(1, 11)),
        tested_seats=[0],
        budget_pairs=10,
        look_every_pairs=10,
        threshold_pp=100.0,
        play=sweep_player,
    )
    assert zero_spread["status"] == "DECIDED"
    assert zero_spread["answer"] == "NOT_ABOVE"

    # Positive SE: difference + half == threshold (interval upper bound hits threshold) -> NOT_ABOVE.
    interval, _, se = cluster_difference_stats([(s, 1.0 if s <= 30 else 0.0) for s in range(1, 41)])
    assert interval is not None and se is not None and se > 0.0
    upper_pp = interval.high * 100.0
    if upper_pp / 100.0 < interval.high:
        upper_pp = math.nextafter(upper_pp, math.inf)
    mixed_player = _ScriptedPlayer(tmp_path / "mixed", _thirty_wins_ten_ties)
    positive_se = run_comparison_series(
        base_deck_id=BASE,
        variant_deck_id=VARIANT,
        seeds=list(range(1, 41)),
        tested_seats=[0],
        budget_pairs=40,
        look_every_pairs=40,
        threshold_pp=upper_pp,
        play=mixed_player,
    )
    assert positive_se["status"] == "DECIDED"
    assert positive_se["answer"] == "NOT_ABOVE"


def test_paired_comparison_and_card_outcomes_never_import_strength_or_tiers() -> None:
    studio_dir = Path(paired_comparison.__file__).resolve().parent
    forbidden = {"strength", "tiers"}
    offending: list[str] = []
    for filename in ("paired_comparison.py", "card_outcomes.py"):
        tree = ast.parse((studio_dir / filename).read_text(encoding="utf-8"), filename=filename)
        import_count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                import_count += 1
                for alias in node.names:
                    parts = set(alias.name.split("."))
                    if parts & forbidden:
                        offending.append(f"{filename} imports forbidden module {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                import_count += 1
                module_parts = set((node.module or "").split("."))
                imported_names = {alias.name for alias in node.names}
                if module_parts & forbidden:
                    offending.append(f"{filename} imports from forbidden module {node.module}")
                if (
                    node.module in (None, "commander_lab.studio")
                    or (node.module or "").startswith(".")
                ) and (imported_names & forbidden):
                    offending.append(
                        f"{filename} imports forbidden symbol {imported_names & forbidden}"
                    )
        assert import_count > 0, f"{filename} unexpectedly parsed zero import statements"
    assert offending == []
