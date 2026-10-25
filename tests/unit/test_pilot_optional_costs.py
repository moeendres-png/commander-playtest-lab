"""Optional costs and alternative costs follow what the seat can pay (#989 phase 5b).

Real games on the pinned engine: of 136 cancelled payments in 24 games, 80 could not be paid from
the first prompt, and about half of those were a choice the pilot made before the payment. The
engine offers a cast because a cheaper way is payable (Shriekmaw's Evoke {1}{B}), asks "Pay Kicker
{3}{B} ?" after checking that one cost, and asks a "you may pay" trigger the same way. The pilot
answered by ranking alone: the full {4}{B} with four sources, the kicker on a {1}{B} creature with
three lands. The payment was cancelled, and the spell was not cast at all.

These tests pin the model's answer to those offers, that the pilot follows it, and the controls
that a cost it can pay, a board it cannot read and a spell whose cost can change are left alone.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from commander_lab.engine.rules.full_game_pilot.common import (
    _alternative_cost_of,
    _alternative_cost_spell,
    _optional_mana_cost,
    _printed_spell_cost,
)
from commander_lab.engine.rules.full_game_pilot_payment_plan import can_pay
from tests.unit.test_full_game_pilot_mana_and_may import (
    _option,
    _policy,
    _request,
    _state,
)


def _tap(option_id: str, effect: str, source: str = "") -> Any:
    return _option(
        option_id,
        "mana_ability",
        f"Land — {{T}}: Add {effect}.",
        source_object_id=source or option_id,
        requires_tap_source=True,
        source_tapped=False,
    )


@pytest.mark.parametrize(
    ("offer", "cost", "expected"),
    [
        ([_tap("a", "{B}"), _tap("b", "{B}"), _tap("c", "{B}")], "{1}{B}", True),
        ([_tap("a", "{B}"), _tap("b", "{B}"), _tap("c", "{B}")], "{1}{B}{3}{B}", False),
        ([_tap("a", "{B}"), _tap("b", "{B}"), _tap("c", "{B}")], "{3}{B}", False),
        ([_tap("a", "{R}"), _tap("b", "{R}")], "{B}", False),
        ([_tap("a", "{C}{C}"), _tap("b", "{B}"), _tap("c", "{B}")], "{3}{B}", True),
        ([_tap("a", "{B}", "x"), _tap("b", "{U}", "x")], "{1}{B}", False),
        ([], "{0}", True),
    ],
)
def test_the_whole_cost_is_paid_from_the_offered_sources(
    offer: list[Any], cost: str, expected: bool
) -> None:
    assert can_pay(offer, cost) is expected


def test_the_pool_counts_towards_the_whole_cost() -> None:
    pool = _option("pool-b", "mana_pool", "Spend B", mana_type="black", mana_available=2)
    assert can_pay([pool, _tap("a", "{B}")], "{2}{B}") is True
    assert can_pay([pool], "{2}{B}") is False


@pytest.mark.parametrize("cost", ["{X}{U}", "{T}", "{S}"])
def test_a_cost_it_does_not_know_is_not_judged(cost: str) -> None:
    assert can_pay([_tap("a", "{B}")], cost) is None


def test_a_source_it_cannot_read_is_not_judged() -> None:
    odd = _option("odd", "mana_ability", "Cabal Coffers — {2}, {T}: Add {B} for each Swamp.")
    assert can_pay([_tap("a", "{B}"), odd], "{B}") is None


@pytest.mark.parametrize(
    ("prompt", "cost"),
    [
        ("Pay Kicker {3}{B} ?", "{3}{B}"),
        ("Pay 2 times Multikicker {2} ?", "{2}"),
        ("Pay {5} and tap all creatures your opponents control?", "{5}"),
        ("Pay {1}?", "{1}"),
        ("{3}, Pay 3 life?", "{3}"),
        ("Pay {2}{W} and return this card from your graveyard to the battlefield?", "{2}{W}"),
        ("Pay 2 life instead of {B}?", None),
        ("Pay 1 life and look at the next 5 cards?", None),
        ("Cast Storm-Kiln Artist? (You still pay the costs)", None),
        ("Draw a card?", None),
    ],
)
def test_the_mana_a_may_prompt_asks_for(prompt: str, cost: str | None) -> None:
    assert _optional_mana_cost(prompt) == cost


def test_the_alternative_cost_question_is_read_from_the_engine_text() -> None:
    prompt = (
        "You may choose an alternative cost for casting <font color='#696969'>Shriekmaw</font> [#]"
    )
    assert _alternative_cost_spell(prompt) == "Shriekmaw"
    assert _alternative_cost_spell("Choose a creature type") is None
    assert (
        _alternative_cost_of(
            "Cast with Evoke alternative cost: {1}{B} (source: <font>Shriekmaw</font>)"
        )
        == "{1}{B}"
    )
    assert _alternative_cost_of("Cast with no alternative cost: {4}{B}") == "{4}{B}"
    assert _alternative_cost_of("Cast with Evoke alternative cost: Exile a black card") is None


def test_the_printed_cost_is_read_only_for_a_spell_whose_cost_cannot_change() -> None:
    assert _printed_spell_cost("Nullpriest of Oblivion") == "{1}{B}"
    # "costs {3} less to cast if it targets a creature that was dealt damage this turn"
    assert _printed_spell_cost("Bitter Downfall") is None
    assert _printed_spell_cost("A Card Nobody Printed") is None


def _board(*lands: str, pool: dict[str, int] | None = None, unreadable: bool = False) -> Any:
    """A precombat-main state whose actor controls one untapped permanent per rule text."""
    state = copy.deepcopy(_state(step="precombat_main"))
    actor = state["players"][0]
    actor["battlefield"] = [
        {"object_id": f"perm-{index}", "name": "Land", "tapped": False, "abilities": [rule]}
        for index, rule in enumerate(lands)
    ]
    if unreadable:
        actor["battlefield"].append({"object_id": "odd", "name": "Mystery", "tapped": False})
    if pool:
        actor["mana_pool"].update(pool)
    return state


_SWAMP = "{T}: Add {B}."


def _ask(
    prompt: str, state: Any, source: dict[str, Any] | None, *, outcome: str, offset: int
) -> Any:
    request = _request(
        "choose_use",
        [
            _option("yes", "boolean", "Yes", value=True),
            _option("no", "boolean", "No", value=False),
        ],
        context={"outcome": outcome},
        prompt=prompt,
        offset=offset,
        state=state,
    )
    if source is not None:
        request["source_object"] = source
    return request


def _answer(request: dict[str, Any]) -> str:
    return str(_policy().decide(request)["selected_option_ids"][0])


_NULLPRIEST = {"ability_type": "spell", "source_name": "Nullpriest of Oblivion"}
_KICKER = "Pay Kicker {3}{B} ?"


def test_a_kicker_the_lands_cannot_pay_on_top_of_the_spell_is_declined() -> None:
    board = _board(_SWAMP, _SWAMP, _SWAMP)
    assert _answer(_ask(_KICKER, board, _NULLPRIEST, outcome="aidontuseit", offset=1)) == "no"


def test_a_kicker_the_lands_can_pay_is_answered_as_before() -> None:
    board = _board(*[_SWAMP] * 6)
    assert _answer(_ask(_KICKER, board, _NULLPRIEST, outcome="aidontuseit", offset=1)) == "yes"


def test_a_kicker_is_left_to_the_pilot_when_the_spell_itself_cannot_be_paid() -> None:
    board = _board(_SWAMP)
    assert _answer(_ask(_KICKER, board, _NULLPRIEST, outcome="aidontuseit", offset=1)) == "yes"


def test_a_kicker_is_left_to_the_pilot_when_a_permanent_states_no_abilities() -> None:
    board = _board(_SWAMP, _SWAMP, _SWAMP, unreadable=True)
    assert _answer(_ask(_KICKER, board, _NULLPRIEST, outcome="aidontuseit", offset=1)) == "yes"


def test_a_kicker_is_left_to_the_pilot_when_the_spells_cost_can_change() -> None:
    board = _board(_SWAMP, _SWAMP, _SWAMP)
    source = {"ability_type": "spell", "source_name": "Bitter Downfall"}
    assert _answer(_ask(_KICKER, board, source, outcome="aidontuseit", offset=1)) == "yes"


def test_a_tapped_land_pays_nothing() -> None:
    board = _board(*[_SWAMP] * 6)
    for permanent in board["players"][0]["battlefield"][:4]:
        permanent["tapped"] = True
    assert _answer(_ask(_KICKER, board, _NULLPRIEST, outcome="aidontuseit", offset=1)) == "no"


def test_floating_mana_pays_towards_the_kicker() -> None:
    board = _board(_SWAMP, _SWAMP, _SWAMP, pool={"black": 3})
    assert _answer(_ask(_KICKER, board, _NULLPRIEST, outcome="aidontuseit", offset=1)) == "yes"


def test_a_you_may_pay_trigger_the_lands_cannot_pay_is_declined() -> None:
    board = _board(*[_SWAMP] * 4)
    trigger = {"ability_type": "triggered_nonmana", "source_name": "Monstrosity of the Lake"}
    prompt = "Pay {5} and tap all creatures your opponents control?"
    assert _answer(_ask(prompt, board, trigger, outcome="benefit", offset=1)) == "no"


def test_a_you_may_pay_trigger_the_lands_can_pay_is_paid() -> None:
    board = _board(*[_SWAMP] * 5)
    trigger = {"ability_type": "triggered_nonmana", "source_name": "Monstrosity of the Lake"}
    prompt = "Pay {5} and tap all creatures your opponents control?"
    assert _answer(_ask(prompt, board, trigger, outcome="benefit", offset=1)) == "yes"


def test_a_multikicker_with_no_mana_for_a_single_payment_is_declined() -> None:
    board = _board()
    chalice = {"ability_type": "spell", "source_name": "Everflowing Chalice"}
    prompt = "Pay 1 time Multikicker {2} ?"
    assert _answer(_ask(prompt, board, chalice, outcome="aidontuseit", offset=1)) == "no"


def test_a_multikicker_offer_counts_the_payments_already_promised() -> None:
    chalice = {"ability_type": "spell", "source_name": "Everflowing Chalice"}
    board = _board(*[_SWAMP] * 3)
    first = _ask("Pay 1 time Multikicker {2} ?", board, chalice, outcome="aidontuseit", offset=1)
    second = _ask("Pay 2 times Multikicker {2} ?", board, chalice, outcome="aidontuseit", offset=2)
    policy = _policy()
    assert policy.decide(first)["selected_option_ids"][0] == "yes"
    assert policy.decide(second)["selected_option_ids"][0] == "no"


def _shriekmaw_question(state: Any) -> Any:
    prompt = (
        "You may choose an alternative cost for casting "
        "<font color='#696969' object_id='#'>Shriekmaw</font> [#]"
    )
    return _request(
        "choice",
        [
            _option(
                "evoke",
                "choice",
                "Cast with Evoke alternative cost: {1}{B} (source: <font>Shriekmaw</font> [#])",
            ),
            _option("full", "choice", "Cast with no alternative cost: {4}{B}"),
        ],
        context={"outcome": "benefit"},
        prompt=prompt,
        state=state,
    )


def test_the_alternative_cost_the_lands_can_pay_is_chosen_over_the_one_they_cannot() -> None:
    board = _board(*[_SWAMP] * 4)
    assert _answer(_shriekmaw_question(board)) == "evoke"


def test_with_mana_for_both_the_usual_choice_stands() -> None:
    usual = _answer(_shriekmaw_question(_board(*[_SWAMP] * 5)))
    unjudged = _answer(_shriekmaw_question(_board(*[_SWAMP] * 5, unreadable=True)))
    assert usual == unjudged


def test_with_mana_for_neither_the_usual_choice_stands() -> None:
    usual = _answer(_shriekmaw_question(_board(_SWAMP)))
    unjudged = _answer(_shriekmaw_question(_board(_SWAMP, unreadable=True)))
    assert usual == unjudged


def test_an_alternative_cost_question_on_a_board_it_cannot_read_is_unchanged() -> None:
    board = _board(*[_SWAMP] * 4, unreadable=True)
    assert _answer(_shriekmaw_question(board)) == _answer(
        _shriekmaw_question(_board(*[_SWAMP] * 5, unreadable=True))
    )


def test_a_source_that_adds_three_mana_of_one_colour_is_counted() -> None:
    # Karmic Guide's echo question, Lotus Field and Sol Ring on the table (plan seed 14): the
    # reader that budgets mana does not know "any one color" and would have read a shortfall.
    board = _board("{T}: Add {R}.", "{T}: Add {C}{C}.", "{T}: Add three mana of any one color.")
    trigger = {"ability_type": "triggered_nonmana", "source_name": "Karmic Guide"}
    assert _answer(_ask("Pay {3}{W}{W}?", board, trigger, outcome="benefit", offset=1)) == "yes"


def test_a_loyalty_ability_that_adds_mana_leaves_the_question_to_the_pilot() -> None:
    board = _board(*[_SWAMP] * 2, "+1: Add {R}{R}.")
    trigger = {"ability_type": "triggered_nonmana", "source_name": "Monstrosity of the Lake"}
    prompt = "Pay {5} and tap all creatures your opponents control?"
    assert _answer(_ask(prompt, board, trigger, outcome="benefit", offset=1)) == "yes"
