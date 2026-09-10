"""Unified deterministic bootstrap gate for Foundry workstreams.

Runs source-lock, duplicate-writer, state, writer-lock/CWD, and policy-drift
checks in one place so the model never hand-interprets fifteen shell outputs.
Prints BOOTSTRAP_PASS or the first fail-closed reason; machine-readable detail
goes to --json-output.

Read-only, except --init-state which writes a minimal schema-2.0 state
document (validated_head=null, placeholder objective the owner must replace).

Exit codes: 0 BOOTSTRAP_PASS (notes allowed); 1 BOOTSTRAP_FAIL.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import drift_check as drift_mod
import source_lock as source_lock_mod
import state as state_mod
import worktree_inventory as inventory_mod
import writer_lock as writer_lock_mod

DEFAULT_PROFILES_DIR = drift_mod.DEFAULT_PROFILES_DIR


def _git(args: list[str], cwd: str) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()[:200]}")
    return proc.stdout.strip()


def _default_state_path(worktree: str) -> str:
    return str(Path(worktree) / ".foundry" / "WORKSTREAM_STATE.yaml")


def init_state(
    worktree: str,
    workstream: str,
    branch: str,
    audit_base_sha: str,
    audit_base_tree: str,
    repository: str = "",
) -> dict:
    try:
        live_head = _git(["rev-parse", "HEAD"], worktree)
    except RuntimeError as exc:
        raise ValueError(f"cannot read HEAD for state init: {exc}") from exc
    return {
        "schema_version": "2.0",
        "repository": repository,
        "worktree": os.path.realpath(os.path.abspath(worktree)),
        "branch": branch,
        "audit_base_sha": audit_base_sha,
        "audit_base_tree": audit_base_tree,
        "state_written_against_head": live_head,
        "validated_head": None,
        "objective": f"BOOTSTRAP PLACEHOLDER for {workstream} (replace with contract objective)",
        "in_scope": [],
        "out_of_scope": [],
        "ownership": workstream,
        "status": "ACTIVE",
        "exact_next_action": "Replace placeholder objective/scope, then proceed.",
    }


def bootstrap(
    worktree: str,
    workstream: str,
    branch: str,
    audit_base_sha: str,
    state_path: str | None,
    profile_name: str,
    profiles_dir: str = DEFAULT_PROFILES_DIR,
    canonical_root: str = "",
    allow_same_cwd_pids: bool = False,
    allow_suppressed_routing: bool = False,
) -> dict:
    """Run every gate. Returns a result dict; verdict is BOOTSTRAP_PASS/FAIL."""
    notes: list[str] = []
    failures: list[str] = []
    canonical = os.path.realpath(os.path.abspath(worktree))
    profile = drift_mod.load_profile(profile_name, profiles_dir)
    slug = str(profile.get("repo_slug", ""))

    # 1. source lock (dirty allowed at bootstrap; reported, not failed).
    reasons = source_lock_mod.verify(slug, branch, audit_base_sha, canonical, allow_dirty=True)
    hard = [r for r in reasons if not r.startswith("dirty worktree")]
    if hard:
        failures.append(f"source lock: {hard[0]}")
    else:
        try:
            porcelain = _git(["status", "--porcelain"], canonical)
            if porcelain:
                notes.append(f"dirty tree ({len(porcelain.splitlines())} entries; continuing)")
        except RuntimeError:
            pass

    # 2. duplicate writer across worktrees of this repo.
    try:
        entries = inventory_mod.inventory(canonical)
        conflicts = inventory_mod.find_duplicate_writers(entries)
    except RuntimeError as exc:
        failures.append(f"worktree inventory: {exc}")
        conflicts = []
    if conflicts:
        failures.append(f"duplicate writer: {conflicts[0]}")

    # 3. state file.
    resolved_state = state_path or _default_state_path(canonical)
    try:
        with open(resolved_state, encoding="utf-8") as handle:
            import yaml

            data = yaml.safe_load(handle)
    except OSError:
        failures.append(f"state missing: {resolved_state} (create with --init-state)")
        data = None
    if data is not None:
        errors = state_mod.validate(data if isinstance(data, dict) else {})
        if errors:
            failures.append(f"invalid state: {errors[0]}")
        else:
            if isinstance(data, dict):
                if str(data.get("schema_version")) == "1.0":
                    notes.append("state schema 1.0 (legacy; migrate to 2.0)")
                if str(data.get("branch", "")) != branch:
                    failures.append(f"state branch {data.get('branch')!r} != expected {branch!r}")
                try:
                    state_wt = os.path.realpath(str(data.get("worktree", "")))
                except (TypeError, ValueError):
                    state_wt = ""
                if state_wt != canonical:
                    failures.append("state worktree does not match this worktree")
                ownership = str(data.get("ownership", ""))
                if not ownership or ownership == "UNKNOWN":
                    notes.append("state ownership unknown (proceeding; push will refuse)")

    # 4. writer lock must be FREE (we acquire later) + no same-CWD opencode.
    lock_path = writer_lock_mod.lock_path_for(canonical)
    if lock_path.exists():
        import fcntl

        try:
            fd = os.open(lock_path, os.O_RDONLY)
        except OSError:
            fd = None
        if fd is not None:
            try:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    holder = writer_lock_mod.read_holder(lock_path) or {}
                    failures.append(
                        "writer already held by "
                        f"{holder.get('workstream', '?')!r} (pid={holder.get('pid', '?')})"
                    )
                else:
                    fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)
    occupants = writer_lock_mod.scan_cwd_processes(canonical)
    live_occupants = [p for p in occupants if "note" not in p]
    if live_occupants and not allow_same_cwd_pids:
        failures.append(
            "same-CWD opencode process(es) "
            f"{[p['pid'] for p in live_occupants]} without this launcher holding the "
            "lock (resolve or pass --allow-same-cwd-pids explicitly)"
        )
    elif live_occupants:
        notes.append(f"same-CWD opencode explicitly allowed: {[p['pid'] for p in live_occupants]}")

    # 5. policy drift.
    drift = drift_mod.check(canonical, profile, canonical_root or "")
    if drift["verdict"] == "DRIFT_FAIL" and not allow_suppressed_routing:
        bad = [
            f
            for f in drift["findings"]
            if f["classification"] in ("SUPERSEDED_BUT_REACHABLE", "AMBIGUOUS")
        ]
        failures.append(f"policy drift: {bad[0]['surface']} {bad[0]['classification']}")
    elif drift["verdict"] == "DRIFT_FAIL":
        notes.append("policy drift explicitly suppressed (canonical text may not reach model)")

    verdict = "BOOTSTRAP_FAIL" if failures else "BOOTSTRAP_PASS"
    return {
        "verdict": verdict,
        "worktree": canonical,
        "workstream": workstream,
        "branch": branch,
        "profile": profile_name,
        "state_path": resolved_state,
        "failures": failures,
        "notes": notes,
        "drift": drift,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Foundry unified bootstrap gate.")
    parser.add_argument("--worktree", required=True)
    parser.add_argument("--workstream", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--audit-base-sha", required=True)
    parser.add_argument("--state", default=None)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--profiles-dir", default=DEFAULT_PROFILES_DIR)
    parser.add_argument("--canonical-root", default="")
    parser.add_argument("--allow-same-cwd-pids", action="store_true")
    parser.add_argument("--allow-suppressed-routing", action="store_true")
    parser.add_argument("--json-output", default=None)
    parser.add_argument("--audit-base-tree", default="0" * 40)
    parser.add_argument(
        "--init-state",
        action="store_true",
        help="Write a minimal 2.0 state file when none exists, then continue.",
    )
    args = parser.parse_args(argv)
    resolved_state = args.state or _default_state_path(
        os.path.realpath(os.path.abspath(args.worktree))
    )
    if args.init_state and not Path(resolved_state).exists():
        try:
            profile = drift_mod.load_profile(args.profile, args.profiles_dir)
            doc = init_state(
                args.worktree,
                args.workstream,
                args.branch,
                args.audit_base_sha,
                args.audit_base_tree,
                str(profile.get("repo_slug", "")),
            )
        except ValueError as exc:
            print(f"BOOTSTRAP_FAIL: {exc}", file=sys.stderr)
            return 1
        import yaml

        Path(resolved_state).parent.mkdir(parents=True, exist_ok=True)
        Path(resolved_state).write_text(yaml.safe_dump(doc), encoding="utf-8")
        print(f"BOOTSTRAP_NOTE: initialized minimal state at {resolved_state}")
    result = bootstrap(
        args.worktree,
        args.workstream,
        args.branch,
        args.audit_base_sha,
        resolved_state,
        args.profile,
        args.profiles_dir,
        args.canonical_root,
        args.allow_same_cwd_pids,
        args.allow_suppressed_routing,
    )
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.json_output:
        Path(args.json_output).write_text(text + "\n", encoding="utf-8")
    print(result["verdict"])
    for failure in result["failures"]:
        print(f"BOOTSTRAP_FAIL: {failure}", file=sys.stderr)
    for note in result["notes"]:
        print(f"BOOTSTRAP_NOTE: {note}")
    return 0 if result["verdict"] == "BOOTSTRAP_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
