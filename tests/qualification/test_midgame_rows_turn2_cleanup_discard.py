"""Turn-2 checkpoint arrival: starting seat, turn-aware stop, scripted discard.

Contract 1.0.25 scripts P1's mandatory turn-1 cleanup discard (CR 514.1) so the
turn-2 NEGATIVE_PARENT_CLASS_FALLBACK checkpoint can be constructed. These
tests drive the fake mid-game lane through that arrival:

* the starting seat comes from the record's own starting-seat declaration and
  is never derived from the turn-2 checkpoint's active player (P2);
* the checkpoint stop is turn-aware: turn 1's precombat main is not the turn-2
  checkpoint;
* the record's cleanup discard is transported from its card-name multiset
  (least option id among same-name copies), and a wrong actor, a missing name,
  a count mismatch or an unscripted extra discard fails the row closed;
* a lenient first-option transport is shown not to be the record's selection.

The tests use a test-local record copy; the contract files themselves are
owned by another run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from commander_lab.qualification.current_boundary import midgame_rows as mr
from commander_lab.qualification.current_boundary.materialization import (
    load_effective_materialization,
)
from commander_lab.qualification.current_boundary.starting_player import (
    midgame_starting_seat,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PARENT_CLASS = "NEGATIVE_PARENT_CLASS_FALLBACK"


def _effective_record() -> dict[str, Any]:
    return load_effective_materialization(REPO_ROOT).record(PARENT_CLASS)


def _turn2_record(value: Any = None, actor: str = "P1") -> dict[str, Any]:
    """The record with a declared starter and the scripted turn-1 discard."""
    if value is None:
        value = {"Mountain": 1}
    record = _effective_record()
    record["starting_player"] = "P1"
    record["decision_script"] = [
        {
            "actor": actor,
            "decision_family": "cleanup_discard",
            "selection": {"selector_kind": "card_identity_multiset", "semantic_value": value},
        }
    ]
    return record


def _card_offer(name: str, native: str, option_id: str) -> dict[str, Any]:
    return {
        "action_id": option_id,
        "action_type": "object",
        "metadata": {
            "option_type": "object",
            "option_id": option_id,
            "label": name,
            "seat": 0,
            "xmage_option_metadata": {"object_id": native, "name": name, "zone": "hand"},
        },
    }


def _discard_frame(
    *,
    decision_id: str = "d-cleanup",
    seat: int = 0,
    actor_id: str = "actor-0",
) -> dict[str, Any]:
    return {
        "decision_id": decision_id,
        "decision_class": "choose_object",
        "actor_id": actor_id,
        "seat": seat,
        "prompt": "Choose a card to discard",
        "legal_options": [{"option_id": "offered", "label": "offered"}],
    }


def _priority_frame(
    *,
    decision_id: str,
    seat: int,
    actor_id: str,
    option_id: str = "pass",
) -> dict[str, Any]:
    return {
        "decision_id": decision_id,
        "decision_class": "priority",
        "actor_id": actor_id,
        "seat": seat,
        "legal_options": [{"option_id": option_id, "option_type": "pass_priority"}],
    }


def _legal(
    actor_id: str,
    actions: list[dict[str, Any]],
    *,
    minimum: int = 1,
    maximum: int = 1,
) -> dict[str, Any]:
    return {
        "actor_id": actor_id,
        "decision": {"minimum_selections": minimum, "maximum_selections": maximum},
        "actions": actions,
    }


def _observation(turn: int, phase: str, step: str, priority: str) -> dict[str, Any]:
    return {
        "turn_number": turn,
        "phase": phase,
        "step": step,
        "priority_player": priority,
    }


class _SequencedClient:
    """A fake mid-game lane that serves recorded (decision, legal) frames.

    A submitted answer advances to the next frame; a read-only refusal does not.
    """

    def __init__(self, frames: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]):
        self._frames = list(frames)
        self.submissions: list[Any] = []
        self.proposals: list[Any] = []
        self.offset = 0
        self.tape: list[dict[str, Any]] = []
        self.engine_commit = "e" * 40

    def _current(self) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        return self._frames[0]

    def pending_decision(
        self, *, attempts: int = 60, interval_s: float = 0.5
    ) -> dict[str, Any] | None:
        return self._current()[0] if self._frames else None

    def request(self, message_type: str, payload: Any = None) -> dict[str, Any]:
        if message_type == "get_legal_actions":
            return {"success": True, "payload": self._current()[1]}
        if message_type == "submit_action":
            self.proposals.append(payload)
            self.tape.append({"message_type": "submit_action"})
            self._frames.pop(0)
            return {"success": True, "payload": {}}
        raise AssertionError(f"unexpected lane request {message_type}")

    def submit_options(self, decision: dict[str, Any], option_ids: list[str]) -> None:
        self.submissions.append(list(option_ids))
        self.tape.append({"message_type": "submit_options"})
        self._frames.pop(0)

    def complete_arrival(self) -> dict[str, Any]:
        return {
            "construction_match": True,
            "mismatches": [],
            "observation": dict(self._current()[2]),
        }

    def events(self, after_offset: int = 0) -> dict[str, Any]:
        return {"latest_offset": self.offset, "events": []}


def _cleanup_frame(
    actions: list[dict[str, Any]],
    *,
    observation: dict[str, Any],
    seat: int = 0,
    minimum: int = 1,
    maximum: int = 1,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return (
        _discard_frame(seat=seat, actor_id=f"actor-{seat}"),
        _legal(f"actor-{seat}", actions, minimum=minimum, maximum=maximum),
        observation,
    )


def _checkpoint_frame(
    observation: dict[str, Any],
    *,
    seat: int = 1,
    decision_id: str = "d-prio2",
    option_id: str = "pass",
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    actor = f"actor-{seat}"
    return (
        _priority_frame(decision_id=decision_id, seat=seat, actor_id=actor, option_id=option_id),
        _legal(actor, [{"action_id": option_id, "metadata": {"seat": seat}}]),
        observation,
    )


def _omission_frame(
    observation: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return (
        _discard_frame(decision_id="d-omit", seat=0),
        _legal(
            "actor-0",
            [_card_offer("Mountain", "n-omit-mtn", "opt-omit-mtn")],
        ),
        observation,
    )


TURN1_CLEANUP = _observation(1, "CLEANUP", "CLEANUP", "P1")
TURN2_MAIN = _observation(2, "PRECOMBAT_MAIN", "PRECOMBAT_MAIN", "P2")


# --------------------------------------------------------------------------- #
# The starting seat comes from the record, never from the checkpoint's active
# --------------------------------------------------------------------------- #


def test_a_later_checkpoints_active_player_is_not_the_starting_seat() -> None:
    assert midgame_starting_seat({"temporal_state": {"turn_number": 2, "active_player": "P2"}}) == (
        None,
        None,
    )


def test_an_explicit_starting_seat_declaration_is_used() -> None:
    seat, source = midgame_starting_seat(
        {
            "starting_player": "P1",
            "temporal_state": {"turn_number": 2, "active_player": "P2"},
        }
    )
    assert seat == "p1"
    assert source == "RECORD_STARTING_PLAYER_FIELD"


def test_a_turn_one_checkpoint_active_player_is_the_starter_by_cr_103_1() -> None:
    seat, _source = midgame_starting_seat(
        {"temporal_state": {"turn_number": 1, "active_player": "P3"}}
    )
    assert seat == "p3"


def test_disagreeing_starter_declarations_are_never_resolved_by_fallback() -> None:
    record = {
        "starting_player": "P1",
        "decision_script": [
            {
                "decision_family": "starting_player",
                "selection": {
                    "matches_only_provider_offered_legal_options": True,
                    "on_zero_match": "FAIL_CLOSED",
                    "on_multiple_match": "FAIL_CLOSED",
                    "selector_kind": "seat",
                    "semantic_value": "P2",
                },
            }
        ],
        "temporal_state": {"turn_number": 1, "active_player": "P3"},
    }
    assert midgame_starting_seat(record) == (None, None)


def test_the_probe_starting_seat_index_uses_only_the_declaration() -> None:
    import importlib.util

    probe_path = REPO_ROOT / "scripts" / "run_midgame_capability_probe.py"
    spec = importlib.util.spec_from_file_location("probe_seat_under_test", probe_path)
    assert spec is not None and spec.loader is not None
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    assert probe.record_starting_seat_index(_turn2_record()) == 0
    # Contract 1.0.25 declares the effective record's starting seat P1, so the
    # undeclared control is built by removing that declaration: a turn-2
    # checkpoint's active player (P2) is still never a starting seat.
    undeclared = _effective_record()
    undeclared["decision_script"] = [
        step
        for step in undeclared.get("decision_script") or ()
        if step.get("decision_family") != "starting_player"
    ]
    undeclared.pop("starting_player", None)
    assert undeclared["temporal_state"]["turn_number"] == 2
    assert probe.record_starting_seat_index(undeclared) is None


# --------------------------------------------------------------------------- #
# The checkpoint stop is turn-aware
# --------------------------------------------------------------------------- #


def test_turn_ones_precombat_main_is_passed_not_taken_as_the_checkpoint() -> None:
    import importlib.util

    probe_path = REPO_ROOT / "scripts" / "run_midgame_capability_probe.py"
    spec = importlib.util.spec_from_file_location("probe_turn_under_test", probe_path)
    assert spec is not None and spec.loader is not None
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    client = _SequencedClient(
        [
            _checkpoint_frame(
                _observation(1, "PRECOMBAT_MAIN", "PRECOMBAT_MAIN", "P1"),
                seat=0,
                decision_id="d-turn1",
                option_id="pass-1",
            ),
            _checkpoint_frame(TURN2_MAIN),
        ]
    )
    verdict = probe.drive_arrival(client, _turn2_record())
    assert verdict is not None and verdict.construction_verdict == "EXACT"
    # The turn-1 priority was passed; the arrival stopped at turn 2 only.
    assert client.submissions == [["pass-1"]]


# --------------------------------------------------------------------------- #
# The scripted cleanup discard is transported from the record's multiset
# --------------------------------------------------------------------------- #


def test_the_scripted_cleanup_discard_submits_the_named_card_and_verifies() -> None:
    record = _turn2_record()
    client = _SequencedClient(
        [
            # The engine offers the same-name copies out of id order: the
            # transport must take the least option id, not the first offer.
            _cleanup_frame(
                [
                    _card_offer("Mountain", "n-mtn-b", "opt-b"),
                    _card_offer("Mountain", "n-mtn-a", "opt-a"),
                ],
                observation=TURN1_CLEANUP,
            ),
            _checkpoint_frame(TURN2_MAIN),
            _omission_frame(TURN2_MAIN),
        ]
    )
    execution = mr.execute_row(client, record, {}, mr.ROWS[PARENT_CLASS])
    assert execution.verified, execution.detail
    (submitted,) = client.proposals
    assert submitted["proposal"]["legal_action_id"] == "opt-a"
    assert submitted["proposal"]["choices"]["selected_option_ids"] == ["opt-a"]
    (arrival_frame,) = [
        frame for frame in execution.decision_trace if frame["selected_key"] == "Mountain:1"
    ]
    assert arrival_frame["decision_class"] == "choose_object"
    assert arrival_frame["principal"] == "P1"
    assert arrival_frame["scripted"] is True
    assert arrival_frame["selected_option_ids"] == ("opt-a",)


def test_a_lenient_first_option_transport_is_not_the_records_selection() -> None:
    record = _turn2_record()
    client = _SequencedClient(
        [
            _cleanup_frame(
                [
                    _card_offer("Island", "n-isl", "opt-0"),
                    _card_offer("Mountain", "n-mtn-a", "opt-1"),
                    _card_offer("Mountain", "n-mtn-b", "opt-2"),
                ],
                observation=TURN1_CLEANUP,
            ),
            _checkpoint_frame(TURN2_MAIN),
            _omission_frame(TURN2_MAIN),
        ]
    )
    execution = mr.execute_row(client, record, {}, mr.ROWS[PARENT_CLASS])
    assert execution.verified, execution.detail
    (submitted,) = client.proposals
    # The first offered option is the Island; the record names one Mountain.
    assert submitted["proposal"]["legal_action_id"] != "opt-0"
    assert submitted["proposal"]["legal_action_id"] == "opt-1"


def test_a_cleanup_discard_asked_of_the_wrong_actor_fails_closed() -> None:
    record = _turn2_record(actor="P1")
    client = _SequencedClient(
        [
            _cleanup_frame(
                [_card_offer("Mountain", "n-mtn-a", "opt-a")],
                observation=TURN1_CLEANUP,
                seat=1,
            )
        ]
    )
    execution = mr.execute_row(client, record, {}, mr.ROWS[PARENT_CLASS])
    assert not execution.verified
    assert "the engine asked the scripted choose_object of P2" in execution.detail
    assert client.proposals == []


def test_a_cleanup_discard_with_a_missing_name_fails_closed() -> None:
    record = _turn2_record()
    client = _SequencedClient(
        [
            _cleanup_frame(
                [_card_offer("Island", "n-isl", "opt-isl")],
                observation=TURN1_CLEANUP,
            )
        ]
    )
    execution = mr.execute_row(client, record, {}, mr.ROWS[PARENT_CLASS])
    assert not execution.verified
    assert "the record selects 1 'Mountain', the engine offers 0" in execution.detail
    assert client.proposals == []


def test_a_cleanup_discard_with_a_count_mismatch_fails_closed() -> None:
    record = _turn2_record(value={"Mountain": 2})
    client = _SequencedClient(
        [
            _cleanup_frame(
                [
                    _card_offer("Mountain", "n-mtn-a", "opt-a"),
                    _card_offer("Mountain", "n-mtn-b", "opt-b"),
                ],
                observation=TURN1_CLEANUP,
                minimum=1,
                maximum=1,
            )
        ]
    )
    execution = mr.execute_row(client, record, {}, mr.ROWS[PARENT_CLASS])
    assert not execution.verified
    assert "the record selects 2 cards, the engine frame asks (1, 1)" in execution.detail
    assert client.proposals == []


def test_an_unscripted_extra_cleanup_discard_fails_closed() -> None:
    record = _turn2_record()
    client = _SequencedClient(
        [
            _cleanup_frame(
                [_card_offer("Mountain", "n-mtn-a", "opt-a")],
                observation=TURN1_CLEANUP,
            ),
            _cleanup_frame(
                [_card_offer("Mountain", "n-mtn-b", "opt-b")],
                observation=TURN1_CLEANUP,
            ),
        ]
    )
    execution = mr.execute_row(client, record, {}, mr.ROWS[PARENT_CLASS])
    assert not execution.verified
    assert "unscripted extra choose_object for P1" in execution.detail


def test_the_cleanup_discard_family_maps_to_the_engine_choose_object_frame() -> None:
    step = {
        "decision_family": "cleanup_discard",
        "selection": {"selector_kind": "card_identity_multiset", "semantic_value": {"Mountain": 1}},
    }
    assert mr.step_decision_class(step) == "choose_object"


def test_an_undeclared_cleanup_discard_is_never_answered_by_the_lab() -> None:
    # The record scripts no discard step: the arrival callback has no step to
    # answer with, so the frame falls through and fails closed.
    record = _effective_record()
    record["decision_script"] = [
        step
        for step in record.get("decision_script") or ()
        if step.get("decision_family") != "cleanup_discard"
    ]
    record["starting_player"] = "P1"
    client = _SequencedClient(
        [
            _cleanup_frame(
                [_card_offer("Mountain", "n-mtn-a", "opt-a")],
                observation=TURN1_CLEANUP,
            )
        ]
    )
    execution = mr.execute_row(client, record, {}, mr.ROWS[PARENT_CLASS])
    assert not execution.verified
    assert "arrival failed closed" in execution.detail
    assert client.proposals == []
