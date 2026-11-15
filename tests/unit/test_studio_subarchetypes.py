"""Tag rules and signal math of the sub-archetype analysis (issue #1368).

All decks are synthetic: small card sets with hand-set roles, mana values and flags, so
every expected tag and share is computed by hand in the test. No store, no corpus.
"""

from __future__ import annotations

import math

from commander_lab.studio import subarchetypes as sa


def _card(
    oracle_id: str,
    *,
    roles: tuple[str, ...] = (),
    mana_value: float | None = 3.0,
    is_land: bool = False,
    is_artifact: bool = False,
    makes_clue: bool = False,
    extra_land: bool = False,
) -> sa.CardInfo:
    return sa.CardInfo(
        oracle_id=oracle_id,
        name=oracle_id,
        roles=frozenset(roles),
        mana_value=mana_value,
        is_land=is_land,
        is_artifact=is_artifact,
        makes_clue=makes_clue,
        extra_land=extra_land,
    )


def _deck(deck_id: str, oracle_ids: tuple[str, ...], bracket: int | None = None) -> sa.DeckInput:
    return sa.DeckInput(
        deck_id=deck_id,
        bracket=bracket,
        oracle_ids=frozenset(oracle_ids),
        names=frozenset(name.casefold() for name in oracle_ids),
    )


def _cards(*cards: sa.CardInfo) -> dict[str, sa.CardInfo]:
    return {card.oracle_id: card for card in cards}


THRESHOLDS = sa.TagThresholds(
    landfall_min_share=0.25,
    blink_bounce_min_share=0.25,
    big_mana_min_share=0.25,
    big_mana_min_value=6.0,
    clue_artifact_min_share=0.25,
)


def test_landfall_tag_counts_landfall_and_extra_land_cards() -> None:
    cards = _cards(
        _card("a", roles=("landfall",)),
        _card("b", extra_land=True),
        _card("c"),
        _card("d"),
        _card("land", is_land=True, mana_value=None),
    )
    tags = sa.tag_deck(_deck("d1", ("a", "b", "c", "d", "land")), cards, (), THRESHOLDS)
    # 2 of 4 distinct nonland cards carry the theme; the land is no denominator card.
    assert tags.shares["landfall"] == 0.5
    assert tags.tags["landfall"] is True


def test_landfall_tag_stays_off_below_the_threshold() -> None:
    cards = _cards(_card("a", roles=("landfall",)), _card("b"), _card("c"), _card("d"))
    tags = sa.tag_deck(_deck("d1", ("a", "b", "c", "d")), cards, (), THRESHOLDS)
    assert tags.shares["landfall"] == 0.25  # exactly at the threshold counts
    assert tags.tags["landfall"] is True
    cards_below = _cards(
        _card("a", roles=("landfall",)), _card("b"), _card("c"), _card("d"), _card("e")
    )
    tags_below = sa.tag_deck(_deck("d2", ("a", "b", "c", "d", "e")), cards_below, (), THRESHOLDS)
    assert tags_below.shares["landfall"] == 0.2
    assert tags_below.tags["landfall"] is False


def test_blink_bounce_tag_merges_flicker_and_bounce_roles() -> None:
    cards = _cards(
        _card("a", roles=("flicker",)),
        _card("b", roles=("bounce",)),
        _card("c"),
        _card("d"),
        _card("e"),
        _card("f"),
        _card("g"),
        _card("h"),
    )
    tags = sa.tag_deck(_deck("d1", ("a", "b", "c", "d", "e", "f", "g", "h")), cards, (), THRESHOLDS)
    assert tags.shares["blink_bounce"] == 0.25
    assert tags.tags["blink_bounce"] is True


def test_big_mana_tag_uses_the_mana_value_share_of_nonland_cards() -> None:
    cards = _cards(
        _card("a", mana_value=7.0),
        _card("b", mana_value=6.0),
        _card("c", mana_value=2.0),
        _card("d", mana_value=1.0),
        _card("bigland", is_land=True, mana_value=None),
    )
    tags = sa.tag_deck(_deck("d1", ("a", "b", "c", "d", "bigland")), cards, (), THRESHOLDS)
    assert tags.shares["big_mana"] == 0.5
    assert tags.tags["big_mana"] is True


