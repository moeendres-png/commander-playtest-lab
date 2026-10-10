"""#701: every multi-option pass on the credited causal path goes through declared_pass.

The two terminal helpers that finish a credited mid-game causal row --
``observe_priority_ring`` and ``observe_scripted_decision`` -- both answer
priority frames on behalf of a player. Before this repair each submitted the
engine's own ``pass_priority`` option directly, which skipped both halves of the
Lab's answer authority:

* #634 B2 -- a multi-option frame is answered only when the record itself declares
  the pass (``priority_pass_through``, CR 117.3d), so the Lab never chooses for a
  player who holds a live response; and
* #695 -- a declared multi-option pass is bounded above by the record's own
  ``temporal_state`` checkpoint, because causal reconstruction rebuilds the
  requested state there rather than advancing the game (CR 500.1).

Controls, one per ruled case, for each helper:

* an undeclared multi-option pass raises and submits nothing;
* a declared multi-option pass past the record's checkpoint, at a later step of
  the same turn and in a later turn, raises and submits nothing;
* a declared multi-option pass at the checkpoint is allowed and traced, naming
  its acting principal, the engine's decision id, its declaring scope and the tag;
* a single-option frame leaves no choice and still passes, for any player, at any
  position, traced as ``single_option``.

The fake client serves the engine's offers and the record's declaration
independently, so a multi-option pass can only be answered through the record.
"""

from __future__ import annotations

from typing import Any

import pytest

from commander_lab.qualification.current_boundary import midgame_rows as mr

PASS_SELECTION = {
    "matches_only_provider_offered_legal_options": True,
    "on_zero_match": "FAIL_CLOSED",
    "on_multiple_match": "FAIL_CLOSED",
    "selector_kind": "semantic_action",
    "semantic_value": "pass_priority",
}
# The declaration a record may carry: every priority from the causal preparation
# start until the lane's own obligation completes is passed (CR 117.3d). The
# obligation loop's own stop is the completion point, so the declaration can
# never extend a row past its natural stop.
OBLIGATION_SCOPE = {
    "from": {"turn": 1, "phase": "beginning"},
    "until": {"event": "OBLIGATION_COMPLETE"},
}
# The record's own checkpoint: turn 1, precombat main.
CHECKPOINT = {"turn_number": 1, "phase": "precombat_main", "step": "main"}

PASS_DECLARATION = {
    "decision_family": "priority_pass_through",
    "actor": "ALL",
    "selection": dict(PASS_SELECTION),
    "scope": dict(OBLIGATION_SCOPE),
}


def _ring_record(*, declared: bool = True) -> dict[str, Any]:
    """A causal record whose ``priority_pass_through`` declaration is present or absent."""
    return {
        "fixture_id": "WS05-MP-PRIO-3",
        "temporal_state": dict(CHECKPOINT),
        "decision_script": [dict(PASS_DECLARATION)] if declared else [],
    }


def _scripted_record(*, declared: bool = True) -> dict[str, Any]:
    """The scripted terminal's record: the row's own scripted decision, then the declaration.

    ``observe_scripted_decision`` reads ``decision_script[0]`` as the row's scripted
    decision, so the declaration follows it; ``declared_pass`` searches the whole
    script for the pass-through step, so its position is immaterial to the bound.
    """
    script: list[dict[str, Any]] = [
        {
            "actor": "P1",
            "decision_family": "choose_object",
            "selection": {
                **PASS_SELECTION,
                "selector_kind": "semantic_action",
                "semantic_value": "obj:a",
            },
        }
    ]
    if declared:
        script.append(dict(PASS_DECLARATION))
    return {
        "fixture_id": "PILOT_CHOOSE_OBJECT",
        "temporal_state": dict(CHECKPOINT),
        "decision_script": script,
    }


# --------------------------------------------------------------------------- #
# Fake lane client
# --------------------------------------------------------------------------- #


def _position(turn: int = 1, phase: str = "precombat_main", step: str = "PRECOMBAT_MAIN") -> dict:
    return {"turn_number": turn, "phase": phase, "step": step}


