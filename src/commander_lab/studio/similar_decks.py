"""Similar source decks (Proposal 3, #1404) and read-only Deck-Browser (Proposal 5, #1323).

All calculations are purely descriptive counts and set overlaps (Jaccard similarity over
non-basic maindeck cards, and card frequencies across filtered deck sets).
- Never claims that similarity or frequency implies deck strength or tournament success.
- Basic lands and the commander itself are excluded from Jaccard similarity.
- Duplicate source decks (`duplicate_of IS NOT NULL`) and decks with the same card set are
  counted once (the lowest deck id); a source deck with the compared card set is left out.
- Order of the nearest source decks: similarity (exact fraction) descending, then `deck_id`.
- Cards outside the Owner's collection are hidden by default (`include_unowned=False`) and
  never carry price or purchase wording.
"""

from __future__ import annotations

import json
import statistics
from collections.abc import Mapping, Sequence
from typing import TypedDict

from . import builder, cache, universe
from .decks import color_set
from .store import COUNTED_SECTIONS, StudioStore

_BASIC_NAMES = frozenset(
    {
        "plains",
        "island",
        "swamp",
        "mountain",
        "forest",
        "wastes",
        "snow-covered plains",
        "snow-covered island",
        "snow-covered swamp",
        "snow-covered mountain",
        "snow-covered forest",
    }
)


class _DeckMeta(TypedDict):
    deck_id: str
    cohort: str
    play_group: str
    bracket: str | None
    platform: str
    url: str
    deck_date: str | None
    tags: str
    size: int


class _SourceIndex(TypedDict):
    decks: list[_DeckMeta]
    cohorts_by_deck: dict[str, set[str]]
    brackets_by_deck: dict[str, str | None]
    cards_by_deck: list[set[str]]
    postings: dict[str, list[int]]
    set_of_deck: list[int]  # decks with the same card set (without basic lands) share one id
    set_ids: dict[frozenset[str], int]


class _PoolInfo(TypedDict):
    card_id: str
    name: str
    owned: int
    available: int
    in_pool: bool
    basic: bool


def _canonical_name(owners: Mapping[str, list[str]], raw_name: str) -> str:
    found = owners.get(raw_name)
    if found:
        return found[0]
    return raw_name


def _basic_oracle_names(store: StudioStore) -> frozenset[str]:
    names = set(_BASIC_NAMES)
    for row in store.connection.execute(
        "SELECT oracle_name, type_line, is_basic_land FROM card_fact"
    ):
        type_line = str(row["type_line"] or "").split(" // ")[0]
        if bool(row["is_basic_land"]) or ("Basic" in type_line and "Land" in type_line):
            names.add(str(row["oracle_name"]).casefold())
    for row in store.connection.execute(
        "SELECT name, front_name, type_line FROM scryfall_card WHERE type_line LIKE '%Basic%Land%'"
    ):
        names.add(str(row["name"]).casefold())
        names.add(str(row["front_name"]).casefold())
    return frozenset(names)


def _commander_source_index(store: StudioStore, commander_names: Sequence[str]) -> _SourceIndex:
    return cache.cached(
        store,
        ("similar_decks_index", tuple(commander_names)),
        lambda: _build_commander_source_index(store, commander_names),
    )


