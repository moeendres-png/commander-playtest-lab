"""Strength index of the tier list: a configurable estimate from usage signals.

``score_pool`` is a pure function: settings and per-card observations in, index and tier
per card out. No I/O, no clock, no store. The store side lives in ``strength_view.py``.

Tierliste v3 (#1364): the index is purely empirical. The rubric has weight 0 (subjective),
the EDHREC commander and bracket inclusion weights are 0 while a counted local corpus exists
(``apply_corpus_rule``, rule E2.a), shares with a denominator below ``EB_MAX_DENOMINATOR`` are
shrunk by empirical Bayes (``beta_binomial_prior``), a counted 0 of N is ``ZERO_COUNT``
(tier D, setting ``zero_count_tier``) and the share scale is logarithmic with
``LOG_SHARE_K``. The text below keeps the older description of the formula; the weights,
scale, cuts and the rules above are what applies, see docs/STUDIO_DECKBUILDER.md.

What the index is. It is ``DERIVED_DESCRIPTIVE``: a weighted mean of percentile ranks of
usage signals (how often a card is played in decks of one commander, in a bracket, in the
deck lists the Owner chose, in tournament lists, the quality of the combos it is part
of, how popular it is overall) plus one observed outcome correlation: the Playgroup atlas gap
between the win rate of players who cast a card and of players who never took it out of
their library. That component is an observation from other players' games, not a causal
effect and not a win rate measured in the Owner's own games. The outcome-based field of
``evidence.py`` stays ``UNRATED`` and is not touched here.

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
   have no denominator and are used as published. The Playgroup gap is a difference in
   percentage points, not a share: it counts only from a minimum sample of games in
   which the card was cast, and the published gap is shrunk towards zero by that sample
   (``n / (n + k)``), so a small sample does not rank high by chance either.
   The ``rubric`` component (#1358, Chulane only) is neither a share nor a rank: its value
   ``(H_mean - 1) / 9`` of a frozen rating file is used directly as the 0..1 score, so the
   magnitude of the rating is kept. It is commander specific and, for a commander without
   the file, a missing source (``NOT_COLLECTED``) that does not lower any coverage.
2. The value becomes a percentile rank (0..1) among the cards of the commander's legal pool
   that have a value for that signal and are ranked at all. The comparison group is the
   whole pool (default), the cards of the same main type or of the same mana value band
   (setting); a group with fewer than ``MIN_GROUP`` valued cards falls back to the pool
   and the component row says so. With ``separate_lands`` (default, #1353 part A) lands are
   scaled against lands and spells against spells, so neither group sets the scale of the
   other (a group below ``MIN_GROUP`` keeps the joint scale, said in the row). Ties share the mean rank. The commander card and basic
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
   in that component (status ``MISSING_AS_LOWEST``, named as such in the row). That is the
   recommended value for the commander and the bracket inclusion since #1350 (EDHREC lists every
   card above its threshold, so "not listed" means "below it"; the 0 is at or below the smallest
   listed card under both share scales); the deck universe stays "skip". Note that
   with ``min_coverage`` 0 an unlisted card (only its other signals count) can outrank a
   card that a source lists at 1 of 755 decks: the recommended minimum coverage exists for
   that reason.
4. ``coverage`` is the weight of the present components over the weight of all components
   with a positive weight. Tier ``U`` ("zu wenig Daten") when the coverage is below
   ``min_coverage`` or fewer than ``min_components`` components with a weight are present;
   otherwise the tier follows the index cuts.

Simulation results are not an input by default: the ``simulation`` component exists and the
Owner can weight it, but its weight is 0 in the defaults and in every preset (Owner decision
2026-11-12), and with weight 0 it changes neither the index nor the tier nor the coverage.
The Owner's marks (favorite, excluded, note) are never an input.
"""

from __future__ import annotations

import math
import random
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field, replace
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
    "Für Chulane zählt außerdem eine eingefrorene Raster-Bewertung (subjektiv, nach "
    "festem Leitfaden von drei unabhängigen Bewertern). "
    "Fehlende Beobachtungen senken die Abdeckung, nie die Karte. Favoriten, Ausschlüsse "
    "und Notizen fließen nicht ein."
)

PRESENT = "PRESENT"
NO_VALUE = "NO_VALUE"
NOT_COLLECTED = "NOT_COLLECTED"
FILTER_CARD = "FILTER_CARD"
NOT_RANKED = "NOT_RANKED"
MISSING_AS_LOWEST = "MISSING_AS_LOWEST"
# A counted zero: the card is in none of the decks of a completely counted universe. It is a
# finding (0 of N decks), ranked like any other count, and labelled as counted.
ZERO_COUNT = "ZERO_COUNT"

# Reasons of a component row (empty when the row needs none).
BELOW_MIN_DENOMINATOR = "BELOW_MIN_DENOMINATOR"
NOT_LISTED = "NOT_LISTED"
VALUE_UNKNOWN = "VALUE_UNKNOWN"
GROUP_TOO_SMALL = "GROUP_TOO_SMALL"
NOT_RANKED_COMMANDER = "NOT_RANKED_COMMANDER"
NOT_RANKED_BASIC_LAND = "NOT_RANKED_BASIC_LAND"
NO_COMMANDER_SIGNAL = "NO_COMMANDER_SIGNAL"
NOT_RANKED_OTHER_COMMANDER = "NOT_RANKED_OTHER_COMMANDER"
NEGATIVE_NEUTRAL = "NEGATIVE_NEUTRAL"
# Tier ``U`` reason of the setting ``zero_count_tier = "U"`` (E4.a): the only evidence about this
# commander is counted zeros (0 of N), nothing positive.
ZERO_COUNT_ONLY = "ZERO_COUNT_ONLY"

TIER_UNKNOWN = "U"
TIER_NOT_RANKED = "N"
TIERS = ("S", "A", "B", "C", "D")
BRACKETS = ("core", "upgraded", "optimized", "cedh")
BRACKET_NONE = "none"
Z_95 = 1.959963984540054
MIN_GROUP = 5

TYPE_LAND = "Land"  # the type group of a land card (``PoolContext.type_group``)
GROUP_LANDS = "Länder"
GROUP_SPELLS = "Zauber"  # every card that is not a land
GROUP_POOL = "pool"
GROUP_TYPE = "type"
GROUP_MANA_BAND = "mana_band"
GROUP_FUNCTION = "function"
RANK_GROUPS = (GROUP_POOL, GROUP_TYPE, GROUP_MANA_BAND, GROUP_FUNCTION)
MEASURE_WILSON = "wilson"
MEASURE_RAW = "raw"
SHARE_MEASURES = (MEASURE_WILSON, MEASURE_RAW)
SCALE_RANK = "rank"
SCALE_SHARE = "share"
SCALE_LOG = "log"
SHARE_SCALES = (SCALE_LOG, SCALE_SHARE, SCALE_RANK)
DEFAULT_SHARE_SCALE = SCALE_LOG
# Curvature of the default share scale ``ln(1 + k v) / ln(1 + k v_max)`` (Owner decision E5.a,
# #1364). With k = 150 and a most-played card of 60 %, a 0.1 % card scores 0.05, 1 % scores 0.20,
# 10 % scores 0.61 and 30 % scores 0.85: rare counts stay visibly apart from zero, the very top is
# flattened. The value is a documented constant, not a tuned parameter; k = 100 and 200 are
# reported by the ranking check as a sensitivity test only.
LOG_SHARE_K = 150.0
ZERO_TIER_D = "D"
ZERO_TIER_U = "U"
ZERO_COUNT_TIERS = (ZERO_TIER_D, ZERO_TIER_U)
DEFAULT_ZERO_COUNT_TIER = ZERO_TIER_D
MISSING_SKIP = "skip"
MISSING_LOWEST = "lowest"
MISSING_CHOICES = (MISSING_SKIP, MISSING_LOWEST)
MIN_EDHREC = "edhrec"
MIN_TOURNAMENT = "tournament"
MIN_CONVERSION = "conversion"
MIN_PLAYGROUP = "playgroup"
MIN_DENOMINATOR_KEYS = (MIN_EDHREC, MIN_TOURNAMENT, MIN_CONVERSION, MIN_PLAYGROUP)
MAX_MIN_DENOMINATOR = 100000

COMBO_COMMANDER = "commander"
COMBO_SPELLBOOK = "spellbook"
COMBO_SOURCES = (COMBO_COMMANDER, COMBO_SPELLBOOK)
DEFAULT_COMBO_SOURCE = COMBO_COMMANDER

# Where the deck-universe component takes its counts from (setting ``universe_source``): "auto"
# (recommended) chooses (see ``universe_choice``), "profile" is the stored profile of
# ``universe_profile`` and no universe without one,
# "counted:<source>:<bracket>" one imported counted deck-list universe, "none" switches the
# component off.
UNIVERSE_AUTO = "auto"
UNIVERSE_PROFILE = "profile"
UNIVERSE_NONE = "none"
UNIVERSE_COUNTED = "counted"
DEFAULT_UNIVERSE_SOURCE = UNIVERSE_AUTO
# Mana value bands of the comparison group "gleiches Manawert-Band"; lands are their own band.
MANA_BANDS = ("0-1", "2", "3", "4", "5+")
BAND_LAND = "Land"
BAND_UNKNOWN = "unbekannt"

COMMANDER_INCLUSION = "commander_inclusion"
BRACKET_INCLUSION = "bracket_inclusion"
DECK_UNIVERSE = "deck_universe"
# Corpus components of the counted local deck corpus of ONE commander (#1364, E3.a). They are
# ``DERIVED_DESCRIPTIVE``: counts and ratios of counts, shown with numerator and denominator.
CORPUS_TUNED = "corpus_tuned"
CORPUS_LOG_LIFT = "corpus_log_lift"
CORPUS_BRACKET_SLOPE = "corpus_bracket_slope"
SYNERGY = "synergy"
TOURNAMENT = "tournament"
TOURNAMENT_LISTS = "tournament_lists"
TOURNAMENT_CONVERSION = "tournament_conversion"
EDHREC_THEME_REACH = "edhrec_theme_reach"
GLOBAL_INCLUSION = "global_inclusion"
COMBOS = "combos"
PLAYGROUP_OBSERVED = "playgroup_observed"
RUBRIC = "rubric"
SIMULATION = "simulation"

