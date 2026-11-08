"""Rank an offered open finishing attack against existing commander pressure."""

from typing import Any

import pytest

from commander_lab.agents import GenericCommanderPilot, KorvoldPilot, RogShaiPilot
from commander_lab.engine.rules.full_game import _RuntimePilot
from commander_lab.engine.rules.full_game_pilot_views import attack_score
from commander_lab.models import PilotConfig, PilotStrength
from tests.unit.test_full_game_pilot_commander_pressure import (
    _attack_request,
    _policy,
    _with_commander_damage,
)


def _request(life: int | None = 3) -> dict[str, Any]:
    request = _with_commander_damage(_attack_request(), {"opponent-3": 20})
    request["pilot_state"]["players"][1]["life"] = life
    request["legal_options"] = [
        option for option in request["legal_options"] if option["option_id"] != "attack-2"
    ]
    return request


def _pick(request: dict[str, Any], pilot_type: type, strength: PilotStrength) -> str:
    policy = _policy(1)
    runtime = policy._pilots[1]
    policy._pilots[1] = _RuntimePilot(
        binding=runtime.binding,
        pilot=pilot_type(PilotConfig(pilot_name="auto", strength=strength)),
    )
    return policy.decide(request)["selected_option_ids"][0]


def _window(request: dict[str, Any]) -> bool:
    option = next(o for o in request["legal_options"] if o["option_id"] == "attack-1")
    return bool(attack_score(option, request["pilot_state"])[1].get("lethal_window"))


@pytest.mark.parametrize("pilot_type", [GenericCommanderPilot, KorvoldPilot, RogShaiPilot])
@pytest.mark.parametrize("pressure", [14, 18, 20])
@pytest.mark.parametrize(
    "strength", [PilotStrength.AVERAGE, PilotStrength.STRONG, PilotStrength.NEAR_OPTIMAL_HEURISTIC]
)
def test_open_finish_beats_another_defenders_commander_pressure(
    pilot_type: type, strength: PilotStrength, pressure: int
) -> None:
    request = _with_commander_damage(_request(), {"opponent-3": pressure})
    assert _window(request)
    assert _pick(request, pilot_type, strength) == "attack-1"


def test_nonlethal_and_blocked_attacks_do_not_get_the_window() -> None:
    nonlethal = _request(4)
    assert not _window(nonlethal)
    assert (
        _pick(nonlethal, GenericCommanderPilot, PilotStrength.NEAR_OPTIMAL_HEURISTIC) == "attack-3"
    )

    blocked = _request()
    blocked["pilot_state"]["players"][1]["battlefield"].append(
        {
            "object_id": "blocker",
            "name": "Birds of Paradise",
            "power": 0,
            "toughness": 1,
            "tapped": False,
        }
    )
    assert not _window(blocked)
    assert _pick(blocked, GenericCommanderPilot, PilotStrength.NEAR_OPTIMAL_HEURISTIC) == "attack-3"


def test_unknown_life_never_creates_a_finishing_window() -> None:
    request = _request(None)
    request["pilot_state"]["players"][0]["battlefield"][0]["power"] = 40
    assert not _window(request)


@pytest.mark.parametrize("life", [True, False, 0, -1])
def test_invalid_life_never_creates_a_finishing_window(life: Any) -> None:
    request = _request(life)
    assert not _window(request)


@pytest.mark.parametrize("flag", [False, "true", None])
@pytest.mark.parametrize("kind", ["combat_target", "removal_target"])
def test_only_boolean_true_on_a_combat_target_gets_the_bonus(flag: Any, kind: str) -> None:
    request = _request()
    policy = _policy(1)
    runtime = policy._pilots[1]
    state = policy._pilot_state(runtime, request["pilot_state"])
    option = next(o for o in request["legal_options"] if o["option_id"] == "attack-1")
    action = policy._combat_action(option, request["pilot_state"])
    baseline = action.model_copy(update={"action_kind": kind})
    flagged = baseline.model_copy(update={"metadata": {**baseline.metadata, "lethal_window": flag}})
    components = runtime.pilot._base_components
    assert components(state, flagged)["win_progress"] == components(state, baseline)["win_progress"]


def test_true_window_increases_only_combat_target_win_progress() -> None:
    request = _request()
    policy = _policy(1)
    runtime = policy._pilots[1]
    state = policy._pilot_state(runtime, request["pilot_state"])
    option = next(o for o in request["legal_options"] if o["option_id"] == "attack-1")
    action = policy._combat_action(option, request["pilot_state"])
    components = runtime.pilot._base_components
    for kind in ("combat_target", "removal_target"):
        baseline = action.model_copy(update={"action_kind": kind})
        flagged = baseline.model_copy(
            update={"metadata": {**baseline.metadata, "lethal_window": True}}
        )
        difference = (
            components(state, flagged)["win_progress"] - components(state, baseline)["win_progress"]
        )
        if kind == "combat_target":
            assert difference > 0.0
        else:
            assert difference == 0.0


def test_crackback_danger_does_not_hide_an_open_finish() -> None:
    request = _request()
    request["pilot_state"]["players"][0]["life"] = 5
    request["pilot_state"]["players"][3]["battlefield"].append(
        {"object_id": "threat", "name": "Grave Titan", "power": 6, "toughness": 6, "tapped": True}
    )
    assert _window(request)
    assert _pick(request, GenericCommanderPilot, PilotStrength.NEAR_OPTIMAL_HEURISTIC) == "attack-1"


def test_no_finishing_defender_is_invented_when_not_offered() -> None:
    request = _request()
    request["legal_options"] = [o for o in request["legal_options"] if o["option_id"] != "attack-1"]
    assert _pick(request, GenericCommanderPilot, PilotStrength.NEAR_OPTIMAL_HEURISTIC) == "attack-3"
