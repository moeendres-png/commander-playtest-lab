"""Colour castability and opening hands of a deck, exact and conditioned on land drops (#1415).

The method follows Frank Karsten ("How Many Sources Do You Need to Consistently Cast Your
Spells? A 2022 Update", https://github.com/frankkarsten/MTG-Math):

1. The colour event is conditioned on the land drops: among the draws that hold at least ``T``
   lands by turn ``T`` (``T`` = the card's mana value, at least 1), how many also hold the
   coloured sources the cost needs. Missing the land drop is a separate event and reported
   apart (``p_land_drops``).
2. Two or more pips of one colour are one compound event (at least that many sources of the
   colour among the same drawn lands), never a product of single-pip probabilities.
3. A multicoloured cost is one joint event over all its colours, computed directly over land
   groups by the colours they produce (a dual land counts for both colours of one draw, but
   only once as a land). Products of per-colour probabilities are not used anywhere.
4. Every probability carries its condition and the counts it was computed from.

Counting rules, shown with the result: sources are lands only (``produced_mana`` of the card
data, else the basic land type); lands that produce no coloured mana per the card data count as
lands but not as direct sources, and lands without card data count as lands with unknown
colours. Hybrid and Phyrexian symbols are not part of the requirement (reported per card).
Draws by turn ``T``: 7 + ``T`` cards (in multiplayer only the starting player skips the first
draw), no mulligan, no extra card draw. Exact multivariate hypergeometric arithmetic, no Monte
Carlo. The result is a description, never a land count recommendation.

Search lands (WP-2 of the builder audit, #1404): every land falls into one class read from the
card data and the rules text of its front face (``classify_land``): ``direkt`` (it produces
coloured mana), ``suchland`` (no coloured mana of its own, and the text searches *your* library
for a basic land card, for cards of named basic land types or for a land card with a basic land
type and puts the card onto the battlefield), ``ohne_farbe`` (known to produce no coloured mana,
no such search) and ``unbekannt`` (no card data, no rules text, or a search text that is not one
of these forms, such as a search for a Gate). Every figure is given twice: ``direkt`` (search
lands are no source, as before) and ``mit Suchland`` (``with_search``). The second one rests on a
calculation assumption, not a rules ruling: a search land counts as a source of every colour that
a land of the main deck matching its search (by type line: supertype Basic and basic land types,
never by name) produces directly, as one land of the joint event, like a dual land. It assumes a
matching card is still in the library and leaves out entering tapped, life payment (fetch lands),
activation costs (for example ``{1}`` of the Panoramas) and that some search lands fetch two
lands. A search land without a matching land in the deck is a known source of no colour.

The commander (WP-3) is one more requirement at the turn of its mana value from the command
zone: library = main deck without the commander, no commander tax. The land count table (WP-3)
gives, for 30 to 40 lands in the same library, the exact chance to hold at least ``T`` lands
among the ``7 + T`` cards seen by turn ``T``.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from fractions import Fraction
from math import comb

SCHEMA = "studio-castability-1"
COLOURS = "WUBRG"
_SYMBOL = re.compile(r"\{([^}]+)\}")
_BASIC_COLOUR = {"Plains": "W", "Island": "U", "Swamp": "B", "Mountain": "R", "Forest": "G"}
OPENING_HAND = 7
EARLY_ACTION_MAX_MV = 2
KEEP_LANDS = (2, 4)


def draws_by_turn(turn: int) -> int:
    """Cards seen by turn ``turn`` when the player draws in the first turn."""
    return OPENING_HAND + turn


def _text(row: Mapping[str, object], key: str) -> str:
    value = row.get(key)
    return "" if value is None else str(value)


def requirement(mana_cost: str) -> tuple[dict[str, int], bool]:
    """Coloured pips of a cost per colour, and whether hybrid or Phyrexian symbols were left
    out. Only the front face of a two-faced cost counts."""
    need: Counter[str] = Counter()
    skipped = False
    for symbol in _SYMBOL.findall(mana_cost.split(" // ")[0]):
        if symbol in COLOURS:
            need[symbol] += 1
        elif "/" in symbol and any(colour in symbol.split("/") for colour in COLOURS):
            skipped = True
    return dict(need), skipped


def land_colours(row: Mapping[str, object]) -> frozenset[str] | None:
    """Colours a land produces; ``None`` when the card data says nothing (unknown)."""
    front_type = _text(row, "type_line").split(" // ")[0]
    produced = row.get("produced_mana")
    if produced is not None:
        letters = frozenset(letter for letter in str(produced) if letter in COLOURS)
        if letters:
            return letters
    basic = frozenset(_BASIC_COLOUR[word] for word in front_type.split() if word in _BASIC_COLOUR)
    if basic:
        return basic
    return None if produced is None else frozenset()


LAND_DIRECT = "direkt"
LAND_SEARCH = "suchland"
LAND_NO_COLOUR = "ohne_farbe"
LAND_UNKNOWN = "unbekannt"
LAND_CLASSES = (LAND_DIRECT, LAND_SEARCH, LAND_NO_COLOUR, LAND_UNKNOWN)
_ALL_BASIC_TYPES = frozenset(_BASIC_COLOUR)
REASON_UNREADABLE_SEARCH = "Suchtext ist keine Suche nach Standardland oder Standardland-Typ"
REASON_TARGETED_SEARCH = "Suche hängt an einem Ziel (Fähigkeit mit „target“)"
_TARGET = re.compile(r"\btargets?\b", re.IGNORECASE)
_REMINDER = re.compile(r"\([^()]*\)")
_ANY_SEARCH = re.compile(r"\bsearch your library\b", re.IGNORECASE)
_LAND_SEARCH = re.compile(
    r"\bsearch your library for (?P<spec>[^.;:]+?) cards?"
    r"(?P<suffix> with a basic land type| that share a land type)?"
    r",?(?: reveal (?:it|them|that card|those cards),)?(?: and)? put "
    r"(?:it|them|that card|those cards) onto the battlefield",
    re.IGNORECASE,
)
_QUANTITY = re.compile(r"^(?:a|an|one|two|three|up to (?:one|two|three))\s+", re.IGNORECASE)
_TYPE_LIST = re.compile(r",\s*(?:or\s+)?|\s+or\s+")
# One searched-for card: (only basic lands, basic land types of which one must match or ``None``).
SearchAlternative = tuple[bool, frozenset[str] | None]
LAND_SEARCH_ASSUMPTION = (
    "Rechenannahme, kein Regelurteil: ein Suchland zählt in „mit Suchland“ als Quelle jeder "
    "Farbe, die ein zu seiner Suche passendes Land im Deck direkt erzeugt (passend nach "
    "Typzeile: Standard-Obertyp und Standardland-Typen, nie nach Namen), und im gemeinsamen "
    "Ereignis wie ein mehrfarbiges Land als ein Land. Angenommen wird, dass ein passendes Land "
    "noch in der Bibliothek liegt. Nicht abgebildet: getappter Eintritt, Lebenspunkte "
    "(Fetchländer), Aktivierungskosten (etwa {1} der Panoramen) und dass manche Suchländer zwei "
    "Länder holen. Ländersuche durch Zauber (Rampe) ist nicht Teil der Zählung."
)


def _front_lines(row: Mapping[str, object]) -> list[str] | None:
    """Abilities (lines) of the front face's rules text without reminder text; ``None`` when
    the card data has no rules text at all."""
    value = row.get("oracle_text")
    if value is None:
        return None
    text = str(value).split("\n//\n")[0].split(" // ")[0]
    previous = None
    while previous != text:
        previous, text = text, _REMINDER.sub("", text)
    return [" ".join(line.split()) for line in text.splitlines() if line.strip()]


def _search_alternatives(text: str) -> tuple[SearchAlternative, ...] | None:
    """The cards a land's own text searches for, or ``None`` when the text is no search of
    the library for basic lands, named basic land types or a land with a basic land type that
    puts the card onto the battlefield."""
    match = _LAND_SEARCH.search(text)
    if match is None:
        return None
    suffix = (match.group("suffix") or "").strip().lower()
    alternatives: list[SearchAlternative] = []
    for raw in re.split(r" cards? and (?:a |an )?", match.group("spec"), flags=re.IGNORECASE):
        part = _QUANTITY.sub("", raw.strip())
        basic = part.lower().startswith("basic ")
        if basic:
            part = part[len("basic ") :].strip()
        if part.lower() == "land":
            if basic:
                alternatives.append((True, None))
            elif suffix == "with a basic land type":
                alternatives.append((False, _ALL_BASIC_TYPES))
            else:
                return None
            continue
        types = [word.strip() for word in _TYPE_LIST.split(part) if word.strip()]
        if not types or any(word not in _BASIC_COLOUR for word in types):
            return None
        alternatives.append((basic, frozenset(types)))
    return tuple(alternatives) if alternatives else None


def classify_land(row: Mapping[str, object]) -> dict[str, object]:
    """Class of one land (see the module text) with the colours it produces directly and,
    for a search land, what it searches for. Reads card data and rules text, never the name."""
    direct = land_colours(row)
    if direct:
        return {"class": LAND_DIRECT, "direct": direct, "search": None, "reason": "erzeugt Farbe"}
    lines = _front_lines(row)
    if lines is None:
        return {
            "class": LAND_UNKNOWN,
            "direct": direct,
            "search": None,
            "reason": "kein Regeltext in den Kartendaten",
        }
    searching = [line for line in lines if _ANY_SEARCH.search(line)]
    readable = [
        (line, alternatives)
        for line in searching
        if (alternatives := _search_alternatives(line)) is not None
    ]
    free = [alternatives for line, alternatives in readable if not _TARGET.search(line)]
    if free:
        return {
            "class": LAND_SEARCH,
            "direct": direct,
            "search": tuple(dict.fromkeys(alt for alternatives in free for alt in alternatives)),
            "reason": "sucht Standardland bzw. Standardland-Typ",
        }
    if searching:
        return {
            "class": LAND_UNKNOWN,
            "direct": direct,
            "search": None,
            "reason": REASON_TARGETED_SEARCH if readable else REASON_UNREADABLE_SEARCH,
        }
    if direct is None:
        return {
            "class": LAND_UNKNOWN,
            "direct": None,
            "search": None,
            "reason": "keine Kartendaten zum erzeugten Mana",
        }
    return {
        "class": LAND_NO_COLOUR,
        "direct": direct,
        "search": None,
        "reason": "erzeugt laut Kartendaten kein farbiges Mana",
    }


def _type_words(type_line: str) -> tuple[frozenset[str], frozenset[str]]:
    """Supertypes/card types and subtypes of a front type line."""
    front = type_line.split(" // ")[0]
    head, _, tail = front.partition("—")
    return frozenset(head.split()), frozenset(tail.split())


def search_matches(alternatives: Sequence[SearchAlternative], type_line: str) -> bool:
    """Whether a card with this type line is one a search with ``alternatives`` may find."""
    head, subtypes = _type_words(type_line)
    if "Land" not in head:
        return False
    for basic_only, types in alternatives:
        if basic_only and "Basic" not in head:
            continue
        if types is None or subtypes & types:
            return True
    return False


def _describe_search(alternatives: Sequence[SearchAlternative]) -> str:
    parts = []
    for basic_only, types in alternatives:
        if types is None:
            parts.append("Standardland")
        elif types == _ALL_BASIC_TYPES and not basic_only:
            parts.append("Land mit Standardland-Typ")
        else:
            names = " oder ".join(sorted(types))
            parts.append(f"Standard-{names}" if basic_only else names)
    return " und ".join(parts)


def search_land_reach(
    rows: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Per land row of the main deck: its class and, for a search land, the colours the lands
    of the deck it may find produce directly (``reach``) and how many such lands there are.
    The list follows the rows; commander rows are left out."""
    lands = [
        row
        for row in rows
        if _text(row, "zone") != "commander" and "Land" in _text(row, "type_line").split(" // ")[0]
    ]
    out: list[dict[str, object]] = []
    for row in lands:
        info = classify_land(row)
        entry: dict[str, object] = {
            "card_id": _text(row, "card_id"),
            "name": _text(row, "oracle_name"),
            "quantity": int(_text(row, "quantity") or "1"),
            "class": info["class"],
            "reason": info["reason"],
            "direct": info["direct"],
            "reach": None,
            "targets": None,
            "searches_for": None,
        }
        alternatives = info["search"]
        if isinstance(alternatives, tuple):
            reach: set[str] = set()
            targets = 0
            for other in lands:
                if other is row or not search_matches(alternatives, _text(other, "type_line")):
                    continue
                colours = land_colours(other)
                targets += int(_text(other, "quantity") or "1")
                reach.update(colours or ())
            entry["reach"] = frozenset(reach)
            entry["targets"] = targets
            entry["searches_for"] = _describe_search(alternatives)
        out.append(entry)
    return out


