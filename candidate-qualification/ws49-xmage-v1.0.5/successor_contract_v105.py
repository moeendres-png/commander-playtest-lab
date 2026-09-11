#!/usr/bin/env python3
"""Immutable WS-47 v1.0.5 lock and provider-neutral digest helpers for WS-49."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

CONTRACT_VERSION = "commander-lab.semantic-fixture-materialization/1.0.5"
CANONICAL_MATERIALIZATION_DIGEST = "631da205c4889929b87e1a3bbf342e8a5bd168e678c7551aaf6ca7a901901e01"
MATERIALIZATION_FILE_SHA256 = "0e47b792cc5232fa0ef06a0cab2a4ebfe9d72d4cbc8bc2bfc5c22b9bf7a940b3"
FREEZE_COMMIT = "192e2b77c0625ad26905bd0ee8dcc3f44a5796c8"
FREEZE_TREE = "f596c54d2cb229b9827c6c94a278175e8312c65c"
NAMESPACE_TREE = "12af73695c801a42a0193ee895d5fc0843d16b0c"

XMAGE_COMMIT = "0c1f455ea8c8fa48ab9d638ad5068ec242800428"
XMAGE_TREE = "fdb8bf56a8bd8199a4ef372e468d93d6550b0649"

STATE_KEYS = (
    "execution_entry_mode",
    "players",
    "deck_state",
    "commander_state",
    "semantic_objects",
    "temporal_state",
    "knowledge_state",
    "rules_randomness",
    "combat_state",
    "stack_state",
    "continuous_rules_effects",
    "extra_turn_creation",
    "elimination_trigger",
    "zone_move_event",
    "setup_validation",
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_sha(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def requested_state_projection(record: dict[str, Any]) -> dict[str, Any]:
    return {key: copy.deepcopy(record[key]) for key in STATE_KEYS if key in record}


def requested_state_digest(record: dict[str, Any]) -> str:
    return canonical_sha(requested_state_projection(record))


def record_digest(record: dict[str, Any]) -> str:
    clone = copy.deepcopy(record)
    clone.pop("materialization_digest", None)
    return canonical_sha(clone)


def load_contract(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    file_sha = hashlib.sha256(raw).hexdigest()
    if file_sha != MATERIALIZATION_FILE_SHA256:
        raise RuntimeError(f"WS49_WS47_MATERIALIZATION_FILE_SHA_MISMATCH:{file_sha}")
    value = json.loads(raw)
    if value.get("schema_version") != CONTRACT_VERSION:
        raise RuntimeError("WS49_WS47_CONTRACT_VERSION_MISMATCH")
    if value.get("canonical_bundle_digest") != CANONICAL_MATERIALIZATION_DIGEST:
        raise RuntimeError("WS49_WS47_CANONICAL_BUNDLE_DIGEST_MISMATCH")
    records = value.get("records")
    if not isinstance(records, list) or len(records) != 135:
        raise RuntimeError("WS49_WS47_RECORD_DENOMINATOR_MISMATCH")
    seen: set[str] = set()
    for record in records:
        fixture_id = record.get("fixture_id")
        if not isinstance(fixture_id, str) or not fixture_id or fixture_id in seen:
            raise RuntimeError(f"WS49_WS47_FIXTURE_ID_INVALID_OR_DUPLICATE:{fixture_id}")
        seen.add(fixture_id)
        if record.get("materialization_digest") != record_digest(record):
            raise RuntimeError(f"WS49_WS47_RECORD_DIGEST_MISMATCH:{fixture_id}")
        if record.get("requested_state_digest") != requested_state_digest(record):
            raise RuntimeError(f"WS49_WS47_REQUESTED_STATE_DIGEST_MISMATCH:{fixture_id}")
        if record.get("semantic_executability") != "SEMANTIC_EXECUTABLE":
            raise RuntimeError(f"WS49_WS47_RECORD_NOT_EXECUTABLE:{fixture_id}")
    return value


def provider_records(contract: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        r for r in contract["records"]
        if r.get("fixture_family") != "actual_card" or r.get("fixture_id") == "CARD_02"
    ]
    ids = [r["fixture_id"] for r in rows]
    if len(rows) != 107 or len(set(ids)) != 107:
        raise RuntimeError(f"WS49_PROVIDER_DENOMINATOR_MISMATCH:{len(rows)}:{len(set(ids))}")
    excluded = {
        r["fixture_id"] for r in contract["records"]
        if r.get("fixture_family") == "actual_card" and r.get("fixture_id") != "CARD_02"
    }
    expected = {f"CARD_{n:02d}" for n in range(1, 30)} - {"CARD_02"}
    if excluded != expected:
        raise RuntimeError("WS49_ACTUAL_CARD_EXCLUSION_SET_MISMATCH")
    return rows
