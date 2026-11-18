"""Defensive field reading with ordered fallback chains (#1453).

Reads external CSV/JSON row fields through explicit, ordered alias tuples so an upstream
column rename (such as EDHREC ``inclusion`` <-> ``num_decks``) is resolved deterministically
and recorded in ``fallbacks_used`` without altering signal definitions, denominators, or the
fail-closed #1416 rate alarms when all aliases are absent or empty.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from .store import StudioStore

EDHREC_DECK_COUNT_ALIASES: tuple[str, ...] = (
    "num_decks",
    "inclusion",
    "decks",
    "decks_with_card",
    "decks_with_card_n_shown",
    "decks_with_card_reported",
)
EDHREC_POTENTIAL_DECKS_ALIASES: tuple[str, ...] = (
    "potential_decks",
    "total_decks",
    "num_decks_potential",
    "eligible_decks",
    "eligible_decks_N_shown",
    "eligible_decks_per_card",
)
EDHREC_INCLUSION_PCT_ALIASES: tuple[str, ...] = (
    "inclusion_pct",
    "inclusion_pct_shown",
    "inclusion_pct_reported",
    "inclusion_rate",
)
EDHREC_SYNERGY_ALIASES: tuple[str, ...] = (
    "synergy",
    "synergy_score",
    "synergy_pct",
    "synergy_pct_shown",
)
EDHREC_LIFT_ALIASES: tuple[str, ...] = (
    "lift",
    "lift_shown",
    "lift_reported",
    "lift_x_reported",
)
CARD_NAME_ALIASES: tuple[str, ...] = (
    "card_name",
    "name",
    "karte",
    "oracle_name",
    "reported_card_name",
    "card_name_on_page",
    "card_name_reported",
)
COMMANDER_NAME_ALIASES: tuple[str, ...] = (
    "commander_name",
    "commander",
)
DECK_LIST_CARDS_ALIASES: tuple[str, ...] = (
    "cards",
    "mainboard",
    "deck_cards",
)

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "num_decks": EDHREC_DECK_COUNT_ALIASES,
    "potential_decks": EDHREC_POTENTIAL_DECKS_ALIASES,
    "inclusion_pct": EDHREC_INCLUSION_PCT_ALIASES,
    "synergy": EDHREC_SYNERGY_ALIASES,
    "lift": EDHREC_LIFT_ALIASES,
    "card_name": CARD_NAME_ALIASES,
    "commander_name": COMMANDER_NAME_ALIASES,
    "cards": DECK_LIST_CARDS_ALIASES,
}

META_FALLBACKS_KEY = "fallbacks_used"


@dataclass
class FallbackTracker:
    """Counts how often a non-primary alias (index >= 1) satisfied a field read (#1453)."""

    counts: dict[tuple[str, str], int] = field(default_factory=dict)

    def record(self, canonical_name: str, used_alias: str, count: int = 1) -> None:
        if count <= 0:
            return
        key = (canonical_name, used_alias)
        self.counts[key] = self.counts.get(key, 0) + count

    def merge(self, other: FallbackTracker) -> None:
        for (canon, alias), cnt in other.counts.items():
            self.record(canon, alias, cnt)

    def to_dict(self) -> dict[str, int]:
        return {
            f"{canon}<-{alias}" if canon else alias: cnt
            for (canon, alias), cnt in sorted(self.counts.items())
        }


def _is_non_empty(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def read_field(
    row: Mapping[str, object],
    aliases: Sequence[str],
    *,
    tracker: FallbackTracker | None = None,
    canonical_name: str = "",
) -> tuple[object | None, str | None]:
    """Read the first non-None, non-empty field from ``aliases`` in order (#1453).

    Returns ``(value, used_alias)`` or ``(None, None)`` when all aliases are absent or empty.
    When an alias at index >= 1 wins, records ``(canonical_name or aliases[0], used_alias)``
    in ``tracker``.
    """
    if not aliases:
        return None, None
    canonical = canonical_name or aliases[0]
    for idx, alias in enumerate(aliases):
        if alias not in row:
            continue
        val = row[alias]
        if _is_non_empty(val):
            if idx >= 1 and tracker is not None:
                tracker.record(canonical, alias)
            return val, alias
    return None, None


def read_str(
    row: Mapping[str, object],
    aliases: Sequence[str],
    *,
    tracker: FallbackTracker | None = None,
    canonical_name: str = "",
) -> str:
    """Read a string field via ``read_field``, returning ``""`` when all aliases are empty."""
    val, _alias = read_field(row, aliases, tracker=tracker, canonical_name=canonical_name)
    if val is None:
        return ""
    return str(val).strip()


def missing_required_columns(
    fieldnames: Sequence[str] | None,
    required: set[str],
    *,
    alias_map: Mapping[str, Sequence[str]] | None = None,
) -> set[str]:
    """Return required column names that are neither present directly nor via a known alias."""
    present = set(fieldnames or ())
    mapping = alias_map if alias_map is not None else FIELD_ALIASES
    missing: set[str] = set()
    for col in required:
        candidates = mapping.get(col, (col,))
        if col not in present and not any(alias in present for alias in candidates):
            missing.add(col)
    return missing


def store_fallbacks_used(store: StudioStore) -> dict[str, int]:
    """Return the cumulative ``fallbacks_used`` dictionary recorded in ``store``."""
    row = store.connection.execute(
        "SELECT value FROM meta WHERE key = ?",
        (META_FALLBACKS_KEY,),
    ).fetchone()
    if row is None or not row[0]:
        return {}
    try:
        loaded = json.loads(str(row[0]))
    except ValueError:
        return {}
    if not isinstance(loaded, dict):
        return {}
    result: dict[str, int] = {}
    for k, v in sorted(loaded.items()):
        if isinstance(k, str) and isinstance(v, int) and not isinstance(v, bool) and v > 0:
            result[k] = v
    return result


def record_store_fallbacks(store: StudioStore, fallbacks: Mapping[str, int]) -> dict[str, int]:
    """Persist non-empty ``fallbacks`` counts into ``store`` meta and return the merged map."""
    if not fallbacks:
        return store_fallbacks_used(store)
    merged = store_fallbacks_used(store)
    for k, v in fallbacks.items():
        if v > 0:
            merged[k] = merged.get(k, 0) + int(v)
    if merged:
        store.connection.execute(
            "INSERT INTO meta(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (META_FALLBACKS_KEY, json.dumps(dict(sorted(merged.items())), ensure_ascii=False)),
        )
    return dict(sorted(merged.items()))
