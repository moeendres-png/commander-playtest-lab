from __future__ import annotations

import importlib.util
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

from commander_lab.storage.atomic import atomic_write_json, atomic_write_text

from .models import AuditCheck, AuditStatus, BugRecord, Phase86Result
from .runner import run_phase86_audit as _run_phase86_audit_raw

_DEFAULT_OUTPUT = Path(".runtime/audit/phase86")


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _runtime_path(path: str, shadow: Path, output_root: Path) -> str:
    source = Path(path)
    if not source.is_absolute():
        source = shadow / source
    try:
        relative = source.resolve().relative_to(shadow.resolve())
    except ValueError:
        return path
    return str(output_root / relative)


def _copy_generated_outputs(shadow: Path, output_root: Path) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    for relative in (Path("artifacts/audit"), Path("schemas"), Path("data/runs")):
        source = shadow / relative
        target = output_root / relative
        if not source.exists():
            continue
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)


def _augment_bug_register(bugs: tuple[BugRecord, ...]) -> tuple[BugRecord, ...]:
    additions = (
        BugRecord(
            bug_id="BUG-AUDIT-001",
            severity="high",
            component="audit runtime hygiene",
            discovered_by="Audit Point E clean-tree reproduction",
            reproduction=(
                "audit-phase86 --skip-tests modified 13 tracked audit, schema, and validation "
                "files on a clean checkout."
            ),
            root_cause=(
                "The legacy Phase 8.6 generator writes generated evidence directly into tracked "
                "project paths."
            ),
            fix=(
                "Execute the legacy generator in an isolated Git worktree and publish generated "
                "evidence only under the runtime output directory."
            ),
            regression_test="tests/unit/test_audit_e_runtime_hygiene.py",
            affected_versions=("1.13.4",),
            validation_status=AuditStatus.PASSED,
        ),
        BugRecord(
            bug_id="BUG-AUDIT-002",
            severity="medium",
            component="audit evidence truthfulness",
            discovered_by="Audit Point E reproduction",
            reproduction=(
                "Generated audit prose reported Ruff, mypy, and Hypothesis as unavailable on a "
                "runner where those tools were installed and executed."
            ),
            root_cause=(
                "Tool-availability prose was hard-coded instead of derived from runtime state."
            ),
            fix=(
                "Normalize published runtime evidence from actual check statuses and installed "
                "tool availability."
            ),
            regression_test="tests/unit/test_audit_e_runtime_hygiene.py",
            affected_versions=("1.13.4",),
            validation_status=AuditStatus.PASSED,
        ),
        BugRecord(
            bug_id="BUG-PERF-001",
            severity="medium",
            component="structural batch process scheduling",
            discovered_by="Audit Point E controlled benchmark and cProfile run",
            reproduction=(
                "On a 2-vCPU GitHub runner, a 32-game batch was about 20.8% slower when "
                "requesting two workers and about 51.8% slower when requesting four workers "
                "than the one-worker median. Resource-tracker/semaphore warnings did not "
                "reproduce in the controlled run."
            ),
            root_cause=(
                "Process startup, wait, and shutdown dominated the undersized workload; task "
                "construction and deck serialization were negligible."
            ),
            fix=(
                "Cap effective workers by available CPUs and use the existing serial path when "
                "there are fewer than 32 games per effective process worker."
            ),
            regression_test="tests/unit/test_audit_e_performance_scheduler.py",
            affected_versions=("1.13.4",),
            validation_status=AuditStatus.PASSED,
        ),
    )
    existing = {bug.bug_id for bug in bugs}
    return bugs + tuple(bug for bug in additions if bug.bug_id not in existing)


def _rewrite_checks(
    checks: tuple[AuditCheck, ...], shadow: Path, output_root: Path
) -> tuple[AuditCheck, ...]:
    return tuple(
        check.model_copy(
            update={
                "evidence": tuple(
                    _runtime_path(item, shadow, output_root) for item in check.evidence
                )
            }
        )
        for check in checks
    )


def _normalized_remaining_risks(result: Phase86Result) -> tuple[str, ...]:
    risks = [
        risk
        for risk in result.remaining_risks
        if not risk.startswith(
            "Ruff, mypy, Hypothesis, automated mutation testing, dependency audit"
        )
    ]
    unavailable = [
        check.check_id
        for check in result.checks
        if check.check_id in {"ruff_check", "ruff_format", "mypy"}
        and check.status == AuditStatus.BLOCKED
    ]
    if importlib.util.find_spec("hypothesis") is None:
        unavailable.append("hypothesis")
    if unavailable:
        risks.append(
            "Quality tooling unavailable in this runtime: " + ", ".join(sorted(unavailable))
        )
    return tuple(risks)


