"""Sub-archetype tagging of corpus decks and the corpus signals per archetype (issue #1368).

Analysis only: nothing here feeds the strength index. Decks are tagged rule-based from
their composition — the roles of their cards (``card_role``, see ``roles.py``), mana
values and two deterministic Oracle-text flags — never from a rating. A deck may carry
several tags. Every tag rule is a share over the deck's distinct nonland cards with a
threshold the caller sets; the measured share is always reported next to the tag, so a
threshold is an auditable line, not a hidden verdict. A card the card table does not know
counts as a plain nonland denominator card: unknown is never a theme card.

The corpus signals are recomputed from the deck sets themselves (the definitions the
tier-list plan of issue #1364 names, computed here because that package is not merged
yet): ``deck_universe`` is a card's inclusion share in a deck set, ``corpus_log_lift``
the natural log of that share over the stored ``edhrec_global_inclusion`` share,
``corpus_tuned`` the inclusion share in the bracket 4+5 decks of a set and
``corpus_bracket_slope`` the tuned share minus the bracket-2 share. A share of a deck
set a card never appears in is a counted 0; a log lift without a positive pair is
unknown (``None``), never a number.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

TAG_LANDFALL = "landfall"
TAG_BLINK_BOUNCE = "blink_bounce"
TAG_BIG_MANA = "big_mana"
TAG_CLUE_ARTIFACT = "clue_artifact"
TAG_CEDH_COMBO = "cedh_combo"
SHARE_TAGS = (TAG_LANDFALL, TAG_BLINK_BOUNCE, TAG_BIG_MANA, TAG_CLUE_ARTIFACT)
ALL_TAGS = (*SHARE_TAGS, TAG_CEDH_COMBO)

SIGNAL_DECK_UNIVERSE = "deck_universe"
SIGNAL_LOG_LIFT = "corpus_log_lift"
SIGNAL_TUNED = "corpus_tuned"
SIGNAL_BRACKET_SLOPE = "corpus_bracket_slope"
SIGNALS = (SIGNAL_DECK_UNIVERSE, SIGNAL_LOG_LIFT, SIGNAL_TUNED, SIGNAL_BRACKET_SLOPE)


@dataclass(frozen=True)
class CardInfo:
    """What the tag rules read of one card: its stored roles, mana value, land and
    artifact flags and two Oracle-text flags (``makes_clue``: the text creates Clue
    tokens; ``extra_land``: the text lets its controller play an additional land)."""

    oracle_id: str
    name: str
    roles: frozenset[str]
    mana_value: float | None
    is_land: bool
    is_artifact: bool
    makes_clue: bool
    extra_land: bool


_CLUE_TEXT = re.compile(r"investigate\b|create[^.\n]*\bclue\b", re.IGNORECASE)
_EXTRA_LAND_TEXT = re.compile(
    r"play (?:up to )?(?:an|one|two|three|four|five|six|seven|eight|nine|ten|\d+)"
    r" additional lands?\b",
    re.IGNORECASE,
)


def creates_clue(oracle_text: str) -> bool:
    """Whether an Oracle text creates Clue tokens: it says ``investigate`` or creates
    a Clue. A text that only mentions Clues (sacrificing or counting them) does not."""
    return bool(_CLUE_TEXT.search(oracle_text))


def plays_extra_land(oracle_text: str) -> bool:
    """Whether an Oracle text lets its controller play an additional land (``play an
    additional land``, ``play two additional lands``, ``play up to three additional
    lands``). Putting a land card onto the battlefield is not playing it and does
    not count."""
    return bool(_EXTRA_LAND_TEXT.search(oracle_text))


@dataclass(frozen=True)
class DeckInput:
    """One deck of the analysed set: its distinct composition cards by oracle id
    (the sections the analysis composes shares over), the name keys those cards
    answer to (full names and front faces, casefolded, the ``combos.py`` discipline),
    its bracket (``None`` when no bracket cohort names one) and ``combo_names``:
    the name keys over all counted sections including the commander and companion
    sections, used only for combo completeness — the basis ``combos.deck_combos``
    checks a deck on, where a combo that names the commander can complete."""

    deck_id: str
    bracket: int | None
    oracle_ids: frozenset[str]
    names: frozenset[str]
    combo_names: frozenset[str] = field(default=frozenset())


@dataclass(frozen=True)
class TagThresholds:
    """The disclosed lines of the tag rules: a share tag holds at or above its share."""

    landfall_min_share: float
    blink_bounce_min_share: float
    big_mana_min_share: float
    big_mana_min_value: float
    clue_artifact_min_share: float


@dataclass(frozen=True)
class DeckTags:
    """The tags of one deck with the measured share behind every share tag (``None``
    when the deck has no nonland card to share over) and the number of complete
    two-card combos it holds."""

    tags: dict[str, bool]
    shares: dict[str, float | None]
    complete_two_card: int


def _is_theme(card: CardInfo | None, tag: str, thresholds: TagThresholds) -> bool:
    if card is None:
        return False
    if tag == TAG_LANDFALL:
        return "landfall" in card.roles or card.extra_land
    if tag == TAG_BLINK_BOUNCE:
        return "flicker" in card.roles or "bounce" in card.roles
    if tag == TAG_BIG_MANA:
        return card.mana_value is not None and card.mana_value >= thresholds.big_mana_min_value
    if tag == TAG_CLUE_ARTIFACT:
        return card.is_artifact or card.makes_clue
    raise ValueError(f"unknown share tag: {tag}")


def tag_deck(
    deck: DeckInput,
    cards: Mapping[str, CardInfo],
    combos: Sequence[frozenset[str]],
    thresholds: TagThresholds,
) -> DeckTags:
    """Tag one deck. ``combos`` are casefolded name sets of listed combos; only the
    two-card ones can tag (a complete three-card combo never does). A combo is
    complete when all its names are among the deck's composition names plus its
    ``combo_names`` (all counted sections, the ``combos.deck_combos`` basis), so a
    combo naming the commander can complete."""
    nonland = [
        oracle_id
        for oracle_id in deck.oracle_ids
        if not (cards.get(oracle_id) is not None and cards[oracle_id].is_land)
    ]
    shares: dict[str, float | None] = {}
    tags: dict[str, bool] = {}
    minimum = {
        TAG_LANDFALL: thresholds.landfall_min_share,
        TAG_BLINK_BOUNCE: thresholds.blink_bounce_min_share,
        TAG_BIG_MANA: thresholds.big_mana_min_share,
        TAG_CLUE_ARTIFACT: thresholds.clue_artifact_min_share,
    }
    for tag in SHARE_TAGS:
        if not nonland:
            shares[tag] = None
            tags[tag] = False
            continue
        hits = sum(1 for oracle_id in nonland if _is_theme(cards.get(oracle_id), tag, thresholds))
        share = hits / len(nonland)
        shares[tag] = share
        tags[tag] = share >= minimum[tag]
    answer_names = deck.names | deck.combo_names
    complete = sum(1 for combo in combos if len(combo) == 2 and combo <= answer_names)
    tags[TAG_CEDH_COMBO] = complete > 0
    return DeckTags(tags=tags, shares=shares, complete_two_card=complete)


def inclusion_shares(decks: Iterable[DeckInput]) -> dict[str, float]:
    """Per oracle id, the share of ``decks`` that list the card. An empty deck set
    gives an empty dict (unknown), never zeros."""
    deck_list = list(decks)
    if not deck_list:
        return {}
    counts: dict[str, int] = {}
    for deck in deck_list:
        for oracle_id in deck.oracle_ids:
            counts[oracle_id] = counts.get(oracle_id, 0) + 1
    return {oracle_id: count / len(deck_list) for oracle_id, count in counts.items()}


def log_lift(corpus_share: float | None, global_share: float | None) -> float | None:
    """``ln(corpus / global)``; ``None`` unless both shares are present and positive."""
    if corpus_share is None or global_share is None:
        return None
    if corpus_share <= 0.0 or global_share <= 0.0:
        return None
    return math.log(corpus_share / global_share)


def bracket_slope(tuned: Mapping[str, float], low: Mapping[str, float], oracle_id: str) -> float:
    """Tuned share minus bracket-2 share of one card; a card absent from a side counts
    as the counted 0 of that side."""
    return tuned.get(oracle_id, 0.0) - low.get(oracle_id, 0.0)


def signal_vectors(
    decks: Iterable[DeckInput],
    pool: Sequence[str],
    global_inclusion: Mapping[str, float | None],
) -> dict[str, dict[str, float | None]]:
    """The four corpus signals of one deck set, per pool card (oracle id).

    The two bracket signals are decoupled: ``corpus_tuned`` needs only the set's
    bracket-4+5 decks, ``corpus_bracket_slope`` needs bracket 2 as well. A set
    without bracket-2 decks still gets its tuned shares (the slope stays unknown,
    ``None``); a set without tuned decks gets neither. ``global_inclusion`` must
    cover every pool card (a missing card is a KeyError, never a silent 0)."""
    deck_list = list(decks)
    shares = inclusion_shares(deck_list)
    tuned_decks = [deck for deck in deck_list if deck.bracket in (4, 5)]
    low_decks = [deck for deck in deck_list if deck.bracket == 2]
    tuned = inclusion_shares(tuned_decks)
    low = inclusion_shares(low_decks)
    vectors: dict[str, dict[str, float | None]] = {signal: {} for signal in SIGNALS}
    for oracle_id in pool:
        share = shares.get(oracle_id, 0.0)
        vectors[SIGNAL_DECK_UNIVERSE][oracle_id] = share
        vectors[SIGNAL_LOG_LIFT][oracle_id] = log_lift(share, global_inclusion[oracle_id])
        vectors[SIGNAL_TUNED][oracle_id] = tuned.get(oracle_id, 0.0) if tuned_decks else None
        vectors[SIGNAL_BRACKET_SLOPE][oracle_id] = (
            bracket_slope(tuned, low, oracle_id) if tuned_decks and low_decks else None
        )
    return vectors


def _ranks(values: Sequence[float]) -> list[float]:
    """Ranks (1-based) with ties averaged, in input order."""
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start
        while end + 1 < len(order) and values[order[end + 1]] == values[order[start]]:
            end += 1
        average = (start + end) / 2.0 + 1.0
        for position in range(start, end + 1):
            ranks[order[position]] = average
        start = end + 1
    return ranks


def spearman(left: Mapping[str, float | None], right: Mapping[str, float | None]) -> float | None:
    """Spearman rank correlation over the cards both sides define (a ``None`` value is
    undefined and drops the card). ``None`` with fewer than three shared cards or when
    either side is constant (no ranking to correlate)."""
    keys = [key for key in left if left[key] is not None and right.get(key) is not None]
    if len(keys) < 3:
        return None
    left_ranks = _ranks([float(left[key]) for key in keys])  # type: ignore[arg-type]
    right_ranks = _ranks([float(right[key]) for key in keys])  # type: ignore[arg-type]
    n = len(keys)
    mean_left = sum(left_ranks) / n
    mean_right = sum(right_ranks) / n
    covariance = sum(
        (a - mean_left) * (b - mean_right) for a, b in zip(left_ranks, right_ranks, strict=True)
    )
    var_left = sum((a - mean_left) ** 2 for a in left_ranks)
    var_right = sum((b - mean_right) ** 2 for b in right_ranks)
    if var_left == 0.0 or var_right == 0.0:
        return None
    return covariance / math.sqrt(var_left * var_right)


__all__ = [
    "ALL_TAGS",
    "SHARE_TAGS",
    "SIGNALS",
    "SIGNAL_BRACKET_SLOPE",
    "SIGNAL_DECK_UNIVERSE",
    "SIGNAL_LOG_LIFT",
    "SIGNAL_TUNED",
    "TAG_BIG_MANA",
    "TAG_BLINK_BOUNCE",
    "TAG_CEDH_COMBO",
    "TAG_CLUE_ARTIFACT",
    "TAG_LANDFALL",
    "CardInfo",
    "DeckInput",
    "DeckTags",
    "TagThresholds",
    "bracket_slope",
    "creates_clue",
    "inclusion_shares",
    "log_lift",
    "plays_extra_land",
    "signal_vectors",
    "spearman",
    "tag_deck",
]
