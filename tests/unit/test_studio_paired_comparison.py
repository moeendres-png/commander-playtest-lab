"""Paired deck comparison on Studio logs (#1267): pairing, stop rule, censoring.

All data is synthetic. The scripted player writes a real Studio game log per game
and reads its exposure back from the log, exactly as the recorded-game player
does, so the tests cover the whole log path without an engine.
"""

from __future__ import annotations

import ast
import hashlib
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
    assert result["discordant_share"] is None
    assert result["discordant_share_if_independent"] is None
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
    # all 10 pairs discordant; independent games at 30 % / 70 % would give 0.3*0.3+0.7*0.7
    assert result["discordant_share"] == 1.0
    assert result["discordant_share_if_independent"] == pytest.approx(0.58)
    # exact sign test: 2 * (1 + 10 + 45 + 120) / 1024
    assert result["sign_test_p_value"] == 0.34375
    ci = result["difference_ci95_pp"]
    assert ci is not None and ci[0] < 0.0 < ci[1]
    assert result["detectable_difference_pp"] is not None
    assert result["status"] == "NOT_DECIDED" and result["stop_reason"] == "SINGLE_LOOK"
    assert result["pods"] == [{"opponents": [OPP1, OPP2], "pairs": 10}]


def test_discordant_share_counts_tied_pairs_in_the_denominator(tmp_path: Path) -> None:
    # 10 pairs: variant only 3, base only 1, both win 1, both lose 5 -> rates 0.2 / 0.4
    outcomes = {1: (0, 1), 2: (0, 1), 3: (0, 1), 4: (1, 0), 5: (1, 1)}
    for seed in range(1, 11):
        base_won, variant_won = outcomes.get(seed, (0, 0))
        _write_log(
            tmp_path,
            f"b{seed}",
            decks=[BASE, OPP1, OPP2],
            winners=[0] if base_won else [1],
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
    assert result["base_rate"] == 0.2 and result["variant_rate"] == 0.4
    assert result["tied_pairs"] == 6
    # 4 discordant of 10 pairs (not of the 4 discordant ones)
    assert result["discordant_share"] == 0.4
    # independent games: 0.2 * 0.6 + 0.4 * 0.8 = 0.44 (not 0.2**2 + 0.4**2 = 0.2)
    assert result["discordant_share_if_independent"] == pytest.approx(0.44)


def test_mixed_engine_commits_are_refused_unless_allowed(tmp_path: Path) -> None:
    _write_log(tmp_path, "b1", decks=[BASE, OPP1, OPP2], winners=[0], seed=1)
    _write_log(tmp_path, "v1", decks=[VARIANT, OPP1, OPP2], winners=[0], seed=1, commit="b" * 40)
    with pytest.raises(ValueError, match="mixed engine commits"):
        compare_logs(tmp_path, base_deck_id=BASE, variant_deck_id=VARIANT)
    pooled = compare_logs(tmp_path, base_deck_id=BASE, variant_deck_id=VARIANT, allow_mixed=True)
    assert len(pooled["engine_commits"]) == 2
    assert any("mixed engine commits" in w for w in pooled["warnings"])


def test_pairs_of_two_table_sizes_are_never_averaged_unless_allowed(tmp_path: Path) -> None:
    """#1694: each pair has one table size, but pairs of 2 and 3 seats in one folder have other
    base win rates; their differences are not averaged into one answer unless allowed."""
    _write_log(tmp_path, "b1", decks=[BASE, OPP1, OPP2], winners=[0], seed=1)
    _write_log(tmp_path, "v1", decks=[VARIANT, OPP1, OPP2], winners=[1], seed=1)
    _write_log(tmp_path, "b2", decks=[BASE, OPP1], winners=[1], seed=2)
    _write_log(tmp_path, "v2", decks=[VARIANT, OPP1], winners=[0], seed=2)
    with pytest.raises(ValueError, match="mixed table sizes in one comparison: 2, 3"):
        compare_logs(tmp_path, base_deck_id=BASE, variant_deck_id=VARIANT)
    pooled = compare_logs(tmp_path, base_deck_id=BASE, variant_deck_id=VARIANT, allow_mixed=True)
    assert pooled["pairs_completed"] == 2
    assert "mixed table sizes pooled: 2, 3" in pooled["warnings"]
    # one table size only: no refusal, no warning
    (tmp_path / "b2.jsonl").unlink()
    (tmp_path / "v2.jsonl").unlink()
    single = compare_logs(tmp_path, base_deck_id=BASE, variant_deck_id=VARIANT)
    assert single["pairs_completed"] == 1
    assert not any("table sizes" in w for w in single["warnings"])


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


def test_look_window_chunk_plan_keeps_seeds_and_assignment_when_games_per_jvm_changes() -> None:
    """#1587: the default 16 (was 6) only regroups the games of a look window into chunks.

    Every game is keyed by (arm, seat, seed), its game id by series, arm, seed and seat, never by
    the chunk it sits in; so the set of games, the seat of each seed and the seed order inside one
    (arm, seat) are the same for every ``games_per_jvm``.
    """
    units = [(seed, seat) for seed in range(1000, 1010) for seat in (0, 1, 2, 3)]

    def games_of(plan: list[tuple[str, int, list[int]]]) -> list[tuple[str, int, int]]:
        return [(arm, seat, seed) for arm, seat, seeds in plan for seed in seeds]

    plans = {
        per_jvm: paired_comparison.plan_look_window_chunks(units, workers=4, games_per_jvm=per_jvm)
        for per_jvm in (1, 6, 16, 24)
    }
    expected = sorted((arm, seat, seed) for arm in paired_comparison.ARMS for seed, seat in units)
    for per_jvm, plan in plans.items():
        assert sorted(games_of(plan)) == expected, per_jvm
        assert all(len(seeds) <= per_jvm for _arm, _seat, seeds in plan)
        for arm in paired_comparison.ARMS:
            for seat in (0, 1, 2, 3):
                in_cell = [seed for a, st, seed in games_of(plan) if (a, st) == (arm, seat)]
                assert in_cell == sorted(in_cell) == [s for s, u_seat in units if u_seat == seat]
    # the chunk plan itself does change: that is the whole effect of the new default
    assert plans[6] != plans[16]
    assert games_of(plans[16]) != [] and len(plans[16]) < len(plans[6])
    # a short window is capped by ceil(games / workers), so 16 and 24 give the same chunks there
    short = [(seed, seat) for seed in (1, 2, 3) for seat in (0, 1)]
    assert paired_comparison.plan_look_window_chunks(
        short, workers=4, games_per_jvm=16
    ) == paired_comparison.plan_look_window_chunks(short, workers=4, games_per_jvm=24)


def test_parallel_window_player_matches_sequential_statistics_and_early_stops(
    tmp_path: Path,
) -> None:
    units = [(seed, seat) for seed in (1, 2) for seat in (0, 1)]
    chunks = paired_comparison.plan_look_window_chunks(units, workers=2, games_per_jvm=3)
    assert chunks == [
        ("base", 0, [1, 2]),
        ("base", 1, [1, 2]),
        ("variant", 0, [1, 2]),
        ("variant", 1, [1, 2]),
    ]

    seq_player = _ScriptedPlayer(
        tmp_path / "seq",
        _variant_sweeps,
        fail=lambda arm, seed, seat: "EngineError" if (arm, seed, seat) == ("base", 3, 0) else None,
    )
    par_inner = _ScriptedPlayer(
        tmp_path / "par",
        _variant_sweeps,
        fail=lambda arm, seed, seat: "EngineError" if (arm, seed, seat) == ("base", 3, 0) else None,
    )
    progress_seen: list[int] = []

    base_deck = SimpleNamespace(deck_id=BASE)
    var_deck = SimpleNamespace(deck_id=VARIANT)
    opp_decks = [SimpleNamespace(deck_id=OPP1), SimpleNamespace(deck_id=OPP2)]
    par_player = paired_comparison.parallel_window_player(
        tmp_path / "par",
        series_id="eq",
        base_deck=base_deck,  # type: ignore[arg-type]
        variant_deck=var_deck,  # type: ignore[arg-type]
        opponents=opp_decks,  # type: ignore[arg-type]
        paths_by_deck_id={},
        seeds=list(range(1, 21)),
        tested_seats=[0, 1],
        budget_pairs=40,
        look_every_pairs=10,
        workers=4,
        games_per_jvm=6,
        play_single=par_inner,
        on_pair_done=progress_seen.append,
    )

    seq_res = run_comparison_series(
        base_deck_id=BASE,
        variant_deck_id=VARIANT,
        seeds=list(range(1, 21)),
        tested_seats=[0, 1],
        budget_pairs=40,
        look_every_pairs=10,
        play=seq_player,
    )
    par_res = run_comparison_series(
        base_deck_id=BASE,
        variant_deck_id=VARIANT,
        seeds=list(range(1, 21)),
        tested_seats=[0, 1],
        budget_pairs=40,
        look_every_pairs=10,
        play=par_player,
    )

    for key in (
        "status",
        "answer",
        "stop_reason",
        "pairs_played",
        "pairs_completed",
        "pairs_censored",
        "looks_used",
        "looks_planned",
        "base_rate",
        "variant_rate",
        "difference_pp",
        "difference_ci95_pp",
        "decision_ci_pp",
        "sign_test_p_value",
        "seeds",
    ):
        assert par_res[key] == seq_res[key], key  # type: ignore[literal-required]
    # Look 3 (30 pairs) decides, so pairs 31..40 were never scheduled or played
    assert len(par_inner.calls) == len(seq_player.calls) == seq_res["pairs_played"] * 2
    assert progress_seen[-1] == seq_res["pairs_played"]


def test_parallel_window_player_announces_each_played_game_before_the_pair_is_done(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Progress per game: every game of a chunk is announced when the engine has played it, before
    the chunk returns, and the pair counting and the results are those of a run without it."""
    deck_ids = ("b", "v", "o1", "o2", "o3")
    decks = {d: SimpleNamespace(deck_id=d) for d in deck_ids}
    events: list[str] = []

    def fake_play_recorded_games(  # type: ignore[no-untyped-def]
        _data, _paths, series_games, *, on_played=None, on_game=None, **_kwargs
    ):
        for game in series_games:
            if on_played is not None:
                on_played(game.game_id)
        for game in series_games:
            if on_game is not None:
                on_game({"game_id": game.game_id})
        return [{"game_id": g.game_id, "seed": g.seed} for g in series_games]

    monkeypatch.setattr(
        "commander_lab.studio.play_batch.play_recorded_games", fake_play_recorded_games
    )
    monkeypatch.setattr(
        paired_comparison,
        "_summary_to_played_game",
        lambda _s: {"exposure": None, "failure_class": None},
    )
    played: list[tuple[str, int, int]] = []
    pair_counts: list[int] = []

    def on_played(arm: str, seed: int, seat: int) -> None:
        played.append((arm, seed, seat))
        events.append("played")

    def on_pair(count: int) -> None:
        pair_counts.append(count)
        events.append("pair")

    player = paired_comparison.parallel_window_player(
        tmp_path,
        series_id="prog",
        base_deck=decks["b"],  # type: ignore[arg-type]
        variant_deck=decks["v"],  # type: ignore[arg-type]
        opponents=[decks["o1"], decks["o2"], decks["o3"]],  # type: ignore[arg-type]
        paths_by_deck_id={d: tmp_path / f"{d}.json" for d in deck_ids},
        seeds=[1, 2, 3],
        tested_seats=[0],
        budget_pairs=3,
        look_every_pairs=3,
        workers=1,
        games_per_jvm=6,
        on_pair_done=on_pair,
        on_game_played=on_played,
    )
    player("base", 1, 0)  # runs the window of the three pairs
    assert sorted(played) == [(arm, seed, 0) for arm in ("base", "variant") for seed in (1, 2, 3)]
    assert pair_counts == [1, 2, 3]
    # all six games are announced before the first pair is counted as done
    assert events == ["played"] * 6 + ["pair"] * 3


def test_a_game_that_failed_is_not_announced_as_played(tmp_path: Path) -> None:
    played: list[tuple[str, int, int]] = []
    inner = _ScriptedPlayer(
        tmp_path,
        _variant_sweeps,
        fail=lambda arm, seed, seat: "EngineError" if (arm, seed) == ("base", 2) else None,
    )
    player = paired_comparison.parallel_window_player(
        tmp_path,
        series_id="prog2",
        base_deck=SimpleNamespace(deck_id=BASE),  # type: ignore[arg-type]
        variant_deck=SimpleNamespace(deck_id=VARIANT),  # type: ignore[arg-type]
        opponents=[SimpleNamespace(deck_id=OPP1), SimpleNamespace(deck_id=OPP2)],  # type: ignore[arg-type]
        paths_by_deck_id={},
        seeds=[1, 2],
        tested_seats=[0],
        budget_pairs=2,
        look_every_pairs=2,
        workers=1,
        games_per_jvm=1,
        play_single=inner,
        on_game_played=lambda *key: played.append(key),
    )
    player("base", 1, 0)
    assert sorted(played) == [("base", 1, 0), ("variant", 1, 0), ("variant", 2, 0)]


def test_play_recorded_games_forwards_explicit_series_engine_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from commander_lab.studio.play_batch import SeriesGame, play_recorded_games

    root = Path(__file__).resolve().parents[2]
    decks = [
        root / "data/decks/deckbau/chulane_current.json",
        root / "data/decks/precons/2026_lorehold_spirit.json",
    ]
    seen_commands: list[tuple[str, ...] | None] = []

    class _FakeRunner:
        def __init__(
            self,
            _data: str | Path,
            _headers: dict[str, tuple[str, dict[str, object]]],
            *,
            command: tuple[str, ...] | None,
            **_kwargs: object,
        ) -> None:
            self.command = command
            seen_commands.append(command)

        def run_batch(self, _items: object) -> list[object]:
            return [RuntimeError("stop-before-jvm")]

        def recorder_of(self, _sid: str) -> SimpleNamespace:
            return SimpleNamespace(close=lambda *_a, **_k: {"status": "failed"})

    monkeypatch.setattr("commander_lab.studio.play_batch.BatchRecordingRunner", _FakeRunner)
    monkeypatch.setattr(
        "commander_lab.studio.play_batch.close_recorded_game",
        lambda _rec, _out: {"game_id": "g1", "status": "failed", "failure_class": "Stopped"},
    )
    custom_cmd = (
        "java",
        "-XX:+UseSerialGC",
        "-Dcommanderlab.fullGame.gamesPerJvm=6",
        "-jar",
        "/x.jar",
        "full-game",
    )
    summaries = play_recorded_games(
        tmp_path,
        decks,
        [SeriesGame(1000, "g1")],
        private_card_repository=True,
        command=custom_cmd,
    )
    assert seen_commands == [custom_cmd]
    assert summaries == [{"game_id": "g1", "status": "failed", "failure_class": "Stopped"}]


# --- the series pool: long-lived JVMs across look windows (#1585) ---------------------------


class _FakePool:
    """Stands in for ``GamePool``: plays each task with a scripted player, in a chosen order."""

    def __init__(self, player: _ScriptedPlayer, *, reverse: bool = False) -> None:
        self.player = player
        self.reverse = reverse
        self.runs: list[list[object]] = []
        self.closed = False
        self.results: dict[str, PlayedGame] = {}

    def run(self, tasks, *, on_played=None, on_done=None, should_cancel=None, record=None):  # type: ignore[no-untyped-def]
        self.runs.append(list(tasks))
        self.record = record
        out = {}
        for task in reversed(tasks) if self.reverse else tasks:
            if should_cancel is not None and should_cancel():
                break
            arm, seed, seat = task.task_id.split(":")
            played = self.player(arm, int(seed), int(seat))
            self.results[task.game_id] = played
            if on_played is not None and played["failure_class"] is None:
                on_played(task)
            summary = {"game_id": task.game_id, "status": "finished"}
            out[task.task_id] = summary
            if on_done is not None:
                on_done(task, summary)
        return out

    def summary(self) -> dict[str, object]:
        return {"executor": "fake-pool"}

    def close(self) -> None:
        self.closed = True


def _pool_player(
    tmp_path: Path, pool: _FakePool, monkeypatch: pytest.MonkeyPatch, **overrides: object
) -> paired_comparison.WindowPlayer:
    monkeypatch.setattr(
        paired_comparison,
        "_summary_to_played_game",
        lambda summary: pool.results[summary["game_id"]],
    )
    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"jar")  # the pool plans every game with the JAR's hash (S1, #1660)
    for deck_id in (BASE, VARIANT, OPP1, OPP2):
        # the pool plans every game with the hash of its deck files (S1, #1660)
        tmp_path.joinpath(f"{deck_id.split('/')[1]}.json").write_text(deck_id, encoding="utf-8")
    options: dict[str, object] = {
        "series_id": "pl",
        "base_deck": SimpleNamespace(deck_id=BASE),
        "variant_deck": SimpleNamespace(deck_id=VARIANT),
        "opponents": [SimpleNamespace(deck_id=OPP1), SimpleNamespace(deck_id=OPP2)],
        "paths_by_deck_id": {
            d: tmp_path / f"{d.split('/')[1]}.json" for d in (BASE, VARIANT, OPP1, OPP2)
        },
        "seeds": list(range(1, 21)),
        "tested_seats": [0, 1],
        "budget_pairs": 40,
        "look_every_pairs": 10,
        "workers": 4,
        "games_per_jvm": 6,
        "pool": pool,
        "command": ("java", "-jar", str(jar), "full-game"),
    }
    options.update(overrides)
    return paired_comparison.parallel_window_player(tmp_path, **options)  # type: ignore[arg-type]


@pytest.mark.parametrize("reverse", [False, True])
def test_the_pool_gives_the_series_of_the_sequential_player_whatever_the_completion_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reverse: bool
) -> None:
    fail = lambda arm, seed, seat: "EngineError" if (arm, seed, seat) == ("base", 3, 0) else None  # noqa: E731
    seq_player = _ScriptedPlayer(tmp_path / "seq", _variant_sweeps, fail=fail)
    pool = _FakePool(
        _ScriptedPlayer(tmp_path / "pool", _variant_sweeps, fail=fail), reverse=reverse
    )
    progress: list[int] = []
    player = _pool_player(tmp_path, pool, monkeypatch, on_pair_done=progress.append)

    common = {
        "base_deck_id": BASE,
        "variant_deck_id": VARIANT,
        "seeds": list(range(1, 21)),
        "tested_seats": [0, 1],
        "budget_pairs": 40,
        "look_every_pairs": 10,
    }
    seq_res = run_comparison_series(**common, play=seq_player)  # type: ignore[arg-type]
    pool_res = run_comparison_series(**common, play=player)  # type: ignore[arg-type]

    for key in (
        "status", "answer", "stop_reason", "pairs_played", "pairs_completed", "pairs_censored",
        "looks_used", "looks_planned", "base_rate", "variant_rate", "difference_pp",
        "difference_ci95_pp", "decision_ci_pp", "sign_test_p_value", "seeds", "failure_classes",
    ):  # fmt: skip
        assert pool_res[key] == seq_res[key], key  # type: ignore[literal-required]
    # the series stopped at look {looks_used}: the pool was asked for one run per window played
    # and never for a game beyond the stop
    assert len(pool.runs) == seq_res["looks_used"] < seq_res["looks_planned"]
    assert [len(run) for run in pool.runs] == [20] * len(pool.runs)
    assert sum(len(run) for run in pool.runs) == seq_res["pairs_played"] * 2
    assert progress[-1] == seq_res["pairs_played"]
    # the pool belongs to the player: it stays open between windows and ends with close()
    assert pool.closed is False
    assert player.pool_summary() == {"executor": "fake-pool"}
    player.close()
    assert pool.closed is True


def test_the_pool_is_given_the_games_of_a_window_with_their_seeds_ids_and_tables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pool = _FakePool(_ScriptedPlayer(tmp_path / "p", _variant_sweeps))
    player = _pool_player(
        tmp_path,
        pool,
        monkeypatch,
        seeds=[10, 11],
        tested_seats=[0, 1],
        budget_pairs=4,
        look_every_pairs=4,
    )
    player("base", 10, 0)
    (window,) = pool.runs
    # base and variant of a unit sit next to each other; no chunk by (arm, seat), all in one list
    assert [(t.task_id, t.game_id) for t in window] == [
        ("base:10:0", "pl-base-s10-t0"),
        ("variant:10:0", "pl-variant-s10-t0"),
        ("base:10:1", "pl-base-s10-t1"),
        ("variant:10:1", "pl-variant-s10-t1"),
        ("base:11:0", "pl-base-s11-t0"),
        ("variant:11:0", "pl-variant-s11-t0"),
        ("base:11:1", "pl-base-s11-t1"),
        ("variant:11:1", "pl-variant-s11-t1"),
    ]
    names = lambda task: [Path(p).stem for p in task.deck_paths]  # noqa: E731
    by_id = {t.task_id: t for t in window}
    # the contender sits in the tested seat, the opponents keep their order around it
    assert names(by_id["base:10:0"]) == ["base", "opp1", "opp2"]
    assert names(by_id["variant:10:1"]) == ["opp2", "variant", "opp1"]
    assert {t.seed for t in window} == {10, 11}


def test_a_series_resumed_in_the_middle_of_a_window_asks_the_pool_for_the_missing_games_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pool = _FakePool(_ScriptedPlayer(tmp_path / "p", _variant_sweeps))
    done = {
        (arm, seed, 0): {"exposure": None, "failure_class": None}
        for seed in (1, 2)
        for arm in ("base", "variant")
    }
    player = _pool_player(
        tmp_path,
        pool,
        monkeypatch,
        seeds=[1, 2, 3, 4],
        tested_seats=[0],
        budget_pairs=4,
        look_every_pairs=4,
        preloaded=done,
    )
    player("base", 3, 0)
    assert [t.task_id for t in pool.runs[0]] == [
        "base:3:0",
        "variant:3:0",
        "base:4:0",
        "variant:4:0",
    ]


def test_cancelling_a_pool_series_raises_the_cancel_error_and_stops_handing_out_games(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pool = _FakePool(_ScriptedPlayer(tmp_path / "p", _variant_sweeps))
    flag = {"stop": False}

    class Stopped(Exception):
        pass

    player = _pool_player(
        tmp_path,
        pool,
        monkeypatch,
        is_cancelled=lambda: flag["stop"],
        cancel_error_factory=Stopped,
        on_game_result=lambda *_a: flag.update(stop=True),
    )
    with pytest.raises(Stopped):
        player("base", 1, 0)
    assert len(pool.player.calls) == 1  # the pool saw the flag after the first game ended


def test_a_pool_series_plans_complete_tasks_and_a_manifest_and_journals_through_the_pool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """S1 (#1660): every planned game is in the manifest before the first one is played."""
    from commander_lab.studio import series_record

    pool = _FakePool(_ScriptedPlayer(tmp_path / "p", _variant_sweeps))
    player = _pool_player(
        tmp_path,
        pool,
        monkeypatch,
        seeds=[10, 11],
        tested_seats=[0, 1],
        budget_pairs=4,
        look_every_pairs=2,
    )
    player("base", 10, 0)
    record = pool.record
    assert isinstance(record, series_record.SeriesRecord)
    manifest = json.loads(record.manifest_path.read_text(encoding="utf-8"))
    assert record.manifest_path.parent.name == "pl"
    # both windows (4 pairs, 8 games) are in the manifest, not only the first one
    assert len(manifest["games"]) == 8 and len(pool.runs[0]) == 4
    task = pool.runs[0][0]
    assert task.seat_styles == (0.5, 0.5, 0.5) and len(set(task.deck_sha256)) == 3
    assert task.deck_sha256[0] == series_record.file_sha256(task.deck_paths[0])
    assert task.jar_sha256 == hashlib.sha256(b"jar").hexdigest()
    assert task.game_key is not None and manifest["games"][0]["game_key"] == task.game_key


@pytest.mark.parametrize("skip_forced", [False, True])
def test_the_manifest_key_of_a_pool_series_is_the_game_key_of_its_pin_and_command_switch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, skip_forced: bool
) -> None:
    """S1 (#1660): the configured engine pin and the command's forced-pass switch are in the key."""
    from commander_lab.studio import game_pool, series_record

    pin = "c" * 40
    monkeypatch.setattr(paired_comparison, "canonical_xmage_engine_pin", lambda: pin)
    jar = tmp_path / "bridge.jar"
    flag = f"-Dcommanderlab.fullGame.skipForcedDecisions={str(skip_forced).lower()}"
    pool = _FakePool(_ScriptedPlayer(tmp_path / "p", _variant_sweeps))
    player = _pool_player(
        tmp_path, pool, monkeypatch, command=("java", flag, "-jar", str(jar), "full-game")
    )
    player("base", 1, 0)
    manifest = json.loads(pool.record.manifest_path.read_text(encoding="utf-8"))
    keys = {game["game_id"]: game["game_key"] for game in manifest["games"]}
    assert pool.runs and pool.runs[0]
    for task in pool.runs[0]:
        expected = series_record.game_key(
            jar_sha256=hashlib.sha256(b"jar").hexdigest(),
            engine_pin=pin,
            pilot_fingerprints=[game_pool.seat_pilot_fingerprint(0.5)] * len(task.deck_paths),
            seat_styles=[0.5] * len(task.deck_paths),
            deck_sha256=[series_record.file_sha256(path) for path in task.deck_paths],
            seed=task.seed,
            strategy="generic",
            table_options=None,
            skip_forced_decisions=skip_forced,
            round_limit=None,
        )
        assert task.game_key == expected and keys[task.game_id] == expected
        assert task.engine_pin == pin and task.skip_forced_decisions is skip_forced


def test_a_pool_series_without_a_bridge_jar_plans_no_game(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from commander_lab.studio.game_pool import GamePoolError

    pool = _FakePool(_ScriptedPlayer(tmp_path / "p", _variant_sweeps))
    player = _pool_player(tmp_path, pool, monkeypatch, command=("wrapper", "full-game"))
    with pytest.raises(GamePoolError, match="JAR"):
        player("base", 1, 0)
    assert pool.runs == []  # nothing handed to the pool


def test_a_determinism_violation_ends_the_window_player(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from commander_lab.studio.series_record import DeterminismViolation

    pool = _FakePool(_ScriptedPlayer(tmp_path / "p", _variant_sweeps))

    def violating_run(tasks, **_kwargs):  # type: ignore[no-untyped-def]
        raise DeterminismViolation(tasks[0].game_key, ["a" * 64, "b" * 64], ["g1", "g2"])

    pool.run = violating_run  # type: ignore[method-assign]
    player = _pool_player(tmp_path, pool, monkeypatch)
    with pytest.raises(DeterminismViolation, match="DETERMINISM_VIOLATION"):
        player("base", 1, 0)


def test_a_pool_series_takes_the_wall_limit_of_its_seat_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from commander_lab.studio import table_spec

    created: list[dict[str, object]] = []

    class _Recorded:
        def __init__(self, folder: object, **kwargs: object) -> None:
            created.append(kwargs)

        def run(self, tasks, *, on_done=None, **_kwargs):  # type: ignore[no-untyped-def]
            for task in tasks:
                on_done(task, {"game_id": task.game_id, "status": "failed"})
            return {}

        def close(self) -> None:
            pass

    monkeypatch.setattr("commander_lab.studio.game_pool.GamePool", _Recorded)
    monkeypatch.setattr(table_spec, "game_wall_limit_seconds", lambda seats: 100.0 * seats)
    monkeypatch.setattr(
        paired_comparison,
        "_summary_to_played_game",
        lambda _s: {"exposure": None, "failure_class": "X"},
    )
    tmp_path.joinpath("x.json").write_text("{}", encoding="utf-8")
    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"jar")
    player = paired_comparison.parallel_window_player(
        tmp_path,
        series_id="wl",
        base_deck=SimpleNamespace(deck_id=BASE),  # type: ignore[arg-type]
        variant_deck=SimpleNamespace(deck_id=VARIANT),  # type: ignore[arg-type]
        opponents=[SimpleNamespace(deck_id=OPP1), SimpleNamespace(deck_id=OPP2)],  # type: ignore[list-item]
        paths_by_deck_id={d: tmp_path / "x.json" for d in (BASE, VARIANT, OPP1, OPP2)},
        seeds=[1],
        tested_seats=[0],
        budget_pairs=1,
        look_every_pairs=1,
        workers=1,
        games_per_jvm=6,
        series_pool=True,
        command=("java", "-jar", str(jar), "full-game"),
    )
    player("base", 1, 0)
    assert created[0]["game_wall_limit_seconds"] == 300.0  # three seats


def test_the_pool_is_off_by_default_and_a_switch_turns_it_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    created: list[dict[str, object]] = []

    class _Recorded:
        def __init__(self, folder: object, **kwargs: object) -> None:
            created.append({"folder": folder, **kwargs})

        def run(self, tasks, *, on_done=None, **_kwargs):  # type: ignore[no-untyped-def]
            for task in tasks:
                on_done(task, {"game_id": task.game_id, "status": "failed"})
            return {}

        def summary(self) -> dict[str, object]:
            return {}

        def close(self) -> None:
            created.append({"closed": True})

    monkeypatch.setattr("commander_lab.studio.game_pool.GamePool", _Recorded)
    monkeypatch.delenv("COMMANDER_LAB_STUDIO_SERIES_POOL", raising=False)
    tmp_path.joinpath("x.json").write_text("{}", encoding="utf-8")
    tmp_path.joinpath("b.jar").write_bytes(b"jar")  # the pool plans with the JAR's hash
    monkeypatch.chdir(tmp_path)
    options = {
        "series_id": "sw",
        "base_deck": SimpleNamespace(deck_id=BASE),
        "variant_deck": SimpleNamespace(deck_id=VARIANT),
        "opponents": [SimpleNamespace(deck_id=OPP1), SimpleNamespace(deck_id=OPP2)],
        "paths_by_deck_id": {d: tmp_path / "x.json" for d in (BASE, VARIANT, OPP1, OPP2)},
        "seeds": [1],
        "tested_seats": [0],
        "budget_pairs": 1,
        "look_every_pairs": 1,
        "workers": 3,
        "games_per_jvm": 6,
        "command": ("java", "-jar", "b.jar", "full-game"),
    }
    off = paired_comparison.parallel_window_player(tmp_path, **options)  # type: ignore[arg-type]
    assert off.pool_summary() is None and created == []

    monkeypatch.setenv("COMMANDER_LAB_STUDIO_SERIES_POOL", "1")
    monkeypatch.setattr(
        paired_comparison,
        "_summary_to_played_game",
        lambda _s: {"exposure": None, "failure_class": "X"},
    )
    on = paired_comparison.parallel_window_player(tmp_path, **options)  # type: ignore[arg-type]
    assert created == []  # nothing starts before the first window
    on("base", 1, 0)
    assert created[0]["workers"] == 3
    assert created[0]["private_card_repository"] is True  # parallel JVMs: own card repository
    assert created[0]["command"] == ("java", "-jar", "b.jar", "full-game")
    on.close()
    assert created[-1] == {"closed": True}


def test_a_series_refuses_games_of_two_pilot_fingerprints() -> None:
    """#1658: the fingerprint, not the constant version string, is the pilot identity; a
    game without one never pools with a game that has one."""
    from commander_lab.studio import paired_comparison as pc

    def game(fingerprint: str | None) -> dict[str, object]:
        return {
            "game_id": f"g-{fingerprint}",
            "engine_commit": "c",
            "pilot": "GenericCommanderPilot 1.0.0",
            "pilot_fingerprint": fingerprint,
            "decision_policy": "p",
        }

    same, _ = pc._check_provenance([game("a" * 64), game("a" * 64)], allow_mixed=False)  # type: ignore[list-item]
    assert same["pilot"] == ["fp:" + "a" * 64]
    for other in ("b" * 64, None):
        with pytest.raises(ValueError, match="mixed pilot versions"):
            pc._check_provenance([game("a" * 64), game(other)], allow_mixed=False)  # type: ignore[list-item]


# --- S1 (#1660): a determinism violation in the journal ends the series on every path ---------


def _stored_series_with_journal(folder: Path, series_id: str, *, violation: bool) -> None:
    """A failed series on disk that is otherwise resumable, with a manifest and a journal."""
    from commander_lab.studio import series_record
    from commander_lab.studio.games import games_folder

    games = games_folder(folder)
    raw = {
        "series_id": series_id,
        "status": "failed",
        "error": "worker exited",  # an ordinary error: the series would be resumable
        "opponent_deck_ids": ["opp/1"],
        "seed_plan": {"first_seed": 1, "seeds_planned": 1},
        "tested_seats": [0],
        "budget_pairs": 1,
        "threshold_pp": 5.0,
    }
    games.joinpath(f"{series_id}.paired.json").write_text(json.dumps(raw), encoding="utf-8")
    decks = games / "paired_decks" / series_id
    decks.mkdir(parents=True)
    decks.joinpath("base-a.json").write_text("{}", encoding="utf-8")
    decks.joinpath("variant-a.json").write_text("{}", encoding="utf-8")
    key = "k" * 64
    record = series_record.SeriesRecord.open(
        folder,
        series_id,
        games=[{"game_id": "g1", "game_key": key}, {"game_id": "g2", "game_key": key}],
        table_hash=None,
        table=None,
    )
    record.record("g1", {"status": "finished", "semantic_transcript_sha256": "a" * 64})
    second = "b" * 64 if violation else "a" * 64
    try:
        record.record("g2", {"status": "finished", "semantic_transcript_sha256": second})
    except series_record.DeterminismViolation:
        assert violation


@pytest.mark.parametrize("pool_switch", [None, "1"])
def test_a_series_with_a_determinism_violation_in_its_journal_is_not_resumable_on_any_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pool_switch: str | None
) -> None:
    from commander_lab.studio import paired_series

    if pool_switch is None:
        monkeypatch.delenv("COMMANDER_LAB_STUDIO_SERIES_POOL", raising=False)  # chunked path
    else:
        monkeypatch.setenv("COMMANDER_LAB_STUDIO_SERIES_POOL", pool_switch)  # pool path
    manager = paired_series.PairedSeriesManager()
    _stored_series_with_journal(tmp_path, "clean", violation=False)
    _stored_series_with_journal(tmp_path, "violated", violation=True)
    clean = manager.get_series(tmp_path, "clean")
    assert clean is not None and clean["resumable"] is True  # the control: same files, no violation
    violated = manager.get_series(tmp_path, "violated")
    assert violated is not None and violated["resumable"] is False
    with pytest.raises(ValueError, match=r"DETERMINISM_VIOLATION.*nicht fortsetzbar"):
        manager.resume_series(tmp_path, "violated", play_override=lambda *_a: {})  # type: ignore[arg-type,return-value]
    assert manager.get_job("violated") is None  # no job, no lock left behind


def test_a_journal_without_a_readable_manifest_blocks_the_resume(tmp_path: Path) -> None:
    from commander_lab.studio import paired_series, series_record

    _stored_series_with_journal(tmp_path, "nomani", violation=False)
    series_record.series_folder(tmp_path, "nomani").joinpath("manifest.json").unlink()
    manager = paired_series.PairedSeriesManager()
    view = manager.get_series(tmp_path, "nomani")
    assert view is not None and view["resumable"] is False
    with pytest.raises(series_record.ManifestMismatch, match="nicht prüfbar"):
        manager.resume_series(tmp_path, "nomani", play_override=lambda *_a: {})  # type: ignore[arg-type,return-value]
