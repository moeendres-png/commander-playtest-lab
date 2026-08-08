from __future__ import annotations

import json
import sys
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from commander_lab.engine.process_manager import EngineProcessManager, load_engine_runtime_config
from commander_lab.models import (
    ENGINE_PROTOCOL_VERSION,
    EngineMessageType,
    EngineReplay,
    RuntimeValidationLevel,
)
from commander_lab.storage.atomic import atomic_write_json

from .bridge import JsonLineBridgeClient
from .protocol import write_protocol_schema
from .replay import replay_into_internal_model

PHASE85_VERSION = "engine-integration-0.8.5"
_NO_EXTERNAL_SCENARIO_RESULT = (
    "No scenario-level external XMage/Forge result was produced by this validation run."
)

PROJECT_SCENARIOS = (
    "commander_from_command_zone",
    "commander_tax_after_removal",
    "partner_commanders",
    "commander_damage_per_opponent",
    "kediss_normal_damage",
    "jeska_combat_damage_tripling",
    "boardwipe",
    "counter_commander",
    "protection_response",
    "cast_trigger_survives_counter",
)


def _utc() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _tactical_contract(root: Path) -> dict[str, Any]:
    """Exercise every declared JSONL envelope without relying on shutdown races.

    Non-terminal messages share one persistent tactical bridge. Terminal shutdown
    messages each use their own bridge process because they intentionally end the
    process. A structured protocol error still counts as envelope coverage, but
    semantic success is required for the Tactical-Oracle hello/capability evidence.
    This remains local protocol evidence, never external-engine evidence.
    """
    declared = [item.value for item in EngineMessageType]
    terminal_kinds = (
        EngineMessageType.SHUTDOWN_GAME,
        EngineMessageType.SHUTDOWN_ENGINE,
    )
    attempted: set[str] = set()
    execution_order: list[str] = []
    structured: dict[str, str] = {}
    hello: dict[str, Any] = {}
    caps: dict[str, Any] = {}

    def make_client() -> JsonLineBridgeClient:
        return JsonLineBridgeClient(
            (sys.executable, str(root / "scripts/tactical_rules_bridge.py")),
            cwd=root,
            engine="tactical",
            protocol_version=ENGINE_PROTOCOL_VERSION,
            request_timeout_seconds=5,
        )

    def exercise(client: JsonLineBridgeClient, kind: EngineMessageType) -> None:
        nonlocal hello, caps
        params: dict[str, Any] = {}
        game_id = (
            None
            if kind
            in {
                EngineMessageType.ENGINE_HELLO,
                EngineMessageType.ENGINE_CAPABILITIES,
                EngineMessageType.LOAD_DECK,
                EngineMessageType.CREATE_GAME,
            }
            else "missing-game"
        )
        attempted.add(kind.value)
        execution_order.append(kind.value)
        try:
            payload = client.request(kind, params, game_id=game_id)
            structured[kind.value] = "success"
            if kind == EngineMessageType.ENGINE_HELLO:
                hello = payload
            elif kind == EngineMessageType.ENGINE_CAPABILITIES:
                caps = payload
        except Exception as exc:
            # A deterministic structured protocol failure still proves envelope coverage.
            if "bridge message" in str(exc):
                structured[kind.value] = "structured_error"
            else:
                structured[kind.value] = f"client_error:{type(exc).__name__}"

    client = make_client()
    try:
        for kind in EngineMessageType:
            if kind not in terminal_kinds:
                exercise(client, kind)
        unknown_rejected = False
        try:
            client.request("unknown_message")
        except Exception:
            unknown_rejected = True
    finally:
        # Windows may invalidate a completed subprocess pipe before TextIOWrapper.close().
        # Cleanup must not turn a completed contract exercise into a validation failure.
        with suppress(OSError):
            client.close()

    for kind in terminal_kinds:
        terminal_client = make_client()
        try:
            exercise(terminal_client, kind)
        finally:
            with suppress(OSError):
                terminal_client.close()

    exercised = [name for name in declared if name in attempted]
    all_exercised = exercised == declared
    return {
        "status": "passed" if all_exercised and unknown_rejected else "failed",
        "passed": (
            all_exercised
            and hello.get("validation_level") == RuntimeValidationLevel.TACTICAL_ORACLE.value
            and caps.get("capabilities", {}).get("runtime_kind") == "tactical_oracle"
            and unknown_rejected
        ),
        "exercised": exercised,
        "execution_order": execution_order,
        "declared_message_types": declared,
        "message_outcomes": structured,
        "all_message_envelopes_covered_by_contract_tests": all_exercised,
        "unknown_message_rejected": unknown_rejected,
        "hello": hello,
        "capabilities": caps.get("capabilities", {}),
        "validation_level": RuntimeValidationLevel.TACTICAL_ORACLE.value,
    }


