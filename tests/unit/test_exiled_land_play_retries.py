"""Unchanged exiled-card play loops stop without inferring land legality."""

from typing import Any

import pytest

from tests.unit.test_full_game_pilot_mana_and_may import _boolean, _policy, _state

PLAY = "Play Plains?"
CONTINUE = "Continue playing the exiled cards?"
SOURCE = {"source_object_id": "dungeon", "ability_original_id": "ability"}


def ask(
    policy: Any,
    prompt: str,
    offset: int,
    *,
    state: Any = None,
    source: Any = SOURCE,
    only_yes: bool = False,
) -> str:
    request = _boolean("playforfree", prompt, offset=offset)
    request["source_object"] = source
    if state is not None:
        request["pilot_state"] = state
    if only_yes:
        request["legal_options"] = [o for o in request["legal_options"] if o["metadata"]["value"]]
    return str(policy.decide(request)["selected_option_ids"][0])


def test_unchanged_play_continue_retry_ends() -> None:
    policy = _policy()
    assert ask(policy, PLAY, 1) == "yes"
    assert ask(policy, CONTINUE, 2) == "no"


def test_successful_play_changed_state_allows_same_name() -> None:
    policy = _policy()
    assert ask(policy, PLAY, 1) == "yes"
    changed = _state()
    changed["players"][0]["battlefield"].append({"name": "Plains", "object_id": "new"})
    assert ask(policy, CONTINUE, 2, state=changed) == "yes"
    assert ask(policy, PLAY, 3, state=changed) == "yes"


@pytest.mark.parametrize("change", ["source", "turn", "seat", "unknown", "other_prompt"])
def test_scope_or_intervening_prompt_keeps_normal_choice(change: str) -> None:
    policy = _policy()
    assert ask(policy, PLAY, 1) == "yes"
    state = _state()
    source: Any = SOURCE
    prompt = CONTINUE
    if change == "source":
        source = {"source_object_id": "different", "ability_original_id": "ability"}
    elif change == "turn":
        state["turn_number"] += 1
    elif change == "seat":
        state["seat"] = 1
    elif change == "unknown":
        source = {"source_object_id": "dungeon"}
    else:
        prompt = "Continue playing cards now?"
    assert ask(policy, prompt, 3, state=state, source=source) == "yes"


def test_yes_only_remains_reachable() -> None:
    policy = _policy()
    ask(policy, PLAY, 1)
    assert ask(policy, CONTINUE, 2, only_yes=True) == "yes"


def test_intervening_boolean_choice_clears_attempt() -> None:
    policy = _policy()
    ask(policy, PLAY, 1)
    ask(policy, "A different question?", 2)
    assert ask(policy, CONTINUE, 3) == "yes"
