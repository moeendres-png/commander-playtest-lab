#!/usr/bin/env python3
from __future__ import annotations

import argparse, base64, hashlib, json, os, shlex, subprocess, tempfile, urllib.parse
from pathlib import Path
from typing import Any

PROTOCOL = "commander-lab.rules-service/1.1.0"
WS44_SCHEMA = "commander-lab.semantic-fixture-materialization/1.0.4"
WS44_BUNDLE = "77b911195525c2fe8aff37f6c9573e5772f358b25646d0be5919314ed5e23b54"
WS44_FILE_SHA = "9b370244e4e5df3132e6e9a3d2b70ad641a5a6023fc7c86832931340d24bfa35"
FORGE_COMMIT = "66caae16015bd403bc0a52fa6689afb5508f74d0"
FORGE_TREE = "40fc8f29ce4de31a964972461db2b48b4221e07f"


def canon(v: Any) -> str:
    return json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(v: Any) -> str:
    return hashlib.sha256(canon(v).encode()).hexdigest()


def enc(v: Any) -> str:
    return urllib.parse.quote("" if v is None else str(v), safe="")


def b64_text(s: str) -> str:
    return base64.b64encode(s.encode()).decode()


def b64_rows(rows: list[list[str]]) -> str:
    return b64_text("\n".join("\t".join(r) for r in rows))


def _presence(v: dict[str, Any], k: str) -> str:
    return str(k in v).lower()


def _list(v: Any) -> str:
    return enc("\u001f".join(str(x) for x in (v or [])))


def knowledge_env(record: dict[str, Any]) -> dict[str, str]:
    ks = record.get("knowledge_state") or {"channel_policy": "ACTOR_ENTITLED_ONLY", "viewer_states": []}
    viewers = ks.get("viewer_states") or []
    vr: list[list[str]] = []
    fr: list[list[str]] = []
    for v in viewers:
        viewer = v["viewer"]
        vr.append([
            enc(viewer), _presence(v, "channels_under_test"), _list(v.get("channels_under_test")),
            _presence(v, "honey_sentinels"), _list(v.get("honey_sentinels")), _list(v.get("invalidation_conditions")),
            _presence(v, "obligation"), enc(v.get("obligation")), _presence(v, "ordered_known_information"),
            _list(v.get("ordered_known_information")), _presence(v, "permitted_public_metadata"),
            _list(v.get("permitted_public_metadata")), _presence(v, "prohibited_metadata"), _list(v.get("prohibited_metadata")),
        ])
        for sid in v.get("known_object_identities") or []:
            fr.append(["KNOWN_OBJECT_IDENTITY", enc(viewer), enc(sid), "", "", "", "", "", "", "", "", "", "", "", ""])
        for x in v.get("known_library_ranges") or []:
            fr.append(["KNOWN_LIBRARY_RANGE", enc(viewer), "", enc(x.get("player")), "", "", "",
                       "" if x.get("start") is None else str(x["start"]),
                       "" if x.get("count") is None else str(x["count"]),
                       "" if x.get("ordered") is None else str(bool(x["ordered"])).lower(), "", enc(x.get("before_event")), "", "", ""])
        for x in v.get("face_down_look_permissions") or []:
            fr.append(["FACE_DOWN_LOOK_PERMISSION", enc(viewer), enc(x.get("object")), "", enc(x.get("zone")), enc(x.get("permission")),
                       enc(x.get("scope")), "", "", "",
                       "" if x.get("persists_while_in_same_exile_object") is None else str(bool(x["persists_while_in_same_exile_object"])).lower(),
                       "", "", "", enc(x.get("viewer") or viewer)])
        for x in v.get("temporary_permissions") or []:
            fr.append(["TEMPORARY_PERMISSION", enc(viewer), enc(x.get("object")), enc(x.get("player")), enc(x.get("zone")), enc(x.get("permission")),
                       enc(x.get("scope")), "", "", "",
                       "" if x.get("persists_while_in_same_exile_object") is None else str(bool(x["persists_while_in_same_exile_object"])).lower(),
                       enc(x.get("before_event")), enc(x.get("controlled_player")), enc(x.get("controller")), enc(x.get("viewer") or viewer)])
    return {
        "COMMANDER_LAB_WS45_KNOWLEDGE_CHANNEL_POLICY_B64": b64_text(str(ks.get("channel_policy", "ACTOR_ENTITLED_ONLY"))),
        "COMMANDER_LAB_WS45_KNOWLEDGE_VIEWER_ROWS_B64": b64_rows(vr),
        "COMMANDER_LAB_WS45_KNOWLEDGE_FACT_ROWS_B64": b64_rows(fr),
    }