class _Client:
    """A lane client serving recorded frames and per-principal projection readbacks.

    Each frame names its decision class, the seat the engine asks, whether a live
    response is offered beside the pass, the (turn, phase, step) that seat's own
    projection reads back while the frame is pending, and the legal actions the
    engine offers for it. A submission advances to the next frame.
    """

    def __init__(self, frames: list[dict[str, Any]]) -> None:
        self.frames = list(frames)
        self.submitted: list[list[str]] = []

    def _decision(self) -> dict[str, Any]:
        frame = self.frames[0]
        options: list[dict[str, Any]] = [
            {"option_type": "pass_priority", "option_id": f"pass-{frame['seat']}"}
        ]
        if frame.get("multi", frame["class"] == "priority"):
            options.append(
                {"option_type": "activate_ability", "option_id": f"cast-{frame['seat']}"}
            )
        return {
            "decision_class": frame["class"],
            "decision_id": f"d-{frame['seat']}-{'m' if len(options) > 1 else 's'}",
            "seat": frame["seat"],
            "actor_id": f"opaque-seat-handle-{frame['seat']}",
            "legal_options": options,
        }

    def pending_decision(self, attempts: int = 0) -> dict[str, Any] | None:
        return self._decision() if self.frames else None

    def request(self, message: str, payload: Any = None) -> dict[str, Any]:
        frame = self.frames[0]
        if message == "get_midgame_projection":
            principal = str((payload or {}).get("actor_id"))
            assert principal == f"P{frame['seat'] + 1}"
            return {"success": True, "payload": {"view": dict(frame["view"])}}
        assert message == "get_legal_actions"
        return {"success": True, "payload": {"actions": list(frame.get("actions") or ())}}

    def submit_options(self, decision: dict[str, Any], options: list[str]) -> None:
        self.submitted.append(list(options))
        self.frames.pop(0)


def _priority(seat: int, view: dict[str, Any], *, multi: bool = True) -> dict[str, Any]:
    return {"class": "priority", "seat": seat, "multi": multi, "view": view}


def _offer(native_id: str) -> dict[str, Any]:
    return {"action_id": native_id, "metadata": {"xmage_option_metadata": {"object_id": native_id}}}


# --------------------------------------------------------------------------- #
# observe_priority_ring
# --------------------------------------------------------------------------- #


def test_the_ring_refuses_an_undeclared_multi_option_pass() -> None:
    probe = mr.probe_module()
    client = _Client([_priority(0, _position())])
    authority = probe.PassAuthority(_ring_record(declared=False))
    with pytest.raises(probe.ml.MidgameLaneError) as excinfo:
        probe.observe_priority_ring(client, "t", authority)
    assert "undeclared priority pass for P1" in str(excinfo.value)
    assert client.submitted == [] and authority.trace == []


@pytest.mark.parametrize(
    ("view", "observed_text"),
    [
        (_position(step="POSTCOMBAT_MAIN"), "turn 1 step POSTCOMBAT_MAIN"),
        (_position(turn=2), "turn 2 step PRECOMBAT_MAIN"),
    ],
)
def test_the_ring_refuses_a_declared_multi_option_pass_past_the_checkpoint(
    view: dict[str, Any], observed_text: str
) -> None:
    probe = mr.probe_module()
    client = _Client([_priority(1, view)])
    authority = probe.PassAuthority(_ring_record())
    with pytest.raises(probe.ml.MidgameLaneError) as excinfo:
        probe.observe_priority_ring(client, "t", authority)
    message = str(excinfo.value)
    assert "is not at or before the record's own checkpoint" in message
    assert observed_text in message  # the observed position
    assert "turn 1 step PRECOMBAT_MAIN" in message  # the record's checkpoint
    assert client.submitted == [] and authority.trace == []


def test_the_ring_allows_a_declared_multi_option_pass_at_the_checkpoint_and_traces_it() -> None:
    probe = mr.probe_module()
    client = _Client([_priority(seat, _position()) for seat in (0, 1, 2)])
    authority = probe.PassAuthority(_ring_record())
    result = probe.observe_priority_ring(client, "t", authority)
    assert client.submitted == [["pass-0"], ["pass-1"], ["pass-2"]]
    assert result["kind"] == "priority_ring_with_live_response"
    assert result["observed"] is True
    assert result["passes_observed"] == 3 and result["principals_observed"] == 3
    assert authority.trace == [
        {
            "kind": "priority_pass",
            "actor": "P1",
            "decision_id": "d-0-m",
            "scope": "decision_script[0]",
            "tag": "t",
        },
        {
            "kind": "priority_pass",
            "actor": "P2",
            "decision_id": "d-1-m",
            "scope": "decision_script[0]",
            "tag": "t",
        },
        {
            "kind": "priority_pass",
            "actor": "P3",
            "decision_id": "d-2-m",
            "scope": "decision_script[0]",
            "tag": "t",
        },
    ]


def test_the_ring_still_passes_a_single_option_frame_for_any_player_at_any_position() -> None:
    probe = mr.probe_module()
    # No choice is offered, so neither the declaration nor the checkpoint can
    # bound the answer: it is the engine's own only offer, for every player.
    client = _Client(
        [
            _priority(0, _position(), multi=False),
            _priority(3, _position(step="POSTCOMBAT_MAIN"), multi=False),
            _priority(4, _position(turn=7, phase="end_turn", step="END_TURN"), multi=False),
        ]
    )
    authority = probe.PassAuthority(_ring_record(declared=False))
    result = probe.observe_priority_ring(client, "t", authority)
    assert client.submitted == [["pass-0"], ["pass-3"], ["pass-4"]]
    assert result["observed"] is True
    assert result["passes_observed"] == 3 and result["principals_observed"] == 3
    assert [entry["scope"] for entry in authority.trace] == ["single_option"] * 3
    assert [entry["actor"] for entry in authority.trace] == ["P1", "P4", "P5"]


