from __future__ import annotations

import json

from commander_lab.engine.structural import StructuralSimulator
from commander_lab.models import (
    PilotConfig,
    PilotDecisionMode,
    PilotStrength,
    StructuralAbortLimits,
    StructuralMatchConfig,
)


def test_auto_specialist_pilots_are_logged(tmp_path, structural_decks) -> None:
    path = tmp_path / "pilot-events.jsonl"
    result = StructuralSimulator(structural_decks).simulate(
        StructuralMatchConfig(
            match_id="pilot-log",
            seed=404,
            deck_ids=("korvold/current", "rogshai/current", "synthetic/control"),
            limits=StructuralAbortLimits(max_turns=25, max_events=30_000, max_no_progress_turns=20),
        ),
        event_log_path=path,
    )
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    decisions = [event for event in events if event["event_type"] == "pilot_decision"]
    mulligans = [event for event in events if event["event_type"] == "london_mulligan"]
    assert decisions
    assert mulligans
    assert {event["payload"]["pilot_name"] for event in mulligans} >= {
        "KorvoldPilot",
        "RogShaiPilot",
    }
    assert result.player_metrics["p1"].pilot_name == "KorvoldPilot"
    assert result.player_metrics["p2"].pilot_name == "RogShaiPilot"
    assert all("breakdown" in event["payload"] for event in decisions)


def test_seeded_stochastic_pilots_replay_identically(tmp_path, structural_decks) -> None:
    configs = (
        PilotConfig(
            strength=PilotStrength.STRONG,
            mode=PilotDecisionMode.STOCHASTIC,
            mistake_rate=0.0,
        ),
        PilotConfig(
            strength=PilotStrength.AVERAGE,
            mode=PilotDecisionMode.STOCHASTIC,
            mistake_rate=0.0,
        ),
        PilotConfig(
            strength=PilotStrength.WEAK,
            mode=PilotDecisionMode.STOCHASTIC,
            mistake_rate=0.1,
        ),
    )
    config = StructuralMatchConfig(
        match_id="stochastic-replay",
        seed=505,
        deck_ids=("korvold/current", "rogshai/current", "synthetic/aggro"),
        pilot_configs=configs,
        limits=StructuralAbortLimits(max_turns=25, max_events=30_000, max_no_progress_turns=20),
    )
    first_path = tmp_path / "first.jsonl"
    second_path = tmp_path / "second.jsonl"
    simulator = StructuralSimulator(structural_decks)
    first = simulator.simulate(config, event_log_path=first_path)
    second = simulator.simulate(config, event_log_path=second_path)
    assert first_path.read_bytes() == second_path.read_bytes()
    assert first.log_sha256 == second.log_sha256


def test_stochastic_pilot_batch_is_worker_count_independent(structural_decks) -> None:
    from commander_lab.engine.structural import run_structural_batch  # noqa: PLC0415
    from commander_lab.models import StructuralBatchConfig  # noqa: PLC0415

    pilot_configs = (
        PilotConfig(
            strength=PilotStrength.STRONG,
            mode=PilotDecisionMode.STOCHASTIC,
            mistake_rate=0.0,
        ),
        PilotConfig(
            strength=PilotStrength.AVERAGE,
            mode=PilotDecisionMode.STOCHASTIC,
            mistake_rate=0.0,
        ),
        PilotConfig(
            strength=PilotStrength.WEAK,
            mode=PilotDecisionMode.STOCHASTIC,
            mistake_rate=0.1,
        ),
    )
    common = dict(
        run_id="pilot-worker-repro",
        seed=606,
        iterations=8,
        deck_ids=("korvold/current", "rogshai/current", "synthetic/aggro"),
        pilot_configs=pilot_configs,
        limits=StructuralAbortLimits(max_turns=25, max_events=30_000, max_no_progress_turns=20),
    )
    serial = run_structural_batch(StructuralBatchConfig(**common, workers=1), structural_decks)
    parallel = run_structural_batch(StructuralBatchConfig(**common, workers=2), structural_decks)
    serial_key = [
        (result.seed, result.placements, result.log_sha256, result.turns)
        for result in serial.match_results
    ]
    parallel_key = [
        (result.seed, result.placements, result.log_sha256, result.turns)
        for result in parallel.match_results
    ]
    assert serial_key == parallel_key
    assert serial.aggregate == parallel.aggregate
