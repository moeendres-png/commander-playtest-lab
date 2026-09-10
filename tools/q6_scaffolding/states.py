"""Required evidence state model for Q6 scaffolding records.

The states below are machine-readable and mutually exclusive per record.
They describe mechanical/scenario *preparation progress only*.

There is deliberately NO state equivalent to runtime behavior PASS.
``READY_FOR_RUNTIME_QUALIFICATION`` means only that the mechanical and
scenario prerequisites are ready for an authoritative runtime qualifier;
it does NOT mean the card works.
"""

from __future__ import annotations

from enum import StrEnum


class ScaffoldingState(StrEnum):
    """Lifecycle states for a single card/scenario scaffolding record."""

    INTAKE_ONLY = "INTAKE_ONLY"
    PARSED = "PARSED"
    STRUCTURED = "STRUCTURED"
    SKELETON_GENERATED = "SKELETON_GENERATED"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    RULES_ADJUDICATION_REQUIRED = "RULES_ADJUDICATION_REQUIRED"
    UNSUPPORTED = "UNSUPPORTED"
    AMBIGUOUS = "AMBIGUOUS"
    READY_FOR_RUNTIME_QUALIFICATION = "READY_FOR_RUNTIME_QUALIFICATION"


# Ordered pipeline stages: each CLI step advances a record one stage, then
# the routing step resolves SKELETON_GENERATED into a terminal routing state.
STAGE_ORDER = (
    ScaffoldingState.INTAKE_ONLY,
    ScaffoldingState.PARSED,
    ScaffoldingState.STRUCTURED,
    ScaffoldingState.SKELETON_GENERATED,
)

# Terminal routing outcomes (assigned by queue routing, never by parsing).
ROUTING_STATES = frozenset(
    {
        ScaffoldingState.MANUAL_REVIEW_REQUIRED,
        ScaffoldingState.RULES_ADJUDICATION_REQUIRED,
        ScaffoldingState.UNSUPPORTED,
        ScaffoldingState.AMBIGUOUS,
        ScaffoldingState.READY_FOR_RUNTIME_QUALIFICATION,
    }
)

# Queue names served by the review-queue builder.
QUEUES = (
    "MANUAL_SCENARIO_REVIEW",
    "RULES_ADJUDICATION",
    "UNSUPPORTED_CAPABILITY",
    "AMBIGUOUS_PARSE",
    "PROVENANCE_REVIEW",
    "RUNTIME_QUALIFICATION_READY",
)


def is_terminal_routing(state: ScaffoldingState) -> bool:
    """Return True once queue routing has assigned a final preparation state."""
    return state in ROUTING_STATES
