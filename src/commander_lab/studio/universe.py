"""Deck universes: owner-selected sets of source decks, and counts over them.

A *universe* is a stored profile (``universe_profile``) whose spec selects source decks
from the corpus: by platform, by cohort membership (``corpus_cohort`` rows such as
``bracket:3`` or ``source:edhrec``), by deck date range and by a minimum main-deck size.
Every figure computed over a universe is a plain count with its denominator: inclusion of
a card is the number of distinct universe decks whose main, commander or companion
sections contain it, over the number of decks in the universe. Exact duplicates
(``corpus_deck.duplicate_of``) never count, matching ``queries.corpus_inclusion``;
unlike that older per-group helper, sections ``sideboard`` and ``maybeboard`` are both
excluded here, because both are outside the deck that was played.

An empty spec selects every stored source deck. A profile whose filters match no deck
yields a universe of size 0; shares over it are ``None`` (unknown), never zero.
"""

from __future__ import annotations

import datetime
import json
from collections.abc import Mapping
from typing import TypedDict

from ._coerce import to_int
from .store import StudioStore, now_utc

COUNTED_SECTIONS = ("main", "commander", "companion")
_SPEC_KEYS = {"platforms", "cohorts", "date_from", "date_to", "min_main_cards"}


class UniverseSpec(TypedDict, total=False):
    """A validated universe spec; absent keys mean "no filter"."""

    platforms: list[str]
    cohorts: list[str]
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
    rows: list[InclusionRow]
    data_class: str


class CooccurrenceRow(TypedDict):
    card_name: str
    decks_together: int


class CooccurrenceResult(TypedDict):
    card_name: str
    profile: str | None
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
    where = ["d.duplicate_of IS NULL"]
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
    sql = f"SELECT d.deck_id FROM corpus_deck d WHERE {' AND '.join(where)}"
    deck_ids = [str(row[0]) for row in store.connection.execute(sql, parameters)]
    for cohort in cleaned.get("cohorts", []):
        members = {
            str(row[0])
            for row in store.connection.execute(
                "SELECT deck_id FROM corpus_cohort WHERE cohort = ?", (cohort,)
            )
        }
        deck_ids = [deck_id for deck_id in deck_ids if deck_id in members]
    minimum = cleaned.get("min_main_cards")
    if minimum:
        sections = ", ".join("?" for _ in COUNTED_SECTIONS)
        sizes = {
            str(row[0]): int(row[1])
            for row in store.connection.execute(
                f"SELECT deck_id, SUM(quantity) FROM corpus_deck_card "
                f"WHERE section IN ({sections}) GROUP BY deck_id",
                COUNTED_SECTIONS,
            )
        }
        deck_ids = [deck_id for deck_id in deck_ids if sizes.get(deck_id, 0) >= minimum]
    return sorted(deck_ids)


def _universe_spec(
    store: StudioStore, profile: str | None, spec: Mapping[str, object] | None
) -> UniverseSpec:
    if profile is not None:
        return get_profile(store, profile)["spec"]
    return _validate_spec(spec or {})


def inclusion(
    store: StudioStore,
    *,
    profile: str | None = None,
    spec: Mapping[str, object] | None = None,
    card_names: list[str] | None = None,
) -> InclusionResult:
    """Per-card deck counts over one universe: hits, denominator, share.

    With ``card_names`` only those cards are returned (missing ones with 0 hits); without
    it, every card that appears in the universe is returned, ordered by hits.
    """
    resolved_spec = _universe_spec(store, profile, spec)
    deck_ids = resolve_universe(store, resolved_spec)
    denominator = len(deck_ids)
    counts: dict[str, int] = {}
    if deck_ids:
        marks = ", ".join("?" for _ in deck_ids)
        sections = ", ".join("?" for _ in COUNTED_SECTIONS)
        counts = {
            str(row[0]): int(row[1])
            for row in store.connection.execute(
                f"SELECT card_name, COUNT(DISTINCT deck_id) FROM corpus_deck_card "
                f"WHERE deck_id IN ({marks}) AND section IN ({sections}) GROUP BY card_name",
                [*deck_ids, *COUNTED_SECTIONS],
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
        "rows": rows,
        "data_class": "DERIVED_DESCRIPTIVE",
    }


def cooccurrence(
    store: StudioStore,
    card_name: str,
    *,
    profile: str | None = None,
    spec: Mapping[str, object] | None = None,
    limit: int = 25,
) -> CooccurrenceResult:
    """How many universe decks contain ``card_name`` together with each other card."""
    deck_ids = resolve_universe(store, _universe_spec(store, profile, spec))
    denominator = 0
    pairs: list[CooccurrenceRow] = []
    if deck_ids:
        marks = ", ".join("?" for _ in deck_ids)
        sections = ", ".join("?" for _ in COUNTED_SECTIONS)
        base = (
            f"SELECT deck_id FROM corpus_deck_card WHERE deck_id IN ({marks}) "
            f"AND section IN ({sections}) AND card_name = ?"
        )
        with_card = sorted(
            {
                str(row[0])
                for row in store.connection.execute(base, [*deck_ids, *COUNTED_SECTIONS, card_name])
            }
        )
        denominator = len(with_card)
        if with_card:
            marks2 = ", ".join("?" for _ in with_card)
            pairs = [
                {"card_name": str(row[0]), "decks_together": int(row[1])}
                for row in store.connection.execute(
                    f"SELECT card_name, COUNT(DISTINCT deck_id) AS decks_together "
                    f"FROM corpus_deck_card "
                    f"WHERE deck_id IN ({marks2}) AND section IN ({sections}) "
                    f"AND card_name != ? GROUP BY card_name "
                    f"ORDER BY decks_together DESC, card_name LIMIT ?",
                    [*with_card, *COUNTED_SECTIONS, card_name, limit],
                )
            ]
    return {
        "card_name": card_name,
        "profile": profile,
        "decks_with_card": denominator,
        "pairs": pairs,
        "data_class": "DERIVED_DESCRIPTIVE",
    }


def snapshot_id(
    store: StudioStore, *, profile: str | None = None, spec: Mapping[str, object] | None = None
) -> str:
    """A short fingerprint of a universe: its spec plus what it currently selects.

    The digest covers the spec, the selected deck ids and each deck's stored card
    fingerprint, so a snapshot id changes when the selection changes *or* when a
    selected deck's cards are replaced by a later import. Two equal snapshot ids mean
    the same spec over the same deck contents; figures can cite the exact universe
    they were counted over.
    """
    import hashlib

    cleaned = _universe_spec(store, profile, spec)
    deck_ids = resolve_universe(store, cleaned)
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
    "UniverseSpec",
    "cooccurrence",
    "get_profile",
    "inclusion",
    "list_profiles",
    "resolve_universe",
    "save_profile",
    "snapshot_id",
]
