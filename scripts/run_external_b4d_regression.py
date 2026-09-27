from __future__ import annotations

import contextlib
import json
import math
import os
from pathlib import Path
from typing import Any

from commander_lab.engine.rules.base import RulesEngineProtocolError
from commander_lab.engine.rules.bridge import ExternalRulesAdapter
from commander_lab.models import (
    EngineMessageType,
    GameState,
    RulesBackend,
    RulesDeckInput,
    RulesEngineAvailability,
    RulesGameRequest,
)

ROOT = Path(__file__).resolve().parents[1]
ROGRAKH = "Rograkh, Son of Rohgahh"


def _runtime_deck() -> RulesDeckInput:
    payload = json.loads((ROOT / "data/decks/rogshai_current.json").read_text(encoding="utf-8"))
    commanders = tuple(str(name) for name in payload["commander"]["commanders"])
    mainboard: list[str] = []
    for row in payload["cards"]:
        if row["zone"] != "main":
            continue
        mainboard.extend([str(row["oracle_name"])] * int(row.get("quantity", 1)))
    return RulesDeckInput(
        deck_id=str(payload["deck_id"]),
        name=str(payload["name"]),
        commander_names=commanders,
        mainboard=tuple(mainboard),
        deck_hash=str(payload["deck_hash"]),
        source_path="data/decks/rogshai_current.json",
    )


