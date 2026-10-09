"""Contract 1.0.30 step A2: the knowledge lane's declared empty attack sets.

The #634 Coordinator ruling (2026-10-09, step A2): every knowledge-projection
record whose obligation window reaches the checkpoint turn's declare-attackers
step declares the active player's attack declaration as an explicit empty
attack set (CR 508.1, 508.8), bound to the record's own active player and the
engine's DECLARE_ATTACKERS step. The knowledge lane's transport answers each
engine declare-attacker frame with the engine's own hold offer; a frame the
record does not declare still fails closed (red control).
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

from commander_lab.qualification.current_boundary import knowledge_projection, midgame_rows
from commander_lab.qualification.current_boundary.midgame_lane import MidgameLaneError

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The engine's own turn order: a checkpoint at or before
#: DECLARE_ATTACKERS has that step inside its obligation window.
_ENGINE_POINT_ORDER = (
    ("beginning", "upkeep"),
    ("beginning", "draw"),
    ("precombat_main", "main"),
    ("combat", "declare_attackers"),
    ("combat", "declare_blockers"),
    ("combat", "combat_damage"),
    ("postcombat_main", "main"),
)
_DECLARE_ATTACKERS_POINT = ("combat", "declare_attackers")


def _resolver():
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import resolve_pre_freeze_contract as resolver

    return resolver


def _records() -> dict[str, dict]:
    return {
        record["fixture_id"]: record
        for record in _resolver().load_effective_materialization()["records"]
    }


def _obligation_step(record: dict) -> dict | None:
    for step in record.get("decision_script") or ():
        if str(step.get("causal_step_id") or "").startswith("priority-pass-obligation-"):
            return step
    return None


def _window_includes_declare_attackers(record: dict) -> bool:
    obligation = _obligation_step(record)
    assert obligation is not None, record.get("fixture_id")
    start = (obligation.get("scope") or {}).get("from") or {}
    point = (str(start.get("phase") or "").lower(), str(start.get("step") or "").lower())
    assert point in _ENGINE_POINT_ORDER, point
    return _ENGINE_POINT_ORDER.index(point) <= _ENGINE_POINT_ORDER.index(_DECLARE_ATTACKERS_POINT)


def _attack_declarations(record: dict) -> list[dict]:
    return [
        step
        for step in record.get("decision_script") or ()
        if isinstance(step, dict) and step.get("decision_family") == "declare_attackers"
    ]


def _declaration_problems(record: dict) -> list[str]:
    temporal = record.get("temporal_state") or {}
    declarations = _attack_declarations(record)
    if len(declarations) != 1:
        return [f"{len(declarations)} declare_attackers step(s)"]
    step = declarations[0]
    selection = step.get("selection") or {}
    problems: list[str] = []
    if step.get("actor") != temporal.get("active_player"):
        problems.append(f"actor {step.get('actor')!r} is not the active player")
    if step.get("turn") != temporal.get("turn_number"):
        problems.append(f"turn {step.get('turn')!r} is not the checkpoint turn")
    if str(step.get("phase") or "").upper() != "DECLARE_ATTACKERS":
        problems.append(f"phase {step.get('phase')!r} is not DECLARE_ATTACKERS")
    if selection.get("selector_kind") != "attacker_assignment":
        problems.append("the selector is not attacker_assignment")
    if selection.get("semantic_value") != {}:
        problems.append("the attack set is not the explicit empty set")
    if selection.get("matches_only_provider_offered_legal_options") is not True:
        problems.append("the step is not bound to provider-offered options")
    if selection.get("on_multiple_match") != "FAIL_CLOSED":
        problems.append("on_multiple_match is not FAIL_CLOSED")
    if selection.get("on_zero_match") != "FAIL_CLOSED":
        problems.append("on_zero_match is not FAIL_CLOSED")
    return problems


def test_every_knowledge_window_reaching_combat_declares_the_empty_attack_set() -> None:
    """Ruling 5: every knowledge record whose obligation window includes the
    checkpoint turn's declare-attackers step declares its empty attack set."""
    records = _records()
    expected: list[str] = []
    for fixture_id in knowledge_projection.ROWS:
        record = records[fixture_id]
        if _window_includes_declare_attackers(record):
            expected.append(fixture_id)
            assert _declaration_problems(record) == [], fixture_id
        else:
            assert _attack_declarations(record) == [], fixture_id
    # Every knowledge row's checkpoint is turn 1 precombat main (the 19
    # HIDDEN_* rows and the sentinel), so every window reaches the step.
    assert expected == list(knowledge_projection.ROWS)
    assert len(expected) == 20


