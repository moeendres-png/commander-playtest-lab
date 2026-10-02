"""AF07 Phase 2b executor extensions on the production midgame lane.

Each extension answers only a decision the engine itself asks, from what the
record's own step names, and fails closed on anything ambiguous:

* an alternative cost (evoke, overload) the record's cast names, either as the
  engine's own alternative spell offer or as its later cost choice;
* a scripted cast that waits for an empty stack (``timing: empty_stack``);
* the order of identical instances of one triggered ability, and of two
  abilities of one source named by a fragment of their rules text;
* record tokens bound per fixture to explicit engine event patterns, decision
  frames or engine-observed permanent state.
"""

from __future__ import annotations

from typing import Any

import pytest

from commander_lab.qualification.current_boundary import midgame_rows as mr


def _offer(label: str, option_type: str, **engine: Any) -> dict[str, Any]:
    return {
        "metadata": {
            "option_type": option_type,
            "option_id": engine.pop("option_id", label),
            "label": label,
            "xmage_option_metadata": engine,
        }
    }


def _cast(label: str, native: str = "native-1") -> dict[str, Any]:
    return _offer(label, "activated_ability", source_object_id=native, ability_type="spell")


def _priority_step(**value: Any) -> dict[str, Any]:
    return {
        "decision_family": "priority",
        "selection": {
            "selector_kind": "semantic_action",
            "semantic_value": {"action": "cast", "object": "obj:x", **value},
        },
    }


PLACED = {"obj:x": "native-1"}


# --------------------------------------------------------------------------- #
# Alternative costs and ambiguous casts
# --------------------------------------------------------------------------- #


def test_an_alternative_cost_selects_the_engine_offer_naming_it() -> None:
    legal = {
        "actions": [
            _cast("Vandalblast — Cast Vandalblast"),
            _cast("Vandalblast — Cast Vandalblast with overload"),
        ]
    }
    chosen = mr._scripted_priority_action(
        legal, _priority_step(alternative_cost="overload"), PLACED, {}
    )
    assert mr._label_of(chosen).endswith("with overload")


def test_several_casts_of_one_card_without_a_named_cost_fail_closed() -> None:
    """The old executor took the first spell offer; now the record must name it."""
    legal = {
        "actions": [
            _cast("Vandalblast — Cast Vandalblast"),
            _cast("Vandalblast — Cast Vandalblast with overload"),
        ]
    }
    with pytest.raises(mr.ml.MidgameLaneError, match="names none"):
        mr._scripted_priority_action(legal, _priority_step(), PLACED, {})


def test_an_alternative_cost_no_offer_or_two_offers_name_fails_closed() -> None:
    legal = {"actions": [_cast("Cast A with flashback"), _cast("Cast A with flashback, kicked")]}
    with pytest.raises(mr.ml.MidgameLaneError, match="alternative cost"):
        mr._scripted_priority_action(
            legal, _priority_step(alternative_cost="flashback"), PLACED, {}
        )
    legal = {"actions": [_cast("Cast A"), _cast("Cast A from exile")]}
    with pytest.raises(mr.ml.MidgameLaneError):
        mr._scripted_priority_action(legal, _priority_step(alternative_cost="evoke"), PLACED, {})


def test_a_single_cast_owes_the_named_alternative_cost_to_the_later_choice() -> None:
    step = _priority_step(alternative_cost="evoke")
    legal = {"actions": [_cast("Shriekmaw — Cast Shriekmaw")]}
    chosen = mr._scripted_priority_action(legal, step, PLACED, {})
    assert mr._pending_alternative_cost(step, chosen) == "evoke"
    assert mr._pending_alternative_cost(_priority_step(), chosen) is None
    named = _cast("Vandalblast — Cast Vandalblast with overload")
    assert mr._pending_alternative_cost(_priority_step(alternative_cost="overload"), named) is None


def test_the_cost_choice_answer_is_the_engine_offer_naming_the_alternative_cost() -> None:
    legal = {
        "actions": [
            _offer("Cast with Evoke alternative cost: {1}{B}", "choice", choice_key="1"),
            _offer("Cast with no alternative cost: {4}{B}", "choice", choice_key="2"),
        ]
    }
    chosen = mr._alternative_cost_answer(legal, "evoke")
    assert "Evoke" in mr._label_of(chosen)
    with pytest.raises(mr.ml.MidgameLaneError):
        mr._alternative_cost_answer(legal, "overload")
    doubled = {"actions": [*legal["actions"], legal["actions"][0]]}
    with pytest.raises(mr.ml.MidgameLaneError):
        mr._alternative_cost_answer(doubled, "evoke")


