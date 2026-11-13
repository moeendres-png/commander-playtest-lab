"""Read models and working state of the deck builder.

Everything here is counted from stored rows. A figure about source decks always comes with
its denominator; nothing here rates a card.
"""

from __future__ import annotations

import functools
import json
import math
import re
import sqlite3
from collections import Counter
from collections.abc import Iterable, Sequence
from statistics import median

from commander_lab.deck_readiness import (
    _CARD_FACTS_PATH,
    _PILOT_KNOWLEDGE_PATH,
    _CardData,
)
from commander_lab.deck_variant import compare_variant, comparison_to_dict
from commander_lab.models import RulesDeckInput

from .decks import RevisionCard, color_set, list_rows
from .store import BINDING_KINDS, StudioStore, now_utc


@functools.lru_cache(maxsize=1)
def _sim_card_data() -> _CardData:
    return _CardData(_CARD_FACTS_PATH, _PILOT_KNOWLEDGE_PATH)


@functools.lru_cache(maxsize=4096)
def sim_readiness_status(card_name: str) -> str:
    """Simulator readiness of ``card_name`` against the repo XMage card facts and pilot catalog."""
    try:
        return _sim_card_data().status_of(card_name).value
    except (OSError, ValueError):
        return "UNKNOWN"


def sim_readiness_available() -> bool:
    """Whether the repo card-fact files behind the readiness status can be read at all."""
    try:
        _sim_card_data()
    except (OSError, ValueError):
        return False
    return True


def _sim_readiness_summary(cards: list[dict[str, object]]) -> dict[str, object]:
    by_status = Counter(str(card["sim_status"]) for card in cards)
    return {
        "available": sim_readiness_available(),
        "ready": by_status.get("OK", 0),
        "total": len(cards),
        "by_status": dict(sorted(by_status.items())),
    }


ALL_DECKS = "all"
SMALL_DENOMINATOR = 30
_TYPE_ORDER = (
    "Land", "Creature", "Planeswalker", "Battle", "Artifact", "Enchantment", "Instant", "Sorcery",
)  # fmt: skip
_SYMBOL = re.compile(r"\{([^}]+)\}")


def main_type(type_line: str | None) -> str:
    """The group a card is listed under: the first fitting type of its front face."""
    front = (type_line or "").split(" // ")[0]
    for name in _TYPE_ORDER:
        if name in front:
            return name
    return "Other"


def bound_to(kind: str, column: str, commander_names: Sequence[str]) -> tuple[str, list[str]]:
    """SQL condition (starting with ``AND``) and its parameters: the row whose key is
    ``column`` is bound to every named commander. Source data is never read without it, so
    the figures of two commanders cannot be mixed. No commander means no row."""
    if kind not in BINDING_KINDS:
        raise ValueError(kind)
    if not commander_names:
        return " AND 0", []
    one = (
        " AND EXISTS (SELECT 1 FROM commander_binding cb WHERE "
        f"cb.kind = '{kind}' AND cb.key = {column} AND cb.commander_name = ?)"
    )
    # Exactly the named commanders: a row bound to a pair is not a row of one of them.
    exact = (
        " AND (SELECT COUNT(*) FROM commander_binding cb WHERE "
        f"cb.kind = '{kind}' AND cb.key = {column}) = {len(set(commander_names))}"
    )
    return one * len(commander_names) + exact, [str(name) for name in commander_names]


def corpus_binding(store: StudioStore, commander_names: Sequence[str]) -> dict[str, object]:
    """How many distinct source decks are bound to the commander, to another one, or to none."""
    db = store.connection
    bound, bound_args = bound_to("corpus_deck", "d.deck_id", commander_names)
    total = int(
        db.execute("SELECT COUNT(*) FROM corpus_deck WHERE duplicate_of IS NULL").fetchone()[0]
    )
    mine = int(
        db.execute(
            f"SELECT COUNT(*) FROM corpus_deck d WHERE d.duplicate_of IS NULL{bound}", bound_args
        ).fetchone()[0]
    )
    unbound = int(
        db.execute(
            "SELECT COUNT(*) FROM corpus_deck d WHERE d.duplicate_of IS NULL AND NOT EXISTS "
            "(SELECT 1 FROM commander_binding cb WHERE cb.kind = 'corpus_deck' "
            "AND cb.key = d.deck_id)"
        ).fetchone()[0]
    )
    return {
        "commander": list(commander_names),
        "bound_decks": mine,
        "other_commander_decks": total - mine - unbound,
        "unbound_decks": unbound,
    }


def list_commanders(
    store: StudioStore, *, include_collection: bool = False
) -> list[dict[str, object]]:
    """Commanders the Studio knows: those of saved decks and those source data is bound to.

    ``in_collection`` says whether the card is in the collection (the pool needs it there).
    With ``include_collection`` the Commander-legal legendary creatures of the collection are
    listed too (``has_data`` False), so a commander without any data yet can be chosen."""
    db = store.connection
    found: dict[str, dict[str, object]] = {}

    def entry(name: str) -> dict[str, object]:
        return found.setdefault(
            name, {"name": name, "saved_decks": 0, "source_decks": 0, "observation_cohorts": 0}
        )

    for row in db.execute(
        "SELECT f.oracle_name AS name, COUNT(DISTINCT b.deck_id) AS n FROM deck_branch b "
        "JOIN deck_revision_card rc ON rc.revision_id = b.revision_id AND rc.zone = 'commander' "
        "JOIN card_fact f ON f.card_id = rc.card_id GROUP BY f.oracle_name"
    ):
        entry(str(row["name"]))["saved_decks"] = int(row["n"])
    for row in db.execute(
        "SELECT cb.commander_name AS name, COUNT(*) AS n FROM commander_binding cb "
        "JOIN corpus_deck d ON d.deck_id = cb.key AND d.duplicate_of IS NULL "
        "WHERE cb.kind = 'corpus_deck' GROUP BY cb.commander_name"
    ):
        entry(str(row["name"]))["source_decks"] = int(row["n"])
    for row in db.execute(
        "SELECT commander_name AS name, COUNT(*) AS n FROM commander_binding "
        "WHERE kind = 'observation_cohort' GROUP BY commander_name"
    ):
        entry(str(row["name"]))["observation_cohorts"] = int(row["n"])
    for name, item in found.items():
        fact = db.execute(
            "SELECT card_id, color_identity FROM card_fact WHERE oracle_name = ?", (name,)
        ).fetchone()
        item["in_collection"] = fact is not None
        item["card_id"] = None if fact is None else str(fact["card_id"])
        item["identity"] = None if fact is None else fact["color_identity"]
        item["has_data"] = True
    if include_collection:
        for row in db.execute(
            "SELECT c.card_id, c.oracle_name, c.color_identity, c.type_line, c.oracle_text "
            "FROM card_fact c JOIN inventory i USING (card_id) WHERE c.commander_legal = 1"
        ):
            front = str(row["type_line"] or "").split(" // ")[0]
            legendary_creature = "Legendary" in front and "Creature" in front
            named = "can be your commander" in str(row["oracle_text"] or "")
            if (legendary_creature or named) and str(row["oracle_name"]) not in found:
                found[str(row["oracle_name"])] = {
                    "name": str(row["oracle_name"]),
                    "saved_decks": 0,
                    "source_decks": 0,
                    "observation_cohorts": 0,
                    "in_collection": True,
                    "card_id": str(row["card_id"]),
                    "identity": row["color_identity"],
                    "has_data": False,
                }
    return sorted(found.values(), key=lambda item: str(item["name"]))


