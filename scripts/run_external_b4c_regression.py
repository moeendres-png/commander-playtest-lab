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
    LegalAction,
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


def _pass_payload(decision: dict[str, Any]) -> dict[str, Any]:
    pass_actions = [
        action for action in decision.get("actions", ()) if action.get("action_type") == "pass_priority"
    ]
    if len(pass_actions) != 1:
        raise SystemExit(f"B4-C expected exactly one pass action, observed {len(pass_actions)}")
    action = pass_actions[0]
    return {
        "decision_id": str(decision["decision_id"]),
        "actor_id": str(decision["actor_id"]),
        "action_id": str(action["action_id"]),
    }


def _proposal(decision: dict[str, Any], action: dict[str, Any]) -> dict[str, Any]:
    return {
        "proposal_id": f"b4c/{decision['decision_id']}/{action['action_id']}",
        "actor_id": str(decision["actor_id"]),
        "legal_action_id": str(action["action_id"]),
        "action_type": str(action["action_type"]),
        "source_object_id": str(action["source_object_id"]),
        "target_ids": [],
        "selected_modes": [],
        "choices": {},
        "decision_tier": 1,
        "policy_name": "b4c-real-regression",
        "rationale": "bounded real-XMage B4-C validation",
    }


def _expect_stale(
    client: Any,
    message_type: EngineMessageType,
    payload: dict[str, Any],
    *,
    game_id: str,
) -> None:
    try:
        client.request(message_type, payload, game_id=game_id)
    except RulesEngineProtocolError as exc:
        message = str(exc)
        if "STALE_EXTERNAL_DECISION" not in message and "STALE_OR_UNKNOWN_EXTERNAL_ACTION" not in message:
            raise SystemExit(f"B4-C stale replay failed for an unexpected reason: {message}") from exc
        return
    raise SystemExit("B4-C stale decision/action replay unexpectedly mutated or succeeded")


def _player_command_zone(state: GameState, player_id: str) -> tuple[str, ...]:
    for player in state.players:
        if player.player_id == player_id:
            return player.zones.command
    raise SystemExit(f"B4-C could not find actor {player_id} in state")