# --------------------------------------------------------------------------- #
# Timing
# --------------------------------------------------------------------------- #


def test_an_empty_stack_timing_waits_for_the_stack_to_resolve() -> None:
    step = _priority_step(timing="empty_stack")
    assert mr._timing_allows(step, {"pilot_state": {"stack": []}})
    assert not mr._timing_allows(step, {"pilot_state": {"stack": [{"name": "Mannequin"}]}})
    assert mr._timing_allows(_priority_step(), {"pilot_state": {"stack": [{"name": "x"}]}})


def test_an_unknown_timing_or_an_unexposed_stack_fails_closed() -> None:
    with pytest.raises(mr.ml.MidgameLaneError, match="not executed"):
        mr._timing_allows(_priority_step(timing="end_of_turn"), {"pilot_state": {"stack": []}})
    with pytest.raises(mr.ml.MidgameLaneError, match="exposes no stack"):
        mr._timing_allows(_priority_step(timing="empty_stack"), {})


# --------------------------------------------------------------------------- #
# Trigger order
# --------------------------------------------------------------------------- #


def _ability(source: str, text: str, ability_id: str = "ab-1", native: str = "src-1") -> dict:
    return _offer(
        f"{source} — {text}",
        "triggered_ability",
        source_name=source,
        ability_original_id=ability_id,
        source_object_id=native,
    )


def _order_step(value: list[str]) -> dict[str, Any]:
    return {
        "decision_family": "trigger_order",
        "selection": {"selector_kind": "order", "semantic_value": value},
    }


def test_identical_instances_listed_once_each_are_interchangeable() -> None:
    magecraft = _ability("Veyran, Voice of Duality", "Magecraft — gets +1/+1")
    legal = {"actions": [magecraft, dict(magecraft)]}
    order = ["trigger:Veyran,_Voice_of_Duality", "trigger:Veyran,_Voice_of_Duality"]
    answer = mr._scripted_answer(legal, _order_step(order), {}, mr.RowSpec())
    assert answer.key == "trigger:Veyran,_Voice_of_Duality"


@pytest.mark.parametrize(
    "actions,order",
    [
        # Listed once, offered twice: the record did not declare the multiplicity.
        (
            [_ability("Veyran", "Magecraft"), _ability("Veyran", "Magecraft")],
            ["trigger:Veyran", "trigger:Other"],
        ),
        # Two different abilities of one source are not interchangeable.
        (
            [_ability("Shriekmaw", "destroy", "ab-1"), _ability("Shriekmaw", "sacrifice", "ab-2")],
            ["trigger:Shriekmaw", "trigger:Shriekmaw"],
        ),
        # The same ability of two different permanents is not interchangeable.
        (
            [
                _ability("Soul Warden", "gain 1 life", native="a"),
                _ability("Soul Warden", "gain 1 life", native="b"),
            ],
            ["trigger:Soul_Warden", "trigger:Soul_Warden"],
        ),
    ],
    ids=["undeclared-multiplicity", "different-abilities", "different-sources"],
)
def test_ambiguous_trigger_instances_fail_closed(actions: list[dict], order: list[str]) -> None:
    with pytest.raises(mr.ml.MidgameLaneError, match="matched 2"):
        mr._scripted_answer({"actions": actions}, _order_step(order), {}, mr.RowSpec())


def test_a_rules_text_fragment_names_one_of_a_sources_abilities() -> None:
    legal = {
        "actions": [
            _ability("Shriekmaw", "When this permanent enters, its controller sacrifices it.", "a"),
            _ability("Shriekmaw", "When {this} enters, destroy target nonblack creature.", "b"),
        ]
    }
    order = ["trigger:Shriekmaw|destroy target", "trigger:Shriekmaw|sacrifices it"]
    answer = mr._scripted_answer(legal, _order_step(order), {}, mr.RowSpec())
    assert "destroy target" in mr._label_of(answer.action)
    with pytest.raises(mr.ml.MidgameLaneError):
        mr._scripted_answer(legal, _order_step(["trigger:Shriekmaw|exile"]), {}, mr.RowSpec())


# --------------------------------------------------------------------------- #
# Bound tokens and permanent-state checks
# --------------------------------------------------------------------------- #

