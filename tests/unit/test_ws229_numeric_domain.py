"""WS229 numeric decision boundary: Lab descriptor/joint/F-RULES-03 evidence.

Covers the S6 positive shapes (P-A1/P-A2/P-M1/P-T1/P-B1/P-N1 unit halves),
Lab-side negatives (N-10/N-14/N-15/N-16/N-23 families), and the five
F-RULES-03 dispositions. Bridge-shaped frames mirror bytes actually emitted
by XmageFullGamePlayer in XmageNumericDomainWs229Test (zero options,
verbatim bounds, joint legs+totals); native/bridge acceptance of those
frames is proven JVM-side, pilot strategy + Lab validation here.
"""

from __future__ import annotations

import random
import time
from typing import Any

import pytest

from commander_lab.agents import GenericCommanderPilot
from commander_lab.agents.pilots import BasePilot
from commander_lab.engine.rules.full_game import (
    ExternalPilotDecisionPolicy,
    FullGamePilotBinding,
    FullGameProtocolError,
    _RuntimePilot,
)
from commander_lab.models import (
    PilotConfig,
    PilotDecision,
    PilotDecisionMode,
    PilotStateView,
    PilotStrength,
)
from commander_lab.semantic_replay.divergence import DivergenceClass, ReplayDivergence
from commander_lab.semantic_replay.recorder import _joint_numeric_of
from commander_lab.semantic_replay.tape import TapeReplayStep
from commander_lab.semantic_replay.tape_helpers import event_digest_for_step


def _policy(
    mode: PilotDecisionMode = PilotDecisionMode.DETERMINISTIC,
) -> ExternalPilotDecisionPolicy:
    runtimes: list[_RuntimePilot] = []
    for seat in range(1, 5):
        config = PilotConfig(
            pilot_name="auto",
            strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
            mode=mode,
        )
        binding = FullGamePilotBinding(
            seat=seat,
            deck_id=f"fixture-{seat}",
            strategy="generic",
            commander_names=("Isamaru, Hound of Konda",),
            config=config,
            pilot_identity="GenericCommanderPilot",
            pilot_version="1.0.0",
            decision_policy_version="xmage-full-game-policy-1.0.0",
        )
        runtimes.append(_RuntimePilot(binding=binding, pilot=GenericCommanderPilot(config)))
    return ExternalPilotDecisionPolicy(tuple(runtimes), 20260915)  # type: ignore[arg-type]


def _state() -> dict[str, Any]:
    actor = {
        "player_id": "actor",
        "seat": 0,
        "life": 40,
        "hand_count": 7,
        "library_count": 92,
        "graveyard_count": 0,
        "battlefield": [],
        "graveyard": [],
        "command": [{"object_id": "commander", "name": "Isamaru, Hound of Konda"}],
        "hand": [{"object_id": f"hand-{index}", "name": "Plains"} for index in range(7)],
        "mana_pool": {"white": 1, "blue": 0, "black": 0, "red": 0, "green": 0, "colorless": 0},
    }
    opponents = [
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
        for seat in range(1, 4)
    ]
    return {
        "game_id": "engine-opaque",
        "actor_id": "actor",
        "seat": 0,
        "turn_number": 1,
        "active_player_id": "actor",
        "priority_player_id": "actor",
        "phase": "precombat_main",
        "step": None,
        "players": [actor, *opponents],
        "stack": [],
    }


def _request(
    decision_class: str,
    options: list[dict[str, Any]],
    *,
    minimum: int,
    maximum: int,
    context: dict[str, Any] | None = None,
    offset: int = 1,
    prompt: str = "",
) -> dict[str, Any]:
    return {
        "decision_id": f"opaque-{decision_class}",
        "decision_offset": offset,
        "actor_id": "actor",
        "decision_class": decision_class,
        "pilot_state": _state(),
        "context": context or {},
        "minimum_selections": minimum,
        "maximum_selections": maximum,
        "legal_options": options,
        "prompt": prompt or decision_class,
    }


