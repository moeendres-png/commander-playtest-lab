#!/usr/bin/env python3
"""WS-44 v1.0.4 builder revision 4: exact schema exception modeling.

Revision 3 closed inherited $ref/additionalProperties composition. Revision 4
models the two predecessor-authorized representation alternatives exactly:
- replay_rng records may omit execution_transaction_policy;
- rules_randomness is either materialized by explicit numeric seed + predetermined
  semantic draws, or by an explicit SCENARIO_SEED binding.
No semantic record bytes or frozen obligations are changed by this revision.
"""
from __future__ import annotations

import argparse
import copy
from pathlib import Path
from typing import Any

import ws44_build_successor_v3 as V3
import ws44_build_successor_v2 as V2

_BASE_PATCH_SCHEMA = V3.patch_schema


def patch_schema(schema: dict[str, Any]) -> dict[str, Any]:
    schema = _BASE_PATCH_SCHEMA(copy.deepcopy(schema))
    record = schema["$defs"]["record"]

    required = list(record.get("required", []))
    if "execution_transaction_policy" not in required:
        raise RuntimeError("expected inherited execution_transaction_policy requirement")
    required.remove("execution_transaction_policy")
    record["required"] = required

    # Preserve the requirement for every non-replay_rng record. The exact five
    # replay_rng records are the only predecessor records that omit this field.
    record.setdefault("allOf", []).append({
        "if": {
            "properties": {"fixture_family": {"not": {"const": "replay_rng"}}},
            "required": ["fixture_family"],
        },
        "then": {"required": ["execution_transaction_policy"]},
    })

    rr = record["properties"]["rules_randomness"]
    rr["required"] = ["channels", "pilot_randomness_prohibited"]
    rr["properties"] = {
        "rules_seed": {"type": "integer"},
        "channels": {"type": "array", "items": {"type": "string"}},
        "predetermined_semantic_draws": {"type": "array"},
        "pilot_randomness_prohibited": {"const": True},
        "seed_binding": {"const": "SCENARIO_SEED"},
        "provider_native_rng_calls_recorded": {"type": "boolean"},
    }
    rr["additionalProperties"] = True
    rr["oneOf"] = [
        {
            "required": ["rules_seed", "predetermined_semantic_draws"],
            "not": {"required": ["seed_binding"]},
        },
        {
            "required": ["seed_binding"],
            "not": {"anyOf": [
                {"required": ["rules_seed"]},
                {"required": ["predetermined_semantic_draws"]},
            ]},
        },
    ]

    assert record["properties"]["materialization_version"]["const"] == V2.VERSION
    return schema


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    V2.patch_schema = patch_schema
    V2.build(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
