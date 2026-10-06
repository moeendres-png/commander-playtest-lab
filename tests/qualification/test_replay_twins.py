"""AF09 clean-process semantic replay twin contract tests.

The tests do not need an engine. They prove, on synthetic twins and a scripted
fake Protocol-2 bridge, that:

* the comparator detects every mandatory adversarial mutation;
* the normalization contract cannot remove a Rules-significant field;
* process identities must be observed and distinct;
* the generic-lane record/replay driver resolves externally supplied decisions
  by the engine's own semantic option identity and fails closed otherwise;
* a bounded-horizon terminal is never a replay PASS;
* the emitted ``clean_process_twin`` document satisfies the AF09 gate.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from commander_lab.qualification.current_boundary import replay_twins as rt

# --------------------------------------------------------------------------- #
# Synthetic twin runs
# --------------------------------------------------------------------------- #


def _process(role: str, pid: int) -> rt.ProcessIdentity:
    return rt.ProcessIdentity(
        role=role,
        pid=pid,
        start_ticks=1000 + pid,
        boot_id="test-boot-id",
        command_sha256=rt.sha256_json(["java", "-cp", "bridge", "full-game"]),
        command=("java", "-cp", "bridge", "full-game"),
        observation="test observation",
    )


def _decision(sequence: int, fingerprint: str) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "kind": "PRIORITY",
        "actor": "p1",
        "revision": sequence,
        "decision_class": "forge:priority/1",
        "policy": "pass_when_offered",
        "chosen_fingerprint": fingerprint,
        "chosen_action_type": "pass_priority",
        "offered_fingerprints": sorted([fingerprint, f"other-{sequence}"]),
        "pre_checkpoint": {
            "kind": "PRIORITY",
            "actor": "p1",
            "revision": sequence,
            "public_state_digest": f"{sequence:064x}"[-64:],
            "legal_set_digest": f"legal-{sequence}",
            "rng_calls": 100 + sequence,
        },
    }


def _event(sequence: int, fingerprint: str) -> dict[str, Any]:
    entry = {
        "sequence": sequence,
        "kind": "PRIORITY",
        "actor": "p1",
        "chosen_fingerprint": fingerprint,
        "rng_calls_before": 100 + sequence,
        "rng_calls_after": 101 + sequence,
        "public_state_digest_before": f"before-{sequence}",
        "public_state_digest_after": f"after-{sequence}",
        "event_offset_before": sequence,
        "event_offset_after": sequence + 1,
        "engine_executed": True,
    }
    return {**entry, "digest": rt.sha256_json(entry)}


def _checkpoint(sequence: int, scope: str, digest: str) -> dict[str, Any]:
    return {
        "sequence": sequence,
        "scope": scope,
        "public_state_digest": digest,
        "rng_calls": 100 + sequence,
        "event_offset": sequence,
    }


def make_run(role: str, pid: int, *, terminal_complete: bool = True) -> rt.TwinRun:
    decisions = [_decision(1, "fp-pass-1"), _decision(2, "fp-pass-2")]
    events = [_event(1, "fp-pass-1"), _event(2, "fp-pass-2")]
    checkpoints = [
        _checkpoint(0, "initial", "initial-state"),
        _checkpoint(1, "post", "state-1"),
        _checkpoint(2, "post", "state-2"),
    ]
    terminal = {
        "kind": "GAME_OVER" if terminal_complete else "DECISION_HORIZON",
        "complete": terminal_complete,
        "game_over": terminal_complete,
        "state_digest": "terminal-state",
        "rng_calls": 500,
        "event_offset": 12,
        "outcomes": [
            {"seat": 0, "life": 40, "won": True, "lost": False, "left": False},
            {"seat": 1, "life": 0, "won": False, "lost": True, "left": False},
        ],
    }
    return rt.TwinRun(
        role=role,
        candidate="forge",
        fixture_identity={
            "fixture_id": "AF09-GENERIC-forge-4P-v1",
            "candidate": "forge",
            "player_count": 4,
            "seed": 424242,
            "lane": "protocol2-jsonl",
            "deck_hashes": ["a" * 64],
        },
        candidate_build={
            "candidate": "forge",
            "engine_commit": "b" * 40,
            "build_identity": {"module": "forge-protocol2-bridge"},
        },
        lab_source={"commit": "c" * 40, "tree": "d" * 40, "clean": True},
        process=_process(role, pid),
        rules_rng={
            "requested_seed": 424242,
            "acknowledged_seed": 424242,
            "classification": "ACKNOWLEDGED_ENGINE_SEED",
            "controlled": True,
            "rng_credit": True,
            "rng_call_coordinates": [
                {"sequence": 1, "before": 101, "after": 102},
                {"sequence": 2, "before": 102, "after": 103},
            ],
        },
        decisions=decisions,
        semantic_events=events,
        checkpoint_state_hashes=checkpoints,
        terminal=terminal,
        process_local_identifiers={"game_id": "per-process-game"},
    )


@pytest.fixture()
def twin_pair() -> tuple[rt.TwinRun, rt.TwinRun]:
    return make_run("RECORD", 4001), make_run("REPLAY", 4002)


# --------------------------------------------------------------------------- #
# Process identity
# --------------------------------------------------------------------------- #


def test_read_process_identity_observes_the_live_process() -> None:
    identity = rt.read_process_identity(os.getpid(), role="TEST", command=("python3", "-c", "x"))
    assert identity.observed
    assert identity.pid == os.getpid()
    assert identity.start_ticks is not None and identity.start_ticks > 0
    assert identity.boot_id
    assert identity.command_sha256 == rt.sha256_json(["python3", "-c", "x"])


def test_read_pidfile_identity_round_trip(tmp_path: Path) -> None:
    pidfile = tmp_path / "engine.pid"
    pidfile.write_text("4321 777777 boot-abc\n", encoding="utf-8")
    identity = rt.read_pidfile_identity(pidfile, role="RECORD", command=("java", "full-game"))
    assert identity.observed
    assert (identity.pid, identity.start_ticks, identity.boot_id) == (4321, 777777, "boot-abc")


def test_read_pidfile_identity_missing_is_not_observed(tmp_path: Path) -> None:
    identity = rt.read_pidfile_identity(tmp_path / "absent.pid", role="RECORD", command=("java",))
    assert not identity.observed
    assert identity.pid is None


def test_process_identities_must_be_distinct() -> None:
    a = _process("RECORD", 11)
    b = _process("REPLAY", 12)
    assert rt.process_identities_distinct([a, b])[0] is True
    assert rt.process_identities_distinct([a, a])[0] is False
    unobserved = rt.ProcessIdentity(
        role="X",
        pid=None,
        start_ticks=None,
        boot_id=None,
        command_sha256="x",
        command=(),
        observation="",
    )
    assert rt.process_identities_distinct([a, unobserved])[0] is False


def test_parse_stat_start_ticks_robust_to_comm_spaces() -> None:
    text = "123 (java thread) R 1 123 123 0 -1 4194560 0 0 0 0 0 0 0 0 20 0 1 0 987654 0 0"
    assert rt._parse_stat_start_ticks(text) == 987654


# --------------------------------------------------------------------------- #
# Normalization contract
# --------------------------------------------------------------------------- #


def test_process_local_normalization_is_explicit_and_reported(twin_pair: tuple[Any, ...]) -> None:
    record, _ = twin_pair
    document = record.to_document()
    document["process_local_identifiers"] = {"game_id": "abc"}
    rule = rt.NormalizationRule(
        path="process_local_identifiers", justification="process_local_identifier"
    )
    normalized, report = rt.apply_normalization(document, [rule])
    assert "process_local_identifiers" not in normalized
    assert any(item["applied"] for item in report)


@pytest.mark.parametrize(
    "path",
    [
        "decisions.*.chosen_fingerprint",
        "semantic_events.*.digest",
        "checkpoint_state_hashes.*.public_state_digest",
        "terminal.outcomes",
        "rules_rng.rng_call_coordinates",
    ],
)
def test_normalizing_a_rules_significant_field_fails(path: str) -> None:
    with pytest.raises(rt.NormalizationContractError):
        rt.NormalizationRule(path=path, justification="process_local_identifier")


def test_unknown_justification_fails() -> None:
    with pytest.raises(rt.NormalizationContractError):
        rt.NormalizationRule(path="process_local_identifiers", justification="because")


# --------------------------------------------------------------------------- #
# Comparator and mandatory adversarial controls
# --------------------------------------------------------------------------- #


def test_identical_semantics_verify(twin_pair: tuple[rt.TwinRun, rt.TwinRun]) -> None:
    record, replay = twin_pair
    comparison = rt.compare_twin_runs(record, replay)
    assert comparison.verified is True
    assert comparison.verdict == "PASS"
    assert not comparison.divergences


def test_changed_decision_is_detected(twin_pair: tuple[Any, ...]) -> None:
    record, replay = twin_pair
    mutated = replay.to_document()
    mutated["decisions"][0]["chosen_fingerprint"] = "tampered"
    comparison = rt.compare_twin_runs(record, mutated)
    assert not comparison.verified
    assert rt.DIVERGENCE_DECISION in {item["code"] for item in comparison.divergences}


def test_changed_seed_is_detected(twin_pair: tuple[Any, ...]) -> None:
    record, replay = twin_pair
    mutated = replay.to_document()
    mutated["rules_rng"]["acknowledged_seed"] = 7
    comparison = rt.compare_twin_runs(record, mutated)
    assert not comparison.verified
    assert rt.DIVERGENCE_RNG in {item["code"] for item in comparison.divergences}


def test_changed_rng_coordinate_is_detected(twin_pair: tuple[Any, ...]) -> None:
    record, replay = twin_pair
    mutated = replay.to_document()
    mutated["rules_rng"]["rng_call_coordinates"][0]["after"] += 3
    comparison = rt.compare_twin_runs(record, mutated)
    assert not comparison.verified
    assert rt.DIVERGENCE_RNG in {item["code"] for item in comparison.divergences}


def test_missing_event_is_detected_and_classified(twin_pair: tuple[Any, ...]) -> None:
    record, replay = twin_pair
    mutated = replay.to_document()
    mutated["semantic_events"].pop(0)
    comparison = rt.compare_twin_runs(record, mutated)
    codes = {item["code"] for item in comparison.divergences}
    assert not comparison.verified
    assert rt.DIVERGENCE_EVENT_MISSING in codes


def test_reordered_event_is_detected_and_classified(twin_pair: tuple[Any, ...]) -> None:
    record, replay = twin_pair
    mutated = replay.to_document()
    mutated["semantic_events"][0], mutated["semantic_events"][1] = (
        mutated["semantic_events"][1],
        mutated["semantic_events"][0],
    )
    comparison = rt.compare_twin_runs(record, mutated)
    codes = {item["code"] for item in comparison.divergences}
    assert not comparison.verified
    assert rt.DIVERGENCE_EVENT_REORDERED in codes


def test_changed_checkpoint_is_detected(twin_pair: tuple[Any, ...]) -> None:
    record, replay = twin_pair
    mutated = replay.to_document()
    mutated["checkpoint_state_hashes"][1]["public_state_digest"] = "f" * 64
    comparison = rt.compare_twin_runs(record, mutated)
    assert not comparison.verified
    assert rt.DIVERGENCE_STATE in {item["code"] for item in comparison.divergences}


def test_changed_terminal_is_detected(twin_pair: tuple[Any, ...]) -> None:
    record, replay = twin_pair
    mutated = replay.to_document()
    mutated["terminal_outcome"]["outcomes"][0]["won"] = False
    comparison = rt.compare_twin_runs(record, mutated)
    assert not comparison.verified
    assert rt.DIVERGENCE_TERMINAL in {item["code"] for item in comparison.divergences}


def test_same_seed_with_different_decisions_is_not_pass(twin_pair: tuple[Any, ...]) -> None:
    record, replay = twin_pair
    mutated = replay.to_document()
    mutated["decisions"][0]["chosen_fingerprint"] = "different-with-same-seed"
    comparison = rt.compare_twin_runs(record, mutated)
    assert comparison.verdict != "PASS"
    assert comparison.verified is False


def test_same_process_identity_is_not_a_twin(twin_pair: tuple[Any, ...]) -> None:
    record, replay = twin_pair
    mutated = replay.to_document()
    mutated["process_identity"] = record.to_document()["process_identity"]
    comparison = rt.compare_twin_runs(record, mutated)
    assert not comparison.verified
    assert rt.DIVERGENCE_PROCESS_NOT_DISTINCT in {item["code"] for item in comparison.divergences}


def test_missing_process_identity_is_not_pass(twin_pair: tuple[Any, ...]) -> None:
    record, replay = twin_pair
    mutated = replay.to_document()
    mutated["process_identity"] = {
        "role": "REPLAY",
        "pid": None,
        "start_ticks": None,
        "boot_id": None,
        "command_sha256": "x",
        "command": [],
        "observation": "unobserved",
        "observed": False,
    }
    comparison = rt.compare_twin_runs(record, mutated)
    assert not comparison.verified
    codes = {item["code"] for item in comparison.divergences}
    assert rt.DIVERGENCE_PROCESS_MISSING in codes


def test_horizon_terminal_is_unknown_not_pass() -> None:
    record = make_run("RECORD", 5001, terminal_complete=False)
    replay = make_run("REPLAY", 5002, terminal_complete=False)
    comparison = rt.compare_twin_runs(record, replay)
    assert comparison.verified is False
    assert comparison.verdict == "UNKNOWN"
    assert rt.DIVERGENCE_TERMINAL_INCOMPLETE in {item["code"] for item in comparison.divergences}


def test_missing_required_section_is_unknown(twin_pair: tuple[Any, ...]) -> None:
    record, replay = twin_pair
    mutated = replay.to_document()
    mutated["semantic_events"] = []
    comparison = rt.compare_twin_runs(record, mutated)
    assert comparison.verified is False
    assert comparison.verdict == "UNKNOWN"
    codes = {item["code"] for item in comparison.divergences}
    assert rt.DIVERGENCE_SECTION_MISSING in codes
    assert rt.DIVERGENCE_EVENT_MISSING in codes


def test_all_mandatory_adversarial_controls_are_detected() -> None:
    record = make_run("RECORD", 6001)
    replay = make_run("REPLAY", 6002)
    results = rt.run_adversarial_controls(record, replay)
    by_name = {item["control"]: item for item in results}
    for name in (
        "changed_decision",
        "changed_seed_or_rng_binding",
        "changed_rng_coordinates",
        "missing_event",
        "reordered_event",
        "changed_checkpoint_hash",
        "changed_terminal",
        "same_seed_different_decisions",
        "same_process_identity_is_not_a_twin",
        "normalization_of_rules_significant_field_fails",
        "baseline_twin_verified",
    ):
        assert name in by_name, name
        assert by_name[name]["detected"] is True, by_name[name]
        assert by_name[name]["applicable"] is True, by_name[name]


# --------------------------------------------------------------------------- #
# Gate-facing document
# --------------------------------------------------------------------------- #


def test_clean_process_twin_document_satisfies_the_af09_gate() -> None:
    from commander_lab.qualification.current_boundary import gate_derivations as gates

    record = make_run("RECORD", 7001)
    replay = make_run("REPLAY", 7002)
    comparison = rt.compare_twin_runs(record, replay)
    controls = rt.run_adversarial_controls(record, replay)
    twin = rt.clean_process_twin_document(
        record=record, replay=replay, comparison=comparison, adversarial_controls=controls
    )
    assert twin["verified"] is True
    for section in rt.REQUIRED_TWIN_SECTIONS:
        assert twin[section], section
    rows = {
        fixture: {"exit_state": "PASS"}
        for fixture in (
            "REPLAY_CLEAN_PROCESS",
            "REPLAY_DECISION_TAPE",
            "REPLAY_EVENT_TAPE",
            "REPLAY_STATE_HASHES",
            "RNG_RULES_TAPE",
        )
    }
    document = {
        "rules_rng_binding": {
            "classification": "ACKNOWLEDGED_ENGINE_SEED",
            "requested_seed": 424242,
            "acknowledged_seed": 424242,
        },
        "semantic_replay": {},
        "clean_process_twin": twin,
    }
    gate = gates.af09_rng_replay("forge", rows, document)
    assert gate["verdict"] == "PASS", gate["nonblocking_limitations"]


def test_unverified_twin_document_cannot_pass_the_gate(twin_pair: tuple[Any, ...]) -> None:
    from commander_lab.qualification.current_boundary import gate_derivations as gates

    record, replay = twin_pair
    mutated = replay.to_document()
    mutated["terminal_outcome"]["complete"] = False
    mutated["terminal_outcome"]["kind"] = "DECISION_HORIZON"
    replay_run = rt.TwinRun(**{**replay.__dict__, "terminal": mutated["terminal_outcome"]})
    comparison = rt.compare_twin_runs(record, replay_run)
    twin = rt.clean_process_twin_document(record=record, replay=replay_run, comparison=comparison)
    assert twin["verified"] is False
    rows = {"REPLAY_CLEAN_PROCESS": {"exit_state": "PASS"}}
    document = {
        "rules_rng_binding": {
            "classification": "ACKNOWLEDGED_ENGINE_SEED",
            "requested_seed": 424242,
            "acknowledged_seed": 424242,
        },
        "semantic_replay": {},
        "clean_process_twin": twin,
    }
    assert gates.af09_rng_replay("forge", rows, document)["verdict"] == "UNKNOWN"


# --------------------------------------------------------------------------- #
# Generic-lane record/replay driver against a scripted fake bridge
# --------------------------------------------------------------------------- #


def _forge_action(action_id: str, action_type: str, fingerprint: str, **extra: Any) -> dict:
    return {
        "action_id": action_id,
        "action_type": action_type,
        "semantic_fingerprint": fingerprint,
        "metadata": {},
        **extra,
    }


class FakeForgeBridge:
    """A scripted Protocol-2 surface for the twin driver, not a Rules engine.

    It publishes exactly the semantic fields the Forge bridge publishes
    (semantic option fingerprints, public-state/legal-set digests, RNG call
    counts, terminal outcomes) so the twin driver's contract can be exercised
    without an engine. It computes no legality.
    """

    def __init__(self, *, deterministic: bool = True, omit_fingerprints: bool = False) -> None:
        self.deterministic = deterministic
        self.omit_fingerprints = omit_fingerprints
        self.nonce = rt.sha256_json(os.urandom(8))[:12]
        self.handles = 0
        self.step = 0
        self.game_over = False
        self.frames = self._script()
        self.popen = type("Popen", (), {"pid": 9000 + id(self) % 1000})()
        self.server = type("Server", (), {"pid": 9000 + id(self) % 1000})()
        self.popen.pid = self.server.pid

    def _script(self) -> list[dict[str, Any]]:
        frames: list[dict[str, Any]] = []
        counter = 0

        def add(kind: str, actor: str, revision: int, actions: list[dict[str, Any]]) -> None:
            nonlocal counter
            counter += 1
            public = rt.sha256_json([kind, actor, revision])
            legal = rt.sha256_json([a["semantic_fingerprint"] for a in actions])
            if not self.deterministic:
                public = rt.sha256_json([public, self.nonce])
            frames.append(
                {
                    "decision": {
                        "kind": kind,
                        "actor": actor,
                        "revision": revision,
                        "decision_id": f"decision-{revision}",
                        "status": "SUPPORTED",
                        "decision_class": f"forge:{kind.lower()}/1",
                        "legal_set_digest": legal,
                        "legal_set_size": len(actions),
                        "rng_binding": {
                            "rules_calls": 100 + revision,
                            "rules_root_seed": 424242,
                            "explicit_seed": True,
                            "root_seed": 424242,
                            "require_explicit_seed": True,
                        },
                        "event_offset": revision,
                        "public_state_digest": public,
                        "principal_observation_digest": rt.sha256_json([public, actor]),
                    },
                    "actions": actions,
                }
            )

        add(
            "STARTING_PLAYER",
            "p1",
            1,
            [
                _forge_action("opt-a", "structural_decision", "fp-start-p1", source_object_id="p1"),
                _forge_action("opt-b", "structural_decision", "fp-start-p2", source_object_id="p2"),
            ],
        )
        for seat, revision in zip(("p1", "p2", "p3", "p4"), (2, 3, 4, 5), strict=True):
            add(
                "MULLIGAN",
                seat,
                revision,
                [
                    _forge_action("opt-keep", "keep", f"fp-keep-{seat}"),
                    _forge_action("opt-mull", "mulligan", f"fp-mull-{seat}"),
                ],
            )
        add(
            "PRIORITY",
            "p1",
            6,
            [
                _forge_action("opt-pass", "pass_priority", "fp-pass-6"),
                _forge_action("opt-concede", "concede", "fp-concede-6"),
                _forge_action("opt-cast", "cast_spell", "fp-cast-6"),
            ],
        )
        add(
            "PRIORITY",
            "p2",
            7,
            [
                _forge_action("opt-pass", "pass_priority", "fp-pass-7"),
                _forge_action("opt-concede", "concede", "fp-concede-7"),
            ],
        )
        return frames

    # -- protocol surface -------------------------------------------------

    def request(
        self,
        message: str,
        params: dict[str, Any] | None = None,
        *,
        game_id: str | None = None,
        timeout_s: float = 0.0,
        **_: Any,
    ) -> dict[str, Any]:
        if message == "start_engine":
            return {"success": True, "payload": {}}
        if message == "get_provider_version":
            return {
                "success": True,
                "payload": {
                    "engine": "forge",
                    "engine_version": "test-1.0",
                    "engine_commit": "e" * 40,
                    "protocol_version": "2.0.0",
                },
            }
        if message == "get_capabilities":
            return {"success": True, "payload": {"capabilities": {"seed_supported": True}}}
        if message == "import_deck":
            self.handles += 1
            return {
                "success": True,
                "payload": {"deck_handle": {"handle_id": f"handle-{self.handles}"}},
            }
        if message == "create_commander_game":
            created = (params or {}).get("request") or {}
            return {
                "success": True,
                "payload": {
                    "seed": created.get("seed"),
                    "player_count": 4,
                },
            }
        if message == "start_game":
            return {"success": True, "payload": {"status": "started"}}
        if message == "get_legal_actions":
            actor = (params or {}).get("actor_id")
            if self.step >= len(self.frames):
                return {
                    "success": True,
                    "payload": {"actions": [], "decision": {"status": "no_pending_decision"}},
                }
            frame = self.frames[self.step]
            if actor != frame["decision"]["actor"]:
                return {"success": False, "status": "WRONG_ACTOR", "errors": []}
            return {"success": True, "payload": json.loads(json.dumps(frame))}
        if message in {"resolve_mulligan", "pass_priority", "submit_action"}:
            return self._advance()
        if message == "get_game_state":
            return {
                "success": True,
                "payload": {"state": self._state(), "game_over": self.game_over},
            }
        if message in {"shutdown_game", "shutdown_engine"}:
            return {"success": True, "payload": {}}
        return {"success": False, "status": "UNSUPPORTED", "errors": []}

    def _advance(self) -> dict[str, Any]:
        self.step += 1
        if self.step >= len(self.frames):
            self.game_over = True
        return {
            "success": True,
            "payload": {
                "decision": {"executed": True},
                "state": self._state(),
                "game_over": self.game_over,
            },
        }

    def _state(self) -> dict[str, Any]:
        index = min(self.step, len(self.frames) - 1)
        public = rt.sha256_json(["state", index])
        if not self.deterministic:
            public = rt.sha256_json([public, self.nonce])
        outcomes = [
            {
                "seat": 0,
                "player_id": "p1",
                "life": 40,
                "lost": False,
                "won": self.game_over,
                "left": False,
            },
            {
                "seat": 1,
                "player_id": "p2",
                "life": 0,
                "lost": self.game_over,
                "won": False,
                "left": False,
            },
        ]
        return {
            "public_state_digest": public,
            "principal_observation_digest": rt.sha256_json([public, "p1"]),
            "rng_binding": {
                "rules_calls": 200 + index,
                "rules_root_seed": 424242,
                "explicit_seed": True,
            },
            "event_offset": index,
            "phase": "beginning",
            "step": "UPKEEP",
            "active_player_id": "p1",
            "priority_player_id": "p1",
            "status": "finished" if self.game_over else "in_progress",
            "terminal_outcomes": outcomes,
            "game_over": self.game_over,
        }


def _fake_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    counters = {"pid": 8000}

    def fake(
        pid: int, *, role: str, command: Any, proc_root: Path | None = None
    ) -> rt.ProcessIdentity:
        counters["pid"] += 1
        return rt.ProcessIdentity(
            role=role,
            pid=counters["pid"],
            start_ticks=counters["pid"] * 10,
            boot_id="test-boot",
            command_sha256=rt.sha256_json([str(part) for part in command]),
            command=tuple(str(part) for part in command),
            observation="test",
        )

    monkeypatch.setattr(rt, "read_process_identity", fake)


LAB_SOURCE = {"commit": "c" * 40, "tree": "d" * 40, "clean": True}


def _gather(
    bridge: FakeForgeBridge,
    *,
    role: str,
    tape: list[dict[str, Any]] | None,
    max_decisions: int = 20,
    concede_after_decisions: int | None = None,
    scripted_starting_seat: str | None = "p1",
) -> rt.TwinRun:
    return rt.gather_generic_lane_process(
        bridge,
        role=role,
        candidate="forge",
        player_count=4,
        seed=424242,
        fixture_id="AF09-GENERIC-forge-4P-v1",
        game_id=f"test-{role.lower()}",
        plan_command=("java", "-cp", "bridge", "forge.bridge.BridgeMain"),
        build_identity={"module": "forge-protocol2-bridge"},
        expected_engine_commit="e" * 40,
        lab_source=LAB_SOURCE,
        decision_tape=tape,
        max_decisions=max_decisions,
        scripted_starting_seat=scripted_starting_seat,
        starting_seat_source=(
            "TEST_DECLARED_STARTING_SEAT" if scripted_starting_seat is not None else None
        ),
        concede_after_decisions=concede_after_decisions,
    )


def test_generic_lane_record_and_replay_twin_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_identity(monkeypatch)
    record = _gather(FakeForgeBridge(), role="RECORD", tape=None)
    assert record.failure is None, record.failure
    replay = _gather(FakeForgeBridge(), role="REPLAY", tape=record.decisions)
    assert replay.failure is None, replay.failure
    comparison = rt.compare_twin_runs(record, replay)
    assert comparison.verified is True, comparison.to_document()
    assert len(record.decisions) == 7
    assert record.terminal["complete"] is True
    assert replay.decisions == record.decisions


def test_generic_lane_refuses_a_starting_player_frame_without_a_declaration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#572: no twin run may answer the engine's starting-player frame by default."""
    _fake_identity(monkeypatch)
    run = _gather(FakeForgeBridge(), role="RECORD", tape=None, scripted_starting_seat=None)
    assert run.failure is not None
    assert "STARTING_PLAYER" in run.failure
    assert "declares no starting seat" in run.failure


