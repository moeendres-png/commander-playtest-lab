"""E-B2 — Forge face-down construction (CR 708.2 face-down status, CR 701.34 manifest).

The Forge bridge now places a battlefield permanent face down as a manifested
permanent and projects ``face_down`` (public) and ``face_down_type`` (only to an
observer whose shown name revealed the identity). These tests pin the Lab side:

* the lane emits the placement request and no longer lists face-down state as
  unobservable or unsupported for the one kind the bridge constructs;
* the checkpoint compares ``face_down`` strictly (``is True`` / ``is False``, never
  ``bool()``), compares the kind from the controller-observer readback, and a missing
  or mistyped readback is UNKNOWN, never EXACT (UNKNOWN != PASS);
* the record's controller-only look permission stays its own open gap (E-B3).

Every test here fails on the pre-E-B2 lane code.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from commander_lab.qualification.current_boundary import forge_scenario_lane as fsl

REPO = Path(__file__).resolve().parents[2]
MANIFESTED_NOTE = "fixture grants controller-only look permission where relevant"


def _commander(cid: str, owner: str, card: str) -> dict:
    return {
        "commander_id": cid,
        "owner": owner,
        "card_identity": card,
        "zone": "command",
        "prior_command_zone_cast_count": 0,
    }


def _object(semantic_id: str, card: str, zone: str, controller: str, **extra) -> dict:
    entry = {
        "semantic_id": semantic_id,
        "card_identity": card,
        "zone": zone,
        "controller": controller,
        "owner": controller,
        "tapped": False,
        "counters": {},
        "face_down": False,
    }
    entry.update(extra)
    return entry


def _face_down_object(**extra) -> dict:
    fields = {"face_down": True, "face_down_type": "MANIFESTED"}
    fields.update(extra)
    zone = fields.pop("zone", "battlefield")
    return _object("obj:p1-fd", "Grizzly Bears", zone, "P1", **fields)


def _record(objects: list[dict], knowledge_state: dict | None = None) -> dict:
    return {
        "fixture_id": "EB2_ROW",
        "fixture_family": "micro_rules",
        "execution_entry_mode": "NATIVE_STATE_LOAD",
        "materialization_status": "OBLIGATION_PRESERVED",
        "obligation_digest": "0" * 64,
        "requested_state_digest": "1" * 64,
        "materialization_digest": "2" * 64,
        "native_procedure": [],
        "decision_script": [],
        "stack_state": [],
        "combat_state": None,
        "action_cost_state": [],
        "knowledge_state": knowledge_state or {"viewer_states": []},
        "rules_randomness": {"predetermined_semantic_draws": []},
        "semantic_objects": [
            _object("obj:P1-commander", "Rograkh, Son of Rohgahh", "command", "P1"),
            _object("obj:P2-commander", "Rograkh, Son of Rohgahh", "command", "P2"),
            *objects,
        ],
        "commander_state": {
            "commanders": [
                _commander("cmd:P1-A", "P1", "Rograkh, Son of Rohgahh"),
                _commander("cmd:P2-A", "P2", "Rograkh, Son of Rohgahh"),
            ],
            "commander_damage_matrix": [],
            "multiple_commander_relations": [],
        },
        "players": [
            {"player_id": "P1", "seat": 1, "life": 40, "poison": 0, "lost": False},
            {"player_id": "P2", "seat": 2, "life": 40, "poison": 0, "lost": False},
        ],
        "temporal_state": {
            "turn_number": 1,
            "phase": "precombat_main",
            "step": "main",
            "active_player": "P1",
            "priority_player": "P1",
        },
        "expected_events": {"required_events": [], "forbidden_events": []},
        "terminal_postconditions": [],
    }


def _row(player_id: str, details: list[dict]) -> dict:
    return {
        "player_id": player_id,
        "seat": int(player_id[1]) - 1,
        "is_actor": player_id == "p1",
        "life": 40,
        "poison_counters": 0,
        "commander_damage_received": {},
        "commander_cast_count": {},
        "zones": {
            "library_size": 99,
            "hand": [],
            "battlefield": [item["name"] for item in details],
            "battlefield_details": details,
            "command": ["Rograkh, Son of Rohgahh", "Commander Effect"],
        },
        "has_lost": False,
    }


def _observation(rows: list[dict]) -> dict:
    return {
        "success": True,
        "payload": {
            "state": {
                "turn_number": 1,
                "phase": "precombat_main",
                "step": "MAIN1",
                "active_player_id": "p1",
                "priority_player_id": "p1",
                "players": rows,
                "stack": [],
                "terminal_outcomes": [
                    {"player_id": "p1", "lost": False, "left": False},
                    {"player_id": "p2", "lost": False, "left": False},
                ],
            },
            "bridge": {"session_status": "RUNNING"},
        },
    }


def _bears(**fields) -> dict:
    detail = {
        "name": "Grizzly Bears",
        "tapped": False,
        "face_down": True,
        "face_down_type": "MANIFESTED",
        "counters": {},
    }
    detail.update(fields)
    return detail


def _seats(controller_detail: dict, opponent_detail: dict | None = None) -> dict:
    """The controller's own view first (the comparison's primary view), then an opponent's."""
    hidden = opponent_detail or {
        "name": "<face-down>",
        "tapped": False,
        "face_down": True,
        "face_down_type": None,
        "counters": {},
    }
    return {
        "p1": _observation([_row("p1", [controller_detail]), _row("p2", [])]),
        "p2": _observation([_row("p1", [hidden]), _row("p2", [])]),
    }


