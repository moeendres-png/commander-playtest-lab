from __future__ import annotations

import hashlib
import json
import time
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

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


class XmageFullGameBatchRunner:
    """Correctness-first batch layer around the one-process/one-game runner.

    A completed record is content-addressed by all scenario, deck, and pilot inputs
    and by the execution identity (protocol, result schema, bridge artifact bytes).
    Re-running the same batch therefore reuses only byte-compatible completed work.
    Failed records are not silently treated as complete and are retried only when
    explicitly requested.
    """

    def __init__(self, runner: XmageFullGameRunner, output_directory: str | Path) -> None:
        self.runner = runner
        self.output_directory = Path(output_directory)

    def execution_identity(self) -> dict[str, Any]:
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
            cwd = Path(
                resolve_engine_working_directory(getattr(self.runner, "cwd", None)) or "."
            ).resolve()
            command = tuple(getattr(self.runner, "command", None) or ())
            for position, token in enumerate(command):
                path = Path(token)
                if path.suffix in {".jar", ".py"}:
                    if not path.is_absolute():
                        path = cwd / path
                    digest = hashlib.sha256()
                    with path.open("rb") as handle:
                        for chunk in iter(lambda: handle.read(1 << 20), b""):
                            digest.update(chunk)
                    artifacts[str(position)] = digest.hexdigest()
            configuration = json.dumps(
                {
                    "command": command,
                    "cwd": str(cwd),
                    "max_decisions": getattr(self.runner, "max_decisions", None),
                    "request_timeout_seconds": getattr(
                        self.runner, "request_timeout_seconds", None
                    ),
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
            "result_schema_version": FullGameConformanceResult.model_fields[
                "schema_version"
            ].default,
            "runner_configuration_sha256": hashlib.sha256(configuration).hexdigest(),
            "bridge_artifacts": artifacts,
        }

    def run(
        self,
        cases: tuple[FullGameBatchCase, ...],
        *,
        resume: bool = True,
        retry_failed: bool = False,
    ) -> FullGameBatchReport:
        self.output_directory.mkdir(parents=True, exist_ok=True)
        records: list[FullGameBatchRecord] = []
        for case in cases:
            execution = self.execution_identity()
            run_key = self._run_key(case, execution)
            path = self.output_directory / f"{run_key}.json"
            existing = self._read_record(path) if resume and path.exists() else None
            if (
                existing is not None
                and existing.case_id == case.case_id
                and existing.run_key == run_key
            ):
                if existing.status == "completed" and (
                    existing.result is not None
                    and existing.result.scenario == case.scenario
                    and existing.result.terminal is True
                    and existing.result.result_payload.get("terminal") is True
                    and type(existing.result.result_payload.get("seed")) is int
                    and existing.result.result_payload.get("seed") == case.scenario.seed
                ):
                    records.append(
                        existing.model_copy(update={"resumed_from_completed_record": True})
                    )
                    continue
                if existing.status == "failed" and not retry_failed:
                    records.append(existing)
                    continue

            started = time.monotonic()
            try:
                result = self.runner.run(
                    scenario=case.scenario,
                    decks=case.decks,
                    pilots=case.pilots,
                )
                if self.execution_identity() != execution:
                    raise ValueError("full-game batch execution identity changed during game")
                record = FullGameBatchRecord(
                    case_id=case.case_id,
                    run_key=run_key,
                    status="completed",
                    elapsed_seconds=time.monotonic() - started,
                    result=result,
                )
            except FullGameProtocolError as exc:
                record = self._failed(case, run_key, started, FullGameFailureClass.PROTOCOL, exc)
            except FullGameConformanceError as exc:
                record = self._failed(
                    case,
                    run_key,
                    started,
                    FullGameFailureClass.CONFORMANCE,
                    exc,
                )
            except (OSError, ValueError) as exc:
                record = self._failed(
                    case,
                    run_key,
                    started,
                    FullGameFailureClass.CONFIGURATION,
                    exc,
                )
            except RuntimeError as exc:
                record = self._failed(case, run_key, started, FullGameFailureClass.ENGINE, exc)
            self._write_record(path, record)
            records.append(record)

        completed = sum(record.status == "completed" for record in records)
        failed = sum(record.status == "failed" for record in records)
        resumed = sum(record.resumed_from_completed_record for record in records)
        return FullGameBatchReport(
            total_cases=len(records),
            completed_cases=completed,
            failed_cases=failed,
            resumed_cases=resumed,
            records=tuple(records),
        )

    def run_key(self, case: FullGameBatchCase) -> str:
        return self._run_key(case, self.execution_identity())

    @staticmethod
    def _run_key(case: FullGameBatchCase, execution: dict[str, Any]) -> str:
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
        return FullGameBatchRecord(
            case_id=case.case_id,
            run_key=run_key,
            status="failed",
            elapsed_seconds=time.monotonic() - started,
            failure_class=failure_class,
            failure_message=redacted_exception_message(exc),
        )

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
    "FullGameBatchCase",
    "FullGameBatchRecord",
    "FullGameBatchReport",
    "FullGameFailureClass",
    "XmageFullGameBatchRunner",
]
