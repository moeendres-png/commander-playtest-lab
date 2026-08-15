from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from commander_lab.whole_deck.models import PolicyId
from commander_lab.whole_deck.optimizer_search import AdaptiveWholeDeckSearch
from commander_lab.whole_deck.optimizer_v2 import (
    DecisionCalibrationPolicy,
    EvidenceContext,
    EvidencePartition,
    ExploratoryEvaluation,
    LearningConfig,
    OptimizerCheckpointStore,
    OptimizerLock,
    OptimizerManifest,
    QDConfig,
    QualityDiversityArchive,
    RacingConfig,
    SyntheticCalibrationFixture,
    assert_partition_disjointness,
    build_semantic_review_queue,
    deck_distance,
    descriptor_for_variant,
    deterministic_shard,
    evaluate_calibration,
    normalize_learning_weights,
    novelty_score,
    operator_names,
    optimizer_cache_identity,
    select_racing_survivors,
    update_learning_weights,
)
from commander_lab.whole_deck.search_models import (
    WholeDeckHardGate,
    WholeDeckMutation,
    WholeDeckNeighborhood,
    WholeDeckVariant,
)


def _partition(
    name: str,
    context: EvidenceContext,
    seed: int,
    scenario_offset: int,
) -> EvidencePartition:
    return EvidencePartition.create(
        partition_id=name,
        evidence_context=context,
        master_seed=seed,
        scenario_ids=tuple(f"scenario-{scenario_offset + index}" for index in range(8)),
        scenario_seeds=tuple(seed + index for index in range(8)),
    )


def _manifest() -> OptimizerManifest:
    return OptimizerManifest(
        run_id="test-optimizer-v2",
        software_commit="a" * 40,
        software_tree="b" * 40,
        package_version="1.20.4",
        engine_version="structural-0.6.0",
        physical_pool_identity="pool-v1",
        control_deck_hash="c" * 64,
        opponent_data_identity="opponents-v1",
        knowledge_identity="knowledge-v1",
        pilot_policy_identity="pilots-v1",
        mulligan_policy_identity="mulligans-v1",
        construction_prior_identity="priors-v1",
        search_seed=17,
        exploratory=_partition("exploratory", EvidenceContext.EXPLORATORY, 100, 0),
        confirmatory=_partition("confirmatory", EvidenceContext.CONFIRMATORY, 200, 100),
        sealed_holdout=_partition("holdout", EvidenceContext.HOLDOUT, 300, 200),
        calibration=DecisionCalibrationPolicy(sesoi=0.05, equivalence_margin=0.025),
    )


def _variant(
    token: str,
    *,
    lands: int = 36,
    average_mv: float = 2.4,
    interaction: float = 12.0,
    score: float = 0.0,
    valid: bool = True,
    policy: PolicyId = PolicyId.OWNED_POOL_NEUTRAL,
    parent: str | None = None,
    neighborhood: WholeDeckNeighborhood | None = None,
) -> WholeDeckVariant:
    nonlands = 98 - lands
    shared = tuple(f"Shared Spell {index}" for index in range(max(0, nonlands - 1)))
    unique = (f"Unique Spell {token}",) if nonlands else ()
    mainboard = tuple("Island" for _ in range(lands)) + shared + unique
    mutation = None
    if neighborhood is not None:
        mutation = WholeDeckMutation(
            neighborhood=neighborhood,
            removed=("Shared Spell 0",),
            added=(f"Unique Spell {token}",),
            changed_slots=1,
            accepted=True,
            objective_delta=score,
        )
    roles = {
        "counter": interaction / 2,
        "removal": interaction / 2,
        "protection": 5.0,
        "ramp": 6.0,
        "selection": 7.0,
        "draw": 5.0,
        "finisher": 4.0,
    }
    return WholeDeckVariant(
        variant_id=f"whole-deck/{token * 64}",
        deck_hash=token * 64,
        mainboard=mainboard,
        policy_id=policy,
        policy_version="test",
        seed=1,
        parent_variant_id=parent,
        mutation=mutation,
        feature_vector={
            "land_count": lands,
            "average_nonland_mv": average_mv,
            "role_strengths": roles,
            "package_counts": {"pkg-a": 3},
            "semantic_support_fraction": 1.0,
            "multiplayer_leverage": {"table": 0.5},
        },
        mana={"land_count": lands, "average_nonland_mv": average_mv},
        objective_prior=score,
        meta_distance={},
        hard_gate=WholeDeckHardGate(
            valid=valid,
            issues=() if valid else ("fixture-invalid",),
            card_count=100,
            land_count=lands,
            basic_count=lands,
        ),
        provenance={"fixture": True},
    )


