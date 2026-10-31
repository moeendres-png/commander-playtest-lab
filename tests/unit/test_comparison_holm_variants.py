"""E6 stage 3: with several variants in one run, Holm decides which verdicts stand.

Scripted batch records drive aggregate_comparison (no JVM). One pair per seed (no seat rotation)
keeps the arithmetic to the exact sign test, so the expected Holm values are hand numbers.
"""

from __future__ import annotations

import importlib.util
import random
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from commander_lab.engine.rules import full_game_comparison as fgc
from commander_lab.engine.rules.full_game_comparison import (
    DeckComparisonSpec,
    PairedVariantResult,
    aggregate_comparison,
    effective_p_value,
    plan_comparison_cases,
    sign_test_p_value,
    student_t_quantile,
)
from tests.unit.test_comparison_precision import (
    XMAGE_COMMIT,
    _deck,
    _other_seat,
    _records_for,
    _report,
)

SEEDS = tuple(range(1, 11))
Script = dict[str, frozenset[int]]  # variant id -> seeds the variant wins
BASELINE_WINS = frozenset({10})  # the one baseline serves every variant


def _wins(count: int, *, seed_10: bool = False) -> frozenset[int]:
    """The variant wins seeds 1..count (and seed 10 if asked). Against a baseline that wins only
    seed 10 that is ``count`` variant-only pairs plus one baseline-only pair, or none if the
    variant wins seed 10 as well (both winning is a tie)."""
    return frozenset(range(1, count + 1)) | (frozenset({10}) if seed_10 else frozenset())


def _spec(variant_ids: tuple[str, ...]) -> DeckComparisonSpec:
    contenders = (
        _deck("base", 1),
        *(_deck(variant_id, index + 2) for index, variant_id in enumerate(variant_ids)),
    )
    return DeckComparisonSpec(
        comparison_id="holm-test",
        contenders=contenders,
        opponents=(_deck("opp-a", 20), _deck("opp-b", 21), _deck("opp-c", 22)),
        seeds=SEEDS,
        rotate_seats=False,
        xmage_commit=XMAGE_COMMIT,
    )


def _winner(script: Script) -> Callable[[str, int, int], tuple[int, ...]]:
    def winner(contender_id: str, seed: int, seat: int) -> tuple[int, ...]:
        wins = BASELINE_WINS if contender_id == "base" else script[contender_id]
        return (seat,) if seed in wins else (_other_seat(seat),)

    return winner


def _run(script: Script, **kwargs: Any) -> tuple[PairedVariantResult, ...]:
    spec = _spec(tuple(script))
    cases = plan_comparison_cases(spec)
    report = aggregate_comparison(spec, _report(_records_for(cases, _winner(script))), **kwargs)
    return report.paired


def _by_id(results: tuple[PairedVariantResult, ...]) -> dict[str, PairedVariantResult]:
    return {result.variant_deck_id: result for result in results}


def test_single_variant_run_is_not_touched_by_holm() -> None:
    (alone,) = _run({"v1": _wins(9)})
    assert (alone.variant_only_wins, alone.baseline_only_wins) == (9, 1)
    assert alone.sign_test_p_value == pytest.approx(sign_test_p_value(9, 1))
    assert alone.holm_adjusted_p_value is None and alone.holm_withheld_verdict is None
    assert alone.effective_p_value == pytest.approx(alone.sign_test_p_value)
    assert alone.verdict == "VARIANT_BETTER"


def test_hand_arithmetic_of_the_holm_values() -> None:
    results = _by_id(_run({"strong": _wins(9), "mid": _wins(6), "weak": _wins(3)}))
    p = {name: result.sign_test_p_value for name, result in results.items()}
    assert p["strong"] < p["mid"] < p["weak"]
    # Holm step-down: smallest p times 3, next times 2, last times 1, never decreasing.
    expected = {
        "strong": 3 * p["strong"],
        "mid": max(3 * p["strong"], 2 * p["mid"]),
        "weak": max(3 * p["strong"], 2 * p["mid"], p["weak"]),
    }
    for name, result in results.items():
        assert result.holm_adjusted_p_value == pytest.approx(min(1.0, expected[name]))
        assert result.effective_p_value == pytest.approx(p[name])


def test_a_verdict_decided_alone_can_be_withheld_in_a_family_and_says_which() -> None:
    (alone,) = _run({"v1": _wins(9)})
    assert alone.verdict == "VARIANT_BETTER" and alone.sign_test_p_value < 0.05
    family = _by_id(_run({f"v{index}": _wins(9) for index in range(1, 6)}))
    assert all(result.verdict == "NO_CLEAR_DIFFERENCE" for result in family.values())
    assert all(result.holm_withheld_verdict == "VARIANT_BETTER" for result in family.values())
    for result in family.values():
        assert result.sign_test_p_value < 0.05
        assert result.holm_adjusted_p_value == pytest.approx(5 * alone.sign_test_p_value)
        assert result.holm_adjusted_p_value is not None and result.holm_adjusted_p_value >= 0.05


