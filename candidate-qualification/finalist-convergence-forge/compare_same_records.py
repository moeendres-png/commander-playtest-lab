#!/usr/bin/env python3
"""Neutral same-record comparator for finalist convergence evidence.

The comparator deliberately ignores provider UUIDs, raw action IDs, raw PRNG sequences,
process IDs, provider callback order, and opaque actor-handle values. It requires the
exact v1.0.1 record digest, identical normalized requested/native state for PASS/PASS
rows, and fixture-family-specific provider-neutral semantic evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

STARTER_ORDER = [
    "PLAYER_COUNT_2P",
    "PLAYER_COUNT_3P",
    "PLAYER_COUNT_4P",
    "PLAYER_COUNT_5P",
    "PILOT_MULLIGAN",
    "PILOT_PRIORITY",
    "PILOT_TARGET",
    "HIDDEN_01",
    "HIDDEN_02",
    "MICRO_STACK",
    "MICRO_REPLACEMENT",
    "WS05-MP-COMBAT-4",
    "RNG_RULES_TAPE",
    "REPLAY_DECISION_TAPE",
    "REPLAY_EVENT_TAPE",
    "REPLAY_CLEAN_PROCESS",
    "REPLAY_STATE_HASHES",
    "CARD_02",
]
PASS = "PASS"
UNSUPPORTED = "CANONICAL_SETUP_UNSUPPORTED"
HIDDEN_IDS = {"HIDDEN_01", "HIDDEN_02"}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows_by_id(
    payload: dict[str, Any], fixture_ids: list[str]
) -> dict[str, dict[str, Any]]:
    rows = {row["fixture_id"]: row for row in payload.get("rows", [])}
    missing = set(fixture_ids) - set(rows)
    if missing:
        raise SystemExit(f"SELECTED_ROW_SET_MISSING:{sorted(missing)}")
    return {fixture_id: rows[fixture_id] for fixture_id in fixture_ids}


def primitive_choices(row: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        decision
        for decision in row.get("canonical_decision_trace", [])
        if decision.get("decision_family") in {"priority", "target"}
    ]


def semantic_events(row: dict[str, Any]) -> list[dict[str, Any]]:
    normalized = []
    for event in row.get("event_tape", []):
        item = {"event_kind": event.get("event_kind")}
        for key in ("object", "target", "P2_life"):
            if key in event:
                item[key] = event[key]
        observation = event.get("native_observation")
        if isinstance(observation, dict) and "P2_life" in observation:
            item["P2_life"] = observation["P2_life"]
        normalized.append(item)
    return normalized


def forge_choices(row: dict[str, Any]) -> dict[str, Any]:
    decisions = row.get("semantic_decisions", [])
    starting = [d for d in decisions if d.get("decision_kind") == "chooseStartingPlayer"]
    if len(starting) != 1 or starting[0].get("selected_semantic_option") != "P1":
        raise ValueError("Forge starting-player semantic trace mismatch")
    mulligans: dict[str, list[str]] = {}
    for decision in decisions:
        if decision.get("decision_kind") == "mulliganKeepHand":
            mulligans.setdefault(str(decision["actor"]), []).append(
                str(decision["selected_semantic_option"])
            )
    return {"starting_player": "P1", "mulligans": mulligans}


def xmage_choices(row: dict[str, Any]) -> dict[str, Any]:
    decisions = row.get("decision_tape", [])
    starting = [d for d in decisions if d.get("decision_kind") == "choose_object"]
    if len(starting) != 1 or starting[0].get("selected_semantic_option_ids") != ["P1"]:
        raise ValueError("XMage starting-player semantic trace mismatch")

    mulligan_rows = [d for d in decisions if d.get("decision_kind") == "mulligan"]
    if not mulligan_rows:
        raise ValueError("XMage emitted no mulligan decisions")
    by_actor: dict[str, list[str]] = {}
    for decision in mulligan_rows:
        actor = f"P{int(decision['actor_seat'])}"
        selected = decision.get("selected_semantic_option_ids", [])
        if len(selected) != 1:
            raise ValueError(f"XMage mulligan selection not singular: {decision}")
        by_actor.setdefault(actor, []).append(str(selected[0]))

    non_p1 = [
        choice
        for actor, choices in by_actor.items()
        if actor != "P1"
        for choice in choices
    ]
    if not non_p1 or len(set(non_p1)) != 1:
        raise ValueError(f"XMage non-P1 keep identity is not stable: {by_actor}")
    keep_id = non_p1[0]
    normalized: dict[str, list[str]] = {}
    for actor, choices in by_actor.items():
        normalized[actor] = ["KEEP" if choice == keep_id else "MULLIGAN" for choice in choices]
    return {"starting_player": "P1", "mulligans": normalized}


def hidden_projection(row: dict[str, Any]) -> dict[str, Any]:
    projection = row.get("actor_projection")
    if not isinstance(projection, dict):
        raise ValueError("AF05 actor_projection missing")
    required = {
        "P2_hand_count": projection.get("P2_hand_count"),
        "P2_library_count": projection.get("P2_library_count"),
        "public_exile": projection.get("public_exile"),
        "controller_face_down_visible": projection.get("controller_face_down_visible"),
        "actor_object_ids_opaque": projection.get("actor_object_ids_opaque"),
    }
    if required != {
        "P2_hand_count": 1,
        "P2_library_count": 1,
        "public_exile": ["Sol Ring"],
        "controller_face_down_visible": ["Grizzly Bears"],
        "actor_object_ids_opaque": True,
    }:
        raise ValueError(f"AF05 semantic projection mismatch: {required}")
    return required


def compare_pass_rows(
    fixture_id: str, forge: dict[str, Any], xmage: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    required_equal = {
        "record_digest": forge.get("record_digest") == xmage.get("record_digest"),
        "requested_semantic_state_digest": forge.get("requested_semantic_state_digest")
        == xmage.get("requested_semantic_state_digest"),
        "normalized_native_constructed_state_digest": forge.get(
            "normalized_native_constructed_state_digest"
        )
        == xmage.get("normalized_native_constructed_state_digest"),
        "requested_native_state_equal": forge.get("requested_native_state_equal") is True
        and xmage.get("requested_native_state_equal") is True,
        "terminal_postcondition_result": forge.get("terminal_postcondition_result")
        == xmage.get("terminal_postcondition_result")
        == "PASS",
    }
    if not required_equal["record_digest"]:
        return "CONTRACT_DEFECT", required_equal

    if fixture_id in {
        "PLAYER_COUNT_2P",
        "PLAYER_COUNT_3P",
        "PLAYER_COUNT_4P",
        "PLAYER_COUNT_5P",
        "PILOT_MULLIGAN",
    }:
        required_equal["terminal_semantic_state"] = (
            forge.get("terminal_semantic_state") == xmage.get("terminal_semantic_state")
        )
        required_equal["semantic_discretionary_selections"] = forge_choices(
            forge
        ) == xmage_choices(xmage)
    elif fixture_id in {"PILOT_PRIORITY", "PILOT_TARGET"}:
        required_equal["terminal_semantic_state"] = (
            forge.get("terminal_semantic_state") == xmage.get("terminal_semantic_state")
        )
        required_equal["semantic_discretionary_selections"] = primitive_choices(
            forge
        ) == primitive_choices(xmage)
        required_equal["semantic_event_tape"] = semantic_events(forge) == semantic_events(xmage)
    elif fixture_id in HIDDEN_IDS:
        required_equal["native_semantic_state"] = forge.get("native_state") == xmage.get(
            "native_state"
        )
        required_equal["actor_projection"] = hidden_projection(forge) == hidden_projection(xmage)
        required_equal["opaque_identity_policy"] = (
            forge["actor_projection"].get("actor_object_ids_opaque") is True
            and xmage["actor_projection"].get("actor_object_ids_opaque") is True
        )
    else:
        required_equal["terminal_semantic_state"] = (
            forge.get("terminal_semantic_state") == xmage.get("terminal_semantic_state")
        )

    if all(required_equal.values()):
        return "DIFFERENTIAL_AGREEMENT_PASS", required_equal
    return "ENGINE_SEMANTIC_DISAGREEMENT", required_equal


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--forge", type=Path, required=True)
    ap.add_argument("--xmage", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--xmage-convergence-head", required=True)
    ap.add_argument("--xmage-workflow-run", required=True)
    ap.add_argument("--xmage-artifact-id", required=True)
    ap.add_argument("--xmage-artifact-digest", required=True)
    ap.add_argument(
        "--fixture-id",
        action="append",
        dest="fixture_ids",
        help="Fixture ID to compare; repeat for an explicit subset (default: Starter-18).",
    )
    args = ap.parse_args()

    fixture_ids = args.fixture_ids or list(STARTER_ORDER)
    if len(fixture_ids) != len(set(fixture_ids)):
        raise SystemExit("DUPLICATE_SELECTED_FIXTURE_ID")

    forge_payload = json.loads(args.forge.read_text(encoding="utf-8"))
    xmage_payload = json.loads(args.xmage.read_text(encoding="utf-8"))
    if forge_payload.get("contract_commit") != xmage_payload.get("contract_commit"):
        raise SystemExit("CONTRACT_COMMIT_MISMATCH")
    if forge_payload.get("contract_bundle_digest") != xmage_payload.get(
        "contract_bundle_digest"
    ):
        raise SystemExit("CONTRACT_BUNDLE_MISMATCH")

    forge_rows = rows_by_id(forge_payload, fixture_ids)
    xmage_rows = rows_by_id(xmage_payload, fixture_ids)
    output_rows: list[dict[str, Any]] = []
    for fixture_id in fixture_ids:
        forge = forge_rows[fixture_id]
        xmage = xmage_rows[fixture_id]
        if forge.get("record_digest") != xmage.get("record_digest"):
            verdict, detail = "CONTRACT_DEFECT", {"record_digest_equal": False}
        elif forge.get("status") == PASS and xmage.get("status") == PASS:
            try:
                verdict, detail = compare_pass_rows(fixture_id, forge, xmage)
            except Exception as exc:
                verdict, detail = "CONTRACT_DEFECT", {
                    "normalization_error": f"{type(exc).__name__}:{exc}"
                }
        elif forge.get("status") == UNSUPPORTED and xmage.get("status") == UNSUPPORTED:
            verdict, detail = "CANONICAL_SETUP_UNSUPPORTED_BOTH", {}
        elif forge.get("status") == UNSUPPORTED:
            verdict, detail = "CANONICAL_SETUP_UNSUPPORTED_FORGE", {}
        elif xmage.get("status") == UNSUPPORTED:
            verdict, detail = "CANONICAL_SETUP_UNSUPPORTED_XMAGE", {}
        elif forge.get("status") == "FAIL" and xmage.get("status") == "FAIL":
            verdict, detail = "PROVIDER_DEFECT_BOTH", {}
        elif forge.get("status") == "FAIL":
            verdict, detail = "PROVIDER_DEFECT_FORGE", {}
        elif xmage.get("status") == "FAIL":
            verdict, detail = "PROVIDER_DEFECT_XMAGE", {}
        else:
            verdict, detail = "CONTRACT_DEFECT", {
                "unexpected_status_pair": [forge.get("status"), xmage.get("status")]
            }
        output_rows.append(
            {
                "fixture_id": fixture_id,
                "record_digest": forge.get("record_digest"),
                "forge_status": forge.get("status"),
                "xmage_status": xmage.get("status"),
                "verdict": verdict,
                "comparison": detail,
            }
        )

    counts: dict[str, int] = {}
    for row in output_rows:
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    evidence = {
        "schema_version": "commander-lab.finalist-same-record-comparison/1.2.0",
        "selected_fixture_ids": fixture_ids,
        "contract_commit": forge_payload["contract_commit"],
        "contract_bundle_digest": forge_payload["contract_bundle_digest"],
        "forge_candidate_commit": forge_payload.get("candidate_commit"),
        "forge_engine_commit": forge_payload.get("forge_commit"),
        "xmage_convergence_head": args.xmage_convergence_head,
        "xmage_workflow_run": int(args.xmage_workflow_run),
        "xmage_artifact_id": int(args.xmage_artifact_id),
        "xmage_artifact_digest": args.xmage_artifact_digest,
        "xmage_behavioral_candidate_commit": xmage_payload.get("candidate_commit"),
        "xmage_engine_commit": xmage_payload.get("xmage_commit"),
        "input_sha256": {
            "forge": sha256_file(args.forge),
            "xmage": sha256_file(args.xmage),
        },
        "counts": counts,
        "rows": output_rows,
        "ignored_identity_dimensions": [
            "provider UUIDs",
            "opaque actor-handle values",
            "raw action IDs",
            "process IDs",
            "raw cross-engine PRNG sequence",
            "provider callback order",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"counts": counts, "output": str(args.output)}, sort_keys=True))
    bad = sum(
        counts.get(key, 0)
        for key in [
            "ENGINE_SEMANTIC_DISAGREEMENT",
            "PROVIDER_DEFECT_FORGE",
            "PROVIDER_DEFECT_XMAGE",
            "PROVIDER_DEFECT_BOTH",
            "CONTRACT_DEFECT",
        ]
    )
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
