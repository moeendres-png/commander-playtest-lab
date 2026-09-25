#!/usr/bin/env python3
"""Build execution-authoritative semantic materialization v1.0.1.

This is an immutable errata transform over WS30 v1.0.0.  It deliberately does
not rewrite the historical artifacts.  The frozen fixture IDs, denominator,
Common bindings, AF mappings, and WS29 card semantics are retained byte-for-
byte where they are contractual; only execution-completeness fields and
causal scenario construction are changed.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAT = ROOT / "qualification" / "materialization"
OUT = ROOT / "qualification" / "finalist_convergence"
OLD_VERSION = "commander-lab.semantic-fixture-materialization/1.0.0"
VERSION = "commander-lab.semantic-fixture-materialization/1.0.1"
WS31_HEAD = "1bee87b9a0c4db90ecbf1f5374fae0732d6dd16e"
WS31_AGGREGATE = "d8337dc0a243fddbede3e9d2cec7b3938a1007970a23dea04855149fbfc55d5e"
COMMON_SHA = "e7f34ea4b2543132440e7e5fdb47c6cb4d4908f05fb49f6fa59f3e0592ca3bd4"
OLD_BUNDLE = "d4f0f78fd8307e708ccbf316f709a70c61e4e73710d16507a531620e1b7018d1"
OLD_RAW = "c99b9947833ace9a59370c06a1a9a9cc1d01601e8b746a82c9acce84864d03c9"

STARTER18 = [
    "PLAYER_COUNT_2P", "PLAYER_COUNT_3P", "PLAYER_COUNT_4P", "PLAYER_COUNT_5P",
    "PILOT_MULLIGAN", "PILOT_PRIORITY", "PILOT_TARGET", "HIDDEN_01", "HIDDEN_02",
    "MICRO_STACK", "MICRO_REPLACEMENT", "WS05-MP-COMBAT-4", "RNG_RULES_TAPE",
    "REPLAY_DECISION_TAPE", "REPLAY_EVENT_TAPE", "REPLAY_CLEAN_PROCESS",
    "REPLAY_STATE_HASHES", "CARD_02",
]

KNOWN_ADDITIONAL = [
    "MICRO_COSTS", "MICRO_MANA_PAYMENT", "MICRO_PRIORITY", "MICRO_TARGETS",
    "MICRO_TRIGGERS", "MICRO_PREVENTION", "MICRO_STATE_BASED_ACTIONS",
    "MICRO_ZONE_CHANGES", "PILOT_MANA_PAYMENT", "PILOT_REPLACEMENT_EFFECT",
    "PILOT_CHOICE", "PILOT_CHOOSE_USE", "PILOT_ANNOUNCE_X", "PILOT_CHOOSE_MODE",
    "PILOT_DECLARE_ATTACKER", "WS05-MP-BLOCK-4", "WS05-MP-TRIG-3",
    "NEGATIVE_PARENT_CLASS_FALLBACK",
]


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_sha(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def raw_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repository_raw_sha(path: Path) -> str:
    """Hash repository bytes independent of the Windows CRLF checkout filter."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def write_json(path: Path, value) -> None:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    path.write_bytes(payload.encode("utf-8"))


def object_(sid, card, owner, zone, *, controller=None, tapped=False,
            commander_id=None, position=None, controlled_since=None):
    value = {
        "semantic_id": sid,
        "card_identity": card,
        "owner": owner,
        "controller": controller or owner,
        "zone": zone,
        "tapped": tapped,
        "face_down": False,
        "counters": {},
        "card_lineage_id": f"line:{sid}",
    }
    if commander_id:
        value["commander_id"] = commander_id
    if position is not None:
        value["zone_position"] = position
    if controlled_since is not None:
        value["controlled_since_turn_began"] = controlled_since
    return value


def decision(family, actor, selector_kind, semantic_value, causal_step):
    return {
        "decision_family": family,
        "actor": actor,
        "selection": {
            "selector_kind": selector_kind,
            "semantic_value": semantic_value,
            "matches_only_provider_offered_legal_options": True,
            "on_zero_match": "FAIL_CLOSED",
            "on_multiple_match": "FAIL_CLOSED",
        },
        "forbidden_fallbacks": [
            "first_option", "random_option", "default_yes_no", "internal_ai",
            "gui_default", "silent_skip", "parent_class_fallback",
        ],
        "notes": "",
        "causal_step_id": causal_step,
    }


def step(step_id, operation, actor=None, source=None, **details):
    value = {"step_id": step_id, "operation": operation, "details": details}
    if actor:
        value["actor"] = actor
    if source:
        value["source_object"] = source
    return value


