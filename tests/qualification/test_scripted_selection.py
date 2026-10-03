"""#459 phase 2: the shared, provider-neutral scripted selector fails closed."""

from __future__ import annotations

import copy

import pytest

from commander_lab.qualification.current_boundary import scripted_selection as ss

FALLBACKS = sorted(ss.FORBIDDEN_FALLBACKS)


def _step(family: str, kind: str, value) -> dict:
    return {
        "actor": "P1",
        "decision_family": family,
        "forbidden_fallbacks": FALLBACKS,
        "selection": {
            "matches_only_provider_offered_legal_options": True,
            "on_multiple_match": "FAIL_CLOSED",
            "on_zero_match": "FAIL_CLOSED",
            "selector_kind": kind,
            "semantic_value": value,
        },
    }


# The live Forge frames observed for MICRO_TARGETS on bridge 20e3e1f7 (labels and
# references verbatim; option ids shortened).
PRIORITY = {
    "decision": {"kind": "PRIORITY", "actor": "p1", "revision": 18},
    "actions": [
        {
            "action_id": "a1",
            "action_type": "pass_priority",
            "source_object_id": None,
            "metadata": {"label": "Pass priority"},
        },
        {
            "action_id": "a2",
            "action_type": "cast_spell",
            "source_object_id": "Lightning Bolt",
            "metadata": {"label": "Lightning Bolt [cast_spell] ({R})"},
        },
        {
            "action_id": "a3",
            "action_type": "cast_spell",
            "source_object_id": "Rograkh, Son of Rohgahh",
            "metadata": {"label": "Rograkh, Son of Rohgahh [cast_spell] ({0})"},
        },
        {
            "action_id": "a4",
            "action_type": "play_land",
            "source_object_id": "Mountain",
            "metadata": {"label": "Mountain [play_land] (no cost)"},
        },
    ],
}
TARGETS = {
    "decision": {"kind": "TARGET_SELECTION", "actor": "p1", "revision": 19},
    "actions": [
        {
            "action_id": f"t{seat}",
            "action_type": "target",
            "source_object_id": None,
            "metadata": {
                "label": f"Target [player p{seat};]",
                "object_refs": [{"kind": "player", "player_id": f"p{seat}"}],
            },
        }
        for seat in range(1, 5)
    ]
    + [
        {
            "action_id": f"b{seat}",
            "action_type": "target",
            "source_object_id": None,
            "metadata": {
                "label": "Target [Grizzly Bears;]",
                "object_refs": [
                    {
                        "kind": "card",
                        "card_id": 404 + seat,
                        "name": "Grizzly Bears",
                        "controller": f"p{seat}",
                        "zone": "Battlefield",
                    }
                ],
            },
        }
        for seat in range(1, 4)
    ],
}
MANA = {
    "decision": {"kind": "MANA_PAYMENT", "actor": "p1", "revision": 20},
    "actions": [
        {
            "action_id": "m1",
            "action_type": "tap_mana_source",
            "source_object_id": "Mountain",
            "metadata": {"label": "Tap Mountain for mana"},
        },
        {
            "action_id": "m2",
            "action_type": "tap_mana_source",
            "source_object_id": None,
            "metadata": {"label": "Decline to tap (leave cost unpaid)"},
        },
    ],
}
OBJECTS = {
    "obj:micro-bolt": ss.SemanticObject("obj:micro-bolt", "Lightning Bolt", "p1", "hand"),
    "obj:p2-bears": ss.SemanticObject("obj:p2-bears", "Grizzly Bears", "p2", "battlefield"),
    "obj:p4-bears": ss.SemanticObject("obj:p4-bears", "Grizzly Bears", "p4", "battlefield"),
    "obj:mountain": ss.SemanticObject("obj:mountain", "Mountain", "p1", "battlefield"),
}


def _select(step, frame):
    decision_class, options = ss.forge_options(frame)
    return ss.select(step, decision_class, options, OBJECTS)


