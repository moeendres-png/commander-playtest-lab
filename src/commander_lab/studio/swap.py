"""Swap helper of the Studio deck builder ("Tausch-Helfer").

Two questions, answered from stored counts only:

* ``replace``: "Was ersetzt diese Karte?" for a card in the deck. The candidates are cards that
  share a role with it, ordered by how many decks of the chosen comparison group play them (most
  played first).
* ``cut``: "Was nehme ich dafür raus?" for a candidate card from the pool. The candidates are the
  cards in the deck that share a role with it, ordered by how rarely the group plays them (rarest
  first).

Every frequency is ``decks`` of ``of`` (the denominator is the size of the comparison group, the
number the pool shows for the same group). A card the group's decks do not name is ``unknown``
(``decks`` and ``share`` are ``None``), never zero, and unknown cards are always listed last. The
count says how often a card is played and nothing about how strong it is. Marks (favourite,
excluded, notes) and labels change neither the order nor which cards are listed; the two mark
flags only travel along as display fields. Nothing here reads prices, simulation results or a
rating.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence

from . import builder, cache, universe, universe_view
from .decks import color_set
from .store import StudioStore

SWAP_MODES = frozenset({"replace", "cut"})
DEFAULT_LIMIT = 50
MAX_LIMIT = 300
MAX_DECK_CARDS = 300


class UnknownCard(KeyError):
    """The card id is not in the Studio store."""


class UnknownCommander(KeyError):
    """The commander is not in the collection."""


class UnknownUniverse(KeyError):
    """No stored universe profile has this name."""


def _is_basic(type_line: str, flag: object) -> bool:
    if bool(flag):
        return True
    front = type_line.split(" // ")[0]
    return "Basic" in front and "Land" in front


def _group_deck_ids(store: StudioStore, commander_names: Sequence[str], cohort: str) -> list[str]:
    """The non-duplicate source decks of the commander in one comparison group, selected the
    way the pool counts them (``builder.cohort_sizes``)."""
    db = store.connection
    bound, args = builder.bound_to("corpus_deck", "d.deck_id", commander_names)
    params: list[object] = [*args]
    sql = f"SELECT d.deck_id FROM corpus_deck d WHERE d.duplicate_of IS NULL{bound}"
    if cohort != builder.ALL_DECKS:
        play_groups = {str(r[0]) for r in db.execute("SELECT DISTINCT play_group FROM corpus_deck")}
        if cohort in play_groups:
            sql += " AND d.play_group = ?"
        else:
            sql += (
                " AND EXISTS (SELECT 1 FROM corpus_cohort cc "
                "WHERE cc.deck_id = d.deck_id AND cc.cohort = ?)"
            )
        params.append(cohort)
    return sorted(str(r[0]) for r in db.execute(sql, params))


class _Group:
    """The comparison group of one request: its denominator and how often a card is played in it.

    Collection cards read the very figures the pool shows (``pool_cards``: ``decks`` per group,
    or the counted spread of a universe). A card outside the collection is looked up by its
    public name in the decks of the group (a union of decks, never a sum of spellings)."""

    def __init__(
        self,
        store: StudioStore,
        commander_names: Sequence[str],
        cohort: str,
        universe_name: str | None,
    ) -> None:
        self.store = store
        self.commander_names = list(commander_names)
        self.cohort = cohort
        self.universe_name = universe_name
        self._spread_by_card: dict[str, Mapping[str, object]] = {}
        self._hits: dict[str, dict[str, int]] = {}
        self._raw_sets: dict[str, set[str]] | None = None
        if universe_name is not None:
            try:
                spread = universe_view.pool_spread(
                    store, universe_name, commander_names=self.commander_names
                )
            except KeyError as error:
                raise UnknownUniverse(universe_name) from error
            self.name = universe_name
            self.kind = "universe"
            self.of = int(spread["universe"]["denominator"])
            self._spread_by_card = {str(item["card_id"]): item for item in spread["cards"]}
        else:
            sizes = builder.cohort_sizes(store, self.commander_names)
            if cohort not in sizes:
                raise ValueError(f"Unbekannte Vergleichsgruppe: {cohort}")
            self.name = cohort
            self.kind = "cohort"
            self.of = int(sizes[cohort])
            self._hits = builder._corpus_hits(store, self.commander_names)

    def pool_count(self, card_id: str, oracle_name: str) -> tuple[int | None, str | None]:
        """(decks, None) for a counted card, (None, reason) for an unknown one."""
        if self.of <= 0:
            return None, "no_source_decks"
        if self.universe_name is not None:
            item = self._spread_by_card.get(card_id)
            if item is None or not bool(item.get("matched")):
                return None, "not_in_decks"
            if bool(item.get("filter_card")):
                return None, "filter_card"
            found = item.get("hits")
            return (int(found), None) if isinstance(found, int) else (None, "not_in_decks")
        per_group = self._hits.get(oracle_name)
        if per_group is None or self.cohort not in per_group:
            return None, "not_in_decks"
        return int(per_group[self.cohort]), None

    def _raw_decks(self) -> dict[str, set[str]]:
        if self._raw_sets is None:
            store, names, cohort = self.store, self.commander_names, self.cohort
            if self.universe_name is not None:
                self._raw_sets = universe.universe_decks(
                    store, profile=self.universe_name, commander_names=names
                )["decks_by_name"]
            else:
                self._raw_sets = cache.cached(
                    store,
                    ("swap_raw_decks", tuple(names), cohort),
                    lambda: universe.deck_sets(store, _group_deck_ids(store, names, cohort), None),
                )
        return self._raw_sets

    def public_count(self, names: Sequence[str]) -> tuple[int | None, str | None]:
        """The decks of the group that list a card outside the collection under one of its
        public names (full name, front face)."""
        if self.of <= 0:
            return None, "no_source_decks"
        wanted = {name.casefold() for name in names if name}
        found: set[str] = set()
        matched = False
        for raw, decks in self._raw_decks().items():
            if raw.casefold() in wanted:
                matched = True
                found |= decks
        return (len(found), None) if matched else (None, "not_in_decks")


def _target_roles(db: sqlite3.Connection, oracle_id: str) -> list[str]:
    return [
        str(row[0])
        for row in db.execute(
            "SELECT role FROM card_role WHERE oracle_id = ? ORDER BY role", (oracle_id,)
        )
    ]


def _roles_by_oracle(db: sqlite3.Connection, roles: Sequence[str]) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    if not roles:
        return found
    marks = ", ".join("?" for _ in roles)
    for row in db.execute(
        f"SELECT oracle_id, role FROM card_role WHERE role IN ({marks})", list(roles)
    ):
        found.setdefault(str(row["oracle_id"]), set()).add(str(row["role"]))
    return found


def _sort_key(mode: str, item: Mapping[str, object]) -> tuple[int, float, str, str]:
    """Known counts first (most played first for ``replace``, rarest first for ``cut``), ties by
    name; unknown counts last, by name."""
    name = str(item["name"])
    decks = item["decks"]
    if not isinstance(decks, int):
        return (1, 0.0, name.casefold(), name)
    return (0, -float(decks) if mode == "replace" else float(decks), name.casefold(), name)


def _basis(
    *,
    mode: str,
    card_name: str,
    fallback_type: str | None,
    group_name: str,
    of: int,
) -> str:
    parts: list[str] = []
    if fallback_type is None:
        parts.append(f"Verglichen werden Karten mit gleicher Rolle wie „{card_name}“.")
    else:
        parts.append(
            f"Für „{card_name}“ sind keine Rollen erfasst. Ersatzweise werden Karten vom "
            f"gleichen Kartentyp ({fallback_type}) verglichen; das ist nur eine grobe Näherung, "
            "keine Rolle."
        )
    if mode == "replace":
        parts.append(
            f"Geordnet nach der Zahl der Decks der Gruppe „{group_name}“, die sie spielen "
            "(häufigste zuerst)."
        )
    else:
        parts.append(
            f"Geordnet nach der Zahl der Decks der Gruppe „{group_name}“, die sie spielen "
            "(seltenste zuerst). Selten gespielt ist eine Zählung und kein Urteil über die Karte."
        )
    parts.append("Eine Karte steht in n von N Decks; sagt nichts über Spielstärke.")
    if of <= 0:
        parts.append(
            "In dieser Gruppe liegen keine Quelldecks vor: alle Häufigkeiten sind unbekannt."
        )
    elif of < builder.SMALL_DENOMINATOR:
        parts.append(
            f"Die Gruppe hat nur {of} Decks (unter {builder.SMALL_DENOMINATOR}): "
            "die Zahlen sind unsicher."
        )
    return " ".join(parts)


def swap_candidates(
    store: StudioStore,
    *,
    commander: str | Sequence[str],
    deck_card_ids: Sequence[str],
    card_id: str,
    mode: str,
    cohort: str = builder.ALL_DECKS,
    universe: str | None = None,
    include_unowned: bool = False,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, object]:
    """Role-sharing replacement candidates (``mode='replace'``) or cut candidates
    (``mode='cut'``) for ``card_id`` under ``commander``, with the frequencies of one comparison
    group (``cohort``) or of a stored universe profile (``universe``, which wins over
    ``cohort``).

    Raises ``ValueError`` (a German sentence) for input that cannot be answered, and
    ``UnknownCard``, ``UnknownCommander`` or ``UnknownUniverse`` (all ``KeyError``) for names
    the store does not know."""
    if mode not in SWAP_MODES:
        raise ValueError(f"Unbekannter Modus: {mode}")
    names = [commander] if isinstance(commander, str) else [str(name) for name in commander]
    if not names or len(names) > 2 or not all(name.strip() for name in names):
        raise ValueError("Gib einen oder zwei Commander an.")
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f"Die Zahl der Zeilen liegt zwischen 1 und {MAX_LIMIT}.")
    deck_ids = list(dict.fromkeys(str(card) for card in deck_card_ids if card))
    if len(deck_ids) > MAX_DECK_CARDS:
        raise ValueError(f"Ein Deck hat höchstens {MAX_DECK_CARDS} verschiedene Karten.")
    try:
        identity, commander_ids = builder.commander_identity(store, names)
    except KeyError as error:
        raise UnknownCommander(error.args[0]) from error

    db = store.connection
    target = db.execute(
        "SELECT card_id, oracle_id, oracle_name, mana_value, type_line, is_basic_land "
        "FROM card_fact WHERE card_id = ?",
        (card_id,),
    ).fetchone()
    if target is None:
        raise UnknownCard(card_id)
    if card_id in commander_ids:
        raise ValueError("Der Commander wird nicht getauscht.")
    if _is_basic(str(target["type_line"] or ""), target["is_basic_land"]):
        raise ValueError("Für Standardländer gibt es keinen Tausch-Helfer.")
    if deck_ids:
        marks = ", ".join("?" for _ in deck_ids)
        known = {
            str(row[0])
            for row in db.execute(f"SELECT card_id FROM card WHERE card_id IN ({marks})", deck_ids)
        }
        missing = [card for card in deck_ids if card not in known]
        if missing:
            raise ValueError(
                f"Diese Karten im Deck kennt das Studio nicht: {', '.join(missing[:5])}"
            )

    group = _Group(store, names, cohort, (universe or "").strip() or None)
    small = group.of < builder.SMALL_DENOMINATOR
    target_name = str(target["oracle_name"])
    target_mv = float(target["mana_value"] or 0.0)
    roles_of_card = _target_roles(db, str(target["oracle_id"])) if target["oracle_id"] else []
    target_roles = set(roles_of_card)
    type_group = builder.main_type(str(target["type_line"] or ""))
    fallback_type = None if target_roles else type_group
    roles_by_oracle = _roles_by_oracle(db, roles_of_card)

    def shared_with(oracle_id: object, type_line: str) -> tuple[bool, list[str]]:
        """(shares something, the shared roles). Without role data for the target: the same
        type group, with no roles named."""
        if fallback_type is not None:
            return builder.main_type(type_line) == fallback_type, []
        shared = sorted(target_roles & roles_by_oracle.get(str(oracle_id), set()))
        return bool(shared), shared

    in_deck_ids = set(deck_ids)
    skip = {card_id, *commander_ids}
    items: list[dict[str, object]] = []

    def entry(
        *,
        cid: str | None,
        oracle_id: str,
        name: str,
        shared: list[str],
        mana_value: object,
        decks: int | None,
        reason: str | None,
        in_deck: bool,
        in_collection: bool,
        available: int,
        favorite: bool,
        excluded: bool,
    ) -> dict[str, object]:
        mv = float(str(mana_value or 0))
        known = decks is not None and group.of > 0
        return {
            "card_id": cid,
            "oracle_id": oracle_id,
            "name": name,
            "shared_roles": shared,
            "mana_value": mv,
            "mv_delta": round(mv - target_mv, 4),
            "decks": decks if known else None,
            "of": group.of,
            "share": round(decks / group.of, 4) if known and decks is not None else None,
            "unknown_reason": None if known else (reason or "not_in_decks"),
            "in_deck": in_deck,
            "in_collection": in_collection,
            "available": available,
            "small_group": small,
            "favorite": favorite,
            "excluded": excluded,
        }

    rows = db.execute(
        "SELECT c.card_id, c.oracle_id, c.oracle_name, c.color_identity, c.mana_value, "
        "c.type_line, c.is_basic_land, c.commander_legal, i.available_lower_bound, "
        "m.favorite, m.excluded "
        "FROM card_fact c JOIN inventory i USING (card_id) LEFT JOIN card_mark m USING (card_id) "
        "ORDER BY c.oracle_name"
    ).fetchall()
    collection_oracles: set[str] = set()
    for row in rows:
        if row["oracle_id"]:
            collection_oracles.add(str(row["oracle_id"]))
        cid = str(row["card_id"])
        if cid in skip:
            continue
        type_line = str(row["type_line"] or "")
        if _is_basic(type_line, row["is_basic_land"]):
            continue
        in_deck = cid in in_deck_ids
        available = int(row["available_lower_bound"] or 0)
        if mode == "cut":
            if not in_deck:
                continue
        else:
            if in_deck or row["commander_legal"] != 1:
                continue
            if not color_set(row["color_identity"]) <= identity:
                continue
            if available < 1 and not include_unowned:
                continue
        found, shared = shared_with(row["oracle_id"], type_line)
        if not found:
            continue
        name = str(row["oracle_name"])
        decks, reason = group.pool_count(cid, name)
        items.append(
            entry(
                cid=cid,
                oracle_id=str(row["oracle_id"] or ""),
                name=name,
                shared=shared,
                mana_value=row["mana_value"],
                decks=decks,
                reason=reason,
                in_deck=in_deck,
                in_collection=True,
                available=max(available, 0),
                favorite=bool(row["favorite"]),
                excluded=bool(row["excluded"]),
            )
        )

    if mode == "replace" and include_unowned:
        # Cards the collection does not hold, known from the public card data: no card id, no
        # free copy. Shown only on request.
        for row in db.execute(
            "SELECT s.oracle_id, s.name, s.front_name, s.mana_value, s.type_line, "
            "s.color_identity FROM scryfall_card s WHERE s.commander_legality = 'legal' "
            "ORDER BY s.name"
        ):
            oracle_id = str(row["oracle_id"])
            if oracle_id in collection_oracles or oracle_id == str(target["oracle_id"]):
                continue
            type_line = str(row["type_line"] or "")
            if _is_basic(type_line, 0) or not color_set(row["color_identity"]) <= identity:
                continue
            found, shared = shared_with(oracle_id, type_line)
            if not found:
                continue
            decks, reason = group.public_count([str(row["name"]), str(row["front_name"])])
            items.append(
                entry(
                    cid=None,
                    oracle_id=oracle_id,
                    name=str(row["name"]),
                    shared=shared,
                    mana_value=row["mana_value"],
                    decks=decks,
                    reason=reason,
                    in_deck=False,
                    in_collection=False,
                    available=0,
                    favorite=False,
                    excluded=False,
                )
            )

    items.sort(key=lambda item: _sort_key(mode, item))
    unknown_count = sum(1 for item in items if item["decks"] is None)
    return {
        "basis": _basis(
            mode=mode,
            card_name=target_name,
            fallback_type=fallback_type,
            group_name=group.name,
            of=group.of,
        ),
        "mode": mode,
        "card_id": card_id,
        "card_name": target_name,
        "group": {"name": group.name, "kind": group.kind, "decks": group.of, "small": small},
        "small_group": small,
        "roles_of_card": roles_of_card,
        "fallback": None
        if fallback_type is None
        else {"kind": "type_group", "type_group": type_group},
        "include_unowned": include_unowned,
        "total": len(items),
        "items": items[:limit],
        "unknown_count": unknown_count,
    }
