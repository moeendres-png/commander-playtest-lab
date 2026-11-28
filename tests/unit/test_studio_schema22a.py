"""Studio Schema 22a (#1703 option B, #1856 option B; Owner decision of 2026-11-28).

Numbered migration 21 -> 22: ``simulation_run`` gains ``games_drawn`` / ``games_decided``
(nullable, NULL = unknown, never 0, no backfill), a file store is backed up before it is migrated
(fail closed), ``migrate --dry-run`` shows the effect on a copy, writers fill the columns and the
pod matrix prefers them. All data is synthetic.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from commander_lab.studio import __main__ as studio_cli
from commander_lab.studio import backup as backup_module
from commander_lab.studio import builder, importers, migrate
from commander_lab.studio import simulations as simulations_module
from commander_lab.studio import store as store_module
from commander_lab.studio.simulations import BatchSimulation, GameSummary
from commander_lab.studio.store import DATABASE_NAME, StudioStore

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "studio_schema21.sql"
NEW_COLUMNS = {"games_drawn", "games_decided"}
COMMANDER = "Synthetic Commander"


def _make_21_store(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / DATABASE_NAME
    raw = sqlite3.connect(path)
    raw.executescript(FIXTURE.read_text(encoding="utf-8"))
    raw.commit()
    raw.close()
    return path


def _columns(path: Path, table: str = "simulation_run") -> set[str]:
    raw = sqlite3.connect(path)
    try:
        return {str(r[1]) for r in raw.execute(f"PRAGMA table_info({table})")}
    finally:
        raw.close()


def _version(path: Path) -> str:
    raw = sqlite3.connect(path)
    try:
        return str(raw.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()[0])
    finally:
        raw.close()


def test_schema_version_is_22() -> None:
    assert store_module.SCHEMA_VERSION == 22


def test_new_store_has_the_columns_and_needs_no_backup(tmp_path: Path) -> None:
    folder = tmp_path / "data"
    store = StudioStore.open(folder)
    store.close()
    assert _columns(folder / DATABASE_NAME) >= NEW_COLUMNS
    assert not (tmp_path / "data-backups").exists()
    memory = StudioStore.in_memory()
    try:
        assert {
            str(r["name"]) for r in memory.connection.execute("PRAGMA table_info(simulation_run)")
        } >= NEW_COLUMNS
    finally:
        memory.close()


def test_fixture_is_a_real_schema_21_store(tmp_path: Path) -> None:
    path = _make_21_store(tmp_path / "data")
    assert _version(path) == "21"
    assert not NEW_COLUMNS & _columns(path)


def test_schema_21_store_migrates_keeps_rows_and_leaves_new_columns_null(tmp_path: Path) -> None:
    path = _make_21_store(tmp_path / "data")
    store = StudioStore.open(tmp_path / "data")
    try:
        assert _version(path) == "22"
        rows = store.connection.execute(
            "SELECT run_id, games_completed, win_rate, games_drawn, games_decided "
            "FROM simulation_run ORDER BY run_id"
        ).fetchall()
    finally:
        store.close()
    assert [r["run_id"] for r in rows] == ["run-a", "run-b", "run-c"]
    assert [r["games_completed"] for r in rows] == [4, 2, 0]
    assert all(r["games_drawn"] is None and r["games_decided"] is None for r in rows)


def test_backup_is_written_before_the_alter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _make_21_store(tmp_path / "data")
    seen: dict[str, object] = {}
    real = backup_module.create_backup

    def spy(data_folder: str | Path, destination_root: str | Path, **kwargs: object):  # type: ignore[no-untyped-def]
        seen["columns"] = _columns(path)
        seen["version"] = _version(path)
        seen["destination"] = Path(destination_root)
        return real(data_folder, destination_root, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(backup_module, "create_backup", spy)
    StudioStore.open(tmp_path / "data").close()
    assert seen["version"] == "21"
    assert not NEW_COLUMNS & seen["columns"]  # type: ignore[operator]
    destination = seen["destination"]
    assert isinstance(destination, Path)
    assert destination.name.startswith("pre-schema-22-")
    assert not destination.is_relative_to(tmp_path / "data")  # a backup never lies in the store
    made = list(destination.glob("commander-studio-backup-*/" + DATABASE_NAME))
    assert len(made) == 1
    assert _version(made[0]) == "21"  # the backup holds the store as it was
    assert _version(path) == "22"


def test_a_failed_backup_leaves_the_store_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _make_21_store(tmp_path / "data")
    before = path.read_bytes()

    def boom(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise OSError("disk full")

    monkeypatch.setattr(backup_module, "create_backup", boom)
    with pytest.raises(OSError, match="disk full"):
        StudioStore.open(tmp_path / "data")
    assert _version(path) == "21"
    assert not NEW_COLUMNS & _columns(path)
    assert path.read_bytes() == before


def test_migration_is_idempotent(tmp_path: Path) -> None:
    path = _make_21_store(tmp_path / "data")
    StudioStore.open(tmp_path / "data").close()
    backups = list((tmp_path / "data-backups").iterdir())
    StudioStore.open(tmp_path / "data").close()  # the second open: no second backup
    assert list((tmp_path / "data-backups").iterdir()) == backups
    raw = sqlite3.connect(path)
    raw.row_factory = sqlite3.Row
    try:
        store_module._migrate_schema_22(raw)
        store_module._migrate_schema_22(raw)
        names = [str(r["name"]) for r in raw.execute("PRAGMA table_info(simulation_run)")]
    finally:
        raw.close()
    assert names.count("games_drawn") == 1 and names.count("games_decided") == 1


def test_migration_adds_only_the_missing_column(tmp_path: Path) -> None:
    raw = sqlite3.connect(":memory:")
    raw.row_factory = sqlite3.Row
    raw.executescript(FIXTURE.read_text(encoding="utf-8"))
    raw.execute("ALTER TABLE simulation_run ADD COLUMN games_drawn INTEGER")
    store_module._migrate_schema_22(raw)
    names = {str(r["name"]) for r in raw.execute("PRAGMA table_info(simulation_run)")}
    assert names >= NEW_COLUMNS


def test_dry_run_leaves_the_real_file_byte_identical_and_reports(tmp_path: Path) -> None:
    path = _make_21_store(tmp_path / "data")
    before = path.read_bytes()
    report = migrate.dry_run(tmp_path / "data")
    assert path.read_bytes() == before
    assert not (tmp_path / "data-backups").exists()
    assert report["current_version"] == 21 and report["target_version"] == 22
    assert report["integrity_check"] == "ok"
    tables = report["tables"]
    assert isinstance(tables, dict)
    assert tables["simulation_run"] == {"before": 3, "after": 3}
    assert report["columns_added"]["simulation_run"] == ["games_drawn", "games_decided"]  # type: ignore[index]
    sha = report["state_export_sha256"]
    assert isinstance(sha, dict)
    assert len(str(sha["before"])) == 64 and len(str(sha["after"])) == 64
    assert sha["before"] == sha["after"]  # additive columns change no exported user state
    assert report["real_store_written"] is False


def test_dry_run_cli_text_and_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _make_21_store(tmp_path / "data")
    before = path.read_bytes()
    assert studio_cli.main(["--data", str(tmp_path / "data"), "migrate", "--dry-run"]) == 0
    text = capsys.readouterr().out
    assert "21" in text and "22" in text and "simulation_run" in text and "games_drawn" in text
    assert (
        studio_cli.main(["--data", str(tmp_path / "data"), "migrate", "--dry-run", "--json"]) == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["target_version"] == 22
    assert path.read_bytes() == before


def test_migrate_without_dry_run_only_explains(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _make_21_store(tmp_path / "data")
    before = path.read_bytes()
    assert studio_cli.main(["--data", str(tmp_path / "data"), "migrate"]) == 0
    assert "backup" in capsys.readouterr().out.lower()
    assert path.read_bytes() == before


def _batch(tmp_path: Path, games: list[GameSummary]) -> tuple[BatchSimulation, dict[str, object]]:
    summary = simulations_module.aggregate_batch_results(games, pod_name="precon")
    batch = BatchSimulation(
        batch_id="s22a",
        data_folder=tmp_path,
        deck_id="chulane",
        revision_id="rev-x",
        pod_name="precon",
        opponent_paths=[],
        seeds=[g.seed for g in games],
        initial_games=games,
    )
    return batch, summary


def test_the_batch_writer_stores_drawn_and_decided(tmp_path: Path) -> None:
    games = [
        GameSummary("g1", 1, "finished", winner_seats=[0], table_size=4),
        GameSummary("g2", 2, "finished", winner_seats=[1], table_size=4),
        GameSummary("g3", 3, "finished", winner_seats=[], table_size=4),  # a draw
    ]
    store = StudioStore.open(tmp_path / "data")
    try:
        batch, summary = _batch(tmp_path, games)
        run_id = simulations_module.save_batch_to_store(store, batch, summary)
        row = store.connection.execute(
            "SELECT games_completed, games_drawn, games_decided, win_rate "
            "FROM simulation_run WHERE run_id = ?",
            (run_id,),
        ).fetchone()
    finally:
        store.close()
    assert (row["games_completed"], row["games_drawn"], row["games_decided"]) == (3, 1, 2)
    assert row["win_rate"] == 0.5  # wins / decided: the base the new column documents


def test_a_summary_without_the_classes_stores_null_never_zero(tmp_path: Path) -> None:
    games = [GameSummary("g1", 1, "finished", winner_seats=[0], table_size=4)]
    store = StudioStore.open(tmp_path / "data")
    try:
        batch, summary = _batch(tmp_path, games)
        summary.pop("games_drawn")
        summary.pop("games_decided")
        run_id = simulations_module.save_batch_to_store(store, batch, summary)
        row = store.connection.execute(
            "SELECT games_drawn, games_decided FROM simulation_run WHERE run_id = ?", (run_id,)
        ).fetchone()
    finally:
        store.close()
    assert (row["games_drawn"], row["games_decided"]) == (None, None)


def test_import_simulation_writes_null_where_draws_are_unknown(tmp_path: Path) -> None:
    report = tmp_path / "sim.json"
    report.write_text(
        json.dumps(
            {
                "plan": {
                    "pod": "precon",
                    "deck_id": "custom/x",
                    "seeds": [1, 2],
                    "games_planned": 2,
                },
                "summary": {
                    "games_completed": 2,
                    "games_failed": 0,
                    "wins_fractional": 1.0,
                    "win_rate_completed_games": 0.5,
                },
            }
        ),
        encoding="utf-8",
    )
    store = StudioStore.open(tmp_path / "data")
    try:
        importers.import_simulation_report(store, report, engine_pin="pin")
        row = store.connection.execute(
            "SELECT games_drawn, games_decided FROM simulation_run"
        ).fetchone()
    finally:
        store.close()
    assert (row["games_drawn"], row["games_decided"]) == (None, None)


def _insert_run(
    store: StudioStore,
    run_id: str,
    *,
    completed: int,
    wins: float,
    win_rate: float | None,
    drawn: int | None,
    decided: int | None,
) -> None:
    store.connection.execute(
        "INSERT OR IGNORE INTO source(source_id, data_class, title, sha256, imported_at) "
        "VALUES ('src-1', 'SIMULATED_RESULT', 't', 'aa', '2026-11-01T00:00:00Z')"
    )
    store.connection.execute(
        "INSERT INTO simulation_run(run_id, deck_id, pod, engine_pin, pilot_policy, seeds, "
        "games_planned, games_completed, games_failed, wins_fractional, win_rate, "
        "hand_dwell_status, source_id, games_drawn, games_decided) "
        "VALUES (?, 'd', 'precon', 'pin', 'p', '[]', ?, ?, 0, ?, ?, 'NOT_MEASURED', 'src-1', ?, ?)",
        (run_id, completed, completed, wins, win_rate, drawn, decided),
    )
    store.connection.execute(
        "INSERT INTO commander_binding(kind, key, commander_name, basis) "
        "VALUES ('simulation_run', ?, ?, 'DECK_REVISION_COMMANDER')",
        (run_id, COMMANDER),
    )
    store.connection.commit()


def test_list_simulations_carries_the_two_fields(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "data")
    try:
        _insert_run(store, "r1", completed=12, wins=5.0, win_rate=0.5, drawn=2, decided=10)
        runs = builder.list_simulations(store, [COMMANDER])
    finally:
        store.close()
    assert (runs[0]["games_drawn"], runs[0]["games_decided"]) == (2, 10)


def test_pod_matrix_base_is_decided_games_when_known(tmp_path: Path) -> None:
    """#1856: 5 wins in 12 finished games, 2 of them draws: 50.0 % of 10 decided, not 41.7 %."""
    store = StudioStore.open(tmp_path / "data")
    try:
        _insert_run(store, "r1", completed=12, wins=5.0, win_rate=0.5, drawn=2, decided=10)
        matrix = builder.pod_matchup_matrix(store, [COMMANDER])
    finally:
        store.close()
    pod = matrix["pods"][0]  # type: ignore[index]
    assert pod["win_rate"] == 0.5
    assert pod["games_drawn"] == 2 and pod["games_decided"] == 10
    assert pod["draws_known"] is True


