from __future__ import annotations

import json
import math
import os
import socket
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from statistics import fmean
from typing import Any

from pydantic import Field, model_validator

from commander_lab.models import FrozenModel
from commander_lab.storage import atomic_write_json, build_exact_result_identity, sha256_value

from .search_models import WholeDeckNeighborhood, WholeDeckVariant

OPTIMIZER_V2_VERSION = "optimizer-v2-0.1.0"


class EvidenceContext(StrEnum):
    EXPLORATORY = "exploratory"
    CONFIRMATORY = "confirmatory"
    HOLDOUT = "holdout"
    CALIBRATION = "calibration"
    SYNTHETIC_FIXTURE = "synthetic_fixture"


class EvidencePartition(FrozenModel):
    partition_id: str
    evidence_context: EvidenceContext
    master_seed: int = Field(ge=0)
    scenario_ids: tuple[str, ...]
    scenario_seeds: tuple[int, ...]
    identity: str = Field(pattern=r"^[0-9a-f]{64}$")

    @classmethod
    def create(
        cls,
        *,
        partition_id: str,
        evidence_context: EvidenceContext,
        master_seed: int,
        scenario_ids: Sequence[str],
        scenario_seeds: Sequence[int],
    ) -> EvidencePartition:
        ids = tuple(str(value) for value in scenario_ids)
        seeds = tuple(int(seed) for seed in scenario_seeds)
        payload = {
            "partition_id": partition_id,
            "evidence_context": evidence_context.value,
            "master_seed": master_seed,
            "scenario_ids": ids,
            "scenario_seeds": seeds,
        }
        return cls(
            partition_id=partition_id,
            evidence_context=evidence_context,
            master_seed=master_seed,
            scenario_ids=ids,
            scenario_seeds=seeds,
            identity=sha256_value(payload),
        )


class QDConfig(FrozenModel):
    land_bin_width: int = Field(default=2, ge=1, le=8)
    mana_value_bin_width: float = Field(default=0.4, gt=0.0, le=2.0)
    interaction_bin_width: float = Field(default=4.0, gt=0.0)
    elites_per_cell: int = Field(default=2, ge=1, le=8)
    novelty_neighbors: int = Field(default=5, ge=1, le=32)
    novelty_weight: float = Field(default=0.15, ge=0.0, le=1.0)


class RacingConfig(FrozenModel):
    budgets: tuple[int, ...] = (32, 64, 128, 256)
    survival_fraction: float = Field(default=0.5, gt=0.0, le=1.0)
    exploration_fraction: float = Field(default=0.20, ge=0.0, le=0.5)
    minimum_survivors: int = Field(default=4, ge=1)
    uncertainty_weight: float = Field(default=0.25, ge=0.0, le=2.0)
    novelty_weight: float = Field(default=0.15, ge=0.0, le=2.0)

    @model_validator(mode="after")
    def valid_budgets(self) -> RacingConfig:
        if not self.budgets or any(value < 1 for value in self.budgets):
            raise ValueError("racing budgets must be positive")
        if tuple(sorted(set(self.budgets))) != self.budgets:
            raise ValueError("racing budgets must be strictly increasing")
        return self


class LearningConfig(FrozenModel):
    update_rate: float = Field(default=0.20, gt=0.0, le=1.0)
    exploration_floor: float = Field(default=0.05, gt=0.0, le=0.25)


