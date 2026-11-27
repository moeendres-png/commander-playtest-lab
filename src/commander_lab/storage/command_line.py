"""Cross-platform command-line splitting helpers for subprocess environment commands."""

from __future__ import annotations

import os
import shlex


def _split_windows_cmdline(raw: str) -> tuple[str, ...]:
    """Parse a Windows ``subprocess.list2cmdline`` string into argv tokens.

    Follows Microsoft C runtime / ``CommandLineToArgvW`` quoting rules so that
    outer quotes added around paths with spaces are stripped rather than kept
    as literal characters (unlike ``shlex.split(..., posix=False)``).
    """
    tokens: list[str] = []
    n = len(raw)
    i = 0
    while i < n:
        while i < n and raw[i] in (" ", "\t"):
            i += 1
        if i >= n:
            break
        buf: list[str] = []
        in_quotes = False
        while i < n:
            ch = raw[i]
            if not in_quotes and ch in (" ", "\t"):
                break
            if ch == "\\":
                bs_count = 0
                while i < n and raw[i] == "\\":
                    bs_count += 1
                    i += 1
                if i < n and raw[i] == '"':
                    buf.append("\\" * (bs_count // 2))
                    if bs_count % 2 == 1:
                        buf.append('"')
                    else:
                        in_quotes = not in_quotes
                    i += 1
                else:
                    buf.append("\\" * bs_count)
                continue
            if ch == '"':
                if in_quotes and i + 1 < n and raw[i + 1] == '"':
                    buf.append('"')
                    i += 2
                else:
                    in_quotes = not in_quotes
                    i += 1
                continue
            buf.append(ch)
            i += 1
        if in_quotes:
            raise ValueError("No closing quotation")
        tokens.append("".join(buf))
    return tuple(tokens)


def parse_command_text(raw: str, *, windows: bool | None = None) -> tuple[str, ...]:
    """Parse a serialized engine command back into argv tokens.

    Inverse of ``launch.command_text`` (``subprocess.list2cmdline`` on Windows,
    ``shlex.join`` on POSIX).
    """
    is_windows = (os.name == "nt") if windows is None else windows
    if is_windows:
        return _split_windows_cmdline(raw)
    return tuple(shlex.split(raw, posix=True))
