"""Deck packages, 6-step guided build plan (#1404 op. 5 & 7), and descriptive upgrade path (B-2).

Everything here is purely descriptive (measured cohort counts, corpus lift, Tagger roles, and
Spellbook shell membership). User marks (favorites, exclusions, notes) never affect sorting,
counts, or suggestions. Unknown corpus counts stay ``None`` (never treated as 0), groups below
``builder.SMALL_DENOMINATOR`` carry ``small_sample=True``, and no claim is made about game
outcomes or card prices.
"""

from __future__ import annotations

import math
import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from . import builder, cache, combos
from .decks import RevisionCard, color_set, list_rows
from .store import StudioStore

PACKAGES_SCHEMA = "studio-deck-packages-1"
BUILD_PLAN_SCHEMA = "studio-build-plan-1"
UPGRADE_PATH_SCHEMA = "studio-upgrade-path-1"

_PLAN_STEPS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    (
        "commander_core",
        "1. Commander & Grundgerüst",
        "Deckgröße (Ziel 100), durchschnittlicher Manawert und Kurven-Kern.",
        (),
    ),
    (
        "mana_base",
        "2. Manabasis & Länder",
        "Länderzahl im Vergleich zur mittleren Hälfte (p25\u2013p75) der Vergleichsgruppe.",
        ("utility_land",),
    ),
    (
        "ramp",
        "3. Ramp & Manabeschleunigung",
        "Mana-Kreaturen, Manasteine, Land-Ramp und Kostenreduktion.",
        ("ramp", "mana_dork", "mana_rock", "land_ramp", "cost_reduction"),
    ),
    (
        "card_advantage",
        "4. Kartenziehen & Kartenvorteil",
        "Kartenziehen, Cantrips, Kartenauswahl und Tutoren.",
        ("card_draw", "card_advantage", "cantrip", "card_selection", "tutor"),
    ),
    (
        "interaction",
        "5. Interaktion & Schutz",
        "Entfernung, Massenentfernung, Konter, Schutz und Friedhofshass.",
        ("removal", "board_wipe", "counterspell", "protection", "graveyard_hate", "bounce", "hate"),
    ),
    (
        "finishers_curve",
        "6. Synergie, Kombos & Abschluss",
        "Blink, Spielsteine, Anthems, Landfall, Evasion, Mana-Senken und Rückholen.",
        ("flicker", "token_production", "anthem", "landfall", "evasion", "mana_sink", "recursion"),
    ),
)


def _is_basic(type_line: str, is_basic_land: object) -> bool:
    if bool(is_basic_land):
        return True
    front = type_line.split(" // ")[0]
    return "Basic" in front and "Land" in front


def _resolve_commanders(
    store: StudioStore,
    commander_names: Sequence[str] | None,
    deck_rows: Sequence[Mapping[str, object]],
) -> list[str]:
    if commander_names:
        cleaned = [str(name).strip() for name in commander_names if str(name).strip()]
        if cleaned:
            return cleaned
    return [str(r["oracle_name"]) for r in deck_rows if str(r["zone"]) == "commander"]


class _PoolCard:
    __slots__ = (
        "available",
        "basic",
        "card_id",
        "in_deck",
        "in_pool",
        "is_commander",
        "is_land",
        "mana_value",
        "name",
        "oracle_id",
        "roles",
        "type_line",
    )

    def __init__(
        self,
        *,
        card_id: str,
        oracle_id: str,
        name: str,
        mana_value: float | None,
        type_line: str,
        is_land: bool,
        basic: bool,
        is_commander: bool,
        in_pool: bool,
        in_deck: bool,
        available: int,
        roles: list[str],
    ) -> None:
        self.card_id = card_id
        self.oracle_id = oracle_id
        self.name = name
        self.mana_value = mana_value
        self.type_line = type_line
        self.is_land = is_land
        self.basic = basic
        self.is_commander = is_commander
        self.in_pool = in_pool
        self.in_deck = in_deck
        self.available = available
        self.roles = roles


