from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from statistics import fmean, stdev
from typing import Any

from commander_lab.models import ObjectiveVector, StructuralDeckProfile

from .search import profile_closing_score, profile_rebuild_score

MODEL_LIMITATIONS = (
    "structural_model_estimates only; not empirical Commander winrates",
    "paired uncertainty reflects Monte Carlo uncertainty inside the configured simulator",
    "opponent/pilot assumptions are model inputs and no opponent-frequency weights are inferred",
    "Tactical Oracle is not an external rules engine",
)


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _numeric_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, (str, bytes, bytearray, int, float)):
        return float(value)
    return default


def _numeric_int(value: object, default: int = 0) -> int:
    if isinstance(value, (str, bytes, bytearray, int)):
        return int(value)
    return default


def normalized_placement_effect(value: float, pod_size: int) -> float:
    return _clamp(value / max(1, pod_size - 1))


def seat_robustness(pairs: Sequence[Mapping[str, object]]) -> float:
    by_seat: dict[int, list[float]] = defaultdict(list)
    for row in pairs:
        seat = _numeric_int(row.get("starting_player_seat", 0))
        delta = _numeric_float(row.get("baseline_placement", 0)) - _numeric_float(
            row.get("variant_placement", 0)
        )
        by_seat[seat].append(delta)
    return min((fmean(values) for values in by_seat.values()), default=0.0)


def scenario_heterogeneity(effects: Iterable[float]) -> dict[str, float]:
    values = tuple(float(value) for value in effects)
    if not values:
        return {
            "scenario_count": 0.0,
            "mean": 0.0,
            "standard_deviation": 0.0,
            "minimum": 0.0,
            "maximum": 0.0,
        }
    return {
        "scenario_count": float(len(values)),
        "mean": fmean(values),
        "standard_deviation": stdev(values) if len(values) > 1 else 0.0,
        "minimum": min(values),
        "maximum": max(values),
    }


def build_robust_objective(
    *,
    baseline: StructuralDeckProfile,
    variant: StructuralDeckProfile,
    central_effect: float,
    worst_quartile_effect: float,
    pair_rows: Sequence[Mapping[str, object]],
    commander_dependency_baseline: float,
    commander_dependency_variant: float,
    matchup_effects: Sequence[float],
    pod_effects: Sequence[tuple[int, float]],
    opponent_uncertainty_effects: Sequence[float],
    physical_allocation_valid: bool,
) -> ObjectiveVector:
    pod_size = _numeric_int(pair_rows[0].get("pod_size", 4), 4) if pair_rows else 4
    matchup_worst = min(matchup_effects, default=central_effect)
    pod_worst = min(
        (normalized_placement_effect(effect, size) for size, effect in pod_effects),
        default=normalized_placement_effect(central_effect, pod_size),
    )
    opponent_worst = min(opponent_uncertainty_effects, default=matchup_worst)
    return ObjectiveVector(
        central_performance=normalized_placement_effect(central_effect, pod_size),
        worst_quartile=normalized_placement_effect(worst_quartile_effect, pod_size),
        commander_independence=_clamp(commander_dependency_baseline - commander_dependency_variant),
        rebuild=_clamp(profile_rebuild_score(variant) - profile_rebuild_score(baseline)),
        finish_reliability=_clamp(profile_closing_score(variant) - profile_closing_score(baseline)),
        matchup_robustness=normalized_placement_effect(matchup_worst, pod_size),
        pod_size_robustness=pod_worst,
        seat_robustness=normalized_placement_effect(seat_robustness(pair_rows), pod_size),
        opponent_uncertainty=normalized_placement_effect(opponent_worst, pod_size),
        physical_allocation=1.0 if physical_allocation_valid else -1.0,
    )


def paired_seed_set_identity(seeds: Sequence[int]) -> dict[str, Any]:
    payload = ",".join(str(seed) for seed in seeds).encode("utf-8")
    return {
        "count": len(seeds),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "seeds": list(seeds),
    }


def recommendation_confidence(
    *,
    constraint_valid: bool,
    adjusted_p_value: float | None,
    worst_case_effect: float,
    holdout_status: str,
) -> str:
    if not constraint_valid:
        return "rejected_constraints"
    if (
        holdout_status == "passed_first_evaluation"
        and worst_case_effect >= 0
        and adjusted_p_value is not None
        and adjusted_p_value <= 0.05
    ):
        return "high_model_internal"
    if worst_case_effect >= 0:
        return "moderate_model_internal"
    return "low_model_internal"


def build_recommendation_trace(
    *,
    candidate_change: Sequence[Mapping[str, object]],
    constraint_status: Mapping[str, object],
    baseline_identity: Mapping[str, object],
    variant_identity: Mapping[str, object],
    paired_seeds: Sequence[int],
    affected_roles: Sequence[str],
    central_effect: Mapping[str, object],
    worst_case_effect: float,
    sensitivity: Mapping[str, object],
    holdout_status: str,
    recommendation_confidence_value: str,
) -> dict[str, object]:
    return {
        "candidate_change": list(candidate_change),
        "constraint_status": dict(constraint_status),
        "baseline_identity": dict(baseline_identity),
        "variant_identity": dict(variant_identity),
        "paired_seed_set": paired_seed_set_identity(tuple(int(seed) for seed in paired_seeds)),
        "affected_roles": list(affected_roles),
        "central_effect": dict(central_effect),
        "worst_case_effect": float(worst_case_effect),
        "sensitivity": dict(sensitivity),
        "holdout_status": holdout_status,
        "model_limitations": list(MODEL_LIMITATIONS),
        "recommendation_confidence": recommendation_confidence_value,
        "evidence_type": "structural_model_estimates",
        "llm_explanation_is_simulation_evidence": False,
        "automatic_application": False,
    }
