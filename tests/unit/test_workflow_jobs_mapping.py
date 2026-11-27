"""Workflow jobs-mapping regression (Issue #208).

Every workflow file must carry a top-level `jobs:` mapping whose jobs each
declare `runs-on` and a non-empty `steps` list. This is the GitHub Actions
schema floor that permissive YAML parsing does not enforce: the R21
env-insert consumed the `jobs:` key of windows-runtime.yml, nesting the
job under `env:` — valid YAML, zero executable jobs. No workflow may
regress to a jobless shape; exemptions require an explicit allow-list
entry with rationale (currently: none).
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOWS_DIR = ".github/workflows"


def _workflow_files(repo_root: Path) -> list[Path]:
    return sorted((repo_root / WORKFLOWS_DIR).glob("*.yml"))


def test_every_workflow_has_executable_jobs_mapping(repo_root: Path) -> None:
    files = _workflow_files(repo_root)
    assert files, "no workflow files found"
    for path in files:
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        jobs = workflow.get("jobs")
        assert isinstance(jobs, dict) and jobs, (
            f"{path.name} has no executable top-level jobs mapping"
        )


def test_every_job_declares_runner_and_steps(repo_root: Path) -> None:
    checked = list(_workflow_files(repo_root))
    assert checked, "nothing was checked: _workflow_files(repo_root) is empty"
    for path in checked:
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        jobs = workflow.get("jobs") or {}
        for job_id, job in jobs.items():
            assert isinstance(job, dict), f"{path.name} job {job_id} is not a mapping"
            assert "runs-on" in job, f"{path.name} job {job_id} lacks runs-on"
            assert isinstance(job.get("steps"), list) and job["steps"], (
                f"{path.name} job {job_id} has no steps"
            )


def test_windows_runtime_job_is_top_level_not_env_nested(repo_root: Path) -> None:
    """Issue #208 exact regression: the windows-runtime job must live under
    top-level `jobs:`, never nested inside `env:`."""
    text = (repo_root / WORKFLOWS_DIR / "windows-runtime.yml").read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    assert "windows-runtime" in (workflow.get("jobs") or {}), (
        "windows-runtime job missing from top-level jobs mapping"
    )
    assert "windows-runtime" not in (workflow.get("env") or {}), (
        "windows-runtime job nested under env (Issue #208 recurrence)"
    )


def test_windows_studio_smoke_runs_the_store_cache_export_and_backup_tests(
    repo_root: Path,
) -> None:
    """#1703 step 1b (K-2b inventory 1.2): the Windows lane must run the tests that pin the
    store file, the cache stamps (``data_version``, file times), the user-state export and the
    backup before the store is split into files (K-2c). The pytest line is part of the step the
    smoke runs; dropping one of the four files from it fails here."""
    text = (repo_root / WORKFLOWS_DIR / "windows-runtime.yml").read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    steps = workflow["jobs"]["windows-runtime"]["steps"]
    smoke = next(step for step in steps if "Studio Windows smoke" in str(step.get("name")))
    pytest_lines = [
        line.strip() for line in str(smoke["run"]).splitlines() if "python -m pytest" in line
    ]
    assert len(pytest_lines) == 1, pytest_lines
    # no narrowing of the selection: no -k, -m, --deselect, --ignore or collect-only option
    arguments = pytest_lines[0].split("python -m pytest", 1)[1].split()
    for argument in arguments:
        assert not argument.startswith(("-k", "-m", "--deselect", "--ignore", "--co")), argument
    for name in (
        "test_studio_engine_provisioning.py",
        "test_studio_simulations.py",
        "test_studio_store.py",
        "test_studio_cache_groups.py",
        "test_studio_state_export.py",
        "test_studio_backup.py",
    ):
        assert f"tests/unit/{name}" in pytest_lines[0], name
        assert (repo_root / "tests" / "unit" / name).is_file(), name
