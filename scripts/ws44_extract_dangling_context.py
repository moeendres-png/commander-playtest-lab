#!/usr/bin/env python3
"""Extract complete record-local context for every detached v1.0.3 dangling obj reference."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ws44_probe_predecessor import (
    OBJ_RE,
    PRE_COMMIT,
    PRE_MAT_PATH,
    iter_leaves,
    json_git_show,
    record_probe,
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True)
    args = ap.parse_args()
    _, bundle = json_git_show(PRE_COMMIT, PRE_MAT_PATH)
    records = bundle["records"]
    affected: list[dict] = []
    for record in records:
        declared = {
            o.get("semantic_id") for o in record.get("semantic_objects", [])
            if isinstance(o, dict) and isinstance(o.get("semantic_id"), str)
        }
        dangling = []
        for path, field, value in iter_leaves(record):
            if not isinstance(value, str) or not OBJ_RE.fullmatch(value):
                continue
            if path.startswith("$.semantic_objects[") and path.endswith(".semantic_id"):
                continue
            if value not in declared:
                dangling.append({"path": path, "field": field, "value": value})
        if dangling:
            probe = record_probe(record)
            probe["detected_dangling"] = dangling
            affected.append(probe)
    out = {
        "artifact_version": "commander-lab.ws44-dangling-contexts/1.0.0",
        "source_commit": PRE_COMMIT,
        "source_mode": "DETACHED_EXACT_GIT_OBJECT_VIA_GIT_SHOW",
        "affected_record_count": len(affected),
        "affected_records": affected,
    }
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, sort_keys=True, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
