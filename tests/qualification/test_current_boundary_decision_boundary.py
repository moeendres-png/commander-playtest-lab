"""AF04 decision-boundary derivation: fail-before and wrong-reason controls.

#255/441 classified the previous hard-coded Forge AF04 UNKNOWN as
``EVIDENCE_ASSEMBLY_GAP_PENDING_BOUNDED_REVALIDATION``: the same-epoch
player-cardinality evidence records externally answered Forge STARTING_PLAYER,
MULLIGAN and PRIORITY frames, so the gate must be derived from that evidence.

These tests are written to be able to fail for the right reason:

* they first prove the real committed epoch derives PASS (so the derivation has
  to consume the artifact, not a literal);
* then every mutation of that evidence must produce the failure class the
  contract names — a contradiction is FAIL, an unmeasured element is UNKNOWN,
  and neither is ever PASS.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from commander_lab.qualification.current_boundary import decision_boundary as db

REPO = Path(__file__).resolve().parents[2]
# The predecessor epoch (main-produced) and the successor epoch produced by this
# workstream. Both are committed, and the AF04 derivation must hold on both: a
# test that only read the predecessor would not cover the epoch #255 consumes.
EPOCHS = (
    REPO / "qualification/current-boundary-epochs/4cad91897216-a43e80d96595",
    REPO / "qualification/current-boundary-epochs/fac12a9b73b1-3234e300d699",
)
EPOCH = EPOCHS[0]


# --------------------------------------------------------------------------- #
# Synthetic same-epoch evidence, shaped exactly like the runner persists it
# --------------------------------------------------------------------------- #


def _forge_scenario(count: int) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """A Forge-shaped cardinality document for one player count."""
    game_id = f"wsr22-forge-{count}p-test"
    tape: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    option_counter = 0

    def option() -> str:
        nonlocal option_counter
        option_counter += 1
        return f"opt-{option_counter:04d}"

    seat_options = [option() for _ in range(count)]
    tape.append(
        {
            "step": "starting_player",
            "kind": "STARTING_PLAYER",
            "actor": "p1",
            "revision": 1,
            "policy": "fixture_scripted_seat",
            "chosen_option_id": seat_options[0],
            "offered_option_ids": seat_options,
            "note": "fixture-scripted seat p1",
        }
    )
    observations.append({"step": "starting_player", "payload": {"decision": {"executed": True}}})
    revision = 1
    for seat in range(1, count + 1):
        mulligan_options = [option(), option()]
        revision += 1
        tape.append(
            {
                "step": "mulligan",
                "kind": "MULLIGAN",
                "actor": f"p{seat}",
                "revision": revision,
                "policy": "keep_all",
                "chosen_option_id": None,
                "offered_option_ids": mulligan_options,
                "note": "external keep decision; no bottoming",
            }
        )
        observations.append(
            {
                "step": "mulligan_keep",
                "payload": {
                    "decision": {"executed": True, "pre_state_hash": "a", "post_state_hash": "b"}
                },
            }
        )
    pass_options = [option()]
    revision += 1
    tape.append(
        {
            "step": "priority",
            "kind": "PRIORITY",
            "actor": "p1",
            "revision": revision,
            "policy": "pass_when_offered",
            "chosen_option_id": pass_options[0],
            "offered_option_ids": pass_options,
            "note": "external priority pass",
        }
    )
    observations.append({"step": "priority_pass", "payload": {"decision": {"executed": True}}})
    results = {
        "candidate": "forge",
        "player_count": count,
        "game_id": game_id,
        "steps_completed": [
            "handshake",
            "import_deck",
            "create_commander_game",
            "start_game",
            "decision_drive",
        ],
        "decision_tape": tape,
        "observations": observations,
        "terminal_facts": {"priority_reached": True},
        "failure": None,
        "failure_kind": None,
    }
    runtime_identity = {
        "engine_candidate_commit": "b" * 40,
        "engine_candidate_tree": "c" * 40,
        "bridge_source_commit": "e" * 40,
        "runner_commit": "d" * 40,
    }
    document = {
        "schema_version": "wsr22.player-cardinality/1.0.0",
        "candidate": "forge",
        "boundary": "FRESH_CURRENT_BOUNDARY_EXECUTION",
        "runtime_identity": runtime_identity,
        "required_counts": [2, 3, 4, 5],
        "bounded_secondary_counts": [6],
        "results": {f"{count}P": results},
    }
    af01 = {
        "engine_commit_reported": "e" * 40,
        "decision_identity_provenance": {"verified": True},
    }
    return document, af01, runtime_identity


def _xmage_scenario(count: int) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """An XMage-shaped cardinality document (no STARTING_PLAYER class)."""
    tape: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    revision = 0
    for seat in range(1, count + 1):
        revision += 1
        keep_option = f"keep-{seat}"
        mulligan_option = f"mulligan-{seat}"
        tape.append(
            {
                "step": "mulligan",
                "kind": "MULLIGAN",
                "actor": f"engine-seat-{seat}",
                "revision": revision,
                "policy": "keep_all",
                "chosen_option_id": None,
                "offered_option_ids": [keep_option, mulligan_option],
                "note": "external keep decision; no bottoming",
            }
        )
        observations.append(
            {
                "step": "mulligan_keep",
                "payload": {
                    "executed_action_id": keep_option,
                    "executed_action_type": "mulligan",
                    "executed_actor_id": f"engine-seat-{seat}",
                    "keep": True,
                    "mulligan_choice_external": True,
                },
            }
        )
    revision += 1
    pass_option = "pass-1"
    tape.append(
        {
            "step": "priority",
            "kind": "PRIORITY",
            "actor": "engine-seat-1",
            "revision": revision,
            "policy": "pass_when_offered",
            "chosen_option_id": pass_option,
            "offered_option_ids": [pass_option],
            "note": "external priority pass",
        }
    )
    observations.append(
        {
            "step": "priority_pass",
            "payload": {
                "executed_action_id": pass_option,
                "executed_action_type": "pass_priority",
                "executed_actor_id": "engine-seat-1",
            },
        }
    )
    results = {
        "candidate": "xmage",
        "player_count": count,
        "game_id": f"wsr22-xmage-{count}p-test",
        "steps_completed": ["handshake", "decision_drive"],
        "decision_tape": tape,
        "observations": observations,
        "terminal_facts": {"priority_reached": True},
        "failure": None,
    }
    runtime_identity = {
        "engine_candidate_commit": "a" * 40,
        "runner_commit": "d" * 40,
    }
    document = {
        "schema_version": "wsr22.player-cardinality/1.0.0",
        "candidate": "xmage",
        "boundary": "FRESH_CURRENT_BOUNDARY_EXECUTION",
        "runtime_identity": runtime_identity,
        "required_counts": [2, 3, 4, 5],
        "bounded_secondary_counts": [6],
        "results": {f"{count}P": results},
    }
    af01 = {
        "engine_commit_reported": "a" * 40,
        "decision_identity_provenance": {"verified": True},
    }
    return document, af01, runtime_identity


def _multi(
    counts: tuple[int, ...] = (2, 3, 4, 5),
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    base: dict[str, Any] | None = None
    for count in counts:
        document, af01, identity = _forge_scenario(count)
        if base is None:
            base = document
        else:
            base["results"].update(document["results"])
    assert base is not None
    return base, af01, identity


def _derive(
    document: dict[str, Any], af01: dict[str, Any], identity: dict[str, Any]
) -> dict[str, Any]:
    return db.derive_decision_boundary("forge", document, af01, identity)


def _first_frame(
    document: dict[str, Any], count: str = "2P", kind: str = "PRIORITY"
) -> dict[str, Any]:
    for entry in document["results"][count]["decision_tape"]:
        if entry["kind"] == kind:
            return entry
    raise AssertionError(f"no {kind} frame in {count}")


def _synthetic(
    counts: tuple[int, ...] = (2, 3, 4, 5),
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return _multi(counts)


# --------------------------------------------------------------------------- #
# Real current-boundary evidence: the derivation must consume it
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("candidate", ["forge", "xmage"])
def test_real_epoch_decision_boundary_derives_pass(candidate: str) -> None:
    cardinality = json.loads(
        (EPOCH / f"PLAYER_CARDINALITY_{candidate.upper()}.json").read_text(encoding="utf-8")
    )
    af01 = json.loads((EPOCH / f"AF01_{candidate.upper()}.json").read_text(encoding="utf-8"))
    document = db.derive_decision_boundary(
        candidate, cardinality, af01, cardinality["runtime_identity"]
    )
    assert document["verdict"] == "PASS", (
        document["contradictions"],
        document["gaps"],
    )
    # The real Forge epoch exercises three classes beyond PRIORITY's predecessor
    # limitation, and the assembler must see them.
    if candidate == "forge":
        assert {"STARTING_PLAYER", "MULLIGAN", "PRIORITY"}.issubset(
            document["externally_answered_decision_classes"]
        )


def test_assembler_reads_the_real_forge_epoch_as_pass() -> None:
    cardinality = json.loads((EPOCH / "PLAYER_CARDINALITY_FORGE.json").read_text(encoding="utf-8"))
    af01 = json.loads((EPOCH / "AF01_FORGE.json").read_text(encoding="utf-8"))
    sys_path = REPO / "scripts/assemble_current_boundary_evidence.py"
    import importlib.util

    spec = importlib.util.spec_from_file_location("assembler_af04", sys_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    gate = module.af04_gate("forge", af01, cardinality, cardinality["runtime_identity"])
    assert gate["gate"] == "AF04"
    assert gate["verdict"] == "PASS", gate["nonblocking_limitations"]
    assert gate["owner_ruling"] == "R-2"


# --------------------------------------------------------------------------- #
# Contradictions: a recorded submission outside the offered domain is FAIL
# --------------------------------------------------------------------------- #


def test_a_cost_order_frame_is_measured_and_an_unanswered_one_fails_closed() -> None:
    """#443 added ORDER_CHOICE to the shared driver; AF04 must cover it."""

    document, af01, identity = _synthetic()
    results = document["results"]["2P"]
    order_option = "order-1"
    results["decision_tape"].insert(
        len(results["decision_tape"]) - 1,
        {
            "step": "cost_order",
            "kind": "ORDER_CHOICE",
            "actor": "p1",
            "revision": 99,
            "policy": "native_declared_cost_part_order",
            "chosen_option_id": order_option,
            "offered_option_ids": [order_option],
            "note": "pilot preserves the provider-published native CostPart order",
        },
    )
    results["observations"].insert(
        len(results["observations"]) - 1,
        {"step": "cost_order", "payload": {"decision": {"executed": True}}},
    )
    assert _derive(document, af01, identity)["verdict"] == "PASS"

    # A cost-order frame answered with an option the engine never offered is a
    # contradiction, exactly as for every other class. The mutation must target
    # the ORDER_CHOICE entry itself, or it would test a different frame.
    order_frames = [
        entry
        for entry in document["results"]["2P"]["decision_tape"]
        if entry["kind"] == "ORDER_CHOICE"
    ]
    assert len(order_frames) == 1
    order_frames[0]["chosen_option_id"] = "order-9"
    mutated = _derive(document, af01, identity)
    assert mutated["verdict"] == "FAIL"
    assert any("order-9" in item["detail"] for item in mutated["contradictions"]), mutated[
        "contradictions"
    ]


