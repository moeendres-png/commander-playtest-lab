"""The strength index as the tier list page shows it: store access around ``strength.py``.

Reads the stored signals of ONE commander (``card_signal``), the counted deck-list share of
the chosen universe profile (``universe_view``) and hands them to the pure scoring
function. Figures of two commanders are never combined: every query names its commander,
and commander-independent signals are stored under the empty commander name.

The Owner's marks are not read here. The simulation component is ``NOT_COLLECTED``: the
stored simulation rows are per deck and per card cast statistics, not an outcome model.

Matching a stored card name to a pool card is deterministic and follows the counted
spread's name discipline (``universe_view.name_claims``): a name belongs to the card whose
**exact oracle name** it is; failing that, to the card whose **engine name** it is; failing
that, to the card whose **front face** it is (a front face is a spelling only when no other
Studio card has it as an exact name). Comparison is case-insensitive. A name that several
cards claim at the best level is ambiguous: it is given to none and listed in the result
(``ambiguous_names``), never dropped silently. When several stored rows resolve to one
card, the row with the better claim wins, then the smaller stored name.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import replace
from typing import TypedDict

from . import strength, universe
from .builder import pool_cards
from .store import StudioStore, now_utc
from .strength import (
    BRACKET_INCLUSION,
    COMBOS,
    COMMANDER_INCLUSION,
    DECK_UNIVERSE,
    GLOBAL_INCLUSION,
    SYNERGY,
    TOURNAMENT_LISTS,
    CardStrength,
    Observation,
    PoolContext,
    StrengthSettings,
)
from .tiers import TierParams
from .universe_view import ProfileSummary, name_claims, pool_spread, profile_summary

MAX_NAME = 80


class StrengthCard(TypedDict):
    card_id: str
    name: str
    index: float | None
    coverage: float | None
    tier: str
    reason: str
    note: str
    present: int
    components: list[strength.ComponentResult]


class AmbiguousName(TypedDict):
    signal: str
    name: str
    candidates: list[str]


class StrengthResult(TypedDict):
    schema: str
    data_class: str
    meaning: str
    commander: str
    settings: dict[str, object]
    universe: ProfileSummary | None
    universe_missing: str | None
    notices: list[str]
    collected: list[str]
    tier_counts: dict[str, int]
    ambiguous_names: list[AmbiguousName]
    cards: list[StrengthCard]


_INDEPENDENT = frozenset({"edhrec_global_inclusion", "spellbook_variants"})
# claim key -> [(claim kind, card id)]
_Claims = dict[str, list[tuple[int, str]]]


def _claim_index(store: StudioStore, ids: list[str]) -> _Claims:
    index: _Claims = {}
    for card_id, claims in name_claims(store, ids).items():
        for key, kind in claims:
            index.setdefault(key, []).append((kind, card_id))
    return index


def _signal_observations(
    store: StudioStore,
    commander: str,
    signal: str,
    claims: _Claims,
    display: Mapping[str, str],
    ambiguous: dict[tuple[str, str], list[str]],
) -> tuple[dict[str, Observation], bool]:
    """Observations of the pool cards for one stored signal, and whether the source has
    any row for it. Commander-independent signals sit under the empty commander name."""
    owner = "" if signal in _INDEPENDENT else commander
    best: dict[str, tuple[int, str, Observation]] = {}
    rows = store.connection.execute(
        "SELECT card_name, value, numerator, denominator FROM card_signal "
        "WHERE commander_name = ? AND signal = ? ORDER BY card_name",
        (owner, signal),
    ).fetchall()
    for row in rows:
        name = str(row["card_name"])
        found = claims.get(name.casefold())
        if not found:
            continue
        kind = min(item[0] for item in found)
        owners = sorted({card for item_kind, card in found if item_kind == kind})
        if len(owners) > 1:
            ambiguous[(signal, name)] = sorted(display[card] for card in owners)
            continue
        card_id = owners[0]
        rank = (kind, name)
        current = best.get(card_id)
        if current is None or rank < (current[0], current[1]):
            best[card_id] = (
                kind,
                name,
                Observation(row["value"], row["numerator"], row["denominator"]),
            )
    return {card_id: item[2] for card_id, item in best.items()}, bool(rows)


def _strings(value: object) -> set[str]:
    if not isinstance(value, list):
        raise TypeError("pool_cards returned an unexpected shape")
    return {str(item) for item in value}


class SignalCoverage(TypedDict):
    scope: str
    rows: int
    rows_with_value: int
    pool_cards_with_value: int
    pool_size: int


def signal_coverage(store: StudioStore, commander: str) -> dict[str, SignalCoverage]:
    """Per stored signal: its rows and how many of the commander's pool cards it gives a
    value (the same name matching as the index). Counts only. A signal without rows for
    this commander is listed with 0 rows: missing, not a weak signal. Raises KeyError when
    the commander is not in the collection."""
    pool = pool_cards(store, [commander], with_signals=False)
    raw_cards = pool["cards"]
    if not isinstance(raw_cards, list):
        raise TypeError("pool_cards returned an unexpected shape")
    ids = [str(card["card_id"]) for card in raw_cards]
    display = {str(card["card_id"]): str(card["name"]) for card in raw_cards}
    claims = _claim_index(store, ids)
    db = store.connection
    result: dict[str, SignalCoverage] = {}
    for row in db.execute("SELECT DISTINCT signal FROM card_signal ORDER BY signal"):
        signal = str(row[0])
        owner = "" if signal in _INDEPENDENT else commander
        counted = db.execute(
            "SELECT COUNT(*), COUNT(value) FROM card_signal "
            "WHERE commander_name = ? AND signal = ?",
            (owner, signal),
        ).fetchone()
        observed, _exists = _signal_observations(store, commander, signal, claims, display, {})
        result[signal] = {
            "scope": "independent" if signal in _INDEPENDENT else "commander",
            "rows": int(counted[0]),
            "rows_with_value": int(counted[1]),
            "pool_cards_with_value": sum(1 for item in observed.values() if item.value is not None),
            "pool_size": len(ids),
        }
    return result


class SignalValue(TypedDict):
    value: float | None
    numerator: int | None
    denominator: int | None


def card_signal_values(
    store: StudioStore, commander: str, card_ids: list[str], display: Mapping[str, str]
) -> dict[str, dict[str, SignalValue]]:
    """Stored usage signals of ONE commander per pool card, for the builder columns.

    Keys per card: ``inclusion`` (decks with the card over the commander's decks),
    ``synergy`` and ``global_inclusion`` (independent of the commander). A card without a
    row for a signal has no entry for it: unknown, never 0. Same name matching as the index."""
    claims = _claim_index(store, card_ids)
    wanted = {
        "inclusion": strength.signal_for(COMMANDER_INCLUSION, strength.BRACKET_NONE),
        "synergy": strength.signal_for(SYNERGY, strength.BRACKET_NONE),
        "global_inclusion": strength.signal_for(GLOBAL_INCLUSION, strength.BRACKET_NONE),
    }
    result: dict[str, dict[str, SignalValue]] = {}
    for key, signal in wanted.items():
        if not signal:
            continue
        observed, _exists = _signal_observations(store, commander, signal, claims, display, {})
        for card_id, item in observed.items():
            if item.value is None:
                continue
            result.setdefault(card_id, {})[key] = {
                "value": float(item.value),
                "numerator": item.numerator,
                "denominator": item.denominator,
            }
    return result


def _float(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def compute(
    store: StudioStore,
    commander: str,
    settings: StrengthSettings,
    *,
    dangling_universe_ok: bool = False,
) -> StrengthResult:
    """Index and tier for every legal pool card of ``commander``.

    Raises KeyError when the commander is not in the collection or the universe profile of
    the settings is unknown. With ``dangling_universe_ok`` (settings read from a saved
    profile) a universe profile that was deleted meanwhile is not an error: the index runs
    with "kein Universum" and the result carries a notice and ``universe_missing``."""
    pool = pool_cards(store, [commander], with_signals=False)
    raw_cards = pool["cards"]
    if not isinstance(raw_cards, list):
        raise TypeError("pool_cards returned an unexpected shape")
    ids = [str(card["card_id"]) for card in raw_cards]
    display = {str(card["card_id"]): str(card["name"]) for card in raw_cards}
    commander_ids = _strings(pool["commander_ids"])
    claims = _claim_index(store, ids)
    ambiguous: dict[tuple[str, str], list[str]] = {}

    notices: list[str] = []
    universe_missing: str | None = None
    summary: ProfileSummary | None = None
    if settings.universe_profile:
        try:
            summary = profile_summary(store, settings.universe_profile, commander_names=[commander])
        except KeyError:
            if not dangling_universe_ok:
                raise
            universe_missing = settings.universe_profile
            settings = replace(settings, universe_profile=None)
            notices.append(
                f"Das Universum „{universe_missing}“ dieser Einstellung gibt es nicht mehr: "
                "die Rechnung läuft mit „kein Universum“."
            )

    per_card: dict[str, dict[str, Observation]] = {card_id: {} for card_id in ids}
    collected: set[str] = set()
    for component in (
        COMMANDER_INCLUSION,
        BRACKET_INCLUSION,
        SYNERGY,
        TOURNAMENT_LISTS,
        GLOBAL_INCLUSION,
        COMBOS,
    ):
        signal = strength.signal_for(component, settings.bracket)
        if not signal:
            continue
        observed, exists = _signal_observations(
            store, commander, signal, claims, display, ambiguous
        )
        if exists:
            collected.add(component)
        for card_id, observation in observed.items():
            per_card[card_id][component] = observation

    filter_cards: set[str] = set()
    universe_minimum = 0
    if summary is not None:
        universe_minimum = summary["min_universe"]
        if summary["denominator"] > 0:
            collected.add(DECK_UNIVERSE)
            spread = pool_spread(store, summary["profile"], ids, commander_names=[commander])
            for item in spread["cards"]:
                if item["filter_card"]:
                    filter_cards.add(item["card_id"])
                elif item["hits"] is not None:
                    per_card[item["card_id"]][DECK_UNIVERSE] = Observation(
                        item["hits"] / item["denominator"], item["hits"], item["denominator"]
                    )

    type_group: dict[str, str] = {}
    bands: dict[str, str] = {}
    unranked: dict[str, str] = {}
    for card in raw_cards:
        card_id = str(card["card_id"])
        group = str(card["group"])
        type_group[card_id] = group
        bands[card_id] = strength.mana_band(_float(card["mana_value"]), is_land=group == "Land")
        if card_id in commander_ids:
            unranked[card_id] = strength.NOT_RANKED_COMMANDER
        elif card["basic"]:
            unranked[card_id] = strength.NOT_RANKED_BASIC_LAND
    context = PoolContext(type_group, bands, unranked, filter_cards, universe_minimum)

    scored = strength.score_pool(settings, per_card, collected, context=context)
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
        "universe": summary,
        "universe_missing": universe_missing,
        "notices": notices,
        "collected": sorted(collected),
        "tier_counts": {tier: tiers.get(tier, 0) for tier in (*strength.TIERS, "U", "N")},
        "ambiguous_names": [
            {"signal": signal, "name": name, "candidates": candidates}
            for (signal, name), candidates in sorted(ambiguous.items())
        ],
        "cards": cards,
    }


# ---------- saved settings of the Owner ----------


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned or len(cleaned) > MAX_NAME:
        raise ValueError(f"a profile name needs 1 to {MAX_NAME} characters")
    return cleaned


def save_profile(store: StudioStore, name: str, settings: StrengthSettings) -> ProfileEntry:
    cleaned = _clean_name(name)
    with store.connection as db:
        db.execute(
            "INSERT OR REPLACE INTO strength_profile(name, spec, created_at) VALUES (?, ?, ?)",
            (cleaned, json.dumps(settings.to_dict(), sort_keys=True), now_utc()),
        )
    return get_profile(store, cleaned)


class ProfileEntry(TypedDict):
    name: str
    settings: dict[str, object] | None
    created_at: str
    valid: bool
    reason: str | None
    universe_missing: str | None


def _entry(store: StudioStore, row: Mapping[str, object]) -> ProfileEntry:
    """A stored profile as the page lists it. A spec that no longer validates (settings
    that were valid when saved and are not any more) is listed with ``valid`` false and the
    reason, never an error that hides the other profiles. ``universe_missing`` names the
    universe profile a valid entry still points to although it was deleted."""
    name, created = str(row["name"]), str(row["created_at"])
    try:
        settings = StrengthSettings.from_dict(_as_mapping(json.loads(str(row["spec"]))))
    except (ValueError, TypeError) as error:  # json.JSONDecodeError is a ValueError
        return {
            "name": name,
            "settings": None,
            "created_at": created,
            "valid": False,
            "reason": str(error),
            "universe_missing": None,
        }
    missing: str | None = None
    if settings.universe_profile:
        try:
            universe.get_profile(store, settings.universe_profile)
        except KeyError:
            missing = settings.universe_profile
    return {
        "name": name,
        "settings": settings.to_dict(),
        "created_at": created,
        "valid": True,
        "reason": None,
        "universe_missing": missing,
    }


def get_profile(store: StudioStore, name: str) -> ProfileEntry:
    row = store.connection.execute(
        "SELECT name, spec, created_at FROM strength_profile WHERE name = ?", (name,)
    ).fetchone()
    if row is None:
        raise KeyError(name)
    return _entry(store, row)


def list_profiles(store: StudioStore) -> list[ProfileEntry]:
    rows = store.connection.execute(
        "SELECT name, spec, created_at FROM strength_profile ORDER BY name"
    ).fetchall()
    return [_entry(store, row) for row in rows]


def delete_profile(store: StudioStore, name: str) -> None:
    with store.connection as db:
        if db.execute("DELETE FROM strength_profile WHERE name = ?", (name,)).rowcount == 0:
            raise KeyError(name)


def _number_text(value: float) -> str:
    """A number the way the Owner reads it: 3 not 3.0, 0,4 with a decimal comma."""
    return (f"{value:g}").replace(".", ",")


_GROUP_CHOICES = {
    strength.GROUP_POOL: "ganzer Pool",
    strength.GROUP_TYPE: "gleicher Kartentyp",
    strength.GROUP_MANA_BAND: "gleiches Manawert-Band",
}
_MEASURE_CHOICES = {
    strength.MEASURE_WILSON: "Wilson-Untergrenze",
    strength.MEASURE_RAW: "roher Anteil",
}
_MISSING_CHOICES = {
    strength.MISSING_SKIP: "auslassen",
    strength.MISSING_LOWEST: "als niedrigster Rang zählen",
}
_BRACKET_CHOICES = {
    "core": "Core (Bracket 1-2)",
    "upgraded": "Upgraded (Bracket 3)",
    "optimized": "Optimized (Bracket 4)",
    "cedh": "cEDH (Bracket 5)",
    "none": "kein Bracket",
}


def _choices(names: Mapping[str, str], recommended: str) -> list[dict[str, object]]:
    return [
        {
            "value": value,
            "label": f"{label} (empfohlen)" if value == recommended else label,
            "recommended": value == recommended,
        }
        for value, label in names.items()
    ]


def _panel_texts() -> dict[str, object]:
    """Labels, help texts and choices of the settings panel, every label with the
    recommendation in parentheses. The recommended values are those of the defaults of
    ``StrengthSettings``: the page draws these texts and hard-codes no value."""
    rec = StrengthSettings()
    universe_minimum = TierParams().min_universe
    cuts = rec.tier_cuts
    labels: dict[str, str] = {}
    helps: dict[str, str] = {}
    for key, weight in rec.weights.items():
        labels[f"weights.{key}"] = f"{strength.LABELS[key]} (empfohlen: {_number_text(weight)})"
        helps[f"weights.{key}"] = (
            "Gewicht des Signals im Mittel der Ränge. 0 schaltet das Signal ab; "
            "ein leeres Feld nimmt den empfohlenen Wert."
        )
    labels[f"weights.{strength.SIMULATION}"] = (
        f"{strength.LABELS[strength.SIMULATION]} (empfohlen: "
        f"{_number_text(rec.weights[strength.SIMULATION])}, derzeit ohne Daten)"
    )
    helps[f"weights.{strength.SIMULATION}"] = (
        "Simulationsergebnisse zählen nicht in die Tierliste und werden dafür vorerst weder "
        "eingeholt noch verarbeitet. Das Gewicht bleibt als Option bestehen und steht auf 0."
    )
    labels["bracket"] = (
        "Bracket-Signal (empfohlen: upgraded für Chulane im Bracket 3; bei Turnierausrichtung cedh)"
    )
    helps["bracket"] = "Welche Bracket-Seite von EDHREC als Bracket-Signal zählt."
    labels["rank_group"] = (
        f"Vergleichsgruppe für den Rang (empfohlen: {_GROUP_CHOICES[rec.rank_group]})"
    )
    helps["rank_group"] = (
        "Gegen welche Karten der Rang berechnet wird. Eine Gruppe mit weniger als "
        f"{strength.MIN_GROUP} Karten mit Wert fällt auf den ganzen Pool zurück "
        "(steht dann in der Signalzeile)."
    )
    labels["share_measure"] = (
        f"Anteil messen als (empfohlen: {_MEASURE_CHOICES[rec.share_measure]})"
    )
    helps["share_measure"] = (
        "Die Wilson-Untergrenze ordnet Karten mit verschieden großen Nennern vorsichtiger; "
        "bei gleichem Nenner ändert sie die Reihenfolge nicht. Gegen kleine Stichproben "
        "schützt der Mindest-Nenner."
    )
    labels["min_denominators.edhrec"] = (
        f"Mindest-Nenner EDHREC-Signale (empfohlen: {rec.min_denominators['edhrec']} Decks)"
    )
    helps["min_denominators.edhrec"] = (
        "Hat die Quelle weniger Decks, wird das Signal für alle Karten nicht verwendet. 0 = kein Minimum."
    )
    labels["min_denominators.deck_universe"] = (
        "Mindest-Nenner Decklisten-Universum (empfohlen: das Mindest-Universum des "
        f"Universums, Standard {universe_minimum} Decks; hier nur lesbar)"
    )
    helps["min_denominators.deck_universe"] = (
        "Wird beim Universum eingestellt (Mindest-Universum) und gilt hier unverändert."
    )
    labels["min_denominators.tournament"] = (
        f"Mindest-Nenner Turnierlisten (empfohlen: {rec.min_denominators['tournament']} Listen)"
    )
    helps["min_denominators.tournament"] = (
        "Gibt es weniger Turnierlisten des Commanders, wird das Signal nicht verwendet. "
        "0 = kein Minimum."
    )
    for key in strength.MISSING_CAPABLE:
        labels[f"missing_value.{key}"] = (
            f"Fehlender Wert bei „{strength.LABELS[key]}“ "
            f"(empfohlen: {_MISSING_CHOICES[rec.missing_value[key]]})"
        )
        helps[f"missing_value.{key}"] = (
            "auslassen: eine nicht gelistete Karte ist eine fehlende Beobachtung (Owner-"
            "Entscheidung B5). als niedrigster Rang: nur sinnvoll, wenn die Quelle die "
            "Karten des Commanders fast vollständig nennt."
        )
    labels["rank_commander_and_basics"] = (
        "Commander und Standardländer bewerten "
        f"(empfohlen: {'an' if rec.rank_commander_and_basics else 'aus'})"
    )
    helps["rank_commander_and_basics"] = (
        "aus: der Commander und die Standardländer bekommen keine Stufe "
        "(„nicht bewertet“) und nehmen keinen Rang weg."
    )
    labels["min_coverage"] = (
        f"Mindestabdeckung in % (empfohlen: {_number_text(round(rec.min_coverage * 100, 1))})"
    )
    helps["min_coverage"] = (
        "Anteil des Gewichts, der vorhanden sein muss, sonst „zu wenig Daten“. Bei 0 kann eine "
        "nicht gelistete Karte (nur ihre anderen Signale zählen) eine Karte überholen, die "
        "eine Quelle bei 1 von 755 Decks nennt."
    )
    labels["min_components"] = f"Mindestzahl Signale (empfohlen: {rec.min_components})"
    helps["min_components"] = "Wie viele gewichtete Signale mindestens vorhanden sein müssen."
    for tier in ("S", "A", "B", "C"):
        labels[f"tier_cuts.{tier}"] = f"Grenze {tier} (empfohlen: {_number_text(cuts[tier])})"
        helps[f"tier_cuts.{tier}"] = (
            "Ab diesem Index beginnt die Stufe. Die Grenzen müssen von S bis C streng fallen."
        )
    groups = [
        {"title": "Gewichte je Signal", "keys": [f"weights.{key}" for key in rec.weights]},
        {"title": "Bracket", "keys": ["bracket"]},
        {"title": "Vergleichsgruppe für den Rang", "keys": ["rank_group"]},
        {"title": "Anteil messen als", "keys": ["share_measure"]},
        {
            "title": "Mindest-Nenner je Signal",
            "keys": [
                "min_denominators.edhrec",
                "min_denominators.deck_universe",
                "min_denominators.tournament",
            ],
        },
        {
            "title": "Fehlender Wert",
            "keys": [f"missing_value.{key}" for key in strength.MISSING_CAPABLE],
        },
        {"title": "Commander und Standardländer", "keys": ["rank_commander_and_basics"]},
        {"title": "Mindestdaten für eine Stufe", "keys": ["min_coverage", "min_components"]},
        {
            "title": (
                "Tier-Grenzen (empfohlen: "
                + " / ".join(_number_text(cuts[tier]) for tier in ("S", "A", "B", "C"))
                + ")"
            ),
            "keys": [f"tier_cuts.{tier}" for tier in ("S", "A", "B", "C")],
        },
    ]
    return {
        "labels": labels,
        "help": helps,
        "groups": groups,
        "choices": {
            "bracket": _choices(_BRACKET_CHOICES, rec.bracket),
            "rank_group": _choices(_GROUP_CHOICES, rec.rank_group),
            "share_measure": _choices(_MEASURE_CHOICES, rec.share_measure),
            "missing_value": _choices(_MISSING_CHOICES, strength.MISSING_SKIP),
            "rank_commander_and_basics": [
                {"value": False, "label": "aus (empfohlen)", "recommended": True},
                {"value": True, "label": "an", "recommended": False},
            ],
        },
        "universe_minimum": universe_minimum,
    }


def presets() -> dict[str, object]:
    """Built-in presets, the recommended values and what the settings panel needs to draw
    itself. ``recommended`` is the one place the recommendations come from."""
    recommended = StrengthSettings().to_dict()
    return {
        "presets": [
            {"name": name, "settings": item.to_dict()} for name, item in strength.PRESETS.items()
        ],
        "components": [
            {"key": key, "label": strength.LABELS[key], "default_weight": weight}
            for key, weight in strength.DEFAULT_WEIGHTS.items()
        ],
        "brackets": [*strength.BRACKETS, strength.BRACKET_NONE],
        "defaults": recommended,
        "recommended": recommended,
        "missing_capable": list(strength.MISSING_CAPABLE),
        "min_group": strength.MIN_GROUP,
        "panel": _panel_texts(),
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
        entry = get_profile(store, profile)
        if entry["settings"] is None:
            raise ValueError(
                f"strength profile {profile!r} is not valid any more: {entry['reason']}"
            )
        return StrengthSettings.from_dict(entry["settings"])
    if preset is not None:
        return strength.PRESETS[preset]
    return StrengthSettings()


def _as_mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError("settings must be a mapping")
    return value


__all__ = [
    "ProfileEntry",
    "SignalCoverage",
    "SignalValue",
    "StrengthResult",
    "card_signal_values",
    "compute",
    "delete_profile",
    "get_profile",
    "list_profiles",
    "presets",
    "resolve_settings",
    "save_profile",
    "signal_coverage",
]
