from __future__ import annotations

from dataclasses import replace
from statistics import median

import pytest

from commander_lab.models import (
    CardRole,
    DataQuality,
    PilotConfig,
    PilotDecisionMode,
    PilotStrength,
    StructuralCardProfile,
    StructuralDeckProfile,
)
from commander_lab.pod_scheduling import BalancedPodScenarioScheduler
from commander_lab.pod_scheduling_5p import BalancedFivePlayerSensitivityScheduler
from commander_lab.repositories.opponents import CurrentOpponentRepository
from commander_lab.whole_deck.campaign import run_balanced_paired_campaign
from commander_lab.whole_deck.discoverability import build_forced_inclusion_feasibility_report
from commander_lab.whole_deck.knowledge_quality import build_knowledge_quality_report
from commander_lab.whole_deck.models import PolicyId
from commander_lab.whole_deck.multiplayer import multiplayer_damage_attribution
from commander_lab.whole_deck.policies import get_policy
from commander_lab.whole_deck.search import WholeDeckSearchEngine
from commander_lab.whole_deck.search_models import WholeDeckSearchConfig
from tests.unit.whole_deck_context_fixture import synthetic_context


def _search_engine(context, *, seed: int = 7) -> WholeDeckSearchEngine:
    return WholeDeckSearchEngine(
        context,
        get_policy(PolicyId.OWNED_POOL_NEUTRAL),
        config=WholeDeckSearchConfig(
            seed=seed,
            diversified_starts=1,
            max_steps_per_start=1,
            finalist_limit=1,
            archive_limit=32,
        ),
    )


def test_verified_empty_rules_text_is_complete_fact_not_missing_oracle(repo_root) -> None:
    report = build_knowledge_quality_report(repo_root)
    expected = {
        "Armored Cancrix",
        "Balduvian Barbarians",
        "Bonebreaker Giant",
        "Canyon Minotaur",
        "Coral Eel",
        "Coral Merfolk",
        "Glory Seeker",
        "Goblin Piker",
        "Goblin Roughrider",
        "Hill Giant",
        "Jhessian Lookout",
        "Maritime Guard",
        "Ogre Resister",
        "Phyrexian Hulk",
        "Savannah Lions",
        "Scoria Elemental",
        "Siege Mastodon",
        "Stonework Puma",
    }
    assert set(report["verified_empty_rules_text_cards"]) == expected
    assert report["verified_empty_rules_text_count"] == 18
    assert report["candidate_fact_coverage_count"] == report["candidate_universe_count"] == 795
    assert report["truly_missing_fact_count"] == 0
    assert report["rules_text_nonempty_count"] == 777
    assert report["semantic_unknown_cause_counts"]["known_no_functional_rules_role"] == 18
    assert report["semantic_unknown_cause_counts"].get("oracle_facts_missing", 0) == 0


def test_unknown_search_prior_uses_separate_neutral_land_and_nonland_medians() -> None:
    context, _ = synthetic_context()
    unknown_land_name = "Dual Land 1"
    unknown_nonland_name = "Filler 1"
    for name in (unknown_land_name, unknown_nonland_name):
        context.cards[name] = replace(
            context.cards[name], semantic_known=False, semantic_evidence="fixture_unknown"
        )
    engine = _search_engine(context)
    known_land = [
        engine._utility[name]
        for name, card in context.cards.items()
        if name != unknown_land_name and card.semantic_known and card.profile.is_land
    ]
    known_nonland = [
        engine._utility[name]
        for name, card in context.cards.items()
        if name != unknown_nonland_name and card.semantic_known and not card.profile.is_land
    ]
    assert engine._utility[unknown_land_name] == pytest.approx(median(known_land))
    assert engine._utility[unknown_nonland_name] == pytest.approx(median(known_nonland))


def test_diversified_constructive_starts_can_select_semantic_unknown() -> None:
    context, _ = synthetic_context()
    target = "Filler 1"
    context.cards[target] = replace(
        context.cards[target], semantic_known=False, semantic_evidence="fixture_unknown"
    )
    found = False
    for seed in range(80):
        engine = _search_engine(context, seed=seed)
        import random

        start = engine.constructive_start(rng=random.Random(seed), diversified=True)
        if target in start:
            found = True
            break
    assert found


def test_forced_inclusion_probe_is_feasibility_only() -> None:
    context, _ = synthetic_context()
    report = build_forced_inclusion_feasibility_report(context, ("Filler 1",), seed=99)
    assert report["probe_type"] == "forced_inclusion_hard_gate_feasibility_not_performance"
    row = report["rows"][0]
    assert row["feasible"] is True
    assert row["automatic_positive_evidence"] is False
    assert row["automatic_negative_evidence"] is False


