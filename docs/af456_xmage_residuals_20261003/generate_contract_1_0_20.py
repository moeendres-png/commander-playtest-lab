"""Generate FULL107 successor contract 1.0.20 from 1.0.19: the #456 residual errata.

Ten denominator records request a state no legal game reaches, or name a
decision in their required events that their own script never makes. Each gets
one erratum; no obligation key (expected events, terminal postconditions) is
touched except MICRO_CONTINUOUS_EFFECTS's measured value (below), so every
other recomputed obligation digest equals its predecessor's.

* FIXTURE_SCRIPT_CONTRACT_ERRATUM (explicit decisions): MICRO_COPY's copier
  keeps the copy's targets (CR 707.10c); MICRO_RULES_RANDOMNESS's caster calls
  the flip (CR 705.2) whose result stays the Rules RNG's.
* FIXTURE_SCRIPT_CONTRACT_ERRATUM (explicit cast): WS05-MP-TRIG-5 names the
  entering creature's cast only in native_procedure prose; WS05-MP-PRIO-3/5
  require a response on the stack (``response_on_stack``) that no scripted step
  casts. Each script gains the cast its sibling record already scripts
  (WS05-MP-TRIG-3, MICRO_PRIORITY), with the record's own declared payment
  sources.
* FIXTURE_DEFECT CR 302.6: a permanent of a player who has had no turn in the
  game cannot have been controlled continuously since its controller's most
  recent turn began (MICRO_PRIORITY, MICRO_STACK, MICRO_PREVENTION).
* FIXTURE_DEFECT CR 508.1f: an attacking creature without vigilance is tapped
  once declared (PILOT_DECLARE_BLOCKER, WS05-MP-BLOCK-4, MICRO_PREVENTION,
  MICRO_REPLACEMENT).
* FIXTURE_DEFECT CR 510.1-510.3: no player has priority in the combat damage
  step before its damage is dealt; MICRO_REPLACEMENT's checkpoint becomes the
  active player's priority in the declare blockers step, after which the
  obligation's damage step runs.
* FIXTURE_OBLIGATION_ERRATUM CR 103.8a (MICRO_CONTINUOUS_EFFECTS, the CARD_16
  precedent): in a four-player game P1 holds the opening seven and its turn-1
  draw besides the five named cards, and the Crawler's trigger on that draw
  costs each opponent 1 life; the Crawler's P/T is restated at that hand
  (13/13). This is the one obligation change in 1.0.20.

Idempotent: always regenerated from the 1.0.19 bytes.
"""

import copy
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(sys.argv[1])
sys.path.insert(0, str(REPO / "scripts"))
import resolve_pre_freeze_contract as resolver  # noqa: E402

PRE = REPO / "qualification/pre-freeze-successor"
src = PRE / "FULL107_SUCCESSOR_CONTRACT_v1_0_19.json"
dst = PRE / "FULL107_SUCCESSOR_CONTRACT_v1_0_20.json"
CHANNEL_POLICY = (
    "Current candidate-neutral qualification-boundary actor-aware observation applies to "
    "prompts, context, options, source/ability/pile metadata, events, transcripts and logs."
)
OVERLAY = {
    "comprehensive_rules_effective_date": "2026-09-25",
    "comprehensive_rules_rule": "fixture-contract successor rule: #456 residual errata",
    "historical_rsp": "commander-lab.rules-service/1.1.0",
    "qualification_boundary": "commander-lab.pre-freeze-qualification/2.0.0",
    "transport_protocol": "2.0.0",
}
DIGEST_MIGRATION = {
    "obligation_digest": "UNCHANGED_OBLIGATION_KEYS_UNTOUCHED",
    "predecessor_non_requested_digests": "HISTORICAL_PROVENANCE_ONLY",
    "successor_non_requested_digest_policy": (
        "REMOVE_STALE_VALUES_AND_PRESERVE_UNDER_historical_digests"
    ),
}
FORBIDDEN = [
    "first_option",
    "random_option",
    "default_yes_no",
    "internal_ai",
    "gui_default",
    "silent_skip",
    "parent_class_fallback",
]

