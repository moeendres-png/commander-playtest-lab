from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any

from commander_lab.decision_statistics import (
    distributionally_robust_lower_bound,
    paired_bootstrap_interval,
)
from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength
from commander_lab.models.mulligan import MulliganContext, MulliganGamePlan, MulliganPolicyName
from commander_lab.mulligan.canonical import MulliganLab
from commander_lab.pod_scheduling import PodScenario
from commander_lab.storage import ExactResultCache, sha256_value

from .campaign import run_balanced_paired_campaign
from .optimizer_v2 import (
    EvidenceContext,
    EvidencePartition,
    ExploratoryEvaluation,
    descriptor_for_variant,
    deterministic_shard,
    optimizer_cache_identity,
)
from .optimizer_v2_release_models import (
    EvaluatorAudit,
    OptimizerV2Manifest,
    calibration_cache_identity,
)
from .orchestrator import WholeDeckCampaignOrchestrator
from .search_models import WholeDeckVariant


def _number(row: dict[str, object], key: str) -> float:
    value = row.get(key)
    if not isinstance(value, int | float):
        raise TypeError(f"paired observation {key} must be numeric")
    return float(value)


def _partition(manifest: OptimizerV2Manifest, context: EvidenceContext) -> EvidencePartition:
    if context == EvidenceContext.EXPLORATORY:
        return manifest.exploratory
    if context == EvidenceContext.CALIBRATION:
        return manifest.calibration_partition
    if context == EvidenceContext.CONFIRMATORY:
        return manifest.confirmatory
    if context == EvidenceContext.HOLDOUT:
        return manifest.sealed_holdout
    raise ValueError(f"unsupported simulation evidence context: {context.value}")


def _verify_partition(scenarios: tuple[PodScenario, ...], partition: EvidencePartition) -> None:
    if tuple(row.scenario_id for row in scenarios) != partition.scenario_ids:
        raise ValueError("scheduled scenario ids do not match frozen evidence partition")
    if tuple(row.seed for row in scenarios) != partition.scenario_seeds:
        raise ValueError("scheduled scenario seeds do not match frozen evidence partition")