TAPE: list[dict[str, Any]] = [
    {"sequence": 8, "type": "SPELL_CAST", "player_player": "P2", "source_object": "obj:bolt"},
    {
        "sequence": 9,
        "type": "TRIGGERED_ABILITY",
        "source_object": "obj:ishai",
        "target_name": "stack ability (Whenever an opponent casts a spell, put a counter)",
    },
    {
        "sequence": 10,
        "type": "COUNTER_ADDED",
        "target_object": "obj:ishai",
        "data": "+1/+1",
        "amount": 1,
    },
]


def test_an_event_binding_matches_fields_exactly_and_names_by_prefix() -> None:
    cast = mr.TerminalCheck("events", event_type="SPELL_CAST", where=(("player_player", "P2"),))
    assert mr.bound_token_evidence(cast, {}, TAPE, []) == {
        "binding": cast.describe(),
        "events": [8],
    }
    wrong = mr.TerminalCheck("events", event_type="SPELL_CAST", where=(("player_player", "P1"),))
    assert mr.bound_token_evidence(wrong, {}, TAPE, []) is None
    prefix = mr.TerminalCheck(
        "events",
        event_type="TRIGGERED_ABILITY",
        where=(("target_name~", "stack ability (Whenever an opponent"),),
    )
    assert mr.check_terminal(prefix, {}, TAPE, [])
    counter = (("target_object", "obj:ishai"), ("data", "+1/+1"))
    exactly_one = mr.TerminalCheck("events", value=1, event_type="COUNTER_ADDED", where=counter)
    assert mr.check_terminal(exactly_one, {}, TAPE, [])
    two = mr.TerminalCheck("events", value=2, event_type="COUNTER_ADDED", where=counter)
    assert not mr.check_terminal(two, {}, TAPE, [])
    none = mr.TerminalCheck(
        "events", value=0, event_type="DAMAGED_PERMANENT", where=(("source_object", "obj:bolt"),)
    )
    assert mr.check_terminal(none, {}, TAPE, [])


def test_a_frame_binding_needs_a_scripted_engine_offer_naming_it() -> None:
    label = "Vandalblast — Cast Vandalblast with overload"
    scripted = mr.Frame("priority", "P1", [label], label, scripted=True)
    unscripted = mr.Frame("priority", "P1", [label], label)
    check = mr.TerminalCheck("selected_frame", value="priority", label="with overload")
    assert mr.check_terminal(check, {}, [], [scripted])
    assert mr.bound_token_evidence(check, {}, [], [scripted])["decision_frames"] == [0]
    assert not mr.check_terminal(check, {}, [], [unscripted])
    offered_elsewhere = mr.Frame("priority", "P1", ["Cast Vandalblast"], label, scripted=True)
    assert not mr.check_terminal(check, {}, [], [offered_elsewhere])
    no_target = mr.TerminalCheck("no_frame", value="target")
    assert mr.check_terminal(no_target, {}, [], [scripted])
    assert not mr.check_terminal(no_target, {}, [], [mr.Frame("target", "P1", ["P2"])])


OBSERVATION = {
    "seats": [
        {
            "player_id": "P1",
            "battlefield": [
                {
                    "card_identity": "Devil Token",
                    "power": 1,
                    "toughness": 1,
                    "keywords": ["haste"],
                    "colors": ["red"],
                },
                {
                    "card_identity": "Devil Token",
                    "power": 1,
                    "toughness": 1,
                    "keywords": ["haste"],
                    "colors": ["red"],
                },
                {
                    "card_identity": "Ishai, Ojutai Dragonspeaker",
                    "power": 2,
                    "toughness": 2,
                    "counters": {"+1/+1": 1},
                    "colors": ["white", "blue"],
                },
            ],
        },
        {"player_id": "P2", "battlefield": []},
    ]
}


def _state(kind: str, identity: str, value: Any, principal: str = "P1") -> Any:
    return mr.TerminalCheck(kind, principal=principal, card_identity=identity, value=value)


