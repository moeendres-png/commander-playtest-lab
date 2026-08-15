from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import fmean, pstdev
from typing import Any

from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength
from commander_lab.storage import sha256_value
from commander_lab.whole_deck.campaign import run_balanced_paired_campaign
from commander_lab.whole_deck.lab_context import enriched_context
from commander_lab.whole_deck.orchestrator import WholeDeckCampaignOrchestrator
from commander_lab.whole_deck.search_context import current_control_mainboard

MODEL_RESOLUTION_MEASUREMENT_VERSION = "model-resolution-measurement-0.1.0"


@dataclass(frozen=True, slots=True)
class ModelResolutionMeasurementProtocol:
    seed: int = 2026081517
    independent_seed_blocks: int = 4
    games_per_seed_block: int = 56
    pilot_axis_games: int = 56
    max_turns: int = 35
    workers: int = 2
    calibrated_sesoi: float = 0.05

    def __post_init__(self) -> None:
        if self.seed < 0:
            raise ValueError("seed must be non-negative")
        if self.independent_seed_blocks < 3:
            raise ValueError("at least three independent seed blocks are required")
        if self.games_per_seed_block < 8:
            raise ValueError("games_per_seed_block must be at least eight")
        if self.pilot_axis_games < 8:
            raise ValueError("pilot_axis_games must be at least eight")
        if self.max_turns < 1:
            raise ValueError("max_turns must be positive")
        if self.workers < 1:
            raise ValueError("workers must be positive")
        if self.calibrated_sesoi < 0.0:
            raise ValueError("calibrated_sesoi must be non-negative")

    @property
    def protocol_hash(self) -> str:
        return sha256_value(
            {
                "version": MODEL_RESOLUTION_MEASUREMENT_VERSION,
                **asdict(self),
            }
        )


def _numeric(row: dict[str, object], key: str) -> float:
    value = row.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"{key} must be numeric")
    return float(value)


def _baseline_observations(campaign: dict[str, object]) -> tuple[dict[str, object], ...]:
    raw = campaign.get("paired_observations")
    if not isinstance(raw, list):
        raise TypeError("campaign paired observations are malformed")
    rows = tuple(row for row in raw if isinstance(row, dict))
    if len(rows) != len(raw):
        raise TypeError("campaign paired observations contain malformed rows")
    return rows


def _baseline_average_placement(campaign: dict[str, object]) -> float:
    baseline = campaign.get("baseline")
    if not isinstance(baseline, dict):
        raise TypeError("campaign baseline summary is malformed")
    return _numeric(baseline, "average_placement")


def _group_spread(values: dict[str, list[float]]) -> tuple[dict[str, float], float | None]:
    means = {key: fmean(rows) for key, rows in sorted(values.items()) if rows}
    if len(means) < 2:
        return means, None
    return means, max(means.values()) - min(means.values())


