from __future__ import annotations

import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from commander_lab.cli.app import app
from commander_lab.models import RuntimeValidationLevel
from commander_lab.models.rules import ValidationLevel
from commander_lab.storage import check_database, migrate_database
from commander_lab.tools.registry import TOOL_DEFINITIONS


FORBIDDEN_TOOLS = {
    "ingest_playtest",
    "calibrate",
    "ingest_local_game",
    "update_local_opponent_profile",
    "inspect_local_meta",
    "compare_observed_to_assumed",
    "detect_local_meta_drift",
    "build_local_meta_scenarios",
    "generate_local_meta_report",
}

FORBIDDEN_CLI = {
    "ingest-playtest",
    "calibrate-playtests",
    "validate-phase9",
}


def test_manual_playtest_tools_are_absent_from_active_registry() -> None:
    names = {definition.name for definition in TOOL_DEFINITIONS}
    assert names.isdisjoint(FORBIDDEN_TOOLS)


def test_manual_playtest_commands_are_absent_from_cli_help() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in FORBIDDEN_CLI:
        assert command not in result.stdout


def test_database_migration_removes_known_legacy_manual_playtest_tables(tmp_path: Path) -> None:
    database = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript(
            """
            CREATE TABLE playtests(id INTEGER PRIMARY KEY);
            CREATE TABLE playtest_games(id INTEGER PRIMARY KEY);
            CREATE TABLE calibration_profiles(id INTEGER PRIMARY KEY);
            CREATE TABLE local_games(id INTEGER PRIMARY KEY);
            CREATE TABLE local_opponent_profiles(id INTEGER PRIMARY KEY);
            """
        )
    result = migrate_database(database)
    assert result["status"] == "passed"
    assert result["schema_version"] >= 2
    assert result["manual_playtest_migration_status"] == "removed_legacy_tables"
    with sqlite3.connect(database) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert not tables.intersection(
        {
            "playtests",
            "playtest_games",
            "calibration_profiles",
            "local_games",
            "local_opponent_profiles",
        }
    )
    assert check_database(database)["manual_playtest_migration_status"] == "removed_legacy_tables"


def test_active_validation_levels_are_exactly_the_non_empirical_three() -> None:
    expected = {"structural_only", "tactical_oracle", "external_rules_engine"}
    assert {item.value for item in ValidationLevel} == expected
    assert {item.value for item in RuntimeValidationLevel} == expected


def test_removed_manual_playtest_models_and_schemas_are_not_active(repo_root: Path) -> None:
    schema_names = {path.name.lower() for path in (repo_root / "schemas/models").glob("*.json")}
    assert not any("playtest" in name or "calibrat" in name for name in schema_names)
    source_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in (repo_root / "src").rglob("*.py")
    )
    for token in (
        "real_playtest_observed",
        "real_playtest_calibration_status",
        "real_imported_games",
        "ingest_playtest",
        "ingest_local_game",
    ):
        assert token not in source_text