def test_generic_lane_refuses_a_declaration_the_engine_does_not_offer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A declared seat that is not one engine-offered option is an ambiguity, not a pass."""
    _fake_identity(monkeypatch)
    run = _gather(FakeForgeBridge(), role="RECORD", tape=None, scripted_starting_seat="p4")
    assert run.failure is not None
    assert "exactly one required" in run.failure


def test_generic_lane_records_the_declared_starting_seat_and_channel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_identity(monkeypatch)
    run = _gather(FakeForgeBridge(), role="RECORD", tape=None, scripted_starting_seat="p1")
    assert run.failure is None, run.failure
    identity = run.fixture_identity
    assert identity["starting_seat_policy"] == "declared:p1:TEST_DECLARED_STARTING_SEAT"
    assert identity["starting_player_declaration"] == {
        "seat": "p1",
        "source": "TEST_DECLARED_STARTING_SEAT",
    }
    assert identity["starting_player_channel"] == ("ENGINE_FRAME_FROM_RECORD_DECLARATION")


def test_generic_lane_replay_fails_closed_on_missing_fingerprints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_identity(monkeypatch)
    bridge = FakeForgeBridge()
    for frame in bridge.frames:
        for action in frame["actions"]:
            action.pop("semantic_fingerprint", None)
    with pytest.raises(rt.TwinChannelUnavailable) as excinfo:
        _gather(bridge, role="RECORD", tape=None)
    assert excinfo.value.channel == "semantic_option_identity"


def test_generic_lane_replay_rejects_a_foreign_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_identity(monkeypatch)
    record = _gather(FakeForgeBridge(), role="RECORD", tape=None)
    foreign = json.loads(json.dumps(record.decisions))
    foreign[0]["chosen_fingerprint"] = "not-offered-anywhere"
    replay = _gather(FakeForgeBridge(), role="REPLAY", tape=foreign)
    assert replay.failure is not None
    assert "matched 0 offered options" in replay.failure
    comparison = rt.compare_twin_runs(record, replay)
    assert comparison.verified is False


def test_generic_lane_horizon_terminal_is_not_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_identity(monkeypatch)
    record = _gather(FakeForgeBridge(), role="RECORD", tape=None, max_decisions=1)
    replay = _gather(FakeForgeBridge(), role="REPLAY", tape=record.decisions, max_decisions=1)
    assert record.terminal["kind"] == "DECISION_HORIZON"
    comparison = rt.compare_twin_runs(record, replay)
    assert comparison.verified is False
    assert comparison.verdict == "UNKNOWN"


def test_generic_lane_nondeterminism_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_identity(monkeypatch)
    record = _gather(FakeForgeBridge(deterministic=True), role="RECORD", tape=None)
    replay = _gather(FakeForgeBridge(deterministic=False), role="REPLAY", tape=record.decisions)
    assert replay.failure is not None
    assert "public state digest differs" in replay.failure
    comparison = rt.compare_twin_runs(record, replay)
    assert comparison.verified is False


def test_generic_lane_concede_horizon_uses_the_engine_offered_concession(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_identity(monkeypatch)
    record = _gather(FakeForgeBridge(), role="RECORD", tape=None, concede_after_decisions=1)
    assert record.failure is None, record.failure
    concession_entries = [
        entry for entry in record.decisions if entry["policy"] == "concede_at_defined_horizon"
    ]
    assert [entry["chosen_fingerprint"] for entry in concession_entries] == [
        "fp-concede-6",
        "fp-concede-7",
    ]
    replay = _gather(
        FakeForgeBridge(),
        role="REPLAY",
        tape=record.decisions,
        concede_after_decisions=1,
    )
    assert replay.failure is None, replay.failure
    assert rt.compare_twin_runs(record, replay).verified is True


def test_record_policy_fails_closed_on_all_duplicate_options() -> None:
    actions = [
        _forge_action("opt-0", "choose_object", "same-fingerprint"),
        _forge_action("opt-1", "choose_object", "same-fingerprint"),
        _forge_action("opt-2", "choose_object", "same-fingerprint"),
    ]
    frame = {"decision": {"actor": "p1", "revision": 9, "kind": "GENERIC_SELECTION"}}
    with pytest.raises(rt.DecisionUnsatisfied) as excinfo:
        rt._record_action_for_kind(
            "forge", "GENERIC_SELECTION", actions, frame, scripted_starting_seat="p1"
        )
    assert "indistinguishable duplicate options" in str(excinfo.value)


def test_record_policy_chooses_a_unique_fingerprint() -> None:
    actions = [
        _forge_action("opt-0", "choose_object", "dup"),
        _forge_action("opt-1", "choose_object", "dup"),
        _forge_action("opt-2", "choose_object", "unique"),
    ]
    frame = {"decision": {"actor": "p1", "revision": 9, "kind": "GENERIC_SELECTION"}}
    chosen, policy = rt._record_action_for_kind(
        "forge", "GENERIC_SELECTION", actions, frame, scripted_starting_seat="p1"
    )
    assert chosen["semantic_fingerprint"] == "unique"
    assert policy == "deterministic_unique_lexicographic_fingerprint"


EVIDENCE_DIR = Path(__file__).resolve().parents[2] / "docs/af09_replay_twins_20261001/evidence"
AF09_ROWS = {
    fixture: {"exit_state": "PASS"}
    for fixture in (
        "REPLAY_CLEAN_PROCESS",
        "REPLAY_DECISION_TAPE",
        "REPLAY_EVENT_TAPE",
        "REPLAY_STATE_HASHES",
        "RNG_RULES_TAPE",
    )
}


@pytest.mark.parametrize("name", ["AF09_REPLAY_TWIN_XMAGE.json", "AF09_REPLAY_TWIN_FORGE.json"])
def test_committed_evidence_verifies_and_passes_the_af09_gate(name: str) -> None:
    from commander_lab.qualification.current_boundary import gate_derivations as gates

    document = json.loads((EVIDENCE_DIR / name).read_text(encoding="utf-8"))
    twin = document["clean_process_twin"]
    assert document["verdict"] == "PASS", name
    assert twin["verified"] is True, name
    assert twin["lab_source"]["clean"] is True, name
    assert all(control["detected"] for control in document["adversarial_controls"]), name
    gate_document = {
        "rules_rng_binding": {
            "classification": "ACKNOWLEDGED_ENGINE_SEED",
            "requested_seed": twin["rules_rng"]["requested_seed"],
            "acknowledged_seed": twin["rules_rng"]["acknowledged_seed"],
        },
        "semantic_replay": {},
        "clean_process_twin": twin,
    }
    gate = gates.af09_rng_replay(document["candidate"], AF09_ROWS, gate_document)
    assert gate["verdict"] == "PASS", gate["nonblocking_limitations"]


def test_committed_xmage_2p_evidence_is_honest_unknown() -> None:
    document = json.loads(
        (EVIDENCE_DIR / "AF09_REPLAY_TWIN_XMAGE_2P.json").read_text(encoding="utf-8")
    )
    assert document["verdict"] == "UNKNOWN"
    assert document["clean_process_twin"]["verified"] is False
    divergence = document["consumer_divergence"]
    assert divergence["divergence_class"] == "CHOSEN_OPTION_AMBIGUOUS"
    assert "step 110" in divergence["detail"]
    # The collision is recorded from the engine and never normalized away.
    assert document["clean_process_twin"]["comparison"]["verified"] is True


def test_xmage_tape_reduction_preserves_required_sections() -> None:
    raw = _synthetic_tape()
    run = rt.xmage_tape_run_from_document(
        raw,
        role="RECORD_FIRST",
        process=_process("RECORD_FIRST", 111),
        lab_source=LAB_SOURCE,
        candidate_build={"module": "engine-bridge"},
        fixture_identity={"fixture_id": "technical-isamaru-full-game-4p-v1"},
    )
    assert run.decisions
    assert run.semantic_events
    assert run.checkpoint_state_hashes
    assert run.rules_rng["acknowledged_seed"] == 424242
    assert run.rules_rng["classification"] == "ACKNOWLEDGED_ENGINE_SEED"
    assert run.terminal["complete"] is True
    comparison = rt.compare_twin_runs(
        run,
        rt.xmage_tape_run_from_document(
            _synthetic_tape(),
            role="RECORD_SECOND",
            process=_process("RECORD_SECOND", 112),
            lab_source=LAB_SOURCE,
            candidate_build={"module": "engine-bridge"},
            fixture_identity={"fixture_id": "technical-isamaru-full-game-4p-v1"},
        ),
    )
    assert comparison.verified is True, comparison.to_document()


def _synthetic_tape() -> dict[str, Any]:
    steps = []
    for sequence in (1, 2):
        steps.append(
            {
                "sequence": sequence,
                "step_kind": "decision",
                "decision_class": "forge:priority/1",
                "actor_principal": 1,
                "decision_revision": sequence,
                "selected_fingerprints": [f"fp-{sequence}"],
                "selected_labels": [],
                "numeric_choice": None,
                "legal_set_size": 2,
                "rng_calls_before": 100 + sequence,
                "rng_calls_after": 101 + sequence,
                "event_offset_before": sequence,
                "event_offset_after": sequence + 1,
                "event_digest": rt.sha256_json(["event", sequence]),
                "post_checkpoint_digest": rt.sha256_json(["post", sequence]),
            }
        )
    return {
        "schema_version": "semantic-replay-tape/1.0.0",
        "tape_id": "a" * 64,
        "game_manifest": {
            "player_count": 4,
            "rules_seed": 424242,
            "commander_identities": ["Isamaru, Hound of Konda"],
        },
        "rng_contract": {
            "root_rules_seed": 424242,
            "rules_seed_explicit": True,
            "require_explicit_seed": True,
        },
        "initial_checkpoint": {
            "rules_seed": 424242,
            "rules_random_calls": 100,
            "turn_number": 1,
            "event_offset": 0,
            "semantic_state_digest": rt.sha256_json(["initial"]),
            "public_state_digest": rt.sha256_json(["initial-public"]),
        },
        "steps": steps,
        "terminal_checkpoint": {
            "terminal": True,
            "turn_number": 2,
            "rules_random_calls": 300,
            "outcomes": [
                {"seat": 1, "life": 40, "won": True, "lost": False, "left": False},
                {"seat": 2, "life": 0, "won": False, "lost": True, "left": False},
            ],
            "semantic_state_digest": rt.sha256_json(["terminal"]),
            "public_state_digest": rt.sha256_json(["terminal-public"]),
        },
        "seal": {"terminal_digest": rt.sha256_json(["terminal-seal"])},
    }
