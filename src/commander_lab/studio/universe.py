"""Deck universes: owner-selected sets of source decks, and counts over them.

A *universe* is a stored profile (``universe_profile``) whose spec selects source decks
from the corpus: by platform, by cohort membership (``corpus_cohort`` rows such as
``bracket:3`` or ``source:edhrec``), by deck date range and by a minimum main-deck size.
Every figure computed over a universe is a plain count with its denominator: inclusion of
a card is the number of distinct universe decks whose counted sections (``main`` and
``mainboard``, the same section under the spelling of the decklist and the corpus importer,
plus ``commander`` and ``companion``) contain it, over the number of decks in the universe. Exact duplicates
never count twice: decks of the universe that share a content fingerprint count once
(the lowest deck id), so the same list stored under two ids is one deck *inside the
selected universe*, whatever its siblings outside it look like. An empty fingerprint
means "content unknown": such a deck is its own key and is never deduplicated. Only cards
with a quantity above zero count, and a deck without any such row in a counted section is
not part of any universe. A deck carrying several bracket cohorts is reported under the
bucket ``multiple`` in the bracket breakdown. Sections ``sideboard`` and ``maybeboard`` are
both excluded here, because both are outside the deck that was played. The minimum deck size
counts each card once per deck and section group: a card listed in both ``main`` and
``mainboard`` contributes its larger quantity, not the sum.

An empty spec selects every stored source deck. A profile whose filters match no deck
yields a universe of size 0; shares over it are ``None`` (unknown), never zero.
"""

from __future__ import annotations

import datetime
import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import TypedDict

from ._coerce import to_int
from .store import StudioStore, now_utc

# The corpus importer stores the main deck as "mainboard", the decklist importer as "main".
COUNTED_SECTIONS = ("main", "mainboard", "commander", "companion")
_SPEC_KEYS = {"platforms", "cohorts", "commanders", "date_from", "date_to", "min_main_cards"}


class UniverseSpec(TypedDict, total=False):
    """A validated universe spec; absent keys mean "no filter"."""

    platforms: list[str]
    cohorts: list[str]
    commanders: list[str]
    date_from: str
    date_to: str
    min_main_cards: int


class Profile(TypedDict):
    profile_id: str
    name: str
    spec: UniverseSpec
    created_at: str


class SavedProfile(TypedDict):
    profile_id: str
    name: str
    spec: UniverseSpec


class InclusionRow(TypedDict):
    card_name: str
    hits: int
    denominator: int
    share: float | None


class InclusionResult(TypedDict):
    profile: str | None
    spec: UniverseSpec
    denominator: int
    denominator_by_platform: dict[str, int]
    denominator_by_bracket: dict[str, int]
    rows: list[InclusionRow]
    data_class: str


class CooccurrenceRow(TypedDict):
    card_name: str
    decks_together: int


class CooccurrenceResult(TypedDict):
    card_name: str
    profile: str | None
    denominator: int
    denominator_by_platform: dict[str, int]
    denominator_by_bracket: dict[str, int]
    decks_with_card: int
    pairs: list[CooccurrenceRow]
    data_class: str


def _string_list(spec: Mapping[str, object], key: str) -> list[str]:
    values = spec.get(key) or []
    if isinstance(values, str) or not isinstance(values, (list, tuple)):
        raise ValueError(f"universe spec {key} must be a list of non-empty strings")
    strings = [value for value in values if isinstance(value, str) and value]
    if len(strings) != len(values):
        raise ValueError(f"universe spec {key} must be a list of non-empty strings")
    return sorted(set(strings))


def _iso_date(spec: Mapping[str, object], key: str) -> str | None:
    if not spec.get(key):
        return None
    try:
        return datetime.date.fromisoformat(str(spec[key])[:10]).isoformat()
    except ValueError:
        raise ValueError(f"universe spec {key} must be an ISO date (YYYY-MM-DD)") from None


def _validate_spec(spec: Mapping[str, object]) -> UniverseSpec:
    unknown = set(spec) - _SPEC_KEYS
    if unknown:
        raise ValueError(f"unknown universe spec keys: {sorted(unknown)}")
    cleaned: UniverseSpec = {}
    platforms = _string_list(spec, "platforms")
    if platforms:
        cleaned["platforms"] = platforms
    cohorts = _string_list(spec, "cohorts")
    if cohorts:
        cleaned["cohorts"] = cohorts
    commanders = _string_list(spec, "commanders")
    if commanders:
        cleaned["commanders"] = commanders
    date_from = _iso_date(spec, "date_from")
    if date_from is not None:
        cleaned["date_from"] = date_from
    date_to = _iso_date(spec, "date_to")
    if date_to is not None:
        cleaned["date_to"] = date_to
    if spec.get("min_main_cards") is not None:
        minimum = to_int(spec["min_main_cards"])
        if minimum < 0:
            raise ValueError("universe spec min_main_cards must not be negative")
        cleaned["min_main_cards"] = minimum
    return cleaned