def _field(equivalence: fsl.CheckpointEquivalence, name: str) -> fsl.FieldVerdict:
    return next(item for item in equivalence.fields if item.field == name)


# ---------------------------------------------------------------------------
# Request emission and dimension classification
# ---------------------------------------------------------------------------
def test_a_manifested_face_down_placement_is_emitted_in_the_bootstrap_request():
    model = fsl.model_requested_state(_record([_face_down_object()]))
    assert model.neutral_initial_state["battlefield"] == [
        {
            "card": "Grizzly Bears",
            "controller": "p1",
            "owner": "p1",
            "face_down": True,
            "face_down_type": "MANIFESTED",
        }
    ]
    assert "semantic_objects.face_down" not in {item.dimension for item in model.hard_unsupported}
    assert model.construction_eligible is True


def test_a_face_up_placement_emits_no_face_down_field():
    model = fsl.model_requested_state(
        _record([_object("obj:p1-bears", "Grizzly Bears", "battlefield", "P1")])
    )
    assert model.neutral_initial_state["battlefield"] == [
        {"card": "Grizzly Bears", "controller": "p1", "owner": "p1"}
    ]


@pytest.mark.parametrize(
    "extra",
    [
        {"face_down_type": "CLOAKED"},
        {"face_down_type": "MORPHED"},
        {"face_down_type": None},
        {"zone": "exile"},
        {"attached_to": "obj:p1-host"},
    ],
    ids=["cloaked", "morphed", "missing-type", "exile", "attached"],
)
def test_a_face_down_request_the_bridge_cannot_construct_stays_unsupported(extra):
    model = fsl.model_requested_state(_record([_face_down_object(**extra)]))
    assert "semantic_objects.face_down" in {item.dimension for item in model.hard_unsupported}
    assert model.construction_eligible is False


def test_face_down_is_no_longer_an_unobservable_dimension():
    assert "face_down" not in fsl._UNOBSERVABLE_RECORD_DIMENSIONS