def _option(option_id: str, option_type: str, label: str, **metadata: Any) -> dict[str, Any]:
    return {
        "option_id": option_id,
        "option_type": option_type,
        "label": label,
        "metadata": metadata,
    }


# --- BasePilot fail-closed contract -------------------------------------------


def test_base_pilot_choose_number_raises() -> None:
    pilot = BasePilot()
    with pytest.raises(NotImplementedError):
        pilot.choose_number(None, {"min": 0, "max": 5}, random.Random(0))  # type: ignore[arg-type]


def test_base_pilot_choose_numbers_raises() -> None:
    pilot = BasePilot()
    with pytest.raises(NotImplementedError):
        pilot.choose_numbers(None, {"legs": []}, random.Random(0))  # type: ignore[arg-type]


# --- Scalar descriptor: lossless at every span --------------------------------


@pytest.mark.parametrize(
    ("decision_class", "minimum", "maximum", "expected"),
    [
        ("announce_x", 0, 5, 5),  # P-A1 small: benefit -> max
        ("announce_x", 0, 100, 100),  # P-A1 large (span>16): benefit -> max
        ("amount", 1, 5, 5),  # P-A2 small
        ("amount", 1, 40, 40),  # P-A2 large
        ("announce_x", 0, 16, 16),  # P-B1 boundary 16
        ("announce_x", 0, 17, 17),  # boundary 17: full domain, no collapse
    ],
)
def test_scalar_benefit_selects_maximum_at_any_span(
    decision_class: str, minimum: int, maximum: int, expected: int
) -> None:
    response = _policy().decide(
        _request(
            decision_class,
            [],
            minimum=0,
            maximum=0,
            context={"outcome": "benefit", "numeric_min": minimum, "numeric_max": maximum},
        )
    )
    assert response["numeric_choice"] == expected


def test_scalar_detriment_selects_minimum() -> None:
    response = _policy().decide(
        _request(
            "announce_x",
            [],
            minimum=0,
            maximum=0,
            context={"outcome": "detriment", "numeric_min": 0, "numeric_max": 100},
        )
    )
    assert response["numeric_choice"] == 0


def test_scalar_neutral_selects_midpoint_deterministically() -> None:
    first = _policy().decide(
        _request(
            "amount",
            [],
            minimum=0,
            maximum=0,
            context={"outcome": "neutral", "numeric_min": 0, "numeric_max": 100},
        )
    )
    second = _policy().decide(
        _request(
            "amount",
            [],
            minimum=0,
            maximum=0,
            context={"outcome": "neutral", "numeric_min": 0, "numeric_max": 100},
        )
    )
    assert first["numeric_choice"] == 50 == second["numeric_choice"]


def test_scalar_stochastic_stays_in_domain_and_is_seeded() -> None:
    context = {"outcome": "benefit", "numeric_min": 0, "numeric_max": 100}
    first = _policy(PilotDecisionMode.STOCHASTIC).decide(
        _request("announce_x", [], minimum=0, maximum=0, context=dict(context))
    )
    second = _policy(PilotDecisionMode.STOCHASTIC).decide(
        _request("announce_x", [], minimum=0, maximum=0, context=dict(context))
    )
    assert 0 <= first["numeric_choice"] <= 100
    assert first["numeric_choice"] == second["numeric_choice"]


def test_huge_span_completes_in_single_decision_budget_without_materialization() -> None:
    # P-N1: span 10^9 is O(1) — no view list is ever built.
    started = time.perf_counter()
    response = _policy().decide(
        _request(
            "announce_x",
            [],
            minimum=0,
            maximum=0,
            context={"outcome": "benefit", "numeric_min": 0, "numeric_max": 1_000_000_000},
        )
    )
    elapsed = time.perf_counter() - started
    assert response["numeric_choice"] == 1_000_000_000
    assert elapsed < 2.0