def by_id(record, sid):
    return next((o for o in record["semantic_objects"] if o["semantic_id"] == sid), None)


def remove_ids(record, ids):
    record["semantic_objects"] = [o for o in record["semantic_objects"] if o["semantic_id"] not in ids]


def add_lands(record, owner, card, count, prefix):
    for i in range(count):
        record["semantic_objects"].append(
            object_(f"obj:{prefix}-{i + 1}", card, owner, "battlefield", controlled_since=True)
        )


def commander_decks(n):
    return [
        {
            "player_id": f"P{i}", "commander_ids": [f"cmd:P{i}-A"],
            "library_template": {"card_identity": "Mountain", "count": 99},
            "opening_hand_size": 7, "shuffle_channel": f"library_shuffle:P{i}",
        }
        for i in range(1, n + 1)
    ]


def natural_player_count(record):
    n = len(record["players"])
    record["execution_entry_mode"] = "NATURAL_GAME_START"
    record["temporal_state"] = {
        "turn_number": 0, "active_player": "P1", "phase": "pregame",
        "step": "game_start", "priority_player": "P1", "extra_turn_queue": [],
    }
    record["deck_state"] = commander_decks(n)
    record["rules_randomness"]["channels"] = [f"library_shuffle:P{i}" for i in range(1, n + 1)]
    record["decision_script"] = [
        decision("mulligan", f"P{i}", "semantic_action", "keep_opening_hand", f"keep-P{i}")
        for i in range(1, n + 1)
    ]
    record["native_procedure"] = [
        step("create", "CREATE_COMMANDER_GAME", player_count=n, starting_life=40),
        step("shuffle", "NATIVE_SEEDED_INITIAL_SHUFFLE", channels=record["rules_randomness"]["channels"]),
        step("draw", "NATIVE_OPENING_HAND_DRAW", cards_each=7),
    ] + [step(f"keep-P{i}", "NATIVE_MULLIGAN_PROMPT", actor=f"P{i}", round=1) for i in range(1, n + 1)] + [
        step("start", "NATIVE_START_FIRST_TURN", actor="P1")
    ]


def fix_mulligan(record):
    record["execution_entry_mode"] = "NATURAL_GAME_START"
    remove_ids(record, {"obj:p1-bears", "obj:p2-bears", "obj:p3-bears"})
    record["deck_state"] = commander_decks(4)
    record["rules_randomness"]["channels"] = [f"library_shuffle:P{i}" for i in range(1, 5)]
    record["decision_script"] = [
        decision("mulligan", "P1", "semantic_action", "mulligan", "mull-r1-P1"),
        decision("mulligan", "P2", "semantic_action", "keep_opening_hand", "mull-r1-P2"),
        decision("mulligan", "P3", "semantic_action", "keep_opening_hand", "mull-r1-P3"),
        decision("mulligan", "P4", "semantic_action", "keep_opening_hand", "mull-r1-P4"),
        decision("mulligan", "P1", "semantic_action", "keep_opening_hand", "mull-r2-P1"),
    ]
    record["native_procedure"] = [
        step("create", "CREATE_COMMANDER_GAME", player_count=4, starting_life=40),
        step("shuffle", "NATIVE_SEEDED_INITIAL_SHUFFLE", channels=record["rules_randomness"]["channels"]),
        step("draw", "NATIVE_OPENING_HAND_DRAW", cards_each=7),
        step("mull-r1-P1", "NATIVE_MULLIGAN_PROMPT", actor="P1", round=1),
        step("mull-r1-P2", "NATIVE_MULLIGAN_PROMPT", actor="P2", round=1),
        step("mull-r1-P3", "NATIVE_MULLIGAN_PROMPT", actor="P3", round=1),
        step("mull-r1-P4", "NATIVE_MULLIGAN_PROMPT", actor="P4", round=1),
        step("mull-r2-P1", "NATIVE_MULLIGAN_PROMPT", actor="P1", round=2),
    ]
    record["expected_events"]["required_events"] = [
        "mulligan:P1:round1", "keep:P2:round1", "keep:P3:round1", "keep:P4:round1",
        "keep:P1:round2", "bottom_count:P1:0",
    ]


