"""Objective quality checks for a strength-index ranking (issue #1349).

``check_ranking`` is a pure function: it takes ``StrengthSettings``, per-card observations,
the set of collected components, card names and ``PoolContext``, and returns the six
objective diagnostic figures defined in #1349:

1. **Agreement with the counted deck lists (Spearman rank correlation)** between the
   strength index and the card's share in the counted lists of the commander, over all
   ranked cards and separately for non-lands (and lands). Because the counted lists are
   themselves one component of the index, this figure is explicitly labelled as a
   plausibility anchor ("wird für diesen Commander wirklich gespielt"), never as a proof
   of causal card strength.
2. **Marginal cards at the top ("Randkarten oben"):** cards in tier ``S`` or ``A`` whose
   share in the counted lists is below 5 % (count, denominator = all cards in ``S`` or ``A``,
   and card names).
3. **Staples at the bottom ("Stammkarten unten"):** cards with more than 30 % share in the
   counted lists that stand in tier ``C`` or ``D`` (count, denominator = all cards above
   30 % share, and card names).
4. **Thin data coverage at the top ("Dünne Datenlage oben"):** cards in tier ``S`` or ``A``
   with fewer than 5 present weighted signals (count, denominator = all cards in ``S`` or
   ``A``, breakdown by signal count, and card names).
5. **Tier distribution ("Stufen-Verteilung"):** per tier (``S, A, B, C, D, U, N``) the card
   count, the pool denominator, the land and non-land counts, and the land share (``None``
   when a tier holds 0 cards).
6. **Leave-one-out stability ("Stabilität"):** for every active weighted signal, how many
   cards change tier when that signal alone is given weight 0, plus the single signal with
   the largest impact.

Since #1364 (Tierliste v3) the report adds, measured and never tuned to a card:

7. **Counter-checks (Gegenproben):** Spearman correlation of the index with the card's share in
   the corpus bracket-5 decks and with the EDHTop16 play rate, each over all ranked cards, over
   spells and over lands. Both OVERLAP with the index (bracket 5 is a subset of the corpus and
   feeds the tournament signal, EDHTop16 feeds the tournament signal), so each also carries a
   held-out variant: the index recomputed with the overlapping components at weight 0
   (``COUNTER_OVERLAP``) against the same reference.
8. **Redundancy matrix:** Spearman correlation between the active weighted components over the
   cards where both have a value; a pair above ``REDUNDANCY_THRESHOLD`` (0.90) is flagged: two
   signals that say the same thing count twice.
9. **Sensitivity of the log share scale:** tier counts, tier changes against the default and the
   agreement with the counted lists for k = 100 / 150 / 200 (the default is 150).

The report also carries the E2.a weight rule that applied and the empirical Bayes priors.

No target ranks are set by an agent. Owner marks (favorites, exclusions, notes) and
simulation results never enter this check.
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from dataclasses import replace
from typing import TypedDict

from . import corpus_signals, strength, strength_view, tier_snapshot, universe_choice, universe_view
from .store import LEGACY_COMMANDER, StudioStore
from .strength import (
    DECK_UNIVERSE,
    TIERS,
    CardStrength,
    Observation,
    PoolContext,
    StrengthSettings,
)

SCHEMA = "studio-ranking-check-1"
ALL_TIERS = (*TIERS, strength.TIER_UNKNOWN, strength.TIER_NOT_RANKED)
TOP_TIERS = ("S", "A")
BOTTOM_TIERS = ("C", "D")
MARGINAL_MAX_SHARE = 0.05
STAPLE_MIN_SHARE = 0.30
MIN_STRONG_SIGNALS = 5
REDUNDANCY_THRESHOLD = 0.90
SENSITIVITY_KS = (100.0, 150.0, 200.0)
COUNTER_NOTE = (
    "Gegenprobe (überlappend): die Referenz ist Teil der Daten des Index (Bracket 5 steckt im "
    "Korpus und im Turnier-Signal, EDHTop16 im Turnier-Signal), die Zahl ist also nicht "
    "unabhängig. Die Zeile „ohne Überlappung“ rechnet den Index mit den überlappenden "
    "Komponenten auf Gewicht 0 neu und ist die ausgehaltene Gegenprobe; kein Beweis für Stärke."
)
# Components that share data with a counter reference: they are set to weight 0 for the
# held-out variant of the counter-check.
COUNTER_OVERLAP: dict[str, tuple[str, ...]] = {
    "bracket_5": (
        strength.DECK_UNIVERSE,
        strength.CORPUS_TUNED,
        strength.TOURNAMENT,
        strength.CORPUS_BRACKET_SLOPE,
    ),
    "edhtop16": (strength.TOURNAMENT,),
}
REDUNDANCY_NOTE = (
    "Spearman zwischen den Rang-Werten zweier aktiver Komponenten über die Karten, bei denen "
    f"beide einen Wert haben. r > {REDUNDANCY_THRESHOLD:.2f} heißt: das Signal zählt doppelt."
)
SENSITIVITY_NOTE = (
    "Stufen bei anderer Krümmung k der Log-Skala ln(1 + k·Anteil) / ln(1 + k·Maximum); der "
    "Standard ist k = 150, Stufen-Grenzen bleiben unverändert."
)

PLAUSIBILITY_ANCHOR_NOTE = (
    "Plausibilitäts-Anker („wird für diesen Commander wirklich gespielt“), kein Beweis "
    "für Stärke: die gezählten Listen sind selbst ein Signal des Index."
)


class CorrelationEntry(TypedDict):
    spearman_rho: float | None
    compared: int
    of_ranked: int


class SpearmanBlock(TypedDict):
    note: str
    counted_lists_label: str
    denominator: int | None
    all_ranked: CorrelationEntry
    non_lands: CorrelationEntry
    lands: CorrelationEntry


class ShareCardEntry(TypedDict):
    card_id: str
    name: str
    tier: str
    index: float | None
    numerator: int | None
    denominator: int | None
    share: float


class MarginalTopBlock(TypedDict):
    threshold_max_share: float
    count: int
    of_s_and_a: int
    names: list[str]
    cards: list[ShareCardEntry]


class StaplesBottomBlock(TypedDict):
    threshold_min_share: float
    count: int
    of_staples: int
    names: list[str]
    cards: list[ShareCardEntry]


class ThinCoverageTopBlock(TypedDict):
    min_signals: int
    count: int
    of_s_and_a: int
    by_signal_count: dict[str, int]
    names: list[str]


class TierRow(TypedDict):
    tier: str
    count: int
    of_pool: int
    lands: int
    non_lands: int
    land_share: float | None


class SignalStabilityRow(TypedDict):
    component: str
    label: str
    weight: float
    tier_changes: int
    of_pool: int


class StabilityBlock(TypedDict):
    signals: list[SignalStabilityRow]
    largest_impact: SignalStabilityRow | None


class HeldOutCheck(TypedDict):
    """The counter-check with the components that share data with the reference at weight 0."""

    zeroed: list[str]
    all_ranked: CorrelationEntry
    non_lands: CorrelationEntry
    lands: CorrelationEntry


class CounterCheck(TypedDict):
    """Agreement of the index with one overlapping reference share (``bracket_5``,
    ``edhtop16``) and, held out, without the overlapping components; the denominator is the
    reference's largest denominator."""

    key: str
    label: str
    denominator: int | None
    note: str
    all_ranked: CorrelationEntry
    non_lands: CorrelationEntry
    lands: CorrelationEntry
    held_out: HeldOutCheck | None