def test_target_amount_companion_path() -> None:
    response = _policy().decide(
        _request(
            "target_amount",
            [_option("actor", "target_amount", "Full Game Seat 1")],
            minimum=1,
            maximum=1,
            context={"outcome": "benefit", "numeric_min": 1, "numeric_max": 40},
        )
    )
    assert response["selected_option_ids"] == ["actor"]
    assert response["numeric_choice"] == 40


# --- Scalar bounds strictness (N-14/N-15 families, Lab lane) -------------------


@pytest.mark.parametrize(
    "context",
    [
        {},
        {"outcome": "benefit", "numeric_min": 0},
        {"outcome": "benefit", "numeric_max": 5},
        {"outcome": "benefit", "numeric_min": 6, "numeric_max": 5},
        {"outcome": "benefit", "numeric_min": True, "numeric_max": 5},
        {"outcome": "benefit", "numeric_min": 0.0, "numeric_max": 5},
        {"outcome": "benefit", "numeric_min": "0", "numeric_max": 5},
    ],
)
def test_scalar_malformed_bounds_fail_closed(context: dict[str, Any]) -> None:
    with pytest.raises(FullGameProtocolError):
        _policy().decide(_request("announce_x", [], minimum=0, maximum=0, context=context))


class _OutOfDomainPilot(GenericCommanderPilot):
    def choose_number(
        self, state: PilotStateView, domain: dict[str, Any], rng: random.Random
    ) -> int:
        return int(domain["max"]) + 1


class _NonIntegerPilot(GenericCommanderPilot):
    def choose_number(
        self, state: PilotStateView, domain: dict[str, Any], rng: random.Random
    ) -> int:
        return "max"  # type: ignore[return-value]


def _hostile_policy(pilot: GenericCommanderPilot) -> ExternalPilotDecisionPolicy:
    config = pilot.config
    binding = FullGamePilotBinding(
        seat=1,
        deck_id="fixture-1",
        strategy="generic",
        commander_names=("Isamaru, Hound of Konda",),
        config=config,
        pilot_identity="GenericCommanderPilot",
        pilot_version="1.0.0",
        decision_policy_version="xmage-full-game-policy-1.0.0",
    )
    runtimes = (
        _RuntimePilot(binding=binding, pilot=pilot),
        *(
            _RuntimePilot(
                binding=FullGamePilotBinding(
                    seat=seat,
                    deck_id=f"fixture-{seat}",
                    strategy="generic",
                    commander_names=("Isamaru, Hound of Konda",),
                    config=config,
                    pilot_identity="GenericCommanderPilot",
                    pilot_version="1.0.0",
                    decision_policy_version="xmage-full-game-policy-1.0.0",
                ),
                pilot=GenericCommanderPilot(config),
            )
            for seat in range(2, 5)
        ),
    )
    return ExternalPilotDecisionPolicy(runtimes, 20260915)  # type: ignore[arg-type]


def test_out_of_domain_pilot_return_fails_closed_without_fallback() -> None:
    # N-23: the new path has no clamp/midpoint/default arm.
    pilot = _OutOfDomainPilot(
        PilotConfig(
            pilot_name="auto", strength=PilotStrength.AVERAGE, mode=PilotDecisionMode.DETERMINISTIC
        )
    )
    with pytest.raises(FullGameProtocolError, match="outside authoritative domain"):
        _hostile_policy(pilot).decide(
            _request(
                "announce_x",
                [],
                minimum=0,
                maximum=0,
                context={"outcome": "benefit", "numeric_min": 0, "numeric_max": 100},
            )
        )


