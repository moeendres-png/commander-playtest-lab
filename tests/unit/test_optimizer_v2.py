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


def _partition(name: str, context: EvidenceContext, seed: int, offset: int) -> EvidencePartition:
    return EvidencePartition.create(
        partition_id=name,
        evidence_context=context,
        master_seed=seed,
        scenario_ids=tuple(f"scenario-{offset + index}" for index in range(8)),
        scenario_seeds=tuple(seed + index for index in range(8)),
    )


def _manifest() -> OptimizerManifest:
    return OptimizerManifest(
        run_id="test-v2",
        software_commit="a" * 40,
        software_tree="b" * 40,
        package_version="1.20.4",
        engine_version="structural-0.6.0",
        physical_pool_identity="pool",
        control_deck_hash="c" * 64,
        opponent_data_identity="opponents",
        knowledge_identity="knowledge",
        pilot_policy_identity="pilots",
        mulligan_policy_identity="mulligans",
        construction_prior_identity="priors",
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
    parent: str | None = None,
    neighborhood: WholeDeckNeighborhood | None = None,
) -> WholeDeckVariant:
    nonlands = 98 - lands
    spells = tuple(f"Shared {index}" for index in range(max(0, nonlands - 1)))
    mainboard = tuple("Island" for _ in range(lands)) + spells + (f"Unique {token}",)
    mutation = None
    if neighborhood is not None:
        mutation = WholeDeckMutation(
            neighborhood=neighborhood,
            removed=("Shared 0",),
            added=(f"Unique {token}",),
            changed_slots=1,
            accepted=True,
            objective_delta=score,
        )
    return WholeDeckVariant(
        variant_id=f"whole-deck/{token * 64}",
        deck_hash=token * 64,
        mainboard=mainboard,
        policy_id=PolicyId.OWNED_POOL_NEUTRAL,
        policy_version="test",
        seed=1,
        parent_variant_id=parent,
        mutation=mutation,
        feature_vector={
            "land_count": lands,
            "average_nonland_mv": average_mv,
            "role_strengths": {
                "counter": interaction / 2,
                "removal": interaction / 2,
                "protection": 5.0,
                "ramp": 6.0,
                "selection": 7.0,
                "draw": 5.0,
                "finisher": 4.0,
            },
            "package_counts": {"pkg": 3},
            "semantic_support_fraction": 1.0,
            "multiplayer_leverage": {"table": 0.5},
        },
        mana={"land_count": lands},
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
    score: float,
    low: float,
    high: float,
    novelty: float = 0.0,
) -> ExploratoryEvaluation:
    return ExploratoryEvaluation(
        candidate_id=variant.variant_id,
        deck_hash=variant.deck_hash,
        generation=0,
        parent_candidate_id=variant.parent_variant_id,
        operator="fixture",
        policy_id=variant.policy_id.value,
        budget=8,
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
        manifest.exploratory, manifest.confirmatory, manifest.sealed_holdout
    )


def test_seed_and_scenario_leakage_fail_closed() -> None:
    exploratory = _partition("exploratory", EvidenceContext.EXPLORATORY, 100, 0)
    seed_leak = EvidencePartition.create(
        partition_id="confirmatory",
        evidence_context=EvidenceContext.CONFIRMATORY,
        master_seed=200,
        scenario_ids=tuple(f"confirm-{index}" for index in range(8)),
        scenario_seeds=exploratory.scenario_seeds,
    )
    with pytest.raises(ValueError, match="seed leakage"):
        assert_partition_disjointness(exploratory, seed_leak)
    scenario_leak = EvidencePartition.create(
        partition_id="confirmatory",
        evidence_context=EvidenceContext.CONFIRMATORY,
        master_seed=200,
        scenario_ids=exploratory.scenario_ids,
        scenario_seeds=tuple(500 + index for index in range(8)),
    )
    with pytest.raises(ValueError, match="scenario leakage"):
        assert_partition_disjointness(exploratory, scenario_leak)


