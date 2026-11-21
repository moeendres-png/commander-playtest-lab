"""A Studio series session: one bridge JVM over many games, results on the shutdown_game ack.

Owner decision E9 (#1612): the result of a game of a Studio series rests on that game's own
acknowledged ``shutdown_game``, read fail-closed, in a result type of its own. These tests drive
the session with a scripted bridge client; the real engine is not involved (NOT_RUN here, see
the real-engine checks of the series pool).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import ClassVar, cast

import pytest
from pydantic import ValidationError

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules import full_game, full_game_series
from commander_lab.engine.rules.full_game import (
    FullGameConformanceError,
    FullGameConformanceResult,
    FullGameMatch,
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
from commander_lab.engine.rules.wire_types import FullGameResultWire
from tests.unit.test_ws223_cardinality_regression import _priority_pass_request

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
    monkeypatch.setattr(full_game, "_RawFullGameClient", _Client)
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


def _clean_ack(game_id: str) -> dict[str, object]:
    """What the bridge answers after a game that ended on its own (``shutdown_unwind`` none)."""
    return {
        "game_id": game_id,
        "shut_down": True,
        "engine_thread_alive": False,
        "game_over": True,
        "shutdown_unwind": "none",
    }


def _game_id(seed: int) -> str:
    scenario = _scenario(seed)
    return f"{scenario.scenario_id}:{scenario.candidate_id}:{scenario.seed}"


def test_a_clean_ack_of_a_game_that_ended_on_its_own_is_accepted() -> None:
    ack = checked_shutdown_ack(_clean_ack(_game_id(1)), game_id=_game_id(1))
    assert ack.shutdown_unwind == "none" and ack.game_over is True


_MISSING = object()


# Each case differs from a clean ack in exactly the named field, so each fails for its own reason.
@pytest.mark.parametrize(
    ("case", "change"),
    [
        ("other_game", {"game_id": "x"}),
        ("not_shut_down", {"shut_down": False}),
        ("engine_thread_alive", {"engine_thread_alive": True}),
        ("shutdown_unwind_missing", {"shutdown_unwind": _MISSING}),
        ("shutdown_unwind_null", {"shutdown_unwind": None}),
        ("shut_down_as_int", {"shut_down": 1}),
        ("shut_down_as_float", {"shut_down": 1.0}),
        ("engine_thread_alive_as_int", {"engine_thread_alive": 0}),
        ("game_over_as_int", {"game_over": 1}),
        ("game_id_as_int", {"game_id": 7}),
        ("extra_field", {"surprise": True}),
    ],
)
def test_an_ack_that_is_not_clean_gives_no_result(case: str, change: dict[str, object]) -> None:
    game_id = _game_id(1)
    ack: dict[str, object] = _clean_ack(game_id)
    for key, value in change.items():
        if value is _MISSING:
            ack.pop(key)
        else:
            ack[key] = value
    with pytest.raises(FullGameConformanceError):
        checked_shutdown_ack(ack, game_id=game_id)


@pytest.mark.parametrize("ack", [None, "ok", [], {"shut_down": True}])
def test_a_missing_ack_gives_no_result(ack: object) -> None:
    with pytest.raises(FullGameConformanceError):
        checked_shutdown_ack(ack, game_id=_game_id(1))


@pytest.mark.parametrize(
    "unwind",
    [
        "IllegalStateException: FULL_GAME_SHUT_DOWN: decision intake was shut down",
        "DecisionException: FULL_GAME_SHUT_DOWN",
        "",
    ],
)
def test_an_ack_whose_engine_thread_was_unwound_by_the_shutdown_gives_no_result(
    unwind: str,
) -> None:
    """P2-1: the shutdown ended a game that was still running; the bridge still says game_over.

    ``XmageFullGameSession.shutdownGame`` calls ``game.end()`` before it reads ``isGameOver()``,
    so ``game_over`` is true in every ack the bridge sends. Only ``shutdown_unwind`` tells a game
    that ended on its own (``"none"``) from one the shutdown cut off (the unwinding exception).
    """
    game_id = _game_id(1)
    with pytest.raises(FullGameConformanceError):
        checked_shutdown_ack({**_clean_ack(game_id), "shutdown_unwind": unwind}, game_id=game_id)


def test_structure_only_an_ack_with_game_over_false_gives_no_result() -> None:
    """Structure test only: the real bridge cannot send ``game_over: false`` (see above)."""
    game_id = _game_id(1)
    with pytest.raises(FullGameConformanceError):
        checked_shutdown_ack({**_clean_ack(game_id), "game_over": False}, game_id=game_id)


def test_a_failed_game_discards_the_jvm_and_never_touches_earlier_results() -> None:
    session = _session(8)
    first = _play(session, 1)
    second = _play(session, 2)
    # the third game's shutdown had to unwind the engine thread (the bridge still says
    # game_over true): no result, the game fails
    _Client.ack_for = lambda game_id, _seed: {
        **_clean_ack(game_id),
        "shutdown_unwind": "IllegalStateException: FULL_GAME_SHUT_DOWN",
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


# --- P2-3: every consumer of single-game evidence refuses the series result type at runtime -----


def _series_result_for(scenario: FutureXmageScenario) -> FullGameSeriesResult:
    """A valid series result for ``scenario``, built without any bridge."""
    from commander_lab.engine.rules.full_game import FullGameHiddenInformationAudit

    wire = {
        **_wire(scenario.seed),
        "outcomes": [{"seat": i, "life": 10, "won": i == 0} for i in range(scenario.player_count)],
    }
    game_id = f"{scenario.scenario_id}:{scenario.candidate_id}:{scenario.seed}"
    return full_game_series.build_series_result(
        scenario,
        {"engine_version": "1.4.61", "engine_commit": COMMIT},  # type: ignore[typeddict-item]
        wire,  # type: ignore[arg-type]
        checked_shutdown_ack(_clean_ack(game_id), game_id=game_id),
        jvm_life_id="t-1",
        position_in_jvm=1,
        hidden_audit=FullGameHiddenInformationAudit(),
    )


def _comparison_setup():  # type: ignore[no-untyped-def]
    from commander_lab.engine.rules.full_game_comparison import plan_comparison_cases
    from tests.unit.test_comparison_finishing_order import _spec

    spec = _spec((1, 2))
    return spec, plan_comparison_cases(spec)


class _SeriesReturningRunner:
    """An evidence-lane runner that (wrongly) hands back a Studio series result."""

    command: tuple[str, ...] = ()
    cwd = None
    max_decisions = None
    request_timeout_seconds = None

    def __init__(self, result: FullGameSeriesResult) -> None:
        self._result = result

    def run(self, *, scenario: object, decks: object, pilots: object) -> object:
        return self._result

    def run_batch(self, games: list[object]) -> list[object]:
        return [self._result for _ in games]


def test_the_evidence_runner_refuses_a_series_result_loudly_for_one_game() -> None:
    from commander_lab.engine.rules.full_game_batch import (
        execute_batch_case,
        execution_identity_of,
    )

    _spec, cases = _comparison_setup()
    case = cases[0]
    runner = _SeriesReturningRunner(_series_result_for(case.scenario))
    # without the check the record's validation error would become a quiet failed record
    with pytest.raises(TypeError, match="FullGameSeriesResult"):
        execute_batch_case(runner, case, "0" * 64, execution_identity_of(runner))  # type: ignore[arg-type]


def test_the_evidence_runner_refuses_a_series_result_in_a_chunk() -> None:
    from commander_lab.engine.rules.full_game_batch import (
        execute_batch_chunk,
        execution_identity_of,
    )

    _spec, cases = _comparison_setup()
    case = cases[0]
    runner = _SeriesReturningRunner(_series_result_for(case.scenario))
    with pytest.raises(TypeError, match="FullGameSeriesResult"):
        execute_batch_chunk(runner, [case], ["0" * 64], execution_identity_of(runner))  # type: ignore[arg-type]


def test_the_comparison_refuses_a_series_result_even_in_an_unvalidated_record() -> None:
    from commander_lab.engine.rules.full_game_batch import FullGameBatchRecord
    from commander_lab.engine.rules.full_game_comparison import aggregate_comparison
    from tests.unit.test_comparison_finishing_order import _outcome, _records, _report

    spec, cases = _comparison_setup()
    script = {
        (case.scenario.candidate_id, case.scenario.seed): (
            (1,),
            [_outcome(1, won=True)] + [_outcome(s, lost=True, lost_on_turn=5) for s in (2, 3, 4)],
        )
        for case in cases
    }
    records = _records(cases, script)
    aggregate_comparison(spec, _report(records))  # the evidence-lane records are counted
    # a series result cannot enter a record through validation ...
    with pytest.raises(ValidationError):
        FullGameBatchRecord(
            case_id=cases[0].case_id,
            run_key="0" * 64,
            status="completed",
            elapsed_seconds=1.0,
            result=_series_result_for(cases[0].scenario),  # type: ignore[arg-type]
        )
    # ... and one that slips in unvalidated is refused before it is counted
    smuggled = records[0].model_copy(update={"result": _series_result_for(cases[0].scenario)})
    with pytest.raises(TypeError, match="FullGameSeriesResult"):
        aggregate_comparison(spec, _report([smuggled, *records[1:]]))


def _script_module(name: str):  # type: ignore[no-untyped-def]
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_qualification_rows_refuse_a_series_result() -> None:
    """``qualify_game_batching`` turns every outcome into a row through ``bench._row_of``."""
    bench = _script_module("benchmark_xmage_full_games")
    with pytest.raises(TypeError, match="FullGameSeriesResult"):
        bench._row_of(_series_result_for(_scenario(1)))
    assert bench._row_of(RuntimeError("x"))["status"] == "failed"


def test_the_real_deck_gate_refuses_a_series_result() -> None:
    from scripts import run_real_deck_gate as gate

    with pytest.raises(TypeError, match="FullGameSeriesResult"):
        gate.summarize_result(_series_result_for(_scenario(1)), "gate")


# --- the runner's public step sequence (D-3, Refs #1663) -------------------------------------------


class _StepClient(_Client):
    """Answers every step of the public sequence and records the payload it was sent."""

    #: the engine's event tape; ``export_event_log`` cuts it like the bridge (``after_offset``)
    tape: ClassVar[list[dict[str, int]]] = [{"n": 0}, {"n": 1}, {"n": 2}]
    #: replaces the ``export_event_log`` answer when set (malformed answers)
    event_answer: ClassVar[object] = None
    #: the decision every status step returns, when set
    decision: ClassVar[dict[str, object] | None] = None
    #: the engine failure every status step reports, when set
    failure: ClassVar[dict[str, object] | None] = None

    def __init__(self, command: tuple[str, ...], **kwargs: object) -> None:
        super().__init__(command, **kwargs)
        self.sent: list[tuple[str, object]] = []
        self.started = False

    def start(self) -> None:
        self.started = True

    def request(self, name: str, payload: object = None) -> object:
        self.sent.append((name, payload))
        if name == "export_event_log":
            if _StepClient.event_answer is not None:
                return _StepClient.event_answer
            assert isinstance(payload, dict)
            after = payload["after_offset"]
            tape = _StepClient.tape
            if not 0 <= after <= len(tape):
                # XmageFullGameSession.eventLogPayload refuses it; the client raises
                raise FullGameProtocolError("INVALID_EVENT_OFFSET", code="BRIDGE_ERROR")
            return {"after_offset": after, "latest_offset": len(tape), "events": tape[after:]}
        if name in {"get_full_game_result", "shutdown_game"}:
            return super().request(name, payload)
        if _StepClient.failure is not None:
            return {"step": name, "failure": _StepClient.failure}
        if _StepClient.decision is not None:
            return {"step": name, "decision": _StepClient.decision}
        return {"step": name}


@pytest.fixture(autouse=True)
def _reset_step_client() -> None:
    _StepClient.event_answer = None
    _StepClient.decision = None
    _StepClient.failure = None


def test_the_public_steps_send_exactly_their_protocol_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(full_game, "_RawFullGameClient", _StepClient)
    runner = _Runner(("java", "-jar", "bridge.jar", "full-game"))
    scenario = _scenario(7)
    policy = runner.decision_policy(scenario, (), ())
    with runner.open_session() as bridge:
        client = bridge.client
        assert isinstance(client, _StepClient) and client.started
        game = bridge.create_game(scenario, (), policy)
        # create_game goes through the runner's own _open_game hook (here: the test override)
        assert client.scenario == scenario and game.provider["engine_commit"] == COMMIT
        assert game.game_id == "studio-game-s7:own:7" and game.policy is policy
        assert game.start() == {"step": "start_full_game"}
        assert game.next_decision() == {"step": "get_full_game_decision"}
        assert game.answer({"selected_option_ids": ["a"]}) == {"step": "submit_full_game_decision"}
        assert game.concede_offer("p1") == {"step": "get_concede_offer"}
        assert game.concede("p1") == {"step": "submit_concede"}
        assert game.result()["seed"] == 7
        assert isinstance(game.shutdown(), dict)
    assert client.sent == [
        ("start_full_game", None),
        ("get_full_game_decision", None),
        ("submit_full_game_decision", {"response": {"selected_option_ids": ["a"]}}),
        ("get_concede_offer", {"player_id": "p1"}),
        ("submit_concede", {"proposal": {"actor_id": "p1", "player_id": "p1"}}),
        ("get_full_game_result", None),
        ("shutdown_game", None),
    ]
    assert client.closed and bridge.shutdown_disposition == FULL_GAME_SHUTDOWN_GRACEFUL


def _game(runner: XmageFullGameRunner | None = None) -> FullGameMatch:
    runner = runner or _Runner(("java", "-jar", "bridge.jar", "full-game"))
    return runner.open_session().create_game(_scenario(1), (), object())


@pytest.mark.parametrize(
    ("offset", "expected"),
    [(0, [0, 1, 2]), (2, [2]), (3, [])],
)
def test_events_are_cut_by_the_engine_after_an_offset(
    monkeypatch: pytest.MonkeyPatch, offset: int, expected: list[int]
) -> None:
    monkeypatch.setattr(full_game, "_RawFullGameClient", _StepClient)
    game = _game()
    page = game.events(offset)
    assert [event["n"] for event in page.events] == expected
    assert page.latest_offset == 3
    client = game._session.client
    assert isinstance(client, _StepClient)
    assert client.sent == [("export_event_log", {"after_offset": offset})]


def test_events_past_the_end_are_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(full_game, "_RawFullGameClient", _StepClient)
    with pytest.raises(FullGameProtocolError):
        _game().events(4)


@pytest.mark.parametrize(
    "answer",
    [
        {"latest_offset": 3},
        {"events": "x", "latest_offset": 3},
        # no events at the offset itself: only the list check can refuse these (B13)
        {"latest_offset": 1},
        {"events": None, "latest_offset": 1},
        {"events": [], "latest_offset": None},
        {"events": [], "latest_offset": 3.0},
        {"events": [{"n": 2}], "latest_offset": 1},
        {"events": [], "latest_offset": 3},
        # a JSON boolean is not an offset, even where True == 1 would fit the length
        {"events": [], "latest_offset": True},
    ],
)
def test_a_malformed_event_answer_is_an_error_not_an_empty_page(
    monkeypatch: pytest.MonkeyPatch, answer: dict[str, object]
) -> None:
    monkeypatch.setattr(full_game, "_RawFullGameClient", _StepClient)
    _StepClient.event_answer = answer
    with pytest.raises(FullGameProtocolError) as raised:
        _game().events(1)
    assert raised.value.code == "INVALID_RESPONSE"


@pytest.mark.parametrize("offset", [-1, True])
def test_events_refuse_a_bad_offset(monkeypatch: pytest.MonkeyPatch, offset: int) -> None:
    monkeypatch.setattr(full_game, "_RawFullGameClient", _StepClient)
    with pytest.raises(ValueError, match="offset"):
        _game().events(offset)


_STATUS_STEPS = ["start", "next_decision", "answer", "concede"]


def _call(game: FullGameMatch, step: str) -> dict[str, object]:
    if step == "answer":
        return cast(dict[str, object], game.answer({}))
    if step == "concede":
        return cast(dict[str, object], game.concede("p1"))
    return cast(dict[str, object], getattr(game, step)())


def _leaky(decision_id: str = "engine-1") -> dict[str, object]:
    frame = _priority_pass_request(4, 1)
    frame["decision_id"] = decision_id
    frame["pilot_state"]["players"][2]["hand"] = [{"object_id": "x", "name": "Hidden Card"}]
    return frame


@pytest.mark.parametrize("step", _STATUS_STEPS)
def test_every_status_step_audits_its_decision_frame(
    monkeypatch: pytest.MonkeyPatch, step: str
) -> None:
    monkeypatch.setattr(full_game, "_RawFullGameClient", _StepClient)
    _StepClient.decision = _priority_pass_request(4, 1)
    game = _game()
    status = _call(game, step)
    assert status["decision"] == _StepClient.decision
    audit = game.hidden_audit
    assert (audit.frames_audited, audit.non_actor_rows_audited) == (1, 3)


@pytest.mark.parametrize("step", _STATUS_STEPS)
def test_a_leaking_frame_from_a_step_fails_closed(
    monkeypatch: pytest.MonkeyPatch, step: str
) -> None:
    """Leak test: another player's hidden hand in a frame read through a step is an error."""
    monkeypatch.setattr(full_game, "_RawFullGameClient", _StepClient)
    _StepClient.decision = _leaky()
    game = _game()
    with pytest.raises(FullGameConformanceError) as raised:
        _call(game, step)
    # the public message is redacted; it names the audit, never the card
    assert str(raised.value).startswith("hidden information not actor-scoped")
    assert "Hidden Card" not in str(raised.value)
    assert game.hidden_audit.frames_audited == 0


