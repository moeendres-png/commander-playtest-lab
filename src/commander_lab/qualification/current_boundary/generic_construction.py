"""Generic-lane construction proof (Commander-Lab #441, Owner decision (c)).

A record whose ``construction_validation`` is required is credited only when the
provider's normalized constructed state equals the requested state
(``REQUESTED_STATE_DIGEST_EQUALS_CONSTRUCTED_STATE_DIGEST``). The frozen digest
preimage is unspecified, so the authorized satisfiable standard is complete
field-level correspondence under the record's own normalization
(docs/workstream_full107_partner_execution_20260922/DIGEST_GATE_ADJUDICATION.md).

The provider emits its constructed state from the native game objects inside the
Rules process (``get_constructed_state``, schema
``commander-lab.generic-constructed-state/4``), read once the natural game start
has constructed the game and parked it at its first pregame decision, before any
decision is answered. This module compares that state with every requested-state
projection key the record carries. Anything it cannot compare fails closed:
the proof is then ``CONSTRUCTION_UNSUPPORTED``, never equality.

The read is an orchestration channel, not an observation (the AF09 precedent of
the Rules-RNG tape): the provider serves it only on a launch carrying an
orchestration key, which no principal-facing launch carries. Hidden content (a
seat's library and hand together) leaves the engine only as an HMAC under that
key; the Lab, which generated the key, computes the same digest from the
record's requested deck. Public zones leave as sizes only.

The state is read at the first mulligan decision of the game, before it is
answered (libraries shuffled, opening hands drawn). A record that requests the
earlier ``game_start`` step is equal there only through the native seeded
shuffle and opening draw its own ``native_procedure`` declares.

One requested fact cannot be read from a pregame engine state and is checked
from the run instead, stated in its own check: ``temporal_state.active_player`` /
``priority_player``, the seat that holds the game's first priority (CR 103.1: the
starting player takes the first turn).

Everything else the record requests empty is read back from the engine, never
inferred (schema ``/4``): the combat in progress, queued extra turns, waiting
triggered abilities and layered continuous effects (``rules_state``), each
seat's hidden cards it may see beyond its own hand (``knowledge``) and the
commander damage it has taken. A missing readback is unsupported.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass, field
from typing import Any

SCHEMA = "commander-lab.generic-constructed-state/4"
EQUAL = "CONSTRUCTION_EQUAL"
MISMATCH = "CONSTRUCTION_MISMATCH"
UNSUPPORTED = "CONSTRUCTION_UNSUPPORTED"

# Requested-state projection keys (commander-lab.requested-state-digest/1.0.0).
PROJECTION_KEYS = (
    "execution_entry_mode",
    "players",
    "deck_state",
    "commander_state",
    "semantic_objects",
    "temporal_state",
    "knowledge_state",
    "rules_randomness",
    "combat_state",
    "stack_state",
    "continuous_rules_effects",
    "extra_turn_creation",
    "elimination_trigger",
    "zone_move_event",
    "setup_validation",
)
# Keys this lane can only satisfy when the record requests nothing for them.
_MUST_BE_EMPTY = (
    "combat_state",
    "continuous_rules_effects",
    "extra_turn_creation",
    "elimination_trigger",
    "zone_move_event",
)
# Where the generic lane reads the constructed state: the first mulligan decision
# of the game, before it is answered. Libraries are shuffled and opening hands
# drawn; no mulligan has been taken. That is the pregame "mulligan" step.
CAPTURE_POINT = "first_mulligan_decision_before_answer"
_OBSERVED_POINT = {"phase": "pregame", "step": "mulligan", "turn_number": 0}
# A record that requests the earlier "game_start" step reaches the observed point
# only through these native steps, which its own native_procedure must declare
# between game creation and the first mulligan prompt.
_GAME_START_TO_MULLIGAN = ("NATIVE_SEEDED_INITIAL_SHUFFLE", "NATIVE_OPENING_HAND_DRAW")


@dataclass(frozen=True)
class FieldCheck:
    field: str
    verdict: str  # EQUAL | MISMATCH | UNSUPPORTED
    requested: Any = None
    observed: Any = None
    detail: str = ""

    def to_document(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "verdict": self.verdict,
            "requested": self.requested,
            "observed": self.observed,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class ConstructionProof:
    verdict: str
    checks: tuple[FieldCheck, ...] = field(default_factory=tuple)

    @property
    def established(self) -> bool:
        return self.verdict == EQUAL

    def failures(self) -> list[FieldCheck]:
        return [check for check in self.checks if check.verdict != "EQUAL"]

    def reason(self) -> str:
        if self.established:
            return "the provider's normalized constructed state equals the requested state"
        failed = self.failures()
        listed = "; ".join(
            f"{check.field} {check.verdict.lower()}: {check.detail}" for check in failed[:6]
        )
        more = f" (+{len(failed) - 6} more)" if len(failed) > 6 else ""
        return f"{self.verdict}: {listed}{more}"

    def to_document(self) -> dict[str, Any]:
        return {
            "schema": "commander-lab.generic-construction-proof/1",
            "verdict": self.verdict,
            "standard": "field-level correspondence under the record's normalization",
            "checks": [check.to_document() for check in self.checks],
        }


def _seat(value: Any) -> str | None:
    return str(value).upper() if isinstance(value, str) and value else None


def _int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


class _Checks:
    def __init__(self) -> None:
        self.items: list[FieldCheck] = []

    def compare(self, name: str, requested: Any, observed: Any, detail: str = "") -> None:
        verdict = "EQUAL" if requested == observed else "MISMATCH"
        self.items.append(FieldCheck(name, verdict, requested, observed, detail))

    def unsupported(self, name: str, detail: str, requested: Any = None) -> None:
        self.items.append(FieldCheck(name, "UNSUPPORTED", requested, None, detail))


def zone_digest(key: bytes, seat: str, zone: str, card_counts: dict[str, int]) -> str:
    """The provider's keyed zone digest, computed from requested card counts.

    HMAC-SHA-256 under the launch's orchestration key over one token per line:
    the schema, the zone label, the seat (``P1``..), then ``name<TAB>count`` per
    distinct name in Java ``String`` order (UTF-16 code units).
    """
    tokens = [SCHEMA, zone, seat]
    tokens += [
        f"{name}\t{card_counts[name]}"
        for name in sorted(card_counts, key=lambda name: name.encode("utf-16-be"))
    ]
    mac = hmac.new(key, digestmod=hashlib.sha256)
    for token in tokens:
        mac.update(token.encode("utf-8") + b"\n")
    return mac.hexdigest()


def _declared_steps_before_first_mulligan(record: dict[str, Any]) -> tuple[str, ...]:
    """The record's declared native operations between creation and the first mulligan."""
    steps: list[str] = []
    for step in record.get("native_procedure") or []:
        operation = str((step or {}).get("operation", "")) if isinstance(step, dict) else ""
        if operation == "CREATE_COMMANDER_GAME":
            steps = []
            continue
        if operation == "NATIVE_MULLIGAN_PROMPT":
            break
        steps.append(operation)
    return tuple(steps)


