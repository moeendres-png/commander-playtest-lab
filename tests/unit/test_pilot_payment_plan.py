"""Mana payments that stay completable (#989 phase 5).

Real games on the pinned engine: in 24 recorded games 136 payments ended in "Cancel mana
payment", and 56 of them could still have been paid at their first prompt. Two shapes made up
most of them: a Mountain's {R} spent on the {1} of a {1}{W} cost left the Rugged Prairie unable to
pay its own {R/W} (the filter check counted mana, not colours), and Hall of Oracles was tapped for
{C} while the untapped Swamp that pays its {1} stayed untouched for a {R} cost.

The model reads only the engine's own option text; these tests pin what it answers, that the pilot
follows it, and the controls that prove an offer it cannot read, or one the usual choice already
completes, changes nothing.
"""

from __future__ import annotations

from typing import Any

import pytest

from commander_lab.engine.rules import full_game_pilot_payment_plan as plan
from commander_lab.engine.rules.full_game_pilot_payment_plan import (
    completing_options,
    completing_outcomes,
    parse_ability,
    parse_unpaid,
)
from tests.unit.test_full_game_pilot_mana_and_may import _option, _policy, _request

_CANCEL = _option("cancel", "cancel_mana_payment", "Cancel mana payment")


def _tap(option_id: str, name: str, effect: str, *, cost: str = "{T}", source: str = "") -> Any:
    return _option(
        option_id,
        "mana_ability",
        f"{name} — {cost}: Add {effect}.",
        source_name=name,
        source_object_id=source or option_id.split("-")[0],
        requires_tap_source=True,
        source_tapped=False,
        pool_covers_mana_cost=True,
    )


def _pool(kind: str, amount: int = 1, *, advances: bool = True) -> Any:
    return _option(
        f"pool-{kind}",
        "mana_pool",
        f"Spend {kind} mana from pool",
        mana_type=kind,
        mana_available=amount,
        advances_payment=advances,
    )


def _prairie() -> list[Any]:
    """Rugged Prairie as the engine offers it: three filter outcomes and the plain {C}."""
    return [
        _tap("prairie-rr", "Rugged Prairie", "{R}{R}", cost="{R/W}, {T}", source="prairie"),
        _tap("prairie-rw", "Rugged Prairie", "{R}{W}", cost="{R/W}, {T}", source="prairie"),
        _tap("prairie-ww", "Rugged Prairie", "{W}{W}", cost="{R/W}, {T}", source="prairie"),
        _tap("prairie-c", "Rugged Prairie", "{C}", source="prairie"),
    ]


def _hall() -> list[Any]:
    return [
        _tap(
            "hall-any",
            "Hall of Oracles",
            "one mana of any color",
            cost="{1}, {T}",
            source="hall",
        ),
        _tap("hall-c", "Hall of Oracles", "{C}", source="hall"),
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("{1}{W}", (1, 1)),
        ("{2}{W/U}{B}", (2, 2)),
        ("{G/P}{1}", (1, 0)),
        ("", (0, 0)),
        ("{W}{W}", (0, 2)),
    ],
)
def test_unpaid_cost_is_read_as_generic_and_pips(text: str, expected: tuple[int, int]) -> None:
    owed = parse_unpaid(text)
    assert owed is not None
    assert (owed[0], len(owed[1])) == expected


@pytest.mark.parametrize("text", ["{X}{R}", "{S}", "{E}", "{2}{Q}"])
def test_unpaid_cost_it_does_not_know_is_unreadable(text: str) -> None:
    assert parse_unpaid(text) is None


@pytest.mark.parametrize(
    ("label", "readable"),
    [
        ("Mountain — {T}: Add {R}.", True),
        ("Rugged Prairie — {R/W}, {T}: Add {W}{W}.", True),
        ("Skycloud Expanse — {1}, {T}: Add {W}{U}.", True),
        ("Hall of Oracles — {1}, {T}: Add one mana of any color.", True),
        ("Treasure — {T}, Sacrifice this artifact: Add one mana of any color.", True),
        ("Caves of Koilos — {T}, Pay 1 life: Add {W}.", True),
        (
            "Springleaf Drum — {T}, Tap an untapped creature you control: Add one mana of any color.",
            False,
        ),
        (
            "Gemstone Mine — {T}, Remove a mining counter from this land: Add one mana of any color.",
            False,
        ),
        ("Mana Vault — Add {C}{C}{C}.", False),
        ("Cabal Coffers — {2}, {T}: Add {B} for each Swamp you control.", False),
    ],
)
def test_ability_text_is_read_or_refused(label: str, readable: bool) -> None:
    ability = parse_ability(_option("o", "mana_ability", label, source_object_id="s"))
    assert (ability is not None) is readable


