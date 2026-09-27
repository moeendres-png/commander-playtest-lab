from __future__ import annotations

from pathlib import Path

from commander_lab.candidate_screening import RogShaiCandidateScreener
from commander_lab.semantic_evidence import SemanticEvidenceType
from commander_lab.tools.service import CommanderToolService

ROOT = Path(__file__).resolve().parents[2]


def test_candidate_screen_exposes_provenance_preserving_semantic_evidence() -> None:
    service = CommanderToolService(ROOT)
    result = RogShaiCandidateScreener(ROOT, service=service).screen_pool()
    summary = result["semantic_evidence"]

    assert summary["coverage_policy"] == "decision_weighted_not_full_pool_annotation"
    assert summary["llm_inferred_is_canonical"] is False
    assert sum(summary["evidence_type_counts"].values()) == result["physical_legal_candidate_count"]
    assert SemanticEvidenceType.LLM_INFERRED.value not in summary["evidence_type_counts"]
    assert all("semantic_evidence" in row for row in result["rows"])
    assert all(
        row["semantic_evidence"]["canonical_project_fact"] is False
        for row in result["rows"]
        if row["semantic_evidence"]["llm_inferred"] is True
    )


def test_decision_weighted_unknowns_are_explicit_not_negative_power_assumptions() -> None:
    service = CommanderToolService(ROOT)
    result = RogShaiCandidateScreener(ROOT, service=service).screen_pool()
    unknowns = [
        row
        for row in result["rows"]
        if row["semantic_evidence"]["evidence_type"] == SemanticEvidenceType.UNKNOWN.value
    ]

    assert unknowns
    assert all(row["explorable"] is True for row in unknowns)
    assert all("power" not in row["semantic_evidence"] for row in unknowns)