def _evaluation(
    variant: WholeDeckVariant,
    *,
    score: float,
    low: float,
    high: float,
    novelty: float = 0.0,
    budget: int = 8,
) -> ExploratoryEvaluation:
    return ExploratoryEvaluation(
        candidate_id=variant.variant_id,
        deck_hash=variant.deck_hash,
        generation=0,
        parent_candidate_id=variant.parent_variant_id,
        operator="fixture",
        policy_id=variant.policy_id.value,
        budget=budget,
        score=score,
        interval_low=low,
        interval_high=high,
        robust_lower_bound=low,
        novelty=novelty,
        qd_cell=descriptor_for_variant(variant).cell(QDConfig()),
    )


def test_evidence_partitions_are_disjoint() -> None:
    manifest = _manifest()
    assert_partition_disjointness(
        manifest.exploratory,
        manifest.confirmatory,
        manifest.sealed_holdout,
    )


def test_seed_leakage_fails_closed() -> None:
    exploratory = _partition("exploratory", EvidenceContext.EXPLORATORY, 100, 0)
    confirmatory = EvidencePartition.create(
        partition_id="confirmatory",
        evidence_context=EvidenceContext.CONFIRMATORY,
        master_seed=200,
        scenario_ids=tuple(f"confirm-{index}" for index in range(8)),
        scenario_seeds=exploratory.scenario_seeds,
    )
    with pytest.raises(ValueError, match="seed leakage"):
        assert_partition_disjointness(exploratory, confirmatory)


def test_scenario_leakage_fails_closed() -> None:
    exploratory = _partition("exploratory", EvidenceContext.EXPLORATORY, 100, 0)
    confirmatory = EvidencePartition.create(
        partition_id="confirmatory",
        evidence_context=EvidenceContext.CONFIRMATORY,
        master_seed=200,
        scenario_ids=exploratory.scenario_ids,
        scenario_seeds=tuple(500 + index for index in range(8)),
    )
    with pytest.raises(ValueError, match="scenario leakage"):
        assert_partition_disjointness(exploratory, confirmatory)


def test_manifest_rejects_wrong_partition_context() -> None:
    manifest = _manifest()
    wrong = manifest.exploratory.model_copy(
        update={"evidence_context": EvidenceContext.CONFIRMATORY}
    )
    with pytest.raises(ValueError, match="must be exploratory"):
        OptimizerManifest.model_validate(
            {**manifest.model_dump(mode="json"), "exploratory": wrong.model_dump(mode="json")}
        )


def test_qd_archive_preserves_distinct_cells() -> None:
    config = QDConfig(elites_per_cell=1)
    archive = QualityDiversityArchive(config)
    low_land = _variant("1", lands=32, average_mv=2.0, interaction=8.0)
    high_land = _variant("2", lands=40, average_mv=3.2, interaction=20.0)
    assert archive.admit(low_land, _evaluation(low_land, score=0.1, low=0.05, high=0.15))
    assert archive.admit(high_land, _evaluation(high_land, score=0.1, low=0.05, high=0.15))
    coverage = archive.coverage()
    assert coverage["occupied_cells"] == 2
    assert coverage["elite_count"] == 2