def test_the_selfless_spirit_payment_finishes_through_the_filter_land() -> None:
    # {1}{W} with a red mana floating and only the Prairie left: spending the pool on the {1}
    # leaves {W} and a Prairie with nothing to pay its {R/W}; paying the Prairie's cost from the
    # pool turns the red into {W}{W} or {R}{W}.
    options = [_CANCEL, _pool("red"), *_prairie()]
    assert completing_options(options, "{1}{W}") == frozenset({"prairie-rw", "prairie-ww"})


def test_first_prompt_of_that_payment_taps_the_land_that_feeds_the_filter() -> None:
    options = [_CANCEL, _tap("mountain-r", "Mountain", "{R}"), *_prairie()]
    assert completing_options(options, "{1}{W}") == frozenset({"mountain-r"})


def test_hall_of_oracles_needs_a_mana_to_pay_its_own_cost() -> None:
    options = [_CANCEL, _tap("swamp-b", "Swamp", "{B}"), *_hall()]
    assert completing_options(options, "{R}") == frozenset({"swamp-b"})


def test_a_mana_that_cannot_help_is_not_a_completing_one() -> None:
    options = [_CANCEL, _pool("black", advances=False), *_hall()]
    # {R} from the Hall paid with the floating {B}
    assert completing_options(options, "{R}") == frozenset({"hall-any"})


def _unfunded(options: list[Any]) -> list[Any]:
    """The same options with the engine's pool verdict set to "short"."""
    return [
        option | {"metadata": {**option["metadata"], "pool_covers_mana_cost": False}}
        for option in options
    ]


def test_an_ability_the_engine_calls_unfunded_is_not_chosen_now() -> None:
    # The engine's verdict on the pool as it is: a floating red would pay the Skycloud Expanse's
    # {1}, but the engine says the pool does not cover it, so it is not an option now.
    expanse = _tap("expanse-wu", "Skycloud Expanse", "{W}{U}", cost="{1}, {T}", source="expanse")
    assert completing_options(
        [_CANCEL, _pool("red", advances=False), expanse], "{W}{U}"
    ) == frozenset({"expanse-wu"})
    assert (
        completing_options([_CANCEL, _pool("red", advances=False), *_unfunded([expanse])], "{W}{U}")
        == frozenset()
    )


def test_a_hybrid_cost_the_flag_calls_short_is_read_from_the_pool() -> None:
    # The flag counts {R/W} as red and white, so a pool holding only red reads as short for the
    # Rugged Prairie. The pool pays it, and the model says so.
    options = [_CANCEL, _pool("red"), *_unfunded(_prairie())]
    assert completing_options(options, "{1}{W}") == frozenset({"prairie-rw", "prairie-ww"})


def test_cancel_is_never_part_of_the_answer() -> None:
    assert completing_options([_CANCEL, _tap("plains-w", "Plains", "{W}")], "{W}") == frozenset(
        {"plains-w"}
    )


def test_a_payment_nothing_can_finish_has_no_completing_option() -> None:
    options = [_CANCEL, _tap("mountain-r", "Mountain", "{R}")]
    assert completing_options(options, "{B}") == frozenset()


def test_a_second_ability_of_a_used_source_is_not_extra_mana() -> None:
    # The Prairie's filter outcomes are alternatives of one tap, never two sources.
    options = [_CANCEL, _pool("red", 2, advances=False), *_prairie()]
    assert completing_options(options, "{W}{W}{W}{W}") == frozenset()


@pytest.mark.parametrize(
    "extra",
    [
        _option(
            "drum",
            "mana_ability",
            "Springleaf Drum — {T}, Tap an untapped creature you control: Add {G}.",
            source_object_id="drum",
        ),
        _option("delve", "special_mana_action", "Dig Through Time — Delve", source_object_id="d"),
        _option("odd", "mana_pool", "Spend plasma mana from pool", mana_type="plasma"),
    ],
)
def test_an_offer_it_cannot_read_is_not_judged(extra: Any) -> None:
    options = [_CANCEL, _tap("mountain-r", "Mountain", "{R}"), extra]
    assert completing_options(options, "{1}") is None


