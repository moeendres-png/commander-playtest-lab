"""WS223 cardinality regression battery (no JVM required).

Proves the representative regressions named in the WS223 contract fail the
gate instead of merging green:

* ``MIN_PLAYERS``/``MAX_PLAYERS`` reverting to 4-only;
* a reintroduced exactly-four guard (legacy ``operational_pod_size`` lane);
* invalid seat ranges (0 / 6);
* lost 5P seat/seed mapping in the create payload;
* 6P accidentally accepted (script table, scenario model, runner
  validation, pilot policy);
* bounded-smoke integrity (early stop, observed classes, seed drift,
  engine failure, unsupported callback, zero-decision terminal).

Plus structural gates on the merge-relevant CI lane itself (cardinalities
covered, fail-closed step present, variable-player triggers present,
replay-only paths excluded from the JVM lane, hashseed/caches pinned).
"""

from __future__ import annotations

import contextlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from commander_lab.candidates.models import FutureXmageScenario
from commander_lab.engine.rules.full_game import (
    FULL_GAME_EVIDENCE_CLASS,
    FULL_GAME_LANE,
    FullGameConformanceError,
    FullGamePilotBinding,
    FullGameProtocolError,
    XmageFullGameRunner,
)
from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength, RulesDeckInput

XMAGE_COMMIT = "db134b9737e951367d65ef5806ad986319cc73ab"
WORKFLOW_REL = ".github/workflows/xmage-full-game-conformance.yml"


def _load_conformance_script() -> Any:
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "ws223_conformance", root / "scripts/run_external_full_game_conformance.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _binding(seat: int, deck_id: str) -> FullGamePilotBinding:
    return FullGamePilotBinding(
        seat=seat,
        deck_id=deck_id,
        strategy="generic",
        commander_names=("Isamaru, Hound of Konda",),
        config=PilotConfig(
            pilot_name="auto",
            strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
            mode=PilotDecisionMode.DETERMINISTIC,
        ),
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-full-game-policy-1.0.0",
    )


def _deck(seat: int) -> RulesDeckInput:
    return RulesDeckInput(
        deck_id=f"fixture-{seat}",
        name=f"Full-game fixture {seat}",
        commander_names=("Isamaru, Hound of Konda",),
        mainboard=tuple("Plains" for _ in range(99)),
        deck_hash=(f"{seat:x}" * 64)[:64],
    )


def _scenario(player_count: int, seed: int = 17) -> FutureXmageScenario:
    decks = [_deck(index) for index in range(1, player_count + 1)]
    assert decks[0].deck_hash is not None
    return FutureXmageScenario(
        candidate_id=decks[0].deck_id,
        deck_hash=decks[0].deck_hash,  # type: ignore[arg-type]
        opponent_deck_ids=tuple(deck.deck_id for deck in decks[1:]),
        player_count=player_count,  # type: ignore[arg-type]
        seat=1,
        scenario_id="ws223-regression",
        seed=seed,
        xmage_commit=XMAGE_COMMIT,
        bridge_version="xmage-engine-bridge-0.1.0-SNAPSHOT",
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-full-game-policy-1.0.0",
    )


def _actor_state(player_count: int) -> dict[str, Any]:
    players: list[dict[str, Any]] = [
        {
            "player_id": "actor",
            "seat": 0,
            "life": 40,
            "hand_count": 7,
            "library_count": 92,
            "graveyard_count": 0,
            "battlefield": [],
            "graveyard": [],
            "command": [{"object_id": "commander", "name": "Isamaru, Hound of Konda"}],
            "hand": [{"object_id": f"card-{index}", "name": "Plains"} for index in range(7)],
            "mana_pool": {
                "white": 0,
                "blue": 0,
                "black": 0,
                "red": 0,
                "green": 0,
                "colorless": 0,
            },
        }
    ]
    for seat in range(1, player_count):
        players.append(
            {
                "player_id": f"opponent-{seat}",
                "seat": seat,
                "life": 40,
                "hand_count": 7,
                "library_count": 92,
                "graveyard_count": 0,
                "battlefield": [],
                "graveyard": [],
                "command": [],
            }
        )
    return {
        "game_id": "opaque-engine-game",
        "actor_id": "actor",
        "seat": 0,
        "turn_number": 1,
        "active_player_id": "actor",
        "priority_player_id": "actor",
        "phase": "precombat_main",
        "step": None,
        "players": players,
        "stack": [],
    }


