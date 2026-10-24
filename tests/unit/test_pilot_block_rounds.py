"""A block declaration is judged as a whole, not attacker by attacker (#989 phase 3).

``block_score`` weighed every attacker alone: a chump block was worth it only when that one
attacker was lethal or left five life. In 24 recorded real games 18 declarations left the pilot
facing lethal damage, and in 7 of them another assignment of the same blockers survived (five
attackers of 4 to 9 power against a pilot at 30 life got no block at all). The engine asks one
blocker at a time, so the pilot keeps the round: what the attackers deal, what the earlier
blockers took off the table, and blocks while what is left is lethal. Every test builds the same
table the old rule got wrong and has a control that shows the rule changes nothing it should not.
"""

from __future__ import annotations

from typing import Any

from commander_lab.engine.rules.full_game import ExternalPilotDecisionPolicy
from commander_lab.engine.rules.full_game_pilot_blocks import (
    BlockRound,
    fresh_round,
    is_pressing,
    note_attackers,
    record_blocks,
    settled_scores,
    unblocked_damage,
    urgent_scores,
)
from tests.unit.test_full_game_pilot_judgment import _PASS, _card, _policy, _request, _state


def _frame(blocker_id: str, attacker_ids: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "option_id": f"block-{blocker_id}-{attacker_id}",
            "label": f"{blocker_id} blocks {attacker_id}",
            "option_type": "declare_blocker",
            "metadata": {"blocker_id": blocker_id, "attacker_id": attacker_id},
        }
        for attacker_id in attacker_ids
    ]


def _declare(
    policy: ExternalPilotDecisionPolicy,
    state: dict[str, Any],
    frames: dict[str, list[str]],
    *,
    offset: int = 1,
) -> dict[str, list[str]]:
    """Ask each blocker in turn, as the engine does; the attackers each one blocks."""
    answers: dict[str, list[str]] = {}
    for blocker_id, attacker_ids in frames.items():
        response = policy.decide(
            _request(
                "declare_blocker",
                _frame(blocker_id, attacker_ids),
                state,
                minimum=0,
                offset=offset,
            )
        )
        prefix = f"block-{blocker_id}-"
        answers[blocker_id] = [
            option_id.removeprefix(prefix) for option_id in response["selected_option_ids"]
        ]
    return answers


def _myrs(count: int) -> list[dict[str, Any]]:
    """1/1 blockers: they kill nothing, so only the pilot's need to survive makes them block."""
    return [_card(f"myr-{index}", "Fixture Myr", 1, 1) for index in range(count)]


def _brute(object_id: str, power: int, **extra: Any) -> dict[str, Any]:
    return _card(object_id, "Fixture Brute", power, 9, **extra)


def _blocked(answers: dict[str, list[str]]) -> list[str]:
    return [attacker for picked in answers.values() for attacker in picked]


def test_attackers_that_are_lethal_together_are_blocked_biggest_first() -> None:
    # 9 + 7 + 6 + 5 + 3 = 30 against 25 life: no single hit is lethal or leaves five life, so the
    # old rule blocked nothing. One block of the biggest brings it to 21; then it is survivable.
    state = _state(
        actor_board=_myrs(5),
        opponent_board=[
            _brute("a9", 9),
            _brute("a7", 7),
            _brute("a6", 6),
            _brute("a5", 5),
            _brute("a3", 3),
        ],
        actor_life=25,
    )
    frames = {f"myr-{index}": ["a9", "a7", "a6", "a5", "a3"] for index in range(5)}
    answers = _declare(_policy(), state, frames)
    assert _blocked(answers) == ["a9"]
    assert answers["myr-0"] == ["a9"]


def test_a_survivable_table_gets_no_chump_block() -> None:
    # Control: the same table at 40 life is 30 damage, survivable, so the ordinary rule decides
    # and the 1/1s stay home.
    state = _state(
        actor_board=_myrs(5),
        opponent_board=[
            _brute("a9", 9),
            _brute("a7", 7),
            _brute("a6", 6),
            _brute("a5", 5),
            _brute("a3", 3),
        ],
        actor_life=40,
    )
    frames = {f"myr-{index}": ["a9", "a7", "a6", "a5", "a3"] for index in range(5)}
    assert _blocked(_declare(_policy(), state, frames)) == []


def test_each_blocker_takes_a_different_attacker() -> None:
    # 8 + 8 + 8 = 24 against 10 life. The old rule judged each blocker alone and sent all three
    # to the same attacker (the best-ranked option of every frame); now each one takes another.
    state = _state(
        actor_board=_myrs(3),
        opponent_board=[_brute("a", 8), _brute("b", 8), _brute("c", 8)],
        actor_life=10,
    )
    answers = _declare(_policy(), state, {f"myr-{index}": ["a", "b", "c"] for index in range(3)})
    assert sorted(_blocked(answers)) == ["a", "b", "c"]