def test_strong_evidence_survives_and_a_weak_neighbour_does_not_take_it_down() -> None:
    family = _by_id(_run({"strong": _wins(9, seed_10=True), "weak": _wins(4), "none": _wins(0)}))
    assert family["strong"].verdict == "VARIANT_BETTER"
    assert family["strong"].holm_withheld_verdict is None
    assert family["weak"].verdict == "NO_CLEAR_DIFFERENCE"
    assert family["weak"].holm_withheld_verdict is None  # never decided, so nothing was held back
    assert family["none"].verdict == "NO_CLEAR_DIFFERENCE"


def test_wrong_reason_control_without_holm_the_family_verdicts_come_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(fgc, "holm_adjust", lambda values: tuple(values))
    family = _by_id(_run({f"v{index}": _wins(9) for index in range(1, 6)}))
    assert all(result.verdict == "VARIANT_BETTER" for result in family.values())
    assert all(result.holm_withheld_verdict is None for result in family.values())


def test_a_variant_without_verdict_basis_is_not_part_of_the_family() -> None:
    script = {"v1": _wins(9), "v2": _wins(9)}
    spec = _spec(tuple(script))
    cases = plan_comparison_cases(spec)
    dropped = {
        case.case_id
        for case in cases
        if case.scenario.candidate_id == "v2" and case.scenario.seed > 4
    }
    records = [r for r in _records_for(cases, _winner(script)) if r.case_id not in dropped]
    paired = _by_id(aggregate_comparison(spec, _report(records)).paired)
    assert paired["v2"].verdict == "INSUFFICIENT"
    assert paired["v2"].effective_p_value is None and paired["v2"].holm_adjusted_p_value is None
    # v1 is alone in the family, so it is judged as in a single-variant run.
    assert paired["v1"].holm_adjusted_p_value is None
    assert paired["v1"].verdict == "VARIANT_BETTER"


def test_effective_p_value_cases() -> None:
    kwargs: dict[str, Any] = {
        "sign_p": 0.01,
        "variant_only": 10,
        "baseline_only": 0,
        "pairs": 40,
        "seed_clusters": 10,
        "cluster_df": 9,
        "difference": 0.25,
    }
    # t exactly at the 5% quantile gives a two-sided p of 0.05, the larger of the two values.
    critical = student_t_quantile(0.975, 9)
    assert effective_p_value(cluster_t=critical, **kwargs) == pytest.approx(0.05, abs=1e-6)
    # A strong t leaves the sign test p as the larger one.
    assert effective_p_value(cluster_t=40.0, **kwargs) == pytest.approx(0.01)
    # A t that leans the other way, or no usable test, is 1.
    assert effective_p_value(cluster_t=-3.0, **kwargs) == 1.0
    assert effective_p_value(cluster_t=None, **{**kwargs, "cluster_df": 0}) == 1.0
    # One pair per seed: the sign test stands alone.
    assert effective_p_value(cluster_t=None, **{**kwargs, "pairs": 10}) == 0.01
    # Zero spread: the sign test over the seeds, 2 / 2**G for G = df + 1 seeds leaning one way.
    small = {**kwargs, "sign_p": 1e-4}
    assert effective_p_value(cluster_t=None, **small) == pytest.approx(2.0 * 0.5**10)
    assert effective_p_value(cluster_t=None, **{**small, "difference": -0.25}) == 1.0
    # Equal counts: no direction, no basis.
    assert effective_p_value(cluster_t=5.0, **{**kwargs, "baseline_only": 10}) == 1.0


def test_family_invariants_on_random_scripts() -> None:
    """Holm only withholds: a decided family verdict is the single-variant verdict with an
    adjusted p below the level; a withheld one was decided alone; adjusted >= effective."""
    rng = random.Random(20261031)
    for _ in range(60):
        count = rng.randint(2, 5)
        script = {
            f"v{index}": frozenset(rng.sample(SEEDS, rng.randint(0, len(SEEDS))))
            for index in range(1, count + 1)
        }
        family = _by_id(_run(script))
        for name, result in family.items():
            (alone,) = _run({name: script[name]})
            assert result.holm_adjusted_p_value is not None
            assert result.effective_p_value is not None
            assert result.holm_adjusted_p_value >= result.effective_p_value - 1e-12
            decided_alone = alone.verdict in ("VARIANT_BETTER", "BASELINE_BETTER")
            if result.verdict in ("VARIANT_BETTER", "BASELINE_BETTER"):
                assert result.verdict == alone.verdict
                assert result.holm_adjusted_p_value < 0.05
                assert result.holm_withheld_verdict is None
            else:
                assert (result.holm_withheld_verdict is not None) == decided_alone


def _script_module() -> Any:
    path = Path(__file__).resolve().parents[2] / "scripts/run_full_game_deck_comparison.py"
    spec = importlib.util.spec_from_file_location("run_full_game_deck_comparison", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_summary_names_the_verdict_holm_did_not_carry() -> None:
    cli = _script_module()
    family = _run({f"v{index}": _wins(9) for index in range(1, 6)})
    rows = [result.model_dump(mode="json") for result in family]
    lines = cli._holm_lines(rows[0], len(rows))
    assert any("Holm over 5 variants: adjusted p=" in line for line in lines)
    assert any("this was VARIANT_BETTER" in line for line in lines)
    assert cli._holm_lines(rows[0], 1) == []
    assert cli._holm_lines({"verdict": "NO_CLEAR_DIFFERENCE"}, 5) == []
