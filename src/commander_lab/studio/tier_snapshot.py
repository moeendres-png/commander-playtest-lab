"""Persisted Tier Snapshot (#1420, D2) and lightweight #1369 target summaries.

Stores the complete, pure ``StrengthResult`` payload per ``(commander_name, spec_hash)``
bound to the store's ``data_epoch()``. Owner marks (``favorite``, ``excluded``, ``note``)
never enter ``StrengthResult`` and are never read or stored here.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, cast

from . import strength
from .store import StudioStore, now_utc
from .strength import StrengthSettings

if TYPE_CHECKING:
    from .strength_view import StrengthResult

SNAPSHOT_SCHEMA = "tier-snapshot-1"
SPEC_VERSION = f"{strength.SCHEMA}:{SNAPSHOT_SCHEMA}"
STALE_NOTICE = "Snapshot veraltet, Neuberechnung läuft"

_SELECT_COLUMNS = (
    "commander_name, spec_hash, profile_name, spec_version, data_epoch, created_at, "
    "tier_counts_json, component_denominators_json, payload_json"
)
_SUMMARY_COLUMNS = (
    "commander_name, spec_hash, profile_name, spec_version, data_epoch, created_at, "
    "tier_counts_json, component_denominators_json"
)


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_spec_hash(settings: StrengthSettings, with_layers: bool = True) -> str:
    """Deterministic SHA-256 over the strength schema, snapshot schema, settings, and with_layers."""
    payload = [strength.SCHEMA, SNAPSHOT_SCHEMA, settings.to_dict(), bool(with_layers)]
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def epoch_fingerprint(store: StudioStore) -> str:
    """Deterministic SHA-256 of ``store.data_epoch()``."""
    return hashlib.sha256(_canonical_json(store.data_epoch()).encode("utf-8")).hexdigest()


def _component_denominators(result: Mapping[str, object]) -> dict[str, dict[str, int | None]]:
    """Per-collected-component denominator and covered-card counts for #1369 targets."""
    collected_raw = result.get("collected")
    collected = [str(name) for name in collected_raw] if isinstance(collected_raw, list) else []
    cards_raw = result.get("cards")
    cards = cards_raw if isinstance(cards_raw, list) else []
    pool_size = len(cards)

    agg: dict[str, dict[str, int | None]] = {
        comp: {
            "denominator": None,
            "covered": 0,
            "present": 0,
            "zero_count": 0,
            "pool_size": pool_size,
        }
        for comp in collected
    }
    for card in cards:
        if not isinstance(card, Mapping):
            continue
        rows = card.get("components")
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            comp = str(row.get("component") or "")
            if comp not in agg:
                continue
            entry = agg[comp]
            status = str(row.get("status") or "")
            denom = row.get("denominator")
            if isinstance(denom, int) and not isinstance(denom, bool):
                prev = entry["denominator"]
                if prev is None or denom > prev:
                    entry["denominator"] = denom
            if status == strength.PRESENT:
                entry["present"] = int(entry["present"] or 0) + 1
                entry["covered"] = int(entry["covered"] or 0) + 1
            elif status == strength.ZERO_COUNT:
                entry["zero_count"] = int(entry["zero_count"] or 0) + 1
                entry["covered"] = int(entry["covered"] or 0) + 1
    return agg


def _summary_from_parts(
    *,
    commander_name: str,
    profile_name: str,
    spec_hash: str,
    spec_version: str,
    data_epoch: str,
    current_epoch: str,
    created_at: str,
    tier_counts_obj: Mapping[str, object],
    component_denominators: Mapping[str, object],
) -> dict[str, object]:
    stale = data_epoch != current_epoch or spec_version != SPEC_VERSION
    return {
        "commander_name": commander_name,
        "profile_name": profile_name,
        "spec_hash": spec_hash,
        "spec_version": spec_version,
        "data_epoch": data_epoch,
        "current_epoch": current_epoch,
        "stale": stale,
        "created_at": created_at,
        "tier_counts": tier_counts_obj.get("total", {}),
        "tier_counts_by_kind": tier_counts_obj.get("by_kind", {}),
        "component_denominators": dict(component_denominators),
    }