def fix_cast_bolt(record, *, target_fixture=False):
    bolt = next(o for o in record["semantic_objects"] if o["card_identity"] == "Lightning Bolt")
    bolt["zone"] = "hand"
    record["semantic_objects"].append(
        object_("obj:pilot-mountain", "Mountain", "P1", "battlefield", controlled_since=True)
    )
    if target_fixture:
        record["decision_script"] = [
            decision("priority", "P1", "semantic_action", {"action": "cast", "object": bolt["semantic_id"]}, "cast-bolt"),
            decision("target", "P1", "semantic_player", "P2", "cast-bolt"),
        ]
    else:
        record["decision_script"] = [
            decision("priority", "P1", "semantic_action", {"action": "cast", "object": bolt["semantic_id"]}, "cast-bolt"),
            decision("target", "P1", "semantic_player", "P2", "cast-bolt"),
        ]
    record["native_procedure"] = [
        step("cast-bolt", "NATIVE_CAST_SPELL", actor="P1", source=bolt["semantic_id"],
             from_zone="hand", cost="{R}", target_cardinality=1),
        step("resolve-bolt", "NATIVE_RESOLVE_TOP_OF_STACK", source=bolt["semantic_id"]),
    ]


def fix_stack(record, priority_only=False):
    record["temporal_state"]["priority_player"] = "P2"
    record["semantic_objects"].append(
        object_("obj:micro-forest", "Forest", "P2", "battlefield", controlled_since=True)
    )
    record["stack_state"] = [{
        "semantic_stack_id": "stack:1", "source_object": "obj:micro-bolt",
        "controller": "P1", "targets": ["obj:micro-target"], "modes": [],
        "cast_complete": True,
    }]
    record["decision_script"] = [
        decision("priority", "P2", "semantic_action",
                 {"action": "cast", "object": "obj:micro-growth"}, "cast-growth"),
        decision("target", "P2", "semantic_object", "obj:micro-target", "cast-growth"),
    ]
    record["native_procedure"] = [
        step("resume", "NATIVE_RESUME_WITH_FULLY_CAST_STACK_SPELL", source="obj:micro-bolt",
             targets=["obj:micro-target"]),
        step("cast-growth", "NATIVE_CAST_SPELL", actor="P2", source="obj:micro-growth",
             from_zone="hand", cost="{G}", target_cardinality=1),
        step("resolve-growth", "NATIVE_RESOLVE_TOP_OF_STACK", source="obj:micro-growth"),
        step("resolve-bolt", "NATIVE_RESOLVE_TOP_OF_STACK", source="obj:micro-bolt"),
    ]


def fix_replacement(record):
    attacker = by_id(record, "obj:micro-3power")
    attacker["controlled_since_turn_began"] = True
    record["temporal_state"].update({"phase": "combat", "step": "combat_damage", "priority_player": "P1"})
    record["combat_state"] = {
        "attackers": {"obj:micro-3power": "P2"}, "blockers": {},
        "unblocked_attackers": ["obj:micro-3power"],
    }
    record["native_procedure"] = [
        step("resume-combat", "NATIVE_ENTER_COMBAT_DAMAGE_STEP", actor="P1"),
        step("damage", "NATIVE_CREATE_COMBAT_DAMAGE_EVENT", source="obj:micro-3power",
             recipient="P2", amount=3),
        step("replacement", "NATIVE_APPLY_REPLACEMENT_EFFECT", source="obj:micro-violence",
             input_damage=3, output_damage=6),
    ]


def fix_combat(record):
    record["temporal_state"].update({"phase": "combat", "step": "declare_attackers", "priority_player": "P1"})
    for sid in ("obj:mp-attacker-0", "obj:mp-attacker-1"):
        by_id(record, sid)["controlled_since_turn_began"] = True
    record["combat_state"] = {
        "attackers": {}, "eligible_attackers": ["obj:mp-attacker-0", "obj:mp-attacker-1"]
    }
    record["decision_script"] = [decision(
        "declare_attacker", "P1", "attacker_assignment",
        {"obj:mp-attacker-0": "P2", "obj:mp-attacker-1": "P3"}, "declare-attackers")]
    record["native_procedure"] = [
        step("enter", "NATIVE_ENTER_DECLARE_ATTACKERS_STEP", actor="P1"),
        step("declare-attackers", "NATIVE_DECLARE_ATTACKERS", actor="P1", assignments={
            "obj:mp-attacker-0": "P2", "obj:mp-attacker-1": "P3"}),
    ]


def fix_replay(record):
    add_lands(record, "P1", "Mountain", 5, "replay-mountain")
    record["decision_script"] = [
        decision("priority", "P1", "semantic_action",
                 {"action": "cast", "object": "obj:replay-burn"}, "cast-burn"),
        decision("choose_mode", "P1", "semantic_mode_key", "create_devils", "cast-burn"),
    ]
    record["native_procedure"] = [
        step("cast-burn", "NATIVE_CAST_SPELL", actor="P1", source="obj:replay-burn",
             from_zone="hand", cost="{3}{R}{R}", mode_count=1),
        step("resolve-burn", "NATIVE_RESOLVE_TOP_OF_STACK", source="obj:replay-burn"),
        step("shuffle", "NATIVE_EXPLICIT_LIBRARY_SHUFFLE", actor="P1",
             channel="library_shuffle:P1", tape="RulesRngTape"),
        step("replay", "FRESH_PROCESS_SEMANTIC_REPLAY", actor="P1",
             compare="semantic checkpoints and terminal state"),
    ]


