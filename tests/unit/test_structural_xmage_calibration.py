from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest

from commander_lab.engine.rules.project import load_rules_deck_snapshot
from commander_lab.engine.structural.card_facts import (
    CardFacts,
    CardFactsCatalog,
    apply_card_facts,
    commander_stats,
    load_card_facts,
    profile_from_facts,
)
from commander_lab.engine.structural.simulator import DEFAULT_TUNING, StructuralTuning
from commander_lab.engine.structural.simulator_fidelity import StructuralSimulator
from commander_lab.engine.structural.xmage_calibration import (
    XmagePod,
    calibration_metrics,
    fact_deck_profile,
    pod_from_record,
    spearman,
    split_pods,
    structural_win_probabilities,
)
from commander_lab.models import CardRole, Color, RulesDeckInput, StructuralCardProfile

ROOT = Path(__file__).resolve().parents[2]


def _facts(name: str, **values: Any) -> CardFacts:
    return CardFacts(
        name=name,
        mana_value=values.get("mana_value", 3.0),
        types=tuple(values.get("types", ("CREATURE",))),
        subtypes=(),
        supertypes=tuple(values.get("supertypes", ())),
        power=values.get("power"),
        toughness=values.get("toughness"),
        rules=tuple(values.get("rules", ())),
        mana_cost=str(values.get("mana_cost", "")),
    )


def _record(seat: int, winner: int | None, *, status: str = "completed") -> dict[str, Any]:
    return {
        "status": status,
        "run_key": f"k{seat}{winner}",
        "result": {
            "scenario": {
                "seat": seat,
                "seed": 7,
                "candidate_id": "me",
                "opponent_deck_ids": ["a", "b", "c"],
            },
            "result_payload": {
                "terminal": True,
                "turn_number": 40,
                "outcomes": [{"seat": index, "won": index == winner} for index in range(4)],
            },
        },
    }


def test_pod_from_record_puts_the_candidate_in_its_seat() -> None:
    pod = pod_from_record(_record(seat=3, winner=2))
    assert pod is not None
    assert pod.deck_ids == ("a", "b", "me", "c")
    assert pod.winner_seat == 2
    assert pod_from_record(_record(seat=1, winner=None)).winner_seat is None  # type: ignore[union-attr]
    assert pod_from_record(_record(seat=1, winner=0, status="failed")) is None


def test_facts_give_uncurated_creatures_their_power_and_keep_curated_values() -> None:
    bear = _facts("Grizzly Bears", power=2.0, rules=())
    profile = profile_from_facts("Grizzly Bears", bear)
    assert profile.is_creature and profile.base_power == 2.0
    flier = _facts("Serra Angel", power=4.0, rules=("Flying, vigilance",))
    assert profile_from_facts("Serra Angel", flier).base_power == pytest.approx(5.0)
    curated = StructuralCardProfile(
        oracle_name="Ishai", roles=frozenset({CardRole.ENABLER}), is_creature=True, base_power=3.5
    )
    assert apply_card_facts(curated, _facts("Ishai", power=1.0)).base_power == 3.5


def test_commander_stats_are_the_commander_cards_own_power() -> None:
    """A commander's base power is the card's power, not the evasion-bumped combat value.

    ``commander_base_power`` is the card fact the deck profile asserts and the simulator
    derives commander damage from it; using ``combat_power`` restated Sauron, a printed
    9-power trampler, as 11.25 and counted its evasion twice (#759).
    """
    trampler = _facts(
        "Sauron, Lord of the Rings",
        mana_value=8.0,
        power=9.0,
        toughness=9.0,
        rules=("Trample",),
    )
    catalog = CardFactsCatalog({"Sauron, Lord of the Rings": trampler})
    assert commander_stats("Sauron, Lord of the Rings", catalog) == (8.0, 9.0)
    # Uncurated cards keep the combat-model power: evasion adds a little to a body's power.
    assert profile_from_facts("Sauron, Lord of the Rings", trampler).base_power == pytest.approx(
        11.25
    )


def test_commander_stats_stay_unknown_when_the_facts_have_no_power() -> None:
    planeswalker = _facts(
        "Quintorius, History Chaser",
        mana_value=4.0,
        types=("PLANESWALKER",),
        rules=("+1: You may discard a card.",),
    )
    catalog = CardFactsCatalog({"Quintorius, History Chaser": planeswalker})
    assert commander_stats("Quintorius, History Chaser", catalog) is None
    assert commander_stats("Nobody Here", catalog) is None
    deck = RulesDeckInput(
        deck_id="d",
        name="Unknown commander deck",
        deck_hash=None,
        commander_names=("Quintorius, History Chaser",),
        mainboard=tuple(f"Filler {index}" for index in range(99)),
    )
    profile, report = fact_deck_profile(deck, known={}, facts=catalog, snapshot_hash="test")
    assert report.without_facts == [f"Filler {index}" for index in range(99)]
    assert profile.commander_base_power["Quintorius, History Chaser"] == 2.0


