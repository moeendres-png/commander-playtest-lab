from __future__ import annotations

import json
from pathlib import Path

from commander_lab.models import (
    CreateReportInput,
    MatchupBatchInput,
    PairedVariantInput,
    RecommendUpgradesInput,
    ValidateDeckInput,
    ValidateUpgradeInput,
    VariantSwap,
)
from commander_lab.tools import CommanderToolService


def run_phase5_demo(root: str | Path, *, iterations: int = 80, seed: int = 20260804) -> dict[str, object]:
    service = CommanderToolService(root)
    validation = service.validate_deck(ValidateDeckInput(deck_id="korvold/current"))
    matchup = service.run_matchup_batch(
        MatchupBatchInput(
            deck_ids=("korvold/current", "synthetic/aggro", "synthetic/control", "synthetic/engine"),
            iterations=iterations,
            seed=seed,
            workers=1,
        )
    )
    recommendations = service.recommend_upgrades(
        RecommendUpgradesInput(
            deck_id="korvold/current",
            candidate_ids=("korvold/mazirek-smoke",),
            max_recommendations=1,
        )
    )
    top = recommendations.result["recommendations"][0]
    swap = VariantSwap(remove=top["remove"], add_candidate_id=top["candidate_id"])
    paired = service.compare_variants_paired(
        PairedVariantInput(
            deck_id="korvold/current",
            swaps=(swap,),
            iterations=iterations,
            seed=seed,
            workers=1,
        )
    )
    validation_result = service.validate_upgrade(
        ValidateUpgradeInput(
            deck_id="korvold/current",
            swaps=(swap,),
            iterations=iterations,
            seed=seed,
            workers=1,
            minimum_place_delta=0.0,
            require_holdout=True,
        )
    )
    report = service.create_report(
        CreateReportInput(
            title="Phase 5 End-to-End Demo — Korvold",
            output_name="phase5_demo_report.md",
            tool_responses=(
                validation.model_dump(mode="json"),
                matchup.model_dump(mode="json"),
                recommendations.model_dump(mode="json"),
                paired.model_dump(mode="json"),
                validation_result.model_dump(mode="json"),
            ),
        )
    )
    payload = {
        "estimate_type": "structural_model_estimates",
        "deck_imported": "korvold/current",
        "validation": validation.model_dump(mode="json"),
        "matchup": matchup.model_dump(mode="json"),
        "candidate_screening": recommendations.model_dump(mode="json"),
        "paired_test": paired.model_dump(mode="json"),
        "upgrade_validation": validation_result.model_dump(mode="json"),
        "report": report.model_dump(mode="json"),
    }
    output = Path(root) / "PHASE5_DEMO_OUTPUT.json"
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return payload
