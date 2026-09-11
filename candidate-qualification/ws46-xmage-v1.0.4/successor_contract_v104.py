#!/usr/bin/env python3
"""Immutable WS-44 v1.0.4 lock and provider-neutral digest helpers for WS-46."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

CONTRACT_VERSION = "commander-lab.semantic-fixture-materialization/1.0.4"
CANONICAL_MATERIALIZATION_DIGEST = "77b911195525c2fe8aff37f6c9573e5772f358b25646d0be5919314ed5e23b54"
MATERIALIZATION_FILE_SHA256 = "9b370244e4e5df3132e6e9a3d2b70ad641a5a6023fc7c86832931340d24bfa35"
FREEZE_COMMIT = "12940248497a8795991cbbd2eedef72945528cfe"
FREEZE_TREE = "cd83c973b269711106d08ab5be2d7672f05bcb7c"
NAMESPACE_TREE = "6579e119605b90248426a3121a47c487b2bb13cd"

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
        raise RuntimeError(f"WS44_MATERIALIZATION_FILE_SHA_MISMATCH:{file_sha}")
    value = json.loads(raw)
    if value.get("schema_version") != CONTRACT_VERSION:
        raise RuntimeError("WS44_CONTRACT_VERSION_MISMATCH")
    if value.get("canonical_bundle_digest") != CANONICAL_MATERIALIZATION_DIGEST:
        raise RuntimeError("WS44_CANONICAL_MATERIALIZATION_DIGEST_MISMATCH")
    records = value.get("records")
    if not isinstance(records, list) or len(records) != 135:
        raise RuntimeError("WS44_RECORD_DENOMINATOR_MISMATCH")
    seen: set[str] = set()
    for record in records:
        fixture_id = record.get("fixture_id")
        if not isinstance(fixture_id, str) or not fixture_id or fixture_id in seen:
            raise RuntimeError(f"WS44_FIXTURE_ID_INVALID_OR_DUPLICATE:{fixture_id}")
        seen.add(fixture_id)
        if record.get("materialization_digest") != record_digest(record):
            raise RuntimeError(f"WS44_RECORD_DIGEST_MISMATCH:{fixture_id}")
        if record.get("requested_state_digest") != requested_state_digest(record):
            raise RuntimeError(f"WS44_REQUESTED_STATE_DIGEST_MISMATCH:{fixture_id}")
        if record.get("semantic_executability") != "SEMANTIC_EXECUTABLE":
            raise RuntimeError(f"WS44_RECORD_NOT_EXECUTABLE:{fixture_id}")
    return value


def provider_records(contract: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [r for r in contract["records"] if r.get("fixture_family") != "actual_card" or r.get("fixture_id") == "CARD_02"]
    ids = [r["fixture_id"] for r in rows]
    if len(rows) != 107 or len(set(ids)) != 107:
        raise RuntimeError(f"WS46_DENOMINATOR_MISMATCH:{len(rows)}:{len(set(ids))}")
    excluded = {r["fixture_id"] for r in contract["records"] if r.get("fixture_family") == "actual_card" and r.get("fixture_id") != "CARD_02"}
    expected = {f"CARD_{n:02d}" for n in range(1, 30)} - {"CARD_02"}
    if excluded != expected:
        raise RuntimeError("WS46_ACTUAL_CARD_EXCLUSION_SET_MISMATCH")
    return rows
