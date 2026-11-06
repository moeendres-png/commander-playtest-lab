"""Engine-provided palettes guide existing mana choices without inventing options."""

import pytest

from commander_lab.engine.rules.full_game_pilot_payment_plan import (
    completing_options,
    parse_ability,
)
from tests.unit.test_full_game_pilot_mana_and_may import _policy, _request
from tests.unit.test_pilot_payment_plan import _CANCEL, _pool, _tap


def plaza(hint: object = None):
    option = _tap(
        "normal",
        "Plaza of Heroes",
        "one mana of any color among legendary permanents you control",
        source="plaza",
    )
    if hint is not None:
        option["metadata"]["mana_production"] = hint
    return option


def hint(colors: object):
    return {"scope": "unrestricted_board_colors", "amount": 1, "colors": colors}


def restricted():
    return _tap(
        "restricted",
        "Plaza of Heroes",
        "one mana of any color. Spend this mana only to cast a legendary spell",
        source="plaza",
    )


@pytest.mark.parametrize("cost", ["{W}", "{U}"])
def test_native_unrestricted_mode_wins_with_both_options_present(cost):
    options = [_CANCEL, plaza(hint(["W", "U"])), restricted()]
    assert len(options) == 3
    assert _policy().decide(_request("mana_payment", options, context={"unpaid_mana": cost}))[
        "selected_option_ids"
    ] == ["normal"]
    assert completing_options(options, cost) == frozenset({"normal", "restricted"})


def test_native_palette_limits_completing_options():
    option = plaza(hint(["R"]))
    assert parse_ability(option).slots == (frozenset("r"),)
    assert completing_options([_CANCEL, option], "{U}") == frozenset()
    assert completing_options([_CANCEL, option], "{R}") == frozenset({"normal"})


@pytest.mark.parametrize(
    "invalid",
    [
        None,
        {},
        {"scope": "unknown", "amount": 1, "colors": ["U"]},
        {"scope": "unrestricted_board_colors", "amount": True, "colors": ["U"]},
        hint([]),
        hint(["U", "U"]),
        hint(["u"]),
        hint("U"),
        hint(["C"]),
    ],
)
def test_invalid_or_absent_hint_keeps_text_fallback(invalid):
    assert parse_ability(plaza(invalid)) is None
    options = [_CANCEL, plaza(invalid), restricted()]
    assert _policy().decide(_request("mana_payment", options, context={"unpaid_mana": "{U}"}))[
        "selected_option_ids"
    ] == ["restricted"]


def test_hint_does_not_make_nonconsuming_or_unknown_cost_readable():
    option = plaza(hint(["U"]))
    option["label"] = (
        "Plaza of Heroes — Add one mana of any color among legendary permanents you control."
    )
    assert parse_ability(option) is None


def test_source_exclusivity_and_filter_prefunding_remain():
    normal = plaza(hint(["W", "U"]))
    other = _tap("other", "Plaza of Heroes", "{W}", source="plaza")
    assert completing_options([_CANCEL, normal, other], "{W}{U}") == frozenset()
    signet = _tap("signet", "Signet", "{W}{U}", cost="{1}, {T}")
    signet["metadata"]["pool_covers_mana_cost"] = False
    assert completing_options([_CANCEL, normal, signet], "{W}{U}") == frozenset({"normal"})
    powerstone = _tap("powerstone", "Powerstone", "{C}")
    assert completing_options([_CANCEL, powerstone, signet], "{W}{U}") == frozenset({"powerstone"})
    assert (
        completing_options([_CANCEL, _pool("colorless", advances=False), signet], "{W}{U}")
        == frozenset()
    )


def test_red_native_palette_does_not_rank_as_blue():
    normal = plaza(hint(["R"]))
    island = _tap("island", "Island", "{U}")
    options = [_CANCEL, normal, island, _pool("red", advances=False)]
    assert _policy().decide(_request("mana_payment", options, context={"unpaid_mana": "{U}"}))[
        "selected_option_ids"
    ] == ["island"]
