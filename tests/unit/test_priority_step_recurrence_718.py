"""#718: a priority window that RECURS inside one step must converge (#718).

Lightning Greaves' ``Equip {0}`` is a free action that uses the stack. When
the seat activates it, XMage keeps a bookmark ``GameState`` for that action
until the step ends, the ability resolves and the same seat gets priority
back in the same ``(turn_number, phase, step)``. The seat therefore
alternates between two windows forever:

* window A -- empty stack, Pass + ``Lightning Greaves — Equip {0}``; the
  pilot's own judgment picks the Equip,
* window B -- the Equip ability on the stack, Pass + a land; the pilot
  passes and the ability resolves,

and window A comes straight back. The consecutive no-progress guard in
``_decide_priority`` only sees *consecutive* identical windows, so this
two-window alternation never trips it (observed: 2156 Equip selections and
2172 priority passes inside one step, ending in an ``OutOfMemoryError`` in
the bridge JVM from the retained per-action bookmark states).

The Lab's own bound is what has to hold: the identical window recurring for
the fourth time inside the same step passes priority, which is always legal,
and the seat latches exactly as the consecutive guard latches. These tests
pin that bound, and pin that it stays a *window-identity* bound rather than
a blanket cap -- three recurrences of the same window in one step are still
pilot discretion, and any change to what the window actually offers (step,
pool, stack, options) is a different window that never inherits a count.
"""

from __future__ import annotations

from typing import Any

from commander_lab.agents.pilots import build_pilot
from commander_lab.engine.rules.full_game import (
    ExternalPilotDecisionPolicy,
    FullGamePilotBinding,
    _RuntimePilot,
)
from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength

SEAT = 1
OTHER_SEAT = 2
PASS = "raw-pass"
EQUIP = "raw-equip"
PLAIN_TAP = "raw-plains"

# The documented no-progress bound in `_decide_priority`: three identical
# windows are permitted, the fourth converges the seat to passing priority.
# #718 reuses that same threshold for a window that RECURS inside one step.
RECURRENCE_TRIP_FRAME = 4

# The #718 loop shape: window A offers the free action, window B is the
# frame in which the activated ability is on the stack. XMage does not offer
# an ability that is already on the stack, so B carries Pass plus a land.
_WINDOW_A_STACK: list[dict[str, str]] = []
_WINDOW_B_STACK: list[dict[str, str]] = [
    {"object_id": "spell-1", "name": "Lightning Greaves — Equip {0}"}
]


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


def _option(option_id: str, option_type: str, label: str, **metadata: Any) -> dict[str, Any]:
    return {
        "option_id": option_id,
        "option_type": option_type,
        "label": label,
        "metadata": metadata,
    }


_PASS = _option(PASS, "pass_priority", "Pass priority")
_EQUIP = _option(
    EQUIP,
    "activated_ability",
    "Lightning Greaves — Equip {0}",
    source_name="Lightning Greaves",
    source_object_id="greaves-1",
    ability_type="equip",
)
_PLAIN_TAP = _option(
    PLAIN_TAP,
    "mana_ability",
    "Plains — {T}: Add {W}.",
    source_name="Plains",
    source_object_id="land-0",
    ability_type="mana",
    mana_cost_generic=0,
    mana_cost_white=0,
    mana_cost_blue=0,
    mana_cost_black=0,
    mana_cost_red=0,
    mana_cost_green=0,
    mana_cost_colorless=0,
    pool_covers_mana_cost=True,
    requires_tap_source=True,
    requires_untap_source=False,
    requires_sacrifice_source=False,
    source_tapped=False,
)

WINDOW_A_OPTIONS = [_PASS, _EQUIP]
WINDOW_B_OPTIONS = [_PASS, _PLAIN_TAP]


