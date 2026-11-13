"""Strength index of the tier list: a configurable estimate from usage signals.

``score_pool`` is a pure function: settings and per-card observations in, index and tier
per card out. No I/O, no clock, no store. The store side lives in ``strength_view.py``.

What the index is. It is ``DERIVED_DESCRIPTIVE``: a weighted mean of percentile ranks of
usage signals (how often a card is played in decks of one commander, in a bracket, in the
deck lists the Owner chose, in tournament lists, how many combos it is part of, how
popular it is overall) plus one observed outcome correlation: the Playgroup atlas gap
between the win rate of players who cast a card and of players who never took it out of
their library. That component is an observation from other players' games, not a causal
effect and not a win rate measured in the Owner's own games. The outcome-based field of
``evidence.py`` stays ``UNRATED`` and is not touched here.

How it is computed, per commander and per signal:

1. A share-type signal carries a numerator and a denominator (decks with the card, decks
   in the sample). Its value is the lower bound of the 95 % Wilson interval of that share,
   so a small sample does not rank high by chance. Synergy and combo counts have no
   denominator and are used as published. The Playgroup gap is a difference in percentage
   points, not a share: it counts only from a minimum sample of games in which the card
   was cast, and the published gap is shrunk towards zero by that sample
   (``n / (n + k)``), so a small sample does not rank high by chance either.
2. The value becomes a percentile rank (0..1) among the cards of the commander's legal pool
   that have a value for that signal. Ties share the mean rank.
3. The index is the weighted mean of the available percentiles, times 100. A component
   without a value is left out and the remaining weights are renormalised. A card that a
   source does not list is a missing observation, never a weak card: it lowers the
   coverage, not the percentile.
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
    "wird) plus einer beobachteten Korrelation aus Playgroup-Spieldaten: um wie viele "
    "Prozentpunkte Spieler häufiger gewannen, wenn sie eine Karte gespielt haben, als wenn "
    "sie in der Bibliothek blieb (kleine Stichproben werden zur Null gezogen). Das ist eine "
    "Beobachtung, keine Kausalität und keine gemessene Siegrate der eigenen Partien. "
    "Fehlende Beobachtungen senken die Abdeckung, nie die Karte. Favoriten, Ausschlüsse "
    "und Notizen fließen nicht ein."
)

PRESENT = "PRESENT"
NO_VALUE = "NO_VALUE"
NOT_COLLECTED = "NOT_COLLECTED"

TIER_UNKNOWN = "U"
TIERS = ("S", "A", "B", "C", "D")
BRACKETS = ("core", "upgraded", "optimized", "cedh")
BRACKET_NONE = "none"
Z_95 = 1.959963984540054

COMMANDER_INCLUSION = "commander_inclusion"
BRACKET_INCLUSION = "bracket_inclusion"
DECK_UNIVERSE = "deck_universe"
SYNERGY = "synergy"
TOURNAMENT_LISTS = "tournament_lists"
GLOBAL_INCLUSION = "global_inclusion"
COMBOS = "combos"
PLAYGROUP_OBSERVED = "playgroup_observed"
SIMULATION = "simulation"

COMPONENTS = (
    COMMANDER_INCLUSION,
    BRACKET_INCLUSION,
    DECK_UNIVERSE,
    SYNERGY,
    TOURNAMENT_LISTS,
    GLOBAL_INCLUSION,
    COMBOS,
    PLAYGROUP_OBSERVED,
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
    PLAYGROUP_OBSERVED: "Beobachtete Sieg-Korrelation (Playgroup)",
    SIMULATION: "Simulation",
}
# Components whose value is a share with a numerator and a denominator (Wilson bound).
SHARE_COMPONENTS = frozenset(
    {COMMANDER_INCLUSION, BRACKET_INCLUSION, DECK_UNIVERSE, TOURNAMENT_LISTS, GLOBAL_INCLUSION}
)
# The Playgroup component is an observed difference (percentage points), not a share.
# It counts only from OBSERVED_MIN_SAMPLE games in which the card was cast, and its
# published gap is shrunk towards zero by OBSERVED_SHRINKAGE (gap * n / (n + k)): the
# same minimum-plus-shrinkage rule the deckbuilder applies to observed win signals, so
# a gap that rests on few games cannot rank high by chance. The signal import applies
# the same minimum before a row is stored at all (signals.ATLAS_MIN_SAMPLE).
OBSERVED_MIN_SAMPLE = 25
OBSERVED_SHRINKAGE = 25

DEFAULT_WEIGHTS: dict[str, float] = {
    COMMANDER_INCLUSION: 3.0,
    BRACKET_INCLUSION: 2.0,
    DECK_UNIVERSE: 2.0,
    SYNERGY: 1.0,
    TOURNAMENT_LISTS: 1.0,
    GLOBAL_INCLUSION: 1.0,
    COMBOS: 1.0,
    PLAYGROUP_OBSERVED: 1.0,
    SIMULATION: 0.0,
}
DEFAULT_CUTS: dict[str, float] = {"S": 90.0, "A": 75.0, "B": 55.0, "C": 35.0}
DEFAULT_BRACKET = "upgraded"
MAX_WEIGHT = 100.0

_SETTINGS_KEYS = frozenset(
    {"weights", "bracket", "universe_profile", "min_coverage", "min_components", "tier_cuts"}
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
        PLAYGROUP_OBSERVED: "playgroup_observed_winrate_gap",
        SIMULATION: "",
    }[component]


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


@dataclass(frozen=True)
class StrengthSettings:
    """The Owner's settings of the index. Validated on construction."""

    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    bracket: str = DEFAULT_BRACKET
    universe_profile: str | None = None
    min_coverage: float = 0.4
    min_components: int = 2
    tier_cuts: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_CUTS))

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
        object.__setattr__(self, "weights", weights)
        object.__setattr__(self, "min_coverage", coverage)
        object.__setattr__(self, "tier_cuts", cuts)

    def effective_weight(self, component: str) -> float:
        """Weight used in the index: the bracket component is off without a bracket."""
        if component == BRACKET_INCLUSION and self.bracket == BRACKET_NONE:
            return 0.0
        return self.weights[component]

    def to_dict(self) -> dict[str, object]:
        return {
            "weights": dict(self.weights),
            "bracket": self.bracket,
            "universe_profile": self.universe_profile,
            "min_coverage": self.min_coverage,
            "min_components": self.min_components,
            "tier_cuts": dict(self.tier_cuts),
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
        if not isinstance(weights, Mapping) or not isinstance(cuts, Mapping):
            raise ValueError("weights and tier_cuts must be objects")
        profile = raw.get("universe_profile", defaults.universe_profile)
        if profile is not None and not isinstance(profile, str):
            raise ValueError("universe_profile must be a name or null")
        bracket = raw.get("bracket", defaults.bracket)
        if not isinstance(bracket, str):
            raise ValueError("bracket must be a text")
        minimum = raw.get("min_components", defaults.min_components)
        if isinstance(minimum, bool) or not isinstance(minimum, int):
            raise ValueError("min_components must be an integer")
        return cls(
            weights={
                **DEFAULT_WEIGHTS,
                **{str(k): _number(v, f"weight {k}") for k, v in weights.items()},
            },
            bracket=bracket,
            universe_profile=profile or None,
            min_coverage=_number(raw.get("min_coverage", defaults.min_coverage), "min_coverage"),
            min_components=minimum,
            tier_cuts={
                **DEFAULT_CUTS,
                **{str(k): _number(v, f"cut {k}") for k, v in cuts.items()},
            },
        )


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


class ComponentResult(TypedDict):
    component: str
    label: str
    signal: str
    status: str
    value: float | None
    numerator: int | None
    denominator: int | None
    wilson: float | None
    percentile: float | None
    weight: float


class CardStrength(TypedDict):
    index: float | None
    coverage: float
    tier: str
    reason: str
    present: int
    components: list[ComponentResult]


def wilson_lower(numerator: int, denominator: int, z: float = Z_95) -> float | None:
    """Lower bound of the Wilson score interval of numerator/denominator (None if n = 0)."""
    if denominator <= 0 or numerator < 0 or numerator > denominator:
        return None
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


def _scored_value(component: str, observation: Observation) -> tuple[float | None, float | None]:
    """(value used for ranking, Wilson bound or None)."""
    if observation.value is None and observation.numerator is None:
        return None, None
    if component == PLAYGROUP_OBSERVED:
        # Observed gap in percentage points; the denominator is the sample (games in
        # which the card was cast). Below the minimum the observation does not count;
        # above it the gap is shrunk towards zero by the sample size.
        if observation.value is None or not math.isfinite(observation.value):
            return None, None
        sample = observation.denominator
        if sample is None or sample < OBSERVED_MIN_SAMPLE:
            return None, None
        return observation.value * sample / (sample + OBSERVED_SHRINKAGE), None
    if component in SHARE_COMPONENTS:
        if observation.numerator is None or observation.denominator is None:
            return None, None
        bound = wilson_lower(observation.numerator, observation.denominator)
        return bound, bound
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


def score_pool(
    settings: StrengthSettings,
    observations: Mapping[str, Mapping[str, Observation]],
    collected: Collection[str],
) -> dict[str, CardStrength]:
    """Index and tier for every card of ``observations`` (card key -> component -> value).

    ``collected`` names the components that have a source for this commander at all; a
    component outside it is ``NOT_COLLECTED``, one inside it without a value for a card is
    ``NO_VALUE``. The keys of ``observations`` are the commander's legal pool: percentile
    ranks are taken among them only."""
    scored: dict[str, dict[str, tuple[float, float | None]]] = {}
    ranks: dict[str, dict[str, float]] = {}
    for component in COMPONENTS:
        values: dict[str, float] = {}
        for card, per_card in observations.items():
            observation = per_card.get(component)
            if observation is None:
                continue
            value, bound = _scored_value(component, observation)
            if value is not None:
                values[card] = value
                scored.setdefault(card, {})[component] = (value, bound)
        ranks[component] = percentile_ranks(values)
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
        for component in COMPONENTS:
            if component == BRACKET_INCLUSION and settings.bracket == BRACKET_NONE:
                continue
            weight = settings.effective_weight(component)
            observation = per_card.get(component)
            hit = scored.get(card, {}).get(component)
            percentile = ranks[component].get(card) if hit is not None else None
            if hit is not None and percentile is not None:
                status = PRESENT
                if weight > 0:
                    present_weight += weight
                    weighted += weight * percentile
                    present += 1
            else:
                status = NO_VALUE if component in collected else NOT_COLLECTED
            components.append(
                {
                    "component": component,
                    "label": LABELS[component],
                    "signal": signal_for(component, settings.bracket),
                    "status": status,
                    "value": observation.value if observation else None,
                    "numerator": observation.numerator if observation else None,
                    "denominator": observation.denominator if observation else None,
                    "wilson": hit[1] if hit else None,
                    "percentile": percentile,
                    "weight": weight,
                }
            )
        coverage = present_weight / total_weight if total_weight > 0 else 0.0
        index = round(100.0 * weighted / present_weight, 1) if present_weight > 0 else None
        enough = coverage >= settings.min_coverage and present >= settings.min_components
        reason = "ENOUGH_DATA" if enough else "TOO_LITTLE_DATA"
        result[card] = {
            "index": index,
            "coverage": round(coverage, 4),
            "tier": _tier(index, settings, enough),
            "reason": reason,
            "present": present,
            "components": components,
        }
    return result
