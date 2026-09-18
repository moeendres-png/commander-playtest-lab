from __future__ import annotations

import pytest
from pydantic import ValidationError

from commander_lab.engine.rules.deckstrength_gate import evaluate_strict_deckstrength_readiness
from commander_lab.engine.rules.deckstrength_readiness import (
    DECKSTRENGTH_EVIDENCE_CLASS,
    TECHNICAL_CONFORMANCE_EVIDENCE_CLASS,
    DeckstrengthDecisionContract,
    EngineCrnProofManifest,
    EngineCrnStreamProof,
    FrozenCandidate,
    FrozenOpponent,
    LaneCapabilities,
    derive_pilot_substream_seed,
)

H64 = "a" * 64
H40 = "b" * 40
XMAGE = "77d7646da6958fdf8125ee7c8f4aabd130d21d4c"
BRIDGE = "175bc06205703c7f003bff6bdd065b793c641ef4"


def contract() -> DeckstrengthDecisionContract:
    return DeckstrengthDecisionContract(
        campaign_id="fixture",
        candidate_population=(
            FrozenCandidate(candidate_id="C001", deck_sha256=H64, role="candidate"),
            FrozenCandidate(candidate_id="C043", deck_sha256="c" * 64, role="control"),
        ),
        opponent_ensemble=tuple(
            FrozenOpponent(opponent_id=f"O{i}", deck_sha256=(f"{i}" * 64)[:64], evidence_class="verified_full")
            for i in range(1, 4)
        ),
        pilot_policy_versions=("rogshai-1", "opponent-1"),
        master_seeds=(101, 102, 103, 104),
        candidate_seats=(1, 2, 3, 4),
        pairing="common_seed_candidate_vs_control",
        replications=2,
        stopping_rule="fixed_n",
        failure_handling="same_seed_no_replacement_fail_closed",
        multiplicity_rule="holm",
        confirmatory_evidence_rule="paired_primary_placement",
        holdout_id="sealed-holdout-1",
        holdout_manifest_sha256="d" * 64,
    )


def technical_lane() -> LaneCapabilities:
    return LaneCapabilities(
        evidence_class=TECHNICAL_CONFORMANCE_EVIDENCE_CLASS,
        official_campaign_eligible=False,
        consumed_gameplay_evidence_capable=False,
        xmage_rules_authority=True,
        commander_lab_pilot_decision_authority=True,
        hidden_information_actor_scoped=True,
        fallback_used=False,
        one_jvm_per_game=True,
        unsupported_paths_fail_closed=True,
    )


def proof() -> EngineCrnProofManifest:
    streams=[]
    for idx,name in enumerate(("opponent_shuffle","rogshai_shuffle","turn_order","engine_misc"), 1):
        streams.append(EngineCrnStreamProof(
            stream_name=name,
            derivation_version="fixture-v1",
            source_commit=H40,
            test_artifact_sha256=(hex(idx)[2:] * 64)[:64],
            invariance_trace_sha256s=(("e" * 63)+str(idx), ("f" * 63)+str(idx)),
            distinct_deck_cases=2,
        ))
    return EngineCrnProofManifest(xmage_commit=XMAGE, bridge_commit=BRIDGE, streams=tuple(streams))


def test_current_technical_lane_cannot_be_promoted_by_metadata() -> None:
    result=evaluate_strict_deckstrength_readiness(
        contract=contract(), lane=technical_lane(), engine_crn_proof=None,
        pilot_crn_substreams_integrated=False,
        expected_xmage_commit=XMAGE, expected_bridge_commit=BRIDGE,
    )
    assert result.ready is False
    assert result.official_candidate_vs_control_allowed is False
    assert "lane_evidence_class_not_deckstrength" in result.blockers
    assert "engine_rules_crn_substreams_unproven" in result.blockers
    assert "pilot_crn_substreams_not_integrated" in result.blockers


def test_named_pilot_substreams_are_deterministic_domain_separated_and_uuid_free() -> None:
    a=derive_pilot_substream_seed(master_seed=42, stream_name="rogshai_tiebreak", semantic_actor_key="rogshai", decision_offset=7, decision_class="priority")
    assert a == derive_pilot_substream_seed(master_seed=42, stream_name="rogshai_tiebreak", semantic_actor_key="rogshai", decision_offset=7, decision_class="priority")
    b=derive_pilot_substream_seed(master_seed=42, stream_name="opponent_tiebreak", semantic_actor_key="opponent-seat-2", decision_offset=7, decision_class="priority")
    assert a != b


def test_contract_rejects_non_four_seat_schedule() -> None:
    data=contract().model_dump()
    data["candidate_seats"]=(1,2,3,3)
    with pytest.raises(ValidationError):
        DeckstrengthDecisionContract.model_validate(data)


def test_crn_manifest_requires_all_four_engine_owned_streams() -> None:
    data=proof().model_dump()
    data["streams"]=data["streams"][:-1]
    with pytest.raises(ValidationError):
        EngineCrnProofManifest.model_validate(data)


def test_synthetic_complete_fixture_can_pass_schema_gate_only() -> None:
    lane=LaneCapabilities(
        evidence_class=DECKSTRENGTH_EVIDENCE_CLASS,
        official_campaign_eligible=True,
        consumed_gameplay_evidence_capable=True,
        xmage_rules_authority=True,
        commander_lab_pilot_decision_authority=True,
        hidden_information_actor_scoped=True,
        fallback_used=False,
        one_jvm_per_game=True,
        unsupported_paths_fail_closed=True,
    )
    result=evaluate_strict_deckstrength_readiness(
        contract=contract(), lane=lane, engine_crn_proof=proof(),
        pilot_crn_substreams_integrated=True,
        expected_xmage_commit=XMAGE, expected_bridge_commit=BRIDGE,
    )
    assert result.ready is True
    assert result.blockers == ()


def test_engine_proof_commit_mismatch_fails_closed() -> None:
    lane=LaneCapabilities(
        evidence_class=DECKSTRENGTH_EVIDENCE_CLASS,
        official_campaign_eligible=True,
        consumed_gameplay_evidence_capable=True,
        xmage_rules_authority=True,
        commander_lab_pilot_decision_authority=True,
        hidden_information_actor_scoped=True,
        fallback_used=False,
        one_jvm_per_game=True,
        unsupported_paths_fail_closed=True,
    )
    result=evaluate_strict_deckstrength_readiness(
        contract=contract(), lane=lane, engine_crn_proof=proof(),
        pilot_crn_substreams_integrated=True,
        expected_xmage_commit="0"*40, expected_bridge_commit=BRIDGE,
    )
    assert result.ready is False
    assert "engine_crn_proof_xmage_commit_mismatch" in result.blockers
