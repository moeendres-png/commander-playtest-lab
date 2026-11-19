"""Coverage-gap matrix of one commander's legal pool, computed from the Studio store (#1545).

Counts only: no card name leaves the store. For the pool (legal collection cards inside the
commander's colour identity) it counts in how many decks of the deduplicated local deck-list
universe each pool card appears, in classes (none, 1 to 4, 5 to 29, 30 to 99, 100 or more, and
unknown when a card's name is ambiguous so that no count exists). The classes sum to the pool
size. The whole local universe and each bracket cohort group are separate matrices with their
own denominator; they are never added together. The header carries the generation time, the pool
size, the denominators and a fingerprint of the store state the figures were read from.

Reads only; the store must be a copy or the Owner's own store, never written here.

Not the same matrix as ``sources.calculate_pool_gap_matrix`` (``studio sources --gap-report``),
and deliberately not merged with it:

* ``sources.calculate_pool_gap_matrix`` grades each pool card's evidence over all layers (facts,
  rules, corpus hits, EDHREC, Spellbook) into a coverage grade and a research-priority score, one
  record per card with its name, against the legacy corpus cohort (``ALL_DECKS``) as denominator.
  It answers "which cards should be researched next".
* This module counts the pool in deck-frequency classes over the deduplicated local deck-list
  universe (the one the tier list uses), one matrix per universe, each with its own denominator,
  counts only. It answers "how thin is the deck data under the pool" and is rebuilt from the
  current store by ``scripts/build_gap_matrix_from_store.py``.

The two use different per-card measures and denominators, so merging would change the existing
grades and figures; they share the pool itself (``builder.pool_cards``). Neither replaces the
other, and neither figure may be quoted without its denominator.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import cast

from . import builder, corpus_signals, universe_choice, universe_view
from .store import StudioStore
from .universe import UniverseSpec

GAP_SCHEMA = "studio-pool-gap-matrix-1"
CLASSES: tuple[tuple[str, int, int | None], ...] = (
    ("in_no_deck", 0, 0),
    ("in_1_to_4_decks", 1, 4),
    ("in_5_to_29_decks", 5, 29),
    ("in_30_to_99_decks", 30, 99),
    ("in_100_or_more_decks", 100, None),
)
UNKNOWN_CLASS = "unknown"


def store_fingerprint(store: StudioStore) -> str:
    """Hash of the data epoch (what imports change); equal fingerprints mean the same imported
    state. It is not a hash of the database file."""
    return hashlib.sha256(repr(store.data_epoch()).encode("utf-8")).hexdigest()


def classify(hits: Sequence[int | None]) -> dict[str, int]:
    """Class counts; a ``None`` count (no count exists) is its own ``unknown`` class."""
    result = {name: 0 for name, _low, _high in CLASSES}
    result[UNKNOWN_CLASS] = 0
    for value in hits:
        if value is None:
            result[UNKNOWN_CLASS] += 1
            continue
        for name, low, high in CLASSES:
            if value >= low and (high is None or value <= high):
                result[name] += 1
                break
    return result


def _matrix(
    store: StudioStore, spec: UniverseSpec, ids: list[str], commander: str, pool: int
) -> dict[str, object]:
    denominator, snapshot, cards = universe_view.spread_for_spec(
        store, spec, ids, commander_names=[commander]
    )
    # Same rule as corpus_signals: a card no deck names is a counted zero, except when its
    # name is ambiguous (a withheld front face): that card has no count (unknown).
    hits: list[int | None] = []
    for item in cards:
        if item["filter_card"]:
            # A card the universe itself requires stands in every deck of the subset by
            # definition: it has no count (and no level), so it is unknown here, never "in no deck".
            hits.append(None)
        elif item["hits"] is not None:
            hits.append(int(item["hits"]))
        else:
            hits.append(None if item.get("ambiguous_front_face") else 0)
    counted = len(hits)
    classes = classify(hits)
    # A pool card the spread does not return has no count either: unknown, not "in no deck".
    classes[UNKNOWN_CLASS] += pool - counted
    return {
        "denominator_decks": denominator,
        "snapshot": snapshot,
        "classes": classes,
        "classes_sum": sum(classes.values()),
        "pool": pool,
    }


def build_gap_matrix(
    store: StudioStore, commander: str, *, now: datetime | None = None
) -> dict[str, object]:
    """The matrix of ``commander``'s pool. ``now`` is only injectable for tests."""
    stamp = (now or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ")
    pool_cards = builder.pool_cards(store, [commander], with_signals=False)
    cards = cast(list[dict[str, object]], pool_cards["cards"])
    ids = [str(card["card_id"]) for card in cards]
    pool = len(ids)
    base = universe_choice.local_spec(store, commander)
    groups: dict[str, object] = {}
    for key, label, cohorts in corpus_signals.COHORT_GROUPS:
        spec = cast(UniverseSpec, {**base, "cohorts": list(cohorts)})
        entry = _matrix(store, spec, ids, commander, pool)
        entry["label"] = label
        groups[key] = entry
    return {
        "schema": GAP_SCHEMA,
        "commander": commander,
        "generated_at_utc": stamp,
        "store_fingerprint": store_fingerprint(store),
        "pool_size": pool,
        "counts_only": "no card names; one matrix per universe, each with its own denominator",
        "all_local_decks": _matrix(store, base, ids, commander, pool),
        "cohort_groups_not_added_together": groups,
    }