def test_a_chump_does_not_repeat_on_an_attacker_that_is_already_blocked() -> None:
    # 8 power against 10 life leaves 2, so every 1/1 judged alone chumps it. Once one has, the
    # next stays home; the old rule sent all three to the same attacker.
    state = _state(actor_board=_myrs(3), opponent_board=[_brute("a", 8)], actor_life=10)
    answers = _declare(_policy(), state, {f"myr-{index}": ["a"] for index in range(3)})
    assert answers == {"myr-0": ["a"], "myr-1": [], "myr-2": []}


def test_a_blocker_that_kills_still_joins_a_block_on_an_attacker_that_is_blocked() -> None:
    # Control: the second blocker survives and kills, so the block is worth making.
    state = _state(
        actor_board=[*_myrs(1), _card("dragon", "Dragon Token", 6, 6)],
        opponent_board=[_card("orc", "Merciless Executioner", 3, 1)],
        actor_life=4,
    )
    answers = _declare(_policy(), state, {"myr-0": ["orc"], "dragon": ["orc"]})
    assert answers["dragon"] == ["orc"]


def test_a_trampler_is_only_held_back_by_the_toughness_of_its_blocker() -> None:
    # 12 life, a 10-power trampler and a 6-power brute: blocking the trampler with a 1/1 saves
    # one damage, blocking the brute saves six and brings the table to 10.
    state = _state(
        actor_board=_myrs(1),
        opponent_board=[_brute("tramp", 10, abilities=["Trample"]), _brute("brute", 6)],
        actor_life=12,
    )
    assert _declare(_policy(), state, {"myr-0": ["tramp", "brute"]}) == {"myr-0": ["brute"]}


def test_double_strike_counts_twice() -> None:
    # 12 life: a 6-power double striker deals 12 and a 7-power brute 7. Both look like a chump
    # worth making when judged alone (the old rule broke the tie by name); the block that takes
    # the 12 off the table is the double striker's.
    state = _state(
        actor_board=_myrs(1),
        opponent_board=[_brute("ds", 6, abilities=["Double strike"]), _brute("zbrute", 7)],
        actor_life=12,
    )
    assert _declare(_policy(), state, {"myr-0": ["ds", "zbrute"]}) == {"myr-0": ["ds"]}


def test_a_commander_hit_that_would_end_the_game_is_blocked_at_full_life() -> None:
    # 17 commander damage taken already, 5 power more makes 22: dead at 40 life.
    state = _state(
        actor_board=_myrs(1),
        opponent_board=[_card("cmd", "Fixture Commander", 5, 5), _brute("brute", 9)],
    )
    state["commander_status"].append(
        {
            "owner_id": "opponent-1",
            "name": "Fixture Commander",
            "commander_damage_to_player": [{"player_id": "actor", "total": 17}],
            "casts_from_command": 0,
        }
    )
    assert _declare(_policy(), state, {"myr-0": ["cmd", "brute"]}) == {"myr-0": ["cmd"]}


def test_a_commander_hit_that_is_not_lethal_is_judged_as_before() -> None:
    # Control: 10 damage taken, 5 more is 15, no clock to answer; 40 life, no block.
    state = _state(
        actor_board=_myrs(1),
        opponent_board=[_card("cmd", "Fixture Commander", 5, 5), _brute("brute", 9)],
    )
    state["commander_status"].append(
        {
            "owner_id": "opponent-1",
            "name": "Fixture Commander",
            "commander_damage_to_player": [{"player_id": "actor", "total": 10}],
            "casts_from_command": 0,
        }
    )
    assert _declare(_policy(), state, {"myr-0": ["cmd", "brute"]}) == {"myr-0": []}


def test_a_menace_attacker_is_not_something_one_blocker_takes_off_the_table() -> None:
    # 7 menace + 5 against 10 life: the engine rejects a lone block of the menace attacker, so the
    # blocker goes to the 5-power brute, which brings the table to 7.
    state = _state(
        actor_board=_myrs(1),
        opponent_board=[_brute("mean", 7, abilities=["Menace"]), _brute("brute", 5)],
        actor_life=10,
    )
    assert _declare(_policy(), state, {"myr-0": ["mean", "brute"]}) == {"myr-0": ["brute"]}


