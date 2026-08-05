from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import fmean, median
from typing import Iterable, Mapping, Sequence

from commander_lab.models import (
    CalibrationParameterResult,
    CalibrationReport,
    CalibrationStatus,
    CategoryEstimate,
    DistributionSummary,
    EvidenceSplit,
    MetricComparison,
    ParameterDecision,
    PlaytestDatasetManifest,
    RealPlaytest,
    SplitStrategy,
    StructuralBatchResult,
)
from commander_lab.storage import sha256_value


NUMERIC_METRICS = (
    "game_turns",
    "commander_cast_turn",
    "removal_events",
    "boardwipes",
    "ishai_peak_power",
    "korvold_draws",
    "archenemy_frequency",
    "placement",
)

PARAMETER_MAP = {
    "game_turns": "game_length_multiplier",
    "commander_cast_turn": "commander_cast_timing_multiplier",
    "removal_events": "removal_frequency_multiplier",
    "boardwipes": "boardwipe_frequency_multiplier",
    "ishai_peak_power": "ishai_growth_multiplier",
    "korvold_draws": "korvold_draw_multiplier",
    "archenemy_frequency": "archenemy_pressure_multiplier",
}


@dataclass(frozen=True, slots=True)
class CalibrationPolicy:
    policy_version: str = "1.0.0"
    train_fraction: float = 0.7
    split_strategy: SplitStrategy = SplitStrategy.CHRONOLOGICAL
    split_seed: int = 20260805
    confidence_level: float = 0.95
    bootstrap_samples: int = 1000
    minimum_train_games: int = 20
    minimum_validation_games: int = 8
    minimum_train_observations: int = 12
    minimum_validation_observations: int = 5
    minimum_validation_improvement: float = 0.05
    prior_strength: float = 20.0
    minimum_multiplier: float = 0.5
    maximum_multiplier: float = 2.0


@dataclass(frozen=True, slots=True)
class Observation:
    source_id: str
    deck_key: str
    deck_version: str
    split: EvidenceSplit
    metrics: Mapping[str, float | None]
    win_axis: str | None = None
    loss_causes: tuple[str, ...] = ()


def deck_key(deck_name: str, commander_names: Iterable[str] = ()) -> str:
    text = " ".join((deck_name, *commander_names)).casefold()
    if "korvold" in text:
        return "korvold"
    if "rogshai" in text or ("ishai" in text and "rograkh" in text):
        return "rogshai"
    compact = "-".join(part for part in deck_name.casefold().replace("/", " ").split() if part)
    return compact or "unknown"


def assign_playtest_splits(
    games: Sequence[RealPlaytest],
    *,
    strategy: SplitStrategy,
    train_fraction: float,
    seed: int,
) -> dict[str, EvidenceSplit]:
    if not 0.0 < train_fraction < 1.0:
        raise ValueError("train_fraction must be between zero and one")
    eligible = [game for game in games if game.validated and not game.excluded_reason]
    assignments = {
        game.game_id: EvidenceSplit.EXCLUDED
        for game in games
        if game not in eligible
    }
    if not eligible:
        return assignments

    if strategy is SplitStrategy.CHRONOLOGICAL:
        ordered = sorted(
            eligible,
            key=lambda game: (game.played_on is None, game.played_on, game.game_id),
        )
    else:
        ordered = sorted(
            eligible,
            key=lambda game: hashlib.sha256(
                f"{seed}|{game.dataset_version}|{game.game_id}".encode()
            ).hexdigest(),
        )

    if len(ordered) == 1:
        assignments[ordered[0].game_id] = EvidenceSplit.TRAIN
        return assignments
    train_count = round(len(ordered) * train_fraction)
    train_count = min(len(ordered) - 1, max(1, train_count))
    for index, game in enumerate(ordered):
        assignments[game.game_id] = (
            EvidenceSplit.TRAIN if index < train_count else EvidenceSplit.VALIDATION
        )
    return assignments