def test_non_integer_pilot_return_fails_closed() -> None:
    pilot = _NonIntegerPilot(
        PilotConfig(
            pilot_name="auto", strength=PilotStrength.AVERAGE, mode=PilotDecisionMode.DETERMINISTIC
        )
    )
    with pytest.raises(FullGameProtocolError, match="non-integer"):
        _hostile_policy(pilot).decide(
            _request(
                "amount",
                [],
                minimum=0,
                maximum=0,
                context={"outcome": "benefit", "numeric_min": 0, "numeric_max": 5},
            )
        )


# --- Joint vector path (P-M1 unit half; N-16/N-23 Lab lane) --------------------


def _joint_context() -> dict[str, Any]:
    return {
        "outcome": "benefit",
        "numeric_legs": [
            {"min": 0, "max": 100, "prompt": "damage to A"},
            {"min": 0, "max": 3, "prompt": "damage to B"},
        ],
        "numeric_total_min": 50,
        "numeric_total_max": 60,
    }


def test_joint_benefit_vector_satisfies_legs_and_binding_total() -> None:
    response = _policy().decide(
        _request("multi_amount", [], minimum=0, maximum=0, context=_joint_context())
    )
    # Deterministic benefit: per-leg maxima [100, 3] repaired into 50..60
    # from the last leg upward -> [60, 0].
    assert response["numeric_choices"] == [60, 0]


def test_joint_deterministic_strategy_is_reproducible() -> None:
    first = _policy().decide(
        _request("multi_amount", [], minimum=0, maximum=0, context=_joint_context())
    )
    second = _policy().decide(
        _request("multi_amount", [], minimum=0, maximum=0, context=_joint_context())
    )
    assert first["numeric_choices"] == second["numeric_choices"]


def test_joint_response_carries_vector_key_not_scalar() -> None:
    response = _policy().decide(
        _request("multi_amount", [], minimum=0, maximum=0, context=_joint_context())
    )
    assert "numeric_choices" in response
    assert "numeric_choice" not in response


class _BadVectorPilot(GenericCommanderPilot):
    VECTOR: tuple[int, ...] = ()

    def choose_numbers(
        self, state: PilotStateView, domain: dict[str, Any], rng: random.Random
    ) -> list[int]:
        return list(self.VECTOR)


@pytest.mark.parametrize(
    ("vector", "match"),
    [
        ((57,), "wrong vector length"),
        ((57, 3, 1), "wrong vector length"),
        ((101, 3), "outside authoritative domain"),
        ((57, 4), "outside authoritative domain"),
        ((10, 0), "outside authoritative band"),
    ],
)
def test_joint_pilot_violations_fail_closed(vector: tuple[int, ...], match: str) -> None:
    pilot = _BadVectorPilot(
        PilotConfig(
            pilot_name="auto", strength=PilotStrength.AVERAGE, mode=PilotDecisionMode.DETERMINISTIC
        )
    )
    pilot.VECTOR = vector
    with pytest.raises(FullGameProtocolError, match=match):
        _hostile_policy(pilot).decide(
            _request("multi_amount", [], minimum=0, maximum=0, context=_joint_context())
        )


def test_joint_non_integer_element_fails_closed() -> None:
    class _MixedPilot(GenericCommanderPilot):
        def choose_numbers(
            self, state: PilotStateView, domain: dict[str, Any], rng: random.Random
        ) -> list[int]:
            return [57, True]  # type: ignore[list-item]

    pilot = _MixedPilot(
        PilotConfig(
            pilot_name="auto", strength=PilotStrength.AVERAGE, mode=PilotDecisionMode.DETERMINISTIC
        )
    )
    with pytest.raises(FullGameProtocolError, match="non-integer element"):
        _hostile_policy(pilot).decide(
            _request("multi_amount", [], minimum=0, maximum=0, context=_joint_context())
        )