class RedundancyPair(TypedDict):
    a: str
    b: str
    spearman_rho: float | None
    compared: int
    flagged: bool


class RedundancyBlock(TypedDict):
    threshold: float
    note: str
    components: list[str]
    pairs: list[RedundancyPair]
    flagged: list[RedundancyPair]


class SensitivityRun(TypedDict):
    k: float
    tier_counts: dict[str, int]
    tier_changes_vs_base: int
    spearman_all_ranked: float | None
    spearman_non_lands: float | None
    spearman_lands: float | None


class SensitivityBlock(TypedDict):
    base_k: float
    note: str
    runs: list[SensitivityRun]


class RankingCheckReport(TypedDict):
    schema: str
    commander: str
    profile_or_preset: str
    pool_size: int
    ranked_count: int
    spearman: SpearmanBlock
    marginal_top: MarginalTopBlock
    staples_bottom: StaplesBottomBlock
    thin_coverage_top: ThinCoverageTopBlock
    tier_distribution: list[TierRow]
    stability: StabilityBlock
    counter_checks: list[CounterCheck]
    redundancy: RedundancyBlock
    sensitivity: SensitivityBlock | None
    weight_rule: strength.WeightRule | None
    shrinkage: dict[str, object]
    tier_snapshot: dict[str, object] | None


def _counted_share(observation: Observation | None) -> float | None:
    """The raw share 0..1 of a counted-list observation, or ``None`` when unknown."""
    if observation is None:
        return None
    if observation.numerator is not None and observation.denominator is not None:
        if observation.denominator <= 0 or not (
            0 <= observation.numerator <= observation.denominator
        ):
            return None
        return observation.numerator / observation.denominator
    if (
        observation.value is not None
        and math.isfinite(observation.value)
        and 0.0 <= observation.value <= 1.0
    ):
        return float(observation.value)
    return None


