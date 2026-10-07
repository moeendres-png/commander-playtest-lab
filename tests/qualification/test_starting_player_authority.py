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
from _protocol2_starting_frames import StartingFrameProcess as _StartingFrameProcess

from commander_lab.qualification.current_boundary import full107, game_driver
from commander_lab.qualification.current_boundary.game_driver import (
    STARTING_PLAYER_CHANNEL_ENGINE_FRAME,
    STARTING_PLAYER_CHANNEL_PROVIDER_CONFIRMED,
)
from commander_lab.qualification.current_boundary.starting_player import (
    STARTER_DECLARATION_FIELD,
    STARTER_DECLARATION_PRE_FIRST_TURN,
    STARTER_DECLARATION_SCRIPT,
    record_starting_seat,
)


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


def test_a_declared_seat_without_an_answered_engine_frame_is_never_a_channel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#572 review P2-2 (mutant M10): the channel needs an answered frame.

    Forge declared p1 but published no STARTING_PLAYER frame in this run: the
    declaration alone must not be labelled ENGINE_FRAME_FROM_RECORD_DECLARATION.
    The construction proof then keeps the temporal active/priority checks
    UNSUPPORTED for this channel (proved end to end in
    ``test_generic_construction_proof``).
    """
    proc = _StartingFrameProcess(candidate="forge", offered_seats=None)
    result = _drive(
        monkeypatch,
        proc,
        [_priority_frame()],
        candidate="forge",
        starting_seat="p1",
        source="TEST_DECLARATION",
    )
    assert result.failure is None, result.failure
    assert result.terminal_facts.get("starting_player_frame_answered") is None
    assert proc.submissions == []
    channel = result.terminal_facts["starting_player_channel"]
    assert channel is None
    assert channel not in game_driver.VERIFIED_STARTING_PLAYER_CHANNELS


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


def test_xmage_the_channel_needs_the_engines_own_start_readback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#572 review: a create echo repeats the request; only start_game confirms it."""
    proc = _StartingFrameProcess(
        candidate="xmage",
        offered_seats=None,
        create_echo=1,  # p2 -> index 1
        start_player_id="engine-p2",
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
    assert result.terminal_facts["starting_player_provider_confirmed_seat"] == "p2"
    assert result.terminal_facts["starting_player_prompt_answer_recorded"] is True
    assert result.terminal_facts["starting_player_channel"] == (
        STARTING_PLAYER_CHANNEL_PROVIDER_CONFIRMED
    )


def test_xmage_without_the_engines_start_readback_the_channel_is_unverified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A create echo alone never establishes the starter."""
    proc = _StartingFrameProcess(
        candidate="xmage",
        create_echo=1,
        start_player_id_present=False,
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
    assert result.terminal_facts["starting_player_provider_acknowledged_seat"] == 1
    assert result.terminal_facts.get("starting_player_provider_confirmed_seat") is None
    assert result.terminal_facts["starting_player_prompt_answer_recorded"] is False
    assert result.terminal_facts["starting_player_channel"] is None


def test_xmage_a_matching_readback_without_an_answered_prompt_is_not_confirmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#572 review P3-3: in a pod of 3+ the readback alone cannot tell a real
    CR 103.2 answer from GameImpl.init's first-player fallback. Without the
    chooser/chosen identities the channel is unverified, never credit."""
    proc = _StartingFrameProcess(
        candidate="xmage",
        create_echo=1,
        start_player_id="engine-p2",
        start_chooser_id_present=False,
        start_chosen_id_present=False,
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
    # The engine's readback names the declared seat, but no prompt answer was
    # recorded, so there is no engine-confirmed channel.
    assert result.terminal_facts.get("starting_player_provider_confirmed_seat") is None
    assert result.terminal_facts["starting_player_prompt_answer_recorded"] is False
    assert result.terminal_facts["starting_player_channel"] is None


@pytest.mark.parametrize(
    "prompt_ids",
    [
        {"start_chooser_id": "engine-p1"},  # the engine asked another chooser
        {"start_chosen_id": "engine-p1"},  # the engine chose another player
    ],
)
def test_xmage_prompt_identities_that_are_not_the_declared_seat_are_never_credit(
    monkeypatch: pytest.MonkeyPatch, prompt_ids: dict[str, str]
) -> None:
    """R3-C2: a prompt identity naming another seat refuses; no fallback seat."""
    proc = _StartingFrameProcess(
        candidate="xmage",
        create_echo=1,
        start_player_id="engine-p2",
        **prompt_ids,
    )
    result = _drive(
        monkeypatch,
        proc,
        [_priority_frame()],
        candidate="xmage",
        starting_seat="p2",
        source="TEST_DECLARATION",
    )
    assert result.failure_kind == "FAIL_CLOSED_UNSATISFIED"
    assert result.failure is not None
    assert "not the declared seat 'p2'" in result.failure
    assert result.terminal_facts["starting_player_channel"] is None


def test_xmage_an_engine_starter_that_is_not_the_declared_seat_is_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The engine's own readback contradicts the declaration: UNKNOWN, not FAIL."""
    proc = _StartingFrameProcess(
        candidate="xmage",
        create_echo=1,
        start_player_id="engine-p1",
    )
    result = _drive(
        monkeypatch,
        proc,
        [_priority_frame()],
        candidate="xmage",
        starting_seat="p2",
        source="TEST_DECLARATION",
    )
    # #572 review P3-2 / R3-C2: the record's decision was not executed, which
    # proves nothing and is never a Rules failure.
    assert result.failure_kind == "FAIL_CLOSED_UNSATISFIED"
    assert result.failure is not None
    assert "starting_player_id as 'p1'" in result.failure
    assert result.terminal_facts["starting_player_channel"] is None


def test_a_starting_seat_mismatch_is_unknown_never_a_rules_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#572 review P3-2: full107 maps the mismatch to UNKNOWN, never FAIL."""
    proc = _StartingFrameProcess(
        candidate="xmage",
        create_echo=1,
        start_player_id="engine-p1",
    )
    result = _drive(
        monkeypatch,
        proc,
        [_priority_frame()],
        candidate="xmage",
        starting_seat="p2",
        source="TEST_DECLARATION",
    )
    record = {
        "fixture_id": "WSR22_PLAYER_COUNT_2P",
        "players": [{"player_id": "P1"}, {"player_id": "P2"}],
    }
    row = full107.cardinality_row(record, result, candidate="xmage", runtime_identity={})
    assert row.outcome == "UNKNOWN"
    assert "does not authorize" in row.reason


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


def test_xmage_create_acknowledging_another_seat_is_unknown(
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
    # #572 review P3-2 / R3-C2: an acknowledgement of another seat means the
    # record's decision was not executed; UNKNOWN, never a Rules FAIL.
    assert result.failure_kind == "FAIL_CLOSED_UNSATISFIED"
    assert result.failure is not None
    assert "acknowledged starting_player_seat 0" in result.failure


def test_xmage_create_without_the_echo_still_needs_the_start_readback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = _StartingFrameProcess(
        candidate="xmage", create_echo_present=False, start_player_id="engine-p1"
    )
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
    # The echo is absent but the engine's own start readback confirms p1.
    assert result.terminal_facts["starting_player_provider_acknowledged_seat"] is None
    assert result.terminal_facts["starting_player_provider_confirmed_seat"] == "p1"
    assert result.terminal_facts["starting_player_channel"] == (
        STARTING_PLAYER_CHANNEL_PROVIDER_CONFIRMED
    )


def test_a_declaration_outside_the_pod_is_row_scoped_fail_closed() -> None:
    class _Never:
        def request(self, *a: object, **k: object) -> dict[str, Any]:
            raise AssertionError("no request may be sent for an invalid declaration")

    result = game_driver.drive_commander_game(
        _Never(),  # type: ignore[arg-type]
        candidate="forge",
        player_count=2,
        seed=1,
        scripted_starting_seat="p4",
        starting_seat_source="TEST_DECLARATION",
    )
    assert result.failure_kind == "FAIL_CLOSED_UNSATISFIED"
    assert result.failure is not None and "outside the 2-player pod" in result.failure
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


def _starter_step(seat: str, *, actor: str = "P2") -> dict[str, Any]:
    return {
        "decision_family": "starting_player",
        "actor": actor,
        "selection": {
            "selector_kind": "seat",
            "semantic_value": seat,
            "matches_only_provider_offered_legal_options": True,
            "on_zero_match": "FAIL_CLOSED",
            "on_multiple_match": "FAIL_CLOSED",
        },
    }


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
    # A later checkpoint's active player is not a declaration, so the scripted
    # step is read on its own (turn 1 is not the pre-first-turn shape).
    scripted = _record(
        decision_script=[_starter_step("P2")],
        temporal_state={"turn_number": 1, "active_player": "P1"},
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


@pytest.mark.parametrize(
    "record",
    [
        pytest.param(
            _record(decision_script=[_starter_step("P2"), _starter_step("P3")]),
            id="two-scripted-steps",
        ),
        pytest.param(
            _record(decision_script=[_starter_step("P2")], starting_player="p3"),
            id="script-and-field",
        ),
        # The pre-first-turn active player *is* the starting player (CR 103.1),
        # so a step that names another seat contradicts the requested state.
        pytest.param(
            _record(decision_script=[_starter_step("P2")]),
            id="script-and-pre-first-turn-state",
        ),
        pytest.param(
            _record(starting_player="p3"),
            id="field-and-pre-first-turn-state",
        ),
    ],
)
def test_two_starters_that_disagree_are_an_ambiguity_never_a_declaration(
    record: dict[str, Any],
) -> None:
    # First-wins would silently pick one of two contradictory statements. An
    # ambiguous record declares nothing, so every caller fails closed.
    assert record_starting_seat(record) == (None, None)


def test_identical_duplicate_declarations_are_one_declaration() -> None:
    duplicate = _record(
        decision_script=[_starter_step("P2"), _starter_step("P2")],
        starting_player="p2",
        temporal_state={"turn_number": 0, "active_player": "P2"},
    )
    assert record_starting_seat(duplicate) == ("p2", STARTER_DECLARATION_SCRIPT)


def test_an_expected_starting_player_token_is_not_a_declaration() -> None:
    """#572: an obligation statement may not be read as the decision."""
    record = _record(
        temporal_state=None,
        expected_events={"required_events": ["starting_player:P1", "first_turn_draw:false"]},
    )
    assert record_starting_seat(record) == (None, None)
