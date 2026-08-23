from __future__ import annotations

import random
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from statistics import fmean
from typing import Any, TypedDict, cast

from commander_lab.decision_statistics import (
    distributionally_robust_lower_bound,
    paired_bootstrap_interval,
)
from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength
from commander_lab.pod_scheduling import PodScenario
from commander_lab.storage import sha256_value

from .campaign import run_balanced_paired_campaign
from .lab_context import EnrichedWholeDeckSearchEngine
from .mechanics_fidelity import assess_card_fidelity, assess_variant_mechanics
from .models import PolicyId
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
EligibilityFunction = Callable[[WholeDeckVariant], bool]


class CoverageDebtCounters(TypedDict):
    attempts: int
    noop: int
    duplicate: int
    illegal: int
    target_cards_considered: int
    newly_exposed_cards: list[str]


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
    screening_only_hashes: tuple[str, ...] = ()
    hypothesis_archive: dict[str, object] | None = None
    telemetry: dict[str, object] | None = None
    search_health: dict[str, object] | None = None


class HypothesisCoverageArchive:
    """Outcome-independent archive for structural coverage/hypothesis generation.

    It never receives or ranks on Structural placement outcomes. Candidates are retained by QD cell,
    evidence route and construction policy using only construction prior + deterministic hash. This
    keeps low-fidelity hypotheses alive without granting their screening scores decision authority.
    """

    def __init__(self, config: QDConfig, *, elites_per_bucket: int = 2) -> None:
        self.config = config
        self.elites_per_bucket = max(1, elites_per_bucket)
        self._buckets: dict[str, list[WholeDeckVariant]] = {}

    def admit(self, variant: WholeDeckVariant, *, route: str) -> bool:
        if not variant.hard_gate.valid:
            return False
        cell = descriptor_for_variant(variant).cell(self.config)
        key = f"{cell}|{route}|{variant.policy_id.value}"
        rows = [row for row in self._buckets.get(key, ()) if row.deck_hash != variant.deck_hash]
        rows.append(variant)
        rows.sort(key=lambda row: (-row.objective_prior, row.deck_hash))
        kept = rows[: self.elites_per_bucket]
        self._buckets[key] = kept
        return any(row.deck_hash == variant.deck_hash for row in kept)

    def variants(self) -> tuple[WholeDeckVariant, ...]:
        by_hash: dict[str, WholeDeckVariant] = {}
        for rows in self._buckets.values():
            for row in rows:
                by_hash.setdefault(row.deck_hash, row)
        return tuple(by_hash[key] for key in sorted(by_hash))

    def coverage(self) -> dict[str, object]:
        variants = self.variants()
        qd_cells = {descriptor_for_variant(row).cell(self.config) for row in variants}
        return {
            "archive_role": "HYPOTHESIS_GENERATION_COVERAGE_ONLY",
            "outcome_ranked": False,
            "bucket_count": len(self._buckets),
            "occupied_qd_cells": len(qd_cells),
            "archive_size": len(variants),
            "qd_cells": sorted(qd_cells),
            "buckets": {
                key: [row.deck_hash for row in self._buckets[key]] for key in sorted(self._buckets)
            },
        }


def _evaluator_context_and_control(
    evaluator: EvaluationFunction,
) -> tuple[Any | None, tuple[str, ...] | None]:
    context = getattr(evaluator, "context", None)
    explicit = getattr(evaluator, "control_mainboard", None)
    if context is not None and isinstance(explicit, tuple):
        return context, tuple(str(value) for value in explicit)
    control = getattr(evaluator, "control", None)
    cards = getattr(control, "cards", None)
    commander_names = frozenset(getattr(control, "commander_names", ()))
    if context is None or cards is None:
        return context, None
    return context, tuple(
        str(card.oracle_name) for card in cards if str(card.oracle_name) not in commander_names
    )


def _variant_fidelity_assessment(
    evaluator: EvaluationFunction,
    variant: WholeDeckVariant,
    *,
    fallback_safe: bool,
) -> dict[str, object]:
    context, control = _evaluator_context_and_control(evaluator)
    if context is None or control is None:
        return {
            "pass": fallback_safe,
            "required_next_evidence_layer": (
                "STRUCTURAL_CONFIRMATORY_ALLOWED" if fallback_safe else "STRUCTURAL_SCREENING_ONLY"
            ),
            "fidelity_distance_to_safe": 0 if fallback_safe else 1,
            "tier_counts": {},
        }
    return assess_variant_mechanics(
        context,
        control=control,
        candidate=variant.mainboard,
        deck_hash=variant.deck_hash,
    )


