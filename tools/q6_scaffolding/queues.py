"""Deterministic review queues and failure-clustering integration.

Queues route scaffolding records to human/Coordinator action. Queue
membership is a deterministic function of record state plus reasons: same
inputs always produce the same queue assignment in the same order.

No queue completion awards behavior credit: queue items carry required
next actions and blockers, never verdicts.

Failure-clustering integration wraps (imports, never modifies)
``tools/foundry/cluster_failures.py`` to group scaffolding-side failures
(parser failures, unsupported tags, scenario-generation gaps,
runtime-preparation gaps). Scaffolding failures carry ``kind`` markers that
keep them separate from engine/runtime behavior failures; this module never
touches runtime failure truth.
"""

from __future__ import annotations

import hashlib
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from foundry import cluster_failures  # read-only reuse; tools/foundry is not edited

from . import SCHEMA_QUEUE_ITEM_V1
from .gate import validate_output
from .states import QUEUES, ScaffoldingState

# State -> queues mapping (deterministic; a record may join several queues).
_STATE_QUEUES: dict[str, tuple[str, ...]] = {
    ScaffoldingState.MANUAL_REVIEW_REQUIRED.value: ("MANUAL_SCENARIO_REVIEW",),
    ScaffoldingState.RULES_ADJUDICATION_REQUIRED.value: (
        "MANUAL_SCENARIO_REVIEW",
        "RULES_ADJUDICATION",
    ),
    ScaffoldingState.UNSUPPORTED.value: (
        "MANUAL_SCENARIO_REVIEW",
        "UNSUPPORTED_CAPABILITY",
    ),
    ScaffoldingState.AMBIGUOUS.value: ("MANUAL_SCENARIO_REVIEW", "AMBIGUOUS_PARSE"),
    ScaffoldingState.READY_FOR_RUNTIME_QUALIFICATION.value: ("RUNTIME_QUALIFICATION_READY",),
}

# Required next action per queue (actionable, never a verdict).
_QUEUE_ACTIONS: dict[str, str] = {
    "MANUAL_SCENARIO_REVIEW": (
        "human reviewer inspects skeleton prerequisites and pre-tags for "
        "mechanical soundness (no behavior judgment)"
    ),
    "RULES_ADJUDICATION": (
        "Coordinator/human Rules authority resolves the open rules questions "
        "against Oracle/Comprehensive Rules/rulings"
    ),
    "UNSUPPORTED_CAPABILITY": (
        "curator extends parser tables or taxonomy from public documentation, "
        "or records the family as out of scope with rationale"
    ),
    "AMBIGUOUS_PARSE": (
        "curator inspects the ambiguous diagnostics against the pinned source "
        "and clarifies or escalates the input"
    ),
    "PROVENANCE_REVIEW": (
        "operator repairs source-lock/provenance metadata; record is blocked "
        "until provenance is complete"
    ),
    "RUNTIME_QUALIFICATION_READY": (
        "authoritative runtime qualifier consumes the skeleton via the WS50 "
        "integration boundary (runtime observations are authoritative)"
    ),
}


@dataclass
class QueueItem:
    """One actionable queue entry. Carries work, never credit."""

    queue: str
    item_id: str
    reason: str
    source: str
    intake_id: str
    card_name_hint: str
    related_capability: str
    required_next_action: str
    blockers: list = field(default_factory=list)
    dependencies: list = field(default_factory=list)
    schema: str = SCHEMA_QUEUE_ITEM_V1

    def as_dict(self) -> dict:
        return asdict(self)


