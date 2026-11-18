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
data, else the basic land type); lands that produce no coloured mana per the card data
(fetch lands, colourless lands) count as lands but not as sources, and lands without card data
count as lands with unknown colours. Hybrid and Phyrexian symbols are not part of the
requirement (reported per card). Draws by turn ``T``: 7 + ``T`` cards (in multiplayer only the
starting player skips the first draw), no mulligan, no extra card draw. Exact multivariate
hypergeometric arithmetic, no Monte Carlo. The result is a description, never a land count
recommendation.
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


def deck_castability(rows: Iterable[Mapping[str, object]]) -> dict[str, object]:
    """Castability of every distinct coloured requirement of the deck's nonland cards, plus
    the opening hand figure. ``rows`` carry ``zone``, ``quantity``, ``oracle_name``,
    ``card_id``, ``type_line``, ``mana_cost``, ``mana_value`` and ``produced_mana``."""
    groups: Counter[frozenset[str]] = Counter()
    unknown_lands = 0
    no_colour_lands = 0
    lands = early = other = 0
    unknown_mv = 0
    requirements: dict[tuple[int, tuple[tuple[str, int], ...]], list[dict[str, object]]] = {}
    hybrid_cards: list[str] = []
    for row in rows:
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
    land_groups = sorted(groups.items(), key=lambda item: ("".join(sorted(item[0])), item[1]))
    items = []
    for (turn, need_items), cards in sorted(requirements.items()):
        result = colour_probability(land_groups, nonland, dict(need_items), turn)
        items.append(
            {
                **result,
                "label": "".join(colour * count for colour, count in need_items),
                "cards": sorted(cards, key=lambda card: str(card["name"])),
            }
        )
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
        "opening_hand": opening_hands(lands, early, other),
        "method": (
            "Exakte multivariate Hypergeometrie nach Karsten (2022): Farbwahrscheinlichkeit "
            "bedingt auf die Land-Drops bis zum Zug des Manawerts; Landmangel getrennt; "
            "mehrere Symbole einer Farbe und mehrere Farben als ein gemeinsames Ereignis. "
            "Ziehen: 7 + Zug Karten, ohne Mulligan und ohne Extraziehen. Quellen: nur Länder."
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
