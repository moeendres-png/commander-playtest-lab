"""Land advisor: the mana base of a deck against its coloured mana symbols.

An observation, not a prescription. For the deck it states the land count, per colour the
coloured symbols in the costs of the non-land cards (the pips and their share) and the lands
that can produce the colour. For each comparison group of source decks it states the same
figures as median and middle half. It never says what to add or cut.

Counting rules (every one of them is shown on the page):

* A land is a card whose FRONT type line says Land. A modal two-faced spell with a land back
  counts as a spell; its land side is reported apart (``modal_land_backs``, ``modal_sources``).
* Pips come from the printed mana cost. A hybrid symbol counts for each of its colours, a
  Phyrexian or "2 or colour" symbol for its colour, ``{C}`` as a colourless symbol, ``{X}``
  and generic mana not at all. A split card counts both halves, every other two-faced card
  only its front.
* A land counts as a source of every colour it can produce, so a three-colour land counts
  three times. Producers that are not lands (mana rocks, creatures) are ``other_sources``.
* A land the card data says produces no mana (a fetch land) is ``lands_no_mana``. A land with
  no card data at all, whose colours cannot be read from a basic land type either, is
  ``lands_unknown_colours``: unknown, never zero.
* The commander's own cost is ``commander_pips`` and is not part of the deck's pips.
* Groups of fewer than 30 decks are flagged.
"""

from __future__ import annotations

import re
import sqlite3
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from statistics import median

from .store import StudioStore

SCHEMA = "studio-land-advisor-1"
SMALL_GROUP = 30
_CHUNK = 500  # deck ids per query, below SQLite's variable limit
COLOURS = "WUBRG"
_SYMBOL = re.compile(r"\{([^}]+)\}")
_BASIC_COLOUR = {"Plains": "W", "Island": "U", "Swamp": "B", "Mountain": "R", "Forest": "G"}
_Row = Mapping[str, object] | sqlite3.Row


def _text(row: _Row, key: str) -> str:
    try:
        value = row[key]
    except (KeyError, IndexError):
        return ""
    return "" if value is None else str(value)


def _front(text: str) -> str:
    return text.split(" // ")[0]


def _costs(row: _Row) -> list[str]:
    cost = _text(row, "mana_cost")
    return cost.split(" // ") if _text(row, "layout") == "split" else [_front(cost)]


def _pips(row: _Row) -> tuple[Counter[str], int]:
    """Coloured pips by colour, and colourless ``{C}`` symbols, of one card."""
    found: Counter[str] = Counter()
    colourless = 0
    for cost in _costs(row):
        for symbol in _SYMBOL.findall(cost):
            parts = symbol.split("/")
            for colour in COLOURS:
                if colour in parts:
                    found[colour] += 1
            if symbol == "C":
                colourless += 1
    return found, colourless


def _has_data(row: _Row) -> bool:
    """False when the row carries no card data for the mana a card produces (``None``); an
    empty string is the card data saying that the card produces none."""
    try:
        return row["produced_mana"] is not None
    except (KeyError, IndexError):
        return False


def _produced(row: _Row, type_line: str) -> tuple[set[str], bool]:
    """Colours a land can produce, and whether they are known."""
    letters = {letter for letter in _text(row, "produced_mana") if letter in COLOURS}
    if letters:
        return letters, True
    if "C" in _text(row, "produced_mana"):
        return set(), True
    basic = {_BASIC_COLOUR[word] for word in type_line.split() if word in _BASIC_COLOUR}
    if basic:
        return basic, True
    return set(), _has_data(row)


