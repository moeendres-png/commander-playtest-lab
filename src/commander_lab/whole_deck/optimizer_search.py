from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from statistics import fmean
from typing import Any

from commander_lab.decision_statistics import (
    distributionally_robust_lower_bound,
    paired_bootstrap_interval,
)
from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength
from commander_lab.pod_scheduling import PodScenario

from .campaign import run_balanced_paired_campaign
from .lab_context import EnrichedWholeDeckSearchEngine
from .optimizer_advancement import CandidatePairedEvidence, merge_pairing_conditions
from .optimizer_v2 import (
    EvidenceContext,
    EvidencePartition,
    ExploratoryEvaluation,
    LearningConfig,
    OptimizerManifest,
    QDConfig,
    QualityDiversityArchive,
    RacingConfig,
    descriptor_for_variant,
    normalize_learning_weights,
    novelty_score,
    operator_names,
    select_racing_survivors,
    update_learning_weights,
)
from .orchestrator import WholeDeckCampaignOrchestrator
from .search_models import WholeDeckMutation, WholeDeckNeighborhood, WholeDeckVariant

EvaluationFunction = Callable[[WholeDeckVariant, int, int], ExploratoryEvaluation]


@dataclass(frozen=True, slots=True)
class OptimizerSearchReport:
    generations: tuple[dict[str, Any], ...]
    archive: dict[str, object]
    operator_weights: dict[str, float]
    policy_weights: dict[str, float]
    unique_legal_decks: int
    evaluation_calls: int
    requested_scenario_pairs: int
    feedback_changed_proposals: bool


def _weighted_choice(rng: random.Random, weights: Mapping[str, float]) -> str:
    ordered = sorted(weights)
    if not ordered:
        raise ValueError("weighted choice requires at least one option")
    total = sum(max(0.0, float(weights[key])) for key in ordered)
    if total <= 0.0:
        return ordered[rng.randrange(len(ordered))]
    point = rng.random() * total
    running = 0.0
    for key in ordered:
        running += max(0.0, float(weights[key]))
        if point <= running:
            return key
    return ordered[-1]


def _placement(row: Mapping[str, object], key: str) -> float:
    value = row.get(key)
    if not isinstance(value, int | float):
        raise TypeError(f"paired campaign {key} must be numeric")
    return float(value)


