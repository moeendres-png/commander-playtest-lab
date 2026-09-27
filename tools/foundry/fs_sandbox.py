"""Fail-closed filesystem sandbox for cross-workstream OpenCode runs.

Cross-workstream sessions need a stronger boundary than OpenCode edit permissions or
Landlock alone: allowed interpreters can perform direct file I/O, and Landlock does not
mediate every metadata operation. This wrapper therefore uses Bubblewrap to make the
entire host filesystem read-only, then re-binds only explicitly authorized roots
read-write.

If Bubblewrap or the required mount namespace is unavailable, execution is refused before
the OpenCode child starts. No unsandboxed fallback exists.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


class SandboxError(RuntimeError):
    """Cross-workstream filesystem isolation could not be installed."""


def _canonical_roots(allowed_roots: list[str]) -> list[str]:
    roots: list[str] = []
    for raw in allowed_roots:
        path = os.path.realpath(os.path.abspath(raw))
        if path == "/":
            raise SandboxError("refusing writable filesystem root")
        if not Path(path).exists():
            raise SandboxError(f"allowed write root does not exist: {path}")
        if path not in roots:
            roots.append(path)
    return sorted(roots)


def build_bwrap_argv(command: list[str], allowed_roots: list[str]) -> list[str]:
    if sys.platform != "linux":
        raise SandboxError("cross-workstream mount sandbox requires Linux")
    binary = shutil.which("bwrap")
    if not binary:
        raise SandboxError(
            "bubblewrap (bwrap) is required for cross-workstream execution; "
            "install it or run without cross-workstream access"
        )
    if not command:
        raise SandboxError("missing child command")

    roots = _canonical_roots(allowed_roots)
    argv = [
        binary,
        "--die-with-parent",
        "--new-session",
        "--ro-bind",
        "/",
        "/",
        "--dev-bind",
        "/dev",
        "/dev",
        "--proc",
        "/proc",
    ]
    for root in roots:
        # Later bind mounts override the enclosing read-only root only for this
        # exact subtree. chmod/xattr/utime outside these roots remain blocked by
        # the read-only mount, unlike the former Landlock-only boundary.
        argv.extend(["--bind", root, root])
    argv.extend(["--", *command])
    return argv


def run(command: list[str], allowed_roots: list[str]) -> int:
    argv = build_bwrap_argv(command, allowed_roots)
    os.environ["FOUNDRY_FS_SANDBOX"] = "bubblewrap-readonly-root"
    proc = subprocess.run(argv, check=False)
    return int(proc.returncode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run one command with a read-only host root and explicit writable binds."
    )
    parser.add_argument("--allow-write", action="append", default=[])
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    try:
        return run(command, args.allow_write)
    except (OSError, SandboxError) as exc:
        print(f"SANDBOX_REFUSED: {exc}", file=sys.stderr)
        return 13


if __name__ == "__main__":
    raise SystemExit(main())
