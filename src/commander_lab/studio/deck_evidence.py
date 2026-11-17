"""Evidence per deck card: one table, one row per card, one column per kind of evidence.

Every cell is a counted value of ONE source with its numerator and denominator and the group
(cohort) named in the column. Nothing is added up, mixed or rated: the payload has no sum, no
score and no combined figure, the groups ``all`` and ``tuned`` are two columns and never one
number, and the Owner's marks (favourite, excluded, note) are not read at all.

Missing is never 0. A card no source deck of the commander names has an unknown count (the
builder's ``decks_known`` convention), a card without an EDHREC row has "no row", a card
without role data has unknown roles. The commander and the basic lands are "not applicable".

Reuse, no second counting: the source-deck counts and the fit come from the cached
source-deck index of ``similar_decks`` (the one ``card_duel`` reads); the EDHREC figure is the
builder's (``builder._edhrec_entry`` over ``builder.widest_edhrec_rows`` and the stored
inclusion signal); the Playgroup figures are the builder's ``playgroup_entry``; the stored
signals (spellbook shells, tournament lists, EDHTop16) are read by
``strength_view.card_signal_values``; the combos are the commander's stored combo list
(``combos.stored_combos``).

``fit`` is the ``card_duel`` figure for the deck card X against the rest of the deck: the
average, over the source decks of the chosen group that play X, of the share of the deck's
other cards (without X, the commander and basic lands) those decks also play, next to the same
average over all source decks of the group (the baseline). All cards of the deck are computed
in one pass: one overlap count per source deck over the postings of the deck's cards.
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from collections.abc import Iterable, Sequence
from itertools import chain

from . import builder, cache, signals
from .combos import _keys, stored_combos
from .similar_decks import (
    _basic_oracle_names,
    _canonical_name,
    _commander_source_index,
)
from .store import StudioStore
from .strength_view import card_signal_values
from .universe import spelling_owners

SCHEMA = "studio-deck-evidence-1"
TUNED = "tuned"
THINNEST_LIMIT = 10
NOT_APPLICABLE = "nicht anwendbar"
NOTE = (
    "Nur Zählwerte je Quelle und Gruppe; sie werden nicht zusammengerechnet und ergeben keine "
    "Gesamtnote."
)
_EXTRA_SIGNALS = {
    "shells": signals.SIGNAL_SHELLS,
    "tournament": signals.SIGNAL_TOURNAMENT,
    "edhtop16": signals.SIGNAL_EDHTOP16,
}


def _round(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(float(value), digits)


def _count(value: object) -> int | None:
    if value is None:
        return None
    return round(float(str(value)))


def _bundle(store: StudioStore, commander_names: Sequence[str]) -> dict[str, object]:
    """The commander-level figures per card id, remembered per store state (read-only).

    Built from the same readers as the builder, over every card of the collection: the EDHREC
    figures, the Playgroup atlas, the roles, the stored signals and the commander's combos.
    The Owner's marks are not among them."""
    return cache.cached(
        store,
        ("deck_evidence_bundle", tuple(commander_names)),
        lambda: _build_bundle(store, tuple(commander_names)),
    )


def _build_bundle(store: StudioStore, commander_names: tuple[str, ...]) -> dict[str, object]:
    db = store.connection
    widest = builder.widest_edhrec_rows(db, commander_names)
    roles = builder.role_names(db)
    atlas = builder.playgroup_rows(db)
    names = {
        str(row["card_id"]): str(row["oracle_name"])
        for row in db.execute("SELECT card_id, oracle_name FROM card_fact")
    }
    stored: dict[str, dict[str, object]] = {}
    if len(commander_names) == 1:
        stored = {
            card_id: dict(found)
            for card_id, found in card_signal_values(
                store, commander_names[0], list(names), names, extra=_EXTRA_SIGNALS
            ).items()
        }
    combo_cards: list[frozenset[str]] = []
    seen: set[frozenset[str]] = set()
    for commander in commander_names:
        for cards, _num_decks in stored_combos(store, commander):
            key = frozenset(name.strip().casefold() for name in cards)
            if key not in seen:
                seen.add(key)
                combo_cards.append(key)
    return {
        "edhrec": {
            card_id: builder._edhrec_entry(widest.get(card_id), found.get("inclusion"))
            for card_id, found in ((cid, stored.get(cid, {})) for cid in names)
        },
        "roles": roles,
        "atlas": atlas,
        "signals": stored,
        "combos": combo_cards,
    }


