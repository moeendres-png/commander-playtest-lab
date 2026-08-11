from __future__ import annotations

import json
from pathlib import Path

from commander_lab.models import (
    BuildOptimizationContextInput,
    GenerateCandidateSwapsInput,
    OptimizeMultipleDecksWithAllocationInput,
    RunRulesCoverageGateInput,
)
from commander_lab.tools.service import CommanderToolService

ALLOWED_EVIDENCE_KINDS = {
    "verified_full_deck",
    "official_precon",
    "directly_observed",
    "reported",
    "partially_observed",
    "inferred",
    "synthetic_completion",
    "unknown",
}


def _service(repo_root: Path) -> CommanderToolService:
    return CommanderToolService(repo_root)


def test_j_p2_active_optimization_targets_exclude_inactive_and_frozen_decks(repo_root: Path) -> None:
    svc = _service(repo_root)
    context = svc.build_optimization_context(BuildOptimizationContextInput())
    assert context.status.value == "completed"
    assert context.result["deck_priority"] == ["rogshai/current"]
    assert set(context.result["available_decks"]) == {"rogshai/current"}

    allocation_request = OptimizeMultipleDecksWithAllocationInput()
    assert allocation_request.deck_ids == ("rogshai/current",)

    korvold = svc.generate_candidate_swaps(
        GenerateCandidateSwapsInput(deck_id="korvold/current", max_candidates=1)
    )
    assert korvold.status.value == "failed"
    assert any("not an active own deck" in error for error in korvold.errors)

    kaervek = svc.generate_candidate_swaps(
        GenerateCandidateSwapsInput(deck_id="kaervek/current", max_candidates=1)
    )
    assert kaervek.status.value == "failed"
    assert any("frozen opponent-only" in error for error in kaervek.errors)


def test_j_p2_rules_coverage_gate_scopes_exact_opponent_deck(repo_root: Path) -> None:
    svc = _service(repo_root)
    cosmic = svc.run_rules_coverage_gate(
        RunRulesCoverageGateInput(deck_id="opponent/cosmic-spiderman-midbudget")
    )
    assert cosmic.status.value == "completed"
    assert cosmic.result["cards_checked"] == 4
    assert cosmic.result["coverage_counts"] == {"unsupported": 4}

    morcant = svc.run_rules_coverage_gate(
        RunRulesCoverageGateInput(deck_id="opponent/morcant-elves")
    )
    assert morcant.status.value == "completed"
    assert morcant.result["cards_checked"] == 72
    assert morcant.result["coverage_counts"] == {"structural_only": 11, "unsupported": 61}

    doom = svc.run_rules_coverage_gate(
        RunRulesCoverageGateInput(deck_id="opponent/doom-prevails-precon")
    )
    assert doom.status.value == "completed"
    assert doom.result["cards_checked"] == 88


def test_j_p2_opponent_profiles_use_explicit_evidence_taxonomy(repo_root: Path) -> None:
    payload = json.loads(
        (repo_root / "data/opponents/current_structural_profiles.json").read_text(encoding="utf-8")
    )
    profiles = {row["deck_id"]: row for row in payload["profiles"]}
    for row in profiles.values():
        kinds = set(row["evidence_kinds"])
        assert kinds
        assert kinds <= ALLOWED_EVIDENCE_KINDS

    assert set(profiles["kaervek/current"]["evidence_kinds"]) == {"verified_full_deck"}
