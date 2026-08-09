from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return {str(key): value for key, value in payload.items()}


def _source_observation(root: Path, key: str, spec: dict[str, Any]) -> dict[str, Any]:
    path = root / spec["import_path"]
    payload = _load(path)
    expected_hash = spec["sha256"]
    expected_id = spec["drive_file_id"]
    if key == "inventory":
        observed_hash = payload.get("source_sha256")
        observed_id = payload.get("source_drive_file_id")
        detail: dict[str, Any] = {"active_physical_rows": payload.get("active_physical_rows")}
    elif key == "korvold_rogshai_decks":
        observed_hash = payload.get("source_sha256")
        observed_id = payload.get("source_drive_file_id")
        manifest = _load(root / "data/decks/manifest.json")
        observed_deck_hashes = {
            deck_id: row.get("deck_hash") for deck_id, row in manifest.get("decks", {}).items()
        }
        detail = {
            "expected_deck_hashes": spec.get("deck_hashes", {}),
            "observed_deck_hashes": observed_deck_hashes,
            "deck_hashes_match": all(
                observed_deck_hashes.get(deck_id) == digest
                for deck_id, digest in spec.get("deck_hashes", {}).items()
            ),
        }
    else:
        observed_hash = payload.get("source_sha256")
        observed_id = payload.get("source_drive_file_id")
        detail = {"deck_records": len(payload.get("decks", []))}
    match = (
        observed_hash == expected_hash
        and observed_id == expected_id
        and detail.get("deck_hashes_match", True)
    )
    return {
        "source": key,
        "status": "MATCH" if match else "DIFFERENT",
        "expected_drive_file_id": expected_id,
        "observed_drive_file_id": observed_id,
        "expected_sha256": expected_hash,
        "observed_sha256": observed_hash,
        **detail,
    }


def audit_current_sources(root: str | Path) -> dict[str, Any]:
    root_path = Path(root)
    registry = _load(root_path / "data/sync/current_sources.json")
    checks = [
        _source_observation(root_path, key, spec) for key, spec in registry["sources"].items()
    ]
    return {
        "schema_version": 1,
        "data_as_of": registry["data_as_of"],
        "status": "MATCH" if all(row["status"] == "MATCH" for row in checks) else "DIFFERENT",
        "checks": checks,
        "scopes": registry.get("scopes", {}),
        "mutated": False,
    }


def sync_current_sources(root: str | Path, *, dry_run: bool = True) -> dict[str, Any]:
    audit = audit_current_sources(root)
    actions = []
    for row in audit["checks"]:
        actions.append(
            {
                "source": row["source"],
                "status": row["status"],
                "action": "would_not_touch" if row["status"] == "MATCH" else "would_update",
            }
        )
    if not dry_run and audit["status"] != "MATCH":
        raise RuntimeError(
            "Canonical source bytes differ from the prepared imports. "
            "Provide and import the canonical Drive exports before "
            "sync; this command has no hidden Google access."
        )
    return {
        "schema_version": 1,
        "dry_run": dry_run,
        "status": audit["status"],
        "actions": actions,
        "mutated": False,
        "note": (
            "Sync finalizes only already-prepared canonical imports; it "
            "never optimizes decks or fetches Drive sources implicitly."
        ),
    }