def _priority_pass_request(player_count: int, offset: int = 3) -> dict[str, Any]:
    return {
        "decision_id": f"engine-{offset}",
        "decision_offset": offset,
        "actor_id": "actor",
        "decision_class": "priority",
        "pilot_state": _actor_state(player_count),
        "context": {},
        "minimum_selections": 1,
        "maximum_selections": 1,
        "legal_options": [
            {"option_id": "pass", "label": "Pass", "option_type": "pass_priority"},
        ],
    }


def _handshake_lane(min_players: int = 2, max_players: int = 6) -> dict[str, Any]:
    return {
        "full_game_lane": {
            "lane": FULL_GAME_LANE,
            "decision_protocol_version": "xmage-external-decision-protocol-1.0.0",
            "min_players": min_players,
            "max_players": max_players,
            "evidence_class": FULL_GAME_EVIDENCE_CLASS,
            "generic_capability_promotion": False,
            "one_game_per_process": True,
            "bit_exact_replay_validated": False,
        },
        "capabilities": {
            "commander_supported": True,
            "partner_supported": True,
            "multiplayer_supported": True,
            "headless_supported": True,
            "seed_supported": True,
            "deck_import_supported": True,
            "target_selection_supported": True,
            "mode_selection_supported": True,
            "trigger_order_supported": True,
            "mulligan_supported": True,
        },
    }