COMPONENTS = (
    COMMANDER_INCLUSION,
    BRACKET_INCLUSION,
    DECK_UNIVERSE,
    CORPUS_TUNED,
    CORPUS_LOG_LIFT,
    CORPUS_BRACKET_SLOPE,
    SYNERGY,
    TOURNAMENT,
    TOURNAMENT_LISTS,
    TOURNAMENT_CONVERSION,
    EDHREC_THEME_REACH,
    GLOBAL_INCLUSION,
    COMBOS,
    PLAYGROUP_OBSERVED,
    RUBRIC,
    SIMULATION,
)
LABELS: dict[str, str] = {
    COMMANDER_INCLUSION: "Aufnahme beim Commander (EDHREC)",
    BRACKET_INCLUSION: "Aufnahme im Bracket (EDHREC)",
    DECK_UNIVERSE: "Decklisten-Universum (gezählt)",
    CORPUS_TUNED: "Korpus getunt (Bracket 4+5, gezählt)",
    CORPUS_LOG_LIFT: "Korpus-Lift gegenüber allen Decks (gedämpft)",
    CORPUS_BRACKET_SLOPE: "Korpus-Bracket-Gefälle (4+5 gegen 2, gedämpft)",
    SYNERGY: "Synergie (EDHREC)",
    TOURNAMENT: "Turnier (EDHTop16 und Korpus Bracket 5)",
    TOURNAMENT_LISTS: "Turnierlisten des Commanders (TopDeck)",
    TOURNAMENT_CONVERSION: "Turnier-Conversion (TopDeck)",
    EDHREC_THEME_REACH: "Reichweite in EDHREC-Themen (Maximum)",
    GLOBAL_INCLUSION: "Aufnahme überhaupt (EDHREC)",
    COMBOS: "Kombos",
    PLAYGROUP_OBSERVED: "Beobachtete Sieg-Korrelation (Playgroup)",
    RUBRIC: "Raster-Bewertung (subjektiv, Gewicht 0, kein objektives Signal)",
    SIMULATION: "Simulation",
}
# Where a component's value comes from (the ``data_class`` of its row). The rubric is a
# subjective rating, never an objective signal (Owner decision E1.a): the label says so.
SUBJECTIVE_RATING = "SUBJECTIVE_RATING"
COMPONENT_DATA_CLASS: dict[str, str] = {
    COMMANDER_INCLUSION: "NORMALIZED_SOURCE",
    BRACKET_INCLUSION: "NORMALIZED_SOURCE",
    DECK_UNIVERSE: DATA_CLASS,
    CORPUS_TUNED: DATA_CLASS,
    CORPUS_LOG_LIFT: DATA_CLASS,
    CORPUS_BRACKET_SLOPE: DATA_CLASS,
    SYNERGY: "NORMALIZED_SOURCE",
    TOURNAMENT: DATA_CLASS,
    TOURNAMENT_LISTS: DATA_CLASS,
    TOURNAMENT_CONVERSION: "NORMALIZED_SOURCE",
    EDHREC_THEME_REACH: DATA_CLASS,
    GLOBAL_INCLUSION: "NORMALIZED_SOURCE",
    COMBOS: "NORMALIZED_SOURCE",
    PLAYGROUP_OBSERVED: "OBSERVED_GAME",
    RUBRIC: SUBJECTIVE_RATING,
    SIMULATION: "SIMULATED_RESULT",
}
# Components the tier list collects no data for at all, for now (Owner decision B11: simulation
# results are not collected for it). Their weight stays adjustable, but while no card has a value
# it adds nothing and must not lower any card's coverage.
UNCOLLECTED_BY_DESIGN = frozenset({SIMULATION})
# Components whose value is a share with a numerator and a denominator (Wilson bound).
SHARE_COMPONENTS = frozenset(
    {
        COMMANDER_INCLUSION,
        BRACKET_INCLUSION,
        DECK_UNIVERSE,
        CORPUS_TUNED,
        TOURNAMENT,
        TOURNAMENT_LISTS,
        TOURNAMENT_CONVERSION,
        EDHREC_THEME_REACH,
        GLOBAL_INCLUSION,
    }
)
# Share components whose numerator 0 is a COUNT of a completely counted corpus (0 of N decks),
# status ``ZERO_COUNT``: a finding that counts fully, unlike a card a source does not list.
ZERO_COUNT_COMPONENTS = frozenset({DECK_UNIVERSE, CORPUS_TUNED, TOURNAMENT})
# The Playgroup component is an observed difference (percentage points), not a share.
# It counts only from OBSERVED_MIN_SAMPLE games in which the card was cast, and its
# published gap is shrunk towards zero by OBSERVED_SHRINKAGE (gap * n / (n + k)): a
# gap that rests on few games is strongly damped towards zero (200 games = half the
# published gap), and in the index the minimum denominator (default 200) drops thin
# samples altogether. The signal import applies OBSERVED_MIN_SAMPLE before a row is stored.
OBSERVED_MIN_SAMPLE = 25
OBSERVED_SHRINKAGE = 200
# Components whose value is already a 0..1 score and is used as it is (no percentile rank, no
# share scale): the magnitude is kept. The rubric value is ``(H_mean - 1) / 9``; the corpus lift
# and slope are ``(clip(damped log10 ratio, +-2) + 2) / 4``.
DIRECT_COMPONENTS = frozenset({RUBRIC, CORPUS_LOG_LIFT, CORPUS_BRACKET_SLOPE})
# Signed log ratios mapped to 0..1 with 0.5 = neutral (ratio 1). In the weighted mean a value
# below neutral would still raise a card whose other scores are near 0, so the index score is
# ``max(0, 2 v - 1)``: only an above-neutral lift or slope adds, neutral or negative is 0. The
# raw signed value stays in the row (``value``, and the note).
ABOVE_NEUTRAL_COMPONENTS = frozenset({CORPUS_LOG_LIFT, CORPUS_BRACKET_SLOPE})


def above_neutral_score(value: float) -> float:
    """The index score of a signed log ratio held in 0..1 (0.5 = neutral): ``max(0, 2v - 1)``."""
    return max(0.0, 2.0 * value - 1.0)


# Components that exist for some commanders only. For a commander without a source they are
# ``NOT_COLLECTED`` (a missing source, never 0) and, unlike a source that was merely not
# imported yet, they do not lower the coverage: the source cannot exist for that commander.
COMMANDER_ONLY_SOURCES = frozenset(
    {
        RUBRIC,
        CORPUS_TUNED,
        CORPUS_LOG_LIFT,
        CORPUS_BRACKET_SLOPE,
        TOURNAMENT,
        EDHREC_THEME_REACH,
    }
)
# Sources that list the commander's cards fairly completely: only for these may an unlisted
# card be counted as the lowest rank (Owner decision B5 keeps "absent" a missing observation).
MISSING_CAPABLE = (COMMANDER_INCLUSION, BRACKET_INCLUSION, DECK_UNIVERSE)
# Components that say something about THIS commander (global inclusion, spellbook combos, the
# Playgroup observation and simulation are independent of the commander): the rule
# "require_commander_signal" asks for at least one of them (or commander-sourced combos)
# with a ranked value before a card gets a tier.
COMMANDER_SPECIFIC = (
    COMMANDER_INCLUSION,
    BRACKET_INCLUSION,
    DECK_UNIVERSE,
    CORPUS_TUNED,
    CORPUS_LOG_LIFT,
    CORPUS_BRACKET_SLOPE,
    SYNERGY,
    TOURNAMENT,
    TOURNAMENT_LISTS,
    EDHREC_THEME_REACH,
    RUBRIC,
)


def is_commander_specific(component: str, combo_source: str = COMBO_COMMANDER) -> bool:
    """Whether ``component`` provides a signal bound to the chosen commander."""
    return component in COMMANDER_SPECIFIC or (
        component == COMBOS and combo_source == COMBO_COMMANDER
    )


# The rubric rates every card with a holistic value H from 1 to 10; the component value is the
# fraction of that range, so 1 is 0.0 and 10 is 1.0 (a magnitude, not a share and not a rank).
RUBRIC_H_MIN = 1.0
RUBRIC_H_MAX = 10.0


def rubric_value(h_mean: float) -> float | None:
    """The rubric component value ``(H - 1) / 9`` of a mean rating, ``None`` when it lies
    outside 1..10 or is not a finite number (unknown, never clipped to a bound)."""
    if not math.isfinite(h_mean) or not RUBRIC_H_MIN <= h_mean <= RUBRIC_H_MAX:
        return None
    return (h_mean - RUBRIC_H_MIN) / (RUBRIC_H_MAX - RUBRIC_H_MIN)


_EDHREC_SHARES = frozenset({COMMANDER_INCLUSION, BRACKET_INCLUSION, GLOBAL_INCLUSION})

# What an unlisted card counts as, per source (recommended values). Since the Owner decision E4.b
# (#1364) nothing is filled with 0: a card a source does not list is a missing observation
# (``NOT_LISTED``), never a weak card and never a counted zero. A COUNTED zero (0 of N decks of a
# completely counted corpus, status ``ZERO_COUNT``) is a finding and counts fully. The Owner can
# still switch EDHREC "lowest" on for the commander and the bracket inclusion (EDHREC lists every
# card above its threshold, so "not listed" there means "below it").
DEFAULT_MISSING_VALUE: dict[str, str] = {
    COMMANDER_INCLUSION: MISSING_SKIP,
    BRACKET_INCLUSION: MISSING_SKIP,
    DECK_UNIVERSE: MISSING_SKIP,
}

# The recommended values are the defaults of ``StrengthSettings`` and of these constants: one
# place in Python. ``strength_view.presets`` serves them, the page never hard-codes them.
#
# Owner decisions of #1364 (Tierliste v3, E1.a to E5.a): the index is purely empirical.
# - E1.a: the rubric is subjective, its weight is 0 here and in every preset (the component, its
#   importer and its column stay).
# - E2.a: while a counted local corpus of at least ``min_universe`` decks exists for the commander,
#   the weights of ``commander_inclusion`` and ``bracket_inclusion`` below are NOT used (rule
#   ``CORPUS_ZERO``, ``apply_corpus_rule``); without such a corpus they are the fallback weights
#   (3 and 2, as before) and the EDHREC inclusion carries the index.
# - E3.a: corpus_tuned, corpus_log_lift, corpus_bracket_slope, tournament and edhrec_theme_reach
#   come from the counted corpus and the sources around it. The TopDeck components stay as
#   columns with weight 0: their data is empty (7 lists, no conversion).
DEFAULT_WEIGHTS: dict[str, float] = {
    COMMANDER_INCLUSION: 3.0,
    BRACKET_INCLUSION: 2.0,
    DECK_UNIVERSE: 4.0,
    CORPUS_TUNED: 1.5,
    CORPUS_LOG_LIFT: 1.0,
    CORPUS_BRACKET_SLOPE: 1.0,
    SYNERGY: 0.0,
    TOURNAMENT: 0.5,
    TOURNAMENT_LISTS: 0.0,
    TOURNAMENT_CONVERSION: 0.0,
    EDHREC_THEME_REACH: 0.5,
    GLOBAL_INCLUSION: 1.0,
    COMBOS: 0.5,
    PLAYGROUP_OBSERVED: 0.0,
    RUBRIC: 0.0,
    SIMULATION: 0.0,
}
# Tier cuts of the purely empirical index, derived once (#1366) from the default ``Ausgewogen``
# index with a rule fixed in advance: C is the smallest whole number above the highest index of
# any card whose only commander evidence is a counted 0 (those cards stay D); A is the smallest
# whole number that keeps every card with less than 5 % in the counted lists out of S and A; S is
# the whole number nearest to 3 % of the ranked non-lands in S, never below A + 1; B is the
# rounded midpoint of A and C. Result 54 / 35 / 20 / 5 (Stand #1371: 72 / 50 / 28 / 14), the same
# for lands. Not tuned to any card.
DEFAULT_CUTS: dict[str, float] = {"S": 54.0, "A": 35.0, "B": 20.0, "C": 5.0}
DEFAULT_MIN_DENOMINATORS: dict[str, int] = {
    MIN_EDHREC: 30,
    MIN_TOURNAMENT: 20,
    MIN_CONVERSION: 20,
    MIN_PLAYGROUP: 200,
}
DEFAULT_BRACKET = "upgraded"
# #1365: "grenzwertig" mark. A card whose index lies closer than this many index points to a tier
# cut is marked (0 switches the mark off). Recommended 2.
DEFAULT_BORDERLINE_DISTANCE = 2.0
MAX_BORDERLINE_DISTANCE = 50.0
# #1365, redefined by D4: confidence of a card = coverage x reliability of its counts; the
# reliability of one share with count k (numerator) is k / (k + CONFIDENCE_K), a counted zero uses
# its denominator. The level names split the 0..1 range.
CONFIDENCE_K = 30
# D4: a counted zero (0 of N decks) is real evidence from N = 30 decks on; below it the zero is
# listed as thin (``zero_count_thin``). A setting of the Owner decision, not tuned to a card.
CONFIDENCE_ZERO_MIN_DENOMINATOR = 30
CONFIDENCE_HIGH = 0.6
CONFIDENCE_MEDIUM = 0.35
# Lands are ranked against lands and spells against spells (#1353 part A): share scaling
# (v / v_max) and percentile ranks are computed inside the two groups, so a land with the most
# decks does not set the scale of the spells and the other way round.
DEFAULT_SEPARATE_LANDS = True
DEFAULT_MIN_COVERAGE = 0.25
DEFAULT_REQUIRE_COMMANDER_SIGNAL = True
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
        "share_scale",
        "min_denominators",
        "missing_value",
        "rank_commander_and_basics",
        "rank_other_commanders",
        "universe_source",
        "require_commander_signal",
        "combo_source",
        "separate_lands",
        "zero_count_tier",
        "edhrec_with_corpus",
        "borderline_distance",
    }
)


