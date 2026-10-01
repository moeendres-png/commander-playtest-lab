from __future__ import annotations

import pytest

from commander_lab.qualification.current_boundary import game_driver
from commander_lab.qualification.current_boundary.game_driver import (
    COST_ORDER_POLICY,
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


class _FakeProcess:
    def __init__(self) -> None:
        self.imports = 0
        self.submissions: list[dict[str, object]] = []

    def request(
        self,
        message_type: str,
        payload: dict[str, object],
        *,
        game_id: str | None = None,
        timeout_s: float = 0,
    ) -> dict[str, object]:
        del game_id, timeout_s
        if message_type == "get_capabilities":
            return {"success": True, "payload": {"capabilities": {"seed_supported": False}}}
        if message_type in {"start_engine", "get_provider_version"}:
            return {"success": True, "payload": {}}
        if message_type == "import_deck":
            self.imports += 1
            return {
                "success": True,
                "payload": {"deck_handle": {"handle_id": f"deck-{self.imports}"}},
            }
        if message_type == "create_commander_game":
            return {"success": True, "payload": {"player_count": 2}}
        if message_type == "start_game":
            return {"success": True, "payload": {"status": "started"}}
        if message_type == "submit_action":
            self.submissions.append(payload)
            return {"success": True, "payload": {"accepted": True}}
        if message_type == "pass_priority":
            return {"success": True, "payload": {"accepted": True}}
        raise AssertionError(f"unexpected request {message_type}")


def test_game_driver_submits_declared_cost_order_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frames = iter(
        [
            {
                "seat": "p1",
                "decision": {
                    "kind": "ORDER_CHOICE",
                    "actor": "p1",
                    "revision": 41,
                    "decision_id": None,
                    "status": "SUPPORTED",
                },
                "actions": [
                    _action("reverse", "cost_order", [1, 0]),
                    _action("native", "cost_order", [0, 1]),
                ],
                "raw": {},
            },
            {
                "seat": "p1",
                "decision": {
                    "kind": "PRIORITY",
                    "actor": "p1",
                    "revision": 42,
                    "decision_id": None,
                    "status": "SUPPORTED",
                },
                "actions": [
                    {
                        "action_id": "pass",
                        "action_type": "pass_priority",
                        "metadata": {},
                    }
                ],
                "raw": {},
            },
        ]
    )

    def _poll(*args: object, **kwargs: object) -> dict[str, object]:
        del args, kwargs
        return next(frames)

    monkeypatch.setattr(game_driver, "poll_decision", _poll)
    proc = _FakeProcess()

    result = game_driver.drive_commander_game(
        proc,  # type: ignore[arg-type]
        candidate="forge",
        player_count=2,
        seed=7,
        drive_to="priority",
    )

    assert result.failure is None
    assert proc.submissions
    proposal = proc.submissions[0]["proposal"]
    assert isinstance(proposal, dict)
    assert proposal["legal_action_id"] == "native"
    assert proposal["action_type"] == "cost_order"
    assert result.decision_tape[0].policy == COST_ORDER_POLICY
    assert result.decision_tape[0].chosen_option_id == "native"
