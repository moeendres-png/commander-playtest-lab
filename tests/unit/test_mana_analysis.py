from __future__ import annotations

import math
from pathlib import Path

from commander_lab.mana_analysis import (
    CastabilityLibraryCard,
    CommanderCastCost,
    ManaAnalyzer,
    simulate_commander_cast_probability,
)
from commander_lab.models import (
    CardRole,
    Color,
    StructuralCardProfile,
    StructuralDeckProfile,
)
from commander_lab.mulligan import MulliganLab
from commander_lab.tools.current_candidates import load_candidate_profiles

ROOT = Path(__file__).resolve().parents[2]


def _candidate_by_name(name: str):
    for candidate in load_candidate_profiles(ROOT).values():
        if candidate.card.oracle_name == name:
            return candidate.card
    raise AssertionError(f"missing candidate fixture: {name}")


def test_tapped_land_classifier_distinguishes_definite_and_conditional() -> None:
    analyzer = ManaAnalyzer(ROOT)
    temple = analyzer.classify_source(_candidate_by_name("Temple of Epiphany"))
    fortress = analyzer.classify_source(_candidate_by_name("Glacial Fortress"))
    assert temple.definitely_enters_tapped is True
    assert temple.conditionally_enters_tapped is False
    assert fortress.definitely_enters_tapped is False
    assert fortress.conditionally_enters_tapped is True


def test_current_rogshai_mana_report_covers_colors_commanders_and_early_signals() -> None:
    lab = MulliganLab(ROOT)
    report = lab.analyze_deck_mana("rogshai/current")
    assert report.deck_hash == lab.deck("rogshai/current").deck_hash
    assert report.land_count == 36
    assert report.colored_sources["W"] > 0
    assert report.colored_sources["U"] > 0
    assert report.colored_sources["R"] > 0
    assert report.ishai_wu_source_counts["W"] > 0
    assert report.ishai_wu_source_counts["U"] > 0
    assert "Ishai, Ojutai Dragonspeaker" in report.commander_color_requirements
    assert set(report.turn_castability_support) == {1, 2, 3}
    assert all(
        0.0 <= float(row["source_supported_share"]) <= 1.0
        for row in report.turn_castability_support.values()
    )
    assert report.evidence_class == "derived_structural_mana_analysis"
    assert "not a rules-exact" in report.approximation_note


def test_opening_hand_reports_approximate_castability_ishai_and_hold_up() -> None:
    lab = MulliganLab(ROOT)
    deck = lab.deck("rogshai/current")
    by_name = {card.oracle_name: card for card in deck.cards}
    test_counter = StructuralCardProfile(
        oracle_name="Deterministic Test Counter",
        mana_value=2.0,
        roles=frozenset({CardRole.COUNTER}),
        color_requirements={Color.BLUE: 1},
        is_permanent=False,
    )
    hand = (
        by_name["Island"],
        by_name["Mountain"],
        by_name["Plains"],
        test_counter,
    )
    report = lab.mana_analyzer.analyze_opening_hand(deck, hand)
    assert report.ishai_wu_color_ready is True
    assert report.t2_interaction_hold_up_ready is True
    assert report.approximate_castable_card_count_by_turn[1] == 0
    assert report.approximate_castable_card_count_by_turn[2] >= 1
    assert "does not solve" in report.approximation_note


def test_mana_delta_is_deterministic_and_zero_for_same_deck() -> None:
    lab = MulliganLab(ROOT)
    deck = lab.deck("rogshai/current")
    delta = lab.mana_analyzer.compare_decks(deck, deck)
    assert delta.colored_source_delta == {}
    assert delta.flexible_source_delta == 0
    assert delta.definitely_tapped_land_delta == 0
    assert delta.conditionally_tapped_land_delta == 0
    assert delta.t1_untapped_source_delta == {}
    assert delta.ishai_wu_source_delta == {"W": 0, "U": 0}


def test_mulligan_features_use_oracle_tapped_source_classification() -> None:
    lab = MulliganLab(ROOT)
    deck = lab.deck("rogshai/current")
    by_name = {card.oracle_name: card for card in deck.cards}
    hand = (
        by_name["Island"],
        by_name["Mountain"],
        by_name["Plains"],
        _candidate_by_name("Temple of Epiphany"),
    )
    features = lab.features(deck, hand)
    assert features.colored_sources["W"] >= 1
    assert features.colored_sources["U"] >= 1
    assert features.colored_sources["R"] >= 1
    assert features.color_stability_score == 1.0
    assert features.tapped_source_count >= 1


def _castability_card(
    name: str,
    *,
    land: bool = False,
    colors: tuple[str, ...] = (),
    tapped: bool = False,
    mana_value: float = 3.0,
    accelerant: bool = False,
) -> CastabilityLibraryCard:
    return CastabilityLibraryCard(
        oracle_name=name,
        produces_colors=frozenset(colors),
        is_land=land,
        definitely_tapped=tapped,
        mana_value=mana_value,
        is_mana_accelerant=accelerant,
    )