def spearman_correlation(
    first: Mapping[str, float],
    second: Mapping[str, float],
) -> float | None:
    """Spearman rank correlation (-1..1) over keys present in both mappings.

    Ties receive their average rank via ``strength.percentile_ranks``. Returns ``None``
    when fewer than two keys are shared or when either side is constant (zero variance).
    """
    shared = [key for key in first if key in second]
    count = len(shared)
    if count < 2:
        return None
    ranks_x = strength.percentile_ranks({key: first[key] for key in shared})
    ranks_y = strength.percentile_ranks({key: second[key] for key in shared})
    mean_x = sum(ranks_x.values()) / count
    mean_y = sum(ranks_y.values()) / count
    cov = sum((ranks_x[key] - mean_x) * (ranks_y[key] - mean_y) for key in shared)
    var_x = sum((ranks_x[key] - mean_x) ** 2 for key in shared)
    var_y = sum((ranks_y[key] - mean_y) ** 2 for key in shared)
    if var_x <= 0.0 or var_y <= 0.0:
        return None
    return round(cov / math.sqrt(var_x * var_y), 4)


def _without_component(settings: StrengthSettings, component: str) -> StrengthSettings:
    """Copy of ``settings`` with ``component``'s weight set to 0.0."""
    return replace(settings, weights={**settings.weights, component: 0.0})


