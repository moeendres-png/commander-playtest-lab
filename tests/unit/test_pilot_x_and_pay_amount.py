"""Pilot judgment on amounts and costs: three defects seen in real games (#989 phase 4b).

* "Choose how much mana to pay" (Minds Aglow, Mana-Charged Dragon) was answered with the
  engine's 2147483647 ceiling; the payment of that much always failed and reversed, so nobody
  ever paid anything.
* An X spell was cast for X = 0 when the visible mana covered only the rest of its cost
  (Goblin Negotiation for {R}{R}: no damage, no tokens, card gone).
* A repeating multikicker or squad offer was capped by the mana alone; the spell's own cost
  comes out of the same mana, so the chain promised payments the mana could not fund and the
  cast was reversed at the payment.

Each test has a control that shows the rule changes nothing it should not.
"""

from __future__ import annotations

from typing import Any

from tests.unit.test_full_game_pilot_mana_and_may import (
    _PASS,
    _option,
    _policy,
    _request,
    _state,
)

INT_MAX = 2147483647


def _lands(count: int) -> dict[str, Any]:
    state = _state(step="precombat_main")
    actor = state["players"][0]
    actor["battlefield"] = [
        {
            "object_id": f"land-{index}",
            "name": "Plains",
            "tapped": False,
            "abilities": ["{T}: Add {W}."],
        }
        for index in range(count)
    ]
    return state


def _spell_option(name: str, **cost: int) -> dict[str, Any]:
    keys = {
        "mana_cost_white": 0,
        "mana_cost_blue": 0,
        "mana_cost_black": 0,
        "mana_cost_red": 0,
        "mana_cost_green": 0,
        "mana_cost_generic": 0,
        "mana_cost_colorless": 0,
    }
    keys.update({f"mana_cost_{colour}": value for colour, value in cost.items()})
    return _option(
        f"cast-{name}",
        "cast",
        f"{name} — Cast {name}",
        ability_type="spell",
        source_name=name,
        source_object_id=f"id-{name}",
        **keys,
    )


def _announce(prompt: str, state: dict[str, Any], source: str) -> dict[str, Any]:
    request = _request(
        "announce_x",
        [],
        context={"numeric_min": 0, "numeric_max": INT_MAX},
        state=state,
        prompt=prompt,
    )
    request["minimum_selections"] = request["maximum_selections"] = 0
    request["source_object"] = {
        "ability_type": "spell",
        "source_name": source,
        "source_object_id": f"stack-{source}",
        "ability_original_id": f"ability-{source}",
    }
    return request


# --- pay any amount of mana -------------------------------------------------------------


def test_pay_any_amount_is_bounded_by_the_mana_the_seat_can_see() -> None:
    response = _policy().decide(_announce("Choose how much mana to pay", _lands(5), "Minds Aglow"))
    assert response["numeric_choice"] == 5


def test_pay_any_amount_with_no_mana_pays_nothing() -> None:
    response = _policy().decide(_announce("Choose how much mana to pay", _lands(0), "Minds Aglow"))
    assert response["numeric_choice"] == 0


def test_other_amount_prompts_keep_the_engine_ceiling() -> None:
    # Control: the bound belongs to the one engine prompt that asks for mana.
    response = _policy().decide(_announce("Choose a number", _lands(5), "Some Spell"))
    assert response["numeric_choice"] == INT_MAX


# --- X spells with nothing left for X ---------------------------------------------------


def test_x_spell_with_nothing_left_for_x_is_withheld() -> None:
    policy = _policy()
    option = _spell_option("Goblin Negotiation", red=2)
    assert policy._x_spell_without_x(option, _lands(2)) is True
    # Control: one more mana is X = 1, a real cast.
    assert policy._x_spell_without_x(option, _lands(3)) is False


def test_x_spell_veto_leaves_other_spells_alone() -> None:
    policy = _policy()
    # No X in the cost; and a spell that does something at X = 0.
    assert policy._x_spell_without_x(_spell_option("Savannah Lions", white=1), _lands(0)) is False
    assert policy._x_spell_without_x(_spell_option("Walking Ballista"), _lands(0)) is True
    assert policy._x_spell_without_x(_spell_option("Chalice of the Void"), _lands(0)) is False


def test_an_unreadable_cost_is_left_to_the_engine() -> None:
    policy = _policy()
    option = _spell_option("Goblin Negotiation", red=2)
    del option["metadata"]["mana_cost_red"]
    assert policy._x_spell_without_x(option, _lands(0)) is False


def test_the_priority_window_passes_instead_of_casting_for_zero() -> None:
    policy = _policy()
    cast = _spell_option("Goblin Negotiation", red=2)
    request = _request("priority", [_PASS, cast], state=_lands(2))
    assert policy.decide(request)["selected_option_ids"] == ["pass"]


# --- multikicker cap includes the spell's own cost --------------------------------------


def _kicker(count: int, source: str) -> dict[str, Any]:
    request = _request(
        "choose_use",
        [
            _option("yes", "boolean", "Yes", value=True),
            _option("no", "boolean", "No", value=False),
        ],
        context={"outcome": "aidontuseit"},
        state=_lands(7),
        prompt=f"Pay {count} {'time' if count == 1 else 'times'} Multikicker {{2}} ?",
        offset=count,
    )
    request["source_object"] = {
        "ability_type": "spell",
        "source_name": source,
        "source_object_id": f"stack-{source}",
        "ability_original_id": f"ability-{source}",
    }
    return request


def _chain(source: str) -> list[str]:
    policy = _policy()
    answers = []
    for count in range(1, 6):
        answer = policy.decide(_kicker(count, source))["selected_option_ids"][0]
        answers.append(answer)
        if answer == "no":
            break
    return answers


def test_the_chain_stops_when_the_spells_own_cost_leaves_no_mana_for_more() -> None:
    # Zephyrim costs {3}{W}: seven lands less four fund one further {2} payment, so the second
    # offer is declined.
    assert _chain("Zephyrim") == ["yes", "no"]


def test_a_free_spell_gets_the_whole_mana_for_payments() -> None:
    # Control: Everflowing Chalice costs {0}; seven lands fund three payments.
    assert _chain("Everflowing Chalice") == ["yes", "yes", "yes", "no"]
