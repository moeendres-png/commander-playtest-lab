#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path

TARGET = "WS05-MP-BLOCK-4"
PREDECESSOR_SHA256 = "9b370244e4e5df3132e6e9a3d2b70ad641a5a6023fc7c86832931340d24bfa35"
PREDECESSOR_VERSION = "commander-lab.semantic-fixture-materialization/1.0.4"


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="qualification/ws44/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_4.json")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    input_path = Path(args.input)
    raw = input_path.read_bytes()
    if sha256_bytes(raw) != PREDECESSOR_SHA256:
        raise SystemExit(f"WS47_PREDECESSOR_SHA256_MISMATCH:{sha256_bytes(raw)}")
    bundle = json.loads(raw)
    if bundle.get("schema_version") != PREDECESSOR_VERSION:
        raise SystemExit(f"WS47_PREDECESSOR_SCHEMA_MISMATCH:{bundle.get('schema_version')}")
    records = [r for r in bundle.get("records", []) if r.get("fixture_id") == TARGET]
    if len(records) != 1:
        raise SystemExit(f"WS47_TARGET_CARDINALITY:{len(records)}")
    record = records[0]
    stored = record.get("materialization_digest")
    projection = dict(record)
    projection.pop("materialization_digest", None)
    recomputed = sha256_bytes(canonical_bytes(projection))
    if stored != recomputed:
        raise SystemExit(f"WS47_TARGET_DIGEST_MISMATCH:{stored}:{recomputed}")
    out = {
        "artifact_version": "commander-lab.ws47-target-fixture-extract/1.0.1",
        "predecessor_schema_version": bundle["schema_version"],
        "predecessor_canonical_bundle_digest": bundle.get("canonical_bundle_digest"),
        "predecessor_file_sha256": sha256_bytes(raw),
        "fixture_id": TARGET,
        "stored_materialization_digest": stored,
        "recomputed_materialization_digest": recomputed,
        "record": record,
    }
    Path(args.output).write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"WS47_TARGET_FIXTURE_EXTRACT=PASS fixture={TARGET} digest={stored}")


if __name__ == "__main__":
    main()
