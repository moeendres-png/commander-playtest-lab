#!/usr/bin/env python3
"""WS223 dependency-lock verifier (offline, no network).

Parses ``requirements/lock.txt`` (pip-compile ``--generate-hashes`` output
plus the WS223 appendix for non-PyPI-hashable local installs) and verifies
the recorded ``DEPENDENCY_LOCK_DIGEST``.

Lock layout:
  * compiler section: ``name==version`` lines each followed by one or more
    ``--hash=...`` lines (real PyPI hashes);
  * appendix section: ``# APPENDIX-ENTRY: name=<name> sha256=<hex> ...``
    lines (exactly 2: the editable local package source digest and the
    compiler-input digest; informational, installed with --no-deps).
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCK_REL = Path("requirements/lock.txt")
DIGEST_REL = Path("qualification/ws223-ci-cardinality-environment-lock/DEPENDENCY_LOCK_DIGEST")

_COMPILER_RE = re.compile(r"^([A-Za-z0-9_.\-]+)==([^\s\\;]+)")
_HASH_RE = re.compile(r"^--hash=([^:\s]+):([0-9a-f]+)$")
_APPENDIX_RE = re.compile(r"^# APPENDIX-ENTRY:\s*name=(\S+)\s+sha256=([0-9a-f]{64})\b")


def _parse_lock(text: str) -> tuple[list[dict], list[dict]]:
    compiler_entries: list[dict] = []
    appendix_entries: list[dict] = []
    current: dict | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.endswith("\\"):
            line = line[:-1].strip()
        if not line:
            current = None
            continue
        if line.startswith("# APPENDIX-ENTRY:"):
            current = None
            match = _APPENDIX_RE.match(line)
            if not match:
                raise ValueError(f"malformed appendix entry: {line}")
            appendix_entries.append({"name": match.group(1), "hashes": [match.group(2)]})
            continue
        if line.startswith("#"):
            current = None
            continue
        match = _COMPILER_RE.match(line)
        if match:
            current = {
                "name": match.group(1),
                "version": match.group(2),
                "hashes": [],
            }
            compiler_entries.append(current)
            continue
        hmatch = _HASH_RE.match(line)
        if hmatch and current is not None:
            current["hashes"].append(f"{hmatch.group(1)}:{hmatch.group(2)}")
            continue
        current = None
    return compiler_entries, appendix_entries


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="verify the WS223 dependency lock")
    parser.add_argument("--lock", default=str(REPO_ROOT / LOCK_REL))
    parser.add_argument("--digest-file", default=str(REPO_ROOT / DIGEST_REL))
    args = parser.parse_args(argv)
    text = Path(args.lock).read_text(encoding="utf-8")
    compiler_entries, appendix_entries = _parse_lock(text)
    if len(compiler_entries) < 100:
        print(f"lock has only {len(compiler_entries)} compiler entries", file=sys.stderr)
        return 1
    if len(appendix_entries) != 2:
        print(f"lock has {len(appendix_entries)} appendix entries, expected 2", file=sys.stderr)
        return 1
    if not all(entry["hashes"] for entry in compiler_entries + appendix_entries):
        print("lock has entries without hashes", file=sys.stderr)
        return 1
    recorded = Path(args.digest_file).read_text(encoding="utf-8").strip()
    actual = hashlib.sha256(text.encode()).hexdigest()
    if actual != recorded:
        print("lock digest mismatch", file=sys.stderr)
        return 1
    print(f"lock ok: {len(compiler_entries)} compiler + {len(appendix_entries)} appendix entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
