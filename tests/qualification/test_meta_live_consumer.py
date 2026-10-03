"""B7 (#488): replay mutations are killed through the live replay consumer.

The live run (a fresh tape recorded on the pinned engine, replayed by
``consumer.replay_tape`` in a fresh process) happens in the meta-qualification
workflow. These tests pin the accounting with a scripted consumer: a kill needs
exactly the expected divergence class, a clean baseline comes first, and nothing
is promoted from the helper comparator.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from commander_lab import meta_qualification as mq
from commander_lab.semantic_replay.divergence import DivergenceClass, ReplayDivergence

ROOT = Path(__file__).resolve().parents[2]
TAPE = json.loads(
    (ROOT / "qualification/ws218-semantic-replay-tape-v1/tapes/ws218-tape-4p.json").read_text()
)


def _detect(baseline: dict, override: dict | None = None, shift: int = 0):
    """A scripted consumer that names the step like ``consumer.replay_tape`` does."""
    override = override or {}

    def replay(path: Path) -> dict:
        tape = json.loads(path.read_text())
        for mutation_id, divergence in mq.LIVE_CONSUMER_DETECTORS.items():
            mutated, index = mq._mutate_real_tape(baseline, mutation_id)
            if tape == mutated:
                step = index + 1 + shift
                detail = "terminal differs" if index >= len(tape["steps"]) else f"step {step}: x"
                raise ReplayDivergence(override.get(mutation_id, divergence), detail)
        assert tape == baseline
        return {"steps_verified": len(tape["steps"])}

    return replay


def test_every_real_tape_mutation_has_a_live_detector() -> None:
    assert {spec.mutation_id for spec in mq.REAL_TAPE_MUTATIONS} == set(mq.LIVE_CONSUMER_DETECTORS)


def test_all_mutations_killed_by_the_expected_class(tmp_path) -> None:
    report = mq.run_live_consumer_mutations(
        TAPE, replay=_detect(TAPE), workdir=tmp_path, source_tape="fresh.tape.json"
    )
    assert report["baseline"]["status"] == "PASS"
    assert report["complete"] is True
    assert report["killed"] == report["attempted"] == len(mq.REAL_TAPE_MUTATIONS)
    assert all(row["execution_tier"] == "LIVE_REPLAY_CONSUMER" for row in report["results"])


def test_a_wrong_divergence_class_is_not_a_kill(tmp_path) -> None:
    """Wrong-reason control: the right failure for the wrong reason survives."""
    replay = _detect(TAPE, {"MQ-EVENT-001": DivergenceClass.SOURCE_LOCK_MISMATCH})
    report = mq.run_live_consumer_mutations(
        TAPE, replay=replay, workdir=tmp_path, source_tape="fresh.tape.json"
    )
    row = next(r for r in report["results"] if r["mutation_id"] == "MQ-EVENT-001")
    assert row["status"] == "SURVIVED"
    assert row["observed_divergence"] == "SOURCE_LOCK_MISMATCH"
    assert report["complete"] is False


def test_the_right_class_at_the_wrong_step_is_not_a_kill(tmp_path) -> None:
    report = mq.run_live_consumer_mutations(
        TAPE, replay=_detect(TAPE, shift=3), workdir=tmp_path, source_tape="fresh.tape.json"
    )
    by_id = {row["mutation_id"]: row["status"] for row in report["results"]}
    assert by_id.pop("MQ-TERMINAL-001") == "KILLED"
    assert set(by_id.values()) == {"SURVIVED"}


def test_an_undetected_mutation_survives(tmp_path) -> None:
    def blind(path: Path) -> dict:
        return {"steps_verified": 1}

    report = mq.run_live_consumer_mutations(
        TAPE, replay=blind, workdir=tmp_path, source_tape="fresh.tape.json"
    )
    assert report["survived"] == len(mq.REAL_TAPE_MUTATIONS)
    assert report["complete"] is False


def test_a_failing_baseline_runs_no_mutation(tmp_path) -> None:
    """A stale tape (e.g. another engine pin) diverges for every input; nothing is credited."""

    def stale(path: Path) -> dict:
        raise ReplayDivergence(DivergenceClass.SOURCE_LOCK_MISMATCH, "engine commit differs")

    report = mq.run_live_consumer_mutations(
        TAPE, replay=stale, workdir=tmp_path, source_tape="stale.tape.json"
    )
    assert report["baseline"]["status"] == "FAIL"
    assert report["not_run"] == len(mq.REAL_TAPE_MUTATIONS)
    assert report["killed"] == 0
    assert report["complete"] is False


@pytest.mark.parametrize("mutation_id", sorted(mq.LIVE_CONSUMER_DETECTORS))
def test_each_mutation_changes_the_replayed_tape(mutation_id, tmp_path) -> None:
    mutated, _ = mq._mutate_real_tape(TAPE, mutation_id)
    assert mutated != TAPE


def test_the_meta_workflow_runs_the_live_consumer_and_requires_every_kill() -> None:
    import yaml

    workflow = yaml.safe_load((ROOT / ".github/workflows/meta-qualification.yml").read_text())
    steps = workflow["jobs"]["mutation-detection"]["steps"]
    names = [step.get("name") for step in steps]
    live = steps[names.index("Kill replay mutations through the live consumer")]
    assert live["run"].strip() == "python scripts/run_live_consumer_mutations.py"
    assert "full-game" in live["env"]["COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD"]
    verify = steps[
        names.index("Verify the live consumer killed every mutation on the pinned engine")
    ]
    for clause in (
        'report["killed"] == 7',
        'report["complete"] is True',
        'report["engine_commit"] == os.environ["XMAGE_COMMIT"]',
    ):
        assert clause in verify["run"], clause
    assert names.index("Package the engine bridge for the live replay consumer") < names.index(
        "Kill replay mutations through the live consumer"
    )
    triggers = workflow.get("on") or workflow.get(True)
    for event in ("pull_request", "push"):
        assert "scripts/run_live_consumer_mutations.py" in triggers[event]["paths"]
