"""Strength index follow-up to #1275: truthful reasons, tiers on the shown index, configurable
other commanders, oracle_id fallback parity. Synthetic data only."""

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


def test_a_filter_card_leaves_the_deck_universe_out_of_its_denominator() -> None:
    """Main's denominator (every weighted component, here 13) minus the deck universe (2) for a
    filter card: 3 of 11 for a card with only the commander inclusion; the control card, which is
    no filter card, has the same signal and the universe too: 5 of 13."""
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
        "w": {"commander_inclusion": Observation(0.3, 30, 100)},  # control: not a filter card
    }
    collected = {strength.COMMANDER_INCLUSION, strength.DECK_UNIVERSE}
    scored = strength.score_pool(
        settings, obs, collected, context=PoolContext(filter_cards=frozenset({"x"}))
    )
    assert scored["x"]["coverage"] == pytest.approx(3 / 11, abs=1e-4)
    assert scored["w"]["coverage"] == pytest.approx(3 / 13, abs=1e-4)
    assert scored["y"]["coverage"] == pytest.approx(5 / 13, abs=1e-4)


def test_no_positive_weight_and_no_source_have_their_own_reasons() -> None:
    zero = StrengthSettings(weights={name: 0.0 for name in strength.COMPONENTS})
    obs = {"a": {"commander_inclusion": Observation(0.9, 90, 100)}}
    only = strength.score_pool(zero, obs, {"commander_inclusion"})["a"]
    assert only["index"] is None and only["tier"] == "U"
    assert only["reason"] == "NO_POSITIVE_WEIGHT"  # not ENOUGH_DATA, not TOO_LITTLE_DATA
    nothing = strength.score_pool(StrengthSettings(), {"a": {}}, set())["a"]
    assert nothing["reason"] == "NO_SOURCE_FOR_COMMANDER" and nothing["tier"] == "U"


def test_the_tier_follows_the_index_as_shown() -> None:
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
    assert result["c"]["tier"] == "A"  # the shown value meets the cut 66.7: never "66.7 but B"


def test_other_commanders_are_ranked_by_default_and_not_when_switched_off() -> None:
    store = _store()
    default = _cards(strength_view.compute(store, CMD, StrengthSettings()))
    assert default["Other Cmd"]["tier"] != "N"  # ranked like any card by default
    assert StrengthSettings().rank_other_commanders is True
    cards = _cards(strength_view.compute(store, CMD, StrengthSettings(rank_other_commanders=False)))
    assert cards["Other Cmd"]["tier"] == "N"
    assert cards["Other Cmd"]["reason"] == strength.NOT_RANKED_OTHER_COMMANDER
    assert cards[CMD]["tier"] == "N" and cards["Forest"]["tier"] == "N"
    # They take no part in the percentile population: Card 00 is the top of the five listed.
    top = next(c for c in cards["Card 00"]["components"] if c["component"] == "commander_inclusion")
    assert top["percentile"] == 1.0
    on = _cards(strength_view.compute(store, CMD, StrengthSettings(rank_commander_and_basics=True)))
    assert on["Other Cmd"]["tier"] != "N"


def test_the_deck_universe_filter_card_has_the_universe_out_of_its_denominator() -> None:
    store = _store()
    for index in range(40):
        add_deck(store, f"d{index}", ["Card 00", "Card 01"])
    universe.save_profile(store, "mit", {"min_universe": 5, "must_contain": ["Card 00"]})
    result = strength_view.compute(store, CMD, StrengthSettings(universe_profile="mit"))
    cards = _cards(result)
    status = {c["component"]: c["status"] for c in cards["Card 00"]["components"]}
    assert status["deck_universe"] == strength.FILTER_CARD
    # the filter card has the universe weight (2) out of its denominator: 3 of 11; the control
    # card of the same pool has the commander inclusion and the universe present: 5 of 13
    assert cards["Card 00"]["coverage"] == pytest.approx(3 / 11, abs=1e-4)
    assert cards["Card 01"]["coverage"] == pytest.approx(5 / 13, abs=1e-4)
    with pytest.raises(KeyError):
        strength_view.compute(store, CMD, StrengthSettings(universe_profile="nope"))


def test_the_minimum_number_of_signals_never_exceeds_the_weighted_components() -> None:
    settings = StrengthSettings(
        weights={name: 0.0 for name in strength.COMPONENTS} | {"commander_inclusion": 1.0},
        min_coverage=0.0,
        min_components=3,
    )
    obs = {"a": {"commander_inclusion": Observation(0.9, 90, 100)}}
    scored = strength.score_pool(settings, obs, {strength.COMMANDER_INCLUSION})
    assert scored["a"]["tier"] != "U" and scored["a"]["reason"] == "ENOUGH_DATA"


