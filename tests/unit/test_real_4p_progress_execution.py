"""Offline controls for the B8 driver and twin-run acceptance boundary."""

from __future__ import annotations

import importlib.util
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


def _frame(turn: int, seat: int = 0) -> dict:
    return {
        "decision": {
            "decision_class": "priority",
            "decision_id": f"d-{turn}-{seat}",
            "actor_id": f"p-{seat}",
            "seat": seat,
            "pilot_state": {
                "turn_number": turn,
                "phase": "PRECOMBAT_MAIN",
                "seat": seat,
                "active_player_id": f"p-{(turn - 1) % 4}",
                "players": [{"player_id": f"p-{i}", "seat": i} for i in range(4)],
            },
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


def _round() -> list[dict]:
    return [_frame(turn, seat) for turn in range(1, 5) for seat in range(4)] + [_frame(5)]


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


def test_script_keeps_technical_evidence_boundary(monkeypatch, repo_root, tmp_path) -> None:
    result, _ = _run(monkeypatch, _round())
    report = _script_run(monkeypatch, repo_root, tmp_path, [result, result])
    assert report["status"] == "PASS"
    assert report["evidence_class"] == "technical_conformance_only"
    assert report["official_campaign_eligible"] is False
    assert report["actual_card_behavior_coverage_claim"] is False
    assert report["progress_contract"]["through_turn"] == 4


def test_the_active_seat_is_resolved_in_the_deciders_view(monkeypatch) -> None:
    result, _client = _run(monkeypatch, _round())
    assert {row[2]: row[5] for row in result.progress_trace} == {1: 0, 2: 1, 3: 2, 4: 3}
    assert full_game._active_seat({"active_player_id": "x", "players": []}) is None
    assert full_game._active_seat(None) is None
