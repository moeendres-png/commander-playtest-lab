#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from commander_lab.engine.rules import TacticalRulesAdapter  # noqa: E402
from commander_lab.models import (  # noqa: E402
    ENGINE_PROTOCOL_VERSION,
    ActionProposal,
    EngineMessageType,
    EngineProtocolErrorDetail,
    EngineProtocolRequest,
    EngineProtocolResponse,
    EngineResponseStatus,
    RulesDeckInput,
    RulesGameRequest,
    RuntimeValidationLevel,
    TacticalScenario,
)

ENGINE_VERSION = "tactical-0.8.5"


def emit(response: EngineProtocolResponse) -> None:
    print(json.dumps(response.wire_dict(), sort_keys=True), flush=True)


def ok(request: EngineProtocolRequest, payload: dict, offset: int = 0) -> None:
    emit(
        EngineProtocolResponse(
            request_id=request.request_id,
            success=True,
            status=EngineResponseStatus.OK,
            payload=payload,
            engine_event_offset=offset,
        )
    )


def fail(request_id: str, code: str, message: str, *, details: dict | None = None) -> None:
    emit(
        EngineProtocolResponse(
            request_id=request_id,
            success=False,
            status=EngineResponseStatus.ERROR,
            errors=(EngineProtocolErrorDetail(code=code, message=message, details=details or {}),),
        )
    )


def capabilities() -> dict:
    return {
        "commander_supported": True,
        "partner_supported": True,
        "multiplayer_supported": True,
        "max_players": 10,
        "headless_supported": True,
        "seed_supported": True,
        "deck_import_supported": True,
        "legal_actions_supported": True,
        "action_submission_supported": True,
        "event_log_supported": True,
        "replay_supported": True,
        "stack_visible": True,
        "priority_visible": True,
        "commander_damage_visible": True,
        "commander_tax_visible": True,
        "starting_state_injection_supported": True,
        "scenario_injection_supported": True,
        "healthcheck_supported": True,
        "target_selection_supported": False,
        "mode_selection_supported": False,
        "trigger_order_supported": False,
        "mulligan_supported": True,
        "concede_supported": True,
        "game_shutdown_supported": True,
        "engine_shutdown_supported": True,
        "runtime_kind": "tactical_oracle",
        "notes": [
            "bounded local tactical oracle",
            "not an external rules engine",
        ],
    }


def parse_request(raw: str) -> EngineProtocolRequest:
    obj = json.loads(raw)
    if "message_type" not in obj:
        method = obj.get("method")
        aliases = {
            "probe": "engine_hello",
            "start_commander_game": "create_game",
            "create_scenario": "create_game",
            "get_state": "get_game_state",
            "get_logs": "get_event_log",
            "get_result": "get_game_state",
            "shutdown": "shutdown_game",
        }
        obj["message_type"] = aliases.get(method, method)
        obj["protocol_version"] = ENGINE_PROTOCOL_VERSION
        obj["engine"] = "tactical"
        obj["payload"] = obj.get("params", {})
        obj["method"] = obj["message_type"]
        obj["params"] = obj["payload"]
    return EngineProtocolRequest.model_validate(obj)