def test_qd_archive_preserves_distinct_strong_architectures() -> None:
    archive = QualityDiversityArchive(QDConfig(elites_per_cell=1))
    first = _variant("1", lands=32, average_mv=2.0, interaction=8.0)
    second = _variant("2", lands=40, average_mv=3.2, interaction=20.0)
    assert archive.admit(first, _evaluation(first, 0.1, 0.05, 0.15))
    assert archive.admit(second, _evaluation(second, 0.1, 0.05, 0.15))
    assert archive.coverage()["occupied_cells"] == 2


def test_invalid_candidate_never_enters_archive() -> None:
    archive = QualityDiversityArchive(QDConfig())
    invalid = _variant("1", valid=False)
    assert not archive.admit(invalid, _evaluation(invalid, 1.0, 0.9, 1.1))


def test_deck_distance_handles_basic_multiplicity_and_architecture() -> None:
    base = _variant("1", lands=36)
    near = _variant("2", lands=37)
    far = _variant("3", lands=44, average_mv=3.8, interaction=28.0)
    assert 0.0 <= deck_distance(base, near).card_multiset <= 1.0
    assert deck_distance(base, far).total > deck_distance(base, near).total


def test_novelty_rewards_distant_candidate() -> None:
    base = _variant("1")
    near = _variant("2", lands=37)
    far = _variant("3", lands=44, average_mv=4.0, interaction=30.0)
    assert novelty_score(far, (base, near), neighbors=2) > novelty_score(
        near, (base,), neighbors=1
    )


def test_racing_keeps_novelty_exploration_slot() -> None:
    config = RacingConfig(
        budgets=(8, 16),
        survival_fraction=0.5,
        exploration_fraction=0.5,
        minimum_survivors=2,
    )
    variants = [_variant(str(index)) for index in range(1, 5)]
    rows = [
        _evaluation(variants[0], 0.35, 0.30, 0.40, 0.1),
        _evaluation(variants[1], 0.25, 0.20, 0.30, 0.1),
        _evaluation(variants[2], -0.35, -0.40, -0.30, 1.0),
        _evaluation(variants[3], -0.25, -0.30, -0.20, 0.2),
    ]
    survivors = select_racing_survivors(rows, config=config)
    assert rows[0].candidate_id in survivors
    assert rows[2].candidate_id in survivors


def test_learning_updates_weights_and_preserves_floor() -> None:
    operators = operator_names()
    initial = normalize_learning_weights({name: 1.0 for name in operators}, floor=0.05)
    updated = update_learning_weights(
        initial,
        {operators[0]: (0.8,), operators[1]: (-0.8,)},
        config=LearningConfig(update_rate=0.4, exploration_floor=0.05),
    )
    assert updated[operators[0]] > initial[operators[0]]
    assert updated[operators[1]] < initial[operators[1]]
    floor_case = update_learning_weights(
        {"a": 0.99, "b": 0.01},
        {"a": (1.0,), "b": (-1.0,)},
        config=LearningConfig(update_rate=1.0, exploration_floor=0.10),
    )
    assert floor_case["b"] >= 0.10
    assert pytest.approx(sum(floor_case.values())) == 1.0


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
    assert summary.targets_met
    assert summary.direction_recovery_rate == 1.0
    assert summary.equivalence_accuracy == 1.0


def test_semantic_review_queue_is_ranked_and_fail_closed() -> None:
    queue = build_semantic_review_queue(
        (
            {
                "oracle_name": "Frontier",
                "frontier_occurrences": 8,
                "high_quality_cell_occurrences": 5,
                "package_completion_signal": 1.0,
                "differentiator_signal": 0.8,
                "possible_decision_impact": 1.0,
            },
            {"oracle_name": "Peripheral", "possible_decision_impact": 0.1},
        )
    )
    assert queue[0].oracle_name == "Frontier"
    assert queue[0].priority_score > queue[1].priority_score
    assert all(row.status == "semantic_unknown_fail_closed" for row in queue)


def _cache_identity(candidate: str, context: EvidenceContext) -> dict[str, Any]:
    manifest = _manifest()
    return optimizer_cache_identity(
        manifest=manifest,
        candidate_deck_hash=candidate,
        control_deck_hash=manifest.control_deck_hash,
        opponent_hashes=("o1", "o2", "o3"),
        pilot_hashes=("pilot",),
        scenario={"id": "scenario"},
        exact_seed_set=(1, 2),
        simulation_config={"max_turns": 35},
        evidence_context=context,
    )


