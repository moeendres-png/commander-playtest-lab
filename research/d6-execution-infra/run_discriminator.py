"""D6 discriminator runner: baseline vs hardened-local vs Ray (if available).

Compares semantic output hashes, seed allocation, failure accounting,
throughput, memory, startup overhead. Writes evidence JSON + prints summary.
Usage: .venv/bin/python research/d6-execution-infra/run_discriminator.py
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tracemalloc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from baseline_executor import run_baseline  # noqa: E402
from hardened_local_executor import run_hardened  # noqa: E402
from workload import build_plan  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
EVIDENCE = os.path.join(ROOT, "evidence")
RUN_ID = "d6-discriminator"
MASTER_SEED = 20260910
N = 24
WORKERS = 4


def sha_of_hashes(records) -> str:
    ok = sorted(r["result_hash"] for r in records if r.get("status") == "completed")
    return hashlib.sha256("|".join(ok).encode()).hexdigest()


def main() -> int:
    shutil.rmtree(EVIDENCE, ignore_errors=True)
    os.makedirs(EVIDENCE, exist_ok=True)
    plan = build_plan(RUN_ID, MASTER_SEED, N)
    with open(os.path.join(EVIDENCE, "plan.json"), "w") as fh:
        json.dump(plan, fh, indent=2, sort_keys=True)

    tracemalloc.start()
    base = run_baseline(plan, workers=WORKERS)
    _, base_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    base["peak_python_bytes"] = base_peak
    with open(os.path.join(EVIDENCE, "baseline.json"), "w") as fh:
        json.dump(base, fh, indent=2, sort_keys=True)

    # Hardened run 1: fresh (with a duplicate submission of job-0003 to test dedupe).
    dup = dict(plan[3])
    tracemalloc.start()
    hard1 = run_hardened(plan, os.path.join(EVIDENCE, "hardened-fresh"),
                         run_id=RUN_ID, master_seed=MASTER_SEED, workers=WORKERS,
                         extra_submissions=[dup])
    _, h1_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    hard1["peak_python_bytes"] = h1_peak

    # Hardened run 2: resume against the same output dir (all completed -> 0 executions).
    hard2 = run_hardened(plan, os.path.join(EVIDENCE, "hardened-fresh"),
                         run_id=RUN_ID, master_seed=MASTER_SEED, workers=WORKERS)

    # Hardened run 3: partial completion resume. Seed 8 completed records, run fresh dir copy.
    partial_dir = os.path.join(EVIDENCE, "hardened-resume")
    os.makedirs(os.path.join(partial_dir, "records"), exist_ok=True)
    fresh_records = os.path.join(EVIDENCE, "hardened-fresh", "records")
    for t in plan[:8]:
        shutil.copy(os.path.join(fresh_records, f"{t['job_id']}.json"),
                    os.path.join(partial_dir, "records", f"{t['job_id']}.json"))
    hard3 = run_hardened(plan, partial_dir, run_id=RUN_ID, master_seed=MASTER_SEED,
                         workers=WORKERS)

    try:
        import ray  # noqa: F401
        from ray_candidate import run_ray  # noqa: E402

        ray_rep = run_ray(plan, os.path.join(EVIDENCE, "ray"),
                          run_id=RUN_ID, master_seed=MASTER_SEED, workers=WORKERS)
        ray_status = "ran"
        try:
            import ray as _ray
            _ray.shutdown()
        except Exception:  # noqa: BLE001
            pass
    except ImportError as exc:
        ray_rep = {"executor": "ray-core", "status": "NOT_RUN", "reason": str(exc)}
        ray_status = "not_installed"

    evidence = {"run_id": RUN_ID, "master_seed": MASTER_SEED, "n": N, "workers": WORKERS,
                "baseline": {k: v for k, v in base.items() if k != "results"},
                "baseline_result_count": len(base["results"]),
                "hardened_fresh": {k: v for k, v in hard1.items() if k != "records"},
                "hardened_resume_full": {k: v for k, v in hard2.items() if k != "records"},
                "hardened_resume_partial": {k: v for k, v in hard3.items() if k != "records"},
                "ray": {k: v for k, v in ray_rep.items() if k != "records"},
                "ray_status": ray_status}
    # Semantic hash comparison over the clean (non-fault) subset: run a clean
    # plan through both executors and compare.
    clean_plan = [dict(t, scenario="clean") for t in plan]
    clean_base = run_baseline(clean_plan, workers=WORKERS)
    clean_hard = run_hardened(clean_plan, os.path.join(EVIDENCE, "hardened-clean"),
                              run_id=RUN_ID + "-clean", master_seed=MASTER_SEED,
                              workers=WORKERS)
    hb = sha_of_hashes([{"status": "completed", "result_hash": r["result_hash"]}
                        for r in clean_base["results"]])
    hh = sha_of_hashes(clean_hard["records"])
    evidence["semantic_hash_baseline_clean"] = hb
    evidence["semantic_hash_hardened_clean"] = hh
    evidence["semantic_hashes_equal"] = hb == hh
    with open(os.path.join(EVIDENCE, "discriminator-evidence.json"), "w") as fh:
        json.dump(evidence, fh, indent=2, sort_keys=True)

    print(f"baseline: completed={base['completed']}/{N} aborted={base['aborted_batch']} "
          f"error={base['error']} wall={base['wall_seconds']:.2f}s")
    print(f"hardened fresh: completed={hard1['completed']}/{N} failed={hard1['failed']} "
          f"executed={hard1['executed_tasks']} wall={hard1['wall_seconds']:.2f}s "
          f"retried={hard1['retried']} dup_suppressed={hard1['duplicates_suppressed']}")
    print(f"hardened resume(full): executed={hard2['executed_tasks']} resumed={hard2['resumed']}")
    print(f"hardened resume(partial 8/24): executed={hard3['executed_tasks']} "
          f"resumed={hard3['resumed']}")
    print(f"ray: {ray_status} {json.dumps({k: v for k, v in ray_rep.items() if k != 'records'})[:300]}")
    print(f"semantic hashes equal (clean plan): {evidence['semantic_hashes_equal']}")
    # Gate assertions for the report.
    assert base["aborted_batch"], "baseline must abort on injected crash (documents gap)"
    assert hard1["completed"] == N, "hardened must complete all incl. retries"
    assert hard2["executed_tasks"] == 0 and hard2["resumed"] == N, "full resume must reuse all"
    assert hard3["resumed"] == 8, "partial resume must reuse exactly the 8 seeded records"
    assert hard1["duplicates_suppressed"] == 1, "duplicate job must be suppressed"
    for r in hard1["records"]:
        if r["job_id"].endswith(("0005", "0011", "0017")):
            orig = next(t for t in plan if t["job_id"] == r["job_id"])
            assert r["seed"] == orig["seed"], "retry must preserve seed identity"
    assert evidence["semantic_hashes_equal"], "semantic outputs must match across executors"
    print("ALL D6 DISCRIMINATOR GATES PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
