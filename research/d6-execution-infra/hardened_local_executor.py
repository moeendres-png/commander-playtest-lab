"""Candidate 1 (improved local): stdlib-only hardened executor.

Properties:
- spawn process pool (one game / one task isolation; strict mode available
  via subprocess per task — same file-backed protocol);
- immutable run manifest (run_id, master_seed, engine version, per-job seeds);
- deterministic seed assignment preserved across retries (retry reuses the
  same job_id + seed, only attempt increments);
- per-task timeout with TIMEOUT failure class;
- retries for CRASH/TIMEOUT/TRANSIENT up to max_retries;
- explicit failure accounting: every job ends completed | failed_* |
  quarantined — a crash never becomes PASS;
- resume: completed records on disk are reused, never re-executed;
- duplicate suppression: same job_id submitted twice executes once;
- quarantine: jobs exhausting retries move to quarantine/ with reason;
- artifact collection: records/<job_id>.json + run-manifest.json + report.json.
"""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from workload import synthetic_game

FAILURE_CLASSES = ("CRASH", "TIMEOUT", "TRANSIENT", "UNKNOWN")


def _classify(exc: BaseException, *, timed_out: bool) -> str:
    if timed_out or isinstance(exc, TimeoutError):
        return "TIMEOUT"
    msg = str(exc)
    if "injected worker crash" in msg:
        return "CRASH"
    if "injected transient" in msg:
        return "TRANSIENT"
    return "UNKNOWN"


def _run_task(task: dict) -> dict:
    return synthetic_game(
        task["job_id"], task["seed"], attempt=task["attempt"], scenario=task["scenario"]
    )


def _manifest(out_dir: Path, run_id: str, master_seed: int, plan: list[dict]) -> Path:
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "master_seed": master_seed,
        "engine_version": "d6-synthetic-v1",
        "immutable": True,
        "jobs": [
            {"job_id": t["job_id"], "index": t["index"], "seed": t["seed"],
             "scenario": t["scenario"]}
            for t in plan
        ],
    }
    path = out_dir / "run-manifest.json"
    if path.exists():
        existing = json.loads(path.read_text())
        assert existing["run_id"] == run_id, "manifest run_id mismatch"
        assert existing["master_seed"] == master_seed, "manifest seed mismatch"
        assert existing["jobs"] == manifest["jobs"], "manifest jobs mutated"
        return path
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return path


def _read_record(records_dir: Path, job_id: str) -> dict | None:
    path = records_dir / f"{job_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _write_record(records_dir: Path, job_id: str, record: dict) -> None:
    tmp = records_dir / f"{job_id}.json.tmp"
    tmp.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    tmp.replace(records_dir / f"{job_id}.json")


