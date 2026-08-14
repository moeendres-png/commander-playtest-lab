from __future__ import annotations

import math
import random
from collections.abc import Mapping, Sequence
from statistics import fmean

from commander_lab.decision_statistics import monte_carlo_standard_error, percentile
from commander_lab.models import CardRole
from commander_lab.models.roles import StructuralMechanic

from .features import card_feature_confidence
from .search_context import SearchCard, WholeDeckSearchContext

MULTIPLAYER_LEVERAGE_VERSION = "2026-08-14.1"


def _numeric_component(row: dict[str, object], key: str) -> float:
    value = row.get(key)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return 0.0


_REPEATABLE_MECHANICS = frozenset(
    {
        StructuralMechanic.REPEATABLE_TOKEN_SOURCE,
        StructuralMechanic.TOKEN_ENGINE,
        StructuralMechanic.LAND_RECURSION,
        StructuralMechanic.ARTIFACT_ENGINE,
        StructuralMechanic.GRAVEYARD_RECURSION,
    }
)


def card_multiplayer_leverage(card: SearchCard) -> dict[str, object]:
    """Return transparent structural leverage components, never a power score."""
    profile = card.profile
    mana_efficiency = max(0.0, 4.0 - profile.mana_value) / 4.0
    confidence = card_feature_confidence(profile).confidence if card.semantic_known else 0.0
    result: dict[str, object] = {
        "oracle_name": card.oracle_name,
        "semantic_known": card.semantic_known,
        "semantic_evidence": card.semantic_evidence,
        "semantic_confidence": confidence,
        "evidence_quality": profile.source_quality.value,
        "mana_efficiency": mana_efficiency,
        "multiplayer_scaling": None,
        "role_compression": None,
        "floor_value": None,
        "immediate_impact": None,
        "turn_cycle_risk": None,
        "setup_dependency": None,
        "commander_independence": None,
        "repeatability": None,
        "evidence_type": "structural_diagnostic_components_not_card_power_score",
    }
    if not card.semantic_known:
        result["unknown_interpretation"] = (
            "Semantic dimensions are UNKNOWN and are not replaced by the neutral numeric search "
            "placeholder stored in the fact-only StructuralCardProfile."
        )
        return result

    mechanics = set(profile.mechanic_tags)
    commander_independence: float | None
    if StructuralMechanic.COMMANDER_INDEPENDENT in mechanics:
        commander_independence = 1.0
    elif StructuralMechanic.COMMANDER_DEPENDENT in mechanics:
        commander_independence = 0.0
    else:
        commander_independence = None

    dependency = 0.0
    if StructuralMechanic.COMMANDER_DEPENDENT in mechanics:
        dependency += 0.65
    dependency += min(0.35, 0.175 * len(profile.conditional_strength))

    if mechanics & set(_REPEATABLE_MECHANICS):
        repeatability = 1.0
    elif profile.is_permanent and CardRole.ENGINE in profile.roles:
        repeatability = 0.5
    else:
        repeatability = 0.0

    result.update(
        {
            "multiplayer_scaling": profile.multiplayer_scaling,
            "role_compression": max(0.0, float(len(profile.roles) - 1)),
            "floor_value": profile.floor_value,
            "immediate_impact": profile.immediate_impact,
            "turn_cycle_risk": profile.turn_cycle_risk,
            "setup_dependency": min(1.0, dependency),
            "commander_independence": commander_independence,
            "repeatability": repeatability,
        }
    )
    return result


