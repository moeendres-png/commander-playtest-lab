"""Strength index follow-up to #1275: coverage counts only sources the commander has, truthful
reasons, tiers on the unrounded index, other commanders not ranked. Synthetic data only."""

from __future__ import annotations

import pytest

from commander_lab.studio import StudioStore, strength, strength_view, universe
from commander_lab.studio.strength import Observation, PoolContext, StrengthSettings
from tests.unit.studio_synth import add_card, add_deck, add_signal, make_store

CMD = "Cmd A"
INCLUSION = "edhrec_commander_inclusion"
CARDS = [f"Card {index:02d}" for index in range(6)]


def _store() -> StudioStore:
    store = make_store()
    add_card(store, CMD, type_line="Legendary Creature — Test")
    add_card(store, "Other Cmd", type_line="Legendary Creature — Test")
    add_card(store, "Forest", type_line="Basic Land — Forest", basic=True)
    for name in CARDS:
        add_card(store, name)
    for index, name in enumerate(CARDS[:5]):  # one source only: 5 of 6 cards listed
        add_signal(store, CMD, INCLUSION, name, 90 - 10 * index, 100)
    add_signal(store, "Other Cmd", INCLUSION, "Card 00", 1, 10)  # makes "Other Cmd" known
    return store


def _cards(result: strength_view.StrengthResult) -> dict[str, strength_view.StrengthCard]:
    return {card["name"]: card for card in result["cards"]}


def test_one_source_does_not_make_every_card_unknown() -> None:
    cards = _cards(strength_view.compute(_store(), CMD, StrengthSettings()))
    top = cards["Card 00"]
    # Sources never imported for this commander count against no card; the card is graded.
    assert top["coverage"] == 1.0 and top["tier"] != "U" and top["reason"] == "ENOUGH_DATA"
    assert cards["Card 05"]["coverage"] == 0.0  # listed nowhere: lower coverage, no index
    assert cards["Card 05"]["tier"] == "U"


def test_score_pool_coverage_ignores_components_never_collected_and_unusable_ones() -> None:
    settings = StrengthSettings(min_coverage=0.4, min_components=2)
    obs = {
        "a": {"commander_inclusion": Observation(0.9, 90, 100)},
        "b": {"commander_inclusion": Observation(0.5, 50, 100)},
    }
    scored = strength.score_pool(settings, obs, {strength.COMMANDER_INCLUSION})
    assert scored["a"]["coverage"] == 1.0 and scored["a"]["tier"] != "U"  # min_components capped
    # A collected signal whose every denominator is below the minimum is wholly unusable and
    # leaves the denominator as well.
    tiny = {"a": {"tournament_lists": Observation(0.5, 1, 2)}, **obs}
    both = strength.score_pool(
        settings, tiny, {strength.COMMANDER_INCLUSION, strength.TOURNAMENT_LISTS}
    )
    assert both["b"]["coverage"] == 1.0


def test_a_filter_card_leaves_the_deck_universe_out_of_its_denominator() -> None:
    settings = StrengthSettings(min_coverage=0.0, min_components=1)
    obs = {
        "x": {"commander_inclusion": Observation(0.9, 90, 100)},
        "y": {
            "commander_inclusion": Observation(0.5, 50, 100),
            "deck_universe": Observation(0.5, 50, 100),
        },
        "z": {
            "commander_inclusion": Observation(0.1, 10, 100),
            "deck_universe": Observation(0.1, 10, 100),
        },
    }
    collected = {strength.COMMANDER_INCLUSION, strength.DECK_UNIVERSE}
    scored = strength.score_pool(
        settings, obs, collected, context=PoolContext(filter_cards=frozenset({"x"}))
    )
    assert scored["x"]["coverage"] == 1.0  # the filter card is not punished for the filter


