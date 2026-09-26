"""Single-writer ownership for Foundry worktrees (flock-backed, fail closed).

Authority model: the kernel ``flock(2)`` on a per-worktree lock file is the
single source of truth. The JSON metadata inside the file is diagnostic only
and never trusted for the acquire/release decision, so stale metadata can
never brick a worktree.

Lock anchor: ``$FOUNDRY_LOCK_DIR`` (default
``~/.local/share/commander-foundry/writer-locks``), filename
``sha1(<canonical worktree path>).lock``. Nothing is written into any
repository tree, so engine worktrees stay pristine. Canonical identity is
``os.path.realpath`` of the worktree, defeating symlink-alias double writers.

Lifetime: the acquirer holds an open fd with ``LOCK_EX`` for the whole writer
session (the launcher holds it across the OpenCode child lifetime). The kernel
releases the lock on any fd close, including ``kill -9`` — no PID-file trust.

This tool never kills processes and never deletes anything. Same-CWD OpenCode
detection is report-only.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_LOCK_SUBDIR = Path(".local/share/commander-foundry/writer-locks")
HELD_EXIT = 11  # distinct exit code: worktree already has a live writer


def lock_dir() -> Path:
    override = os.environ.get("FOUNDRY_LOCK_DIR")
    if override:
        return Path(override)
    home = os.environ.get("HOME", str(Path.home()))
    return Path(home) / DEFAULT_LOCK_SUBDIR


def canonical_worktree(worktree: str) -> str:
    """Resolve symlinks/relative segments: the single writer identity."""
    return os.path.realpath(os.path.abspath(worktree))


def lock_path_for(worktree: str, base: Path | None = None) -> Path:
    digest = hashlib.sha1(canonical_worktree(worktree).encode("utf-8")).hexdigest()
    slug = Path(canonical_worktree(worktree)).name[:32]
    return (base or lock_dir()) / f"{digest}-{slug}.lock"


def _holder_liveness(holder: dict) -> str:
    """Classify recorded holder metadata: LIVE / DEAD / UNKNOWN (diagnostic)."""
    pid = holder.get("pid")
    if not isinstance(pid, int):
        return "UNKNOWN"
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return "DEAD"
    except PermissionError:
        return "UNKNOWN"
    worktree = holder.get("worktree")
    if worktree:
        try:
            cwd = os.readlink(f"/proc/{pid}/cwd")
        except OSError:
            return "UNKNOWN"
        if canonical_worktree(cwd) != canonical_worktree(str(worktree)):
            return f"LIVE-ELSEWHERE(cwd={cwd})"
    return "LIVE"


def read_holder(lock_path: Path) -> dict | None:
    try:
        return json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


class WriterLock:
    """Hold an exclusive flock for a worktree. Use as a context manager."""

    def __init__(self, worktree: str, workstream: str, branch: str, session: str = ""):
        self.worktree = canonical_worktree(worktree)
        self.workstream = workstream
        self.branch = branch
        self.session = session
        self.path = lock_path_for(self.worktree)
        self._fd: int | None = None

    def acquire(self) -> None:
        """Acquire or raise LockedError. Never trusts stale metadata."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            holder = read_holder(self.path) or {}
            raise LockedError(self.worktree, holder) from None
        self._fd = fd
        payload = {
            "worktree": self.worktree,
            "branch": self.branch,
            "workstream": self.workstream,
            "session": self.session,
            "pid": os.getpid(),
            "acquired_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        os.ftruncate(fd, 0)
        os.write(fd, (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8"))

    def release(self) -> None:
        fd, self._fd = self._fd, None
        if fd is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)

    def __enter__(self) -> WriterLock:
        self.acquire()
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()


class LockedError(RuntimeError):
    def __init__(self, worktree: str, holder: dict):
        self.worktree = worktree
        self.holder = holder
        liveness = _holder_liveness(holder) if holder else "UNKNOWN"
        super().__init__(
            f"WRITER_HELD: {worktree} is owned by workstream "
            f"{holder.get('workstream', '?')!r} branch {holder.get('branch', '?')!r} "
            f"(pid={holder.get('pid', '?')}, session={holder.get('session', '?')}, "
            f"holder={liveness}). Refusing second writer."
        )


def scan_cwd_processes(worktree: str) -> list[dict]:
    """Report live `opencode` processes whose CWD is this worktree (read-only).

    Never kills. Excludes self. Only the `opencode` binary counts: helper
    ``python`` processes with the same CWD are not writers by themselves.
    """
    target = canonical_worktree(worktree)
    found = []
    me = os.getpid()
    proc_root = Path("/proc")
    if not proc_root.is_dir():
        return [{"note": "UNAVAILABLE: /proc absent (non-Linux); scan inconclusive"}]
    for entry in proc_root.iterdir():
        if not entry.name.isdigit() or int(entry.name) == me:
            continue
        try:
            cwd = os.readlink(entry / "cwd")
        except OSError:
            continue
        if canonical_worktree(cwd) != target:
            continue
        try:
            cmdline = (entry / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        argv0 = cmdline[0].decode("utf-8", "replace") if cmdline and cmdline[0] else ""
        if os.path.basename(argv0) != "opencode":
            continue
        found.append(
            {
                "pid": int(entry.name),
                "cwd": cwd,
                "cmdline": " ".join(part.decode("utf-8", "replace") for part in cmdline if part)[
                    :200
                ],
            }
        )
    return found


def hold_and_exec(lock: WriterLock, argv: list[str]) -> int:
    """Acquire the lock, run argv as a child, hold until it exits. Launcher path."""
    import subprocess

    lock.acquire()
    try:
        proc = subprocess.run(argv, check=False)
    finally:
        lock.release()
    return proc.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Foundry single-writer lock.")
    sub = parser.add_subparsers(dest="command", required=True)

    acq = sub.add_parser("acquire", help="Acquire and hold until released.")
    acq.add_argument("--worktree", required=True)
    acq.add_argument("--workstream", required=True)
    acq.add_argument("--branch", required=True)
    acq.add_argument("--session", default="")
    acq.add_argument(
        "--hold",
        action="store_true",
        help="Hold until SIGTERM/SIGINT (for tests and launcher probing).",
    )

    chk = sub.add_parser("check", help="Report holder without acquiring.")
    chk.add_argument("--worktree", required=True)
    chk.add_argument("--fail-if-held", action="store_true")

    scn = sub.add_parser("scan", help="List live opencode PIDs with this CWD.")
    scn.add_argument("--worktree", required=True)

    args = parser.parse_args(argv)
    if args.command == "acquire":
        lock = WriterLock(args.worktree, args.workstream, args.branch, args.session)
        try:
            lock.acquire()
        except LockedError as exc:
            print(str(exc), file=sys.stderr)
            for proc in scan_cwd_processes(args.worktree):
                print(f"HOLDER_CANDIDATE: {json.dumps(proc, sort_keys=True)}")
            return HELD_EXIT
        print(f"WRITER_OK: pid={os.getpid()} holds {lock.worktree} ({lock.path})")
        sys.stdout.flush()
        if args.hold:
            import signal

            stop = False

            def _stop(signum: int, frame: object) -> None:
                nonlocal stop
                stop = True

            signal.signal(signal.SIGTERM, _stop)
            signal.signal(signal.SIGINT, _stop)
            while not stop:
                time.sleep(0.1)
            lock.release()
            print("WRITER_RELEASED")
        else:
            # No --hold: release immediately (probe mode). Launchers must use
            # hold_and_exec or --hold so the fd outlives the child.
            lock.release()
            print("WRITER_RELEASED (probe; not held)")
        return 0
    if args.command == "check":
        path = lock_path_for(args.worktree)
        try:
            fd = os.open(path, os.O_RDONLY)
        except FileNotFoundError:
            print(
                json.dumps(
                    {
                        "worktree": canonical_worktree(args.worktree),
                        "held": False,
                        "holder": None,
                        "holder_liveness": "NONE",
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        with os.fdopen(fd, "rb", closefd=True):
            holder = read_holder(path)
            # A non-blocking exclusive flock attempt is the liveness probe:
            # success means no live holder (release immediately); failure
            # means a live fd holds it elsewhere. Metadata is reported only.
            probe = os.open(path, os.O_RDONLY)
            try:
                try:
                    fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    held = True  # held by a live fd elsewhere; never acquired here
                else:
                    held = False
                    fcntl.flock(probe, fcntl.LOCK_UN)
            finally:
                os.close(probe)
        payload = {
            "worktree": canonical_worktree(args.worktree),
            "held": held,
            "holder": holder,
            "holder_liveness": _holder_liveness(holder) if holder else "NONE",
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        if args.fail_if_held and held:
            return HELD_EXIT
        return 0
    if args.command == "scan":
        procs = scan_cwd_processes(args.worktree)
        print(
            json.dumps(
                {"worktree": canonical_worktree(args.worktree), "opencode_pids": procs}, indent=2
            )
        )
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
