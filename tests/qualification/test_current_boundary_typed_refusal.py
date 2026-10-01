"""Explicit typed refusal of an unsupported discretionary decision class.

#255 (2026-10-01) ruled that ``DECISION_TIMEOUT`` does not satisfy an obligation
requiring ``UNSUPPORTED_DISCRETIONARY_DECISION``. The refusal path must be
explicit, auditable, typed, must not select an action, must not mutate the game
state, and must never be manufactured from a timeout.

These tests pin the mechanism without a live engine: a fake transport records
exactly the requests the refusal makes, so the no-submission and no-mutation
conditions are verified on the recorded facts rather than asserted. Every
mutation of those facts must fail closed.
"""

from __future__ import annotations

from typing import Any

import pytest

from commander_lab.qualification.current_boundary import midgame_rows as mr
from commander_lab.qualification.current_boundary import refusal as ref


class _FakeClient:
    """A read-only transport that records every request it is asked to send."""

    def __init__(
        self,
        *,
        offset_before: Any = 12,
        offset_after: Any = 12,
        decision_after: str | None = "dec-1",
        extra_window: tuple[str, ...] = (),
    ) -> None:
        self.tape: list[dict[str, Any]] = []
        self._offset_before = offset_before
        self._offset_after = offset_after
        self._decision_after = decision_after
        self._extra_window = extra_window
        self._pending_reads = 0

    def events(self, after_offset: int = 0) -> dict[str, Any]:
        self.tape.append({"message_type": "get_midgame_events"})
        payloads = [self._offset_before, self._offset_after]
        index = min(self._pending_reads, len(payloads) - 1)
        return {"latest_offset": payloads[index]}

    def pending_decision(
        self, *, attempts: int = 60, interval_s: float = 0.5
    ) -> dict[str, Any] | None:
        self.tape.append({"message_type": "get_midgame_decision"})
        self._pending_reads += 1
        return {"decision_id": self._decision_after}


DECISION: dict[str, Any] = {
    "decision_class": "mode",
    "decision_id": "dec-1",
    "actor_id": "actor-p1",
}
LEGAL: dict[str, Any] = {
    "actions": [
        {"action_id": "opt-mode-a"},
        {"action_id": "opt-mode-b"},
    ]
}


def test_a_well_formed_refusal_selects_nothing_and_proves_no_mutation() -> None:
    client = _FakeClient()
    typed = ref.refuse_pending_decision(client, DECISION, legal=LEGAL)
    document = typed.document()
    assert document["kind"] == ref.TYPED_UNSUPPORTED_DISCRETIONARY_DECISION
    assert document["well_formed"] is True
    assert document["submissions_in_window"] == []
    assert document["decision_class"] == "mode"
    assert document["offered_option_ids"] == ["opt-mode-a", "opt-mode-b"]
    assert document["state_mutated"] is False
    # Every request the refusal made is a read. Nothing was submitted.
    assert set(document["transport_window"]) <= {
        "get_midgame_decision",
        "get_midgame_events",
    }
    assert not (set(document["transport_window"]) & ref.SUBMITTING_MESSAGE_TYPES)


def test_the_typed_kind_is_not_a_timeout() -> None:
    typed = ref.refuse_pending_decision(_FakeClient(), DECISION, legal=LEGAL)
    assert typed.kind == "UNSUPPORTED_DISCRETIONARY_DECISION"
    assert "TIMEOUT" not in typed.kind


def test_a_failure_without_a_pending_frame_cannot_be_refused() -> None:
    with pytest.raises(ref.RefusalError):
        ref.refuse_pending_decision(_FakeClient(), {}, legal=LEGAL)


def test_a_frame_without_an_engine_identity_cannot_be_refused() -> None:
    with pytest.raises(ref.RefusalError):
        ref.refuse_pending_decision(
            _FakeClient(), {"decision_class": "mode", "actor_id": "a"}, legal=LEGAL
        )


def test_a_frame_without_engine_offered_options_cannot_be_refused() -> None:
    with pytest.raises(ref.RefusalError):
        ref.refuse_pending_decision(_FakeClient(), DECISION, legal={"actions": []})


def test_any_submission_in_the_refusal_window_is_rejected() -> None:
    client = _FakeClient(extra_window=("submit_midgame_decision",))
    original_events = client.events

    def events_with_submission(after_offset: int = 0) -> dict[str, Any]:
        # Simulate a handler that submitted an action during the refusal.
        client.tape.append({"message_type": "submit_midgame_decision"})
        return original_events(after_offset)

    client.events = events_with_submission  # type: ignore[method-assign]
    with pytest.raises(ref.RefusalError):
        ref.refuse_pending_decision(client, DECISION, legal=LEGAL)


