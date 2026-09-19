"""Per-card source/rule-path coverage over a verified physical-pool snapshot.

Two coverage kinds are kept strictly separate:

- source coverage: does the card have imported Oracle text, faces, structural
  roles/semantics, and a source-verified oracle identity? (import-level facts)
- rule-path coverage: which explicitly tested behavior paths exist, on which
  engine+pin, with which verdict? Unexecuted paths are UNKNOWN, never PASS.

Parsing or import never counts as behavior coverage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

SourceVerdict = Literal["PRESENT", "ABSENT", "UNKNOWN"]
RuleVerdict = Literal["FULL", "CONDITIONAL_FULL", "PARTIAL", "UNSUPPORTED", "UNKNOWN"]


@dataclass(frozen=True)
class CardSourceCoverage:
    card_id: str
    oracle_name: str
    has_oracle_text: SourceVerdict = "UNKNOWN"
    has_faces: SourceVerdict = "UNKNOWN"
    has_structural_roles: SourceVerdict = "UNKNOWN"
    has_structural_semantics: SourceVerdict = "UNKNOWN"
    oracle_identity: SourceVerdict = "UNKNOWN"
    engine_behavior: RuleVerdict = "UNKNOWN"
    engine_pin: str = "NOT_RUN"


@dataclass
class CoverageMatrix:
    """Explicitly bounded coverage result for one card population."""

    population: str
    population_size: int
    rows: list[CardSourceCoverage] = field(default_factory=list)
    engine_pin: str = "NOT_RUN"

    def source_summary(self) -> dict[str, dict[str, int]]:
        summary: dict[str, dict[str, int]] = {}
        for dimension in (
            "has_oracle_text",
            "has_faces",
            "has_structural_roles",
            "has_structural_semantics",
            "oracle_identity",
        ):
            counts: dict[str, int] = {"PRESENT": 0, "ABSENT": 0, "UNKNOWN": 0}
            for row in self.rows:
                counts[getattr(row, dimension)] += 1
            summary[dimension] = counts
        return summary

    def behavior_summary(self) -> dict[str, int]:
        counts: dict[str, int] = {
            "FULL": 0,
            "CONDITIONAL_FULL": 0,
            "PARTIAL": 0,
            "UNSUPPORTED": 0,
            "UNKNOWN": 0,
        }
        for row in self.rows:
            counts[row.engine_behavior] += 1
        return counts


def build_source_matrix(
    identities: list[dict[str, Any]],
    knowledge_by_id: dict[str, dict[str, Any]],
    semantics_by_id: dict[str, dict[str, Any]],
    verified_oracle_ids: dict[str, str],
    *,
    population: str,
    engine_pin: str = "NOT_RUN",
) -> CoverageMatrix:
    """Build import-level coverage; engine behavior stays UNKNOWN unless tested."""
    matrix = CoverageMatrix(
        population=population, population_size=len(identities), engine_pin=engine_pin
    )
    for record in identities:
        card_id = record.get("card_id")
        knowledge = knowledge_by_id.get(card_id, {})
        semantics = semantics_by_id.get(card_id, {})
        oracle_text = record.get("oracle_text")
        faces = record.get("card_faces_if_relevant")
        roles = (semantics.get("roles") or []) or (
            knowledge.get("functional_semantics") or {}
        ).get("roles", [])
        matrix.rows.append(
            CardSourceCoverage(
                card_id=card_id,
                oracle_name=record.get("oracle_name") or "",
                has_oracle_text="PRESENT" if oracle_text else "ABSENT",
                has_faces="PRESENT" if faces else "ABSENT",
                has_structural_roles="PRESENT" if roles else "ABSENT",
                has_structural_semantics="PRESENT" if semantics else "ABSENT",
                oracle_identity="PRESENT"
                if card_id in verified_oracle_ids
                else "UNKNOWN",
                engine_behavior="UNKNOWN",
                engine_pin=engine_pin,
            )
        )
    return matrix
