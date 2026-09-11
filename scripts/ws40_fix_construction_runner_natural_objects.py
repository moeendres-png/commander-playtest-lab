#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

FINAL_FORGE_COMMIT = "49ea6df753fa6c749138296a1fe9421467136dda"
FINAL_FORGE_TREE = "37ef36359cef74273ca40a2c1c676b8ede84a431"
OLD_FORGE_COMMIT = "3f53c7c4e93c011e781680ae2a0c195dd71414c0"
OLD_FORGE_TREE = "481d3ee3b4798b78b4f00a93cc8e2cb54d05391f"


def replace_function(s: str, name: str, next_name: str, replacement: str) -> str:
    start = s.index(f"def {name}(")
    end = s.index(f"\n\ndef {next_name}", start)
    return s[:start] + replacement.rstrip() + s[end:]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--runner', type=Path, required=True)
    args = ap.parse_args()
    p = args.runner
    s = p.read_text(encoding='utf-8')

    # The checked-in runner is a template; bind the generated executable runner to the
    # reproducibility-qualified final Forge source lock.
    if OLD_FORGE_COMMIT in s:
        s = s.replace(OLD_FORGE_COMMIT, FINAL_FORGE_COMMIT)
    if OLD_FORGE_TREE in s:
        s = s.replace(OLD_FORGE_TREE, FINAL_FORGE_TREE)
    if f'FORGE_COMMIT = "{FINAL_FORGE_COMMIT}"' not in s or f'FORGE_TREE = "{FINAL_FORGE_TREE}"' not in s:
        raise RuntimeError('generated runner Forge source lock not migrated')

    # NATURAL_GAME_START has RegisteredPlayer/Deck commander registration but no live
    # commander Card object yet. Reconstruct only provider-neutral identity metadata after
    # proving the exact native registration. This is not Magic legality or Rules-state echo.
    replacement_objects = r'''def _objects_from_native(raw: dict[str, Any], b: dict[str, Any]) -> list[dict[str, Any]]:
    if b["execution_entry_mode"] == "NATURAL_GAME_START":
        decks = {x["player_id"]: x for x in raw.get("decks") or []}
        commander_meta = {x["commander_id"]: x for x in b.get("commander_identity_metadata") or []}
        out = []
        for meta in b["identity_metadata"]:
            cid = meta.get("commander_id")
            if cid is None:
                raise AssertionError(f"natural semantic object lacks commander identity mapping {meta}")
            cm = commander_meta.get(cid)
            if cm is None:
                raise AssertionError(f"natural commander mapping missing {cid}")
            owner = cm["owner"]
            d = decks.get(owner)
            if d is None or d.get("commander_count") != 1 or d.get("commander_name") != cm["card_identity"]:
                raise AssertionError(f"native natural commander registration mismatch {cid} {d}")
            row = {
                "semantic_id": meta["semantic_id"],
                "card_identity": d["commander_name"],
                "owner": owner,
                "controller": owner,
                "zone": cm["zone"],
                "tapped": False,
                "face_down": False,
                "counters": {},
            }
            for k in ("card_lineage_id", "construction_notes", "commander_id"):
                if k in meta:
                    row[k] = meta[k]
            out.append(row)
        return out

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
    return out'''
    s = replace_function(s, '_objects_from_native', '_commander_from_native', replacement_objects)

    # Remove request Rules-state VALUES from provider-bound configuration. Only semantic
    # identity and requested field SHAPE remain; those are control-plane metadata used to
    # decide which native fields must be proven, never to populate their values.
    old_binding = '''        "stack_semantics": [\n            {k: st[k] for k in ("source_semantic_id", "cast_complete", "costs_paid", "modes", "targets") if k in st}\n            for st in record.get("stack_state") or []\n        ],\n        "combat_semantics": record.get("combat_state"),'''
    new_binding = '''        "stack_source_ids": [st["source_semantic_id"] for st in record.get("stack_state") or []],\n        "combat_fields": sorted((record.get("combat_state") or {}).keys()),'''
    if s.count(old_binding) != 1:
        raise RuntimeError('expected exactly one request-bound stack/combat binding block')
    s = s.replace(old_binding, new_binding, 1)

    replacement_combat = r'''def _combat_from_native(raw: dict[str, Any], b: dict[str, Any]) -> Any:
    fields = set(b.get("combat_fields") or [])
    if not fields:
        return None
    unsupported = sorted(fields.intersection({"eligible_attackers", "eligible_blockers"}))
    if unsupported:
        raise AssertionError(
            "CANONICAL_SETUP_UNSUPPORTED_PROVIDER:COMBAT_LEGAL_SURFACE_NATIVE_OBSERVATION_UNAVAILABLE:"
            + ",".join(unsupported)
        )
    got = raw.get("combat") or {"attackers": {}, "blockers": {}}
    attackers = dict(got.get("attackers") or {})
    blockers = dict(got.get("blockers") or {})
    out: dict[str, Any] = {}
    if "attackers" in fields:
        out["attackers"] = attackers
    if "blockers" in fields:
        out["blockers"] = blockers
    blocked = set(blockers.values())
    unblocked = [sid for sid in attackers if sid not in blocked]
    if "unblocked" in fields:
        out["unblocked"] = unblocked
    if "unblocked_attackers" in fields:
        out["unblocked_attackers"] = unblocked
    unknown = fields.difference({"attackers", "blockers", "unblocked", "unblocked_attackers"})
    if unknown:
        raise AssertionError("CANONICAL_SETUP_UNSUPPORTED_PROVIDER:COMBAT_FIELD_NATIVE_OBSERVATION_UNAVAILABLE:" + ",".join(sorted(unknown)))
    return out'''
    s = replace_function(s, '_combat_from_native', '_stack_from_native', replacement_combat)

    replacement_stack = r'''def _stack_from_native(raw: dict[str, Any], b: dict[str, Any]) -> list[dict[str, Any]]:
    source_ids = list(b.get("stack_source_ids") or [])
    if not source_ids:
        return []
    native = {s["source_semantic_id"]: s for s in raw.get("stack") or []}
    for sid in source_ids:
        got = native.get(sid)
        if got is None or not got.get("native_stack_present"):
            raise AssertionError(f"native stack object missing {sid}")
    # The qualification loader can prove current native stack presence/controller, but it
    # directly materializes the stack and therefore cannot independently prove the frozen
    # historical facts cast_complete/costs_paid or selected Charm modes. Emitting those
    # request values would be request echo. Fail closed instead of manufacturing credit.
    raise AssertionError("CANONICAL_SETUP_UNSUPPORTED_PROVIDER:STACK_CAST_HISTORY_NATIVE_OBSERVATION_UNAVAILABLE")'''
    s = replace_function(s, '_stack_from_native', '_validate_natural_v2', replacement_stack)

    # Keep the no-request-echo claim source-true. The runner may still fail construction on
    # unsupported native proof surfaces; that is a construction-support failure, not request echo.
    if s.count('        "no_request_echo": True,') != 1:
        raise RuntimeError('expected exactly one no_request_echo claim')
    if s.count('            "request_values_used_by_normalizer": False,') != 1:
        raise RuntimeError('expected exactly one request-values proof flag')
    s = s.replace(
        '            "request_values_used_by_normalizer": False,',
        '            "request_values_used_by_normalizer": False,\n'
        '            "status": "PASS_FAIL_CLOSED",\n'
        '            "rules_state_request_values_in_bound_config": False,\n'
        '            "fail_closed_native_proof_gaps": [\n'
        '                "stack_state historical cast/payment/mode facts",\n'
        '                "combat_state eligible_attackers/eligible_blockers legal-surface facts",\n'
        '            ],',
        1,
    )

    p.write_text(s, encoding='utf-8')
    print('WS40_NATURAL_COMMANDER_OBJECT_PROJECTION_FIX=PASS')
    print('WS40_ACTIVE_FORGE_PIN_MIGRATION=PASS')
    print('WS40_NO_REQUEST_ECHO_SOURCE_HARDENED=PASS')


if __name__ == '__main__':
    main()