def randomness_env(record: dict[str, Any]) -> dict[str, str]:
    rr = record.get("rules_randomness") or {}
    fixed = rr.get("rules_seed")
    binding = rr.get("seed_binding")
    effective = int(fixed if fixed is not None else 424242)
    rows = [
        ["fixed_seed", "" if fixed is None else str(fixed)],
        ["seed_binding", enc(binding)],
        ["effective_seed", str(effective)],
        ["pilot_prohibited", str(bool(rr.get("pilot_randomness_prohibited", True))).lower()],
        ["native_calls", str(bool(rr.get("provider_native_rng_calls_recorded", False))).lower()],
    ]
    rows += [["channel", enc(x)] for x in (rr.get("channels") or [])]
    for d in rr.get("predetermined_semantic_draws") or []:
        rows.append(["draw", enc(d["channel"]), enc(d["operation"]), enc(d["result"])])
    return {
        "COMMANDER_LAB_FORGE_RULES_SEED": str(effective),
        "COMMANDER_LAB_WS45_RANDOMNESS_ROWS_B64": b64_rows(rows),
        "COMMANDER_LAB_WS45_RANDOMNESS_HAS_FIXED_SEED": "1" if "rules_seed" in rr else "0",
        "COMMANDER_LAB_WS45_RANDOMNESS_HAS_SEED_BINDING": "1" if "seed_binding" in rr else "0",
        "COMMANDER_LAB_WS45_RANDOMNESS_HAS_PREDETERMINED": "1" if "predetermined_semantic_draws" in rr else "0",
        "COMMANDER_LAB_WS45_RANDOMNESS_HAS_NATIVE_CALLS": "1" if "provider_native_rng_calls_recorded" in rr else "0",
    }


def env_for(record: dict[str, Any]) -> dict[str, str]:
    assert record["execution_entry_mode"] == "NATURAL_GAME_START"
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
    e.update(knowledge_env(record))
    e.update(randomness_env(record))
    return e


def command() -> list[str]:
    raw = os.environ.get("COMMANDER_LAB_FORGE_PROVIDER_CMD")
    if not raw:
        raise RuntimeError("COMMANDER_LAB_FORGE_PROVIDER_CMD missing")
    return shlex.split(raw)


def one_option(frame: dict[str, Any], kind: str) -> str:
    xs = [o for o in frame["payload"]["options"] if o.get("kind") == kind]
    if len(xs) != 1:
        raise AssertionError((kind, xs))
    return str(xs[0]["option_id"])


def submit(proc: subprocess.Popen[str], frame: dict[str, Any], oid: str) -> None:
    assert proc.stdin is not None
    proc.stdin.write(json.dumps({
        "protocol": PROTOCOL, "message_type": "SUBMIT_DECISION",
        "request_id": "reply-" + frame["payload"]["decision_id"], "session_id": frame.get("session_id"),
        "payload": {"decision_id": frame["payload"]["decision_id"], "option_id": oid},
    }, separators=(",", ":")) + "\n")
    proc.stdin.flush()


def run(record: dict[str, Any], overrides: dict[str, str] | None = None) -> dict[str, Any]:
    e = env_for(record)
    e.update(overrides or {})
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as err:
        p = subprocess.Popen(command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err, text=True, env=e, bufsize=1)
        assert p.stdin is not None and p.stdout is not None
        p.stdin.write(json.dumps({"protocol": PROTOCOL, "message_type": "CREATE_SESSION", "request_id": "ws45-natural-noecho", "payload": {"fixture_id": record["fixture_id"]}}, separators=(",", ":")) + "\n")
        p.stdin.flush()
        raw = None
        created = None
        result = None
        messages: list[str] = []
        for _ in range(512):
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
                    submit(p, m, one_option(m, "PLAYER:seat-1"))
                    continue
                if kind == "mulliganKeepHand":
                    submit(p, m, one_option(m, "KEEP"))
                    continue
                raise AssertionError("unexpected natural decision " + kind)
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
    return {"rc": rc, "raw": raw, "created": created, "result": result, "messages": messages, "stderr_tail": stderr[-4000:]}


def successful(x: dict[str, Any]) -> bool:
    return x["rc"] == 0 and x["raw"] is not None and x["created"] is not None and x["result"] is not None and x["result"]["payload"].get("stop_reason") == "WS45_CONSTRUCTION_COMPLETE"