def _group_cell(count: int | None, size: int) -> dict[str, object] | None:
    """Source decks of one group playing the card: ``n`` of ``of`` (the group's decks)."""
    if count is None or not size:
        return None
    return {"n": count, "of": size, "small_group": size < builder.SMALL_DENOMINATOR, "sort": count}


def _edhrec_cell(entry: dict[str, object] | None) -> dict[str, object] | None:
    if entry is None:
        return None
    denominator = _count(entry.get("denominator"))
    numerator = _count(entry.get("numerator"))
    pct = entry.get("pct")
    return {
        "page": str(entry["page"]),
        "main_page": "/" not in str(entry["page"]) and entry.get("origin") == "table",
        "pct": _round(None if pct is None else float(str(pct)), 1),
        "n": numerator,
        "of": denominator,
        "small_group": denominator is not None and denominator < builder.SMALL_DENOMINATOR,
        "note": "Zeile ohne Wert" if pct is None else None,
        "sort": None if pct is None else _round(float(str(pct)), 4),
    }


def _atlas_cell(entry: dict[str, object] | None) -> dict[str, object] | None:
    if entry is None or entry["observed_winrate_gap_pp"] is None:
        return None
    n = _count(entry.get("winrate_when_cast_n"))
    gap = float(str(entry["observed_winrate_gap_pp"]))
    low, high = entry["ci_95_lower_pp"], entry["ci_95_upper_pp"]
    return {
        "gap_pp": gap,
        "ci_low_pp": None if low is None else float(str(low)),
        "ci_high_pp": None if high is None else float(str(high)),
        "n": n,
        "small_group": bool(entry["insufficient_sample"])
        or (n is not None and n < builder.SMALL_DENOMINATOR),
        "status": str(entry["status"]),
        "sort": gap,
    }


def _tournament_cell(found: object, *, derived_numerator: bool = False) -> dict[str, object] | None:
    if not isinstance(found, dict) or found.get("value") is None:
        return None
    numerator = _count(found.get("numerator"))
    denominator = _count(found.get("denominator"))
    return {
        "n": numerator,
        "of": denominator,
        "share": _round(float(str(found["value"]))),
        "derived_numerator": derived_numerator and numerator is not None,
        "small_group": denominator is not None and denominator < builder.SMALL_DENOMINATOR,
        "sort": _round(float(str(found["value"]))),
    }


def _shell_cell(found: object) -> dict[str, object] | None:
    if not isinstance(found, dict) or found.get("value") is None:
        return None
    count = _count(found["value"])
    return {"count": count, "sort": count}


def _applicable(row: sqlite3.Row, name: str, basics: frozenset[str]) -> tuple[bool, str]:
    if row["zone"] == "commander":
        return False, "Commander"
    if bool(row["is_basic_land"]) or name.casefold() in basics:
        return False, "Standardland"
    return True, ""


