#!/usr/bin/env python3
"""Execute exact canonical HIDDEN_01/HIDDEN_02 through the XMage provider.

The Rules Core and XmageKnowledgeLedger remain authoritative. This harness only
constructs the frozen qualification state, verifies privileged native setup,
and audits actor-visible output against the frozen AF05 obligations.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
WS26 = HERE.parents[0] / "ws26-xmage"
sys.path.insert(0, str(WS26))
import run_ws26_gate as gate  # noqa: E402

CONTRACT_VERSION = "commander-lab.semantic-fixture-materialization/1.0.1"
CONTRACT_BUNDLE = "ad1ec6e4baa83be48c0bc07e0bde66c2f8c003af29e411bad0953558154dcfee"
CONTRACT_COMMIT = "9a8b8f5f5961466514eae6103be2d227324a27a8"
SCHEMA = "xmage-qualification-scenario/1.1.0"
HIDDEN_IDS = ("HIDDEN_01", "HIDDEN_02")
COMMANDER = "Rograkh, Son of Rohgahh"
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
    import hashlib

    return hashlib.sha256(canonical(value).encode()).hexdigest()


def seat(player_id: str) -> int:
    if not player_id.startswith("P") or not player_id[1:].isdigit():
        raise ValueError(f"invalid canonical player id: {player_id}")
    return int(player_id[1:])


def deck_payload(fixture_id: str, player_seat: int) -> dict[str, Any]:
    body: dict[str, Any] = {
        "deck_id": f"fc-{fixture_id.lower()}-p{player_seat}",
        "mainboard": ["Mountain"] * 99,
        "commander_names": [COMMANDER],
        "sideboard": [],
    }
    body["deck_hash"] = sha(body)
    return body


def scenario(record: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    players: list[dict[str, Any]] = []
    objects = sorted(record["semantic_objects"], key=lambda item: item["semantic_id"])
    player_count = len(record["players"])
    for number in range(1, player_count + 1):
        player_id = f"P{number}"
        zones: dict[str, list[dict[str, Any]]] = {
            "hand": [], "library": [], "graveyard": [], "exile": [], "battlefield": []
        }
        commanders = []
        for item in objects:
            if item["owner"] != player_id:
                continue
            if item["zone"] == "command":
                commanders.append(item["card_identity"])
                continue
            entry: dict[str, Any] = {
                "semantic_id": item["semantic_id"],
                "card_name": item["card_identity"],
                "tapped": bool(item.get("tapped", False)),
                "controller_seat": seat(item["controller"]),
                "face": "main",
                "face_down": bool(item.get("face_down", False)),
            }
            zones[item["zone"]].append(entry)
        if commanders != [COMMANDER]:
            raise AssertionError(f"commander mismatch for {player_id}: {commanders}")
        for zone in zones:
            zones[zone].sort(key=lambda item: item["semantic_id"])
        life = next(p["life"] for p in record["players"] if p["player_id"] == player_id)
        players.append(
            {
                "seat": number,
                "life": life,
                "commander_names": commanders,
                "zones": zones,
            }
        )
    temporal = record["temporal_state"]
    payload = {
        "schema_version": SCHEMA,
        "scenario_id": f"FINALIST-{record['fixture_id']}",
        "execution_entry_mode": "NATIVE_STATE_LOAD",
        "seed": record["rules_randomness"]["rules_seed"],
        "starting_player_seat": 1,
        "temporal_state": {
            "turn_number": temporal["turn_number"],
            "active_player": temporal["active_player"],
            "priority_player": temporal["priority_player"],
            "phase": temporal["phase"],
            "step": temporal["step"],
        },
        "players": players,
    }
    return [deck_payload(record["fixture_id"], i) for i in range(1, player_count + 1)], payload


def requested_objects(record: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in record["semantic_objects"]:
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


def native_objects(state: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in state["scenario_objects"]:
        zone = "exile" if item["zone"] == "exiled" else item["zone"]
        row: dict[str, Any] = {
            "semantic_id": item["semantic_id"],
            "card_name": item["card_name"],
            "owner_seat": int(item["owner_seat"]),
            "controller_seat": int(item.get("controller_seat", item["owner_seat"])),
            "zone": zone,
            "tapped": bool(item.get("tapped", False)),
            "face_down": bool(item.get("face_down", False)),
        }
        if zone == "library":
            if "zone_position" not in item:
                raise AssertionError(f"native library position missing: {item}")
            row["zone_position"] = int(item["zone_position"])
        rows.append(row)
    return sorted(rows, key=lambda row: row["semantic_id"])


def player(observation: dict[str, Any], player_id: str) -> dict[str, Any]:
    matches = [p for p in observation["players"] if p["player_id"] == player_id]
    if len(matches) != 1:
        raise AssertionError(f"player projection mismatch for {player_id}: {matches}")
    return matches[0]


def collect_object_ids(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "object_id" and isinstance(child, str):
                found.append(child)
            found.extend(collect_object_ids(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(collect_object_ids(child))
    return found


def assert_no_forbidden(path: str, value: Any) -> None:
    blob = canonical(value).casefold()
    for token in FORBIDDEN_ACTOR_TOKENS:
        if token.casefold() in blob:
            raise AssertionError(f"HIDDEN_INFORMATION_LEAK:{path}:{token}")


def assert_opaque_ids(path: str, value: Any) -> None:
    ids = collect_object_ids(value)
    for object_id in ids:
        if not object_id.startswith("obj-"):
            raise AssertionError(f"NON_OPAQUE_ACTOR_OBJECT_ID:{path}:{object_id}")


def verify_actor_projection(fixture_id: str, observation: dict[str, Any]) -> dict[str, Any]:
    p1 = player(observation, "P1")
    p2 = player(observation, "P2")
    if p2["hand_count"] != 1 or p2["library_count"] != 1:
        raise AssertionError(
            f"hidden counts mismatch: hand={p2['hand_count']} library={p2['library_count']}"
        )
    if "hand" in p2:
        raise AssertionError("HIDDEN_01 opponent hand identity collection was exposed")
    if p2.get("known_library") not in ([], None):
        raise AssertionError(f"HIDDEN_02 opponent library knowledge exposed: {p2['known_library']}")
    if p2.get("remembered_library_composition") not in ([], None):
        raise AssertionError(
            "HIDDEN_02 opponent remembered library composition was exposed"
        )
    exile = p2.get("exile") or []
    if len(exile) != 1 or exile[0].get("name") != "Sol Ring":
        raise AssertionError(f"public exile identity not preserved: {exile}")
    battlefield = p1.get("battlefield") or []
    face_down = [item for item in battlefield if item.get("face_down")]
    if len(face_down) != 1 or face_down[0].get("name") != "Grizzly Bears":
        raise AssertionError(f"controller face-down entitlement mismatch: {face_down}")
    assert_no_forbidden(f"{fixture_id}:observation", observation)
    assert_opaque_ids(f"{fixture_id}:observation", observation)
    return {
        "P2_hand_count": p2["hand_count"],
        "P2_library_count": p2["library_count"],
        "public_exile": [item.get("name") for item in exile],
        "controller_face_down_visible": [item.get("name") for item in face_down],
        "actor_object_ids_opaque": True,
    }


def run_one(record: dict[str, Any]) -> dict[str, Any]:
    decks, payload = scenario(record)
    with gate._RawFullGameClient(gate.command(), request_timeout_seconds=240.0) as client:
        client.request("start_engine")
        handles = gate.import_decks(client, decks)
        client.request(
            "create_full_game",
            {
                "game_id": payload["scenario_id"],
                "deck_handles": handles,
                "starting_player_seat": 0,
                "starting_life": 40,
                "seed": record["rules_randomness"]["rules_seed"],
            },
        )
        configured = client.request("configure_qualification_scenario", {"scenario": payload})
        if configured.get("execution_entry_mode") != "NATIVE_STATE_LOAD":
            raise AssertionError(f"execution entry mismatch: {configured}")
        client.request("start_full_game")
        status = client.request("get_full_game_decision")
        pending = status.get("decision")
        if not isinstance(pending, dict) or pending.get("decision_class") != "priority":
            raise AssertionError(f"hidden state did not reach native P1 priority: {status}")
        if status.get("turn") != 1 or status.get("active_player_seat") != 1 or status.get("priority_player_seat") != 1:
            raise AssertionError(f"temporal state mismatch: {status}")

        privileged = client.request("get_qualification_state")["semantic_state"]
        requested = requested_objects(record)
        constructed = native_objects(privileged)
        if requested != constructed:
            raise AssertionError(
                f"requested/native hidden state mismatch: requested={requested} native={constructed}"
            )

        actor_payload = client.request(
            "get_full_game_observation", {"viewer_seat": 0, "decision_subject_seat": 0}
        )
        observation = actor_payload["observation"]
        actor_result = verify_actor_projection(record["fixture_id"], observation)
        assert_no_forbidden(f"{record['fixture_id']}:decision", pending)
        assert_opaque_ids(f"{record['fixture_id']}:decision", pending)

        result = client.request("get_full_game_result")
        transcript = result.get("durable_transcript") or []
        assert_no_forbidden(f"{record['fixture_id']}:transcript", transcript)
        assert_opaque_ids(f"{record['fixture_id']}:transcript", transcript)

    commanders = {
        p["player_id"]: [card.get("name") for card in p.get("command", [])]
        for p in observation["players"]
    }
    if commanders != {f"P{i}": [COMMANDER] for i in range(1, 5)}:
        raise AssertionError(f"commander projection mismatch: {commanders}")
    if any(p["life"] != 40 for p in observation["players"]):
        raise AssertionError("life total mismatch")

    expected_required_event = f"knowledge_projection:{record['fixture_id']}:P1"
    return {
        "fixture_id": record["fixture_id"],
        "status": "PASS",
        "evidence_class": "RUNTIME_VERIFIED",
        "record_digest": record["materialization_digest"],
        "requested_semantic_state_digest": sha(requested),
        "normalized_native_constructed_state_digest": sha(constructed),
        "requested_native_state_equal": True,
        "native_state": constructed,
        "actor_projection": actor_result,
        "channels_runtime_audited": ["state", "option_id", "option_label", "option_metadata", "source_metadata", "ability_metadata", "transcript"],
        "channels_centrally_guarded": ["prompt", "context", "pile_metadata", "event", "log"],
        "forbidden_tokens_absent": list(FORBIDDEN_ACTOR_TOKENS),
        "expected_event_normalization": expected_required_event,
        "terminal_postcondition_result": "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    if contract.get("schema_version") != CONTRACT_VERSION:
        raise SystemExit("CONTRACT_SCHEMA_MISMATCH")
    if contract.get("canonical_bundle_digest") != CONTRACT_BUNDLE:
        raise SystemExit("CONTRACT_BUNDLE_MISMATCH")
    by_id = {row["fixture_id"]: row for row in contract["records"]}
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
    evidence = {
        "schema_version": "commander-lab.xmage-finalist-af05-hidden/1.0.0",
        "contract_commit": CONTRACT_COMMIT,
        "contract_bundle_digest": CONTRACT_BUNDLE,
        "candidate_commit": os.environ.get("GITHUB_SHA", "LOCAL"),
        "provider_implementation_commit": os.environ.get("GITHUB_SHA", "LOCAL"),
        "xmage_commit": gate.XMAGE_COMMIT,
        "xmage_tree": gate.XMAGE_TREE,
        "defect_remediated": "XMAGE_PROVIDER_DEFECT: direct qualification observation bypass",
        "counts": counts,
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"counts": counts, "output": str(args.output)}, sort_keys=True))
    return 0 if counts == {"PASS": 2} else 1


if __name__ == "__main__":
    raise SystemExit(main())