def _timeout_from_environment(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise SystemExit(f"{name} must be a finite positive number of seconds") from exc
    if not math.isfinite(value) or value <= 0.0 or value > 600.0:
        raise SystemExit(f"{name} must be > 0 and <= 600 seconds")
    return value


def _unique_pass(decision: dict[str, Any]) -> dict[str, Any]:
    matches = [
        dict(action)
        for action in decision.get("actions", ())
        if action.get("action_type") == "pass_priority"
    ]
    if len(matches) != 1:
        raise SystemExit(f"B4-D expected one pass action, observed {len(matches)}")
    return matches[0]


def _proposal(decision: dict[str, Any], action: dict[str, Any]) -> dict[str, Any]:
    return {
        "proposal_id": f"b4d/{decision['decision_id']}/{action['action_id']}",
        "actor_id": str(decision["actor_id"]),
        "legal_action_id": str(action["action_id"]),
        "action_type": str(action["action_type"]),
        "source_object_id": str(action["source_object_id"]),
        "target_ids": [],
        "selected_modes": [],
        "choices": {},
        "decision_tier": 1,
        "policy_name": "b4d-real-regression",
        "rationale": "real XMage B4-D event-log linkage validation",
    }


def _validate_events(events: list[dict[str, Any]]) -> None:
    sequences = [int(event["sequence"]) for event in events]
    if sequences != sorted(sequences) or len(sequences) != len(set(sequences)):
        raise SystemExit(f"B4-D event sequence is not strictly monotonic/unique: {sequences}")
    if sequences and sequences != list(range(sequences[0], sequences[0] + len(sequences))):
        raise SystemExit(f"B4-D event sequence contains a gap: {sequences}")
    for event in events:
        if len(str(event["event_id"])) != 64:
            raise SystemExit("B4-D event_id is not a SHA-256 identity")


def _expect_unknown_game(client: Any, game_id: str) -> None:
    try:
        client.request(EngineMessageType.GET_GAME_STATE, {}, game_id=game_id)
    except RulesEngineProtocolError as exc:
        if "Unknown process-local game_id" not in str(exc):
            raise SystemExit(f"B4-D shutdown failed for unexpected reason: {exc}") from exc
        return
    raise SystemExit("B4-D shut down game remained addressable")


def main() -> None:
    request_timeout_seconds = _timeout_from_environment(
        "XMAGE_B4D_REQUEST_TIMEOUT_SECONDS",
        30.0,
    )
    adapter = ExternalRulesAdapter(
        RulesBackend.XMAGE,
        cwd=ROOT,
        request_timeout_seconds=request_timeout_seconds,
    )
    evidence: dict[str, object] = {
        "schema_version": "1.0.0",
        "evidence_class": "external_rules_engine",
        "scope": "xmage_b4d_external_audit_event_log_and_repeated_game_lifecycle",
        "event_log_boundary": "real_xmage_bridge_lifecycle_and_external_action_boundaries",
        "raw_internal_xmage_gameevent_exhaustive": False,
        "automatic_canonical_mutation": False,
        "confirmatory_consumed": False,
        "sealed_holdout_consumed": False,
    }
    try:
        probe = adapter.probe()
        if probe.availability is not RulesEngineAvailability.AVAILABLE:
            raise SystemExit(f"XMage bridge is not available: {probe.model_dump(mode='json')}")
        caps = adapter.get_capabilities()
        if not caps.event_log_supported:
            raise SystemExit("B4-D bridge did not advertise event_log_supported")
        if not caps.game_shutdown_supported:
            raise SystemExit("B4-D bridge did not advertise game_shutdown_supported")

        deck = _runtime_deck()
        client = adapter._require_client()
        handles = tuple(adapter.import_deck(deck).handle_id for _ in range(4))
        game_id = "ci-b4d-event-log-lifecycle-4p"
        created = adapter.create_commander_game(
            RulesGameRequest(
                game_id=game_id,
                deck_handles=handles,
                starting_player_seat=0,
                starting_life=40,
                seed=None,
                external_control=True,
            )
        )
        if created != game_id:
            raise SystemExit("B4-D first game identity mismatch")
        started = adapter.start_game(game_id)
        if started.get("paused") is not True:
            raise SystemExit("B4-D first game did not pause under external control")

        initial_log = client.request(
            EngineMessageType.EXPORT_EVENT_LOG,
            {"after_offset": 0},
            game_id=game_id,
        )
        if initial_log.get("raw_internal_xmage_gameevent_exhaustive") is not False:
            raise SystemExit("B4-D event-log evidence boundary is not explicit")
        if initial_log.get("event_log_source") != "xmage_bridge_external_control":
            raise SystemExit("B4-D event-log source is not the real XMage bridge")
        initial_events = [dict(item) for item in initial_log["log"]["events"]]
        _validate_events(initial_events)
        if [event["event_type"] for event in initial_events] != [
            "game_created",
            "game_started",
        ]:
            raise SystemExit("B4-D initial lifecycle events are incomplete or reordered")
        initial_offset = int(initial_log["latest_event_offset"])
        if initial_offset != 2:
            raise SystemExit(f"B4-D expected initial event offset 2, got {initial_offset}")
        if len(str(initial_log["log"]["log_sha256"])) != 64:
            raise SystemExit("B4-D initial log hash is invalid")

        passes = 0
        action_event: dict[str, Any] | None = None
        for _ in range(64):
            decision = client.request(EngineMessageType.GET_LEGAL_ACTIONS, {}, game_id=game_id)
            commander_actions = [
                dict(action)
                for action in decision.get("actions", ())
                if action.get("action_type") == "cast_commander"
                and action.get("metadata", {}).get("submission_ready") is True
                and action.get("metadata", {}).get("choice_control_required") is False
            ]
            if commander_actions:
                action = commander_actions[0]
                result = client.request(
                    EngineMessageType.SUBMIT_ACTION,
                    {
                        "decision_id": str(decision["decision_id"]),
                        "proposal": _proposal(decision, action),
                    },
                    game_id=game_id,
                )
                if result.get("executed_source_name") != ROGRAKH:
                    raise SystemExit("B4-D expected the real Rograkh B4-C action")
                delta = client.request(
                    EngineMessageType.EXPORT_EVENT_LOG,
                    {"after_offset": initial_offset + passes},
                    game_id=game_id,
                )
                delta_events = [dict(item) for item in delta["log"]["events"]]
                _validate_events(delta_events)
                if len(delta_events) != 1 or delta_events[0]["event_type"] != "action_submitted":
                    raise SystemExit(
                        "B4-D did not link the real submitted action into the event stream"
                    )
                action_event = delta_events[0]
                payload = dict(action_event["payload"])
                if payload.get("decision_id") != decision.get("decision_id"):
                    raise SystemExit("B4-D event decision identity mismatch")
                if payload.get("action_id") != action.get("action_id"):
                    raise SystemExit("B4-D event action identity mismatch")
                if payload.get("source_name") != ROGRAKH:
                    raise SystemExit("B4-D event did not identify Rograkh")
                if len(str(action_event.get("pre_state_hash"))) != 64:
                    raise SystemExit("B4-D action event pre_state_hash is invalid")
                if len(str(action_event.get("post_state_hash"))) != 64:
                    raise SystemExit("B4-D action event post_state_hash is invalid")
                break

            pass_action = _unique_pass(decision)
            client.request(
                EngineMessageType.PASS_PRIORITY,
                {
                    "decision_id": str(decision["decision_id"]),
                    "actor_id": str(decision["actor_id"]),
                    "action_id": str(pass_action["action_id"]),
                },
                game_id=game_id,
            )
            passes += 1
        else:
            raise SystemExit("B4-D did not reach the real Rograkh cast within 64 decisions")

        if action_event is None:
            raise SystemExit("B4-D real action event was not recorded")

        full_before_shutdown = client.request(
            EngineMessageType.EXPORT_EVENT_LOG,
            {"after_offset": 0},
            game_id=game_id,
        )
        full_events = [dict(item) for item in full_before_shutdown["log"]["events"]]
        _validate_events(full_events)
        expected_before_shutdown = 2 + passes + 1
        if len(full_events) != expected_before_shutdown:
            raise SystemExit(
                f"B4-D event count mismatch: expected {expected_before_shutdown}, got {len(full_events)}"
            )
        state = GameState.model_validate(
            client.request(EngineMessageType.GET_GAME_STATE, {}, game_id=game_id)["state"]
        )
        if state.event_sequence != len(full_events):
            raise SystemExit("B4-D GameState.event_sequence does not match event log")

        shutdown = adapter.shutdown_game(game_id)
        if shutdown.get("shutdown") is not True:
            raise SystemExit("B4-D first game did not report successful shutdown")
        if int(shutdown.get("released_deck_handle_count", -1)) != 4:
            raise SystemExit("B4-D first shutdown did not release four deck handles")
        if int(shutdown.get("stored_game_count", -1)) != 0:
            raise SystemExit("B4-D first shutdown leaked a managed game")
        final_events = [dict(item) for item in shutdown["final_log"]["events"]]
        _validate_events(final_events)
        if final_events[-1]["event_type"] != "game_shutdown":
            raise SystemExit("B4-D final event is not game_shutdown")
        _expect_unknown_game(client, game_id)

        second_handles = tuple(adapter.import_deck(deck).handle_id for _ in range(4))
        second_game_id = "ci-b4d-event-log-lifecycle-second-4p"
        adapter.create_commander_game(
            RulesGameRequest(
                game_id=second_game_id,
                deck_handles=second_handles,
                starting_player_seat=1,
                starting_life=40,
                seed=None,
                external_control=False,
            )
        )
        adapter.start_game(second_game_id)
        second_log = adapter.export_event_log(second_game_id)
        if len(second_log.events) != 2:
            raise SystemExit("B4-D second game did not start with independent lifecycle events")
        second_shutdown = adapter.shutdown_game(second_game_id)
        if int(second_shutdown.get("stored_game_count", -1)) != 0:
            raise SystemExit("B4-D repeated-game shutdown leaked managed state")
        _expect_unknown_game(client, second_game_id)

        evidence.update(
            {
                "provider": adapter.get_provider_version(),
                "capabilities": caps.model_dump(mode="json"),
                "first_game_id": game_id,
                "priority_passes_logged": passes,
                "first_game_event_count_before_shutdown": len(full_events),
                "first_game_final_event_count": len(final_events),
                "first_game_final_event_offset": shutdown.get("final_event_offset"),
                "first_game_log_sha256": shutdown["final_log"]["log_sha256"],
                "real_action_event": action_event,
                "second_game_id": second_game_id,
                "second_game_started_and_shutdown": True,
                "resource_cleanup_verified": True,
                "status": "passed",
            }
        )
    finally:
        with contextlib.suppress(Exception):
            adapter.shutdown_engine()
        adapter.close()

    output = ROOT / "artifacts/external-engine/XMAGE_B4D_EVENT_LOG_LIFECYCLE.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