def test_the_capability_matrix_asserts_the_bridge_face_down_fragments(monkeypatch):
    assert set(fsl._SUPPORTED_FIELD_ASSERTIONS["battlefield.face_down"]) == {
        "face_down must be a boolean",
        "face_down_type unsupported: ",
        "setManifested(new SpellAbility.EmptySa(ApiType.Manifest",
    }
    source = "\n".join(
        fragment for fragments in fsl._SUPPORTED_FIELD_ASSERTIONS.values() for fragment in fragments
    ) + "\n".join(fsl._REJECTION_ASSERTIONS.values())
    source += "\n" + "\n".join(
        fragment for fragments in fsl._SCENARIO_HOOK_ASSERTIONS.values() for fragment in fragments
    )
    session = "\n".join(
        fragment for fragments in fsl._HOOK_ASSERTIONS.values() for fragment in fragments
    )
    projection = "\n".join(
        fragment for fragments in fsl._READBACK_ASSERTIONS.values() for fragment in fragments
    )

    def fake(texts):
        def git(args, cwd):
            target = args[-1]
            if target.endswith("StateProjection.java"):
                return texts[2]
            if target.endswith("BridgeSession.java"):
                return texts[1]
            return texts[0]

        return git

    source_info = fsl.ForgeScenarioSource(
        workspace="/nonexistent",
        actual_commit="a" * 40,
        actual_tree="b" * 40,
        rules_core_commit="c" * 40,
        rules_core_tree="d" * 40,
        bridge_commit="e" * 40,
        bridge_tree="f" * 40,
        scenario_source_path=fsl.SCENARIO_SOURCE_RELATIVE,
        scenario_source_sha256="9" * 64,
        session_source_sha256="8" * 64,
        projection_source_sha256="7" * 64,
        rules_core_identity={"engine_equivalent": True},
        bridge_identity={"identical": True},
    )
    from pathlib import Path

    monkeypatch.setattr(fsl, "_git", fake((source, session, projection)))
    matrix = fsl.derive_capability_matrix(source_info, Path("."))
    assert matrix["supported"]["battlefield.face_down"]["status"] == fsl.DIMENSION_SUPPORTED
    # A bridge blob that predates E-B2 (no setManifested call) is capability drift.
    older = source.replace("setManifested(new SpellAbility.EmptySa(ApiType.Manifest", "")
    monkeypatch.setattr(fsl, "_git", fake((older, session, projection)))
    with pytest.raises(fsl.ScenarioCapabilityDrift):
        fsl.derive_capability_matrix(source_info, Path("."))


# ---------------------------------------------------------------------------
# Checkpoint: strict comparison, UNKNOWN, kind mismatch
# ---------------------------------------------------------------------------
def test_the_controller_readback_of_a_manifested_permanent_is_exact():
    model = fsl.model_requested_state(_record([_face_down_object()]))
    equivalence = fsl.compare_checkpoint(model, _seats(_bears()))
    assert equivalence.verdict == fsl.CHECKPOINT_EXACT
    assert _field(equivalence, "battlefield.obj:p1-fd.face_down").verdict == fsl.CHECKPOINT_EXACT
    assert (
        _field(equivalence, "battlefield.obj:p1-fd.face_down_type").verdict == fsl.CHECKPOINT_EXACT
    )


def test_the_kind_is_read_from_the_controller_view_not_the_primary_view():
    """Opponent-first observation order: the primary view cannot name the face-down card."""
    model = fsl.model_requested_state(_record([_face_down_object()]))
    seats = _seats(_bears())
    reordered = {"p2": seats["p2"], "p1": seats["p1"]}
    equivalence = fsl.compare_checkpoint(model, reordered)
    assert equivalence.verdict == fsl.CHECKPOINT_EXACT


def test_a_face_down_request_without_the_controller_view_is_unknown_not_exact():
    model = fsl.model_requested_state(_record([_face_down_object()]))
    seats = _seats(_bears())
    equivalence = fsl.compare_checkpoint(model, {"p2": seats["p2"]})
    assert equivalence.verdict == fsl.CHECKPOINT_UNKNOWN
    assert equivalence.credit_eligible is False


@pytest.mark.parametrize("missing", ["face_down", "face_down_type"])
def test_a_missing_readback_is_unknown_never_exact(missing):
    model = fsl.model_requested_state(_record([_face_down_object()]))
    detail = _bears()
    del detail[missing]
    equivalence = fsl.compare_checkpoint(model, _seats(detail))
    assert equivalence.verdict == fsl.CHECKPOINT_UNKNOWN
    assert equivalence.credit_eligible is False
    assert _field(equivalence, f"battlefield.obj:p1-fd.{missing}").verdict == fsl.CHECKPOINT_UNKNOWN


@pytest.mark.parametrize("observed", [1, 0, "true", "false", None, [], {}])
def test_a_non_bool_face_down_readback_is_unknown_even_when_it_is_truthy_or_falsy(observed):
    face_down = fsl.compare_checkpoint(
        fsl.model_requested_state(_record([_face_down_object()])),
        _seats(_bears(face_down=observed)),
    )
    assert _field(face_down, "battlefield.obj:p1-fd.face_down").verdict == fsl.CHECKPOINT_UNKNOWN
    assert face_down.credit_eligible is False
    face_up = fsl.compare_checkpoint(
        fsl.model_requested_state(
            _record([_object("obj:p1-bears", "Grizzly Bears", "battlefield", "P1")])
        ),
        _seats(_bears(face_down=observed), _bears(face_down=observed)),
    )
    assert face_up.verdict == fsl.CHECKPOINT_UNKNOWN
    assert face_up.credit_eligible is False