def test_a_chosen_option_outside_the_offered_set_is_fail() -> None:
    document, af01, identity = _synthetic()
    _first_frame(document, "2P", "PRIORITY")["chosen_option_id"] = "opt-not-offered"
    result = _derive(document, af01, identity)
    assert result["verdict"] == "FAIL"
    assert any(
        "not among the engine-offered options" in item["detail"]
        for item in result["contradictions"]
    )


def test_a_null_choice_on_priority_is_fail() -> None:
    document, af01, identity = _synthetic()
    _first_frame(document, "2P", "PRIORITY")["chosen_option_id"] = None
    result = _derive(document, af01, identity)
    assert result["verdict"] == "FAIL"
    assert any("no option id" in item["detail"] for item in result["contradictions"])


def test_a_starting_player_choice_outside_the_seat_domain_is_fail() -> None:
    document, af01, identity = _synthetic()
    frame = _first_frame(document, "2P", "STARTING_PLAYER")
    frame["chosen_option_id"] = "opt-9999"
    result = _derive(document, af01, identity)
    assert result["verdict"] == "FAIL"


def test_a_starting_player_frame_not_offering_one_option_per_seat_is_fail() -> None:
    document, af01, identity = _synthetic()
    frame = _first_frame(document, "2P", "STARTING_PLAYER")
    frame["offered_option_ids"] = frame["offered_option_ids"][:1]
    frame["chosen_option_id"] = frame["offered_option_ids"][0]
    result = _derive(document, af01, identity)
    assert result["verdict"] == "FAIL"
    assert any("one option per seat" in item["detail"] for item in result["contradictions"])


