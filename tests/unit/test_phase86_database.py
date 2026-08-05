from __future__ import annotations

from pathlib import Path

import pytest

from commander_lab.storage import (
    backup_database,
    check_database,
    migrate_database,
    restore_database,
    seal_experiment,
)


def _experiment() -> dict[str, object]:
    return {
        "experiment_id": "exp-1",
        "hypothesis": "Variant improves paired placement.",
        "baseline": "korvold/current",
        "variant": {"remove": "A", "add": "B"},
        "scenarios": ["primary", "holdout"],
        "seeds": [1, 2, 3],
        "acceptance_criteria": {"holdout_nonnegative": True},
    }


def test_database_migration_integrity_backup_restore_and_sealed_experiment(tmp_path: Path) -> None:
    database = tmp_path / "lab.sqlite3"
    assert migrate_database(database)["status"] == "passed"
    first = seal_experiment(database, _experiment())
    assert first["sealed_payload_hash"]
    assert seal_experiment(database, _experiment()) == first
    modified = _experiment()
    modified["hypothesis"] = "Changed after results"
    with pytest.raises(ValueError, match="cannot be changed"):
        seal_experiment(database, modified)
    backup = backup_database(database, tmp_path / "backup.sqlite3")
    restored = restore_database(backup, tmp_path / "restored.sqlite3")
    assert check_database(restored)["status"] == "passed"