def test_a_concede_that_answers_with_a_leaking_frame_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The bridge answers submit_concede with the next open decision; it is audited too."""
    monkeypatch.setattr(full_game, "_RawFullGameClient", _StepClient)
    _StepClient.decision = _priority_pass_request(4, 1)
    game = _game()
    game.start()
    _StepClient.decision = _leaky("engine-2")
    with pytest.raises(FullGameConformanceError):
        game.concede("p1")
    assert game.hidden_audit.frames_audited == 1


@pytest.mark.parametrize("step", _STATUS_STEPS)
def test_an_engine_failure_in_a_step_raises_redacted(
    monkeypatch: pytest.MonkeyPatch, step: str
) -> None:
    monkeypatch.setattr(full_game, "_RawFullGameClient", _StepClient)
    _StepClient.failure = {"message": "java.lang.IllegalStateException: Secret Card Name"}
    with pytest.raises(FullGameConformanceError) as raised:
        _call(_game(), step)
    assert str(raised.value).startswith("engine failed: ENGINE_FAILURE")
    assert "Secret Card Name" not in str(raised.value)


def test_a_decision_read_again_is_checked_again_but_counted_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(full_game, "_RawFullGameClient", _StepClient)
    _StepClient.decision = _priority_pass_request(4, 1)
    game = _game()
    game.start()
    game.next_decision()
    game.next_decision()
    assert game.hidden_audit.frames_audited == 1
    # the same decision id delivered again with a leak still fails closed
    _StepClient.decision = _leaky("engine-1")
    with pytest.raises(FullGameConformanceError):
        game.next_decision()


def test_step_audit_counters_reach_the_conformance_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(full_game, "_RawFullGameClient", _StepClient)
    _StepClient.decision = _priority_pass_request(4, 1)
    game = _game()
    game.start()
    second = _priority_pass_request(4, 2)
    _StepClient.decision = second
    game.next_decision()
    game.next_decision()  # the same open decision: no second count
    wire = cast(FullGameResultWire, {**_wire(1), "transcript": []})
    # the result rests on the session's own process end: none before it is closed
    with pytest.raises(FullGameConformanceError):
        game.conformance_result(wire)
    game._session.close()
    result = game.conformance_result(wire)
    assert result.hidden_information_audit.frames_audited == 2
    assert result.claim_basis.hidden_information_actor_scoped == "OBSERVED"


_ALREADY_STARTED = re.escape(
    str(FullGameConformanceError("full game already started in this match"))
)


def test_a_match_is_started_once(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(full_game, "_RawFullGameClient", _StepClient)
    started = _game()
    started.start()
    with pytest.raises(FullGameConformanceError, match=_ALREADY_STARTED):
        started.drive()
    with pytest.raises(FullGameConformanceError, match=_ALREADY_STARTED):
        started.start()
    driven = _game()
    driven.drive()
    with pytest.raises(FullGameConformanceError, match=_ALREADY_STARTED):
        driven.start()


class _AuditingRunner(_Runner):
    """Drives two clean frames through the armed audit, as the real drive loop does."""

    def _drive(self, client, policy, *, stop_after=None, **_kwargs):  # type: ignore[no-untyped-def]
        audit = self._hidden_audit
        assert audit is not None
        audit.frames_audited += 2
        audit.non_actor_rows_audited += 6
        return 2, [], True


def test_the_series_result_carries_the_audit_of_its_drive() -> None:
    session = XmageFullGameSeriesSession(
        _AuditingRunner(("java", "-jar", "bridge.jar", "full-game")), id_prefix="t"
    )
    result = _play(session, 3)
    session.close()
    assert isinstance(result, FullGameSeriesResult)
    assert result.hidden_information_audit.frames_audited == 2
    assert result.hidden_information_audit.non_actor_rows_audited == 6


class _NotTerminalRunner(_Runner):
    def _drive(self, client, policy, *, stop_after=None, **_kwargs):  # type: ignore[no-untyped-def]
        return 3, [], False


def test_a_game_that_did_not_reach_game_over_gives_no_result() -> None:
    session = XmageFullGameSeriesSession(
        _NotTerminalRunner(("java", "-jar", "bridge.jar", "full-game")), id_prefix="t"
    )
    result = _play(session, 3)
    lives = session.close()
    refused = FullGameConformanceError("full game ended without game over")
    assert str(result) == str(full_game.public_error(refused))
    # no result was read and the JVM of the failed game was discarded
    assert _Client.instances[0].requests == []
    assert [life.end for life in lives] == ["game_failed"]


class _CheckedRunner(_Runner):
    """The runner's own input check (no test double for it)."""

    _validated_policy = XmageFullGameRunner._validated_policy