def write_snapshot(
    store: StudioStore,
    commander: str,
    settings: StrengthSettings,
    *,
    profile_name: str = "Ausgewogen",
    with_layers: bool = True,
    result: StrengthResult | Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Compute (if not provided) and persist a pure tier snapshot for ``(commander, spec_hash)``."""
    from . import strength_view

    computed: dict[str, Any] = (
        dict(result)
        if result is not None
        else dict(strength_view.compute(store, commander, settings))
    )
    computed.pop("snapshot", None)
    canonical_commander = str(computed.get("commander") or commander).strip()
    spec_hash = compute_spec_hash(settings, with_layers)
    data_epoch = epoch_fingerprint(store)
    created_at = now_utc()
    tier_counts_obj = {
        "total": dict(computed.get("tier_counts") or {}),
        "by_kind": dict(computed.get("tier_counts_by_kind") or {}),
    }
    comp_denoms = _component_denominators(computed)

    tier_counts_json = _canonical_json(tier_counts_obj)
    comp_denoms_json = _canonical_json(comp_denoms)
    payload_json = _canonical_json(computed)

    with store.connection as db:
        db.execute(
            "INSERT OR REPLACE INTO tier_snapshot ("
            "commander_name, spec_hash, profile_name, spec_version, data_epoch, "
            "created_at, tier_counts_json, component_denominators_json, payload_json"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                canonical_commander,
                spec_hash,
                profile_name,
                SPEC_VERSION,
                data_epoch,
                created_at,
                tier_counts_json,
                comp_denoms_json,
                payload_json,
            ),
        )

    return _summary_from_parts(
        commander_name=canonical_commander,
        profile_name=profile_name,
        spec_hash=spec_hash,
        spec_version=SPEC_VERSION,
        data_epoch=data_epoch,
        current_epoch=data_epoch,
        created_at=created_at,
        tier_counts_obj=tier_counts_obj,
        component_denominators=comp_denoms,
    )


def _lookup_snapshot_row(
    store: StudioStore,
    commander: str,
    spec_hash: str,
    profile_name: str | None,
) -> sqlite3.Row | None:
    row = store.connection.execute(
        f"SELECT {_SELECT_COLUMNS} FROM tier_snapshot WHERE commander_name = ? AND spec_hash = ?",
        (commander, spec_hash),
    ).fetchone()
    if row is not None:
        return cast(sqlite3.Row, row)
    if profile_name is not None:
        fallback = store.connection.execute(
            f"SELECT {_SELECT_COLUMNS} FROM tier_snapshot "
            "WHERE commander_name = ? AND profile_name = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (commander, profile_name),
        ).fetchone()
        return cast(sqlite3.Row | None, fallback)
    return None


def read_snapshot(
    store: StudioStore,
    commander: str,
    settings: StrengthSettings,
    *,
    profile_name: str | None = None,
    with_layers: bool = True,
    dangling_universe_ok: bool = False,
    notices: Sequence[str] = (),
    saved_weights: Mapping[str, float] | None = None,
) -> dict[str, object]:
    """Return cached ``StrengthResult`` on HIT, or compute live with STALE/MISSING metadata."""
    from . import strength_view

    spec_hash = compute_spec_hash(settings, with_layers)
    current_epoch = epoch_fingerprint(store)
    row = _lookup_snapshot_row(store, commander, spec_hash, profile_name)

    if row is not None:
        row_spec_hash = str(row["spec_hash"])
        row_profile = str(row["profile_name"])
        row_spec_version = str(row["spec_version"])
        row_epoch = str(row["data_epoch"])
        row_created = str(row["created_at"])

        exact = (
            row_spec_hash == spec_hash
            and row_spec_version == SPEC_VERSION
            and row_epoch == current_epoch
            and not dangling_universe_ok
            and not notices
            and saved_weights is None
        )
        if exact:
            try:
                payload = json.loads(str(row["payload_json"]))
                tier_counts_obj = json.loads(str(row["tier_counts_json"]))
                comp_denoms = json.loads(str(row["component_denominators_json"]))
                if (
                    isinstance(payload, dict)
                    and isinstance(payload.get("cards"), list)
                    and isinstance(tier_counts_obj, dict)
                    and isinstance(comp_denoms, dict)
                ):
                    payload["snapshot"] = {
                        "status": "HIT",
                        "profile_name": row_profile,
                        "spec_hash": row_spec_hash,
                        "spec_version": row_spec_version,
                        "data_epoch": row_epoch,
                        "current_epoch": current_epoch,
                        "created_at": row_created,
                        "tier_counts": tier_counts_obj.get("total", payload.get("tier_counts")),
                        "component_denominators": comp_denoms,
                    }
                    return payload
            except (ValueError, TypeError):
                pass

        live = dict(
            strength_view.compute(
                store,
                commander,
                settings,
                dangling_universe_ok=dangling_universe_ok,
                notices=notices,
                saved_weights=saved_weights,
            )
        )
        raw_notices = live.get("notices")
        existing_notices = list(raw_notices) if isinstance(raw_notices, list) else []
        if STALE_NOTICE not in existing_notices:
            live["notices"] = [STALE_NOTICE, *existing_notices]
        live["snapshot"] = {
            "status": "STALE",
            "profile_name": profile_name or row_profile,
            "spec_hash": spec_hash,
            "snapshot_spec_hash": row_spec_hash,
            "spec_version": SPEC_VERSION,
            "snapshot_spec_version": row_spec_version,
            "snapshot_epoch": row_epoch,
            "current_epoch": current_epoch,
            "created_at": row_created,
        }
        return live

    live = dict(
        strength_view.compute(
            store,
            commander,
            settings,
            dangling_universe_ok=dangling_universe_ok,
            notices=notices,
            saved_weights=saved_weights,
        )
    )
    live["snapshot"] = {
        "status": "MISSING",
        "profile_name": profile_name,
        "spec_hash": spec_hash,
        "spec_version": SPEC_VERSION,
        "current_epoch": current_epoch,
    }
    return live


def latest_snapshot_summary(store: StudioStore, commander: str) -> dict[str, object] | None:
    """Return lightweight #1369 target summary without loading ``payload_json``."""
    row = store.connection.execute(
        f"SELECT {_SUMMARY_COLUMNS} FROM tier_snapshot "
        "WHERE commander_name = ? ORDER BY created_at DESC LIMIT 1",
        (commander,),
    ).fetchone()
    if row is None:
        return None
    try:
        tier_counts_obj = json.loads(str(row["tier_counts_json"]))
        comp_denoms = json.loads(str(row["component_denominators_json"]))
    except (ValueError, TypeError):
        return None
    if not isinstance(tier_counts_obj, dict) or not isinstance(comp_denoms, dict):
        return None
    current_epoch = epoch_fingerprint(store)
    return _summary_from_parts(
        commander_name=str(row["commander_name"]),
        profile_name=str(row["profile_name"]),
        spec_hash=str(row["spec_hash"]),
        spec_version=str(row["spec_version"]),
        data_epoch=str(row["data_epoch"]),
        current_epoch=current_epoch,
        created_at=str(row["created_at"]),
        tier_counts_obj=tier_counts_obj,
        component_denominators=comp_denoms,
    )


__all__ = [
    "SNAPSHOT_SCHEMA",
    "SPEC_VERSION",
    "STALE_NOTICE",
    "compute_spec_hash",
    "epoch_fingerprint",
    "latest_snapshot_summary",
    "read_snapshot",
    "write_snapshot",
]
