from __future__ import annotations

import itertools

from commander_lab.repositories.opponents import CurrentOpponentRepository
from commander_lab.whole_deck.scenarios import BalancedPodScenarioScheduler


def _scheduler(repo_root):
    repository = CurrentOpponentRepository(repo_root)
    return repository, BalancedPodScenarioScheduler(
        repository.records(), opponent_registry_hash=repository.registry_hash
    )


def test_full_cycle_covers_all_triplets_and_balances_exposure_and_own_seats(repo_root) -> None:
    repository, scheduler = _scheduler(repo_root)
    scenarios = scheduler.schedule(scheduler.combinations_per_cycle, seed=2026081401)
    report = scheduler.coverage_report(scenarios)

    assert len(repository.current_deck_ids()) == 8
    assert scheduler.combinations_per_cycle == 56
    assert len(scenarios) == 56
    assert len({tuple(sorted(row.opponent_deck_ids)) for row in scenarios}) == 56
    assert all(len(set(row.opponent_deck_ids)) == 3 for row in scenarios)
    assert all(len(row.opponent_seat_assignment) == 3 for row in scenarios)
    assert all(
        row.own_seat not in {seat for seat, _ in row.opponent_seat_assignment} for row in scenarios
    )
    assert set(report["games_per_opponent"].values()) == {21}
    assert report["rogshai_seat_counts"] == {"1": 14, "2": 14, "3": 14, "4": 14}
    assert report["complete_coverage_cycles"] == 1
    assert report["incomplete_remainder_games"] == 0
    assert report["opponent_exposure_imbalance"] == 0
    assert (
        report["frequency_interpretation"] == "experimental_equal_coverage_not_real_meta_frequency"
    )

    expected_pairs = set(itertools.combinations(sorted(repository.current_deck_ids()), 2))
    observed_pairs = {tuple(key.split("|", 1)) for key in report["games_per_opponent_pair"]}
    assert observed_pairs == expected_pairs


def test_partial_cycle_is_deterministic_balanced_and_has_no_duplicate_triplet(repo_root) -> None:
    _, scheduler = _scheduler(repo_root)
    first = scheduler.schedule(17, seed=77)
    second = scheduler.schedule(17, seed=77)
    different = scheduler.schedule(17, seed=78)
    report = scheduler.coverage_report(first)

    assert first == second
    assert first != different
    assert len({row.scenario_id for row in first}) == 17
    assert len({tuple(sorted(row.opponent_deck_ids)) for row in first}) == 17
    assert report["opponent_exposure_imbalance"] <= 1
    assert (
        max(report["rogshai_seat_counts"].values()) - min(report["rogshai_seat_counts"].values())
        <= 1
    )
    assert all(row.opponent_registry_hash == scheduler.registry_hash for row in first)


def test_second_cycle_preserves_full_coverage_with_new_scenarios(repo_root) -> None:
    _, scheduler = _scheduler(repo_root)
    rows = scheduler.schedule(2 * scheduler.combinations_per_cycle, seed=2026081402)
    report = scheduler.coverage_report(rows)

    assert len(rows) == 112
    assert report["complete_coverage_cycles"] == 2
    assert report["incomplete_remainder_games"] == 0
    assert set(report["games_per_opponent"].values()) == {42}
    assert set(report["games_per_opponent_triple"].values()) == {2}
    assert len({row.seed for row in rows}) == len(rows)