def real_observations(
    games: Sequence[RealPlaytest],
    assignments: Mapping[str, EvidenceSplit],
) -> list[Observation]:
    observations: list[Observation] = []
    for game in games:
        split = assignments.get(game.game_id, EvidenceSplit.EXCLUDED)
        if split is EvidenceSplit.EXCLUDED:
            continue
        for participant in game.participants:
            key = deck_key(participant.deck_name, participant.commander_names)
            observations.append(
                Observation(
                    source_id=f"{game.game_id}:{participant.player_id}",
                    deck_key=key,
                    deck_version=participant.deck_version,
                    split=split,
                    metrics={
                        "game_turns": _float(game.turns),
                        "commander_cast_turn": _float(participant.first_commander_cast_turn),
                        "removal_events": _float(participant.removal_events),
                        "boardwipes": _float(participant.boardwipes_cast),
                        "ishai_peak_power": _float(participant.ishai_peak_power),
                        "korvold_draws": _float(participant.korvold_cards_drawn),
                        "archenemy_frequency": (
                            float(participant.was_archenemy)
                            if participant.was_archenemy is not None
                            else None
                        ),
                        "placement": _float(participant.placement),
                    },
                    win_axis=participant.win_axis if participant.placement == 1 else None,
                    loss_causes=tuple(participant.loss_causes),
                )
            )
    return observations


def load_structural_batches(paths: Iterable[str | Path]) -> tuple[list[StructuralBatchResult], dict[str, str]]:
    files: list[Path] = []
    for raw in paths:
        path = Path(raw).resolve()
        if path.is_dir():
            files.extend(sorted(path.rglob("structural_results.json")))
        elif path.is_file():
            files.append(path)
        else:
            raise FileNotFoundError(path)
    batches: list[StructuralBatchResult] = []
    hashes: dict[str, str] = {}
    for path in sorted(set(files)):
        raw = path.read_bytes()
        hashes[str(path)] = hashlib.sha256(raw).hexdigest()
        payload = json.loads(raw)
        if isinstance(payload, dict) and "result" in payload and "match_results" in payload["result"]:
            payload = payload["result"]
        batches.append(StructuralBatchResult.model_validate(payload))
    return batches, hashes


def simulated_observations(
    batches: Sequence[StructuralBatchResult],
    *,
    train_fraction: float,
    split_seed: int,
) -> list[Observation]:
    observations: list[Observation] = []
    for batch in batches:
        for match in batch.match_results:
            if match.aborted or not match.completed:
                continue
            digest = hashlib.sha256(
                f"sim|{split_seed}|{batch.run_id}|{match.match_id}".encode()
            ).digest()
            fraction = int.from_bytes(digest[:8], "big") / 2**64
            split = (
                EvidenceSplit.TRAIN if fraction < train_fraction else EvidenceSplit.VALIDATION
            )
            for metrics in match.player_metrics.values():
                key = deck_key(metrics.deck_id, metrics.commander_peak_power)
                observations.append(
                    Observation(
                        source_id=f"{match.match_id}:{metrics.player_id}",
                        deck_key=key,
                        deck_version="structural-current",
                        split=split,
                        metrics={
                            "game_turns": float(match.turns),
                            "commander_cast_turn": _float(metrics.first_commander_cast_turn),
                            "removal_events": float(metrics.removals_resolved),
                            "boardwipes": float(metrics.wipes_resolved),
                            "ishai_peak_power": float(metrics.ishai_peak_power),
                            "korvold_draws": float(metrics.korvold_cards_drawn),
                            "archenemy_frequency": float(metrics.was_archenemy),
                            "placement": float(metrics.placement),
                        },
                        win_axis=_simulated_win_axis(match.end_reason, metrics) if metrics.placement == 1 else None,
                        loss_causes=(metrics.elimination_reason,) if metrics.elimination_reason else (),
                    )
                )
    return observations