class DecisionCalibrationPolicy(FrozenModel):
    sesoi: float = Field(gt=0.0)
    equivalence_margin: float = Field(gt=0.0)
    max_false_promotion: float = Field(default=0.05, ge=0.0, le=1.0)
    max_false_elimination: float = Field(default=0.05, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def valid_equivalence(self) -> DecisionCalibrationPolicy:
        if self.equivalence_margin > self.sesoi:
            raise ValueError("equivalence margin must not exceed SESOI")
        return self


class OptimizerManifest(FrozenModel):
    schema_version: str = "2.0.0"
    optimizer_version: str = OPTIMIZER_V2_VERSION
    run_id: str
    software_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    software_tree: str = Field(pattern=r"^[0-9a-f]{40}$")
    package_version: str
    engine_version: str
    physical_pool_identity: str
    control_deck_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    opponent_data_identity: str
    knowledge_identity: str
    pilot_policy_identity: str
    mulligan_policy_identity: str
    construction_prior_identity: str
    search_seed: int = Field(ge=0)
    exploratory: EvidencePartition
    confirmatory: EvidencePartition
    sealed_holdout: EvidencePartition
    qd: QDConfig = QDConfig()
    racing: RacingConfig = RacingConfig()
    learning: LearningConfig = LearningConfig()
    calibration: DecisionCalibrationPolicy
    max_generations: int = Field(default=4, ge=1, le=64)
    proposals_per_generation: int = Field(default=24, ge=1, le=1000)
    stopping_no_improvement_generations: int = Field(default=2, ge=1, le=32)
    cache_namespace: str = "optimizer-v2"

    @model_validator(mode="after")
    def validate_partitions(self) -> OptimizerManifest:
        expected = (
            (self.exploratory, EvidenceContext.EXPLORATORY),
            (self.confirmatory, EvidenceContext.CONFIRMATORY),
            (self.sealed_holdout, EvidenceContext.HOLDOUT),
        )
        for partition, context in expected:
            if partition.evidence_context != context:
                raise ValueError(f"{partition.partition_id} must be {context.value}")
        assert_partition_disjointness(
            self.exploratory, self.confirmatory, self.sealed_holdout
        )
        return self

    @property
    def manifest_hash(self) -> str:
        return sha256_value(self.model_dump(mode="json"))


class DeckDescriptor(FrozenModel):
    land_count: int
    average_nonland_mv: float
    interaction_strength: float
    protection_strength: float
    velocity_strength: float
    finish_strength: float
    package_count: int
    semantic_support_fraction: float
    multiplayer_scaling: float

    def cell(self, config: QDConfig) -> str:
        land = self.land_count // config.land_bin_width
        mv = math.floor(self.average_nonland_mv / config.mana_value_bin_width)
        interaction = math.floor(self.interaction_strength / config.interaction_bin_width)
        return f"L{land}:M{mv}:I{interaction}"


class DeckDistance(FrozenModel):
    total: float
    card_multiset: float
    package: float
    role_profile: float
    mana_curve: float
    finish_profile: float


class ExploratoryEvaluation(FrozenModel):
    candidate_id: str
    deck_hash: str
    generation: int = Field(ge=0)
    parent_candidate_id: str | None = None
    operator: str
    policy_id: str
    budget: int = Field(ge=1)
    score: float
    interval_low: float
    interval_high: float
    robust_lower_bound: float
    novelty: float = Field(default=0.0, ge=0.0)
    qd_cell: str
    evidence_context: EvidenceContext = EvidenceContext.EXPLORATORY
    evidence_type: str = "structural_model_estimates"

    @property
    def uncertainty_width(self) -> float:
        return max(0.0, self.interval_high - self.interval_low)


class SemanticReviewItem(FrozenModel):
    oracle_name: str
    frontier_occurrences: int = Field(ge=0)
    high_quality_cell_occurrences: int = Field(ge=0)
    package_completion_signal: float = Field(ge=0.0, le=1.0)
    differentiator_signal: float = Field(ge=0.0, le=1.0)
    possible_decision_impact: float = Field(ge=0.0, le=1.0)
    priority_score: float = Field(ge=0.0)
    status: str = "semantic_unknown_fail_closed"


class SyntheticCalibrationFixture(FrozenModel):
    fixture_id: str
    truth_direction: int = Field(ge=-1, le=1)
    observed_delta: float
    interval_low: float
    interval_high: float
    sample_size: int = Field(ge=1)
    evidence_context: EvidenceContext = EvidenceContext.SYNTHETIC_FIXTURE


class CalibrationSummary(FrozenModel):
    fixture_count: int
    false_promotions: int
    false_eliminations: int
    direction_correct: int
    direction_total: int
    equivalence_correct: int
    equivalence_total: int
    false_promotion_rate: float
    false_elimination_rate: float
    direction_recovery_rate: float
    equivalence_accuracy: float
    targets_met: bool


def assert_partition_disjointness(*partitions: EvidencePartition) -> None:
    seed_sets = [set(partition.scenario_seeds) for partition in partitions]
    scenario_sets = [set(partition.scenario_ids) for partition in partitions]
    for left in range(len(partitions)):
        for right in range(left + 1, len(partitions)):
            if seed_sets[left] & seed_sets[right]:
                raise ValueError(
                    f"seed leakage: {partitions[left].partition_id} vs "
                    f"{partitions[right].partition_id}"
                )
            if scenario_sets[left] & scenario_sets[right]:
                raise ValueError(
                    f"scenario leakage: {partitions[left].partition_id} vs "
                    f"{partitions[right].partition_id}"
                )


def _number(mapping: Mapping[str, object], key: str) -> float:
    value = mapping.get(key, 0.0)
    return float(value) if isinstance(value, int | float) else 0.0


def _role_strengths(variant: WholeDeckVariant) -> dict[str, float]:
    raw = variant.feature_vector.get("role_strengths", {})
    if not isinstance(raw, Mapping):
        return {}
    return {
        str(key): float(value)
        for key, value in raw.items()
        if isinstance(value, int | float)
    }


def descriptor_for_variant(variant: WholeDeckVariant) -> DeckDescriptor:
    roles = _role_strengths(variant)
    packages = variant.feature_vector.get("package_counts", {})
    package_count = len(packages) if isinstance(packages, Mapping) else 0
    raw_multiplayer = variant.feature_vector.get("multiplayer_leverage", {})
    multiplayer = 0.0
    if isinstance(raw_multiplayer, Mapping):
        numeric = [
            float(value)
            for value in raw_multiplayer.values()
            if isinstance(value, int | float)
        ]
        multiplayer = fmean(numeric) if numeric else 0.0
    return DeckDescriptor(
        land_count=int(_number(variant.feature_vector, "land_count")),
        average_nonland_mv=_number(variant.feature_vector, "average_nonland_mv"),
        interaction_strength=(
            roles.get("counter", 0.0)
            + roles.get("removal", 0.0)
            + roles.get("wipe", 0.0)
            + roles.get("graveyard_hate", 0.0)
        ),
        protection_strength=roles.get("protection", 0.0),
        velocity_strength=(
            roles.get("ramp", 0.0)
            + roles.get("selection", 0.0)
            + roles.get("draw", 0.0)
        ),
        finish_strength=(
            roles.get("finisher", 0.0)
            + roles.get("payoff", 0.0)
            + roles.get("combat_payoff", 0.0)
        ),
        package_count=package_count,
        semantic_support_fraction=_number(
            variant.feature_vector, "semantic_support_fraction"
        ),
        multiplayer_scaling=multiplayer,
    )


def _multiset_jaccard(left: Sequence[str], right: Sequence[str]) -> float:
    a = Counter(left)
    b = Counter(right)
    keys = set(a) | set(b)
    union = sum(max(a[key], b[key]) for key in keys)
    if union == 0:
        return 1.0
    intersection = sum(min(a[key], b[key]) for key in keys)
    return intersection / union


def _counter_distance(left: Mapping[str, object], right: Mapping[str, object]) -> float:
    keys = set(left) | set(right)
    if not keys:
        return 0.0
    numerator = 0.0
    denominator = 0.0
    for key in keys:
        lv = float(left.get(key, 0.0)) if isinstance(left.get(key, 0.0), int | float) else 0.0
        rv = float(right.get(key, 0.0)) if isinstance(right.get(key, 0.0), int | float) else 0.0
        numerator += abs(lv - rv)
        denominator += max(abs(lv), abs(rv))
    return numerator / denominator if denominator else 0.0


def deck_distance(left: WholeDeckVariant, right: WholeDeckVariant) -> DeckDistance:
    left_packages = left.feature_vector.get("package_counts", {})
    right_packages = right.feature_vector.get("package_counts", {})
    lp = left_packages if isinstance(left_packages, Mapping) else {}
    rp = right_packages if isinstance(right_packages, Mapping) else {}
    card_distance = 1.0 - _multiset_jaccard(left.mainboard, right.mainboard)
    package_distance = _counter_distance(lp, rp)
    role_distance = _counter_distance(_role_strengths(left), _role_strengths(right))
    ld = descriptor_for_variant(left)
    rd = descriptor_for_variant(right)
    mana_distance = min(
        1.0,
        abs(ld.land_count - rd.land_count) / 12.0
        + abs(ld.average_nonland_mv - rd.average_nonland_mv) / 4.0,
    )
    finish_scale = max(1.0, ld.finish_strength, rd.finish_strength)
    finish_distance = min(1.0, abs(ld.finish_strength - rd.finish_strength) / finish_scale)
    total = (
        0.40 * card_distance
        + 0.20 * package_distance
        + 0.20 * role_distance
        + 0.12 * mana_distance
        + 0.08 * finish_distance
    )
    return DeckDistance(
        total=total,
        card_multiset=card_distance,
        package=package_distance,
        role_profile=role_distance,
        mana_curve=mana_distance,
        finish_profile=finish_distance,
    )


def novelty_score(
    candidate: WholeDeckVariant,
    archive: Sequence[WholeDeckVariant],
    *,
    neighbors: int,
) -> float:
    distances = sorted(
        deck_distance(candidate, other).total
        for other in archive
        if other.deck_hash != candidate.deck_hash
    )
    if not distances:
        return 1.0
    return fmean(distances[: min(neighbors, len(distances))])


class QualityDiversityArchive:
    def __init__(self, config: QDConfig) -> None:
        self.config = config
        self._cells: dict[str, list[ExploratoryEvaluation]] = {}
        self._variants: dict[str, WholeDeckVariant] = {}

    def admit(
        self,
        variant: WholeDeckVariant,
        evaluation: ExploratoryEvaluation,
    ) -> bool:
        if not variant.hard_gate.valid:
            return False
        expected = descriptor_for_variant(variant).cell(self.config)
        if evaluation.qd_cell != expected:
            raise ValueError("evaluation QD cell does not match candidate descriptor")
        rows = list(self._cells.get(expected, ()))
        rows = [row for row in rows if row.deck_hash != evaluation.deck_hash]
        rows.append(evaluation)
        rows.sort(
            key=lambda row: (
                row.robust_lower_bound,
                row.score,
                row.novelty,
                row.deck_hash,
            ),
            reverse=True,
        )
        kept = rows[: self.config.elites_per_cell]
        self._cells[expected] = kept
        admitted = any(row.deck_hash == evaluation.deck_hash for row in kept)
        if admitted:
            self._variants[variant.deck_hash] = variant
        active_hashes = {row.deck_hash for cell in self._cells.values() for row in cell}
        self._variants = {
            deck_hash: row
            for deck_hash, row in self._variants.items()
            if deck_hash in active_hashes
        }
        return admitted

    def variants(self) -> tuple[WholeDeckVariant, ...]:
        return tuple(self._variants[key] for key in sorted(self._variants))

    def evaluations(self) -> tuple[ExploratoryEvaluation, ...]:
        return tuple(
            row
            for cell in sorted(self._cells)
            for row in sorted(self._cells[cell], key=lambda item: item.deck_hash)
        )

    def coverage(self) -> dict[str, object]:
        rows = self.evaluations()
        novelties = [row.novelty for row in rows]
        return {
            "occupied_cells": len(self._cells),
            "elite_count": len(rows),
            "mean_novelty": fmean(novelties) if novelties else 0.0,
            "min_novelty": min(novelties) if novelties else 0.0,
            "max_novelty": max(novelties) if novelties else 0.0,
            "cells": {
                cell: [row.deck_hash for row in self._cells[cell]]
                for cell in sorted(self._cells)
            },
        }


def racing_priority(
    evaluation: ExploratoryEvaluation,
    *,
    config: RacingConfig,
) -> float:
    return (
        evaluation.robust_lower_bound
        + config.novelty_weight * evaluation.novelty
        - config.uncertainty_weight * evaluation.uncertainty_width
    )


def select_racing_survivors(
    evaluations: Sequence[ExploratoryEvaluation],
    *,
    config: RacingConfig,
) -> tuple[str, ...]:
    if not evaluations:
        return ()
    target = max(
        config.minimum_survivors,
        math.ceil(len(evaluations) * config.survival_fraction),
    )
    target = min(target, len(evaluations))
    exploration_slots = min(
        target,
        math.ceil(target * config.exploration_fraction),
    )
    exploitation_slots = target - exploration_slots
    ranked = sorted(
        evaluations,
        key=lambda row: (racing_priority(row, config=config), row.deck_hash),
        reverse=True,
    )
    selected = ranked[:exploitation_slots]
    selected_hashes = {row.deck_hash for row in selected}
    novelty_ranked = sorted(
        (row for row in evaluations if row.deck_hash not in selected_hashes),
        key=lambda row: (row.novelty, row.robust_lower_bound, row.deck_hash),
        reverse=True,
    )
    selected.extend(novelty_ranked[:exploration_slots])
    return tuple(row.candidate_id for row in selected)


def normalize_learning_weights(
    raw: Mapping[str, float],
    *,
    floor: float,
) -> dict[str, float]:
    if not raw:
        return {}
    keys = sorted(raw)
    safe = {key: max(0.0, float(raw[key])) for key in keys}
    total = sum(safe.values())
    if total <= 0.0:
        safe = {key: 1.0 for key in keys}
        total = float(len(keys))
    normalized = {key: value / total for key, value in safe.items()}
    minimum = min(floor, 1.0 / len(keys))
    remaining = 1.0 - minimum * len(keys)
    if remaining <= 0.0:
        return {key: 1.0 / len(keys) for key in keys}
    residual_total = sum(max(0.0, value - minimum) for value in normalized.values())
    if residual_total <= 0.0:
        return {key: 1.0 / len(keys) for key in keys}
    return {
        key: minimum
        + remaining * max(0.0, normalized[key] - minimum) / residual_total
        for key in keys
    }


def update_learning_weights(
    weights: Mapping[str, float],
    rewards: Mapping[str, Sequence[float]],
    *,
    config: LearningConfig,
) -> dict[str, float]:
    updated: dict[str, float] = {}
    for key, weight in weights.items():
        observations = rewards.get(key, ())
        reward = fmean(observations) if observations else 0.0
        bounded = max(-1.0, min(1.0, reward))
        updated[key] = max(0.0, float(weight)) * (1.0 + config.update_rate * bounded)
    return normalize_learning_weights(updated, floor=config.exploration_floor)


def decision_for_interval(
    *,
    interval_low: float,
    interval_high: float,
    policy: DecisionCalibrationPolicy,
) -> str:
    if interval_low > policy.sesoi:
        return "PROMOTE"
    if interval_high < -policy.sesoi:
        return "ELIMINATE"
    if interval_low >= -policy.equivalence_margin and interval_high <= policy.equivalence_margin:
        return "EQUIVALENT"
    return "MORE_SAMPLES"


def evaluate_calibration(
    fixtures: Sequence[SyntheticCalibrationFixture],
    *,
    policy: DecisionCalibrationPolicy,
) -> CalibrationSummary:
    false_promotions = 0
    false_eliminations = 0
    direction_correct = 0
    direction_total = 0
    equivalence_correct = 0
    equivalence_total = 0
    for fixture in fixtures:
        decision = decision_for_interval(
            interval_low=fixture.interval_low,
            interval_high=fixture.interval_high,
            policy=policy,
        )
        if decision == "PROMOTE" and fixture.truth_direction <= 0:
            false_promotions += 1
        if decision == "ELIMINATE" and fixture.truth_direction >= 0:
            false_eliminations += 1
        if fixture.truth_direction != 0:
            direction_total += 1
            expected = "PROMOTE" if fixture.truth_direction > 0 else "ELIMINATE"
            direction_correct += decision == expected
        else:
            equivalence_total += 1
            equivalence_correct += decision == "EQUIVALENT"
    count = max(1, len(fixtures))
    fp_rate = false_promotions / count
    fe_rate = false_eliminations / count
    return CalibrationSummary(
        fixture_count=len(fixtures),
        false_promotions=false_promotions,
        false_eliminations=false_eliminations,
        direction_correct=direction_correct,
        direction_total=direction_total,
        equivalence_correct=equivalence_correct,
        equivalence_total=equivalence_total,
        false_promotion_rate=fp_rate,
        false_elimination_rate=fe_rate,
        direction_recovery_rate=(
            direction_correct / direction_total if direction_total else 1.0
        ),
        equivalence_accuracy=(
            equivalence_correct / equivalence_total if equivalence_total else 1.0
        ),
        targets_met=(
            fp_rate <= policy.max_false_promotion
            and fe_rate <= policy.max_false_elimination
        ),
    )


def build_semantic_review_queue(
    signals: Iterable[Mapping[str, object]],
) -> tuple[SemanticReviewItem, ...]:
    rows: list[SemanticReviewItem] = []
    for signal in signals:
        name = str(signal["oracle_name"])
        frontier = int(signal.get("frontier_occurrences", 0))
        cells = int(signal.get("high_quality_cell_occurrences", 0))
        package = float(signal.get("package_completion_signal", 0.0))
        differentiator = float(signal.get("differentiator_signal", 0.0))
        impact = float(signal.get("possible_decision_impact", 0.0))
        score = (
            math.log1p(frontier) * 0.25
            + math.log1p(cells) * 0.20
            + package * 0.15
            + differentiator * 0.15
            + impact * 0.25
        )
        rows.append(
            SemanticReviewItem(
                oracle_name=name,
                frontier_occurrences=max(0, frontier),
                high_quality_cell_occurrences=max(0, cells),
                package_completion_signal=max(0.0, min(1.0, package)),
                differentiator_signal=max(0.0, min(1.0, differentiator)),
                possible_decision_impact=max(0.0, min(1.0, impact)),
                priority_score=max(0.0, score),
            )
        )
    return tuple(
        sorted(rows, key=lambda row: (-row.priority_score, row.oracle_name))
    )


def optimizer_cache_identity(
    *,
    manifest: OptimizerManifest,
    candidate_deck_hash: str,
    control_deck_hash: str,
    opponent_hashes: Sequence[str],
    pilot_hashes: Sequence[str],
    scenario: Mapping[str, Any],
    exact_seed_set: Sequence[int],
    simulation_config: Mapping[str, Any],
    evidence_context: EvidenceContext,
) -> dict[str, Any]:
    if evidence_context == EvidenceContext.HOLDOUT:
        partition = manifest.sealed_holdout
    elif evidence_context == EvidenceContext.CONFIRMATORY:
        partition = manifest.confirmatory
    elif evidence_context == EvidenceContext.EXPLORATORY:
        partition = manifest.exploratory
    else:
        raise ValueError("cache identity only supports simulation evidence partitions")
    config = dict(simulation_config)
    config.update(
        {
            "optimizer_version": manifest.optimizer_version,
            "manifest_hash": manifest.manifest_hash,
            "evidence_context": evidence_context.value,
            "partition_identity": partition.identity,
            "mulligan_policy_identity": manifest.mulligan_policy_identity,
        }
    )
    return build_exact_result_identity(
        engine_version=manifest.engine_version,
        deck_hashes=(control_deck_hash, candidate_deck_hash),
        opponent_hashes=tuple(opponent_hashes),
        pilot_hashes=tuple(pilot_hashes),
        canonical_context_snapshot=manifest.physical_pool_identity,
        scenario=scenario,
        simulation_config=config,
        exact_seed_set=tuple(exact_seed_set),
        policy_config_hashes={
            "construction_prior": manifest.construction_prior_identity,
            "knowledge": manifest.knowledge_identity,
            "opponents": manifest.opponent_data_identity,
            "pilot": manifest.pilot_policy_identity,
            "mulligan": manifest.mulligan_policy_identity,
        },
        tool_name="whole_deck_optimizer_v2",
    )


def deterministic_shard(task_identity: Mapping[str, object], worker_count: int) -> int:
    if worker_count < 1:
        raise ValueError("worker_count must be positive")
    digest = sha256_value(dict(task_identity))
    return int(digest[:16], 16) % worker_count


@dataclass(frozen=True, slots=True)
class OptimizerLock:
    path: Path
    manifest_hash: str

    @classmethod
    def acquire(
        cls,
        run_directory: str | Path,
        *,
        manifest_hash: str,
        stale_after_seconds: int = 43_200,
    ) -> OptimizerLock:
        root = Path(run_directory).resolve()
        root.mkdir(parents=True, exist_ok=True)
        path = root / ".optimizer.lock"
        now = datetime.now(UTC)
        payload = {
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "manifest_hash": manifest_hash,
            "created_at": now.isoformat(),
        }
        if path.exists():
            try:
                current = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise RuntimeError("optimizer lock is corrupt; refusing unsafe overwrite") from exc
            if not isinstance(current, dict):
                raise RuntimeError("optimizer lock is malformed")
            if current.get("manifest_hash") != manifest_hash:
                raise RuntimeError("optimizer directory is locked by a different manifest")
            created = datetime.fromisoformat(str(current["created_at"]))
            age = (now - created).total_seconds()
            lock_host = str(current.get("host", ""))
            lock_pid = int(current.get("pid", -1))
            if lock_host != socket.gethostname():
                raise RuntimeError("optimizer lock belongs to another host")
            pid_alive = True
            try:
                os.kill(lock_pid, 0)
            except (OSError, ProcessLookupError):
                pid_alive = False
            if pid_alive or age <= stale_after_seconds:
                raise RuntimeError("duplicate optimizer runner detected")
            path.unlink()
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        try:
            descriptor = os.open(path, flags, 0o600)
        except FileExistsError as exc:
            raise RuntimeError("duplicate optimizer runner detected") from exc
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
        return cls(path=path, manifest_hash=manifest_hash)

    def release(self) -> None:
        if not self.path.exists():
            return
        current = json.loads(self.path.read_text(encoding="utf-8"))
        if current.get("manifest_hash") != self.manifest_hash:
            raise RuntimeError("optimizer lock identity changed; refusing to remove")
        self.path.unlink()


class OptimizerCheckpointStore:
    def __init__(self, run_directory: str | Path, *, manifest_hash: str) -> None:
        self.root = Path(run_directory).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.manifest_hash = manifest_hash

    def write(self, stage: str, payload: Mapping[str, Any]) -> Path:
        data = {
            "stage": stage,
            "manifest_hash": self.manifest_hash,
            "payload": dict(payload),
        }
        return atomic_write_json(self.root / f"checkpoint-{stage}.json", data)

    def read(self, stage: str) -> dict[str, Any] | None:
        path = self.root / f"checkpoint-{stage}.json"
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("manifest_hash") != self.manifest_hash:
            raise RuntimeError("checkpoint manifest hash mismatch")
        payload = data.get("payload")
        if not isinstance(payload, dict):
            raise RuntimeError("checkpoint payload is malformed")
        return payload


def operator_names() -> tuple[str, ...]:
    return tuple(neighborhood.value for neighborhood in WholeDeckNeighborhood)
