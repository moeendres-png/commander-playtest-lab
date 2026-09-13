#!/usr/bin/env python3
"""WS42 independent construction normalization for extended native state.

This wrapper extends the base field-by-field normalizer only for state surfaces
that WS42 restores through XMage-native APIs and reads back independently before
priority/state-based-action continuation.

The immutable contract supplies semantic labels and comparison expectations.
Dynamic values emitted into normalized constructed state are taken from native
readback. No inherited whole-request echo or requested-state digest is consumed
as construction proof.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import normalize_construction_v103 as base  # noqa: E402

_ORIGINAL_NORMALIZE_SEMANTIC_OBJECTS = base.normalize_semantic_objects
_ORIGINAL_NORMALIZE_COMMANDER_STATE = base.normalize_commander_state


def _native_revealed_ids(readback: dict[str, Any], fixture_id: str) -> set[str]:
    validation = readback.get("native_validation")
    revealed = validation.get("ws42_revealed_state") if isinstance(validation, dict) else None
    if not isinstance(revealed, dict) or revealed.get("valid") is not True:
        base.fail("WS42_NORMALIZE_REVEALED_VALIDATION_MISSING", fixture_id)
    if revealed.get("native_surface") != "GameState.getRevealed":
        base.fail("WS42_NORMALIZE_REVEALED_NATIVE_SURFACE_MISMATCH", fixture_id)
    if revealed.get("physical_zone_fabricated") is not False:
        base.fail("WS42_NORMALIZE_REVEALED_PHYSICAL_ZONE_FABRICATED", fixture_id)
    rows = revealed.get("semantic_revealed_objects")
    if not isinstance(rows, list):
        base.fail("WS42_NORMALIZE_REVEALED_READBACK_MISSING", fixture_id)
    result: set[str] = set()
    for row in rows:
        sid = row.get("semantic_id") if isinstance(row, dict) else None
        if not isinstance(sid, str) or row.get("native_revealed") is not True or sid in result:
            base.fail("WS42_NORMALIZE_REVEALED_ROW_INVALID", fixture_id, row)
        result.add(sid)
    return result


def normalize_semantic_objects(
    record: dict[str, Any], readback: dict[str, Any]
) -> list[dict[str, Any]]:
    fixture_id = record["fixture_id"]

    # Let the frozen base normalizer handle every already-qualified field. We
    # remove only extension expectations from the comparison copy so the base
    # function cannot accidentally treat contract metadata as native proof.
    comparison_record = copy.deepcopy(record)
    attachment_expectations: dict[str, str] = {}
    revealed_expectations: set[str] = set()
    for obj in comparison_record["semantic_objects"]:
        semantic_id = str(obj["semantic_id"])
        attached_to = obj.pop("attached_to", None)
        if attached_to is not None:
            attachment_expectations[semantic_id] = str(attached_to)
        if obj.get("zone") == "revealed":
            # XMage's native storage remains library. Semantic `revealed` is
            # emitted only after the separate native GameState.revealed proof.
            obj["zone"] = "library"
            revealed_expectations.add(semantic_id)

    rows = _ORIGINAL_NORMALIZE_SEMANTIC_OBJECTS(comparison_record, readback)
    rows_by_id = {str(row["semantic_id"]): row for row in rows}

    if revealed_expectations:
        native_revealed = _native_revealed_ids(readback, fixture_id)
        if native_revealed != revealed_expectations:
            base.fail(
                "WS42_NORMALIZE_REVEALED_SET_MISMATCH",
                fixture_id,
                {"native": sorted(native_revealed), "requested": sorted(revealed_expectations)},
            )
        for semantic_id in sorted(revealed_expectations):
            row = rows_by_id.get(semantic_id)
            if row is None:
                base.fail("WS42_NORMALIZE_REVEALED_ROW_MISSING", fixture_id, semantic_id)
            # This semantic zone value is derived solely from native reveal
            # membership proven above, never copied from the request object.
            row["zone"] = "revealed"

    if attachment_expectations:
        native_objects = base.native_scenario_objects(readback, fixture_id)
        for semantic_id, expected_target in sorted(attachment_expectations.items()):
            native_object = native_objects.get(semantic_id)
            if native_object is None:
                base.fail("WS42_NORMALIZE_ATTACHMENT_OBJECT_MISSING", fixture_id, semantic_id)
            native_target = native_object.get("attached_to_semantic_id")
            if native_target is None:
                base.fail("WS42_NORMALIZE_ATTACHMENT_READBACK_MISSING", fixture_id, semantic_id)
            if str(native_target) != expected_target:
                base.fail(
                    "WS42_NORMALIZE_ATTACHMENT_TARGET_MISMATCH",
                    fixture_id,
                    {
                        "semantic_id": semantic_id,
                        "native": native_target,
                        "requested": expected_target,
                    },
                )
            row = rows_by_id.get(semantic_id)
            if row is None:
                base.fail("WS42_NORMALIZE_ATTACHMENT_ROW_MISSING", fixture_id, semantic_id)
            # Crucially, emit the native value, not the requested comparison value.
            row["attached_to"] = str(native_target)

    return rows


def _native_commander_damage(
    readback: dict[str, Any], fixture_id: str
) -> list[dict[str, Any]]:
    validation = readback.get("native_validation")
    extension = validation.get("ws42_native_state_extension") if isinstance(validation, dict) else None
    if not isinstance(extension, dict) or extension.get("valid") is not True:
        base.fail("WS42_NORMALIZE_NATIVE_EXTENSION_VALIDATION_MISSING", fixture_id)
    matrix = extension.get("commander_damage_matrix")
    if not isinstance(matrix, list):
        base.fail("WS42_NORMALIZE_COMMANDER_DAMAGE_READBACK_MISSING", fixture_id)
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in matrix:
        if not isinstance(item, dict):
            base.fail("WS42_NORMALIZE_COMMANDER_DAMAGE_ROW_INVALID", fixture_id, item)
        source = item.get("source_commander_id")
        damaged = item.get("damaged_player")
        amount = item.get("combat_damage")
        if not isinstance(source, str) or not isinstance(damaged, str) or not isinstance(amount, int) or isinstance(amount, bool):
            base.fail("WS42_NORMALIZE_COMMANDER_DAMAGE_ROW_INVALID", fixture_id, item)
        key = (source, damaged)
        if key in seen:
            base.fail("WS42_NORMALIZE_COMMANDER_DAMAGE_DUPLICATE_NATIVE_ROW", fixture_id, key)
        seen.add(key)
        result.append(
            {
                "source_commander_id": source,
                "damaged_player": damaged,
                "combat_damage": amount,
            }
        )
    return result


def normalize_commander_state(record: dict[str, Any], readback: dict[str, Any]) -> dict[str, Any]:
    fixture_id = record["fixture_id"]
    requested_matrix = record["commander_state"].get("commander_damage_matrix") or []

    # The base normalizer remains authoritative for commander identity, zone,
    # owner, partner relationship and native command-zone cast history. Remove
    # only the non-empty damage matrix from its comparison copy because the base
    # implementation intentionally fail-closes that previously unsupported field.
    comparison_record = copy.deepcopy(record)
    comparison_record["commander_state"]["commander_damage_matrix"] = []
    normalized = _ORIGINAL_NORMALIZE_COMMANDER_STATE(comparison_record, readback)
    if not requested_matrix:
        return normalized

    native_matrix = _native_commander_damage(readback, fixture_id)
    native_by_key = {
        (row["source_commander_id"], row["damaged_player"]): row
        for row in native_matrix
    }
    if len(native_by_key) != len(native_matrix):
        base.fail("WS42_NORMALIZE_COMMANDER_DAMAGE_NATIVE_KEY_COLLISION", fixture_id)
    if len(native_matrix) != len(requested_matrix):
        base.fail(
            "WS42_NORMALIZE_COMMANDER_DAMAGE_MATRIX_SIZE_MISMATCH",
            fixture_id,
            {"native": len(native_matrix), "requested": len(requested_matrix)},
        )

    rows: list[dict[str, Any]] = []
    for expected in requested_matrix:
        key = (expected.get("source_commander_id"), expected.get("damaged_player"))
        native = native_by_key.get(key)
        if native is None:
            base.fail("WS42_NORMALIZE_COMMANDER_DAMAGE_NATIVE_ROW_MISSING", fixture_id, key)
        if int(native["combat_damage"]) != int(expected.get("combat_damage", -1)):
            base.fail(
                "WS42_NORMALIZE_COMMANDER_DAMAGE_VALUE_MISMATCH",
                fixture_id,
                {"key": key, "native": native["combat_damage"], "requested": expected.get("combat_damage")},
            )
        # Emit the request-independent native readback row. The semantic IDs in
        # it are mapping labels validated by the native extension; the damage
        # amount itself comes from CommanderInfoWatcher.getDamageToPlayer().
        rows.append(copy.deepcopy(native))

    normalized["commander_damage_matrix"] = rows
    return normalized


def main() -> int:
    base.normalize_semantic_objects = normalize_semantic_objects
    base.normalize_commander_state = normalize_commander_state
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
