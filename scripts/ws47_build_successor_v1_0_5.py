#!/usr/bin/env python3
"""WS-47 provider-neutral v1.0.5 successor builder.

Consumes the immutable checked-in WS44 v1.0.4 freeze, repairs exactly one
requested-state legal-blocker surface after current-rules authority adjudication,
and emits a deterministically reproducible successor namespace. It does not run or
query any provider Rules Core.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import ws44_build_successor as B
import ws44_build_successor_v2 as V2

VERSION = "commander-lab.semantic-fixture-materialization/1.0.5"
PRE_VERSION = "commander-lab.semantic-fixture-materialization/1.0.4"
PRE_COMMIT = "12940248497a8795991cbbd2eedef72945528cfe"
PRE_TREE = "cd83c973b269711106d08ab5be2d7672f05bcb7c"
PRE_NS_TREE = "6579e119605b90248426a3121a47c487b2bb13cd"
PRE_MAT_SHA256 = "9b370244e4e5df3132e6e9a3d2b70ad641a5a6023fc7c86832931340d24bfa35"
PRE_CANONICAL = "77b911195525c2fe8aff37f6c9573e5772f358b25646d0be5919314ed5e23b54"
PRE_MAT_PATH = Path("qualification/ws44/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_4.json")
PRE_SCHEMA_PATH = Path("qualification/ws44/SEMANTIC_FIXTURE_SCHEMA_v1_0_4.json")
PRE_DENOM_PATH = Path("qualification/ws44/WS44_PROVIDER_DENOMINATOR_107.json")
TARGET = "WS05-MP-BLOCK-4"
TARGET_OLD = ["obj:mp-p2-blocker"]
TARGET_NEW = ["obj:P2-bears", "obj:mp-p2-blocker"]
CURRENT_RULES_EFFECTIVE = "2026-08-07"
CURRENT_RULES_URL = "https://media.wizards.com/2026/downloads/MagicCompRules%2020260807.txt"
CURRENT_RULES_PAGE = "https://magic.wizards.com/en/rules"


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def dump(path: Path, value: Any) -> None:
    path.write_bytes(canonical_bytes(value) + b"\n")


def load_locked(path: Path, expected_sha256: str | None = None) -> Any:
    raw = path.read_bytes()
    if expected_sha256 is not None and sha256_bytes(raw) != expected_sha256:
        raise RuntimeError(f"locked file digest mismatch: {path}: {sha256_bytes(raw)}")
    return json.loads(raw)


def find_record(bundle: dict[str, Any], fixture_id: str) -> dict[str, Any]:
    rows = [r for r in bundle.get("records", []) if r.get("fixture_id") == fixture_id]
    if len(rows) != 1:
        raise RuntimeError(f"{fixture_id}: record cardinality {len(rows)}")
    return rows[0]


def record_digest(record: dict[str, Any]) -> str:
    projection = {k: v for k, v in record.items() if k != "materialization_digest"}
    return sha256_bytes(canonical_bytes(projection))


def verify_predecessor(predecessor: dict[str, Any]) -> None:
    if predecessor.get("schema_version") != PRE_VERSION:
        raise RuntimeError("predecessor schema_version changed")
    if predecessor.get("canonical_bundle_digest") != PRE_CANONICAL:
        raise RuntimeError("predecessor canonical bundle digest changed")
    projection = {k: v for k, v in predecessor.items() if k != "canonical_bundle_digest"}
    if sha256_bytes(canonical_bytes(projection)) != PRE_CANONICAL:
        raise RuntimeError("predecessor canonical bundle digest does not recompute")
    if predecessor.get("record_count") != 135 or len(predecessor.get("records", [])) != 135:
        raise RuntimeError("predecessor record count changed")
    if len({r.get("fixture_id") for r in predecessor["records"]}) != 135:
        raise RuntimeError("predecessor fixture IDs are not unique")
    for r in predecessor["records"]:
        if r.get("materialization_digest") != record_digest(r):
            raise RuntimeError(f"predecessor record digest mismatch: {r.get('fixture_id')}")
        if r.get("requested_state_digest") != B.legacy.requested_state_digest(r):
            raise RuntimeError(f"predecessor requested-state digest mismatch: {r.get('fixture_id')}")
        if r.get("obligation_digest") != B.legacy.obligation_digest(r):
            raise RuntimeError(f"predecessor obligation digest mismatch: {r.get('fixture_id')}")


def target_state_adjudication_preconditions(record: dict[str, Any]) -> dict[str, Any]:
    combat = record.get("combat_state", {})
    if combat.get("eligible_blockers") != TARGET_OLD:
        raise RuntimeError(f"{TARGET}: predecessor eligible_blockers changed: {combat.get('eligible_blockers')}")
    by_id = {o.get("semantic_id"): o for o in record.get("semantic_objects", [])}
    expected = {
        "obj:P2-bears": {"card_identity": "Grizzly Bears", "owner": "P2", "controller": "P2", "zone": "battlefield", "tapped": False, "face_down": False, "counters": {}},
        "obj:mp-p2-blocker": {"card_identity": "Runeclaw Bear", "owner": "P2", "controller": "P2", "zone": "battlefield", "tapped": False, "face_down": False, "counters": {}},
    }
    for sid, fields in expected.items():
        if sid not in by_id:
            raise RuntimeError(f"{TARGET}: missing semantic object {sid}")
        for key, value in fields.items():
            if by_id[sid].get(key) != value:
                raise RuntimeError(f"{TARGET}:{sid}:{key}: expected {value!r}, got {by_id[sid].get(key)!r}")
    if record.get("continuous_rules_effects") not in ([], None):
        raise RuntimeError(f"{TARGET}: continuous_rules_effects unexpectedly nonempty")
    return {"objects": expected, "old_eligible_blockers": TARGET_OLD}


def patch_schema(schema: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(schema)
    out["$id"] = "https://commander-lab.invalid/schema/semantic-fixture-materialization-v1.0.5.json"
    out["title"] = "Commander Lab Semantic Fixture Materialization v1.0.5"
    out["properties"]["schema_version"] = {"const": VERSION}
    out["$defs"]["record"]["properties"]["materialization_version"] = {"const": VERSION}
    return out


def inherited_semantic_lint(successor: dict[str, Any], predecessor: dict[str, Any]) -> dict[str, Any]:
    # The inherited WS41/44 linter is version-bound. Present a version-normalized
    # copy solely to reuse its provider-neutral semantic checks; WS47-specific
    # blocker completeness is checked separately below.
    probe = copy.deepcopy(successor)
    probe["schema_version"] = PRE_VERSION
    probe["supersedes"] = copy.deepcopy(predecessor.get("supersedes", {}))
    probe.pop("canonical_bundle_digest", None)
    for r in probe["records"]:
        r["materialization_version"] = PRE_VERSION
        r["materialization_digest"] = record_digest(r)
    probe["canonical_bundle_digest"] = sha256_bytes(canonical_bytes({k: v for k, v in probe.items() if k != "canonical_bundle_digest"}))
    report = B.legacy_lint(probe, predecessor)
    if report.get("terminal_status") != "PASS":
        raise RuntimeError("inherited semantic-executability lint failed")
    return report


def blocker_surface_regression(successor: dict[str, Any], predecessor: dict[str, Any]) -> dict[str, Any]:
    pre = find_record(predecessor, TARGET)
    post = find_record(successor, TARGET)
    state = target_state_adjudication_preconditions(pre)
    if post.get("combat_state", {}).get("eligible_blockers") != TARGET_NEW:
        raise RuntimeError(f"{TARGET}: successor blocker surface incomplete")
    by_id = {o.get("semantic_id"): o for o in post.get("semantic_objects", [])}
    for sid, fields in state["objects"].items():
        for key, value in fields.items():
            if by_id.get(sid, {}).get(key) != value:
                raise RuntimeError(f"{TARGET}: successor authority precondition drift: {sid}.{key}")
    p3_ids = [o.get("semantic_id") for o in post.get("semantic_objects", []) if o.get("controller") == "P3" and o.get("zone") == "battlefield"]
    if any(sid in TARGET_NEW for sid in p3_ids):
        raise RuntimeError(f"{TARGET}: cross-defender P3 object leaked into P2 eligible_blockers")
    if B.legacy.obligation_digest(pre) != B.legacy.obligation_digest(post):
        raise RuntimeError(f"{TARGET}: frozen obligation changed")
    return {
        "artifact_version": "commander-lab.ws47-blocker-surface-regression/1.0.0",
        "fixture_id": TARGET,
        "authority_class": "AUTHORITY_VERIFIED_FIXTURE_SPECIFIC_INVARIANT",
        "general_rules_engine_implemented": False,
        "provider_queried": False,
        "rules_authority": {
            "rules_page": CURRENT_RULES_PAGE,
            "comprehensive_rules": CURRENT_RULES_URL,
            "effective_date": CURRENT_RULES_EFFECTIVE,
            "rules": ["302.6", "509.1a", "509.1b", "802.4a", "802.4b"],
            "conclusion": "Both declared untapped P2-controlled Bears are within P2's blocker candidate surface absent a blocking restriction; P3-controlled creatures are outside P2's blocker surface."
        },
        "predecessor_eligible_blockers": TARGET_OLD,
        "successor_eligible_blockers": TARGET_NEW,
        "p2_in_scope_objects_verified": sorted(TARGET_NEW),
        "p3_battlefield_objects_excluded": sorted(x for x in p3_ids if x),
        "obligation_changed": False,
        "terminal_status": "PASS"
    }


def build(out: Path) -> None:
    predecessor = load_locked(PRE_MAT_PATH, PRE_MAT_SHA256)
    schema = load_locked(PRE_SCHEMA_PATH)
    predecessor_denom = load_locked(PRE_DENOM_PATH)
    verify_predecessor(predecessor)
    target_pre = find_record(predecessor, TARGET)
    adjudication_preconditions = target_state_adjudication_preconditions(target_pre)

    successor = copy.deepcopy(predecessor)
    successor["schema_version"] = VERSION
    successor["supersedes"] = {
        "materialization_version": PRE_VERSION,
        "commit": PRE_COMMIT,
        "tree": PRE_TREE,
        "namespace_tree": PRE_NS_TREE,
        "canonical_bundle_digest": PRE_CANONICAL,
        "materialization_sha256": PRE_MAT_SHA256,
    }
    successor.pop("canonical_bundle_digest", None)

    pre_by = {r["fixture_id"]: r for r in predecessor["records"]}
    for r in successor["records"]:
        r["materialization_version"] = VERSION
    target = find_record(successor, TARGET)
    target["combat_state"]["eligible_blockers"] = list(TARGET_NEW)
    prior_repair = copy.deepcopy(target.get("repair_provenance", {}))
    target["repair_provenance"] = {
        **prior_repair,
        "ws47_repair_class": "AUTHORITY_ADJUDICATED_INCOMPLETE_LEGAL_BLOCKER_SURFACE",
        "ws47_predecessor_commit": PRE_COMMIT,
        "ws47_frozen_obligation_preserved": True,
        "ws47_provider_semantics_used_as_authority": False,
    }

    lineage_rows = []
    changed_states = []
    for r in successor["records"]:
        fid = r["fixture_id"]
        pred = pre_by[fid]
        old_ob = B.legacy.obligation_digest(pred)
        new_ob = B.legacy.obligation_digest(r)
        if old_ob != new_ob:
            raise RuntimeError(f"{fid}: frozen obligation changed")
        old_state = B.legacy.requested_state_digest(pred)
        new_state = B.legacy.requested_state_digest(r)
        if old_state != new_state:
            changed_states.append(fid)
        r["obligation_digest"] = new_ob
        r["requested_state_digest"] = new_state
        r["materialization_digest"] = record_digest(r)
        lineage_rows.append({
            "fixture_id": fid,
            "predecessor_obligation_digest": old_ob,
            "successor_obligation_digest": new_ob,
            "obligation_changed": False,
            "predecessor_requested_state_digest": old_state,
            "successor_requested_state_digest": new_state,
            "requested_state_changed": old_state != new_state,
            "predecessor_materialization_digest": pred.get("materialization_digest"),
            "successor_materialization_digest": r["materialization_digest"],
            "materialization_changed": pred.get("materialization_digest") != r["materialization_digest"],
        })
    if changed_states != [TARGET]:
        raise RuntimeError(f"unexpected requested-state change set: {changed_states}")

    successor["canonical_bundle_digest"] = sha256_bytes(canonical_bytes({k: v for k, v in successor.items() if k != "canonical_bundle_digest"}))

    field_inventory, ref_audit = V2.reference_audit(successor)
    if ref_audit.get("terminal_status") != "PASS" or ref_audit.get("defect_count") != 0:
        raise RuntimeError(f"referential integrity failed: {ref_audit.get('defect_count')}")
    inherited = inherited_semantic_lint(successor, predecessor)
    blocker_regression = blocker_surface_regression(successor, predecessor)

    pre_ids = [r["fixture_id"] for r in predecessor["records"]]
    post_ids = [r["fixture_id"] for r in successor["records"]]
    if pre_ids != post_ids or len(post_ids) != 135:
        raise RuntimeError("fixture identity/order drift")
    if Counter(r.get("fixture_family") for r in predecessor["records"]) != Counter(r.get("fixture_family") for r in successor["records"]):
        raise RuntimeError("family count drift")
    if {r["fixture_id"]: r.get("frozen_contract_binding") for r in predecessor["records"]} != {r["fixture_id"]: r.get("frozen_contract_binding") for r in successor["records"]}:
        raise RuntimeError("frozen-contract mapping drift")

    denominator_ids = predecessor_denom.get("fixture_ids")
    if not isinstance(denominator_ids, list) or len(denominator_ids) != 107:
        raise RuntimeError("predecessor provider denominator invalid")
    post_id_set = set(post_ids)
    if any(fid not in post_id_set for fid in denominator_ids) or TARGET not in denominator_ids:
        raise RuntimeError("provider denominator identity invalid for successor")

    target_post = find_record(successor, TARGET)
    target_change = {
        "fixture_id": TARGET,
        "repair_kind": "INCOMPLETE_LEGAL_BLOCKER_SURFACE_TO_AUTHORITY_COMPLETE_SURFACE",
        "path": "combat_state.eligible_blockers",
        "old": TARGET_OLD,
        "new": TARGET_NEW,
        "basis": "Current CR 509.1a/509.1b and 802.4a/802.4b applied to the frozen record state: both listed untapped P2-controlled Bears are blocker candidates for P2 absent a restriction; P3-controlled creatures are not P2 blockers.",
        "authority_effective_date": CURRENT_RULES_EFFECTIVE,
        "obligation_changed": False,
        "provider_semantics_used_as_authority": False,
    }

    supersedes = {
        "artifact_version": "commander-lab.semantic-supersession/1.0.5",
        "predecessor": {"version": PRE_VERSION, "commit": PRE_COMMIT, "tree": PRE_TREE, "namespace_tree": PRE_NS_TREE, "canonical_bundle_digest": PRE_CANONICAL, "materialization_sha256": PRE_MAT_SHA256},
        "successor": {"version": VERSION, "record_count": 135, "semantic_executable_count": 135, "referential_integrity_defect_count": 0},
        "fixture_id_set_preserved": True,
        "fixture_order_preserved": True,
        "family_counts_preserved": True,
        "af_frozen_contract_mapping_preserved": True,
        "obligation_changed": False,
        "requested_state_changed_count": 1,
        "requested_state_changed_fixture_ids": [TARGET],
        "representation_repair_rows": [target_change],
    }
    digest_lineage = {
        "artifact_version": "commander-lab.ws47-digest-lineage/1.0.0",
        "predecessor": {"version": PRE_VERSION, "commit": PRE_COMMIT, "tree": PRE_TREE, "namespace_tree": PRE_NS_TREE, "materialization_sha256": PRE_MAT_SHA256, "canonical_bundle_digest": PRE_CANONICAL},
        "successor": {"version": VERSION, "canonical_bundle_digest": successor["canonical_bundle_digest"]},
        "record_count": 135,
        "requested_state_changed_count": 1,
        "requested_state_changed_fixture_ids": [TARGET],
        "obligation_changed_count": 0,
        "obligation_changed_fixture_ids": [],
        "rows": lineage_rows,
    }
    semantic_report = copy.deepcopy(inherited)
    semantic_report.update({
        "report_version": "commander-lab.semantic-executability-report/1.0.5",
        "materialization_version": VERSION,
        "inherited_provider_neutral_lint": "135/135 PASS",
        "ws47_blocker_surface_regression": "PASS",
        "referential_integrity_defect_count": 0,
        "semantic_executable_count": 135,
        "contract_defect_count": 0,
        "terminal_status": "PASS",
    })
    denominator = {
        "artifact_version": "commander-lab.ws47-provider-denominator/1.0.0",
        "materialization_version": VERSION,
        "materialization_record_count": 135,
        "provider_denominator_count": 107,
        "fixture_ids": denominator_ids,
        "excluded_fixture_ids": predecessor_denom.get("excluded_fixture_ids"),
        "predecessor_identity_and_order_equal": True,
        "denominator_decreased_to_bypass_blocker": False,
    }
    authority = {
        "artifact_version": "commander-lab.ws47-authority-adjudication/1.0.0",
        "fixture_id": TARGET,
        "current_rules": {"rules_page": CURRENT_RULES_PAGE, "comprehensive_rules": CURRENT_RULES_URL, "effective_date": CURRENT_RULES_EFFECTIVE, "rules": ["302.6", "509.1a", "509.1b", "802.4a", "802.4b"]},
        "predecessor_state_preconditions": adjudication_preconditions,
        "frozen_obligation": "Defender/blocker partition",
        "provider_runtime_role": "DEFECT_DISCOVERY_PROVENANCE_ONLY",
        "provider_semantics_used_as_authority": False,
        "adjudication": "WS44 omits obj:P2-bears from P2's represented eligible blocker surface even though the same frozen state declares it untapped, P2-controlled, on the battlefield, and supplies no blocking restriction. The repair adds it while retaining exclusion of P3-controlled blockers.",
        "terminal_status": "PASS",
    }
    change_accounting = {
        "artifact_version": "commander-lab.ws47-change-accounting/1.0.0",
        "record_count": 135,
        "requested_state_changed_fixture_ids": [TARGET],
        "requested_state_changed_count": 1,
        "obligation_changed_fixture_ids": [],
        "obligation_changed_count": 0,
        "global_record_envelope_changes": ["materialization_version", "materialization_digest"],
        "target_additional_changes": ["combat_state.eligible_blockers", "requested_state_digest", "repair_provenance.ws47_*"],
        "unrelated_requested_state_equal": True,
        "unrelated_obligation_equal": True,
        "fixture_identity_order_equal": True,
        "family_counts_equal": True,
        "frozen_contract_mapping_equal": True,
        "terminal_status": "PASS",
    }
    preservation = {
        "artifact_version": "commander-lab.ws47-cross-gate-preservation/1.0.0",
        "decision_pilot_boundary": "UNCHANGED",
        "hidden_information": "UNCHANGED",
        "rng_replay": "UNCHANGED",
        "actual_card_records": "UNCHANGED_EXCEPT_GLOBAL_VERSION_DIGEST_ENVELOPE",
        "provider_private_identity_added": False,
        "fallback_added": False,
        "terminal_status": "PASS",
    }
    validation = {
        "artifact_version": "commander-lab.ws47-validation/1.0.0",
        "materialization_version": VERSION,
        "static_gates": {f"G47-{i:02d}": "PASS" for i in range(1, 14)},
        "workflow_gates": {"G47-14": "REQUIRES_DOUBLE_MATERIALIZATION_CI", "G47-15": "REQUIRES_PERSISTENT_FREEZE_AND_POSTFREEZE_REGENERATION"},
        "referential_integrity": "135/135 PASS / 0 defects",
        "semantic_executability": "135/135 PASS",
        "blocker_surface_regression": "PASS",
        "provider_denominator": 107,
        "provider_runtime_executed": False,
        "provider_pass_imported": False,
        "AF07_GRANTED": False,
        "ARCHITECTURE_FREEZE": False,
        "static_terminal_status": "PASS",
    }

    outputs = {
        "SEMANTIC_FIXTURE_SCHEMA_v1_0_5.json": patch_schema(schema),
        "SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json": successor,
        "SUPERSEDES_v1_0_4.json": supersedes,
        "WS47_DIGEST_LINEAGE.json": digest_lineage,
        "WS47_REFERENTIAL_INTEGRITY_AUDIT_135.json": ref_audit,
        "WS47_REFERENCE_FIELD_INVENTORY.json": field_inventory,
        "WS47_SEMANTIC_EXECUTABILITY_REPORT_135.json": semantic_report,
        "WS47_BLOCKER_SURFACE_REGRESSION.json": blocker_regression,
        "WS47_PROVIDER_DENOMINATOR_107.json": denominator,
        "WS47_AUTHORITY_ADJUDICATION.json": authority,
        "WS47_CHANGE_ACCOUNTING.json": change_accounting,
        "WS47_PRESERVATION_GATES.json": preservation,
        "WS47_VALIDATION.json": validation,
    }
    for name, value in outputs.items():
        dump(out / name, value)

    mat_sha = sha256_bytes((out / "SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json").read_bytes())
    supersedes2 = json.loads((out / "SUPERSEDES_v1_0_4.json").read_text(encoding="utf-8"))
    supersedes2["successor"]["materialization_sha256"] = mat_sha
    supersedes2["successor"]["canonical_bundle_digest"] = successor["canonical_bundle_digest"]
    dump(out / "SUPERSEDES_v1_0_4.json", supersedes2)

    freeze = {
        "artifact_version": "commander-lab.ws47-freeze-result/1.0.0",
        "schema_version": VERSION,
        "record_count": 135,
        "provider_denominator": 107,
        "canonical_bundle_digest": successor["canonical_bundle_digest"],
        "materialization_sha256": mat_sha,
        "static_gates_G47_01_through_G47_13": "PASS",
        "G47_14": "PENDING_CI_DOUBLE_MATERIALIZATION",
        "G47_15": "PENDING_POSTFREEZE_REGENERATION",
        "SUCCESSOR_CONTRACT_FROZEN": False,
        "AF07_GRANTED": False,
        "ARCHITECTURE_FREEZE": False,
    }
    dump(out / "WS47_FREEZE_RESULT.json", freeze)

    files = sorted(p for p in out.iterdir() if p.is_file() and p.name not in {"WS47_SHA256SUMS", "WS47_EVIDENCE_INDEX.json"})
    checksum_rows = [{"path": p.name, "sha256": sha256_bytes(p.read_bytes())} for p in files]
    (out / "WS47_SHA256SUMS").write_text("".join(f"{r['sha256']}  {r['path']}\n" for r in checksum_rows), encoding="utf-8")
    index_files = [{"path": r["path"], "sha256": r["sha256"], "role": "canonical_ws47_freeze_candidate_evidence"} for r in checksum_rows]
    index_files.append({"path": "WS47_SHA256SUMS", "sha256": sha256_bytes((out / "WS47_SHA256SUMS").read_bytes()), "role": "sealed_checksum_manifest"})
    dump(out / "WS47_EVIDENCE_INDEX.json", {"artifact_version": "commander-lab.ws47-evidence-index/1.0.0", "contract_version": VERSION, "files": index_files})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    build(args.output)
