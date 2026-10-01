"""Explicit typed refusal of an unsupported discretionary decision class.

#255 (2026-10-01) ruled that ``DECISION_TIMEOUT`` does not satisfy an obligation
requiring ``UNSUPPORTED_DISCRETIONARY_DECISION``: a timeout proves bounded
non-response, not the explicit classification of an unsupported decision class.
It also required the smallest fail-closed protocol/control-plane mechanism by
which an external decision handler can explicitly refuse a decision it does not
support, with no fabricated action, no default, no silent skip, no internal AI,
no arbitrary timeout relabelling, an auditable typed result, and no mutation of
the current game state.

This module is that control-plane mechanism. It is deliberately *not* an engine
message: Protocol 2.0.0 has no refusal message, adding one would change the
shared transport schema for both candidates, and the obligation is about the
handler's behaviour, which the Lab owns. A refusal:

* requires a real engine-authored pending frame (decision id, actor, class and a
  non-empty engine-offered option set) — it cannot be manufactured locally;
* sends NO state-mutating request of any kind, so the game state cannot change;
* re-reads the engine through the read-only decision and event channels and
  records that the same frame is still pending and the public event offset is
  unchanged;
* records the exact transport tape window, so an auditor can see that no
  submission occurred for the refused frame; and
* reports a typed kind, distinct from ``DECISION_TIMEOUT``, that the row
  verifier and the receipt consume.

A refusal is never a substitute for answering a decision the handler *can*
answer, and it never fabricates legality: it selects nothing.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

TYPED_UNSUPPORTED_DISCRETIONARY_DECISION = "UNSUPPORTED_DISCRETIONARY_DECISION"

# Message types that can mutate engine or game state. A refusal window may
# contain read-only requests; none of these may appear, or the refusal is not
# no-mutation and cannot satisfy the obligation.
SUBMITTING_MESSAGE_TYPES: frozenset[str] = frozenset(
    {
        "submit_midgame_decision",
        "submit_action",
        "submit_concede",
        "pass_priority",
        "resolve_mulligan",
        "choose_modes",
        "order_triggers",
        "select_targets",
        "advance_priority",
        "advance_phase",
    }
)


class RefusalError(RuntimeError):
    """The typed refusal could not be established and must not be claimed."""


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class TypedDecisionRefusal:
    """One explicit, auditable refusal of an unsupported decision class."""

    kind: str
    decision_class: str
    actor_id: str | None
    decision_id: str | None
    offered_option_ids: tuple[str, ...]
    frame_digest: str
    transport_window: tuple[str, ...]
    event_offset_before: Any
    event_offset_after: Any
    decision_id_after: str | None
    detail: str

    @property
    def submissions_in_window(self) -> tuple[str, ...]:
        return tuple(name for name in self.transport_window if name in SUBMITTING_MESSAGE_TYPES)

    @property
    def well_formed(self) -> bool:
        """Every condition the ruling requires, checked on the recorded facts."""
        return bool(
            self.kind == TYPED_UNSUPPORTED_DISCRETIONARY_DECISION
            and self.decision_class
            and self.decision_id
            and self.actor_id
            and self.offered_option_ids
            and not self.submissions_in_window
            and self.event_offset_before == self.event_offset_after
            and self.decision_id_after == self.decision_id
        )

    def document(self) -> dict[str, Any]:
        return {
            "schema_version": "commander-lab.typed-decision-refusal/1.0.0",
            "kind": self.kind,
            "decision_class": self.decision_class,
            "actor_id": self.actor_id,
            "decision_id": self.decision_id,
            "offered_option_ids": list(self.offered_option_ids),
            "frame_digest": self.frame_digest,
            "transport_window": list(self.transport_window),
            "submissions_in_window": list(self.submissions_in_window),
            "event_offset_before": self.event_offset_before,
            "event_offset_after": self.event_offset_after,
            "decision_id_after": self.decision_id_after,
            "state_mutated": self.event_offset_before != self.event_offset_after
            or self.decision_id_after != self.decision_id,
            "well_formed": self.well_formed,
            "detail": self.detail,
        }


def _frame_offer_ids(legal: dict[str, Any]) -> tuple[str, ...]:
    ids: list[str] = []
    for action in legal.get("actions") or ():
        if not isinstance(action, dict):
            continue
        value = action.get("action_id")
        if isinstance(value, str) and value:
            ids.append(value)
    return tuple(ids)


def refuse_pending_decision(
    client: Any,
    decision: dict[str, Any],
    *,
    legal: dict[str, Any] | None = None,
) -> TypedDecisionRefusal:
    """Refuse one pending engine decision without touching game state.

    ``client`` is the mid-game lane client: this helper uses only its read-only
    channels (``pending_decision``, ``events``) plus its transport tape. It sends
    no submission, so the engine never receives a fabricated action.
    """
    if not isinstance(decision, dict) or not decision:
        raise RefusalError("no pending engine decision exists to refuse")
    decision_class = str(decision.get("decision_class") or "")
    decision_id = decision.get("decision_id")
    actor_id = decision.get("actor_id")
    if not decision_class or not isinstance(decision_id, str) or not decision_id:
        raise RefusalError(
            "the pending decision does not carry a decision_class and decision_id; a refusal "
            "must be bound to the engine-authored frame it refuses"
        )
    if not isinstance(actor_id, str) or not actor_id:
        raise RefusalError("the pending decision does not carry an actor_id")
    if legal is None:
        legal = {}
    offered = _frame_offer_ids(legal)
    if not offered:
        raise RefusalError(
            "the pending decision carries no engine-offered option ids; the frame is not an "
            "engine-authored legal-action domain and a refusal of it would prove nothing"
        )
    frame_digest = _digest({"decision": decision, "offered_option_ids": list(offered)})

    # Read-only window: the refusal itself transmits nothing. The two reads below
    # are the audit of that claim, not a substitute for it.
    before = client.events(0)
    tape_start = len(client.tape)
    again = client.pending_decision(attempts=1, interval_s=0.0)
    after = client.events(0)
    window = tuple(
        str(entry.get("message_type"))
        for entry in client.tape[tape_start:]
        if isinstance(entry, dict)
    )
    decision_id_after = again.get("decision_id") if isinstance(again, dict) and again else None
    detail = (
        f"typed refusal {TYPED_UNSUPPORTED_DISCRETIONARY_DECISION} of {decision_class} "
        f"(actor {actor_id}, revision/decision {decision_id}): no action submitted; the same "
        "frame is still pending and the public event offset is unchanged"
    )
    refusal = TypedDecisionRefusal(
        kind=TYPED_UNSUPPORTED_DISCRETIONARY_DECISION,
        decision_class=decision_class,
        actor_id=actor_id,
        decision_id=decision_id,
        offered_option_ids=offered,
        frame_digest=frame_digest,
        transport_window=window,
        event_offset_before=before.get("latest_offset"),
        event_offset_after=after.get("latest_offset"),
        decision_id_after=decision_id_after if isinstance(decision_id_after, str) else None,
        detail=detail,
    )
    if not refusal.well_formed:
        raise RefusalError(
            "the refusal did not satisfy the no-mutation/typed conditions: "
            f"submissions={refusal.submissions_in_window}, "
            f"offset {refusal.event_offset_before}->{refusal.event_offset_after}, "
            f"decision {refusal.decision_id}->{refusal.decision_id_after}"
        )
    return refusal
