"""PB-03 record-aware dimension admission against the live bridge manifest.

Admission is routing only. It never awards FULL107 credit and never changes the
provider global starting_state_injection_supported capability. A record is
admitted only when every mechanism implied by its required events and frozen
state is positively represented by the bridge itemised restoration manifest.
Unknown, malformed, or unsupported dimensions fail closed.
"""

from __future__ import annotations

from typing import Any

ADMITTED = "ADMITTED_TO_NATIVE_RESTORATION"
BLOCKED_MISSING_DIMENSION = "BLOCKED_MISSING_DIMENSION"
BLOCKED_MANIFEST_UNAVAILABLE = "BLOCKED_MANIFEST_UNAVAILABLE"
BLOCKED_UNKNOWN_DIMENSION = "BLOCKED_UNKNOWN_DIMENSION"
_UNMAPPED = "<unmapped-required-event>"

_EVENT_TOKENS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("commander_choice:hand", ("hand identity",)),
    ("commander_choice:graveyard", ("battlefield/graveyard/exile placement",)),
    ("commander_choice:exile", ("battlefield/graveyard/exile placement",)),
    ("commander_choice:command", ("battlefield/graveyard/exile placement",)),
    ("commander_choice:library", ("partial library identity",)),
    ("attacker_declared", ("qualified turn-1",)),
    ("declare_attacker_frame", ("qualified turn-1",)),
    ("declare_blocker_frame", ("qualified turn-1",)),
    ("legal_blocker_partition", ("qualified turn-1",)),
    ("blocker_declared", ("qualified turn-1",)),
    ("commander_zone_event:hand", ("hand identity",)),
    ("commander_zone_event:graveyard", ("battlefield/graveyard/exile placement",)),
    ("commander_zone_event:exile", ("battlefield/graveyard/exile placement",)),
    ("commander_zone_event:command", ("battlefield/graveyard/exile placement",)),
    ("commander_zone_event:library", ("partial library identity",)),
    ("next_turn", ("qualified turn-1",)),
    ("priority_ring_live_order", ("qualified turn-1",)),
    ("priority_action_resets_pass_count", ("qualified turn-1",)),
    ("extra_turn_created", ("temporal points outside the qualified",)),
    ("response_on_stack", ("stack spells",)),
    ("APNAP_stack_order", ("stack spells",)),
    ("simultaneous_trigger_event", ("stack spells",)),
    ("commander_damage_total", ("commander damage matrices",)),
    ("commander_combat_damage", ("commander damage matrices",)),
    ("commander_damage_checked_per_commander", ("commander damage matrices",)),
    ("player_loses", ("life totals",)),
    ("player_leaves", ("life totals",)),
    ("object_leaves_game", ("life totals",)),
    ("multiplayer_cleanup", ("life totals",)),
    ("rules_rng:", ("explicit Rules-seed binding",)),
    ("readback_required", ("strict native readback",)),
    ("prior_cast_counts", ("prior cast counts",)),
)

_ZONE_TOKENS: dict[str, tuple[str, ...]] = {
    "battlefield": ("battlefield/graveyard/exile placement",),
    "graveyard": ("battlefield/graveyard/exile placement",),
    "exile": ("battlefield/graveyard/exile placement",),
    "hand": ("hand identity",),
    "command": (),
    "library": ("partial library identity",),
    "stack": ("stack spells",),
}

_STATE_TOKENS = (
    "controller/owner divergence",
    "attachments and counters",
    "tapped permanents",
    "poison counters",
    "face_down=true",
    "revealed-zone restoration",
    "temporal points outside the qualified",
    "commander relations other than validated Partner linkage",
    "zero-life pre-start",
)

_DECLARED_TOKENS = frozenset(
    token for _prefix, tokens in _EVENT_TOKENS for token in tokens
) | frozenset(
    token for tokens in _ZONE_TOKENS.values() for token in tokens
) | frozenset(_STATE_TOKENS)


def _normalise(entry: Any) -> str:
    return str(entry or "").lower()