def _build_commander_source_index(
    store: StudioStore, commander_names: Sequence[str]
) -> _SourceIndex:
    db = store.connection
    bound, bound_args = builder.bound_to("corpus_deck", "d.deck_id", commander_names)
    deck_rows = db.execute(
        "SELECT d.deck_id, d.cohort, d.url, d.platform, d.play_group, d.deck_date, d.tags "
        f"FROM corpus_deck d WHERE d.duplicate_of IS NULL{bound} ORDER BY d.deck_id ASC",
        bound_args,
    ).fetchall()
    if not deck_rows:
        return {
            "decks": [],
            "cohorts_by_deck": {},
            "brackets_by_deck": {},
            "cards_by_deck": [],
            "postings": {},
            "set_of_deck": [],
            "set_ids": {},
        }

    deck_ids = [str(r["deck_id"]) for r in deck_rows]
    idx_by_id = {did: i for i, did in enumerate(deck_ids)}

    cohorts_by_deck: dict[str, set[str]] = {did: {"all"} for did in deck_ids}
    brackets_by_deck: dict[str, str | None] = dict.fromkeys(deck_ids)
    for r in deck_rows:
        did = str(r["deck_id"])
        pg = str(r["play_group"] or "")
        if pg:
            cohorts_by_deck[did].add(pg)
        coh = str(r["cohort"] or "")
        if coh:
            cohorts_by_deck[did].add(coh)
            if coh.startswith("bracket:"):
                brackets_by_deck[did] = coh

    placeholders = ",".join("?" for _ in deck_ids)
    for row in db.execute(
        f"SELECT deck_id, cohort FROM corpus_cohort WHERE deck_id IN ({placeholders}) ORDER BY cohort",
        deck_ids,
    ):
        did = str(row["deck_id"])
        coh = str(row["cohort"])
        cohorts_by_deck[did].add(coh)
        if coh.startswith("bracket:") and brackets_by_deck.get(did) is None:
            brackets_by_deck[did] = coh

    owners = universe.spelling_owners(store)
    basics = _basic_oracle_names(store)
    cmd_cf = {str(c).casefold() for c in commander_names}
    sec_placeholders = ",".join("?" for _ in COUNTED_SECTIONS)

    cards_by_deck: list[set[str]] = [set() for _ in deck_ids]
    for row in db.execute(
        "SELECT deck_id, card_name FROM corpus_deck_card "
        f"WHERE deck_id IN ({placeholders}) AND quantity > 0 "
        f"AND LOWER(section) IN ({sec_placeholders})",
        [*deck_ids, *COUNTED_SECTIONS],
    ):
        did = str(row["deck_id"])
        raw_name = str(row["card_name"])
        canonical = _canonical_name(owners, raw_name)
        cf = canonical.casefold()
        if cf in basics or cf in cmd_cf:
            continue
        cards_by_deck[idx_by_id[did]].add(canonical)

    postings: dict[str, list[int]] = {}
    set_ids: dict[frozenset[str], int] = {}
    set_of_deck: list[int] = []
    for i, card_set in enumerate(cards_by_deck):
        for card_name in card_set:
            postings.setdefault(card_name, []).append(i)
        set_of_deck.append(set_ids.setdefault(frozenset(card_set), len(set_ids)))

    decks_meta: list[_DeckMeta] = [
        {
            "deck_id": str(r["deck_id"]),
            "cohort": str(r["cohort"] or ""),
            "play_group": str(r["play_group"] or ""),
            "bracket": brackets_by_deck.get(str(r["deck_id"])),
            "platform": str(r["platform"] or ""),
            "url": str(r["url"] or ""),
            "deck_date": str(r["deck_date"]) if r["deck_date"] is not None else None,
            "tags": str(r["tags"] or ""),
            "size": len(cards_by_deck[i]),
        }
        for i, r in enumerate(deck_rows)
    ]
    return {
        "decks": decks_meta,
        "cohorts_by_deck": cohorts_by_deck,
        "brackets_by_deck": brackets_by_deck,
        "cards_by_deck": cards_by_deck,
        "postings": postings,
        "set_of_deck": set_of_deck,
        "set_ids": set_ids,
    }