def test_cast_target_and_payment_select_the_named_options() -> None:
    assert (
        _select(
            _step("priority", "semantic_action", {"action": "cast", "object": "obj:micro-bolt"}),
            PRIORITY,
        ).option_id
        == "a2"
    )
    assert _select(_step("target", "semantic_player", "P2"), TARGETS).option_id == "t2"
    assert _select(_step("target", "semantic_object", "obj:p2-bears"), TARGETS).option_id == "b2"
    _, options = ss.forge_options(MANA)
    chosen, source = ss.select_mana_source(options, [OBJECTS["obj:mountain"]], set())
    assert chosen.option_id == "m1" and source.semantic_id == "obj:mountain"


def test_zero_match_fails_closed() -> None:
    with pytest.raises(ss.SelectionFailure, match="zero_match"):
        _select(_step("target", "semantic_object", "obj:p4-bears"), TARGETS)
    _, options = ss.forge_options(MANA)
    with pytest.raises(ss.SelectionFailure, match="zero_match"):
        ss.select_mana_source(options, [OBJECTS["obj:mountain"]], {"obj:mountain"})


def test_multiple_match_fails_closed_instead_of_first_option() -> None:
    frame = copy.deepcopy(PRIORITY)
    frame["actions"].append({**frame["actions"][1], "action_id": "a5"})
    with pytest.raises(ss.SelectionFailure, match="multiple_match"):
        _select(
            _step("priority", "semantic_action", {"action": "cast", "object": "obj:micro-bolt"}),
            frame,
        )


def test_decline_to_pay_is_never_selected() -> None:
    frame = copy.deepcopy(MANA)
    frame["actions"] = [frame["actions"][1]]
    _, options = ss.forge_options(frame)
    with pytest.raises(ss.SelectionFailure, match="zero_match"):
        ss.select_mana_source(options, [OBJECTS["obj:mountain"]], set())


def test_booleans_map_only_from_the_bridge_suffix() -> None:
    frame = {
        "decision": {"kind": "REPLACEMENT_CONFIRM", "actor": "p1"},
        "actions": [
            {
                "action_id": "y",
                "action_type": "replacement_confirm",
                "metadata": {"label": "Move to command zone? [Yes]"},
            },
            {
                "action_id": "n",
                "action_type": "replacement_confirm",
                "metadata": {"label": "Move to command zone? [No]"},
            },
        ],
    }
    assert _select(_step("replacement_effect", "boolean", True), frame).option_id == "y"
    assert _select(_step("choice", "boolean", False), frame).option_id == "n"
    unlabeled = copy.deepcopy(frame)
    for action in unlabeled["actions"]:
        action["metadata"]["label"] = "Move to command zone?"
    with pytest.raises(ss.SelectionFailure, match="zero_match"):
        _select(_step("choice", "boolean", True), unlabeled)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda s: s["selection"].update(on_zero_match="FIRST"),
        lambda s: s["selection"].update(on_multiple_match="FIRST"),
        lambda s: s["selection"].update(matches_only_provider_offered_legal_options=False),
        lambda s: s.update(forbidden_fallbacks=["first_option"]),
        lambda s: s["selection"].update(selector_kind="semantic_mode_key"),
    ],
)
def test_a_step_without_the_fail_closed_contract_is_refused(mutate) -> None:
    step = _step("target", "semantic_player", "P2")
    mutate(step)
    with pytest.raises(ss.SelectionFailure):
        _select(step, TARGETS)


def test_a_frame_of_another_class_is_refused() -> None:
    with pytest.raises(ss.SelectionFailure, match="decision_class_mismatch"):
        _select(_step("target", "semantic_player", "P2"), PRIORITY)


def test_an_unmapped_forge_frame_kind_is_refused() -> None:
    with pytest.raises(ss.SelectionFailure, match="frame_kind_not_mapped"):
        ss.forge_options({"decision": {"kind": "COMBAT_DECLARE_ATTACKERS"}, "actions": []})


def test_semantic_objects_come_from_the_record() -> None:
    record = {
        "semantic_objects": [
            {
                "semantic_id": "obj:x",
                "card_identity": "Doom Blade",
                "controller": "P2",
                "zone": "stack",
            },
        ]
    }
    assert ss.semantic_objects(record)["obj:x"] == ss.SemanticObject(
        "obj:x", "Doom Blade", "p2", "stack"
    )
