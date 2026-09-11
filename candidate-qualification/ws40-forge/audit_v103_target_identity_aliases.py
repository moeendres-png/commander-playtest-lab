#!/usr/bin/env python3
"""WS-40 v1.0.3 target-identity audit.

Reads the immutable WS-41 semantic materialization and reports, corpus-wide,
whether target references are exact semantic IDs or can be uniquely related to
a current semantic object through provider-neutral identity fields.

Diagnostic only: no requested-state rewriting and no runtime/qualification credit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "commander-lab.ws40-v1.0.3-target-identity-audit/1.0.1"
SOURCE_COMMIT = "24152acf36b5a560c23ccacfed3f31d3039537eb"
SOURCE_TREE = "428bbe58b2ea7b869200521092a8768108029b47"
SOURCE_SHA256 = "8f6e3778e96079dbb501b9f5d72f007da0549e26b836011a855c0dbd2c6237c5"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def walk(value: Any, path: str = "$") -> Iterable[tuple[str, Any]]:
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            yield from walk(child, f"{path}[{idx}]")


def records(doc: Any) -> list[tuple[str, dict[str, Any]]]:
    if not isinstance(doc, dict) or not isinstance(doc.get("records"), list):
        raise SystemExit("immutable materialization does not contain top-level records list")
    out: list[tuple[str, dict[str, Any]]] = []
    for idx, value in enumerate(doc["records"]):
        if not isinstance(value, dict) or not isinstance(value.get("fixture_id"), str):
            raise SystemExit(f"invalid materialization record at $.records[{idx}]")
        if value.get("fixture_family") == "actual_card" and value.get("fixture_id") != "CARD_02":
            continue
        out.append((f"$.records[{idx}]", value))
    seen: dict[str, str] = {}
    for path, rec in out:
        fid = rec["fixture_id"]
        if fid in seen:
            raise SystemExit(f"duplicate fixture_id {fid!r}: {seen[fid]} and {path}")
        seen[fid] = path
    return out


def semantic_objects(record: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    raw = record.get("semantic_objects") or []
    if not isinstance(raw, list):
        raise SystemExit(f"semantic_objects is not a list in {record.get('fixture_id')}")
    result: list[tuple[str, dict[str, Any]]] = []
    for idx, value in enumerate(raw):
        if not isinstance(value, dict):
            raise SystemExit(f"semantic_objects[{idx}] is not an object in {record.get('fixture_id')}")
        sid = value.get("semantic_id")
        if isinstance(sid, str) and sid:
            result.append((f"$.semantic_objects[{idx}]", value))
    return result


def known_players(record: dict[str, Any], sem: list[tuple[str, dict[str, Any]]]) -> set[str]:
    players: set[str] = set()
    raw = record.get("players") or []
    if not isinstance(raw, list):
        raise SystemExit(f"players is not a list in {record.get('fixture_id')}")
    for value in raw:
        if isinstance(value, str):
            players.add(value)
        elif isinstance(value, dict):
            for key in ("player_id", "id", "semantic_id"):
                if isinstance(value.get(key), str):
                    players.add(value[key])
    for _, obj in sem:
        for key in ("owner", "controller"):
            value = obj.get(key)
            if isinstance(value, str) and value:
                players.add(value)
    temporal = record.get("temporal_state") or {}
    if isinstance(temporal, dict):
        for key in ("active_player", "priority_player"):
            value = temporal.get(key)
            if isinstance(value, str) and value:
                players.add(value)
    return players


def target_refs(record: dict[str, Any]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    stack = record.get("stack_state") or []
    if not isinstance(stack, list):
        raise SystemExit(f"stack_state is not a list in {record.get('fixture_id')}")
    for i, entry in enumerate(stack):
        if not isinstance(entry, dict):
            continue
        targets = entry.get("targets")
        if isinstance(targets, list):
            for j, target in enumerate(targets):
                if isinstance(target, str):
                    refs.append({
                        "surface": "requested_stack_target",
                        "path": f"$.stack_state[{i}].targets[{j}]",
                        "target": target,
                    })

    native = record.get("native_procedure") or []
    for path, value in walk(native, "$.native_procedure"):
        if not isinstance(value, dict):
            continue
        for key, target in value.items():
            if key in {"target", "target_id", "target_object_id"} and isinstance(target, str):
                refs.append({
                    "surface": "native_procedure_target",
                    "path": f"{path}.{key}",
                    "target": target,
                })
            elif key == "targets" and isinstance(target, list):
                for i, item in enumerate(target):
                    if isinstance(item, str):
                        refs.append({
                            "surface": "native_procedure_target",
                            "path": f"{path}.{key}[{i}]",
                            "target": item,
                        })
    return refs


def unique_semantic_ids(entries: list[tuple[str, dict[str, Any]]]) -> list[str]:
    return sorted({obj["semantic_id"] for _, obj in entries if isinstance(obj.get("semantic_id"), str)})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("materialization", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    actual_sha = sha256(args.materialization)
    if actual_sha != SOURCE_SHA256:
        raise SystemExit(f"source materialization sha256 mismatch: {actual_sha}")

    doc = json.loads(args.materialization.read_text())
    recs = records(doc)
    if len(recs) != 107:
        raise SystemExit(f"expected exactly 107 materialization records, got {len(recs)}")

    audit_rows: list[dict[str, Any]] = []
    status_counts: defaultdict[str, int] = defaultdict(int)
    surface_counts: defaultdict[str, int] = defaultdict(int)
    non_exact_fixtures: set[str] = set()
    ambiguous: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    for record_path, record in recs:
        fixture_id = record["fixture_id"]
        sem = semantic_objects(record)
        players = known_players(record, sem)

        by_semantic: defaultdict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
        by_source: defaultdict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
        by_lineage: defaultdict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
        by_lineage_base: defaultdict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
        by_commander: defaultdict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
        for entry in sem:
            _, obj = entry
            sid = obj.get("semantic_id")
            if isinstance(sid, str):
                by_semantic[sid].append(entry)
            source = obj.get("source_object_id")
            if isinstance(source, str) and source:
                by_source[source].append(entry)
            lineage = obj.get("card_lineage_id")
            if isinstance(lineage, str) and lineage:
                by_lineage[lineage].append(entry)
                if lineage.startswith("line:"):
                    by_lineage_base[lineage[5:]].append(entry)
            commander = obj.get("commander_id")
            if isinstance(commander, str) and commander:
                by_commander[commander].append(entry)

        for ref in target_refs(record):
            target = ref["target"]
            surface_counts[ref["surface"]] += 1
            evidence: dict[str, list[str]] = {
                "semantic_id": unique_semantic_ids(by_semantic.get(target, [])),
                "source_object_id": unique_semantic_ids(by_source.get(target, [])),
                "card_lineage_id": unique_semantic_ids(by_lineage.get(target, [])),
                "card_lineage_base": unique_semantic_ids(by_lineage_base.get(target, [])),
                "commander_id": unique_semantic_ids(by_commander.get(target, [])),
            }
            alias_candidates = sorted({sid for key, vals in evidence.items() if key != "semantic_id" for sid in vals})

            if evidence["semantic_id"]:
                status = "EXACT_SEMANTIC_ID"
                resolved = evidence["semantic_id"]
            elif target in players:
                status = "PLAYER_ID"
                resolved = []
            elif len(alias_candidates) == 1:
                status = "UNIQUE_IDENTITY_ALIAS"
                resolved = alias_candidates
                non_exact_fixtures.add(fixture_id)
            elif len(alias_candidates) > 1:
                status = "AMBIGUOUS_IDENTITY_ALIAS"
                resolved = alias_candidates
                non_exact_fixtures.add(fixture_id)
            else:
                status = "UNRESOLVED"
                resolved = []
                non_exact_fixtures.add(fixture_id)

            row = {
                "fixture_id": fixture_id,
                "record_path": record_path,
                **ref,
                "status": status,
                "resolved_semantic_ids": resolved,
                "identity_evidence": evidence,
            }
            audit_rows.append(row)
            status_counts[status] += 1
            if status == "AMBIGUOUS_IDENTITY_ALIAS":
                ambiguous.append(row)
            elif status == "UNRESOLVED":
                unresolved.append(row)

    out = {
        "schema_version": SCHEMA,
        "source_lock": {
            "commit": SOURCE_COMMIT,
            "tree": SOURCE_TREE,
            "materialization_sha256": SOURCE_SHA256,
        },
        "record_count": len(recs),
        "target_reference_count": len(audit_rows),
        "surface_counts": dict(sorted(surface_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "non_exact_fixture_count": len(non_exact_fixtures),
        "non_exact_fixtures": sorted(non_exact_fixtures),
        "ambiguous_count": len(ambiguous),
        "unresolved_count": len(unresolved),
        "safe_for_unique_identity_alias_resolution": not ambiguous and not unresolved,
        "audit_rows": audit_rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")

    print(json.dumps({
        "records": len(recs),
        "targets": len(audit_rows),
        "status_counts": out["status_counts"],
        "ambiguous": len(ambiguous),
        "unresolved": len(unresolved),
        "safe_for_unique_identity_alias_resolution": out["safe_for_unique_identity_alias_resolution"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
