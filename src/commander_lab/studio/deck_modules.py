"""User-defined deck modules: shared core plus swappable strategy packages (#1448).

Unlike ``packages.py`` (corpus co-occurrence groups), deck modules are explicit building
blocks owned by a deck (`role = 'core'` or `'package'`). Selecting one ``core`` module and
one or more ``package`` modules compiles deterministically into a 100-card list, checks for
cross-module duplicate collisions without silent merging, validates via ``decks.validate_rows``,
exports as text, and optionally persists the compiled result as a normal ``deck_revision`` on a
``module:<slug>`` branch so ``deck_diff.py`` and ``paired_series.py`` work out of the box.

Module membership never enters ``tiers.py``, ``strength.py``, or ``deck_evidence.py``.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import asdict

from .decks import (
    DECK_SIZE,
    DeckIssue,
    RevisionCard,
    _any_number_allowed,
    create_revision,
    export_text,
    list_rows,
    validate_rows,
)
from .store import StudioStore, now_utc

MODULE_ROLES = ("core", "package")
DECK_MODULES_SCHEMA = "studio-deck-modules-1"
MODULE_COMPILE_SCHEMA = "studio-module-compile-1"
_SLUG = re.compile(r"[^a-z0-9]+")


def _slugify(value: str) -> str:
    return _SLUG.sub("-", value.casefold()).strip("-") or "mod"


def _require_deck(store: StudioStore, deck_id: str) -> str:
    row = store.connection.execute(
        "SELECT name FROM deck WHERE deck_id = ?",
        (deck_id,),
    ).fetchone()
    if row is None:
        raise KeyError(f"unknown deck: {deck_id}")
    return str(row["name"])


def _merge_module_cards(cards: Sequence[RevisionCard]) -> list[tuple[str, int, int]]:
    """Return sorted ``(card_id, qty, is_commander)`` for one module, rejecting mixed zones."""
    merged_qty: dict[str, int] = {}
    merged_cmd: dict[str, int] = {}
    for card in cards:
        if card.quantity <= 0:
            raise ValueError(f"quantity must be positive: {card.card_id}")
        if card.zone not in {"main", "commander"}:
            raise ValueError(f"unknown zone: {card.zone}")
        is_cmd = 1 if card.zone == "commander" else 0
        if card.card_id in merged_cmd and merged_cmd[card.card_id] != is_cmd:
            raise ValueError(f"card in multiple zones inside module: {card.card_id}")
        merged_cmd[card.card_id] = is_cmd
        merged_qty[card.card_id] = merged_qty.get(card.card_id, 0) + int(card.quantity)
    return [(card_id, merged_qty[card_id], merged_cmd[card_id]) for card_id in sorted(merged_qty)]


def list_modules(store: StudioStore, deck_id: str) -> list[dict[str, object]]:
    """Return all modules defined for ``deck_id``, ordered by ``(role, sort_order, name)``."""
    _require_deck(store, deck_id)
    db = store.connection
    mod_rows = db.execute(
        "SELECT module_id, deck_id, name, role, sort_order, updated_at "
        "FROM deck_module WHERE deck_id = ? "
        "ORDER BY CASE WHEN role = 'core' THEN 0 ELSE 1 END, sort_order, name, module_id",
        (deck_id,),
    ).fetchall()
    if not mod_rows:
        return []

    card_rows = db.execute(
        "SELECT mc.module_id, mc.card_id, mc.qty, mc.is_commander, "
        "c.oracle_name, c.type_line, c.mana_value, c.color_identity, c.is_basic_land "
        "FROM deck_module_card mc "
        "JOIN deck_module m ON m.module_id = mc.module_id "
        "JOIN card_fact c ON c.card_id = mc.card_id "
        "WHERE m.deck_id = ? "
        "ORDER BY mc.is_commander DESC, c.oracle_name, mc.card_id",
        (deck_id,),
    ).fetchall()

    cards_by_mod: dict[str, list[dict[str, object]]] = {}
    total_by_mod: dict[str, int] = {}
    cmd_by_mod: dict[str, int] = {}
    for row in card_rows:
        mid = str(row["module_id"])
        is_cmd = bool(row["is_commander"])
        row_qty = int(row["qty"])
        total_by_mod[mid] = total_by_mod.get(mid, 0) + row_qty
        if is_cmd:
            cmd_by_mod[mid] = cmd_by_mod.get(mid, 0) + row_qty
        cards_by_mod.setdefault(mid, []).append(
            {
                "card_id": str(row["card_id"]),
                "oracle_name": str(row["oracle_name"]),
                "qty": row_qty,
                "quantity": row_qty,
                "is_commander": is_cmd,
                "zone": "commander" if is_cmd else "main",
                "type_line": str(row["type_line"] or ""),
                "mana_value": float(row["mana_value"]) if row["mana_value"] is not None else None,
                "color_identity": str(row["color_identity"] or ""),
                "is_basic_land": bool(row["is_basic_land"]),
            }
        )

    result: list[dict[str, object]] = []
    for mod in mod_rows:
        mid = str(mod["module_id"])
        mod_cards = cards_by_mod.get(mid, [])
        total_cards = total_by_mod.get(mid, 0)
        commander_cards = cmd_by_mod.get(mid, 0)
        result.append(
            {
                "module_id": mid,
                "deck_id": str(mod["deck_id"]),
                "name": str(mod["name"]),
                "role": str(mod["role"]),
                "sort_order": int(mod["sort_order"]),
                "updated_at": str(mod["updated_at"]),
                "total_cards": total_cards,
                "commander_cards": commander_cards,
                "main_cards": total_cards - commander_cards,
                "cards": mod_cards,
            }
        )
    return result


def get_module(store: StudioStore, deck_id: str, module_id: str) -> dict[str, object]:
    """Return one module of ``deck_id`` or raise ``KeyError``."""
    for mod in list_modules(store, deck_id):
        if mod["module_id"] == module_id:
            return mod
    raise KeyError(f"unknown module: {module_id}")


def save_module(
    store: StudioStore,
    *,
    deck_id: str,
    name: str,
    role: str,
    cards: Sequence[RevisionCard],
    module_id: str | None = None,
    sort_order: int = 0,
) -> dict[str, object]:
    """Create or update a deck module (`role` in `('core', 'package')`)."""
    _require_deck(store, deck_id)
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("module name must not be empty")
    if len(clean_name) > 80:
        raise ValueError("module name must not exceed 80 characters")
    if role not in MODULE_ROLES:
        raise ValueError(f"invalid module role: {role!r} (expected one of {MODULE_ROLES})")

    merged = _merge_module_cards(cards)
    db = store.connection
    if merged:
        known = {str(r[0]) for r in db.execute("SELECT card_id FROM card")}
        missing = sorted({cid for cid, _, _ in merged} - known)
        if missing:
            raise ValueError(f"unknown card ids: {missing[:5]}")

    with db:
        if module_id is not None:
            existing = db.execute(
                "SELECT deck_id FROM deck_module WHERE module_id = ?",
                (module_id,),
            ).fetchone()
            if existing is not None and str(existing["deck_id"]) != deck_id:
                raise ValueError(f"module {module_id} belongs to another deck")
            target_id = module_id
        else:
            base = f"{deck_id}:mod:{_slugify(clean_name)}"
            target_id = base
            seq = 2
            while db.execute(
                "SELECT 1 FROM deck_module WHERE module_id = ?",
                (target_id,),
            ).fetchone():
                target_id = f"{base}-{seq}"
                seq += 1

        ts = now_utc()
        db.execute(
            "INSERT INTO deck_module(module_id, deck_id, name, role, sort_order, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(module_id) DO UPDATE SET "
            "name = excluded.name, role = excluded.role, "
            "sort_order = excluded.sort_order, updated_at = excluded.updated_at",
            (target_id, deck_id, clean_name, role, int(sort_order), ts),
        )
        db.execute("DELETE FROM deck_module_card WHERE module_id = ?", (target_id,))
        if merged:
            db.executemany(
                "INSERT INTO deck_module_card(module_id, card_id, qty, is_commander) "
                "VALUES (?, ?, ?, ?)",
                [(target_id, cid, qty, is_cmd) for cid, qty, is_cmd in merged],
            )
    return get_module(store, deck_id, target_id)


def delete_module(store: StudioStore, deck_id: str, module_id: str) -> bool:
    """Delete ``module_id`` under ``deck_id`` or raise ``KeyError``."""
    _require_deck(store, deck_id)
    with store.connection:
        cur = store.connection.execute(
            "DELETE FROM deck_module WHERE deck_id = ? AND module_id = ?",
            (deck_id, module_id),
        )
    if cur.rowcount == 0:
        raise KeyError(f"unknown module: {module_id}")
    return True


def seed_modules_from_cards(
    store: StudioStore,
    *,
    deck_id: str,
    cards: Sequence[RevisionCard],
    core_card_ids: Iterable[str] | None = None,
    core_name: str = "Kern",
    package_name: str = "Paket A",
) -> list[dict[str, object]]:
    """Split a deck list into a ``core`` module and a ``package`` module.

    When ``core_card_ids`` is given, commanders and cards in ``core_card_ids`` are placed in
    the ``core`` module and all remaining main-deck cards go into ``package_name``.
    When ``core_card_ids`` is ``None``, commanders and lands are placed in ``core`` and
    non-land main-deck cards are placed in ``package_name``.
    """
    _require_deck(store, deck_id)
    explicit_core = set(core_card_ids) if core_card_ids is not None else None
    rows = list_rows(store, cards) if cards else []
    land_ids = {
        str(r["card_id"])
        for r in rows
        if "Land" in str(r["type_line"] or "") or bool(r["is_basic_land"])
    }
    core_cards: list[RevisionCard] = []
    pkg_cards: list[RevisionCard] = []
    for card in cards:
        if card.zone == "commander":
            core_cards.append(card)
        elif explicit_core is not None:
            if card.card_id in explicit_core:
                core_cards.append(card)
            else:
                pkg_cards.append(card)
        else:
            if card.card_id in land_ids:
                core_cards.append(card)
            else:
                pkg_cards.append(card)
    core_mod = save_module(
        store,
        deck_id=deck_id,
        name=core_name,
        role="core",
        cards=core_cards,
        sort_order=0,
    )
    pkg_mod = save_module(
        store,
        deck_id=deck_id,
        name=package_name,
        role="package",
        cards=pkg_cards,
        sort_order=1,
    )
    return [core_mod, pkg_mod]


def compile_modules(
    store: StudioStore,
    deck_id: str,
    module_ids: Sequence[str],
    *,
    owned_only: bool = True,
    save: bool = False,
    branch: str | None = None,
    note: str = "",
) -> dict[str, object]:
    """Compile selected modules (`1 core` + `>=1 package`) into a 100-card deck revision.

    Never silently merges cross-module duplicates of singleton cards: any card that is not
    ``_any_number_allowed`` and appears in more than one selected module produces an explicit
    ``DeckIssue("duplicate_across_modules", "error", ...)``.
    """
    deck_name = _require_deck(store, deck_id)
    if len(set(module_ids)) != len(module_ids):
        raise ValueError("duplicate module_id in compile selection")

    by_id = {str(m["module_id"]): m for m in list_modules(store, deck_id)}
    selected: list[dict[str, object]] = []
    for mid in module_ids:
        if mid not in by_id:
            raise KeyError(f"unknown module for deck {deck_id}: {mid}")
        selected.append(by_id[mid])

    core_mods = [m for m in selected if m["role"] == "core"]
    pkg_mods = [m for m in selected if m["role"] == "package"]

    issues: list[DeckIssue] = []
    if len(core_mods) != 1:
        issues.append(
            DeckIssue(
                "core_module_count",
                "error",
                f"{len(core_mods)} Kern-Module gewählt (genau 1 Kern-Modul ist erforderlich)",
            )
        )
    if len(pkg_mods) < 1:
        issues.append(
            DeckIssue(
                "package_module_count",
                "error",
                "Mindestens 1 Strategie-Paket ist erforderlich",
            )
        )

    # Track card occurrences across modules before merging
    occurrences: dict[str, list[tuple[str, str, int, str]]] = {}
    raw_cards: list[RevisionCard] = []
    for mod in selected:
        mid = str(mod["module_id"])
        mname = str(mod["name"])
        mcards = mod["cards"]
        if isinstance(mcards, list):
            for entry in mcards:
                if not isinstance(entry, dict):
                    continue
                cid = str(entry["card_id"])
                raw_qty = entry["qty"]
                qty = raw_qty if isinstance(raw_qty, int) else int(str(raw_qty))
                zone = str(entry["zone"])
                occurrences.setdefault(cid, []).append((mid, mname, qty, zone))
                raw_cards.append(RevisionCard(card_id=cid, quantity=qty, zone=zone))

    rows = list_rows(store, raw_cards) if raw_cards else []
    row_by_cid = {str(r["card_id"]): r for r in rows}

    # Check cross-module collisions explicitly (do not let _merge silently hide them)
    collision_card_ids: set[str] = set()
    for cid, occs in sorted(occurrences.items()):
        if len(occs) <= 1:
            continue
        row = row_by_cid.get(cid)
        oracle_name = str(row["oracle_name"]) if row is not None else cid
        zones_used = {z for _, _, _, z in occs}
        mod_labels = ", ".join(f"{mname} ({qty}x)" for _, mname, qty, _ in occs)
        if len(zones_used) > 1 or row is None or not _any_number_allowed(row):
            collision_card_ids.add(cid)
            issues.append(
                DeckIssue(
                    "duplicate_across_modules",
                    "error",
                    f"{oracle_name}: mehrfach in Modulen ({mod_labels}) — "
                    "Kollision wird nicht still zusammengeführt",
                    cid,
                )
            )

    # Run standard deck construction checks (100 cards, commander count, color identity, ownership)
    base_issues = validate_rows(rows, owned_only=owned_only)
    for b_issue in base_issues:
        # Avoid redundant singleton error when duplicate_across_modules already reported it
        if b_issue.code == "singleton" and b_issue.card_id in collision_card_ids:
            continue
        if b_issue.card_id and b_issue.card_id in occurrences:
            mod_names = ", ".join(mname for _, mname, _, _ in occurrences[b_issue.card_id])
            issues.append(
                DeckIssue(
                    b_issue.code,
                    b_issue.severity,
                    f"{b_issue.message} [Modul: {mod_names}]",
                    b_issue.card_id,
                )
            )
        else:
            issues.append(b_issue)

    total_cards = sum(c.quantity for c in raw_cards)
    commander_cards = sum(c.quantity for c in raw_cards if c.zone == "commander")
    has_errors = any(i.severity == "error" for i in issues)

    pkg_slug = "-".join(_slugify(str(m["name"])) for m in pkg_mods) or "package"
    target_branch = (branch.strip() if branch and branch.strip() else f"module:{pkg_slug}")[:60]

    revision_id: str | None = None
    saved = False
    if save and not has_errors and total_cards == DECK_SIZE:
        mod_summary = " + ".join(str(m["name"]) for m in selected)
        rev_note = note.strip() if note.strip() else f"Kompiliert aus Modulen: {mod_summary}"
        revision_id = create_revision(
            store,
            deck_id=deck_id,
            name=deck_name,
            cards=raw_cards,
            branch=target_branch,
            note=rev_note,
        )
        saved = True

    plain_text = export_text(rows, "plain") if rows else ""
    moxfield_text = export_text(rows, "moxfield") if rows else ""

    return {
        "schema": MODULE_COMPILE_SCHEMA,
        "deck_id": deck_id,
        "module_ids": list(module_ids),
        "core_modules": [str(m["module_id"]) for m in core_mods],
        "package_modules": [str(m["module_id"]) for m in pkg_mods],
        "branch": target_branch,
        "total_cards": total_cards,
        "target_cards": DECK_SIZE,
        "commander_cards": commander_cards,
        "main_cards": total_cards - commander_cards,
        "valid": not has_errors and total_cards == DECK_SIZE,
        "saved": saved,
        "revision_id": revision_id,
        "issues": [asdict(i) for i in issues],
        "cards": [
            {
                "card_id": str(r["card_id"]),
                "oracle_name": str(r["oracle_name"]),
                "quantity": int(r["quantity"]),
                "zone": str(r["zone"]),
                "type_line": str(r["type_line"] or ""),
                "mana_value": float(r["mana_value"]) if r["mana_value"] is not None else None,
                "color_identity": str(r["color_identity"] or ""),
                "modules": [mname for _, mname, _, _ in occurrences.get(str(r["card_id"]), [])],
            }
            for r in rows
        ],
        "export": {
            "plain": plain_text,
            "moxfield": moxfield_text,
        },
    }