def test_a_deck_row_with_an_oracle_id_counts_for_the_card_under_any_spelling() -> None:
    from commander_lab.studio import builder, universe_view

    store = make_store()
    add_card(store, CMD, type_line="Legendary Creature — Test")
    fire_id = add_card(store, "Fire // Ice")
    vault_id = add_card(store, "Lim-Dûl's Vault")
    db = store.connection
    db.execute("UPDATE card SET oracle_id = 'o-fire' WHERE oracle_name = 'Fire // Ice'")
    db.execute("UPDATE card SET oracle_id = 'o-vault' WHERE oracle_name = 'Lim-Dûl''s Vault'")
    add_deck(store, "d1", ["Fire", "Lim-Dul's Vault"])
    add_deck(store, "d2", ["Fire // Ice"])
    db.execute(
        "UPDATE corpus_deck_card SET oracle_id = 'o-vault' WHERE card_name = 'Lim-Dul''s Vault'"
    )
    pool = builder.pool_cards(store, [CMD], with_signals=False)
    cards = {str(c["name"]): c for c in pool["cards"]}  # type: ignore[attr-defined]
    assert cards["Fire // Ice"]["decks"]["all"] == 2  # front face "Fire" + the full name
    assert cards["Lim-Dûl's Vault"]["decks"]["all"] == 1  # accent spelling, found by its id
    assert cards["Lim-Dûl's Vault"]["decks_known"] is True

    universe.save_profile(store, "alle", {"min_universe": 1})
    spread = {
        c["name"]: c
        for c in universe_view.pool_spread(store, "alle", commander_names=[CMD])["cards"]
    }
    assert spread["Lim-Dûl's Vault"]["matched"] is True
    assert spread["Lim-Dûl's Vault"]["matched_name"] == "Lim-Dul's Vault"
    assert spread["Lim-Dûl's Vault"]["hits"] == 1

    co_fire = universe_view.card_cooccurrence(store, "alle", fire_id, commander_names=[CMD])
    co_vault = universe_view.card_cooccurrence(store, "alle", vault_id, commander_names=[CMD])
    assert co_vault["matched"] is True and co_vault["decks_with_card"] == 1
    assert any(
        p["card_name"] == "Lim-Dûl's Vault" and p["decks_together"] == 1 for p in co_fire["pairs"]
    )
    assert any(
        p["card_name"] == "Fire // Ice" and p["decks_together"] == 1 for p in co_vault["pairs"]
    )

    computed = _cards(strength_view.compute(store, CMD, StrengthSettings(universe_profile="alle")))
    vault_comp = next(
        c for c in computed["Lim-Dûl's Vault"]["components"] if c["component"] == "deck_universe"
    )
    assert vault_comp["status"] == strength.PRESENT
    assert vault_comp["numerator"] == 1 and vault_comp["denominator"] == 2


def test_other_commander_names_matches_case_insensitively() -> None:
    store = _store()
    others = strength_view._other_commander_names(store, "other cmd")
    assert "other cmd" not in others
    assert "cmd a" in others


def test_filter_card_removing_sole_weighted_signal_gets_too_little_data() -> None:
    settings = StrengthSettings(
        weights={name: 0.0 for name in strength.COMPONENTS} | {"deck_universe": 1.0},
        min_coverage=0.0,
        min_components=1,
        require_commander_signal=False,
    )
    obs = {"x": {}, "y": {"deck_universe": Observation(0.5, 5, 10)}}
    scored = strength.score_pool(
        settings,
        obs,
        {strength.DECK_UNIVERSE},
        context=PoolContext(filter_cards=frozenset({"x"})),
    )
    assert scored["x"]["tier"] == "U"
    assert scored["x"]["reason"] == "TOO_LITTLE_DATA"


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


def test_the_two_ranking_switches_are_independent() -> None:
    store = _store()
    both = StrengthSettings(rank_commander_and_basics=True, rank_other_commanders=False)
    cards = _cards(strength_view.compute(store, CMD, both))
    # the commander card and basics are ranked, the other commander card still is not
    assert cards["Other Cmd"]["tier"] == "N"
    assert cards["Other Cmd"]["reason"] == strength.NOT_RANKED_OTHER_COMMANDER
    assert cards["Forest"]["tier"] != "N"