def test_big_mana_ignores_cards_without_a_mana_value() -> None:
    cards = _cards(
        _card("a", mana_value=None),
        _card("b", mana_value=7.0),
        _card("c", mana_value=2.0),
        _card("d", mana_value=2.0),
    )
    tags = sa.tag_deck(_deck("d1", ("a", "b", "c", "d")), cards, (), THRESHOLDS)
    # The card without a mana value is a denominator card but never a big-mana card.
    assert tags.shares["big_mana"] == 0.25
    assert tags.tags["big_mana"] is True


def test_clue_artifact_tag_counts_artifacts_and_clue_makers() -> None:
    cards = _cards(
        _card("a", is_artifact=True),
        _card("b", makes_clue=True),
        _card("c"),
        _card("d"),
        _card("e"),
        _card("f"),
        _card("g"),
        _card("h"),
    )
    tags = sa.tag_deck(_deck("d1", ("a", "b", "c", "d", "e", "f", "g", "h")), cards, (), THRESHOLDS)
    assert tags.shares["clue_artifact"] == 0.25
    assert tags.tags["clue_artifact"] is True


def test_cedh_combo_tag_needs_a_complete_two_card_combo() -> None:
    cards = _cards(_card("Alpha"), _card("Beta"), _card("Gamma"), _card("Delta"))
    combos = (frozenset({"alpha", "beta"}), frozenset({"alpha", "gamma", "delta"}))
    complete = sa.tag_deck(_deck("d1", ("Alpha", "Beta", "Gamma")), cards, combos, THRESHOLDS)
    assert complete.tags["cedh_combo"] is True
    incomplete = sa.tag_deck(_deck("d2", ("Alpha", "Gamma")), cards, combos, THRESHOLDS)
    assert incomplete.tags["cedh_combo"] is False
    # The three-card combo alone never tags: only two-card combos count.
    three_only = sa.tag_deck(_deck("d3", ("Alpha", "Gamma", "Delta")), cards, combos, THRESHOLDS)
    assert three_only.tags["cedh_combo"] is False
    assert three_only.complete_two_card == 0


def test_cedh_combo_matching_uses_front_faces() -> None:
    cards = _cards(_card("Front // Back"), _card("Partner"))
    deck = sa.DeckInput(
        deck_id="d1",
        bracket=None,
        oracle_ids=frozenset({"Front // Back", "Partner"}),
        names=frozenset({"front // back", "front", "partner"}),
    )
    combos = (frozenset({"front", "partner"}),)
    tags = sa.tag_deck(deck, cards, combos, THRESHOLDS)
    assert tags.tags["cedh_combo"] is True
    assert tags.complete_two_card == 1


def test_one_deck_can_carry_several_tags() -> None:
    cards = _cards(
        _card("a", roles=("landfall", "flicker"), mana_value=7.0),
        _card("b", roles=("bounce",), mana_value=6.0),
        _card("c", extra_land=True),
        _card("d"),
    )
    tags = sa.tag_deck(_deck("d1", ("a", "b", "c", "d")), cards, (), THRESHOLDS)
    assert tags.tags["landfall"] is True
    assert tags.tags["blink_bounce"] is True
    assert tags.tags["big_mana"] is True


def test_a_deck_without_nonland_cards_gets_no_share_tag() -> None:
    cards = _cards(_card("land", is_land=True, mana_value=None))
    tags = sa.tag_deck(_deck("d1", ("land",)), cards, (), THRESHOLDS)
    assert tags.shares["landfall"] is None
    assert tags.tags["landfall"] is False
    assert tags.tags["big_mana"] is False


def test_a_card_missing_from_the_card_table_counts_as_plain_nonland() -> None:
    cards = _cards(_card("a", roles=("landfall",)))
    tags = sa.tag_deck(_deck("d1", ("a", "unknown")), cards, (), THRESHOLDS)
    # The unknown card is a denominator card without roles (unknown, never a theme card).
    assert tags.shares["landfall"] == 0.5


