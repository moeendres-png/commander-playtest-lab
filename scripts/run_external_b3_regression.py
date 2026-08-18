from __future__ import annotations

import json
from pathlib import Path

from commander_lab.engine.rules.bridge import ExternalRulesAdapter
from commander_lab.models import (
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


def main() -> None:
    adapter = ExternalRulesAdapter(RulesBackend.XMAGE, cwd=ROOT)
    evidence: dict[str, object] = {
        "schema_version": "1.0.0",
        "evidence_class": "external_rules_engine",
        "scope": "xmage_b3_process_regression",
        "automatic_canonical_mutation": False,
        "unsupported_capabilities_exercised": [],
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
        }
        missing = sorted(name for name, value in required.items() if not value)
        if missing:
            raise SystemExit(f"B3 capability regression: missing {missing}")
        if (capabilities.max_players or 0) < 5:
            raise SystemExit("B3 capability regression: max_players < 5")

        forbidden_claims = {
            "seed_supported": capabilities.seed_supported,
            "legal_actions_supported": capabilities.legal_actions_supported,
            "action_submission_supported": capabilities.action_submission_supported,
            "event_log_supported": capabilities.event_log_supported,
            "replay_supported": capabilities.replay_supported,
        }
        unexpectedly_enabled = sorted(name for name, value in forbidden_claims.items() if value)
        if unexpectedly_enabled:
            raise SystemExit(
                "B3 evidence boundary widened without an authorized phase: "
                + ", ".join(unexpectedly_enabled)
            )

        deck = _runtime_deck()
        runs: list[dict[str, object]] = []
        for player_count in range(2, 6):
            handles = tuple(adapter.import_deck(deck).handle_id for _ in range(player_count))
            game_id = f"ci-b3-{player_count}p"
            created_id = adapter.create_commander_game(
                RulesGameRequest(
                    game_id=game_id,
                    deck_handles=handles,
                    starting_player_seat=player_count - 1,
                    starting_life=40,
                )
            )
            if created_id != game_id:
                raise SystemExit(
                    f"B3 game identity mismatch for {player_count}P: {created_id} != {game_id}"
                )
            started = adapter.start_game(game_id)
            if int(started.get("player_count", -1)) != player_count:
                raise SystemExit(f"B3 player-count mismatch for {player_count}P")
            if int(started.get("turn_number", -1)) != 1:
                raise SystemExit(f"B3 start did not reach turn 1 for {player_count}P")
            if started.get("paused") is not True:
                raise SystemExit(f"B3 start did not reach the bounded pause for {player_count}P")
            runs.append(
                {
                    "player_count": player_count,
                    "game_id": game_id,
                    "deck_handles": len(handles),
                    "turn_number": int(started["turn_number"]),
                    "paused": True,
                }
            )

        evidence.update(
            {
                "provider": adapter.get_provider_version(),
                "capabilities": capabilities.model_dump(mode="json"),
                "proven_capabilities": [
                    "real_deck_import",
                    "commander_partner_game_construction",
                    "multiplayer_2_to_5_player_construction",
                    "real_game_start",
                    "bounded_pause_lifecycle",
                ],
                "not_claimed": sorted(forbidden_claims),
                "runs": runs,
                "status": "passed",
            }
        )
    finally:
        adapter.shutdown_engine()

    output = ROOT / "artifacts/external-engine/XMAGE_B3_PROCESS_REGRESSION.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