def _manifest_index(manifest: dict[str, Any] | None) -> dict[str, str] | None:
    if not isinstance(manifest, dict):
        return None
    supported = manifest.get("supported_dimensions")
    unsupported = manifest.get("unsupported_dimensions")
    if not isinstance(supported, list) or not isinstance(unsupported, list):
        return None
    if not supported and not unsupported:
        return None

    index: dict[str, str] = {}
    for token in _DECLARED_TOKENS:
        supported_hit = any(token in _normalise(entry) for entry in supported)
        unsupported_hit = any(token in _normalise(entry) for entry in unsupported)
        if supported_hit:
            index[token] = "supported"
        elif unsupported_hit:
            index[token] = "unsupported"
        else:
            index[token] = "unknown"
    return index


def _required_events(record: dict[str, Any]) -> list[str]:
    events = record.get("expected_events")
    if isinstance(events, dict):
        raw = events.get("required_events") or []
    elif isinstance(events, list):
        raw = events
    else:
        raw = []
    return [str(event) for event in raw]


def _zone_objects(record: dict[str, Any]) -> list[str]:
    zones: set[str] = set()
    for obj in record.get("semantic_objects") or []:
        if isinstance(obj, dict) and isinstance(obj.get("zone"), str):
            zones.add(str(obj["zone"]).lower())
    return sorted(zones)


def _record_state_tokens(record: dict[str, Any]) -> list[str]:
    """Dimensions implied by the frozen state itself, not by its fixture id."""
    tokens: set[str] = set()

    for player in record.get("players") or []:
        if not isinstance(player, dict):
            continue
        life = player.get("life")
        if isinstance(life, int) and not isinstance(life, bool) and life == 0:
            tokens.add("zero-life pre-start")
        poison = player.get("poison")
        if isinstance(poison, int) and not isinstance(poison, bool) and poison != 0:
            tokens.add("poison counters")

    for obj in record.get("semantic_objects") or []:
        if not isinstance(obj, dict):
            continue
        zone = str(obj.get("zone") or "").lower()
        if zone in _ZONE_TOKENS:
            tokens.update(_ZONE_TOKENS[zone])
        elif zone:
            tokens.add(_UNMAPPED)
        if obj.get("owner") != obj.get("controller"):
            tokens.add("controller/owner divergence")
        if obj.get("tapped") is True:
            tokens.add("tapped permanents")
        counters = obj.get("counters")
        if isinstance(counters, dict) and counters:
            tokens.add("attachments and counters")
        attachments = obj.get("attachments")
        if isinstance(attachments, list) and attachments:
            tokens.add("attachments and counters")
        if obj.get("face_down") is True:
            tokens.add("face_down=true")
        if obj.get("revealed") is True:
            tokens.add("revealed-zone restoration")

    temporal = record.get("temporal_state")
    if isinstance(temporal, dict):
        turn = temporal.get("turn_number")
        if isinstance(turn, int) and not isinstance(turn, bool) and turn != 1:
            tokens.add("temporal points outside the qualified")

    commander_state = record.get("commander_state")
    if isinstance(commander_state, dict):
        relations = commander_state.get("multiple_commander_relations") or []
        if isinstance(relations, list):
            for relation in relations:
                if not isinstance(relation, dict):
                    continue
                name = str(relation.get("relation") or "")
                if name and name != "Partner":
                    tokens.add("commander relations other than validated Partner linkage")
    return sorted(tokens)


def required_tokens(
    required_events: list[str],
    zone_objects: list[str] | None = None,
    *,
    record: dict[str, Any] | None = None,
) -> list[str]:
    tokens: list[str] = []
    for event in required_events:
        for prefix, declared in _EVENT_TOKENS:
            if str(event).startswith(prefix):
                tokens.extend(declared)
                break
        else:
            tokens.append(_UNMAPPED)

    for zone in zone_objects or []:
        if zone in _ZONE_TOKENS:
            tokens.extend(_ZONE_TOKENS[zone])
        else:
            tokens.append(_UNMAPPED)

    if record is not None:
        tokens.extend(_record_state_tokens(record))
    return sorted(set(tokens))


