"""The strength index as the tier list page shows it: store access around ``strength.py``.

Reads the stored signals of ONE commander (``card_signal``), the counted deck-list share of
the chosen universe profile (``universe_view``) and hands them to the pure scoring
function. Figures of two commanders are never combined: every query names its commander,
and commander-independent signals are stored under the empty commander name. The
Playgroup atlas signal is one of them: an observed win-rate correlation from multiplayer
games, published per card, not per commander.

The Owner's marks are not read here. The simulation component is ``NOT_COLLECTED``: the
stored simulation rows are per deck and per card cast statistics, not an outcome model.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from typing import TypedDict

from . import strength
from .builder import pool_cards
from .store import StudioStore, now_utc
from .strength import (
    BRACKET_INCLUSION,
    COMBOS,
    COMMANDER_INCLUSION,
    DECK_UNIVERSE,
    GLOBAL_INCLUSION,
    PLAYGROUP_OBSERVED,
    SYNERGY,
    TOURNAMENT_LISTS,
    CardStrength,
    Observation,
    StrengthSettings,
)
from .universe_view import ProfileSummary, pool_spread, profile_summary

MAX_NAME = 80


class StrengthCard(TypedDict):
    card_id: str
    name: str
    index: float | None
    coverage: float
    tier: str
    reason: str
    present: int
    components: list[strength.ComponentResult]


class StrengthResult(TypedDict):
    schema: str
    data_class: str
    meaning: str
    commander: str
    settings: dict[str, object]
    universe: ProfileSummary | None
    collected: list[str]
    tier_counts: dict[str, int]
    cards: list[StrengthCard]


def _front(name: str) -> str:
    return name.split(" // ")[0].strip()


def _name_index(names: Mapping[str, tuple[str, str]]) -> dict[str, str]:
    """Casefolded name key -> card id; a key that two pool cards claim is dropped."""
    claims: dict[str, set[str]] = {}
    for card_id, (oracle, engine) in names.items():
        for name in (oracle, engine, _front(oracle), _front(engine)):
            if name:
                claims.setdefault(name.casefold(), set()).add(card_id)
    return {key: next(iter(ids)) for key, ids in claims.items() if len(ids) == 1}


def _signal_observations(
    store: StudioStore, commander: str, signal: str, by_name: Mapping[str, str]
) -> tuple[dict[str, Observation], bool]:
    """Observations of the pool cards for one stored signal, and whether the source has
    any row for it. Commander-independent signals sit under the empty commander name."""
    owner = "" if signal in _INDEPENDENT else commander
    out: dict[str, Observation] = {}
    rows = store.connection.execute(
        "SELECT card_name, value, numerator, denominator FROM card_signal "
        "WHERE commander_name = ? AND signal = ?",
        (owner, signal),
    ).fetchall()
    for row in rows:
        card_id = by_name.get(str(row["card_name"]).casefold())
        if card_id is not None and card_id not in out:
            out[card_id] = Observation(row["value"], row["numerator"], row["denominator"])
    return out, bool(rows)


_INDEPENDENT = frozenset(
    {"edhrec_global_inclusion", "spellbook_variants", "playgroup_observed_winrate_gap"}
)


def compute(store: StudioStore, commander: str, settings: StrengthSettings) -> StrengthResult:
    """Index and tier for every legal pool card of ``commander``.

    Raises KeyError when the commander is not in the collection or the universe profile of
    the settings is unknown."""
    pool = pool_cards(store, [commander])
    raw_cards = pool["cards"]
    if not isinstance(raw_cards, list):
        raise TypeError("pool_cards returned an unexpected shape")
    ids = [str(card["card_id"]) for card in raw_cards]
    display = {str(card["card_id"]): str(card["name"]) for card in raw_cards}
    names: dict[str, tuple[str, str]] = {}
    for row in store.connection.execute("SELECT card_id, oracle_name, engine_name FROM card_fact"):
        if str(row["card_id"]) in display:
            names[str(row["card_id"])] = (str(row["oracle_name"]), str(row["engine_name"]))
    by_name = _name_index(names)

    per_card: dict[str, dict[str, Observation]] = {card_id: {} for card_id in ids}
    collected: set[str] = set()
    for component in (
        COMMANDER_INCLUSION,
        BRACKET_INCLUSION,
        SYNERGY,
        TOURNAMENT_LISTS,
        GLOBAL_INCLUSION,
        COMBOS,
        PLAYGROUP_OBSERVED,
    ):
        signal = strength.signal_for(component, settings.bracket)
        if not signal:
            continue
        observed, exists = _signal_observations(store, commander, signal, by_name)
        if exists:
            collected.add(component)
        for card_id, observation in observed.items():
            per_card[card_id][component] = observation

    universe: ProfileSummary | None = None
    if settings.universe_profile:
        universe = profile_summary(store, settings.universe_profile, commander_names=[commander])
        if universe["denominator"] > 0:
            collected.add(DECK_UNIVERSE)
            spread = pool_spread(store, settings.universe_profile, ids, commander_names=[commander])
            for item in spread["cards"]:
                if item["hits"] is not None:
                    per_card[item["card_id"]][DECK_UNIVERSE] = Observation(
                        item["hits"] / item["denominator"], item["hits"], item["denominator"]
                    )

    scored = strength.score_pool(settings, per_card, collected)
    cards: list[StrengthCard] = []
    for card_id in ids:
        result: CardStrength = scored[card_id]
        cards.append({"card_id": card_id, "name": display[card_id], **result})
    tiers = Counter(card["tier"] for card in cards)
    return {
        "schema": strength.SCHEMA,
        "data_class": strength.DATA_CLASS,
        "meaning": strength.MEANING,
        "commander": commander,
        "settings": settings.to_dict(),
        "universe": universe,
        "collected": sorted(collected),
        "tier_counts": {tier: tiers.get(tier, 0) for tier in (*strength.TIERS, "U")},
        "cards": cards,
    }


# ---------- saved settings of the Owner ----------


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned or len(cleaned) > MAX_NAME:
        raise ValueError(f"a profile name needs 1 to {MAX_NAME} characters")
    return cleaned


def save_profile(store: StudioStore, name: str, settings: StrengthSettings) -> dict[str, object]:
    cleaned = _clean_name(name)
    with store.connection as db:
        db.execute(
            "INSERT OR REPLACE INTO strength_profile(name, spec, created_at) VALUES (?, ?, ?)",
            (cleaned, json.dumps(settings.to_dict(), sort_keys=True), now_utc()),
        )
    return get_profile(store, cleaned)


def get_profile(store: StudioStore, name: str) -> dict[str, object]:
    row = store.connection.execute(
        "SELECT name, spec, created_at FROM strength_profile WHERE name = ?", (name,)
    ).fetchone()
    if row is None:
        raise KeyError(name)
    return {
        "name": str(row["name"]),
        "settings": StrengthSettings.from_dict(json.loads(row["spec"])).to_dict(),
        "created_at": str(row["created_at"]),
    }


def list_profiles(store: StudioStore) -> list[dict[str, object]]:
    names = [
        str(row["name"])
        for row in store.connection.execute("SELECT name FROM strength_profile ORDER BY name")
    ]
    return [get_profile(store, name) for name in names]


def delete_profile(store: StudioStore, name: str) -> None:
    with store.connection as db:
        if db.execute("DELETE FROM strength_profile WHERE name = ?", (name,)).rowcount == 0:
            raise KeyError(name)


def presets() -> dict[str, object]:
    """Built-in presets plus what the settings panel needs to draw itself."""
    return {
        "presets": [
            {"name": name, "settings": item.to_dict()} for name, item in strength.PRESETS.items()
        ],
        "components": [
            {"key": key, "label": strength.LABELS[key], "default_weight": weight}
            for key, weight in strength.DEFAULT_WEIGHTS.items()
        ],
        "brackets": [*strength.BRACKETS, strength.BRACKET_NONE],
        "defaults": StrengthSettings().to_dict(),
        "meaning": strength.MEANING,
    }


def resolve_settings(
    store: StudioStore,
    *,
    preset: str | None,
    profile: str | None,
    settings: Mapping[str, object] | None,
) -> StrengthSettings:
    """Settings from at most one source: explicit settings, a saved profile or a preset.

    Raises ValueError for several sources or invalid settings, KeyError for an unknown
    preset or profile; none given means the default settings."""
    if sum(item is not None for item in (preset, profile, settings)) > 1:
        raise ValueError("give at most one of preset, profile and settings")
    if settings is not None:
        return StrengthSettings.from_dict(settings)
    if profile is not None:
        return StrengthSettings.from_dict(_as_mapping(get_profile(store, profile)["settings"]))
    if preset is not None:
        return strength.PRESETS[preset]
    return StrengthSettings()


def _as_mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError("settings must be a mapping")
    return value


__all__ = [
    "StrengthResult",
    "compute",
    "delete_profile",
    "get_profile",
    "list_profiles",
    "presets",
    "resolve_settings",
    "save_profile",
]
