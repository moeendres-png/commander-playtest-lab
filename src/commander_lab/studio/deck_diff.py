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
  the commander names the card under any spelling: unknown, never 0).

Only counted figures: no score, no bracket, no power delta, no verdict on a swap.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from . import builder, combos
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
    assert isinstance(base_shape, dict) and isinstance(target_shape, dict)
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
    result["schema"] = SCHEMA
    return result
