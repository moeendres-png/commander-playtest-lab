"""The sweep comparison names what changed per pod and fails closed on unusable input."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
DECKS = ["deck_a", "deck_b", "deck_c", "deck_d"]
REAL_ERROR = (
    "FullGameConformanceError: engine failed: ENGINE_FAILURE "
    "[ENGINE_FAILURE, XMAGE_ACTION_EXECUTION_FAILED] (diagnostics sha256:559363e1f809ce34)"
)
TIMEOUT_ERROR = "BridgeError: DECISION_ADVANCE_TIMEOUT after 75s"
COUNTS = (
    "counts IDENTICAL=0 HASH_CHANGED=0 FIXED=0 BROKEN=0 STILL_FAILED_SAME=0 "
    "STILL_FAILED_OTHER=0 PLAN_MISMATCH=0 ONLY_BEFORE=0 ONLY_AFTER=0"
)


def _module() -> ModuleType:
    name = "precon_sweep_compare"
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts/precon_sweep_compare.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # The frozen dataclass resolves its postponed annotations through sys.modules.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _row(pod: str, status: str, decks: list[str] | None = None, **extra: Any) -> dict[str, Any]:
    row = {
        "pod": pod,
        "seed": 1,
        "status": status,
        "decks": DECKS if decks is None else decks,
        "wall_s": 1.0,
        "child_cpu_s": 1.0,
    }
    row.update(extra)
    return row


def _ok(
    pod: str = "pod-001", semantic: str = "a" * 64, decks: list[str] | None = None
) -> dict[str, Any]:
    return _row(pod, "ok", decks, semantic=semantic, decisions=40, winners=[0])


def _failed(
    pod: str = "pod-001", error: str = REAL_ERROR, decks: list[str] | None = None
) -> dict[str, Any]:
    return _row(pod, "failed", decks, error=error)


def _report(*rows: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    report = {
        "jar": "bridge.jar",
        "game_seed": 7,
        "plan_seed": 11,
        "pods": len(rows),
        "pods_ok": sum(row["status"] == "ok" for row in rows),
        "pods_failed": sum(row["status"] == "failed" for row in rows),
        "families": {},
        "rows": list(rows),
    }
    report.update(overrides)
    return report


def _write(path: Path, payload: Any) -> Path:
    text = payload if isinstance(payload, str) else json.dumps(payload)
    path.write_text(text, encoding="utf-8")
    return path


def _diffs(before: dict[str, Any], after: dict[str, Any]) -> list[Any]:
    return _module().compare_reports(before, after)


def test_a_same_semantic_is_identical() -> None:
    row = _ok("pod-001", "a" * 64)
    assert [(d.pod, d.kind, d.before, d.after) for d in _diffs(_report(row), _report(row))] == [
        ("pod-001", "IDENTICAL", "ok:aaaaaaaaaaaa", "ok:aaaaaaaaaaaa")
    ]


def test_a_different_semantic_is_hash_changed() -> None:
    diffs = _diffs(_report(_ok("pod-001", "a" * 64)), _report(_ok("pod-001", "b" * 64)))
    assert [(d.kind, d.before, d.after) for d in diffs] == [
        ("HASH_CHANGED", "ok:aaaaaaaaaaaa", "ok:bbbbbbbbbbbb")
    ]


def test_a_failed_pod_that_now_plays_is_fixed() -> None:
    diffs = _diffs(_report(_failed("pod-001", REAL_ERROR)), _report(_ok("pod-001", "c" * 64)))
    assert [(d.kind, d.before, d.after) for d in diffs] == [
        ("FIXED", "XMAGE_ACTION_EXECUTION_FAILED", "ok:cccccccccccc")
    ]


def test_an_ok_pod_that_now_fails_is_broken() -> None:
    diffs = _diffs(_report(_ok("pod-001", "c" * 64)), _report(_failed("pod-001", REAL_ERROR)))
    assert [(d.kind, d.before, d.after) for d in diffs] == [
        ("BROKEN", "ok:cccccccccccc", "XMAGE_ACTION_EXECUTION_FAILED")
    ]


def test_two_failed_pods_with_the_same_family_are_still_failed_same() -> None:
    diffs = _diffs(_report(_failed("pod-001", REAL_ERROR)), _report(_failed("pod-001", REAL_ERROR)))
    assert [(d.kind, d.before, d.after) for d in diffs] == [
        ("STILL_FAILED_SAME", "XMAGE_ACTION_EXECUTION_FAILED", "XMAGE_ACTION_EXECUTION_FAILED")
    ]


def test_a_failed_pod_next_to_a_failed_pod_is_never_identical() -> None:
    before = _report(_failed("pod-001", REAL_ERROR), _failed("pod-002", TIMEOUT_ERROR))
    after = _report(_failed("pod-001", REAL_ERROR), _failed("pod-002", TIMEOUT_ERROR))
    kinds = [d.kind for d in _diffs(before, after)]
    assert kinds == ["STILL_FAILED_SAME", "STILL_FAILED_SAME"]
    assert "IDENTICAL" not in kinds


def test_a_failure_that_changes_family_is_still_failed_other() -> None:
    diffs = _diffs(
        _report(_failed("pod-001", REAL_ERROR)), _report(_failed("pod-001", TIMEOUT_ERROR))
    )
    assert [(d.kind, d.before, d.after) for d in diffs] == [
        ("STILL_FAILED_OTHER", "XMAGE_ACTION_EXECUTION_FAILED", "DECISION_ADVANCE_TIMEOUT")
    ]


def test_a_reordered_deck_list_is_a_plan_mismatch_not_identical() -> None:
    before = _report(_ok("pod-001", "a" * 64, ["deck_a", "deck_b", "deck_c", "deck_d"]))
    after = _report(_ok("pod-001", "a" * 64, ["deck_b", "deck_a", "deck_c", "deck_d"]))
    assert [(d.kind, d.before, d.after) for d in _diffs(before, after)] == [
        ("PLAN_MISMATCH", "ok:aaaaaaaaaaaa", "ok:aaaaaaaaaaaa")
    ]


def test_a_reordered_deck_list_is_a_plan_mismatch_not_a_hash_change() -> None:
    before = _report(_ok("pod-001", "a" * 64, ["deck_a", "deck_b", "deck_c", "deck_d"]))
    after = _report(_ok("pod-001", "b" * 64, ["deck_b", "deck_a", "deck_c", "deck_d"]))
    assert [(d.kind, d.before, d.after) for d in _diffs(before, after)] == [
        ("PLAN_MISMATCH", "ok:aaaaaaaaaaaa", "ok:bbbbbbbbbbbb")
    ]


def test_a_pod_only_in_the_before_report_is_only_before() -> None:
    assert [(d.kind, d.before, d.after) for d in _diffs(_report(_ok()), _report())] == [
        ("ONLY_BEFORE", "ok:aaaaaaaaaaaa", "-")
    ]


def test_a_pod_only_in_the_after_report_is_only_after() -> None:
    assert [(d.kind, d.before, d.after) for d in _diffs(_report(), _report(_ok()))] == [
        ("ONLY_AFTER", "-", "ok:aaaaaaaaaaaa")
    ]


def test_a_seed_difference_is_warned_but_still_compared(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _module()
    row = _ok()
    before = _write(tmp_path / "before.json", _report(row, plan_seed=11, game_seed=7))
    after = _write(tmp_path / "after.json", _report(row, plan_seed=12, game_seed=7))
    assert module.main([str(before), str(after)]) == 0
    lines = capsys.readouterr().out.splitlines()
    warnings = [line for line in lines if line.startswith("WARNING seeds differ:")]
    assert warnings == ["WARNING seeds differ: plan_seed 11 -> 12"]
    both = module.render(_report(plan_seed=1, game_seed=2), _report(plan_seed=3, game_seed=4), [])
    assert "WARNING seeds differ: plan_seed 1 -> 3; game_seed 2 -> 4" in both


def test_two_equal_all_ok_reports_exit_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _module()
    report = _report(_ok("pod-001", "a" * 64), _ok("pod-002", "b" * 64))
    path = _write(tmp_path / "sweep.json", report)
    assert module.main([str(path), str(path)]) == 0
    out = capsys.readouterr().out
    assert COUNTS.replace("IDENTICAL=0", "IDENTICAL=2") in out
    assert "IDENTICAL pod-" not in out


def test_any_change_exits_one(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    module = _module()
    before = _write(tmp_path / "before.json", _report(_ok("pod-001", "a" * 64)))
    after = _write(tmp_path / "after.json", _report(_ok("pod-001", "b" * 64)))
    assert module.main([str(before), str(after)]) == 1
    out = capsys.readouterr().out
    assert "HASH_CHANGED pod-001 ok:aaaaaaaaaaaa -> ok:bbbbbbbbbbbb" in out


def test_the_header_names_each_report_and_marks_a_missing_jar() -> None:
    text = _module().render(_report(jar="/tmp/bridge.jar"), _report(jar=None), [])
    assert text.splitlines()[:2] == [
        "before jar=bridge.jar plan_seed=11 game_seed=7",
        "after jar=? plan_seed=11 game_seed=7",
    ]


def test_the_families_line_uses_the_shared_failure_family(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = _module()
    report = _report(_ok("pod-001", "a" * 64), _failed("pod-002", REAL_ERROR))
    path = _write(tmp_path / "sweep.json", report)
    assert module.main([str(path), str(path)]) == 1
    out = capsys.readouterr().out
    assert (
        "STILL_FAILED_SAME pod-002 XMAGE_ACTION_EXECUTION_FAILED -> "
        "XMAGE_ACTION_EXECUTION_FAILED" in out
    )
    assert (
        "families before {'XMAGE_ACTION_EXECUTION_FAILED': 1} "
        "after {'XMAGE_ACTION_EXECUTION_FAILED': 1}" in out
    )


def test_the_families_line_sorts_the_codes() -> None:
    module = _module()
    report = _report(_failed("pod-001", REAL_ERROR), _failed("pod-002", TIMEOUT_ERROR))
    text = module.render(report, report, module.compare_reports(report, report))
    line = next(line for line in text.splitlines() if line.startswith("families "))
    families = "{'DECISION_ADVANCE_TIMEOUT': 1, 'XMAGE_ACTION_EXECUTION_FAILED': 1}"
    assert line == f"families before {families} after {families}"


UNUSABLE_PAYLOADS = [
    pytest.param("{not json", id="invalid-json"),
    pytest.param({"jar": "bridge.jar"}, id="no-rows-list"),
    pytest.param({"rows": [{"status": "ok", "semantic": "a" * 64}]}, id="row-without-pod"),
    pytest.param({"rows": [{"pod": "pod-001", "semantic": "a" * 64}]}, id="row-without-status"),
    pytest.param({"rows": [{"pod": "pod-001", "status": "skipped"}]}, id="unknown-status"),
    pytest.param({"rows": [{"pod": "pod-001", "status": "ok"}]}, id="ok-without-semantic"),
    pytest.param(
        {
            "rows": [
                {"pod": "pod-001", "status": "failed", "error": REAL_ERROR},
                {"pod": "pod-001", "status": "failed", "error": REAL_ERROR},
            ]
        },
        id="duplicate-pod",
    ),
]


@pytest.mark.parametrize("payload", UNUSABLE_PAYLOADS)
def test_an_unusable_report_exits_two_with_no_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], payload: Any
) -> None:
    module = _module()
    good = _write(tmp_path / "good.json", _report(_ok()))
    bad = _write(tmp_path / "bad.json", payload)
    assert module.main([str(bad), str(good)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert len(captured.err.splitlines()) == 1
