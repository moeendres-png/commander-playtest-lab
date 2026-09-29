"""PB-03 dimension admission against the live native-restoration manifest.

Admission answers only whether the frozen *starting state* is constructible by
the restoration seam. It is orthogonal to runtime execution: a blocked frozen
state may still have an engine-native causal reconstruction harness, and an
admitted row may still have no runtime harness. Admission therefore grants no
runtime or FULL107 credit.

The PB-03 denominator is explicit, but a fixture id never decides admission.
Required dimensions are derived only from required events and semantic-object
zones. Unknown dimensions and unavailable manifests fail closed.
"""

from __future__ import annotations

from typing import Any

ADMITTED = "ADMITTED_TO_NATIVE_RESTORATION"
BLOCKED_MISSING_DIMENSION = "BLOCKED_MISSING_DIMENSION"
BLOCKED_MANIFEST_UNAVAILABLE = "BLOCKED_MANIFEST_UNAVAILABLE"
BLOCKED_UNKNOWN_DIMENSION = "BLOCKED_UNKNOWN_DIMENSION"
_UNMAPPED = "<unmapped-required-event>"

PB03_FIXTURE_IDS: tuple[str, ...] = (
    "PILOT_DECLARE_ATTACKER",
    "PILOT_DECLARE_BLOCKER",
    "MICRO_RULES_RANDOMNESS",
    "WS05-MP-PRIO-3",
    "WS05-MP-PRIO-5",
    "WS05-MP-TRIG-3",
    "WS05-MP-TRIG-5",
    "WS05-MP-COMBAT-4",
    "WS05-MP-COMBAT-5",
    "WS05-MP-BLOCK-4",
    "WS05-MP-TURN-3",
    "WS05-MP-TURN-5",
    "WS05-MP-ELIM-OWNED-3",
    "WS05-MP-ELIM-CONTROL-3",
    "WS05-MP-ELIM-STACK-3",
    "WS05-MP-ELIM-PRIO-3",
    "WS05-MP-ELIM-TURN-3",
    "WS05-MP-ELIM-5",
    "WS05-CMD-ZONE-GY-YES",
    "WS05-CMD-ZONE-GY-NO",
    "WS05-CMD-ZONE-EXILE-YES",
    "WS05-CMD-ZONE-EXILE-NO",
    "WS05-CMD-ZONE-HAND-YES",
    "WS05-CMD-ZONE-HAND-NO",
    "WS05-CMD-ZONE-LIB-YES",
    "WS05-CMD-ZONE-LIB-NO",
    "WS05-CMD-DMG-SAME-21",
    "WS05-CMD-DMG-SPLIT",
    "WS05-CMD-DMG-CONTROL",
    "WS05-CMD-ELIM-4",
)

_EVENT_TOKENS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("commander_choice:graveyard", ("battlefield/graveyard/exile placement",)),
    ("commander_choice:exile", ("battlefield/graveyard/exile placement",)),
    ("commander_choice:hand", ("hand identity",)),
    ("commander_choice:library", ("partial library identity",)),
    ("commander_choice:command", ()),
    ("commander_zone_event:graveyard", ("battlefield/graveyard/exile placement",)),
    ("commander_zone_event:exile", ("battlefield/graveyard/exile placement",)),
    ("commander_zone_event:hand", ("hand identity",)),
    ("commander_zone_event:library", ("partial library identity",)),
    ("commander_zone_event:command", ()),
    ("attacker_declared", ("qualified turn-1",)),
    ("declare_attacker_frame", ("qualified turn-1",)),
    ("declare_blocker_frame", ("qualified turn-1",)),
    ("legal_blocker_partition", ("qualified turn-1",)),
    ("blocker_declared", ("qualified turn-1",)),
    ("priority_ring_live_order", ("qualified turn-1",)),
    ("priority_action_resets_pass_count", ("qualified turn-1",)),
    ("response_on_stack", ("stack spells",)),
    ("APNAP_stack_order", ("stack spells",)),
    ("simultaneous_trigger_event", ("stack spells",)),
    ("extra_turn_created", ("temporal points outside the qualified",)),
    ("next_turn", ("temporal points outside the qualified",)),
    ("commander_damage_total", ("commander damage matrices",)),
    ("commander_combat_damage", ("commander damage matrices",)),
    ("commander_damage_checked_per_commander", ("commander damage matrices",)),
    ("player_loses", ("life totals",)),
    ("player_leaves", ("life totals",)),
    ("multiplayer_cleanup", ("life totals",)),
    ("object_leaves_game", ("life totals",)),
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

_DECLARED_TOKENS = frozenset(
    token for _prefix, tokens in _EVENT_TOKENS for token in tokens
) | frozenset(token for tokens in _ZONE_TOKENS.values() for token in tokens)


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
        if any(token in _normalise(entry) for entry in supported):
            index[token] = "supported"
        elif any(token in _normalise(entry) for entry in unsupported):
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


