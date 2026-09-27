"""WS218 divergence taxonomy (fail-closed, machine-readable)."""

from __future__ import annotations

from enum import StrEnum


class DivergenceClass(StrEnum):
    SOURCE_LOCK_MISMATCH = "SOURCE_LOCK_MISMATCH"
    DOMAIN_LOCK_MISMATCH = "DOMAIN_LOCK_MISMATCH"
    INITIAL_STATE_MISMATCH = "INITIAL_STATE_MISMATCH"
    ACTOR_MISMATCH = "ACTOR_MISMATCH"
    DECISION_CLASS_MISMATCH = "DECISION_CLASS_MISMATCH"
    DECISION_REVISION_MISMATCH = "DECISION_REVISION_MISMATCH"
    OBSERVATION_MISMATCH = "OBSERVATION_MISMATCH"
    LEGAL_SET_MISMATCH = "LEGAL_SET_MISMATCH"
    CHOSEN_OPTION_MISSING = "CHOSEN_OPTION_MISSING"
    CHOSEN_OPTION_AMBIGUOUS = "CHOSEN_OPTION_AMBIGUOUS"
    RULES_RNG_CALL_DRIFT = "RULES_RNG_CALL_DRIFT"
    RULES_RNG_RESULT_DRIFT = "RULES_RNG_RESULT_DRIFT"
    EVENT_DIGEST_MISMATCH = "EVENT_DIGEST_MISMATCH"
    STATE_DIGEST_MISMATCH = "STATE_DIGEST_MISMATCH"
    EARLY_TERMINATION = "EARLY_TERMINATION"
    EXTRA_DECISION = "EXTRA_DECISION"
    TERMINAL_OUTCOME_MISMATCH = "TERMINAL_OUTCOME_MISMATCH"
    MALFORMED_TAPE = "MALFORMED_TAPE"


class ReplayDivergence(RuntimeError):
    """Fail-closed replay divergence (no WARN_AND_CONTINUE)."""

    def __init__(self, divergence: DivergenceClass, detail: str) -> None:
        super().__init__(f"{divergence.value}: {detail}")
        self.divergence = divergence
        self.detail = detail


__all__ = ["DivergenceClass", "ReplayDivergence"]