def _synthetic_finisher_deck(
    deck_id: str, *, multiplayer_scaling: float, strength: float
) -> StructuralDeckProfile:
    quality = DataQuality.SYNTHETIC_ASSUMPTION
    commander = StructuralCardProfile(
        oracle_name=f"{deck_id}-commander",
        mana_value=0.0,
        roles=frozenset({CardRole.ENABLER}),
        role_strengths={CardRole.ENABLER: 1.0},
        color_identity=frozenset(),
        produces_colors=frozenset(),
        is_land=False,
        is_permanent=True,
        commander_synergy=0.0,
        floor_value=0.5,
        immediate_impact=0.5,
        turn_cycle_risk=0.5,
        multiplayer_scaling=0.0,
        source_quality=quality,
    )
    cards = [commander]
    for index in range(99):
        cards.append(
            StructuralCardProfile(
                oracle_name=f"{deck_id}-finisher-{index:02d}",
                mana_value=0.0,
                roles=frozenset({CardRole.FINISHER}),
                role_strengths={CardRole.FINISHER: strength},
                color_identity=frozenset(),
                produces_colors=frozenset(),
                is_land=False,
                is_permanent=False,
                commander_synergy=0.0,
                floor_value=1.0,
                immediate_impact=1.0,
                turn_cycle_risk=0.0,
                multiplayer_scaling=multiplayer_scaling,
                source_quality=quality,
            )
        )
    return StructuralDeckProfile(
        deck_id=deck_id,
        deck_hash=(deck_id.encode().hex() + "0" * 64)[:64],
        commander_names=(commander.oracle_name,),
        cards=tuple(cards),
        commander_base_costs={commander.oracle_name: 0.0},
        commander_base_power={commander.oracle_name: 0.0},
        commander_strategy="generic",
        data_snapshot_hash="synthetic-pre-campaign-closure",
    )


def _paired_4p_5p(repo_root, baseline: StructuralDeckProfile, variant: StructuralDeckProfile):
    opponents = CurrentOpponentRepository(repo_root)
    four_scheduler = BalancedPodScenarioScheduler(
        opponents.records(), opponent_registry_hash=opponents.registry_hash
    )
    five_scheduler = BalancedFivePlayerSensitivityScheduler(
        opponents.records(), opponent_registry_hash=opponents.registry_hash
    )
    pilot = PilotConfig(strength=PilotStrength.STRONG, mode=PilotDecisionMode.DETERMINISTIC)
    common = dict(
        baseline=baseline,
        variant=variant,
        opponent_profiles=opponents.profiles(),
        pilot_config=pilot,
        max_turns=3,
        workers=1,
    )
    four = run_balanced_paired_campaign(
        **common,
        scenarios=four_scheduler.schedule(2, seed=2026081501),
        statistics_seed=2026081503,
    )
    five = run_balanced_paired_campaign(
        **common,
        scenarios=five_scheduler.schedule(2, seed=2026081502),
        statistics_seed=2026081504,
    )
    return four, five


def test_real_structural_pipeline_distinguishes_opponent_count_scaling_from_control(
    repo_root,
) -> None:
    baseline = _synthetic_finisher_deck("fixture-baseline", multiplayer_scaling=0.0, strength=0.4)
    scaling = _synthetic_finisher_deck("fixture-scaling", multiplayer_scaling=2.0, strength=0.4)
    non_scaling = _synthetic_finisher_deck(
        "fixture-nonscaling", multiplayer_scaling=0.0, strength=0.8
    )

    scaling_4p, scaling_5p = _paired_4p_5p(repo_root, baseline, scaling)
    control_4p, control_5p = _paired_4p_5p(repo_root, baseline, non_scaling)
    scaling_response = multiplayer_damage_attribution(scaling_4p, scaling_5p)
    control_response = multiplayer_damage_attribution(control_4p, control_5p)

    assert scaling_response["candidate_vs_control_effect_4p"] > 0.0
    assert (
        scaling_response["candidate_vs_control_effect_5p"]
        > scaling_response["candidate_vs_control_effect_4p"]
    )
    assert scaling_response["pod_size_response"] > 0.0
    assert control_response["pod_size_response"] == pytest.approx(0.0, abs=1e-9)
    assert scaling_4p["pairing_conditions"]["candidates_share_match"] is False
    assert scaling_5p["pairing_conditions"]["candidates_share_match"] is False
    assert scaling_4p["pairing_conditions"]["common_random_numbers"] is True
    assert scaling_5p["pairing_conditions"]["common_random_numbers"] is True


def test_controlled_multiplayer_ablation_removes_specific_5p_uplift(repo_root) -> None:
    baseline = _synthetic_finisher_deck("ablation-baseline", multiplayer_scaling=0.0, strength=0.4)
    full = _synthetic_finisher_deck("ablation-full", multiplayer_scaling=2.0, strength=0.4)
    ablated = _synthetic_finisher_deck("ablation-removed", multiplayer_scaling=0.0, strength=0.4)

    full_4p, full_5p = _paired_4p_5p(repo_root, baseline, full)
    ablated_4p, ablated_5p = _paired_4p_5p(repo_root, baseline, ablated)
    full_response = multiplayer_damage_attribution(full_4p, full_5p)
    ablated_response = multiplayer_damage_attribution(ablated_4p, ablated_5p)

    assert full_response["pod_size_response"] > 0.0
    assert ablated_response["pod_size_response"] == pytest.approx(0.0, abs=1e-9)
    assert full_response["pod_size_response"] > ablated_response["pod_size_response"]
    assert full_response["evidence_class"] == "structural_model_estimates"
    assert full_response["causal_claim"] is False
