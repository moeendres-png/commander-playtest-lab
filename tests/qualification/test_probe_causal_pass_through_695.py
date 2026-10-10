"""#695: a causal declared pass is bounded above by the record's own checkpoint.

Causal reconstruction rebuilds the requested state at the record's
``temporal_state`` checkpoint. A multi-option priority frame the record's
``priority_pass_through`` declaration covers is therefore answerable only at an
observed position at or before that checkpoint (CR 117.3d, 500.1); a later
position would advance the game rather than rebuild it, and stops the row.

Controls, one per ruled case:

* a multi-option pass standing exactly at the checkpoint is allowed and traced;
* one at an earlier position inside the same declared scope is allowed;
* one at a later step of the same turn raises and submits nothing;
* one in a later turn raises and submits nothing;
* a record whose ``temporal_state`` position is unreadable fails closed, never
  passing, even for a frame at the checkpoint itself;
* a single-option frame is no choice and still passes after the checkpoint;
* a phase-only checkpoint spans that phase.

The obligation loop's own ``OBLIGATION_COMPLETE`` scope and the arrival context
are untouched: only the causal ``declared_pass`` path carries this bound.
"""

from __future__ import annotations

from typing import Any

import pytest

from commander_lab.qualification.current_boundary import midgame_rows as mr

FAIL_CLOSED = {
    "matches_only_provider_offered_legal_options": True,
    "on_zero_match": "FAIL_CLOSED",
    "on_multiple_match": "FAIL_CLOSED",
}
# The obligation declaration: from the causal preparation start to the lane's own
# completion point, so it covers every observed position on or after turn 1's
# beginning. Only the checkpoint bound above can stop it.
OBLIGATION_SCOPE = {
    "from": {"turn": 1, "phase": "beginning"},
    "until": {"event": "OBLIGATION_COMPLETE"},
}
# The record's own checkpoint: turn 1, precombat main.
CHECKPOINT = {"turn_number": 1, "phase": "precombat_main", "step": "main"}
MISSING = object()


def _record(temporal_state: Any = CHECKPOINT) -> dict[str, Any]:
    record: dict[str, Any] = {
        "decision_script": [
            {
                "decision_family": "priority_pass_through",
                "actor": "ALL",
                "selection": {
                    **FAIL_CLOSED,
                    "selector_kind": "semantic_action",
                    "semantic_value": "pass_priority",
                },
                "scope": dict(OBLIGATION_SCOPE),
            }
        ]
    }
    if temporal_state is not MISSING:
        record["temporal_state"] = temporal_state
    return record


class _Client:
    """A lane client whose projection reads back the given (turn, phase, step)."""

    def __init__(self, decisions: list[dict[str, Any]], view: dict[str, Any]) -> None:
        self.decisions = list(decisions)
        self.view = view
        self.submitted: list[list[str]] = []

    def pending_decision(self, attempts: int = 0) -> dict[str, Any] | None:
        return self.decisions[0] if self.decisions else None

    def submit_options(self, decision: dict[str, Any], options: list[str]) -> None:
        self.submitted.append(list(options))
        self.decisions.pop(0)

    def request(self, message: str, payload: Any) -> dict[str, Any]:
        assert message == "get_midgame_projection"
        assert payload == {"actor_id": "P1"}
        return {"success": True, "payload": {"view": self.view}}


def _priority(*, multi: bool, stack: list[str] | None = None, seat: int = 0) -> dict[str, Any]:
    options = [{"option_type": "pass_priority", "option_id": "pass"}]
    if multi:
        options.append({"option_type": "activate_ability", "option_id": "cast-bolt"})
    return {
        "decision_class": "priority",
        "decision_id": f"d-{len(options)}",
        "seat": seat,
        "legal_options": options,
        "pilot_state": {"stack": ["bolt"] if stack is None else stack},
    }


def _frame(step: str, *, turn: int = 1, multi: bool = True) -> _Client:
    return _Client(
        [_priority(multi=multi)],
        {"turn_number": turn, "phase": "precombat_main", "step": step},
    )


def test_a_declared_pass_through_at_the_checkpoint_is_allowed_and_traced() -> None:
    probe = mr.probe_module()
    client = _frame("PRECOMBAT_MAIN")
    authority = probe.PassAuthority(_record())
    probe.declared_pass(client, client.decisions[0], authority, "t")
    assert client.submitted == [["pass"]]
    assert authority.trace == [
        {
            "kind": "priority_pass",
            "actor": "P1",
            "decision_id": "d-2",
            "scope": "decision_script[0]",
            "tag": "t",
        }
    ]


def test_a_declared_pass_through_at_an_earlier_position_in_scope_is_allowed() -> None:
    probe = mr.probe_module()
    # Turn 1's draw step is inside the declared scope and before the checkpoint.
    client = _Client(
        [_priority(multi=True)],
        {"turn_number": 1, "phase": "beginning", "step": "DRAW"},
    )
    authority = probe.PassAuthority(_record())
    probe.declared_pass(client, client.decisions[0], authority, "t")
    assert client.submitted == [["pass"]]
    assert [entry["scope"] for entry in authority.trace] == ["decision_script[0]"]


