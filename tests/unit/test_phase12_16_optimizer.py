from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

REQUIRED = {
    "build_optimization_context",
    "generate_candidate_swaps",
    "generate_candidate_packages",
    "optimize_deck_against_meta",
    "optimize_multiple_decks_with_allocation",
    "validate_swap",
    "validate_package_change",
    "validate_land_change",
    "validate_mulligan_policy",
    "run_multifidelity_comparison",
    "run_engine_backed_matchup",
    "run_robustness_suite",
    "run_rules_coverage_gate",
    "rank_variants",
    "explain_recommendation",
    "export_recommendation_evidence",
    "create_deck_improvement_report",
}
