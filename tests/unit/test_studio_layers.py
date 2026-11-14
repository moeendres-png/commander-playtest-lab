"""Bewertungsebenen: pod scaling from the oracle text, the measured share layers, the result.

The pod scaling table uses real Oracle texts (as Scryfall publishes them). Everything else is
synthetic. A layer value is never 0 for a missing observation, and a layer never changes the
tier unless the Owner gives it a weight.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from commander_lab.studio import layers, strength
from commander_lab.studio.layers import (
    AtlasRecord,
    LayerCard,
    classify_pod_scaling,
    compute_layers,
    pod_factor,
    share_layer,
)
from commander_lab.studio.strength import Observation, PoolContext, StrengthSettings

# (card, oracle text, class, flag, matched phrases)
POD_CASES = [
    (
        "Gray Merchant of Asphodel",
        "When this creature enters, each opponent loses X life, where X is your devotion to black. You gain life equal to the life lost this way. (Each {B} in the mana costs of permanents you control counts toward your devotion to black.)",
        "SCALES",
        None,
        ["each opponent"],
    ),
    (
        "Impact Tremors",
        "Whenever a creature you control enters, this enchantment deals 1 damage to each opponent.",
        "SCALES",
        None,
        ["each opponent"],
    ),
    (
        "Wheel of Fortune",
        "Each player discards their hand, then draws seven cards.",
        "SCALES",
        "SYMMETRIC",
        ["each player"],
    ),
    (
        "Windfall",
        "Each player discards their hand, then draws cards equal to the greatest number of cards a player discarded this way.",
        "SCALES",
        "SYMMETRIC",
        ["each player"],
    ),
    (
        "The Emperor of Palamecia // The Lord Master of Hell",
        "{T}: Add {U} or {R}. Spend this mana only to cast a noncreature spell.\nWhenever you cast a noncreature spell, if at least four mana was spent to cast it, put a +1/+1 counter on The Emperor of Palamecia. Then if it has three or more +1/+1 counters on it, transform it.\n//\nStarfall — Whenever The Lord Master of Hell attacks, it deals X damage to each opponent, where X is the number of noncreature, nonland cards in your graveyard.",
        "SCALES",
        None,
        ["each opponent"],
    ),
    (
        "Maestros Charm",
        "Choose one —\n• Look at the top five cards of your library. Put one of those cards into your hand and the rest into your graveyard.\n• Each opponent loses 3 life and you gain 3 life.\n• Maestros Charm deals 5 damage to target creature or planeswalker.",
        "SCALES",
        None,
        ["each opponent"],
    ),
    ("Silence", "Your opponents can't cast spells this turn.", "SCALES", None, ["your opponents"]),
    (
        "Narset, Parter of Veils",
        "Each opponent can't draw more than one card each turn.\n\u22122: Look at the top four cards of your library. You may reveal a noncreature, nonland card from among them and put it into your hand. Put the rest on the bottom of your library in a random order.",
        "SCALES",
        None,
        ["each opponent"],
    ),
    (
        "Killer Service",
        'When this enchantment enters, create a number of Food tokens equal to the number of opponents you have. (They\'re artifacts with "{2}, {T}, Sacrifice this token: You gain 3 life.")\nAt the beginning of your end step, you may pay {2} and sacrifice a token. If you do, create a 4/4 green Rhino Warrior creature token.',
        "SCALES",
        None,
        ["number of opponents"],
    ),
    (
        "Rhystic Study",
        "Whenever an opponent casts a spell, you may draw a card unless that player pays {1}.",
        "OPPONENT_TRIGGER",
        None,
        ["whenever an opponent"],
    ),
    (
        "Mystic Remora",
        "Cumulative upkeep {1} (At the beginning of your upkeep, put an age counter on this permanent, then sacrifice it unless you pay its upkeep cost for each age counter on it.)\nWhenever an opponent casts a noncreature spell, you may draw a card unless that player pays {4}.",
        "OPPONENT_TRIGGER",
        None,
        ["whenever an opponent"],
    ),
    (
        "Howling Mine",
        "At the beginning of each player's draw step, if this artifact is untapped, that player draws an additional card.",
        "OPPONENT_TRIGGER",
        "SYMMETRIC",
        ["at the beginning of each player's"],
    ),
    (
        "Smothering Tithe",
        "Whenever an opponent draws a card, that player may pay {2}. If the player doesn't, you create a Treasure token. (It's an artifact with \"{T}, Sacrifice this token: Add one mana of any color.\")",
        "OPPONENT_TRIGGER",
        None,
        ["whenever an opponent"],
    ),
    (
        "Coveted Jewel",
        "When this artifact enters, draw three cards.\n{T}: Add three mana of any one color.\nWhenever one or more creatures an opponent controls attack you and aren't blocked, that player draws three cards and gains control of this artifact. Untap it.",
        "OPPONENT_TRIGGER",
        None,
        ["whenever ... an opponent controls"],
    ),
    (
        "Zndrsplt, Eye of Wisdom",
        "Partner with Okaun, Eye of Chaos (When this creature enters, target player may put Okaun into their hand from their library, then shuffle.)\nAt the beginning of combat on your turn, flip a coin until you lose a flip.\nWhenever a player wins a coin flip, draw a card.",
        "OPPONENT_TRIGGER",
        "SYMMETRIC",
        ["whenever a player"],
    ),
    (
        "Kederekt Parasite",
        "Whenever an opponent draws a card, if you control a red permanent, you may have this creature deal 1 damage to that player.",
        "OPPONENT_TRIGGER",
        None,
        ["whenever an opponent"],
    ),
    (
        "Swords to Plowshares",
        "Exile target creature. Its controller gains life equal to its power.",
        "SINGLE_TARGET",
        None,
        ["exile target creature"],
    ),
    ("Counterspell", "Counter target spell.", "SINGLE_TARGET", None, ["counter target spell"]),
    (
        "Lightning Bolt",
        "Lightning Bolt deals 3 damage to any target.",
        "SINGLE_TARGET",
        None,
        ["deals 3 damage to any target"],
    ),
    ("Mind Rot", "Target player discards two cards.", "NEUTRAL", None, []),
    (
        "Deep Analysis",
        "Target player draws two cards.\nFlashback—{1}{U}, Pay 3 life.",
        "NEUTRAL",
        None,
        [],
    ),
    (
        "Battle Angels of Tyr",
        "Flying, myriad\nWhenever this creature deals combat damage to a player, draw a card.",
        "SCALES",
        None,
        ["Myriad"],
    ),
    (
        "Arcane Lighthouse",
        "{T}: Add {C}.\n{1}, {T}: Until end of turn, creatures your opponents control lose hexproof and shroud and can't have hexproof or shroud.",
        "SCALES",
        None,
        ["… your opponents control"],
    ),
    (
        "Swiftfoot Boots",
        "Equipped creature has hexproof and haste. (It can't be the target of spells or abilities your opponents control.)\nEquip {1}",
        "NEUTRAL",
        None,
        [],
    ),
    (
        "Privileged Position",
        "Other permanents you control have hexproof. They can't be the targets of spells or abilities your opponents control.",
        "NEUTRAL",
        None,
        [],
    ),
    (
        "Beast Within",
        "Destroy target permanent. Its controller creates a 3/3 green Beast creature token.",
        "SINGLE_TARGET",
        None,
        ["destroy target permanent"],
    ),
    (
        "Vindictive Lich",
        "When this creature dies, choose one or more. Each mode must target a different player.\n• Target opponent sacrifices a creature of their choice.\n• Target opponent discards two cards.\n• Target opponent loses 5 life.",
        "SINGLE_TARGET",
        None,
        ["target opponent"],
    ),
    (
        "Kolaghan's Command",
        "Choose two —\n• Return target creature card from your graveyard to your hand.\n• Target player discards a card.\n• Destroy target artifact.\n• Kolaghan's Command deals 2 damage to any target.",
        "SINGLE_TARGET",
        None,
        ["destroy target artifact"],
    ),
    (
        "Forbidden Orchard",
        "{T}: Add one mana of any color.\nWhenever you tap this land for mana, target opponent creates a 1/1 colorless Spirit creature token.",
        "SINGLE_TARGET",
        None,
        ["target opponent"],
    ),
    ("Giant Growth", "Target creature gets +3/+3 until end of turn.", "NEUTRAL", None, []),
    (
        "Pacifism",
        "Enchant creature\nEnchanted creature can't attack or block.",
        "NEUTRAL",
        None,
        [],
    ),
    ("Sol Ring", "{T}: Add {C}{C}.", "NEUTRAL", None, []),
    ("Forest", "({T}: Add {G}.)", "NEUTRAL", None, []),
    (
        "Blade of Selves",
        "Equipped creature has myriad. (Whenever it attacks, for each opponent other than defending player, you may create a token copy that's tapped and attacking that player or a planeswalker they control. Exile the tokens at end of combat.)\nEquip {4}",
        "NEUTRAL",
        None,
        [],
    ),
    (
        "Fact or Fiction",
        "Reveal the top five cards of your library. An opponent separates those cards into two piles. Put one pile into your hand and the other into your graveyard.",
        "NEUTRAL",
        None,
        [],
    ),
    (
        "Fire // Ice",
        "Fire deals 2 damage divided as you choose among one or two targets.\n//\nTap target permanent.\nDraw a card.",
        "NEUTRAL",
        None,
        [],
    ),
    (
        "Edgar Markov",
        "Eminence — Whenever you cast another Vampire spell, if Edgar is in the command zone or on the battlefield, create a 1/1 black Vampire creature token.\nFirst strike, haste\nWhenever Edgar attacks, put a +1/+1 counter on each Vampire you control.",
        "NEUTRAL",
        None,
        [],
    ),
    ("Armageddon", "Destroy all lands.", "NEUTRAL", None, []),
    (
        "Rakdos Charm",
        "Choose one —\n• Exile target player's graveyard.\n• Destroy target artifact.\n• Each creature deals 1 damage to its controller.",
        "SINGLE_TARGET",
        None,
        ["destroy target artifact"],
    ),
    (
        "Silverquill Charm",
        "Choose one —\n• Put two +1/+1 counters on target creature.\n• Exile target creature with power 2 or less.\n• Each opponent loses 3 life and you gain 3 life.",
        "SCALES",
        None,
        ["each opponent"],
    ),
    (
        "Dathon and Picard at El-Adrel",
        "Choose one —\n• Temba, His Arms Wide — Target creature gets +3/+3 and gains trample until end of turn.\n• Shaka, When the Walls Fell — Each opponent sacrifices a nontoken artifact or enchantment of their choice.",
        "SCALES",
        None,
        ["each opponent"],
    ),
    (
        "Terror of the Peaks",
        "Flying\nSpells your opponents cast that target this creature cost an additional 3 life to cast.\nWhenever another creature you control enters, this creature deals damage equal to that creature's power to any target.",
        "SCALES",
        None,
        ["your opponents"],
    ),
    (
        "Fireball",
        "This spell costs {1} more to cast for each target beyond the first.\nFireball deals X damage divided evenly, rounded down, among any number of targets.",
        "NEUTRAL",
        None,
        [],
    ),
    (
        "Loran of the Third Path",
        "Vigilance\nWhen Loran enters, destroy up to one target artifact or enchantment.\n{T}: You and target opponent each draw a card.",
        "SINGLE_TARGET",
        None,
        ["target opponent"],
    ),
    (
        "Esper Charm",
        "Choose one —\n• Destroy target enchantment.\n• Draw two cards.\n• Target player discards two cards.",
        "SINGLE_TARGET",
        None,
        ["destroy target enchantment"],
    ),
    (
        "Hunted Bonebrute",
        "Menace\nWhen this creature enters, target opponent creates two 1/1 white Dog creature tokens.\nWhen this creature dies, each opponent loses 3 life.\nDisguise {1}{B}",
        "SCALES",
        None,
        ["each opponent"],
    ),
    (
        "Sheoldred, Whispering One",
        "Swampwalk (This creature can't be blocked as long as defending player controls a Swamp.)\nAt the beginning of your upkeep, return target creature card from your graveyard to the battlefield.\nAt the beginning of each opponent's upkeep, that player sacrifices a creature of their choice.",
        "OPPONENT_TRIGGER",
        None,
        ["at the beginning of each opponent's"],
    ),
    (
        "Seedborn Muse",
        "Untap all permanents you control during each other player's untap step.",
        "SCALES",
        None,
        ["each other player"],
    ),
    (
        "Canopy Cover",
        "Enchant creature\nEnchanted creature can't be blocked except by creatures with flying or reach.\nEnchanted creature can't be the target of spells or abilities your opponents control.",
        "NEUTRAL",
        None,
        [],
    ),
    (
        "Hysterical Blindness",
        "Creatures your opponents control get -4/-0 until end of turn.",
        "SCALES",
        None,
        ["… your opponents control"],
    ),
    (
        "Mana Geyser",
        "Add {R} for each tapped land your opponents control.",
        "SCALES",
        None,
        ["for each … your opponents control"],
    ),
    (
        "Shadowspear",
        "Equipped creature gets +1/+1 and has trample and lifelink.\n{1}: Permanents your opponents control lose hexproof and indestructible until end of turn.\nEquip {2}",
        "SCALES",
        None,
        ["… your opponents control"],
    ),
    (
        "Authority of the Consuls",
        "Creatures your opponents control enter tapped.\nWhenever a creature an opponent controls enters, you gain 1 life.",
        "SCALES",
        None,
        ["… your opponents control", "whenever ... an opponent controls"],
    ),
    (
        "Grand Abolisher",
        "During your turn, your opponents can't cast spells or activate abilities of artifacts, creatures, or enchantments.",
        "SCALES",
        None,
        ["your opponents"],
    ),
    (
        "Aura of Silence",
        "Artifact and enchantment spells your opponents cast cost {2} more to cast.\nSacrifice this enchantment: Destroy target artifact or enchantment.",
        "SCALES",
        None,
        ["your opponents"],
    ),
    (
        "Cyclonic Rift",
        'Return target nonland permanent you don\'t control to its owner\'s hand.\nOverload {6}{U} (You may cast this spell for its overload cost. If you do, change "target" in its text to "each.")',
        "SCALES",
        None,
        ["Overload"],
    ),
    (
        "Winds of Abandon",
        'Exile target creature you don\'t control. For each creature exiled this way, its controller searches their library for a basic land card. Those players put those cards onto the battlefield tapped, then shuffle.\nOverload {4}{W}{W} (You may cast this spell for its overload cost. If you do, change "target" in its text to "each.")',
        "SCALES",
        None,
        ["Overload"],
    ),
    (
        "Mizzium Mortars",
        'Mizzium Mortars deals 4 damage to target creature you don\'t control.\nOverload {3}{R}{R}{R} (You may cast this spell for its overload cost. If you do, change "target" in its text to "each.")',
        "SCALES",
        None,
        ["Overload"],
    ),
    (
        "Ghostly Prison",
        "Creatures can't attack you unless their controller pays {2} for each creature they control that's attacking you.",
        "SCALES",
        None,
        ["can't attack you unless"],
    ),
    (
        "Propaganda",
        "Creatures can't attack you unless their controller pays {2} for each creature they control that's attacking you.",
        "SCALES",
        None,
        ["can't attack you unless"],
    ),
    (
        "Sphere of Safety",
        "Creatures can't attack you or planeswalkers you control unless their controller pays {X} for each of those creatures, where X is the number of enchantments you control.",
        "SCALES",
        None,
        ["creatures can't attack you"],
    ),
    (
        "Dockside Extortionist",
        "When this creature enters, create X Treasure tokens, where X is the number of artifacts and enchantments your opponents control.",
        "SCALES",
        None,
        ["number of … your opponents control"],
    ),
    (
        "Koma, Cosmos Serpent",
        "This spell can't be countered.\nAt the beginning of each upkeep, create a 3/3 blue Serpent creature token named Koma's Coil.\nSacrifice another Serpent: Choose one —\n• Tap target permanent. Its activated abilities can't be activated this turn.\n• Koma gains indestructible until end of turn.",
        "OPPONENT_TRIGGER",
        "SYMMETRIC",
        ["at the beginning of each upkeep"],
    ),
    (
        "Notion Thief",
        "Flash\nIf an opponent would draw a card except the first one they draw in each of their draw steps, instead that player skips that draw and you draw a card.",
        "OPPONENT_TRIGGER",
        None,
        ["if an opponent would"],
    ),
    (
        "Blind Obedience",
        "Extort (Whenever you cast a spell, you may pay {W/B}. If you do, each opponent loses 1 life and you gain that much life.)\nArtifacts and creatures your opponents control enter tapped.",
        "SCALES",
        None,
        ["… your opponents control", "Extort"],
    ),
    (
        "Ephemerate",
        "Exile target creature you control, then return it to the battlefield under its owner's control.\nRebound (If you cast this spell from your hand, exile it as it resolves. At the beginning of your next upkeep, you may cast this card from exile without paying its mana cost.)",
        "NEUTRAL",
        None,
        [],
    ),
    (
        "Eternal Witness",
        "When this creature enters, you may return target card from your graveyard to your hand.",
        "NEUTRAL",
        None,
        [],
    ),
    (
        "Chulane, Teller of Tales",
        "Vigilance\nWhenever you cast a creature spell, draw a card, then you may put a land card from your hand onto the battlefield.\n{3}, {T}: Return target creature you control to its owner's hand.",
        "NEUTRAL",
        None,
        [],
    ),
]


@pytest.mark.parametrize(
    ("name", "text", "cls", "flag", "phrases"), POD_CASES, ids=[case[0] for case in POD_CASES]
)
def test_pod_scaling_class_of_a_real_card(
    name: str, text: str, cls: str, flag: str | None, phrases: list[str]
) -> None:
    found = classify_pod_scaling(text)
    assert (found["cls"], found["flag"], found["phrases"]) == (cls, flag, phrases), name
    assert found["rank"] == layers.POD_CLASS_RANK[cls]
    assert found["note"] == "aus dem Regeltext abgeleitet, keine Messung"


def test_the_table_has_twenty_real_cards_and_every_class_and_the_flag() -> None:
    assert len(POD_CASES) >= 20
    assert {case[2] for case in POD_CASES} == set(layers.POD_CLASSES)
    assert {case[3] for case in POD_CASES} == {None, layers.SYMMETRIC}


def test_classes_are_ordered_strongest_first_and_rank_by_ordinal() -> None:
    assert layers.POD_CLASSES == (
        layers.SCALES,
        layers.OPPONENT_TRIGGER,
        layers.NEUTRAL,
        layers.SINGLE_TARGET,
    )
    assert [layers.POD_CLASS_RANK[name] for name in layers.POD_CLASSES] == [3, 2, 1, 0]


def test_reminder_text_in_parentheses_is_not_matched() -> None:
    text = "Flying (Whenever an opponent casts a spell, each opponent loses 1 life.)"
    found = classify_pod_scaling(text)
    assert (found["cls"], found["phrases"]) == (layers.NEUTRAL, [])
    # the same words outside the parentheses do count
    open_text = "Flying. Whenever an opponent casts a spell, each opponent loses 1 life."
    assert classify_pod_scaling(open_text)["cls"] == layers.SCALES


def test_a_target_opponent_does_not_weaken_a_scaling_clause() -> None:
    text = "Target opponent discards a card. Each opponent loses 1 life."
    found = classify_pod_scaling(text)
    assert (found["cls"], found["phrases"]) == (layers.SCALES, ["each opponent"])
    assert classify_pod_scaling("Target opponent discards a card.")["cls"] == layers.SINGLE_TARGET


@pytest.mark.parametrize(
    ("text", "flag"),
    [
        ("Each player draws a card.", layers.SYMMETRIC),
        ("Whenever a player casts a spell, you gain 1 life.", layers.SYMMETRIC),
        ("At the beginning of each player's upkeep, that player loses 1 life.", layers.SYMMETRIC),
        ("Each opponent draws a card.", None),
        ("Each other player draws a card.", None),
        ("Whenever an opponent casts a spell, you gain 1 life.", None),
        ("Draw a card.", None),
        ("Destroy target creature.", None),
    ],
)
def test_the_symmetric_flag_marks_effects_that_also_hit_you(text: str, flag: str | None) -> None:
    assert classify_pod_scaling(text)["flag"] == flag


def test_the_trigger_clause_does_not_make_each_players_count_as_scaling() -> None:
    found = classify_pod_scaling("At the beginning of each player's upkeep, draw a card.")
    assert (found["cls"], found["phrases"]) == (
        layers.OPPONENT_TRIGGER,
        ["at the beginning of each player's"],
    )


def test_a_pump_spell_or_recursion_on_a_target_is_no_single_target_removal() -> None:
    assert classify_pod_scaling("Target creature gets +2/+2 until end of turn.")["cls"] == (
        layers.NEUTRAL
    )
    recursion = "Return target creature card from your graveyard to your hand."
    assert classify_pod_scaling(recursion)["cls"] == layers.NEUTRAL
    assert classify_pod_scaling("Target creature gets -3/-3 until end of turn.")["cls"] == (
        layers.SINGLE_TARGET
    )


@pytest.mark.parametrize("pod_size", [2, 3, 4, 5, 6])
def test_the_factor_of_a_scaling_card_counts_the_opponents(pod_size: int) -> None:
    assert pod_factor(layers.SCALES, pod_size) == f"wirkt auf {pod_size - 1} Gegner"
    for cls in (layers.OPPONENT_TRIGGER, layers.NEUTRAL, layers.SINGLE_TARGET):
        assert pod_factor(cls, pod_size) is None


@pytest.mark.parametrize("pod_size", [1, 7, 0, -4])
def test_a_pod_size_outside_two_to_six_is_refused(pod_size: int) -> None:
    with pytest.raises(ValueError, match="pod size"):
        pod_factor(layers.SCALES, pod_size)
    with pytest.raises(ValueError, match="pod size"):
        compute_layers({}, {}, {}, pod_size)


# ---------- measured share layers ----------


def test_a_share_counts_with_its_wilson_bound_raw_share_and_sample() -> None:
    item = share_layer("tempo", 40.0, 100, insufficient=False)
    bound = strength.wilson_lower(40, 100)
    assert (item["status"], item["reason"]) == (layers.OK, "")
    assert (item["raw"], item["n"], item["wilson"], item["value"]) == (0.4, 100, bound, bound)


def test_the_minimum_sample_is_25_games_inclusive() -> None:
    thin = share_layer("tempo", 40.0, 24, insufficient=False)
    assert (thin["status"], thin["reason"], thin["value"], thin["n"]) == (
        layers.UNKNOWN,
        layers.SAMPLE_TOO_SMALL,
        None,
        24,
    )
    assert share_layer("tempo", 40.0, 25, insufficient=False)["status"] == layers.OK
    missing = share_layer("tempo", 40.0, None, insufficient=False)
    assert (missing["status"], missing["reason"]) == (layers.UNKNOWN, layers.SAMPLE_TOO_SMALL)


def test_a_record_flagged_insufficient_is_unknown_whatever_its_sample() -> None:
    item = share_layer("tempo", 40.0, 500, insufficient=True)
    assert (item["status"], item["reason"], item["value"]) == (
        layers.UNKNOWN,
        layers.INSUFFICIENT_SAMPLE,
        None,
    )


def test_a_missing_percent_is_unknown_and_a_published_zero_is_a_value() -> None:
    missing = share_layer("tempo", None, 200, insufficient=False)
    assert (missing["status"], missing["reason"], missing["value"]) == (
        layers.UNKNOWN,
        layers.NO_VALUE_PUBLISHED,
        None,
    )
    zero = share_layer("tempo", 0.0, 200, insufficient=False)
    assert (zero["status"], zero["raw"], zero["value"]) == (layers.OK, 0.0, 0.0)


def test_a_percent_that_the_records_own_count_contradicts_is_kept_and_named() -> None:
    item = share_layer("tempo", 30.0, 120, insufficient=False, cross_check=(31, 120))
    assert item["status"] == layers.OK and item["raw"] == 0.3
    assert item["detail"] == {"discrepancy": True}
    assert "31/120" in item["note"]
    agreeing = share_layer("tempo", 26.0, 120, insufficient=False, cross_check=(31, 120))
    assert agreeing["detail"] is None and agreeing["note"] == ""


def _card(type_line: str = "Creature — Bear", **extra: object) -> LayerCard:
    return LayerCard(name="x", text="Draw a card.", type_line=type_line, **extra)  # type: ignore[arg-type]


def test_playability_uses_the_drawn_count_as_its_denominator() -> None:
    record = AtlasRecord(drawn_to_played_pct=75.0, ever_drawn_n=1574, first_cast_n=1173)
    item = compute_layers({"a": _card()}, {"a": record}, {})["cards"]["a"]["playability"]
    assert (item["n"], item["raw"], item["status"], item["detail"]) == (
        1574,
        0.75,
        layers.OK,
        None,
    )
    # first_cast_n is the numerator: without the drawn count there is no denominator
    no_drawn = AtlasRecord(drawn_to_played_pct=60.0, first_cast_n=40)
    thin = compute_layers({"a": _card()}, {"a": no_drawn}, {})["cards"]["a"]["playability"]
    assert (thin["status"], thin["reason"], thin["value"], thin["percentile"]) == (
        layers.UNKNOWN,
        layers.NO_COUNT,
        None,
        None,
    )


def test_staying_without_its_denominator_is_unknown_for_a_missing_count() -> None:
    record = AtlasRecord(battlefield_survival_pct=50.0, still_on_board_at_end_n=30)
    item = compute_layers({"a": _card()}, {"a": record}, {})["cards"]["a"]["staying"]
    assert (item["status"], item["reason"]) == (layers.UNKNOWN, layers.NO_COUNT)


def test_tempo_uses_the_on_curve_denominator() -> None:
    record = AtlasRecord(on_curve_pct=20.0, on_curve_count=40, on_curve_denominator=200)
    item = compute_layers({"a": _card()}, {"a": record}, {})["cards"]["a"]["tempo"]
    assert (item["n"], item["raw"], item["status"]) == (200, 0.2, layers.OK)


def test_tempo_is_the_on_curve_count_over_its_denominator_and_names_a_different_percent() -> None:
    record = AtlasRecord(on_curve_pct=30.0, on_curve_count=31, on_curve_denominator=120)
    item = compute_layers({"a": _card()}, {"a": record}, {})["cards"]["a"]["tempo"]
    bound = strength.wilson_lower(31, 120)
    assert (item["status"], item["raw"], item["n"], item["wilson"], item["value"]) == (
        layers.OK,
        pytest.approx(31 / 120),
        120,
        bound,
        bound,
    )
    assert item["note"] == "Quelle nennt 30 %"
    assert item["detail"] == {"published_pct": 30.0}
    agreeing = AtlasRecord(on_curve_pct=26.0, on_curve_count=31, on_curve_denominator=120)
    same = compute_layers({"a": _card()}, {"a": agreeing}, {})["cards"]["a"]["tempo"]
    assert (same["note"], same["detail"]) == ("", None)
    assert same["raw"] == pytest.approx(31 / 120)


@pytest.mark.parametrize(
    "record",
    [
        AtlasRecord(on_curve_pct=30.0, on_curve_denominator=120),
        AtlasRecord(on_curve_pct=30.0, on_curve_count=31),
        AtlasRecord(on_curve_count=31, on_curve_denominator=120, insufficient_sample=True),
    ],
)
def test_tempo_without_count_or_denominator_is_unknown_not_the_published_percent(
    record: AtlasRecord,
) -> None:
    item = compute_layers({"a": _card()}, {"a": record}, {})["cards"]["a"]["tempo"]
    assert (item["status"], item["value"], item["raw"], item["percentile"]) == (
        layers.UNKNOWN,
        None,
        None,
        None,
    )
    assert item["reason"] in {layers.NO_COUNT, layers.INSUFFICIENT_SAMPLE}


def test_the_summary_counts_the_tempo_records_whose_percent_differs() -> None:
    cards = {name: _card() for name in "abc"}
    atlas = {
        "a": AtlasRecord(on_curve_pct=30.0, on_curve_count=31, on_curve_denominator=120),
        "b": AtlasRecord(on_curve_pct=26.0, on_curve_count=31, on_curve_denominator=120),
        "c": AtlasRecord(on_curve_pct=60.0, on_curve_count=20, on_curve_denominator=100),
    }
    summary = {item["key"]: item for item in compute_layers(cards, atlas, {})["layers"]}
    assert summary["tempo"]["source_discrepancies"] == 2


@pytest.mark.parametrize(
    ("type_line", "status"),
    [
        ("Creature — Bear", layers.OK),
        ("Artifact Creature — Construct", layers.OK),
        ("Land", layers.OK),
        ("Legendary Planeswalker — Chandra", layers.OK),
        ("Sorcery // Land", layers.OK),
        ("Instant", layers.NOT_APPLICABLE),
        ("Sorcery", layers.NOT_APPLICABLE),
    ],
)
def test_standfestigkeit_is_for_permanents_only(type_line: str, status: str) -> None:
    record = AtlasRecord(
        battlefield_survival_pct=50.0, reached_battlefield_n=100, still_on_board_at_end_n=50
    )
    item = compute_layers({"a": _card(type_line)}, {"a": record}, {})["cards"]["a"]["staying"]
    assert item["status"] == status
    if status == layers.NOT_APPLICABLE:
        assert (item["reason"], item["value"], item["percentile"]) == (
            layers.NOT_A_PERMANENT,
            None,
            None,
        )


def test_a_card_without_an_atlas_row_is_unknown_never_zero() -> None:
    result = compute_layers({"a": _card()}, {}, {})["cards"]["a"]
    for key in ("tempo", "playability", "staying", "win_gap"):
        item = result[key]
        assert (item["status"], item["reason"], item["value"], item["percentile"]) == (
            layers.UNKNOWN,
            layers.NO_RECORD,
            None,
            None,
        ), key


def test_the_commander_and_basic_lands_get_no_value_and_no_rank() -> None:
    cards = {
        "boss": LayerCard("Boss", "Draw a card.", "Legendary Creature", "NOT_RANKED_COMMANDER"),
        "forest": LayerCard("Forest", None, "Basic Land — Forest", "NOT_RANKED_BASIC_LAND"),
        "a": _card(),
        "b": _card(),
    }
    atlas = {
        key: AtlasRecord(on_curve_count=round(pct), on_curve_denominator=100)
        for key, pct in (("boss", 90.0), ("forest", 90.0), ("a", 10.0), ("b", 20.0))
    }
    result = compute_layers(cards, atlas, {})
    for key in ("boss", "forest"):
        for layer in layers.ALL_LAYER_KEYS:
            item = result["cards"][key][layer]
            assert (item["status"], item["reason"], item["value"], item["percentile"]) == (
                layers.NOT_APPLICABLE,
                layers.NOT_RANKED,
                None,
                None,
            )
    assert [result["cards"][key]["tempo"]["percentile"] for key in ("a", "b")] == [0.0, 100.0]
    summary = {item["key"]: item for item in result["layers"]}["tempo"]
    assert (summary["pool_cards"], summary["with_value"], summary["not_applicable"]) == (2, 2, 0)


def test_percentiles_run_from_0_to_100_and_ties_share_the_mean_rank() -> None:
    cards = {name: _card() for name in "abcd"}
    atlas = {
        name: AtlasRecord(on_curve_count=round(10 * pct), on_curve_denominator=1000)
        for name, pct in (("a", 10.0), ("b", 30.0), ("c", 30.0), ("d", 60.0))
    }
    result = compute_layers(cards, atlas, {})["cards"]
    assert [result[name]["tempo"]["percentile"] for name in "abcd"] == [0.0, 50.0, 50.0, 100.0]
    single = compute_layers({"a": _card()}, {"a": atlas["a"]}, {})["cards"]["a"]["tempo"]
    assert single["percentile"] == 50.0


def test_pod_scaling_percentile_ranks_the_class_ordinal() -> None:
    texts = {
        "scales": "Each opponent loses 1 life.",
        "trigger": "Whenever an opponent casts a spell, draw a card.",
        "neutral": "Draw a card.",
        "single": "Counter target spell.",
    }
    cards = {key: LayerCard(key, text, "Instant") for key, text in texts.items()}
    result = compute_layers(cards, {}, {})["cards"]
    values = {key: result[key]["pod_scaling"]["value"] for key in texts}
    assert values == {"scales": 3.0, "trigger": 2.0, "neutral": 1.0, "single": 0.0}
    assert [result[key]["pod_scaling"]["percentile"] for key in texts] == [
        100.0,
        pytest.approx(66.7, abs=0.05),
        pytest.approx(33.3, abs=0.05),
        0.0,
    ]


def test_a_card_without_oracle_text_has_no_pod_scaling_value() -> None:
    result = compute_layers({"a": LayerCard("A", None, "Creature")}, {}, {})["cards"]["a"]
    item = result["pod_scaling"]
    assert (item["status"], item["reason"], item["value"]) == (
        layers.UNKNOWN,
        layers.NO_TEXT,
        None,
    )
    empty = compute_layers({"a": LayerCard("A", "", "Creature")}, {}, {})["cards"]["a"]
    assert empty["pod_scaling"]["status"] == layers.OK  # vanilla: neutral, not unknown


def test_the_pod_size_changes_only_the_shown_factor() -> None:
    cards = {"a": LayerCard("A", "Each opponent loses 1 life.", "Sorcery")}
    small = compute_layers(cards, {}, {}, 2)
    large = compute_layers(cards, {}, {}, 6)
    small_item, large_item = small["cards"]["a"]["pod_scaling"], large["cards"]["a"]["pod_scaling"]
    assert small_item["detail"]["factor"] == "wirkt auf 1 Gegner"  # type: ignore[index]
    assert large_item["detail"]["factor"] == "wirkt auf 5 Gegner"  # type: ignore[index]
    for key in ("value", "percentile", "status", "reason"):
        assert small_item[key] == large_item[key]  # type: ignore[literal-required]
    assert small["pod_size"] == 2 and "nur die gezeigte Zahl" in small["pod_note"]


def test_the_win_gap_layer_is_the_gap_exactly_as_the_index_reads_it() -> None:
    observations = {
        "small": Observation(10.0, None, 25),
        "large": Observation(10.0, None, 100),
        "negative": Observation(-4.0, None, 100),
        "thin": Observation(30.0, None, 24),
    }
    cards = {key: _card() for key in (*observations, "none")}
    result = compute_layers(cards, {}, observations)["cards"]
    assert result["large"]["win_gap"]["value"] == strength.observed_gap(observations["large"])
    assert result["large"]["win_gap"]["value"] == 8.0
    assert (result["large"]["win_gap"]["raw"], result["large"]["win_gap"]["n"]) == (10.0, 100)
    assert result["small"]["win_gap"]["value"] == 5.0
    for key, reason in (("thin", layers.SAMPLE_TOO_SMALL), ("none", layers.NO_RECORD)):
        item = result[key]["win_gap"]
        assert (item["status"], item["reason"], item["value"]) == (layers.UNKNOWN, reason, None)
    # the layer ranks the cards like the index component does
    only_gap = StrengthSettings(
        weights={name: 0.0 for name in strength.COMPONENTS} | {strength.PLAYGROUP_OBSERVED: 1.0},
        min_coverage=0.0,
        min_components=1,
    )
    scored = strength.score_pool(
        only_gap,
        {key: {strength.PLAYGROUP_OBSERVED: obs} for key, obs in observations.items()},
        {strength.PLAYGROUP_OBSERVED},
    )
    for key in ("small", "large", "negative"):
        row = scored[key]["components"][strength.COMPONENTS.index(strength.PLAYGROUP_OBSERVED)]
        assert row["percentile"] is not None
        assert round(100 * row["percentile"], 1) == result[key]["win_gap"]["percentile"]


def test_the_summary_counts_values_unknowns_and_the_kind_of_every_layer() -> None:
    cards = {name: _card() for name in "abc"}
    atlas = {"a": AtlasRecord(on_curve_count=10, on_curve_denominator=100)}
    summary = {item["key"]: item for item in compute_layers(cards, atlas, {})["layers"]}
    assert list(summary) == ["pod_scaling", "tempo", "playability", "staying", "win_gap"]
    assert (summary["tempo"]["with_value"], summary["tempo"]["unknown"]) == (1, 2)
    assert summary["pod_scaling"]["with_value"] == 3
    assert summary["pod_scaling"]["kind"] == layers.KIND_DERIVED
    assert summary["tempo"]["kind"] == layers.KIND_MEASURED
    assert summary["playability"]["denominator"].startswith("ever_drawn_n")
    assert summary["win_gap"]["weight_allowed"] is False
    assert summary["tempo"]["weight_allowed"] is True


# ---------- settings and the index ----------


def test_the_layer_weights_and_the_pod_size_default_to_the_recommendation() -> None:
    defaults = StrengthSettings()
    assert defaults.layer_weights == {
        "pod_scaling": 0.0,
        "tempo": 0.0,
        "playability": 0.0,
        "staying": 0.0,
    }
    assert defaults.pod_size == 4
    assert defaults.active_layers() == ()
    assert set(strength.LAYER_KEYS) == set(defaults.layer_weights)
    for name, preset in strength.PRESETS.items():
        assert preset.layer_weights == defaults.layer_weights, name
        assert preset.weights[strength.SIMULATION] == 0.0, name


@pytest.mark.parametrize(
    "raw",
    [
        {"layer_weights": {"win_gap": 1}},
        {"layer_weights": {"unknown": 1}},
        {"layer_weights": {"tempo": -1}},
        {"layer_weights": {"tempo": 101}},
        {"layer_weights": {"tempo": True}},
        {"layer_weights": []},
        {"pod_size": 1},
        {"pod_size": 7},
        {"pod_size": 4.0},
        {"pod_size": True},
    ],
)
def test_invalid_layer_settings_are_refused(raw: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        StrengthSettings.from_dict(raw)


def test_the_layer_settings_survive_a_round_trip_and_an_older_profile_gets_defaults() -> None:
    settings = StrengthSettings.from_dict({"layer_weights": {"tempo": 2}, "pod_size": 6})
    assert settings.layer_weights["tempo"] == 2.0 and settings.pod_size == 6
    assert StrengthSettings.from_dict(settings.to_dict()) == settings
    legacy = {key: value for key, value in settings.to_dict().items() if key != "layer_weights"}
    del legacy["pod_size"]
    restored, ignored = StrengthSettings.from_stored(legacy)
    assert ignored == [] and restored.layer_weights == StrengthSettings().layer_weights
    assert restored.pod_size == 4


def _two_signal_pool() -> dict[str, dict[str, Observation]]:
    """Three cards: commander inclusion ranks a < b < c, the tempo layer ranks c < b < a."""
    inclusion = {"a": 10, "b": 20, "c": 30}
    tempo = {"a": 0.5, "b": 0.3, "c": 0.1}
    return {
        card: {
            strength.COMMANDER_INCLUSION: Observation(inclusion[card] / 100, inclusion[card], 100),
            strength.layer_component("tempo"): Observation(tempo[card], None, 100),
        }
        for card in "abc"
    }


def _only(weights: dict[str, float], **extra: object) -> StrengthSettings:
    base = {name: 0.0 for name in strength.COMPONENTS}
    base[strength.COMMANDER_INCLUSION] = 1.0
    base.update(weights)
    return StrengthSettings(
        weights=base,
        min_coverage=0.0,
        min_components=1,
        **extra,  # type: ignore[arg-type]
    )


def test_a_layer_with_weight_zero_changes_nothing_in_the_index() -> None:
    collected = {strength.COMMANDER_INCLUSION, strength.layer_component("tempo")}
    pool = _two_signal_pool()
    without_layer = {
        card: {strength.COMMANDER_INCLUSION: obs[strength.COMMANDER_INCLUSION]}
        for card, obs in pool.items()
    }
    plain = strength.score_pool(_only({}), without_layer, {strength.COMMANDER_INCLUSION})
    with_layer_data = strength.score_pool(_only({}), pool, collected)
    assert with_layer_data == plain
    assert [row["component"] for row in with_layer_data["a"]["components"]] == list(
        strength.COMPONENTS
    )


def test_a_weighted_layer_joins_the_index_as_one_more_ranked_component() -> None:
    collected = {strength.COMMANDER_INCLUSION, strength.layer_component("tempo")}
    settings = _only({}, layer_weights={"tempo": 1.0}, share_scale="rank")
    scored = strength.score_pool(settings, _two_signal_pool(), collected)
    # inclusion percentile a 0, b .5, c 1; tempo percentile a 1, b .5, c 0: the mean is .5 each
    assert [scored[card]["index"] for card in "abc"] == [50.0, 50.0, 50.0]
    row = scored["a"]["components"][-1]
    assert (row["component"], row["label"], row["weight"], row["percentile"]) == (
        "layer_tempo",
        "Tempo",
        1.0,
        1.0,
    )
    assert row["signal"] == "playgroup_on_curve_pct" and row["status"] == strength.PRESENT
    lopsided = strength.score_pool(
        _only({}, layer_weights={"tempo": 3.0}, share_scale="rank"), _two_signal_pool(), collected
    )
    assert [lopsided[card]["index"] for card in "abc"] == [75.0, 50.0, 25.0]
    # Under default share_scale="share", the layer itself still ranks by percentile (1, 0.5, 0)
    default_scored = strength.score_pool(
        _only({}, layer_weights={"tempo": 1.0}), _two_signal_pool(), collected
    )
    assert [default_scored[c]["components"][-1]["percentile"] for c in "abc"] == [1.0, 0.5, 0.0]


def test_a_weighted_layer_counts_in_the_coverage_of_cards_without_a_value() -> None:
    pool = _two_signal_pool()
    del pool["c"][strength.layer_component("tempo")]
    scored = strength.score_pool(
        _only({}, layer_weights={"tempo": 1.0}),
        pool,
        {strength.COMMANDER_INCLUSION, strength.layer_component("tempo")},
    )
    assert scored["a"]["coverage"] == 1.0 and scored["c"]["coverage"] == 0.5
    row = scored["c"]["components"][-1]
    assert (row["status"], row["percentile"]) == (strength.NO_VALUE, None)


def test_no_layer_can_satisfy_the_commander_signal_rule() -> None:
    assert not any(name.startswith(strength.LAYER_PREFIX) for name in strength.COMMANDER_SPECIFIC)
    pool = {"a": {strength.layer_component("tempo"): Observation(0.4, None, 100)}}
    only_layer = StrengthSettings(
        weights={name: 0.0 for name in strength.COMPONENTS},
        layer_weights={"tempo": 1.0},
        min_coverage=0.0,
        min_components=1,
    )
    scored = strength.score_pool(only_layer, pool, {strength.layer_component("tempo")})
    assert (scored["a"]["tier"], scored["a"]["reason"]) == (
        strength.TIER_UNKNOWN,
        strength.NO_COMMANDER_SIGNAL,
    )


def test_the_commander_and_basics_stay_unranked_with_a_weighted_layer() -> None:
    pool = _two_signal_pool()
    context = PoolContext(unranked={"a": strength.NOT_RANKED_COMMANDER})
    scored = strength.score_pool(
        _only({}, layer_weights={"tempo": 1.0}, share_scale="rank"),
        pool,
        {strength.COMMANDER_INCLUSION, strength.layer_component("tempo")},
        context=context,
    )
    assert scored["a"]["tier"] == strength.TIER_NOT_RANKED and scored["a"]["index"] is None
    assert [scored[card]["index"] for card in "bc"] == [50.0, 50.0]


def test_a_layer_never_reads_the_owners_marks_or_prices() -> None:
    folder = Path(layers.__file__).parent
    source = (
        (folder / "layers.py").read_text(encoding="utf-8")
        + (folder / "layers_view.py").read_text(encoding="utf-8")
    ).lower()
    for word in ("favorite", "excluded", "price", "card_mark"):
        assert word not in source, word


def test_a_keyword_is_only_matched_on_a_keyword_line_and_long_lines_stay_fast() -> None:
    import time

    for text in (
        "Myriad Landscape enters tapped.",
        "When this creature enters, extort the truth from target player.",
        "Melee weapons you control have haste.",
    ):
        assert classify_pod_scaling(text)["cls"] == layers.NEUTRAL, text
    assert classify_pod_scaling("Flying, vigilance, myriad")["phrases"] == ["Myriad"]
    assert classify_pod_scaling("Overload {3}{R}{R}{R}")["phrases"] == ["Overload"]
    started = time.perf_counter()
    classify_pod_scaling(", ".join(["flying"] * 40) + " and then some text that is no keyword")
    assert time.perf_counter() - started < 0.5