raw = src.read_bytes()
contract = json.loads(raw)
authority = json.loads((REPO / "qualification/CURRENT_PRE_FREEZE_CONTRACT.json").read_text())
base = {
    r["fixture_id"]: r
    for r in json.loads(
        (REPO / authority["full107"]["historical_base_materialization"]).read_text()
    )["records"]
}


def _step(actor: str, step_id: str, family: str, selector: str, value: object) -> dict:
    return {
        "actor": actor,
        "causal_step_id": step_id,
        "decision_family": family,
        "forbidden_fallbacks": list(FORBIDDEN),
        "notes": "",
        "selection": {
            "matches_only_provider_offered_legal_options": True,
            "on_multiple_match": "FAIL_CLOSED",
            "on_zero_match": "FAIL_CLOSED",
            "selector_kind": selector,
            "semantic_value": value,
        },
    }


def _cost(actor: str, identity: str, source: str, sources: list[str], mana: int) -> dict:
    return {
        "actor": actor,
        "card_identity": identity,
        "decision_index": 0,
        "evidence_basis": "EXPLICIT_NATIVE_RESOURCE_STATE",
        "explicit_payment_sources": sources,
        "minimum_mana_or_equivalent": mana,
        "payable": True,
        "source_semantic_id": source,
    }


def _erratum_step(fixture: str, slug: str, details: dict) -> dict:
    return {
        "actor": None,
        "details": {"obligation_changed": False, "provider_semantics_used": False, **details},
        "operation": "FIXTURE_ERRATUM_RECORDED_BY_SUCCESSOR_CONTRACT",
        "source_object": None,
        "step_id": f"erratum-{slug}-{fixture.lower()}",
    }


def _objects_with(old: dict, changes: dict[str, dict]) -> list[dict]:
    objects = copy.deepcopy(old["semantic_objects"])
    found = set()
    for obj in objects:
        change = changes.get(obj["semantic_id"])
        if change is None:
            continue
        for key, (before, after) in change.items():
            assert obj.get(key) == before, (
                old["fixture_id"],
                obj["semantic_id"],
                key,
                obj.get(key),
            )
            obj[key] = after
        found.add(obj["semantic_id"])
    assert found == set(changes), (old["fixture_id"], set(changes) - found)
    return objects


def _corrected(changes: dict[str, dict], key: str) -> dict:
    return {
        semantic: {"predecessor": change[key][0], "successor": change[key][1]}
        for semantic, change in changes.items()
        if key in change
    }


CR302_6 = (
    "a permanent of a player who has had no turn in this game cannot have been controlled "
    "continuously since its controller's most recent turn began (CR 302.6); the request is "
    "corrected to the only reachable value. The obligation never depends on it: a land's mana "
    "ability is not limited by summoning sickness"
)
CR508_1F = (
    "declaring an attacker taps it unless it has vigilance (CR 508.1f); the requested combat "
    "declares this creature as an attacker, so at a checkpoint after the declaration it is "
    "tapped. The request is corrected to the only reachable value"
)

patches: list[dict] = []


def add(
    fixture: str,
    correction_class: str,
    replace: dict,
    errata: list[dict],
    invalidity: dict,
    reason: str,
    append: list[dict] | None = None,
    obligation_changed: bool = False,
) -> None:
    old = base[fixture]
    assert not any(p["fixture_id"] == fixture for p in contract["record_successors"]), fixture
    record = copy.deepcopy(old)
    for key, value in replace.items():
        record[key] = copy.deepcopy(value)
    record["knowledge_state"]["channel_policy"] = CHANNEL_POLICY
    patch = {
        "append_native_procedure": [*(append or []), *errata],
        "authority_overlay": dict(OVERLAY),
        "correction_class": correction_class,
        "digest_migration": {
            **DIGEST_MIGRATION,
            **({"obligation_digest": "CHANGED_OBLIGATION_ERRATUM"} if obligation_changed else {}),
            "reason": reason,
        },
        "evidence_survival": "REQUALIFICATION_REQUIRED",
        "fixture_id": fixture,
        "knowledge_state_channel_policy": CHANNEL_POLICY,
        "predecessor_invalidity": invalidity,
        "predecessor_requested_state_digest": old["requested_state_digest"],
        "replace": replace,
        "successor_requested_state_digest": resolver.requested_state_digest(record),
    }
    if obligation_changed:
        assert resolver.obligation_digest(record) != old["obligation_digest"], fixture
    else:
        assert resolver.obligation_digest(record) == old["obligation_digest"], fixture
    patches.append(patch)