def _state(
    *,
    actor_id: str = "actor-1",
    seat: int = SEAT,
    stack: list[dict[str, str]] | None = None,
    step: str = "precombat_main",
    pool_white: int = 0,
    opponent_hand_count: int = 7,
) -> dict[str, Any]:
    actor = {
        "player_id": actor_id,
        "seat": seat - 1,
        "life": 40,
        "hand_count": 0,
        "library_count": 70,
        "graveyard_count": 0,
        "battlefield": [
            {"object_id": "greaves-1", "name": "Lightning Greaves", "tapped": False},
            {"object_id": "veyran-1", "name": "Veyran, Voice of Duality", "tapped": False},
            {"object_id": "ishai-1", "name": "Ishai, Ojutai Dragonspeaker", "tapped": False},
            {"object_id": "land-0", "name": "Plains", "tapped": False},
        ],
        "command": [],
        "hand": [],
        "mana_pool": {
            "white": pool_white,
            "blue": 0,
            "black": 0,
            "red": 0,
            "green": 0,
            "colorless": 0,
        },
    }
    opponent = {
        "player_id": f"opponent-{opponent_hand_count}",
        "seat": SEAT,
        "life": 40,
        "hand_count": opponent_hand_count,
        "library_count": 71,
        "graveyard_count": 0,
        "battlefield": [],
        "command": [],
    }
    return {
        "game_id": "engine-opaque",
        "actor_id": actor_id,
        "seat": seat - 1,
        "turn_number": 83,
        "active_player_id": actor_id,
        "priority_player_id": actor_id,
        "phase": "precombat_main",
        "step": step,
        "players": [actor, opponent],
        "stack": list(stack or []),
    }


def _request(options: list[dict[str, Any]], offset: int, state: dict[str, Any]) -> dict[str, Any]:
    return {
        "decision_id": f"opaque-priority-{offset}",
        "decision_offset": offset,
        "actor_id": state["actor_id"],
        "decision_class": "priority",
        "pilot_state": state,
        "context": {},
        "minimum_selections": 1,
        "maximum_selections": 1,
        "legal_options": [dict(option) for option in options],
        "prompt": "priority",
        "source_object": None,
    }


def _choose(
    policy: ExternalPilotDecisionPolicy,
    options: list[dict[str, Any]],
    offset: int,
    state: dict[str, Any],
) -> str:
    response = policy.decide(_request(options, offset, state))
    selected = response["selected_option_ids"]
    assert len(selected) == 1, "a priority decision is a single-option answer"
    offered = {option["option_id"] for option in options}
    assert selected[0] in offered, (
        "the Lab must answer with an engine-offered option id, never an invented one"
    )
    return str(selected[0])


def _drive_equip_ping_pong(policy: ExternalPilotDecisionPolicy, rounds: int) -> list[str]:
    """Alternate the two #718 windows and return the picks on window A only."""
    window_a_picks: list[str] = []
    offset = 0
    for _ in range(rounds):
        offset += 1
        window_a_picks.append(
            _choose(policy, WINDOW_A_OPTIONS, offset, _state(stack=_WINDOW_A_STACK))
        )
        offset += 1
        _choose(policy, WINDOW_B_OPTIONS, offset, _state(stack=_WINDOW_B_STACK))
    return window_a_picks


def test_the_equip_ping_pong_converges_on_the_fourth_window_a() -> None:
    """RED CONTROL for #718: the two-window alternation must stop.

    Window A is the pilot's own choice, so the first three are the Equip.
    The fourth recurrence of that identical window inside the same step is
    where the Lab's liveness bound applies, and from there the seat passes
    priority every time the window comes back.
    """
    policy = _policy()

    picks = _drive_equip_ping_pong(policy, 6)

    first_pass = next(index for index, pick in enumerate(picks) if pick == PASS)
    assert first_pass <= RECURRENCE_TRIP_FRAME - 1, (
        "the recurring priority window must converge by the "
        f"{RECURRENCE_TRIP_FRAME}th recurrence in one step; observed picks {picks}"
    )
    assert picks[:first_pass] == [EQUIP] * first_pass, (
        "recurrence inside a step stays pilot discretion until the bound trips; "
        f"observed picks {picks}"
    )
    assert picks[first_pass:] == [PASS] * (len(picks) - first_pass), (
        "once the bound trips, the recurring window keeps passing priority so "
        f"the step can end; observed picks {picks}"
    )


