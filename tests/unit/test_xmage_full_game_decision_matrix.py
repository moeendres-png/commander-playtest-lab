from __future__ import annotations

from typing import Any

import pytest

from commander_lab.agents import GenericCommanderPilot
from commander_lab.engine.rules.full_game import (
    ExternalPilotDecisionPolicy,
    FullGamePilotBinding,
    _RuntimePilot,
)
from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength


def _policy() -> ExternalPilotDecisionPolicy:
    runtimes: list[_RuntimePilot] = []
    for seat in range(1, 5):
        config = PilotConfig(
            pilot_name="auto",
            strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
            mode=PilotDecisionMode.DETERMINISTIC,
        )
        binding = FullGamePilotBinding(
            seat=seat,
            deck_id=f"fixture-{seat}",
            strategy="generic",
            commander_names=("Isamaru, Hound of Konda",),
            config=config,
            pilot_identity="GenericCommanderPilot",
            pilot_version="1.0.0",
            decision_policy_version="xmage-full-game-policy-1.0.0",
        )
        runtimes.append(_RuntimePilot(binding=binding, pilot=GenericCommanderPilot(config)))
    return ExternalPilotDecisionPolicy(tuple(runtimes), 20260824)  # type: ignore[arg-type]


def _state() -> dict[str, Any]:
    actor = {
        "player_id": "actor",
        "seat": 0,
        "life": 40,
        "hand_count": 7,
        "library_count": 92,
        "graveyard_count": 0,
        "battlefield": [],
        "graveyard": [],
        "command": [{"object_id": "commander", "name": "Isamaru, Hound of Konda"}],
        "hand": [{"object_id": f"hand-{index}", "name": "Plains"} for index in range(7)],
        "mana_pool": {
            "white": 1,
            "blue": 0,
            "black": 0,
            "red": 0,
            "green": 0,
            "colorless": 0,
        },
    }
    opponents = [
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
        for seat in range(1, 4)
    ]
    return {
        "game_id": "engine-opaque",
        "actor_id": "actor",
        "seat": 0,
        "turn_number": 1,
        "active_player_id": "actor",
        "priority_player_id": "actor",
        "phase": "precombat_main",
        "step": None,
        "players": [actor, *opponents],
        "stack": [],
    }


def _option(option_id: str, option_type: str, label: str, **metadata: Any) -> dict[str, Any]:
    return {
        "option_id": option_id,
        "option_type": option_type,
        "label": label,
        "metadata": metadata,
    }


def _request(
    decision_class: str,
    options: list[dict[str, Any]],
    *,
    minimum: int,
    maximum: int,
    context: dict[str, Any] | None = None,
    offset: int = 1,
) -> dict[str, Any]:
    return {
        "decision_id": f"opaque-{decision_class}",
        "decision_offset": offset,
        "actor_id": "actor",
        "decision_class": decision_class,
        "pilot_state": _state(),
        "context": context or {},
        "minimum_selections": minimum,
        "maximum_selections": maximum,
        "legal_options": options,
        "prompt": decision_class,
    }


@pytest.mark.parametrize(
    ("decision_class", "options", "minimum", "maximum", "context"),
    [
        (
            "priority",
            [_option("pass", "pass_priority", "Pass priority")],
            1,
            1,
            {},
        ),
        (
            "target",
            [_option("actor", "target", "Full Game Seat 1")],
            1,
            1,
            {"outcome": "benefit"},
        ),
        (
            "choose_object",
            [_option("actor", "choice", "Full Game Seat 1")],
            1,
            1,
            {"outcome": "benefit"},
        ),
        (
            "target_amount",
            [_option("actor", "target_amount", "Full Game Seat 1")],
            1,
            1,
            {"outcome": "benefit", "numeric_min": 1, "numeric_max": 3},
        ),
        (
            "mulligan",
            [
                _option("keep", "keep", "Keep opening hand"),
                _option("mulligan", "mulligan", "Take mulligan"),
            ],
            1,
            1,
            {},
        ),
        (
            "choose_use",
            [
                _option("yes", "boolean", "Yes", value=True),
                _option("no", "boolean", "No", value=False),
            ],
            1,
            1,
            {"outcome": "benefit"},
        ),
        (
            "choice",
            [_option("choice-a", "choice", "Draw a card")],
            1,
            1,
            {},
        ),
        (
            "pile",
            [
                _option("pile-a", "pile", "Pile 1", cards=[{"name": "A"}]),
                _option("pile-b", "pile", "Pile 2", cards=[{"name": "A"}, {"name": "B"}]),
            ],
            1,
            1,
            {"outcome": "benefit"},
        ),
        (
            "mana_payment",
            [
                _option("cancel", "cancel_mana_payment", "Cancel"),
                _option("mana", "mana_ability", "Tap Plains for W"),
            ],
            1,
            1,
            {},
        ),
        ("announce_x", [], 0, 0, {"outcome": "benefit", "numeric_min": 0, "numeric_max": 5}),
        ("amount", [], 0, 0, {"outcome": "benefit", "numeric_min": 1, "numeric_max": 5}),
        (
            "multi_amount",
            [],
            0,
            0,
            {"outcome": "benefit", "numeric_min": 0, "numeric_max": 4},
        ),
        (
            "replacement_effect",
            [_option("replacement", "replacement_effect", "Apply replacement")],
            1,
            1,
            {},
        ),
        (
            "trigger_order",
            [_option("trigger", "triggered_ability", "Resolve trigger")],
            1,
            1,
            {},
        ),
        ("mode", [_option("mode", "mode", "Draw a card")], 1, 1, {}),
        (
            "declare_attacker",
            [
                _option("hold", "hold_attacker", "Hold attacker"),
                _option(
                    "attack",
                    "declare_attacker",
                    "Isamaru attacks Full Game Seat 2",
                    defender_id="opponent-1",
                ),
            ],
            1,
            1,
            {},
        ),
        (
            "declare_blocker",
            [_option("block", "declare_blocker", "Isamaru blocks attacker", attacker_id="a")],
            0,
            1,
            {},
        ),
    ],
)
def test_every_supported_decision_class_returns_only_xmage_legal_output(
    decision_class: str,
    options: list[dict[str, Any]],
    minimum: int,
    maximum: int,
    context: dict[str, Any],
) -> None:
    response = _policy().decide(
        _request(
            decision_class,
            options,
            minimum=minimum,
            maximum=maximum,
            context=context,
        )
    )
    selected = response["selected_option_ids"]
    legal = {option["option_id"] for option in options}
    assert set(selected).issubset(legal)
    assert minimum <= len(selected) <= maximum
    if decision_class in {"announce_x", "amount", "multi_amount", "target_amount"}:
        assert "numeric_choice" in response
        assert context["numeric_min"] <= response["numeric_choice"] <= context["numeric_max"]
