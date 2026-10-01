"""AF05 knowledge projection: verification in both directions.

A conforming capture, shaped like the production mid-game lane's own responses,
verifies every declared row. Each mutation below is a way the boundary can be
violated or the evidence can be hollow, and each must produce exactly the class
the contract names: a demonstrated leak or a denied entitlement is a FAIL, and
anything unmeasured is UNVERIFIED, which earns nothing.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

import pytest

from commander_lab.qualification.current_boundary import knowledge_projection as kp
from commander_lab.qualification.current_boundary import receipts as receipt_mod
from commander_lab.qualification.current_boundary.materialization import (
    load_effective_materialization,
)

LABELS = ("P1", "P2", "P3", "P4")
NATIVE = {label: f"native-{label.lower()}" for label in LABELS}
HAND = {"P1": 8, "P2": 8, "P3": 7, "P4": 7}
LIBRARY = {"P1": 91, "P2": 93, "P3": 92, "P4": 92}
SENTINEL = "WS30_HONEY_P2_PRIVATE_7F3A"


@pytest.fixture(scope="module")
def records() -> dict[str, dict[str, Any]]:
    materialization = load_effective_materialization()
    return {fixture: materialization.record(fixture) for fixture in kp.ROWS}


def _view(viewer: str) -> dict[str, Any]:
    """An actor view shaped like XmageFullGameStateRedactor.actorView."""
    players = []
    for seat, label in enumerate(LABELS):
        own = label == viewer
        entry: dict[str, Any] = {
            "seat": seat,
            "player_id": NATIVE[label] if own else f"op-{seat}",
            "is_actor": own,
            "hand_count": HAND[label],
            "library_count": LIBRARY[label],
            "private_state_visible": own,
            "granted_library": [],
            "library_top_revealed": None,
            "exile": [{"name": "Sol Ring", "object_id": "exile-1"}] if label == "P2" else [],
            "exile_count": 1 if label == "P2" else 0,
            "battlefield": [],
            "command": [{"name": "Rograkh, Son of Rohgahh", "object_id": f"cmd-{seat}"}],
        }
        if own:
            hand = [{"name": "Mountain", "object_id": f"m-{i}"} for i in range(HAND[label])]
            if label == "P2":
                hand[-1] = {"name": "Demonic Tutor", "object_id": "dt"}
            entry["hand"] = hand
        if label == "P1":
            permanent: dict[str, Any] = {"face_down": True, "name": "", "object_id": "fd"}
            if viewer == "P1":
                permanent["private_identity"] = "Grizzly Bears"
            entry["battlefield"] = [permanent]
        players.append(entry)
    return {"actor_id": NATIVE[viewer], "seat": LABELS.index(viewer), "players": players}


def _projection(viewer: str) -> dict[str, Any]:
    return {
        "actor_id": viewer,
        "observation_scope": "principal_scoped",
        "projection_kind": "actor_entitled_knowledge_projection",
        "seat_labels": list(LABELS),
        "view": _view(viewer),
    }


def _frame(actor: str, decision_id: str) -> dict[str, Any]:
    return {
        "actor_id": NATIVE[actor],
        "decision_id": decision_id,
        "decision_class": "priority",
        "prompt": "Choose priority action",
        "context": {},
        "source_object": None,
        "legal_options": [
            {"option_id": "pass", "label": "Pass priority", "metadata": {}},
            {
                "option_id": "cast",
                "label": "Rograkh, Son of Rohgahh - Cast",
                "metadata": {"ability_type": "spell"},
            },
        ],
        "pilot_state": _view(actor),
    }


def _ok(payload: dict[str, Any]) -> dict[str, Any]:
    return {"success": True, "payload": payload}


def _entry(message_type: str, payload: dict[str, Any] | None, response: Any) -> dict[str, Any]:
    request: dict[str, Any] = {"message_type": message_type}
    if payload is not None:
        request["payload"] = payload
    return {"message_type": message_type, "request": request, "response": response}


CAPABILITIES = {
    "capabilities": {
        "knowledge_projection_supported": True,
        "omniscient_state_api": False,
        "raw_engine_object_graph_api": False,
        "observation_scopes": {
            "get_midgame_projection": "principal_scoped_required_requester",
            "get_midgame_state": "principal_scoped_required_requester_counts_only",
            "get_midgame_decision": "acting_principal_frame",
            "get_legal_actions": "acting_principal_frame",
            "get_midgame_events": "public_semantic_event_tape",
            "complete_midgame_arrival": (
                "principal_scoped_or_principal_neutral_opponent_hands_counts_only"
            ),
        },
    }
}
LOSSLESS = {"face_down": 1, "hand_composition": 4, "library_object": 1, "library_order": 1}


def _capture(record: dict[str, Any]) -> kp.Capture:
    scoped = {
        "construction_match": True,
        "mismatches": [],
        "lossless_hidden_checks": dict(LOSSLESS),
        "observation": {"seats": [{"player_id": "P2", "hand_count": 8, "exile": ["Sol Ring"]}]},
    }
    projections = {label: _projection(label) for label in LABELS}
    tape: list[dict[str, Any]] = [
        _entry("get_capabilities", None, _ok(copy.deepcopy(CAPABILITIES))),
        _entry(
            "create_midgame_game",
            {"requested_starting_state": record},
            _ok({"placed_objects": {"obj:hidden-hand": "dt"}}),
        ),
        # P2's own frame names P2's own hand card: P2's channel, not P1's.
        _entry("get_midgame_decision", None, _ok({"decision": _frame("P2", "d1")})),
        # P1's submission; the response carries the next actor's (P2's) frame,
        # which the harness routes to P2.
        _entry(
            "submit_midgame_decision",
            {"response": {"actor_id": NATIVE["P1"], "decision_id": "d0"}},
            _ok({"decision": _frame("P2", "d1"), "started": True}),
        ),
        _entry("get_midgame_decision", None, _ok({"decision": _frame("P1", "d2")})),
        _entry(
            "get_legal_actions",
            None,
            _ok({"actor_id": NATIVE["P1"], "decision": _frame("P1", "d2"), "actions": []}),
        ),
        _entry("complete_midgame_arrival", {"actor_id": "P1"}, _ok(copy.deepcopy(scoped))),
    ]
    for label in LABELS:
        tape.append(_entry("get_midgame_projection", {"actor_id": label}, _ok(projections[label])))
    tape.append(
        _entry(
            "get_midgame_state",
            {"actor_id": NATIVE["P1"]},
            _ok({"actor_id": NATIVE["P1"], "zone_counts": {"seats": []}}),
        )
    )
    tape.append(
        _entry(
            "get_midgame_events",
            {"after_offset": 0},
            _ok({"events": [{"type": "BEGIN_TURN", "player_player": "P1"}], "latest_offset": 1}),
        )
    )
    attempts = []
    for message_type, payload in kp.OMNISCIENCE_ATTEMPTS:
        response = {"success": False, "errors": [{"code": "refused", "message": "no"}]}
        tape.append(_entry(message_type, payload, response))
        attempts.append(
            {
                "message_type": message_type,
                "payload": payload,
                "success": False,
                "error_code": "refused",
            }
        )
    return kp.Capture(
        arrival_verdict="EXACT",
        arrival_mismatches=[],
        checkpoint_decision=_frame("P1", "d2"),
        scoped_arrival=scoped,
        projections=projections,
        natives=dict(NATIVE),
        viewer_state={"actor_id": NATIVE["P1"]},
        events={"events": []},
        capabilities=copy.deepcopy(CAPABILITIES),
        attempts=attempts,
        tape=tape,
        log="log4j:WARN No appenders could be found for logger (mage.util.ClassScanner).\n",
    )


def _verdict(
    records: dict[str, dict[str, Any]],
    fixture: str,
    mutate: Callable[[kp.Capture], None] | None = None,
) -> kp.RowVerdict:
    capture = _capture(records[fixture])
    if mutate is not None:
        mutate(capture)
    return kp.verify(records[fixture], capture, viewer="P1")


def _failed(verdict: kp.RowVerdict) -> list[str]:
    return [check.name for check in verdict.checks if not check.holds]


# --------------------------------------------------------------------------- #
# The record says what each principal may know
# --------------------------------------------------------------------------- #


def test_the_record_derives_forbidden_tokens_and_requested_counts(
    records: dict[str, dict[str, Any]],
) -> None:
    record = records["HIDDEN_01"]
    tokens = kp.forbidden_tokens(record, "P1")
    assert set(tokens.tokens) == {
        "Demonic Tutor",
        "obj:hidden-hand",
        "Vampiric Tutor",
        "obj:hidden-lib-0",
        SENTINEL,
    }
    # P1 controls the face-down permanent and may see it; P3 may not.
    assert "Grizzly Bears" not in kp.forbidden_tokens(record, "P1").tokens
    assert "Grizzly Bears" in kp.forbidden_tokens(record, "P3").tokens
    # The owner may see its own hand card but nobody may see a library card.
    p2 = kp.forbidden_tokens(record, "P2").tokens
    assert "Demonic Tutor" not in p2 and "Vampiric Tutor" in p2
    assert kp.expected_hand_counts(record) == HAND
    assert kp.expected_library_counts(record) == {"P2": 93}
    assert kp.expected_lossless_checks(record) == LOSSLESS
    assert kp.honey_bindings(record) == {SENTINEL: "Demonic Tutor"}


def test_an_identity_also_visible_elsewhere_cannot_decide_and_is_set_aside(
    records: dict[str, dict[str, Any]],
) -> None:
    record = copy.deepcopy(records["HIDDEN_01"])
    exile = next(o for o in record["semantic_objects"] if o["zone"] == "exile")
    exile["card_identity"] = "Demonic Tutor"
    tokens = kp.forbidden_tokens(record, "P1")
    assert "Demonic Tutor" not in tokens.tokens
    assert "Demonic Tutor" in tokens.ambiguous


def test_every_declared_row_is_bound_to_its_records_own_obligation(
    records: dict[str, dict[str, Any]],
) -> None:
    for fixture, kind in kp.ROWS.items():
        state = records[fixture]["knowledge_state"]["viewer_states"][0]
        assert state["viewer"] == "P1"
        assert state["obligation"] == kp.OBLIGATION_TEXT[kind]
        assert records[fixture]["expected_events"]["required_events"] == [
            f"knowledge_projection:{fixture}:P1"
        ]


# --------------------------------------------------------------------------- #
# Positive: a conforming lane verifies every row
# --------------------------------------------------------------------------- #


def test_a_conforming_capture_verifies_every_declared_row(
    records: dict[str, dict[str, Any]],
) -> None:
    for fixture in kp.ROWS:
        verdict = _verdict(records, fixture)
        assert verdict.classification == kp.VERIFIED, (fixture, _failed(verdict))
        assert verdict.token_evidence[f"knowledge_projection:{fixture}:P1"]
        assert verdict.forbidden_evidence[f"leak:{SENTINEL}"]["occurrences"] == []


def test_a_frame_belongs_to_its_actor_whichever_response_carries_it(
    records: dict[str, dict[str, Any]],
) -> None:
    capture = _capture(records["HIDDEN_01"])
    p1 = kp.principal_documents(capture.tape, "P1", capture.natives)
    p2 = kp.principal_documents(capture.tape, "P2", capture.natives)
    frames_p1 = {frame["decision_id"] for frame in kp.frames_of(p1)}
    frames_p2 = {frame["decision_id"] for frame in kp.frames_of(p2)}
    assert frames_p1 == {"d2"}
    assert frames_p2 == {"d1"}
    # The harness control plane carries the requested state and is nobody's channel.
    channels = {item.channel for item in kp.addressed_documents(capture.tape, capture.natives)}
    assert not any("create_midgame_game" in channel for channel in channels)


# --------------------------------------------------------------------------- #
# Demonstrated leaks are FAIL
# --------------------------------------------------------------------------- #


def test_an_opponent_hand_in_the_viewers_projection_is_a_demonstrated_leak(
    records: dict[str, dict[str, Any]],
) -> None:
    def leak(capture: kp.Capture) -> None:
        p2 = capture.projections["P1"]["view"]["players"][1]
        p2["hand"] = [{"name": "Demonic Tutor"}]

    verdict = _verdict(records, "HIDDEN_01", leak)
    assert verdict.classification == kp.FAIL_DEMONSTRATED_LEAK
    assert "opponent_hand_hidden:P2" in _failed(verdict)


def test_a_sentinel_in_the_process_log_is_a_demonstrated_leak(
    records: dict[str, dict[str, Any]],
) -> None:
    def leak(capture: kp.Capture) -> None:
        capture.log += f"restoring {SENTINEL}\n"

    verdict = _verdict(records, "HIDDEN_HONEYCARD_SENTINEL", leak)
    assert verdict.classification == kp.FAIL_DEMONSTRATED_LEAK
    hits = verdict.forbidden_evidence[f"leak:{SENTINEL}"]["occurrences"]
    assert hits == [{"channel_path": "log", "token": SENTINEL}]


def test_a_foreign_hand_inside_the_viewers_own_frame_is_a_demonstrated_leak(
    records: dict[str, dict[str, Any]],
) -> None:
    """The wrong-reason control for per-frame addressing: a frame addressed to
    P1 that embeds P2's view is caught by the frame check and by the scan."""

    def leak(capture: kp.Capture) -> None:
        frame = _frame("P1", "d9")
        frame["pilot_state"] = _view("P2")
        capture.tape.append(_entry("get_midgame_decision", None, _ok({"decision": frame})))

    for fixture in ("HIDDEN_19", "HIDDEN_HONEYCARD_SENTINEL"):
        verdict = _verdict(records, fixture, leak)
        assert verdict.classification == kp.FAIL_DEMONSTRATED_LEAK, fixture
        assert "no_forbidden_token_in_channels_of:P1" in _failed(verdict)
    assert "frame_carries_only_its_actor:d9" in _failed(_verdict(records, "HIDDEN_19", leak))


