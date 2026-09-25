#!/usr/bin/env python3
"""WS-44 v1.0.4 builder revision 3: schema-composition closure.

Revision 2 already closes semantic referential integrity. Revision 3 changes only
the generated JSON Schema composition so that the schema actually validates the
canonical successor bytes under Draft 2020-12. It does not alter semantic repair
logic, requested-state construction, frozen obligations, or provider semantics.
"""
from __future__ import annotations

import argparse
import copy
from pathlib import Path
from typing import Any

import ws44_build_successor_v2 as V2

_BASE_PATCH_SCHEMA = V2.patch_schema
PROTOCOL = "commander-lab.rules-service/1.1.0"


def patch_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Compose the inherited record extension into the closed base record schema.

    The v1.0.3 schema placed additional record properties beside a $ref whose
    referenced target declares additionalProperties=false. Under Draft 2020-12,
    sibling properties do not amend the referenced closed object, so canonical
    v1.0.3/v1.0.4 record extension fields were rejected. Merge those already-
    declared extension properties and requirements into $defs.record instead.
    """
    schema = _BASE_PATCH_SCHEMA(copy.deepcopy(schema))

    record_def = schema["$defs"]["record"]
    record_items = schema["properties"]["records"]["items"]
    extension_properties = record_items.pop("properties", {})
    extension_required = record_items.pop("required", [])

    record_def.setdefault("properties", {}).update(extension_properties)
    required = list(record_def.get("required", []))
    for name in extension_required:
        if name not in required:
            required.append(name)
    record_def["required"] = required

    # These fields are present in the immutable predecessor materialization but
    # absent from the inherited top-level closed schema. Declare them explicitly;
    # do not remove them from the materialization or infer defaults.
    schema["properties"]["authority_lock"] = {"type": "object"}
    schema["properties"]["protocol_version"] = {"const": PROTOCOL}
    top_required = list(schema.get("required", []))
    for name in ("authority_lock", "protocol_version"):
        if name not in top_required:
            top_required.append(name)
    schema["required"] = top_required

    # Assert the resulting composition has no hidden second record schema.
    assert record_items == {"$ref": "#/$defs/record"}
    assert record_def["properties"]["materialization_version"]["const"] == V2.VERSION
    assert schema["properties"]["schema_version"]["const"] == V2.VERSION
    assert "supersedes" in schema["properties"]
    return schema


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    # V2.build resolves patch_schema from its module globals at runtime. Replace
    # only that pure schema transformation for this invocation.
    V2.patch_schema = patch_schema
    V2.build(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
