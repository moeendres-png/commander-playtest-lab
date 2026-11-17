"""Unit tests for #1265 S5 bounded look-ahead coordinator and board heuristic."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import pytest

from commander_lab.agents import build_pilot
from commander_lab.engine.rules.full_game import (
    ExternalPilotDecisionPolicy,
    FullGameConformanceError,
    FullGamePilotBinding,
    FullGameProtocolError,
    LookaheadConfig,
    LookaheadEvaluator,
    audit_actor_scoped_frame,
)
from commander_lab.engine.rules.full_game_pilot.common import _RuntimePilot
from commander_lab.engine.rules.full_game_pilot.lookahead import (
    board_score,
    derive_probe_seed,
)
from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength


def _actor_view(
    *,
    actor_id: str = "p1",
    own_life: int = 40,
    own_lands: int = 3,
    own_creatures: int = 1,
    opp_creatures: int = 1,
    opp_life: int = 40,
    own_won: bool = False,
    own_lost: bool = False,
    opp_lost: bool = False,
    leak_opponent_hand: bool = False,
) -> dict[str, Any]:
    own_bf: list[dict[str, Any]] = [
        {"name": "Forest", "tapped": False, "abilities": ["{T}: Add {G}."]}
        for _ in range(own_lands)
    ] + [
        {"name": "Grizzly Bears", "tapped": False, "power": 2, "toughness": 2}
        for _ in range(own_creatures)
    ]
    opp_bf: list[dict[str, Any]] = [
        {"name": "Savannah Lions", "tapped": False, "power": 2, "toughness": 1}
        for _ in range(opp_creatures)
    ]
    opp_row: dict[str, Any] = {
        "player_id": "seat-1",
        "seat": 1,
        "life": opp_life,
        "poison_counters": 0,
        "hand_count": 4,
        "library_count": 88,
        "graveyard_count": 0,
        "exile_count": 0,
        "has_lost": opp_lost,
        "has_won": False,
        "is_actor": False,
        "private_state_visible": False,
        "battlefield": opp_bf,
        "graveyard": [],
        "command": [],
        "exile": [],
        "granted_library": None,
        "library_top_revealed": None,
    }
    if leak_opponent_hand:
        opp_row["hand"] = [{"name": "Counterspell"}]
    return {
        "game_id": "probe:1",
        "actor_id": actor_id,
        "seat": 0,
        "turn_number": 4,
        "phase": "PRECOMBAT_MAIN",
        "step": "PRECOMBAT_MAIN",
        "commander_status": [{"owner_id": actor_id, "name": "Chulane, Teller of Tales"}],
        "players": [
            {
                "player_id": actor_id,
                "seat": 0,
                "life": own_life,
                "poison_counters": 0,
                "hand_count": 5,
                "library_count": 85,
                "graveyard_count": 0,
                "exile_count": 0,
                "has_lost": own_lost,
                "has_won": own_won,
                "is_actor": True,
                "private_state_visible": True,
                "hand": [],
                "battlefield": own_bf,
                "graveyard": [],
                "command": [],
                "exile": [],
                "granted_library": None,
                "library_top_revealed": None,
            },
            opp_row,
        ],
    }


@dataclass
class _FakeProbeClient:
    start_payloads: dict[str, dict[str, Any]]
    step_payloads: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    ended_probe_ids: list[str] = field(default_factory=list)

    def request(
        self, message_type: str, payload: dict[str, object] | None = None
    ) -> dict[str, Any]:
        body = dict(payload or {})
        self.calls.append((message_type, body))
        if message_type == "start_lookahead_probe":
            option_id = str(body["candidate_option_id"])
            return dict(self.start_payloads[option_id])
        if message_type == "step_lookahead_probe":
            probe_id = str(body["probe_id"])
            queue = self.step_payloads[probe_id]
            return dict(queue.pop(0))
        if message_type == "end_lookahead_probe":
            probe_id = str(body.get("probe_id") or "")
            self.ended_probe_ids.append(probe_id)
            return {"probe_id": probe_id, "ended": True, "probe_thread_alive": False}
        raise AssertionError(f"unexpected message_type: {message_type}")


class _RecordingRolloutPolicy:
    def __init__(self, decided: list[dict[str, Any]]) -> None:
        self._decided = decided

    def decide(self, request: dict[str, object]) -> dict[str, object]:
        self._decided.append(dict(request))
        return {
            "decision_id": str(request["decision_id"]),
            "actor_id": str(request["actor_id"]),
            "selected_option_ids": ["pass-1"],
            "ordering": [],
        }


def test_lookahead_config_and_seed_derivation() -> None:
    default_cfg = LookaheadConfig()
    assert default_cfg.enabled is False
    assert default_cfg.redetermine is True

    with pytest.raises(ValueError, match="max_candidates"):
        LookaheadConfig(max_candidates=1)
    with pytest.raises(ValueError, match="rollout_steps"):
        LookaheadConfig(rollout_steps=0)
    with pytest.raises(ValueError, match="min_turn"):
        LookaheadConfig(min_turn=0)
    with pytest.raises(ValueError, match="max_searches_per_game"):
        LookaheadConfig(max_searches_per_game=-1)
    with pytest.raises(ValueError, match="min_margin"):
        LookaheadConfig(min_margin=math.nan)

    s1 = derive_probe_seed(42, 10, 0)
    s2 = derive_probe_seed(42, 10, 0)
    s3 = derive_probe_seed(42, 10, 1)
    assert s1 == s2
    assert s1 != s3
    assert s1 > 0


def test_board_score_reflects_terminal_and_board_advantage() -> None:
    even = _actor_view(own_creatures=1, opp_creatures=1)
    ahead = _actor_view(own_creatures=3, opp_creatures=0, own_lands=5)
    won = _actor_view(own_won=True)
    lost = _actor_view(own_lost=True)
    opp_out = _actor_view(opp_lost=True)

    assert board_score(ahead, 0) > board_score(even, 0)
    assert board_score(won, 0) == 10_000.0
    assert board_score(opp_out, 0) == 10_000.0
    assert board_score(lost, 0) == -10_000.0


def test_lookahead_switches_candidate_when_margin_met_and_ends_probes() -> None:
    decided_in_rollout: list[dict[str, Any]] = []
    client = _FakeProbeClient(
        start_payloads={
            "opt-cast": {
                "probe_id": "probe-a",
                "probe_seed": 1,
                "redetermined": True,
                "terminal": False,
                "engine_error_count": 0,
                "failure": None,
                "decision": {
                    "decision_id": "d-step-1",
                    "actor_id": "p1",
                    "pilot_state": _actor_view(own_creatures=1),
                },
                "actor_view": _actor_view(own_creatures=1),
            },
            "opt-pass": {
                "probe_id": "probe-b",
                "probe_seed": 2,
                "redetermined": True,
                "terminal": True,
                "engine_error_count": 0,
                "failure": None,
                "decision": None,
                "actor_view": _actor_view(own_creatures=3, opp_creatures=0),
            },
        },
        step_payloads={
            "probe-a": [
                {
                    "probe_id": "probe-a",
                    "probe_seed": 1,
                    "redetermined": True,
                    "terminal": True,
                    "engine_error_count": 0,
                    "failure": None,
                    "decision": None,
                    "actor_view": _actor_view(own_creatures=1, opp_creatures=1),
                }
            ]
        },
    )
    evaluator = LookaheadEvaluator(
        client=client,
        clone_policy=lambda _seed: _RecordingRolloutPolicy(decided_in_rollout),
        game_seed=99,
        config=LookaheadConfig(enabled=True, min_margin=0.5, min_turn=2),
        frame_auditor=audit_actor_scoped_frame,
    )

    chosen = evaluator.choose_priority_option(
        _actor_view(), 15, "opt-cast", ("opt-cast", "opt-pass")
    )
    assert chosen == "opt-pass"
    assert evaluator.searches_used == 1
    assert evaluator.decisions_evaluated == 1
    assert evaluator.decisions_altered == 1
    assert len(decided_in_rollout) == 1
    assert client.ended_probe_ids == ["probe-a", "probe-b"]
    start_calls = [c[1] for c in client.calls if c[0] == "start_lookahead_probe"]
    assert len(start_calls) == 2
    assert start_calls[0]["redetermine"] is True
    assert start_calls[1]["redetermine"] is True


def test_lookahead_keeps_heuristic_below_margin_and_honors_budget() -> None:
    client = _FakeProbeClient(
        start_payloads={
            "opt-a": {
                "probe_id": "pa",
                "terminal": True,
                "engine_error_count": 0,
                "failure": None,
                "decision": None,
                "actor_view": _actor_view(own_life=40),
            },
            "opt-b": {
                "probe_id": "pb",
                "terminal": True,
                "engine_error_count": 0,
                "failure": None,
                "decision": None,
                "actor_view": _actor_view(own_life=41),  # +0.25 < min_margin 0.5
            },
        }
    )
    evaluator = LookaheadEvaluator(
        client=client,
        clone_policy=lambda _seed: _RecordingRolloutPolicy([]),
        game_seed=99,
        config=LookaheadConfig(enabled=True, min_margin=0.5, max_searches_per_game=1),
        frame_auditor=audit_actor_scoped_frame,
    )

    assert (
        evaluator.choose_priority_option(_actor_view(), 20, "opt-a", ("opt-a", "opt-b")) == "opt-a"
    )
    assert evaluator.decisions_altered == 0
    assert evaluator.searches_used == 1

    # Budget exhausted: no further probe RPCs issued.
    calls_before = len(client.calls)
    assert (
        evaluator.choose_priority_option(_actor_view(), 21, "opt-a", ("opt-a", "opt-b")) == "opt-a"
    )
    assert len(client.calls) == calls_before


def test_lookahead_penalizes_engine_error_and_fails_closed_on_leak() -> None:
    err_client = _FakeProbeClient(
        start_payloads={
            "opt-risky": {
                "probe_id": "pr",
                "terminal": True,
                "engine_error_count": 1,
                "failure": None,
                "decision": None,
                "actor_view": _actor_view(own_creatures=4),
            },
            "opt-safe": {
                "probe_id": "ps",
                "terminal": True,
                "engine_error_count": 0,
                "failure": None,
                "decision": None,
                "actor_view": _actor_view(own_creatures=1),
            },
        }
    )
    err_eval = LookaheadEvaluator(
        client=err_client,
        clone_policy=lambda _seed: _RecordingRolloutPolicy([]),
        game_seed=1,
        config=LookaheadConfig(enabled=True),
        frame_auditor=audit_actor_scoped_frame,
    )
    assert (
        err_eval.choose_priority_option(_actor_view(), 5, "opt-risky", ("opt-risky", "opt-safe"))
        == "opt-safe"
    )

    leak_client = _FakeProbeClient(
        start_payloads={
            "opt-a": {
                "probe_id": "p-leak",
                "terminal": True,
                "engine_error_count": 0,
                "failure": None,
                "decision": None,
                "actor_view": _actor_view(leak_opponent_hand=True),
            },
            "opt-b": {
                "probe_id": "p-ok",
                "terminal": True,
                "engine_error_count": 0,
                "failure": None,
                "decision": None,
                "actor_view": _actor_view(),
            },
        }
    )
    leak_eval = LookaheadEvaluator(
        client=leak_client,
        clone_policy=lambda _seed: _RecordingRolloutPolicy([]),
        game_seed=1,
        config=LookaheadConfig(enabled=True),
        frame_auditor=audit_actor_scoped_frame,
    )
    with pytest.raises(FullGameConformanceError, match=r"(ENGINE_FAILURE|scoping audit)"):
        leak_eval.choose_priority_option(_actor_view(), 5, "opt-a", ("opt-a", "opt-b"))
    # Even after §5 audit failure, active probe is closed in finally.
    assert leak_client.ended_probe_ids == ["p-leak"]

    dec_leak_client = _FakeProbeClient(
        start_payloads={
            "opt-a": {
                "probe_id": "p-dec-leak",
                "terminal": False,
                "engine_error_count": 0,
                "failure": None,
                "decision": {
                    "decision_id": "d1",
                    "actor_id": "p1",
                    "pilot_state": _actor_view(leak_opponent_hand=True),
                },
                "actor_view": _actor_view(),
            },
            "opt-b": {
                "probe_id": "p-ok",
                "terminal": True,
                "engine_error_count": 0,
                "failure": None,
                "decision": None,
                "actor_view": _actor_view(),
            },
        }
    )
    dec_leak_eval = LookaheadEvaluator(
        client=dec_leak_client,
        clone_policy=lambda _seed: _RecordingRolloutPolicy([]),
        game_seed=1,
        config=LookaheadConfig(enabled=True),
        frame_auditor=audit_actor_scoped_frame,
    )
    with pytest.raises(FullGameConformanceError, match=r"(ENGINE_FAILURE|scoping audit)"):
        dec_leak_eval.choose_priority_option(_actor_view(), 5, "opt-a", ("opt-a", "opt-b"))
    assert dec_leak_client.ended_probe_ids == ["p-dec-leak"]

    no_redet = LookaheadEvaluator(
        client=err_client,
        clone_policy=lambda _seed: _RecordingRolloutPolicy([]),
        game_seed=1,
        config=LookaheadConfig(enabled=True, redetermine=False),
        frame_auditor=audit_actor_scoped_frame,
    )
    with pytest.raises(
        FullGameProtocolError, match=r"(ENGINE_FAILURE|LOOKAHEAD_REDETERMINATION_REQUIRED)"
    ):
        no_redet.choose_priority_option(_actor_view(), 5, "opt-a", ("opt-a", "opt-b"))


def test_clone_for_rollout_isolates_policy_state() -> None:
    bindings = tuple(
        FullGamePilotBinding(
            seat=seat,
            deck_id=f"deck-{seat}",
            strategy="generic",
            commander_names=("Chulane, Teller of Tales",),
            config=PilotConfig(
                pilot_name="auto",
                strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
                mode=PilotDecisionMode.DETERMINISTIC,
            ),
            pilot_identity="GenericCommanderPilot",
            pilot_version="1.0.0",
            decision_policy_version="xmage-full-game-policy-1.0.0",
        )
        for seat in (1, 2)
    )
    runtime_pilots = tuple(
        _RuntimePilot(binding=b, pilot=build_pilot(b.config, strategy=b.strategy)) for b in bindings
    )
    real_policy = ExternalPilotDecisionPolicy(runtime_pilots, scenario_seed=77)
    real_policy.set_lookahead_chooser(lambda _s, _o, default_id, _c: default_id)

    clone = real_policy.clone_for_rollout(probe_seed=999)
    assert clone.scenario_seed == 999
    assert clone._lookahead_chooser is None

    clone._turn_actions[1] = (3, Counter({"Forest": 1}))
    clone._priority_last_fingerprint[1] = (1, 3, "MAIN", "MAIN", (), (), ())
    assert 1 not in real_policy._turn_actions
    assert 1 not in real_policy._priority_last_fingerprint


def test_runner_drive_minimal_policy_and_lookahead_lifecycle() -> None:
    from commander_lab.engine.rules.full_game import XmageFullGameRunner

    class _MinimalPolicy:
        scenario_seed = 77

        def decide(self, request: dict[str, object]) -> dict[str, object]:
            return {
                "decision_id": str(request["decision_id"]),
                "actor_id": str(request["actor_id"]),
                "selected_option_ids": ["pass-1"],
                "ordering": [],
            }

    class _ImmediateTerminalClient:
        def request(
            self, message_type: str, payload: dict[str, object] | None = None
        ) -> dict[str, object]:
            return {"terminal": True}

    runner_off = XmageFullGameRunner(command=("true",))
    decisions, _obs, terminal = runner_off._drive(
        _ImmediateTerminalClient(),  # type: ignore[arg-type]
        _MinimalPolicy(),  # type: ignore[arg-type]
        stop_after=None,
    )
    assert terminal is True
    assert decisions == 0
    assert runner_off.last_lookahead_stats is None

    bindings = tuple(
        FullGamePilotBinding(
            seat=seat,
            deck_id=f"deck-{seat}",
            strategy="generic",
            commander_names=("Chulane, Teller of Tales",),
            config=PilotConfig(
                pilot_name="auto",
                strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
                mode=PilotDecisionMode.DETERMINISTIC,
            ),
            pilot_identity="GenericCommanderPilot",
            pilot_version="1.0.0",
            decision_policy_version="xmage-full-game-policy-1.0.0",
        )
        for seat in (1, 2)
    )
    runtime_pilots = tuple(
        _RuntimePilot(binding=b, pilot=build_pilot(b.config, strategy=b.strategy)) for b in bindings
    )
    policy_on = ExternalPilotDecisionPolicy(runtime_pilots, scenario_seed=77)
    runner_on = XmageFullGameRunner(
        command=("true",),
        lookahead_config=LookaheadConfig(enabled=True),
    )
    decisions_on, _obs_on, terminal_on = runner_on._drive(
        _ImmediateTerminalClient(),  # type: ignore[arg-type]
        policy_on,
        stop_after=None,
    )
    assert terminal_on is True
    assert decisions_on == 0
    assert policy_on._lookahead_chooser is None
    assert runner_on.last_lookahead_stats == {
        "searches_used": 0,
        "decisions_evaluated": 0,
        "decisions_altered": 0,
    }