# The record's setup_validation clauses this lane establishes, each by what it
# does: it constructs only through the engine's own deck import and game
# creation (inside the Rules process, the engine validating structure), reads
# the engine's normalized constructed state, compares it field by field here,
# and fails closed on any difference. Any other clause or value is unsupported.
_SETUP_CLAUSES: dict[str, Any] = {
    "compare_requested_vs_constructed": True,
    "construct_inside_rules_process": True,
    "expose_normalized_constructed_state": True,
    "native_structural_validation_required": True,
    "on_mismatch": "FAIL_CLOSED",
    "requested_vs_normalized_native_constructed_state_equality_required": True,
}
# The external rules the lane never applies (it computes no legality, layers,
# state-based actions or replacement outcomes, fabricates no option and never
# corrects a setup); a clause naming any other rule is unsupported.
_FORBIDDEN_EXTERNAL_RULES = frozenset(
    {
        "legality_calculation",
        "layers",
        "state_based_actions",
        "replacement_outcomes",
        "fabricated_legal_options",
        "silent_setup_correction",
    }
)


def _check_setup_validation(checks: _Checks, setup: Any) -> None:
    if setup in (None, {}):
        return
    if not isinstance(setup, dict):
        checks.unsupported("setup_validation", "the projection is not a mapping", setup)
        return
    for key, value in sorted(setup.items()):
        name = f"setup_validation.{key}"
        if key == "forbidden_external_rules":
            if isinstance(value, list) and set(value) <= _FORBIDDEN_EXTERNAL_RULES:
                checks.items.append(
                    FieldCheck(
                        name,
                        "EQUAL",
                        value,
                        sorted(_FORBIDDEN_EXTERNAL_RULES),
                        "the lane applies none of these rules",
                    )
                )
            else:
                checks.unsupported(name, "a forbidden rule this lane cannot attest", value)
        elif (
            key in _SETUP_CLAUSES
            and type(value) is type(_SETUP_CLAUSES[key])
            and value == _SETUP_CLAUSES[key]
        ):
            checks.items.append(
                FieldCheck(name, "EQUAL", value, value, "established by how this lane constructs")
            )
        else:
            checks.unsupported(name, "a setup clause this lane does not establish", value)