# --- explicit casts --------------------------------------------------------- #

old = base["WS05-MP-TRIG-5"]
assert old["decision_script"] == [] and old["action_cost_state"] == []
trig3 = base["WS05-MP-TRIG-3"]
assert trig3["decision_script"][0]["selection"]["semantic_value"] == {
    "action": "cast",
    "object": "obj:mp-enter",
}
add(
    "WS05-MP-TRIG-5",
    "FIXTURE_SCRIPT_CONTRACT_ERRATUM",
    {
        "decision_script": [
            _step(
                "P1",
                "cast-creature",
                "priority",
                "semantic_action",
                {"action": "cast", "object": "obj:mp-enter"},
            )
        ],
        "action_cost_state": [
            _cost(
                "P1",
                "Grizzly Bears",
                "obj:mp-enter",
                ["obj:ws05-trig5-cast-0", "obj:ws05-trig5-cast-1"],
                2,
            )
        ],
    },
    [
        _erratum_step(
            "WS05-MP-TRIG-5",
            "open-cast",
            {
                "erratum_class": "FIXTURE_SCRIPT_EXPLICIT_OPENING_CAST",
                "prose_derived_action_injection": False,
                "reason": (
                    "the predecessor decision_script was empty while native_procedure prose "
                    "(cast-enter) named P1's cast of the entering Grizzly Bears that causes the "
                    "simultaneous Soul Warden triggers; the successor scripts that cast through "
                    "the engine-authored legal-action domain exactly as the three-player sibling "
                    "WS05-MP-TRIG-3 does, paid from the record's two declared Forests"
                ),
            },
        )
    ],
    {
        "decision_script": [],
        "reason": (
            "nothing in the predecessor's script causes the creature to enter, so no trigger "
            "event exists; the harness would have had to derive the cast from native_procedure "
            "prose, a forbidden hidden legality source"
        ),
    },
    "Only the decision script and the declared payment sources change.",
)

for fixture, responder, target, forest in (
    ("WS05-MP-PRIO-3", "P3", "obj:P3-bears", "obj:ws05-prio3-green-0"),
    ("WS05-MP-PRIO-5", "P5", "obj:P5-bears", "obj:ws05-prio5-green-0"),
):
    old = base[fixture]
    assert old["decision_script"] == [], fixture
    (response,) = [o for o in old["semantic_objects"] if o["semantic_id"] == "obj:mp-response"]
    assert response["owner"] == responder and response["zone"] == "hand", fixture
    add(
        fixture,
        "FIXTURE_SCRIPT_CONTRACT_ERRATUM",
        {
            "decision_script": [
                _step(
                    responder,
                    "cast-response",
                    "priority",
                    "semantic_action",
                    {"action": "cast", "object": "obj:mp-response"},
                ),
                _step(responder, "cast-response", "target", "semantic_object", target),
            ],
            "action_cost_state": [_cost(responder, "Giant Growth", "obj:mp-response", [forest], 1)],
        },
        [
            _erratum_step(
                fixture,
                "response-cast",
                {
                    "erratum_class": "FIXTURE_SCRIPT_EXPLICIT_RESPONSE_CAST",
                    "prose_derived_action_injection": False,
                    "reason": (
                        f"the record requires a response on the stack (response_on_stack) and "
                        f"a pass count reset by a player action, and it gives {responder} "
                        f"Giant Growth, a Forest and the Bolt's target; its script made no "
                        f"step, so every player passed and the response could never occur. "
                        f"The successor scripts {responder}'s cast of Giant Growth on the "
                        f"Bolt's target, through the engine-authored legal-action domain, as "
                        f"MICRO_PRIORITY scripts the same response"
                    ),
                },
            )
        ],
        {
            "decision_script": [],
            "reason": (
                "the required response has no scripted cause; a harness-chosen response would "
                "be an action the record never made"
            ),
        },
        "Only the decision script and the declared payment sources change.",
    )

