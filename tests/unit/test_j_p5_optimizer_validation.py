from __future__ import annotations

import json
from pathlib import Path

import pytest

from commander_lab.decision_statistics import holm_adjust, paired_randomization_p_value
from commander_lab.models import ObjectiveVector, VariantSwap
from commander_lab.optimization import DEFAULT_CONSTRAINTS, evaluate_constraints
from commander_lab.optimization.jp5 import build_recommendation_trace, paired_seed_set_identity
from commander_lab.tools.service import CommanderToolService, ToolExecutionError

ROOT = Path(__file__).resolve().parents[2]


def test_p5_holdout_is_sealed_and_untouched() -> None:
    data = (ROOT / "data/evals/holdout/J_P5_OPTIMIZER_HOLDOUT_v1.json").read_bytes()
    import hashlib

    assert (
        hashlib.sha256(data).hexdigest()
        == "b75e8622097221b00ad51322e2ad13fe5158cfd8647e92d2cb21a0d65b447203"
    )
    payload = json.loads(data)
    assert payload["status"] == "sealed_untouched"
    assert payload["outcomes_evaluated_at_seal"] is False
    assert payload["scenario_count"] == 24


def test_robust_objective_has_exact_required_axes() -> None:
    fields = set(ObjectiveVector.model_fields)
    assert fields == {
        "central_performance",
        "worst_quartile",
        "commander_independence",
        "rebuild",
        "finish_reliability",
        "matchup_robustness",
        "pod_size_robustness",
        "seat_robustness",
        "opponent_uncertainty",
        "physical_allocation",
    }


def test_current_projection_applies_inactive_korvold_release_without_rewriting_p5() -> None:
    svc = CommanderToolService(ROOT)
    sealed = json.loads(
        (ROOT / "data/collections/current/J_P5_CURRENT_OPTIMIZATION_AVAILABILITY.json").read_text()
    )["cards"]
    release = json.loads(
        (ROOT / "data/collections/current/INACTIVE_FORMER_OWN_DECK_RELEASES.json").read_text()
    )["released_allocations"]
    expected = {str(name): int(quantity) for name, quantity in sealed.items()}
    for name, quantity in release.items():
        expected[str(name)] = expected.get(str(name), 0) + int(quantity)
    assert svc.candidate_inventory == expected
    assert len(release) == 83
    assert len(svc.candidates) >= 500


def test_wrong_commander_identity_fails_closed() -> None:
    svc = CommanderToolService(ROOT)
    baseline = svc._deck("korvold/current")
    altered = baseline.model_copy(
        update={"commander_names": ("Not Korvold",), "commander_base_costs": {"Not Korvold": 5.0}}
    )
    report = evaluate_constraints(altered, DEFAULT_CONSTRAINTS["korvold/current"])
    assert not report.valid
    assert any(issue.code == "commander_identity" for issue in report.issues)


def test_locked_cut_is_rejected_before_simulation() -> None:
    svc = CommanderToolService(ROOT)
    candidate = next(c for c in svc.candidates.values() if "korvold/current" in c.allowed_deck_ids)
    with pytest.raises(ToolExecutionError, match="locked"):
        svc._validate_swap_policy("korvold/current", "Dark Ritual", candidate.card)


def test_simultaneous_allocation_uses_free_copy_capacity() -> None:
    svc = CommanderToolService(ROOT)
    name = next(name for name, qty in svc.candidate_inventory.items() if qty >= 2)
    from commander_lab.optimization import evaluate_simultaneous_allocation

    assert evaluate_simultaneous_allocation(
        {"korvold/current": (name,), "rogshai/current": (name,)}, {name: 2}
    ).valid
    assert not evaluate_simultaneous_allocation(
        {"korvold/current": (name,), "rogshai/current": (name,)}, {name: 1}
    ).valid


def test_paired_randomization_and_holm_are_deterministic() -> None:
    diffs = (1, 1, 0, 1, -1, 1, 0, 1)
    p1 = paired_randomization_p_value(diffs, seed=11)
    p2 = paired_randomization_p_value(diffs, seed=11)
    assert p1 == p2
    adjusted = holm_adjust((p1, 0.04, 0.20))
    assert len(adjusted) == 3
    assert all(0 <= x <= 1 for x in adjusted)


def test_recommendation_trace_contains_required_fields_and_truth_boundary() -> None:
    trace = build_recommendation_trace(
        candidate_change=({"remove": "A", "add": "B"},),
        constraint_status={"valid": True},
        baseline_identity={"deck_hash": "base"},
        variant_identity={"deck_hash": "var"},
        paired_seeds=(1, 2, 3),
        affected_roles=("draw",),
        central_effect={"placement_improvement": 0.1},
        worst_case_effect=0.0,
        sensitivity={"pod": []},
        holdout_status="not_evaluated",
        recommendation_confidence_value="moderate_model_internal",
    )
    required = {
        "candidate_change",
        "constraint_status",
        "baseline_identity",
        "variant_identity",
        "paired_seed_set",
        "affected_roles",
        "central_effect",
        "worst_case_effect",
        "sensitivity",
        "holdout_status",
        "model_limitations",
        "recommendation_confidence",
    }
    assert required <= set(trace)
    assert trace["evidence_type"] == "structural_model_estimates"
    assert trace["llm_explanation_is_simulation_evidence"] is False
    assert paired_seed_set_identity((1, 2, 3))["count"] == 3


def test_challenge_set_is_constraint_safe_and_has_all_classes() -> None:
    svc = CommanderToolService(ROOT)
    payload = json.loads(
        (ROOT / "data/evals/golden/J_P5_OPTIMIZER_CHALLENGE_SET_v1.json").read_text()
    )
    assert {row["class"] for row in payload["variants"]} == {"good", "neutral", "bad"}
    for row in payload["variants"]:
        baseline = svc._deck(row["deck_id"])
        from commander_lab.optimization import build_search_candidate

        built = build_search_candidate(
            baseline,
            (VariantSwap(remove=row["remove"], add_candidate_id=row["add_candidate_id"]),),
            svc.candidates,
            svc._optimization_constraints(row["deck_id"]),
            inventory=svc.candidate_inventory,
            verified_physical_names=svc.verified_candidate_names,
        )
        assert built.constraint_report.valid