def validate_native_surface(x: dict[str, Any], player_count: int) -> None:
    if not successful(x):
        raise AssertionError(f"natural lifecycle failed: {x}")
    raw = x["raw"]
    if raw.get("natural_lifecycle") is not True or raw.get("provider_entry_mode") != "NATURAL_GAME_START":
        raise AssertionError("natural lifecycle identity missing")
    if raw.get("player_count") != player_count or raw.get("rules_commander") is not True:
        raise AssertionError("natural native player/Commander surface mismatch")
    decks = raw.get("decks") or []
    if len(decks) != player_count:
        raise AssertionError("natural deck surface count mismatch")
    for i, d in enumerate(decks, 1):
        required = {"player_id", "main_count", "main_entries", "commander_count", "commander_entries", "registered_starting_life", "live_life", "poison", "lost", "in_game", "hand_count", "library_count", "native_commander_count", "native_commanders"}
        missing = sorted(required - set(d))
        if missing:
            raise AssertionError(f"natural deck surface missing P{i}: {missing}")
        if d["player_id"] != f"P{i}" or d["main_count"] != 99 or d["main_entries"] != [{"card_identity": "Mountain", "count": 99}]:
            raise AssertionError(f"native main deck mismatch {d}")
        if d["commander_count"] != 1 or d["commander_entries"] != [{"card_identity": "Rograkh, Son of Rohgahh", "count": 1}]:
            raise AssertionError(f"native commander deck mismatch {d}")
        if d["registered_starting_life"] != 40 or d["live_life"] != 40 or d["poison"] != 0 or d["lost"] or not d["in_game"]:
            raise AssertionError(f"native natural player state mismatch {d}")
        if d["native_commander_count"] != 1 or len(d["native_commanders"]) != 1:
            raise AssertionError(f"native natural commander object missing {d}")
        c = d["native_commanders"][0]
        if c["card_identity"] != "Rograkh, Son of Rohgahh" or c["owner"] != f"P{i}" or c["controller"] != f"P{i}" or c["zone"] != "command" or c["cast_count"] != 0 or c["tapped"] or c["face_down"] or c["counters"] != {}:
            raise AssertionError(f"native natural commander state mismatch {c}")
    if not isinstance(raw.get("knowledge_state"), dict) or not isinstance(raw.get("rules_randomness"), dict) or not isinstance(raw.get("setup_validation"), dict):
        raise AssertionError("strict natural policy surfaces missing")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--materialization", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    raw_bytes = a.materialization.read_bytes()
    if hashlib.sha256(raw_bytes).hexdigest() != WS44_FILE_SHA:
        raise SystemExit("WS44 materialization digest mismatch")
    doc = json.loads(raw_bytes)
    if doc["schema_version"] != WS44_SCHEMA or doc["canonical_bundle_digest"] != WS44_BUNDLE:
        raise SystemExit("WS44 identity mismatch")
    record = next(r for r in doc["records"] if r["fixture_id"] == "PLAYER_COUNT_2P")
    baseline = run(record)
    validate_native_surface(baseline, 2)
    canary = run(record, {"COMMANDER_LAB_WS45_NATURAL_CANONICAL_B64": b64_text('{"players":[{"life":-999}],"deck_state":"REQUEST_ECHO_CANARY"}')})
    validate_native_surface(canary, 2)
    if baseline["raw"] != canary["raw"]:
        raise AssertionError("REQUEST_ECHO_DETECTED:NATURAL_LIFECYCLE")
    result = {
        "schema_version": "commander-lab.ws45-natural-no-request-echo-extension/1.0.0",
        "status": "PASS",
        "strict_no_request_echo_extension": "PASS",
        "fixture_id": record["fixture_id"],
        "forge": {"commit": FORGE_COMMIT, "tree": FORGE_TREE},
        "ws44": {"schema": WS44_SCHEMA, "bundle_digest": WS44_BUNDLE, "materialization_sha256": WS44_FILE_SHA},
        "historical_successor_credit_imported": 0,
        "construction_credit": "0/107",
        "behavior_credit": "0/107",
        "baseline_raw_digest": digest(baseline["raw"]),
        "canary_raw_digest": digest(canary["raw"]),
        "proof": {
            "natural_output_comes_from_registered_deck_player_and_live_commander_objects": True,
            "request_echo_canary_ignored": True,
            "complete_natural_player_readback": True,
            "complete_natural_deck_composition_readback": True,
            "complete_natural_commander_object_readback": True,
            "knowledge_randomness_setup_surfaces_present": True,
        },
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
