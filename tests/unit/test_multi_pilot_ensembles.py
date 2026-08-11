from __future__ import annotations

import json
import random
from pathlib import Path

import pytest
from pydantic import ValidationError

from commander_lab.agents.ensemble import PilotEnsembleRunner, PilotRegistry, default_ensembles
from commander_lab.agents.pilots import build_pilot
from commander_lab.engine.structural import load_project_structural_decks
from commander_lab.models import (
    CardRole,
    PilotActionView,
    PilotCommanderView,
    PilotConfig,
    PilotInformationPolicy,
    PilotOpponentView,
    PilotStateView,
    PilotStrength,
)

ROOT = Path(__file__).resolve().parents[2]


def _state(
    *, strategy: str, commanders=(), roles=None, battlefield=(), graveyard=5, threat=7.0
) -> PilotStateView:
    return PilotStateView(
        player_id="p1",
        deck_id=f"test/{strategy}",
        strategy=strategy,
        turn=6,
        pod_size=4,
        life=32,
        hand_size=6,
        mana_available=7,
        lands=5,
        ramp_mana=2,
        resources=3,
        tokens=3,
        board_power=5,
        engine_value=2,
        graveyard_size=graveyard,
        battlefield_names=tuple(battlefield),
        hand_names=(),
        role_counts=roles or {},
        commanders=tuple(commanders),
        opponents=(
            PilotOpponentView(
                player_id="p2",
                life=9,
                threat=threat,
                board_power=8,
                engine_value=4,
                graveyard_size=8,
                hand_size=5,
            ),
            PilotOpponentView(
                player_id="p3",
                life=24,
                threat=4,
                board_power=4,
                engine_value=2,
                graveyard_size=3,
                hand_size=4,
            ),
            PilotOpponentView(
                player_id="p4",
                life=30,
                threat=3,
                board_power=3,
                engine_value=1,
                graveyard_size=2,
                hand_size=3,
            ),
        ),
    )


def _action(
    action_id: str,
    name: str,
    *,
    kind="card",
    roles=(),
    remaining=1.0,
    immediate=0.7,
    metadata=None,
    threat=0.0,
    power=0.0,
) -> PilotActionView:
    role_set = frozenset(roles)
    return PilotActionView(
        action_id=action_id,
        action_kind=kind,
        card_name=name,
        mana_cost=3,
        roles=role_set,
        role_strengths={role: 1.0 for role in role_set},
        floor_value=0.7,
        immediate_impact=immediate,
        remaining_mana=remaining,
        target_threat=threat,
        threat_score=threat,
        base_power=power,
        metadata=metadata or {},
    )


def test_registry_has_required_profiles_and_stable_hashes() -> None:
    registry = PilotRegistry(ROOT)
    profiles = registry.profiles()
    names = {profile.pilot_name for profile in profiles}
    assert {
        "KorvoldValuePilot",
        "KorvoldSacrificePilot",
        "KorvoldLandRebuildPilot",
        "KorvoldAggressivePilot",
        "KorvoldConservativePilot",
        "RogShaiTempoPilot",
        "RogShaiVoltronPilot",
        "RogShaiSpellslingerPilot",
        "RogShaiControlPilot",
        "RogShaiProtectedFinishPilot",
    } <= names
    assert all(len(profile.parameter_hash) == 64 for profile in profiles)
    assert all(not profile.information_policy.hidden_opponent_hands for profile in profiles)
    assert all(not profile.information_policy.random_library_order for profile in profiles)
    assert registry.profiles() == profiles


def test_omniscient_policy_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PilotInformationPolicy(hidden_opponent_hands=True)
    with pytest.raises(ValidationError):
        PilotInformationPolicy(exact_future_draws=True)


def test_all_profiles_select_only_supplied_legal_actions() -> None:
    actions = (_action("a", "Engine", roles=(CardRole.ENGINE,)), _action("b", "Pass", kind="pass"))
    for profile in PilotRegistry(ROOT).profiles():
        state = _state(strategy=profile.commander_family)
        pilot = build_pilot(
            PilotConfig(pilot_name=profile.pilot_name, strength=PilotStrength.STRONG),
            strategy=profile.commander_family,
        )
        selected = pilot.choose_action(state, actions, random.Random(7)).selected_action_id
        assert selected in {action.action_id for action in actions}


def test_korvold_profiles_diverge_on_sacrifice_and_rebuild() -> None:
    state = _state(strategy="korvold", graveyard=10)
    outlet = _action(
        "outlet", "Free Outlet", roles=(CardRole.SACRIFICE_OUTLET,), metadata={"sacrifice_value": 3}
    )
    value = _action("value", "Draw Engine", roles=(CardRole.DRAW, CardRole.ENGINE))
    rebuild = _action(
        "rebuild",
        "Aftermath Analyst",
        roles=(CardRole.RECURSION, CardRole.LAND_SYNERGY),
        metadata={"rebuild_line": True},
    )
    sacrifice = build_pilot(
        PilotConfig(pilot_name="KorvoldSacrificePilot", strength=PilotStrength.STRONG),
        strategy="korvold",
    )
    land = build_pilot(
        PilotConfig(pilot_name="KorvoldLandRebuildPilot", strength=PilotStrength.STRONG),
        strategy="korvold",
    )
    assert (
        sacrifice.evaluate_action(state, outlet).total_utility
        > sacrifice.evaluate_action(state, value).total_utility
    )
    assert (
        land.evaluate_action(state, rebuild).total_utility
        > land.evaluate_action(state, value).total_utility
    )


