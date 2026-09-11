#!/usr/bin/env python3
"""Build the immutable provider-neutral WS-32 semantic successor contract v1.0.2."""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from ws32_lint_semantic_v1_0_2 import (
    DIGEST_SPEC,
    VERSION,
    canonical_bytes,
    lint_bundle,
    obligation_digest,
    requested_state_digest,
)

ROOT = Path(__file__).resolve().parents[1]
OLD_DIR = ROOT / "qualification" / "finalist_convergence"
OUT = ROOT / "qualification" / "ws32"
OLD_MAT = OLD_DIR / "SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_1.json"
OLD_SCHEMA = OLD_DIR / "SEMANTIC_FIXTURE_SCHEMA_v1_0_1.json"
OLD_REPORT = OLD_DIR / "SEMANTIC_EXECUTABILITY_REPORT.json"
OLD_COMMIT = "9a8b8f5f5961466514eae6103be2d227324a27a8"
OLD_TREE = "a9eee7458b9c39fd473ea54fdf58f5572cb46a1b"
OLD_BUNDLE = "ad1ec6e4baa83be48c0bc07e0bde66c2f8c003af29e411bad0953558154dcfee"
WS31_HEAD = "1bee87b9a0c4db90ecbf1f5374fae0732d6dd16e"
WS31_AUTHORITY = "d8337dc0a243fddbede3e9d2cec7b3938a1007970a23dea04855149fbfc55d5e"
CR_SHA256 = "9e2268a0ed58f229c5b974a3ae7986c5f91a5a052c4af1a9e672906a427c044c"
PROTOCOL = "commander-lab.rules-service/1.1.0"
REPLAY_IDS = {
    "RNG_RULES_TAPE", "REPLAY_DECISION_TAPE", "REPLAY_EVENT_TAPE",
    "REPLAY_CLEAN_PROCESS", "REPLAY_STATE_HASHES",
}
BURN_NEGATIVE = {"NEGATIVE_FIRST_OPTION", "NEGATIVE_GUI_DEFAULT"}
BOLT_NEGATIVE = {"NEGATIVE_RANDOM_OPTION", "NEGATIVE_SILENT_SKIP"}
ZONE_SOURCE_TARGETS = {
    "WS05-CMD-ZONE-GY-YES": ("obj:cmd-zone-source", "obj:cmd-zone-test", []),
    "WS05-CMD-ZONE-GY-NO": ("obj:cmd-zone-source", "obj:cmd-zone-test", []),
    "WS05-CMD-ZONE-EXILE-YES": ("obj:cmd-zone-source", "obj:cmd-zone-test", []),
    "WS05-CMD-ZONE-EXILE-NO": ("obj:cmd-zone-source", "obj:cmd-zone-test", []),
    "WS05-CMD-ZONE-HAND-YES": ("obj:cmd-zone-source", "obj:cmd-zone-test", []),
    "WS05-CMD-ZONE-HAND-NO": ("obj:cmd-zone-source", "obj:cmd-zone-test", []),
    "WS05-CMD-ZONE-LIB-YES": ("obj:cmd-zone-source", "obj:cmd-zone-test", ["put_creature_on_bottom_of_owners_library"]),
    "WS05-CMD-ZONE-LIB-NO": ("obj:cmd-zone-source", "obj:cmd-zone-test", ["put_creature_on_bottom_of_owners_library"]),
}
STACK_TARGETS = {
    "PILOT_CHOOSE_OBJECT": {"obj:syphon": ["P1"]},
    "MICRO_COPY": {"obj:micro-flare": ["obj:micro-bolt"], "obj:micro-bolt": ["P2"]},
    "MICRO_RULES_RANDOMNESS": {"obj:micro-stitch": []},
    "PILOT_PILE": {"obj:fof": []},
    "CARD_07": {"obj:card07-draw": []},
    "CARD_10": {"obj:card10-p2cmd": []},
    "CARD_13": {"obj:card13-bolt": ["P1"]},
    "CARD_16": {"obj:card16-divination": []},
    "CARD_20": {"obj:card_20-subject": []},
    "CARD_22": {"obj:card22-bolt": ["P1"]},
    "WS05-MP-PRIO-3": {"obj:mp-bolt": ["obj:P3-bears"]},
    "WS05-MP-PRIO-5": {"obj:mp-bolt": ["obj:P5-bears"]},
    "WS05-MP-ELIM-STACK-3": {"obj:leave-bolt": ["P1"]},
}
MINIMUM_MANA = {
    "Lightning Bolt": 1,
    "Burn Down the House": 5,
    "Magma Opus": 8,
    "Jeska, Thrice Reborn": 3,
    "Wash Away": 1,
    "Wear // Tear": 3,
    "Dig Through Time": 2,
    "Vandalblast": 5,
    "Finale of Revelation": 12,
    "Wrath of God": 4,
    "Shriekmaw": 2,
    "Bolt Bend": 1,
    "Makeshift Mannequin": 4,
    "Grizzly Bears": 2,
    "Keldon Marauders": 2,
    "Find // Finality": 6,
    "Boseiju Reaches Skyward // Branch of Boseiju": 4,
    "Rograkh, Son of Rohgahh": 0,
}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value) + b"\n")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def player_id(player: dict[str, Any]) -> str | None:
    for key in ("player_id", "semantic_player_id", "id", "player"):
        if player.get(key):
            return str(player[key])
    return None