def cohort_sizes(store: StudioStore, commander_names: Sequence[str]) -> dict[str, int]:
    """Distinct source decks of the commander per group: all, each play group, each named
    cohort. ``all`` means all decks bound to this commander, never all decks of the store."""
    db = store.connection
    if not commander_names:
        return {}
    bound, bound_args = bound_to("corpus_deck", "d.deck_id", commander_names)
    sizes = {
        ALL_DECKS: int(
            db.execute(
                f"SELECT COUNT(*) FROM corpus_deck d WHERE d.duplicate_of IS NULL{bound}",
                bound_args,
            ).fetchone()[0]
        )
    }
    for row in db.execute(
        "SELECT d.play_group, COUNT(*) AS n FROM corpus_deck d WHERE d.duplicate_of IS NULL"
        f"{bound} GROUP BY d.play_group ORDER BY n DESC",
        bound_args,
    ):
        sizes[str(row["play_group"])] = int(row["n"])
    for row in db.execute(
        "SELECT c.cohort, COUNT(*) AS n FROM corpus_cohort c JOIN corpus_deck d USING (deck_id) "
        f"WHERE d.duplicate_of IS NULL{bound} GROUP BY c.cohort ORDER BY c.cohort",
        bound_args,
    ):
        sizes[str(row["cohort"])] = int(row["n"])
    return sizes


def _corpus_hits(store: StudioStore, commander_names: Sequence[str]) -> dict[str, dict[str, int]]:
    """``{card key: {cohort: decks}}`` over the decks bound to the commander; the key is the
    oracle id, else the card name."""
    db = store.connection
    hits: dict[str, dict[str, int]] = {}
    if not commander_names:
        return hits
    bound, bound_args = bound_to("corpus_deck", "d.deck_id", commander_names)
    key = "COALESCE(k.oracle_id, k.card_name)"
    base = (
        "FROM corpus_deck_card k JOIN corpus_deck d USING (deck_id) "
        f"WHERE d.duplicate_of IS NULL AND k.section != 'sideboard'{bound}"
    )
    for row in db.execute(
        f"SELECT {key} AS card, d.play_group AS cohort, COUNT(DISTINCT k.deck_id) AS n {base} "
        "GROUP BY 1, 2",
        bound_args,
    ):
        entry = hits.setdefault(str(row["card"]), {})
        entry[str(row["cohort"])] = int(row["n"])
        entry[ALL_DECKS] = entry.get(ALL_DECKS, 0) + int(row["n"])
    for row in db.execute(
        f"SELECT {key} AS card, c.cohort AS cohort, COUNT(DISTINCT k.deck_id) AS n "
        "FROM corpus_deck_card k JOIN corpus_deck d USING (deck_id) "
        "JOIN corpus_cohort c USING (deck_id) "
        f"WHERE d.duplicate_of IS NULL AND k.section != 'sideboard'{bound} GROUP BY 1, 2",
        bound_args,
    ):
        hits.setdefault(str(row["card"]), {})[str(row["cohort"])] = int(row["n"])
    return hits


def _edhrec_entry(widest: sqlite3.Row | None, signal: object) -> dict[str, object] | None:
    """The EDHREC figure of a card: the older table row when it has a value, else the
    commander's stored inclusion signal (a share, shown as percent), else None (unknown)."""
    if widest is not None and widest["value"] is not None:
        return {
            "page": str(widest["cohort"]).removeprefix("edhrec:"),
            "pct": widest["value"],
            "numerator": widest["numerator"],
            "denominator": widest["denominator"],
            "origin": "table",
        }
    if isinstance(signal, dict) and signal.get("value") is not None:
        return {
            "page": "Signal-Import (EDHREC)",
            "pct": 100 * float(signal["value"]),
            "numerator": signal.get("numerator"),
            "denominator": signal.get("denominator"),
            "origin": "signal",
        }
    if widest is not None:
        return {
            "page": str(widest["cohort"]).removeprefix("edhrec:"),
            "pct": None,
            "numerator": widest["numerator"],
            "denominator": widest["denominator"],
            "origin": "table",
        }
    return None


