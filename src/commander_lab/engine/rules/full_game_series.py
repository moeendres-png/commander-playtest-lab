"""A Studio series session: one bridge JVM that plays several games, one after the other.

``XmageFullGameRunner.run_batch`` ends every game's result on the clean exit of the JVM that
played it, so a JVM cannot outlive the batch it was started for. A Studio series needs the
opposite: one JVM per worker for the whole series, across every look window, with the result of
a game available as soon as the game is over (Owner decision E9 / E-1a, issue #1612).

The result of a game here rests on the acknowledged ``shutdown_game`` of that game, read
fail-closed, and it is a type of its own, :class:`FullGameSeriesResult`. It is not a
``FullGameConformanceResult``: it carries no ``shutdown_disposition`` claim, evidence,
recording and qualification consumers that take the conformance type refuse it, and it says
which JVM life played the game and at which position. How a JVM life ends (budget reached, a
failed game, closing of the series) is recorded per life and never changes the results of
games that were already acknowledged.

Evidence and qualification lanes keep ``run`` and ``run_batch``; this module is for Studio
``SIMULATED_RESULT`` series only. Batched results are measurements, not qualification proof.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Final, Literal, cast

from pydantic import Field

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.models import RulesDeckInput

from .full_game import (
    _STARTUP_ATTEMPTS,
    _STARTUP_BACKOFF_SECONDS,
    FullGameConformanceError,
    FullGameHiddenInformationAudit,
    FullGamePilotBinding,
    XmageFullGameRunner,
    _is_startup_collision,
    _public_error,
    _RawFullGameClient,
)
from .full_game_batch import _games_per_jvm_permitted
from .full_game_pilot.common import (
    FULL_GAME_DECISION_PROTOCOL_VERSION,
    FULL_GAME_EVIDENCE_CLASS,
    _StrictModel,
)
from .wire_types import FullGameResultWire, ProviderIdentityWire

#: Most games one JVM life may play in a Studio series until the memory and identity of longer
#: lives are measured again (Owner decision E9). The series settings allow fewer (24).
SERIES_JVM_GAME_CAP = 56

SERIES_RESULT_BASIS: Final = "SHUTDOWN_GAME_ACK_NOT_PROCESS_EXIT"
SERIES_EVIDENCE_CLASS: Final = "studio_simulation_measurement"

JvmLifeEnd = Literal["open", "budget", "game_failed", "series_closed"]


class ShutdownGameAck(_StrictModel):
    """The fields of the bridge's ``shutdown_game`` answer that a result rests on.

    ``shutdown_unwind`` is ``"none"`` when the engine thread had already ended on its own before
    the shutdown (the game was over); any other value names the exception the thread was unwound
    with through a refused decision (``XmageFullGameSession.runEngine``), i.e. the shutdown ended
    a game that was still running. ``game_over`` cannot tell the two apart: ``shutdownGame``
    calls ``game.end()`` before it reads the flag, so the bridge always reports it true.
    """

    game_id: str = Field(min_length=1)
    shut_down: Literal[True]
    engine_thread_alive: Literal[False]
    game_over: Literal[True]
    shutdown_unwind: Literal["none"]


#: The flags of the acknowledgement that must be JSON booleans, not ``1``/``1.0``/``0``
#: (``Literal[True]`` accepts ``1`` even in strict mode).
_ACK_BOOL_FIELDS: Final = ("shut_down", "engine_thread_alive", "game_over")


class FullGameSeriesResult(_StrictModel):
    """Result of one game of a Studio series, resting on its acknowledged ``shutdown_game``.

    Deliberately not a subtype of ``FullGameConformanceResult``: that type says the game rests
    on the clean exit of its process. The base here is the game's own shutdown acknowledgement,
    read fail-closed. The flags below are fixed: this is a simulation measurement, never
    qualification, campaign or holdout evidence.
    """

    schema_version: Literal["studio-full-game-series-result-1.0.0"] = (
        "studio-full-game-series-result-1.0.0"
    )
    result_basis: Literal["SHUTDOWN_GAME_ACK_NOT_PROCESS_EXIT"] = SERIES_RESULT_BASIS
    scenario: FutureXmageScenario
    engine_version: str
    xmage_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    decision_protocol_version: str
    decision_count: int = Field(ge=0)
    terminal: Literal[True] = True
    winner_seats: tuple[int, ...]
    result_payload: dict[str, object]
    semantic_transcript_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    shutdown_game_ack: ShutdownGameAck
    jvm_life_id: str = Field(min_length=1)
    position_in_jvm: int = Field(ge=1)
    evidence_class: Literal["studio_simulation_measurement"] = SERIES_EVIDENCE_CLASS
    qualification_evidence: Literal[False] = False
    consumed_gameplay_evidence: Literal[False] = False
    holdout_consumed: Literal[False] = False
    official_campaign_eligible: Literal[False] = False
    xmage_rules_authority: Literal[True] = True
    commander_lab_pilot_decision_authority: Literal[True] = True
    fallback_used: Literal[False] = False
    bit_exact_replay_validated: Literal[False] = False
    hidden_information_audit: FullGameHiddenInformationAudit = Field(
        default_factory=FullGameHiddenInformationAudit
    )


@dataclass
class JvmLife:
    """One bridge JVM from its start to its end."""

    life_id: str
    games: int = 0
    end: JvmLifeEnd = "open"
    #: Observed way the process ended (``graceful_shutdown``, ``forced_kill``, ...), ``None``
    #: while it runs. Never read to decide a result.
    disposition: str | None = None
    started_at: float = field(default_factory=time.monotonic)

    def as_dict(self) -> dict[str, object]:
        return {
            "life_id": self.life_id,
            "games": self.games,
            "end": self.end,
            "disposition": self.disposition,
        }


def checked_shutdown_ack(raw: object, *, game_id: str) -> ShutdownGameAck:
    """The acknowledged ``shutdown_game`` answer, or ``FullGameConformanceError``.

    Fail-closed: a missing answer, ``shut_down`` not true, a live engine thread, a game that is
    not over, an engine thread that the shutdown had to unwind (``shutdown_unwind`` other than
    ``"none"``: the game was still running), a flag that is not a JSON boolean, or the answer of
    another game gives no result.
    """
    if not isinstance(raw, dict):
        raise FullGameConformanceError("shutdown_game gave no acknowledgement")
    if any(type(raw.get(name)) is not bool for name in _ACK_BOOL_FIELDS):
        raise FullGameConformanceError("shutdown_game acknowledgement is not clean")
    try:
        ack = ShutdownGameAck.model_validate(raw, strict=True)
    except ValueError as error:
        raise FullGameConformanceError("shutdown_game acknowledgement is not clean") from error
    if ack.game_id != game_id:
        raise FullGameConformanceError("shutdown_game acknowledged another game")
    return ack


def build_series_result(
    scenario: FutureXmageScenario,
    provider: ProviderIdentityWire,
    result: FullGameResultWire,
    ack: ShutdownGameAck,
    *,
    jvm_life_id: str,
    position_in_jvm: int,
    hidden_audit: FullGameHiddenInformationAudit,
) -> FullGameSeriesResult:
    """The result of a finished game, with the same checks of the engine's answer as a game
    played alone (``XmageFullGameRunner._build_result``) but resting on ``ack``."""
    if result.get("evidence_class") != FULL_GAME_EVIDENCE_CLASS:
        raise FullGameConformanceError("result evidence class is not technical conformance")
    for flag in ("consumed_gameplay_evidence", "holdout_consumed", "official_campaign_eligible"):
        if result.get(flag) is not False:
            raise FullGameConformanceError(f"unsafe full-game result flag: {flag}")
    if result.get("rules_authority") != "xmage":
        raise FullGameConformanceError("result rules authority is not XMage")
    if result.get("decision_policy_authority") != "commander_lab_external_pilot":
        raise FullGameConformanceError("result decision authority is not Commander Lab pilot")
    if result.get("bit_exact_replay_validated") is not False:
        raise FullGameConformanceError("bit-exact replay was promoted without gate")
    if result.get("seed") != scenario.seed:
        raise FullGameConformanceError("result seed mismatch")
    if result.get("terminal") is not True:
        raise FullGameConformanceError("XMage full-game did not terminate")
    outcomes = result.get("outcomes")
    if not isinstance(outcomes, list) or len(outcomes) != scenario.player_count:
        raise FullGameConformanceError("full-game result must contain one seat outcome per player")
    winner_seats = tuple(
        int(item.get("seat", -1)) + 1
        for item in outcomes
        if isinstance(item, dict) and item.get("won") is True
    )
    semantic = XmageFullGameRunner.semantic_transcript(result)
    return FullGameSeriesResult(
        scenario=scenario,
        engine_version=str(provider.get("engine_version", "unknown")),
        xmage_commit=str(provider.get("engine_commit", "")),
        decision_protocol_version=FULL_GAME_DECISION_PROTOCOL_VERSION,
        decision_count=int(cast(int, result.get("decision_count", 0))),
        winner_seats=winner_seats,
        result_payload=cast(dict[str, object], result),
        semantic_transcript_sha256=XmageFullGameRunner._sha256(semantic),
        raw_result_sha256=XmageFullGameRunner._sha256(result),
        shutdown_game_ack=ack,
        jvm_life_id=jvm_life_id,
        position_in_jvm=position_in_jvm,
        hidden_information_audit=hidden_audit,
    )


class XmageFullGameSeriesSession:
    """One worker's bridge JVM for a whole Studio series.

    ``play`` plays one game in the open JVM (starting one when there is none) and returns its
    result, or the public error of the game; it never raises for a game that went wrong. After
    a failed game the JVM is discarded and the next game starts in a fresh one, so a failed game
    takes no neighbour with it, and the results of games that finished before it stand: each
    rests on its own acknowledged ``shutdown_game``. A JVM is retired after ``budget`` games, the
    most the bridge permits for it (``-Dcommanderlab.fullGame.gamesPerJvm``, at most
    :data:`SERIES_JVM_GAME_CAP`). ``close`` ends the open JVM.

    ``runner`` supplies the engine command, the pilots' policy and the drive of a game; it is
    the same runner (or its recording subclass) a game played alone uses, so a game here is the
    game of its seed.
    """

    def __init__(self, runner: XmageFullGameRunner, *, id_prefix: str = "jvm") -> None:
        self._runner = runner
        command = runner.command
        permitted = _games_per_jvm_permitted(command) if command else 1
        self.budget = max(1, min(permitted, SERIES_JVM_GAME_CAP))
        self._id_prefix = id_prefix
        self._client: _RawFullGameClient | None = None
        self._life: JvmLife | None = None
        self._lives: list[JvmLife] = []

    @property
    def lives(self) -> tuple[JvmLife, ...]:
        return tuple(self._lives)

    def play(
        self,
        scenario: FutureXmageScenario,
        decks: tuple[RulesDeckInput, ...],
        pilots: tuple[FullGamePilotBinding, ...],
    ) -> FullGameSeriesResult | Exception:
        attempts = 0
        while True:
            attempts += 1
            first_of_life = self._life is None or self._life.games == 0
            try:
                result = self._play_one(scenario, decks, pilots)
            except Exception as exc:
                self._end_life("game_failed")
                if first_of_life and _is_startup_collision(exc) and attempts < _STARTUP_ATTEMPTS:
                    # nothing of this game exists yet: the card repository was busy, start again
                    time.sleep(_STARTUP_BACKOFF_SECONDS * attempts)
                    continue
                return _public_error(exc)
            if self._life is not None and self._life.games >= self.budget:
                self._end_life("budget")
            return result

    def close(self) -> tuple[JvmLife, ...]:
        """End the open JVM cleanly and return every life of the session."""
        self._end_life("series_closed")
        return self.lives

    def __enter__(self) -> XmageFullGameSeriesSession:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _ensure_jvm(self) -> tuple[_RawFullGameClient, JvmLife]:
        if self._client is not None and self._life is not None:
            return self._client, self._life
        command = self._runner.command
        if command is None:
            raise FullGameConformanceError("full-game bridge is not configured")
        runner = self._runner
        client = _RawFullGameClient(
            command,
            cwd=runner.cwd,
            request_timeout_seconds=runner.request_timeout_seconds,
            private_card_repository=runner.private_card_repository,
            shutdown_grace_seconds=runner.shutdown_grace_seconds,
        )
        client.start()
        life = JvmLife(life_id=f"{self._id_prefix}-{len(self._lives) + 1}")
        self._client, self._life = client, life
        self._lives.append(life)
        return client, life

    def _end_life(self, end: JvmLifeEnd) -> None:
        client, life = self._client, self._life
        self._client = self._life = None
        if client is None:
            return
        disposition = client.close()
        client.shutdown_disposition = disposition
        if life is not None:
            life.end = end
            life.disposition = disposition

    def _play_one(
        self,
        scenario: FutureXmageScenario,
        decks: tuple[RulesDeckInput, ...],
        pilots: tuple[FullGamePilotBinding, ...],
    ) -> FullGameSeriesResult:
        runner = self._runner
        policy = runner._validated_policy(scenario, decks, pilots)
        client, life = self._ensure_jvm()
        audit = FullGameHiddenInformationAudit()
        runner._hidden_audit = audit
        try:
            provider = runner._open_game(client, scenario, decks)
            _count, _, terminal = runner._drive(client, policy, stop_after=None)
        finally:
            runner._hidden_audit = None
        if terminal is not True:
            raise FullGameConformanceError("full game ended without game over")
        wire = cast(FullGameResultWire, client.request("get_full_game_result"))
        protocol_game_id = f"{scenario.scenario_id}:{scenario.candidate_id}:{scenario.seed}"
        ack = checked_shutdown_ack(client.request("shutdown_game"), game_id=protocol_game_id)
        built = build_series_result(
            scenario,
            provider,
            wire,
            ack,
            jvm_life_id=life.life_id,
            position_in_jvm=life.games + 1,
            hidden_audit=audit,
        )
        life.games += 1
        return built


__all__ = [
    "SERIES_EVIDENCE_CLASS",
    "SERIES_JVM_GAME_CAP",
    "SERIES_RESULT_BASIS",
    "FullGameSeriesResult",
    "JvmLife",
    "ShutdownGameAck",
    "XmageFullGameSeriesSession",
    "build_series_result",
    "checked_shutdown_ack",
]
