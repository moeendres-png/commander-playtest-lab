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


def _search_frame(actor: str) -> dict[str, Any]:
    names = ["Vampiric Tutor"] + ["Mountain"] * (LIBRARY["P2"] - 1)
    return {
        "actor_id": NATIVE[actor],
        "decision_id": f"search-{actor}",
        "decision_class": "target",
        "prompt": "Select a card",
        "context": {"targeted": True},
        "source_object": None,
        "legal_options": [
            {
                "option_id": f"lib-{index}",
                "label": name,
                "metadata": {"name": name, "zone": "library", "zone_index": index},
            }
            for index, name in enumerate(names)
        ],
        "pilot_state": _view(actor),
    }


def _library_frame(actor: str, names: list[str], prompt: str) -> dict[str, Any]:
    return {
        "actor_id": NATIVE[actor],
        "decision_id": f"lib-{actor}-{prompt[:8]}",
        "decision_class": "target",
        "prompt": prompt,
        "context": {},
        "source_object": None,
        "legal_options": [
            {
                "option_id": f"lib-{index}",
                "label": name,
                "metadata": {"name": name, "zone": "library", "zone_index": index},
            }
            for index, name in enumerate(names)
        ],
        "pilot_state": _view(actor),
    }


def _pile_frame(actor: str) -> dict[str, Any]:
    return {
        "actor_id": NATIVE[actor],
        "decision_id": f"pile-{actor}",
        "decision_class": "pile",
        "prompt": "Choose a pile to put into hand.",
        "context": {},
        "source_object": None,
        "legal_options": [
            {"option_id": "pile-1", "label": "Pile 1", "metadata": {}},
            {"option_id": "pile-2", "label": "Pile 2", "metadata": {}},
        ],
        "pilot_state": _view(actor),
    }


def _target_frame(label: str = "") -> dict[str, Any]:
    return {
        "actor_id": NATIVE["P1"],
        "decision_id": "target-p1",
        "decision_class": "target",
        "prompt": "Select any target",
        "context": {"targeted": True},
        "source_object": None,
        "legal_options": [
            {
                "option_id": "p2-fd",
                "label": label,
                "metadata": {"name": label, "zone": "battlefield"},
            }
        ],
        "pilot_state": _view("P1"),
    }


def _ward_frame(source_name: str = "", **extra: Any) -> dict[str, Any]:
    """P1's ward payment frame, sourced by P2's face-down permanent."""
    return {
        "actor_id": NATIVE["P1"],
        "decision_id": "ward-p1",
        "decision_class": "choose_use",
        "prompt": "Pay {2}?",
        "context": {"outcome": "benefit"},
        "source_object": {
            "source_object_id": "p2-fd",
            "ability_original_id": "ward-ability",
            "ability_type": "triggered_nonmana",
            "source_name": source_name,
            **extra,
        },
        "legal_options": [
            {"option_id": "yes", "label": "Yes", "metadata": {"value": True}},
            {"option_id": "no", "label": "No", "metadata": {"value": False}},
        ],
        "pilot_state": _view("P1"),
    }