# The engine-native rules state every natural game start must read back empty
# at the first pregame decision (schema /4). Each is the engine's own count.
_RULES_STATE_READBACK = {
    "combat_groups": "combat_state: no combat exists before the first turn",
    "combat_attackers": "combat_state: no creature is attacking",
    "extra_turns": "extra_turn_creation / temporal_state.extra_turn_queue: no extra turn",
    "pending_triggers": "elimination_trigger / stack_state: no triggered ability waits",
    "continuous_effects": "continuous_rules_effects: no layered continuous effect",
}
# The observation-channel policies the lane honours by construction: the
# constructed state is an orchestration read (keyed digests, never a principal
# observation), and every principal observation of the run goes through the
# provider's actor-scoped projection. Any other policy is unsupported.
_KNOWN_CHANNEL_POLICIES = frozenset(
    {
        "RSP actor-aware observation applies to prompts, context, options, source/ability "
        "metadata, events, transcripts and logs.",
        "Current candidate-neutral qualification-boundary actor-aware observation applies to "
        "prompts, context, options, source/ability/pile metadata, events, transcripts and logs.",
    }
)


def _is_count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _check_rules_state(checks: _Checks, rules_state: Any) -> None:
    """Compare every must-be-empty projection with the engine's own readback."""
    if not isinstance(rules_state, dict):
        checks.unsupported("rules_state", "the provider emitted no native rules state")
        return
    for key, meaning in _RULES_STATE_READBACK.items():
        value = rules_state.get(key)
        if not _is_count(value):
            checks.unsupported(f"rules_state.{key}", f"no native readback for {meaning}", value)
        else:
            checks.compare(f"rules_state.{key}", 0, value, meaning)


def _check_knowledge(
    checks: _Checks, knowledge: dict[str, Any], players_by_id: dict[str, dict[str, Any]]
) -> None:
    """Compare each viewer's requested knowledge with the engine's own readback."""
    policy = knowledge.get("channel_policy")
    if policy in (None, ""):
        pass
    elif policy in _KNOWN_CHANNEL_POLICIES:
        checks.items.append(
            FieldCheck(
                "knowledge_state.channel_policy",
                "EQUAL",
                policy,
                "orchestration-keyed constructed state; actor-scoped principal observation",
                "established by how this lane observes",
            )
        )
    else:
        checks.unsupported(
            "knowledge_state.channel_policy",
            "an observation policy this lane cannot attest",
            policy,
        )
    viewers = knowledge.get("viewer_states") or []
    requested: dict[str, Any] = {}
    for view in viewers:
        if not isinstance(view, dict) or not _seat(view.get("viewer")):
            checks.unsupported("knowledge_state.viewer_states", "a malformed viewer state", view)
            return
        requested[_seat(view.get("viewer")) or ""] = view
    for pid in sorted(set(requested) | set(players_by_id)):
        view = requested.get(pid, {})
        permissions = {key: value for key, value in view.items() if key != "viewer" and value}
        if permissions:
            checks.unsupported(
                f"knowledge_state.{pid}", "knowledge permissions are not constructed", permissions
            )
            continue
        seen = (players_by_id.get(pid) or {}).get("knowledge")
        visible = seen.get("visible_hidden_cards") if isinstance(seen, dict) else None
        if not _is_count(visible):
            checks.unsupported(
                f"knowledge_state.{pid}", "the provider emitted no native knowledge readback"
            )
        else:
            checks.compare(
                f"knowledge_state.{pid}",
                0,
                visible,
                "hidden cards this seat may see beyond its own hand, as the engine tracks them",
            )


