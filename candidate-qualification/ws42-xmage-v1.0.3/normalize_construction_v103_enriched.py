#!/usr/bin/env python3
"""WS42 independent construction normalization with native attachment proof.

This wrapper extends the base field-by-field normalizer for the attachment
surface implemented by XmageWs42NativeStateExtension.  The immutable contract
is used only to identify which semantic object is expected to have an
attachment relation and to compare the expected semantic target.  The value
emitted into normalized constructed state is taken from the provider-native
setup-boundary readback field ``attached_to_semantic_id``.

No inherited whole-request echo or requested-state digest is consumed as proof.
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


def normalize_semantic_objects(
    record: dict[str, Any], readback: dict[str, Any]
) -> list[dict[str, Any]]:
    fixture_id = record["fixture_id"]

    # Let the frozen base normalizer handle every already-qualified field.  We
    # remove only attachment expectations from the comparison copy so the base
    # function cannot accidentally treat contract metadata as native proof.
    comparison_record = copy.deepcopy(record)
    attachment_expectations: dict[str, str] = {}
    for obj in comparison_record["semantic_objects"]:
        attached_to = obj.pop("attached_to", None)
        if attached_to is not None:
            attachment_expectations[str(obj["semantic_id"])] = str(attached_to)

    rows = _ORIGINAL_NORMALIZE_SEMANTIC_OBJECTS(comparison_record, readback)
    if not attachment_expectations:
        return rows

    native_objects = base.native_scenario_objects(readback, fixture_id)
    rows_by_id = {str(row["semantic_id"]): row for row in rows}

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


def main() -> int:
    base.normalize_semantic_objects = normalize_semantic_objects
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
