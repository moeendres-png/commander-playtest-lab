from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from commander_lab.storage.run_identity import sha256_run_value


class TacticalEvidenceExecutionStatus(StrEnum):
    NOT_RUN = "NOT_RUN"
    PARTIAL = "PARTIAL"
    PASS = "PASS"
    FAIL = "FAIL"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class TacticalEvidenceRequest:
    question_id: str
    initial_state_hash: str
    relevant_cards: tuple[str, ...]
    rules_question: str
    permitted_action_scope: tuple[str, ...]

    @property
    def fixture_hash(self) -> str:
        return sha256_run_value(asdict(self))

    def as_dict(self) -> dict[str, Any]:
        return {"fixture_hash": self.fixture_hash, **asdict(self)}


@dataclass(frozen=True)
class TacticalEvidenceResult:
    question_id: str
    execution_status: TacticalEvidenceExecutionStatus
    provider: str | None = None
    provider_version: str | None = None
    provider_commit: str | None = None
    fixture_hash: str | None = None
    legal_actions: tuple[str, ...] = ()
    observed_transition: dict[str, Any] | None = None
    replay_or_log: str | None = None
    confidence_scope: str = "bounded_fixture_only"
    evidence_class: str = "targeted_tactical_evidence"
    truth_boundary: str = (
        "bounded tactical evidence; never structural or empirical winrate evidence"
    )

    def __post_init__(self) -> None:
        if self.execution_status == TacticalEvidenceExecutionStatus.PASS:
            required = (
                self.provider,
                self.provider_version,
                self.provider_commit,
                self.fixture_hash,
            )
            if not all(required):
                raise ValueError("PASS tactical evidence requires provider/version/commit/fixture")
        if self.provider is None and self.execution_status not in {
            TacticalEvidenceExecutionStatus.NOT_RUN,
            TacticalEvidenceExecutionStatus.UNAVAILABLE,
        }:
            raise ValueError("executed tactical evidence requires a provider identity")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


__all__ = [
    "TacticalEvidenceExecutionStatus",
    "TacticalEvidenceRequest",
    "TacticalEvidenceResult",
]
