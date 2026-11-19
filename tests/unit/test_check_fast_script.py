from __future__ import annotations

import os
import re
import stat
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_fast.sh"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
_LINT_PATTERNS = (
    ("Ruff lint", r"(ruff check \.)"),
    ("Ruff format", r"(ruff format --check --diff \.)"),
    ("Mypy strict", r"(mypy src/commander_lab)"),
    ("Compile", r"(python -m compileall -q src tests)"),
)


def _init_git_repo(repo: Path) -> None:
    git_env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }
    subprocess.run(["git", "init", "-q"], cwd=repo, env=git_env, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, env=git_env, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, env=git_env, check=True)


def _write_stubs(bin_dir: Path, exit_codes: dict[str, int], log_file: Path | None = None) -> None:
    bin_dir.mkdir(exist_ok=True)
    for tool, code in exit_codes.items():
        body = ["#!/usr/bin/env bash"]
        if log_file is not None:
            body.append(f"printf '%s %s\\n' {tool!r} \"$*\" >> {str(log_file)!r}")
        body.append(f"exit {code}")
        stub = bin_dir / tool
        stub.write_text("\n".join(body) + "\n", encoding="utf-8")
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR)


def test_check_fast_script_exists_and_matches_ci_lint_commands() -> None:
    assert SCRIPT.is_file() and os.access(SCRIPT, os.X_OK)
    workflow = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
    by_name = {
        str(step.get("name", "")): str(step.get("run", ""))
        for step in workflow["jobs"]["lint"]["steps"]
    }
    expected: list[str] = []
    for step_name, pattern in _LINT_PATTERNS:
        match = re.search(pattern, by_name[step_name])
        assert match is not None, f"{step_name} command not found in ci.yml"
        expected.append(match.group(1))

    listed = subprocess.run(
        ["bash", str(SCRIPT), "--list-commands"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert listed.returncode == 0, listed.stderr
    assert [line.strip() for line in listed.stdout.splitlines() if line.strip()] == expected


def test_check_fast_executes_exact_lint_commands_and_changed_tests(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src" / "commander_lab" / "studio").mkdir(parents=True)
    (repo / "tests" / "unit").mkdir(parents=True)
    (repo / "src" / "commander_lab" / "studio" / "alpha.py").write_text("V = 1\n", encoding="utf-8")
    for name in ("test_studio_alpha.py", "test_direct.py", "test_unrelated.py"):
        (repo / "tests" / "unit" / name).write_text(
            "def test_ok() -> None:\n    pass\n", encoding="utf-8"
        )
    _init_git_repo(repo)

    (repo / "src" / "commander_lab" / "studio" / "alpha.py").write_text("V = 2\n", encoding="utf-8")
    (repo / "tests" / "unit" / "test_direct.py").write_text(
        "def test_ok() -> None:\n    assert 1\n", encoding="utf-8"
    )

    bin_dir, log_file = tmp_path / "bin", tmp_path / "invocations.log"
    _write_stubs(bin_dir, {"ruff": 0, "mypy": 0, "python": 0}, log_file)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
        "CHECK_FAST_BASE": "HEAD",
    }
    proc = subprocess.run(
        ["bash", str(SCRIPT)], cwd=repo, env=env, capture_output=True, text=True, check=False
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SUMMARY: PASS" in proc.stdout
    invocations = [line.strip() for line in log_file.read_text(encoding="utf-8").splitlines()]
    assert invocations[:4] == [
        "ruff check .",
        "ruff format --check --diff .",
        "mypy src/commander_lab",
        "python -m compileall -q src tests",
    ]
    assert len(invocations) == 5 and invocations[4].startswith("python -m pytest -q ")
    assert "tests/unit/test_direct.py" in invocations[4]
    assert "tests/unit/test_studio_alpha.py" in invocations[4]
    assert "tests/unit/test_unrelated.py" not in invocations[4]


def test_check_fast_fails_closed_when_lint_step_fails(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir(parents=True)
    (repo / "src" / "x.py").write_text("X = 1\n", encoding="utf-8")
    _init_git_repo(repo)

    bin_dir = tmp_path / "bin"
    _write_stubs(bin_dir, {"ruff": 0, "mypy": 1, "python": 0})
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
        "CHECK_FAST_BASE": "HEAD",
    }
    proc = subprocess.run(
        ["bash", str(SCRIPT)], cwd=repo, env=env, capture_output=True, text=True, check=False
    )

    assert proc.returncode == 1
    assert "[FAIL] mypy src/commander_lab" in proc.stdout
    assert "SUMMARY: FAIL" in proc.stdout
