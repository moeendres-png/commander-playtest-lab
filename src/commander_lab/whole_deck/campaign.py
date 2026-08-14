from __future__ import annotations

import math
import multiprocessing
import os
import time
from collections import Counter, defaultdict
from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
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
from commander_lab.engine.structural import StructuralSimulator
from commander_lab.models import (
    PilotConfig,
    StructuralAbortLimits,
    StructuralDeckProfile,
    StructuralMatchConfig,
)
from commander_lab.pod_scheduling import PodScenario

_CAMPAIGN_BASELINE: StructuralDeckProfile | None = None
_CAMPAIGN_VARIANT: StructuralDeckProfile | None = None
_CAMPAIGN_OPPONENTS: dict[str, StructuralDeckProfile] = {}


def _numeric_float(value: object, *, field: str) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    raise TypeError(f"{field} must be numeric")


def _numeric_int(value: object, *, field: str) -> int:
    if isinstance(value, int):
        return value
    raise TypeError(f"{field} must be an integer")


def _string_tuple(value: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise TypeError(f"{field} must be a sequence")
    return tuple(str(item) for item in value)


def _initialize_campaign_worker(
    baseline: dict[str, Any],
    variant: dict[str, Any],
    opponents: list[dict[str, Any]],
) -> None:
    global _CAMPAIGN_BASELINE, _CAMPAIGN_VARIANT, _CAMPAIGN_OPPONENTS
    _CAMPAIGN_BASELINE = StructuralDeckProfile.model_validate(baseline)
    _CAMPAIGN_VARIANT = StructuralDeckProfile.model_validate(variant)
    parsed = [StructuralDeckProfile.model_validate(row) for row in opponents]
    _CAMPAIGN_OPPONENTS = {deck.deck_id: deck for deck in parsed}


def _seated_decks(
    own: StructuralDeckProfile,
    opponents: dict[str, StructuralDeckProfile],
    scenario: PodScenario,
) -> tuple[StructuralDeckProfile, ...]:
    seats: list[StructuralDeckProfile | None] = [None, None, None, None]
    seats[scenario.own_seat - 1] = own
    for seat, deck_id in scenario.opponent_seat_assignment:
        seats[seat - 1] = opponents[deck_id]
    if any(deck is None for deck in seats):
        raise ValueError(f"scenario {scenario.scenario_id} does not fill all four seats")
    return tuple(deck for deck in seats if deck is not None)


def _simulate_one(
    own: StructuralDeckProfile,
    opponents: dict[str, StructuralDeckProfile],
    scenario: PodScenario,
    *,
    pilot_config: PilotConfig,
    max_turns: int,
    suffix: str,
) -> dict[str, object]:
    seated = _seated_decks(own, opponents, scenario)
    deck_ids = tuple(deck.deck_id for deck in seated)
    if len(deck_ids) != 4 or len(set(deck_ids)) != 4:
        raise ValueError("primary Whole-Deck scenario must contain four distinct decks")
    result = StructuralSimulator({deck.deck_id: deck for deck in seated}).simulate(
        StructuralMatchConfig(
            match_id=f"{scenario.scenario_id}-{suffix}",
            deck_ids=deck_ids,
            limits=StructuralAbortLimits(max_turns=max_turns),
            seed=scenario.seed,
            starting_player_seat=0,
            pilot_configs=(pilot_config,) * 4,
        ),
        run_id=f"balanced4p-{suffix}",
    )
    own_metrics = result.player_metrics[f"p{scenario.own_seat}"]
    return {
        "placement": float(own_metrics.placement),
        "place_1": float(own_metrics.placement == 1),
        "damage": float(own_metrics.normal_damage_dealt + own_metrics.commander_damage_dealt),
        "cards_drawn": float(own_metrics.cards_drawn),
        "log_sha256": result.log_sha256,
    }


def _run_scenario_worker(payload: dict[str, Any]) -> dict[str, object]:
    if _CAMPAIGN_BASELINE is None or _CAMPAIGN_VARIANT is None:
        raise RuntimeError("balanced campaign worker was not initialized")
    raw_opponents = tuple(str(value) for value in payload["opponent_deck_ids"])
    if len(raw_opponents) != 3:
        raise ValueError("balanced campaign scenario requires exactly three opponents")
    opponent_deck_ids = (raw_opponents[0], raw_opponents[1], raw_opponents[2])
    scenario = PodScenario(
        scenario_id=str(payload["scenario_id"]),
        cycle_id=int(payload["cycle_id"]),
        opponent_deck_ids=opponent_deck_ids,
        own_seat=int(payload["own_seat"]),
        opponent_seat_assignment=tuple(
            (int(seat), str(deck_id)) for seat, deck_id in payload["opponent_seat_assignment"]
        ),
        seed=int(payload["seed"]),
        opponent_registry_hash=str(payload["opponent_registry_hash"]),
    )
    index = int(payload["index"])
    pilot = PilotConfig.model_validate(payload["pilot_config"])
    max_turns = int(payload["max_turns"])
    baseline_row = _simulate_one(
        _CAMPAIGN_BASELINE,
        _CAMPAIGN_OPPONENTS,
        scenario,
        pilot_config=pilot,
        max_turns=max_turns,
        suffix=f"baseline-{index:05d}",
    )
    variant_row = _simulate_one(
        _CAMPAIGN_VARIANT,
        _CAMPAIGN_OPPONENTS,
        scenario,
        pilot_config=pilot,
        max_turns=max_turns,
        suffix=f"variant-{index:05d}",
    )
    return {
        "index": index,
        "scenario_id": scenario.scenario_id,
        "cycle_id": scenario.cycle_id,
        "seed": scenario.seed,
        "own_seat": scenario.own_seat,
        "opponent_deck_ids": list(scenario.opponent_deck_ids),
        "opponent_seat_assignment": {
            str(seat): deck_id for seat, deck_id in scenario.opponent_seat_assignment
        },
        "baseline_placement": baseline_row["placement"],
        "variant_placement": variant_row["placement"],
        "baseline_place_1": baseline_row["place_1"],
        "variant_place_1": variant_row["place_1"],
        "baseline_damage": baseline_row["damage"],
        "variant_damage": variant_row["damage"],
        "baseline_cards_drawn": baseline_row["cards_drawn"],
        "variant_cards_drawn": variant_row["cards_drawn"],
        "baseline_log_sha256": baseline_row["log_sha256"],
        "variant_log_sha256": variant_row["log_sha256"],
        "candidate_isolation": True,
    }


def _mean_ci(values: tuple[float, ...], *, seed: int) -> tuple[float, float]:
    if len(values) == 1:
        return values[0], values[0]
    return paired_bootstrap_interval(values, seed=seed)


def _single_deck_summary(
    observations: tuple[dict[str, object], ...],
    *,
    prefix: str,
    seed: int,
) -> dict[str, object]:
    placements = tuple(
        _numeric_float(row[f"{prefix}_placement"], field=f"{prefix}_placement")
        for row in observations
    )
    place_1 = tuple(
        _numeric_float(row[f"{prefix}_place_1"], field=f"{prefix}_place_1")
        for row in observations
    )
    placement_distribution = Counter(int(value) for value in placements)
    per_opponent: dict[str, list[float]] = defaultdict(list)
    per_triple: dict[str, list[float]] = defaultdict(list)
    per_seat: dict[int, list[float]] = defaultdict(list)
    for row in observations:
        placement = _numeric_float(row[f"{prefix}_placement"], field=f"{prefix}_placement")
        opponents = _string_tuple(row["opponent_deck_ids"], field="opponent_deck_ids")
        for opponent in opponents:
            per_opponent[opponent].append(placement)
        per_triple["|".join(sorted(opponents))].append(placement)
        per_seat[_numeric_int(row["own_seat"], field="own_seat")].append(placement)
    ci = _mean_ci(place_1, seed=seed)
    return {
        "games": len(observations),
        "structural_model_estimated_place_1_share": fmean(place_1),
        "place_1_share_model_interval": ci,
        "place_1_share_mcse": monte_carlo_standard_error(place_1),
        "average_placement": fmean(placements),
        "placement_mcse": monte_carlo_standard_error(placements),
        "placement_distribution": {
            str(place): placement_distribution.get(place, 0) for place in range(1, 5)
        },
        "per_opponent_average_placement": {
            opponent: fmean(values) for opponent, values in sorted(per_opponent.items())
        },
        "per_triple_average_placement": {
            triple: fmean(values) for triple, values in sorted(per_triple.items())
        },
        "per_seat_average_placement": {
            str(seat): fmean(values) for seat, values in sorted(per_seat.items())
        },
        "worst_opponent_triple_average_placement": max(
            fmean(values) for values in per_triple.values()
        ),
        "lower_tail_placement_q90": quantile_summary(placements)["q90"],
    }


def run_balanced_paired_campaign(
    *,
    baseline: StructuralDeckProfile,
    variant: StructuralDeckProfile,
    opponent_profiles: dict[str, StructuralDeckProfile],
    scenarios: Iterable[PodScenario],
    pilot_config: PilotConfig,
    max_turns: int,
    statistics_seed: int,
    workers: int = 1,
) -> dict[str, object]:
    """Evaluate baseline and variant in separate games under identical balanced scenarios."""
    scenario_rows = tuple(scenarios)
    if not scenario_rows:
        raise ValueError("balanced campaign requires scenarios")
    if workers < 1:
        raise ValueError("workers must be positive")
    started = time.perf_counter()
    tasks = [
        {
            "index": index,
            "scenario_id": scenario.scenario_id,
            "cycle_id": scenario.cycle_id,
            "opponent_deck_ids": list(scenario.opponent_deck_ids),
            "own_seat": scenario.own_seat,
            "opponent_seat_assignment": list(scenario.opponent_seat_assignment),
            "seed": scenario.seed,
            "opponent_registry_hash": scenario.opponent_registry_hash,
            "pilot_config": pilot_config.model_dump(mode="json"),
            "max_turns": max_turns,
        }
        for index, scenario in enumerate(scenario_rows)
    ]
    initializer_args = (
        baseline.model_dump(mode="json"),
        variant.model_dump(mode="json"),
        [deck.model_dump(mode="json") for deck in opponent_profiles.values()],
    )
    if workers == 1:
        _initialize_campaign_worker(*initializer_args)
        observations = [_run_scenario_worker(task) for task in tasks]
    elif "PYTEST_CURRENT_TEST" in os.environ:
        _initialize_campaign_worker(*initializer_args)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            observations = list(executor.map(_run_scenario_worker, tasks))
    else:
        chunksize = max(1, len(tasks) // (workers * 4))
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=_initialize_campaign_worker,
            initargs=initializer_args,
            mp_context=multiprocessing.get_context("spawn"),
        ) as executor:
            observations = list(executor.map(_run_scenario_worker, tasks, chunksize=chunksize))
    rows = tuple(
        sorted(observations, key=lambda row: _numeric_int(row["index"], field="index"))
    )
    differences = tuple(
        _numeric_float(row["baseline_placement"], field="baseline_placement")
        - _numeric_float(row["variant_placement"], field="variant_placement")
        for row in rows
    )
    place_1_differences = tuple(
        _numeric_float(row["variant_place_1"], field="variant_place_1")
        - _numeric_float(row["baseline_place_1"], field="baseline_place_1")
        for row in rows
    )
    baseline_summary = _single_deck_summary(rows, prefix="baseline", seed=statistics_seed + 11)
    variant_summary = _single_deck_summary(rows, prefix="variant", seed=statistics_seed + 17)
    interval = paired_bootstrap_interval(differences, seed=statistics_seed + 23)
    paired = {
        "games": len(rows),
        "placement_improvement": fmean(differences),
        "paired_placement_delta": fmean(differences),
        "place_1_share_delta": fmean(place_1_differences),
        "paired_effect_size": paired_standardized_effect(differences),
        "paired_bootstrap_interval": interval,
        "paired_randomization_p_value": paired_randomization_p_value(
            differences, seed=statistics_seed + 29
        ),
        "monte_carlo_standard_error": monte_carlo_standard_error(differences),
        "robust_lower_bound": distributionally_robust_lower_bound(differences),
        "bayesian_shrunk_effect": bayesian_shrunk_mean(differences),
        "difference_quantiles": quantile_summary(differences),
        "paired_variant_better_count": sum(value > 0 for value in differences),
        "paired_variant_worse_count": sum(value < 0 for value in differences),
        "paired_tie_count": sum(math.isclose(value, 0.0) for value in differences),
        "uncertainty_interpretation": (
            "model-internal Monte Carlo uncertainty under structural simulation; not empirical "
            "Commander win-rate evidence"
        ),
    }
    return {
        "evidence_class": "structural_model_estimates",
        "baseline": baseline_summary,
        "variant": variant_summary,
        "paired": paired,
        "paired_observations": list(rows),
        "pairing_conditions": {
            "candidates_share_match": False,
            "same_scenarios": True,
            "same_match_seeds": True,
            "same_own_seats": True,
            "same_opponent_seat_assignments": True,
            "same_pilot_configuration": True,
            "same_turn_cap": True,
            "common_random_numbers": True,
        },
        "worker_count": workers,
        "runtime_seconds": time.perf_counter() - started,
    }