def test_a_state_change_during_the_refusal_is_rejected() -> None:
    with pytest.raises(ref.RefusalError):
        ref.refuse_pending_decision(
            _FakeClient(offset_before=12, offset_after=13), DECISION, legal=LEGAL
        )


def test_a_changed_pending_decision_during_the_refusal_is_rejected() -> None:
    with pytest.raises(ref.RefusalError):
        ref.refuse_pending_decision(_FakeClient(decision_after="dec-2"), DECISION, legal=LEGAL)


# --------------------------------------------------------------------------- #
# The obligation token: a typed refusal is required, and only a typed refusal
# --------------------------------------------------------------------------- #


def _frame(**overrides: Any) -> mr.Frame:
    frame = mr.Frame("mode", "P1", ["Devil creature tokens"], refused=True)
    frame.refusal_kind = ref.TYPED_UNSUPPORTED_DISCRETIONARY_DECISION
    for key, value in overrides.items():
        setattr(frame, key, value)
    return frame


def _typed_refusal() -> ref.TypedDecisionRefusal:
    return ref.refuse_pending_decision(_FakeClient(), DECISION, legal=LEGAL)


def _refusal_document(**overrides: Any) -> dict[str, Any]:
    """A refusal document with overrides, recomputing well_formed from the facts."""

    import dataclasses

    document = dataclasses.replace(_typed_refusal(), **overrides).document()
    return document


def test_fail_closed_token_requires_a_well_formed_typed_refusal() -> None:
    token = "fail_closed:UNSUPPORTED_DISCRETIONARY_DECISION"
    found = mr.verify_token(token, [], [_frame()], set(), None, [_refusal_document()])
    assert found is not None
    assert found["refusal_frame_digests"]


def test_fail_closed_token_rejects_a_timeout_relabelled_as_unsupported() -> None:
    token = "fail_closed:UNSUPPORTED_DISCRETIONARY_DECISION"
    timeout = _refusal_document(kind="DECISION_TIMEOUT")
    assert timeout["well_formed"] is False
    assert mr.verify_token(token, [], [_frame()], set(), None, [timeout]) is None


def test_fail_closed_token_rejects_a_refusal_that_mutated_state() -> None:
    token = "fail_closed:UNSUPPORTED_DISCRETIONARY_DECISION"
    mutated = _refusal_document(event_offset_after=13)
    assert mutated["state_mutated"] is True
    assert mutated["well_formed"] is False
    assert mr.verify_token(token, [], [_frame()], set(), None, [mutated]) is None


def test_fail_closed_token_rejects_a_refusal_without_a_frame() -> None:
    token = "fail_closed:UNSUPPORTED_DISCRETIONARY_DECISION"
    assert mr.verify_token(token, [], [], set(), None, [_refusal_document()]) is None


def test_fail_closed_token_rejects_a_refusal_of_a_different_kind() -> None:
    token = "fail_closed:UNSUPPORTED_DISCRETIONARY_DECISION"
    wrong = _frame(refusal_kind="SOME_OTHER_REFUSAL")
    assert mr.verify_token(token, [], [wrong], set(), None, [_refusal_document()]) is None


def test_fail_closed_token_requires_the_engine_offered_domain_to_have_existed() -> None:
    # The refusal record itself proves the frame carried engine-offered options;
    # a record without them is not well formed.
    token = "fail_closed:UNSUPPORTED_DISCRETIONARY_DECISION"
    empty = _refusal_document(offered_option_ids=())
    assert empty["well_formed"] is False
    assert mr.verify_token(token, [], [_frame()], set(), None, [empty]) is None


# --------------------------------------------------------------------------- #
# Supporting token verifiers used by the corrected fixtures
# --------------------------------------------------------------------------- #


def test_decision_frame_token_requires_an_engine_offer_set() -> None:
    token = "decision_frame:choose_mode"
    assert mr.verify_token(token, [], [mr.Frame("mode", "P1", ["a mode"])], set()) is not None
    assert mr.verify_token(token, [], [mr.Frame("mode", "P1", [])], set()) is None
    assert mr.verify_token(token, [], [mr.Frame("target", "P1", ["a target"])], set()) is None


def test_created_token_token_requires_the_exact_count_and_name() -> None:
    tape = [
        {"sequence": 1, "type": "CREATED_TOKEN", "target_name": "Devil"},
        {"sequence": 2, "type": "CREATED_TOKEN", "target_name": "Devil"},
        {"sequence": 3, "type": "CREATED_TOKEN", "target_name": "Devil"},
    ]
    assert mr.verify_token("create_Devil_token:3", tape, [], set()) is not None
    assert mr.verify_token("create_Devil_token:2", tape, [], set()) is None
    assert mr.verify_token("create_Soldier_token:3", tape, [], set()) is None
