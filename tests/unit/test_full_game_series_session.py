"""A Studio series session: one bridge JVM over many games, results on the shutdown_game ack.

Owner decision E9 (#1612): the result of a game of a Studio series rests on that game's own
acknowledged ``shutdown_game``, read fail-closed, in a result type of its own. These tests drive
the session with a scripted bridge client; the real engine is not involved (NOT_RUN here, see
the real-engine checks of the series pool).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

import pytest
from pydantic import ValidationError

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules import full_game_series
from commander_lab.engine.rules.full_game import (
    FullGameConformanceError,
    FullGameConformanceResult,
    FullGameProtocolError,
    XmageFullGameRunner,
)
from commander_lab.engine.rules.full_game_pilot.common import (
    FULL_GAME_DECISION_PROTOCOL_VERSION,
    FULL_GAME_EVIDENCE_CLASS,
    FULL_GAME_SHUTDOWN_GRACEFUL,
)
from commander_lab.engine.rules.full_game_series import (
    SERIES_JVM_GAME_CAP,
    FullGameSeriesResult,
    XmageFullGameSeriesSession,
    checked_shutdown_ack,
)

COMMIT = "a" * 40


def _scenario(seed: int) -> FutureXmageScenario:
    return FutureXmageScenario(
        candidate_id="own",
        deck_hash="d" * 64,
        opponent_deck_ids=("o1", "o2", "o3"),
        player_count=4,
        seat=1,
        scenario_id=f"studio-game-s{seed}",
        seed=seed,
        xmage_commit=COMMIT,
        bridge_version="xmage-engine-bridge-0.1.0-SNAPSHOT",
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-full-game-policy-1.0.0",
    )


def _wire(seed: int) -> dict[str, object]:
    return {
        "evidence_class": FULL_GAME_EVIDENCE_CLASS,
        "consumed_gameplay_evidence": False,
        "holdout_consumed": False,
        "official_campaign_eligible": False,
        "rules_authority": "xmage",
        "decision_policy_authority": "commander_lab_external_pilot",
        "bit_exact_replay_validated": False,
        "seed": seed,
        "terminal": True,
        "turn_number": 9,
        "decision_count": 40 + seed,
        "outcomes": [{"seat": i, "life": 10, "won": i == seed % 4} for i in range(4)],
        "transcript": [],
    }


class _Client:
    """A scripted bridge client; every instance is one JVM."""

    instances: ClassVar[list[_Client]] = []
    start_errors: ClassVar[list[Exception]] = []
    ack_for: ClassVar[Callable[[str, int], object] | None] = None

    def __init__(self, command: tuple[str, ...], **_kwargs: object) -> None:
        self.command = command
        self.requests: list[str] = []
        self.games = 0
        self.scenario: FutureXmageScenario | None = None
        self.shutdown_disposition: str | None = None
        self.closed = False
        _Client.instances.append(self)

    def start(self) -> None:
        if _Client.start_errors:
            raise _Client.start_errors.pop(0)

    def request(self, name: str, _payload: object = None) -> object:
        self.requests.append(name)
        scenario = self.scenario
        assert scenario is not None
        if name == "get_full_game_result":
            return _wire(scenario.seed)
        if name == "shutdown_game":
            self.games += 1
            game_id = f"{scenario.scenario_id}:{scenario.candidate_id}:{scenario.seed}"
            if _Client.ack_for is not None:
                return _Client.ack_for(game_id, scenario.seed)
            return {
                "game_id": game_id,
                "shut_down": True,
                "engine_thread_alive": False,
                "game_over": True,
                "shutdown_unwind": "none",
            }
        raise AssertionError(name)

    def close(self) -> str:
        self.closed = True
        return FULL_GAME_SHUTDOWN_GRACEFUL


class _Runner(XmageFullGameRunner):
    def _validated_policy(self, scenario, decks, pilots):  # type: ignore[no-untyped-def,override]
        return object()

    def _open_game(self, client, scenario, decks):  # type: ignore[no-untyped-def,override]
        client.scenario = scenario
        return {"engine_version": "1.4.61", "engine_commit": COMMIT}

    def _drive(self, client, policy, *, stop_after=None, **_kwargs):  # type: ignore[no-untyped-def,override]
        return 3, [], True


@pytest.fixture(autouse=True)
def _scripted_bridge(monkeypatch: pytest.MonkeyPatch) -> None:
    _Client.instances = []
    _Client.start_errors = []
    _Client.ack_for = None
    monkeypatch.setattr(full_game_series, "_RawFullGameClient", _Client)
    monkeypatch.setattr(full_game_series.time, "sleep", lambda _s: None)


def _session(games_per_jvm: int) -> XmageFullGameSeriesSession:
    command = (
        "java",
        f"-Dcommanderlab.fullGame.gamesPerJvm={games_per_jvm}",
        "-jar",
        "bridge.jar",
        "full-game",
    )
    return XmageFullGameSeriesSession(_Runner(command), id_prefix="t")


def _play(session: XmageFullGameSeriesSession, seed: int) -> FullGameSeriesResult | Exception:
    return session.play(_scenario(seed), (), ())


def test_one_jvm_plays_its_budget_of_games_and_every_result_rests_on_its_own_ack() -> None:
    session = _session(3)
    results = [_play(session, seed) for seed in range(1, 8)]
    lives = session.close()

    assert all(isinstance(result, FullGameSeriesResult) for result in results)
    assert [r.position_in_jvm for r in results if isinstance(r, FullGameSeriesResult)] == [
        1,
        2,
        3,
        1,
        2,
        3,
        1,
    ]
    # 7 games, budget 3: three JVM lives, the last ended by closing the series
    assert [(life.games, life.end) for life in lives] == [
        (3, "budget"),
        (3, "budget"),
        (1, "series_closed"),
    ]
    assert len(_Client.instances) == 3
    # a game's result is read after get_full_game_result and rests on the shutdown_game of that game
    first = _Client.instances[0].requests
    assert first == ["get_full_game_result", "shutdown_game"] * 3
    assert all(client.closed for client in _Client.instances)
    assert {life.disposition for life in lives} == {FULL_GAME_SHUTDOWN_GRACEFUL}


def test_the_result_is_a_type_of_its_own_and_carries_no_process_exit_claim() -> None:
    result = _play(_session(2), 5)
    assert isinstance(result, FullGameSeriesResult)
    assert not isinstance(result, FullGameConformanceResult)
    assert result.result_basis == "SHUTDOWN_GAME_ACK_NOT_PROCESS_EXIT"
    assert result.shutdown_game_ack.game_over is True
    assert "shutdown_disposition" not in FullGameSeriesResult.model_fields
    assert result.qualification_evidence is False
    assert result.semantic_transcript_sha256 and result.winner_seats == (2,)
    # consumers of the conformance type refuse it: its fields do not fit that type
    with pytest.raises(ValidationError):
        FullGameConformanceResult.model_validate(result.model_dump())
    # nor can a series result be made to claim evidence
    for flag in ("qualification_evidence", "consumed_gameplay_evidence", "holdout_consumed"):
        with pytest.raises(ValidationError):
            FullGameSeriesResult.model_validate({**result.model_dump(), flag: True})
    assert FullGameSeriesResult.model_fields["result_basis"].default != (
        FULL_GAME_DECISION_PROTOCOL_VERSION
    )


@pytest.mark.parametrize(
    "ack",
    [
        None,
        "ok",
        {"shut_down": True},
        {"game_id": "x", "shut_down": True, "engine_thread_alive": False, "game_over": True},
        {"game_id": "G", "shut_down": False, "engine_thread_alive": False, "game_over": True},
        {"game_id": "G", "shut_down": True, "engine_thread_alive": True, "game_over": True},
        {"game_id": "G", "shut_down": True, "engine_thread_alive": False, "game_over": False},
        {"game_id": "G", "shut_down": True, "engine_thread_alive": False},
    ],
)
def test_an_ack_that_is_missing_or_not_clean_gives_no_result(ack: object) -> None:
    scenario = _scenario(1)
    game_id = f"{scenario.scenario_id}:{scenario.candidate_id}:{scenario.seed}"
    if isinstance(ack, dict) and ack.get("game_id") == "G":
        ack = {**ack, "game_id": game_id}
    with pytest.raises(FullGameConformanceError):
        checked_shutdown_ack(ack, game_id=game_id)


def test_a_failed_game_discards_the_jvm_and_never_touches_earlier_results() -> None:
    session = _session(8)
    first = _play(session, 1)
    second = _play(session, 2)
    # the third game's ack says the game was not over: no result, the game fails
    _Client.ack_for = lambda game_id, _seed: {
        "game_id": game_id,
        "shut_down": True,
        "engine_thread_alive": False,
        "game_over": False,
    }
    third = _play(session, 3)
    _Client.ack_for = None
    fourth = _play(session, 4)
    lives = session.close()

    assert isinstance(first, FullGameSeriesResult) and isinstance(second, FullGameSeriesResult)
    assert isinstance(third, Exception)  # never a censored or undecided "result"
    assert isinstance(fourth, FullGameSeriesResult)
    # the finished games stand as they were; no replay of them in a JVM of their own
    assert [client.games for client in _Client.instances] == [3, 1]
    assert fourth.position_in_jvm == 1 and fourth.jvm_life_id != first.jvm_life_id
    assert [(life.games, life.end) for life in lives] == [(2, "game_failed"), (1, "series_closed")]


def test_the_budget_never_exceeds_the_cap_of_the_owner_decision() -> None:
    assert SERIES_JVM_GAME_CAP == 56
    assert _session(24).budget == 24
    assert _session(500).budget == SERIES_JVM_GAME_CAP
    assert XmageFullGameSeriesSession(_Runner(("java", "-jar", "b.jar", "full-game"))).budget == 1


def test_a_start_collision_on_the_card_repository_is_retried_in_a_fresh_jvm() -> None:
    _Client.start_errors = [
        FullGameProtocolError(
            "bridge start failed",
            code="BRIDGE_START_FAILED",
            diagnostics=("XMAGE_CARD_REPOSITORY_INIT_FAILED",),
        )
    ]
    session = _session(4)
    result = _play(session, 1)
    assert isinstance(result, FullGameSeriesResult)
    assert result.position_in_jvm == 1
    assert len(session.lives) == 1  # the JVM that never started was no life


def test_a_game_failure_that_is_not_a_collision_is_not_retried() -> None:
    _Client.start_errors = [FullGameProtocolError("no start", code="BRIDGE_START_FAILED")]
    outcome = _play(_session(4), 1)
    assert isinstance(outcome, Exception)
    assert len(_Client.instances) == 1  # one start attempt, no second JVM