def pool_cards(
    store: StudioStore,
    commander_names: Sequence[str],
    *,
    profile: str | None = None,
    with_signals: bool = True,
) -> dict[str, object]:
    """The collection cards a deck under these commanders may use, with everything the
    builder shows per card. Without any commander the colour filter is off (all legal cards).

    With ``profile`` each card additionally carries its counted spread in that deck
    universe (``universe`` per card, plus one ``universe`` block for the whole pool):
    the same figures the tier list shows for the profile, from the same snapshot, so
    the builder and the tier list never show two denominators for one universe. The
    legacy cohort figures stay untouched either way. Raises KeyError for an unknown
    profile and ValueError when the profile is defined for other commanders.

    Without a ``profile`` and without any local deck list of the commander, a counted
    deck-list universe stored for the commander is used when the automatic choice finds one
    (``universe_choice.choose``, the same as the tier list): each card then carries ``counted``
    (decks, denominator, share; a card without a row is a counted zero) and the pool carries
    one ``counted_universe`` block.

    ``with_signals`` adds the commander's stored usage signals (``card_signal``, one
    commander only) as ``signals`` per card. The older EDHREC value is used first; the
    stored inclusion signal fills the card's ``edhrec`` entry only where that has no value."""
    db = store.connection
    identity: frozenset[str] = frozenset() if commander_names else frozenset("WUBRG")
    commander_ids: list[str] = []
    for name in commander_names:
        row = db.execute(
            "SELECT card_id, color_identity FROM card_fact WHERE oracle_name = ?", (name,)
        ).fetchone()
        if row is None:
            raise KeyError(name)
        identity |= color_set(row["color_identity"])
        commander_ids.append(str(row["card_id"]))
    hits = _corpus_hits(store, commander_names)
    edhrec: dict[str, sqlite3.Row] = {}
    cohort_bound, cohort_args = bound_to("observation_cohort", "o.cohort", commander_names)
    for row in db.execute(
        "SELECT o.card_id, o.cohort, o.value, o.numerator, o.denominator FROM observation o "
        f"WHERE o.metric = 'inclusion_pct' AND o.card_id IS NOT NULL{cohort_bound} "
        "ORDER BY o.denominator DESC",
        cohort_args,
    ):
        edhrec.setdefault(str(row["card_id"]), row)
    roles: dict[str, list[str]] = {}
    for row in db.execute("SELECT oracle_id, role FROM card_role ORDER BY role"):
        roles.setdefault(str(row["oracle_id"]), []).append(str(row["role"]))
    playgroup: dict[str, sqlite3.Row] = {}
    for row in db.execute(
        "SELECT oracle_id, card_id, live_inclusion_pct, median_cast_turn, "
        "winrate_when_cast_pct, observed_winrate_gap_pp, ci_95_lower_pp, ci_95_upper_pp, "
        "conservative_ranking_indicator, fetch_status, times_brought, insufficient_sample "
        "FROM playgroup_card_atlas WHERE format_mode = 'multiplayer'"
    ):
        if row["card_id"]:
            playgroup.setdefault(str(row["card_id"]), row)
        if row["oracle_id"]:
            playgroup.setdefault(str(row["oracle_id"]), row)
    signal_values: dict[str, dict[str, object]] = {}
    if with_signals and len(commander_names) == 1:
        # Imported here: strength_view imports this module.
        from . import strength_view

        names = {
            str(r["card_id"]): str(r["oracle_name"])
            for r in db.execute("SELECT card_id, oracle_name FROM card_fact")
        }
        signal_values = {
            card_id: dict(found)
            for card_id, found in strength_view.card_signal_values(
                store, commander_names[0], list(names), names
            ).items()
        }
    cards: list[dict[str, object]] = []
    for row in db.execute(
        "SELECT c.*, i.owned_lower_bound, i.available_lower_bound, i.reserved, "
        "m.favorite, m.excluded, m.note "
        "FROM card_fact c JOIN inventory i USING (card_id) LEFT JOIN card_mark m USING (card_id) "
        "WHERE c.commander_legal = 1 ORDER BY c.oracle_name"
    ):
        if not color_set(row["color_identity"]) <= identity:
            continue
        card_id = str(row["card_id"])
        widest = edhrec.get(card_id)
        pg = playgroup.get(card_id) or (
            playgroup.get(str(row["oracle_id"])) if row["oracle_id"] else None
        )
        cards.append(
            {
                "card_id": card_id,
                "oracle_id": row["oracle_id"],
                "name": row["oracle_name"],
                "mana_cost": row["mana_cost"] or "",
                "mana_value": row["mana_value"],
                "type_line": row["type_line"] or "",
                "group": main_type(row["type_line"]),
                "text": row["oracle_text"] or "",
                "colors": row["color_identity"],
                "power": row["power"],
                "toughness": row["toughness"],
                "basic": bool(row["is_basic_land"]),
                "produced_mana": row["produced_mana"] or "",
                "edhrec_rank": row["edhrec_rank"],
                "game_changer": bool(row["game_changer"]),
                "has_back": row["image_back"] is not None,
                "has_image": row["image_front"] is not None,
                "fact_source": row["fact_source"],
                "sim_status": sim_readiness_status(str(row["oracle_name"])),
                "owned": row["owned_lower_bound"],
                "available": row["available_lower_bound"],
                "reserved": row["reserved"],
                "favorite": bool(row["favorite"]),
                "excluded": bool(row["excluded"]),
                "note": row["note"] or "",
                "roles": roles.get(str(row["oracle_id"]), []),
                "decks": hits.get(str(row["oracle_id"]), hits.get(str(row["oracle_name"]), {})),
                "edhrec": _edhrec_entry(widest, signal_values.get(card_id, {}).get("inclusion")),
                "signals": signal_values.get(card_id, {}),
                "playgroup": None
                if pg is None
                else {
                    "live_inclusion_pct": pg["live_inclusion_pct"],
                    "median_cast_turn": pg["median_cast_turn"],
                    "winrate_when_cast_pct": pg["winrate_when_cast_pct"],
                    "observed_winrate_gap_pp": pg["observed_winrate_gap_pp"],
                    "ci_95_lower_pp": pg["ci_95_lower_pp"],
                    "ci_95_upper_pp": pg["ci_95_upper_pp"],
                    "conservative_ranking_indicator": pg["conservative_ranking_indicator"],
                    "status": pg["fetch_status"],
                    "times_brought": pg["times_brought"],
                    "insufficient_sample": bool(pg["insufficient_sample"]),
                },
            }
        )
    result: dict[str, object] = {
        "commander_ids": commander_ids,
        "identity": "".join(sorted(identity, key="WUBRG".index)),
        "cohorts": cohort_sizes(store, commander_names),
        "corpus_binding": corpus_binding(store, commander_names),
        "small_denominator": SMALL_DENOMINATOR,
        "roles": [str(r[0]) for r in db.execute("SELECT DISTINCT role FROM card_role ORDER BY 1")],
        "sim_readiness": _sim_readiness_summary(cards),
        "cards": cards,
    }
    if (
        profile is None
        and len(commander_names) == 1
        and not cohort_sizes(store, commander_names).get(ALL_DECKS)
    ):
        # No local deck lists of this commander: the counted deck-list universe the tier list
        # chooses automatically (the same server function, ``strength_view``), if one is stored.
        from . import strength_view

        found = strength_view.builder_counted_universe(
            store,
            commander_names[0],
            [str(card["card_id"]) for card in cards],
            {str(card["card_id"]): str(card["name"]) for card in cards},
        )
        if found is not None:
            choice, observed = found
            for card in cards:
                count = observed.get(str(card["card_id"]))
                if count is not None and count.numerator is not None and count.denominator:
                    card["counted"] = {
                        "hits": count.numerator,
                        "denominator": count.denominator,
                        "share": count.numerator / count.denominator,
                    }
            result["counted_universe"] = dict(choice)
    if profile is not None:
        # Imported here, not at module level: sources.py imports this module, and
        # universe_view imports sources — a top-level import would close the circle.
        from . import universe_view

        spread = universe_view.pool_spread(store, profile, commander_names=commander_names)
        by_card = {item["card_id"]: item for item in spread["cards"]}
        for card in cards:
            item = by_card.get(str(card["card_id"]))
            if item is None:
                continue
            card["universe"] = {
                "matched": item["matched"],
                "hits": item["hits"],
                "denominator": item["denominator"],
                "share": item["share"],
                "level": item["level"],
                "reason": item["reason"],
                "filter_card": item["filter_card"],
            }
        result["universe"] = {
            **spread["universe"],
            "params": spread["params"],
            "model_version": spread["model_version"],
            "meaning": spread["meaning"],
        }
    return result


