from __future__ import annotations

from commander_lab.engine.structural import StructuralSimulator, aggregate_structural_results
from commander_lab.engine.structural.telemetry import (
    T1TelemetryAccumulator,
    classify_payment_blocker,
)
from commander_lab.models import (
    CardRole,
    Color,
    StructuralAbortLimits,
    StructuralCardProfile,
    StructuralMatchConfig,
)


def _spell(*, mana_value: float, colors: dict[Color, int]) -> StructuralCardProfile:
    return StructuralCardProfile(
        oracle_name="Telemetry Test Spell",
        mana_value=mana_value,
        roles=frozenset({CardRole.DRAW}),
        color_requirements=colors,
        is_permanent=False,
    )


def test_t1_payment_blockers_are_state_derived() -> None:
    card = _spell(mana_value=2.0, colors={Color.BLUE: 1})
    assert (
        classify_payment_blocker(
            mana_available=1.0,
            available_colors={Color.BLUE},
            card=card,
        )
        == "insufficient_total_mana"
    )
    assert (
        classify_payment_blocker(
            mana_available=2.0,
            available_colors={Color.RED},
            card=card,
        )
        == "missing_color"
    )
    assert (
        classify_payment_blocker(
            mana_available=2.0,
            available_colors={Color.BLUE},
            card=card,
        )
        is None
    )


def test_partner_recast_opportunities_are_evaluated_separately_before_pooling() -> None:
    accumulator = T1TelemetryAccumulator()
    accumulator.record_recast("Commander A", affordable=True)
    accumulator.record_recast("Commander B", affordable=False)
    accumulator.record_recast("Commander A", affordable=True)
    assert accumulator.commander_recast_opportunities == {"Commander A": 2, "Commander B": 1}
    assert accumulator.commander_recast_affordable == {"Commander A": 2}
    assert accumulator.recast_affordability() == 2 / 3


def test_t1_match_metrics_are_measured_without_event_stream_side_effects(
    tmp_path, structural_decks
) -> None:
    config = StructuralMatchConfig(
        match_id="t1-telemetry",
        seed=20260822,
        deck_ids=("rogshai/current", "kaervek/current", "synthetic/aggro"),
        limits=StructuralAbortLimits(max_turns=30, max_events=20_000, max_no_progress_turns=20),
    )
    simulator = StructuralSimulator(structural_decks)
    first_path = tmp_path / "first.jsonl"
    second_path = tmp_path / "second.jsonl"
    first = simulator.simulate(config, event_log_path=first_path)
    second = simulator.simulate(config, event_log_path=second_path)

    assert first_path.read_bytes() == second_path.read_bytes()
    assert first.placements == second.placements
    assert first.winner_ids == second.winner_ids
    assert first.event_count == second.event_count
    assert first.log_sha256 == second.log_sha256
    for metrics in first.player_metrics.values():
        assert metrics.fidelity_telemetry_status == "PARTIAL"
        assert metrics.unused_mana is not None
        assert metrics.colored_mana_failures is not None
        assert metrics.stranded_spells is not None
        assert metrics.stranded_reasons is not None


def test_t1_aggregate_reports_coverage_without_changing_existing_metrics(structural_decks) -> None:
    result = StructuralSimulator(structural_decks).simulate(
        StructuralMatchConfig(
            match_id="t1-aggregate",
            seed=1138,
            deck_ids=("rogshai/current", "kaervek/current", "synthetic/control"),
            limits=StructuralAbortLimits(max_turns=30, max_events=20_000, max_no_progress_turns=20),
        )
    )
    measured = aggregate_structural_results([result])
    telemetry = measured["fidelity_telemetry"]
    assert isinstance(telemetry, dict)
    assert telemetry["schema_version"] == "t1-partial-v1"
    all_players = telemetry["all_players"]
    assert isinstance(all_players, dict)
    assert all_players["unused_mana"]["n"] == len(result.player_metrics)  # type: ignore[index]
    assert all_players["unused_mana"]["measured_count"] == len(result.player_metrics)  # type: ignore[index]

    stripped_metrics = {
        player_id: metrics.model_copy(
            update={
                "unused_mana": None,
                "colored_mana_failures": None,
                "stranded_spells": None,
                "stranded_reasons": None,
                "commander_recast_affordability": None,
                "fidelity_telemetry_status": "NOT_MEASURED",
            }
        )
        for player_id, metrics in result.player_metrics.items()
    }
    unmeasured = aggregate_structural_results(
        [result.model_copy(update={"player_metrics": stripped_metrics})]
    )
    for key in (
        "estimate_type",
        "games",
        "completed_games",
        "aborted_games",
        "average_turns",
        "deck_metrics",
        "pilot_metrics",
    ):
        assert measured[key] == unmeasured[key]
