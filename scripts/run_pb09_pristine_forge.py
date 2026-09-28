#!/usr/bin/env python3
"""PB-09 pristine-upstream Forge FULL107 run (Muse XHIGH).

Executes the current-boundary denominator against pristine upstream Forge
(Rules-Core a37a865a + bridge source 4753bb7c) in the isolated worktree,
failing closed on any identity mismatch. Writes to a NEW evidence directory;
donor files are never touched.

The bridge-driven run produces lifecycle evidence (AF01, cardinality,
START-2, hidden, replay, actual-card) plus honest UNKNOWN for every row
without an audited per-row execution binding (Wave-F native audit pending).
No native-suite row credit is transferred.

Usage:
  python3 scripts/run_pb09_pristine_forge.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

FORGE_PRISTINE_WORKTREE = Path(
    "/tmp/foundry-launch-final-completion-muse-xhigh/launch-final-completion-muse-xhigh-5z86ui59/forge-pristine"
)
PINNED_RULES_CORE = "a37a865a53280dd8ad6fad3384d69611e8c5a42f"
PINNED_BRIDGE_SOURCE = "4753bb7c72ea60d653121e0bab989077b4009f9c"
OUT_SUBDIR = "qualification/pb09-pristine-forge-20260928"


def run(
    *args: str | Path, cwd: Path | None = None, timeout: int = 3600
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(a) for a in args],
        cwd=str(cwd or REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )


def fail_closed(message: str) -> int:
    print(f"FAIL_CLOSED: {message}", file=sys.stderr)
    return 2


def main() -> int:
    if not FORGE_PRISTINE_WORKTREE.is_dir():
        return fail_closed(f"pristine worktree absent: {FORGE_PRISTINE_WORKTREE}")
    head = run("git", "rev-parse", "HEAD", cwd=FORGE_PRISTINE_WORKTREE).stdout.strip()
    if head != PINNED_BRIDGE_SOURCE:
        return fail_closed(f"worktree HEAD {head} != pinned bridge source {PINNED_BRIDGE_SOURCE}")
    ancestor = run(
        "git",
        "merge-base",
        "--is-ancestor",
        PINNED_RULES_CORE,
        "HEAD",
        cwd=FORGE_PRISTINE_WORKTREE,
    )
    if ancestor.returncode != 0:
        return fail_closed(f"{PINNED_RULES_CORE} is not an ancestor of {head}")
    tree = run("git", "rev-parse", "HEAD^{tree}", cwd=FORGE_PRISTINE_WORKTREE).stdout.strip()
    status = run("git", "status", "--short", cwd=FORGE_PRISTINE_WORKTREE).stdout.strip()
    if status:
        return fail_closed(f"pristine worktree not clean: {status[:200]}")
    bridge_classes = FORGE_PRISTINE_WORKTREE / "forge-protocol2-bridge" / "target" / "classes"
    bridge_cp = FORGE_PRISTINE_WORKTREE / "forge-protocol2-bridge" / "target" / "cp-wsr22.txt"
    if not (bridge_classes / "forge" / "bridge" / "BridgeMain.class").is_file():
        return fail_closed("pristine bridge not built (BridgeMain.class absent)")
    if not bridge_cp.is_file():
        return fail_closed("pristine bridge classpath manifest absent")
    print(f"identity OK: HEAD={head} tree={tree}")

    env = dict(os.environ)
    env["COMMANDER_LAB_FORGE_WORKSPACE"] = str(FORGE_PRISTINE_WORKTREE)
    env["COMMANDER_LAB_FORGE_ENGINE_COMMIT"] = PINNED_RULES_CORE
    env["COMMANDER_LAB_OUT_DIR"] = str(REPO_ROOT / OUT_SUBDIR)
    completed = subprocess.run(
        [sys.executable, "scripts/run_current_boundary_qualification.py", "--candidate", "forge"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=7200,
    )
    print(completed.stdout[-3000:])
    print(completed.stderr[-2000:], file=sys.stderr)
    if completed.returncode != 0:
        return fail_closed(f"runner exited {completed.returncode}")

    out_dir = REPO_ROOT / OUT_SUBDIR
    results_path = out_dir / "FULL107_FORGE_RESULTS.json"
    if not results_path.is_file():
        return fail_closed("runner produced no FULL107_FORGE_RESULTS.json")
    results = json.loads(results_path.read_text(encoding="utf-8"))
    identity = results.get("runtime_identity", {})
    if identity.get("engine_candidate_commit") != PINNED_RULES_CORE:
        return fail_closed(
            f"executed engine {identity.get('engine_candidate_commit')} != pin {PINNED_RULES_CORE}"
        )
    print(f"engine identity OK: {identity.get('engine_candidate_commit')}")
    print(f"counts: {json.dumps(results.get('counts'))}")

    receipt = {
        "schema_version": "pb09.pristine-forge-run/1.0.0",
        "pinned_rules_core": PINNED_RULES_CORE,
        "pinned_bridge_source": PINNED_BRIDGE_SOURCE,
        "executed_worktree_head": head,
        "executed_worktree_tree": tree,
        "ancestry_rules_core_is_ancestor": True,
        "worktree_clean": True,
        "bridge_build": {
            "classes": str(bridge_classes),
            "classpath_manifest": str(bridge_cp),
            "bridge_main_present": True,
        },
        "engine_commit_binding": "env:FORGE_ENGINE_SHA (operator-supplied; PB-05 open)",
        "counts": results.get("counts"),
        "out_dir": OUT_SUBDIR,
        "terminal_states": {
            "ARCHITECTURE_FREEZE": "NOT CLAIMED",
            "PRODUCTION_PROVIDER": "NOT SELECTED",
        },
    }
    (out_dir / "PRISTINE_RUN_RECEIPT.json").write_text(
        json.dumps(receipt, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("wrote PRISTINE_RUN_RECEIPT.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
