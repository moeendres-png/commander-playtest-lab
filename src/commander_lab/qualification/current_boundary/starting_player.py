"""Authoritative starting-seat declarations, shared by every record-bearing lane.

The Lab never supplies a default starting seat and never silently chooses the
starting player (#572). A lane may answer an engine-authored STARTING_PLAYER
decision only when the authoritative record (or lane contract) explicitly
declares the seat, and the declaration is always recorded with its source. This
module is the single parser of record-level declarations so the generic lane,
the scripted-pregame lane and the Forge scenario lane cannot drift.

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

An ambiguous record has no declaration either. A record that carries two or
more starter declarations which *disagree* says two different things about who
starts, and an ambiguity is never resolved by order -- first-wins would let a
second, contradictory step quietly overrule or be overruled by the first. The
parser therefore returns ``(None, None)`` and the row is UNKNOWN. Identical
duplicates are not ambiguous (they state one thing twice) and are accepted;
the reported source is still the highest-precedence shape that declared it.
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


def _declarations(record: Any, *, pre_first_turn_shape: bool) -> list[tuple[str, str]] | None:
    """Every valid starter declaration of ``record``, in shape-precedence order.

    ``None`` means a declared shape carries no seat at all (a starting-player
    step without its fail-closed selection contract, or a ``starting_player``
    field naming no seat) while no valid declaration has been read yet: such a
    record has no authority to declare a starter, exactly as before. Once a
    valid declaration exists, a later malformed shape is ignored, and a
    pre-first-turn ``temporal_state`` that names no seat is never a declaration
    in the first place.
    """
    if not isinstance(record, dict):
        return []
    found: list[tuple[str, str]] = []
    for step in record.get("decision_script") or ():
        if not isinstance(step, dict) or step.get("decision_family") != "starting_player":
            continue
        seat = _seat_selector(step.get("selection"))
        if seat not in SEATS:
            if not found:
                return None
            continue
        found.append((seat, STARTER_DECLARATION_SCRIPT))

    declared = record.get("starting_player")
    if isinstance(declared, str):
        seat = _seat_text(declared)
        if seat not in SEATS:
            if not found:
                return None
        else:
            found.append((seat, STARTER_DECLARATION_FIELD))

    if pre_first_turn_shape:
        temporal = record.get("temporal_state")
        if isinstance(temporal, dict):
            turn = temporal.get("turn_number")
            active = temporal.get("active_player")
            if isinstance(turn, int) and not isinstance(turn, bool) and turn == 0:
                seat = _seat_text(active)
                if seat in SEATS:
                    found.append((seat, STARTER_DECLARATION_PRE_FIRST_TURN))
    return found


def _one_declaration(declarations: list[tuple[str, str]] | None) -> tuple[str | None, str | None]:
    """The record's one starting seat, or ``(None, None)`` when there is none.

    A missing, malformed or ambiguous set of declarations is no declaration:
    two declarations that disagree are never resolved by order.
    """
    if not declarations:
        return None, None
    if len({seat for seat, _ in declarations}) > 1:
        return None, None
    return declarations[0]


def record_starting_seat(record: dict[str, Any]) -> tuple[str | None, str | None]:
    """The record's explicit starting-seat declaration and its source, or ``(None, None)``.

    Two or more declarations that disagree are an ambiguity, not a declaration:
    the row is UNKNOWN rather than resolved by shape order.
    """
    return _one_declaration(_declarations(record, pre_first_turn_shape=True))


STARTER_DECLARATION_SETUP_ACTIVE_PLAYER = "RECORD_TEMPORAL_STATE_ACTIVE_PLAYER_SETUP"


STARTER_DECLARATION_TURN_ONE_ACTIVE_PLAYER = "RECORD_TEMPORAL_STATE_TURN_ONE_ACTIVE_PLAYER"


def midgame_starting_seat(record: Any) -> tuple[str | None, str | None]:
    """The starting seat a mid-game arrival must start the engine from.

    The record's explicit declaration (``starting_player`` decision-script step
    or top-level field) always wins. A requested state at turn 1 has exactly one
    consistent starter: turn 1 belongs to the starting player (CR 103.1), the
    engine still performs that turn itself, and the requested state's own
    ``active_player`` therefore is the starter. At any later checkpoint the
    active player is *not* the starter (turn 2 belongs to the next seat), so the
    arithmetic "starter = active - (turn - 1)" is never performed: without an
    explicit declaration the caller gets ``(None, None)`` and fails closed.
    An ambiguous explicit declaration is never resolved by falling back to the
    active player either.
    """
    declarations = _declarations(record, pre_first_turn_shape=True)
    if declarations is None:
        # A declared shape carries no seat at all: that is the parser's refusal
        # of malformed explicit authority, not the absence of a declaration.
        # Only an empty list (no declaration shape present) may use the
        # authorized turn-1 active-player shape below; a malformed explicit
        # ``starting_player`` field or script must never be salvaged from it.
        return None, None
    if declarations:
        declared = _one_declaration(declarations)
        if declared[0] is not None:
            return declared
        return None, None
    if not isinstance(record, dict):
        return None, None
    temporal = record.get("temporal_state")
    if isinstance(temporal, dict):
        turn = temporal.get("turn_number")
        if isinstance(turn, int) and not isinstance(turn, bool) and turn == 1:
            seat = _seat_text(temporal.get("active_player"))
            if seat in SEATS:
                return seat, STARTER_DECLARATION_TURN_ONE_ACTIVE_PLAYER
    return None, None


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
    model that declares no active player fails closed, and a record whose
    scripted step and explicit field disagree is ambiguous -- it never falls
    through to the setup shape either.
    """
    declared = _declarations(getattr(model, "record", None), pre_first_turn_shape=False)
    if declared is None or declared:
        return _one_declaration(declared)
    temporal = getattr(model, "temporal_state", None)
    if isinstance(temporal, dict):
        seat = _seat_text(temporal.get("active_player"))
        if seat in SEATS:
            return seat, STARTER_DECLARATION_SETUP_ACTIVE_PLAYER
    return None, None


def record_starting_seat_for_script_or_field(model: Any) -> tuple[str | None, str | None]:
    """Only the scripted-step / explicit-field declaration of a record-bearing model.

    Two of those declarations that disagree are an ambiguity, never a
    declaration resolved by order.
    """
    record = getattr(model, "record", None)
    return _one_declaration(_declarations(record, pre_first_turn_shape=False))
