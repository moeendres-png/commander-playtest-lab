from __future__ import annotations

import copy
import hashlib
import json
import multiprocessing
import os
import threading
import time
from collections.abc import Iterator
from concurrent.futures import (
    Executor,
    Future,
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    as_completed,
)
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, Protocol, TypedDict

from pydantic import BaseModel, ConfigDict, Field, model_validator

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.models import RulesDeckInput

from .base import resolve_engine_working_directory
from .failure_privacy import redacted_exception_message
from .full_game import (
    FULL_GAME_DECISION_PROTOCOL_VERSION,
    FULL_GAME_EVIDENCE_CLASS,
    FullGameConformanceError,
    FullGameConformanceResult,
    FullGamePilotBinding,
    FullGameProtocolError,
    XmageFullGameRunner,
    kill_live_bridge_processes,
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FullGameFailureClass(StrEnum):
    CONFIGURATION = "configuration"
    PROTOCOL = "protocol"
    CONFORMANCE = "conformance"
    ENGINE = "engine"


class FullGameBatchCase(_StrictModel):
    case_id: str = Field(min_length=1)
    scenario: FutureXmageScenario
    decks: tuple[RulesDeckInput, ...]
    pilots: tuple[FullGamePilotBinding, ...]

    @model_validator(mode="after")
    def case_matches_operational_scope(self) -> FullGameBatchCase:
        player_count = self.scenario.player_count
        if player_count < 2 or player_count > 6:
            raise ValueError("full-game batch cases require two to six players")
        if len(self.decks) != player_count or len(self.pilots) != player_count:
            raise ValueError("full-game batch deck/pilot cardinality must equal player count")
        if {pilot.seat for pilot in self.pilots} != set(range(1, player_count + 1)):
            raise ValueError("full-game batch cases require pilot seats 1..N exactly")
        return self


class FullGameBatchRecord(_StrictModel):
    schema_version: Literal["xmage-full-game-batch-record-1.0.0"] = (
        "xmage-full-game-batch-record-1.0.0"
    )
    case_id: str
    run_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["completed", "failed"]
    elapsed_seconds: float = Field(ge=0.0)
    resumed_from_completed_record: bool = False
    result: FullGameConformanceResult | None = None
    failure_class: FullGameFailureClass | None = None
    failure_message: str | None = None
    evidence_class: Literal["technical_conformance_only"] = FULL_GAME_EVIDENCE_CLASS
    consumed_gameplay_evidence: Literal[False] = False
    holdout_consumed: Literal[False] = False
    official_campaign_eligible: Literal[False] = False
    canonical_data_mutated: Literal[False] = False

    @model_validator(mode="after")
    def coherent_status(self) -> FullGameBatchRecord:
        if self.status == "completed":
            if (
                self.result is None
                or self.failure_class is not None
                or self.failure_message is not None
            ):
                raise ValueError("completed batch record requires result and no failure")
        elif self.result is not None or self.failure_class is None or not self.failure_message:
            raise ValueError("failed batch record requires classified failure and no result")
        return self


class FullGameBatchReport(_StrictModel):
    schema_version: Literal["xmage-full-game-batch-report-1.0.0"] = (
        "xmage-full-game-batch-report-1.0.0"
    )
    total_cases: int = Field(ge=0)
    completed_cases: int = Field(ge=0)
    failed_cases: int = Field(ge=0)
    resumed_cases: int = Field(ge=0)
    records: tuple[FullGameBatchRecord, ...]
    evidence_class: Literal["technical_conformance_only"] = FULL_GAME_EVIDENCE_CLASS
    one_isolated_jvm_per_executed_game: Literal[True] = True
    # C3: the three flags above are the runner's design (a fresh bridge process
    # per executed game, content-addressed reuse, retry only on request),
    # enforced by this module's code path; they are not measured per batch.
    claim_basis: Literal["CODE_DERIVED"] = "CODE_DERIVED"
    idempotent_completed_run_reuse: Literal[True] = True
    failed_runs_retry_only_when_requested: Literal[True] = True
    consumed_gameplay_evidence: Literal[False] = False
    holdout_consumed: Literal[False] = False
    official_campaign_eligible: Literal[False] = False
    canonical_data_mutated: Literal[False] = False

    @model_validator(mode="after")
    def coherent_counts(self) -> FullGameBatchReport:
        completed = sum(record.status == "completed" for record in self.records)
        failed = sum(record.status == "failed" for record in self.records)
        resumed = sum(record.resumed_from_completed_record for record in self.records)
        if self.total_cases != len(self.records):
            raise ValueError("total_cases must match the number of records")
        if self.completed_cases != completed:
            raise ValueError("completed_cases must match completed records")
        if self.failed_cases != failed:
            raise ValueError("failed_cases must match failed records")
        if self.resumed_cases != resumed:
            raise ValueError("resumed_cases must match resumed records")
        if self.completed_cases + self.failed_cases != self.total_cases:
            raise ValueError("every full-game batch record must be completed or failed")
        return self


class _GameRunner(Protocol):
    def run(
        self,
        *,
        scenario: FutureXmageScenario,
        decks: tuple[RulesDeckInput, ...],
        pilots: tuple[FullGamePilotBinding, ...],
    ) -> FullGameConformanceResult: ...


BatchParallelism = Literal["thread", "process"]


class ExecutionIdentity(TypedDict):
    """JSON shape of :func:`execution_identity_of`; it enters every run key."""

    execution_identity_version: int
    decision_protocol_version: str
    result_schema_version: str
    runner_configuration_sha256: str
    bridge_artifacts: dict[str, str]


# SHA-256 of a bridge artifact by (resolved path, size, mtime_ns): the ~79 MB
# jar is read once per batch rather than once per case lookup. A file whose
# size or modification time changed is hashed again.
_ARTIFACT_DIGESTS: dict[tuple[str, int, int], str] = {}
_ARTIFACT_DIGESTS_LOCK = threading.Lock()


def _artifact_sha256(path: Path) -> str:
    resolved = path.resolve()
    with resolved.open("rb") as handle:
        stat = os.fstat(handle.fileno())
        key = (str(resolved), stat.st_size, stat.st_mtime_ns)
        with _ARTIFACT_DIGESTS_LOCK:
            cached = _ARTIFACT_DIGESTS.get(key)
        if cached is not None:
            return cached
        digest = hashlib.sha256()
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    result = digest.hexdigest()
    with _ARTIFACT_DIGESTS_LOCK:
        for stale in [k for k in _ARTIFACT_DIGESTS if k[0] == key[0]]:
            del _ARTIFACT_DIGESTS[stale]
        _ARTIFACT_DIGESTS[key] = result
    return result


def execution_identity_of(runner: Any) -> ExecutionIdentity:
    """What executes a case beyond its own inputs (D2).

    A completed record may be reused only by a run that would execute the
    same bytes: the decision protocol, the result schema and the SHA-256 of
    every bridge artifact file named by the runner's command. A rebuilt
    bridge jar therefore invalidates earlier completed records instead of
    silently lending them to a different build. Recomputed at each lookup
    and checked again before a newly executed result may be completed.

    Command and cwd are digested, never copied into public records. Artifact
    keys are command positions so equal basenames cannot overwrite each
    other. This binds explicit .jar/.py tokens, not an arbitrary JVM's whole
    environment or transitive classpath. Executed artifacts must stay stable
    throughout a game; before/after checks detect persistent drift, not a
    malicious change-and-restore between checks.
    """
    artifacts: dict[str, str] = {}
    identity_unavailable = False
    configuration = b""
    try:
        cwd = Path(resolve_engine_working_directory(getattr(runner, "cwd", None)) or ".").resolve()
        command = tuple(getattr(runner, "command", None) or ())
        for position, token in enumerate(command):
            path = Path(token)
            if path.suffix in {".jar", ".py"}:
                if not path.is_absolute():
                    path = cwd / path
                artifacts[str(position)] = _artifact_sha256(path)
        configuration = json.dumps(
            {
                "command": command,
                "cwd": str(cwd),
                "max_decisions": getattr(runner, "max_decisions", None),
                "request_timeout_seconds": getattr(runner, "request_timeout_seconds", None),
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode()
    except (OSError, ValueError, TypeError, RuntimeError):
        identity_unavailable = True
    if identity_unavailable:
        # Raise outside the handler: even implicit exception context must
        # not retain an engine-local path, diagnostic, notes or traceback.
        raise ValueError("full-game batch execution identity unavailable")
    return {
        "execution_identity_version": 2,
        "decision_protocol_version": FULL_GAME_DECISION_PROTOCOL_VERSION,
        "result_schema_version": FullGameConformanceResult.model_fields["schema_version"].default,
        "runner_configuration_sha256": hashlib.sha256(configuration).hexdigest(),
        "bridge_artifacts": artifacts,
    }


def execute_batch_case(
    runner: _GameRunner,
    case: FullGameBatchCase,
    run_key: str,
    execution: ExecutionIdentity,
) -> FullGameBatchRecord:
    """Play one case in its own bridge process and classify the outcome.

    Module-level so a process worker can run it: every argument is plain data
    or a picklable runner. Only the four documented failure families become a
    failed record; anything else is a defect of the Lab and propagates.
    """
    started = time.monotonic()
    try:
        result = _run_with_startup_retry(runner, case)
        if execution_identity_of(runner) != execution:
            raise ValueError("full-game batch execution identity changed during game")
        return FullGameBatchRecord(
            case_id=case.case_id,
            run_key=run_key,
            status="completed",
            elapsed_seconds=time.monotonic() - started,
            result=result,
        )
    except FullGameProtocolError as exc:
        return _failed_record(case, run_key, started, FullGameFailureClass.PROTOCOL, exc)
    except FullGameConformanceError as exc:
        return _failed_record(case, run_key, started, FullGameFailureClass.CONFORMANCE, exc)
    except (OSError, ValueError) as exc:
        return _failed_record(case, run_key, started, FullGameFailureClass.CONFIGURATION, exc)
    except RuntimeError as exc:
        return _failed_record(case, run_key, started, FullGameFailureClass.ENGINE, exc)


# XMage's card repository is an on-disk database every bridge JVM scans at
# startup. JVMs starting at the same moment can collide on it and fail deck
# import before any game exists (#731: 1-2 of 6 games at 4-6 workers). That
# failure says nothing about the game, so the case is started again; any
# other failure, and this one after the last attempt, stays a failed record.
_STARTUP_RETRY_CODES = frozenset({"XMAGE_CARD_REPOSITORY_INIT_FAILED"})
_STARTUP_ATTEMPTS = 4
_STARTUP_BACKOFF_SECONDS = 3.0


def _is_startup_collision(exc: FullGameProtocolError) -> bool:
    diagnostics = getattr(exc, "diagnostics", ()) or ()
    return any(str(item) in _STARTUP_RETRY_CODES for item in diagnostics)


def _run_with_startup_retry(
    runner: _GameRunner, case: FullGameBatchCase
) -> FullGameConformanceResult:
    for attempt in range(1, _STARTUP_ATTEMPTS + 1):
        try:
            return runner.run(scenario=case.scenario, decks=case.decks, pilots=case.pilots)
        except FullGameProtocolError as exc:
            if attempt == _STARTUP_ATTEMPTS or not _is_startup_collision(exc):
                raise
            time.sleep(_STARTUP_BACKOFF_SECONDS * attempt)
    raise AssertionError("unreachable")  # pragma: no cover


def _failed_record(
    case: FullGameBatchCase,
    run_key: str,
    started: float,
    failure_class: FullGameFailureClass,
    exc: Exception,
) -> FullGameBatchRecord:
    return FullGameBatchRecord(
        case_id=case.case_id,
        run_key=run_key,
        status="failed",
        elapsed_seconds=time.monotonic() - started,
        failure_class=failure_class,
        failure_message=redacted_exception_message(exc),
    )


class XmageFullGameBatchRunner:
    """Correctness-first batch layer around the one-process/one-game runner.

    A completed record is content-addressed by all scenario, deck, and pilot inputs
    and by the execution identity (protocol, result schema, bridge artifact bytes).
    Re-running the same batch therefore reuses only byte-compatible completed work.
    Failed records are not silently treated as complete and are retried only when
    explicitly requested.

    ``workers`` > 1 plays that many games at once (#731). Every game still gets
    its own fresh bridge JVM; only the number of JVMs alive at the same time
    changes. The parent is the single writer of records, writes each one as
    soon as its game ends (so an interrupted batch resumes from there) and
    returns the report in case order, whatever order games finish in.
    ``parallelism="thread"`` drives the bridge processes from threads of this
    process: a JVM that dies (for example out of memory) fails only its own
    case. ``"process"`` also moves the Python pilot work into worker
    processes, for hosts where the pilot rather than the JVM is the limit;
    the runner must then be picklable.
    """

    def __init__(self, runner: XmageFullGameRunner, output_directory: str | Path) -> None:
        self.runner = runner
        self.output_directory = Path(output_directory)

    def execution_identity(self) -> ExecutionIdentity:
        return execution_identity_of(self.runner)

    def run(
        self,
        cases: tuple[FullGameBatchCase, ...],
        *,
        resume: bool = True,
        retry_failed: bool = False,
        workers: int = 1,
        parallelism: BatchParallelism = "thread",
    ) -> FullGameBatchReport:
        if workers < 1:
            raise ValueError("workers must be positive")
        if parallelism not in ("thread", "process"):
            raise ValueError("parallelism must be 'thread' or 'process'")
        self.output_directory.mkdir(parents=True, exist_ok=True)
        records: list[FullGameBatchRecord | None] = [None] * len(cases)
        pending: list[tuple[int, FullGameBatchCase, str, ExecutionIdentity, Path]] = []
        for index, case in enumerate(cases):
            execution = self.execution_identity()
            run_key = self._run_key(case, execution)
            path = self.output_directory / f"{run_key}.json"
            reused = self._reusable_record(case, run_key, path, resume, retry_failed)
            if reused is not None:
                records[index] = reused
                continue
            if workers == 1:
                # Sequential path: identical to the historical behaviour,
                # including a later duplicate case reusing an earlier one.
                record = execute_batch_case(self.runner, case, run_key, execution)
                self._write_record(path, record)
                records[index] = record
                continue
            pending.append((index, case, run_key, execution, path))

        if pending:
            keys = [item[2] for item in pending]
            if len(set(keys)) != len(keys):
                raise ValueError("parallel full-game batch cases must have distinct run keys")
            for index, record, path in self._run_parallel(pending, workers, parallelism):
                self._write_record(path, record)
                records[index] = record

        final = tuple(record for record in records if record is not None)
        if len(final) != len(cases):  # pragma: no cover - every branch fills its slot
            raise RuntimeError("full-game batch lost a case record")
        completed = sum(record.status == "completed" for record in final)
        failed = sum(record.status == "failed" for record in final)
        resumed = sum(record.resumed_from_completed_record for record in final)
        return FullGameBatchReport(
            total_cases=len(final),
            completed_cases=completed,
            failed_cases=failed,
            resumed_cases=resumed,
            records=final,
        )

    def _reusable_record(
        self,
        case: FullGameBatchCase,
        run_key: str,
        path: Path,
        resume: bool,
        retry_failed: bool,
    ) -> FullGameBatchRecord | None:
        existing = self._read_record(path) if resume and path.exists() else None
        if existing is None or existing.case_id != case.case_id or existing.run_key != run_key:
            return None
        if existing.status == "completed" and (
            existing.result is not None
            and existing.result.scenario == case.scenario
            and existing.result.terminal is True
            and existing.result.result_payload.get("terminal") is True
            and type(existing.result.result_payload.get("seed")) is int
            and existing.result.result_payload.get("seed") == case.scenario.seed
        ):
            return existing.model_copy(update={"resumed_from_completed_record": True})
        if existing.status == "failed" and not retry_failed:
            return existing
        return None

    def _parallel_runner(self) -> XmageFullGameRunner:
        """A per-game runner copy whose bridge JVM gets its own card repository.

        #739: JVMs that start together in one directory collide on XMage's
        on-disk card repository, so a parallel game copies it into a private
        directory. The flag is not part of the execution identity: it changes
        where the repository file lives, never what the game plays.
        """
        runner = copy.copy(self.runner)
        if hasattr(runner, "private_card_repository"):
            runner.private_card_repository = True
        return runner

    def _run_parallel(
        self,
        pending: list[tuple[int, FullGameBatchCase, str, ExecutionIdentity, Path]],
        workers: int,
        parallelism: BatchParallelism,
    ) -> Iterator[tuple[int, FullGameBatchRecord, Path]]:
        executor: Executor
        if parallelism == "process":
            executor = ProcessPoolExecutor(
                max_workers=min(workers, len(pending)),
                mp_context=multiprocessing.get_context("spawn"),
            )
        else:
            executor = ThreadPoolExecutor(
                max_workers=min(workers, len(pending)),
                thread_name_prefix="full-game-batch",
            )
        with executor:
            futures: dict[Future[FullGameBatchRecord], tuple[int, Path]] = {
                # Each game gets its own shallow runner copy: the runner keeps
                # per-game state (the hidden-information audit) on itself, and
                # threads sharing one runner would mix or drop those audits.
                executor.submit(
                    execute_batch_case, self._parallel_runner(), case, run_key, execution
                ): (
                    index,
                    path,
                )
                for index, case, run_key, execution, path in pending
            }
            try:
                for future in as_completed(futures):
                    index, path = futures[future]
                    yield index, future.result(), path
            except BaseException:
                # Interrupted (Ctrl-C) or failed: drop queued games and stop the
                # bridge JVMs of games in flight, so leaving the executor does
                # not wait for them to finish. Thread workers share this
                # process's clients; process workers' JVMs get the same signal
                # from the terminal. Nothing in flight becomes a record.
                executor.shutdown(wait=False, cancel_futures=True)
                if parallelism == "thread":
                    kill_live_bridge_processes()
                raise

    def run_key(self, case: FullGameBatchCase) -> str:
        return self._run_key(case, self.execution_identity())

    @staticmethod
    def _run_key(case: FullGameBatchCase, execution: ExecutionIdentity) -> str:
        payload = json.dumps(
            {"case": case.model_dump(mode="json"), "execution": execution},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode()
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _failed(
        case: FullGameBatchCase,
        run_key: str,
        started: float,
        failure_class: FullGameFailureClass,
        exc: Exception,
    ) -> FullGameBatchRecord:
        return _failed_record(case, run_key, started, failure_class, exc)

    @staticmethod
    def _read_record(path: Path) -> FullGameBatchRecord | None:
        try:
            return FullGameBatchRecord.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    @staticmethod
    def _write_record(path: Path, record: FullGameBatchRecord) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(record.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)


__all__ = [
    "BatchParallelism",
    "ExecutionIdentity",
    "FullGameBatchCase",
    "FullGameBatchRecord",
    "FullGameBatchReport",
    "FullGameFailureClass",
    "XmageFullGameBatchRunner",
    "execute_batch_case",
    "execution_identity_of",
]