def test_a_engine_executed_option_outside_the_frame_is_fail() -> None:
    document, af01, identity = _synthetic()
    for observation in document["results"]["2P"]["observations"]:
        if observation["step"] == "mulligan_keep":
            observation["payload"]["executed_action_id"] = "keep-not-offered"
            break
    result = _derive(document, af01, identity)
    assert result["verdict"] == "FAIL"
    assert any("is not among the options" in item["detail"] for item in result["contradictions"])


def test_a_engine_executing_for_a_different_actor_is_fail() -> None:
    document, af01, identity = _xmage_scenario(2)
    document, af01, identity = _multi_with_xmage(document, af01, identity)
    for observation in document["results"]["2P"]["observations"]:
        if observation["step"] == "mulligan_keep":
            observation["payload"]["executed_actor_id"] = "engine-seat-99"
            break
    result = db.derive_decision_boundary("xmage", document, af01, identity)
    assert result["verdict"] == "FAIL"
    assert any("not for the frame actor" in item["detail"] for item in result["contradictions"])


def _multi_with_xmage(
    document: dict[str, Any], af01: dict[str, Any], identity: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    for count in (3, 4, 5):
        extra, _, _ = _xmage_scenario(count)
        document["results"].update(extra["results"])
    document["runtime_identity"] = identity
    return document, af01, identity


def test_engine_reported_non_execution_is_fail() -> None:
    document, af01, identity = _synthetic()
    for observation in document["results"]["2P"]["observations"]:
        if observation["step"] == "priority_pass":
            observation["payload"]["decision"]["executed"] = False
    result = _derive(document, af01, identity)
    assert result["verdict"] == "FAIL"
    assert any("did not accept" in item["detail"] for item in result["contradictions"])


def test_a_keep_value_that_contradicts_keep_all_is_fail() -> None:
    document, af01, identity = _xmage_scenario(2)
    document, af01, identity = _multi_with_xmage(document, af01, identity)
    for observation in document["results"]["2P"]["observations"]:
        if observation["step"] == "mulligan_keep":
            observation["payload"]["keep"] = False
            break
    result = db.derive_decision_boundary("xmage", document, af01, identity)
    assert result["verdict"] == "FAIL"


def test_a_non_external_mulligan_choice_is_fail() -> None:
    document, af01, identity = _xmage_scenario(2)
    document, af01, identity = _multi_with_xmage(document, af01, identity)
    for observation in document["results"]["2P"]["observations"]:
        if observation["step"] == "mulligan_keep":
            observation["payload"]["mulligan_choice_external"] = False
            break
    result = db.derive_decision_boundary("xmage", document, af01, identity)
    assert result["verdict"] == "FAIL"


def test_a_fail_closed_policy_answer_is_fail() -> None:
    document, af01, identity = _synthetic()
    _first_frame(document, "2P", "PRIORITY")["policy"] = "NO_MATCHING_OFFERED_OPTION"
    result = _derive(document, af01, identity)
    assert result["verdict"] == "FAIL"
    assert any("fail-closed policy" in item["detail"] for item in result["contradictions"])


def test_stopping_at_an_unsupported_decision_class_is_fail() -> None:
    document, af01, identity = _synthetic()
    document["results"]["2P"]["terminal_facts"]["stopped_at_decision_kind"] = "TARGET"
    result = _derive(document, af01, identity)
    assert result["verdict"] == "FAIL"
    assert any("stopped at a decision class" in item["detail"] for item in result["contradictions"])


def test_a_mulligan_count_that_is_not_one_per_seat_is_fail() -> None:
    document, af01, identity = _synthetic()
    tape = document["results"]["2P"]["decision_tape"]
    del tape[2]  # drop p2's mulligan frame (and its observation stays unpaired)
    result = _derive(document, af01, identity)
    assert result["verdict"] == "FAIL"
    assert any(
        "every seat must decide exactly once" in item["detail"] for item in result["contradictions"]
    )


def test_the_same_actor_deciding_twice_in_a_row_is_fail() -> None:
    document, af01, identity = _synthetic()
    frames = [
        entry for entry in document["results"]["2P"]["decision_tape"] if entry["kind"] == "MULLIGAN"
    ]
    frames[1]["actor"] = frames[0]["actor"]
    result = _derive(document, af01, identity)
    assert result["verdict"] == "FAIL"
    assert any("same actor decided twice" in item["detail"] for item in result["contradictions"])


def test_non_monotonic_mulligan_revisions_are_fail() -> None:
    document, af01, identity = _synthetic()
    frames = [
        entry for entry in document["results"]["2P"]["decision_tape"] if entry["kind"] == "MULLIGAN"
    ]
    frames[1]["revision"] = frames[0]["revision"]
    result = _derive(document, af01, identity)
    assert result["verdict"] == "FAIL"
    assert any("strictly increasing" in item["detail"] for item in result["contradictions"])


def test_a_foreign_candidate_artifact_cannot_derive_this_candidate() -> None:
    document, af01, identity = _synthetic()
    document["candidate"] = "some-other-engine"
    result = _derive(document, af01, identity)
    assert result["verdict"] == "FAIL"
    assert any("not 'forge'" in item["detail"] for item in result["contradictions"])


def test_a_stale_engine_identity_is_fail() -> None:
    document, af01, identity = _synthetic()
    document["runtime_identity"] = {**identity, "engine_candidate_commit": "f" * 40}
    result = _derive(document, af01, identity)
    assert result["verdict"] == "FAIL"


def test_a_carried_forward_boundary_is_fail() -> None:
    document, af01, identity = _synthetic()
    document["boundary"] = "CARRIED_FORWARD_NOT_REEXECUTED"
    result = _derive(document, af01, identity)
    assert result["verdict"] == "FAIL"
    assert any(
        "not a fresh current-boundary" in item["detail"] for item in result["contradictions"]
    )


def test_a_violated_r2_provenance_is_fail_and_an_unmeasured_one_is_unknown() -> None:
    document, af01, identity = _synthetic()
    violated = dict(af01, decision_identity_provenance={"verified": False})
    assert _derive(document, violated, identity)["verdict"] == "FAIL"
    unmeasured = dict(af01, decision_identity_provenance={"verified": None})
    assert _derive(document, unmeasured, identity)["verdict"] == "UNKNOWN"


# --------------------------------------------------------------------------- #
# Gaps: an unmeasured element stays UNKNOWN
# --------------------------------------------------------------------------- #


def test_a_missing_required_cardinality_is_unknown() -> None:
    document, af01, identity = _synthetic()
    del document["results"]["5P"]
    result = _derive(document, af01, identity)
    assert result["verdict"] == "UNKNOWN"
    assert any(item["cardinality"] == "5P" for item in result["gaps"])


def test_a_missing_engine_response_is_unknown() -> None:
    document, af01, identity = _synthetic()
    document["results"]["2P"]["observations"] = [
        observation
        for observation in document["results"]["2P"]["observations"]
        if observation["step"] != "priority_pass"
    ]
    result = _derive(document, af01, identity)
    assert result["verdict"] == "UNKNOWN"
    assert any("no engine response payload" in item["detail"] for item in result["gaps"])


def test_a_missing_runtime_identity_is_unknown() -> None:
    document, af01, _identity = _synthetic()
    result = _derive(document, af01, {})
    assert result["verdict"] == "UNKNOWN"


def test_an_absent_artifact_is_unknown() -> None:
    result = db.derive_decision_boundary("forge", None, {}, {})
    assert result["verdict"] == "UNKNOWN"


def test_a_priority_frame_that_never_reached_beyond_pregame_is_unknown() -> None:
    document, af01, identity = _synthetic()
    document["results"]["2P"]["decision_tape"] = [
        entry for entry in document["results"]["2P"]["decision_tape"] if entry["kind"] != "PRIORITY"
    ]
    result = _derive(document, af01, identity)
    assert result["verdict"] == "UNKNOWN"
    assert any(
        "vacuous" in item["detail"] or "no priority frame follows" in item["detail"]
        for item in result["gaps"]
    )


def test_a_run_that_never_reached_priority_is_unknown() -> None:
    document, af01, identity = _synthetic()
    document["results"]["2P"]["terminal_facts"]["priority_reached"] = False
    result = _derive(document, af01, identity)
    assert result["verdict"] == "UNKNOWN"


def test_the_gate_is_no_longer_hard_coded_by_candidate() -> None:
    import importlib.util
    import inspect

    path = REPO / "scripts/assemble_current_boundary_evidence.py"
    spec = importlib.util.spec_from_file_location("assembler_af04_source", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = inspect.getsource(module.af04_gate)
    # The previous defect was a candidate-conditional literal verdict and a
    # premise asserted in prose rather than measured.
    assert "Forge stays UNKNOWN" not in source
    assert 'if candidate == "xmage"' not in source
    assert '"verdict": "UNKNOWN"' not in source
    assert "decision_boundary_mod.derive_decision_boundary" in source


def test_the_derivation_does_not_mutate_the_evidence() -> None:
    document, af01, identity = _synthetic()
    snapshot = copy.deepcopy(document)
    _derive(document, af01, identity)
    assert document == snapshot
