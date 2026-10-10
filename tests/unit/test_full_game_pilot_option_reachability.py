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


def test_action_impossible_for_its_own_sake_is_never_re_offered() -> None:
    """An untap cost on an already untapped source cannot be paid at all.

    Only a pool shortfall is worth re-offering as needs-mana-first; this one
    stays withheld whatever the pool holds.
    """
    untap = _option(
        "untap",
        "activated_ability",
        "Wild Growth Walker — {1}, Untap target creature.",
        source_name="Wild Growth Walker",
        source_object_id="walker-1",
        ability_type="activated",
        mana_cost_generic=1,
        mana_cost_white=0,
        mana_cost_blue=0,
        mana_cost_black=0,
        mana_cost_red=0,
        mana_cost_green=0,
        mana_cost_colorless=0,
        pool_covers_mana_cost=False,
        requires_tap_source=False,
        requires_untap_source=True,
        requires_sacrifice_source=False,
        source_tapped=False,
    )
    policy, pilot = _policy(_RecordingPilot)
    response = policy.decide(_request("priority", [_PASS, *_PLAINS_TAPS, untap], offset=1))
    assert response["selected_option_ids"] == ["pass"]
    assert not any("Wild Growth Walker" in view.card_name for view in pilot.seen)


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


def test_a_second_archive_can_fund_the_first() -> None:
    """Two permanents of one card are two sources.

    Matching on the Rules-visible name alone made a second Hedron Archive
    invisible as funding for the first, so the Lab passed a payment it could
    plainly make.
    """
    other_archive = _mana_source("archive-mana-2", "Hedron Archive", "C", object_id="archive-2")
    response = _default_policy().decide(
        _request("priority", [_PASS, _ARCHIVE_MANA, other_archive, ARCHIVE], offset=1)
    )
    assert response["selected_option_ids"] == ["archive-mana-2"]


def test_funding_is_skipped_when_no_source_can_pay_any_of_the_cost() -> None:
    """A {W}{W} action is not funded by tapping a Mountain.

    Spending mana that cannot pay any part of the cost wastes the tap for
    nothing, so when nothing fits the Lab passes instead.
    """
    mountain = _mana_source("tap-mountain", "Mountain", "R", object_id="mountain-1")
    response = _policy(_NeedsManaPilot)[0].decide(
        _request(
            "priority",
            [_PASS, mountain, _archive(mana_cost_white=2, mana_cost_generic=0)],
            offset=1,
        )
    )
    assert response["selected_option_ids"] == ["pass"]


# ---------------------------------------------------------------------------
# P2-2: AIDontUseIt is the engine's own AI label, not a player preference
# ---------------------------------------------------------------------------


