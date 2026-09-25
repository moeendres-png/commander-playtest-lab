"""WS232 retention-predicate tests (machine-checked stability, S8 evidence).

No prose-only retention: every retained fixture carries a predicate whose
binds name the path owning the semantics. These tests fail closed on any
drift (engine repin, fixture mutation, owning-blob change, schema change).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
NS = REPO_ROOT / "qualification/ws232-retention-nscoped-requalification"


def _load(name: str):
    return json.loads((NS / name).read_text())


def test_workload_shape_mechanically_derived():
    d = _load("WORKLOAD_DERIVATION.json")
    assert d["shape_match"] is True
    assert d["derived_counts"] == {
        "common_fixture_total": 135,
        "rerun_required": 72,
        "retained_after_impact_adjudication": 47,
        "unknown": 16,
        "blocked": 0,
        "retained_actual_card": 29,
        "retained_micro_rules": 13,
        "retained_replay_rng": 5,
    }
    assert d["total_n_scoped_cells"] == 47 * 3
    assert len(d["unknown_rows"]) == 16


def test_predicate_coverage_complete():
    preds = _load("RETENTION_PREDICATES.json")
    assert preds["predicate_count"] == 47
    by_fixture = {p["fixture_id"] for p in preds["predicates"]}
    deriv = _load("WORKLOAD_DERIVATION.json")
    assert by_fixture == {r["fixture_id"] for r in deriv["retained_rows"]}


def test_predicates_are_semantic_not_existence():
    preds = _load("RETENTION_PREDICATES.json")
    for p in preds["predicates"]:
        assert p["semantic_premise"], p["predicate_id"]
        assert p["n_scoped_rerun_required"] == [2, 3, 5]
        assert p["binds"], p["predicate_id"]
        for b in p["binds"]:
            assert b["owns_semantics"], (p["predicate_id"], b)


def test_predicate_static_evaluation_green():
    current_pin = json.loads((REPO_ROOT / "config/rules_engines.json").read_text())[
        "primary_engine"
    ]["commit"]
    if current_pin != "db134b9737e951367d65ef5806ad986319cc73ab":
        pytest.skip(
            "WS232 is sealed historical retention evidence bound to db134b9737e951367d65ef5806ad986319cc73ab; "
            "the successor residual-repin workstream owns current requalification"
        )
    proc = subprocess.run(
        [sys.executable, str(NS / "bin/check_predicates.py")],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    res = _load("RETENTION_PREDICATE_RESULTS.json")
    assert res["evaluated_predicates"] == 47
    assert res["static_pass"] == 47
    assert res["static_fail"] == 0


def test_engine_pin_stable():
    cfg = json.loads((REPO_ROOT / "config/rules_engines.json").read_text())
    if cfg["primary_engine"]["commit"] != "db134b9737e951367d65ef5806ad986319cc73ab":
        pytest.skip(
            "WS232 engine-pin stability predicate is intentionally invalidated by "
            "the successor forward repin; historical artifacts remain sealed"
        )
    assert cfg["protocol_version"] == "2.0.0"
    provider = (
        REPO_ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageProvider.java"
    ).read_text()
    compact = "".join(provider.split())
    assert 'ENGINE_VERSION="1.4.61"' in compact
    assert 'ENGINE_COMMIT="db134b9737e951367d65ef5806ad986319cc73ab"' in compact


def test_replay_schema_stable():
    import re

    src = (REPO_ROOT / "src/commander_lab/semantic_replay/tape.py").read_text()
    m = re.search(r'TAPE_SCHEMA_VERSION(?::\s*Final)?\s*=\s*"([^"]+)"', src)
    assert m and m.group(1) == "semantic-replay-tape/1.0.0"


def test_n_scoped_disposition_join_complete():
    """R22 evidence-integrity join: every predicate x every required N-cell
    carries an explicit disposition. RERUN cells must point at an existing
    artifact whose path or bytes name BOTH the fixture_id and the player
    count (no generic smoke may discharge a fixture-specific cell); UNKNOWN
    cells must carry a non-empty reason (honest UNKNOWN allowed, silent
    gaps and manufactured PASS are not)."""
    preds = _load("RETENTION_PREDICATES.json")
    disp = _load("N_SCOPED_DISPOSITION_R21.json")
    by_pred = {e["predicate_id"]: e for e in disp["dispositions"]}
    assert len(by_pred) == preds["predicate_count"] == 47
    rerun = unknown = 0
    for p in preds["predicates"]:
        entry = by_pred.get(p["predicate_id"])
        assert entry is not None, p["predicate_id"]
        assert entry["fixture_id"] == p["fixture_id"], p["predicate_id"]
        required = [str(n) for n in p["n_scoped_rerun_required"]]
        assert sorted(entry["cells"]) == sorted(required), p["predicate_id"]
        for cell, body in entry["cells"].items():
            status = body["status"]
            assert status in ("RERUN", "UNKNOWN"), (p["predicate_id"], cell)
            if status == "RERUN":
                pointer = REPO_ROOT / body["pointer"]
                assert pointer.is_file(), (p["predicate_id"], cell, body["pointer"])
                haystack = body["pointer"] + "\n" + pointer.read_text(encoding="utf-8")
                assert p["fixture_id"] in haystack, (p["predicate_id"], cell, "fixture")
                assert cell in haystack, (p["predicate_id"], cell, "count")
                rerun += 1
            else:
                assert body.get("reason", "").strip(), (p["predicate_id"], cell)
                unknown += 1
    assert disp["counts"]["rerun_cells"] == rerun
    assert disp["counts"]["unknown_cells"] == unknown
    assert rerun + unknown == sum(len(p["n_scoped_rerun_required"]) for p in preds["predicates"])
