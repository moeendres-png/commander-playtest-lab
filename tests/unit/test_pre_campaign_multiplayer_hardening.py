from __future__ import annotations

import random

from commander_lab.models import CardRole
from commander_lab.pod_scheduling_5p import BalancedFivePlayerSensitivityScheduler
from commander_lab.repositories.opponents import CurrentOpponentRepository
from commander_lab.tools import CommanderToolService
from commander_lab.whole_deck.discoverability import build_discoverability_report
from commander_lab.whole_deck.knowledge_quality import build_knowledge_quality_report
from commander_lab.whole_deck.models import PolicyId
from commander_lab.whole_deck.multiplayer import (
    card_multiplayer_leverage,
    deck_multiplayer_leverage,
    multiplayer_pod_response,
)
from commander_lab.whole_deck.orchestrator import (
    FivePlayerSensitivitySpecification,
    WholeDeckCampaignOrchestrator,
)
from commander_lab.whole_deck.policies import get_policy
from commander_lab.whole_deck.readiness import build_campaign_readiness
from commander_lab.whole_deck.search import WholeDeckSearchContext, WholeDeckSearchEngine
from commander_lab.whole_deck.search_context import SearchCard
from commander_lab.whole_deck.search_models import (
    WholeDeckNeighborhood,
    WholeDeckSearchConfig,
)
from tests.unit.whole_deck_context_fixture import synthetic_context
from tests.unit.whole_deck_profile_fixtures import card, profile


def test_five_player_full_cycle_balances_opponents_and_own_seats(repo_root) -> None:
    repository = CurrentOpponentRepository(repo_root)
    scheduler = BalancedFivePlayerSensitivityScheduler(
        repository.records(), opponent_registry_hash=repository.registry_hash
    )
    rows = scheduler.schedule(scheduler.combinations_per_cycle, seed=2026081451)
    report = scheduler.coverage_report(rows)

    assert len(repository.current_deck_ids()) == 14
    assert scheduler.combinations_per_cycle == 1001
    assert len(rows) == 1001
    assert len({tuple(sorted(row.opponent_deck_ids)) for row in rows}) == 1001
    assert all(len(set(row.opponent_deck_ids)) == 4 for row in rows)
    assert set(report["games_per_opponent"].values()) == {286}
    assert report["rogshai_seat_counts"] == {
        "1": 200,
        "2": 200,
        "3": 200,
        "4": 200,
        "5": 201,
    }
    assert report["complete_coverage_cycles"] == 1
    assert report["opponent_exposure_imbalance"] == 0
    assert report["primary_evidence"] is False
    assert (
        report["frequency_interpretation"] == "experimental_equal_coverage_not_real_meta_frequency"
    )


def test_five_player_partial_cycle_is_deterministic_and_balanced(repo_root) -> None:
    repository = CurrentOpponentRepository(repo_root)
    scheduler = BalancedFivePlayerSensitivityScheduler(
        repository.records(), opponent_registry_hash=repository.registry_hash
    )
    first = scheduler.schedule(17, seed=77)
    second = scheduler.schedule(17, seed=77)
    different = scheduler.schedule(17, seed=78)
    report = scheduler.coverage_report(first)
    assert first == second
    assert first != different
    assert report["opponent_exposure_imbalance"] <= 1
    seats = report["rogshai_seat_counts"]
    assert max(seats.values()) - min(seats.values()) <= 1


def test_five_player_sensitivity_is_separate_paired_axis(repo_root) -> None:
    service = CommanderToolService(repo_root)
    baseline = service._deck("rogshai/current")
    variant = baseline.model_copy(
        update={"deck_id": "synthetic/five-player/same-list", "deck_hash": "same-list-5p"}
    )
    result = WholeDeckCampaignOrchestrator(repo_root).run_five_player_sensitivity_pair(
        baseline=baseline,
        variant=variant,
        specification=FivePlayerSensitivitySpecification(
            games=2,
            seed=2026081452,
            max_turns=1,
        ),
    )

    assert result["evidence_axis"] == "five_player_sensitivity"
    assert result["primary_evidence"] is False
    assert result["pod_size"] == 5
    campaign = result["campaign"]
    assert campaign["pod_size"] == 5
    assert campaign["pairing_conditions"]["candidates_share_match"] is False
    assert campaign["pairing_conditions"]["same_scenarios"] is True
    assert campaign["pairing_conditions"]["common_random_numbers"] is True
    assert all(len(row["opponent_deck_ids"]) == 4 for row in campaign["paired_observations"])


