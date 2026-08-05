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
    }


def test_schemas_are_strict_and_unique() -> None:
    registry = ToolRegistry(CommanderToolService(ROOT))
    schemas = registry.list_schemas()
    assert len(schemas) == 32
    assert len({schema["name"] for schema in schemas}) == 32
    assert all(schema["strict"] for schema in schemas)
    assert all(schema["parameters"]["type"] == "object" for schema in schemas)


def test_validate_deck_tool() -> None:
    service = CommanderToolService(ROOT)
    result = service.validate_deck(ValidateDeckInput(deck_id="korvold/current"))
    assert result.status == ToolStatus.COMPLETED
    assert result.result["validation"]["valid"] is True
    assert result.metadata.estimate_type == "structural_model_estimates"