def admit_row(
    required_events: list[str],
    manifest: dict[str, Any] | None,
    zone_objects: list[str] | None = None,
    *,
    record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Decide admission. The verdict is never a runtime result."""
    tokens = required_tokens(required_events, zone_objects, record=record)
    if not tokens:
        return {
            "verdict": BLOCKED_UNKNOWN_DIMENSION,
            "required_tokens": [],
            "missing_tokens": [],
            "unknown_tokens": [],
            "reason": (
                "the row declares no recognised required mechanism; an empty "
                "declaration cannot establish constructibility and fails closed"
            ),
        }
    if _UNMAPPED in tokens:
        return {
            "verdict": BLOCKED_UNKNOWN_DIMENSION,
            "required_tokens": tokens,
            "missing_tokens": [_UNMAPPED],
            "unknown_tokens": [_UNMAPPED],
            "reason": (
                "the row contains an obligation or frozen-state dimension with no "
                "declared mapping, so admission fails closed"
            ),
        }

    index = _manifest_index(manifest)
    if index is None:
        return {
            "verdict": BLOCKED_MANIFEST_UNAVAILABLE,
            "required_tokens": tokens,
            "missing_tokens": tokens,
            "unknown_tokens": [],
            "reason": (
                "the bridge restoration manifest is unavailable or malformed; "
                "the global capability flag is not consulted as a fallback"
            ),
        }

    unknown = [token for token in tokens if index.get(token) == "unknown"]
    missing = [token for token in tokens if index.get(token) != "supported"]
    if unknown:
        return {
            "verdict": BLOCKED_UNKNOWN_DIMENSION,
            "required_tokens": tokens,
            "missing_tokens": missing,
            "unknown_tokens": unknown,
            "reason": (
                "required capability token(s) match neither supported nor unsupported "
                f"bridge dimensions: {sorted(unknown)}"
            ),
        }
    if missing:
        return {
            "verdict": BLOCKED_MISSING_DIMENSION,
            "required_tokens": tokens,
            "missing_tokens": missing,
            "unknown_tokens": [],
            "reason": (
                "required starting-state dimension(s) are explicitly unsupported by "
                f"the bridge manifest: {missing}"
            ),
        }

    return {
        "verdict": ADMITTED,
        "required_tokens": tokens,
        "missing_tokens": [],
        "unknown_tokens": [],
        "reason": (
            "every required mechanism is supported by the live restoration manifest; "
            "the row is routed to native execution and receives no credit from admission"
        ),
    }


def admit_record(record: dict[str, Any], manifest: dict[str, Any] | None) -> dict[str, Any]:
    return admit_row(
        _required_events(record),
        manifest,
        _zone_objects(record),
        record=record,
    )


def admit_manifest(
    records: list[dict[str, Any]], manifest: dict[str, Any] | None
) -> dict[str, Any]:
    admitted: list[str] = []
    blocked: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    for record in records:
        fixture_id = str(record.get("fixture_id") or "")
        result = admit_record(record, manifest)
        row = {
            "fixture_id": fixture_id,
            "verdict": result["verdict"],
            "required_tokens": result["required_tokens"],
            "missing_tokens": result["missing_tokens"],
            "reason": result["reason"],
        }
        rows.append(row)
        if result["verdict"] == ADMITTED:
            admitted.append(fixture_id)
        else:
            blocked[fixture_id] = row

    return {
        "schema_version": "commander-lab.pb03-dimension-admission/2.0.0",
        "classification": "TECHNICALLY_CONFORMANT",
        "rows_total": len(records),
        "admitted": sorted(admitted),
        "blocked": dict(sorted(blocked.items())),
        "rows": sorted(rows, key=lambda row: row["fixture_id"]),
        "counts": {"admitted": len(admitted), "blocked": len(blocked)},
        "projection_note": (
            "admission is routing only. Every admitted row still requires native "
            "runtime execution; PASS/FAIL/UNKNOWN are determined only by observed "
            "runtime evidence"
        ),
    }
