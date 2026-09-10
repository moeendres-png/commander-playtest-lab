"""Concurrency tests for tools/foundry/writer_lock.py.

All tests use real subprocesses and real flock(2) locks in an isolated
FOUNDRY_LOCK_DIR. Nothing here proves security by mocking: a second writer
is an actual second process, a killed holder is SIGKILLed, and stale metadata
is bytes from a dead PID.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
TOOL = [sys.executable, str(ROOT / "tools" / "foundry" / "writer_lock.py")]


def _env(lockdir: Path) -> dict:
    env = dict(os.environ)
    env["FOUNDRY_LOCK_DIR"] = str(lockdir)
    return env


def _start_holder(worktree: Path, lockdir: Path, workstream: str = "ws-test") -> subprocess.Popen:
    proc = subprocess.Popen(
        [
            *TOOL,
            "acquire",
            "--worktree",
            str(worktree),
            "--workstream",
            workstream,
            "--branch",
            "test/branch",
            "--session",
            "ses-test",
            "--hold",
        ],
        env=_env(lockdir),
        cwd=str(worktree),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    assert proc.stdout is not None
    deadline = time.time() + 10
    out = ""
    while time.time() < deadline:
        chunk = proc.stdout.readline()
        if not chunk:
            break
        out += chunk
        if "WRITER_OK" in out:
            return proc
    proc.kill()
    raise AssertionError(f"holder never acquired: {out!r}")


def _stop_holder(proc: subprocess.Popen) -> None:
    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=10)


def test_first_writer_succeeds(tmp_path: Path) -> None:
    wt = tmp_path / "wt-a"
    wt.mkdir()
    proc = _start_holder(wt, tmp_path / "locks")
    assert proc.poll() is None
    _stop_holder(proc)


def test_second_same_worktree_writer_fails_closed(tmp_path: Path) -> None:
    wt = tmp_path / "wt-a"
    wt.mkdir()
    holder = _start_holder(wt, tmp_path / "locks")
    try:
        second = subprocess.run(
            [
                *TOOL,
                "acquire",
                "--worktree",
                str(wt),
                "--workstream",
                "ws-evil",
                "--branch",
                "test/branch",
                "--hold",
            ],
            env=_env(tmp_path / "locks"),
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert second.returncode == 11, second.stdout + second.stderr
        assert "WRITER_HELD" in (second.stdout + second.stderr)
        assert "ws-test" in (second.stdout + second.stderr)
    finally:
        _stop_holder(holder)


def test_different_worktree_succeeds(tmp_path: Path) -> None:
    wa = tmp_path / "wt-a"
    wb = tmp_path / "wt-b"
    wa.mkdir()
    wb.mkdir()
    holder = _start_holder(wa, tmp_path / "locks")
    other = None
    try:
        other = _start_holder(wb, tmp_path / "locks", workstream="ws-other")
        assert other.poll() is None
    finally:
        _stop_holder(holder)
        if other is not None:
            _stop_holder(other)


def test_killed_holder_releases(tmp_path: Path) -> None:
    wt = tmp_path / "wt-a"
    wt.mkdir()
    holder = _start_holder(wt, tmp_path / "locks")
    holder.send_signal(signal.SIGKILL)
    holder.wait(timeout=10)
    # Kernel releases flock on process death: re-acquire must succeed.
    replacement = _start_holder(wt, tmp_path / "locks", workstream="ws-next")
    _stop_holder(replacement)


def test_stale_metadata_cannot_brick_worktree(tmp_path: Path) -> None:
    wt = tmp_path / "wt-a"
    wt.mkdir()
    locks = tmp_path / "locks"
    locks.mkdir()
    from tools.foundry import writer_lock as wl

    path = wl.lock_path_for(str(wt), locks)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Dead PID + no live flock: pure stale bytes.
    path.write_text(
        json.dumps(
            {
                "worktree": str(wt),
                "branch": "test/branch",
                "workstream": "ws-ghost",
                "session": "ses-ghost",
                "pid": 2**30,  # implausible live PID
                "acquired_utc": "2000-01-01T00:00:00+00:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    holder = _start_holder(wt, locks, workstream="ws-real")
    try:
        assert holder.poll() is None
    finally:
        _stop_holder(holder)


def test_symlink_alias_does_not_create_second_writer(tmp_path: Path) -> None:
    real = tmp_path / "real-wt"
    real.mkdir()
    alias = tmp_path / "alias-wt"
    alias.symlink_to(real, target_is_directory=True)
    holder = _start_holder(alias, tmp_path / "locks")
    try:
        second = subprocess.run(
            [
                *TOOL,
                "acquire",
                "--worktree",
                str(real),
                "--workstream",
                "ws-evil",
                "--branch",
                "test/branch",
            ],
            env=_env(tmp_path / "locks"),
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert second.returncode == 11, second.stdout + second.stderr
    finally:
        _stop_holder(holder)


def test_check_reports_holder_without_acquiring(tmp_path: Path) -> None:
    wt = tmp_path / "wt-a"
    wt.mkdir()
    locks = tmp_path / "locks"
    holder = _start_holder(wt, locks)
    try:
        probe = subprocess.run(
            [*TOOL, "check", "--worktree", str(wt), "--fail-if-held"],
            env=_env(locks),
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert probe.returncode == 11
        payload = json.loads(probe.stdout)
        assert payload["held"] is True
        assert payload["holder"]["workstream"] == "ws-test"
        assert payload["holder_liveness"] == "LIVE"
    finally:
        _stop_holder(holder)
    # After release the same check reports free: reader never held anything.
    probe = subprocess.run(
        [*TOOL, "check", "--worktree", str(wt)],
        env=_env(locks),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert probe.returncode == 0
    assert json.loads(probe.stdout)["held"] is False


def _fake_opencode(cwd: Path) -> subprocess.Popen:
    """Spawn a process exposing argv[0]=opencode with the given CWD.

    Uses executable= so the kernel cmdline matches exactly what a native
    `opencode` binary invoked via PATH exposes (argv[0] preserved), while
    the payload is just a sleeping interpreter.
    """
    return subprocess.Popen(
        ["opencode", "-c", "import time; time.sleep(30)"],
        executable=sys.executable,
        cwd=str(cwd),
    )


def test_scan_detects_same_cwd_opencode_process(tmp_path: Path) -> None:
    wt = tmp_path / "wt-a"
    wt.mkdir()
    sleeper = _fake_opencode(wt)
    try:
        probe = subprocess.run(
            [*TOOL, "scan", "--worktree", str(wt)],
            env=_env(tmp_path / "locks"),
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert probe.returncode == 0
        pids = [p["pid"] for p in json.loads(probe.stdout)["opencode_pids"]]
        assert sleeper.pid in pids
    finally:
        sleeper.kill()
        sleeper.wait()


def test_scan_ignores_other_cwd_and_helpers(tmp_path: Path) -> None:
    wt = tmp_path / "wt-a"
    other = tmp_path / "wt-b"
    wt.mkdir()
    other.mkdir()
    elsewhere = _fake_opencode(other)
    helper = subprocess.Popen(["sleep", "30"], cwd=str(wt))
    try:
        probe = subprocess.run(
            [*TOOL, "scan", "--worktree", str(wt)],
            env=_env(tmp_path / "locks"),
            capture_output=True,
            text=True,
            timeout=15,
        )
        pids = [p["pid"] for p in json.loads(probe.stdout)["opencode_pids"]]
        assert elsewhere.pid not in pids
        assert helper.pid not in pids
        assert pids == []
    finally:
        elsewhere.kill()
        helper.kill()
        elsewhere.wait()
        helper.wait()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
