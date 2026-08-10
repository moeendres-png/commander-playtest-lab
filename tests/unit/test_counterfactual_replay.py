from __future__ import annotations

import json
from pathlib import Path

import pytest

from commander_lab.counterfactual import CounterfactualError, CounterfactualReplayLab
from commander_lab.models import CounterfactualEngineMode, HiddenInformationPolicy, SeedPolicy


def _write_replay(root: Path, *, eliminated: bool = False) -> str:
    target = root / "data/runs/counterfactual/source/events/example.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "event_type": "game_started",
            "game_id": "g1",
            "sequence": 0,
            "actor_id": None,
            "payload": {"seed": 17},
        },
        {
            "event_type": "state_checkpoint",
            "game_id": "g1",
            "sequence": 1,
            "actor_id": None,
            "payload": {"reason": "before_decision", "players": [{"player_id": "p1", "life": 40}]},
        },
    ]
    if eliminated:
        rows.append(
            {
                "event_type": "player_eliminated",
                "game_id": "g1",
                "sequence": 2,
                "actor_id": "p1",
                "payload": {},
            }
        )
    rows.append(
        {
            "event_type": "pilot_decision",
            "game_id": "g1",
            "sequence": len(rows),
            "actor_id": "p1",
            "payload": {
                "phase": "counter",
                "selected_action_id": "counter:Kaervek",
                "selected_utility": 2.0,
                "candidates": [["counter:Kaervek", 2.0], ["pass", 3.5], ["counter:Value", 1.0]],
            },
        }
    )
    target.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8"
    )
    return str(target.relative_to(root))


def test_find_and_run_public_counterfactual(tmp_path: Path) -> None:
    source = _write_replay(tmp_path)
    lab = CounterfactualReplayLab(tmp_path)
    branch = lab.find_branchpoints(source)[0]
    result = lab.run(branch, alternative_action="pass", future_samples=1)
    assert result.mean_improvement > 1.5
    assert result.state_diff.interaction_reserve_delta > 0
    assert result.state_diff.hand_delta > 0
    assert result.historical_fact is False
    assert result.external_engine_used is False
    assert (
        result.branchpoint.hidden_information_policy
        == HiddenInformationPolicy.PUBLIC_INFORMATION_ONLY
    )


def test_invalid_offset_and_state_hash_are_rejected(tmp_path: Path) -> None:
    source = _write_replay(tmp_path)
    lab = CounterfactualReplayLab(tmp_path)
    with pytest.raises(CounterfactualError, match="invalid event offset"):
        lab.branchpoint_at(source, 99)
    branch = lab.find_branchpoints(source)[0]
    with pytest.raises(CounterfactualError, match="state hash mismatch"):
        lab.run(branch, alternative_action="pass", expected_state_hash="0" * 64)


def test_illegal_alternative_and_eliminated_player_are_rejected(tmp_path: Path) -> None:
    source = _write_replay(tmp_path)
    lab = CounterfactualReplayLab(tmp_path)
    branch = lab.find_branchpoints(source)[0]
    with pytest.raises(CounterfactualError, match="not legal"):
        lab.run(branch, alternative_action="invented_action")
    eliminated_source = _write_replay(tmp_path / "lost", eliminated=True)
    lost = CounterfactualReplayLab(tmp_path / "lost").find_branchpoints(eliminated_source)[0]
    with pytest.raises(CounterfactualError, match="eliminated player"):
        CounterfactualReplayLab(tmp_path / "lost").run(lost, alternative_action="pass")


def test_replay_drift_is_detected(tmp_path: Path) -> None:
    source = _write_replay(tmp_path)
    lab = CounterfactualReplayLab(tmp_path)
    branch = lab.find_branchpoints(source)[0]
    path = tmp_path / source
    path.write_text(
        path.read_text(encoding="utf-8").replace('"life": 40', '"life": 39'), encoding="utf-8"
    )
    with pytest.raises(CounterfactualError, match="replay drift"):
        lab.verify_branchpoint(branch)


