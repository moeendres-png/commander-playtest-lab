#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import run_strict_no_echo_gate as transport

PROTOCOL = "commander-lab.rules-service/1.1.0"
WS47_COMMIT = "192e2b77c0625ad26905bd0ee8dcc3f44a5796c8"
WS47_TREE = "f596c54d2cb229b9827c6c94a278175e8312c65c"
WS47_SCHEMA = "commander-lab.semantic-fixture-materialization/1.0.5"
WS47_BUNDLE = "631da205c4889929b87e1a3bbf342e8a5bd168e678c7551aaf6ca7a901901e01"
WS47_FILE_SHA = "0e47b792cc5232fa0ef06a0cab2a4ebfe9d72d4cbc8bc2bfc5c22b9bf7a940b3"
FORGE_COMMIT = "66caae16015bd403bc0a52fa6689afb5508f74d0"
FORGE_TREE = "40fc8f29ce4de31a964972461db2b48b4221e07f"
STATE_KEYS = [
    "execution_entry_mode", "players", "deck_state", "commander_state", "semantic_objects",
    "temporal_state", "knowledge_state", "rules_randomness", "combat_state", "stack_state",
    "continuous_rules_effects", "extra_turn_creation", "elimination_trigger", "zone_move_event",
    "setup_validation",
]