def test_land_rebuild_pilot_avoids_visible_graveyard_hate() -> None:
    state = _state(strategy="korvold", graveyard=12)
    exposed = _action(
        "grave",
        "Graveyard Line",
        roles=(CardRole.RECURSION, CardRole.LAND_SYNERGY),
        metadata={"graveyard_hate_exposed": True},
    )
    safe = _action("safe", "Safe Engine", roles=(CardRole.ENGINE,))
    pilot = build_pilot(
        PilotConfig(pilot_name="KorvoldLandRebuildPilot", strength=PilotStrength.STRONG),
        strategy="korvold",
    )
    assert (
        pilot.evaluate_action(state, safe).total_utility
        > pilot.evaluate_action(state, exposed).total_utility
    )


def test_rogshai_control_spends_counter_only_on_real_threat() -> None:
    state = _state(strategy="rogshai", roles={CardRole.COUNTER: 1})
    harmless = _action(
        "harmless", "Counter harmless value", kind="counter", roles=(CardRole.COUNTER,), threat=2
    )
    win = _action(
        "win", "Counter win attempt", kind="counter", roles=(CardRole.COUNTER,), threat=10
    )
    pilot = build_pilot(
        PilotConfig(pilot_name="RogShaiControlPilot", strength=PilotStrength.STRONG),
        strategy="rogshai",
    )
    assert (
        pilot.evaluate_action(state, win).total_utility
        > pilot.evaluate_action(state, harmless).total_utility
    )


def test_protected_finish_pilot_requires_finish_window() -> None:
    commanders = (
        PilotCommanderView(
            name="Ishai, Ojutai Dragonspeaker",
            base_cost=4,
            next_cost=4,
            casts=1,
            on_battlefield=True,
            power=8,
        ),
    )
    state = _state(strategy="rogshai", commanders=commanders)
    unsafe = _action(
        "unsafe", "Jeska, Thrice Reborn", remaining=0, metadata={"protected_finish_window": False}
    )
    safe = _action(
        "safe", "Jeska, Thrice Reborn", remaining=1, metadata={"protected_finish_window": True}
    )
    pilot = build_pilot(
        PilotConfig(pilot_name="RogShaiProtectedFinishPilot", strength=PilotStrength.STRONG),
        strategy="rogshai",
    )
    assert (
        pilot.evaluate_action(state, safe).total_utility
        > pilot.evaluate_action(state, unsafe).total_utility
    )


def test_equal_ensembles_have_five_unique_members() -> None:
    for ensemble in default_ensembles():
        assert len(ensemble.members) == 5
        assert len({member.pilot_name for member in ensemble.members}) == 5
        assert sum(member.weight for member in ensemble.members) == pytest.approx(1.0)


def test_golden_scenario_registry_covers_requested_cases() -> None:
    payload = json.loads((ROOT / "data/pilots/golden_scenarios.json").read_text(encoding="utf-8"))
    ids = {row["scenario_id"] for row in payload["scenarios"]}
    assert ids == {
        "commander-without-immediate-value",
        "protected-commander-window",
        "boardwipe-threat",
        "opponent-can-win",
        "multiple-sacrifice-options",
        "multiple-combat-targets",
        "jeska-kill-window",
        "kediss-versus-single-target-kill",
        "graveyard-package-under-hate",
        "rebuild-after-wipe",
    }


def test_ensemble_summary_reports_worst_median_and_robustness() -> None:
    runner = PilotEnsembleRunner(
        ROOT,
        load_project_structural_decks(
            ROOT, include_synthetic_fixtures=True, include_current_opponents=True
        ),
    )
    ensemble = runner.registry.ensemble("rogshai.equal.v1")
    results = {}
    for index, member in enumerate(ensemble.members):
        results[member.pilot_name] = {
            "average_placement": 2.0 + index * 0.1,
            "place_1_share": 0.3 - index * 0.01,
            "average_commander_damage": 4 + index,
            "average_normal_damage": 12 + index,
            "average_engine_value": 5 + index,
            "political_visibility": 0.2 + index * 0.02,
            "deviation_from_baseline": {"average_placement": index * 0.1},
        }
    summary = runner.ensemble_summary({"results": results}, ensemble)
    assert summary["worst_pilot"]["pilot_name"] == ensemble.members[-1].pilot_name
    assert summary["median_pilot"]["pilot_name"] == ensemble.members[2].pilot_name
    assert summary["pilot_robustness"]["robust"] is True
