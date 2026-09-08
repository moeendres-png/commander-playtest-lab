#!/usr/bin/env python3
"""Fresh independent v1.0.4 -> v1.0.5 impact reconciliation for WS-49."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from successor_contract_v105 import (
    CANONICAL_MATERIALIZATION_DIGEST,
    CONTRACT_VERSION,
    STATE_KEYS,
    load_contract,
    provider_records,
    record_digest,
    requested_state_digest,
    requested_state_projection,
)

V104_VERSION = "commander-lab.semantic-fixture-materialization/1.0.4"
V104_BUNDLE = "77b911195525c2fe8aff37f6c9573e5772f358b25646d0be5919314ed5e23b54"
V104_SHA256 = "9b370244e4e5df3132e6e9a3d2b70ad641a5a6023fc7c86832931340d24bfa35"
EXPECTED_CHANGED = "WS05-MP-BLOCK-4"
EXPECTED_OLD_BLOCKERS = ["obj:mp-p2-blocker"]
EXPECTED_NEW_BLOCKERS = ["obj:P2-bears", "obj:mp-p2-blocker"]
DERIVED_OR_REPRESENTATION_FIELDS = set(STATE_KEYS) | {
    "materialization_version",
    "materialization_digest",
    "requested_state_digest",
    "repair_provenance",
}


def load_v104(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != V104_SHA256:
        raise SystemExit(f"WS49_V104_SHA_MISMATCH:{actual}")
    value = json.loads(raw)
    if value.get("schema_version") != V104_VERSION or value.get("canonical_bundle_digest") != V104_BUNDLE:
        raise SystemExit("WS49_V104_IDENTITY_MISMATCH")
    records = value.get("records") or []
    if len(records) != 135:
        raise SystemExit("WS49_V104_RECORD_COUNT_MISMATCH")
    for record in records:
        if record.get("materialization_digest") != record_digest(record):
            raise SystemExit(f"WS49_V104_RECORD_DIGEST_MISMATCH:{record.get('fixture_id')}")
        if record.get("requested_state_digest") != requested_state_digest(record):
            raise SystemExit(f"WS49_V104_REQUESTED_STATE_DIGEST_MISMATCH:{record.get('fixture_id')}")
    return value


def obligation_projection(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(value)
        for key, value in record.items()
        if key not in DERIVED_OR_REPRESENTATION_FIELDS
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v104", type=Path, required=True)
    parser.add_argument("--v105", type=Path, required=True)
    parser.add_argument("--published-change-accounting", type=Path)
    parser.add_argument("--published-supersedes", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    old = load_v104(args.v104)
    new = load_contract(args.v105)
    old_records = old["records"]
    new_records = new["records"]
    old_ids = [r["fixture_id"] for r in old_records]
    new_ids = [r["fixture_id"] for r in new_records]
    if old_ids != new_ids:
        raise SystemExit("WS49_V104_V105_FIXTURE_ID_ORDER_MISMATCH")
    if [r["fixture_family"] for r in old_records] != [r["fixture_family"] for r in new_records]:
        raise SystemExit("WS49_V104_V105_FAMILY_ORDER_MISMATCH")

    old_by = {r["fixture_id"]: r for r in old_records}
    new_by = {r["fixture_id"]: r for r in new_records}
    requested_changed: list[str] = []
    obligation_changed: list[str] = []
    digest_lineage: list[dict[str, Any]] = []
    for fixture_id in new_ids:
        old_record = old_by[fixture_id]
        new_record = new_by[fixture_id]
        old_requested = requested_state_projection(old_record)
        new_requested = requested_state_projection(new_record)
        if old_requested != new_requested:
            requested_changed.append(fixture_id)
        if obligation_projection(old_record) != obligation_projection(new_record):
            obligation_changed.append(fixture_id)
        digest_lineage.append({
            "fixture_id": fixture_id,
            "old_materialization_digest": old_record["materialization_digest"],
            "new_materialization_digest": new_record["materialization_digest"],
            "old_requested_state_digest": old_record["requested_state_digest"],
            "new_requested_state_digest": new_record["requested_state_digest"],
            "requested_state_changed": old_requested != new_requested,
        })

    if requested_changed != [EXPECTED_CHANGED]:
        raise SystemExit(f"WS49_REQUESTED_STATE_CHANGE_SET_MISMATCH:{requested_changed}")
    if obligation_changed:
        raise SystemExit(f"WS49_OBLIGATION_CHANGE_DETECTED:{obligation_changed}")

    old_target = old_by[EXPECTED_CHANGED]
    new_target = new_by[EXPECTED_CHANGED]
    old_blockers = (old_target.get("combat_state") or {}).get("eligible_blockers")
    new_blockers = (new_target.get("combat_state") or {}).get("eligible_blockers")
    if old_blockers != EXPECTED_OLD_BLOCKERS or new_blockers != EXPECTED_NEW_BLOCKERS:
        raise SystemExit(
            f"WS49_BLOCKER_REPAIR_SHAPE_MISMATCH:old={old_blockers}:new={new_blockers}"
        )

    old_provider_ids = [r["fixture_id"] for r in provider_records(old)]
    new_provider_ids = [r["fixture_id"] for r in provider_records(new)]
    if old_provider_ids != new_provider_ids or len(new_provider_ids) != 107:
        raise SystemExit("WS49_PROVIDER_DENOMINATOR_IDENTITY_ORDER_MISMATCH")

    published_crosscheck: dict[str, Any] = {"used_for_derivation": False}
    if args.published_change_accounting:
        raw = args.published_change_accounting.read_bytes()
        value = json.loads(raw)
        ok = (
            value.get("requested_state_changed_fixture_ids") == [EXPECTED_CHANGED]
            and value.get("obligation_changed_count") == 0
            and value.get("fixture_identity_order_equal") is True
        )
        if not ok:
            raise SystemExit("WS49_PUBLISHED_CHANGE_ACCOUNTING_CROSSCHECK_MISMATCH")
        published_crosscheck["change_accounting_sha256"] = hashlib.sha256(raw).hexdigest()
        published_crosscheck["change_accounting_match"] = True
    if args.published_supersedes:
        raw = args.published_supersedes.read_bytes()
        value = json.loads(raw)
        rows = value.get("representation_repair_rows") or []
        ok = (
            value.get("requested_state_changed_fixture_ids") == [EXPECTED_CHANGED]
            and value.get("obligation_changed") is False
            and len(rows) == 1
            and rows[0].get("fixture_id") == EXPECTED_CHANGED
            and rows[0].get("old") == EXPECTED_OLD_BLOCKERS
            and rows[0].get("new") == EXPECTED_NEW_BLOCKERS
        )
        if not ok:
            raise SystemExit("WS49_PUBLISHED_SUPERSEDES_CROSSCHECK_MISMATCH")
        published_crosscheck["supersedes_sha256"] = hashlib.sha256(raw).hexdigest()
        published_crosscheck["supersedes_match"] = True

    output = {
        "artifact_version": "commander-lab.ws49-v105-impact-reconciliation/1.0.0",
        "historical_successor_runtime_credit_imported": 0,
        "v104": {
            "version": V104_VERSION,
            "sha256": V104_SHA256,
            "canonical_bundle_digest": V104_BUNDLE,
        },
        "v105": {
            "version": CONTRACT_VERSION,
            "canonical_bundle_digest": CANONICAL_MATERIALIZATION_DIGEST,
        },
        "record_count": 135,
        "fixture_identity_order_equal": True,
        "family_identity_order_equal": True,
        "provider_denominator_count": 107,
        "provider_denominator_identity_order_equal": True,
        "all_v105_requested_state_digests_independently_recomputed_equal": True,
        "requested_state_changed_count": 1,
        "requested_state_changed_fixture_ids": requested_changed,
        "only_changed_requested_state": {
            "fixture_id": EXPECTED_CHANGED,
            "path": "combat_state.eligible_blockers",
            "old": old_blockers,
            "new": new_blockers,
        },
        "obligation_changed_count": 0,
        "obligation_changed_fixture_ids": [],
        "published_ws47_crosscheck": published_crosscheck,
        "digest_lineage": digest_lineage,
        "gate": "PASS",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "gate": "PASS",
        "requested_state_changed_fixture_ids": requested_changed,
        "obligation_changed_count": 0,
        "provider_denominator_count": 107,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