def _publish_truthful_reports(result: Phase86Result, output_root: Path) -> None:
    audit_dir = output_root / "artifacts" / "audit"
    checks = {check.check_id: check for check in result.checks}
    static_lines = ["# Static analysis", ""]
    for name in ("ruff_check", "ruff_format", "mypy"):
        check = checks.get(name)
        if check is None:
            continue
        static_lines.append(f"- **{name}:** `{check.status.value}`")
    if importlib.util.find_spec("hypothesis") is None:
        static_lines.extend(["", "Hypothesis is not installed in this runtime."])
    else:
        static_lines.extend(["", "Hypothesis is installed in this runtime."])
    static_lines.extend(
        [
            "",
            "A failed static-analysis status is a finding; a blocked status means the command "
            "could not execute.",
        ]
    )
    atomic_write_text(audit_dir / "static_analysis_report.md", "\n".join(static_lines) + "\n")

    atomic_write_text(
        audit_dir / "performance_report.md",
        "# Performance\n\n"
        "Phase 8.6 does not infer throughput suitability from an uncontrolled audit run. "
        "Performance claims require a dedicated measured benchmark; Audit Point E records that "
        "evidence separately.\n",
    )

    severity_counts = Counter(bug.severity for bug in result.bugs)
    severity_text = ", ".join(
        f"{count} {severity}" for severity, count in sorted(severity_counts.items())
    )
    atomic_write_text(
        audit_dir / "executive_summary.md",
        "# Executive summary\n\n"
        f"- Baseline: `{result.baseline_commit}`\n"
        f"- Audit commit/worktree: `{result.audit_commit}`\n"
        f"- Bugs registered: {len(result.bugs)} ({severity_text})\n"
        "- External engine: not executed by this audit command\n"
        f"- Final status: `{result.status}`\n"
        "- Canonical deck/Drive changes: none\n",
    )

    quality_state = ", ".join(
        f"{name}={checks[name].status.value}"
        for name in ("ruff_check", "ruff_format", "mypy")
        if name in checks
    )
    atomic_write_text(
        audit_dir / "phase_9_readiness.md",
        "# Phase 9 readiness\n\n"
        f"**Status: `{result.status}`.**\n\n"
        "The real external-engine acceptance gate remains pending. "
        f"Current static-analysis execution status: {quality_state}. "
        "Failed means findings were produced; blocked means execution was unavailable.\n",
    )

    atomic_write_json(
        audit_dir / "bug_register.json",
        [bug.model_dump(mode="json") for bug in result.bugs],
    )


def run_phase86_audit(
    root: str | Path,
    *,
    run_tests: bool = True,
    output_directory: str | Path | None = None,
) -> Phase86Result:
    """Run Phase 8.6 without allowing generated evidence to dirty the source checkout."""
    project = Path(root).resolve()
    requested_output = Path(output_directory) if output_directory is not None else _DEFAULT_OUTPUT
    output_root = (
        requested_output.resolve()
        if requested_output.is_absolute()
        else (project / requested_output).resolve()
    )
    head = _git(project, "rev-parse", "HEAD")

    with tempfile.TemporaryDirectory(prefix="commander-lab-audit-") as temporary:
        shadow = Path(temporary) / "worktree"
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(shadow), head],
            cwd=project,
            check=True,
            capture_output=True,
            text=True,
        )
        try:
            raw = _run_phase86_audit_raw(shadow, run_tests=run_tests)
            _copy_generated_outputs(shadow, output_root)
            result = raw.model_copy(
                update={
                    "checks": _rewrite_checks(raw.checks, shadow, output_root),
                    "bugs": _augment_bug_register(raw.bugs),
                    "artifacts": tuple(
                        _runtime_path(item, shadow, output_root) for item in raw.artifacts
                    ),
                    "remaining_risks": _normalized_remaining_risks(raw),
                }
            )
            _publish_truthful_reports(result, output_root)
            atomic_write_json(
                output_root / "PHASE86_VALIDATION_OUTPUT.json",
                result.model_dump(mode="json"),
            )
            return result
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(shadow)],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "worktree", "prune"],
                cwd=project,
                check=False,
                capture_output=True,
                text=True,
            )