def object_map(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {o["semantic_id"]: o for o in record.get("semantic_objects", [])}


def add_object(record: dict[str, Any], sid: str, card: str, owner: str, zone: str, **extra: Any) -> dict[str, Any]:
    existing = object_map(record).get(sid)
    if existing:
        existing.update(extra)
        return existing
    obj = {
        "semantic_id": sid,
        "card_identity": card,
        "card_lineage_id": f"line:{sid}",
        "owner": owner,
        "controller": owner,
        "zone": zone,
        "tapped": False,
        "face_down": False,
        "counters": {},
    }
    obj.update(extra)
    record.setdefault("semantic_objects", []).append(obj)
    return obj


def add_basics(record: dict[str, Any], actor: str, card: str, count: int, prefix: str) -> list[str]:
    ids = []
    for i in range(count):
        sid = f"obj:{prefix}-{i}"
        add_object(record, sid, card, actor, "battlefield")
        ids.append(sid)
    return ids


def move_object(record: dict[str, Any], sid: str, zone: str) -> None:
    obj = object_map(record).get(sid)
    if not obj:
        raise ValueError(f"{record['fixture_id']}: missing object {sid}")
    obj["zone"] = zone
    record["stack_state"] = [r for r in record.get("stack_state", []) if r.get("source_semantic_id") != sid]


def set_player_life(record: dict[str, Any], pid: str, life: int) -> None:
    for p in record.get("players", []):
        if player_id(p) == pid:
            p["life"] = life
            return
    raise ValueError(f"{record['fixture_id']}: player {pid} not found")


def set_temporal(record: dict[str, Any], *, active: str | None = None, priority: str | None = None, phase: str | None = None, step: str | None = None) -> None:
    t = record.setdefault("temporal_state", {})
    if active is not None:
        t["active_player"] = active
    if priority is not None:
        t["priority_player"] = priority
    if phase is not None:
        t["phase"] = phase
    if step is not None:
        t["step"] = step


def mark_attackers_eligible(record: dict[str, Any]) -> None:
    objs = object_map(record)
    for dec in record.get("decision_script", []):
        if dec.get("decision_family") != "declare_attacker":
            continue
        value = dec.get("selection", {}).get("semantic_value")
        if isinstance(value, dict):
            for sid in value:
                if sid in objs:
                    objs[sid]["controlled_since_turn_began"] = True


def complete_stack(record: dict[str, Any]) -> None:
    fid = record["fixture_id"]
    rows_by_id = {r.get("source_semantic_id"): copy.deepcopy(r) for r in record.get("stack_state", []) if r.get("source_semantic_id")}
    overrides = copy.deepcopy(STACK_TARGETS.get(fid, {}))
    if fid in ZONE_SOURCE_TARGETS:
        sid, target, modes = ZONE_SOURCE_TARGETS[fid]
        overrides[sid] = [target]
    result = []
    for obj in record.get("semantic_objects", []):
        if obj.get("zone") != "stack":
            continue
        sid = obj["semantic_id"]
        row = rows_by_id.get(sid, {})
        row.update({
            "source_semantic_id": sid,
            "controller": obj.get("controller"),
            "cast_complete": True,
            "costs_paid": True,
            "targets": overrides.get(sid, row.get("targets", [])),
            "modes": row.get("modes", []),
        })
        if fid in ZONE_SOURCE_TARGETS and sid == ZONE_SOURCE_TARGETS[fid][0]:
            row["modes"] = ZONE_SOURCE_TARGETS[fid][2]
        result.append(row)
    record["stack_state"] = result


def causal_operation(record: dict[str, Any], index: int, decision: dict[str, Any]) -> str:
    family = decision.get("decision_family")
    if family == "priority":
        return "NATIVE_OFFER_PRIORITY_AND_EXECUTE_SELECTED_ACTION"
    if family == "declare_attacker":
        return "NATIVE_ENTER_DECLARE_ATTACKERS_AND_REQUEST_DECLARATION"
    if family == "declare_blocker":
        return "NATIVE_ENTER_DECLARE_BLOCKERS_AND_REQUEST_DECLARATION"
    if family == "mulligan":
        return "NATIVE_EXECUTE_MULLIGAN_ROUND_AND_REQUEST_DECISION"
    if family == "trigger_order":
        return "NATIVE_GENERATE_OR_REVEAL_ORDERABLE_OBJECTS_AND_REQUEST_ORDER"
    if family in {"replacement_effect", "choice"}:
        return "NATIVE_RESOLVE_ZONE_MOVE_AND_REQUEST_COMMANDER_ZONE_CHOICE"
    if family == "pile":
        return "NATIVE_RESOLVE_TOP_STACK_OBJECT_TO_PILE_DECISION"
    if family in {"target_amount", "multi_amount"}:
        return "NATIVE_CONTINUE_CAST_TO_DAMAGE_DISTRIBUTION_DECISION"
    if family == "choose_mode":
        return "NATIVE_BEGIN_OR_CONTINUE_CAST_TO_MODE_DECISION"
    if family == "target":
        return "NATIVE_BEGIN_OR_CONTINUE_RULES_PROCEDURE_TO_TARGET_DECISION"
    if family == "choose_object":
        return "NATIVE_RESOLVE_OR_CONTINUE_RULES_PROCEDURE_TO_OBJECT_DECISION"
    if family == "choose_ability":
        return "NATIVE_ENUMERATE_LEGAL_ACTIVATED_ABILITIES_AND_REQUEST_SELECTION"
    if family == "choose_use":
        return "NATIVE_RESOLVE_OR_CONTINUE_RULES_PROCEDURE_TO_OPTIONAL_DECISION"
    if family == "announce_x":
        return "NATIVE_BEGIN_CAST_TO_X_ANNOUNCEMENT"
    return "NATIVE_REACH_DECLARED_EXTERNAL_DECISION_FRAME"


def build_native_procedure(record: dict[str, Any], *, negative: bool = False, special_prelude: list[dict[str, Any]] | None = None) -> None:
    steps: list[dict[str, Any]] = [{
        "step_id": "load",
        "operation": "NATIVE_CONSTRUCT_AND_VALIDATE_REQUESTED_STATE",
        "details": {"requested_state_digest_required": True},
    }]
    steps.extend(copy.deepcopy(special_prelude or []))
    decisions = record.get("decision_script", [])
    for index, dec in enumerate(decisions):
        cause = f"cause-{index}"
        dec["causal_step_id"] = cause
        steps.append({
            "step_id": cause,
            "operation": causal_operation(record, index, dec),
            "details": {
                "actor": dec.get("actor"),
                "decision_family": dec.get("decision_family"),
                "cause_kind": "PROVIDER_NATIVE_RULES_TRANSACTION",
                "semantic_selection_contract": dec.get("selection"),
                "no_hidden_default": True,
            },
        })
        if negative:
            steps.append({
                "step_id": f"unsupported-{index}",
                "operation": "EXTERNAL_DECISION_HANDLER_INTENTIONALLY_UNAVAILABLE",
                "details": {"required_result": "UNSUPPORTED_DISCRETIONARY_DECISION_FAIL_CLOSED"},
            })
            break
        steps.append({
            "step_id": f"external-{index}",
            "operation": "EXTERNAL_SUBMIT_SELECTED_SEMANTIC_RESPONSE",
            "details": {"decision_index": index, "matches_only_provider_offered_legal_options": True},
        })
        steps.append({
            "step_id": f"advance-{index}",
            "operation": "NATIVE_CONTINUE_WITH_EXPLICIT_SCRIPTED_PRIORITY_PASSES_UNTIL_NEXT_DECLARED_DECISION",
            "details": {"priority_passes_are_scripted_not_fallbacks": True},
        })
    if not negative:
        steps.append({
            "step_id": "settle",
            "operation": "NATIVE_RESOLVE_OR_EVALUATE_DECLARED_RULES_CAUSE_TO_TERMINAL_CHECKPOINT",
            "details": {"automatic_rules_actions_engine_owned": True},
        })
    record["native_procedure"] = steps
    record["execution_transaction_policy"] = {
        "legal_actions": "RULES_CORE_ONLY",
        "automatic_rules_actions": "RULES_CORE_ONLY",
        "discretionary_choices": "ONLY_EXPLICIT_DECISION_SCRIPT_RESPONSES",
        "priority_passes": "EXPLICITLY_SCRIPTED_WHEN_NEEDED_TO_REACH_NEXT_DECLARED_CHECKPOINT",
        "fallbacks": "PROHIBITED",
    }


def repair_pregame(record: dict[str, Any], player_count: int) -> None:
    record["execution_entry_mode"] = "NATURAL_GAME_START"
    record["semantic_objects"] = []
    record["stack_state"] = []
    record.pop("combat_state", None)
    record["deck_state"] = [
        {
            "player_id": f"P{i}",
            "commander": [{"card_identity": "Rograkh, Son of Rohgahh", "count": 1}],
            "main_deck": [{"card_identity": "Mountain", "count": 99}],
            "exact_card_count": 100,
        }
        for i in range(1, player_count + 1)
    ]
    plan = [{"round": 1, "player_id": "P1", "decision": "MULLIGAN"}]
    plan.extend({"round": 1, "player_id": f"P{i}", "decision": "KEEP"} for i in range(2, player_count + 1))
    plan.append({"round": 2, "player_id": "P1", "decision": "KEEP"})
    record["pregame_decision_plan"] = plan
    record["rules_randomness"] = {
        "channels": ["INITIAL_LIBRARY_SHUFFLE"],
        "pilot_randomness_prohibited": True,
        "seed_binding": "SCENARIO_SEED",
    }
    set_temporal(record, active="P1", priority="P1", phase="pregame", step="mulligan")
    if record.get("decision_script"):
        record["decision_script"][0]["causal_step_id"] = "mulligan-round-1"
    record["native_procedure"] = [
        {"step_id": "natural-start", "operation": "NATIVE_CREATE_COMMANDER_GAME_FROM_DECKS", "details": {"player_count": player_count, "starting_life": 40}},
        {"step_id": "initial-shuffle", "operation": "NATIVE_RULES_RNG_INITIAL_LIBRARY_SHUFFLE_ALL_PLAYERS", "details": {"channel": "INITIAL_LIBRARY_SHUFFLE"}},
        {"step_id": "draw-opening", "operation": "NATIVE_DRAW_OPENING_HANDS", "details": {"cards_each": 7}},
        {"step_id": "mulligan-round-1", "operation": "NATIVE_EXECUTE_MULLIGAN_ROUND_AND_REQUEST_DECISION", "details": {"actor": "P1", "round": 1}},
        {"step_id": "responses-round-1", "operation": "EXTERNAL_SUBMIT_EXPLICIT_MULLIGAN_KEEP_RESPONSES", "details": {"plan": plan}},
        {"step_id": "mulligan-round-2", "operation": "NATIVE_EXECUTE_MULLIGAN_ROUND_AND_REQUEST_DECISION", "details": {"actor": "P1", "round": 2}},
        {"step_id": "finish-pregame", "operation": "NATIVE_COMPLETE_LONDON_MULLIGAN_BOTTOMING", "details": {"expected_bottom_count": 1 if player_count == 2 else 0}},
    ]
    record["execution_transaction_policy"] = {
        "legal_actions": "RULES_CORE_ONLY", "automatic_rules_actions": "RULES_CORE_ONLY",
        "discretionary_choices": "EXPLICIT_PREGAME_DECISION_PLAN", "fallbacks": "PROHIBITED",
    }


def repair_replay(record: dict[str, Any]) -> None:
    record["execution_entry_mode"] = "NATIVE_STATE_LOAD"
    record["rules_randomness"] = {
        "channels": ["NATIVE_LIBRARY_SHUFFLE"],
        "pilot_randomness_prohibited": True,
        "seed_binding": "SCENARIO_SEED",
        "provider_native_rng_calls_recorded": True,
    }
    record["replay_contract"] = {
        "transaction": [
            "NATIVE_CONSTRUCT_AND_VALIDATE_REQUESTED_STATE",
            "NATIVE_CAST_BURN_DOWN_THE_HOUSE",
            "EXTERNAL_SELECT_CREATE_DEVILS_MODE",
            "NATIVE_RESOLVE_CAST",
            "NATIVE_RULES_RNG_SHUFFLE_DECLARED_LIBRARY",
            "CAPTURE_DECISION_TAPE_EVENT_TAPE_AND_SEMANTIC_CHECKPOINTS",
        ],
        "fresh_process_replay_required": True,
        "same_provider_semantic_tapes_must_match": True,
        "same_provider_semantic_checkpoints_must_match": True,
        "cross_provider_raw_prng_call_sequence_equality_required": False,
    }
    for dec in record.get("decision_script", []):
        dec["causal_step_id"] = "cast-mode"
    record["native_procedure"] = [
        {"step_id": "load", "operation": "NATIVE_CONSTRUCT_AND_VALIDATE_REQUESTED_STATE", "details": {"requested_state_digest_required": True}},
        {"step_id": "cast-mode", "operation": "NATIVE_CAST_BURN_DOWN_THE_HOUSE_AND_REQUEST_MODE", "details": {"actor": "P1", "required_untapped_mountains": 5}},
        {"step_id": "mode", "operation": "EXTERNAL_SUBMIT_SELECTED_SEMANTIC_RESPONSE", "details": {"semantic_mode": "create_devils"}},
        {"step_id": "resolve", "operation": "NATIVE_RESOLVE_CAST_WITH_EXPLICIT_SCRIPTED_PRIORITY_PASSES", "details": {"fallbacks": "PROHIBITED"}},
        {"step_id": "rules-shuffle", "operation": "NATIVE_RULES_RNG_SHUFFLE_DECLARED_LIBRARY", "details": {"channel": "NATIVE_LIBRARY_SHUFFLE"}},
        {"step_id": "checkpoint", "operation": "NATIVE_CAPTURE_SEMANTIC_REPLAY_CHECKPOINT", "details": {"raw_provider_ids_excluded": True}},
    ]


def repair_defect(record: dict[str, Any]) -> None:
    fid = record["fixture_id"]
    special_prelude: list[dict[str, Any]] = []

    if fid == "PILOT_CHOOSE_OBJECT":
        obj = object_map(record).get("obj:syphon")
        if obj:
            obj["card_identity"] = "Raven's Crime"
        set_temporal(record, active="P2", priority="P1", phase="precombat_main", step="main")
    elif fid in {"PILOT_TARGET_AMOUNT", "PILOT_MULTI_AMOUNT"}:
        move_object(record, "obj:pilot-opus", "hand")
        add_basics(record, "P1", "Mountain", 7, f"{fid.lower()}-mountain")
        add_basics(record, "P1", "Island", 1, f"{fid.lower()}-island")
        special_prelude.append({"step_id": "begin-opus-cast", "operation": "NATIVE_BEGIN_PAYABLE_MAGMA_OPUS_CAST", "details": {"actor": "P1", "mana_value": 8}})
    elif fid == "NEGATIVE_DEFAULT_YES_NO":
        add_object(record, "obj:neg-opt", "Opt", "P1", "stack")
    elif fid in BURN_NEGATIVE:
        add_basics(record, "P1", "Mountain", 5, f"{fid.lower()}-mana")
    elif fid in BOLT_NEGATIVE:
        move_object(record, "obj:neg-bolt", "hand")
        add_basics(record, "P1", "Mountain", 1, f"{fid.lower()}-mana")
    elif fid == "NEGATIVE_INTERNAL_AI":
        add_object(record, "obj:neg-attacker-2", "Grizzly Bears", "P1", "battlefield", controlled_since_turn_began=True)
        for obj in record.get("semantic_objects", []):
            if obj.get("owner") == "P1" and obj.get("card_identity") == "Grizzly Bears" and obj.get("zone") == "battlefield":
                obj["controlled_since_turn_began"] = True
        set_temporal(record, active="P1", priority="P1", phase="combat", step="declare_attackers")
    elif fid == "MICRO_MODES":
        add_basics(record, "P1", "Mountain", 5, "micro-modes-mana")
    elif fid == "CARD_07":
        add_object(record, "obj:card07-lib-0", "Mountain", "P2", "library", zone_position=0)
        add_object(record, "obj:card07-lib-1", "Island", "P2", "library", zone_position=1)
        set_temporal(record, active="P2", priority="P1")
    elif fid == "CARD_16":
        add_object(record, "obj:card16-lib-0", "Mountain", "P1", "library", zone_position=0)
        add_object(record, "obj:card16-lib-1", "Island", "P1", "library", zone_position=1)
    elif fid in {"CARD_04", "CARD_25", "WS05-MP-COMBAT-5"}:
        record["combat_state"] = {"attackers": {}}
        set_temporal(record, phase="combat", step="declare_attackers")
    elif fid == "CARD_08":
        set_temporal(record, phase="precombat_main", step="main")
        special_prelude.append({"step_id": "cast-jeska", "operation": "NATIVE_CAST_AND_RESOLVE_JESKA_WITH_EXPLICIT_PRIORITY_PASSES", "details": {"actor": "P1", "source_semantic_id": "obj:card_08-subject"}})
    elif fid == "CARD_10":
        record["semantic_objects"] = [o for o in record.get("semantic_objects", []) if o.get("semantic_id") != "obj:P2-commander"]
        for c in record.get("commander_state", {}).get("commanders", []):
            if c.get("commander_id") == "cmd:P2-A":
                c["zone"] = "stack"
        set_temporal(record, active="P2", priority="P1")
    elif fid == "CARD_13":
        set_temporal(record, active="P2", priority="P1")
    elif fid == "CARD_17":
        set_temporal(record, active="P2", priority="P2", phase="precombat_main", step="main")
    elif fid == "WS05-MP-PRIO-3":
        add_basics(record, "P3", "Forest", 1, "ws05-prio3-green")
    elif fid == "WS05-MP-PRIO-5":
        add_basics(record, "P5", "Forest", 1, "ws05-prio5-green")
    elif fid == "WS05-MP-TRIG-5":
        record["decision_script"] = []
        add_basics(record, "P1", "Forest", 2, "ws05-trig5-cast")
        special_prelude.extend([
            {"step_id": "cast-enter", "operation": "NATIVE_CAST_AND_RESOLVE_ENTERING_GRIZZLY_BEARS", "details": {"actor": "P1", "source_semantic_id": "obj:mp-enter"}},
            {"step_id": "apnap", "operation": "NATIVE_CREATE_SIMULTANEOUS_SOUL_WARDEN_TRIGGERS_AND_PLACE_APNAP", "details": {"mandatory_triggers": True}},
        ])
    elif fid == "WS05-MP-ELIM-STACK-3":
        set_player_life(record, "P2", 0)
        special_prelude.append({"step_id": "sba-loss", "operation": "NATIVE_CHECK_STATE_BASED_ACTIONS_CAUSING_P2_TO_LOSE_AND_LEAVE", "details": {"cleanup_rule": "CR800.4"}})
    elif fid in {"WS05-CMD-DMG-SPLIT", "WS05-CMD-PARTNER-DMG"}:
        special_prelude.append({"step_id": "damage-sba", "operation": "NATIVE_CHECK_COMMANDER_DAMAGE_STATE_BASED_ACTION", "details": {"damage_is_per_commander": True}})
    elif fid == "WS05-CMD-PARTNER-TAX":
        special_prelude.append({"step_id": "tax-query", "operation": "NATIVE_ENUMERATE_COMMANDER_CAST_COSTS_FOR_BOTH_PARTNERS", "details": {"independent_command_zone_cast_counts": True}})
    elif fid == "CARD_29":
        special_prelude.append({"step_id": "saga-clock", "operation": "NATIVE_ADVANCE_TURNS_AND_SAGA_CHAPTERS_THROUGH_I_II_III", "details": {"no_synthetic_lore_counters": True}})

    if fid in {"WS05-CMD-MULL-2", "WS05-CMD-MULL-4"}:
        repair_pregame(record, 2 if fid.endswith("-2") else 4)
        return

    first = record.get("decision_script", [None])[0] if record.get("decision_script") else None
    if first and first.get("decision_family") == "priority":
        set_temporal(record, priority=first.get("actor"))
    if first and first.get("decision_family") == "declare_attacker":
        set_temporal(record, phase="combat", step="declare_attackers", active=first.get("actor"))
    if first and first.get("decision_family") == "declare_blocker":
        set_temporal(record, phase="combat", step="declare_blockers", priority=first.get("actor"))

    mark_attackers_eligible(record)
    if any(d.get("decision_family") == "declare_attacker" for d in record.get("decision_script", [])):
        record.setdefault("combat_state", {})["attackers"] = {}

    complete_stack(record)
    build_native_procedure(record, negative=record.get("fixture_family") == "pilot_boundary_negative", special_prelude=special_prelude)


def cast_cost_state(record: dict[str, Any], predecessor_pass: bool) -> list[dict[str, Any]]:
    objs = object_map(record)
    rows = []
    for index, dec in enumerate(record.get("decision_script", [])):
        if dec.get("decision_family") != "priority":
            continue
        value = dec.get("selection", {}).get("semantic_value")
        if not isinstance(value, dict) or not str(value.get("action", "")).startswith(("cast", "announce_cast")):
            continue
        sid = value.get("object")
        card = objs.get(sid, {}).get("card_identity") if sid else None
        actor = dec.get("actor")
        untapped_sources = [o["semantic_id"] for o in record.get("semantic_objects", []) if o.get("controller") == actor and o.get("zone") == "battlefield" and not o.get("tapped") and o.get("card_identity") in {"Mountain", "Island", "Swamp", "Forest", "Plains", "Path of Ancestry"}]
        basis = "EXPLICIT_NATIVE_RESOURCE_STATE"
        minimum = MINIMUM_MANA.get(card)
        payable = False
        if card == "Flare of Duplication" and value.get("action") == "cast_alt_cost":
            sacrifice = objs.get(value.get("sacrifice"), {})
            payable = bool(sacrifice) and record.get("temporal_state", {}).get("active_player") != actor
            basis = "ORACLE_ALTERNATIVE_COST_NONACTIVE_TURN_PLUS_NONTOKEN_RED_SACRIFICE"
            minimum = 0
        elif card == "Dig Through Time" and value.get("delve_objects"):
            payable = len(value.get("delve_objects", [])) >= 6 and len(value.get("mana_payment", [])) >= 2
            basis = "DELVE_SIX_PLUS_EXPLICIT_UU_PAYMENT"
            minimum = 2
        elif card == "Rograkh, Son of Rohgahh" or value.get("action") == "cast_commander":
            cid = value.get("commander_id") or objs.get(sid, {}).get("commander_id")
            prior = next((c.get("prior_command_zone_cast_count", 0) for c in record.get("commander_state", {}).get("commanders", []) if c.get("commander_id") == cid), 0)
            minimum = prior * 2
            payable = len(untapped_sources) >= minimum
            basis = "PRINTED_ZERO_PLUS_COMMANDER_TAX"
        elif minimum is not None:
            payable = len(untapped_sources) >= minimum
        elif predecessor_pass:
            payable = True
            basis = "V1_0_1_EXECUTABILITY_PASS_UNCHANGED_CAST_STATE"
        rows.append({
            "decision_index": index,
            "actor": actor,
            "source_semantic_id": sid,
            "card_identity": card,
            "payable": payable,
            "minimum_mana_or_equivalent": minimum,
            "explicit_payment_sources": untapped_sources,
            "evidence_basis": basis,
        })
    return rows


def extract_ids(value: Any, valid_ids: set[str]) -> set[str]:
    found: set[str] = set()
    if isinstance(value, str) and value in valid_ids:
        found.add(value)
    elif isinstance(value, dict):
        for k, v in value.items():
            if k in valid_ids:
                found.add(k)
            found |= extract_ids(v, valid_ids)
    elif isinstance(value, list):
        for item in value:
            found |= extract_ids(item, valid_ids)
    return found


def find_source(name: str) -> Path:
    candidates = list(ROOT.glob(f"**/{name}"))
    if not candidates:
        raise FileNotFoundError(name)
    return sorted(candidates)[0]


def record_digest(record: dict[str, Any]) -> str:
    clone = copy.deepcopy(record)
    clone.pop("materialization_digest", None)
    return hashlib.sha256(canonical_bytes(clone)).hexdigest()


def patch_schema(schema: dict[str, Any]) -> dict[str, Any]:
    schema = copy.deepcopy(schema)
    schema["$id"] = "https://commander-lab.invalid/schema/semantic-fixture-materialization-v1.0.2.json"
    schema["title"] = "Commander Lab Semantic Fixture Materialization v1.0.2"
    if "properties" in schema and "schema_version" in schema["properties"]:
        schema["properties"]["schema_version"] = {"const": VERSION}
    record_schema = schema.get("properties", {}).get("records", {}).get("items", {})
    props = record_schema.setdefault("properties", {})
    if "materialization_version" in props:
        props["materialization_version"] = {"const": VERSION}
    props.update({
        "semantic_executability": {"const": "SEMANTIC_EXECUTABLE"},
        "requested_state_digest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "obligation_digest": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "construction_validation": {"type": "object"},
        "action_cost_state": {"type": "array"},
        "execution_transaction_policy": {"type": "object"},
        "pregame_decision_plan": {"type": "array"},
        "replay_contract": {"type": "object"},
        "repair_provenance": {"type": "object"},
    })
    req = record_schema.setdefault("required", [])
    for key in ("semantic_executability", "requested_state_digest", "obligation_digest", "construction_validation", "action_cost_state", "execution_transaction_policy", "repair_provenance"):
        if key not in req:
            req.append(key)
    return schema


def build() -> None:
    old = load(OLD_MAT)
    old_schema = load(OLD_SCHEMA)
    old_report = load(OLD_REPORT)
    old_status = {r["fixture_id"]: r for r in old_report["records"]}
    defects = {fid for fid, row in old_status.items() if row.get("status") != "PASS"}
    if len(defects) != 63:
        raise RuntimeError(f"expected 63 v1.0.1 defects, got {len(defects)}")

    successor = copy.deepcopy(old)
    successor["schema_version"] = VERSION
    successor["record_count"] = 135
    successor["supersedes"] = {
        "materialization_version": "commander-lab.semantic-fixture-materialization/1.0.1",
        "commit": OLD_COMMIT,
        "tree": OLD_TREE,
        "bundle_digest": OLD_BUNDLE,
    }
    successor["protocol_version"] = PROTOCOL
    successor["authority_lock"] = {
        "ws31_head": WS31_HEAD,
        "aggregate_authority_digest": WS31_AUTHORITY,
        "current_comprehensive_rules_sha256": CR_SHA256,
        "comprehensive_rules_effective_date": "2026-08-07",
    }
    successor.pop("canonical_bundle_digest", None)

    predecessor_by_id = {r["fixture_id"]: r for r in old["records"]}
    ledger_rows = []
    closure_rows = []
    for record in successor["records"]:
        fid = record["fixture_id"]
        predecessor = predecessor_by_id[fid]
        predecessor_digest = predecessor.get("materialization_digest") or record_digest(predecessor)
        record["materialization_version"] = VERSION
        record["semantic_executability"] = "SEMANTIC_EXECUTABLE"
        record["construction_validation"] = {
            "required": True,
            "digest_spec": DIGEST_SPEC,
            "provider_must_emit_normalized_constructed_state": True,
            "credit_condition": "REQUESTED_STATE_DIGEST_EQUALS_CONSTRUCTED_STATE_DIGEST",
            "on_mismatch": "CANONICAL_SETUP_UNSUPPORTED_PROVIDER_AND_NO_RUNTIME_CREDIT",
        }
        record["repair_provenance"] = {
            "predecessor_version": "commander-lab.semantic-fixture-materialization/1.0.1",
            "predecessor_record_digest": predecessor_digest,
            "predecessor_semantic_status": old_status[fid].get("status"),
            "repair_class": "SEMANTIC_EXECUTABILITY_REPAIR" if fid in defects else "SUCCESSOR_METADATA_AND_HARDENING_ONLY",
        }

        if fid in defects:
            repair_defect(record)
        if fid in REPLAY_IDS:
            repair_replay(record)

        complete_stack(record)
        if fid not in defects and fid not in REPLAY_IDS:
            # Preserve v1.0.1 causal transactions, but successor metadata is explicit.
            record.setdefault("execution_transaction_policy", {
                "legal_actions": "RULES_CORE_ONLY",
                "automatic_rules_actions": "RULES_CORE_ONLY",
                "discretionary_choices": "ONLY_EXPLICIT_DECISION_SCRIPT_RESPONSES",
                "priority_passes": "EXPLICITLY_SCRIPTED_WHEN_NEEDED_TO_REACH_NEXT_DECLARED_CHECKPOINT",
                "fallbacks": "PROHIBITED",
            })

        record["action_cost_state"] = cast_cost_state(record, old_status[fid].get("status") == "PASS")
        record["obligation_digest"] = obligation_digest(record)
        record["requested_state_digest"] = requested_state_digest(record)
        record.pop("materialization_digest", None)
        record["materialization_digest"] = record_digest(record)

        defects_before = [e.get("code") for e in old_status[fid].get("errors", [])]
        ledger = {
            "fixture_id": fid,
            "old_digest": predecessor_digest,
            "new_digest": record["materialization_digest"],
            "predecessor_status": old_status[fid].get("status"),
            "defect_codes": defects_before,
            "correction": "Provider-neutral native causal transaction/state completion; no frozen expected event, terminal postcondition, AF binding, or authority identity changed." if fid in defects else "Successor metadata, requested-state digest, construction gate and hardening metadata only.",
            "unchanged_obligation": True,
            "old_obligation_digest": obligation_digest(predecessor),
            "new_obligation_digest": record["obligation_digest"],
            "authority_references": [
                f"WS31@{WS31_HEAD}", f"authority:{WS31_AUTHORITY}", f"CR_SHA256:{CR_SHA256}", "CURRENT_OFFICIAL_ORACLE_AND_RULINGS_WHERE_CARD_SPECIFIC",
            ],
            "linter_result": "PENDING_BUNDLE_LINT",
        }
        ledger_rows.append(ledger)
        if fid in defects:
            closure_rows.append(copy.deepcopy(ledger))

    successor["canonical_bundle_digest"] = hashlib.sha256(canonical_bytes({k: v for k, v in successor.items() if k != "canonical_bundle_digest"})).hexdigest()
    report = lint_bundle(successor, old)
    if report["terminal_status"] != "PASS":
        dump(OUT / "SEMANTIC_EXECUTABILITY_REPORT_v1_0_2.json", report)
        raise RuntimeError(f"successor semantic lint failed: {report['contract_defect_count']} record defects, global={report['global_errors']}")

    for row in ledger_rows:
        row["linter_result"] = "PASS"
    for row in closure_rows:
        row["linter_result"] = "PASS"

    valid_ids = {r["fixture_id"] for r in successor["records"]}
    starter_source = find_source("DIFFERENTIAL_STARTER_18_V1.json")
    union_source = find_source("KNOWN_PASS_UNION_50_V1.json")
    starter_ids = sorted(extract_ids(load(starter_source), valid_ids))
    union_ids = sorted(extract_ids(load(union_source), valid_ids))
    if len(starter_ids) != 18:
        raise RuntimeError(f"Starter source did not yield 18 IDs: {len(starter_ids)}")
    if len(union_ids) != 50:
        raise RuntimeError(f"Union source did not yield 50 IDs: {len(union_ids)}")
    by_id = {r["fixture_id"]: r for r in successor["records"]}

    schema = patch_schema(old_schema)
    materialization_path = OUT / "SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_2.json"
    dump(OUT / "SEMANTIC_FIXTURE_SCHEMA_v1_0_2.json", schema)
    dump(materialization_path, successor)
    dump(OUT / "SEMANTIC_EXECUTABILITY_REPORT_v1_0_2.json", report)
    dump(OUT / "DIFFERENTIAL_STARTER_18_v1_0_2.json", {
        "manifest_version": "commander-lab.differential-starter/1.0.2",
        "materialization_version": VERSION,
        "count": 18,
        "semantic_executable_count": 18,
        "fixture_ids": starter_ids,
        "records": [{"fixture_id": fid, "materialization_digest": by_id[fid]["materialization_digest"]} for fid in starter_ids],
    })
    dump(OUT / "KNOWN_PASS_UNION_50_v1_0_2.json", {
        "manifest_version": "commander-lab.known-pass-union/1.0.2",
        "historical_identity_count": 50,
        "runtime_denominator_count": 50,
        "semantic_executable_count": 50,
        "blocked_count": 0,
        "materialization_version": VERSION,
        "fixture_ids": union_ids,
        "records": [{"fixture_id": fid, "materialization_digest": by_id[fid]["materialization_digest"]} for fid in union_ids],
    })
    critical_ids = sorted(set(starter_ids) | defects | REPLAY_IDS | {"CARD_02"})
    dump(OUT / "CRITICAL_SUCCESSOR_GATE_v1_0_2.json", {
        "manifest_version": "commander-lab.critical-successor-gate/1.0.0",
        "materialization_version": VERSION,
        "count": len(critical_ids),
        "semantic_executable_count": len(critical_ids),
        "definition": "Starter-18 union all 63 v1.0.1 defects union replay/RNG canonical records union corrected CARD_02.",
        "fixture_ids": critical_ids,
        "records": [{"fixture_id": fid, "materialization_digest": by_id[fid]["materialization_digest"]} for fid in critical_ids],
    })
    dump(OUT / "REPLAY_RNG_CANONICAL_TRANSACTIONS_v1_0_2.json", {
        "contract_version": "commander-lab.replay-rng-transaction/1.0.0",
        "materialization_version": VERSION,
        "rules": {
            "native_rules_rng_only": True,
            "fresh_process_replay_required": True,
            "pilot_randomness_prohibited": True,
            "same_provider_semantic_tapes_and_checkpoints_equal": True,
            "cross_provider_raw_prng_sequence_equality_required": False,
        },
        "records": [copy.deepcopy(by_id[fid]) for fid in sorted(REPLAY_IDS)],
    })
    dump(OUT / "CARD_02_v1_0_2.json", copy.deepcopy(by_id["CARD_02"]))
    dump(OUT / "REQUESTED_STATE_DIGEST_SPEC_v1_0_2.json", {
        "spec_version": DIGEST_SPEC,
        "algorithm": "SHA-256",
        "encoding": "UTF-8",
        "canonical_json": {"sort_keys": True, "separators": [",", ":"], "ensure_ascii": False},
        "projection_keys": list(__import__("ws32_lint_semantic_v1_0_2").STATE_KEYS),
        "provider_credit_gate": "requested_state_digest == normalized_constructed_state_digest",
        "mismatch_result": "CANONICAL_SETUP_UNSUPPORTED_PROVIDER / NO_RUNTIME_CREDIT",
    })
    dump(OUT / "TERMINAL_ABC_SUPERSESSION_v1_0_2.json", {
        "artifact_version": "commander-lab.terminal-abc-supersession/1.0.0",
        "decision": "FORMALLY_DEPRECATED",
        "reason": "No normative Terminal A/B/C definitions are recoverable from the canonical project source corpus; inventing them would create new obligations only to preserve historical labels.",
        "historical_labels": ["Terminal A", "Terminal B", "Terminal C"],
        "entry_conditions": "N/A_DEPRECATED",
        "pass_conditions": "N/A_DEPRECATED",
        "fail_conditions": "N/A_DEPRECATED",
        "unknown_semantics": "Historical UNKNOWN remains provenance only and grants no PASS credit.",
        "replacement": {
            "contract_layer": ["G32-01", "G32-02", "G32-03", "G32-04", "G32-05", "G32-06", "G32-07"],
            "architecture_provider_layer": [f"AF{i:02d}" for i in range(12)],
        },
        "scope": "PROJECT_WIDE_LABEL_DEPRECATION; DOES_NOT_CHANGE_AF00_AF11",
    })
    dump(OUT / "SUPERSEDES_v1_0_1.json", {
        "artifact_version": "commander-lab.semantic-supersession/1.0.2",
        "predecessor": {"version": "commander-lab.semantic-fixture-materialization/1.0.1", "commit": OLD_COMMIT, "tree": OLD_TREE, "bundle_digest": OLD_BUNDLE},
        "successor": {"version": VERSION, "record_count": 135, "semantic_executable_count": 135, "contract_defect_count": 0},
        "immutable_predecessor": True,
        "fixture_id_set_preserved": True,
        "frozen_obligation_projection_preserved_135_of_135": True,
        "repaired_predecessor_defects": 63,
        "provider_model_embedded": False,
    })
    dump(OUT / "PER_RECORD_CHANGE_LEDGER_v1_0_2.json", {
        "ledger_version": "commander-lab.semantic-change-ledger/1.0.2",
        "record_count": len(ledger_rows),
        "semantic_repair_count": 63,
        "rows": ledger_rows,
    })
    dump(OUT / "DEFECT_63_CLOSURE_LEDGER_v1_0_2.json", {
        "ledger_version": "commander-lab.semantic-defect-closure/1.0.0",
        "predecessor_defect_count": 63,
        "closed_semantic_executable_count": 63,
        "contract_defect_count": 0,
        "rows": closure_rows,
    })
    dump(OUT / "WS32_SOURCE_LOCK.json", {
        "repository": "moeendres-png/commander-playtest-lab",
        "main_verified_commit": "c83e52ae79ff2242578757c0f517badbb1a2621c",
        "finalist_convergence_final_verified_commit": "36b8e8f241c92fe9baea2ea718f910fd31f5cf23",
        "finalist_convergence_evidence_lock": "20ca41a01132c3d79eee2184c52b2d56a614dff2",
        "v1_0_1_commit": OLD_COMMIT,
        "v1_0_1_tree": OLD_TREE,
        "v1_0_1_bundle_digest": OLD_BUNDLE,
        "ws31_head": WS31_HEAD,
        "authority_aggregate_digest": WS31_AUTHORITY,
        "cr_sha256": CR_SHA256,
        "protocol": PROTOCOL,
    })

    # Freeze digests are over all authoritative outputs except checksum/bundle metadata themselves.
    authoritative = sorted(p for p in OUT.glob("*") if p.is_file() and p.name not in {"SHA256SUMS_v1_0_2", "WS32_BUNDLE_MANIFEST_v1_0_2.json"})
    files = [{"path": str(p.relative_to(ROOT)), "sha256": sha256_file(p), "bytes": p.stat().st_size} for p in authoritative]
    bundle_payload = {"contract_version": VERSION, "files": files}
    bundle_digest = hashlib.sha256(canonical_bytes(bundle_payload)).hexdigest()
    dump(OUT / "WS32_BUNDLE_MANIFEST_v1_0_2.json", {
        "manifest_version": "commander-lab.ws32-freeze-bundle/1.0.0",
        "contract_version": VERSION,
        "bundle_digest_algorithm": "SHA-256(canonical JSON of contract_version + sorted authoritative file rows)",
        "bundle_digest": bundle_digest,
        "files": files,
    })
    checksum_files = sorted([*authoritative, OUT / "WS32_BUNDLE_MANIFEST_v1_0_2.json"])
    (OUT / "SHA256SUMS_v1_0_2").write_text("".join(f"{sha256_file(p)}  {p.name}\n" for p in checksum_files), encoding="utf-8")


if __name__ == "__main__":
    build()
