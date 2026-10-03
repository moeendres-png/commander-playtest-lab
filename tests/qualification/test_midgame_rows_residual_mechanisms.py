"""#456 generic executor mechanisms for the XMage AF06/AF08 residual rows.

* a record's yes/no answer named by its rules family (the commander zone
  choice) answers XMage's one yes/no frame class, and only that frame;
* the commander zone choice is verified against the engine's own moves of the
  record's commander object and the scripted answer on the engine's frame;
* a record's requested combat (``combat_state``) is declared on the engine's
  own frames and then verified against the engine's declaration events;
* CR 400.7 new-object evidence is the engine's own public move between zones;
* commander damage is read from the engine's per-commander readback;
* a FULL107 row with a declared causal-stack entry enters through it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from commander_lab.qualification.current_boundary import midgame_lane as ml
from commander_lab.qualification.current_boundary import midgame_rows as mr

REPO_ROOT = Path(__file__).resolve().parents[2]

# --------------------------------------------------------------------------- #
# Yes/no frames named by their rules family
# --------------------------------------------------------------------------- #


def _step(family: str, selector: str, value: Any = True) -> dict[str, Any]:
    return {
        "decision_family": family,
        "selection": {"selector_kind": selector, "semantic_value": value},
    }


def test_a_boolean_answer_named_by_its_rules_family_answers_the_yes_no_frame() -> None:
    assert mr.step_decision_class(_step("choice", "boolean")) == "choose_use"
    assert mr.step_decision_class(_step("replacement_effect", "boolean")) == "choose_use"


def test_only_a_boolean_selector_rebinds_the_family() -> None:
    # A key choice keeps its own class; a family the binding does not name is
    # spelled as before (including the existing record-to-engine renames).
    assert mr.step_decision_class(_step("choice", "semantic_object")) == "choice"
    assert mr.step_decision_class(_step("target", "boolean")) == "target"
    assert mr.step_decision_class(_step("choose_mode", "semantic_mode_key")) == "mode"


# --------------------------------------------------------------------------- #
# The commander zone choice (CR 903.9)
# --------------------------------------------------------------------------- #

COMMANDERS = {"obj:cmd"}


def _move(sequence: int, source: str, destination: str, obj: str = "obj:cmd") -> dict[str, Any]:
    return {
        "sequence": sequence,
        "type": "ZONE_CHANGE",
        "from": source,
        "to": destination,
        "target_object": obj,
    }


def _zone_frame(prompt: str, answer: str, scripted: bool = True) -> mr.Frame:
    labels = ["Yes", "No"]
    return mr.Frame(
        "choose_use",
        "P1",
        labels,
        selected_label="Yes" if answer == "true" else "No",
        scripted=scripted,
        selected_key=answer,
        prompt=prompt,
    )


GY_PROMPT = "Move Rograkh to the command zone or leave it in current zone (GRAVEYARD)?"
HAND_PROMPT = "Move Rograkh to command zone instead of your hand?"


def test_a_graveyard_move_then_the_command_zone_is_the_yes_answer() -> None:
    tape = [_move(1, "BATTLEFIELD", "GRAVEYARD"), _move(2, "GRAVEYARD", "COMMAND")]
    trace = [_zone_frame(GY_PROMPT, "true")]
    assert mr.verify_token("commander_zone_event:graveyard", tape, trace, COMMANDERS)
    assert mr.verify_token("commander_choice:command", tape, trace, COMMANDERS)
    # The answer was yes: the commander did not stay in the graveyard.
    assert mr.verify_token("commander_choice:graveyard", tape, trace, COMMANDERS) is None


def test_a_no_answer_needs_the_commander_to_stay_where_it_went() -> None:
    tape = [_move(1, "BATTLEFIELD", "GRAVEYARD")]
    trace = [_zone_frame(GY_PROMPT, "false")]
    assert mr.verify_token("commander_choice:graveyard", tape, trace, COMMANDERS)
    assert mr.verify_token("commander_choice:command", tape, trace, COMMANDERS) is None
    # A "no" whose commander nonetheless ended in the command zone is no evidence.
    moved = [*tape, _move(2, "GRAVEYARD", "COMMAND")]
    assert mr.verify_token("commander_choice:graveyard", moved, trace, COMMANDERS) is None


def test_a_replaced_hand_move_is_named_by_the_engine_frame_and_the_command_move() -> None:
    # CR 903.9b: the move to the hand never happens; the engine asked about it.
    tape = [_move(1, "BATTLEFIELD", "COMMAND")]
    trace = [_zone_frame(HAND_PROMPT, "true")]
    assert mr.verify_token("commander_zone_event:hand", tape, trace, COMMANDERS)
    assert mr.verify_token("commander_zone_event:library", tape, trace, COMMANDERS) is None
    # Graveyard and exile are never replaced: a frame alone is no evidence.
    assert mr.verify_token("commander_zone_event:graveyard", tape, trace, COMMANDERS) is None


def test_zone_evidence_needs_a_scripted_answer_and_the_record_commander() -> None:
    tape = [_move(1, "BATTLEFIELD", "COMMAND")]
    unscripted = [_zone_frame(HAND_PROMPT, "true", scripted=False)]
    assert mr.verify_token("commander_zone_event:hand", tape, unscripted, COMMANDERS) is None
    assert mr.verify_token("commander_choice:command", tape, unscripted, COMMANDERS) is None
    other = [_move(1, "BATTLEFIELD", "COMMAND", obj="obj:not-a-commander")]
    trace = [_zone_frame(HAND_PROMPT, "true")]
    assert mr.verify_token("commander_choice:command", other, trace, COMMANDERS) is None


def test_a_boolean_answer_records_the_value_it_submitted() -> None:
    legal = {
        "actions": [
            {
                "metadata": {
                    "option_type": "boolean",
                    "option_id": value,
                    "label": value,
                    "xmage_option_metadata": {"value": value == "yes"},
                }
            }
            for value in ("yes", "no")
        ]
    }
    answer = mr._scripted_answer(legal, _step("choice", "boolean", False), {}, mr.RowSpec(), 0)
    assert answer.key == "false"
    assert answer.action is legal["actions"][1]


# --------------------------------------------------------------------------- #
# Requested combat (combat_state)
# --------------------------------------------------------------------------- #


def test_a_record_without_combat_requests_none() -> None:
    assert mr.requested_combat({}) is None
    assert mr.requested_combat({"combat_state": None}) is None
    # An empty attacker map is a checkpoint snapshot with no combat yet; the
    # record's own script may declare attacks later (CARD_08).
    assert mr.requested_combat({"combat_state": {"attackers": {}}}) is None


def test_listed_blocks_are_the_requested_blocks() -> None:
    combat = mr.requested_combat(
        {"combat_state": {"attackers": {"obj:a": "P2"}, "blockers": {"obj:b": "obj:a"}}}
    )
    assert combat is not None
    assert combat.attackers == (("obj:a", "P2"),)
    assert combat.blocks == (("obj:b", "obj:a"),)


def test_every_attacker_unblocked_requests_no_block() -> None:
    for key in ("unblocked", "unblocked_attackers"):
        combat = mr.requested_combat(
            {"combat_state": {"attackers": {"obj:a": "P2"}, key: ["obj:a"]}}
        )
        assert combat is not None and combat.blocks == ()


def test_unstated_blocks_are_left_to_the_record_script() -> None:
    # Neither blocks nor an unblocked attacker: the blocks are not requested
    # combat, they are the record's own scripted decision (or unanswered).
    combat = mr.requested_combat(
        {"combat_state": {"attackers": {"obj:a": "P2", "obj:c": "P3"}, "unblocked": ["obj:a"]}}
    )
    assert combat is not None and combat.blocks is None


def test_malformed_combat_fails_closed() -> None:
    with pytest.raises(ml.MidgameLaneError):
        mr.requested_combat({"combat_state": {"attackers": ["obj:a"]}})
    with pytest.raises(ml.MidgameLaneError):
        mr.requested_combat({"combat_state": {"attackers": {"obj:a": "P2"}, "blockers": ["x"]}})


def _declared(kind: str, source: str, target: str) -> dict[str, Any]:
    field = "target_player" if kind == "ATTACKER_DECLARED" else "target_object"
    return {"type": kind, "source_object": source, field: target}


def test_the_engine_declarations_must_be_exactly_the_requested_combat() -> None:
    combat = mr.RequestedCombat(attackers=(("obj:a", "P2"),), blocks=(("obj:b", "obj:a"),))
    exact = [
        _declared("ATTACKER_DECLARED", "obj:a", "P2"),
        _declared("BLOCKER_DECLARED", "obj:b", "obj:a"),
    ]
    assert mr.combat_matches_request(combat, exact)["holds"]
    extra_attack = [*exact, _declared("ATTACKER_DECLARED", "obj:c", "P3")]
    assert not mr.combat_matches_request(combat, extra_attack)["holds"]
    wrong_defender = [
        _declared("ATTACKER_DECLARED", "obj:a", "P3"),
        _declared("BLOCKER_DECLARED", "obj:b", "obj:a"),
    ]
    assert not mr.combat_matches_request(combat, wrong_defender)["holds"]
    no_block = exact[:1]
    assert not mr.combat_matches_request(combat, no_block)["holds"]
    # Blocks the record leaves to its script are not compared here.
    scripted_blocks = mr.RequestedCombat(attackers=(("obj:a", "P2"),), blocks=None)
    assert mr.combat_matches_request(scripted_blocks, exact)["holds"]


# --------------------------------------------------------------------------- #
# CR 400.7 new object incarnation
# --------------------------------------------------------------------------- #

RECORD = {"semantic_objects": [{"semantic_id": "obj:bolt", "card_lineage_id": "line:bolt"}]}


def _moved(sequence: int, source: str, destination: str, public: bool = True) -> dict[str, Any]:
    return {**_move(sequence, source, destination, obj="obj:bolt"), "public_identity": public}


def test_a_public_move_between_zones_is_new_object_evidence() -> None:
    window = [_moved(5, "STACK", "GRAVEYARD")]
    assert mr.new_incarnation_evidence("line:bolt", RECORD, window) == {
        "events": [5],
        "from": "STACK",
        "to": "GRAVEYARD",
    }


def test_no_public_move_between_zones_is_no_evidence() -> None:
    assert mr.new_incarnation_evidence("line:bolt", RECORD, []) is None
    assert mr.new_incarnation_evidence("line:bolt", RECORD, [_moved(5, "STACK", "STACK")]) is None
    hidden = [_moved(5, "LIBRARY", "HAND", public=False)]
    assert mr.new_incarnation_evidence("line:bolt", RECORD, hidden) is None
    # Only the lineage's last move counts.
    window = [_moved(4, "HAND", "STACK"), _moved(5, "GRAVEYARD", "LIBRARY", public=False)]
    assert mr.new_incarnation_evidence("line:bolt", RECORD, window) is None
    assert (
        mr.new_incarnation_evidence("line:other", RECORD, [_moved(5, "STACK", "GRAVEYARD")]) is None
    )


def test_no_engine_event_carries_a_zone_change_counter() -> None:
    """Hidden-zone history never reaches the tape: no counter, no new-object flag."""
    source = (
        REPO_ROOT
        / "engine-bridge/src/main/java/org/commanderlab/xmage/XmagePublicEventWatcher.java"
    ).read_text(encoding="utf-8")
    # The watcher reads the counter only to settle a pending exile move; no
    # published key carries it or anything derived from it.
    for key in ('"new_object"', '"incarnation"', '"zone_change_counter"'):
        assert key not in source, key


# --------------------------------------------------------------------------- #
# Commander damage readback
# --------------------------------------------------------------------------- #


def _observation(damage: dict[str, int] | None) -> dict[str, Any]:
    entry: dict[str, Any] = {"card_identity": "Isamaru, Hound of Konda"}
    if damage is not None:
        entry["combat_damage_to"] = damage
    return {"seats": [{"player_id": "P1", "commanders": [entry]}]}


def test_commander_damage_is_the_engine_readback_per_commander() -> None:
    check = mr.TerminalCheck(
        "commander_damage",
        principal="P1",
        card_identity="Isamaru, Hound of Konda",
        value=("P2", 21),
    )
    assert mr.needs_observation(check)
    assert mr.check_terminal(check, _observation({"P2": 21}), [], [])
    assert not mr.check_terminal(check, _observation({"P2": 19}), [], [])
    assert not mr.check_terminal(check, _observation({"P3": 21}), [], [])
    assert not mr.check_terminal(check, _observation(None), [], [])


# --------------------------------------------------------------------------- #
# The FULL107 route uses a row's declared causal-stack entry
# --------------------------------------------------------------------------- #


def test_only_a_declared_causal_stack_entry_routes_a_row() -> None:
    entry = mr.causal_stack_entry("WS05-CMD-ZONE-GY-YES")
    assert entry is not None and entry["entry_mode"] == "causal_stack" and entry["fuel"]
    # A causal elimination or a placement entry is not a stack entry.
    assert mr.causal_stack_entry("WS05-MP-ELIM-OWNED-3") is None
    assert mr.causal_stack_entry("WS05-MP-BLOCK-4") is None
    assert mr.causal_stack_entry("NOT_A_FIXTURE") is None


# --------------------------------------------------------------------------- #
# Event order, frame order and the legal-block partition
# --------------------------------------------------------------------------- #


def _trigger(sequence: int, player: str) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "type": "TRIGGERED_ABILITY",
        "source_name": "Soul Warden",
        "player_player": player,
    }


def test_event_order_reads_the_engine_tape_order_of_the_filtered_events() -> None:
    check = mr.TerminalCheck(
        "event_order",
        event_type="TRIGGERED_ABILITY",
        where=(("source_name~", "Soul Warden"),),
        value=("player_player", ("P1", "P2", "P3")),
    )
    in_order = [_trigger(1, "P1"), _trigger(2, "P2"), _trigger(3, "P3")]
    assert mr.check_terminal(check, {}, in_order, [])
    assert not mr.check_terminal(check, {}, list(reversed(in_order)), [])
    # A missing or an extra trigger is a different order, never a prefix match.
    assert not mr.check_terminal(check, {}, in_order[:2], [])
    assert not mr.check_terminal(check, {}, [*in_order, _trigger(4, "P1")], [])


def _priority_frame(principal: str) -> mr.Frame:
    return mr.Frame("priority", principal, ["Pass priority"])


def test_frame_order_is_a_prefix_of_the_engine_decision_sequence() -> None:
    check = mr.TerminalCheck("frame_order", value=("priority", ("P1", "P2", "P3")))
    trace = [_priority_frame(p) for p in ("P1", "P2", "P3", "P3", "P1")]
    assert mr.check_terminal(check, {}, [], trace)
    assert not mr.check_terminal(check, {}, [], trace[1:])
    assert not mr.check_terminal(check, {}, [], trace[:2])


def _block_frame(principal: str, attackers: tuple[str | None, ...]) -> mr.Frame:
    frame = mr.Frame("declare_blocker", principal, ["x"])
    frame.offered_attackers = attackers
    return frame


def test_the_block_partition_needs_every_offer_to_name_an_attacker_of_the_principal() -> None:
    check = mr.TerminalCheck("blocker_partition", principal="P2", value=(("obj:a2",), ("obj:a3",)))
    assert mr.check_terminal(check, {}, [], [_block_frame("P2", ("obj:a2",))])
    # An offer of P3's attacker to P2 breaks the partition.
    assert not mr.check_terminal(check, {}, [], [_block_frame("P2", ("obj:a2", "obj:a3"))])
    # An offer the record never placed is not an attacker of P2.
    assert not mr.check_terminal(check, {}, [], [_block_frame("P2", (None,))])
    # No frame of the principal, or no other attacked player, proves nothing.
    assert not mr.check_terminal(check, {}, [], [_block_frame("P3", ("obj:a3",))])
    lone = mr.TerminalCheck("blocker_partition", principal="P2", value=(("obj:a2",), ()))
    assert not mr.check_terminal(lone, {}, [], [_block_frame("P2", ("obj:a2",))])


# --------------------------------------------------------------------------- #
# Causal elimination on the FULL107 route
# --------------------------------------------------------------------------- #


def test_only_a_declared_causal_elimination_entry_routes_an_elimination() -> None:
    entry = mr.causal_elimination_entry("WS05-MP-ELIM-OWNED-3")
    assert entry is not None and entry["elimination_victim"] == "P2"
    assert mr.causal_elimination_entry("WS05-CMD-ZONE-GY-YES") is None
    assert mr.causal_elimination_entry("NOT_A_FIXTURE") is None


def test_the_elimination_instruments_are_one_bolt_and_one_mountain_each() -> None:
    entry = mr.causal_elimination_entry("WS05-MP-ELIM-5")
    assert entry is not None
    request = mr.probe_module().elimination_request(entry)
    assert request["actor"] == "P1" and request["victim"] == "P3"
    bolts = [i for i in request["instruments"] if i["card_identity"] == "Lightning Bolt"]
    lands = [i for i in request["instruments"] if i["card_identity"] == "Mountain"]
    assert len(bolts) == len(lands) == entry["bolt_count"]
    assert all(i["owner"] == "P1" for i in request["instruments"])
    assert {i["zone"] for i in bolts} == {"hand"}
    assert {i["zone"] for i in lands} == {"battlefield"}


def test_only_the_declared_composed_entry_routes_a_stack_then_elimination() -> None:
    entry = mr.causal_stack_elimination_entry("WS05-MP-ELIM-STACK-3")
    assert entry is not None
    assert entry["entry_mode"] == mr.probe_module().CAUSAL_STACK_ELIMINATION
    assert entry["elimination_victim"] == "P2" and entry["fuel"]
    # The composed row is routed by exactly one entry.
    assert mr.causal_stack_entry("WS05-MP-ELIM-STACK-3") is None
    assert mr.causal_elimination_entry("WS05-MP-ELIM-STACK-3") is None
    assert mr.causal_stack_elimination_entry("WS05-MP-ELIM-OWNED-3") is None
    assert mr.causal_stack_elimination_entry("WS05-MP-PRIO-3") is None


def test_the_victims_own_cards_are_never_elimination_instruments() -> None:
    """Instruments are the plan's declared ones, never a placed object by its name."""
    plan = {
        "placed_objects": {
            "obj:leave-bolt": "victim-bolt",
            "obj:fuel-mountain-p2": "victim-mountain",
            "obj:elim-bolt-0": "bolt-0",
            "obj:elim-mountain-0": "mountain-0",
        },
        "instruments": [
            {"card_identity": "Lightning Bolt", "zone": "hand", "native_id": "bolt-0"},
            {"card_identity": "Mountain", "zone": "battlefield", "native_id": "mountain-0"},
        ],
    }
    assert mr.probe_module().elimination_instrument_ids(plan) == (["bolt-0"], ["mountain-0"])
    assert mr.probe_module().elimination_instrument_ids({}) == ([], [])


