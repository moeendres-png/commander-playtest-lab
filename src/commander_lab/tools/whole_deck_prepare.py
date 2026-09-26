from __future__ import annotations

from typing import Any

from commander_lab.models import ValidateDeckInput
from commander_lab.whole_deck.lab import WholeDeckDesignLab


def prepare_whole_deck(service: Any, request: Any) -> dict[str, Any]:
    if request.deck_id != "rogshai/current":
        raise ValueError("Whole-Deck Design Lab is scoped to current RogShai")
    validation = service._validate_deck_payload(
        ValidateDeckInput(deck_id=request.deck_id, include_physical_allocation=True)
    )
    prepared = WholeDeckDesignLab(service.root).prepare(
        policies=request.whole_deck_policies,
        seed=request.design_seed,
        diversified_starts=request.whole_deck_diversified_starts,
        steps_per_start=request.whole_deck_steps_per_start,
        finalists_per_policy=request.whole_deck_finalists_per_policy,
        max_variants=request.whole_deck_max_variants,
        output_name=request.whole_deck_output_name,
    )
    return {
        "workflow": "deck_decision_prepare",
        "design_mode": "whole_deck",
        "deck_id": request.deck_id,
        "validation": validation,
        "candidate_count": prepared["candidate_count"],
        "data_snapshot_hash": prepared["data_snapshot_hash"],
        "enrichment_snapshot_hash": prepared["enrichment_snapshot_hash"],
        "prepared_design_path": prepared["prepared_design_path"],
        "design_campaign_id": prepared["design_campaign_id"],
        "policies": prepared["policies"],
        "discoverability": prepared["discoverability"],
        "variants": prepared["variants"],
        "mulligan_contract": prepared["mulligan_contract"],
        "official_structural_campaign_run": False,
        "next_call": "deck_decision_run",
        "automatic_deck_mutation": False,
        "evidence_boundaries": prepared["evidence_boundaries"],
    }