def at_least_lands(library: int, lands: int, draws: int, minimum: int) -> Fraction | None:
    """Exact hypergeometric chance to hold at least ``minimum`` lands among ``draws`` cards
    of a ``library`` with ``lands`` lands; ``None`` when the draw does not fit the library."""
    if library <= 0 or draws > library or lands < 0 or lands > library or draws < 0:
        return None
    total = comb(library, draws)
    hits = sum(
        comb(lands, held) * comb(library - lands, draws - held)
        for held in range(max(0, minimum), min(lands, draws) + 1)
    )
    return Fraction(hits, total)


LAND_TABLE_COUNTS = tuple(range(30, 41))
LAND_TABLE_TURNS = (2, 3, 4, 5, 6, 7)


def land_count_table(library: int, deck_lands: int) -> dict[str, object]:
    """For 30 to 40 lands (and the deck's own count) in a library of ``library`` cards: the
    exact chance to hold at least ``T`` lands among the ``7 + T`` cards seen by turn ``T``."""
    counts = sorted({*LAND_TABLE_COUNTS, deck_lands}) if library > 0 else list(LAND_TABLE_COUNTS)
    rows = []
    for lands in counts:
        cells = []
        for turn in LAND_TABLE_TURNS:
            exact = at_least_lands(library, lands, draws_by_turn(turn), turn)
            cells.append(
                {
                    "turn": turn,
                    "draws": draws_by_turn(turn),
                    "p": None if exact is None else round(float(exact), 4),
                }
            )
        rows.append(
            {
                "lands": lands,
                "deck": lands == deck_lands,
                "in_range": lands in LAND_TABLE_COUNTS,
                "cells": cells,
            }
        )
    return {
        "library": library,
        "deck_lands": deck_lands,
        "turns": list(LAND_TABLE_TURNS),
        "rows": rows,
        "rule": (
            f"Bibliothek {library} Karten (Deck ohne Commander), davon die genannte Zahl Länder; "
            "bis Zug T sind 7 + T Karten gesehen (Zug 1 zieht, ohne Mulligan, ohne Extraziehen); "
            "Wert: Anteil der Ziehungen mit mindestens T Ländern, exakte Hypergeometrie. "
            "Keine Empfehlung einer Landzahl."
        ),
    }


