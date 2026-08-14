from __future__ import annotations

from dataclasses import asdict
from typing import Any

from commander_lab.mana_analysis import ManaAnalyzer
from commander_lab.whole_deck.lab import WholeDeckDesignLab
from commander_lab.whole_deck.orchestrator import (
    WholeDeckCampaignOrchestrator,
    WholeDeckCampaignSpecification,
)
from commander_lab.workflow_session import WorkflowSession


def run_whole_deck(service: Any, request: Any) -> dict[str, Any]:
    with WorkflowSession.open(service.root, service=service) as session:
        lab = WholeDeckDesignLab(service.root)
        baseline = service._deck(request.deck_id)
        variant = lab.materialize_variant(
            request.prepared_design_path,
            request.whole_deck_variant_id,
        )
        unknown_cards = lab.semantic_unknown_cards_for_variant(
            request.prepared_design_path,
            request.whole_deck_variant_id,
        )
        orchestrator = WholeDeckCampaignOrchestrator(service.root)
        campaign_bundle = orchestrator.run_pair(
            baseline=baseline,
            variant=variant,
            specification=WholeDeckCampaignSpecification(
                primary_games=request.iterations,
                holdout_games=request.whole_deck_holdout_iterations,
                seed=request.seed,
                max_turns=request.max_turns,
                workers=request.workers,
            ),
        )
        primary = campaign_bundle["primary"]
        assert isinstance(primary, dict)
        campaign = primary["campaign"]
        assert isinstance(campaign, dict)
        mana = ManaAnalyzer(service.root)
        unknown_gate = {
            "status": "REVIEW_REQUIRED" if unknown_cards else "PASS",
            "semantic_unknown_cards": list(unknown_cards),
            "semantic_unknown_count": len(unknown_cards),
            "interpretation": (
                "Finalist contains fact-only cards without sufficient structural semantics; "
                "do not treat it as a high-confidence winner until reviewed."
                if unknown_cards
                else "All finalist cards have a usable structural representation in this snapshot."
            ),
        }
        return {
            "workflow": "deck_decision_run",
            "comparison_mode": "whole_deck",
            "evidence_class": "structural_model_estimates",
            "baseline_identity": {
                "deck_id": baseline.deck_id,
                "deck_hash": baseline.deck_hash,
            },
            "variant_identity": {
                "deck_id": variant.deck_id,
                "deck_hash": variant.deck_hash,
                "whole_deck_variant_id": request.whole_deck_variant_id,
            },
            "campaign_orchestration": campaign_bundle,
            # Backward-compatible primary aliases for existing diagnose/bundle consumers.
            "opponent_deck_ids": campaign_bundle["opponent_deck_ids"],
            "opponent_registry_hash": campaign_bundle["opponent_registry_hash"],
            "scenario_count": request.iterations,
            "scenarios": primary["scenarios"],
            "opponent_coverage_report": primary["coverage_report"],
            "balanced_campaign": campaign,
            "paired": campaign["paired"],
            "pair_count": len(campaign["paired_observations"]),
            "paired_observations": campaign["paired_observations"],
            "finalist_unknown_gate": unknown_gate,
            "mana_before": asdict(mana.analyze_deck(baseline)),
            "mana_after": asdict(mana.analyze_deck(variant)),
            "mana_delta": asdict(mana.compare_decks(baseline, variant)),
            "workflow_session": session.identity(),
            "execution_envelope": campaign_bundle["execution_envelope"],
            "official_structural_campaign_run": False,
            "campaign_scope": "single_finalist_balanced_4p_comparison",
            "evidence_boundaries": {
                "structural_model_estimates_are_empirical_winrates": False,
                "place_1_share_is_empirical_winrate": False,
                "search_prior_is_simulation_evidence": False,
                "tactical_oracle_is_external_rules_engine": False,
                "external_rules_engine": "NOT_RUN",
                "experimental_opponent_coverage_is_real_meta_frequency": False,
                "holdout_results_are_primary_results": False,
            },
            "automatic_deck_mutation": False,
        }
