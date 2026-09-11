#!/usr/bin/env python3
from __future__ import annotations

import argparse, collections, hashlib, json, os, shlex, subprocess, tempfile
from pathlib import Path
from typing import Any

import run_strict_no_echo_gate as transport

PROTOCOL = "commander-lab.rules-service/1.1.0"
WS44_COMMIT = "12940248497a8795991cbbd2eedef72945528cfe"
WS44_TREE = "cd83c973b269711106d08ab5be2d7672f05bcb7c"
WS44_SCHEMA = "commander-lab.semantic-fixture-materialization/1.0.4"
WS44_BUNDLE = "77b911195525c2fe8aff37f6c9573e5772f358b25646d0be5919314ed5e23b54"
WS44_FILE_SHA = "9b370244e4e5df3132e6e9a3d2b70ad641a5a6023fc7c86832931340d24bfa35"
FORGE_COMMIT = "66caae16015bd403bc0a52fa6689afb5508f74d0"
FORGE_TREE = "40fc8f29ce4de31a964972461db2b48b4221e07f"
PROJECTION_KEYS = [
    "execution_entry_mode", "players", "deck_state", "commander_state", "semantic_objects",
    "temporal_state", "knowledge_state", "rules_randomness", "combat_state", "stack_state",
    "continuous_rules_effects", "extra_turn_creation", "elimination_trigger", "zone_move_event",
    "setup_validation",
]


def canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(v: Any) -> str:
    return hashlib.sha256(canon(v).encode("utf-8")).hexdigest()


def projection(record: dict[str, Any]) -> dict[str, Any]:
    return {k: record.get(k) for k in PROJECTION_KEYS}


def command() -> list[str]:
    raw = os.environ.get("COMMANDER_LAB_FORGE_PROVIDER_CMD")
    if not raw:
        raise RuntimeError("COMMANDER_LAB_FORGE_PROVIDER_CMD missing")
    return shlex.split(raw)


def natural_env(record: dict[str, Any]) -> dict[str, str]:
    t = record["temporal_state"]
    e = os.environ.copy()
    e.update({
        "COMMANDER_LAB_FORGE_PLAYER_COUNT": str(len(record["players"])),
        "COMMANDER_LAB_FORGE_FIXTURE_ID": record["fixture_id"],
        "COMMANDER_LAB_WS40_ENTRY_MODE": "NATURAL_GAME_START",
        "COMMANDER_LAB_WS40_CONSTRUCTION_ONLY": "1",
        "COMMANDER_LAB_WS40_TURN": str(int(t["turn_number"])),
        "COMMANDER_LAB_WS40_ACTIVE_SEAT": "1",
        "COMMANDER_LAB_WS40_PRIORITY_SEAT": "1",
        "COMMANDER_LAB_WS40_PHASE": str(t["phase"]),
        "COMMANDER_LAB_WS40_STEP": str(t["step"]),
        "COMMANDER_LAB_FORGE_STOP_AFTER_PRIORITY": "128",
    })
    e.update(transport.knowledge_env(record))
    e.update(transport.randomness_env(record))
    return e


def env_for(record: dict[str, Any]) -> dict[str, str]:
    if record["execution_entry_mode"] == "NATIVE_STATE_LOAD":
        return transport.env_for(record)
    if record["execution_entry_mode"] == "NATURAL_GAME_START":
        return natural_env(record)
    raise AssertionError("unsupported execution entry mode " + str(record["execution_entry_mode"]))


