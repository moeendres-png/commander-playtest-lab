"""Fail-closed source-lock verification for Foundry workstreams.

Compares live Git reality against an expected lock. Exits 0 only when every
checked identity matches. Any mismatch prints a REASON and exits nonzero.
Never mutates the repository.

Error taxonomy (distinct, never conflated):
- WRONG_LOCAL_REPOSITORY: the local checkout's ``remote.origin.url`` is not
  the canonical ``moeendres-png/commander-playtest-lab`` slug. Stop here;
  never infer canonical-remote ref state from this checkout.
- REQUESTED_REF_ABSENT_FROM_CANONICAL_REMOTE: the local remote IS canonical
  (and fresh-fetched where appropriate) but the requested ref is absent from
  ``origin`` (via ``git ls-remote origin <ref>`` or unresolvable
  ``origin/<ref>``).
"""

from __future__ import annotations

import argparse
import subprocess
import sys

CANONICAL_SLUG = "moeendres-png/commander-playtest-lab"


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


def remote_identity(workdir: str) -> str:
    """Return the full ``remote.origin.url`` or raise."""
    return _git(["config", "--get", "remote.origin.url"], workdir)


def is_canonical_remote(remote_url: str, expected_slug: str = CANONICAL_SLUG) -> bool:
    """True only when the full owner/repo slug is present in the URL."""
    return expected_slug in remote_url


def check_canonical_ref(ref: str, workdir: str, remote: str = "origin") -> tuple[bool, str]:
    """Check a ref against the canonical remote without mutating.

    Returns (present, detail). Uses ``git ls-remote`` first, falling back to
    local ``origin/<ref>`` resolution. Call only after remote identity is
    verified canonical; otherwise the result is meaningless.
    """
    proc = subprocess.run(
        ["git", "ls-remote", remote, ref],
        cwd=workdir,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode == 0:
        if proc.stdout.strip():
            return True, proc.stdout.strip().splitlines()[0]
        return False, f"ref {ref!r} absent from {remote} (empty ls-remote)"
    try:
        resolved = _git(["rev-parse", "--verify", f"{remote}/{ref}"], workdir)
    except RuntimeError as exc:
        return False, f"cannot resolve {remote}/{ref}: {exc}"
    return True, resolved


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
        actual_remote = remote_identity(workdir)
    except RuntimeError as exc:
        return [f"cannot read origin url: {exc}"]
    if "/" in repo:
        # Full-slug mode: require the exact owner/repo slug.
        if not is_canonical_remote(actual_remote, repo):
            reasons.append(f"WRONG_LOCAL_REPOSITORY: expected slug {repo!r} in {actual_remote!r}")
    elif repo not in actual_remote:
        reasons.append(f"repository mismatch: expected {repo!r} in {actual_remote!r}")
    # Back-compat guard: a bare fragment must never mask a wrong owner.
    # If the caller passed only a fragment but the URL carries a different
    # owner for the same repo name, still fail closed.
    if (
        "/" not in repo
        and "commander-playtest-lab" in actual_remote
        and CANONICAL_SLUG not in actual_remote
    ):
        reasons.append(
            f"WRONG_LOCAL_REPOSITORY: remote {actual_remote!r} is not canonical {CANONICAL_SLUG!r}"
        )
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
    parser.add_argument(
        "--repo",
        required=True,
        help="Expected repository slug. Prefer the full canonical slug "
        "'moeendres-png/commander-playtest-lab'; a bare fragment is legacy.",
    )
    parser.add_argument("--branch", required=True, help="Expected branch name.")
    parser.add_argument("--audit-base-sha", required=True, help="Expected base SHA (ancestor).")
    parser.add_argument("--expected-head", default=None, help="Exact expected HEAD SHA.")
    parser.add_argument("--workdir", default=".", help="Worktree to verify.")
    parser.add_argument("--allow-dirty", action="store_true", help="Do not fail on dirty tree.")
    parser.add_argument(
        "--check-remote-ref",
        default=None,
        help="Optional ref to check against the canonical remote via ls-remote "
        "(only meaningful after remote identity passes; absence is "
        "REQUESTED_REF_ABSENT_FROM_CANONICAL_REMOTE, never inferred from an "
        "unrelated clone).",
    )
    args = parser.parse_args(argv)
    reasons = verify(
        args.repo,
        args.branch,
        args.audit_base_sha,
        args.workdir,
        args.expected_head,
        args.allow_dirty,
    )
    if args.check_remote_ref and not any("WRONG_LOCAL_REPOSITORY" in r for r in reasons):
        try:
            actual_remote = remote_identity(args.workdir)
        except RuntimeError as exc:
            reasons.append(f"cannot read origin url for ref check: {exc}")
        else:
            if is_canonical_remote(actual_remote, CANONICAL_SLUG):
                present, detail = check_canonical_ref(args.check_remote_ref, args.workdir)
                if not present:
                    reasons.append(
                        "REQUESTED_REF_ABSENT_FROM_CANONICAL_REMOTE: "
                        f"{args.check_remote_ref!r}: {detail}"
                    )
            else:
                reasons.append(
                    "WRONG_LOCAL_REPOSITORY: refusing remote-ref check from "
                    f"non-canonical remote {actual_remote!r}"
                )
    if reasons:
        for reason in reasons:
            print(f"LOCK_FAIL: {reason}", file=sys.stderr)
        return 1
    print(f"LOCK_OK: {args.branch}@{_git(['rev-parse', 'HEAD'], args.workdir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
