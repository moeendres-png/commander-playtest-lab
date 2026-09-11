#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

WS41_COMMIT = "24152acf36b5a560c23ccacfed3f31d3039537eb"
WS41_TREE = "428bbe58b2ea7b869200521092a8768108029b47"
VERSION = "commander-lab.semantic-fixture-materialization/1.0.3"
EXPECTED_MATERIALIZATION_SHA256 = "8f6e3778e96079dbb501b9f5d72f007da0549e26b836011a855c0dbd2c6237c5"
EXPECTED_CANONICAL_BUNDLE_DIGEST = "545afdeda53a11a2ebb32f534aa1b3186f434aa90bec2c8f2f232851e1abd31b"
STATE_KEYS = (
    "execution_entry_mode", "players", "deck_state", "commander_state",
    "semantic_objects", "temporal_state", "knowledge_state", "rules_randomness",
    "combat_state", "stack_state", "continuous_rules_effects", "extra_turn_creation",
    "elimination_trigger", "zone_move_event", "setup_validation",
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def requested_state_digest(record: dict[str, Any]) -> str:
    projection = {key: copy.deepcopy(record[key]) for key in STATE_KEYS if key in record}
    return sha256_bytes(canonical_bytes(projection))


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--materialization", type=Path, required=True)
    ap.add_argument("--denominator", type=Path, required=True)
    ap.add_argument("--lineage", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    raw = args.materialization.read_bytes()
    raw_sha = sha256_bytes(raw)
    if raw_sha != EXPECTED_MATERIALIZATION_SHA256:
        raise SystemExit(f"materialization SHA256 mismatch: {raw_sha}")

    bundle = json.loads(raw)
    if bundle.get("schema_version") != VERSION:
        raise SystemExit(f"schema/version mismatch: {bundle.get('schema_version')}")
    if bundle.get("canonical_bundle_digest") != EXPECTED_CANONICAL_BUNDLE_DIGEST:
        raise SystemExit("canonical bundle digest mismatch")
    records = bundle.get("records") or []
    if len(records) != 135 or bundle.get("record_count") != 135:
        raise SystemExit("materialization record count is not exactly 135")
    by_id = {r["fixture_id"]: r for r in records}
    if len(by_id) != 135:
        raise SystemExit("materialization fixture IDs are not unique")

    denominator = load(args.denominator)
    if denominator.get("materialization_version") != VERSION:
        raise SystemExit("denominator version mismatch")
    ids = denominator.get("fixture_ids") or []
    if denominator.get("provider_denominator_count") != 107 or len(ids) != 107 or len(set(ids)) != 107:
        raise SystemExit("provider denominator is not exactly 107 unique IDs")
    excluded = set(denominator.get("excluded_fixture_ids") or [])
    derived = [r["fixture_id"] for r in records if r["fixture_id"] not in excluded]
    if derived != ids:
        raise SystemExit("107 denominator IDs do not equal canonical ordered 135-minus-exclusions derivation")
    if "PILOT_CHOICE" not in ids or "CARD_02" not in ids:
        raise SystemExit("required PILOT_CHOICE/CARD_02 identities missing from denominator")

    lineage = load(args.lineage)
    if lineage.get("record_count") != 135:
        raise SystemExit("lineage record count mismatch")
    lineage_rows = {r["fixture_id"]: r for r in lineage.get("rows") or []}
    if len(lineage_rows) != 135:
        raise SystemExit("lineage does not expose exactly 135 unique fixture rows")
    if lineage.get("requested_state_changed_count") != 1 or lineage.get("requested_state_changed_fixture_ids") != ["PILOT_CHOICE"]:
        raise SystemExit("unexpected v1.0.2 -> v1.0.3 requested-state drift surface")
    if lineage.get("obligation_changed_count") != 0:
        raise SystemExit("unexpected obligation drift")

    rows = []
    for index, fixture_id in enumerate(ids, start=1):
        record = by_id.get(fixture_id)
        if record is None:
            raise SystemExit(f"denominator fixture missing from materialization: {fixture_id}")
        digest = requested_state_digest(record)
        embedded = record.get("requested_state_digest")
        lineage_digest = lineage_rows[fixture_id].get("new_requested_state_digest")
        passed = digest == embedded == lineage_digest
        rows.append({
            "index": index,
            "fixture_id": fixture_id,
            "independent_requested_state_digest": digest,
            "embedded_requested_state_digest": embedded,
            "lineage_requested_state_digest": lineage_digest,
            "pass": passed,
        })
        if not passed:
            raise SystemExit(f"requested-state digest mismatch for {fixture_id}")

    report = {
        "schema_version": "commander-lab.ws40-v1.0.3-contract-lock-verification/1.0.0",
        "status": "PASS",
        "immutable_source_lock": {
            "commit": WS41_COMMIT,
            "tree": WS41_TREE,
            "namespace": "qualification/ws41",
            "contract": VERSION,
            "materialization_sha256": raw_sha,
            "canonical_bundle_digest": bundle["canonical_bundle_digest"],
        },
        "denominator": {
            "count": len(ids),
            "ids_unique": True,
            "ordered_derivation_matches": True,
            "historical_runtime_credit": 0,
        },
        "drift": {
            "requested_state_changed_count": lineage["requested_state_changed_count"],
            "requested_state_changed_fixture_ids": lineage["requested_state_changed_fixture_ids"],
            "obligation_changed_count": lineage["obligation_changed_count"],
        },
        "requested_state_digest_verification": {
            "count": len(rows),
            "pass_count": sum(1 for row in rows if row["pass"]),
            "all_pass": all(row["pass"] for row in rows),
            "algorithm": "SHA256(JSON canonical projection over frozen STATE_KEYS; UTF-8; sort_keys; separators comma/colon; absent keys omitted)",
            "rows": rows,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("WS40_V103_CONTRACT_LOCK_VERIFICATION=PASS")
    print(f"WS40_V103_DENOMINATOR={len(ids)}")
    print(f"WS40_V103_REQUESTED_STATE_DIGESTS_PASS={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
