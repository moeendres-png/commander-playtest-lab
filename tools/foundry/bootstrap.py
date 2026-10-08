"""Unified deterministic bootstrap gate for Foundry workstreams.

Runs source-lock, duplicate-writer, state, writer-lock/CWD, and policy-drift
checks in one place so the model never hand-interprets fifteen shell outputs.
Prints BOOTSTRAP_PASS or the first fail-closed reason; machine-readable detail
goes to --json-output.

Read-only, except --init-state which writes a minimal schema-2.0 state
document (validated_head=null, placeholder objective the owner must replace).

Explicit-state authority (ROOT_STATE_SEMANTICS): --state is mandatory.
There is no implicit active repository-root state; the gate never falls
back to <worktree>/.foundry/WORKSTREAM_STATE.yaml. --init-state writes
only to the explicitly supplied --state path.

Exit codes: 0 BOOTSTRAP_PASS (notes allowed); 1 BOOTSTRAP_FAIL.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import drift_check as drift_mod
import reference_roots as reference_mod
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


_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def init_state(
    worktree: str,
    workstream: str,
    branch: str,
    audit_base_sha: str,
    audit_base_tree: str,
    repository: str,
) -> dict:
    """Build a minimal schema-2.0 state document.

    ``repository`` is mandatory: an empty or malformed owner/name slug would
    leave external review evidence unbound to any repository, so it fails
    closed here instead of defaulting to "any repository".
    """
    if not isinstance(repository, str) or not _REPOSITORY_RE.match(repository.strip()):
        raise ValueError(f"repository must be an explicit owner/name slug, got {repository!r}")
    try:
        live_head = _git(["rev-parse", "HEAD"], worktree)
    except RuntimeError as exc:
        raise ValueError(f"cannot read HEAD for state init: {exc}") from exc
    return {
        "schema_version": "2.0",
        "repository": repository.strip(),
        "worktree": os.path.realpath(os.path.abspath(worktree)),
        "branch": branch,
        "audit_base_sha": audit_base_sha,
        "audit_base_tree": audit_base_tree,
        "state_written_against_head": live_head,
        "validated_head": None,
        "validated_tree": None,
        "objective": f"BOOTSTRAP PLACEHOLDER for {workstream} (replace with contract objective)",
        "in_scope": [],
        "out_of_scope": [],
        "ownership": workstream,
        "status": "ACTIVE",
        # Fail-safe policy opt-in for every new workstream: MATERIAL by default
        # requires a fresh-context read-only Space Bunny PASS on the exact
        # validated SHA/tree before PR_READY/COMPLETE. A genuinely
        # generated-state/document-only closeout may switch to NON_MATERIAL,
        # which is still verified against the Git change set by review_gate.py.
        "materiality": "MATERIAL",
        "cross_executor_review": {
            "required": True,
            "logical_profile": "space-bunny",
            "implementation_executor": "deepseek",
            "review_executor": "space-bunny",
            "reviewed_sha": None,
            "reviewed_tree": None,
            "verdict": "UNKNOWN",
            "review_record_path": None,
        },
        "exact_next_action": "Replace placeholder objective/scope, then proceed.",
    }


def parse_worktree_state(spec: str) -> tuple[str, str]:
    """Shared WORKTREE=STATE semantics (canonical in worktree_inventory).

    Kept as a delegate so existing importers keep working; no second
    implementation lives here.
    """
    return inventory_mod.parse_worktree_state(spec)


def bootstrap(
    worktree: str,
    workstream: str,
    branch: str,
    audit_base_sha: str,
    state_path: str,
    profile_name: str,
    profiles_dir: str = DEFAULT_PROFILES_DIR,
    canonical_root: str = "",
    allow_same_cwd_pids: bool = False,
    allow_suppressed_routing: bool = False,
    references: list[dict] | None = None,
    worktree_states: dict[str, str] | None = None,
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

    # 2. duplicate writer across worktrees of this repo. Ownership for each
    # worktree comes only from the explicit state map (launcher auto-supplies
    # its own worktree pair; siblings are operator-declared); otherwise
    # UNKNOWN. No conventional-path fallback exists.
    try:
        entries = inventory_mod.inventory(canonical, worktree_states)
        conflicts = inventory_mod.find_duplicate_writers(entries)
    except RuntimeError as exc:
        failures.append(f"worktree inventory: {exc}")
        conflicts = []
    if conflicts:
        failures.append(f"duplicate writer: {conflicts[0]}")

    # 3. state file. Explicit-state authority: no silent fallback to an
    # implicit worktree-root state path. A missing --state fails closed.
    if not state_path:
        failures.append("explicit --state is required (no implicit active repository-root state)")
        resolved_state = ""
        data = None
    else:
        resolved_state = state_path
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
                # Repository identity drives which GitHub evidence a review can
                # cite; a blank or foreign state repository must not silently
                # mean "accept any repository".
                state_repository = str(data.get("repository") or "").strip()
                if not state_repository:
                    failures.append(
                        "state repository is missing: refusing to accept any repository"
                    )
                elif not slug:
                    failures.append(
                        "profile has no repo_slug: refusing to accept any state repository"
                    )
                elif state_repository != slug:
                    failures.append(
                        f"state repository {state_repository!r} != profile repository {slug!r}"
                    )
                try:
                    state_wt = os.path.realpath(str(data.get("worktree", "")))
                except (TypeError, ValueError):
                    state_wt = ""
                if state_wt != canonical:
                    failures.append("state worktree does not match this worktree")
                ownership = str(data.get("ownership", ""))
                if not ownership or ownership == "UNKNOWN":
                    notes.append("state ownership unknown (proceeding; push will refuse)")
                elif ownership != workstream:
                    failures.append(
                        f"state ownership {ownership!r} != workstream {workstream!r} "
                        "(explicit state conflict: refusing to run under another "
                        "workstream's state)"
                    )

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

    # 6. declared reference roots (read-only verification, fail closed).
    verified_refs: list[dict] = []
    for ref in references or []:
        reasons = reference_mod.verify(ref)
        if reasons:
            failures.append(f"reference {ref.get('label', '?')!r}: {reasons[0]}")
        else:
            verified_refs.append(ref)
    if verified_refs:
        notes.append(
            "verified reference roots: "
            + ", ".join(f"{r['label']}={r['root']}" for r in verified_refs)
        )

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
        "references": verified_refs,
    }


def _parse_cli_references(raws: list[str]) -> list[dict]:
    parsed: list[dict] = []
    for raw in raws:
        try:
            parsed.append(reference_mod.parse_spec(raw))
        except reference_mod.ReferenceError as exc:
            raise SystemExit(f"BOOTSTRAP_FAIL: reference: {exc}") from exc
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Foundry unified bootstrap gate.")
    parser.add_argument("--worktree", required=True)
    parser.add_argument("--workstream", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--audit-base-sha", required=True)
    parser.add_argument(
        "--state",
        required=True,
        help="Explicit workstream state file (mandatory; no implicit fallback).",
    )
    parser.add_argument("--profile", required=True)
    parser.add_argument("--profiles-dir", default=DEFAULT_PROFILES_DIR)
    parser.add_argument("--canonical-root", default="")
    parser.add_argument("--allow-same-cwd-pids", action="store_true")
    parser.add_argument("--allow-suppressed-routing", action="store_true")
    parser.add_argument("--json-output", default=None)
    parser.add_argument("--audit-base-tree", default="0" * 40)
    parser.add_argument(
        "--reference",
        action="append",
        default=[],
        help="Declared read-only reference root as JSON (repeatable).",
    )
    parser.add_argument(
        "--worktree-state",
        action="append",
        default=[],
        help="Explicit ownership authority as WORKTREE=STATE (repeatable).",
    )
    parser.add_argument(
        "--init-state",
        action="store_true",
        help="Write a minimal 2.0 state file when none exists, then continue.",
    )
    args = parser.parse_args(argv)
    resolved_state = args.state
    try:
        worktree_states = inventory_mod.parse_worktree_state_specs(args.worktree_state)
    except ValueError as exc:
        print(f"BOOTSTRAP_FAIL: {exc}", file=sys.stderr)
        return 1
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
        try:
            state_mod.write_state(
                resolved_state,
                doc,
                workdir=os.path.realpath(os.path.abspath(args.worktree)),
            )
        except state_mod.StateWriteError as exc:
            print(f"BOOTSTRAP_FAIL: cannot init state: {exc}", file=sys.stderr)
            return 1
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
        _parse_cli_references(args.reference),
        worktree_states,
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
