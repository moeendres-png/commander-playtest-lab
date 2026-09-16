"""Fail-closed source-lock verification for Foundry workstreams.

Compares live Git reality against an expected lock. Exits 0 only when every
checked identity matches. Any mismatch prints a REASON and exits nonzero.
Never mutates the repository.

Error taxonomy (distinct, never conflated):
- WRONG_LOCAL_REPOSITORY: the local checkout's ``remote.origin.url`` is not
  the canonical ``moeendres-png/commander-playtest-lab`` slug. Stop here;
  never infer canonical-remote ref state from this checkout.
- Ambiguous identity (zero or two-or-more ``remote.origin.url`` records,
  including blank or whitespace-only extras) fails closed: ``verify()``
  reports the lock unreadable and ``check_canonical_ref()`` reports
  ``REMOTE_REF_UNKNOWN``. Record parsing is NUL-delimited so no second
  record can hide behind string stripping.
- EFFECTIVE_URL_REWRITE: an active ``url.*.insteadOf`` rewrite (local,
  global, or environment-provided) — or unreadable rewrite configuration —
  means the effective transport target may differ from the literal
  ``remote.origin.url``. The primary ``verify()`` gate fails closed without
  any remote probe; ``bootstrap.py`` inherits this guard through ``verify()``.
- REQUESTED_REF_ABSENT_FROM_CANONICAL_REMOTE: the local remote IS canonical
  but a successful live query reports no matching exact ref.
- REMOTE_REF_UNKNOWN: transport, execution, or response validation failed.
  Local remote-tracking refs are never substituted for live evidence.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from urllib.parse import urlsplit

CANONICAL_SLUG = "moeendres-png/commander-playtest-lab"


def _git(args: list[str], cwd: str) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, UnicodeError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("Git evidence unavailable") from exc
    if proc.returncode != 0:
        raise RuntimeError("Git evidence command failed")
    return proc.stdout.strip()


def _git_raw(args: list[str], cwd: str) -> bytes:
    """Raw Git stdout bytes: no decoding, no stripping, no record collapse.

    Identity reads must observe every ``remote.*.url`` record (including
    empty or whitespace-only ones). The text-mode ``_git`` helper strips
    outer whitespace, which collapses a trailing blank record back onto the
    canonical URL; it stays untouched for its single-value callers.
    """
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, UnicodeError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("Git evidence unavailable") from exc
    if proc.returncode != 0:
        raise RuntimeError("Git evidence command failed")
    return proc.stdout


def remote_url_records(workdir: str, remote: str = "origin") -> list[str]:
    """Return every ``remote.<name>.url`` record, order- and emptiness-preserving.

    Uses NUL-delimited ``git config --null --get-all`` so blank,
    whitespace-only, or newline-bearing records survive as distinct entries.
    Raises on missing/unreadable configuration, undecodable bytes, or an
    invalid remote name. Never echoes values: diagnostics carry counts only.
    """
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", remote):
        raise RuntimeError("invalid remote name")
    raw = _git_raw(["config", "--null", "--get-all", f"remote.{remote}.url"], workdir)
    parts = raw.split(b"\x00")
    if parts and parts[-1] == b"":
        parts = parts[:-1]
    try:
        return [part.decode("utf-8") for part in parts]
    except UnicodeDecodeError as exc:
        raise RuntimeError("Git evidence unavailable") from exc


def remote_identity(workdir: str) -> str:
    """Return the single ``remote.origin.url`` record or raise.

    Anything other than exactly one record (zero, or two-or-more including
    blank/whitespace-only extras) is ambiguous identity and raises; callers
    fail closed. A single empty record is returned and rejected downstream
    by ``is_canonical_remote``.
    """
    records = remote_url_records(workdir, "origin")
    if len(records) != 1:
        raise RuntimeError(
            "ambiguous remote identity: expected exactly one remote.origin.url record"
        )
    return records[0]


def is_canonical_remote(remote_url: str, expected_slug: str = CANONICAL_SLUG) -> bool:
    """Exact GitHub identity, accepting HTTPS and standard git-user SSH forms."""
    if not re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+", expected_slug):
        return False
    if any(p in {".", ".."} for p in expected_slug.split("/")):
        return False
    if any(ord(c) <= 32 or ord(c) == 127 for c in remote_url):
        return False
    if remote_url.startswith("git@github.com:"):
        remote_url = "ssh://git@github.com/" + remote_url[len("git@github.com:") :]
    try:
        parsed = urlsplit(remote_url)
        if parsed.hostname != "github.com" or parsed.query or parsed.fragment:
            return False
        if parsed.scheme == "https":
            if parsed.username is not None or parsed.port not in (None, 443):
                return False
        elif parsed.scheme == "ssh":
            if (
                parsed.username != "git"
                or parsed.password is not None
                or parsed.port not in (None, 22)
            ):
                return False
        else:
            return False
    except ValueError:
        return False
    path = parsed.path.removesuffix("/").removeprefix("/")
    path = path.removesuffix(".git")
    return path.casefold() == expected_slug.casefold()


def _no_url_rewrites(workdir: str, env: dict[str, str]) -> bool:
    """Inspect only status, never read config values or credential-bearing keys."""
    proc = subprocess.run(
        ["git", "config", "--name-only", "--get-regexp", r"^url\..*\.insteadof$"],
        cwd=workdir,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        timeout=30,
    )
    return proc.returncode == 1  # 0 means a rewrite exists; other failures are unknown.


def check_canonical_ref(ref: str, workdir: str, remote: str = "origin") -> tuple[bool, str]:
    """Check a ref against the canonical remote without mutating.

    Returns (present, detail). False includes both ABSENT and UNKNOWN, with
    a stable diagnostic prefix distinguishing them. Short names mean branches;
    tags require explicit refs/tags/. No local tracking-ref fallback is allowed.
    Call only after remote identity verification. This does not establish
    workstream inactivity, ownership, or permission to start another writer.
    """
    qualified = ref if ref.startswith("refs/") else f"refs/heads/{ref}"
    if (
        not qualified.startswith(("refs/heads/", "refs/tags/"))
        or not ref
        or ref.startswith("-")
        or any(ord(c) < 33 or ord(c) == 127 or c in "~^:?*[\\" for c in ref)
        or ".." in ref
        or "@{" in ref
        or any(
            not p or p.startswith(".") or p.endswith((".", ".lock")) for p in qualified.split("/")
        )
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", remote)
    ):
        return False, "REMOTE_REF_UNKNOWN: invalid exact branch/tag ref or remote name"
    try:
        env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never")
        urls = remote_url_records(workdir, remote)
        if len(urls) != 1:
            return False, "REMOTE_REF_UNKNOWN: ambiguous remote identity; refusing ref check"
        url = urls[0]
        if not is_canonical_remote(url):
            return False, "REMOTE_REF_UNKNOWN: remote identity is not canonical"
        if not _no_url_rewrites(workdir, env):
            return False, "REMOTE_REF_UNKNOWN: URL rewrite configuration present or unreadable"
        proc = subprocess.run(
            [
                "git",
                "-c",
                "http.followRedirects=false",
                "ls-remote",
                "--exit-code",
                "--refs",
                "--",
                url,
                qualified,
            ],
            cwd=workdir,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
            env=env,
        )
        if not _no_url_rewrites(workdir, env):
            return False, "REMOTE_REF_UNKNOWN: URL rewrite configuration changed or unreadable"
    except (RuntimeError, OSError, UnicodeError, subprocess.TimeoutExpired):
        return (
            False,
            "REMOTE_REF_UNKNOWN: live query unavailable; verify access and retry",
        )
    if proc.returncode == 2 and proc.stdout == "":
        return False, (
            "REQUESTED_REF_ABSENT_FROM_CANONICAL_REMOTE: "
            f"{qualified!r}; absence does not establish local inactivity"
        )
    if proc.returncode != 0:
        return False, "REMOTE_REF_UNKNOWN: live query failed; verify access and retry"
    match = re.fullmatch(r"((?!0{40})[0-9a-f]{40})\t" + re.escape(qualified) + r"\n?", proc.stdout)
    if match is None:
        return (
            False,
            "REMOTE_REF_UNKNOWN: unexpected exact-ref response; inspect remote identity",
        )
    return True, f"{match[1]}\t{qualified}"


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
    # Preserve the documented CPL legacy name, never arbitrary fragments.
    expected_slug = CANONICAL_SLUG if repo == "commander-playtest-lab" else repo
    if not is_canonical_remote(actual_remote, expected_slug):
        return ["WRONG_LOCAL_REPOSITORY: origin does not match the exact requested identity"]
    # Primary-gate rewrite guard (WS239 P1 fix): a canonical literal URL
    # proves nothing while an active url.*.insteadOf rewrite (local, global,
    # or environment-provided) redirects effective transport elsewhere. The
    # no-probe verify()/bootstrap path must fail closed here, not only the
    # optional check_canonical_ref() probe. Inspect rewrite presence only
    # (never config values); present-or-unreadable fails closed.
    try:
        rewrites_clean = _no_url_rewrites(
            workdir, dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never")
        )
    except (OSError, subprocess.TimeoutExpired):
        rewrites_clean = False
    if not rewrites_clean:
        reasons.append(
            "EFFECTIVE_URL_REWRITE: Git URL rewrite configuration present or "
            "unreadable; primary identity cannot PASS"
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
        help="Optional exact branch (short name) or refs/heads/... or refs/tags/... "
        "to check against the canonical remote via ls-remote "
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
    if args.check_remote_ref is not None and not reasons:
        try:
            actual_remote = remote_identity(args.workdir)
        except RuntimeError as exc:
            reasons.append(f"cannot read origin url for ref check: {exc}")
        else:
            if is_canonical_remote(actual_remote, CANONICAL_SLUG):
                present, detail = check_canonical_ref(args.check_remote_ref, args.workdir)
                if not present:
                    reasons.append(detail)
            else:
                reasons.append(
                    "WRONG_LOCAL_REPOSITORY: refusing remote-ref check from non-canonical remote"
                )
    if reasons:
        for reason in reasons:
            print(f"LOCK_FAIL: {reason}", file=sys.stderr)
        return 1
    try:
        head = _git(["rev-parse", "--verify", "HEAD"], args.workdir)
    except RuntimeError:
        print("LOCK_FAIL: cannot read final HEAD", file=sys.stderr)
        return 1
    print(f"LOCK_OK: {args.branch}@{head}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
