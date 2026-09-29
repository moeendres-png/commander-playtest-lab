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

from . import receipts as seed_receipts
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
def _declares_seed_support(proc: BridgeProcess) -> bool:
    """Whether the provider declares that it accepts an authoritative seed.

    Absent or unparsable capability data is treated as "does not support", so an
    unknown provider never receives a seed it may reject. The converse mistake
    would be to assume support and fail the whole run.
    """
    try:
        response = proc.request("get_capabilities", {}, timeout_s=60.0)
    except Exception:
        return False
    capabilities = _payload(response).get("capabilities")
    if not isinstance(capabilities, dict):
        return False
    return capabilities.get("seed_supported") is True


def _create_request(
    game_id: str, handles: list[str], seed: int, seed_supported: bool
) -> dict[str, Any]:
    """The authoritative create-game request, with the seed only when supported.

    The seed must reach the provider's authoritative request when the provider
    accepts one, because a requested seed that never left the harness is the
    original defect. When the provider does not declare support, the seed is
    omitted rather than forced, and the run is honestly uncontrolled.
    """
    request: dict[str, Any] = {
        "game_id": game_id,
        "deck_handles": handles,
        "format": "commander",
        "external_control": True,
    }
    if seed_supported:
        request["seed"] = seed
        request["rules_seed"] = seed
        request["options"] = {"seed": seed, "rules_seed": seed}
    return {"request": request}


def _acknowledged_seed(response: Any) -> Any:
    """Extract whatever seed the provider actually acknowledged, if anything.

    A provider may echo the seed at the top level, inside a nested rules/rng
    object, or not at all. Returning ``None`` is a legitimate and important
    answer: it means the engine gave us nothing to confirm and the run is
    uncontrolled.
    """
    if not isinstance(response, dict):
        return None
    for key in ("rules_seed", "seed", "acknowledged_seed", "engine_seed"):
        if key in response:
            return response[key]
    for key in ("rules", "rng", "random", "options", "result", "state"):
        nested = response.get(key)
        if isinstance(nested, dict):
            found = _acknowledged_seed(nested)
            if found is not None:
                return found
    return None


