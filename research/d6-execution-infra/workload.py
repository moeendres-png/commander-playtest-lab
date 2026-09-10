"""D6 deterministic synthetic workload.

Pure hash-math pseudo-games. No Rules semantics: no legal actions, mana,
targets, combat, triggers, or Commander rules appear here. The workload only
exposes executor behaviour: scheduling, retries, worker crashes, timeouts,
duplicate jobs, and resume from partial completion.
"""

from __future__ import annotations

import hashlib
import time

ENGINE_VERSION = "d6-synthetic-v1"


def derive_seed(master_seed: int, run_id: str, index: int) -> int:
    payload = f"{ENGINE_VERSION}|{master_seed}|{run_id}|{index}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big", signed=False)


def job_id_for(run_id: str, index: int) -> str:
    return f"{run_id}-job-{index:04d}"


def synthetic_game(job_id: str, seed: int, *, attempt: int, scenario: str = "clean") -> dict:
    """Deterministic pseudo-game returning a semantic result hash.

    Fault injection is attempt-gated so a retry with the same seed/job_id
    succeeds: this models 'retried game preserves original seed/run identity'.
    """
    if scenario == "crash" and attempt == 0:
        raise RuntimeError(f"injected worker crash for {job_id}")
    if scenario == "timeout" and attempt == 0:
        time.sleep(4.0)  # caller enforces timeout; retry succeeds fast
    if scenario == "flaky" and attempt == 0:
        raise RuntimeError(f"injected transient failure for {job_id}")
    # Deterministic CPU work (~ms) standing in for a real simulation.
    acc = hashlib.sha256(f"{job_id}|{seed}|{attempt}".encode()).digest()
    for _ in range(200):
        acc = hashlib.sha256(acc).digest()
    result_hash = hashlib.sha256(f"result|{job_id}|{seed}|{acc.hex()}".encode()).hexdigest()
    return {"job_id": job_id, "seed": seed, "attempt": attempt, "result_hash": result_hash}


def build_plan(run_id: str, master_seed: int, n: int = 24) -> list[dict]:
    """24-shard plan with deterministic fault placement."""
    faults = {5: "crash", 11: "timeout", 17: "flaky"}
    plan = []
    for index in range(n):
        plan.append(
            {
                "index": index,
                "job_id": job_id_for(run_id, index),
                "seed": derive_seed(master_seed, run_id, index),
                "scenario": faults.get(index, "clean"),
            }
        )
    return plan
