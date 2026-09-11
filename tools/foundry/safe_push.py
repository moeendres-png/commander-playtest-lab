"""Narrow safe checkpoint-push path (SAFE_WRAPPED).

The ONLY authorized remote-write path for Foundry workstreams. Narrow API by
construction: the caller supplies identities, never git flags or refspecs. No
force, no delete, no tags, no multi-ref, no caller-supplied bypass flags exist.

Fail-closed preconditions, in order:

1. state file parses and validates (schema 2.0 required);
2. expected branch is not protected (main/master/HEAD) and is ref-format clean
   (rejects `-`, `:`, whitespace, `..`, `~^:?*[` injection shapes);
3. remote identity contains the expected slug (raw URLs never printed);
4. current branch triple-matches (live == expected == state), no detached HEAD;
5. exactly one worktree owns the branch and it is this worktree;
6. writer lock is currently HELD (flock probe must fail) by a recorded holder
   whose PID is an ancestor of this process (launcher holds across the child);
7. state ownership/branch/worktree match; validated_head non-null and ancestry
   clean (inside source lock, ancestor of live HEAD);
8. tree clean (no partial pushes);
9. audit_base_sha is an ancestor of HEAD (never leaves the source lock);
10. remote ref state: absent -> creation only when audit_base descends from
    (or equals) the creation anchor: by default the remote main/master HEAD;
    when --expected-audit-base-ref names an exact pre-existing remote source
    branch, the anchor is that branch's tip instead (audit_base must be equal
    to or an ancestor of it; the source branch must exist as exactly
    refs/heads/<name> on the already-validated expected remote); present ->
    fast-forward only (remote SHA must be a strict ancestor of HEAD);
    equal -> UP_TO_DATE no-op success;
11. push exactly ``HEAD:refs/heads/<branch>`` to the named remote.

Exit codes: 0 PUSHED / UP_TO_DATE / DRY_RUN_OK; 2 PUSH_REJECT with reason.
Nothing credential-bearing is ever printed (remote URLs redacted, env untouched).
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fcntl

import state as state_mod
import writer_lock as writer_lock_mod

PROTECTED_BRANCHES = {"main", "master", "HEAD"}
REJECT = 2


def _run(args: list[str], cwd: str) -> str:
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} failed: {proc.stderr.strip()[:300]}")
    return proc.stdout.strip()


def _redact_url(url: str) -> str:
    """Strip userinfo (credentials) for any diagnostic output."""
    return re.sub(r"^(https?://)[^/@]+@", r"\1<redacted>@", url)


class _PushReject(Exception):
    """Fail-closed precondition failure (prints as PUSH_REJECT, exit 2)."""


def _emit_push_metric(
    metrics_path: str | None, task_id: str, source_sha: str | None, result: str, reason: str | None
) -> None:
    if not metrics_path:
        return
    import metrics as metrics_mod

    try:
        metrics_mod.record(
            metrics_path,
            _provenance={
                "task_id": "AUTOCAPTURED",
                "task_class": "AUTOCAPTURED",
                "source_sha": "AUTOCAPTURED",
                "push_result": "AUTOCAPTURED",
                "reject_reason": "AUTOCAPTURED",
            },
            task_id=task_id,
            task_class="checkpoint-push",
            source_sha=source_sha,
            push_result=result,
            reject_reason=reason,
        )
    except OSError as exc:
        print(f"PUSH_WARN: metrics not recorded: {exc}", file=sys.stderr)


def _valid_branch_name(branch: str, workdir: str) -> str | None:
    if branch in PROTECTED_BRANCHES or branch.startswith("refs/"):
        return f"protected ref {branch!r}"
    if branch.startswith("-") or branch.startswith("."):
        return f"leading dash/dot in {branch!r}"
    if re.search(r"\s|:|\.\.|[~^:?*\[\\]|\.\.|@{", branch):
        return f"unsafe characters in {branch!r}"
    proc = subprocess.run(
        ["git", "check-ref-format", "--branch", branch],
        cwd=workdir,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return f"git check-ref-format rejects {branch!r}"
    return None


def _valid_source_ref_name(branch: str, target_branch: str, workdir: str) -> str | None:
    """Strict format gate for --expected-audit-base-ref (source identity only).

    Source-reference semantics differ deliberately from push-destination
    semantics: a legitimate historical source branch is identity evidence, not
    a push target, so the protected-branch ban does NOT apply here. Everything
    else is strict: no empty names, no HEAD, no refs/ prefixes, no SHA-like
    pseudo-refs, no tag-like or refspec-like shapes, and git check-ref-format
    must accept the name (this also excludes ls-remote wildcard characters,
    so the remote lookup below is always a literal exact-ref query).
    """
    if not branch or not branch.strip():
        return "empty expected audit-base ref"
    if branch == target_branch:
        return f"source ref {branch!r} must not equal the push target branch"
    if branch == "HEAD" or branch.startswith("refs/"):
        return f"non-branch ref {branch!r}"
    if branch.startswith("-") or branch.startswith("."):
        return f"leading dash/dot in {branch!r}"
    if re.search(r"\s|:|\.\.|[~^:?*\[\\]|\.\.|@{", branch):
        return f"unsafe characters in {branch!r}"
    if re.fullmatch(r"[0-9a-fA-F]{40}", branch):
        return f"SHA-like pseudo-ref {branch!r} (name an exact remote branch)"
    proc = subprocess.run(
        ["git", "check-ref-format", "--branch", branch],
        cwd=workdir,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return f"git check-ref-format rejects {branch!r}"
    return None


def _resolve_expected_remote_base(
    canonical: str,
    remote: str,
    source_ref: str,
    target_branch: str,
    audit_base: str,
) -> str:
    """Resolve the tip of an explicitly named remote source branch (read-only).

    Uses only ``git ls-remote <remote> refs/heads/<source_ref>``: no wildcard
    search, no branch enumeration. Returns the tip SHA when the ref exists as
    exactly one remote ref AND audit_base is equal to or an ancestor of that
    tip (proving the source lock is already part of trusted remote history).
    Raises _PushReject otherwise. Never writes.
    """
    bad = _valid_source_ref_name(source_ref, target_branch, canonical)
    if bad:
        raise _PushReject(bad)
    want = f"refs/heads/{source_ref}"
    try:
        out = _run(["git", "ls-remote", remote, want], canonical)
    except RuntimeError as exc:
        raise _PushReject(f"cannot resolve source ref {source_ref!r}: {exc}") from exc
    lines = [line for line in out.splitlines() if line.strip()]
    if len(lines) != 1:
        raise _PushReject(
            f"source ref {source_ref!r} absent on remote {remote!r} "
            "(name the exact pre-existing remote source branch)"
        )
    fields = lines[0].split()
    if len(fields) != 2 or fields[1] != want:
        raise _PushReject(f"source ref {source_ref!r} resolved ambiguously (refusing)")
    tip = fields[0]
    proved = subprocess.run(
        ["git", "merge-base", "--is-ancestor", audit_base, tip],
        cwd=canonical,
        capture_output=True,
        check=False,
    )
    if audit_base != tip and proved.returncode != 0:
        raise _PushReject(
            f"source ref {source_ref!r} does not contain the audit base "
            "(unrelated remote lineage; refusing creation)"
        )
    return tip


def _ancestor_pids() -> set[int]:
    """PIDs on this process's parent chain (Linux /proc)."""
    chain: set[int] = set()
    try:
        pid = os.getpid()
        while True:
            with open(f"/proc/{pid}/stat", encoding="utf-8") as handle:
                tail = handle.read().rsplit(")", 1)[1].split()
            ppid = int(tail[1])
            chain.add(ppid)
            if ppid <= 1:
                break
            pid = ppid
    except (OSError, ValueError, IndexError):
        pass
    return chain