def test_inclusion_shares_count_decks_not_copies() -> None:
    decks = (
        _deck("d1", ("a", "b")),
        _deck("d2", ("a",)),
        _deck("d3", ("b", "c")),
        _deck("d4", ()),
    )
    shares = sa.inclusion_shares(decks)
    assert shares == {"a": 0.5, "b": 0.5, "c": 0.25}


def test_inclusion_shares_of_no_decks_is_empty() -> None:
    assert sa.inclusion_shares(()) == {}


def test_log_lift_is_the_log_of_corpus_over_global() -> None:
    assert sa.log_lift(0.5, 0.25) == math.log(2.0)
    assert sa.log_lift(0.25, 0.5) == math.log(0.5)


def test_log_lift_is_unknown_without_a_positive_pair() -> None:
    assert sa.log_lift(0.0, 0.25) is None
    assert sa.log_lift(0.5, 0.0) is None
    assert sa.log_lift(0.5, None) is None
    assert sa.log_lift(None, 0.5) is None


def test_bracket_split_shares_and_slope() -> None:
    decks = (
        _deck("t1", ("a", "b"), bracket=4),
        _deck("t2", ("a",), bracket=5),
        _deck("l1", ("b",), bracket=2),
        _deck("l2", ("b", "c"), bracket=2),
        _deck("x1", ("a", "c"), bracket=None),
    )
    tuned = sa.inclusion_shares([deck for deck in decks if deck.bracket in (4, 5)])
    low = sa.inclusion_shares([deck for deck in decks if deck.bracket == 2])
    assert tuned == {"a": 1.0, "b": 0.5}
    assert low == {"b": 1.0, "c": 0.5}
    assert sa.bracket_slope(tuned, low, "a") == 1.0
    assert sa.bracket_slope(tuned, low, "b") == -0.5
    assert sa.bracket_slope(tuned, low, "c") == -0.5
    assert sa.bracket_slope(tuned, low, "missing") == 0.0


def test_spearman_of_identical_and_reversed_vectors() -> None:
    left = {"a": 1.0, "b": 2.0, "c": 3.0, "d": 4.0}
    assert sa.spearman(left, dict(left)) == 1.0
    reversed_right = {"a": 4.0, "b": 3.0, "c": 2.0, "d": 1.0}
    assert sa.spearman(left, reversed_right) == -1.0


def test_spearman_averages_tied_ranks() -> None:
    left = {"a": 1.0, "b": 1.0, "c": 3.0}
    right = {"a": 1.0, "b": 2.0, "c": 3.0}
    value = sa.spearman(left, right)
    assert value is not None
    assert abs(value - 0.8660254037844386) < 1e-12


def test_spearman_uses_only_cards_defined_on_both_sides() -> None:
    left = {"a": 1.0, "b": 2.0, "c": 3.0, "d": None}
    right = {"a": 1.0, "b": 2.0, "c": 3.0}
    assert sa.spearman(left, right) == 1.0


def test_spearman_is_unknown_for_a_constant_vector() -> None:
    left = {"a": 1.0, "b": 1.0, "c": 1.0}
    right = {"a": 1.0, "b": 2.0, "c": 3.0}
    assert sa.spearman(left, right) is None
    assert sa.spearman({"a": 1.0}, {"a": 1.0}) is None


def test_blink_bounce_tag_stays_off_below_the_threshold() -> None:
    cards = _cards(_card("a", roles=("bounce",)), _card("b"), _card("c"), _card("d"), _card("e"))
    tags = sa.tag_deck(_deck("d1", ("a", "b", "c", "d", "e")), cards, (), THRESHOLDS)
    assert tags.shares["blink_bounce"] == 0.2
    assert tags.tags["blink_bounce"] is False


def test_big_mana_tag_stays_off_below_the_threshold() -> None:
    cards = _cards(_card("a", mana_value=7.0), _card("b"), _card("c"), _card("d"), _card("e"))
    tags = sa.tag_deck(_deck("d1", ("a", "b", "c", "d", "e")), cards, (), THRESHOLDS)
    assert tags.shares["big_mana"] == 0.2
    assert tags.tags["big_mana"] is False


