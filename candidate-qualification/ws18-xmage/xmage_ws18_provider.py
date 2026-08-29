#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules.full_game_ws18 import (
    FullGamePilotBindingV2,
    XmageFullGameRunnerV2,
)
from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength, RulesDeckInput

PROTOCOL = "commander-lab.rules-service/1.1.0"
XMAGE_COMMIT = "77d7646da6958fdf8125ee7c8f4aabd130d21d4c"
CANDIDATE = "XMAGE_WS18"
PLAYER_COUNT_FIXTURES = {
    "PLAYER_COUNT_2P": 2,
    "PLAYER_COUNT_3P": 3,
    "PLAYER_COUNT_4P": 4,
    "PLAYER_COUNT_5P": 5,
}
ROOT = Path(__file__).resolve().parents[2]


def _deck(seat: int, player_count: int) -> RulesDeckInput:
    deck_id = f"ws18-technical-isamaru-{player_count}p-seat-{seat}"
    commander = ("Isamaru, Hound of Konda",)
    mainboard = tuple("Plains" for _ in range(99))
    material = json.dumps(
        {
            "deck_id": deck_id,
            "commander_names": commander,
            "mainboard": mainboard,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return RulesDeckInput(
        deck_id=deck_id,
        name=f"WS-18 technical Isamaru {player_count}P seat {seat}",
        commander_names=commander,
        mainboard=mainboard,
        deck_hash=hashlib.sha256(material).hexdigest(),
        source_path="synthetic:ws18-player-count-runtime-only",
    )


def _binding(seat: int, deck: RulesDeckInput) -> FullGamePilotBindingV2:
    return FullGamePilotBindingV2(
        seat=seat,
        deck_id=deck.deck_id,
        strategy="generic",
        commander_names=deck.commander_names,
        config=PilotConfig(
            pilot_name="auto",
            strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
            mode=PilotDecisionMode.DETERMINISTIC,
        ),
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-ws18-player-count-policy-1.0.0",
    )


def _metadata() -> dict[str, Any]:
    return {
        "engine_id": "xmage",
        "engine_version": "1.4.61",
        "ruleset_id": "magic-comprehensive-rules-via-xmage-1.4.61",
        "protocol_version": PROTOCOL,
        "engine_source_commit": XMAGE_COMMIT,
        "adapter_source_commit": os.environ.get("GITHUB_SHA", "UNRESOLVED_OUTSIDE_CI"),
        "supported_player_counts": [2, 3, 4, 5],
        "capabilities": {
            "commander": True,
            "multiplayer": True,
            "external_pilot_decisions": True,
            "actor_scoped_observation_gateway": True,
            "player_count_runtime_fixtures": sorted(PLAYER_COUNT_FIXTURES),
        },
        "strict_external_decision_control": True,
    }


def _response(request: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "protocol": PROTOCOL,
        "message_type": "RESULT",
        "request_id": request.get("request_id"),
        "session_id": request.get("session_id"),
        "payload": payload,
    }


def _run_player_count_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    fixture_id = str(fixture.get("fixture_id", ""))
    expected_count = PLAYER_COUNT_FIXTURES[fixture_id]
    requested_count = int(fixture.get("player_count", -1))
    if requested_count != expected_count:
        return {
            "verdict": "FAIL",
            "evidence_class": "RUNTIME_VERIFIED",
            "reason": (
                f"Fixture cardinality mismatch: {fixture_id} expects {expected_count}, "
                f"manifest requested {requested_count}."
            ),
            "artifact_hashes": {},
        }

    decks = tuple(_deck(seat, expected_count) for seat in range(1, expected_count + 1))
    pilots = tuple(_binding(seat, decks[seat - 1]) for seat in range(1, expected_count + 1))
    own = decks[0]
    assert own.deck_hash is not None
    scenario = FutureXmageScenario(
        candidate_id=own.deck_id,
        deck_hash=own.deck_hash,
        opponent_deck_ids=tuple(deck.deck_id for deck in decks[1:]),
        player_count=expected_count,
        seat=1,
        scenario_id=f"ws18-rsp-{fixture_id.lower()}",
        seed=int(fixture.get("seed", 424242)),
        xmage_commit=XMAGE_COMMIT,
        bridge_version="xmage-engine-bridge-0.1.0-SNAPSHOT",
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-ws18-player-count-policy-1.0.0",
    )
    runner = XmageFullGameRunnerV2(
        cwd=ROOT,
        request_timeout_seconds=120.0,
        max_decisions=50_000,
    )
    result = runner.run(scenario=scenario, decks=decks, pilots=pilots)
    if not result.terminal:
        return {
            "verdict": "FAIL",
            "evidence_class": "RUNTIME_VERIFIED",
            "reason": f"XMage {expected_count}P runtime did not reach terminal game state.",
            "artifact_hashes": {},
        }
    if result.decision_count <= 0:
        return {
            "verdict": "FAIL",
            "evidence_class": "RUNTIME_VERIFIED",
            "reason": f"XMage {expected_count}P runtime exercised no external pilot decisions.",
            "artifact_hashes": {},
        }
    outcomes = result.result_payload.get("outcomes")
    if not isinstance(outcomes, list) or len(outcomes) != expected_count:
        return {
            "verdict": "FAIL",
            "evidence_class": "RUNTIME_VERIFIED",
            "reason": (
                f"XMage {expected_count}P runtime returned invalid stable outcome cardinality: "
                f"{0 if not isinstance(outcomes, list) else len(outcomes)}."
            ),
            "artifact_hashes": {},
        }
    return {
        "verdict": "PASS",
        "evidence_class": "RUNTIME_VERIFIED",
        "reason": (
            f"Executed a real isolated XMage {expected_count}P Commander lifecycle to terminal "
            f"state with {result.decision_count} externally piloted decisions and "
            f"{len(outcomes)} stable seat outcomes."
        ),
        "artifact_hashes": {
            "semantic_transcript_sha256": result.semantic_transcript_sha256,
            "raw_result_sha256": result.raw_result_sha256,
        },
    }


def handle(request: dict[str, Any]) -> dict[str, Any]:
    if request.get("protocol") != PROTOCOL:
        return _response(
            request,
            {
                "verdict": "FAIL",
                "evidence_class": "RUNTIME_VERIFIED",
                "reason": f"Protocol mismatch; expected {PROTOCOL}.",
                "artifact_hashes": {},
            },
        )
    message_type = request.get("message_type")
    if message_type == "START_ENGINE":
        return _response(request, {"verdict": "PASS", "metadata": _metadata()})
    if message_type == "GET_CAPABILITIES":
        return _response(request, {"verdict": "PASS", "metadata": _metadata()})
    if message_type != "RUN_FIXTURE":
        return _response(
            request,
            {
                "verdict": "UNSUPPORTED",
                "evidence_class": "NOT_RUN",
                "reason": f"Unsupported RSP message_type: {message_type!r}.",
                "artifact_hashes": {},
            },
        )

    payload = request.get("payload")
    fixture = payload.get("fixture") if isinstance(payload, dict) else None
    if not isinstance(fixture, dict):
        return _response(
            request,
            {
                "verdict": "FAIL",
                "evidence_class": "RUNTIME_VERIFIED",
                "reason": "RUN_FIXTURE payload.fixture is required.",
                "artifact_hashes": {},
            },
        )
    fixture_id = str(fixture.get("fixture_id", ""))
    if fixture_id not in PLAYER_COUNT_FIXTURES:
        return _response(
            request,
            {
                "verdict": "NOT_RUN",
                "evidence_class": "NOT_RUN",
                "reason": (
                    "WS-18 RSP adapter has no candidate-specific executable materialization for "
                    f"{fixture_id}; no PASS is inferred from XMage source/card coverage."
                ),
                "artifact_hashes": {},
            },
        )
    try:
        result = _run_player_count_fixture(fixture)
    except Exception as exc:
        result = {
            "verdict": "FAIL",
            "evidence_class": "RUNTIME_VERIFIED",
            "reason": f"XMage runtime fixture raised {type(exc).__name__}: {exc}",
            "artifact_hashes": {},
        }
    return _response(request, result)


def main() -> int:
    line = sys.stdin.readline()
    if not line.strip():
        print(json.dumps({"payload": {"verdict": "FAIL", "reason": "empty request"}}))
        return 0
    try:
        request = json.loads(line)
    except json.JSONDecodeError as exc:
        print(json.dumps({"payload": {"verdict": "FAIL", "reason": f"invalid JSON: {exc}"}}))
        return 0
    print(json.dumps(handle(request), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
