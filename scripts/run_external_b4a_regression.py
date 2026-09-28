from __future__ import annotations

import contextlib
import json
import math
import os
from pathlib import Path

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
from commander_lab.qualification.current_boundary.full107 import validate_principal_scoping

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

        # A principal is mandatory. The pre-remediation B4-A regression sent an
        # empty request and therefore exercised the global, unscoped snapshot.
        # Pin the fail-closed contract first so a future seat-0 fallback cannot
        # silently revive that path.
        try:
            client.request(EngineMessageType.GET_GAME_STATE, {}, game_id=game_id)
        except RulesEngineProtocolError as exc:
            if "observer_player_id_required" not in str(exc):
                raise SystemExit(f"B4-A wrong omitted-observer failure: {exc}") from exc
        else:
            raise SystemExit("B4-A omitted observer_player_id did not fail closed")

        try:
            client.request(
                EngineMessageType.GET_GAME_STATE,
                {"observer_player_id": "not-a-live-principal"},
                game_id=game_id,
            )
        except RulesEngineProtocolError as exc:
            if "UNKNOWN_OBSERVER_PLAYER_ID" not in str(exc):
                raise SystemExit(f"B4-A wrong unknown-observer failure: {exc}") from exc
        else:
            raise SystemExit("B4-A unknown observer_player_id did not fail closed")

        requested = ("p1", "p2", "p3", "p4")
        raw_views: dict[str, dict[str, object]] = {}
        states: dict[str, GameState] = {}
        offsets: list[int] = []
        bindings: list[dict[str, object]] = []

        for expected_seat, principal in enumerate(requested):
            raw = client.request(
                EngineMessageType.GET_GAME_STATE,
                {"observer_player_id": principal},
                game_id=game_id,
            )
            state = GameState.model_validate(raw["state"])
            raw_views[principal] = raw
            states[principal] = state

            if raw.get("observer_player_id") != principal:
                raise SystemExit(f"B4-A requester echo mismatch for {principal}")
            if raw.get("observer_seat") != expected_seat:
                raise SystemExit(f"B4-A observer seat mismatch for {principal}")
            engine_id = raw.get("observer_engine_player_id")
            if not isinstance(engine_id, str) or not engine_id:
                raise SystemExit(f"B4-A live engine principal id missing for {principal}")
            if state.players[expected_seat].player_id != engine_id:
                raise SystemExit(f"B4-A observer binding does not match state row for {principal}")

            if state.game_id != game_id:
                raise SystemExit("B4-A state returned wrong game_id")
            if state.seed is not None or state.rng_counter is not None:
                raise SystemExit("B4-A invented a seed or RNG counter")
            if state.turn_number != 1 or state.step != "upkeep":
                raise SystemExit(
                    f"B4-A unexpected turn/step: turn={state.turn_number}, step={state.step!r}"
                )
            if state.active_player_id is None:
                raise SystemExit("B4-A did not expose the active player")
            if len(state.players) != 4:
                raise SystemExit("B4-A state did not expose four players")
            if state.stack:
                raise SystemExit("B4-A bounded handoff unexpectedly has a nonempty stack")

            for seat, player in enumerate(state.players):
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

                hand = list(player.zones.hand)
                if seat == expected_seat:
                    if any(card == "<hidden>" for card in hand):
                        raise SystemExit(f"B4-A hid the requester's own hand for {principal}")
                elif any(card != "<hidden>" for card in hand):
                    raise SystemExit(
                        f"B4-A exposed opponent hand identity to requester {principal}"
                    )

                library = list(player.zones.library)
                if any(card != "<hidden>" for card in library):
                    raise SystemExit(
                        f"B4-A exposed library identity/order to requester {principal}"
                    )

                expected_player_id = engine_id if seat == expected_seat else f"op-{seat}"
                if player.player_id != expected_player_id:
                    raise SystemExit(
                        f"B4-A principal id projection mismatch for {principal}, seat {seat}"
                    )

            offset = int(raw.get("state_observation_offset", -1))
            offsets.append(offset)
            if raw.get("seed_controlled") is not False:
                raise SystemExit("B4-A seed-control boundary is not explicit")
            if raw.get("legal_actions_complete") is not False:
                raise SystemExit("B4-A legal-action completeness boundary widened")
            bindings.append(
                {
                    "requester": principal,
                    "observer_seat": expected_seat,
                    "engine_id_matches_state_row": True,
                }
            )

        if offsets[0] < 1 or offsets != list(range(offsets[0], offsets[0] + len(offsets))):
            raise SystemExit(f"B4-A state observation offsets are not monotonic: {offsets}")

        canonical_states = {
            json.dumps(raw_views[principal]["state"], sort_keys=True, separators=(",", ":"))
            for principal in requested
        }
        if len(canonical_states) != 4:
            raise SystemExit(
                f"B4-A principal views are not independently scoped: {len(canonical_states)} distinct"
            )

        scoping = validate_principal_scoping(raw_views, requested_seats=requested)
        if scoping.get("verdict") != "PRINCIPAL_SCOPED":
            raise SystemExit(
                "B4-A shared qualification validator rejected principal scoping: "
                + json.dumps(scoping, sort_keys=True)
            )

        engine_ids = {
            principal: str(raw_views[principal]["observer_engine_player_id"])
            for principal in requested
        }
        for principal in requested:
            serialized = json.dumps(raw_views[principal]["state"], sort_keys=True)
            for other, engine_id in engine_ids.items():
                if other != principal and engine_id in serialized:
                    raise SystemExit(
                        f"B4-A requester {principal} received foreign live principal id {other}"
                    )

        first_state = states["p1"]
        evidence.update(
            {
                "provider": adapter.get_provider_version(),
                "capabilities": capabilities.model_dump(mode="json"),
                "game_id": game_id,
                "engine_game_id": str(raw_views["p1"].get("engine_game_id")),
                "principal_scoping": {
                    "requesters": list(requested),
                    "distinct_state_views": len(canonical_states),
                    "bindings": bindings,
                    "opponent_hands_placeholder_only": True,
                    "libraries_placeholder_only": True,
                    "foreign_live_principal_ids_absent": True,
                    "omitted_observer_fails_closed": True,
                    "unknown_observer_fails_closed": True,
                    "shared_validator_verdict": scoping.get("verdict"),
                    "shared_validator_attribution": scoping.get("attribution"),
                    "shared_validator_findings": scoping.get("findings"),
                },
                "state_observation_offsets": offsets,
                "turn_number": first_state.turn_number,
                "phase": first_state.phase.value,
                "step": first_state.step,
                "player_count": len(first_state.players),
                "hand_sizes": [len(player.zones.hand) for player in first_state.players],
                "library_sizes": [len(player.zones.library) for player in first_state.players],
                "command_zone_sizes": [len(player.zones.command) for player in first_state.players],
                "stack_size": len(first_state.stack),
                "event_sequence_observed": first_state.event_sequence,
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
