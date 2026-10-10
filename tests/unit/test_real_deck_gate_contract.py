"""Driver contract controls; synthetic runs never establish native card behaviour."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts import run_real_deck_gate as gate

from commander_lab.semantic_replay.recorder import _deck_ref
from tests.unit.test_full_game_semantic_tape_gate import _tape
from tests.unit.test_xmage_full_game import _result


def test_real_decks_satisfy_recorder_without_mutating_source() -> None:
    paths = (
        gate.ROOT / "data/decks/rogshai_current.json",
        gate.ROOT / "data/decks/opponents/kaervek/current/deck.json",
    )
    # The manifest loader is authority; compare every deck's ordered material too.
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    canonical = gate.load_gate_decks(gate.ROOT)
    _, decks, _ = gate.build_gate_setup(gate.ROOT, gate.BASE_SEED)
    for deck, family in zip(decks, gate.SEAT_DECKS, strict=True):
        assert _deck_ref(deck).deck_hash == deck.deck_hash
        assert deck.mainboard == canonical[family].mainboard
        assert deck.commander_names == canonical[family].commander_names
    assert before == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


@pytest.mark.parametrize("count", [0, -1])
def test_nonpositive_batches_fail_before_engine_or_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, count: int
) -> None:
    def forbidden():
        pytest.fail("engine constructed for an empty batch")

    monkeypatch.setattr(gate, "XmageFullGameRunner", forbidden)
    args = argparse.Namespace(
        root=str(gate.ROOT), count=count, base_seed=1, out_dir=str(tmp_path / "output")
    )
    assert gate.cmd_batch(args) != 0
    assert not (tmp_path / "output").exists()
    with pytest.raises(SystemExit) as exc:
        gate.main(["batch", "--count", str(count), "--out-dir", str(tmp_path / "output")])
    assert exc.value.code == 2


@pytest.mark.parametrize("terminal", [True, False])
@pytest.mark.parametrize("tape_pass", [True, False])
def test_replay_scope_and_verdict_are_bounded_and_nonvacuous(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, terminal: bool, tape_pass: bool
) -> None:
    class FakeRunner:
        def run(self, *, scenario, **kwargs):
            return _result(scenario).model_copy(update={"terminal": terminal})

    monkeypatch.setattr(gate, "XmageFullGameRunner", FakeRunner)
    tape = (
        _tape()
        if tape_pass
        else _tape(
            fresh_process_replay_pass=False,
            replay_steps_verified=0,
            replay_divergence_class="EVENT_DIGEST_MISMATCH",
        )
    )
    monkeypatch.setattr(gate, "run_semantic_tape_replay", lambda *a, **kw: tape)
    out = tmp_path / "replay.json"
    assert gate.cmd_replay(argparse.Namespace(root=gate.ROOT, seed=7, out=out)) == (
        0 if terminal and tape_pass else 1
    )
    import json

    payload = json.loads(out.read_text())
    assert payload["semantic_replay_scope"] == "bounded_decision_tape_with_native_concessions"
    assert payload["natural_terminal_runs_verified"] is terminal
    assert payload["full_natural_terminal_replay_validated"] is False
    assert payload["bit_exact_replay_validated"] is False


@pytest.mark.parametrize(
    "kind",
    [
        "failed",
        "nonterminal",
        "missing",
        "empty",
        "misbound",
        "rawseed",
        "rawterminal",
        "completed",
    ],
)
def test_batch_requires_every_requested_terminal_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    seen = []

    class FakeBatch:
        def __init__(self, *a):
            pass

        def run(self, cases, **kwargs):
            seen.extend(c.scenario.seed for c in cases)
            records = [
                SimpleNamespace(
                    case_id=c.case_id,
                    status="failed" if kind == "failed" else "completed",
                    elapsed_seconds=0,
                    failure_class=None,
                    failure_message=None,
                    result=None
                    if kind == "missing"
                    else _result(c.scenario).model_copy(
                        update={
                            "terminal": kind != "nonterminal",
                            "scenario": c.scenario.model_copy(update={"seed": 999})
                            if kind == "misbound"
                            else c.scenario,
                        }
                    ),
                )
                for c in cases
            ]
            if kind == "empty":
                records = []
            if kind in {"rawseed", "rawterminal"}:
                for record in records:
                    record.result.result_payload["seed" if kind == "rawseed" else "terminal"] = (
                        999 if kind == "rawseed" else False
                    )
            return SimpleNamespace(
                total_cases=len(records),
                completed_cases=len(records) if kind != "failed" else 0,
                failed_cases=len(records) if kind == "failed" else 0,
                resumed_cases=len(records),
                records=records,
            )

    monkeypatch.setattr(gate, "XmageFullGameBatchRunner", FakeBatch)
    assert gate.cmd_batch(
        argparse.Namespace(root=gate.ROOT, base_seed=17, count=2, out_dir=tmp_path)
    ) == (0 if kind == "completed" else 1)
    assert seen == [17, 18]