def test_a_library_card_shown_to_any_principal_is_a_demonstrated_leak(
    records: dict[str, dict[str, Any]],
) -> None:
    def leak(capture: kp.Capture) -> None:
        # Even the owner is not entitled to its library's identities.
        own = capture.projections["P2"]["view"]["players"][1]
        own["granted_library"] = [{"name": "Vampiric Tutor"}]

    verdict = _verdict(records, "HIDDEN_02", leak)
    assert verdict.classification == kp.FAIL_DEMONSTRATED_LEAK
    assert "library_object_unseen_by:P2" in _failed(verdict)


def test_a_face_down_identity_shown_to_an_opponent_is_a_demonstrated_leak(
    records: dict[str, dict[str, Any]],
) -> None:
    def leak(capture: kp.Capture) -> None:
        permanent = capture.projections["P3"]["view"]["players"][0]["battlefield"][0]
        permanent["private_identity"] = "Grizzly Bears"

    verdict = _verdict(records, "HIDDEN_04", leak)
    assert verdict.classification == kp.FAIL_DEMONSTRATED_LEAK
    assert "face_down_identity_withheld:obj:facedown:P3" in _failed(verdict)


def test_a_served_omniscient_request_is_a_demonstrated_leak(
    records: dict[str, dict[str, Any]],
) -> None:
    def served(capture: kp.Capture) -> None:
        capture.attempts[0]["success"] = True

    verdict = _verdict(records, "HIDDEN_19", served)
    assert verdict.classification == kp.FAIL_DEMONSTRATED_LEAK