def _nonnegative_int(value: object, default: int = 0) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return default


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


def _evaluator_mechanics_gate(evaluator: EvaluationFunction) -> EligibilityFunction | None:
    explicit = getattr(evaluator, "structural_decision_safe", None)
    if callable(explicit):
        return cast(EligibilityFunction, explicit)

    context = getattr(evaluator, "context", None)
    control = getattr(evaluator, "control", None)
    cards = getattr(control, "cards", None)
    commander_names = frozenset(getattr(control, "commander_names", ()))
    if context is None or cards is None:
        return None
    control_mainboard = tuple(
        str(card.oracle_name) for card in cards if str(card.oracle_name) not in commander_names
    )

    def _gate(variant: WholeDeckVariant) -> bool:
        assessment = assess_variant_mechanics(
            context,
            control=control_mainboard,
            candidate=variant.mainboard,
            deck_hash=variant.deck_hash,
        )
        return assessment.get("pass") is True

    return _gate


class AdaptiveWholeDeckSearch:
    """Two-lane exploratory search with strict decision-evidence isolation.

    Every legal candidate may enter the outcome-independent hypothesis/coverage archive after its
    authorized first Structural screening look. Only question-specifically decision-safe candidates
    may receive later Structural racing budgets, enter the decision QD archive, or train adaptive
    performance rewards. Screening outcomes never rank or select hypothesis parents.
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
        self.expensive_evidence_eligible = _evaluator_mechanics_gate(evaluator)

    def _eligible_for_expensive_evidence(self, variant: WholeDeckVariant) -> bool:
        if self.expensive_evidence_eligible is None:
            return True
        return bool(self.expensive_evidence_eligible(variant))

    def _assessment(self, variant: WholeDeckVariant) -> dict[str, object]:
        safe = self._eligible_for_expensive_evidence(variant)
        return _variant_fidelity_assessment(self.evaluator, variant, fallback_safe=safe)

    @staticmethod
    def _operator_label(variant: WholeDeckVariant) -> str:
        explicit = variant.provenance.get("optimizer_operator")
        if isinstance(explicit, str) and explicit:
            return explicit
        if variant.mutation is not None:
            return variant.mutation.neighborhood.value
        return "construction_prior"

    def _evaluate_batch(
        self,
        variants: Sequence[WholeDeckVariant],
        *,
        generation: int,
        archive: QualityDiversityArchive,
        hypothesis_archive: HypothesisCoverageArchive | None = None,
    ) -> tuple[list[ExploratoryEvaluation], int, int]:
        if hypothesis_archive is None:
            hypothesis_archive = HypothesisCoverageArchive(self.qd)
        if not variants:
            return [], 0, 0
        current: list[ExploratoryEvaluation] = []
        calls = 0
        scenario_pairs = 0
        first_budget = self.racing.budgets[0]
        assessments: dict[str, dict[str, object]] = {}
        for variant in variants:
            assessment = self._assessment(variant)
            assessments[variant.variant_id] = assessment
            hypothesis_archive.admit(
                variant,
                route=str(assessment.get("required_next_evidence_layer", "UNKNOWN")),
            )
        hypothesis_reference = hypothesis_archive.variants()
        for index, variant in enumerate(variants):
            raw = self.evaluator(variant, first_budget, generation * 100_003 + index)
            novelty = novelty_score(
                variant,
                hypothesis_reference,
                neighbors=self.qd.novelty_neighbors,
            )
            current.append(
                raw.model_copy(
                    update={
                        "generation": generation,
                        "novelty": novelty,
                        "qd_cell": descriptor_for_variant(variant).cell(self.qd),
                        "operator": self._operator_label(variant),
                    }
                )
            )
            calls += 1
            scenario_pairs += first_budget

        by_id = {row.candidate_id: row for row in current}
        variant_by_id = {variant.variant_id: variant for variant in variants}
        active_ids = tuple(by_id)
        for budget_index, budget in enumerate(self.racing.budgets[1:], start=1):
            active_rows = tuple(
                by_id[candidate_id]
                for candidate_id in active_ids
                if assessments[candidate_id].get("pass") is True
            )
            if not active_rows:
                break
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
                        "operator": self._operator_label(variant),
                    }
                )
                calls += 1
                scenario_pairs += budget
            by_id.update(next_rows)
            active_ids = survivor_ids

        final_rows = list(by_id.values())
        for row in final_rows:
            variant = variant_by_id[row.candidate_id]
            if assessments[row.candidate_id].get("pass") is True:
                archive.admit(variant, row)
        return final_rows, calls, scenario_pairs

    def _fidelity_repair_proposals(
        self,
        *,
        control_variant: WholeDeckVariant | None,
        generation: int,
        limit: int,
        seen: Mapping[str, WholeDeckVariant],
    ) -> tuple[list[WholeDeckVariant], dict[str, int]]:
        counters = {"attempts": 0, "noop": 0, "duplicate": 0, "illegal": 0}
        if control_variant is None or limit <= 0:
            return [], counters
        context, control = _evaluator_context_and_control(self.evaluator)
        engine = self.engines.get(PolicyId.CURRENT_CONTROL.value)
        if context is None or control is None or engine is None:
            return [], counters

        control_counts = Counter(control)
        safe_remove_names = [
            name
            for name in sorted(control_counts)
            if assess_card_fidelity(context, name).get("decision_safe") is True
        ]
        safe_add_names: list[str] = []
        for name, card in sorted(context.cards.items()):
            if assess_card_fidelity(context, name).get("decision_safe") is not True:
                continue
            current = control_counts[name]
            available = int(getattr(card, "available_quantity", 0))
            if bool(getattr(card, "is_basic", False)) or current < available:
                safe_add_names.append(name)
        pairs = [
            (remove_name, add_name)
            for remove_name in safe_remove_names
            for add_name in safe_add_names
            if remove_name != add_name
        ]
        rng = random.Random(self.seed ^ (generation * 0x9E37_79B1))
        rng.shuffle(pairs)
        proposals: list[WholeDeckVariant] = []
        for remove_name, add_name in pairs:
            if len(proposals) >= limit:
                break
            counters["attempts"] += 1
            board = list(control)
            try:
                index = board.index(remove_name)
            except ValueError:
                counters["noop"] += 1
                continue
            board[index] = add_name
            candidate = tuple(board)
            if candidate == control:
                counters["noop"] += 1
                continue
            mutation = WholeDeckMutation(
                neighborhood=WholeDeckNeighborhood.ROLE_PACKAGE,
                removed=(remove_name,),
                added=(add_name,),
                changed_slots=1,
            )
            proposal = engine.evaluate_mainboard(
                candidate,
                seed=self.seed + generation * 2_000_003 + counters["attempts"],
                parent_variant_id=control_variant.variant_id,
                mutation=mutation,
            )
            proposal = proposal.model_copy(
                update={
                    "provenance": {
                        **proposal.provenance,
                        "optimizer_operator": "fidelity_repair",
                        "proposal_lane": "DECISION_SAFE_REACHABILITY",
                        "control_aware_special_emitter": True,
                        "fresh_rebuild_policy_prior": False,
                        "optimizer_generation": generation,
                    }
                }
            )
            if not proposal.hard_gate.valid:
                counters["illegal"] += 1
                continue
            if proposal.deck_hash in seen or any(
                row.deck_hash == proposal.deck_hash for row in proposals
            ):
                counters["duplicate"] += 1
                continue
            if self._assessment(proposal).get("pass") is not True:
                # The emitter is a reachability helper, never a fidelity override.
                counters["illegal"] += 1
                continue
            proposals.append(proposal)
        return proposals, counters

    def _coverage_debt_proposals(
        self,
        *,
        control_variant: WholeDeckVariant | None,
        generation: int,
        limit: int,
        seen: Mapping[str, WholeDeckVariant],
    ) -> tuple[list[WholeDeckVariant], CoverageDebtCounters]:
        """Emit deterministic outcome-independent forced-inclusion coverage hypotheses.

        This lane pays down finite-search exposure debt only.  It does not read Structural
        placement/effect values, does not rank by screening outcomes and does not bypass normal
        legality or mechanics-fidelity gates.  A generated candidate may later enter the Decision
        lane only through the ordinary independent fidelity assessment.
        """

        counters: CoverageDebtCounters = {
            "attempts": 0,
            "noop": 0,
            "duplicate": 0,
            "illegal": 0,
            "target_cards_considered": 0,
            "newly_exposed_cards": [],
        }
        if control_variant is None or limit <= 0:
            return [], counters
        context, control = _evaluator_context_and_control(self.evaluator)
        engine = self.engines.get(PolicyId.CURRENT_CONTROL.value)
        if context is None or control is None or engine is None:
            return [], counters

        control_counts = Counter(control)
        exposure_counts: Counter[str] = Counter()
        for variant in seen.values():
            exposure_counts.update(set(variant.mainboard))

        candidates: list[str] = []
        for name, card in sorted(context.cards.items()):
            current = control_counts[name]
            available = int(getattr(card, "available_quantity", 0))
            if not bool(getattr(card, "is_basic", False)) and current >= available:
                continue
            candidates.append(name)
        candidates.sort(key=lambda name: (exposure_counts[name], name))

        proposals: list[WholeDeckVariant] = []
        newly_exposed: list[str] = []
        for add_name in candidates:
            if len(proposals) >= limit:
                break
            counters["target_cards_considered"] += 1
            add_card = context.cards[add_name]
            # Coherence preference is outcome-independent: preserve land/nonland shape first, then
            # prefer role overlap.  A stable hash breaks any remaining ties deterministically.
            add_roles = frozenset(getattr(getattr(add_card, "profile", None), "roles", ()))
            add_is_land = bool(getattr(add_card, "is_basic", False)) or bool(
                getattr(getattr(add_card, "profile", None), "is_land", False)
            )

            def removal_key(
                remove_name: str,
                *,
                add_name_bound: str = add_name,
                add_roles_bound: frozenset[object] = add_roles,
                add_is_land_bound: bool = add_is_land,
            ) -> tuple[int, int, str]:
                remove_card = context.cards.get(remove_name)
                remove_profile = getattr(remove_card, "profile", None)
                remove_is_land = bool(getattr(remove_card, "is_basic", False)) or bool(
                    getattr(remove_profile, "is_land", False)
                )
                remove_roles = set(getattr(remove_profile, "roles", ()))
                same_land_class = 0 if remove_is_land == add_is_land_bound else 1
                role_gap = len(add_roles_bound.symmetric_difference(remove_roles))
                tie = sha256_value(
                    {
                        "seed": self.seed,
                        "generation": generation,
                        "add": add_name_bound,
                        "remove": remove_name,
                    }
                )
                return same_land_class, role_gap, tie

            remove_names = [
                name
                for name in sorted(control_counts)
                if name != add_name and control_counts[name] > 0
            ]
            remove_names.sort(key=removal_key)
            for remove_name in remove_names:
                counters["attempts"] += 1
                board = list(control)
                try:
                    index = board.index(remove_name)
                except ValueError:
                    counters["noop"] += 1
                    continue
                board[index] = add_name
                candidate = tuple(board)
                if candidate == control:
                    counters["noop"] += 1
                    continue
                mutation = WholeDeckMutation(
                    neighborhood=WholeDeckNeighborhood.ROLE_PACKAGE,
                    removed=(remove_name,),
                    added=(add_name,),
                    changed_slots=1,
                )
                proposal = engine.evaluate_mainboard(
                    candidate,
                    seed=self.seed + generation * 3_000_017 + counters["attempts"],
                    parent_variant_id=control_variant.variant_id,
                    mutation=mutation,
                )
                proposal = proposal.model_copy(
                    update={
                        "provenance": {
                            **proposal.provenance,
                            "optimizer_operator": "coverage_debt",
                            "proposal_lane": "COVERAGE_DEBT",
                            "coverage_only_parent": True,
                            "outcome_ranked": False,
                            "control_aware_special_emitter": True,
                            "fresh_rebuild_policy_prior": False,
                            "optimizer_generation": generation,
                            "coverage_target_card": add_name,
                            "coverage_prior_exposure_count": exposure_counts[add_name],
                        }
                    }
                )
                if not proposal.hard_gate.valid:
                    counters["illegal"] += 1
                    continue
                if proposal.deck_hash in seen or any(
                    row.deck_hash == proposal.deck_hash for row in proposals
                ):
                    counters["duplicate"] += 1
                    continue
                proposals.append(proposal)
                if exposure_counts[add_name] == 0:
                    newly_exposed.append(add_name)
                break

        counters["newly_exposed_cards"] = sorted(set(newly_exposed))
        return proposals, counters

    def run(
        self,
        *,
        initial_variants: Sequence[WholeDeckVariant],
        generations: int,
        proposals_per_generation: int,
    ) -> OptimizerSearchReport:
        legal_initial = [
            row.model_copy(
                update={
                    "provenance": {
                        **row.provenance,
                        "optimizer_generation": 0,
                        "proposal_lane": (
                            "DECISION_ANCHOR"
                            if row.policy_id == PolicyId.CURRENT_CONTROL
                            else "CONSTRUCTION_PRIOR"
                        ),
                    }
                }
            )
            for row in initial_variants
            if row.hard_gate.valid
        ]
        if not legal_initial:
            raise ValueError("adaptive search has no legal initial variants")

        archive = QualityDiversityArchive(self.qd)
        hypothesis_archive = HypothesisCoverageArchive(self.qd)
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
        variants_by_id: dict[str, WholeDeckVariant] = {row.variant_id: row for row in legal_initial}
        evaluations_by_variant: dict[str, ExploratoryEvaluation] = {}
        rejection_counts: Counter[str] = Counter()
        parent_hashes: dict[str, set[str]] = {
            "decision_lane": set(),
            "hypothesis_lane": set(),
        }
        adaptive_reward_observations = 0
        generated_by_generation: dict[int, list[WholeDeckVariant]] = {0: list(legal_initial)}

        initial_eval, calls, pairs = self._evaluate_batch(
            legal_initial,
            generation=0,
            archive=archive,
            hypothesis_archive=hypothesis_archive,
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
                "decision_archive": archive.coverage(),
                "hypothesis_archive": hypothesis_archive.coverage(),
                "operator_weights": dict(operator_weights),
                "policy_weights": dict(policy_weights),
            }
        )
        feedback_changed = False
        control_variant = next(
            (
                row
                for row in legal_initial
                if row.policy_id == PolicyId.CURRENT_CONTROL and row.parent_variant_id is None
            ),
            None,
        )

        for generation in range(1, generations + 1):
            combined: dict[str, WholeDeckVariant] = {
                row.deck_hash: row for row in hypothesis_archive.variants()
            }
            combined.update({row.deck_hash: row for row in archive.variants()})
            parents = tuple(combined[key] for key in sorted(combined))
            if not parents:
                break
            parent_by_policy: dict[str, list[WholeDeckVariant]] = defaultdict(list)
            for parent in parents:
                parent_by_policy[parent.policy_id.value].append(parent)

            repair_limit = min(4, max(1, proposals_per_generation // 6))
            repair, repair_counts = self._fidelity_repair_proposals(
                control_variant=control_variant,
                generation=generation,
                limit=repair_limit,
                seen=seen,
            )
            rejection_counts.update(
                {
                    "raw_proposals_attempted": repair_counts["attempts"],
                    "noop_proposals_rejected": repair_counts["noop"],
                    "duplicate_proposals_rejected": repair_counts["duplicate"],
                    "illegal_proposals_rejected": repair_counts["illegal"],
                }
            )
            coverage_limit = min(2, max(1, proposals_per_generation // 8))
            coverage, coverage_counts = self._coverage_debt_proposals(
                control_variant=control_variant,
                generation=generation,
                limit=max(0, min(coverage_limit, proposals_per_generation - len(repair))),
                seen=seen,
            )
            rejection_counts.update(
                {
                    "raw_proposals_attempted": coverage_counts["attempts"],
                    "noop_proposals_rejected": coverage_counts["noop"],
                    "duplicate_proposals_rejected": coverage_counts["duplicate"],
                    "illegal_proposals_rejected": coverage_counts["illegal"],
                }
            )
            proposals: list[WholeDeckVariant] = list(repair) + list(coverage)
            proposal_metadata: dict[str, tuple[str, str, str, str]] = {}
            for proposal in repair:
                parent_id = proposal.parent_variant_id or ""
                proposal_metadata[proposal.variant_id] = (
                    parent_id,
                    "fidelity_repair",
                    PolicyId.CURRENT_CONTROL.value,
                    "decision_lane",
                )
                seen[proposal.deck_hash] = proposal
                variants_by_id[proposal.variant_id] = proposal
            for proposal in coverage:
                parent_id = proposal.parent_variant_id or ""
                proposal_metadata[proposal.variant_id] = (
                    parent_id,
                    "coverage_debt",
                    PolicyId.CURRENT_CONTROL.value,
                    "coverage_debt",
                )
                seen[proposal.deck_hash] = proposal
                variants_by_id[proposal.variant_id] = proposal
                parent_hashes["hypothesis_lane"].add(
                    control_variant.deck_hash if control_variant else ""
                )

            attempts = 0
            max_attempts = max(proposals_per_generation * 12, 32)
            while len(proposals) < proposals_per_generation and attempts < max_attempts:
                attempts += 1
                rejection_counts["raw_proposals_attempted"] += 1
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
                parent_safe = self._assessment(parent).get("pass") is True
                parent_source = "decision_lane" if parent_safe else "hypothesis_lane"
                parent_hashes[parent_source].add(parent.deck_hash)
                operator_name = _weighted_choice(rng, operator_weights)
                neighborhood = WholeDeckNeighborhood(operator_name)
                engine = self.engines[policy_id]
                board, removed, added = engine.propose(parent.mainboard, neighborhood, rng)
                if board == parent.mainboard or not removed or not added:
                    rejection_counts["noop_proposals_rejected"] += 1
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
                proposal = proposal.model_copy(
                    update={
                        "provenance": {
                            **proposal.provenance,
                            "optimizer_generation": generation,
                            "proposal_lane": parent_source,
                        }
                    }
                )
                if not proposal.hard_gate.valid:
                    rejection_counts["illegal_proposals_rejected"] += 1
                    continue
                if proposal.deck_hash in seen:
                    rejection_counts["duplicate_proposals_rejected"] += 1
                    continue
                seen[proposal.deck_hash] = proposal
                variants_by_id[proposal.variant_id] = proposal
                proposals.append(proposal)
                proposal_metadata[proposal.variant_id] = (
                    parent.variant_id,
                    operator_name,
                    policy_id,
                    parent_source,
                )

            generated_by_generation[generation] = list(proposals)
            generation_eval, calls, pairs = self._evaluate_batch(
                proposals,
                generation=generation,
                archive=archive,
                hypothesis_archive=hypothesis_archive,
            )
            total_calls += calls
            total_pairs += pairs
            operator_rewards: dict[str, list[float]] = defaultdict(list)
            policy_rewards: dict[str, list[float]] = defaultdict(list)
            proposal_by_id = {proposal.variant_id: proposal for proposal in proposals}
            for row in generation_eval:
                evaluations_by_variant[row.candidate_id] = row
                variant = proposal_by_id[row.candidate_id]
                if self._assessment(variant).get("pass") is not True:
                    continue
                metadata = proposal_metadata.get(row.candidate_id)
                if metadata is None:
                    continue
                parent_id, operator_name, policy_id, parent_source = metadata
                if parent_source == "coverage_debt":
                    # Coverage debt is hypothesis-generation infrastructure; its outcomes must not
                    # train adaptive operator/policy rewards.
                    continue
                parent_variant = variants_by_id.get(parent_id)
                if (
                    parent_variant is None
                    or self._assessment(parent_variant).get("pass") is not True
                ):
                    continue
                parent_eval = evaluations_by_variant.get(parent_id)
                if parent_eval is None:
                    continue
                reward = row.robust_lower_bound - parent_eval.robust_lower_bound
                if operator_name in operator_weights:
                    operator_rewards[operator_name].append(reward)
                if policy_id in policy_weights:
                    policy_rewards[policy_id].append(reward)
                adaptive_reward_observations += 1

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
            generation_assessments = [self._assessment(row) for row in proposals]
            distances = [
                _nonnegative_int(row.get("fidelity_distance_to_safe", 0))
                for row in generation_assessments
            ]
            history.append(
                {
                    "generation": generation,
                    "candidate_count": len(proposals),
                    "attempts": attempts
                    + repair_counts["attempts"]
                    + coverage_counts["attempts"],
                    "decision_archive": archive.coverage(),
                    "hypothesis_archive": hypothesis_archive.coverage(),
                    "operator_weights": dict(operator_weights),
                    "policy_weights": dict(policy_weights),
                    "operator_rewards": {
                        key: list(values) for key, values in sorted(operator_rewards.items())
                    },
                    "policy_rewards": {
                        key: list(values) for key, values in sorted(policy_rewards.items())
                    },
                    "safe_promotions": sum(
                        row.get("pass") is True for row in generation_assessments
                    ),
                    "fidelity_distance_to_safe": {
                        "minimum": min(distances) if distances else None,
                        "mean": fmean(distances) if distances else None,
                    },
                    "fidelity_repair_generated": len(repair),
                    "coverage_debt_generated": len(coverage),
                    "coverage_debt_targets_considered": coverage_counts[
                        "target_cards_considered"
                    ],
                    "coverage_debt_newly_exposed_cards": list(
                        coverage_counts["newly_exposed_cards"]
                    ),
                }
            )
            if not proposals:
                break

        assessment_by_hash = {deck_hash: self._assessment(row) for deck_hash, row in seen.items()}
        screening_only_hashes = tuple(
            sorted(
                deck_hash
                for deck_hash, assessment in assessment_by_hash.items()
                if assessment.get("pass") is not True
            )
        )
        route_counts: Counter[str] = Counter(
            str(row.get("required_next_evidence_layer", "UNKNOWN"))
            for row in assessment_by_hash.values()
        )
        decision_safe_generated = sum(
            row.get("pass") is True for row in assessment_by_hash.values()
        )
        policies_seen = sorted({row.policy_id.value for row in seen.values()})
        operators_seen = sorted({self._operator_label(row) for row in seen.values()})
        all_cards = {name for row in seen.values() for name in row.mainboard}
        context, _control = _evaluator_context_and_control(self.evaluator)
        pool_count = len(getattr(context, "cards", {})) if context is not None else 0
        package_ids: set[str] = set()
        role_profiles: set[str] = set()
        mana_values: set[float] = set()
        land_counts: set[int] = set()
        finish_values: set[float] = set()
        for variant in seen.values():
            packages = variant.feature_vector.get("package_counts", {})
            if isinstance(packages, Mapping):
                package_ids.update(str(key) for key in packages)
            roles = variant.feature_vector.get("role_strengths", {})
            if isinstance(roles, Mapping):
                role_profiles.add(
                    repr(
                        tuple(
                            sorted(
                                (str(k), float(v))
                                for k, v in roles.items()
                                if isinstance(v, int | float)
                            )
                        )
                    )
                )
            descriptor = descriptor_for_variant(variant)
            mana_values.add(round(descriptor.average_nonland_mv, 3))
            land_counts.add(descriptor.land_count)
            finish_values.add(round(descriptor.finish_strength, 3))

        decision_coverage = archive.coverage()
        hypothesis_coverage = hypothesis_archive.coverage()
        control_hash = str(getattr(getattr(self.evaluator, "control", None), "deck_hash", ""))
        decision_hashes = {
            deck_hash
            for values in cast(Mapping[str, list[str]], decision_coverage.get("cells", {})).values()
            for deck_hash in values
        }
        noncontrol_decision = {value for value in decision_hashes if value != control_hash}
        health_flags: list[str] = []
        if _nonnegative_int(hypothesis_coverage.get("occupied_qd_cells", 0)) <= 1 and len(seen) > 1:
            health_flags.append("SEARCH_COLLAPSE")
        if not noncontrol_decision:
            health_flags.extend(["DECISION_LANE_EMPTY", "FIDELITY_LIVENESS_LIMIT"])
        if adaptive_reward_observations == 0:
            health_flags.append("ADAPTIVE_REWARD_INACTIVE")
        if route_counts["TACTICAL_EVIDENCE_REQUIRED"]:
            health_flags.append("TACTICAL_EVIDENCE_NEEDED")
        if route_counts["EXTERNAL_RULES_EVIDENCE_REQUIRED"]:
            health_flags.append("EXTERNAL_RULES_EVIDENCE_NEEDED")
        primary_status = (
            "SEARCH_HEALTHY"
            if not {"SEARCH_COLLAPSE", "DECISION_LANE_EMPTY"}.intersection(health_flags)
            else health_flags[0]
        )
        coverage_debt_cards = sorted(
            {
                str(name)
                for row in history
                for name in cast(list[object], row.get("coverage_debt_newly_exposed_cards", []))
            }
        )
        telemetry: dict[str, object] = {
            **dict(rejection_counts),
            "unique_legal_decks_generated": len(seen),
            "unique_legal_decks_evaluated": len(seen),
            "duplicate_decks_removed": rejection_counts["duplicate_proposals_rejected"],
            "construction_policy_coverage": policies_seen,
            "construction_policy_coverage_count": len(policies_seen),
            "operator_coverage": operators_seen,
            "operator_coverage_count": len(operators_seen),
            "candidate_card_exposure": len(all_cards),
            "candidate_card_exposure_names": sorted(all_cards),
            "candidate_card_unexposed_names": (
                sorted(set(getattr(context, "cards", {})) - all_cards)
                if context is not None
                else []
            ),
            "candidate_card_exposure_fraction": (
                len(all_cards) / pool_count if pool_count else None
            ),
            "coverage_debt_newly_exposed_cards": coverage_debt_cards,
            "coverage_debt_newly_exposed_card_count": len(coverage_debt_cards),
            "coverage_debt_generated_count": sum(
                int(row.get("coverage_debt_generated", 0)) for row in history
            ),
            "coverage_debt_outcome_ranked": False,
            "package_coverage": sorted(package_ids),
            "package_coverage_count": len(package_ids),
            "mana_curve_diversity": len(mana_values),
            "land_count_diversity": len(land_counts),
            "role_profile_diversity": len(role_profiles),
            "finish_axis_diversity": len(finish_values),
            "hypothesis_qd_cells_occupied": hypothesis_coverage.get("occupied_qd_cells", 0),
            "hypothesis_archive_size": hypothesis_coverage.get("archive_size", 0),
            "decision_qd_cells_occupied": decision_coverage.get("occupied_cells", 0),
            "decision_archive_size": decision_coverage.get("elite_count", 0),
            "decision_safe_generated": decision_safe_generated,
            "screening_only_generated": route_counts["STRUCTURAL_SCREENING_ONLY"],
            "tactical_required_generated": route_counts["TACTICAL_EVIDENCE_REQUIRED"],
            "external_required_generated": route_counts["EXTERNAL_RULES_EVIDENCE_REQUIRED"],
            "unsupported_generated": route_counts["SEMANTIC_OR_MODEL_CAPABILITY_REQUIRED"],
            "screening_or_higher_route_generated": len(seen) - decision_safe_generated,
            "route_counts": dict(sorted(route_counts.items())),
            "safe_promotions_by_generation": {
                str(row["generation"]): row.get("safe_promotions", 0)
                for row in history
                if int(row["generation"]) > 0
            },
            "fidelity_distance_to_safe_by_generation": {
                str(row["generation"]): row.get("fidelity_distance_to_safe")
                for row in history
                if int(row["generation"]) > 0
            },
            "decision_parent_count": len(parent_hashes["decision_lane"]),
            "hypothesis_generation_parent_count": len(parent_hashes["hypothesis_lane"]),
            "parent_source_distribution": {key: len(value) for key, value in parent_hashes.items()},
            "adaptive_reward_observation_count": adaptive_reward_observations,
            "adaptive_reward_changed_weights": feedback_changed,
            "total_structural_scenario_pairs_requested": total_pairs,
        }
        return OptimizerSearchReport(
            generations=tuple(history),
            archive=decision_coverage,
            operator_weights=operator_weights,
            policy_weights=policy_weights,
            unique_legal_decks=len(seen),
            evaluation_calls=total_calls,
            requested_scenario_pairs=total_pairs,
            feedback_changed_proposals=feedback_changed,
            screening_only_hashes=screening_only_hashes,
            hypothesis_archive=hypothesis_coverage,
            telemetry=telemetry,
            search_health={
                "primary_status": primary_status,
                "flags": sorted(set(health_flags)),
                "decision_noncontrol_elite_count": len(noncontrol_decision),
                "decision_noncontrol_elite_hashes": sorted(noncontrol_decision),
                "truth_boundary": (
                    "Search-health diagnosis; hypothesis coverage does not upgrade screening "
                    "outcomes into confirmatory evidence."
                ),
            },
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
        self.control_mainboard = control_mainboard
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

    def structural_decision_safe(self, variant: WholeDeckVariant) -> bool:
        assessment = assess_variant_mechanics(
            self.context,
            control=self.control_mainboard,
            candidate=variant.mainboard,
            deck_hash=variant.deck_hash,
        )
        return assessment.get("pass") is True

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
