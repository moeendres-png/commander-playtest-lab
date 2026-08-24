from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from commander_lab.agents import GenericCommanderPilot
from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules.full_game import (
    FULL_GAME_DECISION_PROTOCOL_VERSION,
    FULL_GAME_EVIDENCE_CLASS,
    ExternalPilotDecisionPolicy,
    FullGameConformanceResult,
    FullGamePilotBinding,
    FullGameProtocolError,
    XmageFullGameRunner,
    _RuntimePilot,
)
from commander_lab.engine.rules.full_game_batch import (
    FullGameBatchCase,
    FullGameFailureClass,
    XmageFullGameBatchRunner,
)
from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength, RulesDeckInput

XMAGE_COMMIT = "77d7646da6958fdf8125ee7c8f4aabd130d21d4c"


def _binding(seat: int, deck_id: str) -> FullGamePilotBinding:
    config = PilotConfig(
        pilot_name="auto",
        strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
        mode=PilotDecisionMode.DETERMINISTIC,
    )
    return FullGamePilotBinding(
        seat=seat,
        deck_id=deck_id,
        strategy="generic",
        commander_names=("Isamaru, Hound of Konda",),
        config=config,
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-full-game-policy-1.0.0",
    )


def _runtime_policy(seed: int = 7) -> ExternalPilotDecisionPolicy:
    runtimes = tuple(
        _RuntimePilot(
            binding=_binding(seat, f"fixture-{seat}"),
            pilot=GenericCommanderPilot(_binding(seat, f"fixture-{seat}").config),
        )
        for seat in range(1, 5)
    )
    return ExternalPilotDecisionPolicy(runtimes, seed)


def _actor_state() -> dict[str, Any]:
    players: list[dict[str, Any]] = [
        {
            "player_id": "actor",
            "seat": 0,
            "life": 40,
            "hand_count": 7,
            "library_count": 92,
            "graveyard_count": 0,
            "battlefield": [],
            "graveyard": [],
            "command": [{"object_id": "commander", "name": "Isamaru, Hound of Konda"}],
            "hand": [{"object_id": f"card-{index}", "name": "Plains"} for index in range(7)],
            "mana_pool": {
                "white": 0,
                "blue": 0,
                "black": 0,
                "red": 0,
                "green": 0,
                "colorless": 0,
            },
        }
    ]
    for seat in range(1, 4):
        players.append(
            {
                "player_id": f"opponent-{seat}",
                "seat": seat,
                "life": 40,
                "hand_count": 7,
                "library_count": 92,
                "graveyard_count": 0,
                "battlefield": [],
                "graveyard": [],
                "command": [],
            }
        )
    return {
        "game_id": "opaque-engine-game",
        "actor_id": "actor",
        "seat": 0,
        "turn_number": 1,
        "active_player_id": "actor",
        "priority_player_id": "actor",
        "phase": "precombat_main",
        "step": None,
        "players": players,
        "stack": [],
    }


def _boolean_request(*, decision_id: str, offset: int) -> dict[str, Any]:
    return {
        "decision_id": decision_id,
        "decision_offset": offset,
        "actor_id": "actor",
        "decision_class": "choose_use",
        "pilot_state": _actor_state(),
        "context": {"outcome": "benefit"},
        "minimum_selections": 1,
        "maximum_selections": 1,
        "legal_options": [
            {
                "option_id": "yes",
                "label": "Yes",
                "option_type": "boolean",
                "metadata": {"value": True},
            },
            {
                "option_id": "no",
                "label": "No",
                "option_type": "boolean",
                "metadata": {"value": False},
            },
        ],
    }


def _decks() -> tuple[RulesDeckInput, RulesDeckInput, RulesDeckInput, RulesDeckInput]:
    mainboard = tuple("Plains" for _ in range(99))
    return tuple(
        RulesDeckInput(
            deck_id=f"fixture-{seat}",
            name=f"Full-game fixture {seat}",
            commander_names=("Isamaru, Hound of Konda",),
            mainboard=mainboard,
            deck_hash=(f"{seat:x}" * 64)[:64],
        )
        for seat in range(1, 5)
    )  # type: ignore[return-value]


def _scenario(
    decks: tuple[RulesDeckInput, RulesDeckInput, RulesDeckInput, RulesDeckInput],
) -> FutureXmageScenario:
    assert decks[0].deck_hash is not None
    return FutureXmageScenario(
        candidate_id=decks[0].deck_id,
        deck_hash=decks[0].deck_hash,
        opponent_deck_ids=(decks[1].deck_id, decks[2].deck_id, decks[3].deck_id),
        player_count=4,
        seat=1,
        scenario_id="technical-full-game-smoke",
        seed=17,
        xmage_commit=XMAGE_COMMIT,
        bridge_version="xmage-engine-bridge-0.1.0-SNAPSHOT",
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-full-game-policy-1.0.0",
    )


def _result(scenario: FutureXmageScenario) -> FullGameConformanceResult:
    return FullGameConformanceResult(
        scenario=scenario,
        engine_version="1.4.61",
        xmage_commit=XMAGE_COMMIT,
        decision_protocol_version=FULL_GAME_DECISION_PROTOCOL_VERSION,
        decision_count=12,
        terminal=True,
        winner_seats=(1,),
        result_payload={
            "evidence_class": FULL_GAME_EVIDENCE_CLASS,
            "consumed_gameplay_evidence": False,
            "holdout_consumed": False,
            "official_campaign_eligible": False,
            "rules_authority": "xmage",
            "decision_policy_authority": "commander_lab_external_pilot",
            "seed": scenario.seed,
            "terminal": True,
            "outcomes": [{"seat": index, "won": index == 0} for index in range(4)],
            "transcript": [],
        },
        semantic_transcript_sha256="a" * 64,
        raw_result_sha256="b" * 64,
    )


