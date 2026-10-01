from __future__ import annotations

import pytest

from commander_lab.qualification.current_boundary.game_driver import (
    DecisionUnsatisfied,
    select_cost_order_action,
)


def _action(
    action_id: str | None,
    action_type: str,
    indices: object = None,
) -> dict[str, object]:
    metadata: dict[str, object] = {}
    if indices is not None:
        metadata["cost_order_indices"] = indices
    action: dict[str, object] = {
        "action_type": action_type,
        "metadata": metadata,
    }
    if action_id is not None:
        action["action_id"] = action_id
    return action


def test_complete_cost_order_selects_native_declaration_order_not_offer_position() -> None:
    actions = [
        _action("reverse", "cost_order", [2, 1, 0]),
        _action("mixed", "cost_order", [1, 0, 2]),
        _action("native", "cost_order", [0, 1, 2]),
    ]

    chosen = select_cost_order_action(actions)

    assert chosen is actions[2]
    assert chosen["action_id"] == "native"


def test_complete_cost_order_is_stable_when_provider_reorders_options() -> None:
    native = _action("native", "cost_order", [0, 1, 2])
    reverse = _action("reverse", "cost_order", [2, 1, 0])

    assert select_cost_order_action([native, reverse]) is native
    assert select_cost_order_action([reverse, native]) is native


def test_iterative_cost_order_selects_lowest_remaining_native_index() -> None:
    actions = [
        _action("part-4", "cost_order_next", [4]),
        _action("part-1", "cost_order_next", [1]),
        _action("part-3", "cost_order_next", [3]),
    ]

    chosen = select_cost_order_action(actions)

    assert chosen["action_id"] == "part-1"


@pytest.mark.parametrize(
    "actions",
    [
        [],
        [_action("x", "cost_order", None)],
        [_action("x", "cost_order", [0, True])],
        [_action("x", "cost_order", [0, -1])],
        [_action("x", "cost_order", [0, 0])],
        [_action("x", "cost_order", [0])],
        [
            _action("a", "cost_order", [0, 1]),
            _action("b", "cost_order", [0, 2]),
        ],
        [
            _action("a", "cost_order_next", [2]),
            _action("b", "cost_order_next", [2]),
        ],
        [_action("x", "choose_mode", [0, 1])],
        [
            _action("a", "cost_order", [0, 1]),
            _action("b", "cost_order_next", [0]),
        ],
    ],
)
def test_malformed_or_non_cost_order_domains_fail_closed(
    actions: list[dict[str, object]],
) -> None:
    with pytest.raises(DecisionUnsatisfied):
        select_cost_order_action(actions)  # type: ignore[arg-type]


def test_ambiguous_native_order_fails_closed() -> None:
    actions = [
        _action("native-a", "cost_order", [0, 1]),
        _action("native-b", "cost_order", [0, 1]),
    ]

    with pytest.raises(DecisionUnsatisfied, match="identify one legal option"):
        select_cost_order_action(actions)  # type: ignore[arg-type]


def test_chosen_cost_order_requires_engine_action_identity() -> None:
    actions = [
        _action(None, "cost_order", [0, 1]),
        _action("reverse", "cost_order", [1, 0]),
    ]

    with pytest.raises(DecisionUnsatisfied, match="no action_id"):
        select_cost_order_action(actions)  # type: ignore[arg-type]
