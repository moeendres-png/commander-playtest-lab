#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

PROJECTION_KEYS = [
    "execution_entry_mode", "players", "deck_state", "commander_state", "semantic_objects",
    "temporal_state", "knowledge_state", "rules_randomness", "combat_state", "stack_state",
    "continuous_rules_effects", "extra_turn_creation", "elimination_trigger", "zone_move_event",
    "setup_validation",
]
AF_FAMILY = {
    "AF04": {"pilot_boundary", "pilot_boundary_negative"},
    "AF05": {"hidden_information"},
    "AF06": {"micro_rules"},
    "AF08": {"multiplayer_commander"},
    "AF09": {"replay_rng"},
}
EXPECTED_AF = {"AF04": 24, "AF05": 20, "AF06": 17, "AF08": 36, "AF09": 5}
VOLATILE_COMPARE_KEYS = {
    "materialization_version", "materialization_digest", "supersedes_record_digest", "repair_provenance"
}


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def projection(record: dict[str, Any]) -> dict[str, Any]:
    return {k: record[k] for k in PROJECTION_KEYS if k in record}


def stable_record(record: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in record.items() if k not in VOLATILE_COMPARE_KEYS}


def meaningful(value: Any) -> bool:
    return value not in (None, [], {})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--v103", type=Path, required=True)
    ap.add_argument("--v104", type=Path, required=True)
    ap.add_argument("--denominator", type=Path, required=True)
    ap.add_argument("--supersedes", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    v103 = json.loads(args.v103.read_text(encoding="utf-8"))
    v104 = json.loads(args.v104.read_text(encoding="utf-8"))
    denom = json.loads(args.denominator.read_text(encoding="utf-8"))
    supersedes = json.loads(args.supersedes.read_text(encoding="utf-8"))

    records3 = v103["records"]
    records4 = v104["records"]
    by3 = {r["fixture_id"]: r for r in records3}
    by4 = {r["fixture_id"]: r for r in records4}
    ids4 = [r["fixture_id"] for r in records4]
    if len(ids4) != len(set(ids4)):
        raise AssertionError("duplicate v1.0.4 fixture ids")

    reconstructed = [
        r["fixture_id"] for r in records4
        if r["fixture_family"] != "actual_card" or r["fixture_id"] == "CARD_02"
    ]
    manifest_ids = denom["provider_record_ids"]
    if reconstructed != manifest_ids:
        raise AssertionError("independently reconstructed provider denominator differs from WS44 manifest")
    if len(reconstructed) != 107:
        raise AssertionError(f"provider denominator {len(reconstructed)} != 107")

    digest_failures = []
    for rid in reconstructed:
        r = by4[rid]
        got = digest(projection(r))
        if got != r["requested_state_digest"]:
            digest_failures.append({"fixture_id": rid, "expected": r["requested_state_digest"], "recomputed": got})
    if digest_failures:
        raise AssertionError(f"requested-state digest failures: {digest_failures[:3]}")

    af_members: dict[str, list[str]] = {}
    for af, fams in AF_FAMILY.items():
        af_members[af] = [rid for rid in reconstructed if by4[rid]["fixture_family"] in fams]
    af_counts = {af: len(ids) for af, ids in af_members.items()}
    if af_counts != EXPECTED_AF:
        raise AssertionError(f"AF counts {af_counts} != {EXPECTED_AF}")
    if by4["CARD_02"]["fixture_family"] != "actual_card":
        raise AssertionError("CARD_02 family mismatch")

    common_ids = [rid for rid in ids4 if rid in by3]
    stable_changed = [rid for rid in common_ids if stable_record(by3[rid]) != stable_record(by4[rid])]
    requested_changed = [rid for rid in common_ids if by3[rid].get("requested_state_digest") != by4[rid].get("requested_state_digest")]

    repairs = supersedes.get("representation_repair_rows") or []
    repair_ids = [row["fixture_id"] for row in repairs]
    unique_repair_ids = list(dict.fromkeys(repair_ids))
    reconstructed_set = set(reconstructed)
    provider_repair_ids = [rid for rid in unique_repair_ids if rid in reconstructed_set]

    populated_projection_fields: dict[str, dict[str, Any]] = {}
    for key in PROJECTION_KEYS:
        matching = [rid for rid in reconstructed if key in by4[rid] and meaningful(by4[rid][key])]
        populated_projection_fields[key] = {"count": len(matching), "fixture_ids": matching}

    family_counts = Counter(by4[rid]["fixture_family"] for rid in reconstructed)
    result = {
        "schema": "commander-lab.ws45-v104-impact-reconciliation/1.0.0",
        "status": "PASS",
        "materialization_contract": v104["schema_version"],
        "canonical_bundle_digest": v104["canonical_bundle_digest"],
        "zero_historical_successor_runtime_credit": True,
        "denominator": {
            "count": len(reconstructed),
            "independently_reconstructed_ids": reconstructed,
            "manifest_exact_match": True,
            "family_counts": dict(sorted(family_counts.items())),
        },
        "requested_state_digest_verification": {
            "pass_count": len(reconstructed),
            "fail_count": 0,
            "all_pass": True,
        },
        "af_membership": {af: {"count": len(ids), "fixture_ids": ids} for af, ids in af_members.items()},
        "card_02": {"included": "CARD_02" in reconstructed, "count": reconstructed.count("CARD_02")},
        "v103_v104_comparison": {
            "common_fixture_count": len(common_ids),
            "stable_payload_changed_count": len(stable_changed),
            "stable_payload_changed_fixture_ids": stable_changed,
            "requested_state_digest_changed_count": len(requested_changed),
            "requested_state_digest_changed_fixture_ids": requested_changed,
        },
        "supersedes_repairs": {
            "repair_row_count": len(repairs),
            "unique_fixture_ids_overall": unique_repair_ids,
            "unique_fixture_count_overall": len(unique_repair_ids),
            "provider_relevant_fixture_ids": provider_repair_ids,
            "provider_relevant_fixture_count": len(provider_repair_ids),
            "provider_excluded_fixture_ids": [rid for rid in unique_repair_ids if rid not in reconstructed_set],
            "all_provider_semantics_used_false": all(row.get("provider_semantics_used") is False for row in repairs),
            "all_obligation_changed_false": all(row.get("obligation_changed") is False for row in repairs),
        },
        "provider_projection_field_population": populated_projection_fields,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
