"""An interrupted parallel batch stops its bridge JVMs at once.

Before, Ctrl-C during ``_run_parallel`` left the ``with executor`` block,
which waits for every game in flight to finish: with hung or long games the
batch sat there for minutes, and each game still ran its own close path.
Now the interrupt drops queued games and kills the live bridge processes,
so the games in flight fail fast and nothing in flight becomes a record.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from commander_lab.engine.rules import full_game, full_game_batch
from commander_lab.engine.rules.full_game import FullGameProtocolError, _RawFullGameClient

# Answers start_engine, then never answers anything else (a hung game). Before it
# hangs it drops a marker file, so the test knows the game is blocked in that request.
_WEDGED_BRIDGE = """
import json, os, sys, time
from pathlib import Path
for line in sys.stdin:
    request = json.loads(line)
    if request["message_type"] == "start_engine":
        print(json.dumps({"protocol_version": request["protocol_version"],
                          "request_id": request["request_id"], "success": True,
                          "status": "ok", "payload": {}, "errors": []}), flush=True)
        continue
    (Path(__file__).parent / f"hung-{os.getpid()}").touch()
    time.sleep(3600)
"""

GAMES = 3
REQUEST_TIMEOUT = 120.0


def _live_clients() -> list[_RawFullGameClient]:
    with full_game._LIVE_CLIENTS_LOCK:
        return list(full_game._LIVE_CLIENTS)


def test_interrupting_a_parallel_batch_kills_games_in_flight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = tmp_path / "wedged_bridge.py"
    script.write_text(_WEDGED_BRIDGE, encoding="utf-8")
    clients: list[_RawFullGameClient] = []
    failures: list[str] = []
    interrupted_at: list[float] = []

    def play_hung_game(*_: Any) -> Any:
        client = _RawFullGameClient(
            (sys.executable, str(script), "full-game"),
            cwd=tmp_path,
            request_timeout_seconds=REQUEST_TIMEOUT,
            shutdown_grace_seconds=0.5,
        )
        clients.append(client)
        with client:
            client.request("start_engine")
            try:
                client.request("get_full_game_decision")
            except FullGameProtocolError as error:
                failures.append(error.code)
                raise
        raise AssertionError("a hung game never finishes")

    def interrupt_once_all_games_run(futures: Any) -> Iterator[Any]:
        # Interrupt only once every bridge holds its unanswered request: a game
        # still starting would fail with another code (BRIDGE_EXITED/UNUSABLE) or
        # outside the try block, depending on timing.
        deadline = time.monotonic() + 60
        while len(list(tmp_path.glob("hung-*"))) < GAMES and time.monotonic() < deadline:
            time.sleep(0.05)
        assert len(list(tmp_path.glob("hung-*"))) == GAMES
        assert len(_live_clients()) == GAMES
        interrupted_at.append(time.monotonic())
        raise KeyboardInterrupt
        yield  # pragma: no cover - makes this a generator like as_completed

    monkeypatch.setattr(full_game_batch, "execute_batch_case", play_hung_game)
    monkeypatch.setattr(full_game_batch, "as_completed", interrupt_once_all_games_run)
    runner: Any = SimpleNamespace()
    batch = full_game_batch.XmageFullGameBatchRunner(runner, tmp_path / "records")
    pending: list[Any] = [
        (index, SimpleNamespace(), f"key-{index}", {}, tmp_path / "records" / f"{index}.json")
        for index in range(GAMES)
    ]

    with pytest.raises(KeyboardInterrupt):
        list(batch._run_parallel(pending, GAMES, "thread"))
    # Without the kill this waits out REQUEST_TIMEOUT for every hung game.
    assert interrupted_at, "the batch was interrupted"
    assert time.monotonic() - interrupted_at[0] < REQUEST_TIMEOUT / 4
    assert len(clients) == GAMES
    assert sorted(failures) == ["BRIDGE_CLOSED"] * GAMES
    assert all(client._process is None for client in clients)
    assert _live_clients() == []
    assert not (tmp_path / "records").exists()


def test_kill_live_bridge_processes_ignores_finished_clients(tmp_path: Path) -> None:
    assert full_game.kill_live_bridge_processes() == 0