def deck_profile(rows: Iterable[_Row]) -> dict[str, object]:
    """The figures of one deck. ``rows`` carry ``zone``, ``quantity``, ``type_line``,
    ``mana_cost``, ``produced_mana``, ``layout`` and, for commanders, ``color_identity``."""
    pips: Counter[str] = Counter()
    commander_pips: Counter[str] = Counter()
    land_sources: Counter[str] = Counter()
    other_sources: Counter[str] = Counter()
    modal_sources: Counter[str] = Counter()
    identity: set[str] = set()
    lands = nonland = modal_backs = unknown_lands = colourless_pips = colourless_lands = 0
    no_mana_lands = 0
    for row in rows:
        quantity = int(_text(row, "quantity") or "1")
        type_line = _text(row, "type_line")
        front_type = _front(type_line)
        if _text(row, "zone") == "commander":
            identity.update(letter for letter in _text(row, "color_identity") if letter in COLOURS)
            commander_pips.update(_pips(row)[0])
            continue
        if "Land" in front_type:
            lands += quantity
            colours, known = _produced(row, front_type)
            if not known:
                unknown_lands += quantity
            for colour in colours:
                land_sources[colour] += quantity
            if known and not colours:
                if "C" in _text(row, "produced_mana"):
                    colourless_lands += quantity
                else:
                    no_mana_lands += quantity
            continue
        nonland += quantity
        coloured, plain = _pips(row)
        for colour, count in coloured.items():
            pips[colour] += count * quantity
        colourless_pips += plain * quantity
        if " // " in type_line and "Land" in type_line.split(" // ", 1)[1]:
            modal_backs += quantity
            for colour in _produced(row, "")[0]:
                modal_sources[colour] += quantity
        else:
            for colour in {c for c in _text(row, "produced_mana") if c in COLOURS}:
                other_sources[colour] += quantity
    total = sum(pips.values())
    shown = [c for c in COLOURS if c in identity or pips[c] or land_sources[c]]
    colours_out = [
        {
            "colour": colour,
            "in_identity": colour in identity,
            "pips": pips[colour],
            "pip_share": round(pips[colour] / total, 4) if total else None,
            "land_sources": land_sources[colour],
            "other_sources": other_sources[colour],
            "modal_sources": modal_sources[colour],
        }
        for colour in shown
    ]
    return {
        "schema": SCHEMA,
        "lands": lands,
        "nonland": nonland,
        "identity": [c for c in COLOURS if c in identity],
        "total_pips": total,
        "colourless_pips": colourless_pips,
        "colourless_lands": colourless_lands,
        "lands_no_mana": no_mana_lands,
        "commander_pips": {c: commander_pips[c] for c in COLOURS if commander_pips[c]},
        "modal_land_backs": modal_backs,
        "lands_unknown_colours": unknown_lands,
        "colours": colours_out,
    }


def _span(values: Sequence[float]) -> dict[str, float]:
    ordered = sorted(values)

    def percentile(share: float) -> float:
        position = share * (len(ordered) - 1)
        low = int(position)
        high = min(low + 1, len(ordered) - 1)
        return ordered[low] + (ordered[high] - ordered[low]) * (position - low)

    return {
        "median": round(float(median(ordered)), 2),
        "p25": round(percentile(0.25), 2),
        "p75": round(percentile(0.75), 2),
    }


def _compact(profile: Mapping[str, object]) -> dict[str, object]:
    colours = profile["colours"]
    if not isinstance(colours, list):
        raise TypeError("profile colours must be a list")
    return {
        "lands": profile["lands"],
        "colours": {str(entry["colour"]): entry for entry in colours},
    }


def group_figures(
    cohort: str, decks: Sequence[Mapping[str, object]], *, decks_total: int
) -> dict[str, object]:
    """Median and middle half of one comparison group. ``decks`` are compact per-deck
    figures (``lands`` and ``colours`` as colour to figures); a colour a deck lacks counts 0
    for that deck, because the decks are complete."""
    group: dict[str, object] = {
        "cohort": cohort,
        "decks": decks_total,
        "decks_counted": len(decks),
        "small": len(decks) < SMALL_GROUP,
        "lands": None,
        "colours": {},
    }
    if not decks:
        return group
    group["lands"] = _span([float(str(deck["lands"])) for deck in decks])
    seen: set[str] = set()
    for deck in decks:
        colours = deck["colours"]
        if not isinstance(colours, Mapping):
            raise TypeError("deck colours must be a mapping")
        seen.update(str(key) for key in colours)
    out: dict[str, dict[str, object]] = {}
    for colour in (c for c in COLOURS if c in seen):
        figures: dict[str, list[float]] = {"land_sources": [], "pips": [], "pip_share": []}
        for deck in decks:
            colours = deck["colours"]
            if not isinstance(colours, Mapping):
                raise TypeError("deck colours must be a mapping")
            entry = colours.get(colour)
            for key in ("land_sources", "pips"):
                figures[key].append(float(str(entry[key])) if entry else 0.0)
            share = entry["pip_share"] if entry else None
            if share is not None:
                figures["pip_share"].append(float(str(share)))
        out[colour] = {key: (_span(values) if values else None) for key, values in figures.items()}
    group["colours"] = out
    return group