def check_ranking(
    settings: StrengthSettings,
    observations: Mapping[str, Mapping[str, Observation]],
    collected: Collection[str],
    *,
    names: Mapping[str, str] | None = None,
    context: PoolContext | None = None,
    counted_lists: Mapping[str, Observation] | None = None,
    counted_lists_label: str = "",
    commander: str = "",
    profile_or_preset: str = "Standard",
    scored: Mapping[str, CardStrength] | None = None,
    counter_shares: Mapping[str, tuple[str, Mapping[str, Observation]]] | None = None,
    weight_rule: strength.WeightRule | None = None,
) -> RankingCheckReport:
    """Pure diagnostic check of a strength-index ranking: the six #1349 metrics plus the
    counter-checks, the redundancy matrix and the log-scale sensitivity of #1364.

    ``counter_shares`` maps a key to ``(label, observations)`` of an overlapping reference share
    (the corpus bracket 5, EDHTop16). ``weight_rule`` is the E2.a rule that applied."""
    ctx = context or PoolContext()
    display = {card: (names[card] if names and card in names else card) for card in observations}
    diagnostics: dict[str, object] = {}
    base_scored = (
        dict(scored)
        if scored is not None
        else strength.score_pool(
            settings, observations, collected, context=ctx, diagnostics=diagnostics
        )
    )
    if counted_lists is None:
        counted: Mapping[str, Observation] = {
            card: obs
            for card, per_card in observations.items()
            if (obs := per_card.get(DECK_UNIVERSE)) is not None
        }
    else:
        counted = counted_lists

    denominators = [
        obs.denominator
        for obs in counted.values()
        if obs.denominator is not None and obs.denominator > 0
    ]
    ref_denominator = max(denominators) if denominators else None

    shares: dict[str, float] = {}
    for card in observations:
        share = _counted_share(counted.get(card))
        if share is not None:
            shares[card] = share

    ranked_indices: dict[str, float] = {
        card: float(item["index"])
        for card, item in base_scored.items()
        if item["tier"] in TIERS and item["index"] is not None
    }
    non_land_indices: dict[str, float] = {
        card: idx for card, idx in ranked_indices.items() if ctx.type_group.get(card) != "Land"
    }
    land_indices: dict[str, float] = {
        card: idx for card, idx in ranked_indices.items() if ctx.type_group.get(card) == "Land"
    }

    all_shared = sum(1 for card in ranked_indices if card in shares)
    non_land_shared = sum(1 for card in non_land_indices if card in shares)
    land_shared = sum(1 for card in land_indices if card in shares)

    def _entry(indices: Mapping[str, float], other: Mapping[str, float]) -> CorrelationEntry:
        return {
            "spearman_rho": spearman_correlation(indices, other),
            "compared": sum(1 for card in indices if card in other),
            "of_ranked": len(indices),
        }

    spearman_block: SpearmanBlock = {
        "note": PLAUSIBILITY_ANCHOR_NOTE,
        "counted_lists_label": counted_lists_label,
        "denominator": ref_denominator,
        "all_ranked": {
            "spearman_rho": spearman_correlation(ranked_indices, shares),
            "compared": all_shared,
            "of_ranked": len(ranked_indices),
        },
        "non_lands": {
            "spearman_rho": spearman_correlation(non_land_indices, shares),
            "compared": non_land_shared,
            "of_ranked": len(non_land_indices),
        },
        "lands": {
            "spearman_rho": spearman_correlation(land_indices, shares),
            "compared": land_shared,
            "of_ranked": len(land_indices),
        },
    }

    top_cards = [card for card, item in base_scored.items() if item["tier"] in TOP_TIERS]
    top_cards.sort(
        key=lambda card: (
            -(base_scored[card]["index"] or 0.0),
            display[card],
            card,
        )
    )
    marginal_cards: list[ShareCardEntry] = []
    for card in top_cards:
        share = shares.get(card)
        if share is None or share >= MARGINAL_MAX_SHARE:
            continue
        obs = counted.get(card)
        marginal_cards.append(
            {
                "card_id": card,
                "name": display[card],
                "tier": base_scored[card]["tier"],
                "index": base_scored[card]["index"],
                "numerator": obs.numerator if obs else None,
                "denominator": obs.denominator if obs else None,
                "share": round(share, 4),
            }
        )

    staple_cards = [card for card, share in shares.items() if share > STAPLE_MIN_SHARE]
    staple_cards.sort(key=lambda card: (-shares[card], display[card], card))
    staples_bottom_cards: list[ShareCardEntry] = []
    for card in staple_cards:
        item = base_scored.get(card)
        if item is None or item["tier"] not in BOTTOM_TIERS:
            continue
        obs = counted.get(card)
        staples_bottom_cards.append(
            {
                "card_id": card,
                "name": display[card],
                "tier": item["tier"],
                "index": item["index"],
                "numerator": obs.numerator if obs else None,
                "denominator": obs.denominator if obs else None,
                "share": round(shares[card], 4),
            }
        )

    thin_cards = [card for card in top_cards if base_scored[card]["present"] < MIN_STRONG_SIGNALS]
    by_present = Counter(base_scored[card]["present"] for card in top_cards)
    thin_block: ThinCoverageTopBlock = {
        "min_signals": MIN_STRONG_SIGNALS,
        "count": len(thin_cards),
        "of_s_and_a": len(top_cards),
        "by_signal_count": {str(k): by_present[k] for k in sorted(by_present)},
        "names": [display[card] for card in thin_cards],
    }

    pool_size = len(observations)
    tier_rows: list[TierRow] = []
    for tier in ALL_TIERS:
        in_tier = [card for card, item in base_scored.items() if item["tier"] == tier]
        count = len(in_tier)
        lands = sum(1 for card in in_tier if ctx.type_group.get(card) == "Land")
        tier_rows.append(
            {
                "tier": tier,
                "count": count,
                "of_pool": pool_size,
                "lands": lands,
                "non_lands": count - lands,
                "land_share": round(lands / count, 4) if count > 0 else None,
            }
        )

    rated_components = strength.COMPONENTS
    stability_rows: list[SignalStabilityRow] = []
    for component in rated_components:
        weight = settings.effective_weight(component)
        if weight <= 0.0 or component not in collected:
            continue
        reduced = _without_component(settings, component)
        reduced_scored = strength.score_pool(reduced, observations, collected, context=ctx)
        changed = sum(
            1 for card in observations if reduced_scored[card]["tier"] != base_scored[card]["tier"]
        )
        stability_rows.append(
            {
                "component": component,
                "label": strength.component_label(component, combo_source=settings.combo_source),
                "weight": weight,
                "tier_changes": changed,
                "of_pool": pool_size,
            }
        )
    largest_impact = (
        max(stability_rows, key=lambda row: row["tier_changes"]) if stability_rows else None
    )

    counter_checks: list[CounterCheck] = []
    for key, (label, reference) in (counter_shares or {}).items():
        reference_shares = {
            card: share
            for card in observations
            if (share := _counted_share(reference.get(card))) is not None
        }
        reference_denominators = [
            obs.denominator
            for obs in reference.values()
            if obs.denominator is not None and obs.denominator > 0
        ]
        held_out: HeldOutCheck | None = None
        zeroed = [
            name for name in COUNTER_OVERLAP.get(key, ()) if settings.effective_weight(name) > 0
        ]
        if zeroed:
            held_settings = settings
            for name in zeroed:
                held_settings = _without_component(held_settings, name)
            held_scored = strength.score_pool(held_settings, observations, collected, context=ctx)
            held_all = {
                card: float(item["index"])
                for card, item in held_scored.items()
                if item["tier"] in TIERS and item["index"] is not None
            }
            held_non_lands = {
                card: idx for card, idx in held_all.items() if ctx.type_group.get(card) != "Land"
            }
            held_lands = {
                card: idx for card, idx in held_all.items() if ctx.type_group.get(card) == "Land"
            }
            held_out = {
                "zeroed": zeroed,
                "all_ranked": _entry(held_all, reference_shares),
                "non_lands": _entry(held_non_lands, reference_shares),
                "lands": _entry(held_lands, reference_shares),
            }
        counter_checks.append(
            {
                "key": key,
                "label": label,
                "denominator": max(reference_denominators) if reference_denominators else None,
                "note": COUNTER_NOTE,
                "all_ranked": _entry(ranked_indices, reference_shares),
                "non_lands": _entry(non_land_indices, reference_shares),
                "lands": _entry(land_indices, reference_shares),
                "held_out": held_out,
            }
        )

    redundancy = _redundancy(settings, collected, base_scored)
    sensitivity = _sensitivity(settings, observations, collected, ctx, base_scored, shares)
    shrinkage = diagnostics.get("shrinkage")

    return {
        "schema": SCHEMA,
        "commander": commander,
        "profile_or_preset": profile_or_preset,
        "pool_size": pool_size,
        "ranked_count": len(ranked_indices),
        "spearman": spearman_block,
        "marginal_top": {
            "threshold_max_share": MARGINAL_MAX_SHARE,
            "count": len(marginal_cards),
            "of_s_and_a": len(top_cards),
            "names": [entry["name"] for entry in marginal_cards],
            "cards": marginal_cards,
        },
        "staples_bottom": {
            "threshold_min_share": STAPLE_MIN_SHARE,
            "count": len(staples_bottom_cards),
            "of_staples": len(staple_cards),
            "names": [entry["name"] for entry in staples_bottom_cards],
            "cards": staples_bottom_cards,
        },
        "thin_coverage_top": thin_block,
        "tier_distribution": tier_rows,
        "stability": {
            "signals": stability_rows,
            "largest_impact": largest_impact,
        },
        "counter_checks": counter_checks,
        "redundancy": redundancy,
        "sensitivity": sensitivity,
        "weight_rule": weight_rule,
        "shrinkage": dict(shrinkage) if isinstance(shrinkage, dict) else {},
        "tier_snapshot": None,
    }


