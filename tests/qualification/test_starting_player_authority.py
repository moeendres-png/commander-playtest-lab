"""#572: the Lab never chooses the starting player.

Every control here fails on the pre-fix implementation, where
``drive_commander_game`` defaulted ``scripted_starting_seat`` to ``"p1"`` and
answered every engine STARTING_PLAYER frame with it, and the XMage create
request omitted the seat entirely so the bridge's seat-0 default applied.

The binding rule: the starting seat must be explicitly declared by the
authoritative record/contract and submitted only through the engine-authored
legal decision frame, or the path must fail closed. The construction proof may
compare temporal active/priority facts only on a channel the engine confirmed.
"""

from __future__ import annotations

from typing import Any

import pytest

from commander_lab.qualification.current_boundary import game_driver
from commander_lab.qualification.current_boundary.game_driver import (
    STARTING_PLAYER_CHANNEL_ENGINE_FRAME,
    STARTING_PLAYER_CHANNEL_PROVIDER_ACK,
)
from commander_lab.qualification.current_boundary.starting_player import (
    STARTER_DECLARATION_FIELD,
    STARTER_DECLARATION_PRE_FIRST_TURN,
    STARTER_DECLARATION_SCRIPT,
    record_starting_seat,
)


class _StartingFrameProcess:
    """A Protocol-2 surface that records every create request and submission."""

    def __init__(
        self,
        *,
        candidate: str,
        offered_seats: list[str | None] | None = None,
        create_echo: int | None = None,
        create_echo_present: bool = True,
        submit_error: dict[str, Any] | None = None,
    ) -> None:
        self.candidate = candidate
        self.offered_seats = offered_seats
        self.create_echo = create_echo
        self.create_echo_present = create_echo_present
        self.submit_error = submit_error
        self.create_requests: list[dict[str, Any]] = []
        self.submissions: list[dict[str, Any]] = []
        self.passes = 0
        self.handles = 0

    def request(
        self,
        message_type: str,
        payload: dict[str, Any],
        *,
        game_id: str | None = None,
        timeout_s: float = 0,
    ) -> dict[str, Any]:
        del game_id, timeout_s
        if message_type in {"start_engine", "get_provider_version"}:
            return {"success": True, "payload": {}}
        if message_type == "get_capabilities":
            return {"success": True, "payload": {"capabilities": {"seed_supported": False}}}
        if message_type == "import_deck":
            self.handles += 1
            return {"success": True, "payload": {"deck_handle": {"handle_id": f"d{self.handles}"}}}
        if message_type == "create_commander_game":
            self.create_requests.append(payload["request"])
            created: dict[str, Any] = {"player_count": 2}
            if self.create_echo_present:
                created["starting_player_seat"] = self.create_echo
            return {"success": True, "payload": created}
        if message_type == "start_game":
            return {"success": True, "payload": {"status": "started"}}
        if message_type == "submit_action":
            self.submissions.append(payload)
            if self.submit_error is not None:
                return self.submit_error
            return {"success": True, "payload": {"decision": {"executed": True}}}
        if message_type == "pass_priority":
            self.passes += 1
            return {"success": True, "payload": {}}
        raise AssertionError(f"unexpected request {message_type}")


def _starting_frame(offered: list[str | None], *, actor: str = "p1") -> dict[str, Any]:
    return {
        "seat": "p1",
        "decision": {
            "kind": "STARTING_PLAYER",
            "actor": actor,
            "revision": 3,
            "decision_id": "d" * 64,
            "status": "SUPPORTED",
        },
        "actions": [
            {
                "action_id": f"opt-{index}",
                "action_type": "structural_decision",
                "source_object_id": seat if seat is None else seat.upper(),
            }
            for index, seat in enumerate(offered)
        ],
        "raw": {},
    }


def _priority_frame() -> dict[str, Any]:
    return {
        "seat": "p1",
        "decision": {
            "kind": "PRIORITY",
            "actor": "p1",
            "revision": 4,
            "decision_id": "e" * 64,
            "status": "SUPPORTED",
        },
        "actions": [{"action_id": "pass", "action_type": "pass_priority", "metadata": {}}],
        "raw": {},
    }