def calibrate_playtests(
    *,
    manifest: PlaytestDatasetManifest,
    games: Sequence[RealPlaytest],
    simulation_batches: Sequence[StructuralBatchResult],
    simulation_source_hashes: Mapping[str, str],
    policy: CalibrationPolicy,
    target_deck_versions: Mapping[str, str] | None = None,
) -> CalibrationReport:
    assignments = dict(manifest.split_assignments)
    real = real_observations(games, assignments)
    target_deck_versions = dict(target_deck_versions or {})
    version_sets: dict[str, set[str]] = defaultdict(set)
    for item in real:
        if item.deck_key in {"korvold", "rogshai"}:
            version_sets[item.deck_key].add(item.deck_version)
    version_conflicts = {
        key: tuple(sorted(versions))
        for key, versions in version_sets.items()
        if key not in target_deck_versions and len(versions) > 1
    }
    real = [
        item
        for item in real
        if item.deck_key not in target_deck_versions
        or item.deck_version == target_deck_versions[item.deck_key]
    ]
    simulated = simulated_observations(
        simulation_batches,
        train_fraction=policy.train_fraction,
        split_seed=policy.split_seed,
    )
    deck_keys = sorted(
        {
            item.deck_key
            for item in real
            if item.deck_key in {"korvold", "rogshai"}
            and item.deck_key not in version_conflicts
        }
    )
    comparisons: list[MetricComparison] = []
    parameters: list[CalibrationParameterResult] = []
    accepted: dict[str, float] = {}

    for key in deck_keys:
        for metric in NUMERIC_METRICS:
            if metric == "ishai_peak_power" and key != "rogshai":
                continue
            if metric == "korvold_draws" and key != "korvold":
                continue
            for split in (EvidenceSplit.TRAIN, EvidenceSplit.VALIDATION):
                real_values, real_missing = _metric_values(real, key, metric, split)
                sim_values, sim_missing = _metric_values(simulated, key, metric, split)
                real_summary = summarize_distribution(
                    real_values,
                    missing=real_missing,
                    confidence_level=policy.confidence_level,
                    bootstrap_samples=policy.bootstrap_samples,
                    seed=_stable_seed(policy.split_seed, key, metric, split.value, "real"),
                )
                sim_summary = summarize_distribution(
                    sim_values,
                    missing=sim_missing,
                    confidence_level=policy.confidence_level,
                    bootstrap_samples=policy.bootstrap_samples,
                    seed=_stable_seed(policy.split_seed, key, metric, split.value, "sim"),
                )
                status = "available"
                if not real_values:
                    status = "insufficient_real"
                elif not sim_values:
                    status = "insufficient_simulated"
                comparisons.append(
                    MetricComparison(
                        deck_key=key,
                        metric=metric,
                        split=split,
                        real=real_summary,
                        simulated=sim_summary,
                        mean_delta_real_minus_simulated=(
                            real_summary.mean - sim_summary.mean
                            if real_summary.mean is not None and sim_summary.mean is not None
                            else None
                        ),
                        comparison_status=status,
                    )
                )

            if metric in PARAMETER_MAP:
                result = _calibrate_parameter(
                    key=key,
                    metric=metric,
                    real=real,
                    simulated=simulated,
                    policy=policy,
                )
                parameters.append(result)
                if result.accepted_value is not None:
                    accepted[f"{key}.{result.parameter_name}"] = result.accepted_value

    train_ids = tuple(
        sorted(game_id for game_id, split in assignments.items() if split is EvidenceSplit.TRAIN)
    )
    validation_ids = tuple(
        sorted(game_id for game_id, split in assignments.items() if split is EvidenceSplit.VALIDATION)
    )
    excluded_ids = tuple(
        sorted(game_id for game_id, split in assignments.items() if split is EvidenceSplit.EXCLUDED)
    )
    status = _report_status(parameters, train_ids, validation_ids, simulation_batches, policy)
    policy_payload = asdict(policy)
    policy_hash = sha256_value(policy_payload)
    calibration_id = sha256_value(
        {
            "dataset_hash": manifest.data_hash,
            "simulation_hashes": dict(sorted(simulation_source_hashes.items())),
            "split": assignments,
            "policy": policy_payload,
            "target_deck_versions": target_deck_versions,
        }
    )[:20]
    simulated_matches_total = sum(len(batch.match_results) for batch in simulation_batches)
    simulated_matches_used = sum(
        1
        for batch in simulation_batches
        for match in batch.match_results
        if match.completed and not match.aborted
    )
    simulated_exclusion_reasons: Counter[str] = Counter()
    for batch in simulation_batches:
        for match in batch.match_results:
            if match.aborted:
                simulated_exclusion_reasons[match.abort_reason or "aborted_unspecified"] += 1
            elif not match.completed:
                simulated_exclusion_reasons["not_completed"] += 1

    warnings = [
        "Validation games are an internal holdout and are not independent external confirmation.",
        "Training games are never reused as validation evidence.",
        "Accepted parameters are written to a calibration profile only; engine defaults are unchanged.",
        "Real playtests cannot validate comprehensive Magic rules while external_engine_validation_pending=true.",
    ]
    if version_conflicts:
        warnings.append(
            "Multiple real deck versions were present without an explicit target; affected decks were not calibrated: "
            + ", ".join(f"{key}={list(values)}" for key, values in sorted(version_conflicts.items()))
        )
    if not simulation_batches:
        warnings.append("No structural simulation reference was provided; no parameter can be calibrated.")
    if simulated_matches_total != simulated_matches_used:
        warnings.append(
            f"Excluded {simulated_matches_total - simulated_matches_used} aborted or incomplete "
            "structural matches from calibration distributions."
        )
    if len(train_ids) < policy.minimum_train_games:
        warnings.append(
            f"Only {len(train_ids)} training games; policy requires {policy.minimum_train_games}."
        )
    if len(validation_ids) < policy.minimum_validation_games:
        warnings.append(
            f"Only {len(validation_ids)} validation games; policy requires {policy.minimum_validation_games}."
        )

    return CalibrationReport(
        calibration_id=calibration_id,
        created_at=datetime.now(UTC),
        dataset_id=manifest.dataset_id,
        dataset_version=manifest.dataset_version,
        dataset_hash=manifest.data_hash,
        policy_version=policy.policy_version,
        policy_hash=policy_hash,
        target_deck_versions=dict(sorted(target_deck_versions.items())),
        version_conflicts=version_conflicts,
        simulation_source_hashes=dict(sorted(simulation_source_hashes.items())),
        simulation_run_ids=tuple(sorted(batch.run_id for batch in simulation_batches)),
        simulation_master_seeds=tuple(sorted(batch.master_seed for batch in simulation_batches)),
        simulation_estimate_types=tuple(
            sorted({batch.estimate_type for batch in simulation_batches})
        ),
        simulated_matches_total=simulated_matches_total,
        simulated_matches_used=simulated_matches_used,
        simulated_matches_excluded=simulated_matches_total - simulated_matches_used,
        simulated_exclusion_reasons=dict(sorted(simulated_exclusion_reasons.items())),
        split_strategy=manifest.split_strategy or policy.split_strategy,
        split_seed=manifest.split_seed if manifest.split_seed is not None else policy.split_seed,
        train_game_ids=train_ids,
        validation_game_ids=validation_ids,
        excluded_game_ids=excluded_ids,
        status=status,
        comparisons=tuple(comparisons),
        categorical_real=_categorical_summaries(real, policy.confidence_level),
        categorical_simulated=_categorical_summaries(simulated, policy.confidence_level),
        parameter_results=tuple(parameters),
        accepted_parameters=dict(sorted(accepted.items())),
        confidence_level=policy.confidence_level,
        bootstrap_samples=policy.bootstrap_samples,
        warnings=tuple(warnings),
        methodology=(
            "A dataset split is sealed before model comparison.",
            "Parameter proposals use shrunken real-to-simulated mean ratios.",
            "Training mean differences must have a bootstrap interval excluding zero.",
            "A proposal is accepted only when it improves error on unused validation games.",
            "No parameter is inferred from a single game or automatically applied to canonical models.",
        ),
    )


