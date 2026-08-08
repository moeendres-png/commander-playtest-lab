from __future__ import annotations

from pathlib import Path

from commander_lab.models import (
    BuildOptimizationContextInput,
    GenerateCandidateSwapsInput,
    RunEngineBackedMatchupInput,
    RunRulesCoverageGateInput,
    RunRobustnessSuiteInput,
    ValidateSwapInput,
    VariantSwap,
)
from commander_lab.tools.registry import TOOL_DEFINITIONS, ToolRegistry
from commander_lab.tools.service import CommanderToolService

ROOT = Path(__file__).resolve().parents[2]

REQUIRED = {
    "build_optimization_context", "generate_candidate_swaps",
    "generate_candidate_packages", "optimize_deck_against_meta",
    "optimize_multiple_decks_with_allocation", "validate_swap",
    "validate_package_change", "validate_land_change",
    "validate_mulligan_policy", "run_multifidelity_comparison",
    "run_engine_backed_matchup", "run_robustness_suite",
    "run_rules_coverage_gate", "rank_variants",
    "explain_recommendation", "export_recommendation_evidence",
    "create_deck_improvement_report",
}


def service() -> CommanderToolService:
    return CommanderToolService(ROOT)


def test_high_level_tools_are_registered_with_unique_schemas() -> None:
    names = [definition.name for definition in TOOL_DEFINITIONS]
    assert REQUIRED <= set(names)
    assert len(names) == len(set(names)) == 100
    schemas = ToolRegistry(service()).list_schemas()
    assert len(schemas) == 100
    assert all(schema["strict"] for schema in schemas)


def test_optimization_context_is_read_only_and_truth_bounded() -> None:
    response = service().build_optimization_context(BuildOptimizationContextInput())
    assert response.status.value == "completed"
    assert response.result["validation_level"] == "structural_only"
    assert response.result["deck_priority"] == [
        "korvold/current", "rogshai/current", "kaervek/current"
    ]
    assert response.result["external_engine"]["execution_status"] == "blocked"
    assert response.result["automatic_application"] is False
    assert response.result["canonical_files_modified"] is False


def test_candidate_swaps_never_apply_changes() -> None:
    response = service().generate_candidate_swaps(
        GenerateCandidateSwapsInput(deck_id="korvold/current", max_candidates=2)
    )
    assert response.status.value == "completed"
    assert response.result["count"] == 2
    assert response.result["automatic_application"] is False
    assert {row["recommendation_status"] for row in response.result["candidates"]} == {"candidate_swap"}


def test_rules_coverage_cannot_claim_external_validation() -> None:
    response = service().run_rules_coverage_gate(
        RunRulesCoverageGateInput(deck_id="korvold/current", require_external=True)
    )
    assert response.status.value == "completed"
    assert response.result["external_gate_passed"] is False
    assert response.result["gate_status"] == "blocked"
    assert response.result["highest_validation_level"] in {"structural_only", "tactical_oracle"}


def test_engine_backed_matchup_returns_blocked_not_fake_success() -> None:
    response = service().run_engine_backed_matchup(
        RunEngineBackedMatchupInput(
            deck_ids=("korvold/current", "synthetic/aggro"), provider="xmage", iterations=1
        )
    )
    assert response.status.value == "completed"
    assert response.result["execution_status"] == "blocked"
    assert response.result["external_rules_engine_observations"] == 0
    assert response.result["synthetic_or_tactical_substitution"] is False


def test_candidate_universe_uses_current_read_only_inventory() -> None:
    svc = service()
    assert len(svc.candidates) >= 500
    assert len(svc.verified_candidate_names) == len(svc.candidates)
    inferred = [c for c in svc.candidates.values() if c.candidate_id.startswith("inventory/")]
    assert inferred
    assert all(c.card.source_quality.value == "project_inferred" for c in inferred)
    assert all(svc.candidate_inventory[c.card.oracle_name] > 0 for c in svc.candidates.values())


def test_validate_swap_executes_politics_pod_tactical_and_external_truth_gates() -> None:
    svc = service()
    response = svc.validate_swap(ValidateSwapInput(
        deck_id="korvold/current",
        swaps=(VariantSwap(remove="Vampiric Rites", add_candidate_id="korvold/mazirek-smoke"),),
        iterations=1, workers=1, seed=123, max_turns=8,
        holdout_pods=(), sensitivity_seeds=(), sensitivity_strengths=(),
    ))
    assert response.status.value == "completed"
    assert len(response.result["politics_sensitivity"]) == 10
    assert {row["pod_size"] for row in response.result["pod_size_sensitivity"]} == {3, 4, 5}
    assert response.result["tactical_oracle_result"]["execution_status"] == "passed"
    assert response.result["tactical_oracle_result"]["external_engine_claimed"] is False
    assert response.result["xmage_result"]["execution_status"] == "blocked"
    assert response.result["forge_result"]["execution_status"] == "blocked"


def test_robustness_suite_runs_structural_scenarios_instead_of_reading_old_artifact() -> None:
    svc = service()
    response = svc.run_robustness_suite(RunRobustnessSuiteInput(
        deck_id="korvold/current",
        swaps=(VariantSwap(remove="Vampiric Rites", add_candidate_id="korvold/mazirek-smoke"),),
        iterations=1, workers=1, seed=456, max_turns=8,
        holdout_pods=(), sensitivity_seeds=(), sensitivity_strengths=(),
        include_politics=True, include_pod_sizes=(3,),
    ))
    assert response.status.value == "completed"
    assert response.result["execution_status"] == "passed"
    assert response.result["scenario_count"] == 10
    assert all(row["pod_size"] == 3 for row in response.result["scenario_results"])
    assert response.result["automatic_application"] is False