# Q1-b (#1665, Charta v2 E15 Q1): settings keys a later version RETIRED. Reading settings
# (``from_dict``, ``from_stored``: stored profiles, remembered browser settings, API bodies)
# accepts and drops exactly these keys, so a profile saved before a key fell stays valid; every
# OTHER unknown key still raises, so a typo stays visible. Grouped by where the key sits:
# ``weights`` (component names), ``min_denominators`` and ``top_level`` (settings keys). A key
# moves here in the same change that removes it from the live keys (never both at once).
RETIRED_WEIGHTS = "weights"
RETIRED_MIN_DENOMINATORS = "min_denominators"
RETIRED_TOP_LEVEL = "top_level"
RETIRED_SETTING_KEYS: Mapping[str, frozenset[str]] = {
    RETIRED_WEIGHTS: frozenset(),
    RETIRED_MIN_DENOMINATORS: frozenset(),
    # Q1-b2 (#1677): the rating layers (``layer_weights``) and their pod size fell.
    RETIRED_TOP_LEVEL: frozenset({"layer_weights", "pod_size"}),
}
# The value a retired top-level key had by default when it fell: a stored profile that held a
# different value gets one calm notice that the value no longer acts (``retired_deviations``).
# ``layer_weights``: every layer weight 0; ``pod_size``: 4 players.
RETIRED_TOP_LEVEL_DEFAULTS: Mapping[str, object] = {"layer_weights": 0.0, "pod_size": 4}


def _retired(group: str) -> frozenset[str]:
    """The retired keys of one group, read at call time."""
    return RETIRED_SETTING_KEYS.get(group, frozenset())


def retired_deviations(raw: Mapping[str, object]) -> list[str]:
    """The retired top-level keys of ``raw`` (a stored settings spec) whose value differed from
    the default it had when the key fell, sorted. ``layer_weights`` differs when any weight is
    not 0; an unreadable value counts as differing (it was not the default)."""
    found: list[str] = []
    for key in sorted(_retired(RETIRED_TOP_LEVEL) & set(RETIRED_TOP_LEVEL_DEFAULTS)):
        if key not in raw:
            continue
        value, default = raw[key], RETIRED_TOP_LEVEL_DEFAULTS[key]
        values = list(value.values()) if isinstance(value, Mapping) else [value]
        not_a_map = key == "layer_weights" and not isinstance(value, Mapping)
        if not_a_map or any(isinstance(item, bool) or item != default for item in values):
            found.append(key)
    return found


def _without_retired(values: Mapping[str, object], group: str) -> dict[str, object]:
    """``values`` without the keys of ``group`` that a later version retired."""
    retired = _retired(group)
    return {key: value for key, value in values.items() if str(key) not in retired}


# The combos component can read either the commander's EDHREC combo deck counts (default,
# ``commander``) or the Spellbook quality mixture across the three commander-independent
# signals below (``spellbook``). In Spellbook mode, the first part is the primary signal and
# decides which cards the source lists; the other parts refine the rank of listed cards.
COMBO_PART_VARIANTS = "spellbook_variants"
COMBO_PART_TWO_CARD = "spellbook_two_card_variants"
COMBO_PART_PARTNERS = "spellbook_partners_in_collection"
COMBO_PARTS = (COMBO_PART_VARIANTS, COMBO_PART_TWO_CARD, COMBO_PART_PARTNERS)
# The shell parts (#1366): distinct spellbook combos instead of raw variants.
# When the store holds them, they replace the variant parts in the mixture and
# the shell count is the primary part; the variant count stays a stored signal
# for display only.
COMBO_PART_SHELLS = "spellbook_shells"
COMBO_PART_TWO_CARD_SHELLS = "spellbook_two_card_shells"
COMBO_PART_COMMANDER_SHELLS = "spellbook_commander_shells"
COMBO_SHELL_PARTS = (COMBO_PART_SHELLS, COMBO_PART_TWO_CARD_SHELLS, COMBO_PART_COMMANDER_SHELLS)
SIGNAL_COMBO_COMMANDER = "edhrec_combo_decks"


def signal_for(
    component: str,
    bracket: str,
    *,
    combo_source: str = COMBO_SPELLBOOK,
    spellbook_shells: bool = False,
) -> str:
    """The stored signal name behind a component (empty when none is stored)."""
    if component == BRACKET_INCLUSION:
        return f"edhrec_bracket_inclusion:{bracket}" if bracket != BRACKET_NONE else ""
    if component == COMBOS:
        if combo_source == COMBO_COMMANDER:
            return SIGNAL_COMBO_COMMANDER
        return COMBO_PART_SHELLS if spellbook_shells else COMBO_PART_VARIANTS
    return {
        COMMANDER_INCLUSION: "edhrec_commander_inclusion",
        DECK_UNIVERSE: "deck_list_share",
        # derived from the counted corpus and the sources around it, not stored as such
        CORPUS_TUNED: "corpus_share:bracket:4+5",
        CORPUS_LOG_LIFT: "corpus_log_lift",
        CORPUS_BRACKET_SLOPE: "corpus_bracket_slope:4+5_vs_2",
        TOURNAMENT: "tournament_pool:edhtop16+corpus_bracket:5",
        EDHREC_THEME_REACH: "edhrec_theme_inclusion_max",
        SYNERGY: "edhrec_commander_synergy",
        TOURNAMENT_LISTS: "tournament_lists",
        TOURNAMENT_CONVERSION: "topdeck_card_conversion",
        GLOBAL_INCLUSION: "edhrec_global_inclusion",
        PLAYGROUP_OBSERVED: "playgroup_observed_winrate_gap",
        RUBRIC: "rubric_h_mean",
        SIMULATION: "",
    }[component]


def parse_universe_source(value: str) -> tuple[str, str, str] | None:
    """``(kind, source, bracket)`` of a ``universe_source`` value, ``None`` when it is not one.

    ``auto``, ``profile`` and ``none`` have an empty source and bracket; ``counted:<source>:
    <bracket>`` names one counted universe (neither part may be empty or contain a colon)."""
    if value in (UNIVERSE_AUTO, UNIVERSE_PROFILE, UNIVERSE_NONE):
        return value, "", ""
    parts = value.split(":")
    if len(parts) == 3 and parts[0] == UNIVERSE_COUNTED and parts[1].strip() and parts[2].strip():
        return UNIVERSE_COUNTED, parts[1], parts[2]
    return None


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
    share_scale: str = DEFAULT_SHARE_SCALE
    min_denominators: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_MIN_DENOMINATORS))
    missing_value: dict[str, str] = field(default_factory=dict)
    rank_commander_and_basics: bool = False
    # Other commanders known to the store are ordinary cards of the 99 for this commander:
    # ranked by default; off marks them tier N (NOT_RANKED_OTHER_COMMANDER).
    rank_other_commanders: bool = True
    universe_source: str = DEFAULT_UNIVERSE_SOURCE
    require_commander_signal: bool = DEFAULT_REQUIRE_COMMANDER_SIGNAL
    combo_source: str = DEFAULT_COMBO_SOURCE
    separate_lands: bool = DEFAULT_SEPARATE_LANDS
    # E4: what a card whose only evidence about this commander is counted zeros (0 of N) gets:
    # "D" (E4.b, recommended: the zero is a finding and counts fully) or "U" (E4.a: too little data,
    # reason ZERO_COUNT_ONLY).
    zero_count_tier: str = DEFAULT_ZERO_COUNT_TIER
    # E2.a: keep the EDHREC commander and bracket inclusion weights although a counted local
    # corpus exists (off by default: the corpus replaces them, see ``apply_corpus_rule``).
    edhrec_with_corpus: bool = False
    # #1365: index distance to a tier cut below which a card is marked "grenzwertig" (0 = off).
    borderline_distance: float = DEFAULT_BORDERLINE_DISTANCE

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
        if self.share_scale not in SHARE_SCALES:
            raise ValueError(f"share_scale must be one of {', '.join(SHARE_SCALES)}")
        if self.combo_source not in COMBO_SOURCES:
            raise ValueError(f"combo_source must be one of {', '.join(COMBO_SOURCES)}")
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
        missing = {
            name: self.missing_value.get(name, DEFAULT_MISSING_VALUE[name])
            for name in MISSING_CAPABLE
        }
        for name, choice in missing.items():
            if choice not in MISSING_CHOICES:
                raise ValueError(f"missing_value {name} must be skip or lowest")
        if not isinstance(self.rank_commander_and_basics, bool):
            raise ValueError("rank_commander_and_basics must be true or false")
        if not isinstance(self.rank_other_commanders, bool):
            raise ValueError("rank_other_commanders must be true or false")
        if not isinstance(self.separate_lands, bool):
            raise ValueError("separate_lands must be true or false")
        if self.zero_count_tier not in ZERO_COUNT_TIERS:
            raise ValueError(f"zero_count_tier must be one of {', '.join(ZERO_COUNT_TIERS)}")
        if not isinstance(self.edhrec_with_corpus, bool):
            raise ValueError("edhrec_with_corpus must be true or false")
        distance = _number(self.borderline_distance, "borderline_distance")
        if not 0.0 <= distance <= MAX_BORDERLINE_DISTANCE:
            raise ValueError(
                f"borderline_distance must be between 0 and {MAX_BORDERLINE_DISTANCE:g}"
            )
        object.__setattr__(self, "borderline_distance", distance)
        if not isinstance(self.require_commander_signal, bool):
            raise ValueError("require_commander_signal must be true or false")
        if parse_universe_source(self.universe_source) is None:
            raise ValueError(
                "universe_source must be auto, profile, none or counted:<source>:<bracket>"
            )
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
        """The smallest denominator a signal needs to be used (0 = no minimum)."""
        if component in _EDHREC_SHARES:
            return self.min_denominators[MIN_EDHREC]
        if component in (TOURNAMENT, TOURNAMENT_LISTS):
            return self.min_denominators[MIN_TOURNAMENT]
        if component == EDHREC_THEME_REACH:
            return self.min_denominators[MIN_EDHREC]
        if component == CORPUS_TUNED:
            return universe_minimum
        if component == TOURNAMENT_CONVERSION:
            return self.min_denominators[MIN_CONVERSION]
        if component == PLAYGROUP_OBSERVED:
            return self.min_denominators[MIN_PLAYGROUP]
        if component == DECK_UNIVERSE:
            return universe_minimum
        return 0

    @classmethod
    def recommended(cls) -> StrengthSettings:
        """Recommended default strength settings (Ausgewogen)."""
        return cls()

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
            "share_scale": self.share_scale,
            "min_denominators": dict(self.min_denominators),
            "missing_value": dict(self.missing_value),
            "rank_commander_and_basics": self.rank_commander_and_basics,
            "rank_other_commanders": self.rank_other_commanders,
            "universe_source": self.universe_source,
            "require_commander_signal": self.require_commander_signal,
            "combo_source": self.combo_source,
            "separate_lands": self.separate_lands,
            "zero_count_tier": self.zero_count_tier,
            "edhrec_with_corpus": self.edhrec_with_corpus,
            "borderline_distance": self.borderline_distance,
        }

    @classmethod
    def from_stored(cls, raw: Mapping[str, object]) -> tuple[StrengthSettings, list[str]]:
        """Settings of a STORED profile: top-level keys this version does not know (a profile
        written by another version) are ignored and returned, sorted; retired keys
        (``RETIRED_SETTING_KEYS``) are dropped without being named; invalid VALUES still
        raise ValueError."""
        unknown = sorted(set(raw) - _SETTINGS_KEYS - _retired(RETIRED_TOP_LEVEL))
        known = {key: value for key, value in raw.items() if key in _SETTINGS_KEYS}
        return cls.from_dict(known), unknown

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> StrengthSettings:
        """Settings from a plain mapping; absent keys take the default, retired keys
        (``RETIRED_SETTING_KEYS``) are dropped, every other unknown key fails."""
        unknown = set(raw) - _SETTINGS_KEYS - _retired(RETIRED_TOP_LEVEL)
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
        share_scale = raw.get("share_scale", defaults.share_scale)
        combo_source = raw.get("combo_source", defaults.combo_source)
        if (
            not isinstance(rank_group, str)
            or not isinstance(share_measure, str)
            or not isinstance(share_scale, str)
            or not isinstance(combo_source, str)
        ):
            raise ValueError(
                "rank_group, share_measure, share_scale and combo_source must be texts"
            )
        ranked = raw.get("rank_commander_and_basics", defaults.rank_commander_and_basics)
        if not isinstance(ranked, bool):
            raise ValueError("rank_commander_and_basics must be true or false")
        other_ranked = raw.get("rank_other_commanders", defaults.rank_other_commanders)
        if not isinstance(other_ranked, bool):
            raise ValueError("rank_other_commanders must be true or false")
        universe_source = raw.get("universe_source", defaults.universe_source)
        if not isinstance(universe_source, str):
            raise ValueError("universe_source must be a text")
        require = raw.get("require_commander_signal", defaults.require_commander_signal)
        if not isinstance(require, bool):
            raise ValueError("require_commander_signal must be true or false")
        separate = raw.get("separate_lands", defaults.separate_lands)
        if not isinstance(separate, bool):
            raise ValueError("separate_lands must be true or false")
        zero_tier = raw.get("zero_count_tier", defaults.zero_count_tier)
        if not isinstance(zero_tier, str):
            raise ValueError("zero_count_tier must be a text")
        with_corpus = raw.get("edhrec_with_corpus", defaults.edhrec_with_corpus)
        if not isinstance(with_corpus, bool):
            raise ValueError("edhrec_with_corpus must be true or false")
        return cls(
            weights={
                **DEFAULT_WEIGHTS,
                **{
                    str(k): _number(v, f"weight {k}")
                    for k, v in _without_retired(_mapping(weights), RETIRED_WEIGHTS).items()
                },
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
            share_scale=share_scale,
            min_denominators={
                **DEFAULT_MIN_DENOMINATORS,
                **{
                    str(k): _count(v, f"min_denominators {k}")
                    for k, v in _without_retired(
                        _mapping(minimums), RETIRED_MIN_DENOMINATORS
                    ).items()
                },
            },
            missing_value={str(k): str(v) for k, v in _mapping(missing).items()},
            rank_commander_and_basics=ranked,
            rank_other_commanders=other_ranked,
            universe_source=universe_source,
            require_commander_signal=require,
            combo_source=combo_source,
            separate_lands=separate,
            zero_count_tier=zero_tier,
            edhrec_with_corpus=with_corpus,
            borderline_distance=_number(
                raw.get("borderline_distance", defaults.borderline_distance),
                "borderline_distance",
            ),
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
                # EDHREC fallback weights (used without a counted local corpus, rule E2.a)
                COMMANDER_INCLUSION: 3.0,
                BRACKET_INCLUSION: 2.0,
                DECK_UNIVERSE: 4.5,
                CORPUS_TUNED: 1.0,
                CORPUS_LOG_LIFT: 2.0,
                CORPUS_BRACKET_SLOPE: 0.5,
                SYNERGY: 0.0,
                TOURNAMENT: 0.0,
                TOURNAMENT_LISTS: 0.0,
                TOURNAMENT_CONVERSION: 0.0,
                EDHREC_THEME_REACH: 1.0,
                GLOBAL_INCLUSION: 0.5,
                COMBOS: 0.5,
                PLAYGROUP_OBSERVED: 0.0,
                RUBRIC: 0.0,
                SIMULATION: 0.0,
            },
            DEFAULT_BRACKET,
        ),
        _preset(
            "Turniernah",
            {
                COMMANDER_INCLUSION: 1.0,
                BRACKET_INCLUSION: 2.0,
                DECK_UNIVERSE: 2.5,
                CORPUS_TUNED: 2.5,
                CORPUS_LOG_LIFT: 0.5,
                CORPUS_BRACKET_SLOPE: 2.0,
                SYNERGY: 0.0,
                TOURNAMENT: 2.0,
                TOURNAMENT_LISTS: 0.0,
                TOURNAMENT_CONVERSION: 0.0,
                EDHREC_THEME_REACH: 0.0,
                GLOBAL_INCLUSION: 0.5,
                COMBOS: 1.0,
                PLAYGROUP_OBSERVED: 0.0,
                RUBRIC: 0.0,
                SIMULATION: 0.0,
            },
            "cedh",
        ),
    ]
)


