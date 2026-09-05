#!/usr/bin/env python3
"""Fail-closed audit of WS-42's provider translation against immutable v1.0.3.

This validates translation integrity only. It does not inspect XMage runtime and
therefore grants no construction or behavior credit.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from canonical_v103 import deck_and_scenario
from successor_contract_v103 import canonical_sha, load_contract, provider_records


def _seed_binding(record: dict[str, Any], scenario: dict[str, Any]) -> tuple[str, int | None, int]:
    randomness = record.get("rules_randomness")
    if not isinstance(randomness, dict):
        raise RuntimeError(f"WS42_RULES_RANDOMNESS_MISSING:{record['fixture_id']}")
    scenario_seed = scenario.get("seed")
    if not isinstance(scenario_seed, int) or isinstance(scenario_seed, bool) or scenario_seed < 0:
        raise RuntimeError(f"WS42_EXECUTION_SEED_INVALID:{record['fixture_id']}:{scenario_seed!r}")

    fixed = randomness.get("rules_seed")
    if isinstance(fixed, int) and not isinstance(fixed, bool):
        if scenario_seed != fixed:
            raise RuntimeError(
                f"WS42_EXECUTION_SEED_MISMATCH:{record['fixture_id']}:{scenario_seed}:{fixed}"
            )
        return "CONTRACT_FIXED_RULES_SEED", fixed, scenario_seed

    if fixed is not None:
        raise RuntimeError(f"WS42_RULES_SEED_INVALID:{record['fixture_id']}:{fixed!r}")
    if randomness.get("seed_binding") != "SCENARIO_SEED":
        raise RuntimeError(f"WS42_RULES_SEED_BINDING_MISSING:{record['fixture_id']}")
    return "CONTRACT_SCENARIO_SEED_BINDING", None, scenario_seed


def _audit_record(record: dict[str, Any]) -> dict[str, Any]:
    decks, scenario = deck_and_scenario(record)
    translated = scenario.get("successor_requested_state")
    if not isinstance(translated, dict):
        raise RuntimeError(f"WS42_TRANSLATED_REQUEST_MISSING:{record['fixture_id']}")
    translated_digest = canonical_sha(translated)
    expected_digest = record["requested_state_digest"]
    if translated_digest != expected_digest:
        raise RuntimeError(
            f"WS42_TRANSLATED_REQUEST_DIGEST_MISMATCH:{record['fixture_id']}:"
            f"{translated_digest}:{expected_digest}"
        )
    embedded_digest = scenario.get("successor_requested_state_digest")
    if embedded_digest != expected_digest:
        raise RuntimeError(
            f"WS42_EMBEDDED_REQUEST_DIGEST_MISMATCH:{record['fixture_id']}:"
            f"{embedded_digest}:{expected_digest}"
        )

    randomness = record.get("rules_randomness")
    if translated.get("rules_randomness") != randomness:
        raise RuntimeError(f"WS42_TRANSLATED_RANDOMNESS_MUTATED:{record['fixture_id']}")
    seed_binding_mode, contract_seed, scenario_seed = _seed_binding(record, scenario)

    if len(decks) != len(record["players"]):
        raise RuntimeError(
            f"WS42_TRANSLATED_DECK_COUNT_MISMATCH:{record['fixture_id']}:"
            f"{len(decks)}:{len(record['players'])}"
        )

    return {
        "fixture_id": record["fixture_id"],
        "fixture_family": record["fixture_family"],
        "record_digest": record["materialization_digest"],
        "requested_state_digest": expected_digest,
        "translated_requested_state_digest": translated_digest,
        "request_digest_exact": True,
        "contract_rules_seed": contract_seed,
        "scenario_execution_seed": scenario_seed,
        "seed_binding_mode": seed_binding_mode,
        "rules_seed_binding_exact": True,
        "player_count": len(record["players"]),
        "translated_deck_count": len(decks),
        "runtime_credit": "NONE",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    contract = load_contract(args.contract)
    records = provider_records(contract)
    rows = [_audit_record(record) for record in records]
    if len(rows) != 107 or len({row["fixture_id"] for row in rows}) != 107:
        raise RuntimeError("WS42_TRANSLATION_DENOMINATOR_MISMATCH")

    binding_counts: dict[str, int] = {}
    for row in rows:
        mode = row["seed_binding_mode"]
        binding_counts[mode] = binding_counts.get(mode, 0) + 1
    if binding_counts != {
        "CONTRACT_FIXED_RULES_SEED": 100,
        "CONTRACT_SCENARIO_SEED_BINDING": 7,
    }:
        raise RuntimeError(f"WS42_RULES_SEED_BINDING_DENOMINATOR_MISMATCH:{binding_counts}")

    output = {
        "schema_version": "commander-lab.ws42-translation-integrity/1.0.1",
        "materialization_version": contract["schema_version"],
        "canonical_bundle_digest": contract["canonical_bundle_digest"],
        "denominator": 107,
        "record_count": len(rows),
        "all_request_digests_exact": all(row["request_digest_exact"] for row in rows),
        "all_rules_seed_bindings_exact": all(row["rules_seed_binding_exact"] for row in rows),
        # Compatibility field retained for the existing CI assertion. Its value
        # means the complete seed contract (fixed or SCENARIO_SEED-bound) is exact.
        "all_rules_seeds_exact": all(row["rules_seed_binding_exact"] for row in rows),
        "seed_binding_counts": binding_counts,
        "historical_runtime_pass_imported": False,
        "construction_credit_granted": False,
        "behavior_runtime_credit_granted": False,
        "records": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "record_count": len(rows),
        "all_request_digests_exact": output["all_request_digests_exact"],
        "all_rules_seed_bindings_exact": output["all_rules_seed_bindings_exact"],
        "seed_binding_counts": binding_counts,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
