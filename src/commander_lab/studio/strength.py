"""Strength index of the tier list: a configurable estimate from usage signals.

``score_pool`` is a pure function: settings and per-card observations in, index and tier
per card out. No I/O, no clock, no store. The store side lives in ``strength_view.py``.

What the index is. It is ``DERIVED_DESCRIPTIVE``: a weighted mean of percentile ranks of
usage signals (how often a card is played in decks of one commander, in a bracket, in the
deck lists the Owner chose, in tournament lists, how many combos it is part of, how
popular it is overall). It is an estimate from usage, not a measured win rate. The
outcome-based field of ``evidence.py`` stays ``UNRATED`` and is not touched here.

How it is computed, per commander and per signal:

1. A share-type signal carries a numerator and a denominator (decks with the card, decks
   in the sample). Its value is the lower bound of the 95 % Wilson interval of that share
   (setting "Anteil messen als": ``wilson``) or the raw share (``raw``). What Wilson does
   and does not do: it shrinks a share towards 0.5 the more, the smaller the denominator
   is, so it can reorder cards **whose denominators differ**. Within one signal of one
   commander all cards usually share one denominator, and then the bound is a monotone
   function of the numerator: the order stays exactly the raw order and the percentile
   below still spreads over 0..1, whatever the sample size. Wilson is therefore no
   protection against a small sample. That protection is the **minimum denominator per
   signal** (settings): below it the whole signal is ``NO_VALUE`` with the reason
   ``BELOW_MIN_DENOMINATOR`` for every card, and it is not used. Synergy and combo counts
   have no denominator and are used as published.
2. The value becomes a percentile rank (0..1) among the cards of the commander's legal pool
   that have a value for that signal and are ranked at all. The comparison group is the
   whole pool (default), the cards of the same main type or of the same mana value band
   (setting); a group with fewer than ``MIN_GROUP`` valued cards falls back to the pool
   and the component row says so. Ties share the mean rank. The commander card and basic
   lands are not ranked (tier ``N``, "nicht bewertet") unless the Owner switches that on;
   the cards a deck-universe card filter requires get status ``FILTER_CARD`` in the deck
   universe component (they are in every deck of the subset by definition: no value, not
   ranked).
3. The index is the weighted mean of the available percentiles, times 100. A component
   without a value is left out and the remaining weights are renormalised. A card that a
   source does not list is a missing observation, never a weak card: it lowers the
   coverage, not the percentile. Only for the commander inclusion, the bracket inclusion
   and the deck universe, sources that list the commander's cards fairly completely, the
   Owner can choose "als niedrigster Rang zählen": an unlisted card then gets percentile 0
   in that component (status ``MISSING_AS_LOWEST``, named as such in the row). Note that
   with ``min_coverage`` 0 an unlisted card (only its other signals count) can outrank a
   card that a source lists at 1 of 755 decks: the recommended minimum coverage exists for
   that reason.
4. ``coverage`` is the weight of the present components over the weight of all components
   with a positive weight. Tier ``U`` ("zu wenig Daten") when the coverage is below
   ``min_coverage`` or fewer than ``min_components`` components with a weight are present;
   otherwise the tier follows the index cuts.

The Owner's marks (favorite, excluded, note) are never an input.
"""

from __future__ import annotations

import math
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from itertools import pairwise
from typing import TypedDict

SCHEMA = "studio-strength-1"
DATA_CLASS = "DERIVED_DESCRIPTIVE"
MEANING = (
    "Stärke-Index: eine Schätzung aus Nutzungssignalen (wie oft eine Karte bei diesem "
    "Commander, in einem Bracket, in den gewählten Decklisten und in Turnierlisten gespielt "
    "wird). Er ist keine gemessene Siegrate und keine Aussage über Ergebnisse. Fehlende "
    "Beobachtungen senken die Abdeckung, nie die Karte. Favoriten, Ausschlüsse und Notizen "
    "fließen nicht ein."
)

PRESENT = "PRESENT"
NO_VALUE = "NO_VALUE"
NOT_COLLECTED = "NOT_COLLECTED"
FILTER_CARD = "FILTER_CARD"
NOT_RANKED = "NOT_RANKED"
MISSING_AS_LOWEST = "MISSING_AS_LOWEST"

