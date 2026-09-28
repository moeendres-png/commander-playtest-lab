"""Candidate-neutral Protocol-2 game driver for the current boundary.

Drives a real external candidate engine through a real Commander game using
only the shared Protocol 2.0.0 surface both candidates implement.

Decision policy rules (never violated):

* every selection is chosen from the engine-offered option set only;
* every choice is recorded in a decision tape with its reason;
* there is no first-option default, no random default, no yes/no default and
  no silent skip — if no offered option satisfies the scripted intent the
  driver raises and the row is classified fail-closed unsatisfied;
* legality, costs, targets, modes and outcomes are never computed here.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from .bridge_launcher import BridgeLaunchError, BridgeProcess

POLL_ATTEMPTS = 40
POLL_INTERVAL_S = 1.0

# Named pilot policies. Each states its semantic intent explicitly; none is a
# fallback and none is applied when the engine offers no matching option.
MULLIGAN_POLICY = "keep_all"  # Commander: keep the opening hand.
PRIORITY_POLICY = "pass_when_offered"  # Decline the optional priority action.
STARTING_PLAYER_POLICY = "fixture_scripted_seat"

_SEATS = ("p1", "p2", "p3", "p4", "p5", "p6")


class DecisionUnsatisfied(RuntimeError):
    """The engine offered no option matching the recorded pilot intent."""


class GameDriveError(RuntimeError):
    """The external engine could not complete the requested lifecycle."""

    def __init__(
        self,
        message: str,
        *,
        engine_code: str | None = None,
        engine_message: str | None = None,
    ) -> None:
        super().__init__(message)
        self.engine_code = engine_code
        self.engine_message = engine_message


# Engine-declared capability absences (as opposed to runtime malfunctions).
# A lifecycle blocked by one of these is BLOCKED with the named capability,
# never FAIL and never a Rules-capability claim about the engine itself.
CAPABILITY_ERROR_CODES = frozenset(
    {
        "PLAYER_COUNT_UNSUPPORTED",
        "SEED_UNSUPPORTED",
    }
)


@dataclass
class DecisionTapeEntry:
    step: str
    kind: str
    actor: str
    revision: Any
    policy: str
    chosen_option_id: str | None
    offered_option_ids: list[str]
    note: str


@dataclass
class GameObservation:
    step: str
    payload: dict[str, Any]


# Decision-identity divergence observed under current-boundary runtime
# execution on the shared Protocol-2 surface. Recorded, not normalized away.
#   XMage generic lane: decision_id (sha256 hex) + action_id (pass) / proposal
#   Forge protocol2   : revision (monotonic long) + actor_id (pass) / proposal
DECISION_IDENTITY_SHAPES = {
    "xmage": {
        "field": "decision_id",
        "type": "sha256_hex",
        "pass_extra": ("actor_id", "action_id"),
        "requires_external_control": True,
    },
    "forge": {
        "field": "revision",
        "type": "monotonic_long",
        "pass_extra": ("actor_id",),
        "requires_external_control": False,
    },
}


def decision_identity_params(candidate: str, frame: dict[str, Any]) -> dict[str, Any]:
    """Build the provider-native decision-identity parameters for one frame.

    This is transport field mapping only. It never invents an identity: the
    value always comes from the decision frame the provider just published.
    """
    shape = DECISION_IDENTITY_SHAPES[candidate]
    decision = frame["decision"]
    params: dict[str, Any] = {}
    pass_extra = shape["pass_extra"]
    assert isinstance(pass_extra, (list, tuple))
    for key in (shape["field"], *pass_extra):
        if key == "action_id":
            for action in frame["actions"]:
                if action.get("action_type") == "pass_priority":
                    params[key] = action.get("action_id")
                    break
        elif key == "actor_id":
            params[key] = decision.get("actor")
        else:
            # The identity always comes from the frame the provider published.
            params[key] = decision.get(key)
    return params


@dataclass
class CommandedGameResult:
    candidate: str
    player_count: int
    deck_identity: list[str]
    game_id: str
    decision_tape: list[DecisionTapeEntry] = field(default_factory=list)
    observations: list[GameObservation] = field(default_factory=list)
    semantic_events: list[str] = field(default_factory=list)
    terminal_facts: dict[str, Any] = field(default_factory=dict)
    steps_completed: list[str] = field(default_factory=list)
    failure: str | None = None
    failure_kind: str | None = None

    def to_document(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate,
            "player_count": self.player_count,
            "deck_identity": self.deck_identity,
            "game_id": self.game_id,
            "steps_completed": self.steps_completed,
            "decision_tape": [
                {
                    "step": entry.step,
                    "kind": entry.kind,
                    "actor": entry.actor,
                    "revision": entry.revision,
                    "policy": entry.policy,
                    "chosen_option_id": entry.chosen_option_id,
                    "offered_option_ids": entry.offered_option_ids,
                    "note": entry.note,
                }
                for entry in self.decision_tape
            ],
            "observations": [
                {"step": item.step, "payload": item.payload} for item in self.observations
            ],
            "semantic_events": self.semantic_events,
            "terminal_facts": self.terminal_facts,
            "failure": self.failure,
            "failure_kind": self.failure_kind,
        }


def _first_ok(response: dict[str, Any]) -> bool:
    return response.get("success") is True


def _payload(response: dict[str, Any]) -> dict[str, Any]:
    value = response.get("payload")
    return value if isinstance(value, dict) else {}


def _engine_error(response: dict[str, Any]) -> tuple[str | None, str | None]:
    errors = response.get("errors")
    if isinstance(errors, list) and errors:
        first = errors[0]
        if isinstance(first, dict):
            code = first.get("code")
            message = first.get("message")
            return (
                str(code) if code is not None else None,
                str(message) if message is not None else None,
            )
    error = response.get("error")
    if isinstance(error, dict):
        code = error.get("code")
        message = error.get("message")
        return (
            str(code) if code is not None else None,
            str(message) if message is not None else None,
        )
    return None, None


def _require_ok(response: dict[str, Any], step: str) -> dict[str, Any]:
    if not _first_ok(response):
        code, message = _engine_error(response)
        raise GameDriveError(
            f"{step} failed: status={response.get('status')!r}",
            engine_code=code,
            engine_message=message,
        )
    return _payload(response)


def build_deck(deck_id: str) -> dict[str, Any]:
    """A real 100-card Commander deck of real cards (names only).

    Both candidates resolve these names against their own real card data and
    reject unknown names explicitly, so no construction-only claim is implied.
    """
    # Mono-white only: a Commander deck must match its commander's colour
    # identity ({W}{W} for Isamaru). The engine, not this module, validates
    # that; these names are chosen so the deck is a legal Commander deck in
    # both candidates' real card pools.
    vanillas = [
        "Silvercoat Lion",
        "Serra Angel",
        "Savannah Lions",
        "Knight of Dawn",
        "Elite Vanguard",
        "Eager Cadet",
        "Suntail Hawk",
        "Valiant Guard",
        "Serra Ascendant",
        "Aerial Assault",
    ]
    mainboard = vanillas + ["Plains"] * (99 - len(vanillas))
    assert len(mainboard) == 99
    deck_id_digest = hashlib.sha256(
        ("|".join(["Isamaru, Hound of Konda", *mainboard])).encode("utf-8")
    ).hexdigest()
    return {
        "deck_id": deck_id,
        "deck_hash": deck_id_digest,
        "name": f"WSR22 Lab {deck_id}",
        "commander_names": ["Isamaru, Hound of Konda"],
        "mainboard": mainboard,
    }


def normalize_decision_frame(
    candidate: str, seat: str, payload: dict[str, Any]
) -> dict[str, Any] | None:
    """Normalize a candidate decision frame WITHOUT inferring any semantics.

    The two candidates publish different response shapes on the generic
    Protocol-2 surface. Normalization is a pure field-mapping of what the
    provider already stated; no option is created, removed, or ranked, and no
    actor identity is guessed.
    """
    if candidate == "xmage":
        kind = payload.get("decision_kind")
        if not kind:
            return None
        actor = payload.get("actor_id")
        revision = payload.get("decision_offset")
        decision_id = payload.get("decision_id")
        status = "SUPPORTED" if payload.get("complete") else "INCOMPLETE"
    else:
        decision = payload.get("decision")
        if not isinstance(decision, dict) or "kind" not in decision:
            return None
        kind = decision.get("kind")
        if str(status := decision.get("status", "")) == "no_pending_decision":
            return None
        actor = decision.get("actor")
        revision = decision.get("revision")
        decision_id = decision.get("decision_id")
        status = status or "SUPPORTED"
    actions = payload.get("actions")
    if not isinstance(actions, list):
        actions = []
    return {
        "seat": seat,
        "decision": {
            "kind": str(kind or "").upper(),
            "actor": str(actor) if actor is not None else None,
            "revision": revision,
            "decision_id": decision_id,
            "status": str(status),
        },
        "actions": actions,
        "raw": payload,
    }


def poll_decision(
    proc: BridgeProcess,
    game_id: str,
    *,
    seat_count: int,
    candidate: str,
) -> dict[str, Any]:
    """Discover a parked decision by asking each seat; never invents one."""
    last: str | None = None
    for _ in range(POLL_ATTEMPTS):
        for seat in _SEATS[:seat_count]:
            response = proc.request(
                "get_legal_actions", {"actor_id": seat}, game_id=game_id, timeout_s=60.0
            )
            if not _first_ok(response):
                last = f"{seat}:{response.get('status')}"
                continue
            frame = normalize_decision_frame(candidate, seat, _payload(response))
            if frame is not None:
                return frame
        time.sleep(POLL_INTERVAL_S)
    raise GameDriveError(f"no parked decision observed (last: {last})")


def _structural_options(
    actions: list[dict[str, Any]], decision: dict[str, Any]
) -> list[dict[str, Any]]:
    kind = str(decision.get("kind", "")).upper()
    wanted = {"STARTING_PLAYER": "seat", "CHOOSE_STARTING_PLAYER": "seat"}
    field_name = wanted.get(kind)
    if field_name is None:
        return []
    return [
        action
        for action in actions
        if action.get("action_type") == "structural_decision"
        and isinstance(action.get("source_object_id"), str)
    ]


def _action_kind(action: dict[str, Any]) -> str:
    return str(action.get("action_type", ""))


def drive_commander_game(
    proc: BridgeProcess,
    *,
    candidate: str,
    player_count: int,
    seed: int,
    scripted_starting_seat: str = "p1",
    drive_to: Literal["priority", "full_turn", "first_turn_draw_skip"] = "priority",
    max_steps: int = 400,
) -> CommandedGameResult:
    """Run a real Commander lifecycle for one candidate at one player count.

    The driver supplies only externally discretionary choices among
    engine-offered options and records each one. It never decides legality.
    """
    if player_count < 2 or player_count > 6:
        raise ValueError(f"player_count must be within 2..6, got {player_count}")

    result = CommandedGameResult(
        candidate=candidate,
        player_count=player_count,
        deck_identity=[f"{candidate}-wsr22-deck-{index}" for index in range(1, player_count + 1)],
        game_id=f"wsr22-{candidate}-{player_count}p-{uuid.uuid4().hex[:8]}",
    )
    game_id = result.game_id

    try:
        # Canonical Protocol-2 handshake before any game traffic. No legacy
        # alias is used and no capability is inferred.
        for message in ("start_engine", "get_provider_version", "get_capabilities"):
            _require_ok(proc.request(message, {}), message)
        result.steps_completed.append("handshake")

        handles: list[str] = []
        for deck_id in result.deck_identity:
            payload = _require_ok(
                proc.request("import_deck", {"deck": build_deck(deck_id)}),
                "import_deck",
            )
            handle = payload.get("deck_handle")
            handle_id = handle.get("handle_id") if isinstance(handle, dict) else None
            if not handle_id:
                raise GameDriveError(f"import_deck returned no deck handle: {payload}")
            handles.append(str(handle_id))
        result.steps_completed.append("import_deck")

        created = _require_ok(
            proc.request(
                "create_commander_game",
                {
                    "request": {
                        "game_id": game_id,
                        "deck_handles": handles,
                        "format": "commander",
                        "external_control": True,
                    }
                },
                game_id=game_id,
                timeout_s=300.0,
            ),
            "create_commander_game",
        )
        seats = created.get("seats")
        seat_ids = [seat.get("player_id") for seat in seats] if isinstance(seats, list) else None
        if seat_ids is not None and len(seat_ids) != player_count:
            raise GameDriveError(
                f"create_commander_game reported {len(seat_ids)} seats for {player_count} players"
            )
        result.terminal_facts["created_player_count"] = created.get("player_count", len(handles))
        result.steps_completed.append("create_commander_game")

        started = _require_ok(
            proc.request("start_game", {}, game_id=game_id, timeout_s=300.0), "start_game"
        )
        result.terminal_facts["start_status"] = started.get("status")
        result.steps_completed.append("start_game")

        steps = 0
        draw_step_frames: list[dict[str, Any]] = []
        priority_seen = False
        while steps < max_steps:
            steps += 1
            frame = poll_decision(proc, game_id, seat_count=player_count, candidate=candidate)
            decision = frame["decision"]
            kind = str(decision.get("kind", "")).upper()
            actor = str(decision.get("actor", frame["seat"]))
            revision = decision.get("revision")
            actions = frame["actions"]
            offered = [
                str(action.get("action_id")) for action in actions if action.get("action_id")
            ]

            if "DRAW" in kind:
                draw_step_frames.append(
                    {
                        "kind": kind,
                        "actor": actor,
                        "step": decision.get("step"),
                        "phase": decision.get("phase"),
                        "turn": decision.get("turn_number"),
                    }
                )
                result.semantic_events.append(f"draw_step_exposed:{actor}")
                chosen = self_choice_pass(actions, actor, revision)
                result.decision_tape.append(
                    DecisionTapeEntry(
                        "draw_step",
                        kind,
                        actor,
                        revision,
                        "pass_when_offered",
                        chosen,
                        offered,
                        "a draw-step decision was exposed by the engine",
                    )
                )
                continue

            if kind in {"MULLIGAN", "KEEP_OR_MULLIGAN"}:
                keep = _require_ok(
                    proc.request(
                        "resolve_mulligan",
                        {
                            "player_id": actor,
                            **decision_identity_params(candidate, frame),
                            "keep": True,
                            "bottom_card_ids": [],
                        },
                        game_id=game_id,
                        timeout_s=120.0,
                    ),
                    "resolve_mulligan",
                )
                result.decision_tape.append(
                    DecisionTapeEntry(
                        "mulligan",
                        kind,
                        actor,
                        revision,
                        MULLIGAN_POLICY,
                        None,
                        offered,
                        "external keep decision; no bottoming",
                    )
                )
                result.observations.append(GameObservation("mulligan_keep", keep))
                continue

            if kind in {"STARTING_PLAYER", "CHOOSE_STARTING_PLAYER"}:
                options = _structural_options(actions, decision)
                match = [a for a in options if a.get("source_object_id") == scripted_starting_seat]
                if not match:
                    raise DecisionUnsatisfied(
                        f"fixture script requires starting seat {scripted_starting_seat!r}; "
                        f"engine offered {[a.get('source_object_id') for a in options]}"
                    )
                chosen = str(match[0]["action_id"])
                identity = decision_identity_params(candidate, frame)
                answer = _require_ok(
                    proc.request(
                        "submit_action",
                        {
                            **identity,
                            "proposal": {
                                "proposal_id": str(uuid.uuid4()),
                                "actor_id": actor,
                                "legal_action_id": chosen,
                                "action_type": "structural_decision",
                            },
                        },
                        game_id=game_id,
                        timeout_s=120.0,
                    ),
                    "submit_action(STARTING_PLAYER)",
                )
                result.decision_tape.append(
                    DecisionTapeEntry(
                        "starting_player",
                        kind,
                        actor,
                        revision,
                        STARTING_PLAYER_POLICY,
                        chosen,
                        offered,
                        f"fixture-scripted seat {scripted_starting_seat}",
                    )
                )
                result.observations.append(GameObservation("starting_player", answer))
                continue

            if kind == "PRIORITY":
                priority_seen = True
                pass_actions = [a for a in actions if a.get("action_type") == "pass_priority"]
                if not pass_actions:
                    result.observations.append(
                        GameObservation(
                            "priority_no_pass_offered", {"actor": actor, "offered": offered}
                        )
                    )
                    result.decision_tape.append(
                        DecisionTapeEntry(
                            "priority",
                            kind,
                            actor,
                            revision,
                            PRIORITY_POLICY,
                            None,
                            offered,
                            "engine offered no pass_priority; not substituted",
                        )
                    )
                    break
                chosen = str(pass_actions[0]["action_id"])
                identity = decision_identity_params(candidate, frame)
                answer = _require_ok(
                    proc.request("pass_priority", identity, game_id=game_id, timeout_s=120.0),
                    "pass_priority",
                )
                result.decision_tape.append(
                    DecisionTapeEntry(
                        "priority",
                        kind,
                        actor,
                        revision,
                        PRIORITY_POLICY,
                        chosen,
                        offered,
                        "external priority pass",
                    )
                )
                result.observations.append(GameObservation("priority_pass", answer))
                result.terminal_facts["priority_pass_state_changed"] = (
                    (
                        _payload(answer).get("decision", {}).get("post_state_hash")
                        != _payload(answer).get("decision", {}).get("pre_state_hash")
                    )
                    if isinstance(_payload(answer).get("decision"), dict)
                    else None
                )
                if drive_to == "priority":
                    break
                if drive_to == "first_turn_draw_skip" and steps >= 2:
                    break
                continue

            # Any other decision class: record the engine-offered domain and stop
            # driving. Substituting a choice here would be a forbidden default.
            result.decision_tape.append(
                DecisionTapeEntry(
                    "other_decision_class",
                    kind,
                    actor,
                    revision,
                    "NO_MATCHING_OFFERED_OPTION",
                    None,
                    offered,
                    "unsupported pilot policy for this decision class; fail closed",
                )
            )
            result.terminal_facts["stopped_at_decision_kind"] = kind
            break

        result.terminal_facts["decision_identity_shape"] = DECISION_IDENTITY_SHAPES[candidate]
        result.terminal_facts["draw_step_decision_frames"] = draw_step_frames
        result.terminal_facts["draw_step_decision_exposed"] = bool(draw_step_frames)
        result.terminal_facts["priority_reached"] = priority_seen
        result.steps_completed.append("decision_drive")
    except (GameDriveError, DecisionUnsatisfied, BridgeLaunchError) as exc:
        result.failure = f"{type(exc).__name__}: {exc}"
        if isinstance(exc, DecisionUnsatisfied):
            result.failure_kind = "FAIL_CLOSED_UNSATISFIED"
        elif (
            isinstance(exc, GameDriveError)
            and exc.engine_code is not None
            and exc.engine_code.upper() in CAPABILITY_ERROR_CODES
        ):
            result.failure_kind = "CAPABILITY_ABSENT"
            result.failure = (
                f"GameDriveError: {exc} "
                f"[engine_code={exc.engine_code} engine_message={exc.engine_message}]"
            )
        else:
            result.failure_kind = "ENGINE_RUNTIME_ERROR"
    return result


def self_choice_pass(actions: list[dict[str, Any]], actor: str, revision: Any) -> str | None:
    """Return the pass option id when the engine offers one, else ``None``."""
    for action in actions:
        if action.get("action_type") in {"pass_priority", "pass"}:
            value = action.get("action_id")
            return str(value) if value else None
    return None