@dataclass(frozen=True)
class ObservationPart:
    """One cohort that an observation is made of (n of N of that cohort alone). Only the
    tournament component adds cohorts (EDHTop16 + corpus bracket 5, E3.a); the parts are shown,
    they never change the pooled value."""

    key: str
    label: str
    numerator: int
    denominator: int


@dataclass(frozen=True)
class Observation:
    """One published or counted value of a card for one component. ``None`` is unknown."""

    value: float | None
    numerator: int | None = None
    denominator: int | None = None
    # Free text a source adds to the row of a present value (the rubric: H, spread, raters).
    note: str = ""
    # A producer that picks one value among several shares (the highest EDHREC theme) shrinks
    # each share first and takes the maximum of the posterior means: ``shrunk`` is that value,
    # ``prior`` the prior it used. ``score_pool`` ranks it as it is, without shrinking again.
    shrunk: float | None = None
    prior: SharePrior | None = None
    # The cohorts a pooled count was added from (empty for every other observation).
    parts: tuple[ObservationPart, ...] = ()


@dataclass(frozen=True)
class PoolContext:
    """What ``score_pool`` needs to know about the cards besides their observations.

    ``type_group`` and ``mana_band`` map a card key to its comparison group; ``unranked``
    maps a card key to the reason it is not ranked (``NOT_RANKED_COMMANDER`` or
    ``NOT_RANKED_BASIC_LAND``); ``filter_cards`` are the cards a card filter of the deck
    universe requires; ``universe_minimum`` is the minimum universe of the chosen profile
    (the minimum denominator of the deck-universe component). ``function_group`` maps a
    card key to its functional roles (``card_role``): a card can carry several roles and
    then belongs to each of its role groups (see ``_groups_of``)."""

    type_group: Mapping[str, str] = field(default_factory=dict)
    mana_band: Mapping[str, str] = field(default_factory=dict)
    unranked: Mapping[str, str] = field(default_factory=dict)
    filter_cards: Collection[str] = field(default_factory=frozenset)
    universe_minimum: int = 0
    function_group: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    spellbook_shells: bool = False


class ComponentPart(TypedDict):
    """One cohort of a pooled count, with its own n / N (D5)."""

    key: str
    label: str
    numerator: int
    denominator: int


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
    # Empirical Bayes (denominator below ``EB_MAX_DENOMINATOR``): the posterior mean that was
    # ranked instead of the Wilson bound, and the prior of the component (None otherwise).
    shrunk: float | None
    prior_mean: float | None
    prior_strength: float | None
    data_class: str
    percentile: float | None
    weight: float
    min_denominator: int
    group: str | None
    group_size: int | None
    group_fallback: bool
    # D5: the cohorts a pooled count was added from, each with its own n / N (``parts`` is empty
    # for every row that is no pool), and the hint when two cohorts were added. Display only: the
    # value, the score and the index are those of the pooled count.
    parts: list[ComponentPart]
    mixed_cohorts_note: str | None


class CardStrength(TypedDict):
    index: float | None
    coverage: float | None
    tier: str
    reason: str
    note: str
    present: int
    components: list[ComponentResult]
    # #1365: confidence from coverage and denominators (None without an index), its level
    # ("high" / "medium" / "low"), and the "grenzwertig" mark: the index lies closer than
    # ``borderline_distance`` to a tier cut (``borderline_cut`` names the nearest cut tier,
    # ``cut_distance`` the distance in index points).
    confidence: float | None
    confidence_level: str | None
    borderline: bool
    borderline_cut: str | None
    cut_distance: float | None
    # D4: ``confidence`` / ``confidence_level`` hang on the COUNT (numerator) of the shares; the
    # earlier definition on the denominator stays as ``confidence_by_denominator`` (+ level), and
    # ``zero_count_thin`` names the components whose counted zero rests on fewer than
    # ``CONFIDENCE_ZERO_MIN_DENOMINATOR`` decks (a zero that is real, but thin).
    confidence_by_denominator: float | None
    confidence_by_denominator_level: str | None
    zero_count_thin: list[str]
    # "gezaehlte_null" when more than half of the confidence weight rests on counted zeros
    # (confidence in an absence, 0 of N decks), else "zaehler"; None without a confidence.
    confidence_basis: str | None


def _confidence_rows(components: Collection[ComponentResult]) -> list[ComponentResult]:
    return [
        row
        for row in components
        if row["weight"] > 0 and row["percentile"] is not None and row["denominator"]
    ]


def confidence_by_denominator_value(
    coverage: float, components: Collection[ComponentResult]
) -> float:
    """The confidence of #1365, kept for reference: ``coverage`` times the weight-weighted mean of
    ``N / (N + CONFIDENCE_K)`` over the weighted components that have a value and a denominator
    N. It hangs on the DENOMINATOR, so a card in 3 of 10 128 decks scores as sure as one in
    3 000 (all 922 cards of the Chulane pool were "high"); ``confidence_value`` replaces it."""
    rows = _confidence_rows(components)
    total = sum(row["weight"] for row in rows)
    if total <= 0:
        return 0.0
    reliability = sum(
        row["weight"] * (row["denominator"] or 0) / ((row["denominator"] or 0) + CONFIDENCE_K)
        for row in rows
    )
    return round(coverage * reliability / total, 4)


def count_reliability(row: ComponentResult) -> float:
    """Reliability 0..1 of one row from its COUNT k: ``k / (k + CONFIDENCE_K)`` (D4). A counted
    zero (0 of N, rule B12/E4.b) is real evidence: its count is the denominator N, thin only below
    ``CONFIDENCE_ZERO_MIN_DENOMINATOR``. A row without a numerator (the Playgroup gap has only its
    sample) has no count to build on: reliability 0, never the sample size."""
    numerator = row["numerator"]
    if numerator is None:
        return 0.0
    count = (row["denominator"] or 0) if numerator == 0 else numerator
    return count / (count + CONFIDENCE_K)


CONFIDENCE_BASIS_ZERO = "gezaehlte_null"
CONFIDENCE_BASIS_COUNT = "zaehler"


def confidence_basis(components: Collection[ComponentResult]) -> str:
    """Where the confidence comes from: ``gezaehlte_null`` when more than half of the weight of
    the rows it is made of sits on counted zeros (0 of N decks: confidence in an ABSENCE),
    otherwise ``zaehler`` (it rests on positive counts). The formula does not change (B12)."""
    rows = _confidence_rows(components)
    total = sum(row["weight"] for row in rows)
    zeros = sum(row["weight"] for row in rows if row["numerator"] == 0)
    return CONFIDENCE_BASIS_ZERO if total > 0 and zeros * 2 > total else CONFIDENCE_BASIS_COUNT


def zero_count_thin_components(components: Collection[ComponentResult]) -> list[str]:
    """The weighted components whose counted zero rests on fewer than
    ``CONFIDENCE_ZERO_MIN_DENOMINATOR`` decks."""
    return [
        row["component"]
        for row in _confidence_rows(components)
        if row["numerator"] == 0 and (row["denominator"] or 0) < CONFIDENCE_ZERO_MIN_DENOMINATOR
    ]


def confidence_value(coverage: float, components: Collection[ComponentResult]) -> float:
    """Confidence 0..1 of a card (D4): ``coverage`` times the weight-weighted mean of
    ``count_reliability`` over the weighted components that have a value and a denominator (a
    counted zero included). It hangs on the COUNT of each share, not on its denominator: 3 of
    10 000 decks is thin, 3 000 of 10 000 is not. Without such a component the reliability is 0.
    It says how well the figures are counted, not how good the card is."""
    rows = _confidence_rows(components)
    total = sum(row["weight"] for row in rows)
    if total <= 0:
        return 0.0
    reliability = sum(row["weight"] * count_reliability(row) for row in rows)
    return round(coverage * reliability / total, 4)


def confidence_level(confidence: float) -> str:
    """ "high" from 0.6, "medium" from 0.35, else "low"."""
    if confidence >= CONFIDENCE_HIGH:
        return "high"
    return "medium" if confidence >= CONFIDENCE_MEDIUM else "low"


def borderline_info(
    index: float | None, cuts: Mapping[str, float], distance: float
) -> tuple[bool, str | None, float | None]:
    """(borderline, nearest cut tier, distance to it) of an index. Borderline means strictly
    closer than ``distance`` to a cut; a distance of 0 switches the mark off."""
    if index is None:
        return False, None, None
    tier, cut = min(cuts.items(), key=lambda item: abs(index - item[1]))
    gap = round(abs(index - cut), 4)
    return distance > 0 and gap < distance, tier, gap


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


def zero_floor_ranks(values: Mapping[str, float]) -> dict[str, float]:
    """Percentile ranks where a value of 0 (a counted 0: no combo) scores 0.0 instead of the
    mean rank of its tie group; the other values are ranked among all values, so they sit above
    the zeros. Identical to ``percentile_ranks`` when no value is 0."""
    ranks = percentile_ranks(values)
    return {key: (0.0 if value <= 0.0 else ranks[key]) for key, value in values.items()}