def save_profile(store: StudioStore, name: str, spec: Mapping[str, object]) -> SavedProfile:
    """Store (or replace) a named universe profile; returns the stored profile."""
    cleaned = _validate_spec(spec)
    profile_id = f"universe:{name}"
    with store.connection as db:
        db.execute(
            "INSERT OR REPLACE INTO universe_profile(profile_id, name, spec, created_at) "
            "VALUES (?, ?, ?, ?)",
            (profile_id, name, json.dumps(cleaned, sort_keys=True), now_utc()),
        )
    return {"profile_id": profile_id, "name": name, "spec": cleaned}


def list_profiles(store: StudioStore) -> list[dict[str, object]]:
    rows = store.connection.execute(
        "SELECT profile_id, name, spec, created_at FROM universe_profile ORDER BY name"
    ).fetchall()
    return [
        {
            "profile_id": row["profile_id"],
            "name": row["name"],
            "spec": json.loads(row["spec"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def get_profile(store: StudioStore, name: str) -> Profile:
    row = store.connection.execute(
        "SELECT profile_id, name, spec, created_at FROM universe_profile WHERE name = ?",
        (name,),
    ).fetchone()
    if row is None:
        raise KeyError(name)
    profile: Profile = {
        "profile_id": str(row["profile_id"]),
        "name": str(row["name"]),
        "spec": json.loads(row["spec"]),
        "created_at": str(row["created_at"]),
    }
    return profile


def resolve_universe(store: StudioStore, spec: Mapping[str, object]) -> list[str]:
    """Deck ids of the universe a spec selects, in stable order."""
    cleaned = _validate_spec(spec)
    where = ["1 = 1"]
    parameters: list[str] = []
    if cleaned.get("platforms"):
        marks = ", ".join("?" for _ in cleaned["platforms"])
        where.append(f"d.platform IN ({marks})")
        parameters.extend(cleaned["platforms"])
    if cleaned.get("date_from"):
        where.append("d.deck_date >= ?")
        parameters.append(cleaned["date_from"])
    if cleaned.get("date_to"):
        where.append("d.deck_date <= ?")
        parameters.append(cleaned["date_to"])
    sql = f"SELECT d.deck_id, d.fingerprint FROM corpus_deck d WHERE {' AND '.join(where)}"
    selected = [(str(row[0]), str(row[1])) for row in store.connection.execute(sql, parameters)]
    deck_ids = [deck_id for deck_id, _ in selected]
    counted_marks = ", ".join("?" for _ in COUNTED_SECTIONS)
    with_cards = {
        str(row[0])
        for row in store.connection.execute(
            f"SELECT DISTINCT deck_id FROM corpus_deck_card "
            f"WHERE section IN ({counted_marks}) AND quantity > 0",
            COUNTED_SECTIONS,
        )
    }
    deck_ids = [deck_id for deck_id in deck_ids if deck_id in with_cards]
    for cohort in cleaned.get("cohorts", []):
        members = {
            str(row[0])
            for row in store.connection.execute(
                "SELECT deck_id FROM corpus_cohort WHERE cohort = ?", (cohort,)
            )
        }
        deck_ids = [deck_id for deck_id in deck_ids if deck_id in members]
    for commander in cleaned.get("commanders", []):
        # Only decks bound to the commander count; a deck without a binding is counted
        # for no commander, so figures of two commanders never share a denominator.
        bound = {
            str(row[0])
            for row in store.connection.execute(
                "SELECT key FROM commander_binding "
                "WHERE kind = 'corpus_deck' AND commander_name = ?",
                (commander,),
            )
        }
        deck_ids = [deck_id for deck_id in deck_ids if deck_id in bound]
    minimum = cleaned.get("min_main_cards")
    if minimum:
        sections = ", ".join("?" for _ in COUNTED_SECTIONS)
        # "main" and "mainboard" are one section: per (deck, card) the larger quantity.
        sizes = {
            str(row[0]): int(row[1])
            for row in store.connection.execute(
                f"SELECT deck_id, SUM(quantity) FROM ("
                f"SELECT deck_id, card_name, "
                f"CASE WHEN section IN ('main', 'mainboard') THEN 'main' ELSE section END AS grp, "
                f"MAX(quantity) AS quantity FROM corpus_deck_card "
                f"WHERE section IN ({sections}) GROUP BY deck_id, card_name, grp) "
                f"GROUP BY deck_id",
                COUNTED_SECTIONS,
            )
        }
        deck_ids = [deck_id for deck_id in deck_ids if sizes.get(deck_id, 0) >= minimum]
    # Query-time dedupe inside the selected universe: one deck per content fingerprint,
    # the lowest deck id wins.
    fingerprints = dict(selected)
    first_by_fingerprint: dict[str, str] = {}
    for deck_id in sorted(deck_ids):
        fingerprint = fingerprints[deck_id]
        key = fingerprint if fingerprint else f"\x00unknown:{deck_id}"
        first_by_fingerprint.setdefault(key, deck_id)
    return sorted(first_by_fingerprint.values())


@contextmanager
def _universe_table(store: StudioStore, deck_ids: list[str]) -> Iterator[str]:
    """Load the deck ids into a TEMP table so queries never bind one variable per deck.

    SQLite caps bound variables (999 on older builds); a universe can be larger."""
    name = "temp.universe_deck"
    db = store.connection
    db.execute(f"DROP TABLE IF EXISTS {name}")
    # CREATE ... AS SELECT is one statement with one bound variable and, unlike an INSERT,
    # opens no implicit transaction: a read-only query must not leave the connection locked.
    db.execute(
        "CREATE TEMP TABLE universe_deck AS SELECT value AS deck_id FROM json_each(?)",
        (json.dumps(deck_ids),),
    )
    try:
        yield name
    finally:
        db.execute(f"DROP TABLE IF EXISTS {name}")


def _composition(store: StudioStore, deck_ids: list[str]) -> tuple[dict[str, int], dict[str, int]]:
    """Denominator split by source platform and by bracket cohort.

    Decks without a bracket cohort count as ``unknown``, decks with several different
    bracket cohorts as ``multiple``; the buckets sum to the denominator."""
    by_platform: dict[str, int] = {}
    by_bracket: dict[str, int] = {}
    if not deck_ids:
        return by_platform, by_bracket
    with _universe_table(store, deck_ids) as universe_deck:
        for platform, count in store.connection.execute(
            f"SELECT d.platform, COUNT(*) FROM corpus_deck d "
            f"JOIN {universe_deck} u ON u.deck_id = d.deck_id "
            f"GROUP BY d.platform ORDER BY d.platform"
        ):
            by_platform[str(platform)] = int(count)
        brackets_of: dict[str, set[str]] = {}
        for deck_id, cohort in store.connection.execute(
            f"SELECT c.deck_id, c.cohort FROM corpus_cohort c "
            f"JOIN {universe_deck} u ON u.deck_id = c.deck_id "
            f"WHERE c.cohort LIKE 'bracket:%'"
        ):
            brackets_of.setdefault(str(deck_id), set()).add(str(cohort))
    for deck_id in deck_ids:
        labels = brackets_of.get(deck_id, set())
        label = "unknown" if not labels else "multiple" if len(labels) > 1 else next(iter(labels))
        by_bracket[label] = by_bracket.get(label, 0) + 1
    return by_platform, dict(sorted(by_bracket.items()))


def _universe_spec(
    store: StudioStore,
    profile: str | None,
    spec: Mapping[str, object] | None,
    commander_names: Sequence[str] | None,
) -> UniverseSpec:
    """The spec of a profile or a free spec, narrowed to ``commander_names`` when given.

    A spec that already names other commanders is not silently widened or replaced."""
    if profile is not None:
        resolved = get_profile(store, profile)["spec"]
    else:
        resolved = _validate_spec(spec or {})
    if commander_names:
        wanted = sorted({str(name) for name in commander_names})
        stored = resolved.get("commanders")
        if stored and sorted(stored) != wanted:
            raise ValueError(f"the universe is defined for {sorted(stored)}, not for {wanted}")
        resolved = {**resolved, "commanders": wanted}
    return resolved


def inclusion(
    store: StudioStore,
    *,
    profile: str | None = None,
    spec: Mapping[str, object] | None = None,
    card_names: list[str] | None = None,
    commander_names: Sequence[str] | None,
) -> InclusionResult:
    """Per-card deck counts over one universe: hits, denominator, share.

    With ``card_names`` only those cards are returned (missing ones with 0 hits); without
    it, every card that appears in the universe is returned, ordered by hits.
    """
    resolved_spec = _universe_spec(store, profile, spec, commander_names)
    deck_ids = resolve_universe(store, resolved_spec)
    denominator = len(deck_ids)
    by_platform, by_bracket = _composition(store, deck_ids)
    counts: dict[str, int] = {}
    if deck_ids:
        sections = ", ".join("?" for _ in COUNTED_SECTIONS)
        with _universe_table(store, deck_ids) as universe_deck:
            counts = {
                str(row[0]): int(row[1])
                for row in store.connection.execute(
                    f"SELECT c.card_name, COUNT(DISTINCT c.deck_id) FROM corpus_deck_card c "
                    f"JOIN {universe_deck} u ON u.deck_id = c.deck_id "
                    f"WHERE c.section IN ({sections}) AND c.quantity > 0 "
                    f"GROUP BY c.card_name",
                    COUNTED_SECTIONS,
                )
            }
    names = card_names if card_names is not None else sorted(counts, key=lambda n: (-counts[n], n))
    rows: list[InclusionRow] = [
        {
            "card_name": name,
            "hits": counts.get(name, 0),
            "denominator": denominator,
            "share": counts.get(name, 0) / denominator if denominator else None,
        }
        for name in names
    ]
    return {
        "profile": profile,
        "spec": resolved_spec,
        "denominator": denominator,
        "denominator_by_platform": by_platform,
        "denominator_by_bracket": by_bracket,
        "rows": rows,
        "data_class": "DERIVED_DESCRIPTIVE",
    }


def cooccurrence(
    store: StudioStore,
    card_name: str,
    *,
    profile: str | None = None,
    spec: Mapping[str, object] | None = None,
    limit: int | None = 25,
    commander_names: Sequence[str] | None,
) -> CooccurrenceResult:
    """How many universe decks contain ``card_name`` together with each other card.

    ``limit`` caps the pair list (``None`` = all pairs); it must be at least 1."""
    if limit is not None and limit < 1:
        raise ValueError("limit must be at least 1 (or None for no limit)")
    deck_ids = resolve_universe(store, _universe_spec(store, profile, spec, commander_names))
    universe_size = len(deck_ids)
    by_platform, by_bracket = _composition(store, deck_ids)
    denominator = 0
    pairs: list[CooccurrenceRow] = []
    if deck_ids:
        sections = ", ".join("?" for _ in COUNTED_SECTIONS)
        with _universe_table(store, deck_ids) as universe_deck:
            denominator = int(
                store.connection.execute(
                    f"SELECT COUNT(DISTINCT c.deck_id) FROM corpus_deck_card c "
                    f"JOIN {universe_deck} u ON u.deck_id = c.deck_id "
                    f"WHERE c.section IN ({sections}) AND c.quantity > 0 AND c.card_name = ?",
                    [*COUNTED_SECTIONS, card_name],
                ).fetchone()[0]
            )
            if denominator:
                pairs = [
                    {"card_name": str(row[0]), "decks_together": int(row[1])}
                    for row in store.connection.execute(
                        f"SELECT o.card_name, COUNT(DISTINCT o.deck_id) AS decks_together "
                        f"FROM corpus_deck_card o JOIN {universe_deck} u "
                        f"ON u.deck_id = o.deck_id "
                        f"WHERE o.section IN ({sections}) AND o.quantity > 0 "
                        f"AND o.card_name != ? AND o.deck_id IN ("
                        f"SELECT c.deck_id FROM corpus_deck_card c "
                        f"JOIN {universe_deck} v ON v.deck_id = c.deck_id "
                        f"WHERE c.section IN ({sections}) AND c.quantity > 0 "
                        f"AND c.card_name = ?) "
                        f"GROUP BY o.card_name "
                        f"ORDER BY decks_together DESC, o.card_name LIMIT ?",
                        [
                            *COUNTED_SECTIONS,
                            card_name,
                            *COUNTED_SECTIONS,
                            card_name,
                            -1 if limit is None else limit,
                        ],
                    )
                ]
    return {
        "card_name": card_name,
        "profile": profile,
        "denominator": universe_size,
        "denominator_by_platform": by_platform,
        "denominator_by_bracket": by_bracket,
        "decks_with_card": denominator,
        "pairs": pairs,
        "data_class": "DERIVED_DESCRIPTIVE",
    }


class UniverseDecks(TypedDict):
    """One resolved universe with the deck ids behind every raw card name."""

    spec: UniverseSpec
    denominator: int
    denominator_by_platform: dict[str, int]
    denominator_by_bracket: dict[str, int]
    snapshot_id: str
    data_class: str
    decks_by_name: dict[str, set[str]]


def universe_decks(
    store: StudioStore, *, profile: str, commander_names: Sequence[str] | None
) -> UniverseDecks:
    """Resolve a profile once: its figures and, per raw card name, the universe decks that
    list it in a counted section with a quantity above zero."""
    spec = _universe_spec(store, profile, None, commander_names)
    deck_ids = resolve_universe(store, spec)
    by_platform, by_bracket = _composition(store, deck_ids)
    decks_by_name: dict[str, set[str]] = {}
    if deck_ids:
        sections = ", ".join("?" for _ in COUNTED_SECTIONS)
        with _universe_table(store, deck_ids) as universe_deck:
            for name, deck_id in store.connection.execute(
                f"SELECT DISTINCT c.card_name, c.deck_id FROM corpus_deck_card c "
                f"JOIN {universe_deck} u ON u.deck_id = c.deck_id "
                f"WHERE c.section IN ({sections}) AND c.quantity > 0",
                COUNTED_SECTIONS,
            ):
                decks_by_name.setdefault(str(name), set()).add(str(deck_id))
    return {
        "spec": spec,
        "denominator": len(deck_ids),
        "denominator_by_platform": by_platform,
        "denominator_by_bracket": by_bracket,
        "snapshot_id": _snapshot_of(store, spec, deck_ids),
        "data_class": "DERIVED_DESCRIPTIVE",
        "decks_by_name": decks_by_name,
    }


def cooccurrence_in_decks(
    store: StudioStore, deck_ids: set[str], exclude: set[str], limit: int
) -> list[CooccurrenceRow]:
    """Cards listed together within ``deck_ids`` (a card's own decks), most common first.

    ``exclude`` holds casefolded names left out of the pairs (the card's own spellings)."""
    if not deck_ids:
        return []
    sections = ", ".join("?" for _ in COUNTED_SECTIONS)
    with _universe_table(store, sorted(deck_ids)) as universe_deck:
        rows = [
            (str(row[0]), int(row[1]))
            for row in store.connection.execute(
                f"SELECT o.card_name, COUNT(DISTINCT o.deck_id) FROM corpus_deck_card o "
                f"JOIN {universe_deck} u ON u.deck_id = o.deck_id "
                f"WHERE o.section IN ({sections}) AND o.quantity > 0 GROUP BY o.card_name",
                COUNTED_SECTIONS,
            )
        ]
    kept = sorted(
        (item for item in rows if item[0].casefold() not in exclude),
        key=lambda item: (-item[1], item[0]),
    )
    return [{"card_name": name, "decks_together": count} for name, count in kept[:limit]]


def snapshot_id(
    store: StudioStore,
    *,
    profile: str | None = None,
    spec: Mapping[str, object] | None = None,
    commander_names: Sequence[str] | None,
) -> str:
    """A short fingerprint of a universe: its spec plus what it currently selects.

    The digest covers the spec, the selected deck ids and each deck's stored card
    fingerprint, so a snapshot id changes when the selection changes *or* when a
    selected deck's cards are replaced by a later import. Two equal snapshot ids mean
    the same spec over the same deck contents; figures can cite the exact universe
    they were counted over.
    """
    cleaned = _universe_spec(store, profile, spec, commander_names)
    return _snapshot_of(store, cleaned, resolve_universe(store, cleaned))


def _snapshot_of(store: StudioStore, cleaned: UniverseSpec, deck_ids: list[str]) -> str:
    import hashlib

    fingerprints = {
        str(row[0]): str(row[1])
        for row in store.connection.execute("SELECT deck_id, fingerprint FROM corpus_deck")
    }
    digest = hashlib.sha256()
    digest.update(json.dumps(cleaned, sort_keys=True).encode())
    for deck_id in deck_ids:
        digest.update(f"\n{deck_id}:{fingerprints.get(deck_id, '')}".encode())
    return f"universe:{digest.hexdigest()[:16]}:{len(deck_ids)}"


__all__ = [
    "COUNTED_SECTIONS",
    "CooccurrenceResult",
    "InclusionResult",
    "Profile",
    "SavedProfile",
    "UniverseDecks",
    "UniverseSpec",
    "cooccurrence",
    "cooccurrence_in_decks",
    "get_profile",
    "inclusion",
    "list_profiles",
    "resolve_universe",
    "save_profile",
    "snapshot_id",
    "universe_decks",
]
