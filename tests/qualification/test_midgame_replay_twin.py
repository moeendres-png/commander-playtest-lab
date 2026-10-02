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

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

import pytest

from commander_lab.qualification.current_boundary import midgame_replay_twin as mrt
from commander_lab.qualification.current_boundary import midgame_rows as midgame_rows_mod
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
        "pilot_state": {"turn_number": 1, "phase": "precombat_main"},
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
    checkpoints = [
        {"decision": decision, "rules_random_calls": 7, "privileged_state_digest": "p" * 64}
    ]
    stream = mrt.input_stream(tape, checkpoints, {NATIVE_A: "obj:replay-mountain-1"})
    assert [entry["kind"] for entry in stream] == ["complete_midgame_arrival", "decision"]
    assert stream[1]["rules_random_calls"] == 7
    assert stream[1]["privileged_state_digest"] == "p" * 64
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
        "rules_rng": {
            "rng_call_coordinates": [
                # The engine's own Rules-RNG operation with its result ...
                {
                    "operation": "LIBRARY_SHUFFLE",
                    "sequence": 0,
                    "seat": 0,
                    "before": 0,
                    "after": 99,
                    "library_size": 99,
                    "result_digest": "r" * 64,
                },
                # ... and the randomness each answer let the engine consume.
                {"sequence": 0, "before": 396, "after": 396},
            ]
        },
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
            {
                "public_state_digest": "p" * 64,
                "observation_digest": "o" * 64,
                "privileged_state_digest": "v" * 64,
            }
        ],
        "terminal": {"complete": True, "privileged_state_digest": "t" * 64},
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


DETECTED = {"control": "DIFFERENT_SEED_CHANGES_RULES_RNG_RESULT", "detected": True}


@pytest.mark.parametrize("fixture_id", mrt.ROWS)
def test_every_row_property_holds_on_a_verified_twin(fixture_id: str) -> None:
    record, replay = _runs()
    properties = mrt.row_properties(fixture_id, record, replay, True, seed_control=DETECTED)
    assert properties["scenario_obligation_observed"] is True
    assert all(properties.values()), properties


@pytest.mark.parametrize("fixture_id", mrt.ROWS)
def test_no_row_holds_without_a_verified_twin(fixture_id: str) -> None:
    record, replay = _runs()
    assert not all(
        mrt.row_properties(fixture_id, record, replay, False, seed_control=DETECTED).values()
    )


def test_a_call_count_without_a_result_is_no_rules_rng_tape() -> None:
    """P1 of the review: equal counts and a shuffle event prove nothing about
    the randomness; the row needs the operation's result."""
    record, replay = _runs()
    record.twin.rules_rng["rng_call_coordinates"] = [{"sequence": 0, "before": 3, "after": 3}]
    properties = mrt.row_properties("RNG_RULES_TAPE", record, replay, True, seed_control=DETECTED)
    assert properties["rules_rng_results_recorded"] is False
    assert properties["p1_library_shuffle_result_taped"] is False


def test_an_operation_that_consumed_no_randomness_is_not_a_result() -> None:
    record, replay = _runs()
    record.twin.rules_rng["rng_call_coordinates"][0]["after"] = 0
    properties = mrt.row_properties("RNG_RULES_TAPE", record, replay, True, seed_control=DETECTED)
    assert properties["rules_rng_results_recorded"] is False


def test_a_result_the_seed_does_not_change_is_no_rng_evidence() -> None:
    record, replay = _runs()
    for control in (None, {"detected": False}):
        properties = mrt.row_properties(
            "RNG_RULES_TAPE", record, replay, True, seed_control=control
        )
        assert properties["rng_result_depends_on_seed"] is False


def test_p1s_own_shuffle_result_is_required() -> None:
    record, replay = _runs()
    properties = mrt.row_properties(
        "RNG_RULES_TAPE", record, replay, True, seat=2, seed_control=DETECTED
    )
    assert properties["p1_library_shuffle_result_taped"] is False


def test_the_state_hash_row_needs_the_privileged_hashes() -> None:
    record, replay = _runs()
    record.twin.checkpoint_state_hashes[0]["privileged_state_digest"] = None
    properties = mrt.row_properties("REPLAY_STATE_HASHES", record, replay, True)
    assert properties["privileged_hashes_recorded"] is False


def test_a_frame_without_the_deciders_observation_fails_closed() -> None:
    decision = _decision("d-1", [_mountain("o-1", NATIVE_A)])
    decision.pop("pilot_state")
    with pytest.raises(mrt.ReplayTwinRowError, match="pilot_state"):
        mrt.decision_identity(decision)