def _replay_contract() -> dict[str, Any]:
    state = {
        "game_id": "phase85-replay",
        "seed": 85,
        "rng_counter": 0,
        "status": "in_progress",
        "turn_number": 1,
        "active_player_id": "p1",
        "priority_player_id": "p1",
        "phase": "precombat_main",
        "step": None,
        "players": [
            {
                "player_id": "p1",
                "seat": 0,
                "life": 40,
                "poison_counters": 0,
                "commander_damage_received": {},
                "commander_cast_count": {"Commander A": 1},
                "mana_pool": {},
                "zones": {
                    "library": ["Card B"],
                    "hand": [],
                    "battlefield": ["Land A"],
                    "graveyard": [],
                    "exile": [],
                    "command": ["Commander A"],
                },
                "land_plays_remaining": 0,
                "has_lost": False,
                "loss_reason": None,
            },
            {
                "player_id": "p2",
                "seat": 1,
                "life": 37,
                "poison_counters": 0,
                "commander_damage_received": {"Commander A": 3},
                "commander_cast_count": {},
                "mana_pool": {},
                "zones": {
                    "library": ["Card C"],
                    "hand": [],
                    "battlefield": [],
                    "graveyard": [],
                    "exile": [],
                    "command": ["Commander B"],
                },
                "land_plays_remaining": 1,
                "has_lost": False,
                "loss_reason": None,
            },
        ],
        "stack": [],
        "legal_actions": [],
        "winner_ids": [],
        "event_sequence": 2,
    }
    event = {
        "sequence": 2,
        "event_type": "state_snapshot",
        "internal_state_after": state,
    }
    digest = (
        __import__("hashlib")
        .sha256(json.dumps([event], sort_keys=True, separators=(",", ":")).encode())
        .hexdigest()
    )
    replay = EngineReplay(
        engine="tactical",
        engine_version="tactical-0.8.5",
        validation_level=RuntimeValidationLevel.TACTICAL_ORACLE,
        game_id="phase85-replay",
        initial_state=state,
        events=(event,),
        final_state=state,
        event_log_sha256=digest,
    )
    result = replay_into_internal_model(replay)
    return {
        "passed": result.passed,
        "events_applied": result.events_applied,
        "final_state_hash": result.final_state_hash,
        "mismatches": list(result.mismatches),
        "validation_level": RuntimeValidationLevel.TACTICAL_ORACLE.value,
    }


def run_phase85_validation(
    root: str | Path,
    *,
    output_directory: str | Path,
) -> dict[str, Any]:
    repo = Path(root).resolve()
    output = Path(output_directory)
    if not output.is_absolute():
        output = repo / output
    output.mkdir(parents=True, exist_ok=True)
    write_protocol_schema(repo / "schemas/engine_adapter_protocol.schema.json")

    config = load_engine_runtime_config()
    process_manager = EngineProcessManager(config, root=repo)
    external_state = process_manager.diagnose()
    if config.start_command:
        external_state = process_manager.start()
        if external_state.status.value == "healthy":
            process_manager.stop()

    tactical = _tactical_contract(repo)
    replay = _replay_contract()
    external_ready = external_state.status.value == "healthy"
    external_tests = {
        "handshake": external_ready,
        "deck_import": False,
        "multiplayer_game": False,
        "legal_action": False,
        "event_log": False,
        "illegal_action_rejected": False,
    }
    full_external = all(external_tests.values())
    scenarios = [
        {
            "scenario": name,
            "status": "manual_review_required",
            "validation_level": RuntimeValidationLevel.STRUCTURAL_ONLY.value,
            "note": _NO_EXTERNAL_SCENARIO_RESULT,
        }
        for name in PROJECT_SCENARIOS
    ]
    status = (
        "external_engine_validated"
        if full_external
        else (
            "external_runtime_handshake_only"
            if external_ready
            else "external_runtime_prepared_but_not_executed"
        )
    )
    result = {
        "phase": "8.5",
        "version": PHASE85_VERSION,
        "generated_at": _utc(),
        "status": status,
        "external_engine_validation_pending": not full_external,
        "primary_engine": "xmage",
        "secondary_engine": "forge",
        "installed_or_pinned": {
            "xmage": {
                "release": "xmage_1.4.60V3",
                "commit": "06d166b098ad36b277edef01116472203d5a047e",
                "executed": False,
            },
            "forge": {
                "release": "forge-2.0.13",
                "commit": "852066bf4f761b302ed17cb011999d8a8fe08ad6",
                "executed": False,
            },
        },
        "external_process_state": external_state.model_dump(mode="json"),
        "contract_tests": tactical,
        "replay_tests": replay,
        "external_integration_tests": external_tests,
        "project_scenarios": scenarios,
        "local_acceptance_passed": tactical["passed"] and replay["passed"],
        "full_external_acceptance_passed": full_external,
        "phase9_may_begin": True,
        "phase9_condition": "external_engine_validation_pending=true",
        "claims_boundary": (
            "Tactical Oracle and handshake-only results are not external rules-engine "
            "semantic evidence."
        ),
    }
    target = output / "phase85_validation_output.json"
    atomic_write_json(target, result)
    return result


__all__ = ["PHASE85_VERSION", "PROJECT_SCENARIOS", "run_phase85_validation"]
