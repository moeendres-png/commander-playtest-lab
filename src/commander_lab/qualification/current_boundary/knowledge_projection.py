"""AF05 actor-entitled knowledge projection on the production mid-game lane.

For the HIDDEN_* rows whose obligation is a knowledge boundary at a constructed
checkpoint, the record is executed on the XMage mid-game lane and the boundary
is verified against the engine's own actor-entitled projection and against
every channel a principal receives::

    SLOT-04 lossless successor record -> native construction with the engine's
    field-level and lossless readback (EXACT, and every lossless check the
    record declares reported as performed) -> the actor-entitled projection of
    every principal, read from the live rules state -> the record's own viewer
    obligation, compared against values the record itself requests ->
    forbidden-identity and honey-sentinel scan over every channel the viewer
    receives, with positive controls -> runner-bound positive receipt

The module computes no Rules semantics and chooses nothing. What a principal
may know is read from the record (semantic objects, deck state, look
permissions, honey sentinels); what the principal was shown is read from the
engine. A row is verified only if every check holds and no scan is vacuous.

A demonstrated defect is never reported as UNKNOWN: an identity a principal is
not entitled to found in a channel that principal receives, or entitled
information missing although the engine verified the state it comes from, is
classified as a FAIL with the exact findings. Anything this module could not
measure leaves the row unverified, which earns nothing.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import midgame_lane as ml
from . import midgame_rows as midgame_rows_mod
from . import receipts as receipt_mod

EXECUTION_MODE = "MIDGAME_LANE_KNOWLEDGE_PROJECTION"
TEST_IDENTITY_PREFIX = "midgame-lane:knowledge-projection#"
RECEIPT_FILE_PREFIX = "knowledge-projection-xmage--"
EXECUTIONS_SCHEMA = "commander-lab.knowledge-projection-executions/1.0.0"
POSITIVE_FIXTURE_RECEIPT_SCHEMA = receipt_mod.POSITIVE_FIXTURE_RECEIPT_SCHEMA

VERIFIED = "VERIFIED"
UNVERIFIED = "UNVERIFIED"
FAIL_DEMONSTRATED_LEAK = "FAIL_DEMONSTRATED_LEAK"
FAIL_ENTITLEMENT_DENIED = "FAIL_ENTITLEMENT_DENIED"
FAIL_CLASSIFICATIONS = (FAIL_DEMONSTRATED_LEAK, FAIL_ENTITLEMENT_DENIED)

# The construct-and-project rows and the knowledge obligation each one names.
# The obligation kind selects which of the record's own requests is the row's
# focus; every check reads its expected values from the record itself.
ROWS: dict[str, str] = {
    "HIDDEN_01": "opponent_hand",
    "HIDDEN_02": "opponent_library",
    "HIDDEN_03": "public_exile",
    "HIDDEN_04": "face_down_controller",
    "HIDDEN_19": "no_omniscient_api",
    "HIDDEN_HONEYCARD_SENTINEL": "honey_sentinel",
    "HIDDEN_07": "reveal_audience",
    "HIDDEN_08": "look_audience",
    "HIDDEN_09": "search_inspection",
    "HIDDEN_14": "target_metadata",
    "HIDDEN_17": "copy_face_down",
    "HIDDEN_18": "transcript_privacy",
    "HIDDEN_10": "scry_knowledge",
    "HIDDEN_13": "pile_metadata",
    "HIDDEN_05": "exile_permission_persists",
    "HIDDEN_15": "source_metadata",
    "HIDDEN_16": "ability_metadata",
    "HIDDEN_06": "exile_permission_invalidates",
    "HIDDEN_11": "shuffle_invalidates_order",
    "HIDDEN_12": "controlled_player_authority",
}

# The record's own obligation sentence for each kind. A record whose viewer
# obligation names something else is not the row this module knows how to
# verify, so it fails closed before any execution.
OBLIGATION_TEXT: dict[str, str] = {
    "opponent_hand": "opponent hand identities absent while count remains visible",
    "opponent_library": "library identities/order absent while count remains visible",
    "public_exile": "face-up exile identities public",
    "face_down_controller": ("face-down permanent controller sees identity while opponents do not"),
    "no_omniscient_api": "pilot code cannot access omniscient raw engine APIs",
    "reveal_audience": "reveal reaches exactly legal audience",
    "look_audience": "look reaches only specified audience",
    "search_inspection": "hidden-zone search inspection does not leak",
    "target_metadata": "target option metadata does not leak",
    "copy_face_down": "copy/face-down interactions hide original identity",
    "transcript_privacy": "transcripts omit actor-private state",
    "scry_knowledge": "scry/surveil top-N actor knowledge",
    "pile_metadata": "pile metadata does not leak",
    "exile_permission_persists": "face-down exile actor-specific permission persists",
    "source_metadata": "source metadata does not leak",
    "ability_metadata": "ability metadata does not leak",
    "exile_permission_invalidates": "face-down exile knowledge invalidates correctly",
    "shuffle_invalidates_order": "shuffle invalidates order knowledge",
    "controlled_player_authority": "controlled-player authority receives legally visible information",
    "honey_sentinel": (
        "unique forbidden sentinels scanned across prompt/context/option IDs/labels/"
        "metadata/source/state/transcript/logs"
    ),
}

# Requests a pilot could send in an attempt to read state it is not entitled
# to. Each must be refused by the engine lane with a typed error.
OMNISCIENCE_ATTEMPTS: tuple[tuple[str, dict[str, Any]], ...] = (
    ("get_midgame_projection", {}),
    ("get_midgame_projection", {"actor_id": "*"}),
    ("get_midgame_projection", {"actor_id": "ALL"}),
    ("get_midgame_projection", {"actor_id": "P9"}),
    ("get_midgame_state", {}),
    ("complete_midgame_arrival", {"actor_id": "P9"}),
    ("get_full_game_state", {}),
    ("get_omniscient_state", {}),
    ("dump_engine_state", {}),
    ("get_raw_engine_object_graph", {}),
    # The AF09 orchestration channel: refused on every launch without an
    # orchestration key, which no principal-facing launch carries.
    ("get_rules_rng_tape", {}),
)

# A scripted mode key, per row, bound to the text of the one engine-offered mode
# it names (the same convention as the mid-game rows' ``mode_bindings``). The
# key has no machine meaning in the record; the bound text must occur in exactly
# one engine mode label or the scripted step fails closed.
MODE_BINDINGS: dict[str, tuple[tuple[str, str], ...]] = {
    "HIDDEN_15": (("cloak_top", "Cloak the top card"),),
    "HIDDEN_16": (("cloak_top", "Cloak the top card"),),
}

# Observation messages whose scope the lane must declare.
SCOPED_OBSERVATIONS = (
    "get_midgame_projection",
    "get_midgame_state",
    "get_midgame_decision",
    "get_legal_actions",
    "get_midgame_events",
    "complete_midgame_arrival",
)

# Channels of the frozen knowledge contract that the lane carries in a frame.
FRAME_CHANNEL_FIELDS = (
    ("prompt", "prompt"),
    ("context", "context"),
    ("source_metadata", "source_object"),
)

# Harness control-plane messages. They carry the requested state (the harness
# is the constructor), so they are no principal's channel.
CONTROL_PLANE = {"create_midgame_game", "start_midgame_game"}


# --------------------------------------------------------------------------- #
# What the record entitles each principal to know
# --------------------------------------------------------------------------- #


def _objects(record: dict[str, Any]) -> list[dict[str, Any]]:
    return [dict(item) for item in record.get("semantic_objects") or ()]


def _labels(record: dict[str, Any]) -> list[str]:
    players = sorted(record.get("players") or (), key=lambda player: int(player["seat"]))
    return [str(player["player_id"]) for player in players]


def _viewer_state(record: dict[str, Any]) -> dict[str, Any]:
    states = list((record.get("knowledge_state") or {}).get("viewer_states") or ())
    if len(states) != 1:
        raise ValueError("the record must declare exactly one viewer state")
    return dict(states[0])


def _look_permitted(obj: dict[str, Any], viewer: str, permissions: Iterable[Any]) -> bool:
    for permission in permissions:
        if (
            isinstance(permission, dict)
            and permission.get("object") == obj.get("semantic_id")
            and permission.get("viewer") == viewer
            and permission.get("scope") == "identity"
        ):
            return True
    return False


#: Temporary permissions that entitle their viewer to an object's identity once
#: the record's scripted event has happened.
IDENTITY_PERMISSIONS = frozenset({"reveal", "look", "look_at_face_down_exile"})


def _temporarily_entitled(obj: dict[str, Any], viewer: str, temporary: Iterable[Any]) -> bool:
    for permission in temporary:
        if (
            isinstance(permission, dict)
            and permission.get("object") == obj.get("semantic_id")
            and permission.get("permission") in IDENTITY_PERMISSIONS
            and permission.get("viewer") in (viewer, "ALL_PLAYERS")
        ):
            return True
    return False


def entitled(
    obj: dict[str, Any],
    viewer: str,
    permissions: Iterable[Any] = (),
    temporary: Iterable[Any] = (),
) -> bool:
    """Whether the record entitles ``viewer`` to the object's identity.

    Hand cards are their owner's; library cards are nobody's; a face-down
    permanent is its controller's and any principal's the record grants a look;
    every other requested zone here is public. ``temporary`` holds the record's
    temporary permissions, which apply only after the record's scripted event
    (a reveal to every player, a look by one).
    """
    if _temporarily_entitled(obj, viewer, temporary):
        return True
    zone = obj.get("zone")
    if zone == "library":
        return False
    if zone == "hand":
        return obj.get("owner") == viewer
    if obj.get("face_down"):
        return obj.get("controller") == viewer or _look_permitted(obj, viewer, permissions)
    return True


def honey_bindings(record: dict[str, Any]) -> dict[str, str]:
    """Sentinel -> identity of the object the record attaches it to."""
    bindings: dict[str, str] = {}
    for obj in _objects(record):
        for note in obj.get("construction_notes") or ():
            if isinstance(note, str) and note.startswith("honey_sentinel:"):
                bindings[note.removeprefix("honey_sentinel:")] = str(obj["card_identity"])
    return bindings


#: A construction note that names a distinctive fragment of an object's own
#: rules text. Like a honey sentinel it is the harness's knowledge only: a
#: principal not entitled to the object must never receive the fragment.
ABILITY_TEXT_NOTE = "oracle_ability_text:"


def ability_text_bindings(record: dict[str, Any]) -> dict[str, str]:
    """Rules-text fragment -> semantic id of the object the record attaches it to."""
    bindings: dict[str, str] = {}
    for obj in _objects(record):
        for note in obj.get("construction_notes") or ():
            if isinstance(note, str) and note.startswith(ABILITY_TEXT_NOTE):
                bindings[note.removeprefix(ABILITY_TEXT_NOTE)] = str(obj["semantic_id"])
    return bindings


@dataclass(frozen=True)
class ForbiddenTokens:
    """Strings a principal must never receive, and the tokens that cannot decide."""

    tokens: dict[str, str]
    ambiguous: dict[str, str]


def _scripted_casts(record: dict[str, Any]) -> list[str]:
    """The objects the record's own decision script casts."""
    casts: list[str] = []
    for step in record.get("decision_script") or ():
        value = ((step or {}).get("selection") or {}).get("semantic_value")
        if isinstance(value, dict) and value.get("action") == "cast" and value.get("object"):
            casts.append(str(value["object"]))
    return casts


