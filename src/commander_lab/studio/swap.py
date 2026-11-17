"""Swap helper for the Studio deck builder: role-matched replacements and cut candidates.

Purely descriptive (same Tagger roles and frequency in the chosen comparison group or
universe). Never claims that a swap improves winrate. Unknown frequency is never treated as
zero or "rarely played" and is always placed after cards with known frequency. User marks
never alter sort order or frequency figures (``excluded`` only filters out replacement
candidates).

Figures per candidate are separate groups, never summed: the chosen comparison group (drives
the order) plus, outside a universe, the groups ``all`` and ``tuned`` (brackets 4 and 5)
side by side, each as ``decks`` of ``of`` source decks. A lift is only reported when the card
appears in at least ``SWAP_LIFT_MIN_N`` source decks of the chosen group and the global share
is known; otherwise it is unknown (never 0), and unknown values always sort after known ones.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from . import builder, universe_view
from .decks import color_set
from .store import StudioStore

SWAP_MODES = frozenset({"replace", "cut"})
SWAP_SORT_MODES = frozenset({"hits", "lift"})
# A lift divides a share by a global share; with fewer source decks than this holding the card
# the share is too thin to quote a lift (the figure would be noise, not a measurement).
SWAP_LIFT_MIN_N = 30
# Revisions walked back from the head of the deck variant when looking for earlier cards.
SWAP_HISTORY_LIMIT = 200
_COMPARE_GROUPS = (("all", "all"), ("tuned", "tuned (Bracket 4+5)"))


def _is_basic(type_line: str, flag: object) -> bool:
    if bool(flag):
        return True
    front = type_line.split(" // ")[0]
    return "Basic" in front and "Land" in front


def _global_shares_by_name(store: StudioStore) -> dict[str, float]:
    """Read commander-independent EDHREC global inclusion share per card name (0..1)."""
    shares: dict[str, float] = {}
    for row in store.connection.execute(
        "SELECT card_name, value, numerator, denominator FROM card_signal "
        "WHERE signal = 'edhrec_global_inclusion' AND (commander_name IS NULL OR commander_name = '')"
    ):
        num = row["numerator"]
        den = row["denominator"]
        val = row["value"]
        share: float | None = None
        if num is not None and den:
            share = float(num) / float(den)
        elif val is not None:
            share = float(val)
        if share is not None and share > 0:
            key = str(row["card_name"]).strip().casefold()
            if key:
                shares[key] = share
    return shares


def _removal_history(
    store: StudioStore, deck_id: str, branch: str
) -> tuple[dict[str, object] | None, set[str], dict[str, dict[str, str]]]:
    """Oracle ids of the head revision of ``deck_id``/``branch`` and, per oracle id that an
    earlier revision of its ancestry held but the head does not, the latest such revision.
    ``None`` as first element when the deck or variant is unknown."""
    db = store.connection
    head = db.execute(
        "SELECT revision_id FROM deck_branch WHERE deck_id = ? AND branch = ?",
        (deck_id, branch),
    ).fetchone()
    if head is None:
        return None, set(), {}
    chain: list[sqlite3.Row] = []
    seen: set[str] = set()
    next_id: str | None = str(head["revision_id"])
    while next_id and next_id not in seen and len(chain) < SWAP_HISTORY_LIMIT:
        row = db.execute(
            "SELECT revision_id, parent_revision_id, created_at FROM deck_revision "
            "WHERE revision_id = ? AND deck_id = ?",
            (next_id, deck_id),
        ).fetchone()
        if row is None:
            break
        seen.add(next_id)
        chain.append(row)
        next_id = str(row["parent_revision_id"]) if row["parent_revision_id"] else None
    truncated = bool(next_id) and next_id not in seen

    def oracles_of(revision_id: str) -> set[str]:
        return {
            str(row[0])
            for row in db.execute(
                "SELECT c.oracle_id FROM deck_revision_card rc JOIN card_fact c USING (card_id) "
                "WHERE rc.revision_id = ? AND c.oracle_id IS NOT NULL",
                (revision_id,),
            )
        }

    head_oracles = oracles_of(str(chain[0]["revision_id"])) if chain else set()
    earlier: dict[str, dict[str, str]] = {}
    for row in chain[1:]:  # newest first: the first revision that held a card wins
        for oracle_id in oracles_of(str(row["revision_id"])) - head_oracles:
            earlier.setdefault(
                oracle_id,
                {"revision_id": str(row["revision_id"]), "created_at": str(row["created_at"])},
            )
    meta: dict[str, object] = {
        "deck_id": deck_id,
        "branch": branch,
        "head_revision_id": str(head["revision_id"]),
        "revisions_checked": len(chain) - 1 if chain else 0,
        "truncated": truncated,
    }
    return meta, head_oracles, earlier


def _group_figure(
    hits: dict[str, dict[str, int]], name: str, group: str, size: int | None
) -> dict[str, object]:
    """``decks`` of ``of`` for one group. Unknown (``None``) when the card or the group has no
    data; a missing group size gives ``of`` ``None``, never 0."""
    in_group = hits.get(name, {}).get(group)
    if not size or in_group is None:
        return {"decks": None, "of": size or None, "share": None}
    return {"decks": int(in_group), "of": size, "share": round(int(in_group) / size, 4)}


def _lift_figure(
    decks: int | None, of: int, share: float | None, global_share: float | None
) -> tuple[float | None, str | None]:
    """``(lift, why_unknown)``: a lift only from at least ``SWAP_LIFT_MIN_N`` source decks of the
    group and a known global share; otherwise ``None`` and the reason."""
    if decks is None or share is None:
        return None, "Häufigkeit unbekannt"
    if decks < SWAP_LIFT_MIN_N:
        return None, f"zu dünn: {decks} von {of} Decks (Minimum {SWAP_LIFT_MIN_N})"
    if global_share is None or global_share <= 0:
        return None, "globaler Anteil unbekannt"
    return round(share / global_share, 4), None


def _order_rule(sort_by: str, mode: str) -> str:
    by = "Lift" if sort_by == "lift" else "Anzahl Quelldecks"
    direction = "absteigend" if mode == "replace" else "aufsteigend"
    return (
        "Deterministisch, in dieser Reihenfolge: (1) bekannter Wert vor unbekanntem; "
        f"(2) {by} in der gewählten Gruppe, {direction}; (3) mehr gemeinsame Rollen; "
        "(4) kleinerer Mana-Wert-Abstand zur Zielkarte; (5) Name; (6) Karten-ID. "
        "Markierungen, die Spalten all/tuned und frühere Revisionen ändern die Reihenfolge nicht."
    )


def swap_candidates(
    store: StudioStore,
    *,
    commander: str | Sequence[str],
    deck_card_ids: Sequence[str],
    card_id: str,
    mode: str,
    cohort: str = "all",
    universe: str | None = None,
    exclude_marked: bool = True,
    sort_by: str = "hits",
    deck_id: str | None = None,
    branch: str = "main",
) -> dict[str, object]:
    """Role-sharing replacement candidates (``mode='replace'``) or cut candidates
    (``mode='cut'``) for ``card_id`` under ``commander``.

    With ``deck_id`` (and ``branch``), a replacement candidate that an earlier revision of that
    saved deck held and its head no longer holds carries ``removed_before`` (the latest such
    revision). It is a fact for display only and never influences figures or order.
    """
    if mode not in SWAP_MODES:
        raise ValueError(f"mode must be one of {sorted(SWAP_MODES)}, got {mode!r}")
    if sort_by not in SWAP_SORT_MODES:
        raise ValueError(f"sort_by must be one of {sorted(SWAP_SORT_MODES)}, got {sort_by!r}")
    commander_names = [commander] if isinstance(commander, str) else [str(c) for c in commander]
    if not commander_names or not all(commander_names):
        raise ValueError("commander is required")
    identity, commander_ids = builder.commander_identity(store, commander_names)

    db = store.connection
    target = db.execute(
        "SELECT card_id, oracle_id, oracle_name, mana_value FROM card_fact WHERE card_id = ?",
        (card_id,),
    ).fetchone()
    if target is None:
        raise KeyError(card_id)

    roles_by_oracle: dict[str, list[str]] = {}
    for row in db.execute("SELECT oracle_id, role FROM card_role ORDER BY role"):
        roles_by_oracle.setdefault(str(row["oracle_id"]), []).append(str(row["role"]))

    roles_of_card = list(roles_by_oracle.get(str(target["oracle_id"]), []))
    target_roles = set(roles_of_card)
    target_mv = float(target["mana_value"] or 0.0)

    universe_name = (universe or "").strip() or None
    universe_by_card: dict[str, dict[str, object]] | None = None
    if universe_name is not None:
        spread = universe_view.pool_spread(store, universe_name, commander_names=commander_names)
        group_name = universe_name
        of = int(spread["universe"]["denominator"])
        universe_by_card = {str(item["card_id"]): dict(item) for item in spread["cards"]}
        hits: dict[str, dict[str, int]] = {}
        cohorts: dict[str, int] = {}
    else:
        cohorts = builder.cohort_sizes(store, commander_names)
        hits = builder._corpus_hits(store, commander_names)
        group_name = cohort
        of = int(cohorts.get(cohort, 0))

    global_shares = _global_shares_by_name(store)
    compare_sizes: dict[str, int | None] = {
        key: (int(cohorts[key]) if cohorts.get(key) else None) for key, _ in _COMPARE_GROUPS
    }
    history: dict[str, object] | None = None
    head_oracles: set[str] = set()
    removed_by_oracle: dict[str, dict[str, str]] = {}
    if deck_id:
        history, head_oracles, removed_by_oracle = _removal_history(store, deck_id, branch)
    deck_set = {str(cid) for cid in deck_card_ids if cid}
    cmd_set = set(commander_ids)

    keyed: list[tuple[int, float, int, float, str, str, dict[str, object]]] = []
    if target_roles:
        for row in db.execute(
            "SELECT c.card_id, c.oracle_id, c.oracle_name, c.color_identity, c.mana_value, "
            "c.type_line, c.is_basic_land, i.available_lower_bound, m.excluded "
            "FROM card_fact c "
            "JOIN inventory i USING (card_id) "
            "LEFT JOIN card_mark m USING (card_id) "
            "WHERE c.commander_legal = 1 "
            "ORDER BY c.oracle_name"
        ):
            if not color_set(row["color_identity"]) <= identity:
                continue
            cid = str(row["card_id"])
            if cid == card_id or cid in cmd_set:
                continue
            type_line = str(row["type_line"] or "")
            if _is_basic(type_line, row["is_basic_land"]):
                continue
            card_roles = roles_by_oracle.get(str(row["oracle_id"]), [])
            shared = sorted(target_roles & set(card_roles))
            if not shared:
                continue

            in_deck = cid in deck_set
            available = int(row["available_lower_bound"] or 0)
            if mode == "replace":
                if in_deck or available < 1:
                    continue
                if exclude_marked and bool(row["excluded"]):
                    continue
            else:
                if not in_deck:
                    continue

            name = str(row["oracle_name"])
            decks_val: int | None = None
            share_val: float | None = None
            if universe_by_card is not None:
                u_item = universe_by_card.get(cid)
                u_hits = u_item.get("hits") if u_item is not None else None
                if (
                    u_item is not None
                    and bool(u_item.get("matched"))
                    and not bool(u_item.get("filter_card"))
                    and isinstance(u_hits, int)
                    and of > 0
                ):
                    decks_val = u_hits
                    share_val = round(u_hits / of, 4)
            elif of > 0 and name in hits and cohort in hits[name]:
                hits_int = int(hits[name][cohort])
                decks_val = hits_int
                share_val = round(hits_int / of, 4)

            g_share = global_shares.get(name.casefold()) or global_shares.get(
                name.split(" // ")[0].casefold()
            )
            lift_val, lift_why = _lift_figure(decks_val, of, share_val, g_share)
            groups_val: dict[str, dict[str, object]] | None = None
            if universe_by_card is None:
                groups_val = {
                    key: _group_figure(hits, name, key, compare_sizes[key])
                    for key, _ in _COMPARE_GROUPS
                }
            removed_before: dict[str, str] | None = None
            if history is not None and not in_deck:
                oracle_id = str(row["oracle_id"])
                if oracle_id not in head_oracles:
                    removed_before = removed_by_oracle.get(oracle_id)

            mv = float(row["mana_value"] or 0.0)
            mv_delta = round(mv - target_mv, 4)
            if sort_by == "lift":
                if lift_val is None:
                    unknown_flag = 1
                    freq_order = 0.0
                else:
                    unknown_flag = 0
                    freq_order = -lift_val if mode == "replace" else lift_val
            elif share_val is None or decks_val is None:
                unknown_flag = 1
                freq_order = 0.0
            else:
                unknown_flag = 0
                freq_order = -float(decks_val) if mode == "replace" else float(decks_val)

            keyed.append(
                (
                    unknown_flag,
                    freq_order,
                    -len(shared),
                    abs(mv_delta),
                    name,
                    cid,
                    {
                        "card_id": cid,
                        "name": name,
                        "shared_roles": shared,
                        "shared_role_count": len(shared),
                        "target_role_count": len(target_roles),
                        "mana_value": mv,
                        "mv_delta": mv_delta,
                        "decks": decks_val,
                        "of": of,
                        "share": share_val,
                        "lift": lift_val,
                        "lift_unknown_reason": lift_why,
                        "groups": groups_val,
                        "removed_before": removed_before,
                        "decks_known": decks_val is not None,
                        "in_deck": in_deck,
                        "available": available,
                    },
                )
            )

    keyed.sort(key=lambda entry: entry[:6])
    items = [entry[6] for entry in keyed]
    unknown_count = sum(
        1
        for item in items
        if (item["lift"] is None if sort_by == "lift" else item["decks"] is None)
    )
    small = of < builder.SMALL_DENOMINATOR
    return {
        "basis": (
            "Gleiche Rolle (Tagger) und Häufigkeit (bzw. Lift gegen globale EDHREC-Verbreitung) "
            "in den Quelldecks der Vergleichsgruppe; keine Aussage über Spielstärke."
        ),
        "mode": mode,
        "sort_by": sort_by,
        "order_rule": _order_rule(sort_by, mode),
        "lift_min_n": SWAP_LIFT_MIN_N,
        "compare_groups": (
            None
            if universe_by_card is not None
            else [
                {"key": key, "label": label, "decks": compare_sizes[key]}
                for key, label in _COMPARE_GROUPS
            ]
        ),
        "history": history,
        "target_role_count": len(target_roles),
        "card_id": card_id,
        "group": {
            "name": group_name,
            "decks": of,
            "small": small,
        },
        "of": of,
        "source_label": group_name,
        "small_sample": small,
        "roles_of_card": roles_of_card,
        "roles": roles_of_card,
        "items": items,
        "candidates": items,
        "unknown_count": unknown_count,
    }
