"""Version comparison of two deck lists with counted deltas (#1414, #1404 option 8).

Extends ``builder.diff_lists`` (added, removed and changed cards, land/creature/nonland counts,
average mana value, land-draw probabilities, role deltas) with:

* the mana curve per mana value before and after,
* coloured pips and coloured land sources per colour before and after,
* listed combos complete in the deck before and after, with the combos that became complete
  or stopped being complete,
* the overlap of the two lists as a count (shared card slots of all slots, both numbers),
* per added, removed or changed card: roles, mana value and how many source decks of the
  commander in the chosen group play it (``decks`` of ``of``; ``None`` when no source deck of
  the commander names the card under any spelling: unknown, never 0),
* the mana base before and after (``manabase``, WP-5 of the builder audit, #1404): per coloured
  requirement the exact colour access of both lists and the delta in percentage points, the
  opening hand, the colour access per colour (opening hand, untapped source in turns 1 and 2),
  the lands per tapped class and the commander on curve (``manabase_delta``).

Only counted figures: no score, no bracket, no power delta, no verdict on a swap.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from . import builder, castability, combos
from .decks import RevisionCard, list_rows
from .land_advisor import deck_profile
from .store import StudioStore

SCHEMA = "studio-deck-diff-1"


def _slots(cards: Sequence[RevisionCard]) -> dict[str, int]:
    found: dict[str, int] = {}
    for card in cards:
        found[card.card_id] = found.get(card.card_id, 0) + card.quantity
    return found


def _combo_keys(view: dict[str, object]) -> dict[str, list[str]]:
    complete = view.get("complete")
    keys: dict[str, list[str]] = {}
    for entry in complete if isinstance(complete, list) else []:
        cards = [str(name) for name in entry.get("cards", [])]
        keys[json.dumps(sorted(name.casefold() for name in cards))] = cards
    return keys


_REQ_FIELDS = ("p_land_drops", "p_colours_given_lands", "p_on_curve")


def _pp(base: object, target: object) -> float | None:
    """Delta in percentage points of two shares; ``None`` (unknown) when one side is unknown."""
    if not isinstance(base, int | float) or not isinstance(target, int | float):
        return None
    return round((float(target) - float(base)) * 100, 2)


def _req_side(result: Mapping[str, object]) -> dict[str, object]:
    with_search = result.get("with_search")
    search = with_search if isinstance(with_search, Mapping) else {}
    side: dict[str, object] = {field: result.get(field) for field in _REQ_FIELDS}
    side["sources"] = result.get("sources")
    side["p_colours_given_lands_with_search"] = search.get("p_colours_given_lands")
    side["p_on_curve_with_search"] = search.get("p_on_curve")
    return side


def _side_deltas(base: Mapping[str, object], target: Mapping[str, object]) -> dict[str, object]:
    keys = (*_REQ_FIELDS, "p_colours_given_lands_with_search", "p_on_curve_with_search")
    return {key: _pp(base.get(key), target.get(key)) for key in keys}


def _access_values(entry: Mapping[str, object]) -> dict[str, object]:
    hand = entry["opening_hand"]
    turns = entry["turns"]
    assert isinstance(hand, Mapping) and isinstance(turns, list)
    values: dict[str, object] = {"hand": hand["p"], "hand_high": hand["p_high"]}
    for turn in turns:
        values[f"turn{turn['turn']}_low"] = turn["p_low"]
        values[f"turn{turn['turn']}_high"] = turn["p_high"]
    return values


def _colours(cast: Mapping[str, object]) -> set[str]:
    block = cast["colour_access"]
    assert isinstance(block, Mapping)
    return {str(entry["colour"]) for entry in block["colours"]}


def manabase_delta(
    base_rows: Sequence[Mapping[str, object]], target_rows: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    """The mana base before (``base``) and after (``target``), both computed exactly with
    ``castability`` (WP-5). A requirement that only one list has is computed on the land
    base of the other list too (the same exact rule) and marked with ``in_base`` and
    ``in_target``; a value that cannot be computed on a side is ``None`` (unknown), and so is
    every delta it enters. Deltas are percentage points of the shares rounded to four
    decimals. The commander delta is given only for the same commander(s)."""
    cast = {
        "base": castability.deck_castability(base_rows),
        "target": castability.deck_castability(target_rows),
    }
    basis = {
        "base": castability.LandBasis(base_rows),
        "target": castability.LandBasis(target_rows),
    }
    found: dict[str, dict[tuple[int, str], dict[str, object]]] = {"base": {}, "target": {}}
    needs: dict[tuple[int, str], dict[str, int]] = {}
    for side in ("base", "target"):
        for item in cast[side]["requirements"]:  # type: ignore[attr-defined]
            key = (int(item["turn"]), str(item["label"]))
            found[side][key] = item
            needs[key] = dict(item["need"])
    requirements = []
    for key in sorted(needs):
        sides: dict[str, dict[str, object]] = {}
        for side in ("base", "target"):
            result = found[side].get(key) or basis[side].requirement(needs[key], key[0])
            sides[side] = _req_side(result)
        requirements.append(
            {
                "label": key[1],
                "turn": key[0],
                "need": needs[key],
                "in_base": key in found["base"],
                "in_target": key in found["target"],
                "base": sides["base"],
                "target": sides["target"],
                "delta_pp": _side_deltas(sides["base"], sides["target"]),
            }
        )

    def hand(side: str) -> object:
        opening = cast[side]["opening_hand"]
        return opening.get("p_keepable") if isinstance(opening, Mapping) else None

    # Colour access per colour (WP-4 stage 2) on both lists; a colour only one list needs is
    # computed on the other list as well, with the same rule.
    needed = sorted(
        {
            str(entry["colour"])
            for side in ("base", "target")
            for entry in cast[side]["colour_access"]["colours"]  # type: ignore[index]
        },
        key=castability.COLOURS.index,
    )
    access = {
        side: {
            str(entry["colour"]): _access_values(entry)
            for entry in castability.colour_access(rows, needed)["colours"]  # type: ignore[attr-defined]
        }
        for side, rows in (("base", base_rows), ("target", target_rows))
    }
    colour_rows = [
        {
            "colour": colour,
            "in_base": colour in _colours(cast["base"]),
            "in_target": colour in _colours(cast["target"]),
            "base": access["base"][colour],
            "target": access["target"][colour],
            "delta_pp": {
                key: _pp(access["base"][colour][key], access["target"][colour][key])
                for key in access["base"][colour]
            },
        }
        for colour in needed
    ]

    tapped = {side: cast[side]["tapped"] for side in ("base", "target")}
    tapped_counts = {
        side: dict(tapped[side]["counts"])  # type: ignore[index]
        for side in ("base", "target")
    }
    commanders = {
        side: [entry for entry in cast[side]["commander"]]  # type: ignore[attr-defined]
        for side in ("base", "target")
    }
    names = {side: sorted(str(entry["name"]) for entry in commanders[side]) for side in commanders}
    same = bool(names["base"]) and names["base"] == names["target"]
    commander_rows = []
    by_name = {side: {str(e["name"]): e for e in commanders[side]} for side in commanders}
    for name in sorted(set(names["base"]) | set(names["target"])):
        row: dict[str, object] = {"name": name}
        for side in ("base", "target"):
            entry = by_name[side].get(name)
            row[side] = None if entry is None or not entry.get("known") else _req_side(entry)
        base_side, target_side = row["base"], row["target"]
        row["delta_pp"] = (
            _side_deltas(base_side, target_side)
            if same and isinstance(base_side, Mapping) and isinstance(target_side, Mapping)
            else None
        )
        commander_rows.append(row)
    return {
        "requirements": requirements,
        "opening_hand": {
            "rule": cast["target"]["opening_hand"]["rule"],  # type: ignore[index]
            "base": hand("base"),
            "target": hand("target"),
            "delta_pp": _pp(hand("base"), hand("target")),
        },
        "colour_access": colour_rows,
        "tapped": {
            "base": tapped_counts["base"],
            "target": tapped_counts["target"],
            "base_of": tapped["base"]["of"],  # type: ignore[index]
            "target_of": tapped["target"]["of"],  # type: ignore[index]
            "delta": {
                key: int(tapped_counts["target"][key]) - int(tapped_counts["base"][key])
                for key in castability.TAP_CLASSES
            },
        },
        "commander": {"same": same, "rows": commander_rows},
        "lists": {
            side: {
                "main_cards": cast[side]["main_cards"],
                "lands": cast[side]["lands"],
                "lands_unknown_colours": cast[side]["lands_unknown_colours"],
            }
            for side in ("base", "target")
        },
        "assumptions": {
            "search": castability.LAND_SEARCH_ASSUMPTION,
            "access": castability.TAPPED_ACCESS_ASSUMPTION,
            "access_rule": castability.TAPPED_ACCESS_RULE,
            "tapped_rule": castability.TAPPED_RULE,
            "delta": (
                "Delta = aktuell minus Basis in Prozentpunkten, aus den auf vier Nachkommastellen "
                "gerundeten exakten Anteilen beider Stände; unbekannt, wenn ein Stand nicht "
                "rechenbar ist. Eine Anforderung, die nur eine Liste hat, ist auf der "
                "Manabasis der anderen Liste mit derselben Regel gerechnet."
            ),
        },
    }


def diff_impact(
    store: StudioStore,
    base_cards: Sequence[RevisionCard],
    target_cards: Sequence[RevisionCard],
    *,
    cohort: str = builder.ALL_DECKS,
) -> dict[str, object]:
    """``builder.diff_lists`` plus the counted deltas of the module text."""
    result = builder.diff_lists(store, base_cards, target_cards)
    base_rows = list_rows(store, base_cards)
    target_rows = list_rows(store, target_cards)

    base_profile = deck_profile(base_rows)
    target_profile = deck_profile(target_rows)
    colours: dict[str, dict[str, int]] = {}
    for side, profile in (("base", base_profile), ("target", target_profile)):
        entries = profile["colours"]
        for entry in entries if isinstance(entries, list) else []:
            row = colours.setdefault(
                str(entry["colour"]),
                {"base_pips": 0, "target_pips": 0, "base_sources": 0, "target_sources": 0},
            )
            row[f"{side}_pips"] = int(entry["pips"])
            row[f"{side}_sources"] = int(entry["land_sources"])
    result["colour_deltas"] = {colour: colours[colour] for colour in "WUBRG" if colour in colours}

    base_shape = result["base_shape"]
    target_shape = result["target_shape"]
    if not isinstance(base_shape, dict) or not isinstance(target_shape, dict):
        raise TypeError("diff_lists must return deck shapes as dicts")
    result["curve_deltas"] = {
        key: {
            "base": int(base_shape["curve"].get(key, 0)),
            "target": int(target_shape["curve"].get(key, 0)),
        }
        for key in (str(value) for value in range(8))
    }

    base_commanders = sorted({str(r["oracle_name"]) for r in base_rows if r["zone"] == "commander"})
    target_commanders = sorted(
        {str(r["oracle_name"]) for r in target_rows if r["zone"] == "commander"}
    )
    same_commander = base_commanders == target_commanders
    # Each side is read against its own commander's combo list: lists of two commanders are
    # never mixed. Only with the same commander(s) is a before/after transition shown.
    base_combos = combos.deck_combos(store, base_rows, base_commanders)
    target_combos = combos.deck_combos(store, target_rows, target_commanders)
    before = _combo_keys(base_combos)
    after = _combo_keys(target_combos)
    base_listed = int(str(base_combos.get("listed") or 0))
    listed = int(str(target_combos.get("listed") or 0))
    result["combo_delta"] = {
        "comparable": same_commander,
        "listed": listed,
        "base_listed": base_listed,
        "base_complete": len(before) if base_listed else None,
        "target_complete": len(after) if listed else None,
        "now_complete": (
            [after[key] for key in sorted(set(after) - set(before))] if same_commander else []
        ),
        "no_longer_complete": (
            [before[key] for key in sorted(set(before) - set(after))] if same_commander else []
        ),
    }
    result["commanders"] = {
        "base": base_commanders,
        "target": target_commanders,
        "same": same_commander,
    }

    base_slots = _slots(base_cards)
    target_slots = _slots(target_cards)
    shared = sum(min(base_slots[cid], target_slots.get(cid, 0)) for cid in base_slots)
    result["overlap"] = {
        "shared_slots": shared,
        "base_slots": sum(base_slots.values()),
        "target_slots": sum(target_slots.values()),
        "meaning": "gemeinsame Kartenplätze (Commander eingeschlossen), gezählt, keine Wertung",
    }

    # Frequencies of a card come from the source decks of the side it belongs to: added and
    # changed cards from the current list's commander, removed cards from the base's.
    sides = {
        "target": (
            builder.cohort_sizes(store, target_commanders) if target_commanders else {},
            builder._corpus_hits(store, target_commanders) if target_commanders else {},
        ),
        "base": (
            builder.cohort_sizes(store, base_commanders) if base_commanders else {},
            builder._corpus_hits(store, base_commanders) if base_commanders else {},
        ),
    }
    roles: dict[str, list[str]] = {}
    facts: dict[str, tuple[str, object]] = {}
    changed_ids = [
        str(item["card_id"])
        for key in ("added", "removed", "changed")
        for item in result[key]  # type: ignore[attr-defined]
    ]
    db = store.connection
    for start in range(0, len(changed_ids), 500):
        chunk = changed_ids[start : start + 500]
        marks = ",".join("?" * len(chunk))
        for row in db.execute(
            f"SELECT card_id, oracle_name, mana_value FROM card_fact WHERE card_id IN ({marks})",
            chunk,
        ):
            facts[str(row["card_id"])] = (str(row["oracle_name"]), row["mana_value"])
        for row in db.execute(
            "SELECT c.card_id, r.role FROM card_fact c JOIN card_role r USING (oracle_id) "
            f"WHERE c.card_id IN ({marks}) ORDER BY r.role",
            chunk,
        ):
            roles.setdefault(str(row["card_id"]), []).append(str(row["role"]))
    for key in ("added", "removed", "changed"):
        sizes, hits = sides["base" if key == "removed" else "target"]
        of = sizes.get(cohort)
        for item in result[key]:  # type: ignore[attr-defined]
            card_id = str(item["card_id"])
            name, mana_value = facts.get(card_id, (str(item["name"]), None))
            counts = hits.get(name)
            item["roles"] = roles.get(card_id, [])
            item["mana_value"] = mana_value
            item["decks"] = None if counts is None or of is None else int(counts.get(cohort, 0))
            item["of"] = of
    target_of = sides["target"][0].get(cohort)
    base_of = sides["base"][0].get(cohort)
    result["cohort"] = {
        "key": cohort,
        "decks": target_of,
        "base_decks": base_of,
        "small": any(n is not None and n < builder.SMALL_DENOMINATOR for n in (target_of, base_of)),
    }
    result["manabase"] = manabase_delta(
        [dict(row) for row in base_rows], [dict(row) for row in target_rows]
    )
    result["schema"] = SCHEMA
    return result