def queue_item_id(queue: str, intake_id: str, reason: str) -> str:
    """Stable queue-item identity (no timestamps, no randomness)."""
    canonical = "|".join(["q6-queue-v1", queue, intake_id, reason])
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def build_queues(routed: list[dict]) -> dict[str, list[dict]]:
    """Build all six queues deterministically from routed record dicts.

    Each routed dict needs: intake_id, card_name_hint, state, reasons
    (list), capability (str), provenance_complete (bool). Output maps queue
    name -> sorted item list. Queue order and item order are stable.
    """
    queues: dict[str, list[dict]] = {name: [] for name in QUEUES}
    for record in sorted(routed, key=lambda r: r["intake_id"]):
        state = record["state"]
        reasons = list(record.get("reasons", [])) or ["state:" + state]
        capability = record.get("capability", "UNCLUSTERED")
        for reason in sorted(set(reasons)):
            for queue in _STATE_QUEUES.get(state, ()):
                item = QueueItem(
                    queue=queue,
                    item_id=queue_item_id(queue, record["intake_id"], reason),
                    reason=reason,
                    source="q6_scaffolding.queue_router",
                    intake_id=record["intake_id"],
                    card_name_hint=record.get("card_name_hint", ""),
                    related_capability=capability,
                    required_next_action=_QUEUE_ACTIONS[queue],
                    blockers=list(record.get("blockers", [])),
                    dependencies=list(record.get("dependencies", [])),
                )
                queues[queue].append(item.as_dict())
        if not record.get("provenance_complete", True):
            item = QueueItem(
                queue="PROVENANCE_REVIEW",
                item_id=queue_item_id(
                    "PROVENANCE_REVIEW", record["intake_id"], "provenance_incomplete"
                ),
                reason="provenance_incomplete",
                source="q6_scaffolding.queue_router",
                intake_id=record["intake_id"],
                card_name_hint=record.get("card_name_hint", ""),
                related_capability=capability,
                required_next_action=_QUEUE_ACTIONS["PROVENANCE_REVIEW"],
                blockers=["source_lock_incomplete"],
            )
            queues["PROVENANCE_REVIEW"].append(item.as_dict())
    for name in queues:
        queues[name].sort(key=lambda i: i["item_id"])
        for item in queues[name]:
            validate_output(item, artifact=f"queue-item:{name}")
    return queues


def scaffolding_failure_records(routed: list[dict]) -> list[dict]:
    """Emit failure-clustering input for scaffolding-side gaps only.

    Each record is consumable by ``tools/foundry/cluster_failures.cluster``
    (keys: id/message/evidence/verdict) with an extra ``kind`` marker that
    keeps scaffolding preparation gaps separate from engine/runtime behavior
    failures. Verdict is always UNKNOWN: clustering never assigns cause and
    never promotes anything to PASS.
    """
    records: list[dict] = []
    for record in sorted(routed, key=lambda r: r["intake_id"]):
        state = record["state"]
        if state == ScaffoldingState.READY_FOR_RUNTIME_QUALIFICATION.value:
            continue
        kind = {
            ScaffoldingState.AMBIGUOUS.value: "scaffolding/parser_failure",
            ScaffoldingState.UNSUPPORTED.value: "scaffolding/unsupported_capability",
            ScaffoldingState.MANUAL_REVIEW_REQUIRED.value: ("scaffolding/runtime_preparation_gap"),
            ScaffoldingState.RULES_ADJUDICATION_REQUIRED.value: (
                "scaffolding/runtime_preparation_gap"
            ),
        }.get(state, "scaffolding/scenario_generation_gap")
        for reason in sorted(set(record.get("reasons", ["state:" + state]))):
            records.append(
                {
                    "id": (
                        f"{record['intake_id']}:{state}:"
                        f"{hashlib.sha256(reason.encode()).hexdigest()[:12]}"
                    ),
                    "message": f"{kind} {record.get('card_name_hint', '')} {reason}",
                    "evidence": record["intake_id"],
                    "verdict": "UNKNOWN",
                    "kind": kind,
                }
            )
    return records


def cluster_scaffolding_failures(routed: list[dict]) -> list[dict]:
    """Group scaffolding failure records via the shared clustering helper."""
    return cluster_failures.cluster(scaffolding_failure_records(routed))


def queue_summary(queues: dict[str, list[dict]]) -> dict[str, Any]:
    """Deterministic per-queue counts plus total (no behavior semantics)."""
    return {
        "queues": {name: len(items) for name, items in sorted(queues.items())},
        "total_items": sum(len(items) for items in queues.values()),
    }