def summarize_distribution(
    values: Sequence[float],
    *,
    missing: int,
    confidence_level: float,
    bootstrap_samples: int,
    seed: int,
) -> DistributionSummary:
    if not values:
        return DistributionSummary(
            observations=0,
            missing=missing,
            confidence_level=confidence_level,
        )
    ordered = sorted(float(value) for value in values)
    interval = _bootstrap_mean_interval(
        ordered,
        confidence_level=confidence_level,
        samples=bootstrap_samples,
        seed=seed,
    )
    return DistributionSummary(
        observations=len(ordered),
        missing=missing,
        mean=fmean(ordered),
        median=median(ordered),
        minimum=ordered[0],
        maximum=ordered[-1],
        q25=_quantile(ordered, 0.25),
        q75=_quantile(ordered, 0.75),
        confidence_level=confidence_level,
        mean_interval=interval,
    )


def _calibrate_parameter(
    *,
    key: str,
    metric: str,
    real: Sequence[Observation],
    simulated: Sequence[Observation],
    policy: CalibrationPolicy,
) -> CalibrationParameterResult:
    train_real, _ = _metric_values(real, key, metric, EvidenceSplit.TRAIN)
    validation_real, _ = _metric_values(real, key, metric, EvidenceSplit.VALIDATION)
    train_sim, _ = _metric_values(simulated, key, metric, EvidenceSplit.TRAIN)
    validation_sim, _ = _metric_values(simulated, key, metric, EvidenceSplit.VALIDATION)
    counts = {
        "train_real_observations": len(train_real),
        "validation_real_observations": len(validation_real),
        "train_simulated_observations": len(train_sim),
        "validation_simulated_observations": len(validation_sim),
    }
    rationale: list[str] = []
    if (
        len(train_real) < policy.minimum_train_observations
        or len(validation_real) < policy.minimum_validation_observations
        or len(train_sim) < policy.minimum_train_observations
        or len(validation_sim) < policy.minimum_validation_observations
    ):
        rationale.append("Per-metric train or validation evidence is below the configured threshold.")
        return CalibrationParameterResult(
            deck_key=key,
            metric=metric,
            parameter_name=PARAMETER_MAP[metric],
            decision=ParameterDecision.INSUFFICIENT_EVIDENCE,
            rationale=tuple(rationale),
            **counts,
        )

    real_mean = fmean(train_real)
    sim_mean = fmean(train_sim)
    if abs(sim_mean) < 1e-9:
        rationale.append("The simulated training mean is zero, so a bounded ratio is undefined.")
        return CalibrationParameterResult(
            deck_key=key,
            metric=metric,
            parameter_name=PARAMETER_MAP[metric],
            decision=ParameterDecision.INSUFFICIENT_EVIDENCE,
            rationale=tuple(rationale),
            **counts,
        )

    difference_interval = _bootstrap_difference_interval(
        train_real,
        train_sim,
        confidence_level=policy.confidence_level,
        samples=policy.bootstrap_samples,
        seed=_stable_seed(policy.split_seed, key, metric, "difference"),
    )
    if difference_interval[0] <= 0.0 <= difference_interval[1]:
        rationale.append("The training difference interval includes zero; no stable calibration signal.")
        return CalibrationParameterResult(
            deck_key=key,
            metric=metric,
            parameter_name=PARAMETER_MAP[metric],
            decision=ParameterDecision.NO_SIGNAL,
            train_difference_interval=difference_interval,
            rationale=tuple(rationale),
            **counts,
        )

    raw_ratio = real_mean / sim_mean
    weight = len(train_real) / (len(train_real) + policy.prior_strength)
    proposed = 1.0 + weight * (raw_ratio - 1.0)
    proposed = min(policy.maximum_multiplier, max(policy.minimum_multiplier, proposed))
    validation_real_mean = fmean(validation_real)
    validation_sim_mean = fmean(validation_sim)
    before = abs(validation_real_mean - validation_sim_mean)
    after = abs(validation_real_mean - validation_sim_mean * proposed)
    improvement = (before - after) / max(before, 1e-9)
    if improvement >= policy.minimum_validation_improvement:
        decision = ParameterDecision.ACCEPTED_INTERNAL_HOLDOUT
        accepted = proposed
        rationale.append(
            "The shrunken training ratio improved error on the sealed internal validation split."
        )
    else:
        decision = ParameterDecision.REJECTED_VALIDATION
        accepted = None
        rationale.append(
            "The training-derived proposal did not improve the sealed validation split enough."
        )
    return CalibrationParameterResult(
        deck_key=key,
        metric=metric,
        parameter_name=PARAMETER_MAP[metric],
        decision=decision,
        proposed_value=proposed,
        accepted_value=accepted,
        train_difference_interval=difference_interval,
        validation_error_before=before,
        validation_error_after=after,
        validation_improvement_fraction=improvement,
        rationale=tuple(rationale),
        **counts,
    )