def test_pod_matrix_keeps_todays_figure_and_flags_unknown_draws_when_null(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "data")
    try:
        _insert_run(store, "r1", completed=12, wins=5.0, win_rate=0.5, drawn=None, decided=None)
        matrix = builder.pod_matchup_matrix(store, [COMMANDER])
    finally:
        store.close()
    pod = matrix["pods"][0]  # type: ignore[index]
    assert pod["win_rate"] == round(5.0 / 12, 4)  # 41.7 %: today's figure, a draw counts as a loss
    assert pod["games_drawn"] is None and pod["games_decided"] is None
    assert pod["draws_known"] is False


def test_js_pod_matrix_uses_decided_base_and_marks_unknown(tmp_path: Path) -> None:
    from tests.unit.test_studio_static_guards import _interim_js

    known = {
        "games_completed": 12,
        "wins_fractional": 5.0,
        "win_rate": 0.5,
        "games_drawn": 2,
        "games_decided": 10,
    }
    unknown = {
        "games_completed": 12,
        "wins_fractional": 5.0,
        "win_rate": 0.5,
        "games_drawn": None,
        "games_decided": None,
    }
    out = _interim_js(
        f"[podWinFigure([{json.dumps(known)}]), podWinFigure([{json.dumps(unknown)}])]"
    )
    assert out == [
        {"wins": 5.0, "base": 10, "drawsHidden": False},
        {"wins": 5.0, "base": 12, "drawsHidden": True},
    ]
    assert _interim_js(f"runHasHiddenDraws({json.dumps(known)})") is False
    assert _interim_js(f"runHasHiddenDraws({json.dumps(unknown)})") is True


