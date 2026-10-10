"""Full-game pilot judgment on standalone mana and engine-declined may-prompts.

Real-deck 4P games on the pinned engine showed two pilot defects:

* every priority window, the pilot tapped its lands for mana it could not
  spend (mana abilities scored as free card plays), so in its own main phase
  nothing was castable and games ran 90-240 turns with almost no spells cast;
* the pilot answered "Yes" to every repeated "Pay N times Multikicker" offer
  (outcome AIDontUseIt, whose engine affordability check covers one payment),
  looping until max_decisions aborted the game.

The engine stays the authority in both cases; these tests pin the pilot's own
choice among the offered options and the controls that prove nothing else
changed (payments still tap sources, real actions still beat passing).
"""

from __future__ import annotations

from typing import Any

import pytest

from commander_lab.agents import GenericCommanderPilot
from commander_lab.agents.pilots import STANDALONE_MANA_ABILITY_UTILITY
from commander_lab.engine.rules.full_game import (
    ExternalPilotDecisionPolicy,
    FullGamePilotBinding,
    _RuntimePilot,
)
from commander_lab.models import (
    PilotActionView,
    PilotConfig,
    PilotDecisionMode,
    PilotStrength,
)


def _policy(
    mode: PilotDecisionMode = PilotDecisionMode.DETERMINISTIC,
) -> ExternalPilotDecisionPolicy:
    runtimes: list[_RuntimePilot] = []
    for seat in range(1, 5):
        config = PilotConfig(
            pilot_name="auto", strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC, mode=mode
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
    return ExternalPilotDecisionPolicy(tuple(runtimes), 20261010)  # type: ignore[arg-type]


def _state(*, step: str = "upkeep", pool_white: int = 0) -> dict[str, Any]:
    actor = {
        "player_id": "actor",
        "seat": 0,
        "life": 40,
        "hand_count": 2,
        "library_count": 90,
        "graveyard_count": 0,
        "battlefield": [
            {"object_id": f"land-{index}", "name": "Plains", "tapped": False} for index in range(3)
        ],
        "graveyard": [],
        "command": [{"object_id": "commander", "name": "Isamaru, Hound of Konda"}],
        "hand": [
            {"object_id": "hand-0", "name": "Savannah Lions"},
            {"object_id": "hand-1", "name": "Plains"},
        ],
        "mana_pool": {
            "white": pool_white,
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
        "turn_number": 5,
        "active_player_id": "actor",
        "priority_player_id": "actor",
        "phase": "beginning" if step == "upkeep" else "precombat_main",
        "step": step,
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
    context: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    prompt: str = "",
    offset: int = 1,
) -> dict[str, Any]:
    return {
        "decision_id": f"opaque-{decision_class}-{offset}",
        "decision_offset": offset,
        "actor_id": "actor",
        "decision_class": decision_class,
        "pilot_state": state or _state(),
        "context": context or {},
        "minimum_selections": 1,
        "maximum_selections": 1,
        "legal_options": options,
        "prompt": prompt or decision_class,
    }


_TAPS = [
    _option("tap-a", "mana_ability", "Plains — {T}: Add {W}.", source_name="Plains"),
    _option("tap-b", "mana_ability", "Plains — {T}: Add {W}.", source_name="Plains"),
    _option("tap-c", "mana_ability", "Plains — {T}: Add {W}.", source_name="Plains"),
]
_PASS = _option("pass", "pass_priority", "Pass priority")


@pytest.mark.parametrize("mode", list(PilotDecisionMode))
def test_pilot_does_not_float_mana_it_cannot_spend(mode: PilotDecisionMode) -> None:
    # The upkeep window of the real-deck games: only taps and pass are offered.
    response = _policy(mode).decide(_request("priority", [_PASS, *_TAPS]))
    assert response["selected_option_ids"] == ["pass"]


def test_pilot_still_takes_a_real_action_over_passing() -> None:
    # Positive control: an engine-offered cast beats both passing and floating.
    cast = _option(
        "cast",
        "activated_ability",
        "Savannah Lions — Cast Savannah Lions",
        source_name="Savannah Lions",
        source_object_id="hand-0",
        ability_type="spell",
        mana_cost_white=1,
        mana_cost_generic=0,
        # The engine's verdict over the empty pool; untapped Plains pay it.
        pool_covers_mana_cost=False,
        requires_tap_source=False,
        requires_untap_source=False,
        requires_sacrifice_source=False,
    )
    response = _policy().decide(
        _request("priority", [_PASS, *_TAPS, cast], state=_state(step="precombat_main"))
    )
    assert response["selected_option_ids"] == ["cast"]


def test_pilot_still_plays_a_land() -> None:
    play = _option(
        "play",
        "activated_ability",
        "Plains — Play Plains",
        source_name="Plains",
        source_object_id="hand-1",
    )
    response = _policy().decide(
        _request("priority", [_PASS, *_TAPS, play], state=_state(step="precombat_main"))
    )
    assert response["selected_option_ids"] == ["play"]


def test_mana_payment_still_taps_a_source() -> None:
    # Control: the payment frame of a cast must still be paid from sources;
    # the float-only judgment never applies inside a payment.
    response = _policy().decide(
        _request(
            "mana_payment",
            [_option("cancel", "cancel_mana_payment", "Cancel"), *_TAPS],
            context={"unpaid_mana": "{W}"},
        )
    )
    assert response["selected_option_ids"][0].startswith("tap-")


def test_float_only_utility_ranks_below_pass() -> None:
    pilot = GenericCommanderPilot(
        PilotConfig(
            pilot_name="auto",
            strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
            mode=PilotDecisionMode.DETERMINISTIC,
        )
    )
    policy = _policy()
    state = policy._pilot_state(policy._pilots[1], _state())
    tap = PilotActionView(
        action_id="tap",
        action_kind="card",
        card_name="Plains",
        floor_value=0.5,
        immediate_impact=0.35,
        metadata={"is_mana_ability": True, "floats_mana_only": True},
    )
    unflagged = tap.model_copy(update={"metadata": {"is_mana_ability": True}})
    passing = PilotActionView(
        action_id="pass", action_kind="pass", card_name="Pass priority", floor_value=0.15
    )
    tap_value = pilot.evaluate_action(state, tap).total_utility
    pass_value = pilot.evaluate_action(state, passing).total_utility
    assert tap_value == STANDALONE_MANA_ABILITY_UTILITY
    assert tap_value < pass_value
    # Negative control: without the float-only flag the old scoring (a free
    # card play) still outranks passing, which is what wasted every land.
    assert pilot.evaluate_action(state, unflagged).total_utility > pass_value


def _boolean(outcome: str, prompt: str, offset: int = 1) -> dict[str, Any]:
    return _request(
        "choose_use",
        [
            _option("yes", "boolean", "Yes", value=True),
            _option("no", "boolean", "No", value=False),
        ],
        context={"outcome": outcome},
        prompt=prompt,
        offset=offset,
        state=_state(step="precombat_main"),
    )


def test_repeated_multikicker_offer_is_declined() -> None:
    policy = _policy()
    for count in (1, 2, 3):
        times = "1 time " if count == 1 else f"{count} times "
        response = policy.decide(
            _boolean("aidontuseit", f"Pay {times}Multikicker {{2}} ?", offset=count)
        )
        assert response["selected_option_ids"] == ["no"]


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [("benefit", "yes"), ("detriment", "no"), ("aidontuseit", "no")],
)
def test_boolean_outcome_polarity(outcome: str, expected: str) -> None:
    response = _policy().decide(_boolean(outcome, "Use the ability?"))
    assert response["selected_option_ids"] == [expected]