def _synthetic_library(
    land_count: int,
    *,
    land_colors: tuple[str, ...] = ("W",),
    accelerant_count: int = 0,
) -> tuple[CastabilityLibraryCard, ...]:
    cards = [
        _castability_card(f"Test Land {index}", land=True, colors=land_colors)
        for index in range(land_count)
    ]
    cards.extend(
        _castability_card(f"Test Rock {index}", mana_value=2.0, accelerant=True, colors=("C",))
        for index in range(accelerant_count)
    )
    cards.extend(
        _castability_card(f"Test Filler {index}")
        for index in range(99 - land_count - accelerant_count)
    )
    return tuple(cards)


def _two_drop() -> tuple[CommanderCastCost, ...]:
    return (CommanderCastCost(name="Test Commander", mana_value=2.0, color_pips={}),)


def test_two_drop_commander_draw_probability_matches_hypergeometric() -> None:
    library = _synthetic_library(40)
    result = simulate_commander_cast_probability(library, _two_drop())
    observed = result.probability["Test Commander"]["draw"][2]

    def hypergeometric(k: int) -> float:
        return math.comb(40, k) * math.comb(59, 8 - k) / math.comb(99, 8)

    # Two lands must be in play by the turn-2 check: at least 2 lands among the 8
    # cards seen on turn 1, or exactly 1 with the turn-2 draw a land (39/91).
    exact = 1.0 - hypergeometric(0) - hypergeometric(1) * (52 / 91)
    assert abs(observed - exact) < 0.02


def test_adding_lands_raises_every_turn_probability() -> None:
    commanders = _two_drop()
    fewer = simulate_commander_cast_probability(_synthetic_library(20), commanders)
    more = simulate_commander_cast_probability(_synthetic_library(23), commanders)
    for mode in ("play", "draw"):
        for turn in range(2, 11):
            assert (
                more.probability["Test Commander"][mode][turn]
                > fewer.probability["Test Commander"][mode][turn]
            ), f"{mode} turn {turn}"
    # Removing the same 3 lands lowers every turn's probability again.
    for mode in ("play", "draw"):
        for turn in range(2, 11):
            assert (
                fewer.probability["Test Commander"][mode][turn]
                < more.probability["Test Commander"][mode][turn]
            ), f"{mode} turn {turn}"


def test_same_seed_gives_identical_castability_numbers() -> None:
    library = _synthetic_library(36, accelerant_count=4)
    commanders = (CommanderCastCost(name="Test Commander", mana_value=4.0, color_pips={"W": 1}),)
    first = simulate_commander_cast_probability(library, commanders)
    second = simulate_commander_cast_probability(library, commanders)
    assert first == second


def test_commander_needing_white_with_no_white_sources_stays_zero() -> None:
    library = _synthetic_library(40, land_colors=())
    commanders = (CommanderCastCost(name="Test Commander", mana_value=4.0, color_pips={"W": 2}),)
    result = simulate_commander_cast_probability(library, commanders)
    for mode in ("play", "draw"):
        assert all(
            probability == 0.0
            for probability in result.probability["Test Commander"][mode].values()
        )
        assert result.expected_turn["Test Commander"][mode] is None


def _synthetic_structural_profile(land_count: int) -> StructuralDeckProfile:
    lands = [
        StructuralCardProfile(
            oracle_name=f"Test Land {index}",
            mana_value=0.0,
            roles=frozenset({CardRole.MANA_SOURCE}),
            produces_colors=frozenset({Color.WHITE}),
            is_land=True,
        )
        for index in range(land_count)
    ]
    filler = [
        StructuralCardProfile(
            oracle_name=f"Test Filler {index}",
            mana_value=3.0,
            roles=frozenset(),
        )
        for index in range(99 - land_count)
    ]
    commander = StructuralCardProfile(
        oracle_name="Test Commander",
        mana_value=2.0,
        roles=frozenset(),
        is_permanent=False,
    )
    return StructuralDeckProfile(
        deck_id="test/synthetic",
        deck_hash="synthetic",
        commander_names=("Test Commander",),
        cards=tuple([*lands, *filler, commander]),
        commander_base_costs={"Test Commander": 2.0},
        data_snapshot_hash="test",
    )


def test_analyze_deck_reports_commander_cast_probability() -> None:
    analyzer = ManaAnalyzer(ROOT)
    report = analyzer.analyze_deck(_synthetic_structural_profile(40))
    probabilities = report.commander_cast_probability["Test Commander"]
    assert set(probabilities) == {"play", "draw"}
    for mode in ("play", "draw"):
        assert list(probabilities[mode]) == list(range(2, 11))
        turns = [probabilities[mode][turn] for turn in range(2, 11)]
        assert all(0.0 <= probability <= 1.0 for probability in turns)
        assert turns == sorted(turns)
        assert all(probability == round(probability, 3) for probability in turns)
    expected = report.expected_commander_turn["Test Commander"]
    assert expected["play"] is not None and 2.0 <= expected["play"] <= 10.0
    assert expected["draw"] is not None and 2.0 <= expected["draw"] <= 10.0
    assert report.evidence_class == "derived_structural_mana_analysis"
    assert "no mulligans" in report.approximation_note
