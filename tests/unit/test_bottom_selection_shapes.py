"""Bottom-of-library selection shapes.

The bridge flags every native putCardsOnBottomOfLibrary path with
``bottom_of_library_selection``. Two shapes share it: London mulligan
(options are hand cards) and library bottom-ordering (e.g. Dig Through
Time: options are looked-at library cards, disjoint from hand). Only the
London shape may use opening-hand bottom valuation; library ordering
must rank the offered options.
"""

from __future__ import annotations

import random

import pytest

from commander_lab.agents.pilots import build_pilot
from commander_lab.engine.rules.full_game import (
    ExternalPilotDecisionPolicy,
    FullGamePilotBinding,
    _RuntimePilot,
)
from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength


def _policy() -> ExternalPilotDecisionPolicy:
    runtimes: list[_RuntimePilot] = []
    for seat in (1, 2):
        binding = FullGamePilotBinding(
            seat=seat,
            deck_id=f"test/seat-{seat}",
            strategy="generic",
            commander_names=("Test Commander",),
            config=PilotConfig(
                pilot_name="auto",
                strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
                mode=PilotDecisionMode.DETERMINISTIC,
            ),
            pilot_identity="GenericCommanderPilot",
            pilot_version="1.0.0",
            decision_policy_version="xmage-full-game-policy-1.0.0",
        )
        runtimes.append(
            _RuntimePilot(binding=binding, pilot=build_pilot(binding.config, strategy="generic"))
        )
    return ExternalPilotDecisionPolicy(tuple(runtimes), scenario_seed=1)


def _request() -> dict:
    return {"context": {"bottom_of_library_selection": True, "outcome": "neutral"}}


def _state(hand_ids: list[str]) -> dict:
    return {
        "actor_id": "actor-1",
        "players": [
            {
                "player_id": "actor-1",
                "mana_pool": {},
                "hand": [
                    {"object_id": card_id, "name": f"Hand Card {index}"}
                    for index, card_id in enumerate(hand_ids)
                ],
            }
        ],
    }


def _option(card_id: str, name: str) -> dict:
    return {
        "option_id": card_id,
        "option_type": "choice",
        "label": name,
        "metadata": {"object_id": card_id, "name": name},
    }


def test_london_shape_uses_hand_bottom_valuation() -> None:
    policy = _policy()
    hand = ["hand-1", "hand-2", "hand-3"]
    options = [_option(card_id, f"Hand Card {index}") for index, card_id in enumerate(hand)]
    selected = policy._decide_targets(
        policy._pilots[1], _state(hand), _request(), options, 1, 1, random.Random(0)
    )
    assert len(selected) == 1
    assert selected[0] in hand


def test_library_shape_ranks_offered_options() -> None:
    """Dig Through Time shape: options are library cards, not hand cards."""
    policy = _policy()
    hand = ["hand-1", "hand-2"]
    options = [
        _option("lib-1", "Farewell"),
        _option("lib-2", "Port Town"),
        _option("lib-3", "Exotic Orchard"),
        _option("lib-4", "Island"),
        _option("lib-5", "Reliquary Tower"),
    ]
    selected = policy._decide_targets(
        policy._pilots[1], _state(hand), _request(), options, 1, 1, random.Random(0)
    )
    assert len(selected) == 1
    assert selected[0] in {option["option_id"] for option in options}
    assert selected[0] not in hand


def _mode_option(mode_id: str, label: str, targets_available: bool | None) -> dict:
    metadata: dict = {"mode_id": mode_id}
    if targets_available is not None:
        metadata["mode_targets_available"] = targets_available
    return {
        "option_id": mode_id,
        "option_type": "mode",
        "label": label,
        "metadata": metadata,
    }


def test_mode_prefers_targets_available() -> None:
    """Abrade shape: the targetless mode must not be selected when a
    viable mode is offered."""
    policy = _policy()
    options = [
        _mode_option("mode-damage", "deal 3 damage to target creature", False),
        _mode_option("mode-artifact", "destroy target artifact", True),
    ]
    selected = policy._decide_mode(policy._pilots[1], _state(["hand-1"]), options, random.Random(0))
    assert selected == "mode-artifact"


def test_mode_unknown_flag_means_no_filtering() -> None:
    policy = _policy()
    options = [
        _mode_option("mode-a", "draw a card", None),
        _mode_option("mode-b", "create a token", None),
    ]
    selected = policy._decide_mode(policy._pilots[1], _state(["hand-1"]), options, random.Random(0))
    assert selected in {"mode-a", "mode-b"}


def test_mode_all_targetless_still_chooses_offered() -> None:
    """No viable mode: pilot still chooses (bridge maps doom to pass)."""
    policy = _policy()
    options = [
        _mode_option("mode-a", "deal 3 damage to target creature", False),
        _mode_option("mode-b", "destroy target artifact", False),
    ]
    selected = policy._decide_mode(policy._pilots[1], _state(["hand-1"]), options, random.Random(0))
    assert selected in {"mode-a", "mode-b"}


