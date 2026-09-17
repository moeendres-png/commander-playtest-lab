#!/usr/bin/env python3
"""Build provider-neutral WS-44 semantic fixture materialization v1.0.4.

All predecessor bytes are consumed only from the exact immutable WS-41 Git object.
No descendant working-tree qualification/ws41 file is a semantic input.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterator

import ws41_lint_semantic_v1_0_3 as legacy

VERSION = "commander-lab.semantic-fixture-materialization/1.0.4"
PRE_VERSION = "commander-lab.semantic-fixture-materialization/1.0.3"
PRE_COMMIT = "24152acf36b5a560c23ccacfed3f31d3039537eb"
PRE_TREE = "428bbe58b2ea7b869200521092a8768108029b47"
PRE_NS_TREE = "af8a26e7e74a859d5f4a983b69e4ff108e7123f4"
PRE_MAT_PATH = "qualification/ws41/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_3.json"
PRE_SCHEMA_PATH = "qualification/ws41/SEMANTIC_FIXTURE_SCHEMA_v1_0_3.json"
PRE_DENOM_PATH = "qualification/ws41/WS41_PROVIDER_DENOMINATOR_107.json"
PRE_MAT_BLOB = "a05106d42ff3e51fe68acf45bb03aa356784142c"
PRE_MAT_SHA256 = "8f6e3778e96079dbb501b9f5d72f007da0549e26b836011a855c0dbd2c6237c5"
PRE_CANONICAL_DIGEST = "545afdeda53a11a2ebb32f534aa1b3186f434aa90bec2c8f2f232851e1abd31b"
TERMINAL_WS41_COMMIT = "de478cf084529067776866aefb04d5c92efafeea"
TERMINAL_WS41_TREE = "39642b1fce2056a2b43d38f1ad2910bf94001b65"
TERMINAL_WS41_NS_TREE = "cf40fe6157d4681dda31c1fe2b2aacb9cecbb374"
WS40_TERMINAL = "87b0a571cb3f9d18378150e3546fbe8fac4b6366"
WS40_ATOMIC_EVIDENCE = "fbb4b9c8534b11b8daf70a162fdb081d34ac2ab7"
WS42_TERMINAL = "a455f596389fde2d61703a0e6918415db2fd18c2"
WS42_TREE = "af62bcea93c5416289264492fbc066a1dbd5b2d0"
WS43_TERMINAL = "a96f0db9a4d2cb8ef646281ab5bf0ee351d0a52e"
WS43_TREE = "cafdbcd9e08bbd1da64a8ef4dcd50f1e63e44f2e"
MAIN_COMMIT = "c83e52ae79ff2242578757c0f517badbb1a2621c"
MAIN_TREE = "551c0d55a171508618d2b7d29e0f49b19893f886"

IMMUTABLE_13 = [
    "SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_3.json",
    "SEMANTIC_FIXTURE_SCHEMA_v1_0_3.json",
    "SUPERSEDES_v1_0_2.json",
    "WS41_DIGEST_LINEAGE.json",
    "WS41_PILOT_CHOICE_SUPERSESSION_PROOF.json",
    "WS41_PROVIDER_DENOMINATOR_107.json",
    "WS41_REMAINING_DEFECTS_2.json",
    "WS41_SEMANTIC_EXECUTABILITY_REPORT_135.json",
    "WS41_SEMANTIC_LINTER_RULES.json",
    "WS41_SOURCE_LOCK.json",
    "WS41_TARGETED_STACK_STATE_AUDIT_135.json",
    "WS41_WS32_CONTENT_INTEGRITY_COMPARISON.json",
    "WS41_WS39_CONTRADICTION_REPRODUCTION.json",
]
ALLOWLIST_5 = [
    "WS41_BUNDLE_MANIFEST_v1_0_3.json",
    "WS41_EVIDENCE_INDEX.json",
    "WS41_FINAL_HANDOFF.md",
    "WS41_SHA256SUMS",
    "WS41_VALIDATION.json",
]
OBJ_RE = re.compile(r"^obj:[A-Za-z0-9_.-]+$")
OBJ_EMBED_RE = re.compile(r"obj:[A-Za-z0-9_.-]+")
CMD_RE = re.compile(r"^cmd:[A-Za-z0-9_.-]+$")
CMD_EMBED_RE = re.compile(r"cmd:[A-Za-z0-9_.-]+")
LINE_RE = re.compile(r"^line:[A-Za-z0-9_.:-]+$")
STACK_RE = re.compile(r"^stack:([1-9][0-9]*)$")
PLAYER_RE = re.compile(r"^P[1-9][0-9]*$")
PLAYER_EMBED_RE = re.compile(r"(?<![A-Za-z0-9_])P[1-9][0-9]*(?![A-Za-z0-9_])")

REPAIRS = [
    ("PILOT_REPLACEMENT_EFFECT", "stack_state[0].targets[0]", "obj:P1-commander", "obj:p1-commander-bf", "Native Procedure resumes Unsummon with obj:p1-commander-bf as its exact target."),
    ("MICRO_MANA_PAYMENT", "action_cost_state[0].source_semantic_id", "obj:micro-counter", "obj:micro-counterspell", "Declared Counterspell semantic object is obj:micro-counterspell."),
    ("MICRO_MANA_PAYMENT", "decision_script[0].selection.semantic_value.object", "obj:micro-counter", "obj:micro-counterspell", "The cast action must bind the declared Counterspell object."),
    ("MICRO_MANA_PAYMENT", "native_procedure[0].source_object", "obj:micro-counter", "obj:micro-counterspell", "The native Counterspell cast procedure must bind the declared Counterspell object."),
    ("MICRO_PRIORITY", "stack_state[0].targets[0]", "obj:P2-bears", "obj:micro-target", "Frozen Native Procedure and target decision both bind obj:micro-target; obj:p2-bears is a distinct object."),
    ("MICRO_STACK", "stack_state[0].targets[0]", "obj:P2-bears", "obj:micro-target", "Frozen Native Procedure and target decision both bind obj:micro-target; obj:p2-bears is a distinct object."),
    ("MICRO_TRIGGERS", "native_procedure[2].source_object", "obj:micro-surge", "obj:micro-warstorm", "Declared Warstorm Surge semantic object is obj:micro-warstorm."),
    ("WS05-MP-BLOCK-4", "combat_state.eligible_blockers[0]", "obj:mp-blocker", "obj:mp-p2-blocker", "Decision and native blocker assignment both bind obj:mp-p2-blocker."),
]


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args])


def git_text(*args: str) -> str:
    return git(*args).decode("utf-8").strip()


def git_json(commit: str, path: str) -> Any:
    return json.loads(git("show", f"{commit}:{path}").decode("utf-8"))


def canonical_bytes(value: Any) -> bytes:
    return legacy.canonical_bytes(value)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value) + b"\n")


def record_digest(record: dict[str, Any]) -> str:
    clone = copy.deepcopy(record)
    clone.pop("materialization_digest", None)
    return sha256_bytes(canonical_bytes(clone))


def find_record(bundle: dict[str, Any], fixture_id: str) -> dict[str, Any]:
    matches = [r for r in bundle["records"] if r.get("fixture_id") == fixture_id]
    if len(matches) != 1:
        raise RuntimeError(f"{fixture_id}: expected exactly one record, got {len(matches)}")
    return matches[0]


def ls_tree(commit: str, path: str) -> dict[str, str]:
    text = git("ls-tree", commit, path).decode("utf-8")
    # when path is a tree, resolve and list its direct children
    tree = git_text("rev-parse", f"{commit}:{path}")
    rows = git("ls-tree", tree).decode("utf-8").splitlines()
    out: dict[str, str] = {}
    for row in rows:
        meta, name = row.split("\t", 1)
        _mode, _type, sha = meta.split()
        out[name] = sha
    return out


def verify_predecessor_authority() -> dict[str, Any]:
    if git_text("show", "-s", "--format=%T", PRE_COMMIT) != PRE_TREE:
        raise RuntimeError("pinned predecessor tree mismatch")
    if git_text("rev-parse", f"{PRE_COMMIT}:qualification/ws41") != PRE_NS_TREE:
        raise RuntimeError("pinned predecessor namespace tree mismatch")
    pred_files = ls_tree(PRE_COMMIT, "qualification/ws41")
    if len(pred_files) != 18 or set(pred_files) != set(IMMUTABLE_13 + ALLOWLIST_5):
        raise RuntimeError("pinned predecessor qualification/ws41 is not exact 18-file authority namespace")
    if pred_files["SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_3.json"] != PRE_MAT_BLOB:
        raise RuntimeError("pinned materialization blob mismatch")
    raw = git("show", f"{PRE_COMMIT}:{PRE_MAT_PATH}")
    if sha256_bytes(raw) != PRE_MAT_SHA256:
        raise RuntimeError("pinned materialization SHA256 mismatch")
    bundle = json.loads(raw.decode("utf-8"))
    if bundle.get("canonical_bundle_digest") != PRE_CANONICAL_DIGEST:
        raise RuntimeError("pinned canonical bundle digest mismatch")

    if git_text("show", "-s", "--format=%T", TERMINAL_WS41_COMMIT) != TERMINAL_WS41_TREE:
        raise RuntimeError("later WS41 terminal tree mismatch")
    if git_text("rev-parse", f"{TERMINAL_WS41_COMMIT}:qualification/ws41") != TERMINAL_WS41_NS_TREE:
        raise RuntimeError("later WS41 namespace tree mismatch")
    later_files = ls_tree(TERMINAL_WS41_COMMIT, "qualification/ws41")
    if set(later_files) != set(pred_files):
        raise RuntimeError("later WS41 namespace path set drift")
    immutable_rows = [{"path": p, "predecessor_blob": pred_files[p], "later_blob": later_files[p], "byte_identical": pred_files[p] == later_files[p]} for p in IMMUTABLE_13]
    allow_rows = [{"path": p, "predecessor_blob": pred_files[p], "later_blob": later_files[p], "changed": pred_files[p] != later_files[p]} for p in ALLOWLIST_5]
    changed = sorted(p for p in pred_files if pred_files[p] != later_files[p])
    if not all(r["byte_identical"] for r in immutable_rows):
        raise RuntimeError("immutable 13-file semantic/support payload drift")
    if changed != sorted(ALLOWLIST_5) or not all(r["changed"] for r in allow_rows):
        raise RuntimeError(f"attestation drift outside/short of exact allowlist: {changed}")
    validation = git_json(TERMINAL_WS41_COMMIT, "qualification/ws41/WS41_VALIDATION.json")
    validation_text = json.dumps(validation, sort_keys=True)
    if PRE_COMMIT not in validation_text or PRE_TREE not in validation_text:
        raise RuntimeError("later WS41 validation does not point downstream to exact predecessor lock")
    return {
        "artifact_version": "commander-lab.ws44-predecessor-authority-verification/1.0.0",
        "coordinator_authority": "OPTION_2 / DETACHED_IMMUTABLE_PREDECESSOR_WITH_STRICT_ATTESTATION_SCOPE",
        "predecessor": {"commit": PRE_COMMIT, "tree": PRE_TREE, "namespace_tree": PRE_NS_TREE, "file_count": 18, "materialization_blob": PRE_MAT_BLOB, "materialization_sha256": PRE_MAT_SHA256, "canonical_bundle_digest": PRE_CANONICAL_DIGEST},
        "later_attestation": {"commit": TERMINAL_WS41_COMMIT, "tree": TERMINAL_WS41_TREE, "namespace_tree": TERMINAL_WS41_NS_TREE},
        "immutable_13": immutable_rows,
        "allowlisted_5": allow_rows,
        "changed_paths": changed,
        "validation_downstream_lock_exact": True,
        "terminal_status": "PASS",
    }


def get_path(record: dict[str, Any], path: str) -> Any:
    cur: Any = record
    for token in re.findall(r"[^.\[\]]+|\[[0-9]+\]", path):
        if token.startswith("["):
            cur = cur[int(token[1:-1])]
        else:
            cur = cur[token]
    return cur


def set_path(record: dict[str, Any], path: str, expected: Any, new: Any) -> None:
    tokens = re.findall(r"[^.\[\]]+|\[[0-9]+\]", path)
    cur: Any = record
    for token in tokens[:-1]:
        cur = cur[int(token[1:-1])] if token.startswith("[") else cur[token]
    last = tokens[-1]
    actual = cur[int(last[1:-1])] if last.startswith("[") else cur[last]
    if actual != expected:
        raise RuntimeError(f"{path}: predecessor value mismatch: expected={expected!r} actual={actual!r}")
    if last.startswith("["):
        cur[int(last[1:-1])] = new
    else:
        cur[last] = new


def prove_micro_identity(predecessor: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for fid in ("MICRO_PRIORITY", "MICRO_STACK"):
        r = find_record(predecessor, fid)
        objs = {o["semantic_id"]: o for o in r.get("semantic_objects", [])}
        if "obj:P2-bears" in objs:
            raise RuntimeError(f"{fid}: defect no longer dangling")
        for required in ("obj:p2-bears", "obj:micro-target"):
            if required not in objs:
                raise RuntimeError(f"{fid}: missing plausible referent {required}")
        if objs["obj:p2-bears"] == objs["obj:micro-target"] or "obj:p2-bears" == "obj:micro-target":
            raise RuntimeError(f"{fid}: plausible referents are not distinct")
        old_target = r.get("stack_state", [])[0].get("targets", [None])[0]
        native_target = r.get("native_procedure", [])[0].get("details", {}).get("targets", [None])[0]
        target_choices = [d.get("selection", {}).get("semantic_value") for d in r.get("decision_script", []) if d.get("decision_family") == "target"]
        if old_target != "obj:P2-bears" or native_target != "obj:micro-target" or target_choices != ["obj:micro-target"]:
            raise RuntimeError(f"{fid}: frozen record-local identity relations do not prove obj:micro-target")
        for sid in ("obj:p2-bears", "obj:micro-target"):
            obj = objs[sid]
            if obj.get("card_identity") != "Grizzly Bears" or obj.get("controller") != "P2" or obj.get("zone") != "battlefield":
                raise RuntimeError(f"{fid}: plausible referent shape changed for {sid}")
        rows.append({
            "fixture_id": fid,
            "dangling_requested_target": old_target,
            "plausible_referents": [
                {"semantic_id": "obj:p2-bears", "card_identity": objs["obj:p2-bears"]["card_identity"], "controller": objs["obj:p2-bears"]["controller"], "zone": objs["obj:p2-bears"]["zone"]},
                {"semantic_id": "obj:micro-target", "card_identity": objs["obj:micro-target"]["card_identity"], "controller": objs["obj:micro-target"]["controller"], "zone": objs["obj:micro-target"]["zone"]},
            ],
            "native_procedure_exact_target": native_target,
            "decision_script_exact_target": target_choices[0],
            "intended_target": "obj:micro-target",
            "basis": "record-local frozen Native Procedure and target decision converge exactly on obj:micro-target; obj:p2-bears remains a distinct semantic identity, so case/name/controller heuristics are forbidden and unnecessary",
            "provider_semantics_used": False,
        })
    return {"artifact_version": "commander-lab.ws44-micro-target-identity-adjudication/1.0.0", "rows": rows, "authority_resolution": "PROVEN_PROVIDER_NEUTRALLY", "terminal_status": "PASS"}


def walk_strings(value: Any, path: str = "$") -> Iterator[tuple[str, str, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(key, str):
                yield "key", f"{path}.<key:{key}>", key
            yield from walk_strings(child, f"{path}.{key}")
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from walk_strings(child, f"{path}[{i}]")
    elif isinstance(value, str):
        yield "value", path, value


def shape(path: str) -> str:
    return re.sub(r"\[[0-9]+\]", "[]", path)


def reference_audit(bundle: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = []
    inventory: dict[str, Counter[str]] = defaultdict(Counter)
    total_refs = 0
    total_errors = 0
    alias_count = 0
    for r in bundle["records"]:
        fid = r["fixture_id"]
        objects = [o.get("semantic_id") for o in r.get("semantic_objects", []) if isinstance(o, dict)]
        object_counts = Counter(x for x in objects if isinstance(x, str))
        players = [p.get("player_id") for p in r.get("players", []) if isinstance(p, dict)]
        player_counts = Counter(x for x in players if isinstance(x, str))
        commander_decls = [c.get("commander_id") for c in r.get("commander_state", {}).get("commanders", []) if isinstance(c, dict)]
        commander_counts = Counter(x for x in commander_decls if isinstance(x, str))
        lineage_decls = [o.get("card_lineage_id") for o in r.get("semantic_objects", []) if isinstance(o, dict) and isinstance(o.get("card_lineage_id"), str)]
        lineage_counts = Counter(lineage_decls)
        step_decls = [s.get("step_id") for s in r.get("native_procedure", []) if isinstance(s, dict) and isinstance(s.get("step_id"), str)]
        step_counts = Counter(step_decls)
        errors: list[dict[str, Any]] = []
        refs: list[dict[str, Any]] = []

        def add(kind: str, path: str, value: str, matches: int, reason: str | None = None) -> None:
            nonlocal total_refs
            total_refs += 1
            inventory[kind][shape(path)] += 1
            status = "PASS" if matches == 1 else "FAIL"
            row = {"namespace": kind, "path": path, "value": value, "match_count": matches, "status": status}
            if reason:
                row["reason"] = reason
            refs.append(row)
            if status != "PASS":
                errors.append(row)

        if any(v > 1 for v in object_counts.values()):
            errors.append({"namespace": "semantic_object", "path": "$.semantic_objects", "status": "FAIL", "reason": "duplicate semantic object declaration", "duplicates": sorted(k for k, v in object_counts.items() if v > 1)})
        if any(v > 1 for v in player_counts.values()):
            errors.append({"namespace": "player", "path": "$.players", "status": "FAIL", "reason": "duplicate player declaration"})
        if any(v > 1 for v in commander_counts.values()):
            errors.append({"namespace": "commander", "path": "$.commander_state.commanders", "status": "FAIL", "reason": "duplicate commander declaration"})
        if any(v > 1 for v in step_counts.values()):
            errors.append({"namespace": "native_step", "path": "$.native_procedure", "status": "FAIL", "reason": "duplicate native step declaration"})

        seen_ref_keys: set[tuple[str, str, str]] = set()
        for kind, path, text in walk_strings(r):
            # Explicit aliases are not present in v1.0.3/v1.0.4. Any future alias-shaped field fails closed until schema/rules are extended.
            if ".aliases" in path or ".alias" in path:
                alias_count += 1
                errors.append({"namespace": "alias", "path": path, "value": text, "status": "FAIL", "reason": "alias mechanism is not declared by v1.0.4 schema/rules"})

            is_obj_decl = kind == "value" and path.startswith("$.semantic_objects[") and path.endswith(".semantic_id")
            is_player_decl = kind == "value" and path.startswith("$.players[") and path.endswith(".player_id")
            is_commander_decl = kind == "value" and path.startswith("$.commander_state.commanders[") and path.endswith(".commander_id")
            is_line_decl = kind == "value" and path.startswith("$.semantic_objects[") and path.endswith(".card_lineage_id")
            is_step_decl = kind == "value" and path.startswith("$.native_procedure[") and path.endswith(".step_id")

            # Exact object references, including mapping keys.
            if OBJ_RE.fullmatch(text) and not is_obj_decl:
                key = ("semantic_object", path, text)
                if key not in seen_ref_keys:
                    seen_ref_keys.add(key); add("semantic_object", path, text, object_counts[text])
            # Embedded object references in events/channels/lineage tokens.
            for token in OBJ_EMBED_RE.findall(text):
                if token == text and (is_obj_decl or ("semantic_object", path, token) in seen_ref_keys):
                    continue
                key = ("semantic_object", path + "#embedded", token)
                if key not in seen_ref_keys:
                    seen_ref_keys.add(key); add("semantic_object", path + "#embedded", token, object_counts[token])

            if CMD_RE.fullmatch(text) and not is_commander_decl:
                key = ("commander", path, text)
                if key not in seen_ref_keys:
                    seen_ref_keys.add(key); add("commander", path, text, commander_counts[text])
            for token in CMD_EMBED_RE.findall(text):
                if token == text and (is_commander_decl or ("commander", path, token) in seen_ref_keys):
                    continue
                key = ("commander", path + "#embedded", token)
                if key not in seen_ref_keys:
                    seen_ref_keys.add(key); add("commander", path + "#embedded", token, commander_counts[token])

            if LINE_RE.fullmatch(text) and not is_line_decl:
                key = ("lineage", path, text)
                if key not in seen_ref_keys:
                    seen_ref_keys.add(key); add("lineage", path, text, lineage_counts[text])

            mstack = STACK_RE.fullmatch(text)
            if mstack:
                idx = int(mstack.group(1))
                add("stack", path, text, 1 if 1 <= idx <= len(r.get("stack_state", [])) else 0, "1-based stack_state ordinal")

            # Structured and embedded player references. Avoid treating declaration itself as a reference.
            if PLAYER_RE.fullmatch(text) and not is_player_decl:
                key = ("player", path, text)
                if key not in seen_ref_keys:
                    seen_ref_keys.add(key); add("player", path, text, player_counts[text])
            for token in PLAYER_EMBED_RE.findall(text):
                if token == text and (is_player_decl or ("player", path, token) in seen_ref_keys):
                    continue
                key = ("player", path + "#embedded", token)
                if key not in seen_ref_keys:
                    seen_ref_keys.add(key); add("player", path + "#embedded", token, player_counts[token])

            if kind == "value" and path.endswith(".causal_step_id"):
                add("native_step", path, text, step_counts[text])

        # Type-sensitive hard checks for the most important reference-bearing fields.
        for _kind, path, text in walk_strings(r):
            field = path.rsplit(".", 1)[-1]
            if field in {"source_object", "source_semantic_id", "attached_to"} and not OBJ_RE.fullmatch(text):
                errors.append({"namespace": "typed_field", "path": path, "value": text, "status": "FAIL", "reason": f"{field} requires obj: namespace"})
            if field in {"actor", "controller", "owner", "active_player", "priority_player", "holder", "viewer", "player_id"} and path != "$.players[].player_id" and PLAYER_RE.fullmatch(text) is None:
                # Only identity-like values are type checked; non-player uses of generic words are ignored by requiring known structured suffix.
                if any(seg in path for seg in ("semantic_objects", "decision_script", "temporal_state", "stack_state", "knowledge_state", "priority_script", "deck_state", "pregame_decision_plan", "native_procedure", "action_cost_state", "commander_state")):
                    errors.append({"namespace": "typed_field", "path": path, "value": text, "status": "FAIL", "reason": f"{field} requires P<n> player namespace"})

        total_errors += len(errors)
        rows.append({"fixture_id": fid, "reference_count": len(refs), "status": "PASS" if not errors else "FAIL", "errors": errors})

    inventory_artifact = {
        "artifact_version": "commander-lab.ws44-reference-field-inventory/1.0.0",
        "record_count": len(rows),
        "typed_namespaces": ["semantic_object", "player", "commander", "lineage", "stack", "native_step", "alias"],
        "field_path_shapes": {k: [{"path": p, "count": n} for p, n in sorted(v.items())] for k, v in sorted(inventory.items())},
        "alias_occurrence_count": alias_count,
        "embedded_event_reference_parsing": True,
        "mapping_key_reference_parsing": True,
    }
    audit = {
        "artifact_version": "commander-lab.ws44-referential-integrity-audit/1.0.0",
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
    props = schema.get("properties", {})
    if "schema_version" in props:
        props["schema_version"] = {"const": VERSION}
    rprops = props.get("records", {}).get("items", {}).get("properties", {})
    if "materialization_version" in rprops:
        rprops["materialization_version"] = {"const": VERSION}
    return schema


def legacy_lint(successor: dict[str, Any], predecessor: dict[str, Any]) -> dict[str, Any]:
    shim = copy.deepcopy(successor)
    shim["schema_version"] = legacy.VERSION
    for record in shim["records"]:
        record["materialization_version"] = legacy.VERSION
    report = legacy.lint_bundle(shim, predecessor)
    if report.get("terminal_status") != "PASS":
        return report
    out = copy.deepcopy(report)
    out["report_version"] = "commander-lab.ws44-inherited-ws41-semantic-lint/1.0.0"
    out["materialization_version"] = VERSION
    out["legacy_compatibility_projection"] = "Only version discriminator shimmed to v1.0.3; requested-state and obligation projections are unchanged."
    return out


def build(out: Path) -> None:
    authority = verify_predecessor_authority()
    predecessor = git_json(PRE_COMMIT, PRE_MAT_PATH)
    schema = git_json(PRE_COMMIT, PRE_SCHEMA_PATH)
    predecessor_denom = git_json(PRE_COMMIT, PRE_DENOM_PATH)
    if len(predecessor.get("records", [])) != 135:
        raise RuntimeError("predecessor does not contain 135 records")
    micro_adjudication = prove_micro_identity(predecessor)

    successor = copy.deepcopy(predecessor)
    successor["schema_version"] = VERSION
    successor["record_count"] = 135
    successor["supersedes"] = {"materialization_version": PRE_VERSION, "commit": PRE_COMMIT, "tree": PRE_TREE, "namespace_tree": PRE_NS_TREE, "canonical_bundle_digest": PRE_CANONICAL_DIGEST, "materialization_sha256": PRE_MAT_SHA256}
    successor.pop("canonical_bundle_digest", None)

    pre_by = {r["fixture_id"]: r for r in predecessor["records"]}
    for record in successor["records"]:
        record["materialization_version"] = VERSION
        prior = copy.deepcopy(record.get("repair_provenance", {}))
        record["repair_provenance"] = {
            **prior,
            "ws44_predecessor_commit": PRE_COMMIT,
            "ws44_repair_class": "REFERENTIAL_INTEGRITY_REPRESENTATION_REPAIR" if record["fixture_id"] in {x[0] for x in REPAIRS} else "SUCCESSOR_VERSION_AND_REFERENTIAL_LINTER_HARDENING_ONLY",
            "frozen_obligation_preserved": True,
            "provider_semantics_used": False,
        }

    repair_rows = []
    for fid, path, old, new, basis in REPAIRS:
        record = find_record(successor, fid)
        objects = Counter(o.get("semantic_id") for o in record.get("semantic_objects", []) if isinstance(o, dict))
        if objects[new] != 1:
            raise RuntimeError(f"{fid}: repaired referent {new} does not resolve exactly once")
        if objects[old] != 0:
            raise RuntimeError(f"{fid}: old dangling value unexpectedly declares an object")
        set_path(record, path, old, new)
        repair_rows.append({"fixture_id": fid, "path": path, "old": old, "new": new, "basis": basis, "provider_semantics_used": False})

    lineage_rows = []
    for record in successor["records"]:
        fid = record["fixture_id"]
        pred = pre_by[fid]
        old_ob = legacy.obligation_digest(pred)
        new_ob = legacy.obligation_digest(record)
        if old_ob != new_ob:
            raise RuntimeError(f"{fid}: frozen obligation changed")
        old_state = legacy.requested_state_digest(pred)
        new_state = legacy.requested_state_digest(record)
        record["obligation_digest"] = new_ob
        record["requested_state_digest"] = new_state
        record["materialization_digest"] = record_digest(record)
        lineage_rows.append({
            "fixture_id": fid,
            "predecessor_obligation_digest": old_ob,
            "successor_obligation_digest": new_ob,
            "obligation_changed": False,
            "predecessor_requested_state_digest": old_state,
            "successor_requested_state_digest": new_state,
            "requested_state_changed": old_state != new_state,
            "predecessor_materialization_digest": pred.get("materialization_digest"),
            "successor_materialization_digest": record["materialization_digest"],
            "materialization_changed": pred.get("materialization_digest") != record["materialization_digest"],
        })

    successor["canonical_bundle_digest"] = sha256_bytes(canonical_bytes({k: v for k, v in successor.items() if k != "canonical_bundle_digest"}))

    # Recompute after top-level digest only; record digests intentionally do not include bundle digest.
    field_inventory, ref_audit = reference_audit(successor)
    if ref_audit["terminal_status"] != "PASS":
        dump(out / "WS44_REFERENTIAL_INTEGRITY_AUDIT_135.json", ref_audit)
        dump(out / "WS44_REFERENCE_FIELD_INVENTORY.json", field_inventory)
        raise RuntimeError(f"referential integrity failed with {ref_audit['defect_count']} defects")

    inherited = legacy_lint(successor, predecessor)
    if inherited.get("terminal_status") != "PASS":
        dump(out / "WS44_INHERITED_WS41_LINT_REPORT_135.json", inherited)
        raise RuntimeError("inherited WS41 semantic lint failed")
    semantic_report = copy.deepcopy(inherited)
    semantic_report["report_version"] = "commander-lab.semantic-executability-report/1.0.4"
    semantic_report["materialization_version"] = VERSION
    semantic_report["referential_integrity_defect_count"] = 0
    semantic_report["semantic_executable_count"] = 135
    semantic_report["contract_defect_count"] = 0
    semantic_report["terminal_status"] = "PASS"

    pre_ids = [r["fixture_id"] for r in predecessor["records"]]
    post_ids = [r["fixture_id"] for r in successor["records"]]
    if pre_ids != post_ids:
        raise RuntimeError("fixture identity/order changed")
    pre_family = Counter(r.get("fixture_family") for r in predecessor["records"])
    post_family = Counter(r.get("fixture_family") for r in successor["records"])
    if pre_family != post_family:
        raise RuntimeError("family counts changed")
    pre_af = {r["fixture_id"]: r.get("frozen_contract_binding") for r in predecessor["records"]}
    post_af = {r["fixture_id"]: r.get("frozen_contract_binding") for r in successor["records"]}
    if pre_af != post_af:
        raise RuntimeError("AF/frozen contract mapping changed")

    excluded = {f"CARD_{n:02d}" for n in range(1, 30)} - {"CARD_02"}
    denominator_ids = [fid for fid in post_ids if fid not in excluded]
    if len(denominator_ids) != 107:
        raise RuntimeError(f"provider denominator reconstructed as {len(denominator_ids)}, expected 107")
    if denominator_ids != predecessor_denom.get("fixture_ids"):
        raise RuntimeError("provider denominator identity set/order drift")

    changed_states = [x["fixture_id"] for x in lineage_rows if x["requested_state_changed"]]
    changed_obligations = [x["fixture_id"] for x in lineage_rows if x["obligation_changed"]]
    if changed_obligations:
        raise RuntimeError(f"obligation changes forbidden: {changed_obligations}")

    ws43_reconciliation = {
        "artifact_version": "commander-lab.ws44-ws43-scope-reconciliation/1.0.0",
        "ws43": {"commit": WS43_TERMINAL, "tree": WS43_TREE, "classification": "COMPLETE / TERMINAL_FAIL_DIGEST_INTEGRITY_DEFECT", "G43_01": "FAIL", "successor_contract_frozen": False},
        "ws44_new_gate_authority": "OPTION_2 / DETACHED_IMMUTABLE_PREDECESSOR_WITH_STRICT_ATTESTATION_SCOPE",
        "retroactive_ws43_reinterpretation": False,
        "terminal_status": "PASS",
    }
    defect_repro = {
        "artifact_version": "commander-lab.ws44-ws40-micro-defect-reproduction/1.0.0",
        "source": {"commit": PRE_COMMIT, "materialization_blob": PRE_MAT_BLOB},
        "ws40_terminal": WS40_TERMINAL,
        "ws42_terminal": WS42_TERMINAL,
        "rows": [
            {"fixture_id": fid, "path": "stack_state[0].targets[0]", "value": "obj:P2-bears", "exact_declaration_count": 0, "classification": "DANGLING_REFERENCE"}
            for fid in ("MICRO_PRIORITY", "MICRO_STACK")
        ],
        "provider_side_resolution_forbidden": True,
        "terminal_status": "PASS",
    }
    ref_rules = {
        "artifact_version": "commander-lab.ws44-referential-integrity-linter-rules/1.0.0",
        "case_sensitive": True,
        "exactly_one_resolution_required": True,
        "namespaces": {
            "semantic_object": "semantic_objects[].semantic_id; exact and embedded obj: references plus mapping keys",
            "player": "players[].player_id; structured and embedded P<n> references",
            "commander": "commander_state.commanders[].commander_id; cmd: references",
            "lineage": "semantic_objects[].card_lineage_id; line: references",
            "stack": "1-based stack:<n> references into stack_state",
            "native_step": "native_procedure[].step_id referenced by causal_step_id",
            "alias": "not present/authorized in v1.0.4; any alias-shaped field fails closed",
        },
        "forbidden_resolution": ["case_folding", "card_name_matching", "owner_matching", "controller_matching", "first_candidate", "positional_matching", "provider_native_identity_guessing", "request_echo", "hidden_provider_alias"],
        "negative_regression": {"value": "obj:P2-bears", "must_fail_resolution": True},
    }
    digest_lineage = {
        "artifact_version": "commander-lab.ws44-digest-lineage/1.0.0",
        "predecessor": {"version": PRE_VERSION, "commit": PRE_COMMIT, "tree": PRE_TREE, "namespace_tree": PRE_NS_TREE, "materialization_sha256": PRE_MAT_SHA256, "canonical_bundle_digest": PRE_CANONICAL_DIGEST},
        "successor": {"version": VERSION, "canonical_bundle_digest": successor["canonical_bundle_digest"]},
        "record_count": 135,
        "requested_state_changed_count": len(changed_states),
        "requested_state_changed_fixture_ids": changed_states,
        "obligation_changed_count": 0,
        "obligation_changed_fixture_ids": [],
        "rows": lineage_rows,
    }
    supersedes = {
        "artifact_version": "commander-lab.semantic-supersession/1.0.4",
        "predecessor": {"version": PRE_VERSION, "commit": PRE_COMMIT, "tree": PRE_TREE, "namespace_tree": PRE_NS_TREE, "canonical_bundle_digest": PRE_CANONICAL_DIGEST, "materialization_sha256": PRE_MAT_SHA256},
        "successor": {"version": VERSION, "record_count": 135, "semantic_executable_count": 135, "referential_integrity_defect_count": 0},
        "fixture_id_set_preserved": True,
        "family_counts_preserved": True,
        "af_frozen_contract_mapping_preserved": True,
        "obligation_changed": False,
        "representation_repair_rows": repair_rows,
    }
    denominator = {
        "artifact_version": "commander-lab.ws44-provider-denominator/1.0.0",
        "materialization_version": VERSION,
        "materialization_record_count": 135,
        "provider_denominator_count": 107,
        "fixture_ids": denominator_ids,
        "excluded_fixture_ids": sorted(excluded),
        "identity_derivation": "All 135 v1.0.4 IDs minus CARD_01..CARD_29 except retained successor sentinel CARD_02.",
        "predecessor_identity_set_equal": True,
        "denominator_decreased_to_bypass_blocker": False,
    }
    source_lock = {
        "artifact_version": "commander-lab.ws44-source-lock/1.0.0",
        "repository": "moeendres-png/commander-playtest-lab",
        "current_main": {"commit": MAIN_COMMIT, "tree": MAIN_TREE},
        "predecessor": {"commit": PRE_COMMIT, "tree": PRE_TREE, "namespace_tree": PRE_NS_TREE, "materialization_blob": PRE_MAT_BLOB, "materialization_sha256": PRE_MAT_SHA256, "canonical_bundle_digest": PRE_CANONICAL_DIGEST},
        "later_ws41_attestation": {"commit": TERMINAL_WS41_COMMIT, "tree": TERMINAL_WS41_TREE, "namespace_tree": TERMINAL_WS41_NS_TREE},
        "ws40": {"terminal": WS40_TERMINAL, "atomic_evidence": WS40_ATOMIC_EVIDENCE},
        "ws42": {"terminal": WS42_TERMINAL, "tree": WS42_TREE},
        "ws43": {"terminal": WS43_TERMINAL, "tree": WS43_TREE},
        "source_mode": "DETACHED_EXACT_GIT_OBJECT_VIA_GIT_SHOW",
    }
    validation = {
        "artifact_version": "commander-lab.ws44-validation/1.0.0",
        "materialization_version": VERSION,
        "static_gates": {
            "G44-01": "PASS", "G44-02": "PASS", "G44-03": "PASS", "G44-04": "PASS", "G44-05": "PASS", "G44-06": "PASS",
            "G44-07": "PASS", "G44-08": "PASS", "G44-09": "PASS", "G44-10": "PASS", "G44-11": "PASS", "G44-12": "PASS",
            "G44-14": "PASS",
        },
        "workflow_gates": {"G44-13": "REQUIRES_DOUBLE_MATERIALIZATION_CI", "G44-15": "REQUIRES_PERSISTENT_FREEZE_AND_POSTFREEZE_REGENERATION"},
        "global_referential_integrity_defects": 0,
        "semantic_executability": "135/135",
        "provider_denominator": 107,
        "provider_runtime_executed": False,
        "provider_pass_imported": False,
        "AF07_GRANTED": False,
        "ARCHITECTURE_FREEZE": False,
        "static_terminal_status": "PASS",
    }

    dump(out / "SEMANTIC_FIXTURE_SCHEMA_v1_0_4.json", patch_schema(schema))
    dump(out / "SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_4.json", successor)
    dump(out / "WS44_SOURCE_LOCK.json", source_lock)
    dump(out / "WS44_PREDECESSOR_AUTHORITY_VERIFICATION.json", authority)
    dump(out / "WS44_WS43_SCOPE_RECONCILIATION.json", ws43_reconciliation)
    dump(out / "WS44_WS40_MICRO_DEFECT_REPRODUCTION.json", defect_repro)
    dump(out / "WS44_MICRO_TARGET_IDENTITY_ADJUDICATION.json", micro_adjudication)
    dump(out / "WS44_REFERENCE_FIELD_INVENTORY.json", field_inventory)
    dump(out / "WS44_REFERENTIAL_INTEGRITY_LINTER_RULES.json", ref_rules)
    dump(out / "WS44_REFERENTIAL_INTEGRITY_AUDIT_135.json", ref_audit)
    dump(out / "WS44_INHERITED_WS41_LINT_REPORT_135.json", inherited)
    dump(out / "WS44_SEMANTIC_EXECUTABILITY_REPORT_135.json", semantic_report)
    dump(out / "WS44_PROVIDER_DENOMINATOR_107.json", denominator)
    dump(out / "WS44_DIGEST_LINEAGE.json", digest_lineage)
    dump(out / "SUPERSEDES_v1_0_3.json", supersedes)
    dump(out / "WS44_REPAIR_MATRIX.json", {"artifact_version": "commander-lab.ws44-repair-matrix/1.0.0", "repair_count": len(repair_rows), "changed_fixture_count": len(set(x["fixture_id"] for x in repair_rows)), "rows": repair_rows, "obligation_changed": False})
    dump(out / "WS44_VALIDATION.json", validation)

    # Digest the rendered materialization and seal an authoritative deterministic file set.
    mat_sha = sha256_bytes((out / "SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_4.json").read_bytes())
    lineage = json.loads((out / "WS44_DIGEST_LINEAGE.json").read_text(encoding="utf-8"))
    lineage["successor"]["materialization_sha256"] = mat_sha
    dump(out / "WS44_DIGEST_LINEAGE.json", lineage)
    supersedes2 = json.loads((out / "SUPERSEDES_v1_0_3.json").read_text(encoding="utf-8"))
    supersedes2["successor"]["materialization_sha256"] = mat_sha
    supersedes2["successor"]["canonical_bundle_digest"] = successor["canonical_bundle_digest"]
    dump(out / "SUPERSEDES_v1_0_3.json", supersedes2)

    files = sorted(p for p in out.iterdir() if p.is_file() and p.name not in {"WS44_SHA256SUMS", "WS44_EVIDENCE_INDEX.json"})
    checksum_rows = [{"path": p.name, "sha256": sha256_bytes(p.read_bytes())} for p in files]
    (out / "WS44_SHA256SUMS").write_text("".join(f"{r['sha256']}  {r['path']}\n" for r in checksum_rows), encoding="utf-8")
    index_files = [{"path": r["path"], "sha256": r["sha256"], "role": "canonical_ws44_freeze_evidence"} for r in checksum_rows]
    index_files.append({"path": "WS44_SHA256SUMS", "sha256": sha256_bytes((out / "WS44_SHA256SUMS").read_bytes()), "role": "sealed_checksum_manifest"})
    dump(out / "WS44_EVIDENCE_INDEX.json", {"artifact_version": "commander-lab.ws44-evidence-index/1.0.0", "contract_version": VERSION, "files": index_files, "postfreeze_ci_attestation_external": "candidate-qualification/ws44-v1.0.4-authority/WS44_POSTFREEZE_ATTESTATION.json"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    build(args.output)
