from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


DECKSTRENGTH_EVIDENCE_CLASS = "xmage_deckstrength_candidate_vs_control"
TECHNICAL_CONFORMANCE_EVIDENCE_CLASS = "technical_conformance_only"
ENGINE_CRN_STREAMS = (
    "opponent_shuffle",
    "rogshai_shuffle",
    "turn_order",
    "engine_misc",
)
PILOT_CRN_STREAMS = ("opponent_tiebreak", "rogshai_tiebreak")


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FrozenCandidate(_StrictModel):
    candidate_id: str = Field(min_length=1)
    deck_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    role: Literal["candidate", "control"]


class FrozenOpponent(_StrictModel):
    opponent_id: str = Field(min_length=1)
    deck_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evidence_class: str = Field(min_length=1)


class DeckstrengthDecisionContract(_StrictModel):
    schema_version: Literal["xmage-deckstrength-decision-contract-1.0.0"] = (
        "xmage-deckstrength-decision-contract-1.0.0"
    )
    campaign_id: str = Field(min_length=1)
    candidate_population: tuple[FrozenCandidate, ...]
    opponent_ensemble: tuple[FrozenOpponent, ...]
    pilot_policy_versions: tuple[str, ...]
    master_seeds: tuple[int, ...]
    candidate_seats: tuple[Literal[1, 2, 3, 4], ...]
    pairing: Literal["common_seed_candidate_vs_control"]
    replications: int = Field(ge=1)
    stopping_rule: str = Field(min_length=1)
    failure_handling: Literal["same_seed_no_replacement_fail_closed"]
    multiplicity_rule: str = Field(min_length=1)
    confirmatory_evidence_rule: str = Field(min_length=1)
    holdout_id: str = Field(min_length=1)
    holdout_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    holdout_consumed: Literal[False] = False
    pod_size: Literal[4] = 4
    one_jvm_per_game: Literal[True] = True
    xmage_rules_authority: Literal[True] = True
    commander_lab_pilot_decision_authority: Literal[True] = True
    hidden_information_actor_scoped: Literal[True] = True
    ai_fallback_allowed: Literal[False] = False
    default_fallback_allowed: Literal[False] = False
    random_fallback_allowed: Literal[False] = False
    unsupported_paths_fail_closed: Literal[True] = True
    requested_evidence_class: Literal["xmage_deckstrength_candidate_vs_control"] = (
        DECKSTRENGTH_EVIDENCE_CLASS
    )

    @model_validator(mode="after")
    def freeze_population_and_schedule(self) -> "DeckstrengthDecisionContract":
        if len(self.candidate_population) < 2:
            raise ValueError("candidate population must contain at least two frozen decks")
        ids = [item.candidate_id for item in self.candidate_population]
        if len(ids) != len(set(ids)):
            raise ValueError("candidate population contains duplicate candidate_id")
        if not any(item.role == "control" for item in self.candidate_population):
            raise ValueError("candidate population must contain at least one control")
        if len(self.opponent_ensemble) < 3:
            raise ValueError("4p campaign requires at least three frozen opponents")
        opp_ids = [item.opponent_id for item in self.opponent_ensemble]
        if len(opp_ids) != len(set(opp_ids)):
            raise ValueError("opponent ensemble contains duplicate opponent_id")
        if not self.pilot_policy_versions or any(not value.strip() for value in self.pilot_policy_versions):
            raise ValueError("pilot policy versions must be frozen")
        if not self.master_seeds or len(self.master_seeds) != len(set(self.master_seeds)):
            raise ValueError("master seeds must be non-empty and unique")
        if len(self.master_seeds) != len(self.candidate_seats):
            raise ValueError("candidate_seats must map one-for-one to master_seeds")
        if set(self.candidate_seats) != {1, 2, 3, 4}:
            raise ValueError("candidate schedule must exercise all four seats")
        return self


class EngineCrnStreamProof(_StrictModel):
    stream_name: Literal[
        "opponent_shuffle", "rogshai_shuffle", "turn_order", "engine_misc"
    ]
    derivation_version: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    test_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    invariance_trace_sha256s: tuple[str, ...]
    distinct_deck_cases: int = Field(ge=2)
    same_seed_deck_independent_invariance_passed: Literal[True] = True

    @model_validator(mode="after")
    def require_reproducible_evidence(self) -> "EngineCrnStreamProof":
        if len(self.invariance_trace_sha256s) < 2:
            raise ValueError("CRN proof requires at least two invariance trace hashes")
        for value in self.invariance_trace_sha256s:
            if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
                raise ValueError("invariance trace hashes must be lowercase SHA256")
        return self


