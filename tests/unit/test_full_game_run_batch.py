from __future__ import annotations

from typing import Any, ClassVar

import pytest

from commander_lab.engine.rules import full_game, full_game_batch
from commander_lab.engine.rules.full_game import (
    FULL_GAME_SHUTDOWN_GRACEFUL,
    FullGameConformanceError,
    FullGameProtocolError,
    XmageFullGameRunner,
)


class _FakeClient:
    instances: ClassVar[list[_FakeClient]] = []

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        self.requests: list[str] = []
        self.shutdown_disposition: str | None = None
        _FakeClient.instances.append(self)

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.shutdown_disposition = FULL_GAME_SHUTDOWN_GRACEFUL

    def request(self, message_type: str) -> dict[str, Any]:
        self.requests.append(message_type)
        return {}


def test_a_failed_game_moves_the_rest_to_a_fresh_process(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeClient.instances = []
    monkeypatch.setattr(full_game, "_RawFullGameClient", _FakeClient)
    runner = XmageFullGameRunner(("java", "-jar", "x.jar", "full-game"))
    monkeypatch.setattr(runner, "_validated_policy", lambda scenario, *_: scenario)
    monkeypatch.setattr(runner, "_open_game", lambda *_: {})

    def drive(_client: Any, policy: str, **_kwargs: Any) -> tuple[int, Any, bool]:
        if policy == "bad":
            raise FullGameConformanceError("engine failure")
        return 1, None, True

    monkeypatch.setattr(runner, "_drive", drive)
    monkeypatch.setattr(
        XmageFullGameRunner,
        "_build_result",
        classmethod(
            lambda _cls, scenario, *_args, shutdown_disposition, **_kw: (
                scenario,
                shutdown_disposition,
            )
        ),
    )
    games: Any = [("a", (), ()), ("bad", (), ()), ("c", (), ())]
    outcomes = runner.run_batch(games)

    assert outcomes[0] == ("a", FULL_GAME_SHUTDOWN_GRACEFUL)
    assert isinstance(outcomes[1], FullGameConformanceError)
    assert outcomes[2] == ("c", FULL_GAME_SHUTDOWN_GRACEFUL)
    assert len(_FakeClient.instances) == 2
    assert _FakeClient.instances[0].requests == ["get_full_game_result", "shutdown_game"]


class _KilledClient(_FakeClient):
    """The process the first instances start ends the way ``dispositions`` says."""

    dispositions: ClassVar[list[str]] = []

    def __exit__(self, *_args: object) -> None:
        self.shutdown_disposition = self.dispositions[len(_FakeClient.instances) - 1]


def _runner_with_killed_processes(
    monkeypatch: pytest.MonkeyPatch, dispositions: list[str]
) -> XmageFullGameRunner:
    _FakeClient.instances = []
    _KilledClient.dispositions = dispositions
    monkeypatch.setattr(full_game, "_RawFullGameClient", _KilledClient)
    runner = XmageFullGameRunner(("java", "-jar", "x.jar", "full-game"))
    monkeypatch.setattr(runner, "_validated_policy", lambda scenario, *_: scenario)
    monkeypatch.setattr(runner, "_open_game", lambda *_: {})

    def drive(_client: Any, policy: str, **_kwargs: Any) -> tuple[int, Any, bool]:
        if policy == "hang":
            raise FullGameConformanceError("bridge closed")
        return 1, None, True

    def build(_cls: Any, scenario: Any, *_args: Any, shutdown_disposition: str, **_kw: Any) -> Any:
        if shutdown_disposition != FULL_GAME_SHUTDOWN_GRACEFUL:
            raise FullGameConformanceError(
                f"full game shutdown not graceful: {shutdown_disposition}"
            )
        return scenario

    monkeypatch.setattr(runner, "_drive", drive)
    monkeypatch.setattr(XmageFullGameRunner, "_build_result", classmethod(build))
    return runner


def test_games_finished_before_a_hang_are_played_again_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # process 1 plays a and b, then hangs on "hang" and is killed; a and b are replayed in
    # processes 2 and 3, c runs in process 4
    runner = _runner_with_killed_processes(
        monkeypatch, ["forced_kill", *[FULL_GAME_SHUTDOWN_GRACEFUL] * 3]
    )
    games: Any = [("a", (), ()), ("b", (), ()), ("hang", (), ()), ("c", (), ())]
    outcomes = runner.run_batch(games)

    assert outcomes[:2] == ["a", "b"]
    assert isinstance(outcomes[2], FullGameConformanceError)
    assert outcomes[3] == "c"
    assert len(_FakeClient.instances) == 4


def test_a_replayed_game_that_cannot_shut_down_cleanly_is_not_replayed_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _runner_with_killed_processes(monkeypatch, ["forced_kill", "unacked_exit"])
    games: Any = [("a", (), ()), ("hang", (), ())]
    outcomes = runner.run_batch(games)

    assert isinstance(outcomes[0], FullGameConformanceError)
    assert "shutdown not graceful" in str(outcomes[0])
    assert isinstance(outcomes[1], FullGameConformanceError)
    assert len(_FakeClient.instances) == 2


def test_an_unclean_exit_without_a_failed_game_still_fails_every_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _runner_with_killed_processes(monkeypatch, ["unacked_exit"])
    games: Any = [("a", (), ()), ("b", (), ())]
    outcomes = runner.run_batch(games)

    assert all(
        isinstance(outcome, FullGameConformanceError) and "shutdown not graceful" in str(outcome)
        for outcome in outcomes
    )
    assert len(_FakeClient.instances) == 1


def _collision() -> FullGameProtocolError:
    return FullGameProtocolError(
        "start_game failed",
        code="BRIDGE_ERROR",
        diagnostics=("deck_import_failed", "XMAGE_CARD_REPOSITORY_INIT_FAILED"),
    )


def _runner_opening_games(
    monkeypatch: pytest.MonkeyPatch, opens: list[Exception | None]
) -> tuple[XmageFullGameRunner, list[float]]:
    """Each game opening takes the next entry of ``opens``: an exception is raised, None passes."""
    _FakeClient.instances = []
    monkeypatch.setattr(full_game, "_RawFullGameClient", _FakeClient)
    sleeps: list[float] = []
    monkeypatch.setattr(full_game.time, "sleep", sleeps.append)
    runner = XmageFullGameRunner(("java", "-jar", "x.jar", "full-game"))
    monkeypatch.setattr(runner, "_validated_policy", lambda scenario, *_: scenario)
    calls = iter(opens)

    def open_game(*_args: Any) -> dict[str, Any]:
        failure = next(calls, None)
        if failure is not None:
            raise failure
        return {}

    monkeypatch.setattr(runner, "_open_game", open_game)
    monkeypatch.setattr(runner, "_drive", lambda *_a, **_k: (1, None, True))
    monkeypatch.setattr(
        XmageFullGameRunner,
        "_build_result",
        classmethod(lambda _cls, scenario, *_args, **_kw: scenario),
    )
    return runner, sleeps


def test_a_start_up_collision_on_the_first_game_starts_it_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner, sleeps = _runner_opening_games(monkeypatch, [_collision(), _collision()])
    games: Any = [("a", (), ()), ("b", (), ())]
    outcomes = runner.run_batch(games)

    assert outcomes == ["a", "b"]
    assert len(_FakeClient.instances) == 3  # two collided starts, then one process for both
    assert sleeps == [3.0, 6.0]


def test_a_start_up_collision_that_does_not_go_away_stays_a_failed_game(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner, sleeps = _runner_opening_games(monkeypatch, [_collision()] * 4)
    games: Any = [("a", (), ()), ("b", (), ())]
    outcomes = runner.run_batch(games)

    assert isinstance(outcomes[0], FullGameProtocolError)
    assert outcomes[1] == "b"
    assert len(_FakeClient.instances) == 5  # four starts of a, then one process for b
    assert sleeps == [3.0, 6.0, 9.0]


def test_other_failures_and_later_games_are_not_started_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    other = FullGameProtocolError("start_game failed", code="BRIDGE_ERROR", diagnostics=("x",))
    # a fails for another reason; b (first game of the next process) is fine; c collides after
    # b played in the same process, which is no start-up collision
    runner, sleeps = _runner_opening_games(monkeypatch, [other, None, _collision()])
    games: Any = [("a", (), ()), ("b", (), ()), ("c", (), ())]
    outcomes = runner.run_batch(games)

    assert isinstance(outcomes[0], FullGameProtocolError)
    assert outcomes[1] == "b"
    assert isinstance(outcomes[2], FullGameProtocolError)
    assert sleeps == []
    assert len(_FakeClient.instances) == 2  # a alone, then b and c in the next process


def test_the_start_up_retry_matches_the_batch_runner() -> None:
    assert full_game._STARTUP_COLLISION_CODES == full_game_batch._STARTUP_RETRY_CODES
    assert full_game._STARTUP_ATTEMPTS == full_game_batch._STARTUP_ATTEMPTS
    assert full_game._STARTUP_BACKOFF_SECONDS == full_game_batch._STARTUP_BACKOFF_SECONDS
