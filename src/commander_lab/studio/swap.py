"""Swap helper for the Studio deck builder: role-matched replacements and cut candidates.

Purely descriptive (same Tagger roles and frequency in the chosen comparison group or
universe). Never claims that a swap improves winrate. Unknown frequency is never treated as
zero or "rarely played" and is always placed after cards with known frequency. User marks
never alter sort order or frequency figures (``excluded`` only filters out replacement
candidates).
"""

from __future__ import annotations

from collections.abc import Sequence

from . import builder, universe_view
from .store import StudioStore

SWAP_MODES = frozenset({"replace", "cut"})


def _is_basic(type_line: str, flag: object) -> bool:
    if bool(flag):
        return True
    front = type_line.split(" // ")[0]
    return "Basic" in front and "Land" in front


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
) -> dict[str, object]:
    """Role-sharing replacement candidates (``mode='replace'``) or cut candidates
    (``mode='cut'``) for ``card_id`` under ``commander``.
    """
    if mode not in SWAP_MODES:
        raise ValueError(f"mode must be one of {sorted(SWAP_MODES)}, got {mode!r}")
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
    else:
        cohorts = builder.cohort_sizes(store, commander_names)
        hits = builder._corpus_hits(store, commander_names)
        group_name = cohort
        of = int(cohorts.get(cohort, 0))

    deck_set = {str(cid) for cid in deck_card_ids if cid}
    cmd_set = set(commander_ids)

    keyed: list[tuple[int, float, int, float, str, dict[str, object]]] = []
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
            if not builder.color_set(row["color_identity"]) <= identity:
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
            if universe_by_card is not None:
                u_item = universe_by_card.get(cid)
                if (
                    u_item is not None
                    and bool(u_item.get("matched"))
                    and not bool(u_item.get("filter_card"))
                    and u_item.get("hits") is not None
                    and of > 0
                ):
                    decks_val: int | None = int(u_item["hits"])  # type: ignore[arg-type]
                    share_val: float | None = round(decks_val / of, 4)
                else:
                    decks_val = None
                    share_val = None
            elif of > 0 and name in hits and cohort in hits[name]:
                decks_val = int(hits[name][cohort])
                share_val = round(decks_val / of, 4)
            else:
                decks_val = None
                share_val = None

            mv = float(row["mana_value"] or 0.0)
            mv_delta = round(mv - target_mv, 4)
            if share_val is None or decks_val is None:
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
                    {
                        "card_id": cid,
                        "name": name,
                        "shared_roles": shared,
                        "mana_value": mv,
                        "mv_delta": mv_delta,
                        "decks": decks_val,
                        "of": of,
                        "share": share_val,
                        "decks_known": decks_val is not None,
                        "in_deck": in_deck,
                        "available": available,
                    },
                )
            )

    keyed.sort(key=lambda entry: entry[:5])
    items = [entry[5] for entry in keyed]
    unknown_count = sum(1 for item in items if item["decks"] is None)
    small = of < builder.SMALL_DENOMINATOR
    return {
        "basis": (
            "Gleiche Rolle (Tagger) und Häufigkeit in den Quelldecks der Vergleichsgruppe; "
            "keine Aussage über Spielstärke."
        ),
        "mode": mode,
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