class EngineCrnProofManifest(_StrictModel):
    schema_version: Literal["xmage-engine-crn-proof-1.0.0"] = "xmage-engine-crn-proof-1.0.0"
    xmage_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    bridge_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    streams: tuple[EngineCrnStreamProof, ...]
    one_isolated_jvm_per_game_validated: Literal[True] = True

    @model_validator(mode="after")
    def require_all_engine_streams(self) -> "EngineCrnProofManifest":
        names = [item.stream_name for item in self.streams]
        if sorted(names) != sorted(ENGINE_CRN_STREAMS):
            raise ValueError(f"engine CRN proof must contain exactly {ENGINE_CRN_STREAMS!r}")
        return self


class LaneCapabilities(_StrictModel):
    evidence_class: str = Field(min_length=1)
    official_campaign_eligible: bool
    consumed_gameplay_evidence_capable: bool
    xmage_rules_authority: bool
    commander_lab_pilot_decision_authority: bool
    hidden_information_actor_scoped: bool
    fallback_used: bool
    one_jvm_per_game: bool
    unsupported_paths_fail_closed: bool


class DeckstrengthReadinessResult(_StrictModel):
    schema_version: Literal["xmage-deckstrength-readiness-result-1.0.0"] = (
        "xmage-deckstrength-readiness-result-1.0.0"
    )
    ready: bool
    blockers: tuple[str, ...]
    engine_crn_proven: bool
    pilot_crn_substreams_available: bool
    official_candidate_vs_control_allowed: bool


def derive_pilot_substream_seed(
    *, master_seed: int, stream_name: Literal["opponent_tiebreak", "rogshai_tiebreak"],
    semantic_actor_key: str, decision_offset: int, decision_class: str,
) -> int:
    """Domain-separated pilot RNG seed independent of XMage UUIDs and deck contents."""
    if master_seed < 0 or decision_offset < 1 or not semantic_actor_key.strip() or not decision_class.strip():
        raise ValueError("invalid pilot substream seed material")
    material = (
        f"commander-lab-crn-v1|{master_seed}|{stream_name}|{semantic_actor_key}|"
        f"{decision_offset}|{decision_class}"
    )
    return int.from_bytes(hashlib.sha256(material.encode("utf-8")).digest()[:8], "big")


def evaluate_deckstrength_readiness(
    *, contract: DeckstrengthDecisionContract, lane: LaneCapabilities,
    engine_crn_proof: EngineCrnProofManifest | None,
) -> DeckstrengthReadinessResult:
    """Fail closed. A technical-conformance lane can never be promoted by metadata alone."""
    del contract  # Pydantic construction is the contract validation gate.
    blockers: list[str] = []
    if lane.evidence_class != DECKSTRENGTH_EVIDENCE_CLASS:
        blockers.append("lane_evidence_class_not_deckstrength")
    if not lane.official_campaign_eligible:
        blockers.append("lane_not_official_campaign_eligible")
    if not lane.consumed_gameplay_evidence_capable:
        blockers.append("lane_cannot_emit_gameplay_evidence")
    if not lane.xmage_rules_authority:
        blockers.append("xmage_not_sole_rules_authority")
    if not lane.commander_lab_pilot_decision_authority:
        blockers.append("commander_lab_pilots_not_sole_discretionary_policy")
    if not lane.hidden_information_actor_scoped:
        blockers.append("hidden_information_not_actor_scoped")
    if lane.fallback_used:
        blockers.append("decision_fallback_present")
    if not lane.one_jvm_per_game:
        blockers.append("one_jvm_per_game_not_enforced")
    if not lane.unsupported_paths_fail_closed:
        blockers.append("unsupported_paths_not_fail_closed")
    if engine_crn_proof is None:
        blockers.append("engine_rules_crn_substreams_unproven")
    ready = not blockers
    return DeckstrengthReadinessResult(
        ready=ready,
        blockers=tuple(blockers),
        engine_crn_proven=engine_crn_proof is not None,
        pilot_crn_substreams_available=True,
        official_candidate_vs_control_allowed=ready,
    )