def test_qd_archive_replaces_weaker_elite_in_same_cell() -> None:
    config = QDConfig(elites_per_cell=1)
    archive = QualityDiversityArchive(config)
    weak = _variant("1")
    strong = _variant("2")
    assert archive.admit(weak, _evaluation(weak, score=-0.1, low=-0.2, high=0.0))
    assert archive.admit(strong, _evaluation(strong, score=0.2, low=0.1, high=0.3))
    assert tuple(row.deck_hash for row in archive.variants()) == (strong.deck_hash,)


def test_invalid_candidate_never_enters_qd_archive() -> None:
    archive = QualityDiversityArchive(QDConfig())
    invalid = _variant("1", valid=False)
    assert not archive.admit(invalid, _evaluation(invalid, score=1.0, low=0.9, high=1.1))
    assert archive.coverage()["elite_count"] == 0


def test_deck_distance_treats_basic_multiplicity_as_multiset() -> None:
    base = _variant("1", lands=36)
    near = _variant("2", lands=37)
    far = _variant("3", lands=44, average_mv=3.8, interaction=28.0)
    near_distance = deck_distance(base, near)
    far_distance = deck_distance(base, far)
    assert 0.0 <= near_distance.card_multiset <= 1.0
    assert far_distance.total > near_distance.total


def test_novelty_is_higher_for_architecturally_distant_candidate() -> None:
    base = _variant("1", lands=36, average_mv=2.3, interaction=12.0)
    near = _variant("2", lands=37, average_mv=2.4, interaction=12.0)
    far = _variant("3", lands=44, average_mv=4.0, interaction=30.0)
    archive = (base, near)
    assert novelty_score(far, archive, neighbors=2) > novelty_score(near, (base,), neighbors=1)


def test_racing_keeps_explicit_novelty_exploration_slot() -> None:
    config = RacingConfig(
        budgets=(8, 16),
        survival_fraction=0.5,
        exploration_fraction=0.5,
        minimum_survivors=2,
    )
    rows = []
    for token, low, novelty in (
        ("1", 0.30, 0.1),
        ("2", 0.20, 0.1),
        ("3", -0.40, 1.0),
        ("4", -0.30, 0.2),
    ):
        variant = _variant(token)
        rows.append(
            _evaluation(
                variant,
                score=low + 0.05,
                low=low,
                high=low + 0.1,
                novelty=novelty,
            )
        )
    survivors = select_racing_survivors(rows, config=config)
    assert rows[0].candidate_id in survivors
    assert rows[2].candidate_id in survivors


def test_learning_feedback_changes_operator_weights() -> None:
    operators = operator_names()
    initial = normalize_learning_weights({name: 1.0 for name in operators}, floor=0.05)
    updated = update_learning_weights(
        initial,
        {operators[0]: (0.8, 0.6), operators[1]: (-0.8, -0.5)},
        config=LearningConfig(update_rate=0.4, exploration_floor=0.05),
    )
    assert updated[operators[0]] > initial[operators[0]]
    assert updated[operators[1]] < initial[operators[1]]


def test_learning_preserves_exploration_floor() -> None:
    initial = {"a": 0.99, "b": 0.01}
    updated = update_learning_weights(
        initial,
        {"a": (1.0,), "b": (-1.0,)},
        config=LearningConfig(update_rate=1.0, exploration_floor=0.10),
    )
    assert updated["b"] >= 0.10
    assert pytest.approx(sum(updated.values())) == 1.0


def test_calibration_recovers_null_positive_and_negative() -> None:
    policy = DecisionCalibrationPolicy(
        sesoi=0.05,
        equivalence_margin=0.025,
        max_false_promotion=0.0,
        max_false_elimination=0.0,
    )
    fixtures = (
        SyntheticCalibrationFixture(
            fixture_id="null",
            truth_direction=0,
            observed_delta=0.0,
            interval_low=-0.01,
            interval_high=0.01,
            sample_size=256,
        ),
        SyntheticCalibrationFixture(
            fixture_id="positive",
            truth_direction=1,
            observed_delta=0.12,
            interval_low=0.08,
            interval_high=0.16,
            sample_size=256,
        ),
        SyntheticCalibrationFixture(
            fixture_id="negative",
            truth_direction=-1,
            observed_delta=-0.12,
            interval_low=-0.16,
            interval_high=-0.08,
            sample_size=256,
        ),
    )
    summary = evaluate_calibration(fixtures, policy=policy)
    assert summary.false_promotions == 0
    assert summary.false_eliminations == 0
    assert summary.direction_recovery_rate == 1.0
    assert summary.equivalence_accuracy == 1.0
    assert summary.targets_met