def _joint(
    groups: Sequence[tuple[frozenset[str], int]],
    nonland: int,
    draws: int,
    min_lands: int,
    need: Mapping[str, int],
) -> tuple[int, int, int]:
    """Exact counts of draws (as numbers of card subsets of size ``draws``): all draws, draws
    with at least ``min_lands`` lands, and draws with at least ``min_lands`` lands AND, for
    every colour in ``need``, at least ``need[colour]`` drawn lands producing it.

    Dynamic programme over the land groups (lands with the same produced colours): the state
    is the number of lands drawn and, per needed colour, the sources drawn capped at the need.
    """
    colours = sorted(need)
    caps = tuple(need[c] for c in colours)
    states: dict[tuple[int, tuple[int, ...]], int] = {(0, tuple(0 for _ in colours)): 1}
    for produced, size in groups:
        nxt: dict[tuple[int, tuple[int, ...]], int] = {}
        hits = tuple(1 if c in produced else 0 for c in colours)
        for (lands, got), ways in states.items():
            for take in range(0, min(size, draws - lands) + 1):
                key = (
                    lands + take,
                    tuple(
                        min(cap, g + take * h) for cap, g, h in zip(caps, got, hits, strict=True)
                    ),
                )
                nxt[key] = nxt.get(key, 0) + ways * comb(size, take)
        states = nxt
    total = comb(sum(size for _, size in groups) + nonland, draws)
    with_lands = 0
    with_both = 0
    for (lands, got), ways in states.items():
        rest = draws - lands
        if rest < 0 or rest > nonland:
            continue
        count = ways * comb(nonland, rest)
        if lands >= min_lands:
            with_lands += count
            if got == caps:
                with_both += count
    return total, with_lands, with_both


