#!/usr/bin/env python3
"""Inventory identifier-like namespaces and reference-bearing paths in pinned v1.0.3."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterator

from ws44_probe_predecessor import PRE_COMMIT, PRE_MAT_PATH, json_git_show

PREFIX_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):(.*)$")
PLAYER_RE = re.compile(r"^P[1-9][0-9]*$")


def walk(value: Any, path: str = "$") -> Iterator[tuple[str, str, str, str | None]]:
    """Yield (kind,path,string,field). Includes string dictionary keys."""
    if isinstance(value, dict):
        for key, child in value.items():
            key_path = f"{path}.<key:{key}>"
            if isinstance(key, str):
                yield "key", key_path, key, None
            yield from walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from walk(child, f"{path}[{i}]")
    elif isinstance(value, str):
        field = path.rsplit(".", 1)[-1] if "." in path else None
        yield "value", path, value, field


def shape(path: str) -> str:
    return re.sub(r"\[[0-9]+\]", "[]", path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    _, bundle = json_git_show(PRE_COMMIT, PRE_MAT_PATH)
    prefix_counts: Counter[str] = Counter()
    prefix_paths: dict[str, Counter[str]] = defaultdict(Counter)
    prefix_examples: dict[str, list[dict]] = defaultdict(list)
    player_paths: Counter[str] = Counter()
    special_fields: Counter[str] = Counter()
    for record in bundle["records"]:
        fid = record["fixture_id"]
        for kind, path, text, field in walk(record):
            m = PREFIX_RE.match(text)
            if m:
                prefix = m.group(1)
                prefix_counts[prefix] += 1
                prefix_paths[prefix][shape(path)] += 1
                if len(prefix_examples[prefix]) < 12:
                    prefix_examples[prefix].append({"fixture_id": fid, "kind": kind, "path": path, "value": text})
            if PLAYER_RE.fullmatch(text):
                player_paths[shape(path)] += 1
            if field in {
                "semantic_id", "source_semantic_id", "source_object", "attached_to", "lineage_id", "commander_id",
                "causal_step_id", "step_id", "transaction_id", "source_transaction_id", "decision_id", "alias", "aliases",
                "defender", "defended_player", "controller", "owner", "actor", "active_player", "priority_holder",
            }:
                special_fields[field] += 1
    out = {
        "artifact_version": "commander-lab.ws44-reference-namespace-inventory/1.0.0",
        "source_commit": PRE_COMMIT,
        "record_count": len(bundle["records"]),
        "prefixes": [
            {
                "prefix": p,
                "occurrence_count": prefix_counts[p],
                "path_shapes": [{"path": k, "count": v} for k, v in prefix_paths[p].most_common()],
                "examples": prefix_examples[p],
            }
            for p in sorted(prefix_counts)
        ],
        "player_id_path_shapes": [{"path": k, "count": v} for k, v in player_paths.most_common()],
        "special_field_counts": dict(sorted(special_fields.items())),
    }
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