def _priority(sequence: int | None, stack: int | None) -> mr.Frame:
    frame = mr.Frame("priority", "P1", ["Pass priority"])
    frame.tape_sequence = sequence
    frame.stack_size = stack
    return frame


def test_the_stack_after_an_event_is_read_from_the_next_priority_frame() -> None:
    check = mr.TerminalCheck(
        "stack_empty_after", event_type="LOST", where=(("player_player", "P2"),)
    )
    tape = [{"type": "LOST", "sequence": 10, "player_player": "P2"}]
    # The frame asked before the loss still shows the spell; the next one does not.
    assert mr.check_terminal(check, {}, tape, [_priority(9, 1), _priority(10, 0)])
    # The spell is still on the stack after the loss: the obligation is not met.
    assert not mr.check_terminal(check, {}, tape, [_priority(10, 1), _priority(12, 0)])
    # No priority frame after the loss, no event, or no stack shown: not met.
    assert not mr.check_terminal(check, {}, tape, [_priority(9, 0)])
    assert not mr.check_terminal(check, {}, [], [_priority(10, 0)])
    assert not mr.check_terminal(check, {}, tape, [_priority(10, None)])
    # Another player's loss is not the anchor.
    other = [{"type": "LOST", "sequence": 10, "player_player": "P3"}]
    assert not mr.check_terminal(check, {}, other, [_priority(10, 0)])