def test_red_control_an_undeclared_or_mismatched_attack_frame_is_unscripted() -> None:
    """The declaration is identity-bound: only the declared actor, turn and
    step match; a record without it has no answer (the transport raises)."""
    records = _records()
    probe = midgame_rows.probe_module()
    for fixture_id in knowledge_projection.ROWS:
        record = records[fixture_id]
        temporal = record.get("temporal_state") or {}
        declared = {
            "turn_number": temporal["turn_number"],
            "phase": "combat",
            "step": "DECLARE_ATTACKERS",
        }
        actor = str(temporal["active_player"])
        assert probe._scripted_empty_declare_attackers(record, actor, declared) is not None
        # An opponent's attack frame is not the declared actor's.
        assert probe._scripted_empty_declare_attackers(record, "P9", declared) is None
        # A frame in another turn is outside the declaration's binding.
        other_turn = {**declared, "turn_number": int(temporal["turn_number"]) + 1}
        assert probe._scripted_empty_declare_attackers(record, actor, other_turn) is None
        # A frame at another step is not the declared step.
        other_step = {**declared, "step": "PRECOMBAT_MAIN"}
        assert probe._scripted_empty_declare_attackers(record, actor, other_step) is None
        # Without the declaration the same frame has no answer at all.
        mutated = copy.deepcopy(record)
        mutated["decision_script"] = [
            step
            for step in mutated["decision_script"]
            if step.get("decision_family") != "declare_attackers"
        ]
        assert probe._scripted_empty_declare_attackers(mutated, actor, declared) is None


_DECLARE_ATTACKERS_STEP = {
    "actor": "P1",
    "causal_step_id": "declare-attackers-r1-p1",
    "decision_family": "declare_attackers",
    "phase": "DECLARE_ATTACKERS",
    "selection": {
        "matches_only_provider_offered_legal_options": True,
        "on_multiple_match": "FAIL_CLOSED",
        "on_zero_match": "FAIL_CLOSED",
        "selector_kind": "attacker_assignment",
        "semantic_value": {},
    },
    "turn": 1,
}


class _AttackFrameClient:
    """The minimal transport surface run_script touches on attack frames.

    The engine frame is one ``declare_attacker`` decision for P1's sole
    creature; after the hold is submitted the readback moves past the
    declared attack step, exactly as the live engine's own progression does.
    """

    def __init__(self) -> None:
        self.tape = [
            {
                "message_type": "create_midgame_game",
                "response": {
                    "payload": {"placed_objects": {}, "commander_objects": {}},
                },
            }
        ]
        self.observation: dict = {
            "turn_number": 1,
            "phase": "combat",
            "step": "DECLARE_ATTACKERS",
        }
        self.attack_frames = 0
        self.submissions: list[dict] = []

    def pending_decision(self, attempts: int = 1, interval_s: float = 0.0) -> dict:
        if self.attack_frames == 0:
            return {"decision_class": "declare_attacker", "seat": 0, "legal_options": []}
        return {
            "decision_class": "priority",
            "seat": 0,
            "legal_options": [{"option_id": "pass-1", "option_type": "pass_priority"}],
            "pilot_state": {"stack": []},
        }

    def complete_arrival(self) -> dict:
        return {"observation": dict(self.observation)}

    def request(self, message_type: str, payload) -> dict:
        if message_type == "get_legal_actions":
            if self.attack_frames == 0:
                return {
                    "success": True,
                    "payload": {
                        "actor_id": "native-P1",
                        "actions": [
                            {
                                "action_id": "hold-1",
                                "action_type": "hold_attacker",
                                "metadata": {
                                    "option_type": "hold_attacker",
                                    "xmage_option_metadata": {"object_id": "creature-1"},
                                },
                            }
                        ],
                    },
                }
            return {
                "success": True,
                "payload": {
                    "actor_id": "native-P1",
                    "actions": [{"action_id": "pass-1", "action_type": "priority", "metadata": {}}],
                },
            }
        if message_type == "complete_midgame_arrival":
            return {"success": True, "payload": {"observation": dict(self.observation)}}
        if message_type == "submit_action":
            self.submissions.append(payload)
            self.attack_frames += 1
            self.observation = {
                "turn_number": 1,
                "phase": "postcombat_main",
                "step": "POSTCOMBAT_MAIN",
            }
            return {"success": True, "payload": {}}
        raise AssertionError(f"unexpected request {message_type}")


def _transport_record(step: dict | None) -> dict:
    return {
        "fixture_id": "T_A2",
        "decision_script": [copy.deepcopy(step)] if step is not None else [],
        "temporal_state": {"priority_player": "P1", "turn_number": 1},
        "action_cost_state": [],
    }


def test_the_transport_answers_the_declared_empty_attack_set_with_the_hold() -> None:
    client = _AttackFrameClient()
    trace = knowledge_projection.run_script(client, _transport_record(_DECLARE_ATTACKERS_STEP))
    assert trace == [{"decision_class": "declare_attacker", "step": 0}]
    assert client.submissions == [
        {
            "proposal": {
                "proposal_id": "knowledge-0",
                "actor_id": "native-P1",
                "legal_action_id": "hold-1",
                "action_type": "hold_attacker",
                "target_ids": [],
                "selected_modes": [],
                "choices": {"ordering": []},
                "decision_tier": 1,
                "policy_name": "midgame-causal-external-pilot",
            }
        }
    ]


def test_red_control_an_undeclared_attack_frame_still_fails_closed() -> None:
    client = _AttackFrameClient()
    with pytest.raises(MidgameLaneError, match="unscripted declare_attacker for P1"):
        knowledge_projection.run_script(client, _transport_record(None))
    assert client.submissions == []
