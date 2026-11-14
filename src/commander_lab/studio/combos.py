"""Listed combos of a commander against one deck list.

The combos come from the commander's combo list file (``edhrec_<commander>_combos``): each
row names the full card set of one combo and the number of decks the source counted it in.
This module only compares card sets: which listed combos a deck holds completely and which
lack exactly one card. It is a count over a public list, not a rating, and a combo the
source does not list is unknown here, not absent.

Names are matched by the full card name, then by the FRONT face of a two-part card, never
by the back half.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Sequence

from .store import StudioStore

SCHEMA = "studio-deck-combos-1"


def _keys(name: str) -> list[str]:
    """The names a deck card answers to: its full name and, for a two-part card, its front
    face."""
    full = name.strip().casefold()
    front = full.split(" // ")[0].strip()
    return [full] if front == full else [full, front]


def stored_combos(store: StudioStore, commander: str) -> list[tuple[list[str], int]]:
    """Every stored combo of ``commander``: (card names, deck count), in list order."""
    rows = store.connection.execute(
        "SELECT cards, num_decks FROM commander_combo WHERE commander_name = ? COLLATE NOCASE "
        "ORDER BY ordinal",
        (commander,),
    ).fetchall()
    found: list[tuple[list[str], int]] = []
    for row in rows:
        # A damaged row (no JSON list of names, no count) is skipped: it must not take the
        # deck check down with it.
        try:
            cards = json.loads(row["cards"])
            decks = int(row["num_decks"])
        except (TypeError, ValueError):
            continue
        if not isinstance(cards, list) or not cards:
            continue
        if not all(isinstance(name, str) and name.strip() for name in cards):
            continue
        found.append((list(cards), decks))
    return found


def deck_combos(
    store: StudioStore, rows: Sequence[sqlite3.Row], commanders: Iterable[str] | None = None
) -> dict[str, object]:
    """Listed combos of the deck's commander(s): complete in the deck, or one card short.

    ``rows`` are the deck rows (``oracle_name``, ``zone``). The commander is taken from the
    rows of zone ``commander`` unless ``commanders`` names it. Without a stored combo list
    the result says so (``listed`` 0), it never reports "no combos".
    """
    names: set[str] = set()
    for row in rows:
        names.update(_keys(str(row["oracle_name"])))
    chosen = (
        list(commanders)
        if commanders is not None
        else [str(row["oracle_name"]) for row in rows if row["zone"] == "commander"]
    )
    complete: list[dict[str, object]] = []
    one_missing: list[dict[str, object]] = []
    listed = 0
    seen: set[str] = set()
    for commander in chosen:
        for cards, decks in stored_combos(store, commander):
            key = json.dumps(sorted(name.casefold() for name in cards))
            if key in seen:
                continue
            seen.add(key)
            listed += 1
            missing = [name for name in cards if name.strip().casefold() not in names]
            entry: dict[str, object] = {"cards": cards, "num_decks": decks}
            if not missing:
                complete.append(entry)
            elif len(missing) == 1:
                one_missing.append({**entry, "missing": missing[0]})
    complete.sort(key=lambda item: (-int(str(item["num_decks"])), str(item["cards"])))
    one_missing.sort(key=lambda item: (-int(str(item["num_decks"])), str(item["cards"])))
    return {
        "schema": SCHEMA,
        "commanders": chosen,
        "listed": listed,
        "complete": complete,
        "one_missing": one_missing,
        "meaning": (
            "Vergleich mit der Kombo-Liste der Quelle für diesen Commander. Gezählt wird nur, "
            "was die Quelle listet; eine nicht gelistete Kombo ist hier unbekannt. Die Deckzahl "
            "ist die Zahl der Decks, in denen die Quelle die Kombo gezählt hat. Keine Bewertung."
        ),
    }
