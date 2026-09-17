#!/usr/bin/env python3
"""Independently reconstruct WS-46's exact immutable v1.0.4 provider denominator."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from successor_contract_v104 import (
    CANONICAL_MATERIALIZATION_DIGEST,
    CONTRACT_VERSION,
    FREEZE_COMMIT,
    FREEZE_TREE,
    MATERIALIZATION_FILE_SHA256,
    NAMESPACE_TREE,
    load_contract,
    provider_records,
    requested_state_digest,
)

EXPECTED_FAMILIES = {
    "player_count": 4,
    "pilot_boundary": 17,
    "pilot_boundary_negative": 7,
    "hidden_information": 20,
    "replay_rng": 5,
    "micro_rules": 17,
    "actual_card": 1,
    "multiplayer_commander": 36,
}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--contract", type=Path, required=True)
    p.add_argument("--published-denominator", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()

    contract = load_contract(args.contract)
    records = provider_records(contract)
    family_counts = Counter(r["fixture_family"] for r in records)
    if dict(family_counts) != EXPECTED_FAMILIES:
        raise SystemExit(f"WS46_FAMILY_COUNTS_MISMATCH:{dict(family_counts)}")

    rows = []
    for ordinal, record in enumerate(records, 1):
        computed = requested_state_digest(record)
        if computed != record["requested_state_digest"]:
            raise SystemExit(f"WS46_REQUESTED_STATE_RECOMPUTE_MISMATCH:{record['fixture_id']}")
        rows.append({
            "ordinal": ordinal,
            "fixture_id": record["fixture_id"],
            "fixture_family": record["fixture_family"],
            "materialization_digest": record["materialization_digest"],
            "requested_state_digest": record["requested_state_digest"],
            "execution_entry_mode": record["execution_entry_mode"],
            "native_operations": [s["operation"] for s in (record.get("native_procedure") or [])],
            "decision_families": [s["decision_family"] for s in (record.get("decision_script") or [])],
        })

    published_match = None
    published_sha = None
    if args.published_denominator:
        import hashlib
        raw = args.published_denominator.read_bytes()
        published_sha = hashlib.sha256(raw).hexdigest()
        published = json.loads(raw)
        published_ids = published.get("fixture_ids")
        derived_ids = [r["fixture_id"] for r in rows]
        published_match = published_ids == derived_ids and published.get("provider_denominator_count") == 107
        if not published_match:
            raise SystemExit("WS46_PUBLISHED_DENOMINATOR_POSTHOC_CROSSCHECK_MISMATCH")

    output = {
        "artifact_version": "commander-lab.ws46-denominator-manifest/1.0.0",
        "derivation": "immutable 135-record v1.0.4 materialization filtered independently by fixture_family != actual_card OR fixture_id == CARD_02",
        "published_ws44_provider_denominator_used_for_derivation": False,
        "published_ws44_provider_denominator_posthoc_match": published_match,
        "published_ws44_provider_denominator_sha256": published_sha,
        "historical_successor_pass_imported": False,
        "fresh_runtime_credit_granted": False,
        "contract": {
            "version": CONTRACT_VERSION,
            "commit": FREEZE_COMMIT,
            "tree": FREEZE_TREE,
            "namespace_tree": NAMESPACE_TREE,
            "materialization_sha256": MATERIALIZATION_FILE_SHA256,
            "canonical_bundle_digest": CANONICAL_MATERIALIZATION_DIGEST,
            "record_count": len(contract["records"]),
        },
        "provider_denominator": len(records),
        "unique_fixture_ids": len({r["fixture_id"] for r in rows}),
        "family_counts": dict(sorted(family_counts.items())),
        "all_requested_state_digests_recomputed_equal": True,
        "records": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: output[k] for k in ("provider_denominator", "unique_fixture_ids", "family_counts", "all_requested_state_digests_recomputed_equal")}, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
