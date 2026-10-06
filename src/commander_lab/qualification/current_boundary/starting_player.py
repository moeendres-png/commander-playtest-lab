"""Authoritative starting-seat declarations, shared by every record-bearing lane.

The Lab never chooses the starting player (#572). A lane may answer an
engine-authored STARTING_PLAYER decision only when the authoritative record (or
lane contract) explicitly declares the seat, and the declaration is always
recorded with its source. This module is the single parser of record-level
declarations so the generic lane, the scripted-pregame lane and the Forge
scenario lane cannot drift.

A declaration exists only in one of exactly three shapes:

1. a ``decision_script`` step whose ``decision_family`` is ``starting_player``,
   with the fail-closed selection contract intact and a ``seat`` selector
   naming one seat (the shape the Forge scenario lane already authorizes);
2. a top-level ``starting_player`` field naming a seat;
3. ``temporal_state.active_player`` only when the requested state is the
   pre-first-turn state (``turn_number`` 0), where the active player *is* the
   starting player (CR 103.1).

Anything else -- a later checkpoint's active player, an expected-event token, a
provider field, a lane default -- is no declaration: the caller gets
``(None, None)`` and the lane fails closed on the engine's frame.
"""

from __future__ import annotations

from typing import Any

SEATS = ("p1", "p2", "p3", "p4", "p5", "p6")

STARTER_DECLARATION_SCRIPT = "RECORD_DECISION_SCRIPT"
STARTER_DECLARATION_FIELD = "RECORD_STARTING_PLAYER_FIELD"
STARTER_DECLARATION_PRE_FIRST_TURN = "RECORD_TEMPORAL_STATE_PRE_FIRST_TURN_ACTIVE_PLAYER"


def _seat_text(value: Any) -> str:
    return str(value).strip().lower() if isinstance(value, str) else ""


def _seat_selector(selection: Any) -> str:
    """The seat a scripted starting-player decision names, or "" (no authority)."""
    if not isinstance(selection, dict):
        return ""
    if (
        selection.get("matches_only_provider_offered_legal_options") is not True
        or selection.get("on_zero_match") != "FAIL_CLOSED"
        or selection.get("on_multiple_match") != "FAIL_CLOSED"
        or selection.get("selector_kind") != "seat"
    ):
        return ""
    return _seat_text(selection.get("semantic_value"))


def record_starting_seat(record: dict[str, Any]) -> tuple[str | None, str | None]:
    """The record's explicit starting-seat declaration and its source, or ``(None, None)``."""
    for step in record.get("decision_script") or ():
        if not isinstance(step, dict) or step.get("decision_family") != "starting_player":
            continue
        seat = _seat_selector(step.get("selection"))
        return (seat, STARTER_DECLARATION_SCRIPT) if seat in SEATS else (None, None)

    declared = record.get("starting_player")
    if isinstance(declared, str):
        seat = _seat_text(declared)
        return (seat, STARTER_DECLARATION_FIELD) if seat in SEATS else (None, None)

    temporal = record.get("temporal_state")
    if isinstance(temporal, dict):
        turn = temporal.get("turn_number")
        active = temporal.get("active_player")
        if isinstance(turn, int) and not isinstance(turn, bool) and turn == 0:
            seat = _seat_text(active)
            if seat in SEATS:
                return seat, STARTER_DECLARATION_PRE_FIRST_TURN
    return None, None


STARTER_DECLARATION_SETUP_ACTIVE_PLAYER = "RECORD_TEMPORAL_STATE_ACTIVE_PLAYER_SETUP"


def requested_active_seat_index(record: Any) -> int | None:
    """The seat index of a requested state's own ``active_player``, or ``None``.

    The mid-game lane builds a requested mid-game state and the engine itself
    then offers the CR 103.2 starting-player choice to its choosing player; the
    lane's arrival pilot answers that frame from the same record field, so the
    create-time value is *who is asked*, never the starter. It is still an
    explicit, record-derived declaration: without it the lane fails closed
    instead of falling back to seat 0.
    """
    if not isinstance(record, dict):
        return None
    temporal = record.get("temporal_state")
    if isinstance(temporal, dict):
        seat = _seat_text(temporal.get("active_player"))
        if seat in SEATS:
            return SEATS.index(seat)
    return None


def scenario_setup_starting_seat(model: Any) -> tuple[str | None, str | None]:
    """The scenario lane's setup declaration of the starting seat, or ``(None, None)``.

    The Forge scenario lane constructs a requested state on top of a fresh game
    and must answer the engine's own starting-player frame to reach it. That
    answer is *setup*, never starting-player credit: a starting-player obligation
    is credited only on the scenario lane's ``FIXTURE_DECISION_SCRIPT`` basis
    (``evaluate_first_turn_draw``). The declaration precedence is the scripted
    step / explicit field first, then the requested state's own
    ``temporal_state.active_player`` (the state the engine will verify at the
    checkpoint), whatever turn that state is at. There is still no default: a
    model that declares no active player fails closed.
    """
    seat, source = record_starting_seat_for_script_or_field(model)
    if seat is not None:
        return seat, source
    temporal = getattr(model, "temporal_state", None)
    if isinstance(temporal, dict):
        seat = _seat_text(temporal.get("active_player"))
        if seat in SEATS:
            return seat, STARTER_DECLARATION_SETUP_ACTIVE_PLAYER
    return None, None


def record_starting_seat_for_script_or_field(model: Any) -> tuple[str | None, str | None]:
    """Only the scripted-step / explicit-field declaration of a record-bearing model."""
    record = getattr(model, "record", None)
    if not isinstance(record, dict):
        return None, None
    for step in record.get("decision_script") or ():
        if not isinstance(step, dict) or step.get("decision_family") != "starting_player":
            continue
        seat = _seat_selector(step.get("selection"))
        return (seat, STARTER_DECLARATION_SCRIPT) if seat in SEATS else (None, None)
    declared = record.get("starting_player")
    if isinstance(declared, str):
        seat = _seat_text(declared)
        return (seat, STARTER_DECLARATION_FIELD) if seat in SEATS else (None, None)
    return None, None