def test_a_player_left_only_when_the_engine_reports_both_loss_and_leaving() -> None:
    check = mr.TerminalCheck("player_left", principal="P2")
    assert mr.needs_observation(check)

    def seat(**fields: Any) -> dict[str, Any]:
        return {"seats": [{"player_id": "P2", **fields}]}

    assert mr.check_terminal(check, seat(lost=True, left=True), [], [])
    assert not mr.check_terminal(check, seat(lost=True, left=False), [], [])
    assert not mr.check_terminal(check, seat(lost=False, left=True), [], [])
    assert not mr.check_terminal(check, {"seats": []}, [], [])


# --------------------------------------------------------------------------- #
# Stack objects, scripted payments, pending extra turns
# --------------------------------------------------------------------------- #

STACK_RECORD = {"stack_state": [{"source_semantic_id": "obj:bolt"}]}


def test_a_stack_object_is_the_records_own_stack_entry() -> None:
    step = {"selection": {"selector_kind": "semantic_stack_object", "semantic_value": "stack:1"}}
    resolved = mr.stack_object_step(step, STACK_RECORD)
    assert resolved["selection"]["selector_kind"] == "semantic_object"
    assert resolved["selection"]["semantic_value"] == "obj:bolt"
    other = {"selection": {"selector_kind": "semantic_object", "semantic_value": "obj:x"}}
    assert mr.stack_object_step(other, STACK_RECORD) is other