def known_range_objects(record: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """(viewer, object) for every requested library object inside a range the
    record's viewer state says that viewer knows."""
    state = _viewer_state(record)
    pairs: list[tuple[str, dict[str, Any]]] = []
    for known in state.get("known_library_ranges") or ():
        if not isinstance(known, dict):
            continue
        start, count = int(known.get("start", 0)), int(known.get("count", 0))
        for obj in _objects(record):
            position = obj.get("zone_position")
            if (
                obj.get("zone") == "library"
                and obj.get("owner") == known.get("player")
                and isinstance(position, int)
                and start <= position < start + count
            ):
                pairs.append((str(known.get("viewer")), obj))
    return pairs


def forbidden_tokens(
    record: dict[str, Any],
    viewer: str,
    *,
    after_event: bool = False,
    casts: Iterable[str] | None = None,
    control_active: bool = True,
) -> ForbiddenTokens:
    """The identities, semantic ids and sentinels ``viewer`` is not entitled to.

    A card identity the viewer may also legitimately see through another object
    (or through its scaffolding template) cannot decide anything and is set
    aside as ambiguous rather than scanned. ``after_event`` applies the record's
    temporary permissions, which hold only once its scripted event happened.
    ``casts`` names the scripted casts already made (every scripted cast when
    None); ``control_active`` says whether a declared control has begun. A
    scan of a capture binds both to the tape (``_token_segments``).
    """
    state = _viewer_state(record)
    permissions = state.get("face_down_look_permissions") or ()
    temporary = list(state.get("temporary_permissions") or ()) if after_event else []
    if after_event:
        # An identity the record says its viewer knows is knowledge the scripted
        # event gave it; before the event it is the viewer's like any other.
        temporary += [
            {"object": known, "permission": "look", "viewer": state.get("viewer")}
            for known in state.get("known_object_identities") or ()
        ]
        # A card the script itself casts is put onto the stack, a public zone
        # (CR 601.2a): after the event every principal may know it.
        made = _scripted_casts(record) if casts is None else set(casts)
        temporary += [
            {"object": cast, "permission": "reveal", "viewer": "ALL_PLAYERS"}
            for cast in _scripted_casts(record)
            if cast in made
        ]
        # A library range the record says a viewer knows (a scry or surveil of
        # the top N) entitles that viewer, and only that viewer, to the range's
        # cards once the event happened.
        temporary += [
            {"object": str(obj["semantic_id"]), "permission": "look", "viewer": viewer_label}
            for viewer_label, obj in known_range_objects(record)
        ]
        # A controlled-player permission is explicit contract data, not inferred
        # legality. Once the real Rules-Core effect has happened, the named
        # controller may receive the controlled player's hand identities. The
        # permission deliberately grants no library or unrelated-player data.
        for relation in state.get("temporary_permissions") or ():
            if not isinstance(relation, dict):
                continue
            controlled = relation.get("controlled_player")
            controller = relation.get("controller")
            if (
                control_active
                and relation.get("permission")
                == "only information P1 is entitled to while making P2 decisions under rules"
                and controller == viewer
                and controlled
            ):
                temporary += [
                    {
                        "object": str(obj["semantic_id"]),
                        "permission": "look",
                        "viewer": viewer,
                    }
                    for obj in _objects(record)
                    if obj.get("zone") == "hand" and obj.get("owner") == controlled
                ]
    visible: set[str] = set()
    hidden: dict[str, str] = {}
    texts = ability_text_bindings(record)
    for obj in _objects(record):
        identity = str(obj["card_identity"])
        if entitled(obj, viewer, permissions, temporary):
            visible.add(identity)
        else:
            hidden[identity] = f"identity of {obj['semantic_id']}"
            hidden[str(obj["semantic_id"])] = "semantic id of a hidden object"
            for fragment, owner in texts.items():
                if owner == obj["semantic_id"]:
                    hidden[fragment] = f"rules text of {obj['semantic_id']}"
    for deck in record.get("deck_state") or ():
        template = (deck.get("library_template") or {}).get("card_identity")
        if template:
            visible.add(str(template))
    tokens: dict[str, str] = {}
    ambiguous: dict[str, str] = {}
    for token, why in hidden.items():
        (ambiguous if token in visible else tokens)[token] = why
    for state in (record.get("knowledge_state") or {}).get("viewer_states") or ():
        for sentinel in state.get("honey_sentinels") or ():
            tokens[str(sentinel)] = "honey sentinel"
    return ForbiddenTokens(tokens, ambiguous)


def expected_hand_counts(record: dict[str, Any]) -> dict[str, int]:
    """Requested checkpoint hand sizes for every principal whose hand is declared."""
    counts: dict[str, int] = {}
    objects = _objects(record)
    for deck in record.get("deck_state") or ():
        hand = deck.get("checkpoint_hand")
        if not isinstance(hand, dict) or hand.get("completeness") != "COMPLETE":
            continue
        player = str(deck["player_id"])
        requested = sum(1 for o in objects if o.get("zone") == "hand" and o["owner"] == player)
        counts[player] = requested + int(hand["template_count"])
    return counts


def expected_library_counts(record: dict[str, Any]) -> dict[str, int]:
    """Requested checkpoint library sizes for every principal whose library is declared."""
    counts: dict[str, int] = {}
    for deck in record.get("deck_state") or ():
        library = deck.get("checkpoint_library")
        if not isinstance(library, dict) or library.get("completeness") != (
            "COMPLETE_TOP_TO_BOTTOM"
        ):
            continue
        total = 0
        for run in library.get("runs") or ():
            total += 1 if "semantic_id" in run else int(run["count"])
        counts[str(deck["player_id"])] = total
    return counts


def expected_lossless_checks(record: dict[str, Any]) -> dict[str, int]:
    """How many engine-direct lossless checks of each kind the record requires.

    The lane reports counts per kind only: a check names the player or object
    it verified, and its observation goes to requesters who may not be entitled
    to know that such a state was requested.
    """
    counts: dict[str, int] = {}

    def add(kind: str) -> None:
        counts[kind] = counts.get(kind, 0) + 1

    for deck in record.get("deck_state") or ():
        if isinstance(deck.get("checkpoint_library"), dict):
            add("library_order")
            for run in deck["checkpoint_library"].get("runs") or ():
                if "semantic_id" in run:
                    add("library_object")
        if isinstance(deck.get("checkpoint_hand"), dict):
            add("hand_composition")
    for obj in _objects(record):
        if obj.get("face_down_type"):
            add("face_down")
        # The engine's checkpoint verification also checks every requested
        # tapped state and counter set of a permanent.
        if obj.get("zone") == "battlefield":
            if obj.get("tapped"):
                add("tapped")
            if obj.get("counters"):
                add("counters")
    return counts


# --------------------------------------------------------------------------- #
# Execution on the lane
# --------------------------------------------------------------------------- #


@dataclass
class Capture:
    """Everything the lane returned for one row, verbatim."""

    arrival_verdict: str | None = None
    arrival_mismatches: list[str] = field(default_factory=list)
    checkpoint_decision: dict[str, Any] | None = None
    scoped_arrival: dict[str, Any] = field(default_factory=dict)
    projections: dict[str, dict[str, Any]] = field(default_factory=dict)
    natives: dict[str, str] = field(default_factory=dict)
    viewer_state: dict[str, Any] = field(default_factory=dict)
    events: dict[str, Any] = field(default_factory=dict)
    capabilities: dict[str, Any] = field(default_factory=dict)
    attempts: list[dict[str, Any]] = field(default_factory=list)
    tape: list[dict[str, Any]] = field(default_factory=list)
    log: str = ""
    failure: str | None = None
    # The record's scripted event: where on the tape it began, every answer
    # given, and whether every scripted step was answered and resolved.
    script_start: int | None = None
    script_trace: list[dict[str, Any]] = field(default_factory=list)
    script_complete: bool = False
    temporal_snapshots: list[dict[str, Any]] = field(default_factory=list)
    controlled_decision: dict[str, Any] | None = None
    controlled_submission: dict[str, Any] | None = None


def _payload(response: dict[str, Any]) -> dict[str, Any]:
    payload = response.get("payload")
    return payload if isinstance(payload, dict) else {}


def _error_code(response: dict[str, Any]) -> str | None:
    errors = response.get("errors")
    if isinstance(errors, list) and errors and isinstance(errors[0], dict):
        code = errors[0].get("code")
        return str(code) if code else None
    return None


def capture_row(client: ml.MidgameLaneClient, record: dict[str, Any], *, viewer: str) -> Capture:
    """Arrive at the record's checkpoint and read every channel. Never raises
    for a lane-level refusal: the capture records where it stopped."""
    probe = midgame_rows_mod.probe_module()
    capture = Capture()
    capture.capabilities = _payload(client.request("get_capabilities", None))
    try:
        arrival = probe.drive_arrival(client, record)
    except ml.MidgameLaneError as exc:
        capture.failure = f"arrival failed closed: {exc}"
        return capture
    if arrival is None:
        capture.failure = "the engine did not reach the record's checkpoint"
        return capture
    capture.arrival_verdict = arrival.construction_verdict
    capture.arrival_mismatches = list(arrival.mismatches)
    capture.checkpoint_decision = client.pending_decision(attempts=4, interval_s=0.25)
    client.request("get_legal_actions", None)
    capture.scoped_arrival = _payload(
        client.request("complete_midgame_arrival", {"actor_id": viewer})
    )
    if record.get("decision_script"):
        capture.script_start = len(client.tape)

        def snapshot_before_action(causal_step_id: str, position: int) -> None:
            projections: dict[str, dict[str, Any]] = {}
            for label in _labels(record):
                response = client.request("get_midgame_projection", {"actor_id": label})
                if not response.get("success"):
                    raise ml.MidgameLaneError(
                        f"temporal snapshot for {label} failed closed: {_error_code(response)}"
                    )
                projections[label] = _payload(response)
            events_response = client.request("get_midgame_events", {"after_offset": 0})
            if not events_response.get("success"):
                raise ml.MidgameLaneError(
                    f"temporal event snapshot failed closed: {_error_code(events_response)}"
                )
            capture.temporal_snapshots.append(
                {
                    "causal_step_id": causal_step_id,
                    "script_position": position,
                    "tape_index": len(client.tape),
                    # Backward-compatible viewer alias used by HIDDEN_11.
                    "projection": projections[viewer],
                    "projections": projections,
                    "events": _payload(events_response),
                }
            )

        try:
            capture.script_trace = run_script(
                client,
                record,
                snapshot_before_action=(
                    snapshot_before_action
                    if record.get("fixture_id") in {"HIDDEN_06", "HIDDEN_11"}
                    else None
                ),
            )
            capture.script_complete = True
            if record.get("fixture_id") == "HIDDEN_12":
                capture.controlled_decision, capture.controlled_submission = (
                    advance_to_controlled_decision(client, record)
                )
        except ml.MidgameLaneError as exc:
            capture.failure = f"the scripted event failed closed: {exc}"
            return capture
    for label in _labels(record):
        response = client.request("get_midgame_projection", {"actor_id": label})
        if not response.get("success"):
            capture.failure = f"projection for {label} failed closed: {_error_code(response)}"
            return capture
        capture.projections[label] = _payload(response)
        actor = (_payload(response).get("view") or {}).get("actor_id")
        if isinstance(actor, str):
            capture.natives[label] = actor
    if viewer not in capture.natives:
        capture.failure = "the viewer's projection named no principal"
        return capture
    capture.viewer_state = _payload(
        client.request("get_midgame_state", {"actor_id": capture.natives[viewer]})
    )
    capture.events = _payload(client.request("get_midgame_events", {"after_offset": 0}))
    for message_type, payload in OMNISCIENCE_ATTEMPTS:
        response = client.request(message_type, payload)
        capture.attempts.append(
            {
                "message_type": message_type,
                "payload": payload,
                "success": bool(response.get("success")),
                "error_code": _error_code(response),
            }
        )
    return capture


def _activation_offer(legal: dict[str, Any], native: str) -> dict[str, Any]:
    offers = [
        action
        for action in legal.get("actions") or ()
        if action.get("action_type") == "activate_ability"
        and ((action.get("metadata") or {}).get("xmage_option_metadata") or {}).get(
            "source_object_id"
        )
        == native
    ]
    if len(offers) != 1:
        raise ml.MidgameLaneError(f"the engine offered {len(offers)} activations of the source")
    offer: dict[str, Any] = offers[0]
    return offer


def _library_object_offer(
    legal: dict[str, Any], step: dict[str, Any], record: dict[str, Any]
) -> dict[str, Any] | None:
    """The offer naming a requested library object, or None for any other selector.

    The lane places libraries after arrival and reports no hidden object's
    native id, so a library object is matched by the record's own checkpoint
    position and identity, both of which the engine's offer to the searching
    player carries. Zero or several matches fail closed.
    """
    selection = step.get("selection") or {}
    if selection.get("selector_kind") != "semantic_object":
        return None
    obj = next(
        (o for o in _objects(record) if o.get("semantic_id") == selection.get("semantic_value")),
        None,
    )
    if obj is None or obj.get("zone") != "library":
        return None
    matches = [
        action
        for action in legal.get("actions") or ()
        if (meta := ((action.get("metadata") or {}).get("xmage_option_metadata") or {})).get("zone")
        == "library"
        and meta.get("zone_index") == obj.get("zone_position")
        and meta.get("name") == obj.get("card_identity")
    ]
    if len(matches) != 1:
        raise ml.MidgameLaneError(
            f"the scripted library object {obj['semantic_id']} matched {len(matches)} engine offers"
        )
    offer: dict[str, Any] = matches[0]
    return offer


def _library_objects_offers(
    legal: dict[str, Any], step: dict[str, Any], record: dict[str, Any]
) -> list[dict[str, Any]] | None:
    """The offers naming a set of requested library objects (a pile, a split
    of revealed cards), or None for any other selector.

    Each object is matched as ``_library_object_offer`` matches one: by the
    record's checkpoint position and identity in the engine's own offer. The
    set's size must be one the engine frame authorizes; any zero, repeated or
    ambiguous match fails closed.
    """
    selection = step.get("selection") or {}
    value = selection.get("semantic_value")
    if selection.get("selector_kind") != "semantic_objects" or not isinstance(value, list):
        return None
    objects = {str(o.get("semantic_id")): o for o in _objects(record)}
    requested = [objects.get(str(key)) for key in value]
    if not requested or any(obj is None or obj.get("zone") != "library" for obj in requested):
        return None
    offers: list[dict[str, Any]] = []
    for obj in requested:
        assert obj is not None  # checked above
        single = {
            "selection": {"selector_kind": "semantic_object", "semantic_value": obj["semantic_id"]}
        }
        offer = _library_object_offer(legal, single, record)
        if offer is None or any(offer is seen for seen in offers):
            raise ml.MidgameLaneError(f"the scripted library set {value!r} is ambiguous")
        offers.append(offer)
    bounds = midgame_rows_mod._engine_selection_bounds(legal)
    if bounds is None or not bounds[0] <= len(offers) <= bounds[1]:
        raise ml.MidgameLaneError(
            f"the record selects {len(offers)} library objects, the engine frame asks {bounds}"
        )
    return offers


def _pile_offer(legal: dict[str, Any], step: dict[str, Any]) -> dict[str, Any] | None:
    """The engine's offer of the pile the record names by its label, or None.

    A pile frame offers its piles by label ("Pile 1", "Pile 2"); the record's
    ``pile_label`` names one, and exactly one engine offer must carry it.
    """
    selection = step.get("selection") or {}
    if selection.get("selector_kind") != "pile_label":
        return None
    label = selection.get("semantic_value")
    if not isinstance(label, str) or not label:
        raise ml.MidgameLaneError(f"pile_label carries {label!r}")
    matches: list[dict[str, Any]] = [
        action
        for action in legal.get("actions") or ()
        if midgame_rows_mod._label_of(action).strip() == label
    ]
    if len(matches) != 1:
        raise ml.MidgameLaneError(f"the pile {label!r} matched {len(matches)} engine offers")
    return matches[0]


def face_down_permanents(projection: dict[str, Any], controller: str) -> list[str]:
    """The face-down permanents ``controller`` controls, as one principal's own
    projection shows them (object handles only, never an identity)."""
    labels = list(projection.get("seat_labels") or ())
    found: list[str] = []
    for player in (projection.get("view") or {}).get("players") or ():
        seat = player.get("seat") if isinstance(player, dict) else None
        if not isinstance(seat, int) or seat >= len(labels) or labels[seat] != controller:
            continue
        for permanent in player.get("battlefield") or ():
            if isinstance(permanent, dict) and permanent.get("face_down") is True:
                found.append(str(permanent.get("object_id")))
    return found


def _face_down_target_offer(
    client: ml.MidgameLaneClient, legal: dict[str, Any], step: dict[str, Any], principal: str
) -> dict[str, Any] | None:
    """The offer targeting the one face-down permanent the named player controls,
    or None for any other selector.

    The permanent is found in the acting principal's own projection, the only
    knowledge a pilot in that seat holds; zero or several matches fail closed.
    """
    selection = step.get("selection") or {}
    if selection.get("selector_kind") != "semantic_face_down_permanent":
        return None
    response = client.request("get_midgame_projection", {"actor_id": principal})
    if not response.get("success"):
        raise ml.MidgameLaneError("the acting principal's projection failed closed")
    handles = face_down_permanents(_payload(response), str(selection.get("semantic_value")))
    matches = [
        action
        for action in legal.get("actions") or ()
        if len(handles) == 1 and list(action.get("allowed_target_ids") or ()) == handles
    ]
    if len(matches) != 1:
        raise ml.MidgameLaneError(
            f"the scripted face-down target matched {len(matches)} engine offers"
        )
    offer: dict[str, Any] = matches[0]
    return offer


def _face_down_exile_cast_offer(
    client: ml.MidgameLaneClient,
    legal: dict[str, Any],
    step: dict[str, Any],
    record: dict[str, Any],
    principal: str,
) -> dict[str, Any] | None:
    """Match a cast of a currently face-down exiled object from actor-visible state.

    The object started in a hidden library, so no setup/native handle is used.
    The acting principal's own redacted projection must expose exactly one
    matching face-down exile object, and exactly one current engine legal action
    must name that projected handle as its source.
    """
    selection = step.get("selection") or {}
    value = selection.get("semantic_value")
    if (
        selection.get("selector_kind") != "semantic_action"
        or not isinstance(value, dict)
        or value.get("action") != "cast"
        or not value.get("object")
    ):
        return None
    object_id = str(value["object"])
    permission = next(
        (
            item
            for item in _viewer_state(record).get("temporary_permissions") or ()
            if isinstance(item, dict)
            and item.get("object") == object_id
            and item.get("viewer") == principal
            and item.get("permission") == "look_at_face_down_exile"
        ),
        None,
    )
    if permission is None:
        return None
    obj = next((item for item in _objects(record) if item.get("semantic_id") == object_id), None)
    if obj is None:
        raise ml.MidgameLaneError(f"the scripted exile object {object_id} is undeclared")
    response = client.request("get_midgame_projection", {"actor_id": principal})
    if not response.get("success"):
        raise ml.MidgameLaneError("the acting principal's exile projection failed closed")
    projection = _payload(response)
    owner = _player_entry(projection, str(obj["owner"])) or {}
    handles = [
        str(card.get("object_id"))
        for card in owner.get("exile") or ()
        if isinstance(card, dict)
        and card.get("face_down") is True
        and card.get("name") == obj.get("card_identity")
        and card.get("object_id")
    ]
    if len(handles) != 1:
        raise ml.MidgameLaneError(
            f"the scripted face-down exile cast has {len(handles)} actor-visible handles"
        )
    matches = midgame_rows_mod._source_casts(legal, handles[0])
    if len(matches) != 1:
        raise ml.MidgameLaneError(
            f"the face-down exile handle matched {len(matches)} engine legal actions"
        )
    offer: dict[str, Any] = matches[0]
    return offer


def _boolean_offer(legal: dict[str, Any], step: dict[str, Any]) -> dict[str, Any] | None:
    """The yes/no offer the step names, or None for any other selector."""
    selection = step.get("selection") or {}
    if selection.get("selector_kind") != "boolean":
        return None
    wanted = selection.get("semantic_value")
    if not isinstance(wanted, bool):
        raise ml.MidgameLaneError(f"boolean selector carries {wanted!r}")
    matches = [
        action
        for action in legal.get("actions") or ()
        if (action.get("metadata") or {}).get("option_type") == "boolean"
        and ((action.get("metadata") or {}).get("xmage_option_metadata") or {}).get("value")
        is wanted
    ]
    if len(matches) != 1:
        raise ml.MidgameLaneError(f"the scripted answer {wanted} matched {len(matches)} offers")
    offer: dict[str, Any] = matches[0]
    return offer


def _controlled_relationship(record: dict[str, Any]) -> tuple[str, str]:
    """Return (controller, controlled player) from the record's own permission."""
    relationships = [
        item
        for item in _viewer_state(record).get("temporary_permissions") or ()
        if isinstance(item, dict)
        and item.get("controller")
        and item.get("controlled_player")
        and item.get("permission")
        == "only information P1 is entitled to while making P2 decisions under rules"
    ]
    if len(relationships) != 1:
        raise ml.MidgameLaneError(
            f"controlled-player row declares {len(relationships)} control relationships"
        )
    relation = relationships[0]
    return str(relation["controller"]), str(relation["controlled_player"])


def _record_seat_index(record: dict[str, Any], label: str) -> int:
    matches = [
        int(player["seat"]) - 1
        for player in record.get("players") or ()
        if str(player.get("player_id")) == label
    ]
    if len(matches) != 1:
        raise ml.MidgameLaneError(f"record names {len(matches)} seats for {label}")
    return matches[0]


def _unique_option_of_type(decision: dict[str, Any], option_type: str) -> str:
    matches = [
        str(option.get("option_id"))
        for option in decision.get("legal_options") or ()
        if isinstance(option, dict)
        and option.get("option_type") == option_type
        and option.get("option_id")
    ]
    if len(matches) != 1:
        raise ml.MidgameLaneError(
            f"expected exactly one {option_type} option, observed {len(matches)}"
        )
    return matches[0]


def advance_to_controlled_decision(
    client: ml.MidgameLaneClient, record: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Advance only by engine-offered priority passes to the controlled turn.

    Mindslaver's effect is already established by the record's explicit script.
    This observer then accepts no discretionary class except priority. Every
    transition uses the exact pass option XMage offers. The first frame whose
    native address says controller acting-for controlled player is itself
    answered with that frame's exact pass option so actor/decision/option
    identity is exercised, not merely inspected.
    """
    probe = midgame_rows_mod.probe_module()
    controller, controlled = _controlled_relationship(record)
    controller_seat = _record_seat_index(record, controller)
    controlled_seat = _record_seat_index(record, controlled)

    for _ in range(120):
        decision = client.pending_decision(attempts=5)
        if decision is None:
            raise ml.MidgameLaneError("the engine went terminal before the controlled turn")
        legal = probe.legal_actions(client)
        principal = probe.decision_principal(decision, legal)
        acting_for = decision.get("acting_for_seat")
        if acting_for is not None:
            if (
                principal != controller
                or decision.get("seat") != controller_seat
                or acting_for != controlled_seat
            ):
                raise ml.MidgameLaneError(
                    "the engine exposed a controlled-player frame for the wrong authority"
                )
            passed = probe.option_of_type(decision, "pass_priority")
            if passed is None:
                raise ml.MidgameLaneError(
                    "the controlled-player authority frame offered no pass_priority option"
                )
            observed = json.loads(json.dumps(decision))
            client.submit_options(decision, [passed])
            return observed, {
                "decision_id": str(decision.get("decision_id")),
                "decision_offset": decision.get("decision_offset"),
                "actor_id": str(decision.get("actor_id")),
                "selected_option_id": str(passed),
                "accepted": True,
                **_binding_controls(client, record, decision, str(passed)),
            }

        if str(decision.get("decision_class")) != "priority":
            raise ml.MidgameLaneError(
                "advancing to the controlled turn encountered unsupported "
                f"{decision.get('decision_class')}"
            )
        passed = _unique_option_of_type(decision, "pass_priority")
        if not passed:
            raise ml.MidgameLaneError("the engine offered no pass while advancing turns")
        client.submit_options(decision, [passed])
    raise ml.MidgameLaneError("the controlled-player authority frame was not reached")


def _rejection(client: ml.MidgameLaneClient, response: dict[str, Any]) -> str | None:
    """Submit a raw decision response; the engine's error code, or None if it
    was accepted."""
    result = client.request("submit_midgame_decision", {"response": response})
    return None if result.get("success") else str(_error_code(result) or "REJECTED")


def _binding_controls(
    client: ml.MidgameLaneClient,
    record: dict[str, Any],
    answered: dict[str, Any],
    option_id: str,
) -> dict[str, Any]:
    """Actor and revision binding of the controlled decision, exercised live.

    The lane's decision id is derived by the engine from the game, the decision
    offset (its revision), the deciding actor and the decision class, so an id
    names one revision of one actor's decision. Two submissions the engine must
    refuse without touching the game prove it: the answered (now stale) id
    again, and the next pending decision submitted under a foreign actor. The
    next pending decision must be unchanged afterwards.
    """
    _, controlled = _controlled_relationship(record)
    stale = _rejection(
        client,
        {
            "decision_id": answered["decision_id"],
            "actor_id": answered["actor_id"],
            "selected_option_ids": [option_id],
            "ordering": [],
        },
    )
    pending = client.pending_decision(attempts=5)
    foreign_native = None
    labels = [label for label in _labels(record) if label != controlled]
    for label in labels:
        response = client.request("get_midgame_projection", {"actor_id": label})
        actor = ((_payload(response).get("view") or {}).get("actor_id")) if response else None
        if pending is not None and isinstance(actor, str) and actor != pending.get("actor_id"):
            foreign_native = actor
            break
    # The probe must be refused for its actor; it offers only an engine pass,
    # so even a wrongly accepted probe could not choose anything substantive.
    options = [
        str(option.get("option_id"))
        for option in (pending or {}).get("legal_options") or ()
        if isinstance(option, dict)
        and option.get("option_id")
        and option.get("option_type") == "pass_priority"
    ]
    foreign = (
        _rejection(
            client,
            {
                "decision_id": pending["decision_id"],
                "actor_id": foreign_native,
                "selected_option_ids": options[:1],
                "ordering": [],
            },
        )
        if pending is not None and foreign_native is not None and options
        else None
    )
    after = client.pending_decision(attempts=5)
    return {
        "stale_replay_rejected": stale,
        "foreign_actor_rejected": foreign,
        "foreign_actor_attempted": foreign_native is not None and bool(options),
        "pending_unchanged": pending is not None
        and after is not None
        and after.get("decision_id") == pending.get("decision_id"),
    }


def run_script(
    client: ml.MidgameLaneClient,
    record: dict[str, Any],
    *,
    snapshot_before_action: Callable[[str, int], None] | None = None,
) -> list[dict[str, Any]]:
    """Answer the record's decision script from the engine's own offers only.

    A scripted priority step casts or activates the named object once the
    stack is empty (a script declares events, never responses); a scripted
    target or choice step selects the named player, the named library object,
    the one face-down permanent a named player controls, or the named yes/no; a mana payment uses only the record's
    explicit payment sources; every other priority is passed. The event is
    complete when every step was answered and the checkpoint's priority player
    holds priority again with an empty stack. Anything else fails closed.
    """
    probe = midgame_rows_mod.probe_module()
    created = next(
        (
            _payload(entry["response"])
            for entry in client.tape
            if entry.get("message_type") == "create_midgame_game"
        ),
        {},
    )
    placed = {str(k): str(v) for k, v in (created.get("placed_objects") or {}).items()}
    commanders = {str(k): str(v) for k, v in (created.get("commander_objects") or {}).items()}
    script = list(record.get("decision_script") or ())
    sources = [
        placed[source]
        for cost in record.get("action_cost_state") or ()
        for source in cost.get("explicit_payment_sources") or ()
        if source in placed
    ]
    holder = str((record.get("temporal_state") or {}).get("priority_player"))
    trace: list[dict[str, Any]] = []
    position = 0
    for _ in range(80):
        decision = client.pending_decision(attempts=5)
        if decision is None:
            raise ml.MidgameLaneError("the engine went terminal during the scripted event")
        legal = probe.legal_actions(client)
        principal = probe.decision_principal(decision, legal)
        decision_class = str(decision.get("decision_class"))
        step = script[position] if position < len(script) else None
        scripted = step is not None and step.get("actor") == principal
        if decision_class == "priority":
            stack = (decision.get("pilot_state") or {}).get("stack")
            if step is None and principal == holder and stack == []:
                return trace
            # A scripted action starts its own event: it waits for the previous
            # one to resolve, so no step is ever taken as a response.
            if (
                scripted
                and step is not None
                and step.get("decision_family") == "priority"
                and stack == []
            ):
                if snapshot_before_action is not None:
                    snapshot_before_action(str(step.get("causal_step_id") or ""), position)
                value = (step.get("selection") or {}).get("semantic_value") or {}
                action: dict[str, Any] | None
                if value.get("action") == "activate":
                    native = placed.get(str(value.get("object")))
                    if native is None:
                        raise ml.MidgameLaneError("the scripted source was not placed")
                    action = _activation_offer(legal, native)
                else:
                    action = _face_down_exile_cast_offer(client, legal, step, record, principal)
                    if action is None:
                        action = midgame_rows_mod._scripted_priority_action(
                            legal, step, placed, commanders
                        )
                if action is None:
                    raise ml.MidgameLaneError("the scripted action matched no engine offer")
                index = len(client.tape)
                probe.submit_proposal(client, legal, action, f"knowledge-{len(trace)}")
                # Where the scripted action entered the tape: a cast is public
                # from here on, never earlier (_token_segments).
                trace.append(
                    {"decision_class": decision_class, "step": position, "tape_index": index}
                )
                position += 1
                continue
            passed = probe.option_of_type(decision, "pass_priority")
            if passed is None:
                raise ml.MidgameLaneError("the engine offered no pass")
            client.submit_options(decision, [passed])
            continue
        if decision_class == "mana_payment":
            offer = midgame_rows_mod._mana_offer(legal, sources)
            if offer is None:
                raise ml.MidgameLaneError("no declared mana source was offered")
            probe.submit_proposal(client, legal, offer, f"knowledge-mana-{len(trace)}")
            trace.append({"decision_class": decision_class, "step": None})
            continue
        if (
            scripted
            and step is not None
            and midgame_rows_mod.engine_decision_class(str(step.get("decision_family")))
            == decision_class
        ):
            pile = _library_objects_offers(legal, step, record)
            if pile is not None:
                probe.submit_proposal(
                    client,
                    legal,
                    pile[0],
                    f"knowledge-{len(trace)}",
                    selected_option_ids=[
                        str((offer.get("metadata") or {}).get("option_id")) for offer in pile
                    ],
                )
                trace.append({"decision_class": decision_class, "step": position})
                position += 1
                continue
            chosen = (
                _library_object_offer(legal, step, record)
                or _boolean_offer(legal, step)
                or _pile_offer(legal, step)
            )
            if chosen is None:
                chosen = _face_down_target_offer(client, legal, step, principal)
            if chosen is None:
                spec = midgame_rows_mod.RowSpec(
                    mode_bindings=MODE_BINDINGS.get(str(record.get("fixture_id")), ())
                )
                chosen = midgame_rows_mod._scripted_answer(legal, step, placed, spec).action
                if chosen is None:
                    # The record selects nothing on a frame whose own minimum
                    # is zero (a scry that keeps every card on top).
                    client.submit_options(decision, [])
                    trace.append({"decision_class": decision_class, "step": position})
                    position += 1
                    continue
            probe.submit_proposal(client, legal, chosen, f"knowledge-{len(trace)}")
            trace.append({"decision_class": decision_class, "step": position})
            position += 1
            continue
        raise ml.MidgameLaneError(f"unscripted {decision_class} for {principal}")
    raise ml.MidgameLaneError("the scripted event did not complete within its bound")


# --------------------------------------------------------------------------- #
# Channels a principal receives
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class AddressedDocument:
    """One piece of a lane response or request, and the principal it belongs to.

    ``addressee`` is a principal label, or None for a public document.
    """

    addressee: str | None
    channel: str
    document: Any


def addressed_documents(
    tape: list[dict[str, Any]], natives: dict[str, str], *, start: int = 0
) -> list[AddressedDocument]:
    """Every piece of the tape, addressed to the principal it names.

    A decision frame belongs to the actor it names, whichever protocol response
    carries it: a submission's response carries the next actor's frame for the
    harness to route, and the production full-game driver hands each frame to
    the pilot of the seat the frame names. A scoped observation belongs to its
    requester; everything else is public. The harness control plane (create and
    start, which carry the requested state itself) is nobody's channel.
    """
    labels_by_native = {native: label for label, native in natives.items()}

    def label_of(principal: Any) -> str | None:
        if not isinstance(principal, str) or not principal:
            return None
        return labels_by_native.get(principal, principal)

    out: list[AddressedDocument] = []
    for index, entry in enumerate(tape, start=start):
        if "response" not in entry:
            continue
        message_type = str(entry.get("message_type"))
        if message_type in CONTROL_PLANE:
            continue
        name = f"tape[{index}]:{message_type}"
        request = entry.get("request") or {}
        raw_payload = request.get("payload")
        payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
        response = entry.get("response") or {}
        body = _payload(response)
        if not response.get("success"):
            # A refused submission's request is still its submitter's own
            # answer; the engine's refusal stays public, so anything the refusal
            # carries is scanned for every principal.
            author: str | None = None
            if message_type in {"submit_midgame_decision", "submit_action"}:
                answer = payload.get(
                    "response" if message_type == "submit_midgame_decision" else "proposal"
                )
                author = label_of(answer.get("actor_id")) if isinstance(answer, dict) else None
            out.append(AddressedDocument(author, f"{name}.request", request))
            out.append(AddressedDocument(None, f"{name}.response", response))
            continue
        if message_type in {"get_midgame_decision", "submit_midgame_decision", "submit_action"}:
            # Both submission messages answer with the next pending frame; the
            # answer itself is the submitter's (an option answer or a proposal).
            submitter: str | None = None
            if message_type != "get_midgame_decision":
                answer = payload.get(
                    "response" if message_type == "submit_midgame_decision" else "proposal"
                )
                submitter = label_of(answer.get("actor_id")) if isinstance(answer, dict) else None
                out.append(AddressedDocument(submitter, f"{name}.request", request))
            else:
                out.append(AddressedDocument(None, f"{name}.request", request))
            decision = body.get("decision")
            private = {"decision"}
            if isinstance(decision, dict) and decision:
                actor = label_of(decision.get("actor_id"))
                out.append(AddressedDocument(actor, f"{name}.frame", decision))
                # A submission's next_actions project that same next decision,
                # so they are routed with its frame. Only when every action names
                # that frame's decision; otherwise they stay public and are
                # scanned for every principal (fail closed).
                if _projects_frame(body.get("next_actions"), decision):
                    private.add("next_actions")
                    out.append(
                        AddressedDocument(actor, f"{name}.next_actions", body["next_actions"])
                    )
            status = {key: value for key, value in response.items() if key != "payload"}
            status["payload"] = {key: value for key, value in body.items() if key not in private}
            # A submission's status echoes the submitter's own answer (the
            # executed action and its ids): it answers the submitter. A pure
            # read of the pending decision has no submitter and stays public.
            out.append(
                AddressedDocument(
                    submitter,
                    f"{name}.status",
                    status,
                )
            )
            continue
        if message_type == "get_legal_actions":
            out.append(AddressedDocument(None, f"{name}.request", request))
            out.append(AddressedDocument(label_of(body.get("actor_id")), f"{name}.frame", response))
            continue
        if message_type in {
            "get_midgame_projection",
            "get_midgame_state",
            "complete_midgame_arrival",
        }:
            requester = label_of(payload.get("actor_id"))
            out.append(AddressedDocument(requester, f"{name}.request", request))
            out.append(AddressedDocument(requester, f"{name}.response", response))
            continue
        out.append(AddressedDocument(None, f"{name}.request", request))
        out.append(AddressedDocument(None, f"{name}.response", response))
    return out


def _projects_frame(actions: Any, decision: dict[str, Any]) -> bool:
    """Whether a non-empty action list projects exactly this decision frame."""
    if not isinstance(actions, list) or not actions:
        return False
    decision_id = decision.get("decision_id")
    return bool(decision_id) and all(
        isinstance(action, dict)
        and (action.get("metadata") or {}).get("decision_id") == decision_id
        for action in actions
    )


def principal_documents(
    tape: list[dict[str, Any]], principal: str, natives: dict[str, str], *, start: int = 0
) -> list[AddressedDocument]:
    """Every document the principal receives: its own and the public ones."""
    return [
        item
        for item in addressed_documents(tape, natives, start=start)
        if item.addressee is None or item.addressee == principal
    ]


def frames_of(documents: Iterable[AddressedDocument]) -> list[dict[str, Any]]:
    """The decision frames among the documents (a legal-action answer carries one)."""
    frames: list[dict[str, Any]] = []
    for item in documents:
        if not item.channel.endswith(".frame") or not isinstance(item.document, dict):
            continue
        if "decision_id" in item.document:
            frames.append(item.document)
        else:
            nested = _payload(item.document).get("decision")
            if isinstance(nested, dict) and nested:
                frames.append(nested)
    return frames


def _walk(value: Any, path: str) -> Iterator[tuple[str, str]]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield f"{path}.{key}", str(key)
            yield from _walk(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk(item, f"{path}[{index}]")
    elif isinstance(value, str):
        yield path, value


def scan(documents: Iterable[tuple[str, Any]], tokens: Iterable[str]) -> list[dict[str, str]]:
    """Every occurrence of a token in any key or string value of the documents."""
    wanted = [token for token in tokens if token]
    hits: list[dict[str, str]] = []
    for name, document in documents:
        for path, text in _walk(document, name):
            for token in wanted:
                if token in text:
                    hits.append({"channel_path": path, "token": token})
    return hits


def channel_documents(
    documents: list[AddressedDocument], log: str
) -> tuple[list[tuple[str, Any]], dict[str, int]]:
    """The principal's documents as scan input, and how much each channel held."""
    coverage: dict[str, int] = {
        "prompt": 0,
        "context": 0,
        "option_id": 0,
        "option_label": 0,
        "option_metadata": 0,
        "source_metadata": 0,
        "ability_metadata": 0,
        "pile_metadata": 0,
        "state": 0,
        "event": 0,
        "transcript": len(documents),
        "log": len(log),
    }
    for frame in frames_of(documents):
        for channel, key in FRAME_CHANNEL_FIELDS:
            if key in frame:
                coverage[channel] += 1
        for option in frame.get("legal_options") or ():
            if not isinstance(option, dict):
                continue
            coverage["option_id"] += 1 if option.get("option_id") else 0
            coverage["option_label"] += 1 if "label" in option else 0
            metadata = option.get("metadata")
            if isinstance(metadata, dict):
                coverage["option_metadata"] += 1
                coverage["ability_metadata"] += sum(
                    1 for key in metadata if str(key).startswith("ability_")
                )
                coverage["pile_metadata"] += sum(1 for key in metadata if "pile" in str(key))
        if isinstance(frame.get("pilot_state"), dict):
            coverage["state"] += 1
    for item in documents:
        if not item.channel.endswith(".response") or not isinstance(item.document, dict):
            continue
        body = _payload(item.document)
        if not body:
            continue
        if any(
            f":{name}." in item.channel
            for name in ("get_midgame_projection", "get_midgame_state", "complete_midgame_arrival")
        ):
            coverage["state"] += 1
        if ":get_midgame_events." in item.channel:
            coverage["event"] += 1 + len(body.get("events") or ())
    scanned: list[tuple[str, Any]] = [(item.channel, item.document) for item in documents]
    scanned.append(("log", log))
    return scanned, coverage


#: Channels that must have carried content for a scan to mean anything. The log
#: may be empty (nothing was written); pile and ability metadata exist only on
#: frames that offer them, and the whole frame is scanned either way.
REQUIRED_COVERAGE = (
    "prompt",
    "context",
    "option_id",
    "option_label",
    "option_metadata",
    "source_metadata",
    "state",
    "event",
    "transcript",
)


# --------------------------------------------------------------------------- #
# Verification
# --------------------------------------------------------------------------- #


@dataclass
class Check:
    name: str
    holds: bool
    detail: str
    kind: str = "MEASURED"  # MEASURED | LEAK | ENTITLEMENT


@dataclass
class RowVerdict:
    fixture_id: str
    viewer: str
    classification: str
    checks: list[Check]
    token_evidence: dict[str, Any] = field(default_factory=dict)
    forbidden_evidence: dict[str, Any] = field(default_factory=dict)
    channel_coverage: dict[str, int] = field(default_factory=dict)
    detail: str = ""

    @property
    def verified(self) -> bool:
        return self.classification == VERIFIED

    def document(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "viewer": self.viewer,
            "classification": self.classification,
            "verified": self.verified,
            "detail": self.detail,
            "checks": [check.__dict__ for check in self.checks],
            "token_evidence": self.token_evidence,
            "forbidden_evidence": self.forbidden_evidence,
            "channel_coverage": self.channel_coverage,
        }


def _player_entry(projection: dict[str, Any], label: str) -> dict[str, Any] | None:
    seat_labels = projection.get("seat_labels")
    view = projection.get("view") or {}
    if not isinstance(seat_labels, list) or label not in seat_labels:
        return None
    seat = seat_labels.index(label)
    for player in view.get("players") or ():
        if isinstance(player, dict) and player.get("seat") == seat:
            return player
    return None


def _names(cards: Any) -> list[str]:
    return [str(card.get("name")) for card in cards or () if isinstance(card, dict)]


def _viewer_binding(capture: Capture, labels: list[str], viewer: str) -> list[Check]:
    checks: list[Check] = []
    for label in labels:
        projection = capture.projections.get(label) or {}
        view = projection.get("view") or {}
        seat_labels = projection.get("seat_labels")
        bound = (
            projection.get("actor_id") == label
            and projection.get("observation_scope") == "principal_scoped"
            and isinstance(seat_labels, list)
            and sorted(seat_labels) == sorted(labels)
            and view.get("actor_id") == capture.natives.get(label)
        )
        actors = [
            player.get("seat")
            for player in view.get("players") or ()
            if isinstance(player, dict) and player.get("is_actor") is True
        ]
        own = _player_entry(projection, label)
        bound = bound and own is not None and actors == [own.get("seat")]
        checks.append(
            Check(
                f"projection_bound_to:{label}",
                bound,
                "the projection names the requested principal, a seat-label bijection and "
                "exactly one actor seat, which is the requester's own",
            )
        )
    natives = list(capture.natives.values())
    checks.append(
        Check(
            "distinct_principals",
            len(set(natives)) == len(labels),
            f"{len(set(natives))} distinct principal ids for {len(labels)} seats",
        )
    )
    return checks


def _construction(record: dict[str, Any], capture: Capture) -> list[Check]:
    expected = expected_lossless_checks(record)
    raw = capture.scoped_arrival.get("lossless_hidden_checks")
    reported = dict(raw) if isinstance(raw, dict) else {}
    return [
        Check(
            "construction_exact",
            capture.arrival_verdict == "EXACT"
            and capture.scoped_arrival.get("construction_match") is True
            and capture.scoped_arrival.get("mismatches") == [],
            f"arrival {capture.arrival_verdict}, construction_match "
            f"{capture.scoped_arrival.get('construction_match')}, mismatches "
            f"{capture.scoped_arrival.get('mismatches')}",
        ),
        Check(
            "lossless_checks_performed",
            bool(expected) and reported == expected,
            f"required {expected}; the engine reported {reported}",
        ),
    ]


def _opponent_hand(record: dict[str, Any], capture: Capture, viewer: str) -> list[Check]:
    checks: list[Check] = []
    counts = expected_hand_counts(record)
    view = capture.projections[viewer]
    for label in _labels(record):
        if label == viewer:
            continue
        entry = _player_entry(view, label)
        if entry is None or "private_state_visible" not in entry:
            checks.append(Check(f"opponent_entry_present:{label}", False, "no measurable entry"))
            continue
        checks.append(
            Check(
                f"opponent_hand_hidden:{label}",
                "hand" not in entry and entry["private_state_visible"] is False,
                f"{viewer}'s view of {label} carries no hand array and no private state",
                "LEAK",
            )
        )
        if label in counts:
            checks.append(
                Check(
                    f"opponent_hand_count_visible:{label}",
                    entry.get("hand_count") == counts[label],
                    f"requested {counts[label]}, {viewer} sees {entry.get('hand_count')}",
                    "ENTITLEMENT",
                )
            )
    # Positive control: each requested hand object is shown to its owner, so its
    # absence from the viewer's channels is not an absence from the game.
    for obj in _objects(record):
        if obj.get("zone") != "hand" or obj["owner"] == viewer:
            continue
        own = _player_entry(capture.projections[obj["owner"]], obj["owner"]) or {}
        checks.append(
            Check(
                f"owner_sees_own_hand_object:{obj['semantic_id']}",
                obj["card_identity"] in _names(own.get("hand")),
                f"{obj['owner']}'s own projection lists the requested hand object",
                "ENTITLEMENT",
            )
        )
    return checks


def _opponent_library(record: dict[str, Any], capture: Capture, viewer: str) -> list[Check]:
    checks: list[Check] = []
    counts = expected_library_counts(record)
    library_objects = [o for o in _objects(record) if o.get("zone") == "library"]
    owners = sorted({str(o["owner"]) for o in library_objects})
    view = capture.projections[viewer]
    for owner in owners:
        entry = _player_entry(view, owner)
        if (
            entry is None
            or owner not in counts
            or "granted_library" not in entry
            or "library_top_revealed" not in entry
        ):
            checks.append(Check(f"library_entry_measurable:{owner}", False, "not measurable"))
            continue
        checks.append(
            Check(
                f"library_count_visible:{owner}",
                entry.get("library_count") == counts[owner],
                f"requested {counts[owner]}, {viewer} sees {entry.get('library_count')}",
                "ENTITLEMENT",
            )
        )
        checks.append(
            Check(
                f"library_identities_and_order_absent:{owner}",
                not entry["granted_library"] and entry["library_top_revealed"] is None,
                f"{viewer}'s view of {owner} carries no granted library and no revealed top",
                "LEAK",
            )
        )
    # No principal, the owner included, is entitled to a library card's identity.
    identities = [(str(o["card_identity"]), str(o["semantic_id"])) for o in library_objects]
    for label, projection in capture.projections.items():
        hits = scan(
            [(f"projection:{label}", projection)],
            [token for pair in identities for token in pair],
        )
        checks.append(
            Check(
                f"library_object_unseen_by:{label}",
                not hits,
                f"{len(hits)} library identity occurrences in {label}'s projection",
                "LEAK",
            )
        )
    return checks


def _public_exile(record: dict[str, Any], capture: Capture, viewer: str) -> list[Check]:
    checks: list[Check] = []
    known = set(_viewer_state(record).get("known_object_identities") or ())
    objects = [o for o in _objects(record) if o["semantic_id"] in known]
    if not objects:
        return [Check("public_exile_declared", False, "the record names no known object")]
    for obj in objects:
        if obj.get("zone") != "exile" or obj.get("face_down"):
            checks.append(
                Check(f"public_exile_declared:{obj['semantic_id']}", False, "not face-up exile")
            )
            continue
        requested = sum(
            1 for o in _objects(record) if o.get("zone") == "exile" and o["owner"] == obj["owner"]
        )
        for label, projection in capture.projections.items():
            entry = _player_entry(projection, str(obj["owner"]))
            if entry is None:
                checks.append(
                    Check(f"exile_entry_present:{obj['owner']}:{label}", False, "no entry")
                )
                continue
            checks.append(
                Check(
                    f"public_exile_visible:{obj['semantic_id']}:{label}",
                    obj["card_identity"] in _names(entry.get("exile"))
                    and entry.get("exile_count") == requested,
                    f"{label} sees {obj['owner']}'s exile {_names(entry.get('exile'))} "
                    f"(count {entry.get('exile_count')}, requested {requested})",
                    "ENTITLEMENT",
                )
            )
    return checks


def _face_down(record: dict[str, Any], capture: Capture, viewer: str) -> list[Check]:
    checks: list[Check] = []
    permissions = _viewer_state(record).get("face_down_look_permissions") or ()
    objects = [o for o in _objects(record) if o.get("face_down")]
    if not objects:
        return [Check("face_down_declared", False, "the record names no face-down object")]
    for obj in objects:
        controller = str(obj["controller"])
        for label, projection in capture.projections.items():
            entry = _player_entry(projection, controller)
            if entry is None:
                checks.append(Check(f"controller_entry_present:{label}", False, "no entry"))
                continue
            face_down = [
                permanent
                for permanent in entry.get("battlefield") or ()
                if isinstance(permanent, dict) and permanent.get("face_down") is True
            ]
            if len(face_down) != 1:
                checks.append(
                    Check(
                        f"face_down_present:{obj['semantic_id']}:{label}",
                        False,
                        f"{label} sees {len(face_down)} face-down permanents of {controller}",
                        "ENTITLEMENT",
                    )
                )
                continue
            permanent = face_down[0]
            public_name_hidden = permanent.get("name") in ("", None)
            if entitled(obj, label, permissions):
                checks.append(
                    Check(
                        f"face_down_identity_entitled:{obj['semantic_id']}:{label}",
                        permanent.get("private_identity") == obj["card_identity"]
                        and public_name_hidden,
                        f"{label} is entitled; private identity shown: "
                        f"{permanent.get('private_identity') == obj['card_identity']}",
                        "ENTITLEMENT",
                    )
                )
            else:
                checks.append(
                    Check(
                        f"face_down_identity_withheld:{obj['semantic_id']}:{label}",
                        not permanent.get("private_identity") and public_name_hidden,
                        f"{label} is not entitled; the permanent shows no identity",
                        "LEAK",
                    )
                )
    return checks


def _logged_names(projection: dict[str, Any], log: str) -> list[str]:
    view = projection.get("view") or {}
    return [
        str(card.get("name"))
        for entry in view.get(log) or ()
        if isinstance(entry, dict)
        for card in entry.get("cards") or ()
        if isinstance(card, dict)
    ]


def _event_audience(record: dict[str, Any], capture: Capture, kind: str) -> list[Check]:
    """A reveal reaches every principal; a look reaches its viewer and nobody else.

    The audience is the record's own temporary permission; what each principal
    was shown is the engine's own reveal or look log in that principal's
    projection, read after the record's scripted event.
    """
    wanted = "reveal" if kind == "reveal_audience" else "look"
    log = "revealed" if wanted == "reveal" else "looked_at"
    permissions = [
        permission
        for permission in _viewer_state(record).get("temporary_permissions") or ()
        if isinstance(permission, dict) and permission.get("permission") == wanted
    ]
    objects = {str(obj["semantic_id"]): obj for obj in _objects(record)}
    checks = [
        Check(
            "scripted_event_executed",
            capture.script_complete and bool(capture.script_trace),
            f"{len(capture.script_trace)} scripted answers, complete={capture.script_complete}",
        ),
        Check(f"{wanted}_permission_declared", bool(permissions), f"{len(permissions)} declared"),
    ]
    for permission in permissions:
        obj = objects.get(str(permission.get("object")))
        if obj is None:
            checks.append(Check(f"{wanted}_object_declared", False, str(permission)))
            continue
        identity = str(obj["card_identity"])
        audience = str(permission.get("viewer"))
        for label, projection in capture.projections.items():
            shown = identity in _logged_names(projection, log)
            if audience in (label, "ALL_PLAYERS"):
                checks.append(
                    Check(
                        f"{wanted}_reaches:{obj['semantic_id']}:{label}",
                        shown,
                        f"{label}'s {log} log names the object: {shown}",
                        "ENTITLEMENT",
                    )
                )
                continue
            checks.append(
                Check(
                    f"{wanted}_withheld_from:{obj['semantic_id']}:{label}",
                    not shown,
                    f"{label}'s {log} log names the object: {shown}",
                    "LEAK",
                )
            )
            hits, _, tokens = _scan_principal(record, capture, label)
            checks.append(
                Check(
                    f"no_forbidden_token_in_channels_of:{label}",
                    not hits,
                    f"{len(hits)} occurrences of {sorted(tokens.tokens)}",
                    "LEAK",
                )
            )
    return checks


def _event_checks(capture: Capture) -> list[Check]:
    return [
        Check(
            "scripted_event_executed",
            capture.script_complete and bool(capture.script_trace),
            f"{len(capture.script_trace)} scripted answers, complete={capture.script_complete}",
        )
    ]


def _library_options(frame: dict[str, Any]) -> list[dict[str, Any]]:
    """The frame's offers of a library card (a search or look choice)."""
    options: list[dict[str, Any]] = []
    for option in frame.get("legal_options") or ():
        meta = option.get("metadata") if isinstance(option, dict) else None
        if isinstance(meta, dict) and meta.get("zone") == "library":
            options.append(option)
    return options


def _after_event_frames(capture: Capture, principal: str) -> list[dict[str, Any]]:
    start = len(capture.tape) if capture.script_start is None else capture.script_start
    documents = [
        item
        for item in addressed_documents(capture.tape[start:], capture.natives, start=start)
        if item.addressee == principal
    ]
    return frames_of(documents)


def _search_inspection(record: dict[str, Any], capture: Capture, viewer: str) -> list[Check]:
    """The searcher alone inspects its library; nobody else sees a searched card.

    The searcher and zone are the record's own search permission. The search
    is evidenced by the searcher's own frame offering every card of that
    library; every other principal must receive no library offer and no
    identity it is not entitled to.
    """
    checks = _event_checks(capture)
    searches = [
        permission
        for permission in _viewer_state(record).get("temporary_permissions") or ()
        if isinstance(permission, dict) and permission.get("permission") == "search"
    ]
    checks.append(
        Check("search_permission_declared", len(searches) == 1, f"{len(searches)} declared")
    )
    if len(searches) != 1:
        return checks
    searcher = str(searches[0].get("viewer"))
    zone = str(searches[0].get("zone"))
    owner = zone.removesuffix(".library")
    expected = expected_library_counts(record).get(owner)
    identities = sorted(
        str(obj["card_identity"])
        for obj in _objects(record)
        if obj.get("zone") == "library" and obj.get("owner") == owner
    )
    checks.append(
        Check(
            "search_zone_is_searcher_library",
            zone == f"{searcher}.library" and expected is not None,
            f"searcher {searcher}, zone {zone}, checkpoint size {expected}",
        )
    )
    frames = _after_event_frames(capture, searcher)
    # Frames without any options measure nothing: unmeasured, never denied.
    checks.append(
        Check(
            f"searcher_frames_observed:{searcher}",
            any(frame.get("legal_options") for frame in frames),
            f"{len(frames)} frames after the event",
        )
    )
    offered = [_library_options(frame) for frame in frames]
    widest = max(offered, key=len, default=[])
    names = {str((option.get("metadata") or {}).get("name")) for option in widest}
    checks.append(
        Check(
            f"search_inspects_whole_zone:{searcher}",
            bool(widest) and len(widest) == expected and set(identities) <= names,
            f"{len(widest)} library offers of {expected}; requested identities offered: "
            f"{set(identities) <= names}",
            "ENTITLEMENT" if any(frame.get("legal_options") for frame in frames) else "MEASURED",
        )
    )
    for label in _labels(record):
        if label == searcher:
            continue
        leaked = [
            len(_library_options(frame))
            for frame in frames_of(principal_documents(capture.tape, label, capture.natives))
            if _library_options(frame)
        ]
        checks.append(
            Check(
                f"no_search_offer_to:{label}",
                not leaked,
                f"{sum(leaked)} library offers in {len(leaked)} frames",
                "LEAK",
            )
        )
        if label == viewer:
            continue  # the viewer's full scan is the row's general check
        hits, _, tokens = _scan_principal(record, capture, label)
        checks.append(
            Check(
                f"no_forbidden_token_in_channels_of:{label}",
                not hits,
                f"{len(hits)} occurrences of {sorted(tokens.tokens)}",
                "LEAK",
            )
        )
    return checks


def _scry_knowledge(record: dict[str, Any], capture: Capture, viewer: str) -> list[Check]:
    """A scry or surveil of the top N: its viewer alone sees exactly that range.

    The range is the record's own ``known_library_ranges``. The look is
    evidenced by the viewer's own frame offering exactly the range's cards from
    the library; the cards return to the library (the engine's own library to
    library moves); every other principal receives no library offer and no
    identity of the range.
    """
    checks = _event_checks(capture)
    ranges = [
        known
        for known in _viewer_state(record).get("known_library_ranges") or ()
        if isinstance(known, dict)
    ]
    checks.append(Check("known_range_declared", len(ranges) == 1, f"{len(ranges)} declared"))
    if len(ranges) != 1:
        return checks
    known = ranges[0]
    knower = str(known.get("viewer"))
    owner = str(known.get("player"))
    objects = [obj for label, obj in known_range_objects(record) if label == knower]
    identities = sorted(str(obj["card_identity"]) for obj in objects)
    checks.append(
        Check(
            "known_range_requested_exactly",
            len(objects) == int(known.get("count", -1)) and len(set(identities)) == len(identities),
            f"{len(objects)} distinct requested objects for a range of {known.get('count')}",
        )
    )
    frames = _after_event_frames(capture, knower)
    measured = any(frame.get("legal_options") for frame in frames)
    # Frames without any options measure nothing: unmeasured, never denied.
    checks.append(
        Check(f"knower_frames_observed:{knower}", measured, f"{len(frames)} frames after the event")
    )
    offered = [
        sorted(str((option.get("metadata") or {}).get("name")) for option in _library_options(f))
        for f in frames
    ]
    checks.append(
        Check(
            f"range_shown_exactly_to:{knower}",
            identities in offered,
            f"library offers shown to {knower}: {offered}",
            "ENTITLEMENT" if measured else "MEASURED",
        )
    )
    returned = [
        event
        for event in (capture.events.get("events") or ())
        if event.get("type") == "ZONE_CHANGE"
        and event.get("from") == "LIBRARY"
        and event.get("to") == "LIBRARY"
        and event.get("player_player") == owner
    ]
    checks.append(
        Check(
            "range_returned_to_library",
            len(returned) == len(objects),
            f"{len(returned)} library-to-library moves of {owner}'s cards",
        )
    )
    for label in _labels(record):
        if label == knower:
            continue
        leaked = [
            len(_library_options(frame))
            for frame in frames_of(principal_documents(capture.tape, label, capture.natives))
            if _library_options(frame)
        ]
        checks.append(
            Check(
                f"no_range_offer_to:{label}",
                not leaked,
                f"{sum(leaked)} library offers in {len(leaked)} frames",
                "LEAK",
            )
        )
        if label == viewer:
            continue
        hits, _, tokens = _scan_principal(record, capture, label)
        checks.append(
            Check(
                f"no_forbidden_token_in_channels_of:{label}",
                not hits,
                f"{len(hits)} occurrences of {sorted(tokens.tokens)}",
                "LEAK",
            )
        )
    return checks


def _shuffle_invalidates_order(
    record: dict[str, Any], capture: Capture, viewer: str
) -> list[Check]:
    """A native shuffle destroys order knowledge but not legitimate memory.

    The record declares the exact pre-shuffle range the viewer looked at. The
    engine projection after the scripted native shuffle must still preserve
    those identities for the entitled viewer, must explicitly mark the order
    invalidated, and must not serialize the former engine order. Other
    principals remain unentitled to those library identities.
    """
    checks = _event_checks(capture)
    ranges = [
        item
        for item in _viewer_state(record).get("known_library_ranges") or ()
        if isinstance(item, dict)
        and item.get("viewer") == viewer
        and item.get("before_event") == "shuffle"
        and item.get("ordered") is True
    ]
    checks.append(
        Check(
            "one_pre_shuffle_known_range_declared",
            len(ranges) == 1,
            f"{len(ranges)} ordered pre-shuffle ranges declared for {viewer}",
        )
    )
    if len(ranges) != 1:
        return checks

    known = ranges[0]
    owner = str(known.get("player"))
    start = int(known.get("start", 0))
    count = int(known.get("count", 0))
    ordered_objects = sorted(
        (
            obj
            for obj in _objects(record)
            if obj.get("zone") == "library"
            and obj.get("owner") == owner
            and isinstance(obj.get("zone_position"), int)
            and start <= int(obj["zone_position"]) < start + count
        ),
        key=lambda obj: int(obj["zone_position"]),
    )
    expected_order = [str(obj["card_identity"]) for obj in ordered_objects]
    checks.append(
        Check(
            "known_range_is_losslessly_materialized",
            len(expected_order) == count and count > 0,
            f"{len(expected_order)} requested objects cover declared count {count}",
        )
    )

    pre_shuffle = [
        snapshot
        for snapshot in capture.temporal_snapshots
        if snapshot.get("causal_step_id") == "elixir-shuffle"
    ]
    checks.append(
        Check(
            "pre_shuffle_snapshot_observed",
            len(pre_shuffle) == 1,
            f"{len(pre_shuffle)} snapshots captured immediately before the shuffle action",
        )
    )
    pre_events: list[dict[str, Any]] = []
    if len(pre_shuffle) == 1:
        pre_projection = pre_shuffle[0].get("projection") or {}
        pre_view = pre_projection.get("view") or {}
        pre_observations = [
            entry
            for entry in pre_view.get("looked_at") or ()
            if isinstance(entry, dict) and _logged_card_names(entry) == expected_order
        ]
        checks.append(
            Check(
                "pre_shuffle_ordered_snapshot_matches_engine_look",
                len(pre_observations) == 1
                and pre_observations[0].get("order_invalidated_by_shuffle") is not True,
                f"{len(pre_observations)} ordered observations exactly match {expected_order}",
                "ENTITLEMENT",
            )
        )
        pre_events = list((pre_shuffle[0].get("events") or {}).get("events") or ())

    post_events = list(capture.events.get("events") or ())
    pre_shuffle_events = [
        event
        for event in pre_events
        if event.get("type") == "LIBRARY_SHUFFLED" and event.get("player_player") == owner
    ]
    post_shuffle_events = [
        event
        for event in post_events
        if event.get("type") == "LIBRARY_SHUFFLED" and event.get("player_player") == owner
    ]
    checks.append(
        Check(
            "native_shuffle_observed_after_ordered_snapshot",
            len(pre_shuffle) == 1 and len(post_shuffle_events) > len(pre_shuffle_events),
            f"{len(pre_shuffle_events)} {owner} shuffles before snapshot; "
            f"{len(post_shuffle_events)} after scripted event",
        )
    )

    projection = capture.projections.get(viewer) or {}
    view = projection.get("view") or {}
    observations = [
        entry
        for entry in view.get("looked_at") or ()
        if isinstance(entry, dict) and sorted(_logged_card_names(entry)) == sorted(expected_order)
    ]
    checks.append(
        Check(
            "remembered_identity_set_observed",
            len(observations) == 1,
            f"{len(observations)} look observations retain exactly {sorted(expected_order)}",
            "ENTITLEMENT",
        )
    )
    if len(observations) == 1:
        observation = observations[0]
        actual_order = _logged_card_names(observation)
        checks.extend(
            [
                Check(
                    "shuffle_order_invalidated_explicitly",
                    observation.get("order_invalidated_by_shuffle") is True,
                    f"order_invalidated_by_shuffle={observation.get('order_invalidated_by_shuffle')!r}",
                    "LEAK",
                ),
                Check(
                    "pre_shuffle_order_not_retained",
                    actual_order != expected_order,
                    f"before={expected_order}; after={actual_order}",
                    "LEAK",
                ),
                Check(
                    "invalidated_memory_is_canonical_not_engine_order",
                    actual_order == sorted(expected_order),
                    f"after={actual_order}; canonical={sorted(expected_order)}",
                    "LEAK",
                ),
            ]
        )

    owner_entry = _player_entry(projection, owner) or {}
    checks.append(
        Check(
            "no_active_library_grant_survives_shuffle",
            not list(owner_entry.get("granted_library") or ()),
            f"{len(owner_entry.get('granted_library') or ())} active library grants remain",
            "LEAK",
        )
    )

    identities = set(expected_order)
    for label in _labels(record):
        if label == viewer:
            continue
        other = capture.projections.get(label) or {}
        leaked = [
            name
            for entry in ((other.get("view") or {}).get("looked_at") or ())
            if isinstance(entry, dict)
            for name in _logged_card_names(entry)
            if name in identities
        ]
        checks.append(
            Check(
                f"remembered_identity_withheld_from:{label}",
                not leaked,
                f"{label} received {leaked}",
                "LEAK",
            )
        )
        hits, _, tokens = _scan_principal(record, capture, label)
        checks.append(
            Check(
                f"no_forbidden_token_in_channels_of:{label}",
                not hits,
                f"{len(hits)} occurrences of {sorted(tokens.tokens)}",
                "LEAK",
            )
        )
    return checks


def _logged_card_names(entry: dict[str, Any]) -> list[str]:
    return [
        str(card.get("name"))
        for card in entry.get("cards") or ()
        if isinstance(card, dict) and card.get("name")
    ]


def _pile_frames(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The frames that split cards into piles or choose a pile."""
    return [
        frame
        for frame in frames
        if frame.get("decision_class") == "pile" or "pile" in str(frame.get("prompt") or "").lower()
    ]


def _pile_metadata(record: dict[str, Any], capture: Capture, viewer: str) -> list[Check]:
    """Piles are made of legally revealed cards, and no pile frame carries more.

    The revealed cards are the record's own reveal permissions (every player);
    the reveal itself is checked as a reveal audience. Every principal's pile
    frames (the split, the choice) must exist where the engine asked one and
    must carry no identity, semantic id or sentinel that principal is not
    entitled to once the event happened.
    """
    checks = _event_audience(record, capture, "reveal_audience")
    asked = 0
    for label in _labels(record):
        frames = _pile_frames(frames_of(principal_documents(capture.tape, label, capture.natives)))
        asked += len(frames)
        tokens = forbidden_tokens(record, label, after_event=True)
        hits = scan([(f"pile_frame:{label}", frame) for frame in frames], tokens.tokens)
        checks.append(
            Check(
                f"pile_frames_carry_only_entitled_identities:{label}",
                not hits,
                f"{len(frames)} pile frames, {len(hits)} forbidden occurrences",
                "LEAK",
            )
        )
    checks.append(
        Check("pile_frames_observed", asked >= 2, f"{asked} pile frames across the table")
    )
    return checks


def _target_metadata(
    record: dict[str, Any],
    capture: Capture,
    viewer: str,
    classes: tuple[str, ...] = ("target",),
) -> list[Check]:
    """A hidden permanent offered as a target carries no hidden identity.

    The hidden target is a face-down permanent the viewer does not control, as
    the viewer's own projection shows it; the record's script targets it. Each
    offer of it must name no identity the viewer is denied, and its label and
    name may carry nothing beyond the public face-down characteristics.
    """
    checks = _event_checks(capture)
    own = capture.projections.get(viewer) or {}
    hidden = {
        handle
        for label in _labels(record)
        if label != viewer
        for handle in face_down_permanents(own, label)
    }
    denied = forbidden_tokens(record, viewer, after_event=True).tokens
    offers = [
        option
        for frame in _after_event_frames(capture, viewer)
        if frame.get("decision_class") in classes
        for option in frame.get("legal_options") or ()
        if isinstance(option, dict) and option.get("option_id") in hidden
    ]
    checks.append(
        Check(
            f"hidden_target_offered:{viewer}",
            bool(hidden) and bool(offers),
            f"{len(hidden)} face-down permanents the viewer does not control; "
            f"{len(offers)} target offers of them",
        )
    )
    for option in offers:
        metadata = option.get("metadata") or {}
        named = [str(option.get("label") or ""), str(metadata.get("name") or "")]
        hits = scan([("option", option)], denied)
        checks.append(
            Check(
                f"hidden_target_option_carries_no_identity:{option.get('option_id')}",
                not hits and not any(named),
                f"label/name {named}; {len(hits)} denied tokens",
                "LEAK",
            )
        )
    return checks


def _copy_face_down(record: dict[str, Any], capture: Capture, viewer: str) -> list[Check]:
    """A copy of a hidden face-down permanent copies only what is public.

    The viewer's own choice of what to copy must offer the hidden permanent
    without its identity; the resulting copy, in the viewer's own projection,
    must be a face-up permanent with only the face-down characteristics (no
    name, 2/2, no private identity); and every principal other than the
    viewer and the hidden permanent's controller must receive no denied
    identity anywhere.
    """
    checks = _target_metadata(record, capture, viewer, ("target", "choose_object"))
    own = capture.projections.get(viewer) or {}
    labels = list(own.get("seat_labels") or ())
    copies = [
        permanent
        for player in (own.get("view") or {}).get("players") or ()
        if isinstance(player, dict)
        and isinstance(player.get("seat"), int)
        and player["seat"] < len(labels)
        and labels[player["seat"]] == viewer
        for permanent in player.get("battlefield") or ()
        if isinstance(permanent, dict)
        and permanent.get("face_down") is not True
        and not permanent.get("name")
    ]
    public_only = [
        permanent
        for permanent in copies
        if permanent.get("power") == 2
        and permanent.get("toughness") == 2
        and not permanent.get("private_identity")
    ]
    checks.append(
        Check(
            "copy_has_only_face_down_characteristics",
            len(copies) == 1 and len(public_only) == 1,
            f"{len(copies)} nameless face-up copies; {len(public_only)} with only 2/2 and no identity",
            "LEAK" if copies else "MEASURED",
        )
    )
    controllers = {
        label for label in _labels(record) if label != viewer and face_down_permanents(own, label)
    }
    for label in _labels(record):
        if label == viewer or label in controllers:
            continue
        hits, _, tokens = _scan_principal(record, capture, label)
        checks.append(
            Check(
                f"no_forbidden_token_in_channels_of:{label}",
                not hits,
                f"{len(hits)} occurrences of {sorted(tokens.tokens)}",
                "LEAK",
            )
        )
    return checks


def _transcript_privacy(record: dict[str, Any], capture: Capture, viewer: str) -> list[Check]:
    """A principal's private knowledge stays out of every shared transcript.

    The private knowledge is the record's own: the viewer's known identities,
    which its scripted look gives it, and every hand. The public documents (the
    event tape, status and refusal envelopes) and the process log may carry no
    identity any principal is denied, and no other principal may receive the
    viewer's private knowledge in any channel.
    """
    checks = _event_checks(capture)
    state = _viewer_state(record)
    objects = {str(obj["semantic_id"]): obj for obj in _objects(record)}
    known = [objects.get(str(known)) for known in state.get("known_object_identities") or ()]
    private = [
        obj
        for obj in known
        if obj is not None and (obj.get("zone") in ("hand", "library") or obj.get("face_down"))
    ]
    checks.append(
        Check(
            "private_knowledge_declared",
            bool(private) and len(private) == len(known),
            f"{len(private)} private known identities of {len(known)}",
        )
    )
    own = capture.projections.get(viewer) or {}
    for obj in private:
        shown = str(obj["card_identity"]) in _logged_names(own, "looked_at")
        checks.append(
            Check(
                f"private_knowledge_reaches:{obj['semantic_id']}:{viewer}",
                shown,
                f"{viewer}'s looked_at log names the object: {shown}",
                "ENTITLEMENT",
            )
        )
    denied: dict[str, str] = {}
    for label in _labels(record):
        for after in (False, True):
            denied.update(forbidden_tokens(record, label, after_event=after).tokens)
    public = [
        (item.channel, item.document)
        for item in addressed_documents(capture.tape, capture.natives)
        if item.addressee is None
    ] + [("log", capture.log)]
    hits = scan(public, denied)
    checks.append(
        Check(
            "public_transcript_omits_private_state",
            not hits and len(public) > 1,
            f"{len(public)} public documents; {len(hits)} occurrences of {sorted(denied)}",
            "LEAK",
        )
    )
    for label in _labels(record):
        if label == viewer:
            continue
        other_hits, _, tokens = _scan_principal(record, capture, label)
        checks.append(
            Check(
                f"no_forbidden_token_in_channels_of:{label}",
                not other_hits,
                f"{len(other_hits)} occurrences of {sorted(tokens.tokens)}",
                "LEAK",
            )
        )
    return checks


def _after_event_permissions(record: dict[str, Any]) -> list[Any]:
    """The record's temporary permissions, which hold once its event happened."""
    return list(_viewer_state(record).get("temporary_permissions") or ())


def _hidden_permanents(record: dict[str, Any], capture: Capture, viewer: str) -> dict[str, str]:
    """Face-down permanent handle -> controller, for every face-down permanent the
    viewer does not control, as the viewer's own projection shows them."""
    own = capture.projections.get(viewer) or {}
    return {
        handle: label
        for label in _labels(record)
        if label != viewer
        for handle in face_down_permanents(own, label)
    }


def _scan_others(record: dict[str, Any], capture: Capture, skip: Iterable[str]) -> list[Check]:
    """Every other principal's full channel scan, except the ones named."""
    checks: list[Check] = []
    skipped = set(skip)
    for label in _labels(record):
        if label in skipped:
            continue
        hits, _, tokens = _scan_principal(record, capture, label)
        checks.append(
            Check(
                f"no_forbidden_token_in_channels_of:{label}",
                not hits,
                f"{len(hits)} occurrences of {sorted(tokens.tokens)}",
                "LEAK",
            )
        )
    return checks


def _exile_permission_persists(
    record: dict[str, Any], capture: Capture, viewer: str
) -> list[Check]:
    """A permission to look at a face-down exiled card lasts while the card does.

    The permission is the record's own (``look_at_face_down_exile`` for the
    viewer, persisting while the card stays the same exile object). The public
    tape shows the move into exile without the card's identity and names its
    public source; that source must have left the battlefield before the
    projections were read, so the look is measured after the effect that
    granted it is gone. The viewer's own projection must then still show the
    card face down in its owner's exile, and nobody else may see it anywhere.
    """
    checks = _event_checks(capture)
    permissions = [
        permission
        for permission in _after_event_permissions(record)
        if isinstance(permission, dict)
        and permission.get("permission") == "look_at_face_down_exile"
        and permission.get("viewer") == viewer
    ]
    checks.append(
        Check(
            "persistent_exile_look_declared",
            bool(permissions)
            and all(p.get("persists_while_in_same_exile_object") is True for p in permissions),
            f"{len(permissions)} persistent look permissions for {viewer}",
        )
    )
    events = list((capture.events or {}).get("events") or ())
    moves = [
        index
        for index, event in enumerate(events)
        if event.get("type") == "ZONE_CHANGE"
        and event.get("to") == "EXILED"
        and event.get("from") in ("LIBRARY", "HAND")
        and event.get("public_identity") is False
    ]
    checks.append(
        Check(
            "face_down_exile_on_public_tape",
            len(moves) == 1,
            f"{len(moves)} unnamed moves from a hidden zone into exile",
        )
    )
    source = events[moves[0]].get("source_object") if len(moves) == 1 else None
    later = events[moves[0] + 1 :] if len(moves) == 1 else []
    departures = [
        event
        for event in later
        if event.get("type") == "ZONE_CHANGE"
        and event.get("from") == "BATTLEFIELD"
        and source is not None
        and event.get("target_object") == source
    ]
    checks.append(
        Check(
            "granting_source_left_before_measurement",
            source is not None and bool(departures),
            f"the exile's public source {source} left the battlefield {len(departures)} times "
            "after the exile",
        )
    )
    objects = {str(obj["semantic_id"]): obj for obj in _objects(record)}
    for permission in permissions:
        obj = objects.get(str(permission.get("object")))
        if obj is None:
            checks.append(Check("exile_look_object_declared", False, str(permission)))
            continue
        identity = str(obj["card_identity"])
        for label, projection in capture.projections.items():
            entry = _player_entry(projection, str(obj["owner"])) or {}
            face_down = [
                card
                for card in entry.get("exile") or ()
                if isinstance(card, dict) and card.get("face_down") is True
            ]
            shown = [card for card in face_down if card.get("name") == identity]
            if label == viewer:
                checks.append(
                    Check(
                        f"face_down_exile_shown_to_viewer:{obj['semantic_id']}",
                        len(shown) == 1,
                        f"{viewer}'s view of {obj['owner']}'s exile shows the card face down: "
                        f"{len(shown)}",
                        "ENTITLEMENT",
                    )
                )
            else:
                checks.append(
                    Check(
                        f"face_down_exile_withheld_from:{obj['semantic_id']}:{label}",
                        not face_down,
                        f"{label}'s view of {obj['owner']}'s exile lists {len(face_down)} "
                        "face-down cards",
                        "LEAK",
                    )
                )
    checks.extend(_scan_others(record, capture, skip=(viewer,)))
    return checks


def _exile_permission_invalidates(
    record: dict[str, Any], capture: Capture, viewer: str
) -> list[Check]:
    """A face-down exile look ends when the native object leaves exile.

    The pre-cast snapshot must prove that the engine actually established the
    actor-specific face-down exile view. A later native EXILED -> STACK move of
    that same card must occur after the snapshot. Final projections may remember
    a now-public identity through ordinary game history, but no principal may
    retain the old face-down exile entry or its private exile handle.
    """
    checks = _event_checks(capture)
    permissions = [
        item
        for item in _after_event_permissions(record)
        if isinstance(item, dict)
        and item.get("permission") == "look_at_face_down_exile"
        and item.get("viewer") == viewer
        and item.get("object")
    ]
    checks.append(
        Check(
            "invalidating_exile_look_declared",
            len(permissions) == 1
            and "object changes zone or becomes a new object"
            in (_viewer_state(record).get("invalidation_conditions") or ()),
            f"{len(permissions)} look permissions; invalidation="
            f"{_viewer_state(record).get('invalidation_conditions')}",
        )
    )
    if len(permissions) != 1:
        return checks

    object_id = str(permissions[0]["object"])
    obj = next((item for item in _objects(record) if item.get("semantic_id") == object_id), None)
    checks.append(Check("invalidated_object_declared", obj is not None, object_id))
    if obj is None:
        return checks
    identity = str(obj["card_identity"])
    owner = str(obj["owner"])

    snapshots = [
        snapshot
        for snapshot in capture.temporal_snapshots
        if snapshot.get("causal_step_id") == "cast-exiled-card"
    ]
    checks.append(
        Check(
            "pre_zone_change_exile_snapshot_observed",
            len(snapshots) == 1,
            f"{len(snapshots)} snapshots immediately before the exile object leaves",
        )
    )
    if len(snapshots) == 1:
        snapshot = snapshots[0]
        snapshot_projections = snapshot.get("projections") or {}
        viewer_projection = snapshot_projections.get(viewer) or snapshot.get("projection") or {}
        owner_view = _player_entry(viewer_projection, owner) or {}
        viewer_face_down = [
            card
            for card in owner_view.get("exile") or ()
            if isinstance(card, dict)
            and card.get("face_down") is True
            and card.get("name") == identity
        ]
        checks.append(
            Check(
                "permission_active_before_zone_change",
                len(viewer_face_down) == 1,
                f"{len(viewer_face_down)} matching face-down exile entries in {viewer}'s snapshot",
                "ENTITLEMENT",
            )
        )
        for label in _labels(record):
            if label == viewer:
                continue
            projection = snapshot_projections.get(label) or {}
            entry = _player_entry(projection, owner) or {}
            leaked = [
                card
                for card in entry.get("exile") or ()
                if isinstance(card, dict) and card.get("face_down") is True
            ]
            checks.append(
                Check(
                    f"permission_not_shared_before_zone_change:{label}",
                    not leaked,
                    f"{len(leaked)} face-down exile entries shown to {label}",
                    "LEAK",
                )
            )

        pre_events = list((snapshot.get("events") or {}).get("events") or ())
        grants = [
            event
            for event in pre_events
            if event.get("type") == "ZONE_CHANGE"
            and event.get("from") in {"LIBRARY", "HAND"}
            and event.get("to") == "EXILED"
            and event.get("public_identity") is False
        ]
        checks.append(
            Check(
                "native_face_down_exile_grant_precedes_snapshot",
                len(grants) == 1,
                f"{len(grants)} hidden-zone -> face-down exile moves before snapshot",
            )
        )
        pre_departures = [
            event
            for event in pre_events
            if event.get("type") == "ZONE_CHANGE"
            and event.get("from") == "EXILED"
            and event.get("to") == "STACK"
            and event.get("target_name") == identity
        ]
    else:
        pre_events = []
        pre_departures = []

    post_events = list(capture.events.get("events") or ())
    departures = [
        event
        for event in post_events
        if event.get("type") == "ZONE_CHANGE"
        and event.get("from") == "EXILED"
        and event.get("to") == "STACK"
        and event.get("target_name") == identity
    ]
    checks.append(
        Check(
            "native_exile_zone_change_observed_after_snapshot",
            len(snapshots) == 1 and len(departures) > len(pre_departures),
            f"{len(pre_departures)} matching moves before snapshot; "
            f"{len(departures)} after scripted event",
        )
    )

    stale_handles: set[str] = set()
    if len(snapshots) == 1:
        pre_projection = (snapshots[0].get("projections") or {}).get(viewer) or {}
        pre_entry = _player_entry(pre_projection, owner) or {}
        stale_handles = {
            str(card.get("object_id"))
            for card in pre_entry.get("exile") or ()
            if isinstance(card, dict)
            and card.get("face_down") is True
            and card.get("name") == identity
            and card.get("object_id")
        }

    for label, projection in capture.projections.items():
        entry = _player_entry(projection, owner) or {}
        stale = [
            card
            for card in entry.get("exile") or ()
            if isinstance(card, dict)
            and (
                card.get("face_down") is True
                or card.get("name") == identity
                or str(card.get("object_id")) in stale_handles
            )
        ]
        checks.append(
            Check(
                f"no_stale_face_down_exile_permission:{label}",
                not stale,
                f"{len(stale)} stale face-down/private exile entries remain for {label}",
                "LEAK",
            )
        )
    # Whole surface, in time: until the cast nobody but the viewer may receive
    # the face-down card's identity, semantic id or exile handle on any channel.
    # From the cast on the card is a public object; the engine keeps its native
    # id across zones, so the handle then names a public object.
    cast_at = _cast_indices(record, capture).get(object_id)
    boundary = cast_at if cast_at is not None else len(capture.tape)
    for label in _labels(record):
        if label == viewer:
            continue
        early = principal_documents(capture.tape[:boundary], label, capture.natives)
        handle_hits = scan([(item.channel, item.document) for item in early], stale_handles)
        checks.append(
            Check(
                f"face_down_handle_withheld_before_zone_change:{label}",
                bool(stale_handles) and not handle_hits,
                f"{len(handle_hits)} occurrences of the exile handle before tape {boundary}",
                "LEAK" if stale_handles else "MEASURED",
            )
        )
    checks.extend(_scan_others(record, capture, skip=(viewer,)))
    return checks


def _controlled_player_authority(
    record: dict[str, Any], capture: Capture, viewer: str
) -> list[Check]:
    """The Rules Core, not the harness, determines who makes a controlled turn decision."""
    checks = _event_checks(capture)
    try:
        controller, controlled = _controlled_relationship(record)
    except ml.MidgameLaneError as exc:
        return [*checks, Check("controlled_relationship_declared", False, str(exc))]
    checks.append(
        Check(
            "controlled_relationship_declared",
            controller == viewer,
            f"controller={controller}; controlled={controlled}; viewer={viewer}",
        )
    )
    decision = capture.controlled_decision or {}
    expected_controller_seat = _record_seat_index(record, controller)
    expected_controlled_seat = _record_seat_index(record, controlled)
    checks.append(
        Check(
            "engine_addresses_controlled_decision_to_controller",
            bool(decision)
            and decision.get("actor_id") == capture.natives.get(controller)
            and decision.get("seat") == expected_controller_seat
            and decision.get("acting_for_seat") == expected_controlled_seat,
            f"actor={decision.get('actor_id')}; seat={decision.get('seat')}; "
            f"acting_for={decision.get('acting_for_seat')}",
            "ENTITLEMENT",
        )
    )

    pilot_state = decision.get("pilot_state") or {}
    controlled_row = next(
        (
            player
            for player in pilot_state.get("players") or ()
            if isinstance(player, dict) and player.get("seat") == expected_controlled_seat
        ),
        None,
    )
    hand_expected = {
        str(obj["card_identity"])
        for obj in _objects(record)
        if obj.get("zone") == "hand" and obj.get("owner") == controlled
    }
    hand_seen = {
        str(card.get("name"))
        for card in (controlled_row or {}).get("hand") or ()
        if isinstance(card, dict) and card.get("name")
    }
    checks.append(
        Check(
            "controller_receives_controlled_players_hand",
            controlled_row is not None and hand_expected <= hand_seen,
            f"expected controlled hand identities {sorted(hand_expected)}; saw {sorted(hand_seen)}",
            "ENTITLEMENT",
        )
    )

    forbidden_in_frame: set[str] = set()
    # Controlling another player grants the information that player could see,
    # not omniscient access to that player's library or unrelated principals.
    forbidden_in_frame.update(
        str(obj["card_identity"])
        for obj in _objects(record)
        if obj.get("zone") == "library" and obj.get("owner") == controlled
    )
    forbidden_in_frame.update(
        str(obj["card_identity"])
        for obj in _objects(record)
        if obj.get("zone") == "hand" and obj.get("owner") not in {controller, controlled}
    )
    hidden_hits = scan([("controlled_decision", decision)], forbidden_in_frame)
    checks.append(
        Check(
            "controlled_decision_is_not_omniscient",
            not hidden_hits,
            f"{len(hidden_hits)} forbidden library/unrelated-hand occurrences",
            "LEAK",
        )
    )

    submission = capture.controlled_submission or {}
    offered = {
        str(option.get("option_id"))
        for option in decision.get("legal_options") or ()
        if isinstance(option, dict) and option.get("option_id")
    }
    selected = str(submission.get("selected_option_id") or "")
    checks.append(
        Check(
            "controlled_decision_submission_uses_exact_engine_identity",
            bool(decision)
            and submission.get("accepted") is True
            and submission.get("decision_id") == decision.get("decision_id")
            and submission.get("actor_id") == decision.get("actor_id")
            and selected in offered
            and len(offered) > 0,
            f"decision={submission.get('decision_id')}; actor={submission.get('actor_id')}; "
            f"selected={selected}; offered={sorted(offered)}",
        )
    )

    # Decision frames are addressed by their actor. P2/P3/P4 must not receive
    # the controller's acting-for frame through any response envelope.
    for label in _labels(record):
        if label == controller:
            continue
        received = [
            frame
            for frame in frames_of(principal_documents(capture.tape, label, capture.natives))
            if frame.get("decision_id") == decision.get("decision_id")
        ]
        checks.append(
            Check(
                f"controlled_frame_withheld_from:{label}",
                not received,
                f"{len(received)} copies of the controlled decision reached {label}",
                "LEAK",
            )
        )
        # The decision's own identity (its revision-unique decision id) reaches
        # nobody else through any channel either. Option ids are not material:
        # the engine derives them from the option, so an ordinary pass carries
        # the same id in every principal's frames.
        decision_id = str(decision.get("decision_id") or "")
        material = scan(
            [
                (item.channel, item.document)
                for item in principal_documents(capture.tape, label, capture.natives)
            ],
            [decision_id] if decision_id else [],
        )
        checks.append(
            Check(
                f"controlled_decision_identity_withheld_from:{label}",
                bool(decision_id) and not material,
                f"{len(material)} occurrences of the controlled decision id",
                "LEAK",
            )
        )
    # Actor + revision binding, exercised live: the answered id is refused when
    # replayed, a foreign actor is refused on the next decision, and neither
    # probe changes the pending decision.
    checks.append(
        Check(
            "controlled_decision_revision_and_actor_bound",
            submission.get("decision_offset") == decision.get("decision_offset")
            and isinstance(decision.get("decision_offset"), int)
            and submission.get("stale_replay_rejected") is not None
            and submission.get("foreign_actor_attempted") is True
            and submission.get("foreign_actor_rejected") is not None
            and submission.get("pending_unchanged") is True,
            f"offset={submission.get('decision_offset')}; "
            f"stale replay -> {submission.get('stale_replay_rejected')}; "
            f"foreign actor -> {submission.get('foreign_actor_rejected')}; "
            f"pending unchanged={submission.get('pending_unchanged')}",
        )
    )
    # Every principal other than the controller, on every channel, in time:
    # the controlled player keeps its own hand; nobody else ever sees it.
    checks.extend(_scan_others(record, capture, skip=(controller,)))
    return checks


def _source_metadata(record: dict[str, Any], capture: Capture, viewer: str) -> list[Check]:
    """A decision whose source is a hidden permanent names nothing hidden.

    The hidden source is a face-down permanent the viewer does not control, as
    the viewer's own projection shows it; the record's script makes it the
    source of a decision the viewer must answer (a ward trigger asking the
    viewer to pay). Each such frame's prompt, context and source metadata must
    carry no identity the viewer is denied, and the source is named by nothing
    beyond its public face-down characteristics (no name). Every principal but
    the viewer and the face-down permanent's controller is scanned in full.
    """
    checks = _event_checks(capture)
    hidden = _hidden_permanents(record, capture, viewer)
    denied = forbidden_tokens(record, viewer, after_event=True).tokens
    frames = [
        frame
        for frame in _after_event_frames(capture, viewer)
        if (frame.get("source_object") or {}).get("source_object_id") in hidden
    ]
    checks.append(
        Check(
            f"hidden_source_frame_reached:{viewer}",
            bool(hidden) and bool(frames),
            f"{len(hidden)} face-down permanents the viewer does not control; {len(frames)} "
            "frames whose source is one of them",
        )
    )
    for frame in frames:
        source = frame.get("source_object") or {}
        hits = scan(
            [
                ("prompt", frame.get("prompt")),
                ("context", frame.get("context")),
                ("source_metadata", source),
            ],
            denied,
        )
        checks.append(
            Check(
                f"hidden_source_frame_carries_no_identity:{frame.get('decision_id')}",
                not hits and not source.get("source_name"),
                f"source name {source.get('source_name')!r}; {len(hits)} denied tokens",
                "LEAK",
            )
        )
    checks.extend(_scan_others(record, capture, skip=(viewer, *hidden.values())))
    return checks


def _ability_metadata(record: dict[str, Any], capture: Capture, viewer: str) -> list[Check]:
    """An ability of a hidden permanent is described by its public face only.

    The hidden permanent is a face-down permanent the viewer does not control;
    the record's script puts one of its abilities in front of the viewer (a
    ward trigger). Every piece of ability metadata the viewer receives about it
    (a frame's source ability, an option's ability fields, the permanent's own
    ability list) must carry no identity or rules text the viewer is denied,
    including the hidden card's own rules text the record declares. Every
    principal but the viewer and the face-down permanent's controller is
    scanned in full.
    """
    checks = _event_checks(capture)
    hidden = _hidden_permanents(record, capture, viewer)
    denied = forbidden_tokens(record, viewer, after_event=True).tokens
    documents: list[tuple[str, Any]] = []
    for frame in _after_event_frames(capture, viewer):
        source = frame.get("source_object") or {}
        if source.get("source_object_id") in hidden and source.get("ability_type"):
            documents.append((f"frame:{frame.get('decision_id')}:source_ability", source))
        for option in frame.get("legal_options") or ():
            metadata = (option.get("metadata") or {}) if isinstance(option, dict) else {}
            if metadata.get("source_object_id") in hidden and any(
                str(key).startswith("ability_") for key in metadata
            ):
                documents.append((f"frame:{frame.get('decision_id')}:option_ability", option))
    reached = len(documents)
    own = capture.projections.get(viewer) or {}
    for label in set(hidden.values()):
        entry = _player_entry(own, label) or {}
        for permanent in entry.get("battlefield") or ():
            if isinstance(permanent, dict) and permanent.get("object_id") in hidden:
                documents.append((f"projection:{permanent.get('object_id')}", permanent))
    checks.append(
        Check(
            f"hidden_ability_metadata_reached:{viewer}",
            bool(hidden) and reached > 0,
            f"{len(hidden)} face-down permanents the viewer does not control; {reached} "
            "pieces of ability metadata about them",
        )
    )
    hits = scan(documents, denied)
    checks.append(
        Check(
            f"hidden_ability_metadata_carries_nothing_hidden:{viewer}",
            not hits,
            f"{len(documents)} documents; {len(hits)} denied tokens "
            f"(including {len(ability_text_bindings(record))} declared rules-text fragments)",
            "LEAK",
        )
    )
    checks.extend(_scan_others(record, capture, skip=(viewer, *hidden.values())))
    return checks


def _no_omniscient_api(capture: Capture) -> list[Check]:
    capabilities = capture.capabilities.get("capabilities") or {}
    scopes = capabilities.get("observation_scopes") or {}
    checks = [
        Check(
            "declared_no_omniscient_surface",
            capabilities.get("omniscient_state_api") is False
            and capabilities.get("raw_engine_object_graph_api") is False
            and capabilities.get("knowledge_projection_supported") is True,
            "static declaration, recorded but never sufficient on its own",
        ),
        Check(
            "every_observation_scoped",
            all(
                isinstance(scopes.get(name), str)
                and scopes[name]
                and "omniscient" not in scopes[name]
                for name in SCOPED_OBSERVATIONS
            ),
            f"declared scopes: {scopes}",
        ),
    ]
    for attempt in capture.attempts:
        name = f"{attempt['message_type']}:{json.dumps(attempt['payload'], sort_keys=True)}"
        checks.append(
            Check(
                f"omniscience_not_served:{name}",
                attempt["success"] is False,
                "the lane served the request" if attempt["success"] else "the lane refused",
                "LEAK",
            )
        )
        checks.append(
            Check(
                f"omniscience_refusal_typed:{name}",
                bool(attempt["error_code"]),
                f"refusal code {attempt['error_code']}",
            )
        )
    checks.append(
        Check(
            "omniscience_attempts_made",
            len(capture.attempts) == len(OMNISCIENCE_ATTEMPTS),
            f"{len(capture.attempts)} of {len(OMNISCIENCE_ATTEMPTS)} attempts made",
        )
    )
    # A frame is polled more than once; every occurrence must agree.
    consistent: dict[str, bool] = {}
    for decision in frames_of(addressed_documents(capture.tape, capture.natives)):
        state = decision.get("pilot_state")
        decision_id = str(decision.get("decision_id"))
        if not isinstance(state, dict) or not state.get("actor_id"):
            checks.append(Check(f"frame_state_present:{decision_id}", False, "no state"))
            continue
        holds = state.get("actor_id") == decision.get("actor_id")
        consistent[decision_id] = consistent.get(decision_id, True) and holds
    for decision_id, holds in consistent.items():
        checks.append(
            Check(
                f"frame_carries_only_its_actor:{decision_id}",
                holds,
                "every occurrence embeds the acting principal's own view",
                "LEAK",
            )
        )
    frames = len(consistent)
    checks.append(Check("frames_observed", frames > 0, f"{frames} decision frames observed"))
    return checks


def _cast_indices(record: dict[str, Any], capture: Capture) -> dict[str, int | None]:
    """Scripted cast object -> the tape index of its submission (None when the
    trace does not record one: the cast then counts from the script's start)."""
    script = list(record.get("decision_script") or ())
    at = {
        int(entry["step"]): entry.get("tape_index")
        for entry in capture.script_trace
        if isinstance(entry, dict) and isinstance(entry.get("step"), int)
    }
    indices: dict[str, int | None] = {}
    for position, step in enumerate(script):
        value = ((step or {}).get("selection") or {}).get("semantic_value")
        if isinstance(value, dict) and value.get("action") == "cast" and value.get("object"):
            index = at.get(position)
            indices[str(value["object"])] = index if isinstance(index, int) else None
    return indices


def _control_start(record: dict[str, Any], capture: Capture) -> int | None:
    """The tape index of the first frame the engine addresses to a declared
    controller acting for the controlled player, or None if there is none (or
    no control is declared)."""
    if capture.script_start is None:
        return None
    try:
        controller, controlled = _controlled_relationship(record)
        seat = _record_seat_index(record, controlled)
    except ml.MidgameLaneError:
        return None
    for index in range(capture.script_start, len(capture.tape)):
        documents = principal_documents(
            capture.tape[index : index + 1], controller, capture.natives, start=index
        )
        for frame in frames_of(item for item in documents if item.addressee == controller):
            if frame.get("acting_for_seat") == seat:
                return index
    return None


def _token_segments(
    record: dict[str, Any], capture: Capture, principal: str
) -> list[tuple[int, ForbiddenTokens]]:
    """(first tape index, tokens) for each stretch of the tape over which the
    principal's entitlement is constant.

    Before the record's scripted event nothing temporary holds. From it on the
    record's temporary permissions hold, except two whose start the engine
    itself marks on the tape: a scripted cast makes its card public only from
    its own submission on (CR 601.2a), and a declared control entitles its
    controller only from the first frame the engine addresses to it acting for
    the controlled player. A control no frame shows is unmeasured rather than
    absent: its window then starts with the event, and the row cannot verify
    (its controlled-frame checks fail).
    """
    segments = [(0, forbidden_tokens(record, principal))]
    if capture.script_start is None:
        return segments
    casts = _cast_indices(record, capture)
    control = _control_start(record, capture)
    if control is None:
        control = capture.script_start
    points = {capture.script_start}
    points.update(i for i in casts.values() if i is not None and i > capture.script_start)
    if control is not None:
        points.add(control)
    for point in sorted(points):
        made = [cast for cast, index in casts.items() if index is None or index <= point]
        segments.append(
            (
                point,
                forbidden_tokens(
                    record,
                    principal,
                    after_event=True,
                    casts=made,
                    control_active=control <= point,
                ),
            )
        )
    return segments


def _scan_principal(
    record: dict[str, Any], capture: Capture, principal: str
) -> tuple[list[dict[str, str]], dict[str, int], ForbiddenTokens]:
    """Scan everything the principal received, each document against the
    entitlement of the stretch of the tape it belongs to (``_token_segments``),
    and the process log against the entitlement at the end."""
    segments = _token_segments(record, capture, principal)
    bounds = [start for start, _ in segments[1:]] + [len(capture.tape)]
    documents: list[AddressedDocument] = []
    hits: list[dict[str, str]] = []
    for (start, tokens), end in zip(segments, bounds, strict=True):
        part = principal_documents(capture.tape[start:end], principal, capture.natives, start=start)
        documents.extend(part)
        hits += scan([(item.channel, item.document) for item in part], tokens.tokens)
    scanned, coverage = channel_documents(documents, capture.log)
    hits += scan([(name, doc) for name, doc in scanned if name == "log"], segments[-1][1].tokens)
    merged_tokens: dict[str, str] = {}
    merged_ambiguous: dict[str, str] = {}
    for _, tokens in segments:
        merged_tokens.update(tokens.tokens)
        merged_ambiguous.update(tokens.ambiguous)
    return hits, coverage, ForbiddenTokens(merged_tokens, merged_ambiguous)


def verify(record: dict[str, Any], capture: Capture, *, viewer: str = "P1") -> RowVerdict:
    """The row's knowledge verdict against the record's own requests."""
    fixture_id = str(record["fixture_id"])
    kind = ROWS.get(fixture_id)
    if kind is None:
        return RowVerdict(fixture_id, viewer, UNVERIFIED, [], detail="not a declared row")
    state = _viewer_state(record)
    if state.get("viewer") != viewer or state.get("obligation") != OBLIGATION_TEXT[kind]:
        return RowVerdict(
            fixture_id, viewer, UNVERIFIED, [], detail="the record's viewer obligation differs"
        )
    if capture.failure is not None:
        return RowVerdict(fixture_id, viewer, UNVERIFIED, [], detail=capture.failure)
    labels = _labels(record)
    if sorted(capture.projections) != sorted(labels):
        return RowVerdict(fixture_id, viewer, UNVERIFIED, [], detail="a projection is missing")

    checks = _construction(record, capture) + _viewer_binding(capture, labels, viewer)
    # A FAIL needs a measured state: the requested construction, and the
    # record's scripted event when it declares one. An event that never ran
    # leaves its obligation unmeasured, never denied.
    construction_holds = all(check.holds for check in checks) and (
        not record.get("decision_script") or capture.script_complete
    )

    # Forbidden-identity and sentinel scan over every channel the viewer receives.
    hits, coverage, tokens = _scan_principal(record, capture, viewer)
    scan_checks: list[Check] = []
    scan_checks.append(
        Check(
            f"no_forbidden_token_in_channels_of:{viewer}",
            not hits,
            f"{len(hits)} occurrences of {sorted(tokens.tokens)}",
            "LEAK",
        )
    )
    uncovered = [name for name in REQUIRED_COVERAGE if coverage.get(name, 0) <= 0]
    scan_checks.append(
        Check(
            "scan_coverage",
            not uncovered,
            f"channels without content: {uncovered}"
            if uncovered
            else "every channel carried content",
        )
    )
    # Positive controls: the scanner finds what it scans for where it may be.
    bindings = honey_bindings(record)
    sentinel_seen = all(scan([("tape", capture.tape)], [sentinel]) for sentinel in bindings)
    scan_checks.append(
        Check(
            "scanner_detects_sentinel_in_request",
            bool(bindings) and sentinel_seen,
            "each honey sentinel is found in the harness's own create request",
        )
    )
    owner_controls: list[bool] = []
    after_temporary = _after_event_permissions(record) if capture.script_start is not None else []
    for obj in _objects(record):
        if obj["card_identity"] not in bindings.values():
            continue
        identity = [str(obj["card_identity"])]
        if obj.get("zone") == "hand":
            owner_controls.append(
                bool(
                    scan(
                        [("projection", capture.projections.get(str(obj["owner"])) or {})],
                        identity,
                    )
                )
            )
            continue
        # A honey-bound object outside any hand (moved there by the record's
        # scripted event) is found where the event entitles a principal to it.
        entitled_labels = [
            label
            for label in _labels(record)
            if entitled(obj, label, state.get("face_down_look_permissions") or (), after_temporary)
        ]
        if entitled_labels:
            owner_controls.append(
                all(
                    scan([("projection", capture.projections.get(label) or {})], identity)
                    for label in entitled_labels
                )
            )
    scan_checks.append(
        Check(
            "scanner_detects_honey_identity_where_entitled",
            bool(owner_controls) and all(owner_controls),
            "the honey-bound identity is found in the projection of every principal entitled to it",
        )
    )
    texts = ability_text_bindings(record)
    if texts:
        scan_checks.append(
            Check(
                "scanner_detects_ability_text_in_request",
                all(scan([("tape", capture.tape)], [fragment]) for fragment in texts),
                "each declared rules-text fragment is found in the harness's own create request",
            )
        )
    checks.extend(scan_checks)

    focus: list[Check]
    if kind == "opponent_hand":
        focus = _opponent_hand(record, capture, viewer)
    elif kind == "opponent_library":
        focus = _opponent_library(record, capture, viewer)
    elif kind == "public_exile":
        focus = _public_exile(record, capture, viewer)
    elif kind == "face_down_controller":
        focus = _face_down(record, capture, viewer)
        # The obligation is also every non-entitled principal's: scan theirs.
        permissions = state.get("face_down_look_permissions") or ()
        for label in labels:
            for obj in _objects(record):
                if not obj.get("face_down") or entitled(obj, label, permissions):
                    continue
                other_hits, _, other_tokens = _scan_principal(record, capture, label)
                focus.append(
                    Check(
                        f"no_forbidden_token_in_channels_of:{label}",
                        not other_hits,
                        f"{len(other_hits)} occurrences of {sorted(other_tokens.tokens)}",
                        "LEAK",
                    )
                )
    elif kind == "no_omniscient_api":
        focus = _no_omniscient_api(capture)
    elif kind in ("reveal_audience", "look_audience"):
        focus = _event_audience(record, capture, kind)
    elif kind == "search_inspection":
        focus = _search_inspection(record, capture, viewer)
    elif kind == "scry_knowledge":
        focus = _scry_knowledge(record, capture, viewer)
    elif kind == "pile_metadata":
        focus = _pile_metadata(record, capture, viewer)
    elif kind == "shuffle_invalidates_order":
        focus = _shuffle_invalidates_order(record, capture, viewer)
    elif kind == "target_metadata":
        focus = _target_metadata(record, capture, viewer)
    elif kind == "copy_face_down":
        focus = _copy_face_down(record, capture, viewer)
    elif kind == "transcript_privacy":
        focus = _transcript_privacy(record, capture, viewer)
    elif kind == "exile_permission_persists":
        focus = _exile_permission_persists(record, capture, viewer)
    elif kind == "exile_permission_invalidates":
        focus = _exile_permission_invalidates(record, capture, viewer)
    elif kind == "controlled_player_authority":
        focus = _controlled_player_authority(record, capture, viewer)
    elif kind == "source_metadata":
        focus = _source_metadata(record, capture, viewer)
    elif kind == "ability_metadata":
        focus = _ability_metadata(record, capture, viewer)
    else:
        # The sentinel row's obligation is the scan itself, with its controls.
        focus = []
    checks.extend(focus)
    if kind == "honey_sentinel":
        focus = list(scan_checks)

    required = list((record.get("expected_events") or {}).get("required_events") or ())
    forbidden = list((record.get("expected_events") or {}).get("forbidden_events") or ())
    token_evidence = {token: [check.__dict__ for check in focus] for token in required}
    forbidden_evidence = {
        token: {
            "occurrences": hits,
            "tokens_scanned": sorted(tokens.tokens),
            "ambiguous_tokens_not_scanned": tokens.ambiguous,
        }
        for token in forbidden
    }

    leaks = [check for check in checks if not check.holds and check.kind == "LEAK"]
    denied = [check for check in checks if not check.holds and check.kind == "ENTITLEMENT"]
    if construction_holds and leaks:
        classification = FAIL_DEMONSTRATED_LEAK
    elif construction_holds and denied:
        classification = FAIL_ENTITLEMENT_DENIED
    elif all(check.holds for check in checks) and focus and required:
        classification = VERIFIED
    else:
        classification = UNVERIFIED
    failed = [check.name for check in checks if not check.holds]
    return RowVerdict(
        fixture_id,
        viewer,
        classification,
        checks,
        token_evidence=token_evidence,
        forbidden_evidence=forbidden_evidence,
        channel_coverage=coverage,
        detail="every check holds" if not failed else f"failed: {failed}",
    )


# --------------------------------------------------------------------------- #
# Receipts
# --------------------------------------------------------------------------- #


def positive_receipt(
    verdict: RowVerdict,
    record: dict[str, Any],
    *,
    candidate_commit: str,
    runner_digest: str,
    execution_document: dict[str, Any],
) -> dict[str, Any]:
    """The runner-bound positive fixture receipt for a verified row."""
    if not verdict.verified:
        raise ValueError(f"{verdict.fixture_id} is not verified; no positive receipt")
    document: dict[str, Any] = {
        "schema_version": POSITIVE_FIXTURE_RECEIPT_SCHEMA,
        "candidate": "xmage",
        "candidate_commit": candidate_commit,
        "runner_digest": runner_digest,
        "fixture_id": verdict.fixture_id,
        "test_identity": TEST_IDENTITY_PREFIX + verdict.fixture_id,
        "execution_mode": EXECUTION_MODE,
        "construction_verdict": "EXACT",
        "obligation_exercised": {
            "required_events": list(
                (record.get("expected_events") or {}).get("required_events") or ()
            ),
            "forbidden_events": list(
                (record.get("expected_events") or {}).get("forbidden_events") or ()
            ),
            "terminal_postconditions": list(record.get("terminal_postconditions") or ()),
            "viewer_obligation": _viewer_state(record).get("obligation"),
            "requested_state_digest": record.get("requested_state_digest"),
            "obligation_digest": record.get("obligation_digest"),
        },
        "observed_assertion": {
            "viewer": verdict.viewer,
            "token_evidence": verdict.token_evidence,
            "forbidden_evidence": verdict.forbidden_evidence,
            "channel_coverage": verdict.channel_coverage,
            "checks": [check.__dict__ for check in verdict.checks],
        },
        "assertion_kind": "POSITIVE_BEHAVIOUR",
        "assertion_class": "KNOWLEDGE_BOUNDARY_OBSERVED",
        "outcome": "PASS",
        "runtime_receipt_digest": receipt_mod.document_digest(execution_document),
    }
    document["receipt_digest"] = receipt_mod.document_digest(document)
    return document


def execute_and_persist(
    *,
    workspace: Path,
    records: dict[str, dict[str, Any]],
    candidate_commit: str,
    runner_digest: str,
    out_dir: Path,
    fixtures: tuple[str, ...] | None = None,
    viewer: str = "P1",
) -> dict[str, Any]:
    """Execute every declared row on a fresh lane process and persist receipts.

    This producer owns only its own prefixed receipts and deletes them first, so
    a row that no longer verifies cannot keep credit from an earlier run.
    """
    probe = midgame_rows_mod.probe_module()
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob(f"{RECEIPT_FILE_PREFIX}*.json"):
        stale.unlink()
    selected = tuple(ROWS) if fixtures is None else fixtures
    executions: dict[str, Any] = {}
    for fixture_id in selected:
        record = records[fixture_id]
        request = {
            "game_id": f"knowledge-{fixture_id}",
            "plan_id": f"knowledge-{fixture_id}",
            "seed": probe.SEED,
            "requested_starting_state": record,
        }
        capture = Capture()
        engine_commit: str | None = None
        try:
            with probe.open_client(workspace) as client:
                client.request("get_provider_version", None)
                client.read_dimension_manifest()
                created = client.request("create_midgame_game", request)
                if created.get("success"):
                    client.request("start_midgame_game", None)
                    capture = capture_row(client, record, viewer=viewer)
                else:
                    capture.failure = f"creation refused: {_error_code(created)}"
                engine_commit = client.engine_commit
            capture.tape = list(client.tape)
            capture.log = client.stderr_log
        except ml.MidgameLaneError as exc:
            capture.failure = f"lane failed closed: {exc}"
        verdict = verify(record, capture, viewer=viewer)
        document = verdict.document()
        document["engine_commit"] = engine_commit
        document["requested_state_digest"] = record.get("requested_state_digest")
        document["obligation_digest"] = record.get("obligation_digest")
        document["log_chars"] = len(capture.log)
        if engine_commit != candidate_commit:
            document["classification"] = UNVERIFIED
            document["verified"] = False
            document["detail"] = (
                f"engine reported {engine_commit}, not the candidate {candidate_commit}"
            )
        elif verdict.verified:
            receipt = positive_receipt(
                verdict,
                record,
                candidate_commit=candidate_commit,
                runner_digest=runner_digest,
                execution_document=document,
            )
            receipt_mod.persist(out_dir / f"{RECEIPT_FILE_PREFIX}{fixture_id}.json", receipt)
            document["receipt_digest"] = receipt["receipt_digest"]
        executions[fixture_id] = document
    return {
        "schema_version": EXECUTIONS_SCHEMA,
        "execution_mode": EXECUTION_MODE,
        "candidate": "xmage",
        "candidate_commit": candidate_commit,
        "runner_digest": runner_digest,
        "viewer": viewer,
        "rows_declared": len(executions),
        "rows_verified": sum(1 for doc in executions.values() if doc.get("verified")),
        "rows_failed": sorted(
            fixture
            for fixture, doc in executions.items()
            if doc.get("classification") in FAIL_CLASSIFICATIONS
        ),
        "rows": executions,
    }


def demonstrated_failures(
    document: dict[str, Any] | None, *, candidate_commit: str, runner_digest: str
) -> dict[str, dict[str, Any]]:
    """Rows a bound executions document shows failing, with their findings.

    Only a document bound to the assembling candidate and runner counts; any
    other document is somebody else's evidence and demonstrates nothing here.
    """
    if not isinstance(document, dict) or document.get("schema_version") != EXECUTIONS_SCHEMA:
        return {}
    if (
        document.get("candidate_commit") != candidate_commit
        or not runner_digest
        or document.get("runner_digest") != runner_digest
    ):
        return {}
    failures: dict[str, dict[str, Any]] = {}
    for fixture_id, row in (document.get("rows") or {}).items():
        if not isinstance(row, dict) or row.get("classification") not in FAIL_CLASSIFICATIONS:
            continue
        if row.get("engine_commit") != candidate_commit:
            continue
        failures[str(fixture_id)] = {
            "classification": row["classification"],
            "failed_checks": [
                check
                for check in row.get("checks") or ()
                if isinstance(check, dict) and not check.get("holds")
            ],
        }
    return failures