def test_calibration_does_not_call_ambiguous_small_effect_positive() -> None:
    policy = DecisionCalibrationPolicy(sesoi=0.05, equivalence_margin=0.025)
    fixture = SyntheticCalibrationFixture(
        fixture_id="small-ambiguous",
        truth_direction=1,
        observed_delta=0.04,
        interval_low=-0.01,
        interval_high=0.09,
        sample_size=64,
    )
    summary = evaluate_calibration((fixture,), policy=policy)
    assert summary.direction_correct == 0


def test_semantic_review_queue_is_decision_weighted_and_fail_closed() -> None:
    queue = build_semantic_review_queue(
        (
            {
                "oracle_name": "Frontier Unknown",
                "frontier_occurrences": 8,
                "high_quality_cell_occurrences": 5,
                "package_completion_signal": 1.0,
                "differentiator_signal": 0.8,
                "possible_decision_impact": 1.0,
            },
            {
                "oracle_name": "Peripheral Unknown",
                "frontier_occurrences": 0,
                "high_quality_cell_occurrences": 0,
                "package_completion_signal": 0.0,
                "differentiator_signal": 0.0,
                "possible_decision_impact": 0.1,
            },
        )
    )
    assert queue[0].oracle_name == "Frontier Unknown"
    assert queue[0].priority_score > queue[1].priority_score
    assert all(row.status == "semantic_unknown_fail_closed" for row in queue)


def test_cache_identity_changes_across_evidence_partitions() -> None:
    manifest = _manifest()
    common: dict[str, Any] = {
        "manifest": manifest,
        "candidate_deck_hash": "d" * 64,
        "control_deck_hash": manifest.control_deck_hash,
        "opponent_hashes": ("opp-1", "opp-2", "opp-3"),
        "pilot_hashes": ("pilot",),
        "scenario": {"id": "scenario"},
        "exact_seed_set": (1, 2),
        "simulation_config": {"max_turns": 35},
    }
    exploratory = optimizer_cache_identity(
        **common,
        evidence_context=EvidenceContext.EXPLORATORY,
    )
    confirmatory = optimizer_cache_identity(
        **common,
        evidence_context=EvidenceContext.CONFIRMATORY,
    )
    assert exploratory != confirmatory
    assert exploratory["simulation_config"] != confirmatory["simulation_config"]


def test_cache_identity_invalidates_on_candidate_change() -> None:
    manifest = _manifest()
    kwargs: dict[str, Any] = {
        "manifest": manifest,
        "control_deck_hash": manifest.control_deck_hash,
        "opponent_hashes": ("opp-1", "opp-2", "opp-3"),
        "pilot_hashes": ("pilot",),
        "scenario": {"id": "scenario"},
        "exact_seed_set": (1, 2),
        "simulation_config": {"max_turns": 35},
        "evidence_context": EvidenceContext.EXPLORATORY,
    }
    first = optimizer_cache_identity(candidate_deck_hash="d" * 64, **kwargs)
    second = optimizer_cache_identity(candidate_deck_hash="e" * 64, **kwargs)
    assert first != second


def test_deterministic_sharding_is_stable() -> None:
    task = {"candidate": "abc", "scenario": "x", "seed": 7}
    assert deterministic_shard(task, 4) == deterministic_shard(task, 4)
    assert 0 <= deterministic_shard(task, 4) < 4


def test_optimizer_lock_blocks_duplicate_runner(tmp_path: Path) -> None:
    lock = OptimizerLock.acquire(tmp_path, manifest_hash="a" * 64)
    try:
        with pytest.raises(RuntimeError, match="duplicate optimizer runner"):
            OptimizerLock.acquire(tmp_path, manifest_hash="a" * 64)
    finally:
        lock.release()
    assert not (tmp_path / ".optimizer.lock").exists()


