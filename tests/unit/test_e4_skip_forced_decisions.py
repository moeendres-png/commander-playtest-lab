"""Regression and contract tests for #1299 (SIMULATE E4: skip forced pass_priority)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from commander_lab.agents import GenericCommanderPilot
from commander_lab.engine.rules.full_game import (
    ExternalPilotDecisionPolicy,
    FullGamePilotBinding,
    _RuntimePilot,
)
from commander_lab.models import PilotConfig, PilotStrength
from commander_lab.studio import games, launch
from commander_lab.studio.play import close_recorded_game

ROOT = Path(__file__).resolve().parents[2]
HEADER = {"seed": 7, "engine_commit": "a" * 40, "seats": [{"seat": 0}, {"seat": 1}]}
_PASS: dict[str, Any] = {
    "option_id": "pass",
    "label": "Pass priority",
    "option_type": "pass_priority",
}


def _policy() -> ExternalPilotDecisionPolicy:
    runtimes: list[_RuntimePilot] = []
    for seat in range(1, 5):
        config = PilotConfig(pilot_name="auto", strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC)
        binding = FullGamePilotBinding(
            seat=seat,
            deck_id=f"fixture-{seat}",
            strategy="generic",
            commander_names=("Esior, Wardwing Familiar",),
            config=config,
            pilot_identity="GenericCommanderPilot",
            pilot_version="1.0.0",
            decision_policy_version="xmage-full-game-policy-1.0.0",
        )
        runtimes.append(_RuntimePilot(binding=binding, pilot=GenericCommanderPilot(config)))
    return ExternalPilotDecisionPolicy(tuple(runtimes), 20261011)  # type: ignore[arg-type]


def _card(
    object_id: str, name: str, power: int = 0, toughness: int = 0, **extra: Any
) -> dict[str, Any]:
    return {
        "object_id": object_id,
        "name": name,
        "tapped": False,
        "power": power,
        "toughness": toughness,
        "damage": 0,
        **extra,
    }


def _state(
    *,
    actor_board: list[dict[str, Any]] | None = None,
    opponent_board: list[dict[str, Any]] | None = None,
    actor_life: int = 40,
    opponent_life: int = 40,
) -> dict[str, Any]:
    lands = [_card(f"island-{index}", "Island") for index in range(3)]
    actor = {
        "player_id": "actor",
        "seat": 0,
        "life": actor_life,
        "hand_count": 0,
        "library_count": 90,
        "graveyard_count": 0,
        "battlefield": [*lands, *(actor_board or [])],
        "graveyard": [],
        "command": [],
        "hand": [],
        "mana_pool": {},
    }
    opponents = [
        {
            "player_id": f"opponent-{seat}",
            "seat": seat,
            "life": opponent_life if seat == 1 else 40,
            "hand_count": 7,
            "library_count": 92,
            "graveyard_count": 0,
            "battlefield": list(opponent_board or []) if seat == 1 else [],
            "graveyard": [],
            "command": [],
        }
        for seat in range(1, 4)
    ]
    return {
        "game_id": "engine-opaque",
        "actor_id": "actor",
        "seat": 0,
        "turn_number": 6,
        "active_player_id": "actor",
        "priority_player_id": "actor",
        "phase": "precombat_main",
        "step": "precombat_main",
        "players": [actor, *opponents],
        "stack": [],
        "commander_status": [
            {
                "owner_id": "actor",
                "name": "Esior, Wardwing Familiar",
                "commander_damage_to_player": [],
                "casts_from_command": 1,
            }
        ],
    }


def _request(
    decision_class: str,
    options: list[dict[str, Any]],
    state: dict[str, Any],
    *,
    minimum: int = 1,
    maximum: int = 1,
    offset: int = 1,
) -> dict[str, Any]:
    return {
        "decision_id": f"opaque-{decision_class}-{offset}",
        "decision_offset": offset,
        "actor_id": "actor",
        "decision_class": decision_class,
        "pilot_state": state,
        "context": {},
        "minimum_selections": minimum,
        "maximum_selections": maximum,
        "legal_options": options,
        "prompt": decision_class,
    }


def _attack_options(attacker_id: str, name: str) -> list[dict[str, Any]]:
    return [
        {
            "option_id": "hold",
            "label": f"Do not attack with {name}",
            "option_type": "hold_attacker",
            "metadata": {"object_id": attacker_id, "name": name},
        },
        {
            "option_id": "attack-1",
            "label": f"{name} attacks Seat 2",
            "option_type": "declare_attacker",
            "metadata": {"object_id": attacker_id, "name": name, "defender_id": "opponent-1"},
        },
    ]


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


def test_condition4_telemetry_persisted_and_exposed_by_studio_games(tmp_path: Path) -> None:
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

    listed = games.list_games(tmp_path)
    row = next(entry for entry in listed if entry["game_id"] == "g-e4")
    assert row["result"]["decision_count"] == 19
    assert row["result"]["forced_decisions_skipped"] == 14
    detail = games.read_game(tmp_path, "g-e4", start=0, count=10)
    assert detail["result"]["decision_count"] == 19
    assert detail["result"]["forced_decisions_skipped"] == 14

    partie_js = (ROOT / "src/commander_lab/studio/static/partie.js").read_text(encoding="utf-8")
    assert "forced_decisions_skipped" in partie_js
    assert "erzwungene Pässe" in partie_js


# ---- interactive play uses the series switches (#1591) ----------------------------------------

SKIP_ON = "-Dcommanderlab.fullGame.skipForcedDecisions=true"
SKIP_OFF = "-Dcommanderlab.fullGame.skipForcedDecisions=false"


def test_interactive_command_has_the_series_flags_and_keeps_the_jar_and_launch_words(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"x")
    monkeypatch.setenv(launch.ENGINE_COMMAND_ENV, f"java -Xmx3g -jar {jar} full-game")
    base = launch.engine_command(tmp_path)
    assert base == ("java", "-Xmx3g", "-jar", str(jar), "full-game")
    command = launch.interactive_bridge_command(base)
    assert command is not None
    assert SKIP_ON in command and "-XX:+UseSerialGC" in command
    assert command[0] == "java" and command[-3:] == ("-jar", str(jar.resolve()), "full-game")
    assert "-Xmx3g" in command and command.count(SKIP_ON) == 1
    # no batch property: an interactive game is one game in one JVM
    assert not any("gamesPerJvm" in part for part in command)
    # the series command is the same command plus the batch property, nothing else
    series = launch.series_engine(tmp_path, 1)
    assert series is not None and series.command == command


def test_interactive_command_honours_the_environment_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"x")
    # the switch can be turned off in the environment command (the "without switch" probe)
    off = launch.interactive_bridge_command(("java", SKIP_OFF, "-jar", str(jar), "full-game"))
    assert off is not None and SKIP_OFF in off and SKIP_ON not in off
    # serial GC is not added twice
    twice = launch.interactive_bridge_command(
        ("java", "-XX:+UseSerialGC", "-jar", str(jar), "full-game")
    )
    assert twice is not None and twice.count("-XX:+UseSerialGC") == 1
    # a launcher that is not java, or has no -jar file, is used as it is; no engine stays none
    assert launch.interactive_bridge_command(("/opt/wrapper", "full-game")) == (
        "/opt/wrapper",
        "full-game",
    )
    assert launch.interactive_bridge_command(("java", "-jar")) == ("java", "-jar")
    assert launch.interactive_bridge_command(None) is None
    # the environment command itself is not changed: it is still what engine_command returns
    monkeypatch.setenv(launch.ENGINE_COMMAND_ENV, f"java -jar {jar} full-game")
    assert launch.engine_command(tmp_path) == ("java", "-jar", str(jar), "full-game")


def test_interactive_command_names_the_archive_only_when_present(tmp_path: Path) -> None:
    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"x")
    base = ("java", "-jar", str(jar), "full-game")
    plain = launch.interactive_bridge_command(base)
    assert plain is not None
    assert not any(part.startswith("-XX:SharedArchiveFile=") for part in plain)
    jar.with_suffix(".jsa").write_bytes(b"x")
    archived = launch.interactive_bridge_command(base)
    assert archived is not None
    assert any(part.startswith("-XX:SharedArchiveFile=") for part in archived)


def test_the_play_manager_starts_the_session_with_the_fast_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from commander_lab.models import RulesDeckInput
    from commander_lab.studio import play

    jar = tmp_path / "bridge.jar"
    jar.write_bytes(b"x")
    monkeypatch.setenv(launch.ENGINE_COMMAND_ENV, f"java -Xmx3g -jar {jar} full-game")
    decks = tuple(
        play._with_hash(
            RulesDeckInput(
                deck_id=deck_id,
                name=deck_id,
                deck_hash=None,
                commander_names=(name,),
                mainboard=("Forest",) * 99,
                sideboard=(),
            )
        )
        for deck_id, name in (
            ("own", "Chulane, Teller of Tales"),
            ("opp", "Kinnan, Bonder Prodigy"),
        )
    )
    monkeypatch.setattr(play, "load_decks", lambda _paths: decks)
    monkeypatch.setattr(play, "bridge_jar_sha256", lambda *_a, **_k: "ab" * 32)
    started: list[play.InteractiveGameSession] = []

    def fake_start(self: play.InteractiveGameSession, **_kwargs: object) -> None:
        started.append(self)

    monkeypatch.setattr(play.InteractiveGameSession, "start", fake_start)
    play.InteractivePlayManager().start_game(
        tmp_path, [Path("a.json"), Path("b.json")], seed=3, human_seats=[0], game_id="g-1591"
    )
    assert len(started) == 1
    command = started[0]._command
    assert command is not None
    assert SKIP_ON in command and "-XX:+UseSerialGC" in command
    assert command[-3:] == ("-jar", str(jar.resolve()), "full-game")
    # the human seat is still declared to the bridge, which never skips a human decision
    assert started[0].human_seats == frozenset({0})
