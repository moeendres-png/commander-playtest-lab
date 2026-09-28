"""Rejected capsules must not disclose state/parser/subprocess payloads."""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from foundry import context_capsule as capsule


def test_yaml_error_does_not_echo_source(tmp_path, capsys):
    state = tmp_path / "state.yaml"
    state.write_text("objective: PRIVATE_SENTINEL: broken\n")
    assert capsule.main(["--state", str(state), "--workdir", str(tmp_path)]) == 2
    captured = capsys.readouterr()
    assert not captured.out
    assert "PRIVATE_SENTINEL" not in captured.err
    assert "CAPSULE_REJECT" in captured.err


def test_schema_error_does_not_echo_value(tmp_path, monkeypatch, capsys):
    state = tmp_path / "state.yaml"
    state.write_text("schema_version: '2.0'\n")
    monkeypatch.setattr(
        capsule.state_mod, "validate", lambda data: ["bad status: PRIVATE_SENTINEL"]
    )
    assert capsule.main(["--state", str(state)]) == 2
    assert "PRIVATE_SENTINEL" not in capsys.readouterr().err


def test_git_failure_does_not_echo_stderr(monkeypatch):
    monkeypatch.setattr(
        capsule.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 1, "", "PRIVATE_SENTINEL"),
    )
    with pytest.raises(capsule.CapsuleError) as error:
        capsule._git(["status", "--porcelain"], ".")
    assert "PRIVATE_SENTINEL" not in str(error.value)


@pytest.mark.parametrize(
    "error",
    [
        OSError("PRIVATE_SENTINEL"),
        subprocess.TimeoutExpired("PRIVATE_SENTINEL", 15),
        UnicodeDecodeError("utf8", b"\xff", 0, 1, "PRIVATE_SENTINEL"),
    ],
)
def test_git_exceptions_are_bounded_and_private(monkeypatch, capsys, error):
    def fail(*args, **kwargs):
        assert kwargs["timeout"] == 15
        raise error

    monkeypatch.setattr(capsule.subprocess, "run", fail)
    monkeypatch.setattr(capsule, "_load_state", lambda path: {})
    assert capsule.main(["--state", "unused"]) == 2
    captured = capsys.readouterr()
    assert not captured.out and "CAPSULE_REJECT" in captured.err
    assert "PRIVATE_SENTINEL" not in captured.err


@pytest.mark.parametrize(
    "raw",
    [
        b"\xffPRIVATE_SENTINEL",
        b"[" * 2000,
        b"schema_version: '2.0'\nstatus: {PRIVATE_SENTINEL: value}\n",
    ],
)
def test_malformed_state_never_escapes_as_traceback(tmp_path, capsys, raw):
    state = tmp_path / "state.yaml"
    state.write_bytes(raw)
    assert capsule.main(["--state", str(state)]) == 2
    captured = capsys.readouterr()
    assert not captured.out and "CAPSULE_REJECT" in captured.err
    assert "PRIVATE_SENTINEL" not in captured.err and "Traceback" not in captured.err


def test_private_state_path_not_echoed(tmp_path, capsys):
    assert capsule.main(["--state", str(tmp_path / "PRIVATE_SENTINEL")]) == 2
    assert "PRIVATE_SENTINEL" not in capsys.readouterr().err


def test_branch_conflict_does_not_echo_state(monkeypatch):
    monkeypatch.setattr(capsule.state_mod, "_is_ancestor", lambda *args: True)
    problems = capsule._check_identity(
        {"branch": "PRIVATE_SENTINEL", "audit_base_sha": "a" * 40},
        {"branch": "main", "head": "a" * 40},
        ".",
    )
    assert "branch mismatch" in problems[0]
    assert "PRIVATE_SENTINEL" not in problems[0]


def test_git_success_control(monkeypatch):
    monkeypatch.setattr(
        capsule.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, "main\n", ""),
    )
    assert capsule._git(["rev-parse", "--abbrev-ref", "HEAD"], ".") == "main"