def test_permanent_state_checks_hold_for_every_permanent_of_the_identity() -> None:
    assert mr.check_terminal(_state("power_toughness", "Devil Token", (1, 1)), OBSERVATION, [], [])
    assert mr.check_terminal(_state("keyword", "Devil Token", "haste"), OBSERVATION, [], [])
    assert mr.check_terminal(_state("colors", "Devil Token", ("red",)), OBSERVATION, [], [])
    ishai = "Ishai, Ojutai Dragonspeaker"
    assert mr.check_terminal(_state("counters", ishai, (("+1/+1", 1),)), OBSERVATION, [], [])
    assert mr.check_terminal(_state("colors", ishai, ("blue", "white")), OBSERVATION, [], [])
    assert not mr.check_terminal(_state("counters", ishai, (("+1/+1", 2),)), OBSERVATION, [], [])
    assert not mr.check_terminal(_state("keyword", ishai, "flying"), OBSERVATION, [], [])
    one_differs = {
        "seats": [
            {
                "player_id": "P1",
                "battlefield": [
                    *OBSERVATION["seats"][0]["battlefield"][:1],
                    {"card_identity": "Devil Token", "power": 2, "toughness": 1},
                ],
            }
        ]
    }
    assert not mr.check_terminal(
        _state("power_toughness", "Devil Token", (1, 1)), one_differs, [], []
    )
    assert not mr.check_terminal(_state("keyword", "Devil Token", "haste"), one_differs, [], [])


def test_a_permanent_check_on_an_absent_identity_never_holds() -> None:
    for kind, value in (
        ("power_toughness", (1, 1)),
        ("counters", ()),
        ("keyword", "haste"),
        ("colors", ()),
    ):
        assert not mr.check_terminal(_state(kind, "Grizzly Bears", value), OBSERVATION, [], [])


def test_not_on_battlefield_needs_the_seat_and_no_permanent_of_the_identity() -> None:
    assert mr.check_terminal(
        _state("not_on_battlefield", "Sol Ring", None, "P2"), OBSERVATION, [], []
    )
    assert not mr.check_terminal(
        _state("not_on_battlefield", "Devil Token", None), OBSERVATION, [], []
    )
    # An unobserved seat is no evidence of absence.
    assert not mr.check_terminal(
        _state("not_on_battlefield", "Sol Ring", None, "P3"), OBSERVATION, [], []
    )


def test_a_bound_token_takes_precedence_and_an_unbound_unknown_token_stays_unobserved() -> None:
    assert mr.verify_token("spell_cast:P2", TAPE, [], set()) is None
    binding = mr.TerminalCheck("events", event_type="SPELL_CAST", where=(("player_player", "P2"),))
    assert mr.bound_token_evidence(binding, {}, TAPE, []) is not None


# --------------------------------------------------------------------------- #
# Phase 2c: card parts, activations, owed cost choices, empty selections
# --------------------------------------------------------------------------- #


def _part(label: str, source: str, parent: str | None, name: str) -> dict[str, Any]:
    engine: dict[str, Any] = {
        "source_object_id": source,
        "ability_type": "spell",
        "source_name": name,
    }
    if parent is not None:
        engine["source_parent_object_id"] = parent
    return _offer(label, "activated_ability", **engine)


SPLIT = {
    "actions": [
        _part("Tear — Cast Tear", "half-tear", "native-1", "Tear"),
        _part("Wear — Cast Wear", "half-wear", "native-1", "Wear"),
        _part("Wear // Tear — Cast fused Wear // Tear", "native-1", None, "Wear // Tear"),
        _part("Other — Cast Tear", "half-other", "native-9", "Tear"),
    ]
}


def test_a_split_half_is_the_placed_cards_part_named_by_the_half() -> None:
    step = _priority_step(action="cast_split_half", half="Tear")
    chosen = mr._scripted_priority_action(SPLIT, step, PLACED, {})
    assert mr._engine_meta(chosen)["source_object_id"] == "half-tear"
    with pytest.raises(mr.ml.MidgameLaneError, match="matched 0"):
        mr._scripted_priority_action(
            SPLIT, _priority_step(action="cast_split_half", half="X"), PLACED, {}
        )


def test_the_fused_cast_is_the_engine_offer_naming_the_fused_cast() -> None:
    chosen = mr._scripted_priority_action(SPLIT, _priority_step(action="cast_fused"), PLACED, {})
    assert mr._label_of(chosen).endswith("Cast fused Wear // Tear")


def test_a_plain_cast_of_a_split_card_names_no_part_and_fails_closed() -> None:
    with pytest.raises(mr.ml.MidgameLaneError, match="names none"):
        mr._scripted_priority_action(SPLIT, _priority_step(), PLACED, {})


def _ability_offer(label: str, mana: bool, native: str = "native-1") -> dict[str, Any]:
    return _offer(
        label,
        "mana_ability" if mana else "activated_ability",
        source_object_id=native,
        ability_type="activated_mana" if mana else "activated_nonmana",
        mana_ability=mana,
    )


