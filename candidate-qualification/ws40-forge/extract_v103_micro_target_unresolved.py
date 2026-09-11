#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SCHEMA = "commander-lab.ws40-v1.0.3-micro-target-unresolved-extract/1.0.0"
SOURCE_COMMIT = "24152acf36b5a560c23ccacfed3f31d3039537eb"
SOURCE_TREE = "428bbe58b2ea7b869200521092a8768108029b47"
SOURCE_SHA256 = "8f6e3778e96079dbb501b9f5d72f007da0549e26b836011a855c0dbd2c6237c5"
FIXTURES = ("MICRO_PRIORITY", "MICRO_STACK")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("materialization", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    actual = sha256(args.materialization)
    if actual != SOURCE_SHA256:
        raise SystemExit(f"materialization sha256 mismatch: {actual}")
    doc = json.loads(args.materialization.read_text())
    records = doc.get("records")
    if not isinstance(records, list):
        raise SystemExit("top-level records is not a list")

    selected = []
    for fixture_id in FIXTURES:
        matches = [r for r in records if isinstance(r, dict) and r.get("fixture_id") == fixture_id]
        if len(matches) != 1:
            raise SystemExit(f"expected exactly one {fixture_id}, got {len(matches)}")
        selected.append(matches[0])

    out = {
        "schema_version": SCHEMA,
        "source_lock": {
            "commit": SOURCE_COMMIT,
            "tree": SOURCE_TREE,
            "materialization_sha256": SOURCE_SHA256,
        },
        "fixture_ids": list(FIXTURES),
        "record_count": len(selected),
        "records": selected,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"fixture_ids": list(FIXTURES), "record_count": len(selected)}, sort_keys=True))


if __name__ == "__main__":
    main()