def test_cache_identity_separates_partitions_and_candidates() -> None:
    assert _cache_identity("d" * 64, EvidenceContext.EXPLORATORY) != _cache_identity(
        "d" * 64, EvidenceContext.CONFIRMATORY
    )
    assert _cache_identity("d" * 64, EvidenceContext.EXPLORATORY) != _cache_identity(
        "e" * 64, EvidenceContext.EXPLORATORY
    )


def test_deterministic_sharding_is_stable() -> None:
    task = {"candidate": "abc", "scenario": "x", "seed": 7}
    assert deterministic_shard(task, 4) == deterministic_shard(task, 4)
    assert 0 <= deterministic_shard(task, 4) < 4


def test_duplicate_lock_is_blocked(tmp_path: Path) -> None:
    lock = OptimizerLock.acquire(tmp_path, manifest_hash="a" * 64)
    try:
        with pytest.raises(RuntimeError, match="duplicate optimizer runner"):
            OptimizerLock.acquire(tmp_path, manifest_hash="a" * 64)
    finally:
        lock.release()


def test_checkpoint_resume_is_manifest_bound(tmp_path: Path) -> None:
    store = OptimizerCheckpointStore(tmp_path, manifest_hash="a" * 64)
    store.write("search", {"completed": ["one"]})
    assert store.read("search") == {"completed": ["one"]}
    with pytest.raises(RuntimeError, match="manifest hash mismatch"):
        OptimizerCheckpointStore(tmp_path, manifest_hash="b" * 64).read("search")


class _FakeEngine:
    def __init__(self) -> None:
        self.counter = 2

    def propose(
        self,
        mainboard: tuple[str, ...],
        neighborhood: WholeDeckNeighborhood,
        rng: Any,
    ) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
        del rng
        self.counter += 1
        board = list(mainboard)
        removed = board[-1]
        added = f"Proposal {self.counter}-{neighborhood.value}"
        board[-1] = added
        return tuple(board), (removed,), (added,)

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
            score=self.counter / 10,
            parent=parent_variant_id,
            neighborhood=mutation.neighborhood if mutation else None,
        ).model_copy(update={"mainboard": mainboard, "seed": seed or 0, "mutation": mutation})


class _FakeEvaluator:
    def __call__(
        self,
        variant: WholeDeckVariant,
        budget: int,
        statistics_offset: int,
    ) -> ExploratoryEvaluation:
        del statistics_offset
        score = int(variant.deck_hash[0], 16) / 20.0
        width = 1.0 / budget
        return ExploratoryEvaluation(
            candidate_id=variant.variant_id,
            deck_hash=variant.deck_hash,
            generation=0,
            parent_candidate_id=variant.parent_variant_id,
            operator=variant.mutation.neighborhood.value if variant.mutation else "prior",
            policy_id=variant.policy_id.value,
            budget=budget,
            score=score,
            interval_low=score - width,
            interval_high=score + width,
            robust_lower_bound=score - width,
            qd_cell=descriptor_for_variant(variant).cell(QDConfig()),
        )


def _adaptive_run(seed: int) -> Any:
    search = AdaptiveWholeDeckSearch(
        {PolicyId.OWNED_POOL_NEUTRAL.value: _FakeEngine()},  # type: ignore[dict-item]
        evaluator=_FakeEvaluator(),
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


def test_adaptive_feedback_changes_later_proposal_weights() -> None:
    report = _adaptive_run(101)
    assert report.feedback_changed_proposals
    assert report.unique_legal_decks > 2
    assert any(generation.get("operator_rewards") for generation in report.generations[1:])


def test_adaptive_search_is_same_seed_reproducible() -> None:
    first = _adaptive_run(101)
    second = _adaptive_run(101)
    assert first.archive == second.archive
    assert first.operator_weights == second.operator_weights
    assert first.policy_weights == second.policy_weights
    assert first.requested_scenario_pairs == second.requested_scenario_pairs


def test_exploratory_evidence_cannot_masquerade_as_confirmatory() -> None:
    row = _evaluation(_variant("1"), 0.1, 0.05, 0.15)
    assert row.evidence_context == EvidenceContext.EXPLORATORY
    assert row.evidence_type == "structural_model_estimates"