def _single_owner(workdir: str, branch: str) -> str | None:
    """None when exactly this worktree owns the branch; else a reason."""
    try:
        raw = _run(["git", "worktree", "list", "--porcelain"], workdir)
    except RuntimeError as exc:
        return f"cannot list worktrees: {exc}"
    owners = []
    path = head_branch = None
    for line in raw.splitlines():
        if line.startswith("worktree "):
            if path is not None:
                owners.append((path, head_branch))
            path, head_branch = line[len("worktree ") :], None
        elif line.startswith("branch "):
            head_branch = line[len("branch ") :]
    if path is not None:
        owners.append((path, head_branch))
    want = f"refs/heads/{branch}"
    matches = [p for p, b in owners if b == want]
    if len(matches) != 1:
        return f"branch {branch!r} owned by {len(matches)} worktrees (want exactly 1)"
    if os.path.realpath(matches[0]) != os.path.realpath(workdir):
        return f"branch {branch!r} owned by {matches[0]!r}, not this worktree"
    return None


def _lock_held_by_ancestor(canonical_worktree: str) -> str | None:
    """None when a live-held lock names an ancestor PID; else a reason."""
    lock_path = writer_lock_mod.lock_path_for(canonical_worktree)
    try:
        fd = os.open(lock_path, os.O_RDONLY)
    except FileNotFoundError:
        return "no writer lock (run inside the validated launcher)"
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            held = True
        else:
            fcntl.flock(fd, fcntl.LOCK_UN)
            held = False
    finally:
        os.close(fd)
    if not held:
        return "writer lock not held (stale or missing holder; run inside the launcher)"
    holder = writer_lock_mod.read_holder(lock_path) or {}
    pid = holder.get("pid")
    if not isinstance(pid, int):
        return "writer lock holder metadata invalid"
    if pid not in _ancestor_pids():
        return (
            f"writer lock held by pid {pid} which is not an ancestor of this "
            "process (push only from inside the lock-holding launcher)"
        )
    return None


