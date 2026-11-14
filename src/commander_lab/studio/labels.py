"""Archetype labels: free-form words the Owner puts on a card or on a saved deck.

Like the marks (favorite, excluded, note) they are the Owner's own and live only in the
Studio store. They filter the pool table and show in the card window. They are never an
input of a tier, the strength index, the rating layers or any evidence figure
(``evidence.TIER_POLICY["never_inputs"]``); a test proves that tier and index are identical
with and without labels.
"""

from __future__ import annotations

import re

from .store import StudioStore, now_utc

MAX_LABEL_LENGTH = 40
MAX_LABELS = 20
_SPACE = re.compile(r"\s+")
_FORBIDDEN = re.compile(r"[<>\x00-\x1f]")


def clean(values: object) -> list[str]:
    """The labels of a request, trimmed, spaces collapsed, unique ignoring case, sorted.

    ``ValueError`` for more than ``MAX_LABELS``, a label longer than ``MAX_LABEL_LENGTH`` or
    one with angle brackets or control characters."""
    if not isinstance(values, (list, tuple)):
        raise ValueError("labels are a list of words")
    found: dict[str, str] = {}
    for value in values:
        if not isinstance(value, str):
            raise ValueError("a label is text")
        text = _SPACE.sub(" ", value).strip()
        if not text:
            continue
        if len(text) > MAX_LABEL_LENGTH:
            raise ValueError(f"a label has at most {MAX_LABEL_LENGTH} characters")
        if _FORBIDDEN.search(text):
            raise ValueError("a label holds no angle brackets or control characters")
        found.setdefault(text.casefold(), text)
    if len(found) > MAX_LABELS:
        raise ValueError(f"at most {MAX_LABELS} labels")
    return sorted(found.values(), key=str.casefold)


def card_labels(store: StudioStore) -> dict[str, list[str]]:
    """Every card that has labels, as card id to its sorted labels."""
    found: dict[str, list[str]] = {}
    for row in store.connection.execute("SELECT card_id, label FROM card_label"):
        found.setdefault(str(row["card_id"]), []).append(str(row["label"]))
    return {card_id: sorted(names, key=str.casefold) for card_id, names in found.items()}


def deck_labels(store: StudioStore) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for row in store.connection.execute("SELECT deck_id, label FROM deck_label"):
        found.setdefault(str(row["deck_id"]), []).append(str(row["label"]))
    return {deck_id: sorted(names, key=str.casefold) for deck_id, names in found.items()}


def known_labels(store: StudioStore) -> list[str]:
    """All labels in use on cards or decks, one spelling each, for suggestions."""
    names: dict[str, str] = {}
    for table in ("card_label", "deck_label"):
        for row in store.connection.execute(f"SELECT label FROM {table}"):  # noqa: S608
            names.setdefault(str(row["label"]).casefold(), str(row["label"]))
    return sorted(names.values(), key=str.casefold)


def _replace(store: StudioStore, table: str, key: str, owner: str, values: list[str]) -> None:
    with store.connection as db:
        db.execute(f"DELETE FROM {table} WHERE {key} = ?", (owner,))  # noqa: S608
        db.executemany(
            f"INSERT INTO {table}({key}, label, created_at) VALUES (?, ?, ?)",  # noqa: S608
            [(owner, label, now_utc()) for label in values],
        )


def set_card_labels(store: StudioStore, card_id: str, values: object) -> list[str]:
    """Replace the labels of a card. ``KeyError`` for an unknown card."""
    cleaned = clean(values)
    if (
        store.connection.execute("SELECT 1 FROM card WHERE card_id = ?", (card_id,)).fetchone()
        is None
    ):
        raise KeyError(card_id)
    _replace(store, "card_label", "card_id", card_id, cleaned)
    return cleaned


def set_deck_labels(store: StudioStore, deck_id: str, values: object) -> list[str]:
    """Replace the labels of a saved deck. ``KeyError`` for an unknown deck."""
    cleaned = clean(values)
    if (
        store.connection.execute("SELECT 1 FROM deck WHERE deck_id = ?", (deck_id,)).fetchone()
        is None
    ):
        raise KeyError(deck_id)
    _replace(store, "deck_label", "deck_id", deck_id, cleaned)
    return cleaned