def _pool_lookup(
    store: StudioStore, commander_names: Sequence[str]
) -> tuple[dict[str, _PoolInfo], dict[str, str]]:
    """Return `(by_oracle_name, name_by_card_id)` for the commander's collection cards."""
    identity, _ = builder.commander_identity(store, commander_names)
    by_name: dict[str, _PoolInfo] = {}
    name_by_id: dict[str, str] = {}
    for row in store.connection.execute(
        "SELECT c.card_id, c.oracle_name, c.color_identity, c.commander_legal, "
        "c.type_line, c.is_basic_land, i.owned_lower_bound, i.available_lower_bound "
        "FROM card_fact c JOIN inventory i USING (card_id)"
    ):
        cid = str(row["card_id"])
        name = str(row["oracle_name"])
        name_by_id[cid] = name
        in_pool = row["commander_legal"] == 1 and color_set(row["color_identity"]) <= identity
        by_name[name] = {
            "card_id": cid,
            "name": name,
            "owned": int(row["owned_lower_bound"] or 0),
            "available": int(row["available_lower_bound"] or 0),
            "in_pool": bool(in_pool),
            "basic": bool(row["is_basic_land"])
            or ("Basic" in str(row["type_line"] or "") and "Land" in str(row["type_line"] or "")),
        }
    return by_name, name_by_id


class UnknownDeckSource(KeyError):
    """The revision, deck or variant that names the list to compare does not exist."""


def resolve_user_deck_cards(
    store: StudioStore,
    *,
    revision_id: str | None = None,
    deck_id: str | None = None,
    branch: str | None = None,
    card_ids: Sequence[str] | None = None,
) -> list[str]:
    """The card ids of the list to compare, from exactly one of: explicit ``card_ids``, a saved
    ``revision_id``, or a ``deck_id`` with a variant (``branch``, default ``main``): the working
    draft of the variant when there is one (the list the builder shows), else its newest saved
    revision. Raises ``ValueError`` (German sentence) for no source, several sources or a variant
    without a deck, and ``UnknownDeckSource`` for a revision, deck or variant that is not stored."""
    given = (card_ids is not None) + bool(revision_id) + bool(deck_id)
    if given != 1:
        raise ValueError(
            "Gib einen Stand, ein Deck mit Variante oder eine Kartenliste an (genau eines davon)."
        )
    if branch and not deck_id:
        raise ValueError("Gib ein Deck an: eine Variante gehört immer zu einem Deck.")
    if card_ids is not None:
        return [str(cid) for cid in card_ids if cid]
    db = store.connection

    def revision_cards(revision: str) -> list[str]:
        return [
            str(r["card_id"])
            for r in db.execute(
                "SELECT card_id FROM deck_revision_card WHERE revision_id = ? AND quantity > 0",
                (revision,),
            )
        ]

    if revision_id:
        if db.execute("SELECT 1 FROM deck_revision WHERE revision_id = ?", (revision_id,)).fetchone() is None:
            raise UnknownDeckSource("revision")
        return revision_cards(revision_id)
    if db.execute("SELECT 1 FROM deck WHERE deck_id = ?", (deck_id,)).fetchone() is None:
        raise UnknownDeckSource("deck")
    variant = branch or "main"
    draft = db.execute(
        "SELECT cards FROM deck_draft WHERE deck_id = ? AND branch = ?", (deck_id, variant)
    ).fetchone()
    if draft is not None:
        parsed = json.loads(str(draft["cards"]))
        return [str(item["card_id"]) for item in parsed if int(item.get("quantity", 0)) > 0]
    head = db.execute(
        "SELECT revision_id FROM deck_branch WHERE deck_id = ? AND branch = ?", (deck_id, variant)
    ).fetchone()
    if head is None:
        raise UnknownDeckSource("deck variant")
    return revision_cards(str(head["revision_id"]))


METHOD = "jaccard_without_basic_lands"
NOTE = "Ähnlich heißt: gleiche Karten, nicht: erfolgreich."
EMPTY_GROUP = "zu wenige Decks in dieser Gruppe"
EMPTY_DECK = "Dein Deck hat noch keine Karten zum Vergleichen (Standardländer und Commander zählen nicht)."