def test_uncurated_lands_and_mana_rocks_take_their_colours_from_the_rules() -> None:
    temple = _facts(
        "Test Temple",
        mana_value=0.0,
        types=("LAND",),
        rules=("{this} enters tapped.", "{T}: Add {U}.", "{T}: Add {R}."),
    )
    painland = _facts(
        "Test Painland",
        mana_value=0.0,
        types=("LAND",),
        rules=("{T}: Add {C}.", "{T}: Add {W}. {this} deals 1 damage to you."),
    )
    rock = _facts(
        "Test Signet",
        mana_value=2.0,
        types=("ARTIFACT",),
        rules=("{1}, {T}: Add {G}{U}.",),
    )
    any_color = _facts(
        "Test Gem",
        mana_value=2.0,
        types=("ARTIFACT",),
        rules=("{T}: Add one mana of any color.",),
    )
    assert profile_from_facts("Test Temple", temple).produces_colors == {Color.BLUE, Color.RED}
    assert profile_from_facts("Test Painland", painland).produces_colors == {Color.WHITE}
    assert profile_from_facts("Test Signet", rock).produces_colors == {Color.GREEN, Color.BLUE}
    assert profile_from_facts("Test Gem", any_color).produces_colors == set(Color)
    curated = StructuralCardProfile(oracle_name="Test Temple", is_land=True, roles=frozenset())
    assert apply_card_facts(curated, temple).produces_colors == frozenset()


def test_a_commander_without_curated_pips_takes_its_colour_cost_from_the_facts() -> None:
    chulane = _facts("Chulane", mana_value=5.0, power=4.0, toughness=5.0, mana_cost="{2}{G}{W}{U}")
    catalog = CardFactsCatalog({"Chulane": chulane, "Bears": _facts("Bears", mana_cost="{1}{G}")})
    curated = StructuralCardProfile(oracle_name="Chulane", roles=frozenset())
    deck = RulesDeckInput(
        deck_id="d",
        name="Commander pips",
        deck_hash=None,
        commander_names=("Chulane",),
        mainboard=("Bears",) * 99,
    )
    profile, _ = fact_deck_profile(
        deck, known={"Chulane": curated}, facts=catalog, snapshot_hash="test"
    )
    by_name = {card.oracle_name: card for card in profile.cards}
    assert {
        color.value: count for color, count in by_name["Chulane"].color_requirements.items()
    } == {
        "G": 1,
        "U": 1,
        "W": 1,
    }
    assert by_name["Bears"].color_requirements == {}


def test_facts_mark_finishers_from_their_text() -> None:
    drain = _facts("Test Drain Spell", types=("SORCERY",), rules=("Each opponent loses X life.",))
    profile = profile_from_facts("Test Drain Spell", drain)
    assert CardRole.FINISHER in profile.roles
    assert profile.role_strengths[CardRole.FINISHER] == 1.0


def test_fact_lookup_ignores_case_accents_and_back_faces() -> None:
    catalog = CardFactsCatalog(
        {"Troll of Khazad-dum": _facts("Troll of Khazad-dum", power=6.0), "Wear": _facts("Wear")}
    )
    assert catalog.get("Troll of Khazad-dûm") is not None
    assert catalog.get("Wear // Tear") is not None
    assert catalog.get("Nothing Here") is None


def test_metrics_reward_the_model_that_ranks_like_xmage() -> None:
    pods = [XmagePod(f"g{index}", index, ("strong", "weak", "x", "y"), 0, 48) for index in range(6)]
    right = [[0.7, 0.1, 0.1, 0.1]] * 6
    wrong = [[0.1, 0.7, 0.1, 0.1]] * 6
    good = calibration_metrics(pods, right, [12.0] * 6, min_games=1)
    bad = calibration_metrics(pods, wrong, [12.0] * 6, min_games=1)
    assert good["log_loss"] == pytest.approx(-math.log(0.7))
    assert good["log_loss"] < good["log_loss_uniform"] < bad["log_loss"]
    assert good["xmage_mean_rounds"] == 12.0
    assert spearman([1, 2, 3], [10, 20, 30]) == pytest.approx(1.0)
    assert spearman([1, 2, 3], [30, 20, 10]) == pytest.approx(-1.0)
    first, second = split_pods(pods)
    assert len(first) == len(second) == 3
    assert {pod.game_key for pod in first}.isdisjoint(pod.game_key for pod in second)


def test_default_tuning_is_the_long_standing_model() -> None:
    assert StructuralTuning() == DEFAULT_TUNING
    assert DEFAULT_TUNING.creature_attack == 0.62
    assert set(DEFAULT_TUNING.as_dict()) >= {"creature_attack", "finisher_damage"}


@pytest.mark.skipif(load_card_facts(ROOT) is None, reason="card facts not exported")
def test_a_collection_deck_replays_in_the_structural_model() -> None:
    facts = load_card_facts(ROOT)
    assert facts is not None
    deck: RulesDeckInput = load_rules_deck_snapshot(
        ROOT / "data/coverage_decks/collection/agrus.json"
    )
    profile, report = fact_deck_profile(deck, known={}, facts=facts, snapshot_hash="test")
    assert report.without_facts == []
    assert report.inferred_from_facts == 100
    assert sum(card.base_power for card in profile.cards if card.is_creature) > 20
    pod = XmagePod("g", 1, (deck.deck_id,) * 4, 0, 40)
    probabilities, abort_rate, turns = structural_win_probabilities(
        pod,
        {deck.deck_id: profile},
        seeds=range(1, 3),
        simulator_factory=StructuralSimulator,
    )
    assert sum(probabilities) == pytest.approx(1.0) or abort_rate > 0
    assert turns > 0
