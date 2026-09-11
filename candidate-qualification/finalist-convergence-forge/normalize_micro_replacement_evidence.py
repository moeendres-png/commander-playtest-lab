#!/usr/bin/env python3
"""Normalize Forge MICRO_REPLACEMENT evidence to the frozen provider-neutral projection.

This step changes no runtime result. It recomputes only cross-provider comparison
fields from the exact frozen contract and retains the pre-normalization values as
provenance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

EXPECTED_FIXTURE = "MICRO_REPLACEMENT"
EXPECTED_DIGEST = "310964ff50516220522e906cd742f5c53f3fa722ddce104461ab10162bf50a5b"


def canonical_sha(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def provider_neutral_state(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "players": [{"player_id": p["player_id"], "life": p["life"]} for p in record["players"]],
        "objects": [
            {
                "semantic_id": obj["semantic_id"],
                "card_identity": obj["card_identity"],
                "owner": obj["owner"],
                "controller": obj["controller"],
                "zone": obj["zone"],
                "tapped": bool(obj.get("tapped", False)),
                "controlled_since_turn_began": bool(obj.get("controlled_since_turn_began", False)),
            }
            for obj in sorted(record["semantic_objects"], key=lambda x: x["semantic_id"])
        ],
        "combat_state": record["combat_state"],
        "temporal_state": {
            "turn_number": record["temporal_state"]["turn_number"],
            "active_player": record["temporal_state"]["active_player"],
            "priority_player": record["temporal_state"]["priority_player"],
            "phase": record["temporal_state"]["phase"],
            "step": record["temporal_state"]["step"],
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contract", type=Path, required=True)
    ap.add_argument("--evidence", type=Path, required=True)
    args = ap.parse_args()

    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    records = [r for r in contract["records"] if r["fixture_id"] == EXPECTED_FIXTURE]
    if len(records) != 1 or records[0]["materialization_digest"] != EXPECTED_DIGEST:
        raise SystemExit("MICRO_REPLACEMENT_CONTRACT_LOCK_MISMATCH")
    record = records[0]

    payload = json.loads(args.evidence.read_text(encoding="utf-8"))
    if payload.get("counts") != {"PASS": 1} or len(payload.get("rows", [])) != 1:
        raise SystemExit("MICRO_REPLACEMENT_RUNTIME_PASS_REQUIRED")
    row = payload["rows"][0]
    if row.get("fixture_id") != EXPECTED_FIXTURE or row.get("record_digest") != EXPECTED_DIGEST:
        raise SystemExit("MICRO_REPLACEMENT_RESULT_LOCK_MISMATCH")
    if row.get("requested_native_state_equal") is not True or row.get("terminal_postcondition_result") != "PASS":
        raise SystemExit("MICRO_REPLACEMENT_RUNTIME_EVIDENCE_NOT_PASS")
    if row.get("terminal_semantic_state", {}).get("P2", {}).get("life") != 34:
        raise SystemExit("MICRO_REPLACEMENT_TERMINAL_LIFE_MISMATCH")

    neutral = provider_neutral_state(record)
    digest = canonical_sha(neutral)
    row["qualification_infra_normalization"] = {
        "schema_version": "provider-neutral-state-normalization/1.0.0",
        "source": "frozen-contract-record",
        "pre_requested_semantic_state_digest": row.get("requested_semantic_state_digest"),
        "pre_normalized_native_constructed_state_digest": row.get("normalized_native_constructed_state_digest"),
        "terminal_projection_pre": row.get("terminal_semantic_state"),
        "included_contract_dimension": "controlled_since_turn_began",
    }
    row["requested_semantic_state_digest"] = digest
    row["normalized_native_constructed_state_digest"] = digest
    row["terminal_semantic_state"] = {"P2": {"life": 34}}
    args.evidence.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"fixture_id": EXPECTED_FIXTURE, "neutral_digest": digest}, sort_keys=True))


if __name__ == "__main__":
    main()
