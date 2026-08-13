from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from statistics import fmean

from commander_lab.mana_analysis import DeckManaAnalysis
from commander_lab.models import CardRole, StructuralDeckProfile

from .models import DeckDesignPolicy, PolicyId
from .search_models import ManaBasePolicy

BASIC_LANDS = frozenset({"Plains", "Island", "Mountain", "Swamp", "Forest", "Wastes"})


def _land_bounds(policy: DeckDesignPolicy) -> tuple[int, int, int, int]:
    corridor = policy.target_corridors.get("land_count")
    if corridor is None:
        return 33, 39, 0, 98
    pref_low = max(0, round(corridor.preferred_minimum))
    pref_high = min(98, round(corridor.preferred_maximum))
    hard_low = 0 if corridor.hard_minimum is None else max(0, round(corridor.hard_minimum))
    hard_high = 98 if corridor.hard_maximum is None else min(98, round(corridor.hard_maximum))
    return pref_low, pref_high, hard_low, hard_high


def derive_mana_base_policy(policy: DeckDesignPolicy) -> ManaBasePolicy:
    pref_low, pref_high, hard_low, hard_high = _land_bounds(policy)
    midpoint = max(1, round((pref_low + pref_high) / 2))
    if policy.policy_id == PolicyId.CURRENT_CONTROL:
        w, u, r = 16, 17, 13
        basic_low, basic_high = 12, 22
    else:
        w = max(10, round(midpoint * 0.42))
        u = max(11, round(midpoint * 0.45))
        r = max(8, round(midpoint * 0.32))
        basic_low = max(3, round(midpoint * 0.16))
        basic_high = max(basic_low, round(midpoint * 0.48))
    if policy.policy_id == PolicyId.LOW_LAND_HIGH_VELOCITY:
        basic_low = 3
        basic_high = 12
    return ManaBasePolicy(
        preferred_land_minimum=pref_low,
        preferred_land_maximum=pref_high,
        hard_land_minimum=hard_low,
        hard_land_maximum=hard_high,
        preferred_basic_minimum=basic_low,
        preferred_basic_maximum=basic_high,
        minimum_white_sources=w,
        minimum_blue_sources=u,
        minimum_red_sources=r,
        preferred_t1_untapped_sources=max(10, round(midpoint * 0.38)),
        preferred_flexible_sources=max(6, round(midpoint * 0.22)),
        preferred_maximum_tapped_lands=max(5, round(midpoint * 0.28)),
        utility_land_budget=max(5, round(midpoint * 0.22)),
    )


def _number(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _integer(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return round(value)
    return default


def _string_number_mapping(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, int] = {}
    for key, raw in value.items():
        if isinstance(key, str) and isinstance(raw, (int, float)):
            result[key] = round(raw)
    return result


def whole_deck_mana_summary(
    deck: StructuralDeckProfile, analysis: DeckManaAnalysis
) -> dict[str, object]:
    commander_names = set(deck.commander_names)
    noncommanders = [card for card in deck.cards if card.oracle_name not in commander_names]
    nonlands = [card for card in noncommanders if not card.is_land]
    basics = sum(card.oracle_name in BASIC_LANDS for card in noncommanders)
    ramp = sum(CardRole.RAMP in card.roles for card in noncommanders)
    selection = sum(CardRole.SELECTION in card.roles for card in noncommanders)
    lands = analysis.land_count
    colored = dict(sorted(analysis.colored_sources.items()))
    t1 = dict(sorted(analysis.t1_untapped_land_sources.items()))
    turn2 = analysis.turn_castability_support.get(2, {})
    source_ratios = [
        min(1.0, colored.get("W", 0) / 16.0),
        min(1.0, colored.get("U", 0) / 17.0),
    ]
    commander_castability_support = sum(source_ratios) / len(source_ratios)
    return {
        "land_count": lands,
        "basic_count": basics,
        "nonbasic_land_count": lands - basics,
        "colored_sources": colored,
        "ishai_wu_source_counts": dict(sorted(analysis.ishai_wu_source_counts.items())),
        "flexible_source_count": analysis.flexible_source_count,
        "definitely_tapped_land_count": analysis.definitely_tapped_land_count,
        "conditionally_tapped_land_count": analysis.conditionally_tapped_land_count,
        "t1_untapped_land_sources": t1,
        "turn2_source_supported_share": _number(turn2.get("source_supported_share"), 1.0),
        "ramp_count": ramp,
        "selection_count": selection,
        "average_nonland_mv": fmean(card.mana_value for card in nonlands) if nonlands else 0.0,
        "commander_castability_support": commander_castability_support,
        "evidence_type": "structural_mana_search_summary_not_opening_hand_probability",
    }


def mana_soft_score(summary: dict[str, object], policy: ManaBasePolicy) -> float:
    colored = Counter(_string_number_mapping(summary.get("colored_sources")))
    land_count = _integer(summary.get("land_count"))
    basic_count = _integer(summary.get("basic_count"))
    t1 = Counter(_string_number_mapping(summary.get("t1_untapped_land_sources")))
    flexible = _integer(summary.get("flexible_source_count"))
    tapped = _integer(summary.get("definitely_tapped_land_count"))
    turn2 = _number(summary.get("turn2_source_supported_share"))
    ramp = _integer(summary.get("ramp_count"))
    selection = _integer(summary.get("selection_count"))

    def ratio(actual: int, target: int) -> float:
        return 1.0 if target <= 0 else min(1.0, actual / target)

    color_score = (
        ratio(colored["W"], policy.minimum_white_sources)
        + ratio(colored["U"], policy.minimum_blue_sources)
        + ratio(colored["R"], policy.minimum_red_sources)
    ) / 3.0
    t1_total = max(t1.values(), default=0)
    t1_score = ratio(t1_total, policy.preferred_t1_untapped_sources)
    flex_score = ratio(flexible, policy.preferred_flexible_sources)
    tapped_penalty = max(0, tapped - policy.preferred_maximum_tapped_lands) / max(1, land_count)
    basic_penalty = 0.0
    if basic_count < policy.preferred_basic_minimum:
        basic_penalty = (policy.preferred_basic_minimum - basic_count) / max(1, land_count)
    elif basic_count > policy.preferred_basic_maximum:
        basic_penalty = (basic_count - policy.preferred_basic_maximum) / max(1, land_count)
    velocity_bonus = min(0.25, (ramp + selection) / 80.0)
    return float(
        color_score * 0.35
        + t1_score * 0.15
        + flex_score * 0.10
        + turn2 * 0.25
        + velocity_bonus
        - tapped_penalty * 0.5
        - basic_penalty * 0.2
    )
