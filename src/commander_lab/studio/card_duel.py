"""Card duel: two cards side by side, observed only (#1404 option 3, "A oder B?").

For each of the two cards: roles, mana value, type, how many source decks of the commander in
the chosen group play it (``decks`` of ``of``), and how well it fits the rest of the deck as
observed in those decks:

    fit(X) = average, over the source decks that play X, of the share of the deck's other cards
             (without the two duel cards, the commander and basic lands) they also play
    baseline = the same average over all source decks of the group

``fit`` above ``baseline`` means: decks that play X share more of your other cards than the
group does on average. It is an observation of co-occurrence, never "better". A card no source
deck of the group plays has ``fit`` unknown (``None``), not 0. Groups under 30 decks are
flagged. Counting reuses the cached source-deck index of ``similar_decks`` (non-duplicate
decks, counted sections, spellings merged, without basics and commander).
"""

from __future__ import annotations

from collections.abc import Sequence

from . import builder, universe
from .similar_decks import _basic_oracle_names, _canonical_name, _commander_source_index
from .store import StudioStore

SCHEMA = "studio-card-duel-1"


def card_duel(
    store: StudioStore,
    commander_names: Sequence[str],
    *,
    deck_card_ids: Sequence[str],
    card_a: str,
    card_b: str,
    cohort: str = builder.ALL_DECKS,
) -> dict[str, object]:
    """The duel of ``card_a`` and ``card_b`` against the deck ``deck_card_ids``."""
    if not commander_names:
        raise ValueError("commander is required")
    db = store.connection
    facts = {
        str(row["card_id"]): row
        for row in db.execute(
            "SELECT card_id, oracle_name, oracle_id, mana_value, type_line, mana_cost "
            f"FROM card_fact WHERE card_id IN ({','.join('?' * len({*deck_card_ids, card_a, card_b}))})",
            [*{*deck_card_ids, card_a, card_b}],
        )
    }
    for card_id in (card_a, card_b):
        if card_id not in facts:
            raise KeyError(card_id)
    owners = universe.spelling_owners(store)
    basics = _basic_oracle_names(store)
    commanders_cf = {name.casefold() for name in commander_names}

    def canonical(card_id: str) -> str:
        return _canonical_name(owners, str(facts[card_id]["oracle_name"]))

    duel_names = {canonical(card_a), canonical(card_b)}
    others = {
        name
        for name in (canonical(cid) for cid in deck_card_ids if cid in facts)
        if name not in duel_names
        and name.casefold() not in basics
        and name.casefold() not in commanders_cf
    }

    index = _commander_source_index(store, commander_names)
    decks = index["decks"]
    cohorts = index["cohorts_by_deck"]
    postings = index["postings"]
    members = {i for i, deck in enumerate(decks) if cohort in cohorts.get(deck["deck_id"], set())}
    of = len(members)

    def average_share(deck_indices: set[int]) -> float | None:
        if not deck_indices or not others:
            return None
        hits = sum(len(deck_indices.intersection(postings.get(name, ()))) for name in others)
        return round(hits / (len(deck_indices) * len(others)), 4)

    baseline = average_share(members)
    roles: dict[str, list[str]] = {}
    for row in db.execute(
        "SELECT c.card_id, r.role FROM card_fact c JOIN card_role r USING (oracle_id) "
        "WHERE c.card_id IN (?, ?) ORDER BY r.role",
        (card_a, card_b),
    ):
        roles.setdefault(str(row["card_id"]), []).append(str(row["role"]))

    def side(card_id: str) -> dict[str, object]:
        name = canonical(card_id)
        playing = members.intersection(postings.get(name, ()))
        # A card absent from the index is named by no source deck of the commander: unknown.
        known = name in postings
        decks_count = len(playing) if known else None
        return {
            "card_id": card_id,
            "name": str(facts[card_id]["oracle_name"]),
            "mana_cost": facts[card_id]["mana_cost"],
            "mana_value": facts[card_id]["mana_value"],
            "group": builder.main_type(facts[card_id]["type_line"]),
            "roles": roles.get(card_id, []),
            "in_deck": card_id in set(deck_card_ids),
            "decks": decks_count,
            "of": of,
            "share": None if decks_count is None or not of else round(decks_count / of, 4),
            "fit": average_share(playing) if known else None,
            "fit_decks": len(playing) if known else None,
            "small": known and len(playing) < builder.SMALL_DENOMINATOR,
        }

    a_side = side(card_a)
    b_side = side(card_b)
    return {
        "schema": SCHEMA,
        "cohort": {"key": cohort, "decks": of, "small": of < builder.SMALL_DENOMINATOR},
        "other_cards": len(others),
        "baseline": baseline,
        "a": a_side,
        "b": b_side,
        "shared_roles": sorted(set(a_side["roles"]) & set(b_side["roles"])),  # type: ignore[arg-type]
        "meaning": (
            "Beobachtet, nicht „besser“: Passung = durchschnittlicher Anteil deiner übrigen "
            "Karten (ohne die beiden, Commander und Standardländer) in den Quelldecks, die die "
            "Karte spielen; Grundwert = derselbe Anteil über alle Quelldecks der Gruppe."
        ),
    }