# Reasons of a component row (empty when the row needs none).
BELOW_MIN_DENOMINATOR = "BELOW_MIN_DENOMINATOR"
NOT_LISTED = "NOT_LISTED"
VALUE_UNKNOWN = "VALUE_UNKNOWN"
GROUP_TOO_SMALL = "GROUP_TOO_SMALL"
NOT_RANKED_COMMANDER = "NOT_RANKED_COMMANDER"
NOT_RANKED_BASIC_LAND = "NOT_RANKED_BASIC_LAND"

TIER_UNKNOWN = "U"
TIER_NOT_RANKED = "N"
TIERS = ("S", "A", "B", "C", "D")
BRACKETS = ("core", "upgraded", "optimized", "cedh")
BRACKET_NONE = "none"
Z_95 = 1.959963984540054
MIN_GROUP = 5

GROUP_POOL = "pool"
GROUP_TYPE = "type"
GROUP_MANA_BAND = "mana_band"
RANK_GROUPS = (GROUP_POOL, GROUP_TYPE, GROUP_MANA_BAND)
MEASURE_WILSON = "wilson"
MEASURE_RAW = "raw"
SHARE_MEASURES = (MEASURE_WILSON, MEASURE_RAW)
MISSING_SKIP = "skip"
MISSING_LOWEST = "lowest"
MISSING_CHOICES = (MISSING_SKIP, MISSING_LOWEST)
MIN_EDHREC = "edhrec"
MIN_TOURNAMENT = "tournament"
MIN_DENOMINATOR_KEYS = (MIN_EDHREC, MIN_TOURNAMENT)
MAX_MIN_DENOMINATOR = 100000
# Mana value bands of the comparison group "gleiches Manawert-Band"; lands are their own band.
MANA_BANDS = ("0-1", "2", "3", "4", "5+")
BAND_LAND = "Land"
BAND_UNKNOWN = "unbekannt"

COMMANDER_INCLUSION = "commander_inclusion"
BRACKET_INCLUSION = "bracket_inclusion"
DECK_UNIVERSE = "deck_universe"
SYNERGY = "synergy"
TOURNAMENT_LISTS = "tournament_lists"
GLOBAL_INCLUSION = "global_inclusion"
COMBOS = "combos"
SIMULATION = "simulation"

COMPONENTS = (
    COMMANDER_INCLUSION,
    BRACKET_INCLUSION,
    DECK_UNIVERSE,
    SYNERGY,
    TOURNAMENT_LISTS,
    GLOBAL_INCLUSION,
    COMBOS,
    SIMULATION,
)
LABELS: dict[str, str] = {
    COMMANDER_INCLUSION: "Aufnahme beim Commander (EDHREC)",
    BRACKET_INCLUSION: "Aufnahme im Bracket (EDHREC)",
    DECK_UNIVERSE: "Decklisten-Universum (gezählt)",
    SYNERGY: "Synergie (EDHREC)",
    TOURNAMENT_LISTS: "Turnierlisten des Commanders",
    GLOBAL_INCLUSION: "Aufnahme überhaupt (EDHREC)",
    COMBOS: "Kombos (Commander Spellbook)",
    SIMULATION: "Simulation",
}
# Components whose value is a share with a numerator and a denominator (Wilson bound).
SHARE_COMPONENTS = frozenset(
    {COMMANDER_INCLUSION, BRACKET_INCLUSION, DECK_UNIVERSE, TOURNAMENT_LISTS, GLOBAL_INCLUSION}
)
# Sources that list the commander's cards fairly completely: only for these may an unlisted
# card be counted as the lowest rank (Owner decision B5 keeps "absent" a missing observation).
MISSING_CAPABLE = (COMMANDER_INCLUSION, BRACKET_INCLUSION, DECK_UNIVERSE)
_EDHREC_SHARES = frozenset({COMMANDER_INCLUSION, BRACKET_INCLUSION, GLOBAL_INCLUSION})