@pytest.mark.parametrize("value", ["stack:2", "stack:0", "top", "", "stack:1x"])
def test_a_stack_object_the_record_never_requested_fails_closed(value: str) -> None:
    step = {"selection": {"selector_kind": "semantic_stack_object", "semantic_value": value}}
    with pytest.raises(ml.MidgameLaneError):
        mr.stack_object_step(step, STACK_RECORD)


def test_a_pool_spend_names_its_color_or_fails_closed() -> None:
    assert mr._spent_color("Spend blue mana from pool") == "blue"
    with pytest.raises(ml.MidgameLaneError):
        mr._spent_color("Island — {T}: Add {U}.")


def test_pending_extra_turns_are_the_engine_order_exactly() -> None:
    check = mr.TerminalCheck("pending_extra_turns", value=("P3", "P2"))
    assert mr.needs_observation(check)
    assert mr.check_terminal(check, {"pending_extra_turns": ["P3", "P2"]}, [], [])
    assert not mr.check_terminal(check, {"pending_extra_turns": ["P2", "P3"]}, [], [])
    assert not mr.check_terminal(check, {}, [], [])


# --------------------------------------------------------------------------- #
# Review fixes: row membership, absent sources, players in the game, blocks
# --------------------------------------------------------------------------- #

# Every row this workstream reports as verified must be produced by the PB-03
# producer: a spec missing from ROWS is silently never run.
WORKSTREAM_ROWS = {
    *(
        f"WS05-CMD-ZONE-{zone}-{answer}"
        for zone in ("GY", "EXILE", "HAND", "LIB")
        for answer in ("YES", "NO")
    ),
    "MICRO_COMBAT",
    "WS05-CMD-DMG-SAME-21",
    "WS05-CMD-ELIM-4",
    "WS05-CMD-DMG-SPLIT",
    "MICRO_ZONE_CHANGES",
    "MICRO_STATE_BASED_ACTIONS",
    "MICRO_PRIORITY",
    "MICRO_STACK",
    "WS05-MP-PRIO-3",
    "WS05-MP-PRIO-5",
    "WS05-MP-TRIG-3",
    "WS05-MP-TRIG-5",
    "MICRO_CONTINUOUS_EFFECTS",
    "WS05-MP-BLOCK-4",
    "PILOT_DECLARE_BLOCKER",
    "MICRO_REPLACEMENT",
    "MICRO_PREVENTION",
    "WS05-MP-ELIM-OWNED-3",
    "WS05-MP-ELIM-PRIO-3",
    "WS05-MP-ELIM-5",
    "WS05-MP-ELIM-TURN-3",
    "WS05-CMD-PARTNER-DMG",
    "MICRO_MANA_PAYMENT",
    "MICRO_COPY",
    "MICRO_RULES_RANDOMNESS",
    "MICRO_CONTROL",
    "WS05-CMD-DMG-CONTROL",
    "WS05-CMD-PARTNER-TAX",
    "WS05-MP-ELIM-STACK-3",
}


