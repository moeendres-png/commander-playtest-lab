from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FrozenModel(BaseModel):
    """Immutable value object used for deterministic state and provenance records."""

    model_config = ConfigDict(frozen=True, extra="forbid", validate_assignment=True)


class MutableModel(BaseModel):
    """Validated mutable aggregate used at import and orchestration boundaries."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Color(StrEnum):
    WHITE = "W"
    BLUE = "U"
    BLACK = "B"
    RED = "R"
    GREEN = "G"


class DataQuality(StrEnum):
    AUTHORITATIVE = "authoritative"
    PROJECT_VERIFIED = "project_verified"
    PROJECT_INFERRED = "project_inferred"
    SYNTHETIC_ASSUMPTION = "synthetic_assumption"
    UNKNOWN = "unknown"


class SourceRef(FrozenModel):
    source_type: str
    source_name: str
    source_path: str | None = None
    retrieved_at: datetime | None = None
    data_as_of: datetime | None = None
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    quality: DataQuality = DataQuality.UNKNOWN
    notes: str | None = None


class NumericRange(FrozenModel):
    minimum: float
    maximum: float

    def contains(self, value: float) -> bool:
        return self.minimum <= value <= self.maximum


class ErrorDetail(FrozenModel):
    code: str
    message: str
    path: tuple[str | int, ...] = ()
    context: dict[str, Any] = Field(default_factory=dict)


def utc_now() -> datetime:
    return datetime.now(UTC)