def pool_counts(store: StudioStore, commander_names: Sequence[str]) -> dict[str, int]:
    """How many collection cards fall inside the commander's colour identity, and how they
    split by Commander legality: ``legal`` (the pool), ``legality_unknown`` (legality is
    NULL, empty or ``unknown``: excluded from the pool, but listed as unknown and never as illegal) and
    ``not_legal`` (banned or not legal). Raises KeyError for a commander not in the
    collection. Counts only; the pool itself is ``pool_cards``."""
    db = store.connection
    identity: frozenset[str] = frozenset()
    for name in commander_names:
        row = db.execute(
            "SELECT color_identity FROM card_fact WHERE oracle_name = ?", (name,)
        ).fetchone()
        if row is None:
            raise KeyError(name)
        identity |= color_set(row["color_identity"])
    counts = {"in_identity": 0, "legal": 0, "legality_unknown": 0, "not_legal": 0}
    for row in db.execute(
        "SELECT f.color_identity, f.commander_legal, f.fact_source, s.commander_legality "
        "FROM card_fact f JOIN inventory i USING (card_id) "
        "LEFT JOIN scryfall_card s ON s.oracle_id = f.oracle_id"
    ):
        if not color_set(row["color_identity"]) <= identity:
            continue
        counts["in_identity"] += 1
        if row["commander_legal"] == 1:
            counts["legal"] += 1
        elif (
            row["fact_source"] == "scryfall" and row["commander_legality"] in (None, "", "unknown")
        ) or (row["fact_source"] != "scryfall" and row["commander_legal"] is None):
            counts["legality_unknown"] += 1
        else:
            counts["not_legal"] += 1
    return counts


def legality_unknown_in_collection(store: StudioStore) -> int:
    """Collection cards whose Commander legality is unknown (NULL, empty or ``unknown``), any colour."""
    row = store.connection.execute(
        "SELECT COUNT(*) FROM card_fact f JOIN inventory i USING (card_id) "
        "LEFT JOIN scryfall_card s ON s.oracle_id = f.oracle_id "
        "WHERE (f.fact_source = 'scryfall' AND (s.commander_legality IS NULL "
        "OR s.commander_legality IN ('', 'unknown'))) "
        "OR (f.fact_source != 'scryfall' AND f.commander_legal IS NULL)"
    ).fetchone()
    return int(row[0])


def card_cooccurrence(
    store: StudioStore,
    card_id: str,
    commander_names: Sequence[str],
    *,
    cohort: str = ALL_DECKS,
    limit: int = 25,
) -> dict[str, object]:
    """Other collection cards that appear in the same non-duplicate source decks as ``card_id``.

    Pure count (``DERIVED_DESCRIPTIVE``): ``both_hits`` is the numerator and ``card_decks`` (the
    number of distinct non-duplicate source decks of the commander in ``cohort`` that contain
    ``card_id``) is the denominator.
    """
    db = store.connection
    target = db.execute(
        "SELECT oracle_id, oracle_name FROM card_fact WHERE card_id = ?", (card_id,)
    ).fetchone()
    if target is None:
        raise KeyError(card_id)
    oracle_id = target["oracle_id"]
    oracle_name = str(target["oracle_name"])
    cohort_join, bound_args = bound_to("corpus_deck", "d.deck_id", commander_names)
    params: list[object] = [*bound_args]
    if cohort != ALL_DECKS:
        play_groups = {str(r[0]) for r in db.execute("SELECT DISTINCT play_group FROM corpus_deck")}
        if cohort in play_groups:
            cohort_join += " AND d.play_group = ?"
            params.append(cohort)
        else:
            cohort_join += (
                " AND EXISTS (SELECT 1 FROM corpus_cohort cc "
                "WHERE cc.deck_id = d.deck_id AND cc.cohort = ?)"
            )
            params.append(cohort)
    match_clause = "(k.oracle_id = ? OR k.card_name = ?)" if oracle_id else "k.card_name = ?"
    match_params: list[object] = [oracle_id, oracle_name] if oracle_id else [oracle_name]
    deck_ids = [
        str(r[0])
        for r in db.execute(
            "SELECT DISTINCT k.deck_id FROM corpus_deck_card k JOIN corpus_deck d USING (deck_id) "
            f"WHERE d.duplicate_of IS NULL AND k.section != 'sideboard' AND {match_clause}"
            f"{cohort_join}",
            [*match_params, *params],
        )
    ]
    card_decks = len(deck_ids)
    if card_decks == 0:
        return {
            "cohort": cohort,
            "card_decks": 0,
            "data_class": "DERIVED_DESCRIPTIVE",
            "cards": [],
        }
    placeholders = ",".join("?" for _ in deck_ids)
    rows = db.execute(
        "SELECT c.card_id, c.oracle_name AS name, COUNT(DISTINCT k.deck_id) AS both_hits "
        "FROM corpus_deck_card k JOIN card_fact c "
        "ON (k.oracle_id IS NOT NULL AND k.oracle_id = c.oracle_id) "
        "OR (k.oracle_id IS NULL AND k.card_name = c.oracle_name) "
        f"WHERE k.deck_id IN ({placeholders}) AND k.section != 'sideboard' "
        "AND c.card_id != ? AND c.commander_legal = 1 "
        "GROUP BY c.card_id, c.oracle_name ORDER BY both_hits DESC, c.oracle_name ASC LIMIT ?",
        [*deck_ids, card_id, limit],
    ).fetchall()
    return {
        "cohort": cohort,
        "card_decks": card_decks,
        "data_class": "DERIVED_DESCRIPTIVE",
        "cards": [
            {
                "card_id": str(r["card_id"]),
                "name": str(r["name"]),
                "both_hits": int(r["both_hits"]),
                "card_decks": card_decks,
                "share": round(int(r["both_hits"]) / card_decks, 4),
            }
            for r in rows
        ],
    }


