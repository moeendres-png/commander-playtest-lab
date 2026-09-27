from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import Field, model_validator

from commander_lab.models import FrozenModel
from commander_lab.storage import sha256_value

from .optimizer_v2 import (
    EvidenceContext,
    EvidencePartition,
    OptimizerManifest,
    assert_partition_disjointness,
)

OPTIMIZER_V2_RELEASE_SCHEMA = "2.1.0"


class OptimizerV2Manifest(OptimizerManifest):
    """Release-candidate manifest with a fourth, tuning-isolated calibration partition."""

    schema_version: str = OPTIMIZER_V2_RELEASE_SCHEMA
    calibration_partition: EvidencePartition

    @model_validator(mode="after")
    def validate_release_partitions(self) -> OptimizerV2Manifest:
        if self.calibration_partition.evidence_context != EvidenceContext.CALIBRATION:
            raise ValueError("calibration_partition must be calibration evidence")
        assert_partition_disjointness(
            self.exploratory,
            self.calibration_partition,
            self.confirmatory,
            self.sealed_holdout,
        )
        return self


class EvaluatorAudit(FrozenModel):
    evidence_context: EvidenceContext
    requested_scenario_pairs: int = Field(default=0, ge=0)
    executed_scenario_pairs: int = Field(default=0, ge=0)
    cache_hits: int = Field(default=0, ge=0)
    cache_misses: int = Field(default=0, ge=0)
    cache_stores: int = Field(default=0, ge=0)
    skipped_illegal: int = Field(default=0, ge=0)
    failures: int = Field(default=0, ge=0)
    retries: int = Field(default=0, ge=0)
    requested_workers: int = Field(default=1, ge=1)
    shard_counts: dict[str, int] = Field(default_factory=dict)


class FrontierHandoff(FrozenModel):
    schema_version: str = "1.0.0"
    manifest_hash: str
    source_evidence_context: EvidenceContext = EvidenceContext.EXPLORATORY
    elites: tuple[dict[str, Any], ...]
    frontier_hash: str
    canonical_deck_mutation: bool = False
    holdout_used: bool = False

    @classmethod
    def create(
        cls,
        *,
        manifest_hash: str,
        elites: tuple[dict[str, Any], ...],
    ) -> FrontierHandoff:
        payload = {
            "manifest_hash": manifest_hash,
            "source_evidence_context": EvidenceContext.EXPLORATORY.value,
            "elites": elites,
        }
        return cls(
            manifest_hash=manifest_hash,
            elites=elites,
            frontier_hash=sha256_value(payload),
        )


class FaceValidityCase(FrozenModel):
    case_id: str
    hypothesis: str
    candidate_deck_hash: str
    decision: str
    score: float
    interval_low: float
    interval_high: float
    robust_lower_bound: float
    legal: bool
    expected_not_promote: bool = False
    expected_equivalent: bool = False


class OptimizerExecutionAudit(FrozenModel):
    schema_version: str = "1.0.0"
    manifest_hash: str
    run_id: str
    stage: str
    evidence_context: str
    evaluator: dict[str, Any]
    resumed: int = Field(default=0, ge=0)
    search_proposal_rejections: int = Field(default=0, ge=0)
    outputs: dict[str, str] = Field(default_factory=dict)
    confirmatory_partition_opened: bool = False
    sealed_holdout_partition_opened: bool = False
    canonical_deck_mutation: bool = False
    inventory_mutation: bool = False
    physical_allocation_mutation: bool = False
    opponent_observation_mutation: bool = False
    kaervek_mutation: bool = False


def calibration_cache_identity(
    *,
    manifest: OptimizerV2Manifest,
    candidate_deck_hash: str,
    control_deck_hash: str,
    opponent_hashes: tuple[str, ...],
    pilot_hashes: tuple[str, ...],
    scenario: Mapping[str, Any],
    exact_seed_set: tuple[int, ...],
    simulation_config: Mapping[str, Any],
) -> dict[str, Any]:
    from commander_lab.storage import build_exact_result_identity

    config = dict(simulation_config)
    config.update(
        {
            "optimizer_release_schema": OPTIMIZER_V2_RELEASE_SCHEMA,
            "manifest_hash": manifest.manifest_hash,
            "evidence_context": EvidenceContext.CALIBRATION.value,
            "partition_identity": manifest.calibration_partition.identity,
            "mulligan_policy_identity": manifest.mulligan_policy_identity,
        }
    )
    return build_exact_result_identity(
        engine_version=manifest.engine_version,
        deck_hashes=(control_deck_hash, candidate_deck_hash),
        opponent_hashes=opponent_hashes,
        pilot_hashes=pilot_hashes,
        canonical_context_snapshot=manifest.physical_pool_identity,
        scenario=scenario,
        simulation_config=config,
        exact_seed_set=exact_seed_set,
        policy_config_hashes={
            "construction_prior": manifest.construction_prior_identity,
            "knowledge": manifest.knowledge_identity,
            "opponents": manifest.opponent_data_identity,
            "pilot": manifest.pilot_policy_identity,
            "mulligan": manifest.mulligan_policy_identity,
        },
        tool_name="whole_deck_optimizer_v2_calibration",
    )
