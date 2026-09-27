from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/phase12_20/isolated_pytest"
OUT.mkdir(parents=True, exist_ok=True)
FILES = sorted(ROOT.glob("tests/**/test_*.py"))


def parse_counts(text: str):
    out = {k: 0 for k in ("passed", "failed", "skipped", "error")}
    for k in out:
        patt = "errors" if k == "error" else k
        m = re.findall(rf"(\d+) {patt}", text)
        if m:
            out[k] = int(m[-1])
    return out


def run_file(p: Path):
    rel = str(p.relative_to(ROOT))
    start = time.time()
    proc = subprocess.Popen(
        [sys.executable, "-m", "pytest", "-q", rel],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
        env={**os.environ, "PYTHONPATH": "src"},
    )
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=65)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            stdout, stderr = proc.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate()
    text = (stdout + "\n" + stderr).strip()
    counts = parse_counts(text)
    if (
        timed_out
        and counts["failed"] == 0
        and counts["error"] == 0
        and (counts["passed"] or counts["skipped"])
    ):
        status = "passed_with_cleanup_timeout"
    elif timed_out:
        status = "timeout"
    elif proc.returncode == 0:
        status = "passed"
    else:
        status = "failed"
    log = OUT / (p.stem + "." + p.parent.name + ".log")
    log.write_text(text + "\n", encoding="utf-8")
    return {
        "file": rel,
        "status": status,
        "returncode": proc.returncode,
        "seconds": round(time.time() - start, 3),
        "counts": counts,
        "log": str(log.relative_to(ROOT)),
        "tail": "\n".join(text.splitlines()[-10:]),
    }


rows = []
with ThreadPoolExecutor(max_workers=6) as ex:
    futs = {ex.submit(run_file, p): p for p in FILES}
    for i, f in enumerate(as_completed(futs), 1):
        r = f.result()
        rows.append(r)
        print(f"[{i}/{len(FILES)}] {r['status']} {r['file']} {r['counts']}", flush=True)
rows.sort(key=lambda x: x["file"])
summary = {
    "files": len(rows),
    "tests_passed": sum(r["counts"]["passed"] for r in rows),
    "tests_failed": sum(r["counts"]["failed"] for r in rows),
    "tests_skipped": sum(r["counts"]["skipped"] for r in rows),
    "tests_errors": sum(r["counts"]["error"] for r in rows),
    "cleanup_timeouts": sum(r["status"] == "passed_with_cleanup_timeout" for r in rows),
    "bad_files": [r["file"] for r in rows if r["status"] in {"failed", "timeout"}],
}
(ROOT / "artifacts/phase12_20/FINAL_TEST_RESULTS.json").write_text(
    json.dumps({"summary": summary, "files": rows}, indent=2) + "\n"
)
lines = ["# Final isolated pytest suite", json.dumps(summary, indent=2), ""]
for r in rows:
    lines.append(f"{r['status']}: {r['file']} :: {r['counts']}")
(ROOT / "artifacts/phase12_20/FINAL_TEST_RESULTS.txt").write_text("\n".join(lines) + "\n")
print("SUMMARY", json.dumps(summary, indent=2), flush=True)
if summary["bad_files"] or summary["tests_failed"] or summary["tests_errors"]:
    raise SystemExit(1)
