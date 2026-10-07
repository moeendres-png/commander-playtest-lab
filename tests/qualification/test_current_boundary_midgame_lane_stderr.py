"""The mid-game lane drains stderr with the shared bounded drain (#580, #561).

The lane used to drain its child's stderr with a blocking ``readline``: a single
endless diagnostic line was buffered without bound before its newline, and a
descendant that inherited the pipe could pin the drain thread forever after the
direct child exited. These tests bind the lane to the shared bounded,
non-blocking drain (``bridge_launcher.StderrDrain``): bounded ``os.read`` chunks
behind ``select``, incremental decoding, a stop flag and a grace join.
"""

from __future__ import annotations

import contextlib
import os
import signal
import sys
import threading
import time
from pathlib import Path

from commander_lab.qualification.current_boundary import bridge_launcher as B
from commander_lab.qualification.current_boundary import midgame_lane as ml

# A child that answers every request, framed exactly as the lane's transport
# reads it. It is only ever a transport stub: no engine semantics are claimed.
_ANSWER_LOOP = """\
import json, sys
for raw in sys.stdin:
    line = raw.strip()
    if not line:
        continue
    req = json.loads(line)
    sys.stdout.write(json.dumps({"request_id": req["request_id"], "ok": True}) + "\\n")
    sys.stdout.flush()
    if req["message_type"] == "shutdown_engine":
        break
"""


def _stub(tmp_path: Path, body: str) -> Path:
    script = tmp_path / "stub_midgame_lane.py"
    script.write_text(body, encoding="utf-8")
    return script


def _line_stub(tmp_path: Path, line: str) -> Path:
    return _stub(
        tmp_path,
        f"import sys\nsys.stderr.write({line!r})\nsys.stderr.flush()\n" + _ANSWER_LOOP,
    )


def _client(script: Path) -> ml.MidgameLaneClient:
    return ml.MidgameLaneClient((sys.executable, str(script)), script.parent)


def test_a_blocked_or_long_line_does_not_stall_the_child(tmp_path, monkeypatch) -> None:
    """A line far longer than the pipe buffer must not block the child.

    The old blocking ``readline`` held the whole line in an unbounded buffer;
    once the child had written more than the pipe capacity it blocked forever
    and never answered the request.
    """
    # Chunk the drain so the test also exercises the bounded read itself.
    monkeypatch.setattr(B, "STDERR_READ_CHUNK_BYTES", 4096)
    line = "x" * 1_500_000
    script = _line_stub(tmp_path, line)
    with _client(script) as client:
        started = time.monotonic()
        assert client.request("handshake", {}, timeout_s=20)["ok"] is True
        assert time.monotonic() - started < 20.0
    # The whole unterminated line is retained (well under the lane's cap).
    assert client.stderr_log == line


def test_a_long_unterminated_line_is_visible_while_the_child_is_alive(
    tmp_path, monkeypatch
) -> None:
    """The bounded drain exposes chunks before a newline ever arrives.

    A blocking ``readline`` keeps the partial line inside its own buffer, so the
    lane's log stayed empty while the child was alive; the shared drain appends
    every bounded chunk it reads.
    """
    monkeypatch.setattr(B, "STDERR_READ_CHUNK_BYTES", 4096)
    line = "y" * 200_000
    script = _line_stub(tmp_path, line)
    with _client(script) as client:
        assert client.request("handshake", {}, timeout_s=20)["ok"] is True
        deadline = time.monotonic() + 5.0
        while client.stderr_log != line and time.monotonic() < deadline:
            time.sleep(0.01)
        assert client.stderr_log == line


def test_a_truncating_tail_capture_is_visible_and_not_scannable(tmp_path, monkeypatch) -> None:
    """A tail capture that dropped its oldest chunks must report the gap.

    The lane keeps the newest stderr for the end-of-run log scan, so beyond the
    retention cap it drops the oldest text. Before this fix that loss was
    invisible: the capture reported itself complete and untruncated, and the
    hidden-information scan could treat the gap as a complete log.
    """
    monkeypatch.setattr(B, "STDERR_READ_CHUNK_BYTES", 64)
    monkeypatch.setattr(ml.MidgameLaneClient, "STDERR_RETENTION_CHARS", 128, raising=False)
    script = _line_stub(tmp_path, "first\n" + "z" * 4096 + "\nlast\n")
    with _client(script) as client:
        assert client.request("handshake", {}, timeout_s=20)["ok"] is True
    drain = client._stderr_drain
    assert drain is not None
    # Behavioral red on the pre-fix drain: tail drops were never marked.
    assert drain.capture().truncated is True
    capture = client.stderr_capture()
    assert capture.complete is True
    assert capture.truncated is True
    assert capture.scannable is False
    assert capture.text.endswith("last\n")
    assert "first" not in capture.text
    # stderr_log still exposes the retained text, never a completeness claim.
    assert client.stderr_log == capture.text


def test_close_releases_both_read_ends(tmp_path) -> None:
    """The lane's close must not retain the stdout/stderr read descriptors.

    The drain owns stderr until it stops; stdout has no other reader after the
    child exits. Both read ends used to stay open until the client was
    collected.
    """
    script = _line_stub(tmp_path, "hello\n")
    client = _client(script)
    with client:
        assert client.request("handshake", {}, timeout_s=20)["ok"] is True
        process = client._process
    assert process is not None
    assert process.stdout is not None and process.stdout.closed
    assert process.stderr is not None and process.stderr.closed


_DESCENDANT_BODY = """\
import json, os, subprocess, sys
descendant = subprocess.Popen(
    [sys.executable, "-c", "import time; time.sleep(300)"],
    stdin=subprocess.DEVNULL,
    stdout=subprocess.DEVNULL,
)
with open(os.path.join(os.path.dirname(__file__), "descendant.pid"), "w") as pid:
    pid.write(str(descendant.pid))
# stderr is inherited: the descendant holds the pipe after this process exits.
sys.stderr.write("[lane] starting\\n")
sys.stderr.flush()
for raw in sys.stdin:
    line = raw.strip()
    if not line:
        continue
    req = json.loads(line)
    sys.stdout.write(json.dumps({"request_id": req["request_id"], "ok": True}) + "\\n")
    sys.stdout.flush()
    if req["message_type"] == "shutdown_engine":
        break
"""


def test_close_reclaims_a_drain_a_descendant_holds_open(tmp_path, monkeypatch) -> None:
    """The close/join path stops a drain the direct child's descendant holds open.

    The direct child exits, but its sleeping descendant inherited the stderr
    pipe. A blocking ``readline`` thread would stay blocked on that pipe for the
    life of the test process; ``close`` must stop and reclaim it after the grace.
    """
    monkeypatch.setattr(ml, "STDERR_DRAIN_GRACE_S", 0.2, raising=False)
    script = _stub(tmp_path, _DESCENDANT_BODY)
    pid_file = tmp_path / "descendant.pid"
    client = _client(script)
    try:
        with client:
            assert client.request("handshake", {}, timeout_s=20)["ok"] is True
        # The direct child is gone; the descendant still holds stderr open. No
        # live drain thread may remain: the old blocking ``readline`` stayed
        # pinned on the inherited pipe past close.
        assert not any(
            thread.name == "midgame-lane-stderr" and thread.is_alive()
            for thread in threading.enumerate()
        )
        drain = client._stderr_drain
        assert drain is not None
        assert drain.draining is False
        assert client.stderr_log == "[lane] starting\n"
    finally:
        if pid_file.exists():
            with contextlib.suppress(ProcessLookupError, ValueError):
                os.kill(int(pid_file.read_text(encoding="utf-8")), signal.SIGTERM)
