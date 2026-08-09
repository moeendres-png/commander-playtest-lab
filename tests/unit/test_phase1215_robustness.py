from __future__ import annotations

from pathlib import Path

from commander_lab.robustness import (
    PILOT_PROFILES,
    POLITICS_REGIMES,
    build_registry,
    run_policy_tournament,
)


def test_required_synthetic_profiles_and_politics_exist(repo_root: Path) -> None:
    registry = build_registry(repo_root)
    assert len(PILOT_PROFILES) == 16
    assert len(POLITICS_REGIMES) == 10
    assert {x["pilot_id"] for x in registry["pilot_profiles"]} == set(PILOT_PROFILES)
    assert all(not x["hidden_information_access"] for x in registry["pilot_profiles"])
    assert all(
        x["scenario_axis_only"] and not x["predicted_truth"] for x in registry["politics_regimes"]
    )
    assert all(not x["assumed_cards_confirmed"] for x in registry["opponent_variants"])


def test_policy_tournament_is_deterministic_and_structural(repo_root: Path) -> None:
    registry = build_registry(repo_root)
    a = run_policy_tournament(registry["opponent_variants"])
    b = run_policy_tournament(registry["opponent_variants"])
    assert a == b
    assert a["validation_level"] == "structural_only"
    assert a["hidden_information_access"] is False
    assert a["empirical_weights_used"] is False
    assert {x["pilot"] for x in a["rankings"]} == set(PILOT_PROFILES)
    assert {row["pod_size"] for row in a["scenario_rows"]} == {3, 4, 5}


def test_structural_policy_mapping_uses_real_pilot_weights_and_truth_boundary(
    repo_root: Path,
) -> None:
    from commander_lab.robustness import pilot_config_for

    aggressive = pilot_config_for("aggressive", "rational_threat_focus")
    conservative = pilot_config_for("conservative", "rational_threat_focus")
    assert aggressive.weights is not None and conservative.weights is not None
    assert aggressive.weights.win_progress > conservative.weights.win_progress
    assert aggressive.weights.political_visibility > conservative.weights.political_visibility
    assert aggressive.information_policy.hidden_opponent_hands is False
    assert aggressive.information_policy.random_library_order is False
    assert aggressive.information_policy.exact_future_draws is False


def test_current_uncertainty_registry_preserves_known_unknown_counts(repo_root: Path) -> None:
    registry = build_registry(repo_root)
    by_deck = {}
    for row in registry["opponent_variants"]:
        by_deck.setdefault(row["deck_id"], row)
    assert by_deck["opponent/cosmic-spiderman-midbudget"]["confirmed_card_count"] == 4
    assert by_deck["opponent/cosmic-spiderman-midbudget"]["unknown_slot_count"] == 96
    assert by_deck["opponent/morcant-elves"]["confirmed_card_count"] == 54
    assert by_deck["opponent/morcant-elves"]["unknown_slot_count"] == 0
    doom = by_deck["opponent/doom-prevails-precon"]
    assert doom["baseline_precon_cards"] == 100
    assert doom["upgrade_slots_unknown"] is True
    assert (
        len(
            [
                r
                for r in registry["opponent_variants"]
                if r["deck_id"] == "opponent/doom-prevails-precon"
            ]
        )
        == 3
    )


def test_structural_policy_tournament_executes_real_simulator(repo_root: Path) -> None:
    from commander_lab.robustness import PolicyTournamentConfig, run_structural_policy_tournament

    result = run_structural_policy_tournament(
        repo_root,
        config=PolicyTournamentConfig(
            pod_sizes=(3,), iterations_per_scenario=1, max_turns=10, rounds=2
        ),
        deck_ids=("korvold/current",),
        pilot_profiles=("weak", "strong"),
        politics_regimes=("rational_threat_focus",),
    )
    assert result["execution_status"] == "passed"
    assert result["self_play_status"] == "structural_policy_tournament_executed"
    assert result["game_count"] == 2
    assert result["scenario_count"] == 1
    assert result["common_random_numbers"] is True
    assert result["unknown_cards_invented"] is False
    assert {row["pilot"] for row in result["rows"]} == {"weak", "strong"}
    assert len({row["match_seed"] for row in result["rows"]}) == 1


def test_structural_policy_tournament_is_worker_independent(repo_root: Path) -> None:
    from commander_lab.robustness import PolicyTournamentConfig, run_structural_policy_tournament

    kwargs = {
        "root": repo_root,
        "deck_ids": ("korvold/current",),
        "pilot_profiles": ("weak", "strong"),
        "politics_regimes": ("rational_threat_focus", "combo_prevention"),
    }
    one = run_structural_policy_tournament(
        config=PolicyTournamentConfig(
            seed=99, rounds=2, pod_sizes=(3,), iterations_per_scenario=1, max_turns=8, workers=1
        ),
        **kwargs,
    )
    two = run_structural_policy_tournament(
        config=PolicyTournamentConfig(
            seed=99, rounds=2, pod_sizes=(3,), iterations_per_scenario=1, max_turns=8, workers=2
        ),
        **kwargs,
    )
    assert one["rows"] == two["rows"]
    assert one["rankings"] == two["rankings"]
    assert one["regret_minimization"] == two["regret_minimization"]


def test_structural_self_play_uses_same_profile_on_all_seats(repo_root: Path) -> None:
    from commander_lab.robustness import run_structural_self_play

    result = run_structural_self_play(
        repo_root,
        deck_ids=("korvold/current",),
        pilot_profiles=("weak", "strong"),
        pod_sizes=(3,),
        max_turns=8,
        seed=1234,
    )
    assert result["execution_status"] == "passed"
    assert result["self_play_status"] == "structural_same_policy_all_seats_executed"
    assert result["game_count"] == 2
    assert all(row["all_seats_same_policy_profile"] for row in result["rows"])
    assert len({row["match_seed"] for row in result["rows"]}) == 1
    assert result["unknown_cards_invented"] is False
