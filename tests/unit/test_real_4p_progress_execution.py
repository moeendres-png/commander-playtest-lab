"""Offline controls for the B8 driver and twin-run acceptance boundary."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

import commander_lab.engine.rules.full_game as full_game
from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules.full_game import (
    FullGameConformanceError,
    XmageFullGameRunner,
)


def _scenario() -> FutureXmageScenario:
    return FutureXmageScenario(
        candidate_id="own",
        deck_hash="ab" * 32,
        opponent_deck_ids=("a", "b", "c"),
        player_count=4,
        seat=1,
        scenario_id="offline-progress",
        seed=7,
        xmage_commit="db" * 20,
        bridge_version="test",
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-full-game-policy-1.0.0",
    )


def _frame(turn: int, seat: int = 0, active: int | None = None, *, drop_active=False) -> dict:
    # The engine reports the active player in the actor-scoped id space: the
    # actor's own id, or the seat-derived opaque token of another principal.
    active = (turn - 1) % 4 if active is None else active
    players = [{"player_id": f"p-{i}" if i == seat else f"op-{i}", "seat": i} for i in range(4)]
    state = {
        "turn_number": turn,
        "phase": "PRECOMBAT_MAIN",
        "seat": seat,
        "active_player_id": players[active]["player_id"],
        "players": players,
    }
    if drop_active:
        del state["active_player_id"]
    return {
        "decision": {
            "decision_class": "priority",
            "decision_id": f"d-{turn}-{seat}",
            "actor_id": f"p-{seat}",
            "seat": seat,
            "pilot_state": state,
            "legal_options": [{"option_id": "pass", "kind": "pass", "label": "Pass"}],
        }
    }


class _Client:
    def __init__(self, statuses: list[dict]) -> None:
        self.statuses = iter(statuses)
        self.submissions: list[dict] = []
        self.shutdown_disposition = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.shutdown_disposition = full_game.FULL_GAME_SHUTDOWN_GRACEFUL

    def request(self, kind: str, payload=None) -> dict:
        if kind == "submit_full_game_decision":
            self.submissions.append(payload["response"])
        return next(self.statuses)


class _Policy:
    def __init__(self, number: int = 1) -> None:
        self.number = number

    def decide(self, frame: dict) -> dict:
        return {
            "decision_id": frame["decision_id"],
            "actor_id": frame["actor_id"],
            "selected_option_ids": ["pass"],
            "ordering": [],
            "numeric_choice": self.number,
        }


def _run(monkeypatch, statuses, *, cap=30, boundary=5, number=1):
    client = _Client(statuses)
    monkeypatch.setattr(full_game, "_RawFullGameClient", lambda *a, **kw: client)
    monkeypatch.setattr(XmageFullGameRunner, "_validated_policy", lambda *a: _Policy(number))
    monkeypatch.setattr(XmageFullGameRunner, "_open_game", lambda *a: {"engine_version": "test"})
    result = XmageFullGameRunner(command=("java", "full-game")).run_smoke(
        scenario=_scenario(),
        decks=(),
        pilots=(),
        smoke_decision_target=cap,
        stop_at_turn=boundary,
    )
    return result, client


def _round(**kwargs) -> list[dict]:
    return [_frame(turn, seat, **kwargs) for turn in range(1, 5) for seat in range(4)] + [_frame(5)]


def _one_seat_round() -> list[dict]:
    """Every seat answers priority on every turn, but seat 1 is active for turns 2-4."""
    return [
        _frame(turn, seat, 0 if turn == 1 else 1) for turn in range(1, 5) for seat in range(4)
    ] + [_frame(5)]


def test_trace_records_the_engine_reported_active_seat(monkeypatch) -> None:
    result, _ = _run(monkeypatch, _round())
    # Bound from the engine's active-player field, never from who answered.
    assert {(row[1], row[2], row[4]) for row in result.progress_trace} == {
        (seat, turn, turn - 1) for turn in range(1, 5) for seat in range(4)
    }
    contract = full_game.smoke_progress_contract(
        result.progress_trace, player_count=4, through_turn=4
    )
    assert contract["met"] is True, contract["violations"]
    assert contract["active_seat_by_turn"] == [0, 1, 2, 3]


def test_active_seat_is_bound_into_progress_digest(monkeypatch) -> None:
    honest, _ = _run(monkeypatch, _round())
    other_order, _ = _run(
        monkeypatch,
        [_frame(turn, seat, (turn + 1) % 4) for turn in range(1, 5) for seat in range(4)]
        + [_frame(5)],
    )
    assert honest.progress_digest != other_order.progress_digest


@pytest.mark.parametrize(
    "state",
    [
        {},
        {"active_player_id": None, "players": [{"player_id": "op-0", "seat": 0}]},
        {"active_player_id": "op-9", "players": [{"player_id": "op-0", "seat": 0}]},
        {"active_player_id": "op-0"},
        {"active_player_id": "op-0", "players": [{"player_id": "op-0", "seat": True}]},
        {
            "active_player_id": "op-0",
            "players": [{"player_id": "op-0", "seat": 0}, {"player_id": "op-0", "seat": 1}],
        },
    ],
)
def test_unresolvable_engine_active_player_is_none(state) -> None:
    assert full_game.engine_active_seat(state) is None


def test_turn_contract_rejects_decision_cap_before_boundary(monkeypatch) -> None:
    with pytest.raises(FullGameConformanceError, match="turn boundary"):
        _run(monkeypatch, _round(), cap=2)


def test_turn_contract_rejects_early_terminal(monkeypatch) -> None:
    with pytest.raises(FullGameConformanceError, match="turn boundary"):
        _run(monkeypatch, [_frame(1), {"terminal": True}])


def test_response_content_is_bound_into_progress_digest(monkeypatch) -> None:
    first, _ = _run(monkeypatch, _round(), number=1)
    second, _ = _run(monkeypatch, _round(), number=2)
    assert first.progress_digest != second.progress_digest


def test_boundary_is_observed_without_answering_it(monkeypatch) -> None:
    result, client = _run(monkeypatch, _round())
    assert result.stop_reason == "turn_boundary"
    assert result.stop_turn_number == 5
    assert result.decision_count == len(client.submissions) == 16
    assert all(row[2] <= 4 for row in result.progress_trace)


def _script(repo_root: Path):
    path = repo_root / "scripts/run_real_4p_full_game_smoke.py"
    spec = importlib.util.spec_from_file_location("b8_offline_smoke", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _script_run(monkeypatch, repo_root, tmp_path, results):
    module = _script(repo_root)
    setup = module.build_real_4p_setup(repo_root)
    monkeypatch.setattr(module, "build_real_4p_setup", lambda root: setup)
    monkeypatch.delenv("XMAGE_COMMIT", raising=False)
    results = [
        item.model_copy(update={"seed": setup[0].seed, "xmage_commit": setup[0].xmage_commit})
        for item in results
    ]
    sequence = iter(results)

    class Runner:
        def __init__(self, **kwargs):
            pass

        def run_smoke(self, **kwargs):
            return next(sequence)

    monkeypatch.setattr(module, "XmageFullGameRunner", Runner)
    return module.run_live_smoke(tmp_path, smoke_decisions=30, progress_turns=4)


def test_script_checks_the_second_twin_contract(monkeypatch, repo_root, tmp_path) -> None:
    first, _ = _run(monkeypatch, _round())
    second = first.model_copy(update={"progress_trace": first.progress_trace[:1]})
    with pytest.raises(FullGameConformanceError, match="progress"):
        _script_run(monkeypatch, repo_root, tmp_path, [first, second])


def test_script_rejects_a_missing_twin_digest(monkeypatch, repo_root, tmp_path) -> None:
    result, _ = _run(monkeypatch, _round())
    invalid = result.model_copy(update={"progress_digest": None})
    with pytest.raises(FullGameConformanceError, match="progress"):
        _script_run(monkeypatch, repo_root, tmp_path, [invalid, invalid])


def test_script_rejects_one_seat_taking_turns_two_to_four(monkeypatch, repo_root, tmp_path) -> None:
    result, _ = _run(monkeypatch, _one_seat_round())
    assert {row[1] for row in result.progress_trace} == {0, 1, 2, 3}
    with pytest.raises(FullGameConformanceError, match="first full round was not taken"):
        _script_run(monkeypatch, repo_root, tmp_path, [result, result])
    report = json.loads(
        (tmp_path / "artifacts/xmage-full-game/REAL_4P_TECHNICAL_SMOKE.json").read_text()
    )
    assert report["status"] == "FAIL"
    assert report["progress_contract"]["active_seat_by_turn"] == [0, 1, 1, 1]


def test_script_rejects_a_missing_engine_active_player(monkeypatch, repo_root, tmp_path) -> None:
    result, _ = _run(monkeypatch, _round(drop_active=True))
    assert all(row[4] is None for row in result.progress_trace)
    with pytest.raises(FullGameConformanceError, match="no engine-reported active seat"):
        _script_run(monkeypatch, repo_root, tmp_path, [result, result])


def test_script_rejects_twins_with_a_different_seat_order(monkeypatch, repo_root, tmp_path) -> None:
    first, _ = _run(monkeypatch, _round())
    second, _ = _run(
        monkeypatch,
        [_frame(turn, seat, (turn + 1) % 4) for turn in range(1, 5) for seat in range(4)]
        + [_frame(5)],
    )
    with pytest.raises(FullGameConformanceError, match="twin_match=False"):
        _script_run(monkeypatch, repo_root, tmp_path, [first, second])


def test_script_keeps_technical_evidence_boundary(monkeypatch, repo_root, tmp_path) -> None:
    result, _ = _run(monkeypatch, _round())
    report = _script_run(monkeypatch, repo_root, tmp_path, [result, result])
    assert report["status"] == "PASS"
    assert report["evidence_class"] == "technical_conformance_only"
    assert report["official_campaign_eligible"] is False
    assert report["actual_card_behavior_coverage_claim"] is False
    assert report["progress_contract"]["through_turn"] == 4
    assert report["progress_contract"]["active_seat_by_turn"] == [0, 1, 2, 3]
    assert report["twin_active_seat_by_turn"] == [[0, 1, 2, 3], [0, 1, 2, 3]]