def test_identical_seed_and_worker_count_are_deterministic(tmp_path: Path) -> None:
    source = _write_replay(tmp_path)
    lab = CounterfactualReplayLab(tmp_path)
    branch = lab.find_branchpoints(source)[0]
    kwargs = dict(
        alternative_action="pass",
        hidden_information_policy=HiddenInformationPolicy.MULTIPLE_FUTURE_SAMPLES,
        seed_policy=SeedPolicy.DERIVED_SEEDS,
        seed=33,
        future_samples=12,
    )
    one = lab.run(branch, workers=1, **kwargs)
    four = lab.run(branch, workers=4, **kwargs)
    assert one.future_samples == four.future_samples
    assert one.mean_improvement == four.mean_improvement


def test_hidden_information_modes_and_external_engine_boundary(tmp_path: Path) -> None:
    source = _write_replay(tmp_path)
    lab = CounterfactualReplayLab(tmp_path)
    branch = lab.find_branchpoints(source)[0]
    same = lab.run(
        branch,
        alternative_action="pass",
        hidden_information_policy=HiddenInformationPolicy.SAME_REALIZED_FUTURE,
        future_samples=20,
    )
    assert len(same.future_samples) == 1
    multi = lab.run(
        branch,
        alternative_action="pass",
        hidden_information_policy=HiddenInformationPolicy.MULTIPLE_FUTURE_SAMPLES,
        seed_policy=SeedPolicy.DERIVED_SEEDS,
        future_samples=10,
    )
    assert multi.improvement_variance > 0
    with pytest.raises(CounterfactualError, match="external engine is not available"):
        lab.run(
            branch, alternative_action="pass", engine_mode=CounterfactualEngineMode.EXTERNAL_ENGINE
        )


def test_compare_regret_and_fixture_export(tmp_path: Path) -> None:
    source = _write_replay(tmp_path)
    lab = CounterfactualReplayLab(tmp_path)
    branch = lab.find_branchpoints(source)[0]
    preferred = lab.run(branch, alternative_action="pass")
    worse = lab.run(branch, alternative_action="counter:Value")
    comparison = lab.compare([preferred, worse])
    assert comparison.best_alternative == "pass"
    assert lab.regret(preferred).decision_regret > 0
    target = tmp_path / "fixture.json"
    payload = lab.export_fixture(branch, target)
    assert target.is_file()
    assert payload["truth_boundary"] == "model_alternative_not_historical_fact"


def test_tactical_oracle_actions_are_executed_without_external_claim(tmp_path: Path) -> None:
    target = tmp_path / "data/runs/counterfactual/source/events/tactical.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "event_type": "game_started",
            "game_id": "g2",
            "sequence": 0,
            "actor_id": None,
            "payload": {"seed": 1},
        },
        {
            "event_type": "pilot_decision",
            "game_id": "g2",
            "sequence": 1,
            "actor_id": "p1",
            "payload": {
                "phase": "main",
                "selected_action_id": "cast-now",
                "selected_utility": 2.0,
                "counterfactual_actions": [
                    {
                        "action_id": "cast-now",
                        "utility": 2.0,
                        "legal": True,
                        "action_kind": "cast_commander",
                        "tactical_rule": "commander_tax",
                        "tactical_input": {
                            "prior_command_zone_casts": 0,
                            "printed_generic_cost": 5,
                        },
                    },
                    {
                        "action_id": "cast-later",
                        "utility": 2.2,
                        "legal": True,
                        "action_kind": "cast_commander",
                        "tactical_rule": "commander_tax",
                        "tactical_input": {
                            "prior_command_zone_casts": 1,
                            "printed_generic_cost": 5,
                        },
                    },
                ],
            },
        },
    ]
    target.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8"
    )
    lab = CounterfactualReplayLab(tmp_path)
    branch = lab.find_branchpoints(str(target.relative_to(tmp_path)))[0]
    result = lab.run(
        branch,
        alternative_action="cast-later",
        engine_mode=CounterfactualEngineMode.TACTICAL_ORACLE,
    )
    assert result.provenance["validation_level"] == "tactical_oracle"
    assert result.tactical_oracle_used is True
    assert result.tactical_observations["chosen"]["total_cast_cost"] == 5
    assert result.tactical_observations["alternative"]["total_cast_cost"] == 7
    assert result.external_engine_used is False
    assert any("not an external rules engine" in warning for warning in result.warnings)