def card_neutral_boards(
    store: StudioStore, card_id: str, commander_names: Sequence[str]
) -> dict[str, object]:
    """Counts of ``card_id`` in neutral non-mainboard source sections (MAYBEBOARD, CUTS, SIDEBOARD).

    Stored in ``neutral_board_row`` and never mixed into mainboard frequencies.
    """
    db = store.connection
    target = db.execute(
        "SELECT oracle_id, oracle_name FROM card_fact WHERE card_id = ?", (card_id,)
    ).fetchone()
    if target is None:
        raise KeyError(card_id)
    bound, bound_args = bound_to("neutral_source", "n.source_key", commander_names)
    batch_sources = int(
        db.execute(
            f"SELECT COUNT(DISTINCT n.source_key) FROM neutral_board_row n WHERE 1{bound}",
            bound_args,
        ).fetchone()[0]
    )
    if batch_sources == 0:
        return {"batch_sources": 0, "data_class": "DERIVED_DESCRIPTIVE", "sections": []}
    oracle_id = target["oracle_id"]
    oracle_name = str(target["oracle_name"])
    section_totals = {
        str(r["section"]): int(r["n"])
        for r in db.execute(
            "SELECT n.section, COUNT(DISTINCT n.source_key) AS n FROM neutral_board_row n "
            f"WHERE 1{bound} GROUP BY n.section",
            bound_args,
        )
    }
    match_clause = "(n.oracle_id = ? OR n.card_name = ?)" if oracle_id else "n.card_name = ?"
    match_params: list[object] = [oracle_id, oracle_name] if oracle_id else [oracle_name]
    hits_by_section = {
        str(r["section"]): int(r["hits"])
        for r in db.execute(
            "SELECT n.section, COUNT(DISTINCT n.source_key) AS hits FROM neutral_board_row n "
            f"WHERE {match_clause}{bound} GROUP BY n.section",
            [*match_params, *bound_args],
        )
    }
    sections: list[dict[str, object]] = []
    for sec in ("MAYBEBOARD", "CUTS", "SIDEBOARD"):
        sec_den = section_totals.get(sec, 0)
        if sec_den == 0:
            continue
        hits = hits_by_section.get(sec, 0)
        sections.append(
            {
                "section": sec,
                "hits": hits,
                "section_sources": sec_den,
                "batch_sources": batch_sources,
                "share_of_section": round(hits / sec_den, 4),
            }
        )
    return {
        "batch_sources": batch_sources,
        "data_class": "DERIVED_DESCRIPTIVE",
        "sections": sections,
    }


def card_simulations(
    store: StudioStore, card_id: str, commander_names: Sequence[str]
) -> list[dict[str, object]]:
    """Simulated cast opportunities for one card across the stored ``SIMULATED_RESULT`` runs
    of the commander."""
    db = store.connection
    target = db.execute(
        "SELECT oracle_name, engine_name FROM card_fact WHERE card_id = ?", (card_id,)
    ).fetchone()
    if target is None:
        raise KeyError(card_id)
    bound, bound_args = bound_to("simulation_run", "r.run_id", commander_names)
    rows = db.execute(
        "SELECT r.run_id, r.pod, r.engine_pin, r.pilot_policy, r.hand_dwell_status, "
        "sc.games_completed, sc.games_offered, sc.games_cast_after_offer, sc.games_rotted, "
        "sc.offered_castable, sc.cast_count, sc.mean_first_cast_round "
        "FROM simulation_card sc JOIN simulation_run r USING (run_id) "
        f"WHERE (sc.card_id = ? OR sc.card_name IN (?, ?)){bound} ORDER BY r.pod",
        (card_id, target["oracle_name"], target["engine_name"], *bound_args),
    ).fetchall()
    return [
        {
            **dict(item),
            "data_class": "SIMULATED_RESULT",
        }
        for item in rows
    ]


def list_simulations(store: StudioStore, commander_names: Sequence[str]) -> list[dict[str, object]]:
    """The stored ``SIMULATED_RESULT`` runs of the commander with their summary metrics and
    per-card cast counts."""
    db = store.connection
    runs: list[dict[str, object]] = []
    bound, bound_args = bound_to("simulation_run", "r.run_id", commander_names)
    for run in db.execute(
        "SELECT r.run_id, r.deck_id, r.pod, r.engine_pin, r.pilot_policy, r.seeds, "
        "r.games_planned, r.games_completed, r.games_failed, r.wins_fractional, r.win_rate, "
        f"r.mean_rounds, r.hand_dwell_status FROM simulation_run r WHERE 1{bound} "
        "ORDER BY r.pod, r.run_id",
        bound_args,
    ):
        cards = [
            dict(row)
            for row in db.execute(
                "SELECT card_id, card_name, games_completed, games_offered, "
                "games_cast_after_offer, games_rotted, offered_castable, cast_count, "
                "mean_first_cast_round FROM simulation_card WHERE run_id = ? "
                "ORDER BY games_offered DESC, card_name ASC",
                (run["run_id"],),
            )
        ]
        runs.append(
            {
                **dict(run),
                "seeds": json.loads(str(run["seeds"])),
                "data_class": "SIMULATED_RESULT",
                "cards": cards,
            }
        )
    return runs


