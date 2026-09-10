"""Candidate 2 (Ray Core): same file-backed protocol over ray.remote tasks.

Only runs when `ray` is importable. Semantics mirror hardened_local_executor
(resume, retry with preserved seed identity, timeout via ray.wait, duplicate
suppression, quarantine, manifest) so the comparison measures substrate cost,
not protocol differences.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from hardened_local_executor import _classify, _manifest, _read_record, _write_record
from workload import synthetic_game


def run_ray(plan, out_dir, *, run_id, master_seed, workers=4,
            task_timeout_seconds=2.0, max_retries=1, extra_submissions=None) -> dict:
    import ray  # noqa: PLC0415

    out = Path(out_dir)
    records = out / "records"
    quarantine = out / "quarantine"
    records.mkdir(parents=True, exist_ok=True)
    quarantine.mkdir(parents=True, exist_ok=True)
    _manifest(out, run_id, master_seed, plan)

    seen: dict[str, dict] = {}
    for task in list(plan) + list(extra_submissions or []):
        seen.setdefault(task["job_id"], task)
    unique_tasks = [seen[t["job_id"]] for t in plan]
    duplicates_suppressed = (len(plan) + len(extra_submissions or [])) - len(seen)

    started = time.perf_counter()
    init_started = time.perf_counter()
    if not ray.is_initialized():
        ray.init(num_cpus=workers, ignore_reinit_error=True, include_dashboard=False)
    init_seconds = time.perf_counter() - init_started

    @ray.remote
    def _remote(task: dict) -> dict:
        return synthetic_game(
            task["job_id"], task["seed"], attempt=task["attempt"], scenario=task["scenario"]
        )

    first_result_at: float | None = None
    executed = resumed = 0
    retried: dict[str, int] = {}
    pending = []
    for task in unique_tasks:
        rec = _read_record(records, task["job_id"])
        if rec is not None and rec.get("status") == "completed":
            resumed += 1
            continue
        pending.append(task)
    attempts = {t["job_id"]: 0 for t in pending}
    scenarios = {t["job_id"]: t["scenario"] for t in pending}
    remaining = list(pending)
    while remaining:
        refs = {
            _remote.remote(
                {"job_id": t["job_id"], "seed": t["seed"],
                 "attempt": attempts[t["job_id"]], "scenario": scenarios[t["job_id"]]}
            ): t
            for t in remaining
        }
        remaining = []
        ref_list = list(refs)
        deadline = time.monotonic() + task_timeout_seconds
        done_ok: dict = {}
        timed_out_refs: set = set()
        while ref_list:
            wait_s = max(0.0, deadline - time.monotonic())
            done, ref_list = ray.wait(ref_list, num_returns=len(ref_list), timeout=wait_s)
            for r in done:
                done_ok[r] = refs[r]
            if ref_list and time.monotonic() >= deadline:
                for r in ref_list:
                    timed_out_refs.add(r)
                    ray.cancel(r, force=True)
                break
        for ref, task in refs.items():
            jid = task["job_id"]
            attempt = attempts[jid]
            executed += 1
            if ref in timed_out_refs:
                error: BaseException | None = TimeoutError(
                    f"ray task exceeded {task_timeout_seconds}s for {jid}"
                )
                payload = None
                timed_out = True
            else:
                try:
                    payload = ray.get(ref)
                    error = None
                except Exception as exc:  # noqa: BLE001
                    payload, error = None, exc
                timed_out = isinstance(error, TimeoutError) if error else False
            if error is None:
                assert payload["seed"] == task["seed"] and payload["job_id"] == jid
                _write_record(records, jid, {"job_id": jid, "seed": task["seed"],
                                             "status": "completed", "attempt": attempt,
                                             "result_hash": payload["result_hash"]})
                if first_result_at is None:
                    first_result_at = time.perf_counter() - started
            else:
                fclass = _classify(error, timed_out=timed_out)
                if attempt < max_retries and fclass in ("CRASH", "TIMEOUT", "TRANSIENT"):
                    attempts[jid] = attempt + 1
                    retried[jid] = attempt + 1
                    remaining.append(task)
                else:
                    record = {"job_id": jid, "seed": task["seed"],
                              "status": f"failed_{fclass.lower()}", "attempt": attempt,
                              "failure_class": fclass,
                              "failure_message": f"{type(error).__name__}: {error}"}
                    _write_record(records, jid, record)
                    (quarantine / f"{jid}.json").write_text(json.dumps(record, indent=2) + "\n")

    wall = time.perf_counter() - started
    final_records = [_read_record(records, t["job_id"]) for t in unique_tasks]
    assert all(r is not None for r in final_records)
    completed = sum(1 for r in final_records if r["status"] == "completed")
    failed = [r for r in final_records if r["status"] != "completed"]
    manifest_hash = hashlib.sha256((out / "run-manifest.json").read_bytes()).hexdigest()
    report = {"executor": "ray-core", "total": len(unique_tasks), "completed": completed,
              "failed": len(failed),
              "failure_classes": sorted({r.get("failure_class", "?") for r in failed}),
              "executed_tasks": executed, "resumed": resumed,
              "duplicates_suppressed": duplicates_suppressed, "retried": retried,
              "wall_seconds": wall, "ray_init_seconds": init_seconds,
              "startup_overhead_seconds": first_result_at, "manifest_sha256": manifest_hash}
    (out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    report["records"] = final_records
    return report
