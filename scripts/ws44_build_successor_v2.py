#!/usr/bin/env python3
"""WS-44 v1.0.4 successor builder, referential-integrity closure revision.

Consumes only the exact detached WS-41 predecessor object. This revision closes
record-local identity defects discovered by the complete 135-record audit without
changing any frozen obligation projection and without aliases or provider inference.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterator

import ws44_build_successor as B

VERSION = B.VERSION
# Embedded IDs deliberately require an alnum/underscore terminal character so
# event delimiters such as '->' and sentence punctuation are not consumed.
OBJ_EMBED_RE = re.compile(r"obj:[A-Za-z0-9_](?:[A-Za-z0-9_.-]*[A-Za-z0-9_])?")
CMD_EMBED_RE = re.compile(r"cmd:[A-Za-z0-9_](?:[A-Za-z0-9_.-]*[A-Za-z0-9_])?")
AUDIENCE_SENTINELS = {"ALL_PLAYERS"}
OBLIGATION_KEYS = set(B.legacy.OBLIGATION_KEYS)


def walk_strings(value: Any, path: str = "$") -> Iterator[tuple[str, str, str]]:
    yield from B.walk_strings(value, path)


def rename_semantic_identity(record: dict[str, Any], old: str, new: str) -> list[str]:
    """Rename an exact semantic identity only outside the frozen obligation projection."""
    changed: list[str] = []

    def visit(value: Any, path: str) -> Any:
        if isinstance(value, dict):
            out: dict[Any, Any] = {}
            for key, child in value.items():
                key_path = f"{path}.{key}"
                if path == "$" and key in OBLIGATION_KEYS:
                    out[key] = child
                    continue
                new_key = new if key == old else key
                if new_key != key:
                    changed.append(f"{path}.<key:{key}>")
                out[new_key] = visit(child, key_path)
            return out
        if isinstance(value, list):
            return [visit(child, f"{path}[{i}]") for i, child in enumerate(value)]
        if isinstance(value, str):
            if value == old:
                changed.append(path)
                return new
            if value == f"line:{old}":
                changed.append(path)
                return f"line:{new}"
        return value

    rewritten = visit(record, "$")
    record.clear()
    record.update(rewritten)
    return changed


def apply_additional_representation_repairs(successor: dict[str, Any], predecessor: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    # MICRO_STATE_BASED_ACTIONS: one and only one Memnite is the object whose frozen
    # expected events already identify it as obj:micro-zero. Rename representation,
    # never the obligation.
    sba = B.find_record(successor, "MICRO_STATE_BASED_ACTIONS")
    pred_sba = B.find_record(predecessor, "MICRO_STATE_BASED_ACTIONS")
    pred_ids = Counter(o.get("semantic_id") for o in pred_sba.get("semantic_objects", []))
    if pred_ids["obj:sba-memnite"] != 1 or pred_ids["obj:micro-zero"] != 0:
        raise RuntimeError("MICRO_STATE_BASED_ACTIONS identity preconditions changed")
    required = pred_sba.get("expected_events", {}).get("required_events", [])
    if "continuous_pt:obj:micro-zero:0/0" not in required or "move_to_graveyard:obj:micro-zero" not in required:
        raise RuntimeError("MICRO_STATE_BASED_ACTIONS frozen obligation no longer proves obj:micro-zero identity")
    changed = rename_semantic_identity(sba, "obj:sba-memnite", "obj:micro-zero")
    if not changed:
        raise RuntimeError("MICRO_STATE_BASED_ACTIONS rename changed no representation paths")
    rows.append({
        "fixture_id": "MICRO_STATE_BASED_ACTIONS",
        "repair_kind": "RECORD_LOCAL_IDENTITY_RENAME",
        "old": "obj:sba-memnite",
        "new": "obj:micro-zero",
        "changed_representation_paths": changed,
        "basis": "The record declares exactly one Memnite; its native SBA procedure follows that object, while both frozen required events identify the same 0/0 object as obj:micro-zero.",
        "obligation_changed": False,
        "provider_semantics_used": False,
    })

    # CARD_01: the single Ishai subject is the object named by the frozen terminal
    # condition. Align the declared semantic identity to that already-frozen name.
    c1 = B.find_record(successor, "CARD_01")
    pred_c1 = B.find_record(predecessor, "CARD_01")
    pred_ids = Counter(o.get("semantic_id") for o in pred_c1.get("semantic_objects", []))
    if pred_ids["obj:card_01-subject"] != 1 or pred_ids["obj:card01-ishai"] != 0:
        raise RuntimeError("CARD_01 identity preconditions changed")
    if not any("obj:card01-ishai" in x for x in pred_c1.get("terminal_postconditions", [])):
        raise RuntimeError("CARD_01 frozen terminal condition no longer proves obj:card01-ishai identity")
    changed = rename_semantic_identity(c1, "obj:card_01-subject", "obj:card01-ishai")
    if not changed:
        raise RuntimeError("CARD_01 rename changed no representation paths")
    rows.append({
        "fixture_id": "CARD_01",
        "repair_kind": "RECORD_LOCAL_IDENTITY_RENAME",
        "old": "obj:card_01-subject",
        "new": "obj:card01-ishai",
        "changed_representation_paths": changed,
        "basis": "The record declares exactly one Ishai subject and the frozen terminal condition names that subject obj:card01-ishai.",
        "obligation_changed": False,
        "provider_semantics_used": False,
    })

    # WS05-MP-TRIG-3: one native step intentionally creates three simultaneous Soul
    # Warden triggers. A scalar card-name source is ambiguous; encode the exact three
    # predeclared source identities instead.
    trig = B.find_record(successor, "WS05-MP-TRIG-3")
    pred_trig = B.find_record(predecessor, "WS05-MP-TRIG-3")
    step = pred_trig.get("native_procedure", [])[2]
    exact_sources = ["obj:soulwarden-1", "obj:soulwarden-2", "obj:soulwarden-3"]
    if step.get("operation") != "NATIVE_CREATE_TRIGGER" or step.get("source_object") != "Soul Warden" or step.get("details", {}).get("count") != 3:
        raise RuntimeError("WS05-MP-TRIG-3 source preconditions changed")
    declared = {o.get("semantic_id"): o for o in pred_trig.get("semantic_objects", [])}
    if any(s not in declared for s in exact_sources):
        raise RuntimeError("WS05-MP-TRIG-3 exact source identities missing")
    if [declared[s].get("controller") for s in exact_sources] != ["P1", "P2", "P3"]:
        raise RuntimeError("WS05-MP-TRIG-3 source/controller relation changed")
    succ_step = trig["native_procedure"][2]
    if succ_step.pop("source_object", None) != "Soul Warden":
        raise RuntimeError("WS05-MP-TRIG-3 ambiguous source changed before repair")
    succ_step["source_objects"] = exact_sources
    rows.append({
        "fixture_id": "WS05-MP-TRIG-3",
        "repair_kind": "AMBIGUOUS_MULTI_SOURCE_TO_EXACT_IDENTITY_VECTOR",
        "path": "native_procedure[2]",
        "old": {"source_object": "Soul Warden", "details.count": 3},
        "new": {"source_objects": exact_sources, "details.count": 3},
        "basis": "The native procedure creates exactly three simultaneous triggers and the record declares exactly the three source identities listed, one controlled by each player P1/P2/P3.",
        "obligation_changed": False,
        "provider_semantics_used": False,
    })
    return rows


def reference_audit(bundle: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = []
    inventory: dict[str, Counter[str]] = defaultdict(Counter)
    total_refs = 0
    total_errors = 0
    alias_count = 0
    audience_count = 0
    for r in bundle["records"]:
        fid = r["fixture_id"]
        object_counts = Counter(o.get("semantic_id") for o in r.get("semantic_objects", []) if isinstance(o, dict) and isinstance(o.get("semantic_id"), str))
        player_counts = Counter(p.get("player_id") for p in r.get("players", []) if isinstance(p, dict) and isinstance(p.get("player_id"), str))
        commander_counts = Counter(c.get("commander_id") for c in r.get("commander_state", {}).get("commanders", []) if isinstance(c, dict) and isinstance(c.get("commander_id"), str))
        lineage_counts = Counter(o.get("card_lineage_id") for o in r.get("semantic_objects", []) if isinstance(o, dict) and isinstance(o.get("card_lineage_id"), str))
        step_counts = Counter(s.get("step_id") for s in r.get("native_procedure", []) if isinstance(s, dict) and isinstance(s.get("step_id"), str))
        errors: list[dict[str, Any]] = []
        refs: list[dict[str, Any]] = []

        def add(ns: str, path: str, value: str, matches: int, reason: str | None = None) -> None:
            nonlocal total_refs
            total_refs += 1
            inventory[ns][B.shape(path)] += 1
            status = "PASS" if matches == 1 else "FAIL"
            row: dict[str, Any] = {"namespace": ns, "path": path, "value": value, "match_count": matches, "status": status}
            if reason:
                row["reason"] = reason
            refs.append(row)
            if status != "PASS":
                errors.append(row)

        for ns, counts, path in (
            ("semantic_object", object_counts, "$.semantic_objects"),
            ("player", player_counts, "$.players"),
            ("commander", commander_counts, "$.commander_state.commanders"),
            ("lineage", lineage_counts, "$.semantic_objects[].card_lineage_id"),
            ("native_step", step_counts, "$.native_procedure"),
        ):
            dup = sorted(k for k, v in counts.items() if v > 1)
            if dup:
                errors.append({"namespace": ns, "path": path, "status": "FAIL", "reason": "duplicate declaration", "duplicates": dup})

        seen: set[tuple[str, str, str]] = set()
        for kind, path, text in walk_strings(r):
            if ".aliases" in path or ".alias" in path:
                alias_count += 1
                errors.append({"namespace": "alias", "path": path, "value": text, "status": "FAIL", "reason": "aliases are not authorized or required by v1.0.4"})

            is_obj_decl = kind == "value" and path.startswith("$.semantic_objects[") and path.endswith(".semantic_id")
            is_player_decl = kind == "value" and path.startswith("$.players[") and path.endswith(".player_id")
            is_commander_decl = kind == "value" and path.startswith("$.commander_state.commanders[") and path.endswith(".commander_id")
            is_line_decl = kind == "value" and path.startswith("$.semantic_objects[") and path.endswith(".card_lineage_id")

            if B.OBJ_RE.fullmatch(text) and not is_obj_decl:
                key = ("semantic_object", path, text)
                if key not in seen:
                    seen.add(key); add("semantic_object", path, text, object_counts[text])
            # A line: token is a distinct typed namespace; never recursively reinterpret
            # its internal spelling as an obj: reference.
            if not B.LINE_RE.fullmatch(text):
                for token in OBJ_EMBED_RE.findall(text):
                    if token == text and (is_obj_decl or ("semantic_object", path, token) in seen):
                        continue
                    key = ("semantic_object", path + "#embedded", token)
                    if key not in seen:
                        seen.add(key); add("semantic_object", path + "#embedded", token, object_counts[token])

            if B.CMD_RE.fullmatch(text) and not is_commander_decl:
                key = ("commander", path, text)
                if key not in seen:
                    seen.add(key); add("commander", path, text, commander_counts[text])
            for token in CMD_EMBED_RE.findall(text):
                if token == text and (is_commander_decl or ("commander", path, token) in seen):
                    continue
                key = ("commander", path + "#embedded", token)
                if key not in seen:
                    seen.add(key); add("commander", path + "#embedded", token, commander_counts[token])

            if B.LINE_RE.fullmatch(text) and not is_line_decl:
                key = ("lineage", path, text)
                if key not in seen:
                    seen.add(key); add("lineage", path, text, lineage_counts[text])

            mstack = B.STACK_RE.fullmatch(text)
            if mstack:
                idx = int(mstack.group(1))
                add("stack", path, text, 1 if 1 <= idx <= len(r.get("stack_state", [])) else 0, "1-based initial stack_state ordinal")

            if B.PLAYER_RE.fullmatch(text) and not is_player_decl:
                key = ("player", path, text)
                if key not in seen:
                    seen.add(key); add("player", path, text, player_counts[text])
            for token in B.PLAYER_EMBED_RE.findall(text):
                if token == text and (is_player_decl or ("player", path, token) in seen):
                    continue
                key = ("player", path + "#embedded", token)
                if key not in seen:
                    seen.add(key); add("player", path + "#embedded", token, player_counts[token])

            if kind == "value" and path.endswith(".causal_step_id"):
                add("native_step", path, text, step_counts[text])

        # Hard typing for identity-bearing structured fields. source_objects is an
        # explicit vector and each member is already exact-checked by the generic walk.
        for _kind, path, text in walk_strings(r):
            field = path.rsplit(".", 1)[-1]
            if field in {"source_object", "source_semantic_id", "attached_to"} and not B.OBJ_RE.fullmatch(text):
                errors.append({"namespace": "typed_field", "path": path, "value": text, "status": "FAIL", "reason": f"{field} requires obj: namespace"})
            if field == "viewer" and text in AUDIENCE_SENTINELS:
                audience_count += 1
                inventory["audience_scope"][B.shape(path)] += 1
                continue
            if field in {"actor", "controller", "owner", "active_player", "priority_player", "holder", "viewer", "player_id"} and B.PLAYER_RE.fullmatch(text) is None:
                if any(seg in path for seg in ("semantic_objects", "decision_script", "temporal_state", "stack_state", "knowledge_state", "priority_script", "deck_state", "pregame_decision_plan", "native_procedure", "action_cost_state", "commander_state")):
                    errors.append({"namespace": "typed_field", "path": path, "value": text, "status": "FAIL", "reason": f"{field} requires P<n> player namespace or its closed field-specific sentinel"})

        total_errors += len(errors)
        rows.append({"fixture_id": fid, "reference_count": len(refs), "status": "PASS" if not errors else "FAIL", "errors": errors})

    inventory_artifact = {
        "artifact_version": "commander-lab.ws44-reference-field-inventory/1.0.1",
        "record_count": len(rows),
        "typed_namespaces": ["semantic_object", "player", "audience_scope", "commander", "lineage", "stack", "native_step", "alias"],
        "field_path_shapes": {k: [{"path": p, "count": n} for p, n in sorted(v.items())] for k, v in sorted(inventory.items())},
        "alias_occurrence_count": alias_count,
        "audience_sentinel_occurrence_count": audience_count,
        "closed_audience_sentinels": sorted(AUDIENCE_SENTINELS),
        "embedded_event_reference_parsing": True,
        "embedded_token_terminal_punctuation_excluded": True,
        "lineage_namespace_not_recursively_reinterpreted_as_object_namespace": True,
        "mapping_key_reference_parsing": True,
    }
    audit = {
        "artifact_version": "commander-lab.ws44-referential-integrity-audit/1.0.1",
        "materialization_version": VERSION,
        "record_count": len(rows),
        "reference_count": total_refs,
        "defect_count": total_errors,
        "pass_count": sum(x["status"] == "PASS" for x in rows),
        "records": rows,
        "historical_negative_regression": {"value": "obj:P2-bears", "exact_resolution_expected": 0, "implicit_resolution_forbidden": True},
        "terminal_status": "PASS" if total_errors == 0 and len(rows) == 135 else "FAIL",
    }
    return inventory_artifact, audit


def patch_schema(schema: dict[str, Any]) -> dict[str, Any]:
    schema = copy.deepcopy(schema)
    schema["$id"] = "https://commander-lab.invalid/schema/semantic-fixture-materialization-v1.0.4.json"
    schema["title"] = "Commander Lab Semantic Fixture Materialization v1.0.4"
    schema["properties"]["schema_version"] = {"const": VERSION}
    schema["properties"]["supersedes"] = {"type": "object"}
    schema["$defs"]["record"]["properties"]["materialization_version"] = {"const": VERSION}
    return schema


def build(out: Path) -> None:
    authority = B.verify_predecessor_authority()
    predecessor = B.git_json(B.PRE_COMMIT, B.PRE_MAT_PATH)
    schema = B.git_json(B.PRE_COMMIT, B.PRE_SCHEMA_PATH)
    predecessor_denom = B.git_json(B.PRE_COMMIT, B.PRE_DENOM_PATH)
    if len(predecessor.get("records", [])) != 135:
        raise RuntimeError("predecessor does not contain 135 records")
    micro_adjudication = B.prove_micro_identity(predecessor)

    successor = copy.deepcopy(predecessor)
    successor["schema_version"] = VERSION
    successor["record_count"] = 135
    successor["supersedes"] = {"materialization_version": B.PRE_VERSION, "commit": B.PRE_COMMIT, "tree": B.PRE_TREE, "namespace_tree": B.PRE_NS_TREE, "canonical_bundle_digest": B.PRE_CANONICAL_DIGEST, "materialization_sha256": B.PRE_MAT_SHA256}
    successor.pop("canonical_bundle_digest", None)

    pre_by = {r["fixture_id"]: r for r in predecessor["records"]}
    repair_fixtures = {x[0] for x in B.REPAIRS} | {"MICRO_STATE_BASED_ACTIONS", "CARD_01", "WS05-MP-TRIG-3"}
    for record in successor["records"]:
        record["materialization_version"] = VERSION
        prior = copy.deepcopy(record.get("repair_provenance", {}))
        record["repair_provenance"] = {
            **prior,
            "ws44_predecessor_commit": B.PRE_COMMIT,
            "ws44_repair_class": "REFERENTIAL_INTEGRITY_REPRESENTATION_REPAIR" if record["fixture_id"] in repair_fixtures else "SUCCESSOR_VERSION_AND_REFERENTIAL_LINTER_HARDENING_ONLY",
            "frozen_obligation_preserved": True,
            "provider_semantics_used": False,
        }

    repair_rows: list[dict[str, Any]] = []
    for fid, path, old, new, basis in B.REPAIRS:
        record = B.find_record(successor, fid)
        objects = Counter(o.get("semantic_id") for o in record.get("semantic_objects", []) if isinstance(o, dict))
        if objects[new] != 1 or objects[old] != 0:
            raise RuntimeError(f"{fid}: exact referent preconditions failed for {path}")
        B.set_path(record, path, old, new)
        repair_rows.append({"fixture_id": fid, "repair_kind": "DANGLING_REFERENCE_TO_PROVEN_EXISTING_IDENTITY", "path": path, "old": old, "new": new, "basis": basis, "obligation_changed": False, "provider_semantics_used": False})
    repair_rows.extend(apply_additional_representation_repairs(successor, predecessor))

    lineage_rows = []
    for record in successor["records"]:
        fid = record["fixture_id"]
        pred = pre_by[fid]
        old_ob = B.legacy.obligation_digest(pred)
        new_ob = B.legacy.obligation_digest(record)
        if old_ob != new_ob:
            raise RuntimeError(f"{fid}: frozen obligation changed")
        old_state = B.legacy.requested_state_digest(pred)
        new_state = B.legacy.requested_state_digest(record)
        record["obligation_digest"] = new_ob
        record["requested_state_digest"] = new_state
        record["materialization_digest"] = B.record_digest(record)
        lineage_rows.append({"fixture_id": fid, "predecessor_obligation_digest": old_ob, "successor_obligation_digest": new_ob, "obligation_changed": False, "predecessor_requested_state_digest": old_state, "successor_requested_state_digest": new_state, "requested_state_changed": old_state != new_state, "predecessor_materialization_digest": pred.get("materialization_digest"), "successor_materialization_digest": record["materialization_digest"], "materialization_changed": pred.get("materialization_digest") != record["materialization_digest"]})

    successor["canonical_bundle_digest"] = B.sha256_bytes(B.canonical_bytes({k: v for k, v in successor.items() if k != "canonical_bundle_digest"}))
    field_inventory, ref_audit = reference_audit(successor)
    if ref_audit["terminal_status"] != "PASS":
        B.dump(out / "WS44_REFERENTIAL_INTEGRITY_AUDIT_135.json", ref_audit)
        B.dump(out / "WS44_REFERENCE_FIELD_INVENTORY.json", field_inventory)
        raise RuntimeError(f"referential integrity failed with {ref_audit['defect_count']} defects")

    inherited = B.legacy_lint(successor, predecessor)
    if inherited.get("terminal_status") != "PASS":
        B.dump(out / "WS44_INHERITED_WS41_LINT_REPORT_135.json", inherited)
        raise RuntimeError("inherited WS41 semantic lint failed")
    semantic_report = copy.deepcopy(inherited)
    semantic_report.update({"report_version": "commander-lab.semantic-executability-report/1.0.4", "materialization_version": VERSION, "referential_integrity_defect_count": 0, "semantic_executable_count": 135, "contract_defect_count": 0, "terminal_status": "PASS"})

    pre_ids = [r["fixture_id"] for r in predecessor["records"]]
    post_ids = [r["fixture_id"] for r in successor["records"]]
    if pre_ids != post_ids:
        raise RuntimeError("fixture identity/order changed")
    if Counter(r.get("fixture_family") for r in predecessor["records"]) != Counter(r.get("fixture_family") for r in successor["records"]):
        raise RuntimeError("family counts changed")
    if {r["fixture_id"]: r.get("frozen_contract_binding") for r in predecessor["records"]} != {r["fixture_id"]: r.get("frozen_contract_binding") for r in successor["records"]}:
        raise RuntimeError("AF/frozen contract mapping changed")

    excluded = {f"CARD_{n:02d}" for n in range(1, 30)} - {"CARD_02"}
    denominator_ids = [fid for fid in post_ids if fid not in excluded]
    if len(denominator_ids) != 107 or denominator_ids != predecessor_denom.get("fixture_ids"):
        raise RuntimeError("provider denominator identity/count drift")

    changed_states = [x["fixture_id"] for x in lineage_rows if x["requested_state_changed"]]
    if any(x["obligation_changed"] for x in lineage_rows):
        raise RuntimeError("obligation changes forbidden")

    ws43_reconciliation = {"artifact_version": "commander-lab.ws44-ws43-scope-reconciliation/1.0.0", "ws43": {"commit": B.WS43_TERMINAL, "tree": B.WS43_TREE, "classification": "COMPLETE / TERMINAL_FAIL_DIGEST_INTEGRITY_DEFECT", "G43_01": "FAIL", "successor_contract_frozen": False}, "ws44_new_gate_authority": "OPTION_2 / DETACHED_IMMUTABLE_PREDECESSOR_WITH_STRICT_ATTESTATION_SCOPE", "retroactive_ws43_reinterpretation": False, "terminal_status": "PASS"}
    defect_repro = {"artifact_version": "commander-lab.ws44-ws40-micro-defect-reproduction/1.0.0", "source": {"commit": B.PRE_COMMIT, "materialization_blob": B.PRE_MAT_BLOB}, "ws40_terminal": B.WS40_TERMINAL, "ws42_terminal": B.WS42_TERMINAL, "rows": [{"fixture_id": fid, "path": "stack_state[0].targets[0]", "value": "obj:P2-bears", "exact_declaration_count": 0, "classification": "DANGLING_REFERENCE"} for fid in ("MICRO_PRIORITY", "MICRO_STACK")], "provider_side_resolution_forbidden": True, "terminal_status": "PASS"}
    ref_rules = {
        "artifact_version": "commander-lab.ws44-referential-integrity-linter-rules/1.0.1",
        "case_sensitive": True,
        "exactly_one_resolution_required": True,
        "namespaces": {"semantic_object": "semantic_objects[].semantic_id; exact/embedded references and mapping keys", "player": "players[].player_id", "audience_scope": "closed field-specific sentinels; currently ALL_PLAYERS only", "commander": "commander_state.commanders[].commander_id", "lineage": "semantic_objects[].card_lineage_id; independent typed namespace", "stack": "1-based stack:<n> references into initial stack_state", "native_step": "native_procedure[].step_id referenced by causal_step_id", "alias": "not present or authorized in v1.0.4"},
        "source_object_rule": "scalar source_object/source_semantic_id/attached_to must be exact obj: identity; multi-source native steps use source_objects[] with each member resolving exactly once",
        "embedded_token_rule": "event-token obj:/cmd: references terminate on alnum/underscore; syntax delimiters and sentence punctuation are excluded; line: values are never recursively reinterpreted as obj: values",
        "forbidden_resolution": ["case_folding", "card_name_matching", "owner_matching", "controller_matching", "first_candidate", "positional_matching", "provider_native_identity_guessing", "request_echo", "hidden_provider_alias"],
        "negative_regression": {"value": "obj:P2-bears", "must_fail_resolution": True},
    }
    digest_lineage = {"artifact_version": "commander-lab.ws44-digest-lineage/1.0.0", "predecessor": {"version": B.PRE_VERSION, "commit": B.PRE_COMMIT, "tree": B.PRE_TREE, "namespace_tree": B.PRE_NS_TREE, "materialization_sha256": B.PRE_MAT_SHA256, "canonical_bundle_digest": B.PRE_CANONICAL_DIGEST}, "successor": {"version": VERSION, "canonical_bundle_digest": successor["canonical_bundle_digest"]}, "record_count": 135, "requested_state_changed_count": len(changed_states), "requested_state_changed_fixture_ids": changed_states, "obligation_changed_count": 0, "obligation_changed_fixture_ids": [], "rows": lineage_rows}
    supersedes = {"artifact_version": "commander-lab.semantic-supersession/1.0.4", "predecessor": {"version": B.PRE_VERSION, "commit": B.PRE_COMMIT, "tree": B.PRE_TREE, "namespace_tree": B.PRE_NS_TREE, "canonical_bundle_digest": B.PRE_CANONICAL_DIGEST, "materialization_sha256": B.PRE_MAT_SHA256}, "successor": {"version": VERSION, "record_count": 135, "semantic_executable_count": 135, "referential_integrity_defect_count": 0}, "fixture_id_set_preserved": True, "family_counts_preserved": True, "af_frozen_contract_mapping_preserved": True, "obligation_changed": False, "representation_repair_rows": repair_rows}
    denominator = {"artifact_version": "commander-lab.ws44-provider-denominator/1.0.0", "materialization_version": VERSION, "materialization_record_count": 135, "provider_denominator_count": 107, "fixture_ids": denominator_ids, "excluded_fixture_ids": sorted(excluded), "identity_derivation": "All 135 v1.0.4 IDs minus CARD_01..CARD_29 except retained successor sentinel CARD_02.", "predecessor_identity_set_equal": True, "denominator_decreased_to_bypass_blocker": False}
    source_lock = {"artifact_version": "commander-lab.ws44-source-lock/1.0.0", "repository": "moeendres-png/commander-playtest-lab", "current_main": {"commit": B.MAIN_COMMIT, "tree": B.MAIN_TREE}, "predecessor": {"commit": B.PRE_COMMIT, "tree": B.PRE_TREE, "namespace_tree": B.PRE_NS_TREE, "materialization_blob": B.PRE_MAT_BLOB, "materialization_sha256": B.PRE_MAT_SHA256, "canonical_bundle_digest": B.PRE_CANONICAL_DIGEST}, "later_ws41_attestation": {"commit": B.TERMINAL_WS41_COMMIT, "tree": B.TERMINAL_WS41_TREE, "namespace_tree": B.TERMINAL_WS41_NS_TREE}, "ws40": {"terminal": B.WS40_TERMINAL, "atomic_evidence": B.WS40_ATOMIC_EVIDENCE}, "ws42": {"terminal": B.WS42_TERMINAL, "tree": B.WS42_TREE}, "ws43": {"terminal": B.WS43_TERMINAL, "tree": B.WS43_TREE}, "source_mode": "DETACHED_EXACT_GIT_OBJECT_VIA_GIT_SHOW"}
    validation = {"artifact_version": "commander-lab.ws44-validation/1.0.0", "materialization_version": VERSION, "static_gates": {f"G44-{i:02d}": "PASS" for i in list(range(1, 13)) + [14]}, "workflow_gates": {"G44-13": "REQUIRES_DOUBLE_MATERIALIZATION_CI", "G44-15": "REQUIRES_PERSISTENT_FREEZE_AND_POSTFREEZE_REGENERATION"}, "global_referential_integrity_defects": 0, "semantic_executability": "135/135", "provider_denominator": 107, "provider_runtime_executed": False, "provider_pass_imported": False, "AF07_GRANTED": False, "ARCHITECTURE_FREEZE": False, "static_terminal_status": "PASS"}

    outputs = {
        "SEMANTIC_FIXTURE_SCHEMA_v1_0_4.json": patch_schema(schema),
        "SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_4.json": successor,
        "WS44_SOURCE_LOCK.json": source_lock,
        "WS44_PREDECESSOR_AUTHORITY_VERIFICATION.json": authority,
        "WS44_WS43_SCOPE_RECONCILIATION.json": ws43_reconciliation,
        "WS44_WS40_MICRO_DEFECT_REPRODUCTION.json": defect_repro,
        "WS44_MICRO_TARGET_IDENTITY_ADJUDICATION.json": micro_adjudication,
        "WS44_REFERENCE_FIELD_INVENTORY.json": field_inventory,
        "WS44_REFERENTIAL_INTEGRITY_LINTER_RULES.json": ref_rules,
        "WS44_REFERENTIAL_INTEGRITY_AUDIT_135.json": ref_audit,
        "WS44_INHERITED_WS41_LINT_REPORT_135.json": inherited,
        "WS44_SEMANTIC_EXECUTABILITY_REPORT_135.json": semantic_report,
        "WS44_PROVIDER_DENOMINATOR_107.json": denominator,
        "WS44_DIGEST_LINEAGE.json": digest_lineage,
        "SUPERSEDES_v1_0_3.json": supersedes,
        "WS44_REPAIR_MATRIX.json": {"artifact_version": "commander-lab.ws44-repair-matrix/1.0.1", "repair_count": len(repair_rows), "changed_fixture_count": len(set(x["fixture_id"] for x in repair_rows)), "rows": repair_rows, "obligation_changed": False},
        "WS44_VALIDATION.json": validation,
    }
    for name, value in outputs.items():
        B.dump(out / name, value)

    mat_sha = B.sha256_bytes((out / "SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_4.json").read_bytes())
    lineage = json.loads((out / "WS44_DIGEST_LINEAGE.json").read_text(encoding="utf-8")); lineage["successor"]["materialization_sha256"] = mat_sha; B.dump(out / "WS44_DIGEST_LINEAGE.json", lineage)
    supersedes2 = json.loads((out / "SUPERSEDES_v1_0_3.json").read_text(encoding="utf-8")); supersedes2["successor"]["materialization_sha256"] = mat_sha; supersedes2["successor"]["canonical_bundle_digest"] = successor["canonical_bundle_digest"]; B.dump(out / "SUPERSEDES_v1_0_3.json", supersedes2)

    files = sorted(p for p in out.iterdir() if p.is_file() and p.name not in {"WS44_SHA256SUMS", "WS44_EVIDENCE_INDEX.json"})
    checksum_rows = [{"path": p.name, "sha256": B.sha256_bytes(p.read_bytes())} for p in files]
    (out / "WS44_SHA256SUMS").write_text("".join(f"{r['sha256']}  {r['path']}\n" for r in checksum_rows), encoding="utf-8")
    index_files = [{"path": r["path"], "sha256": r["sha256"], "role": "canonical_ws44_freeze_evidence"} for r in checksum_rows]
    index_files.append({"path": "WS44_SHA256SUMS", "sha256": B.sha256_bytes((out / "WS44_SHA256SUMS").read_bytes()), "role": "sealed_checksum_manifest"})
    B.dump(out / "WS44_EVIDENCE_INDEX.json", {"artifact_version": "commander-lab.ws44-evidence-index/1.0.0", "contract_version": VERSION, "files": index_files, "postfreeze_ci_attestation_external": "candidate-qualification/ws44-v1.0.4-authority/WS44_POSTFREEZE_ATTESTATION.json"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    build(args.output)