def card_detail(
    store: StudioStore,
    card_id: str,
    commander_names: Sequence[str],
    *,
    cohort: str = ALL_DECKS,
) -> dict[str, object]:
    """Everything stored about one card under the commander: observations with numerator,
    denominator, address and data class, plus co-occurring cards, neutral boards and
    simulation runs. Source rows bound to another commander are never shown."""
    db = store.connection
    row = db.execute("SELECT * FROM card_fact WHERE card_id = ?", (card_id,)).fetchone()
    if row is None:
        raise KeyError(card_id)
    cohort_bound, cohort_args = bound_to("observation_cohort", "o.cohort", commander_names)
    observations = [
        dict(item)
        for item in db.execute(
            "SELECT o.cohort, o.metric, o.value, o.numerator, o.denominator, o.data_class, "
            "o.url, o.snapshot FROM observation o "
            f"WHERE (o.card_id = ? OR o.card_name = ?){cohort_bound} "
            "ORDER BY o.metric, o.denominator DESC",
            (card_id, row["oracle_name"], *cohort_args),
        )
    ]
    used_in = [
        dict(item)
        for item in db.execute(
            "SELECT b.deck_id, b.branch, d.name FROM deck_branch b JOIN deck d USING (deck_id) "
            "JOIN deck_revision_card rc ON rc.revision_id = b.revision_id WHERE rc.card_id = ?",
            (card_id,),
        )
    ]
    pg_row = db.execute(
        "SELECT * FROM playgroup_card_atlas "
        "WHERE (card_id = ? OR (oracle_id IS NOT NULL AND oracle_id = ?)) "
        "AND format_mode = 'multiplayer'",
        (card_id, row["oracle_id"]),
    ).fetchone()
    playgroup_detail: dict[str, object] | None = None
    if pg_row is not None:
        oracle_id = str(pg_row["oracle_id"])
        top_commanders = [
            dict(tc)
            for tc in db.execute(
                "SELECT rank, commander_name, commander_slug, color_identity, decks_count "
                "FROM playgroup_top_commander WHERE oracle_id = ? AND format_mode = 'multiplayer' ORDER BY rank",
                (oracle_id,),
            )
        ]
        final_zones = [
            dict(fz)
            for fz in db.execute(
                "SELECT zone_name, pct, instances_n "
                "FROM playgroup_final_zone WHERE oracle_id = ? AND format_mode = 'multiplayer' ORDER BY zone_name",
                (oracle_id,),
            )
        ]
        warnings: list[object] = []
        if pg_row["quality_warnings_json"]:
            try:
                warnings = json.loads(pg_row["quality_warnings_json"])
            except Exception:
                warnings = []
        playgroup_detail = dict(pg_row)
        playgroup_detail["top_commanders"] = top_commanders
        playgroup_detail["final_zones"] = final_zones
        playgroup_detail["quality_warnings"] = warnings
        playgroup_detail["insufficient_sample"] = bool(pg_row["insufficient_sample"])
        playgroup_detail["attribution"] = "Playgroup.gg (CC BY 4.0)"
        playgroup_detail["disclosure"] = (
            "Live-Korrelation (Playgroup.gg), keine kausale Kartenstärke."
        )

    return {
        "card_id": card_id,
        "sim_status": sim_readiness_status(str(row["oracle_name"])),
        "observations": observations,
        "used_in": used_in,
        "commander": list(commander_names),
        "cooccurrence": card_cooccurrence(store, card_id, commander_names, cohort=cohort),
        "neutral_boards": card_neutral_boards(store, card_id, commander_names),
        "simulations": card_simulations(store, card_id, commander_names),
        "playgroup": playgroup_detail,
    }


def _percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    position = share * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def cohort_shapes(store: StudioStore, commander_names: Sequence[str]) -> list[dict[str, object]]:
    """How the source decks of the commander are built, per cohort: lands, creatures, average mana value of
    nonland cards (median and middle half). Decks with unresolved cards are left out and
    counted."""
    db = store.connection
    if not commander_names:
        return []
    bound, bound_args = bound_to("corpus_deck", "d.deck_id", commander_names)
    rows = db.execute(
        "SELECT s.*, d.play_group FROM corpus_deck_stat s JOIN corpus_deck d USING (deck_id) "
        f"WHERE d.duplicate_of IS NULL{bound}",
        bound_args,
    ).fetchall()
    members: dict[str, list[sqlite3.Row]] = {ALL_DECKS: list(rows)}
    for row in rows:
        members.setdefault(str(row["play_group"]), []).append(row)
    named = db.execute("SELECT cohort, deck_id FROM corpus_cohort").fetchall()
    by_id = {str(row["deck_id"]): row for row in rows}
    for item in named:
        found = by_id.get(str(item["deck_id"]))
        if found is not None:
            members.setdefault(str(item["cohort"]), []).append(found)
    role_names = [str(r[0]) for r in db.execute("SELECT DISTINCT role FROM card_role ORDER BY 1")]
    role_cards: dict[tuple[str, str], int] = {
        (str(r["deck_id"]), str(r["role"])): int(r["cards"])
        for r in db.execute("SELECT deck_id, role, cards FROM corpus_deck_role")
    }
    shapes: list[dict[str, object]] = []
    for cohort, group in members.items():
        complete = [row for row in group if row["resolved"] == row["cards"]]
        shape: dict[str, object] = {
            "cohort": cohort,
            "decks": len(group),
            "decks_counted": len(complete),
        }
        if complete:
            for field, values in (
                ("lands", [float(row["lands"]) for row in complete]),
                ("creatures", [float(row["creatures"]) for row in complete]),
                (
                    "mana_value",
                    [
                        row["nonland_mana_value"] / row["nonland_cards"]
                        for row in complete
                        if row["nonland_cards"]
                    ],
                ),
            ):
                if values:
                    shape[field] = {
                        "median": round(median(values), 2),
                        "p25": round(_percentile(values, 0.25), 2),
                        "p75": round(_percentile(values, 0.75), 2),
                    }
        if complete and role_names:
            spans: dict[str, dict[str, float]] = {}
            for role in role_names:
                counts = [float(role_cards.get((str(row["deck_id"]), role), 0)) for row in complete]
                spans[role] = {
                    "median": round(median(counts), 2),
                    "p25": round(_percentile(counts, 0.25), 2),
                    "p75": round(_percentile(counts, 0.75), 2),
                }
            shape["roles"] = spans
        shapes.append(shape)
    return shapes


def deck_roles(store: StudioStore, cards: Iterable[RevisionCard]) -> dict[str, int]:
    """How many main-deck cards of a list carry each role tag. A card may carry several."""
    counts: Counter[str] = Counter()
    db = store.connection
    for card in cards:
        if card.zone != "main":
            continue
        for row in db.execute(
            "SELECT r.role FROM card c JOIN card_role r USING (oracle_id) WHERE c.card_id = ?",
            (card.card_id,),
        ):
            counts[str(row["role"])] += card.quantity
    return dict(counts)


