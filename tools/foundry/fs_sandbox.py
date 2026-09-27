"""Unprivileged Linux Landlock write sandbox for cross-workstream OpenCode runs.

Reads and execution remain unrestricted. Filesystem mutation is allowed only beneath
explicit --allow-write roots. This closes the known permission-layer gap where an allowed
interpreter can perform file I/O without going through OpenCode's edit tool.

The wrapper is intentionally fail-closed: unsupported kernels/architectures or any rule
installation failure abort before the OpenCode child is exec'd.
"""

from __future__ import annotations

import argparse
import ctypes
import errno
import os
import platform
import sys
from pathlib import Path

# Linux UAPI constants.
LANDLOCK_CREATE_RULESET_VERSION = 1
LANDLOCK_RULE_PATH_BENEATH = 1
PR_SET_NO_NEW_PRIVS = 38

ACCESS_FS_WRITE_FILE = 1 << 1
ACCESS_FS_REMOVE_DIR = 1 << 4
ACCESS_FS_REMOVE_FILE = 1 << 5
ACCESS_FS_MAKE_CHAR = 1 << 6
ACCESS_FS_MAKE_DIR = 1 << 7
ACCESS_FS_MAKE_REG = 1 << 8
ACCESS_FS_MAKE_SOCK = 1 << 9
ACCESS_FS_MAKE_FIFO = 1 << 10
ACCESS_FS_MAKE_BLOCK = 1 << 11
ACCESS_FS_MAKE_SYM = 1 << 12
ACCESS_FS_REFER = 1 << 13
ACCESS_FS_TRUNCATE = 1 << 14

_BASE_WRITE_MASK = (
    ACCESS_FS_WRITE_FILE
    | ACCESS_FS_REMOVE_DIR
    | ACCESS_FS_REMOVE_FILE
    | ACCESS_FS_MAKE_CHAR
    | ACCESS_FS_MAKE_DIR
    | ACCESS_FS_MAKE_REG
    | ACCESS_FS_MAKE_SOCK
    | ACCESS_FS_MAKE_FIFO
    | ACCESS_FS_MAKE_BLOCK
    | ACCESS_FS_MAKE_SYM
)

# Landlock syscall numbers are stable on the Linux architectures used by this project.
_SYSCALLS = {
    "x86_64": (444, 445, 446),
    "amd64": (444, 445, 446),
    "aarch64": (444, 445, 446),
    "arm64": (444, 445, 446),
}


class RulesetAttr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64)]


class PathBeneathAttr(ctypes.Structure):
    _fields_ = [
        ("allowed_access", ctypes.c_uint64),
        ("parent_fd", ctypes.c_int32),
    ]


class SandboxError(RuntimeError):
    """Landlock setup failed; callers must not continue unsandboxed."""


def _syscalls() -> tuple[int, int, int]:
    machine = platform.machine().lower()
    try:
        return _SYSCALLS[machine]
    except KeyError as exc:
        raise SandboxError(f"unsupported Linux architecture for Landlock: {machine!r}") from exc


def _libc() -> ctypes.CDLL:
    return ctypes.CDLL(None, use_errno=True)


def landlock_abi() -> int:
    if sys.platform != "linux":
        raise SandboxError("Landlock sandbox requires Linux")
    create_nr, _, _ = _syscalls()
    libc = _libc()
    rc = libc.syscall(create_nr, 0, 0, LANDLOCK_CREATE_RULESET_VERSION)
    if rc < 0:
        err = ctypes.get_errno()
        raise SandboxError(f"Landlock ABI query failed: errno={err} ({os.strerror(err)})")
    if rc < 1:
        raise SandboxError(f"Landlock ABI {rc} is unsupported")
    return int(rc)


def handled_write_mask(abi: int) -> int:
    mask = _BASE_WRITE_MASK
    if abi >= 2:
        mask |= ACCESS_FS_REFER
    if abi >= 3:
        mask |= ACCESS_FS_TRUNCATE
    return mask


def restrict_writes(allowed_roots: list[str]) -> int:
    """Install a write-only Landlock ruleset; return the negotiated ABI."""
    abi = landlock_abi()
    mask = handled_write_mask(abi)
    create_nr, add_nr, restrict_nr = _syscalls()
    libc = _libc()

    ruleset_attr = RulesetAttr(mask)
    ruleset_fd = libc.syscall(
        create_nr,
        ctypes.byref(ruleset_attr),
        ctypes.sizeof(ruleset_attr),
        0,
    )
    if ruleset_fd < 0:
        err = ctypes.get_errno()
        raise SandboxError(f"Landlock ruleset creation failed: errno={err} ({os.strerror(err)})")

    opened: list[int] = []
    try:
        canonical: list[str] = []
        for raw in allowed_roots:
            path = os.path.realpath(os.path.abspath(raw))
            if path not in canonical:
                canonical.append(path)
        for path in canonical:
            if not Path(path).exists():
                raise SandboxError(f"allowed write root does not exist: {path}")
            flags = getattr(os, "O_PATH", 0) | os.O_CLOEXEC
            fd = os.open(path, flags)
            opened.append(fd)
            attr = PathBeneathAttr(mask, fd)
            rc = libc.syscall(
                add_nr,
                ruleset_fd,
                LANDLOCK_RULE_PATH_BENEATH,
                ctypes.byref(attr),
                0,
            )
            if rc < 0:
                err = ctypes.get_errno()
                raise SandboxError(
                    f"Landlock add-rule failed for {path}: errno={err} ({os.strerror(err)})"
                )

        rc = libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0)
        if rc != 0:
            err = ctypes.get_errno()
            raise SandboxError(f"PR_SET_NO_NEW_PRIVS failed: errno={err} ({os.strerror(err)})")
        rc = libc.syscall(restrict_nr, ruleset_fd, 0)
        if rc < 0:
            err = ctypes.get_errno()
            hint = " (kernel Landlock disabled)" if err in (errno.ENOSYS, errno.EOPNOTSUPP) else ""
            raise SandboxError(
                f"Landlock restrict-self failed: errno={err} ({os.strerror(err)}){hint}"
            )
    finally:
        for fd in opened:
            os.close(fd)
        os.close(ruleset_fd)
    return abi


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one command under a Landlock write sandbox.")
    parser.add_argument("--allow-write", action="append", default=[])
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print("SANDBOX_REFUSED: missing child command", file=sys.stderr)
        return 2
    try:
        abi = restrict_writes(args.allow_write)
    except (OSError, SandboxError) as exc:
        print(f"SANDBOX_REFUSED: {exc}", file=sys.stderr)
        return 13
    os.environ["FOUNDRY_LANDLOCK_ABI"] = str(abi)
    os.execvpe(command[0], command, os.environ)
    return 127


if __name__ == "__main__":
    raise SystemExit(main())
