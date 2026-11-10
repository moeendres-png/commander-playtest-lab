"""Read models of the Studio: figures computed from stored rows, each with its denominator."""

from __future__ import annotations

from typing import Any

from .decks import color_set
from .store import StudioStore


def legal_pool(store: StudioStore, commander_names: list[str]) -> list[dict[str, Any]]:
    """Cards of the collection a deck under these commanders may use, by the stored data:
    Commander-legal and inside the commanders' color identity. ``available`` may be 0."""
    identity: frozenset[str] = frozenset()
    for name in commander_names:
        row = store.connection.execute(
            "SELECT color_identity FROM card WHERE oracle_name = ?", (name,)
        ).fetchone()
        if row is None:
            raise KeyError(name)
        identity |= color_set(row["color_identity"])
    rows = store.connection.execute(
        "SELECT c.card_id, c.oracle_name, c.color_identity, c.type_line, c.mana_value, "
        "i.available_lower_bound AS available, i.reserved "
        "FROM card c JOIN inventory i USING (card_id) WHERE c.commander_legal = 1 "
        "ORDER BY c.oracle_name"
    ).fetchall()
    return [dict(row) for row in rows if color_set(row["color_identity"]) <= identity]


def corpus_inclusion(
    store: StudioStore, card_name: str, *, play_group: str | None = None
) -> dict[str, Any]:
    """In how many distinct source decks a card appears: hits and denominator.

    Exact duplicates count once. ``play_group`` narrows the cohort (for example
    ``community`` or ``turnier_cedh``); the denominator is the number of distinct decks of
    that cohort. No decks in the cohort means the share is unknown, not zero.
    """
    where = "d.duplicate_of IS NULL"
    parameters: list[Any] = []
    if play_group is not None:
        where += " AND d.play_group = ?"
        parameters.append(play_group)
    denominator = int(
        store.connection.execute(
            f"SELECT COUNT(*) FROM corpus_deck d WHERE {where}", parameters
        ).fetchone()[0]
    )
    hits = int(
        store.connection.execute(
            "SELECT COUNT(DISTINCT c.deck_id) FROM corpus_deck_card c JOIN corpus_deck d "
            f"USING (deck_id) WHERE {where} AND c.card_name = ? AND c.section != 'sideboard'",
            [*parameters, card_name],
        ).fetchone()[0]
    )
    return {
        "card_name": card_name,
        "play_group": play_group or "all",
        "hits": hits,
        "denominator": denominator,
        "share": hits / denominator if denominator else None,
        "data_class": "DERIVED_DESCRIPTIVE",
    }