def share_scale_values(
    values: Mapping[str, float], scale: str = DEFAULT_SHARE_SCALE, log_k: float = LOG_SHARE_K
) -> dict[str, float]:
    """Convert share-signal values into 0..1 component scores under ``scale`` (issue #1351).

    - ``rank``: percentile rank 0..1 via ``percentile_ranks`` (identical to the rank-only
      index).
    - ``log`` (default, E5.a of #1364): ``ln(1 + k v) / ln(1 + k v_max)`` with ``k = LOG_SHARE_K``
      (150) and ``v_max`` the largest value in ``values``. A share of 0 scores exactly 0, the
      largest scores 1, and small counts stay visibly above zero (a 0.1 % card scores 0.05 when
      the largest share is 60 %).
    - ``share``: square root of the share relative to the largest value in ``values``
      (``sqrt(v / max_v)``), dampening the very top while keeping 3 % and 30 % far apart.
    - For both: a single valued card takes ``0.5`` (or ``0.0`` when its value is 0), and an
      all-zero population gets ``0.0``.
    """
    if scale == SCALE_RANK:
        return percentile_ranks(values)
    if scale not in (SCALE_SHARE, SCALE_LOG):
        raise ValueError(f"share_scale must be one of {', '.join(SHARE_SCALES)}")
    count = len(values)
    if count == 0:
        return {}
    if count == 1:
        return {key: (0.5 if val > 0.0 else 0.0) for key, val in values.items()}
    highest = max(values.values())
    if highest <= 0.0:
        return {key: 0.0 for key in values}
    if scale == SCALE_LOG:
        return log_share_scores(values, highest, log_k)
    return {key: math.sqrt(max(0.0, value) / highest) for key, value in values.items()}


def log_share_scores(
    values: Mapping[str, float], highest: float, k: float = LOG_SHARE_K
) -> dict[str, float]:
    """``ln(1 + k v) / ln(1 + k v_max)`` per key (``highest`` is ``v_max`` > 0). ``k`` is a
    parameter only so that the ranking check can report the sensitivity of k = 100 / 150 / 200;
    every setting uses ``LOG_SHARE_K``."""
    top = math.log1p(k * highest)
    return {key: math.log1p(k * max(0.0, value)) / top for key, value in values.items()}


# ---------- empirical Bayes shrinkage of shares with a small denominator (#1364) ----------
# A share ``k / n`` with ``n`` below ``EB_MAX_DENOMINATOR`` is replaced by the posterior mean of a
# Beta-Binomial model, ``(k + m M) / (n + M)``: the share is pulled towards the prior mean ``m`` of
# the component, the more so the smaller ``n`` is and the larger the prior strength ``M`` (a
# pseudo-count). Both are estimated per component from the pool by the method of moments, so a
# card with 0 of 48 keeps a small positive value (the sample cannot rule out a small rate) and
# the order of cards with the same denominator is exactly the raw order. Shares with a
# denominator of ``EB_MAX_DENOMINATOR`` or more (the 2,823 counted decks, EDHREC's thousands) keep
# the Wilson bound: their sample is large enough that the bound hardly differs from the share.
EB_MAX_DENOMINATOR = 500
# The prior strength is clamped to [EB_STRENGTH_MIN, EB_STRENGTH_MAX]: below 2 the prior is
# weaker than a single observation and the estimate is just the raw share; above 200 a 48-deck
# sample would hardly move the prior (n / (n + M) < 20 %) and the signal would be flattened.
EB_STRENGTH_MIN = 2.0
EB_STRENGTH_MAX = 200.0
# The prior is only estimated from at least this many valued cards; below that the Wilson bound
# stays in use for them (a prior from three cards is noise).
EB_MIN_CARDS = MIN_GROUP


@dataclass(frozen=True)
class SharePrior:
    """The Beta prior of one component: mean ``m``, strength ``M = alpha + beta`` and how many
    cards it was estimated from (``clamped`` when the strength hit a bound)."""

    mean: float
    strength: float
    cards: int
    clamped: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "prior_mean": round(self.mean, 6),
            "prior_strength": round(self.strength, 3),
            "cards": self.cards,
            "strength_clamped": self.clamped,
            "max_denominator": EB_MAX_DENOMINATOR,
            "strength_range": [EB_STRENGTH_MIN, EB_STRENGTH_MAX],
        }


def beta_binomial_prior(counts: Collection[tuple[int, int]]) -> SharePrior | None:
    """Method-of-moments Beta prior of ``(numerator, denominator)`` pairs, ``None`` below
    ``EB_MIN_CARDS`` pairs or without any decks.

    ``m`` is the pooled share ``sum(k) / sum(n)``. With weights ``n_i`` the weighted variance
    of the shares estimates ``tau2 (1 - 1/nbar) + m (1 - m) / nbar`` (``tau2`` the prior variance
    ``m (1 - m) / (M + 1)``, ``nbar`` the mean denominator), which is solved for ``tau2``. No
    excess variance (``tau2 <= 0``) or a degenerate mean (all 0 or all n) gives the maximum
    strength; the strength is clamped to ``[EB_STRENGTH_MIN, EB_STRENGTH_MAX]``."""
    pairs = [(k, n) for k, n in counts if n > 0 and 0 <= k <= n]
    if len(pairs) < EB_MIN_CARDS:
        return None
    total = sum(n for _k, n in pairs)
    mean = sum(k for k, _n in pairs) / total
    if mean <= 0.0 or mean >= 1.0:
        return SharePrior(min(max(mean, 0.0), 1.0), EB_STRENGTH_MAX, len(pairs), True)
    mean_n = total / len(pairs)
    variance = sum(n * (k / n - mean) ** 2 for k, n in pairs) / total
    if mean_n <= 1.0:
        return SharePrior(mean, EB_STRENGTH_MAX, len(pairs), True)
    tau2 = (variance - mean * (1.0 - mean) / mean_n) / (1.0 - 1.0 / mean_n)
    if tau2 <= 0.0:
        return SharePrior(mean, EB_STRENGTH_MAX, len(pairs), True)
    raw = mean * (1.0 - mean) / tau2 - 1.0
    strength = min(max(raw, EB_STRENGTH_MIN), EB_STRENGTH_MAX)
    return SharePrior(mean, strength, len(pairs), strength != raw)


def shrunk_share(numerator: int, denominator: int, prior: SharePrior) -> float:
    """Posterior mean ``(k + m M) / (n + M)`` of a share under ``prior``."""
    return (numerator + prior.mean * prior.strength) / (denominator + prior.strength)


# ---------- derived corpus signals (#1364, E3.a) ----------
# Both values are ``DERIVED_DESCRIPTIVE`` ratios of counts: a base-10 log ratio, damped towards 0
# (no difference) by ``n / (n + LOG_RATIO_DAMPING)`` of the hit count ``n``, capped at +-2 (a
# factor of 100) and scaled to 0..1 as ``(x + 2) / 4`` (0.5 = no difference). The damping keeps a
# card with one or two decks from reaching an extreme, whatever its ratio is.
LOG_RATIO_DAMPING = 5
LOG_RATIO_CAP = 2.0
SLOPE_MIN_HITS = 5


def _damped_log_value(log_ratio: float, hits: int) -> float:
    damped = log_ratio * hits / (hits + LOG_RATIO_DAMPING)
    return (max(-LOG_RATIO_CAP, min(LOG_RATIO_CAP, damped)) + LOG_RATIO_CAP) / (2 * LOG_RATIO_CAP)


def log_lift_value(hits: int, total: int, global_share: float | None) -> float | None:
    """The corpus lift of a card: ``log10((hits / total) / global_share)``, damped by
    ``hits / (hits + 5)``, capped at +-2 and scaled to 0..1. ``None`` for a card with no hit
    (the lift of a count of 0 is undefined, not low), without a corpus or without a positive
    global share."""
    if hits <= 0 or total <= 0 or hits > total:
        return None
    if global_share is None or not math.isfinite(global_share) or global_share <= 0.0:
        return None
    return _damped_log_value(math.log10((hits / total) / global_share), hits)


def bracket_slope_value(
    high_hits: int, high_total: int, low_hits: int, low_total: int
) -> float | None:
    """The bracket slope of a card: ``log10`` of the share in the higher brackets (4 and 5)
    over the share in the lower one (bracket 2), damped by ``n / (n + 5)`` of ALL hits in both
    groups, capped at +-2 and scaled to 0..1. Only from ``SLOPE_MIN_HITS`` hits; a group
    without a hit uses half a deck ((h + 0.5) / (n + 1), the Jeffreys estimate) so that the
    ratio stays finite."""
    hits = high_hits + low_hits
    if hits < SLOPE_MIN_HITS or high_total <= 0 or low_total <= 0:
        return None
    if not (0 <= high_hits <= high_total and 0 <= low_hits <= low_total):
        return None
    high = (high_hits + 0.5) / (high_total + 1)
    low = (low_hits + 0.5) / (low_total + 1)
    return _damped_log_value(math.log10(high / low), hits)


# ---------- the EDHREC weight rule of the counted corpus (#1364, E2.a) ----------
RULE_CORPUS_ZERO = "CORPUS_ZERO"
RULE_EDHREC_FALLBACK = "EDHREC_FALLBACK"
RULE_EDHREC_KEPT = "EDHREC_KEPT"
EDHREC_RULE_COMPONENTS = (COMMANDER_INCLUSION, BRACKET_INCLUSION)


class WeightRule(TypedDict):
    """Which weight rule the result was computed with (counts and codes only)."""

    rule: str
    corpus_available: bool
    corpus_decks: int
    min_universe: int
    requested: dict[str, float]
    effective: dict[str, float]
    note: str


def apply_corpus_rule(
    settings: StrengthSettings, *, corpus_decks: int, min_universe: int
) -> tuple[StrengthSettings, WeightRule]:
    """Settings with the E2.a rule applied, and the rule that applied.

    - ``CORPUS_ZERO``: a counted local corpus of at least ``min_universe`` decks exists, and the
      setting ``edhrec_with_corpus`` is off (default): the weights of the EDHREC commander and
      bracket inclusion are 0, the corpus signals carry the index.
    - ``EDHREC_FALLBACK``: there is no such corpus: the EDHREC weights apply as set.
    - ``EDHREC_KEPT``: a corpus exists, but the setting keeps the EDHREC weights.
    The rule is explicit and always reported; it never changes any other weight."""
    available = corpus_decks > 0 and corpus_decks >= min_universe
    requested = {name: settings.weights[name] for name in EDHREC_RULE_COMPONENTS}
    if not available:
        rule = RULE_EDHREC_FALLBACK
        note = (
            f"Kein gezählter lokaler Korpus (mindestens {min_universe} Decks nötig, "
            f"{corpus_decks} vorhanden): die EDHREC-Gewichte gelten."
        )
        effective = dict(requested)
    elif settings.edhrec_with_corpus:
        rule = RULE_EDHREC_KEPT
        note = (
            f"Gezählter lokaler Korpus mit {corpus_decks} Decks vorhanden, die EDHREC-Gewichte "
            "bleiben auf Wunsch (Einstellung) bestehen."
        )
        effective = dict(requested)
    else:
        rule = RULE_CORPUS_ZERO
        note = (
            f"Gezählter lokaler Korpus mit {corpus_decks} Decks vorhanden: die EDHREC-Gewichte "
            "für Aufnahme beim Commander und im Bracket sind 0, der Korpus trägt den Index."
        )
        effective = {name: 0.0 for name in EDHREC_RULE_COMPONENTS}
    resolved = (
        settings
        if effective == requested
        else replace(settings, weights={**settings.weights, **effective})
    )
    return resolved, {
        "rule": rule,
        "corpus_available": available,
        "corpus_decks": corpus_decks,
        "min_universe": min_universe,
        "requested": requested,
        "effective": effective,
        "note": note,
    }


def combo_quality(
    parts: Mapping[str, Mapping[str, float]], primary: str = COMBO_PART_VARIANTS
) -> dict[str, float]:
    """The combos value of a card: the mean of its percentile ranks in the combo
    quality parts, over the cards the primary part lists (the variant count, or
    the shell count when the store holds the shell parts, #1366). A card the
    primary part does not list gets no value (not listed, not 0); a part beyond
    the primary one counts only for the cards that have a value in it, so the
    mean of a card with fewer parts is the mean of the parts it has. The value
    is itself a rank mixture in 0..1: ``score_pool`` ranks it among the pool
    like every other component value, which keeps the order of this mixture."""
    primary_values = parts.get(primary, {})
    ranks = {name: percentile_ranks(values) for name, values in parts.items() if values}
    result: dict[str, float] = {}
    for card, count in primary_values.items():
        if count <= 0.0:
            # a counted 0 (no qualifying combo) scores 0, below every card that has one; the
            # tie-mean rank of the zero group would give it about the median
            result[card] = 0.0
            continue
        found = [ranks[name][card] for name in ranks if card in ranks[name]]
        if found:
            result[card] = sum(found) / len(found)
    return result


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


