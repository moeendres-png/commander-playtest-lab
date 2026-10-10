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


def test_the_control_row_causes_its_aura_through_a_declared_flash_enabler() -> None:
    entry = mr.causal_stack_elimination_entry("WS05-MP-ELIM-CONTROL-3")
    assert entry is not None
    assert entry["caused_permanents"] == ["obj:leave-controlmagic"]
    cards = {card["card_identity"] for card in entry["fuel"]}
    assert "Leyline of Anticipation" in cards
    assert all(card["owner"] == "P2" for card in entry["fuel"])
    # The elimination row without caused permanents keeps its own entry shape.
    assert not mr.causal_stack_elimination_entry("WS05-MP-ELIM-STACK-3").get("caused_permanents")


class _ResolvingClient:
    """A lane client whose engine offers the given decisions in turn."""

    def __init__(self, decisions: list[dict[str, Any] | None]) -> None:
        self.decisions = list(decisions)
        self.submitted: list[list[str]] = []

    def pending_decision(self) -> dict[str, Any] | None:
        return self.decisions.pop(0) if self.decisions else None

    def submit_options(self, decision: dict[str, Any], options: list[str]) -> None:
        self.submitted.append(options)


def _priority_decision(stack: list[str] | None) -> dict[str, Any]:
    decision: dict[str, Any] = {
        "decision_class": "priority",
        "decision_id": "d",
        "seat": 0,
        "legal_options": [{"option_type": "pass_priority", "option_id": "pass"}],
    }
    if stack is not None:
        decision["pilot_state"] = {"stack": stack}
    return decision


def test_resolving_the_stack_only_passes_priority_until_it_is_empty() -> None:
    probe = mr.probe_module()
    client = _ResolvingClient(
        [_priority_decision(["aura"]), _priority_decision(["aura"]), _priority_decision([])]
    )
    authority = probe.PassAuthority({"decision_script": []})
    probe.resolve_stack(client, "t", authority)
    assert client.submitted == [["pass"], ["pass"]]
    # A pass-only frame leaves no choice; each pass is still traced (#634 B2).
    assert [entry["scope"] for entry in authority.trace] == ["single_option", "single_option"]
    # Any other decision, a frame without a stack, or the engine going
    # terminal fails closed instead of being answered.
    for decisions in (
        [{"decision_class": "target", "legal_options": []}],
        [_priority_decision(None)],
        [None],
    ):
        with pytest.raises(probe.ml.MidgameLaneError):
            probe.resolve_stack(
                _ResolvingClient(decisions), "t", probe.PassAuthority({"decision_script": []})
            )


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


def _readback(pending: tuple[str, ...] | None) -> mr.Frame:
    return mr.Frame("priority", "P1", [], pending_extra_turns=pending)


def test_an_extra_turn_is_created_when_the_engine_queue_gains_it() -> None:
    created = mr.TerminalCheck("extra_turn_created", principal="P3", value=("P3", "P2"))
    assert not mr.needs_observation(created)
    trace = [_readback(()), _readback(None), _readback(("P2",)), _readback(("P3", "P2"))]
    assert mr.check_terminal(created, {}, [], trace)
    assert mr.bound_token_evidence(created, {}, [], trace)["decision_frames"] == [3]
    # Already pending when the run began: nothing was created in the run.
    assert not mr.check_terminal(created, {}, [], [_readback(("P3",)), *trace[1:]])
    # The run's first frame was never read back: no baseline, no creation.
    assert not mr.check_terminal(created, {}, [], [_readback(None), *trace[1:]])
    # The queue must be exactly the requested order, never a superset or a swap.
    assert not mr.check_terminal(created, {}, [], [*trace[:3], _readback(("P2", "P3"))])
    assert not mr.check_terminal(created, {}, [], [*trace[:3], _readback(("P3", "P2", "P1"))])
    assert not mr.check_terminal(created, {}, [], [])