def _report_status(
    parameters: Sequence[CalibrationParameterResult],
    train_ids: Sequence[str],
    validation_ids: Sequence[str],
    batches: Sequence[StructuralBatchResult],
    policy: CalibrationPolicy,
) -> CalibrationStatus:
    if not train_ids or not batches:
        return CalibrationStatus.INSUFFICIENT_EVIDENCE
    if len(train_ids) < policy.minimum_train_games or len(validation_ids) < policy.minimum_validation_games:
        return CalibrationStatus.INSUFFICIENT_EVIDENCE
    if any(result.decision is ParameterDecision.ACCEPTED_INTERNAL_HOLDOUT for result in parameters):
        return CalibrationStatus.VALIDATED_INTERNAL_HOLDOUT
    if any(result.decision is ParameterDecision.REJECTED_VALIDATION for result in parameters):
        return CalibrationStatus.REJECTED_ON_VALIDATION
    if any(result.proposed_value is not None for result in parameters):
        return CalibrationStatus.PROVISIONAL
    return CalibrationStatus.INSUFFICIENT_EVIDENCE


def _metric_values(
    observations: Sequence[Observation],
    key: str,
    metric: str,
    split: EvidenceSplit,
) -> tuple[list[float], int]:
    selected = [item for item in observations if item.deck_key == key and item.split is split]
    values = [float(value) for item in selected if (value := item.metrics.get(metric)) is not None]
    return values, len(selected) - len(values)