class AdaptiveWholeDeckSearch:
    """Performance-informed search over existing legal Whole-Deck operators.

    Results are exploratory only. Confirmatory and holdout execution are intentionally
    absent so search feedback cannot consume either evidence partition.
    """

    def __init__(
        self,
        engines: Mapping[str, EnrichedWholeDeckSearchEngine],
        *,
        evaluator: EvaluationFunction,
        seed: int,
        qd: QDConfig,
        racing: RacingConfig,
        learning: LearningConfig,
    ) -> None:
        if not engines:
            raise ValueError("adaptive search requires at least one construction engine")
        self.engines = dict(engines)
        self.evaluator = evaluator
        self.seed = seed
        self.qd = qd
        self.racing = racing
        self.learning = learning

    def _evaluate_batch(
        self,
        variants: Sequence[WholeDeckVariant],
        *,
        generation: int,
        archive: QualityDiversityArchive,
    ) -> tuple[list[ExploratoryEvaluation], int, int]:
        if not variants:
            return [], 0, 0
        current: list[ExploratoryEvaluation] = []
        calls = 0
        scenario_pairs = 0
        first_budget = self.racing.budgets[0]
        for index, variant in enumerate(variants):
            raw = self.evaluator(variant, first_budget, generation * 100_003 + index)
            novelty = novelty_score(
                variant,
                archive.variants(),
                neighbors=self.qd.novelty_neighbors,
            )
            current.append(
                raw.model_copy(
                    update={
                        "generation": generation,
                        "novelty": novelty,
                        "qd_cell": descriptor_for_variant(variant).cell(self.qd),
                    }
                )
            )
            calls += 1
            scenario_pairs += first_budget

        by_id = {row.candidate_id: row for row in current}
        variant_by_id = {variant.variant_id: variant for variant in variants}
        active_ids = tuple(by_id)
        for budget_index, budget in enumerate(self.racing.budgets[1:], start=1):
            active_rows = tuple(by_id[candidate_id] for candidate_id in active_ids)
            survivor_ids = select_racing_survivors(active_rows, config=self.racing)
            next_rows: dict[str, ExploratoryEvaluation] = {}
            for index, candidate_id in enumerate(survivor_ids):
                variant = variant_by_id[candidate_id]
                raw = self.evaluator(
                    variant,
                    budget,
                    generation * 100_003 + budget_index * 10_007 + index,
                )
                previous = by_id[candidate_id]
                next_rows[candidate_id] = raw.model_copy(
                    update={
                        "generation": generation,
                        "novelty": previous.novelty,
                        "qd_cell": previous.qd_cell,
                    }
                )
                calls += 1
                scenario_pairs += budget
            by_id.update(next_rows)
            active_ids = survivor_ids

        final_rows = list(by_id.values())
        for row in final_rows:
            archive.admit(variant_by_id[row.candidate_id], row)
        return final_rows, calls, scenario_pairs

    def run(
        self,
        *,
        initial_variants: Sequence[WholeDeckVariant],
        generations: int,
        proposals_per_generation: int,
    ) -> OptimizerSearchReport:
        legal_initial = [row for row in initial_variants if row.hard_gate.valid]
        if not legal_initial:
            raise ValueError("adaptive search has no legal initial variants")

        archive = QualityDiversityArchive(self.qd)
        rng = random.Random(self.seed)
        operator_weights = normalize_learning_weights(
            {name: 1.0 for name in operator_names()},
            floor=self.learning.exploration_floor,
        )
        policy_weights = normalize_learning_weights(
            {name: 1.0 for name in sorted(self.engines)},
            floor=self.learning.exploration_floor,
        )
        history: list[dict[str, Any]] = []
        seen: dict[str, WholeDeckVariant] = {row.deck_hash: row for row in legal_initial}
        evaluations_by_variant: dict[str, ExploratoryEvaluation] = {}

        initial_eval, calls, pairs = self._evaluate_batch(
            legal_initial,
            generation=0,
            archive=archive,
        )
        total_calls = calls
        total_pairs = pairs
        for row in initial_eval:
            evaluations_by_variant[row.candidate_id] = row
        history.append(
            {
                "generation": 0,
                "candidate_count": len(legal_initial),
                "archive": archive.coverage(),
                "operator_weights": dict(operator_weights),
                "policy_weights": dict(policy_weights),
            }
        )
        feedback_changed = False

        for generation in range(1, generations + 1):
            parents = archive.variants()
            if not parents:
                break
            parent_by_policy: dict[str, list[WholeDeckVariant]] = defaultdict(list)
            for parent in parents:
                parent_by_policy[parent.policy_id.value].append(parent)

            proposals: list[WholeDeckVariant] = []
            proposal_metadata: dict[str, tuple[str, str, str]] = {}
            attempts = 0
            max_attempts = max(proposals_per_generation * 12, 32)
            while len(proposals) < proposals_per_generation and attempts < max_attempts:
                attempts += 1
                available_policy_weights = {
                    key: policy_weights[key] for key in policy_weights if parent_by_policy.get(key)
                }
                if not available_policy_weights:
                    break
                policy_id = _weighted_choice(rng, available_policy_weights)
                parent_pool = sorted(
                    parent_by_policy[policy_id],
                    key=lambda row: row.deck_hash,
                )
                parent = parent_pool[rng.randrange(len(parent_pool))]
                operator_name = _weighted_choice(rng, operator_weights)
                neighborhood = WholeDeckNeighborhood(operator_name)
                engine = self.engines[policy_id]
                board, removed, added = engine.propose(parent.mainboard, neighborhood, rng)
                if board == parent.mainboard or not removed or not added:
                    continue
                mutation = WholeDeckMutation(
                    neighborhood=neighborhood,
                    removed=removed,
                    added=added,
                    changed_slots=max(len(removed), len(added)),
                )
                proposal = engine.evaluate_mainboard(
                    board,
                    seed=self.seed + generation * 1_000_003 + attempts,
                    parent_variant_id=parent.variant_id,
                    mutation=mutation,
                )
                if not proposal.hard_gate.valid or proposal.deck_hash in seen:
                    continue
                seen[proposal.deck_hash] = proposal
                proposals.append(proposal)
                proposal_metadata[proposal.variant_id] = (
                    parent.variant_id,
                    operator_name,
                    policy_id,
                )

            generation_eval, calls, pairs = self._evaluate_batch(
                proposals,
                generation=generation,
                archive=archive,
            )
            total_calls += calls
            total_pairs += pairs
            operator_rewards: dict[str, list[float]] = defaultdict(list)
            policy_rewards: dict[str, list[float]] = defaultdict(list)
            for row in generation_eval:
                evaluations_by_variant[row.candidate_id] = row
                parent_id, operator_name, policy_id = proposal_metadata[row.candidate_id]
                parent_eval = evaluations_by_variant.get(parent_id)
                reward = row.robust_lower_bound - (
                    parent_eval.robust_lower_bound if parent_eval is not None else 0.0
                )
                operator_rewards[operator_name].append(reward)
                policy_rewards[policy_id].append(reward)

            old_operator = dict(operator_weights)
            old_policy = dict(policy_weights)
            operator_weights = update_learning_weights(
                operator_weights,
                operator_rewards,
                config=self.learning,
            )
            policy_weights = update_learning_weights(
                policy_weights,
                policy_rewards,
                config=self.learning,
            )
            feedback_changed = feedback_changed or (
                operator_weights != old_operator or policy_weights != old_policy
            )
            history.append(
                {
                    "generation": generation,
                    "candidate_count": len(proposals),
                    "attempts": attempts,
                    "archive": archive.coverage(),
                    "operator_weights": dict(operator_weights),
                    "policy_weights": dict(policy_weights),
                    "operator_rewards": {
                        key: list(values) for key, values in sorted(operator_rewards.items())
                    },
                    "policy_rewards": {
                        key: list(values) for key, values in sorted(policy_rewards.items())
                    },
                }
            )
            if not proposals:
                break

        return OptimizerSearchReport(
            generations=tuple(history),
            archive=archive.coverage(),
            operator_weights=operator_weights,
            policy_weights=policy_weights,
            unique_legal_decks=len(seen),
            evaluation_calls=total_calls,
            requested_scenario_pairs=total_pairs,
            feedback_changed_proposals=feedback_changed,
        )


