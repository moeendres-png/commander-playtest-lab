"""Normalized semantic comparison between candidates.

`SAME_SEMANTICS` used to be decided by two exit labels:

    if xr["exit_state"] == fr["exit_state"] == "PASS":
        disposition = "SAME_SEMANTICS"

That is not a semantic comparison. Two engines can each report PASS while
observing materially different things -- a different turn number, a different
library count, an extra or missing event in the sequence -- and this labelled
them equal. The label is also what the historical ``25/107 SAME_SEMANTICS``
figure counted, so the figure never measured semantics at all.

This module compares the *observed* facts. Each side is reduced to a normalized
signature over the semantic evidence it actually recorded, and the two
signatures are compared. Normalization removes everything that is legitimately
candidate-specific (engine commit, provider name, session and object ids,
timestamps, absolute paths) while preserving everything the Rules can observe.

Absence is handled honestly. A side with no semantic evidence yields
``NO_SIGNATURE``, and no equality is claimed from it. Equal labels with unequal
signatures are a *difference*, not a pass.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

# Keys that legitimately differ between candidates or between runs. Removing
# them is what makes a comparison semantic rather than incidental.
_IDENTITY_KEYS: frozenset[str] = frozenset(
    {
        "actor_id",
        "active_player_id",
        "active_player_actor_safe_id",
        "actor_safe_id",
        "bridge_pid",
        "candidate",
        "commit",
        "controller_id",
        "decision_id",
        "duration_seconds",
        "engine_build",
        "engine_candidate_commit",
        "engine_candidate_tree",
        "engine_commit",
        "engine_identity",
        "engine_version",
        "executed_decision_id",
        "exit_state",
        "execution_mode",
        "evidence_class",
        "failure_reason",
        "fixture_id",
        "game_id",
        "handle",
        "host",
        "lane",
        "object_id",
        "pid",
        "plan_id",
        "player_id",
        "priority_player_id",
        "priority_player_actor_safe_id",
        "provider",
        "provider_version",
        "receipt_digest",
        "reason",
        "request_id",
        "revision",
        "runner_commit",
        "runner_tree",
        "rules_authority",
        "runner_root",
        "seat",
        "session_id",
        "source_revision",
        "started_at",
        "wall_clock",
    }
)

# Values that are never semantic: durations, pids, absolute paths, hashes of
# candidate-specific bytes.
_VOLATILE_VALUE = re.compile(
    r"^(/|\d{4}-\d{2}-\d{2}T|[0-9a-f]{32,}$)",
    re.IGNORECASE,
)

# The evidence keys that carry the Rules-visible observations for a row. A row
# that recorded none of these cannot support a semantic comparison.
SEMANTIC_EVIDENCE_KEYS: tuple[str, ...] = (
    "semantic_events",
    "observed_decision_kinds",
    "observed_draw_semantic_events",
    "observed_draw_step_frames",
    "observed_actor_zone_counts",
    "observed_starting_actor",
    "decision_tape",
    "terminal_facts",
    "draw_step_decision_exposed",
    "priority_reached",
    "created_player_count",
    "player_count",
)


def _strip(value: Any, key: str | None = None) -> Any:
    if key is not None and key in _IDENTITY_KEYS:
        return None
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for inner_key, inner_value in value.items():
            stripped = _strip(inner_value, inner_key)
            if stripped is not None:
                out[inner_key] = stripped
        return out
    if isinstance(value, (list, tuple)):
        return [_strip(item) for item in value]
    if isinstance(value, str) and _VOLATILE_VALUE.match(value):
        return None
    if isinstance(value, float):
        return value
    return value


def semantic_signature(row: dict[str, Any]) -> dict[str, Any]:
    """Reduce a row to its normalized Rules-visible observations.

    Returns ``{"present": False}`` when the row recorded no semantic evidence,
    which the caller must treat as "cannot claim equality" rather than "equal".
    """
    evidence = row.get("evidence") or {}
    if not isinstance(evidence, dict):
        return {"present": False, "reason": "no evidence mapping recorded"}

    observed: dict[str, Any] = {}
    for key in SEMANTIC_EVIDENCE_KEYS:
        if key in evidence:
            stripped = _strip(evidence[key], key)
            if stripped not in (None, {}, []):
                observed[key] = stripped

    if not observed:
        return {
            "present": False,
            "reason": "the row recorded none of the semantic evidence keys, so no "
            "semantic comparison is possible from PASS labels alone",
            "searched": list(SEMANTIC_EVIDENCE_KEYS),
        }

    canonical = json.dumps(observed, sort_keys=True, default=str, separators=(",", ":"))
    return {
        "present": True,
        "observed_keys": sorted(observed),
        "digest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "normalized": observed,
    }


def compare_semantics(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Compare two rows semantically.

    The returned ``disposition`` is one of:

    ``SAME_SEMANTICS``
        Both sides recorded semantic evidence and the normalized observations are
        byte-identical after removing candidate-specific identity.
    ``SEMANTIC_DIFFERENCE``
        Both sides recorded evidence and it differs. This needs Rules
        adjudication; it is not a pass and not a tie.
    ``UNKNOWN_NO_COMPARABLE_EVIDENCE``
        At least one side recorded no semantic evidence, so equality cannot be
        established. This is an evidence gap.
    """
    left_signature = semantic_signature(left)
    right_signature = semantic_signature(right)

    if not left_signature["present"] or not right_signature["present"]:
        missing = "left" if not left_signature["present"] else "right"
        return {
            "disposition": "UNKNOWN_NO_COMPARABLE_EVIDENCE",
            "equal": None,
            "left": {"present": left_signature["present"]},
            "right": {"present": right_signature["present"]},
            "reason": (
                f"the {missing} side recorded no semantic evidence, so PASS/PASS "
                "labels cannot establish semantic equality"
            ),
        }

    equal = left_signature["digest"] == right_signature["digest"]
    differing = sorted(
        key
        for key in set(left_signature["observed_keys"]) | set(right_signature["observed_keys"])
        if json.dumps(left_signature["normalized"].get(key), sort_keys=True, default=str)
        != json.dumps(right_signature["normalized"].get(key), sort_keys=True, default=str)
    )
    return {
        "disposition": "SAME_SEMANTICS" if equal else "SEMANTIC_DIFFERENCE",
        "equal": equal,
        "left_digest": left_signature["digest"],
        "right_digest": right_signature["digest"],
        "differing_keys": differing,
        "compared_keys": left_signature["observed_keys"],
        "reason": (
            "the normalized Rules-visible observations are identical"
            if equal
            else "both sides report PASS but the normalized observations differ on: "
            + ", ".join(differing)
        ),
    }