def summarize_resolution_measurements(
    *,
    block_means: tuple[float, ...],
    observations: tuple[dict[str, object], ...],
    pilot_means: dict[str, float],
    calibrated_sesoi: float,
) -> dict[str, object]:
    """Summarize comparable resolution and non-comparable robustness axes.

    The seed-block range is measured on the same average-placement scale as
    `placement_improvement`. Seat, opponent-input and pilot spreads are reported as structural
    sensitivity axes and are deliberately not folded into the resolution threshold.
    """
    if len(block_means) < 3:
        raise ValueError("at least three independent block means are required")
    if not observations:
        raise ValueError("resolution summary requires structural observations")
    if calibrated_sesoi < 0.0:
        raise ValueError("calibrated_sesoi must be non-negative")

    seed_block_range = max(block_means) - min(block_means)
    seed_block_sd = pstdev(block_means)
    seed_block_mcse = seed_block_sd / math.sqrt(len(block_means))

    seat_rows: dict[str, list[float]] = defaultdict(list)
    opponent_group_rows: dict[str, list[float]] = defaultdict(list)
    placements: list[float] = []
    place_1: list[float] = []
    for row in observations:
        placement = _numeric(row, "baseline_placement")
        placements.append(placement)
        place_1.append(_numeric(row, "baseline_place_1"))
        seat_rows[str(row.get("own_seat"))].append(placement)
        raw_opponents = row.get("opponent_deck_ids")
        if not isinstance(raw_opponents, list):
            raise TypeError("opponent_deck_ids must be a list")
        opponent_group_rows["|".join(sorted(str(value) for value in raw_opponents))].append(
            placement
        )

    seat_means, seat_spread = _group_spread(seat_rows)
    opponent_group_means, opponent_group_spread = _group_spread(opponent_group_rows)
    pilot_spread = (
        max(pilot_means.values()) - min(pilot_means.values()) if len(pilot_means) >= 2 else None
    )

    distribution = Counter(int(value) for value in placements)
    placement_concentration = max(distribution.values()) / len(placements)
    unique_placements = len(distribution)
    seat_concentration = seat_spread is not None and seat_spread <= 0.15
    compression_limit = placement_concentration >= 0.90 and seat_concentration
    effective_resolution = max(calibrated_sesoi, seed_block_range)
    seat_sensitivity_material = seat_spread is not None and seat_spread > effective_resolution
    scenario_sensitivity_material = (
        opponent_group_spread is not None and opponent_group_spread > effective_resolution
    )
    pilot_sensitivity_material = pilot_spread is not None and pilot_spread > effective_resolution

    return {
        "status": "MEASURED",
        "metric": "placement_improvement",
        "metric_unit": "average_placement_positions",
        "calibrated_sesoi": calibrated_sesoi,
        "sampling_resolution": {
            "axis": "independent_null_seed_blocks",
            "block_means": list(block_means),
            "block_range": seed_block_range,
            "block_population_sd": seed_block_sd,
            "block_mean_mcse": seed_block_mcse,
            "evidence_class": "structural_model_estimates",
            "epistemic_class": "PRECISION_ONLY_SAME_MODEL",
        },
        "effective_resolution": effective_resolution,
        "effective_resolution_rule": (
            "max(calibrated_sesoi, independent_same-model_seed-block_range); "
            "robustness/input sensitivity axes are reported separately and are not averaged into "
            "the resolution threshold"
        ),
        "robustness_axis_spreads": {
            "seat_assignment": seat_spread,
            "admissible_opponent_group": opponent_group_spread,
            "pilot_policy": pilot_spread,
        },
        "robustness_axis_means": {
            "seat_assignment": seat_means,
            "admissible_opponent_group": opponent_group_means,
            "pilot_policy": dict(sorted(pilot_means.items())),
        },
        "robustness_materiality": {
            "seat_assignment_exceeds_sampling_resolution": seat_sensitivity_material,
            "admissible_opponent_group_exceeds_sampling_resolution": scenario_sensitivity_material,
            "pilot_policy_exceeds_sampling_resolution": pilot_sensitivity_material,
        },
        "decision_use": {
            "absolute_pooled_structural_claims_allowed": not seat_sensitivity_material,
            "paired_candidate_comparisons_allowed": True,
            "paired_candidate_conditions": [
                "same_seed",
                "same_own_seat",
                "same_opponent_seat_assignment",
                "balanced_own_seat_coverage",
                "report_seat_stratified_effect_consistency",
                "report_admissible_scenario_robustness",
            ],
            "seat_sensitivity_gate": (
                "REQUIRE_BALANCED_PAIRED_AND_SEAT_STRATIFIED_EVIDENCE"
                if seat_sensitivity_material
                else "STANDARD_PAIRED_EVIDENCE"
            ),
            "scenario_sensitivity_gate": (
                "REQUIRE_SCENARIO_ROBUSTNESS"
                if scenario_sensitivity_material
                else "STANDARD_SCENARIO_EVIDENCE"
            ),
            "pilot_sensitivity_gate": (
                "REQUIRE_PILOT_ROBUSTNESS"
                if pilot_sensitivity_material
                else "STANDARD_PILOT_EVIDENCE"
            ),
        },
        "starting_player_contract": {
            "campaign_runner_starting_player_seat_index": 0,
            "interpretation": (
                "physical seat 1 starts in Whole-Deck campaign matches; RogShai own seat rotates "
                "through balanced scenarios, so absolute seat effects are expected model inputs and "
                "must be controlled by same-seat pairing for deck comparisons"
            ),
        },
        "outcome_compression": {
            "status": "MODEL_INFORMATION_LIMIT" if compression_limit else "INFORMATIVE",
            "placement_distribution": {str(key): distribution[key] for key in sorted(distribution)},
            "unique_placement_values": unique_placements,
            "dominant_placement_share": placement_concentration,
            "place_1_share": fmean(place_1),
            "seat_spread": seat_spread,
            "folded_into_effective_resolution": False,
        },
        "unsupported_same_metric_axes": {
            "mulligan_policy": (
                "UNSUPPORTED_SEPARATELY: current Structural match runner does not expose a frozen "
                "mulligan-policy intervention on the same placement metric"
            ),
            "tie_quantization": (
                "DIAGNOSTIC_ONLY: integer placement compression is reported directly; no arbitrary "
                "numeric tie penalty is invented"
            ),
        },
    }


def _run_control_only_campaign(
    *,
    control: Any,
    orchestrator: WholeDeckCampaignOrchestrator,
    scenarios: tuple[Any, ...],
    pilot: PilotConfig,
    max_turns: int,
    workers: int,
    statistics_seed: int,
) -> dict[str, object]:
    # The paired runner is intentionally reused to avoid a second simulation path. Only the
    # baseline side is consumed for resolution measurement. The identical variant side is a
    # deterministic execution-control duplicate and is not interpreted as a zero-noise estimate.
    return run_balanced_paired_campaign(
        baseline=control,
        variant=control,
        opponent_profiles=orchestrator.opponents.profiles(),
        scenarios=scenarios,
        pilot_config=pilot,
        max_turns=max_turns,
        statistics_seed=statistics_seed,
        workers=workers,
    )


