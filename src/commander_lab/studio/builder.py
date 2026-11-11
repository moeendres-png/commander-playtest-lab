"""Read models and working state of the deck builder.

Everything here is counted from stored rows. A figure about source decks always comes with
its denominator; nothing here rates a card.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from collections import Counter
from collections.abc import Iterable, Sequence
from statistics import median

from .decks import RevisionCard, color_set, list_rows
from .store import StudioStore, now_utc

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


def cohort_sizes(store: StudioStore) -> dict[str, int]:
    """Distinct source decks per group: all, each play group, each named cohort."""
    db = store.connection
    sizes = {
        ALL_DECKS: int(
            db.execute("SELECT COUNT(*) FROM corpus_deck WHERE duplicate_of IS NULL").fetchone()[0]
        )
    }
    for row in db.execute(
        "SELECT play_group, COUNT(*) AS n FROM corpus_deck WHERE duplicate_of IS NULL "
        "GROUP BY play_group ORDER BY n DESC"
    ):
        sizes[str(row["play_group"])] = int(row["n"])
    for row in db.execute(
        "SELECT c.cohort, COUNT(*) AS n FROM corpus_cohort c JOIN corpus_deck d USING (deck_id) "
        "WHERE d.duplicate_of IS NULL GROUP BY c.cohort ORDER BY c.cohort"
    ):
        sizes[str(row["cohort"])] = int(row["n"])
    return sizes


def _corpus_hits(store: StudioStore) -> dict[str, dict[str, int]]:
    """``{card key: {cohort: decks}}``; the key is the oracle id, else the card name."""
    db = store.connection
    hits: dict[str, dict[str, int]] = {}
    key = "COALESCE(k.oracle_id, k.card_name)"
    base = (
        "FROM corpus_deck_card k JOIN corpus_deck d USING (deck_id) "
        "WHERE d.duplicate_of IS NULL AND k.section != 'sideboard'"
    )
    for row in db.execute(
        f"SELECT {key} AS card, d.play_group AS cohort, COUNT(DISTINCT k.deck_id) AS n {base} "
        "GROUP BY 1, 2"
    ):
        entry = hits.setdefault(str(row["card"]), {})
        entry[str(row["cohort"])] = int(row["n"])
        entry[ALL_DECKS] = entry.get(ALL_DECKS, 0) + int(row["n"])
    for row in db.execute(
        f"SELECT {key} AS card, c.cohort AS cohort, COUNT(DISTINCT k.deck_id) AS n "
        "FROM corpus_deck_card k JOIN corpus_deck d USING (deck_id) "
        "JOIN corpus_cohort c USING (deck_id) "
        "WHERE d.duplicate_of IS NULL AND k.section != 'sideboard' GROUP BY 1, 2"
    ):
        hits.setdefault(str(row["card"]), {})[str(row["cohort"])] = int(row["n"])
    return hits


def pool_cards(store: StudioStore, commander_names: Sequence[str]) -> dict[str, object]:
    """The collection cards a deck under these commanders may use, with everything the
    builder shows per card."""
    db = store.connection
    identity: frozenset[str] = frozenset()
    commander_ids: list[str] = []
    for name in commander_names:
        row = db.execute(
            "SELECT card_id, color_identity FROM card_fact WHERE oracle_name = ?", (name,)
        ).fetchone()
        if row is None:
            raise KeyError(name)
        identity |= color_set(row["color_identity"])
        commander_ids.append(str(row["card_id"]))
    hits = _corpus_hits(store)
    edhrec: dict[str, sqlite3.Row] = {}
    for row in db.execute(
        "SELECT card_id, cohort, value, numerator, denominator FROM observation "
        "WHERE metric = 'inclusion_pct' AND card_id IS NOT NULL "
        "ORDER BY denominator DESC"
    ):
        edhrec.setdefault(str(row["card_id"]), row)
    roles: dict[str, list[str]] = {}
    for row in db.execute("SELECT oracle_id, role FROM card_role ORDER BY role"):
        roles.setdefault(str(row["oracle_id"]), []).append(str(row["role"]))
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
        cards.append(
            {
                "card_id": card_id,
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
                "owned": row["owned_lower_bound"],
                "available": row["available_lower_bound"],
                "reserved": row["reserved"],
                "favorite": bool(row["favorite"]),
                "excluded": bool(row["excluded"]),
                "note": row["note"] or "",
                "roles": roles.get(str(row["oracle_id"]), []),
                "decks": hits.get(str(row["oracle_id"]), hits.get(str(row["oracle_name"]), {})),
                "edhrec": None
                if widest is None
                else {
                    "page": str(widest["cohort"]).removeprefix("edhrec:"),
                    "pct": widest["value"],
                    "numerator": widest["numerator"],
                    "denominator": widest["denominator"],
                },
            }
        )
    return {
        "commander_ids": commander_ids,
        "identity": "".join(sorted(identity, key="WUBRG".index)),
        "cohorts": cohort_sizes(store),
        "small_denominator": SMALL_DENOMINATOR,
        "roles": [str(r[0]) for r in db.execute("SELECT DISTINCT role FROM card_role ORDER BY 1")],
        "cards": cards,
    }


def card_cooccurrence(
    store: StudioStore, card_id: str, *, cohort: str = ALL_DECKS, limit: int = 15
) -> dict[str, object]:
    """Other collection cards that appear in the same non-duplicate source decks as ``card_id``.

    Pure count (``DERIVED_DESCRIPTIVE``): ``both_hits`` is the numerator and ``card_decks`` (the
    number of distinct non-duplicate source decks in ``cohort`` that contain ``card_id``) is the
    denominator.
    """
    db = store.connection
    target = db.execute(
        "SELECT oracle_id, oracle_name FROM card_fact WHERE card_id = ?", (card_id,)
    ).fetchone()
    if target is None:
        raise KeyError(card_id)
    oracle_id = target["oracle_id"]
    oracle_name = str(target["oracle_name"])
    cohort_join = ""
    params: list[object] = []
    if cohort != ALL_DECKS:
        play_groups = {str(r[0]) for r in db.execute("SELECT DISTINCT play_group FROM corpus_deck")}
        if cohort in play_groups:
            cohort_join = " AND d.play_group = ?"
            params.append(cohort)
        else:
            cohort_join = " AND EXISTS (SELECT 1 FROM corpus_cohort cc WHERE cc.deck_id = d.deck_id AND cc.cohort = ?)"
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


def card_neutral_boards(store: StudioStore, card_id: str) -> dict[str, object]:
    """Counts of ``card_id`` in neutral non-mainboard source sections (MAYBEBOARD, CUTS, SIDEBOARD).

    Stored in ``neutral_board_row`` and never mixed into mainboard frequencies.
    """
    db = store.connection
    target = db.execute(
        "SELECT oracle_id, oracle_name FROM card_fact WHERE card_id = ?", (card_id,)
    ).fetchone()
    if target is None:
        raise KeyError(card_id)
    batch_sources = int(
        db.execute("SELECT COUNT(DISTINCT source_key) FROM neutral_board_row").fetchone()[0]
    )
    if batch_sources == 0:
        return {"batch_sources": 0, "data_class": "DERIVED_DESCRIPTIVE", "sections": []}
    oracle_id = target["oracle_id"]
    oracle_name = str(target["oracle_name"])
    section_totals = {
        str(r["section"]): int(r["n"])
        for r in db.execute(
            "SELECT section, COUNT(DISTINCT source_key) AS n FROM neutral_board_row "
            "GROUP BY section"
        )
    }
    match_clause = "(oracle_id = ? OR card_name = ?)" if oracle_id else "card_name = ?"
    match_params: list[object] = [oracle_id, oracle_name] if oracle_id else [oracle_name]
    hits_by_section = {
        str(r["section"]): int(r["hits"])
        for r in db.execute(
            "SELECT section, COUNT(DISTINCT source_key) AS hits FROM neutral_board_row "
            f"WHERE {match_clause} GROUP BY section",
            match_params,
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


def card_simulations(store: StudioStore, card_id: str) -> list[dict[str, object]]:
    """Simulated cast opportunities for one card across stored ``SIMULATED_RESULT`` runs."""
    db = store.connection
    target = db.execute(
        "SELECT oracle_name, engine_name FROM card_fact WHERE card_id = ?", (card_id,)
    ).fetchone()
    if target is None:
        raise KeyError(card_id)
    rows = db.execute(
        "SELECT r.run_id, r.pod, r.engine_pin, r.pilot_policy, r.hand_dwell_status, "
        "sc.games_completed, sc.games_offered, sc.games_cast_after_offer, sc.games_rotted, "
        "sc.offered_castable, sc.cast_count, sc.mean_first_cast_round "
        "FROM simulation_card sc JOIN simulation_run r USING (run_id) "
        "WHERE sc.card_id = ? OR sc.card_name IN (?, ?) ORDER BY r.pod",
        (card_id, target["oracle_name"], target["engine_name"]),
    ).fetchall()
    return [
        {
            **dict(item),
            "data_class": "SIMULATED_RESULT",
        }
        for item in rows
    ]


def list_simulations(store: StudioStore) -> list[dict[str, object]]:
    """All stored ``SIMULATED_RESULT`` runs with their summary metrics and per-card cast counts."""
    db = store.connection
    runs: list[dict[str, object]] = []
    for run in db.execute(
        "SELECT run_id, deck_id, pod, engine_pin, pilot_policy, seeds, games_planned, "
        "games_completed, games_failed, wins_fractional, win_rate, mean_rounds, hand_dwell_status "
        "FROM simulation_run ORDER BY pod, run_id"
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


def card_detail(store: StudioStore, card_id: str, *, cohort: str = ALL_DECKS) -> dict[str, object]:
    """Everything stored about one card: observations with numerator, denominator, address
    and data class, plus co-occurring cards, neutral boards and simulation runs."""
    db = store.connection
    row = db.execute("SELECT * FROM card_fact WHERE card_id = ?", (card_id,)).fetchone()
    if row is None:
        raise KeyError(card_id)
    observations = [
        dict(item)
        for item in db.execute(
            "SELECT cohort, metric, value, numerator, denominator, data_class, url, snapshot "
            "FROM observation WHERE card_id = ? OR card_name = ? ORDER BY metric, denominator DESC",
            (card_id, row["oracle_name"]),
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
    return {
        "card_id": card_id,
        "observations": observations,
        "used_in": used_in,
        "cooccurrence": card_cooccurrence(store, card_id, cohort=cohort),
        "neutral_boards": card_neutral_boards(store, card_id),
        "simulations": card_simulations(store, card_id),
    }


def _percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    position = share * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def cohort_shapes(store: StudioStore) -> list[dict[str, object]]:
    """How the source decks are built, per cohort: lands, creatures, average mana value of
    nonland cards (median and middle half). Decks with unresolved cards are left out and
    counted."""
    db = store.connection
    rows = db.execute(
        "SELECT s.*, d.play_group FROM corpus_deck_stat s JOIN corpus_deck d USING (deck_id) "
        "WHERE d.duplicate_of IS NULL"
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
        decks.append({**dict(deck), "branches": branches})
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
