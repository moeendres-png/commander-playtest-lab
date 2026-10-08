"""#441 XMage residual rows whose scenario a reviewed sibling already executes.

Each binding names what the record's token means on the engine and nothing
weaker: the wrong-reason controls below show that the evidence of another
object, another player, another question, a second question or a different
payment does not satisfy it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from commander_lab.qualification.current_boundary import midgame_lane as ml
from commander_lab.qualification.current_boundary import midgame_rows as mr
from commander_lab.qualification.current_boundary.materialization import (
    load_effective_materialization,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _binding(fixture_id: str, token: str) -> Any:
    return dict(mr.ROWS[fixture_id].token_bindings)[token]


def _evidence(
    check: Any, tape: list[dict[str, Any]], trace: list[mr.Frame]
) -> dict[str, Any] | None:
    return mr.bound_token_evidence(check, {}, tape, trace)


def _move(sequence: int, obj: str, source: str, destination: str) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "type": "ZONE_CHANGE",
        "target_object": obj,
        "from": source,
        "to": destination,
    }


# --------------------------------------------------------------------------- #
# PILOT_CHOOSE_OBJECT: the discarded card is the Mountain, and only it
# --------------------------------------------------------------------------- #

DISCARD = ("PILOT_CHOOSE_OBJECT", "object_selected:obj:p1-hand-a")


def test_the_chosen_card_is_discarded_and_the_other_stays() -> None:
    check = _binding(*DISCARD)
    tape = [_move(9, "obj:p1-hand-a", "HAND", "GRAVEYARD")]
    assert _evidence(check, tape, []) is not None


def test_discarding_the_other_card_or_both_is_not_the_selection() -> None:
    check = _binding(*DISCARD)
    for tape in (
        [_move(9, "obj:p1-hand-b", "HAND", "GRAVEYARD")],
        [
            _move(9, "obj:p1-hand-a", "HAND", "GRAVEYARD"),
            _move(10, "obj:p1-hand-b", "HAND", "GRAVEYARD"),
        ],
        # The chosen card leaving the hand some other way is not a discard.
        [_move(9, "obj:p1-hand-a", "HAND", "EXILED")],
        [],
    ):
        assert _evidence(check, tape, []) is None, tape


# --------------------------------------------------------------------------- #
# PILOT_REPLACEMENT_EFFECT: the CR 903.9b question, asked of P1 exactly once
# --------------------------------------------------------------------------- #

HAND_PROMPT = "Move Rograkh, Son of Rohgahh [dd2] to command zone instead of your hand?"
FRAME = ("PILOT_REPLACEMENT_EFFECT", "replacement_effect_frame:P1")


def _question(
    principal: str = "P1", prompt: str = HAND_PROMPT, cls: str = "choose_use"
) -> mr.Frame:
    return mr.Frame(
        cls,
        principal,
        ["Yes", "No"],
        selected_label="Yes",
        scripted=True,
        selected_key="true",
        prompt=prompt,
    )


def test_the_replacement_frame_is_the_owners_command_zone_question() -> None:
    assert _evidence(_binding(*FRAME), [], [_question()]) is not None


def test_another_player_another_question_or_a_second_ask_is_not_the_frame() -> None:
    check = _binding(*FRAME)
    for trace in (
        [],
        [_question(principal="P2")],
        [_question(prompt="Use Path of Ancestry's ability?")],
        # The graveyard choice (CR 903.9a) is asked after the move, not instead of it.
        [
            _question(
                prompt="Move Rograkh to the command zone or leave it in current zone (GRAVEYARD)?"
            )
        ],
        [_question(cls="priority")],
        [_question(), _question()],
    ):
        assert _evidence(check, [], trace) is None, trace


def test_the_replacement_answer_is_the_vocabularys_command_zone_choice() -> None:
    binding = _binding("PILOT_REPLACEMENT_EFFECT", "commander_replacement_chosen:command")
    assert binding == mr.VocabularyToken("commander_choice:command")


# --------------------------------------------------------------------------- #
# PILOT_MANA_PAYMENT: two blue mana charged for the one Counterspell
# --------------------------------------------------------------------------- #

PAYMENT = ("PILOT_MANA_PAYMENT", "mana_paid:UU")
CAST = {
    "sequence": 10,
    "type": "SPELL_CAST",
    "source_object": "obj:counterspell",
    "player_player": "P1",
}


def _tap() -> mr.Frame:
    return mr.Frame(
        "mana_payment",
        "P1",
        ["Island — {T}: Add {U}."],
        selected_label="Island — {T}: Add {U}.",
        selected_option_type="mana_ability",
        scripted=True,
    )


def _spend(color: str = "blue") -> mr.Frame:
    label = f"Spend {color} mana from pool"
    return mr.Frame(
        "mana_payment",
        "P1",
        [label],
        selected_label=label,
        selected_option_type="mana_pool",
        scripted=True,
    )


def test_two_blue_mana_charged_for_the_one_counterspell_is_the_payment() -> None:
    trace = [_tap(), _spend(), _tap(), _spend()]
    assert _evidence(_binding(*PAYMENT), [CAST], trace) is not None


def test_another_amount_color_cast_count_or_floating_mana_is_not_the_payment() -> None:
    check = _binding(*PAYMENT)
    paid = [_tap(), _spend(), _tap(), _spend()]
    for tape, trace in (
        ([CAST], [_tap(), _spend()]),
        ([CAST], [_tap(), _spend("red"), _tap(), _spend("red")]),
        # A tapped mana that was never spent floated: the charge is unmeasured.
        ([CAST], [_tap(), _spend(), _tap(), _spend(), _tap()]),
        ([], paid),
        ([CAST, {**CAST, "sequence": 11}], paid),
        ([{**CAST, "player_player": "P2"}], paid),
    ):
        assert _evidence(check, tape, trace) is None, (tape, trace)


def test_the_payment_is_made_only_from_the_records_islands() -> None:
    assert mr.ROWS["PILOT_MANA_PAYMENT"].mana_sources == ("obj:island-a", "obj:island-b")


# --------------------------------------------------------------------------- #
# NEGATIVE rows
# --------------------------------------------------------------------------- #


def test_the_attack_refusal_is_verified_by_the_records_vocabulary_alone() -> None:
    assert mr.ROWS["NEGATIVE_INTERNAL_AI"] == mr.RowSpec()


def test_the_yes_no_refusal_runs_only_on_its_reachable_scenario() -> None:
    # Contract 1.0.21 E2b replaced the scry (a card selection on XMage) with
    # Garruk's Packleader's optional draw, a genuine yes/no question caused by
    # a scripted Centaur Courser cast; the spec pays only from the record's
    # declared Forests, and the probe refuses the record's choose_use frame.
    record = load_effective_materialization(REPO_ROOT).record("NEGATIVE_DEFAULT_YES_NO")
    assert "Packleader" in record["negative_fallback_probe"]["production_reachable_trigger"]
    (cost,) = record["action_cost_state"]
    spec = mr.ROWS["NEGATIVE_DEFAULT_YES_NO"]
    assert spec.mana_sources == tuple(cost["explicit_payment_sources"])
    probe = record["decision_script"][-1]
    assert probe["selection"]["selector_kind"] == "fail_closed_probe"
    assert mr.step_decision_class(probe) == "choose_use"


# --------------------------------------------------------------------------- #
# NEGATIVE_PARENT_CLASS_FALLBACK: the record declares its omitted handler
# --------------------------------------------------------------------------- #

PARENT_CLASS = "NEGATIVE_PARENT_CLASS_FALLBACK"


def _parent_class_record() -> dict[str, Any]:
    return load_effective_materialization(REPO_ROOT).record(PARENT_CLASS)


class _OmissionClient:
    """A fake mid-game lane whose engine offers the record's own frames.

    ``fallback_answers`` models the wrong reason: a bridge that silently
    answers the frame through its parent engine class instead of waiting for
    the external client. The second read of the pending choose_object frame
    then finds it gone, with a discard already on the tape.
    """

    def __init__(self, decisions: list[dict[str, Any]], *, fallback_answers: bool = False) -> None:
        self._decisions = list(decisions)
        self._fallback_answers = fallback_answers
        self._object_reads = 0
        self.offset = 0
        self.tape: list[dict[str, Any]] = []
        self.submissions: list[Any] = []
        self._events: list[dict[str, Any]] = []
        self.engine_commit = "e" * 40

    def pending_decision(
        self, *, attempts: int = 60, interval_s: float = 0.5
    ) -> dict[str, Any] | None:
        if self._decisions and self._decisions[0].get("decision_class") == "choose_object":
            self._object_reads += 1
            if self._fallback_answers and self._object_reads > 1:
                self._decisions.pop(0)
                self.offset += 1
                self._events.append(
                    {
                        "sequence": self.offset,
                        "type": "ZONE_CHANGE",
                        "from": "HAND",
                        "to": "GRAVEYARD",
                        "player_player": "P1",
                    }
                )
        return self._decisions[0] if self._decisions else None

    def events(self, after_offset: int = 0) -> dict[str, Any]:
        return {
            "latest_offset": self.offset,
            "events": [e for e in self._events if e["sequence"] > after_offset],
        }

    def complete_arrival(self) -> dict[str, Any]:
        pending = self._decisions[0] if self._decisions else None
        if pending is not None and pending.get("decision_class") == "choose_object":
            # The record's scripted cleanup discard is the turn-1 CLEANUP one
            # (contract 1.0.26 declares turn/phase on the step).
            return {
                "construction_match": True,
                "mismatches": [],
                "observation": {
                    "phase": "CLEANUP",
                    "step": "CLEANUP",
                    "priority_player": "P1",
                    "turn_number": 1,
                },
            }
        # The record's declared checkpoint is turn 2 (P2 active); a turn-1
        # readback is not that checkpoint.
        return {
            "construction_match": True,
            "mismatches": [],
            "observation": {
                "phase": "PRECOMBAT_MAIN",
                "step": "PRECOMBAT_MAIN",
                "priority_player": "P1",
                "turn_number": 2,
            },
        }

    def request(self, message_type: str, payload: Any = None) -> dict[str, Any]:
        if message_type == "get_legal_actions":
            seat = self._decisions[0].get("seat", 0) if self._decisions else 0
            return {"success": True, "payload": self._legal(seat)}
        if message_type == "submit_action":
            pending = self._decisions[0] if self._decisions else None
            assert pending is not None and pending["decision_class"] == "choose_object", (
                "the declared omission must submit no action for its frame"
            )
            self.submissions.append([payload["proposal"]["legal_action_id"]])
            self._decisions.pop(0)
            return {"success": True, "payload": {}}
        raise AssertionError(f"unexpected lane request {message_type}")

    def submit_options(self, decision: dict[str, Any], option_ids: list[str]) -> None:
        assert decision["decision_class"] in ("priority", "cleanup_discard"), (
            "the declared omission must submit no answer for its frame"
        )
        self.submissions.append(list(option_ids))
        if self._decisions:
            self._decisions.pop(0)

    @staticmethod
    def _legal(seat: int) -> dict[str, Any]:
        return {
            "actor_id": f"actor-{seat}",
            "decision": {"minimum_selections": 1, "maximum_selections": 1},
            "actions": [
                {
                    "action_id": f"opt-hand-{name.lower()}",
                    "action_type": "discard",
                    "metadata": {
                        "label": f"{name} — discard",
                        "option_id": f"opt-hand-{name.lower()}",
                        "seat": seat,
                        "xmage_option_metadata": {
                            "name": name,
                            "object_id": f"hand-{name.lower()}-{seat}",
                        },
                    },
                }
                for name in ("Mountain", "Island")
            ],
        }


def _cleanup_frame(seat: int = 0) -> dict[str, Any]:
    # XMage publishes the forced cleanup discard (CR 514.1) as its own
    # choose_object frame over the hand (midgame_rows.ENGINE_DECISION_CLASS maps
    # the record's cleanup_discard family onto that engine class).
    return {
        "decision_id": "d-cleanup",
        "decision_class": "choose_object",
        "actor_id": f"actor-{seat}",
        "seat": seat,
        "prompt": "Discard down to your maximum hand size",
    }


def _priority(seat: int = 0) -> dict[str, Any]:
    return {
        "decision_id": "d-priority",
        "decision_class": "priority",
        "actor_id": f"actor-{seat}",
        "seat": seat,
        "legal_options": [{"option_type": "pass_priority", "option_id": "pass"}],
    }


def _discard_frame(seat: int = 0) -> dict[str, Any]:
    return {
        "decision_id": "d-discard",
        "decision_class": "choose_object",
        "actor_id": f"actor-{seat}",
        "seat": seat,
        "prompt": "Choose a card to discard",
    }


def test_the_parent_class_record_declares_its_omitted_handler() -> None:
    record = _parent_class_record()
    assert mr.ROWS[PARENT_CLASS] == mr.RowSpec()
    assert mr.declared_omission_probe(record) == ("choose_object", "P1")
    # The probe is record-driven: without the expected actor it must not fire.
    stripped = {**record, "native_procedure": []}
    assert mr.declared_omission_probe(stripped) is None


def test_the_omission_refusal_is_verified_with_no_answer_applied() -> None:
    record = _parent_class_record()
    client = _OmissionClient([_cleanup_frame(), _priority(), _discard_frame()])
    execution = mr.execute_row(client, record, {}, mr.ROWS[PARENT_CLASS])
    assert execution.verified, execution.detail
    assert execution.detail == "obligation observed"
    # The record's own scripted turn-1 cleanup discard (CR 514.1) is answered
    # first, then the checkpoint priority is passed; the refused frame itself is
    # never answered (the fake rejects any other submission).
    assert client.submissions == [["opt-hand-mountain"], ["pass"]]
    (refusal,) = execution.refusals
    assert refusal["well_formed"] is True
    assert refusal["decision_class"] == "choose_object"
    assert refusal["kind"] == mr.refusal_mod.TYPED_UNSUPPORTED_DISCRETIONARY_DECISION
    assert execution.token_evidence["decision_frame:choose_object"]["decision_frames"]
    assert execution.token_evidence["fail_closed:UNSUPPORTED_DISCRETIONARY_DECISION"][
        "refusal_frame_digests"
    ]


def test_a_parent_class_fallback_that_answers_the_frame_is_never_a_pass() -> None:
    """Wrong-reason control: if the engine's own/AI choice answered the frame
    through the parent class, the frame would be gone and the tape advanced;
    the no-mutation refusal cannot be established and the row fails closed."""
    record = _parent_class_record()
    client = _OmissionClient([_priority(), _discard_frame()], fallback_answers=True)
    execution = mr.execute_row(client, record, {}, mr.ROWS[PARENT_CLASS])
    assert not execution.verified
    assert "declared omission refusal failed closed" in execution.detail
    assert execution.refusals == []


def test_the_omission_refusal_fires_only_for_the_declared_actor() -> None:
    record = _parent_class_record()
    client = _OmissionClient([_priority(seat=1), _discard_frame(seat=1)])
    execution = mr.execute_row(client, record, {}, mr.ROWS[PARENT_CLASS])
    assert not execution.verified
    assert "unscripted choose_object for P2" in execution.detail
    assert execution.refusals == []
    assert client.submissions == [["pass"]]


# --------------------------------------------------------------------------- #
# PILOT_CHOICE: the record's named choice on the engine's own choice frame
# --------------------------------------------------------------------------- #

COLORS = ("Black", "Blue", "Green", "Red", "White")
CHOOSE_RED = {
    "decision_family": "choice",
    "selection": {"selector_kind": "semantic_choice_key", "semantic_value": "RED"},
}


def _choice_offer(text: str, *, key: str | None = None, option_type: str = "choice") -> dict:
    engine: dict[str, Any] = {"choice": text}
    if key is not None:
        engine["choice_key"] = key
    return {
        "metadata": {
            "option_type": option_type,
            "option_id": f"choice-{key or text}",
            "label": text,
            "xmage_option_metadata": engine,
        }
    }


def _answer(offers: list[dict], step: dict = CHOOSE_RED) -> mr.ScriptedAnswer:
    return mr._scripted_answer({"actions": offers}, step, {}, mr.RowSpec())


def test_the_choice_key_selects_exactly_the_engine_offer_it_names() -> None:
    answer = _answer([_choice_offer(color) for color in COLORS])
    assert mr._label_of(answer.action) == "Red"
    assert answer.key == "RED"
    # A keyed menu is matched by the engine's key, not by its display text.
    keyed = _answer([_choice_offer("Pay life", key="red"), _choice_offer("Red", key="other")])
    assert mr._label_of(keyed.action) == "Pay life"


@pytest.mark.parametrize("requested", ["red", "Red", " RED ", "rEd"])
def test_the_requested_key_is_normalized_like_the_offers(requested: str) -> None:
    step = {**CHOOSE_RED, "selection": {**CHOOSE_RED["selection"], "semantic_value": requested}}
    answer = _answer([_choice_offer(color) for color in COLORS], step)
    assert mr._label_of(answer.action) == "Red"
    assert answer.key == "RED"
    spaced = {**CHOOSE_RED, "selection": {**CHOOSE_RED["selection"], "semantic_value": "Red Blue"}}
    assert _answer([_choice_offer("red  blue"), _choice_offer("Red")], spaced).key == "RED_BLUE"


@pytest.mark.parametrize("requested", [None, "", "  ", 7])
def test_a_missing_requested_key_fails_closed(requested: Any) -> None:
    step = {**CHOOSE_RED, "selection": {**CHOOSE_RED["selection"], "semantic_value": requested}}
    with pytest.raises(ml.MidgameLaneError):
        _answer([_choice_offer(color) for color in COLORS], step)


@pytest.mark.parametrize(
    "offers",
    [
        # Not offered: a partial or fuzzy match never selects.
        [_choice_offer(color) for color in ("Black", "Blue", "Green", "White")],
        [_choice_offer("Reddish"), _choice_offer("Infrared")],
        # Offered twice: ambiguous.
        [_choice_offer("Red"), _choice_offer("red")],
        # The right text on another kind of offer is not a choice.
        [_choice_offer("Red", option_type="target")],
    ],
)
def test_a_choice_the_engine_did_not_offer_once_fails_closed(offers: list[dict]) -> None:
    with pytest.raises(ml.MidgameLaneError):
        _answer(offers)


def _choice_frame(**overrides: Any) -> mr.Frame:
    fields: dict[str, Any] = {
        "selected_label": "Red",
        "scripted": True,
        "selected_key": "RED",
    }
    fields.update(overrides)
    decision_class = fields.pop("decision_class", "choice")
    return mr.Frame(decision_class, "P1", list(COLORS), **fields)


def test_the_choice_token_is_the_scripted_answer_on_the_choice_frame() -> None:
    assert mr.verify_token("choice:RED", [], [_choice_frame()], set()) is not None


@pytest.mark.parametrize(
    "frame",
    [
        _choice_frame(scripted=False),
        _choice_frame(selected_key="GREEN", selected_label="Green"),
        _choice_frame(selected_label="Crimson"),
        _choice_frame(decision_class="mode"),
    ],
)
def test_another_answer_an_unscripted_or_unoffered_one_is_not_the_choice(frame: mr.Frame) -> None:
    assert mr.verify_token("choice:RED", [], [frame], set()) is None


def test_the_choice_row_runs_on_the_records_vocabulary() -> None:
    assert mr.ROWS["PILOT_CHOICE"] == mr.RowSpec()


# --------------------------------------------------------------------------- #
# PILOT_CHOOSE_ABILITY: the record's ability key, activated on the priority frame
# --------------------------------------------------------------------------- #

JESKA = "native-jeska"
ZERO = "Jeska, Thrice Reborn — 0: Choose target creature. Until your next turn, ..."
MINUS_X = "Jeska, Thrice Reborn — -X: {this} deals X damage to each of up to three targets."
CHOOSE_ZERO = {
    "actor": "P1",
    "decision_family": "choose_ability",
    "selection": {
        "selector_kind": "semantic_ability_key",
        "semantic_value": "loyalty_0_triple_damage",
    },
}


def _activation(label: str, source: str = JESKA, ability_type: str = "activated") -> dict:
    return {
        "metadata": {
            "option_type": "activated_ability",
            "option_id": f"opt-{label[:12]}-{source}",
            "label": label,
            "xmage_option_metadata": {"source_object_id": source, "ability_type": ability_type},
        }
    }


def _ability_answer(offers: list[dict]) -> dict:
    spec = mr.ROWS["PILOT_CHOOSE_ABILITY"]
    return mr._ability_choice_answer(
        {"actions": offers},
        "loyalty_0_triple_damage",
        spec,
        {
            "obj:jeska": JESKA,
        },
    )


def test_the_ability_key_activates_exactly_the_bound_ability_of_its_source() -> None:
    assert mr._is_ability_choice(CHOOSE_ZERO)
    assert mr._label_of(_ability_answer([_activation(MINUS_X), _activation(ZERO)])) == ZERO


@pytest.mark.parametrize(
    "offers",
    [
        [_activation(MINUS_X)],
        # The same ability of another permanent is not the record's source.
        [_activation(MINUS_X), _activation(ZERO, source="native-other")],
        [_activation(ZERO), _activation(ZERO)],
        # A cast is never an activation.
        [_activation(ZERO, ability_type="spell")],
    ],
)
def test_an_ability_the_engine_did_not_offer_once_for_the_source_fails_closed(
    offers: list[dict],
) -> None:
    with pytest.raises(ml.MidgameLaneError):
        _ability_answer(offers)


def test_an_unbound_ability_key_fails_closed() -> None:
    with pytest.raises(ml.MidgameLaneError):
        mr._ability_choice_answer({"actions": [_activation(ZERO)]}, "loyalty_0", mr.RowSpec(), {})


def _ability_frame(**overrides: Any) -> mr.Frame:
    fields: dict[str, Any] = {
        "selected_label": ZERO,
        "scripted": True,
        "selected_key": "ability:loyalty_0_triple_damage",
    }
    fields.update(overrides)
    principal = fields.pop("principal", "P1")
    decision_class = fields.pop("decision_class", "priority")
    return mr.Frame(decision_class, principal, ["Pass priority", MINUS_X, ZERO], **fields)


def test_the_ability_tokens_are_the_scripted_activation_on_the_priority_frame() -> None:
    trace = [_ability_frame()]
    assert mr.verify_token("choose_ability_frame:P1", [], trace, set()) is not None
    assert mr.verify_token("ability_selected:loyalty_0_triple_damage", [], trace, set()) is not None


@pytest.mark.parametrize(
    "frame",
    [
        _ability_frame(scripted=False),
        _ability_frame(selected_key="ability:other_key"),
        _ability_frame(selected_label="Jeska — 0: something the engine did not offer"),
        _ability_frame(decision_class="mode"),
    ],
)
def test_another_unscripted_or_unoffered_activation_is_not_the_ability(frame: mr.Frame) -> None:
    assert mr.verify_token("ability_selected:loyalty_0_triple_damage", [], [frame], set()) is None


@pytest.mark.parametrize(
    "frame",
    [
        _ability_frame(scripted=False),
        _ability_frame(selected_label="Jeska — 0: something the engine did not offer"),
        _ability_frame(decision_class="mode"),
    ],
)
def test_an_unscripted_or_unoffered_activation_is_not_an_ability_frame(frame: mr.Frame) -> None:
    assert mr.verify_token("choose_ability_frame:P1", [], [frame], set()) is None


def test_the_ability_frame_is_the_named_players() -> None:
    # A plain priority pass is not an ability choice, and P2's frame is not P1's.
    assert (
        mr.verify_token("choose_ability_frame:P1", [], [_ability_frame(principal="P2")], set())
        is None
    )
    passed = _ability_frame(selected_key=None, selected_label="Pass priority")
    assert mr.verify_token("choose_ability_frame:P1", [], [passed], set()) is None
