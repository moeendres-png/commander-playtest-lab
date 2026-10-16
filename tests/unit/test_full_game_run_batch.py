from __future__ import annotations

from typing import Any, ClassVar

import pytest

from commander_lab.engine.rules import full_game
from commander_lab.engine.rules.full_game import (
    FULL_GAME_SHUTDOWN_GRACEFUL,
    FullGameConformanceError,
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
