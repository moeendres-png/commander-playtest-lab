"""Similar source decks (Proposal 3, #1404) and read-only Deck-Browser (Proposal 5, #1323).

All calculations are purely descriptive counts and set overlaps (Jaccard similarity over
non-basic maindeck cards, and card frequencies across filtered deck sets).
- Never claims that similarity or frequency implies deck strength or tournament success.
- Basic lands and the commander itself are excluded from Jaccard similarity.
- Duplicate source decks (`duplicate_of IS NOT NULL`) are excluded.
- Tie-break for nearest source decks is deterministic by `deck_id` ascending.
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


class _PoolInfo(TypedDict):
    card_id: str
    name: str
    owned: int
    available: int
    in_pool: bool
    basic: bool


def _canonical_name(owners: Mapping[str, list[str]], raw_name: str) -> str:
    """The collection card a deck spelling names. ``owners`` (``universe.spelling_owners``) is
    keyed by the casefolded spelling, so the lookup casefolds too: a deck listing only the
    front face of a two-faced or adventure card counts for that card."""
    found = owners.get(raw_name.casefold())
    if found:
        exact = [cand for cand in found if cand.casefold() == raw_name.casefold()]
        return sorted(exact)[0] if exact else sorted(found)[0]
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

    for cohs in cohorts_by_deck.values():
        if cohs & {"bracket:4", "bracket:5"}:
            cohs.add("tuned")

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
    for i, card_set in enumerate(cards_by_deck):
        for card_name in card_set:
            postings.setdefault(card_name, []).append(i)

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


def resolve_user_deck_cards(
    store: StudioStore,
    *,
    revision_id: str | None = None,
    deck_id: str | None = None,
    branch: str = "main",
    card_ids: Sequence[str] | None = None,
) -> list[str]:
    """Resolve a list of `card_id`s from explicit `card_ids`, a `revision_id`, or `deck_id`+`branch`."""
    if card_ids is not None:
        return [str(cid) for cid in card_ids if cid]
    db = store.connection
    if revision_id:
        return [
            str(r["card_id"])
            for r in db.execute(
                "SELECT card_id FROM deck_revision_card WHERE revision_id = ? AND quantity > 0",
                (revision_id,),
            )
        ]
    if deck_id:
        draft = db.execute(
            "SELECT cards FROM deck_draft WHERE deck_id = ? AND branch = ?",
            (deck_id, branch),
        ).fetchone()
        if draft is not None:
            parsed = json.loads(str(draft["cards"]))
            return [str(item["card_id"]) for item in parsed if int(item.get("quantity", 0)) > 0]
        rev = db.execute(
            "SELECT revision_id FROM deck_branch WHERE deck_id = ? AND branch = ?",
            (deck_id, branch),
        ).fetchone()
        if rev is not None:
            return [
                str(r["card_id"])
                for r in db.execute(
                    "SELECT card_id FROM deck_revision_card WHERE revision_id = ? AND quantity > 0",
                    (str(rev["revision_id"]),),
                )
            ]
    return []


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
    """Compute Jaccard similarity against non-duplicate source decks of `commander_names`
    (without basic lands and without the commander).
    """
    if not commander_names:
        raise ValueError("commander is required")
    n = max(1, min(int(n), 100))
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

    allowed_indices = [
        i
        for i, d in enumerate(decks_meta)
        if cohort in cohorts_by_deck.get(d["deck_id"], set()) and d["size"] > 0
    ]
    if not allowed_indices:
        return {
            "decks_considered": 0,
            "n": n,
            "cohort": cohort,
            "method": "jaccard_nonbasic",
            "note": "Ähnlich heißt gleiche Karten (ohne Standardländer), nicht erfolgreich.",
            "empty_reason": f"Keine Quelldecks in der Gruppe „{cohort}“ vorhanden.",
            "user_nonbasic_cards": len(user_cards),
            "median_similarity_all": None,
            "nearest": [],
            "they_play_you_dont": [],
            "you_play_they_dont": [],
        }

    if not user_cards:
        return {
            "decks_considered": len(allowed_indices),
            "n": n,
            "cohort": cohort,
            "method": "jaccard_nonbasic",
            "note": "Ähnlich heißt gleiche Karten (ohne Standardländer), nicht erfolgreich.",
            "empty_reason": "Dein Deck enthält noch keine Nicht-Standardländer-Karten zum Vergleichen.",
            "user_nonbasic_cards": 0,
            "median_similarity_all": 0.0,
            "nearest": [],
            "they_play_you_dont": [],
            "you_play_they_dont": [],
        }

    shared_by_idx = [0] * len(decks_meta)
    for cname in user_cards:
        for idx in postings.get(cname, ()):
            shared_by_idx[idx] += 1

    u_size = len(user_cards)
    scored: list[tuple[float, int, str, int, dict[str, object]]] = []
    all_sims: list[float] = []
    for idx in allowed_indices:
        meta = decks_meta[idx]
        d_size = meta["size"]
        shared = shared_by_idx[idx]
        union = u_size + d_size - shared
        sim = round(shared / union, 4) if union > 0 else 0.0
        all_sims.append(sim)
        did = meta["deck_id"]
        scored.append(
            (
                -sim,
                -shared,
                did,
                idx,
                {
                    "deck_id": did,
                    "similarity": sim,
                    "shared": shared,
                    "size": d_size,
                    "bracket": meta["bracket"],
                    "cohort": meta["cohort"],
                    "play_group": meta["play_group"],
                    "platform": meta["platform"],
                    "url": meta["url"],
                    "deck_date": meta["deck_date"],
                },
            )
        )

    # Sort by similarity DESC, shared DESC, deck_id ASC (deterministic tie-break)
    scored.sort(key=lambda item: (item[0], item[1], item[2]))
    top = scored[:n]
    nearest = [item[4] for item in top]
    nearest_indices = [item[3] for item in top]
    k = len(nearest)
    median_sim = round(float(statistics.median(all_sims)), 4) if all_sims else None

    # Count cards across the nearest k source decks
    nearest_card_hits: dict[str, int] = {}
    for idx in nearest_indices:
        for cname in cards_by_deck[idx]:
            nearest_card_hits[cname] = nearest_card_hits.get(cname, 0) + 1

    they_play_keyed: list[tuple[int, str, dict[str, object]]] = []
    for cname, hits in nearest_card_hits.items():
        if cname in user_cards:
            continue
        pinfo = by_name.get(cname)
        owned = pinfo["owned"] if pinfo is not None else 0
        available = pinfo["available"] if pinfo is not None else 0
        in_pool = pinfo["in_pool"] if pinfo is not None else False
        if not include_unowned and (not in_pool or owned <= 0):
            continue
        they_play_keyed.append(
            (
                -hits,
                cname,
                {
                    "card_id": pinfo["card_id"] if pinfo is not None else None,
                    "name": cname,
                    "hits": hits,
                    "of": k,
                    "share": round(hits / k, 4) if k > 0 else 0.0,
                    "owned": owned,
                    "available": available,
                    "in_pool": in_pool,
                },
            )
        )
    they_play_keyed.sort(key=lambda item: (item[0], item[1]))
    they_play = [item[2] for item in they_play_keyed]

    you_play_keyed: list[tuple[int, str, dict[str, object]]] = []
    for cname in sorted(user_cards):
        hits = nearest_card_hits.get(cname, 0)
        pinfo = by_name.get(cname)
        you_play_keyed.append(
            (
                hits,
                cname,
                {
                    "card_id": pinfo["card_id"] if pinfo is not None else None,
                    "name": cname,
                    "hits": hits,
                    "of": k,
                    "share": round(hits / k, 4) if k > 0 else 0.0,
                    "owned": pinfo["owned"] if pinfo is not None else 0,
                    "available": pinfo["available"] if pinfo is not None else 0,
                    "in_pool": pinfo["in_pool"] if pinfo is not None else False,
                },
            )
        )
    you_play_keyed.sort(key=lambda item: (item[0], item[1]))
    you_play = [item[2] for item in you_play_keyed]

    return {
        "decks_considered": len(allowed_indices),
        "n": k,
        "cohort": cohort,
        "method": "jaccard_nonbasic",
        "note": "Ähnlich heißt gleiche Karten (ohne Standardländer), nicht erfolgreich.",
        "empty_reason": None,
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