def test_multiplayer_response_is_delta_of_separate_paired_effects() -> None:
    four = {
        "paired_observations": [
            {"baseline_placement": 3.0, "variant_placement": 2.8},
            {"baseline_placement": 3.0, "variant_placement": 2.8},
            {"baseline_placement": 3.0, "variant_placement": 2.8},
        ]
    }
    five = {
        "paired_observations": [
            {"baseline_placement": 4.0, "variant_placement": 3.3},
            {"baseline_placement": 4.0, "variant_placement": 3.3},
            {"baseline_placement": 4.0, "variant_placement": 3.3},
        ]
    }
    response = multiplayer_pod_response(four, five, seed=9)
    assert response["candidate_vs_control_effect_5p"] > response["candidate_vs_control_effect_4p"]
    assert response["pod_size_response"] > 0
    assert response["classification"] == "STRUCTURALLY_BETTER_WITH_LARGER_POD"
    assert response["evidence_class"] == "structural_model_estimates"


def test_unknown_multiplayer_dimensions_remain_unknown_not_zero(repo_root) -> None:
    context = WholeDeckSearchContext.from_project(repo_root)
    unknown = next(card for card in context.cards.values() if not card.semantic_known)
    row = card_multiplayer_leverage(unknown)
    assert row["multiplayer_scaling"] is None
    assert row["floor_value"] is None
    assert row["setup_dependency"] is None
    assert row["semantic_known"] is False
    assert "UNKNOWN" in row["unknown_interpretation"]


def test_multiplayer_leverage_is_multidimensional_without_scalar_power_score() -> None:
    context, baseline = synthetic_context()
    report = deck_multiplayer_leverage(context, baseline)
    assert report["scalar_power_score"] is None
    dimensions = report["dimensions"]
    assert set(
        (
            "multiplayer_scaling",
            "mana_efficiency",
            "role_compression",
            "floor_value",
            "immediate_impact",
            "turn_cycle_risk",
            "setup_dependency",
            "commander_independence",
            "repeatability",
            "semantic_confidence",
        )
    ) <= set(dimensions)


def test_discoverability_report_surfaces_every_unseen_candidate() -> None:
    context, baseline = synthetic_context()
    engine = WholeDeckSearchEngine(
        context,
        get_policy(PolicyId.OWNED_POOL_NEUTRAL),
        config=WholeDeckSearchConfig(
            seed=41,
            diversified_starts=0,
            max_steps_per_start=1,
            finalist_limit=1,
            archive_limit=32,
        ),
    )
    result = engine.run(current_control=baseline)
    report = build_discoverability_report(context, (result,))

    assert report["candidate_search_exploration_recall"] < 1.0
    assert report["candidate_visibility_recall"] == 1.0
    assert report["unseen_candidate_count"] == len(report["discovery_review_queue"])
    assert report["candidate_discoverability_status"] == (
        "PASS_WITH_EXPLICIT_DISCOVERY_REVIEW_QUEUE"
    )
    assert all(
        row["automatic_negative_evidence"] is False for row in report["discovery_review_queue"]
    )


