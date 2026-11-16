"""Where each card is bound: saved decks and storage locations (#1419). Display only.

* **Binding.** Every saved deck binds the copies its current list uses. Variants of one deck
  are alternatives of the same physical deck, so a deck binds the copies of its ``main``
  variant (or, without one, of its most recently saved variant); the other variants are listed
  but bind nothing. Drafts never bind. A card is **overbooked** when the copies bound by all
  saved decks exceed the copies free for own decks (``available_lower_bound``). Nothing is
  locked or changed: an overbooking is a data note.
* **Reserved** copies (``reserved``, kept for opponents' decks) are a separate figure and are
  already outside the free copies; they are shown, never mixed into the deck bindings.
* **Locations** come only from the inventory workbook's lot sheet (``card_location``). When a
  card has no location rows the field is absent, not "unknown".
"""

from __future__ import annotations

from .store import StudioStore

SCHEMA = "studio-allocation-1"


def _binding_branches(store: StudioStore) -> dict[str, tuple[str, str, str]]:
    """``{deck_id: (deck name, branch, revision_id)}`` of the variant that binds copies."""
    chosen: dict[str, tuple[str, str, str]] = {}
    for row in store.connection.execute(
        "SELECT d.deck_id, d.name, b.branch, b.revision_id, r.created_at "
        "FROM deck d JOIN deck_branch b USING (deck_id) "
        "JOIN deck_revision r ON r.revision_id = b.revision_id "
        "ORDER BY d.deck_id, (b.branch = 'main') DESC, r.created_at DESC, b.branch"
    ):
        chosen.setdefault(
            str(row["deck_id"]), (str(row["name"]), str(row["branch"]), str(row["revision_id"]))
        )
    return chosen


def allocation(store: StudioStore) -> dict[str, object]:
    """Bindings, overbooking and locations of every card that is bound or has locations."""
    db = store.connection
    binding = _binding_branches(store)
    decks: dict[str, list[dict[str, object]]] = {}
    for deck_id, (name, branch, revision_id) in sorted(binding.items()):
        for row in db.execute(
            "SELECT card_id, SUM(quantity) AS quantity FROM deck_revision_card "
            "WHERE revision_id = ? GROUP BY card_id",
            (revision_id,),
        ):
            decks.setdefault(str(row["card_id"]), []).append(
                {
                    "deck_id": deck_id,
                    "deck_name": name,
                    "branch": branch,
                    "revision_id": revision_id,
                    "quantity": int(row["quantity"]),
                }
            )
    other_variants: dict[str, list[dict[str, object]]] = {}
    for row in db.execute(
        "SELECT d.deck_id, d.name, b.branch, b.revision_id, rc.card_id, SUM(rc.quantity) AS q "
        "FROM deck d JOIN deck_branch b USING (deck_id) "
        "JOIN deck_revision_card rc ON rc.revision_id = b.revision_id "
        "GROUP BY d.deck_id, b.branch, rc.card_id ORDER BY d.deck_id, b.branch"
    ):
        deck_id = str(row["deck_id"])
        if binding.get(deck_id, ("", "", ""))[1] == str(row["branch"]):
            continue
        other_variants.setdefault(str(row["card_id"]), []).append(
            {
                "deck_id": deck_id,
                "deck_name": str(row["name"]),
                "branch": str(row["branch"]),
                "revision_id": str(row["revision_id"]),
                "quantity": int(row["q"]),
            }
        )
    locations: dict[str, list[dict[str, object]]] = {}
    for row in db.execute(
        "SELECT card_id, location_id, location_name, location_type, quantity "
        "FROM card_location ORDER BY card_id, quantity DESC, location_name"
    ):
        locations.setdefault(str(row["card_id"]), []).append(
            {
                "location_id": str(row["location_id"]),
                "name": str(row["location_name"]),
                "type": row["location_type"],
                "quantity": int(row["quantity"]),
            }
        )
    inventory = {
        str(row["card_id"]): row
        for row in db.execute(
            "SELECT card_id, owned_lower_bound, reserved, available_lower_bound FROM inventory"
        )
    }
    cards: dict[str, dict[str, object]] = {}
    for card_id in sorted(set(decks) | set(locations) | set(other_variants)):
        stock = inventory.get(card_id)
        bound = sum(int(str(item["quantity"])) for item in decks.get(card_id, []))
        available = None if stock is None else int(stock["available_lower_bound"])
        entry: dict[str, object] = {
            "bound": bound,
            "available": available,
            "owned": None if stock is None else int(stock["owned_lower_bound"]),
            "reserved": None if stock is None else int(stock["reserved"]),
            # Without an inventory row the free copies are unknown: no overbooking is claimed.
            "overbooked": available is not None and bound > available,
            "decks": decks.get(card_id, []),
            "other_variants": other_variants.get(card_id, []),
        }
        if card_id in locations:
            entry["locations"] = locations[card_id]
        cards[card_id] = entry
    overbooked = sorted(card_id for card_id, entry in cards.items() if entry["overbooked"])
    return {
        "schema": SCHEMA,
        "binding_rule": (
            "Ein gespeichertes Deck bindet die Karten seiner Variante main (ohne main: der "
            "zuletzt gespeicherten Variante); weitere Varianten sind Alternativen und binden "
            "nichts. Entwürfe binden nichts. Überbucht: gebundene Exemplare über den freien."
        ),
        "decks_binding": [
            {"deck_id": deck_id, "deck_name": name, "branch": branch, "revision_id": revision}
            for deck_id, (name, branch, revision) in sorted(binding.items())
        ],
        "locations_known": bool(locations),
        "overbooked": overbooked,
        "cards": cards,
    }
