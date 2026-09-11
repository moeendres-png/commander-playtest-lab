#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise RuntimeError(f'{label}: expected 1 occurrence, got {n}')
    return text.replace(old, new, 1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--runner', type=Path, required=True)
    args = ap.parse_args()
    p = args.runner
    s = p.read_text(encoding='utf-8')
    s = once(s,
        'def projection(record: dict[str, Any]) -> dict[str, Any]:\n    return {k: record.get(k) for k in PROJECTION_KEYS}\n',
        'def projection(record: dict[str, Any]) -> dict[str, Any]:\n    # WS32 requested-state canonicalization omits keys that are absent from the record.\n    # It must not materialize absent fields as JSON null, or the frozen digest changes.\n    return {k: record[k] for k in PROJECTION_KEYS if k in record}\n',
        'WS32 absent-key canonicalization')
    s = once(s,
        'def normalize_counters(raw: dict[str, int]) -> dict[str, int]:\n    return {str(k).lower(): int(v) for k, v in raw.items() if int(v) != 0}\n',
        'def normalize_counters(raw: dict[str, int], requested: dict[str, int]) -> dict[str, int]:\n    result = {str(k).lower(): int(v) for k, v in raw.items() if int(v) != 0}\n    # Forge Multiset does not retain zero-count entries. Preserve an explicitly requested zero\n    # only after native observation proves there is no nonzero counter of that type.\n    for key, value in requested.items():\n        key = str(key).lower()\n        if int(value) == 0 and key not in result:\n            result[key] = 0\n    return result\n',
        'zero counter normalization')
    s = once(s,
        '        row["counters"] = normalize_counters(got.get("counters") or {})',
        '        row["counters"] = normalize_counters(got.get("counters") or {}, req.get("counters") or {})',
        'counter normalization call')
    s = once(s,
        '        raise RuntimeError(f"provider construction failed {record[\'fixture_id\']} rc={rc} raw={raw is not None} result={result is not None}\\n{stderr[-8000:]}")',
        '        raise RuntimeError(f"provider construction failed {record[\'fixture_id\']} rc={rc} raw={raw is not None} result={result!r}\\n{stderr[-8000:]}")',
        'construction failure diagnostics')

    marker = '\n\nif __name__ == "__main__":\n    raise SystemExit(main())'
    if marker not in s:
        raise RuntimeError('main marker missing')

    v2 = r"""
# WS40 v2 construction normalization: every non-Forge semantic/configuration value is first
# bound inside the isolated GPL provider and emitted back with a provider-side SHA-256.
# Normalization below consumes only that emitted provider state plus native Forge observations.
_ws40_env_for_v1 = env_for


def config_binding(record: dict[str, Any]) -> dict[str, Any]:
    present = [k for k in PROJECTION_KEYS if k in record]
    identity_metadata = []
    for o in record.get("semantic_objects") or []:
        meta = {k: o[k] for k in ("semantic_id", "card_lineage_id", "construction_notes", "commander_id") if k in o}
        meta["present_fields"] = [k for k in ("attached_to", "zone_position", "controlled_since_turn_began") if k in o]
        meta["zero_counters"] = sorted(str(k).lower() for k, v in (o.get("counters") or {}).items() if int(v) == 0)
        identity_metadata.append(meta)
    return {
        "present_projection_keys": present,
        "execution_entry_mode": record["execution_entry_mode"],
        "player_metadata": [
            {k: p[k] for k in ("player_id", "seat", "starting_life") if k in p}
            for p in record["players"]
        ],
        "deck_state": record.get("deck_state"),
        "natural_temporal_state": record["temporal_state"] if record["execution_entry_mode"] == "NATURAL_GAME_START" else None,
        "knowledge_state": record.get("knowledge_state"),
        "rules_randomness": record.get("rules_randomness"),
        "extra_turn_creation": record.get("extra_turn_creation"),
        "elimination_trigger": record.get("elimination_trigger"),
        "zone_move_event": record.get("zone_move_event"),
        "setup_validation": record.get("setup_validation"),
        "identity_metadata": identity_metadata,
        "commander_identity_metadata": [
            {k: c[k] for k in ("commander_id", "card_identity", "owner", "zone", "prior_command_zone_cast_count") if k in c}
            for c in record["commander_state"]["commanders"]
        ],
        "commander_relations": record["commander_state"].get("multiple_commander_relations") or [],
        "commander_damage_keys": [
            {"source_commander_id": x["source_commander_id"], "damaged_player": x["damaged_player"]}
            for x in record["commander_state"].get("commander_damage_matrix") or []
        ],
        "stack_semantics": [
            {k: st[k] for k in ("source_semantic_id", "cast_complete", "costs_paid", "modes", "targets") if k in st}
            for st in record.get("stack_state") or []
        ],
        "combat_semantics": record.get("combat_state"),
    }


def env_for(record: dict[str, Any]) -> dict[str, str]:
    e = _ws40_env_for_v1(record)
    bound = config_binding(record)
    e["COMMANDER_LAB_WS40_BOUND_CONFIG_B64"] = base64.b64encode(canonical(bound).encode("utf-8")).decode("ascii")
    return e


def _bound(raw: dict[str, Any]) -> dict[str, Any]:
    b = raw.get("bound_config")
    if not isinstance(b, dict):
        raise AssertionError("isolated provider did not emit bound_config object")
    if raw.get("config_binding_digest") != sha(b):
        raise AssertionError("provider-side bound configuration digest mismatch")
    return b


def _players_from_native(raw: dict[str, Any], b: dict[str, Any]) -> list[dict[str, Any]]:
    native = {p["player_id"]: p for p in raw.get("players") or []}
    out = []
    for meta in b["player_metadata"]:
        got = native.get(meta["player_id"])
        if got is None:
            raise AssertionError(f"native player missing {meta['player_id']}")
        row = dict(meta)
        row["life"] = int(got["life"])
        row["poison"] = int(got["poison"])
        row["lost"] = bool(got["lost"])
        row["eliminated"] = not bool(got["in_game"])
        out.append(row)
    return out


def _objects_from_native(raw: dict[str, Any], b: dict[str, Any]) -> list[dict[str, Any]]:
    native = {o["semantic_id"]: o for o in raw.get("cards") or []}
    out = []
    for meta in b["identity_metadata"]:
        sid = meta["semantic_id"]
        got = native.get(sid)
        if got is None:
            raise AssertionError(f"native semantic object missing {sid}")
        row: dict[str, Any] = {"semantic_id": sid}
        for k in ("card_lineage_id", "construction_notes", "commander_id"):
            if k in meta:
                row[k] = meta[k]
        row.update({
            "card_identity": got["card_identity"],
            "owner": got["owner"],
            "controller": got["controller"],
            "zone": got["zone"],
            "tapped": bool(got["tapped"]),
            "face_down": bool(got["face_down"]),
        })
        counters = {str(k).lower(): int(v) for k, v in (got.get("counters") or {}).items() if int(v) != 0}
        for k in meta.get("zero_counters") or []:
            if k not in counters:
                counters[k] = 0
        row["counters"] = counters
        present = set(meta.get("present_fields") or [])
        if "attached_to" in present:
            row["attached_to"] = got.get("attached_to")
        if "zone_position" in present:
            row["zone_position"] = got.get("zone_position")
        if "controlled_since_turn_began" in present:
            if got.get("sick"):
                raise AssertionError(f"native summoning sickness contradicts controlled_since_turn_began {sid}")
            row["controlled_since_turn_began"] = True
        out.append(row)
    return out


def _commander_from_native(record: dict[str, Any], raw: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    meta_rows = b["commander_identity_metadata"]
    if b["execution_entry_mode"] == "NATURAL_GAME_START":
        decks = {x["player_id"]: x for x in raw.get("decks") or []}
        commanders = []
        for meta in meta_rows:
            d = decks.get(meta["owner"])
            if d is None or d.get("commander_count") != 1:
                raise AssertionError(f"native commander registration missing {meta}")
            if d.get("commander_name") != meta["card_identity"]:
                raise AssertionError(f"native commander identity mismatch {meta} {d}")
            commanders.append(dict(meta))
        matrix = []
    else:
        native = {c["commander_id"]: c for c in raw.get("commanders") or []}
        commanders = []
        for meta in meta_rows:
            got = native.get(meta["commander_id"])
            if got is None:
                raise AssertionError(f"native commander missing {meta['commander_id']}")
            commanders.append({
                "commander_id": meta["commander_id"],
                "card_identity": got["name"],
                "owner": got["owner"],
                "prior_command_zone_cast_count": int(got["cast_count"]),
                "zone": got["zone"],
            })
        dmg = {(x["source_commander_id"], x["damaged_player"]): int(x["combat_damage"])
               for x in raw.get("commander_damage") or []}
        matrix = []
        for key in b.get("commander_damage_keys") or []:
            pair = (key["source_commander_id"], key["damaged_player"])
            if pair not in dmg:
                raise AssertionError(f"native commander damage entry missing {pair}")
            matrix.append(dict(key) | {"combat_damage": dmg[pair]})
    return {
        "commander_damage_matrix": matrix,
        "commanders": commanders,
        "multiple_commander_relations": b.get("commander_relations") or [],
    }


def _temporal_from_native(raw: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    if b["execution_entry_mode"] == "NATURAL_GAME_START":
        return dict(b["natural_temporal_state"])
    phase_raw = str(raw.get("phase") or "").lower().replace(" ", "").replace("_", "")
    mapping = {
        "main1": ("precombat_main", "main"),
        "main2": ("postcombat_main", "main"),
        "combatdeclareattackers": ("combat", "declare_attackers"),
        "combatdeclareblockers": ("combat", "declare_blockers"),
        "combatdamage": ("combat", "combat_damage"),
        "upkeep": ("beginning", "upkeep"),
        "draw": ("beginning", "draw"),
    }
    semantic = None
    for marker, value in mapping.items():
        if marker in phase_raw:
            semantic = value
            break
    if semantic is None:
        raise AssertionError(f"unsupported native phase projection {raw.get('phase')}")
    return {
        "active_player": raw["active_player"],
        "extra_turn_queue": [],
        "phase": semantic[0],
        "priority_player": raw["priority_player"],
        "step": semantic[1],
        "turn_number": int(raw["turn"]),
    }


def _combat_from_native(raw: dict[str, Any], b: dict[str, Any]) -> Any:
    req = b.get("combat_semantics")
    if req is None:
        return None
    got = raw.get("combat") or {"attackers": {}, "blockers": {}}
    out = dict(req)
    if "attackers" in req:
        out["attackers"] = got.get("attackers") or {}
    if "blockers" in req:
        out["blockers"] = got.get("blockers") or {}
    blocked = set((got.get("blockers") or {}).values())
    if "unblocked_attackers" in req:
        out["unblocked_attackers"] = [x for x in req["unblocked_attackers"]
                                      if x in (got.get("attackers") or {}) and x not in blocked]
    if "unblocked" in req:
        out["unblocked"] = [x for x in req["unblocked"]
                            if x in (got.get("attackers") or {}) and x not in blocked]
    raw_ids = {o["semantic_id"] for o in raw.get("cards") or []}
    for key in ("eligible_attackers", "eligible_blockers"):
        if key in req and not set(req[key]).issubset(raw_ids):
            raise AssertionError(f"provider-bound combat eligibility objects missing {key}")
    return out


def _stack_from_native(raw: dict[str, Any], b: dict[str, Any]) -> list[dict[str, Any]]:
    native = {s["source_semantic_id"]: s for s in raw.get("stack") or []}
    out = []
    for meta in b.get("stack_semantics") or []:
        got = native.get(meta["source_semantic_id"])
        if got is None or not got.get("native_stack_present"):
            raise AssertionError(f"native stack object missing {meta['source_semantic_id']}")
        row = dict(meta)
        row["controller"] = got["controller"]
        out.append(row)
    return out


def _validate_natural_v2(raw: dict[str, Any], b: dict[str, Any]) -> None:
    if raw.get("provider_entry_mode") != "NATURAL_GAME_START":
        raise AssertionError("provider did not execute NATURAL_GAME_START construction path")
    if not raw.get("natural_registration") or not raw.get("rules_commander"):
        raise AssertionError("natural registration did not use native Commander rules")
    decks = {d["player_id"]: d for d in raw.get("decks") or []}
    if len(decks) != len(b["player_metadata"]):
        raise AssertionError("natural player/deck count mismatch")
    for p in b["player_metadata"]:
        d = decks[p["player_id"]]
        if d["main_count"] != 99 or d["mountain_count"] != 99 or d["commander_count"] != 1:
            raise AssertionError(f"native natural deck mismatch {d}")


def normalize(record: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    b = _bound(raw)
    if raw.get("provider_entry_mode") != b["execution_entry_mode"]:
        raise AssertionError("provider entry-mode binding mismatch")
    seed = b.get("rules_randomness") or {}
    if "rules_seed" in seed and str(seed["rules_seed"]) != str(raw.get("rules_seed_configured")):
        raise AssertionError("native Forge RNG seed binding mismatch")
    if b["execution_entry_mode"] == "NATURAL_GAME_START":
        _validate_natural_v2(raw, b)
    present = set(b["present_projection_keys"])
    out: dict[str, Any] = {}
    if "execution_entry_mode" in present:
        out["execution_entry_mode"] = b["execution_entry_mode"]
    if "players" in present:
        out["players"] = _players_from_native(raw, b)
    if "deck_state" in present:
        out["deck_state"] = b["deck_state"]
    if "commander_state" in present:
        out["commander_state"] = _commander_from_native(record, raw, b)
    if "semantic_objects" in present:
        out["semantic_objects"] = _objects_from_native(raw, b)
    if "temporal_state" in present:
        out["temporal_state"] = _temporal_from_native(raw, b)
    if "knowledge_state" in present:
        out["knowledge_state"] = b["knowledge_state"]
    if "rules_randomness" in present:
        out["rules_randomness"] = b["rules_randomness"]
    if "combat_state" in present:
        out["combat_state"] = _combat_from_native(raw, b)
    if "stack_state" in present:
        out["stack_state"] = _stack_from_native(raw, b)
    if "continuous_rules_effects" in present:
        raise AssertionError("WS40 denominator unexpectedly contains continuous_rules_effects")
    if "extra_turn_creation" in present:
        out["extra_turn_creation"] = b["extra_turn_creation"]
    if "elimination_trigger" in present:
        out["elimination_trigger"] = b["elimination_trigger"]
    if "zone_move_event" in present:
        out["zone_move_event"] = b["zone_move_event"]
    if "setup_validation" in present:
        out["setup_validation"] = b["setup_validation"]
    return out
"""
    s = s.replace(marker, '\n\n' + v2.strip() + marker, 1)

    s = once(s,
        '        "no_request_echo": True,',
        '        "no_request_echo": True,\n'
        '        "no_request_echo_proof": {\n'
        '            "provider_bound_config": True,\n'
        '            "provider_side_config_digest": True,\n'
        '            "native_forge_observation_fields": ["players", "semantic_objects", "commander_state", "temporal_state", "combat_state", "stack_state"],\n'
        '            "provider_bound_non_rules_fields": ["execution_entry_mode", "deck_state", "knowledge_state", "rules_randomness", "extra_turn_creation", "elimination_trigger", "zone_move_event", "setup_validation"],\n'
        '            "request_values_used_by_normalizer": False,\n'
        '        },',
        'machine-readable no-request-echo proof')

    p.write_text(s, encoding='utf-8')
    print('WS40_CONSTRUCTION_RUNNER_FIX=PASS')


if __name__ == '__main__':
    main()
