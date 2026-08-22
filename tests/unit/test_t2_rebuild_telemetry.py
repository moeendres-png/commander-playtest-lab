from __future__ import annotations

from commander_lab.engine.structural import StructuralSimulator, aggregate_structural_results
from commander_lab.engine.structural.telemetry import T1TelemetryAccumulator
from commander_lab.models import StructuralAbortLimits, StructuralMatchConfig


def test_t2_commander_removal_recovery_is_exact_and_turn_based() -> None:
    telemetry = T1TelemetryAccumulator()
    assert telemetry.record_disruption(
        "commander_removal", turn=3, commander_name="Commander A"
    )
    telemetry.observe_recovery(
        turn=4,
        commander_names_on_battlefield=set(),
        board_power=0.0,
        engine_value=0.0,
    )
    assert telemetry.rebuild_mean_turns() is None
    assert len(telemetry.open_rebuild_episodes) == 1

    telemetry.observe_recovery(
        turn=5,
        commander_names_on_battlefield={"Commander A"},
        board_power=0.0,
        engine_value=0.0,
    )
    assert telemetry.rebuild_mean_turns() == 2.0
    assert telemetry.rebuild_completed_counts == {"commander_removal": 1}
    assert not telemetry.open_rebuild_episodes


def test_t2_engine_and_board_recovery_use_exact_pre_disruption_state() -> None:
    telemetry = T1TelemetryAccumulator()
    assert telemetry.record_disruption(
        "engine_loss", turn=4, baseline_engine_value=2.0
    )
    assert telemetry.record_disruption(
        "board_wipe",
        turn=4,
        baseline_board_power=6.0,
        baseline_engine_value=3.0,
    )
    telemetry.observe_recovery(
        turn=5,
        commander_names_on_battlefield=set(),
        board_power=5.9,
        engine_value=1.99,
    )
    assert telemetry.rebuild_mean_turns() is None
    assert len(telemetry.open_rebuild_episodes) == 2

    telemetry.observe_recovery(
        turn=6,
        commander_names_on_battlefield=set(),
        board_power=6.0,
        engine_value=2.0,
    )
    assert telemetry.rebuild_mean_turns() == 2.0
    assert telemetry.rebuild_completed_counts == {"board_wipe": 1, "engine_loss": 1}


def test_t2_duplicate_open_disruption_is_not_double_counted() -> None:
    telemetry = T1TelemetryAccumulator()
    assert telemetry.record_disruption(
        "engine_loss", turn=2, baseline_engine_value=3.0
    )
    assert not telemetry.record_disruption(
        "engine_loss", turn=3, baseline_engine_value=4.0
    )
    assert telemetry.rebuild_disruption_counts == {"engine_loss": 1}
    assert len(telemetry.open_rebuild_episodes) == 1


def test_t2_unresolved_episode_is_censored_not_zero() -> None:
    telemetry = T1TelemetryAccumulator()
    telemetry.record_disruption("board_wipe", turn=3, baseline_board_power=4.0)
    telemetry.observe_recovery(
        turn=7,
        commander_names_on_battlefield=set(),
        board_power=3.5,
        engine_value=0.0,
    )
    assert telemetry.rebuild_mean_turns() is None
    assert telemetry.rebuild_open_counts() == {"board_wipe": 1}


def test_t2_unsupported_metrics_remain_not_measured_and_aggregate_coverage_is_explicit(
    structural_decks,
) -> None:
    result = StructuralSimulator(structural_decks).simulate(
        StructuralMatchConfig(
            match_id="t2-coverage",
            seed=2026082202,
            deck_ids=(
                "rogshai/current",
                "kaervek/current",
                "synthetic/control",
                "synthetic/aggro",
            ),
            limits=StructuralAbortLimits(
                max_turns=12,
                max_events=20_000,
                max_no_progress_turns=12,
            ),
        ),
        run_id="balanced-t2-coverage",
    )
    for metrics in result.player_metrics.values():
        assert metrics.mana_source_usage is None
        assert metrics.dead_card_rate is None

    aggregate = aggregate_structural_results([result])
    telemetry = aggregate["fidelity_telemetry"]
    assert isinstance(telemetry, dict)
    all_players = telemetry["all_players"]
    assert isinstance(all_players, dict)
    assert all_players["mana_source_usage"] == {
        "n": 4,
        "measured_count": 0,
        "not_measured_count": 4,
    }
    assert all_players["dead_card_rate"]["measured_count"] == 0
    assert all_players["dead_card_rate"]["not_measured_count"] == 4


def test_t2_same_seed_is_deterministic_for_rebuild_telemetry(structural_decks) -> None:
    config = StructuralMatchConfig(
        match_id="t2-determinism",
        seed=2026082203,
        deck_ids=(
            "rogshai/current",
            "kaervek/current",
            "synthetic/control",
            "synthetic/aggro",
        ),
        limits=StructuralAbortLimits(max_turns=20, max_events=20_000, max_no_progress_turns=20),
    )
    first = StructuralSimulator(structural_decks).simulate(config, run_id="balanced-t2-proof")
    second = StructuralSimulator(structural_decks).simulate(config, run_id="balanced-t2-proof")
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