def test_a_declared_pass_through_at_a_later_step_of_the_same_turn_raises() -> None:
    probe = mr.probe_module()
    client = _frame("POSTCOMBAT_MAIN")
    authority = probe.PassAuthority(_record())
    with pytest.raises(probe.ml.MidgameLaneError) as excinfo:
        probe.declared_pass(client, client.decisions[0], authority, "t")
    message = str(excinfo.value)
    assert "is not at or before the record's own checkpoint" in message
    assert "turn 1 step PRECOMBAT_MAIN" in message  # the bound
    assert "turn 1 step POSTCOMBAT_MAIN" in message  # the observed position
    assert client.submitted == [] and authority.trace == []


def test_a_declared_pass_through_in_a_later_turn_raises() -> None:
    probe = mr.probe_module()
    client = _frame("PRECOMBAT_MAIN", turn=2)
    authority = probe.PassAuthority(_record())
    with pytest.raises(probe.ml.MidgameLaneError) as excinfo:
        probe.declared_pass(client, client.decisions[0], authority, "t")
    message = str(excinfo.value)
    assert "is not at or before the record's own checkpoint" in message
    assert "turn 2 step PRECOMBAT_MAIN" in message  # the observed position
    assert "turn 1 step PRECOMBAT_MAIN" in message  # the bound
    assert client.submitted == [] and authority.trace == []


def test_an_unreadable_temporal_state_fails_closed_and_never_passes() -> None:
    probe = mr.probe_module()
    for temporal_state in (
        MISSING,
        None,
        {},
        {"turn_number": 1},
        {"turn_number": 1, "phase": "pregame", "step": "game_start"},
        {"turn_number": "1", "phase": "precombat_main", "step": "main"},
    ):
        # Even at the checkpoint itself: without a readable record position the
        # Lab cannot prove the pass rebuilds rather than advances.
        client = _frame("PRECOMBAT_MAIN")
        authority = probe.PassAuthority(_record(temporal_state))
        with pytest.raises(probe.ml.MidgameLaneError) as excinfo:
            probe.declared_pass(client, client.decisions[0], authority, "t")
        assert "is not at or before the record's own checkpoint" in str(excinfo.value)
        assert client.submitted == [] and authority.trace == []


def test_a_checkpoint_naming_no_step_spans_the_whole_of_its_phase() -> None:
    probe = mr.probe_module()
    authority = probe.PassAuthority(
        _record({"turn_number": 1, "phase": "precombat_main", "step": None})
    )
    inside = _frame("PRECOMBAT_MAIN")
    probe.declared_pass(inside, inside.decisions[0], authority, "t")
    assert inside.submitted == [["pass"]]
    outside = _frame("POSTCOMBAT_MAIN")
    with pytest.raises(probe.ml.MidgameLaneError, match="is not at or before"):
        probe.declared_pass(outside, outside.decisions[0], authority, "t")
    assert outside.submitted == []


def test_a_single_option_frame_after_the_checkpoint_still_passes() -> None:
    probe = mr.probe_module()
    # No choice is offered, so the record's checkpoint cannot bound the answer.
    for view in (
        {"turn_number": 1, "phase": "precombat_main", "step": "CLEANUP"},
        {"turn_number": 7, "phase": "postcombat_main", "step": "END_TURN"},
    ):
        client = _Client([_priority(multi=False)], view)
        authority = probe.PassAuthority(_record())
        probe.declared_pass(client, client.decisions[0], authority, "t")
        assert client.submitted == [["pass"]]
        assert [entry["scope"] for entry in authority.trace] == ["single_option"]


def test_the_causal_stack_helper_carries_the_bound() -> None:
    probe = mr.probe_module()
    later = _Client(
        [_priority(multi=True), _priority(multi=True, stack=[])],
        {"turn_number": 1, "phase": "precombat_main", "step": "POSTCOMBAT_MAIN"},
    )
    authority = probe.PassAuthority(_record())
    with pytest.raises(probe.ml.MidgameLaneError, match="is not at or before"):
        probe.resolve_stack(later, "t", authority)
    assert later.submitted == [] and authority.trace == []
    # The same helper at the checkpoint passes and names its declaring step.
    at_checkpoint = _Client(
        [_priority(multi=True), _priority(multi=True, stack=[])],
        {"turn_number": 1, "phase": "precombat_main", "step": "PRECOMBAT_MAIN"},
    )
    authority = probe.PassAuthority(_record())
    probe.resolve_stack(at_checkpoint, "t", authority)
    assert at_checkpoint.submitted == [["pass"]]
    assert [entry["scope"] for entry in authority.trace] == ["decision_script[0]"]


def test_the_obligation_scope_semantics_are_unchanged_by_the_causal_bound() -> None:
    # The lane's own obligation loop and the arrival context evaluate
    # ``_priority_pass_through_scope`` directly and are not narrowed here: a
    # position after the record's checkpoint is still inside a declared
    # ``OBLIGATION_COMPLETE`` scope.
    probe = mr.probe_module()
    record = _record()
    later = {"turn_number": 4, "phase": "combat", "step": "COMBAT_DAMAGE"}
    assert probe._priority_pass_through_scope(record, "P1", later, obligation=True) == 0
    assert probe._priority_pass_through_scope(record, "P1", later, obligation=False) is None
    assert probe._scripted_priority_pass_through(record, "P1", later, obligation=True) is True