def test_the_extra_turn_rows_bind_creation_to_the_cast_and_the_engine_queue() -> None:
    for fixture in ("WS05-MP-TURN-3", "WS05-MP-TURN-5"):
        bindings = dict(mr.ROWS[fixture].token_bindings)
        assert set(bindings) == {
            "extra_turn_created:P2",
            "extra_turn_created:P3",
            "next_turn:P3",
            "next_turn:P2",
        }
        cast, cast_first, created = bindings["extra_turn_created:P3"]
        assert (cast.kind, cast.event_type) == ("events", "SPELL_CAST")
        assert ("source_object", "obj:mp-nexus") in cast.where
        assert cast_first.kind == "events_precede"
        assert (created.kind, created.principal, created.value) == (
            "extra_turn_created",
            "P3",
            ("P3", "P2"),
        )
        # Codex P1 (#536): the creation is ordered after the spell resolves.
        assert created.after is not None and ("from", "STACK") in created.after.where
        assert ("target_object", "obj:mp-nexus") in created.after.where
        assert mr._reads_extra_turns(bindings["extra_turn_created:P2"])
        assert mr._reads_extra_turns(bindings["next_turn:P2"])


def _at(pending: tuple[str, ...] | None, sequence: int | None) -> mr.Frame:
    return mr.Frame("priority", "P1", [], pending_extra_turns=pending, tape_sequence=sequence)


_WARP_RESOLVED = mr.TerminalCheck(
    "events", event_type="ZONE_CHANGE", where=(("target_object", "obj:w"), ("from", "STACK"))
)
_TAPE = [{"sequence": 5, "type": "ZONE_CHANGE", "target_object": "obj:w", "from": "STACK"}]


def test_an_extra_turn_queued_before_its_spell_resolves_is_not_created_by_it() -> None:
    """Codex P1 (#536): a queue entry read before the resolution is a broken mechanic."""
    created = mr.TerminalCheck(
        "extra_turn_created", principal="P2", value=("P2",), after=_WARP_RESOLVED
    )
    good = [_at((), None), _at((), 3), _at(None, 4), _at(("P2",), 6)]
    assert mr._extra_turn_frames(created, good, _TAPE) == [3]
    early = [_at((), None), _at(("P2",), 3), _at(("P2",), 6)]
    assert mr._extra_turn_frames(created, early, _TAPE) == []
    assert not mr.check_terminal(created, {}, _TAPE, early)
    # The spell never resolved: no creation, whatever the queue reads.
    assert mr._extra_turn_frames(created, good, []) == []


def test_p2s_next_turn_is_its_extra_turn_only_if_the_engine_consumed_the_entry() -> None:
    """Codex P1 (#536): P2's normal turn after P3's must not pass as its extra turn."""
    p3 = mr.TerminalCheck("events", event_type="BEGIN_TURN", where=(("player_player", "P3"),))
    p2 = mr.TerminalCheck("events", event_type="BEGIN_TURN", where=(("player_player", "P2"),))
    held = mr.TerminalCheck("pending_extra_turns_between", value=("P2",), after=p3, before=p2)
    consumed = mr.TerminalCheck("pending_extra_turns_between", value=(), after=p2)
    tape = [
        {"sequence": 10, "type": "BEGIN_TURN", "player_player": "P3"},
        {"sequence": 20, "type": "BEGIN_TURN", "player_player": "P2"},
    ]
    correct = [_at(("P3", "P2"), 9), _at(("P2",), 12), _at((), 21)]
    assert mr.check_terminal(held, {}, tape, correct)
    assert mr.check_terminal(consumed, {}, tape, correct)
    # The engine dropped P2's entry when P3's extra turn began.
    dropped = [_at(("P3", "P2"), 9), _at((), 12), _at((), 21)]
    assert not mr.check_terminal(held, {}, tape, dropped)
    # P2 took its normal turn and left the entry queued.
    ignored = [_at(("P3", "P2"), 9), _at(("P2",), 12), _at(("P2",), 21)]
    assert not mr.check_terminal(consumed, {}, tape, ignored)
    # The run never reached P2's turn.
    assert not mr.check_terminal(held, {}, tape[:1], correct)