class ProjectPairedEvaluator:
    """Manifest-bound exploratory evaluator using the balanced 4P scheduler."""

    def __init__(
        self,
        *,
        root: str,
        manifest: OptimizerManifest,
        orchestrator: WholeDeckCampaignOrchestrator,
        control_mainboard: tuple[str, ...],
        context: Any,
        workers: int,
        max_turns: int,
    ) -> None:
        self.root = root
        self.manifest = manifest
        self.orchestrator = orchestrator
        self.context = context
        self.control = context.materialize(control_mainboard, label="optimizer-v2-control")
        if self.control.deck_hash != manifest.control_deck_hash:
            raise ValueError("optimizer manifest control hash does not match current control")
        self.workers = workers
        self.max_turns = max_turns
        self.scenarios = tuple(
            orchestrator.scheduler.schedule(
                len(manifest.exploratory.scenario_ids),
                seed=manifest.exploratory.master_seed,
            )
        )
        _verify_partition(self.scenarios, manifest.exploratory)
        self.advancement_evidence: dict[str, CandidatePairedEvidence] = {}

    def __call__(
        self,
        variant: WholeDeckVariant,
        budget: int,
        statistics_offset: int,
    ) -> ExploratoryEvaluation:
        if budget > len(self.scenarios):
            raise ValueError("exploratory budget exceeds frozen scenario partition")
        if not variant.hard_gate.valid:
            raise ValueError("illegal candidate reached paired simulation")

        candidate = self.context.materialize(
            variant.mainboard,
            label=variant.deck_hash[:12],
        )
        chosen = self.scenarios[:budget]
        groups = (
            (
                PilotConfig(
                    strength=PilotStrength.STRONG,
                    mode=PilotDecisionMode.DETERMINISTIC,
                ),
                chosen[::2],
            ),
            (
                PilotConfig(
                    strength=PilotStrength.AVERAGE,
                    mode=PilotDecisionMode.DETERMINISTIC,
                ),
                chosen[1::2],
            ),
        )
        observations: list[dict[str, object]] = []
        pairing_rows: list[Mapping[str, object]] = []
        for pilot, scenarios in groups:
            if not scenarios:
                continue
            result = run_balanced_paired_campaign(
                baseline=self.control,
                variant=candidate,
                opponent_profiles=self.orchestrator.opponents.profiles(),
                scenarios=scenarios,
                pilot_config=pilot,
                max_turns=self.max_turns,
                statistics_seed=self.manifest.exploratory.master_seed + statistics_offset,
                workers=self.workers,
            )
            raw = result.get("paired_observations", [])
            if not isinstance(raw, list):
                raise TypeError("paired campaign observations are malformed")
            observations.extend(row for row in raw if isinstance(row, dict))
            raw_pairing = result.get("pairing_conditions")
            if not isinstance(raw_pairing, Mapping):
                raise TypeError("paired campaign pairing conditions are malformed")
            pairing_rows.append(raw_pairing)

        differences = tuple(
            _placement(row, "baseline_placement") - _placement(row, "variant_placement")
            for row in observations
        )
        if len(differences) != budget:
            raise RuntimeError("exploratory paired evaluator did not cover requested budget")
        interval = paired_bootstrap_interval(
            differences,
            seed=self.manifest.exploratory.master_seed + statistics_offset + 23,
        )
        robust = distributionally_robust_lower_bound(differences)
        score = fmean(differences)
        self.advancement_evidence[variant.variant_id] = CandidatePairedEvidence(
            candidate_id=variant.variant_id,
            deck_hash=variant.deck_hash,
            budget=budget,
            interval_low=interval[0],
            interval_high=interval[1],
            observations=tuple(dict(row) for row in observations),
            pairing_conditions=merge_pairing_conditions(pairing_rows),
        )
        return ExploratoryEvaluation(
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
            score=score,
            interval_low=interval[0],
            interval_high=interval[1],
            robust_lower_bound=robust,
            qd_cell=descriptor_for_variant(variant).cell(self.manifest.qd),
            evidence_context=EvidenceContext.EXPLORATORY,
            evidence_type="structural_model_estimates",
        )


def _verify_partition(
    scenarios: Sequence[PodScenario],
    partition: EvidencePartition,
) -> None:
    ids = tuple(row.scenario_id for row in scenarios)
    seeds = tuple(row.seed for row in scenarios)
    if ids != partition.scenario_ids or seeds != partition.scenario_seeds:
        raise ValueError("scheduled scenarios do not match frozen evidence partition")
