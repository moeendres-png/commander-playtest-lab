"""Native tap-gate budgeting and prefunding controls for engine-offered mana sources."""

from __future__ import annotations

import random

import pytest

from commander_lab.engine.rules.full_game_pilot_payment_plan import can_pay, completing_options
from tests.unit.test_full_game_pilot_mana_and_may import _option, _policy, _request
from tests.unit.test_pilot_optional_costs import _board
from tests.unit.test_pilot_payment_plan import _CANCEL, _pool, _tap


@pytest.mark.parametrize("blocked", [True, False, None, "true"])
def test_budget_uses_only_the_explicit_native_source_tap_verdict(blocked: object) -> None:
    state = _board("{T}: Add {G}.")
    actor = state["players"][0]
    creature = actor["battlefield"][0]
    creature["name"] = "Elvish Mystic"
    creature["source_tap_mana_abilities_blocked"] = blocked
    # These descriptive fields must not become a second summoning-sickness implementation.
    creature["entered_this_turn"] = True
    creature["haste"] = False
    expected = 0 if blocked is True else 1
    policy = _policy()
    assert policy._mana_budget(state) == expected
    assert policy._available_mana(actor) == expected
    offer = policy._visible_mana_offer(actor)
    assert offer is not None
    assert can_pay(offer, "{G}") is bool(expected)


def test_an_unfunded_filter_remains_a_future_source_in_the_visible_offer() -> None:
    state = _board("{T}: Add {B}.", "{1}, {T}: Add {W}{U}.")
    actor = state["players"][0]
    for permanent in actor["battlefield"]:
        permanent["source_tap_mana_abilities_blocked"] = False
    offer = _policy()._visible_mana_offer(actor)
    assert offer is not None
    assert can_pay(offer, "{W}{U}") is True


def _filter(*, funded: bool | None) -> dict:
    option = _tap("filter", "Skycloud Expanse", "{W}{U}", cost="{1}, {T}")
    option["metadata"].update(
        {
            f"mana_cost_{color}": 0
            for color in ("white", "blue", "black", "red", "green", "colorless")
        }
    )
    option["metadata"].update(mana_cost_generic=1, pool_covers_mana_cost=funded)
    return option


@pytest.mark.parametrize("funded", [False, None])
def test_planned_source_funds_the_filter_before_tapping_it(funded: bool | None) -> None:
    options = [_CANCEL, _filter(funded=funded), _tap("swamp", "Swamp", "{B}")]
    assert _policy()._planned_mana_source(options, "{W}{U}") == "swamp"


def test_planned_filter_can_use_native_or_existing_completion_proof() -> None:
    assert _policy()._planned_mana_source([_CANCEL, _filter(funded=True)], "{W}{U}") == "filter"


@pytest.mark.parametrize("funded", [False, None])
def test_hybrid_filter_uses_completion_proof_without_replacing_other_guards(
    funded: bool | None,
) -> None:
    prairie = _tap("prairie", "Rugged Prairie", "{W}{W}", cost="{R/W}, {T}")
    prairie["metadata"].update(pool_covers_mana_cost=funded, mana_cost_white=1, mana_cost_red=1)
    good = completing_options([_CANCEL, _pool("red", advances=False), prairie], "{W}{W}")
    assert good == frozenset({"prairie"})
    assert _policy()._planned_mana_source([_CANCEL, prairie], "{W}{W}") is None
    assert _policy()._planned_mana_source([_CANCEL, prairie], "{W}{W}", payable=good) == "prairie"


def test_budget_does_not_count_an_unbootstrapped_filter() -> None:
    state = _board("{1}, {T}: Add {W}{U}.")
    actor = state["players"][0]
    actor["battlefield"][0]["source_tap_mana_abilities_blocked"] = False
    policy = _policy()
    assert policy._mana_budget(state) == 0
    assert policy._available_mana(actor, state=state) == 0


@pytest.mark.parametrize("opponent", [False, True])
def test_unmodeled_mana_multiplier_keeps_the_prior_estimate(opponent: bool) -> None:
    from commander_lab.agents.card_knowledge import card_facts

    state = _board("{T}: Add {G}.", "{5}, {T}: Add {W}{U}{B}{R}{G}.")
    facts = card_facts("Mana Reflection")
    assert facts is not None
    state["players"][1 if opponent else 0]["battlefield"].append(
        {"name": facts.name, "tapped": False, "abilities": [facts.oracle_text]}
    )
    policy = _policy()
    assert can_pay(policy._visible_mana_offer(state["players"][0]), "{2}") is False
    assert policy._mana_budget(state) == 2
    assert policy._available_mana(state["players"][0], state=state) == 2


def test_budget_keeps_a_filter_chain_with_a_free_initial_source() -> None:
    state = _board("{T}: Add {B}.", "{1}, {T}: Add {W}{U}.", "{1}, {T}: Add {G}{W}.")
    policy = _policy()
    assert policy._mana_budget(state) == 3
    assert policy._available_mana(state["players"][0], state=state) == 3


def test_priority_remembers_the_same_funding_estimate_used_by_the_retry_guard() -> None:
    state = _board("{2}, {T}: Add {C}{C}{C}.")
    spell = _option(
        "cast-ring",
        "activated_ability",
        "Cast Sol Ring",
        ability_type="spell",
        source_name="Sol Ring",
        source_object_id="ring",
        mana_cost_generic=1,
    )
    policy = _policy()
    policy.decide(
        _request(
            "priority", [_option("pass", "pass_priority", "Pass priority"), spell], state=state
        )
    )
    assert policy._last_priority_visible_mana[1] == 0
    state["players"][0]["mana_pool"]["white"] = 1
    assert policy._available_mana(state["players"][0], state=state) == 1


def test_unfunded_filter_without_a_funding_source_has_no_automatic_plan() -> None:
    assert _policy()._planned_mana_source([_CANCEL, _filter(funded=False)], "{W}{U}") is None


@pytest.mark.parametrize("reserved", [False, True])
def test_pool_funded_filter_obeys_the_same_reservation_guard(reserved: bool) -> None:
    # A defensive offered-option control; native code already excludes some own-source
    # combinations. Funding must not bypass the pilot's other source-reservation checks.
    policy = _policy()
    if reserved:
        policy._payment_source[1] = "filter"
        policy._last_priority_source[1] = "filter"
        policy._last_priority_label[1] = "Skycloud Expanse — {2}, {T}: Draw a card."
    options = [_CANCEL, _pool("black", advances=False), _filter(funded=True)]
    choice = policy._choose_mana_option(
        policy._pilots[1], _board(), options, {"unpaid_mana": "{W}{U}"}, random.Random(1)
    )
    assert choice == ("cancel" if reserved else "filter")


def test_filter_plan_keeps_the_seed_mana_out_of_the_spell_payment() -> None:
    options = [_CANCEL, _pool("black"), _filter(funded=True)]
    assert completing_options(options, "{1}{U}") == frozenset({"filter"})
