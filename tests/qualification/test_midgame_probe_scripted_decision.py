"""The causal-stack terminal credits only the row's own scripted decision.

After the stack is rebuilt causally, ``observe_scripted_decision`` passes
priority through engine-offered passes until the engine asks a non-priority
decision (or the scripted actor holds priority for a scripted cast). It is
observed only if the engine's decision class equals the scripted family
exactly, the scripted actor is asked, and exactly one engine offer matches the
scripted selection. These tests drive it against recorded frames.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

PROBE = Path(__file__).resolve().parents[2] / "scripts" / "run_midgame_capability_probe.py"


@pytest.fixture(scope="module")
def probe() -> Any:
    spec = importlib.util.spec_from_file_location("midgame_probe_under_test", PROBE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _priority(seat: int) -> tuple[dict[str, Any], dict[str, Any]]:
    decision = {
        "decision_class": "priority",
        "seat": seat,
        "legal_options": [{"option_id": f"pass-{seat}", "option_type": "pass_priority"}],
    }
    return decision, {"actions": [{"action_id": f"pass-{seat}", "metadata": {"seat": seat}}]}


def _frame(
    decision_class: str, seat: int, actions: list[dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any]]:
    return {"decision_class": decision_class, "seat": seat}, {"actions": actions}


class RecordedEngine:
    """Serves recorded (decision, legal actions) frames; a pass advances."""

    def __init__(self, frames: list[tuple[dict[str, Any], dict[str, Any]]]) -> None:
        self.frames = frames
        self.submitted: list[str] = []

    def pending_decision(self, *, attempts: int = 60) -> dict[str, Any] | None:
        return self.frames[0][0] if self.frames else None

    def request(self, message_type: str, params: Any, **_: Any) -> dict[str, Any]:
        assert message_type == "get_legal_actions"
        return {"success": True, "payload": self.frames[0][1]}

    def submit_options(self, decision: dict[str, Any], option_ids: list[str]) -> dict[str, Any]:
        self.submitted.extend(option_ids)
        self.frames.pop(0)
        return {}


def _record(actor: str, family: str, value: Any) -> dict[str, Any]:
    return {
        "decision_script": [
            {"actor": actor, "decision_family": family, "selection": {"semantic_value": value}}
        ]
    }


def _offer(native_id: str) -> dict[str, Any]:
    return {"action_id": native_id, "metadata": {"xmage_option_metadata": {"object_id": native_id}}}


def test_the_scripted_object_choice_after_engine_passes_is_observed(probe: Any) -> None:
    engine = RecordedEngine(
        [_priority(1), _priority(0), _frame("choose_object", 0, [_offer("n-a"), _offer("n-b")])]
    )
    terminal = probe.observe_scripted_decision(
        engine, "t", _record("P1", "choose_object", "obj:a"), {"obj:a": "n-a"}
    )
    assert terminal["observed"] is True
    assert engine.submitted == ["pass-1", "pass-0"]


def test_a_different_engine_class_is_reported_not_aliased(probe: Any) -> None:
    boolean = [{"action_id": "y", "metadata": {"xmage_option_metadata": {"value": True}}}]
    engine = RecordedEngine([_frame("choose_use", 0, boolean)])
    terminal = probe.observe_scripted_decision(
        engine, "t", _record("P1", "replacement_effect", True), {}
    )
    assert terminal["observed"] is False
    assert "replacement_effect:P1" in terminal["detail"]
    assert "choose_use:P1" in terminal["detail"]


def test_the_scripted_decision_asked_of_another_player_is_not_observed(probe: Any) -> None:
    engine = RecordedEngine([_frame("choose_object", 3, [_offer("n-a")])])
    terminal = probe.observe_scripted_decision(
        engine, "t", _record("P2", "choose_object", "obj:a"), {"obj:a": "n-a"}
    )
    assert terminal["observed"] is False
    assert "choose_object:P4" in terminal["detail"]


def test_an_ambiguous_choice_fails_closed(probe: Any) -> None:
    labels = [
        {"action_id": str(i), "metadata": {"label": label}}
        for i, label in enumerate(["Red", "red"])
    ]
    engine = RecordedEngine([_frame("choice", 0, labels)])
    terminal = probe.observe_scripted_decision(engine, "t", _record("P1", "choice", "RED"), {})
    assert terminal["observed"] is False


def test_the_scripted_caster_holding_priority_is_never_passed(probe: Any) -> None:
    cast = {
        "action_id": "cast",
        "metadata": {
            "seat": 0,
            "xmage_option_metadata": {"source_object_id": "n-spell", "ability_type": "spell"},
        },
    }
    decision, _ = _priority(0)
    engine = RecordedEngine([_priority(1), (decision, {"actions": [cast]})])
    terminal = probe.observe_scripted_decision(
        engine,
        "t",
        _record("P1", "priority", {"action": "cast", "object": "obj:spell"}),
        {"obj:spell": "n-spell"},
    )
    assert terminal["observed"] is True
    assert engine.submitted == ["pass-1"]