@pytest.mark.parametrize(
    "context",
    [
        {"outcome": "benefit"},
        {"outcome": "benefit", "numeric_legs": []},
        {
            "outcome": "benefit",
            "numeric_legs": [{"min": 5, "max": 1}],
            "numeric_total_min": 0,
            "numeric_total_max": 9,
        },
        {
            "outcome": "benefit",
            "numeric_legs": [{"min": 3, "max": 3}, {"min": 3, "max": 3}],
            "numeric_total_min": 5,
            "numeric_total_max": 5,
        },
        {
            "outcome": "benefit",
            "numeric_legs": [{"min": 0, "max": 4}],
            "numeric_total_min": 9,
            "numeric_total_max": 1,
        },
    ],
)
def test_joint_malformed_or_empty_domain_fails_closed(context: dict[str, Any]) -> None:
    with pytest.raises(FullGameProtocolError):
        _policy().decide(_request("multi_amount", [], minimum=0, maximum=0, context=context))


# --- F-RULES-03 dispositions ----------------------------------------------------


def test_mulligan_cap_forces_keep_with_record() -> None:
    policy = _policy()
    policy._mulligan_count[1] = 3
    response = policy.decide(
        _request(
            "mulligan",
            [
                _option("keep", "keep", "Keep opening hand"),
                _option("mulligan", "mulligan", "Take mulligan"),
            ],
            minimum=1,
            maximum=1,
        )
    )
    # Seven Plains score below every keep threshold, so the pilot wants a
    # mulligan; the cap forces the keep instead.
    assert response["selected_option_ids"] == ["keep"]


def test_priority_mana_abilities_are_offered_to_pilot() -> None:
    # Old code auto-passed here, hiding two discretionary mana abilities.
    response = _policy().decide(
        _request(
            "priority",
            [
                _option("pass", "pass_priority", "Pass priority"),
                _option("mana-a", "mana_ability", "Tap Plains for W"),
                _option("mana-b", "mana_ability", "Tap Mountain for R"),
            ],
            minimum=1,
            maximum=1,
        )
    )
    assert response["selected_option_ids"] in (["mana-a"], ["mana-b"])


def test_priority_lone_pass_is_forced() -> None:
    response = _policy().decide(
        _request(
            "priority",
            [_option("pass", "pass_priority", "Pass priority")],
            minimum=1,
            maximum=1,
        )
    )
    assert response["selected_option_ids"] == ["pass"]


def test_pool_single_candidate_is_forced() -> None:
    response = _policy().decide(
        _request(
            "mana_payment",
            [
                _option("cancel", "cancel_mana_payment", "Cancel"),
                _option("pool-white", "mana_pool", "Spend white mana", mana_type="white"),
                _option("tap", "mana_ability", "Tap Plains for W"),
            ],
            minimum=1,
            maximum=1,
            context={"unpaid_mana": "{W}"},
        )
    )
    assert response["selected_option_ids"] == ["pool-white"]


def test_pool_multiple_candidates_go_to_pilot() -> None:
    response = _policy().decide(
        _request(
            "mana_payment",
            [
                _option("cancel", "cancel_mana_payment", "Cancel"),
                _option("pool-blue", "mana_pool", "Spend blue mana", mana_type="blue"),
                _option("pool-white", "mana_pool", "Spend white mana", mana_type="white"),
                _option("tap", "mana_ability", "Tap Plains for W"),
            ],
            minimum=1,
            maximum=1,
            context={"unpaid_mana": "{3}"},
        )
    )
    assert response["selected_option_ids"] in (["pool-blue"], ["pool-white"])


def test_pool_liveness_guard_still_avoids_wrong_color() -> None:
    response = _policy().decide(
        _request(
            "mana_payment",
            [
                _option("cancel", "cancel_mana_payment", "Cancel"),
                _option("pool-blue", "mana_pool", "Spend blue mana", mana_type="blue"),
                _option("tap", "mana_ability", "Tap Plains for W"),
            ],
            minimum=1,
            maximum=1,
            context={"unpaid_mana": "{W}"},
        )
    )
    assert response["selected_option_ids"] != ["pool-blue"]


