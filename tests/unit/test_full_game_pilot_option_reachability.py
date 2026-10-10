"""Every engine-offered discretionary option stays reachable in the full game.

Four review findings from #688, pinned here as behaviour:

* P2-1 an activated ability that taps/sacrifices its own source *and* costs
  mana (Hedron Archive ``{2}, {T}, Sacrifice``) was withheld for pool
  shortfall while every priority mana ability scored ``-1.0``, so the pool
  could never fill and the activation was unreachable;
* P2-2 ``AIDontUseIt`` was read as "decline", so every kicker, buyback,
  dredge, replicate and squad prompt was refused -- an engine-AI label was
  deciding for the player;
* P3-1 ``floats_mana_only`` was stamped on every priority mana ability
  regardless of its cost facts (Ashnod's Altar in response to removal is a
  real use, not idle floating);
* P3-2 payment-frame selection of a mana ability with its own mana cost
  (Agent of Stromgald ``{R}: Add {B}``) is legal and must stay selectable.

The engine stays the authority on legality throughout: these tests pin the
Lab's own routing and ranking, never a legality verdict.
"""

from __future__ import annotations

from typing import Any

from commander_lab.agents.pilots import STANDALONE_MANA_ABILITY_UTILITY, BasePilot, build_pilot
from commander_lab.engine.rules.full_game import (
    BOOLEAN_YES_REPEAT_LIMIT,
    ExternalPilotDecisionPolicy,
    FullGamePilotBinding,
    _RuntimePilot,
)
from commander_lab.models import (
    PilotActionView,
    PilotConfig,
    PilotDecisionMode,
    PilotStateView,
    PilotStrength,
    PilotUtilityBreakdown,
)

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


class _PassFirstPilot(BasePilot):
    """Test double: ranks every non-passing action below passing.

    It lets the reachability routing be tested independently of the generic
    scorer's arithmetic: whatever the pilot ranks, the Lab must route exactly
    that intent.
    """

    pilot_name = "PassFirstPilot"

    def evaluate_action(
        self, state: PilotStateView, action: PilotActionView
    ) -> PilotUtilityBreakdown:
        del state
        if action.action_kind == "pass":
            return PilotUtilityBreakdown(total_utility=1.0)
        return PilotUtilityBreakdown(total_utility=0.0)


class _NeedsManaPilot(BasePilot):
    """Test double: ranks a mana-first action above everything else."""

    pilot_name = "NeedsManaPilot"

    def evaluate_action(
        self, state: PilotStateView, action: PilotActionView
    ) -> PilotUtilityBreakdown:
        del state
        if action.metadata.get("needs_mana_first") is True:
            return PilotUtilityBreakdown(total_utility=2.0)
        if action.action_kind == "pass":
            return PilotUtilityBreakdown(total_utility=1.0)
        return PilotUtilityBreakdown(total_utility=0.0)


class _RecordingPilot(_NeedsManaPilot):
    """Test double that also records the action views it was offered."""

    pilot_name = "RecordingNeedsManaPilot"

    def __init__(self, config: PilotConfig | None = None) -> None:
        super().__init__(config)
        self.seen: list[PilotActionView] = []

    def choose_action(  # type: ignore[override]
        self, state: PilotStateView, actions: Any, rng: Any
    ) -> Any:
        self.seen.extend(actions)
        return super().choose_action(state, actions, rng)