def fix_card02(record):
    remove_ids(record, {"obj:card_02-subject"})
    record["decision_script"] = [decision(
        "priority", "P1", "semantic_action",
        {"action": "cast_commander", "commander_id": "cmd:P1-A", "from_zone": "command"},
        "cast-commander")]
    record["native_procedure"] = [
        step("cast-commander", "NATIVE_CAST_COMMANDER", actor="P1", source="obj:P1-commander",
             printed_cost="{0}", prior_command_zone_cast_count=0, commander_tax="{0}"),
        step("resolve", "NATIVE_RESOLVE_TOP_OF_STACK", source="obj:P1-commander"),
    ]


def fix_known_additional(record):
    fid = record["fixture_id"]
    if fid == "MICRO_COSTS":
        # Six legal creature targets, including both of P1's commanders, preserve the
        # exact Esior once-per-spell discriminator. Hex {4}{B}{B} + {3} = {7}{B}{B}.
        remove_ids(record, {"obj:p1-bears", "obj:p2-bears", "obj:p3-bears", "obj:micro-hex"})
        p1cmd = by_id(record, "obj:P1-commander")
        p1cmd["zone"] = "battlefield"; p1cmd["controlled_since_turn_began"] = True
        record["commander_state"]["commanders"][0]["zone"] = "battlefield"
        record["semantic_objects"] += [
            object_("obj:cost-a", "Grizzly Bears", "P1", "battlefield", controlled_since=True),
            object_("obj:cost-b", "Grizzly Bears", "P2", "battlefield", controlled_since=True),
            object_("obj:cost-c", "Grizzly Bears", "P3", "battlefield", controlled_since=True),
            object_("obj:cost-d", "Grizzly Bears", "P4", "battlefield", controlled_since=True),
            object_("obj:micro-hex", "Hex", "P2", "hand"),
        ]
        existing_kediss = by_id(record, "obj:micro-cmd-b")
        existing_kediss["controlled_since_turn_began"] = True
        record["commander_state"]["commanders"].append({
            "commander_id": "cmd:P1-B", "card_identity": "Kediss, Emberclaw Familiar",
            "owner": "P1", "zone": "battlefield", "prior_command_zone_cast_count": 0,
        })
        add_lands(record, "P2", "Swamp", 9, "cost-swamp")
        targets = ["obj:P1-commander", "obj:micro-cmd-b", "obj:cost-a", "obj:cost-b", "obj:cost-c", "obj:cost-d"]
        record["decision_script"] = [
            decision("priority", "P2", "semantic_action", {"action": "cast", "object": "obj:micro-hex"}, "cast-hex"),
            decision("target", "P2", "semantic_objects", targets, "cast-hex"),
        ]
        record["native_procedure"] = [step(
            "cast-hex", "NATIVE_CAST_SPELL", actor="P2", source="obj:micro-hex", from_zone="hand",
            printed_cost="{4}{B}{B}", targets=targets, expected_total_cost="{7}{B}{B}")]
        record["scenario_notes"].append("OBLIGATION_PRESERVED: Hex has six legal creature targets and Esior increases the spell once by {3} although two commanders are targeted.")
    elif fid in {"MICRO_MANA_PAYMENT", "PILOT_MANA_PAYMENT"}:
        record["stack_state"] = [{"semantic_stack_id": "stack:1", "source_object": "obj:opp-bolt" if fid.startswith("PILOT") else "obj:micro-bolt", "controller": "P2", "targets": ["P1"], "modes": [], "cast_complete": True}]
        source = "obj:counterspell" if fid.startswith("PILOT") else "obj:micro-counter"
        record["decision_script"] = [
            decision("priority", "P1", "semantic_action", {"action": "cast", "object": source}, "cast-counter"),
            decision("target", "P1", "semantic_stack_object", "stack:1", "cast-counter"),
            decision("mana_payment", "P1", "mana_payment", {"mana": ["U", "U"]}, "cast-counter"),
        ]
        record["native_procedure"] = [step("cast-counter", "NATIVE_CAST_SPELL", actor="P1", source=source, from_zone="hand", cost="{U}{U}", target_cardinality=1)]
    elif fid == "MICRO_PRIORITY":
        fix_stack(record, priority_only=True)
    elif fid == "MICRO_TARGETS":
        fix_cast_bolt(record, target_fixture=True)
    elif fid == "MICRO_TRIGGERS":
        add_lands(record, "P1", "Forest", 2, "trigger-forest")
        record["decision_script"] = [
            decision("priority", "P1", "semantic_action", {"action": "cast", "object": "obj:micro-enter"}, "cast-creature"),
            decision("target", "P1", "semantic_player", "P2", "warstorm-trigger"),
        ]
        record["native_procedure"] = [
            step("cast-creature", "NATIVE_CAST_SPELL", actor="P1", source="obj:micro-enter", from_zone="hand", cost="{1}{G}"),
            step("resolve-creature", "NATIVE_RESOLVE_TOP_OF_STACK", source="obj:micro-enter"),
            step("warstorm-trigger", "NATIVE_CREATE_TRIGGER", actor="P1", source="obj:micro-surge", target_cardinality=1),
        ]
    elif fid == "MICRO_PREVENTION":
        fog = next(o for o in record["semantic_objects"] if o["card_identity"] == "Fog")
        fog["zone"] = "hand"
        add_lands(record, "P2", "Forest", 1, "fog-forest")
        attacker = next(o for o in record["semantic_objects"] if o["semantic_id"].startswith("obj:micro-attacker"))
        attacker["controlled_since_turn_began"] = True
        record["temporal_state"].update({"phase": "combat", "step": "declare_attackers", "priority_player": "P2"})
        record.pop("continuous_rules_effects", None)
        record["combat_state"] = {"attackers": {attacker["semantic_id"]: "P2"}, "blockers": {}, "unblocked_attackers": [attacker["semantic_id"]]}
        record["decision_script"] = [decision("priority", "P2", "semantic_action", {"action": "cast", "object": fog["semantic_id"]}, "cast-fog")]
        record["native_procedure"] = [
            step("cast-fog", "NATIVE_CAST_SPELL", actor="P2", source=fog["semantic_id"], from_zone="hand", cost="{G}"),
            step("resolve-fog", "NATIVE_RESOLVE_TOP_OF_STACK", source=fog["semantic_id"]),
            step("damage", "NATIVE_ENTER_COMBAT_DAMAGE_STEP", actor="P1"),
        ]
    elif fid == "MICRO_STATE_BASED_ACTIONS":
        remove_ids(record, {o["semantic_id"] for o in record["semantic_objects"] if o["card_identity"] in {"Find // Finality", "Grizzly Bears"} and o["semantic_id"].startswith("obj:micro")})
        record.pop("continuous_rules_effects", None)
        record["semantic_objects"] += [
            object_("obj:sba-night", "Night of Souls' Betrayal", "P1", "battlefield", controlled_since=True),
            object_("obj:sba-memnite", "Memnite", "P1", "hand"),
        ]
        record["decision_script"] = [decision("priority", "P1", "semantic_action", {"action": "cast", "object": "obj:sba-memnite"}, "cast-memnite")]
        record["native_procedure"] = [
            step("cast-memnite", "NATIVE_CAST_SPELL", actor="P1", source="obj:sba-memnite", from_zone="hand", cost="{0}"),
            step("resolve", "NATIVE_RESOLVE_TOP_OF_STACK", source="obj:sba-memnite"),
            step("sba", "NATIVE_CHECK_STATE_BASED_ACTIONS", source="obj:sba-memnite", expected_toughness=0),
        ]
    elif fid == "MICRO_ZONE_CHANGES":
        bolt = next(o for o in record["semantic_objects"] if o["card_identity"] == "Lightning Bolt")
        record["stack_state"] = [{"semantic_stack_id": "stack:1", "source_object": bolt["semantic_id"], "controller": "P1", "targets": ["P2"], "modes": [], "cast_complete": True}]
        record["native_procedure"] = [
            step("resume", "NATIVE_RESUME_WITH_FULLY_CAST_STACK_SPELL", source=bolt["semantic_id"], targets=["P2"]),
            step("resolve", "NATIVE_RESOLVE_TOP_OF_STACK", source=bolt["semantic_id"]),
        ]
    elif fid == "PILOT_REPLACEMENT_EFFECT":
        remove_ids(record, {"obj:P1-commander"})
        commander = by_id(record, "obj:p1-commander-bf")
        commander["card_lineage_id"] = "line:obj:P1-commander"
        record["commander_state"]["commanders"][0]["zone"] = "battlefield"
        record["semantic_objects"].append(object_("obj:pilot-unsummon", "Unsummon", "P2", "stack"))
        record["stack_state"] = [{"semantic_stack_id": "stack:1", "source_object": "obj:pilot-unsummon", "controller": "P2", "targets": [commander["semantic_id"]], "modes": [], "cast_complete": True}]
        record["decision_script"] = [decision("replacement_effect", "P1", "boolean", True, "resolve-unsummon")]
        record["native_procedure"] = [
            step("resume", "NATIVE_RESUME_WITH_FULLY_CAST_STACK_SPELL", source="obj:pilot-unsummon", targets=[commander["semantic_id"]]),
            step("resolve-unsummon", "NATIVE_RESOLVE_TOP_OF_STACK", source="obj:pilot-unsummon"),
        ]
    elif fid == "PILOT_CHOICE":
        record["stack_state"] = [{"semantic_stack_id": "stack:1", "source_object": "obj:utopia", "controller": "P1", "targets": ["obj:forest"], "modes": [], "cast_complete": True}]
        record["decision_script"] = [decision("choice", "P1", "semantic_choice_key", "RED", "resolve-utopia")]
        record["native_procedure"] = [step("resolve-utopia", "NATIVE_RESOLVE_TOP_OF_STACK", source="obj:utopia", attached_to="obj:forest")]
    elif fid == "PILOT_CHOOSE_USE":
        record["semantic_objects"] += [object_("obj:path-marauders", "Keldon Marauders", "P1", "hand"), object_("obj:path-mountain", "Mountain", "P1", "battlefield", controlled_since=True)]
        record["decision_script"] = [
            decision("priority", "P1", "semantic_action", {"action": "cast", "object": "obj:path-marauders"}, "cast-warrior"),
            decision("mana_payment", "P1", "mana_payment", {"sources": ["obj:path", "obj:path-mountain"], "mana": ["R", "R"]}, "cast-warrior"),
            decision("choose_use", "P1", "boolean", False, "resolve-scry"),
        ]
        record["native_procedure"] = [
            step("cast-warrior", "NATIVE_CAST_SPELL", actor="P1", source="obj:path-marauders", from_zone="hand", cost="{1}{R}", shared_commander_type="Warrior"),
            step("resolve-warrior", "NATIVE_RESOLVE_TOP_OF_STACK", source="obj:path-marauders"),
            step("resolve-scry", "NATIVE_RESOLVE_TRIGGER", source="obj:path", effect="scry 1"),
        ]
    elif fid == "PILOT_ANNOUNCE_X":
        add_lands(record, "P1", "Island", 5, "finale-island")
        record["decision_script"] = [
            decision("priority", "P1", "semantic_action", {"action": "cast", "object": "obj:finale"}, "cast-finale"),
            decision("announce_x", "P1", "integer", 3, "cast-finale"),
        ]
        record["native_procedure"] = [step("cast-finale", "NATIVE_CAST_SPELL", actor="P1", source="obj:finale", from_zone="hand", cost="{X}{U}{U}", announced_x=3)]
    elif fid == "PILOT_CHOOSE_MODE":
        add_lands(record, "P1", "Mountain", 5, "pilot-burn-mountain")
        record["decision_script"] = [
            decision("priority", "P1", "semantic_action", {"action": "cast", "object": "obj:burn"}, "cast-burn"),
            decision("choose_mode", "P1", "semantic_mode_key", "create_devils", "cast-burn"),
        ]
        record["native_procedure"] = [step("cast-burn", "NATIVE_CAST_SPELL", actor="P1", source="obj:burn", from_zone="hand", cost="{3}{R}{R}", mode_count=1)]
    elif fid == "PILOT_DECLARE_ATTACKER":
        attacker = by_id(record, "obj:p1-bears"); attacker["controlled_since_turn_began"] = True
        record["temporal_state"].update({"phase": "combat", "step": "declare_attackers", "priority_player": "P1"})
        record["combat_state"] = {"attackers": {}, "eligible_attackers": [attacker["semantic_id"]]}
        record["decision_script"] = [decision("declare_attacker", "P1", "attacker_assignment", {attacker["semantic_id"]: "P2"}, "declare")]
        record["native_procedure"] = [step("enter", "NATIVE_ENTER_DECLARE_ATTACKERS_STEP", actor="P1"), step("declare", "NATIVE_DECLARE_ATTACKERS", actor="P1", assignments={attacker["semantic_id"]: "P2"})]
    elif fid == "WS05-MP-BLOCK-4":
        record["temporal_state"].update({"phase": "combat", "step": "declare_blockers", "active_player": "P1", "priority_player": "P2"})
        cs = record["combat_state"]
        cs.setdefault("eligible_blockers", ["obj:mp-blocker"])
        record["native_procedure"] = [step("enter", "NATIVE_ENTER_DECLARE_BLOCKERS_STEP", actor="P2"), step("declare", "NATIVE_DECLARE_BLOCKERS", actor="P2", assignments=record["decision_script"][0]["selection"]["semantic_value"])]
        for d in record["decision_script"]: d["causal_step_id"] = "declare"
    elif fid == "WS05-MP-TRIG-3":
        add_lands(record, "P1", "Forest", 2, "mp-trigger-forest")
        record["decision_script"] = [decision("priority", "P1", "semantic_action", {"action": "cast", "object": "obj:mp-enter"}, "cast-creature")]
        record["native_procedure"] = [step("cast-creature", "NATIVE_CAST_SPELL", actor="P1", source="obj:mp-enter", from_zone="hand", cost="{1}{G}"), step("resolve", "NATIVE_RESOLVE_TOP_OF_STACK", source="obj:mp-enter"), step("triggers", "NATIVE_CREATE_TRIGGER", source="Soul Warden", count=3)]
    elif fid == "NEGATIVE_PARENT_CLASS_FALLBACK":
        record["semantic_objects"].append(object_("obj:negative-syphon", "Syphon Mind", "P2", "stack"))
        record["stack_state"] = [{"semantic_stack_id": "stack:1", "source_object": "obj:negative-syphon", "controller": "P2", "targets": [], "modes": [], "cast_complete": True}]
        record["decision_script"] = []
        record["negative_fallback_probe"].update({"omitted_handler": "choose_object", "expected_termination": "DECISION_SELECTOR_UNSUPPORTED", "production_decision_reached_natively": True})
        record["native_procedure"] = [step("resume", "NATIVE_RESUME_WITH_FULLY_CAST_STACK_SPELL", source="obj:negative-syphon"), step("resolve", "NATIVE_RESOLVE_TOP_OF_STACK", source="obj:negative-syphon", expected_decision_actor="P1", intentionally_omitted_handler="choose_object")]


