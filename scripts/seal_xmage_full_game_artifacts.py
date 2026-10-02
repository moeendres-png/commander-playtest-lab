#!/usr/bin/env python3
"""Seal and verify the XMage full-game technical-evidence artifact root.

The manifest is intentionally standard sha256sum format with paths relative to
its own artifact root, so the uploaded package can be independently checked
with:

    cd <artifact-root>
    sha256sum -c SHA256SUMS

This module owns artifact integrity only. It does not interpret FullGame rules,
replay, player-count, or provider-qualification semantics.
"""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

MANIFEST_NAME = "SHA256SUMS"
_LINE = re.compile(r"^([0-9a-f]{64})  (\./.+)$")

REQUIRED_EVIDENCE = (
    "FULL_GAME_PILOT_BINDING_SCHEMA.json",
    "FULL_GAME_CONFORMANCE_RESULT_SCHEMA.json",
    "FULL_GAME_REPLAY_GATE_SCHEMA.json",
    "FULL_GAME_BATCH_CASE_SCHEMA.json",
    "FULL_GAME_BATCH_RECORD_SCHEMA.json",
    "FULL_GAME_BATCH_REPORT_SCHEMA.json",
    "ARCHITECTURE_INVARIANT_REPORT.json",
    "XMAGE_FULL_GAME_CONFORMANCE.json",
    "XMAGE_FULL_GAME_REPLAY_GATE.json",
    "HIDDEN_INFORMATION_BOUNDARY_REPORT.json",
    "XMAGE_FULL_GAME_SMOKE_2P.json",
    "XMAGE_FULL_GAME_SMOKE_3P.json",
    "XMAGE_FULL_GAME_SMOKE_5P.json",
    "XMAGE_FULL_GAME_SMOKE_6P.json",
    "XMAGE_FULL_GAME_FAIL_CLOSED_7P.json",
    "TEST_VALIDATION_REPORT.json",
)


class ArtifactIntegrityError(RuntimeError):
    """The full-game evidence package cannot be sealed or verified."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _payload_files(root: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file() and path.name != MANIFEST_NAME
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def _require_evidence(root: Path) -> None:
    missing = [name for name in REQUIRED_EVIDENCE if not (root / name).is_file()]
    if missing:
        raise ArtifactIntegrityError(
            "required full-game evidence missing: " + ", ".join(missing)
        )


def write_manifest(root: Path) -> Path:
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    manifest = root / MANIFEST_NAME

    # A failed seal must never leave a stale manifest from the checkout or a
    # prior attempt that could be mistaken for current integrity evidence.
    manifest.unlink(missing_ok=True)
    _require_evidence(root)

    files = _payload_files(root)
    if not files:
        raise ArtifactIntegrityError("artifact root contains no payload files")

    lines = [
        f"{_sha256(path)}  ./{path.relative_to(root).as_posix()}"
        for path in files
    ]
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if manifest.stat().st_size == 0:
        raise ArtifactIntegrityError("checksum manifest is empty")
    return manifest


def _read_manifest(root: Path) -> dict[str, str]:
    manifest = root / MANIFEST_NAME
    if not manifest.is_file() or manifest.stat().st_size == 0:
        raise ArtifactIntegrityError("checksum manifest is missing or empty")

    entries: dict[str, str] = {}
    for number, raw in enumerate(manifest.read_text(encoding="utf-8").splitlines(), start=1):
        match = _LINE.fullmatch(raw)
        if match is None:
            raise ArtifactIntegrityError(f"invalid checksum manifest line {number}")
        digest, encoded_path = match.groups()
        relative = encoded_path[2:]
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts or relative == "":
            raise ArtifactIntegrityError(f"unsafe checksum path on line {number}")
        normalized = candidate.as_posix()
        if normalized in entries:
            raise ArtifactIntegrityError(f"duplicate checksum entry: {normalized}")
        entries[normalized] = digest

    if not entries:
        raise ArtifactIntegrityError("checksum manifest contains no entries")
    return entries


def verify_manifest(root: Path) -> None:
    root = root.resolve()
    entries = _read_manifest(root)

    required_missing = [name for name in REQUIRED_EVIDENCE if name not in entries]
    if required_missing:
        raise ArtifactIntegrityError(
            "required evidence absent from checksum manifest: "
            + ", ".join(required_missing)
        )

    actual_files = {
        path.relative_to(root).as_posix()
        for path in _payload_files(root)
    }
    listed_files = set(entries)
    if actual_files != listed_files:
        missing = sorted(actual_files - listed_files)
        stale = sorted(listed_files - actual_files)
        raise ArtifactIntegrityError(
            f"checksum coverage mismatch: unlisted={missing} missing={stale}"
        )

    for relative, expected in entries.items():
        path = root / relative
        if not path.is_file():
            raise ArtifactIntegrityError(f"hashed file is missing: {relative}")
        actual = _sha256(path)
        if actual != expected:
            raise ArtifactIntegrityError(f"checksum mismatch: {relative}")


def seal(root: Path) -> Path:
    manifest = root.resolve() / MANIFEST_NAME
    try:
        write_manifest(root)
        verify_manifest(root)
    except Exception:
        # Preserve the evidence files for forensic upload, but never preserve a
        # manifest that failed to seal/verify.
        manifest.unlink(missing_ok=True)
        raise
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("artifacts/xmage-full-game"),
        help="Full-game artifact root to seal and verify",
    )
    args = parser.parse_args(argv)
    seal(args.root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