def _redundancy(
    settings: StrengthSettings,
    collected: Collection[str],
    scored: Mapping[str, CardStrength],
) -> RedundancyBlock:
    """Spearman between the rank values of every two active weighted components over the cards
    where both have a value. Only counted values enter (a value filled in for a missing card,
    ``MISSING_AS_LOWEST``, is not an observation)."""
    active = [
        name
        for name in strength.COMPONENTS
        if settings.effective_weight(name) > 0 and name in collected
    ]
    values: dict[str, dict[str, float]] = {name: {} for name in active}
    for card, item in scored.items():
        for row in item["components"]:
            percentile = row["percentile"]
            if (
                row["component"] in values
                and percentile is not None
                and row["status"] in (strength.PRESENT, strength.ZERO_COUNT)
            ):
                values[row["component"]][card] = percentile
    pairs: list[RedundancyPair] = []
    for index, first in enumerate(active):
        for second in active[index + 1 :]:
            rho = spearman_correlation(values[first], values[second])
            pairs.append(
                {
                    "a": first,
                    "b": second,
                    "spearman_rho": rho,
                    "compared": sum(1 for card in values[first] if card in values[second]),
                    "flagged": rho is not None and rho > REDUNDANCY_THRESHOLD,
                }
            )
    return {
        "threshold": REDUNDANCY_THRESHOLD,
        "note": REDUNDANCY_NOTE,
        "components": active,
        "pairs": pairs,
        "flagged": [pair for pair in pairs if pair["flagged"]],
    }


def _sensitivity(
    settings: StrengthSettings,
    observations: Mapping[str, Mapping[str, Observation]],
    collected: Collection[str],
    context: PoolContext,
    base_scored: Mapping[str, CardStrength],
    shares: Mapping[str, float],
) -> SensitivityBlock | None:
    """Tier counts and agreement for the curvature k of the log share scale, ``None`` for any
    other scale. The default k reuses the base scoring."""
    if settings.share_scale != strength.SCALE_LOG:
        return None
    runs: list[SensitivityRun] = []
    for k in SENSITIVITY_KS:
        scored = (
            base_scored
            if k == strength.LOG_SHARE_K
            else strength.score_pool(settings, observations, collected, context=context, log_k=k)
        )
        counts = Counter(item["tier"] for item in scored.values())
        indices = {
            card: float(item["index"])
            for card, item in scored.items()
            if item["tier"] in TIERS and item["index"] is not None
        }
        runs.append(
            {
                "k": k,
                "tier_counts": {tier: counts.get(tier, 0) for tier in ALL_TIERS},
                "tier_changes_vs_base": sum(
                    1 for card in scored if scored[card]["tier"] != base_scored[card]["tier"]
                ),
                "spearman_all_ranked": spearman_correlation(indices, shares),
                "spearman_non_lands": spearman_correlation(
                    {c: v for c, v in indices.items() if context.type_group.get(c) != "Land"},
                    shares,
                ),
                "spearman_lands": spearman_correlation(
                    {c: v for c, v in indices.items() if context.type_group.get(c) == "Land"},
                    shares,
                ),
            }
        )
    return {"base_k": strength.LOG_SHARE_K, "note": SENSITIVITY_NOTE, "runs": runs}


