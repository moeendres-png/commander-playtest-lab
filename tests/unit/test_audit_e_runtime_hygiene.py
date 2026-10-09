from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from commander_lab.audit import Phase86Result, run_phase86_audit


@dataclass(frozen=True)
class _Phase86Run:
    """One real completed audit and the checkout state observed around it."""

    root: Path
    before: str
    after: str
    result: Phase86Result
    output_root: Path


def _status(root: Path) -> str:
    return subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


@pytest.fixture(scope="module")
def phase86_run() -> _Phase86Run:
    """Run the real audit once per module and share its completed result/report."""
    root = Path(__file__).resolve().parents[2]
    before = _status(root)
    result = run_phase86_audit(root, run_tests=False)
    after = _status(root)
    return _Phase86Run(
        root=root,
        before=before,
        after=after,
        result=result,
        output_root=root / ".runtime" / "audit" / "phase86",
    )


def test_phase86_audit_keeps_checkout_clean(phase86_run: _Phase86Run) -> None:
    assert phase86_run.after == phase86_run.before

    output_root = phase86_run.output_root
    assert (output_root / "PHASE86_VALIDATION_OUTPUT.json").is_file()
    assert (output_root / "artifacts" / "audit" / "bug_register.json").is_file()
    assert (output_root / "schemas" / "models").is_dir()
    assert all(str(output_root) in artifact for artifact in phase86_run.result.artifacts)

    validation = json.loads(
        (output_root / "PHASE86_VALIDATION_OUTPUT.json").read_text(encoding="utf-8")
    )
    bug_ids = {bug["bug_id"] for bug in validation["bugs"]}
    assert "BUG-AUDIT-001" in bug_ids
    assert "BUG-AUDIT-002" in bug_ids
    assert "BUG-PERF-001" in bug_ids


def test_phase86_audit_publishes_runtime_derived_tool_availability(
    phase86_run: _Phase86Run,
) -> None:
    output_root = phase86_run.output_root

    report = (output_root / "artifacts" / "audit" / "static_analysis_report.md").read_text(
        encoding="utf-8"
    )
    assert "could not be installed in the current sandbox" not in report

    statuses = {check.check_id: check.status for check in phase86_run.result.checks}
    for check_id in ("ruff_check", "ruff_format", "mypy"):
        if check_id in statuses:
            assert f"**{check_id}:** `{statuses[check_id].value}`" in report