def run_hardened(
    plan: list[dict],
    out_dir: str | Path,
    *,
    run_id: str,
    master_seed: int,
    workers: int = 4,
    task_timeout_seconds: float = 2.0,
    max_retries: int = 1,
    extra_submissions: list[dict] | None = None,
) -> dict:
    out = Path(out_dir)
    records = out / "records"
    quarantine = out / "quarantine"
    records.mkdir(parents=True, exist_ok=True)
    quarantine.mkdir(parents=True, exist_ok=True)
    _manifest(out, run_id, master_seed, plan)

    # Duplicate suppression: first submission wins.
    seen: dict[str, dict] = {}
    for task in list(plan) + list(extra_submissions or []):
        seen.setdefault(task["job_id"], task)
    unique_tasks = [seen[t["job_id"]] for t in plan]

    started = time.perf_counter()
    first_result_at: float | None = None
    executed = 0
    resumed = 0
    duplicates_suppressed = (len(plan) + len(extra_submissions or [])) - len(seen)
    retried: dict[str, int] = {}

    # Resume: reuse completed records without re-execution.
    pending: list[dict] = []
    for task in unique_tasks:
        rec = _read_record(records, task["job_id"])
        if rec is not None and rec.get("status") == "completed":
            resumed += 1
            if first_result_at is None:
                first_result_at = 0.0
            continue
        pending.append(task)

    attempts: dict[str, int] = {t["job_id"]: 0 for t in pending}
    scenarios = {t["job_id"]: t["scenario"] for t in pending}
    remaining = list(pending)

    with ProcessPoolExecutor(
        max_workers=workers, mp_context=multiprocessing.get_context("spawn")
    ) as ex:
        while remaining:
            futures = {
                ex.submit(
                    _run_task,
                    {
                        "job_id": t["job_id"],
                        "seed": t["seed"],
                        "attempt": attempts[t["job_id"]],
                        "scenario": scenarios[t["job_id"]],
                    },
                ): t
                for t in remaining
            }
            remaining = []
            for fut, task in futures.items():
                jid = task["job_id"]
                attempt = attempts[jid]
                timed_out = False
                try:
                    payload = fut.result(timeout=task_timeout_seconds)
                    error: BaseException | None = None
                except Exception as exc:  # noqa: BLE001 - failure accounting
                    payload = None
                    error = exc
                    timed_out = isinstance(exc, TimeoutError)
                    # concurrent.futures raises TimeoutError on fut.result(timeout=...)
                    try:
                        fut.cancel()
                    except Exception:  # noqa: BLE001,S110
                        pass
                executed += 1
                if error is None:
                    assert payload is not None
                    assert payload["seed"] == task["seed"], "seed identity violated"
                    assert payload["job_id"] == jid, "run identity violated"
                    _write_record(
                        records,
                        jid,
                        {
                            "job_id": jid,
                            "seed": task["seed"],
                            "status": "completed",
                            "attempt": attempt,
                            "result_hash": payload["result_hash"],
                        },
                    )
                    if first_result_at is None:
                        first_result_at = time.perf_counter() - started
                else:
                    fclass = _classify(error, timed_out=timed_out)
                    if attempt < max_retries and fclass in ("CRASH", "TIMEOUT", "TRANSIENT"):
                        attempts[jid] = attempt + 1
                        retried[jid] = attempt + 1
                        remaining.append(task)
                    else:
                        record = {
                            "job_id": jid,
                            "seed": task["seed"],
                            "status": f"failed_{fclass.lower()}",
                            "attempt": attempt,
                            "failure_class": fclass,
                            "failure_message": f"{type(error).__name__}: {error}",
                        }
                        _write_record(records, jid, record)
                        (quarantine / f"{jid}.json").write_text(
                            json.dumps(record, indent=2, sort_keys=True) + "\n"
                        )

    wall = time.perf_counter() - started
    # Artifact collection: final report + manifest hash.
    final_records = []
    for task in unique_tasks:
        rec = _read_record(records, task["job_id"])
        assert rec is not None, f"missing record for {task['job_id']}"
        final_records.append(rec)
    completed = sum(1 for r in final_records if r["status"] == "completed")
    failed = [r for r in final_records if r["status"] != "completed"]
    assert all("result_hash" in r for r in final_records if r["status"] == "completed")
    # A crash must never become PASS: failed records carry no result_hash.
    assert all("result_hash" not in r for r in failed), "failure leaked a result hash"
    manifest_hash = hashlib.sha256((out / "run-manifest.json").read_bytes()).hexdigest()
    report = {
        "executor": "hardened-local",
        "total": len(unique_tasks),
        "completed": completed,
        "failed": len(failed),
        "failure_classes": sorted({r.get("failure_class", "?") for r in failed}),
        "executed_tasks": executed,
        "resumed": resumed,
        "duplicates_suppressed": duplicates_suppressed,
        "retried": retried,
        "wall_seconds": wall,
        "startup_overhead_seconds": first_result_at,
        "manifest_sha256": manifest_hash,
    }
    (out / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    report["records"] = final_records
    return report
