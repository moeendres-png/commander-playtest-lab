#!/usr/bin/env python3
"""Immutable WS-32 v1.0.2 lock and provider-neutral digest helpers for WS-34."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

CONTRACT_VERSION = "commander-lab.semantic-fixture-materialization/1.0.2"
CANONICAL_MATERIALIZATION_DIGEST = "ff3b3def5d2ee7c06a4f8eec2173ffa1dec576b5710b9332d5faa537c9653b23"
MATERIALIZATION_FILE_SHA256 = "0d8ff372e1645806f37f5cca1ddeb309c094cee90b8ae4e0b12b8dab08afe261"
FREEZE_BUNDLE_DIGEST = "61002a78c7fdd2ab4bec30e64742a7954e9a6448e8f39e05503dbe26492aa20b"
FREEZE_MANIFEST_SHA256 = "3c1e45faaa6b6de1db80bcb86a98055d461d715314d2215bb585303de00f4e83"
FREEZE_COMMIT = "038d0f38635eecee4e331c99af41f148de267a26"
FREEZE_TREE = "0d160128119f2bad30b220a17c43419b50b7edbe"
VALIDATION_MARKER_COMMIT = "62d7bd4fdeca8ecc2435d29f35f4abf095021e55"
VALIDATION_RUN_ID = 33570562695

XMAGE_COMMIT = "77d7646da6958fdf8125ee7c8f4aabd130d21d4c"
XMAGE_TREE = "f0a028b265f9c008ea0aedc4cec6b8f14500b69f"

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
    if hashlib.sha256(raw).hexdigest() != MATERIALIZATION_FILE_SHA256:
        raise RuntimeError("WS32_MATERIALIZATION_FILE_SHA_MISMATCH")
    value = json.loads(raw)
    if value.get("schema_version") != CONTRACT_VERSION:
        raise RuntimeError("WS32_CONTRACT_VERSION_MISMATCH")
    if value.get("canonical_bundle_digest") != CANONICAL_MATERIALIZATION_DIGEST:
        raise RuntimeError("WS32_CANONICAL_MATERIALIZATION_DIGEST_MISMATCH")
    records = value.get("records")
    if not isinstance(records, list) or len(records) != 135:
        raise RuntimeError("WS32_RECORD_DENOMINATOR_MISMATCH")
    for record in records:
        if record.get("materialization_digest") != record_digest(record):
            raise RuntimeError(f"WS32_RECORD_DIGEST_MISMATCH:{record.get('fixture_id')}")
        if record.get("requested_state_digest") != requested_state_digest(record):
            raise RuntimeError(f"WS32_REQUESTED_STATE_DIGEST_MISMATCH:{record.get('fixture_id')}")
        if record.get("semantic_executability") != "SEMANTIC_EXECUTABLE":
            raise RuntimeError(f"WS32_RECORD_NOT_EXECUTABLE:{record.get('fixture_id')}")
    return value


def ws34_records(contract: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        record
        for record in contract["records"]
        if record.get("fixture_family") != "actual_card" or record.get("fixture_id") == "CARD_02"
    ]
    if len(rows) != 107:
        raise RuntimeError(f"WS34_DENOMINATOR_MISMATCH:{len(rows)}")
    return rows