def _activation(**value: Any) -> dict[str, Any]:
    return {
        "decision_family": "priority",
        "selection": {
            "selector_kind": "semantic_action",
            "semantic_value": {"source": "obj:x", **value},
        },
    }


def test_an_activation_is_the_sources_ability_named_by_its_rules_text() -> None:
    legal = {
        "actions": [
            _ability_offer("Jeska — +1: Add {R}{R}.", False),
            _ability_offer("Jeska — 0: Choose target creature.", False),
            _ability_offer("Other — 0: Choose", False, native="native-2"),
            _cast("Jeska — Cast Jeska"),
        ]
    }
    chosen = mr._scripted_priority_action(
        legal, _activation(action="activate", ability="0:"), PLACED, {}
    )
    assert "0: Choose target" in mr._label_of(chosen)
    with pytest.raises(mr.ml.MidgameLaneError, match="matched 2"):
        mr._scripted_priority_action(legal, _activation(action="activate"), PLACED, {})


def test_activate_mana_requires_a_mana_ability() -> None:
    legal = {"actions": [_ability_offer("Altar — Sacrifice a creature: Add {C}{C}.", True)]}
    assert mr._scripted_priority_action(legal, _activation(action="activate_mana"), PLACED, {})
    assert mr._scripted_priority_action(legal, _activation(action="activate"), PLACED, {})
    nonmana = {"actions": [_ability_offer("Spy — {T}: Look", False)]}
    with pytest.raises(mr.ml.MidgameLaneError):
        mr._scripted_priority_action(nonmana, _activation(action="activate_mana"), PLACED, {})
    with pytest.raises(mr.ml.MidgameLaneError, match="was not placed"):
        mr._scripted_priority_action(
            nonmana, _activation(action="activate", source="obj:y"), PLACED, {}
        )


def test_owed_cost_choices_are_answered_from_the_engines_own_offers() -> None:
    step = _activation(action="activate", sacrifice_cost="obj:x", color="R")
    assert mr._pending_cost_choices(step) == [("sacrifice", "obj:x"), ("color", "R")]
    bears = _offer("Grizzly Bears", "choice", object_id="native-1")
    legal = {"actions": [bears, _offer("Hill Giant", "choice", object_id="native-2")]}
    assert mr._cost_choice_answer(legal, "sacrifice", "obj:x", PLACED) is bears
    colors = {"actions": [_offer("Red", "choice"), _offer("Green", "choice")]}
    assert mr._label_of(mr._cost_choice_answer(colors, "color", "R", PLACED)) == "Red"
    with pytest.raises(mr.ml.MidgameLaneError):
        mr._cost_choice_answer(colors, "color", "U", PLACED)


def _multi(minimum: int) -> dict[str, Any]:
    return {
        "decision": {"minimum_selections": minimum, "maximum_selections": 1},
        "actions": [_offer("Mountain", "target", object_id="native-1")],
    }


def test_an_empty_selection_needs_a_frame_whose_minimum_is_zero() -> None:
    step = {
        "decision_family": "target",
        "selection": {"selector_kind": "semantic_objects", "semantic_value": []},
    }
    answer = mr._scripted_answer(_multi(0), step, PLACED, mr.RowSpec())
    assert answer.action is None and answer.key == "none"
    with pytest.raises(mr.ml.MidgameLaneError, match="requires"):
        mr._scripted_answer(_multi(1), step, PLACED, mr.RowSpec())