def test_clue_artifact_tag_stays_off_below_the_threshold() -> None:
    cards = _cards(_card("a", is_artifact=True), _card("b"), _card("c"), _card("d"), _card("e"))
    tags = sa.tag_deck(_deck("d1", ("a", "b", "c", "d", "e")), cards, (), THRESHOLDS)
    assert tags.shares["clue_artifact"] == 0.2
    assert tags.tags["clue_artifact"] is False


def test_cedh_combo_can_complete_through_the_commander_section() -> None:
    cards = _cards(_card("Partner"))
    combos = (frozenset({"the commander", "partner"}),)
    deck = sa.DeckInput(
        deck_id="d1",
        bracket=None,
        oracle_ids=frozenset({"Partner"}),
        names=frozenset({"partner"}),
        combo_names=frozenset({"the commander"}),
    )
    tags = sa.tag_deck(deck, cards, combos, THRESHOLDS)
    assert tags.tags["cedh_combo"] is True
    assert tags.complete_two_card == 1
    # The same deck seen on its composition names alone cannot complete a combo
    # that names the commander: the commander section is not part of the composition.
    composition_only = sa.DeckInput(
        deck_id="d2",
        bracket=None,
        oracle_ids=frozenset({"Partner"}),
        names=frozenset({"partner"}),
    )
    tags_without = sa.tag_deck(composition_only, cards, combos, THRESHOLDS)
    assert tags_without.tags["cedh_combo"] is False
    assert tags_without.complete_two_card == 0


def test_creates_clue_reads_investigate_and_clue_creation() -> None:
    assert sa.creates_clue("Whenever a land you control enters, investigate.") is True
    assert sa.creates_clue("Create a Clue token.") is True
    assert sa.creates_clue("Create two Clue tokens.") is True
    # Merely mentioning or sacrificing a Clue creates none.
    assert sa.creates_clue("Sacrifice a Clue: Draw a card.") is False
    assert sa.creates_clue("Clues you control are artifacts in addition to their types.") is False
    assert sa.creates_clue("Draw a card.") is False


def test_plays_extra_land_reads_the_play_wordings() -> None:
    assert sa.plays_extra_land("You may play an additional land on each of your turns.") is True
    assert sa.plays_extra_land("You may play two additional lands on each of your turns.") is True
    # The "up to N" wording class (Summer Bloom) counts as well.
    assert sa.plays_extra_land("You may play up to three additional lands this turn.") is True
    assert sa.plays_extra_land("You may play up to two additional lands this turn.") is True
    # Putting a land card onto the battlefield is not playing an additional land.
    assert (
        sa.plays_extra_land("You may put a land card from your hand onto the battlefield.") is False
    )
    assert sa.plays_extra_land("You may play lands from the top of your library.") is False
    assert sa.plays_extra_land("Draw a card.") is False


def test_signal_vectors_tuned_does_not_need_a_bracket_two_cohort() -> None:
    decks = (
        _deck("t1", ("a", "b"), bracket=4),
        _deck("t2", ("a",), bracket=5),
    )
    vectors = sa.signal_vectors(decks, ["a", "b"], {"a": 0.5, "b": 0.25})
    assert vectors["deck_universe"] == {"a": 1.0, "b": 0.5}
    assert vectors["corpus_tuned"] == {"a": 1.0, "b": 0.5}
    assert vectors["corpus_bracket_slope"] == {"a": None, "b": None}


def test_signal_vectors_without_tuned_decks_has_no_bracket_signals() -> None:
    decks = (_deck("l1", ("a",), bracket=2), _deck("x1", ("b",), bracket=None))
    vectors = sa.signal_vectors(decks, ["a", "b"], {"a": 0.5, "b": 0.25})
    assert vectors["corpus_tuned"] == {"a": None, "b": None}
    assert vectors["corpus_bracket_slope"] == {"a": None, "b": None}


def test_signal_vectors_with_both_cohorts_computes_the_slope() -> None:
    decks = (
        _deck("t1", ("a", "b"), bracket=4),
        _deck("l1", ("b",), bracket=2),
    )
    vectors = sa.signal_vectors(decks, ["a", "b"], {"a": 0.5, "b": 0.25})
    assert vectors["corpus_tuned"] == {"a": 1.0, "b": 1.0}
    assert vectors["corpus_bracket_slope"] == {"a": 1.0, "b": 0.0}
