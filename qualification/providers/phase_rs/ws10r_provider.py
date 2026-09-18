#!/usr/bin/env python3
"""Fail-closed WS-10R transport for the WS-20 v2 phase.rs candidate.

This process is not a Rules Core. It never derives legality, targets, costs,
priority, hidden information, random outcomes, or Commander semantics. For the
common fixture harness it transports only results produced by exact engine-native
probes in the same CI run. An exact fixture without native materialization is
UNSUPPORTED/NOT_RUN.

The handshake is intentionally truthful: this is a qualification transport, not
a complete production RSP session bridge. Production capability remains false
until native phase.rs sessions/observations/decision frames can represent the full
RSP 1.1.0 surface losslessly.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

PROTOCOL = "commander-lab.rules-service/1.1.0"
SOURCE_COMMIT = "5c87559082f4703c10c3f70692a02bb675c5e576"
TARGET_BASELINE = "c83e52ae79ff2242578757c0f517badbb1a2621c"


def emit(request: dict, payload: dict, message_type: str = "FIXTURE_RESULT") -> None:
    print(
        json.dumps(
            {
                "protocol": PROTOCOL,
                "message_type": message_type,
                "request_id": request.get("request_id"),
                "session_id": request.get("session_id"),
                "payload": payload,
            },
            sort_keys=True,
        )
    )


def load_runtime_map() -> dict:
    value = os.environ.get("WS20_RUNTIME_RESULT_MAP")
    if not value:
        return {}
    path = Path(value)
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def build_identity() -> dict:
    return {
        "candidate": "phase.rs-ws20-v2-patched",
        "target_baseline": TARGET_BASELINE,
        "upstream_commit": SOURCE_COMMIT,
        "patched_tree": os.environ.get("WS20_PHASE_PATCHED_TREE"),
        "patch_sha256": os.environ.get("WS20_PHASE_PATCH_SHA256"),
        "provider_sha256": os.environ.get("WS20_PROVIDER_SHA256"),
        "common_manifest_sha256": os.environ.get("WS20_COMMON_MANIFEST_SHA256"),
    }


def main() -> int:
    line = sys.stdin.readline()
    if not line.strip():
        return 2
    try:
        request = json.loads(line)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "protocol": PROTOCOL,
                    "message_type": "ERROR",
                    "payload": {"code": "MALFORMED_JSON", "detail": str(exc)},
                },
                sort_keys=True,
            )
        )
        return 0

    if request.get("protocol") != PROTOCOL:
        emit(
            request,
            {
                "code": "PROTOCOL_MISMATCH",
                "expected": PROTOCOL,
                "received": request.get("protocol"),
            },
            "ERROR",
        )
        return 0

    message_type = request.get("message_type")
    if message_type == "HANDSHAKE":
        emit(
            request,
            {
                **build_identity(),
                "protocol": PROTOCOL,
                "production_capable": False,
                "provider_role": "qualification_transport_only",
                "native_action_authority": "phase_engine::types::actions::GameAction",
                "qualification_fixture_materialization": "engine-native-evidence-only",
                "unsupported_policy": "fail-closed",
                "native_session_bridge": False,
                "actor_scoped_observation_bridge": False,
                "clean_process_rsp_replay_bridge": False,
            },
            "HANDSHAKE_RESULT",
        )
        return 0

    if message_type == "RUN_FIXTURE":
        fixture = request.get("payload", {}).get("fixture", {})
        fixture_id = fixture.get("fixture_id")
        runtime_map = load_runtime_map()
        result = runtime_map.get(fixture_id)
        if isinstance(result, dict):
            # Workflow-created engine-native result. Transport without reinterpretation.
            emit(request, result)
            return 0
        emit(
            request,
            {
                "verdict": "UNSUPPORTED",
                "evidence_class": "NOT_RUN",
                "reason": (
                    "No engine-native materialization exists for this exact common fixture at "
                    "the locked phase.rs build. The Foundry adapter refuses to reconstruct "
                    "rules state/actions or synthesize a PASS."
                ),
                "artifact_hashes": {},
            },
        )
        return 0

    emit(
        request,
        {
            "code": "UNSUPPORTED_OPERATION",
            "detail": (
                f"{message_type!r} is not implemented by the WS-20 v2 qualification transport. "
                "No fallback, internal AI, default choice, or adapter-side Rules Core is permitted."
            ),
            "identity": build_identity(),
        },
        "ERROR",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
