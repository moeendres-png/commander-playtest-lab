"""Unit tests for the WS-48 behavior postcondition registry (no engine needed)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MOD = REPO / "candidate-qualification/ws48-forge-v1.0.5/behavior_postconditions.py"


def _load():
    spec = importlib.util.spec_from_file_location("ws48_behavior_postconditions", MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pc = _load()


def _ctx(**kw):
    base = {"snapshot": {"cards": [], "stack": []}, "feed": [], "matches": [], "stop": {}}
    base.update(kw)
    return base


def test_unknown_template_fails_closed():
    out = pc.check_one("The moon is made of cheese.", {}, _ctx())
    assert out["status"] == "FAIL"
    assert out["violations"][0].startswith(pc.UNIMPLEMENTED_PREFIX)


def test_stack_empty_pass_and_fail():
    assert pc.check_one("Stack is empty after both spells resolve.", {}, _ctx())["status"] == "PASS"
    ctx = _ctx(snapshot={"cards": [], "stack": [{"source": "x"}]})
    assert pc.check_one("Stack is empty after both spells resolve.", {}, ctx)["status"] == "FAIL"


def test_selected_from_offered_requires_match_log():
    rec = {"decision_script": [{"actor": "P1"}, {"actor": "P1"}]}
    out = pc.check_one(
        "Selected cast action was among provider-offered legal options and no adapter legality was invented.",
        rec,
        _ctx(matches=[{"decision_id": "d1", "offered_digest": "abc", "offered_count": 3}]),
    )
    assert out["status"] == "FAIL"
    good = _ctx(
        matches=[
            {
                "decision_id": "d1",
                "offered_digest": "abc",
                "offered_count": 3,
                "match_rule": "semantic_action",
            },
            {
                "decision_id": "d2",
                "offered_digest": "def",
                "offered_count": 2,
                "match_rule": "semantic_object",
            },
        ]
    )
    out = pc.check_one(
        "Selected cast action was among provider-offered legal options and no adapter legality was invented.",
        rec,
        good,
    )
    assert out["status"] == "PASS"


def test_negative_probe_checks():
    ctx = _ctx(stop={"code": "UNSUPPORTED_DISCRETIONARY_DECISION:first_option"})
    assert (
        pc.check_one(
            "Session/fixture terminates with typed unsupported discretionary-decision failure.",
            {},
            ctx,
        )["status"]
        == "PASS"
    )
    assert (
        pc.check_one(
            "Session/fixture terminates with typed unsupported discretionary-decision failure.",
            {},
            _ctx(stop={"stop_reason": "WS23_EXTERNAL_EOF"}),
        )["status"]
        == "FAIL"
    )
    assert pc.check_one("No first_option behavior selected an option.", {}, ctx)["status"] == "PASS"
    bad = _ctx(
        stop={"code": "UNSUPPORTED_DISCRETIONARY_DECISION:first_option"},
        feed=["fallback_used:first_option"],
    )
    assert pc.check_one("No first_option behavior selected an option.", {}, bad)["status"] == "FAIL"
