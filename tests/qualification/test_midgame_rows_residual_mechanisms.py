"""#456 generic executor mechanisms for the XMage AF06/AF08 residual rows.

* a record's yes/no answer named by its rules family (the commander zone
  choice) answers XMage's one yes/no frame class, and only that frame;
* the commander zone choice is verified against the engine's own moves of the
  record's commander object and the scripted answer on the engine's frame;
* a record's requested combat (``combat_state``) is declared on the engine's
  own frames and then verified against the engine's declaration events;
* CR 400.7 new-object evidence is the engine's own incarnation, never assumed;
* commander damage is read from the engine's per-commander readback;
* a FULL107 row with a declared causal-stack entry enters through it.
"""

from __future__ import annotations

from typing import Any

import pytest

from commander_lab.qualification.current_boundary import midgame_lane as ml
from commander_lab.qualification.current_boundary import midgame_rows as mr

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


def _incarnated(sequence: int, source: str, destination: str, incarnation: Any) -> dict[str, Any]:
    event = _move(sequence, source, destination, obj="obj:bolt")
    if incarnation is not None:
        event["incarnation"] = incarnation
    return event


def test_a_move_with_a_greater_engine_incarnation_is_a_new_object() -> None:
    history = [_incarnated(1, "HAND", "STACK", 3), _incarnated(5, "STACK", "GRAVEYARD", 4)]
    evidence = mr.new_incarnation_evidence("line:bolt", RECORD, history, history[1:])
    assert evidence == {"events": [1, 5], "incarnations": [3, 4]}


def test_no_incarnation_or_no_earlier_move_is_no_evidence() -> None:
    unreported = [_incarnated(1, "HAND", "STACK", None), _incarnated(5, "STACK", "GRAVEYARD", 4)]
    assert mr.new_incarnation_evidence("line:bolt", RECORD, unreported, unreported[1:]) is None
    single = [_incarnated(5, "STACK", "GRAVEYARD", 4)]
    assert mr.new_incarnation_evidence("line:bolt", RECORD, single, single) is None
    same = [_incarnated(1, "HAND", "STACK", 4), _incarnated(5, "STACK", "GRAVEYARD", 4)]
    assert mr.new_incarnation_evidence("line:bolt", RECORD, same, same[1:]) is None
    assert mr.new_incarnation_evidence("line:other", RECORD, same, same[1:]) is None


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
