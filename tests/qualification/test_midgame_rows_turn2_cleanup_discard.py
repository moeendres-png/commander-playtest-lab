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

import pytest

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


def _probe_module(name: str) -> Any:
    import importlib.util

    probe_path = REPO_ROOT / "scripts" / "run_midgame_capability_probe.py"
    spec = importlib.util.spec_from_file_location(name, probe_path)
    assert spec is not None and spec.loader is not None
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    return probe


_FAIL_CLOSED = {
    "matches_only_provider_offered_legal_options": True,
    "on_zero_match": "FAIL_CLOSED",
    "on_multiple_match": "FAIL_CLOSED",
}


def _turn2_record(value: Any = None, actor: str = "P1") -> dict[str, Any]:
    """The record with a declared starter and its full pre-checkpoint history.

    The test-local copy carries the ruled transport shape (contract 1.0.26 is
    produced by its own generator): the pregame keeps (CR 103.5), the arrival
    priority pass-through (CR 117.3d) and P1's empty turn-1 attack declaration
    (CR 508.1) are the record's own declarations; the Lab transports them and
    never chooses for a player.
    """
    if value is None:
        value = {"Mountain": 1}
    record = _effective_record()
    record["starting_player"] = "P1"
    record["decision_script"] = [
        {
            "actor": seat,
            "decision_family": "mulligan",
            "selection": {
                **_FAIL_CLOSED,
                "selector_kind": "semantic_action",
                "semantic_value": "keep_opening_hand",
            },
        }
        for seat in ("P1", "P2", "P3", "P4")
    ] + [
        {
            "actor": "ALL",
            "decision_family": "priority_pass_through",
            "scope": {
                "from": {"turn": 1, "phase": "beginning"},
                "until": {"turn": 2, "phase": "precombat_main", "step": "main"},
            },
            "selection": {
                **_FAIL_CLOSED,
                "selector_kind": "semantic_action",
                "semantic_value": "pass_priority",
            },
        },
        {
            "actor": "P1",
            "decision_family": "declare_attackers",
            "phase": "DECLARE_ATTACKERS",
            "turn": 1,
            "selection": {
                **_FAIL_CLOSED,
                "selector_kind": "attacker_assignment",
                "semantic_value": {},
            },
        },
        {
            "actor": actor,
            "decision_family": "cleanup_discard",
            "phase": "CLEANUP",
            "turn": 1,
            "selection": {
                **_FAIL_CLOSED,
                "selector_kind": "card_identity_multiset",
                "semantic_value": value,
            },
        },
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


def _attacker_frame(
    *,
    decision_id: str = "d-atk-1",
    seat: int = 0,
    actor_id: str = "actor-0",
    option_id: str = "hold-1",
) -> dict[str, Any]:
    return {
        "decision_id": decision_id,
        "decision_class": "declare_attacker",
        "actor_id": actor_id,
        "seat": seat,
        "legal_options": [{"option_id": option_id, "option_type": "hold_attacker"}],
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


def _precheckpoint_history_frames() -> list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]:
    """The record's declared pre-checkpoint history as engine frames.

    The contract scripts four pregame keeps (CR 103.5) and P1's empty turn-1
    attack declaration (CR 508.1) before the turn-2 checkpoint. Tests that
    reach the checkpoint must transport them like the engine does; the arrival
    ledger refuses an unconsumed declared step.
    """
    frames: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    for seat in range(4):
        frames.append(
            (
                {
                    "decision_id": f"d-mull-{seat}",
                    "decision_class": "mulligan",
                    "actor_id": f"actor-{seat}",
                    "seat": seat,
                    "legal_options": [{"option_id": f"keep-{seat}", "option_type": "keep"}],
                },
                _legal(
                    f"actor-{seat}",
                    [{"action_id": f"keep-{seat}", "metadata": {"seat": seat}}],
                ),
                {"phase": "UNINITIALIZED", "step": "MULLIGAN", "priority_player": f"P{seat + 1}"},
            )
        )
    frames.append(
        (
            _attacker_frame(decision_id="d-atk-history"),
            _legal("actor-0", [{"action_id": "hold-history", "metadata": {"seat": 0}}]),
            _observation(1, "COMBAT", "DECLARE_ATTACKERS", "P1"),
        )
    )
    return frames


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


def test_a_malformed_explicit_starter_field_is_never_salvaged_from_turn_one() -> None:
    """Review 5462161504 control (1 of 2 refusals): a malformed explicit
    ``starting_player`` field is the parser's refusal, not an absent
    declaration, so it must never fall back to the authorized turn-1
    active-player shape."""
    assert midgame_starting_seat(
        {"starting_player": "INVALID", "temporal_state": {"turn_number": 1, "active_player": "P2"}}
    ) == (None, None)


def test_a_malformed_scripted_starter_step_is_never_salvaged_from_turn_one() -> None:
    """Review 5462161504 control (2 of 2 refusals): a ``starting_player`` script
    step without its fail-closed selection contract carries no seat, and a
    turn-1 active player must never repair that malformed authority."""
    record = {
        "decision_script": [
            {
                "decision_family": "starting_player",
                # The selector kind names a seat, but the fail-closed selection
                # contract is missing: no valid declaration has been read.
                "selection": {"selector_kind": "seat", "semantic_value": "P1"},
            }
        ],
        "temporal_state": {"turn_number": 1, "active_player": "P2"},
    }
    assert midgame_starting_seat(record) == (None, None)


def test_an_absent_starter_declaration_at_turn_one_uses_the_authorized_shape() -> None:
    """Positive control: with no declaration shape at all, the turn-1 active
    player is the starter (CR 103.1) and the authorized shape is used."""
    assert midgame_starting_seat({"temporal_state": {"turn_number": 1, "active_player": "P3"}}) == (
        "p3",
        "RECORD_TEMPORAL_STATE_TURN_ONE_ACTIVE_PLAYER",
    )


def test_an_explicit_starter_declaration_wins_at_a_later_checkpoint() -> None:
    """Positive control: a valid explicit declaration is used even when the
    checkpoint's active player (turn 2, P2) is a different seat."""
    seat, source = midgame_starting_seat(
        {
            "starting_player": "P1",
            "temporal_state": {"turn_number": 2, "active_player": "P2"},
        }
    )
    assert (seat, source) == ("p1", "RECORD_STARTING_PLAYER_FIELD")


def test_drive_arrival_refuses_a_malformed_starter_before_any_label_or_frame() -> None:
    """Review 5462161504: the arrival driver refuses missing/invalid starting
    authority before deriving any seat label; the checkpoint's active player
    (P2) is never used as a fallback. No engine frame is answered."""
    probe = _probe_module("probe_authority_under_test")
    record = _turn2_record()
    record["starting_player"] = "INVALID"
    client = _SequencedClient([_checkpoint_frame(TURN2_MAIN)])
    with pytest.raises(mr.ml.MidgameLaneError) as excinfo:
        probe.drive_arrival(client, record)
    assert "no usable starting authority" in str(excinfo.value)
    assert client.submissions == []


def test_drive_arrival_refuses_an_undeclared_starter_for_a_later_checkpoint() -> None:
    """Review 5462161504: without any starting declaration a turn-2 checkpoint
    fails closed before the arrival answers anything."""
    probe = _probe_module("probe_no_authority_under_test")
    record = _turn2_record()
    record.pop("starting_player")
    client = _SequencedClient([_checkpoint_frame(TURN2_MAIN)])
    with pytest.raises(mr.ml.MidgameLaneError) as excinfo:
        probe.drive_arrival(client, record)
    assert "no usable starting authority" in str(excinfo.value)
    assert client.submissions == []


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
            *_precheckpoint_history_frames(),
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
            *_precheckpoint_history_frames(),
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


# --------------------------------------------------------------------------- #
# Pre-checkpoint transport is only ever the record's own declaration
# --------------------------------------------------------------------------- #


def test_an_unscripted_turn_one_attacker_frame_fails_closed() -> None:
    """Review 5462161504 P1 red control: the absence of a combat declaration in
    the record is not an answer. The frame must be refused before any
    submission, never auto-held."""
    record = _turn2_record()
    record["decision_script"] = [
        step
        for step in record["decision_script"]
        if step.get("decision_family") != "declare_attackers"
    ]
    client = _SequencedClient(
        [
            (
                _attacker_frame(),
                _legal("actor-0", [{"action_id": "hold-1", "metadata": {"seat": 0}}]),
                _observation(1, "COMBAT", "DECLARE_ATTACKERS", "P1"),
            ),
            _checkpoint_frame(TURN2_MAIN),
        ]
    )
    execution = mr.execute_row(client, record, {}, mr.ROWS[PARENT_CLASS])
    assert not execution.verified
    assert "never holds an unrecorded attack" in execution.detail
    assert client.submissions == []


def test_a_scripted_empty_attack_declaration_answers_each_offered_creature() -> None:
    """The record's own empty ``declare_attackers`` declaration is transported:
    each engine attacker frame gets its own offered hold option (CR 508.1)."""
    probe = _probe_module("probe_attacker_under_test")
    record = _turn2_record()
    client = _SequencedClient(
        [
            (
                _attacker_frame(),
                _legal("actor-0", [{"action_id": "hold-1", "metadata": {"seat": 0}}]),
                _observation(1, "COMBAT", "DECLARE_ATTACKERS", "P1"),
            ),
            (
                _attacker_frame(decision_id="d-atk-2", option_id="hold-2"),
                _legal("actor-0", [{"action_id": "hold-2", "metadata": {"seat": 0}}]),
                _observation(1, "COMBAT", "DECLARE_ATTACKERS", "P1"),
            ),
            _checkpoint_frame(TURN2_MAIN),
        ]
    )
    verdict = probe.drive_arrival(client, record)
    assert verdict is not None and verdict.construction_verdict == "EXACT"
    assert client.submissions == [["hold-1"], ["hold-2"]]


def test_an_attacker_frame_without_a_readable_turn_fails_closed() -> None:
    """Probe item 2: a turn comparison without an int ``turn_number`` is never
    guessed; the attacker frame fails closed."""
    probe = _probe_module("probe_no_turn_under_test")
    record = _turn2_record()
    client = _SequencedClient(
        [
            (
                _attacker_frame(),
                _legal("actor-0", [{"action_id": "hold-1", "metadata": {"seat": 0}}]),
                {"phase": "COMBAT", "step": "DECLARE_ATTACKERS", "priority_player": "P1"},
            )
        ]
    )
    with pytest.raises(mr.ml.MidgameLaneError) as excinfo:
        probe.drive_arrival(client, record)
    assert "without a readable turn" in str(excinfo.value)
    assert client.submissions == []


def test_an_unscripted_priority_pass_fails_closed() -> None:
    """The arrival pilot never passes priority on a player's behalf: a priority
    frame outside a declared ``priority_pass_through`` scope fails closed."""
    record = _turn2_record()
    record["decision_script"] = [
        step
        for step in record["decision_script"]
        if step.get("decision_family") != "priority_pass_through"
    ]
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
    execution = mr.execute_row(client, record, {}, mr.ROWS[PARENT_CLASS])
    assert not execution.verified
    assert "scripts no priority pass-through" in execution.detail
    assert client.submissions == []


def test_an_unscripted_mulligan_keep_fails_closed() -> None:
    """The arrival pilot never keeps an opening hand on a player's behalf: a
    mulligan frame without the record's own keep step fails closed."""
    probe = _probe_module("probe_mulligan_under_test")
    record = _turn2_record()
    record["decision_script"] = [
        step for step in record["decision_script"] if step.get("decision_family") != "mulligan"
    ]
    client = _SequencedClient(
        [
            (
                {
                    "decision_id": "d-mull-1",
                    "decision_class": "mulligan",
                    "actor_id": "actor-0",
                    "seat": 0,
                    "legal_options": [{"option_id": "keep-1", "option_type": "keep"}],
                },
                _legal("actor-0", [{"action_id": "keep-1", "metadata": {"seat": 0}}]),
                {"phase": "UNINITIALIZED", "step": "MULLIGAN", "priority_player": "P1"},
            )
        ]
    )
    with pytest.raises(mr.ml.MidgameLaneError) as excinfo:
        probe.drive_arrival(client, record)
    assert "scripts no mulligan keep for P1" in str(excinfo.value)
    assert client.submissions == []


def test_a_cleanup_discard_is_bound_to_its_declared_phase_and_turn() -> None:
    """Probe item 4: the same decision family at another turn's cleanup is not
    the scripted step; the frame fails closed rather than matching by class."""
    record = _turn2_record()
    client = _SequencedClient(
        [
            _cleanup_frame(
                [_card_offer("Mountain", "n-mtn-a", "opt-a")],
                observation=_observation(2, "CLEANUP", "CLEANUP", "P2"),
                seat=1,
            )
        ]
    )
    execution = mr.execute_row(client, record, {}, mr.ROWS[PARENT_CLASS])
    assert not execution.verified
    assert "cleanup_discard for turn 1" in execution.detail
    assert client.submissions == []


# --------------------------------------------------------------------------- #
# PR #624 review round: scope, history completeness and frame routing controls
# --------------------------------------------------------------------------- #


def test_a_priority_frame_outside_the_declared_scope_fails_closed() -> None:
    """Review item 1: the pass-through applies only inside the record's own
    ``scope.from``/``scope.until`` window. A turn-2 priority frame whose scope
    ended on turn 1 must never be passed by the Lab."""
    probe = _probe_module("probe_scope_under_test")
    record = _turn2_record()
    for step in record["decision_script"]:
        if step.get("decision_family") == "priority_pass_through":
            step["scope"] = {
                "from": {"turn": 1, "phase": "beginning"},
                "until": {"turn": 1, "phase": "precombat_main", "step": "main"},
            }
    client = _SequencedClient(
        [
            *_precheckpoint_history_frames(),
            _checkpoint_frame(_observation(2, "BEGINNING", "UPKEEP", "P2"), decision_id="d-oos"),
        ]
    )
    with pytest.raises(mr.ml.MidgameLaneError) as excinfo:
        probe.drive_arrival(client, record)
    assert "scripts no priority pass-through" in str(excinfo.value)


def test_a_priority_frame_without_a_readable_turn_fails_closed() -> None:
    """Review item 1: the scope cannot be evaluated from an unreadable frame;
    a priority frame without a turn number is never passed."""
    probe = _probe_module("probe_no_turn_scope_under_test")
    record = _turn2_record()
    client = _SequencedClient(
        [
            *_precheckpoint_history_frames(),
            _checkpoint_frame(
                {"phase": "PRECOMBAT_MAIN", "step": "PRECOMBAT_MAIN", "priority_player": "P2"},
                decision_id="d-no-turn",
            ),
        ]
    )
    with pytest.raises(mr.ml.MidgameLaneError) as excinfo:
        probe.drive_arrival(client, record)
    assert "readable turn or phase" in str(excinfo.value)


def test_a_priority_frame_without_a_turn_is_never_a_checkpoint() -> None:
    """Review item 3: PRECOMBAT_MAIN without a readable turn_number is never
    taken as the checkpoint. Mutation: dropping the turn guard from
    ``_arrival_at_checkpoint`` makes this assertion fail."""
    probe = _probe_module("probe_checkpoint_turn_under_test")
    assert (
        probe._arrival_at_checkpoint(
            {"phase": "PRECOMBAT_MAIN", "step": "PRECOMBAT_MAIN"},
            2,
            "PRECOMBAT_MAIN",
            "PRECOMBAT_MAIN",
        )
        is False
    )
    assert (
        probe._arrival_at_checkpoint(
            {"turn_number": True, "phase": "PRECOMBAT_MAIN", "step": "PRECOMBAT_MAIN"},
            2,
            "PRECOMBAT_MAIN",
            "PRECOMBAT_MAIN",
        )
        is False
    )


def test_an_in_game_choice_is_not_answered_by_a_seat_label() -> None:
    """Review item 4: the starting-seat label selects only the pre-game setup
    frame; an in-game choose_object offering a seat-labelled option is never
    answered from that label."""
    probe = _probe_module("probe_in_game_label_under_test")
    record = _turn2_record()
    record["decision_script"] = [
        step
        for step in record["decision_script"]
        if step.get("decision_family") != "cleanup_discard"
    ]
    label_action = {
        "action_id": "seat-opt",
        "metadata": {"label": "Full Game Seat 1", "seat": 0},
    }
    client = _SequencedClient(
        [
            *_precheckpoint_history_frames(),
            (
                {
                    "decision_id": "d-in-game",
                    "decision_class": "choose_object",
                    "actor_id": "actor-0",
                    "seat": 0,
                    "legal_options": [
                        {
                            "option_id": "seat-opt",
                            "option_type": "object",
                            "label": "Full Game Seat 1",
                        }
                    ],
                },
                _legal("actor-0", [label_action]),
                _observation(1, "PRECOMBAT_MAIN", "PRECOMBAT_MAIN", "P1"),
            ),
        ]
    )
    with pytest.raises(mr.ml.MidgameLaneError) as excinfo:
        probe.drive_arrival(client, record)
    assert "offered no option" in str(excinfo.value)
    assert "seat-opt" not in [opt for submission in client.submissions for opt in submission]


def test_an_unconsumed_declared_history_step_fails_closed() -> None:
    """Review item 5: a declared pre-checkpoint transport step the engine never
    asked fails the row closed instead of silently skipping a mandatory
    player decision."""
    record = _turn2_record()
    record["decision_script"] = [
        step
        for step in record["decision_script"]
        if step.get("decision_family") in {"starting_player", "cleanup_discard"}
    ]
    client = _SequencedClient([_checkpoint_frame(TURN2_MAIN)])
    execution = mr.execute_row(client, record, {}, mr.ROWS[PARENT_CLASS])
    assert not execution.verified
    assert "unconsumed transport step fails closed" in execution.detail
    assert client.submissions == []


def test_an_unconsumed_declared_mulligan_keep_fails_closed() -> None:
    """Review item 5: a declared keep that was never answered is refused."""
    record = _turn2_record()
    record["decision_script"] = [
        step
        for step in record["decision_script"]
        if step.get("decision_family") in {"starting_player", "mulligan"}
    ]
    client = _SequencedClient([_checkpoint_frame(TURN2_MAIN)])
    execution = mr.execute_row(client, record, {}, mr.ROWS[PARENT_CLASS])
    assert not execution.verified
    assert "unconsumed transport step fails closed" in execution.detail


def test_a_later_checkpoint_without_declared_keeps_fails_closed_in_placement() -> None:
    """Review item 2: ``drive_to_precombat_main`` never keeps a hand for a
    player at a later-turn checkpoint without the record's own keep step."""
    probe = _probe_module("probe_placement_keep_under_test")
    record = {
        "fixture_id": "PLACEMENT_LATER",
        "starting_player": "P1",
        "temporal_state": {
            "turn_number": 2,
            "phase": "precombat_main",
            "step": "main",
            "active_player": "P2",
        },
        "decision_script": [],
    }
    client = _SequencedClient(
        [
            (
                {
                    "decision_id": "d-mull",
                    "decision_class": "mulligan",
                    "actor_id": "actor-0",
                    "seat": 0,
                    "legal_options": [{"option_id": "keep", "option_type": "keep"}],
                },
                _legal("actor-0", [{"action_id": "keep", "metadata": {"seat": 0}}]),
                {"phase": "UNINITIALIZED", "step": "MULLIGAN", "priority_player": "P1"},
            )
        ]
    )
    with pytest.raises(mr.ml.MidgameLaneError) as excinfo:
        probe.drive_to_precombat_main(client, record)
    assert "scripts no mulligan keep" in str(excinfo.value)


def test_a_later_checkpoint_without_declared_passes_fails_closed_in_placement() -> None:
    """Review item 2: ``drive_to_precombat_main`` never passes priority for a
    player at a later-turn checkpoint without the record's own pass-through."""
    probe = _probe_module("probe_placement_pass_under_test")
    record = {
        "fixture_id": "PLACEMENT_LATER",
        "starting_player": "P1",
        "temporal_state": {
            "turn_number": 2,
            "phase": "precombat_main",
            "step": "main",
            "active_player": "P2",
        },
        "decision_script": [],
    }
    client = _SequencedClient(
        [
            _checkpoint_frame(
                _observation(1, "PRECOMBAT_MAIN", "PRECOMBAT_MAIN", "P1"), decision_id="d-p"
            )
        ]
    )
    with pytest.raises(mr.ml.MidgameLaneError) as excinfo:
        probe.drive_to_precombat_main(client, record)
    assert "scripts no priority pass-through" in str(excinfo.value)