def _frame(
    cohort: str,
    requested: int,
    considered: int,
    user_cards: int,
    **more: object,
) -> dict[str, object]:
    """The answer without neighbours (an empty group or an empty deck): never an error."""
    return {
        "decks_considered": considered,
        "n": 0,
        "n_requested": requested,
        "cohort": cohort,
        "method": METHOD,
        "note": NOTE,
        "min_hits": 0,
        "small_group": considered < builder.SMALL_DENOMINATOR,
        "small_group_limit": builder.SMALL_DENOMINATOR,
        "identical_to_deck": 0,
        "duplicates_removed": 0,
        "user_nonbasic_cards": user_cards,
        "median_similarity_all": None,
        "nearest": [],
        "they_play_you_dont": [],
        "you_play_they_dont": [],
        **more,
    }


def find_similar_decks(
    store: StudioStore,
    commander_names: Sequence[str],
    *,
    deck_card_ids: Sequence[str] = (),
    deck_card_names: Sequence[str] = (),
    cohort: str = "all",
    n: int = 20,
    include_unowned: bool = False,
) -> dict[str, object]:
    """Jaccard similarity of a deck list against the source decks of the commander, without
    basic lands and without the commander. Counting only: nothing here says a deck is good.

    - A source deck counts once per card set (the lowest deck id keeps it), and a source deck
      with exactly the compared card set (the deck itself) is left out.
    - Order: similarity descending, then deck id ascending (an exact fraction, no rounding ties).
    - ``they_play_you_dont``: cards in at least ``ceil(0.4 * n)`` of the ``n`` neighbours that the
      deck does not have; cards outside the collection only with ``include_unowned``.
    - ``you_play_they_dont``: deck cards that at most one neighbour plays (``none_play`` marks 0).
    - Every count carries its denominator (``hits`` of ``of``); an empty group or deck answers
      with ``empty_reason`` and empty lists."""
    if not commander_names:
        raise ValueError("commander is required")
    requested = max(1, min(int(n), 100))
    by_name, name_by_id = _pool_lookup(store, commander_names)
    basics = _basic_oracle_names(store)
    cmd_cf = {str(c).casefold() for c in commander_names}
    owners = universe.spelling_owners(store)

    user_cards: set[str] = set()
    for cid in deck_card_ids:
        cname = name_by_id.get(str(cid))
        if cname:
            canonical = _canonical_name(owners, cname)
            if canonical.casefold() not in basics and canonical.casefold() not in cmd_cf:
                user_cards.add(canonical)
    for raw in deck_card_names:
        canonical = _canonical_name(owners, str(raw))
        if canonical.casefold() not in basics and canonical.casefold() not in cmd_cf:
            user_cards.add(canonical)

    index = _commander_source_index(store, commander_names)
    decks_meta = index["decks"]
    cohorts_by_deck = index["cohorts_by_deck"]
    cards_by_deck = index["cards_by_deck"]
    postings = index["postings"]
    set_of_deck = index["set_of_deck"]

    allowed = [
        i
        for i, d in enumerate(decks_meta)
        if cohort in cohorts_by_deck.get(d["deck_id"], set()) and d["size"] > 0
    ]
    own_set = index["set_ids"].get(frozenset(user_cards)) if user_cards else None
    identical = sum(1 for i in allowed if own_set is not None and set_of_deck[i] == own_set)
    seen_sets: set[int] = set()
    kept: list[int] = []  # decks_meta is ordered by deck id: the lowest id keeps a card set
    for i in allowed:
        if set_of_deck[i] == own_set or set_of_deck[i] in seen_sets:
            continue
        seen_sets.add(set_of_deck[i])
        kept.append(i)
    removed = len(allowed) - identical - len(kept)
    if not kept:
        return _frame(
            cohort, requested, 0, len(user_cards), empty_reason=EMPTY_GROUP,
            identical_to_deck=identical, duplicates_removed=removed,
        )  # fmt: skip
    if not user_cards:
        return _frame(
            cohort, requested, len(kept), 0, empty_reason=EMPTY_DECK,
            duplicates_removed=removed,
        )  # fmt: skip

    shared_by_idx = [0] * len(decks_meta)
    for cname in user_cards:
        for idx in postings.get(cname, ()):
            shared_by_idx[idx] += 1

    u_size = len(user_cards)
    scored: list[tuple[float, str, int]] = []
    for idx in kept:
        shared = shared_by_idx[idx]
        # Equal fractions give equal floats (correctly rounded division), so a tie stays a tie.
        scored.append((-(shared / (u_size + decks_meta[idx]["size"] - shared)), decks_meta[idx]["deck_id"], idx))
    scored.sort()
    top = scored[:requested]
    k = len(top)
    nearest: list[dict[str, object]] = []
    for score, did, idx in top:
        meta = decks_meta[idx]
        nearest.append(
            {
                "deck_id": did,
                "similarity": round(-score, 4),
                "shared": shared_by_idx[idx],
                "size": meta["size"],
                "bracket": meta["bracket"],
                "cohort": meta["cohort"],
                "play_group": meta["play_group"],
                "platform": meta["platform"],
                "url": meta["url"],
                "deck_date": meta["deck_date"],
            }
        )
    median_sim = round(float(statistics.median(-item[0] for item in scored)), 4)

    hits_of: dict[str, int] = {}
    for _score, _did, idx in top:
        for cname in cards_by_deck[idx]:
            hits_of[cname] = hits_of.get(cname, 0) + 1
    min_hits = (2 * k + 4) // 5  # ceil(0.4 * k) in whole numbers

    def row(cname: str, hits: int) -> dict[str, object]:
        info = by_name.get(cname)
        return {
            "card_id": info["card_id"] if info is not None else None,
            "name": cname,
            "hits": hits,
            "of": k,
            "share": round(hits / k, 4),
            "owned": info["owned"] if info is not None else 0,
            "available": info["available"] if info is not None else 0,
            "in_pool": info["in_pool"] if info is not None else False,
        }

    they_play: list[dict[str, object]] = []
    for cname, hits in sorted(hits_of.items(), key=lambda item: (-item[1], item[0])):
        if cname in user_cards or hits < min_hits:
            continue
        found = row(cname, hits)
        if not include_unowned and (not found["in_pool"] or int(found["owned"]) <= 0):  # type: ignore[call-overload]
            continue
        they_play.append(found)

    you_play: list[dict[str, object]] = []
    for cname in sorted(user_cards, key=lambda name: (hits_of.get(name, 0), name)):
        hits = hits_of.get(cname, 0)
        if hits <= 1:
            you_play.append({**row(cname, hits), "none_play": hits == 0})

    return {
        "decks_considered": len(kept),
        "n": k,
        "n_requested": requested,
        "cohort": cohort,
        "method": METHOD,
        "note": NOTE,
        "empty_reason": None,
        "min_hits": min_hits,
        "small_group": len(kept) < builder.SMALL_DENOMINATOR,
        "small_group_limit": builder.SMALL_DENOMINATOR,
        "identical_to_deck": identical,
        "duplicates_removed": removed,
        "user_nonbasic_cards": u_size,
        "median_similarity_all": median_sim,
        "nearest": nearest,
        "they_play_you_dont": they_play,
        "you_play_they_dont": you_play,
    }