def _mana_option(option_id: str, option_type: str, label: str, metadata: dict) -> dict:
    return {
        "option_id": option_id,
        "option_type": option_type,
        "label": label,
        "metadata": metadata,
    }


def _hybrid_payment_options() -> list[dict]:
    """Cascade Bluffs {U/R} payment shape: white pool mana is offered but
    natively non-advancing; blue/red advance."""
    return [
        _mana_option("cancel", "cancel_mana_payment", "Cancel mana payment", {}),
        _mana_option(
            "pool-w",
            "mana_pool",
            "Spend white mana from pool",
            {"mana_type": "white", "mana_available": 1, "advances_payment": False},
        ),
        _mana_option(
            "pool-u",
            "mana_pool",
            "Spend blue mana from pool",
            {"mana_type": "blue", "mana_available": 1, "advances_payment": True},
        ),
        _mana_option(
            "pool-r",
            "mana_pool",
            "Spend red mana from pool",
            {"mana_type": "red", "mana_available": 1, "advances_payment": True},
        ),
    ]


def test_mana_payment_excludes_non_advancing_pool() -> None:
    """Hybrid {U/R}: white pool spend must never be selected."""
    policy = _policy()
    context = {"unpaid_mana": "{U/R}"}
    for _ in range(2):
        selected = policy._decide_mana(
            policy._pilots[1],
            _state(["hand-1"]),
            _hybrid_payment_options(),
            context,
            random.Random(0),
        )
        assert selected in {"pool-u", "pool-r"}, selected


def test_mana_payment_no_progress_guard_cancels() -> None:
    """Three identical mana-payment offers: take the offered cancel."""
    policy = _policy()
    options = _hybrid_payment_options()
    context = {"unpaid_mana": "{U/R}"}
    runtimes = policy._pilots[1]
    first = policy._decide_mana(runtimes, _state(["hand-1"]), options, context, random.Random(0))
    assert first in {"pool-u", "pool-r"}
    second = policy._decide_mana(runtimes, _state(["hand-1"]), options, context, random.Random(0))
    assert second in {"pool-u", "pool-r"}
    third = policy._decide_mana(runtimes, _state(["hand-1"]), options, context, random.Random(0))
    assert third == "cancel"


def test_mana_payment_unknown_flag_means_usable() -> None:
    """Absent advances_payment: no filtering (engine authority)."""
    policy = _policy()
    options = [
        _mana_option("cancel", "cancel_mana_payment", "Cancel mana payment", {}),
        _mana_option(
            "pool-w",
            "mana_pool",
            "Spend white mana from pool",
            {"mana_type": "white", "mana_available": 1},
        ),
    ]
    selected = policy._decide_mana(
        policy._pilots[1],
        _state(["hand-1"]),
        options,
        {"unpaid_mana": "{1}"},
        random.Random(0),
    )
    assert selected == "pool-w"


def test_payment_withholds_unfunded_costed_mana_ability() -> None:
    """Signet-like {1},{T} ability with empty pool: not selectable inside
    payment; the pilot cancels instead of failing activation."""
    policy = _policy()
    options = [
        _mana_option("cancel", "cancel_mana_payment", "Cancel mana payment", {}),
        {
            "option_id": "signet",
            "option_type": "mana_ability",
            "label": "Rakdos Signet — {1}, {T}: Add {B}{R}.",
            "metadata": {
                "mana_cost_generic": 1,
                "pool_covers_mana_cost": False,
                "requires_tap_source": True,
                "source_tapped": False,
            },
        },
    ]
    selected = policy._decide_mana(
        policy._pilots[1],
        _state(["hand-1"]),
        options,
        {"unpaid_mana": "{1}"},
        random.Random(0),
    )
    assert selected == "cancel"


def test_payment_keeps_funded_costed_mana_ability() -> None:
    policy = _policy()
    options = [
        _mana_option("cancel", "cancel_mana_payment", "Cancel mana payment", {}),
        {
            "option_id": "signet",
            "option_type": "mana_ability",
            "label": "Rakdos Signet — {1}, {T}: Add {B}{R}.",
            "metadata": {
                "mana_cost_generic": 1,
                "pool_covers_mana_cost": True,
                "requires_tap_source": True,
                "source_tapped": False,
            },
        },
    ]
    selected = policy._decide_mana(
        policy._pilots[1],
        _state(["hand-1"]),
        options,
        {"unpaid_mana": "{1}"},
        random.Random(0),
    )
    assert selected == "signet"


def _priority_option(option_id: str, option_type: str, label: str) -> dict:
    return {
        "option_id": option_id,
        "option_type": option_type,
        "label": label,
        "metadata": {"source_name": label},
    }


def _priority_state() -> dict:
    return {
        "actor_id": "actor-1",
        "turn_number": 7,
        "phase": "main",
        "step": "main1",
        "stack": [],
        "players": [{"player_id": "actor-1", "mana_pool": {}}],
    }