# --------------------------------------------------------------------------- #
# Denied entitlements are FAIL
# --------------------------------------------------------------------------- #


def test_a_wrong_opponent_hand_count_is_a_denied_entitlement(
    records: dict[str, dict[str, Any]],
) -> None:
    def wrong(capture: kp.Capture) -> None:
        capture.projections["P1"]["view"]["players"][1]["hand_count"] = 7

    verdict = _verdict(records, "HIDDEN_01", wrong)
    assert verdict.classification == kp.FAIL_ENTITLEMENT_DENIED
    assert "opponent_hand_count_visible:P2" in _failed(verdict)


def test_the_controller_not_shown_its_face_down_identity_is_a_denied_entitlement(
    records: dict[str, dict[str, Any]],
) -> None:
    def withheld(capture: kp.Capture) -> None:
        permanent = capture.projections["P1"]["view"]["players"][0]["battlefield"][0]
        del permanent["private_identity"]

    verdict = _verdict(records, "HIDDEN_04", withheld)
    assert verdict.classification == kp.FAIL_ENTITLEMENT_DENIED


def test_a_hidden_public_exile_card_is_a_denied_entitlement(
    records: dict[str, dict[str, Any]],
) -> None:
    def hidden(capture: kp.Capture) -> None:
        capture.projections["P4"]["view"]["players"][1]["exile"] = []

    verdict = _verdict(records, "HIDDEN_03", hidden)
    assert verdict.classification == kp.FAIL_ENTITLEMENT_DENIED
    assert "public_exile_visible:obj:public-exile:P4" in _failed(verdict)