def _categorical_summaries(
    observations: Sequence[Observation],
    confidence_level: float,
) -> dict[str, dict[str, CategoryEstimate]]:
    result: dict[str, dict[str, CategoryEstimate]] = {}
    for key in sorted({item.deck_key for item in observations}):
        for split in (EvidenceSplit.TRAIN, EvidenceSplit.VALIDATION):
            wins = [
                item.win_axis
                for item in observations
                if item.deck_key == key and item.split is split and item.win_axis
            ]
            if wins:
                result[f"{key}:{split.value}:win_axis"] = _category_estimates(
                    wins, confidence_level
                )
            losses = [
                cause
                for item in observations
                if item.deck_key == key and item.split is split
                for cause in item.loss_causes
                if cause
            ]
            if losses:
                result[f"{key}:{split.value}:loss_cause"] = _category_estimates(
                    losses, confidence_level
                )
    return result


def _category_estimates(
    values: Sequence[str],
    confidence_level: float,
) -> dict[str, CategoryEstimate]:
    counts = Counter(values)
    total = len(values)
    return {
        key: CategoryEstimate(
            count=count,
            total=total,
            proportion=count / total,
            interval=_wilson_interval(count, total, confidence_level),
        )
        for key, count in sorted(counts.items())
    }


def _wilson_interval(successes: int, total: int, confidence_level: float) -> tuple[float, float]:
    if total == 0:
        return (0.0, 1.0)
    z = _normal_quantile(0.5 + confidence_level / 2.0)
    proportion = successes / total
    denominator = 1.0 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total))
        / denominator
    )
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def _bootstrap_mean_interval(
    values: Sequence[float],
    *,
    confidence_level: float,
    samples: int,
    seed: int,
) -> tuple[float, float]:
    if len(values) == 1:
        return (values[0], values[0])
    rng = random.Random(seed)
    means = [
        fmean(values[rng.randrange(len(values))] for _ in values)
        for _ in range(samples)
    ]
    means.sort()
    alpha = (1.0 - confidence_level) / 2.0
    return (_quantile(means, alpha), _quantile(means, 1.0 - alpha))