def update_schema(old_schema):
    schema = copy.deepcopy(old_schema)
    schema["$id"] = VERSION
    schema["title"] = "Commander Lab Semantic Fixture Materialization v1.0.1"
    schema["properties"]["schema_version"] = {"const": VERSION}
    schema["$defs"]["record"]["properties"]["materialization_version"] = {"const": VERSION}
    schema["$defs"]["record"]["properties"]["execution_entry_mode"] = {
        "enum": ["NATURAL_GAME_START", "NATIVE_STATE_LOAD"]
    }
    schema["$defs"]["record"]["properties"]["native_procedure"] = {
        "type": "array", "minItems": 1, "items": {"type": "object"}
    }
    schema["$defs"]["record"]["properties"]["supersedes_record_digest"] = {
        "type": "string", "pattern": "^[0-9a-f]{64}$"
    }
    schema["$defs"]["record"]["required"] += ["execution_entry_mode", "native_procedure"]
    schema["$defs"]["object"]["properties"]["controlled_since_turn_began"] = {"type": "boolean"}
    schema["$defs"]["decision"]["properties"]["causal_step_id"] = {"type": "string", "minLength": 1}
    schema["$defs"]["decision"]["required"].append("causal_step_id")
    return schema


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    old_path = MAT / "SEMANTIC_FIXTURE_MATERIALIZATION_v1.json"
    old = load(old_path)
    if old["schema_version"] != OLD_VERSION or old["canonical_bundle_digest"] != OLD_BUNDLE:
        raise SystemExit("fail closed: WS30 v1.0.0 identity mismatch")
    if repository_raw_sha(old_path) != OLD_RAW:
        raise SystemExit("fail closed: WS30 v1.0.0 raw SHA mismatch")

    corpus = copy.deepcopy(old)
    corpus["schema_version"] = VERSION
    records = corpus["records"]
    table = {r["fixture_id"]: r for r in records}
    changed = set()
    for record in records:
        record["materialization_version"] = VERSION
        record["execution_entry_mode"] = "NATIVE_STATE_LOAD"
        record["native_procedure"] = [step("load", "NATIVE_CONSTRUCT_AND_VALIDATE_REQUESTED_STATE")]
        record["setup_validation"]["requested_vs_normalized_native_constructed_state_equality_required"] = True
        record["authority_provenance"]["ws31_authority_head"] = WS31_HEAD
        record["authority_provenance"]["ws31_authority_domain_digest"] = WS31_AGGREGATE
        for scripted_decision in record["decision_script"]:
            scripted_decision.setdefault("causal_step_id", "UNSPECIFIED_NATIVE_CAUSE")
        if record["fixture_family"] == "actual_card":
            record["authority_provenance"]["ws29_expected_semantics_preserved"] = True

    for fid in STARTER18:
        r = table[fid]
        if fid.startswith("PLAYER_COUNT_"): natural_player_count(r)
        elif fid == "PILOT_MULLIGAN": fix_mulligan(r)
        elif fid == "PILOT_PRIORITY": fix_cast_bolt(r)
        elif fid == "PILOT_TARGET": fix_cast_bolt(r, target_fixture=True)
        elif fid in {"HIDDEN_01", "HIDDEN_02"}:
            r["native_procedure"] = [step("load", "NATIVE_CONSTRUCT_AND_VALIDATE_REQUESTED_STATE"), step("project", "NATIVE_KNOWLEDGE_PROJECTION", compare_requested_projection=True)]
        elif fid == "MICRO_STACK": fix_stack(r)
        elif fid == "MICRO_REPLACEMENT": fix_replacement(r)
        elif fid == "WS05-MP-COMBAT-4": fix_combat(r)
        elif fid in {"RNG_RULES_TAPE", "REPLAY_DECISION_TAPE", "REPLAY_EVENT_TAPE", "REPLAY_CLEAN_PROCESS", "REPLAY_STATE_HASHES"}: fix_replay(r)
        elif fid == "CARD_02": fix_card02(r)
        changed.add(fid)

    for fid in KNOWN_ADDITIONAL:
        fix_known_additional(table[fid]); changed.add(fid)

    for record in records:
        old_digest = record.pop("materialization_digest")
        record["supersedes_record_digest"] = old_digest
        record["materialization_digest"] = canonical_sha(record)

    corpus.pop("canonical_bundle_digest")
    corpus["canonical_bundle_digest"] = canonical_sha(corpus)
    schema = update_schema(load(MAT / "SEMANTIC_FIXTURE_SCHEMA_v1.json"))
    starter_source = load(MAT / "DIFFERENTIAL_STARTER_18.json")
    union_source = load(MAT / "KNOWN_PASS_UNION_50.json")
    starter = {
        **{k: v for k, v in starter_source.items() if k != "records"},
        "schema_version": "finalist-convergence-differential-starter-18/1.0.1",
        "records": [copy.deepcopy(table[fid]) for fid in starter_source["fixture_ids"]],
    }
    union = {
        **{k: v for k, v in union_source.items() if k != "records"},
        "schema_version": "finalist-convergence-known-pass-union-50/1.0.1",
        "records": [copy.deepcopy(table[fid]) for fid in union_source["fixture_ids"]],
    }
    supersedes = {
        "schema_version": "commander-lab.semantic-fixture-supersession/1.0.1",
        "old_version": OLD_VERSION, "new_version": VERSION,
        "old_bundle_digest": OLD_BUNDLE, "new_bundle_digest": corpus["canonical_bundle_digest"],
        "old_raw_sha256": OLD_RAW, "new_raw_sha256": None,
        "changed_fixture_ids": sorted(changed),
        "defect_classification": "SEMANTIC_EXECUTABILITY_DEFECT",
        "precise_correction": "Added explicit execution entry, native causal procedures, complete cast/target/mana/combat/pregame/RNG construction, commander-incarnation uniqueness, and requested-versus-native equality gate.",
        "frozen_common_obligation_unchanged": {
            "fixture_count": len(records), "unique_fixture_ids": len({r['fixture_id'] for r in records}),
            "common_manifest_sha256": COMMON_SHA,
            "af_mapping": "INHERIT_BY_REFERENCE_NO_REDEFINITION",
            "ws29_card_expected_semantics": "PRESERVED_CARD_01_29",
        },
        "authority_binding": {"ws31_head": WS31_HEAD, "ws31_aggregate": WS31_AGGREGATE},
    }
    outputs = {
        "SEMANTIC_FIXTURE_SCHEMA_v1_0_1.json": schema,
        "SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_1.json": corpus,
        "DIFFERENTIAL_STARTER_18_v1_0_1.json": starter,
        "KNOWN_PASS_UNION_50_v1_0_1.json": union,
    }
    for name, value in outputs.items():
        write_json(OUT / name, value)
    supersedes["new_raw_sha256"] = raw_sha(OUT / "SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_1.json")
    write_json(OUT / "SUPERSEDES_v1_0_0.json", supersedes)
    names = list(outputs) + ["SUPERSEDES_v1_0_0.json"]
    (OUT / "SHA256SUMS").write_bytes(("\n".join(f"{raw_sha(OUT / name)}  {name}" for name in names) + "\n").encode())
    print(json.dumps({
        "status": "BUILT", "record_count": len(records),
        "unique_ids": len({r['fixture_id'] for r in records}),
        "family_counts": Counter(r["fixture_family"] for r in records),
        "bundle_digest": corpus["canonical_bundle_digest"],
        "raw_sha256": supersedes["new_raw_sha256"], "changed_fixture_count": len(changed),
    }, default=dict, indent=2))


if __name__ == "__main__":
    main()
