"""C2: the actor-scoped hidden-information claim rests on a per-frame runtime audit.

Every decision frame of a full game is audited: exactly one actor row, the
frame's own actor, and no other player's hand or mana pool unless the engine
marked that row visible to this principal (control, CR 723.4). A clean run
reports the claim as OBSERVED with frame counts; a leaking frame ends the run
fail closed; a run that audited nothing stays DECLARED_NOT_OBSERVED.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

import commander_lab.engine.rules.full_game as full_game_module
from commander_lab.engine.rules.full_game import (
    FULL_GAME_EVIDENCE_CLASS,
    FullGameConformanceError,
    XmageFullGameRunner,
    audit_actor_scoped_frame,
)
from tests.unit.test_ws223_cardinality_regression import (
    _binding,
    _deck,
    _priority_pass_request,
    _scenario,
    _ScriptedBridge,
)

SENTINEL = "Honeycard Sentinel 1d7e"


def _frame(player_count: int = 4) -> dict[str, Any]:
    return _priority_pass_request(player_count, 1)


def test_a_clean_frame_passes_and_counts_opponent_rows() -> None:
    rows, visible, violations = audit_actor_scoped_frame(_frame(4))
    assert (rows, visible, violations) == (3, 0, [])


def test_an_opponent_hand_is_a_violation_named_by_seat_only() -> None:
    frame = _frame(4)
    frame["pilot_state"]["players"][2]["hand"] = [{"object_id": "x", "name": SENTINEL}]
    _, _, violations = audit_actor_scoped_frame(frame)
    assert violations == ["seat 2 exposes hand to another principal"]
    assert SENTINEL not in " ".join(violations)


def test_an_opponent_mana_pool_is_a_violation() -> None:
    frame = _frame(4)
    frame["pilot_state"]["players"][1]["mana_pool"] = {"white": 3}
    assert audit_actor_scoped_frame(frame)[2] == ["seat 1 exposes mana_pool to another principal"]


def test_an_engine_marked_visible_row_is_counted_not_flagged() -> None:
    frame = _frame(4)
    controlled = frame["pilot_state"]["players"][3]
    controlled["private_state_visible"] = True
    controlled["hand"] = []
    assert audit_actor_scoped_frame(frame) == (3, 1, [])


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda f: f["pilot_state"]["players"][0].__setitem__("is_actor", False), "0 actor rows"),
        (lambda f: f.__setitem__("actor_id", "someone-else"), "not the frame's actor"),
        (lambda f: f.pop("pilot_state"), "no principal-scoped player state"),
    ],
)
def test_malformed_actor_rows_are_violations(mutate: Any, expected: str) -> None:
    frame = _frame(4)
    mutate(frame)
    assert any(expected in v for v in audit_actor_scoped_frame(frame)[2])


def _result_payload(player_count: int, seed: int) -> dict[str, Any]:
    return {
        "evidence_class": FULL_GAME_EVIDENCE_CLASS,
        "consumed_gameplay_evidence": False,
        "holdout_consumed": False,
        "official_campaign_eligible": False,
        "rules_authority": "xmage",
        "decision_policy_authority": "commander_lab_external_pilot",
        "bit_exact_replay_validated": False,
        "seed": seed,
        "terminal": True,
        "decision_count": 4,
        "outcomes": [
            {"seat": index, "won": index == 0, "lost": index != 0, "left": False}
            for index in range(player_count)
        ],
        "transcript": [],
    }


def _run(monkeypatch: pytest.MonkeyPatch, frames: list[dict[str, Any]]) -> Any:
    player_count, seed = 4, 23
    bridge = _ScriptedBridge(player_count, frames)
    original = bridge.request

    def request(message_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if message_type == "get_full_game_result":
            return _result_payload(player_count, seed)
        return original(message_type, payload)

    bridge.request = request  # type: ignore[method-assign]
    monkeypatch.setattr(full_game_module, "_RawFullGameClient", lambda *a, **k: bridge)
    runner = XmageFullGameRunner(command=("java", "-jar", "bridge.jar", "full-game"))
    return runner.run(
        scenario=_scenario(player_count, seed=seed),
        decks=tuple(_deck(seat) for seat in range(1, player_count + 1)),
        pilots=tuple(_binding(seat, f"fixture-{seat}") for seat in range(1, player_count + 1)),
    )


def test_a_clean_game_reports_the_claim_as_observed(monkeypatch: pytest.MonkeyPatch) -> None:
    frames = [_priority_pass_request(4, offset + 1) for offset in range(4)]
    result = _run(monkeypatch, frames)
    assert result.hidden_information_audit.frames_audited == 4
    assert result.hidden_information_audit.non_actor_rows_audited == 12
    assert result.hidden_information_audit.non_actor_rows_engine_visible == 0
    assert result.claim_basis.hidden_information_actor_scoped == "OBSERVED"


def test_a_leaking_frame_ends_the_game_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    frames = [_priority_pass_request(4, offset + 1) for offset in range(4)]
    leaking = copy.deepcopy(frames[2])
    leaking["pilot_state"]["players"][1]["hand"] = [{"object_id": "h", "name": SENTINEL}]
    frames[2] = leaking
    with pytest.raises(FullGameConformanceError, match="not actor-scoped at decision 3") as caught:
        _run(monkeypatch, frames)
    assert SENTINEL not in str(caught.value)


def test_a_result_without_an_audit_stays_declared() -> None:
    from tests.unit.test_xmage_full_game import _decks, _result
    from tests.unit.test_xmage_full_game import _scenario as scenario_of

    result = _result(scenario_of(_decks()))
    assert result.hidden_information_audit.frames_audited == 0
    assert result.claim_basis.hidden_information_actor_scoped == "DECLARED_NOT_OBSERVED"
