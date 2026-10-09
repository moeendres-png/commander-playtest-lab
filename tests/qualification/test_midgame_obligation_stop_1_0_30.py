"""#643 regression-repair red control: the obligation declaration never drives
the midgame row forward.

The 1.0.30 erratum appends a declaration-only obligation ``priority_pass_through``
(and, for the knowledge rows, an empty attack set) after the record's own steps.
Before the repair, the obligation loop's cursor stalled on that trailing
declaration, so the row never reached its pre-1.0.30 natural stop and ran into
combat, where an undeclared ``declare_attacker`` stopped it unverified.

The fake client below offers the record's own typed refusal frame and then an
attacker frame. The row must stop at its natural point ("obligation observed")
without ever fetching or answering the attacker frame; the mutation (removing
the declaration-only cursor skip) stops it unverified on the attacker.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from commander_lab.qualification.current_boundary import midgame_rows as mr
from commander_lab.qualification.current_boundary.materialization import (
    load_effective_materialization,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_FIXTURE = "NEGATIVE_DEFAULT_YES_NO"


def _record() -> dict[str, Any]:
    record = copy.deepcopy(load_effective_materialization(REPO_ROOT).record(BASE_FIXTURE))
    record["fixture_id"] = "T_OBLIGATION_STOP"
    script = record["decision_script"]
    keep = [step for step in script if step.get("decision_family") == "mulligan"]
    arrival = next(
        step
        for step in script
        if step.get("decision_family") == "priority_pass_through" and step.get("precedence") is None
    )
    probe = next(
        step
        for step in script
        if (step.get("selection") or {}).get("selector_kind") == "fail_closed_probe"
    )
    obligation = next(
        step
        for step in script
        if step.get("decision_family") == "priority_pass_through"
        and step.get("precedence") == "SCRIPTED_STEPS_FIRST"
    )
    record["decision_script"] = [*keep, arrival, probe, obligation]
    return record


class _FakeClient:
    """The record's own refusal frame, then an undeclared attacker frame."""

    def __init__(self) -> None:
        self.tape: list[dict[str, Any]] = []
        self.engine_commit = "e" * 40
        self.submissions: list[list[str]] = []
        self.attacker_fetched = False
        self._decisions: list[dict[str, Any]] = [
            {
                "decision_id": f"d-mull-{seat}",
                "decision_class": "mulligan",
                "actor_id": f"actor-{seat}",
                "seat": seat,
                "legal_options": [{"option_id": f"keep-{seat}", "option_type": "keep"}],
            }
            for seat in range(4)
        ]
        self._decisions.append(
            {
                "decision_id": "d-probe",
                "decision_class": "choose_use",
                "actor_id": "actor-0",
                "seat": 0,
                "legal_options": [{"option_id": "probe-0", "option_type": "choose_use"}],
            }
        )
        self._decisions.append(
            {
                "decision_id": "d-atk",
                "decision_class": "declare_attacker",
                "actor_id": "actor-0",
                "seat": 0,
                "legal_options": [{"option_id": "hold", "option_type": "hold_attacker"}],
            }
        )

    def pending_decision(self, attempts: int = 1, interval_s: float = 0.0) -> dict[str, Any] | None:
        if not self._decisions:
            return None
        pending = self._decisions[0]
        if pending.get("decision_id") == "d-atk":
            self.attacker_fetched = True
        return pending

    def events(self, after_offset: int = 0) -> dict[str, Any]:
        return {"latest_offset": 0, "events": []}

    def complete_arrival(self) -> dict[str, Any]:
        return {
            "construction_match": True,
            "mismatches": [],
            "observation": {
                "turn_number": 1,
                "phase": "PRECOMBAT_MAIN",
                "step": "PRECOMBAT_MAIN",
                "priority_player": "P1",
            },
        }

    def request(self, message_type: str, payload: Any = None) -> dict[str, Any]:
        if message_type == "get_legal_actions":
            seat = self._decisions[0].get("seat", 0) if self._decisions else 0
            return {
                "success": True,
                "payload": {
                    "actor_id": f"actor-{seat}",
                    "actions": [
                        {
                            "action_id": "probe-0",
                            "action_type": "choose_use",
                            "metadata": {
                                "option_id": "probe-0",
                                "seat": seat,
                            },
                        }
                    ],
                },
            }
        raise AssertionError(f"unexpected lane request {message_type}")

    def submit_options(self, decision: dict[str, Any], option_ids: list[str]) -> None:
        assert decision.get("decision_class") == "mulligan", (
            "the declared refusal and the undeclared attacker frame must never be answered"
        )
        self.submissions.append(list(option_ids))
        self._decisions.pop(0)


def test_red_control_the_obligation_declaration_never_extends_the_row() -> None:
    client = _FakeClient()
    execution = mr.execute_row(client, _record(), {}, mr.RowSpec())
    assert execution.verified, execution.detail
    assert execution.detail == "obligation observed"
    assert not client.attacker_fetched, (
        "the row must stop at its natural point, before the undeclared attacker frame"
    )
    assert client.submissions == [["keep-0"], ["keep-1"], ["keep-2"], ["keep-3"]]