def _boolean(
    outcome: str,
    prompt: str,
    *,
    offset: int = 1,
    source_name: str = "Kicked Card",
    state: dict[str, Any] | None = None,
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
        state=state or _state(),
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


def _multikicker_prompt(offer: int, *, cost: str = "{2}") -> str:
    """The offer exactly as ``KickerAbility.addOptionalAdditionalCosts`` writes it.

    ``"Pay " + (activatedCount + 1) + (" time "|" times ") + cost + " ?"`` --
    so the number names the offer being made, not a total, and a source that
    read it as a total would answer the wrong questions.
    """
    return f"Pay {offer} {'time' if offer == 1 else 'times'} Multikicker {cost} ?"


def test_repeated_multikicker_sequence_ends_with_no_within_the_cap() -> None:
    """Three untapped Plains and a {2} multikicker fund exactly one payment."""
    policy = _default_policy()
    answers = [
        policy.decide(_boolean("aidontuseit", _multikicker_prompt(offer), offset=offer))[
            "selected_option_ids"
        ][0]
        for offer in (1, 2, 3)
    ]
    assert answers[:2] == ["yes", "no"]
    # The engine stops re-offering once the pilot says No; a third entry only
    # pins that the No reset the chain rather than leaving a spent count.
    assert answers[2] == "yes"


def test_multikicker_cap_counts_the_per_payment_cost_not_the_offer_ordinal() -> None:
    """N is the offer ordinal, so the cap must come from what one payment costs.

    Reading N as a declared total would let the pilot answer Yes while N only
    counts offers -- with three untapped Plains and {2} that is one payment.
    """
    policy = _default_policy()
    assert [
        policy.decide(_boolean("aidontuseit", _multikicker_prompt(1), offset=1))[
            "selected_option_ids"
        ][0],
        policy.decide(_boolean("aidontuseit", _multikicker_prompt(2), offset=2))[
            "selected_option_ids"
        ][0],
    ] == ["yes", "no"]


def test_multikicker_pool_mana_funds_further_payments() -> None:
    """Six mana of pool and lands with a {2} cost funds three payments."""
    policy = _default_policy()
    answers = [
        policy.decide(
            _boolean(
                "aidontuseit", _multikicker_prompt(offer), offset=offer, state=_state(pool_white=3)
            )
        )["selected_option_ids"][0]
        for offer in (1, 2, 3, 4)
    ]
    assert answers == ["yes", "yes", "yes", "no"]


def test_ordinary_may_trigger_prompt_is_never_capped() -> None:
    """Mentor of the Meek asks "Pay {1}?" once per creature entering.

    Same source, same outcome, four times in one turn. It is four separate
    discretionary questions, not one repeating offer: a guard that cannot
    parse the prompt must not answer the fourth for the player.
    """
    policy = _default_policy()
    answers = [
        policy.decide(
            _boolean(
                "benefit",
                "Pay {1}?",
                offset=offer,
                source_name="Mentor of the Meek",
            )
        )["selected_option_ids"][0]
        for offer in (1, 2, 3, 4)
    ]
    assert answers == ["yes", "yes", "yes", "yes"]


def test_unparseable_prompt_is_never_capped() -> None:
    """No ordinal means no cap: the Lab does not bound a choice it cannot read."""
    policy = _default_policy()
    answers = [
        policy.decide(_boolean("aidontuseit", "Use the ability?", offset=offer))[
            "selected_option_ids"
        ][0]
        for offer in (1, 2, 3, 4, 5)
    ]
    assert answers == ["yes"] * 5


def test_an_ordinary_prompt_between_offers_resets_the_chain() -> None:
    """Only consecutive re-offers of one ability are counted."""
    policy = _default_policy()
    assert (
        policy.decide(_boolean("aidontuseit", _multikicker_prompt(1), offset=1))[
            "selected_option_ids"
        ][0]
        == "yes"
    )
    assert (
        policy.decide(_boolean("aidontuseit", "Pay {2}?", offset=2, source_name="Buyback Spell"))[
            "selected_option_ids"
        ][0]
        == "yes"
    )
    assert (
        policy.decide(_boolean("aidontuseit", _multikicker_prompt(2), offset=3))[
            "selected_option_ids"
        ][0]
        == "yes"
    )


def test_different_source_resets_the_repeat_count() -> None:
    policy = _default_policy()
    first = [
        policy.decide(
            _boolean("aidontuseit", _multikicker_prompt(offer), offset=offer, source_name="First")
        )["selected_option_ids"][0]
        for offer in (1, 2)
    ]
    assert first == ["yes", "no"]
    second = policy.decide(
        _boolean("aidontuseit", _multikicker_prompt(1), offset=3, source_name="Second")
    )["selected_option_ids"]
    assert second == ["yes"]


def test_boolean_source_key_prefers_the_ability_original_id() -> None:
    """Chain memory keys on the engine's card-definition identity."""
    policy = _default_policy()
    # Two instances of one ability agree, whatever the engine calls them: the
    # key must not move when a per-instance object id differs between processes.
    assert policy._boolean_source_key(
        {"ability_original_id": "orig-1", "source_object_id": "inst-a"}
    ) == policy._boolean_source_key({"ability_original_id": "orig-1", "source_object_id": "inst-b"})
    # The Rules-visible name only decides when no original id is reported.
    assert policy._boolean_source_key(
        {"source_name": "Hedron Archive", "source_object_id": "inst-a"}
    ) == policy._boolean_source_key({"source_name": "Hedron Archive", "source_object_id": "inst-b"})
    assert policy._boolean_source_key({"source_name": "Archive A"}) != policy._boolean_source_key(
        {"source_name": "Archive B"}
    )
    # An instance id is the last resort, and it is the engine's own.
    assert policy._boolean_source_key({"source_object_id": "inst-a"}) == "instance:inst-a"
    assert policy._boolean_source_key({"source_name": "X"}) != policy._boolean_source_key(
        {"source_object_id": "inst-a"}
    )
    assert policy._boolean_source_key(None) == ""


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
_TREASURE = _option(
    "treasure",
    "mana_ability",
    "Treasure — {T}, Sacrifice this: Add one mana.",
    source_name="Treasure",
    source_object_id="treasure-1",
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
    # What the bridge really reports: SacrificeSourceCost is the source itself.
    requires_sacrifice_source=True,
    source_tapped=False,
)
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
# Ashnod's Altar, "Sacrifice a creature: Add {C}{C}", with the facts the bridge
# really emits for it: no mana cost, and requires_sacrifice_source False,
# because it sacrifices a *target*, not the source (SacrificeSourceCost only).
_ASHNODS_ALTAR = _option(
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


def test_self_sacrificing_mana_ability_still_floats_only() -> None:
    """Treasure/Lotus Petal spend their own source to produce mana.

    Spending the source is part of producing the mana, not something the
    window could have spent the mana on: the pool empties at the end of the
    step (CR 106.4) and the Treasure is gone. So [pass, Treasure] in a main
    phase with an empty stack must pass, not burn the Treasure.
    """
    view = _default_policy()._priority_mana_action(_TREASURE, _state())
    assert view.metadata["floats_mana_only"] is True
    response = _default_policy().decide(
        _request("priority", [_PASS, _TREASURE], state=_state(), offset=1)
    )
    assert response["selected_option_ids"] == ["pass"]


def test_sacrifice_another_permanent_ability_reports_no_bridge_fact() -> None:
    """Known limitation, pinned rather than faked: see the finding.

    ``enrichAbilityCostFacts`` sets ``requires_sacrifice_source`` only for
    ``SacrificeSourceCost``. Ashnod's Altar sacrifices a *creature* (a target),
    so the bridge reports no cost fact that distinguishes it from a Treasure,
    and the Lab keeps the conservative float-only flag even when answering it
    against a removal spell is the right play. Closing this needs the bridge
    to emit a fact for a sacrificed-another-permanent cost; the pilot must not
    invent one by reading the label.
    """
    assert _ASHNODS_ALTAR["metadata"]["requires_sacrifice_source"] is False
    view = _default_policy()._priority_mana_action(_ASHNODS_ALTAR, _state())
    assert view.metadata["floats_mana_only"] is True


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
