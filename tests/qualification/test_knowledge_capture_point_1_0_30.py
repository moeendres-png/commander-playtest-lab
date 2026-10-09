"""#643 regression-repair controls: the knowledge transport's capture point.

The A3 binding to ``temporal_state`` moved the capture ahead of the record's own
scripted obligation events (the PB-03 AF05 regression). The restored capture
point is the pre-1.0.30 point the epoch ff688b58 qualified: the first
empty-stack priority of the checkpoint's priority player after every scripted
step has been answered. The obligation pass-through is a standing declaration,
not a cursor step: it may answer only priority frames inside its declared scope
(a temporal ``[scope.from, scope.until)`` window or the symbolic
``{"event": "OBLIGATION_COMPLETE"}`` obligation bound), and it never transits
past the capture point.

Each control is a red control: the mutation of one assumption must fail closed.
"""

from __future__ import annotations

import copy

import pytest

from commander_lab.qualification.current_boundary import knowledge_projection
from commander_lab.qualification.current_boundary.midgame_lane import MidgameLaneError

_CAPTURE = {"turn_number": 1, "phase": "precombat_main", "step": "main"}


def _pass_through_step(*, symbolic: bool = True) -> dict:
    until = {"event": "OBLIGATION_COMPLETE"} if symbolic else {"turn": 1, "phase": "ending"}
    return {
        "actor": "ALL",
        "causal_step_id": "priority-pass-obligation-t-capture",
        "decision_family": "priority_pass_through",
        "precedence": "SCRIPTED_STEPS_FIRST",
        "scope": {
            "from": {"turn": 1, "phase": "precombat_main", "step": "main"},
            "until": until,
        },
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
        self.projection_requests: list[dict] = []
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

    def submit_options(self, decision: dict, option_ids: list[str]) -> dict:
        self.passes.append(list(option_ids))
        return {}

    def request(self, message_type: str, payload) -> dict:
        if message_type == "get_legal_actions":
            return {"success": True, "payload": {"actor_id": "native-P1", "actions": self.actions}}
        if message_type == "get_midgame_projection":
            self.projection_requests.append(dict(payload or {}))
            return {"success": True, "payload": {"view": dict(self.observation)}}
        if message_type == "complete_midgame_arrival":
            # The construction compare names hidden objects once the event
            # has begun: the scripted event never reads it (AF05).
            raise AssertionError("the scripted event requested complete_midgame_arrival")
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
    """A priority frame whose engine point is outside the declared scope is
    never passed by the Lab, even while a scripted step is pending."""
    record = _record([_activation_step("P2"), _pass_through_step(symbolic=False)])
    client = _PriorityClient(
        {"turn_number": 2, "phase": "precombat_main", "step": "PRECOMBAT_MAIN"}
    )
    with pytest.raises(MidgameLaneError, match="outside the record's declared pass-through scope"):
        knowledge_projection.run_script(client, record)
    assert client.passes == []
    assert client.proposals == []


def test_red_control_capture_follows_the_last_scripted_step() -> None:
    """The capture is the first empty-stack holder priority AFTER the record's
    scripted steps: the scripted activation is answered first, then the holder
    frame captures. A pass-through transit past that point would submit a pass
    (and loop until the bound) instead of returning the trace."""
    record = _record([_activation_step(), _pass_through_step()])
    client = _PriorityClient(
        {"turn_number": 1, "phase": "precombat_main", "step": "PRECOMBAT_MAIN"},
        actions=[_ACTIVATION_OFFER],
        placed={"obj:source": "native-source"},
    )
    trace = knowledge_projection.run_script(client, record)
    assert trace == [{"decision_class": "priority", "step": 0, "tape_index": 1}]
    # The capture frame itself was never passed by the declaration.
    assert client.passes == []
    assert [payload["proposal"]["action_type"] for payload in client.proposals] == [
        "activate_ability"
    ]


def test_red_control_a_symbolic_scope_never_authorizes_before_its_from() -> None:
    """The obligation declaration's symbolic bound still enforces ``scope.from``:
    a frame before the checkpoint fails closed instead of being passed."""
    record = _record([_activation_step("P2"), _pass_through_step()])
    client = _PriorityClient({"turn_number": 1, "phase": "beginning", "step": "UPKEEP"})
    with pytest.raises(MidgameLaneError, match="outside the record's declared pass-through scope"):
        knowledge_projection.run_script(client, record)
    assert client.passes == []
