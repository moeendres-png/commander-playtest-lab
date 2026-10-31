"""A colour pick inside a payment serves the payment around it (#989 phase 6).

Real games on the pinned engine: Hall of Oracles ("{1}, {T}: Add one mana of any color") opens a
payment of its own, {1}, inside the payment of the spell. That inner payment replaced what the
pilot remembered the spell still needed, so the colour pick saw only a generic {1}, took the
colour of the hand, and the spell was left with a colour no source made. Shriekmaw ({B}) got red
(seed 13), Garna got a wrong colour (seed 4), and the cast was cancelled.

These tests pin the pick for the Hall inside a payment and the controls that a pick outside a
payment, one inside a payment that needs no colour, and one after a later window are unchanged.
"""

from __future__ import annotations

from typing import Any

from tests.unit.test_full_game_pilot_mana_and_may import _option, _policy, _request

_CANCEL = _option("cancel", "cancel_mana_payment", "Cancel mana payment")
_COLOURS = ["Black", "Blue", "Green", "Red", "White"]


def _payment(unpaid: str, *, ability: str, name: str, offset: int) -> dict[str, Any]:
    """A mana payment of a spell or of the Hall's own mana ability."""
    options = [
        _CANCEL,
        _option("hall", "mana_ability", "Hall of Oracles — {1}, {T}: Add one mana of any color."),
    ]
    request = _request("mana_payment", options, context={"unpaid_mana": unpaid}, offset=offset)
    request["source_object"] = {
        "ability_type": ability,
        "source_name": name,
        "source_object_id": f"{name}-id",
    }
    return request


def _hall_pick(offset: int) -> dict[str, Any]:
    return _request(
        "choice",
        [_option(f"c-{name.lower()}", "choice", name) for name in _COLOURS],
        context={"outcome": "putmanainpool"},
        prompt="Select a color of mana to add 1 of it Hall of Oracles [#]",
        offset=offset,
    )


def _pick_inside(spell_unpaid: str) -> str:
    """The colour picked for the Hall while a spell with ``spell_unpaid`` is being paid."""
    policy = _policy()
    policy.decide(_payment(spell_unpaid, ability="spell", name="Shriekmaw", offset=1))
    policy.decide(_payment("{1}", ability="activated_mana", name="Hall of Oracles", offset=2))
    return str(policy.decide(_hall_pick(offset=3))["selected_option_ids"][0])


def test_the_hall_adds_the_colour_the_spell_around_it_needs() -> None:
    # Negative control (fails without the change): only the Hall's own {1} was remembered, no
    # colour was needed, and the hand's colour (white) won the pick.
    assert _pick_inside("{B}") == "c-black"


def test_a_spell_that_needs_no_colour_leaves_the_usual_pick() -> None:
    # Control: {2} is paid by any colour, so the ranking by the hand decides as before.
    assert _pick_inside("{2}") == "c-white"


def test_a_pick_outside_a_payment_is_unchanged() -> None:
    # Control: nothing is being paid, so nothing is remembered about a spell's cost.
    assert str(_policy().decide(_hall_pick(offset=1))["selected_option_ids"][0]) == "c-white"


def test_a_later_priority_window_forgets_the_spells_cost() -> None:
    # Control: a payment that ended (the next window is a priority decision) must not colour a
    # later, unrelated Hall payment, whose own colour pick then ranks by the hand as before.
    policy = _policy()
    policy.decide(_payment("{B}", ability="spell", name="Shriekmaw", offset=1))
    policy.decide(
        _request("priority", [_option("pass", "pass_priority", "Pass priority")], offset=2)
    )
    policy.decide(_payment("{1}", ability="activated_mana", name="Hall of Oracles", offset=3))
    assert str(policy.decide(_hall_pick(offset=4))["selected_option_ids"][0]) == "c-white"