def _drive(
    monkeypatch: pytest.MonkeyPatch,
    proc: _StartingFrameProcess,
    frames: list[dict[str, Any]],
    *,
    candidate: str,
    starting_seat: str | None,
    source: str | None,
) -> game_driver.CommandedGameResult:
    queue = iter(frames)
    monkeypatch.setattr(game_driver, "poll_decision", lambda *a, **k: next(queue))
    return game_driver.drive_commander_game(
        proc,  # type: ignore[arg-type]
        candidate=candidate,
        player_count=2,
        seed=7,
        scripted_starting_seat=starting_seat,
        starting_seat_source=source,
    )


def test_a_missing_declaration_never_answers_a_starting_player_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#572: the old p1 default submitted an option here; now nothing is sent."""
    proc = _StartingFrameProcess(candidate="forge", offered_seats=["p1", "p2"])
    result = _drive(
        monkeypatch,
        proc,
        [_starting_frame(["p1", "p2"]), _priority_frame()],
        candidate="forge",
        starting_seat=None,
        source=None,
    )
    assert result.failure_kind == "FAIL_CLOSED_UNSATISFIED"
    assert result.failure is not None and "declares no starting seat" in result.failure
    assert proc.submissions == []
    assert result.terminal_facts["starting_player_channel"] is None


def test_a_declared_seat_is_taken_from_the_engine_offered_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = _StartingFrameProcess(candidate="forge", offered_seats=["p1", "p2"])
    result = _drive(
        monkeypatch,
        proc,
        [_starting_frame(["p1", "p2"]), _priority_frame()],
        candidate="forge",
        starting_seat="p2",
        source="TEST_DECLARATION",
    )
    assert result.failure is None, result.failure
    assert len(proc.submissions) == 1
    assert proc.submissions[0]["proposal"]["legal_action_id"] == "opt-1"
    assert result.terminal_facts["starting_player_channel"] == (
        STARTING_PLAYER_CHANNEL_ENGINE_FRAME
    )
    assert result.terminal_facts["starting_player_declaration"] == {
        "seat": "p2",
        "source": "TEST_DECLARATION",
    }


@pytest.mark.parametrize(
    "offered",
    [
        ["p1", "p1"],  # two options name the declared seat: ambiguous identity
        ["p2", "p3"],  # the declared seat is not offered at all
        [None],  # no option identity to bind
    ],
)
def test_a_foreign_or_ambiguous_starting_option_identity_fails(
    monkeypatch: pytest.MonkeyPatch, offered: list[str | None]
) -> None:
    proc = _StartingFrameProcess(candidate="forge", offered_seats=offered)
    result = _drive(
        monkeypatch,
        proc,
        [_starting_frame(offered), _priority_frame()],
        candidate="forge",
        starting_seat="p1",
        source="TEST_DECLARATION",
    )
    assert result.failure_kind == "FAIL_CLOSED_UNSATISFIED"
    assert proc.submissions == []


def test_a_refused_starting_player_submission_is_never_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A stale/foreign revision refusal is terminal; no fallback option is tried."""
    proc = _StartingFrameProcess(
        candidate="forge",
        offered_seats=["p1", "p2"],
        submit_error={
            "success": False,
            "errors": [{"code": "stale_revision", "message": "decision revision is stale"}],
        },
    )
    result = _drive(
        monkeypatch,
        proc,
        [_starting_frame(["p1", "p2"]), _priority_frame()],
        candidate="forge",
        starting_seat="p1",
        source="TEST_DECLARATION",
    )
    assert result.failure_kind == "ENGINE_RUNTIME_ERROR"
    assert result.failure is not None and "stale_revision" in result.failure
    assert len(proc.submissions) == 1
    assert result.terminal_facts["starting_player_channel"] is None


def test_xmage_create_declares_the_seat_and_requires_the_engine_acknowledgement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = _StartingFrameProcess(
        candidate="xmage",
        offered_seats=None,
        create_echo=1,  # p2 -> index 1
    )
    result = _drive(
        monkeypatch,
        proc,
        [_priority_frame()],
        candidate="xmage",
        starting_seat="p2",
        source="TEST_DECLARATION",
    )
    assert result.failure is None, result.failure
    assert proc.create_requests[0]["starting_player_seat"] == 1
    assert result.terminal_facts["starting_player_provider_acknowledged_seat"] == 1
    assert result.terminal_facts["starting_player_channel"] == (
        STARTING_PLAYER_CHANNEL_PROVIDER_ACK
    )


def test_xmage_without_a_declaration_refuses_before_any_game_traffic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#572: no declaration means no XMage game at all, not a seat-0 game."""
    proc = _StartingFrameProcess(candidate="xmage", create_echo_present=False)
    result = _drive(
        monkeypatch,
        proc,
        [_priority_frame()],
        candidate="xmage",
        starting_seat=None,
        source=None,
    )
    assert result.failure_kind == "FAIL_CLOSED_UNSATISFIED"
    assert (
        result.failure is not None and "requires an explicit starting_player_seat" in result.failure
    )
    assert proc.create_requests == []
    assert proc.handles == 0
    assert result.terminal_facts["starting_player_channel"] is None


