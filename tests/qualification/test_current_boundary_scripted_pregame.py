"""#441 PILOT_MULLIGAN: a record's scripted pregame on the candidate-neutral lane.

The driver answers every engine mulligan frame from the record's plan, for the
seat the engine names as the frame's actor (never the seat that happened to
poll), in the plan's order; an unscripted, extra or missing frame fails closed.
The row is credited only from the engine's own decisions and each seat's
engine-reported hand at the first priority after the pregame.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from commander_lab.qualification.current_boundary import full107, game_driver
from commander_lab.qualification.current_boundary.materialization import (
    load_effective_materialization,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAN = (("p1", False), ("p2", True), ("p3", True), ("p4", True), ("p1", True))
ENGINE_IDS = {"p1": "uuid-a", "p2": "uuid-b", "p3": "uuid-c", "p4": "uuid-d"}


def _record() -> dict[str, Any]:
    records = load_effective_materialization(REPO_ROOT).denominator_records()
    return copy.deepcopy(next(r for r in records if r["fixture_id"] == "PILOT_MULLIGAN"))


class _FakeProcess:
    """A bridge that reports seats either at creation or through state envelopes."""

    def __init__(self, *, roster_at_create: bool, hands: dict[str, int] | None = None) -> None:
        self.roster_at_create = roster_at_create
        self.hands = hands or {seat: 7 for seat in ENGINE_IDS}
        self.imports = 0
        self.mulligans: list[tuple[str, bool]] = []

    def actor(self, seat: str) -> str:
        return seat if self.roster_at_create else ENGINE_IDS[seat]

    def request(
        self,
        message_type: str,
        payload: dict[str, Any],
        *,
        game_id: str | None = None,
        timeout_s: float = 0,
    ) -> dict[str, Any]:
        del game_id, timeout_s
        if message_type == "get_capabilities":
            return {"success": True, "payload": {"capabilities": {"seed_supported": False}}}
        if message_type in {"start_engine", "get_provider_version"}:
            return {"success": True, "payload": {}}
        if message_type == "import_deck":
            self.imports += 1
            return {"success": True, "payload": {"deck_handle": {"handle_id": f"d{self.imports}"}}}
        if message_type == "create_commander_game":
            created: dict[str, Any] = {"player_count": 4}
            if self.roster_at_create:
                created["seats"] = [
                    {"seat": index, "player_id": seat} for index, seat in enumerate(ENGINE_IDS)
                ]
            return {"success": True, "payload": created}
        if message_type == "start_game":
            return {"success": True, "payload": {"status": "started"}}
        if message_type == "resolve_mulligan":
            self.mulligans.append((str(payload["player_id"]), bool(payload["keep"])))
            return {"success": True, "payload": {"keep": payload["keep"]}}
        if message_type == "pass_priority":
            return {"success": True, "payload": {}}
        if message_type == "get_game_state":
            seat = str(payload["observer_player_id"])
            index = list(ENGINE_IDS).index(seat)
            rows = [
                {
                    "player_id": self.actor(other),
                    "seat": position,
                    "zones": {"hand": [None] * self.hands[other], "library_size": 92},
                    **({"is_actor": other == seat} if self.roster_at_create else {}),
                }
                for position, other in enumerate(ENGINE_IDS)
            ]
            state = {"players": rows, "turn_number": 1, "phase": "beginning", "step": "upkeep"}
            envelope = (
                {}
                if self.roster_at_create
                else {
                    "observer_player_id": seat,
                    "observer_seat": index,
                    "observer_engine_player_id": ENGINE_IDS[seat],
                }
            )
            return {"success": True, "payload": {"state": state, **envelope}}
        raise AssertionError(f"unexpected request {message_type}")


def _frame(kind: str, actor: str) -> dict[str, Any]:
    # Every frame is reported to the first seat that polls: the polled seat is
    # never the actor's identity.
    return {
        "seat": "p1",
        "decision": {
            "kind": kind,
            "actor": actor,
            "revision": 1,
            "decision_id": None,
            "status": "SUPPORTED",
        },
        "actions": (
            [{"action_id": "pass", "action_type": "pass_priority", "metadata": {}}]
            if kind == "PRIORITY"
            else [{"action_id": "keep"}, {"action_id": "mull"}]
        ),
        "raw": {},
    }


def _drive(
    monkeypatch: pytest.MonkeyPatch,
    proc: _FakeProcess,
    asked: list[str],
    plan: tuple[tuple[str, bool], ...] = PLAN,
) -> game_driver.CommandedGameResult:
    frames = iter(
        [_frame("MULLIGAN", proc.actor(seat)) for seat in asked]
        + [_frame("PRIORITY", proc.actor("p1"))]
    )
    monkeypatch.setattr(game_driver, "poll_decision", lambda *a, **k: next(frames))
    return game_driver.drive_commander_game(
        proc,  # type: ignore[arg-type]
        candidate="xmage",
        player_count=4,
        seed=424242,
        drive_to="priority",
        mulligan_plan=plan,
    )


ASKED_IN_PLAN_ORDER = ["p1", "p2", "p3", "p4", "p1"]


@pytest.mark.parametrize("roster_at_create", [False, True])
def test_every_mulligan_frame_is_answered_from_the_plan_for_its_actor(
    monkeypatch: pytest.MonkeyPatch, roster_at_create: bool
) -> None:
    proc = _FakeProcess(roster_at_create=roster_at_create)
    result = _drive(monkeypatch, proc, ASKED_IN_PLAN_ORDER)
    assert result.failure is None
    assert [keep for _, keep in proc.mulligans] == [keep for _, keep in PLAN]
    tape = [(e.actor, e.chosen_option_id) for e in result.decision_tape if e.step == "mulligan"]
    assert tape == [(seat, "keep" if keep else "mulligan") for seat, keep in PLAN]
    assert all(
        e.policy == game_driver.SCRIPTED_MULLIGAN_POLICY
        for e in result.decision_tape
        if e.step == "mulligan"
    )
    hands = result.terminal_facts["post_pregame_zone_counts"]
    assert {seat: hands[seat]["hand_count"] for seat in ENGINE_IDS} == dict.fromkeys(ENGINE_IDS, 7)


@pytest.mark.parametrize(
    "asked",
    [
        # Another seat than the plan's next entry.
        ["p2", "p1", "p3", "p4", "p1"],
        # A frame after the plan is exhausted.
        [*ASKED_IN_PLAN_ORDER, "p2"],
        # A plan entry the engine never asked.
        ["p1", "p2", "p3", "p4"],
    ],
)
def test_an_unscripted_extra_or_missing_mulligan_fails_closed(
    monkeypatch: pytest.MonkeyPatch, asked: list[str]
) -> None:
    result = _drive(monkeypatch, _FakeProcess(roster_at_create=False), asked)
    assert result.failure is not None and "DecisionUnsatisfied" in result.failure
    assert result.failure_kind == "FAIL_CLOSED_UNSATISFIED"


def test_an_actor_outside_the_engines_roster_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proc = _FakeProcess(roster_at_create=False)
    frames = iter([_frame("MULLIGAN", "uuid-unknown")])
    monkeypatch.setattr(game_driver, "poll_decision", lambda *a, **k: next(frames))
    result = game_driver.drive_commander_game(
        proc,  # type: ignore[arg-type]
        candidate="xmage",
        player_count=4,
        seed=1,
        mulligan_plan=PLAN,
    )
    assert result.failure is not None and "not a seat" in result.failure
    assert proc.mulligans == []


def test_the_records_plan_and_script_must_agree() -> None:
    record = _record()
    assert full107.scripted_pregame_plan(record) == PLAN
    disagreeing = copy.deepcopy(record)
    disagreeing["decision_script"][0]["selection"]["semantic_value"] = "keep_opening_hand"
    with pytest.raises(ValueError):
        full107.scripted_pregame_plan(disagreeing)
    other_actor = copy.deepcopy(record)
    other_actor["decision_script"][1]["actor"] = "P3"
    with pytest.raises(ValueError):
        full107.scripted_pregame_plan(other_actor)


def _row(
    monkeypatch: pytest.MonkeyPatch, proc: _FakeProcess, asked: list[str]
) -> full107.RowResult:
    frames = iter(
        [_frame("MULLIGAN", proc.actor(seat)) for seat in asked]
        + [_frame("PRIORITY", proc.actor("p1"))]
    )
    monkeypatch.setattr(game_driver, "poll_decision", lambda *a, **k: next(frames))
    return full107.scripted_pregame_row(
        _record(),
        proc,  # type: ignore[arg-type]
        candidate="xmage",
        runtime_identity={},
    )


def test_the_engine_observed_pregame_is_the_records_obligation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = _row(monkeypatch, _FakeProcess(roster_at_create=False), ASKED_IN_PLAN_ORDER)
    assert row.outcome == "PASS", row.reason
    assert row.execution_mode == full107.SCRIPTED_PREGAME_MODE
    assert row.evidence["unmet_required_events"] == []


def test_a_bottomed_card_is_not_the_free_mulligan(monkeypatch: pytest.MonkeyPatch) -> None:
    # P1 kept six cards: one was bottomed, so "bottom_count:P1:0" is not shown.
    proc = _FakeProcess(roster_at_create=False, hands={"p1": 6, "p2": 7, "p3": 7, "p4": 7})
    row = _row(monkeypatch, proc, ASKED_IN_PLAN_ORDER)
    assert row.outcome == "UNKNOWN"
    assert row.evidence["unmet_required_events"] == ["bottom_count:P1:0"]


def test_a_pregame_that_did_not_complete_is_never_credited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = _row(monkeypatch, _FakeProcess(roster_at_create=False), ["p2", *ASKED_IN_PLAN_ORDER])
    assert row.outcome == "UNKNOWN"
    assert "did not complete" in row.reason


def test_only_the_declared_scripted_pregame_rows_take_this_route() -> None:
    assert full107.SCRIPTED_PREGAME_ROWS == ("PILOT_MULLIGAN",)
