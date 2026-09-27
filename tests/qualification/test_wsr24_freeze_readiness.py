"""WSR24 freeze-readiness validators.

Guards the Architecture Freeze decision packet
(``docs/architecture_freeze_readiness_20260927/``) against the failure modes
that matter: missing gates, non-PASS promotion, missing capabilities, silent
provider defaults, asymmetric candidate packets, reconciled-count drift, and
ADR-template gaps.

Every test reads the committed artifacts (plus the live gate catalog/schema);
nothing here re-runs qualification or invents evidence.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from commander_lab.freeze_readiness import (
    NON_PASS_VERDICTS,
    REQUIRED_CAPABILITIES,
    REQUIRED_GATES,
    check_freeze_eligibility,
    find_banned_keys,
    packet_shape,
    validate_readiness_packet,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
READY_DIR = REPO_ROOT / "docs" / "architecture_freeze_readiness_20260927"
CATALOG_PATH = (
    REPO_ROOT
    / "qualification"
    / "pre-freeze-successor"
    / "architecture_freeze_gate_catalog_v2.json"
)
SCHEMA_PATH = (
    REPO_ROOT
    / "qualification"
    / "pre-freeze-successor"
    / "architecture_freeze_contract_v2.schema.json"
)

ALL_PASS_GATES = [
    {"gate_id": gid, "verdict": "PASS", "reason": "r", "evidence_refs": ["e"]}
    for gid in REQUIRED_GATES
]
FULL_CAPS = {cap: True for cap in REQUIRED_CAPABILITIES}


def _load(name: str) -> dict:
    return json.loads((READY_DIR / name).read_text())


# --------------------------------------------------------------------------
# 1. Gate catalog / schema semantics (live files, never approximated)
# --------------------------------------------------------------------------


def test_gate_catalog_has_exactly_12_required_af_gates():
    catalog = json.loads(CATALOG_PATH.read_text())
    gates = catalog["gates"]
    assert [g["id"] for g in gates] == REQUIRED_GATES
    assert all(g["required"] is True for g in gates)


def test_schema_requires_12_gates_and_all_pass_conditional():
    schema = json.loads(SCHEMA_PATH.read_text())
    gate_results = schema["properties"]["gate_results"]
    assert gate_results["minItems"] == 12
    assert gate_results["maxItems"] == 12
    # Every AF00-AF11 id must appear in the allOf contains clauses.
    allof_text = json.dumps(schema["allOf"])
    for gid in REQUIRED_GATES:
        assert f'"const": "AF{gid[2:]}"' in allof_text or f'"const": "{gid}"' in allof_text
    # The freeze_eligible=true conditional must demand all-PASS verdicts,
    # empty missing_required_capabilities, and the 11 required flags true.
    conditional = schema["allOf"][-1]
    assert conditional["if"] == {
        "properties": {"freeze_eligible": {"const": True}},
        "required": ["freeze_eligible"],
    }
    then_text = json.dumps(conditional["then"])
    assert '"const": "PASS"' in then_text
    assert '"maxItems": 0' in then_text
    for cap in REQUIRED_CAPABILITIES:
        assert '"const": true' in then_text
        assert cap in then_text


# --------------------------------------------------------------------------
# 2. Eligibility function: happy path + adversarial negatives
# --------------------------------------------------------------------------


def test_eligibility_happy_path_all_pass_full_caps():
    eligible, reasons = check_freeze_eligibility(ALL_PASS_GATES, dict(FULL_CAPS), [])
    assert eligible is True
    assert reasons == []


def test_eligibility_missing_gate_prevents():
    gates = [g for g in ALL_PASS_GATES if g["gate_id"] != "AF07"]
    eligible, reasons = check_freeze_eligibility(gates, dict(FULL_CAPS), [])
    assert eligible is False
    assert any("AF07" in r and "missing" in r for r in reasons)


def test_eligibility_duplicate_gate_prevents():
    gates = [*ALL_PASS_GATES, dict(ALL_PASS_GATES[0])]
    eligible, reasons = check_freeze_eligibility(gates, dict(FULL_CAPS), [])
    assert eligible is False
    assert any("duplicat" in r for r in reasons)


def test_eligibility_unknown_gate_id_prevents():
    gates = [dict(g) for g in ALL_PASS_GATES]
    gates[0] = {"gate_id": "AF12", "verdict": "PASS", "reason": "r", "evidence_refs": ["e"]}
    eligible, reasons = check_freeze_eligibility(gates, dict(FULL_CAPS), [])
    assert eligible is False
    assert any("AF12" in r for r in reasons)


@pytest.mark.parametrize("verdict", list(NON_PASS_VERDICTS))
def test_eligibility_each_non_pass_verdict_prevents(verdict):
    gates = [dict(g) for g in ALL_PASS_GATES]
    gates[3] = {"gate_id": "AF03", "verdict": verdict, "reason": "r", "evidence_refs": ["e"]}
    eligible, reasons = check_freeze_eligibility(gates, dict(FULL_CAPS), [])
    assert eligible is False
    assert any("AF03" in r for r in reasons)


def test_eligibility_missing_required_capability_prevents():
    caps = dict(FULL_CAPS)
    del caps["legal_actions_supported"]
    eligible, reasons = check_freeze_eligibility(ALL_PASS_GATES, caps, [])
    assert eligible is False
    assert any("legal_actions_supported" in r for r in reasons)


def test_eligibility_false_capability_prevents():
    caps = dict(FULL_CAPS)
    caps["replay_supported"] = False
    eligible, reasons = check_freeze_eligibility(ALL_PASS_GATES, caps, [])
    assert eligible is False
    assert any("replay_supported" in r for r in reasons)


def test_eligibility_nonempty_missing_list_prevents():
    eligible, reasons = check_freeze_eligibility(
        ALL_PASS_GATES, dict(FULL_CAPS), ["seed_supported"]
    )
    assert eligible is False
    assert any("non-empty" in r for r in reasons)


def test_eligibility_empty_gate_results_prevents():
    eligible, reasons = check_freeze_eligibility([], dict(FULL_CAPS), [])
    assert eligible is False
    assert any("missing required gate AF00" in r for r in reasons)


def test_eligibility_empty_reason_or_refs_is_flagged():
    gates = [dict(g) for g in ALL_PASS_GATES]
    gates[0] = {"gate_id": "AF00", "verdict": "PASS", "reason": "", "evidence_refs": []}
    eligible, reasons = check_freeze_eligibility(gates, dict(FULL_CAPS), [])
    assert eligible is False
    assert any("empty reason" in r for r in reasons)
    assert any("empty evidence_refs" in r for r in reasons)


# --------------------------------------------------------------------------
# 3. Readiness packets: structure, verdicts, honesty, symmetry
# --------------------------------------------------------------------------


def _xmage():
    return _load("XMAGE_FREEZE_READINESS.json")


def _forge():
    return _load("FORGE_FREEZE_READINESS.json")


def test_readiness_packets_have_12_gates_exactly_once():
    for packet in (_xmage(), _forge()):
        assert validate_readiness_packet(packet) == []
        gates = packet["gates"]
        assert len(gates) == 12
        assert sorted(g["gate"] for g in gates) == REQUIRED_GATES


def test_readiness_packets_match_wsr22_verdicts():
    xmage = {g["gate"]: g["current_verdict"] for g in _xmage()["gates"]}
    forge = {g["gate"]: g["current_verdict"] for g in _forge()["gates"]}
    assert xmage == {
        "AF00": "PASS",
        "AF01": "UNKNOWN",
        "AF02": "PASS",
        "AF03": "PASS",
        "AF04": "FAIL",
        "AF05": "UNKNOWN",
        "AF06": "UNKNOWN",
        "AF07": "UNKNOWN",
        "AF08": "UNKNOWN",
        "AF09": "UNKNOWN",
        "AF10": "PASS",
        "AF11": "FAIL",
    }
    assert forge == {
        "AF00": "PASS",
        "AF01": "PASS",
        "AF02": "PASS",
        "AF03": "PASS",
        "AF04": "UNKNOWN",
        "AF05": "UNKNOWN",
        "AF06": "UNKNOWN",
        "AF07": "UNKNOWN",
        "AF08": "UNKNOWN",
        "AF09": "UNKNOWN",
        "AF10": "PASS",
        "AF11": "FAIL",
    }


def test_readiness_packets_claim_no_eligibility_and_name_real_preventers():
    for packet in (_xmage(), _forge()):
        elig = packet["freeze_eligibility"]
        assert elig["freeze_eligible"] is False
        assert len(elig["prevented_by"]) >= 1
        verdicts = {g["gate"]: g["current_verdict"] for g in packet["gates"]}
        non_pass = {gid for gid, v in verdicts.items() if v != "PASS"}
        joined = " ".join(elig["prevented_by"])
        for gid in non_pass:
            assert gid in joined, f"{gid} is non-PASS but unnamed in prevented_by"


def test_readiness_packets_are_structurally_symmetric():
    assert packet_shape(_xmage()) == packet_shape(_forge())


def test_no_ranking_or_winner_keys_in_machine_packets():
    for name in (
        "WSR22_EVIDENCE_INGEST.json",
        "XMAGE_FREEZE_READINESS.json",
        "FORGE_FREEZE_READINESS.json",
        "FREEZE_GATE_BINDING_MAP.json",
        "SOURCE_LOCK.json",
    ):
        hits = find_banned_keys(_load(name))
        assert hits == [], f"{name} contains banned keys: {hits}"


def test_no_freeze_eligible_true_anywhere_in_wsr24_json():
    for path in READY_DIR.glob("*.json"):
        text = path.read_text()
        assert '"freeze_eligible": true' not in text, f"{path.name} claims eligibility"


def test_no_default_provider_in_wsr24_artifacts():
    source_lock = _load("SOURCE_LOCK.json")
    assert source_lock["production_provider"] == "NOT SELECTED"
    assert source_lock["architecture_freeze"] == "NOT CLAIMED"
    for packet in (_xmage(), _forge()):
        assert packet["candidate"] in ("xmage", "forge")
        assert "no_ranking" in packet
    slots = (READY_DIR / "COORDINATOR_DECISION_SLOTS.md").read_text()
    assert "SLOT-01" in slots  # provider selection stays a Coordinator slot


# --------------------------------------------------------------------------
# 4. Count reconciliation (107 everywhere; blockers 0/4/4)
# --------------------------------------------------------------------------


def test_full107_counts_reconcile_to_107_each():
    ingest = _load("WSR22_EVIDENCE_INGEST.json")
    for candidate in ("xmage", "forge"):
        counts = ingest["full107_counts"][candidate]
        parts = ["PASS", "FAIL", "UNKNOWN", "BLOCKED", "CRASH", "TIMEOUT", "PROTOCOL_FAILURE"]
        assert sum(counts[p] for p in parts) == 107 == counts["TOTAL"]


def test_full107_counts_match_dispatched_values():
    ingest = _load("WSR22_EVIDENCE_INGEST.json")
    assert ingest["full107_counts"]["xmage"]["PASS"] == 30
    assert ingest["full107_counts"]["xmage"]["UNKNOWN"] == 44
    assert ingest["full107_counts"]["xmage"]["BLOCKED"] == 33
    assert ingest["full107_counts"]["xmage"]["FAIL"] == 0
    assert ingest["full107_counts"]["forge"]["PASS"] == 79
    assert ingest["full107_counts"]["forge"]["UNKNOWN"] == 21
    assert ingest["full107_counts"]["forge"]["BLOCKED"] == 7
    assert ingest["full107_counts"]["forge"]["FAIL"] == 0


def test_native_promotions_never_exceed_pass():
    ingest = _load("WSR22_EVIDENCE_INGEST.json")
    for candidate in ("xmage", "forge"):
        counts = ingest["full107_counts"][candidate]
        assert counts["native_promotions"] <= counts["PASS"]
    assert ingest["evidence_class"] == "FRESH_CURRENT_BOUNDARY_EXECUTION"


def test_comparison_totals_reconcile_to_107():
    ingest = _load("WSR22_EVIDENCE_INGEST.json")
    comp = ingest["comparison"]["dispositions"]
    assert comp["SAME_SEMANTICS"] == 25
    assert comp["NON_COMPARABLE"] == 82
    assert comp["SAME_SEMANTICS"] + comp["NON_COMPARABLE"] == 107
    assert ingest["denominator_reconciliation"] == {
        "xmage_full107_total": 107,
        "forge_full107_total": 107,
        "comparison_total": 107,
    }


def test_blocker_counts_reconcile_to_source_register():
    ingest = _load("WSR22_EVIDENCE_INGEST.json")
    blockers = ingest["provider_blockers"]
    assert blockers["counts"] == {
        "PROVIDER_BLOCKING": 0,
        "BOUNDED_NON_BLOCKING": 4,
        "UNKNOWN_IMPACT": 4,
    }
    assert sorted(blockers["ids"]["BOUNDED_NON_BLOCKING"]) == ["PB-01", "PB-02", "PB-04", "PB-05"]
    assert sorted(blockers["ids"]["UNKNOWN_IMPACT"]) == ["PB-03", "PB-06", "PB-07", "PB-08"]
    assert ingest["divergence"]["count"] == 0
    assert ingest["divergence"]["ruled_visible_divergences"] == []


# --------------------------------------------------------------------------
# 5. Binding map + ADR template + DAGs + decision slots
# --------------------------------------------------------------------------


def test_binding_map_covers_all_12_gates_exactly_once():
    binding = _load("FREEZE_GATE_BINDING_MAP.json")
    assert sorted(b["gate"] for b in binding["bindings"]) == REQUIRED_GATES
    summary = binding["freeze_eligibility_summary"]
    assert "NOT ELIGIBLE" in summary["xmage"]
    assert "NOT ELIGIBLE" in summary["forge"]


ADR_FIELDS = [
    "RULES_CORE",
    "PRODUCTION_PROVIDER",
    "ENGINE_REPOSITORY",
    "ENGINE_COMMIT",
    "ENGINE_TREE",
    "ENGINE_BUILD_ARTIFACT",
    "ENGINE_BUILD_SHA256",
    "PROTOCOL_VERSION",
    "PROTOCOL_SCHEMA_IDENTITY",
    "BRIDGE_ARCHITECTURE",
    "PROCESS_TOPOLOGY",
    "PLAYER_COUNTS_SUPPORTED",
    "PLAYER_COUNTS_FAIL_CLOSED",
    "HIDDEN_INFORMATION_MODEL",
    "OBSERVATION_CONTRACT",
    "LEGAL_ACTION_CONTRACT",
    "DECISION_CONTRACT",
    "TARGET/MODE/CHOICE CONTRACT",
    "RULES_RNG_CONTRACT",
    "SEMANTIC_REPLAY_CONTRACT",
    "FAILURE_SEMANTICS",
    "PROCESS_ISOLATION",
    "ACTUAL_CARD_QUALIFICATION_BOUNDARY",
    "MULTIPLAYER_COMMANDER_BOUNDARY",
    "INTEROP_LICENSE_TOPOLOGY",
    "SOURCE_LOCK",
    "SUPPORTED_PATHS",
    "UNSUPPORTED_PATHS",
    "KNOWN_BOUNDED_LIMITATIONS",
    "QUALIFICATION_EVIDENCE",
    "AF00_AF11_RESULTS",
    "FREEZE_ELIGIBILITY",
]


def test_adr_template_contains_every_mandatory_field():
    text = (READY_DIR / "ARCHITECTURE_FREEZE_ADR_TEMPLATE.md").read_text()
    for field in ADR_FIELDS:
        assert field in text, f"ADR template missing {field}"
    assert "COORDINATOR-FILL" in text
    # The only CLAIMED occurrence must be the checklist fill-task, never a claim.
    claimed_lines = [line for line in text.splitlines() if "ARCHITECTURE_FREEZE = CLAIMED" in line]
    assert len(claimed_lines) == 1
    assert claimed_lines[0].lstrip().startswith("- [ ]")


def _normalize_dag_headers(headers: list[str]) -> list[str]:
    normalized = []
    for h in headers:
        h = h.replace("XMAGE", "CAND").replace("FORGE", "CAND")
        h = h.replace("xmage", "cand").replace("forge", "cand")
        normalized.append(h)
    return normalized


def test_remediation_dags_are_structurally_symmetric():
    def headers(name: str) -> list[str]:
        return [
            line for line in (READY_DIR / name).read_text().splitlines() if line.startswith("## ")
        ]

    xmage_h = _normalize_dag_headers(headers("REMEDIATION_DAG_XMAGE.md"))
    forge_h = _normalize_dag_headers(headers("REMEDIATION_DAG_FORGE.md"))
    assert xmage_h == forge_h
    for name in ("REMEDIATION_DAG_XMAGE.md", "REMEDIATION_DAG_FORGE.md"):
        text = (READY_DIR / name).read_text()
        assert "CONDITIONAL, NOT selected" in text
        assert "no recommendation" in text


def test_decision_slots_have_required_anatomy_and_no_winner():
    text = (READY_DIR / "COORDINATOR_DECISION_SLOTS.md").read_text()
    slots = re.findall(r"^## SLOT-(\d+)", text, flags=re.M)
    assert len(slots) == 10
    for required in (
        "QUESTION",
        "WHY_COORDINATOR_AUTHORITY",
        "EXACT_EVIDENCE",
        "AVAILABLE_OPTIONS",
        "TECHNICAL_CONSEQUENCE",
    ):
        assert text.count(required) >= 10, f"missing anatomy header {required}"
    assert "No slot names a recommended winner" in text
    assert "NO RECOMMENDED WINNER" in text
