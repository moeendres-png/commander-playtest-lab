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

from . import layers, strength, strength_view, tiers, universe_choice, universe_view
from .builder import pool_cards
from .store import LEGACY_COMMANDER, StudioStore
from .strength import (
    DECK_UNIVERSE,
    LAYER_PREFIX,
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
    if component.startswith(LAYER_PREFIX):
        key = component[len(LAYER_PREFIX) :]
        return replace(settings, layer_weights={**settings.layer_weights, key: 0.0})
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
) -> RankingCheckReport:
    """Pure diagnostic check of a strength-index ranking across all six #1349 metrics."""
    ctx = context or PoolContext()
    display = {card: (names[card] if names and card in names else card) for card in observations}
    base_scored = (
        dict(scored)
        if scored is not None
        else strength.score_pool(settings, observations, collected, context=ctx)
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

    rated_components = (*strength.COMPONENTS, *settings.active_layers())
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
    }


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
    """Compute the #1349 ranking check against ``store`` for ``commander``."""
    resolved = strength_view.resolve_settings(
        store, preset=preset, profile=profile, settings=settings
    )
    label = profile or preset or "Ausgewogen"
    pool = pool_cards(store, [commander], with_signals=False)
    raw_cards = pool["cards"]
    if not isinstance(raw_cards, list):
        raise TypeError("pool_cards returned an unexpected shape")
    ids = [str(card["card_id"]) for card in raw_cards]
    display = {str(card["card_id"]): str(card["name"]) for card in raw_cards}
    commander_ids = strength_view._strings(pool["commander_ids"])
    claims = strength_view._claim_index(store, ids)
    ambiguous: dict[tuple[str, str], list[str]] = {}

    summary: universe_view.ProfileSummary | None = None
    kind, _source, _bracket = strength.parse_universe_source(resolved.universe_source) or ("",) * 3
    if resolved.universe_profile and kind in (strength.UNIVERSE_AUTO, strength.UNIVERSE_PROFILE):
        try:
            summary = universe_view.profile_summary(
                store, resolved.universe_profile, commander_names=[commander]
            )
        except KeyError:
            resolved = replace(resolved, universe_profile=None)
    choice = universe_choice.choose(store, commander, resolved, summary)

    per_card: dict[str, dict[str, Observation]] = {card_id: {} for card_id in ids}
    collected: set[str] = set()
    for component in (
        strength.COMMANDER_INCLUSION,
        strength.BRACKET_INCLUSION,
        strength.SYNERGY,
        strength.TOURNAMENT_LISTS,
        strength.TOURNAMENT_CONVERSION,
        strength.GLOBAL_INCLUSION,
        strength.COMBOS,
        strength.PLAYGROUP_OBSERVED,
    ):
        signal = strength.signal_for(
            component, resolved.bracket, combo_source=resolved.combo_source
        )
        if not signal:
            continue
        if component == strength.COMBOS and resolved.combo_source == strength.COMBO_SPELLBOOK:
            observed, exists = strength_view._combo_observations(
                store, commander, claims, display, ambiguous
            )
        else:
            observed, exists = strength_view._signal_observations(
                store, commander, signal, claims, display, ambiguous
            )
        if exists:
            collected.add(component)
        for card_id, observation in observed.items():
            per_card[card_id][component] = observation

    filter_cards: set[str] = set()
    universe_minimum = tiers.TierParams().min_universe
    if choice["kind"] == universe_choice.KIND_PROFILE and summary is not None:
        universe_minimum = summary["min_universe"]
        if summary["denominator"] > 0:
            collected.add(DECK_UNIVERSE)
            spread = universe_view.pool_spread(
                store, summary["profile"], ids, commander_names=[commander]
            )
            strength_view._fill_spread(per_card, filter_cards, spread["cards"])
    elif choice["kind"] == universe_choice.KIND_LOCAL:
        local_total, _snapshot, local_cards = universe_view.spread_for_spec(
            store, universe_choice.local_spec(store, commander), ids, commander_names=[commander]
        )
        if local_total > 0:
            collected.add(DECK_UNIVERSE)
            strength_view._fill_spread(per_card, filter_cards, local_cards)
    elif choice["kind"] == universe_choice.KIND_COUNTED:
        for item in universe_choice.counted_universes(store, commander):
            if item["value"] == choice["counted"]:
                collected.add(DECK_UNIVERSE)
                for card_id, observation in strength_view.counted_observations(
                    store, commander, item, claims, display, ambiguous
                ).items():
                    per_card[card_id][DECK_UNIVERSE] = observation

    type_group: dict[str, str] = {}
    bands: dict[str, str] = {}
    unranked = strength_view._unranked_cards(raw_cards, commander_ids)
    for card in raw_cards:
        card_id = str(card["card_id"])
        group = str(card["group"])
        type_group[card_id] = group
        bands[card_id] = strength.mana_band(
            strength_view._float(card["mana_value"]), is_land=group == "Land"
        )

    weighted = [key for key in strength.LAYER_KEYS if resolved.layer_weights[key] > 0]
    if weighted:
        layer_result = strength_view._layer_result(
            store, raw_cards, display, claims, unranked, per_card, resolved.pod_size
        )
        for card_id, found in layers.index_observations(layer_result, weighted).items():
            per_card[card_id].update(found)
        for key in weighted:
            if any(item[key]["status"] == layers.OK for item in layer_result["cards"].values()):
                collected.add(strength.layer_component(key))

    others = strength_view._other_commander_names(store, commander)
    tier_unranked = dict(unranked)
    for card in raw_cards:
        card_id = str(card["card_id"])
        if card_id not in tier_unranked and str(card["name"]).casefold() in others:
            tier_unranked[card_id] = strength.NOT_RANKED_OTHER_COMMANDER

    context = PoolContext(
        type_group,
        bands,
        tier_unranked,
        filter_cards,
        universe_minimum,
        function_group=strength_view._function_groups(store, raw_cards),
    )

    if DECK_UNIVERSE in collected and choice["kind"] in (
        universe_choice.KIND_LOCAL,
        universe_choice.KIND_COUNTED,
    ):
        counted_lists = {
            card_id: obs
            for card_id, per in per_card.items()
            if (obs := per.get(DECK_UNIVERSE)) is not None
        }
        counted_label = choice["label"]
    else:
        counted_lists, counted_label = _reference_counted_lists(store, commander, ids, display)

    return check_ranking(
        resolved,
        per_card,
        collected,
        names=display,
        context=context,
        counted_lists=counted_lists,
        counted_lists_label=counted_label,
        commander=commander,
        profile_or_preset=label,
    )


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
    return "\n".join(lines)


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
