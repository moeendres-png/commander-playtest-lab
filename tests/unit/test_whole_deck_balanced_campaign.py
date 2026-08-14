from __future__ import annotations

from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength
from commander_lab.repositories.opponents import CurrentOpponentRepository
from commander_lab.tools.service import CommanderToolService
from commander_lab.whole_deck.campaign import run_balanced_paired_campaign
from commander_lab.whole_deck.scenarios import BalancedPodScenarioScheduler


def test_balanced_campaign_keeps_candidates_in_separate_matches(repo_root) -> None:
    service = CommanderToolService(repo_root)
    baseline = service._deck("rogshai/current")
    variant = baseline.model_copy(
        update={
            "deck_id": "synthetic/whole-deck/test-variant",
            "deck_hash": "test-variant-hash",
        }
    )
    opponents = CurrentOpponentRepository(repo_root)
    scheduler = BalancedPodScenarioScheduler(
        opponents.records(), opponent_registry_hash=opponents.registry_hash
    )
    scenarios = scheduler.schedule(2, seed=991)
    result = run_balanced_paired_campaign(
        baseline=baseline,
        variant=variant,
        opponent_profiles=opponents.profiles(),
        scenarios=scenarios,
        pilot_config=PilotConfig(
            strength=PilotStrength.STRONG,
            mode=PilotDecisionMode.DETERMINISTIC,
        ),
        max_turns=2,
        statistics_seed=992,
    )

    assert result["evidence_class"] == "structural_model_estimates"
    assert result["pairing_conditions"] == {
        "candidates_share_match": False,
        "same_scenarios": True,
        "same_match_seeds": True,
        "same_own_seats": True,
        "same_opponent_seat_assignments": True,
        "same_pilot_configuration": True,
        "same_turn_cap": True,
        "common_random_numbers": True,
    }
    rows = result["paired_observations"]
    assert len(rows) == 2
    assert all(row["candidate_isolation"] is True for row in rows)
    assert [row["seed"] for row in rows] == [scenario.seed for scenario in scenarios]
    assert [row["own_seat"] for row in rows] == [scenario.own_seat for scenario in scenarios]
    assert result["baseline"]["games"] == 2
    assert result["variant"]["games"] == 2


def test_balanced_campaign_is_worker_count_reproducible(repo_root) -> None:
    service = CommanderToolService(repo_root)
    baseline = service._deck("rogshai/current")
    variant = baseline.model_copy(
        update={
            "deck_id": "synthetic/whole-deck/worker-variant",
            "deck_hash": "worker-variant-hash",
        }
    )
    opponents = CurrentOpponentRepository(repo_root)
    scheduler = BalancedPodScenarioScheduler(
        opponents.records(), opponent_registry_hash=opponents.registry_hash
    )
    scenarios = scheduler.schedule(4, seed=1991)
    kwargs = dict(
        baseline=baseline,
        variant=variant,
        opponent_profiles=opponents.profiles(),
        scenarios=scenarios,
        pilot_config=PilotConfig(
            strength=PilotStrength.STRONG,
            mode=PilotDecisionMode.DETERMINISTIC,
        ),
        max_turns=2,
        statistics_seed=1992,
    )
    serial = run_balanced_paired_campaign(**kwargs, workers=1)
    parallel = run_balanced_paired_campaign(**kwargs, workers=2)

    assert serial["paired_observations"] == parallel["paired_observations"]
    assert serial["paired"] == parallel["paired"]
    assert serial["baseline"] == parallel["baseline"]
    assert serial["variant"] == parallel["variant"]
