#!/usr/bin/env python3
"""Fail-closed semantic-executability linter for WS-32 materialization v1.0.2."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

VERSION = "commander-lab.semantic-fixture-materialization/1.0.2"
DIGEST_SPEC = "commander-lab.requested-state-digest/1.0.0"
STATE_KEYS = (
    "execution_entry_mode", "players", "deck_state", "commander_state",
    "semantic_objects", "temporal_state", "knowledge_state", "rules_randomness",
    "combat_state", "stack_state", "continuous_rules_effects", "extra_turn_creation",
    "elimination_trigger", "zone_move_event", "setup_validation",
)
OBLIGATION_KEYS = (
    "fixture_id", "fixture_family", "frozen_contract_binding", "card_authority_binding",
    "expected_events", "terminal_postconditions",
)
TARGET_ONE = {
    "Lightning Bolt", "Doom Blade", "Swords to Plowshares", "Unsummon",
    "Bant Charm", "Flare of Duplication", "Wash Away", "Bolt Bend",
    "Makeshift Mannequin",
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def requested_state_projection(record: dict[str, Any]) -> dict[str, Any]:
    return {key: copy.deepcopy(record[key]) for key in STATE_KEYS if key in record}


def requested_state_digest(record: dict[str, Any]) -> str:
    return sha256_json(requested_state_projection(record))


def obligation_projection(record: dict[str, Any]) -> dict[str, Any]:
    return {key: copy.deepcopy(record.get(key)) for key in OBLIGATION_KEYS}


def obligation_digest(record: dict[str, Any]) -> str:
    return sha256_json(obligation_projection(record))


def _objects(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {obj["semantic_id"]: obj for obj in record.get("semantic_objects", [])}


def _stack_rows(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row.get("source_semantic_id"): row for row in record.get("stack_state", []) if row.get("source_semantic_id")}


def _selected_attackers(record: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for dec in record.get("decision_script", []):
        if dec.get("decision_family") != "declare_attacker":
            continue
        value = dec.get("selection", {}).get("semantic_value")
        if isinstance(value, dict):
            result.update(k for k in value if isinstance(k, str) and k.startswith("obj:"))
    return result


def _is_cast_decision(decision: dict[str, Any]) -> bool:
    if decision.get("decision_family") != "priority":
        return False
    value = decision.get("selection", {}).get("semantic_value")
    if not isinstance(value, dict):
        return False
    action = str(value.get("action", ""))
    return action.startswith("cast") or action == "announce_cast"


def lint_record(record: dict[str, Any], predecessor: dict[str, Any] | None = None) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    fid = record.get("fixture_id", "<missing>")

    def err(code: str, message: str) -> None:
        errors.append({"code": code, "message": message})

    if record.get("materialization_version") != VERSION:
        err("VERSION", f"{fid}: materialization_version is not {VERSION}")
    if record.get("execution_entry_mode") not in {"NATURAL_GAME_START", "NATIVE_STATE_LOAD"}:
        err("EXECUTION_ENTRYPOINT", f"{fid}: execution entry mode is absent or invalid")
    if record.get("semantic_executability") != "SEMANTIC_EXECUTABLE":
        err("TERMINAL_EXECUTABILITY", f"{fid}: record is not terminally SEMANTIC_EXECUTABLE")

    objects = _objects(record)
    commander_occurrences: dict[str, list[str]] = {}
    for obj in record.get("semantic_objects", []):
        cid = obj.get("commander_id")
        if cid:
            commander_occurrences.setdefault(cid, []).append(obj["semantic_id"])
    for cid, ids in commander_occurrences.items():
        if len(ids) > 1:
            err("COMMANDER_CURRENT_INCARNATION_UNIQUENESS", f"{fid}: {cid} has multiple current objects {ids}")

    procedures = record.get("native_procedure", [])
    step_ids = {step.get("step_id") for step in procedures if step.get("step_id")}
    if not procedures:
        err("NATIVE_CAUSAL_PATH", f"{fid}: native_procedure is empty")
    meaningful_native = [
        step for step in procedures
        if str(step.get("operation", "")).startswith("NATIVE_")
        and step.get("operation") != "NATIVE_CONSTRUCT_AND_VALIDATE_REQUESTED_STATE"
    ]
    required_events = record.get("expected_events", {}).get("required_events", [])
    if required_events and not meaningful_native:
        err("EXPECTED_EVENT_CAUSALITY", f"{fid}: required events have no native causal operation")

    for index, dec in enumerate(record.get("decision_script", [])):
        cause = dec.get("causal_step_id")
        if not cause or cause == "UNSPECIFIED_NATIVE_CAUSE" or cause not in step_ids:
            err("NATIVE_DECISION_CAUSALITY", f"{fid}: decision {index} has no valid native causal step")
            continue
        step = next((s for s in procedures if s.get("step_id") == cause), {})
        if not str(step.get("operation", "")).startswith("NATIVE_"):
            err("NATIVE_DECISION_CAUSALITY", f"{fid}: decision {index} cause {cause} is not native")
        actor = step.get("details", {}).get("actor")
        if actor and actor != dec.get("actor"):
            err("LEGAL_CURRENT_ACTOR", f"{fid}: decision {index} actor {dec.get('actor')} != causal actor {actor}")

    cost_rows = {row.get("decision_index"): row for row in record.get("action_cost_state", [])}
    for index, dec in enumerate(record.get("decision_script", [])):
        if _is_cast_decision(dec):
            row = cost_rows.get(index)
            if not row or row.get("payable") is not True:
                err("PAYABLE_SCRIPTED_CAST", f"{fid}: cast decision {index} lacks explicit payable evidence")

    stack_rows = _stack_rows(record)
    for sid, obj in objects.items():
        if obj.get("zone") != "stack":
            continue
        row = stack_rows.get(sid)
        if not row:
            err("COMPLETE_FULLY_CAST_STACK", f"{fid}: stack object {sid} has no stack_state row")
            continue
        if row.get("cast_complete") is not True or row.get("costs_paid") is not True:
            err("COMPLETE_FULLY_CAST_STACK", f"{fid}: stack object {sid} is not explicitly fully cast/paid")
        if "targets" not in row or "modes" not in row:
            err("COMPLETE_FULLY_CAST_STACK", f"{fid}: stack object {sid} omits targets or modes")
        if obj.get("card_identity") in TARGET_ONE and len(row.get("targets", [])) != 1:
            err("TARGET_CARDINALITY", f"{fid}: {obj.get('card_identity')} stack object {sid} requires exactly one target")

    temporal = record.get("temporal_state", {})
    for key in ("active_player", "priority_player", "phase", "step", "turn_number"):
        if key not in temporal:
            err("NO_HIDDEN_DEFAULTS", f"{fid}: temporal_state omits {key}")

    attackers = _selected_attackers(record)
    if attackers:
        preapplied = set(record.get("combat_state", {}).get("attackers", {}))
        if attackers & preapplied:
            err("TURN_BASED_ACTION_PREAPPLIED", f"{fid}: attacker declaration is already present in initial combat state")
        for sid in attackers:
            obj = objects.get(sid)
            if not obj or obj.get("controlled_since_turn_began") is not True:
                err("ATTACK_ELIGIBILITY", f"{fid}: attacker {sid} lacks controlled_since_turn_began=true")
        first = next(i for i, d in enumerate(record.get("decision_script", [])) if d.get("decision_family") == "declare_attacker")
        if first == 0 and temporal.get("step") != "declare_attackers":
            err("TURN_BASED_ACTION_ENTRY", f"{fid}: initial attacker decision does not enter declare_attackers")

    blocker_indices = [i for i, d in enumerate(record.get("decision_script", [])) if d.get("decision_family") == "declare_blocker"]
    if blocker_indices and blocker_indices[0] == 0 and temporal.get("step") != "declare_blockers":
        err("TURN_BASED_ACTION_ENTRY", f"{fid}: initial blocker decision does not enter declare_blockers")

    if temporal.get("phase") == "pregame" or temporal.get("step") == "mulligan":
        if record.get("execution_entry_mode") != "NATURAL_GAME_START":
            err("STRICT_PREGAME_ENTRY", f"{fid}: pregame/mulligan record is not NATURAL_GAME_START")
        decks = record.get("deck_state", [])
        players = record.get("players", [])
        if len(decks) != len(players) or not players:
            err("STRICT_PREGAME_COMPLETE", f"{fid}: deck_state does not cover every player")
        plan = record.get("pregame_decision_plan", [])
        if not plan or not all(p.get("player_id") and p.get("decision") for p in plan):
            err("STRICT_PREGAME_COMPLETE", f"{fid}: complete external mulligan/keep plan is absent")

    if record.get("fixture_family") == "replay_rng":
        rng = record.get("rules_randomness", {})
        if not rng.get("channels") or rng.get("pilot_randomness_prohibited") is not True:
            err("REPLAY_RNG_CAUSALITY", f"{fid}: Rules RNG contract is incomplete")
        if not any("SHUFFLE" in str(step.get("operation", "")) or "RNG" in str(step.get("operation", "")) for step in procedures):
            err("REPLAY_RNG_CAUSALITY", f"{fid}: replay record has no native RNG/shuffle transaction")
        if not record.get("replay_contract"):
            err("REPLAY_RNG_CAUSALITY", f"{fid}: replay_contract is absent")

    for effect in record.get("continuous_rules_effects", []):
        text = json.dumps(effect, ensure_ascii=False).lower()
        if any(token in text for token in ("resolved earlier", "historical spell", "synthetic historical")):
            err("NO_SYNTHETIC_HISTORICAL_RULE_EFFECT", f"{fid}: synthetic historical rules effect detected")

    cv = record.get("construction_validation", {})
    if cv.get("required") is not True or cv.get("digest_spec") != DIGEST_SPEC:
        err("CONSTRUCTION_VALIDATION", f"{fid}: construction validation is not mandatory under {DIGEST_SPEC}")
    if cv.get("credit_condition") != "REQUESTED_STATE_DIGEST_EQUALS_CONSTRUCTED_STATE_DIGEST":
        err("CONSTRUCTION_VALIDATION", f"{fid}: requested/constructed digest equality is not the credit gate")
    if record.get("requested_state_digest") != requested_state_digest(record):
        err("REQUESTED_STATE_DIGEST", f"{fid}: requested_state_digest mismatch")
    if record.get("obligation_digest") != obligation_digest(record):
        err("OBLIGATION_DIGEST", f"{fid}: stored obligation digest mismatch")
    if predecessor is not None and obligation_projection(record) != obligation_projection(predecessor):
        err("OBLIGATION_DRIFT", f"{fid}: frozen obligation projection changed from v1.0.1")
    return errors


def lint_bundle(bundle: dict[str, Any], predecessor_bundle: dict[str, Any] | None = None) -> dict[str, Any]:
    records = bundle.get("records", [])
    predecessor_by_id = {r["fixture_id"]: r for r in (predecessor_bundle or {}).get("records", [])}
    rows = []
    seen: set[str] = set()
    duplicate_ids: list[str] = []
    for record in records:
        fid = record.get("fixture_id", "<missing>")
        if fid in seen:
            duplicate_ids.append(fid)
        seen.add(fid)
        errors = lint_record(record, predecessor_by_id.get(fid))
        rows.append({"fixture_id": fid, "status": "PASS" if not errors else "CONTRACT_DEFECT", "errors": errors})

    global_errors: list[dict[str, str]] = []
    if bundle.get("schema_version") != VERSION:
        global_errors.append({"code": "SCHEMA_VERSION", "message": f"schema_version != {VERSION}"})
    if bundle.get("record_count") != 135 or len(records) != 135:
        global_errors.append({"code": "COMPLETE_ACCOUNTING", "message": f"expected 135 records, got declared={bundle.get('record_count')} actual={len(records)}"})
    if duplicate_ids:
        global_errors.append({"code": "COMPLETE_ACCOUNTING", "message": f"duplicate fixture IDs: {sorted(set(duplicate_ids))}"})
    if predecessor_bundle is not None:
        predecessor_ids = {r["fixture_id"] for r in predecessor_bundle.get("records", [])}
        if seen != predecessor_ids:
            global_errors.append({"code": "IMMUTABLE_PROVENANCE", "message": "successor fixture ID set differs from v1.0.1"})

    passed = sum(row["status"] == "PASS" for row in rows)
    defects = len(rows) - passed
    return {
        "report_version": "commander-lab.semantic-executability-report/1.0.2",
        "materialization_version": VERSION,
        "record_count": len(rows),
        "semantic_executable_count": passed,
        "contract_defect_count": defects,
        "global_errors": global_errors,
        "records": rows,
        "terminal_status": "PASS" if passed == 135 and not global_errors else "FAIL",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("materialization", type=Path)
    parser.add_argument("--predecessor", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    bundle = json.loads(args.materialization.read_text(encoding="utf-8"))
    predecessor = json.loads(args.predecessor.read_text(encoding="utf-8")) if args.predecessor else None
    report = lint_bundle(bundle, predecessor)
    rendered = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if report["terminal_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