def _zones(record: dict[str, Any]) -> list[str]:
    zones: set[str] = set()
    for obj in record.get("semantic_objects") or []:
        if isinstance(obj, dict) and isinstance(obj.get("zone"), str):
            zones.add(str(obj["zone"]).lower())
    return sorted(zones)


def required_tokens(required_events: list[str], zones: list[str]) -> list[str]:
    tokens: list[str] = []
    for event in required_events:
        matched = False
        for prefix, declared in _EVENT_TOKENS:
            if str(event).startswith(prefix):
                tokens.extend(declared)
                matched = True
                break
        if not matched:
            tokens.append(_UNMAPPED)

    for zone in zones:
        zone_tokens = _ZONE_TOKENS.get(zone)
        if zone_tokens is None:
            tokens.append(_UNMAPPED)
        else:
            tokens.extend(zone_tokens)
    return sorted(set(tokens))


def admit_record(
    record: dict[str, Any], manifest: dict[str, Any] | None
) -> dict[str, Any]:
    tokens = required_tokens(_required_events(record), _zones(record))
    if not tokens:
        return {
            "verdict": BLOCKED_UNKNOWN_DIMENSION,
            "required_tokens": [],
            "missing_tokens": [],
            "unknown_tokens": [],
            "reason": "empty dimension declaration fails closed",
        }

    if _UNMAPPED in tokens:
        return {
            "verdict": BLOCKED_UNKNOWN_DIMENSION,
            "required_tokens": tokens,
            "missing_tokens": [_UNMAPPED],
            "unknown_tokens": [_UNMAPPED],
            "reason": "at least one required event or zone has no declared restoration dimension",
        }

    index = _manifest_index(manifest)
    if index is None:
        return {
            "verdict": BLOCKED_MANIFEST_UNAVAILABLE,
            "required_tokens": tokens,
            "missing_tokens": tokens,
            "unknown_tokens": [],
            "reason": (
                "live restoration manifest is unavailable or malformed; "
                "starting_state_injection_supported is not used as a fallback"
            ),
        }

    unknown = [token for token in tokens if index.get(token) == "unknown"]
    missing = [token for token in tokens if index.get(token) == "unsupported"]
    if unknown:
        return {
            "verdict": BLOCKED_UNKNOWN_DIMENSION,
            "required_tokens": tokens,
            "missing_tokens": unknown,
            "unknown_tokens": unknown,
            "reason": f"required dimension is absent from both manifest lists: {unknown}",
        }
    if missing:
        return {
            "verdict": BLOCKED_MISSING_DIMENSION,
            "required_tokens": tokens,
            "missing_tokens": missing,
            "unknown_tokens": [],
            "reason": f"live restoration manifest marks required dimension unsupported: {missing}",
        }

    return {
        "verdict": ADMITTED,
        "required_tokens": tokens,
        "missing_tokens": [],
        "unknown_tokens": [],
        "reason": (
            "all frozen-state dimensions are supported by the live restoration manifest; "
            "this is admission only and grants no runtime or FULL107 credit"
        ),
    }


def admit_manifest(
    records: list[dict[str, Any]], manifest: dict[str, Any] | None
) -> dict[str, Any]:
    by_id = {str(record.get("fixture_id") or ""): record for record in records}
    missing_scope = [fixture for fixture in PB03_FIXTURE_IDS if fixture not in by_id]
    if missing_scope:
        raise ValueError(f"PB-03 denominator rows absent from materialization: {missing_scope}")

    rows: list[dict[str, Any]] = []
    admitted: list[str] = []
    blocked: dict[str, dict[str, Any]] = {}
    for fixture_id in PB03_FIXTURE_IDS:
        result = admit_record(by_id[fixture_id], manifest)
        row = {
            "fixture_id": fixture_id,
            "verdict": result["verdict"],
            "required_tokens": result["required_tokens"],
            "missing_tokens": result["missing_tokens"],
            "unknown_tokens": result["unknown_tokens"],
            "reason": result["reason"],
        }
        rows.append(row)
        if result["verdict"] == ADMITTED:
            admitted.append(fixture_id)
        else:
            blocked[fixture_id] = row

    return {
        "schema_version": "commander-lab.pb03-dimension-admission/3.0.0",
        "classification": "TECHNICALLY_CONFORMANT",
        "derivation": "required_events + semantic_objects[].zone only",
        "rows_total": len(PB03_FIXTURE_IDS),
        "admitted": sorted(admitted),
        "blocked": dict(sorted(blocked.items())),
        "rows": sorted(rows, key=lambda row: row["fixture_id"]),
        "counts": {"admitted": len(admitted), "blocked": len(blocked)},
        "runtime_relation": (
            "ORTHOGONAL: blocked admission does not prohibit genuine causal runtime "
            "execution; admitted admission does not prove runtime execution"
        ),
        "full107_credit": "NONE_FROM_ADMISSION",
    }