def test_the_recurrence_bound_stays_a_window_identity_bound() -> None:
    """Three recurrences in one step are still the pilot's own discretion.

    The bound is not a blanket per-step cap: the seat keeps taking its free
    action for the first three occurrences of an identical window.
    """
    policy = _policy()

    picks = [
        _choose(policy, WINDOW_A_OPTIONS, offset, _state(stack=_WINDOW_A_STACK))
        for offset in (1, 2, 3)
    ]

    assert picks == [EQUIP] * 3, f"observed picks {picks}"


def test_a_step_change_between_recurrences_resets_the_bound() -> None:
    """The same window in a different step is a different step's window.

    Three occurrences in one step, then three in the next, then back to the
    first step: the counter is per (turn_number, phase, step), so the seat
    is still free to act rather than being permanently pinned to passing.
    """
    policy = _policy()

    picks = [
        *[
            _choose(policy, WINDOW_A_OPTIONS, offset, _state(stack=_WINDOW_A_STACK))
            for offset in (1, 2, 3)
        ],
        *[
            _choose(
                policy,
                WINDOW_A_OPTIONS,
                offset,
                _state(stack=_WINDOW_A_STACK, step="postcombat_main"),
            )
            for offset in (4, 5, 6)
        ],
        _choose(policy, WINDOW_A_OPTIONS, 7, _state(stack=_WINDOW_A_STACK)),
    ]

    assert picks == [EQUIP] * 7, f"observed picks {picks}"


def test_a_pool_that_changes_between_frames_is_a_different_window() -> None:
    """Money the seat actually floated is progress, not a recurrence.

    Same step, same stack, same options, but the pool differs on every
    frame, so no window ever recurs and nothing converges to passing.
    """
    policy = _policy()

    picks = [
        _choose(policy, WINDOW_A_OPTIONS, offset, _state(stack=_WINDOW_A_STACK, pool_white=white))
        for offset, white in enumerate((0, 1, 2, 3, 4), start=1)
    ]

    assert picks == [EQUIP] * 5, f"observed picks {picks}"


def test_a_stack_that_changes_between_frames_is_a_different_window() -> None:
    """A different stack is a different window, not a recurrence of the old one.

    Three distinct stacks cycling in one step: each window recurs only
    three times, so the bound never trips and the seat keeps acting.
    """
    policy = _policy()
    # Nine activations in one turn: lift the pilot's per-turn action cap
    # (#732) so this test sees the recurrence bound alone.
    policy._TURN_ABILITY_CAP = 100
    stacks = (
        _WINDOW_A_STACK,
        _WINDOW_B_STACK,
        [{"object_id": "spell-2", "name": "Counterspell"}],
    )

    picks = [
        _choose(policy, WINDOW_A_OPTIONS, offset, _state(stack=stacks[(offset - 1) % 3]))
        for offset in (1, 2, 3, 4, 5, 6, 7, 8, 9)
    ]

    assert picks == [EQUIP] * 9, f"observed picks {picks}"


def test_the_recurrence_bound_reads_no_information_the_seat_cannot_see() -> None:
    """An opponent's hidden hand size is not part of the window identity.

    Opponent hand counts are hidden information; a guard fingerprint that
    consumed them would both leak them into Lab-side state and hand a
    looping seat a way to dodge the bound. The same window still trips on
    its fourth recurrence however the opponent's count moves.
    """
    policy = _policy()

    picks = [
        _choose(
            policy,
            WINDOW_A_OPTIONS,
            offset,
            _state(stack=_WINDOW_A_STACK, opponent_hand_count=opponent_hand_count),
        )
        for offset, opponent_hand_count in enumerate((7, 6, 5, 4), start=1)
    ]

    assert picks[:3] == [EQUIP] * 3, f"observed picks {picks}"
    assert picks[3] == PASS, f"observed picks {picks}"


def test_one_seat_recurring_does_not_converge_another_seat() -> None:
    """The bound is per seat: a looping seat must not pass another seat's turn."""
    policy = _policy()

    _drive_equip_ping_pong(policy, 6)

    other = _state(actor_id="actor-2", seat=OTHER_SEAT, stack=_WINDOW_A_STACK)
    picked = _choose(policy, WINDOW_A_OPTIONS, 99, other)
    assert picked == EQUIP, (
        "the other seat has its own first occurrence of this window and keeps "
        f"its discretion; observed {picked}"
    )
