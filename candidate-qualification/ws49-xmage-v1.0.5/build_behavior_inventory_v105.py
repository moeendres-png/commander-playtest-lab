#!/usr/bin/env python3
"""Build WS49 G49-09 behavior obligation inventory from immutable WS47 v1.0.5.

Reads the exact WS47 materialization (SHA-pinned by successor_contract_v105),
filters the 107-record provider denominator, and emits one obligation row per
record: entry mode, decision families/selectors, native procedure, expected
events, terminal postconditions, RNG channels, and viewer states.

Strict validation (fail-closed, no engine needed):
- exact contract/file/bundle/record digests (via successor_contract_v105)
- exactly 107 unique provider fixture ids, family/entry-mode distributions
- every decision entry carries all 7 forbidden fallbacks, FAIL_CLOSED on
  zero/multiple match, and matches_only_provider_offered_legal_options
- every record carries a non-empty native procedure, expected events, and
  terminal postconditions

Output grants zero behavior credit. It is the execution plan G49-09 runs.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from successor_contract_v105 import (
    CANONICAL_MATERIALIZATION_DIGEST,
    CONTRACT_VERSION,
    FREEZE_COMMIT,
    FREEZE_TREE,
    MATERIALIZATION_FILE_SHA256,
    NAMESPACE_TREE,
    load_contract,
    provider_records,
)

EXPECTED_FAMILIES = {
    "player_count": 4,
    "pilot_boundary": 17,
    "pilot_boundary_negative": 7,
    "hidden_information": 20,
    "replay_rng": 5,
    "micro_rules": 17,
    "actual_card": 1,
    "multiplayer_commander": 36,
}
EXPECTED_ENTRY_MODES = {"NATIVE_STATE_LOAD": 100, "NATURAL_GAME_START": 7}
EXPECTED_NATURAL_START_FIXTURES = [
    "PLAYER_COUNT_2P",
    "PLAYER_COUNT_3P",
    "PLAYER_COUNT_4P",
    "PLAYER_COUNT_5P",
    "PILOT_MULLIGAN",
    "WS05-CMD-MULL-2",
    "WS05-CMD-MULL-4",
]
ALL_FALLBACKS = {
    "first_option",
    "random_option",
    "default_yes_no",
    "internal_ai",
    "gui_default",
    "silent_skip",
    "parent_class_fallback",
}


def check(cond: bool, code: str, detail: Any = None) -> None:
    if not cond:
        suffix = "" if detail is None else ":" + json.dumps(detail, sort_keys=True)[:500]
        raise SystemExit(f"WS49_BEHAVIOR_INVENTORY_{code}{suffix}")


def inventory_decision(entry: dict[str, Any], fixture_id: str) -> dict[str, Any]:
    check(isinstance(entry, dict), "DECISION_ENTRY_NOT_OBJECT", fixture_id)
    for key in ("actor", "causal_step_id", "decision_family"):
        check(
            isinstance(entry.get(key), str) and entry[key],
            "DECISION_ENTRY_FIELD_INVALID",
            [fixture_id, key],
        )
    check(
        set(entry.get("forbidden_fallbacks") or []) == ALL_FALLBACKS,
        "DECISION_FALLBACK_SET_CHANGED",
        fixture_id,
    )
    selection = entry.get("selection")
    check(isinstance(selection, dict), "DECISION_SELECTION_NOT_OBJECT", fixture_id)
    check(
        selection.get("matches_only_provider_offered_legal_options") is True,
        "DECISION_MATCH_POLICY_CHANGED",
        fixture_id,
    )
    check(
        selection.get("on_multiple_match") == "FAIL_CLOSED",
        "DECISION_MULTIPLE_MATCH_NOT_FAIL_CLOSED",
        fixture_id,
    )
    check(
        selection.get("on_zero_match") == "FAIL_CLOSED",
        "DECISION_ZERO_MATCH_NOT_FAIL_CLOSED",
        fixture_id,
    )
    check(
        isinstance(selection.get("selector_kind"), str) and selection["selector_kind"],
        "DECISION_SELECTOR_KIND_INVALID",
        fixture_id,
    )
    return {
        "actor": entry["actor"],
        "causal_step_id": entry["causal_step_id"],
        "decision_family": entry["decision_family"],
        "selector_kind": selection["selector_kind"],
        "semantic_value": selection.get("semantic_value"),
        "notes": entry.get("notes") or "",
    }


def inventory_record(ordinal: int, record: dict[str, Any]) -> dict[str, Any]:
    fixture_id = record["fixture_id"]
    players = record.get("players") or []
    player_ids = [
        p["player_id"]
        for p in players
        if isinstance(p, dict) and isinstance(p.get("player_id"), str)
    ]
    check(
        len(player_ids) == len(players) and len(set(player_ids)) == len(player_ids),
        "RECORD_PLAYERS_INVALID",
        fixture_id,
    )

    decisions = [inventory_decision(e, fixture_id) for e in (record.get("decision_script") or [])]
    for d in decisions:
        if d["selector_kind"] != "fail_closed_probe":
            check(d["actor"] in player_ids, "DECISION_ACTOR_NOT_A_PLAYER", [fixture_id, d["actor"]])

    procedure = record.get("native_procedure") or []
    check(isinstance(procedure, list) and len(procedure) > 0, "NATIVE_PROCEDURE_EMPTY", fixture_id)
    ops = []
    for step in procedure:
        check(
            isinstance(step, dict) and isinstance(step.get("operation"), str),
            "NATIVE_PROCEDURE_STEP_INVALID",
            fixture_id,
        )
        ops.append(step["operation"])

    expected = record.get("expected_events") or {}
    check(
        isinstance(expected.get("required_events"), list),
        "EXPECTED_EVENTS_REQUIRED_MISSING",
        fixture_id,
    )
    check(
        isinstance(expected.get("forbidden_events"), list),
        "EXPECTED_EVENTS_FORBIDDEN_MISSING",
        fixture_id,
    )
    terminals = record.get("terminal_postconditions")
    check(
        isinstance(terminals, list)
        and len(terminals) > 0
        and all(isinstance(t, str) and t for t in terminals),
        "TERMINAL_POSTCONDITIONS_EMPTY",
        fixture_id,
    )

    rng = record.get("rules_randomness") or {}
    knowledge = record.get("knowledge_state") or {}
    viewers = [
        v.get("viewer") for v in (knowledge.get("viewer_states") or []) if isinstance(v, dict)
    ]

    return {
        "ordinal": ordinal,
        "fixture_id": fixture_id,
        "fixture_family": record.get("fixture_family"),
        "execution_entry_mode": record.get("execution_entry_mode"),
        "player_count": len(player_ids),
        "player_ids": player_ids,
        "materialization_digest": record.get("materialization_digest"),
        "requested_state_digest": record.get("requested_state_digest"),
        "decision_entry_count": len(decisions),
        "decision_families": sorted({d["decision_family"] for d in decisions}),
        "decision_selector_kinds": sorted({d["selector_kind"] for d in decisions}),
        "decision_actors": sorted({d["actor"] for d in decisions}),
        "decisions": decisions,
        "native_procedure_operations": ops,
        "native_procedure_step_count": len(ops),
        "expected_required_events": list(expected.get("required_events") or []),
        "expected_forbidden_events": list(expected.get("forbidden_events") or []),
        "expected_ordering_constraints": list(expected.get("ordering_constraints") or []),
        "expected_partial_order_constraints": list(expected.get("partial_order_constraints") or []),
        "terminal_postconditions": list(terminals),
        "rules_channels": list(rng.get("channels") or []),
        "predetermined_semantic_draws": list(rng.get("predetermined_semantic_draws") or []),
        "knowledge_viewers": viewers,
        "behavior_status": "UNKNOWN_NOT_RUN",
        "behavior_credit_granted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    contract = load_contract(args.contract)
    records = provider_records(contract)

    family_counts = Counter(r["fixture_family"] for r in records)
    check(dict(family_counts) == EXPECTED_FAMILIES, "FAMILY_COUNTS_MISMATCH", dict(family_counts))
    entry_counts = Counter(r["execution_entry_mode"] for r in records)
    check(
        dict(entry_counts) == EXPECTED_ENTRY_MODES, "ENTRY_MODE_COUNTS_MISMATCH", dict(entry_counts)
    )
    natural_ids = [
        r["fixture_id"] for r in records if r["execution_entry_mode"] == "NATURAL_GAME_START"
    ]
    check(
        natural_ids == EXPECTED_NATURAL_START_FIXTURES,
        "NATURAL_START_IDENTITY_MISMATCH",
        natural_ids,
    )
    check(
        len({r["fixture_id"] for r in records}) == 107, "FIXTURE_IDS_NOT_UNIQUE_107", len(records)
    )

    rows = [inventory_record(ordinal, record) for ordinal, record in enumerate(records, 1)]

    decision_family_totals: Counter[str] = Counter()
    selector_totals: Counter[str] = Counter()
    operation_totals: Counter[str] = Counter()
    for row in rows:
        for d in row["decisions"]:
            decision_family_totals[d["decision_family"]] += 1
            selector_totals[d["selector_kind"]] += 1
        for op in row["native_procedure_operations"]:
            operation_totals[op] += 1

    output = {
        "artifact_version": "commander-lab.ws49-behavior-inventory/1.0.0",
        "derivation": "immutable 135-record v1.0.5 materialization filtered to the 107-record provider denominator; per-record behavior obligations transcribed, never executed",
        "contract": {
            "version": CONTRACT_VERSION,
            "commit": FREEZE_COMMIT,
            "tree": FREEZE_TREE,
            "namespace_tree": NAMESPACE_TREE,
            "materialization_sha256": MATERIALIZATION_FILE_SHA256,
            "canonical_bundle_digest": CANONICAL_MATERIALIZATION_DIGEST,
            "record_count": len(contract["records"]),
        },
        "provider_denominator": 107,
        "unique_fixture_ids": 107,
        "family_counts": dict(sorted(family_counts.items())),
        "entry_mode_counts": dict(sorted(entry_counts.items())),
        "natural_start_fixture_ids": natural_ids,
        "decision_family_totals": dict(sorted(decision_family_totals.items())),
        "decision_selector_kind_totals": dict(sorted(selector_totals.items())),
        "native_operation_totals": dict(sorted(operation_totals.items())),
        "historical_successor_runtime_credit_imported": 0,
        "behavior_credit_granted": False,
        "records": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "provider_denominator": 107,
                "family_counts": output["family_counts"],
                "entry_mode_counts": output["entry_mode_counts"],
                "decision_family_totals": output["decision_family_totals"],
                "decision_selector_kind_totals": output["decision_selector_kind_totals"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