# --- control history (CR 302.6) and attack taps (CR 508.1f) ------------------- #

for fixture, changes in (
    ("MICRO_PRIORITY", {"obj:micro-forest": {"controlled_since_turn_began": (True, False)}}),
    ("MICRO_STACK", {"obj:micro-forest": {"controlled_since_turn_began": (True, False)}}),
):
    add(
        fixture,
        "FIXTURE_DEFECT_CORRECTION_CR302_6",
        {"semantic_objects": _objects_with(base[fixture], changes)},
        [
            _erratum_step(
                fixture,
                "control-history",
                {
                    "comprehensive_rules": "302.6",
                    "erratum_class": "FIXTURE_DEFECT_CR_302_6",
                    "corrected_objects": _corrected(changes, "controlled_since_turn_began"),
                    "reason": "P2 has had no turn in this game (P1 is active on turn 1): "
                    + CR302_6,
                },
            )
        ],
        {
            "controlled_since_turn_began": {
                k: v["controlled_since_turn_began"][0] for k, v in changes.items()
            },
            "reason": "the request is unreachable on P1's turn 1 for a permanent P2 controls",
        },
        "Only one permanent's control-history request changes.",
    )

prevention = {
    "obj:fog-forest-1": {"controlled_since_turn_began": (True, False)},
    "obj:micro-attacker": {"tapped": (False, True)},
}
add(
    "MICRO_PREVENTION",
    "FIXTURE_DEFECT_CORRECTION_CR302_6_CR508_1F",
    {"semantic_objects": _objects_with(base["MICRO_PREVENTION"], prevention)},
    [
        _erratum_step(
            "MICRO_PREVENTION",
            "control-history",
            {
                "comprehensive_rules": "302.6",
                "erratum_class": "FIXTURE_DEFECT_CR_302_6",
                "corrected_objects": _corrected(prevention, "controlled_since_turn_began"),
                "reason": "P2 has had no turn in this game (P1 is active on turn 1): " + CR302_6,
            },
        ),
        _erratum_step(
            "MICRO_PREVENTION",
            "attack-tap",
            {
                "comprehensive_rules": "508.1f",
                "erratum_class": "FIXTURE_DEFECT_CR_508_1F",
                "corrected_objects": _corrected(prevention, "tapped"),
                "reason": "the checkpoint is P2's priority in the declare attackers step: "
                + CR508_1F,
            },
        ),
    ],
    {
        "controlled_since_turn_began": {"obj:fog-forest-1": True},
        "tapped": {"obj:micro-attacker": False},
        "reason": "both requests are unreachable after P1 declared its attack on turn 1",
    },
    "Only two permanents' tapped and control-history requests change.",
)

for fixture, attackers in (
    ("PILOT_DECLARE_BLOCKER", ["obj:p1-bears"]),
    ("WS05-MP-BLOCK-4", ["obj:mp-a2", "obj:mp-a3"]),
):
    old = base[fixture]
    assert sorted(old["combat_state"]["attackers"]) == sorted(attackers), fixture
    changes = {semantic: {"tapped": (False, True)} for semantic in attackers}
    replace: dict = {"semantic_objects": _objects_with(old, changes)}
    errata = [
        _erratum_step(
            fixture,
            "attack-tap",
            {
                "comprehensive_rules": "508.1f",
                "erratum_class": "FIXTURE_DEFECT_CR_508_1F",
                "corrected_objects": _corrected(changes, "tapped"),
                "reason": "the checkpoint is the declare blockers step: " + CR508_1F,
            },
        )
    ]
    invalidity: dict = {
        "tapped": dict.fromkeys(attackers, False),
        "reason": "an attacker without vigilance is never untapped after its declaration",
    }
    correction = "FIXTURE_DEFECT_CORRECTION_CR508_1F"
    reason = "Only the attacking creatures' tapped requests change."
    if fixture == "WS05-MP-BLOCK-4":
        # The requested combat attacks P2 and P3, so both are defending players
        # and the engine asks each in turn (CR 509.1); the record scripts only
        # P2's block. P3's declaration is part of the same turn-based action
        # and cannot be left to the harness.
        assert [s["actor"] for s in old["decision_script"]] == ["P2"]
        replace["decision_script"] = [
            *copy.deepcopy(old["decision_script"]),
            _step("P3", "declare-p3", "declare_blocker", "blocker_assignment", {}),
        ]
        errata.append(
            _erratum_step(
                fixture,
                "second-defender",
                {
                    "comprehensive_rules": "509.1",
                    "erratum_class": "FIXTURE_SCRIPT_EXPLICIT_DEFENDER_DECLARATION",
                    "prose_derived_action_injection": False,
                    "reason": (
                        "the requested combat attacks P2 (obj:mp-a2) and P3 (obj:mp-a3), so "
                        "both are defending players and each declares blockers in the "
                        "declare blockers step (CR 509.1); the predecessor scripted only P2. "
                        "The successor states P3's declaration explicitly: P3 blocks nothing "
                        "(the record names only P2's blockers as eligible). P2's obligation "
                        "is untouched"
                    ),
                },
            )
        )
        invalidity["decision_script_defenders"] = ["P2"]
        correction = "FIXTURE_DEFECT_CORRECTION_CR508_1F_SCRIPT_CONTRACT"
        reason = "The attackers' tapped requests change and P3's block declaration is scripted."
    add(fixture, correction, replace, errata, invalidity, reason)

