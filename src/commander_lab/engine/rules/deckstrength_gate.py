from __future__ import annotations

from commander_lab.engine.rules.deckstrength_readiness import (
    DeckstrengthDecisionContract,
    DeckstrengthReadinessResult,
    EngineCrnProofManifest,
    LaneCapabilities,
    evaluate_deckstrength_readiness,
)


def evaluate_strict_deckstrength_readiness(
    *,
    contract: DeckstrengthDecisionContract,
    lane: LaneCapabilities,
    engine_crn_proof: EngineCrnProofManifest | None,
    pilot_crn_substreams_integrated: bool,
    expected_xmage_commit: str,
    expected_bridge_commit: str,
) -> DeckstrengthReadinessResult:
    """Final fail-closed gate for official Candidate-v-Control XMage evidence."""
    base = evaluate_deckstrength_readiness(
        contract=contract,
        lane=lane,
        engine_crn_proof=engine_crn_proof,
    )
    blockers = list(base.blockers)
    if not pilot_crn_substreams_integrated:
        blockers.append("pilot_crn_substreams_not_integrated")
    if engine_crn_proof is not None:
        if engine_crn_proof.xmage_commit != expected_xmage_commit:
            blockers.append("engine_crn_proof_xmage_commit_mismatch")
        if engine_crn_proof.bridge_commit != expected_bridge_commit:
            blockers.append("engine_crn_proof_bridge_commit_mismatch")
    ready = not blockers
    return DeckstrengthReadinessResult(
        ready=ready,
        blockers=tuple(blockers),
        engine_crn_proven=engine_crn_proof is not None,
        pilot_crn_substreams_available=pilot_crn_substreams_integrated,
        official_candidate_vs_control_allowed=ready,
    )