class _ScriptedBridge:
    """In-memory stand-in for ``_RawFullGameClient`` (protocol shapes only).

    Answers the exact request sequence ``run``/``run_smoke`` emit. Pilot
    legality stays with the real ``ExternalPilotDecisionPolicy``; only
    transport is scripted.
    """

    def __init__(
        self,
        player_count: int,
        decisions: list[dict[str, Any]],
        *,
        seed_drift: bool = False,
        fail_engine: bool = False,
    ) -> None:
        self.player_count = player_count
        self.decisions = list(decisions)
        self.seed_drift = seed_drift
        self.fail_engine = fail_engine
        self.requests: list[tuple[str, dict[str, Any]]] = []
        self.closed = False

    def request(self, message_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        body = dict(payload or {})
        self.requests.append((message_type, body))
        if message_type == "start_engine":
            return {"lane": FULL_GAME_LANE}
        if message_type == "get_provider_version":
            return {
                "engine": "xmage",
                "engine_commit": XMAGE_COMMIT,
                "engine_version": "1.4.61",
            }
        if message_type == "get_capabilities":
            return _handshake_lane()
        if message_type == "import_deck":
            return {"deck_handle": {"handle_id": f"handle-{len(self.requests)}"}}
        if message_type == "create_full_game":
            seed = body.get("seed", 0)
            return {
                "player_count": len(body.get("deck_handles", [])),
                "seed": seed + 1 if self.seed_drift else seed,
                "evidence_class": FULL_GAME_EVIDENCE_CLASS,
                "holdout_consumed": False,
            }
        if message_type in (
            "start_full_game",
            "submit_full_game_decision",
            "get_full_game_decision",
        ):
            if self.fail_engine:
                return {"failure": {"code": "scripted", "message": "boom"}}
            if self.decisions:
                return {"decision": self.decisions.pop(0)}
            return {"terminal": True}
        if message_type == "get_full_game_result":
            raise AssertionError("result payload is supplied by the test spy, not the bridge")
        if message_type == "shutdown_engine":
            return {}
        raise AssertionError(f"unexpected bridge request {message_type!r}")

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self.request("shutdown_engine")
        self.closed = True

    def __enter__(self) -> _ScriptedBridge:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def _runner_with_bridge(
    monkeypatch: pytest.MonkeyPatch, bridge: _ScriptedBridge
) -> XmageFullGameRunner:
    import commander_lab.engine.rules.full_game as full_game_module

    monkeypatch.setattr(full_game_module, "_RawFullGameClient", lambda *a, **k: bridge)
    return XmageFullGameRunner(command=("java", "-jar", "bridge.jar", "full-game"))


# --- Constant guards: MIN/MAX revert to 4-only must fail --------------------


def test_supported_cardinality_constants_cover_two_to_six() -> None:
    assert XmageFullGameRunner.MIN_PLAYERS == 2
    assert XmageFullGameRunner.MAX_PLAYERS == 6


def test_conformance_script_covers_two_to_six_plus_fail_closed_seven() -> None:
    module = _load_conformance_script()
    assert module.SUPPORTED_PLAYER_COUNTS == (2, 3, 4, 5, 6)
    assert module.FULL_GATE_PLAYER_COUNT == 4
    assert set(module.SMOKE_PLAYER_COUNTS) == {2, 3, 5, 6}
    assert set(module.CARDINALITY_SEEDS) == {2, 3, 4, 5, 6}
    assert len(set(module.CARDINALITY_SEEDS.values())) == 5


def test_smoke_decision_targets_are_calibrated_not_lowered() -> None:
    """Live calibration 2026-09-15: 5P@25 misses priority; 5P needs 45.
    R19 calibration 2026-09-21: 6P needs 55 (live bounded-smoke PASS)."""
    module = _load_conformance_script()
    assert module.SMOKE_DECISION_TARGETS == {2: 25, 3: 25, 5: 45, 6: 55}
    assert set(module.SMOKE_REQUIRED_DECISION_CLASSES) == {"mulligan", "priority"}


@pytest.mark.parametrize("player_count", [2, 3, 4, 5, 6])
def test_conformance_setup_builds_exact_coverage(player_count: int) -> None:
    module = _load_conformance_script()
    scenario, decks, pilots = module.build_setup(player_count)
    assert scenario.player_count == player_count
    assert len(decks) == player_count and len(pilots) == player_count
    assert {pilot.seat for pilot in pilots} == set(range(1, player_count + 1))
    assert len({deck.deck_id for deck in decks}) == player_count
    assert scenario.seed == module.CARDINALITY_SEEDS[player_count]


@pytest.mark.parametrize("player_count", [0, 1, 7])
def test_conformance_setup_rejects_unsupported_cardinality(player_count: int) -> None:
    module = _load_conformance_script()
    with pytest.raises((ValueError, ValidationError)):
        module.build_setup(player_count)


def test_fail_closed_probe_never_launches_engine(tmp_path: Path) -> None:
    module = _load_conformance_script()
    summary = module.prove_fail_closed(7, out_dir=tmp_path)
    assert summary["status"] == "FAIL_CLOSED"
    assert summary["engine_launched"] is False
    payload = json.loads((tmp_path / "XMAGE_FULL_GAME_FAIL_CLOSED_7P.json").read_text())
    assert payload["status"] == "FAIL_CLOSED"


# --- Layered 6P rejection ----------------------------------------------------


def test_scenario_model_rejects_seven_players() -> None:
    with pytest.raises(ValidationError):
        FutureXmageScenario(
            candidate_id="fixture-1",
            deck_hash="a" * 64,
            opponent_deck_ids=tuple(f"fixture-{seat}" for seat in range(2, 8)),
            player_count=7,
            seat=1,
            scenario_id="ws223-seven",
            seed=1,
            xmage_commit=XMAGE_COMMIT,
            bridge_version="xmage-engine-bridge-0.1.0-SNAPSHOT",
            pilot_identity="GenericCommanderPilot",
            pilot_version="1.0.0",
            decision_policy_version="xmage-full-game-policy-1.0.0",
        )


def test_runner_validation_rejects_smuggled_seven_player_scenario() -> None:
    scenario = _scenario(6).model_copy(update={"player_count": 7})
    decks = tuple(_deck(seat) for seat in range(1, 7))
    pilots = tuple(_binding(seat, f"fixture-{seat}") for seat in range(1, 7))
    with pytest.raises(FullGameConformanceError):
        XmageFullGameRunner._validate_inputs(scenario, decks, pilots)


def test_binding_rejects_seat_zero_and_seat_seven() -> None:
    with pytest.raises(ValidationError):
        _binding(0, "fixture-0")
    with pytest.raises(ValidationError):
        _binding(7, "fixture-7")


def test_legacy_four_only_lane_still_rejected() -> None:
    scenario = _scenario(4)
    provider = {"engine": "xmage", "engine_commit": XMAGE_COMMIT}
    lane = _handshake_lane()
    lane["full_game_lane"] = {
        "lane": FULL_GAME_LANE,
        "decision_protocol_version": "xmage-external-decision-protocol-1.0.0",
        "operational_pod_size": 4,
        "evidence_class": FULL_GAME_EVIDENCE_CLASS,
        "generic_capability_promotion": False,
        "one_game_per_process": True,
        "bit_exact_replay_validated": False,
    }
    with pytest.raises(FullGameConformanceError):
        XmageFullGameRunner._validate_handshake(scenario, provider, lane)


# --- 5P mapping via the shared open-game path --------------------------------


def test_five_player_create_payload_preserves_seat_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player_count = 5
    seed = 20260827
    bridge = _ScriptedBridge(
        player_count, [_priority_pass_request(player_count, offset + 1) for offset in range(6)]
    )
    runner = _runner_with_bridge(monkeypatch, bridge)
    scenario = _scenario(player_count, seed=seed)
    decks = tuple(_deck(seat) for seat in range(1, player_count + 1))
    pilots = tuple(_binding(seat, f"fixture-{seat}") for seat in range(1, player_count + 1))
    smoke = runner.run_smoke(scenario=scenario, decks=decks, pilots=pilots, smoke_decision_target=5)
    create = next(body for kind, body in bridge.requests if kind == "create_full_game")
    assert len(create["deck_handles"]) == player_count
    assert create["seed"] == seed
    assert create["starting_player_seat"] == seed % player_count
    assert create["starting_life"] == 40
    assert smoke.player_count == player_count
    assert smoke.seed_preserved is True
    assert smoke.player_count_preserved is True
    assert bridge.closed is True


# --- Bounded-smoke integrity --------------------------------------------------


def test_smoke_stops_at_target_with_observed_classes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player_count = 3
    bridge = _ScriptedBridge(
        player_count, [_priority_pass_request(player_count, offset + 1) for offset in range(30)]
    )
    runner = _runner_with_bridge(monkeypatch, bridge)
    scenario = _scenario(player_count)
    decks = tuple(_deck(seat) for seat in range(1, player_count + 1))
    pilots = tuple(_binding(seat, f"fixture-{seat}") for seat in range(1, player_count + 1))
    smoke = runner.run_smoke(scenario=scenario, decks=decks, pilots=pilots, smoke_decision_target=5)
    assert smoke.decision_count == 5
    assert smoke.terminal_reached is False
    assert smoke.bounded_criterion_met is True
    assert list(smoke.observed_decision_classes) == ["priority"]
    assert smoke.unsupported_callback_seen is False
    assert smoke.clean_shutdown is True
    submits = [body for kind, body in bridge.requests if kind == "submit_full_game_decision"]
    assert len(submits) == 5


def test_smoke_seed_drift_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    player_count = 2
    bridge = _ScriptedBridge(
        player_count,
        [_priority_pass_request(player_count)],
        seed_drift=True,
    )
    runner = _runner_with_bridge(monkeypatch, bridge)
    scenario = _scenario(player_count)
    decks = tuple(_deck(seat) for seat in range(1, player_count + 1))
    pilots = tuple(_binding(seat, f"fixture-{seat}") for seat in range(1, player_count + 1))
    with pytest.raises(FullGameConformanceError, match="player-count/seed contract"):
        runner.run_smoke(scenario=scenario, decks=decks, pilots=pilots)


def test_smoke_engine_failure_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    player_count = 2
    bridge = _ScriptedBridge(player_count, [], fail_engine=True)
    runner = _runner_with_bridge(monkeypatch, bridge)
    scenario = _scenario(player_count)
    decks = tuple(_deck(seat) for seat in range(1, player_count + 1))
    pilots = tuple(_binding(seat, f"fixture-{seat}") for seat in range(1, player_count + 1))
    with pytest.raises(FullGameConformanceError, match="engine failed"):
        runner.run_smoke(scenario=scenario, decks=decks, pilots=pilots)


def test_smoke_unsupported_decision_class_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player_count = 2
    bad = _priority_pass_request(player_count)
    bad["decision_class"] = "unmapped_future_choice"
    bridge = _ScriptedBridge(player_count, [bad])
    runner = _runner_with_bridge(monkeypatch, bridge)
    scenario = _scenario(player_count)
    decks = tuple(_deck(seat) for seat in range(1, player_count + 1))
    pilots = tuple(_binding(seat, f"fixture-{seat}") for seat in range(1, player_count + 1))
    with pytest.raises(FullGameProtocolError, match="unsupported discretionary decision class"):
        runner.run_smoke(scenario=scenario, decks=decks, pilots=pilots)


def test_smoke_zero_decision_terminal_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    player_count = 2
    bridge = _ScriptedBridge(player_count, [])
    runner = _runner_with_bridge(monkeypatch, bridge)
    scenario = _scenario(player_count)
    decks = tuple(_deck(seat) for seat in range(1, player_count + 1))
    pilots = tuple(_binding(seat, f"fixture-{seat}") for seat in range(1, player_count + 1))
    with pytest.raises(FullGameConformanceError, match="no authoritative decisions"):
        runner.run_smoke(scenario=scenario, decks=decks, pilots=pilots)


def test_smoke_rejects_missing_bridge_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD", raising=False)
    runner = XmageFullGameRunner(command=None)
    scenario = _scenario(2)
    decks = tuple(_deck(seat) for seat in range(1, 3))
    pilots = tuple(_binding(seat, f"fixture-{seat}") for seat in range(1, 3))
    with pytest.raises(FullGameConformanceError, match="not configured"):
        runner.run_smoke(scenario=scenario, decks=decks, pilots=pilots)


def test_smoke_rejects_non_positive_target() -> None:
    runner = XmageFullGameRunner(command=("java", "-jar", "bridge.jar", "full-game"))
    scenario = _scenario(2)
    decks = tuple(_deck(seat) for seat in range(1, 3))
    pilots = tuple(_binding(seat, f"fixture-{seat}") for seat in range(1, 3))
    with pytest.raises(ValueError, match="smoke_decision_target"):
        runner.run_smoke(scenario=scenario, decks=decks, pilots=pilots, smoke_decision_target=0)


def test_shared_drive_still_reaches_terminal_for_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The `_drive` refactor must preserve `run()`'s terminal path exactly."""

    import commander_lab.engine.rules.full_game as full_game_module

    player_count = 3
    seed = 17
    bridge = _ScriptedBridge(
        player_count, [_priority_pass_request(player_count, offset + 1) for offset in range(4)]
    )
    monkeypatch.setattr(full_game_module, "_RawFullGameClient", lambda *a, **k: bridge)

    result_payload = {
        "evidence_class": FULL_GAME_EVIDENCE_CLASS,
        "consumed_gameplay_evidence": False,
        "holdout_consumed": False,
        "official_campaign_eligible": False,
        "rules_authority": "xmage",
        "decision_policy_authority": "commander_lab_external_pilot",
        "bit_exact_replay_validated": False,
        "seed": seed,
        "terminal": True,
        "decision_count": 4,
        "outcomes": [
            {"seat": index, "won": index == 0, "lost": index != 0, "left": False}
            for index in range(player_count)
        ],
        "transcript": [],
    }

    calls: list[str] = []
    original_request = bridge.request

    def spy_request(message_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        calls.append(message_type)
        if message_type == "get_full_game_result":
            return dict(result_payload)
        return original_request(message_type, payload)

    bridge.request = spy_request  # type: ignore[method-assign]
    runner = XmageFullGameRunner(command=("java", "-jar", "bridge.jar", "full-game"))
    scenario = _scenario(player_count, seed=seed)
    decks = tuple(_deck(seat) for seat in range(1, player_count + 1))
    pilots = tuple(_binding(seat, f"fixture-{seat}") for seat in range(1, player_count + 1))
    result = runner.run(scenario=scenario, decks=decks, pilots=pilots)
    assert result.terminal is True
    assert result.decision_count == 4
    assert result.winner_seats == (1,)
    assert "get_full_game_result" in calls


# --- CI lane structure --------------------------------------------------------


def _workflow(repo_root: Path) -> dict[str, Any]:
    text = (repo_root / WORKFLOW_REL).read_text(encoding="utf-8")
    return yaml.safe_load(text)


def test_cardinality_lane_covers_two_to_five(repo_root: Path) -> None:
    """The lane must invoke live execution per count, not merely name numbers."""
    text = (repo_root / WORKFLOW_REL).read_text(encoding="utf-8")
    for count in ("2", "3", "5"):
        assert f"--player-count {count}" in text, (
            f"cardinality lane must run live smoke for {count}P, not just mention {count}"
        )
    assert "run_external_full_game_conformance.py" in text


def test_cardinality_lane_has_fail_closed_step(repo_root: Path) -> None:
    text = (repo_root / WORKFLOW_REL).read_text(encoding="utf-8")
    assert "--expect-fail-closed" in text
    assert "--player-count 6" in text or "--player-count=6" in text


def test_cardinality_lane_uses_bounded_smoke(repo_root: Path) -> None:
    text = (repo_root / WORKFLOW_REL).read_text(encoding="utf-8")
    assert "--smoke-decisions" in text
    assert "--player-count 2 --smoke-decisions 25" in text
    assert "--player-count 3 --smoke-decisions 25" in text
    assert "--player-count 5 --smoke-decisions 45" in text


def test_cardinality_lane_triggers_variable_player_surfaces(repo_root: Path) -> None:
    workflow = _workflow(repo_root)
    triggers = workflow[True] if True in workflow else workflow.get("on", {})
    watched: set[str] = set()
    for event in ("pull_request", "push"):
        paths = (triggers.get(event) or {}).get("paths") or []
        watched.update(paths)
    required = {
        "src/commander_lab/engine/rules/full_game.py",
        "src/commander_lab/engine/rules/full_game_batch.py",
        "src/commander_lab/agents/**",
        "src/commander_lab/models/pilots.py",
        "src/commander_lab/candidates/models.py",
        "tests/unit/test_xmage_full_game.py",
        "tests/unit/test_xmage_variable_player.py",
        "scripts/run_external_full_game_conformance.py",
        "engine-bridge/**",
    }
    missing = sorted(name for name in required if name not in watched)
    assert not missing, f"cardinality lane trigger gap: {missing}"


def test_cardinality_lane_push_and_pr_filters_match(repo_root: Path) -> None:
    workflow = _workflow(repo_root)
    triggers = workflow[True] if True in workflow else workflow.get("on", {})
    pr_paths = set((triggers.get("pull_request") or {}).get("paths") or [])
    push_paths = set((triggers.get("push") or {}).get("paths") or [])
    production = {
        "engine-bridge/**",
        "src/commander_lab/engine/rules/full_game.py",
        "src/commander_lab/engine/rules/full_game_batch.py",
        "src/commander_lab/agents/**",
        "src/commander_lab/models/pilots.py",
        "src/commander_lab/candidates/models.py",
        "scripts/run_external_full_game_conformance.py",
    }
    assert production <= pr_paths, f"PR filter gap: {sorted(production - pr_paths)}"
    assert production <= push_paths, f"push filter gap: {sorted(production - push_paths)}"


def test_replay_only_paths_stay_off_the_jvm_lane(repo_root: Path) -> None:
    """WS218 trigger adjudication: replay-only changes ride the light lane."""
    text = (repo_root / WORKFLOW_REL).read_text(encoding="utf-8")
    trigger_lines = [line for line in text.splitlines() if line.strip().startswith("- ")]
    assert not any("semantic_replay" in line for line in trigger_lines), (
        "replay-only path triggers would silently multiply JVM cost"
    )
    assert not any("test_semantic_replay_tape" in line for line in trigger_lines)


def test_cardinality_lane_pins_hashseed_and_lock_cache(repo_root: Path) -> None:
    text = (repo_root / WORKFLOW_REL).read_text(encoding="utf-8")
    assert 'PYTHONHASHSEED: "0"' in text
    assert "requirements/lock.txt" in text
