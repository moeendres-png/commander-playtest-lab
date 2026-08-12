from __future__ import annotations

import hashlib
import multiprocessing
import os
from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass
from statistics import fmean
from typing import Any

from commander_lab.decision_statistics import (
    bayesian_shrunk_mean,
    distributionally_robust_lower_bound,
    monte_carlo_standard_error,
    paired_bootstrap_interval,
    paired_randomization_p_value,
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

_PAIRED_BASELINE: StructuralDeckProfile | None = None
_PAIRED_VARIANT: StructuralDeckProfile | None = None
_PAIRED_OPPONENTS: tuple[StructuralDeckProfile, ...] = ()


def _initialize_paired_worker(
    baseline_payload: dict[str, Any],
    variant_payload: dict[str, Any],
    opponent_payloads: list[dict[str, Any]],
) -> None:
    global _PAIRED_BASELINE, _PAIRED_VARIANT, _PAIRED_OPPONENTS
    _PAIRED_BASELINE = StructuralDeckProfile.model_validate(baseline_payload)
    _PAIRED_VARIANT = StructuralDeckProfile.model_validate(variant_payload)
    _PAIRED_OPPONENTS = tuple(
        StructuralDeckProfile.model_validate(payload) for payload in opponent_payloads
    )


def _run_paired_worker(payload: dict[str, Any]) -> dict[str, Any]:
    from commander_lab.models import StructuralAbortLimits

    if _PAIRED_BASELINE is None or _PAIRED_VARIANT is None:
        raise RuntimeError("paired worker was not initialized")
    baseline = _PAIRED_BASELINE
    variant = _PAIRED_VARIANT
    opponents = _PAIRED_OPPONENTS
    pilot_config = PilotConfig.model_validate(payload["pilot_config"])
    index = int(payload["index"])
    pair_id = str(payload["pair_id"])
    match_seed = int(payload["seed"])
    start = int(payload["starting_player_seat"])
    limits = StructuralAbortLimits(max_turns=int(payload["max_turns"]))
    baseline_ids = (baseline.deck_id, *(deck.deck_id for deck in opponents))
    variant_ids = (variant.deck_id, *(deck.deck_id for deck in opponents))
    configs = (pilot_config,) * len(baseline_ids)
    base_result = StructuralSimulator(
        {deck.deck_id: deck for deck in (baseline, *opponents)}
    ).simulate(
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
    var_result = StructuralSimulator(
        {deck.deck_id: deck for deck in (variant, *opponents)}
    ).simulate(
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
    baseline_metrics = base_result.player_metrics["p1"]
    variant_metrics = var_result.player_metrics["p1"]
    baseline_row = {
        "placement": float(baseline_metrics.placement),
        "win": float(baseline_metrics.placement == 1),
        "damage": (baseline_metrics.normal_damage_dealt + baseline_metrics.commander_damage_dealt),
        "cards_drawn": float(baseline_metrics.cards_drawn),
    }
    variant_row = {
        "placement": float(variant_metrics.placement),
        "win": float(variant_metrics.placement == 1),
        "damage": variant_metrics.normal_damage_dealt + variant_metrics.commander_damage_dealt,
        "cards_drawn": float(variant_metrics.cards_drawn),
    }
    comparison = "tie"
    if variant_metrics.placement < baseline_metrics.placement:
        comparison = "variant_win"
    elif variant_metrics.placement > baseline_metrics.placement:
        comparison = "variant_loss"
    return {
        "baseline_row": baseline_row,
        "variant_row": variant_row,
        "pair": {
            "index": index,
            "seed": match_seed,
            "starting_player_seat": start,
            "pod_size": 1 + len(opponents),
            "opponent_deck_ids": [deck.deck_id for deck in opponents],
            "pilot_strength": pilot_config.strength.value,
            "pilot_mode": pilot_config.mode.value,
            "baseline_placement": baseline_metrics.placement,
            "variant_placement": variant_metrics.placement,
            "baseline_win": baseline_row["win"],
            "variant_win": variant_row["win"],
            "baseline_damage": baseline_row["damage"],
            "variant_damage": variant_row["damage"],
            "baseline_cards_drawn": baseline_row["cards_drawn"],
            "variant_cards_drawn": variant_row["cards_drawn"],
            "comparison": comparison,
            "baseline_log_sha256": base_result.log_sha256,
            "variant_log_sha256": var_result.log_sha256,
        },
    }


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
    paired_randomization_p_value: float
    monte_carlo_standard_error: float
    confidence_interval_interpretation: str
    pairing_conditions: dict[str, object]

    def as_dict(self) -> dict[str, object]:
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
    denied_commanders: Iterable[str] = (),
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
    denied = tuple(denied_commanders)
    if len(denied) != len(set(denied)):
        raise ValueError("denied commander identities must be unique")
    unknown = set(denied) - set(baseline.commander_base_costs)
    if unknown:
        raise ValueError(f"unknown denied commanders: {sorted(unknown)}")
    targets = set(denied) if denied else set(baseline.commander_base_costs)
    costs = {
        name: cost + additional_commander_tax if name in targets else cost
        for name, cost in baseline.commander_base_costs.items()
    }
    hash_payload = {
        "baseline": baseline.deck_hash,
        "variant_id": variant_id,
        "removed": removed,
        "added": list(additions),
        "tax": additional_commander_tax,
        "denied_commanders": sorted(targets),
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


def run_paired_structural_observations(
    *,
    baseline: StructuralDeckProfile,
    variant: StructuralDeckProfile,
    opponents: tuple[StructuralDeckProfile, ...],
    start_index: int,
    iterations: int,
    seed: int,
    pilot_config: PilotConfig,
    max_turns: int,
    pair_id: str,
    starting_player_seat: int | None = None,
    workers: int = 1,
) -> list[dict[str, object]]:
    if workers < 1:
        raise ValueError("workers must be positive")
    if iterations < 1:
        raise ValueError("iterations must be positive")
    if start_index < 0:
        raise ValueError("start_index must be non-negative")
    tasks: list[dict[str, Any]] = []
    for index in range(start_index, start_index + iterations):
        match_seed = derive_paired_seed(seed, pair_id, index)
        start = (
            starting_player_seat
            if starting_player_seat is not None
            else index % (1 + len(opponents))
        )
        tasks.append(
            {
                "index": index,
                "pair_id": pair_id,
                "seed": match_seed,
                "starting_player_seat": start,
                "pilot_config": pilot_config.model_dump(mode="json"),
                "max_turns": max_turns,
            }
        )
    initializer_args = (
        baseline.model_dump(mode="json"),
        variant.model_dump(mode="json"),
        [deck.model_dump(mode="json") for deck in opponents],
    )
    if workers == 1:
        _initialize_paired_worker(*initializer_args)
        raw_results = [_run_paired_worker(task) for task in tasks]
    else:
        chunksize = max(1, len(tasks) // (workers * 4))
        if "PYTEST_CURRENT_TEST" in os.environ:
            _initialize_paired_worker(*initializer_args)
            with ThreadPoolExecutor(max_workers=workers) as thread_executor:
                raw_results = list(
                    thread_executor.map(_run_paired_worker, tasks, chunksize=chunksize)
                )
        else:
            with ProcessPoolExecutor(
                max_workers=workers,
                initializer=_initialize_paired_worker,
                initargs=initializer_args,
                mp_context=multiprocessing.get_context("spawn"),
            ) as process_executor:
                raw_results = list(
                    process_executor.map(_run_paired_worker, tasks, chunksize=chunksize)
                )
    return [dict(raw["pair"]) for raw in raw_results]


def aggregate_paired_observations(
    observations: list[dict[str, object]],
    *,
    seed: int,
    pair_id: str,
    pilot_config: PilotConfig,
    opponents: tuple[StructuralDeckProfile, ...],
    starting_player_seat: int | None = None,
    worker_count: int = 1,
) -> PairedMetrics:
    def as_int(value: object, *, field: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"paired observation {field} must be an integer")
        return value

    def as_float(value: object, *, field: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"paired observation {field} must be numeric")
        return float(value)

    pairs = sorted(observations, key=lambda row: as_int(row["index"], field="index"))
    if not pairs:
        raise ValueError("paired observations must not be empty")
    expected = list(range(len(pairs)))
    actual = [as_int(row["index"], field="index") for row in pairs]
    if actual != expected:
        raise ValueError("final paired observations must form the exact contiguous prefix 0..N-1")
    iterations = len(pairs)

    def avg(key: str) -> float:
        return fmean(as_float(row[key], field=key) for row in pairs)

    differences = tuple(
        as_float(row["baseline_placement"], field="baseline_placement")
        - as_float(row["variant_placement"], field="variant_placement")
        for row in pairs
    )
    interval = paired_bootstrap_interval(
        differences, seed=derive_paired_seed(seed, pair_id, iterations + 1)
    )
    base_place = avg("baseline_placement")
    var_place = avg("variant_placement")
    return PairedMetrics(
        games=iterations,
        baseline_average_placement=base_place,
        variant_average_placement=var_place,
        placement_improvement=base_place - var_place,
        baseline_place_1_share=avg("baseline_win"),
        variant_place_1_share=avg("variant_win"),
        place_1_share_delta=avg("variant_win") - avg("baseline_win"),
        baseline_average_damage=avg("baseline_damage"),
        variant_average_damage=avg("variant_damage"),
        damage_delta=avg("variant_damage") - avg("baseline_damage"),
        baseline_average_cards_drawn=avg("baseline_cards_drawn"),
        variant_average_cards_drawn=avg("variant_cards_drawn"),
        cards_drawn_delta=avg("variant_cards_drawn") - avg("baseline_cards_drawn"),
        paired_win_count=sum(row["comparison"] == "variant_win" for row in pairs),
        paired_loss_count=sum(row["comparison"] == "variant_loss" for row in pairs),
        paired_tie_count=sum(row["comparison"] == "tie" for row in pairs),
        requested_runs=iterations,
        started_runs=iterations,
        valid_runs=iterations,
        failed_runs=0,
        discarded_runs=0,
        actual_sample_size=iterations,
        seeds=tuple(as_int(row["seed"], field="seed") for row in pairs),
        worker_count=worker_count,
        validation_level="structural_only",
        paired_or_unpaired="paired",
        effect_size=paired_standardized_effect(differences),
        confidence_interval=interval,
        bootstrap_method="deterministic_paired_percentile_bootstrap_2000",
        holdout_definition="primary paired scenario; holdouts reported separately",
        worst_case_result=min(differences),
        scenario_weights="equal within this paired scenario",
        pilot_weights=f"single configured pilot: {pilot_config.strength.value}",
        multiple_testing_method="not_applicable_single_comparison; Holm required for ranked families",
        rounding_policy="unrounded internal values; presentation may round to six decimals",
        bayesian_shrunk_effect=bayesian_shrunk_mean(differences),
        distributionally_robust_lower_bound=distributionally_robust_lower_bound(differences),
        quantiles=quantile_summary(differences),
        paired_randomization_p_value=paired_randomization_p_value(
            differences, seed=derive_paired_seed(seed, pair_id, iterations + 2)
        ),
        monte_carlo_standard_error=monte_carlo_standard_error(differences),
        confidence_interval_interpretation=(
            "model-internal Monte Carlo uncertainty interval for the paired structural simulator; "
            "not an empirical Commander confidence interval"
        ),
        pairing_conditions={
            "common_random_numbers": True,
            "same_seeds": True,
            "same_seats": True,
            "same_pod_size": True,
            "same_opponent_assumptions": True,
            "same_pilot_configuration": True,
            "pod_size": 1 + len(opponents),
            "opponent_deck_ids": [deck.deck_id for deck in opponents],
            "pilot_strength": pilot_config.strength.value,
            "pilot_mode": pilot_config.mode.value,
            "seat_policy": "explicit_fixed"
            if starting_player_seat is not None
            else "deterministic_rotation",
            "starting_player_seat": starting_player_seat,
        },
    )


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
    starting_player_seat: int | None = None,
    workers: int = 1,
) -> tuple[PairedMetrics, list[dict[str, object]]]:
    pairs = run_paired_structural_observations(
        baseline=baseline,
        variant=variant,
        opponents=opponents,
        start_index=0,
        iterations=iterations,
        seed=seed,
        pilot_config=pilot_config,
        max_turns=max_turns,
        pair_id=pair_id,
        starting_player_seat=starting_player_seat,
        workers=workers,
    )
    metrics = aggregate_paired_observations(
        pairs,
        seed=seed,
        pair_id=pair_id,
        pilot_config=pilot_config,
        opponents=opponents,
        starting_player_seat=starting_player_seat,
        worker_count=workers,
    )
    return metrics, pairs
