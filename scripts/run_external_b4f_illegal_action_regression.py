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
OUTPUT = ROOT / "artifacts/external-engine/XMAGE_B4F_ILLEGAL_ACTION_REJECTION.json"


def _runtime_deck() -> RulesDeckInput:
    payload = json.loads((ROOT / "data/decks/rogshai_current.json").read_text(encoding="utf-8"))
    commanders = tuple(str(name) for name in payload["commander"]["commanders"])
    mainboard: list[str] = []
    for row in payload["cards"]:
        if row["zone"] == "main":
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


def _pass_payload(decision: dict[str, Any]) -> dict[str, str]:
    pass_actions = [
        action
        for action in decision.get("actions", ())
        if action.get("action_type") == "pass_priority"
    ]
    if len(pass_actions) != 1:
        raise SystemExit(
            f"B4-F illegal-action gate expected one pass action, observed {len(pass_actions)}"
        )
    return {
        "decision_id": str(decision["decision_id"]),
        "actor_id": str(decision["actor_id"]),
        "action_id": str(pass_actions[0]["action_id"]),
    }


def main() -> None:
    timeout_seconds = _timeout_from_environment("XMAGE_B4F_REQUEST_TIMEOUT_SECONDS", 30.0)
    adapter = ExternalRulesAdapter(
        RulesBackend.XMAGE,
        cwd=ROOT,
        request_timeout_seconds=timeout_seconds,
    )
    evidence: dict[str, object] = {
        "schema_version": "1.0.0",
        "evidence_class": "external_rules_engine",
        "scope": "xmage_b4f_current_decision_illegal_action_rejection_4p",
        "automatic_canonical_mutation": False,
        "sealed_holdout_consumed": False,
    }
    try:
        probe = adapter.probe()
        if probe.availability is not RulesEngineAvailability.AVAILABLE:
            raise SystemExit(f"XMage bridge unavailable: {probe.model_dump(mode='json')}")

        deck = _runtime_deck()
        handles = tuple(adapter.import_deck(deck).handle_id for _ in range(4))
        game_id = "ci-b4f-illegal-action-4p"
        adapter.create_commander_game(
            RulesGameRequest(
                game_id=game_id,
                deck_handles=handles,
                starting_player_seat=0,
                starting_life=40,
                seed=None,
                external_control=True,
            )
        )
        started = adapter.start_game(game_id)
        if started.get("paused") is not True or started.get("external_control") is not True:
            raise SystemExit("B4-F illegal-action game did not reach external-control pause")

        client = adapter._require_client()
        before_raw = client.request(EngineMessageType.GET_GAME_STATE, {}, game_id=game_id)
        before = GameState.model_validate(before_raw["state"])
        decision_before = client.request(
            EngineMessageType.GET_LEGAL_ACTIONS,
            {},
            game_id=game_id,
        )
        if decision_before.get("actor_id") != before.priority_player_id:
            raise SystemExit("B4-F illegal-action actor does not match live XMage priority")
        enumerated_ids = {
            str(action["action_id"])
            for action in decision_before.get("actions", ())
        }
        illegal_action_id = "b4f-illegal-action-not-enumerated"
        if illegal_action_id in enumerated_ids:
            raise SystemExit("B4-F illegal-action sentinel unexpectedly exists in legal actions")

        illegal_payload = {
            "decision_id": str(decision_before["decision_id"]),
            "proposal": {
                "proposal_id": "b4f/illegal-action-rejection",
                "actor_id": str(decision_before["actor_id"]),
                "legal_action_id": illegal_action_id,
                "action_type": "cast_commander",
                "source_object_id": "b4f-illegal-source-not-enumerated",
                "target_ids": [],
                "selected_modes": [],
                "choices": {},
                "decision_tier": 1,
                "policy_name": "b4f-illegal-action-regression",
                "rationale": "prove rejection of a non-enumerated action in a current state-bound decision",
            },
        }

        rejection_message: str | None = None
        try:
            client.request(
                EngineMessageType.SUBMIT_ACTION,
                illegal_payload,
                game_id=game_id,
            )
        except RulesEngineProtocolError as exc:
            rejection_message = str(exc)
            if "STALE_OR_UNKNOWN_EXTERNAL_ACTION" not in rejection_message:
                raise SystemExit(
                    "B4-F illegal action was rejected for an unexpected reason: "
                    + rejection_message
                ) from exc
        else:
            raise SystemExit("B4-F non-enumerated current-decision action unexpectedly succeeded")

        after_raw = client.request(EngineMessageType.GET_GAME_STATE, {}, game_id=game_id)
        after = GameState.model_validate(after_raw["state"])
        decision_after = client.request(
            EngineMessageType.GET_LEGAL_ACTIONS,
            {},
            game_id=game_id,
        )
        state_unchanged = before.model_dump(mode="json") == after.model_dump(mode="json")
        decision_unchanged = (
            decision_before.get("decision_id") == decision_after.get("decision_id")
            and decision_before.get("actor_id") == decision_after.get("actor_id")
            and [action.get("action_id") for action in decision_before.get("actions", ())]
            == [action.get("action_id") for action in decision_after.get("actions", ())]
        )
        if not state_unchanged or not decision_unchanged:
            raise SystemExit("B4-F illegal-action rejection mutated provider state or decision")

        valid_pass = client.request(
            EngineMessageType.PASS_PRIORITY,
            _pass_payload(decision_after),
            game_id=game_id,
        )
        if valid_pass.get("executed_action_type") != "pass_priority":
            raise SystemExit("B4-F provider did not remain usable after illegal-action rejection")

        evidence.update(
            {
                "provider": adapter.get_provider_version(),
                "game_id": game_id,
                "player_count": 4,
                "decision_id": decision_before.get("decision_id"),
                "enumerated_action_count": len(enumerated_ids),
                "submitted_illegal_action_id": illegal_action_id,
                "rejection": "STALE_OR_UNKNOWN_EXTERNAL_ACTION",
                "rejection_message": rejection_message,
                "state_unchanged_after_rejection": state_unchanged,
                "decision_unchanged_after_rejection": decision_unchanged,
                "valid_action_succeeded_after_rejection": True,
                "status": "passed",
            }
        )
    finally:
        with contextlib.suppress(Exception):
            adapter.shutdown_engine()
        adapter.close()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(OUTPUT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
