"""Generate FULL107 successor contract 1.0.21 from 1.0.20: the #441 Claude-lane errata.

The Owner delegated the contract authority for these errata (#441). Each one is
versioned, digest-bound and lineage-preserving; no historical PASS transfers
(every changed row is REQUALIFICATION_REQUIRED, and none of them was PASS).
The decisions are recorded on #441 (comment 5984201192), decided by CR text.

* E1 LOSSLESS_LIBRARY_MATERIALIZATION_ERRATUM_SLOT04: PILOT_CHOOSE_USE and
  NEGATIVE_DEFAULT_YES_NO name a known library top card but declare no complete
  library or hand, which SLOT-04 L7 refuses on every candidate.
* E2 (a) PILOT_CHOOSE_USE: for scry 1 the provider's 0..1 card selection is the
  yes/no question of CR 701.22a (false <-> the empty selection). Recorded as an
  adjudication; no record field changes beyond E1.
* E2 (b) NEGATIVE_DEFAULT_YES_NO: a card-selection frame has no yes/no default
  to forbid, so the scenario becomes a genuine optional trigger (Garruk's
  Packleader, "you may draw a card", caused by a scripted Centaur Courser cast).
  The obligation keys are untouched.
* E3 PILOT_PILE: Fact or Fiction on the stack with its five cards already
  revealed is no state any game reaches; the five cards are the library top
  five and P1 casts Fact or Fiction through the causal stack, and P1's pile
  choice is scripted.
* WS05-MP-TURN-3/5 (CR 614.6, CR 500.7, CR 508.1): a resolved Nexus of Fate is
  never in a graveyard, and an extra turn's creation is no state but an event;
  both spells are cast through the causal stack, every combat before the
  observation point declares no attackers, and each cleanup discard is scripted.
* WS05-CMD-MULL-2/4 (CR 103.5): each round-1 mulligan gets its round-2 keep and
  London bottom selection; the deck shape gets the library template.
* RNG_RULES_TAPE (CR 701.24): the only P1 shuffle had no Rules consequence; P1
  casts Chaos Warp after Burn Down the House, so a card-caused shuffle of
  distinguishable cards decides the revealed card. Supersedes the 1.0.19
  SLOT-04 patch of the same fixture, which it keeps as lineage.
* MICRO_LAYERS (CR 613): the layer tokens are characteristic readbacks, not
  events, and a vanilla 2/2 cannot discriminate them; P2's creature becomes
  Serra Angel (4/4 flying, vigilance).

Idempotent: always regenerated from the 1.0.20 bytes.
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
src = PRE / "FULL107_SUCCESSOR_CONTRACT_v1_0_20.json"
dst = PRE / "FULL107_SUCCESSOR_CONTRACT_v1_0_21.json"
DECISIONS = "#441 comment 5984201192 (Owner-delegated contract authority, decided by CR text)"
CHANNEL_POLICY = (
    "Current candidate-neutral qualification-boundary actor-aware observation applies to "
    "prompts, context, options, source/ability/pile metadata, events, transcripts and logs."
)
OVERLAY = {
    "comprehensive_rules_effective_date": "2026-09-25",
    "comprehensive_rules_rule": "fixture-contract successor rule: #441 Claude-lane errata",
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
existing = {p["fixture_id"]: p for p in contract["record_successors"]}
(card12,) = [p for p in contract["record_successors"] if p["fixture_id"] == "CARD_12"]
SLOT04_AUTHORITY = card12["append_native_procedure"][0]["details"]["authority"]
SCAFFOLDING = card12["append_native_procedure"][0]["details"]["scaffolding_template"]


def _step(
    actor: str, step_id: str, family: str, selector: str, value: object, notes: str = ""
) -> dict:
    return {
        "actor": actor,
        "causal_step_id": step_id,
        "decision_family": family,
        "forbidden_fallbacks": list(FORBIDDEN),
        "notes": notes,
        "selection": {
            "matches_only_provider_offered_legal_options": True,
            "on_multiple_match": "FAIL_CLOSED",
            "on_zero_match": "FAIL_CLOSED",
            "selector_kind": selector,
            "semantic_value": value,
        },
    }


def _cost(
    actor: str, identity: str, source: str, sources: list[str], mana: int, index: int = 0
) -> dict:
    return {
        "actor": actor,
        "card_identity": identity,
        "decision_index": index,
        "evidence_basis": "EXPLICIT_NATIVE_RESOURCE_STATE",
        "explicit_payment_sources": sources,
        "minimum_mana_or_equivalent": mana,
        "payable": True,
        "source_semantic_id": source,
    }


def _card(semantic_id: str, identity: str, owner: str, zone: str, **extra: object) -> dict:
    return {
        "card_identity": identity,
        "card_lineage_id": f"line:{semantic_id}",
        "controller": owner,
        "counters": {},
        "face_down": False,
        "owner": owner,
        "semantic_id": semantic_id,
        "tapped": False,
        "zone": zone,
        **extra,
    }


def _erratum_step(fixture: str, slug: str, details: dict) -> dict:
    return {
        "actor": None,
        "details": {
            "authority": DECISIONS,
            "obligation_changed": False,
            "provider_semantics_used": False,
            **details,
        },
        "operation": "FIXTURE_ERRATUM_RECORDED_BY_SUCCESSOR_CONTRACT",
        "source_object": None,
        "step_id": f"erratum-{slug}-{fixture.lower()}",
    }


def _deck(player: str, hand_templates: int, library: list[str] | None = None) -> dict:
    """A lossless SLOT-04 deck entry on the 99-Mountain scaffolding template.

    The hand is complete (``hand_templates`` scaffolding cards plus the record's
    named hand objects); a player whose library names objects gets the complete
    library, the named objects on top in record order, then the template cards
    not in hand (named objects come in addition to the template, as in the
    1.0.19 replay/RNG errata).
    """
    deck = {
        "checkpoint_hand": {
            "completeness": "COMPLETE",
            "template_card_identity": "Mountain",
            "template_count": hand_templates,
        },
        "commander_ids": [f"cmd:{player}-A"],
        "library_template": {"card_identity": "Mountain", "count": 99},
        "opening_hand_size": 7,
        "player_id": player,
        "shuffle_channel": f"library_shuffle:{player}",
    }
    if library:
        deck["checkpoint_library"] = {
            "completeness": "COMPLETE_TOP_TO_BOTTOM",
            "runs": [{"semantic_id": semantic} for semantic in library]
            + [{"card_identity": "Mountain", "count": 99 - hand_templates}],
        }
    return deck


def _pregame_deck(player: str) -> dict:
    return {
        "commander_ids": [f"cmd:{player}-A"],
        "library_template": {"card_identity": "Mountain", "count": 99},
        "opening_hand_size": 7,
        "player_id": player,
        "shuffle_channel": f"library_shuffle:{player}",
    }


def _players(record: dict) -> list[str]:
    return [player["player_id"] for player in record["players"]]


patches: list[dict] = []
superseded: dict[str, dict] = {}


def add(
    fixture: str,
    correction_class: str,
    replace: dict,
    errata: list[dict],
    invalidity: dict,
    reason: str,
    *,
    supersede: bool = False,
) -> None:
    old = base[fixture]
    prior = existing.get(fixture)
    if supersede:
        assert prior is not None, fixture
        superseded[fixture] = prior
    else:
        assert prior is None, fixture
    merged_replace = copy.deepcopy(prior["replace"]) if prior else {}
    merged_replace.update(copy.deepcopy(replace))
    record = copy.deepcopy(old)
    for key, value in merged_replace.items():
        record[key] = copy.deepcopy(value)
    record["knowledge_state"]["channel_policy"] = CHANNEL_POLICY
    # A superseded patch's erratum steps are lineage, never active procedure:
    # they stay under superseded_successor_patch, so no executor reads an
    # instruction the successor replaces.
    appended = list(errata)
    patch = {
        "append_native_procedure": appended,
        "authority_overlay": dict(OVERLAY),
        "correction_class": correction_class,
        "digest_migration": {**DIGEST_MIGRATION, "reason": reason},
        "evidence_survival": "REQUALIFICATION_REQUIRED",
        "fixture_id": fixture,
        "knowledge_state_channel_policy": CHANNEL_POLICY,
        "predecessor_invalidity": invalidity,
        "predecessor_requested_state_digest": old["requested_state_digest"],
        "replace": merged_replace,
        "successor_requested_state_digest": resolver.requested_state_digest(record),
    }
    if prior is not None:
        patch["superseded_successor_patch"] = {
            "contract": "commander-lab.full107/1.0.20-successor",
            "correction_class": prior["correction_class"],
            "patch_sha256": hashlib.sha256(
                resolver.canonical_json(prior).encode("utf-8")
            ).hexdigest(),
            "successor_requested_state_digest": prior["successor_requested_state_digest"],
            "append_native_procedure": copy.deepcopy(prior["append_native_procedure"]),
            "lineage": (
                "its replace is kept and extended; its erratum steps are preserved here as "
                "history and are not active procedure"
            ),
        }
    # No obligation key changes in 1.0.21: every required event and terminal
    # postcondition is the predecessor's, so no historical obligation is restated.
    assert resolver.obligation_digest(record) == old["obligation_digest"], fixture
    assert patch["successor_requested_state_digest"] != old["requested_state_digest"], fixture
    patches.append(patch)


# --- E1 + E2(a): PILOT_CHOOSE_USE ------------------------------------------- #

old = base["PILOT_CHOOSE_USE"]
assert old.get("deck_state") is None
(top,) = [o for o in old["semantic_objects"] if o["zone"] == "library"]
assert top["semantic_id"] == "obj:top-known" and top["zone_position"] == 0
hand = [o["semantic_id"] for o in old["semantic_objects"] if o["zone"] == "hand"]
assert hand == ["obj:path-marauders"], hand
(scry,) = [s for s in old["decision_script"] if s["decision_family"] == "choose_use"]
assert scry["selection"] == {
    **scry["selection"],
    "selector_kind": "boolean",
    "semantic_value": False,
}
add(
    "PILOT_CHOOSE_USE",
    "LOSSLESS_LIBRARY_MATERIALIZATION_ERRATUM_SLOT04",
    {"deck_state": [_deck("P1", 8, ["obj:top-known"]), *(_deck(p, 7) for p in ("P2", "P3", "P4"))]},
    [
        _erratum_step(
            "PILOT_CHOOSE_USE",
            "lossless",
            {
                "slot04_authority": SLOT04_AUTHORITY,
                "erratum_class": "LOSSLESS_LIBRARY_MATERIALIZATION_ERRATUM_SLOT04",
                "complete_checkpoint_hands": {
                    "P1": "obj:path-marauders plus 8 template cards (opening 7 and the turn-1 "
                    "draw, CR 103.8a skips it only in a two-player game)",
                    "P2": "7 template cards",
                    "P3": "7 template cards",
                    "P4": "7 template cards",
                },
                "complete_checkpoint_libraries": {
                    "P1": "obj:top-known on top, then the 91 remaining template cards"
                },
                "scaffolding_template": SCAFFOLDING,
            },
        ),
        _erratum_step(
            "PILOT_CHOOSE_USE",
            "scry-binary",
            {
                "erratum_class": "DECISION_SURFACE_ADJUDICATION_CR_701_22A",
                "comprehensive_rules": "701.22a",
                "adjudication": (
                    "to scry 1 is to look at the top card and choose to put it on the bottom "
                    "or leave it on top (CR 701.22a): one binary choice. A provider that asks "
                    "scry N as a selection of 0..N cards to put on the bottom asks, for N = 1, "
                    "exactly that question. The record's choose_use step (boolean false, "
                    "scry_choice:keep_top) is answered on that frame as the empty selection; "
                    "true would be the selection of the one card. The selection must be the "
                    "provider's own frame for this scry, with exactly the one looked-at card "
                    "offered, or the step fails closed"
                ),
                "decision_family_binding": {
                    "record_family": "choose_use",
                    "provider_surface": "scry 1 card selection (0..1 cards to the bottom)",
                    "false": "empty selection",
                    "true": "the one offered card",
                },
            },
        ),
    ],
    {
        "predecessor_values": {"deck_state": None},
        "reason": (
            "the record names P1's library top card but declares no complete library or "
            "hand; under SLOT-04 L7 a partial library request fails closed on every candidate"
        ),
    },
    "Only deck_state changes; the scry binding is an adjudication, not a field change.",
)

# --- E1 + E2(b): NEGATIVE_DEFAULT_YES_NO ------------------------------------ #

old = base["NEGATIVE_DEFAULT_YES_NO"]
assert old.get("deck_state") is None
ids = [
    o["semantic_id"] for o in old["semantic_objects"] if o["zone"] not in ("command", "battlefield")
]
assert ids == ["obj:neg-top", "obj:neg-opt"], ids
(probe,) = old["decision_script"]
assert probe["decision_family"] == "choose_use"
assert probe["selection"]["selector_kind"] == "fail_closed_probe"
objects = [o for o in copy.deepcopy(old["semantic_objects"]) if o["semantic_id"] != "obj:neg-opt"]
forests = [f"obj:neg-forest-{index}" for index in range(3)]
objects += [
    _card("obj:neg-packleader", "Garruk's Packleader", "P1", "battlefield"),
    _card("obj:neg-courser", "Centaur Courser", "P1", "hand"),
    *(_card(forest, "Forest", "P1", "battlefield") for forest in forests),
]
add(
    "NEGATIVE_DEFAULT_YES_NO",
    "ACTUAL_CARD_SCENARIO_ERRATUM",
    {
        "semantic_objects": objects,
        "stack_state": [],
        "deck_state": [_deck("P1", 8, ["obj:neg-top"]), *(_deck(p, 7) for p in ("P2", "P3", "P4"))],
        "decision_script": [
            _step(
                "P1",
                "cast-courser",
                "priority",
                "semantic_action",
                {"action": "cast", "object": "obj:neg-courser"},
            ),
            _step(
                "P1",
                "cast-courser",
                "mana_payment",
                "mana_payment",
                {"mana": ["G", "G", "G"], "sources": forests},
            ),
            copy.deepcopy(probe),
        ],
        "action_cost_state": [_cost("P1", "Centaur Courser", "obj:neg-courser", forests, 3)],
        "negative_fallback_probe": {
            **old["negative_fallback_probe"],
            "production_reachable_trigger": (
                "P1's Centaur Courser (power 3) enters under P1's control, so P1's Garruk's "
                "Packleader triggers and asks 'you may draw a card': yes versus no."
            ),
        },
    },
    [
        _erratum_step(
            "NEGATIVE_DEFAULT_YES_NO",
            "optional-trigger",
            {
                "erratum_class": "ACTUAL_CARD_SCENARIO_ERRATUM",
                "comprehensive_rules": "603.5, 701.22a",
                "reason": (
                    "the obligation is that an unanswered yes/no decision fails closed instead "
                    "of taking the default_yes_no fallback. The predecessor's cause is Opt's "
                    "scry 1, which a provider may ask as a card selection that has no yes/no "
                    "default to forbid, so the forbidden fallback could not even occur there. "
                    "The successor's cause is a genuine optional trigger (CR 603.5): P1's "
                    "Garruk's Packleader sees P1's Centaur Courser (power 3) enter and asks "
                    "'you may draw a card'. The Courser is cast from hand through the "
                    "engine-offered legal actions, paid from the three declared Forests, so "
                    "the frame is caused, never placed. The probe step is unchanged"
                ),
                "removed_objects": {"obj:neg-opt": "Opt on the stack (no longer the cause)"},
                "complete_checkpoint_hands": {
                    "P1": "obj:neg-courser plus 8 template cards",
                    "P2": "7 template cards",
                    "P3": "7 template cards",
                    "P4": "7 template cards",
                },
                "complete_checkpoint_libraries": {
                    "P1": "obj:neg-top on top, then the 91 remaining template cards"
                },
                "slot04_authority": SLOT04_AUTHORITY,
            },
        )
    ],
    {
        "predecessor_values": {"deck_state": None, "stack_state": old["stack_state"]},
        "reason": (
            "a partial library request (SLOT-04 L7), and a cause whose frame may be a card "
            "selection with no yes/no default, so the obligation's forbidden fallback has no "
            "occasion to be refused"
        ),
    },
    "The objects, the stack, the hands, the script and the payment sources change.",
)

# --- E3: PILOT_PILE ---------------------------------------------------------- #

old = base["PILOT_PILE"]
assert old.get("deck_state") is None
revealed = [o for o in old["semantic_objects"] if o["zone"] == "revealed"]
assert [o["semantic_id"] for o in revealed] == [f"obj:fof-{i}" for i in range(5)]
assert [o["zone_position"] for o in revealed] == list(range(5))
islands = [f"obj:fof-island-{index}" for index in range(4)]
objects = copy.deepcopy(old["semantic_objects"])
for obj in objects:
    if obj["zone"] == "revealed":
        obj["zone"] = "library"
    elif obj["semantic_id"] == "obj:fof":
        assert obj["zone"] == "stack"
        obj["zone"] = "hand"
objects += [_card(island, "Island", "P1", "battlefield") for island in islands]
(partition,) = old["decision_script"]
assert partition["decision_family"] == "pile" and partition["actor"] == "P2"
add(
    "PILOT_PILE",
    "CAUSAL_STACK_SCENARIO_ERRATUM",
    {
        "semantic_objects": objects,
        "stack_state": [],
        "deck_state": [
            _deck("P1", 8, [o["semantic_id"] for o in revealed]),
            *(_deck(p, 7) for p in ("P2", "P3", "P4")),
        ],
        "decision_script": [
            _step(
                "P1",
                "cast-fof",
                "priority",
                "semantic_action",
                {"action": "cast", "object": "obj:fof"},
            ),
            # Fact or Fiction's "an opponent separates": P1 chooses which
            # opponent as it casts (CR 601.2c), as HIDDEN_13 scripts it.
            _step("P1", "cast-fof", "target", "semantic_player", "P2"),
            _step(
                "P1",
                "cast-fof",
                "mana_payment",
                "mana_payment",
                {"mana": ["U", "U", "U", "U"], "sources": islands},
            ),
            copy.deepcopy(partition),
            _step(
                "P1",
                "choose-pile",
                "pile",
                "pile_label",
                "Pile 1",
                notes="pile_a of the partition step; the obligation never depends on the choice",
            ),
        ],
        "action_cost_state": [_cost("P1", "Fact or Fiction", "obj:fof", islands, 4)],
    },
    [
        _erratum_step(
            "PILOT_PILE",
            "causal-stack",
            {
                "erratum_class": "CAUSAL_STACK_SCENARIO_ERRATUM",
                "comprehensive_rules": "608.2c, 701.20",
                "reason": (
                    "the predecessor holds Fact or Fiction on the stack and its five cards "
                    "already in a revealed zone: no game reaches that state, because the cards "
                    "are revealed only as Fact or Fiction resolves, and until then they are the "
                    "top five of P1's library. The successor makes them library positions 0-4 "
                    "of P1's complete library and P1 casts Fact or Fiction from hand, paid by "
                    "four declared Islands; the partition is then the engine's own frame for "
                    "P2, and P1's following pile choice is scripted (the obligation is the "
                    "partition, never the choice)"
                ),
                "partition_binding": (
                    "P2's partition is answered on the provider's own pile-separation frame; a "
                    "provider that asks it as a selection of the first pile receives pile_a"
                ),
                "complete_checkpoint_hands": {
                    "P1": "obj:fof plus 8 template cards",
                    "P2": "7 template cards",
                    "P3": "7 template cards",
                    "P4": "7 template cards",
                },
                "complete_checkpoint_libraries": {
                    "P1": "obj:fof-0..obj:fof-4 on top in that order, then the 91 remaining "
                    "template cards"
                },
                "slot04_authority": SLOT04_AUTHORITY,
            },
        )
    ],
    {
        "predecessor_values": {
            "deck_state": None,
            "stack_state": old["stack_state"],
            "revealed_zone": [o["semantic_id"] for o in revealed],
        },
        "reason": "a state with the spell on the stack and its result already revealed",
    },
    "The objects' zones, the stack, the hands, the library, the script and the payment change.",
)

# --- WS05-MP-TURN-3 / TURN-5 -------------------------------------------------- #

for fixture in ("WS05-MP-TURN-3", "WS05-MP-TURN-5"):
    old = base[fixture]
    players = _players(old)
    assert old["decision_script"] == [] and old.get("deck_state") is None
    assert old["temporal_state"]["phase"] == "postcombat_main"
    assert [e["player"] for e in old["extra_turn_creation"]] == ["P2", "P3"]
    objects = copy.deepcopy(old["semantic_objects"])
    for obj in objects:
        if obj["semantic_id"] == "obj:mp-time-warp":
            assert obj["zone"] == "graveyard" and obj["owner"] == "P1"
            obj["zone"] = "hand"
        elif obj["semantic_id"] == "obj:mp-nexus":
            assert obj["zone"] == "graveyard" and obj["owner"] == "P3"
            obj["zone"] = "hand"
    p1_islands = [f"obj:turn-p1-island-{i}" for i in range(5)]
    p3_islands = [f"obj:turn-p3-island-{i}" for i in range(7)]
    objects += [_card(island, "Island", "P1", "battlefield") for island in p1_islands]
    objects += [_card(island, "Island", "P3", "battlefield") for island in p3_islands]
    # The checkpoint hands are those the game deals: at P1's first precombat
    # main P1 holds its opening seven plus its first draw (no player skips it
    # in a multiplayer game, CR 103.8c) and every other player its opening
    # seven, each besides the record's named spell (the SLOT-04 precedent).
    decks = [_deck(p, 8 if p == "P1" else 7) for p in players]
    # The checkpoint is P1's precombat main: a state at P1's postcombat main
    # must already have passed P1's combat, whose attack declaration (P1's
    # Bears can attack) is a discretionary choice the record never scripts.
    temporal = copy.deepcopy(old["temporal_state"])
    temporal["phase"] = "precombat_main"
    add(
        fixture,
        "CAUSAL_EXTRA_TURN_SCENARIO_ERRATUM",
        {
            "semantic_objects": objects,
            "extra_turn_creation": [],
            "temporal_state": temporal,
            "deck_state": decks,
            "decision_script": [
                _step(
                    "P1",
                    "cast-time-warp",
                    "priority",
                    "semantic_action",
                    {"action": "cast", "object": "obj:mp-time-warp"},
                ),
                _step("P1", "cast-time-warp", "target", "semantic_player", "P2"),
                _step(
                    "P1",
                    "cast-time-warp",
                    "mana_payment",
                    "mana_payment",
                    {"mana": ["U", "U", "U", "U", "U"], "sources": p1_islands},
                ),
                _step(
                    "P3",
                    "cast-nexus",
                    "priority",
                    "semantic_action",
                    {"action": "cast", "object": "obj:mp-nexus", "timing": "empty_stack"},
                ),
                _step(
                    "P3",
                    "cast-nexus",
                    "mana_payment",
                    "mana_payment",
                    {"mana": ["U"] * 7, "sources": p3_islands},
                ),
                _step(
                    "P1",
                    "p1-combat",
                    "declare_attacker",
                    "attacker_assignment",
                    {},
                    notes="CR 508.1: the active player declares no attackers",
                ),
                _step(
                    "P1",
                    "p1-cleanup",
                    "choose_object",
                    "card_identity_multiset",
                    {"Mountain": 1},
                    notes="CR 514.1: P1 ends its turn with eight cards and discards one",
                ),
                _step(
                    "P3",
                    "p3-extra-turn-combat",
                    "declare_attacker",
                    "attacker_assignment",
                    {},
                    notes="CR 508.1: the active player declares no attackers",
                ),
                _step(
                    "P3",
                    "p3-extra-turn-cleanup",
                    "choose_object",
                    "card_identity_multiset",
                    {"Mountain": 1},
                    notes="CR 514.1: P3 ends its extra turn with eight cards and discards one",
                ),
            ],
            "action_cost_state": [
                _cost("P1", "Time Warp", "obj:mp-time-warp", p1_islands, 5),
                _cost("P3", "Nexus of Fate", "obj:mp-nexus", p3_islands, 7, index=1),
            ],
        },
        [
            _erratum_step(
                fixture,
                "causal-extra-turns",
                {
                    "erratum_class": "CAUSAL_EXTRA_TURN_SCENARIO_ERRATUM",
                    "comprehensive_rules": "500.7, 508.1, 514.1, 608.2n, 614.1a, 614.6",
                    "nexus_zone": (
                        "Nexus of Fate: 'If Nexus of Fate would be put into a graveyard from "
                        "anywhere, reveal Nexus of Fate and shuffle it into its owner's library "
                        "instead.' That replacement (CR 614.1a, 614.6) applies to the last "
                        "step of its own resolution (CR 608.2n), so a resolved Nexus is never "
                        "in a graveyard: the predecessor's request is unreachable"
                    ),
                    "extra_turn_cause": (
                        "the required events extra_turn_created:P2 and extra_turn_created:P3 "
                        "are events, not state: a requested state that already contains both "
                        "extra turns leaves nothing to observe. P1 casts Time Warp targeting P2 "
                        "and, once it resolved, P3 casts Nexus of Fate on P1's turn (an "
                        "instant), each through the engine-offered legal actions and paid "
                        "from declared Islands; the engine then takes P3's extra turn before "
                        "P2's (CR 500.7)"
                    ),
                    "combat": (
                        "the observation passes through the rest of P1's turn and all of P3's "
                        "extra turn; each attack declaration is the active player's "
                        "discretionary choice (CR 508.1), so the script declares no attackers "
                        "for P1 and then for P3. The checkpoint moves from P1's postcombat to "
                        "its precombat main: a postcombat checkpoint has already passed P1's "
                        "combat, an attack declaration the record never scripts (the XMage "
                        "midgame lane refuses that arrival)"
                    ),
                    "cleanup": (
                        "the checkpoint hands are the dealt hands, complete: P1 holds eight "
                        "template cards (its opening seven and its first draw, CR 103.8c) "
                        "and every other player seven, each besides the named spell. P1 ends "
                        "its turn with eight cards and P3 its extra turn with eight (seven "
                        "after Nexus of Fate and its draw), so each discards one at its "
                        "cleanup (CR 514.1). That discard is the owner's choice and is "
                        "scripted on the engine's object frame (the PILOT_CHOOSE_OBJECT "
                        "discard family) as the card-identity multiset {Mountain: 1}"
                    ),
                    "cleanup_selector_equivalence": (
                        "the selection is the multiset of card identities discarded; every "
                        "offered card with that identity that is no named record object is "
                        "the same semantic selection (identical template cards), so it "
                        "matches once, never as several options. A frame that offers a "
                        "named record object with that identity, or no card with it, fails "
                        "closed (the WS05-CMD-MULL-2 London-bottom precedent)"
                    ),
                    "slot04_authority": SLOT04_AUTHORITY,
                },
            )
        ],
        {
            "predecessor_values": {
                "obj:mp-nexus": "graveyard",
                "obj:mp-time-warp": "graveyard",
                "extra_turn_creation": old["extra_turn_creation"],
                "temporal_state.phase": "postcombat_main",
                "decision_script": [],
            },
            "reason": (
                "a resolved Nexus of Fate in a graveyard (CR 614.6) and extra turns created "
                "before the run, so their creation events cannot occur"
            ),
        },
        "The objects, the extra-turn history, the hands, the script and the payment change.",
    )

# --- WS05-CMD-MULL-2 / MULL-4 ---------------------------------------------- #

for fixture, free in (("WS05-CMD-MULL-2", False), ("WS05-CMD-MULL-4", True)):
    old = base[fixture]
    players = _players(old)
    (first,) = old["decision_script"]
    assert first["selection"]["semantic_value"] == "mulligan_once" and first["actor"] == "P1"
    assert all("main_deck" in deck for deck in old["deck_state"])
    plan = old["pregame_decision_plan"]
    assert [(e["player_id"], e["decision"]) for e in plan] == [
        ("P1", "MULLIGAN"),
        *((p, "KEEP") for p in players[1:]),
        ("P1", "KEEP"),
    ], plan
    script = [
        _step("P1", "mull-r1-P1", "mulligan", "semantic_action", "mulligan"),
        *(
            _step(p, f"mull-r1-{p}", "mulligan", "semantic_action", "keep_opening_hand")
            for p in players[1:]
        ),
        _step("P1", "mull-r2-P1", "mulligan", "semantic_action", "keep_opening_hand"),
    ]
    if not free:
        script.append(
            _step(
                "P1",
                "bottom-r2-P1",
                "london_bottom",
                "card_identity_multiset",
                {"Mountain": 1},
                notes="CR 103.5: one card owed after one non-free mulligan",
            )
        )
    add(
        fixture,
        "FIXTURE_SCRIPT_CONTRACT_ERRATUM",
        {"deck_state": [_pregame_deck(p) for p in players], "decision_script": script},
        [
            _erratum_step(
                fixture,
                "scripted-pregame",
                {
                    "erratum_class": "FIXTURE_SCRIPT_CONTRACT_ERRATUM",
                    "comprehensive_rules": "103.5, 103.5c",
                    "reason": (
                        "CR 103.5 asks every player, in turn order, whether to mulligan, and "
                        "repeats the question after each mulligan for those who took one. The "
                        "predecessor scripts only P1's round-1 mulligan ('mulligan_once'), so "
                        "the other seats' round-1 keeps and P1's round-2 keep are unscripted "
                        "and every route fails closed there, although the record's own "
                        "pregame_decision_plan names them. The successor's decision script "
                        "states exactly that plan, entry for entry, in the PILOT_MULLIGAN shape"
                        + (
                            ""
                            if free
                            else "; the one card owed after a non-free two-player mulligan "
                            "is a London bottom selection, named as a card multiset because "
                            "the hand holds only identical template cards"
                        )
                    ),
                    "deck_shape": (
                        "the predecessor's main_deck/exact_card_count shape predates the "
                        "library template and is refused (INVALID_DECK_STATE); the successor "
                        "uses the template shape of PILOT_MULLIGAN with the same 99 Mountains "
                        "and commander"
                    ),
                    "decision_family_binding": (
                        None
                        if free
                        else {
                            "record_family": "london_bottom",
                            "provider_surface": "the London mulligan's bottom selection",
                            "selector": "card_identity_multiset",
                            "equivalence": (
                                "the selection is the multiset of card identities put on the "
                                "bottom; every subset of the hand with that multiset is the "
                                "same semantic selection (the hand holds only identical "
                                "template cards), so it matches once, never as several "
                                "options. A hand in which no subset has the multiset fails "
                                "closed"
                            ),
                        }
                    ),
                    "route": "PROTOCOL2_SCRIPTED_PREGAME (the PILOT_MULLIGAN precedent)",
                },
            )
        ],
        {
            "predecessor_values": {"decision_script": old["decision_script"]},
            "reason": "unscripted round-1 keeps and round-2 keep, and a refused deck shape",
        },
        "Only the deck shape and the decision script change.",
    )

# --- RNG_RULES_TAPE: a card-caused shuffle (supersedes the 1.0.19 patch) ----- #

old = base["RNG_RULES_TAPE"]
prior = existing["RNG_RULES_TAPE"]
assert prior["correction_class"] == "LOSSLESS_LIBRARY_MATERIALIZATION_ERRATUM_SLOT04"
objects = copy.deepcopy(old["semantic_objects"])
extra_mountains = [f"obj:replay-mountain-{i}" for i in (6, 7, 8)]
assert not any(o["semantic_id"] in extra_mountains for o in objects)
objects += [
    _card("obj:replay-warp", "Chaos Warp", "P1", "hand"),
    *(_card(m, "Mountain", "P1", "battlefield") for m in extra_mountains),
]
decks = copy.deepcopy(prior["replace"]["deck_state"])
script = copy.deepcopy(old["decision_script"])
script += [
    _step(
        "P1",
        "cast-warp",
        "priority",
        "semantic_action",
        {"action": "cast", "object": "obj:replay-warp", "timing": "empty_stack"},
    ),
    _step("P1", "cast-warp", "target", "semantic_object", "obj:replay-mountain-1"),
    _step(
        "P1",
        "cast-warp",
        "mana_payment",
        "mana_payment",
        {"mana": ["R", "R", "R"], "sources": extra_mountains},
    ),
]
costs = copy.deepcopy(old["action_cost_state"])
costs.append(_cost("P1", "Chaos Warp", "obj:replay-warp", extra_mountains, 3, index=1))
add(
    "RNG_RULES_TAPE",
    "CARD_CAUSED_RULES_RNG_SCENARIO_ERRATUM",
    {
        "semantic_objects": objects,
        "deck_state": decks,
        "decision_script": script,
        "action_cost_state": costs,
    },
    [
        _erratum_step(
            "RNG_RULES_TAPE",
            "card-caused-shuffle",
            {
                "erratum_class": "CARD_CAUSED_RULES_RNG_SCENARIO_ERRATUM",
                "comprehensive_rules": "701.24",
                "reason": (
                    "the 1.0.19 erratum found that nothing in the scenario causes a shuffle "
                    "after construction: the only P1 shuffle is the start-of-game shuffle of "
                    "identical scaffolding cards, which the complete library replaces, so its "
                    "result has no Rules consequence (the replay twin's seed control confirms "
                    "it: rng_result_has_state_consequence is false) and needs adjudication. "
                    "Adjudicated: after Burn Down the House resolves, P1 casts Chaos Warp "
                    "(current Oracle: 'The owner of target permanent shuffles it into their "
                    "library, then reveals the top card of their library. If it's a permanent "
                    "card, they put it onto the battlefield.') on its tapped Mountain, paid by "
                    "three further declared Mountains. That shuffle is card-caused and orders "
                    "P1's complete library, whose top seven are distinguishable, so its result "
                    "decides the revealed card and the library order"
                ),
                "required_event_binding": (
                    "rules_rng:library_shuffle:P1 is the Chaos Warp shuffle; the start-of-game "
                    "scaffolding shuffle never satisfies it. The record's native step "
                    "'rules-shuffle' is realized by this card cause, never by a harness shuffle"
                ),
                "no_player_choice": "the current Oracle text asks no 'may'; the put is mandatory",
                "lossless_construction": {
                    key: prior["append_native_procedure"][0]["details"][key]
                    for key in (
                        "complete_checkpoint_hands",
                        "complete_checkpoint_libraries",
                        "first_turn_draw",
                        "scaffolding_template",
                    )
                },
                "supersedes_erratum_step": prior["append_native_procedure"][0]["step_id"],
            },
        )
    ],
    {
        "predecessor_values": {"decision_script": old["decision_script"]},
        "reason": (
            "no Rules-caused shuffle after construction, so the RNG result has no state consequence"
        ),
    },
    (
        "The objects, the script and the payment sources change; the 1.0.19 deck_state and its "
        "SLOT-04 erratum step are kept, and the obligation keys are untouched"
    ),
    supersede=True,
)

# --- MICRO_LAYERS: discriminating characteristic readbacks ------------------ #

old = base["MICRO_LAYERS"]
objects = copy.deepcopy(old["semantic_objects"])
(target,) = [o for o in objects if o["semantic_id"] == "obj:p2-bears"]
assert target["card_identity"] == "Grizzly Bears" and target["controller"] == "P2"
target.update(
    {
        "card_identity": "Serra Angel",
        "semantic_id": "obj:p2-angel",
        "card_lineage_id": "line:obj:p2-angel",
    }
)
add(
    "MICRO_LAYERS",
    "FIXTURE_OBSERVABILITY_ERRATUM",
    {"semantic_objects": objects},
    [
        _erratum_step(
            "MICRO_LAYERS",
            "layer-readbacks",
            {
                "erratum_class": "FIXTURE_OBSERVABILITY_ERRATUM",
                "comprehensive_rules": "613.1f, 613.4b, 613.4c, 613.7",
                "token_semantics": (
                    "layer6_remove_abilities, layer7b_set_pt:1/1 and layer7c_modify_pt:+1/+1 "
                    "are applications of continuous effects when characteristics are "
                    "determined (CR 613), not game events; each is established by a "
                    "characteristic readback of the engine's own state at the checkpoint, "
                    "never by an event log"
                ),
                "discrimination": {
                    "layer6_remove_abilities": "obj:p2-angel (printed flying, vigilance) has no abilities",
                    "layer7b_set_pt:1/1": "obj:p2-angel (printed 4/4, no Anthem: P2's) is 1/1",
                    "layer7c_modify_pt:+1/+1": "obj:micro-layer-bears (P1's) is 2/2 with no abilities",
                },
                "wrong_reason_controls": (
                    "Humility ignored: the Angel reads 4/4 with flying and vigilance and P1's "
                    "Bears 3/3; Anthem ignored: P1's Bears reads 1/1"
                ),
                "reason": (
                    "the predecessor's only creatures are vanilla Grizzly Bears, so 'no "
                    "abilities' holds without Humility and P1's Bears' printed 2/2 equals the "
                    "expected result: no readback could tell the layers applied. P2's Bears "
                    "becomes Serra Angel; the obligation tokens and the postcondition about "
                    "P1's Bears are unchanged"
                ),
            },
        )
    ],
    {
        "predecessor_values": {"obj:p2-bears": "Grizzly Bears"},
        "reason": "no object whose characteristics discriminate the layer applications",
    },
    "One object's identity changes; the obligation keys are untouched.",
)

# --- assemble --------------------------------------------------------------- #

# A superseding patch takes its predecessor's place, so every other overlay
# keeps its order; the new fixtures follow.
by_fixture = {patch["fixture_id"]: patch for patch in patches}
contract["record_successors"] = [
    by_fixture[p["fixture_id"]] if p["fixture_id"] in superseded else p
    for p in contract["record_successors"]
] + [patch for patch in patches if patch["fixture_id"] not in superseded]
accounting = contract["change_accounting"]
for patch in patches:
    fixture = patch["fixture_id"]
    if fixture not in accounting["changed_fixture_ids"]:
        accounting["changed_fixture_ids"].append(fixture)
        accounting["unchanged_provider_denominator_rows"] -= 1
    accounting["per_fixture_correction_class"][fixture] = patch["correction_class"]
accounting["changed_fixture_count"] = len(accounting["changed_fixture_ids"])
contract["contract_id"] = "commander-lab.full107/1.0.21-successor"
contract["effective_materialization_version"] = (
    "commander-lab.semantic-fixture-materialization/1.0.21-successor"
)
contract["materialization_schema_version_note"] = (
    "the record shape is unchanged from the 1.0.8 successor schema; 1.0.21 adds the #441 "
    "Claude-lane errata (E1-E3, WS05-MP-TURN-3/5, WS05-CMD-MULL-2/4, RNG_RULES_TAPE, "
    "MICRO_LAYERS) while preserving every other 1.0.20 overlay byte-semantically"
)
contract["predecessor"] = {
    "path": "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_20.json",
    "record_count": len(json.loads(raw)["record_successors"]),
    "role": (
        "historical successor overlays are preserved; this contract re-applies every current "
        "overlay to the same 1.0.5 historical base, adds the #441 Claude-lane errata, and "
        "extends (never drops) the one 1.0.19 overlay it supersedes"
    ),
    "schema_version": json.loads(raw)["predecessor"]["schema_version"],
    "sha256": hashlib.sha256(raw).hexdigest(),
}
dst.write_text(json.dumps(contract, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

schema_src = PRE / "SEMANTIC_FIXTURE_SCHEMA_v1_0_20_SUCCESSOR.json"
schema_text = schema_src.read_text(encoding="utf-8")
schema = json.loads(schema_text)
schema["title"] = schema["title"].replace("1.0.20", "1.0.21")
schema["$id"] = schema["$id"].replace("1.0.20", "1.0.21")
enum = schema["$defs"]["record"]["properties"]["materialization_version"]["enum"]
if "commander-lab.semantic-fixture-materialization/1.0.21-successor" not in enum:
    enum.append("commander-lab.semantic-fixture-materialization/1.0.21-successor")
schema["properties"]["contract_id"]["const"] = "commander-lab.full107/1.0.21-successor"
schema["properties"]["schema_version"]["const"] = (
    "commander-lab.semantic-fixture-materialization/1.0.21-successor"
)
indent = 2 if schema_text.startswith('{\n  "') else 1
(PRE / "SEMANTIC_FIXTURE_SCHEMA_v1_0_21_SUCCESSOR.json").write_text(
    json.dumps(schema, indent=indent, ensure_ascii=False) + "\n", encoding="utf-8"
)

apath = REPO / "qualification/CURRENT_PRE_FREEZE_CONTRACT.json"
auth = json.loads(apath.read_text())
full = auth["full107"]
full["successor_contract"] = (
    "qualification/pre-freeze-successor/FULL107_SUCCESSOR_CONTRACT_v1_0_21.json"
)
full["effective_materialization_schema"] = (
    "qualification/pre-freeze-successor/SEMANTIC_FIXTURE_SCHEMA_v1_0_21_SUCCESSOR.json"
)
for patch in patches:
    fixture = patch["fixture_id"]
    if fixture not in full["changed_fixture_ids"]:
        full["changed_fixture_ids"].append(fixture)
        full["unchanged_fixture_count"] -= 1
    full["evidence_survival"][fixture] = "REQUALIFICATION_REQUIRED_" + patch["correction_class"]
apath.write_text(json.dumps(auth, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print("wrote", dst.name, "records", len(contract["record_successors"]))
