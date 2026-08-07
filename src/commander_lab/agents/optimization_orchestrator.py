from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Iterable


class RunProfile(StrEnum):
    QUICK_SCREEN = "quick_screen"
    STANDARD_VALIDATION = "standard_validation"
    DEEP_VALIDATION = "deep_validation"
    EXTERNAL_ENGINE_VALIDATION = "external_engine_validation"
    FULL_OPTIMIZATION = "full_optimization"


@dataclass(frozen=True, slots=True)
class OptimizationPlan:
    profile: RunProfile
    tools: tuple[str, ...]
    requires_external_engine: bool
    applies_changes: bool = False


PROFILE_TOOLS: dict[RunProfile, tuple[str, ...]] = {
    RunProfile.QUICK_SCREEN: (
        "build_optimization_context", "validate_deck", "inspect_deck",
        "generate_candidate_swaps", "rank_variants", "explain_recommendation",
    ),
    RunProfile.STANDARD_VALIDATION: (
        "build_optimization_context", "generate_candidate_swaps", "validate_swap",
        "run_holdout", "run_sensitivity", "run_rules_coverage_gate",
        "run_robustness_suite", "explain_recommendation",
    ),
    RunProfile.DEEP_VALIDATION: (
        "build_optimization_context", "generate_candidate_swaps",
        "generate_candidate_packages", "optimize_deck_against_meta",
        "run_commander_denial", "run_counterfactual", "run_robustness_suite",
        "run_rules_coverage_gate", "rank_variants", "explain_recommendation",
    ),
    RunProfile.EXTERNAL_ENGINE_VALIDATION: (
        "build_optimization_context", "run_rules_coverage_gate",
        "run_engine_backed_matchup", "run_multifidelity_comparison",
        "explain_recommendation",
    ),
    RunProfile.FULL_OPTIMIZATION: (
        "build_optimization_context", "generate_candidate_swaps",
        "generate_candidate_packages", "optimize_multiple_decks_with_allocation",
        "optimize_deck_against_meta", "run_robustness_suite",
        "run_multifidelity_comparison", "rank_variants",
        "export_recommendation_evidence", "create_deck_improvement_report",
    ),
}


def select_run_profile(user_goal: str) -> RunProfile:
    normalized = user_goal.casefold()
    if any(token in normalized for token in ("xmage", "forge", "external engine", "regelengine")):
        return RunProfile.EXTERNAL_ENGINE_VALIDATION
    if any(token in normalized for token in ("vollständig optim", "full optimization", "gleichzeitig", "allokation")):
        return RunProfile.FULL_OPTIMIZATION
    if any(token in normalized for token in ("warum", "diagnos", "paket", "deep", "ausführlich")):
        return RunProfile.DEEP_VALIDATION
    if any(token in normalized for token in ("schnell", "quick", "screen")):
        return RunProfile.QUICK_SCREEN
    return RunProfile.STANDARD_VALIDATION


def build_optimization_plan(user_goal: str, *, available_tools: Iterable[str]) -> OptimizationPlan:
    profile = select_run_profile(user_goal)
    available = set(available_tools)
    tools = tuple(tool for tool in PROFILE_TOOLS[profile] if tool in available)
    return OptimizationPlan(
        profile=profile,
        tools=tools,
        requires_external_engine=profile == RunProfile.EXTERNAL_ENGINE_VALIDATION,
        applies_changes=False,
    )