def test_an_absent_pending_queue_is_never_read_as_a_drained_one() -> None:
    """#553 Audit 1 C1/C2: absence, null and junk stay unread, only [] is empty."""
    assert mr._pending_extra_turns({"pending_extra_turns": []}) == ()
    assert mr._pending_extra_turns({"pending_extra_turns": ["P2"]}) == ("P2",)
    for unread in (
        {},
        {"pending_extra_turns": None},
        {"pending_extra_turns": "P2"},
        {"pending_extra_turns": [2]},
        {"pending_extra_turns": {"P2": 1}},
        None,
    ):
        assert mr._pending_extra_turns(unread) is None
    # The terminal observation check fails closed on an absent field too.
    empty = mr.TerminalCheck("pending_extra_turns", value=())
    assert mr.check_terminal(empty, {"pending_extra_turns": []}, [], [])
    assert not mr.check_terminal(empty, {}, [], [])
    assert not mr.check_terminal(empty, {"pending_extra_turns": None}, [], [])
    # P2's consumed entry needs a frame that read the engine's empty queue; a
    # frame whose readback lacked the field cannot satisfy it.
    p2 = mr.TerminalCheck("events", event_type="BEGIN_TURN", where=(("player_player", "P2"),))
    consumed = mr.TerminalCheck("pending_extra_turns_between", value=(), after=p2)
    tape = [{"sequence": 20, "type": "BEGIN_TURN", "player_player": "P2"}]
    unread = mr._pending_extra_turns({})
    assert not mr.check_terminal(consumed, {}, tape, [_at(unread, 21)])
    assert mr.check_terminal(
        consumed, {}, tape, [_at(mr._pending_extra_turns({"pending_extra_turns": []}), 21)]
    )


class _ArrivalClient:
    def __init__(self, observation: Any) -> None:
        self.observation = observation

    def complete_arrival(self) -> dict[str, Any]:
        return {"observation": self.observation}


def test_a_frame_readback_without_the_queue_is_a_failed_read() -> None:
    """The readback site itself: an arrival without the field is never ``()``."""
    frame = mr.Frame("priority", "P1", [])
    mr._read_pending_extra_turns(frame, _ArrivalClient({}))
    assert frame.pending_extra_turns is None and frame.pending_read_failed
    frame = mr.Frame("priority", "P1", [])
    mr._read_pending_extra_turns(frame, _ArrivalClient({"pending_extra_turns": []}))
    assert frame.pending_extra_turns == () and not frame.pending_read_failed
    frame = mr.Frame("priority", "P1", [])
    mr._read_pending_extra_turns(frame, _ArrivalClient(None))
    assert frame.pending_extra_turns is None and frame.pending_read_failed


def test_a_failed_read_before_the_resolution_leaves_the_creation_unverified() -> None:
    created = mr.TerminalCheck(
        "extra_turn_created", principal="P2", value=("P2",), after=_WARP_RESOLVED
    )
    failed = mr.Frame("priority", "P1", [], tape_sequence=3, pending_read_failed=True)
    trace = [_at((), None), failed, _at(("P2",), 6)]
    assert mr._extra_turn_frames(created, trace, _TAPE) == []
    # A merely skipped readback in the same span still says nothing.
    skipped = [_at((), None), _at(None, 3), _at(("P2",), 6)]
    assert mr._extra_turn_frames(created, skipped, _TAPE) == [2]


def test_a_declared_library_channel_needs_the_players_own_shuffle() -> None:
    record = {"rules_randomness": {"channels": ["library_shuffle:P3", "coin_flip:obj:x"]}}
    shuffled = {"sequence": 11, "type": "LIBRARY_SHUFFLED", "player_player": "P3"}
    assert mr.declared_shuffle_channels(record, [shuffled]) == {"library_shuffle:P3": True}
    other = {**shuffled, "player_player": "P2"}
    assert mr.declared_shuffle_channels(record, [other]) == {"library_shuffle:P3": False}
    assert mr.declared_shuffle_channels(record, []) == {"library_shuffle:P3": False}
    assert mr.declared_shuffle_channels({"rules_randomness": {"channels": []}}, []) == {}


def _hand_offer(name: str, native: str) -> dict[str, Any]:
    return {
        "metadata": {
            "option_type": "object",
            "option_id": f"opt-{native}",
            "label": name,
            "xmage_option_metadata": {"object_id": native, "name": name, "zone": "hand"},
        }
    }


def _discard(value: Any, offers: list[dict[str, Any]], bounds: tuple[int, int] | None = (1, 1)):
    legal: dict[str, Any] = {"actions": offers}
    if bounds is not None:
        legal["decision"] = {"minimum_selections": bounds[0], "maximum_selections": bounds[1]}
    step = {
        "decision_family": "choose_object",
        "selection": {"selector_kind": "card_identity_multiset", "semantic_value": value},
    }
    return mr._scripted_answer(legal, step, {"obj:spell": "n-spell"}, mr.RowSpec())