# --- MICRO_REPLACEMENT: the damage-step checkpoint (CR 510) ------------------- #

old = base["MICRO_REPLACEMENT"]
assert old["temporal_state"]["step"] == "combat_damage"
temporal = {**old["temporal_state"], "step": "declare_blockers"}
replacement = {"obj:micro-3power": {"tapped": (False, True)}}
add(
    "MICRO_REPLACEMENT",
    "FIXTURE_DEFECT_CORRECTION_CR510_CR508_1F",
    {
        "temporal_state": temporal,
        "semantic_objects": _objects_with(old, replacement),
    },
    [
        _erratum_step(
            "MICRO_REPLACEMENT",
            "damage-step-checkpoint",
            {
                "comprehensive_rules": "510.1-510.3",
                "erratum_class": "FIXTURE_DEFECT_CR_510",
                "predecessor_step": "combat_damage",
                "successor_step": "declare_blockers",
                "reason": (
                    "the predecessor asked for P1's priority in the combat damage step before "
                    "the damage it then requires; combat damage is assigned and dealt as the "
                    "step begins and players receive priority only afterwards (CR 510.1-510.3), "
                    "so that state does not exist. The successor's checkpoint is P1's priority "
                    "in the declare blockers step (no blocks, as the requested combat states); "
                    "the obligation's own native step (resume-combat) then enters the combat "
                    "damage step, where the doubled damage is dealt"
                ),
            },
        ),
        _erratum_step(
            "MICRO_REPLACEMENT",
            "attack-tap",
            {
                "comprehensive_rules": "508.1f",
                "erratum_class": "FIXTURE_DEFECT_CR_508_1F",
                "corrected_objects": _corrected(replacement, "tapped"),
                "reason": "the checkpoint is the declare blockers step: " + CR508_1F,
            },
        ),
    ],
    {
        "temporal_state": old["temporal_state"],
        "tapped": {"obj:micro-3power": False},
        "reason": "no legal game holds priority in the combat damage step before its damage",
    },
    "The checkpoint step and the attacker's tapped request change.",
)

# --- copier and coin-call decisions the records never script ----------------- #