def test_the_ring_mixes_a_declared_multi_option_pass_with_a_single_option_frame() -> None:
    probe = mr.probe_module()
    client = _Client(
        [
            _priority(0, _position(), multi=True),
            _priority(1, _position(), multi=False),
            _priority(2, _position(), multi=True),
        ]
    )
    authority = probe.PassAuthority(_ring_record())
    result = probe.observe_priority_ring(client, "t", authority)
    assert client.submitted == [["pass-0"], ["pass-1"], ["pass-2"]]
    assert [entry["scope"] for entry in authority.trace] == [
        "decision_script[0]",
        "single_option",
        "decision_script[0]",
    ]
    assert result["observed"] is True


def test_the_ring_still_stops_on_a_non_priority_frame_without_answering_it() -> None:
    probe = mr.probe_module()
    client = _Client([{"class": "choose_object", "seat": 0, "view": _position()}])
    authority = probe.PassAuthority(_ring_record(declared=False))
    result = probe.observe_priority_ring(client, "t", authority)
    assert result["observed"] is False
    assert result["passes_observed"] == 0
    assert client.submitted == [] and authority.trace == []


# --------------------------------------------------------------------------- #
# observe_scripted_decision
# --------------------------------------------------------------------------- #

PLACED = {"obj:a": "n-a"}


def test_the_scripted_terminal_refuses_an_undeclared_multi_option_pass() -> None:
    probe = mr.probe_module()
    record = _scripted_record(declared=False)
    client = _Client([_priority(1, _position())])
    authority = probe.PassAuthority(record)
    with pytest.raises(probe.ml.MidgameLaneError) as excinfo:
        probe.observe_scripted_decision(client, "t", record, PLACED, authority)
    assert "undeclared priority pass for P2" in str(excinfo.value)
    assert client.submitted == [] and authority.trace == []


@pytest.mark.parametrize(
    ("view", "observed_text"),
    [
        (_position(step="POSTCOMBAT_MAIN"), "turn 1 step POSTCOMBAT_MAIN"),
        (_position(turn=2), "turn 2 step PRECOMBAT_MAIN"),
    ],
)
def test_the_scripted_terminal_refuses_a_declared_multi_option_pass_past_the_checkpoint(
    view: dict[str, Any], observed_text: str
) -> None:
    probe = mr.probe_module()
    record = _scripted_record()
    client = _Client([_priority(2, view)])
    authority = probe.PassAuthority(record)
    with pytest.raises(probe.ml.MidgameLaneError) as excinfo:
        probe.observe_scripted_decision(client, "t", record, PLACED, authority)
    message = str(excinfo.value)
    assert "is not at or before the record's own checkpoint" in message
    assert observed_text in message  # the observed position
    assert "turn 1 step PRECOMBAT_MAIN" in message  # the record's checkpoint
    assert client.submitted == [] and authority.trace == []


def test_the_scripted_terminal_passes_a_declared_non_actor_frame_at_the_checkpoint() -> None:
    probe = mr.probe_module()
    record = _scripted_record()
    # A non-actor who holds a live response at the checkpoint: the record declares
    # the pass, so the Lab answers it and traces whose answer it gave.
    client = _Client(
        [
            _priority(1, _position(), multi=True),
            {"class": "choose_object", "seat": 0, "view": _position(), "actions": [_offer("n-a")]},
        ]
    )
    authority = probe.PassAuthority(record)
    terminal = probe.observe_scripted_decision(client, "t", record, PLACED, authority)
    assert client.submitted == [["pass-1"]]
    assert authority.trace == [
        {
            "kind": "priority_pass",
            "actor": "P2",
            "decision_id": "d-1-m",
            "scope": "decision_script[1]",
            "tag": "t",
        }
    ]
    # The row's own scripted choice is then asked of P1 with exactly one offer.
    assert terminal["kind"] == "scripted_decision_offered"
    assert terminal["observed"] is True


def test_the_scripted_terminal_still_passes_a_single_option_frame_for_a_non_actor() -> None:
    probe = mr.probe_module()
    record = _scripted_record(declared=False)
    client = _Client(
        [
            _priority(1, _position(step="POSTCOMBAT_MAIN"), multi=False),
            {
                "class": "choice",
                "seat": 0,
                "view": _position(),
                "actions": [{"action_id": "red", "metadata": {"label": "Red"}}],
            },
        ]
    )
    authority = probe.PassAuthority(record)
    terminal = probe.observe_scripted_decision(client, "t", record, PLACED, authority)
    assert client.submitted == [["pass-1"]]
    assert [entry["scope"] for entry in authority.trace] == ["single_option"]
    assert authority.trace[0]["actor"] == "P2"
    assert (
        terminal["observed"] is False
    )  # the engine asked ``choice``, the record scripts a choice for P1
    assert "choice:P1" in terminal["detail"]