def test_bottom_routing_uses_structured_flag_not_prompt_text() -> None:
    bottom_prompt = (
        "Select cards to put on the BOTTOM of your LIBRARY (last one chosen will be bottommost)"
    )
    options = [_option(f"hand-{index}", "choice", "Plains") for index in range(3)]
    # Prompt text alone must NOT trigger bottom routing (sniff is dead).
    generic = _policy().decide(
        _request(
            "choose_object",
            options,
            minimum=0,
            maximum=0,
            context={"outcome": "neutral"},
            prompt=bottom_prompt,
        )
    )
    assert generic["selected_option_ids"] == []
    # The structured bridge flag routes to bottom-card strategy.
    bottomed = _policy().decide(
        _request(
            "choose_object",
            options,
            minimum=1,
            maximum=1,
            context={"outcome": "neutral", "bottom_of_library_selection": True},
            prompt=bottom_prompt,
        )
    )
    assert len(bottomed["selected_option_ids"]) == 1
    assert set(bottomed["selected_option_ids"]).issubset({o["option_id"] for o in options})


def test_boolean_missing_metadata_fails_closed() -> None:
    # N-10 Lab lane.
    with pytest.raises(FullGameProtocolError, match="explicit boolean"):
        _policy().decide(
            _request(
                "choose_use",
                [_option("yes", "boolean", "Yes"), _option("no", "boolean", "No")],
                minimum=1,
                maximum=1,
                context={"outcome": "benefit"},
            )
        )


def test_unoffered_pilot_selection_fails_closed() -> None:
    # Hostile pilot invents an option id outside the offered set.

    class _ForgingPilot(GenericCommanderPilot):
        def choose_action(  # type: ignore[override]
            self, state: PilotStateView, actions: Any, rng: random.Random
        ) -> PilotDecision:
            return PilotDecision(
                pilot_name=self.pilot_name,
                strength=self.config.strength,
                mode=self.config.mode,
                selected_action_id="forged-not-offered",
            )

    pilot = _ForgingPilot(
        PilotConfig(
            pilot_name="auto", strength=PilotStrength.AVERAGE, mode=PilotDecisionMode.DETERMINISTIC
        )
    )
    with pytest.raises(FullGameProtocolError, match="unknown"):
        _hostile_policy(pilot).decide(
            _request(
                "choice",
                [_option("choice-a", "choice", "Draw a card")],
                minimum=1,
                maximum=1,
            )
        )


# --- Replay vector extension ------------------------------------------------------


def _digest() -> str:
    return "f" * 64


def test_tape_accepts_joint_vector_step() -> None:
    step = TapeReplayStep(
        sequence=1,
        step_kind="decision",
        decision_class="multi_amount",
        actor_principal=1,
        decision_revision=9,
        principal_observation_digest=_digest(),
        legal_set_digest=_digest(),
        legal_set_size=0,
        numeric_choices=(55, 3),
        numeric_legs_min=(0, 0),
        numeric_legs_max=(100, 3),
        numeric_total_min=50,
        numeric_total_max=60,
        rng_calls_before=0,
        event_offset_before=9,
        event_digest=_digest(),
    )
    assert step.numeric_choices == (55, 3)


