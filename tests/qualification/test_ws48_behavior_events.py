"""Unit tests for the WS-48 behavior event-feed verifier (no engine needed)."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MOD = REPO / "candidate-qualification/ws48-forge-v1.0.5/behavior_events.py"


def _ws47_path() -> Path:
    for cand in (
        os.environ.get("WS47_MATERIALIZATION_JSON", ""),
        "/tmp/opencode/ws47/qualification/ws47/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json",
        "contract-lock/qualification/ws47/SEMANTIC_FIXTURE_MATERIALIZATION_v1_0_5.json",
    ):
        if cand and Path(cand).is_file():
            return Path(cand)
    pytest.skip("WS-47 v1.0.5 materialization not available")
    raise AssertionError("unreachable")


def _load():
    spec = importlib.util.spec_from_file_location("ws48_behavior_events", MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


be = _load()


def _record(fid):
    doc = json.loads(_ws47_path().read_text())
    return next(r for r in doc["records"] if r["fixture_id"] == fid)


def test_micro_stack_ordering_pass():
    ee = _record("MICRO_STACK")["expected_events"]
    feed = [
        "priority:P2",
        "spell_cast:Giant_Growth",
        "stack_push:Giant_Growth",
        "resolve:Giant_Growth",
        "resolve:Lightning_Bolt",
    ]
    assert be.verify(ee, feed)["status"] == "PASS"


def test_micro_stack_wrong_order_fails():
    ee = _record("MICRO_STACK")["expected_events"]
    feed = [
        "spell_cast:Giant_Growth",
        "resolve:Lightning_Bolt",
        "resolve:Giant_Growth",
    ]
    out = be.verify(ee, feed)
    assert out["status"] == "FAIL"
    assert any(v.startswith("ORDER_VIOLATED") for v in out["violations"])


def test_missing_required_fails():
    ee = _record("MICRO_STACK")["expected_events"]
    out = be.verify(ee, ["priority:P2"])
    assert out["status"] == "FAIL"
    assert out["missing_required"]


def test_hidden_sentinel_scans_snapshots():
    ee = _record("HIDDEN_01")["expected_events"]
    sentinel = next(e for e in ee["forbidden_events"] if e.startswith("leak:"))
    feed = ["knowledge_projection:HIDDEN_01:P1"]
    assert be.verify(ee, feed)["status"] == "PASS"
    bad = be.verify(ee, feed, snapshot_texts=[f'{{"note": "{sentinel}"}}'])
    assert bad["status"] == "FAIL"
    assert bad["forbidden_observed"] == [sentinel]


def test_apnap_partial_order():
    ee = _record("WS05-MP-TRIG-3")["expected_events"]
    poc = ee["partial_order_constraints"][0]
    good = ["trigger:Soul_Warden:P1", "trigger:Soul_Warden:P2", "trigger:Soul_Warden:P3"]
    assert be.verify_apnap([], poc, good) == []
    bad = ["trigger:Soul_Warden:P2", "trigger:Soul_Warden:P1"]
    assert be.verify_apnap([], poc, bad) != []