# --------------------------------------------------------------------------- #
# Anything unmeasured is UNVERIFIED, never PASS
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("name", "mutate"),
    [
        (
            "a lossless check that never ran",
            lambda c: c.scoped_arrival["lossless_hidden_checks"].pop("face_down"),
        ),
        ("an inexact construction", lambda c: setattr(c, "arrival_verdict", "MISMATCH")),
        ("a construction mismatch", lambda c: c.scoped_arrival.update(mismatches=["x"])),
        (
            "frames without prompts or options",
            lambda c: c.tape.__setitem__(
                slice(None),
                [
                    e
                    for e in c.tape
                    if e["message_type"]
                    not in {"get_midgame_decision", "get_legal_actions", "submit_midgame_decision"}
                ],
            ),
        ),
        ("a lane failure", lambda c: setattr(c, "failure", "lane failed closed")),
        (
            "an unbound projection",
            lambda c: c.projections["P2"].update(seat_labels=["P1", "P2", "P3"]),
        ),
    ],
)
def test_unmeasured_evidence_is_unverified_never_a_pass(
    records: dict[str, dict[str, Any]], name: str, mutate: Callable[[kp.Capture], None]
) -> None:
    for fixture in kp.ROWS:
        verdict = _verdict(records, fixture, mutate)
        assert verdict.classification == kp.UNVERIFIED, (name, fixture, _failed(verdict))