def observed_gap(observation: Observation) -> float | None:
    """The Playgroup gap as the index reads it: the published gap in percentage points, shrunk
    towards zero by the sample (``gap * n / (n + k)``); ``None`` below ``OBSERVED_MIN_SAMPLE``
    games in which the card was cast or without a value. The denominator is that sample."""
    if observation.value is None or not math.isfinite(observation.value):
        return None
    sample = observation.denominator
    if sample is None or sample < OBSERVED_MIN_SAMPLE:
        return None
    return observation.value * sample / (sample + OBSERVED_SHRINKAGE)


def _scored_value(
    component: str, observation: Observation, measure: str = MEASURE_WILSON
) -> tuple[float | None, float | None]:
    """(value used for ranking, Wilson bound or None)."""
    if observation.value is None and observation.numerator is None:
        return None, None
    if component == PLAYGROUP_OBSERVED:
        return observed_gap(observation), None
    if component in SHARE_COMPONENTS:
        return _share_values(component, observation, measure)
    if observation.value is None or not math.isfinite(observation.value):
        return None, None
    if component in DIRECT_COMPONENTS and not 0.0 <= observation.value <= 1.0:
        return None, None  # a score outside 0..1 is not a score: unknown, never clipped
    return observation.value, None


def _tier(index: float | None, settings: StrengthSettings, enough: bool) -> str:
    if index is None or not enough:
        return TIER_UNKNOWN
    for tier in ("S", "A", "B", "C"):
        if index >= settings.tier_cuts[tier]:
            return tier
    return "D"


NO_COMMANDER_SIGNAL_NOTE = "kein Signal speziell für diesen Commander"
ZERO_COUNT_ONLY_NOTE = (
    "einziger Beleg zu diesem Commander sind gezählte Nullen (0 von N Decks); Einstellung "
    "„Stufe bei gezählter Null“: zu wenig Daten"
)
NOT_RANKED_NOTES = {
    NOT_RANKED_COMMANDER: "nicht bewertet (Commander)",
    NOT_RANKED_BASIC_LAND: "nicht bewertet (Standardland)",
    NOT_RANKED_OTHER_COMMANDER: "nicht bewertet (anderer Commander)",
}


@dataclass
class _ComponentRanking:
    """Values and percentile ranks of one component over the ranked cards of the pool."""

    values: dict[str, float]
    wilson: dict[str, float | None]
    reasons: dict[str, str]
    pool_ranks: dict[str, float]
    group_ranks: dict[str, tuple[tuple[str, ...], dict[str, int], float]]
    reference_denominator: int | None
    minimum: int
    # empirical Bayes: card -> posterior mean, and the prior it came from (None without any)
    shrunk: dict[str, float] = field(default_factory=dict)
    prior: SharePrior | None = None
    # separate lands under the pool comparison: card -> (group name, valued cards in it,
    # fell back to the whole pool because the group was smaller than ``MIN_GROUP``)
    land_split: dict[str, tuple[str, int, bool]] = field(default_factory=dict)

    @property
    def usable(self) -> bool:
        return bool(self.values)


def _groups_of(settings: StrengthSettings, context: PoolContext, card: str) -> tuple[str, ...]:
    """The comparison groups of a card under the chosen ``rank_group``.

    Type and mana band give one group each. The function gives one group per functional
    role of the card, so a card with several roles belongs to several groups; its group
    rank is the mean of its ranks in those groups (``_rank_component``). The pool gives
    no group. A card of which no group of the chosen kind is known has none — under the
    function that is a card without a sourced role, said openly, never a group of its own.
    """
    if settings.rank_group == GROUP_TYPE:
        name = context.type_group.get(card, "")
        return (name,) if name else ()
    if settings.rank_group == GROUP_MANA_BAND:
        name = context.mana_band.get(card, "")
        return (name,) if name else ()
    if settings.rank_group == GROUP_FUNCTION:
        return tuple(context.function_group.get(card, ()))
    return ()


def _scale_component_values(
    component: str,
    values: Mapping[str, float],
    settings: StrengthSettings,
    log_k: float = LOG_SHARE_K,
) -> dict[str, float]:
    """Convert component values to 0..1 scores: share components use ``settings.share_scale``,
    direct components (the rubric) keep their 0..1 value, the other non-share components
    (synergy, combos, playgroup) always use ``percentile_ranks``."""
    if component in SHARE_COMPONENTS:
        return share_scale_values(values, settings.share_scale, log_k)
    if component in ABOVE_NEUTRAL_COMPONENTS:
        return {card: above_neutral_score(value) for card, value in values.items()}
    if component in DIRECT_COMPONENTS:
        return dict(values)
    if component == COMBOS:
        return zero_floor_ranks(values)
    return percentile_ranks(values)


def _is_land(context: PoolContext, card: str) -> bool:
    return context.type_group.get(card) == TYPE_LAND


def _split_scale(
    component: str,
    values: Mapping[str, float],
    settings: StrengthSettings,
    context: PoolContext,
    log_k: float = LOG_SHARE_K,
) -> tuple[dict[str, float], dict[str, tuple[str, int, bool]]]:
    """Pool-level 0..1 scores of ``values`` and, when ``settings.separate_lands`` is on, the
    land split behind them: lands are scaled against lands and spells against spells. A group
    with fewer than ``MIN_GROUP`` valued cards keeps its score from the whole population (said in
    the row), like every too small comparison group. Without ``separate_lands`` it is the
    plain scaling of the whole pool."""
    if not settings.separate_lands or component in DIRECT_COMPONENTS:
        # a direct score does not depend on the other cards: nothing to split
        return _scale_component_values(component, values, settings, log_k), {}
    parts = (
        (GROUP_LANDS, {card: v for card, v in values.items() if _is_land(context, card)}),
        (GROUP_SPELLS, {card: v for card, v in values.items() if not _is_land(context, card)}),
    )
    scores: dict[str, float] = {}
    info: dict[str, tuple[str, int, bool]] = {}
    whole: dict[str, float] | None = None
    for name, part in parts:
        if not part:
            continue
        small = len(part) < MIN_GROUP
        if small:
            if whole is None:
                whole = _scale_component_values(component, values, settings, log_k)
            scaled = {card: whole[card] for card in part}
        else:
            scaled = _scale_component_values(component, part, settings, log_k)
        scores.update(scaled)
        info.update({card: (name, len(part), small) for card in part})
    return scores, info