def measure_current_model_resolution(
    root: str | Path,
    *,
    protocol: ModelResolutionMeasurementProtocol | None = None,
) -> dict[str, object]:
    """Run a bounded, non-confirmatory Structural resolution measurement on current RogShai.

    This is technical calibration evidence only. It does not search candidates, change the deck,
    consume confirmatory evidence, or inspect sealed holdout evidence.
    """
    spec = protocol or ModelResolutionMeasurementProtocol()
    project = Path(root).resolve()
    context, _, _ = enriched_context(project)
    control = context.materialize(
        current_control_mainboard(project), label="model-resolution-current-control"
    )
    orchestrator = WholeDeckCampaignOrchestrator(project)
    strong = PilotConfig(
        strength=PilotStrength.STRONG,
        mode=PilotDecisionMode.DETERMINISTIC,
    )

    block_means: list[float] = []
    observations: list[dict[str, object]] = []
    block_reports: list[dict[str, object]] = []
    all_scenario_seeds: set[int] = set()
    for index in range(spec.independent_seed_blocks):
        block_seed = spec.seed + (index + 1) * 1_000_003
        scenarios = tuple(
            orchestrator.scheduler.schedule(spec.games_per_seed_block, seed=block_seed)
        )
        scenario_seeds = {row.seed for row in scenarios}
        if all_scenario_seeds & scenario_seeds:
            raise RuntimeError("independent resolution seed blocks overlap")
        all_scenario_seeds.update(scenario_seeds)
        campaign = _run_control_only_campaign(
            control=control,
            orchestrator=orchestrator,
            scenarios=scenarios,
            pilot=strong,
            max_turns=spec.max_turns,
            workers=spec.workers,
            statistics_seed=block_seed ^ 0x5245534F,
        )
        block_mean = _baseline_average_placement(campaign)
        block_means.append(block_mean)
        block_observations = _baseline_observations(campaign)
        observations.extend(block_observations)
        block_reports.append(
            {
                "block_index": index,
                "master_seed": block_seed,
                "games": len(block_observations),
                "average_placement": block_mean,
                "coverage_report": orchestrator.scheduler.coverage_report(scenarios),
                "paired_duplicate_interpretation": "execution_control_only",
            }
        )

    pilot_seed = spec.seed ^ 0x50494C4F
    pilot_scenarios = tuple(orchestrator.scheduler.schedule(spec.pilot_axis_games, seed=pilot_seed))
    if all_scenario_seeds & {row.seed for row in pilot_scenarios}:
        raise RuntimeError("pilot sensitivity scenarios overlap seed-resolution blocks")
    pilot_means: dict[str, float] = {}
    for label, pilot in (
        ("strong_deterministic", strong),
        (
            "average_deterministic",
            PilotConfig(
                strength=PilotStrength.AVERAGE,
                mode=PilotDecisionMode.DETERMINISTIC,
            ),
        ),
    ):
        campaign = _run_control_only_campaign(
            control=control,
            orchestrator=orchestrator,
            scenarios=pilot_scenarios,
            pilot=pilot,
            max_turns=spec.max_turns,
            workers=spec.workers,
            statistics_seed=pilot_seed ^ int(sha256_value(label)[:8], 16),
        )
        pilot_means[label] = _baseline_average_placement(campaign)

    summary = summarize_resolution_measurements(
        block_means=tuple(block_means),
        observations=tuple(observations),
        pilot_means=pilot_means,
        calibrated_sesoi=spec.calibrated_sesoi,
    )
    report = {
        "schema_version": "1.0.0",
        "measurement_version": MODEL_RESOLUTION_MEASUREMENT_VERSION,
        "protocol": {**asdict(spec), "protocol_hash": spec.protocol_hash},
        "deck_id": "rogshai/current",
        "deck_hash": control.deck_hash,
        "data_snapshot_hash": control.data_snapshot_hash,
        "opponent_registry_hash": orchestrator.opponents.registry_hash,
        "opponent_deck_ids": list(orchestrator.opponents.current_deck_ids()),
        "evidence_context": "technical_model_resolution_calibration",
        "evidence_class": "structural_model_estimates",
        "truth_boundary": (
            "measured same-model Structural resolution and sensitivity only; not empirical Commander "
            "performance, not a local opponent-frequency estimate, and not an external rules engine"
        ),
        "confirmatory_evidence_consumed": False,
        "sealed_holdout_evidence_consumed": False,
        "candidate_search_performed": False,
        "canonical_deck_mutation": False,
        "official_rogshai_optimizer_run": False,
        "seed_blocks": block_reports,
        "pilot_axis": {
            "master_seed": pilot_seed,
            "games_per_pilot": spec.pilot_axis_games,
            "means": dict(sorted(pilot_means.items())),
            "coverage_report": orchestrator.scheduler.coverage_report(pilot_scenarios),
        },
        **summary,
    }
    return {"report_hash": sha256_value(report), **report}


__all__ = [
    "MODEL_RESOLUTION_MEASUREMENT_VERSION",
    "ModelResolutionMeasurementProtocol",
    "measure_current_model_resolution",
    "summarize_resolution_measurements",
]