def test_every_workstream_row_is_produced() -> None:
    assert set(mr.ROWS) >= WORKSTREAM_ROWS
    assert len(mr.ROWS) == 22 + len(WORKSTREAM_ROWS)
    # The partner-zone row is executed by Forge as written; XMage has no spec.
    assert "WS05-CMD-PARTNER-ZONE" not in mr.ROWS


def test_an_absent_source_means_no_source_of_any_kind() -> None:
    check = mr.TerminalCheck(
        "events", event_type="DESTROYED_PERMANENT", where=(("source_object", None),), value=1
    )
    assert mr.check_terminal(check, {}, [{"type": "DESTROYED_PERMANENT", "sequence": 1}], [])
    # The bridge reports `source_present` for a source it withholds or cannot map.
    for other in ({"source_player": "P2"}, {"source_present": True}, {"source_object": "obj:x"}):
        event = {"type": "DESTROYED_PERMANENT", "sequence": 1, **other}
        assert not mr.check_terminal(check, {}, [event], []), other


def test_an_unnamed_object_is_present_but_not_named() -> None:
    check = mr.TerminalCheck(
        "events",
        event_type="DAMAGED_PLAYER",
        where=(("source_object", mr.UNNAMED_OBJECT),),
        value=1,
    )
    copy = {"type": "DAMAGED_PLAYER", "sequence": 1, "source_present": True}
    assert mr.check_terminal(check, {}, [copy], [])
    for other in ({}, {"source_object": "obj:x"}, {"source_player": "P2"}):
        event = {"type": "DAMAGED_PLAYER", "sequence": 1, "source_present": True, **other}
        if not other:
            event.pop("source_present")
        assert not mr.check_terminal(check, {}, [event], []), other