def test_a_pool_spend_the_engine_calls_advancing_but_the_model_cannot_use_is_not_judged() -> None:
    # The engine's flag and the model disagree on an elementary fact (a blue mana on a {W} cost),
    # so the model keeps out of it and the engine's verdict stands.
    options = [_CANCEL, _tap("plains-w", "Plains", "{W}"), _pool("blue")]
    assert completing_options(options, "{W}") is None
    advancing = [
        option | {"metadata": {**option["metadata"], "advances_payment": False}}
        for option in [_pool("blue")]
    ]
    assert completing_options(
        [_CANCEL, _tap("plains-w", "Plains", "{W}"), *advancing], "{W}"
    ) == frozenset({"plains-w"})


def test_a_search_that_outgrows_its_budget_is_not_judged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(plan, "_NODE_CAP", 1)
    options = [_CANCEL, *_prairie(), _pool("red")]
    assert completing_options(options, "{1}{W}") is None


def test_the_pilot_pays_the_filter_instead_of_spending_the_pool() -> None:
    # Negative control (fails on the code before the change): the old order spent the pool first.
    options = [_CANCEL, _pool("red"), *_prairie()]
    for _ in range(2):
        response = _policy().decide(
            _request("mana_payment", options, context={"unpaid_mana": "{1}{W}"})
        )
        assert response["selected_option_ids"][0] in {"prairie-rw", "prairie-ww"}


def test_the_pilot_pays_the_filter_the_engine_flags_as_short_when_the_pool_covers_it() -> None:
    # The engine's own offer in a real game (seed 2, Selfless Spirit): every filter outcome of
    # the Prairie carries pool_covers_mana_cost=False while a red mana floats. Without the model's
    # own reading the pilot withheld them and spent the red on the {1}, then cancelled.
    options = [_CANCEL, _pool("red"), *_unfunded(_prairie()[:3]), _prairie()[3]]
    response = _policy().decide(
        _request("mana_payment", options, context={"unpaid_mana": "{1}{W}"})
    )
    assert response["selected_option_ids"][0] in {"prairie-rw", "prairie-ww"}


def test_a_filter_with_a_plain_cost_the_engine_flags_as_short_stays_withheld() -> None:
    # Control: the flag is still authoritative for a cost that is not hybrid.
    expanse = _unfunded(
        [_tap("expanse-wu", "Skycloud Expanse", "{W}{U}", cost="{1}, {T}", source="expanse")]
    )
    options = [_CANCEL, _pool("red"), *expanse]
    response = _policy().decide(
        _request("mana_payment", options, context={"unpaid_mana": "{1}{W}"})
    )
    assert response["selected_option_ids"] == ["pool-red"]


def test_the_pilot_taps_the_swamp_not_the_hall_for_a_red_cost() -> None:
    options = [_CANCEL, *_hall(), _tap("swamp-b", "Swamp", "{B}")]
    response = _policy().decide(_request("mana_payment", options, context={"unpaid_mana": "{R}"}))
    assert response["selected_option_ids"] == ["swamp-b"]


def test_a_choice_that_already_completes_is_left_alone() -> None:
    # Control: Plains pays {W} directly, no narrowing involved.
    options = [_CANCEL, _tap("plains-w", "Plains", "{W}"), _tap("island-u", "Island", "{U}")]
    response = _policy().decide(_request("mana_payment", options, context={"unpaid_mana": "{W}"}))
    assert response["selected_option_ids"] == ["plains-w"]


def test_a_payment_that_cannot_finish_still_taps_instead_of_cancelling() -> None:
    # Control: when no option completes the usual choice stays (the engine judges it).
    options = [_CANCEL, _tap("mountain-r", "Mountain", "{R}")]
    response = _policy().decide(_request("mana_payment", options, context={"unpaid_mana": "{B}"}))
    assert response["selected_option_ids"] == ["mountain-r"]


def test_an_unreadable_offer_keeps_the_usual_choice() -> None:
    drum = _option(
        "drum",
        "mana_ability",
        "Springleaf Drum — {T}, Tap an untapped creature you control: Add one mana of any color.",
        source_object_id="drum",
    )
    options = [_CANCEL, _pool("red"), drum]
    response = _policy().decide(_request("mana_payment", options, context={"unpaid_mana": "{1}"}))
    assert response["selected_option_ids"] == ["pool-red"]


# --- colour picks inside a payment -------------------------------------------------------------


def _spire() -> Any:
    return _option(
        "spire-any",
        "mana_ability",
        "Spire of Industry — {T}, Pay 1 life: Add one mana of any color.",
        source_name="Spire of Industry",
        source_object_id="spire",
        requires_tap_source=True,
        source_tapped=False,
        pool_covers_mana_cost=True,
    )


