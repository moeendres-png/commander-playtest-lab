"""Generic-lane construction proof (Commander-Lab #441, Owner decision (c)).

A record whose ``construction_validation`` is required is credited only when the
provider's normalized constructed state equals the requested state
(``REQUESTED_STATE_DIGEST_EQUALS_CONSTRUCTED_STATE_DIGEST``). The frozen digest
preimage is unspecified, so the authorized satisfiable standard is complete
field-level correspondence under the record's own normalization
(docs/workstream_full107_partner_execution_20260922/DIGEST_GATE_ADJUDICATION.md).

The provider emits its constructed state from the native game objects inside the
Rules process (``get_constructed_state``, schema
``commander-lab.generic-constructed-state/1``), read once the natural game start
has constructed the game and parked it at its first pregame decision, before any
decision is answered. This module compares that state with every requested-state
projection key the record carries. Anything it cannot compare fails closed:
the proof is then ``CONSTRUCTION_UNSUPPORTED``, never equality.

The state is read at the first mulligan decision of the game, before it is
answered (libraries shuffled, opening hands drawn). A record that requests the
earlier ``game_start`` step is equal there only through the native seeded
shuffle and opening draw its own ``native_procedure`` declares.

Two requested facts cannot be read from a pregame engine state and are checked
from the run instead, each stated in its own check:

* ``temporal_state.active_player`` / ``priority_player``: the seat that holds the
  game's first priority (CR 103.1: the starting player takes the first turn);
* an empty ``knowledge_state`` and an empty ``commander_damage_matrix``: at a
  natural game start no spell or ability has resolved, so no knowledge
  permission or commander damage can exist; a non-empty request is unsupported.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

SCHEMA = "commander-lab.generic-constructed-state/1"
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


def _counts(value: Any) -> Counter[str] | None:
    if not isinstance(value, dict):
        return None
    out: Counter[str] = Counter()
    for name, count in value.items():
        number = _int(count)
        if not isinstance(name, str) or number is None or number < 0:
            return None
        out[name] += number
    return out


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


def compare(
    record: dict[str, Any],
    constructed: dict[str, Any] | None,
    *,
    acknowledged_seed: int | None,
    first_priority_seat: str | None,
    capture: str | None,
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

    mode = record.get("execution_entry_mode")
    if mode != "NATURAL_GAME_START":
        checks.unsupported(
            "execution_entry_mode", "the generic lane constructs only a natural game start", mode
        )
    for key in _MUST_BE_EMPTY:
        if record.get(key):
            checks.unsupported(key, "this lane constructs none of it", record.get(key))

    players_by_id: dict[str, dict[str, Any]] = {}
    for player in constructed.get("players") or []:
        if isinstance(player, dict) and _seat(player.get("player_id")):
            players_by_id[_seat(player.get("player_id")) or ""] = player
    requested_players = record.get("players") or []
    checks.compare(
        "players.roster",
        sorted(_seat(p.get("player_id")) or "" for p in requested_players),
        sorted(players_by_id),
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
        checks.compare(
            f"players.{pid}.eliminated",
            wanted.get("eliminated"),
            bool(seen.get("lost")) or bool(seen.get("left")),
        )

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
        library = _counts(seen.get("library_card_counts"))
        hand = _counts(seen.get("hand_card_counts"))
        if library is None or hand is None:
            checks.unsupported(f"deck_state.{pid}", "library or hand counts are malformed")
            continue
        checks.compare(
            f"deck_state.{pid}.main_deck",
            {template["card_identity"]: template["count"]},
            dict(library + hand),
            "library and hand together are the main deck before any card leaves them",
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
    requested_commanders: dict[str, list[tuple[str, str, int]]] = {}
    for commander in commander_state.get("commanders") or []:
        owner = _seat(commander.get("owner")) or ""
        requested_commanders.setdefault(owner, []).append(
            (
                str(commander.get("card_identity")),
                str(commander.get("zone")),
                int(commander.get("prior_command_zone_cast_count") or 0),
            )
        )
    for pid, seen in players_by_id.items():
        observed = sorted(
            (
                str(entry.get("card_identity")),
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
        controller = _seat(obj.get("controller")) or ""
        plain = (
            controller == owner
            and not obj.get("tapped")
            and not obj.get("counters")
            and not obj.get("face_down")
            and not obj.get("attachments")
        )
        seen = players_by_id.get(owner) or {}
        present = any(
            isinstance(entry, dict)
            and entry.get("card_identity") == obj.get("card_identity")
            and entry.get("zone") == "command"
            for entry in seen.get("commanders") or []
        )
        checks.items.append(
            FieldCheck(
                f"semantic_objects.{sid}",
                "EQUAL" if plain and present else "MISMATCH" if plain else "UNSUPPORTED",
                {"card_identity": obj.get("card_identity"), "owner": owner, "zone": zone},
                {"present_in_owner_command_zone": present},
                "a command-zone commander, owned and controlled by its owner, untapped, "
                "with no counters, attachments or face-down status",
            )
        )
    for pid, seen in players_by_id.items():
        for zone in ("battlefield", "graveyard", "exile"):
            zone_counts = _counts(seen.get(f"{zone}_card_counts"))
            checks.compare(
                f"zones.{pid}.{zone}",
                {},
                dict(zone_counts) if zone_counts is not None else None,
                "the requested state places no object in this zone",
            )

    temporal = record.get("temporal_state") or {}
    observed_point = _OBSERVED_POINT if capture == CAPTURE_POINT else {"capture": capture}
    for key in ("phase", "turn_number"):
        checks.compare(
            f"temporal_state.{key}",
            temporal.get(key),
            observed_point.get(key),
            f"the state was read at {capture!r}",
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

    knowledge = record.get("knowledge_state") or {}
    viewer_states = knowledge.get("viewer_states") or []
    knowledge_empty = all(
        isinstance(view, dict) and not any(value for key, value in view.items() if key != "viewer")
        for view in viewer_states
    )
    if knowledge_empty:
        checks.items.append(
            FieldCheck(
                "knowledge_state",
                "EQUAL",
                "no knowledge permissions",
                "none can exist at a natural game start",
                "no spell or ability has resolved before the first pregame decision",
            )
        )
    else:
        checks.unsupported(
            "knowledge_state", "knowledge permissions are not constructed", knowledge
        )

    randomness = record.get("rules_randomness") or {}
    checks.compare(
        "rules_randomness.rules_seed",
        randomness.get("rules_seed"),
        acknowledged_seed,
        "the seed the engine acknowledged on game creation",
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
