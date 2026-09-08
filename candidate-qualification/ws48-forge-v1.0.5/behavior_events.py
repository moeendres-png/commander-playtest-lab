#!/usr/bin/env python3
"""WS-48 behavior event-feed verifier (provider-neutral, harness-side).

Verifies a record's ``expected_events`` contract against an ordered native event
feed plus the terminal native snapshot text:

- every ``required_events`` entry must occur at least once (exact string match);
- no ``forbidden_events`` entry may occur in the feed or in any snapshot text
  (honey-sentinel leakage scans the snapshots too);
- every ``ordering_constraints`` pair ``[a, b]`` requires all occurrences of
  ``a`` before all occurrences of ``b``;
- ``partial_order_constraints`` supports the WS-47 APNAP trigger-placement rule.

This module performs no Magic legality reasoning. It only compares strings the
provider natively emitted.
"""

from __future__ import annotations

from typing import Any


def _indices(feed: list[str], event: str) -> list[int]:
    return [i for i, e in enumerate(feed) if e == event]


def verify_required(feed: list[str], required: list[str]) -> list[str]:
    """Return the subset of required events missing from the feed."""
    return [e for e in required if not _indices(feed, e)]


def verify_forbidden(
    feed: list[str], forbidden: list[str], snapshot_texts: list[str] | None = None
) -> list[str]:
    """Return forbidden entries observed in the feed or snapshot texts."""
    haystacks = list(feed) + list(snapshot_texts or [])
    return [e for e in forbidden if any(e in h for h in haystacks)]


def verify_ordering(feed: list[str], pairs: list[list[str]]) -> list[str]:
    """Return human-readable violations; empty means all pairs ordered.

    Pair ``[a, b]`` holds iff both occur and every ``a`` precedes every ``b``.
    """
    violations = []
    for pair in pairs:
        if len(pair) != 2:
            violations.append(f"MALFORMED_ORDER_PAIR:{pair!r}")
            continue
        a, b = pair
        ia, ib = _indices(feed, a), _indices(feed, b)
        if not ia or not ib:
            violations.append(f"ORDER_MISSING:{a!r}:{b!r}")
        elif max(ia) >= min(ib):
            violations.append(f"ORDER_VIOLATED:{a!r}:{b!r}")
    return violations


def verify_apnap(
    feed: list[str], constraint: dict[str, Any], stack_order_events: list[str] | None = None
) -> list[str]:
    """Verify the WS-47 APNAP trigger-placement partial-order constraint.

    ``constraint`` carries ``before_player_groups`` (active player first, then
    nonactive players in turn order). ``stack_order_events`` lists trigger-stack
    placement events in bottom-to-top order using ``trigger:<name>:<Pid>``
    naming; when absent, the check falls back to ``APNAP_stack_order``-prefixed
    feed events.
    """
    groups = constraint.get("before_player_groups") or []
    if not groups:
        return ["APNAP_MALFORMED:missing before_player_groups"]
    ordered = list(stack_order_events or [e for e in feed if e.startswith("APNAP_stack_order")])
    if not ordered:
        return ["APNAP_MISSING:stack_order evidence absent"]
    rank = {pid: i for i, pid in enumerate(groups)}
    last = -1
    for event in ordered:
        pid = event.rsplit(":", 1)[-1] if ":" in event else ""
        if pid not in rank:
            return [f"APNAP_UNKNOWN_PLAYER:{event!r}"]
        if rank[pid] < last:
            return [f"APNAP_ORDER_VIOLATED:{event!r}"]
        last = rank[pid]
    return []


def verify(
    expected_events: dict[str, Any],
    feed: list[str],
    snapshot_texts: list[str] | None = None,
    stack_order_events: list[str] | None = None,
) -> dict[str, Any]:
    """Verify a full ``expected_events`` contract. PASS iff no violations."""
    required = list((expected_events or {}).get("required_events") or [])
    forbidden = list((expected_events or {}).get("forbidden_events") or [])
    ordering = list((expected_events or {}).get("ordering_constraints") or [])
    partial = list((expected_events or {}).get("partial_order_constraints") or [])
    missing = verify_required(feed, required)
    leaked = verify_forbidden(feed, forbidden, snapshot_texts)
    order_bad = verify_ordering(feed, ordering)
    partial_bad = []
    for constraint in partial:
        if isinstance(constraint, dict) and "before_player_groups" in constraint:
            partial_bad.extend(verify_apnap(feed, constraint, stack_order_events))
        else:
            partial_bad.append(f"PARTIAL_ORDER_UNSUPPORTED:{constraint!r}")
    violations = (
        [f"MISSING:{e}" for e in missing]
        + [f"FORBIDDEN_OBSERVED:{e}" for e in leaked]
        + order_bad
        + partial_bad
    )
    return {
        "status": "PASS" if not violations else "FAIL",
        "missing_required": missing,
        "forbidden_observed": leaked,
        "ordering_violations": order_bad,
        "partial_order_violations": partial_bad,
        "violations": violations,
    }
