"""E6 stage 2: a decided deck-comparison verdict needs the cluster-robust t test to agree.

The four seat rotations of one seed share a library shuffle, so the pair sign test counts them as
independent observations. These tests drive scripted batch records through aggregate_comparison
(no JVM): discordant pairs bunched into few seeds must not decide a verdict, the same number of
discordant pairs spread over many seeds must, and a run with one pair per seed keeps the pair test.
"""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import pytest

from commander_lab.engine.rules import full_game_comparison as fgc
from commander_lab.engine.rules.full_game_comparison import (
    aggregate_comparison,
    cluster_t_statistic,
    plan_comparison_cases,
    student_t_quantile,
)
from tests.unit.test_comparison_precision import (
    _other_seat,
    _records_for,
    _report,
    _spec,
)

SEEDS = tuple(range(1, 11))


def _winner_for(variant_wins: set[tuple[int, int]], baseline_wins: set[tuple[int, int]]):  # type: ignore[no-untyped-def]
    """The tested seat wins for the named (seed, seat) pairs of one contender, else loses."""

    def winner(contender_id: str, seed: int, seat: int) -> tuple[int, ...]:
        wins = variant_wins if contender_id == "variant" else baseline_wins
        return (seat,) if (seed, seat) in wins else (_other_seat(seat),)

    return winner


def _compare(winner, *, rotate: bool = True):  # type: ignore[no-untyped-def]
    spec = _spec(SEEDS, rotate=rotate)
    cases = plan_comparison_cases(spec)
    return aggregate_comparison(spec, _report(_records_for(cases, winner))).paired[0]


def test_cluster_t_statistic_hand_arithmetic() -> None:
    # Seeds: [1, 1], [0, 0], [1, 0]. n = 6, mean 0.5; per-seed sums of (d - mean): 1, -1, 0.
    # se^2 = G / (G - 1) * sum(u^2) / n^2 = 3/2 * 2 / 36, t = 0.5 / se.
    differences = [(1, 1.0), (1, 1.0), (2, 0.0), (2, 0.0), (3, 1.0), (3, 0.0)]
    statistic, df = cluster_t_statistic(differences)
    assert df == 2
    assert statistic == pytest.approx(0.5 / math.sqrt(1.5 * 2.0 / 36.0))


def test_cluster_t_statistic_without_spread_or_seeds() -> None:
    assert cluster_t_statistic([(1, 1.0), (2, 1.0)]) == (None, 1)  # same net in every seed
    assert cluster_t_statistic([(1, 1.0), (1, -1.0)]) == (None, 0)  # one seed
    assert cluster_t_statistic([(1, 1.0)]) == (None, 0)


def test_discordant_pairs_bunched_in_three_seeds_do_not_decide() -> None:
    # 12 variant-only pairs, all in seeds 1 to 3 (four rotations each): the pair test alone is
    # p = 2 / 2**12 < 0.05, but three of ten seeds carry the signal: t = 1.96 < t(9) = 2.26.
    variant_wins = {(seed, seat) for seed in (1, 2, 3) for seat in (1, 2, 3, 4)}
    paired = _compare(_winner_for(variant_wins, set()))
    assert paired.pairs_completed == 40
    assert (paired.variant_only_wins, paired.baseline_only_wins) == (12, 0)
    assert paired.sign_test_p_value < 0.05
    assert paired.cluster_t_df == 9
    assert paired.cluster_t_statistic == pytest.approx(1.96, abs=0.01)
    assert paired.cluster_t_statistic < student_t_quantile(0.975, 9)
    assert paired.verdict == "NO_CLEAR_DIFFERENCE"
    assert paired.pair_test_verdict == "VARIANT_BETTER"