def _reference_counted_lists(
    store: StudioStore,
    commander: str,
    ids: list[str],
    display: Mapping[str, str],
) -> tuple[dict[str, Observation], str]:
    """Counted deck-list observations for ``commander`` as plausibility anchor."""
    choice = universe_choice.choose(store, commander, StrengthSettings(), None)
    if choice["kind"] == universe_choice.KIND_LOCAL:
        local_total, _snapshot, local_cards = universe_view.spread_for_spec(
            store, universe_choice.local_spec(store, commander), ids, commander_names=[commander]
        )
        if local_total > 0:
            per_card: dict[str, dict[str, Observation]] = {card_id: {} for card_id in ids}
            strength_view._fill_spread(per_card, set(), local_cards)
            return (
                {
                    card_id: obs
                    for card_id, per in per_card.items()
                    if (obs := per.get(DECK_UNIVERSE)) is not None
                },
                choice["label"],
            )
    if choice["kind"] == universe_choice.KIND_COUNTED:
        claims = strength_view._claim_index(store, ids)
        for item in universe_choice.counted_universes(store, commander):
            if item["value"] == choice["counted"]:
                return (
                    strength_view.counted_observations(store, commander, item, claims, display, {}),
                    choice["label"],
                )
    return {}, choice["label"]


def run_ranking_check(
    store: StudioStore,
    commander: str,
    *,
    profile: str | None = None,
    preset: str | None = None,
    settings: Mapping[str, object] | None = None,
) -> RankingCheckReport:
    """Compute the #1349 ranking check against ``store`` for ``commander``. The observations,
    the corpus rule (E2.a) and the settings are exactly those of the tier list
    (``strength_view.prepare``)."""
    resolved = strength_view.resolve_settings(
        store, preset=preset, profile=profile, settings=settings
    )
    label = profile or preset or "Ausgewogen"
    prepared = strength_view.prepare(store, commander, resolved, dangling_universe_ok=True)
    ids = prepared.ids
    display = prepared.display
    per_card = prepared.per_card
    if DECK_UNIVERSE in prepared.collected and prepared.choice["kind"] in (
        universe_choice.KIND_LOCAL,
        universe_choice.KIND_COUNTED,
    ):
        counted_lists = {
            card_id: obs
            for card_id, per in per_card.items()
            if (obs := per.get(DECK_UNIVERSE)) is not None
        }
        counted_label = prepared.choice["label"]
    else:
        counted_lists, counted_label = _reference_counted_lists(store, commander, ids, display)

    counter_shares: dict[str, tuple[str, Mapping[str, Observation]]] = {}
    if prepared.corpus_counts is not None:
        group = prepared.corpus_counts.groups[corpus_signals.KEY_TOURNAMENT]
        if group.denominator > 0:
            counter_shares["bracket_5"] = (
                f"Korpus {group.label} (Anteil, Nenner {group.denominator})",
                {
                    card_id: Observation(hits / group.denominator, hits, group.denominator)
                    for card_id, hits in group.hits.items()
                },
            )
    if prepared.edhtop16:
        counter_shares["edhtop16"] = ("EDHTop16-Spielrate", prepared.edhtop16)

    report = check_ranking(
        prepared.effective,
        per_card,
        prepared.collected,
        names=display,
        context=prepared.context,
        counted_lists=counted_lists,
        counted_lists_label=counted_label,
        commander=commander,
        profile_or_preset=label,
        counter_shares=counter_shares,
        weight_rule=prepared.weight_rule,
    )
    report["tier_snapshot"] = tier_snapshot.latest_snapshot_summary(store, commander)
    return report


def _fmt_rho(value: float | None) -> str:
    return "unbekannt" if value is None else f"{value:.4f}"


def _fmt_pct(value: float | None) -> str:
    return "unbekannt" if value is None else f"{value * 100:.1f} %"


def _table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    cells = [[str(item) for item in row] for row in rows]
    widths = [
        max(len(h), *(len(row[i]) for row in cells)) if cells else len(h)
        for i, h in enumerate(headers)
    ]

    def line(items: Sequence[str]) -> str:
        return "  ".join(item.ljust(widths[i]) for i, item in enumerate(items)).rstrip()

    return "\n".join([line(headers), line(["-" * w for w in widths]), *(line(r) for r in cells)])


