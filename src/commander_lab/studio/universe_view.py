"""The deck universe as the browser shows it: per-card counted spread and co-occurrence.

Everything here is a plain count over one stored universe profile (see ``universe.py``),
with its denominator and its origin (profile, snapshot). The spread level (S-D, or U) is
the tier function of ``tiers.py`` applied to the inclusion share. It measures how often a
card is played in the chosen decks, not how strong it is: it does not touch the evidence
model or its unrated policy, and favourites, excludes and notes are never read here.

Name mapping: universe counts are keyed by the raw ``card_name`` of the imported decks.
A Studio card may appear there as its oracle name, its engine name or the front face of a
double-faced name. Names are compared case-insensitively (``str.casefold``). When several
spellings occur, their hits are NOT summed (a deck may list a card under one spelling
only, but the spellings of one card can overlap across sources): the largest count is
reported and every spelling is listed with its own count. When no spelling occurs in the
universe, absence cannot be told from a spelling mismatch, so the card is reported as
unmatched: level ``U``, share ``None``, never a zero.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypedDict

from .store import StudioStore
from .tiers import TierParams, TierParamsDict, tier_for_share
from .universe import (
    CooccurrenceRow,
    InclusionResult,
    UniverseSpec,
    cooccurrence,
    get_profile,
    inclusion,
    snapshot_id,
)

NAME_NOT_FOUND = "NAME_NOT_FOUND_IN_UNIVERSE"
MEANING = (
    "Verbreitung (gezählt): in wie vielen Decks des gewählten Universums die Karte steht. "
    "Das ist keine Kartenstärke und kein Tier der Bewertung."
)


class ProfileSummary(TypedDict):
    profile: str
    spec: UniverseSpec
    denominator: int
    denominator_by_platform: dict[str, int]
    denominator_by_bracket: dict[str, int]
    snapshot_id: str
    data_class: str


class Spelling(TypedDict):
    name: str
    hits: int


class CardSpread(TypedDict):
    card_id: str
    name: str
    matched: bool
    matched_name: str | None
    hits: int | None
    denominator: int
    share: float | None
    level: str
    reason: str
    spellings: list[Spelling]


class SpreadUniverse(TypedDict):
    profile: str
    snapshot_id: str
    denominator: int
    denominator_by_platform: dict[str, int]
    denominator_by_bracket: dict[str, int]
    data_class: str


class PoolSpread(TypedDict):
    universe: SpreadUniverse
    params: TierParamsDict
    meaning: str
    cards: list[CardSpread]


class CardCooccurrence(TypedDict):
    card_id: str
    matched: bool
    matched_name: str | None
    profile: str
    snapshot_id: str
    denominator: int
    denominator_label: str
    decks_with_card: int | None
    decks_with_card_label: str
    denominator_by_platform: dict[str, int]
    denominator_by_bracket: dict[str, int]
    pairs: list[CooccurrenceRow]
    data_class: str


def profile_summary(store: StudioStore, name: str) -> ProfileSummary:
    """Spec, deck count, breakdowns and snapshot of a stored profile (KeyError if unknown)."""
    profile = get_profile(store, name)
    counted = inclusion(store, profile=name, card_names=[])
    return {
        "profile": name,
        "spec": profile["spec"],
        "denominator": counted["denominator"],
        "denominator_by_platform": counted["denominator_by_platform"],
        "denominator_by_bracket": counted["denominator_by_bracket"],
        "snapshot_id": snapshot_id(store, profile=name),
        "data_class": counted["data_class"],
    }


def _spellings(oracle_name: str, engine_name: str) -> list[str]:
    candidates = [
        oracle_name,
        engine_name,
        oracle_name.split(" // ")[0].strip(),
        engine_name.split(" // ")[0].strip(),
    ]
    seen: set[str] = set()
    result: list[str] = []
    for candidate in candidates:
        if candidate and candidate.casefold() not in seen:
            seen.add(candidate.casefold())
            result.append(candidate)
    return result


def _universe_counts(counted: InclusionResult) -> dict[str, tuple[str, int]]:
    """Casefolded name -> (raw name with the most hits, those hits)."""
    best: dict[str, tuple[str, int]] = {}
    for row in counted["rows"]:
        key = row["card_name"].casefold()
        if key not in best or row["hits"] > best[key][1]:
            best[key] = (row["card_name"], row["hits"])
    return best


def _card_rows(store: StudioStore, card_ids: Sequence[str] | None) -> list[tuple[str, str, str]]:
    sql = "SELECT card_id, oracle_name, engine_name FROM card_fact"
    if card_ids is None:
        rows = store.connection.execute(sql + " ORDER BY oracle_name, card_id").fetchall()
    else:
        rows = []
        for card_id in card_ids:
            row = store.connection.execute(sql + " WHERE card_id = ?", (card_id,)).fetchone()
            if row is None:
                raise KeyError(card_id)
            rows.append(row)
    return [(str(r["card_id"]), str(r["oracle_name"]), str(r["engine_name"])) for r in rows]


def _spread_of(
    card: tuple[str, str, str],
    counts: dict[str, tuple[str, int]],
    denominator: int,
    params: TierParams,
) -> CardSpread:
    card_id, oracle_name, engine_name = card
    found = [
        counts[key]
        for key in (name.casefold() for name in _spellings(oracle_name, engine_name))
        if key in counts and counts[key][1] > 0
    ]
    unique = list({raw: (raw, hits) for raw, hits in found}.values())
    spellings: list[Spelling] = [{"name": raw, "hits": hits} for raw, hits in unique]
    if not unique:
        return {
            "card_id": card_id,
            "name": oracle_name,
            "matched": False,
            "matched_name": None,
            "hits": None,
            "denominator": denominator,
            "share": None,
            "level": "U",
            "reason": NAME_NOT_FOUND,
            "spellings": [],
        }
    matched_name, hits = max(unique, key=lambda item: item[1])
    share = hits / denominator if denominator else None
    level, reason = tier_for_share(share, denominator, params)
    return {
        "card_id": card_id,
        "name": oracle_name,
        "matched": True,
        "matched_name": matched_name,
        "hits": hits,
        "denominator": denominator,
        "share": share,
        "level": level,
        "reason": reason,
        "spellings": spellings,
    }


def pool_spread(
    store: StudioStore, profile: str, card_ids: Sequence[str] | None = None
) -> PoolSpread:
    """Counted spread of Studio cards (all, or the given ids) in one profile's universe.

    Raises KeyError for an unknown profile or card id."""
    summary = profile_summary(store, profile)
    counted = inclusion(store, profile=profile)
    counts = _universe_counts(counted)
    params = TierParams()
    denominator = summary["denominator"]
    return {
        "universe": {
            "profile": profile,
            "snapshot_id": summary["snapshot_id"],
            "denominator": denominator,
            "denominator_by_platform": summary["denominator_by_platform"],
            "denominator_by_bracket": summary["denominator_by_bracket"],
            "data_class": summary["data_class"],
        },
        "params": params.to_dict(),
        "meaning": MEANING,
        "cards": [
            _spread_of(card, counts, denominator, params) for card in _card_rows(store, card_ids)
        ],
    }


def card_cooccurrence(
    store: StudioStore, profile: str, card_id: str, limit: int = 25
) -> CardCooccurrence:
    """Cards played together with one card in the universe, for the matched spelling.

    Raises KeyError for an unknown profile or card, ValueError when ``limit`` < 1."""
    if limit < 1:
        raise ValueError("limit must be at least 1")
    spread = pool_spread(store, profile, [card_id])
    card = spread["cards"][0]
    universe = spread["universe"]
    base: CardCooccurrence = {
        "card_id": card_id,
        "matched": card["matched"],
        "matched_name": card["matched_name"],
        "profile": profile,
        "snapshot_id": universe["snapshot_id"],
        "denominator": universe["denominator"],
        "denominator_label": "Decks im Universum",
        "decks_with_card": None,
        "decks_with_card_label": "Decks mit dieser Karte",
        "denominator_by_platform": universe["denominator_by_platform"],
        "denominator_by_bracket": universe["denominator_by_bracket"],
        "pairs": [],
        "data_class": universe["data_class"],
    }
    matched_name = card["matched_name"]
    if matched_name is None:
        return base
    result = cooccurrence(store, matched_name, profile=profile, limit=limit)
    base["decks_with_card"] = result["decks_with_card"]
    base["pairs"] = result["pairs"]
    return base


__all__ = [
    "NAME_NOT_FOUND",
    "CardCooccurrence",
    "CardSpread",
    "PoolSpread",
    "ProfileSummary",
    "card_cooccurrence",
    "pool_spread",
    "profile_summary",
]