def test_a_card_identity_multiset_selects_identical_template_cards() -> None:
    offers = [_hand_offer("Mountain", f"n-{index}") for index in range(8)]
    answer = _discard({"Mountain": 1}, offers)
    assert answer.option_ids == ("opt-n-0",)
    assert answer.key == "Mountain:1"
    two = _discard({"Mountain": 2}, offers, bounds=(2, 2))
    assert two.option_ids == ("opt-n-0", "opt-n-1")


@pytest.mark.parametrize(
    ("value", "offers", "bounds"),
    [
        # A named record object of the requested identity is never a template card.
        (
            {"Mountain": 1},
            [_hand_offer("Mountain", "n-0"), _hand_offer("Mountain", "n-spell")],
            (1, 1),
        ),
        # Fewer cards of the identity than requested.
        ({"Mountain": 2}, [_hand_offer("Mountain", "n-0"), _hand_offer("Island", "n-1")], (2, 2)),
        ({"Mountain": 1}, [_hand_offer("Island", "n-1")], (1, 1)),
        # A total the engine frame does not authorize, or no frame bounds.
        ({"Mountain": 1}, [_hand_offer("Mountain", "n-0")], (2, 2)),
        ({"Mountain": 1}, [_hand_offer("Mountain", "n-0")], None),
        # Malformed multisets.
        ({}, [_hand_offer("Mountain", "n-0")], (1, 1)),
        ({"Mountain": 0}, [_hand_offer("Mountain", "n-0")], (1, 1)),
        ({"Mountain": True}, [_hand_offer("Mountain", "n-0")], (1, 1)),
        (["Mountain"], [_hand_offer("Mountain", "n-0")], (1, 1)),
    ],
)
def test_a_card_identity_multiset_fails_closed(
    value: Any, offers: list[dict[str, Any]], bounds: tuple[int, int] | None
) -> None:
    with pytest.raises(ml.MidgameLaneError):
        _discard(value, offers, bounds)


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
    # #561: the game-start command-zone obligation, executed on XMage's own
    # constructed-state readback (Forge already executes it as written).
    "WS05-CMD-PARTNER-ZONE",
    "WS05-MP-ELIM-STACK-3",
    "WS05-MP-ELIM-CONTROL-3",
    # #441 residuals: rows whose scenario a reviewed sibling already executes.
    "PILOT_CHOOSE_OBJECT",
    "PILOT_REPLACEMENT_EFFECT",
    "PILOT_MANA_PAYMENT",
    "NEGATIVE_INTERNAL_AI",
    "PILOT_CHOICE",
    "PILOT_CHOOSE_ABILITY",
    # #441 contract 1.0.21: two causal extra turns.
    "WS05-MP-TURN-3",
    "WS05-MP-TURN-5",
    # #441 contract 1.0.21 E2b: the yes/no fail-closed sibling.
    "NEGATIVE_DEFAULT_YES_NO",
    # #441 contract 1.0.21 E3: Fact or Fiction cast through the causal stack.
    "PILOT_PILE",
    # #441 contract 1.0.21 E1: Path of Ancestry's scry 1 on XMage's card frame.
    "PILOT_CHOOSE_USE",
    # #441 contract 1.0.21: the layer tokens as discriminating readbacks.
    "MICRO_LAYERS",
    # #592: the parent-class fallback negative, whose omitted choose_object
    # handler the record declares itself (negative_fallback_probe).
    "NEGATIVE_PARENT_CLASS_FALLBACK",
}


def test_every_workstream_row_is_produced() -> None:
    assert set(mr.ROWS) >= WORKSTREAM_ROWS
    assert len(mr.ROWS) == 22 + len(WORKSTREAM_ROWS)
    # The partner-zone row is executed by Forge as written and now has its own
    # XMage spec (the game-start command-zone readback check).
    assert "WS05-CMD-PARTNER-ZONE" in mr.ROWS


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


def test_a_probe_refuses_only_a_frame_of_its_own_decision_class() -> None:
    """NEGATIVE_DEFAULT_YES_NO: P1's priority after the cast is not the probed
    yes/no frame; the probe's class decides which frame is refused."""
    probe = {
        "actor": "P1",
        "decision_family": "choose_use",
        "selection": {"selector_kind": "fail_closed_probe", "semantic_value": None},
    }
    assert mr.step_decision_class(probe) == "choose_use"
    assert mr.step_decision_class({**probe, "decision_family": "priority"}) == "priority"