def test_ordering_frame_count_pool_and_hand_checks() -> None:
    tape = [
        {"sequence": 1, "type": "SACRIFICED_PERMANENT", "source_object": "obj:b"},
        {"sequence": 2, "type": "SACRIFICED_PERMANENT", "source_object": "obj:b"},
        {"sequence": 3, "type": "ZONE_CHANGE", "source_object": "obj:b", "to": "GRAVEYARD"},
        {"sequence": 4, "type": "SACRIFICED_PERMANENT", "source_object": "obj:late"},
    ]
    precede = mr.TerminalCheck(
        "events_precede",
        event_type="SACRIFICED_PERMANENT",
        where=(("source_object", "obj:b"),),
        value=("ZONE_CHANGE", (("to", "GRAVEYARD"),)),
    )
    assert mr.check_terminal(precede, {}, tape, [])
    late = mr.TerminalCheck(
        "events_precede",
        event_type="SACRIFICED_PERMANENT",
        where=(),
        value=("ZONE_CHANGE", (("to", "GRAVEYARD"),)),
    )
    assert not mr.check_terminal(late, {}, tape, [])
    scry = mr.Frame("target", "P1", ["Mountain"], prompt="Select up to one card (Scry)")
    once = mr.TerminalCheck("frame_count", value=("target", 1), principal="P1", label="(Scry)")
    assert mr.check_terminal(once, {}, [], [scry])
    assert not mr.check_terminal(once, {}, [], [scry, scry])
    spend = mr.Frame(
        "mana_payment",
        "P1",
        ["Spend red mana from pool"],
        "Spend red mana from pool",
        selected_option_type="mana_pool",
    )
    assert mr.check_terminal(mr.TerminalCheck("pool_spend", value="red"), {}, [], [spend])
    assert not mr.check_terminal(mr.TerminalCheck("pool_spend", value="blue"), {}, [], [spend])
    observation = {
        "seats": [
            {
                "player_id": "P1",
                "hand_count": 17,
                "graveyard": ["Sol Ring"],
                "battlefield": [
                    {"card_identity": "Island", "tapped": False},
                    {"card_identity": "Island", "tapped": True},
                ],
            }
        ]
    }
    hand = mr.TerminalCheck("hand_count_min", principal="P1", value=8)
    assert mr.check_terminal(hand, observation, [], [])
    grave = mr.TerminalCheck("in_graveyard", principal="P1", card_identity="Sol Ring")
    assert mr.check_terminal(grave, observation, [], [])
    untapped = _state("untapped_count", "Island", 1)
    assert mr.check_terminal(untapped, observation, [], [])
    assert not mr.check_terminal(_state("untapped_count", "Island", 2), observation, [], [])
    discard = mr.Frame("choose_object", "P2", ["Mountain"], prompt="Select a card to discard")
    no_p1_discard = mr.TerminalCheck(
        "no_frame", value="choose_object", principal="P1", label="discard"
    )
    assert mr.check_terminal(no_p1_discard, {}, [], [discard])
    assert not mr.check_terminal(
        mr.TerminalCheck("no_frame", value="choose_object", label="discard"), {}, [], [discard]
    )


def test_a_token_bound_to_several_checks_needs_every_one() -> None:
    cast = mr.TerminalCheck("events", event_type="SPELL_CAST", where=(("player_player", "P2"),))
    absent = mr.TerminalCheck("events", event_type="DAMAGED_PLAYER")
    both = mr.bound_token_evidence((cast, cast), {}, TAPE, [])
    assert both is not None and len(both["parts"]) == 2
    assert mr.bound_token_evidence((cast, absent), {}, TAPE, []) is None


_DIES = {
    "trigger": "DiesSourceTriggeredAbility",
    "effects": ["DamageTargetEffect"],
    "rule": "When this creature dies, it deals 1 damage to any target.",
}


def _devil(**overrides: Any) -> dict[str, Any]:
    devil = {
        "card_identity": "Devil Token",
        "power": 1,
        "toughness": 1,
        "token": True,
        "keywords": ["haste"],
        "colors": ["red"],
        "triggered_abilities": [dict(_DIES)],
    }
    devil.update(overrides)
    return {key: value for key, value in devil.items() if value is not None}


def _p1(*battlefield: dict[str, Any]) -> dict[str, Any]:
    return {"seats": [{"player_id": "P1", "battlefield": list(battlefield)}]}


DIES_DAMAGE = ("DiesSourceTriggeredAbility", "DamageTargetEffect")


def test_a_triggered_ability_check_reads_the_engine_classes_on_every_permanent() -> None:
    three = _p1(_devil(), _devil(), _devil())
    assert mr.check_terminal(_state("triggered_ability", "Devil Token", DIES_DAMAGE), three, [], [])
    assert mr.check_terminal(_state("token_count", "Devil Token", 3), three, [], [])
    # Wrong reason: a hasty red 1/1 token without the death trigger.
    missing = _p1(_devil(), _devil(), _devil(triggered_abilities=None))
    assert not mr.check_terminal(
        _state("triggered_ability", "Devil Token", DIES_DAMAGE), missing, [], []
    )
    # Wrong reason: the right event with another effect, or the right effect on
    # another event; the rules text alone never satisfies the check.
    other_effect = _p1(_devil(triggered_abilities=[dict(_DIES, effects=["GainLifeEffect"])]))
    other_event = _p1(
        _devil(triggered_abilities=[dict(_DIES, trigger="EntersBattlefieldTriggeredAbility")])
    )
    text_only = _p1(_devil(triggered_abilities=[{"rule": _DIES["rule"]}]))
    for observation in (other_effect, other_event, text_only):
        assert not mr.check_terminal(
            _state("triggered_ability", "Devil Token", DIES_DAMAGE), observation, [], []
        )
    assert not mr.check_terminal(
        _state("triggered_ability", "Grizzly Bears", DIES_DAMAGE), three, [], []
    )


