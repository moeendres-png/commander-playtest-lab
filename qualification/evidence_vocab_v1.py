#!/usr/bin/env python3
"""WS221 controlled evidence vocabulary (v1).

Single controlled vocabulary/mapping architecture for qualification evidence
classes. Four semantic axes stay distinct — they are NEVER collapsed into one
enum:

  Axis 1  EVIDENCE_CLASS          how a claim was established (11 terms)
  Axis 2  VERDICT                 qualification outcome of a fixture/gate (7 terms)
  Axis 3  FAILURE_CLASSIFICATION  machine failure bucket (9 terms)
  Axis 4  OMISSION_REASON         why runtime did not run (5 terms)

Hard doctrine (project-wide, non-negotiable):

  UNKNOWN != PASS.
  CODE_DERIVED != RUNTIME_VERIFIED.
  Construction / import / readback is not behavior (at most CODE_DERIVED or
  SOURCE_DERIVED, never RUNTIME_VERIFIED).

Machine joins (notably ``qualification/harness.py``) must fail closed: a
missing, malformed, or unmapped evidence class is rejected — never defaulted,
never upgraded. See :func:`require_evidence_class`.
"""

from __future__ import annotations

import json
from pathlib import Path

VOCAB_VERSION = "evidence-vocab-v1"

# Axis 1 — controlled evidence classes (union of the WS17 machine enum and the
# doctrine policy enum; CODE_DERIVED is shared, NOT_RUN and UNKNOWN are
# deliberately distinct: NOT_RUN = required runtime not executed;
# UNKNOWN = classification not established; both fail closed).
EVIDENCE_CLASSES = (
    "RUNTIME_VERIFIED",
    "DIRECT_CODE_FAIL",
    "CODE_DERIVED",
    "SOURCE_DERIVED",
    "NOT_RUN",
    "DIRECTLY_VERIFIED",
    "TECHNICALLY_CONFORMANT",
    "EXTERNALLY_RULE_VALIDATED",
    "MODELED",
    "SYNTHETIC",
    "UNKNOWN",
)

EVIDENCE_CLASS_NOTES = {
    "RUNTIME_VERIFIED": "observed by executed runtime against authoritative Rules/pinned engine.",
    "DIRECT_CODE_FAIL": "machine-observed direct failure of code/contract; grants no behavior credit.",
    "CODE_DERIVED": "derived from static code/diff/config inspection; never runtime verification.",
    "SOURCE_DERIVED": "derived from source/provenance records (pins, locks, manifests).",
    "NOT_RUN": "required runtime not executed; fail closed.",
    "DIRECTLY_VERIFIED": "directly verified by probe/read/test execution outside the runtime engine.",
    "TECHNICALLY_CONFORMANT": "technical conformance on a bounded lane/fixture; not decision evidence.",
    "EXTERNALLY_RULE_VALIDATED": "validated against external Rules authority (CR/Oracle/ruling).",
    "MODELED": "model estimate; never empirical.",
    "SYNTHETIC": "synthetic fixture/assumption; never empirical.",
    "UNKNOWN": "classification not established; fail closed, never PASS.",
}

# Axis 2 — qualification verdicts (unchanged WS17 vocabulary).
VERDICTS = (
    "PASS",
    "FAIL",
    "UNKNOWN",
    "NOT_RUN",
    "PARTIAL",
    "UNSUPPORTED",
    "NOT_APPLICABLE",
)

# Axis 3 — machine failure classifications (unchanged WS17 vocabulary).
FAILURE_CLASSIFICATIONS = (
    "DIRECT_RULES_FAIL",
    "DIRECT_PILOT_BOUNDARY_FAIL",
    "DIRECT_CARD_COVERAGE_FAIL",
    "PROTOCOL_ADAPTER_MISSING",
    "QUALIFICATION_INFRASTRUCTURE_MISSING",
    "AUTHORITY_BLOCKED",
    "RUNTIME_NOT_RUN",
    "RUNTIME_PASS",
    "REMEDIATION_REQUIRED",
)

# Axis 4 — omission reason codes (unchanged WS17 vocabulary).
OMISSION_REASONS = (
    "PROTOCOL_ADAPTER_MISSING",
    "REMEDIATION_REQUIRED",
    "AUTHORITY_BLOCKED",
    "PROVIDER_ABSENT",
    "RUNTIME_UNAVAILABLE",
)

# Explicitly NOT evidence classes: separate disposition/inventory axes that
# must never be flattened into Axis 1 (documented to prevent future misjoins).
NON_EVIDENCE_AXES = (
    "pin_consumer_disposition",
    "risk_matrix_class",
    "ws79_impact_disposition",
    "retention_anchor_type",
    "decision_bundle_evidence_tag",
    "full_game_conformance_tag",
)


class UnmappedEvidenceTerm(ValueError):
    """Raised when an evidence-class term is missing or outside the controlled enum."""


def require_evidence_class(term: object) -> str:
    """Validate a provider/seal evidence-class term; fail closed on anything else.

    Returns the term unchanged when it is a member of :data:`EVIDENCE_CLASSES`.
    Raises :class:`UnmappedEvidenceTerm` for missing, non-string, or unmapped
    terms — including free prose. Callers at machine joins must catch this and
    demote the row to ``verdict=UNKNOWN`` / ``evidence_class=UNKNOWN``; they
    must never substitute ``RUNTIME_VERIFIED`` or any other stronger class.
    """
    if not isinstance(term, str) or term not in EVIDENCE_CLASSES:
        raise UnmappedEvidenceTerm(f"unmapped evidence class: {term!r}")
    return term


def is_satisfying_evidence(verdict: str, evidence_class: str) -> bool:
    """True only for an explicit runtime PASS — the single credit-granting pair."""
    return verdict == "PASS" and evidence_class == "RUNTIME_VERIFIED"


def _legacy_map_path() -> Path:
    return Path(__file__).resolve().parent / "evidence" / "evidence_legacy_map_v1.json"


def load_legacy_map() -> dict:
    return json.loads(_legacy_map_path().read_text(encoding="utf-8"))


def map_legacy_evidence_class(term: object) -> dict:
    """Adapt a known legacy free-prose evidence term at read time.

    Returns ``{"evidence_class": ..., "legacy": True, "note": ...}`` for terms
    present in ``evidence_legacy_map_v1.json`` (ws90's per-aspect term returns
    ``{"aspects": {...}}`` instead of a single class). Raises
    :class:`UnmappedEvidenceTerm` for anything else. Sealed artifacts are never
    rewritten; the mapping travels with the consumer.
    """
    if not isinstance(term, str):
        raise UnmappedEvidenceTerm(f"unmapped evidence class: {term!r}")
    if term in EVIDENCE_CLASSES:
        return {"evidence_class": term, "legacy": False, "note": "native controlled term"}
    for entry in load_legacy_map().get("mappings", []):
        if entry.get("legacy_term") == term:
            if entry.get("mapped_aspects"):
                return {
                    "aspects": dict(entry["mapped_aspects"]),
                    "legacy": True,
                    "note": entry.get("note", ""),
                }
            return {
                "evidence_class": entry["mapped_evidence_class"],
                "legacy": True,
                "legacy_qualified": entry.get("legacy_qualified", True),
                "note": entry.get("note", ""),
            }
    raise UnmappedEvidenceTerm(f"unmapped evidence class: {term!r}")
