"""SLOT-03 option (c): the decision-identity shim is protocol translation only.

`decision_identity_params` maps each provider's native decision identity into
the submission parameters (XMage: ``decision_id`` + pass ``action_id``; Forge:
``revision``; both: ``actor_id``). The condition the Coordinator option (c)
attaches is a provenance test: every submitted identity value must byte-match a
value in the frame the provider just offered. The shim may translate field
names; it may never invent, derive, normalise or carry over an identity.
"""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest

from commander_lab.qualification.current_boundary.game_driver import (
    DECISION_IDENTITY_SHAPES,
    decision_identity_params,
)

XMAGE_FRAME: dict[str, Any] = {
    "decision": {
        "decision_id": "9f" * 32,
        "actor": "p3",
        "decision_class": "priority",
    },
    "actions": [
        {"action_id": "opt-cast-1", "action_type": "cast_spell"},
        {"action_id": "opt-pass-7", "action_type": "pass_priority"},
    ],
}

FORGE_FRAME: dict[str, Any] = {
    "decision": {"revision": 918273645546372819, "actor": "p2", "decision_class": "priority"},
    "actions": [{"action_id": "a-1", "action_type": "pass_priority"}],
}


def _frame_values(frame: dict[str, Any]) -> list[Any]:
    values: list[Any] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        else:
            values.append(node)

    walk(frame)
    return values


@pytest.mark.parametrize(("candidate", "frame"), [("xmage", XMAGE_FRAME), ("forge", FORGE_FRAME)])
def test_every_submitted_identity_byte_matches_the_offering_frame(
    candidate: str, frame: dict[str, Any]
) -> None:
    params = decision_identity_params(candidate, frame)
    offered = _frame_values(frame)
    shape = DECISION_IDENTITY_SHAPES[candidate]
    assert set(params) == {shape["field"], *shape["pass_extra"]}
    for key, value in params.items():
        assert any(
            type(value) is type(candidate_value) and value == candidate_value
            for candidate_value in offered
        ), f"{candidate}.{key}={value!r} is not a value the provider offered"


def test_xmage_pass_identity_is_the_offered_pass_option_not_the_first_option() -> None:
    params = decision_identity_params("xmage", XMAGE_FRAME)
    assert params["action_id"] == "opt-pass-7"
    assert params["decision_id"] == XMAGE_FRAME["decision"]["decision_id"]
    assert params["actor_id"] == "p3"


def test_forge_revision_keeps_its_native_type_and_value() -> None:
    params = decision_identity_params("forge", FORGE_FRAME)
    assert params["revision"] == 918273645546372819
    assert type(params["revision"]) is int
    # The value survives the JSON transport byte-for-byte.
    assert json.loads(json.dumps(params))["revision"] == 918273645546372819


@pytest.mark.parametrize(("candidate", "frame"), [("xmage", XMAGE_FRAME), ("forge", FORGE_FRAME)])
def test_identity_follows_each_new_frame_and_is_never_carried_over(
    candidate: str, frame: dict[str, Any]
) -> None:
    first = decision_identity_params(candidate, frame)
    later = copy.deepcopy(frame)
    field = DECISION_IDENTITY_SHAPES[candidate]["field"]
    later["decision"][field] = "ab" * 32 if candidate == "xmage" else frame["decision"][field] + 1
    second = decision_identity_params(candidate, later)
    assert second[field] == later["decision"][field]
    assert second[field] != first[field]


def test_the_shim_does_not_mutate_the_offering_frame() -> None:
    frame = copy.deepcopy(XMAGE_FRAME)
    decision_identity_params("xmage", frame)
    assert frame == XMAGE_FRAME


def test_a_frame_without_the_native_identity_is_not_given_one() -> None:
    # Missing identity is never synthesised: the parameter is absent/None and
    # the provider's own stale-decision check rejects the submission.
    frame = copy.deepcopy(XMAGE_FRAME)
    del frame["decision"]["decision_id"]
    frame["actions"] = [a for a in frame["actions"] if a["action_type"] != "pass_priority"]
    params = decision_identity_params("xmage", frame)
    assert params.get("decision_id") is None
    assert "action_id" not in params