def render_ranking_check(report: RankingCheckReport) -> str:
    """Format a ``RankingCheckReport`` as a concise German diagnostic text report."""
    sp = report["spearman"]
    denom_txt = (
        f"Nenner {sp['denominator']}" if sp["denominator"] is not None else "Nenner unbekannt"
    )
    marginal = report["marginal_top"]
    staples = report["staples_bottom"]
    thin = report["thin_coverage_top"]
    stab = report["stability"]
    largest = stab["largest_impact"]

    lines: list[str] = [
        f"Prüfzahlen für die Rangfolge: {report['commander']} ({report['profile_or_preset']})",
        f"Pool: {report['pool_size']} Karten, gerankt (S bis D): {report['ranked_count']} Karten",
        "",
        f"1. Übereinstimmung mit den gezählten Listen ({denom_txt})",
        f"   Hinweis: {sp['note']}",
        f"   Alle gerankten Karten:  Spearman r = {_fmt_rho(sp['all_ranked']['spearman_rho'])} "
        f"({sp['all_ranked']['compared']} / {sp['all_ranked']['of_ranked']} Karten)",
        f"   Nicht-Länder:           Spearman r = {_fmt_rho(sp['non_lands']['spearman_rho'])} "
        f"({sp['non_lands']['compared']} / {sp['non_lands']['of_ranked']} Karten)",
        f"   Länder:                 Spearman r = {_fmt_rho(sp['lands']['spearman_rho'])} "
        f"({sp['lands']['compared']} / {sp['lands']['of_ranked']} Karten)",
        "",
        f"2. Randkarten oben (Stufe S oder A mit < {marginal['threshold_max_share'] * 100:.0f} % "
        f"Anteil in den gezählten Listen): {marginal['count']} / {marginal['of_s_and_a']}",
        "   Namen: " + (", ".join(marginal["names"]) if marginal["names"] else "keine"),
        "",
        f"3. Stammkarten unten (> {staples['threshold_min_share'] * 100:.0f} % Anteil in den "
        f"gezählten Listen, aber Stufe C oder D): {staples['count']} / {staples['of_staples']}",
        "   Namen: " + (", ".join(staples["names"]) if staples["names"] else "keine"),
        "",
        f"4. Dünne Datenlage oben (Stufe S oder A mit < {thin['min_signals']} Signalen): "
        f"{thin['count']} / {thin['of_s_and_a']}",
        "   Nach Signalzahl in S/A: "
        + (
            ", ".join(f"{k} Signale: {v}" for k, v in thin["by_signal_count"].items())
            if thin["by_signal_count"]
            else "keine"
        ),
        "",
        "5. Stufen-Verteilung und Anteil Länder je Stufe:",
        _table(
            ["Stufe", "Karten", "Nicht-Länder", "Länder", "Anteil Länder"],
            [
                (
                    row["tier"],
                    f"{row['count']} / {row['of_pool']}",
                    row["non_lands"],
                    row["lands"],
                    _fmt_pct(row["land_share"]),
                )
                for row in report["tier_distribution"]
            ],
        ),
        "",
        "6. Stabilität (Stufenwechsel beim Weglassen je eines Signals):",
    ]
    if stab["signals"]:
        lines.append(
            _table(
                ["Signal", "Bezeichnung", "Gewicht", "Stufenwechsel"],
                [
                    (
                        row["component"],
                        row["label"],
                        f"{row['weight']:g}",
                        f"{row['tier_changes']} / {row['of_pool']}",
                    )
                    for row in stab["signals"]
                ],
            )
        )
    else:
        lines.append("   keine aktiven gewichteten Signale")
    if largest is not None:
        lines.append(
            f"   Größter Einzel-Einfluss: {largest['label']} ({largest['component']}) — "
            f"{largest['tier_changes']} / {largest['of_pool']} Karten wechseln die Stufe"
        )
    lines.extend(_extra_lines(report))
    return "\n".join(lines)


def _entry_text(entry: CorrelationEntry) -> str:
    return f"{_fmt_rho(entry['spearman_rho'])} ({entry['compared']} / {entry['of_ranked']})"


