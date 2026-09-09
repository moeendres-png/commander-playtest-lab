"""Fail-closed source-lock verification for Foundry workstreams.

Compares live Git reality against an expected lock. Exits 0 only when every
checked identity matches. Any mismatch prints a REASON and exits nonzero.
Never mutates the repository.
"""

from __future__ import annotations

import argparse
import subprocess
import sys


def _git(args: list[str], cwd: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def verify(
    repo: str,
    branch: str,
    audit_base_sha: str,
    workdir: str,
    expected_head: str | None = None,
    allow_dirty: bool = False,
) -> list[str]:
    """Return a list of mismatch reasons; empty means the lock holds."""
    reasons: list[str] = []
    try:
        actual_remote = _git(["config", "--get", "remote.origin.url"], workdir)
    except RuntimeError as exc:
        return [f"cannot read origin url: {exc}"]
    if repo not in actual_remote:
        reasons.append(f"repository mismatch: expected {repo!r} in {actual_remote!r}")
    try:
        actual_branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], workdir)
    except RuntimeError as exc:
        return [*reasons, f"cannot read branch: {exc}"]
    if actual_branch != branch:
        reasons.append(f"branch mismatch: expected {branch!r}, found {actual_branch!r}")
    try:
        actual_head = _git(["rev-parse", "HEAD"], workdir)
    except RuntimeError as exc:
        return [*reasons, f"cannot read HEAD: {exc}"]
    if expected_head is not None and actual_head != expected_head:
        reasons.append(f"HEAD mismatch: expected {expected_head}, found {actual_head}")
    try:
        merge_base = _git(["merge-base", "HEAD", audit_base_sha], workdir)
    except RuntimeError:
        reasons.append(f"audit base {audit_base_sha} unreachable from HEAD {actual_head}")
    else:
        if merge_base != audit_base_sha:
            reasons.append(f"audit base {audit_base_sha} is not an ancestor of HEAD {actual_head}")
    try:
        porcelain = _git(["status", "--porcelain"], workdir)
    except RuntimeError as exc:
        reasons.append(f"cannot read status: {exc}")
    else:
        if porcelain and not allow_dirty:
            reasons.append(f"dirty worktree ({len(porcelain.splitlines())} changed entries)")
    try:
        _git(["rev-parse", "--show-toplevel"], workdir)
    except RuntimeError as exc:
        reasons.append(f"cannot read worktree root: {exc}")
    return reasons


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a Foundry source lock (fail closed).")
    parser.add_argument("--repo", required=True, help="Expected repository slug fragment.")
    parser.add_argument("--branch", required=True, help="Expected branch name.")
    parser.add_argument("--audit-base-sha", required=True, help="Expected base SHA (ancestor).")
    parser.add_argument("--expected-head", default=None, help="Exact expected HEAD SHA.")
    parser.add_argument("--workdir", default=".", help="Worktree to verify.")
    parser.add_argument("--allow-dirty", action="store_true", help="Do not fail on dirty tree.")
    args = parser.parse_args(argv)
    reasons = verify(
        args.repo,
        args.branch,
        args.audit_base_sha,
        args.workdir,
        args.expected_head,
        args.allow_dirty,
    )
    if reasons:
        for reason in reasons:
            print(f"LOCK_FAIL: {reason}", file=sys.stderr)
        return 1
    print(f"LOCK_OK: {args.branch}@{_git(['rev-parse', 'HEAD'], args.workdir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
