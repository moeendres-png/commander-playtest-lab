from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .database import connect_database, migrate_database
from .run_identity import canonical_run_json_bytes, sha256_run_value


class ResultCacheCorruptionError(RuntimeError):
    """Raised when a stored exact-result cache entry fails identity or result verification."""


@dataclass(frozen=True)
class ResultCacheLookup:
    cache_key: str
    cache_hit: bool
    evidence_class: str
    result: dict[str, Any]


def build_exact_result_identity(
    *,
    engine_version: str,
    deck_hashes: Sequence[str],
    opponent_hashes: Sequence[str],
    pilot_hashes: Sequence[str],
    canonical_context_snapshot: str,
    scenario: Mapping[str, Any],
    simulation_config: Mapping[str, Any],
    exact_seed_set: Sequence[int],
    policy_config_hashes: Mapping[str, str],
    tool_name: str = "structural_paired_comparison",
) -> dict[str, Any]:
    """Build the complete deterministic identity for one reusable simulation result."""
    if not engine_version:
        raise ValueError("engine_version is required")
    if not canonical_context_snapshot:
        raise ValueError("canonical_context_snapshot is required")
    if not exact_seed_set:
        raise ValueError("exact_seed_set must not be empty")
    return {
        "cache_identity_version": 1,
        "tool_name": tool_name,
        "engine_version": engine_version,
        "deck_hashes": list(deck_hashes),
        "opponent_hashes": list(opponent_hashes),
        "pilot_hashes": list(pilot_hashes),
        "canonical_context_snapshot": canonical_context_snapshot,
        "scenario": dict(scenario),
        "simulation_config": dict(simulation_config),
        "exact_seed_set": [int(seed) for seed in exact_seed_set],
        "policy_config_hashes": dict(policy_config_hashes),
    }


class ExactResultCache:
    """Content-addressed read-through cache backed by the existing hardened SQLite store."""

    def __init__(self, database_path: str | Path, *, root: str | Path | None = None) -> None:
        self.database_path = Path(database_path)
        self.root = Path(root).resolve() if root is not None else None
        migrate_database(self.database_path)

    def key_for(self, identity: Mapping[str, Any]) -> str:
        return sha256_run_value(dict(identity), root=self.root)

    def get(self, identity: Mapping[str, Any]) -> ResultCacheLookup | None:
        expected_key = self.key_for(identity)
        with closing(connect_database(self.database_path)) as connection:
            row = connection.execute(
                "SELECT identity_json,result_json,result_hash,evidence_class "
                "FROM result_cache WHERE cache_key=?",
                (expected_key,),
            ).fetchone()
        if row is None:
            return None

        identity_json = str(row["identity_json"])
        if (
            canonical_run_json_bytes(dict(identity), root=self.root).decode("utf-8")
            != identity_json
        ):
            raise ResultCacheCorruptionError("cache identity payload does not match requested key")
        try:
            result = json.loads(str(row["result_json"]))
        except json.JSONDecodeError as exc:
            raise ResultCacheCorruptionError("cached result is not valid JSON") from exc
        if not isinstance(result, dict):
            raise ResultCacheCorruptionError("cached result must be a JSON object")
        result_hash = sha256_run_value(result, root=self.root)
        if result_hash != str(row["result_hash"]):
            raise ResultCacheCorruptionError("cached result hash mismatch")

        with closing(connect_database(self.database_path)) as connection, connection:
            connection.execute(
                "UPDATE result_cache SET hit_count=hit_count+1 WHERE cache_key=?",
                (expected_key,),
            )
        return ResultCacheLookup(
            cache_key=expected_key,
            cache_hit=True,
            evidence_class=str(row["evidence_class"]),
            result=result,
        )

    def put(
        self,
        identity: Mapping[str, Any],
        result: Mapping[str, Any],
        *,
        evidence_class: str,
    ) -> ResultCacheLookup:
        cache_key = self.key_for(identity)
        identity_json = canonical_run_json_bytes(dict(identity), root=self.root).decode("utf-8")
        result_json = json.dumps(
            dict(result),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        normalized_result = json.loads(result_json)
        if not isinstance(normalized_result, dict):
            raise ValueError("cached result must serialize to a JSON object")
        result_hash = sha256_run_value(normalized_result, root=self.root)
        with closing(connect_database(self.database_path)) as connection, connection:
            connection.execute(
                "INSERT INTO result_cache("
                "cache_key,identity_json,result_json,result_hash,evidence_class,created_at,hit_count"
                ") VALUES(?,?,?,?,?,?,0) "
                "ON CONFLICT(cache_key) DO UPDATE SET "
                "identity_json=excluded.identity_json,result_json=excluded.result_json,"
                "result_hash=excluded.result_hash,evidence_class=excluded.evidence_class,"
                "created_at=excluded.created_at,hit_count=0",
                (
                    cache_key,
                    identity_json,
                    result_json,
                    result_hash,
                    evidence_class,
                    datetime.now(UTC).isoformat(),
                ),
            )
        return ResultCacheLookup(
            cache_key=cache_key,
            cache_hit=False,
            evidence_class=evidence_class,
            result=normalized_result,
        )

    def get_or_compute(
        self,
        identity: Mapping[str, Any],
        *,
        evidence_class: str,
        compute: Callable[[], Mapping[str, Any]],
    ) -> ResultCacheLookup:
        cached = self.get(identity)
        if cached is not None:
            if cached.evidence_class != evidence_class:
                raise ResultCacheCorruptionError(
                    "cached evidence class differs from the requested evidence class"
                )
            return cached
        result = compute()
        return self.put(identity, result, evidence_class=evidence_class)


__all__ = [
    "ExactResultCache",
    "ResultCacheCorruptionError",
    "ResultCacheLookup",
    "build_exact_result_identity",
]
