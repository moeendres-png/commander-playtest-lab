"""The quality gate decision (scripts/ci_gate.py) and its wiring in ci.yml."""

from __future__ import annotations

import importlib.util
import re
import shlex
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("ci_gate", ROOT / "scripts" / "ci_gate.py")
assert _spec is not None and _spec.loader is not None
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

PACKAGING_PARTS = ("packaging-1", "packaging-2")
OK = {
    "changes": "success",
    "lint": "success",
    "tests": "success",
    "packaging-1": "success",
    "packaging-2": "success",
}
BOTH_SKIPPED = {"packaging-1": "skipped", "packaging-2": "skipped"}


def run(results: dict[str, str], flag: str) -> int:
    args = [f"--job={name}={value}" for name, value in results.items()]
    allow = [item for part in PACKAGING_PARTS for item in ("--allow-skipped", part)]
    return int(gate.main([*args, *allow, "--packaging-needed", flag]))


def _workflow() -> dict:
    return yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("overrides", "flag", "expected"),
    [
        ({}, "true", 0),
        ({}, "false", 0),
        ({"lint": "failure"}, "false", 1),
        ({"tests": "failure"}, "true", 1),
        ({"packaging-1": "failure"}, "true", 1),
        ({"packaging-2": "failure"}, "true", 1),
        ({"packaging-1": "failure", "packaging-2": "failure"}, "true", 1),
        ({"lint": "cancelled"}, "false", 1),
        ({"tests": "cancelled"}, "false", 1),
        ({"packaging-1": "cancelled"}, "true", 1),
        ({"packaging-2": "cancelled"}, "true", 1),
        ({"changes": "cancelled"}, "false", 1),
        ({"tests": "skipped"}, "false", 1),
        ({"lint": "skipped"}, "false", 1),
        ({"changes": "skipped"}, "false", 1),
        # Both packaging halves are skipped together when no packaging input changed.
        (BOTH_SKIPPED, "false", 0),
        (BOTH_SKIPPED, "true", 1),
        (BOTH_SKIPPED, "", 1),
        (BOTH_SKIPPED, "False", 1),
        # A half that is skipped while the other ran is never accepted, whatever the flag.
        ({"packaging-1": "skipped"}, "true", 1),
        ({"packaging-2": "skipped"}, "true", 1),
        ({"packaging-1": "skipped"}, "false", 1),
        ({"packaging-2": "skipped"}, "false", 1),
        ({"packaging-1": "skipped", "packaging-2": "failure"}, "false", 1),
        ({"packaging-1": "cancelled", "packaging-2": "skipped"}, "false", 1),
        ({"packaging-1": "", "packaging-2": "success"}, "true", 1),
        ({"changes": "failure", **BOTH_SKIPPED, "tests": "skipped"}, "", 1),
        ({"changes": "failure", **BOTH_SKIPPED}, "false", 1),
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


def _gate_step(workflow: dict) -> dict:
    job = workflow["jobs"]["quality"]
    return next(item for item in job["steps"] if "ci_gate.py" in str(item.get("run")))


def test_ci_workflow_gate_step_uses_the_script_with_strict_shell() -> None:
    workflow = _workflow()
    job = workflow["jobs"]["quality"]
    assert job["if"] == "always()"
    assert "continue-on-error" not in job
    step = _gate_step(workflow)
    assert job["steps"][-1] is step
    assert "if" not in step and "continue-on-error" not in step
    assert step["run"].lstrip().startswith("set -euo pipefail")
    for needed in job["needs"]:
        assert f"needs.{needed}.result" in str(step["env"].values())
        assert f'--job {needed}="$' in step["run"]


def test_quality_gate_step_binds_every_needed_job_to_its_own_result() -> None:
    """Every env var is exactly one ``needs.<job>.result`` and each ``--job X`` reads X's var.

    A swapped pair, a missing half, an extra ``--job`` or a hard-coded result fails here.
    """
    workflow = _workflow()
    job = workflow["jobs"]["quality"]
    assert job["needs"] == ["changes", "lint", "tests", *PACKAGING_PARTS]
    step = _gate_step(workflow)
    run_text = step["run"]
    env = dict(step["env"])
    assert env.pop("PACKAGING_NEEDED") == "${{ needs.changes.outputs.packaging }}"
    bound: dict[str, str] = {}
    for var, expr in env.items():
        match = re.fullmatch(r"\$\{\{\s*needs\.([A-Za-z0-9_-]+)\.result\s*\}\}", str(expr).strip())
        assert match is not None, (var, expr)
        assert match.group(1) not in bound, f"two variables bound to {match.group(1)}"
        bound[match.group(1)] = var
    assert set(bound) == set(job["needs"])
    command = shlex.split(run_text.strip().splitlines()[-1])
    jobs = [command[i + 1] for i, token in enumerate(command) if token == "--job"]
    assert jobs == [f"{needed}=${bound[needed]}" for needed in job["needs"]]
    allowed = [command[i + 1] for i, token in enumerate(command) if token == "--allow-skipped"]
    assert allowed == list(PACKAGING_PARTS)
    flag = command[command.index("--packaging-needed") + 1]
    assert flag == "$PACKAGING_NEEDED"
    assert "--allow-skipped=" not in run_text and "--job=" not in run_text


def _without_test_ids(step: dict) -> dict:
    """The step with the half-specific test selection removed from its pytest command."""
    run_text = step.get("run")
    if not isinstance(run_text, str) or not run_text.lstrip().startswith("pytest"):
        return step
    kept = [
        token
        for token in shlex.split(run_text)
        if "::" not in token and not token.startswith("--junitxml=")
    ]
    return {**step, "run": " ".join(kept)}


def test_the_packaging_halves_are_the_same_job_except_for_their_test_ids() -> None:
    """Both halves build the wheel and run the smoke and its check; only the test ids differ.

    The same skip condition on both makes a lone skipped half impossible; scripts/ci_gate.py
    rejects one anyway.
    """
    jobs = _workflow()["jobs"]
    first, second = (jobs[name] for name in PACKAGING_PARTS)
    assert sorted(name for name in jobs if name.startswith("packaging")) == list(PACKAGING_PARTS)
    for name, job in zip(PACKAGING_PARTS, (first, second), strict=True):
        assert job["needs"] == "changes", name
        assert job["if"] == "${{ needs.changes.outputs.packaging == 'true' }}", name
        assert "strategy" not in job and "continue-on-error" not in job, name
        assert job["name"] == f"packaging {name[-1]}/2"
        pytest_steps = [
            step for step in job["steps"] if str(step.get("run", "")).lstrip().startswith("pytest")
        ]
        assert len(pytest_steps) == 1, name
        assert f"--junitxml=artifacts/quality/pytest-junit-{name}.xml" in pytest_steps[0]["run"]
        assert job["steps"][-1]["with"]["name"] == "ci-evidence-${{ github.job }}"
    assert {k: v for k, v in first.items() if k not in {"steps", "name"}} == {
        k: v for k, v in second.items() if k not in {"steps", "name"}
    }
    assert [_without_test_ids(step) for step in first["steps"]] == [
        _without_test_ids(step) for step in second["steps"]
    ]


def test_tests_and_packaging_checkouts_fetch_full_history() -> None:
    """Some tests diff against old commits; a shallow clone makes them fail or skip silently."""
    workflow = _workflow()
    for name in ("tests", *PACKAGING_PARTS):
        checkouts = [
            step
            for step in workflow["jobs"][name]["steps"]
            if "actions/checkout@" in step.get("uses", "")
        ]
        assert checkouts, name
        for step in checkouts:
            assert str((step.get("with") or {}).get("fetch-depth")) == "0", (
                f"{name}: shallow checkout"
            )
    text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "--unshallow" not in text


def _sparse_checkout(job: dict) -> tuple[dict, list[str]]:
    checkouts = [step for step in job["steps"] if "actions/checkout@" in step.get("uses", "")]
    assert len(checkouts) == 1
    options = checkouts[0].get("with") or {}
    return options, str(options.get("sparse-checkout", "")).split()


@pytest.mark.parametrize(
    ("job_name", "files"),
    [
        # ci_change_scope.py reads pyproject.toml; without it every pull request would fall
        # back to the full run (packaging always on) and no other test would notice.
        ("changes", ["scripts/ci_change_scope.py", "/pyproject.toml"]),
        ("quality", ["scripts/ci_gate.py"]),
        ("security", ["scripts/ci_gate.py"]),
    ],
)
def test_changes_and_gate_jobs_use_a_slim_checkout_without_credentials(
    job_name: str, files: list[str]
) -> None:
    job = _workflow()["jobs"][job_name]
    options, listed = _sparse_checkout(job)
    assert listed == files
    assert options.get("sparse-checkout-cone-mode") is False
    assert options.get("persist-credentials") is False
    assert "fetch-depth" not in options and "ref" not in options
    paths = [path.removeprefix("/") for path in files]
    for path in paths:
        assert (ROOT / path).is_file(), path
    for step in job["steps"]:
        for token in re.findall(r"scripts/[A-Za-z0-9_./-]+\.py", str(step.get("run", ""))):
            assert token in paths, f"{job_name} runs {token}, which its checkout leaves out"


def test_changes_still_fetches_the_base_commit_for_the_diff() -> None:
    step = next(
        item
        for item in _workflow()["jobs"]["changes"]["steps"]
        if "ci_change_scope.py" in str(item.get("run", ""))
    )
    assert step["env"]["BASE_SHA"] == "${{ github.event.pull_request.base.sha }}"
    assert 'git fetch --no-tags --depth=1 origin "$BASE_SHA"' in step["run"]
    assert '--base "$BASE_SHA"' in step["run"]
    assert step["run"].lstrip().startswith("set -euo pipefail")