def test_a_partition_is_asked_as_its_first_pile_on_the_object_frame() -> None:
    step = {
        "decision_family": "pile",
        "selection": {
            "selector_kind": "partition",
            "semantic_value": {"pile_a": ["obj:a", "obj:b"], "pile_b": ["obj:c"]},
        },
    }
    assert mr.step_decision_class(step) == "choose_object"
    label = {"decision_family": "pile", "selection": {"selector_kind": "pile_label"}}
    assert mr.step_decision_class(label) == "pile"
    assert mr._partition_first_pile(step["selection"]["semantic_value"]) == ["obj:a", "obj:b"]


@pytest.mark.parametrize(
    "value",
    [
        None,
        {"pile_a": ["obj:a"]},
        {"pile_a": [], "pile_b": ["obj:c"]},
        {"pile_a": ["obj:a"], "pile_b": []},
        {"pile_a": ["obj:a"], "pile_b": ["obj:a"]},
        {"pile_a": "obj:a", "pile_b": ["obj:c"]},
    ],
)
def test_a_malformed_partition_fails_closed(value: Any) -> None:
    with pytest.raises(ml.MidgameLaneError):
        mr._partition_first_pile(value)


def _pile_label_offer(label: str) -> dict[str, Any]:
    return {"metadata": {"option_type": "pile", "option_id": f"pile-{label}", "label": label}}


def test_a_pile_label_selects_exactly_the_named_pile() -> None:
    step = {"decision_family": "pile", "selection": {"selector_kind": "pile_label"}}
    offers = {"actions": [_pile_label_offer("Pile 1"), _pile_label_offer("Pile 2")]}
    chosen = mr._scripted_answer(
        offers,
        {**step, "selection": {**step["selection"], "semantic_value": "Pile 1"}},
        {},
        mr.RowSpec(),
    )
    assert mr._label_of(chosen.action) == "Pile 1"
    for bad in ("Pile 3", "", None):
        with pytest.raises(ml.MidgameLaneError):
            mr._scripted_answer(
                offers,
                {**step, "selection": {**step["selection"], "semantic_value": bad}},
                {},
                mr.RowSpec(),
            )


def test_a_scripted_frame_needs_the_principal_the_class_and_the_prompt() -> None:
    check = mr.TerminalCheck(
        "scripted_frame", principal="P2", value="choose_object", label="first pile"
    )
    asked = mr.Frame(
        "choose_object", "P2", [], scripted=True, prompt="Select cards to put in the first pile"
    )
    assert mr.check_terminal(check, {}, [], [asked])
    assert mr.bound_token_evidence(check, {}, [], [asked])["decision_frames"] == [0]
    for other in (
        mr.Frame("choose_object", "P3", [], scripted=True, prompt=asked.prompt),
        mr.Frame("choose_object", "P2", [], scripted=False, prompt=asked.prompt),
        mr.Frame("target", "P2", [], scripted=True, prompt=asked.prompt),
        mr.Frame("choose_object", "P2", [], scripted=True, prompt="Select a card to discard"),
    ):
        assert not mr.check_terminal(check, {}, [], [other])


SCRY_SPEC = mr.RowSpec(scry_binding="obj:top-known")
SCRY_PLACED = {"obj:top-known": "native-top"}


def _scry_step(value: Any, family: str = "choose_use") -> dict[str, Any]:
    return {
        "decision_family": family,
        "selection": {"selector_kind": "boolean", "semantic_value": value},
    }


def _scry_legal(natives: list[str], bounds: tuple[int, int] | None = (0, 1)) -> dict[str, Any]:
    legal: dict[str, Any] = {
        "actions": [
            {
                "metadata": {
                    "option_type": "object",
                    "option_id": f"opt-{native}",
                    "label": "Mountain",
                    "xmage_option_metadata": {"object_id": native, "name": "Mountain"},
                }
            }
            for native in natives
        ]
    }
    if bounds is not None:
        legal["decision"] = {"minimum_selections": bounds[0], "maximum_selections": bounds[1]}
    return legal