def _hypergeom_at_least(total_n: int, success_k: int, draws: int, min_hits: int) -> float | None:
    if total_n < draws or draws <= 0 or success_k < 0 or success_k > total_n:
        return None
    denom = math.comb(total_n, draws)
    if denom == 0:
        return None
    hits = sum(
        math.comb(success_k, i) * math.comb(total_n - success_k, draws - i)
        for i in range(max(min_hits, 0), min(success_k, draws) + 1)
        if 0 <= draws - i <= total_n - success_k
    )
    return round(hits / denom, 4)


def _hypergeom_range(
    total_n: int, success_k: int, draws: int, low_hits: int, high_hits: int
) -> float | None:
    if total_n < draws or draws <= 0 or success_k < 0 or success_k > total_n:
        return None
    denom = math.comb(total_n, draws)
    if denom == 0:
        return None
    hits = sum(
        math.comb(success_k, i) * math.comb(total_n - success_k, draws - i)
        for i in range(max(low_hits, 0), min(high_hits, success_k, draws) + 1)
        if 0 <= draws - i <= total_n - success_k
    )
    return round(hits / denom, 4)


def draw_probabilities(main_cards: int, lands: int) -> dict[str, object] | None:
    """Exact hypergeometric land-draw probabilities on the main deck (``DERIVED_DESCRIPTIVE``)."""
    if main_cards < 10:
        return None
    return {
        "data_class": "DERIVED_DESCRIPTIVE",
        "main_cards": main_cards,
        "lands": lands,
        "opening_7": {
            "draws": 7,
            "at_least_2_lands": _hypergeom_at_least(main_cards, lands, 7, 2),
            "at_least_3_lands": _hypergeom_at_least(main_cards, lands, 7, 3),
            "between_3_and_4_lands": _hypergeom_range(main_cards, lands, 7, 3, 4),
            "at_least_4_lands": _hypergeom_at_least(main_cards, lands, 7, 4),
        },
        "turn_3_draw_9": {
            "draws": 9,
            "at_least_3_lands": _hypergeom_at_least(main_cards, lands, 9, 3),
            "at_least_4_lands": _hypergeom_at_least(main_cards, lands, 9, 4),
        },
        "turn_4_draw_10": {
            "draws": 10,
            "at_least_3_lands": _hypergeom_at_least(main_cards, lands, 10, 3),
            "at_least_4_lands": _hypergeom_at_least(main_cards, lands, 10, 4),
        },
    }


def deck_shape(rows: Iterable[sqlite3.Row]) -> dict[str, object]:
    """Counts of one deck list: size, types, curve, color symbols, mana sources, and
    exact hypergeometric land-draw probabilities."""
    total = 0
    types: Counter[str] = Counter()
    curve: Counter[int] = Counter()
    pips: Counter[str] = Counter()
    sources: Counter[str] = Counter()
    mana_value_sum = 0.0
    nonland = 0
    for row in rows:
        quantity = int(row["quantity"])
        total += quantity
        if row["zone"] == "commander":
            continue
        group = main_type(row["type_line"])
        types[group] += quantity
        produced = str(row["produced_mana"] or "")
        for letter in produced:
            sources[letter] += quantity
        if group == "Land":
            continue
        nonland += quantity
        value = float(row["mana_value"] or 0)
        mana_value_sum += value * quantity
        curve[min(int(value), 7)] += quantity
        front_cost = str(row["mana_cost"] or "").split(" // ")[0]
        for symbol in _SYMBOL.findall(front_cost):
            for letter in "WUBRG":
                if letter in symbol.split("/"):
                    pips[letter] += quantity
    lands = types.get("Land", 0)
    main_cards = lands + nonland
    return {
        "cards": total,
        "types": dict(types),
        "curve": {str(key): curve.get(key, 0) for key in range(8)},
        "pips": dict(pips),
        "mana_sources": dict(sources),
        "lands": lands,
        "creatures": types.get("Creature", 0),
        "nonland": nonland,
        "mana_value": round(mana_value_sum / nonland, 2) if nonland else None,
        "draw_probabilities": draw_probabilities(main_cards, lands),
    }


def diff_lists(
    store: StudioStore,
    base_cards: Sequence[RevisionCard],
    target_cards: Sequence[RevisionCard],
) -> dict[str, object]:
    """Objective card, shape and role difference between two deck lists (``DERIVED_DESCRIPTIVE``)."""
    base_rows = list_rows(store, base_cards)
    target_rows = list_rows(store, target_cards)
    base_by_id = {
        str(r["card_id"]): (int(r["quantity"]), str(r["oracle_name"]), main_type(r["type_line"]))
        for r in base_rows
        if r["zone"] == "main"
    }
    target_by_id = {
        str(r["card_id"]): (int(r["quantity"]), str(r["oracle_name"]), main_type(r["type_line"]))
        for r in target_rows
        if r["zone"] == "main"
    }
    added: list[dict[str, object]] = []
    removed: list[dict[str, object]] = []
    changed: list[dict[str, object]] = []
    added_slots = 0
    removed_slots = 0
    for card_id in sorted(
        set(base_by_id) | set(target_by_id),
        key=lambda cid: (target_by_id.get(cid) or base_by_id[cid])[1],
    ):
        b_item = base_by_id.get(card_id)
        t_item = target_by_id.get(card_id)
        if b_item is None and t_item is not None:
            added.append(
                {"card_id": card_id, "name": t_item[1], "group": t_item[2], "quantity": t_item[0]}
            )
            added_slots += t_item[0]
        elif t_item is None and b_item is not None:
            removed.append(
                {"card_id": card_id, "name": b_item[1], "group": b_item[2], "quantity": b_item[0]}
            )
            removed_slots += b_item[0]
        elif b_item is not None and t_item is not None and b_item[0] != t_item[0]:
            delta = t_item[0] - b_item[0]
            changed.append(
                {
                    "card_id": card_id,
                    "name": t_item[1],
                    "group": t_item[2],
                    "base_quantity": b_item[0],
                    "target_quantity": t_item[0],
                    "delta": delta,
                }
            )
            if delta > 0:
                added_slots += delta
            else:
                removed_slots += -delta
    base_shape = deck_shape(base_rows)
    target_shape = deck_shape(target_rows)
    base_roles = deck_roles(store, base_cards)
    target_roles = deck_roles(store, target_cards)
    all_roles = sorted(set(base_roles) | set(target_roles))
    role_deltas = {
        role: {
            "base": base_roles.get(role, 0),
            "target": target_roles.get(role, 0),
            "delta": target_roles.get(role, 0) - base_roles.get(role, 0),
        }
        for role in all_roles
        if base_roles.get(role, 0) != target_roles.get(role, 0)
    }
    return {
        "data_class": "DERIVED_DESCRIPTIVE",
        "added": added,
        "removed": removed,
        "changed": changed,
        "added_slots": added_slots,
        "removed_slots": removed_slots,
        "base_shape": base_shape,
        "target_shape": target_shape,
        "role_deltas": role_deltas,
    }


