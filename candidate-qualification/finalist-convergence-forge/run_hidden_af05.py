#!/usr/bin/env python3
"""Execute exact canonical HIDDEN_01/HIDDEN_02 against the isolated Forge JVM."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Any

PROTOCOL = "commander-lab.rules-service/1.1.0"
CONTRACT_VERSION = "commander-lab.semantic-fixture-materialization/1.0.1"
CONTRACT_COMMIT = "9a8b8f5f5961466514eae6103be2d227324a27a8"
CONTRACT_BUNDLE = "ad1ec6e4baa83be48c0bc07e0bde66c2f8c003af29e411bad0953558154dcfee"
FORGE_COMMIT = "1e604105f9e279331063824943b9222b6589f5d8"
FORGE_TREE = "994976e06aaf99b807646b60b1aa2ac9f7703df4"
HIDDEN_IDS = ("HIDDEN_01", "HIDDEN_02")
HONEY = "WS30_HONEY_P2_PRIVATE_7F3A"
FORBIDDEN_ACTOR_TOKENS = (
    HONEY,
    "Demonic Tutor",
    "Vampiric Tutor",
    "obj:hidden-hand",
    "obj:hidden-lib-0",
    "line:obj:hidden-hand",
    "line:obj:hidden-lib-0",
)


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def seat(player_id: str) -> int:
    return int(player_id[1:])


def requested_objects(record: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in record["semantic_objects"]:
        # Command-zone bootstrap objects are transport/bootstrap context rather than
        # part of the AF05 same-record hidden-information discriminator. XMage uses
        # the same normalization boundary.
        if item["zone"] == "command":
            continue
        row: dict[str, Any] = {
            "semantic_id": item["semantic_id"],
            "card_name": item["card_identity"],
            "owner_seat": seat(item["owner"]),
            "controller_seat": seat(item["controller"]),
            "zone": item["zone"],
            "tapped": bool(item.get("tapped", False)),
            "face_down": bool(item.get("face_down", False)),
        }
        if item["zone"] == "library":
            row["zone_position"] = int(item["zone_position"])
        rows.append(row)
    return sorted(rows, key=lambda row: row["semantic_id"])


def command() -> list[str]:
    raw = os.environ.get("COMMANDER_LAB_FORGE_PROVIDER_CMD")
    if not raw:
        raise RuntimeError("COMMANDER_LAB_FORGE_PROVIDER_CMD missing")
    return shlex.split(raw)


def field_player(observation: dict[str, Any], player_id: str) -> dict[str, Any]:
    matches = [p for p in observation["players"] if p["player_id"] == player_id]
    if len(matches) != 1:
        raise AssertionError(f"actor observation player mismatch {player_id}: {matches}")
    return matches[0]


def collect_object_ids(value: Any) -> list[str]:
    result: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "object_id" and isinstance(child, str):
                result.append(child)
            result.extend(collect_object_ids(child))
    elif isinstance(value, list):
        for child in value:
            result.extend(collect_object_ids(child))
    return result


def assert_actor_safe(path: str, value: Any) -> None:
    blob = canonical(value).casefold()
    for token in FORBIDDEN_ACTOR_TOKENS:
        if token.casefold() in blob:
            raise AssertionError(f"HIDDEN_INFORMATION_LEAK:{path}:{token}")
    for object_id in collect_object_ids(value):
        if not object_id.startswith("obj-"):
            raise AssertionError(f"NON_OPAQUE_ACTOR_OBJECT_ID:{path}:{object_id}")


def send(proc: subprocess.Popen[str], frame: dict[str, Any], option_id: str) -> None:
    assert proc.stdin is not None
    proc.stdin.write(
        json.dumps(
            {
                "protocol": PROTOCOL,
                "message_type": "SUBMIT_DECISION",
                "request_id": f"reply-{frame['payload']['decision_id']}",
                "session_id": frame.get("session_id"),
                "payload": {
                    "decision_id": frame["payload"]["decision_id"],
                    "option_id": option_id,
                },
            },
            separators=(",", ":"),
        )
        + "\n"
    )
    proc.stdin.flush()


def one_option(frame: dict[str, Any], kind: str) -> str:
    matches = [o for o in frame["payload"]["options"] if o.get("kind") == kind]
    if len(matches) != 1:
        raise AssertionError(f"semantic option not unique {kind}: {frame['payload']['options']}")
    return str(matches[0]["option_id"])


def split_names(value: Any) -> list[str]:
    if not isinstance(value, str) or not value:
        return []
    return value.split("|")


def verify_setup(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    if snapshot.get("turn") != 1 or snapshot.get("phase") != "MAIN1":
        raise AssertionError(f"AF05 temporal setup mismatch: {snapshot}")
    if snapshot.get("active_actor") != "seat-1" or snapshot.get("priority_actor") != "seat-1":
        raise AssertionError(f"AF05 active/priority mismatch: {snapshot}")
    by_id = {p["player_id"]: p for p in snapshot["players"]}
    if set(by_id) != {"P1", "P2", "P3", "P4"}:
        raise AssertionError(f"AF05 player set mismatch: {by_id}")
    if any(p["life"] != 40 for p in by_id.values()):
        raise AssertionError(f"AF05 life mismatch: {by_id}")
    if split_names(by_id["P2"].get("hand_names")) != ["Demonic Tutor"]:
        raise AssertionError(f"AF05 P2 hand setup mismatch: {by_id['P2']}")
    if split_names(by_id["P2"].get("library_names")) != ["Vampiric Tutor"]:
        raise AssertionError(f"AF05 P2 library setup mismatch: {by_id['P2']}")
    if split_names(by_id["P2"].get("exile_names")) != ["Sol Ring"]:
        raise AssertionError(f"AF05 P2 exile setup mismatch: {by_id['P2']}")
    for player_id in ("P1", "P3", "P4"):
        player = by_id[player_id]
        if split_names(player.get("hand_names")):
            raise AssertionError(f"AF05 unexpected {player_id} hand state: {player}")
        if split_names(player.get("library_names")):
            raise AssertionError(f"AF05 unexpected {player_id} library state: {player}")
        if split_names(player.get("exile_names")):
            raise AssertionError(f"AF05 unexpected {player_id} exile state: {player}")
    p1_battlefield = by_id["P1"].get("battlefield", [])
    p1_fd = [c for c in p1_battlefield if c.get("face_down")]
    if len(p1_battlefield) != 1 or len(p1_fd) != 1 or p1_fd[0].get("name") != "Grizzly Bears":
        raise AssertionError(f"AF05 face-down setup mismatch: {p1_battlefield}")
    if any(by_id[p].get("battlefield") for p in ("P2", "P3", "P4")):
        raise AssertionError(f"AF05 unexpected opponent battlefield state: {by_id}")

    # Reconstruct the provider-neutral semantic state from the actually observed
    # privileged Forge state. This is deliberately not copied from the request.
    native = [
        {
            "semantic_id": "obj:facedown",
            "card_name": p1_fd[0]["name"],
            "owner_seat": 1,
            "controller_seat": 1,
            "zone": "battlefield",
            "tapped": False,
            "face_down": bool(p1_fd[0]["face_down"]),
        },
        {
            "semantic_id": "obj:hidden-hand",
            "card_name": split_names(by_id["P2"]["hand_names"])[0],
            "owner_seat": 2,
            "controller_seat": 2,
            "zone": "hand",
            "tapped": False,
            "face_down": False,
        },
        {
            "semantic_id": "obj:hidden-lib-0",
            "card_name": split_names(by_id["P2"]["library_names"])[0],
            "owner_seat": 2,
            "controller_seat": 2,
            "zone": "library",
            "tapped": False,
            "face_down": False,
            "zone_position": 0,
        },
        {
            "semantic_id": "obj:public-exile",
            "card_name": split_names(by_id["P2"]["exile_names"])[0],
            "owner_seat": 2,
            "controller_seat": 2,
            "zone": "exile",
            "tapped": False,
            "face_down": False,
        },
    ]
    return sorted(native, key=lambda row: row["semantic_id"])


def verify_actor(observation: dict[str, Any]) -> dict[str, Any]:
    p1 = field_player(observation, "P1")
    p2 = field_player(observation, "P2")
    if p2.get("hand_count") != 1 or p2.get("library_count") != 1:
        raise AssertionError(f"AF05 permitted counts mismatch: {p2}")
    if "hand" in p2:
        raise AssertionError(f"HIDDEN_01 opponent hand identities exposed: {p2['hand']}")
    if p2.get("known_library") not in ([], None):
        raise AssertionError(f"HIDDEN_02 opponent library identities/order exposed: {p2['known_library']}")
    exile = p2.get("exile") or []
    if len(exile) != 1 or exile[0].get("name") != "Sol Ring":
        raise AssertionError(f"public exile projection mismatch: {exile}")
    face_down = [card for card in (p1.get("battlefield") or []) if card.get("face_down")]
    if len(face_down) != 1 or face_down[0].get("name") != "Grizzly Bears":
        raise AssertionError(f"controller face-down visibility mismatch: {face_down}")
    assert_actor_safe("observation", observation)
    return {
        "P2_hand_count": 1,
        "P2_library_count": 1,
        "public_exile": ["Sol Ring"],
        "controller_face_down_visible": ["Grizzly Bears"],
        "actor_object_ids_opaque": True,
    }


def run_one(record: dict[str, Any]) -> dict[str, Any]:
    env = os.environ.copy()
    env["COMMANDER_LAB_FORGE_PLAYER_COUNT"] = "4"
    env["COMMANDER_LAB_FORGE_RULES_SEED"] = str(record["rules_randomness"]["rules_seed"])
    env["COMMANDER_LAB_FORGE_FIXTURE_ID"] = record["fixture_id"]
    env["COMMANDER_LAB_FORGE_STOP_AFTER_PRIORITY"] = "128"
    setup: dict[str, Any] | None = None
    native_state: list[dict[str, Any]] | None = None
    actor_evidence: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    after_setup = False

    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as stderr:
        proc = subprocess.Popen(
            command(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr,
            text=True,
            env=env,
            bufsize=1,
        )
        assert proc.stdin is not None and proc.stdout is not None
        proc.stdin.write(
            json.dumps(
                {
                    "protocol": PROTOCOL,
                    "message_type": "CREATE_SESSION",
                    "request_id": f"forge-af05-{record['fixture_id']}",
                    "payload": {"fixture_id": record["fixture_id"]},
                },
                separators=(",", ":"),
            )
            + "\n"
        )
        proc.stdin.flush()
        for _ in range(256):
            line = proc.stdout.readline()
            if not line:
                break
            message = json.loads(line)
            mtype = message.get("message_type")
            if mtype == "SESSION_CREATED":
                continue
            if mtype == "QUALIFICATION_STATE":
                setup = message["payload"]["snapshot"]
                native_state = verify_setup(setup)
                after_setup = True
                continue
            if mtype == "DECISION_FRAME":
                if not after_setup:
                    decision = message["payload"]["decision_kind"]
                    if decision == "chooseStartingPlayer":
                        send(proc, message, one_option(message, "PLAYER:seat-1"))
                    elif decision == "mulliganKeepHand":
                        send(proc, message, one_option(message, "KEEP"))
                    else:
                        raise AssertionError(f"unexpected bootstrap decision: {message}")
                    continue
                if message.get("actor_id") != "seat-1" or message["payload"].get("decision_kind") != "priority":
                    raise AssertionError(f"AF05 first canonical decision mismatch: {message}")
                observation = message["payload"].get("observation")
                if not isinstance(observation, dict):
                    raise AssertionError(f"AF05 actor observation missing: {message}")
                actor_evidence = verify_actor(observation)
                assert_actor_safe("decision_frame", message)
                send(proc, message, one_option(message, "PASS"))
                continue
            if mtype == "SESSION_RESULT":
                result = message
                break
            raise AssertionError(f"unexpected provider message: {message}")
        if proc.stdin:
            proc.stdin.close()
        rc = proc.wait(timeout=30)
        stderr.seek(0)
        error_text = stderr.read()
    if rc != 0:
        raise RuntimeError(f"Forge AF05 provider exit {rc}: {error_text[-5000:]}")
    if setup is None or native_state is None or actor_evidence is None or result is None:
        raise AssertionError("AF05 runtime evidence incomplete")
    if result["payload"].get("stop_reason") != "FINALIST_AF05_TERMINAL":
        raise AssertionError(f"AF05 stop reason mismatch: {result['payload'].get('stop_reason')}")

    requested = requested_objects(record)
    requested_digest = sha(requested)
    native_digest = sha(native_state)
    if native_state != requested or native_digest != requested_digest:
        raise AssertionError(
            f"REQUESTED_NATIVE_STATE_MISMATCH:requested={requested}:native={native_state}"
        )
    return {
        "fixture_id": record["fixture_id"],
        "status": "PASS",
        "evidence_class": "RUNTIME_VERIFIED",
        "record_digest": record["materialization_digest"],
        "requested_semantic_state_digest": requested_digest,
        "normalized_native_constructed_state_digest": native_digest,
        "requested_native_state_equal": True,
        "native_state": native_state,
        "raw_native_constructed_state": setup,
        "raw_native_constructed_state_digest": sha(setup),
        "actor_projection": actor_evidence,
        "channels_runtime_audited": ["state", "option_id", "option_label", "option_metadata"],
        "channels_centrally_guarded": [
            "source_metadata",
            "ability_metadata",
            "pile_metadata",
            "prompt",
            "context",
            "event",
            "transcript",
            "log",
        ],
        "forbidden_tokens_absent": list(FORBIDDEN_ACTOR_TOKENS),
        "expected_event_normalization": f"knowledge_projection:{record['fixture_id']}:P1",
        "terminal_postcondition_result": "PASS",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--contract", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    payload = json.loads(args.contract.read_text(encoding="utf-8"))
    if payload.get("schema_version") != CONTRACT_VERSION:
        raise SystemExit("CONTRACT_SCHEMA_MISMATCH")
    if payload.get("canonical_bundle_digest") != CONTRACT_BUNDLE:
        raise SystemExit("CONTRACT_BUNDLE_MISMATCH")
    by_id = {row["fixture_id"]: row for row in payload["records"]}
    rows = []
    for fixture_id in HIDDEN_IDS:
        record = by_id[fixture_id]
        try:
            rows.append(run_one(record))
        except Exception as exc:
            rows.append(
                {
                    "fixture_id": fixture_id,
                    "status": "FAIL",
                    "evidence_class": "RUNTIME_VERIFIED",
                    "record_digest": record["materialization_digest"],
                    "failure_signature": f"{type(exc).__name__}:{exc}",
                    "terminal_postcondition_result": "FAIL",
                }
            )
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    out = {
        "schema_version": "commander-lab.forge-finalist-af05-hidden/1.0.0",
        "contract_commit": CONTRACT_COMMIT,
        "contract_bundle_digest": CONTRACT_BUNDLE,
        "candidate_commit": os.environ.get(
            "COMMANDER_LAB_CONVERGENCE_BRANCH_HEAD", os.environ.get("GITHUB_SHA", "LOCAL")
        ),
        "forge_commit": FORGE_COMMIT,
        "forge_tree": FORGE_TREE,
        "process_boundary": "SEPARATE_GPL_JVM",
        "counts": counts,
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"counts": counts, "output": str(args.output)}, sort_keys=True))
    return 0 if counts == {"PASS": 2} else 1


if __name__ == "__main__":
    raise SystemExit(main())
