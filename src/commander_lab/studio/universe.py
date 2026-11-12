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

import json
from typing import Any

from .store import StudioStore, now_utc

COUNTED_SECTIONS = ("main", "commander", "companion")
_SPEC_KEYS = {"platforms", "cohorts", "date_from", "date_to", "min_main_cards"}


def _validate_spec(spec: dict[str, Any]) -> dict[str, Any]:
    unknown = set(spec) - _SPEC_KEYS
    if unknown:
        raise ValueError(f"unknown universe spec keys: {sorted(unknown)}")
    cleaned: dict[str, Any] = {}
    for key in ("platforms", "cohorts"):
        values = spec.get(key) or []
        if not all(isinstance(value, str) and value for value in values):
            raise ValueError(f"universe spec {key} must be a list of non-empty strings")
        if values:
            cleaned[key] = sorted(set(values))
    for key in ("date_from", "date_to"):
        if spec.get(key):
            cleaned[key] = str(spec[key])[:10]
    if spec.get("min_main_cards") is not None:
        minimum = int(spec["min_main_cards"])
        if minimum < 0:
            raise ValueError("universe spec min_main_cards must not be negative")
        cleaned["min_main_cards"] = minimum
    return cleaned


def save_profile(store: StudioStore, name: str, spec: dict[str, Any]) -> dict[str, Any]:
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


def list_profiles(store: StudioStore) -> list[dict[str, Any]]:
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


def get_profile(store: StudioStore, name: str) -> dict[str, Any]:
    row = store.connection.execute(
        "SELECT profile_id, name, spec, created_at FROM universe_profile WHERE name = ?",
        (name,),
    ).fetchone()
    if row is None:
        raise KeyError(name)
    profile: dict[str, Any] = {
        "profile_id": str(row["profile_id"]),
        "name": str(row["name"]),
        "spec": json.loads(row["spec"]),
        "created_at": str(row["created_at"]),
    }
    return profile


def resolve_universe(store: StudioStore, spec: dict[str, Any]) -> list[str]:
    """Deck ids of the universe a spec selects, in stable order."""
    cleaned = _validate_spec(spec)
    where = ["d.duplicate_of IS NULL"]
    parameters: list[Any] = []
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
    store: StudioStore, profile: str | None, spec: dict[str, Any] | None
) -> dict[str, Any]:
    if profile is not None:
        found: dict[str, Any] = get_profile(store, profile)["spec"]
        return found
    return _validate_spec(spec or {})


def inclusion(
    store: StudioStore,
    *,
    profile: str | None = None,
    spec: dict[str, Any] | None = None,
    card_names: list[str] | None = None,
) -> dict[str, Any]:
    """Per-card deck counts over one universe: hits, denominator, share.

    With ``card_names`` only those cards are returned (missing ones with 0 hits); without
    it, every card that appears in the universe is returned, ordered by hits.
    """
    deck_ids = resolve_universe(store, _universe_spec(store, profile, spec))
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
    rows = [
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
        "spec": _universe_spec(store, profile, spec),
        "denominator": denominator,
        "rows": rows,
        "data_class": "DERIVED_DESCRIPTIVE",
    }


def cooccurrence(
    store: StudioStore,
    card_name: str,
    *,
    profile: str | None = None,
    spec: dict[str, Any] | None = None,
    limit: int = 25,
) -> dict[str, Any]:
    """How many universe decks contain ``card_name`` together with each other card."""
    deck_ids = resolve_universe(store, _universe_spec(store, profile, spec))
    denominator = 0
    pairs: list[dict[str, Any]] = []
    if deck_ids:
        marks = ", ".join("?" for _ in deck_ids)
        sections = ", ".join("?" for _ in COUNTED_SECTIONS)
        base = (
            f"SELECT deck_id FROM corpus_deck_card WHERE deck_id IN ({marks}) "
            f"AND section IN ({sections}) AND card_name = ?"
        )
        with_card = [
            str(row[0])
            for row in store.connection.execute(base, [*deck_ids, *COUNTED_SECTIONS, card_name])
        ]
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
    store: StudioStore, *, profile: str | None = None, spec: dict[str, Any] | None = None
) -> str:
    """A short fingerprint of a universe: its spec plus the deck ids it currently selects.

    Two snapshots with the same id select the same decks under the same spec; any import
    that changes the selection changes the id, so figures can cite the exact universe
    they were counted over.
    """
    import hashlib

    cleaned = _universe_spec(store, profile, spec)
    deck_ids = resolve_universe(store, cleaned)
    digest = hashlib.sha256()
    digest.update(json.dumps(cleaned, sort_keys=True).encode())
    for deck_id in deck_ids:
        digest.update(f"\n{deck_id}".encode())
    return f"universe:{digest.hexdigest()[:16]}:{len(deck_ids)}"


__all__ = [
    "COUNTED_SECTIONS",
    "cooccurrence",
    "get_profile",
    "inclusion",
    "list_profiles",
    "resolve_universe",
    "save_profile",
    "snapshot_id",
]
