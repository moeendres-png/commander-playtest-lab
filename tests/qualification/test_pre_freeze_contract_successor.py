from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_PATH = REPO_ROOT / "qualification/CURRENT_PRE_FREEZE_CONTRACT.json"
SUCCESSOR_PATH = (
    REPO_ROOT / "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_17.json"
)
PREDECESSOR_CONTRACT_PATH = (
    REPO_ROOT / "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_16.json"
)
V115_CONTRACT_PATH = (
    REPO_ROOT / "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_15.json"
)
V106_CONTRACT_PATH = (
    REPO_ROOT / "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_6.json"
)
# The SLOT-04 lossless hidden-state errata (#255 comment 5925956587) for the six
# construct-and-project HIDDEN rows.
HIDDEN_ERRATA_IDS = [
    "HIDDEN_01",
    "HIDDEN_02",
    "HIDDEN_03",
    "HIDDEN_04",
    "HIDDEN_19",
    "HIDDEN_HONEYCARD_SENTINEL",
]
# The SLOT-04 event-scenario errata: a real reveal and a real look.
# In the order the successor contracts added them (1.0.9, 1.0.10, 1.0.11).
HIDDEN_EVENT_ERRATA_IDS = [
    "HIDDEN_07",
    "HIDDEN_08",
    "HIDDEN_09",
    "HIDDEN_14",
    "HIDDEN_18",
    "HIDDEN_17",
]
# The successor contract carries the adjudicated fixture errata from #255/441
# section C (the rows whose script began inside a cast, plus the MICRO_COSTS
# CR 307.1 fixture-defect correction), the CR 103.8a START-2 successor, and the
# SLOT-04 HIDDEN errata.
# The SLOT-04 lossless-library errata for AF07 rows outside the denominator (1.0.12).
CARD_LIBRARY_ERRATA_IDS = ["CARD_09", "CARD_12", "CARD_15", "CARD_27", "CARD_29"]
# The AF07 decision-script errata (1.0.13): CARD_09 keeps its place (its
# lossless-library overlay is carried inside it); the others are appended.
CARD_SCRIPT_ERRATA_IDS = [
    "CARD_01",
    "CARD_04",
    "CARD_05",
    "CARD_18",
    "CARD_23",
    "CARD_26",
    "CARD_08",
    "CARD_11",
    "CARD_21",
]
# Rows whose 1.0.12 lossless-library overlay travels inside a later
# decision-script erratum (they keep their place in the patch order).
CARRIED_LIBRARY_ERRATA_IDS = ["CARD_09", "CARD_15", "CARD_27"]
CARD_ERRATA_IDS = [*CARD_LIBRARY_ERRATA_IDS, *CARD_SCRIPT_ERRATA_IDS]
# The later SLOT-04 event-scenario errata (1.0.15): a scry and a pile split.
LATE_HIDDEN_EVENT_ERRATA_IDS = ["HIDDEN_10", "HIDDEN_13"]
# The SLOT-04 event-scenario errata (1.0.16): a look at a face-down exiled card
# that outlives its source, and a cloaked permanent's ward as a hidden source
# and a hidden ability.
BATCH5_HIDDEN_EVENT_ERRATA_IDS = ["HIDDEN_05", "HIDDEN_15", "HIDDEN_16"]
# Final XMage AF05 event rows in 1.0.17: shuffle invalidation, face-down
# exile invalidation, and controlled-player authority.
BATCH6_HIDDEN_EVENT_ERRATA_IDS = ["HIDDEN_11", "HIDDEN_06", "HIDDEN_12"]
CHANGED_FIXTURE_IDS = [
    "WS05-CMD-START-2",
    "MICRO_MODES",
    "NEGATIVE_FIRST_OPTION",
    "NEGATIVE_GUI_DEFAULT",
    "NEGATIVE_RANDOM_OPTION",
    "NEGATIVE_SILENT_SKIP",
    "PILOT_TARGET_AMOUNT",
    "PILOT_MULTI_AMOUNT",
    "MICRO_COSTS",
    *HIDDEN_ERRATA_IDS,
    *HIDDEN_EVENT_ERRATA_IDS,
    *CARD_ERRATA_IDS,
    *LATE_HIDDEN_EVENT_ERRATA_IDS,
    *BATCH5_HIDDEN_EVENT_ERRATA_IDS,
    *BATCH6_HIDDEN_EVENT_ERRATA_IDS,
]
# Of those, the rows inside the 107-row provider denominator; the AF07 CARD
# rows are outside it, so correcting them leaves the denominator untouched.
DENOMINATOR_CHANGED_FIXTURE_IDS = [
    fixture for fixture in CHANGED_FIXTURE_IDS if fixture not in CARD_ERRATA_IDS
]
AF01_PATH = REPO_ROOT / "qualification/pre-freeze-successor/AF01_QUALIFICATION_BOUNDARY_V2.json"
AF_CATALOG_PATH = (
    REPO_ROOT / "qualification/pre-freeze-successor/architecture_freeze_gate_catalog_v2.json"
)
AF_SCHEMA_PATH = (
    REPO_ROOT / "qualification/pre-freeze-successor/architecture_freeze_contract_v2.schema.json"
)
MATERIALIZATION_SCHEMA_PATH = (
    REPO_ROOT / "qualification/pre-freeze-successor/SEMANTIC_FIXTURE_SCHEMA_v1_0_17_SUCCESSOR.json"
)
RULES_AUTHORITY_PATH = REPO_ROOT / "qualification/pre-freeze-successor/CURRENT_RULES_AUTHORITY.json"


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolver():
    path = REPO_ROOT / "scripts/resolve_pre_freeze_contract.py"
    spec = importlib.util.spec_from_file_location("pre_freeze_resolver", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_current_authority_preserves_history_and_lists_every_changed_fixture() -> None:
    authority = _json(AUTHORITY_PATH)
    assert authority["full107"]["denominator_count"] == 107
    assert authority["full107"]["changed_fixture_ids"] == CHANGED_FIXTURE_IDS
    assert authority["full107"]["unchanged_fixture_count"] == 107 - len(
        DENOMINATOR_CHANGED_FIXTURE_IDS
    )
    assert (
        authority["full107"]["evidence_survival"]["WS05-CMD-START-2"]
        == "REQUALIFICATION_REQUIRED_SEMANTIC_CHANGE"
    )
    assert (
        authority["full107"]["evidence_survival"]["MICRO_COSTS"]
        == "REQUALIFICATION_REQUIRED_FIXTURE_DEFECT_CORRECTION_CR_307_1"
    )
    assert (
        authority["full107"]["successor_contract"]
        == "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_17.json"
    )
    for fixture_id in HIDDEN_ERRATA_IDS:
        assert authority["full107"]["evidence_survival"][fixture_id] == (
            "REQUALIFICATION_REQUIRED_LOSSLESS_HIDDEN_STATE_ERRATUM_SLOT04"
        )
    # Every changed fixture needs requalification; none may inherit credit.
    for fixture_id in CHANGED_FIXTURE_IDS:
        assert authority["full107"]["evidence_survival"][fixture_id].startswith(
            "REQUALIFICATION_REQUIRED"
        )
    assert (
        authority["full107"]["evidence_migration"]["common_comparison_runtime_credit"]
        == "FRESH_CURRENT_BOUNDARY_EXECUTION_REQUIRED_ALL_107"
    )
    assert authority["full107"]["evidence_migration"]["automatic_carry_forward"] is False
    assert "PROVIDER_SELECTION" in authority["forbidden_claims"]
    assert "ARCHITECTURE_FREEZE" in authority["forbidden_claims"]

    base = REPO_ROOT / authority["full107"]["historical_base_materialization"]
    assert (
        hashlib.sha256(base.read_bytes()).hexdigest()
        == authority["full107"]["historical_base_sha256"]
    )


def test_start2_successor_matches_cr1038a_shape_and_new_digest() -> None:
    successor = _json(SUCCESSOR_PATH)
    patch = successor["record_successors"][0]
    assert patch["fixture_id"] == "WS05-CMD-START-2"
    assert successor["rules_authority"]["rule"] == "103.8a"
    assert patch["evidence_survival"] == "REQUALIFICATION_REQUIRED"

    resolver = _resolver()
    record = resolver.effective_record("WS05-CMD-START-2")
    assert record["temporal_state"] == {
        "turn_number": 1,
        "phase": "precombat_main",
        "step": "main",
        "active_player": "P1",
        "priority_player": "P1",
        "extra_turn_queue": [],
    }
    assert "first_turn_draw_step_skipped:true" in record["expected_events"]["required_events"]
    assert "draw_step_started:P1:turn1" in record["expected_events"]["forbidden_events"]
    assert "draw_step_draw:P1:turn1" in record["expected_events"]["forbidden_events"]
    assert record["requested_state_digest"] == patch["successor_requested_state_digest"]
    assert (
        resolver.requested_state_digest(record)
        == "bc01a714cbaa035d2f7954d4fd2dcabb63c391160f78774749ab50ab63fa4342"
    )
    assert "RSP" not in record["knowledge_state"]["channel_policy"]
    assert record["knowledge_state"]["channel_policy"].startswith(
        "Current candidate-neutral qualification-boundary"
    )
    for current_key in ("materialization_digest", "obligation_digest", "supersedes_record_digest"):
        assert current_key in record
    for historical_key in ("materialization_digest", "obligation_digest"):
        assert historical_key in record["historical_digests"]
    assert record["obligation_digest"] == resolver.obligation_digest(record)
    assert record["materialization_digest"] == resolver.materialization_digest(record)


def test_the_predecessor_successor_contract_is_preserved_byte_for_byte() -> None:
    """Historical overlays are provenance; the new contract supersedes them."""

    contract = _json(SUCCESSOR_PATH)
    predecessor = _json(PREDECESSOR_CONTRACT_PATH)
    assert contract["predecessor"]["path"].endswith("FULL107_SUCCESSOR_CONTRACT_v1_0_16.json")
    assert (
        contract["predecessor"]["sha256"]
        == hashlib.sha256(PREDECESSOR_CONTRACT_PATH.read_bytes()).hexdigest()
    )
    # Every predecessor overlay is carried over unchanged, in order, digests
    # included, except the rows whose lossless-library overlay now travels
    # inside a decision-script erratum (checked below).
    carried = contract["record_successors"][: len(predecessor["record_successors"])]
    assert [patch["fixture_id"] for patch in carried] == [
        patch["fixture_id"] for patch in predecessor["record_successors"]
    ]
    for new, old in zip(carried, predecessor["record_successors"], strict=True):
        if new["correction_class"] == old["correction_class"]:
            assert new == old
            continue
        # A lossless-library overlay now carried inside a decision-script erratum.
        assert new["fixture_id"] in CARRIED_LIBRARY_ERRATA_IDS
        assert old["correction_class"] == "LOSSLESS_LIBRARY_MATERIALIZATION_ERRATUM_SLOT04"
        assert new["replace"]["deck_state"] == old["replace"]["deck_state"]
        assert new["append_native_procedure"][0] == old["append_native_procedure"][0]
        assert (
            new["predecessor_requested_state_digest"] == old["predecessor_requested_state_digest"]
        )
    # The CR 103.8a patch still equals the 1.0.6 original.
    start2 = next(
        patch
        for patch in contract["record_successors"]
        if patch["fixture_id"] == "WS05-CMD-START-2"
    )
    original = _json(V106_CONTRACT_PATH)["record_successors"][0]
    assert start2 == {**original, "correction_class": "OFFICIAL_RULES_AUTHORITY_CORRECTION"}


def test_inside_cast_errata_reach_the_opening_cast_through_the_legal_action_domain() -> None:
    contract = _json(SUCCESSOR_PATH)
    resolver = _resolver()
    base_bundle = _json(
        REPO_ROOT / _json(AUTHORITY_PATH)["full107"]["historical_base_materialization"]
    )
    errata = {
        patch["fixture_id"]: patch
        for patch in contract["record_successors"]
        if patch.get("correction_class") == "FIXTURE_SCRIPT_CONTRACT_ERRATUM"
    }
    assert set(errata) == {
        "MICRO_MODES",
        "NEGATIVE_FIRST_OPTION",
        "NEGATIVE_GUI_DEFAULT",
        "NEGATIVE_RANDOM_OPTION",
        "NEGATIVE_SILENT_SKIP",
        "PILOT_TARGET_AMOUNT",
        "PILOT_MULTI_AMOUNT",
    }
    for fixture_id, patch in errata.items():
        record = resolver.effective_record(fixture_id)
        first = record["decision_script"][0]
        # The successor's first scripted step is an engine-offered cast; the
        # predecessor's first step (the inside-cast decision) is preserved after
        # it, so the intended obligation is unchanged.
        assert first["decision_family"] == "priority", fixture_id
        selection = first["selection"]
        assert selection["selector_kind"] == "semantic_action"
        assert selection["semantic_value"]["action"] == "cast"
        assert selection["matches_only_provider_offered_legal_options"] is True
        assert selection["on_zero_match"] == "FAIL_CLOSED"
        # The predecessor's own inside-cast step must survive at index 1. Compare
        # against the historical base record, not against the patch the resolver
        # just applied (which would be tautological).
        base_record = next(
            item for item in base_bundle["records"] if item["fixture_id"] == fixture_id
        )
        assert record["decision_script"][1:] == base_record["decision_script"]
        assert base_record["decision_script"][0]["decision_family"] != "priority"
        # The cast is payable only from the record's own explicit sources.
        assert record["action_cost_state"], fixture_id
        assert record["action_cost_state"][0]["payable"] is True
        assert record["action_cost_state"][0]["explicit_payment_sources"]
        assert record["repair_provenance"]["correction_class"] == (
            "FIXTURE_SCRIPT_CONTRACT_ERRATUM"
        )
        assert record["requested_state_digest"] == patch["successor_requested_state_digest"]
        assert record["requested_state_digest"] != patch["predecessor_requested_state_digest"]
        # The erratum is recorded on the record itself, and it explicitly
        # disclaims prose-derived action injection.
        erratum = record["native_procedure"][-1]
        assert erratum["operation"] == "FIXTURE_ERRATUM_RECORDED_BY_SUCCESSOR_CONTRACT"
        assert erratum["details"]["prose_derived_action_injection"] is False


def test_micro_costs_correction_makes_the_scripted_sorcery_legal_and_preserves_the_obligation() -> (
    None
):
    """CR 307.1: a sorcery needs its controller's own main phase."""

    resolver = _resolver()
    record = resolver.effective_record("MICRO_COSTS")
    assert record["temporal_state"] == {
        "active_player": "P2",
        "extra_turn_queue": [],
        "phase": "precombat_main",
        "priority_player": "P2",
        "step": "main",
        "turn_number": 1,
    }
    # The intended cost/interaction obligation is untouched: the scripted cast
    # and its target assignment, the required cost event and the postcondition
    # are the predecessor's.
    first = record["decision_script"][0]
    assert first["decision_family"] == "priority"
    assert first["selection"]["semantic_value"] == {
        "action": "cast",
        "object": "obj:micro-hex",
    }
    assert "cost_determined:base_plus_3_generic" in record["expected_events"]["required_events"]
    assert record["terminal_postconditions"] == [
        "Targeting two P1 commanders while Esior is controlled adds exactly {3} total, once."
    ]
    assert record["repair_provenance"]["correction_class"] == ("FIXTURE_DEFECT_CORRECTION_CR307_1")
    erratum = record["native_procedure"][-1]["details"]
    assert erratum["comprehensive_rules"] == "307.1"
    assert erratum["provider_semantics_used"] is False


def test_lane_rows_bound_to_corrected_fixtures_agree_with_the_records() -> None:
    """Every registered lane row must be executable against its own record.

    A lane spec that names a mana source the record does not place, or a cast
    object the record does not carry, would fail at run time for a harness
    reason rather than an engine reason. This is a static consistency check over
    the corrected fixtures; it proves nothing about engine behaviour.
    """

    from commander_lab.qualification.current_boundary import midgame_rows as mr

    resolver = _resolver()
    corrected = [
        fixture_id for fixture_id in CHANGED_FIXTURE_IDS if fixture_id != "WS05-CMD-START-2"
    ]
    for fixture_id in corrected:
        if fixture_id not in mr.ROWS:
            continue
        record = resolver.effective_record(fixture_id)
        semantic_ids = {str(o["semantic_id"]) for o in record["semantic_objects"]}
        spec = mr.ROWS[fixture_id]
        for source in spec.mana_sources:
            assert source in semantic_ids, (fixture_id, source)
        priority_steps = [
            step for step in record["decision_script"] if step["decision_family"] == "priority"
        ]
        assert priority_steps, fixture_id
        for step in priority_steps:
            target = step["selection"]["semantic_value"].get("object")
            if target is not None:
                assert target in semantic_ids, (fixture_id, target)


def test_the_materialization_receipt_names_every_corrected_fixture() -> None:
    """The receipt must agree with the authority, not with a hard-coded default.

    The effective manifest #255 reads advertised one corrected fixture while
    nine were in effect, because the receipt fell back to a literal whenever the
    bundle carried no changed set. The authority is the sole source.
    """

    from commander_lab.qualification.current_boundary.materialization import (
        load_effective_materialization,
    )

    authority = _json(AUTHORITY_PATH)
    materialization = load_effective_materialization(REPO_ROOT)
    receipt = materialization.receipt()
    assert receipt["changed_fixture_ids"] == authority["full107"]["changed_fixture_ids"]
    assert len(receipt["changed_fixture_ids"]) == len(CHANGED_FIXTURE_IDS)
    assert receipt["contract_id"] == "commander-lab.full107/1.0.17-successor"


def test_successor_overlay_does_not_mutate_other_records() -> None:
    authority = _json(AUTHORITY_PATH)
    base = _json(REPO_ROOT / authority["full107"]["historical_base_materialization"])
    effective = _resolver().load_effective_materialization()
    old = {record["fixture_id"]: record for record in base["records"]}
    new = {record["fixture_id"]: record for record in effective["records"]}

    assert (
        effective["schema_version"]
        == "commander-lab.semantic-fixture-materialization/1.0.17-successor"
    )
    assert effective["contract_id"] == "commander-lab.full107/1.0.17-successor"
    assert effective["protocol"] == base["protocol"]
    assert effective["protocol_role"] == "HISTORICAL_FIXTURE_ENCODING_PROVENANCE"
    assert effective["qualification_boundary"] == "commander-lab.pre-freeze-qualification/2.0.0"
    assert effective["common_fixture_manifest_sha256"] == base["common_fixture_manifest_sha256"]
    assert effective["historical_authority_lock"] == base["authority_lock"]
    assert effective["authority_lock"]["receipt_path"].endswith("CURRENT_RULES_AUTHORITY.json")
    assert (
        effective["supersedes"]["historical_canonical_bundle_digest"]
        == base["canonical_bundle_digest"]
    )
    assert effective["canonical_bundle_digest"] == _resolver().canonical_bundle_digest(effective)
    Draft202012Validator(_json(MATERIALIZATION_SCHEMA_PATH)).validate(effective)
    assert old.keys() == new.keys()
    for fixture_id in old:
        if fixture_id in CHANGED_FIXTURE_IDS:
            assert old[fixture_id] != new[fixture_id]
            # Lineage is preserved rather than rewritten: the predecessor's
            # digests survive under historical_digests and the successor names
            # the record it supersedes.
            assert (
                new[fixture_id]["supersedes_record_digest"]
                == old[fixture_id]["materialization_digest"]
            )
        else:
            assert old[fixture_id] == new[fixture_id]


def test_af01_uses_current_candidate_neutral_protocol_boundary() -> None:
    boundary = _json(AF01_PATH)
    config = _json(REPO_ROOT / "config/rules_engines.json")
    protocol_schema = _json(REPO_ROOT / "schemas/engine_adapter_protocol.schema.json")

    assert boundary["candidate_neutral"] is True
    assert boundary["transport"]["required_version"] == config["protocol_version"] == "2.0.0"
    assert protocol_schema["x-commander-lab-protocol-version"] == "2.0.0"
    assert boundary["required_handshake"]["messages"] == [
        "start_engine",
        "get_provider_version",
        "get_capabilities",
    ]
    assert (
        boundary["truthful_capability_requirements"][
            "client_may_not_infer_support_from_provider_name"
        ]
        is True
    )
    assert (
        boundary["rules_authority_invariants"]["adapter_or_pilot_legality_reconstruction_forbidden"]
        is True
    )
    assert boundary["fail_closed_invariants"][
        "unsupported_production_reachable_decision"
    ].startswith("TYPED_UNSUPPORTED")


def test_af_catalog_has_exact_required_gate_set_and_no_rsp11_af01_binding() -> None:
    catalog = _json(AF_CATALOG_PATH)
    ids = [gate["id"] for gate in catalog["gates"]]
    assert ids == [f"AF{i:02d}" for i in range(12)]
    assert all(gate["required"] is True for gate in catalog["gates"])
    af01 = next(gate for gate in catalog["gates"] if gate["id"] == "AF01")
    assert "RSP 1.1" not in af01["description"]
    assert "2.0.0" in af01["description"]
    assert catalog["qualification_boundary"] == "commander-lab.pre-freeze-qualification/2.0.0"


def test_freeze_schema_binds_current_boundary_without_claiming_freeze() -> None:
    schema = _json(AF_SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    props = schema["properties"]
    assert (
        props["qualification_boundary"]["const"] == "commander-lab.pre-freeze-qualification/2.0.0"
    )
    assert props["transport_protocol_version"]["const"] == "2.0.0"
    assert (
        props["protocol_schema_identity"]["const"]
        == "git-blob:ea8651f75a1461ecc41dc1f24586c00bff97fee5"
    )
    assert props["architecture_winner"]["const"] is False
    assert props["gate_results"]["minItems"] == props["gate_results"]["maxItems"] == 12
    assert "evidence_refs" in props["gate_results"]["items"]["required"]

    legacy = _json(
        REPO_ROOT / "qualification/protocol/ws10r/architecture_freeze_gate_catalog_v1.json"
    )
    assert legacy["protocol"] == "commander-lab.rules-service/1.1.0"


def _freeze_result(verdict: str = "PASS", freeze_eligible: bool = True) -> dict:
    return {
        "schema_version": "architecture-freeze-result/2.0.0",
        "architecture_winner": False,
        "candidate": "fixture-candidate",
        "qualification_boundary": "commander-lab.pre-freeze-qualification/2.0.0",
        "transport_protocol_version": "2.0.0",
        "protocol_schema_identity": "git-blob:ea8651f75a1461ecc41dc1f24586c00bff97fee5",
        "source_lock": {
            "provider_source": {
                "repository": "example/provider",
                "commit": "a" * 40,
                "tree": "b" * 40,
            },
            "adapter_source": {
                "repository": "example/adapter",
                "commit": "c" * 40,
                "tree": "d" * 40,
            },
            "build": {
                "artifact_identity": "candidate.jar",
                "artifact_sha256": "e" * 64,
            },
        },
        "truthful_capabilities": {
            "reported_by_provider": True,
            "runtime_kind": "external_rules_engine",
            "capabilities": {
                "commander_supported": True,
                "multiplayer_supported": True,
                "deck_import_supported": True,
                "legal_actions_supported": True,
                "action_submission_supported": True,
                "event_log_supported": True,
                "headless_supported": True,
                "seed_supported": True,
                "replay_supported": True,
                "game_shutdown_supported": True,
                "engine_shutdown_supported": True,
                "priority_visible": True,
                "stack_visible": True,
                "commander_tax_visible": True,
                "commander_damage_visible": True,
                "mulligan_supported": True,
                "target_selection_supported": True,
                "mode_selection_supported": True,
                "trigger_order_supported": True,
                "concede_supported": True,
                "starting_state_injection_supported": False,
                "scenario_injection_supported": False,
            },
            "required_capabilities": [
                "commander_supported",
                "multiplayer_supported",
                "deck_import_supported",
                "legal_actions_supported",
                "action_submission_supported",
                "event_log_supported",
                "headless_supported",
                "seed_supported",
                "replay_supported",
                "game_shutdown_supported",
                "engine_shutdown_supported",
            ],
            "missing_required_capabilities": [],
        },
        "gate_results": [
            {
                "gate_id": f"AF{i:02d}",
                "verdict": verdict,
                "reason": "test evidence",
                "evidence_refs": [f"artifact:AF{i:02d}"],
            }
            for i in range(12)
        ],
        "freeze_eligible": freeze_eligible,
    }


def test_freeze_schema_rejects_wrong_protocol_schema_identity() -> None:
    validator = Draft202012Validator(_json(AF_SCHEMA_PATH))
    invalid = _freeze_result()
    invalid["protocol_schema_identity"] = "git-blob:" + "0" * 40
    with pytest.raises(ValidationError):
        validator.validate(invalid)


def test_freeze_schema_requires_all_gate_ids_once_and_evidence_refs() -> None:
    validator = Draft202012Validator(_json(AF_SCHEMA_PATH))
    validator.validate(_freeze_result())

    duplicate = _freeze_result()
    duplicate["gate_results"][11]["gate_id"] = "AF10"
    with pytest.raises(ValidationError):
        validator.validate(duplicate)

    no_evidence = _freeze_result()
    no_evidence["gate_results"][0]["evidence_refs"] = []
    with pytest.raises(ValidationError):
        validator.validate(no_evidence)


def test_freeze_eligible_true_requires_all_pass() -> None:
    validator = Draft202012Validator(_json(AF_SCHEMA_PATH))
    invalid = _freeze_result()
    invalid["gate_results"][3]["verdict"] = "PARTIAL"
    with pytest.raises(ValidationError):
        validator.validate(invalid)

    not_eligible = _freeze_result(verdict="PARTIAL", freeze_eligible=False)
    validator.validate(not_eligible)


def test_current_rules_authority_binds_current_official_rules_page() -> None:
    """The receipt must bind the current official source byte-exactly.

    The subject of this test legitimately changed: the Coordinator adjudicated on
    2026-09-27 that the direct official 2026-09-25 capture supersedes the earlier
    2026-08-07 receipt. The protections are unchanged and are still asserted -
    fail-closed reproduction, an explicit supersession record that preserves the
    prior receipt rather than deleting it, and the claim that no blanket FULL107
    rerun is owed.
    """
    receipt = _json(RULES_AUTHORITY_PATH)
    successor = _json(SUCCESSOR_PATH)
    assert receipt["authority"] == "Wizards of the Coast (direct official capture)"
    assert receipt["authority_status"] == "CURRENT_OFFICIAL_SOURCE_DIRECTLY_VERIFIED"
    source = receipt["current_official_source"]
    assert source["resolved_official_txt_url"].endswith("MagicCompRules%2020260925.txt")
    assert source["effective_date"] == "2026-09-25"
    assert "September 25, 2026" in source["document_effective_date_text"]
    assert source["rule_103_8a_exact_text"].startswith("103.8a ")
    # Byte-exact identity is now claimed and must carry a real hash.
    assert source["byte_exact_sha256"] == (
        "8d860e451f20f38865b725b42d82feb714c725373dd8f3b32b8652b3eeb070ca"
    )
    assert source["byte_exact_status"] == "DIRECT_CAPTURE_AND_HASHED"
    assert source["official_txt_bytes"] == 977752
    # The capture was independently re-fetched and corroborated.
    reverified = source["independent_reverification"]
    assert reverified["effective_date_text_confirmed"] is True
    assert reverified["rule_103_8a_text_matches_capture_verbatim"] is True

    # The superseded receipt is recorded, not erased.
    supersedes = receipt["supersedes"]
    assert supersedes["effective_date"] == "2026-08-07"
    assert supersedes["disposition"] == "STALE_RECEIPT"
    assert supersedes["preserved_not_deleted"] is True
    assert "404" in supersedes["reason"]

    impact = receipt["rules_semantic_impact"]
    assert impact["FULL107_RUNTIME_EVIDENCE_INVALIDATED"] == "NO"
    assert impact["FULL107_BLANKET_RERUN_REQUIRED"] == "NO"
    assert receipt["reproduction"]["fail_closed_if_rules_page_target_changes"] is True
    assert receipt["reproduction"]["fail_closed_on_source_drift"] is True

    assert successor["rules_authority"]["current_authority_status"] == receipt["authority_status"]
    assert successor["rules_authority"]["semantic_basis_effective_date"] == "2026-09-25"
    # The byte-identity claim is now true and must agree with the receipt.
    assert successor["rules_authority"]["byte_identity_claim"] is True
    assert successor["rules_authority"]["byte_exact_sha256"] == source["byte_exact_sha256"]
    assert successor["rules_authority"]["freshness_conflict_resolved"] == "2026-09-27"


def test_freeze_schema_rejects_unbound_source_or_capabilities() -> None:
    validator = Draft202012Validator(_json(AF_SCHEMA_PATH))

    no_source = _freeze_result()
    no_source["source_lock"] = {}
    with pytest.raises(ValidationError):
        validator.validate(no_source)

    no_capabilities = _freeze_result()
    no_capabilities["truthful_capabilities"] = {}
    with pytest.raises(ValidationError):
        validator.validate(no_capabilities)

    missing_capability = _freeze_result()
    missing_capability["truthful_capabilities"]["missing_required_capabilities"] = [
        "legal_actions_supported"
    ]
    with pytest.raises(ValidationError):
        validator.validate(missing_capability)


def test_historical_full107_runtime_credit_is_not_automatically_promoted() -> None:
    authority = _json(AUTHORITY_PATH)
    migration = authority["full107"]["evidence_migration"]
    assert migration["protocol_boundary_changed"] is True
    assert migration["automatic_carry_forward"] is False
    assert migration["source_identity_alone_is_sufficient"] is False
    assert migration["impact_adjudication_required"] is True
    assert (
        migration["common_comparison_runtime_credit"]
        == "FRESH_CURRENT_BOUNDARY_EXECUTION_REQUIRED_ALL_107"
    )


def test_slot04_hidden_errata_make_the_hidden_state_lossless_without_changing_the_obligation() -> (
    None
):
    """#255 comment 5925956587: a partial library and an untyped face-down state
    fail closed, so the HIDDEN records are corrected and versioned.

    Each corrected record keeps every predecessor object and obligation; it gains
    exactly a typed face-down state and a complete checkpoint library and hands.
    """
    contract = _json(SUCCESSOR_PATH)
    resolver = _resolver()
    base = {
        record["fixture_id"]: record
        for record in _json(
            REPO_ROOT / _json(AUTHORITY_PATH)["full107"]["historical_base_materialization"]
        )["records"]
    }
    errata = {
        patch["fixture_id"]: patch
        for patch in contract["record_successors"]
        if patch.get("correction_class") == "LOSSLESS_HIDDEN_STATE_MATERIALIZATION_ERRATUM_SLOT04"
    }
    assert sorted(errata) == sorted(HIDDEN_ERRATA_IDS)
    for fixture_id in HIDDEN_ERRATA_IDS:
        record = resolver.effective_record(fixture_id)
        predecessor = base[fixture_id]
        # The obligation is untouched: its digest is the predecessor's.
        assert record["obligation_digest"] == predecessor["obligation_digest"]
        assert record["expected_events"] == predecessor["expected_events"]
        assert record["terminal_postconditions"] == predecessor["terminal_postconditions"]
        assert (
            record["knowledge_state"]["viewer_states"]
            == predecessor["knowledge_state"]["viewer_states"]
        )
        # The requested state changed, so its digest moved and lineage survives.
        assert record["requested_state_digest"] != predecessor["requested_state_digest"]
        assert record["requested_state_digest"] == resolver.requested_state_digest(record)
        assert record["supersedes_record_digest"] == predecessor["materialization_digest"]
        assert record["historical_digests"]["obligation_digest"] == predecessor["obligation_digest"]
        # Objects: exactly the predecessor's, the face-down one now typed.
        typed = [o for o in record["semantic_objects"] if o.get("face_down_type")]
        assert [(o["semantic_id"], o["face_down_type"]) for o in typed] == [
            ("obj:facedown", "MANIFESTED")
        ]
        untyped = [
            {k: v for k, v in o.items() if k != "face_down_type"}
            for o in record["semantic_objects"]
        ]
        assert untyped == predecessor["semantic_objects"]
        # Deck state: one complete entry per player, template remainder exact.
        decks = {deck["player_id"]: deck for deck in record["deck_state"]}
        assert sorted(decks) == ["P1", "P2", "P3", "P4"]
        hands = {pid: deck["checkpoint_hand"]["template_count"] for pid, deck in decks.items()}
        # P1 is the active player of a four-player table: rule 103.8a skips the
        # first draw only in a two-player game, so P1 holds 7 + 1.
        assert hands == {"P1": 8, "P2": 7, "P3": 7, "P4": 7}
        for deck in decks.values():
            assert deck["library_template"] == {"card_identity": "Mountain", "count": 99}
            assert deck["checkpoint_hand"]["completeness"] == "COMPLETE"
        library = decks["P2"]["checkpoint_library"]
        assert library["completeness"] == "COMPLETE_TOP_TO_BOTTOM"
        assert library["runs"] == [
            {"semantic_id": "obj:hidden-lib-0"},
            {"card_identity": "Mountain", "count": 99 - hands["P2"]},
        ]
        # No other player's library is declared: it holds template cards only.
        assert all("checkpoint_library" not in decks[pid] for pid in ("P1", "P3", "P4"))
        assert record["repair_provenance"]["correction_class"] == (
            "LOSSLESS_HIDDEN_STATE_MATERIALIZATION_ERRATUM_SLOT04"
        )
        erratum = record["native_procedure"][-1]
        assert erratum["operation"] == "FIXTURE_ERRATUM_RECORDED_BY_SUCCESSOR_CONTRACT"
        assert erratum["details"]["obligation_changed"] is False
        assert erratum["details"]["provider_semantics_used"] is False
        assert errata[fixture_id]["predecessor_invalidity"]["untyped_face_down_objects"] == [
            "obj:facedown"
        ]
        assert errata[fixture_id]["predecessor_invalidity"]["partial_library_objects"] == [
            "obj:hidden-lib-0"
        ]


def test_the_other_hidden_records_keep_their_predecessor_bytes() -> None:
    """The HIDDEN_05-18 rows without an event-scenario erratum yet keep their
    predecessor bytes, so they still fail closed on the lossless lane."""
    resolver = _resolver()
    base = {
        record["fixture_id"]: record
        for record in _json(
            REPO_ROOT / _json(AUTHORITY_PATH)["full107"]["historical_base_materialization"]
        )["records"]
    }
    for index in range(5, 19):
        fixture_id = f"HIDDEN_{index:02d}"
        if fixture_id in (
            *HIDDEN_EVENT_ERRATA_IDS,
            *LATE_HIDDEN_EVENT_ERRATA_IDS,
            *BATCH5_HIDDEN_EVENT_ERRATA_IDS,
            *BATCH6_HIDDEN_EVENT_ERRATA_IDS,
        ):
            continue
        assert fixture_id not in CHANGED_FIXTURE_IDS
        record = resolver.effective_record(fixture_id)
        assert record == base[fixture_id]
        assert "deck_state" not in record
        assert not any(o.get("face_down_type") for o in record["semantic_objects"])


def test_the_successor_schema_types_the_face_down_state_and_the_deck_state() -> None:
    schema = _json(MATERIALIZATION_SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    effective = _resolver().load_effective_materialization()
    validator = Draft202012Validator(schema)
    validator.validate(effective)

    def mutated(fixture_id: str, mutate) -> dict:  # type: ignore[no-untyped-def]
        candidate = json.loads(json.dumps(effective))
        record = next(r for r in candidate["records"] if r["fixture_id"] == fixture_id)
        mutate(record)
        return candidate

    def manual(record: dict) -> None:
        next(o for o in record["semantic_objects"] if o.get("face_down"))["face_down_type"] = (
            "MANUAL"
        )

    def typed_face_up(record: dict) -> None:
        exile = next(o for o in record["semantic_objects"] if o["zone"] == "exile")
        exile["face_down_type"] = "MANIFESTED"

    def partial(record: dict) -> None:
        deck = next(d for d in record["deck_state"] if "checkpoint_library" in d)
        deck["checkpoint_library"]["completeness"] = "PARTIAL"

    for mutation in (manual, typed_face_up, partial):
        with pytest.raises(ValidationError):
            validator.validate(mutated("HIDDEN_04", mutation))
    # The 1.0.7 schema does not know the lossless shapes at all.
    with pytest.raises(ValidationError):
        Draft202012Validator(
            _json(
                REPO_ROOT
                / "qualification/pre-freeze-successor/SEMANTIC_FIXTURE_SCHEMA_v1_0_7_SUCCESSOR.json"
            )
        ).validate(effective)


def test_hidden_event_errata_add_a_real_event_and_keep_the_obligation() -> None:
    """HIDDEN_07, 08, 09, 14, 17 and 18 name a reveal, a look, a search, a
    hidden target, a copy and a private look but no event that causes one. The successor adds the causing objects and a decision script
    that only selects engine offers; the obligation and the lossless base state
    are unchanged."""
    contract = _json(SUCCESSOR_PATH)
    resolver = _resolver()
    base = {
        record["fixture_id"]: record
        for record in _json(
            REPO_ROOT / _json(AUTHORITY_PATH)["full107"]["historical_base_materialization"]
        )["records"]
    }
    lossless = resolver.effective_record("HIDDEN_01")
    errata = {
        patch["fixture_id"]: patch
        for patch in contract["record_successors"]
        if patch.get("correction_class") == "HIDDEN_EVENT_SCENARIO_ERRATUM_SLOT04"
        and patch["fixture_id"] not in LATE_HIDDEN_EVENT_ERRATA_IDS
        and patch["fixture_id"] not in BATCH5_HIDDEN_EVENT_ERRATA_IDS
        and patch["fixture_id"] not in BATCH6_HIDDEN_EVENT_ERRATA_IDS
    }
    assert sorted(errata) == sorted(HIDDEN_EVENT_ERRATA_IDS)
    added = {
        "HIDDEN_07": {"obj:hidden07-telepathy": "Telepathy", "obj:hidden07-island": "Island"},
        "HIDDEN_08": {"obj:hidden08-spy": "Orcish Spy"},
        "HIDDEN_09": {
            "obj:hidden09-portal": "Planar Portal",
            **{f"obj:hidden09-island-{i}": "Island" for i in range(1, 7)},
        },
        "HIDDEN_14": {
            "obj:hidden14-mastery": "Mastery of the Unseen",
            **{f"obj:hidden14-plains-{i}": "Plains" for i in range(1, 5)},
            "obj:hidden14-pyromancer": "Prodigal Pyromancer",
        },
        "HIDDEN_17": {
            "obj:hidden17-mastery": "Mastery of the Unseen",
            **{f"obj:hidden17-plains-{i}": "Plains" for i in range(1, 5)},
            "obj:hidden17-image": "Phantasmal Image",
            "obj:hidden17-island-1": "Island",
            "obj:hidden17-island-2": "Island",
        },
        "HIDDEN_18": {"obj:hidden18-spy": "Orcish Spy"},
    }
    p2_owned = {
        *added["HIDDEN_09"],
        *(semantic_id for semantic_id in added["HIDDEN_14"] if "pyromancer" not in semantic_id),
        *(
            semantic_id
            for semantic_id in added["HIDDEN_17"]
            if "mastery" in semantic_id or "plains" in semantic_id
        ),
    }
    for fixture_id in HIDDEN_EVENT_ERRATA_IDS:
        record = resolver.effective_record(fixture_id)
        predecessor = base[fixture_id]
        assert record["obligation_digest"] == predecessor["obligation_digest"]
        assert record["expected_events"] == predecessor["expected_events"]
        assert (
            record["knowledge_state"]["viewer_states"]
            == predecessor["knowledge_state"]["viewer_states"]
        )
        assert predecessor["decision_script"] == []
        assert record["deck_state"] == lossless["deck_state"]
        objects = {o["semantic_id"]: o for o in record["semantic_objects"]}
        for semantic_id, card in added[fixture_id].items():
            assert objects[semantic_id]["card_identity"] == card
            assert objects[semantic_id]["owner"] == ("P2" if semantic_id in p2_owned else "P1")
        assert len(objects) == len(lossless["semantic_objects"]) + len(added[fixture_id])
        for step in record["decision_script"]:
            selection = step["selection"]
            assert selection["matches_only_provider_offered_legal_options"] is True
            assert selection["on_zero_match"] == selection["on_multiple_match"] == "FAIL_CLOSED"
        assert record["repair_provenance"]["correction_class"] == (
            "HIDDEN_EVENT_SCENARIO_ERRATUM_SLOT04"
        )
        erratum = record["native_procedure"][-1]["details"]
        assert erratum["obligation_changed"] is False
        assert erratum["prose_derived_action_injection"] is False


def test_card_library_errata_complete_the_library_and_keep_the_obligation() -> None:
    """CARD_09/12/15/27/29 name only the top library cards their obligation
    uses; under SLOT-04 a partial library fails closed, so the successor
    declares the complete checkpoint library and hands and changes nothing
    else. They are outside the provider denominator, which stays 107 rows."""
    contract = _json(SUCCESSOR_PATH)
    resolver = _resolver()
    base = {
        record["fixture_id"]: record
        for record in _json(
            REPO_ROOT / _json(AUTHORITY_PATH)["full107"]["historical_base_materialization"]
        )["records"]
    }
    denominator = set(
        _json(REPO_ROOT / "qualification/ws47/WS47_PROVIDER_DENOMINATOR_107.json")["fixture_ids"]
    )
    errata = {
        patch["fixture_id"]: patch
        for patch in contract["record_successors"]
        if patch.get("correction_class") == "LOSSLESS_LIBRARY_MATERIALIZATION_ERRATUM_SLOT04"
        or patch["fixture_id"] in CARRIED_LIBRARY_ERRATA_IDS
    }
    assert sorted(errata) == CARD_LIBRARY_ERRATA_IDS
    assert contract["change_accounting"]["unchanged_provider_denominator_rows"] == 107 - len(
        DENOMINATOR_CHANGED_FIXTURE_IDS
    )
    for fixture_id in CARD_LIBRARY_ERRATA_IDS:
        assert fixture_id not in denominator
        script_erratum = fixture_id in CARRIED_LIBRARY_ERRATA_IDS
        assert sorted(errata[fixture_id]["replace"]) == (
            ["decision_script", "deck_state"] if script_erratum else ["deck_state"]
        )
        record = resolver.effective_record(fixture_id)
        predecessor = base[fixture_id]
        assert record["obligation_digest"] == predecessor["obligation_digest"]
        assert record["semantic_objects"] == predecessor["semantic_objects"]
        if not script_erratum:
            assert record["decision_script"] == predecessor["decision_script"]
        library_objects = sorted(
            (o for o in predecessor["semantic_objects"] if o["zone"] == "library"),
            key=lambda o: o["zone_position"],
        )
        p1 = next(d for d in record["deck_state"] if d["player_id"] == "P1")
        runs = p1["checkpoint_library"]["runs"]
        assert p1["checkpoint_library"]["completeness"] == "COMPLETE_TOP_TO_BOTTOM"
        assert [run.get("semantic_id") for run in runs[:-1]] == [
            o["semantic_id"] for o in library_objects
        ]
        assert runs[-1] == {"card_identity": "Mountain", "count": 99 - 8}
        assert all(d["checkpoint_hand"]["completeness"] == "COMPLETE" for d in record["deck_state"])


def test_card_script_errata_answer_the_engine_asked_decisions_and_keep_the_obligation() -> None:
    """The AF07 decision-script errata only add, reorder or retype the steps
    that answer decisions the Rules Core itself asks; the obligation, the
    objects and the denominator stay as they were."""
    contract = _json(SUCCESSOR_PATH)
    resolver = _resolver()
    base = {
        record["fixture_id"]: record
        for record in _json(
            REPO_ROOT / _json(AUTHORITY_PATH)["full107"]["historical_base_materialization"]
        )["records"]
    }
    denominator = set(
        _json(REPO_ROOT / "qualification/ws47/WS47_PROVIDER_DENOMINATOR_107.json")["fixture_ids"]
    )
    errata = {
        patch["fixture_id"]: patch
        for patch in contract["record_successors"]
        if patch.get("correction_class") == "ACTUAL_CARD_DECISION_SCRIPT_ERRATUM"
    }
    assert sorted(errata) == sorted([*CARRIED_LIBRARY_ERRATA_IDS, *CARD_SCRIPT_ERRATA_IDS])
    for fixture_id, patch in errata.items():
        assert fixture_id not in denominator
        record = resolver.effective_record(fixture_id)
        predecessor = base[fixture_id]
        assert record["obligation_digest"] == predecessor["obligation_digest"]
        assert record["semantic_objects"] == predecessor["semantic_objects"]
        assert record["expected_events"] == predecessor["expected_events"]
        assert record["terminal_postconditions"] == predecessor["terminal_postconditions"]
        assert (
            patch["predecessor_invalidity"]["predecessor_decision_script"]
            == (predecessor["decision_script"])
        )
        assert set(patch["replace"]) <= {
            "decision_script",
            "action_cost_state",
            "deck_state",
            "temporal_state",
        }
        erratum = record["native_procedure"][-1]["details"]
        assert erratum["erratum_class"] == "ACTUAL_CARD_DECISION_SCRIPT_ERRATUM"
        assert erratum["obligation_changed"] is False
        assert erratum["prose_derived_action_injection"] is False
        objects = {o["semantic_id"] for o in record["semantic_objects"]}
        for step in record["decision_script"]:
            assert step["forbidden_fallbacks"]
            assert step["selection"]["on_multiple_match"] == "FAIL_CLOSED"
            value = step["selection"]["semantic_value"]
            named = (
                [value]
                if isinstance(value, str)
                else value
                if isinstance(value, list)
                else [value.get("object")]
                if isinstance(value, dict) and "object" in value
                else list(value)
                if isinstance(value, dict)
                else []
            )
            for item in named:
                if isinstance(item, str) and item.startswith("obj:"):
                    assert item in objects, (fixture_id, item)


def test_late_hidden_event_errata_add_a_scry_and_a_pile_split() -> None:
    """HIDDEN_10 (scry knowledge) and HIDDEN_13 (pile metadata) name a scry and
    piles but no event that makes them. The successor adds Magma Jet (scry 2)
    and Fact or Fiction on top of the lossless base, with P1's requested
    library top as complete checkpoint library runs. The obligation is
    unchanged; HIDDEN_13 declares the cast's legal reveal of the five cards."""
    contract = _json(SUCCESSOR_PATH)
    resolver = _resolver()
    base = {
        record["fixture_id"]: record
        for record in _json(
            REPO_ROOT / _json(AUTHORITY_PATH)["full107"]["historical_base_materialization"]
        )["records"]
    }
    lossless = resolver.effective_record("HIDDEN_01")
    patches = {
        patch["fixture_id"]: patch
        for patch in contract["record_successors"]
        if patch["fixture_id"] in LATE_HIDDEN_EVENT_ERRATA_IDS
    }
    assert sorted(patches) == sorted(LATE_HIDDEN_EVENT_ERRATA_IDS)
    expected_library = {
        "HIDDEN_10": ["Counterspell", "Brainstorm"],
        "HIDDEN_13": ["Counterspell", "Brainstorm", "Ponder", "Preordain", "Opt"],
    }
    for fixture_id in LATE_HIDDEN_EVENT_ERRATA_IDS:
        assert patches[fixture_id]["correction_class"] == "HIDDEN_EVENT_SCENARIO_ERRATUM_SLOT04"
        record = resolver.effective_record(fixture_id)
        predecessor = base[fixture_id]
        assert record["obligation_digest"] == predecessor["obligation_digest"]
        assert record["expected_events"] == predecessor["expected_events"]
        assert predecessor["decision_script"] == []
        objects = {o["semantic_id"]: o for o in record["semantic_objects"]}
        library = sorted(
            (o for o in objects.values() if o["zone"] == "library" and o["owner"] == "P1"),
            key=lambda o: o["zone_position"],
        )
        assert [o["card_identity"] for o in library] == expected_library[fixture_id]
        p1 = next(d for d in record["deck_state"] if d["player_id"] == "P1")
        runs = p1["checkpoint_library"]["runs"]
        assert [run.get("semantic_id") for run in runs[:-1]] == [o["semantic_id"] for o in library]
        assert runs[-1] == {"card_identity": "Mountain", "count": 99 - 8}
        others = [d for d in record["deck_state"] if d["player_id"] != "P1"]
        assert others == [d for d in lossless["deck_state"] if d["player_id"] != "P1"]
        state = record["knowledge_state"]["viewer_states"][0]
        old_state = predecessor["knowledge_state"]["viewer_states"][0]
        for key, value in old_state.items():
            if key != "temporary_permissions":
                assert state[key] == value, (fixture_id, key)
        for step in record["decision_script"]:
            assert step["selection"]["on_multiple_match"] == "FAIL_CLOSED"
    h13 = resolver.effective_record("HIDDEN_13")["knowledge_state"]["viewer_states"][0]
    assert h13["temporary_permissions"] == [
        {"object": f"obj:hidden13-lib-{i}", "permission": "reveal", "viewer": "ALL_PLAYERS"}
        for i in range(5)
    ]
    h10 = resolver.effective_record("HIDDEN_10")["knowledge_state"]["viewer_states"][0]
    assert h10["temporary_permissions"] == []
    assert h10["known_library_ranges"] == [
        {"count": 2, "ordered": True, "player": "P1", "start": 0, "viewer": "P1"}
    ]


def test_batch6_hidden11_adds_ordered_look_then_native_shuffle_without_changing_obligation() -> (
    None
):
    contract = _json(SUCCESSOR_PATH)
    predecessor = _json(PREDECESSOR_CONTRACT_PATH)
    resolver = _resolver()
    base = {
        record["fixture_id"]: record
        for record in _json(
            REPO_ROOT / _json(AUTHORITY_PATH)["full107"]["historical_base_materialization"]
        )["records"]
    }
    added = contract["record_successors"][len(predecessor["record_successors"]) :]
    assert [patch["fixture_id"] for patch in added] == BATCH6_HIDDEN_EVENT_ERRATA_IDS

    patch = added[0]
    assert patch["fixture_id"] == "HIDDEN_11"
    assert patch["correction_class"] == "HIDDEN_EVENT_SCENARIO_ERRATUM_SLOT04"
    assert patch["authority_overlay"]["comprehensive_rules_rule"] == "701.24a"
    assert patch["successor_requested_state_digest"] == (
        "d2310a2be374a3a6db5703d879a92dae3cfc9b7cd290183efb2ac2b288f4f5e6"
    )

    record = resolver.effective_record("HIDDEN_11")
    old = base["HIDDEN_11"]
    assert record["requested_state_digest"] == patch["successor_requested_state_digest"]
    assert record["obligation_digest"] == old["obligation_digest"]
    assert record["expected_events"] == old["expected_events"]
    assert record["terminal_postconditions"] == old["terminal_postconditions"]
    assert record["repair_provenance"]["correction_class"] == (
        "HIDDEN_EVENT_SCENARIO_ERRATUM_SLOT04"
    )

    viewer = record["knowledge_state"]["viewer_states"][0]
    assert viewer["obligation"] == "shuffle invalidates order knowledge"
    assert viewer["invalidation_conditions"] == ["P2 library shuffled"]
    assert viewer["known_library_ranges"] == [
        {
            "before_event": "shuffle",
            "count": 3,
            "ordered": True,
            "player": "P2",
            "start": 0,
            "viewer": "P1",
        }
    ]

    assert [step["causal_step_id"] for step in record["decision_script"]] == [
        "spy-look",
        "spy-target-p2",
        "elixir-shuffle",
    ]
    for step in record["decision_script"]:
        selection = step["selection"]
        assert selection["matches_only_provider_offered_legal_options"] is True
        assert selection["on_zero_match"] == selection["on_multiple_match"] == "FAIL_CLOSED"

    objects = {obj["semantic_id"]: obj for obj in record["semantic_objects"]}
    assert objects["obj:hidden11-spy"]["card_identity"] == "Orcish Spy"
    assert objects["obj:hidden11-elixir"]["card_identity"] == "Elixir of Immortality"
    assert [objects[f"obj:hidden11-lib-{i}"]["zone_position"] for i in (1, 2)] == [1, 2]

    p2 = next(deck for deck in record["deck_state"] if deck["player_id"] == "P2")
    assert p2["checkpoint_library"]["completeness"] == "COMPLETE_TOP_TO_BOTTOM"
    runs = p2["checkpoint_library"]["runs"]
    assert [run.get("semantic_id") for run in runs[:3]] == [
        "obj:hidden-lib-0",
        "obj:hidden11-lib-1",
        "obj:hidden11-lib-2",
    ]


def test_batch6_hidden06_and_hidden12_add_native_invalidation_and_control_routes() -> None:
    contract = _json(SUCCESSOR_PATH)
    predecessor = _json(PREDECESSOR_CONTRACT_PATH)
    resolver = _resolver()
    base = {
        record["fixture_id"]: record
        for record in _json(
            REPO_ROOT / _json(AUTHORITY_PATH)["full107"]["historical_base_materialization"]
        )["records"]
    }
    added = contract["record_successors"][len(predecessor["record_successors"]) :]
    by_id = {patch["fixture_id"]: patch for patch in added}
    assert list(by_id) == BATCH6_HIDDEN_EVENT_ERRATA_IDS

    expected_digests = {
        "HIDDEN_06": "6e76fe052384d35fde93725ac46e74b0f999e20d8fdfe5a19732a3d1d5225b00",
        "HIDDEN_12": "24c95853e7ec3e152c64d5d01835b51b90b75097daf4d66bdb2014915aaf17b6",
    }
    expected_steps = {
        "HIDDEN_06": [
            "cast-gonti",
            "gonti-target-opponent",
            "gonti-exile-face-down",
            "cast-exiled-card",
        ],
        "HIDDEN_12": ["activate-mindslaver", "mindslaver-target-p2"],
    }
    for fixture_id in ("HIDDEN_06", "HIDDEN_12"):
        patch = by_id[fixture_id]
        record = resolver.effective_record(fixture_id)
        old = base[fixture_id]
        assert old["decision_script"] == []
        assert patch["correction_class"] == "HIDDEN_EVENT_SCENARIO_ERRATUM_SLOT04"
        assert patch["successor_requested_state_digest"] == expected_digests[fixture_id]
        assert record["requested_state_digest"] == expected_digests[fixture_id]
        assert record["obligation_digest"] == old["obligation_digest"]
        assert record["expected_events"] == old["expected_events"]
        assert record["terminal_postconditions"] == old["terminal_postconditions"]
        assert record["knowledge_state"]["viewer_states"] == old["knowledge_state"]["viewer_states"]
        assert record["repair_provenance"]["correction_class"] == (
            "HIDDEN_EVENT_SCENARIO_ERRATUM_SLOT04"
        )
        assert [step["causal_step_id"] for step in record["decision_script"]] == (
            expected_steps[fixture_id]
        )
        for step in record["decision_script"]:
            selection = step["selection"]
            assert selection["matches_only_provider_offered_legal_options"] is True
            assert selection["on_zero_match"] == selection["on_multiple_match"] == "FAIL_CLOSED"
        p2 = next(deck for deck in record["deck_state"] if deck["player_id"] == "P2")
        assert p2["checkpoint_library"]["completeness"] == "COMPLETE_TOP_TO_BOTTOM"

    h06 = resolver.effective_record("HIDDEN_06")
    h06_objects = {obj["semantic_id"]: obj for obj in h06["semantic_objects"]}
    assert h06_objects["obj:hidden-hand"]["card_identity"] == "Memnite"
    assert h06_objects["obj:hidden-hand"]["zone"] == "library"
    assert h06_objects["obj:hidden-hand"]["zone_position"] == 0
    assert h06_objects["obj:hidden06-gonti"]["card_identity"] == "Gonti, Lord of Luxury"
    assert h06["knowledge_state"]["viewer_states"][0]["invalidation_conditions"] == [
        "object changes zone or becomes a new object"
    ]

    h12 = resolver.effective_record("HIDDEN_12")
    h12_objects = {obj["semantic_id"]: obj for obj in h12["semantic_objects"]}
    assert h12_objects["obj:hidden12-mindslaver"]["card_identity"] == "Mindslaver"
    assert h12_objects["obj:hidden12-p3-hand"]["owner"] == "P3"
    assert h12_objects["obj:hidden12-p3-hand"]["zone"] == "hand"
    assert h12["temporal_state"] == {
        "active_player": "P1",
        "extra_turn_queue": [],
        "phase": "postcombat_main",
        "priority_player": "P1",
        "step": "main",
        "turn_number": 1,
    }
    assert h12["knowledge_state"]["viewer_states"][0]["temporary_permissions"] == [
        {
            "controlled_player": "P2",
            "controller": "P1",
            "permission": "only information P1 is entitled to while making P2 decisions under rules",
        }
    ]
    details = h12["native_procedure"][-1]["details"]
    assert details["measurement_progression"] == (
        "ENGINE_OFFERED_PASS_PRIORITY_ONLY_UNTIL_FIRST_ACTING_FOR_FRAME_THEN_SUBMIT_ITS_EXACT_PASS"
    )


def test_batch5_hidden_event_errata_add_a_real_event_and_keep_the_obligation() -> None:
    """HIDDEN_05 (a persistent look at a face-down exiled card), HIDDEN_15 (source
    metadata) and HIDDEN_16 (ability metadata) name a hidden exile, source or
    ability, but no event ever makes one. The 1.0.16 successor adds the event on
    the lossless base; the obligation and the viewer state are unchanged."""
    contract = _json(PREDECESSOR_CONTRACT_PATH)
    predecessor = _json(V115_CONTRACT_PATH)
    resolver = _resolver()
    base = {
        record["fixture_id"]: record
        for record in _json(
            REPO_ROOT / _json(AUTHORITY_PATH)["full107"]["historical_base_materialization"]
        )["records"]
    }
    added = contract["record_successors"][len(predecessor["record_successors"]) :]
    assert [patch["fixture_id"] for patch in added] == BATCH5_HIDDEN_EVENT_ERRATA_IDS
    for patch in added:
        fixture_id = patch["fixture_id"]
        assert patch["correction_class"] == "HIDDEN_EVENT_SCENARIO_ERRATUM_SLOT04"
        record = resolver.effective_record(fixture_id)
        old = base[fixture_id]
        assert old["decision_script"] == []
        assert record["obligation_digest"] == old["obligation_digest"]
        assert record["expected_events"] == old["expected_events"]
        assert record["terminal_postconditions"] == old["terminal_postconditions"]
        assert record["knowledge_state"]["viewer_states"] == old["knowledge_state"]["viewer_states"]
        assert record["repair_provenance"]["correction_class"] == (
            "HIDDEN_EVENT_SCENARIO_ERRATUM_SLOT04"
        )
        erratum = record["native_procedure"][-1]["details"]
        assert erratum["obligation_changed"] is False
        assert erratum["prose_derived_action_injection"] is False
        for step in record["decision_script"]:
            selection = step["selection"]
            assert selection["matches_only_provider_offered_legal_options"] is True
            assert selection["on_zero_match"] == selection["on_multiple_match"] == "FAIL_CLOSED"
        objects = {o["semantic_id"]: o for o in record["semantic_objects"]}
        # The lossless base: a typed face-down state, complete libraries and hands.
        assert objects["obj:facedown"]["face_down_type"] == "MANIFESTED"
        assert not any(o.get("face_down") and not o.get("face_down_type") for o in objects.values())
        p2 = next(d for d in record["deck_state"] if d["player_id"] == "P2")
        runs = p2["checkpoint_library"]["runs"]
        assert p2["checkpoint_library"]["completeness"] == "COMPLETE_TOP_TO_BOTTOM"
        assert sum(1 if "semantic_id" in run else run["count"] for run in runs) == (
            p2["library_template"]["count"]
            - p2["checkpoint_hand"]["template_count"]
            + sum(1 for run in runs if "semantic_id" in run)
        )
    # HIDDEN_05: the honey-bound card is P2's library top, obj:hidden-lib-0 is fifth,
    # so P1's look at the top four never shows it; Gonti grants the look and P2's
    # Bolt removes Gonti before the look is measured.
    h05 = resolver.effective_record("HIDDEN_05")
    objects = {o["semantic_id"]: o for o in h05["semantic_objects"]}
    assert objects["obj:hidden-hand"]["zone"] == "library"
    assert objects["obj:hidden-hand"]["zone_position"] == 0
    assert objects["obj:hidden-hand"]["face_down"] is False
    assert objects["obj:hidden-lib-0"]["zone_position"] == 4
    assert [step["selection"]["semantic_value"] for step in h05["decision_script"]][2] == (
        "obj:hidden-hand"
    )
    assert objects["obj:hidden05-gonti"]["card_identity"] == "Gonti, Lord of Luxury"
    assert h05["decision_script"][-1]["selection"]["semantic_value"] == "obj:hidden05-gonti"
    state = h05["knowledge_state"]["viewer_states"][0]
    assert state["temporary_permissions"] == [
        {
            "object": "obj:hidden-hand",
            "permission": "look_at_face_down_exile",
            "persists_while_in_same_exile_object": True,
            "viewer": "P1",
        }
    ]
    # HIDDEN_15/16: Ransom Note cloaks P2's library top; only HIDDEN_16 declares
    # the hidden card's rules-text fragment for the ability-metadata scan.
    for fixture_id in ("HIDDEN_15", "HIDDEN_16"):
        record = resolver.effective_record(fixture_id)
        objects = {o["semantic_id"]: o for o in record["semantic_objects"]}
        tag = fixture_id.lower().replace("_", "")
        assert objects[f"obj:{tag}-note"]["card_identity"] == "Ransom Note"
        assert objects[f"obj:{tag}-note"]["controller"] == "P2"
        assert [step["decision_family"] for step in record["decision_script"]] == [
            "priority",
            "choose_mode",
            "priority",
            "target",
            "choose_use",
        ]
        notes = objects["obj:hidden-lib-0"].get("construction_notes") or []
        texts = [note for note in notes if note.startswith("oracle_ability_text:")]
        assert texts == (
            ["oracle_ability_text:then shuffle and put that card on top"]
            if fixture_id == "HIDDEN_16"
            else []
        )
