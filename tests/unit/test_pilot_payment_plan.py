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
    )


def _pool(kind: str, amount: int = 1) -> Any:
    return _option(
        f"pool-{kind}",
        "mana_pool",
        f"Spend {kind} mana from pool",
        mana_type=kind,
        mana_available=amount,
        advances_payment=True,
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
    options = [_CANCEL, _pool("black"), *_hall()]
    # {R} from the Hall paid with the floating {B}
    assert completing_options(options, "{R}") == frozenset({"hall-any"})


def test_an_ability_the_engine_calls_unfunded_is_not_chosen_now() -> None:
    # The engine's verdict on the pool as it is: the Prairie cannot be activated before the red
    # mana is in the pool, however well it would finish the payment afterwards.
    unfunded = [
        option | {"metadata": {**option["metadata"], "pool_covers_mana_cost": False}}
        for option in _prairie()
    ]
    options = [_CANCEL, _pool("red"), *unfunded]
    assert completing_options(options, "{1}{W}") == frozenset()
    assert completing_options(
        [_CANCEL, _tap("mountain-r", "Mountain", "{R}"), *unfunded], "{1}{W}"
    ) == frozenset({"mountain-r"})


def test_cancel_is_never_part_of_the_answer() -> None:
    assert completing_options([_CANCEL, _tap("plains-w", "Plains", "{W}")], "{W}") == frozenset(
        {"plains-w"}
    )


def test_a_payment_nothing_can_finish_has_no_completing_option() -> None:
    options = [_CANCEL, _tap("mountain-r", "Mountain", "{R}")]
    assert completing_options(options, "{B}") == frozenset()


def test_a_second_ability_of_a_used_source_is_not_extra_mana() -> None:
    # The Prairie's filter outcomes are alternatives of one tap, never two sources.
    options = [_CANCEL, _pool("red", 2), *_prairie()]
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
