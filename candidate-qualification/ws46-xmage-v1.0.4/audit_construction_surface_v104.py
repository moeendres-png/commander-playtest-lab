#!/usr/bin/env python3
"""Extract exact immutable WS44 construction surfaces still absent from WS42.

Audit only: grants no provider/runtime credit and never interprets Magic legality.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from successor_contract_v104 import load_contract, provider_records  # noqa: E402

SURFACES = (
    "combat_state",
    "extra_turn_creation",
    "elimination_trigger",
    "zone_move_event",
)
KNOWLEDGE_GRANT_KEYS = (
    "face_down_look_permissions",
    "known_library_ranges",
    "known_object_identities",
    "temporary_permissions",
    "invalidation_conditions",
)


def nonempty(value: Any) -> bool:
    return value not in (None, {}, [], "", False)


def has_knowledge_grants(record: dict[str, Any]) -> bool:
    for viewer in (record.get("knowledge_state") or {}).get("viewer_states") or []:
        if any(nonempty(viewer.get(key)) for key in KNOWLEDGE_GRANT_KEYS):
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contract", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ns = ap.parse_args()

    contract = load_contract(ns.contract)
    records = provider_records(contract)
    rows: list[dict[str, Any]] = []
    counts = {key: 0 for key in SURFACES}
    counts["knowledge_grants"] = 0
    entry_modes = Counter(str(record.get("execution_entry_mode")) for record in records)

    for record in records:
        present = [key for key in SURFACES if nonempty(record.get(key))]
        knowledge = has_knowledge_grants(record)
        if not (present or knowledge):
            continue
        row: dict[str, Any] = {
            "fixture_id": record["fixture_id"],
            "fixture_family": record["fixture_family"],
            "requested_state_digest": record["requested_state_digest"],
            "execution_entry_mode": record.get("execution_entry_mode"),
        }
        for key in present:
            row[key] = record[key]
            counts[key] += 1
        if knowledge:
            row["knowledge_state"] = record["knowledge_state"]
            counts["knowledge_grants"] += 1
        rows.append(row)

    payload = {
        "schema_version": "commander-lab.ws46-construction-surface-audit/1.0.1",
        "contract_version": contract["schema_version"],
        "canonical_bundle_digest": contract["canonical_bundle_digest"],
        "provider_denominator": len(records),
        "execution_entry_modes": dict(sorted(entry_modes.items())),
        "counts": counts,
        "record_count_with_open_surface": len(rows),
        "records": rows,
        "runtime_credit_granted": False,
        "historical_pass_imported": False,
        "provider_semantics_used": False,
    }
    ns.output.parent.mkdir(parents=True, exist_ok=True)
    ns.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"counts": counts, "entry_modes": dict(sorted(entry_modes.items())), "records": len(rows)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
