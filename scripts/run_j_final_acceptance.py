from __future__ import annotations

import json
from pathlib import Path

from commander_lab import __version__
from commander_lab.engine.structural import ENGINE_VERSION
from commander_lab.fresh_rebuild import load_fresh_rebuild_runtime, load_fresh_rogshai_universe
from commander_lab.models import (
    CardAblationInput,
    CommanderDenialInput,
    PackageAblationInput,
    PilotStrength,
    SearchVariantsInput,
    SensitivityInput,
)
from commander_lab.priority_workflows import PriorityWorkflowFacade
from commander_lab.project_context import load_project_context
from commander_lab.tools.service import CommanderToolService

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/j-final/J_FINAL_EXECUTED_EVIDENCE.json"
DECK_ID = "rogshai/current"
SEED = 20260811


def response_payload(response: object) -> dict[str, object]:
    return response.model_dump(mode="json")  # type: ignore[attr-defined,no-any-return]


def main() -> int:
    context = load_project_context(ROOT)
    service = CommanderToolService(ROOT)
    fresh = load_fresh_rogshai_universe(ROOT)
    runtime = load_fresh_rebuild_runtime(ROOT)
    facade = PriorityWorkflowFacade(ROOT)
    opponents = context.primary_opponent_deck_ids(DECK_ID)

    build_screen = facade.build_screen(DECK_ID, limit=795)
    if build_screen["candidate_recall"] != 1.0:
        raise RuntimeError("J-FINAL candidate recall is not complete")
    if build_screen["discoverable_candidate_count"] != 795:
        raise RuntimeError("J-FINAL candidate universe is not 795/795 discoverable")

    mana_mulligan = facade.mulligan_mana(DECK_ID)
    controlled_variant = facade.compare_validate(
        deck_id=DECK_ID,
        remove="Flare of Duplication",
        add_candidate_id="inventory/rootborn-defenses-677fdbcf",
        iterations=2,
        seed=SEED,
        max_turns=12,
    )
    if controlled_variant.get("status") != "completed":
        raise RuntimeError(f"controlled J-FINAL variant did not complete: {controlled_variant}")

    denial = service.run_commander_denial(
        CommanderDenialInput(
            deck_id=DECK_ID,
            opponent_deck_ids=opponents,
            iterations=2,
            seed=SEED,
            max_turns=12,
        )
    )
    card_ablation = service.run_card_ablation(
        CardAblationInput(
            deck_id=DECK_ID,
            card_name="Flare of Duplication",
            opponent_deck_ids=opponents,
            iterations=2,
            seed=SEED,
            max_turns=12,
        )
    )
    package_ablation = service.run_package_ablation(
        PackageAblationInput(
            deck_id=DECK_ID,
            card_names=("Flare of Duplication",),
            opponent_deck_ids=opponents,
            iterations=1,
            seed=SEED,
            max_turns=12,
        )
    )
    sensitivity = service.run_sensitivity(
        SensitivityInput(
            deck_ids=(DECK_ID, *opponents),
            iterations=1,
            seeds=(SEED,),
            pilot_strengths=(PilotStrength.STRONG,),
            seed=SEED,
            max_turns=12,
        )
    )
    bounded_search = service.search_variants(
        SearchVariantsInput(
            deck_id=DECK_ID,
            candidate_ids=("inventory/rootborn-defenses-677fdbcf",),
            opponent_deck_ids=opponents,
            max_cuts=1,
            max_results=1,
            iterations=1,
            seed=SEED,
            max_turns=12,
        )
    )

    diagnosis = facade.diagnose_next_experiment(controlled_variant)
    bundle_paths = facade.create_decision_bundle(
        controlled_variant,
        ROOT / "artifacts/j-final/decision-bundle",
        worst_case_sensitivity_result=sensitivity.result,
        commander_denial_result=denial.result,
        ablation_result=card_ablation.result,
        recommendation_status="structural_evidence_only",
    )

    coverage = runtime["candidate_universe"]["coverage_counts"]
    evidence = {
        "schema_version": "1.0",
        "evidence_class": "structural_model_estimates",
        "truth_boundaries": {
            "structural_model_estimates_are_empirical_winrate": False,
            "tactical_oracle_is_external_rules_engine": False,
            "model_decision_quality_is_real_game_proof": False,
            "historical_deck_membership_is_card_quality_prior": False,
            "inactive_korvold_allocation_blocks_rogshai": False,
        },
        "software": {
            "package_version": __version__,
            "engine_version": ENGINE_VERSION,
            "context_snapshot_hash": context.snapshot_hash,
        },
        "scope": {
            "active_own_decks": list(context.active_own_deck_ids),
            "historical_own_decks": list(context.historical_own_deck_ids),
            "frozen_opponent_only": sorted(service.FROZEN_OPPONENT_ONLY_DECK_IDS),
        },
        "candidate_universe": {
            "legal_physical": fresh.candidate_count,
            "discoverable": build_screen["discoverable_candidate_count"],
            "candidate_recall": build_screen["candidate_recall"],
            "fully_high_confidence_modeled": coverage["STRUCTURALLY_MODELED"],
            "partially_modeled": coverage["PARTIALLY_MODELED"],
            "structurally_unmodeled": coverage["STRUCTURALLY_UNMODELED"],
            "review_required_before_model_dependent_scoring": fresh.review_required_count,
            "lightning_greaves_available_to_rogshai": fresh.available_quantities[
                "Lightning Greaves"
            ],
        },
        "build_screen": build_screen,
        "mana_mulligan": mana_mulligan,
        "controlled_variant": controlled_variant,
        "commander_denial": response_payload(denial),
        "card_ablation": response_payload(card_ablation),
        "package_ablation": response_payload(package_ablation),
        "sensitivity": response_payload(sensitivity),
        "bounded_search": response_payload(bounded_search),
        "diagnosis": diagnosis,
        "decision_bundle": bundle_paths,
        "holdout_governance": {
            "J_HOLDOUT_v1": "CONSUMED_HISTORICAL_EVIDENCE_NOT_REUSED",
            "fresh_blind_holdout_claimed": False,
        },
        "canonical_files_modified": False,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS",
        "candidate_recall": build_screen["candidate_recall"],
        "context_snapshot_hash": context.snapshot_hash,
        "decision_bundle": bundle_paths,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