def _columns(denominators: dict[str, list[int]], commander: str) -> list[dict[str, object]]:
    short = commander.split(",")[0]
    columns: list[dict[str, object]] = [
        {
            "key": "decks_all",
            "short": f"Decks von {short}",
            "label": "Quelldecks, Gruppe „alle“",
            "basis": f"Decks des Commanders ({short}): in wie vielen der Quelldecks der Gruppe "
            "„alle“ steht die Karte (n/N)",
            "missing": "unbekannt (kein Quelldeck nennt die Karte)",
        },
        {
            "key": "decks_tuned",
            "short": "Bracket 4 und 5, abgeleitet",
            "label": "Quelldecks, Gruppe „tuned“",
            "basis": "Gruppe „tuned“ = abgeleitet aus Bracket 4 und 5; überschneidet sich mit "
            "„alle“ (n/N)",
            "missing": "unbekannt (kein Quelldeck nennt die Karte)",
        },
        {
            "key": "edhrec",
            "short": f"Seite je Zelle genannt (Seiten von {short})",
            "label": "EDHREC-Anteil",
            "basis": f"Anteil der Decks auf einer EDHREC-Seite von {short} (n/N); die Seite steht "
            "in der Zelle: Hauptseite des Commanders oder eine Unterseite (Thema), wenn die "
            "Hauptseite keine Zeile für die Karte hat",
            "missing": "keine Zeile",
        },
        {
            "key": "shells",
            "short": f"für {short} gezählt, ohne Nenner",
            "label": "Spellbook-Shells",
            "basis": f"Anzahl Combo-Shells mit der Karte, gezählt für {short} (Farbidentität "
            "und Kartenpool); Zählwert ohne Nenner",
            "missing": "keine Zeile",
        },
        {
            "key": "combos",
            "short": f"gespeicherte Kombos von {short}",
            "label": "Kombo-beteiligt",
            "basis": f"in wie vielen der gespeicherten Kombos von {short} die Karte steht "
            "(n von den gelisteten Kombos)",
            "missing": "keine Kombo-Liste gespeichert",
        },
        {
            "key": "playgroup",
            "short": f"alle Commander, Mehrspieler (nicht nur {short})",
            "label": "Playgroup: Siegraten-Differenz",
            "basis": f"beobachtete Differenz mit 95-%-Intervall und n (Partien mit gewirkter "
            f"Karte); alle Commander, Mehrspieler (nicht nur {short})",
            "missing": "keine Zeile",
        },
    ]
    if "topdeck" in denominators:
        columns.append(
            {
                "key": "topdeck",
                "short": f"Listen von {short}",
                "of": denominators["topdeck"],
                "label": "TopDeck-Turnierlisten",
                "basis": f"Listen von {short} mit der Karte (n/N, N = Zahl der Listen; sehr "
                "kleine Gruppe)",
                "missing": "keine Zeile",
            }
        )
    if "edhtop16" in denominators:
        columns.append(
            {
                "key": "edhtop16",
                "short": f"Einträge von {short}",
                "of": denominators["edhtop16"],
                "label": "EDHTop16",
                "basis": f"Spielrate bei {short} in den Turnier-Einträgen (n/N; n = Rate mal N "
                "abgeleitet, N = Zahl der Einträge)",
                "missing": "keine Zeile",
            }
        )
    columns += [
        {
            "key": "roles",
            "short": "öffentliche Rollen-Tags",
            "label": "Rollen",
            "basis": "Rollen der Karte (öffentliche Rollen-Tags)",
            "missing": "unbekannt (keine Rolle)",
        },
        {
            "key": "role_count",
            "short": "Zahl der Rollen",
            "label": "Anzahl Rollen",
            "basis": "Zahl der Rollen der Karte",
            "missing": "unbekannt (keine Rolle)",
        },
        {
            "key": "fit",
            "short": "mit Grundwert der Gruppe",
            "label": "Passung zu den übrigen Karten",
            "basis": "In der gewählten Gruppe: durchschnittlicher Anteil der übrigen Karten dieses "
            "Decks (ohne die Karte selbst, Commander, Standardländer), den die Quelldecks "
            "spielen, die die Karte spielen; daneben der Grundwert über alle Quelldecks der "
            "Gruppe und die Zahl dieser Decks",
            "missing": "unbekannt (kein Quelldeck der Gruppe spielt die Karte)",
        },
    ]
    return columns


def order_cards(
    cards: Iterable[dict[str, object]], column: str = "decks_all", *, descending: bool = False
) -> list[dict[str, object]]:
    """The sort contract of the table. Applicable cards by the chosen column's own value
    (never by a sum or a mix of columns), unknown values ALWAYS after the known ones in both
    directions, ties by name; cards "not applicable" (commander, basic lands) last.

    Default: ``decks_all`` ascending, the thinnest evidence first. Marks play no part."""

    def cell_sort(card: dict[str, object]) -> object:
        cells = card["cells"]
        if not isinstance(cells, dict):
            raise TypeError("cells must be a mapping")
        cell = cells.get(column)
        return None if cell is None else cell["sort"]

    def name(card: dict[str, object]) -> str:
        return str(card["name"]).casefold()

    applicable = [card for card in cards if card["applicable"]]
    other = [card for card in cards if not card["applicable"]]
    known = [card for card in applicable if cell_sort(card) is not None]
    unknown = [card for card in applicable if cell_sort(card) is None]
    known.sort(key=name)
    known.sort(key=lambda card: cell_sort(card), reverse=descending)  # type: ignore[arg-type,return-value]
    unknown.sort(key=name)
    other.sort(key=lambda card: (card["zone"] != "commander", name(card)))
    return [*known, *unknown, *other]