def test_xmage_create_acknowledging_another_seat_fails_the_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = _StartingFrameProcess(candidate="xmage", create_echo=0)
    result = _drive(
        monkeypatch,
        proc,
        [_priority_frame()],
        candidate="xmage",
        starting_seat="p2",
        source="TEST_DECLARATION",
    )
    assert result.failure_kind == "ENGINE_RUNTIME_ERROR"
    assert result.failure is not None
    assert "acknowledged starting_player_seat 0" in result.failure


def test_xmage_create_without_the_echo_is_an_unverified_channel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = _StartingFrameProcess(candidate="xmage", create_echo_present=False)
    result = _drive(
        monkeypatch,
        proc,
        [_priority_frame()],
        candidate="xmage",
        starting_seat="p1",
        source="TEST_DECLARATION",
    )
    assert result.failure is None, result.failure
    assert proc.create_requests[0]["starting_player_seat"] == 0
    assert result.terminal_facts["starting_player_channel"] is None


def test_a_declaration_outside_the_pod_is_refused() -> None:
    class _Never:
        def request(self, *a: object, **k: object) -> dict[str, Any]:
            raise AssertionError("no request may be sent for an invalid declaration")

    with pytest.raises(ValueError, match="outside"):
        game_driver.drive_commander_game(
            _Never(),  # type: ignore[arg-type]
            candidate="forge",
            player_count=2,
            seed=1,
            scripted_starting_seat="p4",
            starting_seat_source="TEST_DECLARATION",
        )
    with pytest.raises(ValueError, match="declared together"):
        game_driver.drive_commander_game(
            _Never(),  # type: ignore[arg-type]
            candidate="forge",
            player_count=2,
            seed=1,
            scripted_starting_seat="p1",
            starting_seat_source=None,
        )


def _record(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "fixture_id": "TEST",
        "decision_script": [],
        "temporal_state": {"turn_number": 0, "active_player": "P1"},
    }
    record.update(overrides)
    return record


def test_record_declarations_are_only_the_three_authoritative_shapes() -> None:
    assert record_starting_seat(_record()) == ("p1", STARTER_DECLARATION_PRE_FIRST_TURN)
    assert record_starting_seat(
        _record(temporal_state={"turn_number": 1, "active_player": "P1"})
    ) == (
        None,
        None,
    )
    assert record_starting_seat(_record(temporal_state={"turn_number": 0})) == (None, None)
    assert record_starting_seat(_record(temporal_state={}, starting_player="p3")) == (
        "p3",
        STARTER_DECLARATION_FIELD,
    )
    scripted = _record(
        decision_script=[
            {
                "decision_family": "starting_player",
                "actor": "P2",
                "selection": {
                    "selector_kind": "seat",
                    "semantic_value": "P2",
                    "matches_only_provider_offered_legal_options": True,
                    "on_zero_match": "FAIL_CLOSED",
                    "on_multiple_match": "FAIL_CLOSED",
                },
            }
        ]
    )
    assert record_starting_seat(scripted) == ("p2", STARTER_DECLARATION_SCRIPT)
    # A scripted step without its fail-closed selection contract has no authority.
    broken = _record(
        decision_script=[
            {
                "decision_family": "starting_player",
                "actor": "P2",
                "selection": {"selector_kind": "seat", "semantic_value": "P2"},
            }
        ]
    )
    assert record_starting_seat(broken) == (None, None)
    assert record_starting_seat(_record(temporal_state=None)) == (None, None)


def test_an_expected_starting_player_token_is_not_a_declaration() -> None:
    """#572: an obligation statement may not be read as the decision."""
    record = _record(
        temporal_state=None,
        expected_events={"required_events": ["starting_player:P1", "first_turn_draw:false"]},
    )
    assert record_starting_seat(record) == (None, None)
