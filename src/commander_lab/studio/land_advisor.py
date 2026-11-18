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

from . import cache
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


def _colour_rows(
    identity: set[str],
    pips: Counter[str],
    land_sources: Counter[str],
    other_sources: Counter[str],
    modal_sources: Counter[str],
) -> tuple[int, list[dict[str, object]]]:
    """The total of coloured pips and the per-colour entries of one deck's figures."""
    total = sum(pips.values())
    shown = [c for c in COLOURS if c in identity or pips[c] or land_sources[c]]
    return total, [
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


def deck_profile(rows: Iterable[_Row]) -> dict[str, object]:
    """The figures of one deck. ``rows`` carry ``zone``, ``quantity``, ``type_line``,
    ``mana_cost``, ``produced_mana``, ``layout`` and, for commanders, ``color_identity``."""
    row_list = list(rows)
    identity: set[str] = set()
    for row in row_list:
        if _text(row, "zone") == "commander":
            identity.update(letter for letter in _text(row, "color_identity") if letter in COLOURS)
    pips: Counter[str] = Counter()
    commander_pips: Counter[str] = Counter()
    land_sources: Counter[str] = Counter()
    other_sources: Counter[str] = Counter()
    modal_sources: Counter[str] = Counter()
    lands = nonland = modal_backs = unknown_lands = colourless_pips = colourless_lands = 0
    no_mana_lands = 0
    for row in row_list:
        quantity = int(_text(row, "quantity") or "1")
        type_line = _text(row, "type_line")
        front_type = _front(type_line)
        if _text(row, "zone") == "commander":
            commander_pips.update(_pips(row)[0])
            continue
        if "Land" in front_type:
            lands += quantity
            colours, known = _produced(row, front_type)
            if not known:
                unknown_lands += quantity
            for colour in colours:
                if not identity or colour in identity:
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
                if not identity or colour in identity:
                    modal_sources[colour] += quantity
        else:
            for colour in {c for c in _text(row, "produced_mana") if c in COLOURS}:
                if not identity or colour in identity:
                    other_sources[colour] += quantity
    total, colours_out = _colour_rows(identity, pips, land_sources, other_sources, modal_sources)
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
    left out and counted.

    Remembered per store state and commander (``cache.py``, read-only result)."""
    if not commander_names:
        return []
    return cache.cached(
        store,
        ("land_source_groups", tuple(commander_names)),
        lambda: _source_deck_groups_uncached(store, commander_names),
    )


class _CardTraits:
    """What one distinct card row contributes to a source deck's figures, read once."""

    __slots__ = ("colours", "kind", "pips")

    def __init__(self, kind: int, colours: frozenset[str], pips: tuple[tuple[str, int], ...]):
        self.kind = kind  # 0 land, 1 spell with a land back, 2 other spell
        self.colours = colours  # land sources / modal sources / other sources
        self.pips = pips


def _card_traits(
    type_line: object, mana_cost: object, produced: object, layout: object
) -> _CardTraits:
    """The same reading as ``deck_profile`` gives a deck's card without a zone (a source
    deck has no commander row, so the identity is empty and every colour counts)."""
    # The raw values go in: a NULL produced_mana (no card data) is not an empty one.
    row = {
        "type_line": type_line,
        "mana_cost": mana_cost,
        "produced_mana": produced,
        "layout": layout,
    }
    type_line = _text(row, "type_line")
    front_type = _front(type_line)
    if "Land" in front_type:
        return _CardTraits(0, frozenset(_produced(row, front_type)[0]), ())
    pips = tuple(_pips(row)[0].items())
    if " // " in type_line and "Land" in type_line.split(" // ", 1)[1]:
        return _CardTraits(1, frozenset(_produced(row, "")[0]), pips)
    return _CardTraits(2, frozenset(c for c in _text(row, "produced_mana") if c in COLOURS), pips)


def _source_deck_groups_uncached(
    store: StudioStore, commander_names: Sequence[str]
) -> list[dict[str, object]]:
    from . import builder

    members = builder.cohort_members(store, commander_names)
    if not members:
        return []
    # Only complete decks enter a group's figures; the others are counted, not read.
    complete_ids = sorted(
        {
            str(row["deck_id"])
            for group in members.values()
            for row in group
            if row["resolved"] == row["cards"]
        }
    )
    # The card data is read once per card (a card is in thousands of decks), the deck rows
    # without a join; a card without card data is left out, as the inner join did.
    traits: dict[str, _CardTraits] = {}
    shared: dict[tuple[object, object, object, object], _CardTraits] = {}
    for oracle_id, type_line, mana_cost, produced, layout in store.connection.execute(
        "SELECT oracle_id, type_line, mana_cost, produced_mana, layout FROM scryfall_card"
    ):
        key = (type_line, mana_cost, produced, layout)
        trait = shared.get(key)
        if trait is None:
            trait = shared[key] = _card_traits(type_line, mana_cost, produced, layout)
        traits[oracle_id] = trait
    totals: dict[str, tuple[list[int], Counter[str], Counter[str], Counter[str], Counter[str]]] = {
        deck_id: ([0], Counter(), Counter(), Counter(), Counter()) for deck_id in complete_ids
    }
    for start in range(0, len(complete_ids), _CHUNK):
        chunk = complete_ids[start : start + _CHUNK]
        marks = ", ".join("?" for _ in chunk)
        query = (
            "SELECT k.deck_id, k.quantity, k.oracle_id FROM corpus_deck_card k "
            f"WHERE k.deck_id IN ({marks}) AND LOWER(k.section) IN ('main', 'mainboard')"
        )
        for deck_id, quantity, oracle_id in store.connection.execute(query, chunk):
            trait = traits.get(oracle_id)
            if trait is None:
                continue
            lands, pips, land_sources, other_sources, modal_sources = totals[deck_id]
            amount = int(quantity if quantity is not None else 1)
            if trait.kind == 0:
                lands[0] += amount
                for colour in trait.colours:
                    land_sources[colour] += amount
            else:
                for colour, count in trait.pips:
                    pips[colour] += count * amount
                target = modal_sources if trait.kind == 1 else other_sources
                for colour in trait.colours:
                    target[colour] += amount
    compact: dict[str, dict[str, object]] = {}
    for deck_id, (lands, pips, land_sources, other_sources, modal_sources) in totals.items():
        _, colours = _colour_rows(set(), pips, land_sources, other_sources, modal_sources)
        compact[deck_id] = {
            "lands": lands[0],
            "colours": {str(entry["colour"]): entry for entry in colours},
        }
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

    from .decks import color_set

    keyed: list[tuple[int, float, str, dict[str, object]]] = []
    for row in store.connection.execute(
        "SELECT c.card_id, c.oracle_name, c.color_identity, c.type_line, "
        "c.is_basic_land, c.layout, c.produced_mana, i.available_lower_bound "
        "FROM card_fact c JOIN inventory i USING (card_id) "
        "WHERE c.commander_legal = 1 ORDER BY c.oracle_name"
    ):
        if not color_set(row["color_identity"]) <= identity:
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
        if of > 0:
            hits_int = int(hits.get(name, {}).get(cohort, 0))
            share_float = round(hits_int / of, 4)
            if share_float < min_share:
                continue
            decks_val: int | None = hits_int
            share_val: float | None = share_float
            sort_key = (0, -share_float, name)
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


LAND_CYCLES_SCHEMA = "studio-land-cycles-1"

LAND_CYCLES: tuple[dict[str, object], ...] = (
    {
        "key": "fetch",
        "label": "Fetchländer",
        "description": "Zweifarbige Suchländer für Standardland-Typen",
        "cards": (
            ("Flooded Strand", ("W", "U")),
            ("Polluted Delta", ("U", "B")),
            ("Bloodstained Mire", ("B", "R")),
            ("Wooded Foothills", ("R", "G")),
            ("Windswept Heath", ("G", "W")),
            ("Marsh Flats", ("W", "B")),
            ("Scalding Tarn", ("U", "R")),
            ("Verdant Catacombs", ("B", "G")),
            ("Arid Mesa", ("R", "W")),
            ("Misty Rainforest", ("G", "U")),
        ),
    },
    {
        "key": "shock",
        "label": "Shockländer",
        "description": "Zweifarbige Länder mit zwei Standardland-Typen (2 Lebenspunkte für ungetappt)",
        "cards": (
            ("Hallowed Fountain", ("W", "U")),
            ("Watery Grave", ("U", "B")),
            ("Blood Crypt", ("B", "R")),
            ("Stomping Ground", ("R", "G")),
            ("Temple Garden", ("G", "W")),
            ("Godless Shrine", ("W", "B")),
            ("Steam Vents", ("U", "R")),
            ("Overgrown Tomb", ("B", "G")),
            ("Sacred Foundry", ("R", "W")),
            ("Breeding Pool", ("G", "U")),
        ),
    },
    {
        "key": "original_dual",
        "label": "ABUR-Dualländer",
        "description": "Klassische zweifarbige Länder mit zwei Standardland-Typen ohne Nachteil",
        "cards": (
            ("Tundra", ("W", "U")),
            ("Underground Sea", ("U", "B")),
            ("Badlands", ("B", "R")),
            ("Taiga", ("R", "G")),
            ("Savannah", ("G", "W")),
            ("Scrubland", ("W", "B")),
            ("Volcanic Island", ("U", "R")),
            ("Bayou", ("B", "G")),
            ("Plateau", ("R", "W")),
            ("Tropical Island", ("G", "U")),
        ),
    },
    {
        "key": "crowd",
        "label": "Battlebond-/Zuschauerländer",
        "description": "Zweifarbige Länder, die ab zwei oder mehr Gegnern ungetappt ins Spiel kommen",
        "cards": (
            ("Sea of Clouds", ("W", "U")),
            ("Morphic Pool", ("U", "B")),
            ("Luxury Suite", ("B", "R")),
            ("Spire Garden", ("R", "G")),
            ("Bountiful Promenade", ("G", "W")),
            ("Vault of Champions", ("W", "B")),
            ("Training Center", ("U", "R")),
            ("Undergrowth Stadium", ("B", "G")),
            ("Spectator Seating", ("R", "W")),
            ("Rejuvenating Springs", ("G", "U")),
        ),
    },
    {
        "key": "slow",
        "label": "Slowländer",
        "description": "Zweifarbige Länder, die ab zwei anderen Ländern ungetappt ins Spiel kommen",
        "cards": (
            ("Deserted Beach", ("W", "U")),
            ("Shipwreck Marsh", ("U", "B")),
            ("Haunted Ridge", ("B", "R")),
            ("Rockfall Vale", ("R", "G")),
            ("Overgrown Farmland", ("G", "W")),
            ("Shattered Sanctum", ("W", "B")),
            ("Stormcarved Coast", ("U", "R")),
            ("Deathcap Glade", ("B", "G")),
            ("Sundown Pass", ("R", "W")),
            ("Dreamroot Cascade", ("G", "U")),
        ),
    },
    {
        "key": "fast",
        "label": "Fastländer",
        "description": "Zweifarbige Länder, die bei höchstens zwei anderen Ländern ungetappt ins Spiel kommen",
        "cards": (
            ("Seachrome Coast", ("W", "U")),
            ("Darkslick Shores", ("U", "B")),
            ("Blackcleave Cliffs", ("B", "R")),
            ("Copperline Gorge", ("R", "G")),
            ("Razorverge Thicket", ("G", "W")),
            ("Concealed Courtyard", ("W", "B")),
            ("Spirebluff Canal", ("U", "R")),
            ("Blooming Marsh", ("B", "G")),
            ("Inspiring Vantage", ("R", "W")),
            ("Botanical Sanctum", ("G", "U")),
        ),
    },
    {
        "key": "pain",
        "label": "Painländer",
        "description": "Zweifarbige Länder für farbloses Mana oder farbiges Mana gegen 1 Lebenspunkt",
        "cards": (
            ("Adarkar Wastes", ("W", "U")),
            ("Underground River", ("U", "B")),
            ("Sulfurous Springs", ("B", "R")),
            ("Karplusan Forest", ("R", "G")),
            ("Brushland", ("G", "W")),
            ("Caves of Koilos", ("W", "B")),
            ("Shivan Reef", ("U", "R")),
            ("Llanowar Wastes", ("B", "G")),
            ("Battlefield Forge", ("R", "W")),
            ("Yavimaya Coast", ("G", "U")),
        ),
    },
    {
        "key": "check",
        "label": "Checkländer",
        "description": "Zweifarbige Länder, die bei passendem Standardland-Typ ungetappt ins Spiel kommen",
        "cards": (
            ("Glacial Fortress", ("W", "U")),
            ("Drowned Catacomb", ("U", "B")),
            ("Dragonskull Summit", ("B", "R")),
            ("Rootbound Crag", ("R", "G")),
            ("Sunpetal Grove", ("G", "W")),
            ("Isolated Chapel", ("W", "B")),
            ("Sulfur Falls", ("U", "R")),
            ("Woodland Cemetery", ("B", "G")),
            ("Clifftop Retreat", ("R", "W")),
            ("Hinterland Harbor", ("G", "U")),
        ),
    },
    {
        "key": "filter",
        "label": "Filterländer (Shadowmoor/Eventide)",
        "description": "Zweifarbige Hybrid-Filterländer",
        "cards": (
            ("Mystic Gate", ("W", "U")),
            ("Sunken Ruins", ("U", "B")),
            ("Graven Cairns", ("B", "R")),
            ("Fire-Lit Thicket", ("R", "G")),
            ("Wooded Bastion", ("G", "W")),
            ("Fetid Heath", ("W", "B")),
            ("Cascade Bluffs", ("U", "R")),
            ("Twilight Mire", ("B", "G")),
            ("Rugged Prairie", ("R", "W")),
            ("Flooded Grove", ("G", "U")),
        ),
    },
    {
        "key": "pathway",
        "label": "Pathway-Länder (MDFC)",
        "description": "Modale doppelseitige Einzelfarbländer",
        "cards": (
            ("Hengegate Pathway // Mistgate Pathway", ("W", "U")),
            ("Clearwater Pathway // Murkwater Pathway", ("U", "B")),
            ("Blightstep Pathway // Searstep Pathway", ("B", "R")),
            ("Cragcrown Pathway // Timbercrown Pathway", ("R", "G")),
            ("Branchloft Pathway // Boulderloft Pathway", ("G", "W")),
            ("Brightclimb Pathway // Grimclimb Pathway", ("W", "B")),
            ("Riverglide Pathway // Lavaglide Pathway", ("U", "R")),
            ("Darkbore Pathway // Slitherbore Pathway", ("B", "G")),
            ("Needleverge Pathway // Pillarverge Pathway", ("R", "W")),
            ("Barkchannel Pathway // Tidechannel Pathway", ("G", "U")),
        ),
    },
    {
        "key": "horizon",
        "label": "Horizon-Länder",
        "description": "Zweifarbige Länder mit Lebenspunkt-Bezahlung und Kartenzieh-Opferfähigkeit",
        "cards": (
            ("Horizon Canopy", ("G", "W")),
            ("Silent Clearing", ("W", "B")),
            ("Fiery Islet", ("U", "R")),
            ("Nurturing Peatland", ("B", "G")),
            ("Sunbaked Canyon", ("R", "W")),
            ("Waterlogged Grove", ("G", "U")),
        ),
    },
    {
        "key": "surveil",
        "label": "Surveil-Länder",
        "description": "Zweifarbige Länder mit zwei Standardland-Typen und Überwachen 1 beim Eintritt",
        "cards": (
            ("Meticulous Archive", ("W", "U")),
            ("Undercity Sewers", ("U", "B")),
            ("Raucous Theater", ("B", "R")),
            ("Commercial District", ("R", "G")),
            ("Lush Portico", ("G", "W")),
            ("Shadowy Backstreet", ("W", "B")),
            ("Thundering Falls", ("U", "R")),
            ("Underground Mortuary", ("B", "G")),
            ("Elegant Parlor", ("R", "W")),
            ("Hedge Maze", ("G", "U")),
        ),
    },
    {
        "key": "triome",
        "label": "Triome / Dreifarbländer",
        "description": "Dreifarbige Länder mit drei Standardland-Typen und Umwandlung (Ikoria & New Capenna)",
        "cards": (
            ("Raugrin Triome", ("U", "R", "W")),
            ("Zagoth Triome", ("B", "G", "U")),
            ("Indatha Triome", ("W", "B", "G")),
            ("Ketria Triome", ("G", "U", "R")),
            ("Savai Triome", ("R", "W", "B")),
            ("Raffine's Tower", ("W", "U", "B")),
            ("Xander's Lounge", ("U", "B", "R")),
            ("Ziatora's Proving Ground", ("B", "R", "G")),
            ("Jetmir's Garden", ("R", "G", "W")),
            ("Spara's Headquarters", ("G", "W", "U")),
        ),
    },
    {
        "key": "verge",
        "label": "Verge-Länder",
        "description": "Zweifarbige Länder mit einer Grundfarbe und bedingter Zweitfarbe über Standardland-Typen",
        "cards": (
            ("Floodfarm Verge", ("W", "U")),
            ("Gloomlake Verge", ("U", "B")),
            ("Blazemire Verge", ("B", "R")),
            ("Thornspire Verge", ("R", "G")),
            ("Hushwood Verge", ("G", "W")),
            ("Bleachbone Verge", ("W", "B")),
            ("Riverpyre Verge", ("U", "R")),
            ("Wastewood Verge", ("B", "G")),
            ("Sunbillow Verge", ("R", "W")),
            ("Willowrush Verge", ("G", "U")),
        ),
    },
)


def land_cycles_summary(store: StudioStore, rows: Iterable[_Row]) -> dict[str, object]:
    """Descriptive completeness of the pinned ``LAND_CYCLES`` in the deck and collection pool
    (#1452).

    Every count carries its explicit denominator (``total``, the cycle cards within the
    commander's colour identity, or all cycle cards when no commander colour identity is
    present). Holds no recommendation, upgrade or purchase language.
    """
    row_list = list(rows)
    has_commander = False
    identity: set[str] = set()
    in_deck_names: set[str] = set()
    in_deck_ids: set[str] = set()
    for row in row_list:
        zone = _text(row, "zone")
        if zone == "commander":
            has_commander = True
            identity.update(letter for letter in _text(row, "color_identity") if letter in COLOURS)
        qty = int(_text(row, "quantity") or "1")
        if zone in ("main", "commander", "") and qty > 0:
            name = _text(row, "oracle_name")
            if name:
                in_deck_names.add(name.casefold())
                in_deck_names.add(_front(name).casefold())
            cid = _text(row, "card_id")
            if cid:
                in_deck_ids.add(cid)

    pool_by_name: dict[str, dict[str, object]] = {}
    for db_row in store.connection.execute(
        "SELECT c.card_id, c.oracle_name, i.owned_lower_bound, i.available_lower_bound "
        "FROM card_fact c JOIN inventory i USING (card_id) "
        "WHERE c.commander_legal = 1 ORDER BY c.oracle_name"
    ):
        cid = str(db_row["card_id"])
        oname = str(db_row["oracle_name"])
        entry: dict[str, object] = {
            "card_id": cid,
            "oracle_name": oname,
            "total_owned": int(db_row["owned_lower_bound"] or 0),
            "available": int(db_row["available_lower_bound"] or 0),
        }
        pool_by_name[oname.casefold()] = entry
        front_key = _front(oname).casefold()
        if front_key not in pool_by_name:
            pool_by_name[front_key] = entry

    cycles_out: list[dict[str, object]] = []
    legal_lands_total = 0
    in_deck_total = 0
    in_pool_extra_total = 0
    in_pool_total = 0

    for cycle in LAND_CYCLES:
        raw_cards = cycle["cards"]
        if not isinstance(raw_cards, tuple):
            raise TypeError("LAND_CYCLES cards must be a tuple")
        legal_cards = [
            (str(name), tuple(str(c) for c in colours))
            for name, colours in raw_cards
            if (not has_commander and not identity) or set(colours) <= identity
        ]
        total = len(legal_cards)
        card_entries: list[dict[str, object]] = []
        for card_name, colours in legal_cards:
            key_full = card_name.casefold()
            key_front = _front(card_name).casefold()
            pool_entry = pool_by_name.get(key_full) or pool_by_name.get(key_front)
            pool_card_id: str | None = (
                str(pool_entry["card_id"]) if pool_entry is not None else None
            )
            avail = int(str(pool_entry["available"])) if pool_entry is not None else 0
            owned_qty = int(str(pool_entry["total_owned"])) if pool_entry is not None else 0
            is_in_deck = (
                key_full in in_deck_names
                or key_front in in_deck_names
                or (pool_card_id is not None and pool_card_id in in_deck_ids)
            )
            owned = pool_entry is not None and (owned_qty > 0 or avail > 0)
            is_in_pool = bool(owned or is_in_deck)
            is_extra_in_pool = bool(not is_in_deck and avail > 0)
            if is_in_deck:
                status = "im Deck"
            elif avail > 0:
                status = "im Pool (frei)"
            elif owned:
                status = "im Pool (0 frei)"
            else:
                status = "nicht in Sammlung"
            card_entries.append(
                {
                    "name": card_name,
                    "card_id": pool_card_id,
                    "colours": [c for c in COLOURS if c in colours],
                    "in_deck": is_in_deck,
                    "in_pool": is_in_pool,
                    "in_pool_extra": is_extra_in_pool,
                    "available": avail,
                    "status": status,
                }
            )
        in_deck_count = sum(1 for c in card_entries if c["in_deck"])
        in_pool_extra_count = sum(1 for c in card_entries if c["in_pool_extra"])
        in_pool_count = sum(1 for c in card_entries if c["in_pool"])
        summary = (
            f"{in_deck_count} / {total} im Deck, {in_pool_extra_count} weitere von {total} im Pool"
            if total > 0
            else "0 / 0 in Farbidentität"
        )
        legal_lands_total += total
        in_deck_total += in_deck_count
        in_pool_extra_total += in_pool_extra_count
        in_pool_total += in_pool_count
        cycles_out.append(
            {
                "key": str(cycle["key"]),
                "label": str(cycle["label"]),
                "description": str(cycle["description"]),
                "cycle_size": len(raw_cards),
                "total": total,
                "in_deck": in_deck_count,
                "in_pool_extra": in_pool_extra_count,
                "in_pool_total": in_pool_count,
                "summary": summary,
                "cards": card_entries,
            }
        )

    return {
        "schema": LAND_CYCLES_SCHEMA,
        "data_class": "derived_descriptive",
        "has_commander": has_commander,
        "identity": [c for c in COLOURS if c in identity],
        "cycles_total": len(LAND_CYCLES),
        "legal_lands_total": legal_lands_total,
        "in_deck_total": in_deck_total,
        "in_pool_extra_total": in_pool_extra_total,
        "in_pool_total": in_pool_total,
        "cycles": cycles_out,
    }