def _pool_index(
    store: StudioStore,
    identity: frozenset[str],
    commander_ids: Sequence[str],
    deck_card_ids: set[str],
) -> tuple[dict[str, _PoolCard], dict[str, str], dict[str, list[str]]]:
    """Return ``(by_card_id, card_id_by_name_cf, roles_by_oracle)`` for legal pool cards + deck."""
    db = store.connection
    roles_by_oracle: dict[str, list[str]] = {}
    for row in db.execute("SELECT oracle_id, role FROM card_role ORDER BY role"):
        roles_by_oracle.setdefault(str(row["oracle_id"]), []).append(str(row["role"]))

    cmd_set = set(commander_ids)
    by_id: dict[str, _PoolCard] = {}
    id_by_cf: dict[str, str] = {}
    for row in db.execute(
        "SELECT c.card_id, c.oracle_id, c.oracle_name, c.color_identity, c.mana_value, "
        "c.type_line, c.is_basic_land, c.commander_legal, "
        "i.owned_lower_bound, i.available_lower_bound "
        "FROM card_fact c JOIN inventory i USING (card_id) ORDER BY c.oracle_name"
    ):
        cid = str(row["card_id"])
        owned = int(row["owned_lower_bound"] or 0)
        in_identity = color_set(row["color_identity"]) <= identity if identity else True
        legal = bool(row["commander_legal"])
        in_pool = owned > 0 and legal and in_identity
        in_deck = cid in deck_card_ids
        if not in_pool and not in_deck:
            continue
        type_line = str(row["type_line"] or "")
        basic = _is_basic(type_line, row["is_basic_land"])
        name = str(row["oracle_name"])
        item = _PoolCard(
            card_id=cid,
            oracle_id=str(row["oracle_id"]),
            name=name,
            mana_value=float(row["mana_value"]) if row["mana_value"] is not None else None,
            type_line=type_line,
            is_land="Land" in type_line.split(" // ")[0],
            basic=basic,
            is_commander=cid in cmd_set,
            in_pool=in_pool,
            in_deck=in_deck,
            available=int(row["available_lower_bound"] or 0),
            roles=list(roles_by_oracle.get(str(row["oracle_id"]), ())),
        )
        by_id[cid] = item
        if in_pool:
            id_by_cf[name.casefold()] = cid
            if " // " in name:
                id_by_cf.setdefault(name.split(" // ")[0].casefold(), cid)
    return by_id, id_by_cf, roles_by_oracle


def _cohort_candidates(store: StudioStore, commander_names: Sequence[str], cohort: str) -> set[str]:
    db = store.connection
    cohort_join, bound_args = builder.bound_to("corpus_deck", "d.deck_id", commander_names)
    params: list[object] = [*bound_args]
    if cohort == "tuned":
        cohort_join += (
            " AND EXISTS (SELECT 1 FROM corpus_cohort cc "
            "WHERE cc.deck_id = d.deck_id AND cc.cohort IN ('bracket:4', 'bracket:5'))"
        )
    elif cohort != builder.ALL_DECKS:
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
    return {
        str(r[0])
        for r in db.execute(
            f"SELECT d.deck_id FROM corpus_deck d WHERE d.duplicate_of IS NULL{cohort_join}",
            params,
        )
    }


def _cohort_candidates_cached(
    store: StudioStore, commander_names: Sequence[str], cohort: str
) -> frozenset[str]:
    """The non-duplicate source decks of one comparison group, per store state."""
    return cache.cached(
        store,
        ("package_candidates", tuple(commander_names), cohort),
        lambda: frozenset(_cohort_candidates(store, commander_names, cohort)),
    )


def _cohort_deck_sets(
    store: StudioStore, commander_names: Sequence[str], cohort: str
) -> dict[str, set[str]]:
    """The decks listing each card, over the source decks of one comparison group: the
    expensive pass over the corpus of the packages. It does not depend on the deck being
    edited, so it is kept per store state, commander and group (read-only result)."""
    from .universe import deck_sets, spelling_owners

    if cohort == builder.ALL_DECKS:  # the same pass the pool counts use
        return builder.corpus_deck_sets(store, commander_names)
    return cache.cached(
        store,
        ("package_deck_sets", tuple(commander_names), cohort),
        lambda: deck_sets(
            store, _cohort_candidates_cached(store, commander_names, cohort), spelling_owners(store)
        ),
    )