def test_the_inputs_are_checked_before_any_jvm_starts() -> None:
    session = XmageFullGameSeriesSession(
        _CheckedRunner(("java", "-jar", "bridge.jar", "full-game")), id_prefix="t"
    )
    result = _play(session, 3)  # four seats, no decks: the runner's own check refuses it
    assert isinstance(result, FullGameConformanceError)
    refused = FullGameConformanceError(
        "deck/pilot cardinality must equal the scenario player count"
    )
    assert str(result) == str(full_game.public_error(refused))
    assert _Client.instances == []
    assert session.close() == ()


def test_drive_arms_the_hidden_information_audit_only_while_it_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(full_game, "_RawFullGameClient", _StepClient)
    seen: list[object] = []

    class _AuditRunner(_Runner):
        def _drive(self, client, policy, *, stop_after=None, **_kwargs):  # type: ignore[no-untyped-def]
            seen.append(self._hidden_audit)
            raise FullGameProtocolError("boom", code="ENGINE_FAILURE")

    runner = _AuditRunner(("java", "-jar", "bridge.jar", "full-game"))
    game = runner.open_session().create_game(_scenario(1), (), object())
    with pytest.raises(FullGameProtocolError):
        game.drive()
    assert seen == [game.hidden_audit] and runner._hidden_audit is None


def test_a_bridge_session_needs_a_configured_command() -> None:
    runner = _Runner(("java",))
    runner.command = None
    with pytest.raises(FullGameConformanceError, match="not configured"):
        runner.open_session()