def _rank_component(
    settings: StrengthSettings,
    context: PoolContext,
    component: str,
    observations: Mapping[str, Mapping[str, Observation]],
    skipped: Collection[str],
    log_k: float = LOG_SHARE_K,
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
    small: dict[str, tuple[int, int]] = {}
    pre_shrunk: dict[str, float] = {}
    pre_prior: SharePrior | None = None
    for card, per_card in observations.items():
        if card in skipped:
            continue
        observation = per_card.get(component)
        if observation is None:
            reasons[card] = BELOW_MIN_DENOMINATOR if whole_below else NOT_LISTED
            continue
        if whole_below or (
            (component in SHARE_COMPONENTS or component == PLAYGROUP_OBSERVED)
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
        if component == SYNERGY and value < 0.0:
            reasons[card] = NEGATIVE_NEUTRAL
            continue
        values[card] = value
        wilson[card] = bound
        if (
            component in SHARE_COMPONENTS
            and settings.share_measure == MEASURE_WILSON
            and observation.shrunk is not None
            and observation.prior is not None
        ):
            values[card] = pre_shrunk[card] = observation.shrunk
            wilson[card] = None
            pre_prior = observation.prior
        elif (
            component in SHARE_COMPONENTS
            and settings.share_measure == MEASURE_WILSON
            and observation.numerator is not None
            and observation.denominator is not None
            and 0 < observation.denominator < EB_MAX_DENOMINATOR
        ):
            small[card] = (observation.numerator, observation.denominator)
    prior = beta_binomial_prior(list(small.values())) if small else None
    shrunk: dict[str, float] = dict(pre_shrunk)
    if prior is None:
        prior = pre_prior
    if prior is not None:
        for card, (numerator, denominator) in small.items():
            shrunk[card] = values[card] = shrunk_share(numerator, denominator, prior)
            wilson[card] = None
    pool_ranks, land_split = _split_scale(component, values, settings, context, log_k)
    group_ranks: dict[str, tuple[tuple[str, ...], dict[str, int], float]] = {}
    if settings.rank_group != GROUP_POOL:
        # a comparison group never mixes lands and spells while ``separate_lands`` is on
        members: dict[tuple[str, bool], dict[str, float]] = {}
        for card, value in values.items():
            land = settings.separate_lands and _is_land(context, card)
            for name in _groups_of(settings, context, card):
                members.setdefault((name, land), {})[card] = value
        found: dict[str, dict[str, tuple[int, float]]] = {}
        for (name, _land), group_values in members.items():
            if len(group_values) >= MIN_GROUP:
                ranks = _scale_component_values(component, group_values, settings, log_k)
                for card, rank in ranks.items():
                    found.setdefault(card, {})[name] = (len(group_values), rank)
        for card, per_group in found.items():
            names = tuple(name for name in _groups_of(settings, context, card) if name in per_group)
            sizes = {name: per_group[name][0] for name in names}
            percentile = sum(per_group[name][1] for name in names) / len(names)
            group_ranks[card] = (names, sizes, percentile)
    return _ComponentRanking(
        values,
        wilson,
        reasons,
        pool_ranks,
        group_ranks,
        reference,
        minimum,
        shrunk,
        prior,
        land_split,
    )


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
    if reason == NEGATIVE_NEUTRAL:
        return "negative Synergie (< 0) wirkt nicht als Abzug (neutral)"
    if reason == MISSING_AS_LOWEST:
        return "nicht gelistet, als niedrigster Rang gezählt (Einstellung)"
    if reason == ZERO_COUNT:
        denominator = observation.denominator if observation is not None else None
        return (
            f"gezählt: in 0 von {denominator} Decks (der Korpus ist vollständig gezählt, "
            "die Karte steht in keinem Deck; ein Befund, keine fehlende Beobachtung)"
        )
    if reason == FILTER_CARD:
        return (
            "Filterkarte des Universums: steht per Definition in jedem Deck der Teilmenge, "
            "ohne Wert und nicht gerankt"
        )
    return NOT_RANKED_NOTES.get(reason, "")


def component_label(component: str, *, combo_source: str = COMBO_COMMANDER) -> str:
    """The German label of an index component."""
    if component == COMBOS:
        return (
            "Kombos (EDHREC, beim Commander)"
            if combo_source == COMBO_COMMANDER
            else "Kombos (Commander Spellbook)"
        )
    return LABELS[component]


def weights_without_effect(settings: StrengthSettings, collected: Collection[str]) -> list[str]:
    """Notes for a positive weight on a source that has no data at all (it cannot act)."""
    return [
        f"{LABELS[name]}: keine Daten, Gewicht ohne Wirkung"
        for name in COMPONENTS
        if name in UNCOLLECTED_BY_DESIGN
        and name not in collected
        and settings.effective_weight(name) > 0
    ]


def _component_parts(observation: Observation | None, status: str) -> list[ComponentPart]:
    if observation is None or status not in (PRESENT, ZERO_COUNT):
        return []
    return [
        {
            "key": part.key,
            "label": part.label,
            "numerator": part.numerator,
            "denominator": part.denominator,
        }
        for part in observation.parts
    ]


MIXED_COHORTS_NOTE = "zwei Kohorten addiert (E3.a)"


def _mixed_cohorts_note(observation: Observation | None, status: str) -> str | None:
    """The hint on a pooled count that was added from two cohorts (D5)."""
    if observation is None or status not in (PRESENT, ZERO_COUNT) or len(observation.parts) < 2:
        return None
    return MIXED_COHORTS_NOTE


# ---------- stability of the tier against the weights (D6) ----------

# The tier of a card is re-derived under weight variants and the share of variants that keep it
# is reported. Variants (all on the weights of the request, only weights above 0 move): every such
# weight alone x0.8 and x1.2, plus ``STABILITY_RANDOM_VARIANTS`` variants in which all of them
# move at once by a factor drawn uniformly from 0.8..1.2 with the fixed seed ``STABILITY_SEED``.
# The ranking of the components does not depend on the weights, so a variant re-aggregates the
# stored component ranks of each card exactly as ``score_pool`` does (same sums, same rounding,
# same cuts, same coverage rule); the test suite compares the unchanged variant with the tiers
# of ``score_pool``. A card whose share of kept tiers is below ``STABILITY_UNSHARP_BELOW`` is
# "unscharf" (its tier is not robust against plausible weights).
STABILITY_FACTOR = 0.2
STABILITY_RANDOM_VARIANTS = 64
STABILITY_SEED = 20261117
STABILITY_UNSHARP_BELOW = 0.8


@dataclass(frozen=True)
class TierInputs:
    """What the aggregation of one card needs again for a weight variant: the ranked weighted
    components it has (component, rank 0..1 in the order of ``score_pool``), the weighted
    components it could have (the coverage denominator) and the minimum number of signals."""

    present: tuple[tuple[str, float], ...]
    possible: tuple[str, ...]
    needed: int


class TierAlternative(TypedDict):
    tier: str
    variants: int


class TierStability(TypedDict):
    stability: float
    kept: int
    variants: int
    alternatives: list[TierAlternative]


def stability_factor_sets(names: Collection[str]) -> list[dict[str, float]]:
    """The weight factor sets of the variants, in a fixed order: for every name (sorted) x0.8
    and x1.2 alone, then the seeded random sets. Names are the weights above 0 that move."""
    ordered = sorted(names)
    sets: list[dict[str, float]] = []
    for name in ordered:
        for factor in (1.0 - STABILITY_FACTOR, 1.0 + STABILITY_FACTOR):
            sets.append({other: (factor if other == name else 1.0) for other in ordered})
    rng = random.Random(STABILITY_SEED)
    for _ in range(STABILITY_RANDOM_VARIANTS):
        sets.append(
            {name: rng.uniform(1.0 - STABILITY_FACTOR, 1.0 + STABILITY_FACTOR) for name in ordered}
        )
    return sets


def _variant_tier(
    settings: StrengthSettings,
    inputs: TierInputs,
    weights: Mapping[str, float],
    possible_weight: float,
) -> str:
    present_weight = 0.0
    weighted = 0.0
    for component, percentile in inputs.present:
        weight = weights[component]
        present_weight += weight
        weighted += weight * percentile
    coverage = present_weight / possible_weight if possible_weight > 0 else 0.0
    index = round(100.0 * weighted / present_weight, 1) if present_weight > 0 else None
    present = len(inputs.present)
    enough = present > 0 and coverage >= settings.min_coverage and present >= inputs.needed
    return _tier(index, settings, enough)


def tier_stability(
    settings: StrengthSettings,
    inputs: Mapping[str, TierInputs],
    tiers: Mapping[str, str],
    factor_sets: Sequence[Mapping[str, float]] | None = None,
) -> dict[str, TierStability]:
    """Per card of ``inputs`` (the ranked cards with a tier): the share of weight variants that
    keep the card's tier in ``tiers``, the number of variants and the other tiers the variants
    gave (most frequent first). ``factor_sets`` overrides the variants (tests); the default are
    ``stability_factor_sets`` over the components that carry a weight above 0."""
    names: set[str] = set()
    for item in inputs.values():
        names.update(name for name, _rank in item.present)
        names.update(item.possible)
    sets = list(factor_sets) if factor_sets is not None else stability_factor_sets(names)
    base = {name: settings.effective_weight(name) for name in names}
    variant_weights = [
        {name: base[name] * factors.get(name, 1.0) for name in names} for factors in sets
    ]
    totals: dict[tuple[str, ...], list[float]] = {}
    answers: dict[tuple[object, ...], tuple[int, dict[str, int]]] = {}
    result: dict[str, TierStability] = {}
    for card, item in inputs.items():
        tier = tiers[card]
        key = (item.present, item.possible, item.needed, tier)
        found = answers.get(key)
        if found is None:
            possible_totals = totals.get(item.possible)
            if possible_totals is None:
                possible_totals = [
                    sum(weights[name] for name in item.possible) for weights in variant_weights
                ]
                totals[item.possible] = possible_totals
            other: dict[str, int] = {}
            kept = 0
            for weights, possible_weight in zip(variant_weights, possible_totals, strict=True):
                variant = _variant_tier(settings, item, weights, possible_weight)
                if variant == tier:
                    kept += 1
                else:
                    other[variant] = other.get(variant, 0) + 1
            found = (kept, other)
            answers[key] = found
        kept, other = found
        order = (*TIERS, TIER_UNKNOWN)
        result[card] = {
            "stability": round(kept / len(sets), 4) if sets else 1.0,
            "kept": kept,
            "variants": len(sets),
            "alternatives": [
                {"tier": name, "variants": count}
                for name, count in sorted(
                    other.items(), key=lambda entry: (-entry[1], order.index(entry[0]))
                )
            ],
        }
    return result


# ---------- relative tiers inside the pool (an additional view, never the default) ----------

# A SETTING, not a measurement: the percentile rank inside the ranked cards of the group decides
# the relative tier. S is the top 3 %, A up to 10 %, B up to 25 %, C up to 50 %, D up to 75 %,
# E up to 90 %, F the lowest 10 % by rank position. Lands and spells are ranked apart; only ranked
# cards (tier S to D) count; cards with the same index share the tier of the best rank position of
# their group of ties, so F can turn out smaller than 10 %. A group of fewer than
# ``RELATIVE_MIN_GROUP`` ranked cards has no relative tier (a single card would be "F").
RELATIVE_TIER_PERCENTILES: tuple[tuple[str, int], ...] = (
    ("S", 3),
    ("A", 10),
    ("B", 25),
    ("C", 50),
    ("D", 75),
    ("E", 90),
)
RELATIVE_TIER_LAST = "F"
RELATIVE_TIERS = (*(name for name, _percent in RELATIVE_TIER_PERCENTILES), RELATIVE_TIER_LAST)
RELATIVE_TIER_NOTE = "relativ im Pool, keine Aussage über Spielstärke"
RELATIVE_TIER_F_NOTE = (
    "F = die untersten 10 % nach Rangposition; bei Gleichstand teilt die ganze Gruppe die Stufe "
    "der besten Rangposition, daher kann F kleiner ausfallen"
)
RELATIVE_MIN_GROUP = 10
RELATIVE_GROUP_SPELLS = "spells"
RELATIVE_GROUP_LANDS = "lands"


class RelativeRank(TypedDict):
    """Rank ``rank`` of ``total`` ranked cards of the group (``spells`` or ``lands``)."""

    rank: int
    total: int
    group: str


def relative_tier_for(rank: int, total: int) -> str | None:
    """The relative tier of a card at ``rank`` (1 = best) of ``total``: the first tier whose
    percentage covers ``rank / total`` (integer arithmetic, so a limit is exact). ``None`` for a
    group of fewer than ``RELATIVE_MIN_GROUP`` ranked cards."""
    if total < RELATIVE_MIN_GROUP:
        return None
    for name, percent in RELATIVE_TIER_PERCENTILES:
        if rank * 100 <= percent * total:
            return name
    return RELATIVE_TIER_LAST


def relative_tiers(
    entries: Mapping[str, tuple[float, bool]],
) -> dict[str, tuple[str | None, RelativeRank]]:
    """Per card of ``entries`` (card -> (index, is land); only ranked cards) its relative tier and
    ``RelativeRank``. Lands and spells are ranked apart; equal indexes share the best rank of
    their group of ties (competition ranking: 1, 2, 2, 4) and therefore the same tier."""
    result: dict[str, tuple[str | None, RelativeRank]] = {}
    for is_land, group in ((False, RELATIVE_GROUP_SPELLS), (True, RELATIVE_GROUP_LANDS)):
        members = sorted(
            ((index, card) for card, (index, land) in entries.items() if land == is_land),
            key=lambda item: (-item[0], item[1]),
        )
        total = len(members)
        rank = 0
        previous: float | None = None
        for position, (index, card) in enumerate(members, start=1):
            if previous is None or index != previous:
                rank, previous = position, index
            result[card] = (
                relative_tier_for(rank, total),
                {"rank": rank, "total": total, "group": group},
            )
    return result


# ---------- the weight per source family (D2) ----------

# Which source family each component reads from, taken from the code (never from a label); line
# numbers as of #1369:
# - the source-deck corpus: ``deck_universe`` counts the commander's local decks with
#   ``universe_view.spread_for_spec(universe_choice.local_spec(...))`` (strength_view.py:1022, the
#   ``KIND_LOCAL`` branch of ``prepare``); ``corpus_signals.count_corpus`` (corpus_signals.py:126,
#   called at strength_view.py:1043) counts the SAME decks again, once as a whole and once per
#   cohort. ``corpus_log_lift`` takes its numerator from that whole count
#   (corpus_signals.py:168, ``corpus_observations``), ``corpus_tuned`` and the numerator of
#   ``corpus_bracket_slope`` from the bracket 4+5 cohort, the slope's comparison from bracket 2.
#   Nested subsets of the same decks, not independent confirmations.
# - EDHREC pages and themes: ``edhrec_theme_reach`` (strength_view.py:288
#   ``_theme_reach_observations``), ``global_inclusion`` (the stored ``edhrec_global_inclusion``),
#   ``commander_inclusion``, ``bracket_inclusion`` and ``synergy`` (stored EDHREC commander pages,
#   read by ``_signal_observations``, strength_view.py:192).
# - tournament: ``corpus_signals.tournament_observations`` (corpus_signals.py:229, called at
#   strength_view.py:1066) adds EDHTop16 and the corpus bracket 5 (a subset of the source decks)
#   to one n / N (D5).
# - combos: ``_combo_observations`` (strength_view.py:392) / the stored EDHREC combo signal.
# - everything else (Playgroup, rubric, simulation, the TopDeck lists and conversion): other,
#   weight 0 in the defaults.
FAMILY_SOURCE_DECKS = "source_decks"
FAMILY_EDHREC = "edhrec"
FAMILY_TOURNAMENT = "tournament"
FAMILY_COMBOS = "combos"
FAMILY_OTHER = "other"
SOURCE_DECKS_NOTE = "verschachtelte Teilmengen derselben Decks, keine unabhängigen Bestätigungen"
TOURNAMENT_FAMILY_NOTE = (
    "EDHTop16 und Korpus-Bracket 5 (Teilmenge der Quelldecks) zu einem n/N addiert (E3.a)"
)
EDHREC_FAMILY_NOTE = "veröffentlichte EDHREC-Zahlen (Seiten, Themen, Gesamtaufnahme)"
OTHER_FAMILY_NOTE = "Playgroup, Rubrik, Simulation und TopDeck-Listen"
WEIGHT_FAMILIES: tuple[tuple[str, str, tuple[str, ...], str], ...] = (
    (
        FAMILY_SOURCE_DECKS,
        "Quelldeck-Korpus (alle lokalen Decks)",
        (DECK_UNIVERSE, CORPUS_TUNED, CORPUS_LOG_LIFT, CORPUS_BRACKET_SLOPE),
        SOURCE_DECKS_NOTE,
    ),
    (
        FAMILY_EDHREC,
        "EDHREC-Seiten/Themen",
        (EDHREC_THEME_REACH, GLOBAL_INCLUSION, COMMANDER_INCLUSION, BRACKET_INCLUSION, SYNERGY),
        EDHREC_FAMILY_NOTE,
    ),
    (FAMILY_TOURNAMENT, "Turnier", (TOURNAMENT,), TOURNAMENT_FAMILY_NOTE),
    (FAMILY_COMBOS, "Kombos", (COMBOS,), ""),
)


class WeightFamily(TypedDict):
    family: str
    label: str
    components: list[str]
    effective_weight: float
    share_of_total: float
    note: str


def weight_families(settings: StrengthSettings) -> list[WeightFamily]:
    """The effective weight of ``settings`` per source family (D2), as the index uses it: the
    weights after rule E2.a and the bracket switch (field ``effective_weight``).
    ``deck_universe`` counts as source-deck corpus because the index reads the commander's local
    decks (hard-coded: with a stored universe profile or a counted repo universe it would read
    another deck set). Every component belongs to
    exactly one family; ``share_of_total`` is the family weight over the total weight (0 without
    any positive weight). Display only: no weight changes."""
    all_components = COMPONENTS
    named = {name for _key, _label, names, _note in WEIGHT_FAMILIES for name in names}
    rest = tuple(name for name in all_components if name not in named)
    groups = (
        *WEIGHT_FAMILIES,
        (FAMILY_OTHER, "Sonstige (Gewicht 0 im Standard)", rest, OTHER_FAMILY_NOTE),
    )
    weights = {name: settings.effective_weight(name) for name in all_components}
    total = sum(weights.values())
    return [
        {
            "family": key,
            "label": label,
            "components": list(names),
            "effective_weight": round(sum(weights[name] for name in names), 4),
            "share_of_total": round(sum(weights[name] for name in names) / total, 4)
            if total > 0
            else 0.0,
            "note": note,
        }
        for key, label, names, note in groups
    ]


def score_pool(
    settings: StrengthSettings,
    observations: Mapping[str, Mapping[str, Observation]],
    collected: Collection[str],
    *,
    context: PoolContext | None = None,
    diagnostics: dict[str, object] | None = None,
    log_k: float = LOG_SHARE_K,
) -> dict[str, CardStrength]:
    """Index and tier for every card of ``observations`` (card key -> component -> value).

    ``diagnostics`` (optional) is filled with ``shrinkage``: per component the empirical Bayes
    prior (mean, strength, cards) of the shares with a denominator below ``EB_MAX_DENOMINATOR``.
    ``log_k`` is the curvature of the log share scale: always ``LOG_SHARE_K`` except for the
    sensitivity test of the ranking check (k = 100 / 150 / 200).

    ``collected`` names the components that have a source for this commander at all; a
    component outside it is ``NOT_COLLECTED``, one inside it without a value for a card is
    ``NO_VALUE`` (with a reason). The keys of ``observations`` are the commander's legal
    pool: percentile ranks are taken among its ranked cards only (see ``PoolContext``)."""
    ctx = context or PoolContext()
    # two independent switches: one for the commander card and basic lands, one for the
    # other commander cards of the pool
    unranked = {
        key: why
        for key, why in ctx.unranked.items()
        if not (
            settings.rank_other_commanders
            if why == NOT_RANKED_OTHER_COMMANDER
            else settings.rank_commander_and_basics
        )
    }
    filter_cards = frozenset(ctx.filter_cards)
    rated = COMPONENTS
    rankings: dict[str, _ComponentRanking] = {}
    for component in rated:
        skipped = set(unranked) | (filter_cards if component == DECK_UNIVERSE else set())
        rankings[component] = _rank_component(
            settings, ctx, component, observations, skipped, log_k
        )
    # Components with a weight and usable data FOR THIS COMMANDER (collected, and at least one
    # usable value in the pool): decides the reason ``NO_SOURCE_FOR_COMMANDER`` only.
    commander_weight = {
        name: settings.effective_weight(name)
        for name in rated
        if settings.effective_weight(name) > 0 and name in collected and rankings[name].usable
    }
    # The coverage denominator stays main's rule (Owner-visible numbers such as "4 of 13"): every
    # weighted component counts, except the by-design uncollected ones that were not
    # collected. A source never imported still counts against a card.
    denominator_weight = {
        name: settings.effective_weight(name)
        for name in rated
        if settings.effective_weight(name) > 0
        and not (
            (name in UNCOLLECTED_BY_DESIGN or name in COMMANDER_ONLY_SOURCES)
            and name not in collected
        )
    }
    any_positive_weight = any(settings.effective_weight(name) > 0 for name in rated)
    if diagnostics is not None:
        diagnostics["shrinkage"] = {
            name: ranking.prior.to_dict()
            for name, ranking in rankings.items()
            if ranking.prior is not None and settings.effective_weight(name) > 0
        }
    tier_inputs: dict[str, TierInputs] | None = None
    if diagnostics is not None:
        tier_inputs = {}
        diagnostics["tier_inputs"] = tier_inputs
    result: dict[str, CardStrength] = {}
    for card, per_card in observations.items():
        components: list[ComponentResult] = []
        present_weight = 0.0
        weighted = 0.0
        present = 0
        present_rows: list[tuple[str, float]] = []
        specific = False
        specific_positive = False
        not_ranked = unranked.get(card)
        for component in rated:
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
                if (
                    component in ZERO_COUNT_COMPONENTS
                    and observation is not None
                    and observation.numerator == 0
                ):
                    status, reason = ZERO_COUNT, ZERO_COUNT
                percentile = ranking.pool_ranks[card]
                if settings.rank_group != GROUP_POOL:
                    found = ranking.group_ranks.get(card)
                    if found is not None:
                        names, sizes, group_percentile = found
                        group = " + ".join(names)
                        group_size = sizes[names[0]] if len(names) == 1 else None
                        percentile = group_percentile
                    else:
                        group = " + ".join(_groups_of(settings, ctx, card)) or None
                        group_fallback = True
                elif card in ranking.land_split:
                    group, group_size, group_fallback = ranking.land_split[card]
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
                present_rows.append((component, percentile))
            note = _component_note(reason, ranking, observation) if reason else ""
            if status == PRESENT and card in ranking.shrunk and ranking.prior is not None:
                note = (
                    f"Anteil bei kleinem Nenner ({observation.denominator if observation else '?'}"
                    f" Decks) zum Prior gezogen (empirisches Bayes, Prior-Mittel "
                    f"{ranking.prior.mean:.4f}, Stärke {ranking.prior.strength:.1f})"
                )
            if status == PRESENT and observation is not None and observation.note:
                note = observation.note
            if (
                percentile is not None
                and weight > 0
                and is_commander_specific(component, settings.combo_source)
                and status in (PRESENT, ZERO_COUNT)
            ):
                # MISSING_AS_LOWEST counts as a value for the index and the coverage, but a
                # card the commander's lists do not name is no evidence about this commander
                specific = True
                if status == PRESENT:
                    specific_positive = True
            if group_fallback and settings.rank_group == GROUP_POOL:
                note = (
                    f"Vergleichsgruppe „{group}“ hat nur {group_size} Karten mit Wert "
                    f"(weniger als {MIN_GROUP}): Rang im ganzen Pool (Länder und Zauber zusammen)"
                )
            elif group_fallback:
                note = _fallback_note(group, ranking, settings, ctx, card)
            components.append(
                {
                    "component": component,
                    "label": component_label(component, combo_source=settings.combo_source),
                    "signal": signal_for(
                        component,
                        settings.bracket,
                        combo_source=settings.combo_source,
                        spellbook_shells=ctx.spellbook_shells,
                    ),
                    "status": status,
                    "reason": GROUP_TOO_SMALL if group_fallback else reason,
                    "note": note,
                    "value": observation.value if observation else None,
                    "numerator": observation.numerator if observation else None,
                    "denominator": observation.denominator if observation else None,
                    "wilson": ranking.wilson.get(card) if status in (PRESENT, ZERO_COUNT) else None,
                    "shrunk": ranking.shrunk.get(card) if status in (PRESENT, ZERO_COUNT) else None,
                    "prior_mean": (
                        ranking.prior.mean
                        if ranking.prior is not None and card in ranking.shrunk
                        else None
                    ),
                    "prior_strength": (
                        ranking.prior.strength
                        if ranking.prior is not None and card in ranking.shrunk
                        else None
                    ),
                    "data_class": COMPONENT_DATA_CLASS.get(component, DATA_CLASS),
                    "percentile": percentile,
                    "weight": weight,
                    "min_denominator": ranking.minimum,
                    "group": group,
                    "group_size": group_size,
                    "group_fallback": group_fallback,
                    "parts": _component_parts(observation, status),
                    "mixed_cohorts_note": _mixed_cohorts_note(observation, status),
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
                "confidence": None,
                "confidence_level": None,
                "borderline": False,
                "borderline_cut": None,
                "cut_distance": None,
                "confidence_by_denominator": None,
                "confidence_by_denominator_level": None,
                "zero_count_thin": [],
                "confidence_basis": None,
            }
            continue
        # A filter card has no deck-universe value by definition: that component is not
        # applicable to it and leaves its denominator.
        possible = {
            name: weight
            for name, weight in denominator_weight.items()
            if not (name == DECK_UNIVERSE and card in filter_cards)
        }
        total_weight = sum(possible.values())
        coverage = present_weight / total_weight if total_weight > 0 else 0.0
        index = round(100.0 * weighted / present_weight, 1) if present_weight > 0 else None
        # The minimum number of signals never exceeds the number of weighted components of
        # this card: a profile with one positive weight cannot show two signals.
        needed = min(settings.min_components, len(possible))
        enough = present > 0 and coverage >= settings.min_coverage and present >= needed
        blocked = settings.require_commander_signal and not specific
        # E4.a: the only evidence about this commander is counted zeros (0 of N): too little data
        zero_only = settings.zero_count_tier == ZERO_TIER_U and specific and not specific_positive
        if not any_positive_weight:
            reason_code = "NO_POSITIVE_WEIGHT"
        elif not commander_weight:
            reason_code = "NO_SOURCE_FOR_COMMANDER"
        elif blocked:
            reason_code = NO_COMMANDER_SIGNAL
        elif zero_only:
            reason_code = ZERO_COUNT_ONLY
        else:
            reason_code = "ENOUGH_DATA" if enough else "TOO_LITTLE_DATA"
        if reason_code in ("NO_POSITIVE_WEIGHT", "NO_SOURCE_FOR_COMMANDER"):
            enough = False
        tier = _tier(index, settings, enough and not blocked and not zero_only)
        # confidence describes a tier; a card without one (U, N) has no confidence to show
        confidence = (
            confidence_value(coverage, components) if index is not None and tier in TIERS else None
        )
        # a card without a tier (U) is not near a cut: it has no tier to change
        borderline, cut_tier, cut_gap = borderline_info(
            index if tier in TIERS else None, settings.tier_cuts, settings.borderline_distance
        )
        if tier_inputs is not None and tier in TIERS:
            tier_inputs[card] = TierInputs(tuple(present_rows), tuple(possible), needed)
        result[card] = {
            "index": index,
            "coverage": round(coverage, 4),
            # the tier follows the index as shown (rounded to one decimal)
            "tier": tier,
            "reason": reason_code,
            "note": {
                NO_COMMANDER_SIGNAL: NO_COMMANDER_SIGNAL_NOTE,
                ZERO_COUNT_ONLY: ZERO_COUNT_ONLY_NOTE,
            }.get(reason_code, ""),
            "present": present,
            "components": components,
            "confidence": confidence,
            "confidence_level": confidence_level(confidence) if confidence is not None else None,
            "borderline": borderline,
            "borderline_cut": cut_tier,
            "cut_distance": cut_gap,
            "confidence_by_denominator": (
                confidence_by_denominator_value(coverage, components)
                if index is not None and tier in TIERS
                else None
            ),
            "confidence_by_denominator_level": (
                confidence_level(confidence_by_denominator_value(coverage, components))
                if index is not None and tier in TIERS
                else None
            ),
            "zero_count_thin": (
                zero_count_thin_components(components)
                if index is not None and tier in TIERS
                else []
            ),
            "confidence_basis": (
                confidence_basis(components) if index is not None and tier in TIERS else None
            ),
        }
    return result


def _fallback_note(
    group: str | None,
    ranking: _ComponentRanking,
    settings: StrengthSettings,
    context: PoolContext,
    card: str,
) -> str:
    groups = _groups_of(settings, context, card)
    if settings.rank_group == GROUP_FUNCTION and not groups:
        return "Keine Funktion bekannt (keine Rolle aus den Quellen belegt): Rang im ganzen Pool"
    # a comparison group never mixes lands and spells while ``separate_lands`` is on
    same_kind = [
        other
        for other in ranking.values
        if not settings.separate_lands or _is_land(context, other) == _is_land(context, card)
    ]
    if groups:
        size = max(
            sum(1 for other in same_kind if name in _groups_of(settings, context, other))
            for name in groups
        )
    else:
        size = sum(1 for other in same_kind if not _groups_of(settings, context, other))
    name = group or "ohne Gruppe"
    return (
        f"Vergleichsgruppe „{name}“ hat nur {size} Karten mit Wert (weniger als {MIN_GROUP}): "
        "Rang im ganzen Pool"
    )