# The recommended values are the defaults of ``StrengthSettings`` and of these constants: one
# place in Python. ``strength_view.presets`` serves them, the page never hard-codes them.
DEFAULT_WEIGHTS: dict[str, float] = {
    COMMANDER_INCLUSION: 3.0,
    BRACKET_INCLUSION: 2.0,
    DECK_UNIVERSE: 2.0,
    SYNERGY: 1.0,
    TOURNAMENT_LISTS: 1.0,
    GLOBAL_INCLUSION: 1.0,
    COMBOS: 1.0,
    SIMULATION: 0.0,
}
DEFAULT_CUTS: dict[str, float] = {"S": 90.0, "A": 75.0, "B": 55.0, "C": 35.0}
DEFAULT_MIN_DENOMINATORS: dict[str, int] = {MIN_EDHREC: 30, MIN_TOURNAMENT: 5}
DEFAULT_BRACKET = "upgraded"
DEFAULT_MIN_COVERAGE = 0.4
DEFAULT_MIN_COMPONENTS = 2
MAX_WEIGHT = 100.0

_SETTINGS_KEYS = frozenset(
    {
        "weights",
        "bracket",
        "universe_profile",
        "min_coverage",
        "min_components",
        "tier_cuts",
        "rank_group",
        "share_measure",
        "min_denominators",
        "missing_value",
        "rank_commander_and_basics",
    }
)


def signal_for(component: str, bracket: str) -> str:
    """The stored signal name behind a component (empty when none is stored)."""
    if component == BRACKET_INCLUSION:
        return f"edhrec_bracket_inclusion:{bracket}" if bracket != BRACKET_NONE else ""
    return {
        COMMANDER_INCLUSION: "edhrec_commander_inclusion",
        DECK_UNIVERSE: "deck_list_share",
        SYNERGY: "edhrec_commander_synergy",
        TOURNAMENT_LISTS: "tournament_lists",
        GLOBAL_INCLUSION: "edhrec_global_inclusion",
        COMBOS: "spellbook_variants",
        SIMULATION: "",
    }[component]


