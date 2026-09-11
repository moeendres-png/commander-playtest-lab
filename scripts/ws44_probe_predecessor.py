#!/usr/bin/env python3
"""WS-44 detached v1.0.3 predecessor semantic/reference probe.

This script is intentionally read-only with respect to the predecessor. It obtains
canonical bytes only through `git show <pinned commit>:<path>`, proves their SHA256,
and emits compact machine-readable evidence used before any v1.0.4 mutation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterator

from ws41_lint_semantic_v1_0_3 import obligation_digest, requested_state_digest

PRE_COMMIT = "24152acf36b5a560c23ccacfed3f31d3039537eb"
PRE_TREE = "428bbe58b2ea7b869200521092a8768108029b47"
PRE_NS_TREE = "af8a26e7e74a859d5f4a983b69e4ff108e7123f4"
PRE_MAT_PATH = "qualification/ws41/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_3.json"
PRE_MAT_BLOB = "a05106d42ff3e51fe68acf45bb03aa356784142c"
PRE_MAT_SHA256 = "8f6e3778e96079dbb501b9f5d72f007da0549e26b836011a855c0dbd2c6237c5"
PRE_BUNDLE_DIGEST = "545afdeda53a11a2ebb32f534aa1b3186f434aa90bec2c8f2f232851e1abd31b"
MICRO_IDS = ("MICRO_PRIORITY", "MICRO_STACK")
OBJ_RE = re.compile(r"^obj:[A-Za-z0-9_.:-]+$")


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args])


def json_git_show(commit: str, path: str) -> tuple[bytes, Any]:
    raw = git("show", f"{commit}:{path}")
    return raw, json.loads(raw.decode("utf-8"))


def iter_leaves(value: Any, path: str = "$") -> Iterator[tuple[str, str | None, Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from iter_leaves(child, f"{path}.{key}")
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from iter_leaves(child, f"{path}[{i}]")
    else:
        field = path.rsplit(".", 1)[-1] if "." in path else None
        yield path, field, value


def compact_object(obj: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "semantic_id", "card_identity", "owner", "controller", "zone", "zone_position",
        "commander_id", "lineage_id", "source_semantic_id", "attached_to", "tapped", "face_down",
    )
    out = {k: obj[k] for k in keys if k in obj}
    for k in ("counters", "known_to", "aliases"):
        if k in obj:
            out[k] = obj[k]
    return out


def record_probe(record: dict[str, Any]) -> dict[str, Any]:
    declared = [o.get("semantic_id") for o in record.get("semantic_objects", []) if isinstance(o, dict)]
    declared_set = {x for x in declared if isinstance(x, str)}
    duplicate_ids = sorted([x for x, n in Counter(declared).items() if isinstance(x, str) and n > 1])
    refs: list[dict[str, Any]] = []
    for path, field, value in iter_leaves(record):
        if not isinstance(value, str) or not OBJ_RE.fullmatch(value):
            continue
        is_declaration = path.startswith("$.semantic_objects[") and path.endswith(".semantic_id")
        if is_declaration:
            continue
        refs.append({
            "path": path,
            "field": field,
            "value": value,
            "namespace": "semantic_object",
            "match_count": 1 if value in declared_set else 0,
            "status": "PASS" if value in declared_set else "DANGLING_REFERENCE",
        })
    return {
        "fixture_id": record.get("fixture_id"),
        "fixture_family": record.get("fixture_family"),
        "declared_object_count": len(declared),
        "duplicate_object_ids": duplicate_ids,
        "semantic_objects": [compact_object(o) for o in record.get("semantic_objects", []) if isinstance(o, dict)],
        "object_references": refs,
        "dangling_object_references": [r for r in refs if r["status"] != "PASS"],
        "native_procedure": record.get("native_procedure", []),
        "decision_script": record.get("decision_script", []),
        "stack_state": record.get("stack_state", []),
        "expected_events": record.get("expected_events", []),
        "expected_postconditions": record.get("expected_postconditions", []),
        "obligation_digest": obligation_digest(record),
        "requested_state_digest": requested_state_digest(record),
        "materialization_digest": record.get("materialization_digest"),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    commit_tree = git("show", "-s", "--format=%T", PRE_COMMIT).decode().strip()
    if commit_tree != PRE_TREE:
        raise SystemExit(f"predecessor tree mismatch: {commit_tree}")
    ns_tree = git("rev-parse", f"{PRE_COMMIT}:qualification/ws41").decode().strip()
    if ns_tree != PRE_NS_TREE:
        raise SystemExit(f"predecessor namespace tree mismatch: {ns_tree}")
    blob = git("rev-parse", f"{PRE_COMMIT}:{PRE_MAT_PATH}").decode().strip()
    if blob != PRE_MAT_BLOB:
        raise SystemExit(f"materialization blob mismatch: {blob}")

    raw, bundle = json_git_show(PRE_COMMIT, PRE_MAT_PATH)
    digest = hashlib.sha256(raw).hexdigest()
    if digest != PRE_MAT_SHA256:
        raise SystemExit(f"materialization SHA256 mismatch: {digest}")
    if bundle.get("canonical_bundle_digest") != PRE_BUNDLE_DIGEST:
        raise SystemExit("canonical bundle digest mismatch")
    records = bundle.get("records", [])
    if len(records) != 135:
        raise SystemExit(f"record count mismatch: {len(records)}")

    field_counts: Counter[str] = Counter()
    dangling: list[dict[str, Any]] = []
    duplicate_rows: list[dict[str, Any]] = []
    all_ref_count = 0
    for record in records:
        declared = [o.get("semantic_id") for o in record.get("semantic_objects", []) if isinstance(o, dict)]
        declared_set = {x for x in declared if isinstance(x, str)}
        dup = sorted([x for x, n in Counter(declared).items() if isinstance(x, str) and n > 1])
        if dup:
            duplicate_rows.append({"fixture_id": record.get("fixture_id"), "duplicate_ids": dup})
        for path, field, value in iter_leaves(record):
            if not isinstance(value, str) or not OBJ_RE.fullmatch(value):
                continue
            if path.startswith("$.semantic_objects[") and path.endswith(".semantic_id"):
                continue
            all_ref_count += 1
            field_counts[field or "<none>"] += 1
            if value not in declared_set:
                dangling.append({
                    "fixture_id": record.get("fixture_id"), "path": path, "field": field,
                    "value": value, "status": "DANGLING_REFERENCE",
                })

    by_id = {r.get("fixture_id"): r for r in records}
    micro = {fid: record_probe(by_id[fid]) for fid in MICRO_IDS}
    exact_bug_rows = [r for r in dangling if r["value"] == "obj:P2-bears"]
    out = {
        "artifact_version": "commander-lab.ws44-predecessor-semantic-probe/1.0.0",
        "workstream": "WS-44",
        "source_mode": "DETACHED_EXACT_GIT_OBJECT_VIA_GIT_SHOW",
        "predecessor": {
            "commit": PRE_COMMIT, "tree": PRE_TREE, "namespace_tree": PRE_NS_TREE,
            "materialization_path": PRE_MAT_PATH, "materialization_blob": PRE_MAT_BLOB,
            "materialization_sha256": PRE_MAT_SHA256, "canonical_bundle_digest": PRE_BUNDLE_DIGEST,
        },
        "record_count": len(records),
        "global_object_reference_count": all_ref_count,
        "reference_field_inventory": [{"field": k, "count": v} for k, v in sorted(field_counts.items())],
        "duplicate_object_id_record_count": len(duplicate_rows),
        "duplicate_object_id_records": duplicate_rows,
        "dangling_object_reference_count": len(dangling),
        "dangling_object_references": dangling,
        "historical_bug_exact_match_count": len(exact_bug_rows),
        "historical_bug_exact_matches": exact_bug_rows,
        "micro_records": micro,
        "probe_classification": "PASS_REPRODUCED_EXACT_V1_0_3_REFERENTIAL_DEFECT" if len(exact_bug_rows) == 2 else "FAIL_UNEXPECTED_DEFECT_SHAPE",
    }
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    if out["probe_classification"] != "PASS_REPRODUCED_EXACT_V1_0_3_REFERENTIAL_DEFECT":
        raise SystemExit(out["probe_classification"])


if __name__ == "__main__":
    main()
