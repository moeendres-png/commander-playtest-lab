#!/usr/bin/env python3
"""Audit whether native card targets may be normalized via frozen card lineage.

Diagnostic only. Reads the immutable WS41 v1.0.3 materialization plus its exact
107-record provider denominator. It never rewrites requested state and grants no
qualification credit.

Candidate observer projection under audit:
  current native Card -> uniquely bound semantic ObjSpec ->
  card_lineage_id suffix when it is a well-formed `line:<semantic identity>`;
  otherwise current semantic_id.

The candidate is considered safe for already-resolved stack targets only when
that projection reproduces every frozen requested stack target exactly. Any
unresolved or ambiguous requested target is reported separately and is never
silently guessed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SCHEMA = "commander-lab.ws40-v1.0.3-identity-normalization-projection-audit/1.0.0"
SOURCE_COMMIT = "24152acf36b5a560c23ccacfed3f31d3039537eb"
SOURCE_TREE = "428bbe58b2ea7b869200521092a8768108029b47"
SOURCE_SHA256 = "8f6e3778e96079dbb501b9f5d72f007da0549e26b836011a855c0dbd2c6237c5"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def lineage_suffix(obj: dict[str, Any]) -> str | None:
    value = obj.get("card_lineage_id")
    if isinstance(value, str) and value.startswith("line:") and len(value) > 5:
        return value[5:]
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("materialization", type=Path)
    ap.add_argument("denominator", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    actual_sha = sha256(args.materialization)
    if actual_sha != SOURCE_SHA256:
        raise SystemExit(f"materialization sha256 mismatch: {actual_sha}")

    doc = json.loads(args.materialization.read_text())
    denominator = json.loads(args.denominator.read_text())
    ids = denominator.get("fixture_ids")
    if not isinstance(ids, list) or len(ids) != 107 or len(set(ids)) != 107:
        raise SystemExit("invalid exact WS41 provider denominator")
    if denominator.get("provider_denominator_count") != 107:
        raise SystemExit("WS41 denominator count field is not 107")

    all_records = doc.get("records")
    if not isinstance(all_records, list):
        raise SystemExit("materialization records missing")
    by_fixture: dict[str, dict[str, Any]] = {}
    for rec in all_records:
        if isinstance(rec, dict) and isinstance(rec.get("fixture_id"), str):
            fid = rec["fixture_id"]
            if fid in by_fixture:
                raise SystemExit(f"duplicate fixture_id {fid}")
            by_fixture[fid] = rec
    missing = [fid for fid in ids if fid not in by_fixture]
    if missing:
        raise SystemExit(f"denominator fixtures missing from materialization: {missing}")

    object_rows: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    object_relation_counts: Counter[str] = Counter()
    target_status_counts: Counter[str] = Counter()
    divergent_objects: list[dict[str, Any]] = []
    duplicate_lineage_bases: list[dict[str, Any]] = []
    projection_breaks: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []

    for denominator_index, fid in enumerate(ids, 1):
        rec = by_fixture[fid]
        objects = rec.get("semantic_objects") or []
        if not isinstance(objects, list):
            raise SystemExit(f"semantic_objects not a list: {fid}")

        by_sid: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        by_lineage_suffix: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
        for object_index, obj in enumerate(objects):
            if not isinstance(obj, dict):
                raise SystemExit(f"bad semantic object {fid}[{object_index}]")
            sid = obj.get("semantic_id")
            if not isinstance(sid, str) or not sid:
                continue
            suffix = lineage_suffix(obj)
            if suffix is None:
                relation = "NO_WELL_FORMED_LINEAGE_SUFFIX"
                projected = sid
            elif suffix == sid:
                relation = "LINEAGE_SUFFIX_EQUALS_SEMANTIC_ID"
                projected = suffix
            else:
                relation = "LINEAGE_SUFFIX_DIFFERS_FROM_SEMANTIC_ID"
                projected = suffix
            object_relation_counts[relation] += 1
            row = {
                "fixture_id": fid,
                "denominator_index": denominator_index,
                "object_index": object_index,
                "semantic_id": sid,
                "card_lineage_id": obj.get("card_lineage_id"),
                "lineage_suffix": suffix,
                "candidate_projected_identity": projected,
                "relation": relation,
                "card_identity": obj.get("card_identity"),
                "commander_id": obj.get("commander_id"),
                "zone": obj.get("zone"),
                "owner": obj.get("owner"),
                "controller": obj.get("controller"),
            }
            object_rows.append(row)
            by_sid[sid].append(obj)
            if suffix is not None:
                by_lineage_suffix[suffix].append(obj)
            if relation == "LINEAGE_SUFFIX_DIFFERS_FROM_SEMANTIC_ID":
                divergent_objects.append(row)

        for suffix, matches in sorted(by_lineage_suffix.items()):
            unique_sids = sorted({m.get("semantic_id") for m in matches if isinstance(m.get("semantic_id"), str)})
            if len(unique_sids) > 1:
                duplicate_lineage_bases.append({
                    "fixture_id": fid,
                    "denominator_index": denominator_index,
                    "lineage_suffix": suffix,
                    "semantic_ids": unique_sids,
                })

        players = {
            p.get("player_id") for p in (rec.get("players") or [])
            if isinstance(p, dict) and isinstance(p.get("player_id"), str)
        }
        stack = rec.get("stack_state") or []
        if not isinstance(stack, list):
            raise SystemExit(f"stack_state not a list: {fid}")
        for stack_index, entry in enumerate(stack):
            if not isinstance(entry, dict):
                continue
            targets = entry.get("targets") or []
            if not isinstance(targets, list):
                raise SystemExit(f"stack targets not a list: {fid}[{stack_index}]")
            for target_index, requested in enumerate(targets):
                if not isinstance(requested, str):
                    continue
                base = {
                    "fixture_id": fid,
                    "denominator_index": denominator_index,
                    "stack_index": stack_index,
                    "target_index": target_index,
                    "source_semantic_id": entry.get("source_semantic_id"),
                    "requested_target": requested,
                }
                if requested in players:
                    row = {**base, "resolution_status": "PLAYER_ID", "resolved_semantic_id": None,
                           "resolved_lineage_suffix": None, "candidate_projected_identity": requested,
                           "projection_equals_requested": True}
                else:
                    exact = by_sid.get(requested, [])
                    lineage = by_lineage_suffix.get(requested, [])
                    if len(exact) == 1:
                        obj = exact[0]
                        sid = obj["semantic_id"]
                        suffix = lineage_suffix(obj)
                        projected = suffix if suffix is not None else sid
                        row = {**base, "resolution_status": "EXACT_SEMANTIC_ID",
                               "resolved_semantic_id": sid, "resolved_lineage_suffix": suffix,
                               "candidate_projected_identity": projected,
                               "projection_equals_requested": projected == requested}
                    elif len(exact) > 1:
                        row = {**base, "resolution_status": "AMBIGUOUS_EXACT_SEMANTIC_ID",
                               "resolved_semantic_ids": sorted({o["semantic_id"] for o in exact}),
                               "candidate_projected_identity": None, "projection_equals_requested": False}
                    elif len(lineage) == 1:
                        obj = lineage[0]
                        sid = obj["semantic_id"]
                        suffix = lineage_suffix(obj)
                        projected = suffix if suffix is not None else sid
                        row = {**base, "resolution_status": "UNIQUE_LINEAGE_SUFFIX",
                               "resolved_semantic_id": sid, "resolved_lineage_suffix": suffix,
                               "candidate_projected_identity": projected,
                               "projection_equals_requested": projected == requested}
                    elif len(lineage) > 1:
                        row = {**base, "resolution_status": "AMBIGUOUS_LINEAGE_SUFFIX",
                               "resolved_semantic_ids": sorted({o["semantic_id"] for o in lineage}),
                               "candidate_projected_identity": None, "projection_equals_requested": False}
                    else:
                        row = {**base, "resolution_status": "UNRESOLVED",
                               "resolved_semantic_id": None, "resolved_lineage_suffix": None,
                               "candidate_projected_identity": None, "projection_equals_requested": False}
                target_rows.append(row)
                target_status_counts[row["resolution_status"]] += 1
                if row["resolution_status"].startswith("AMBIGUOUS"):
                    ambiguous.append(row)
                elif row["resolution_status"] == "UNRESOLVED":
                    unresolved.append(row)
                elif not row["projection_equals_requested"]:
                    projection_breaks.append(row)

    resolved_card_targets = [
        r for r in target_rows
        if r["resolution_status"] in {"EXACT_SEMANTIC_ID", "UNIQUE_LINEAGE_SUFFIX"}
    ]
    candidate_preserves_all_resolved_card_targets = all(
        r["projection_equals_requested"] for r in resolved_card_targets
    )

    pilot_replacement = [r for r in target_rows if r["fixture_id"] == "PILOT_REPLACEMENT_EFFECT"]
    micro_problem_rows = [r for r in target_rows if r["fixture_id"] in {"MICRO_PRIORITY", "MICRO_STACK"}]

    report = {
        "schema_version": SCHEMA,
        "source_lock": {
            "commit": SOURCE_COMMIT,
            "tree": SOURCE_TREE,
            "materialization_sha256": SOURCE_SHA256,
            "denominator_blob_sha": "8318f897a37d9f98a95dd786a93a5564bd5b6fc1",
            "denominator_count": 107,
        },
        "historical_runtime_credit_imported": 0,
        "record_count": 107,
        "semantic_object_count": len(object_rows),
        "semantic_object_relation_counts": dict(sorted(object_relation_counts.items())),
        "divergent_semantic_lineage_object_count": len(divergent_objects),
        "duplicate_lineage_suffix_group_count": len(duplicate_lineage_bases),
        "stack_target_reference_count": len(target_rows),
        "stack_target_status_counts": dict(sorted(target_status_counts.items())),
        "resolved_card_target_count": len(resolved_card_targets),
        "projection_break_count_on_resolved_card_targets": len(projection_breaks),
        "ambiguous_stack_target_count": len(ambiguous),
        "unresolved_stack_target_count": len(unresolved),
        "candidate_projection": {
            "definition": "native card -> unique bound semantic ObjSpec -> well-formed card_lineage_id suffix when present, else current semantic_id",
            "uses_requested_target_value_for_observer_projection": False,
            "uses_card_name_heuristic": False,
            "uses_case_folding": False,
            "uses_owner_controller_guess": False,
            "preserves_every_resolved_frozen_stack_target_exactly": candidate_preserves_all_resolved_card_targets,
            "safe_to_apply_to_resolved_native_card_targets": candidate_preserves_all_resolved_card_targets and not duplicate_lineage_bases,
            "does_not_resolve_unresolved_contract_targets": True,
        },
        "pilot_replacement_effect_rows": pilot_replacement,
        "micro_priority_stack_rows": [r for r in micro_problem_rows if r["fixture_id"] == "MICRO_PRIORITY"],
        "micro_stack_stack_rows": [r for r in micro_problem_rows if r["fixture_id"] == "MICRO_STACK"],
        "projection_breaks": projection_breaks,
        "ambiguous_stack_targets": ambiguous,
        "unresolved_stack_targets": unresolved,
        "duplicate_lineage_suffix_groups": duplicate_lineage_bases,
        "divergent_semantic_lineage_objects": divergent_objects,
        "stack_target_rows": target_rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "records": report["record_count"],
        "objects": report["semantic_object_count"],
        "divergent_objects": report["divergent_semantic_lineage_object_count"],
        "stack_targets": report["stack_target_reference_count"],
        "status_counts": report["stack_target_status_counts"],
        "projection_breaks": report["projection_break_count_on_resolved_card_targets"],
        "ambiguous": report["ambiguous_stack_target_count"],
        "unresolved": report["unresolved_stack_target_count"],
        "safe_projection": report["candidate_projection"]["safe_to_apply_to_resolved_native_card_targets"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
