"""Source-lock provenance and deterministic intake identities.

Every intake record carries a full provenance chain
(repository / commit / path / content hash / tool version) and a stable
intake ID derived deterministically from that chain. Same input plus same
tool version always yields the same identity and output.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass

from . import Q6_SCAFFOLDING_VERSION


class ProvenanceError(ValueError):
    """Raised when source-lock metadata is missing, ambiguous, or mismatched."""


@dataclass(frozen=True)
class SourceLock:
    """Pinned external input location. All fields required (fail closed)."""

    source_corpus: str  # e.g. "forge-card-scripts"
    source_repository: str  # e.g. "https://github.com/Card-Forge/forge.git"
    source_commit: str  # full commit SHA (pin)
    source_path: str  # path within the source repository

    def validate(self) -> None:
        missing = [
            name
            for name in (
                "source_corpus",
                "source_repository",
                "source_commit",
                "source_path",
            )
            if not getattr(self, name) or not str(getattr(self, name)).strip()
        ]
        if missing:
            raise ProvenanceError(
                f"missing source-lock metadata: {', '.join(missing)} "
                "(intake fails closed without a complete source lock)"
            )
        commit = self.source_commit.strip()
        if len(commit) < 7 or any(c not in "0123456789abcdefABCDEF" for c in commit):
            raise ProvenanceError(
                f"ambiguous source commit pin: {self.source_commit!r} "
                "(a hex commit SHA is required)"
            )


@dataclass(frozen=True)
class Provenance:
    """Full provenance chain stamped on every scaffolding artifact."""

    source_corpus: str
    source_repository: str
    source_commit: str
    source_path: str
    input_hash: str  # sha256 hex of the raw ingested bytes
    tool_version: str
    intake_id: str

    def as_dict(self) -> dict:
        return asdict(self)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_intake_id(
    lock: SourceLock, input_hash: str, tool_version: str = Q6_SCAFFOLDING_VERSION
) -> str:
    """Derive the stable intake ID for an input + tool version.

    The ID is ``sha256("q6-intake-v1" | corpus | repository | commit | path
    | input_hash | tool_version)`` truncated to 32 hex chars (128 bits).
    """
    lock.validate()
    canonical = "|".join(
        [
            "q6-intake-v1",
            lock.source_corpus.strip(),
            lock.source_repository.strip(),
            lock.source_commit.strip(),
            lock.source_path.strip(),
            input_hash.strip().lower(),
            tool_version.strip(),
        ]
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def build_provenance(lock: SourceLock, raw: bytes) -> Provenance:
    """Validate the source lock, hash the input, and stamp provenance."""
    lock.validate()
    digest = sha256_hex(raw)
    return Provenance(
        source_corpus=lock.source_corpus.strip(),
        source_repository=lock.source_repository.strip(),
        source_commit=lock.source_commit.strip(),
        source_path=lock.source_path.strip(),
        input_hash=digest,
        tool_version=Q6_SCAFFOLDING_VERSION,
        intake_id=compute_intake_id(lock, digest),
    )


def check_input_hash(raw: bytes, expected_hash: str, *, source: str) -> None:
    """Fail closed when recorded content hash does not match the bytes."""
    actual = sha256_hex(raw)
    if actual.lower() != expected_hash.strip().lower():
        raise ProvenanceError(
            f"hash mismatch for {source}: recorded {expected_hash} != "
            f"computed {actual} (input fails closed)"
        )
