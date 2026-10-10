"""#703 pilot memory for engine-reversed priority activations.

XMage answers an activation it cannot complete — the observed shape is an
announced X that leaves a required target with no legal choice, so
``Targets.makeChoice`` skips the target without asking the player and the
activation is rewound (CR 601.2e / 727) — by re-offering priority to the
same seat with the same stack and the same option still on offer.

The pilot must not loop on that option. It stays engine-offered (the Lab
never decides for the player and never hides an engine-authorized option);
the pilot simply stops selecting it while the engine keeps re-offering the
very frame it already reversed. Any change to the window re-opens it.
"""

from __future__ import annotations

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
SHELOB = "raw-shelob"
ISAMARU = "raw-isamaru"


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
        _priority_option(SHELOB, "activated_ability", "Shelob, Dread Weaver"),
        _priority_option(ISAMARU, "activated_ability", "Isamaru, Hound of Konda"),
    ]


def test_reversed_priority_option_is_not_re_picked_in_the_same_window() -> None:
    """The engine answered the Shelob activation with the same frame again.

    Frame 1 the pilot picks Shelob. XMage reverses it (required target left
    with no legal choice after the announced X) and re-offers priority in the
    same window with Shelob still on offer. The pilot must not pick it again.
    """
    policy = _policy()
    runtime = policy._pilots[SEAT]

    first = policy._decide_priority(runtime, _priority_state(), _options(), random.Random(0))
    assert first == SHELOB, "first frame must take the highest-ranked action"

    second = policy._decide_priority(runtime, _priority_state(), _options(), random.Random(0))
    assert second != SHELOB, "the engine reversed this option in this window; re-picking it loops"
    assert second in {option["option_id"] for option in _options()}


def test_reversed_option_stays_engine_offered_and_never_auto_picked() -> None:
    """Withholding is de-ranking inside the pilot, not option removal.

    The reversed option is still present in the offered set on every frame;
    the Lab neither hides it nor submits it.
    """
    policy = _policy()
    runtime = policy._pilots[SEAT]

    policy._decide_priority(runtime, _priority_state(), _options(), random.Random(0))
    offered = _options()
    assert SHELOB in {option["option_id"] for option in offered}
    for _ in range(5):
        selected = policy._decide_priority(
            runtime, _priority_state(), list(offered), random.Random(0)
        )
        assert selected != SHELOB
        assert SHELOB in {option["option_id"] for option in offered}


def test_reversal_memory_is_per_seat() -> None:
    """One seat's reversal never de-ranks another seat's offer."""
    policy = _policy()
    seat_one = policy._pilots[1]
    seat_two = policy._pilots[2]

    policy._decide_priority(seat_one, _priority_state(), _options(), random.Random(0))
    assert (
        policy._decide_priority(seat_two, _priority_state(), _options(), random.Random(0)) != PASS
    )


def test_changed_window_reopens_the_reversed_option() -> None:
    """CR 601.2e/727 rewinds to the moment before the proposal.

    Once the turn moves on the option is no longer the same frame, so the
    pilot is free to select it again.
    """
    policy = _policy()
    runtime = policy._pilots[SEAT]

    policy._decide_priority(runtime, _priority_state(), _options(), random.Random(0))
    assert (
        policy._decide_priority(runtime, _priority_state(), _options(), random.Random(0)) != SHELOB
    )

    changed = _priority_state()
    changed["turn_number"] = 8
    assert policy._decide_priority(runtime, changed, _options(), random.Random(0)) == SHELOB


def test_changed_stack_reopens_the_reversed_option() -> None:
    """A changed stack is a new window even inside the same turn/step."""
    policy = _policy()
    runtime = policy._pilots[SEAT]

    policy._decide_priority(runtime, _priority_state(), _options(), random.Random(0))
    assert (
        policy._decide_priority(runtime, _priority_state(), _options(), random.Random(0)) != SHELOB
    )

    stacked = _priority_state()
    stacked["stack"] = [{"name": "Shelob, Dread Weaver"}]
    assert policy._decide_priority(runtime, stacked, _options(), random.Random(0)) == SHELOB


def test_option_no_longer_offered_is_not_treated_as_reversed() -> None:
    """The engine taking the option off the offer is not a rewind.

    That is ordinary progress: the action was taken, so nothing is withheld
    when a later frame offers a different set.
    """
    policy = _policy()
    runtime = policy._pilots[SEAT]

    policy._decide_priority(runtime, _priority_state(), _options(), random.Random(0))
    without_shelob = [option for option in _options() if option["option_id"] != SHELOB]
    assert (
        policy._decide_priority(runtime, _priority_state(), without_shelob, random.Random(0))
        != PASS
    )
    assert (
        policy._decide_priority(runtime, _priority_state(), _options(), random.Random(0)) == SHELOB
    )