def _to_rules_deck(
    store: StudioStore, cards: Sequence[RevisionCard], deck_id: str
) -> RulesDeckInput | None:
    rows = list_rows(store, cards)
    cmds: list[str] = []
    main: list[str] = []
    for row in rows:
        name = str(row["engine_name"] or row["oracle_name"])
        qty = int(row["quantity"])
        if row["zone"] == "commander":
            cmds.extend([name] * qty)
        else:
            main.extend([name] * qty)
    if not cmds or len(cmds) + len(main) != 100:
        return None
    try:
        return RulesDeckInput(
            deck_id=deck_id,
            name=deck_id,
            commander_names=tuple(cmds),
            mainboard=tuple(main),
        )
    except ValueError:
        return None


def prefilter_lists(
    store: StudioStore,
    base_cards: Sequence[RevisionCard],
    target_cards: Sequence[RevisionCard],
    *,
    trials: int = 2000,
) -> dict[str, object]:
    """Compare ``target_cards`` against ``base_cards`` using the simulator prefilter and
    commander castability model (``HEURISTIC_MODEL``, seed 20261016).

    Requires two valid 100-card Commander lists; returns ``comparable: False`` otherwise.
    """
    base_deck = _to_rules_deck(store, base_cards, "baseline")
    target_deck = _to_rules_deck(store, target_cards, "variant")
    if base_deck is None or target_deck is None:
        return {
            "data_class": "HEURISTIC_MODEL",
            "comparable": False,
            "reason": "Vorfilter benötigt zwei vollständige 100-Karten-Commander-Listen.",
        }
    comp = compare_variant(base_deck, target_deck, trials=trials)
    return {
        "data_class": "HEURISTIC_MODEL",
        "comparable": True,
        **comparison_to_dict(comp),
    }


def read_draft(store: StudioStore, deck_id: str, branch: str) -> dict[str, object] | None:
    row = store.connection.execute(
        "SELECT cards, base_revision_id, updated_at FROM deck_draft WHERE deck_id = ? "
        "AND branch = ?",
        (deck_id, branch),
    ).fetchone()
    if row is None:
        return None
    return {
        "cards": json.loads(row["cards"]),
        "base_revision_id": row["base_revision_id"],
        "updated_at": row["updated_at"],
    }


def write_draft(
    store: StudioStore,
    deck_id: str,
    branch: str,
    cards: Sequence[RevisionCard],
    base_revision_id: str | None,
) -> None:
    """Keep the list being worked on. A draft is not a revision: it is overwritten."""
    payload = json.dumps(
        [{"card_id": c.card_id, "quantity": c.quantity, "zone": c.zone} for c in cards]
    )
    with store.connection as db:
        db.execute(
            "INSERT INTO deck_draft(deck_id, branch, cards, base_revision_id, updated_at) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT(deck_id, branch) DO UPDATE SET "
            "cards = excluded.cards, base_revision_id = excluded.base_revision_id, "
            "updated_at = excluded.updated_at",
            (deck_id, branch, payload, base_revision_id, now_utc()),
        )


def drop_draft(store: StudioStore, deck_id: str, branch: str) -> None:
    with store.connection as db:
        db.execute("DELETE FROM deck_draft WHERE deck_id = ? AND branch = ?", (deck_id, branch))


def set_mark(
    store: StudioStore, card_id: str, *, favorite: bool, excluded: bool, note: str
) -> None:
    """The Owner's own marks on a card: favorite, excluded from suggestions, a note."""
    with store.connection as db:
        if db.execute("SELECT 1 FROM card WHERE card_id = ?", (card_id,)).fetchone() is None:
            raise KeyError(card_id)
        db.execute(
            "INSERT INTO card_mark(card_id, favorite, excluded, note, updated_at) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT(card_id) DO UPDATE SET "
            "favorite = excluded.favorite, excluded = excluded.excluded, note = excluded.note, "
            "updated_at = excluded.updated_at",
            (card_id, int(favorite), int(excluded), note, now_utc()),
        )


def list_decks(store: StudioStore) -> list[dict[str, object]]:
    db = store.connection
    decks: list[dict[str, object]] = []
    for deck in db.execute("SELECT deck_id, name, created_at FROM deck ORDER BY name"):
        branches = [
            dict(row)
            for row in db.execute(
                "SELECT b.branch, b.revision_id, r.created_at, r.note, "
                "(SELECT SUM(quantity) FROM deck_revision_card c "
                " WHERE c.revision_id = b.revision_id) AS cards, "
                "(SELECT 1 FROM deck_draft f WHERE f.deck_id = b.deck_id "
                " AND f.branch = b.branch) AS has_draft "
                "FROM deck_branch b JOIN deck_revision r USING (revision_id) "
                "WHERE b.deck_id = ? ORDER BY b.branch",
                (deck["deck_id"],),
            )
        ]
        commanders = [
            str(row[0])
            for row in db.execute(
                "SELECT DISTINCT f.oracle_name FROM deck_branch b JOIN deck_revision_card rc "
                "ON rc.revision_id = b.revision_id AND rc.zone = 'commander' "
                "JOIN card_fact f ON f.card_id = rc.card_id WHERE b.deck_id = ? ORDER BY 1",
                (deck["deck_id"],),
            )
        ]
        decks.append({**dict(deck), "commanders": commanders, "branches": branches})
    return decks


def history(store: StudioStore, deck_id: str) -> list[dict[str, object]]:
    return [
        dict(row)
        for row in store.connection.execute(
            "SELECT r.revision_id, r.parent_revision_id, r.note, r.created_at, "
            "(SELECT SUM(quantity) FROM deck_revision_card c "
            " WHERE c.revision_id = r.revision_id) AS cards "
            "FROM deck_revision r WHERE r.deck_id = ? ORDER BY r.created_at DESC, r.rowid DESC",
            (deck_id,),
        )
    ]