def mana_band(mana_value: float | None, *, is_land: bool) -> str:
    """The mana value band of a card: lands are their own band, 0 and 1 share one band,
    5 and more share the last one, an unknown mana value is ``unbekannt`` (never 0)."""
    if is_land:
        return BAND_LAND
    if mana_value is None or not math.isfinite(mana_value):
        return BAND_UNKNOWN
    if mana_value < 2:
        return MANA_BANDS[0]
    if mana_value >= 5:
        return MANA_BANDS[4]
    return MANA_BANDS[int(mana_value) - 1]


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _count(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be a whole number")
    if not 0 <= value <= MAX_MIN_DENOMINATOR:
        raise ValueError(f"{name} must be between 0 and {MAX_MIN_DENOMINATOR}")
    return value


@dataclass(frozen=True)
class StrengthSettings:
    """The Owner's settings of the index. Validated on construction. The defaults are the
    recommended values."""

    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    bracket: str = DEFAULT_BRACKET
    universe_profile: str | None = None
    min_coverage: float = DEFAULT_MIN_COVERAGE
    min_components: int = DEFAULT_MIN_COMPONENTS
    tier_cuts: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_CUTS))
    rank_group: str = GROUP_POOL
    share_measure: str = MEASURE_WILSON
    min_denominators: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_MIN_DENOMINATORS))
    missing_value: dict[str, str] = field(default_factory=dict)
    rank_commander_and_basics: bool = False

    def __post_init__(self) -> None:
        weights = {name: DEFAULT_WEIGHTS[name] for name in COMPONENTS}
        for name, value in self.weights.items():
            if name not in DEFAULT_WEIGHTS:
                raise ValueError(f"unknown component: {name}")
            weight = _number(value, f"weight {name}")
            if weight < 0 or weight > MAX_WEIGHT:
                raise ValueError(f"weight {name} must be between 0 and {MAX_WEIGHT:g}")
            weights[name] = weight
        if self.bracket != BRACKET_NONE and self.bracket not in BRACKETS:
            raise ValueError("bracket must be one of core, upgraded, optimized, cedh, none")
        if self.universe_profile is not None and not self.universe_profile.strip():
            raise ValueError("universe_profile must be a name or none")
        coverage = _number(self.min_coverage, "min_coverage")
        if not 0.0 <= coverage <= 1.0:
            raise ValueError("min_coverage must be between 0 and 1")
        if (
            isinstance(self.min_components, bool)
            or not isinstance(self.min_components, int)
            or not 0 <= self.min_components <= len(COMPONENTS)
        ):
            raise ValueError(f"min_components must be an integer from 0 to {len(COMPONENTS)}")
        if set(self.tier_cuts) != set(DEFAULT_CUTS):
            raise ValueError("tier_cuts needs exactly S, A, B and C")
        cuts = {tier: _number(self.tier_cuts[tier], f"cut {tier}") for tier in DEFAULT_CUTS}
        ordered = [cuts[tier] for tier in ("S", "A", "B", "C")]
        if any(not 0.0 <= cut <= 100.0 for cut in ordered):
            raise ValueError("tier cuts must lie between 0 and 100")
        if any(high <= low for high, low in pairwise(ordered)):
            raise ValueError("tier cuts must fall strictly from S to C")
        if self.rank_group not in RANK_GROUPS:
            raise ValueError(f"rank_group must be one of {', '.join(RANK_GROUPS)}")
        if self.share_measure not in SHARE_MEASURES:
            raise ValueError(f"share_measure must be one of {', '.join(SHARE_MEASURES)}")
        unknown_minimum = set(self.min_denominators) - set(MIN_DENOMINATOR_KEYS)
        if unknown_minimum:
            raise ValueError(f"unknown min_denominators: {', '.join(sorted(unknown_minimum))}")
        minimums = {
            key: _count(self.min_denominators.get(key, DEFAULT_MIN_DENOMINATORS[key]), key)
            for key in MIN_DENOMINATOR_KEYS
        }
        unknown_missing = set(self.missing_value) - set(MISSING_CAPABLE)
        if unknown_missing:
            raise ValueError(
                "missing_value can only be set for "
                f"{', '.join(MISSING_CAPABLE)}, not for {', '.join(sorted(unknown_missing))}"
            )
        missing = {name: self.missing_value.get(name, MISSING_SKIP) for name in MISSING_CAPABLE}
        for name, choice in missing.items():
            if choice not in MISSING_CHOICES:
                raise ValueError(f"missing_value {name} must be skip or lowest")
        if not isinstance(self.rank_commander_and_basics, bool):
            raise ValueError("rank_commander_and_basics must be true or false")
        object.__setattr__(self, "weights", weights)
        object.__setattr__(self, "min_coverage", coverage)
        object.__setattr__(self, "tier_cuts", cuts)
        object.__setattr__(self, "min_denominators", minimums)
        object.__setattr__(self, "missing_value", missing)

    def effective_weight(self, component: str) -> float:
        """Weight used in the index: the bracket component is off without a bracket."""
        if component == BRACKET_INCLUSION and self.bracket == BRACKET_NONE:
            return 0.0
        return self.weights[component]

    def minimum_denominator(self, component: str, universe_minimum: int) -> int:
        """The smallest denominator a share signal needs to be used (0 = no minimum)."""
        if component in _EDHREC_SHARES:
            return self.min_denominators[MIN_EDHREC]
        if component == TOURNAMENT_LISTS:
            return self.min_denominators[MIN_TOURNAMENT]
        if component == DECK_UNIVERSE:
            return universe_minimum
        return 0

    def to_dict(self) -> dict[str, object]:
        return {
            "weights": dict(self.weights),
            "bracket": self.bracket,
            "universe_profile": self.universe_profile,
            "min_coverage": self.min_coverage,
            "min_components": self.min_components,
            "tier_cuts": dict(self.tier_cuts),
            "rank_group": self.rank_group,
            "share_measure": self.share_measure,
            "min_denominators": dict(self.min_denominators),
            "missing_value": dict(self.missing_value),
            "rank_commander_and_basics": self.rank_commander_and_basics,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> StrengthSettings:
        """Settings from a plain mapping; absent keys take the default, unknown keys fail."""
        unknown = set(raw) - _SETTINGS_KEYS
        if unknown:
            raise ValueError(f"unknown settings: {', '.join(sorted(unknown))}")
        defaults = cls()
        weights = raw.get("weights", {})
        cuts = raw.get("tier_cuts", {})
        minimums = raw.get("min_denominators", {})
        missing = raw.get("missing_value", {})
        if not all(isinstance(item, Mapping) for item in (weights, cuts, minimums, missing)):
            raise ValueError(
                "weights, tier_cuts, min_denominators and missing_value must be objects"
            )
        profile = raw.get("universe_profile", defaults.universe_profile)
        if profile is not None and not isinstance(profile, str):
            raise ValueError("universe_profile must be a name or null")
        bracket = raw.get("bracket", defaults.bracket)
        if not isinstance(bracket, str):
            raise ValueError("bracket must be a text")
        minimum = raw.get("min_components", defaults.min_components)
        if isinstance(minimum, bool) or not isinstance(minimum, int):
            raise ValueError("min_components must be an integer")
        rank_group = raw.get("rank_group", defaults.rank_group)
        share_measure = raw.get("share_measure", defaults.share_measure)
        if not isinstance(rank_group, str) or not isinstance(share_measure, str):
            raise ValueError("rank_group and share_measure must be texts")
        ranked = raw.get("rank_commander_and_basics", defaults.rank_commander_and_basics)
        if not isinstance(ranked, bool):
            raise ValueError("rank_commander_and_basics must be true or false")
        return cls(
            weights={
                **DEFAULT_WEIGHTS,
                **{str(k): _number(v, f"weight {k}") for k, v in _mapping(weights).items()},
            },
            bracket=bracket,
            universe_profile=profile or None,
            min_coverage=_number(raw.get("min_coverage", defaults.min_coverage), "min_coverage"),
            min_components=minimum,
            tier_cuts={
                **DEFAULT_CUTS,
                **{str(k): _number(v, f"cut {k}") for k, v in _mapping(cuts).items()},
            },
            rank_group=rank_group,
            share_measure=share_measure,
            min_denominators={
                **DEFAULT_MIN_DENOMINATORS,
                **{
                    str(k): _count(v, f"min_denominators {k}")
                    for k, v in _mapping(minimums).items()
                },
            },
            missing_value={str(k): str(v) for k, v in _mapping(missing).items()},
            rank_commander_and_basics=ranked,
        )


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("a settings group must be an object")
    return value


def _preset(name: str, weights: dict[str, float], bracket: str) -> tuple[str, StrengthSettings]:
    return name, StrengthSettings(weights={**DEFAULT_WEIGHTS, **weights}, bracket=bracket)


PRESETS: dict[str, StrengthSettings] = dict(
    [
        ("Ausgewogen", StrengthSettings()),
        _preset(
            "Commander-nah",
            {
                COMMANDER_INCLUSION: 5.0,
                SYNERGY: 3.0,
                BRACKET_INCLUSION: 3.0,
                GLOBAL_INCLUSION: 0.0,
            },
            DEFAULT_BRACKET,
        ),
        _preset(
            "Turniernah",
            {
                BRACKET_INCLUSION: 4.0,
                TOURNAMENT_LISTS: 4.0,
                COMMANDER_INCLUSION: 2.0,
                DECK_UNIVERSE: 1.0,
                SYNERGY: 1.0,
            },
            "cedh",
        ),
    ]
)


@dataclass(frozen=True)
class Observation:
    """One published or counted value of a card for one component. ``None`` is unknown."""

    value: float | None
    numerator: int | None = None
    denominator: int | None = None


@dataclass(frozen=True)
class PoolContext:
    """What ``score_pool`` needs to know about the cards besides their observations.

    ``type_group`` and ``mana_band`` map a card key to its comparison group; ``unranked``
    maps a card key to the reason it is not ranked (``NOT_RANKED_COMMANDER`` or
    ``NOT_RANKED_BASIC_LAND``); ``filter_cards`` are the cards a card filter of the deck
    universe requires; ``universe_minimum`` is the minimum universe of the chosen profile
    (the minimum denominator of the deck-universe component)."""

    type_group: Mapping[str, str] = field(default_factory=dict)
    mana_band: Mapping[str, str] = field(default_factory=dict)
    unranked: Mapping[str, str] = field(default_factory=dict)
    filter_cards: Collection[str] = field(default_factory=frozenset)
    universe_minimum: int = 0


class ComponentResult(TypedDict):
    component: str
    label: str
    signal: str
    status: str
    reason: str
    note: str
    value: float | None
    numerator: int | None
    denominator: int | None
    wilson: float | None
    percentile: float | None
    weight: float
    min_denominator: int
    group: str | None
    group_size: int | None
    group_fallback: bool


class CardStrength(TypedDict):
    index: float | None
    coverage: float | None
    tier: str
    reason: str
    note: str
    present: int
    components: list[ComponentResult]


def wilson_lower(numerator: int, denominator: int, z: float = Z_95) -> float | None:
    """Lower bound of the Wilson score interval of numerator/denominator (None if n = 0).

    No successes give exactly 0.0. The bound grows with the numerator and with the
    denominator; for one fixed denominator it keeps the order of the raw shares."""
    if denominator <= 0 or numerator < 0 or numerator > denominator:
        return None
    if numerator == 0:
        return 0.0
    n = float(denominator)
    p = numerator / n
    spread = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n))
    return max(0.0, (p + z * z / (2.0 * n) - spread) / (1.0 + z * z / n))