def test_the_same_pairs_spread_over_ten_seeds_decide() -> None:
    # 12 variant-only pairs in ten seeds (two seeds carry two): t = 9.
    variant_wins = {(seed, 1) for seed in SEEDS} | {(1, 2), (2, 2)}
    paired = _compare(_winner_for(variant_wins, set()))
    assert (paired.variant_only_wins, paired.baseline_only_wins) == (12, 0)
    assert paired.cluster_t_statistic == pytest.approx(9.0)
    assert paired.verdict == "VARIANT_BETTER"
    assert paired.pair_test_verdict is None


def test_baseline_direction_needs_a_negative_t() -> None:
    baseline_wins = {(seed, 1) for seed in SEEDS} | {(1, 2), (2, 2)}
    paired = _compare(_winner_for(set(), baseline_wins))
    assert paired.cluster_t_statistic == pytest.approx(-9.0)
    assert paired.verdict == "BASELINE_BETTER"


def test_identical_seeds_decide_by_the_sign_test_over_seeds() -> None:
    # Every seed has the same net difference (no spread, so no t): ten seeds all for the variant
    # are 2 / 2**10 < 0.05; five seeds would be 2 / 2**5 = 0.0625 and cannot decide.
    variant_wins = {(seed, seat) for seed in SEEDS for seat in (1, 2, 3, 4)}
    paired = _compare(_winner_for(variant_wins, set()))
    assert paired.cluster_t_statistic is None and paired.cluster_t_df == 9
    assert paired.verdict == "VARIANT_BETTER"
    spec5 = _spec((1, 2, 3, 4, 5), rotate=True)
    cases5 = plan_comparison_cases(spec5)
    five = aggregate_comparison(
        spec5, _report(_records_for(cases5, _winner_for(variant_wins, set())))
    ).paired[0]
    assert five.sign_test_p_value < 0.05
    assert five.verdict == "NO_CLEAR_DIFFERENCE"
    assert five.pair_test_verdict == "VARIANT_BETTER"


def test_one_pair_per_seed_keeps_the_pair_test_alone() -> None:
    variant_wins = {(seed, 1) for seed in SEEDS}
    paired = _compare(_winner_for(variant_wins, set()), rotate=False)
    assert paired.pairs_completed == paired.seed_clusters_completed == 10
    assert paired.verdict == "VARIANT_BETTER"
    assert paired.pair_test_verdict is None


def test_wrong_reason_control_without_the_cluster_test_the_bunched_run_decides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the cluster test always agreed (a huge t), the bunched run would be decided again, so
    the test above cannot pass for the wrong reason."""
    monkeypatch.setattr(fgc, "cluster_t_statistic", lambda _differences: (99.0, 9))
    variant_wins = {(seed, seat) for seed in (1, 2, 3) for seat in (1, 2, 3, 4)}
    paired = _compare(_winner_for(variant_wins, set()))
    assert paired.verdict == "VARIANT_BETTER"


def _script_module():  # type: ignore[no-untyped-def]
    path = Path(__file__).resolve().parents[2] / "scripts/run_full_game_deck_comparison.py"
    spec = importlib.util.spec_from_file_location("run_full_game_deck_comparison", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_summary_names_the_pair_verdict_the_cluster_test_did_not_confirm() -> None:
    cli = _script_module()
    variant_wins = {(seed, seat) for seed in (1, 2, 3) for seat in (1, 2, 3, 4)}
    row = _compare(_winner_for(variant_wins, set())).model_dump(mode="json")
    lines = cli._cluster_t_lines(row)
    assert any("per seed t test: t=+1.96 (df 9)" in line for line in lines)
    assert any("pair test alone would say VARIANT_BETTER" in line for line in lines)


def test_summary_prints_nothing_for_old_payloads_and_one_pair_per_seed() -> None:
    cli = _script_module()
    assert cli._cluster_t_lines({"verdict": "NO_CLEAR_DIFFERENCE", "pairs_completed": 40}) == []
    one_per_seed = {
        "cluster_t_statistic": 2.5,
        "seed_clusters_completed": 10,
        "pairs_completed": 10,
    }
    assert cli._cluster_t_lines(one_per_seed) == []
