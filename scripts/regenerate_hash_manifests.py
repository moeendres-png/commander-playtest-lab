#!/usr/bin/env python3
"""Regenerate the qualification hash manifests, in dependency order.

Order matters and is the whole point of this script:

1. ``qualification/SHA256SUMS`` covers every file under ``qualification/`` except
   itself and any ``__pycache__``.
2. ``WS17_SHA256SUMS`` covers the explicit root inputs plus every file under
   ``qualification/`` INCLUDING every nested ``SHA256SUMS``, so the root entry set
   is exactly the qualification tree minus build noise.

Because the root manifest hashes the qualification manifest, generating them in
the other order produces a root manifest that never verifies. The verification
gate is ``tests/qualification/test_ws17_qualification.py``, which recomputes every
digest and additionally requires the entry SETS to match the tree exactly, so a
stale or missing entry fails rather than passing unnoticed.

Run this after runtime evidence is generated and before sealing:

    python scripts/regenerate_hash_manifests.py

It is idempotent: running it twice on an unchanged tree produces byte-identical
output.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
QUALIFICATION = REPO_ROOT / "qualification"

# Root inputs that are not under qualification/.
ROOT_EXTRA_INPUTS: tuple[str, ...] = (
    "pyproject.toml",
    ".github/workflows/production-qualification.yml",
    "tests/qualification/test_ws17_qualification.py",
)

# Excluded everywhere: build noise, never a tracked artifact.
_EXCLUDED_DIR_PARTS = {"__pycache__", ".pytest_cache"}


def _is_excluded(path: Path) -> bool:
    return bool(_EXCLUDED_DIR_PARTS.intersection(path.parts))


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _qualification_files() -> list[Path]:
    return sorted(
        path
        for path in QUALIFICATION.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS" and not _is_excluded(path)
    )


def _write_manifest(manifest: Path, entries: list[tuple[str, str]]) -> None:
    """Write a sha256sum-compatible manifest: digest, two spaces, relative path."""
    body = "".join(f"{digest}  {relative}\n" for relative, digest in sorted(entries))
    manifest.write_text(body, encoding="utf-8")


def regenerate() -> int:
    # Step 1: the qualification manifest.
    qualification_manifest = QUALIFICATION / "SHA256SUMS"
    qualification_entries = [
        (str(path.relative_to(QUALIFICATION)), _digest(path)) for path in _qualification_files()
    ]
    _write_manifest(qualification_manifest, qualification_entries)
    print(
        f"wrote {qualification_manifest.relative_to(REPO_ROOT)}: {len(qualification_entries)} entries"
    )

    # Step 2: the root manifest, which hashes the qualification manifest as well.
    root_entries: list[tuple[str, str]] = []
    for relative in ROOT_EXTRA_INPUTS:
        path = REPO_ROOT / relative
        if not path.is_file():
            print(f"ERROR: required root input missing: {relative}", file=sys.stderr)
            return 1
        root_entries.append((relative, _digest(path)))
    for path in _qualification_files():
        root_entries.append((str(path.relative_to(REPO_ROOT)), _digest(path)))
    # Every nested manifest too, INCLUDING qualification/SHA256SUMS itself. The
    # root entry set is "everything under qualification/ except build noise", so
    # omitting a nested SHA256SUMS leaves the root manifest incomplete and the
    # set comparison fails even though every digest present is correct.
    nested_manifests = sorted(
        path
        for path in QUALIFICATION.rglob("SHA256SUMS")
        if path.is_file() and not _is_excluded(path)
    )
    for path in nested_manifests:
        root_entries.append((str(path.relative_to(REPO_ROOT)), _digest(path)))
    root_manifest = REPO_ROOT / "WS17_SHA256SUMS"
    _write_manifest(root_manifest, root_entries)
    print(f"wrote {root_manifest.relative_to(REPO_ROOT)}: {len(root_entries)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(regenerate())
