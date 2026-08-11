from pathlib import Path

from commander_lab.models import (
    GoldfishInput,
    PairedVariantInput,
    RecommendUpgradesInput,
    ToolStatus,
    VariantSwap,
)
from commander_lab.tools import CommanderToolService

ROOT = Path(__file__).resolve().parents[2]


def test_large_run_requires_approval() -> None:
    service = CommanderToolService(ROOT)
    result = service.run_goldfish(GoldfishInput(deck_id="korvold/current", iterations=5001))
    assert result.status == ToolStatus.REQUIRES_APPROVAL


def test_recommendation_is_screening_not_confirmation() -> None:
    service = CommanderToolService(ROOT)
    result = service.recommend_upgrades(
        RecommendUpgradesInput(
            deck_id="rogshai/current",
            candidate_ids=("inventory/rootborn-defenses-677fdbcf",),
            max_recommendations=2,
        )
    )
    assert result.status == ToolStatus.COMPLETED
    assert result.result["method"] == "role_profile_screening_only"
    assert all(row["requires_paired_validation"] for row in result.result["recommendations"])


def test_paired_variant_tool_runs() -> None:
    service = CommanderToolService(ROOT)
    result = service.compare_variants_paired(
        PairedVariantInput(
            deck_id="rogshai/current",
            swaps=(
                VariantSwap(
                    remove="Flare of Duplication",
                    add_candidate_id="inventory/rootborn-defenses-677fdbcf",
                ),
            ),
            iterations=4,
            seed=7,
        )
    )
    assert result.status == ToolStatus.COMPLETED
    assert result.result["comparison"]["games"] == 4
