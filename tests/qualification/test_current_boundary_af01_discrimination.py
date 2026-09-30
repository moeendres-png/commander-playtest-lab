"""AF01 decision-time probes must discriminate (F-37).

The sealed AF01 artifacts credited ``fail_closed_illegal_action``,
``fail_closed_stale_or_unknown_decision`` and (for Forge)
``fail_closed_unsupported_decision`` as PASS, although every probe request was
malformed: no proposal object, no actor. Both candidates rejected them for that
unrelated reason. These tests drive ``run_af01`` against scripted providers and
pin that only a well-formed, single-defect probe that is rejected without
mutation earns PASS.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from commander_lab.qualification.current_boundary.af01 import run_af01

DECISION_TIME = (
    "fail_closed_illegal_action",
    "fail_closed_stale_or_unknown_decision",
    "fail_closed_unsupported_decision",
    "rules_core_sole_legality_authority",
)


class ScriptedProvider:
    """A Protocol-2 XMage-shaped provider with one parked priority decision."""

    def __init__(self, behaviour: str) -> None:
        self.behaviour = behaviour
        self.decision_id = "a" * 64
        self.transcript: list[dict[str, Any]] = []
        self.plan = SimpleNamespace(lane="scripted-generic-lane")

    def _ok(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"success": True, "status": "ok", "protocol_version": "2.0.0", "payload": payload}

    def _error(self, code: str) -> dict[str, Any]:
        return {
            "success": False,
            "status": "error",
            "protocol_version": "2.0.0",
            "errors": [{"code": code, "message": code, "retryable": False}],
        }

    def _frame(self) -> dict[str, Any]:
        return self._ok(
            {
                "decision_kind": "priority",
                "actor_id": "p1",
                "decision_id": self.decision_id,
                "decision_offset": 4,
                "complete": True,
                "actions": [{"action_id": "pass-1", "action_type": "pass_priority"}],
            }
        )

    def request(
        self,
        message_type: str,
        params: dict[str, Any] | None = None,
        *,
        game_id: str | None = None,
        protocol_version: str = "2.0.0",
        request_id: str | None = None,
        timeout_s: float = 0.0,
    ) -> dict[str, Any]:
        params = params or {}
        if protocol_version != "2.0.0":
            return self._error("protocol_mismatch")
        if message_type in {"start_engine", "get_provider_version", "get_capabilities"}:
            response = self._ok({"provider": "xmage", "engine_commit": "e" * 40})
            response["request_id"] = request_id
            return response
        if message_type == "get_legal_actions":
            if "decision_class" in params:
                if self.behaviour == "malformed":
                    return self._error("malformed_request")
                if self.behaviour == "lenient":
                    return self._frame()
                return self._error("unsupported_decision_class")
            return self._frame()
        if message_type == "submit_action":
            if self.behaviour == "malformed" or "proposal" not in params:
                return self._error("malformed_request")
            if params.get("decision_id") != self.decision_id:
                return self._error("stale_decision")
            if self.behaviour == "mutating":
                self.decision_id = "b" * 64
            return self._error("illegal_action")
        return self._error("unknown_message")


def _verdicts(behaviour: str) -> dict[str, str]:
    report = run_af01(
        ScriptedProvider(behaviour),  # type: ignore[arg-type]
        candidate="xmage",
        expected_commit="e" * 40,
        runner_commit="b" * 40,
        runner_tree="c" * 40,
        game_id="af01-probe",
        seat_count=1,
    )
    return {result.name: result.verdict for result in report.invariants}


def test_a_strict_provider_passes_every_decision_time_probe() -> None:
    verdicts = _verdicts("strict")
    assert {name: verdicts[name] for name in DECISION_TIME} == dict.fromkeys(DECISION_TIME, "PASS")


def test_malformed_request_rejections_are_not_credited() -> None:
    verdicts = _verdicts("malformed")
    for name in DECISION_TIME:
        assert verdicts[name] == "UNKNOWN", (name, verdicts[name])


def test_serving_an_unsupported_decision_class_fails() -> None:
    verdicts = _verdicts("lenient")
    assert verdicts["fail_closed_unsupported_decision"] == "FAIL"
    assert verdicts["fail_closed_illegal_action"] == "PASS"


@pytest.mark.parametrize("name", ["fail_closed_illegal_action"])
def test_a_rejection_that_still_mutates_the_game_fails(name: str) -> None:
    assert _verdicts("mutating")[name] == "FAIL"