def _terminate_offer() -> list[Any]:
    """Terminate ({B}{R}) with the Spire, two black sources and two colourless ones (seed 8)."""
    return [
        _CANCEL,
        _spire(),
        _tap("swamp-b", "Swamp", "{B}"),
        _tap("myr-b", "Leaden Myr", "{B}"),
        _tap("hedron-cc", "Hedron Archive", "{C}{C}"),
        _tap("ring-cc", "Sol Ring", "{C}{C}"),
    ]


def _colour_pick(*, offset: int = 2) -> dict[str, Any]:
    names = ["Black", "Blue", "Green", "Red", "White"]
    return _request(
        "choice",
        [_option(f"c-{name.lower()}", "choice", name) for name in names],
        context={"outcome": "putmanainpool"},
        prompt="Select a color of mana to add 1 of it Spire of Industry [#]",
        offset=offset,
    )


def test_outcomes_name_the_colour_the_rest_of_the_payment_needs() -> None:
    options = _terminate_offer()
    black, red = ("b",), ("r",)
    assert completing_outcomes(options, "{B}{R}", "spire-any", [black, red]) == frozenset({red})


def test_outcomes_are_not_judged_for_a_pool_spend() -> None:
    options = [_CANCEL, _pool("red")]
    assert completing_outcomes(options, "{R}", "pool-red", [("r",)]) is None


def test_the_pilot_picks_the_colour_the_payment_still_needs() -> None:
    # Negative control (fails without the change): the cost ranking scores {B} and {R} alike and
    # the label order took Black, leaving a {R} no source could make; the payment was cancelled.
    policy = _policy()
    first = policy.decide(
        _request("mana_payment", _terminate_offer(), context={"unpaid_mana": "{B}{R}"})
    )
    assert first["selected_option_ids"] == ["spire-any"]
    pick = policy.decide(_colour_pick())
    assert pick["selected_option_ids"] == ["c-red"]


def test_a_colour_pick_outside_a_payment_is_unchanged() -> None:
    # Control: nothing is being paid, so the cost ranking and the label order decide as before.
    pick = _policy().decide(_colour_pick(offset=1))
    assert pick["selected_option_ids"] == ["c-white"]


def test_a_pick_every_colour_of_which_completes_is_unchanged() -> None:
    # Control: {1} is paid by whatever colour the Spire makes; the usual ranking decides.
    policy = _policy()
    policy.decide(_request("mana_payment", [_CANCEL, _spire()], context={"unpaid_mana": "{1}"}))
    pick = policy.decide(_colour_pick())
    assert pick["selected_option_ids"] == ["c-white"]


def test_a_later_priority_window_forgets_the_offer() -> None:
    policy = _policy()
    policy.decide(_request("mana_payment", _terminate_offer(), context={"unpaid_mana": "{B}{R}"}))
    policy.decide(
        _request("priority", [_option("pass", "pass_priority", "Pass priority")], offset=2)
    )
    pick = policy.decide(_colour_pick(offset=3))
    # the stale cost still ranks {B} and {R} alike, as before; the offer's colours are not used
    assert pick["selected_option_ids"] == ["c-black"]


def _combination_request() -> dict[str, Any]:
    request = _request(
        "multi_amount",
        [],
        context={
            "numeric_legs": [
                {"min": 0, "max": 2, "prompt": "U"},
                {"min": 0, "max": 2, "prompt": "B"},
                {"min": 0, "max": 2, "prompt": "R"},
            ],
            "numeric_total_min": 2,
            "numeric_total_max": 2,
            "outcome": "putmanainpool",
        },
        offset=2,
    )
    request["minimum_selections"] = request["maximum_selections"] = 0
    return request


def test_the_pilot_splits_a_combination_towards_the_colour_still_owed() -> None:
    relic = _option(
        "relic",
        "mana_ability",
        "Relic of Sauron — {T}: Add two mana in any combination of {U}, {B}, {R}.",
        source_name="Relic of Sauron",
        source_object_id="relic",
        requires_tap_source=True,
        source_tapped=False,
        pool_covers_mana_cost=True,
    )
    policy = _policy()
    policy.decide(_request("mana_payment", [_CANCEL, relic], context={"unpaid_mana": "{1}{R}"}))
    split = policy.decide(_combination_request())["numeric_choices"]
    assert split[2] >= 1
    assert sum(split) == 2


def test_a_combination_outside_a_payment_is_left_to_the_pilot() -> None:
    split = _policy().decide(_combination_request())["numeric_choices"]
    assert sum(split) == 2
