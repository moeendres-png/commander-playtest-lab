"""Regression and contract tests for #1299 (SIMULATE E4: skip forced pass_priority)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, create_revision, games, launch
from commander_lab.studio.play import close_recorded_game
from commander_lab.studio.web import create_app
from tests.unit.test_full_game_pilot_judgment import (
    _PASS,
    _attack_options,
    _card,
    _policy,
    _request,
    _state,
)
from tests.unit.test_studio_builder import _deck, _fill

ROOT = Path(__file__).resolve().parents[2]
HEADER = {"seed": 7, "engine_commit": "a" * 40, "seats": [{"seat": 0}, {"seat": 1}]}


def test_series_engine_enables_skip_forced_decisions_and_honors_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"x")
    monkeypatch.setenv(launch.ENGINE_COMMAND_ENV, f"java -Xmx3g -jar {jar} full-game")
    enabled = launch.series_engine(tmp_path, 3)
    assert enabled is not None
    assert "-Dcommanderlab.fullGame.skipForcedDecisions=true" in enabled.jvm_flags

    monkeypatch.setenv(
        launch.ENGINE_COMMAND_ENV,
        f"java -Xmx3g -Dcommanderlab.fullGame.skipForcedDecisions=false -jar {jar} full-game",
    )
    overridden = launch.series_engine(tmp_path, 3)
    assert overridden is not None
    assert "-Dcommanderlab.fullGame.skipForcedDecisions=false" in overridden.jvm_flags
    assert "-Dcommanderlab.fullGame.skipForcedDecisions=true" not in overridden.jvm_flags


def test_condition3_declare_attacker_resets_block_round_without_priority_frame() -> None:
    policy = _policy()
    state = _state(
        actor_board=[
            _card("myr-0", "Fixture Myr", 1, 1),
            _card("myr-1", "Fixture Myr", 1, 1),
        ],
        opponent_board=[_card("brute", "Fixture Brute", 8, 9)],
        actor_life=6,
    )
    # Combat 1: declare_blocker for seat 1 (actor) skips myr-1 after myr-0 chumps brute.
    req1 = _request(
        "declare_blocker",
        [
            {
                "option_id": "block-myr-0-brute",
                "label": "myr-0 blocks brute",
                "option_type": "declare_blocker",
                "metadata": {"blocker_id": "myr-0", "attacker_id": "brute"},
            }
        ],
        state,
        minimum=0,
        offset=1,
    )
    res1 = policy.decide(req1)
    assert res1["selected_option_ids"] == ["block-myr-0-brute"]

    # Combat 2 (same turn, intervening priority passed forced in bridge): opponent seat 2 declares attacks.
    opp_state = {
        **state,
        "actor_id": "opponent-1",
        "seat": 1,
        "phase": "combat",
        "step": "declare_attackers",
        "players": [
            {**state["players"][1], "is_actor": True, "hand": []},
            {k: v for k, v in state["players"][0].items() if k not in {"hand", "mana_pool"}},
        ],
    }
    opp_att_req = _request(
        "declare_attacker",
        _attack_options("brute", "Fixture Brute"),
        opp_state,
        offset=2,
    )
    opp_att_req["actor_id"] = "opponent-1"
    policy.decide(opp_att_req)
    assert policy._block_round == {}
    assert policy._block_frame_asks == {}

    # Defender myr-1 must still see a fresh round and chump brute.
    req2 = _request(
        "declare_blocker",
        [
            {
                "option_id": "block-myr-1-brute",
                "label": "myr-1 blocks brute",
                "option_type": "declare_blocker",
                "metadata": {"blocker_id": "myr-1", "attacker_id": "brute"},
            }
        ],
        state,
        minimum=0,
        offset=3,
    )
    assert policy.decide(req2)["selected_option_ids"] == ["block-myr-1-brute"]


def test_condition3_step_transition_clears_transient_but_keeps_turn_memory() -> None:
    policy = _policy()
    state = _state(actor_board=[], opponent_board=[])
    # First priority decision establishes step (6, precombat_main, precombat_main)
    policy.decide(_request("priority", [_PASS], state, offset=1))

    # Populate both transient and cross-turn state on seat 1.
    policy._priority_cost_facts[1] = {"src-1": 4}
    policy._last_priority_label[1] = "Cast Spell A"
    policy._last_priority_source[1] = "src-1"
    policy._last_priority_visible_mana[1] = 3
    policy._optional_mana_commitments[1] = {"src-1": (1, 2)}
    policy._turn_actions[1] = (6, Counter({"Spell A": 1}))
    policy._failed_payments[1] = (6, {"Old Failed": 2})
    policy._own_cast_names[1] = ["Spell A"]
    policy._equipped_to[(1, "eq-1")] = (6, "cre-1")

    # Non-priority frame in a NEW step (combat / begin_combat): step transition clears transient state.
    next_step_state = {**state, "phase": "combat", "step": "begin_combat"}
    policy.decide(
        _request(
            "choose_use",
            [
                {
                    "option_id": "yes",
                    "label": "Yes",
                    "option_type": "choose_use",
                    "metadata": {"value": True},
                },
                {
                    "option_id": "no",
                    "label": "No",
                    "option_type": "choose_use",
                    "metadata": {"value": False},
                },
            ],
            next_step_state,
            offset=2,
        )
    )
    assert 1 not in policy._priority_cost_facts
    assert 1 not in policy._last_priority_source
    assert 1 not in policy._last_priority_label
    assert 1 not in policy._last_priority_visible_mana
    assert 1 not in policy._optional_mana_commitments
    # Cross-turn state stays intact.
    assert policy._turn_actions[1][1]["Spell A"] == 1
    assert policy._failed_payments[1][1]["Old Failed"] == 2
    assert policy._own_cast_names[1] == ["Spell A"]
    assert policy._equipped_to[(1, "eq-1")] == (6, "cre-1")


def test_condition3_same_step_different_source_isolation_and_nested_mana_ability() -> None:
    policy = _policy()
    state = _state(
        actor_board=[_card("c1", "Bear", 2, 2)],
        opponent_board=[],
    )
    policy.decide(_request("priority", [_PASS], state, offset=1))
    policy._last_priority_label[1] = "Equip Boots"
    policy._last_priority_source[1] = "boots-1"
    policy._last_priority_visible_mana[1] = 4

    # Nested activated_mana ability of another source (e.g. Hall of Oracles) inside payment: keep outer state.
    nested_mana_req = _request(
        "mana_payment",
        [{"option_id": "cancel", "label": "Cancel payment", "option_type": "cancel_mana_payment"}],
        state,
        offset=2,
    )
    nested_mana_req["source_object"] = {
        "source_object_id": "hall-1",
        "ability_type": "activated_mana",
    }
    policy.decide(nested_mana_req)
    # _remember_failed_payment also ignored cancel from hall-1 when last priority source was boots-1.
    assert 1 not in policy._failed_payments
    assert policy._last_priority_label.get(1) == "Equip Boots"
    assert policy._last_priority_source.get(1) == "boots-1"

    # Unrelated target frame in the same step from a DIFFERENT non-mana source must NOT touch boots-1
    # equipment tracking and must clear stale priority state for seat 1.
    other_target_req = _request(
        "target",
        [
            {
                "option_id": "t1",
                "label": "Bear",
                "option_type": "target",
                "metadata": {"object_id": "c1"},
            }
        ],
        state,
        minimum=1,
        offset=3,
    )
    other_target_req["source_object"] = {"source_object_id": "trigger-99"}
    policy.decide(other_target_req)
    assert (1, "trigger-99") not in policy._equipped_to
    assert (1, "boots-1") not in policy._equipped_to
    assert 1 not in policy._last_priority_source
    assert 1 not in policy._last_priority_label


def test_condition4_telemetry_persisted_and_exposed_by_studio_api(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path)
    try:
        _fill(store, tmp_path)
        create_revision(store, deck_id="test", name="Test", cards=_deck())
    finally:
        store.close()

    recorder = games.GameRecorder(tmp_path, "g-e4", HEADER)
    recorder.record(
        {
            "decision_class": "priority",
            "seat": 0,
            "actor_id": "p0",
            "prompt": "Choose",
            "legal_options": [{"option_id": "o1", "label": "Play Forest"}],
            "pilot_state": {
                "turn_number": 1,
                "phase": "precombat_main",
                "step": "precombat_main",
                "active_player_id": "p0",
                "players": [
                    {
                        "player_id": "p0",
                        "seat": 0,
                        "life": 40,
                        "is_actor": True,
                        "battlefield": [],
                        "graveyard": [],
                        "command": [],
                    },
                    {
                        "player_id": "opponent-1",
                        "seat": 1,
                        "life": 40,
                        "battlefield": [],
                        "graveyard": [],
                        "command": [],
                    },
                ],
                "stack": [],
            },
        },
        {"selected_option_ids": ["o1"]},
    )
    fake_outcome: Any = SimpleNamespace(
        winner_seats=(1,),
        decision_count=19,
        engine_version="2.0.0",
        semantic_transcript_sha256="b" * 64,
        result_payload={"forced_decisions_skipped": 14},
    )
    summary = close_recorded_game(recorder, fake_outcome)
    assert summary["decision_count"] == 19
    assert summary["forced_decisions_skipped"] == 14
    assert summary["frames"] == 1

    with TestClient(create_app(tmp_path)) as client:
        listed = client.get("/api/games").json()
        row = next(entry for entry in listed if entry["game_id"] == "g-e4")
        assert row["result"]["decision_count"] == 19
        assert row["result"]["forced_decisions_skipped"] == 14
        detail = client.get("/api/games/g-e4?start=0&count=10").json()
        assert detail["result"]["decision_count"] == 19
        assert detail["result"]["forced_decisions_skipped"] == 14

    partie_js = (ROOT / "src/commander_lab/studio/static/partie.js").read_text(encoding="utf-8")
    assert "forced_decisions_skipped" in partie_js
    assert "erzwungene Pässe" in partie_js