def browse_decks(
    store: StudioStore,
    *,
    commander: str = "",
    q: str = "",
    origin: str = "all",
    cohort: str = "all",
    label: str = "",
    must_contain: Sequence[str] = (),
    must_not_contain: Sequence[str] = (),
    include_unowned: bool = False,
    limit_decks: int = 100,
    limit_cards: int = 60,
) -> dict[str, object]:
    """Read-only Deck-Browser (#1323 & #1404 Proposal 5): filter saved Studio decks and
    non-duplicate source decks by commander, search query, origin, cohort/bracket, label,
    must-contain cards, and must-not-contain cards, and compute card co-occurrence (`n/N` and `%`)
    across the filtered deck set.
    """
    from .labels import deck_labels as _deck_labels

    db = store.connection
    owners = universe.spelling_owners(store)
    basics = _basic_oracle_names(store)

    must_in = {
        _canonical_name(owners, name.strip()).casefold()
        for name in must_contain
        if name and name.strip()
    }
    must_out = {
        _canonical_name(owners, name.strip()).casefold()
        for name in must_not_contain
        if name and name.strip()
    }
    q_cf = q.strip().casefold()
    label_cf = label.strip().casefold()
    cmd_filter = commander.strip()

    # Pool lookup for ownership badges
    owned_by_name: dict[str, tuple[str, int, int]] = {}
    for row in db.execute(
        "SELECT c.card_id, c.oracle_name, i.owned_lower_bound, i.available_lower_bound "
        "FROM card_fact c JOIN inventory i USING (card_id)"
    ):
        owned_by_name[str(row["oracle_name"])] = (
            str(row["card_id"]),
            int(row["owned_lower_bound"] or 0),
            int(row["available_lower_bound"] or 0),
        )

    matched_decks: list[dict[str, object]] = []
    matched_card_sets: list[set[str]] = []

    # 1. Saved Studio decks (each branch revision)
    if origin in ("all", "saved") and cohort == "all":
        labels_by_deck = _deck_labels(store)
        for drow in db.execute(
            "SELECT d.deck_id, d.name, b.branch, b.revision_id, r.created_at "
            "FROM deck d "
            "JOIN deck_branch b USING (deck_id) "
            "JOIN deck_revision r ON r.revision_id = b.revision_id "
            "ORDER BY d.name ASC, b.branch ASC"
        ):
            did = str(drow["deck_id"])
            branch = str(drow["branch"])
            rev_id = str(drow["revision_id"])
            d_labels = labels_by_deck.get(did, [])
            if label_cf and not any(lbl.casefold() == label_cf for lbl in d_labels):
                continue

            crows = db.execute(
                "SELECT f.oracle_name, rc.zone, rc.quantity "
                "FROM deck_revision_card rc JOIN card_fact f USING (card_id) "
                "WHERE rc.revision_id = ? AND rc.quantity > 0",
                (rev_id,),
            ).fetchall()
            cmds = sorted(str(r["oracle_name"]) for r in crows if str(r["zone"]) == "commander")
            if cmd_filter and cmd_filter not in cmds:
                continue

            display_name = f"{drow['name']} ({branch})" if branch != "main" else str(drow["name"])
            if q_cf:
                hay = f"{display_name} {' '.join(cmds)} {' '.join(d_labels)}".casefold()
                if q_cf not in hay:
                    continue

            all_names_cf = {
                _canonical_name(owners, str(r["oracle_name"])).casefold() for r in crows
            }
            if must_in and not (must_in <= all_names_cf):
                continue
            if must_out and (must_out & all_names_cf):
                continue

            cmd_cf_set = {c.casefold() for c in cmds}
            nonbasic_cards: set[str] = {
                _canonical_name(owners, str(r["oracle_name"]))
                for r in crows
                if str(r["oracle_name"]).casefold() not in basics
                and str(r["oracle_name"]).casefold() not in cmd_cf_set
            }
            total_qty = sum(int(r["quantity"]) for r in crows)
            matched_decks.append(
                {
                    "id": f"saved:{did}:{branch}",
                    "deck_id": did,
                    "branch": branch,
                    "revision_id": rev_id,
                    "origin": "saved",
                    "name": display_name,
                    "commander": " // ".join(cmds),
                    "cohort": "saved",
                    "bracket": None,
                    "platform": "Studio",
                    "url": "",
                    "deck_date": str(drow["created_at"])[:10],
                    "labels": d_labels,
                    "cards": total_qty,
                }
            )
            matched_card_sets.append(nonbasic_cards)

    # 2. Read-only source decks
    if origin in ("all", "source"):
        if cmd_filter:
            commander_list = [cmd_filter]
        else:
            commander_list = [
                str(r[0])
                for r in db.execute(
                    "SELECT DISTINCT commander_name FROM commander_binding WHERE kind = 'corpus_deck' ORDER BY 1"
                )
            ]
        for cname in commander_list:
            idx = _commander_source_index(store, [cname])
            decks_meta = idx["decks"]
            cohorts_by_deck = idx["cohorts_by_deck"]
            cards_by_deck = idx["cards_by_deck"]
            for i, meta in enumerate(decks_meta):
                did = meta["deck_id"]
                if cohort != "all" and cohort not in cohorts_by_deck.get(did, set()):
                    continue
                tags_raw = meta["tags"]
                deck_tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
                if label_cf and not any(label_cf in t.casefold() for t in deck_tags):
                    continue
                if q_cf:
                    hay = f"{did} {cname} {meta['platform']} {meta['cohort']} {tags_raw}".casefold()
                    if q_cf not in hay:
                        continue
                cset = cards_by_deck[i]
                cset_cf = {c.casefold() for c in cset}
                if must_in and not (must_in <= cset_cf):
                    continue
                if must_out and (must_out & cset_cf):
                    continue
                matched_decks.append(
                    {
                        "id": f"source:{did}",
                        "deck_id": did,
                        "branch": None,
                        "revision_id": None,
                        "origin": "source",
                        "name": did,
                        "commander": cname,
                        "cohort": meta["cohort"],
                        "bracket": meta["bracket"],
                        "platform": meta["platform"],
                        "url": meta["url"],
                        "deck_date": meta["deck_date"],
                        "labels": deck_tags,
                        "cards": meta["size"],
                    }
                )
                matched_card_sets.append(cset)

    total_decks = len(matched_decks)
    card_counts: dict[str, int] = {}
    for cset in matched_card_sets:
        for cname in cset:
            if cname.casefold() in must_in:
                continue
            card_counts[cname] = card_counts.get(cname, 0) + 1

    co_keyed: list[tuple[int, str, dict[str, object]]] = []
    for cname, hits in card_counts.items():
        pinfo = owned_by_name.get(cname)
        cid_val = pinfo[0] if pinfo is not None else None
        owned = pinfo[1] if pinfo is not None else 0
        available = pinfo[2] if pinfo is not None else 0
        if not include_unowned and owned <= 0:
            continue
        co_keyed.append(
            (
                -hits,
                cname,
                {
                    "card_id": cid_val,
                    "name": cname,
                    "decks": hits,
                    "of": total_decks,
                    "share": round(hits / total_decks, 4) if total_decks > 0 else 0.0,
                    "owned": owned,
                    "available": available,
                    "in_collection": owned > 0,
                },
            )
        )
    co_keyed.sort(key=lambda item: (item[0], item[1]))
    cooccurrence = [item[2] for item in co_keyed]

    return {
        "total_decks": total_decks,
        "small_sample": 0 < total_decks < builder.SMALL_DENOMINATOR,
        "small_denominator": builder.SMALL_DENOMINATOR,
        "filters": {
            "commander": cmd_filter,
            "q": q,
            "origin": origin,
            "cohort": cohort,
            "label": label,
            "must_contain": list(must_contain),
            "must_not_contain": list(must_not_contain),
            "include_unowned": include_unowned,
        },
        "decks": matched_decks[: max(1, min(int(limit_decks), 500))],
        "cooccurrence": cooccurrence[: max(1, min(int(limit_cards), 300))],
        "total_cooccurrence_cards": len(cooccurrence),
    }