def deck_multiplayer_leverage(
    context: WholeDeckSearchContext,
    mainboard: Sequence[str],
) -> dict[str, object]:
    rows = [card_multiplayer_leverage(context.cards[name]) for name in mainboard]
    dimensions = (
        "multiplayer_scaling",
        "mana_efficiency",
        "role_compression",
        "floor_value",
        "immediate_impact",
        "turn_cycle_risk",
        "setup_dependency",
        "commander_independence",
        "repeatability",
        "semantic_confidence",
    )
    aggregates: dict[str, dict[str, float | int]] = {}
    for dimension in dimensions:
        values = [
            float(value)
            for row in rows
            if isinstance((value := row.get(dimension)), (int, float))
            and not isinstance(value, bool)
        ]
        aggregates[dimension] = {
            "mean": fmean(values) if values else 0.0,
            "supported_cards": len(values),
            "support_fraction": len(values) / len(rows) if rows else 0.0,
        }
    known_rows = [row for row in rows if row["semantic_known"]]
    ranked = sorted(
        known_rows,
        key=lambda row: (
            -_numeric_component(row, "multiplayer_scaling"),
            str(row["oracle_name"]),
        ),
    )
    return {
        "schema_version": "1.0.0",
        "diagnostic_version": MULTIPLAYER_LEVERAGE_VERSION,
        "card_count": len(rows),
        "semantic_known_count": len(known_rows),
        "semantic_unknown_count": len(rows) - len(known_rows),
        "dimensions": aggregates,
        "highest_multiplayer_scaling_cards": [
            {
                "oracle_name": row["oracle_name"],
                "multiplayer_scaling": row["multiplayer_scaling"],
                "mana_efficiency": row["mana_efficiency"],
                "turn_cycle_risk": row["turn_cycle_risk"],
                "repeatability": row["repeatability"],
            }
            for row in ranked[:10]
        ],
        "evidence_type": "structural_diagnostic_components_not_card_power_score",
        "scalar_power_score": None,
    }


def _paired_differences(campaign: Mapping[str, object]) -> tuple[float, ...]:
    raw = campaign.get("paired_observations")
    if not isinstance(raw, list):
        raise ValueError("campaign is missing paired_observations")
    differences: list[float] = []
    for row in raw:
        if not isinstance(row, Mapping):
            raise TypeError("paired observation must be a mapping")
        baseline = row.get("baseline_placement")
        variant = row.get("variant_placement")
        if not isinstance(baseline, (int, float)) or not isinstance(variant, (int, float)):
            raise TypeError("paired placement values must be numeric")
        differences.append(float(baseline) - float(variant))
    if not differences:
        raise ValueError("campaign has no paired observations")
    return tuple(differences)


def _difference_of_means_bootstrap_interval(
    four_player: tuple[float, ...],
    five_player: tuple[float, ...],
    *,
    seed: int,
    resamples: int = 2000,
) -> tuple[float, float]:
    if len(four_player) == len(five_player) == 1:
        value = five_player[0] - four_player[0]
        return value, value
    rng = random.Random(seed)
    samples: list[float] = []
    for _ in range(resamples):
        four_mean = fmean(four_player[rng.randrange(len(four_player))] for _ in four_player)
        five_mean = fmean(five_player[rng.randrange(len(five_player))] for _ in five_player)
        samples.append(five_mean - four_mean)
    return percentile(samples, 0.025), percentile(samples, 0.975)


def multiplayer_pod_response(
    four_player_campaign: Mapping[str, object],
    five_player_campaign: Mapping[str, object],
    *,
    seed: int,
) -> dict[str, object]:
    """Compare variant-vs-control structural effects across 4P and 5P axes."""
    four = _paired_differences(four_player_campaign)
    five = _paired_differences(five_player_campaign)
    effect_4p = fmean(four)
    effect_5p = fmean(five)
    response = effect_5p - effect_4p
    interval = _difference_of_means_bootstrap_interval(four, five, seed=seed)
    combined_mcse = math.sqrt(
        monte_carlo_standard_error(four) ** 2 + monte_carlo_standard_error(five) ** 2
    )
    if interval[0] > 0.0:
        classification = "STRUCTURALLY_BETTER_WITH_LARGER_POD"
    elif interval[1] < 0.0:
        classification = "STRUCTURALLY_WORSE_WITH_LARGER_POD"
    else:
        classification = "NOT_STRUCTURALLY_DISTINGUISHABLE"
    return {
        "candidate_vs_control_effect_4p": effect_4p,
        "candidate_vs_control_effect_5p": effect_5p,
        "pod_size_response": response,
        "pod_size_response_model_interval": interval,
        "pod_size_response_mcse": combined_mcse,
        "classification": classification,
        "point_direction": (
            "better_with_more_players"
            if response > 0
            else "worse_with_more_players"
            if response < 0
            else "unchanged_point_estimate"
        ),
        "evidence_class": "structural_model_estimates",
        "interpretation": (
            "Difference of candidate-vs-control paired placement effects between separate balanced "
            "4P primary and 5P sensitivity scenario sets. This is model-internal sensitivity, not "
            "an empirical pod-size effect or local opponent frequency estimate."
        ),
    }