def test_the_dry_run_leaves_nothing_next_to_the_store(tmp_path: Path) -> None:
    _make_21_store(tmp_path / "data")
    assert migrate.dry_run(tmp_path / "data")["current_version"] == 21
    assert sorted(p.name for p in (tmp_path / "data").iterdir()) == [DATABASE_NAME]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["data"]


def test_legacy_series_record_seat_curve_leaves_a_draw_out_of_its_base(tmp_path: Path) -> None:
    """#1856: the fallback seat curve of a legacy record uses the games with a winner, like
    every other seat curve (a draw is neither a win nor a loss)."""
    from starlette.testclient import TestClient

    from commander_lab.studio import games
    from commander_lab.studio.web import create_app

    StudioStore.open(tmp_path).close()
    gdir = games.games_folder(tmp_path)
    gdir.mkdir(parents=True, exist_ok=True)
    record = {
        "batch_id": "legacy-draw",
        "deck_id": "chulane",
        "pod": "precon",
        "opponent_ids": ["a", "b", "c"],
        "status": "completed",
        "games": [
            {"game_id": "g0", "seed": 1000, "status": "finished", "winner_seats": [0]},
            {"game_id": "g1", "seed": 1001, "status": "finished", "winner_seats": []},
        ],
        "summary": {"games_completed": 2, "games_planned": 2},
    }
    (gdir / "legacy-draw.series.json").write_text(json.dumps(record), encoding="utf-8")
    body = TestClient(create_app(tmp_path)).get("/api/simulations/batch/legacy-draw").json()
    assert body["validity_block"]["seat_curve"]["seats"][0]["n_of_N"] == "1/1"
