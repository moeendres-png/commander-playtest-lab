"""Structural PASS-impossibility gate.

This module is the hard enforcement point for the rule that Q6 scaffolding
can never award behavior PASS, qualification credit, or coverage promotion.

Two mechanisms combine:

1. EXCLUSION BY CONSTRUCTION: no scaffolding schema defined in this package
   contains a behavior-credit field. There is nowhere to store a PASS.
2. FAIL-CLOSED VALIDATION: :func:`reject_promotion_fields` scans any
   external input (imported fixtures, corpus rows, operator-supplied JSON)
   and :func:`validate_output` scans every artifact this pipeline emits.
   Any behavior-credit, expected-outcome, or coverage field present raises
   :class:`PromotionRejected` instead of flowing through.

Both entry points raise; they never coerce, strip-and-continue, or warn.
Stripping would hide contamination, so rejection is the only disposition.
"""

from __future__ import annotations

from typing import Any


class PromotionRejected(ValueError):
    """Raised when input/output carries behavior-credit or coverage fields."""


# Exact forbidden output keys (case-insensitive). Scaffolding artifacts must
# never contain these: there is no legitimate scaffolding use for them.
FORBIDDEN_OUTPUT_KEYS = frozenset(
    {
        "behavior_pass",
        "behavior_result",
        "coverage_increment",
        "coverage_delta",
        "coverage_promotion",
        "qualified",
        "qualification_credit",
        "externally_rule_validated",
        "pass_verdict",
        "expected_outcome",
        "expected_life_total",
        "expected_life",
        "expected_permanents",
        "expected_permanent_state",
        "legal_options",
        "exact_legal_option_list",
        "pass_criteria",
    }
)

# Key prefixes rejected on *input* (external fixtures/corpus rows/operator
# JSON). Covers D2's expected/assert/outcome rule plus AI-driver and
# harness-hook markers that must never become scaffolding truth.
FORBIDDEN_INPUT_PREFIXES = (
    "expected",
    "assert",
    "outcome",
    "behavior_",
    "coverage_",
    "qualif",
)

# Exact input keys rejected in addition to the prefix rule.
FORBIDDEN_INPUT_KEYS = frozenset(
    {
        "pass",
        "passed",
        "result",
        "verdict",
        "engine_ai",
        "aiplaypriority",
        "strictchoosemode",
    }
)

# Exact input keys that are legitimate despite matching a forbidden prefix.
# ``expected_hash`` is a content-integrity field (sha256 of ingested bytes),
# not an expected behavioral outcome; it is how intake verifies inputs.
ALLOWED_INPUT_KEYS = frozenset({"expected_hash"})

# Substring markers (case-insensitive) rejected inside free-text input fields:
# engine AI drivers and harness hooks per D2 BOUNDED_REUSE Phase C, plus
# snake_case promotion markers. The snake_case form never occurs in natural
# card text (cf. bare words like "verdict", which Supreme Verdict proves
# must NOT be matched), so these catch smuggled promotion fields hiding as
# opaque param names or raw values (e.g. ``behavior_pass$ True`` in a
# script) without false-positiving on Oracle wording.
FORBIDDEN_TEXT_MARKERS = (
    "aiplaypriority",
    "cardtestcommander4playerswithaihelps",
    "runCode",
    "rollbackTurns",
    "setStrictChooseMode",
    "behavior_pass",
    "behavior_result",
    "coverage_increment",
    "coverage_delta",
    "coverage_promotion",
    "qualification_credit",
    "externally_rule_validated",
    "pass_verdict",
    "expected_outcome",
    "expected_life_total",
    "expected_life",
    "expected_permanents",
    "expected_permanent_state",
    "legal_options",
    "exact_legal_option_list",
    "pass_criteria",
)


def _normalize_key(key: str) -> str:
    return key.strip().lower().replace("-", "_").replace(" ", "_")


def _iter_mapping_keys(obj: Any) -> Any:
    """Yield every mapping key in a nested structure (dicts in lists too)."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield key
            yield from _iter_mapping_keys(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iter_mapping_keys(item)


def _iter_text_values(obj: Any) -> Any:
    """Yield every string value in a nested structure."""
    if isinstance(obj, dict):
        for value in obj.values():
            yield from _iter_text_values(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iter_text_values(item)
    elif isinstance(obj, str):
        yield obj


def reject_promotion_fields(obj: Any, *, source: str = "<input>") -> None:
    """Reject external input carrying behavior-credit or expected-outcome data.

    Raises :class:`PromotionRejected` on the first violation found. Clean
    input returns None.
    """
    for key in _iter_mapping_keys(obj):
        norm = _normalize_key(str(key))
        if norm in ALLOWED_INPUT_KEYS:
            continue
        if norm in FORBIDDEN_OUTPUT_KEYS or norm in FORBIDDEN_INPUT_KEYS:
            raise PromotionRejected(
                f"promotion field rejected from {source}: key {key!r} "
                "must never enter scaffolding intake"
            )
        if norm.startswith(FORBIDDEN_INPUT_PREFIXES):
            raise PromotionRejected(
                f"expected-outcome contamination rejected from {source}: "
                f"key {key!r} (expected/assert/outcome data is not Rules truth)"
            )
    for text in _iter_text_values(obj):
        lowered = text.lower()
        for marker in FORBIDDEN_TEXT_MARKERS:
            if marker.lower() in lowered:
                raise PromotionRejected(
                    f"engine/harness marker rejected from {source}: "
                    f"{marker!r} (engine AI and harness hooks are not importable)"
                )


def validate_output(obj: Any, *, artifact: str = "<artifact>") -> None:
    """Prove a pipeline-emitted artifact carries no behavior-credit fields.

    Called by every builder in this package before an artifact is returned
    or persisted. Raises :class:`PromotionRejected` on violation.
    """
    for key in _iter_mapping_keys(obj):
        if _normalize_key(str(key)) in FORBIDDEN_OUTPUT_KEYS:
            raise PromotionRejected(
                f"structural gate violation in {artifact}: output key {key!r} "
                "is incapable of existing in scaffolding output"
            )
    # Promotion markers smuggled as opaque values (param names, raw corpus
    # text) fail closed here exactly as on the input side: snake_case
    # markers never occur in natural card text.
    for text in _iter_text_values(obj):
        lowered = text.lower()
        for marker in FORBIDDEN_TEXT_MARKERS:
            if marker.lower() in lowered:
                raise PromotionRejected(
                    f"structural gate violation in {artifact}: promotion marker "
                    f"{marker!r} must never appear in scaffolding output"
                )