for fixture, step_id, value, erratum_class, reason, invalid in (
    (
        "MICRO_COPY",
        "copy-targets",
        False,
        "FIXTURE_SCRIPT_EXPLICIT_COPY_TARGET_CHOICE",
        (
            "Flare of Duplication's copy may have new targets chosen by its controller (CR "
            "707.10c); the engine asks P1 that question when the Flare resolves, and the "
            "predecessor scripted no answer, so the obligation could never be reached. The "
            "successor answers it explicitly: the copy keeps the copied Bolt's target, as "
            "the record's own postcondition requires a copy with the copied characteristics"
        ),
        "the copier's optional new-target decision has no scripted answer",
    ),
    (
        "MICRO_RULES_RANDOMNESS",
        "coin-call",
        True,
        "FIXTURE_SCRIPT_EXPLICIT_COIN_CALL",
        (
            "Stitch in Time's flip is won or lost (CR 705.2): the engine asks P1 to call it "
            "before the Rules RNG flips. The record predetermines the flip's result (HEADS) "
            "and that winning it creates the extra turn, but scripted no call, so the "
            "obligation could never be reached. The successor scripts P1's call of heads. "
            "The flip itself stays the Rules RNG's, under the record's own seed; the harness "
            "never sets it"
        ),
        "the caster's call of the coin flip has no scripted answer",
    ),
):
    old = base[fixture]
    assert old["decision_script"] == [], fixture
    add(
        fixture,
        "FIXTURE_SCRIPT_CONTRACT_ERRATUM",
        {"decision_script": [_step("P1", step_id, "choice", "boolean", value)]},
        [
            _erratum_step(
                fixture,
                step_id,
                {
                    "erratum_class": erratum_class,
                    "prose_derived_action_injection": False,
                    "reason": reason,
                },
            )
        ],
        {"decision_script": [], "reason": invalid},
        "Only the decision script changes.",
    )

# --- MICRO_CONTINUOUS_EFFECTS: the natural arrival (CR 103.8a) --------------- #

old = base["MICRO_CONTINUOUS_EFFECTS"]
players = copy.deepcopy(old["players"])
for player in players:
    if player["player_id"] != "P1":
        assert player["life"] == 40
        player["life"] = 39
assert old["expected_events"]["required_events"] == ["continuous_pt_evaluated:5/5"]
expected_events = copy.deepcopy(old["expected_events"])
expected_events["required_events"] = ["continuous_pt_evaluated:13/13"]
postconditions = [
    "Psychosis Crawler power/toughness are 13/13 from current P1 hand size (13 cards: the "
    "opening seven, the turn-1 draw and the five named Mountains) without a trigger."
]
add(
    "MICRO_CONTINUOUS_EFFECTS",
    "FIXTURE_OBLIGATION_ERRATUM_CR103_8A",
    {
        "players": players,
        "expected_events": expected_events,
        "terminal_postconditions": postconditions,
    },
    [
        _erratum_step(
            "MICRO_CONTINUOUS_EFFECTS",
            "natural-arrival",
            {
                "comprehensive_rules": "103.5, 103.8a, 504.1, 603.2, 604.3",
                "erratum_class": "FIXTURE_OBLIGATION_ERRATUM_CR_103_8A",
                "obligation_changed": True,
                "precedent": "CARD_16 ACTUAL_CARD_OBLIGATION_ERRATUM (same card, same arrival)",
                "corrected_life": {"P2": [40, 39], "P3": [40, 39], "P4": [40, 39]},
                "corrected_required_events": {
                    "predecessor": ["continuous_pt_evaluated:5/5"],
                    "successor": ["continuous_pt_evaluated:13/13"],
                },
                "predecessor_obligation_digest": old["obligation_digest"],
                "reason": (
                    "the predecessor measures the Crawler at a five-card hand with the "
                    "opponents at 40 on P1's turn-1 precombat main in a four-player game. The "
                    "construction plays the real start of the game and turn 1: P1 holds the "
                    "opening seven plus the turn-1 draw (CR 103.5; CR 103.8a exempts only a "
                    "two-player game) besides the five named Mountains, 13 cards; and the "
                    "Crawler, on the battlefield since the turn began, sees that draw, so each "
                    "opponent is at 39 (caused and compared, never set). A five-card hand needs "
                    "a Lab-side hand mutation (forbidden by SLOT-04 L7). The mechanism under "
                    "test is unchanged: the Crawler's characteristic-defining power and "
                    "toughness (CR 604.3) equal P1's hand size, evaluated continuously without "
                    "a trigger; only the measured value is restated at the reachable hand"
                ),
            },
        )
    ],
    {
        "players_life": {"P2": 40, "P3": 40, "P4": 40},
        "predecessor_required_events": ["continuous_pt_evaluated:5/5"],
        "predecessor_terminal_postconditions": old["terminal_postconditions"],
        "reason": (
            "a five-card hand and untouched opponents are unreachable at P1's turn-1 main "
            "phase in a four-player game with the Crawler in play"
        ),
    },
    (
        "The opponents' caused life, the required event and the postcondition change, so the "
        "requested-state, obligation and materialization digests all change; the predecessor "
        "obligation digest is preserved under historical_digests and in this erratum's details"
    ),
    obligation_changed=True,
)

