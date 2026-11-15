"""Counted-corpus signals of the strength index (#1364, Owner decisions E3.a and E2.a).

The corpus is the set of local deck lists bound to ONE commander (``universe_choice.local_spec``,
deduplicated by content fingerprint). Everything here is a count over those decks or a ratio of
counts (``DERIVED_DESCRIPTIVE``), always shown with numerator and denominator:

- ``corpus_tuned``: decks with the card over the decks of the brackets 4 and 5.
- ``corpus_log_lift``: the damped log ratio of the card's share in the whole corpus to its share
  in all EDHREC decks (``strength.log_lift_value``).
- ``corpus_bracket_slope``: the damped log ratio of the share in the brackets 4 and 5 to the
  share in bracket 2 (``strength.bracket_slope_value``).
- ``tournament``: the EDHTop16 play rate (the commander's published entries, the card count
  derived from the published rate) and the card's decks of the corpus bracket 5, pooled into one
  share: sum of the numerators over the sum of the denominators. A card without an EDHTop16 row
  counts with the corpus bracket 5 alone (EDHTop16 lists only the staples; not listed is
  unknown, never 0). The pooled share has a denominator below 500 and is then shrunk like every
  small-denominator share (``strength.beta_binomial_prior``).

A card whose name is ambiguous (a withheld front face) has no count: unknown, not 0. Counting
needs a corpus of at least ``min_universe`` decks; below it nothing here exists and the EDHREC
weights apply (``strength.apply_corpus_rule``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TypedDict, cast

from . import strength, universe_choice, universe_view
from .store import StudioStore
from .strength import Observation
from .universe import UniverseSpec

TUNED_COHORTS = ("bracket:4", "bracket:5")
LOW_COHORTS = ("bracket:2",)
TOURNAMENT_COHORTS = ("bracket:5",)
KEY_TUNED = "tuned"
KEY_LOW = "low"
KEY_TOURNAMENT = "tournament"
COHORT_GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (KEY_TUNED, "Brackets 4 und 5", TUNED_COHORTS),
    (KEY_LOW, "Bracket 2", LOW_COHORTS),
    (KEY_TOURNAMENT, "Bracket 5", TOURNAMENT_COHORTS),
)
# Pages of an EDHREC commander that are a bracket or a price variant, not a theme: the bracket
# signal already carries them.
VARIANT_PAGES = frozenset({"core", "upgraded", "optimized", "cedh", "budget", "exhibition"})


class CohortInfo(TypedDict):
    key: str
    label: str
    cohorts: list[str]
    denominator: int


class CorpusInfo(TypedDict):
    """What the result says about the corpus (counts and names only)."""

    available: bool
    decks: int
    min_universe: int
    snapshot_id: str
    cohorts: list[CohortInfo]


@dataclass(frozen=True)
class CohortCount:
    key: str
    label: str
    cohorts: tuple[str, ...]
    denominator: int
    hits: Mapping[str, int]


@dataclass(frozen=True)
class CorpusCounts:
    decks: int
    snapshot_id: str
    full: Mapping[str, int]
    groups: Mapping[str, CohortCount]

    def info(self, minimum: int) -> CorpusInfo:
        return {
            "available": True,
            "decks": self.decks,
            "min_universe": minimum,
            "snapshot_id": self.snapshot_id,
            "cohorts": [
                {
                    "key": group.key,
                    "label": group.label,
                    "cohorts": list(group.cohorts),
                    "denominator": group.denominator,
                }
                for group in self.groups.values()
            ],
        }


def no_corpus(decks: int, minimum: int) -> CorpusInfo:
    return {
        "available": False,
        "decks": decks,
        "min_universe": minimum,
        "snapshot_id": "",
        "cohorts": [],
    }


def _hits(cards: Sequence[universe_view.CardSpread]) -> dict[str, int]:
    """Decks per card id. A card no deck names is a counted zero, except when its name is
    ambiguous (a withheld front face): that card has no entry (unknown)."""
    found: dict[str, int] = {}
    for item in cards:
        if item["filter_card"]:
            continue
        if item["hits"] is not None:
            found[item["card_id"]] = int(item["hits"])
        elif not item.get("ambiguous_front_face"):
            found[item["card_id"]] = 0
    return found


def count_corpus(
    store: StudioStore, commander: str, card_ids: Sequence[str], minimum: int
) -> CorpusCounts | None:
    """The counted corpus of ``commander`` over the given cards, ``None`` below ``minimum``
    decks (or without any deck)."""
    base = universe_choice.local_spec(store, commander)
    total, snapshot, cards = universe_view.spread_for_spec(
        store, base, card_ids, commander_names=[commander]
    )
    if total <= 0 or total < minimum:
        return None
    groups: dict[str, CohortCount] = {}
    for key, label, cohorts in COHORT_GROUPS:
        spec = cast(UniverseSpec, {**base, "cohorts": list(cohorts)})
        denominator, _snapshot, group_cards = universe_view.spread_for_spec(
            store, spec, card_ids, commander_names=[commander]
        )
        groups[key] = CohortCount(key, label, cohorts, denominator, _hits(group_cards))
    return CorpusCounts(total, snapshot, _hits(cards), groups)


def _percent(share: float) -> str:
    return f"{share * 100:.1f}".replace(".", ",") + " %"


def global_share(observation: Observation | None) -> float | None:
    """The share of a card in all decks (EDHREC "Aufnahme überhaupt"): the counts when they
    are published, else the stored rate."""
    if observation is None:
        return None
    if observation.numerator is not None and observation.denominator:
        return observation.numerator / observation.denominator
    return observation.value


def corpus_observations(
    counts: CorpusCounts, global_inclusion: Mapping[str, Observation]
) -> dict[str, dict[str, Observation]]:
    """Per component (``corpus_tuned``, ``corpus_log_lift``, ``corpus_bracket_slope``) the
    observations of the cards it has a value for. A card without a value (no hit for the lift,
    fewer than five hits for the slope, an unknown count) is absent: missing, never 0."""
    tuned_group = counts.groups[KEY_TUNED]
    low_group = counts.groups[KEY_LOW]
    result: dict[str, dict[str, Observation]] = {
        strength.CORPUS_TUNED: {},
        strength.CORPUS_LOG_LIFT: {},
        strength.CORPUS_BRACKET_SLOPE: {},
    }
    if tuned_group.denominator > 0:
        for card_id, hits in tuned_group.hits.items():
            result[strength.CORPUS_TUNED][card_id] = Observation(
                hits / tuned_group.denominator, hits, tuned_group.denominator
            )
    for card_id, hits in counts.full.items():
        share = global_share(global_inclusion.get(card_id))
        lift = strength.log_lift_value(hits, counts.decks, share)
        if lift is not None and share is not None:
            factor = f"{(hits / counts.decks) / share:.1f}".replace(".", ",")
            result[strength.CORPUS_LOG_LIFT][card_id] = Observation(
                lift,
                hits,
                counts.decks,
                note=(
                    f"Korpus {_percent(hits / counts.decks)} ({hits} von {counts.decks} Decks) "
                    f"gegen alle Decks {_percent(share)}: Lift {factor}"
                ),
            )
    if tuned_group.denominator > 0 and low_group.denominator > 0:
        for card_id, high_hits in tuned_group.hits.items():
            low_hits = low_group.hits.get(card_id)
            if low_hits is None:
                continue
            slope = strength.bracket_slope_value(
                high_hits, tuned_group.denominator, low_hits, low_group.denominator
            )
            if slope is not None:
                result[strength.CORPUS_BRACKET_SLOPE][card_id] = Observation(
                    slope,
                    high_hits,
                    tuned_group.denominator,
                    note=(
                        f"Bracket 4+5: {high_hits} von {tuned_group.denominator} "
                        f"({_percent(high_hits / tuned_group.denominator)}), Bracket 2: "
                        f"{low_hits} von {low_group.denominator} "
                        f"({_percent(low_hits / low_group.denominator)})"
                    ),
                )
    return result


def tournament_observations(
    counts: CorpusCounts | None, edhtop16: Mapping[str, Observation]
) -> dict[str, Observation]:
    """The pooled tournament share per card: EDHTop16 (numerator and denominator, the numerator
    derived from the published rate when only the rate is stored) plus the corpus bracket 5.
    Parts without a count are left out; a card with no part has no observation."""
    group = counts.groups[KEY_TOURNAMENT] if counts is not None else None
    result: dict[str, Observation] = {}
    card_ids = set(edhtop16)
    if group is not None:
        card_ids |= set(group.hits)
    for card_id in sorted(card_ids):
        parts: list[tuple[str, int, int]] = []
        top16 = edhtop16.get(card_id)
        if top16 is not None and top16.numerator is not None and top16.denominator:
            parts.append(("EDHTop16", top16.numerator, top16.denominator))
        if group is not None and group.denominator > 0 and card_id in group.hits:
            parts.append(("Korpus Bracket 5", group.hits[card_id], group.denominator))
        if not parts:
            continue
        numerator = sum(part[1] for part in parts)
        denominator = sum(part[2] for part in parts)
        result[card_id] = Observation(
            numerator / denominator,
            numerator,
            denominator,
            note=(
                " + ".join(f"{name} {num} von {den}" for name, num, den in parts)
                + f" (zusammengelegt: {numerator} von {denominator})"
            ),
        )
    return result
