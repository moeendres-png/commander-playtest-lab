"""Transport-failure handling of the full-game bridge client.

Once a request times out, or the reply cannot be paired with its request,
the line-oriented channel is no longer trustworthy: a late reply would be
read as the answer to the next request. Before this guard, close() still
sent ``shutdown_engine`` over that channel and waited a whole request
timeout (120 s by default) for an answer a wedged JVM never gives, before
the shutdown grace and the kill. A batch paid that for every hung game.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from commander_lab.engine.rules.full_game import (
    _STDERR_BUFFER_LINES,
    FULL_GAME_SHUTDOWN_FORCED_KILL,
    FULL_GAME_SHUTDOWN_GRACEFUL,
    FullGameProtocolError,
    _RawFullGameClient,
)

# A scripted stand-in for the bridge JVM. It logs every message type it
# reads, answers start_engine and shutdown_engine at once, and handles
# "get_full_game_decision" according to MODE:
#   wedge  - never answers (a hung JVM);
#   late   - answers only after LATE_SECONDS (after the client gave up);
#   stderr - writes STDERR_LINES lines to stderr, then answers.
_FAKE_BRIDGE = """
import json, sys, time
mode, log_path, late, stderr_lines = sys.argv[1], sys.argv[2], float(sys.argv[3]), int(sys.argv[4])
def reply(request):
    print(json.dumps({"protocol_version": request["protocol_version"],
                      "request_id": request["request_id"], "success": True,
                      "status": "ok", "payload": {"type": request["message_type"]},
                      "errors": []}), flush=True)
for line in sys.stdin:
    request = json.loads(line)
    with open(log_path, "a", encoding="utf-8") as log:
        log.write(request["message_type"] + "\\n")
    if request["message_type"] != "get_full_game_decision":
        reply(request)
        if request["message_type"] == "shutdown_engine":
            break
        continue
    if mode == "wedge":
        time.sleep(3600)
    elif mode == "late":
        time.sleep(late)
        reply(request)
    else:
        for index in range(stderr_lines):
            print(f"engine log line {index}", file=sys.stderr)
        sys.stderr.flush()
        reply(request)
"""

REQUEST_TIMEOUT = 1.0
SHUTDOWN_GRACE = 0.5


def _client(
    tmp_path: Path, mode: str, *, late: float = 0.0, stderr_lines: int = 0
) -> tuple[_RawFullGameClient, Path]:
    script = tmp_path / "fake_bridge.py"
    script.write_text(_FAKE_BRIDGE, encoding="utf-8")
    log = tmp_path / "received.log"
    command = (
        sys.executable,
        str(script),
        mode,
        str(log),
        str(late),
        str(stderr_lines),
        "full-game",
    )
    client = _RawFullGameClient(
        command,
        cwd=tmp_path,
        request_timeout_seconds=REQUEST_TIMEOUT,
        shutdown_grace_seconds=SHUTDOWN_GRACE,
    )
    return client, log


def _received(log: Path) -> list[str]:
    return log.read_text(encoding="utf-8").split() if log.exists() else []


def test_a_wedged_bridge_is_killed_without_waiting_out_another_request_timeout(
    tmp_path: Path,
) -> None:
    client, log = _client(tmp_path, "wedge")
    client.start()
    assert client.request("start_engine") == {"type": "start_engine"}
    with pytest.raises(FullGameProtocolError) as caught:
        client.request("get_full_game_decision")
    assert caught.value.code == "BRIDGE_TIMEOUT"
    assert client.transport_failure == "BRIDGE_TIMEOUT"

    started = time.monotonic()
    disposition = client.close()
    elapsed = time.monotonic() - started

    assert disposition == FULL_GAME_SHUTDOWN_FORCED_KILL
    # Only the shutdown grace is spent; the old path added a full request
    # timeout for a shutdown_engine reply that never comes.
    assert elapsed < SHUTDOWN_GRACE + REQUEST_TIMEOUT
    assert _received(log) == ["start_engine", "get_full_game_decision"]


def test_a_late_reply_is_never_read_as_the_answer_to_the_next_request(tmp_path: Path) -> None:
    client, log = _client(tmp_path, "late", late=REQUEST_TIMEOUT + 0.5)
    client.start()
    client.request("start_engine")
    with pytest.raises(FullGameProtocolError) as caught:
        client.request("get_full_game_decision")
    assert caught.value.code == "BRIDGE_TIMEOUT"
    time.sleep(1.0)  # the late reply is now queued

    with pytest.raises(FullGameProtocolError) as refused:
        client.request("get_full_game_result")
    assert refused.value.code == "BRIDGE_UNUSABLE"
    client.close()
    # The refused request was never written to the bridge.
    assert "get_full_game_result" not in _received(log)


def test_a_healthy_channel_still_shuts_down_gracefully(tmp_path: Path) -> None:
    client, log = _client(tmp_path, "stderr")
    with client:
        client.request("start_engine")
        client.request("get_full_game_decision")
    assert client.transport_failure is None
    assert client.shutdown_disposition == FULL_GAME_SHUTDOWN_GRACEFUL
    assert _received(log) == ["start_engine", "get_full_game_decision", "shutdown_engine"]


def test_a_write_to_an_exited_bridge_is_a_transport_failure(tmp_path: Path) -> None:
    client, _log = _client(tmp_path, "stderr")
    client.start()
    process = client._process
    assert process is not None and process.stdin is not None

    class _BrokenPipe:
        closed = False

        def write(self, _text: str) -> int:
            raise BrokenPipeError(32, "Broken pipe")

        def flush(self) -> None:  # pragma: no cover - write fails first
            return None

        def close(self) -> None:
            self.closed = True

    real_stdin = process.stdin
    process.stdin = _BrokenPipe()  # type: ignore[assignment]
    try:
        with pytest.raises(FullGameProtocolError) as caught:
            client.request("start_engine")
        assert caught.value.code == "BRIDGE_NOT_WRITABLE"
        assert client.transport_failure == "BRIDGE_NOT_WRITABLE"
    finally:
        process.stdin = real_stdin
        client.close()


def test_bridge_stderr_kept_in_memory_is_bounded(tmp_path: Path) -> None:
    lines = 5 * _STDERR_BUFFER_LINES
    client, _log = _client(tmp_path, "stderr", stderr_lines=lines)
    with client:
        client.request("start_engine")
        client.request("get_full_game_decision")
        deadline = time.monotonic() + 10
        while (
            not client.stderr_tail or client.stderr_tail[-1] != f"engine log line {lines - 1}"
        ) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert len(client._stderr_lines) <= _STDERR_BUFFER_LINES
        assert client.stderr_tail[-1] == f"engine log line {lines - 1}"
        assert len(client.stderr_tail) == 80
