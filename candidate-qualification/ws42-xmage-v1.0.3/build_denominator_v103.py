#!/usr/bin/env python3
"""Independently reconstruct WS-42's exact v1.0.3 provider denominator.

The script reads only the immutable materialization and the hard contract rule:
exclude Actual-Card records except CARD_02. It does not consume WS41's published
provider-denominator artifact and imports no historical runtime result.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from successor_contract_v103 import (
    CANONICAL_MATERIALIZATION_DIGEST,
    CONTRACT_VERSION,
    FREEZE_COMMIT,
    FREEZE_TREE,
    MATERIALIZATION_FILE_SHA256,
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    contract = load_contract(args.contract)
    records = provider_records(contract)
    family_counts = Counter(record["fixture_family"] for record in records)
    if dict(family_counts) != EXPECTED_FAMILIES:
        raise SystemExit(f"WS42_FAMILY_COUNTS_MISMATCH:{dict(family_counts)}")

    rows = []
    for index, record in enumerate(records, 1):
        computed_requested = requested_state_digest(record)
        if computed_requested != record["requested_state_digest"]:
            raise SystemExit(f"WS42_REQUESTED_STATE_RECOMPUTE_MISMATCH:{record['fixture_id']}")
        rows.append({
            "ordinal": index,
            "fixture_id": record["fixture_id"],
            "fixture_family": record["fixture_family"],
            "materialization_digest": record["materialization_digest"],
            "requested_state_digest": record["requested_state_digest"],
            "execution_entry_mode": record["execution_entry_mode"],
            "native_operations": [step["operation"] for step in (record.get("native_procedure") or [])],
            "decision_families": [step["decision_family"] for step in (record.get("decision_script") or [])],
        })

    output = {
        "artifact_version": "commander-lab.ws42-denominator-manifest/1.0.0",
        "derivation": "immutable 135-record v1.0.3 materialization filtered by fixture_family != actual_card OR fixture_id == CARD_02",
        "published_ws41_provider_denominator_consumed": False,
        "historical_successor_pass_imported": False,
        "fresh_runtime_credit_granted": False,
        "contract": {
            "version": CONTRACT_VERSION,
            "commit": FREEZE_COMMIT,
            "tree": FREEZE_TREE,
            "materialization_sha256": MATERIALIZATION_FILE_SHA256,
            "canonical_bundle_digest": CANONICAL_MATERIALIZATION_DIGEST,
            "record_count": len(contract["records"]),
        },
        "provider_denominator": len(records),
        "unique_fixture_ids": len({row["fixture_id"] for row in rows}),
        "family_counts": dict(sorted(family_counts.items())),
        "all_requested_state_digests_recomputed_equal": True,
        "records": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "provider_denominator": output["provider_denominator"],
        "unique_fixture_ids": output["unique_fixture_ids"],
        "family_counts": output["family_counts"],
        "all_requested_state_digests_recomputed_equal": True,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
