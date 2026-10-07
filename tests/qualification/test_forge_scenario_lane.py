"""Issue #455 — Forge current-boundary scenario lane.

These tests pin the lane contract:

* the ScenarioBootstrap capability matrix is derived from the exact pinned
  source and fails closed on source drift;
* requested-state dimensions the bootstrap cannot represent are never dropped
  and never converted into a PASS;
* checkpoint equivalence is field-level, and construction alone earns nothing;
* the obligation must be observed from engine facts;
* the scenario seam is producer-only (the generic driver still has no scenario
  field), and the producer persists canonical R-4 receipts that the shared
  assembler credits only for the exact effective digests and executing runner.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
RUNNER = REPO / "scripts" / "run_current_boundary_qualification.py"
sys.path.insert(0, str(REPO / "src"))

from commander_lab.qualification.current_boundary import forge_scenario_lane as fsl  # noqa: E402

BRIDGE_MODULE = fsl.BRIDGE_MODULE


# ---------------------------------------------------------------------------
# Synthetic records and observations
# ---------------------------------------------------------------------------
def _commander(cid: str, owner: str, card: str, zone: str = "command") -> dict:
    return {
        "commander_id": cid,
        "owner": owner,
        "card_identity": card,
        "zone": zone,
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


def _record(
    fixture_id: str = "TEST_ROW",
    *,
    semantic_objects: list[dict] | None = None,
    commander_state: dict | None = None,
    players: list[dict] | None = None,
    temporal_state: dict | None = None,
    required_events: list[str] | None = None,
    postconditions: list[str] | None = None,
    native_procedure: list[dict] | None = None,
    decision_script: list[dict] | None = None,
    stack_state: list[dict] | None = None,
    combat_state: dict | None = None,
    action_cost_state: list[dict] | None = None,
) -> dict:
    commanders = commander_state or {
        "commanders": [
            _commander("cmd:P1-A", "P1", "Rograkh, Son of Rohgahh"),
            _commander("cmd:P2-A", "P2", "Rograkh, Son of Rohgahh"),
        ],
        "commander_damage_matrix": [],
        "multiple_commander_relations": [],
    }
    return {
        "fixture_id": fixture_id,
        "fixture_family": "micro_rules",
        "execution_entry_mode": "NATIVE_STATE_LOAD",
        "materialization_status": "OBLIGATION_PRESERVED",
        "obligation_digest": "0" * 64,
        "requested_state_digest": "1" * 64,
        "materialization_digest": "2" * 64,
        "native_procedure": native_procedure or [],
        "decision_script": decision_script or [],
        "stack_state": stack_state or [],
        "combat_state": combat_state,
        "action_cost_state": action_cost_state or [],
        "knowledge_state": {"viewer_states": []},
        "rules_randomness": {"predetermined_semantic_draws": []},
        "semantic_objects": semantic_objects
        if semantic_objects is not None
        else [
            _object("obj:P1-commander", "Rograkh, Son of Rohgahh", "command", "P1"),
            _object("obj:P2-commander", "Rograkh, Son of Rohgahh", "command", "P2"),
            _object("obj:p1-bears", "Grizzly Bears", "battlefield", "P1"),
        ],
        "commander_state": commanders,
        "players": players
        if players is not None
        else [
            {"player_id": "P1", "seat": 1, "life": 40, "poison": 0, "lost": False},
            {"player_id": "P2", "seat": 2, "life": 40, "poison": 0, "lost": False},
        ],
        "temporal_state": temporal_state
        if temporal_state is not None
        else {
            "turn_number": 1,
            "phase": "precombat_main",
            "step": "main",
            "active_player": "P1",
            "priority_player": "P1",
        },
        "expected_events": {
            "required_events": required_events or [],
            "forbidden_events": [],
        },
        "terminal_postconditions": postconditions or [],
    }


def _zone_row(
    player_id: str,
    *,
    life: int = 40,
    hand: list[str] | None = None,
    battlefield: list[str] | None = None,
    battlefield_details: list[dict] | None = None,
    command: list[str] | None = None,
    commander_damage: dict | None = None,
    has_lost: bool = False,
) -> dict:
    return {
        "player_id": player_id,
        "seat": int(player_id[1]) - 1,
        "is_actor": player_id == "p1",
        "life": life,
        "poison_counters": 0,
        "commander_damage_received": commander_damage or {},
        "commander_cast_count": {},
        "zones": {
            "library_size": 99,
            "hand": hand or [],
            "battlefield": battlefield or [],
            "battlefield_details": battlefield_details or [],
            "command": command or [],
        },
        "has_lost": has_lost,
    }


def _observation(
    rows: list[dict],
    *,
    turn: int = 1,
    phase: str = "precombat_main",
    step: str = "MAIN1",
    active: str = "p1",
    priority: str = "p1",
    terminal_outcomes: list[dict] | None = None,
) -> dict:
    return {
        "success": True,
        "payload": {
            "state": {
                "turn_number": turn,
                "phase": phase,
                "step": step,
                "active_player_id": active,
                "priority_player_id": priority,
                "players": rows,
                "stack": [],
                "terminal_outcomes": terminal_outcomes
                if terminal_outcomes is not None
                else [
                    {"player_id": "p1", "lost": False, "left": False},
                    {"player_id": "p2", "lost": False, "left": False},
                ],
            },
            "bridge": {"session_status": "RUNNING"},
        },
    }


# ---------------------------------------------------------------------------
# Capability matrix derivation
# ---------------------------------------------------------------------------
_SCENARIO_SOURCE = "\n".join(
    [
        'neutral.has("battlefield")',
        'optString(entry, "card", "")',
        "battlefield entry missing controller",
        "takeCommander(owner, placement.cardName)",
        "takeFromLibrary(owner, placement.cardName)",
        "Card.fromPaperCard(paper, owner)",
        'entry.has("tapped")',
        "tapped must be a boolean",
        'entry.has("counters")',
        "counters must be an object",
        "counter amounts must be integers",
        "CounterEnumType.valueOf(counter.getKey())",
        'entry.has("attached_to")',
        "attach host not on battlefield: ",
        "aura.attachToEntity(host, null)",
        'neutral.has("hands")',
        "scenario_placed_hand",
        'neutral.has("life")',
        "scenario_set_life",
        '"commander_damage_taken"',
        "scenario_commander_damage",
        "continuous_effects_present",
        "scenario must not inject stack",
        "scenario must not inject decisions",
    ]
)
_SESSION_SOURCE = "\n".join(
    [
        "final ScenarioBootstrap.Plan capturedPlan = scenarioPlan;",
        "ScenarioBootstrap.apply(self, capturedGame, capturedPlan);",
        "capturedMatch.startGame(capturedGame, () -> {",
        "public synchronized void setScenarioPlan(ScenarioBootstrap.Plan plan)",
    ]
)


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
        rules_core_identity={"engine_equivalent": True},
        bridge_identity={"identical": True},
    )


def _fake_git(scenario: str, session: str):
    def fake(args, cwd):
        target = args[-1]
        return session if target.endswith("BridgeSession.java") else scenario

    return fake


def test_capability_matrix_derives_supported_and_rejected(monkeypatch):
    monkeypatch.setattr(fsl, "_git", _fake_git(_SCENARIO_SOURCE, _SESSION_SOURCE))
    matrix = fsl.derive_capability_matrix(_source(), Path("."))
    assert matrix["supported"]["battlefield"]["status"] == fsl.DIMENSION_SUPPORTED
    assert matrix["supported"]["hands"]["status"] == fsl.DIMENSION_SUPPORTED
    assert matrix["supported"]["life"]["status"] == fsl.DIMENSION_SUPPORTED
    assert matrix["supported"]["commander_damage"]["status"] == fsl.DIMENSION_SUPPORTED
    assert matrix["rejected"]["stack"]["status"] == fsl.DIMENSION_UNSUPPORTED
    assert matrix["rejected"]["decision_script"]["status"] == fsl.DIMENSION_UNSUPPORTED


def test_capability_matrix_fails_closed_on_source_drift(monkeypatch):
    drifted = _SCENARIO_SOURCE.replace("scenario must not inject stack", "stack accepted")
    monkeypatch.setattr(fsl, "_git", _fake_git(drifted, _SESSION_SOURCE))
    with pytest.raises(fsl.ScenarioCapabilityDrift):
        fsl.derive_capability_matrix(_source(), Path("."))


def test_capability_matrix_detects_hook_removal(monkeypatch):
    monkeypatch.setattr(fsl, "_git", _fake_git(_SCENARIO_SOURCE, "// no hook"))
    with pytest.raises(fsl.ScenarioCapabilityDrift):
        fsl.derive_capability_matrix(_source(), Path("."))


# ---------------------------------------------------------------------------
# Requested-state translation and fail-closed dimension classification
# ---------------------------------------------------------------------------
def test_translation_builds_only_supported_fields():
    model = fsl.model_requested_state(_record())
    assert model.neutral_initial_state["battlefield"] == [
        {"card": "Grizzly Bears", "controller": "p1", "owner": "p1"}
    ]
    assert model.construction_eligible is True
    assert model.credit_eligible is True


def test_stack_state_fails_closed_with_exact_dimension():
    record = _record(
        stack_state=[
            {
                "source_semantic_id": "obj:micro-bolt",
                "controller": "P1",
                "targets": ["P2"],
            }
        ]
    )
    model = fsl.model_requested_state(record)
    assert model.construction_eligible is False
    dimensions = {item.dimension: item for item in model.hard_unsupported}
    assert "stack_state" in dimensions
    assert dimensions["stack_state"].runtime_probe == "stack"
    assert "stack injection" in dimensions["stack_state"].detail


def test_decision_script_is_execution_blocker_not_bootstrap_misattribution():
    record = _record(
        decision_script=[
            {
                "actor": "P1",
                "decision_family": "choose_mode",
                "selection": {
                    "selector_kind": "semantic_mode_key",
                    "semantic_value": "create_devils",
                },
            }
        ]
    )
    model = fsl.model_requested_state(record)
    assert model.construction_eligible is False
    finding = model.hard_unsupported[0]
    assert finding.dimension == "decision_execution.choose_mode.semantic_mode_key"
    assert "must not build a second generic selector" in finding.detail
    # The decision script is never presented as neutral-state injection.
    assert "inject" not in finding.detail


def test_combat_state_and_combat_step_fail_closed():
    record = _record(
        combat_state={"attackers": {"obj:mp-a2": "P2"}},
        temporal_state={
            "turn_number": 1,
            "phase": "combat",
            "step": "declare_blockers",
            "active_player": "P1",
            "priority_player": "P2",
        },
    )
    model = fsl.model_requested_state(record)
    dimensions = {item.dimension for item in model.hard_unsupported}
    assert "combat_state" in dimensions
    assert "temporal_state.combat_step" in dimensions
    assert fsl.temporal_reachable(model) is False


def test_hand_after_natural_draw_is_unconstructible():
    record = _record(
        players=[
            {"player_id": "P1", "seat": 1, "life": 40, "poison": 0, "lost": False},
            {"player_id": "P2", "seat": 2, "life": 40, "poison": 0, "lost": False},
            {"player_id": "P3", "seat": 3, "life": 40, "poison": 0, "lost": False},
            {"player_id": "P4", "seat": 4, "life": 40, "poison": 0, "lost": False},
        ],
        semantic_objects=[
            _object("obj:P1-commander", "Rograkh, Son of Rohgahh", "command", "P1"),
            _object("obj:micro-burn", "Burn Down the House", "hand", "P1"),
        ],
    )
    model = fsl.model_requested_state(record)
    dimensions = {item.dimension for item in model.hard_unsupported}
    assert "temporal_checkpoint.exact_hand_after_draw" in dimensions


def test_prior_command_zone_cast_count_is_unsupported():
    record = _record(
        commander_state={
            "commanders": [
                _commander("cmd:P1-A", "P1", "Rograkh, Son of Rohgahh"),
                _commander("cmd:P1-B", "P1", "Kediss, Emberclaw Familiar"),
            ],
            "commander_damage_matrix": [],
            "multiple_commander_relations": [],
        },
        semantic_objects=[
            _object(
                "obj:p1-cmd-a",
                "Rograkh, Son of Rohgahh",
                "command",
                "P1",
                commander_id="cmd:P1-A",
            ),
            _object(
                "obj:p1-cmd-b",
                "Kediss, Emberclaw Familiar",
                "command",
                "P1",
                commander_id="cmd:P1-B",
            ),
        ],
    )
    record["commander_state"]["commanders"][0]["prior_command_zone_cast_count"] = 2
    model = fsl.model_requested_state(record)
    dimensions = {item.dimension for item in model.hard_unsupported}
    assert "commander_state.prior_command_zone_cast_count" in dimensions


# ---------------------------------------------------------------------------
# Checkpoint equivalence
# ---------------------------------------------------------------------------
def _supported_model() -> fsl.RequestedStateModel:
    record = _record(
        semantic_objects=[
            _object("obj:P1-commander", "Rograkh, Son of Rohgahh", "command", "P1"),
            _object("obj:P2-commander", "Rograkh, Son of Rohgahh", "command", "P2"),
            _object(
                "obj:p1-bears",
                "Grizzly Bears",
                "battlefield",
                "P1",
                tapped=True,
                counters={"P1P1": 1},
            ),
        ],
        commander_state={
            "commanders": [
                _commander("cmd:P1-A", "P1", "Rograkh, Son of Rohgahh"),
                _commander("cmd:P1-B", "P1", "Kediss, Emberclaw Familiar"),
            ],
            "commander_damage_matrix": [
                {"damaged_player": "P2", "source_commander_id": "cmd:P1-A", "combat_damage": 11},
                {"damaged_player": "P2", "source_commander_id": "cmd:P1-B", "combat_damage": 10},
            ],
            "multiple_commander_relations": [],
        },
    )
    record["semantic_objects"].append(_object("obj:P2-bears", "Grizzly Bears", "battlefield", "P2"))
    return fsl.model_requested_state(record)


def _exact_observations() -> dict[str, dict]:
    rows = [
        _zone_row(
            "p1",
            life=40,
            battlefield=["Grizzly Bears"],
            battlefield_details=[
                {"name": "Grizzly Bears", "tapped": True, "counters": {"+1/+1": 1}}
            ],
            command=["Rograkh, Son of Rohgahh", "Commander Effect"],
        ),
        _zone_row(
            "p2",
            life=40,
            battlefield=["Grizzly Bears"],
            battlefield_details=[{"name": "Grizzly Bears", "tapped": False, "counters": {}}],
            command=["Rograkh, Son of Rohgahh", "Commander Effect"],
            commander_damage={"Rograkh, Son of Rohgahh": 11, "Kediss, Emberclaw Familiar": 10},
        ),
    ]
    return {"p1": _observation(rows)}


def test_checkpoint_exact_for_supported_fields():
    model = _supported_model()
    equivalence = fsl.compare_checkpoint(model, _exact_observations())
    assert equivalence.verdict == fsl.CHECKPOINT_EXACT
    assert equivalence.credit_eligible is True


def test_checkpoint_mismatch_cannot_be_credited():
    observations = _exact_observations()
    state = observations["p1"]["payload"]["state"]
    state["players"][0]["life"] = 39
    equivalence = fsl.compare_checkpoint(_supported_model(), observations)
    assert equivalence.verdict == fsl.CHECKPOINT_MISMATCH
    assert equivalence.credit_eligible is False
    mismatched = [field for field in equivalence.fields if field.verdict == fsl.CHECKPOINT_MISMATCH]
    assert any(field.field == "players.p1.life" for field in mismatched)


def test_stack_unsupported_dimension_can_never_be_exact():
    record = _record(
        stack_state=[{"source_semantic_id": "obj:x", "controller": "P1", "targets": ["P2"]}]
    )
    model = fsl.model_requested_state(record)
    equivalence = fsl.compare_checkpoint(model, _exact_observations())
    assert equivalence.verdict == fsl.CHECKPOINT_UNSUPPORTED_DIMENSION
    assert equivalence.credit_eligible is False


def test_commander_damage_name_collision_fails_closed():
    record = _record(
        commander_state={
            "commanders": [
                _commander("cmd:P1-A", "P1", "Rograkh, Son of Rohgahh"),
                _commander("cmd:P1-B", "P1", "Rograkh, Son of Rohgahh"),
            ],
            "commander_damage_matrix": [
                {"damaged_player": "P2", "source_commander_id": "cmd:P1-A", "combat_damage": 11},
                {"damaged_player": "P2", "source_commander_id": "cmd:P1-B", "combat_damage": 10},
            ],
            "multiple_commander_relations": [],
        },
        semantic_objects=[
            _object("obj:P1-A", "Rograkh, Son of Rohgahh", "command", "P1"),
            _object("obj:P1-B", "Rograkh, Son of Rohgahh", "command", "P1"),
            _object("obj:P2-commander", "Rograkh, Son of Rohgahh", "command", "P2"),
        ],
    )
    model = fsl.model_requested_state(record)
    rows = [
        _zone_row("p1", command=["Rograkh, Son of Rohgahh", "Rograkh, Son of Rohgahh"]),
        _zone_row(
            "p2",
            command=["Rograkh, Son of Rohgahh"],
            commander_damage={"Rograkh, Son of Rohgahh": 21},
        ),
    ]
    equivalence = fsl.compare_checkpoint(model, {"p1": _observation(rows)})
    damage_field = next(
        field
        for field in equivalence.fields
        if field.field == "players.p2.commander_damage_received"
    )
    assert damage_field.verdict == fsl.CHECKPOINT_MISMATCH
    assert "ambiguous" in damage_field.detail


# ---------------------------------------------------------------------------
# Obligation evaluation
# ---------------------------------------------------------------------------
def test_obligation_requires_engine_facts():
    model = _supported_model()
    verdict = fsl.evaluate_obligation(model, {})
    assert verdict.observed is False
    assert verdict.credit_eligible_observation is False


def test_commander_damage_obligation_observed_and_missing():
    record = _record(
        commander_state={
            "commanders": [
                _commander("cmd:P1-A", "P1", "Rograkh, Son of Rohgahh"),
                _commander("cmd:P1-B", "P1", "Kediss, Emberclaw Familiar"),
            ],
            "commander_damage_matrix": [
                {"damaged_player": "P2", "source_commander_id": "cmd:P1-A", "combat_damage": 11},
                {"damaged_player": "P2", "source_commander_id": "cmd:P1-B", "combat_damage": 10},
            ],
            "multiple_commander_relations": [],
        },
        required_events=["commander_damage_checked_per_commander"],
        semantic_objects=[
            _object("obj:P1-commander", "Rograkh, Son of Rohgahh", "command", "P1"),
            _object("obj:P2-commander", "Rograkh, Son of Rohgahh", "command", "P2"),
        ],
    )
    model = fsl.model_requested_state(record)
    rows = [
        _zone_row("p1", command=["Rograkh, Son of Rohgahh", "Kediss, Emberclaw Familiar"]),
        _zone_row(
            "p2",
            commander_damage={"Rograkh, Son of Rohgahh": 11, "Kediss, Emberclaw Familiar": 10},
        ),
    ]
    verdict = fsl.evaluate_obligation(model, {"p1": _observation(rows)})
    assert verdict.observed is True
    assert verdict.credit_eligible_observation is True
    assert verdict.terminal_facts["p2.aggregate_commander_damage"] == 21

    # Wrong terminal fact: the engine wrongly applied the loss -> no credit.
    lost_rows = [
        _zone_row("p1", command=["Rograkh, Son of Rohgahh", "Kediss, Emberclaw Familiar"]),
        _zone_row(
            "p2",
            commander_damage={"Rograkh, Son of Rohgahh": 21},
            has_lost=True,
        ),
    ]
    wrong = fsl.evaluate_obligation(
        model,
        {
            "p1": _observation(
                lost_rows,
                terminal_outcomes=[
                    {"player_id": "p1", "lost": False, "left": False},
                    {"player_id": "p2", "lost": True, "left": False},
                ],
            )
        },
    )
    assert wrong.observed is False
    assert wrong.credit_eligible_observation is False


# ---------------------------------------------------------------------------
# First-turn draw (WS05-CMD-START-3): engine counts across the draw step
# ---------------------------------------------------------------------------
_START = ["starting_player:P1", "first_turn_draw:true"]
_CHOICE = {
    "chooser": "p2",
    "revision": 1,
    "chosen_seat": "p1",
    "offered_seats": ["p1", "p2", "p3"],
    "policy": "fixture_decision_script",
    "basis": fsl.STARTING_PLAYER_AUTHORIZED_BASIS,
}
# What the lane records when it picks the starter itself (no scripted response).
_LAB_CHOICE = dict(_CHOICE, policy="requested_starting_seat", basis="LAB_SELECTED_ENGINE_OFFERED")


def _snap(step: str, hands: dict, libraries: dict, *, active: str = "p1", turn: int = 1) -> dict:
    return {
        "turn_number": turn,
        "active_player": active,
        "phase": "beginning",
        "step": step,
        "priority_player": active,
        "players": {
            player: {"hand": hands[player], "library_size": libraries[player]} for player in hands
        },
    }


def _draw_progression(p1_hand_after: int = 8, p1_library_after: int = 91, **extra) -> list:
    before = _snap("upkeep", {"p1": 7, "p2": 7, "p3": 7}, {"p1": 92, "p2": 92, "p3": 92})
    hands = {"p1": p1_hand_after, "p2": 7, "p3": 7, **extra.get("hands", {})}
    libraries = {"p1": p1_library_after, "p2": 92, "p3": 92, **extra.get("libraries", {})}
    after = _snap("draw", hands, libraries, active=extra.get("active", "p1"))
    return [before, after]


def test_first_turn_draw_obligation_is_mapped_from_the_record():
    record = _record(required_events=list(_START))
    assert fsl._obligation_kind(fsl.model_requested_state(record)) == (
        "starting_player_first_turn_draw"
    )
    # A record naming only one of the two tokens has no such contract.
    record = _record(required_events=["first_turn_draw:true"])
    assert fsl._obligation_kind(fsl.model_requested_state(record)) is None


def test_first_turn_draw_observed_from_the_draw_step_counts():
    verdict = fsl.evaluate_first_turn_draw(list(_START), _draw_progression(), dict(_CHOICE))
    assert verdict.observed is True
    assert verdict.terminal_facts["starting_player_basis"] == fsl.STARTING_PLAYER_AUTHORIZED_BASIS
    assert "scripted response" in verdict.reason
    assert verdict.credit_eligible_observation is True
    assert verdict.semantic_events == _START
    assert verdict.terminal_facts["deltas"]["p1"] == {"hand": 1, "library": -1}


@pytest.mark.parametrize(
    ("required", "progression", "reason"),
    [
        # Final-state coincidence: the right hand size without a draw-step change.
        (_START, _draw_progression(p1_hand_after=7, p1_library_after=92), "do not match"),
        # The wrong value: the engine drew but the record says it must not.
        (["starting_player:P1", "first_turn_draw:false"], _draw_progression(), "do not match"),
        # The wrong starter: no recorded selection of P2.
        (["starting_player:P2", "first_turn_draw:true"], _draw_progression(), "selection"),
        # The engine started another seat's turn than the one selected.
        (_START, _draw_progression(active="p2"), "starter"),
        # The earlier snapshot is not in the beginning phase.
        (_START, [dict(_draw_progression()[0], phase="main"), _draw_progression()[1]], "bracket"),
        # The draw-step snapshot does not give the starter priority.
        (
            _START,
            [_draw_progression()[0], dict(_draw_progression()[1], priority_player="p2")],
            "bracket",
        ),
        # Another player's counts changed in the same window.
        (_START, _draw_progression(hands={"p2": 8}, libraries={"p2": 91}), "do not match"),
        # A hand change that did not come from the library (not a draw).
        (_START, _draw_progression(p1_library_after=92), "do not match"),
        # No snapshot before the draw step: nothing to compare against.
        (_START, _draw_progression()[1:], "both sides"),
        # The draw step of a later turn is not the first turn.
        (_START, [dict(snap, turn_number=2) for snap in _draw_progression()], "both sides"),
        # A malformed obligation names no single starter.
        (["first_turn_draw:true"], _draw_progression(), "exactly one"),
    ],
)
def test_first_turn_draw_wrong_reasons_fail_closed(required, progression, reason):
    verdict = fsl.evaluate_first_turn_draw(list(required), progression, dict(_CHOICE))
    assert verdict.observed is False
    assert verdict.credit_eligible_observation is False
    assert verdict.semantic_events == []
    assert reason in verdict.reason


def test_a_lab_selected_starter_earns_no_credit():
    """Wrong-reason control (#511 P1): identical engine counts, but the starter was
    chosen by the Lab from the requested state, not by a scripted response."""
    verdict = fsl.evaluate_first_turn_draw(list(_START), _draw_progression(), dict(_LAB_CHOICE))
    assert verdict.observed is False
    assert verdict.credit_eligible_observation is False
    assert "without contract authority" in verdict.reason


def test_an_unscripted_starting_player_obligation_is_refused():
    """The lane refuses the row up front: no record may let it pick the starter."""
    record = _record(required_events=list(_START))
    refused = {f.dimension for f in fsl.model_requested_state(record).hard_unsupported}
    assert fsl.STARTING_PLAYER_UNSCRIPTED in refused
    scripted = _record(required_events=list(_START))
    scripted["decision_script"] = [
        {
            "decision_family": "starting_player",
            "actor": "P2",
            "selection": {"selector_kind": "seat"},
        }
    ]
    refused = {f.dimension for f in fsl.model_requested_state(scripted).hard_unsupported}
    assert fsl.STARTING_PLAYER_UNSCRIPTED not in refused


def test_progression_snapshot_carries_counts_only():
    state = {
        "turn_number": 1,
        "active_player_id": "P1",
        "phase": "BEGINNING",
        "step": "UPKEEP",
        "priority_player_id": "p2",
        "players": [
            {"player_id": "p1", "zones": {"hand": ["Island", "Opt"], "library_size": 90}},
            {"player_id": "p2", "zones": {"hand": ["<hidden>"], "library_size": 91}},
        ],
    }
    snapshot = fsl.progression_snapshot(state)
    assert snapshot["step"] == "upkeep"
    assert snapshot["active_player"] == "p1"
    assert snapshot["players"] == {
        "p1": {"hand": 2, "library_size": 90},
        "p2": {"hand": 1, "library_size": 91},
    }
    assert "Island" not in repr(snapshot)


# ---------------------------------------------------------------------------
# probe_row wrong-reason controls (fake bridge, no engine)
# ---------------------------------------------------------------------------
class _FakeProc:
    def __init__(self, *, create_success: bool = True):
        self.create_success = create_success
        self.requests: list[tuple[str, dict]] = []

    def request(self, message_type, params=None, **kwargs):
        params = params or {}
        self.requests.append((message_type, params))
        if message_type in ("start_engine", "get_provider_version", "get_capabilities"):
            return {"success": True, "payload": {}}
        if message_type == "import_deck":
            return {"success": True, "payload": {"deck_handle": {"handle_id": "h1"}}}
        if message_type == "create_commander_game":
            if not self.create_success:
                return {"success": False, "errors": [{"code": "game_creation_failed"}]}
            return {"success": True, "payload": {"status": "created", "player_count": 1}}
        if message_type == "start_game":
            return {"success": True, "payload": {"status": "started"}}
        if message_type in ("pass_priority", "resolve_mulligan", "submit_action"):
            return {"success": True, "payload": {}}
        return {"success": True, "payload": {}}


def _frame(kind: str, actor: str, revision: int, actions: list[dict] | None = None) -> dict:
    return {
        "seat": actor,
        "decision": {"kind": kind, "actor": actor, "revision": revision, "status": "SUPPORTED"},
        "actions": actions or [],
        "raw": {},
    }


def _run_probe(monkeypatch, *, model, observations, create_success=True):
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

    def fake_all_seats(proc, game_id, seat_count):
        return observations

    monkeypatch.setattr(fsl, "poll_decision", fake_poll)
    monkeypatch.setattr(fsl, "observe_seat_state", fake_seat_state)
    monkeypatch.setattr(fsl, "observe_all_seats", fake_all_seats)
    proc = _FakeProc(create_success=create_success)
    return fsl.probe_row(
        proc, model=model, source=_source(), root=REPO, inject_unsupported_probe=False
    )


def test_a_scenario_without_a_declared_starting_seat_fails_closed(monkeypatch):
    """#572: the old `or "p1"` answered this frame; now nothing is submitted."""
    model = _supported_model()
    model.record.pop("starting_player", None)
    model.record["decision_script"] = []
    model.temporal_state["active_player"] = None
    frame = _frame(
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
    )
    monkeypatch.setattr(fsl, "poll_decision", lambda *a, **k: frame)
    proc = _FakeProc()
    result = fsl.drive_scenario_game(proc, model, seed=7, max_steps=1)
    assert result.failure_kind == "FAIL_CLOSED_UNSATISFIED"
    assert result.failure is not None and "declares no starting seat" in result.failure
    assert not any(message == "submit_action" for message, _ in proc.requests)


def test_a_scripted_starting_seat_is_answered_on_the_engine_frame(monkeypatch):
    model = _supported_model()
    model.record["decision_script"] = [
        {
            "decision_family": "starting_player",
            "actor": "P1",
            "selection": {
                "selector_kind": "seat",
                "semantic_value": "P1",
                "matches_only_provider_offered_legal_options": True,
                "on_zero_match": "FAIL_CLOSED",
                "on_multiple_match": "FAIL_CLOSED",
            },
        }
    ]
    frame = _frame(
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
    )
    monkeypatch.setattr(fsl, "poll_decision", lambda *a, **k: frame)
    proc = _FakeProc()
    result = fsl.drive_scenario_game(proc, model, seed=7, max_steps=1)
    assert any(message == "submit_action" for message, _ in proc.requests)
    choice = result.terminal_facts["starting_player_choice"]
    assert choice["chosen_seat"] == "p1"
    assert choice["policy"] == "fixture_decision_script"
    assert choice["basis"] == fsl.STARTING_PLAYER_AUTHORIZED_BASIS


def test_control_positive_executes_and_credits(monkeypatch):
    model = _supported_model()
    model.record["expected_events"]["required_events"] = ["commander_damage_checked_per_commander"]
    observations = _exact_observations()
    evidence = _run_probe(monkeypatch, model=model, observations=observations)
    classification = evidence.fields["classification"]
    assert classification["result"] == fsl.RESULT_OBLIGATION_OBSERVED
    assert evidence.fields["receipt_eligibility"]["eligible"] is True


def test_control_successful_construction_alone_cannot_pass(monkeypatch):
    # Exact construction, but no obligation facts for a declared obligation:
    # no commander damage was requested or observed, so the declared behavior is
    # unobserved even though every compared checkpoint field matches.
    model = _supported_model()
    model.record["expected_events"]["required_events"] = ["commander_damage_checked_per_commander"]
    model.record["commander_state"]["commander_damage_matrix"] = []
    model.commander_damage_by_player = {}
    observations = _exact_observations()
    observations["p1"]["payload"]["state"]["players"][1]["commander_damage_received"] = {}
    evidence = _run_probe(monkeypatch, model=model, observations=observations)
    classification = evidence.fields["classification"]
    assert classification["result"] == fsl.RESULT_OBLIGATION_NOT_OBSERVABLE
    assert evidence.fields["receipt_eligibility"]["eligible"] is False


def test_control_checkpoint_mismatch_cannot_pass(monkeypatch):
    observations = _exact_observations()
    state = observations["p1"]["payload"]["state"]
    state["players"][0]["life"] = 39
    evidence = _run_probe(
        monkeypatch, model=fsl.model_requested_state(_record()), observations=observations
    )
    classification = evidence.fields["classification"]
    assert classification["result"] == fsl.RESULT_CHECKPOINT_MISMATCH
    assert evidence.fields["receipt_eligibility"]["eligible"] is False


def test_control_transport_only_cannot_pass(monkeypatch):
    evidence = _run_probe(
        monkeypatch,
        model=fsl.model_requested_state(_record()),
        observations=_exact_observations(),
        create_success=False,
    )
    classification = evidence.fields["classification"]
    assert classification["result"] == fsl.RESULT_ENGINE_REJECTED
    assert evidence.fields["receipt_eligibility"]["eligible"] is False


def test_control_unsupported_field_fails_closed_in_probe(monkeypatch):
    model = fsl.model_requested_state(
        _record(
            stack_state=[{"source_semantic_id": "obj:x", "controller": "P1", "targets": ["P2"]}]
        )
    )

    def fake_poll(proc, game_id, *, seat_count, candidate):
        return _frame(
            "PRIORITY", "p1", 1, [{"action_id": "opt-pass", "action_type": "pass_priority"}]
        )

    monkeypatch.setattr(fsl, "poll_decision", fake_poll)
    monkeypatch.setattr(fsl, "observe_seat_state", lambda *a, **k: _observation([]))
    monkeypatch.setattr(fsl, "observe_all_seats", lambda *a, **k: {})
    proc = _FakeProc()
    proc.create_success = False  # exact requested state is rejected by the engine
    evidence = fsl.probe_row(
        proc,
        model=model,
        source=_source(),
        root=REPO,
        inject_unsupported_probe=True,
    )
    classification = evidence.fields["classification"]
    assert classification["result"] in (
        fsl.RESULT_UNSUPPORTED_DIMENSION,
        fsl.RESULT_ENGINE_REJECTED,
    )
    assert classification["result"] != fsl.RESULT_OBLIGATION_OBSERVED


# ---------------------------------------------------------------------------
# Source identity binding
# ---------------------------------------------------------------------------
def _git(args, cwd):
    completed = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True
    )
    return completed.stdout