def test_discretionary_boolean_choice_is_made_by_commander_lab_pilot() -> None:
    policy = _runtime_policy()
    response = policy.decide(_boolean_request(decision_id="engine-a", offset=3))
    assert response["selected_option_ids"] == ["yes"]


def test_pilot_rng_identity_does_not_depend_on_random_engine_game_uuid() -> None:
    first = _runtime_policy(seed=81).decide(_boolean_request(decision_id="engine-a", offset=9))
    second = _runtime_policy(seed=81).decide(_boolean_request(decision_id="engine-b", offset=9))
    assert first["selected_option_ids"] == second["selected_option_ids"]


def test_unknown_discretionary_decision_class_fails_closed() -> None:
    request = _boolean_request(decision_id="engine-a", offset=1)
    request["decision_class"] = "unmapped_future_choice"
    with pytest.raises(FullGameProtocolError, match="unsupported discretionary decision class"):
        _runtime_policy().decide(request)


def test_semantic_transcript_drops_private_state_and_engine_object_ids() -> None:
    semantic = XmageFullGameRunner.semantic_transcript(
        {
            "seed": 3,
            "turn_number": 2,
            "decision_count": 1,
            "transcript": [
                {
                    "sequence": 1,
                    "kind": "decision_accepted",
                    "decision_class": "priority",
                    "actor_seat": 0,
                    "prompt": "Choose priority action",
                    "selected_option_types": ["pass_priority"],
                    "selected_option_labels": ["Pass priority"],
                    "numeric_choice": None,
                    "pilot_state": {"hand": ["SECRET"]},
                    "object_id": "opaque-random-uuid",
                }
            ],
            "outcomes": [],
        }
    )
    encoded = json.dumps(semantic, sort_keys=True)
    assert "SECRET" not in encoded
    assert "opaque-random-uuid" not in encoded


def test_semantic_transcript_normalizes_xmage_process_local_prompt_ids() -> None:
    base = {
        "seed": 3,
        "turn_number": 2,
        "decision_count": 1,
        "outcomes": [],
    }
    first = {
        **base,
        "transcript": [
            {
                "sequence": 1,
                "kind": "decision_requested",
                "decision_class": "mana_payment",
                "actor_seat": 0,
                "prompt": (
                    "{W}<div><font object_id='64c42435-d2e2-4aa3-8ce7-7a77ecaecc00'>"
                    "Isamaru, Hound of Konda</font> [64c]</div>"
                ),
                "selected_option_types": None,
                "selected_option_labels": None,
                "numeric_choice": None,
            }
        ],
    }
    second = {
        **base,
        "transcript": [
            {
                "sequence": 1,
                "kind": "decision_requested",
                "decision_class": "mana_payment",
                "actor_seat": 0,
                "prompt": (
                    "{W}<div><font object_id='07f0fab5-af4b-4f72-905b-bd7184dfc56a'>"
                    "Isamaru, Hound of Konda</font> [07f]</div>"
                ),
                "selected_option_types": None,
                "selected_option_labels": None,
                "numeric_choice": None,
            }
        ],
    }
    first_semantic = XmageFullGameRunner.semantic_transcript(first)
    second_semantic = XmageFullGameRunner.semantic_transcript(second)
    assert first_semantic == second_semantic
    encoded = json.dumps(first_semantic, sort_keys=True)
    assert "object_id" not in encoded
    assert "64c42435" not in encoded


class _FakeRunner:
    def __init__(self, result: FullGameConformanceResult) -> None:
        self.result = result
        self.calls = 0

    def run(self, **_kwargs: object) -> FullGameConformanceResult:
        self.calls += 1
        return self.result


class _FailingRunner:
    def __init__(self) -> None:
        self.calls = 0

    def run(self, **_kwargs: object) -> FullGameConformanceResult:
        self.calls += 1
        raise FullGameProtocolError("synthetic protocol failure")


def test_batch_completed_result_is_content_addressed_and_resumed(tmp_path: Path) -> None:
    decks = _decks()
    scenario = _scenario(decks)
    case = FullGameBatchCase(
        case_id="case-1",
        scenario=scenario,
        decks=decks,
        pilots=tuple(_binding(seat, f"fixture-{seat}") for seat in range(1, 5)),  # type: ignore[arg-type]
    )
    fake = _FakeRunner(_result(scenario))
    batch = XmageFullGameBatchRunner(fake, tmp_path)  # type: ignore[arg-type]
    first = batch.run((case,))
    second = batch.run((case,))
    assert fake.calls == 1
    assert first.completed_cases == 1
    assert second.resumed_cases == 1
    assert second.records[0].resumed_from_completed_record is True
    assert second.records[0].consumed_gameplay_evidence is False
    assert second.records[0].holdout_consumed is False


def test_failed_batch_record_is_classified_and_not_silently_retried(tmp_path: Path) -> None:
    decks = _decks()
    scenario = _scenario(decks)
    case = FullGameBatchCase(
        case_id="case-failure",
        scenario=scenario,
        decks=decks,
        pilots=tuple(_binding(seat, f"fixture-{seat}") for seat in range(1, 5)),  # type: ignore[arg-type]
    )
    fake = _FailingRunner()
    batch = XmageFullGameBatchRunner(fake, tmp_path)  # type: ignore[arg-type]
    first = batch.run((case,))
    second = batch.run((case,))
    assert fake.calls == 1
    assert first.failed_cases == 1
    assert second.records[0].failure_class is FullGameFailureClass.PROTOCOL
    assert second.records[0].official_campaign_eligible is False