def _decide_push(
    worktree: str,
    expected_branch: str,
    state_path: str,
    remote: str,
    expected_slug: str,
    dry_run: bool,
    ctx: dict,
    expected_audit_base_ref: str | None = None,
) -> str:
    """Run all gates; perform the push. Returns 'RESULT branch@sha'; raises _PushReject."""
    canonical = os.path.realpath(os.path.abspath(worktree))

    # 1. state parses + validates (2.0 required for ancestry semantics).
    try:
        with open(state_path, encoding="utf-8") as handle:
            import yaml

            data = yaml.safe_load(handle)
    except OSError as exc:
        raise _PushReject(f"cannot read state: {exc}") from exc
    if not isinstance(data, dict):
        raise _PushReject("state is not a mapping")
    if str(data.get("schema_version", "")) != "2.0":
        raise _PushReject("state schema 2.0 required (migrate first)")
    errors = state_mod.validate(data)
    if errors:
        raise _PushReject(f"invalid state: {errors[0]}")

    # 2. branch name safety.
    bad = _valid_branch_name(expected_branch, canonical)
    if bad:
        raise _PushReject(bad)

    # 3. remote identity.
    try:
        url = _run(["git", "config", "--get", f"remote.{remote}.url"], canonical)
    except RuntimeError:
        raise _PushReject(f"remote {remote!r} has no URL") from None
    if expected_slug not in url:
        raise _PushReject(
            f"WRONG_REMOTE: remote {remote!r} identity {_redact_url(url)!r} lacks expected slug"
        )

    # 4. triple match + no detached HEAD.
    try:
        live_branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], canonical)
        live_head = _run(["git", "rev-parse", "HEAD"], canonical)
    except RuntimeError as exc:
        raise _PushReject(f"cannot read live branch/HEAD: {exc}") from exc
    ctx["source_sha"] = live_head
    if live_branch == "HEAD":
        raise _PushReject("detached HEAD (push requires the workstream branch)")
    state_branch = str(data.get("branch", ""))
    if not (live_branch == expected_branch == state_branch):
        raise _PushReject(
            f"branch mismatch: live={live_branch!r} expected={expected_branch!r} "
            f"state={state_branch!r}"
        )

    # 5. single-worktree ownership.
    owner_problem = _single_owner(canonical, expected_branch)
    if owner_problem:
        raise _PushReject(owner_problem)

    # 6. ancestor-held writer lock.
    lock_problem = _lock_held_by_ancestor(canonical)
    if lock_problem:
        raise _PushReject(lock_problem)

    # 7. state coherence + validation credit.
    if (
        str(data.get("worktree", "")) != canonical
        and os.path.realpath(str(data.get("worktree", "."))) != canonical
    ):
        raise _PushReject("state worktree does not match this worktree")
    ownership = str(data.get("ownership", ""))
    if not ownership or ownership == "UNKNOWN":
        raise _PushReject("state ownership missing (unknown owner cannot push)")
    ctx["task_id"] = ownership
    validated = data.get("validated_head")
    if validated is None:
        raise _PushReject("validated_head is null (validate before checkpoint push)")
    ancestry = state_mod.check_validated_ancestry(state_path, canonical)
    fatal = [
        n
        for n in ancestry
        if n.startswith("VALIDATED_OUTSIDE_LOCK") or n.startswith("VALIDATED_REWRITTEN")
    ]
    if fatal:
        raise _PushReject(fatal[0])

    # 8. clean tree.
    try:
        porcelain = _run(["git", "status", "--porcelain"], canonical)
    except RuntimeError as exc:
        raise _PushReject(f"cannot read status: {exc}") from exc
    if porcelain:
        raise _PushReject(f"dirty worktree ({len(porcelain.splitlines())} entries; commit first)")

    # 9. source-lock ancestry.
    base = str(data.get("audit_base_sha", ""))
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", base, live_head],
        cwd=canonical,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise _PushReject("audit base is not an ancestor of HEAD (left the source lock)")

    # 10. remote ref state.
    try:
        ls = _run(["git", "ls-remote", remote, f"refs/heads/{expected_branch}"], canonical)
    except RuntimeError as exc:
        raise _PushReject(f"cannot read remote ref state: {exc}") from exc
    remote_sha = ls.split()[0] if ls else None
    if remote_sha == live_head:
        return f"UP_TO_DATE {expected_branch}@{live_head[:12]}"
    if remote_sha is not None:
        ahead = subprocess.run(
            ["git", "merge-base", "--is-ancestor", remote_sha, live_head],
            cwd=canonical,
            capture_output=True,
            check=False,
        )
        if ahead.returncode != 0:
            raise _PushReject(
                "non-fast-forward (remote has commits outside this history; "
                "never force-push: reconcile by hand outside the launcher)"
            )
    else:
        if expected_audit_base_ref is not None:
            # Explicit non-main lineage: the caller names one exact
            # pre-existing remote source branch that must already contain the
            # audit base. Identity evidence only; never a refspec.
            _resolve_expected_remote_base(
                canonical, remote, expected_audit_base_ref, expected_branch, base
            )
            # Proven: audit_base is reachable from the named remote source
            # branch, so creation from this lineage is permitted.
        else:
            remote_main = None
            for candidate in ("refs/heads/main", "refs/heads/master"):
                try:
                    out = _run(["git", "ls-remote", remote, candidate], canonical)
                except RuntimeError as exc:
                    raise _PushReject(
                        f"cannot resolve remote HEAD for creation gate: {exc}"
                    ) from exc
                if out:
                    remote_main = out.split()[0]
                    break
            if remote_main is None:
                raise _PushReject(
                    "cannot resolve remote main/master for creation gate "
                    "(unknown remote state; refusing)"
                )
            created = subprocess.run(
                ["git", "merge-base", "--is-ancestor", base, remote_main],
                cwd=canonical,
                capture_output=True,
                check=False,
            )
            if base != remote_main and created.returncode != 0:
                raise _PushReject(
                    "branch creation refused: audit base is outside the remote history"
                )

    # 11. the single authorized write: exact refspec, no flags by construction.
    if dry_run:
        return f"DRY_RUN_OK {expected_branch}@{live_head[:12]}"
    push_env = dict(os.environ)
    push_env["FOUNDRY_SAFE_PUSH"] = "1"  # launcher-installed pre-push hook marker
    proc = subprocess.run(
        ["git", "push", remote, f"HEAD:refs/heads/{expected_branch}"],
        cwd=canonical,
        env=push_env,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise _PushReject(f"git push refused: {(proc.stderr.strip() or proc.stdout.strip())[:300]}")
    return f"PUSHED {expected_branch}@{live_head[:12]}"


def safe_push(
    worktree: str,
    expected_branch: str,
    state_path: str,
    remote: str = "origin",
    expected_slug: str = "moeendres-png/commander-playtest-lab",
    dry_run: bool = False,
    metrics_path: str | None = None,
    expected_audit_base_ref: str | None = None,
) -> int:
    """Narrow safe checkpoint push with fail-closed gates and metric emission."""
    ctx: dict = {"task_id": "UNKNOWN", "source_sha": None}
    try:
        outcome = _decide_push(
            worktree,
            expected_branch,
            state_path,
            remote,
            expected_slug,
            dry_run,
            ctx,
            expected_audit_base_ref,
        )
    except _PushReject as rej:
        reason = str(rej)
        print(f"PUSH_REJECT: {reason}", file=sys.stderr)
        _emit_push_metric(metrics_path, ctx["task_id"], ctx["source_sha"], "REJECTED", reason)
        return REJECT
    _emit_push_metric(metrics_path, ctx["task_id"], ctx["source_sha"], outcome.split()[0], None)
    print(f"SAFE_PUSH_OK: {outcome}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Narrow safe checkpoint push.")
    parser.add_argument("--worktree", required=True)
    parser.add_argument("--expected-branch", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--remote", default="origin")
    parser.add_argument(
        "--expected-slug",
        default="moeendres-png/commander-playtest-lab",
        help="Trust root for the remote URL (substring match).",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--metrics", default=None, help="Append AUTOCAPTURED push record here.")
    parser.add_argument(
        "--expected-audit-base-ref",
        default=None,
        help=(
            "Exact pre-existing remote source branch proving the audit base is "
            "already part of trusted remote history (e.g. "
            "'foundry/ws39-commander-history-state-restore'). Only consulted "
            "when the target branch does not yet exist on the remote: the "
            "audit base must be equal to or an ancestor of this branch's tip. "
            "Without it, creation stays anchored to remote main/master. "
            "Branch name only: no refspecs, tags, SHAs, or wildcards."
        ),
    )
    args = parser.parse_args(argv)
    return safe_push(
        args.worktree,
        args.expected_branch,
        args.state,
        args.remote,
        args.expected_slug,
        args.dry_run,
        args.metrics,
        args.expected_audit_base_ref,
    )


if __name__ == "__main__":
    raise SystemExit(main())