DECISION_IDENTITY_SHAPES: dict[str, dict[str, Any]] = {
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
    decision_keys: list[str] = [shape["field"], *shape["pass_extra"]]
    for key in decision_keys:
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
    seed_binding: Any = None

    def to_document(self) -> dict[str, Any]:
        return {
            "rules_rng_binding": (
                self.seed_binding.to_document() if self.seed_binding is not None else None
            ),
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


def _require_ok(response: dict[str, Any], step: str) -> dict[str, Any]:
    """Unwrap a payload, raising with the provider's own error detail preserved.

    Reporting only the status made every provider rejection indistinguishable, and
    a rejected create request is not a diagnosable failure without its code and
    message. The detail is carried into the error text and, through the driver's
    failure record, into the evidence.
    """
    if not _first_ok(response):
        raise GameDriveError(f"{step} failed: {_failure_detail(response)}")
    return _payload(response)


def _failure_detail(response: dict[str, Any]) -> str:
    """A compact, faithful rendering of why the provider refused."""
    errors = response.get("errors")
    if isinstance(errors, list) and errors:
        parts = []
        for entry in errors:
            if isinstance(entry, dict):
                code = entry.get("code", "UNKNOWN")
                message = entry.get("message", "")
                parts.append(f"{code}: {message}" if message else str(code))
            else:
                parts.append(str(entry))
        return "; ".join(parts)
    status = response.get("status")
    return f"status={status!r} with no error detail from the provider"


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


def _zone_count_record(
    *,
    seat: int,
    hand: Any,
    library_size: int | None,
    principal: str,
    envelope_bound: bool,
) -> dict[str, Any]:
    """The persisted proof of one principal-scoped zone-count observation.

    ``engine_id_matches_state_row`` is emitted only when an observer envelope
    was actually present and its resolved live engine id was checked against
    the acting seat's own row. A marker-bound response has no engine id to
    compare, and recording ``false`` for it would read as a failed proof.
    """
    record: dict[str, Any] = {
        "seat": seat,
        "hand_count": len(hand) if isinstance(hand, list) else None,
        "library_count": library_size,
        "observer_player_id": principal,
        "binding_mechanism": "LIVE_ENGINE_ENVELOPE" if envelope_bound else "STATE_ACTOR_MARKER",
    }
    if envelope_bound:
        record["engine_id_matches_state_row"] = True
    return record


def _observe_principal_checkpoint(
    proc: BridgeProcess,
    *,
    game_id: str,
    principal: str,
    player_count: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read one principal-scoped zone-count + temporal checkpoint from the engine.

    The helper accepts only the two authoritative binding mechanisms already
    qualified by the current boundary: an exact live-engine observer envelope
    or a single in-state actor marker. It persists no live engine identifier.
    """
    if principal not in _SEATS[:player_count]:
        raise GameDriveError(
            f"principal {principal!r} is not one of {_SEATS[:player_count]}"
        )
    seat_index = _SEATS.index(principal)
    observed = proc.request(
        "get_game_state",
        {"observer_player_id": principal},
        game_id=game_id,
        timeout_s=60.0,
    )
    payload = _payload(observed)
    state_view = payload.get("state", payload)
    if not isinstance(state_view, dict):
        raise GameDriveError("principal-scoped response has no state object")
    rows = state_view.get("players")
    rows = rows if isinstance(rows, list) else []
    if seat_index >= len(rows) or not isinstance(rows[seat_index], dict):
        raise GameDriveError(
            "the principal-scoped response carries no row for the requested seat"
        )
    actor_row = rows[seat_index]
    if actor_row.get("seat") != seat_index:
        raise GameDriveError("the requested seat row does not report the requested seat")

    envelope_present = any(
        key in payload
        for key in ("observer_player_id", "observer_engine_player_id", "observer_seat")
    )
    envelope_bound = False
    if envelope_present:
        engine_id = payload.get("observer_engine_player_id")
        envelope_bound = (
            payload.get("observer_player_id") == principal
            and payload.get("observer_seat") == seat_index
            and isinstance(engine_id, str)
            and bool(engine_id)
            and actor_row.get("player_id") == engine_id
        )
        if not envelope_bound:
            raise GameDriveError(
                "the observer envelope does not bind the requested principal to "
                "the live engine row at the requested seat"
            )

    marked = [row for row in rows if isinstance(row, dict) and row.get("is_actor") is True]
    marker_bound = False
    if marked:
        marker_bound = len(marked) == 1 and marked[0].get("seat") == seat_index
        if not marker_bound:
            raise GameDriveError(
                "the in-state actor marker does not identify exactly the requested principal"
            )

    if not (envelope_bound or marker_bound):
        raise GameDriveError(
            "the response establishes no authoritative requested principal"
        )

    raw_zones = actor_row.get("zones")
    zones: dict[str, Any] = raw_zones if isinstance(raw_zones, dict) else {}
    hand = zones.get("hand")
    library_size = zones.get("library_size")
    if isinstance(library_size, bool) or not isinstance(library_size, int):
        library = zones.get("library")
        library_size = len(library) if isinstance(library, list) else None

    def _temporal_text(key: str) -> str | None:
        value = state_view.get(key)
        return str(value).strip().lower() if value is not None else None

    turn_number = state_view.get("turn_number")
    if isinstance(turn_number, bool) or not isinstance(turn_number, int):
        turn_number = None
    checkpoint = {
        "turn_number": turn_number,
        "phase": _temporal_text("phase"),
        "step": _temporal_text("step"),
        "observer_player_id": principal,
    }
    return (
        _zone_count_record(
            seat=seat_index,
            hand=hand,
            library_size=library_size,
            principal=principal,
            envelope_bound=envelope_bound,
        ),
        checkpoint,
    )


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

        # Whether the seed may be sent is a declared provider capability, not a
        # harness preference. The XMage generic B4-D lane reports
        # seed_supported=false and rejects a create request carrying a seed with
        # `unsupported_game_option`, which turned an honestly uncontrolled run
        # into a hard failure. Ask the provider, then send the seed only if it
        # declares support. When it does not, the run proceeds with no seed and
        # the binding below is UNCONTROLLED_ENGINE_RNG, which earns no RNG or
        # replay credit. That is the correct outcome, not a workaround.
        seed_supported = _declares_seed_support(proc)
        result.terminal_facts["provider_seed_supported"] = seed_supported
        result.terminal_facts["seed_sent_to_provider"] = bool(seed_supported)

        created = _require_ok(
            proc.request(
                "create_commander_game",
                _create_request(game_id, handles, seed, seed_supported),
                game_id=game_id,
                timeout_s=300.0,
            ),
            "create_commander_game",
        )
        # Seed control is derived from what the engine acknowledged, never from
        # the fact that the caller asked. An engine that echoes nothing is
        # UNCONTROLLED and earns no RNG or replay credit.
        binding = seed_receipts.classify_seed_binding(
            requested_seed=seed,
            acknowledged_seed=_acknowledged_seed(created),
            source="create_commander_game_response",
        )
        result.terminal_facts["rules_rng_binding"] = binding.to_document()
        result.seed_binding = binding
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
        start2_baseline_counts: dict[str, Any] | None = None
        start2_baseline_checkpoint: dict[str, Any] | None = None
        start2_post_counts: dict[str, Any] | None = None
        start2_post_checkpoint: dict[str, Any] | None = None
        start2_priority_checkpoints: list[dict[str, Any]] = []
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

                # START-2 is a temporal/state-transition obligation. Observe the
                # scripted starting principal at its own priority checkpoints:
                # upkeep supplies the post-mulligan/pre-draw baseline; precombat
                # main supplies the postcondition. A draw-step priority is itself
                # proof that CR 103.8a was not applied.
                if (
                    drive_to == "first_turn_draw_skip"
                    and frame.get("seat") == scripted_starting_seat
                ):
                    try:
                        counts, checkpoint = _observe_principal_checkpoint(
                            proc,
                            game_id=game_id,
                            principal=scripted_starting_seat,
                            player_count=player_count,
                        )
                        start2_priority_checkpoints.append(checkpoint)
                        turn = checkpoint.get("turn_number")
                        phase = checkpoint.get("phase")
                        step = checkpoint.get("step")
                        if (
                            turn == 1
                            and phase == "beginning"
                            and step == "upkeep"
                            and start2_baseline_counts is None
                        ):
                            start2_baseline_counts = counts
                            start2_baseline_checkpoint = checkpoint
                        if turn == 1 and phase == "beginning" and step == "draw":
                            draw_step_frames.append(
                                {
                                    "kind": kind,
                                    "actor": actor,
                                    "step": step,
                                    "phase": phase,
                                    "turn": turn,
                                    "source": "principal_scoped_state",
                                }
                            )
                            result.semantic_events.append(
                                f"draw_step_exposed:{scripted_starting_seat}"
                            )
                        if turn == 1 and phase == "precombat_main":
                            start2_post_counts = counts
                            start2_post_checkpoint = checkpoint
                            # The obligation is established at the first
                            # post-draw-step checkpoint. Do not mutate state by
                            # passing priority after the observation.
                            break
                    except Exception as exc:
                        result.terminal_facts.setdefault(
                            "start2_checkpoint_errors", []
                        ).append(str(exc))

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

        if drive_to == "first_turn_draw_skip":
            result.terminal_facts["start2_baseline_zone_counts"] = (
                [start2_baseline_counts] if start2_baseline_counts is not None else None
            )
            result.terminal_facts["start2_post_zone_counts"] = (
                [start2_post_counts] if start2_post_counts is not None else None
            )
            result.terminal_facts["start2_baseline_checkpoint"] = start2_baseline_checkpoint
            result.terminal_facts["start2_post_checkpoint"] = start2_post_checkpoint
            result.terminal_facts["start2_priority_checkpoints"] = start2_priority_checkpoints
            result.terminal_facts["observed_actor_zone_counts"] = (
                [start2_post_counts] if start2_post_counts is not None else None
            )
            result.terminal_facts["observed_zone_count_source"] = (
                "ENGINE_REPORTED_PRINCIPAL_SCOPED"
                if start2_post_counts is not None
                else None
            )

        result.terminal_facts["decision_identity_shape"] = DECISION_IDENTITY_SHAPES[candidate]
        result.terminal_facts["draw_step_decision_frames"] = draw_step_frames
        result.terminal_facts["draw_step_decision_exposed"] = bool(draw_step_frames)
        result.terminal_facts["priority_reached"] = priority_seen
        result.steps_completed.append("decision_drive")
    except (GameDriveError, DecisionUnsatisfied, BridgeLaunchError) as exc:
        result.failure = f"{type(exc).__name__}: {exc}"
        result.failure_kind = (
            "FAIL_CLOSED_UNSATISFIED"
            if isinstance(exc, DecisionUnsatisfied)
            else "ENGINE_RUNTIME_ERROR"
        )
    return result


def self_choice_pass(actions: list[dict[str, Any]], actor: str, revision: Any) -> str | None:
    """Return the pass option id when the engine offers one, else ``None``."""
    for action in actions:
        if action.get("action_type") in {"pass_priority", "pass"}:
            value = action.get("action_id")
            return str(value) if value else None
    return None
