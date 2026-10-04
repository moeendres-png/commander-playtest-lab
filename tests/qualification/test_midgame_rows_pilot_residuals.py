"""#441 XMage residual rows whose scenario a reviewed sibling already executes.

Each binding names what the record's token means on the engine and nothing
weaker: the wrong-reason controls below show that the evidence of another
object, another player, another question, a second question or a different
payment does not satisfy it.
"""

from __future__ import annotations

from typing import Any

import pytest

from commander_lab.qualification.current_boundary import midgame_lane as ml
from commander_lab.qualification.current_boundary import midgame_rows as mr


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


def test_the_yes_no_refusal_has_no_spec_until_its_scenario_is_reachable() -> None:
    # Its record's known library top card is not restored by the lane, and
    # XMage asks scry as a card selection rather than a yes/no question.
    assert "NEGATIVE_DEFAULT_YES_NO" not in mr.ROWS


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
