from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_PATH = REPO_ROOT / "qualification/CURRENT_PRE_FREEZE_CONTRACT.json"
SUCCESSOR_PATH = (
    REPO_ROOT
    / "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_6.json"
)
AF01_PATH = REPO_ROOT / "qualification/pre-freeze-successor/AF01_QUALIFICATION_BOUNDARY_V2.json"
AF_CATALOG_PATH = (
    REPO_ROOT / "qualification/pre-freeze-successor/architecture_freeze_gate_catalog_v2.json"
)
AF_SCHEMA_PATH = (
    REPO_ROOT / "qualification/pre-freeze-successor/architecture_freeze_contract_v2.schema.json"
)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolver():
    path = REPO_ROOT / "scripts/resolve_pre_freeze_contract.py"
    spec = importlib.util.spec_from_file_location("pre_freeze_resolver", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_current_authority_preserves_history_and_changes_only_start2() -> None:
    authority = _json(AUTHORITY_PATH)
    assert authority["full107"]["denominator_count"] == 107
    assert authority["full107"]["changed_fixture_ids"] == ["WS05-CMD-START-2"]
    assert authority["full107"]["unchanged_fixture_count"] == 106
    assert authority["full107"]["evidence_survival"]["WS05-CMD-START-2"] == "REQUALIFICATION_REQUIRED"
    assert "PROVIDER_SELECTION" in authority["forbidden_claims"]
    assert "ARCHITECTURE_FREEZE" in authority["forbidden_claims"]

    base = REPO_ROOT / authority["full107"]["historical_base_materialization"]
    assert hashlib.sha256(base.read_bytes()).hexdigest() == authority["full107"]["historical_base_sha256"]


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
    assert resolver.requested_state_digest(record) == "bc01a714cbaa035d2f7954d4fd2dcabb63c391160f78774749ab50ab63fa4342"
    assert "RSP" not in record["knowledge_state"]["channel_policy"]
    assert record["knowledge_state"]["channel_policy"].startswith(
        "Current candidate-neutral qualification-boundary"
    )
    for stale_key in ("materialization_digest", "obligation_digest", "supersedes_record_digest"):
        assert stale_key not in record
        assert stale_key in record["historical_digests"]


def test_successor_overlay_does_not_mutate_other_records() -> None:
    authority = _json(AUTHORITY_PATH)
    base = _json(REPO_ROOT / authority["full107"]["historical_base_materialization"])
    effective = _resolver().load_effective_materialization()
    old = {record["fixture_id"]: record for record in base["records"]}
    new = {record["fixture_id"]: record for record in effective["records"]}
    assert old.keys() == new.keys()
    for fixture_id in old:
        if fixture_id == "WS05-CMD-START-2":
            assert old[fixture_id] != new[fixture_id]
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
    assert boundary["truthful_capability_requirements"]["client_may_not_infer_support_from_provider_name"] is True
    assert boundary["rules_authority_invariants"]["adapter_or_pilot_legality_reconstruction_forbidden"] is True
    assert boundary["fail_closed_invariants"]["unsupported_production_reachable_decision"].startswith("TYPED_UNSUPPORTED")


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
    props = schema["properties"]
    assert props["qualification_boundary"]["const"] == "commander-lab.pre-freeze-qualification/2.0.0"
    assert props["transport_protocol_version"]["const"] == "2.0.0"
    assert props["af_results"]["minItems"] == props["af_results"]["maxItems"] == 12

    legacy = _json(REPO_ROOT / "qualification/protocol/ws10r/architecture_freeze_gate_catalog_v1.json")
    assert legacy["protocol"] == "commander-lab.rules-service/1.1.0"
