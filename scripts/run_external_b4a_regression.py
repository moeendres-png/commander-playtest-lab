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
        "XMAGE_B4A_REQUEST_TIMEOUT_SECONDS",
        30.0,
    )
    adapter = ExternalRulesAdapter(
        RulesBackend.XMAGE,
        cwd=ROOT,
        request_timeout_seconds=request_timeout_seconds,
    )
    evidence: dict[str, object] = {
        "schema_version": "1.1.0",
        "evidence_class": "external_rules_engine",
        "scope": "xmage_b4a_real_game_state_observation",
        "automatic_canonical_mutation": False,
        "confirmatory_consumed": False,
        "sealed_holdout_consumed": False,
        "seed_claim": "unknown_uncontrolled_for_this_run",
        "later_capabilities": "not_part_of_b4a_regression_contract",
    }
    try:
        probe = adapter.probe()
        if probe.availability is not RulesEngineAvailability.AVAILABLE:
            raise SystemExit(f"XMage bridge is not available: {probe.model_dump(mode='json')}")

        capabilities = probe.capabilities
        required = {
            "deck_import_supported": capabilities.deck_import_supported,
            "commander_supported": capabilities.commander_supported,
            "partner_supported": capabilities.partner_supported,
            "multiplayer_supported": capabilities.multiplayer_supported,
            "headless_supported": capabilities.headless_supported,
            "stack_visible": capabilities.stack_visible,
            "priority_visible": capabilities.priority_visible,
        }
        missing = sorted(name for name, value in required.items() if not value)
        if missing:
            raise SystemExit(f"B4-A capability regression: missing {missing}")

        deck = _runtime_deck()
        handles = tuple(adapter.import_deck(deck).handle_id for _ in range(4))
        game_id = "ci-b4a-state-4p"
        created_id = adapter.create_commander_game(
            RulesGameRequest(
                game_id=game_id,
                deck_handles=handles,
                starting_player_seat=0,
                starting_life=40,
                seed=None,
            )
        )
        if created_id != game_id:
            raise SystemExit(f"B4-A game identity mismatch: {created_id} != {game_id}")

        started = adapter.start_game(game_id)
        if int(started.get("turn_number", -1)) != 1 or started.get("paused") is not True:
            raise SystemExit("B4-A real game did not reach the bounded B3 handoff")

        client = adapter._require_client()
        first_raw = client.request(EngineMessageType.GET_GAME_STATE, {}, game_id=game_id)
        second_raw = client.request(EngineMessageType.GET_GAME_STATE, {}, game_id=game_id)
        state = GameState.model_validate(first_raw["state"])

        if state.game_id != game_id:
            raise SystemExit("B4-A state returned wrong game_id")
        if state.seed is not None or state.rng_counter is not None:
            raise SystemExit("B4-A invented a seed or RNG counter")
        if state.turn_number != 1 or state.step != "upkeep":
            raise SystemExit(
                f"B4-A unexpected turn/step: turn={state.turn_number}, step={state.step!r}"
            )
        if state.active_player_id is None:
            raise SystemExit("B4-A did not expose the real active player")
        if len(state.players) != 4:
            raise SystemExit("B4-A state did not expose four players")
        if state.stack:
            raise SystemExit("B4-A bounded handoff unexpectedly has a nonempty stack")

        for player in state.players:
            if player.life != 40:
                raise SystemExit(
                    f"B4-A unexpected life total for {player.player_id}: {player.life}"
                )
            if len(player.zones.hand) != 7:
                raise SystemExit(f"B4-A unexpected hand size for {player.player_id}")
            if len(player.zones.library) != 91:
                raise SystemExit(f"B4-A unexpected library size for {player.player_id}")
            if len(player.zones.command) != 2:
                raise SystemExit(f"B4-A commander zone mismatch for {player.player_id}")

        first_offset = int(first_raw.get("state_observation_offset", -1))
        second_offset = int(second_raw.get("state_observation_offset", -1))
        if first_offset < 1 or second_offset != first_offset + 1:
            raise SystemExit(
                f"B4-A state observation offset is not monotonic: {first_offset} -> {second_offset}"
            )
        if first_raw.get("seed_controlled") is not False:
            raise SystemExit("B4-A seed-control boundary is not explicit")
        if first_raw.get("legal_actions_complete") is not False:
            raise SystemExit("B4-A legal-action completeness boundary widened")

        evidence.update(
            {
                "provider": adapter.get_provider_version(),
                "capabilities": capabilities.model_dump(mode="json"),
                "game_id": game_id,
                "engine_game_id": str(first_raw.get("engine_game_id")),
                "state_observation_offsets": [first_offset, second_offset],
                "turn_number": state.turn_number,
                "phase": state.phase.value,
                "step": state.step,
                "active_player_id": state.active_player_id,
                "priority_player_id": state.priority_player_id,
                "player_count": len(state.players),
                "hand_sizes": [len(player.zones.hand) for player in state.players],
                "library_sizes": [len(player.zones.library) for player in state.players],
                "command_zone_sizes": [len(player.zones.command) for player in state.players],
                "stack_size": len(state.stack),
                "event_sequence_observed": state.event_sequence,
                "status": "passed",
            }
        )
    finally:
        with contextlib.suppress(Exception):
            adapter.shutdown_engine()
        adapter.close()

    output = ROOT / "artifacts/external-engine/XMAGE_B4A_STATE_REGRESSION.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