def test_seeded_package_exploration_does_not_starve_smaller_viable_package() -> None:
    base_context, baseline = synthetic_context()
    extra: list[SearchCard] = []
    for package_id, count in (("alpha-large", 8), ("zeta-small", 6)):
        for index in range(count):
            name = f"{package_id}-{index}"
            extra.append(
                card(
                    name,
                    profile=profile(
                        name,
                        mv=2.0,
                        roles=frozenset({CardRole.ENGINE}),
                        package_ids=frozenset({package_id}),
                    ),
                    utility=1.0,
                )
            )
    context = WholeDeckSearchContext.synthetic(tuple(base_context.cards.values()) + tuple(extra))
    engine = WholeDeckSearchEngine(
        context,
        get_policy(PolicyId.OWNED_POOL_NEUTRAL),
        config=WholeDeckSearchConfig(
            seed=5,
            diversified_starts=0,
            max_steps_per_start=1,
            minimum_neighborhood_changes=6,
            maximum_neighborhood_changes=8,
            finalist_limit=1,
            archive_limit=64,
        ),
    )
    seen_packages: set[str] = set()
    for seed in range(50):
        _, _, additions = engine.propose(
            baseline, WholeDeckNeighborhood.ENGINE_PACKAGE, random.Random(seed)
        )
        if additions and additions[0].startswith("alpha-large"):
            seen_packages.add("alpha-large")
        if additions and additions[0].startswith("zeta-small"):
            seen_packages.add("zeta-small")
    assert seen_packages == {"alpha-large", "zeta-small"}


def test_unknown_cause_audit_reconciles_current_unknowns(repo_root) -> None:
    report = build_knowledge_quality_report(repo_root)
    assert sum(report["semantic_unknown_cause_counts"].values()) == report["semantic_unknown_count"]
    assert report["semantic_recoverable_parser_gap_count"] == 0
    assert report["semantic_unknown_count"] > 0


def test_campaign_readiness_includes_separate_five_player_sensitivity(repo_root) -> None:
    gates = {
        "ci_status": "PASS",
        "security_status": "PASS",
        "windows_status": "PASS",
        "j_p6_status": "PASS",
        "j_final_status": "PASS",
        "release_status": "PASS",
    }
    report = build_campaign_readiness(repo_root, external_gates=gates, smoke_status="PASS")
    assert report["primary_pod_scheduler_status"] == "PASS"
    assert report["five_player_sensitivity_status"] == "PASS"
    assert report["five_player_full_cycle_combinations"] == 1001
    assert report["five_player_full_cycle_coverage"]["primary_evidence"] is False
    assert report["ready_for_official_campaign"] is True


def test_public_whole_deck_run_can_add_five_player_sensitivity(repo_root) -> None:
    from commander_lab.models.whole_deck_tooling import (
        WholeDeckDecisionPrepareInput,
        WholeDeckDecisionRunInput,
    )

    service = CommanderToolService(repo_root)
    prepared = service.deck_decision_prepare(
        WholeDeckDecisionPrepareInput(
            design_mode="whole_deck",
            whole_deck_policies=("OWNED_POOL_NEUTRAL",),
            whole_deck_diversified_starts=0,
            whole_deck_steps_per_start=1,
            whole_deck_finalists_per_policy=1,
            whole_deck_max_variants=1,
            design_seed=2026081453,
            whole_deck_output_name="test-multiplayer-hardening-design.json",
        )
    )
    assert prepared.status.value == "completed"
    discoverability = prepared.result["discoverability"]
    assert discoverability["candidate_visibility_recall"] == 1.0
    variant_id = prepared.result["variants"][0]["variant_id"]
    run = service.deck_decision_run(
        WholeDeckDecisionRunInput(
            comparison_mode="whole_deck",
            prepared_design_path=prepared.result["prepared_design_path"],
            whole_deck_variant_id=variant_id,
            iterations=1,
            whole_deck_five_player_sensitivity_iterations=1,
            seed=2026081454,
            max_turns=1,
        )
    )
    assert run.status.value == "completed"
    assert run.result["campaign_orchestration"]["campaign_specification"]["pod_size"] == 4
    assert run.result["five_player_sensitivity"]["pod_size"] == 5
    assert run.result["five_player_sensitivity"]["primary_evidence"] is False
    assert run.result["multiplayer_response"]["evidence_class"] == "structural_model_estimates"
    assert run.result["evidence_boundaries"]["five_player_sensitivity_is_primary_evidence"] is False