def _rows_from_cards(
    store: StudioStore, cards: Sequence[RevisionCard]
) -> tuple[Sequence[sqlite3.Row], list[dict[str, object]], set[str]]:
    raw_rows = list_rows(store, cards)
    rows = [dict(r) for r in raw_rows]
    deck_ids = {str(r["card_id"]) for r in rows}
    return raw_rows, rows, deck_ids


def deck_packages(
    store: StudioStore,
    commander_names: Sequence[str] | None,
    cards: Sequence[RevisionCard],
    *,
    cohort: str = builder.ALL_DECKS,
    template_snapshot_path: Path | None = None,
) -> dict[str, object]:
    """Identify synergistic card packages & Spellbook shell packages around the current deck."""
    raw_rows, deck_rows, deck_ids = _rows_from_cards(store, cards)
    chosen = _resolve_commanders(store, commander_names, deck_rows)
    if not chosen:
        return {
            "schema": PACKAGES_SCHEMA,
            "cohort": cohort,
            "cohort_decks": 0,
            "small_sample": False,
            "shell_packages": [],
            "synergy_packages": [],
            "meaning": "Kein Commander gewählt: Pakete gehören zu einem Commander.",
        }

    identity, commander_ids = builder.commander_identity(store, chosen)
    by_id, id_by_cf, _ = _pool_index(store, identity, commander_ids, deck_ids)

    # 1. Spellbook shell packages touched by the deck (or with free missing pool pieces)
    combo_data = combos.deck_combos(
        store,
        raw_rows,
        chosen,
        template_snapshot_path=template_snapshot_path,
    )
    shell_packages: list[dict[str, object]] = []
    raw_pool_shells = combo_data.get("pool_shells")
    if isinstance(raw_pool_shells, Sequence):
        for sh in raw_pool_shells:
            if not isinstance(sh, Mapping):
                continue
            raw_in_deck = sh.get("in_deck")
            if not isinstance(raw_in_deck, Sequence) or not raw_in_deck:
                continue
            shell_packages.append(dict(sh))

    # 2. Empirical corpus co-occurrence packages (single batched pass over cohort deck_sets)
    cohort_decks = len(_cohort_candidates_cached(store, chosen, cohort))
    small = 0 < cohort_decks < builder.SMALL_DENOMINATOR
    synergy_keyed: list[tuple[int, int, str, dict[str, object]]] = []
    if cohort_decks > 0:
        sets = _cohort_deck_sets(store, chosen, cohort)
        partner_keys = builder._cached_combo_partners(chosen)

        deck_nonbasic = [
            by_id[cid]
            for cid in deck_ids
            if cid in by_id and not by_id[cid].basic and not by_id[cid].is_commander
        ]
        # Analyze anchors present in at least 3 cohort decks (sorted by decks descending, top 20)
        anchors = sorted(
            [
                (len(sets.get(c.name, set())), c)
                for c in deck_nonbasic
                if len(sets.get(c.name, set())) >= 3
            ],
            key=lambda item: (-item[0], item[1].name),
        )[:20]

        # What a card name stands for in the pool does not depend on the anchor: resolve it
        # once (same order as ``sets``), not once per anchor.
        partners_pool: list[tuple[str, set[str], str, _PoolCard]] = []
        for pname, pset in sets.items():
            p_cid = id_by_cf.get(pname.casefold()) or id_by_cf.get(
                pname.split(" // ")[0].casefold()
            )
            if p_cid is None or p_cid not in by_id:
                continue
            p_info = by_id[p_cid]
            if p_info.basic or p_info.is_commander:
                continue
            partners_pool.append((pname, pset, p_cid, p_info))

        for anchor_decks, anchor in anchors:
            anchor_name = anchor.name
            anchor_cf = anchor_name.casefold()
            anchor_set = sets[anchor_name]
            min_both = max(3, math.ceil(0.05 * anchor_decks))
            missing_keyed: list[tuple[float, int, str, dict[str, object]]] = []
            shared_keyed: list[tuple[float, int, str, dict[str, object]]] = []
            for pname, pset, p_cid, p_info in partners_pool:
                if pname == anchor_name:
                    continue
                # The overlap cannot exceed the smaller set: skip the intersection then.
                if min(len(anchor_set), len(pset)) < min_both:
                    continue
                both = len(anchor_set & pset)
                if both < min_both:
                    continue
                p_decks = len(pset)
                if p_decks == 0:
                    continue
                lift = (both / anchor_decks) / (p_decks / cohort_decks)
                is_partner = f"{anchor_cf}||{pname.casefold()}" in partner_keys
                if lift < 1.5 and not is_partner:
                    continue
                lift_rounded = round(lift, 3)
                entry: dict[str, object] = {
                    "card_id": p_cid,
                    "name": p_info.name,
                    "roles": p_info.roles,
                    "mana_value": p_info.mana_value,
                    "both_hits": both,
                    "anchor_decks": anchor_decks,
                    "partner_decks": p_decks,
                    "cohort_decks": cohort_decks,
                    "share": round(both / anchor_decks, 4),
                    "lift": lift_rounded,
                    "combo_partner": is_partner,
                    "available": p_info.available,
                }
                sort_key = (-lift_rounded, -both, p_info.name)
                if p_info.in_deck:
                    shared_keyed.append((*sort_key, entry))
                elif p_info.available > 0:
                    missing_keyed.append((*sort_key, entry))

            if not missing_keyed and not shared_keyed:
                continue
            missing_keyed.sort(key=lambda item: item[:3])
            shared_keyed.sort(key=lambda item: item[:3])
            missing_partners = [item[3] for item in missing_keyed[:8]]
            shared_in_deck = [item[3] for item in shared_keyed[:8]]
            synergy_keyed.append(
                (
                    -len(missing_partners),
                    -anchor_decks,
                    anchor_name,
                    {
                        "anchor": {
                            "card_id": anchor.card_id,
                            "name": anchor_name,
                            "roles": anchor.roles,
                            "decks": anchor_decks,
                            "of": cohort_decks,
                            "small_sample": anchor_decks < builder.SMALL_DENOMINATOR,
                        },
                        "in_deck_partners": shared_in_deck,
                        "free_pool_partners": missing_partners,
                    },
                )
            )
        synergy_keyed.sort(key=lambda item: item[:3])
    synergy_packages: list[dict[str, object]] = [item[3] for item in synergy_keyed]

    return {
        "schema": PACKAGES_SCHEMA,
        "cohort": cohort,
        "cohort_decks": cohort_decks,
        "small_sample": small,
        "small_denominator": builder.SMALL_DENOMINATOR,
        "shell_packages": shell_packages,
        "synergy_packages": synergy_packages[:15],
        "meaning": (
            "Synergie-Pakete aus gemeinsamen Quelldecks (Lift ≥ 1,5 oder Spellbook-Partner) "
            "und berührte Spellbook-Kombo-Shells. Reine Beobachtung, keine Stärke- oder Siegwertung."
        ),
    }