def test_tape_rejects_scalar_vector_mixing() -> None:
    with pytest.raises(Exception, match="either a scalar or a joint"):
        TapeReplayStep(
            sequence=1,
            step_kind="decision",
            decision_class="multi_amount",
            actor_principal=1,
            decision_revision=9,
            principal_observation_digest=_digest(),
            legal_set_digest=_digest(),
            legal_set_size=0,
            numeric_choice=3,
            numeric_min=1,
            numeric_max=3,
            numeric_choices=(2, 2),
            numeric_legs_min=(1, 1),
            numeric_legs_max=(3, 3),
            numeric_total_min=2,
            numeric_total_max=6,
            rng_calls_before=0,
            event_offset_before=9,
            event_digest=_digest(),
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"numeric_choices": (1,)},
        {"numeric_choices": (1, 9)},
        {"numeric_choices": (0, 0)},
    ],
)
def test_tape_rejects_incoherent_joint_vectors(overrides: dict[str, Any]) -> None:
    base: dict[str, Any] = {
        "sequence": 1,
        "step_kind": "decision",
        "decision_class": "multi_amount",
        "actor_principal": 1,
        "decision_revision": 9,
        "principal_observation_digest": _digest(),
        "legal_set_digest": _digest(),
        "legal_set_size": 0,
        "numeric_legs_min": (1, 1),
        "numeric_legs_max": (3, 3),
        "numeric_total_min": 2,
        "numeric_total_max": 6,
        "rng_calls_before": 0,
        "event_offset_before": 9,
        "event_digest": _digest(),
    }
    with pytest.raises(ValueError, match=r"joint|leg|total|length|band|bounds"):
        TapeReplayStep(**{**base, **overrides})


def test_scalar_event_digest_is_byte_stable() -> None:
    # The conditional vector binding must not move any scalar digest.
    digest = event_digest_for_step(
        sequence=1,
        decision_class="announce_x",
        actor_principal=1,
        selected_fingerprints=(),
        numeric_choice=3,
        rng_calls_before=0,
        rng_calls_after=1,
        turn_before=1,
        turn_after=1,
        observation_digest=_digest(),
        post_digest=None,
    )
    from commander_lab.semantic_replay.canonicalization import canonical_hash

    assert digest == canonical_hash(
        {
            "actor_principal": 1,
            "decision_class": "announce_x",
            "numeric_choice": 3,
            "observation_digest": _digest(),
            "post_digest": None,
            "rng_calls_after": 1,
            "rng_calls_before": 0,
            "selected_fingerprints": [],
            "sequence": 1,
            "turn_after": 1,
            "turn_before": 1,
        }
    )


def test_joint_event_digest_binds_vector() -> None:
    plain = event_digest_for_step(
        sequence=1,
        decision_class="multi_amount",
        actor_principal=1,
        selected_fingerprints=(),
        numeric_choice=None,
        rng_calls_before=0,
        rng_calls_after=1,
        turn_before=1,
        turn_after=1,
        observation_digest=_digest(),
        post_digest=None,
    )
    bound = event_digest_for_step(
        sequence=1,
        decision_class="multi_amount",
        actor_principal=1,
        selected_fingerprints=(),
        numeric_choice=None,
        numeric_choices=(2, 2),
        rng_calls_before=0,
        rng_calls_after=1,
        turn_before=1,
        turn_after=1,
        observation_digest=_digest(),
        post_digest=None,
    )
    assert plain != bound


def test_recorder_joint_capture() -> None:
    decision = {"context": _joint_context()}
    response = {"selected_option_ids": [], "numeric_choices": [55, 3]}
    choices, legs_min, legs_max, total_min, total_max = _joint_numeric_of(decision, response)
    assert choices == (55, 3)
    assert legs_min == (0, 0)
    assert legs_max == (100, 3)
    assert (total_min, total_max) == (50, 60)


def test_recorder_joint_absent_for_scalar() -> None:
    decision = {"context": {"numeric_min": 0, "numeric_max": 5}}
    response = {"selected_option_ids": [], "numeric_choice": 3}
    assert _joint_numeric_of(decision, response) == (None, None, None, None, None)


def test_recorder_joint_malformed_diverges() -> None:
    decision = {
        "context": {"numeric_legs": [{"min": 0}], "numeric_total_min": 0, "numeric_total_max": 1}
    }
    response = {"selected_option_ids": [], "numeric_choices": [0]}
    with pytest.raises(ReplayDivergence) as exc:
        _joint_numeric_of(decision, response)
    assert exc.value.divergence == DivergenceClass.DECISION_CLASS_MISMATCH
