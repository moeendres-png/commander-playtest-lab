"""Shutdown-observability regression tests (P1 evidence integrity).

A bounded/live run must NOT report clean_shutdown=True merely because
close() suppressed a shutdown_engine failure and forcibly killed the JVM.
close() returns an observed disposition; run_smoke() fails closed on
anything but graceful_shutdown.
"""

from __future__ import annotations

import pytest

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules.full_game import (
    FULL_GAME_SHUTDOWN_ALREADY_EXITED,
    FULL_GAME_SHUTDOWN_FORCED_KILL,
    FULL_GAME_SHUTDOWN_GRACEFUL,
    FULL_GAME_SHUTDOWN_UNACKED_EXIT,
    FullGameConformanceError,
    XmageFullGameRunner,
    _RawFullGameClient,
)


class _FakeStream:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeProcess:
    """Scripted subprocess: poll() replays a script, then repeats last."""

    def __init__(self, poll_script: list) -> None:
        self._poll_script = list(poll_script)
        self.kill_calls = 0
        self.stdin = _FakeStream()
        self.stdout = _FakeStream()
        self.stderr = _FakeStream()

    def poll(self):  # type: ignore[no-untyped-def]
        if len(self._poll_script) > 1:
            return self._poll_script.pop(0)
        return self._poll_script[0]

    def wait(self, timeout=None):  # type: ignore[no-untyped-def]
        return None

    def kill(self) -> None:
        self.kill_calls += 1


def _client_with(process: _FakeProcess | None, *, request_ok: bool = True) -> _RawFullGameClient:
    client = _RawFullGameClient(command=("java", "-jar", "bridge.jar", "full-game"))
    client._process = process
    calls: list[str] = []

    def fake_request(message_type: str, payload=None):  # type: ignore[no-untyped-def]
        calls.append(message_type)
        if message_type == "shutdown_engine" and not request_ok:
            raise FullGameProtocolErrorShim("bridge wedged")
        return {}

    client.request = fake_request  # type: ignore[method-assign]
    client.request_calls = calls  # type: ignore[attr-defined]
    return client


class FullGameProtocolErrorShim(RuntimeError):
    pass


def test_close_graceful_when_shutdown_acked_and_clean_exit() -> None:
    process = _FakeProcess([None, None, 0])
    client = _client_with(process, request_ok=True)
    assert client.close() == FULL_GAME_SHUTDOWN_GRACEFUL
    assert process.kill_calls == 0


def test_close_forced_kill_when_process_never_exits() -> None:
    process = _FakeProcess([None, None, None])
    client = _client_with(process, request_ok=True)
    assert client.close() == FULL_GAME_SHUTDOWN_FORCED_KILL
    assert process.kill_calls == 1


def test_close_unacked_exit_when_shutdown_fails_but_process_exits() -> None:
    process = _FakeProcess([None, 0])
    client = _client_with(process, request_ok=False)
    assert client.close() == FULL_GAME_SHUTDOWN_UNACKED_EXIT
    assert process.kill_calls == 0


def test_close_already_exited_without_shutdown_request() -> None:
    process = _FakeProcess([3])
    client = _client_with(process, request_ok=True)
    assert client.close() == FULL_GAME_SHUTDOWN_ALREADY_EXITED
    assert client.request_calls == []


def test_close_without_process_is_already_exited() -> None:
    client = _client_with(None)
    assert client.close() == FULL_GAME_SHUTDOWN_ALREADY_EXITED


def _scenario() -> FutureXmageScenario:
    return FutureXmageScenario(
        candidate_id="own",
        deck_hash="ab" * 32,
        opponent_deck_ids=("opp-1", "opp-2", "opp-3"),
        player_count=4,
        seat=1,
        scenario_id="shutdown-gate",
        seed=7,
        xmage_commit="db" * 20,
        bridge_version="test",
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-full-game-policy-1.0.0",
    )


class _StubClient:
    """Transport stub with scripted shutdown disposition."""

    def __init__(self, disposition: str) -> None:
        self._disposition = disposition
        self.shutdown_disposition: str | None = None

    def __enter__(self) -> _StubClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.shutdown_disposition = self._disposition


def _run_smoke_with_disposition(monkeypatch: pytest.MonkeyPatch, disposition: str):  # type: ignore[no-untyped-def]
    import commander_lab.engine.rules.full_game as full_game_module

    runner = XmageFullGameRunner(command=("java", "-jar", "bridge.jar", "full-game"))
    monkeypatch.setattr(full_game_module, "_RawFullGameClient", lambda *a, **k: _StubClient(disposition))
    monkeypatch.setattr(
        XmageFullGameRunner,
        "_validated_policy",
        lambda self, scenario, decks, pilots: object(),
    )
    monkeypatch.setattr(
        XmageFullGameRunner,
        "_open_game",
        lambda self, client, scenario, decks: {"engine_version": "1.4.61"},
    )
    monkeypatch.setattr(
        XmageFullGameRunner,
        "_drive",
        lambda self, client, policy, stop_after=None: (5, ("priority",), False),
    )
    return runner.run_smoke(
        scenario=_scenario(), decks=(), pilots=(), smoke_decision_target=5
    )


def test_run_smoke_passes_on_graceful_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _run_smoke_with_disposition(monkeypatch, FULL_GAME_SHUTDOWN_GRACEFUL)
    assert result.clean_shutdown is True
    assert result.decision_count == 5


def test_run_smoke_fails_closed_on_forced_kill(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(FullGameConformanceError, match="not graceful"):
        _run_smoke_with_disposition(monkeypatch, FULL_GAME_SHUTDOWN_FORCED_KILL)


def test_run_smoke_fails_closed_on_unacked_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(FullGameConformanceError, match="not graceful"):
        _run_smoke_with_disposition(monkeypatch, FULL_GAME_SHUTDOWN_UNACKED_EXIT)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