def get_browser_deck_detail(store: StudioStore, item_id: str) -> dict[str, object]:
    """Return the read-only card list of a saved Studio deck (`saved:<deck_id>:<branch>`) or
    a source deck (`source:<deck_id>`) for inspection in the Deck-Browser."""
    db = store.connection
    owners = universe.spelling_owners(store)
    owned_by_name: dict[str, tuple[str, int, int]] = {}
    for row in db.execute(
        "SELECT c.card_id, c.oracle_name, i.owned_lower_bound, i.available_lower_bound "
        "FROM card_fact c JOIN inventory i USING (card_id)"
    ):
        owned_by_name[str(row["oracle_name"])] = (
            str(row["card_id"]),
            int(row["owned_lower_bound"] or 0),
            int(row["available_lower_bound"] or 0),
        )

    if item_id.startswith("saved:"):
        parts = item_id.split(":", 2)
        if len(parts) != 3:
            raise KeyError(item_id)
        _, did, branch = parts
        row = db.execute(
            "SELECT d.name, b.revision_id FROM deck d JOIN deck_branch b USING (deck_id) "
            "WHERE d.deck_id = ? AND b.branch = ?",
            (did, branch),
        ).fetchone()
        if row is None:
            raise KeyError(item_id)
        cards = [
            {
                "name": str(r["oracle_name"]),
                "quantity": int(r["quantity"]),
                "section": str(r["zone"]),
                "card_id": str(r["card_id"]),
                "in_collection": True,
                "owned": int(r["owned_lower_bound"] or 0),
                "available": int(r["available_lower_bound"] or 0),
            }
            for r in db.execute(
                "SELECT rc.card_id, rc.zone, rc.quantity, f.oracle_name, "
                "i.owned_lower_bound, i.available_lower_bound "
                "FROM deck_revision_card rc "
                "JOIN card_fact f USING (card_id) "
                "JOIN inventory i USING (card_id) "
                "WHERE rc.revision_id = ? ORDER BY rc.zone ASC, f.oracle_name ASC",
                (str(row["revision_id"]),),
            )
        ]
        return {
            "id": item_id,
            "origin": "saved",
            "name": f"{row['name']} ({branch})" if branch != "main" else str(row["name"]),
            "cards": cards,
        }

    did = item_id.removeprefix("source:")
    drow = db.execute(
        "SELECT deck_id, cohort, url, platform, play_group, deck_date, tags "
        "FROM corpus_deck WHERE deck_id = ?",
        (did,),
    ).fetchone()
    if drow is None:
        raise KeyError(item_id)
    sec_placeholders = ",".join("?" for _ in COUNTED_SECTIONS)
    cards = []
    for r in db.execute(
        "SELECT card_name, quantity, section FROM corpus_deck_card "
        f"WHERE deck_id = ? AND quantity > 0 AND LOWER(section) IN ({sec_placeholders}) "
        "ORDER BY section ASC, card_name ASC",
        (did, *COUNTED_SECTIONS),
    ):
        raw_name = str(r["card_name"])
        canonical = _canonical_name(owners, raw_name)
        pinfo = owned_by_name.get(canonical)
        cid_val = pinfo[0] if pinfo is not None else None
        owned = pinfo[1] if pinfo is not None else 0
        available = pinfo[2] if pinfo is not None else 0
        cards.append(
            {
                "name": canonical,
                "quantity": int(r["quantity"]),
                "section": str(r["section"]),
                "card_id": cid_val,
                "in_collection": owned > 0,
                "owned": owned,
                "available": available,
            }
        )
    return {
        "id": f"source:{did}",
        "origin": "source",
        "name": did,
        "cohort": str(drow["cohort"] or ""),
        "platform": str(drow["platform"] or ""),
        "url": str(drow["url"] or ""),
        "deck_date": drow["deck_date"],
        "cards": cards,
    }