def test_first_shuffle_digest_reads_the_seats_first_shuffle() -> None:
    results = [
        {"operation": "LIBRARY_SHUFFLE", "seat": 1, "result_digest": "x"},
        {"operation": "LIBRARY_SHUFFLE", "seat": 0, "result_digest": "first"},
        {"operation": "LIBRARY_SHUFFLE", "seat": 0, "result_digest": "mulligan"},
    ]
    assert mrt.first_shuffle_digest(results, 0) == "first"
    assert mrt.first_shuffle_digest(results, 3) is None


def test_p1_seat_follows_the_records_seat_order() -> None:
    record = {"players": [{"player_id": "P2", "seat": 2}, {"player_id": "P1", "seat": 1}]}
    assert mrt.p1_seat(record) == 0
    with pytest.raises(mrt.ReplayTwinRowError):
        mrt.p1_seat({"players": [{"player_id": "P2", "seat": 1}]})


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


# --------------------------------------------------------------------------- #
# Record, replay and the seed control against a scripted fake engine
# --------------------------------------------------------------------------- #


def _sha(*parts: object) -> str:
    return hashlib.sha256("|".join(str(part) for part in parts).encode()).hexdigest()


class FakeEngine(mrt.TapingLaneClient):
    """A scripted engine process: fresh native ids per process, seeded results.

    It casts Burn Down the House and creates three Devils. ``seed_sensitive``
    makes the shuffle result depend on the seed; ``diverge_frame`` offers a
    different second frame; ``diverge_terminal`` ends in a different state.
    """

    processes = 0

    def __init__(
        self,
        *,
        seed_sensitive: bool = True,
        diverge_frame: bool = False,
        diverge_terminal: bool = False,
    ) -> None:
        super().__init__(("fake-engine",), Path("."))
        FakeEngine.processes += 1
        self.process_number = FakeEngine.processes
        self.seed_sensitive = seed_sensitive
        self.diverge_frame = diverge_frame
        self.diverge_terminal = diverge_terminal
        self.burn = str(uuid.uuid4())
        self.devils = [str(uuid.uuid4()) for _ in range(3)]
        self.stage = 0
        self.seed = 0

    def __enter__(self) -> FakeEngine:
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    @property
    def pid(self) -> int | None:
        return self.process_number

    def _decision(self) -> dict[str, Any] | None:
        state = {"turn_number": 1, "phase": "precombat_main", "stage": self.stage}
        if self.stage == 0:
            options = [
                {
                    "option_id": f"cast-{self.burn}",
                    "option_type": "action",
                    "label": "Cast Burn Down the House",
                    "metadata": {"object_id": self.burn},
                },
                {"option_id": "pass", "option_type": "action", "label": "Pass priority"},
            ]
            return {
                "decision_id": f"{uuid.uuid4()}",
                "decision_class": "priority",
                "seat": 0,
                "actor_id": "P1",
                "minimum_selections": 1,
                "maximum_selections": 1,
                "legal_options": options,
                "pilot_state": state,
            }
        if self.stage == 1:
            mode_label = "Deal 6 damage" if self.diverge_frame else "Deal 5 damage"
            options = [
                {
                    "option_id": "m1",
                    "option_type": "choice",
                    "label": "Devil creature tokens",
                    "metadata": {"choice": "Devil creature tokens"},
                },
                {
                    "option_id": "m2",
                    "option_type": "choice",
                    "label": mode_label,
                    "metadata": {"choice": mode_label},
                },
            ]
            return {
                "decision_id": f"{uuid.uuid4()}",
                "decision_class": "mode",
                "seat": 0,
                "actor_id": "P1",
                "minimum_selections": 1,
                "maximum_selections": 1,
                "legal_options": options,
                "pilot_state": state,
            }
        return None

    def request(self, message_type: str, payload: Any, **_: Any) -> dict[str, Any]:
        result: dict[str, Any]
        if message_type == "get_provider_version":
            self._engine_commit = COMMIT
            result = {"success": True, "payload": {"engine_commit": COMMIT}}
        elif message_type == "get_capabilities":
            result = {
                "success": True,
                "payload": {"capabilities": {"starting_state_dimensions": {"schema_version": "1"}}},
            }
        elif message_type == "create_midgame_game":
            self.seed = int(payload["seed"])
            result = {
                "success": True,
                "payload": {
                    "game_id": payload["game_id"],
                    "placed_objects": {"obj:replay-burn": self.burn},
                    "rules_seed_binding": {
                        "explicit_seed": self.seed,
                        "rules_seed_explicit": True,
                        "rules_seed_matches": True,
                        "seed_scope": "game",
                    },
                },
            }
        elif message_type in {"start_midgame_game", "complete_midgame_arrival"}:
            battlefield = self.devils if self.stage >= 2 else []
            result = {"success": True, "payload": {"observation": {"battlefield": battlefield}}}
        elif message_type == "get_midgame_decision":
            result = {"success": True, "payload": {"decision": self._decision()}}
        elif message_type == "submit_midgame_decision":
            self.stage += 1
            result = {"success": True, "payload": {}}
        elif message_type == "get_rules_rng_tape":
            seed_part = self.seed if self.seed_sensitive else 0
            terminal = "diverged" if (self.diverge_terminal and self.stage >= 2) else ""
            result = {
                "success": True,
                "payload": {
                    "rules_random_calls": 99,
                    "rules_rng_results": [
                        {
                            "operation": "LIBRARY_SHUFFLE",
                            "sequence": 0,
                            "seat": 0,
                            "before": 0,
                            "after": 99,
                            "library_size": 99,
                            "result_digest": _sha("shuffle", seed_part),
                        }
                    ],
                    "privileged_state_digest": _sha("state", self.stage, terminal),
                },
            }
        elif message_type == "get_midgame_events":
            events: list[dict[str, Any]] = [
                {"sequence": 1, "type": "LIBRARY_SHUFFLED", "player_player": "P1"}
            ]
            if self.stage >= 2:
                events += [
                    {"sequence": 2 + index, "type": "CREATED_TOKEN", "object": devil}
                    for index, devil in enumerate(self.devils)
                ]
            result = {"success": True, "payload": {"events": events}}
        else:
            result = {"success": False, "errors": [{"code": "unsupported_message"}]}
        self._tape.append(
            {"message_type": message_type, "request": {"payload": payload}, "response": result}
        )
        return result


