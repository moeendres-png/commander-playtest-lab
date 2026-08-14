from __future__ import annotations

from typing import Any
from commander_lab.models import PilotDecisionMode, PilotStrength
from commander_lab.whole_deck.lab import WholeDeckDesignLab
from commander_lab.workflow_session import WorkflowSession


def run_whole_deck(service: Any, request: Any) -> dict[str, Any]:
    with WorkflowSession.open(service.root, service=service) as session:
        lab = WholeDeckDesignLab(service.root)
        baseline = service._deck(request.deck_id)
        variant = lab.materialize_variant(request.prepared_design_path, request.whole_deck_variant_id)
        opponent_ids = tuple(session.context.primary_opponent_deck_ids(request.deck_id))
        metrics, observations = service._paired_variant_metrics(
            baseline=baseline,
            variant=variant,
            opponent_deck_ids=opponent_ids,
            iterations=request.iterations,
            seed=request.seed,
            pilot_strength=PilotStrength.STRONG,
            pilot_mode=PilotDecisionMode.DETERMINISTIC,
            max_turns=request.max_turns,
            pair_id=f"whole-deck-{variant.deck_hash[:12]}",
            workers=1,
        )
        return {
            "workflow": "deck_decision_run",
            "comparison_mode": "whole_deck",
            "evidence_class": "structural_model_estimates",
            "baseline_identity": {"deck_id": baseline.deck_id, "deck_hash": baseline.deck_hash},
            "variant_identity": {"deck_id": variant.deck_id, "deck_hash": variant.deck_hash, "whole_deck_variant_id": request.whole_deck_variant_id},
            "opponent_deck_ids": opponent_ids,
            "paired": metrics.as_dict(),
            "pair_count": len(observations),
            "paired_observations": observations,
            "mana_before": service.mana.analyze_deck(baseline).__dict__,
            "mana_after": service.mana.analyze_deck(variant).__dict__,
            "mana_delta": service.mana.compare_decks(baseline, variant).__dict__,
            "workflow_session": session.identity(),
            "execution_envelope": {"requested_workers": request.workers, "effective_workers": 1, "worker_fallback_applied": request.workers != 1},
            "evidence_boundaries": {"structural_model_estimates_are_empirical_winrates": False, "search_prior_is_simulation_evidence": False, "tactical_oracle_is_external_rules_engine": False, "external_rules_engine": "NOT_RUN"},
            "automatic_deck_mutation": False,
        }