def _policy(pilot_factory: Any = BasePilot) -> tuple[ExternalPilotDecisionPolicy, Any]:
    runtimes: list[_RuntimePilot] = []
    for seat in range(1, 5):
        config = PilotConfig(
            pilot_name="auto",
            strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
            mode=PilotDecisionMode.DETERMINISTIC,
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
        runtimes.append(_RuntimePilot(binding=binding, pilot=pilot_factory(config)))
    # Seat 1 is the pilot the fixtures' actor (seat 0) drives.
    return (
        ExternalPilotDecisionPolicy(tuple(runtimes), 20261010),  # type: ignore[arg-type]
        runtimes[0].pilot,
    )


def _default_policy() -> ExternalPilotDecisionPolicy:
    return _policy(BasePilot)[0]


def _state(
    *, step: str = "precombat_main", pool_white: int = 0, untapped_lands: int = 3
) -> dict[str, Any]:
    actor = {
        "player_id": "actor",
        "seat": 0,
        "life": 40,
        "hand_count": 2,
        "library_count": 90,
        "graveyard_count": 0,
        "battlefield": [
            {"object_id": f"land-{index}", "name": "Plains", "tapped": index >= untapped_lands}
            for index in range(3)
        ],
        "graveyard": [],
        "command": [{"object_id": "commander", "name": "Isamaru, Hound of Konda"}],
        "hand": [
            {"object_id": "hand-0", "name": "Savannah Lions"},
            {"object_id": "hand-1", "name": "Plains"},
        ],
        "mana_pool": {
            "white": pool_white,
            "blue": 0,
            "black": 0,
            "red": 0,
            "green": 0,
            "colorless": 0,
        },
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
        "turn_number": 5,
        "active_player_id": "actor",
        "priority_player_id": "actor",
        "phase": "beginning" if step == "upkeep" else "precombat_main",
        "step": step,
        "players": [actor, *opponents],
        "stack": [],
    }


def _option(option_id: str, option_type: str, label: str, **metadata: Any) -> dict[str, Any]:
    return {
        "option_id": option_id,
        "option_type": option_type,
        "label": label,
        "metadata": metadata,
    }


def _request(
    decision_class: str,
    options: list[dict[str, Any]],
    *,
    context: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    prompt: str = "",
    offset: int = 1,
    source_object: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "decision_id": f"opaque-{decision_class}-{offset}",
        "decision_offset": offset,
        "actor_id": "actor",
        "decision_class": decision_class,
        "pilot_state": state or _state(),
        "context": context or {},
        "minimum_selections": 1,
        "maximum_selections": 1,
        "legal_options": options,
        "prompt": prompt or decision_class,
        "source_object": source_object,
    }


def _mana_source(
    option_id: str, name: str, produced: str, *, object_id: str | None = None
) -> dict[str, Any]:
    """A tap-only mana ability with the full engine cost-fact set."""
    return _option(
        option_id,
        "mana_ability",
        f"{name} — {{T}}: Add {{{produced}}}.",
        source_name=name,
        source_object_id=object_id or f"obj-{option_id}",
        ability_type="mana",
        mana_cost_generic=0,
        mana_cost_white=0,
        mana_cost_blue=0,
        mana_cost_black=0,
        mana_cost_red=0,
        mana_cost_green=0,
        mana_cost_colorless=0,
        pool_covers_mana_cost=True,
        requires_tap_source=True,
        requires_untap_source=False,
        requires_sacrifice_source=False,
        source_tapped=False,
    )


_PLAIN_TAP = _mana_source("tap-plain", "Plains", "W", object_id="land-0")
_ISLAND_TAP = _mana_source("tap-island", "Island", "U", object_id="land-1")
_ARCHIVE_MANA = _mana_source("archive-mana", "Hedron Archive", "C", object_id="archive-1")
_PLAINS_TAPS = [
    _mana_source(f"tap-{index}", "Plains", "W", object_id=f"land-{index}") for index in range(3)
]
_PASS = _option("pass", "pass_priority", "Pass priority")


def _archive(**metadata: Any) -> dict[str, Any]:
    """ARCHIVE with engine cost facts overridden (the bridge's own numbers)."""
    return {**ARCHIVE, "metadata": {**ARCHIVE["metadata"], **metadata}}


# Hedron Archive: {2}, {T}, Sacrifice: Add {C}{C}. Its own mana cost is exactly
# the case the pool-shortfall gate used to withhold with no way back.
ARCHIVE = _option(
    "archive",
    "activated_ability",
    "Hedron Archive — {2}, {T}, Sacrifice: Add {C}{C}.",
    source_name="Hedron Archive",
    source_object_id="archive-1",
    ability_type="activated",
    mana_cost_generic=2,
    mana_cost_white=0,
    mana_cost_blue=0,
    mana_cost_black=0,
    mana_cost_red=0,
    mana_cost_green=0,
    mana_cost_colorless=0,
    pool_covers_mana_cost=False,
    requires_tap_source=True,
    requires_untap_source=False,
    requires_sacrifice_source=True,
    source_tapped=False,
)


# ---------------------------------------------------------------------------
# P2-1: pool-shortfall actions stay reachable, funded from another source
# ---------------------------------------------------------------------------


def test_pool_shortfall_action_is_offered_to_the_pilot_at_all() -> None:
    """It must reach the pilot; the Lab never hides an engine-offered option."""
    policy, pilot = _policy(_RecordingPilot)
    response = policy.decide(_request("priority", [_PASS, *_PLAINS_TAPS, ARCHIVE], offset=1))
    assert response["selected_option_ids"][0].startswith("tap-")
    assert any("Hedron Archive" in view.card_name for view in pilot.seen)


def test_pool_shortfall_action_view_is_marked_needing_mana_first() -> None:
    policy, pilot = _policy(_RecordingPilot)
    response = policy.decide(_request("priority", [_PASS, *_PLAINS_TAPS, ARCHIVE], offset=1))
    assert response["selected_option_ids"][0].startswith("tap-")
    marked = [
        view
        for view in pilot.seen
        if view.metadata.get("needs_mana_first") is True and "Hedron Archive" in view.card_name
    ]
    assert len(marked) == 1


def test_pool_covering_the_cost_selects_the_action_itself() -> None:
    """With the cost already in the pool the Archive is affordable outright."""
    response = _default_policy().decide(
        _request(
            "priority",
            [_PASS, *_PLAINS_TAPS, _archive(pool_covers_mana_cost=True)],
            state=_state(pool_white=2),
        )
    )
    assert response["selected_option_ids"] == ["archive"]


def test_upkeep_window_with_only_taps_and_pass_still_passes() -> None:
    """Control: no intent needs mana, so floating stays below passing."""
    response = _default_policy().decide(
        _request("priority", [_PASS, *_PLAINS_TAPS], state=_state(step="upkeep"))
    )
    assert response["selected_option_ids"] == ["pass"]


def test_action_ranked_below_pass_does_not_tap_anything() -> None:
    """A withheld action the pilot does not want must cost no mana."""
    response = _policy(_PassFirstPilot)[0].decide(
        _request("priority", [_PASS, *_PLAINS_TAPS, ARCHIVE], offset=1)
    )
    assert response["selected_option_ids"] == ["pass"]


def test_funding_mana_ability_never_comes_from_the_actions_own_source() -> None:
    """Hedron Archive is a land: its own {T} must not pay its own {2}."""
    response = _default_policy().decide(
        _request("priority", [_PASS, _ARCHIVE_MANA, *_PLAINS_TAPS, ARCHIVE], offset=1)
    )
    assert response["selected_option_ids"][0].startswith("tap-")


def test_funding_falls_back_to_passing_when_only_own_source_can_tap() -> None:
    """No other source exists: pass (always legal) rather than self-payment.

    The action stays engine-offered and the priority no-progress guard bounds
    the repetition, so nothing here silently deletes the option.
    """
    response = _default_policy().decide(
        _request("priority", [_PASS, _ARCHIVE_MANA, ARCHIVE], offset=1)
    )
    assert response["selected_option_ids"] == ["pass"]


def test_priority_no_progress_guard_still_bounds_the_mana_first_loop() -> None:
    """Identical windows repeat: the existing guard stops the loop."""
    policy = _default_policy()
    answers = [
        policy.decide(_request("priority", [_PASS, *_PLAINS_TAPS, ARCHIVE], offset=index))[
            "selected_option_ids"
        ][0]
        for index in (1, 2, 3, 4)
    ]
    assert all(answer.startswith("tap-") for answer in answers[:3])
    assert answers[3] == "pass"


def test_funding_prefers_the_mana_the_action_cost_names() -> None:
    """mana_payment_fit ranks the funding source against the action's cost."""
    white_cost_archive = _archive(mana_cost_white=1, mana_cost_generic=1)
    response = _policy(_NeedsManaPilot)[0].decide(
        _request(
            "priority",
            [_PASS, _ISLAND_TAP, _PLAIN_TAP, white_cost_archive],
            offset=1,
        )
    )
    assert response["selected_option_ids"] == ["tap-plain"]


# ---------------------------------------------------------------------------
# P2-2: AIDontUseIt is the engine's own AI label, not a player preference
# ---------------------------------------------------------------------------


def _boolean(
    outcome: str,
    prompt: str,
    *,
    offset: int = 1,
    source_name: str = "Kicked Card",
) -> dict[str, Any]:
    return _request(
        "choose_use",
        [
            _option("yes", "boolean", "Yes", value=True),
            _option("no", "boolean", "No", value=False),
        ],
        context={"outcome": outcome},
        prompt=prompt,
        offset=offset,
        state=_state(),
        source_object={
            "source_object_id": f"src-{source_name}",
            "ability_original_id": f"ability-{source_name}",
            "ability_type": "activated",
            "source_name": source_name,
        },
    )


def test_single_kicker_prompt_is_answered_yes() -> None:
    """One kicker payment is a normal discretionary choice, not a loop."""
    response = _default_policy().decide(_boolean("aidontuseit", "Kicker {2}?"))
    assert response["selected_option_ids"] == ["yes"]


def test_buyback_prompt_is_answered_yes() -> None:
    response = _default_policy().decide(_boolean("aidontuseit", "Pay {3} (Buyback)?"))
    assert response["selected_option_ids"] == ["yes"]


def test_repeated_multikicker_sequence_ends_with_no_within_the_cap() -> None:
    """Pay "N times" is parseable, so the cap is what the pilot can fund."""
    policy = _default_policy()
    answers = [
        policy.decide(_boolean("aidontuseit", "Pay 2 times Multikicker {2} ?", offset=index))[
            "selected_option_ids"
        ][0]
        for index in (1, 2, 3)
    ]
    assert answers == ["yes", "yes", "no"]


def test_unparseable_repeat_cap_is_a_fixed_small_constant() -> None:
    """No parseable cost: the fixed guard constant bounds consecutive yeses.

    A "No" is a real answer the engine acts on (it stops re-offering), so the
    count restarts afterwards; the invariant is that no run of consecutive
    yeses ever exceeds the cap.
    """
    policy = _default_policy()
    answers = [
        policy.decide(_boolean("aidontuseit", "Use the ability?", offset=index))[
            "selected_option_ids"
        ][0]
        for index in (1, 2, 3, 4, 5)
    ]
    assert answers[:BOOLEAN_YES_REPEAT_LIMIT] == ["yes"] * BOOLEAN_YES_REPEAT_LIMIT
    assert answers[BOOLEAN_YES_REPEAT_LIMIT] == "no"
    assert (
        max(len(run) for run in "".join("Y" if a == "yes" else "N" for a in answers).split("N"))
        <= BOOLEAN_YES_REPEAT_LIMIT
    )


def test_different_source_resets_the_repeat_count() -> None:
    policy = _default_policy()
    first = [
        policy.decide(
            _boolean(
                "aidontuseit", "Pay 2 times Multikicker {2} ?", offset=index, source_name="First"
            )
        )["selected_option_ids"][0]
        for index in (1, 2, 3)
    ]
    assert first == ["yes", "yes", "no"]
    second = policy.decide(
        _boolean("aidontuseit", "Pay 2 times Multikicker {2} ?", offset=4, source_name="Second")
    )["selected_option_ids"]
    assert second == ["yes"]


def test_detriment_polarity_is_unchanged() -> None:
    """Removing the engine-AI label must not touch detriment polarity."""
    response = _default_policy().decide(
        _boolean("detriment", "Discard a card?", source_name="Curse")
    )
    assert response["selected_option_ids"] == ["no"]


# ---------------------------------------------------------------------------
# P3-1: floats_mana_only follows the bridge's cost facts
# ---------------------------------------------------------------------------

_SOL_RING = _mana_source("sol-ring", "Sol Ring", "C", object_id="sol-ring-1")
_AGENT_OF_STROMGALD = _option(
    "agent",
    "mana_ability",
    "Agent of Stromgald — {R}: Add {B}.",
    source_name="Agent of Stromgald",
    source_object_id="agent-1",
    ability_type="mana",
    mana_cost_generic=0,
    mana_cost_white=0,
    mana_cost_blue=0,
    mana_cost_black=0,
    mana_cost_red=1,
    mana_cost_green=0,
    mana_cost_colorless=0,
    pool_covers_mana_cost=False,
    requires_tap_source=False,
    requires_untap_source=False,
    requires_sacrifice_source=False,
    source_tapped=False,
)


def test_pure_mana_ability_still_floats_only() -> None:
    """Control: no mana cost, only a tap -> idling, so it ranks below pass."""
    view = _default_policy()._priority_mana_action(_SOL_RING, _state())
    assert view.metadata["floats_mana_only"] is True


def test_costed_mana_ability_is_not_float_only() -> None:
    """Agent of Stromgald's {R}: Add {B} is more than idling."""
    view = _default_policy()._priority_mana_action(_AGENT_OF_STROMGALD, _state())
    assert view.metadata.get("floats_mana_only") is not True


def test_sacrificing_mana_ability_in_response_is_reachable() -> None:
    """Ashnod's Altar answered against removal is a real use, not floating."""
    altar = _option(
        "altar",
        "mana_ability",
        "Ashnod's Altar — Sacrifice a creature: Add {C}{C}.",
        source_name="Ashnod's Altar",
        source_object_id="altar-1",
        ability_type="mana",
        mana_cost_generic=0,
        mana_cost_white=0,
        mana_cost_blue=0,
        mana_cost_black=0,
        mana_cost_red=0,
        mana_cost_green=0,
        mana_cost_colorless=0,
        pool_covers_mana_cost=True,
        requires_tap_source=False,
        requires_untap_source=False,
        requires_sacrifice_source=True,
        source_tapped=False,
    )
    state = _state()
    state["stack"] = [{"name": "Doom Blade"}]
    response = _default_policy().decide(
        _request("priority", [_PASS, *_PLAINS_TAPS, altar], state=state, offset=1)
    )
    assert response["selected_option_ids"] == ["altar"]


def test_mana_ability_without_cost_facts_keeps_the_float_only_flag() -> None:
    """Absent facts are unknown, and unknown keeps the conservative flag."""
    bare = _option(
        "bare", "mana_ability", "Unknown Artifact — {T}: Add {C}.", source_name="Unknown"
    )
    view = _default_policy()._priority_mana_action(bare, _state())
    assert view.metadata["floats_mana_only"] is True


def test_float_only_utility_is_unchanged_for_genuine_floating() -> None:
    config = PilotConfig(
        pilot_name="auto",
        strength=PilotStrength.NEAR_OPTIMAL_HEURISTIC,
        mode=PilotDecisionMode.DETERMINISTIC,
    )
    pilot = build_pilot(config, strategy="generic")
    policy = _default_policy()
    state = policy._pilot_state(policy._pilots[1], _state())
    assert (
        pilot.evaluate_action(
            state, policy._priority_mana_action(_SOL_RING, _state())
        ).total_utility
        == STANDALONE_MANA_ABILITY_UTILITY
    )


# ---------------------------------------------------------------------------
# P3-2: a costed mana ability stays selectable inside a payment
# ---------------------------------------------------------------------------


def _payment_request(offset: int) -> dict[str, Any]:
    return _request(
        "mana_payment",
        [
            _option("cancel", "cancel_mana_payment", "Cancel mana payment"),
            _PLAIN_TAP,
            _AGENT_OF_STROMGALD,
        ],
        context={"unpaid_mana": "{B}"},
        offset=offset,
    )


def test_costed_mana_ability_is_selectable_in_a_payment_frame() -> None:
    """CR 605.3a / 601.2g: activating a mana ability to pay a cost is legal."""
    response = _default_policy().decide(_payment_request(1))
    assert response["selected_option_ids"] == ["agent"]


def test_mana_no_progress_guard_cancels_the_costed_mana_repeat() -> None:
    """Selecting it repeatedly cannot loop forever."""
    policy = _default_policy()
    answers = [
        policy.decide(_payment_request(index))["selected_option_ids"][0] for index in (1, 2, 3)
    ]
    assert answers == ["agent", "agent", "cancel"]
