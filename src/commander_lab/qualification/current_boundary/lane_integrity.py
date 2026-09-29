"""Lane-integrity check: a real Commander game must have shuffled.

CR 103.3 requires each player to shuffle their library as part of starting a
game. A lane that reports it never reached a shuffle has therefore not executed
a legal game start, whatever else it did. That is a Rules-correctness statement
about the game, not a coverage note about the harness, and conflating the two is
how the XMage shuffle defect survived observation:

* ``XmageBridgePlayer.shuffleLibrary`` was a no-op, so no shuffle ever ran;
* the committed evidence faithfully recorded the consequence as
  ``HIDDEN_11 = "no shuffle/order-knowledge invalidation scenario reachable"``;
* that line was read as an ordinary gap in scenario coverage, because nothing
  connected it to the rule that makes a missing shuffle *impossible* in a legal
  game.

This module makes that connection explicit. It reads the recorded lane signals
and refuses to let an order-knowledge obligation be credited on a lane that
demonstrates no shuffling, so the same defect cannot reappear as a quiet
coverage limitation.

It is deliberately conservative about what it claims:

* It does not diagnose the engine. "No shuffle was observed" is a fact about the
  run; whether the cause is a harness seam or an engine defect is for the owner
  of that lane.
* It does not fabricate a version of CR 103.3. It cites the requirement and
  reports the inconsistency.
* It never moves a gate verdict. It produces a blocking reason for specific
  obligations.
"""

from __future__ import annotations

import json
from typing import Any

LANE_INTEGRITY_OK = "LANE_SHUFFLE_DEMONSTRATED"
LANE_INTEGRITY_UNPROVEN = "LANE_SHUFFLE_NOT_DEMONSTRATED"

# The rule that makes a missing shuffle decisive rather than incidental.
_SHUFFLE_REQUIREMENT = "CR 103.3 requires each player to shuffle their library when starting a game"

# Obligations that cannot be credited on a lane which demonstrates no shuffling,
# because the obligation is about order knowledge that shuffling is what
# invalidates.
_ORDER_KNOWLEDGE_OBLIGATIONS: frozenset[str] = frozenset(
    {
        "HIDDEN_11",  # shuffle invalidates order knowledge
        "HIDDEN_02",  # library identities/order absent while count remains visible
        "HIDDEN_09",  # hidden-zone search inspection does not leak
        "HIDDEN_10",  # scry/surveil top-N actor knowledge
    }
)

_NO_SHUFFLE_MARKERS: tuple[str, ...] = (
    "no shuffle",
    "no_shuffle",
    "shuffle not reachable",
    "not reachable",
    "unreached",
)


def _mentions_no_shuffle(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    lowered = value.lower()
    return any(marker in lowered for marker in _NO_SHUFFLE_MARKERS)


def _lane_signals(
    document: dict[str, Any], seed_binding: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Extract the recorded lane capability signals, without inventing any.

    ``seed_binding`` lets a caller supply the Rules-seed binding recorded in the
    artifact that actually establishes it. Reading seed control only from the
    hidden-information document would under-report a candidate whose binding is
    recorded elsewhere, which would be its own inaccuracy.
    """
    identity = document.get("runtime_identity") or {}
    observations = document.get("principal_observations") or {}

    seed_controlled = None
    if isinstance(seed_binding, dict) and seed_binding:
        seed_controlled = seed_binding.get("controlled")
        if seed_controlled is None:
            seed_controlled = seed_binding.get("seed_controlled")
    if seed_controlled is None:
        seed_controlled = identity.get("seed_controlled")
    seed_value = None
    rng_counter = None
    if isinstance(observations, dict) and observations:
        first = next(iter(observations.values()))
        first = first if isinstance(first, dict) else {}
        state = first.get("state") or {}
        seed_value = state.get("seed")
        rng_counter = state.get("rng_counter")
        if seed_controlled is None:
            seed_controlled = first.get("seed_controlled")

    seams = document.get("historical_forge_seams_classified_freshly") or {}
    no_shuffle_obligations = sorted(str(k) for k, v in seams.items() if _mentions_no_shuffle(v))

    return {
        "seed_controlled": seed_controlled,
        "seed_value_present": seed_value is not None,
        "rng_counter": rng_counter,
        "unreached_shuffle_obligations": no_shuffle_obligations,
    }


def assess_lane_integrity(
    document: dict[str, Any], *, seed_binding: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Whether the lane demonstrates the shuffling a legal game start requires."""
    signals = _lane_signals(document, seed_binding)

    # A lane demonstrates shuffling when it binds a Rules seed or reports Rules
    # randomness activity, AND records no order-knowledge obligation as
    # unreachable for shuffling.
    #
    # Only POSITIVE signals count. The absence of a complaint is not evidence
    # that a shuffle happened, so a run that says nothing at all must never be
    # read as a demonstrated one -- that inversion is what let the XMage defect
    # pass as a coverage gap.
    shuffle_evidence: list[str] = []
    if signals["seed_controlled"] is True and signals["seed_value_present"]:
        shuffle_evidence.append("the lane bound a Rules seed and reports seed control")
    if signals["rng_counter"] is not None:
        shuffle_evidence.append(
            f"the lane reports Rules randomness activity ({signals['rng_counter']})"
        )

    not_demonstrated: list[str] = []
    if signals["unreached_shuffle_obligations"]:
        not_demonstrated.append(
            "the run records order-knowledge obligations as unreachable for shuffling: "
            + ", ".join(signals["unreached_shuffle_obligations"])
        )
    if not shuffle_evidence:
        not_demonstrated.append(
            "the lane reports neither an acknowledged Rules seed nor any Rules randomness activity"
        )
    if not shuffle_evidence and not signals["unreached_shuffle_obligations"]:
        not_demonstrated.append(
            "the run records nothing about shuffling at all, which is not the same as shuffling"
        )

    demonstrated = bool(shuffle_evidence) and not signals["unreached_shuffle_obligations"]
    return {
        "disposition": LANE_INTEGRITY_OK if demonstrated else LANE_INTEGRITY_UNPROVEN,
        "signals": signals,
        "evidence": shuffle_evidence,
        "blocking_reasons": not_demonstrated,
        "rule_basis": _SHUFFLE_REQUIREMENT,
        "consequence": (
            "obligations about order knowledge cannot be credited on this lane and stay UNKNOWN; "
            "the missing shuffle is recorded as an inconsistency with a legal game start rather "
            "than as an ordinary coverage gap"
            if not demonstrated
            else "the lane demonstrates shuffling, so order-knowledge obligations may be assessed "
            "on their own evidence"
        ),
        "does_not_claim": (
            "that the engine is defective, or that a repaired lane satisfies any obligation: a "
            "fresh run at the repaired revision is what establishes that"
        ),
    }


def blocking_obligations(assessment: dict[str, Any]) -> list[str]:
    """The order-knowledge obligations this lane cannot credit.

    Empty when the lane demonstrates shuffling. Derived from the catalog of
    order-knowledge obligations rather than from whatever the run happened to
    mention, so an obligation is blocked by its own nature and not by whether the
    harness noticed it.
    """
    if assessment["disposition"] == LANE_INTEGRITY_OK:
        return []
    return sorted(_ORDER_KNOWLEDGE_OBLIGATIONS)


def load_json(path: Any) -> Any:
    import pathlib

    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