def test_a_bound_scry_is_answered_on_the_card_frame(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        mr,
        "_semantic_offers",
        lambda key, actions, placed: [
            a
            for a in actions
            if a["metadata"]["xmage_option_metadata"]["object_id"] == placed.get(key)
        ],
    )
    assert mr.answers_frame(_scry_step(False), "target", SCRY_SPEC)
    assert not mr.answers_frame(_scry_step(False), "choose_use", SCRY_SPEC)
    # Without the row's binding the yes/no step keeps XMage's yes/no class.
    assert mr.answers_frame(_scry_step(False), "choose_use", mr.RowSpec())
    keep = mr._scripted_answer(
        _scry_legal(["native-top"]), _scry_step(False), SCRY_PLACED, SCRY_SPEC
    )
    assert keep.action is None and keep.key == "false"
    bottom = mr._scripted_answer(
        _scry_legal(["native-top"]), _scry_step(True), SCRY_PLACED, SCRY_SPEC
    )
    assert bottom.option_ids == ("opt-native-top",) and bottom.key == "true"
    for legal, value in (
        (_scry_legal(["native-other"]), False),
        (_scry_legal(["native-top", "native-other"]), False),
        (_scry_legal(["native-top"], bounds=(1, 1)), False),
        (_scry_legal(["native-top"], bounds=None), False),
        (_scry_legal(["native-top"]), "false"),
    ):
        with pytest.raises(ml.MidgameLaneError):
            mr._scripted_answer(legal, _scry_step(value), SCRY_PLACED, SCRY_SPEC)


def test_a_scripted_key_needs_the_answered_frame() -> None:
    check = mr.TerminalCheck("scripted_key", principal="P1", value=("target", "false"))
    kept = mr.Frame("target", "P1", ["Mountain"], scripted=True, selected_key="false")
    assert mr.bound_token_evidence(check, {}, [], [kept])["decision_frames"] == [0]
    for other in (
        mr.Frame("target", "P1", ["Mountain"], scripted=True, selected_key="true"),
        mr.Frame("target", "P2", ["Mountain"], scripted=True, selected_key="false"),
        mr.Frame("target", "P1", ["Mountain"], scripted=False, selected_key="false"),
    ):
        assert not mr.check_terminal(check, {}, [], [other])


def _layers_observation(angel: dict, p1_bears: tuple[int, int], p3_bears: tuple[int, int]) -> dict:
    def bears(pt: tuple[int, int]) -> dict:
        return {"card_identity": "Grizzly Bears", "power": pt[0], "toughness": pt[1]}

    return {
        "seats": [
            {"player_id": "P1", "battlefield": [bears(p1_bears), bears(p1_bears)]},
            {"player_id": "P2", "battlefield": [{"card_identity": "Serra Angel", **angel}]},
            {"player_id": "P3", "battlefield": [bears(p3_bears)]},
        ]
    }


def _layer_tokens_hold(observation: dict) -> dict[str, bool]:
    spec = mr.ROWS["MICRO_LAYERS"]
    result = {}
    for token, binding in spec.token_bindings:
        checks = binding if isinstance(binding, tuple) else (binding,)
        result[token] = all(mr.check_terminal(check, observation, [], []) for check in checks)
    return result


def test_micro_layers_reads_each_layer_from_a_discriminating_permanent() -> None:
    # Humility and Glorious Anthem as the engine applies them (CR 613.4b-c).
    applied = _layers_observation({"power": 1, "toughness": 1}, (2, 2), (1, 1))
    assert _layer_tokens_hold(applied) == {
        "layer6_remove_abilities": True,
        "layer7b_set_pt:1/1": True,
        "layer7c_modify_pt:+1/+1": True,
    }
    # Humility ignored: a 4/4 flier with vigilance and 3/3 Bears.
    no_humility = _layers_observation(
        {"power": 4, "toughness": 4, "keywords": ["flying", "vigilance"]}, (3, 3), (2, 2)
    )
    assert not any(_layer_tokens_hold(no_humility).values())
    # Anthem ignored: P1's Bears are 1/1, so only layer 7c fails.
    no_anthem = _layers_observation({"power": 1, "toughness": 1}, (1, 1), (1, 1))
    assert _layer_tokens_hold(no_anthem) == {
        "layer6_remove_abilities": True,
        "layer7b_set_pt:1/1": True,
        "layer7c_modify_pt:+1/+1": False,
    }


def test_a_keyword_absent_check_needs_the_permanent() -> None:
    check = mr.TerminalCheck(
        "keyword_absent", principal="P2", card_identity="Serra Angel", value="flying"
    )
    assert mr.needs_observation(check)
    assert not mr.check_terminal(
        check, {"players": [{"player_id": "P2", "battlefield": []}]}, [], []
    )
