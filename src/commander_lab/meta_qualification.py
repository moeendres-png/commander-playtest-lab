"""Meta-qualification mutation runner over existing semantic replay infrastructure.

This module does not implement Magic rules and does not reconstruct legality. It
injects controlled faults into an already recorded real semantic replay tape and
asks the existing provider-neutral comparator whether the fault is detected.
Runtime-bound mutations may only be promoted when an external runtime gate has
actually executed the named detector on the same source head.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from commander_lab.semantic_replay.comparator import compare_tapes
from commander_lab.semantic_replay.divergence import DivergenceClass, ReplayDivergence

CATALOG_VERSION = "commander-lab.rules-mutation-catalog/1.0.0"
RESULT_SCHEMA_VERSION = "commander-lab.meta-verification-result/1.0.0"


@dataclass(frozen=True)
class MutationSpec:
    mutation_id: str
    expected_detector: str
    execution_tier: str


REAL_TAPE_MUTATIONS: tuple[MutationSpec, ...] = (
    MutationSpec("MQ-LEGAL-001", "LEGAL_ACTION_SET_MISMATCH", "REAL_REPLAY_TAPE"),
    MutationSpec("MQ-DECISION-001", "DECISION_IDENTITY_MISMATCH", "REAL_REPLAY_TAPE"),
    MutationSpec("MQ-RNG-001", "RULES_RNG_MISMATCH", "REAL_REPLAY_TAPE"),
    MutationSpec("MQ-EVENT-001", "EVENT_MISMATCH", "REAL_REPLAY_TAPE"),
    MutationSpec("MQ-OBS-001", "PUBLIC_STATE_MISMATCH", "REAL_REPLAY_TAPE"),
    MutationSpec("MQ-STATE-001", "PUBLIC_STATE_MISMATCH", "REAL_REPLAY_TAPE"),
    MutationSpec("MQ-TERMINAL-001", "TERMINAL_OUTCOME_MISMATCH", "REAL_REPLAY_TAPE"),
)

RUNTIME_REQUIRED_MUTATIONS: tuple[MutationSpec, ...] = (
    MutationSpec(
        "MQ-HIDDEN-001",
        "XmageFullGameHiddenInformationTest#qualificationOracleKillsInjectedOpponentPrivateIdentity",
        "LIVE_XMAGE_BOUNDARY",
    ),
)


# B7 (#488): the divergence class the live replay consumer
# (``semantic_replay.consumer.replay_tape``) must raise for each real-tape
# mutation when a fresh engine process replays the mutated tape.
LIVE_CONSUMER_DETECTORS: dict[str, DivergenceClass] = {
    "MQ-LEGAL-001": DivergenceClass.LEGAL_SET_MISMATCH,
    "MQ-DECISION-001": DivergenceClass.CHOSEN_OPTION_MISSING,
    "MQ-RNG-001": DivergenceClass.RULES_RNG_CALL_DRIFT,
    "MQ-EVENT-001": DivergenceClass.EVENT_DIGEST_MISMATCH,
    "MQ-OBS-001": DivergenceClass.OBSERVATION_MISMATCH,
    "MQ-STATE-001": DivergenceClass.STATE_DIGEST_MISMATCH,
    "MQ-TERMINAL-001": DivergenceClass.TERMINAL_OUTCOME_MISMATCH,
}
LIVE_RESULT_SCHEMA_VERSION = "commander-lab.meta-verification-live-consumer/1.0.0"


def _nonzero_digest(current: str) -> str:
    replacement = "0" * 64
    if current == replacement:
        replacement = "1" * 64
    return replacement


def _mutate_real_tape(tape: dict[str, Any], mutation_id: str) -> tuple[dict[str, Any], int | None]:
    mutated = copy.deepcopy(tape)
    steps = mutated["steps"]
    if not steps:
        raise ValueError("semantic replay tape has no decision steps")
    target = min(40, len(steps) - 1)
    step = steps[target]

    if mutation_id == "MQ-LEGAL-001":
        step["legal_set_digest"] = _nonzero_digest(step["legal_set_digest"])
        return mutated, target
    if mutation_id == "MQ-DECISION-001":
        fingerprints = list(step.get("selected_fingerprints") or [])
        if not fingerprints:
            fingerprints = ["meta-mutation-choice"]
        else:
            fingerprints[0] = "meta-mutation-choice"
        step["selected_fingerprints"] = fingerprints
        return mutated, target
    if mutation_id == "MQ-RNG-001":
        step["rng_calls_after"] = int(step["rng_calls_after"] or 0) + 1
        return mutated, target
    if mutation_id == "MQ-EVENT-001":
        step["event_digest"] = _nonzero_digest(step["event_digest"])
        return mutated, target
    if mutation_id == "MQ-OBS-001":
        step["principal_observation_digest"] = _nonzero_digest(step["principal_observation_digest"])
        return mutated, target
    if mutation_id == "MQ-STATE-001":
        current = step.get("post_checkpoint_digest")
        if not isinstance(current, str):
            raise ValueError("selected replay step has no post checkpoint digest")
        step["post_checkpoint_digest"] = _nonzero_digest(current)
        return mutated, target
    if mutation_id == "MQ-TERMINAL-001":
        outcomes = mutated["terminal_checkpoint"]["outcomes"]
        if not outcomes:
            raise ValueError("semantic replay tape has no terminal outcomes")
        outcomes[0]["won"] = not bool(outcomes[0]["won"])
        return mutated, len(steps)

    raise KeyError(f"unknown mutation: {mutation_id}")


def run_meta_verification(
    tape: dict[str, Any],
    *,
    source_tape: str,
    runtime_kills: set[str] | None = None,
) -> dict[str, Any]:
    """Run executable mutations while preserving fail-closed NOT_RUN accounting."""
    results: list[dict[str, Any]] = []
    runtime_kills = runtime_kills or set()

    for spec in REAL_TAPE_MUTATIONS:
        mutated, expected_index = _mutate_real_tape(tape, spec.mutation_id)
        comparison = compare_tapes(tape, mutated)
        divergence = comparison.divergence
        observed = divergence.kind.value if divergence is not None else None
        record_index = divergence.record_index if divergence is not None else None
        was_killed = (
            not comparison.match
            and observed == spec.expected_detector
            and record_index == expected_index
        )
        results.append(
            {
                "mutation_id": spec.mutation_id,
                "status": "KILLED" if was_killed else "SURVIVED",
                "expected_detector": spec.expected_detector,
                "observed_detector": observed,
                "record_index": record_index,
            }
        )

    for spec in RUNTIME_REQUIRED_MUTATIONS:
        executed = spec.mutation_id in runtime_kills
        results.append(
            {
                "mutation_id": spec.mutation_id,
                "status": "KILLED" if executed else "NOT_RUN",
                "expected_detector": spec.expected_detector,
                "observed_detector": spec.expected_detector if executed else None,
                "record_index": None,
            }
        )

    attempted = sum(row["status"] != "NOT_RUN" for row in results)
    killed_count = sum(row["status"] == "KILLED" for row in results)
    survived = sum(row["status"] == "SURVIVED" for row in results)
    not_run = sum(row["status"] == "NOT_RUN" for row in results)
    total = len(results)

    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "catalog_version": CATALOG_VERSION,
        "source_tape": source_tape,
        "results": results,
        "attempted": attempted,
        "killed": killed_count,
        "survived": survived,
        "not_run": not_run,
        "kill_rate": killed_count / attempted if attempted else None,
        "catalog_coverage": attempted / total if total else 0.0,
    }


def run_live_consumer_mutations(
    tape: dict[str, Any],
    *,
    replay: Callable[[Path], dict[str, Any]],
    workdir: Path,
    source_tape: str,
) -> dict[str, Any]:
    """Replay every real-tape mutation through the live consumer (B7).

    ``replay`` consumes one tape file in a fresh engine process and raises
    ``ReplayDivergence`` on the first divergence (``consumer.replay_tape``).
    The unmutated tape must replay cleanly first: a baseline that does not
    replay leaves every mutation NOT_RUN, because a divergence would then prove
    nothing about the mutation. A mutation is KILLED only when the consumer
    raises exactly its expected class at the mutated step (the consumer names
    the step as ``step N:``; a terminal mutation is checked at the end); a pass,
    another class or another step is SURVIVED.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    baseline_path = workdir / "baseline.tape.json"
    baseline_path.write_text(json.dumps(tape, sort_keys=True), encoding="utf-8")
    baseline: dict[str, Any]
    try:
        verdict = replay(baseline_path)
        baseline = {"status": "PASS", "steps_verified": verdict.get("steps_verified")}
    except ReplayDivergence as exc:
        baseline = {"status": "FAIL", "divergence": exc.divergence.value, "detail": exc.detail}

    results: list[dict[str, Any]] = []
    for spec in REAL_TAPE_MUTATIONS:
        expected = LIVE_CONSUMER_DETECTORS[spec.mutation_id]
        row: dict[str, Any] = {
            "mutation_id": spec.mutation_id,
            "execution_tier": "LIVE_REPLAY_CONSUMER",
            "expected_divergence": expected.value,
            "observed_divergence": None,
            "detail": None,
        }
        if baseline["status"] != "PASS":
            results.append({**row, "status": "NOT_RUN"})
            continue
        mutated, index = _mutate_real_tape(tape, spec.mutation_id)
        assert index is not None
        expected_step = index + 1 if index < len(tape["steps"]) else None
        row["expected_step"] = expected_step
        path = workdir / f"{spec.mutation_id}.tape.json"
        path.write_text(json.dumps(mutated, sort_keys=True), encoding="utf-8")
        try:
            replay(path)
            results.append({**row, "status": "SURVIVED"})
        except ReplayDivergence as exc:
            observed = exc.divergence.value
            at_step = expected_step is None or exc.detail.startswith(f"step {expected_step}:")
            results.append(
                {
                    **row,
                    "status": "KILLED" if observed == expected.value and at_step else "SURVIVED",
                    "observed_divergence": observed,
                    "detail": exc.detail,
                }
            )

    killed = sum(row["status"] == "KILLED" for row in results)
    return {
        "schema_version": LIVE_RESULT_SCHEMA_VERSION,
        "catalog_version": CATALOG_VERSION,
        "source_tape": source_tape,
        "baseline": baseline,
        "results": results,
        "attempted": sum(row["status"] != "NOT_RUN" for row in results),
        "killed": killed,
        "survived": sum(row["status"] == "SURVIVED" for row in results),
        "not_run": sum(row["status"] == "NOT_RUN" for row in results),
        "complete": baseline["status"] == "PASS" and killed == len(results),
    }


__all__ = [
    "CATALOG_VERSION",
    "LIVE_CONSUMER_DETECTORS",
    "LIVE_RESULT_SCHEMA_VERSION",
    "REAL_TAPE_MUTATIONS",
    "RESULT_SCHEMA_VERSION",
    "RUNTIME_REQUIRED_MUTATIONS",
    "MutationSpec",
    "run_live_consumer_mutations",
    "run_meta_verification",
]
