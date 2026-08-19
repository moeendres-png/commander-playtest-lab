from __future__ import annotations

import contextlib
import json
import math
import os
from pathlib import Path

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


def main() -> None:
    request_timeout_seconds = _timeout_from_environment(
        "XMAGE_B4B_REQUEST_TIMEOUT_SECONDS",
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
        "scope": "xmage_b4b_first_real_priority_and_legal_action_enumeration",
        "automatic_canonical_mutation": False,
        "confirmatory_consumed": False,
        "sealed_holdout_consumed": False,
        "action_submission_exercised": False,
        "global_legal_actions_capability_promoted": False,
        "global_reason": (
            "only the first real priority decision class is proven; advancing through priority, "
            "combat and choice classes belongs to later B4 slices"
        ),
    }
    try:
        probe = adapter.probe()
        if probe.availability is not RulesEngineAvailability.AVAILABLE:
            raise SystemExit(f"XMage bridge is not available: {probe.model_dump(mode='json')}")

        capabilities = probe.capabilities
        if capabilities.legal_actions_supported:
            raise SystemExit("B4-B must not promote global legal_actions_supported")
        if capabilities.action_submission_supported:
            raise SystemExit("B4-B must not promote action_submission_supported")
        if capabilities.event_log_supported:
            raise SystemExit("B4-B must not promote event_log_supported")

        deck = _runtime_deck()
        handles = tuple(adapter.import_deck(deck).handle_id for _ in range(4))
        game_id = "ci-b4b-priority-4p"
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
            raise SystemExit(f"B4-B game identity mismatch: {created_id} != {game_id}")

        started = adapter.start_game(game_id)
        if started.get("external_control") is not True:
            raise SystemExit("B4-B game did not enter external-control mode")
        if started.get("paused") is not True:
            raise SystemExit("B4-B game did not pause at the external decision")
        if int(started.get("turn_number", -1)) != 1:
            raise SystemExit("B4-B game did not remain on turn 1")

        client = adapter._require_client()
        state_raw = client.request(EngineMessageType.GET_GAME_STATE, {}, game_id=game_id)
        state = GameState.model_validate(state_raw["state"])
        if state.step != "upkeep":
            raise SystemExit(f"B4-B expected first real upkeep priority, observed {state.step!r}")
        if state.priority_player_id is None:
            raise SystemExit("B4-B state did not expose priority player")

        first = client.request(EngineMessageType.GET_LEGAL_ACTIONS, {}, game_id=game_id)
        second = client.request(EngineMessageType.GET_LEGAL_ACTIONS, {}, game_id=game_id)

        if first.get("global_capability_promoted") is not False:
            raise SystemExit("B4-B widened global legal-actions capability")
        if first.get("decision_kind") != "priority":
            raise SystemExit(f"B4-B unexpected decision kind: {first.get('decision_kind')!r}")
        if first.get("actor_id") != state.priority_player_id:
            raise SystemExit("B4-B actor does not match real XMage priority player")
        if first.get("decision_id") != second.get("decision_id"):
            raise SystemExit("B4-B repeated query changed decision identity")
        if first.get("decision_offset") != second.get("decision_offset"):
            raise SystemExit("B4-B repeated query changed decision offset")
        if first.get("actions") != second.get("actions"):
            raise SystemExit("B4-B repeated query changed legal-action payload")

        actions = tuple(LegalAction.model_validate(item) for item in first.get("actions", ()))
        if not actions:
            raise SystemExit("B4-B exposed no actions")
        if len({action.action_id for action in actions}) != len(actions):
            raise SystemExit("B4-B action IDs are not unique")
        if any(action.actor_id != state.priority_player_id for action in actions):
            raise SystemExit("B4-B exposed action for the wrong actor")

        action_types = {action.action_type.value for action in actions}
        if "pass_priority" not in action_types:
            raise SystemExit("B4-B did not expose pass priority")

        evidence.update(
            {
                "provider": adapter.get_provider_version(),
                "capabilities": capabilities.model_dump(mode="json"),
                "game_id": game_id,
                "engine_game_id": str(first.get("engine_game_id")),
                "turn_number": state.turn_number,
                "phase": state.phase.value,
                "step": state.step,
                "actor_id": first.get("actor_id"),
                "decision_id": first.get("decision_id"),
                "decision_offset": first.get("decision_offset"),
                "decision_complete_for_priority_class": first.get("complete"),
                "action_count": len(actions),
                "action_types": sorted(action_types),
                "action_ids": [action.action_id for action in actions],
                "submission_ready_count": sum(
                    bool(action.metadata.get("submission_ready")) for action in actions
                ),
                "status": "passed",
            }
        )
    finally:
        with contextlib.suppress(Exception):
            adapter.shutdown_engine()
        adapter.close()

    output = ROOT / "artifacts/external-engine/XMAGE_B4B_DECISION_REGRESSION.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
