"""P2-1 controls: the knowledge transport's capture point and pass-through scope.

The #643 review P2-1: the obligation pass-through is a standing declaration,
not a cursor step. It may answer only priority frames whose engine-observed
(turn, step) lie inside its declared ``[scope.from, scope.until)`` window, and
only after every pending scripted step has had its own frame (the record's
``SCRIPTED_STEPS_FIRST`` precedence). The knowledge projection capture happens
at the record's own declared capture point (``temporal_state``), never at
"wherever the pass-through stops".

Each control is a red control: the mutation of one assumption must fail closed.
"""

from __future__ import annotations

import copy

import pytest

from commander_lab.qualification.current_boundary import knowledge_projection
from commander_lab.qualification.current_boundary.midgame_lane import MidgameLaneError

_CAPTURE = {"turn_number": 1, "phase": "precombat_main", "step": "main"}


def _pass_through_scope() -> dict:
    return {
        "from": {"turn": 1, "phase": "precombat_main", "step": "main"},
        "until": {"turn": 1, "phase": "ending"},
    }


def _pass_through_step() -> dict:
    return {
        "actor": "ALL",
        "causal_step_id": "priority-pass-obligation-t-capture",
        "decision_family": "priority_pass_through",
        "precedence": "SCRIPTED_STEPS_FIRST",
        "scope": _pass_through_scope(),
        "selection": {
            "matches_only_provider_offered_legal_options": True,
            "on_multiple_match": "FAIL_CLOSED",
            "on_zero_match": "FAIL_CLOSED",
            "selector_kind": "semantic_action",
            "semantic_value": "pass_priority",
        },
    }


def _record(script: list[dict], *, capture: dict | None = None) -> dict:
    point = dict(_CAPTURE if capture is None else capture)
    return {
        "fixture_id": "T_CAPTURE",
        "decision_script": copy.deepcopy(script),
        "temporal_state": {
            "priority_player": "P1",
            "turn_number": point["turn_number"],
            "phase": point["phase"],
            "step": point["step"],
        },
        "action_cost_state": [],
    }


class _PriorityClient:
    """A minimal priority-frame transport: one standing P1 frame per call."""

    def __init__(
        self,
        observation: dict,
        *,
        seat: int = 0,
        stack: list | None = None,
        actions: list[dict] | None = None,
        placed: dict[str, str] | None = None,
    ) -> None:
        self.tape = [
            {
                "message_type": "create_midgame_game",
                "response": {"payload": {"placed_objects": placed or {}, "commander_objects": {}}},
            }
        ]
        self.observation = dict(observation)
        self.seat = seat
        self.stack = list(stack or [])
        self.actions = list(actions or [])
        self.proposals: list[dict] = []
        self.passes: list[list[str]] = []

    def pending_decision(self, attempts: int = 1, interval_s: float = 0.0) -> dict:
        return {
            "decision_class": "priority",
            "seat": self.seat,
            "legal_options": [{"option_id": "pass-1", "option_type": "pass_priority"}],
            "pilot_state": {"stack": list(self.stack)},
        }

    def complete_arrival(self) -> dict:
        return {"observation": dict(self.observation)}

    def submit_options(self, decision: dict, option_ids: list[str]) -> dict:
        self.passes.append(list(option_ids))
        return {}

    def request(self, message_type: str, payload) -> dict:
        if message_type == "get_legal_actions":
            return {"success": True, "payload": {"actor_id": "native-P1", "actions": self.actions}}
        if message_type == "complete_midgame_arrival":
            return {"success": True, "payload": {"observation": dict(self.observation)}}
        if message_type == "submit_action":
            self.proposals.append(payload)
            return {"success": True, "payload": {}}
        if message_type == "submit_midgame_decision":
            self.passes.append(list((payload or {}).get("selected_option_ids") or ()))
            return {"success": True, "payload": {}}
        raise AssertionError(f"unexpected request {message_type}")


def _activation_step(actor: str = "P1") -> dict:
    return {
        "actor": actor,
        "causal_step_id": "scripted-activation",
        "decision_family": "priority",
        "selection": {
            "matches_only_provider_offered_legal_options": True,
            "on_multiple_match": "FAIL_CLOSED",
            "on_zero_match": "FAIL_CLOSED",
            "selector_kind": "semantic_action",
            "semantic_value": {"action": "activate", "object": "obj:source"},
        },
    }


_ACTIVATION_OFFER = {
    "action_id": "activate-1",
    "action_type": "activate_ability",
    "metadata": {"xmage_option_metadata": {"source_object_id": "native-source"}},
}


def test_red_control_a_pass_through_before_a_scripted_step_cannot_consume_its_frame() -> None:
    """The declaration is skipped by the cursor: the scripted activation answers
    the frame, never the pass-through that merely sits before it."""
    record = _record([_pass_through_step(), _activation_step()])
    client = _PriorityClient(
        {"turn_number": 1, "phase": "precombat_main", "step": "PRECOMBAT_MAIN"},
        actions=[_ACTIVATION_OFFER],
        placed={"obj:source": "native-source"},
    )
    trace = knowledge_projection.run_script(client, record)
    assert trace == [{"decision_class": "priority", "step": 1, "tape_index": 1}]
    assert client.passes == []
    assert [payload["proposal"]["action_type"] for payload in client.proposals] == [
        "activate_ability"
    ]


def test_red_control_a_frame_outside_the_declared_scope_fails_closed() -> None:
    """A priority frame whose engine point is outside every declared scope is
    never passed by the Lab, even while a scripted step is pending."""
    record = _record([_activation_step("P2"), _pass_through_step()])
    client = _PriorityClient(
        {"turn_number": 2, "phase": "precombat_main", "step": "PRECOMBAT_MAIN"}
    )
    with pytest.raises(MidgameLaneError, match="outside the record's declared pass-through scope"):
        knowledge_projection.run_script(client, record)
    assert client.passes == []
    assert client.proposals == []


def test_red_control_the_capture_point_is_the_declared_one() -> None:
    """The event completes only where the record declares; an engine parked at
    another step fails closed instead of capturing there."""
    record = _record([])
    at_capture = _PriorityClient(
        {"turn_number": 1, "phase": "precombat_main", "step": "PRECOMBAT_MAIN"}
    )
    assert knowledge_projection.run_script(at_capture, record) == []
    away = _PriorityClient(
        {"turn_number": 1, "phase": "postcombat_main", "step": "POSTCOMBAT_MAIN"}
    )
    with pytest.raises(MidgameLaneError, match="away from the record's declared capture point"):
        knowledge_projection.run_script(away, record)
    assert away.passes == []