contract["record_successors"].extend(patches)
accounting = contract["change_accounting"]
for patch in patches:
    accounting["changed_fixture_ids"].append(patch["fixture_id"])
    accounting["per_fixture_correction_class"][patch["fixture_id"]] = patch["correction_class"]
accounting["changed_fixture_count"] = len(accounting["changed_fixture_ids"])
accounting["unchanged_provider_denominator_rows"] -= len(patches)
contract["contract_id"] = "commander-lab.full107/1.0.20-successor"
contract["effective_materialization_version"] = (
    "commander-lab.semantic-fixture-materialization/1.0.20-successor"
)
contract["materialization_schema_version_note"] = (
    "the record shape is unchanged from the 1.0.8 successor schema; 1.0.20 adds the #456 "
    "residual errata (explicit casts for WS05-MP-TRIG-5/PRIO-3/PRIO-5; CR 302.6, 508.1f, "
    "510 fixture-defect corrections for MICRO_PRIORITY, MICRO_STACK, MICRO_PREVENTION, "
    "PILOT_DECLARE_BLOCKER, WS05-MP-BLOCK-4 and MICRO_REPLACEMENT; the CR 103.8a obligation "
    "erratum of MICRO_CONTINUOUS_EFFECTS) while preserving every 1.0.19 overlay "
    "byte-semantically"
)
contract["predecessor"] = {
    "path": "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_19.json",
    "record_count": len(json.loads(raw)["record_successors"]),
    "role": (
        "historical successor overlays are preserved; this contract re-applies every current "
        "overlay to the same 1.0.5 historical base and adds the #456 residual errata"
    ),
    "schema_version": json.loads(raw)["predecessor"]["schema_version"],
    "sha256": hashlib.sha256(raw).hexdigest(),
}
dst.write_text(json.dumps(contract, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

schema_src = PRE / "SEMANTIC_FIXTURE_SCHEMA_v1_0_19_SUCCESSOR.json"
schema_text = schema_src.read_text(encoding="utf-8")
schema = json.loads(schema_text)
schema["title"] = schema["title"].replace("1.0.19", "1.0.20")
schema["$id"] = schema["$id"].replace("1.0.19", "1.0.20")
enum = schema["$defs"]["record"]["properties"]["materialization_version"]["enum"]
if "commander-lab.semantic-fixture-materialization/1.0.20-successor" not in enum:
    enum.append("commander-lab.semantic-fixture-materialization/1.0.20-successor")
schema["properties"]["contract_id"]["const"] = "commander-lab.full107/1.0.20-successor"
schema["properties"]["schema_version"]["const"] = (
    "commander-lab.semantic-fixture-materialization/1.0.20-successor"
)
indent = 2 if schema_text.startswith('{\n  "') else 1
(PRE / "SEMANTIC_FIXTURE_SCHEMA_v1_0_20_SUCCESSOR.json").write_text(
    json.dumps(schema, indent=indent, ensure_ascii=False) + "\n", encoding="utf-8"
)

apath = REPO / "qualification/CURRENT_PRE_FREEZE_CONTRACT.json"
auth = json.loads(apath.read_text())
full = auth["full107"]
full["successor_contract"] = (
    "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_20.json"
)
full["effective_materialization_schema"] = (
    "qualification/pre-freeze-successor/SEMANTIC_FIXTURE_SCHEMA_v1_0_20_SUCCESSOR.json"
)
for patch in patches:
    fixture = patch["fixture_id"]
    if fixture not in full["changed_fixture_ids"]:
        full["changed_fixture_ids"].append(fixture)
        full["unchanged_fixture_count"] -= 1
    full["evidence_survival"][fixture] = "REQUALIFICATION_REQUIRED_" + patch["correction_class"]
apath.write_text(json.dumps(auth, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("wrote", dst.name, "records", len(contract["record_successors"]))