class _FakeIdentity:
    def __init__(self, role: str, pid: int) -> None:
        self.role, self.pid = role, pid

    def to_document(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "pid": self.pid,
            "start_ticks": 1000 + self.pid,
            "boot_id": "boot",
            "observed": True,
        }


@pytest.fixture
def fake_lane(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Patches the executor (record only), process identity and sleeps."""
    calls = {"execute_row": 0}

    class _Execution:
        def document(self) -> dict[str, Any]:
            return {"verified": True, "terminal_facts": {"tokens_created": 3}}

    def fake_execute_row(client: Any, record: Any, created: Any, spec: Any) -> _Execution:
        calls["execute_row"] += 1
        client.pending_decision()
        client.complete_arrival()
        cast = client.pending_decision()
        client.submit_options(cast, [cast["legal_options"][0]["option_id"]])
        mode = client.pending_decision()
        devils = [o["option_id"] for o in mode["legal_options"] if o["label"].startswith("Devil")]
        client.submit_options(mode, devils)
        return _Execution()

    monkeypatch.setattr(midgame_rows_mod, "execute_row", fake_execute_row)
    monkeypatch.setattr(
        mrt, "_process_identity", lambda client, role: _FakeIdentity(role, client.pid)
    )
    monkeypatch.setattr("time.sleep", lambda _s: None)
    return calls


def _scenario(fixture_id: str) -> dict[str, Any]:
    return {
        **_record(fixture_id),
        "players": [{"player_id": "P1", "seat": 1}, {"player_id": "P2", "seat": 2}],
    }


def _factory(**replay_flags: Any) -> Any:
    made: list[FakeEngine] = []

    def factory(_workspace: Path) -> FakeEngine:
        # The first process records; every later one replays or controls.
        engine = FakeEngine(**({} if not made else replay_flags))
        made.append(engine)
        return engine

    factory.made = made  # type: ignore[attr-defined]
    return factory


@pytest.mark.parametrize("fixture_id", mrt.ROWS)
def test_a_genuine_clean_process_replay_verifies_every_row(
    fake_lane: dict[str, Any], fixture_id: str
) -> None:
    factory = _factory()
    document = mrt.twin_row(
        Path("."),
        _scenario(fixture_id),
        seed=424242,
        lab_source={"commit": "l"},
        client_factory=factory,
    )
    assert document["verified"] is True, document["detail"]
    assert document["demonstrated_divergence"] is None
    # The replay never ran the executor: only the record did.
    assert fake_lane["execute_row"] == 1
    # Record and replay (and, for the RNG row, the seed control) are distinct processes.
    pids = {engine.pid for engine in factory.made}
    assert len(pids) == len(factory.made) == (3 if fixture_id == "RNG_RULES_TAPE" else 2)
    twin = document["clean_process_twin"]
    assert twin["terminal_outcome"].get("terminal_facts") is None
    if fixture_id == "RNG_RULES_TAPE":
        assert document["seed_control"]["detected"] is True


def test_a_seed_insensitive_result_is_no_rng_evidence(fake_lane: dict[str, Any]) -> None:
    def factory(_workspace: Path) -> FakeEngine:
        return FakeEngine(seed_sensitive=False)

    document = mrt.twin_row(
        Path("."),
        _scenario("RNG_RULES_TAPE"),
        seed=424242,
        lab_source={"commit": "l"},
        client_factory=factory,
    )
    assert document["verified"] is False
    assert document["row_properties"]["rng_result_depends_on_seed"] is False
    assert document["seed_control"]["detected"] is False


def test_a_diverging_frame_is_a_demonstrated_violation(fake_lane: dict[str, Any]) -> None:
    document = mrt.twin_row(
        Path("."),
        _scenario("REPLAY_CLEAN_PROCESS"),
        seed=424242,
        lab_source={"commit": "l"},
        client_factory=_factory(diverge_frame=True),
    )
    assert document["verified"] is False
    assert document["demonstrated_divergence"]["classification"] == "REPLAY_FRAME_DIVERGENCE"


def test_the_replay_terminal_is_its_own(fake_lane: dict[str, Any]) -> None:
    """A replay ending in a different state is caught by its own terminal digest."""
    document = mrt.twin_row(
        Path("."),
        _scenario("REPLAY_CLEAN_PROCESS"),
        seed=424242,
        lab_source={"commit": "l"},
        client_factory=_factory(diverge_terminal=True),
    )
    assert document["verified"] is False
    finding = document["demonstrated_divergence"]
    assert finding["classification"] == "REPLAY_TAPE_DIVERGENCE"
    assert "terminal_outcome" in finding["differing_checks"]


def test_a_harness_refusal_is_not_a_demonstrated_violation(fake_lane: dict[str, Any]) -> None:
    record = _scenario("REPLAY_CLEAN_PROCESS")
    recorded = mrt.record_process(
        Path("."), record, seed=1, lab_source={}, client_factory=_factory()
    )
    replayed = mrt.replay_process(
        Path("."), record, recorded, seed=1, lab_source={}, client_factory=_factory()
    )
    replayed.twin.failure = "CHOSEN_OPTION_AMBIGUOUS"
    replayed.twin.terminal = {"complete": False, "kind": "REPLAY_FAILED_CLOSED"}
    comparison = twins.compare_twin_runs(recorded.twin, replayed.twin)
    assert mrt.demonstrated_divergence(comparison, recorded, replayed) is None
    # An unverified record demonstrates nothing either.
    recorded.execution = {"verified": False}
    replayed.divergence = True
    assert mrt.demonstrated_divergence(comparison, recorded, replayed) is None


# --------------------------------------------------------------------------- #
# Assembler-facing binding
# --------------------------------------------------------------------------- #


def _bound_document(**overrides: Any) -> dict[str, Any]:
    rows = {
        fixture: {
            "verified": True,
            "receipt_digest": f"digest-{fixture}",
            "demonstrated_divergence": None,
        }
        for fixture in mrt.ROWS
    }
    document = {
        "execution_mode": mrt.EXECUTION_MODE,
        "candidate_commit": COMMIT,
        "runner_digest": "r" * 64,
        "rows": rows,
    }
    document.update(overrides)
    return document


def test_receipts_bind_only_to_a_complete_bound_document() -> None:
    bound = mrt.bound_receipt_digests(
        _bound_document(), candidate_commit=COMMIT, runner_digest="r" * 64
    )
    assert bound == {fixture: f"digest-{fixture}" for fixture in mrt.ROWS}
    partial = _bound_document()
    partial["rows"].pop("RNG_RULES_TAPE")
    for document, commit, runner in (
        (partial, COMMIT, "r" * 64),
        (_bound_document(), "d" * 40, "r" * 64),
        (_bound_document(), COMMIT, "x" * 64),
        (_bound_document(execution_mode="OTHER"), COMMIT, "r" * 64),
        (None, COMMIT, "r" * 64),
    ):
        assert (
            mrt.bound_receipt_digests(document, candidate_commit=commit, runner_digest=runner) == {}
        )


def test_a_bound_demonstrated_divergence_is_reported_as_a_failure() -> None:
    document = _bound_document()
    document["rows"]["REPLAY_EVENT_TAPE"]["demonstrated_divergence"] = {
        "classification": "REPLAY_TAPE_DIVERGENCE"
    }
    failures = mrt.demonstrated_failures(document, candidate_commit=COMMIT, runner_digest="r" * 64)
    assert failures == {"REPLAY_EVENT_TAPE": {"classification": "REPLAY_TAPE_DIVERGENCE"}}
    assert (
        mrt.demonstrated_failures(document, candidate_commit="d" * 40, runner_digest="r" * 64) == {}
    )
