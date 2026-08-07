from __future__ import annotations
import json
from pathlib import Path
from commander_lab.robustness import PILOT_PROFILES, POLITICS_REGIMES, build_registry, run_policy_tournament


def test_required_synthetic_profiles_and_politics_exist(repo_root: Path) -> None:
    registry=build_registry(repo_root)
    assert len(PILOT_PROFILES) == 16
    assert len(POLITICS_REGIMES) == 10
    assert {x['pilot_id'] for x in registry['pilot_profiles']} == set(PILOT_PROFILES)
    assert all(not x['hidden_information_access'] for x in registry['pilot_profiles'])
    assert all(x['scenario_axis_only'] and not x['predicted_truth'] for x in registry['politics_regimes'])
    assert all(not x['assumed_cards_confirmed'] for x in registry['opponent_variants'])


def test_policy_tournament_is_deterministic_and_structural(repo_root: Path) -> None:
    registry=build_registry(repo_root)
    a=run_policy_tournament(registry['opponent_variants'])
    b=run_policy_tournament(registry['opponent_variants'])
    assert a == b
    assert a['validation_level'] == 'structural_only'
    assert a['hidden_information_access'] is False
    assert a['empirical_weights_used'] is False
    assert {x['pilot'] for x in a['rankings']} == set(PILOT_PROFILES)
    assert {row['pod_size'] for row in a['scenario_rows']} == {3,4,5}
