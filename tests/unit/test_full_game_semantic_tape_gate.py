"""C1: the full-game replay gate is decided by the semantic replay tape system.

`XmageFullGameRunner.run_replay_gate` used to compare two reduced transcript
hashes from the conformance runner. `commander_lab.semantic_replay.gate` now
records two tapes in fresh processes, compares them step by step
(`compare_tapes`) and consumes the first tape in a third fresh process
(`replay_tape`). The twin transcript hash stays a diagnostic only.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

import commander_lab.semantic_replay.comparator as comparator_mod
import commander_lab.semantic_replay.consumer as consumer_mod
import commander_lab.semantic_replay.recorder as recorder_mod
from commander_lab.engine.rules.full_game import (
    FullGameConformanceError,
    FullGameReplayGate,
    FullGameSemanticTapeEvidence,
    XmageFullGameRunner,
)
from commander_lab.semantic_replay import gate as gate_mod
from commander_lab.semantic_replay.comparator import (
    ComparisonResult,
    DivergenceKind,
    FirstDivergence,
)
from commander_lab.semantic_replay.divergence import DivergenceClass, ReplayDivergence

_A = "a" * 64
_B = "b" * 64


def _tape(**overrides: Any) -> FullGameSemanticTapeEvidence:
    values: dict[str, Any] = {
        "tape_schema_version": "semantic-replay-tape/1.0.0",
        "first_tape_id": _A,
        "second_tape_id": _A,
        "recorded_steps": 127,
        "tape_comparison_match": True,
        "compared_steps": 127,
        "fresh_process_replay_pass": True,
        "replay_steps_verified": 127,
    }
    values.update(overrides)
    return FullGameSemanticTapeEvidence(**values)


def _run(semantic: str, raw: str = _A) -> Any:
    return SimpleNamespace(semantic_transcript_sha256=semantic, raw_result_sha256=raw)


def _scenario() -> Any:
    return SimpleNamespace(scenario_id="c1", seed=7)


def test_the_verdict_is_the_tape_not_the_twin_hash() -> None:
    diverged = _tape(
        fresh_process_replay_pass=False,
        replay_steps_verified=0,
        replay_divergence_class="EVENT_DIGEST_MISMATCH",
    )
    gate = XmageFullGameRunner.replay_gate(
        scenario=_scenario(), first=_run(_A), second=_run(_A), tape=diverged
    )
    assert gate.twin_transcript_hash_match is True
    assert gate.semantic_replay_match is False

    agreeing = XmageFullGameRunner.replay_gate(
        scenario=_scenario(), first=_run(_A), second=_run(_B), tape=_tape()
    )
    assert agreeing.twin_transcript_hash_match is False
    assert agreeing.semantic_replay_match is True


def test_the_gate_refuses_a_verdict_that_contradicts_the_tape() -> None:
    gate = XmageFullGameRunner.replay_gate(
        scenario=_scenario(), first=_run(_A), second=_run(_A), tape=_tape()
    )
    payload = gate.model_dump(mode="json")
    payload["semantic_replay_match"] = False
    with pytest.raises(ValidationError, match="semantic tape verdict"):
        FullGameReplayGate.model_validate(payload)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"tape_comparison_match": False}, "first divergence"),
        ({"first_divergence_kind": "EVENT_MISMATCH"}, "first divergence"),
        ({"fresh_process_replay_pass": False}, "divergence class"),
        ({"replay_steps_verified": 126}, "every recorded step"),
    ],
)
def test_tape_evidence_is_internally_consistent(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        _tape(**overrides)


class _FakeTape:
    schema_version = "semantic-replay-tape/1.0.0"

    def __init__(self, tape_id: str, steps: int) -> None:
        self.tape_id = tape_id
        self.steps = tuple(range(steps))


def _patch_tape_system(
    monkeypatch: pytest.MonkeyPatch,
    *,
    ids: tuple[str, str] = (_A, _A),
    comparison: ComparisonResult | None = None,
    replay_error: ReplayDivergence | None = None,
) -> list[tuple[str, Any]]:
    calls: list[tuple[str, Any]] = []
    recorded = iter(ids)

    def fake_record(**kwargs: Any) -> _FakeTape:
        tape_id = next(recorded)
        Path(kwargs["output_path"]).write_text(json.dumps({"tape_id": tape_id}), encoding="utf-8")
        calls.append(("record", tuple(kwargs["command"])))
        return _FakeTape(tape_id, 5)

    def fake_compare(expected: dict[str, Any], actual: dict[str, Any]) -> ComparisonResult:
        calls.append(("compare", (expected["tape_id"], actual["tape_id"])))
        return comparison or ComparisonResult(match=True, compared_steps=5)

    def fake_replay(path: Path, *, command: tuple[str, ...], cwd: Any = None) -> dict[str, Any]:
        calls.append(("replay", Path(path).name))
        if replay_error is not None:
            raise replay_error
        return {"pass": True, "steps_verified": 5}

    monkeypatch.setattr(recorder_mod, "record_tape", fake_record)
    monkeypatch.setattr(comparator_mod, "compare_tapes", fake_compare)
    monkeypatch.setattr(consumer_mod, "replay_tape", fake_replay)
    return calls


def _runner() -> XmageFullGameRunner:
    return XmageFullGameRunner(command=("java", "-jar", "bridge.jar", "full-game"))


def test_two_fresh_recordings_are_compared_and_the_first_is_consumed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls = _patch_tape_system(monkeypatch)
    evidence = gate_mod.run_semantic_tape_replay(
        _runner(), scenario=_scenario(), decks=(), pilots=(), tape_dir=tmp_path
    )
    assert [name for name, _ in calls] == ["record", "record", "compare", "replay"]
    assert calls[3] == ("replay", "first.tape.json")
    assert evidence.passed is True
    assert evidence.recorded_steps == evidence.replay_steps_verified == 5


def test_a_consumer_divergence_fails_the_gate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_tape_system(
        monkeypatch,
        replay_error=ReplayDivergence(DivergenceClass.EVENT_DIGEST_MISMATCH, "step 3"),
    )
    evidence = gate_mod.run_semantic_tape_replay(
        _runner(), scenario=_scenario(), decks=(), pilots=(), tape_dir=tmp_path
    )
    assert evidence.passed is False
    assert evidence.replay_divergence_class == "EVENT_DIGEST_MISMATCH"


def test_a_comparison_divergence_fails_the_gate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    divergence = FirstDivergence(
        kind=DivergenceKind.LEGAL_ACTION_SET_MISMATCH,
        record_index=2,
        decision_offset=2,
        actor_principal=1,
        expected_record={},
        actual_record={},
        context_window=[],
        expected_source_lock={},
        actual_source_lock={},
        expected_provider="xmage",
        actual_provider="xmage",
    )
    _patch_tape_system(
        monkeypatch,
        ids=(_A, _B),
        comparison=ComparisonResult(match=False, compared_steps=2, divergence=divergence),
    )
    evidence = gate_mod.run_semantic_tape_replay(
        _runner(), scenario=_scenario(), decks=(), pilots=(), tape_dir=tmp_path
    )
    assert evidence.passed is False
    assert evidence.first_divergence_kind == "LEGAL_ACTION_SET_MISMATCH"
    assert (evidence.first_tape_id, evidence.second_tape_id) == (_A, _B)


def test_the_tape_replay_requires_an_explicit_bridge_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD", raising=False)
    with pytest.raises(FullGameConformanceError, match="semantic tape replay"):
        gate_mod.run_semantic_tape_replay(
            XmageFullGameRunner(), scenario=_scenario(), decks=(), pilots=(), tape_dir=tmp_path
        )
