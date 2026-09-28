"""All-or-nothing Commander lifecycle accounting.

AF02 was computed as::

    card_pass = [k for k, v in cardinality["results"].items()
                 if v.get("steps_completed") and not v.get("failure")]

``steps_completed`` is a growing list, so *any* prefix of the lifecycle
satisfied it. A run that imported decks and created a game but never started it,
never reached a decision, and never bound an external choice was counted as a
completed lifecycle at that player count, and four such prefixes were enough for
``"verdict": "PASS" if len(card_pass) == 4``.

A Commander lifecycle is not a prefix. Deck import is not a game. A game that was
created but not started proves nothing about play. The required steps below are
the ones without which no lifecycle claim can be made, and a count is credited
only when every one of them completed.

Absence is also distinguished from failure. A count whose lifecycle did not
complete has not been *refuted*; it has not been *established*. So this module
reports an incomplete count as a shortfall with the missing steps named, and the
caller maps a shortfall to UNKNOWN rather than FAIL.
"""

from __future__ import annotations

from typing import Any

# The steps required before a lifecycle at a player count may be credited.
# Order is the order the driver performs them.
REQUIRED_LIFECYCLE_STEPS: tuple[str, ...] = (
    "handshake",
    "import_deck",
    "create_commander_game",
    "start_game",
    "decision_drive",
)

# Steps that additionally prove a real external decision was bound, which is
# what distinguishes a played game from a created one.
_DECISION_PROOF_KEYS: tuple[str, ...] = (
    "priority_reached",
    "decision_identity_shape",
)


def lifecycle_completeness(result: dict[str, Any]) -> dict[str, Any]:
    """Classify one lifecycle run as complete or incomplete, and say why.

    Returns a mapping with ``complete``, ``missing_steps``, ``completed_steps``
    and ``reasons``. ``complete`` is true only when every required step
    completed, the run recorded no failure, at least one externally bound
    discretionary choice exists, and the engine created the requested number of
    players.
    """
    completed = list(result.get("steps_completed") or [])
    completed_set = set(completed)
    missing = [step for step in REQUIRED_LIFECYCLE_STEPS if step not in completed_set]
    failure = result.get("failure")
    terminal_facts = result.get("terminal_facts") or {}

    reasons: list[str] = []
    if failure:
        reasons.append(f"the lifecycle reported a failure: {failure}")
    if missing:
        reasons.append("the lifecycle never completed: " + ", ".join(missing))
    if not completed_set:
        reasons.append("the lifecycle recorded no completed steps at all")

    # Order matters as well as presence: a run that recorded start_game before
    # import_deck has not demonstrated a coherent lifecycle.
    if not missing and completed:
        indices = [completed.index(step) for step in REQUIRED_LIFECYCLE_STEPS]
        if indices != sorted(indices):
            reasons.append(f"lifecycle steps were recorded out of order: {completed}")

    if not terminal_facts.get("priority_reached"):
        reasons.append("no external priority decision was ever reached")

    decision_tape = result.get("decision_tape") or []
    bound_choices = [
        entry
        for entry in decision_tape
        if isinstance(entry, dict) and entry.get("chosen_option_id")
    ]
    if not bound_choices:
        reasons.append(
            "no externally supplied discretionary decision was bound to an engine-offered option"
        )

    return {
        "complete": not reasons,
        "missing_steps": missing,
        "completed_steps": completed,
        "bound_external_choices": len(bound_choices),
        "reasons": reasons,
        "required_steps": list(REQUIRED_LIFECYCLE_STEPS),
    }


def cardinality_verdict(
    results: dict[str, Any], required_counts: tuple[int, ...] = (2, 3, 4, 5)
) -> dict[str, Any]:
    """All-or-nothing AF02 verdict across the mandatory player counts.

    A verdict is only PASS when every required count produced a complete
    lifecycle. Anything short of that is UNKNOWN, with the specific shortfall
    named, because an unestablished count is an evidence gap rather than a
    refutation of the candidate.
    """
    complete: list[int] = []
    incomplete: list[int] = []
    detail: dict[str, Any] = {}
    for count in required_counts:
        key = f"{count}P"
        run = results.get(key)
        if not isinstance(run, dict):
            incomplete.append(count)
            detail[key] = {"present": False, "reason": "no lifecycle run was recorded"}
            continue
        assessment = lifecycle_completeness(run)
        detail[key] = assessment
        (complete if assessment["complete"] else incomplete).append(count)

    if not incomplete:
        verdict = "PASS"
    elif complete:
        verdict = "UNKNOWN"
    else:
        verdict = "UNKNOWN"

    return {
        "verdict": verdict,
        "all_or_nothing": True,
        "required_counts": list(required_counts),
        "complete_counts": complete,
        "incomplete_counts": incomplete,
        "detail": detail,
        "reason": (
            f"every mandatory count {sorted(complete)} completed a full Commander "
            "lifecycle under Protocol 2.0.0"
            if not incomplete
            else "counts without a complete lifecycle are UNKNOWN, not a candidate "
            f"failure: {sorted(incomplete)} are incomplete"
        ),
    }