def compare(
    record: dict[str, Any],
    constructed: dict[str, Any] | None,
    *,
    acknowledged_seed: int | None,
    first_priority_seat: str | None,
    capture: str | None,
    orchestration_key: bytes | None,
) -> ConstructionProof:
    """Compare the provider's constructed state with the record's requested state."""
    checks = _Checks()
    if not isinstance(constructed, dict):
        checks.unsupported("constructed_state", "the provider emitted no constructed state")
        return ConstructionProof(UNSUPPORTED, tuple(checks.items))
    if constructed.get("schema") != SCHEMA:
        checks.unsupported(
            "constructed_state.schema", f"unknown schema {constructed.get('schema')!r}"
        )
        return ConstructionProof(UNSUPPORTED, tuple(checks.items))
    if constructed.get("observation_scope") != "orchestration_keyed_digests" or not (
        isinstance(orchestration_key, bytes) and len(orchestration_key) >= 16
    ):
        checks.unsupported(
            "constructed_state.observation_scope",
            "hidden zones are compared only as digests under this run's orchestration key",
            constructed.get("observation_scope"),
        )
        return ConstructionProof(UNSUPPORTED, tuple(checks.items))
    digest_key: bytes = orchestration_key

    mode = record.get("execution_entry_mode")
    if mode != "NATURAL_GAME_START":
        checks.unsupported(
            "execution_entry_mode", "the generic lane constructs only a natural game start", mode
        )
    for key in _MUST_BE_EMPTY:
        if record.get(key):
            checks.unsupported(key, "this lane constructs none of it", record.get(key))
    _check_rules_state(checks, constructed.get("rules_state"))

    raw_players = constructed.get("players")
    players_by_id: dict[str, dict[str, Any]] = {}
    observed_roster: list[str] = []
    for player in raw_players if isinstance(raw_players, list) else []:
        seat = _seat(player.get("player_id")) if isinstance(player, dict) else None
        observed_roster.append(seat or "<malformed>")
        if seat and isinstance(player, dict):
            players_by_id.setdefault(seat, player)
    requested_players = record.get("players") or []
    # The raw roster, not a mapping of it: a duplicate or malformed row is a
    # mismatch, never silently collapsed into the requested set.
    checks.compare(
        "players.roster",
        sorted(_seat(p.get("player_id")) or "" for p in requested_players),
        sorted(observed_roster),
        "exactly one well-formed row per requested player",
    )
    for wanted in requested_players:
        pid = _seat(wanted.get("player_id")) or ""
        seen = players_by_id.get(pid)
        if seen is None:
            continue
        checks.compare(f"players.{pid}.seat", wanted.get("seat"), _int(seen.get("seat")))
        checks.compare(f"players.{pid}.life", wanted.get("life"), _int(seen.get("life")))
        checks.compare(
            f"players.{pid}.starting_life",
            wanted.get("starting_life"),
            _int(seen.get("life")),
            "at the natural game start life is the starting life",
        )
        checks.compare(f"players.{pid}.poison", wanted.get("poison"), _int(seen.get("poison")))
        checks.compare(f"players.{pid}.lost", wanted.get("lost"), seen.get("lost"))
        lost, left = seen.get("lost"), seen.get("left")
        if not isinstance(lost, bool) or not isinstance(left, bool):
            # An absent or malformed lost/left readback is not a reported
            # "still in the game" (#553 Audit 1 A1).
            checks.unsupported(
                f"players.{pid}.eliminated",
                "the provider reported no lost/left readback",
                {"lost": lost, "left": left},
            )
        else:
            checks.compare(f"players.{pid}.eliminated", wanted.get("eliminated"), lost or left)

    for deck in record.get("deck_state") or []:
        pid = _seat(deck.get("player_id")) or ""
        seen = players_by_id.get(pid)
        if seen is None:
            continue
        template = deck.get("library_template")
        if (
            not isinstance(template, dict)
            or not isinstance(template.get("card_identity"), str)
            or _int(template.get("count")) is None
            or set(deck)
            - {
                "player_id",
                "commander_ids",
                "library_template",
                "opening_hand_size",
                "shuffle_channel",
            }
        ):
            checks.unsupported(
                f"deck_state.{pid}", "only a single-identity library template is compared", deck
            )
            continue
        requested_deck = {template["card_identity"]: template["count"]}
        expected = zone_digest(digest_key, pid, "library_and_hand", requested_deck)
        observed_digest = seen.get("library_and_hand_digest")
        checks.items.append(
            FieldCheck(
                f"deck_state.{pid}.main_deck",
                "EQUAL"
                if isinstance(observed_digest, str)
                and hmac.compare_digest(expected, observed_digest)
                else "MISMATCH",
                {"card_counts": requested_deck, "hmac_sha256": expected},
                {"hmac_sha256": observed_digest},
                "library and hand together are the main deck before any card leaves them; "
                "compared as digests under this run's orchestration key",
            )
        )
        checks.compare(
            f"deck_state.{pid}.opening_hand_size",
            deck.get("opening_hand_size"),
            _int(seen.get("hand_size")),
            "read at the first mulligan decision, after the opening draw",
        )

    commander_state = record.get("commander_state") or {}
    if commander_state.get("multiple_commander_relations"):
        checks.unsupported(
            "commander_state.multiple_commander_relations",
            "partner and companion relations are not compared",
            commander_state.get("multiple_commander_relations"),
        )
    if commander_state.get("commander_damage_matrix"):
        checks.unsupported(
            "commander_state.commander_damage_matrix",
            "commander damage cannot be constructed at a natural game start",
            commander_state.get("commander_damage_matrix"),
        )
    else:
        for pid, seen in sorted(players_by_id.items()):
            taken = seen.get("commander_damage_taken")
            if not isinstance(taken, int) or isinstance(taken, bool):
                checks.unsupported(
                    f"commander_state.commander_damage_matrix.{pid}",
                    "the provider emitted no commander damage readback",
                )
            else:
                checks.compare(
                    f"commander_state.commander_damage_matrix.{pid}",
                    0,
                    taken,
                    "the engine's commander damage this seat has taken (CR 903.10a)",
                )
    requested_commanders: dict[str, list[tuple[str, str, str, int]]] = {}
    for commander in commander_state.get("commanders") or []:
        owner = _seat(commander.get("owner")) or ""
        requested_commanders.setdefault(owner, []).append(
            (
                str(commander.get("card_identity")),
                owner,
                str(commander.get("zone")),
                int(commander.get("prior_command_zone_cast_count") or 0),
            )
        )
    for pid, seen in players_by_id.items():
        if not isinstance(seen.get("commanders"), list):
            # A missing or non-list readback is not "no commanders" (#553 Audit 1 A2).
            checks.unsupported(
                f"commander_state.{pid}",
                "the provider reported no commander list",
                seen.get("commanders"),
            )
            continue
        # Each commander as the provider reports it, its native owner included:
        # a commander registered for this seat that the engine says another
        # seat owns is a mismatch, never folded into the seat that lists it.
        observed = sorted(
            (
                str(entry.get("card_identity")),
                _seat(entry.get("owner")) or "",
                str(entry.get("zone")),
                _int(entry.get("prior_command_zone_cast_count")) or 0,
            )
            for entry in seen.get("commanders") or []
            if isinstance(entry, dict)
        )
        if any(
            isinstance(entry, dict) and _int(entry.get("prior_command_zone_cast_count")) is None
            for entry in seen.get("commanders") or []
        ):
            checks.unsupported(
                f"commander_state.{pid}", "the provider reported no commander cast count"
            )
            continue
        checks.compare(
            f"commander_state.{pid}.commanders",
            sorted(requested_commanders.get(pid, [])),
            observed,
        )

    for obj in record.get("semantic_objects") or []:
        zone = obj.get("zone")
        sid = obj.get("semantic_id")
        if zone != "command" or not obj.get("commander_id"):
            checks.unsupported(
                f"semantic_objects.{sid}", "only commander objects in the command zone", obj
            )
            continue
        owner = _seat(obj.get("owner")) or ""
        seen = players_by_id.get(owner) or {}
        # The provider's own commander object of this identity in its owner's
        # command zone. Every attribute the record states is compared with the
        # value the engine emits; none is inferred from the request.
        native = [
            entry
            for entry in seen.get("commanders") or []
            if isinstance(entry, dict)
            and entry.get("card_identity") == obj.get("card_identity")
            and _seat(entry.get("owner")) == owner
            and entry.get("zone") == "command"
        ]
        requested_object = {
            "card_identity": obj.get("card_identity"),
            "owner": owner,
            "zone": zone,
            "controller": _seat(obj.get("controller")) or "",
            "tapped": bool(obj.get("tapped")),
            "face_down": bool(obj.get("face_down")),
            "counters": {k: v for k, v in (obj.get("counters") or {}).items() if v},
            "attachments": len(obj.get("attachments") or ()),
        }
        if len(native) != 1:
            checks.items.append(
                FieldCheck(
                    f"semantic_objects.{sid}",
                    "MISMATCH",
                    requested_object,
                    {"matching_command_zone_commanders": len(native)},
                    "exactly one engine commander object of this identity in its owner's "
                    "command zone",
                )
            )
            continue
        entry = native[0]
        missing = [
            key
            for key in ("controller", "tapped", "face_down", "counters", "attachments")
            if key not in entry
        ]
        if missing:
            checks.unsupported(
                f"semantic_objects.{sid}",
                f"the provider emitted no native {', '.join(missing)} for this object",
                obj,
            )
            continue
        observed_counters = entry.get("counters")
        observed_object = {
            "card_identity": entry.get("card_identity"),
            "owner": _seat(entry.get("owner")) or "",
            "zone": entry.get("zone"),
            "controller": _seat(entry.get("controller")) or "",
            "tapped": entry.get("tapped"),
            "face_down": entry.get("face_down"),
            "counters": (
                {k: v for k, v in observed_counters.items() if v}
                if isinstance(observed_counters, dict)
                else observed_counters
            ),
            "attachments": entry.get("attachments"),
        }
        checks.items.append(
            FieldCheck(
                f"semantic_objects.{sid}",
                "EQUAL" if observed_object == requested_object else "MISMATCH",
                requested_object,
                observed_object,
                "the engine's own commander object: owner, controller, tapped state, "
                "face-down status, counters and attachments as the engine emits them",
            )
        )
    for pid, seen in players_by_id.items():
        for zone in ("battlefield", "graveyard", "exile"):
            checks.compare(
                f"zones.{pid}.{zone}",
                0,
                _int(seen.get(f"{zone}_size")),
                "the requested state places no object in this zone",
            )

    temporal = record.get("temporal_state") or {}
    # The point is established from the provider's own emitted fields, never
    # assumed from the capture label: no turn has begun when the engine reports
    # no phase, no active and no priority player, and its native turn counter
    # is still before the first turn (0, or 1 for an engine that counts the
    # coming first turn). Anything else is the point the provider reports.
    emitted = {
        "turn_number": constructed.get("turn_number"),
        "phase": constructed.get("phase"),
        "active_player": constructed.get("active_player"),
        "priority_player": constructed.get("priority_player"),
    }
    no_turn_begun = (
        all(key in constructed for key in ("phase", "active_player", "priority_player"))
        and emitted["phase"] is None
        and emitted["active_player"] is None
        and emitted["priority_player"] is None
        and _int(emitted["turn_number"]) in (0, 1)
    )
    if capture != CAPTURE_POINT:
        observed_point: dict[str, Any] = {"capture": capture}
    elif no_turn_begun:
        observed_point = _OBSERVED_POINT
    else:
        observed_point = {"emitted": emitted}
    for key in ("phase", "turn_number"):
        checks.compare(
            f"temporal_state.{key}",
            temporal.get(key),
            observed_point.get(key),
            f"the state was read at {capture!r}; the provider emitted {emitted}",
        )
    requested_step = temporal.get("step")
    observed_step = observed_point.get("step")
    if requested_step == "game_start" and observed_step == "mulligan":
        declared = _declared_steps_before_first_mulligan(record)
        checks.items.append(
            FieldCheck(
                "temporal_state.step",
                "EQUAL" if declared == _GAME_START_TO_MULLIGAN else "MISMATCH",
                requested_step,
                {"read_at": observed_step, "declared_native_steps": declared},
                "game_start advances to the mulligan step only through the record's own "
                "declared native seeded shuffle and opening draw",
            )
        )
    else:
        checks.compare(
            "temporal_state.step",
            requested_step,
            observed_step,
            f"the state was read at {capture!r}",
        )
    if temporal.get("extra_turn_queue"):
        checks.unsupported("temporal_state.extra_turn_queue", "no extra turn exists at game start")
    for key in ("active_player", "priority_player"):
        checks.compare(
            f"temporal_state.{key}",
            _seat(temporal.get(key)),
            _seat(first_priority_seat),
            "the starting player holds the game's first priority (CR 103.1)",
        )

    _check_knowledge(checks, record.get("knowledge_state") or {}, players_by_id)

    _check_setup_validation(checks, record.get("setup_validation"))

    randomness = record.get("rules_randomness") or {}
    checks.compare(
        "rules_randomness.rules_seed",
        randomness.get("rules_seed"),
        acknowledged_seed,
        "the seed the engine acknowledged on game creation",
    )
    # Every requested Rules-RNG channel (and every deck's own shuffle channel)
    # must have been used: the engine reports, per seat, the Rules-RNG shuffles
    # of that library so far. Equal decks and hands look the same shuffled or
    # not, so the seed alone never establishes the shuffle (Codex P1, #530).
    channels = list(randomness.get("channels") or [])
    for deck in record.get("deck_state") or []:
        channel = deck.get("shuffle_channel") if isinstance(deck, dict) else None
        if channel and channel not in channels:
            channels.append(channel)
    for channel in channels:
        name = f"rules_randomness.channel.{channel}"
        shuffled = re.fullmatch(r"library_shuffle:(P[1-9])", str(channel))
        if shuffled is None:
            checks.unsupported(name, "only library-shuffle channels are constructed here", channel)
            continue
        seen = players_by_id.get(shuffled.group(1)) or {}
        count = _int(seen.get("library_shuffles"))
        if count is None:
            checks.unsupported(name, "the provider reported no Rules-RNG shuffle of this library")
            continue
        checks.items.append(
            FieldCheck(
                name,
                "EQUAL" if count >= 1 else "MISMATCH",
                "at least one Rules-RNG shuffle",
                {"library_shuffles": count},
                "the engine's own taped shuffles of this seat's library before the capture",
            )
        )
    if randomness.get("predetermined_semantic_draws"):
        checks.unsupported(
            "rules_randomness.predetermined_semantic_draws",
            "predetermined draws are not constructed",
        )

    stack_size = _int(constructed.get("stack_size"))
    checks.compare(
        "stack_state",
        list(record.get("stack_state") or []),
        [] if stack_size == 0 else {"stack_size": constructed.get("stack_size")},
    )

    verdicts = {check.verdict for check in checks.items}
    if "UNSUPPORTED" in verdicts:
        verdict = UNSUPPORTED
    elif "MISMATCH" in verdicts:
        verdict = MISMATCH
    else:
        verdict = EQUAL
    return ConstructionProof(verdict, tuple(checks.items))