def run_native(record: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as err:
        p = subprocess.Popen(command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err, text=True, env=env_for(record), bufsize=1)
        assert p.stdin is not None and p.stdout is not None
        p.stdin.write(json.dumps({"protocol": PROTOCOL, "message_type": "CREATE_SESSION", "request_id": "ws45-construct-" + record["fixture_id"], "payload": {"fixture_id": record["fixture_id"]}}, separators=(",", ":")) + "\n")
        p.stdin.flush()
        created = None
        raw = None
        result = None
        messages: list[str] = []
        for _ in range(1024):
            line = p.stdout.readline()
            if not line:
                break
            m = json.loads(line)
            typ = m.get("message_type")
            messages.append(str(typ))
            if typ == "SESSION_CREATED":
                created = m
                continue
            if typ == "QUALIFICATION_STATE":
                raw = m["payload"]["raw_native"]
                continue
            if typ == "DECISION_FRAME":
                kind = m["payload"]["decision_kind"]
                if kind == "chooseStartingPlayer":
                    transport.submit(p, m, transport.option(m, "PLAYER:seat-1"))
                    continue
                if kind == "mulliganKeepHand":
                    transport.submit(p, m, transport.option(m, "KEEP"))
                    continue
                raise AssertionError("construction reached unexpected discretionary decision: " + kind)
            if typ == "SESSION_RESULT":
                result = m
                break
            raise AssertionError(f"unexpected provider message {m}")
        try:
            p.stdin.close()
        except Exception:
            pass
        rc = p.wait(timeout=60)
        err.seek(0)
        stderr = err.read()
    if rc != 0 or created is None or raw is None or result is None:
        raise RuntimeError(f"provider construction failed {record['fixture_id']} rc={rc} created={created is not None} raw={raw is not None} result={result is not None} stderr={stderr[-6000:]}")
    stop = result["payload"].get("stop_reason")
    expected = "WS45_CONSTRUCTION_COMPLETE" if record["execution_entry_mode"] == "NATURAL_GAME_START" else "WS40_CONSTRUCTION_COMPLETE"
    if stop != expected:
        raise AssertionError(f"provider controlled stop mismatch {record['fixture_id']}: expected={expected} actual={stop}")
    return {"created": created["payload"]["snapshot"], "raw": raw, "result": result["payload"]["snapshot"], "messages": messages}


def counters(v: dict[str, Any] | None) -> dict[str, int]:
    return {str(k).lower(): int(n) for k, n in (v or {}).items() if int(n) != 0}


def normalize_players_state(record: dict[str, Any], evidence: dict[str, Any]) -> list[dict[str, Any]]:
    raw = evidence["raw"]
    got = {p["player_id"]: p for p in raw.get("players") or []}
    initial = evidence["created"].get("players") or []
    if len(initial) != len(record["players"]):
        raise AssertionError("initial native player count mismatch")
    out = []
    for i, shape in enumerate(record["players"]):
        pid = shape["player_id"]
        p = got[pid]
        out.append({
            "eliminated": not bool(p["in_game"]),
            "life": int(p["life"]),
            "lost": bool(p["lost"]),
            "player_id": pid,
            "poison": int(p["poison"]),
            "seat": int(shape["seat"]),
            "starting_life": int(initial[i]["life"]),
        })
    return out


def natural_decks(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {d["player_id"]: d for d in raw.get("decks") or []}


def normalize_players_natural(record: dict[str, Any], evidence: dict[str, Any]) -> list[dict[str, Any]]:
    by = natural_decks(evidence["raw"])
    out = []
    for shape in record["players"]:
        pid = shape["player_id"]
        p = by[pid]
        out.append({
            "eliminated": not bool(p["in_game"]),
            "life": int(p["live_life"]),
            "lost": bool(p["lost"]),
            "player_id": pid,
            "poison": int(p["poison"]),
            "seat": int(shape["seat"]),
            "starting_life": int(p["registered_starting_life"]),
        })
    return out


def normalize_deck_natural(record: dict[str, Any], raw: dict[str, Any]) -> list[dict[str, Any]]:
    by = natural_decks(raw)
    channels = list((raw.get("rules_randomness") or {}).get("channels") or [])
    out = []
    for shape in record.get("deck_state") or []:
        pid = shape["player_id"]
        d = by[pid]
        if "library_template" in shape:
            entries = d["main_entries"]
            if len(entries) != 1:
                raise AssertionError(f"natural library template nonunique {pid}: {entries}")
            matching_channels = [x for x in channels if x.endswith(":" + pid)]
            if len(matching_channels) != 1:
                raise AssertionError(f"natural shuffle channel nonunique {pid}: {channels}")
            out.append({
                "commander_ids": list(shape["commander_ids"]),
                "library_template": dict(entries[0]),
                "opening_hand_size": int(d["hand_count"]),
                "player_id": pid,
                "shuffle_channel": matching_channels[0],
            })
        else:
            out.append({
                "commander": list(d["commander_entries"]),
                "exact_card_count": int(d["main_count"]) + int(d["commander_count"]),
                "main_deck": list(d["main_entries"]),
                "player_id": pid,
            })
    return out


def native_relations(obs: dict[str, Any]) -> list[dict[str, Any]]:
    return list(obs.get("multiple_commander_relations") or [])


def derive_partner(commander_id: str, relations: list[dict[str, Any]]) -> str:
    matches = [r for r in relations if commander_id in (r.get("commander_ids") or [])]
    if len(matches) != 1:
        raise AssertionError(f"native Partner relation nonunique for {commander_id}: {matches}")
    ids = list(matches[0]["commander_ids"])
    if len(ids) != 2:
        raise AssertionError("native Partner relation arity")
    return ids[1] if ids[0] == commander_id else ids[0]


def normalize_commander_state(record: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    obs = raw["ws45_observation"]
    rel = native_relations(obs)
    by = {c["commander_id"]: c for c in raw.get("commanders") or []}
    commanders = []
    for shape in record["commander_state"]["commanders"]:
        c = by[shape["commander_id"]]
        row = {
            "card_identity": c["name"], "commander_id": shape["commander_id"], "owner": c["owner"],
            "prior_command_zone_cast_count": int(c["cast_count"]), "zone": c["zone"],
        }
        if "partner_with" in shape:
            row["partner_with"] = derive_partner(shape["commander_id"], rel)
        commanders.append(row)
    dmg = {(d["source_commander_id"], d["damaged_player"]): int(d["combat_damage"]) for d in raw.get("commander_damage") or []}
    matrix = []
    for shape in record["commander_state"].get("commander_damage_matrix") or []:
        key = (shape["source_commander_id"], shape["damaged_player"])
        matrix.append({"combat_damage": dmg[key], "damaged_player": key[1], "source_commander_id": key[0]})
    return {"commander_damage_matrix": matrix, "commanders": commanders, "multiple_commander_relations": rel}


def normalize_commander_natural(record: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    decks = natural_decks(raw)
    commanders = []
    for shape in record["commander_state"]["commanders"]:
        pid = shape["owner"]
        choices = [c for c in decks[pid]["native_commanders"] if c["card_identity"] == shape["card_identity"]]
        if len(choices) != 1:
            raise AssertionError(f"natural commander native identity nonunique {shape['commander_id']}: {choices}")
        c = choices[0]
        row = {
            "card_identity": c["card_identity"], "commander_id": shape["commander_id"], "owner": c["owner"],
            "prior_command_zone_cast_count": int(c["cast_count"]), "zone": c["zone"],
        }
        if "partner_with" in shape:
            raise AssertionError("natural Partner relation not supported by current denominator")
        commanders.append(row)
    return {"commander_damage_matrix": [], "commanders": commanders, "multiple_commander_relations": []}


def shape_metadata(shape: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    for k in ("semantic_id", "card_lineage_id", "commander_id", "construction_notes"):
        if k in shape:
            row[k] = shape[k]
    return row


def normalize_objects_state(record: dict[str, Any], raw: dict[str, Any]) -> list[dict[str, Any]]:
    by = {o["semantic_id"]: o for o in raw.get("cards") or []}
    out = []
    for shape in record.get("semantic_objects") or []:
        g = by[shape["semantic_id"]]
        row = shape_metadata(shape, {
            "card_identity": g["card_identity"], "controller": g["controller"], "counters": counters(g.get("counters")),
            "face_down": bool(g["face_down"]), "owner": g["owner"], "tapped": bool(g["tapped"]), "zone": g["zone"],
        })
        if "attached_to" in shape:
            row["attached_to"] = g.get("attached_to")
        if "zone_position" in shape:
            row["zone_position"] = g.get("zone_position")
        if "controlled_since_turn_began" in shape:
            if bool(g.get("sick")):
                raise AssertionError("native card remains summoning sick despite controlled-since-turn-began semantic")
            row["controlled_since_turn_began"] = True
        out.append(row)
    return out


def normalize_objects_natural(record: dict[str, Any], raw: dict[str, Any]) -> list[dict[str, Any]]:
    decks = natural_decks(raw)
    out = []
    for shape in record.get("semantic_objects") or []:
        if not shape.get("commander_id"):
            raise AssertionError("natural semantic object lacks commander identity")
        choices = [c for c in decks[shape["owner"]]["native_commanders"] if c["card_identity"] == shape["card_identity"]]
        if len(choices) != 1:
            raise AssertionError(f"natural semantic commander nonunique {shape['semantic_id']}: {choices}")
        c = choices[0]
        row = shape_metadata(shape, {
            "card_identity": c["card_identity"], "controller": c["controller"], "counters": counters(c.get("counters")),
            "face_down": bool(c["face_down"]), "owner": c["owner"], "tapped": bool(c["tapped"]), "zone": c["zone"],
        })
        out.append(row)
    return out


def phase_pair(raw_phase: Any) -> tuple[str, str]:
    p = str(raw_phase or "").upper().replace(" ", "_")
    mapping = {
        "MAIN1": ("precombat_main", "main"), "MAIN2": ("postcombat_main", "main"),
        "UPKEEP": ("beginning", "upkeep"), "DRAW": ("beginning", "draw"),
        "COMBAT_DECLARE_ATTACKERS": ("combat", "declare_attackers"),
        "COMBAT_DECLARE_BLOCKERS": ("combat", "declare_blockers"),
        "COMBAT_DAMAGE": ("combat", "combat_damage"),
    }
    if p not in mapping:
        raise AssertionError("unmapped native phase " + repr(raw_phase))
    return mapping[p]


def normalize_temporal_state(raw: dict[str, Any]) -> dict[str, Any]:
    phase, step = phase_pair(raw.get("phase"))
    return {"active_player": raw["active_player"], "extra_turn_queue": [], "phase": phase, "priority_player": raw["priority_player"], "step": step, "turn_number": int(raw["turn"])}


def normalize_temporal_natural(record: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    if raw.get("natural_lifecycle") is not True or raw.get("provider_entry_mode") != "NATURAL_GAME_START":
        raise AssertionError("natural lifecycle checkpoint missing")
    active = raw.get("native_active_player")
    priority = raw.get("native_priority_player") or active
    if int(raw.get("native_turn", 0)) < 1 or not raw.get("native_phase"):
        raise AssertionError("natural first-turn lifecycle not reached")
    semantic_step = record["temporal_state"]["step"]
    if semantic_step not in {"game_start", "mulligan"}:
        raise AssertionError("unsupported natural semantic checkpoint " + semantic_step)
    if semantic_step == "mulligan" and not (raw.get("mulligan_trace") or []):
        raise AssertionError("mulligan semantic checkpoint lacks native mulligan trace")
    return {"active_player": active, "extra_turn_queue": [], "phase": "pregame", "priority_player": priority, "step": semantic_step, "turn_number": 0}


def normalize_combat(shape: Any, raw: dict[str, Any]) -> Any:
    if shape is None:
        return None
    g = raw.get("combat") or {}
    out: dict[str, Any] = {}
    if "attackers" in shape:
        out["attackers"] = dict(g.get("attackers") or {})
    if "blockers" in shape:
        out["blockers"] = dict(g.get("blockers") or {})
    if "eligible_attackers" in shape:
        out["eligible_attackers"] = list(g.get("eligible_attackers") or [])
    if "eligible_blockers" in shape:
        out["eligible_blockers"] = list(g.get("eligible_blockers") or [])
    if "unblocked_attackers" in shape or "unblocked" in shape:
        attackers = list((g.get("attackers") or {}).keys())
        blocked = set((g.get("blockers") or {}).values())
        unblocked = [sid for sid in attackers if sid not in blocked]
        if "unblocked_attackers" in shape:
            out["unblocked_attackers"] = unblocked
        if "unblocked" in shape:
            out["unblocked"] = unblocked
    return out


def normalize_stack(shape: list[dict[str, Any]], raw: dict[str, Any]) -> list[dict[str, Any]]:
    by = {s["source_semantic_id"]: s for s in raw.get("stack") or []}
    out = []
    for item in shape:
        g = by[item["source_semantic_id"]]
        if not g.get("native_stack_present"):
            raise AssertionError("native stack object absent " + item["source_semantic_id"])
        out.append({
            "cast_complete": bool(g["cast_complete"]), "controller": g["controller"], "costs_paid": bool(g["costs_paid"]),
            "modes": list(g.get("modes") or []), "source_semantic_id": item["source_semantic_id"], "targets": list(g.get("targets") or []),
        })
    return out


def normalize(record: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    raw = evidence["raw"]
    mode = raw.get("provider_entry_mode")
    if mode != record["execution_entry_mode"]:
        raise AssertionError(f"native entry mode mismatch {record['fixture_id']} {mode}")
    if mode == "NATURAL_GAME_START":
        return {
            "execution_entry_mode": mode,
            "players": normalize_players_natural(record, evidence),
            "deck_state": normalize_deck_natural(record, raw),
            "commander_state": normalize_commander_natural(record, raw),
            "semantic_objects": normalize_objects_natural(record, raw),
            "temporal_state": normalize_temporal_natural(record, raw),
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
    obs = raw["ws45_observation"]
    return {
        "execution_entry_mode": mode,
        "players": normalize_players_state(record, evidence),
        "deck_state": None,
        "commander_state": normalize_commander_state(record, raw),
        "semantic_objects": normalize_objects_state(record, raw),
        "temporal_state": normalize_temporal_state(raw),
        "knowledge_state": obs["knowledge_state"],
        "rules_randomness": obs["rules_randomness"],
        "combat_state": normalize_combat(record.get("combat_state"), raw),
        "stack_state": normalize_stack(record.get("stack_state") or [], raw),
        "continuous_rules_effects": None,
        "extra_turn_creation": obs["extra_turn_creation"],
        "elimination_trigger": obs["elimination_trigger"],
        "zone_move_event": obs["zone_move_event"],
        "setup_validation": obs["setup_validation"],
    }


def write_report(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--materialization", type=Path, required=True)
    ap.add_argument("--denominator", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    raw_bytes = a.materialization.read_bytes()
    if hashlib.sha256(raw_bytes).hexdigest() != WS44_FILE_SHA:
        raise SystemExit("immutable WS44 materialization file digest mismatch")
    doc = json.loads(raw_bytes)
    if doc["schema_version"] != WS44_SCHEMA or doc["canonical_bundle_digest"] != WS44_BUNDLE:
        raise SystemExit("immutable WS44 materialization identity mismatch")
    denom = json.loads(a.denominator.read_text())
    ids = list(denom["fixture_ids"])
    if len(ids) != 107 or len(set(ids)) != 107:
        raise SystemExit("WS44 provider denominator is not exact 107 unique IDs")
    by_id = {r["fixture_id"]: r for r in doc["records"]}
    records = [by_id[x] for x in ids]
    rows: list[dict[str, Any]] = []
    result: dict[str, Any] = {
        "schema_version": "commander-lab.ws45-forge-fresh-construction-107/1.0.0",
        "status": "IN_PROGRESS", "denominator": 107, "pass_count": 0,
        "historical_successor_credit_imported": 0, "construction_credit": "0/107", "behavior_credit": "0/107",
        "ws44": {"commit": WS44_COMMIT, "tree": WS44_TREE, "schema": WS44_SCHEMA, "bundle_digest": WS44_BUNDLE, "materialization_sha256": WS44_FILE_SHA},
        "forge": {"commit": FORGE_COMMIT, "tree": FORGE_TREE},
        "no_request_echo_authority": ["WS45_CHECKPOINT_19_STRICT_NO_REQUEST_ECHO_PASS", "NATURAL_LIFECYCLE_NO_ECHO_EXTENSION"],
        "normalization_policy": "Rules-state values from emitted native Forge state/typed observation only; request supplies immutable provider-neutral identity labels and field shape only.",
        "rows": rows,
    }
    for index, record in enumerate(records, 1):
        try:
            requested = projection(record)
            rd = digest(requested)
            if rd != record["requested_state_digest"]:
                raise AssertionError(f"frozen requested digest mismatch {rd} != {record['requested_state_digest']}")
            evidence = run_native(record)
            normalized = normalize(record, evidence)
            nd = digest(normalized)
            if normalized != requested or nd != rd:
                raise AssertionError("REQUESTED_NATIVE_STATE_MISMATCH:" + record["fixture_id"] + ":requested=" + canon(requested) + ":normalized=" + canon(normalized))
            row = {
                "index": index, "fixture_id": record["fixture_id"], "fixture_family": record["fixture_family"],
                "materialization_digest": record["materialization_digest"], "entry_mode": record["execution_entry_mode"],
                "requested_state_digest": rd, "normalized_constructed_state_digest": nd,
                "requested_native_state_equal": True, "construction_status": "PASS", "evidence_class": "RUNTIME_VERIFIED",
                "raw_native_snapshot_digest": digest(evidence["raw"]), "initial_native_snapshot_digest": digest(evidence["created"]),
                "forge_commit": FORGE_COMMIT, "forge_tree": FORGE_TREE,
            }
            rows.append(row)
            result["pass_count"] = len(rows)
            write_report(a.output, result)
            print(f"WS45 CONSTRUCTION {index:03d}/107 PASS {record['fixture_id']} {rd}", flush=True)
        except Exception as ex:
            rows.append({"index": index, "fixture_id": record["fixture_id"], "fixture_family": record["fixture_family"], "entry_mode": record["execution_entry_mode"], "construction_status": "FAIL", "error": str(ex)[:20000], "forge_commit": FORGE_COMMIT, "forge_tree": FORGE_TREE})
            result["status"] = "FAIL"
            result["failure_index"] = index
            result["failure_fixture_id"] = record["fixture_id"]
            result["pass_count"] = sum(1 for r in rows if r["construction_status"] == "PASS")
            write_report(a.output, result)
            print(f"WS45 CONSTRUCTION {index:03d}/107 FAIL {record['fixture_id']}: {ex}", flush=True)
            return 1
    counts = collections.Counter(r["fixture_family"] for r in rows)
    result.update({
        "status": "PASS", "pass_count": 107, "construction_credit": "107/107",
        "family_counts": dict(sorted(counts.items())),
        "hard_gate": "PASS",
    })
    write_report(a.output, result)
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