class CachedPartitionEvaluator:
    """Exact-cache, manifest-bound evaluator for all Optimizer-v2 evidence partitions.

    Worker count is deliberately absent from the exact-result identity: the underlying paired
    runner sorts deterministic scenario tasks by their frozen index, so worker count is an
    execution detail rather than a scientific input. The acceptance suite separately verifies
    worker-count result equivalence.
    """

    def __init__(
        self,
        *,
        root: str | Path,
        manifest: OptimizerV2Manifest,
        orchestrator: WholeDeckCampaignOrchestrator,
        control_mainboard: tuple[str, ...],
        context: Any,
        evidence_context: EvidenceContext,
        run_directory: str | Path,
        workers: int,
        max_turns: int,
        enable_mulligan_sensitivity: bool = True,
    ) -> None:
        self.root = Path(root).resolve()
        self.manifest = manifest
        self.orchestrator = orchestrator
        self.context = context
        self.evidence_context = evidence_context
        self.partition = _partition(manifest, evidence_context)
        self.control = context.materialize(control_mainboard, label="optimizer-v2-control")
        if self.control.deck_hash != manifest.control_deck_hash:
            raise ValueError("optimizer manifest control hash does not match current control")
        if workers < 1:
            raise ValueError("workers must be positive")
        self.workers = workers
        self.max_turns = max_turns
        self.enable_mulligan_sensitivity = enable_mulligan_sensitivity
        self.scenarios = tuple(
            orchestrator.scheduler.schedule(
                len(self.partition.scenario_ids), seed=self.partition.master_seed
            )
        )
        _verify_partition(self.scenarios, self.partition)
        run_path = Path(run_directory).resolve()
        run_path.mkdir(parents=True, exist_ok=True)
        self.cache = ExactResultCache(run_path / "optimizer-v2-cache.sqlite", root=self.root)
        self.requested_scenario_pairs = 0
        self.executed_scenario_pairs = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.cache_stores = 0
        self.skipped_illegal = 0
        self.failures = 0
        self.retries = 0
        self.shards: Counter[int] = Counter()
        self.variants_by_hash: dict[str, WholeDeckVariant] = {}
        self.evaluations_by_hash: dict[str, ExploratoryEvaluation] = {}
        self.cached_payload_by_hash: dict[str, dict[str, Any]] = {}
        self._mulligan_lab: MulliganLab | None = None

    def _mulligan_sensitivity(self, candidate: Any, budget: int) -> dict[str, object]:
        if not self.enable_mulligan_sensitivity:
            return {"status": "disabled_by_frozen_execution_contract"}
        if self._mulligan_lab is None:
            self._mulligan_lab = MulliganLab(self.root)
        lab = self._mulligan_lab
        deck = candidate.model_copy(update={"deck_id": "rogshai/current"})
        samples = min(128, max(32, budget))
        seed = int(
            sha256_value(
                {
                    "manifest": self.manifest.manifest_hash,
                    "deck": candidate.deck_hash,
                    "budget": budget,
                    "axis": "optimizer_v2_mulligan_sensitivity",
                }
            )[:16],
            16,
        ) % (2**31 - 1)
        context = MulliganContext(
            deck_id="rogshai/current",
            deck_hash=candidate.deck_hash,
            opponent_ensemble_id="optimizer-v2-balanced-4p",
            pod_size=4,
            pilot_profile_id="RogShaiPilot",
            game_plan=MulliganGamePlan.PROTECTED_COMMANDER,
            seed=seed,
        )
        policies = (
            MulliganPolicyName.CURRENT_PILOT,
            MulliganPolicyName.CONSERVATIVE,
            MulliganPolicyName.INTERACTION_ORIENTED,
        )
        rows: dict[str, dict[str, float]] = {}
        for policy in policies:
            first_keeps = 0
            mulligans = 0
            color_issues = 0
            for draws in lab.iter_draw_sequences(deck, samples=samples, seed=seed):
                result = lab.london_mulligan_from_draws(deck, draws, policy, context)
                first_keeps += int(result.mulligans_taken == 0)
                mulligans += result.mulligans_taken
                color_issues += int(result.evaluation.features.color_stability_score < 2 / 3)
            rows[policy.value] = {
                "first_keep_rate": first_keeps / samples,
                "average_mulligans": mulligans / samples,
                "color_problem_rate": color_issues / samples,
            }
        keep_rates = [row["first_keep_rate"] for row in rows.values()]
        average_mulligans = [row["average_mulligans"] for row in rows.values()]
        return {
            "status": "executed",
            "samples_per_policy": samples,
            "policies": rows,
            "first_keep_rate_range": max(keep_rates) - min(keep_rates),
            "average_mulligans_range": max(average_mulligans) - min(average_mulligans),
            "outcome_dependent_policy_selection": False,
            "evidence_type": "structural_model_estimates",
        }

    def _identity(
        self,
        *,
        candidate_hash: str,
        scenarios: tuple[PodScenario, ...],
        budget: int,
    ) -> dict[str, Any]:
        opponent_hashes = tuple(
            sorted(deck.deck_hash for deck in self.orchestrator.opponents.profiles().values())
        )
        pilot_hashes = (
            self.manifest.pilot_policy_identity,
            sha256_value(
                {
                    "assignment": "scenario_parity_fixed_ensemble",
                    "profiles": ("strong_deterministic", "average_deterministic"),
                }
            ),
        )
        scenario = {
            "partition_identity": self.partition.identity,
            "scenario_ids": tuple(row.scenario_id for row in scenarios),
            "budget": budget,
        }
        simulation_config = {
            "max_turns": self.max_turns,
            "pilot_assignment": "scenario_parity_fixed_ensemble",
            "mulligan_sensitivity": self.enable_mulligan_sensitivity,
            "evaluator_schema": "optimizer-v2-cached-partition-1.0.0",
        }
        seeds = tuple(row.seed for row in scenarios)
        if self.evidence_context == EvidenceContext.CALIBRATION:
            return calibration_cache_identity(
                manifest=self.manifest,
                candidate_deck_hash=candidate_hash,
                control_deck_hash=self.control.deck_hash,
                opponent_hashes=opponent_hashes,
                pilot_hashes=pilot_hashes,
                scenario=scenario,
                exact_seed_set=seeds,
                simulation_config=simulation_config,
            )
        return optimizer_cache_identity(
            manifest=self.manifest,
            candidate_deck_hash=candidate_hash,
            control_deck_hash=self.control.deck_hash,
            opponent_hashes=opponent_hashes,
            pilot_hashes=pilot_hashes,
            scenario=scenario,
            exact_seed_set=seeds,
            simulation_config=simulation_config,
            evidence_context=self.evidence_context,
        )

    def _compute(
        self,
        *,
        candidate: Any,
        scenarios: tuple[PodScenario, ...],
        budget: int,
    ) -> dict[str, Any]:
        observations: list[dict[str, object]] = []
        pilot_deltas: dict[str, list[float]] = defaultdict(list)
        groups = (
            (
                "strong_deterministic",
                PilotConfig(
                    strength=PilotStrength.STRONG,
                    mode=PilotDecisionMode.DETERMINISTIC,
                ),
                scenarios[::2],
            ),
            (
                "average_deterministic",
                PilotConfig(
                    strength=PilotStrength.AVERAGE,
                    mode=PilotDecisionMode.DETERMINISTIC,
                ),
                scenarios[1::2],
            ),
        )
        statistics_seed = int(
            sha256_value(
                {
                    "partition": self.partition.identity,
                    "candidate": candidate.deck_hash,
                    "budget": budget,
                    "axis": "statistics",
                }
            )[:16],
            16,
        ) % (2**31 - 1)
        for label, pilot, group in groups:
            if not group:
                continue
            result = run_balanced_paired_campaign(
                baseline=self.control,
                variant=candidate,
                opponent_profiles=self.orchestrator.opponents.profiles(),
                scenarios=group,
                pilot_config=pilot,
                max_turns=self.max_turns,
                statistics_seed=statistics_seed,
                workers=self.workers,
            )
            raw = result.get("paired_observations", [])
            if not isinstance(raw, list):
                raise TypeError("paired campaign observations are malformed")
            for row in raw:
                if not isinstance(row, dict):
                    continue
                delta = _number(row, "baseline_placement") - _number(row, "variant_placement")
                pilot_deltas[label].append(delta)
                observations.append(row)
        differences = tuple(
            _number(row, "baseline_placement") - _number(row, "variant_placement")
            for row in observations
        )
        if len(differences) != budget:
            raise RuntimeError("paired evaluator did not cover requested frozen budget")
        interval = paired_bootstrap_interval(differences, seed=statistics_seed + 23)
        triple_rows: dict[str, list[float]] = defaultdict(list)
        for row in observations:
            opponents = row.get("opponent_deck_ids", [])
            if not isinstance(opponents, list):
                continue
            key = "|".join(sorted(str(value) for value in opponents))
            triple_rows[key].append(
                _number(row, "baseline_placement") - _number(row, "variant_placement")
            )
        per_pilot = {key: fmean(values) for key, values in sorted(pilot_deltas.items())}
        pilot_values = list(per_pilot.values())
        sensitivity = {
            "pilot": {
                "status": "executed",
                "mean_paired_delta": per_pilot,
                "range": max(pilot_values) - min(pilot_values) if pilot_values else 0.0,
                "assignment_outcome_dependent": False,
            },
            "mulligan": self._mulligan_sensitivity(candidate, budget),
            "matchup_decomposition": {
                key: fmean(values) for key, values in sorted(triple_rows.items())
            },
        }
        return {
            "budget": budget,
            "score": fmean(differences),
            "interval_low": interval[0],
            "interval_high": interval[1],
            "robust_lower_bound": distributionally_robust_lower_bound(differences),
            "sensitivity": sensitivity,
            "observation_count": len(observations),
            "evidence_context": self.evidence_context.value,
            "evidence_type": "structural_model_estimates",
        }

    def __call__(
        self,
        variant: WholeDeckVariant,
        budget: int,
        statistics_offset: int,
    ) -> ExploratoryEvaluation:
        del statistics_offset
        if budget > len(self.scenarios):
            raise ValueError("requested budget exceeds frozen evidence partition")
        if not variant.hard_gate.valid:
            self.skipped_illegal += 1
            raise ValueError("illegal candidate reached paired simulation")
        candidate = self.context.materialize(variant.mainboard, label=variant.deck_hash[:12])
        chosen = self.scenarios[:budget]
        self.requested_scenario_pairs += budget
        for scenario in chosen:
            shard = deterministic_shard(
                {"scenario_id": scenario.scenario_id, "seed": scenario.seed}, self.workers
            )
            self.shards[shard] += 1
        identity = self._identity(candidate_hash=candidate.deck_hash, scenarios=chosen, budget=budget)
        try:
            cached = self.cache.get(identity)
            if cached is not None:
                self.cache_hits += 1
                payload = cached.result
            else:
                self.cache_misses += 1
                payload = self._compute(candidate=candidate, scenarios=chosen, budget=budget)
                self.executed_scenario_pairs += budget
                stored = self.cache.put(
                    identity,
                    payload,
                    evidence_class="structural_model_estimates",
                )
                payload = stored.result
                self.cache_stores += 1
        except Exception:
            self.failures += 1
            raise
        sensitivity = payload.get("sensitivity", {})
        if not isinstance(sensitivity, dict):
            raise TypeError("cached sensitivity payload is malformed")
        evaluation = ExploratoryEvaluation(
            candidate_id=variant.variant_id,
            deck_hash=variant.deck_hash,
            generation=0,
            parent_candidate_id=variant.parent_variant_id,
            operator=(
                variant.mutation.neighborhood.value
                if variant.mutation is not None
                else "construction_prior"
            ),
            policy_id=variant.policy_id.value,
            budget=budget,
            score=float(payload["score"]),
            interval_low=float(payload["interval_low"]),
            interval_high=float(payload["interval_high"]),
            robust_lower_bound=float(payload["robust_lower_bound"]),
            qd_cell=descriptor_for_variant(variant).cell(self.manifest.qd),
            evidence_context=self.evidence_context,
            evidence_type="structural_model_estimates",
        )
        self.variants_by_hash[variant.deck_hash] = variant
        self.evaluations_by_hash[variant.deck_hash] = evaluation
        self.cached_payload_by_hash[variant.deck_hash] = payload
        return evaluation

    def audit(self) -> EvaluatorAudit:
        return EvaluatorAudit(
            evidence_context=self.evidence_context,
            requested_scenario_pairs=self.requested_scenario_pairs,
            executed_scenario_pairs=self.executed_scenario_pairs,
            cache_hits=self.cache_hits,
            cache_misses=self.cache_misses,
            cache_stores=self.cache_stores,
            skipped_illegal=self.skipped_illegal,
            failures=self.failures,
            retries=self.retries,
            requested_workers=self.workers,
            shard_counts={str(key): value for key, value in sorted(self.shards.items())},
        )
