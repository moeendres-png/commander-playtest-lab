"""DR-CLOSURE-01 Phase 5: provider-neutral first-semantic-divergence comparator.

Independent method reimplementation (no donor code): given two normalized
semantic replay tapes recorded under the same semantic input, same Rules seed
and same deterministic decisions, compare step-by-step and report the first
meaningful mismatch. Built on the existing tape schema, source locks and
semantic digests; creates no parallel replay architecture.

A MATCH means trace agreement only — never a Rules PASS (official Rules
remain authority). Process-local UUIDs never enter the compared fields: the
tape schema already stores fingerprints/digests, so the comparator compares
semantic identities, never raw engine IDs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import ValidationError

from .canonicalization import canonical_bytes
from .tape import SemanticReplayTape


class DivergenceKind(StrEnum):
    INITIAL_STATE_MISMATCH = "INITIAL_STATE_MISMATCH"
    LEGAL_ACTION_SET_MISMATCH = "LEGAL_ACTION_SET_MISMATCH"
    DECISION_IDENTITY_MISMATCH = "DECISION_IDENTITY_MISMATCH"
    RULES_RNG_MISMATCH = "RULES_RNG_MISMATCH"
    EVENT_MISMATCH = "EVENT_MISMATCH"
    PUBLIC_STATE_MISMATCH = "PUBLIC_STATE_MISMATCH"
    TERMINAL_OUTCOME_MISMATCH = "TERMINAL_OUTCOME_MISMATCH"
    EARLY_TERMINATION = "EARLY_TERMINATION"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"


@dataclass(frozen=True)
class FirstDivergence:
    kind: DivergenceKind
    record_index: int
    decision_offset: int | None
    actor_principal: int | None
    expected_record: dict[str, Any]
    actual_record: dict[str, Any]
    context_window: list[dict[str, Any]]
    expected_source_lock: dict[str, Any]
    actual_source_lock: dict[str, Any]
    expected_provider: str | None
    actual_provider: str | None


@dataclass(frozen=True)
class ComparisonResult:
    match: bool
    compared_steps: int
    divergence: FirstDivergence | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


def _safe_lock(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("source_lock")
    return dict(value) if isinstance(value, dict) else {}


def _provider_of(lock: dict[str, Any]) -> str | None:
    for key in ("provider_identity", "rules_authority_identity", "adapter_identity"):
        value = lock.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _sequence_or_none(value: Any) -> list[Any] | None:
    if value is None:
        return None
    return list(value)


def _legal_domain(step: dict[str, Any]) -> dict[str, Any]:
    return {
        "legal_set_digest": step.get("legal_set_digest"),
        "legal_set_size": step.get("legal_set_size"),
        "numeric_min": step.get("numeric_min"),
        "numeric_max": step.get("numeric_max"),
        "numeric_legs_min": _sequence_or_none(step.get("numeric_legs_min")),
        "numeric_legs_max": _sequence_or_none(step.get("numeric_legs_max")),
        "numeric_total_min": step.get("numeric_total_min"),
        "numeric_total_max": step.get("numeric_total_max"),
    }


def _selection(step: dict[str, Any]) -> dict[str, Any]:
    return {
        "selected_fingerprints": list(step.get("selected_fingerprints") or ()),
        "numeric_choice": step.get("numeric_choice"),
        "numeric_choices": _sequence_or_none(step.get("numeric_choices")),
    }


def _slim(step: dict[str, Any]) -> dict[str, Any]:
    return {
        "sequence": step.get("sequence"),
        "step_kind": step.get("step_kind"),
        "decision_class": step.get("decision_class"),
        "actor_principal": step.get("actor_principal"),
        "decision_revision": step.get("decision_revision"),
        **_legal_domain(step),
        **_selection(step),
        "rng_calls_before": step.get("rng_calls_before"),
        "rng_calls_after": step.get("rng_calls_after"),
        "event_offset_before": step.get("event_offset_before"),
        "event_offset_after": step.get("event_offset_after"),
        "event_digest": step.get("event_digest"),
        "principal_observation_digest": step.get("principal_observation_digest"),
        "post_checkpoint_digest": step.get("post_checkpoint_digest"),
    }


def _checkpoint_slim(checkpoint: dict[str, Any]) -> dict[str, Any]:
    return {
        "rules_seed": checkpoint.get("rules_seed"),
        "rules_random_calls": checkpoint.get("rules_random_calls"),
        "turn_number": checkpoint.get("turn_number"),
        "phase": checkpoint.get("phase"),
        "step": checkpoint.get("step"),
        "decision_sequence": checkpoint.get("decision_sequence"),
        "event_offset": checkpoint.get("event_offset"),
        "semantic_state_digest": checkpoint.get("semantic_state_digest"),
        "public_state_digest": checkpoint.get("public_state_digest"),
        "principal_digests": dict(checkpoint.get("principal_digests") or {}),
    }


def _terminal_slim(terminal: dict[str, Any]) -> dict[str, Any]:
    outcomes = [dict(row) for row in terminal.get("outcomes") or ()]
    outcomes.sort(key=canonical_bytes)
    return {
        "terminal": terminal.get("terminal"),
        "turn_number": terminal.get("turn_number"),
        "rules_random_calls": terminal.get("rules_random_calls"),
        "outcomes": outcomes,
        "semantic_state_digest": terminal.get("semantic_state_digest"),
        "public_state_digest": terminal.get("public_state_digest"),
    }


def compare_tapes(
    expected: dict[str, Any],
    actual: dict[str, Any],
    context_radius: int = 3,
) -> ComparisonResult:
    """Compare two validated semantic tapes; return MATCH or first divergence."""
    expected_lock = _safe_lock(expected)
    actual_lock = _safe_lock(actual)
    expected_provider = _provider_of(expected_lock)
    actual_provider = _provider_of(actual_lock)

    def diverge(
        kind: DivergenceKind,
        record_index: int,
        decision_offset: int | None,
        actor: int | None,
        expected_record: dict[str, Any],
        actual_record: dict[str, Any],
        window: list[dict[str, Any]],
    ) -> ComparisonResult:
        return ComparisonResult(
            match=False,
            compared_steps=record_index,
            divergence=FirstDivergence(
                kind=kind,
                record_index=record_index,
                decision_offset=decision_offset,
                actor_principal=actor,
                expected_record=expected_record,
                actual_record=actual_record,
                context_window=window,
                expected_source_lock=expected_lock,
                actual_source_lock=actual_lock,
                expected_provider=expected_provider,
                actual_provider=actual_provider,
            ),
        )

    try:
        expected_model = SemanticReplayTape.model_validate(expected)
    except ValidationError:
        return diverge(
            DivergenceKind.PROVIDER_FAILURE,
            -1,
            None,
            None,
            {"schema": "invalid", "side": "expected"},
            {},
            [],
        )
    try:
        actual_model = SemanticReplayTape.model_validate(actual)
    except ValidationError:
        return diverge(
            DivergenceKind.PROVIDER_FAILURE,
            -1,
            None,
            None,
            {},
            {"schema": "invalid", "side": "actual"},
            [],
        )

    expected = expected_model.model_dump(mode="json")
    actual = actual_model.model_dump(mode="json")
    expected_lock = dict(expected["source_lock"])
    actual_lock = dict(actual["source_lock"])
    expected_provider = _provider_of(expected_lock)
    actual_provider = _provider_of(actual_lock)

    expected_manifest = dict(expected["game_manifest"])
    actual_manifest = dict(actual["game_manifest"])
    if expected_manifest != actual_manifest:
        return diverge(
            DivergenceKind.INITIAL_STATE_MISMATCH,
            -1,
            None,
            None,
            {"game_manifest": expected_manifest},
            {"game_manifest": actual_manifest},
            [],
        )

    expected_rng = dict(expected["rng_contract"])
    actual_rng = dict(actual["rng_contract"])
    if expected_rng != actual_rng:
        return diverge(
            DivergenceKind.RULES_RNG_MISMATCH,
            -1,
            None,
            None,
            {"rng_contract": expected_rng},
            {"rng_contract": actual_rng},
            [],
        )

    expected_initial = _checkpoint_slim(dict(expected["initial_checkpoint"]))
    actual_initial = _checkpoint_slim(dict(actual["initial_checkpoint"]))
    if expected_initial != actual_initial:
        return diverge(
            DivergenceKind.INITIAL_STATE_MISMATCH,
            -1,
            None,
            None,
            {"initial_checkpoint": expected_initial},
            {"initial_checkpoint": actual_initial},
            [],
        )

    expected_steps = list(expected["steps"])
    actual_steps = list(actual["steps"])

    def window(steps: list[dict[str, Any]], index: int) -> list[dict[str, Any]]:
        start = max(0, index - context_radius)
        return [_slim(step) for step in steps[start:index]]

    common = min(len(expected_steps), len(actual_steps))
    for index in range(common):
        exp = expected_steps[index]
        act = actual_steps[index]
        actor = exp.get("actor_principal")
        offset = exp.get("decision_revision")
        if (
            exp.get("step_kind") != act.get("step_kind")
            or exp.get("decision_class") != act.get("decision_class")
            or exp.get("actor_principal") != act.get("actor_principal")
            or exp.get("decision_revision") != act.get("decision_revision")
        ):
            return diverge(
                DivergenceKind.DECISION_IDENTITY_MISMATCH,
                index,
                offset,
                actor,
                _slim(exp),
                _slim(act),
                window(expected_steps, index),
            )

        if _legal_domain(exp) != _legal_domain(act):
            return diverge(
                DivergenceKind.LEGAL_ACTION_SET_MISMATCH,
                index,
                offset,
                actor,
                _slim(exp),
                _slim(act),
                window(expected_steps, index),
            )

        if _selection(exp) != _selection(act):
            return diverge(
                DivergenceKind.DECISION_IDENTITY_MISMATCH,
                index,
                offset,
                actor,
                _slim(exp),
                _slim(act),
                window(expected_steps, index),
            )

        if exp.get("rng_calls_before") != act.get("rng_calls_before") or exp.get(
            "rng_calls_after"
        ) != act.get("rng_calls_after"):
            return diverge(
                DivergenceKind.RULES_RNG_MISMATCH,
                index,
                offset,
                actor,
                _slim(exp),
                _slim(act),
                window(expected_steps, index),
            )

        if (
            exp.get("event_offset_before") != act.get("event_offset_before")
            or exp.get("event_offset_after") != act.get("event_offset_after")
            or exp.get("event_digest") != act.get("event_digest")
        ):
            return diverge(
                DivergenceKind.EVENT_MISMATCH,
                index,
                offset,
                actor,
                _slim(exp),
                _slim(act),
                window(expected_steps, index),
            )

        if exp.get("principal_observation_digest") != act.get(
            "principal_observation_digest"
        ) or exp.get("post_checkpoint_digest") != act.get("post_checkpoint_digest"):
            return diverge(
                DivergenceKind.PUBLIC_STATE_MISMATCH,
                index,
                offset,
                actor,
                _slim(exp),
                _slim(act),
                window(expected_steps, index),
            )

    if len(expected_steps) != len(actual_steps):
        longer = expected_steps if len(expected_steps) > len(actual_steps) else actual_steps
        return diverge(
            DivergenceKind.EARLY_TERMINATION,
            common,
            None,
            None,
            {"step_count": len(expected_steps)},
            {"step_count": len(actual_steps)},
            window(longer, common),
        )

    expected_terminal = _terminal_slim(dict(expected["terminal_checkpoint"]))
    actual_terminal = _terminal_slim(dict(actual["terminal_checkpoint"]))
    if expected_terminal != actual_terminal:
        return diverge(
            DivergenceKind.TERMINAL_OUTCOME_MISMATCH,
            len(expected_steps),
            None,
            None,
            {"terminal_checkpoint": expected_terminal},
            {"terminal_checkpoint": actual_terminal},
            window(expected_steps, len(expected_steps)),
        )

    return ComparisonResult(match=True, compared_steps=len(expected_steps))


__all__ = [
    "ComparisonResult",
    "DivergenceKind",
    "FirstDivergence",
    "compare_tapes",
]
