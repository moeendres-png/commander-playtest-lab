"""The quality gate decision (scripts/ci_gate.py) and its wiring in ci.yml."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("ci_gate", ROOT / "scripts" / "ci_gate.py")
assert _spec is not None and _spec.loader is not None
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

OK = {"changes": "success", "lint": "success", "tests": "success", "packaging": "success"}


def run(results: dict[str, str], flag: str) -> int:
    args = [f"--job={name}={value}" for name, value in results.items()]
    return int(gate.main([*args, "--allow-skipped", "packaging", "--packaging-needed", flag]))


@pytest.mark.parametrize(
    ("overrides", "flag", "expected"),
    [
        ({}, "true", 0),
        ({}, "false", 0),
        ({"lint": "failure"}, "false", 1),
        ({"tests": "failure"}, "true", 1),
        ({"packaging": "failure"}, "true", 1),
        ({"lint": "cancelled"}, "false", 1),
        ({"tests": "cancelled"}, "false", 1),
        ({"packaging": "cancelled"}, "true", 1),
        ({"changes": "cancelled"}, "false", 1),
        ({"tests": "skipped"}, "false", 1),
        ({"lint": "skipped"}, "false", 1),
        ({"changes": "skipped"}, "false", 1),
        ({"packaging": "skipped"}, "false", 0),
        ({"packaging": "skipped"}, "true", 1),
        ({"packaging": "skipped"}, "", 1),
        ({"packaging": "skipped"}, "False", 1),
        ({"changes": "failure", "packaging": "skipped", "tests": "skipped"}, "", 1),
        ({"changes": "failure", "packaging": "skipped"}, "false", 1),
        ({"lint": ""}, "false", 1),
        ({"lint": "weird"}, "false", 1),
    ],
)
def test_gate_decision_table(overrides: dict[str, str], flag: str, expected: int) -> None:
    assert run({**OK, **overrides}, flag) == expected


def test_gate_prints_every_job_result(capsys: pytest.CaptureFixture[str]) -> None:
    run({**OK, "tests": "failure"}, "false")
    out = capsys.readouterr().out
    for name in OK:
        assert name in out
    assert "tests finished as 'failure'" in out


def test_gate_without_control_job_fails() -> None:
    assert gate.main(["--job", "lint=success", "--packaging-needed", "false"]) == 1


def test_gate_rejects_repeated_job() -> None:
    assert gate.main(["--job", "lint=success", "--job", "lint=failure"]) == 2


def test_ci_workflow_gate_step_uses_the_script_with_strict_shell() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    job = workflow["jobs"]["quality"]
    assert job["if"] == "always()"
    step = next(item for item in job["steps"] if "ci_gate.py" in str(item.get("run")))
    assert "if" not in step and "continue-on-error" not in step
    assert step["run"].lstrip().startswith("set -euo pipefail")
    for needed in job["needs"]:
        assert f"needs.{needed}.result" in str(step["env"].values())
        assert f'--job {needed}="$' in step["run"]