def _extra_lines(report: RankingCheckReport) -> list[str]:
    """Sections 7 to 9 of #1364 and the rule and prior block."""
    lines: list[str] = ["", "7. Gegenproben (Spearman des Index gegen überlappende Referenzen):"]
    if report["counter_checks"]:
        lines.append(f"   Hinweis: {COUNTER_NOTE}")
        lines.append(
            _table(
                ["Referenz", "Nenner", "Alle", "Zauber", "Länder"],
                [
                    (
                        item["label"],
                        "unbekannt" if item["denominator"] is None else item["denominator"],
                        _entry_text(item["all_ranked"]),
                        _entry_text(item["non_lands"]),
                        _entry_text(item["lands"]),
                    )
                    for item in report["counter_checks"]
                ]
                + [
                    (
                        f"{item['key']}, ohne Überlappung",
                        "",
                        _entry_text(held["all_ranked"]),
                        _entry_text(held["non_lands"]),
                        _entry_text(held["lands"]),
                    )
                    for item in report["counter_checks"]
                    if (held := item["held_out"]) is not None
                ],
            )
        )
        lines += [
            f"   ohne Überlappung ({item['key']}): Gewicht 0 für " + ", ".join(held["zeroed"])
            for item in report["counter_checks"]
            if (held := item["held_out"]) is not None
        ]
    else:
        lines.append("   keine Referenz vorhanden (kein Korpus, keine EDHTop16-Zeilen)")
    redundancy = report["redundancy"]
    lines += ["", f"8. Redundanz (r > {redundancy['threshold']:.2f} zwischen aktiven Komponenten):"]
    lines.append(f"   Hinweis: {redundancy['note']}")
    if redundancy["pairs"]:
        lines.append(
            _table(
                ["Komponente A", "Komponente B", "Spearman", "Karten", "Befund"],
                [
                    (
                        pair["a"],
                        pair["b"],
                        _fmt_rho(pair["spearman_rho"]),
                        pair["compared"],
                        "REDUNDANT" if pair["flagged"] else "",
                    )
                    for pair in redundancy["pairs"]
                ],
            )
        )
    lines.append(
        "   Redundant: "
        + (
            ", ".join(f"{pair['a']} / {pair['b']}" for pair in redundancy["flagged"])
            if redundancy["flagged"]
            else "kein Paar"
        )
    )
    lines += ["", "9. Sensitivität der Log-Skala (Krümmung k):"]
    sensitivity = report["sensitivity"]
    if sensitivity is None:
        lines.append("   nicht berechnet (die Anteils-Skala ist nicht „Logarithmus“)")
    else:
        lines.append(f"   Hinweis: {sensitivity['note']}")
        lines.append(
            _table(
                ["k", *ALL_TIERS, "Wechsel gegen k=150", "Spearman alle"],
                [
                    (
                        f"{run['k']:g}",
                        *(run["tier_counts"][tier] for tier in ALL_TIERS),
                        run["tier_changes_vs_base"],
                        _fmt_rho(run["spearman_all_ranked"]),
                    )
                    for run in sensitivity["runs"]
                ],
            )
        )
    rule = report["weight_rule"]
    if rule is not None:
        lines += ["", f"Gewichtsregel E2.a: {rule['rule']} — {rule['note']}"]
        lines.append(
            "   Gewichte (verlangt -> wirksam): "
            + ", ".join(
                f"{name} {rule['requested'][name]:g} -> {rule['effective'][name]:g}"
                for name in rule["requested"]
            )
        )
    if report["shrinkage"]:
        lines.append("")
        lines.append("Empirisches Bayes (Anteile mit Nenner unter 500, Prior aus dem Pool):")
        for component, prior in report["shrinkage"].items():
            if isinstance(prior, dict):
                lines.append(
                    f"   {component}: Prior-Mittel {prior['prior_mean']}, "
                    f"Prior-Stärke {prior['prior_strength']} ({prior['cards']} Karten)"
                )
    snap = report.get("tier_snapshot")
    if isinstance(snap, dict):
        state = "VERALTET" if snap.get("stale") else "AKTUELL"
        lines.append("")
        lines.append(
            f"Tier-Snapshot ({snap.get('profile_name', '')}): {state} · "
            f"Epoche {str(snap.get('data_epoch', ''))[:12]} · "
            f"Stand {snap.get('created_at', '')}"
        )
    return lines


def run_command(args: argparse.Namespace) -> int:
    """CLI handler for ``python -m commander_lab.studio ranking-check``."""
    commander = str(getattr(args, "commander", None) or LEGACY_COMMANDER).strip()
    profile: str | None = getattr(args, "profile", None)
    preset: str | None = getattr(args, "preset", None)
    json_only: bool = bool(getattr(args, "json", False))
    store = StudioStore.open(args.data)
    try:
        try:
            report = run_ranking_check(store, commander, profile=profile, preset=preset)
        except (KeyError, ValueError) as error:
            raise SystemExit(f"ranking-check: {error}") from None
        if json_only:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            print(render_ranking_check(report))
            print()
            print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    finally:
        store.close()


__all__ = [
    "ALL_TIERS",
    "BOTTOM_TIERS",
    "MARGINAL_MAX_SHARE",
    "MIN_STRONG_SIGNALS",
    "PLAUSIBILITY_ANCHOR_NOTE",
    "SCHEMA",
    "STAPLE_MIN_SHARE",
    "TOP_TIERS",
    "RankingCheckReport",
    "check_ranking",
    "render_ranking_check",
    "run_command",
    "run_ranking_check",
    "spearman_correlation",
]
