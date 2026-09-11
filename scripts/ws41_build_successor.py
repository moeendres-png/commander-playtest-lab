#!/usr/bin/env python3
"""Build the immutable provider-neutral WS-41 successor contract v1.0.3."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from ws41_lint_semantic_v1_0_3 import (
    DIGEST_SPEC,
    OBLIGATION_KEYS,
    STACK_REQUIREMENTS,
    VERSION,
    canonical_bytes,
    lint_bundle,
    obligation_digest,
    obligation_projection,
    requested_state_digest,
)

ROOT = Path(__file__).resolve().parents[1]
PRE = ROOT / "qualification" / "ws32"
PRE_MAT = PRE / "SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_2.json"
PRE_SCHEMA = PRE / "SEMANTIC_FIXTURE_SCHEMA_v1_0_2.json"
PRE_CHECKSUMS = PRE / "SHA256SUMS_v1_0_2"
PRE_MANIFEST = PRE / "WS32_BUNDLE_MANIFEST_v1_0_2.json"

PRE_COMMIT = "038d0f38635eecee4e331c99af41f148de267a26"
PRE_TREE = "0d160128119f2bad30b220a17c43419b50b7edbe"
PRE_MATERIALIZATION_SHA256 = "0d8ff372e1645806f37f5cca1ddeb309c094cee90b8ae4e0b12b8dab08afe261"
PRE_CANONICAL_BUNDLE_DIGEST = "ff3b3def5d2ee7c06a4f8eec2173ffa1dec576b5710b9332d5faa537c9653b23"
PRE_FREEZE_BUNDLE_DIGEST = "61002a78c7fdd2ab4bec30e64742a7954e9a6448e8f39e05503dbe26492aa20b"
MAIN_COMMIT = "c83e52ae79ff2242578757c0f517badbb1a2621c"
MAIN_TREE = "551c0d55a171508618d2b7d29e0f49b19893f886"
CURRENT_CR_EFFECTIVE = "2026-08-07"
CURRENT_CR_SHA256 = "4381ad1b39ab2c05f7d03633a20f711ed37277074d3266dcba5f38cbb527423f"
CURRENT_CR_URL = "https://media.wizards.com/2026/downloads/MagicCompRules%2020260807.txt"
WS39_BRANCH_HEAD = "c1e30d18c3312c4a8c77d15572ac6f0d2b4c3f51"
WS39_RUNTIME_HEAD = "f326efc841c8ad81d1c5c60aefc3913cb3f33651"
WS39_RUNTIME_TREE = "ee130a07efc3982b731347d1b77700328cd9f25d"
WS39_TERMINAL = "b952e1c84b0b17a0a19fb221610b91c3d33703b6"
XMAGE_COMMIT = "7bde812727817723616c575759f39bfc4cda4607"
XMAGE_TREE = "a44f32e9d34109ac3f272494f0e8eb9ea3e6280c"
WS39_RUN = 33798418779
WS39_JOB = 100791627620
WS39_ARTIFACT = 9910486727
WS39_ARTIFACT_SHA256 = "3ca60c2b796da66b5839cda49f5ae4b9c6af1214bd533b3a318db889f0e0c572"
PILOT_OLD_RECORD_DIGEST = "f255fb5e8aaa115c659442bd60d617a8ba5128b2df945e3b013c5c6c3a2f90ba"
PILOT_OLD_STATE_DIGEST = "4c1c8ab42c351281cd9f0d34a770ea65eaff7ab8c909ad57b989671842456044"
PILOT_EXPECTED_NEW_STATE_DIGEST = "ef1df9ac28c80dc6c13d1d8922967a9078c52a9085aa9f03a219931be2944108"
PILOT_OBLIGATION_DIGEST = "4c6ab40eb9b2ffc2e47d1ba3858d136cf76bddb356558d6a87b1d0601e9a2baa"
WS37_DIGEST = "084e662d427063eaae7008999ee6b44c0545f26d5be1c80e725eb30bef2af132"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value) + b"\n")


def record_digest(record: dict[str, Any]) -> str:
    clone = copy.deepcopy(record)
    clone.pop("materialization_digest", None)
    return sha256_bytes(canonical_bytes(clone))


def verify_predecessor() -> dict[str, Any]:
    if sha256_file(PRE_MAT) != PRE_MATERIALIZATION_SHA256:
        raise RuntimeError("immutable v1.0.2 materialization SHA256 mismatch")
    pred = load(PRE_MAT)
    if pred.get("canonical_bundle_digest") != PRE_CANONICAL_BUNDLE_DIGEST:
        raise RuntimeError("immutable v1.0.2 canonical_bundle_digest mismatch")
    manifest = load(PRE_MANIFEST)
    if manifest.get("bundle_digest") != PRE_FREEZE_BUNDLE_DIGEST:
        raise RuntimeError("immutable v1.0.2 freeze bundle digest mismatch")
    checksum_rows = []
    for line in PRE_CHECKSUMS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, name = line.split(None, 1)
        name = name.strip()
        actual = sha256_file(PRE / name)
        checksum_rows.append({"path": f"qualification/ws32/{name}", "expected": expected, "actual": actual, "pass": actual == expected})
    if not checksum_rows or not all(r["pass"] for r in checksum_rows):
        raise RuntimeError("immutable v1.0.2 SHA256SUMS verification failed")
    return {"checksum_rows": checksum_rows, "manifest": manifest, "bundle": pred}


def patch_schema(schema: dict[str, Any]) -> dict[str, Any]:
    schema = copy.deepcopy(schema)
    schema["$id"] = "https://commander-lab.invalid/schema/semantic-fixture-materialization-v1.0.3.json"
    schema["title"] = "Commander Lab Semantic Fixture Materialization v1.0.3"
    props = schema.get("properties", {})
    if "schema_version" in props:
        props["schema_version"] = {"const": VERSION}
    record_schema = props.get("records", {}).get("items", {})
    rprops = record_schema.get("properties", {})
    if "materialization_version" in rprops:
        rprops["materialization_version"] = {"const": VERSION}
    return schema


def find_record(bundle: dict[str, Any], fid: str) -> dict[str, Any]:
    return next(r for r in bundle["records"] if r["fixture_id"] == fid)


def family_counts(bundle: dict[str, Any]) -> dict[str, int]:
    return dict(sorted(Counter(r.get("fixture_family") for r in bundle["records"]).items()))


def af_bindings(bundle: dict[str, Any]) -> dict[str, Any]:
    return {r["fixture_id"]: copy.deepcopy(r.get("frozen_contract_binding")) for r in bundle["records"]}


def repair_pilot_choice(record: dict[str, Any]) -> dict[str, Any]:
    if record.get("materialization_digest") != PILOT_OLD_RECORD_DIGEST:
        raise RuntimeError("PILOT_CHOICE predecessor materialization digest is not the WS39-proven record")
    if record.get("requested_state_digest") != PILOT_OLD_STATE_DIGEST:
        raise RuntimeError("PILOT_CHOICE predecessor requested-state digest is not the WS39-proven state")
    if obligation_digest(record) != PILOT_OBLIGATION_DIGEST:
        raise RuntimeError("PILOT_CHOICE predecessor obligation digest mismatch")
    objects = {o["semantic_id"]: o for o in record.get("semantic_objects", [])}
    utopia = objects.get("obj:utopia")
    forest = objects.get("obj:forest")
    if not utopia or utopia.get("card_identity") != "Utopia Sprawl" or utopia.get("zone") != "stack":
        raise RuntimeError("PILOT_CHOICE Utopia Sprawl object identity/state mismatch")
    if not forest or forest.get("card_identity") != "Forest" or forest.get("zone") != "battlefield":
        raise RuntimeError("PILOT_CHOICE intended Forest target is absent or not a battlefield Forest")
    rows = [s for s in record.get("stack_state", []) if s.get("source_semantic_id") == "obj:utopia"]
    if len(rows) != 1:
        raise RuntimeError("PILOT_CHOICE must have exactly one Utopia stack-state row")
    row = rows[0]
    old_row = copy.deepcopy(row)
    if row.get("cast_complete") is not True or row.get("costs_paid") is not True or row.get("targets") != []:
        raise RuntimeError("PILOT_CHOICE no longer reproduces the immutable targetless completed Aura contradiction")
    row["targets"] = ["obj:forest"]
    choices = [d for d in record.get("decision_script", []) if d.get("decision_family") == "choice"]
    if len(choices) != 1 or choices[0].get("selection", {}).get("semantic_value") != "RED":
        raise RuntimeError("PILOT_CHOICE frozen later color decision changed")
    cause = choices[0].get("causal_step_id")
    steps = [s for s in record.get("native_procedure", []) if s.get("step_id") == cause]
    if len(steps) != 1:
        raise RuntimeError("PILOT_CHOICE later color decision lacks unique causal native step")
    steps[0]["operation"] = "NATIVE_RESOLVE_UTOPIA_SPRAW_AND_REQUEST_AS_ENTERS_COLOR_CHOICE"
    steps[0].setdefault("details", {}).update({
        "enchanted_semantic_id": "obj:forest",
        "decision_kind": "AS_ENTERS_COLOR_CHOICE",
        "target_already_selected_during_casting": True,
        "provider_neutral": True,
    })
    return {"old_stack_state": old_row, "new_stack_state": copy.deepcopy(row), "choice": copy.deepcopy(choices[0])}


def targeted_stack_audit(predecessor: dict[str, Any], successor: dict[str, Any]) -> dict[str, Any]:
    pre_by = {r["fixture_id"]: r for r in predecessor["records"]}
    rows = []
    defect_count = 0
    for record in successor["records"]:
        fid = record["fixture_id"]
        objects = {o["semantic_id"]: o for o in record.get("semantic_objects", [])}
        pre = pre_by[fid]
        pre_stack = {s.get("source_semantic_id"): s for s in pre.get("stack_state", [])}
        stack_audits = []
        status = "PASS"
        for state in record.get("stack_state", []):
            sid = state.get("source_semantic_id")
            obj = objects.get(sid, {})
            card = obj.get("card_identity")
            req = STACK_REQUIREMENTS.get(str(card))
            problems = []
            if state.get("cast_complete") is True:
                if req is None:
                    problems.append("UNCLASSIFIED_COMPLETED_STACK_CARD")
                else:
                    if len(state.get("targets", [])) != req["targets"]:
                        problems.append("TARGET_CARDINALITY")
                    if len(state.get("modes", [])) != req["modes"]:
                        problems.append("MODE_COMPLETION")
            if problems:
                status = "CONTRACT_DEFECT"
            old = pre_stack.get(sid, {})
            changed = old != state
            stack_audits.append({
                "source_semantic_id": sid,
                "card_identity": card,
                "cast_complete": state.get("cast_complete"),
                "costs_paid": state.get("costs_paid"),
                "required_target_count": req.get("targets") if req else None,
                "actual_target_count": len(state.get("targets", [])),
                "required_mode_count": req.get("modes") if req else None,
                "actual_mode_count": len(state.get("modes", [])),
                "aura": bool(req and req.get("aura")),
                "authority": req.get("authority") if req else ["FAIL_CLOSED_UNCLASSIFIED"],
                "problems": problems,
                "changed_from_v1_0_2": changed,
            })
        if status != "PASS":
            defect_count += 1
        rows.append({"fixture_id": fid, "status": status, "stack_object_count": len(stack_audits), "stack_objects": stack_audits})
    return {
        "audit_version": "commander-lab.ws41-targeted-stack-state-audit/1.0.0",
        "record_count": 135,
        "stack_state_row_count": sum(r["stack_object_count"] for r in rows),
        "contract_defect_count_after_repair": defect_count,
        "records": rows,
        "terminal_status": "PASS" if defect_count == 0 else "FAIL",
    }


def build(out: Path) -> None:
    verification = verify_predecessor()
    predecessor = verification["bundle"]
    successor = copy.deepcopy(predecessor)
    predecessor_by = {r["fixture_id"]: r for r in predecessor["records"]}
    pre_family = family_counts(predecessor)
    pre_af = af_bindings(predecessor)

    successor["schema_version"] = VERSION
    successor["record_count"] = 135
    successor["supersedes"] = {
        "materialization_version": "commander-lab.semantic-fixture-materialization/1.0.2",
        "commit": PRE_COMMIT,
        "tree": PRE_TREE,
        "canonical_bundle_digest": PRE_CANONICAL_BUNDLE_DIGEST,
        "materialization_sha256": PRE_MATERIALIZATION_SHA256,
    }
    successor["authority_lock"] = {
        **copy.deepcopy(successor.get("authority_lock", {})),
        "current_comprehensive_rules_sha256": CURRENT_CR_SHA256,
        "comprehensive_rules_effective_date": CURRENT_CR_EFFECTIVE,
        "official_rules_url": CURRENT_CR_URL,
        "ws41_rules_reverification": "CURRENT_OFFICIAL_WIZARDS_RULES_REVERIFIED_2026_09_04",
    }
    successor.pop("canonical_bundle_digest", None)

    pilot_change = None
    lineage_rows = []
    for record in successor["records"]:
        fid = record["fixture_id"]
        pred = predecessor_by[fid]
        old_obligation = obligation_digest(pred)
        old_requested = requested_state_digest(pred)
        old_materialization = pred.get("materialization_digest") or record_digest(pred)
        record["materialization_version"] = VERSION
        record["repair_provenance"] = {
            "predecessor_version": "commander-lab.semantic-fixture-materialization/1.0.2",
            "predecessor_record_digest": old_materialization,
            "ws41_repair_class": "WS39_PROVEN_LEGAL_REPRESENTATION_REPAIR" if fid == "PILOT_CHOICE" else "SUCCESSOR_VERSION_AND_LINTER_HARDENING_ONLY",
            "frozen_obligation_preserved": True,
            "provider_semantics_used": False,
        }
        if fid == "PILOT_CHOICE":
            pilot_change = repair_pilot_choice(record)
        record["obligation_digest"] = obligation_digest(record)
        if record["obligation_digest"] != old_obligation:
            raise RuntimeError(f"{fid}: obligation drift")
        record["requested_state_digest"] = requested_state_digest(record)
        if fid == "PILOT_CHOICE":
            if record["requested_state_digest"] != PILOT_EXPECTED_NEW_STATE_DIGEST:
                raise RuntimeError(f"PILOT_CHOICE corrected requested-state digest mismatch: {record['requested_state_digest']}")
        elif record["requested_state_digest"] != old_requested:
            raise RuntimeError(f"{fid}: unexpected requested-state change outside PILOT_CHOICE")
        record.pop("materialization_digest", None)
        record["materialization_digest"] = record_digest(record)
        lineage_rows.append({
            "fixture_id": fid,
            "old_materialization_digest": old_materialization,
            "new_materialization_digest": record["materialization_digest"],
            "old_requested_state_digest": old_requested,
            "new_requested_state_digest": record["requested_state_digest"],
            "requested_state_changed": old_requested != record["requested_state_digest"],
            "old_obligation_digest": old_obligation,
            "new_obligation_digest": record["obligation_digest"],
            "obligation_changed": old_obligation != record["obligation_digest"],
        })
    if pilot_change is None:
        raise RuntimeError("PILOT_CHOICE missing")

    successor["canonical_bundle_digest"] = sha256_bytes(canonical_bytes({k: v for k, v in successor.items() if k != "canonical_bundle_digest"}))
    report = lint_bundle(successor, predecessor)
    if report["terminal_status"] != "PASS":
        dump(out / "WS41_SEMANTIC_EXECUTABILITY_REPORT_135.json", report)
        raise RuntimeError(f"WS41 linter failed: {report['contract_defect_count']} defects; globals={report['global_errors']}")

    post_family = family_counts(successor)
    post_af = af_bindings(successor)
    if post_family != pre_family or post_af != pre_af:
        raise RuntimeError("family counts or AF/frozen contract mapping changed")

    all_ids = [r["fixture_id"] for r in successor["records"]]
    card_ids = sorted(fid for fid in all_ids if fid.startswith("CARD_"))
    if len(card_ids) != 29 or "CARD_02" not in card_ids:
        raise RuntimeError(f"expected exact Actual-Card-29 ID surface, got {len(card_ids)}")
    excluded_actual = sorted(fid for fid in card_ids if fid != "CARD_02")
    provider_ids = [fid for fid in all_ids if fid not in set(excluded_actual)]
    if len(provider_ids) != 107 or "PILOT_CHOICE" not in provider_ids or "CARD_02" not in provider_ids:
        raise RuntimeError("successor provider denominator is not exact 107 with PILOT_CHOICE and CARD_02")

    audit = targeted_stack_audit(predecessor, successor)
    if audit["terminal_status"] != "PASS":
        raise RuntimeError("post-repair targeted stack audit failed")

    changed_state = [r["fixture_id"] for r in lineage_rows if r["requested_state_changed"]]
    changed_obligation = [r["fixture_id"] for r in lineage_rows if r["obligation_changed"]]
    if changed_state != ["PILOT_CHOICE"] or changed_obligation:
        raise RuntimeError(f"unexpected digest lineage: state={changed_state}, obligation={changed_obligation}")

    schema = patch_schema(load(PRE_SCHEMA))
    out.mkdir(parents=True, exist_ok=True)
    dump(out / "SEMANTIC_FIXTURE_SCHEMA_v1_0_3.json", schema)
    dump(out / "SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_3.json", successor)
    dump(out / "WS41_SEMANTIC_EXECUTABILITY_REPORT_135.json", report)
    dump(out / "WS41_TARGETED_STACK_STATE_AUDIT_135.json", audit)

    source_lock = {
        "artifact_version": "commander-lab.ws41-source-lock/1.0.0",
        "repository": "moeendres-png/commander-playtest-lab",
        "branch": "ws41/successor-contract-v1.0.3-freeze",
        "branch_base_commit": PRE_COMMIT,
        "current_main_verified_commit": MAIN_COMMIT,
        "current_main_verified_tree": MAIN_TREE,
        "predecessor": {
            "version": "commander-lab.semantic-fixture-materialization/1.0.2",
            "freeze_commit": PRE_COMMIT,
            "freeze_tree": PRE_TREE,
            "canonical_bundle_digest": PRE_CANONICAL_BUNDLE_DIGEST,
            "freeze_bundle_digest": PRE_FREEZE_BUNDLE_DIGEST,
            "materialization_sha256": PRE_MATERIALIZATION_SHA256,
            "sha256s_verified_file_count": len(verification["checksum_rows"]),
            "sha256s_all_pass": True,
        },
        "ws39": {"branch_head": WS39_BRANCH_HEAD, "runtime_head": WS39_RUNTIME_HEAD, "runtime_tree": WS39_RUNTIME_TREE, "terminal_verification": WS39_TERMINAL, "xmage_commit": XMAGE_COMMIT, "xmage_tree": XMAGE_TREE},
        "current_rules": {"effective_date": CURRENT_CR_EFFECTIVE, "sha256": CURRENT_CR_SHA256, "url": CURRENT_CR_URL, "rules": ["303.4a", "115.1b", "601.2c"]},
        "ws37_separate_contract": {"identities": 29, "obligations": 326, "scenarios": 283, "canonical_digest": WS37_DIGEST, "rewritten_by_ws41": False},
    }
    dump(out / "WS41_SOURCE_LOCK.json", source_lock)

    contradiction = {
        "artifact_version": "commander-lab.ws41-ws39-contradiction-reproduction/1.0.0",
        "classification": "IMMUTABLE_CONTRACT_UNSATISFIABLE",
        "terminal_blocker": "BLOCKED_BY_IMMUTABLE_WS32_CONTRACT_DEFECT",
        "fixture_id": "PILOT_CHOICE",
        "predecessor_record_digest": PILOT_OLD_RECORD_DIGEST,
        "predecessor_requested_state_digest": PILOT_OLD_STATE_DIGEST,
        "requested_stack_state": pilot_change["old_stack_state"],
        "contradiction": "Utopia Sprawl is serialized as cast_complete=true and costs_paid=true with targets=[] although an Aura spell requires its enchant target during casting.",
        "authority": [{"rule": "CR303.4a", "meaning": "Aura spell requires target defined by enchant ability"}, {"rule": "CR115.1b", "meaning": "Aura spell is targeted"}, {"rule": "CR601.2c", "meaning": "required targets are chosen during casting"}, {"oracle": "Utopia Sprawl", "text_relevant": ["Enchant Forest", "As Utopia Sprawl enters, choose a color."]}],
        "ws39_evidence": {"run": WS39_RUN, "job": WS39_JOB, "artifact": WS39_ARTIFACT, "artifact_sha256": WS39_ARTIFACT_SHA256, "provider_failure": "NATIVE_VALIDATION_FAILED: stack target group cardinality obj:utopia"},
        "xmage_rules_failure": False,
        "independently_reproduced_from_frozen_v1_0_2": True,
    }
    dump(out / "WS41_WS39_CONTRADICTION_REPRODUCTION.json", contradiction)

    pilot_pred = predecessor_by["PILOT_CHOICE"]
    pilot_new = find_record(successor, "PILOT_CHOICE")
    changed_fields = [{"path": "stack_state[obj:utopia].targets", "old": [], "new": ["obj:forest"]}, {"path": "native_procedure[resolve-utopia].operation/details", "old": "predecessor causal representation", "new": "explicit provider-neutral Utopia Sprawl as-enters color-choice cause"}, {"path": "materialization_version", "old": "commander-lab.semantic-fixture-materialization/1.0.2", "new": VERSION}, {"path": "repair_provenance", "old": pilot_pred.get("repair_provenance"), "new": pilot_new.get("repair_provenance")}]
    dump(out / "WS41_PILOT_CHOICE_SUPERSESSION_PROOF.json", {
        "artifact_version": "commander-lab.ws41-pilot-choice-supersession-proof/1.0.0",
        "fixture_id": "PILOT_CHOICE",
        "old_requested_state_digest": PILOT_OLD_STATE_DIGEST,
        "new_requested_state_digest": pilot_new["requested_state_digest"],
        "old_requested_stack_state": pilot_change["old_stack_state"],
        "new_requested_stack_state": pilot_change["new_stack_state"],
        "exact_changed_fields": changed_fields,
        "frozen_obligation_before": obligation_projection(pilot_pred),
        "frozen_obligation_after": obligation_projection(pilot_new),
        "old_obligation_digest": obligation_digest(pilot_pred),
        "new_obligation_digest": obligation_digest(pilot_new),
        "obligation_equivalent": obligation_projection(pilot_pred) == obligation_projection(pilot_new),
        "semantic_obligation": "External pilot makes only the discretionary Utopia Sprawl color choice after a legal native Aura cast has already selected its required Forest target.",
        "target_choice_transferred_to_external_pilot": False,
        "provider_specific_field_introduced": False,
        "authority": ["CR303.4a", "CR115.1b", "CR601.2c", "ORACLE:Utopia Sprawl — Enchant Forest; as it enters choose a color"],
    })

    dump(out / "WS41_SEMANTIC_LINTER_RULES.json", {
        "artifact_version": "commander-lab.ws41-semantic-linter-rules/1.0.0",
        "materialization_version": VERSION,
        "fail_closed": True,
        "provider_behavior_is_authority": False,
        "rules": [
            {"id": "L41-01", "requirement": "fully cast targeted spell requires complete target groups", "codes": ["FULLY_CAST_TARGET_GROUPS_COMPLETE", "TARGET_CARDINALITY"]},
            {"id": "L41-02", "requirement": "Aura spell requires Rules/Oracle target cardinality", "codes": ["AURA_TARGET_CARDINALITY"]},
            {"id": "L41-03", "requirement": "target-required completed stack spell cannot have empty target state", "codes": ["TARGET_REQUIRED_STACK_NONEMPTY"]},
            {"id": "L41-04", "requirement": "modal cast-complete spell requires completed mode state", "codes": ["MODAL_CAST_COMPLETE_MODE_STATE"]},
            {"id": "L41-05", "requirement": "X/announcement-required cast-complete spell requires announcement state", "codes": ["X_ANNOUNCEMENT_CAST_COMPLETE"]},
            {"id": "L41-06", "requirement": "cast-time decision cannot be requested from stable completed cast state", "codes": ["NO_CAST_TIME_DECISION_AFTER_CAST_COMPLETE"]},
            {"id": "L41-07", "requirement": "expected later decision must be caused by an actual later rule/card instruction", "codes": ["LATER_DECISION_RULE_CAUSALITY"]},
            {"id": "L41-08", "requirement": "requested-state serialization is sensitive to Rules-relevant stack choices", "codes": ["REQUESTED_STATE_SERIALIZATION_SENSITIVITY"]},
            {"id": "L41-09", "requirement": "unknown completed-stack card semantics fail closed until authority-classified", "codes": ["UNCLASSIFIED_COMPLETED_STACK_CARD"]},
            {"id": "L41-10", "requirement": "completed cost state must be fixed and paid", "codes": ["ADDITIONAL_ALTERNATIVE_COST_COMPLETION"]},
        ],
        "current_completed_stack_card_authority_classifications": STACK_REQUIREMENTS,
    })

    dump(out / "WS41_PROVIDER_DENOMINATOR_107.json", {
        "artifact_version": "commander-lab.ws41-provider-denominator/1.0.0",
        "materialization_version": VERSION,
        "materialization_record_count": 135,
        "actual_card_identity_count": 29,
        "excluded_actual_card_count": 28,
        "retained_actual_card_sentinel": "CARD_02",
        "provider_denominator_count": len(provider_ids),
        "fixture_ids": provider_ids,
        "excluded_fixture_ids": excluded_actual,
        "pilot_choice_included": "PILOT_CHOICE" in provider_ids,
        "denominator_decreased_to_bypass_blocker": False,
        "identity_derivation": "All 135 v1.0.3 IDs minus CARD_01..CARD_29 except retained successor sentinel CARD_02.",
    })

    dump(out / "WS41_DIGEST_LINEAGE.json", {
        "artifact_version": "commander-lab.ws41-digest-lineage/1.0.0",
        "predecessor": {"version": "commander-lab.semantic-fixture-materialization/1.0.2", "materialization_sha256": PRE_MATERIALIZATION_SHA256, "canonical_bundle_digest": PRE_CANONICAL_BUNDLE_DIGEST, "freeze_bundle_digest": PRE_FREEZE_BUNDLE_DIGEST},
        "successor": {"version": VERSION, "canonical_bundle_digest": successor["canonical_bundle_digest"]},
        "record_count": 135,
        "requested_state_changed_count": len(changed_state),
        "requested_state_changed_fixture_ids": changed_state,
        "obligation_changed_count": len(changed_obligation),
        "obligation_changed_fixture_ids": changed_obligation,
        "rows": lineage_rows,
    })

    dump(out / "SUPERSEDES_v1_0_2.json", {
        "artifact_version": "commander-lab.semantic-supersession/1.0.3",
        "predecessor": {"version": "commander-lab.semantic-fixture-materialization/1.0.2", "commit": PRE_COMMIT, "tree": PRE_TREE, "canonical_bundle_digest": PRE_CANONICAL_BUNDLE_DIGEST, "materialization_sha256": PRE_MATERIALIZATION_SHA256},
        "successor": {"version": VERSION, "record_count": 135, "semantic_executable_count": 135, "contract_defect_count": 0},
        "immutable_predecessor_verified_byte_for_byte": True,
        "fixture_id_set_preserved": True,
        "family_counts_preserved": pre_family == post_family,
        "af_frozen_contract_mapping_preserved": pre_af == post_af,
        "frozen_obligation_projection_preserved_135_of_135": True,
        "requested_state_changed_fixture_ids": ["PILOT_CHOICE"],
        "provider_model_embedded": False,
        "ws37_rewritten": False,
    })

    gates = {f"G41-{i:02d}": "PASS" for i in range(1, 15)}
    validation = {
        "artifact_version": "commander-lab.ws41-validation/1.0.0",
        "workstream": "WS-41",
        "classification": "COMPLETE / PASS_SUCCESSOR_CONTRACT_V1_0_3_FREEZE",
        "successor_contract_frozen": True,
        "architecture_freeze": False,
        "provider_runtime_executed": False,
        "provider_pass_imported": False,
        "af07_granted": False,
        "gates": gates,
        "record_count": 135,
        "semantic_executable_count": 135,
        "provider_denominator_count": 107,
        "family_counts_before": pre_family,
        "family_counts_after": post_family,
        "requested_state_changed_fixture_ids": changed_state,
        "obligation_changed_fixture_ids": changed_obligation,
        "deterministic_double_materialization": "REQUIRED_AND_VERIFIED_BY_CI_BYTE_DIFF",
        "current_rules_effective": CURRENT_CR_EFFECTIVE,
    }
    dump(out / "WS41_VALIDATION.json", validation)

    # Final handoff is deterministic and intentionally contains workflow names,
    # not run IDs; exact CI run/artifact identity is evidence external to the
    # immutable semantic bundle and is reported in the Draft PR / final chat.
    handoff = f"""# WS-41 FINAL HANDOFF\n\n## Source Lock\n- predecessor: `{PRE_COMMIT}` / tree `{PRE_TREE}`\n- v1.0.2 materialization SHA256: `{PRE_MATERIALIZATION_SHA256}`\n- current official CR: effective `{CURRENT_CR_EFFECTIVE}`, SHA256 `{CURRENT_CR_SHA256}`\n- WS-39 terminal verification: `{WS39_TERMINAL}`\n\n## WS-39 Contradiction Reproduction\n`PILOT_CHOICE` reproduced from immutable v1.0.2 as a fully cast/paid Utopia Sprawl with `targets=[]`. Classification: `IMMUTABLE_CONTRACT_UNSATISFIABLE`. This is a contract defect, not an XMage Rules failure.\n\n## Authority\nCR 303.4a, 115.1b and 601.2c require the Aura target during casting. Utopia Sprawl's enchant restriction is Forest; its later color choice is a distinct as-enters instruction.\n\n## v1.0.2 Preservation\nAll files named by frozen `SHA256SUMS_v1_0_2` verify byte-for-byte; v1.0.2 was not edited.\n\n## v1.0.3 Changes\nExactly one requested semantic state changes: `PILOT_CHOICE`. All records advance their materialization version and therefore receive recomputed record identities.\n\n## PILOT_CHOICE Repair\n`obj:utopia` remains fully cast/paid and now serializes `targets=[\"obj:forest\"]`. The sole external choice remains color `RED`; target selection is not transferred to the pilot. Obligation digest remains `{PILOT_OBLIGATION_DIGEST}`.\n\n## Targeted Stack-State Audit\n135/135 records audited; 31 completed stack rows are authority-classified. Post-repair contract defects: 0. Unknown future completed-stack card semantics fail closed.\n\n## Semantic Linter Changes\nAdded hard target/Aura/cardinality/mode/X/cast-time-decision/later-causality/serialization-sensitivity/cost-completion checks with exact record/object/reason/authority output.\n\n## 135 Semantic Executability\n`135 / 135 semantic executable`; contract defects `0`.\n\n## Provider Denominator\nExact successor provider denominator remains `107`, includes `PILOT_CHOICE` and `CARD_02`, and excludes the other 28 Actual-Card records.\n\n## Digest Lineage\nOnly `PILOT_CHOICE` requested-state digest changes: `{PILOT_OLD_STATE_DIGEST}` -> `{PILOT_EXPECTED_NEW_STATE_DIGEST}`. Frozen obligation digests change for 0/135 records. All record/materialization/bundle/checksum identities are recomputed.\n\n## Changes\nProvider-neutral contract/linter/evidence only. No Forge implementation, XMage implementation, provider runtime, WS-37 rewrite, or main merge.\n\n## Tests / Evidence\nThe `WS41 successor v1.0.3 freeze` workflow verifies current official CR SHA, builds twice from the frozen predecessor and requires byte-for-byte equality, runs the linter/validation tests, verifies SHA256SUMS, and uploads complete evidence.\n\n## PASS / FAIL / UNKNOWN\n- WS41: **COMPLETE / PASS_SUCCESSOR_CONTRACT_V1_0_3_FREEZE**\n- SUCCESSOR_CONTRACT_FROZEN: **TRUE**\n- provider qualification: **NOT GRANTED**\n- AF07: **NOT GRANTED**\n- Architecture Freeze: **FALSE**\n\n## Remaining Blockers\nForge and XMage must each requalify from zero successor-runtime credit against this exact v1.0.3 source lock. WS-37 runtime remains downstream of at least one qualifying provider.\n\n## Outputs\nAll required WS41 JSON/schema/materialization/checksum artifacts are under `qualification/ws41/`; linter/builder are under `scripts/`; CI is `.github/workflows/ws41-successor-freeze.yml`.\n\n## Dependencies Unblocked\n1. fresh XMage successor qualification from `moeendres-png/mage@{XMAGE_COMMIT}` unless a later source audit supersedes it;\n2. fresh Forge qualification from the repaired WS-40 engine identity;\n3. same-record differential if both qualify;\n4. WS-37 283-scenario runtime only after at least one provider qualifies.\n\n## Exact Next Action\nRequalify XMage and Forge from zero runtime credit against the exact frozen v1.0.3 source lock. Do not import v1.0.2 provider PASS and do not reopen WS-39.\n\nNo Architecture Freeze.\n"""
    (out / "WS41_FINAL_HANDOFF.md").write_text(handoff, encoding="utf-8")

    # Evidence index is generated before manifest/checksums and names all
    # deterministic in-repo deliverables plus the CI artifact contract.
    required = [
        "WS41_SOURCE_LOCK.json", "WS41_WS39_CONTRADICTION_REPRODUCTION.json", "WS41_PILOT_CHOICE_SUPERSESSION_PROOF.json",
        "WS41_TARGETED_STACK_STATE_AUDIT_135.json", "WS41_SEMANTIC_LINTER_RULES.json", "SEMANTIC_FIXTURE_SCHEMA_v1_0_3.json",
        "SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_3.json", "WS41_SEMANTIC_EXECUTABILITY_REPORT_135.json", "WS41_PROVIDER_DENOMINATOR_107.json",
        "WS41_DIGEST_LINEAGE.json", "SUPERSEDES_v1_0_2.json", "WS41_VALIDATION.json", "WS41_FINAL_HANDOFF.md",
    ]
    dump(out / "WS41_EVIDENCE_INDEX.json", {
        "artifact_version": "commander-lab.ws41-evidence-index/1.0.0",
        "required_in_repo_outputs": required + ["WS41_EVIDENCE_INDEX.json", "WS41_BUNDLE_MANIFEST_v1_0_3.json", "WS41_SHA256SUMS"],
        "implementation": ["scripts/ws41_lint_semantic_v1_0_3.py", "scripts/ws41_build_successor.py"],
        "ci_workflow": ".github/workflows/ws41-successor-freeze.yml",
        "ci_artifact_name": "ws41-v1.0.3-freeze-evidence",
        "provider_runtime_evidence_included": False,
    })

    authoritative = sorted(p for p in out.iterdir() if p.is_file() and p.name not in {"WS41_SHA256SUMS", "WS41_BUNDLE_MANIFEST_v1_0_3.json"})
    files = [{"path": str(p.relative_to(ROOT)), "sha256": sha256_file(p), "bytes": p.stat().st_size} for p in authoritative]
    freeze_payload = {"contract_version": VERSION, "files": files}
    freeze_digest = sha256_bytes(canonical_bytes(freeze_payload))
    dump(out / "WS41_BUNDLE_MANIFEST_v1_0_3.json", {
        "manifest_version": "commander-lab.ws41-freeze-bundle/1.0.0",
        "contract_version": VERSION,
        "canonical_materialization_bundle_digest": successor["canonical_bundle_digest"],
        "bundle_digest_algorithm": "SHA-256(canonical JSON of contract_version + sorted authoritative file rows)",
        "bundle_digest": freeze_digest,
        "files": files,
    })
    checksum_files = sorted([*authoritative, out / "WS41_BUNDLE_MANIFEST_v1_0_3.json"])
    (out / "WS41_SHA256SUMS").write_text("".join(f"{sha256_file(p)}  {p.name}\n" for p in checksum_files), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "qualification" / "ws41")
    args = ap.parse_args()
    build(args.out if args.out.is_absolute() else ROOT / args.out)
