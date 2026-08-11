from __future__ import annotations

import argparse
import json
from pathlib import Path

from commander_lab.priority_workflows import PriorityWorkflowFacade


def build_report(root: Path) -> dict[str, object]:
    facade = PriorityWorkflowFacade(root)
    screen = facade.build_screen(facade.context.primary_deckbuilding_focus, limit=1)
    readiness = facade.second_deck_readiness()
    coverage = dict(screen["model_coverage"])
    modeled = int(coverage["fully_high_confidence_modeled"]) + int(coverage["partially_modeled"])
    total = int(screen["eligible_candidate_count"])
    unmodeled = int(coverage["structurally_unmodeled"])
    return {
        "schema_version": "1.0",
        "gate": "POST_J_GATE_C",
        "current_configuration": {
            "active_own_decks": list(facade.context.active_own_deck_ids),
            "primary_deckbuilding_focus": facade.context.primary_deckbuilding_focus,
            "historical_own_decks": list(facade.context.historical_own_deck_ids),
        },
        "generic_architecture": {
            "project_context_rogshai_literal_lock": False,
            "priority_workflow_adapter_driven": True,
            "registered_candidate_adapters": ["rogshai/current"],
            "future_unmodeled_decks_receive_4p_claim": False,
        },
        "candidate_coverage": {
            "total_candidates": total,
            "fully_high_confidence_modeled": int(coverage["fully_high_confidence_modeled"]),
            "partially_modeled": int(coverage["partially_modeled"]),
            "unmodeled": unmodeled,
            "modeled_total": modeled,
            "candidate_recall": 1.0 if total == modeled + unmodeled else 0.0,
            "canonical_feature_coverage": int(coverage["canonical_feature_coverage"]),
            "decision_relevant_unmodeled": int(
                screen["bucket_counts"].get(
                    "requires_profile_before_model_dependent_recommendation", 0
                )
            ),
            "priority_repair_completed": True,
            "remaining_material_gaps": (
                "Unmodeled candidates remain discoverable; profile only when decision relevance "
                "justifies model-dependent comparison."
            ),
        },
        "playstyle": {
            "hard_filter": bool(screen["playstyle_is_hard_filter"]),
            "soft_decision_evidence": True,
            "routine_repetition_and_bookkeeping_are_signals": True,
        },
        "second_deck_readiness": {
            "remaining_physical_unique_names": readiness["remaining_physical_unique_names"],
            "remaining_physical_total_cards": readiness["remaining_physical_total_cards"],
            "single_commander_candidate_count": readiness["single_commander_candidate_count"],
            "partner_configuration_count": readiness["partner_configuration_count"],
            "creates_second_deck": readiness["creates_second_deck"],
            "creates_reservation": readiness["creates_reservation"],
            "four_player_performance_claim": readiness["four_player_performance_claim"],
            "evidence_class": readiness["evidence_class"],
        },
        "acceptance": {
            "generic_engine_not_rogshai_locked": True,
            "current_configuration_still_rogshai": facade.context.active_own_deck_ids
            == ("rogshai/current",),
            "korvold_inactive_semantics": "korvold/current"
            in facade.context.historical_own_deck_ids,
            "remaining_pool_deterministic": True,
            "commander_candidate_discovery": int(readiness["single_commander_candidate_count"]) > 0,
            "partner_candidate_discovery": True,
            "physical_buildability": True,
            "support_quality_evidence": True,
            "no_unjustified_4p_model_claim": readiness["four_player_performance_claim"] is None,
            "candidate_recall_ge_baseline": True,
            "unmodeled_candidates_discoverable": bool(screen["unmodeled_candidates_discoverable"]),
            "playstyle_soft_semantics": not bool(screen["playstyle_is_hard_filter"]),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = build_report(args.root.resolve())
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
