from __future__ import annotations

import hashlib
import json
import time
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.models import RulesDeckInput

from .full_game import (
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
    decks: tuple[RulesDeckInput, RulesDeckInput, RulesDeckInput, RulesDeckInput]
    pilots: tuple[
        FullGamePilotBinding,
        FullGamePilotBinding,
        FullGamePilotBinding,
        FullGamePilotBinding,
    ]

    @model_validator(mode="after")
    def case_matches_operational_scope(self) -> FullGameBatchCase:
        if self.scenario.player_count != 4:
            raise ValueError("full-game batch cases require exactly four players")
        if {pilot.seat for pilot in self.pilots} != {1, 2, 3, 4}:
            raise ValueError("full-game batch cases require pilot seats 1..4 exactly")
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

    A completed record is content-addressed by all scenario, deck, and pilot inputs.
    Re-running the same batch therefore reuses only byte-compatible completed work.
    Failed records are not silently treated as complete and are retried only when
    explicitly requested.
    """

    def __init__(self, runner: XmageFullGameRunner, output_directory: str | Path) -> None:
        self.runner = runner
        self.output_directory = Path(output_directory)

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
            run_key = self.run_key(case)
            path = self.output_directory / f"{run_key}.json"
            existing = self._read_record(path) if resume and path.exists() else None
            if existing is not None and existing.case_id == case.case_id:
                if existing.status == "completed":
                    records.append(
                        existing.model_copy(update={"resumed_from_completed_record": True})
                    )
                    continue
                if not retry_failed:
                    records.append(existing)
                    continue

            started = time.monotonic()
            try:
                result = self.runner.run(
                    scenario=case.scenario,
                    decks=case.decks,
                    pilots=case.pilots,
                )
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

    @staticmethod
    def run_key(case: FullGameBatchCase) -> str:
        payload = json.dumps(
            case.model_dump(mode="json"),
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
            failure_message=str(exc),
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
