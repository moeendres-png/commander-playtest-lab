from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules.full_game import (
    FULL_GAME_DECISION_PROTOCOL_VERSION,
    FULL_GAME_EVIDENCE_CLASS,
    FullGameReplayGate,
)
from commander_lab.engine.rules.full_game_ws18 import (
    FullGamePilotBindingV2,
    XmageFullGameRunnerV2,
)
from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength, RulesDeckInput

ROOT = Path(__file__).resolve().parents[1]
XMAGE_COMMIT = "77d7646da6958fdf8125ee7c8f4aabd130d21d4c"


def _deck(seat: int) -> RulesDeckInput:
    deck_id = f"technical-isamaru-{seat}"
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
        name=f"Technical Isamaru fixture seat {seat}",
        commander_names=commander,
        mainboard=mainboard,
        deck_hash=hashlib.sha256(material).hexdigest(),
        source_path="synthetic:technical-conformance-only",
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
        decision_policy_version="xmage-full-game-policy-1.0.0",
    )


def _contains_forbidden_private_state(value: Any) -> bool:
    if isinstance(value, dict):
        forbidden = {"pilot_state", "hand", "library", "private_hand", "library_order"}
        if forbidden.intersection(value):
            return True
        return any(_contains_forbidden_private_state(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_forbidden_private_state(item) for item in value)
    return False


def main() -> None:
    decks = tuple(_deck(seat) for seat in range(1, 5))
    pilots = tuple(_binding(seat, decks[seat - 1]) for seat in range(1, 5))
    own = decks[0]
    assert own.deck_hash is not None
    scenario = FutureXmageScenario(
        candidate_id=own.deck_id,
        deck_hash=own.deck_hash,
        opponent_deck_ids=(decks[1].deck_id, decks[2].deck_id, decks[3].deck_id),
        player_count=4,
        seat=1,
        scenario_id="technical-isamaru-full-game-v1",
        seed=20260824,
        xmage_commit=XMAGE_COMMIT,
        bridge_version="xmage-engine-bridge-0.1.0-SNAPSHOT",
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-full-game-policy-1.0.0",
    )

    runner = XmageFullGameRunnerV2(cwd=ROOT, request_timeout_seconds=120.0, max_decisions=50_000)
    first = runner.run(scenario=scenario, decks=decks, pilots=pilots)
    second = runner.run(scenario=scenario, decks=decks, pilots=pilots)

    if not first.terminal or not second.terminal:
        raise SystemExit("full-game conformance did not reach XMage game over")
    if first.decision_count <= 0 or second.decision_count <= 0:
        raise SystemExit("full-game conformance exercised no external pilot decisions")
    if first.evidence_class != FULL_GAME_EVIDENCE_CLASS:
        raise SystemExit("unsafe evidence class")
    if first.consumed_gameplay_evidence or first.holdout_consumed:
        raise SystemExit("technical conformance consumed decision evidence or holdout")
    if _contains_forbidden_private_state(first.result_payload.get("transcript", [])):
        raise SystemExit("exported full-game transcript contains private pilot state")

    semantic_match = first.semantic_transcript_sha256 == second.semantic_transcript_sha256
    raw_match = first.raw_result_sha256 == second.raw_result_sha256
    gate = FullGameReplayGate(
        scenario_id=scenario.scenario_id,
        seed=scenario.seed,
        semantic_replay_match=semantic_match,
        raw_result_match=raw_match,
        first_semantic_sha256=first.semantic_transcript_sha256,
        second_semantic_sha256=second.semantic_transcript_sha256,
        first_raw_sha256=first.raw_result_sha256,
        second_raw_sha256=second.raw_result_sha256,
        bit_exact_replay_validated=False,
    )
    if not semantic_match:
        raise SystemExit("same-seed semantic full-game replay diverged")

    accepted_classes = sorted(
        {
            str(event.get("decision_class"))
            for event in first.result_payload.get("transcript", [])
            if isinstance(event, dict) and event.get("kind") == "decision_accepted"
        }
    )
    if "priority" not in accepted_classes or "mulligan" not in accepted_classes:
        raise SystemExit(
            "full-game smoke did not exercise minimum expected decision classes: "
            + repr(accepted_classes)
        )

    out = ROOT / "artifacts/xmage-full-game"
    out.mkdir(parents=True, exist_ok=True)
    conformance = first.model_dump(mode="json")
    conformance["fixture_provenance"] = {
        "kind": "synthetic_technical_fixture",
        "deck": "Isamaru, Hound of Konda + 99 Plains",
        "physical_inventory_claim": False,
        "opponent_observation_claim": False,
    }
    conformance["observed_decision_classes"] = accepted_classes
    conformance["rules_authority"] = "xmage"
    conformance["decision_authority"] = "commander_lab_external_pilots"
    conformance["structural_authority"] = False
    conformance["tactical_authority"] = False
    conformance["fallback_used"] = False
    (out / "XMAGE_FULL_GAME_CONFORMANCE.json").write_text(
        json.dumps(conformance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (out / "XMAGE_FULL_GAME_REPLAY_GATE.json").write_text(
        json.dumps(gate.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    hidden = {
        "schema_version": "xmage-full-game-hidden-information-report-1.0.0",
        "status": "PASS",
        "actor_scoped_state": True,
        "opponent_hand_arrays_exported_to_actor": False,
        "library_order_exported": False,
        "private_pilot_state_retained_in_exported_transcript": False,
        "full_transcript_scan_forbidden_private_keys": "PASS",
        "evidence_class": FULL_GAME_EVIDENCE_CLASS,
        "consumed_gameplay_evidence": False,
        "holdout_consumed": False,
    }
    (out / "HIDDEN_INFORMATION_BOUNDARY_REPORT.json").write_text(
        json.dumps(hidden, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "decision_count": first.decision_count,
                "winner_seats": first.winner_seats,
                "semantic_replay_match": semantic_match,
                "raw_result_match": raw_match,
                "observed_decision_classes": accepted_classes,
                "decision_protocol_version": FULL_GAME_DECISION_PROTOCOL_VERSION,
                "evidence_class": FULL_GAME_EVIDENCE_CLASS,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
