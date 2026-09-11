#!/usr/bin/env python3
"""Read-only detached-source context extractor for WS-44 reference failures.

This script never consumes descendant qualification/ws41 bytes and never mutates
semantic records. It exists only to make fail-closed linter diagnostics auditable.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

PRE_COMMIT = "24152acf36b5a560c23ccacfed3f31d3039537eb"
PRE_PATH = "qualification/ws41/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_3.json"
FIXTURES = [
    "PILOT_REPLACEMENT_EFFECT",
    "PILOT_DECLARE_ATTACKER",
    "PILOT_DECLARE_BLOCKER",
    "HIDDEN_07",
    "MICRO_STATE_BASED_ACTIONS",
    "CARD_01",
    "WS05-MP-TRIG-3",
    "WS05-MP-COMBAT-4",
    "WS05-MP-COMBAT-5",
    "WS05-MP-BLOCK-4",
    "WS05-MP-ELIM-OWNED-3",
]
PROBLEM_LITERALS = [
    "obj:P1-commander",
    "obj:p1-bears",
    "obj:p2-bears",
    "ALL_PLAYERS",
    "obj:micro-zero",
    "obj:card01-ishai",
    "Soul Warden",
    "obj:mp-attacker-0",
    "obj:mp-attacker-1",
    "obj:mp-attacker-2",
    "obj:mp-p2-blocker",
    "obj:leave-owned",
]


def detached_bundle() -> dict[str, Any]:
    raw = subprocess.check_output(["git", "show", f"{PRE_COMMIT}:{PRE_PATH}"])
    return json.loads(raw.decode("utf-8"))


def walk(value: Any, path: str = "$") -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(key, str):
                out.append({"kind": "key", "path": f"{path}.<key:{key}>", "value": key})
            out.extend(walk(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            out.extend(walk(child, f"{path}[{i}]"))
    elif isinstance(value, str):
        out.append({"kind": "value", "path": path, "value": value})
    return out


def projected_object(obj: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "semantic_id", "card_identity", "zone", "owner", "controller",
        "card_lineage_id", "commander_id", "object_kind", "types",
    )
    return {k: obj.get(k) for k in keys if k in obj}


def build_context() -> dict[str, Any]:
    bundle = detached_bundle()
    by_id = {r["fixture_id"]: r for r in bundle["records"]}
    records = []
    for fid in FIXTURES:
        r = by_id[fid]
        strings = walk(r)
        occurrences = []
        for literal in PROBLEM_LITERALS:
            hits = [row for row in strings if literal in row["value"]]
            if hits:
                occurrences.append({"literal": literal, "hits": hits})
        records.append({
            "fixture_id": fid,
            "semantic_objects": [projected_object(o) for o in r.get("semantic_objects", [])],
            "stack_state": r.get("stack_state"),
            "decision_script": r.get("decision_script"),
            "native_procedure": r.get("native_procedure"),
            "expected_events": r.get("expected_events"),
            "terminal_postconditions": r.get("terminal_postconditions"),
            "knowledge_state": r.get("knowledge_state") if fid == "HIDDEN_07" else None,
            "zone_move_event": r.get("zone_move_event"),
            "continuous_rules_effects": r.get("continuous_rules_effects"),
            "occurrences": occurrences,
        })
    return {
        "artifact_version": "commander-lab.ws44-reference-failure-context/1.0.0",
        "source_commit": PRE_COMMIT,
        "source_path": PRE_PATH,
        "source_mode": "DETACHED_GIT_SHOW_ONLY",
        "record_count": len(records),
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = build_context()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
