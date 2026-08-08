from __future__ import annotations

import json
import subprocess
from pathlib import Path

from commander_lab.audit import run_phase86_audit


def _status(root: Path) -> str:
    return subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def test_phase86_audit_keeps_checkout_clean() -> None:
    root = Path(__file__).resolve().parents[2]
    before = _status(root)

    result = run_phase86_audit(root, run_tests=False)

    after = _status(root)
    assert after == before

    output_root = root / ".runtime" / "audit" / "phase86"
    assert (output_root / "PHASE86_VALIDATION_OUTPUT.json").is_file()
    assert (output_root / "artifacts" / "audit" / "bug_register.json").is_file()
    assert (output_root / "schemas" / "models").is_dir()
    assert all(str(output_root) in artifact for artifact in result.artifacts)

    validation = json.loads(
        (output_root / "PHASE86_VALIDATION_OUTPUT.json").read_text(encoding="utf-8")
    )
    bug_ids = {bug["bug_id"] for bug in validation["bugs"]}
    assert "BUG-AUDIT-001" in bug_ids
    assert "BUG-AUDIT-002" in bug_ids
    assert "BUG-PERF-001" in bug_ids


def test_phase86_audit_publishes_runtime_derived_tool_availability() -> None:
    root = Path(__file__).resolve().parents[2]
    result = run_phase86_audit(root, run_tests=False)
    output_root = root / ".runtime" / "audit" / "phase86"

    report = (output_root / "artifacts" / "audit" / "static_analysis_report.md").read_text(
        encoding="utf-8"
    )
    assert "could not be installed in the current sandbox" not in report

    statuses = {check.check_id: check.status for check in result.checks}
    for check_id in ("ruff_check", "ruff_format", "mypy"):
        if check_id in statuses:
            assert f"**{check_id}:** `{statuses[check_id].value}`" in report