def percentile_ranks(values: Mapping[str, float]) -> dict[str, float]:
    """Percentile rank 0..1 per key; ties share the mean rank; a single value is 0.5."""
    count = len(values)
    if count == 0:
        return {}
    if count == 1:
        return {key: 0.5 for key in values}
    ordered = sorted(values.values())
    first: dict[float, int] = {}
    last: dict[float, int] = {}
    for position, value in enumerate(ordered):
        first.setdefault(value, position)
        last[value] = position
    return {key: (first[value] + last[value]) / 2.0 / (count - 1) for key, value in values.items()}


def _share_values(
    component: str, observation: Observation, measure: str
) -> tuple[float | None, float | None]:
    """(value used for ranking, Wilson bound or None) of a share observation."""
    if observation.numerator is None or observation.denominator is None:
        return None, None
    if observation.denominator <= 0 or not 0 <= observation.numerator <= observation.denominator:
        return None, None
    if measure == MEASURE_RAW:
        return observation.numerator / observation.denominator, None
    bound = wilson_lower(observation.numerator, observation.denominator)
    return bound, bound


def _scored_value(
    component: str, observation: Observation, measure: str = MEASURE_WILSON
) -> tuple[float | None, float | None]:
    """(value used for ranking, Wilson bound or None)."""
    if observation.value is None and observation.numerator is None:
        return None, None
    if component in SHARE_COMPONENTS:
        return _share_values(component, observation, measure)
    if observation.value is None or not math.isfinite(observation.value):
        return None, None
    return observation.value, None


