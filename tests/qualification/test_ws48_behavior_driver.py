"""Driver-core tests against a fake B1-style provider (no engine needed)."""

from __future__ import annotations

import importlib.util
import os
import stat
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MOD = REPO / "candidate-qualification/ws48-forge-v1.0.5/behavior_driver.py"


def _load():
    spec = importlib.util.spec_from_file_location("ws48_behavior_driver", MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


drv = _load()

FAKE = """#!/usr/bin/env python3
import json,sys
def emit(m): sys.stdout.write(json.dumps(m,separators=(",",":"))+"\\n"); sys.stdout.flush()
def frame(did,kind,actor,options):
    return {"protocol":"P","message_type":"DECISION_FRAME","request_id":did,
            "session_id":"s1","actor_id":actor,
            "payload":{"decision_id":did,"decision_kind":kind,
                        "options":[{"option_id":o,"kind":k} for o,k in options]}}
def state(stage,stack):
    return {"protocol":"P","message_type":"QUALIFICATION_STATE","request_id":stage,
            "session_id":"s1","payload":{"stage":stage,"raw_native":{"cards":[],"stack":stack}}}
def event(name):
    return {"protocol":"P","message_type":"EVENT","request_id":"e",
            "session_id":"s1","payload":{"name":name}}
def read_submit():
    line=sys.stdin.readline(); m=json.loads(line)
    assert m["message_type"]=="SUBMIT_DECISION", m
    return m["payload"]["option_id"]
def main():
    line=sys.stdin.readline(); m=json.loads(line)
    assert m["message_type"]=="CREATE_SESSION", m
    emit({"protocol":"P","message_type":"SESSION_CREATED","request_id":"c",
          "session_id":"s1","payload":{"snapshot":{}}})
    emit(state("after_native_setup_validation",[]))
    emit(frame("d1","priority","P2",[("o0","PASS"),("o1","FORGE_LEGAL_ACTION:Giant Growth:hand:cast:obj:micro-growth")]))
    assert read_submit()=="o1"
    emit(frame("d2","chooseCard", "P2",[("o0","TARGET_CARD_SEMANTIC:obj:micro-target"),("o1","TARGET_CARD_SEMANTIC:obj:other")]))
    assert read_submit()=="o0"
    emit(event("spell_cast:Giant_Growth")); emit(event("stack_push:Giant_Growth"))
    emit(state("behavior_checkpoint",[{"source":"Giant Growth"}]))
    emit(frame("d3","priority","P1",[("o0","PASS"),("o1","FORGE_LEGAL_ACTION:Useless:hand:x:null")]))
    assert read_submit()=="o0"
    emit(event("resolve:Giant_Growth")); emit(event("resolve:Lightning_Bolt"))
    emit(state("behavior_checkpoint",[]))
    emit({"protocol":"P","message_type":"SESSION_RESULT","request_id":"r",
          "session_id":"s1","payload":{"stop_reason":"WS48_BEHAVIOR_DRIVER_TEST_END","snapshot":{}}})
main()
"""


def _record():
    return {
        "fixture_id": "DRIVER_TEST",
        "decision_script": [
            {
                "actor": "P2",
                "causal_step_id": "cast-growth",
                "decision_family": "priority",
                "selection": {
                    "selector_kind": "semantic_action",
                    "semantic_value": {"action": "cast", "object": "obj:micro-growth"},
                    "matches_only_provider_offered_legal_options": True,
                    "on_multiple_match": "FAIL_CLOSED",
                    "on_zero_match": "FAIL_CLOSED",
                },
            },
            {
                "actor": "P2",
                "causal_step_id": "cast-growth",
                "decision_family": "target",
                "selection": {
                    "selector_kind": "semantic_object",
                    "semantic_value": "obj:micro-target",
                    "matches_only_provider_offered_legal_options": True,
                    "on_multiple_match": "FAIL_CLOSED",
                    "on_zero_match": "FAIL_CLOSED",
                },
            },
        ],
        "expected_events": {
            "required_events": [
                "spell_cast:Giant_Growth",
                "stack_push:Giant_Growth",
                "resolve:Giant_Growth",
                "resolve:Lightning_Bolt",
            ],
            "forbidden_events": [],
            "ordering_constraints": [
                ["spell_cast:Giant_Growth", "resolve:Giant_Growth"],
                ["resolve:Giant_Growth", "resolve:Lightning_Bolt"],
            ],
            "partial_order_constraints": [],
        },
        "terminal_postconditions": ["Stack is empty after both spells resolve."],
    }


def test_kind_has_ref_boundaries():
    assert drv.kind_has_ref("SEMANTIC_CARD:obj:micro-target:Grizzly Bears", "obj:micro-target")
    assert not drv.kind_has_ref(
        "SEMANTIC_CARD:obj:micro-target-2:Grizzly Bears", "obj:micro-target"
    )
    assert drv.kind_has_ref("PLAYER:P2", "P2")
    assert not drv.kind_has_ref("ATTACK_ASSIGNMENT:obj:P2-bears=P3", "P2")
    assert drv.kind_has_ref("FORGE_LEGAL_ACTION:Giant Growth:hand:Pump:obj:micro-growth", "obj:micro-growth")


def test_drive_cast_target_pass_resolve(tmp_path, monkeypatch):
    fake = tmp_path / "fake_provider.py"
    fake.write_text(FAKE)
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("COMMANDER_LAB_FORGE_PROVIDER_CMD", f"{fake}")
    record = _record()
    proc = drv.open_session(record, dict(os.environ))
    session = drv.Session(record, proc)

    def on_frame(sess, frame):
        if frame["payload"]["decision_kind"] == "priority" and sess.next_expected() is None:
            sess.answer_pass(frame)
            return
        expected = sess.next_expected()
        assert expected is not None
        sess.answer_expected(frame, expected)

    # d1 priority: first script entry is the cast; d2 target; d3 priority with no
    # script left -> scripted pass.
    stop = drv.drive_until_result(session, on_frame)
    assert stop["stop_reason"] == "WS48_BEHAVIOR_DRIVER_TEST_END"
    proc.stdin.close()
    proc.wait(timeout=30)
    assert session.decision_index == 2
    assert session.passes == 1
    assert session.feed == [
        "spell_cast:Giant_Growth",
        "stack_push:Giant_Growth",
        "resolve:Giant_Growth",
        "resolve:Lightning_Bolt",
    ]
    out = drv.verify_terminal(record, session)
    assert out["status"] == "PASS", out
    assert out["events"]["status"] == "PASS"
    assert out["postconditions"]["status"] == "PASS"


def test_zero_match_fails_closed(tmp_path, monkeypatch):
    fake = tmp_path / "fake_provider.py"
    fake.write_text(FAKE)
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("COMMANDER_LAB_FORGE_PROVIDER_CMD", f"{fake}")
    record = _record()
    record["decision_script"][0]["selection"]["semantic_value"] = {
        "action": "cast",
        "object": "obj:nonexistent",
    }
    proc = drv.open_session(record, dict(os.environ))
    session = drv.Session(record, proc)
    try:
        drv.drive_until_result(
            session, lambda sess, frame: sess.answer_expected(frame, sess.next_expected())
        )
    except drv.BehaviorFailure as ex:
        assert "ZERO" in str(ex)
    else:
        raise AssertionError("expected fail-closed BehaviorFailure")
    finally:
        proc.kill()
