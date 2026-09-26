from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass

from commander_lab.storage.run_identity import sha256_run_value


@dataclass(frozen=True)
class ConservativeAdaptiveBudgetPlan:
    """Quality-first budget plan that never eliminates on noisy early means.

    Static elimination is allowed only for candidates already classified as clearly
    deprioritized by the deterministic screen. Surviving candidates retain the full paired
    budget; later per-comparison continuation is controlled by DecisionInformationState.
    """

    schema_version: str
    full_budget_per_candidate: int
    candidate_ids: tuple[str, ...]
    retained_candidate_ids: tuple[str, ...]
    eliminated_candidate_ids: tuple[str, ...]
    full_control_paired_comparisons: int
    planned_paired_comparisons: int
    simulation_reduction: float
    elimination_rule: str = "deterministic_static_deprioritize_only"
    noisy_early_elimination_allowed: bool = False

    @property
    def plan_hash(self) -> str:
        return sha256_run_value(asdict(self))

    def as_dict(self) -> dict[str, object]:
        return {"plan_hash": self.plan_hash, **asdict(self)}


def build_conservative_adaptive_budget_plan(
    screen_buckets: Mapping[str, str],
    *,
    full_budget_per_candidate: int,
) -> ConservativeAdaptiveBudgetPlan:
    if full_budget_per_candidate < 1:
        raise ValueError("full_budget_per_candidate must be positive")
    ids = tuple(sorted(str(candidate_id) for candidate_id in screen_buckets))
    eliminated = tuple(
        candidate_id
        for candidate_id in ids
        if screen_buckets[candidate_id] == "deprioritize_static"
    )
    retained = tuple(candidate_id for candidate_id in ids if candidate_id not in eliminated)
    full = len(ids) * full_budget_per_candidate
    planned = len(retained) * full_budget_per_candidate
    reduction = 1.0 - planned / full if full else 0.0
    return ConservativeAdaptiveBudgetPlan(
        schema_version="1.0.0",
        full_budget_per_candidate=full_budget_per_candidate,
        candidate_ids=ids,
        retained_candidate_ids=retained,
        eliminated_candidate_ids=eliminated,
        full_control_paired_comparisons=full,
        planned_paired_comparisons=planned,
        simulation_reduction=reduction,
    )


def challenge_quality_metrics(
    plan: ConservativeAdaptiveBudgetPlan,
    labels: Mapping[str, str],
) -> dict[str, object]:
    material_finalists = {candidate_id for candidate_id, label in labels.items() if label == "good"}
    retained = set(plan.retained_candidate_ids)
    recovered = material_finalists & retained
    eliminated_material = material_finalists - retained
    recall = len(recovered) / len(material_finalists) if material_finalists else 1.0
    false_elimination = (
        len(eliminated_material) / len(material_finalists) if material_finalists else 0.0
    )
    return {
        "material_finalist_count": len(material_finalists),
        "material_finalist_recall": recall,
        "false_elimination_rate_of_material_finalists": false_elimination,
        "eliminated_material_finalist_ids": tuple(sorted(eliminated_material)),
        "quality_gate_pass": recall == 1.0 and false_elimination == 0.0,
        "truth_boundary": "frozen structural challenge labels, not empirical card-quality truth",
    }


__all__ = [
    "ConservativeAdaptiveBudgetPlan",
    "build_conservative_adaptive_budget_plan",
    "challenge_quality_metrics",
]