def _tier(index: float | None, settings: StrengthSettings, enough: bool) -> str:
    if index is None or not enough:
        return TIER_UNKNOWN
    for tier in ("S", "A", "B", "C"):
        if index >= settings.tier_cuts[tier]:
            return tier
    return "D"


NOT_RANKED_NOTES = {
    NOT_RANKED_COMMANDER: "nicht bewertet (Commander)",
    NOT_RANKED_BASIC_LAND: "nicht bewertet (Standardland)",
}


@dataclass
class _ComponentRanking:
    """Values and percentile ranks of one component over the ranked cards of the pool."""

    values: dict[str, float]
    wilson: dict[str, float | None]
    reasons: dict[str, str]
    pool_ranks: dict[str, float]
    group_ranks: dict[str, tuple[str, int, dict[str, float]]]
    reference_denominator: int | None
    minimum: int

    @property
    def usable(self) -> bool:
        return bool(self.values)


def _group_of(settings: StrengthSettings, context: PoolContext, card: str) -> str:
    if settings.rank_group == GROUP_TYPE:
        return context.type_group.get(card, "")
    if settings.rank_group == GROUP_MANA_BAND:
        return context.mana_band.get(card, "")
    return ""


def _rank_component(
    settings: StrengthSettings,
    context: PoolContext,
    component: str,
    observations: Mapping[str, Mapping[str, Observation]],
    skipped: Collection[str],
) -> _ComponentRanking:
    minimum = settings.minimum_denominator(component, context.universe_minimum)
    denominators = [
        item.denominator
        for card, per_card in observations.items()
        if card not in skipped and (item := per_card.get(component)) and item.denominator
    ]
    reference = max(denominators) if denominators else None
    whole_below = minimum > 0 and reference is not None and reference < minimum
    values: dict[str, float] = {}
    wilson: dict[str, float | None] = {}
    reasons: dict[str, str] = {}
    for card, per_card in observations.items():
        if card in skipped:
            continue
        observation = per_card.get(component)
        if observation is None:
            reasons[card] = BELOW_MIN_DENOMINATOR if whole_below else NOT_LISTED
            continue
        if whole_below or (
            component in SHARE_COMPONENTS
            and minimum > 0
            and observation.denominator is not None
            and observation.denominator < minimum
        ):
            reasons[card] = BELOW_MIN_DENOMINATOR
            continue
        value, bound = _scored_value(component, observation, settings.share_measure)
        if value is None:
            reasons[card] = VALUE_UNKNOWN
            continue
        values[card] = value
        wilson[card] = bound
    pool_ranks = percentile_ranks(values)
    group_ranks: dict[str, tuple[str, int, dict[str, float]]] = {}
    if settings.rank_group != GROUP_POOL:
        members: dict[str, dict[str, float]] = {}
        for card, value in values.items():
            members.setdefault(_group_of(settings, context, card), {})[card] = value
        for name, group_values in members.items():
            if name and len(group_values) >= MIN_GROUP:
                ranks = percentile_ranks(group_values)
                for card in group_values:
                    group_ranks[card] = (name, len(group_values), ranks)
    return _ComponentRanking(values, wilson, reasons, pool_ranks, group_ranks, reference, minimum)