def _share(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(float(Fraction(numerator, denominator)), 4)


def colour_probability(
    groups: Sequence[tuple[frozenset[str], int]],
    nonland: int,
    need: Mapping[str, int],
    turn: int,
) -> dict[str, object]:
    """Karsten castability of one requirement on curve (``turn``), see the module text."""
    draws = draws_by_turn(turn)
    total, with_lands, with_both = _joint(groups, nonland, draws, turn, need)
    sources = {c: sum(size for produced, size in groups if c in produced) for c in sorted(need)}
    return {
        "turn": turn,
        "draws": draws,
        "need": dict(sorted(need.items())),
        "sources": sources,
        "p_land_drops": _share(with_lands, total),
        "p_colours_given_lands": _share(with_both, with_lands),
        "p_on_curve": _share(with_both, total),
        "condition": f"bedingt auf mindestens {turn} Länder unter {draws} gezogenen Karten",
    }


def opening_hands(lands: int, early: int, other: int) -> dict[str, object]:
    """Share of 7-card opening hands with 2 to 4 lands and at least one early action (a
    nonland card of mana value at most 2), exact."""
    low, high = KEEP_LANDS
    total = comb(lands + early + other, OPENING_HAND)
    keep = 0
    for land_count in range(low, high + 1):
        rest = OPENING_HAND - land_count
        without_early = comb(other, rest)
        keep += comb(lands, land_count) * (comb(early + other, rest) - without_early)
    return {
        "hand": OPENING_HAND,
        "lands": lands,
        "early_actions": early,
        "other_cards": other,
        "rule": (
            f"{low} bis {high} Länder und mindestens eine Nicht-Land-Karte mit Manawert "
            f"höchstens {EARLY_ACTION_MAX_MV}"
        ),
        "p_keepable": _share(keep, total),
    }


HAND_EXTRA_DRAWS = (0, 1, 2, 3)


def role_in_hand(library: int, role_cards: int, draws: int) -> dict[str, object]:
    """Exact chance that a hand of ``draws`` cards from ``library`` cards holds at least one
    of ``role_cards`` role cards, and the complement (none): hypergeometric, no simulation."""
    if draws < 0 or library < draws or role_cards < 0 or role_cards > library:
        return {"draws": draws, "p_at_least_1": None, "p_none": None}
    total = comb(library, draws)
    none = comb(library - role_cards, draws)
    return {
        "draws": draws,
        "p_at_least_1": _share(total - none, total),
        "p_none": _share(none, total),
    }


def hand_roles(
    rows: Iterable[Mapping[str, object]], roles: Mapping[str, Sequence[str]]
) -> dict[str, object]:
    """Starting-hand chance per role of the deck (#1404): for each role with at least one
    card, P(at least one card of the role) in the 7-card opening hand and after 1, 2 and 3
    further cards, and P(none). ``rows`` carry ``zone``, ``quantity``, ``card_id`` and
    ``type_line``; ``roles`` maps ``card_id`` to its role tags. The library is the main deck
    without the commander. A card counts for every role it carries, roles are never added.
    A card without role data is unknown, not role-less: the figures are computed from the
    known role cards among all library cards, so they are lower bounds for the roles."""
    library = 0
    counts: Counter[str] = Counter()
    with_roles = nonland = nonland_with_roles = modal_lands = 0
    for row in rows:
        if _text(row, "zone") == "commander":
            continue
        quantity = int(_text(row, "quantity") or "1")
        library += quantity
        tags = set(roles.get(_text(row, "card_id"), ()))
        faces = _text(row, "type_line").split(" // ")
        is_land = "Land" in faces[0]
        if not is_land:
            nonland += quantity
            # The front face decides; a land back face is only named, it never changes a figure.
            if any("Land" in back for back in faces[1:]):
                modal_lands += quantity
        if tags:
            with_roles += quantity
            if not is_land:
                nonland_with_roles += quantity
            for tag in tags:
                counts[tag] += quantity
    items = [
        {
            "role": role,
            "cards": cards,
            "of": library,
            "hands": [
                {"extra": extra, **role_in_hand(library, cards, OPENING_HAND + extra)}
                for extra in HAND_EXTRA_DRAWS
            ],
        }
        for role, cards in sorted(counts.items())
    ]
    return {
        "hand": OPENING_HAND,
        "library": library,
        "cards_with_role_data": with_roles,
        "nonland_cards": nonland,
        "nonland_with_role_data": nonland_with_roles,
        "modal_land_cards": modal_lands,
        "roles_known": bool(counts),
        "roles": items,
        "assumption": (
            f"Starthand {OPENING_HAND} Karten ohne Mulligan; danach 1, 2 und 3 weitere Karten "
            "(Zug 1 bis 3 gezogen, Zug 1 zieht; der Startspieler zieht in Zug 1 nicht: für "
            "ihn gilt die Spalte einen Zug früher). Nenner: Karten im Deck ohne Commander. "
            "Eine Karte zählt für jede ihrer Rollen, Rollen werden nie addiert. Karten ohne "
            "Rollendaten sind unbekannt, nicht rollenlos: die Werte sind Untergrenzen. "
            "Die Vorderseite entscheidet, ob eine Karte als Land zählt: eine Karte mit "
            "Land-Rückseite („Modal-Land“) zählt als Nichtland; die Wahrscheinlichkeiten "
            "ändern sich dadurch nicht."
        ),
    }


def _letters(value: object) -> list[str]:
    return [c for c in COLOURS if isinstance(value, frozenset) and c in value]


def _sorted_groups(groups: Counter[frozenset[str]]) -> list[tuple[frozenset[str], int]]:
    return sorted(groups.items(), key=lambda item: ("".join(sorted(item[0])), item[1]))


def _with_search(
    search_groups: Sequence[tuple[frozenset[str], int]],
    nonland: int,
    need: Mapping[str, int],
    turn: int,
) -> dict[str, object]:
    result = colour_probability(search_groups, nonland, need, turn)
    return {
        "sources": result["sources"],
        "p_colours_given_lands": result["p_colours_given_lands"],
        "p_on_curve": result["p_on_curve"],
    }


def _commander_entries(
    commanders: Sequence[Mapping[str, object]],
    land_groups: Sequence[tuple[frozenset[str], int]],
    search_groups: Sequence[tuple[frozenset[str], int]],
    nonland: int,
) -> list[dict[str, object]]:
    """The commander's own cost as a requirement on curve from the command zone (WP-3)."""
    out: list[dict[str, object]] = []
    for row in commanders:
        base: dict[str, object] = {
            "card_id": _text(row, "card_id"),
            "name": _text(row, "oracle_name"),
            "mana_cost": _text(row, "mana_cost"),
        }
        value = row.get("mana_value")
        if value is None:
            out.append({**base, "known": False, "reason": "Manawert unbekannt"})
            continue
        need, skipped = requirement(_text(row, "mana_cost"))
        turn = max(1, int(float(str(value))))
        result = colour_probability(land_groups, nonland, need, turn)
        out.append(
            {
                **base,
                "known": True,
                **result,
                "label": "".join(colour * count for colour, count in sorted(need.items())),
                "hybrid_or_phyrexian": skipped,
                "with_search": _with_search(search_groups, nonland, need, turn),
            }
        )
    return out


def deck_castability(rows: Iterable[Mapping[str, object]]) -> dict[str, object]:
    """Castability of every distinct coloured requirement of the deck's nonland cards, plus
    the opening hand figure. ``rows`` carry ``zone``, ``quantity``, ``oracle_name``,
    ``card_id``, ``type_line``, ``mana_cost``, ``mana_value``, ``produced_mana`` and
    ``oracle_text``. Each requirement and the commander are given ``direkt`` (the top-level
    fields) and ``mit Suchland`` (``with_search``)."""
    row_list = list(rows)
    groups: Counter[frozenset[str]] = Counter()
    search_counter: Counter[frozenset[str]] = Counter()
    unknown_lands = 0
    no_colour_lands = 0
    lands = early = other = 0
    unknown_mv = 0
    requirements: dict[tuple[int, tuple[tuple[str, int], ...]], list[dict[str, object]]] = {}
    hybrid_cards: list[str] = []
    classes = search_land_reach(row_list)
    class_counts: Counter[str] = Counter()
    for entry in classes:
        quantity = int(str(entry["quantity"]))
        class_counts[str(entry["class"])] += quantity
        reach = entry["reach"]
        direct = entry["direct"]
        if isinstance(reach, frozenset):
            search_counter[reach] += quantity
        elif isinstance(direct, frozenset):
            search_counter[direct] += quantity
        else:
            search_counter[frozenset()] += quantity
    commanders = [row for row in row_list if _text(row, "zone") == "commander"]
    for row in row_list:
        if _text(row, "zone") == "commander":
            continue
        quantity = int(_text(row, "quantity") or "1")
        front_type = _text(row, "type_line").split(" // ")[0]
        if "Land" in front_type:
            lands += quantity
            colours = land_colours(row)
            if colours is None:
                unknown_lands += quantity
                groups[frozenset()] += quantity
            else:
                if not colours:
                    no_colour_lands += quantity
                groups[colours] += quantity
            continue
        value = row.get("mana_value")
        if value is None:
            unknown_mv += quantity
            other += quantity
            continue
        mana_value = float(str(value))
        if mana_value <= EARLY_ACTION_MAX_MV:
            early += quantity
        else:
            other += quantity
        need, skipped = requirement(_text(row, "mana_cost"))
        if skipped:
            hybrid_cards.append(_text(row, "oracle_name"))
        if not need:
            continue
        turn = max(1, int(mana_value))
        key = (turn, tuple(sorted(need.items())))
        requirements.setdefault(key, []).append(
            {"card_id": _text(row, "card_id"), "name": _text(row, "oracle_name")}
        )
    nonland = early + other
    land_groups = _sorted_groups(groups)
    search_groups = _sorted_groups(search_counter)
    items = []
    for (turn, need_items), cards in sorted(requirements.items()):
        result = colour_probability(land_groups, nonland, dict(need_items), turn)
        items.append(
            {
                **result,
                "label": "".join(colour * count for colour, count in need_items),
                "cards": sorted(cards, key=lambda card: str(card["name"])),
                "with_search": _with_search(search_groups, nonland, dict(need_items), turn),
            }
        )
    search_lands = [
        {
            "card_id": entry["card_id"],
            "name": entry["name"],
            "quantity": entry["quantity"],
            "searches_for": entry["searches_for"],
            "reach": _letters(entry["reach"]),
            "targets": entry["targets"],
        }
        for entry in classes
        if entry["class"] == LAND_SEARCH
    ]
    unknown_class = [
        {"card_id": entry["card_id"], "name": entry["name"], "reason": entry["reason"]}
        for entry in classes
        if entry["class"] == LAND_UNKNOWN
    ]
    return {
        "schema": SCHEMA,
        "data_class": "DERIVED_DESCRIPTIVE",
        "main_cards": lands + nonland,
        "lands": lands,
        "land_sources": {
            colour: sum(size for produced, size in land_groups if colour in produced)
            for colour in COLOURS
        },
        "lands_unknown_colours": unknown_lands,
        "lands_without_coloured_mana": no_colour_lands,
        "cards_unknown_mana_value": unknown_mv,
        "hybrid_or_phyrexian_cards": sorted(hybrid_cards),
        "requirements": items,
        "land_sources_with_search": {
            colour: sum(size for produced, size in search_groups if colour in produced)
            for colour in COLOURS
        },
        "land_classes": {
            "counts": {name: class_counts[name] for name in LAND_CLASSES},
            "classified": lands - class_counts[LAND_UNKNOWN],
            "of": lands,
            "search_lands": search_lands,
            "unknown": unknown_class,
            "assumption": LAND_SEARCH_ASSUMPTION,
            "origin": (
                "Klasse aus Kartendaten (erzeugtes Mana, Typzeile) und Regeltext der "
                "Vorderseite ohne Erinnerungstext; nie aus dem Kartennamen"
            ),
        },
        "commander": _commander_entries(commanders, land_groups, search_groups, nonland),
        "land_count_table": land_count_table(lands + nonland, lands),
        "opening_hand": opening_hands(lands, early, other),
        "method": (
            "Exakte multivariate Hypergeometrie nach Karsten (2022): Farbwahrscheinlichkeit "
            "bedingt auf die Land-Drops bis zum Zug des Manawerts; Landmangel getrennt; "
            "mehrere Symbole einer Farbe und mehrere Farben als ein gemeinsames Ereignis. "
            "Ziehen: 7 + Zug Karten, ohne Mulligan und ohne Extraziehen. Quellen: nur Länder; "
            "„direkt“ ohne Suchländer, „mit Suchland“ unter der genannten Rechenannahme."
        ),
        "source": (
            "https://www.tcgplayer.com/content/article/How-Many-Sources-Do-You-Need-to-"
            "Consistently-Cast-Your-Spells-A-2022-Update/dc23a7d2-0a16-4c0b-ad36-586fcca03ad8"
        ),
    }


SAMPLE_HAND_SCHEMA = "studio-sample-hand-1"


def draw_sample_hand(
    rows: Iterable[Mapping[str, object]],
    *,
    seed: int = 1,
    mulligans: int = 0,
    draw_steps: int = 0,
    bottom_indices: Sequence[int] = (),
) -> dict[str, object]:
    """Deterministic seeded 7-card sample opening hand and London Mulligan simulator (#1404)."""
    import random

    clamped_mulligans = max(0, min(int(mulligans), OPENING_HAND))
    clamped_draws = max(0, min(int(draw_steps), 10))
    keyed_cards: list[tuple[str, int, dict[str, object]]] = []
    for row in rows:
        if _text(row, "zone") == "commander":
            continue
        quantity = max(0, int(_text(row, "quantity") or "1"))
        is_land = "Land" in _text(row, "type_line").split(" // ")[0]
        colours_set = land_colours(row) if is_land else frozenset()
        raw_mv = row.get("mana_value")
        mv = float(str(raw_mv)) if raw_mv is not None else None
        need_map, _ = requirement(_text(row, "mana_cost")) if not is_land else ({}, False)
        cid = _text(row, "card_id")
        base_card: dict[str, object] = {
            "card_id": cid,
            "name": _text(row, "oracle_name") or cid,
            "type_line": _text(row, "type_line"),
            "mana_cost": _text(row, "mana_cost"),
            "mana_value": mv,
            "is_land": is_land,
            "produced_colours": sorted(colours_set) if colours_set else [],
            "need": dict(sorted(need_map.items())),
        }
        for copy_idx in range(quantity):
            keyed_cards.append((cid, copy_idx, dict(base_card)))
    keyed_cards.sort(key=lambda item: (item[0], item[1]))
    library_cards = [item[2] for item in keyed_cards]

    rng = random.Random(int(seed))
    deck_copy = list(library_cards)
    for _ in range(clamped_mulligans + 1):
        deck_copy = list(library_cards)
        rng.shuffle(deck_copy)

    hand_slice = deck_copy[:OPENING_HAND]
    extra_slice = deck_copy[OPENING_HAND : OPENING_HAND + clamped_draws]
    valid_bottom = sorted({int(i) for i in bottom_indices if 0 <= int(i) < len(hand_slice)})
    bottom_set = set(valid_bottom)

    kept_lands = 0
    kept_sources: Counter[str] = Counter()
    for idx, card in enumerate(hand_slice):
        if idx not in bottom_set and card["is_land"]:
            kept_lands += 1
            for c in card["produced_colours"]:  # type: ignore[attr-defined]
                kept_sources[str(c)] += 1

    def _can_cast(
        card: Mapping[str, object], lands_avail: int, sources_avail: Mapping[str, int]
    ) -> bool | None:
        if card["is_land"] or card["mana_value"] is None:
            return None
        if lands_avail < int(float(str(card["mana_value"]))):
            return False
        need_dict = card["need"]
        return isinstance(need_dict, Mapping) and all(
            int(sources_avail.get(str(col), 0)) >= int(cnt) for col, cnt in need_dict.items()
        )

    hand_out: list[dict[str, object]] = []
    kept_out: list[dict[str, object]] = []
    early_kept = castable_kept = nonland_kept = 0
    for idx, card in enumerate(hand_slice):
        bottomed = idx in bottom_set
        castable = _can_cast(card, kept_lands, kept_sources)
        item = {
            **card,
            "index": idx,
            "bottomed": bottomed,
            "castable_from_kept_lands": castable,
        }
        hand_out.append(item)
        if not bottomed:
            kept_out.append(item)
            if not card["is_land"]:
                nonland_kept += 1
                mv_val = card["mana_value"]
                if mv_val is not None and float(str(mv_val)) <= EARLY_ACTION_MAX_MV:
                    early_kept += 1
                if castable is True:
                    castable_kept += 1

    running_lands = kept_lands
    running_sources: Counter[str] = Counter(kept_sources)
    extra_out: list[dict[str, object]] = []
    for step_idx, card in enumerate(extra_slice, start=1):
        if card["is_land"]:
            running_lands += 1
            for c in card["produced_colours"]:  # type: ignore[attr-defined]
                running_sources[str(c)] += 1
        extra_out.append(
            {
                **card,
                "turn_drawn": step_idx,
                "castable_by_turn_drawn": _can_cast(card, running_lands, running_sources),
            }
        )

    return {
        "schema": SAMPLE_HAND_SCHEMA,
        "data_class": "HEURISTIC_MODEL",
        "seed": int(seed),
        "mulligans": clamped_mulligans,
        "bottom_required": max(0, clamped_mulligans - 1),
        "bottom_indices": valid_bottom,
        "draw_steps": clamped_draws,
        "library_size": len(library_cards),
        "hand": hand_out,
        "kept_hand": kept_out,
        "extra_draws": extra_out,
        "summary": {
            "kept_cards": len(kept_out),
            "lands_in_kept": kept_lands,
            "nonlands_in_kept": nonland_kept,
            "early_actions_in_kept": early_kept,
            "castable_nonlands_in_kept": castable_kept,
            "kept_land_sources": {c: int(kept_sources.get(c, 0)) for c in COLOURS},
        },
        "assumption": (
            "Deterministische Beispielhand (London-Mulligan mit freiem erstem Commander-Mulligan; "
            "Zufalls-Seed explizit; Quellenprüfung nur über gezogene Länder)."
        ),
    }