def test_a_token_count_counts_only_engine_tokens_of_the_identity() -> None:
    assert not mr.check_terminal(
        _state("token_count", "Devil Token", 3), _p1(_devil(), _devil()), [], []
    )
    four = _p1(_devil(), _devil(), _devil(), _devil())
    assert not mr.check_terminal(_state("token_count", "Devil Token", 3), four, [], [])
    # A same-named permanent that is not an engine token never stands in for one.
    card = _p1(_devil(), _devil(), _devil(token=None))
    assert not mr.check_terminal(_state("token_count", "Devil Token", 3), card, [], [])
    assert not mr.check_terminal(_state("token_count", "Devil Token", 0), {"seats": []}, [], [])


# --------------------------------------------------------------------------- #
# Delve, library objects and ordered object sets (CARD_12)
# --------------------------------------------------------------------------- #


def _graveyard_card(native: str, ability_type: str = "special_mana_payment") -> dict[str, Any]:
    offer = _offer("Mountain", "choice", object_id=native, name="Mountain", zone="graveyard")
    offer["metadata"]["source_object"] = {"ability_type": ability_type}
    return offer


def test_delve_answers_the_exact_graveyard_card_the_record_names() -> None:
    legal = {"actions": [_graveyard_card("gy-0"), _graveyard_card("gy-1")]}
    assert mr._delve_card_answer(legal, "gy-1") is legal["actions"][1]
    with pytest.raises(mr.ml.MidgameLaneError):
        mr._delve_card_answer(legal, "gy-9")
    # Wrong reason: the same object offered by a frame that is not the delve
    # source's own payment choice.
    other = {"actions": [_graveyard_card("gy-1", ability_type="activated")]}
    with pytest.raises(mr.ml.MidgameLaneError):
        mr._delve_card_answer(other, "gy-1")
    delve = _offer("Dig Through Time — Exile a card from your graveyard: Delve", "special")
    assert mr._delve_offer({"actions": [_offer("Island — {T}: Add {U}.", "mana"), delve]}) is delve
    with pytest.raises(mr.ml.MidgameLaneError):
        mr._delve_offer({"actions": [_offer("Island — {T}: Add {U}.", "mana")]})


def _library_card(native: str, index: int, name: str = "Mountain") -> dict[str, Any]:
    return _offer(name, "target", object_id=native, name=name, zone="library", zone_index=index)


LIBRARY_RECORD = {
    "semantic_objects": [
        {
            "semantic_id": "obj:lib1",
            "zone": "library",
            "zone_position": 0,
            "card_identity": "Mountain",
        },
        {
            "semantic_id": "obj:lib2",
            "zone": "library",
            "zone_position": 1,
            "card_identity": "Mountain",
        },
        {"semantic_id": "obj:hand", "zone": "hand", "card_identity": "Island"},
    ]
}


def test_library_objects_bind_to_engine_ids_at_first_sight_only_while_unchanged() -> None:
    keyed = mr.library_positions(LIBRARY_RECORD, {})
    assert set(keyed) == {"obj:lib1", "obj:lib2"}
    legal = {"actions": [_library_card("n-a", 0), _library_card("n-b", 1)]}
    assert mr._bind_library_objects(legal, keyed, []) == {"obj:lib1": "n-a", "obj:lib2": "n-b"}
    # After any library change the positions are no longer checkpoint positions:
    # nothing binds, and a later selection of the object fails closed.
    moved = [{"type": "ZONE_CHANGE", "from": "LIBRARY", "to": "HAND"}]
    assert mr._bind_library_objects(legal, keyed, moved) == {}
    shuffled = [{"type": "LIBRARY_SHUFFLED"}]
    assert mr._bind_library_objects(legal, keyed, shuffled) == {}
    # A different card at the position never binds.
    wrong = {"actions": [_library_card("n-a", 0, name="Island")]}
    assert mr._bind_library_objects(wrong, keyed, []) == {}
    # An object the restoration placed is never re-keyed by position.
    assert mr.library_positions(LIBRARY_RECORD, {"obj:lib1": "placed"}) == {
        "obj:lib2": keyed["obj:lib2"]
    }