def deck_evidence(
    store: StudioStore, rows: Sequence[sqlite3.Row], *, cohort: str = builder.ALL_DECKS
) -> dict[str, object]:
    """The evidence table of the deck ``rows`` (``decks.list_rows``).

    Raises ValueError without a commander or for a group the commander has no decks in."""
    commander_names = tuple(str(row["oracle_name"]) for row in rows if row["zone"] == "commander")
    if not commander_names:
        raise ValueError("commander is required")
    sizes = builder.cohort_sizes(store, commander_names)
    if cohort != builder.ALL_DECKS and cohort not in sizes:
        raise ValueError(f"unknown group: {cohort}")

    index = _commander_source_index(store, commander_names)
    decks = index["decks"]
    cohorts_by_deck = index["cohorts_by_deck"]
    postings = index["postings"]
    members = {
        group: {
            i for i, deck in enumerate(decks) if group in cohorts_by_deck.get(deck["deck_id"], ())
        }
        for group in {builder.ALL_DECKS, TUNED, cohort}
    }
    owners = spelling_owners(store)
    basics = _basic_oracle_names(store)
    bundle = _bundle(store, commander_names)
    edhrec: dict[str, dict[str, object] | None] = bundle["edhrec"]  # type: ignore[assignment]
    role_map: dict[str, list[str]] = bundle["roles"]  # type: ignore[assignment]
    atlas: dict[str, sqlite3.Row] = bundle["atlas"]  # type: ignore[assignment]
    stored: dict[str, dict[str, object]] = bundle["signals"]  # type: ignore[assignment]
    combo_sets: list[frozenset[str]] = bundle["combos"]  # type: ignore[assignment]
    oracle_by_card = {
        str(r["card_id"]): str(r["oracle_id"] or "")
        for r in store.connection.execute(
            f"SELECT card_id, oracle_id FROM card_fact WHERE card_id IN "
            f"({','.join('?' * len(rows))})",
            [str(row["card_id"]) for row in rows],
        )
    }

    # One pass for the whole deck: how many of the deck's cards each source deck plays.
    deck_names: dict[str, str] = {}
    applicable_rows: dict[str, tuple[bool, str]] = {}
    for row in rows:
        canonical = _canonical_name(owners, str(row["oracle_name"]))
        applicable_rows[str(row["card_id"])] = _applicable(row, canonical, basics)
        deck_names[str(row["card_id"])] = canonical
    deckset = {deck_names[card_id] for card_id, (ok, _why) in applicable_rows.items() if ok}
    overlap: Counter[int] = Counter(
        chain.from_iterable(postings[name] for name in deckset if name in postings)
    )
    chosen = members[cohort]
    chosen_overlap = sum(overlap[i] for i in chosen)
    others = len(deckset) - 1

    cards: list[dict[str, object]] = []
    tournament_n: dict[str, set[int]] = {}
    for row in rows:
        card_id = str(row["card_id"])
        ok, why = applicable_rows[card_id]
        base: dict[str, object] = {
            "card_id": card_id,
            "name": str(row["oracle_name"]),
            "quantity": int(row["quantity"]),
            "zone": str(row["zone"]),
            "group": builder.main_type(row["type_line"]),
            "applicable": ok,
            "reason": None if ok else why,
        }
        if not ok:
            cards.append({**base, "cells": {}})
            continue
        name = deck_names[card_id]
        known = name in postings
        listed = postings.get(name, ())
        cells: dict[str, dict[str, object] | None] = {}
        for key, group in (("decks_all", builder.ALL_DECKS), ("decks_tuned", TUNED)):
            count: int | None = None
            if known:
                count = (
                    len(listed)
                    if group == builder.ALL_DECKS
                    else sum(1 for i in listed if i in members[group])
                )
            cells[key] = _group_cell(count, len(members[group]))
        cells["edhrec"] = _edhrec_cell(edhrec.get(card_id))
        found = stored.get(card_id, {})
        cells["shells"] = _shell_cell(found.get("shells"))
        names = _keys(str(row["oracle_name"]))
        cells["combos"] = (
            {
                "n": (n := sum(1 for combo in combo_sets if any(k in combo for k in names))),
                "of": len(combo_sets),
                "small_group": len(combo_sets) < builder.SMALL_DENOMINATOR,
                "sort": n,
            }
            if combo_sets
            else None
        )
        oracle_id = oracle_by_card.get(card_id, "")
        cells["playgroup"] = _atlas_cell(
            builder.playgroup_entry(
                atlas.get(card_id) or (atlas.get(oracle_id) if oracle_id else None)
            )
        )
        cells["topdeck"] = _tournament_cell(found.get("tournament"))
        cells["edhtop16"] = _tournament_cell(found.get("edhtop16"), derived_numerator=True)
        for key in ("topdeck", "edhtop16"):
            cell = cells[key]
            if cell is not None:
                tournament_n.setdefault(key, set())
                if cell["of"] is not None:
                    tournament_n[key].add(int(str(cell["of"])))
        card_roles = role_map.get(oracle_id, []) if oracle_id else []
        cells["roles"] = (
            {"roles": card_roles, "sort": ", ".join(card_roles).casefold()} if card_roles else None
        )
        cells["role_count"] = (
            {"n": len(card_roles), "sort": len(card_roles)} if card_roles else None
        )
        # Fit and baseline: the card_duel figures with this card as the only duel card.
        playing = [i for i in listed if i in chosen] if known else []
        fit: dict[str, object] | None = None
        if known and chosen and others > 0:
            baseline = _round((chosen_overlap - len(playing)) / (len(chosen) * others))
            value = (
                _round((sum(overlap[i] for i in playing) - len(playing)) / (len(playing) * others))
                if playing
                else None
            )
            fit = {
                "value": value,
                "baseline": baseline,
                "decks": len(playing),
                "of": len(chosen),
                "small_group": len(playing) < builder.SMALL_DENOMINATOR,
                "sort": value,
            }
        cells["fit"] = fit
        cards.append({**base, "cells": cells})

    columns = _columns(
        {key: sorted(found) for key, found in tournament_n.items()}, commander_names[0]
    )
    ordered = order_cards(cards)
    known_decks = [
        card
        for card in ordered
        if card["applicable"] and card["cells"]["decks_all"] is not None  # type: ignore[index]
    ]
    thinnest = [
        {
            "card_id": card["card_id"],
            "name": card["name"],
            "n": card["cells"]["decks_all"]["n"],  # type: ignore[index]
            "of": card["cells"]["decks_all"]["of"],  # type: ignore[index]
        }
        for card in known_decks[:THINNEST_LIMIT]
    ]
    applicable_count = sum(1 for card in cards if card["applicable"])
    group_size = len(members[builder.ALL_DECKS])
    return {
        "schema": SCHEMA,
        "commander": list(commander_names),
        "cohort": {
            "key": cohort,
            "decks": len(chosen),
            "small_group": len(chosen) < builder.SMALL_DENOMINATOR,
        },
        "groups": {
            group: {
                "decks": len(members[group]),
                "small_group": len(members[group]) < builder.SMALL_DENOMINATOR,
            }
            for group in (builder.ALL_DECKS, TUNED)
        },
        "small_group_below": builder.SMALL_DENOMINATOR,
        "columns": columns,
        "cards": ordered,
        "footer": {
            "decks_all": {"of": group_size},
            "decks_tuned": {"of": len(members[TUNED])},
            "fit": {
                "baseline": _round(chosen_overlap / (len(chosen) * len(deckset)))
                if chosen and deckset
                else None,
                "decks": len(chosen),
                "deck_cards": len(deckset),
            },
        },
        "thinnest": {
            "group": builder.ALL_DECKS,
            "cards": thinnest,
            "unknown": applicable_count - len(known_decks),
            "applicable": applicable_count,
        },
        "order": "wenigste Quelldecks zuerst; unbekannt immer zuletzt; bei Gleichstand nach Name",
        "note": NOTE,
    }