def _bootstrap_difference_interval(
    real: Sequence[float],
    simulated: Sequence[float],
    *,
    confidence_level: float,
    samples: int,
    seed: int,
) -> tuple[float, float]:
    rng = random.Random(seed)
    differences = []
    for _ in range(samples):
        real_mean = fmean(real[rng.randrange(len(real))] for _ in real)
        simulated_mean = fmean(simulated[rng.randrange(len(simulated))] for _ in simulated)
        differences.append(real_mean - simulated_mean)
    differences.sort()
    alpha = (1.0 - confidence_level) / 2.0
    return (_quantile(differences, alpha), _quantile(differences, 1.0 - alpha))


def _quantile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("quantile requires values")
    if len(values) == 1:
        return float(values[0])
    position = (len(values) - 1) * min(1.0, max(0.0, probability))
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(values[lower])
    fraction = position - lower
    return float(values[lower] * (1.0 - fraction) + values[upper] * fraction)


def _normal_quantile(probability: float) -> float:
    # Acklam's rational approximation; adequate for interval construction without SciPy.
    if not 0.0 < probability < 1.0:
        raise ValueError("probability must be between zero and one")
    a = (-39.6968302866538, 220.946098424521, -275.928510446969, 138.357751867269, -30.6647980661472, 2.50662827745924)
    b = (-54.4760987982241, 161.585836858041, -155.698979859887, 66.8013118877197, -13.2806815528857)
    c = (-0.00778489400243029, -0.322396458041136, -2.40075827716184, -2.54973253934373, 4.37466414146497, 2.93816398269878)
    d = (0.00778469570904146, 0.32246712907004, 2.445134137143, 3.75440866190742)
    low = 0.02425
    high = 1 - low
    if probability < low:
        q = math.sqrt(-2 * math.log(probability))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if probability > high:
        q = math.sqrt(-2 * math.log(1 - probability))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = probability - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


def _simulated_win_axis(end_reason: str, metrics: object) -> str:
    commander_damage = float(getattr(metrics, "commander_damage_dealt", 0.0))
    normal_damage = float(getattr(metrics, "normal_damage_dealt", 0.0))
    if commander_damage >= 21.0:
        return "commander_damage"
    if normal_damage >= 80.0:
        return "table_damage"
    if "combat" in end_reason:
        return "combat"
    return end_reason or "structural_unknown"


def _float(value: int | float | None) -> float | None:
    return None if value is None else float(value)


def _stable_seed(seed: int, *parts: str) -> int:
    digest = hashlib.sha256("|".join((str(seed), *parts)).encode()).digest()
    return int.from_bytes(digest[:8], "big")