def main() -> None:
    request_timeout_seconds = _timeout_from_environment(
        "XMAGE_B4C_REQUEST_TIMEOUT_SECONDS",
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
        "scope": "xmage_b4c_bounded_priority_submission_and_real_rograkh_cast",
        "automatic_canonical_mutation": False,
        "confirmatory_consumed": False,
        "sealed_holdout_consumed": False,
        "global_legal_actions_capability_promoted": False,
        "global_action_submission_capability_promoted": False,
        "global_reason": (
            "B4-C proves bounded current-priority PASS_PRIORITY and submission-ready targetless/nonmodal "
            "action execution only; combat, targets, modes and other choice classes remain incomplete"
        ),
    }
    try:
        probe = adapter.probe()
        if probe.availability is not RulesEngineAvailability.AVAILABLE:
            raise SystemExit(f"XMage bridge is not available: {probe.model_dump(mode='json')}")
        capabilities = probe.capabilities
        if capabilities.legal_actions_supported:
            raise SystemExit("B4-C must not globally promote legal_actions_supported")
        if capabilities.action_submission_supported:
            raise SystemExit("B4-C must not globally promote action_submission_supported")
        if capabilities.event_log_supported:
            raise SystemExit("B4-C must not promote event_log_supported")

        deck = _runtime_deck()
        if ROGRAKH not in deck.commander_names:
            raise SystemExit("B4-C current RogShai runtime deck does not contain Rograkh")
        handles = tuple(adapter.import_deck(deck).handle_id for _ in range(4))
        game_id = "ci-b4c-rograkh-cast-4p"
        created_id = adapter.create_commander_game(
            RulesGameRequest(
                game_id=game_id,
                deck_handles=handles,
                starting_player_seat=0,
                starting_life=40,
                seed=None,
                external_control=True,
            )
        )
        if created_id != game_id:
            raise SystemExit(f"B4-C game identity mismatch: {created_id} != {game_id}")
        started = adapter.start_game(game_id)
        if started.get("external_control") is not True or started.get("paused") is not True:
            raise SystemExit("B4-C game did not pause under external control")

        client = adapter._require_client()
        stale_pass_rejected = False
        stale_submit_rejected = False
        passes_submitted = 0
        observed_steps: list[str | None] = []
        cast_evidence: dict[str, object] | None = None

        for iteration in range(64):
            state_raw = client.request(EngineMessageType.GET_GAME_STATE, {}, game_id=game_id)
            state = GameState.model_validate(state_raw["state"])
            observed_steps.append(state.step)
            decision = client.request(EngineMessageType.GET_LEGAL_ACTIONS, {}, game_id=game_id)

            if decision.get("global_capability_promoted") is not False:
                raise SystemExit("B4-C widened global legal-action capability")
            if decision.get("actor_id") != state.priority_player_id:
                raise SystemExit("B4-C decision actor does not match XMage priority player")

            raw_actions = tuple(dict(action) for action in decision.get("actions", ()))
            actions = tuple(LegalAction.model_validate(action) for action in raw_actions)
            if not actions:
                raise SystemExit("B4-C observed an empty priority action set")

            commander_actions = [
                action
                for action in raw_actions
                if action.get("action_type") == "cast_commander"
                and bool(action.get("metadata", {}).get("submission_ready"))
                and not bool(action.get("metadata", {}).get("choice_control_required"))
            ]

            if commander_actions:
                if len(commander_actions) != 1:
                    raise SystemExit(
                        "B4-C expected the zero-mana Rograkh action to be the unique submission-ready commander cast"
                    )
                action = commander_actions[0]
                source_id = str(action["source_object_id"])
                before_command = _player_command_zone(state, str(decision["actor_id"]))
                if source_id not in before_command:
                    raise SystemExit("B4-C commander source is not in the actor command zone before cast")

                proposal = _proposal(decision, action)
                payload = {
                    "decision_id": str(decision["decision_id"]),
                    "proposal": proposal,
                }
                result = client.request(EngineMessageType.SUBMIT_ACTION, payload, game_id=game_id)
                if result.get("bounded_submission") is not True:
                    raise SystemExit("B4-C submit result is not marked bounded")
                if result.get("global_capability_promoted") is not False:
                    raise SystemExit("B4-C submit result widened global capability")
                if result.get("executed_source_name") != ROGRAKH:
                    raise SystemExit(
                        f"B4-C expected real Rograkh execution, got {result.get('executed_source_name')!r}"
                    )
                if result.get("executed_action_type") != "cast_commander":
                    raise SystemExit("B4-C did not execute the enumerated cast_commander action")

                after = GameState.model_validate(result["state"])
                after_command = _player_command_zone(after, str(decision["actor_id"]))
                if source_id in after_command:
                    raise SystemExit("B4-C Rograkh remained in command zone after successful XMage cast")
                if not after.stack:
                    raise SystemExit("B4-C Rograkh cast did not produce a real XMage stack object")
                next_decision = dict(result["next_decision"])
                if next_decision.get("decision_id") == decision.get("decision_id"):
                    raise SystemExit("B4-C submit did not advance to a new external decision")

                _expect_stale(
                    client,
                    EngineMessageType.SUBMIT_ACTION,
                    payload,
                    game_id=game_id,
                )
                stale_submit_rejected = True
                cast_evidence = {
                    "iteration": iteration,
                    "source_object_id": source_id,
                    "source_name": result.get("executed_source_name"),
                    "executed_decision_id": result.get("executed_decision_id"),
                    "executed_action_id": result.get("executed_action_id"),
                    "next_decision_id": next_decision.get("decision_id"),
                    "stack_size_after_cast": len(after.stack),
                    "command_zone_size_before": len(before_command),
                    "command_zone_size_after": len(after_command),
                    "turn_number": after.turn_number,
                    "phase": after.phase.value,
                    "step": after.step,
                }
                break

            pass_payload = _pass_payload(decision)
            pass_result = client.request(
                EngineMessageType.PASS_PRIORITY,
                pass_payload,
                game_id=game_id,
            )
            passes_submitted += 1
            if pass_result.get("executed_action_type") != "pass_priority":
                raise SystemExit("B4-C PASS_PRIORITY did not execute the real pass action")
            if pass_result.get("bounded_submission") is not True:
                raise SystemExit("B4-C pass result is not marked bounded")
            if dict(pass_result["next_decision"]).get("decision_id") == decision.get("decision_id"):
                raise SystemExit("B4-C PASS_PRIORITY did not advance the external decision")
            if not stale_pass_rejected:
                _expect_stale(
                    client,
                    EngineMessageType.PASS_PRIORITY,
                    pass_payload,
                    game_id=game_id,
                )
                stale_pass_rejected = True
        else:
            raise SystemExit("B4-C did not reach a submission-ready Rograkh cast within 64 decisions")

        if cast_evidence is None:
            raise SystemExit("B4-C did not record Rograkh cast evidence")
        if not stale_pass_rejected or not stale_submit_rejected:
            raise SystemExit("B4-C stale-decision protection was not proven for both pass and submit")

        evidence.update(
            {
                "provider": adapter.get_provider_version(),
                "capabilities": capabilities.model_dump(mode="json"),
                "game_id": game_id,
                "passes_submitted": passes_submitted,
                "stale_pass_rejected": stale_pass_rejected,
                "stale_submit_rejected": stale_submit_rejected,
                "observed_steps": observed_steps,
                "real_rograkh_cast": cast_evidence,
                "status": "passed",
            }
        )
    finally:
        with contextlib.suppress(Exception):
            adapter.shutdown_engine()
        adapter.close()

    output = ROOT / "artifacts/external-engine/XMAGE_B4C_ACTION_REGRESSION.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
