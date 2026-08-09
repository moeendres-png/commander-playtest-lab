from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass
from statistics import fmean

from commander_lab.decision_statistics import (
    bayesian_shrunk_mean,
    distributionally_robust_lower_bound,
    paired_bootstrap_interval,
    paired_standardized_effect,
    quantile_summary,
)
from commander_lab.engine.structural import ENGINE_VERSION, StructuralSimulator
from commander_lab.models import (
    CardRole,
    PilotConfig,
    StructuralCardProfile,
    StructuralDeckProfile,
    StructuralMatchConfig,
)
from commander_lab.storage import sha256_value


@dataclass(frozen=True, slots=True)
class PairedMetrics:
    games: int
    baseline_average_placement: float
    variant_average_placement: float
    placement_improvement: float
    baseline_place_1_share: float
    variant_place_1_share: float
    place_1_share_delta: float
    baseline_average_damage: float
    variant_average_damage: float
    damage_delta: float
    baseline_average_cards_drawn: float
    variant_average_cards_drawn: float
    cards_drawn_delta: float
    paired_win_count: int
    paired_loss_count: int
    paired_tie_count: int
    requested_runs: int
    started_runs: int
    valid_runs: int
    failed_runs: int
    discarded_runs: int
    actual_sample_size: int
    seeds: tuple[int, ...]
    worker_count: int
    validation_level: str
    paired_or_unpaired: str
    effect_size: float
    confidence_interval: tuple[float, float]
    bootstrap_method: str
    holdout_definition: str
    worst_case_result: float
    scenario_weights: str
    pilot_weights: str
    multiple_testing_method: str
    rounding_policy: str
    bayesian_shrunk_effect: float
    distributionally_robust_lower_bound: float
    quantiles: dict[str, float]

    def as_dict(self) -> dict[str, float | int]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


def derive_paired_seed(master_seed: int, pair_id: str, index: int) -> int:
    payload = f"{ENGINE_VERSION}|paired|{master_seed}|{pair_id}|{index}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big", signed=False)


def variant_deck(
    baseline: StructuralDeckProfile,
    *,
    variant_id: str,
    removals: Iterable[str] = (),
    additions: Iterable[StructuralCardProfile] = (),
    additional_commander_tax: int = 0,
    suppress_commander_synergy: bool = False,
) -> StructuralDeckProfile:
    cards = list(baseline.cards)
    removed: list[str] = []
    for name in removals:
        index = next((i for i, card in enumerate(cards) if card.oracle_name == name), None)
        if index is None:
            raise ValueError(f"card not found in deck profile: {name}")
        cards.pop(index)
        removed.append(name)
    cards.extend(additions)
    if len(cards) != len(baseline.cards):
        raise ValueError("variant must preserve structural deck size")
    if suppress_commander_synergy:
        cards = [card.model_copy(update={"commander_synergy": 0.0}) for card in cards]
    costs = {
        name: cost + additional_commander_tax
        for name, cost in baseline.commander_base_costs.items()
    }
    hash_payload = {
        "baseline": baseline.deck_hash,
        "variant_id": variant_id,
        "removed": removed,
        "added": list(additions),
        "tax": additional_commander_tax,
        "suppress": suppress_commander_synergy,
    }
    return baseline.model_copy(
        update={
            "deck_id": variant_id,
            "deck_hash": sha256_value(hash_payload),
            "cards": tuple(cards),
            "commander_base_costs": costs,
        }
    )


def ablation_filler(
    card: StructuralCardProfile, *, suffix: str = "ablation"
) -> StructuralCardProfile:
    return StructuralCardProfile(
        oracle_name=f"{card.oracle_name} [{suffix} filler]",
        mana_value=card.mana_value,
        roles=frozenset({CardRole.MANA_SOURCE}) if card.is_land else frozenset(),
        role_strengths={CardRole.MANA_SOURCE: 1.0} if card.is_land else {},
        color_requirements=card.color_requirements,
        produces_colors=card.produces_colors if card.is_land else frozenset(),
        is_land=card.is_land,
        is_permanent=card.is_permanent,
        is_creature=card.is_creature,
        base_power=max(0.0, card.base_power * 0.25),
        floor_value=0.05,
        immediate_impact=0.0,
        turn_cycle_risk=1.0 if card.is_permanent else 0.0,
        multiplayer_scaling=0.0,
        notes="Role-neutral structural ablation filler; preserves card count and mana value.",
    )


def profile_score(card: StructuralCardProfile) -> float:
    role_value = sum(card.role_strengths.get(role, 1.0) for role in card.roles)
    return (
        card.floor_value * 1.4
        + card.immediate_impact * 1.2
        + card.commander_synergy
        + card.multiplayer_scaling * 0.8
        + role_value * 0.22
        - card.turn_cycle_risk * 0.9
        - max(0.0, card.mana_value - 4.0) * 0.15
    )


def role_summary(deck: StructuralDeckProfile) -> dict[str, int]:
    summary: dict[str, int] = {role.value: 0 for role in CardRole}
    for card in deck.cards:
        for role in card.roles:
            summary[role.value] += 1
    return summary


