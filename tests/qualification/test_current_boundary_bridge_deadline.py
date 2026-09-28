"""Adversarial tests for the Protocol-2 bridge deadline.

Every case here uses a real child process, because the defect being fixed is a
real blocking read against a real pipe. A mock cannot demonstrate that a stalled
child is actually terminated and reaped, so these tests spawn real processes.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from commander_lab.qualification.current_boundary import bridge_launcher as B


def _child(body: str) -> str:
    """A standalone JSONL echo/stub child script."""
    return textwrap.dedent(body)


STUB_DIR = Path(__file__).resolve().parent / "_bridge_stubs"


def _write_stub(name: str, body: str) -> Path:
    STUB_DIR.mkdir(exist_ok=True)
    path = STUB_DIR / name
    path.write_text(_child(body), encoding="utf-8")
    path.chmod(0o755)
    return path


def _respond_ok() -> str:
    return """\
        import json, sys
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            req = json.loads(line)
            sys.stdout.write(json.dumps({"request_id": req.get("request_id"),
                                         "ok": True}) + "\\n")
            sys.stdout.flush()
    """


def _spawn(script: Path) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, str(script)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )


def _session(popen: subprocess.Popen) -> B.BridgeProcess:
    # The plan is not consulted by the transport path under test; only the live
    # child, the transcript and the request/response contract matter here.
    return B.BridgeProcess(
        plan=B.LaunchPlan(
            candidate="xmage",
            lane="stub",
            argv=(),
            cwd=Path("."),
            env_overrides={},
            expected_engine_commit="0" * 40,
            build_identity={},
            workspace="",
        ),
        popen=popen,
        transcript=[],
    )


def test_normal_response_is_returned() -> None:
    script = _write_stub("ok.py", _respond_ok())
    popen = _spawn(script)
    try:
        session = _session(popen)
        response = session.request("handshake", {}, timeout_s=30.0)
        assert response["ok"] is True
    finally:
        popen.kill()
        popen.wait(timeout=5)


def test_no_output_times_out_and_terminates_child() -> None:
    script = _write_stub(
        "silent.py",
        """\
        import sys, time
        for line in sys.stdin:
            line = line.strip()
            if line:
                time.sleep(600)   # accept, then stall forever
    """,
    )
    popen = _spawn(script)
    try:
        session = _session(popen)
        started = time.monotonic()
        with pytest.raises(B.BridgeTimeout, match="classified TIMEOUT"):
            session.request("handshake", {}, timeout_s=1.0)
        elapsed = time.monotonic() - started
        assert elapsed < 20.0, "the deadline must actually bound the read"
        # The child must be dead and reaped: no zombie left behind.
        assert popen.poll() is not None, "stalled child was not terminated"
        assert popen.returncode is not None
    finally:
        if popen.poll() is None:
            popen.kill()
        popen.wait(timeout=5)


def test_child_alive_forever_times_out_and_is_reaped() -> None:
    script = _write_stub(
        "forever.py",
        """\
        import sys, time
        sys.stdin.readline()
        while True:
            time.sleep(1)     # never answers, never exits
    """,
    )
    popen = _spawn(script)
    try:
        session = _session(popen)
        with pytest.raises(B.BridgeTimeout):
            session.request("handshake", {}, timeout_s=1.0)
        assert popen.poll() is not None
    finally:
        if popen.poll() is None:
            popen.kill()
        popen.wait(timeout=5)


def test_partial_line_never_becomes_a_pass() -> None:
    """A truncated line must be a protocol failure, not a silent default."""
    script = _write_stub(
        "partial.py",
        """\
        import json, sys
        for line in sys.stdin:
            line = line.strip()
            if line:
                req = json.loads(line)
                sys.stdout.write('{"request_id": "' + str(req.get("request_id")))
                sys.stdout.flush()
    """,
    )
    popen = _spawn(script)
    try:
        session = _session(popen)
        with pytest.raises((B.BridgeTimeout, B.BridgeLaunchError)) as excinfo:
            session.request("handshake", {}, timeout_s=2.0)
        assert "PASS" not in str(excinfo.value)
    finally:
        if popen.poll() is None:
            popen.kill()
        popen.wait(timeout=5)


def test_process_exit_before_response_is_a_launch_error() -> None:
    script = _write_stub(
        "exits.py",
        """\
        import sys
        sys.stdin.readline()
        sys.exit(3)
    """,
    )
    popen = _spawn(script)
    try:
        session = _session(popen)
        with pytest.raises(B.BridgeLaunchError, match="closed stdout"):
            session.request("handshake", {}, timeout_s=10.0)
    finally:
        if popen.poll() is None:
            popen.kill()
        popen.wait(timeout=5)


def test_late_response_within_a_generous_deadline_succeeds() -> None:
    script = _write_stub(
        "late.py",
        """\
        import json, sys, time
        for line in sys.stdin:
            line = line.strip()
            if line:
                req = json.loads(line)
                time.sleep(0.5)
                sys.stdout.write(json.dumps({"request_id": req.get("request_id"),
                                             "ok": True}) + "\\n")
                sys.stdout.flush()
    """,
    )
    popen = _spawn(script)
    try:
        session = _session(popen)
        assert session.request("handshake", {}, timeout_s=30.0)["ok"] is True
    finally:
        popen.kill()
        popen.wait(timeout=5)


def test_execution_continues_after_a_timeout() -> None:
    """A stalled candidate must not prevent the next candidate from running."""
    stalled = _write_stub(
        "stall1.py",
        """\
        import sys, time
        for line in sys.stdin:
            if line.strip():
                time.sleep(600)
    """,
    )
    healthy = _write_stub("ok2.py", _respond_ok())

    first = _spawn(stalled)
    try:
        with pytest.raises(B.BridgeTimeout):
            _session(first).request("handshake", {}, timeout_s=1.0)
    finally:
        if first.poll() is None:
            first.kill()
        first.wait(timeout=5)

    second = _spawn(healthy)
    try:
        assert _session(second).request("handshake", {}, timeout_s=30.0)["ok"] is True
    finally:
        second.kill()
        second.wait(timeout=5)


def test_timeout_is_recorded_in_the_transcript() -> None:
    script = _write_stub(
        "silent2.py",
        """\
        import sys, time
        for line in sys.stdin:
            if line.strip():
                time.sleep(600)
    """,
    )
    popen = _spawn(script)
    try:
        session = _session(popen)
        with pytest.raises(B.BridgeTimeout):
            session.request("handshake", {"k": 1}, timeout_s=1.0)
        timeouts = [t for t in session.transcript if t.get("direction") == "timeout"]
        assert timeouts, "the applied timeout must be recorded as evidence"
        assert timeouts[0]["timeout_s"] == 1.0
        assert timeouts[0]["classification"] == "TIMEOUT"
        assert timeouts[0]["message_type"] == "handshake"
    finally:
        if popen.poll() is None:
            popen.kill()
        popen.wait(timeout=5)


def test_timeout_error_names_the_timeout() -> None:
    script = _write_stub(
        "silent3.py",
        """\
        import sys, time
        for line in sys.stdin:
            if line.strip():
                time.sleep(600)
    """,
    )
    popen = _spawn(script)
    try:
        with pytest.raises(B.BridgeTimeout, match=r"within 1\.0s"):
            _session(popen).request("handshake", {}, timeout_s=1.0)
    finally:
        if popen.poll() is None:
            popen.kill()
        popen.wait(timeout=5)


def test_no_zombie_remains_after_timeout() -> None:
    script = _write_stub(
        "silent4.py",
        """\
        import sys, time
        for line in sys.stdin:
            if line.strip():
                time.sleep(600)
    """,
    )
    popen = _spawn(script)
    pid = popen.pid
    try:
        with pytest.raises(B.BridgeTimeout):
            _session(popen).request("handshake", {}, timeout_s=1.0)
        # waitpid already reaped it, so the pid is gone rather than a zombie.
        assert popen.poll() is not None
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
    finally:
        if popen.poll() is None:
            popen.kill()
        popen.wait(timeout=5)
