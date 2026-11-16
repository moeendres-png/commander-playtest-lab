"""Guided cut from more than 100 cards to exactly 100 (#1418, after DeckFlow's "Cut Lab").

The page serves one cut suggestion after another (accept, reject, later). The order of the
suggestions comes only from measured figures, never from the Owner's marks and never from a
rating:

1. Cards whose source-deck frequency is known come first, the least played share first (the
   share in the chosen comparison group of the commander's source decks, with numerator and
   denominator). Cards no source deck names (frequency unknown) form a separate group after
   them: unknown is never treated as 0.
2. Ties: the more deck cards share the card's roles (role redundancy), the earlier; then name.
3. A cut that would drop a role below the minimum the page shows (guardrail, editable; the
   page's default is the lower quartile of the comparison group) is moved behind the cuts that
   keep every minimum, and says which role it touches.
4. Cards the page has deferred come last; rejected cards, locked cards, the commander and basic
   lands (adjusted with the separate basic-land counter) are never suggested.

Every suggestion carries only the measurable change of the deck figures: curve bucket, roles
before and after, coloured pips, land count, and whether the card is part of a listed combo
complete in the deck (a hint badge, no automatic lock). No text rates a card.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence

from . import builder, combos
from .decks import DECK_SIZE, RevisionCard, list_rows
from .land_advisor import _pips
from .store import StudioStore

SCHEMA = "studio-cut-lab-1"


def _merged(cards: Iterable[RevisionCard]) -> dict[tuple[str, str], int]:
    found: Counter[tuple[str, str]] = Counter()
    for card in cards:
        found[(card.card_id, card.zone)] += card.quantity
    return dict(found)


def cut_suggestions(
    store: StudioStore,
    cards: Sequence[RevisionCard],
    *,
    locked: Iterable[str] = (),
    rejected: Iterable[str] = (),
    deferred: Iterable[str] = (),
    role_minimums: Mapping[str, int] | None = None,
    cohort: str = builder.ALL_DECKS,
) -> dict[str, object]:
    """The ordered cut suggestions of a list (see the module text)."""
    locked_ids = set(locked)
    rejected_ids = set(rejected)
    deferred_order = {card_id: index for index, card_id in enumerate(deferred)}
    minimums = {str(role): int(value) for role, value in (role_minimums or {}).items()}
    rows = list_rows(store, cards)
    total = sum(int(row["quantity"]) for row in rows)
    commanders = sorted({str(row["oracle_name"]) for row in rows if row["zone"] == "commander"})
    sizes = builder.cohort_sizes(store, commanders) if commanders else {}
    of = sizes.get(cohort)
    hits = builder._corpus_hits(store, commanders) if commanders else {}

    ids = [str(row["card_id"]) for row in rows]
    roles: dict[str, list[str]] = {}
    db = store.connection
    for start in range(0, len(ids), 500):
        chunk = ids[start : start + 500]
        marks = ",".join("?" * len(chunk))
        for row in db.execute(
            "SELECT c.card_id, r.role FROM card_fact c JOIN card_role r USING (oracle_id) "
            f"WHERE c.card_id IN ({marks}) ORDER BY r.role",
            chunk,
        ):
            roles.setdefault(str(row["card_id"]), []).append(str(row["role"]))

    role_counts: Counter[str] = Counter()
    for row in rows:
        if row["zone"] != "main":
            continue
        for role in roles.get(str(row["card_id"]), []):
            role_counts[role] += int(row["quantity"])

    combo_view = combos.deck_combos(store, rows, commanders) if commanders else None
    combo_parts: dict[str, list[list[str]]] = {}
    complete = combo_view.get("complete") if combo_view else None
    for entry in complete if isinstance(complete, list) else []:
        names = [str(name) for name in entry.get("cards", [])]
        for name in names:
            combo_parts.setdefault(name.casefold(), []).append(names)

    items: list[dict[str, object]] = []
    for row in rows:
        card_id = str(row["card_id"])
        if row["zone"] != "main" or card_id in locked_ids or card_id in rejected_ids:
            continue
        if row["is_basic_land"]:
            continue
        name = str(row["oracle_name"])
        counts = hits.get(name)
        decks = None if counts is None or of is None else int(counts.get(cohort, 0))
        card_roles = roles.get(card_id, [])
        role_change = {
            role: {
                "before": role_counts[role],
                "after": role_counts[role] - 1,
                "minimum": minimums.get(role),
            }
            for role in card_roles
        }
        below = sorted(
            role
            for role, change in role_change.items()
            if change["minimum"] is not None and int(change["after"]) < int(change["minimum"])
        )
        front_type = str(row["type_line"] or "").split(" // ")[0]
        land = "Land" in front_type
        pips, _ = _pips(row) if not land else (Counter(), 0)
        mana_value = row["mana_value"]
        items.append(
            {
                "card_id": card_id,
                "name": name,
                "quantity": int(row["quantity"]),
                "decks": decks,
                "of": of,
                "share": None if decks is None or not of else round(decks / of, 4),
                "group": "known" if decks is not None else "unknown",
                "roles": card_roles,
                "role_change": role_change,
                "redundancy": min((role_counts[r] for r in card_roles), default=None),
                "below_minimum": below,
                "mana_value": mana_value,
                "curve_bucket": None if land or mana_value is None else min(int(mana_value), 7),
                "lands_delta": -1 if land else 0,
                "pips_delta": {colour: -count for colour, count in sorted(pips.items())},
                "combo_parts": combo_parts.get(name.casefold(), []),
                "deferred": card_id in deferred_order,
            }
        )

    def key(item: dict[str, object]) -> tuple[object, ...]:
        share = item["share"]
        redundancy = item["redundancy"]
        return (
            item["deferred"],
            deferred_order.get(str(item["card_id"]), -1),
            bool(item["below_minimum"]),
            item["group"] == "unknown",
            share if isinstance(share, float) else 0.0,
            -(redundancy if isinstance(redundancy, int) else -1),
            str(item["name"]),
        )

    items.sort(key=key)
    basics = sum(
        int(row["quantity"]) for row in rows if row["zone"] == "main" and row["is_basic_land"]
    )
    return {
        "schema": SCHEMA,
        "total": total,
        "target": DECK_SIZE,
        "excess": total - DECK_SIZE,
        "locked": sorted(locked_ids),
        "basic_lands": basics,
        "cohort": {
            "key": cohort,
            "decks": of,
            "small": of is not None and of < builder.SMALL_DENOMINATOR,
        },
        "role_minimums": minimums,
        "suggestions": items,
        "order": (
            "Reihenfolge nur aus gemessenen Größen: zuerst Karten mit bekannter Spielhäufigkeit "
            "(geringster Anteil zuerst), dann Karten ohne bekannte Häufigkeit; bei Gleichstand "
            "höhere Rollen-Redundanz zuerst. Vorschläge unter einer Rollen-Mindestzahl kommen "
            "danach, zurückgestellte zuletzt. Gesperrte, abgelehnte Karten, der Commander und "
            "Standardländer werden nie vorgeschlagen. Keine Wertung einer Karte."
        ),
    }


def patch_text(
    base: Sequence[RevisionCard], target: Sequence[RevisionCard], names: Mapping[str, str]
) -> str:
    """The ADD/CUT patch from ``base`` to ``target`` as text, one line per card."""
    before = _merged(base)
    after = _merged(target)
    lines: list[str] = []
    for key in sorted(
        set(before) | set(after), key=lambda item: (names.get(item[0], item[0]), item[1])
    ):
        delta = after.get(key, 0) - before.get(key, 0)
        if delta:
            word = "ADD" if delta > 0 else "CUT"
            zone = " (Commander)" if key[1] == "commander" else ""
            lines.append(f"{word} {abs(delta)} {names.get(key[0], key[0])}{zone}")
    return "\n".join(lines)


def finish(
    store: StudioStore, base: Sequence[RevisionCard], target: Sequence[RevisionCard]
) -> dict[str, object]:
    """The final list and the patch from the starting list (for export and saving)."""
    rows = list_rows(store, target)
    names = {
        str(row["card_id"]): str(row["oracle_name"]) for row in [*rows, *list_rows(store, base)]
    }
    total = sum(int(row["quantity"]) for row in rows)
    return {
        "schema": SCHEMA,
        "total": total,
        "exactly_100": total == DECK_SIZE,
        "list_text": "\n".join(f"{row['quantity']} {row['engine_name']}" for row in rows),
        "patch_text": patch_text(base, target, names),
    }