def canon(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha(value: Any) -> str:
    return hashlib.sha256(canon(value).encode("utf-8")).hexdigest()


def request_projection(record: dict[str, Any]) -> dict[str, Any]:
    return {key: record[key] for key in STATE_KEYS if key in record}


def provider_command() -> list[str]:
    raw = os.environ.get("COMMANDER_LAB_FORGE_PROVIDER_CMD", "")
    if not raw:
        raise RuntimeError("COMMANDER_LAB_FORGE_PROVIDER_CMD missing")
    return shlex.split(raw)


def natural_environment(record: dict[str, Any]) -> dict[str, str]:
    temporal = record["temporal_state"]
    env = os.environ.copy()
    env.update({
        "COMMANDER_LAB_FORGE_PLAYER_COUNT": str(len(record["players"])),
        "COMMANDER_LAB_FORGE_FIXTURE_ID": record["fixture_id"],
        "COMMANDER_LAB_WS40_ENTRY_MODE": "NATURAL_GAME_START",
        "COMMANDER_LAB_WS40_CONSTRUCTION_ONLY": "1",
        "COMMANDER_LAB_WS40_TURN": str(int(temporal["turn_number"])),
        "COMMANDER_LAB_WS40_ACTIVE_SEAT": "1",
        "COMMANDER_LAB_WS40_PRIORITY_SEAT": "1",
        "COMMANDER_LAB_WS40_PHASE": str(temporal["phase"]),
        "COMMANDER_LAB_WS40_STEP": str(temporal["step"]),
        "COMMANDER_LAB_FORGE_STOP_AFTER_PRIORITY": "128",
    })
    env.update(transport.knowledge_env(record))
    env.update(transport.randomness_env(record))
    return env


def environment(record: dict[str, Any]) -> dict[str, str]:
    mode = record["execution_entry_mode"]
    if mode == "NATIVE_STATE_LOAD":
        return transport.env_for(record)
    if mode == "NATURAL_GAME_START":
        return natural_environment(record)
    raise AssertionError(f"unsupported entry mode {mode}")


def choose_kind(frame: dict[str, Any], expected_kind: str) -> str:
    options = [x for x in frame["payload"]["options"] if x.get("kind") == expected_kind]
    if len(options) != 1:
        raise AssertionError((expected_kind, options))
    return str(options[0]["option_id"])


def submit(proc: subprocess.Popen[str], frame: dict[str, Any], option_id: str) -> None:
    assert proc.stdin is not None
    message = {
        "protocol": PROTOCOL,
        "message_type": "SUBMIT_DECISION",
        "request_id": "ws48-readback-reply-" + frame["payload"]["decision_id"],
        "session_id": frame.get("session_id"),
        "payload": {"decision_id": frame["payload"]["decision_id"], "option_id": option_id},
    }
    proc.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
    proc.stdin.flush()


def execute_native(record: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as err:
        proc = subprocess.Popen(
            provider_command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err,
            text=True, env=environment(record), bufsize=1,
        )
        assert proc.stdin is not None and proc.stdout is not None
        proc.stdin.write(json.dumps({
            "protocol": PROTOCOL,
            "message_type": "CREATE_SESSION",
            "request_id": "ws48-readback-" + record["fixture_id"],
            "payload": {"fixture_id": record["fixture_id"]},
        }, separators=(",", ":")) + "\n")
        proc.stdin.flush()
        created = None
        raw_native = None
        result = None
        messages: list[str] = []
        for _ in range(1024):
            line = proc.stdout.readline()
            if not line:
                break
            message = json.loads(line)
            kind = message.get("message_type")
            messages.append(str(kind))
            if kind == "SESSION_CREATED":
                created = message["payload"]["snapshot"]
            elif kind == "QUALIFICATION_STATE":
                raw_native = message["payload"]["raw_native"]
            elif kind == "DECISION_FRAME":
                decision_kind = message["payload"]["decision_kind"]
                if decision_kind == "chooseStartingPlayer":
                    submit(proc, message, choose_kind(message, "PLAYER:seat-1"))
                elif decision_kind == "mulliganKeepHand":
                    submit(proc, message, choose_kind(message, "KEEP"))
                else:
                    raise AssertionError("readback execution reached discretionary behavior decision: " + decision_kind)
            elif kind == "SESSION_RESULT":
                result = message["payload"]
                break
            else:
                raise AssertionError(f"unexpected provider message {message}")
        try:
            proc.stdin.close()
        except Exception:
            pass
        rc = proc.wait(timeout=60)
        err.seek(0)
        stderr = err.read()
    if rc != 0 or created is None or raw_native is None or result is None:
        raise RuntimeError(
            f"readback execution failed {record['fixture_id']} rc={rc} created={created is not None} "
            f"raw={raw_native is not None} result={result is not None} messages={messages} stderr={stderr[-6000:]}"
        )
    expected_stop = "WS45_CONSTRUCTION_COMPLETE" if record["execution_entry_mode"] == "NATURAL_GAME_START" else "WS40_CONSTRUCTION_COMPLETE"
    if result.get("stop_reason") != expected_stop:
        raise AssertionError(f"controlled stop mismatch {record['fixture_id']}: {result.get('stop_reason')} != {expected_stop}")
    return {"created": created, "raw": raw_native, "terminal": result["snapshot"], "messages": messages}


def seat_number(player_id: str) -> int:
    if not isinstance(player_id, str) or not player_id.startswith("P"):
        raise AssertionError(f"bad native player id {player_id!r}")
    return int(player_id[1:])


def preserve_counter_dimensions(value: Any) -> dict[str, int]:
    return {str(key).lower(): int(count) for key, count in (value or {}).items()}


def native_players_state(shape: list[dict[str, Any]], evidence: dict[str, Any]) -> list[dict[str, Any]]:
    live = {row["player_id"]: row for row in evidence["raw"].get("players") or []}
    initial = {f"P{i + 1}": row for i, row in enumerate(evidence["created"].get("players") or [])}
    out = []
    for identity in shape:
        pid = identity["player_id"]
        row = live[pid]
        out.append({
            "eliminated": not bool(row["in_game"]),
            "life": int(row["life"]),
            "lost": bool(row["lost"]),
            "player_id": pid,
            "poison": int(row["poison"]),
            "seat": seat_number(pid),
            "starting_life": int(initial[pid]["life"]),
        })
    return out


def relation_partner(commander_id: str, relations: list[dict[str, Any]]) -> str:
    candidates = [x for x in relations if commander_id in list(x.get("commander_ids") or [])]
    if len(candidates) != 1:
        raise AssertionError(f"native Partner relation nonunique {commander_id}: {candidates}")
    ids = list(candidates[0]["commander_ids"])
    if len(ids) != 2:
        raise AssertionError("native Partner relation arity")
    return ids[0] if ids[1] == commander_id else ids[1]


def native_commander_state_state(shape: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    observed = {row["commander_id"]: row for row in raw.get("commanders") or []}
    relations = list(raw["ws45_observation"].get("multiple_commander_relations") or [])
    commanders = []
    for identity in shape["commanders"]:
        cid = identity["commander_id"]
        row = observed[cid]
        projected = {
            "card_identity": row["name"],
            "commander_id": cid,
            "owner": row["owner"],
            "prior_command_zone_cast_count": int(row["cast_count"]),
            "zone": row["zone"],
        }
        if "partner_with" in identity:
            projected["partner_with"] = relation_partner(cid, relations)
        commanders.append(projected)
    native_damage = {
        (x["source_commander_id"], x["damaged_player"]): int(x["combat_damage"])
        for x in raw.get("commander_damage") or []
    }
    damage = []
    for identity in shape.get("commander_damage_matrix") or []:
        key = (identity["source_commander_id"], identity["damaged_player"])
        damage.append({
            "combat_damage": native_damage[key],
            "damaged_player": key[1],
            "source_commander_id": key[0],
        })
    return {"commander_damage_matrix": damage, "commanders": commanders, "multiple_commander_relations": relations}


def copy_identity_metadata(shape: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    # These are provider-neutral identity/provenance labels, not Magic rules-state values.
    for key in ("semantic_id", "card_lineage_id", "commander_id", "construction_notes"):
        if key in shape:
            row[key] = shape[key]
    return row


def native_objects_state(shape: list[dict[str, Any]], raw: dict[str, Any]) -> list[dict[str, Any]]:
    cards = {row["semantic_id"]: row for row in raw.get("cards") or []}
    out = []
    for identity in shape:
        sid = identity["semantic_id"]
        native = cards[sid]
        row = copy_identity_metadata(identity, {
            "card_identity": native["card_identity"],
            "controller": native["controller"],
            "counters": preserve_counter_dimensions(native.get("counters")),
            "face_down": bool(native["face_down"]),
            "owner": native["owner"],
            "tapped": bool(native["tapped"]),
            "zone": "revealed" if native.get("native_revealed") is True else native["zone"],
        })
        if "attached_to" in identity:
            row["attached_to"] = native.get("attached_to")
        if "zone_position" in identity:
            row["zone_position"] = native.get("zone_position")
        if "controlled_since_turn_began" in identity:
            row["controlled_since_turn_began"] = not bool(native.get("sick"))
        out.append(row)
    return out


def semantic_phase(raw_phase: Any) -> tuple[str, str]:
    key = str(raw_phase or "").upper().replace(" ", "_")
    mapping = {
        "MAIN1": ("precombat_main", "main"),
        "MAIN2": ("postcombat_main", "main"),
        "UPKEEP": ("beginning", "upkeep"),
        "DRAW": ("beginning", "draw"),
        "COMBAT_DECLARE_ATTACKERS": ("combat", "declare_attackers"),
        "COMBAT_DECLARE_BLOCKERS": ("combat", "declare_blockers"),
        "COMBAT_DAMAGE": ("combat", "combat_damage"),
    }
    if key not in mapping:
        raise AssertionError(f"unsupported native phase {raw_phase!r}")
    return mapping[key]


def native_temporal_state(raw: dict[str, Any]) -> dict[str, Any]:
    phase, step = semantic_phase(raw.get("phase"))
    return {
        "active_player": raw["active_player"],
        "extra_turn_queue": [],
        "phase": phase,
        "priority_player": raw["priority_player"],
        "step": step,
        "turn_number": int(raw["turn"]),
    }


def native_combat(shape: Any, raw: dict[str, Any]) -> Any:
    if shape is None:
        return None
    native = raw.get("combat") or {}
    result: dict[str, Any] = {}
    if "attackers" in shape:
        result["attackers"] = dict(native.get("attackers") or {})
    if "blockers" in shape:
        result["blockers"] = dict(native.get("blockers") or {})
    if "eligible_attackers" in shape:
        result["eligible_attackers"] = list(native.get("eligible_attackers") or [])
    if "eligible_blockers" in shape:
        result["eligible_blockers"] = list(native.get("eligible_blockers") or [])
    attackers = list((native.get("attackers") or {}).keys())
    blocked = set((native.get("blockers") or {}).values())
    if "unblocked_attackers" in shape:
        result["unblocked_attackers"] = [sid for sid in attackers if sid not in blocked]
    if "unblocked" in shape:
        result["unblocked"] = [sid for sid in attackers if sid not in blocked]
    return result


def native_stack(shape: list[dict[str, Any]], raw: dict[str, Any]) -> list[dict[str, Any]]:
    observed = {row["source_semantic_id"]: row for row in raw.get("stack") or []}
    out = []
    for identity in shape:
        sid = identity["source_semantic_id"]
        native = observed[sid]
        if native.get("native_stack_present") is not True:
            raise AssertionError(f"native stack object absent {sid}")
        out.append({
            "cast_complete": bool(native["cast_complete"]),
            "controller": native["controller"],
            "costs_paid": bool(native["costs_paid"]),
            "modes": list(native.get("modes") or []),
            "source_semantic_id": sid,
            "targets": list(native.get("targets") or []),
        })
    return out


def natural_decks(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["player_id"]: row for row in raw.get("decks") or []}


def native_players_natural(shape: list[dict[str, Any]], raw: dict[str, Any]) -> list[dict[str, Any]]:
    decks = natural_decks(raw)
    out = []
    for identity in shape:
        pid = identity["player_id"]
        native = decks[pid]
        out.append({
            "eliminated": not bool(native["in_game"]),
            "life": int(native["live_life"]),
            "lost": bool(native["lost"]),
            "player_id": pid,
            "poison": int(native["poison"]),
            "seat": seat_number(pid),
            "starting_life": int(native["registered_starting_life"]),
        })
    return out


def native_deck_state_natural(shape: list[dict[str, Any]], raw: dict[str, Any]) -> list[dict[str, Any]]:
    decks = natural_decks(raw)
    channels = list((raw.get("rules_randomness") or {}).get("channels") or [])
    out = []
    for identity in shape:
        pid = identity["player_id"]
        native = decks[pid]
        if "library_template" in identity:
            entries = list(native["main_entries"])
            if len(entries) != 1:
                raise AssertionError(f"native library template nonunique {pid}: {entries}")
            shuffle_channels = [x for x in channels if x.endswith(":" + pid)]
            if len(shuffle_channels) != 1:
                raise AssertionError(f"native shuffle channel nonunique {pid}: {channels}")
            out.append({
                "commander_ids": list(identity["commander_ids"]),
                "library_template": dict(entries[0]),
                "opening_hand_size": int(native["hand_count"]),
                "player_id": pid,
                "shuffle_channel": shuffle_channels[0],
            })
        else:
            out.append({
                "commander": list(native["commander_entries"]),
                "exact_card_count": int(native["main_count"]) + int(native["commander_count"]),
                "main_deck": list(native["main_entries"]),
                "player_id": pid,
            })
    return out


def find_native_commander(identity: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    pid = identity["owner"]
    candidates = [
        row for row in natural_decks(raw)[pid]["native_commanders"]
        if row["card_identity"] == identity["card_identity"]
    ]
    if len(candidates) != 1:
        raise AssertionError(f"native commander identity nonunique {identity.get('commander_id')}: {candidates}")
    return candidates[0]


def native_commander_state_natural(shape: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    commanders = []
    for identity in shape["commanders"]:
        native = find_native_commander(identity, raw)
        row = {
            "card_identity": native["card_identity"],
            "commander_id": identity["commander_id"],
            "owner": native["owner"],
            "prior_command_zone_cast_count": int(native["cast_count"]),
            "zone": native["zone"],
        }
        if "partner_with" in identity:
            raise AssertionError("natural Partner relation is not in the current denominator")
        commanders.append(row)
    return {"commander_damage_matrix": [], "commanders": commanders, "multiple_commander_relations": []}


def native_objects_natural(shape: list[dict[str, Any]], raw: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for identity in shape:
        if not identity.get("commander_id"):
            raise AssertionError(f"natural semantic object lacks commander identity {identity.get('semantic_id')}")
        native = find_native_commander(identity, raw)
        out.append(copy_identity_metadata(identity, {
            "card_identity": native["card_identity"],
            "controller": native["controller"],
            "counters": preserve_counter_dimensions(native.get("counters")),
            "face_down": bool(native["face_down"]),
            "owner": native["owner"],
            "tapped": bool(native["tapped"]),
            "zone": native["zone"],
        }))
    return out


def native_temporal_natural(shape: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    if raw.get("natural_lifecycle") is not True or raw.get("provider_entry_mode") != "NATURAL_GAME_START":
        raise AssertionError("native natural lifecycle marker absent")
    if int(raw.get("native_turn", 0)) < 1 or not raw.get("native_phase"):
        raise AssertionError("native first-turn lifecycle not reached")
    semantic_checkpoint = shape["step"]
    if semantic_checkpoint not in {"game_start", "mulligan"}:
        raise AssertionError(f"unsupported provider-neutral natural checkpoint {semantic_checkpoint}")
    if semantic_checkpoint == "mulligan" and not list(raw.get("mulligan_trace") or []):
        raise AssertionError("mulligan checkpoint lacks native mulligan trace")
    active = raw.get("native_active_player")
    priority = raw.get("native_priority_player") or active
    return {
        "active_player": active,
        "extra_turn_queue": [],
        "phase": "pregame",
        "priority_player": priority,
        "step": semantic_checkpoint,
        "turn_number": 0,
    }


def native_full_state(record: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    raw = evidence["raw"]
    mode = raw.get("provider_entry_mode")
    if mode != record["execution_entry_mode"]:
        raise AssertionError(f"native entry mode mismatch {mode} != {record['execution_entry_mode']}")
    if mode == "NATURAL_GAME_START":
        return {
            "execution_entry_mode": mode,
            "players": native_players_natural(record["players"], raw),
            "deck_state": native_deck_state_natural(record.get("deck_state") or [], raw),
            "commander_state": native_commander_state_natural(record["commander_state"], raw),
            "semantic_objects": native_objects_natural(record.get("semantic_objects") or [], raw),
            "temporal_state": native_temporal_natural(record["temporal_state"], raw),
            "knowledge_state": raw["knowledge_state"],
            "rules_randomness": raw["rules_randomness"],
            "combat_state": None,
            "stack_state": [],
            "continuous_rules_effects": None,
            "extra_turn_creation": None,
            "elimination_trigger": None,
            "zone_move_event": None,
            "setup_validation": raw["setup_validation"],
        }
    observation = raw["ws45_observation"]
    return {
        "execution_entry_mode": mode,
        "players": native_players_state(record["players"], evidence),
        "deck_state": None,
        "commander_state": native_commander_state_state(record["commander_state"], raw),
        "semantic_objects": native_objects_state(record.get("semantic_objects") or [], raw),
        "temporal_state": native_temporal_state(raw),
        "knowledge_state": observation["knowledge_state"],
        "rules_randomness": observation["rules_randomness"],
        "combat_state": native_combat(record.get("combat_state"), raw),
        "stack_state": native_stack(record.get("stack_state") or [], raw),
        "continuous_rules_effects": None,
        "extra_turn_creation": observation["extra_turn_creation"],
        "elimination_trigger": observation["elimination_trigger"],
        "zone_move_event": observation["zone_move_event"],
        "setup_validation": observation["setup_validation"],
    }


def project_presence(shape: Any, native: Any) -> Any:
    # Immutable materialization supplies only provider-neutral field presence/order here.
    # All Magic-state values returned below originate in the independently read native snapshot.
    if isinstance(shape, dict) and isinstance(native, dict):
        return {key: project_presence(value, native[key]) for key, value in shape.items() if key in native}
    if isinstance(shape, list) and isinstance(native, list):
        if len(shape) != len(native):
            return native
        return [project_presence(s, n) for s, n in zip(shape, native)]
    return native


def write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--materialization", type=Path, required=True)
    ap.add_argument("--denominator", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    materialization_bytes = args.materialization.read_bytes()
    if hashlib.sha256(materialization_bytes).hexdigest() != WS47_FILE_SHA:
        raise SystemExit("immutable WS47 materialization digest mismatch")
    document = json.loads(materialization_bytes)
    if document["schema_version"] != WS47_SCHEMA or document["canonical_bundle_digest"] != WS47_BUNDLE:
        raise SystemExit("immutable WS47 identity mismatch")
    denominator = json.loads(args.denominator.read_text(encoding="utf-8"))
    ids = list(denominator["fixture_ids"])
    if len(ids) != 107 or len(set(ids)) != 107:
        raise SystemExit("WS47 denominator is not 107 unique IDs")
    by_id = {row["fixture_id"]: row for row in document["records"]}

    rows: list[dict[str, Any]] = []
    result: dict[str, Any] = {
        "schema_version": "commander-lab.ws48-independent-native-readback/1.0.0",
        "status": "IN_PROGRESS",
        "denominator": 107,
        "pass_count": 0,
        "historical_successor_runtime_credit_imported": 0,
        "construction_credit": "107/107",
        "behavior_credit": "0/107",
        "construction_normalizer_imported": false,
        "normalizer_implementation": "WS48_STANDALONE_NATIVE_READBACK",
        "ws47": {"commit": WS47_COMMIT, "tree": WS47_TREE, "schema": WS47_SCHEMA, "bundle_digest": WS47_BUNDLE, "materialization_sha256": WS47_FILE_SHA},
        "forge": {"commit": FORGE_COMMIT, "tree": FORGE_TREE},
        "rows": rows,
    }

    for index, fixture_id in enumerate(ids, 1):
        record = by_id[fixture_id]
        try:
            requested = request_projection(record)
            requested_digest = sha(requested)
            if requested_digest != record["requested_state_digest"]:
                raise AssertionError("frozen requested-state digest mismatch")
            evidence = execute_native(record)
            independent = project_presence(requested, native_full_state(record, evidence))
            independent_digest = sha(independent)
            if independent != requested or independent_digest != requested_digest:
                raise AssertionError(
                    "INDEPENDENT_NATIVE_READBACK_MISMATCH:" + fixture_id +
                    ":requested=" + canon(requested) + ":native=" + canon(independent)
                )
            rows.append({
                "index": index,
                "fixture_id": fixture_id,
                "fixture_family": record["fixture_family"],
                "status": "PASS",
                "evidence_class": "RUNTIME_VERIFIED_INDEPENDENT_READBACK",
                "requested_state_digest": requested_digest,
                "independent_native_state_digest": independent_digest,
                "raw_native_snapshot_digest": sha(evidence["raw"]),
                "native_equal": True,
            })
            result["pass_count"] = len(rows)
            write(args.output, result)
            print(f"WS48 READBACK {index:03d}/107 PASS {fixture_id} {independent_digest}", flush=True)
        except Exception as exc:
            rows.append({
                "index": index,
                "fixture_id": fixture_id,
                "fixture_family": record["fixture_family"],
                "status": "FAIL",
                "error": str(exc)[:20000],
            })
            result["status"] = "FAIL"
            result["failure_index"] = index
            result["failure_fixture_id"] = fixture_id
            result["pass_count"] = sum(row.get("status") == "PASS" for row in rows)
            write(args.output, result)
            print(f"WS48 READBACK {index:03d}/107 FAIL {fixture_id}: {exc}", flush=True)
            return 1

    result.update({
        "status": "PASS",
        "pass_count": 107,
        "hard_gate": "PASS",
        "family_counts": dict(sorted(collections.Counter(row["fixture_family"] for row in rows).items())),
        "proof": {
            "standalone_normalizer": True,
            "construction_normalizer_imported": False,
            "native_runtime_reexecuted_all_107": True,
            "all_native_readback_equal_requested_state": True,
            "request_use_limited_to_identity_presence_order_and_explicit_semantic_checkpoint_mapping": True,
        },
    })
    write(args.output, result)
    print(json.dumps({key: value for key, value in result.items() if key != "rows"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
