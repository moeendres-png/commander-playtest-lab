"""Runner identity facts fail closed (B4) and Forge needs an explicit checkout (B5).

The runner's ``git()`` used to return whatever stdout a failed command left,
so a missing checkout or a broken repository was recorded as an empty
``runner_commit`` / ``adapter_commit`` instead of stopping the run. And the
Forge checkout defaulted to one machine's historical path, so a run silently
bound whatever tree sat there.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

from commander_lab.qualification.current_boundary import receipts as R

REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "scripts" / "run_current_boundary_qualification.py"
ASSEMBLER = REPO / "scripts" / "assemble_current_boundary_evidence.py"


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    env = ["-c", "user.name=t", "-c", "user.email=t@example.invalid"]
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    (path / "f.txt").write_text("x\n", encoding="utf-8")
    subprocess.run(["git", *env, "-C", str(path), "add", "f.txt"], check=True)
    subprocess.run(["git", *env, "-C", str(path), "commit", "-q", "-m", "c"], check=True)
    return path


def _load_runner(monkeypatch: pytest.MonkeyPatch, forge_workspace: str | None):
    if forge_workspace is None:
        monkeypatch.delenv("FORGE_WORKSPACE", raising=False)
    else:
        monkeypatch.setenv("FORGE_WORKSPACE", forge_workspace)
    spec = importlib.util.spec_from_file_location("strict_identity_runner", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_git_fact_returns_a_full_sha(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path / "repo")
    value = R.git_fact(repo, "rev-parse", "HEAD", sha=True)
    assert len(value) == 40 and int(value, 16) >= 0


@pytest.mark.parametrize(
    ("args", "sha"),
    [
        (("rev-parse", "no-such-ref"), True),  # command fails
        (("config", "--get", "no.such.key"), False),  # returncode 1, no output
        (("rev-parse", "--abbrev-ref", "HEAD"), True),  # succeeds, but not a SHA
    ],
)
def test_git_fact_refuses_anything_that_is_not_the_fact(
    tmp_path: Path, args: tuple[str, ...], sha: bool
) -> None:
    repo = _init_repo(tmp_path / "repo")
    with pytest.raises(R.ReceiptError):
        R.git_fact(repo, *args, sha=sha)


def test_git_fact_refuses_a_missing_checkout(tmp_path: Path) -> None:
    with pytest.raises(R.ReceiptError, match="not a directory"):
        R.git_fact(tmp_path / "absent", "rev-parse", "HEAD", sha=True)


def test_git_fact_refuses_a_directory_outside_any_repository(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()
    ceiling = subprocess.run(
        ["git", "-C", str(plain), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if ceiling.returncode == 0:
        pytest.skip("the scratch directory lies inside a Git checkout on this machine")
    with pytest.raises(R.ReceiptError):
        R.git_fact(plain, "rev-parse", "HEAD", sha=True)


def test_runner_git_fails_closed_instead_of_recording_an_empty_identity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    runner = _load_runner(monkeypatch, None)
    with pytest.raises(SystemExit, match="no identity, no credit"):
        runner.git("rev-parse", "HEAD", cwd=tmp_path / "absent")
    assert len(runner.git("rev-parse", "HEAD")) == 40


def test_forge_has_no_default_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _load_runner(monkeypatch, None)
    assert runner.FORGE_WORKSPACE is None
    assert runner.NATIVE_SUITE_BINDING["forge"]["engine_tree"] == "UNCONFIGURED"
    with pytest.raises(SystemExit, match="FORGE_WORKSPACE is not set"):
        runner.require_forge_workspace()


def test_forge_workspace_must_exist(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runner = _load_runner(monkeypatch, str(tmp_path / "absent"))
    with pytest.raises(SystemExit, match="not a directory"):
        runner.require_forge_workspace()


def test_forge_workspace_must_be_its_checkouts_top_level(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo = _init_repo(tmp_path / "forge")
    nested = repo / "forge-protocol2-bridge"
    nested.mkdir()
    runner = _load_runner(monkeypatch, str(nested))
    with pytest.raises(SystemExit, match="not the top level"):
        runner.require_forge_workspace()
    runner = _load_runner(monkeypatch, str(repo))
    assert runner.require_forge_workspace() == repo
    assert len(runner.NATIVE_SUITE_BINDING["forge"]["engine_tree"]) == 40


def test_a_forge_run_stops_before_writing_anything(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = _load_runner(monkeypatch, None)
    written: list[str] = []
    monkeypatch.setattr(runner, "write", lambda name, payload: written.append(name))
    monkeypatch.setattr(runner.OUT_DIR.__class__, "mkdir", lambda *a, **k: written.append("mkdir"))
    monkeypatch.setattr("sys.argv", ["runner", "--candidate", "forge"])
    with pytest.raises(SystemExit, match="FORGE_WORKSPACE is not set"):
        runner.main()
    assert written == []


@pytest.mark.parametrize("script", [RUNNER, ASSEMBLER])
def test_no_machine_specific_checkout_path_is_hard_coded(script: Path) -> None:
    assert "/home/" not in script.read_text(encoding="utf-8")
