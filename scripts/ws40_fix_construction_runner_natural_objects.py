#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--runner', type=Path, required=True)
    args = ap.parse_args()
    p = args.runner
    s = p.read_text(encoding='utf-8')
    start = s.index('def _objects_from_native(raw: dict[str, Any], b: dict[str, Any]) -> list[dict[str, Any]]:')
    end = s.index('\n\ndef _commander_from_native', start)
    replacement = r'''def _objects_from_native(raw: dict[str, Any], b: dict[str, Any]) -> list[dict[str, Any]]:
    # NATURAL_GAME_START has RegisteredPlayer/Deck commander registration but no live Card object yet.
    # Reconstruct only the frozen pregame commander object projection after validating that native
    # registration contains the exact commander identity for the mapped owner. This is identity mapping,
    # not a fabricated rules state: Commander rules are enabled and the actual runtime later creates the
    # command-zone Card through Forge's normal game-start path.
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
    s = s[:start] + replacement + s[end:]

    # Fail closed: a provider-side digest proves integrity of request-bound configuration, not
    # independent native observation of Rules state. The v2 normalizer still carries request-bound
    # stack semantics (cast_complete/costs_paid/modes/targets) and portions of combat semantics into
    # the normalized projection. Those fields are not eligible for no-request-echo credit until they
    # are independently observed/derived from Forge-native state or reclassified by contract authority
    # as non-Rules configuration. Do not allow a 107/107 digest equality to mask this provenance gap.
    if s.count('        "no_request_echo": True,') != 1:
        raise RuntimeError('expected exactly one optimistic no_request_echo claim')
    s = s.replace('        "no_request_echo": True,', '        "no_request_echo": False,', 1)
    if s.count('            "request_values_used_by_normalizer": False,') != 1:
        raise RuntimeError('expected exactly one request-values proof flag')
    s = s.replace(
        '            "request_values_used_by_normalizer": False,',
        '            "request_values_used_by_normalizer": True,\n'
        '            "status": "NOT_GRANTED",\n'
        '            "rules_state_gaps": [\n'
        '                "stack_state.cast_complete",\n'
        '                "stack_state.costs_paid",\n'
        '                "stack_state.modes",\n'
        '                "stack_state.targets",\n'
        '                "combat_state request-bound subfields not overwritten by native Combat observation",\n'
        '            ],',
        1,
    )

    p.write_text(s, encoding='utf-8')
    print('WS40_NATURAL_COMMANDER_OBJECT_PROJECTION_FIX=PASS')
    print('WS40_NO_REQUEST_ECHO_FAIL_CLOSED=PASS')


if __name__ == '__main__':
    main()