def source_deck_groups(
    store: StudioStore, commander_names: Sequence[str]
) -> list[dict[str, object]]:
    """The same figures for every comparison group of the commander's source decks (the
    groups ``builder.cohort_shapes`` uses). Decks with cards the card data does not know are
    left out and counted."""
    from . import builder

    members = builder.cohort_members(store, commander_names)
    if not members:
        return []
    wanted = {str(row["deck_id"]) for group in members.values() for row in group}
    cards: dict[str, list[sqlite3.Row]] = {deck_id: [] for deck_id in wanted}
    ordered = sorted(wanted)
    for start in range(0, len(ordered), _CHUNK):
        chunk = ordered[start : start + _CHUNK]
        marks = ", ".join("?" for _ in chunk)
        query = (
            "SELECT k.deck_id, k.quantity, s.type_line, s.mana_cost, s.produced_mana, s.layout "
            "FROM corpus_deck_card k JOIN scryfall_card s ON s.oracle_id = k.oracle_id "
            f"WHERE k.deck_id IN ({marks}) AND LOWER(k.section) IN ('main', 'mainboard')"
        )
        for row in store.connection.execute(query, chunk):
            cards[str(row["deck_id"])].append(row)
    compact: dict[str, dict[str, object]] = {}
    for deck_id, rows in cards.items():
        compact[deck_id] = _compact(deck_profile(rows))
    groups: list[dict[str, object]] = []
    for cohort, group in members.items():
        complete = [
            compact[str(row["deck_id"])] for row in group if row["resolved"] == row["cards"]
        ]
        groups.append(group_figures(cohort, complete, decks_total=len(group)))
    return groups


def land_candidates(
    store: StudioStore,
    commander_names: Sequence[str],
    deck_cards: Sequence[object] = (),
    *,
    cohort: str = "all",
    min_share: float = 0.20,
) -> list[dict[str, object]]:
    """Free non-basic lands of the commander's legal collection pool that are not in the
    deck and appear in at least ``min_share`` of ``cohort`` (unknown frequencies sorted last).

    Marks are never read or used for ordering. Unknown produced colours stay ``None``.
    """
    from . import builder

    if not commander_names:
        return []
    try:
        identity, commander_ids = builder.commander_identity(store, commander_names)
    except KeyError:
        return []
    in_deck_ids = set(commander_ids)
    in_deck_names: set[str] = set()
    for item in deck_cards:
        if isinstance(item, str):
            in_deck_ids.add(item)
            in_deck_names.add(item)
            continue
        cid = getattr(item, "card_id", None) or (
            item.get("card_id") if isinstance(item, Mapping) else None
        )
        zone = (
            getattr(item, "zone", "main")
            if not isinstance(item, Mapping)
            else item.get("zone", "main")
        )
        qty = (
            getattr(item, "quantity", 1)
            if not isinstance(item, Mapping)
            else item.get("quantity", 1)
        )
        if cid and str(zone) in ("main", "commander") and int(qty or 0) > 0:
            in_deck_ids.add(str(cid))

    cohorts = builder.cohort_sizes(store, commander_names)
    hits = builder._corpus_hits(store, commander_names)
    of = int(cohorts.get(cohort, 0))
    small_group = of < SMALL_GROUP

    keyed: list[tuple[int, float, str, dict[str, object]]] = []
    for row in store.connection.execute(
        "SELECT c.card_id, c.oracle_name, c.color_identity, c.type_line, "
        "c.is_basic_land, c.layout, c.produced_mana, i.available_lower_bound "
        "FROM card_fact c JOIN inventory i USING (card_id) "
        "WHERE c.commander_legal = 1 ORDER BY c.oracle_name"
    ):
        if not builder.color_set(row["color_identity"]) <= identity:
            continue
        card_id = str(row["card_id"])
        if card_id in in_deck_ids or str(row["oracle_name"]) in in_deck_names:
            continue
        available = int(row["available_lower_bound"] or 0)
        if available <= 0:
            continue
        type_line = _text(row, "type_line")
        front_type = _front(type_line)
        if "Land" not in front_type or bool(row["is_basic_land"]):
            continue
        if any(word in _BASIC_COLOUR for word in front_type.split()) and "Basic" in front_type:
            continue
        colours_set, known_colours = _produced(row, front_type)
        colours_out: list[str] | None = (
            [c for c in COLOURS if c in colours_set] if known_colours else None
        )
        name = str(row["oracle_name"])
        if of > 0 and name in hits and cohort in hits[name]:
            decks_val: int | None = int(hits[name][cohort])
            share_val: float | None = round(decks_val / of, 4)
            if share_val < min_share:
                continue
            sort_key = (0, -share_val, name)
        else:
            decks_val = None
            share_val = None
            sort_key = (1, 0.0, name)
        keyed.append(
            (
                *sort_key,
                {
                    "card_id": card_id,
                    "name": name,
                    "colours": colours_out,
                    "decks": decks_val,
                    "of": of,
                    "share": share_val,
                    "available": available,
                    "small_group": small_group,
                },
            )
        )
    keyed.sort(key=lambda entry: entry[:3])
    return [entry[3] for entry in keyed]