def _component_note(
    reason: str, ranking: _ComponentRanking, observation: Observation | None
) -> str:
    if reason == BELOW_MIN_DENOMINATOR:
        seen = (
            observation.denominator
            if observation is not None and observation.denominator is not None
            else ranking.reference_denominator
        )
        return (
            f"Nenner {seen} liegt unter dem Mindest-Nenner {ranking.minimum} (Einstellung): "
            "Signal wird nicht verwendet"
        )
    if reason == NOT_LISTED:
        return "von der Quelle nicht gelistet (fehlende Beobachtung, keine Schwäche)"
    if reason == VALUE_UNKNOWN:
        return "die Quelle nennt keinen Wert (unbekannt, nicht 0)"
    if reason == MISSING_AS_LOWEST:
        return "nicht gelistet, als niedrigster Rang gezählt (Einstellung)"
    if reason == FILTER_CARD:
        return (
            "Filterkarte des Universums: steht per Definition in jedem Deck der Teilmenge, "
            "ohne Wert und nicht gerankt"
        )
    return NOT_RANKED_NOTES.get(reason, "")


def score_pool(
    settings: StrengthSettings,
    observations: Mapping[str, Mapping[str, Observation]],
    collected: Collection[str],
    *,
    context: PoolContext | None = None,
) -> dict[str, CardStrength]:
    """Index and tier for every card of ``observations`` (card key -> component -> value).

    ``collected`` names the components that have a source for this commander at all; a
    component outside it is ``NOT_COLLECTED``, one inside it without a value for a card is
    ``NO_VALUE`` (with a reason). The keys of ``observations`` are the commander's legal
    pool: percentile ranks are taken among its ranked cards only (see ``PoolContext``)."""
    ctx = context or PoolContext()
    unranked = {} if settings.rank_commander_and_basics else dict(ctx.unranked)
    filter_cards = frozenset(ctx.filter_cards)
    rankings: dict[str, _ComponentRanking] = {}
    for component in COMPONENTS:
        skipped = set(unranked) | (filter_cards if component == DECK_UNIVERSE else set())
        rankings[component] = _rank_component(settings, ctx, component, observations, skipped)
    total_weight = sum(
        settings.effective_weight(name)
        for name in COMPONENTS
        if settings.effective_weight(name) > 0
    )
    result: dict[str, CardStrength] = {}
    for card, per_card in observations.items():
        components: list[ComponentResult] = []
        present_weight = 0.0
        weighted = 0.0
        present = 0
        not_ranked = unranked.get(card)
        for component in COMPONENTS:
            if component == BRACKET_INCLUSION and settings.bracket == BRACKET_NONE:
                continue
            weight = settings.effective_weight(component)
            observation = per_card.get(component)
            ranking = rankings[component]
            status, reason = NO_VALUE, ranking.reasons.get(card, "")
            percentile: float | None = None
            group: str | None = None
            group_size: int | None = None
            group_fallback = False
            if not_ranked is not None:
                status, reason = NOT_RANKED, not_ranked
            elif component == DECK_UNIVERSE and card in filter_cards:
                status, reason = FILTER_CARD, FILTER_CARD
            elif card in ranking.values:
                status, reason = PRESENT, ""
                percentile = ranking.pool_ranks[card]
                if settings.rank_group != GROUP_POOL:
                    found = ranking.group_ranks.get(card)
                    if found is not None:
                        group, group_size = found[0], found[1]
                        percentile = found[2][card]
                    else:
                        group = _group_of(settings, ctx, card) or None
                        group_fallback = True
            elif (
                reason == NOT_LISTED
                and component in collected
                and ranking.usable
                and settings.missing_value.get(component) == MISSING_LOWEST
            ):
                status, reason, percentile = MISSING_AS_LOWEST, MISSING_AS_LOWEST, 0.0
            elif component not in collected:
                status, reason = NOT_COLLECTED, ""
            if percentile is not None and weight > 0:
                present_weight += weight
                weighted += weight * percentile
                present += 1
            note = _component_note(reason, ranking, observation) if reason else ""
            if group_fallback:
                note = _fallback_note(group, ranking, settings, ctx, card)
            components.append(
                {
                    "component": component,
                    "label": LABELS[component],
                    "signal": signal_for(component, settings.bracket),
                    "status": status,
                    "reason": GROUP_TOO_SMALL if group_fallback else reason,
                    "note": note,
                    "value": observation.value if observation else None,
                    "numerator": observation.numerator if observation else None,
                    "denominator": observation.denominator if observation else None,
                    "wilson": ranking.wilson.get(card) if status == PRESENT else None,
                    "percentile": percentile,
                    "weight": weight,
                    "min_denominator": ranking.minimum,
                    "group": group,
                    "group_size": group_size,
                    "group_fallback": group_fallback,
                }
            )
        if not_ranked is not None:
            result[card] = {
                "index": None,
                "coverage": None,
                "tier": TIER_NOT_RANKED,
                "reason": not_ranked,
                "note": NOT_RANKED_NOTES[not_ranked],
                "present": 0,
                "components": components,
            }
            continue
        coverage = present_weight / total_weight if total_weight > 0 else 0.0
        index = round(100.0 * weighted / present_weight, 1) if present_weight > 0 else None
        enough = coverage >= settings.min_coverage and present >= settings.min_components
        result[card] = {
            "index": index,
            "coverage": round(coverage, 4),
            "tier": _tier(index, settings, enough),
            "reason": "ENOUGH_DATA" if enough else "TOO_LITTLE_DATA",
            "note": "",
            "present": present,
            "components": components,
        }
    return result


def _fallback_note(
    group: str | None,
    ranking: _ComponentRanking,
    settings: StrengthSettings,
    context: PoolContext,
    card: str,
) -> str:
    size = sum(
        1
        for other in ranking.values
        if _group_of(settings, context, other) == _group_of(settings, context, card)
    )
    name = group or "ohne Gruppe"
    return (
        f"Vergleichsgruppe „{name}“ hat nur {size} Karten mit Wert (weniger als {MIN_GROUP}): "
        "Rang im ganzen Pool"
    )
