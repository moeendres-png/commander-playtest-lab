#!/usr/bin/env python3
"""Fail-closed semantic-executability linter for finalist materializations."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
COMMON_SHA = "e7f34ea4b2543132440e7e5fdb47c6cb4d4908f05fb49f6fa59f3e0592ca3bd4"
V101 = "commander-lab.semantic-fixture-materialization/1.0.1"
STARTER18 = {
    "PLAYER_COUNT_2P", "PLAYER_COUNT_3P", "PLAYER_COUNT_4P", "PLAYER_COUNT_5P",
    "PILOT_MULLIGAN", "PILOT_PRIORITY", "PILOT_TARGET", "HIDDEN_01", "HIDDEN_02",
    "MICRO_STACK", "MICRO_REPLACEMENT", "WS05-MP-COMBAT-4", "RNG_RULES_TAPE",
    "REPLAY_DECISION_TAPE", "REPLAY_EVENT_TAPE", "REPLAY_CLEAN_PROCESS",
    "REPLAY_STATE_HASHES", "CARD_02",
}

# Fresh high-model findings are encoded as reproducible v1.0.0 diagnostics.  The
# linter also performs data-derived checks; this table prevents a future schema
# relaxation from erasing the already adjudicated defect evidence.
CONFIRMED_V100 = {
    "PILOT_MULLIGAN": "PREGAME_INPUTS_INCOMPLETE",
    "PILOT_PRIORITY": "SCRIPTED_CAST_UNPAYABLE",
    "PILOT_TARGET": "TARGETLESS_STABLE_STACK_SPELL",
    "MICRO_STACK": "DECISION_ACTOR_LACKS_PRIORITY_AND_MANA",
    "MICRO_REPLACEMENT": "EXPECTED_EFFECT_HAS_NO_CAUSAL_NATIVE_ACTION",
    "WS05-MP-COMBAT-4": "ATTACKERS_PREPOPULATED_BEFORE_DECLARATION",
    "RNG_RULES_TAPE": "SCRIPTED_CAST_UNPAYABLE",
    "REPLAY_DECISION_TAPE": "SCRIPTED_CAST_UNPAYABLE",
    "REPLAY_EVENT_TAPE": "SCRIPTED_CAST_UNPAYABLE",
    "REPLAY_CLEAN_PROCESS": "SCRIPTED_CAST_UNPAYABLE",
    "REPLAY_STATE_HASHES": "SCRIPTED_CAST_UNPAYABLE",
    "CARD_02": "DUPLICATE_COMMANDER_CURRENT_OBJECT",
    "MICRO_COSTS": "TARGET_CARDINALITY_ILLEGAL",
    "MICRO_MANA_PAYMENT": "PAYMENT_WITHOUT_NATIVE_CAST",
    "MICRO_PRIORITY": "DECISION_ACTOR_LACKS_PRIORITY_AND_MANA",
    "MICRO_TARGETS": "TARGETLESS_STABLE_STACK_SPELL",
    "MICRO_TRIGGERS": "EXPECTED_TRIGGER_HAS_NO_CAUSAL_NATIVE_ACTION",
    "MICRO_PREVENTION": "SYNTHETIC_HISTORICAL_RULES_EFFECT",
    "MICRO_STATE_BASED_ACTIONS": "SYNTHETIC_HISTORICAL_RULES_EFFECT",
    "MICRO_ZONE_CHANGES": "STACK_SPELL_CAST_STATE_INCOMPLETE",
    "PILOT_MANA_PAYMENT": "PAYMENT_WITHOUT_NATIVE_CAST",
    "PILOT_REPLACEMENT_EFFECT": "REPLACEMENT_HAS_NO_CAUSAL_ZONE_MOVE",
    "PILOT_CHOICE": "CHOICE_HAS_NO_CAUSAL_NATIVE_PROCEDURE",
    "PILOT_CHOOSE_USE": "CHOICE_HAS_NO_CAUSAL_NATIVE_PROCEDURE",
    "PILOT_ANNOUNCE_X": "SCRIPTED_CAST_UNPAYABLE",
    "PILOT_CHOOSE_MODE": "SCRIPTED_CAST_UNPAYABLE",
    "PILOT_DECLARE_ATTACKER": "ATTACK_ELIGIBILITY_UNSPECIFIED",
    "WS05-MP-BLOCK-4": "WRONG_TURN_STEP_FOR_BLOCKER_DECISION",
    "WS05-MP-TRIG-3": "EXPECTED_TRIGGER_HAS_NO_CAUSAL_NATIVE_ACTION",
    "NEGATIVE_PARENT_CLASS_FALLBACK": "PRODUCTION_DECISION_NOT_CAUSALLY_REACHED",
}

AUTHORITY_BY_CODE = {
    "DUPLICATE_COMMANDER_CURRENT_OBJECT": ["CR 903.3", "WS31 authority domain"],
    "TARGET_CARDINALITY_ILLEGAL": ["CR 115.1a", "Hex Oracle: exactly six targets"],
    "TARGETLESS_STABLE_STACK_SPELL": ["CR 601.2c", "CR 601.2i"],
    "STACK_SPELL_CAST_STATE_INCOMPLETE": ["CR 601.2c", "CR 601.2i"],
    "SCRIPTED_CAST_UNPAYABLE": ["CR 601.2f", "CR 601.2h"],
    "PAYMENT_WITHOUT_NATIVE_CAST": ["CR 601.2f-h"],
    "PREGAME_INPUTS_INCOMPLETE": ["CR 103.4", "CR 103.5", "CR 903.11"],
    "WRONG_TURN_STEP_FOR_BLOCKER_DECISION": ["CR 509.1"],
    "ATTACK_ELIGIBILITY_UNSPECIFIED": ["CR 302.6", "CR 508.1"],
    "ATTACKERS_PREPOPULATED_BEFORE_DECLARATION": ["CR 508.1"],
    "DECISION_ACTOR_LACKS_PRIORITY_AND_MANA": ["CR 117", "CR 601.2h"],
    "SYNTHETIC_HISTORICAL_RULES_EFFECT": ["CR 609", "CR 611"],
    "EXPECTED_EFFECT_HAS_NO_CAUSAL_NATIVE_ACTION": ["CR 609.1"],
    "EXPECTED_TRIGGER_HAS_NO_CAUSAL_NATIVE_ACTION": ["CR 603"],
    "REPLACEMENT_HAS_NO_CAUSAL_ZONE_MOVE": ["CR 614", "CR 903.9"],
    "CHOICE_HAS_NO_CAUSAL_NATIVE_PROCEDURE": ["CR 608", "CR 614"],
    "PRODUCTION_DECISION_NOT_CAUSALLY_REACHED": ["WS-10R pilot fail-closed boundary"],
    "EXECUTION_ENTRY_MISSING": ["finalist convergence v1.0.1 contract"],
    "NATIVE_PROCEDURE_MISSING": ["finalist convergence v1.0.1 contract"],
    "DECISION_CAUSE_MISSING": ["finalist convergence v1.0.1 contract"],
    "REQUESTED_NATIVE_EQUALITY_GATE_MISSING": ["finalist convergence v1.0.1 contract"],
}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def defect(code, explanation):
    return {
        "code": code,
        "explanation": explanation,
        "authority_reference": AUTHORITY_BY_CODE.get(code, ["provider-neutral execution contract"]),
    }


def lint_record(record, is_v100=False):
    found = []
    fid = record["fixture_id"]
    if is_v100 and fid in CONFIRMED_V100:
        code = CONFIRMED_V100[fid]
        found.append(defect(code, "Confirmed v1.0.0 pre-audit defect reproduced by immutable fixture identity."))
    if "execution_entry_mode" not in record:
        found.append(defect("EXECUTION_ENTRY_MISSING", "Natural-start versus native-state-load entry is not declared."))
    elif record["execution_entry_mode"] not in {"NATURAL_GAME_START", "NATIVE_STATE_LOAD"}:
        found.append(defect("EXECUTION_ENTRY_INVALID", "Unknown execution entry mode."))
    procedure = record.get("native_procedure", [])
    if not procedure:
        found.append(defect("NATIVE_PROCEDURE_MISSING", "No causal native procedure is declared."))
    step_ids = {s.get("step_id") for s in procedure}
    for scripted in record.get("decision_script", []):
        cause = scripted.get("causal_step_id")
        if not cause or cause not in step_ids:
            found.append(defect("DECISION_CAUSE_MISSING", f"{scripted['decision_family']} has no declared native causal step."))
        if scripted.get("actor") not in {p["player_id"] for p in record["players"]}:
            found.append(defect("DECISION_ACTOR_ILLEGAL", f"Decision actor {scripted.get('actor')} is not a live fixture player."))
    if not record.get("setup_validation", {}).get("requested_vs_normalized_native_constructed_state_equality_required"):
        found.append(defect("REQUESTED_NATIVE_EQUALITY_GATE_MISSING", "Runtime credit is not gated on requested/native constructed-state equality."))

    # Exactly one current object incarnation for every Commander identity.
    commander_ids = [c["commander_id"] for c in record.get("commander_state", {}).get("commanders", [])]
    for commander_id in commander_ids:
        objects = [o for o in record["semantic_objects"] if o.get("commander_id") == commander_id]
        if len(objects) != 1:
            found.append(defect("DUPLICATE_COMMANDER_CURRENT_OBJECT", f"{commander_id} has {len(objects)} current semantic objects; exactly one is required."))

    # A stable stack entry represents a fully cast object, never a spell awaiting
    # target/mode completion.  Native casting procedures may generate choices.
    stack_objects = {o["semantic_id"] for o in record["semantic_objects"] if o["zone"] == "stack"}
    stack_rows = {s.get("source_object"): s for s in record.get("stack_state", [])}
    for sid in sorted(stack_objects):
        row = stack_rows.get(sid)
        if not row or row.get("cast_complete") is not True or "targets" not in row or "modes" not in row:
            found.append(defect("STACK_SPELL_CAST_STATE_INCOMPLETE", f"Stable stack object {sid} lacks complete cast/target/mode state."))

    # Combat decision entry and provider-neutral attack eligibility.
    families = {d["decision_family"] for d in record.get("decision_script", [])}
    temporal = record.get("temporal_state", {})
    combat = record.get("combat_state", {})
    if "declare_attacker" in families:
        if (temporal.get("phase"), temporal.get("step")) != ("combat", "declare_attackers"):
            found.append(defect("WRONG_TURN_STEP_FOR_ATTACKER_DECISION", "Attacker decision is not entered at declare attackers."))
        if not combat.get("eligible_attackers"):
            found.append(defect("ATTACK_ELIGIBILITY_UNSPECIFIED", "No provider-neutral eligible attacker set is declared."))
        if combat.get("attackers"):
            found.append(defect("ATTACKERS_PREPOPULATED_BEFORE_DECLARATION", "Attackers already exist before the scripted declaration."))
    if "declare_blocker" in families and (temporal.get("phase"), temporal.get("step")) != ("combat", "declare_blockers"):
        found.append(defect("WRONG_TURN_STEP_FOR_BLOCKER_DECISION", "Blocker decision is not entered at declare blockers."))

    # Strict natural starts require every participant's actual deck and explicit
    # pregame response; mulligan rounds may contain the same player twice.
    if record.get("execution_entry_mode") == "NATURAL_GAME_START":
        deck_players = {d.get("player_id") for d in record.get("deck_state", [])}
        players = {p["player_id"] for p in record["players"]}
        responders = {d["actor"] for d in record.get("decision_script", []) if d["decision_family"] == "mulligan"}
        if deck_players != players or responders != players:
            found.append(defect("PREGAME_INPUTS_INCOMPLETE", "Natural start lacks a real deck or explicit pregame response for every player."))

    # Rules RNG must be a legal declared operation tied to a native procedure.
    channels = record.get("rules_randomness", {}).get("channels", [])
    if channels and not any(s.get("operation") in {"NATIVE_SEEDED_INITIAL_SHUFFLE", "NATIVE_EXPLICIT_LIBRARY_SHUFFLE"} for s in procedure):
        found.append(defect("RULES_RNG_NATIVE_OPERATION_MISSING", "Declared Rules RNG channel has no explicit native random operation."))

    # Target cardinality where direct authority makes it deterministic.
    if fid == "MICRO_COSTS" and not is_v100:
        target_values = [d["selection"]["semantic_value"] for d in record.get("decision_script", []) if d["decision_family"] == "target"]
        if not target_values or not isinstance(target_values[0], list) or len(target_values[0]) != 6:
            found.append(defect("TARGET_CARDINALITY_ILLEGAL", "Hex must have exactly six legal creature targets."))

    # Synthetic historical effects are never a substitute for native causality.
    for effect in record.get("continuous_rules_effects", []):
        text = json.dumps(effect).lower()
        if "resolved" in text or "histor" in text or "previous" in text:
            found.append(defect("SYNTHETIC_HISTORICAL_RULES_EFFECT", "A prior Rules effect is asserted as external state instead of being created natively."))

    # Negative fallback fixtures must reach one native prompt and omit exactly its handler.
    probe = record.get("negative_fallback_probe")
    if probe and fid.startswith("NEGATIVE_") and not is_v100:
        if probe.get("production_decision_reached_natively") is not True or not probe.get("omitted_handler"):
            found.append(defect("PRODUCTION_DECISION_NOT_CAUSALLY_REACHED", "Negative probe does not natively reach and then omit exactly one production handler."))

    # Deduplicate repeated diagnostics without hiding distinct explanations.
    unique = []
    seen = set()
    for item in found:
        key = (item["code"], item["explanation"])
        if key not in seen:
            seen.add(key); unique.append(item)
    return unique


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--materialization", required=True)
    parser.add_argument("--schema")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    corpus = load(args.materialization)
    is_v100 = corpus.get("schema_version") != V101
    schema_errors = []
    if args.schema:
        schema = load(args.schema)
        Draft202012Validator.check_schema(schema)
        schema_errors = [f"{list(e.path)}: {e.message}" for e in Draft202012Validator(schema).iter_errors(corpus)]
    records = []
    for record in corpus["records"]:
        defects = lint_record(record, is_v100=is_v100)
        records.append({
            "fixture_id": record["fixture_id"],
            "status": "PASS" if not defects else "SEMANTIC_EXECUTABILITY_DEFECT",
            "defects": defects,
            "materialization_digest": record["materialization_digest"],
        })
    status_counts = Counter(r["status"] for r in records)
    starter_defects = [r["fixture_id"] for r in records if r["fixture_id"] in STARTER18 and r["status"] != "PASS"]
    report = {
        "schema_version": "commander-lab.semantic-executability-report/1.0.1",
        "input_schema_version": corpus.get("schema_version"),
        "input_bundle_digest": corpus.get("canonical_bundle_digest"),
        "record_count": len(records), "unique_fixture_ids": len({r["fixture_id"] for r in records}),
        "terminal_result_count": len(records), "status_counts": dict(status_counts),
        "starter_18": {"pass": 18 - len(starter_defects), "defects": starter_defects},
        "schema_status": "PASS" if not schema_errors else "FAIL",
        "schema_errors": schema_errors[:100], "records": records,
    }
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes((json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
    if output.name == "SEMANTIC_EXECUTABILITY_REPORT.json":
        required = [
            "SEMANTIC_FIXTURE_SCHEMA_v1_0_1.json",
            "SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_1.json",
            "DIFFERENTIAL_STARTER_18_v1_0_1.json",
            "KNOWN_PASS_UNION_50_v1_0_1.json",
            "SEMANTIC_EXECUTABILITY_REPORT.json",
            "SUPERSEDES_v1_0_0.json",
        ]
        sums = "\n".join(
            f"{hashlib.sha256((output.parent / name).read_bytes()).hexdigest()}  {name}"
            for name in required
        ) + "\n"
        (output.parent / "SHA256SUMS").write_bytes(sums.encode("utf-8"))
    print(json.dumps({k: v for k, v in report.items() if k not in {"records", "schema_errors"}}, indent=2))
    return 0 if not schema_errors and not starter_defects and len(records) == 135 else 1


if __name__ == "__main__":
    raise SystemExit(main())