def _format_span(entry: object) -> dict[str, float] | None:
    if not isinstance(entry, Mapping):
        return None
    return {
        "p25": float(entry.get("p25", 0.0)),
        "median": float(entry.get("median", 0.0)),
        "p75": float(entry.get("p75", 0.0)),
    }


def build_plan(
    store: StudioStore,
    commander_names: Sequence[str] | None,
    cards: Sequence[RevisionCard],
    *,
    cohort: str = builder.ALL_DECKS,
) -> dict[str, object]:
    """Guided 6-step deck-building overview against cohort reference spans + role coverage n/N (#1404 op. 5, #1413)."""
    rows_sql = list_rows(store, cards)
    deck_rows = [dict(r) for r in rows_sql]
    deck_ids = {str(r["card_id"]) for r in deck_rows}
    chosen = _resolve_commanders(store, commander_names, deck_rows)
    if not chosen:
        return {
            "schema": BUILD_PLAN_SCHEMA,
            "cohort": cohort,
            "cohort_decks": 0,
            "small_sample": False,
            "steps": [],
            "role_coverage": [],
            "meaning": "Kein Commander gewählt: der Bauplan gehört zu einem Commander.",
        }

    identity, commander_ids = builder.commander_identity(store, chosen)
    by_id, _id_by_cf, _ = _pool_index(store, identity, commander_ids, deck_ids)
    cohorts = builder.cohort_sizes(store, chosen)
    cohort_decks = int(cohorts.get(cohort, 0))
    small = 0 < cohort_decks < builder.SMALL_DENOMINATOR
    hits = builder._corpus_hits(store, chosen)
    shape = builder.deck_shape(rows_sql)
    deck_roles = builder.deck_roles(store, cards)
    shapes = builder.cohort_shapes(store, chosen)
    ref_shape = next((s for s in shapes if s.get("cohort") == cohort), None)
    ref_roles_raw = ref_shape.get("roles") if isinstance(ref_shape, Mapping) else {}
    ref_roles: Mapping[str, object] = ref_roles_raw if isinstance(ref_roles_raw, Mapping) else {}

    # Pool role coverage n/N (#1413)
    pool_cards = [c for c in by_id.values() if c.in_pool]
    pool_total = len(pool_cards)
    pool_role_counts: dict[str, int] = {}
    pool_tagged = 0
    for card in pool_cards:
        if card.roles:
            pool_tagged += 1
        for role in card.roles:
            pool_role_counts[role] = pool_role_counts.get(role, 0) + 1

    all_roles = sorted(set(pool_role_counts) | set(deck_roles) | set(ref_roles))
    role_coverage = [
        {
            "role": role,
            "deck_count": int(deck_roles.get(role, 0)),
            "pool_tagged": int(pool_role_counts.get(role, 0)),
            "pool_total": pool_total,
            "cohort_span": _format_span(ref_roles.get(role)),
        }
        for role in all_roles
    ]

    free_nonbasic_pool = [
        c
        for c in pool_cards
        if not c.in_deck and not c.basic and not c.is_commander and c.available > 0
    ]

    def _top_pool_for_roles(
        step_roles: Sequence[str], *, lands_only: bool = False
    ) -> list[dict[str, object]]:
        role_set = set(step_roles)
        ranked: list[tuple[int, float, str, dict[str, object]]] = []
        for c in free_nonbasic_pool:
            if lands_only:
                if not c.is_land:
                    continue
            else:
                if c.is_land or not (set(c.roles) & role_set):
                    continue
            name = c.name
            c_hits = (
                int(hits[name][cohort])
                if cohort_decks > 0 and name in hits and cohort in hits[name]
                else None
            )
            share = (
                round(c_hits / cohort_decks, 4)
                if (c_hits is not None and cohort_decks > 0)
                else None
            )
            ranked.append(
                (
                    0 if c_hits is not None else 1,
                    -(c_hits or 0),
                    name,
                    {
                        "card_id": c.card_id,
                        "name": name,
                        "roles": c.roles,
                        "mana_value": c.mana_value,
                        "decks": c_hits,
                        "of": cohort_decks,
                        "share": share,
                        "available": c.available,
                    },
                )
            )
        ranked.sort(key=lambda item: item[:3])
        return [item[3] for item in ranked[:8]]

    deck_total_cards = sum(int(r["quantity"]) for r in deck_rows)
    lands_count = sum(
        int(r["quantity"])
        for r in deck_rows
        if "Land" in str(r["type_line"] or "").split(" // ")[0]
    )

    steps_out: list[dict[str, object]] = []
    for key, title, description, step_roles in _PLAN_STEPS:
        if key == "commander_core":
            cmd_present = [
                str(r["oracle_name"]) for r in deck_rows if str(r["zone"]) == "commander"
            ]
            mv_span = (
                _format_span(ref_shape.get("mana_value"))
                if isinstance(ref_shape, Mapping)
                else None
            )
            metrics = [
                {"label": "Deckgröße", "deck": deck_total_cards, "target": 100, "span": None},
                {
                    "label": "Ø Manawert (Nicht-Länder)",
                    "deck": shape.get("mana_value"),
                    "target": mv_span["median"] if mv_span else None,
                    "span": mv_span,
                },
            ]
            cands: list[dict[str, object]] = []
            status = "COMPLETE" if cmd_present and deck_total_cards == 100 else "OPEN"
        elif key == "mana_base":
            land_span = (
                _format_span(ref_shape.get("lands")) if isinstance(ref_shape, Mapping) else None
            )
            metrics = [
                {
                    "label": "Länder im Deck",
                    "deck": lands_count,
                    "target": land_span["median"] if land_span else None,
                    "span": land_span,
                }
            ]
            cands = _top_pool_for_roles(step_roles, lands_only=True)
            status = (
                "IN_SPAN"
                if land_span and land_span["p25"] <= lands_count <= land_span["p75"]
                else ("OPEN" if lands_count == 0 else "CHECK")
            )
        else:
            metrics = []
            in_span_count = 0
            known_spans = 0
            for role in step_roles:
                d_cnt = int(deck_roles.get(role, 0))
                r_span = _format_span(ref_roles.get(role))
                if r_span is not None:
                    known_spans += 1
                    if r_span["p25"] <= d_cnt <= r_span["p75"]:
                        in_span_count += 1
                metrics.append(
                    {
                        "role": role,
                        "deck": d_cnt,
                        "pool_tagged": int(pool_role_counts.get(role, 0)),
                        "pool_total": pool_total,
                        "span": r_span,
                    }
                )
            cands = _top_pool_for_roles(step_roles, lands_only=False)
            status = (
                "IN_SPAN"
                if known_spans > 0 and in_span_count >= max(1, known_spans // 2)
                else "CHECK"
            )

        steps_out.append(
            {
                "key": key,
                "title": title,
                "description": description,
                "status": status,
                "metrics": metrics,
                "free_pool_candidates": cands,
            }
        )

    return {
        "schema": BUILD_PLAN_SCHEMA,
        "cohort": cohort,
        "cohort_decks": cohort_decks,
        "small_sample": small,
        "small_denominator": builder.SMALL_DENOMINATOR,
        "pool_tagged": pool_tagged,
        "pool_total": pool_total,
        "steps": steps_out,
        "role_coverage": role_coverage,
        "meaning": (
            "6-Schritte-Bauplan entlang der Vergleichsgruppe (Median und mittlere Hälfte p25\u2013p75) "
            "und Tagger-Rollenbelegung im Kartenpool. Reine Orientierung, keine Pflichtgrenze."
        ),
    }


def upgrade_path(
    store: StudioStore,
    commander_names: Sequence[str] | None,
    cards: Sequence[RevisionCard],
    *,
    cohort: str = builder.ALL_DECKS,
) -> dict[str, object]:
    """Descriptive role-matched comparison of current deck cards vs free pool alternatives (B-2).

    Never reads user marks (favorites, exclusions, notes), never ranks unknown corpus cards as
    zero, and never claims a card makes the deck stronger.
    """
    _raw_rows, deck_rows, deck_ids = _rows_from_cards(store, cards)
    chosen = _resolve_commanders(store, commander_names, deck_rows)
    if not chosen:
        return {
            "schema": UPGRADE_PATH_SCHEMA,
            "cohort": cohort,
            "cohort_decks": 0,
            "small_sample": False,
            "swap_suggestions": [],
            "missing_staples": [],
            "unknown_corpus_cards": [],
            "meaning": "Kein Commander gewählt.",
        }

    identity, commander_ids = builder.commander_identity(store, chosen)
    by_id, _id_by_cf, _ = _pool_index(store, identity, commander_ids, deck_ids)
    cohorts = builder.cohort_sizes(store, chosen)
    cohort_decks = int(cohorts.get(cohort, 0))
    small = 0 < cohort_decks < builder.SMALL_DENOMINATOR
    hits = builder._corpus_hits(store, chosen)

    def _freq(name: str) -> tuple[int | None, float | None]:
        if cohort_decks <= 0 or name not in hits or cohort not in hits[name]:
            return (None, None)
        d_hits = int(hits[name][cohort])
        return (d_hits, round(d_hits / cohort_decks, 4))

    free_pool = [
        c
        for c in by_id.values()
        if c.in_pool and not c.in_deck and not c.basic and not c.is_commander and c.available > 0
    ]

    deck_nonbasic = [c for c in by_id.values() if c.in_deck and not c.basic and not c.is_commander]

    suggestions_keyed: list[tuple[float, float, str, dict[str, object]]] = []
    unknown_deck_cards: list[dict[str, object]] = []
    for dcard in deck_nonbasic:
        dname = dcard.name
        d_hits, d_share = _freq(dname)
        d_roles = set(dcard.roles)
        if d_hits is None or d_share is None:
            unknown_deck_cards.append(
                {
                    "card_id": dcard.card_id,
                    "name": dname,
                    "roles": dcard.roles,
                    "mana_value": dcard.mana_value,
                }
            )
            continue
        if not d_roles:
            continue
        d_mv = float(dcard.mana_value or 0.0)
        better_alts: list[tuple[int, int, str, float, dict[str, object]]] = []
        for pcard in free_pool:
            shared = sorted(d_roles & set(pcard.roles))
            if not shared:
                continue
            pname = pcard.name
            p_hits, p_share = _freq(pname)
            if p_hits is None or p_share is None or p_hits <= d_hits:
                continue
            p_mv = float(pcard.mana_value or 0.0)
            better_alts.append(
                (
                    -p_hits,
                    -len(shared),
                    pname,
                    p_share,
                    {
                        "card_id": pcard.card_id,
                        "name": pname,
                        "shared_roles": shared,
                        "mana_value": p_mv,
                        "mv_delta": round(p_mv - d_mv, 4),
                        "decks": p_hits,
                        "of": cohort_decks,
                        "share": p_share,
                        "available": pcard.available,
                    },
                )
            )
        if not better_alts:
            continue
        better_alts.sort(key=lambda item: (item[0], item[1], item[2]))
        share_gap = round(better_alts[0][3] - d_share, 4)
        suggestions_keyed.append(
            (
                d_share,
                -share_gap,
                dname,
                {
                    "cut": {
                        "card_id": dcard.card_id,
                        "name": dname,
                        "roles": dcard.roles,
                        "mana_value": dcard.mana_value,
                        "decks": d_hits,
                        "of": cohort_decks,
                        "share": d_share,
                    },
                    "alternatives": [item[4] for item in better_alts[:3]],
                    "share_gap": share_gap,
                },
            )
        )

    suggestions_keyed.sort(key=lambda item: (item[0], item[1], item[2]))

    # Top free pool cards not yet in the deck by measured cohort share
    staples_keyed: list[tuple[int, str, dict[str, object]]] = []
    for pcard in free_pool:
        pname = pcard.name
        p_hits, p_share = _freq(pname)
        if p_hits is None or p_share is None or p_hits <= 0:
            continue
        staples_keyed.append(
            (
                -p_hits,
                pname,
                {
                    "card_id": pcard.card_id,
                    "name": pname,
                    "roles": pcard.roles,
                    "mana_value": pcard.mana_value,
                    "is_land": pcard.is_land,
                    "decks": p_hits,
                    "of": cohort_decks,
                    "share": p_share,
                    "available": pcard.available,
                },
            )
        )
    staples_keyed.sort(key=lambda item: (item[0], item[1]))

    return {
        "schema": UPGRADE_PATH_SCHEMA,
        "cohort": cohort,
        "cohort_decks": cohort_decks,
        "small_sample": small,
        "small_denominator": builder.SMALL_DENOMINATOR,
        "swap_suggestions": [item[3] for item in suggestions_keyed[:20]],
        "missing_staples": [item[2] for item in staples_keyed[:15]],
        "unknown_corpus_cards": sorted(unknown_deck_cards, key=lambda item: str(item["name"])),
        "meaning": (
            "Beschreibender Vergleich über gemeinsame Tagger-Rollen und die gemessene Häufigkeit "
            "in den Quelldecks (n/N). Persönliche Marken und Notizen werden ignoriert; unbekannte "
            "Korpus-Karten stehen getrennt und nie als 0."
        ),
    }


def _parse_commander_arg(commander: str | Iterable[str] | None) -> list[str] | None:
    if commander is None:
        return None
    if isinstance(commander, str):
        stripped = commander.strip()
        return [stripped] if stripped else None
    cleaned = [str(item).strip() for item in commander if str(item).strip()]
    return cleaned or None


__all__ = [
    "BUILD_PLAN_SCHEMA",
    "PACKAGES_SCHEMA",
    "UPGRADE_PATH_SCHEMA",
    "build_plan",
    "deck_packages",
    "upgrade_path",
]