def test_a_leak_on_an_inexact_construction_is_not_attributed(
    records: dict[str, dict[str, Any]],
) -> None:
    """Without the requested state, a hit cannot be attributed to the boundary."""

    def both(capture: kp.Capture) -> None:
        capture.arrival_verdict = "MISMATCH"
        capture.log += SENTINEL

    assert _verdict(records, "HIDDEN_01", both).classification == kp.UNVERIFIED


def test_the_positive_controls_must_find_what_the_scan_looks_for(
    records: dict[str, dict[str, Any]],
) -> None:
    def hollow(capture: kp.Capture) -> None:
        own = capture.projections["P2"]["view"]["players"][1]
        own["hand"] = [{"name": "Mountain"} for _ in range(8)]

    verdict = _verdict(records, "HIDDEN_HONEYCARD_SENTINEL", hollow)
    assert verdict.classification == kp.UNVERIFIED
    assert "scanner_detects_honey_identity_where_entitled" in _failed(verdict)


def test_a_record_naming_another_obligation_is_not_verified(
    records: dict[str, dict[str, Any]],
) -> None:
    record = copy.deepcopy(records["HIDDEN_01"])
    record["knowledge_state"]["viewer_states"][0]["obligation"] = "something else"
    verdict = kp.verify(record, _capture(record), viewer="P1")
    assert verdict.classification == kp.UNVERIFIED


# --------------------------------------------------------------------------- #
# Receipts and the FAIL hand-off
# --------------------------------------------------------------------------- #


def test_a_verified_row_yields_a_creditable_bound_receipt(
    records: dict[str, dict[str, Any]],
) -> None:
    record = records["HIDDEN_01"]
    verdict = _verdict(records, "HIDDEN_01")
    receipt = kp.positive_receipt(
        verdict,
        record,
        candidate_commit="c" * 40,
        runner_digest="runner",
        execution_document=verdict.document(),
    )
    assert receipt["test_identity"] == "midgame-lane:knowledge-projection#HIDDEN_01"
    credited = receipt_mod.positive_fixture_credit(
        [receipt],
        candidate="xmage",
        expected_commit="c" * 40,
        denominator={"HIDDEN_01": record},
        expected_runner_digest="runner",
    )
    assert credited == {"HIDDEN_01": ["midgame-lane:knowledge-projection#HIDDEN_01"]}
    for commit, runner in (("d" * 40, "runner"), ("c" * 40, "other")):
        assert not receipt_mod.positive_fixture_credit(
            [receipt],
            candidate="xmage",
            expected_commit=commit,
            denominator={"HIDDEN_01": record},
            expected_runner_digest=runner,
        )


def test_an_unverified_row_has_no_receipt(records: dict[str, dict[str, Any]]) -> None:
    verdict = _verdict(records, "HIDDEN_01", lambda c: setattr(c, "arrival_verdict", None))
    with pytest.raises(ValueError):
        kp.positive_receipt(
            verdict,
            records["HIDDEN_01"],
            candidate_commit="c" * 40,
            runner_digest="runner",
            execution_document={},
        )


def test_demonstrated_failures_count_only_from_a_bound_document() -> None:
    document = {
        "schema_version": kp.EXECUTIONS_SCHEMA,
        "candidate_commit": "c" * 40,
        "runner_digest": "runner",
        "rows": {
            "HIDDEN_01": {
                "classification": kp.FAIL_DEMONSTRATED_LEAK,
                "engine_commit": "c" * 40,
                "checks": [{"name": "x", "holds": False}, {"name": "y", "holds": True}],
            },
            "HIDDEN_02": {"classification": kp.UNVERIFIED, "engine_commit": "c" * 40},
        },
    }
    failures = kp.demonstrated_failures(document, candidate_commit="c" * 40, runner_digest="runner")
    assert failures == {
        "HIDDEN_01": {
            "classification": kp.FAIL_DEMONSTRATED_LEAK,
            "failed_checks": [{"name": "x", "holds": False}],
        }
    }
    assert not kp.demonstrated_failures(document, candidate_commit="d" * 40, runner_digest="runner")
    assert not kp.demonstrated_failures(document, candidate_commit="c" * 40, runner_digest="other")
    assert not kp.demonstrated_failures(None, candidate_commit="c" * 40, runner_digest="runner")