def test_a_face_up_request_meeting_a_face_down_readback_is_a_mismatch():
    model = fsl.model_requested_state(
        _record([_object("obj:p1-bears", "Grizzly Bears", "battlefield", "P1")])
    )
    equivalence = fsl.compare_checkpoint(model, _seats(_bears(face_down=True)))
    assert equivalence.verdict == fsl.CHECKPOINT_MISMATCH
    assert (
        _field(equivalence, "battlefield.obj:p1-bears.face_down").verdict == fsl.CHECKPOINT_MISMATCH
    )


def test_a_face_down_request_meeting_a_face_up_readback_is_a_mismatch():
    model = fsl.model_requested_state(_record([_face_down_object()]))
    equivalence = fsl.compare_checkpoint(
        model, _seats(_bears(face_down=False, face_down_type=None))
    )
    assert equivalence.verdict == fsl.CHECKPOINT_MISMATCH
    assert _field(equivalence, "battlefield.obj:p1-fd.face_down").verdict == fsl.CHECKPOINT_MISMATCH


def test_a_kind_mismatch_is_a_mismatch_and_earns_no_credit():
    model = fsl.model_requested_state(_record([_face_down_object()]))
    equivalence = fsl.compare_checkpoint(model, _seats(_bears(face_down_type="CLOAKED")))
    assert equivalence.verdict == fsl.CHECKPOINT_MISMATCH
    assert equivalence.credit_eligible is False
    kind = _field(equivalence, "battlefield.obj:p1-fd.face_down_type")
    assert kind.verdict == fsl.CHECKPOINT_MISMATCH
    assert (kind.requested, kind.observed) == ("MANIFESTED", "CLOAKED")


# ---------------------------------------------------------------------------
# probe_row: a missing face_down readback is its own result, never a mismatch
# ---------------------------------------------------------------------------
class _FakeProc:
    """The minimal BridgeProcess surface probe_row/drive_scenario_game call."""

    def __init__(self) -> None:
        self.requests: list[tuple[str, dict]] = []

    def request(self, message_type, params=None, **kwargs):
        self.requests.append((message_type, params or {}))
        if message_type == "import_deck":
            return {"success": True, "payload": {"deck_handle": {"handle_id": "h1"}}}
        if message_type == "create_commander_game":
            return {"success": True, "payload": {"status": "created", "player_count": 1}}
        return {"success": True, "payload": {}}


def _frame(kind: str, actor: str, revision: int, actions: list[dict] | None = None) -> dict:
    return {
        "seat": actor,
        "decision": {"kind": kind, "actor": actor, "revision": revision, "status": "SUPPORTED"},
        "actions": actions or [],
        "raw": {},
    }


def _source() -> fsl.ForgeScenarioSource:
    return fsl.ForgeScenarioSource(
        workspace="/nonexistent",
        actual_commit="a" * 40,
        actual_tree="b" * 40,
        rules_core_commit="c" * 40,
        rules_core_tree="d" * 40,
        bridge_commit="e" * 40,
        bridge_tree="f" * 40,
        scenario_source_path=fsl.SCENARIO_SOURCE_RELATIVE,
        scenario_source_sha256="9" * 64,
        session_source_sha256="8" * 64,
        projection_source_sha256="7" * 64,
        rules_core_identity={"engine_equivalent": True},
        bridge_identity={"identical": True},
    )


def _run_probe(
    monkeypatch, *, model: fsl.RequestedStateModel, observations: dict
) -> fsl.RowEvidence:
    frames = [
        _frame(
            "STARTING_PLAYER",
            "p1",
            1,
            [
                {
                    "action_id": "opt-start",
                    "action_type": "structural_decision",
                    "source_object_id": "p1",
                }
            ],
        ),
        _frame("PRIORITY", "p1", 2, [{"action_id": "opt-pass", "action_type": "pass_priority"}]),
    ]
    queue = list(frames)

    def fake_poll(proc, game_id, *, seat_count, candidate):
        return queue.pop(0) if queue else frames[-1]

    def fake_seat_state(proc, game_id, seat):
        return observations.get(seat) or next(iter(observations.values()))

    monkeypatch.setattr(fsl, "poll_decision", fake_poll)
    monkeypatch.setattr(fsl, "observe_seat_state", fake_seat_state)
    monkeypatch.setattr(fsl, "observe_all_seats", lambda proc, game_id, seat_count: observations)
    return fsl.probe_row(
        _FakeProc(), model=model, source=_source(), root=REPO, inject_unsupported_probe=False
    )