def test_checkpoint_resume_is_manifest_bound(tmp_path: Path) -> None:
    store = OptimizerCheckpointStore(tmp_path, manifest_hash="a" * 64)
    store.write("search", {"completed": ["one", "two"]})
    assert store.read("search") == {"completed": ["one", "two"]}
    mismatched = OptimizerCheckpointStore(tmp_path, manifest_hash="b" * 64)
    with pytest.raises(RuntimeError, match="manifest hash mismatch"):
        mismatched.read("search")


class _FakeEngine:
    def __init__(self) -> None:
        self.counter = 2

    def propose(
        self,
        mainboard: tuple[str, ...],
        neighborhood: WholeDeckNeighborhood,
        rng: Any,
    ) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
        self.counter += 1
        replacement = f"Fake Proposal {self.counter}-{neighborhood.value}"
        board = list(mainboard)
        removed = board[-1]
        board[-1] = replacement
        return tuple(board), (removed,), (replacement,)

    def evaluate_mainboard(
        self,
        mainboard: tuple[str, ...],
        *,
        seed: int | None = None,
        parent_variant_id: str | None = None,
        mutation: WholeDeckMutation | None = None,
    ) -> WholeDeckVariant:
        token = f"{self.counter:x}"[-1]
        return _variant(
            token,
            score=float(self.counter) / 10,
            parent=parent_variant_id,
            neighborhood=mutation.neighborhood if mutation else None,
        ).model_copy(update={"mainboard": mainboard, "seed": seed or 0, "mutation": mutation})


class _FakeEvaluator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def __call__(
        self,
        variant: WholeDeckVariant,
        budget: int,
        statistics_offset: int,
    ) -> ExploratoryEvaluation:
        del statistics_offset
        self.calls.append((variant.variant_id, budget))
        token = int(variant.deck_hash[0], 16)
        score = token / 20.0
        width = 1.0 / budget
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
            interval_low=score - width,
            interval_high=score + width,
            robust_lower_bound=score - width,
            qd_cell=descriptor_for_variant(variant).cell(QDConfig()),
        )


def _adaptive_run(seed: int) -> Any:
    engine = _FakeEngine()
    evaluator = _FakeEvaluator()
    search = AdaptiveWholeDeckSearch(
        {PolicyId.OWNED_POOL_NEUTRAL.value: engine},  # type: ignore[dict-item]
        evaluator=evaluator,
        seed=seed,
        qd=QDConfig(elites_per_cell=2),
        racing=RacingConfig(
            budgets=(4, 8),
            survival_fraction=0.5,
            exploration_fraction=0.5,
            minimum_survivors=1,
        ),
        learning=LearningConfig(update_rate=0.4, exploration_floor=0.05),
    )
    return search.run(
        initial_variants=(_variant("1"), _variant("2")),
        generations=2,
        proposals_per_generation=4,
    )


def test_adaptive_search_performance_feedback_changes_later_proposal_weights() -> None:
    report = _adaptive_run(101)
    assert report.feedback_changed_proposals
    assert report.unique_legal_decks > 2
    assert len(report.generations) >= 2
    assert any(
        generation.get("operator_rewards")
        for generation in report.generations[1:]
    )


def test_adaptive_search_is_same_seed_reproducible() -> None:
    first = _adaptive_run(101)
    second = _adaptive_run(101)
    assert first.archive == second.archive
    assert first.operator_weights == second.operator_weights
    assert first.policy_weights == second.policy_weights
    assert first.unique_legal_decks == second.unique_legal_decks
    assert first.requested_scenario_pairs == second.requested_scenario_pairs


def test_exploratory_evaluation_cannot_masquerade_as_confirmatory() -> None:
    variant = _variant("1")
    row = _evaluation(variant, score=0.1, low=0.05, high=0.15)
    assert row.evidence_context == EvidenceContext.EXPLORATORY
    assert row.evidence_type == "structural_model_estimates"