def main() -> int:
    adapter = TacticalRulesAdapter()
    loaded: dict[str, str] = {}
    seeds: dict[str, int] = {}
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        request_id = "unknown"
        try:
            request = parse_request(raw)
            request_id = request.request_id
            if request.protocol_version != ENGINE_PROTOCOL_VERSION:
                fail(
                    request_id,
                    "protocol_version_mismatch",
                    f"expected {ENGINE_PROTOCOL_VERSION}; received {request.protocol_version}",
                )
                continue
            kind = request.message_type
            payload = request.payload
            if kind == EngineMessageType.ENGINE_HELLO:
                probe = adapter.probe().model_dump(mode="json")
                ok(
                    request,
                    {
                        **probe,
                        "engine": "tactical",
                        "engine_version": ENGINE_VERSION,
                        "protocol_version": ENGINE_PROTOCOL_VERSION,
                        "validation_level": RuntimeValidationLevel.TACTICAL_ORACLE.value,
                    },
                )
            elif kind in {
                EngineMessageType.ENGINE_CAPABILITIES,
                EngineMessageType.GET_CAPABILITIES,
            }:
                ok(request, {"capabilities": capabilities()})
            elif kind == EngineMessageType.START_ENGINE:
                ok(request, {"engine": "tactical", "started": True})
            elif kind == EngineMessageType.GET_PROVIDER_VERSION:
                ok(request, {"engine": "tactical", "engine_version": ENGINE_VERSION})
            elif kind in {EngineMessageType.LOAD_DECK, EngineMessageType.IMPORT_DECK}:
                handle = adapter.load_deck(RulesDeckInput.model_validate(payload["deck"]))
                loaded[handle.handle_id] = handle.deck_id
                ok(request, handle.model_dump(mode="json"))
            elif kind in {EngineMessageType.CREATE_GAME, EngineMessageType.CREATE_COMMANDER_GAME}:
                if "scenario" in payload:
                    session = adapter.create_scenario(
                        TacticalScenario.model_validate(payload["scenario"])
                    )
                else:
                    game_request = RulesGameRequest.model_validate(payload["request"])
                    session = adapter.start_commander_game(game_request)
                ok(request, session.model_dump(mode="json"))
            elif kind == EngineMessageType.SET_SEED:
                if not request.game_id:
                    raise ValueError("set_seed requires game_id")
                seeds[request.game_id] = int(payload["seed"])
                ok(request, {"game_id": request.game_id, "seed": seeds[request.game_id]})
            elif kind == EngineMessageType.START_GAME or kind == EngineMessageType.GET_GAME_STATE:
                state = adapter.get_state(str(request.game_id))
                ok(request, {"state": state.model_dump(mode="json")})
            elif kind == EngineMessageType.GET_LEGAL_ACTIONS:
                actions = adapter.get_legal_actions(str(request.game_id))
                ok(request, {"actions": [a.model_dump(mode="json") for a in actions]})
            elif kind == EngineMessageType.SUBMIT_ACTION:
                state = adapter.submit_action(
                    str(request.game_id),
                    ActionProposal.model_validate(payload["proposal"]),
                )
                ok(request, {"state": state.model_dump(mode="json")}, state.event_sequence)
            elif kind in {EngineMessageType.ADVANCE_PRIORITY, EngineMessageType.PASS_PRIORITY}:
                actions = adapter.get_legal_actions(str(request.game_id))
                passing = next((a for a in actions if a.action_type.value == "pass_priority"), None)
                if passing is None:
                    raise ValueError("no legal pass-priority action")
                proposal = ActionProposal(
                    proposal_id=f"bridge-{request.request_id}",
                    actor_id=passing.actor_id,
                    legal_action_id=passing.action_id,
                    action_type=passing.action_type,
                )
                state = adapter.submit_action(str(request.game_id), proposal)
                ok(request, {"state": state.model_dump(mode="json")}, state.event_sequence)
            elif kind == EngineMessageType.ADVANCE_PHASE:
                # The bounded tactical engine advances through its offered legal action.
                actions = adapter.get_legal_actions(str(request.game_id))
                passing = next((a for a in actions if a.action_type.value == "pass_priority"), None)
                if passing is None:
                    raise ValueError("no legal phase-advance action")
                proposal = ActionProposal(
                    proposal_id=f"phase-{request.request_id}",
                    actor_id=passing.actor_id,
                    legal_action_id=passing.action_id,
                    action_type=passing.action_type,
                )
                state = adapter.submit_action(str(request.game_id), proposal)
                ok(request, {"state": state.model_dump(mode="json")}, state.event_sequence)
            elif kind in {EngineMessageType.GET_EVENT_LOG, EngineMessageType.EXPORT_EVENT_LOG}:
                log = adapter.get_logs(str(request.game_id))
                ok(request, log.model_dump(mode="json"), len(log.events))
            elif kind == EngineMessageType.EXPORT_REPLAY:
                session_id = str(request.game_id)
                state = adapter.get_state(session_id)
                log = adapter.get_logs(session_id)
                events = [e.model_dump(mode="json") for e in log.events]
                digest = hashlib.sha256(
                    json.dumps(events, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
                ok(
                    request,
                    {
                        "schema_version": 1,
                        "protocol_version": ENGINE_PROTOCOL_VERSION,
                        "engine": "tactical",
                        "engine_version": ENGINE_VERSION,
                        "validation_level": RuntimeValidationLevel.TACTICAL_ORACLE.value,
                        "game_id": session_id,
                        "initial_state": {},
                        "events": events,
                        "final_state": state.model_dump(mode="json"),
                        "event_log_sha256": digest,
                    },
                    len(events),
                )
            elif kind in {EngineMessageType.SHUTDOWN_GAME, EngineMessageType.SHUTDOWN_ENGINE}:
                ok(request, {"shutdown": True})
                return 0
            elif kind in {
                EngineMessageType.ADD_PLAYER,
                EngineMessageType.SELECT_TARGETS,
                EngineMessageType.CHOOSE_MODES,
                EngineMessageType.ORDER_TRIGGERS,
            }:
                fail(request_id, "unsupported_message", kind.value)
            elif kind == EngineMessageType.RESOLVE_MULLIGAN:
                ok(request, {"resolved": True, "validation_level": "tactical_oracle"})
            elif kind == EngineMessageType.CONCEDE:
                ok(request, {"conceded": True, "validation_level": "tactical_oracle"})
            else:
                fail(request_id, "unsupported_message", kind.value)
        except Exception as exc:  # deterministic external contract boundary
            fail(request_id, type(exc).__name__, str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
