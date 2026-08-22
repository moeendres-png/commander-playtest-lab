from __future__ import annotations

from commander_lab.engine.structural import StructuralSimulator
from commander_lab.engine.structural.simulator import _Player
from commander_lab.engine.structural.telemetry import T1TelemetryAccumulator
from commander_lab.models import (
    StructuralAbortLimits,
    StructuralMatchConfig,
    StructuralPlayerMetrics,
)


class _TelemetryDiscardingSimulator(StructuralSimulator):
    """Control path with identical Structural execution but no retained T1 observations."""

    def _telemetry_for(self, player: _Player) -> T1TelemetryAccumulator:
        return T1TelemetryAccumulator()

    def _attach_t1_metrics(self, metrics: StructuralPlayerMetrics) -> StructuralPlayerMetrics:
        return metrics


def test_optimizer_v2_t1_telemetry_is_execution_and_scoring_inert(structural_decks) -> None:
    config = StructuralMatchConfig(
        match_id="optimizer-t1-noninterference",
        seed=2026082201,
        deck_ids=("rogshai/current", "kaervek/current", "synthetic/control", "synthetic/aggro"),
        limits=StructuralAbortLimits(max_turns=30, max_events=20_000, max_no_progress_turns=30),
    )
    measured = StructuralSimulator(structural_decks).simulate(config, run_id="balanced-t1-proof")
    control = _TelemetryDiscardingSimulator(structural_decks).simulate(
        config, run_id="balanced-t1-proof"
    )

    assert measured.placements == control.placements
    assert measured.winner_ids == control.winner_ids
    assert measured.turns == control.turns
    assert measured.completed == control.completed
    assert measured.aborted == control.aborted
    assert measured.abort_reason == control.abort_reason
    assert measured.end_reason == control.end_reason
    assert measured.event_count == control.event_count
    assert measured.log_sha256 == control.log_sha256

    for player_id, measured_metrics in measured.player_metrics.items():
        control_metrics = control.player_metrics[player_id]
        measured_payload = measured_metrics.model_dump(mode="json")
        control_payload = control_metrics.model_dump(mode="json")
        for field in (
            "unused_mana",
            "colored_mana_failures",
            "stranded_spells",
            "stranded_reasons",
            "commander_recast_affordability",
            "fidelity_telemetry_status",
        ):
            measured_payload.pop(field)
            control_payload.pop(field)
        assert measured_payload == control_payload