def test_no_positive_weight_and_no_source_have_their_own_reasons() -> None:
    zero = StrengthSettings(weights={name: 0.0 for name in strength.COMPONENTS})
    obs = {"a": {"commander_inclusion": Observation(0.9, 90, 100)}}
    only = strength.score_pool(zero, obs, {"commander_inclusion"})["a"]
    assert only["index"] is None and only["tier"] == "U"
    assert only["reason"] == "NO_POSITIVE_WEIGHT"  # not ENOUGH_DATA, not TOO_LITTLE_DATA
    nothing = strength.score_pool(StrengthSettings(), {"a": {}}, set())["a"]
    assert nothing["reason"] == "NO_SOURCE_FOR_COMMANDER" and nothing["tier"] == "U"


def test_the_tier_follows_the_unrounded_index() -> None:
    settings = StrengthSettings(
        weights={name: 0.0 for name in strength.COMPONENTS} | {"synergy": 1.0},
        tier_cuts={"S": 90.0, "A": 66.7, "B": 40.0, "C": 10.0},
        min_coverage=0.0,
        min_components=1,
    )
    values = zip("abcd", (1, 2, 3, 4), strict=True)
    obs = {key: {"synergy": Observation(value)} for key, value in values}
    result = strength.score_pool(settings, obs, {"synergy"})
    assert result["c"]["index"] == 66.7  # raw 66.666...: shown as 66.7
    assert result["c"]["tier"] == "B"  # but below the cut 66.7


def test_other_commanders_are_not_ranked_unless_switched_on() -> None:
    store = _store()
    cards = _cards(strength_view.compute(store, CMD, StrengthSettings()))
    assert cards["Other Cmd"]["tier"] == "N"
    assert cards["Other Cmd"]["reason"] == strength.NOT_RANKED_OTHER_COMMANDER
    assert cards[CMD]["tier"] == "N" and cards["Forest"]["tier"] == "N"
    # They take no part in the percentile population: Card 00 is the top of the five listed.
    top = next(c for c in cards["Card 00"]["components"] if c["component"] == "commander_inclusion")
    assert top["percentile"] == 1.0
    on = _cards(strength_view.compute(store, CMD, StrengthSettings(rank_commander_and_basics=True)))
    assert on["Other Cmd"]["tier"] != "N"


def test_the_deck_universe_filter_card_keeps_its_full_coverage() -> None:
    store = _store()
    for index in range(40):
        add_deck(store, f"d{index}", ["Card 00", "Card 01"])
    universe.save_profile(store, "mit", {"min_universe": 5, "must_contain": ["Card 00"]})
    result = strength_view.compute(store, CMD, StrengthSettings(universe_profile="mit"))
    cards = _cards(result)
    assert cards["Card 00"]["coverage"] == 1.0
    status = {c["component"]: c["status"] for c in cards["Card 00"]["components"]}
    assert status["deck_universe"] == strength.FILTER_CARD
    with pytest.raises(KeyError):
        strength_view.compute(store, CMD, StrengthSettings(universe_profile="nope"))


def test_bracket_labels_follow_the_bracket_column_of_the_imported_files() -> None:
    import csv
    from pathlib import Path

    folder = Path(__file__).resolve().parents[2] / "data" / "research" / "deckbuilder_1655"
    seen: dict[str, str] = {}
    for variant in strength.BRACKETS:
        path = folder / f"commander_bracket_signals_{variant}_1.csv"
        with path.open(newline="", encoding="utf-8") as handle:
            row = next(csv.DictReader(handle))
        assert row["variant"] == variant
        seen[variant] = row["bracket"]
    assert seen == {"core": "2", "upgraded": "3", "optimized": "4", "cedh": "5"}
    choices = strength_view.presets()["panel"]["choices"]["bracket"]  # type: ignore[index,call-overload]
    served = {choice["value"]: choice["label"] for choice in choices}
    for variant, number in seen.items():
        assert f"Bracket {number})" in served[variant], (variant, served[variant])
