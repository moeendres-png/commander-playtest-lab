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


class _ScriptedHookClient:
    """Minimal scripted client exercising the real ``_drive`` loop and ``after_drive`` hook."""

    script_queue: ClassVar[list[list[dict[str, object]]]] = []
    instances: ClassVar[list[_ScriptedHookClient]] = []

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        self._responses = list(self.script_queue.pop(0))
        self.requests: list[str] = []
        self.shutdown_disposition: str | None = None
        _ScriptedHookClient.instances.append(self)

    def start(self) -> None:
        pass

    def close(self) -> str:
        self.shutdown_disposition = FULL_GAME_SHUTDOWN_GRACEFUL
        return FULL_GAME_SHUTDOWN_GRACEFUL

    def __enter__(self) -> _ScriptedHookClient:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def request(
        self, message_type: str, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        del payload
        self.requests.append(message_type)
        if message_type == "get_full_game_result":
            return {
                "evidence_class": full_game.FULL_GAME_EVIDENCE_CLASS,
                "consumed_gameplay_evidence": False,
                "holdout_consumed": False,
                "official_campaign_eligible": False,
                "rules_authority": "xmage",
                "decision_policy_authority": "commander_lab_external_pilot",
                "bit_exact_replay_validated": False,
                "seed": 17,
                "turn_number": 2,
                "decision_count": 1,
                "terminal": True,
                "transcript": [
                    {
                        "sequence": 1,
                        "kind": "decision",
                        "decision_class": "priority",
                        "actor_seat": 0,
                        "prompt": "Pass priority",
                        "selected_option_types": ["pass"],
                        "selected_option_labels": ["Pass"],
                        "numeric_choice": None,
                    }
                ],
                "outcomes": [
                    {"seat": 0, "life": 40, "won": True, "lost": False, "left": False},
                    {"seat": 1, "life": 0, "won": False, "lost": True, "left": False},
                ],
            }
        if message_type == "shutdown_game":
            return {"shut_down": True}
        if message_type == "export_event_log":
            return {"events": [{"sequence": 1, "turn": 1, "step": "MAIN1", "kind": "pass"}]}
        return self._responses.pop(0)


def _minimal_decision(turn: int = 1) -> dict[str, object]:
    return {
        "decision_id": f"d-{turn}",
        "actor_id": "p0",
        "decision_class": "priority",
        "seat": 0,
        "legal_options": [{"option_id": "pass", "label": "Pass", "option_type": "pass"}],
        "pilot_state": {
            "seat": 0,
            "turn_number": turn,
            "phase": "main1",
            "step": "precombat_main",
            "players": [
                {
                    "player_id": "p0",
                    "seat": 0,
                    "is_actor": True,
                    "life": 40,
                    "hand": [],
                    "battlefield": [],
                    "graveyard": [],
                },
                {
                    "player_id": "p1",
                    "seat": 1,
                    "is_actor": False,
                    "life": 40,
                    "hand_count": 7,
                    "battlefield": [],
                    "graveyard": [],
                },
            ],
        },
    }


_HOOK_COMMIT = "a" * 40


def _hook_scenario() -> Any:
    from commander_lab.candidates.models import FutureXmageScenario

    return FutureXmageScenario(
        candidate_id="deck-a",
        deck_hash="d" * 64,
        opponent_deck_ids=("deck-b",),
        player_count=2,
        seat=1,
        scenario_id="hook-sc",
        seed=17,
        xmage_commit=_HOOK_COMMIT,
        bridge_version="xmage-engine-bridge-0.1.0-SNAPSHOT",
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-full-game-policy-1.0.0",
    )


class _PassPolicy:
    def decide(self, decision: dict[str, object]) -> dict[str, object]:
        return {
            "decision_id": decision["decision_id"],
            "selected_option_ids": ["pass"],
        }


class _WrappingPolicy:
    def __init__(self, inner: full_game.FullGameDecisionPolicy, seen: list[str]) -> None:
        self._inner = inner
        self._seen = seen

    def decide(self, decision: dict[str, object]) -> dict[str, object]:
        self._seen.append(str(decision["decision_id"]))
        return self._inner.decide(decision)


class _PublicHookRunner(XmageFullGameRunner):
    """Subclass overriding only public hooks (``decision_policy`` and ``after_drive``)."""

    def __init__(self, command: tuple[str, ...]) -> None:
        super().__init__(command)
        self.policy_calls = 0
        self.decisions_seen: list[str] = []
        self.after_drive_calls: list[tuple[bool, list[str]]] = []

    def decision_policy(
        self, scenario: Any, decks: Any, pilots: Any
    ) -> full_game.FullGameDecisionPolicy:
        self.policy_calls += 1
        inner = super().decision_policy(scenario, decks, pilots)
        return _WrappingPolicy(inner, self.decisions_seen)

    def after_drive(self, client: full_game.FullGameBridgeClient, *, terminal: bool) -> None:
        requests = getattr(client, "requests", [])
        self.after_drive_calls.append((terminal, list(requests)))
        client.request("export_event_log")


def test_public_hooks_fire_on_all_paths_and_preserve_transcript_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#1731: ``decision_policy`` and ``after_drive`` cover ``run``, ``run_batch``, ``run_smoke``
    (all 4 normal return paths of ``_drive``) and ``FullGameMatch.drive``, skip on exceptions,
    and preserve identical transcript/raw result hashes."""
    cmd = ("java", "-jar", "x.jar", "full-game")
    scenario = _hook_scenario()
    provider: Any = {"engine_version": "1.4.61", "engine_commit": _HOOK_COMMIT}
    monkeypatch.setattr(full_game, "_RawFullGameClient", _ScriptedHookClient)

    def wire_runner(runner: XmageFullGameRunner) -> None:
        monkeypatch.setattr(runner, "_validated_policy", lambda *_a: _PassPolicy())
        monkeypatch.setattr(runner, "_open_game", lambda *_a, **_k: provider)

    # 1. Equivalence: bare runner vs public-hook subclass on run()
    bare = XmageFullGameRunner(cmd)
    hooked = _PublicHookRunner(cmd)
    wire_runner(bare)
    wire_runner(hooked)
    _ScriptedHookClient.instances = []
    _ScriptedHookClient.script_queue = [
        [{"decision": _minimal_decision(1)}, {"terminal": True}],
        [{"decision": _minimal_decision(1)}, {"terminal": True}],
    ]
    bare_res = bare.run(scenario=scenario, decks=(), pilots=())
    hooked_res = hooked.run(scenario=scenario, decks=(), pilots=())
    assert hooked_res.semantic_transcript_sha256 == bare_res.semantic_transcript_sha256
    assert hooked_res.raw_result_sha256 == bare_res.raw_result_sha256
    assert hooked.policy_calls == 1
    assert hooked.decisions_seen == ["d-1"]
    assert hooked.after_drive_calls == [(True, ["start_full_game", "submit_full_game_decision"])]
    assert _ScriptedHookClient.instances[1].requests == [
        "start_full_game",
        "submit_full_game_decision",
        "export_event_log",
        "get_full_game_result",
    ]

    # 2. run_batch(): decision_policy + after_drive before get_full_game_result & shutdown_game
    batch_runner = _PublicHookRunner(cmd)
    wire_runner(batch_runner)
    _ScriptedHookClient.instances = []
    _ScriptedHookClient.script_queue = [
        [{"decision": _minimal_decision(1)}, {"terminal": True}],
    ]
    batch_outcomes = batch_runner.run_batch([(scenario, (), ())])
    assert len(batch_outcomes) == 1
    assert not isinstance(batch_outcomes[0], Exception)
    assert batch_outcomes[0].semantic_transcript_sha256 == bare_res.semantic_transcript_sha256
    assert batch_runner.policy_calls == 1
    assert [t for t, _ in batch_runner.after_drive_calls] == [True]
    assert _ScriptedHookClient.instances[0].requests == [
        "start_full_game",
        "submit_full_game_decision",
        "export_event_log",
        "get_full_game_result",
        "shutdown_game",
    ]

    # 3. run_smoke(): all 3 non-terminal return paths (stop_at_turn, decision stop_after, tail stop_after)
    for label, script, stop_at_turn in (
        (
            "turn_boundary",
            [{"decision": _minimal_decision(1)}, {"decision": _minimal_decision(2)}],
            2,
        ),
        (
            "decision_limit_on_decision",
            [{"decision": _minimal_decision(1)}, {"decision": _minimal_decision(1)}],
            None,
        ),
        (
            "decision_limit_after_empty_status",
            [{"decision": _minimal_decision(1)}, {}],
            None,
        ),
    ):
        smoke_runner = _PublicHookRunner(cmd)
        wire_runner(smoke_runner)
        _ScriptedHookClient.instances = []
        _ScriptedHookClient.script_queue = [script]
        smoke_res = smoke_runner.run_smoke(
            scenario=scenario,
            decks=(),
            pilots=(),
            smoke_decision_target=1,
            stop_at_turn=stop_at_turn,
        )
        assert smoke_res.terminal_reached is False, label
        assert smoke_runner.policy_calls == 1, label
        assert [t for t, _ in smoke_runner.after_drive_calls] == [False], label

    # 4. FullGameMatch.drive(): calls after_drive on terminal
    match_runner = _PublicHookRunner(cmd)
    wire_runner(match_runner)
    _ScriptedHookClient.instances = []
    _ScriptedHookClient.script_queue = [
        [{"decision": _minimal_decision(1)}, {"terminal": True}],
    ]
    policy = match_runner.decision_policy(scenario, (), ())
    with match_runner.open_session() as session:
        match = session.create_game(scenario, (), policy)
        count, _classes, terminal = match.drive()
    assert (count, terminal) == (1, True)
    assert [t for t, _ in match_runner.after_drive_calls] == [True]

    # 5. Exception in _drive: after_drive MUST NOT fire
    failing_runner = _PublicHookRunner(cmd)
    wire_runner(failing_runner)
    _ScriptedHookClient.instances = []
    _ScriptedHookClient.script_queue = [[{"failure": {"code": "ENGINE_FAILURE"}}]]
    with pytest.raises(FullGameConformanceError):
        failing_runner.run(scenario=scenario, decks=(), pilots=())
    assert failing_runner.after_drive_calls == []