def test_a_new_combat_in_the_same_turn_starts_a_new_round() -> None:
    # An extra combat is a separate accepted declaration. The priority window between them ends
    # the round: the first combat's block on the brute must not count in the second, where only
    # the other creature can block it.
    policy = _policy()
    state = _state(actor_board=_myrs(2), opponent_board=[_brute("brute", 8)], actor_life=6)
    first = _declare(policy, state, {"myr-0": ["brute"], "myr-1": ["brute"]}, offset=1)
    assert first == {"myr-0": ["brute"], "myr-1": []}
    policy.decide(_request("priority", [_PASS], state, offset=2))
    assert _declare(policy, state, {"myr-1": ["brute"]}, offset=3) == {"myr-1": ["brute"]}


def test_a_new_turn_starts_a_new_round() -> None:
    policy = _policy()
    state = _state(actor_board=_myrs(1), opponent_board=[_brute("brute", 8)], actor_life=6)
    frames = {"myr-0": ["brute"]}
    assert _declare(policy, state, frames, offset=1) == {"myr-0": ["brute"]}
    # No decision of another class in between (a skipped priority window): the turn moved on.
    state["turn_number"] += 1
    assert _declare(policy, state, frames, offset=2) == {"myr-0": ["brute"]}


def test_the_round_keeps_the_ordinary_block_when_nothing_is_lethal() -> None:
    # Control: a dragon that survives and kills still blocks a small attacker at full life.
    state = _state(
        actor_board=[_card("dragon", "Dragon Token", 6, 6)],
        opponent_board=[_card("orc", "Merciless Executioner", 3, 1)],
    )
    assert _declare(_policy(), state, {"dragon": ["orc"]}) == {"dragon": ["orc"]}


def _round_for(state: dict[str, Any], attacker_ids: list[str]) -> BlockRound:
    round_ = BlockRound(turn=state["turn_number"])
    note_attackers(round_, _frame("myr-0", attacker_ids), state)
    return round_


def test_round_damage_counts_power_doubled_by_double_strike() -> None:
    state = _state(
        actor_board=_myrs(1),
        opponent_board=[_brute("ds", 4, abilities=["Double strike"]), _brute("plain", 5)],
    )
    round_ = _round_for(state, ["ds", "plain"])
    assert round_.damage == {"ds": 8.0, "plain": 5.0}
    assert unblocked_damage(round_) == 13.0
    assert is_pressing(round_, 13.0) and not is_pressing(round_, 14.0)


def test_a_recorded_block_comes_off_the_table_and_a_re_ask_replaces_it() -> None:
    state = _state(
        actor_board=[_card("big", "Fixture Wall", 0, 7)],
        opponent_board=[_brute("tramp", 10, abilities=["Trample"]), _brute("plain", 5)],
    )
    round_ = _round_for(state, ["tramp", "plain"])
    options = _frame("big", ["tramp", "plain"])
    record_blocks(round_, "big", options[:1], state)
    # The wall stops seven of the trampler's ten.
    assert unblocked_damage(round_) == 3.0 + 5.0
    record_blocks(round_, "big", options[1:], state)
    assert unblocked_damage(round_) == 10.0
    record_blocks(round_, "big", [], state)
    assert unblocked_damage(round_) == 15.0


def test_urgent_scores_are_none_while_the_table_is_survivable() -> None:
    state = _state(
        actor_board=_myrs(1), opponent_board=[_brute("a", 5), _brute("b", 4)], actor_life=10
    )
    round_ = _round_for(state, ["a", "b"])
    options = _frame("myr-0", ["a", "b"])
    assert urgent_scores(round_, "myr-0", options, [0.0, 0.0], state) is None
    state["players"][0]["life"] = 9
    scores = urgent_scores(round_, "myr-0", options, [0.0, 0.0], state)
    assert scores is not None and scores[0] > scores[1] > 0.0


def test_settled_scores_only_cap_a_chump_on_a_blocked_attacker() -> None:
    state = _state(
        actor_board=[_card("big", "Fixture Wall", 0, 7), *_myrs(1)],
        opponent_board=[_brute("a", 5), _brute("b", 5)],
    )
    round_ = _round_for(state, ["a", "b"])
    options = _frame("myr-0", ["a", "b"])
    record_blocks(round_, "big", _frame("big", ["a"]), state)
    assert settled_scores(round_, "myr-0", options, [1.5, 1.5], [True, True]) == [0.0, 1.5]
    # A block that survives or kills is not a chump and is left to the ordinary rule.
    assert settled_scores(round_, "myr-0", options, [2.0, 1.5], [False, True]) == [2.0, 1.5]
    # The blocker's own earlier answer does not count against its re-ask.
    assert settled_scores(round_, "big", _frame("big", ["a"]), [1.5], [True]) == [1.5]


def test_a_new_turn_gives_a_fresh_round() -> None:
    stored = BlockRound(turn=4)
    stored.damage["x"] = 3.0
    assert fresh_round(stored, 4) is stored
    assert fresh_round(stored, 5).damage == {}
    assert fresh_round(None, 5).turn == 5
