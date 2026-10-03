"""Adversarial tests for the AF07 actual-card campaign producer.

These tests are engine-free: they exercise derivation, obligation-plan binding,
verdict logic and receipt shape. No test may make an engine process, and no test
may upgrade partial evidence into a PASS.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar

import pytest

from commander_lab.qualification.current_boundary import actual_card_campaign as campaign
from commander_lab.qualification.current_boundary import midgame_rows as midgame_rows_mod
from commander_lab.qualification.current_boundary import receipts as receipt_mod
from commander_lab.qualification.current_boundary.bridge_launcher import (
    canonical_xmage_engine_pin,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

# The live pin is resolved from config/rules_engines.json, never restated: the
# repository ratchet forbids a second literal copy.
PIN = canonical_xmage_engine_pin()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


# The ownership while #450 was the active midgame writer: owner routing is
# tested against this explicit map, independent of the live default.
FOREIGN_450 = {
    "src/commander_lab/qualification/current_boundary/midgame_rows.py": "PR #450",
    "scripts/run_midgame_capability_probe.py": "PR #450",
    "tests/qualification/test_current_boundary_midgame_rows.py": "PR #450",
}


def _record(
    fixture_id: str = "CARD_02",
    identity: str = "Rograkh, Son of Rohgahh",
    *,
    postconditions: tuple[str, ...] = ("Obligation holds.",),
    required_events: tuple[str, ...] = ("creature_entered",),
    **overrides: Any,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "fixture_id": fixture_id,
        "fixture_family": "actual_card",
        "card_authority_binding": {"card_identity": identity},
        "expected_events": {
            "required_events": list(required_events),
            "forbidden_events": [],
        },
        "terminal_postconditions": list(postconditions),
        "requested_state_digest": "a" * 64,
        "obligation_digest": "b" * 64,
        "materialization_version": "commander-lab.semantic-fixture-materialization/1.0.5",
        "materialization_digest": "c" * 64,
        "action_cost_state": [],
        "semantic_objects": [],
        "temporal_state": {"phase": "precombat_main", "step": "main"},
    }
    record.update(overrides)
    return record


def _row(record: dict[str, Any], *, in_denominator: bool = True) -> campaign.CardRow:
    return campaign.CardRow(
        fixture_id=str(record["fixture_id"]),
        card_identity=str(record["card_authority_binding"]["card_identity"]),
        record=record,
        in_effective_denominator=in_denominator,
        excluded_by_frozen_denominator=not in_denominator,
        requested_state_digest=record.get("requested_state_digest"),
        obligation_digest=record.get("obligation_digest"),
        materialization_version=record.get("materialization_version"),
        materialization_digest=record.get("materialization_digest"),
    )


def _measurement(
    fixture_id: str = "CARD_02",
    *,
    phase: str = "EXECUTED",
    detail: str = "obligation observed",
    verified: bool = True,
    construction: str = "EXACT",
    missing_tokens: tuple[str, ...] = (),
    token_evidence: dict[str, Any] | None = None,
    terminal_facts: dict[str, Any] | None = None,
    engine_commit: str | None = PIN,
    creation_errors: list[dict[str, Any]] | None = None,
) -> campaign.RowMeasurement:
    return campaign.RowMeasurement(
        fixture_id=fixture_id,
        phase=phase,
        engine_commit=engine_commit,
        construction_verdict=construction if phase == "EXECUTED" else None,
        creation_errors=creation_errors or [],
        execution=(
            {
                "fixture_id": fixture_id,
                "verified": verified,
                "construction_verdict": construction,
                "detail": detail,
                "missing_tokens": list(missing_tokens),
                "token_evidence": token_evidence or {},
                "terminal_facts": terminal_facts or {},
                "decision_trace": [],
                "refusals": [],
            }
            if phase == "EXECUTED"
            else None
        ),
    )


# --------------------------------------------------------------------------- #
# Derivation
# --------------------------------------------------------------------------- #


def test_corpus_is_derived_from_the_frozen_manifests() -> None:
    corpus = campaign.derive_corpus(REPO_ROOT)
    assert len(corpus.rows) == campaign.CORPUS_COUNT
    assert corpus.rows == tuple(sorted(corpus.rows, key=lambda row: row.fixture_id))

    domain = json.loads((REPO_ROOT / corpus.domain_manifest).read_text(encoding="utf-8"))
    assert corpus.identities == tuple(domain["regression_corpus_29"])

    fixtures = json.loads((REPO_ROOT / corpus.fixture_manifest).read_text(encoding="utf-8"))
    expected_map = {
        str(item["fixture_id"]): str(item["card_identity"])
        for item in fixtures["fixtures"]
        if str(item["fixture_id"]).startswith("CARD_") and item.get("card_identity")
    }
    assert corpus.fixture_identities == dict(sorted(expected_map.items()))
    assert {row.card_identity for row in corpus.rows} == set(corpus.identities)


def test_every_row_binds_the_effective_record_and_its_digests() -> None:
    corpus = campaign.derive_corpus(REPO_ROOT)
    for row in corpus.rows:
        binding = row.record["card_authority_binding"]
        assert binding["card_identity"] == row.card_identity
        assert row.record["fixture_family"] == "actual_card"
        assert row.requested_state_digest
        assert row.obligation_digest
        assert row.materialization_version


def test_the_credit_route_is_derived_not_assumed() -> None:
    corpus = campaign.derive_corpus(REPO_ROOT)
    in_denominator = {row.fixture_id for row in corpus.rows if row.in_effective_denominator}
    excluded = {row.fixture_id for row in corpus.rows if row.excluded_by_frozen_denominator}
    assert in_denominator == {"CARD_02"}
    assert len(excluded) == 28
    assert in_denominator | excluded == {row.fixture_id for row in corpus.rows}
    assert not (in_denominator & excluded)


def test_derivation_fails_closed_when_the_corpus_identity_is_dropped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    domain = json.loads(
        (REPO_ROOT / "qualification/manifests/ACTUAL_CARD_DOMAIN_v1.json").read_text(
            encoding="utf-8"
        )
    )
    domain["regression_corpus_29"] = domain["regression_corpus_29"][:-1]
    target = tmp_path / "qualification/manifests/ACTUAL_CARD_DOMAIN_v1.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(domain), encoding="utf-8")
    fixtures = REPO_ROOT / "qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json"
    (tmp_path / "qualification/manifests/COMMON_FIXTURE_MANIFEST_v1.json").write_text(
        fixtures.read_text(encoding="utf-8"), encoding="utf-8"
    )
    with pytest.raises(campaign.ActualCardCampaignError):
        campaign.derive_corpus(tmp_path)


# --------------------------------------------------------------------------- #
# Requirement derivation
# --------------------------------------------------------------------------- #


def test_starting_state_dimensions_are_derived_from_the_record() -> None:
    record = _record(
        stack_state=[{"semantic_id": "obj:bolt"}],
        semantic_objects=[
            {"zone": "battlefield", "counters": {"+1/+1": 1}, "tapped": True, "controller": "P1"},
            {"zone": "battlefield", "owner": "P1", "controller": "P2"},
            {"zone": "revealed", "owner": "P2", "controller": "P2"},
            {"zone": "library", "owner": "P2", "controller": "P2"},
        ],
        commander_state={"multiple_commander_relations": [{"a": "P1"}]},
        knowledge_state={
            "viewer_states": [{"viewer": "P1", "known_library_ranges": [{"a": 1, "b": 2}]}]
        },
    )
    dimensions = campaign.required_state_dimensions(record)
    assert "stack_objects" in dimensions
    assert "counters" in dimensions
    assert "tapped_permanents" in dimensions
    assert "control_divergence" in dimensions
    assert "revealed_zone" in dimensions
    assert "library_identity_objects" in dimensions
    assert "commander_relations" in dimensions
    assert "hidden_library_identity" in dimensions
    assert "temporal_checkpoint_unqualified" not in dimensions


def test_unqualified_temporal_point_is_flagged() -> None:
    record = _record(temporal_state={"phase": "combat", "step": "end_of_combat"})
    assert "temporal_checkpoint_unqualified" in campaign.required_state_dimensions(record)
    record = _record(temporal_state={"phase": "combat", "step": "combat_damage"})
    assert "temporal_checkpoint_unqualified" not in campaign.required_state_dimensions(record)


def test_executor_requirements_are_derived_from_script_and_procedure() -> None:
    record = _record(
        decision_script=[
            {
                "decision_family": "priority",
                "selection": {
                    "selector_kind": "semantic_action",
                    "semantic_value": {
                        "action": "cast",
                        "object": "obj:subject",
                        "target": "obj:x",
                        "delve_objects": ["obj:gy"],
                        "x": 3,
                    },
                },
            },
            {
                "decision_family": "choose_object",
                "selection": {"selector_kind": "semantic_object_set", "semantic_value": ["a"]},
            },
        ],
        native_procedure=[{"operation": "NATIVE_CAST_THING"}],
    )
    requirements = campaign.executor_requirements(record)
    assert "priority_action:cast" in requirements
    assert "inline_target" in requirements
    assert "inline_delve" in requirements
    assert "inline_x" in requirements
    assert "selector:semantic_object_set" in requirements
    assert "native_op:NATIVE_CAST_THING" in requirements


# --------------------------------------------------------------------------- #
# Obligation plans
# --------------------------------------------------------------------------- #


def test_every_plan_covers_its_effective_record_exactly() -> None:
    corpus = campaign.derive_corpus(REPO_ROOT)
    for fixture_id, plan in campaign.PLANS.items():
        row = corpus.row(fixture_id)
        assert plan.fixture_id == fixture_id
        assert plan.stale_reasons(row.record) == ()
        assert plan.proofs, f"{fixture_id} declares no proof"
        assert any(proof.terminal_check is not None for proof in plan.proofs) or any(
            proof.event_token is not None for proof in plan.proofs
        )


def test_plan_is_stale_when_the_record_postcondition_changes() -> None:
    plan = campaign.ObligationPlan(
        fixture_id="CARD_X",
        proofs=(campaign.PostconditionProof("A holds.", event_token="damage:P2:1"),),
    )
    record = _record(
        "CARD_X",
        postconditions=("A holds.", "B holds."),
        required_events=("damage:P2:1",),
    )
    reasons = plan.stale_reasons(record)
    assert reasons
    assert "B holds." in " ".join(reasons)


def test_plan_is_stale_when_an_event_proof_leaves_required_events() -> None:
    plan = campaign.ObligationPlan(
        fixture_id="CARD_X",
        proofs=(campaign.PostconditionProof("A holds.", event_token="damage:P2:1"),),
    )
    record = _record("CARD_X", postconditions=("A holds.",), required_events=("other_event",))
    assert plan.stale_reasons(record)


def test_postcondition_proof_requires_exactly_one_proof_kind() -> None:
    with pytest.raises(campaign.ActualCardCampaignError):
        campaign.PostconditionProof("A holds.")
    with pytest.raises(campaign.ActualCardCampaignError):
        campaign.PostconditionProof(
            "A holds.",
            event_token="damage:P2:1",
            terminal_check=midgame_rows_mod.TerminalCheck("life", principal="P2", value=1),
        )


# --------------------------------------------------------------------------- #
# Verdicts
# --------------------------------------------------------------------------- #


def _complete_direct_pass(
    *,
    fixture_id: str = "CARD_24",
    verified: bool = True,
    construction: str = "EXACT",
    engine_commit: str | None = PIN,
    terminal_facts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = _record(
        fixture_id,
        "Warstorm Surge",
        postconditions=("P2 is at 18 life after trigger resolves.",),
    )
    row = _row(record)
    measurement = _measurement(
        fixture_id,
        verified=verified,
        construction=construction,
        engine_commit=engine_commit,
        terminal_facts=terminal_facts or {"P2 is at 18 life": True},
        token_evidence={"entering_creature_damage:P2:2": {"events": [7]}},
    )
    return campaign.evaluate_row(
        row,
        measurement,
        expected_engine_commit=PIN,
        foreign_owned_surfaces=FOREIGN_450,
    )


def test_direct_pass_requires_complete_bound_evidence() -> None:
    evaluation = _complete_direct_pass()
    assert evaluation["outcome"] == campaign.OUTCOME_DIRECT_PASS
    assert evaluation["direct_receipt_eligible"] is True
    assert evaluation["postcondition_proofs"]
    assert all(item["held"] for item in evaluation["postcondition_proofs"])


def test_a_failed_proof_blocks_direct_pass() -> None:
    evaluation = _complete_direct_pass(terminal_facts={"P2 is at 18 life": False})
    assert evaluation["outcome"] != campaign.OUTCOME_DIRECT_PASS
    assert evaluation["direct_receipt_eligible"] is False


def test_engine_commit_mismatch_blocks_direct_pass() -> None:
    evaluation = _complete_direct_pass(engine_commit="0" * 40)
    assert evaluation["outcome"] != campaign.OUTCOME_DIRECT_PASS
    assert evaluation["direct_receipt_eligible"] is False


def test_construction_mismatch_blocks_direct_pass() -> None:
    evaluation = _complete_direct_pass(construction="MISMATCH")
    assert evaluation["outcome"] != campaign.OUTCOME_DIRECT_PASS
    assert evaluation["direct_receipt_eligible"] is False


def test_unverified_execution_blocks_direct_pass() -> None:
    evaluation = _complete_direct_pass(verified=False)
    assert evaluation["outcome"] != campaign.OUTCOME_DIRECT_PASS


def test_a_row_without_a_plan_can_never_direct_pass() -> None:
    record = _record("CARD_99", "Some Card", postconditions=("Obligation holds.",))
    row = _row(record)
    measurement = _measurement(
        "CARD_99",
        token_evidence={"creature_entered": {"events": [1]}},
        terminal_facts={},
    )
    evaluation = campaign.evaluate_row(
        row, measurement, expected_engine_commit=PIN, foreign_owned_surfaces={}
    )
    assert evaluation["outcome"] == campaign.OUTCOME_MEASURED
    assert evaluation["direct_receipt_eligible"] is False
    assert evaluation["blocker_class"] == campaign.BLOCKER_HARNESS_DEFECT


def test_unsupported_dimension_refusal_maps_to_provider_adapter_defect() -> None:
    record = _record("CARD_99", "Some Card", stack_state=[{"semantic_id": "obj:bolt"}])
    row = _row(record)
    measurement = _measurement(
        "CARD_99",
        phase="CREATION_REFUSED",
        creation_errors=[
            {
                "code": "midgame_starting_state_rejected",
                "message": "stack spells are not supported",
            }
        ],
    )
    evaluation = campaign.evaluate_row(
        row, measurement, expected_engine_commit=PIN, foreign_owned_surfaces={}
    )
    assert evaluation["blocker_class"] == campaign.BLOCKER_PROVIDER_ADAPTER_DEFECT
    assert evaluation["blocker_surface"] == campaign.SURFACE_NATIVE_RESTORATION


def test_engine_named_unsupported_zone_maps_to_the_adapter() -> None:
    record = _record(
        "CARD_99",
        "Some Card",
        semantic_objects=[{"zone": "library", "semantic_id": "obj:lib"}],
    )
    row = _row(record)
    measurement = _measurement(
        "CARD_99",
        phase="CREATION_REFUSED",
        creation_errors=[
            {
                "code": "midgame_starting_state_rejected",
                "message": (
                    "RestorationException: UNSUPPORTED_ZONE: CARD_99 obj:lib requests library"
                ),
            }
        ],
    )
    measurement.dimension_manifest = {
        "unsupported_dimensions": [
            "legacy/frozen partial library identity: no complete permutation, fail closed"
        ]
    }
    evaluation = campaign.evaluate_row(
        row, measurement, expected_engine_commit=PIN, foreign_owned_surfaces={}
    )
    assert evaluation["blocker_class"] == campaign.BLOCKER_PROVIDER_ADAPTER_DEFECT
    assert "partial library identity" in evaluation["blocker_detail"]


def test_stack_refusal_with_a_declared_causal_entry_is_a_probe_dependency() -> None:
    record = _record(
        "CARD_13",
        "Flare of Duplication",
        semantic_objects=[
            {"zone": "stack", "semantic_id": "obj:card13-bolt"},
            {"zone": "hand", "semantic_id": "obj:card_13-subject"},
        ],
        stack_state=[{"semantic_id": "obj:card13-bolt"}],
    )
    row = _row(record)
    measurement = _measurement(
        "CARD_13",
        phase="CREATION_REFUSED",
        creation_errors=[
            {
                "code": "midgame_starting_state_rejected",
                "message": (
                    "RestorationException: UNSUPPORTED_ZONE: CARD_13 obj:card13-bolt requests stack"
                ),
            }
        ],
    )
    measurement.dimension_manifest = {
        "unsupported_dimensions": [
            "stack spells (casting requires real costs/timing: executor scope)"
        ]
    }
    evaluation = campaign.evaluate_row(
        row,
        measurement,
        expected_engine_commit=PIN,
        foreign_owned_surfaces=FOREIGN_450,
        causal_entry_rows=("CARD_13",),
    )
    assert evaluation["blocker_class"] == campaign.BLOCKER_DEPENDENCY_WAITING
    assert evaluation["blocker_surface"] == campaign.SURFACE_MIDGAME_PROBE
    assert evaluation["blocker_owner"] == "PR #450"

    without_causal = campaign.evaluate_row(
        row,
        measurement,
        expected_engine_commit=PIN,
        foreign_owned_surfaces=FOREIGN_450,
    )
    assert without_causal["blocker_class"] == campaign.BLOCKER_PROVIDER_ADAPTER_DEFECT


def test_engine_named_zone_absent_from_the_record_stays_unknown() -> None:
    row = _row(_record("CARD_99", "Some Card"))
    measurement = _measurement(
        "CARD_99",
        phase="CREATION_REFUSED",
        creation_errors=[
            {
                "code": "midgame_starting_state_rejected",
                "message": "RestorationException: UNSUPPORTED_ZONE: CARD_99 obj:lib requests library",
            }
        ],
    )
    measurement.dimension_manifest = {
        "unsupported_dimensions": ["legacy/frozen partial library identity"]
    }
    evaluation = campaign.evaluate_row(
        row, measurement, expected_engine_commit=PIN, foreign_owned_surfaces={}
    )
    assert evaluation["blocker_class"] == campaign.BLOCKER_UNKNOWN


def test_an_unattributable_refusal_stays_unknown() -> None:
    row = _row(_record("CARD_99", "Some Card"))
    measurement = _measurement(
        "CARD_99",
        phase="CREATION_REFUSED",
        creation_errors=[{"code": "something_new", "message": "no rule matches"}],
    )
    evaluation = campaign.evaluate_row(
        row, measurement, expected_engine_commit=PIN, foreign_owned_surfaces={}
    )
    assert evaluation["blocker_class"] == campaign.BLOCKER_UNKNOWN


def test_unscripted_decision_family_absent_from_the_record_is_a_contract_dependency() -> None:
    record = _record(
        "CARD_99",
        "Some Card",
        decision_script=[
            {
                "decision_family": "priority",
                "selection": {
                    "selector_kind": "semantic_action",
                    "semantic_value": {"action": "cast"},
                },
            }
        ],
    )
    row = _row(record)
    measurement = _measurement(
        "CARD_99",
        detail="unscripted choose_object for P1: the row stops unverified",
        verified=False,
    )
    foreign = dict(FOREIGN_450)
    foreign[campaign.SURFACE_SUCCESSOR_CONTRACT] = "PR #462"
    evaluation = campaign.evaluate_row(
        row, measurement, expected_engine_commit=PIN, foreign_owned_surfaces=foreign
    )
    assert evaluation["blocker_class"] == campaign.BLOCKER_DEPENDENCY_WAITING
    assert evaluation["blocker_surface"] == campaign.SURFACE_SUCCESSOR_CONTRACT
    assert evaluation["blocker_owner"] == "PR #462"
    # Once no foreign writer owns the contract, the same gap is a fixture
    # defect for this campaign to correct, never a dependency or a pass.
    assert campaign.SURFACE_SUCCESSOR_CONTRACT not in campaign.DEFAULT_FOREIGN_OWNED_SURFACES
    unowned = campaign.evaluate_row(
        row,
        measurement,
        expected_engine_commit=PIN,
        foreign_owned_surfaces=campaign.DEFAULT_FOREIGN_OWNED_SURFACES,
    )
    assert unowned["blocker_class"] == campaign.BLOCKER_FIXTURE_DEFECT
    assert unowned["blocker_surface"] == campaign.SURFACE_SUCCESSOR_CONTRACT
    assert unowned["blocker_owner"] is None


def test_unscripted_decision_family_the_record_scripts_is_an_executor_dependency() -> None:
    record = _record(
        "CARD_99",
        "Some Card",
        decision_script=[
            {
                "decision_family": "declare_blocker",
                "selection": {"selector_kind": "blocker_assignment", "semantic_value": {}},
            }
        ],
    )
    row = _row(record)
    measurement = _measurement(
        "CARD_99",
        detail="unscripted declare_blocker for P2: the row stops unverified",
        verified=False,
    )
    evaluation = campaign.evaluate_row(
        row,
        measurement,
        expected_engine_commit=PIN,
        foreign_owned_surfaces=FOREIGN_450,
    )
    assert evaluation["blocker_class"] == campaign.BLOCKER_DEPENDENCY_WAITING
    assert evaluation["blocker_surface"] == campaign.SURFACE_MIDGAME_ROWS


def test_executor_gap_is_dependency_waiting_while_the_surface_is_foreign() -> None:
    row = _row(_record("CARD_99", "Some Card"))
    measurement = _measurement(
        "CARD_99",
        detail="unscripted declare_blocker for P2: the row stops unverified",
        verified=False,
    )
    foreign = campaign.evaluate_row(
        row,
        measurement,
        expected_engine_commit=PIN,
        foreign_owned_surfaces=FOREIGN_450,
    )
    assert foreign["blocker_class"] == campaign.BLOCKER_DEPENDENCY_WAITING
    assert foreign["blocker_owner"] == "PR #450"
    free = campaign.evaluate_row(
        row, measurement, expected_engine_commit=PIN, foreign_owned_surfaces={}
    )
    assert free["blocker_class"] == campaign.BLOCKER_HARNESS_DEFECT
    assert free["blocker_owner"] is None


def test_unsupported_scripted_action_is_classified_from_the_executor_detail() -> None:
    row = _row(_record("CARD_99", "Some Card"))
    measurement = _measurement(
        "CARD_99",
        detail=(
            "execution failed closed: scripted priority action 'activate' is not executed "
            "by this lane"
        ),
        verified=False,
    )
    evaluation = campaign.evaluate_row(
        row,
        measurement,
        expected_engine_commit=PIN,
        foreign_owned_surfaces=FOREIGN_450,
    )
    assert evaluation["blocker_class"] == campaign.BLOCKER_DEPENDENCY_WAITING
    assert evaluation["blocker_surface"] == campaign.SURFACE_MIDGAME_ROWS


def test_missing_required_events_never_pass() -> None:
    record = _record("CARD_99", "Some Card", postconditions=("Obligation holds.",))
    row = _row(record)
    measurement = _measurement(
        "CARD_99",
        missing_tokens=("damage:P2:4",),
        token_evidence={},
        terminal_facts={},
    )
    evaluation = campaign.evaluate_row(
        row, measurement, expected_engine_commit=PIN, foreign_owned_surfaces={}
    )
    assert evaluation["outcome"] == campaign.OUTCOME_BLOCKED
    assert evaluation["direct_receipt_eligible"] is False


# --------------------------------------------------------------------------- #
# Receipts
# --------------------------------------------------------------------------- #


def _receipt_row() -> campaign.CardRow:
    record = _record(
        "CARD_24",
        "Warstorm Surge",
        postconditions=("P2 is at 18 life after trigger resolves.",),
        required_events=("entering_creature_damage:P2:2",),
    )
    return _row(record)


def test_receipt_refused_for_a_non_pass() -> None:
    row = _receipt_row()
    measurement = _measurement("CARD_24", verified=False)
    evaluation = campaign.evaluate_row(
        row, measurement, expected_engine_commit=PIN, foreign_owned_surfaces={}
    )
    with pytest.raises(campaign.ActualCardCampaignError):
        campaign.positive_receipt(
            row,
            evaluation,
            measurement,
            candidate="xmage",
            candidate_commit=PIN,
            runner_digest="d" * 64,
        )


def test_receipt_is_schema_valid_and_credits_only_the_bound_obligation(
    tmp_path: Path,
) -> None:
    row = _receipt_row()
    measurement = _measurement(
        "CARD_24",
        terminal_facts={"P2 is at 18 life": True},
        token_evidence={"entering_creature_damage:P2:2": {"events": [7]}},
    )
    evaluation = campaign.evaluate_row(
        row, measurement, expected_engine_commit=PIN, foreign_owned_surfaces={}
    )
    assert evaluation["outcome"] == campaign.OUTCOME_DIRECT_PASS
    receipt = campaign.positive_receipt(
        row,
        evaluation,
        measurement,
        candidate="xmage",
        candidate_commit=PIN,
        runner_digest="d" * 64,
    )
    path = receipt_mod.persist(tmp_path / "CARD_24.json", receipt)
    loaded = receipt_mod.load_positive_fixture_receipt(path)
    assert loaded["test_identity"].startswith(campaign.TEST_IDENTITY_PREFIX)

    denominator = {
        "CARD_24": {
            "requested_state_digest": row.requested_state_digest,
            "obligation_digest": row.obligation_digest,
        }
    }
    credit = receipt_mod.positive_fixture_credit(
        [loaded],
        candidate="xmage",
        expected_commit=PIN,
        denominator=denominator,
        expected_runner_digest="d" * 64,
    )
    assert credit == {"CARD_24": [loaded["test_identity"]]}

    stale_denominator = {
        "CARD_24": {
            "requested_state_digest": "0" * 64,
            "obligation_digest": row.obligation_digest,
        }
    }
    assert (
        receipt_mod.positive_fixture_credit(
            [loaded],
            candidate="xmage",
            expected_commit=PIN,
            denominator=stale_denominator,
            expected_runner_digest="d" * 64,
        )
        == {}
    )


# --------------------------------------------------------------------------- #
# Matrix
# --------------------------------------------------------------------------- #


def test_matrix_always_carries_every_frozen_identity() -> None:
    corpus = campaign.derive_corpus(REPO_ROOT)
    evaluations = {
        "CARD_02": {
            "outcome": campaign.OUTCOME_DIRECT_PASS,
            "blocker_class": None,
            "direct_receipt_eligible": True,
        }
    }
    matrix = campaign.build_matrix(corpus, evaluations)
    assert matrix["schema_version"] == campaign.MATRIX_SCHEMA
    assert len(matrix["rows"]) == campaign.CORPUS_COUNT
    assert {row["fixture_id"] for row in matrix["rows"]} == {row.fixture_id for row in corpus.rows}
    outcomes = matrix["summary"]["outcomes"]
    assert sum(outcomes.values()) == campaign.CORPUS_COUNT
    assert matrix["summary"]["direct_pass"] == ["CARD_02"]
    unmeasured = [row for row in matrix["rows"] if row["fixture_id"] != "CARD_02"]
    assert all(row["verdict"]["outcome"] == campaign.OUTCOME_UNKNOWN for row in unmeasured)


def test_matrix_digest_changes_with_content() -> None:
    corpus = campaign.derive_corpus(REPO_ROOT)
    first = campaign.build_matrix(corpus, {})
    second = campaign.build_matrix(corpus, {})
    assert campaign.matrix_digest(first) == campaign.matrix_digest(second)
    first["summary"]["direct_pass"] = ["CARD_02"]
    assert campaign.matrix_digest(first) != campaign.matrix_digest(second)


def test_matrix_refuses_a_pass_without_receipt_eligibility() -> None:
    corpus = campaign.derive_corpus(REPO_ROOT)
    evaluations = {
        row.fixture_id: {
            "outcome": campaign.OUTCOME_BLOCKED,
            "blocker_class": campaign.BLOCKER_UNKNOWN,
            "direct_receipt_eligible": False,
        }
        for row in corpus.rows
    }
    evaluations["CARD_02"] = {
        "outcome": campaign.OUTCOME_DIRECT_PASS,
        "blocker_class": None,
        "direct_receipt_eligible": False,
    }
    with pytest.raises(campaign.ActualCardCampaignError):
        campaign.build_matrix(corpus, evaluations)

    evaluations["CARD_02"]["direct_receipt_eligible"] = True
    matrix = campaign.build_matrix(corpus, evaluations)
    assert matrix["summary"]["direct_pass"] == ["CARD_02"]
    assert matrix["summary"]["direct_receipt_eligible"] == ["CARD_02"]


def test_no_surface_has_a_foreign_writer_once_450_and_462_are_merged() -> None:
    assert dict(campaign.DEFAULT_FOREIGN_OWNED_SURFACES) == {}


def test_a_vocabulary_binding_and_its_cost_obligation_reach_the_row_spec() -> None:
    """CARD_03's free-text cost token is bound to the engine-verified cost
    vocabulary, and the plan's cost declaration reaches the executor's spec; the
    free text itself never verifies anything."""
    plan = campaign.plan_for("CARD_03")
    assert plan is not None
    bindings = dict(plan.token_bindings)
    cost = bindings["total_cost_determined"]
    assert isinstance(cost, midgame_rows_mod.VocabularyToken)
    assert cost.token == "cost_determined:base_plus_3_generic"
    record = {"action_cost_state": [], "terminal_postconditions": []}
    spec = campaign.derive_row_spec(record, plan)
    assert spec.cost_obligation == ("obj:card03-spell", "{6}{U}{R}", "{9}{U}{R}")
    document = plan.document()
    rendered = {item["token"]: item["check"] for item in document["token_bindings"]}
    assert rendered["total_cost_determined"] == {
        "vocabulary_token": "cost_determined:base_plus_3_generic"
    }
    # A row with no plan carries no cost declaration.
    assert campaign.derive_row_spec(record, None).cost_obligation is None


def test_stack_rows_enter_through_the_declared_causal_stack_route() -> None:
    """A record that places spells on the stack is never placed with them: it
    enters through the production probe's declared causal-stack route, whose
    fuel is declared there; a placement row has no causal entry."""
    for fixture_id in ("CARD_07", "CARD_10", "CARD_13", "CARD_16", "CARD_20", "CARD_22"):
        entry = campaign.causal_entry(fixture_id)
        assert entry is not None and entry["entry_mode"] == "causal_stack"
        # Rograkh costs {0}: CARD_10's commander spell is the one fuel-free frame.
        assert entry["fuel"] or fixture_id == "CARD_10", fixture_id
    assert campaign.causal_entry("CARD_02") is None
    assert campaign.causal_entry("CARD_26") is None


def test_a_causal_reconstruction_is_its_own_receipt_fact() -> None:
    placement = midgame_rows_mod.RowExecution("CARD_02", True, "EXACT", "ok")
    assert "causal_reconstruction" not in placement.document()
    verdict = {"causal_match": True, "mismatches": [], "frames_verified": 1}
    causal = midgame_rows_mod.RowExecution(
        "CARD_22",
        True,
        "EXACT",
        "ok",
        causal_reconstruction={"entry_mode": "causal_stack", "verdict": verdict},
    )
    assert causal.document()["causal_reconstruction"]["verdict"] == verdict


# --------------------------------------------------------------------------- #
# Same-epoch producer (PB-03)
# --------------------------------------------------------------------------- #


class _FakeProbe:
    CAUSAL_ROWS: ClassVar[dict[str, Any]] = {}

    class _Client:
        engine_artifact: ClassVar[dict[str, str]] = {"kind": "file", "sha256": "e" * 64}

        def __enter__(self) -> _FakeProbe._Client:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

    def open_client(self, workspace: Path) -> _FakeProbe._Client:
        return self._Client()


def test_execute_and_persist_receipts_only_direct_passes_and_survives_a_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipts_dir = tmp_path / "receipts" / campaign.RECEIPT_SUBDIR
    receipts_dir.mkdir(parents=True)
    # A receipt left by an earlier run for a row that no longer verifies.
    (receipts_dir / "CARD_05.json").write_text("{}", encoding="utf-8")

    def fake_measure(client: Any, row: campaign.CardRow, plan: Any, *, seed: int) -> Any:
        if row.fixture_id == "CARD_02":
            raise RuntimeError("bridge process died")
        return _measurement(row.fixture_id)

    def fake_evaluate(row: campaign.CardRow, measurement: Any, **_: Any) -> dict[str, Any]:
        passed = row.fixture_id == "CARD_24" and measurement.phase == "EXECUTED"
        return {
            "outcome": campaign.OUTCOME_DIRECT_PASS if passed else campaign.OUTCOME_BLOCKED,
            "blocker_class": None if passed else campaign.BLOCKER_HARNESS_DEFECT,
            "blocker_detail": None if passed else measurement.phase,
            "direct_receipt_eligible": passed,
            "construction_verdict": "EXACT",
            "postcondition_proofs": [],
        }

    monkeypatch.setattr(midgame_rows_mod, "probe_module", lambda: _FakeProbe())
    monkeypatch.setattr(campaign, "measure_row", fake_measure)
    monkeypatch.setattr(campaign, "evaluate_row", fake_evaluate)

    seen: list[str] = []
    matrix = campaign.execute_and_persist(
        workspace=tmp_path,
        candidate_commit=PIN,
        runner_digest="d" * 64,
        receipts_dir=receipts_dir,
        fixtures=["CARD_24", "CARD_02", "CARD_05"],
        root=REPO_ROOT,
        measurements_dir=tmp_path / "measurements",
        on_row=lambda row, evaluation: seen.append(row.fixture_id),
    )

    assert seen == ["CARD_24", "CARD_02", "CARD_05"]
    assert sorted(path.name for path in receipts_dir.iterdir()) == ["CARD_24.json"]
    receipt = receipt_mod.load_positive_fixture_receipt(receipts_dir / "CARD_24.json")
    assert receipt["runner_digest"] == "d" * 64
    assert receipt["candidate_commit"] == PIN
    crashed = json.loads((tmp_path / "measurements" / "CARD_02.json").read_text())
    assert crashed["phase"] == "LANE_FAILED"
    assert "bridge process died" in crashed["runtime_error"]
    assert matrix["campaign"]["candidate_commit"] == PIN
    assert matrix["campaign"]["runner_digest"] == "d" * 64
    assert matrix["campaign"]["receipt_subdir"] == campaign.RECEIPT_SUBDIR
    assert matrix["summary"]["direct_pass"] == ["CARD_24"]
    # The rows that were not selected are present and unexecuted, never credited.
    assert matrix["summary"]["outcomes"][campaign.OUTCOME_UNKNOWN] == campaign.CORPUS_COUNT - 3


def test_execute_and_persist_refuses_an_unknown_fixture_before_touching_receipts(
    tmp_path: Path,
) -> None:
    receipts_dir = tmp_path / "receipts"
    with pytest.raises(campaign.ActualCardCampaignError, match="CARD_99"):
        campaign.execute_and_persist(
            workspace=tmp_path,
            candidate_commit=PIN,
            runner_digest="d" * 64,
            receipts_dir=receipts_dir,
            fixtures=["CARD_99"],
            root=REPO_ROOT,
        )
    assert not receipts_dir.exists()


def test_campaign_receipts_never_share_the_full107_receipt_directory() -> None:
    # CARD_02 is produced by both the midgame denominator lane and the campaign;
    # one directory would let either producer overwrite the other's evidence.
    assert campaign.RECEIPT_SUBDIR != receipt_mod.POSITIVE_RECEIPT_SUBDIR


# --------------------------------------------------------------------------- #
# Demonstrated failure
# --------------------------------------------------------------------------- #


def _evaluated_facts(row: campaign.CardRow, *, held: bool) -> dict[str, bool]:
    plan = campaign.plan_for(row.fixture_id)
    assert plan is not None
    return {
        check.describe(): held
        for proof in plan.proofs
        if proof.event_token is None
        for check in proof.checks
    }


def _executed(row: campaign.CardRow, facts: dict[str, bool], **execution: Any) -> Any:
    measurement = _measurement(row.fixture_id, verified=False, terminal_facts=facts)
    assert measurement.execution is not None
    measurement.execution = {**measurement.execution, "script_consumed": True, **execution}
    return measurement


def test_an_evaluated_contradiction_after_the_whole_script_is_fail() -> None:
    row = _receipt_row()
    measurement = _executed(row, _evaluated_facts(row, held=False))
    evaluation = campaign.evaluate_row(
        row, measurement, expected_engine_commit=PIN, foreign_owned_surfaces={}
    )
    assert evaluation["outcome"] == campaign.OUTCOME_FAIL
    assert evaluation["blocker_class"] == campaign.BLOCKER_ENGINE_DEFECT
    assert evaluation["direct_receipt_eligible"] is False


@pytest.mark.parametrize(
    "variant",
    ["unevaluated_check", "script_unfinished", "missing_token", "foreign_build"],
)
def test_an_absence_of_evidence_is_never_fail(variant: str) -> None:
    row = _receipt_row()
    facts = _evaluated_facts(row, held=False)
    execution: dict[str, Any] = {}
    commit = PIN
    if variant == "unevaluated_check":
        facts = {}
    elif variant == "script_unfinished":
        execution["script_consumed"] = False
    elif variant == "missing_token":
        execution["missing_tokens"] = ["entering_creature_damage:P2:2"]
    else:
        commit = "0" * 40
    measurement = _executed(row, facts, **execution)
    measurement.engine_commit = commit
    evaluation = campaign.evaluate_row(
        row, measurement, expected_engine_commit=PIN, foreign_owned_surfaces={}
    )
    assert evaluation["outcome"] != campaign.OUTCOME_FAIL
