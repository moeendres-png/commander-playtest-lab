"""WS224 name-canary negatives (Oracle B — synthetic sentinels, no JVM).

Supplements the UUID oracle: proves Lab projection/digest/transcript/error/
replay layers never emit hidden card names even when the hidden names are
unmistakable test-only sentinels. Sentinels are never real cards, never in any
deck, never pilot heuristics, never Rules inputs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from commander_lab.agents import GenericCommanderPilot
from commander_lab.engine.rules.full_game import (
    ExternalPilotDecisionPolicy,
    FullGamePilotBinding,
    XmageFullGameRunner,
    _RuntimePilot,
)
from commander_lab.models import PilotConfig, PilotDecisionMode, PilotStrength
from commander_lab.semantic_replay.divergence import DivergenceClass, ReplayDivergence
from commander_lab.semantic_replay.fingerprint import (
    canonical_actor_view,
    internal_checkpoint_digest,
    legal_set_digest,
    option_fingerprint,
    principal_observation_digest,
    public_state_digest,
)

ALPHA = "WS224_CANARY_ALPHA_SENTINEL"
BETA = "WS224_CANARY_BETA_SENTINEL"
GAMMA = "WS224_CANARY_GAMMA_SENTINEL"
DELTA = "WS224_CANARY_DELTA_SENTINEL"
SENTINELS = (ALPHA, BETA, GAMMA, DELTA)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _player(
    player_id: str,
    seat: int,
    *,
    actor: bool,
    hand_names: list[str] | None = None,
    smuggled_opponent_hand: list[str] | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "player_id": player_id,
        "seat": seat,
        "life": 40,
        "hand_count": 7,
        "library_count": 92,
        "graveyard_count": 0,
        "battlefield": [],
        "graveyard": [],
        "command": [],
        "is_actor": actor,
    }
    if actor:
        entry["hand"] = [
            {"object_id": f"card-{index}", "name": name}
            for index, name in enumerate(hand_names or ["Plains"])
        ]
        entry["mana_pool"] = {
            "white": 0,
            "blue": 0,
            "black": 0,
            "red": 0,
            "green": 0,
            "colorless": 0,
        }
        entry["command"] = [{"object_id": "cmd-1", "name": "Isamaru, Hound of Konda"}]
    if smuggled_opponent_hand is not None:
        # Simulates a buggy redactor: production must STILL drop it downstream.
        entry["hand"] = [
            {"object_id": f"smuggled-{index}", "name": name}
            for index, name in enumerate(smuggled_opponent_hand)
        ]
    return entry


def _state(player_count: int, *, smuggle: bool = False) -> dict[str, Any]:
    players = [_player("actor", 0, actor=True, hand_names=["Plains", "Savannah Lions"])]
    hidden = [BETA, GAMMA, DELTA, ALPHA]
    for seat in range(1, player_count):
        players.append(
            _player(
                f"opponent-{seat}",
                seat,
                actor=False,
                smuggled_opponent_hand=[hidden[seat - 1]] if smuggle else None,
            )
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
        "commander_status": [],
    }


def _assert_no_sentinels(value: object, surface: str) -> None:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False)
    for sentinel in SENTINELS:
        assert sentinel not in encoded, f"{surface} leaks {sentinel}"


def _binding(seat: int, deck_id: str) -> FullGamePilotBinding:
    config = PilotConfig(
        pilot_name="auto",
        strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
        mode=PilotDecisionMode.DETERMINISTIC,
    )
    return FullGamePilotBinding(
        seat=seat,
        deck_id=deck_id,
        strategy="generic",
        commander_names=("Isamaru, Hound of Konda",),
        config=config,
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-full-game-policy-1.0.0",
    )


def _policy(player_count: int) -> ExternalPilotDecisionPolicy:
    runtimes = tuple(
        _RuntimePilot(
            binding=_binding(seat, f"fixture-{seat}"),
            pilot=GenericCommanderPilot(_binding(seat, f"fixture-{seat}").config),
        )
        for seat in range(1, player_count + 1)
    )
    return ExternalPilotDecisionPolicy(runtimes, 7)


def _priority_request(player_count: int, *, smuggle: bool = False) -> dict[str, Any]:
    return {
        "decision_id": "engine-a",
        "decision_offset": 3,
        "actor_id": "actor",
        "decision_class": "priority",
        "pilot_state": _state(player_count, smuggle=smuggle),
        "context": {},
        "minimum_selections": 1,
        "maximum_selections": 1,
        "legal_options": [
            {"option_id": "pass", "label": "Pass", "option_type": "pass_priority"},
        ],
    }


@pytest.mark.parametrize("player_count", [2, 3, 4, 5])
def test_canonical_view_and_digests_carry_no_hidden_sentinels(player_count: int) -> None:
    state = _state(player_count)
    view = canonical_actor_view(state)
    _assert_no_sentinels(view, "canonical_actor_view")
    # Actor-public names MUST survive (no global scrub).
    encoded = json.dumps(view, ensure_ascii=False)
    assert "Plains" in encoded
    assert "Isamaru, Hound of Konda" in encoded
    legal = [{"label": "Pass", "metadata": {}, "option_id": "pass", "option_type": "pass_priority"}]
    _assert_no_sentinels(principal_observation_digest(state), "observation digest")
    _assert_no_sentinels(public_state_digest(state), "public digest")
    _assert_no_sentinels(legal_set_digest(legal, state), "legal-set digest")
    _assert_no_sentinels(
        internal_checkpoint_digest(
            pilot_state=state,
            legal_options=legal,
            rules_seed=7,
            rules_random_calls=10,
            turn_number=1,
            decision_offset=3,
        ),
        "checkpoint digest",
    )


@pytest.mark.parametrize("player_count", [2, 3, 4, 5])
def test_canonical_view_drops_smuggled_opponent_hand(player_count: int) -> None:
    state = _state(player_count, smuggle=True)
    view = canonical_actor_view(state)
    _assert_no_sentinels(view, "canonical_actor_view (smuggled)")
    _assert_no_sentinels(principal_observation_digest(state), "observation digest (smuggled)")
    _assert_no_sentinels(public_state_digest(state), "public digest (smuggled)")


@pytest.mark.parametrize("player_count", [2, 3, 4, 5])
def test_policy_input_exposes_no_opponent_names(player_count: int) -> None:
    policy = _policy(player_count)
    runtime = policy._pilots[1]
    view = policy._pilot_state(runtime, _state(player_count, smuggle=True))
    dumped = view.model_dump_json()
    _assert_no_sentinels(json.loads(dumped), "PilotStateView")
    # Actor's own public names remain visible to the actor's pilot.
    assert "Plains" in dumped
    assert "Savannah Lions" in dumped
    assert len(view.opponents) == player_count - 1


@pytest.mark.parametrize("player_count", [2, 3, 4, 5])
def test_policy_decide_path_carries_no_hidden_sentinels(player_count: int) -> None:
    policy = _policy(player_count)
    response = policy.decide(_priority_request(player_count, smuggle=True))
    assert response["selected_option_ids"] == ["pass"]
    _assert_no_sentinels(response, "policy response")


def test_option_fingerprint_generic_fallback_excludes_uuid_like_name_keys() -> None:
    state = _state(2)
    option = {
        "label": "Choose",
        "metadata": {
            "object_id": "11111111-2222-3333-4444-555555555555",
            "source_object_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "name": ALPHA,
            "note": "public-note",
        },
        "option_id": "opt-1",
        "option_type": "weird_future_type",
    }
    printed = option_fingerprint(option, state)
    assert isinstance(printed, str) and len(printed) == 64
    # Hashes never carry raw names; the join rule is covered structurally.
    _assert_no_sentinels(printed, "option fingerprint")


def test_semantic_transcript_carries_no_hidden_sentinels() -> None:
    result = {
        "seed": 7,
        "turn_number": 2,
        "decision_count": 2,
        "transcript": [
            {
                "sequence": 1,
                "kind": "decision_requested",
                "decision_class": "priority",
                "actor_seat": 0,
                "prompt": "Pass priority?",
                "selected_option_types": ["pass_priority"],
                "selected_option_labels": ["Pass"],
                "numeric_choice": None,
            },
            {
                "sequence": 2,
                "kind": "decision_accepted",
                "decision_class": "mulligan",
                "actor_seat": 1,
                "prompt": "Keep?",
                "selected_option_types": ["keep"],
                "selected_option_labels": ["Keep opening hand"],
                "numeric_choice": None,
            },
        ],
        "outcomes": [
            {"seat": 0, "life": 40, "won": True, "lost": False, "left": False},
            {"seat": 1, "life": 40, "won": False, "lost": True, "left": False},
        ],
    }
    semantic = XmageFullGameRunner.semantic_transcript(result)
    _assert_no_sentinels(semantic, "semantic_transcript")
    # Detector check: a planted sentinel IS found (scanner is not blind).
    planted = json.loads(json.dumps(semantic))
    planted["events"][0]["prompt"] = f"Choose {ALPHA} now"
    with pytest.raises(AssertionError):
        _assert_no_sentinels(planted, "planted transcript")


def test_all_divergence_diagnostics_carry_no_hidden_names() -> None:
    details = {
        DivergenceClass.SOURCE_LOCK_MISMATCH: "recorded engine d*40 vs live e*40",
        DivergenceClass.DOMAIN_LOCK_MISMATCH: "player count 4 vs 3",
        DivergenceClass.INITIAL_STATE_MISMATCH: "initial digest differs (calls=196)",
        DivergenceClass.ACTOR_MISMATCH: "step 3: recorded seat 2 native seat 1",
        DivergenceClass.DECISION_CLASS_MISMATCH: "step 3: recorded=priority native=target",
        DivergenceClass.DECISION_REVISION_MISMATCH: "step 3: recorded rev 9 native rev 10",
        DivergenceClass.OBSERVATION_MISMATCH: "step 3: observation differs",
        DivergenceClass.LEGAL_SET_MISMATCH: "step 3: legal set differs (native=4 recorded=3)",
        DivergenceClass.CHOSEN_OPTION_MISSING: "step 3: recorded choice absent natively",
        DivergenceClass.CHOSEN_OPTION_AMBIGUOUS: "step 3: recorded choice matches 2 native options",
        DivergenceClass.RULES_RNG_CALL_DRIFT: "step 3: RNG calls before differ",
        DivergenceClass.RULES_RNG_RESULT_DRIFT: "replay seed mismatch",
        DivergenceClass.EVENT_DIGEST_MISMATCH: "step 3: event digest does not recompute",
        DivergenceClass.STATE_DIGEST_MISMATCH: "step 3: post-state differs",
        DivergenceClass.EARLY_TERMINATION: "game ended before replay step 3",
        DivergenceClass.EXTRA_DECISION: "replay consumed all steps but the game offers another decision",
        DivergenceClass.TERMINAL_OUTCOME_MISMATCH: "terminal outcomes differ",
        DivergenceClass.MALFORMED_TAPE: "schema invalid: steps must be densely ordered",
    }
    assert set(details) == set(DivergenceClass)
    for klass, detail in details.items():
        exc = ReplayDivergence(klass, detail)
        _assert_no_sentinels(str(exc), f"divergence {klass.value}")
        assert klass.value in str(exc)


def test_conformance_error_texts_carry_no_hidden_names() -> None:
    policy = _policy(4)
    bad_class = dict(_priority_request(4))
    bad_class["decision_class"] = "future_hidden_class"
    with pytest.raises(Exception) as caught:
        policy.decide(bad_class)
    _assert_no_sentinels(str(caught.value), "unhandled-class error")
    bad_state = _priority_request(4)
    bad_state["pilot_state"] = {"actor_id": "actor"}
    with pytest.raises(Exception) as caught2:
        policy.decide(bad_state)
    _assert_no_sentinels(str(caught2.value), "malformed-state error")


def test_sealed_ws218_tapes_have_no_pilot_visible_hidden_arrays() -> None:
    tapes_dir = REPO_ROOT / "qualification/ws218-semantic-replay-tape-v1/tapes"
    tapes = sorted(tapes_dir.glob("ws218-tape-*.json"))
    assert len(tapes) == 4, f"expected sealed 2P-5P tapes, found {tapes}"
    for tape_path in tapes:
        tape = json.loads(tape_path.read_text(encoding="utf-8"))
        steps = tape.get("steps", [])
        assert steps, f"{tape_path.name} has no steps"
        encoded_steps = json.dumps(steps)
        # Pilot-facing steps never carry hand/mana/granted arrays (privileged
        # decklists live ONLY in game_manifest, classified EXPECTED_PRIVILEGED).
        assert '"hand"' not in encoded_steps, tape_path.name
        assert '"mana_pool"' not in encoded_steps, tape_path.name
        assert '"granted_library"' not in encoded_steps, tape_path.name
        _assert_no_sentinels(steps, f"tape steps {tape_path.name}")
        manifest = tape.get("game_manifest", {})
        assert 2 <= int(manifest.get("player_count", 0)) <= 5
