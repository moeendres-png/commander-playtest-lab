from pathlib import Path

from commander_lab.models import ToolStatus, ValidateDeckInput
from commander_lab.tools import TOOL_DEFINITIONS, CommanderToolService, ToolRegistry

ROOT = Path(__file__).resolve().parents[2]


def test_all_required_tools_are_exposed() -> None:
    names = {definition.name for definition in TOOL_DEFINITIONS}
    assert names == {
        "validate_deck", "inspect_deck", "run_goldfish", "run_matchup_batch",
        "compare_decks", "compare_variants_paired", "run_card_ablation",
        "run_package_ablation", "run_commander_denial", "generate_swap_matrix",
        "search_variants", "run_local_search", "run_beam_search", "run_package_search",
        "evaluate_pareto_front", "estimate_shapley", "run_holdout", "run_sensitivity", "recommend_upgrades",
        "validate_upgrade", "ingest_playtest", "calibrate", "create_report",
        "import_meta_deck", "import_tournament_result", "import_primer_reference",
        "create_meta_snapshot", "query_meta_cards", "query_meta_packages",
        "compare_deck_to_meta", "compare_meta_periods", "generate_meta_report",
        "import_primer", "extract_primer_rules", "validate_pilot_rules",
        "compile_pilot_policy", "compare_policy_versions", "run_policy_eval",
        "generate_primer_conflict_report",
        "generate_pilot_robustness_report",
        "test_variant_across_pilots",
        "run_pilot_ensemble",
        "compare_pilots",
        "run_pilot_benchmark",
        "inspect_pilot",
        "list_pilot_profiles",
        "extract_archetypes", "extract_packages", "inspect_package",
        "compare_package_versions", "evaluate_package_density",
        "detect_orphaned_cards", "generate_package_report",
        "trace_artifact_provenance", "trace_recommendation_sources",
        "list_superseded_sources", "verify_source_hash",
        "generate_provenance_report", "audit_unreferenced_claims",
        "ingest_local_game", "update_local_opponent_profile", "inspect_local_meta",
        "compare_observed_to_assumed", "detect_local_meta_drift",
        "build_local_meta_scenarios", "generate_local_meta_report",
        "create_opponent_ensemble", "add_opponent_variant", "validate_ensemble",
        "run_ensemble_matchups", "compare_variant_sensitivity",
        "evaluate_robust_upgrade", "generate_ensemble_report",
        "sample_opening_hands", "evaluate_opening_hand",
        "compare_mulligan_policies", "run_mulligan_lab",
        "generate_keep_rules", "test_keep_rule", "create_mulligan_report",
        "find_counterfactual_branchpoints", "list_alternative_actions",
        "run_counterfactual", "compare_counterfactuals",
        "generate_decision_regret_report", "export_minimal_counterfactual_fixture",
    }


def test_schemas_are_strict_and_unique() -> None:
    registry = ToolRegistry(CommanderToolService(ROOT))
    schemas = registry.list_schemas()
    assert len(schemas) == 86
    assert len({schema["name"] for schema in schemas}) == 86
    assert all(schema["strict"] for schema in schemas)
    assert all(schema["parameters"]["type"] == "object" for schema in schemas)


def test_validate_deck_tool() -> None:
    service = CommanderToolService(ROOT)
    result = service.validate_deck(ValidateDeckInput(deck_id="korvold/current"))
    assert result.status == ToolStatus.COMPLETED
    assert result.result["validation"]["valid"] is True
    assert result.metadata.estimate_type == "structural_model_estimates"