def test_a_player_in_the_game_has_neither_lost_nor_left() -> None:
    check = mr.TerminalCheck("player_in_game", principal="P2")
    assert mr.needs_observation(check)

    def seat(**fields: Any) -> dict[str, Any]:
        return {"seats": [{"player_id": "P2", **fields}]}

    assert mr.check_terminal(check, seat(lost=False, left=False), [], [])
    assert not mr.check_terminal(check, seat(lost=True, left=False), [], [])
    assert not mr.check_terminal(check, seat(lost=False), [], [])
    assert not mr.check_terminal(check, {"seats": []}, [], [])


def test_requested_blocks_are_checked_even_when_the_script_attacks() -> None:
    combat = mr.RequestedCombat(attackers=(("obj:a", "P2"),), blocks=(("obj:b", "obj:a"),))
    blocks_only = [
        _declared("ATTACKER_DECLARED", "obj:a", "P3"),
        _declared("BLOCKER_DECLARED", "obj:b", "obj:a"),
    ]
    # The script's own attack is not compared; the requested block is.
    assert mr.combat_matches_request(combat, blocks_only, compare_attacks=False)["holds"]
    assert not mr.combat_matches_request(combat, [], compare_attacks=False)["holds"]
    # With every attacker unblocked, a scripted attack must still have happened.
    unblocked = mr.RequestedCombat(attackers=(("obj:a", "P2"),), blocks=())
    assert not mr.combat_matches_request(unblocked, [], compare_attacks=False)["holds"]
    attacked = [_declared("ATTACKER_DECLARED", "obj:a", "P2")]
    assert mr.combat_matches_request(unblocked, attacked, compare_attacks=False)["holds"]
