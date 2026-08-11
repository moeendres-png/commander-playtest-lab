from __future__ import annotations

import json

from commander_lab.engine.structural import StructuralSimulator, commander_cast_cost
from commander_lab.models import StructuralAbortLimits, StructuralMatchConfig


def test_commander_tax_cost() -> None:
    assert commander_cast_cost(5, 0) == 5
    assert commander_cast_cost(5, 1) == 7
    assert commander_cast_cost(4, 3) == 10


def test_fixed_seed_produces_byte_identical_event_logs(tmp_path, structural_decks) -> None:
    simulator = StructuralSimulator(structural_decks)
    config = StructuralMatchConfig(
        match_id="repro-match",
        seed=42,
        deck_ids=("rogshai/current", "kaervek/current", "synthetic/aggro"),
        limits=StructuralAbortLimits(max_turns=30, max_events=20_000, max_no_progress_turns=20),
    )
    first_path = tmp_path / "first.jsonl"
    second_path = tmp_path / "second.jsonl"
    first = simulator.simulate(config, event_log_path=first_path)
    second = simulator.simulate(config, event_log_path=second_path)
    assert first_path.read_bytes() == second_path.read_bytes()
    assert first.log_sha256 == second.log_sha256
    assert first.placements == second.placements
    assert first.winner_ids == second.winner_ids


def test_different_seed_changes_log_hash(structural_decks) -> None:
    simulator = StructuralSimulator(structural_decks)
    base = dict(
        deck_ids=("rogshai/current", "kaervek/current", "synthetic/aggro"),
        limits=StructuralAbortLimits(max_turns=30, max_events=20_000, max_no_progress_turns=20),
    )
    first = simulator.simulate(StructuralMatchConfig(match_id="a", seed=1, **base))
    second = simulator.simulate(StructuralMatchConfig(match_id="b", seed=2, **base))
    assert first.log_sha256 != second.log_sha256


def test_goldfish_is_labelled_structural_estimate(structural_decks) -> None:
    result = StructuralSimulator(structural_decks).simulate(
        StructuralMatchConfig(
            match_id="goldfish",
            seed=9,
            deck_ids=("rogshai/current",),
            limits=StructuralAbortLimits(max_turns=30, max_events=20_000, max_no_progress_turns=20),
        )
    )
    assert result.estimate_type == "structural_model_estimates"
    assert result.completed
    assert result.winner_ids == ("p1",)
    assert result.end_reason == "goldfish_lethal"


def test_every_started_turn_has_summary(tmp_path, structural_decks) -> None:
    path = tmp_path / "events.jsonl"
    result = StructuralSimulator(structural_decks).simulate(
        StructuralMatchConfig(
            match_id="turn-log",
            seed=100,
            deck_ids=("rogshai/current", "kaervek/current", "synthetic/control"),
            limits=StructuralAbortLimits(max_turns=30, max_events=20_000, max_no_progress_turns=20),
        ),
        event_log_path=path,
    )
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    starts = [event for event in events if event["event_type"] == "turn_started"]
    summaries = [event for event in events if event["event_type"] == "turn_summary"]
    assert result.completed
    assert len(starts) == len(summaries)
    assert len(starts) > 0


def test_abort_limit_is_reported(structural_decks) -> None:
    result = StructuralSimulator(structural_decks).simulate(
        StructuralMatchConfig(
            match_id="abort",
            seed=55,
            deck_ids=("synthetic/control", "synthetic/control"),
            limits=StructuralAbortLimits(max_turns=1, max_events=20_000, max_no_progress_turns=20),
        )
    )
    assert result.aborted
    assert result.abort_reason == "max_turns"
    assert result.end_reason == "aborted_max_turns"