def test_an_unknown_readback_reports_its_own_result_not_a_mismatch(monkeypatch):
    """A missing ``face_down`` readback in probe_row is RESULT_CHECKPOINT_UNKNOWN.

    Mutant-killing: replacing ``result = RESULT_CHECKPOINT_UNKNOWN`` with
    ``result = RESULT_CHECKPOINT_MISMATCH`` in the lane's classification branch
    fails this test (the result vocabulary must keep UNKNOWN distinct from a
    verified mismatch).
    """
    model = fsl.model_requested_state(_record([_face_down_object()]))
    detail = _bears()
    del detail["face_down"]
    evidence = _run_probe(monkeypatch, model=model, observations=_seats(detail))
    classification = evidence.fields["classification"]
    assert classification["result"] == fsl.RESULT_CHECKPOINT_UNKNOWN
    assert classification["result"] != fsl.RESULT_CHECKPOINT_MISMATCH
    assert evidence.fields["receipt_eligibility"]["eligible"] is False


# ---------------------------------------------------------------------------
# The controller-only look permission stays a separate open gap (E-B3)
# ---------------------------------------------------------------------------
def test_the_record_look_permission_note_keeps_its_own_gap_open():
    model = fsl.model_requested_state(
        _record([_face_down_object(construction_notes=[MANIFESTED_NOTE])])
    )
    dimensions = {item.dimension for item in model.hard_unsupported}
    assert "knowledge_state.face_down_look_permissions" in dimensions
    assert "semantic_objects.face_down" not in dimensions
    assert model.construction_eligible is False
    assert model.credit_eligible is False
    equivalence = fsl.compare_checkpoint(model, _seats(_bears()))
    assert equivalence.verdict == fsl.CHECKPOINT_UNSUPPORTED_DIMENSION
    assert equivalence.credit_eligible is False


def test_a_stated_look_permission_in_knowledge_state_stays_unsupported():
    record = _record(
        [_face_down_object()],
        knowledge_state={
            "viewer_states": [
                {"viewer": "P2", "face_down_look_permissions": ["obj:p1-fd"]},
            ]
        },
    )
    model = fsl.model_requested_state(record)
    assert "knowledge_state" in {item.dimension for item in model.hard_unsupported}
    assert model.construction_eligible is False


def test_a_structured_look_permission_is_a_gap_without_the_free_text_phrase():
    """Review P2 6039789823: the structured field is authoritative.

    The note below never says "look permission"; only the record's own
    ``knowledge_state.viewer_states[*].face_down_look_permissions`` (the field
    ``knowledge_projection`` reads) names the object. The E-B3 gap must stay
    open, or the row silently leaves the AF05 ``knowledge_construction`` count.
    """
    record = _record(
        [_face_down_object(construction_notes=["controller may look at obj:p1-fd"])],
        knowledge_state={
            "viewer_states": [
                {
                    "viewer": "P1",
                    "face_down_look_permissions": [
                        {"object": "obj:p1-fd", "scope": "identity", "viewer": "P1"}
                    ],
                }
            ]
        },
    )
    model = fsl.model_requested_state(record)
    dimensions = {item.dimension for item in model.hard_unsupported}
    assert "knowledge_state.face_down_look_permissions" in dimensions
    assert model.construction_eligible is False


def test_a_structured_look_permission_on_another_object_is_not_this_gap():
    """Wrong-object control: the structured match is per requested object."""
    record = _record(
        [_face_down_object(construction_notes=["controller may look at obj:p1-fd"])],
        knowledge_state={
            "viewer_states": [
                {
                    "viewer": "P1",
                    "face_down_look_permissions": [
                        {"object": "obj:another-permanent", "scope": "identity", "viewer": "P1"}
                    ],
                }
            ]
        },
    )
    model = fsl.model_requested_state(record)
    assert "knowledge_state.face_down_look_permissions" not in {
        item.dimension for item in model.hard_unsupported
    }
