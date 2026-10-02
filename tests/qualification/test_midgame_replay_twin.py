"""AF09 midgame clean-process replay twin: tape identity, replay resolution, producer.

These tests use no engine. The live record/replay of the five replay/RNG rows
is executed by the PB-03 runner on the production midgame lane; here the pure
parts are pinned: which requests are external inputs, how an answer is
identified across processes, that an indistinguishable answer fails closed
instead of picking a first match, how each row's own property is read off the
tapes, and that only a verified twin built by the candidate commit earns a
receipt.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from commander_lab.qualification.current_boundary import midgame_replay_twin as mrt
from commander_lab.qualification.current_boundary import receipts as receipt_mod
from commander_lab.qualification.current_boundary import replay_twins as twins

NATIVE_A = "11111111-1111-4111-8111-111111111111"
NATIVE_B = "22222222-2222-4222-8222-222222222222"
NATIVE_C = "33333333-3333-4333-8333-333333333333"
COMMIT = "c" * 40


def _mountain(option_id: str, native: str) -> dict[str, Any]:
    return {
        "option_id": option_id,
        "option_type": "object",
        "label": "Mountain",
        "metadata": {"object_id": native},
    }


def _decision(decision_id: str, options: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    return {
        "decision_id": decision_id,
        "decision_class": "mana_payment",
        "seat": 0,
        "actor_id": "actor-1",
        "minimum_selections": 1,
        "maximum_selections": 1,
        "legal_options": options,
        **extra,
    }


def _answer(decision_id: str, selected: list[str], success: bool = True) -> dict[str, Any]:
    return {
        "message_type": "submit_midgame_decision",
        "request": {
            "payload": {"response": {"decision_id": decision_id, "selected_option_ids": selected}}
        },
        "response": {"success": success},
    }


# --------------------------------------------------------------------------- #
# Row spec
# --------------------------------------------------------------------------- #


def test_the_five_rows_are_the_denominator_replay_rows() -> None:
    from commander_lab.qualification.current_boundary.full107 import REPLAY_ROWS

    assert set(mrt.ROWS) == set(REPLAY_ROWS)


def test_row_spec_refuses_a_non_replay_row() -> None:
    with pytest.raises(mrt.ReplayTwinRowError):
        mrt.row_spec("CARD_01")


def test_row_spec_binds_every_record_token_to_an_engine_observation() -> None:
    spec = mrt.row_spec("RNG_RULES_TAPE")
    tokens = dict(spec.token_bindings)
    assert set(tokens) == {
        "rules_rng:library_shuffle:P1",
        "decision:choose_mode:create_devils",
        "create_Devil_token:3",
    }
    assert tokens["decision:choose_mode:create_devils"].value == "mode"
    # The Rules RNG operation is the start-of-game shuffle, so the tape is read
    # from the engine's first event.
    assert spec.observe_from_game_start is True


# --------------------------------------------------------------------------- #
# External input stream
# --------------------------------------------------------------------------- #


def test_only_accepted_state_changing_requests_are_inputs() -> None:
    decision = _decision("d-1", [_mountain("o-1", NATIVE_A)])
    tape = [
        {"message_type": "get_midgame_state", "response": {"success": True}},
        _answer("d-1", ["o-1"], success=False),
        {"message_type": "complete_midgame_arrival", "response": {"success": True}},
        _answer("d-1", ["o-1"]),
    ]
    checkpoints = [{"decision": decision, "rules_random_calls": 7}]
    stream = mrt.input_stream(tape, checkpoints, {NATIVE_A: "obj:replay-mountain-1"})
    assert [entry["kind"] for entry in stream] == ["complete_midgame_arrival", "decision"]
    assert stream[1]["rules_random_calls"] == 7
    assert stream[1]["frame"] == mrt.decision_identity(decision)


def test_an_answer_to_an_untaped_decision_fails_closed() -> None:
    with pytest.raises(mrt.ReplayTwinRowError, match="never taped"):
        mrt.input_stream([_answer("d-9", ["o-1"])], [], {})


def test_an_answer_selecting_an_unoffered_option_fails_closed() -> None:
    decision = _decision("d-1", [_mountain("o-1", NATIVE_A)])
    with pytest.raises(mrt.ReplayTwinRowError, match="did not offer"):
        mrt.input_stream(
            [_answer("d-1", ["o-2"])], [{"decision": decision, "rules_random_calls": 0}], {}
        )


# --------------------------------------------------------------------------- #
# Cross-process answer identity
# --------------------------------------------------------------------------- #


def test_record_objects_distinguish_otherwise_identical_offers() -> None:
    decision = _decision("d-1", [_mountain("o-1", NATIVE_A), _mountain("o-2", NATIVE_B)])
    prints = mrt._fingerprints_by_option(
        decision, {NATIVE_A: "obj:replay-mountain-1", NATIVE_B: "obj:replay-mountain-2"}
    )
    assert prints["o-1"] != prints["o-2"]


def test_the_identity_survives_a_different_process_local_id() -> None:
    record = _decision("d-1", [_mountain("o-1", NATIVE_A)])
    replay = _decision("d-7", [_mountain("o-5", NATIVE_C)])
    left = mrt._fingerprints_by_option(record, {NATIVE_A: "obj:replay-mountain-1"})
    right = mrt._fingerprints_by_option(replay, {NATIVE_C: "obj:replay-mountain-1"})
    assert left["o-1"] == right["o-5"]


def test_unrecorded_objects_collide_and_the_replay_refuses_a_first_match() -> None:
    decision = _decision("d-1", [_mountain("o-1", NATIVE_A), _mountain("o-2", NATIVE_B)])
    prints = mrt._fingerprints_by_option(decision, {})
    assert prints["o-1"] == prints["o-2"]
    with pytest.raises(mrt.ReplayTwinRowError, match="CHOSEN_OPTION_AMBIGUOUS"):
        mrt._resolve(decision, [prints["o-1"]], {})


def test_a_recorded_answer_the_engine_no_longer_offers_fails_closed() -> None:
    decision = _decision("d-1", [_mountain("o-1", NATIVE_A)])
    with pytest.raises(mrt.ReplayTwinRowError, match="matched 0 offers"):
        mrt._resolve(decision, ["f" * 64], {NATIVE_A: "obj:replay-mountain-1"})


def test_a_unique_recorded_answer_resolves_to_the_offered_option() -> None:
    names = {NATIVE_A: "obj:replay-mountain-1", NATIVE_B: "obj:replay-mountain-2"}
    decision = _decision("d-1", [_mountain("o-1", NATIVE_A), _mountain("o-2", NATIVE_B)])
    wanted = mrt._fingerprints_by_option(decision, names)["o-2"]
    assert mrt._resolve(decision, [wanted], names) == ["o-2"]


# --------------------------------------------------------------------------- #
# Canonical events and Rules RNG
# --------------------------------------------------------------------------- #


def test_canonical_events_drop_process_local_identity_but_keep_history() -> None:
    record = [
        {"sequence": 1, "type": "CREATED_TOKEN", "object": NATIVE_A},
        {"sequence": 2, "type": "CREATED_TOKEN", "object": NATIVE_B},
        {"sequence": 3, "type": "TAPPED", "object": NATIVE_A},
    ]
    replay = [
        {"sequence": 9, "type": "CREATED_TOKEN", "object": NATIVE_C},
        {"sequence": 10, "type": "CREATED_TOKEN", "object": NATIVE_A},
        {"sequence": 11, "type": "TAPPED", "object": NATIVE_C},
    ]
    assert mrt.canonical_events(record) == mrt.canonical_events(replay)
    other_history = [*replay[:2], {"sequence": 11, "type": "TAPPED", "object": NATIVE_A}]
    assert mrt.canonical_events(record) != mrt.canonical_events(other_history)


def test_rules_rng_coordinates_bracket_each_answer() -> None:
    created = {
        "rules_seed_binding": {
            "explicit_seed": 424242,
            "rules_seed_explicit": True,
            "rules_seed_matches": True,
        }
    }
    stream = [
        {"kind": "complete_midgame_arrival"},
        {"kind": "decision", "rules_random_calls": 3},
        {"kind": "decision", "rules_random_calls": 5},
    ]
    rng = mrt._rules_rng(created, 424242, stream, 6)
    assert rng["controlled"] is True
    assert rng["rng_call_coordinates"] == [
        {"sequence": 0, "before": 3, "after": 5},
        {"sequence": 1, "before": 5, "after": 6},
    ]


def test_an_unmatched_seed_is_never_acknowledged() -> None:
    created = {
        "rules_seed_binding": {
            "explicit_seed": 1,
            "rules_seed_explicit": True,
            "rules_seed_matches": False,
        }
    }
    rng = mrt._rules_rng(created, 424242, [], None)
    assert rng["acknowledged_seed"] is None
    assert rng["controlled"] is False


# --------------------------------------------------------------------------- #
# Row properties
# --------------------------------------------------------------------------- #


def _twin(role: str, **overrides: Any) -> twins.TwinRun:
    base: dict[str, Any] = {
        "role": role,
        "candidate": "xmage",
        "fixture_identity": {"fixture_id": "REPLAY_CLEAN_PROCESS"},
        "candidate_build": {"engine_commit": COMMIT},
        "lab_source": {"commit": "l" * 40},
        "process": None,
        "rules_rng": {"rng_call_coordinates": [{"sequence": 0, "before": 3, "after": 3}]},
        "decisions": [
            {
                "index": 0,
                "frame": {"decision_class": "mode"},
                "selected_fingerprints": ["a" * 64],
                "numeric_choice": None,
            }
        ],
        "semantic_events": [
            {"type": "LIBRARY_SHUFFLED", "player_player": "P1"},
            *({"type": "CREATED_TOKEN", "object": f"native#{index}"} for index in range(3)),
        ],
        "checkpoint_state_hashes": [
            {"public_state_digest": "p" * 64, "observation_digest": "o" * 64}
        ],
        "terminal": {"complete": True},
    }
    base.update(overrides)
    return twins.TwinRun(**base)


def _runs(**replay_overrides: Any) -> tuple[mrt.ProcessRun, mrt.ProcessRun]:
    stream = [{"kind": "decision"}]
    record = mrt.ProcessRun(
        "RECORD",
        _twin("RECORD"),
        execution={"verified": True},
        stream=stream,
        native_object_ids={"obj:replay-burn": NATIVE_A},
    )
    replay = mrt.ProcessRun(
        "REPLAY",
        _twin("REPLAY", **replay_overrides),
        stream=list(stream),
        native_object_ids={"obj:replay-burn": NATIVE_B},
    )
    return record, replay


@pytest.mark.parametrize("fixture_id", mrt.ROWS)
def test_every_row_property_holds_on_a_verified_twin(fixture_id: str) -> None:
    record, replay = _runs()
    properties = mrt.row_properties(fixture_id, record, replay, True)
    assert properties["scenario_obligation_observed"] is True
    assert all(properties.values()), properties


@pytest.mark.parametrize("fixture_id", mrt.ROWS)
def test_no_row_holds_without_a_verified_twin(fixture_id: str) -> None:
    record, replay = _runs()
    assert not all(mrt.row_properties(fixture_id, record, replay, False).values())


def test_a_replay_that_failed_closed_did_not_consume_only_the_tape() -> None:
    record, replay = _runs(failure="CHOSEN_OPTION_AMBIGUOUS")
    properties = mrt.row_properties("REPLAY_CLEAN_PROCESS", record, replay, True)
    assert properties["replay_consumed_only_the_tape"] is False


def test_shared_process_local_identity_is_not_a_clean_process() -> None:
    record, replay = _runs()
    replay.native_object_ids = dict(record.native_object_ids)
    properties = mrt.row_properties("REPLAY_STATE_HASHES", record, replay, True)
    assert properties["process_local_identity_differs"] is False


def test_a_native_id_on_the_event_tape_fails_the_event_row() -> None:
    record, replay = _runs()
    record.twin.semantic_events.append({"type": "TAPPED", "object": NATIVE_A})
    properties = mrt.row_properties("REPLAY_EVENT_TAPE", record, replay, True)
    assert properties["event_tape_free_of_native_ids"] is False


def test_rng_coordinates_inside_the_decision_tape_fail_the_rng_row() -> None:
    record, replay = _runs()
    record.twin.decisions[0]["rules_random_calls"] = 3
    properties = mrt.row_properties("RNG_RULES_TAPE", record, replay, True)
    assert properties["rng_tape_separate_from_decisions"] is False


def test_row_properties_refuse_a_non_replay_row() -> None:
    record, replay = _runs()
    with pytest.raises(mrt.ReplayTwinRowError):
        mrt.row_properties("CARD_01", record, replay, True)


# --------------------------------------------------------------------------- #
# Producer
# --------------------------------------------------------------------------- #


def _record(fixture_id: str) -> dict[str, Any]:
    return {
        "fixture_id": fixture_id,
        "requested_state_digest": "s" * 64,
        "obligation_digest": "b" * 64,
        "expected_events": {"required_events": ["CREATED_TOKEN"]},
        "terminal_postconditions": ["three Devil tokens"],
    }


def _twin_document(fixture_id: str, *, verified: bool, engine_commit: str) -> dict[str, Any]:
    twin = {
        "verified": verified,
        "verdict": "PASS",
        "candidate_build": {"engine_commit": engine_commit},
    }
    return {
        "fixture_id": fixture_id,
        "verified": verified,
        "detail": "fake",
        "clean_process_twin": twin,
        "row_properties": {"clean_replay_equal_checkpoints": verified},
        "twin_digest": twins.sha256_json(twin),
    }


def _produce(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcomes: dict[str, tuple[bool, str]]
) -> dict[str, Any]:
    def fake_twin_row(workspace: Path, record: dict[str, Any], **_: Any) -> dict[str, Any]:
        verified, commit = outcomes[record["fixture_id"]]
        return _twin_document(record["fixture_id"], verified=verified, engine_commit=commit)

    monkeypatch.setattr(mrt, "twin_row", fake_twin_row)
    monkeypatch.setattr(mrt, "lab_source_identity", lambda root: {"commit": "l" * 40})
    return mrt.execute_and_persist(
        workspace=tmp_path,
        records={fixture: _record(fixture) for fixture in mrt.ROWS},
        candidate_commit=COMMIT,
        runner_digest="r" * 64,
        out_dir=tmp_path / "positive",
        lab_root=tmp_path,
        fixtures=tuple(outcomes),
    )


def test_only_a_verified_twin_built_by_the_candidate_earns_a_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    document = _produce(
        tmp_path,
        monkeypatch,
        {
            "REPLAY_CLEAN_PROCESS": (True, COMMIT),
            "REPLAY_EVENT_TAPE": (True, "d" * 40),
            "RNG_RULES_TAPE": (False, COMMIT),
        },
    )
    assert document["rows_declared"] == 3
    assert document["rows_verified"] == 1
    assert "not the candidate" in document["rows"]["REPLAY_EVENT_TAPE"]["detail"]
    receipts, rejected = receipt_mod.collect_positive_fixture_receipts(tmp_path / "positive")
    assert rejected == []
    assert [receipt["fixture_id"] for receipt in receipts] == ["REPLAY_CLEAN_PROCESS"]
    receipt = receipts[0]
    assert receipt["test_identity"] == mrt.TEST_IDENTITY_PREFIX + "REPLAY_CLEAN_PROCESS"
    assert receipt["candidate_commit"] == COMMIT
    assert receipt["runner_digest"] == "r" * 64
    assert receipt["obligation_exercised"]["obligation_digest"] == "b" * 64
    assert document["rows"]["REPLAY_CLEAN_PROCESS"]["receipt_digest"] == receipt["receipt_digest"]
    assert document["clean_process_twin"]["verified"] is True


def test_a_rerun_removes_the_stale_receipt_of_a_row_that_no_longer_verifies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _produce(tmp_path, monkeypatch, {"REPLAY_STATE_HASHES": (True, COMMIT)})
    assert list((tmp_path / "positive").glob("*.json"))
    document = _produce(tmp_path, monkeypatch, {"REPLAY_STATE_HASHES": (False, COMMIT)})
    assert document["rows_verified"] == 0
    assert document["clean_process_twin"] is None
    assert not list((tmp_path / "positive").glob("*.json"))


def test_the_receipt_file_names_never_collide_with_midgame_row_receipts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _produce(tmp_path, monkeypatch, {"RNG_RULES_TAPE": (True, COMMIT)})
    names = [path.name for path in (tmp_path / "positive").glob("*.json")]
    assert names == ["af09-midgame-replay-twin-RNG_RULES_TAPE.json"]
    payload = json.loads((tmp_path / "positive" / names[0]).read_text(encoding="utf-8"))
    assert payload["execution_mode"] == mrt.EXECUTION_MODE
