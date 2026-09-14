#!/usr/bin/env python3
"""Immutable WS-41 v1.0.3 lock and provider-neutral digest helpers for WS-42."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

CONTRACT_VERSION = "commander-lab.semantic-fixture-materialization/1.0.3"
CANONICAL_MATERIALIZATION_DIGEST = "545afdeda53a11a2ebb32f534aa1b3186f434aa90bec2c8f2f232851e1abd31b"
MATERIALIZATION_FILE_SHA256 = "8f6e3778e96079dbb501b9f5d72f007da0549e26b836011a855c0dbd2c6237c5"
FREEZE_COMMIT = "24152acf36b5a560c23ccacfed3f31d3039537eb"
FREEZE_TREE = "428bbe58b2ea7b869200521092a8768108029b47"

XMAGE_COMMIT = "7bde812727817723616c575759f39bfc4cda4607"
XMAGE_TREE = "a44f32e9d34109ac3f272494f0e8eb9ea3e6280c"

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
        raise RuntimeError(f"WS41_MATERIALIZATION_FILE_SHA_MISMATCH:{file_sha}")
    value = json.loads(raw)
    if value.get("schema_version") != CONTRACT_VERSION:
        raise RuntimeError("WS41_CONTRACT_VERSION_MISMATCH")
    if value.get("canonical_bundle_digest") != CANONICAL_MATERIALIZATION_DIGEST:
        raise RuntimeError("WS41_CANONICAL_MATERIALIZATION_DIGEST_MISMATCH")
    records = value.get("records")
    if not isinstance(records, list) or len(records) != 135:
        raise RuntimeError("WS41_RECORD_DENOMINATOR_MISMATCH")
    seen: set[str] = set()
    for record in records:
        fixture_id = record.get("fixture_id")
        if not isinstance(fixture_id, str) or not fixture_id or fixture_id in seen:
            raise RuntimeError(f"WS41_FIXTURE_ID_INVALID_OR_DUPLICATE:{fixture_id}")
        seen.add(fixture_id)
        if record.get("materialization_digest") != record_digest(record):
            raise RuntimeError(f"WS41_RECORD_DIGEST_MISMATCH:{fixture_id}")
        if record.get("requested_state_digest") != requested_state_digest(record):
            raise RuntimeError(f"WS41_REQUESTED_STATE_DIGEST_MISMATCH:{fixture_id}")
        if record.get("semantic_executability") != "SEMANTIC_EXECUTABLE":
            raise RuntimeError(f"WS41_RECORD_NOT_EXECUTABLE:{fixture_id}")
    return value


def provider_records(contract: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        record
        for record in contract["records"]
        if record.get("fixture_family") != "actual_card" or record.get("fixture_id") == "CARD_02"
    ]
    ids = [row["fixture_id"] for row in rows]
    if len(rows) != 107 or len(set(ids)) != 107:
        raise RuntimeError(f"WS42_DENOMINATOR_MISMATCH:{len(rows)}:{len(set(ids))}")
    excluded = {
        record["fixture_id"]
        for record in contract["records"]
        if record.get("fixture_family") == "actual_card" and record.get("fixture_id") != "CARD_02"
    }
    expected_excluded = {f"CARD_{number:02d}" for number in range(1, 30)} - {"CARD_02"}
    if excluded != expected_excluded:
        raise RuntimeError("WS42_ACTUAL_CARD_EXCLUSION_SET_MISMATCH")
    return rows