def _without_p2_hand_card(value: Any) -> None:
    """Replace P2's requested hand card by a template card everywhere."""
    if isinstance(value, dict):
        if value.get("object_id") == "dt" and value.get("name") == "Demonic Tutor":
            value["name"] = "Mountain"
        for item in value.values():
            _without_p2_hand_card(item)
    elif isinstance(value, list):
        for item in value:
            _without_p2_hand_card(item)


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
        # The engine runs one lossless check per requested library, library
        # object, hand and typed face-down object (two libraries for a row
        # that also requests the viewer's own library top).
        "lossless_hidden_checks": dict(LOSSLESS)
        if kp.expected_lossless_checks(record) == LOSSLESS
        else kp.expected_lossless_checks(record),
        "observation": {"seats": [{"player_id": "P2", "hand_count": 8, "exile": ["Sol Ring"]}]},
    }
    projections = {label: _projection(label) for label in LABELS}
    kind = kp.ROWS.get(str(record["fixture_id"]))
    # The record's scripted event, as the engine logs it in each projection.
    if kind == "reveal_audience":
        for label in LABELS:
            projections[label]["view"]["revealed"] = [
                {"title": "Cards in Full Game Seat 2's hand", "cards": [{"name": "Demonic Tutor"}]}
            ]
    if kind in ("look_audience", "transcript_privacy"):
        projections["P1"]["view"]["looked_at"] = [
            {"title": "Orcish Spy", "cards": [{"name": "Vampiric Tutor"}, {"name": "Mountain"}]}
        ]
    if kind == "shuffle_invalidates_order":
        projections["P1"]["view"]["looked_at"] = [
            {
                "title": "Orcish Spy",
                "order_invalidated_by_shuffle": True,
                "cards": [
                    {"name": "Enlightened Tutor"},
                    {"name": "Mystical Tutor"},
                    {"name": "Vampiric Tutor"},
                ],
            }
        ]
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
    script_start = len(tape) if record.get("decision_script") else None
    if kind == "copy_face_down":
        # P2's manifested permanent; P1's copy choice offering it without its
        # identity; P1's copy with only the face-down characteristics.
        for label in LABELS:
            projections[label]["view"]["players"][1]["battlefield"] = [
                {"face_down": True, "name": "", "object_id": "p2-fd"}
            ]
        projections["P1"]["view"]["players"][0]["battlefield"].append(
            {"face_down": False, "name": "", "object_id": "copy", "power": 2, "toughness": 2}
        )
        frame = _target_frame()
        frame["decision_class"] = "choose_object"
        tape.append(_entry("get_midgame_decision", None, _ok({"decision": frame})))
    if kind == "target_metadata":
        # P2's manifested permanent, as P1's own projection shows it, and P1's
        # target frame offering it with its public face-down characteristics.
        for label in LABELS:
            projections[label]["view"]["players"][1]["battlefield"] = [
                {"face_down": True, "name": "", "object_id": "p2-fd"}
            ]
        tape.append(_entry("get_midgame_decision", None, _ok({"decision": _target_frame()})))
    if kind == "search_inspection":
        # The searcher's own frame offers its whole library, as XMage's
        # library-card choice does.
        tape.append(_entry("get_midgame_decision", None, _ok({"decision": _search_frame("P2")})))
    if kind == "scry_knowledge":
        # P1's own scry frame offers exactly its top two library cards.
        tape.append(
            _entry(
                "get_midgame_decision",
                None,
                _ok({"decision": _library_frame("P1", ["Counterspell", "Brainstorm"], "Scry")}),
            )
        )
    if kind == "pile_metadata":
        # Fact or Fiction reveals five cards to every player; P2 splits them,
        # P1 chooses a pile.
        revealed = ["Counterspell", "Brainstorm", "Ponder", "Preordain", "Opt"]
        for label in LABELS:
            projections[label]["view"]["revealed"] = [
                {"title": "Fact or Fiction", "cards": [{"name": name} for name in revealed]}
            ]
        split = _library_frame("P2", revealed, "Select cards to put in the first pile")
        split["decision_class"] = "choose_object"
        tape.append(_entry("get_midgame_decision", None, _ok({"decision": split})))
        tape.append(_entry("get_midgame_decision", None, _ok({"decision": _pile_frame("P1")})))
    events: list[dict[str, Any]] = [
        {"type": "ZONE_CHANGE", "from": "LIBRARY", "to": "LIBRARY", "player_player": "P1"}
        for _ in range(2 if kind == "scry_knowledge" else 0)
    ]
    temporal_snapshots: list[dict[str, Any]] = []
    if kind == "shuffle_invalidates_order":
        pre_projection = copy.deepcopy(projections["P1"])
        pre_projection["view"]["looked_at"] = [
            {
                "title": "Orcish Spy",
                "cards": [
                    {"name": "Vampiric Tutor"},
                    {"name": "Mystical Tutor"},
                    {"name": "Enlightened Tutor"},
                ],
            }
        ]
        temporal_snapshots.append(
            {
                "causal_step_id": "elixir-shuffle",
                "script_position": 2,
                "tape_index": len(tape),
                "projection": pre_projection,
                "events": {"events": []},
            }
        )
        events.append(
            {
                "sequence": 10,
                "type": "LIBRARY_SHUFFLED",
                "player_player": "P2",
                "target_player": "P2",
                "public_identity": True,
            }
        )
    if kind == "exile_permission_persists":
        # Gonti exiles P2's library card face down; P1 alone may look at it,
        # and still does after P2's Bolt has destroyed Gonti.
        projections["P1"]["view"]["players"][1]["exile"].append(
            {"name": "Demonic Tutor", "object_id": "dt-exiled", "face_down": True}
        )
        for label in LABELS:
            projections[label]["view"]["players"][1]["exile_count"] = 2
        events += [
            {
                "type": "ZONE_CHANGE",
                "from": "LIBRARY",
                "to": "EXILED",
                "public_identity": False,
                "player_player": "P2",
                "source_object": "obj:hidden05-gonti",
                "source_name": "Gonti, Lord of Luxury",
            },
            {
                "type": "ZONE_CHANGE",
                "from": "BATTLEFIELD",
                "to": "GRAVEYARD",
                "public_identity": True,
                "player_player": "P1",
                "target_object": "obj:hidden05-gonti",
                "target_name": "Gonti, Lord of Luxury",
            },
        ]
    controlled_decision: dict[str, Any] | None = None
    controlled_submission: dict[str, Any] | None = None
    if kind == "exile_permission_invalidates":
        pre_projections = {label: copy.deepcopy(projections[label]) for label in LABELS}
        pre_projections["P1"]["view"]["players"][1]["exile"].append(
            {"name": "Memnite", "object_id": "memnite-exiled", "face_down": True}
        )
        for label in LABELS:
            pre_projections[label]["view"]["players"][1]["exile_count"] = 2
        grant = {
            "sequence": 3,
            "type": "ZONE_CHANGE",
            "from": "LIBRARY",
            "to": "EXILED",
            "public_identity": False,
            "player_player": "P2",
            "source_object": "obj:hidden06-gonti",
            "source_name": "Gonti, Lord of Luxury",
        }
        departure = {
            "sequence": 7,
            "type": "ZONE_CHANGE",
            "from": "EXILED",
            "to": "STACK",
            "public_identity": True,
            "player_player": "P2",
            "target_name": "Memnite",
        }
        temporal_snapshots.append(
            {
                "causal_step_id": "cast-exiled-card",
                "script_position": 3,
                "tape_index": len(tape),
                "projection": copy.deepcopy(pre_projections["P1"]),
                "projections": pre_projections,
                "events": {"events": [grant]},
            }
        )
        events.extend([grant, departure])
        for label in LABELS:
            projections[label]["view"]["players"][0]["battlefield"].append(
                {"name": "Memnite", "object_id": "memnite-new-object", "face_down": False}
            )

    if kind == "controlled_player_authority":
        p1_view = copy.deepcopy(projections["P1"]["view"])
        p2_row = p1_view["players"][1]
        p2_row["private_state_visible"] = True
        p2_row["hand"] = [{"name": "Demonic Tutor", "object_id": "dt-controlled"}]
        controlled_decision = _frame("P1", "controlled-p2")
        controlled_decision["seat"] = 0
        controlled_decision["acting_for_seat"] = 1
        controlled_decision["pilot_state"] = p1_view
        controlled_decision["legal_options"] = [
            {
                "option_id": "controlled-pass",
                "option_type": "pass_priority",
                "label": "Pass priority",
                "metadata": {},
            }
        ]
        controlled_submission = {
            "decision_id": "controlled-p2",
            "actor_id": NATIVE["P1"],
            "selected_option_id": "controlled-pass",
            "accepted": True,
        }
        tape.append(
            _entry("get_midgame_decision", None, _ok({"decision": controlled_decision}))
        )
        tape.append(
            _entry(
                "submit_midgame_decision",
                {
                    "response": {
                        "decision_id": "controlled-p2",
                        "actor_id": NATIVE["P1"],
                        "selected_option_ids": ["controlled-pass"],
                    }
                },
                _ok({}),
            )
        )
        projections["P1"]["view"] = copy.deepcopy(p1_view)

    if kind in ("source_metadata", "ability_metadata"):
        # P2's cloaked permanent (P2 may look at it); P1 targets it and its ward
        # trigger asks P1 to pay {2}.
        for label in LABELS:
            permanent: dict[str, Any] = {
                "face_down": True,
                "name": "",
                "object_id": "p2-fd",
                "abilities": [],
            }
            if label == "P2":
                permanent["private_identity"] = "Vampiric Tutor"
            projections[label]["view"]["players"][1]["battlefield"] = [permanent]
        tape.append(_entry("get_midgame_decision", None, _ok({"decision": _ward_frame()})))
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
    if kind == "exile_permission_persists":
        _without_p2_hand_card(tape)
    return kp.Capture(
        arrival_verdict="EXACT",
        arrival_mismatches=[],
        checkpoint_decision=_frame("P1", "d2"),
        scoped_arrival=scoped,
        projections=projections,
        natives=dict(NATIVE),
        viewer_state={"actor_id": NATIVE["P1"]},
        events={"events": events},
        capabilities=copy.deepcopy(CAPABILITIES),
        attempts=attempts,
        tape=tape,
        log="log4j:WARN No appenders could be found for logger (mage.util.ClassScanner).\n",
        script_start=script_start,
        script_trace=[{"decision_class": "priority", "step": 0}] if script_start else [],
        script_complete=script_start is not None,
        temporal_snapshots=temporal_snapshots,
        controlled_decision=controlled_decision,
        controlled_submission=controlled_submission,
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


def _remove_one_lossless_check(capture: kp.Capture) -> None:
    checks = capture.scoped_arrival["lossless_hidden_checks"]
    assert checks
    checks.pop(sorted(checks)[0])


@pytest.mark.parametrize(
    ("name", "mutate"),
    [
        (
            "a lossless check that never ran",
            _remove_one_lossless_check,
        ),
        ("an inexact construction", lambda c: setattr(c, "arrival_verdict", "MISMATCH")),
        ("a construction mismatch", lambda c: c.scoped_arrival.update(mismatches=["x"])),
        (
            "frames without prompts or options",
            # In place, so the tape keeps its length and the event boundary.
            lambda c: c.tape.__setitem__(
                slice(None),
                [
                    _entry("get_provider_version", None, _ok({}))
                    if e["message_type"]
                    in {"get_midgame_decision", "get_legal_actions", "submit_midgame_decision"}
                    else e
                    for e in c.tape
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


# --------------------------------------------------------------------------- #
# Scripted events: a reveal reaches everyone, a look reaches only its viewer
# --------------------------------------------------------------------------- #


def test_a_reveal_that_misses_a_principal_is_a_denied_entitlement(
    records: dict[str, dict[str, Any]],
) -> None:
    def missed(capture: kp.Capture) -> None:
        capture.projections["P3"]["view"]["revealed"] = []

    verdict = _verdict(records, "HIDDEN_07", missed)
    assert verdict.classification == kp.FAIL_ENTITLEMENT_DENIED
    assert "reveal_reaches:obj:hidden-hand:P3" in _failed(verdict)


def test_a_look_shown_to_another_principal_is_a_demonstrated_leak(
    records: dict[str, dict[str, Any]],
) -> None:
    def leaked(capture: kp.Capture) -> None:
        capture.projections["P3"]["view"]["looked_at"] = [{"cards": [{"name": "Vampiric Tutor"}]}]

    verdict = _verdict(records, "HIDDEN_08", leaked)
    assert verdict.classification == kp.FAIL_DEMONSTRATED_LEAK
    assert "look_withheld_from:obj:hidden-lib-0:P3" in _failed(verdict)


def test_a_permission_does_not_reach_back_before_its_event(
    records: dict[str, dict[str, Any]],
) -> None:
    """The look entitles P1 only after it happened: the same identity in a
    frame P1 received before the event is a leak."""

    def early(capture: kp.Capture) -> None:
        frame = _frame("P1", "d0")
        frame["pilot_state"]["players"][1]["granted_library"] = [{"name": "Vampiric Tutor"}]
        capture.tape.insert(2, _entry("get_midgame_decision", None, _ok({"decision": frame})))
        assert capture.script_start is not None
        capture.script_start += 1

    verdict = _verdict(records, "HIDDEN_08", early)
    assert verdict.classification == kp.FAIL_DEMONSTRATED_LEAK
    assert "no_forbidden_token_in_channels_of:P1" in _failed(verdict)


def test_an_event_that_never_ran_is_unverified_not_denied(
    records: dict[str, dict[str, Any]],
) -> None:
    def never(capture: kp.Capture) -> None:
        capture.script_complete = False
        for label in LABELS:
            capture.projections[label]["view"]["revealed"] = []

    verdict = _verdict(records, "HIDDEN_07", never)
    assert verdict.classification == kp.UNVERIFIED


# --------------------------------------------------------------------------- #
# Search inspection and transcript privacy
# --------------------------------------------------------------------------- #


def _replace_entry(capture: kp.Capture, find: Callable[[dict[str, Any]], bool], entry: Any) -> None:
    index = next(i for i, item in enumerate(capture.tape) if find(item))
    capture.tape[index] = entry


def _is_search(item: dict[str, Any]) -> bool:
    decision = (item.get("response") or {}).get("payload", {}).get("decision") or {}
    return str(decision.get("decision_id", "")).startswith("search-")


def test_a_search_offered_to_another_principal_is_a_leak(
    records: dict[str, dict[str, Any]],
) -> None:
    def offer_to_p3(capture: kp.Capture) -> None:
        frame = _search_frame("P3")
        for option in frame["legal_options"]:
            option["label"] = option["metadata"]["name"] = "Mountain"
        capture.tape.append(_entry("get_midgame_decision", None, _ok({"decision": frame})))

    verdict = _verdict(records, "HIDDEN_09", offer_to_p3)
    assert verdict.classification == kp.FAIL_DEMONSTRATED_LEAK
    assert _failed(verdict) == ["no_search_offer_to:P3"]


def test_a_searched_identity_in_the_viewers_channels_is_a_leak(
    records: dict[str, dict[str, Any]],
) -> None:
    def route_to_p1(capture: kp.Capture) -> None:
        _replace_entry(
            capture,
            _is_search,
            _entry("get_midgame_decision", None, _ok({"decision": _search_frame("P1")})),
        )

    verdict = _verdict(records, "HIDDEN_09", route_to_p1)
    assert verdict.classification == kp.FAIL_DEMONSTRATED_LEAK
    assert "no_search_offer_to:P1" in _failed(verdict)
    assert "no_forbidden_token_in_channels_of:P1" in _failed(verdict)


def test_a_search_that_hides_the_library_from_the_searcher_is_denied(
    records: dict[str, dict[str, Any]],
) -> None:
    def truncated(capture: kp.Capture) -> None:
        frame = _search_frame("P2")
        frame["legal_options"] = frame["legal_options"][1:]
        _replace_entry(
            capture, _is_search, _entry("get_midgame_decision", None, _ok({"decision": frame}))
        )

    verdict = _verdict(records, "HIDDEN_09", truncated)
    assert verdict.classification == kp.FAIL_ENTITLEMENT_DENIED
    assert _failed(verdict) == ["search_inspects_whole_zone:P2"]


def test_a_private_identity_in_the_public_event_tape_is_a_leak(
    records: dict[str, dict[str, Any]],
) -> None:
    def public_event(capture: kp.Capture) -> None:
        _replace_entry(
            capture,
            lambda item: item.get("message_type") == "get_midgame_events",
            _entry(
                "get_midgame_events",
                {"after_offset": 0},
                _ok({"events": [{"type": "LOOKED_AT", "card": "Vampiric Tutor"}]}),
            ),
        )

    verdict = _verdict(records, "HIDDEN_18", public_event)
    assert verdict.classification == kp.FAIL_DEMONSTRATED_LEAK
    failed = _failed(verdict)
    assert "public_transcript_omits_private_state" in failed
    assert {"no_forbidden_token_in_channels_of:P2", "no_forbidden_token_in_channels_of:P3"} <= set(
        failed
    )


def test_private_knowledge_the_viewer_never_received_is_denied(
    records: dict[str, dict[str, Any]],
) -> None:
    def never_looked(capture: kp.Capture) -> None:
        capture.projections["P1"]["view"]["looked_at"] = []

    verdict = _verdict(records, "HIDDEN_18", never_looked)
    assert verdict.classification == kp.FAIL_ENTITLEMENT_DENIED
    assert _failed(verdict) == ["private_knowledge_reaches:obj:hidden-lib-0:P1"]


def test_known_identities_entitle_the_viewer_only_after_the_event(
    records: dict[str, dict[str, Any]],
) -> None:
    record = records["HIDDEN_18"]
    assert "Vampiric Tutor" in kp.forbidden_tokens(record, "P1").tokens
    assert "Vampiric Tutor" not in kp.forbidden_tokens(record, "P1", after_event=True).tokens
    assert "Vampiric Tutor" in kp.forbidden_tokens(record, "P2", after_event=True).tokens


def test_a_hidden_target_named_in_its_option_is_a_leak(
    records: dict[str, dict[str, Any]],
) -> None:
    def named(capture: kp.Capture) -> None:
        _replace_entry(
            capture,
            lambda item: (
                (item.get("response") or {})
                .get("payload", {})
                .get("decision", {})
                .get("decision_id")
                == "target-p1"
            ),
            _entry(
                "get_midgame_decision", None, _ok({"decision": _target_frame("Vampiric Tutor")})
            ),
        )

    verdict = _verdict(records, "HIDDEN_14", named)
    assert verdict.classification == kp.FAIL_DEMONSTRATED_LEAK
    assert set(_failed(verdict)) == {
        "no_forbidden_token_in_channels_of:P1",
        "hidden_target_option_carries_no_identity:p2-fd",
    }


def test_a_target_frame_that_never_offers_the_hidden_permanent_is_unverified(
    records: dict[str, dict[str, Any]],
) -> None:
    def no_offer(capture: kp.Capture) -> None:
        for label in LABELS:
            capture.projections[label]["view"]["players"][1]["battlefield"] = []

    verdict = _verdict(records, "HIDDEN_14", no_offer)
    assert verdict.classification == kp.UNVERIFIED
    assert _failed(verdict) == ["hidden_target_offered:P1"]


def test_a_copy_that_carries_the_hidden_identity_is_a_leak(
    records: dict[str, dict[str, Any]],
) -> None:
    def named_copy(capture: kp.Capture) -> None:
        battlefield = capture.projections["P1"]["view"]["players"][0]["battlefield"]
        battlefield[-1] = {
            "face_down": False,
            "name": "",
            "object_id": "copy",
            "power": 2,
            "toughness": 2,
            "private_identity": "Vampiric Tutor",
        }

    verdict = _verdict(records, "HIDDEN_17", named_copy)
    assert verdict.classification == kp.FAIL_DEMONSTRATED_LEAK
    assert "copy_has_only_face_down_characteristics" in _failed(verdict)


def test_a_card_the_script_casts_is_public_only_after_the_event(
    records: dict[str, dict[str, Any]],
) -> None:
    record = records["HIDDEN_17"]
    # P1's hand card is P1's alone until the script casts it onto the stack.
    assert "Phantasmal Image" in kp.forbidden_tokens(record, "P3").tokens
    assert "Phantasmal Image" not in kp.forbidden_tokens(record, "P3", after_event=True).tokens
    # Nothing else about P2's hidden cards becomes public with it.
    after = kp.forbidden_tokens(record, "P3", after_event=True).tokens
    assert {"Demonic Tutor", "Vampiric Tutor"} <= set(after)


# --------------------------------------------------------------------------- #
# HIDDEN_11 — native shuffle invalidates order while retaining identity memory
# --------------------------------------------------------------------------- #


def _hidden11_observation(capture: kp.Capture) -> dict[str, Any]:
    looked = capture.projections["P1"]["view"]["looked_at"]
    assert len(looked) == 1
    return looked[0]


def test_shuffle_invalidation_keeps_identity_memory_but_not_the_old_order(
    records: dict[str, dict[str, Any]],
) -> None:
    verdict = _verdict(records, "HIDDEN_11")
    assert verdict.classification == kp.VERIFIED, _failed(verdict)
    observation = _hidden11_observation(_capture(records["HIDDEN_11"]))
    assert observation["order_invalidated_by_shuffle"] is True
    assert [card["name"] for card in observation["cards"]] == [
        "Enlightened Tutor",
        "Mystical Tutor",
        "Vampiric Tutor",
    ]


def test_shuffle_without_pre_shuffle_snapshot_is_unverified(
    records: dict[str, dict[str, Any]],
) -> None:
    def mutate(capture: kp.Capture) -> None:
        capture.temporal_snapshots = []

    verdict = _verdict(records, "HIDDEN_11", mutate)
    assert verdict.classification == kp.UNVERIFIED
    assert "pre_shuffle_snapshot_observed" in _failed(verdict)


def test_final_state_without_a_new_native_shuffle_event_is_unverified(
    records: dict[str, dict[str, Any]],
) -> None:
    def mutate(capture: kp.Capture) -> None:
        capture.events["events"] = [
            event
            for event in capture.events["events"]
            if event.get("type") != "LIBRARY_SHUFFLED"
        ]

    verdict = _verdict(records, "HIDDEN_11", mutate)
    assert verdict.classification == kp.UNVERIFIED
    assert "native_shuffle_observed_after_ordered_snapshot" in _failed(verdict)


def test_shuffle_event_not_ordered_after_the_snapshot_is_unverified(
    records: dict[str, dict[str, Any]],
) -> None:
    def mutate(capture: kp.Capture) -> None:
        capture.temporal_snapshots[0]["events"] = copy.deepcopy(capture.events)

    verdict = _verdict(records, "HIDDEN_11", mutate)
    assert verdict.classification == kp.UNVERIFIED
    assert "native_shuffle_observed_after_ordered_snapshot" in _failed(verdict)


def test_pre_shuffle_snapshot_must_show_the_order_the_engine_actually_revealed(
    records: dict[str, dict[str, Any]],
) -> None:
    def mutate(capture: kp.Capture) -> None:
        looked = capture.temporal_snapshots[0]["projection"]["view"]["looked_at"][0]
        looked["cards"] = list(reversed(looked["cards"]))

    verdict = _verdict(records, "HIDDEN_11", mutate)
    assert verdict.classification == kp.FAIL_ENTITLEMENT_DENIED
    assert "pre_shuffle_ordered_snapshot_matches_engine_look" in _failed(verdict)


def test_shuffle_without_explicit_order_invalidation_is_a_leak(
    records: dict[str, dict[str, Any]],
) -> None:
    def mutate(capture: kp.Capture) -> None:
        _hidden11_observation(capture).pop("order_invalidated_by_shuffle")

    verdict = _verdict(records, "HIDDEN_11", mutate)
    assert verdict.classification == kp.FAIL_DEMONSTRATED_LEAK
    assert "shuffle_order_invalidated_explicitly" in _failed(verdict)


def test_shuffle_that_retains_pre_shuffle_order_is_a_leak(
    records: dict[str, dict[str, Any]],
) -> None:
    def mutate(capture: kp.Capture) -> None:
        _hidden11_observation(capture)["cards"] = [
            {"name": "Vampiric Tutor"},
            {"name": "Mystical Tutor"},
            {"name": "Enlightened Tutor"},
        ]

    verdict = _verdict(records, "HIDDEN_11", mutate)
    assert verdict.classification == kp.FAIL_DEMONSTRATED_LEAK
    assert {
        "pre_shuffle_order_not_retained",
        "invalidated_memory_is_canonical_not_engine_order",
    } <= set(_failed(verdict))


def test_shuffle_that_erases_a_legitimately_seen_identity_is_denied(
    records: dict[str, dict[str, Any]],
) -> None:
    def mutate(capture: kp.Capture) -> None:
        _hidden11_observation(capture)["cards"] = _hidden11_observation(capture)["cards"][:2]

    verdict = _verdict(records, "HIDDEN_11", mutate)
    assert verdict.classification == kp.FAIL_ENTITLEMENT_DENIED
    assert "remembered_identity_set_observed" in _failed(verdict)


def test_shuffle_memory_leaked_to_another_principal_is_a_demonstrated_leak(
    records: dict[str, dict[str, Any]],
) -> None:
    def mutate(capture: kp.Capture) -> None:
        capture.projections["P3"]["view"]["looked_at"] = [
            {
                "title": "Orcish Spy",
                "order_invalidated_by_shuffle": True,
                "cards": [{"name": "Vampiric Tutor"}],
            }
        ]

    verdict = _verdict(records, "HIDDEN_11", mutate)
    assert verdict.classification == kp.FAIL_DEMONSTRATED_LEAK
    assert "remembered_identity_withheld_from:P3" in _failed(verdict)


# --------------------------------------------------------------------------- #
# HIDDEN_10 (scry knowledge) and HIDDEN_13 (pile metadata)
# --------------------------------------------------------------------------- #


def _decision_frames(capture: kp.Capture) -> list[dict[str, Any]]:
    return [
        entry["response"]["payload"]["decision"]
        for entry in capture.tape
        if entry.get("message_type") == "get_midgame_decision"
        and isinstance(((entry.get("response") or {}).get("payload") or {}).get("decision"), dict)
    ]


def test_a_scry_range_entitles_its_viewer_only_after_the_event(
    records: dict[str, dict[str, Any]],
) -> None:
    record = records["HIDDEN_10"]
    before = kp.forbidden_tokens(record, "P1").tokens
    after = kp.forbidden_tokens(record, "P1", after_event=True).tokens
    assert "Counterspell" in before and "Brainstorm" in before
    assert "Counterspell" not in after and "Brainstorm" not in after
    for label in ("P2", "P3", "P4"):
        assert "Counterspell" in kp.forbidden_tokens(record, label, after_event=True).tokens


def test_a_scry_range_offered_to_another_principal_is_a_leak(
    records: dict[str, dict[str, Any]],
) -> None:
    def leak(capture: kp.Capture) -> None:
        capture.tape.append(
            _entry(
                "get_midgame_decision",
                None,
                _ok({"decision": _library_frame("P2", ["Counterspell", "Brainstorm"], "Scry")}),
            )
        )

    verdict = _verdict(records, "HIDDEN_10", leak)
    assert verdict.classification == kp.FAIL_DEMONSTRATED_LEAK
    assert "no_range_offer_to:P2" in _failed(verdict)


def test_a_scry_that_shows_its_viewer_another_range_is_denied(
    records: dict[str, dict[str, Any]],
) -> None:
    def wrong(capture: kp.Capture) -> None:
        for frame in _decision_frames(capture):
            if frame.get("prompt") == "Scry":
                frame["legal_options"] = frame["legal_options"][:1]

    verdict = _verdict(records, "HIDDEN_10", wrong)
    assert "range_shown_exactly_to:P1" in _failed(verdict)
    assert verdict.classification != kp.VERIFIED


def test_a_private_identity_in_a_pile_frame_is_a_leak(
    records: dict[str, dict[str, Any]],
) -> None:
    def leak(capture: kp.Capture) -> None:
        for frame in _decision_frames(capture):
            if frame.get("decision_class") == "pile":
                frame["legal_options"][0]["label"] = "Pile 1 (Demonic Tutor)"

    verdict = _verdict(records, "HIDDEN_13", leak)
    assert verdict.classification == kp.FAIL_DEMONSTRATED_LEAK
    assert "pile_frames_carry_only_entitled_identities:P1" in _failed(verdict)


def test_piles_that_never_reached_the_table_are_unverified(
    records: dict[str, dict[str, Any]],
) -> None:
    def no_piles(capture: kp.Capture) -> None:
        for frame in _decision_frames(capture):
            if frame.get("decision_class") == "pile" or "pile" in str(frame.get("prompt")):
                frame["decision_class"] = "priority"
                frame["prompt"] = "Choose priority action"

    verdict = _verdict(records, "HIDDEN_13", no_piles)
    assert "pile_frames_observed" in _failed(verdict)
    assert verdict.classification != kp.VERIFIED


def test_a_pile_is_chosen_only_by_the_engine_label_the_record_names() -> None:
    legal = {
        "actions": [
            {"metadata": {"label": "Pile 1"}},
            {"metadata": {"label": "Pile 2"}},
        ]
    }
    step = {"selection": {"selector_kind": "pile_label", "semantic_value": "Pile 2"}}
    assert kp._pile_offer(legal, step) is legal["actions"][1]
    with pytest.raises(kp.ml.MidgameLaneError):
        kp._pile_offer(
            legal, {"selection": {"selector_kind": "pile_label", "semantic_value": "Pile 3"}}
        )
    with pytest.raises(kp.ml.MidgameLaneError):
        kp._pile_offer(legal, {"selection": {"selector_kind": "pile_label", "semantic_value": 1}})
    assert kp._pile_offer(legal, {"selection": {"selector_kind": "semantic_object"}}) is None


# --------------------------------------------------------------------------- #
# 1.0.16: a persistent look at a face-down exiled card, a hidden source, a
# hidden ability
# --------------------------------------------------------------------------- #


def _exile_view(capture: kp.Capture, label: str) -> list[dict[str, Any]]:
    exile: list[dict[str, Any]] = capture.projections[label]["view"]["players"][1]["exile"]
    return exile


def test_a_face_down_exiled_card_shown_to_another_principal_is_a_leak(
    records: dict[str, dict[str, Any]],
) -> None:
    def mutate(capture: kp.Capture) -> None:
        _exile_view(capture, "P3").append(
            {"name": "Demonic Tutor", "object_id": "dt-exiled", "face_down": True}
        )

    verdict = _verdict(records, "HIDDEN_05", mutate)
    assert verdict.classification == kp.FAIL_DEMONSTRATED_LEAK
    assert "face_down_exile_withheld_from:obj:hidden-hand:P3" in _failed(verdict)


def test_a_look_that_ends_with_its_source_is_a_denied_entitlement(
    records: dict[str, dict[str, Any]],
) -> None:
    def mutate(capture: kp.Capture) -> None:
        exile = _exile_view(capture, "P1")
        exile[:] = [card for card in exile if not card.get("face_down")]

    verdict = _verdict(records, "HIDDEN_05", mutate)
    assert verdict.classification == kp.FAIL_ENTITLEMENT_DENIED
    assert "face_down_exile_shown_to_viewer:obj:hidden-hand" in _failed(verdict)


def test_a_look_measured_while_its_source_remains_is_unverified(
    records: dict[str, dict[str, Any]],
) -> None:
    """Persistence is measured only after the granting source has gone."""

    def mutate(capture: kp.Capture) -> None:
        capture.events["events"] = [
            event for event in capture.events["events"] if event.get("from") != "BATTLEFIELD"
        ]

    verdict = _verdict(records, "HIDDEN_05", mutate)
    assert verdict.classification == kp.UNVERIFIED
    assert "granting_source_left_before_measurement" in _failed(verdict)


def test_a_face_down_exile_named_on_the_public_tape_is_a_leak(
    records: dict[str, dict[str, Any]],
) -> None:
    def mutate(capture: kp.Capture) -> None:
        named = {
            "type": "ZONE_CHANGE",
            "from": "LIBRARY",
            "to": "EXILED",
            "public_identity": True,
            "target_name": "Demonic Tutor",
            "target_object": "obj:hidden-hand",
        }
        capture.events["events"][0] = named
        for entry in capture.tape:
            if entry["message_type"] == "get_midgame_events":
                entry["response"]["payload"]["events"].append(dict(named))

    verdict = _verdict(records, "HIDDEN_05", mutate)
    assert verdict.classification == kp.FAIL_DEMONSTRATED_LEAK
    failed = _failed(verdict)
    assert "face_down_exile_on_public_tape" in failed
    assert "no_forbidden_token_in_channels_of:P2" in failed


def test_a_hidden_source_named_in_its_frame_is_a_leak(
    records: dict[str, dict[str, Any]],
) -> None:
    def mutate(capture: kp.Capture) -> None:
        _replace_entry(
            capture,
            lambda item: (
                item["message_type"] == "get_midgame_decision"
                and (item["response"]["payload"].get("decision") or {}).get("decision_id")
                == "ward-p1"
            ),
            _entry(
                "get_midgame_decision",
                None,
                _ok({"decision": _ward_frame(source_name="Vampiric Tutor")}),
            ),
        )

    verdict = _verdict(records, "HIDDEN_15", mutate)
    assert verdict.classification == kp.FAIL_DEMONSTRATED_LEAK
    assert any(
        name.startswith("hidden_source_frame_carries_no_identity") for name in _failed(verdict)
    )


def test_a_hidden_source_that_never_reaches_the_viewer_is_unverified(
    records: dict[str, dict[str, Any]],
) -> None:
    def mutate(capture: kp.Capture) -> None:
        capture.tape[:] = [
            item
            for item in capture.tape
            if (item["response"].get("payload") or {}).get("decision", {}) is None
            or ((item["response"].get("payload") or {}).get("decision") or {}).get("decision_id")
            != "ward-p1"
        ]

    verdict = _verdict(records, "HIDDEN_15", mutate)
    assert verdict.classification == kp.UNVERIFIED
    assert "hidden_source_frame_reached:P1" in _failed(verdict)


def test_a_hidden_cards_rules_text_in_ability_metadata_is_a_leak(
    records: dict[str, dict[str, Any]],
) -> None:
    def mutate(capture: kp.Capture) -> None:
        _replace_entry(
            capture,
            lambda item: (
                item["message_type"] == "get_midgame_decision"
                and (item["response"]["payload"].get("decision") or {}).get("decision_id")
                == "ward-p1"
            ),
            _entry(
                "get_midgame_decision",
                None,
                _ok(
                    {
                        "decision": _ward_frame(
                            rule="Search your library for a card, then shuffle and put that "
                            "card on top."
                        )
                    }
                ),
            ),
        )

    verdict = _verdict(records, "HIDDEN_16", mutate)
    assert verdict.classification == kp.FAIL_DEMONSTRATED_LEAK
    failed = _failed(verdict)
    assert "hidden_ability_metadata_carries_nothing_hidden:P1" in failed


def test_a_hidden_permanents_projected_abilities_are_scanned(
    records: dict[str, dict[str, Any]],
) -> None:
    def mutate(capture: kp.Capture) -> None:
        capture.projections["P1"]["view"]["players"][1]["battlefield"][0]["abilities"] = [
            "Search your library for a card, then shuffle and put that card on top."
        ]

    verdict = _verdict(records, "HIDDEN_16", mutate)
    assert verdict.classification == kp.FAIL_DEMONSTRATED_LEAK
    assert "hidden_ability_metadata_carries_nothing_hidden:P1" in _failed(verdict)


def test_a_hidden_ability_that_never_reaches_the_viewer_is_unverified(
    records: dict[str, dict[str, Any]],
) -> None:
    def mutate(capture: kp.Capture) -> None:
        for item in capture.tape:
            decision = (item["response"].get("payload") or {}).get("decision")
            if isinstance(decision, dict) and decision.get("decision_id") == "ward-p1":
                decision["source_object"] = None

    verdict = _verdict(records, "HIDDEN_16", mutate)
    assert verdict.classification == kp.UNVERIFIED
    assert "hidden_ability_metadata_reached:P1" in _failed(verdict)


def test_a_declared_rules_text_fragment_is_forbidden_only_where_the_object_is(
    records: dict[str, dict[str, Any]],
) -> None:
    fragment = "then shuffle and put that card on top"
    record = records["HIDDEN_16"]
    assert kp.ability_text_bindings(record) == {fragment: "obj:hidden-lib-0"}
    for label in ("P1", "P3", "P4"):
        assert fragment in kp.forbidden_tokens(record, label, after_event=True).tokens
    # A record that declares no fragment forbids none.
    assert kp.ability_text_bindings(records["HIDDEN_15"]) == {}
