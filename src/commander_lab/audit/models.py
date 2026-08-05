from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from commander_lab.models.common import FrozenModel, utc_now


class AuditStatus(StrEnum):
    NOT_RUN = "not_run"
    BLOCKED = "blocked"
    FAILED = "failed"
    PASSED = "passed"
    PASSED_WITH_LIMITATIONS = "passed_with_limitations"


class FeatureDecision(StrEnum):
    IMPLEMENT_NOW = "implement_now"
    IMPLEMENT_LATER = "implement_later"
    EXPERIMENTAL = "experimental"
    REJECT = "reject"
    ALREADY_PRESENT = "already_present"


class AuditCheck(FrozenModel):
    check_id: str
    component: str
    status: AuditStatus
    summary: str
    evidence: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


class BugRecord(FrozenModel):
    bug_id: str
    severity: str
    component: str
    discovered_by: str
    reproduction: str
    root_cause: str
    fix: str
    regression_test: str
    affected_versions: tuple[str, ...]
    validation_status: AuditStatus


class FeatureCandidate(FrozenModel):
    feature: str
    source: str
    benefit: str
    effort: str
    risk: str
    project_fit: str
    decision: FeatureDecision
    rationale: str


class Phase86Result(FrozenModel):
    schema_version: int = 1
    phase: str = "8.6"
    generated_at: datetime = Field(default_factory=utc_now)
    baseline_commit: str
    audit_commit: str | None = None
    status: str
    external_engine_validation_pending: bool
    checks: tuple[AuditCheck, ...]
    bugs: tuple[BugRecord, ...]
    artifacts: tuple[str, ...]
    remaining_risks: tuple[str, ...]
    phase9_allowed: bool
