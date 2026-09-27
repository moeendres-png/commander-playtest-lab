"""WS218 source/domain lock collection + enforcement (fail closed)."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

from .divergence import DivergenceClass, ReplayDivergence
from .tape import TapeSourceLock

LAB_REPOSITORY = "moeendres-png/commander-playtest-lab"
ENGINE_REPOSITORY = "xmage-engine (pinned via XmageProvider)"
ADAPTER_IDENTITY = "xmage-engine-bridge full-game lane"
RULES_AUTHORITY = "xmage"


def _git(args: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(cwd) if cwd else None,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def collect_lab_lock(repo_root: Path | None = None) -> dict[str, str]:
    root = repo_root or Path.cwd()
    commit = _git(["rev-parse", "HEAD"], root)
    tree = _git(["rev-parse", "HEAD^{tree}"], root)
    return {"lab_repository": LAB_REPOSITORY, "lab_commit": commit, "lab_tree": tree}


def protocol_schema_digest(repo_root: Path | None = None) -> str:
    root = repo_root or Path.cwd()
    candidates = [
        root / "schemas/engine_adapter_protocol.schema.json",
        root / "schemas/engine_protocol/EngineProtocolRequest.schema.json",
        root / "schemas/engine_protocol/EngineProtocolResponse.schema.json",
    ]
    hasher = hashlib.sha256()
    found = 0
    for path in sorted(candidates):
        if path.exists():
            hasher.update(path.read_bytes())
            hasher.update(b"\x00")
            found += 1
    if found == 0:
        raise RuntimeError("no protocol schema files found for digest")
    return hasher.hexdigest()


def collect_source_lock(
    *,
    engine_commit: str,
    engine_version: str,
    engine_tree: str | None,
    decision_protocol_version: str,
    protocol_version: str,
    repo_root: Path | None = None,
    oracle_snapshot_identity: str | None = None,
    rulings_snapshot_identity: str | None = None,
    commander_authority_identity: str | None = None,
) -> TapeSourceLock:
    lab = collect_lab_lock(repo_root)
    digest = protocol_schema_digest(repo_root)
    return TapeSourceLock(
        lab_repository=lab["lab_repository"],
        lab_commit=lab["lab_commit"],
        lab_tree=lab["lab_tree"],
        provider_identity="xmage",
        engine_repository=ENGINE_REPOSITORY,
        engine_commit=engine_commit,
        engine_tree=engine_tree,
        engine_version=engine_version,
        adapter_identity=ADAPTER_IDENTITY,
        protocol_version=protocol_version,
        decision_protocol_version=decision_protocol_version,
        protocol_schema_digest=digest,
        rules_authority_identity="xmage",
        oracle_snapshot_identity=oracle_snapshot_identity,
        rulings_snapshot_identity=rulings_snapshot_identity,
        commander_authority_identity=commander_authority_identity,
    )


def verify_source_lock(recorded: TapeSourceLock, observed: TapeSourceLock) -> None:
    """Refuse before game execution under any material mismatch."""
    mismatched: list[str] = []
    for field in (
        "lab_repository",
        "lab_commit",
        "lab_tree",
        "provider_identity",
        "engine_repository",
        "engine_commit",
        "engine_version",
        "adapter_identity",
        "protocol_version",
        "decision_protocol_version",
        "protocol_schema_digest",
        "rules_authority_identity",
    ):
        if getattr(recorded, field) != getattr(observed, field):
            mismatched.append(field)
    # Optional snapshot identities bind when the recorder knew them; a
    # recorded value must still match when the observer knows it.
    for field in (
        "oracle_snapshot_identity",
        "rulings_snapshot_identity",
        "commander_authority_identity",
        "engine_tree",
    ):
        recorded_value = getattr(recorded, field)
        observed_value = getattr(observed, field)
        if recorded_value is not None and observed_value is not None:
            if recorded_value != observed_value:
                mismatched.append(field)
        elif recorded_value is not None and observed_value is None:
            mismatched.append(field)
    if mismatched:
        raise ReplayDivergence(
            DivergenceClass.SOURCE_LOCK_MISMATCH,
            "material source lock mismatch: " + ",".join(sorted(mismatched)),
        )


def verify_domain_lock(recorded: dict[str, Any], observed: dict[str, Any]) -> None:
    """Domain lock: decks, player count, seats, commanders, starting config."""
    keys = (
        "deck_hashes",
        "player_count",
        "seat_map",
        "commanders",
        "starting_life",
        "starting_player_contract",
    )
    mismatched = [k for k in keys if recorded.get(k) != observed.get(k)]
    if mismatched:
        raise ReplayDivergence(
            DivergenceClass.DOMAIN_LOCK_MISMATCH,
            "material domain lock mismatch: " + ",".join(sorted(mismatched)),
        )


__all__ = [
    "ADAPTER_IDENTITY",
    "ENGINE_REPOSITORY",
    "LAB_REPOSITORY",
    "collect_lab_lock",
    "collect_source_lock",
    "protocol_schema_digest",
    "verify_domain_lock",
    "verify_source_lock",
]
