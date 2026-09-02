#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PROJECTION_KEYS = [
    "execution_entry_mode", "players", "deck_state", "commander_state",
    "semantic_objects", "temporal_state", "knowledge_state", "rules_randomness",
    "combat_state", "stack_state", "continuous_rules_effects", "extra_turn_creation",
    "elimination_trigger", "zone_move_event", "setup_validation",
]


def canonical_sha(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def requested_state_projection(record: dict[str, Any]) -> dict[str, Any]:
    # Exact copy of scripts/ws32_lint_semantic_v1_0_2.py at
    # 038d0f38635eecee4e331c99af41f148de267a26: omit absent keys rather than
    # normalizing them to JSON null.
    return {key: record[key] for key in PROJECTION_KEYS if key in record}


def shape(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: shape(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        if not value:
            return []
        unique = []
        seen = set()
        for item in value:
            s = shape(item)
            key = json.dumps(s, sort_keys=True, separators=(",", ":"))
            if key not in seen:
                seen.add(key)
                unique.append(s)
        return unique
    return type(value).__name__


def owned(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in records if not r["fixture_id"].startswith("CARD_") or r["fixture_id"] == "CARD_02"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--materialization", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    bundle = json.loads(args.materialization.read_text(encoding="utf-8"))
    if bundle.get("schema_version") != "commander-lab.semantic-fixture-materialization/1.0.2":
        raise SystemExit("WS40_CONTRACT_VERSION_MISMATCH")
    rows = owned(bundle["records"])
    if len(rows) != 107 or len({r["fixture_id"] for r in rows}) != 107:
        raise SystemExit("WS40_DENOMINATOR_DRIFT")

    digest_mismatches = []
    field_shapes: dict[str, dict[str, list[str]]] = {k: defaultdict(list) for k in PROJECTION_KEYS}
    native_ops: Counter[str] = Counter()
    decision_families: Counter[str] = Counter()
    object_zones: Counter[str] = Counter()
    object_features: Counter[str] = Counter()
    card_identities: Counter[str] = Counter()
    per_record = []

    for r in rows:
        requested = requested_state_projection(r)
        digest = canonical_sha(requested)
        if digest != r["requested_state_digest"]:
            digest_mismatches.append({"fixture_id": r["fixture_id"], "expected": r["requested_state_digest"], "computed": digest})
        for k in PROJECTION_KEYS:
            marker = r[k] if k in r else {"__ABSENT__": True}
            s = json.dumps(shape(marker), sort_keys=True, separators=(",", ":"))
            field_shapes[k][s].append(r["fixture_id"])
        for step in r.get("native_procedure", []):
            native_ops[str(step.get("operation", "<missing>"))] += 1
        for d in r.get("decision_script", []):
            decision_families[str(d.get("decision_family", "<missing>"))] += 1
        for o in r.get("semantic_objects", []):
            object_zones[str(o.get("zone"))] += 1
            card_identities[str(o.get("card_identity"))] += 1
            for feature in ("tapped", "face_down", "controlled_since_turn_began", "attached_to", "commander_id", "zone_position"):
                if feature in o and o.get(feature) not in (False, None, {}, []):
                    object_features[feature] += 1
            if o.get("counters"):
                object_features["counters"] += 1

        per_record.append({
            "fixture_id": r["fixture_id"],
            "fixture_family": r["fixture_family"],
            "entry_mode": r["execution_entry_mode"],
            "requested_state_digest": r["requested_state_digest"],
            "projection_keys_present": [k for k in PROJECTION_KEYS if k in r],
            "player_count": len(r["players"]),
            "object_count": len(r.get("semantic_objects", [])),
            "stack_count": len(r.get("stack_state") or []),
            "has_combat": bool(r.get("combat_state")),
            "decision_families": [d["decision_family"] for d in r.get("decision_script", [])],
            "native_operations": [str(s.get("operation")) for s in r.get("native_procedure", [])],
        })

    payload = {
        "schema_version": "ws40-native-construction-requirements/1.0.1",
        "contract_version": bundle["schema_version"],
        "contract_bundle_digest": bundle["canonical_bundle_digest"],
        "digest_spec": "commander-lab.requested-state-digest/1.0.0",
        "digest_source_commit": "038d0f38635eecee4e331c99af41f148de267a26",
        "digest_projection_absent_key_policy": "OMIT",
        "denominator": len(rows),
        "requested_digest_recomputed": len(rows) - len(digest_mismatches),
        "requested_digest_mismatches": digest_mismatches,
        "entry_modes": dict(Counter(r["execution_entry_mode"] for r in rows)),
        "family_counts": dict(Counter(r["fixture_family"] for r in rows)),
        "player_counts": dict(Counter(str(len(r["players"])) for r in rows)),
        "native_operations": dict(native_ops),
        "decision_families": dict(decision_families),
        "object_zones": dict(object_zones),
        "object_features": dict(object_features),
        "unique_card_identities": sorted(card_identities),
        "unique_card_identity_count": len(card_identities),
        "field_shapes": {
            k: [{"shape": json.loads(s), "count": len(ids), "sample_ids": ids[:8]} for s, ids in shapes.items()]
            for k, shapes in field_shapes.items()
        },
        "records": per_record,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "denominator": len(rows),
        "requested_digest_recomputed": payload["requested_digest_recomputed"],
        "digest_ok": not digest_mismatches,
        "entry_modes": payload["entry_modes"],
        "unique_card_identity_count": len(card_identities),
    }, sort_keys=True))
    return 0 if not digest_mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
