from __future__ import annotations

import json
from pathlib import Path

from commander_lab.decision_statistics import holm_adjust, paired_randomization_p_value
from commander_lab.models import ObjectiveVector
from commander_lab.optimization import DEFAULT_CONSTRAINTS, evaluate_constraints
from commander_lab.optimization.jp5 import build_recommendation_trace, paired_seed_set_identity
from commander_lab.tools.service import CommanderToolService

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
    assert len(svc.candidates) >= 300
    assert {deck_id for c in svc.candidates.values() for deck_id in c.allowed_deck_ids} == {
        "rogshai/current"
    }


def test_wrong_commander_identity_fails_closed() -> None:
    svc = CommanderToolService(ROOT)
    baseline = svc._deck("rogshai/current")
    altered = baseline.model_copy(
        update={
            "commander_names": ("Not Ishai", "Not Rograkh"),
            "commander_base_costs": {"Not Ishai": 4.0, "Not Rograkh": 0.0},
        }
    )
    report = evaluate_constraints(altered, DEFAULT_CONSTRAINTS["rogshai/current"])
    assert not report.valid
    assert any(issue.code == "commander_identity" for issue in report.issues)


def test_inactive_korvold_does_not_create_a_current_locked_cut() -> None:
    protected = json.loads((ROOT / "config/protected_cards.json").read_text(encoding="utf-8"))
    assert protected.get("protected_cards", {}) in ({}, [])
    svc = CommanderToolService(ROOT)
    candidate = next(c for c in svc.candidates.values() if "rogshai/current" in c.allowed_deck_ids)
    svc._validate_swap_policy("rogshai/current", "Kykar, Wind's Fury", candidate.card)


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


def test_current_challenge_set_preserves_classes_and_truth_boundary() -> None:
    payload = json.loads(
        (ROOT / "data/evals/golden/J_P5_OPTIMIZER_CHALLENGE_SET_v1.json").read_text()
    )
    assert {row["class"] for row in payload["variants"]} == {"good", "neutral", "bad"}
    assert payload["evidence_boundary"] == "structural_model_estimates"
    assert payload["canonical_mutation_allowed"] is False
    assert {row["deck_id"] for row in payload["variants"]} == {"rogshai/current"}
