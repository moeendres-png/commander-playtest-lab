"""#703 pilot side: an engine-reversed priority activation must not loop.

XMage answers an activation it cannot complete — the observed shape is an
announced X that leaves a required target with no legal choice, so
``Targets.makeChoice`` skips the target without asking the player and the
activation is rewound (CR 601.2e / 727) — by re-offering priority to the same
seat with the same stack, the same turn/step and the same option still on
offer. The bridge hands that frame back to the pilot unchanged.

The Lab does not need a second mechanism for this. The per-seat priority
no-progress latch already bounds a seat that keeps re-picking an option in an
identical window: three identical windows are allowed, the fourth trips the
latch, and every later frame with that same fingerprint passes priority so the
phase advances. These tests pin that bound and pin the invariant that matters
for the Lab's authority — the reversed option is still engine-offered on every
frame and is never removed from the offered set, and the Lab never passes
priority on the player's behalf before the latch has actually tripped.
"""

from __future__ import annotations

import copy
import random

from commander_lab.agents.pilots import build_pilot
from commander_lab.engine.rules.full_game import (
    ExternalPilotDecisionPolicy,
    FullGamePilotBinding,
    _RuntimePilot,
)
from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength

SEAT = 1
PASS = "raw-pass"
REVERSED = "raw-reversed-activation"
OTHER = "raw-other-activation"

# The documented no-progress bound in `_decide_priority`: three identical
# windows are permitted, the fourth trips the latch.
LATCH_TRIP_FRAME = 4


def _policy() -> ExternalPilotDecisionPolicy:
    runtimes = []
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


def _options() -> list[dict]:
    return [
        _priority_option(PASS, "pass_priority", "Pass priority"),
        _priority_option(REVERSED, "activated_ability", "Reversed X-target activation"),
        _priority_option(OTHER, "activated_ability", "Other activation"),
    ]


def _drive(policy: ExternalPilotDecisionPolicy, runtime: _RuntimePilot, frames: int) -> list[str]:
    """Answer ``frames`` consecutive priority frames in one identical window."""
    return [
        policy._decide_priority(runtime, _priority_state(), list(_options()), random.Random(0))
        for _ in range(frames)
    ]


def test_reversed_activation_converges_to_passing_within_the_latch_bound() -> None:
    """The engine re-offers the very frame it reversed; the seat stops looping.

    Frame 1 the pilot takes the activation. XMage reverses it and hands the
    identical window back. The pilot may keep taking it while the latch allows
    (that is the pilot's own discretion, not a Lab decision), but the latch
    must converge the seat to passing at the documented frame and keep it
    passing for as long as the window stays identical.
    """
    policy = _policy()
    runtime = policy._pilots[SEAT]

    picks = _drive(policy, runtime, 7)

    assert picks[0] == REVERSED, "the first frame must take the highest-ranked action"
    assert all(pick in {option["option_id"] for option in _options()} for pick in picks)
    assert picks[: LATCH_TRIP_FRAME - 1] == [REVERSED] * (LATCH_TRIP_FRAME - 1), (
        "the seat may keep re-picking the reversed option only inside the "
        "documented no-progress bound"
    )
    assert picks[LATCH_TRIP_FRAME - 1 :] == [PASS] * (len(picks) - LATCH_TRIP_FRAME + 1), (
        "once the latch trips the seat must pass priority so the phase advances"
    )


def test_the_reversed_option_is_never_removed_from_the_offered_set() -> None:
    """The Lab de-ranks nothing: the engine keeps offering the option.

    The reversal is the engine's own 601.2e/727 rewind, so the option stays in
    the offered set on every frame, unmutated. The policy must not rewrite the
    engine's offer, and every id it returns must be one the engine offered.
    """
    policy = _policy()
    runtime = policy._pilots[SEAT]

    for _ in range(6):
        offered = copy.deepcopy(_options())
        pristine = copy.deepcopy(offered)
        selected = policy._decide_priority(runtime, _priority_state(), offered, random.Random(0))
        assert offered == pristine, "the Lab must not mutate the engine's offered options"
        assert REVERSED in {option["option_id"] for option in offered}
        assert selected in {option["option_id"] for option in pristine}


def test_a_window_change_reopens_the_activation() -> None:
    """601.2e/727 rewinds to the moment before the proposal, not after.

    A different window is a different frame: the latch unlatches and the
    activation becomes selectable again, so a later legal frame is not
    permanently blocked by an earlier reversal.
    """
    policy = _policy()
    runtime = policy._pilots[SEAT]

    _drive(policy, runtime, 5)
    assert policy._priority_latched.get(runtime.binding.seat) is not None, (
        "precondition: the seat latched while the window never changed"
    )

    moved_on = _priority_state()
    moved_on["turn_number"] = 8
    assert (
        policy._decide_priority(runtime, moved_on, list(_options()), random.Random(0)) == REVERSED
    )


def test_a_changed_stack_reopens_the_activation() -> None:
    """A changed stack is a new window even inside the same turn and step."""
    policy = _policy()
    runtime = policy._pilots[SEAT]

    _drive(policy, runtime, 5)

    stacked = _priority_state()
    stacked["stack"] = [{"name": "Some Spell"}]
    assert policy._decide_priority(runtime, stacked, list(_options()), random.Random(0)) == REVERSED


def test_the_reversal_of_one_seat_does_not_converge_another_seat() -> None:
    """The bound is per seat: one seat looping must not pass another seat's turn."""
    policy = _policy()
    first = policy._pilots[1]
    second = policy._pilots[2]

    picks = _drive(policy, first, 5)
    assert picks[-1] == PASS, "precondition: the first seat latched"

    other_seat_state = _priority_state()
    other_seat_state["actor_id"] = "actor-2"
    other_seat_state["players"] = [{"player_id": "actor-2", "mana_pool": {}}]
    assert (
        policy._decide_priority(second, other_seat_state, list(_options()), random.Random(0))
        == REVERSED
    )
