from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, model_validator

from .common import FrozenModel, MutableModel

PROVENANCE_SCHEMA_VERSION = "1.0.0"

class SourceType(StrEnum):
    DIRECT_USER_STATEMENT = "direct_user_statement"
    CHAT_CONVERSATION = "chat_conversation"
    GOOGLE_DRIVE_FILE = "google_drive_file"
    REPOSITORY = "repository"
    OFFICIAL_DECKLIST = "official_decklist"
    TOURNAMENT_RESULT = "tournament_result"
    PRIMER = "primer"
    GUIDE = "guide"
    REAL_GAME = "real_game"
    SYNTHETIC_ASSUMPTION = "synthetic_assumption"
    MODEL_INFERENCE = "model_inference"
    WEB_RESEARCH = "web_research"

class VerificationStatus(StrEnum):
    VERIFIED = "verified"
    HASH_VERIFIED = "hash_verified"
    PARTIALLY_VERIFIED = "partially_verified"
    UNVERIFIED = "unverified"
    SUPERSEDED = "superseded"
    MISSING = "missing"

class ClaimKind(StrEnum):
    SOURCE_FACT = "source_fact"
    MODEL_OUTPUT = "model_output"
    INFERENCE = "inference"

class LicenseRecord(FrozenModel):
    license_id: str
    license_name: str
    usage_rights: tuple[str, ...] = ()
    restrictions: tuple[str, ...] = ()
    full_text_storage_allowed: bool = False
    notes: str | None = None

class SourceRecord(FrozenModel):
    source_id: str
    source_type: SourceType
    title: str
    author: str | None = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    published_at: datetime | None = None
    url_or_drive_id: str | None = None
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    license: str = "unknown"
    usage_rights: tuple[str, ...] = ()
    git_commit: str | None = None
    package_version: str | None = None
    derived_from: tuple[str, ...] = ()
    transformation: str | None = None
    supersedes: tuple[str, ...] = ()
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    observed: bool = False
    notes: str | None = None

    @model_validator(mode="after")
    def synthetic_not_observed(self) -> "SourceRecord":
        if self.source_type in {SourceType.SYNTHETIC_ASSUMPTION, SourceType.MODEL_INFERENCE} and self.observed:
            raise ValueError("synthetic assumptions and model inferences cannot be marked observed")
        return self

class ArtifactRecord(FrozenModel):
    artifact_id: str
    artifact_type: str
    title: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    path_or_drive_id: str | None = None
    git_commit: str | None = None
    package_version: str | None = None
    derived_from: tuple[str, ...] = ()
    transformation_ids: tuple[str, ...] = ()
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

class DerivedDataRecord(FrozenModel):
    derived_id: str
    data_type: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    derived_from: tuple[str, ...]
    transformation_id: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    model_label: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

class TransformationRecord(FrozenModel):
    transformation_id: str
    name: str
    description: str
    input_ids: tuple[str, ...]
    output_ids: tuple[str, ...]
    code_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    git_commit: str | None = None
    package_version: str | None = None
    deterministic: bool = True
    parameters_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    executed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

class CitationRecord(FrozenModel):
    citation_id: str
    claim_id: str
    claim_text: str
    claim_kind: ClaimKind
    source_ids: tuple[str, ...] = ()
    derived_ids: tuple[str, ...] = ()
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    location: str | None = None

    @model_validator(mode="after")
    def evidence_required(self) -> "CitationRecord":
        if not self.source_ids and not self.derived_ids:
            raise ValueError("citation requires a source or derived record")
        return self

class SupersessionRecord(FrozenModel):
    supersession_id: str
    old_id: str
    new_id: str
    reason: str
    authority_rank_old: int = Field(ge=0)
    authority_rank_new: int = Field(ge=0)
    effective_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    historical_record_retained: bool = True

    @model_validator(mode="after")
    def newer_authority_required(self) -> "SupersessionRecord":
        if self.old_id == self.new_id:
            raise ValueError("a record cannot supersede itself")
        if self.authority_rank_new < self.authority_rank_old:
            raise ValueError("superseding record cannot have lower authority")
        return self

class ProvenanceGraph(MutableModel):
    schema_version: str = PROVENANCE_SCHEMA_VERSION
    graph_id: str
    sources: list[SourceRecord] = Field(default_factory=list)
    artifacts: list[ArtifactRecord] = Field(default_factory=list)
    derived_data: list[DerivedDataRecord] = Field(default_factory=list)
    transformations: list[TransformationRecord] = Field(default_factory=list)
    citations: list[CitationRecord] = Field(default_factory=list)
    supersessions: list[SupersessionRecord] = Field(default_factory=list)
    licenses: list[LicenseRecord] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    git_commit: str | None = None
    package_version: str | None = None
