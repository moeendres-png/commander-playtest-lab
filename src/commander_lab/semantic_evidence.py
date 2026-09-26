from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from commander_lab.models import CandidateProfile, DataQuality
from commander_lab.storage.run_identity import sha256_run_value


class SemanticEvidenceType(StrEnum):
    CANONICAL_PROJECT = "CANONICAL_PROJECT"
    PROJECT_DERIVED = "PROJECT_DERIVED"
    DETERMINISTIC_ORACLE = "DETERMINISTIC_ORACLE"
    EXTERNAL_STRUCTURED = "EXTERNAL_STRUCTURED"
    PROJECT_HEURISTIC = "PROJECT_HEURISTIC"
    LLM_INFERRED = "LLM_INFERRED"
    HUMAN_REVIEWED = "HUMAN_REVIEWED"
    UNKNOWN = "UNKNOWN"


class SemanticConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class DecisionMateriality(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class SemanticEvidenceRecord:
    card_id: str | None
    oracle_name: str
    feature: str
    value: Any
    confidence: SemanticConfidence
    evidence_type: SemanticEvidenceType
    source_id: str | None
    source_version: str | None
    extraction_method: str
    review_status: str
    decision_materiality: DecisionMateriality

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def evidence_hash(self) -> str:
        return sha256_run_value(self)


_DECISION_ROLES = frozenset(
    {
        "counter",
        "draw",
        "engine",
        "finisher",
        "land",
        "mana_source",
        "protection",
        "ramp",
        "rebuild",
        "removal",
        "selection",
        "wipe",
    }
)


def summarize_semantic_records(records: Iterable[SemanticEvidenceRecord]) -> dict[str, Any]:
    materialized = tuple(records)
    by_feature: dict[str, list[SemanticEvidenceRecord]] = {}
    for record in materialized:
        by_feature.setdefault(record.feature, []).append(record)
    conflicts: list[dict[str, Any]] = []
    for feature, rows in sorted(by_feature.items()):
        values = {sha256_run_value(row.value) for row in rows}
        material = any(row.decision_materiality == DecisionMateriality.HIGH for row in rows)
        if material and len(values) > 1:
            conflicts.append(
                {
                    "feature": feature,
                    "record_hashes": [row.evidence_hash for row in rows],
                    "source_ids": [row.source_id for row in rows],
                }
            )
    payload = {
        "records": [
            {"evidence_hash": record.evidence_hash, **record.as_dict()} for record in materialized
        ],
        "material_conflicts": conflicts,
        "material_conflict": bool(conflicts),
        "requires_semantic_adjudication": bool(conflicts),
        "automatic_promotion": False,
        "automatic_rejection": False,
        "llm_inferred_is_canonical": False,
        "truth_boundary": "semantic conflict routing, not empirical card power",
    }
    payload["semantic_record_set_hash"] = sha256_run_value(payload)
    return payload


def semantic_evidence_summary(
    *,
    oracle_name: str,
    profile: CandidateProfile | None,
    annotation_roles: tuple[str, ...] = (),
    annotation_packages: tuple[str, ...] = (),
    additional_records: tuple[SemanticEvidenceRecord, ...] = (),
) -> dict[str, Any]:
    roles = set(annotation_roles)
    packages = set(annotation_packages)
    source_types: set[str] = set()
    source_ids: set[str] = set()
    provenance_records: list[dict[str, Any]] = []

    if profile is not None:
        profile_roles = tuple(sorted(role.value for role in profile.card.roles))
        profile_packages = tuple(sorted(profile.card.package_ids))
        roles.update(profile_roles)
        packages.update(profile_packages)
        source_types.update(source.source_type for source in profile.card.sources)
        source_ids.update(
            source.source_path for source in profile.card.sources if source.source_path
        )
        provenance_records.append(
            {
                "layer": "structural_profile",
                "roles": profile_roles,
                "package_ids": profile_packages,
                "source_types": tuple(sorted(source_types)),
                "source_ids": tuple(sorted(source_ids)),
            }
        )
    if annotation_roles or annotation_packages:
        provenance_records.append(
            {
                "layer": "canonical_feature_annotation",
                "roles": tuple(sorted(annotation_roles)),
                "package_ids": tuple(sorted(annotation_packages)),
            }
        )

    if profile is None and not annotation_roles and not annotation_packages:
        evidence_type = SemanticEvidenceType.UNKNOWN
        confidence = SemanticConfidence.UNKNOWN
    elif profile is not None and profile.card.source_quality in {
        DataQuality.AUTHORITATIVE,
        DataQuality.PROJECT_VERIFIED,
    }:
        evidence_type = SemanticEvidenceType.CANONICAL_PROJECT
        confidence = SemanticConfidence.HIGH
    elif annotation_roles or annotation_packages:
        evidence_type = SemanticEvidenceType.PROJECT_DERIVED
        confidence = SemanticConfidence.MEDIUM
    elif profile is not None and profile.card.source_quality == DataQuality.PROJECT_INFERRED:
        evidence_type = SemanticEvidenceType.PROJECT_HEURISTIC
        confidence = SemanticConfidence.LOW
    else:
        evidence_type = SemanticEvidenceType.UNKNOWN
        confidence = SemanticConfidence.UNKNOWN

    if (roles & _DECISION_ROLES) or packages:
        materiality = DecisionMateriality.HIGH
    elif roles:
        materiality = DecisionMateriality.MEDIUM
    else:
        materiality = DecisionMateriality.LOW
    canonical_ready = evidence_type in {
        SemanticEvidenceType.CANONICAL_PROJECT,
        SemanticEvidenceType.PROJECT_DERIVED,
        SemanticEvidenceType.DETERMINISTIC_ORACLE,
        SemanticEvidenceType.EXTERNAL_STRUCTURED,
        SemanticEvidenceType.HUMAN_REVIEWED,
    }
    conflict_summary = summarize_semantic_records(additional_records)
    needs_targeted_adjudication = (
        materiality == DecisionMateriality.HIGH and not canonical_ready
    ) or conflict_summary["material_conflict"] is True
    payload = {
        "oracle_name": oracle_name,
        "evidence_type": evidence_type.value,
        "confidence": confidence.value,
        "decision_materiality": materiality.value,
        "roles": tuple(sorted(roles)),
        "package_ids": tuple(sorted(packages)),
        "source_types": tuple(sorted(source_types)),
        "source_ids": tuple(sorted(source_ids)),
        "provenance_records": provenance_records,
        "canonical_project_fact": evidence_type == SemanticEvidenceType.CANONICAL_PROJECT,
        "llm_inferred": evidence_type == SemanticEvidenceType.LLM_INFERRED,
        "needs_targeted_adjudication": needs_targeted_adjudication,
        "semantic_conflict": conflict_summary,
        "truth_boundary": "semantic evidence and confidence, not empirical card power",
    }
    payload["semantic_evidence_hash"] = sha256_run_value(payload)
    return payload


__all__ = [
    "DecisionMateriality",
    "SemanticConfidence",
    "SemanticEvidenceRecord",
    "SemanticEvidenceType",
    "semantic_evidence_summary",
    "summarize_semantic_records",
]