def _make_forge_repo(tmp_path: Path) -> dict[str, str]:
    repo = tmp_path / "forge"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "config", "user.email", "fsl@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "FSL Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True)
    (repo / BRIDGE_MODULE).mkdir(parents=True)
    (repo / BRIDGE_MODULE / "Bridge.java").write_text("// bridge v1\n", encoding="utf-8")
    (repo / "forge-game").mkdir()
    (repo / "forge-game" / "Game.java").write_text("// rules v1\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repo, check=True)
    base = _git(["rev-parse", "HEAD"], repo).strip()
    (repo / BRIDGE_MODULE / "Bridge.java").write_text("// bridge v2\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "bridge-change"], cwd=repo, check=True)
    bridge = _git(["rev-parse", "HEAD"], repo).strip()
    return {
        "repo": str(repo),
        "base": base,
        "bridge": bridge,
        "base_tree": _git(["rev-parse", f"{base}^{{tree}}"], repo).strip(),
    }


def test_bridge_identity_mismatch_invalidates_credit(monkeypatch, tmp_path):
    repo = _make_forge_repo(tmp_path)
    authority = {
        "repository": "https://github.com/moeendres-png/forge.git",
        "rules_core_commit": repo["base"],
        "rules_core_tree": repo["base_tree"],
        "bridge_repository": "https://github.com/moeendres-png/forge.git",
        # Bind the OLD bridge commit while the checkout executes the NEW one.
        "bridge_commit": repo["base"],
        "bridge_tree": repo["base_tree"],
    }
    monkeypatch.setattr(fsl, "canonical_forge_authority", lambda: authority)
    monkeypatch.setattr(fsl.receipt_mod, "FORGE_RULES_CORE_MODULE_ROOTS", ("forge-game",))
    monkeypatch.setattr(
        fsl.receipt_mod,
        "engine_tree_equivalence",
        lambda *a, **k: {
            "engine_equivalent": True,
            "modules": [],
            "differing_modules": [],
            "one_sided_modules": [],
        },
    )
    with pytest.raises(fsl.ScenarioLaneError):
        fsl.bind_forge_scenario_source(repo["repo"])


def test_dirty_checkout_is_refused(monkeypatch, tmp_path):
    repo = _make_forge_repo(tmp_path)
    (Path(repo["repo"]) / "forge-game" / "Game.java").write_text("// dirty\n", encoding="utf-8")
    monkeypatch.setattr(
        fsl,
        "canonical_forge_authority",
        lambda: {
            "repository": "https://github.com/moeendres-png/forge.git",
            "rules_core_commit": repo["bridge"],
            "rules_core_tree": _git(
                ["rev-parse", f"{repo['bridge']}^{{tree}}"], Path(repo["repo"])
            ).strip(),
            "bridge_repository": "https://github.com/moeendres-png/forge.git",
            "bridge_commit": repo["bridge"],
            "bridge_tree": _git(
                ["rev-parse", f"{repo['bridge']}^{{tree}}"], Path(repo["repo"])
            ).strip(),
        },
    )
    with pytest.raises(fsl.ScenarioLaneError, match="uncommitted"):
        fsl.bind_forge_scenario_source(repo["repo"])


# ---------------------------------------------------------------------------
# Fail-before and producer boundary
# ---------------------------------------------------------------------------
# Phase 1 proved the generic current-boundary path had no scenario seam at all.
# Phase 2 integrates the producer into that chain, so the seam is now reached
# only through the lane's explicit producer call. The generic driver still has
# no scenario field, and the generic row classifier still blocks the wave
# before the producer executes (fail-before control below).
def test_game_driver_has_no_generic_scenario_seam():
    driver_source = (
        REPO / "src" / "commander_lab" / "qualification" / "current_boundary" / "game_driver.py"
    ).read_text(encoding="utf-8")
    assert '"scenario"' not in driver_source
    lane_source = (
        REPO
        / "src"
        / "commander_lab"
        / "qualification"
        / "current_boundary"
        / "forge_scenario_lane.py"
    ).read_text(encoding="utf-8")
    assert "neutral_initial_state" in lane_source


def test_shared_runner_and_assembler_integrate_the_producer():
    runner_source = RUNNER.read_text(encoding="utf-8")
    assembler_source = (REPO / "scripts" / "assemble_current_boundary_evidence.py").read_text(
        encoding="utf-8"
    )
    # The shared runner is the only caller: it runs the producer after the clean
    # runner identity is captured and persists its execution document.
    assert "forge_scenario_lane_mod.execute_and_persist(" in runner_source
    assert "FORGE_SCENARIO_EXECUTIONS.json" in runner_source
    assert "FORGE_SCENARIO_TEST_IDENTITY_PREFIX" in assembler_source
    # No second assembler: the Forge evidence is assembled by the canonical
    # assembler from the committed receipt contract, not by this lane.
    assert "def assemble" not in (
        REPO
        / "src"
        / "commander_lab"
        / "qualification"
        / "current_boundary"
        / "forge_scenario_lane.py"
    ).read_text(encoding="utf-8")


def test_fail_before_shared_runner_blocks_the_wave(monkeypatch):
    monkeypatch.delenv("FORGE_WORKSPACE", raising=False)
    spec = importlib.util.spec_from_file_location("fsl_runner_under_test", RUNNER)
    assert spec is not None and spec.loader is not None
    runner = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = runner
    spec.loader.exec_module(runner)
    materialization = runner.load_effective_materialization(REPO)
    identity = {"starting_state_injection_supported": True}
    rows = {
        row.fixture_id: row
        for row in runner.classify_remaining(
            materialization, set(), candidate="forge", identity=identity
        )
    }
    wave = (
        "MICRO_COPY",
        "MICRO_COSTS",
        "MICRO_MODES",
        "MICRO_REPLACEMENT",
        "MICRO_ZONE_CHANGES",
        "WS05-MP-BLOCK-4",
        "WS05-MP-COMBAT-4",
    )
    for fixture_id in wave:
        row = rows[fixture_id]
        assert row.outcome == "BLOCKED", f"{fixture_id} should be BLOCKED before the lane"
        # The shared runner credits nothing here: since #459 the reason names the
        # row's first missing Forge mechanism, and only a lane receipt promotes it.
        assert "first missing mechanism" in row.reason, row.reason
        assert "PASS" not in row.reason, row.reason


def test_lane_classifies_the_wave_with_exact_blockers():
    runner_spec = importlib.util.spec_from_file_location("fsl_runner_census", RUNNER)
    assert runner_spec is not None and runner_spec.loader is not None
    runner = importlib.util.module_from_spec(runner_spec)
    sys.modules[runner_spec.name] = runner
    runner_spec.loader.exec_module(runner)
    materialization = runner.load_effective_materialization(REPO)
    records = {record["fixture_id"]: record for record in materialization.denominator_records()}
    wave = (
        "MICRO_COPY",
        "MICRO_COSTS",
        "MICRO_MODES",
        "MICRO_REPLACEMENT",
        "MICRO_ZONE_CHANGES",
        "WS05-MP-BLOCK-4",
        "WS05-MP-COMBAT-4",
    )
    for fixture_id in wave:
        model = fsl.model_requested_state(records[fixture_id])
        assert model.hard_unsupported, f"{fixture_id} must have exact blockers"
        assert model.credit_eligible is False
    copy_model = fsl.model_requested_state(records["MICRO_COPY"])
    assert any(item.dimension == "stack_state" for item in copy_model.hard_unsupported)


# ---------------------------------------------------------------------------
# Canonical R-4 receipts (the only credit route into the shared chain)
# ---------------------------------------------------------------------------
def _observed_evidence(monkeypatch) -> tuple[fsl.RowEvidence, dict]:
    model = _supported_model()
    model.record["expected_events"]["required_events"] = ["commander_damage_checked_per_commander"]
    evidence = _run_probe(monkeypatch, model=model, observations=_exact_observations())
    assert evidence.fields["classification"]["result"] == fsl.RESULT_OBLIGATION_OBSERVED
    return evidence, model.record


def test_positive_receipt_validates_and_credits(monkeypatch, tmp_path):
    from commander_lab.qualification.current_boundary import receipts as receipt_mod

    evidence, record = _observed_evidence(monkeypatch)
    receipt = fsl.positive_receipt(
        evidence, record, candidate_commit="c" * 40, runner_digest="r" * 64
    )
    path = tmp_path / f"{fsl.FORGE_SCENARIO_RECEIPT_PREFIX}{record['fixture_id']}.json"
    receipt_mod.persist(path, receipt)
    loaded = receipt_mod.load_positive_fixture_receipt(path)
    assert loaded["candidate"] == "forge"
    assert loaded["candidate_commit"] == "c" * 40
    assert (
        loaded["obligation_exercised"]["requested_state_digest"] == record["requested_state_digest"]
    )
    assert loaded["obligation_exercised"]["obligation_digest"] == record["obligation_digest"]
    assert loaded["observed_assertion"]["checkpoint_verdict"] == fsl.CHECKPOINT_EXACT
    credited = receipt_mod.positive_fixture_credit(
        [loaded],
        candidate="forge",
        expected_commit="c" * 40,
        denominator={record["fixture_id"]: record},
        expected_runner_digest="r" * 64,
    )
    assert credited == {record["fixture_id"]: [receipt["test_identity"]]}


def test_stale_or_mismatched_receipt_earns_no_credit(monkeypatch, tmp_path):
    from commander_lab.qualification.current_boundary import receipts as receipt_mod

    evidence, record = _observed_evidence(monkeypatch)
    receipt = fsl.positive_receipt(
        evidence, record, candidate_commit="c" * 40, runner_digest="r" * 64
    )
    fixture = record["fixture_id"]
    # Wrong engine candidate, wrong runner, and a changed effective obligation
    # digest each yield zero credit.
    assert not receipt_mod.positive_fixture_credit(
        [receipt],
        candidate="forge",
        expected_commit="d" * 40,
        denominator={fixture: record},
        expected_runner_digest="r" * 64,
    )
    assert not receipt_mod.positive_fixture_credit(
        [receipt],
        candidate="forge",
        expected_commit="c" * 40,
        denominator={fixture: record},
        expected_runner_digest="s" * 64,
    )
    moved = dict(record)
    moved["obligation_digest"] = "9" * 64
    assert not receipt_mod.positive_fixture_credit(
        [receipt],
        candidate="forge",
        expected_commit="c" * 40,
        denominator={fixture: moved},
        expected_runner_digest="r" * 64,
    )
    # A tampered receipt does not even load.
    tampered = tmp_path / "tampered.json"
    document = dict(receipt)
    document["observed_assertion"] = {"checkpoint_verdict": fsl.CHECKPOINT_MISMATCH}
    receipt_mod.persist(tampered, document)
    with pytest.raises(receipt_mod.ReceiptError):
        receipt_mod.load_positive_fixture_receipt(tampered)


def test_positive_receipt_rejects_construction_only(monkeypatch):
    model = fsl.model_requested_state(_record())
    evidence = _run_probe(monkeypatch, model=model, observations=_exact_observations())
    assert evidence.fields["classification"]["result"] != fsl.RESULT_OBLIGATION_OBSERVED
    with pytest.raises(fsl.ScenarioLaneError):
        fsl.positive_receipt(
            evidence, model.record, candidate_commit="c" * 40, runner_digest="r" * 64
        )


def test_variance_receipt_is_labelled_not_exact():
    evidence = fsl.RowEvidence(fixture_id="VAR_ROW")
    evidence.set(
        "classification",
        {
            "result": fsl.RESULT_OBLIGATION_OBSERVED,
            "obligation_kind": "player_leaves_multiplayer_cleanup",
        },
    )
    evidence.set("receipt_eligibility", {"eligible": True, "reason": "ok"})
    evidence.set(
        "checkpoint_equivalence",
        {
            "verdict": fsl.CHECKPOINT_ALLOWED_VARIANCE,
            "variance_source": "fixture.native_procedure NATIVE_CAUSE_DECLARED_PLAYER_LOSS",
        },
    )
    evidence.set("external_decision_selection", [{"policy": "pass_when_offered"}])
    evidence.set("semantic_events", ["player_leaves:p2"])
    evidence.set("terminal_facts", {"obligation": {"p2.lost": True}})
    evidence.set("native_bootstrap", {"applied": True})
    record = {
        "fixture_id": "VAR_ROW",
        "requested_state_digest": "a" * 64,
        "obligation_digest": "b" * 64,
        "expected_events": {"required_events": ["player_leaves:p2"]},
        "terminal_postconditions": ["p2 leaves the game"],
    }
    receipt = fsl.positive_receipt(
        evidence, record, candidate_commit="c" * 40, runner_digest="r" * 64
    )
    assert receipt["assertion_class"] == "BEHAVIOUR_OBSERVED_FIXTURE_DECLARED_CAUSE_VARIANCE"
    assert receipt["observed_assertion"]["checkpoint_verdict"] == fsl.CHECKPOINT_ALLOWED_VARIANCE
    assert "NATIVE_CAUSE_DECLARED_PLAYER_LOSS" in (
        receipt["observed_assertion"]["checkpoint_variance_source"] or ""
    )


def test_selection_covers_eligible_rows_and_the_declared_wave():
    from commander_lab.qualification.current_boundary.materialization import (
        load_effective_materialization,
    )

    materialization = load_effective_materialization(REPO)
    records = {record["fixture_id"]: record for record in materialization.denominator_records()}
    selected = set(fsl.select_execution_fixtures(records))
    for fixture_id in fsl.FORGE_SCENARIO_BLOCKER_WAVE:
        assert fixture_id in selected
    for fixture_id, record in records.items():
        model = fsl.model_requested_state(record)
        if model.credit_eligible and fsl.temporal_reachable(model):
            assert fixture_id in selected
    # The structurally credit-eligible rows, the 6 causal-route commander zone rows
    # (#520), the causal stack-then-elimination row and the 7 wave rows.
    # WS05-CMD-START-2 and START-3 are refused (#511 P1): their obligations name a
    # starting player that no record scripts, so the lane may not choose one.
    assert len(selected) == 21
    assert "WS05-MP-ELIM-STACK-3" in selected
    assert not {"WS05-CMD-START-2", "WS05-CMD-START-3"} & selected


def test_execute_and_persist_requires_bound_identity(tmp_path):
    with pytest.raises(fsl.ScenarioLaneError):
        fsl.execute_and_persist(
            forge_workspace=tmp_path,
            records={},
            candidate_commit="",
            runner_digest="r" * 64,
            lab_root=REPO,
            out_dir=tmp_path,
        )


def test_execute_and_persist_rejects_cross_wired_candidate(monkeypatch, tmp_path):
    monkeypatch.setattr(fsl, "bind_forge_scenario_source", lambda workspace: _source())
    with pytest.raises(fsl.ScenarioLaneError):
        fsl.execute_and_persist(
            forge_workspace=tmp_path,
            records={},
            candidate_commit="d" * 40,
            runner_digest="r" * 64,
            lab_root=REPO,
            out_dir=tmp_path,
        )


def _synthetic_observed_evidence(fixture_id: str) -> fsl.RowEvidence:
    evidence = fsl.RowEvidence(fixture_id=fixture_id)
    evidence.set(
        "classification",
        {
            "result": fsl.RESULT_OBLIGATION_OBSERVED,
            "obligation_kind": "commander_damage_checked_per_commander",
        },
    )
    evidence.set("receipt_eligibility", {"eligible": True, "reason": "ok"})
    evidence.set(
        "checkpoint_equivalence",
        {"verdict": fsl.CHECKPOINT_EXACT, "variance_source": None},
    )
    evidence.set("external_decision_selection", [{"policy": "pass_when_offered"}])
    evidence.set("semantic_events", ["commander_damage_per_commander_evaluated:p2"])
    evidence.set("terminal_facts", {"obligation": {"p2.aggregate_commander_damage": 21}})
    evidence.set("native_bootstrap", {"applied": True})
    return evidence


def test_execute_and_persist_writes_only_observed_receipts(monkeypatch, tmp_path):
    from commander_lab.qualification.current_boundary import receipts as receipt_mod

    monkeypatch.setattr(fsl, "bind_forge_scenario_source", lambda workspace: _source())
    monkeypatch.setattr(fsl, "derive_capability_matrix", lambda source, root: {"ok": True})

    launched = []

    class _Proc:
        def __init__(self, ordinal: int) -> None:
            self.ordinal = ordinal
            self.closed = False

        def close(self) -> None:
            assert self.closed is False
            self.closed = True

    def launch(_source):
        proc = _Proc(len(launched))
        launched.append(proc)
        return proc, {"runtime": "synthetic", "process_ordinal": proc.ordinal}

    monkeypatch.setattr(fsl, "launch_forge_scenario", launch)

    records = {
        "OBSERVED": {
            "fixture_id": "OBSERVED",
            "requested_state_digest": "1" * 64,
            "obligation_digest": "2" * 64,
            "expected_events": {"required_events": ["commander_damage_checked_per_commander"]},
            "terminal_postconditions": [],
        },
        "BLOCKED": {
            "fixture_id": "BLOCKED",
            "requested_state_digest": "3" * 64,
            "obligation_digest": "4" * 64,
            "expected_events": {"required_events": ["player_leaves:p2"]},
            "terminal_postconditions": [],
        },
    }

    def fake_probe(proc, *, model, source, root, seed, max_steps):
        if model.fixture_id == "OBSERVED":
            return _synthetic_observed_evidence(model.fixture_id)
        evidence = fsl.RowEvidence(fixture_id=model.fixture_id)
        evidence.set(
            "classification",
            {"result": fsl.RESULT_UNSUPPORTED_DIMENSION, "reasons": ["blocked"]},
        )
        evidence.set("receipt_eligibility", {"eligible": False, "reason": "blocked"})
        return evidence

    monkeypatch.setattr(fsl, "probe_row", fake_probe)
    # A stale own-prefix receipt must be removed; a foreign producer's receipt
    # must survive.
    stale = tmp_path / f"{fsl.FORGE_SCENARIO_RECEIPT_PREFIX}STALE.json"
    stale.write_text("{}\n", encoding="utf-8")
    foreign = tmp_path / "midgame-row.json"
    foreign.write_text("{}\n", encoding="utf-8")

    document = fsl.execute_and_persist(
        forge_workspace=tmp_path,
        records=records,
        candidate_commit="c" * 40,
        runner_digest="r" * 64,
        lab_root=REPO,
        out_dir=tmp_path,
    )
    assert document["rows_observed"] == 1
    assert document["receipts_written"] == ["OBSERVED"]
    assert document["process_isolation"] == "FRESH_PROCESS_PER_FIXTURE"
    assert set(document["runtime_identities"]) == set(records)
    assert len(launched) == len(records)
    assert all(proc.closed for proc in launched)
    assert len({proc.ordinal for proc in launched}) == len(records)
    assert (tmp_path / f"{fsl.FORGE_SCENARIO_RECEIPT_PREFIX}OBSERVED.json").is_file()
    assert not (tmp_path / f"{fsl.FORGE_SCENARIO_RECEIPT_PREFIX}BLOCKED.json").exists()
    assert not stale.exists()
    assert foreign.is_file()
    receipt_mod.load_positive_fixture_receipt(
        tmp_path / f"{fsl.FORGE_SCENARIO_RECEIPT_PREFIX}OBSERVED.json"
    )


@pytest.mark.parametrize(
    "choice",
    [
        None,
        dict(_CHOICE, chosen_seat="p2"),
        dict(_CHOICE, offered_seats=["p2", "p3"]),
    ],
)
def test_first_turn_draw_requires_the_recorded_starting_selection(choice):
    """The starter is the Lab's engine-offered selection; without that record, no credit."""
    verdict = fsl.evaluate_first_turn_draw(list(_START), _draw_progression(), choice)
    assert verdict.observed is False
    assert "selection" in verdict.reason
