"""Meta-qualification mutation runner over existing semantic replay infrastructure.

This module does not implement Magic rules and does not reconstruct legality. It
injects controlled faults into an already recorded real semantic replay tape and
asks the existing provider-neutral comparator whether the fault is detected.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from commander_lab.semantic_replay.comparator import compare_tapes

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
    MutationSpec("MQ-HIDDEN-001", "XmageFullGameHiddenInformationTest", "RUNTIME_BRIDGE_REQUIRED"),
)


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
        step["principal_observation_digest"] = _nonzero_digest(
            step["principal_observation_digest"]
        )
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
) -> dict[str, Any]:
    """Run all currently executable semantic mutations and account for NOT_RUN entries."""
    results: list[dict[str, Any]] = []

    for spec in REAL_TAPE_MUTATIONS:
        mutated, expected_index = _mutate_real_tape(tape, spec.mutation_id)
        comparison = compare_tapes(tape, mutated)
        divergence = comparison.divergence
        observed = divergence.kind.value if divergence is not None else None
        record_index = divergence.record_index if divergence is not None else None
        killed = (
            not comparison.match
            and observed == spec.expected_detector
            and record_index == expected_index
        )
        results.append(
            {
                "mutation_id": spec.mutation_id,
                "status": "KILLED" if killed else "SURVIVED",
                "expected_detector": spec.expected_detector,
                "observed_detector": observed,
                "record_index": record_index,
            }
        )

    for spec in RUNTIME_REQUIRED_MUTATIONS:
        results.append(
            {
                "mutation_id": spec.mutation_id,
                "status": "NOT_RUN",
                "expected_detector": spec.expected_detector,
                "observed_detector": None,
                "record_index": None,
            }
        )

    attempted = sum(row["status"] != "NOT_RUN" for row in results)
    killed = sum(row["status"] == "KILLED" for row in results)
    survived = sum(row["status"] == "SURVIVED" for row in results)
    not_run = sum(row["status"] == "NOT_RUN" for row in results)
    total = len(results)

    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "catalog_version": CATALOG_VERSION,
        "source_tape": source_tape,
        "results": results,
        "attempted": attempted,
        "killed": killed,
        "survived": survived,
        "not_run": not_run,
        "kill_rate": killed / attempted if attempted else None,
        "catalog_coverage": attempted / total if total else 0.0,
    }


__all__ = [
    "CATALOG_VERSION",
    "REAL_TAPE_MUTATIONS",
    "RESULT_SCHEMA_VERSION",
    "RUNTIME_REQUIRED_MUTATIONS",
    "MutationSpec",
    "run_meta_verification",
]