def test_an_ordered_object_set_names_each_object_by_engine_identity() -> None:
    step = {
        "decision_family": "choose_object",
        "selection": {"selector_kind": "order", "semantic_value": ["obj:a", "obj:b"]},
    }
    legal = {"actions": [_library_card("n-b", 0), _library_card("n-a", 1)]}
    placed = {"obj:a": "n-a", "obj:b": "n-b"}
    first = mr._scripted_answer(legal, step, placed, mr.RowSpec(), 0)
    assert first.action is legal["actions"][1] and first.key == "obj:a"
    second = mr._scripted_answer(legal, step, placed, mr.RowSpec(), 1)
    assert second.action is legal["actions"][0] and second.key == "obj:b"
    with pytest.raises(mr.ml.MidgameLaneError):
        mr._scripted_answer({"actions": [legal["actions"][0]]}, step, placed, mr.RowSpec(), 0)


def _frame(decision_class: str, prompt: str, labels: int, key: str | None = None) -> mr.Frame:
    return mr.Frame(
        decision_class, "P1", ["Mountain"] * labels, scripted=True, selected_key=key, prompt=prompt
    )


def test_frame_evidence_checks_read_scripted_engine_frames() -> None:
    look = mr.TerminalCheck("frame_offers", value=("target", 7), label="into your hand")
    assert mr.check_terminal(look, {}, [], [_frame("target", "Select (to put into your hand)", 7)])
    assert not mr.check_terminal(look, {}, [], [_frame("target", "Select (into your hand)", 6)])
    unscripted = _frame("target", "into your hand", 7)
    unscripted.scripted = False
    assert not mr.check_terminal(look, {}, [], [unscripted])
    order = mr.TerminalCheck(
        "selected_sequence", value=("choose_object", ("obj:3", "obj:4")), label="BOTTOM"
    )
    in_order = [
        _frame("choose_object", "BOTTOM", 2, "obj:3"),
        _frame("choose_object", "BOTTOM", 1, "obj:4"),
    ]
    assert mr.check_terminal(order, {}, [], in_order)
    assert not mr.check_terminal(order, {}, [], list(reversed(in_order)))
    assert not mr.check_terminal(order, {}, [], in_order[:1])


def test_a_graveyard_mana_value_is_the_engine_characteristic_of_a_card_present() -> None:
    check = mr.TerminalCheck(
        "graveyard_mana_value", principal="P1", card_identity="Dig Through Time", value=8
    )
    seat = {
        "player_id": "P1",
        "graveyard": ["Dig Through Time"],
        "graveyard_mana_values": {"Dig Through Time": 8},
    }
    assert mr.check_terminal(check, {"seats": [seat]}, [], [])
    assert not mr.check_terminal(
        check, {"seats": [{**seat, "graveyard_mana_values": {"Dig Through Time": 2}}]}, [], []
    )
    # The value alone, without the card in the graveyard, proves nothing.
    assert not mr.check_terminal(check, {"seats": [{**seat, "graveyard": []}]}, [], [])
    assert not mr.check_terminal(check, {"seats": [{**seat, "graveyard_mana_values": {}}]}, [], [])


def test_battlefield_exact_compares_the_whole_battlefield_as_a_multiset() -> None:
    check = mr.TerminalCheck(
        "battlefield_exact", principal="P1", value=("Branch of Boseiju", "Forest", "Forest")
    )
    seat = {
        "player_id": "P1",
        "battlefield": [
            {"card_identity": "Forest"},
            {"card_identity": "Branch of Boseiju"},
            {"card_identity": "Forest"},
        ],
    }
    assert mr.check_terminal(check, {"seats": [seat]}, [], [])
    # One land more (a played land would raise the count) or one fewer fails.
    more = {**seat, "battlefield": [*seat["battlefield"], {"card_identity": "Forest"}]}
    assert not mr.check_terminal(check, {"seats": [more]}, [], [])
    assert not mr.check_terminal(
        check, {"seats": [{**seat, "battlefield": seat["battlefield"][:2]}]}, [], []
    )
    assert not mr.check_terminal(check, {"seats": []}, [], [])