def run_paired_structural_comparison(
    *,
    baseline: StructuralDeckProfile,
    variant: StructuralDeckProfile,
    opponents: tuple[StructuralDeckProfile, ...],
    iterations: int,
    seed: int,
    pilot_config: PilotConfig,
    max_turns: int,
    pair_id: str,
) -> tuple[PairedMetrics, list[dict[str, object]]]:
    baseline_registry = {deck.deck_id: deck for deck in (baseline, *opponents)}
    variant_registry = {deck.deck_id: deck for deck in (variant, *opponents)}
    base_sim = StructuralSimulator(baseline_registry)
    var_sim = StructuralSimulator(variant_registry)
    base_rows: list[dict[str, float]] = []
    var_rows: list[dict[str, float]] = []
    pairs: list[dict[str, object]] = []
    for index in range(iterations):
        match_seed = derive_paired_seed(seed, pair_id, index)
        start = index % (1 + len(opponents))
        baseline_ids = (baseline.deck_id, *(deck.deck_id for deck in opponents))
        variant_ids = (variant.deck_id, *(deck.deck_id for deck in opponents))
        configs = (pilot_config,) * len(baseline_ids)
        from commander_lab.models import StructuralAbortLimits

        limits = StructuralAbortLimits(max_turns=max_turns)
        base_result = base_sim.simulate(
            StructuralMatchConfig(
                match_id=f"{pair_id}-base-{index:08d}",
                deck_ids=baseline_ids,
                limits=limits,
                seed=match_seed,
                starting_player_seat=start,
                pilot_configs=configs,
            ),
            run_id=f"{pair_id}-baseline",
        )
        var_result = var_sim.simulate(
            StructuralMatchConfig(
                match_id=f"{pair_id}-variant-{index:08d}",
                deck_ids=variant_ids,
                limits=limits,
                seed=match_seed,
                starting_player_seat=start,
                pilot_configs=configs,
            ),
            run_id=f"{pair_id}-variant",
        )
        b = base_result.player_metrics["p1"]
        v = var_result.player_metrics["p1"]
        base_row = {
            "placement": float(b.placement),
            "win": float(b.placement == 1),
            "damage": b.normal_damage_dealt + b.commander_damage_dealt,
            "cards_drawn": float(b.cards_drawn),
        }
        var_row = {
            "placement": float(v.placement),
            "win": float(v.placement == 1),
            "damage": v.normal_damage_dealt + v.commander_damage_dealt,
            "cards_drawn": float(v.cards_drawn),
        }
        base_rows.append(base_row)
        var_rows.append(var_row)
        comparison = "tie"
        if v.placement < b.placement:
            comparison = "variant_win"
        elif v.placement > b.placement:
            comparison = "variant_loss"
        pairs.append(
            {
                "index": index,
                "seed": match_seed,
                "starting_player_seat": start,
                "baseline_placement": b.placement,
                "variant_placement": v.placement,
                "comparison": comparison,
                "baseline_log_sha256": base_result.log_sha256,
                "variant_log_sha256": var_result.log_sha256,
            }
        )
    avg = lambda rows, key: fmean(row[key] for row in rows)
    base_place = avg(base_rows, "placement")
    var_place = avg(var_rows, "placement")
    differences = tuple(
        float(row["baseline_placement"]) - float(row["variant_placement"]) for row in pairs
    )
    interval = paired_bootstrap_interval(
        differences, seed=derive_paired_seed(seed, pair_id, iterations + 1)
    )
    metrics = PairedMetrics(
        games=iterations,
        baseline_average_placement=base_place,
        variant_average_placement=var_place,
        placement_improvement=base_place - var_place,
        baseline_place_1_share=avg(base_rows, "win"),
        variant_place_1_share=avg(var_rows, "win"),
        place_1_share_delta=avg(var_rows, "win") - avg(base_rows, "win"),
        baseline_average_damage=avg(base_rows, "damage"),
        variant_average_damage=avg(var_rows, "damage"),
        damage_delta=avg(var_rows, "damage") - avg(base_rows, "damage"),
        baseline_average_cards_drawn=avg(base_rows, "cards_drawn"),
        variant_average_cards_drawn=avg(var_rows, "cards_drawn"),
        cards_drawn_delta=avg(var_rows, "cards_drawn") - avg(base_rows, "cards_drawn"),
        paired_win_count=sum(row["comparison"] == "variant_win" for row in pairs),
        paired_loss_count=sum(row["comparison"] == "variant_loss" for row in pairs),
        paired_tie_count=sum(row["comparison"] == "tie" for row in pairs),
        requested_runs=iterations,
        started_runs=iterations,
        valid_runs=len(pairs),
        failed_runs=0,
        discarded_runs=0,
        actual_sample_size=len(pairs),
        seeds=tuple(derive_paired_seed(seed, pair_id, index) for index in range(iterations)),
        worker_count=1,
        validation_level="structural_only",
        paired_or_unpaired="paired",
        effect_size=paired_standardized_effect(differences),
        confidence_interval=interval,
        bootstrap_method="deterministic_paired_percentile_bootstrap_2000",
        holdout_definition="primary paired scenario; holdouts reported separately",
        worst_case_result=min(differences),
        scenario_weights="equal within this paired scenario",
        pilot_weights=f"single configured pilot: {pilot_config.strength.value}",
        multiple_testing_method=(
            "not_applicable_single_comparison; Holm required for ranked families"
        ),
        rounding_policy="unrounded internal values; presentation may round to six decimals",
        bayesian_shrunk_effect=bayesian_shrunk_mean(differences),
        distributionally_robust_lower_bound=distributionally_robust_lower_bound(differences),
        quantiles=quantile_summary(differences),
    )
    return metrics, pairs