def test_priority_selection_is_order_independent() -> None:
    """Same offer in different bridge orders: same raw option selected."""
    policy = _policy()
    options = [
        _priority_option("raw-pass", "pass_priority", "Pass priority"),
        _priority_option("raw-bolt", "activated_ability", "Lightning Bolt"),
        _priority_option("raw-abrade", "activated_ability", "Abrade"),
        _priority_option("raw-mountain", "mana_ability", "Mountain"),
    ]
    first = policy._decide_priority(
        policy._pilots[1], _priority_state(), list(options), random.Random(0)
    )
    reversed_options = list(reversed(options))
    second = policy._decide_priority(
        policy._pilots[1], _priority_state(), reversed_options, random.Random(0)
    )
    assert first == second
    assert first in {option["option_id"] for option in options}


def test_priority_no_progress_guard_passes() -> None:
    """Greaves shape: identical priority window four times in a row.
    The fourth must pass so the phase advances."""
    policy = _policy()
    options = [
        _priority_option("raw-pass", "pass_priority", "Pass priority"),
        _priority_option("raw-greaves", "activated_ability", "Lightning Greaves"),
    ]
    runtime = policy._pilots[1]
    picks = [
        policy._decide_priority(runtime, _priority_state(), list(options), random.Random(0))
        for _ in range(4)
    ]
    assert picks[0] == "raw-greaves"
    assert picks[3] == "raw-pass"


def test_priority_guard_latches_until_window_changes() -> None:
    """A single forced pass must not resume the loop: while the window
    stays identical the seat keeps passing; a changed window unlatches."""
    policy = _policy()
    options = [
        _priority_option("raw-pass", "pass_priority", "Pass priority"),
        _priority_option("raw-greaves", "activated_ability", "Lightning Greaves"),
    ]
    runtime = policy._pilots[1]
    picks = [
        policy._decide_priority(runtime, _priority_state(), list(options), random.Random(0))
        for _ in range(7)
    ]
    assert picks[:3] == ["raw-greaves"] * 3
    assert picks[3:] == ["raw-pass"] * 4
    changed = _priority_state()
    changed["turn_number"] = 8
    assert (
        policy._decide_priority(runtime, changed, list(options), random.Random(0)) == "raw-greaves"
    )


def test_priority_guard_ignores_forced_pass_rounds() -> None:
    """Interleaved 1-option forced passes (priority reset rounds) must
    neither trip the guard nor break a genuine no-progress chain."""
    policy = _policy()
    options = [
        _priority_option("raw-pass", "pass_priority", "Pass priority"),
        _priority_option("raw-greaves", "activated_ability", "Lightning Greaves"),
    ]
    forced = [_priority_option("raw-pass", "pass_priority", "Pass priority")]
    runtime = policy._pilots[1]
    picks = []
    for _ in range(4):
        picks.append(
            policy._decide_priority(runtime, _priority_state(), list(options), random.Random(0))
        )
        forced_pick = policy._decide_priority(
            runtime, _priority_state(), list(forced), random.Random(0)
        )
        assert forced_pick == "raw-pass"
    assert picks[:3] == ["raw-greaves"] * 3
    assert picks[3] == "raw-pass"


def test_target_selection_is_order_independent() -> None:
    """Same targets in different bridge orders: same raw option selected."""
    policy = _policy()
    request = {"context": {"outcome": "detriment"}}
    options = [
        _option("raw-island-a", "Island"),
        _option("raw-mountain", "Mountain"),
        _option("raw-island-b", "Island"),
    ]
    first = policy._decide_targets(
        policy._pilots[1], _state(["hand-1"]), request, list(options), 1, 1, random.Random(0)
    )
    second = policy._decide_targets(
        policy._pilots[1],
        _state(["hand-1"]),
        request,
        list(reversed(options)),
        1,
        1,
        random.Random(0),
    )
    assert first == second
    assert first[0] in {option["option_id"] for option in options}


def _zoned_option(option_id: str, name: str, zone: str, zone_index: int) -> dict:
    return {
        "option_id": option_id,
        "option_type": "choice",
        "label": name,
        "metadata": {"object_id": option_id, "name": name, "zone": zone, "zone_index": zone_index},
    }


def test_zoned_target_pick_is_order_and_identity_independent() -> None:
    """Fetch shape: two same-named library cards at fixed positions.
    Whatever the bridge order, the same POSITION is selected, so twin
    libraries keep identical name-orders after the tutor."""
    policy = _policy()
    request = {"context": {"outcome": "neutral"}}
    options = [
        _zoned_option("raw-alpha", "Island", "library", 5),
        _zoned_option("raw-beta", "Island", "library", 12),
    ]
    first = policy._decide_targets(
        policy._pilots[1], _state(["hand-1"]), request, list(options), 1, 1, random.Random(0)
    )
    second = policy._decide_targets(
        policy._pilots[1],
        _state(["hand-1"]),
        request,
        list(reversed(options)),
        1,
        1,
        random.Random(0),
    )
    assert first == second
    assert first[0] in {"raw-alpha", "raw-beta"}


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
