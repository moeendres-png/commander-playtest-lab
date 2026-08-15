from __future__ import annotations

from pathlib import Path

import pytest

from commander_lab.whole_deck.lab import WholeDeckDesignLab
from commander_lab.whole_deck.models import PolicyId
from commander_lab.whole_deck.optimizer_v2 import EvidenceContext
from commander_lab.whole_deck.optimizer_v2_evaluator import CachedPartitionEvaluator
from commander_lab.whole_deck.optimizer_v2_release import (
    build_release_manifest_from_project,
    run_release_holdout,
)
from commander_lab.whole_deck.optimizer_v2_release_models import FrontierHandoff
from commander_lab.whole_deck.orchestrator import WholeDeckCampaignOrchestrator
from commander_lab.whole_deck.search import current_control_mainboard
from commander_lab.whole_deck.search_models import WholeDeckHardGate, WholeDeckVariant


@pytest.fixture(scope="module")
def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def release_manifest(project_root: Path):
    return build_release_manifest_from_project(
        project_root,
        run_id="optimizer-v2-release-tests",
        search_seed=2026081511,
        exploratory_games=8,
        calibration_games=8,
        confirmatory_games=8,
        holdout_games=8,
    )


def _control_variant(root: Path) -> WholeDeckVariant:
    lab = WholeDeckDesignLab(root)
    mainboard = current_control_mainboard(root)
    profile = lab.context.materialize(mainboard, label="optimizer-v2-test-control")
    land_count = sum(lab.context.cards[name].profile.is_land for name in mainboard)
    return WholeDeckVariant(
        variant_id=f"whole-deck/{profile.deck_hash}",
        deck_hash=profile.deck_hash,
        mainboard=mainboard,
        policy_id=PolicyId.OWNED_POOL_NEUTRAL,
        policy_version="release-test",
        seed=1,
        feature_vector={
            "land_count": land_count,
            "average_nonland_mv": 2.5,
            "role_strengths": {},
            "package_counts": {},
        },
        mana={"land_count": land_count},
        objective_prior=0.0,
        meta_distance={},
        hard_gate=WholeDeckHardGate(
            valid=True,
            card_count=100,
            land_count=land_count,
            basic_count=sum(name in {"Plains", "Island", "Mountain"} for name in mainboard),
        ),
        provenance={"release_test": True},
    )


def _evaluator(
    root: Path,
    manifest,
    directory: Path,
    *,
    workers: int,
    mulligan: bool,
) -> CachedPartitionEvaluator:
    lab = WholeDeckDesignLab(root)
    return CachedPartitionEvaluator(
        root=root,
        manifest=manifest,
        orchestrator=WholeDeckCampaignOrchestrator(root),
        control_mainboard=current_control_mainboard(root),
        context=lab.context,
        evidence_context=EvidenceContext.EXPLORATORY,
        run_directory=directory,
        workers=workers,
        max_turns=12,
        enable_mulligan_sensitivity=mulligan,
    )


def test_release_manifest_has_four_disjoint_partitions(release_manifest) -> None:
    identities = {
        release_manifest.exploratory.identity,
        release_manifest.calibration_partition.identity,
        release_manifest.confirmatory.identity,
        release_manifest.sealed_holdout.identity,
    }
    assert len(identities) == 4
    seed_sets = (
        set(release_manifest.exploratory.scenario_seeds),
        set(release_manifest.calibration_partition.scenario_seeds),
        set(release_manifest.confirmatory.scenario_seeds),
        set(release_manifest.sealed_holdout.scenario_seeds),
    )
    for index, left in enumerate(seed_sets):
        for right in seed_sets[index + 1 :]:
            assert not left & right


def test_candidate_mulligan_sensitivity_executes_real_policies(
    project_root: Path, release_manifest, tmp_path: Path
) -> None:
    evaluator = _evaluator(
        project_root, release_manifest, tmp_path / "mulligan", workers=1, mulligan=True
    )
    candidate = evaluator.context.materialize(
        current_control_mainboard(project_root), label="mulligan-release-test"
    )
    payload = evaluator._mulligan_sensitivity(candidate, 32)
    assert payload["status"] == "executed"
    assert payload["samples_per_policy"] == 32
    policies = payload["policies"]
    assert isinstance(policies, dict)
    assert set(policies) == {"current_pilot", "conservative", "interaction_oriented"}
    assert payload["outcome_dependent_policy_selection"] is False


def test_exact_cache_miss_store_hit_and_fresh_equivalence(
    project_root: Path, release_manifest, tmp_path: Path
) -> None:
    variant = _control_variant(project_root)
    evaluator = _evaluator(
        project_root, release_manifest, tmp_path / "cache", workers=1, mulligan=False
    )
    fresh = evaluator(variant, 2, 0)
    second = evaluator(variant, 2, 999)
    audit = evaluator.audit()
    assert audit.cache_misses == 1
    assert audit.cache_stores == 1
    assert audit.cache_hits == 1
    assert audit.executed_scenario_pairs == 2
    assert audit.requested_scenario_pairs == 4
    assert fresh.model_dump(mode="json") == second.model_dump(mode="json")


def test_worker_count_one_and_two_are_result_equivalent(
    project_root: Path, release_manifest, tmp_path: Path
) -> None:
    variant = _control_variant(project_root)
    one = _evaluator(
        project_root, release_manifest, tmp_path / "worker-one", workers=1, mulligan=False
    )(variant, 2, 0)
    two = _evaluator(
        project_root, release_manifest, tmp_path / "worker-two", workers=2, mulligan=False
    )(variant, 2, 0)
    assert one.score == two.score
    assert one.interval_low == two.interval_low
    assert one.interval_high == two.interval_high
    assert one.robust_lower_bound == two.robust_lower_bound


def test_shard_plan_covers_every_requested_scenario(
    project_root: Path, release_manifest, tmp_path: Path
) -> None:
    variant = _control_variant(project_root)
    evaluator = _evaluator(
        project_root, release_manifest, tmp_path / "shards", workers=2, mulligan=False
    )
    evaluator(variant, 4, 0)
    audit = evaluator.audit()
    assert sum(audit.shard_counts.values()) == 4
    assert set(audit.shard_counts) <= {"0", "1"}


def test_frontier_handoff_hash_detects_payload_change() -> None:
    first = FrontierHandoff.create(
        manifest_hash="a" * 64,
        elites=({"deck_hash": "b" * 64, "variant": {"mainboard": ["Island"]}},),
    )
    second = FrontierHandoff.create(
        manifest_hash="a" * 64,
        elites=({"deck_hash": "c" * 64, "variant": {"mainboard": ["Island"]}},),
    )
    assert first.frontier_hash != second.frontier_hash
    assert first.holdout_used is False


def test_holdout_refuses_without_explicit_authorization(
    project_root: Path, release_manifest, tmp_path: Path
) -> None:
    with pytest.raises(RuntimeError, match="explicit --authorize-holdout"):
        run_release_holdout(
            project_root,
            release_manifest,
            confirmatory_path=tmp_path / "unused.json",
            run_directory=tmp_path,
            authorize_holdout=False,
        )


def test_evaluator_classifies_exploratory_evidence_only(
    project_root: Path, release_manifest, tmp_path: Path
) -> None:
    variant = _control_variant(project_root)
    evaluation = _evaluator(
        project_root, release_manifest, tmp_path / "classification", workers=1, mulligan=False
    )(variant, 1, 0)
    assert evaluation.evidence_context == EvidenceContext.EXPLORATORY
    assert evaluation.evidence_type == "structural_model_estimates"
