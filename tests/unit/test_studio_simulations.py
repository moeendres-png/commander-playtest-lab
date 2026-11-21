"""Unit and integration tests for Studio batch simulations (M5).

Verifies:
- Wilson score interval calculation (no false certainty for small samples).
- Telemetry extraction from recorded game logs.
- Batch results aggregation (win rate, denominator, confidence intervals, mean rounds, card stats).
- BatchSimulationManager execution with deterministic seeds and process isolation.
- Cancellation and graceful shutdown.
- Store persistence into simulation_run and simulation_card tables.
- Web API endpoints (/api/simulations/batch, /api/simulations/batch/{id}, etc.).
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
import types
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from commander_lab.studio import builder, games, play
from commander_lab.studio import simulations as simulations_module
from commander_lab.studio import store as store_module
from commander_lab.studio.decks import RevisionCard, create_revision
from commander_lab.studio.launch import POD_PRESETS, SeriesEngine
from commander_lab.studio.simulations import (
    BatchSimulation,
    GameSummary,
    SimulationBatchManager,
    aggregate_batch_results,
    extract_game_log_telemetry,
    opponent_table,
    wilson_score_interval,
)
from commander_lab.studio.store import DataClass, StudioStore
from commander_lab.studio.web import create_app

HEADER: dict[str, object] = {
    "engine_commit": "f4d12f6e80",
    "pilot": "GenericCommanderPilot 1.0.0",
    "decision_policy": "xmage-full-game-policy-1.0.0",
    "strategy": "generic",
    "seats": [
        {"seat": 0, "deck_id": "chulane", "commanders": ["Chulane, Teller of Tales"]},
        {"seat": 1, "deck_id": "opp1", "commanders": ["Osgir, the Reconstructor"]},
        {"seat": 2, "deck_id": "opp2", "commanders": ["Bello, Bard of the Brambles"]},
        {"seat": 3, "deck_id": "opp3", "commanders": ["Emmara, Soul of the Accord"]},
    ],
}


def _mock_decision(
    turn: int = 1,
    seat: int = 0,
    hand: list[str] | None = None,
    dc: str = "play_land",
    chosen: list[str] | None = None,
) -> dict[str, object]:
    hand_cards = hand if hand is not None else ["Forest", "Sol Ring"]
    players = [
        {
            "seat": 0,
            "player_id": "p0",
            "life": 40,
            "hand": [{"name": c} for c in hand_cards],
        },
        {"seat": 1, "player_id": "p1", "life": 40, "hand_count": 7},
        {"seat": 2, "player_id": "p2", "life": 40, "hand_count": 7},
        {"seat": 3, "player_id": "p3", "life": 40, "hand_count": 7},
    ]
    return {
        "seat": seat,
        "decision_class": dc,
        "pilot_state": {
            "turn_number": turn,
            "phase": "main1",
            "active_player_id": f"p{seat}",
            "players": players,
            "stack": [],
        },
        "legal_options": [
            {"option_id": "o1", "label": "Pass priority"},
            {"option_id": "o2", "label": (chosen[0] if chosen else "Forest")},
        ],
    }


def _seed_test_deck(store: StudioStore, deck_id: str = "chulane") -> str:
    src = store.register_source(
        data_class=DataClass.NORMALIZED_SOURCE,
        title="test_seed_source",
        sha256="0" * 64,
    )
    store.connection.execute(
        "INSERT OR IGNORE INTO card(card_id, oracle_name, color_identity, source_id) "
        "VALUES ('c_chulane', 'Chulane, Teller of Tales', 'WUG', ?)",
        (src,),
    )
    store.connection.execute(
        "INSERT OR IGNORE INTO card(card_id, oracle_name, color_identity, source_id) "
        "VALUES ('c_sol_ring', 'Sol Ring', 'C', ?)",
        (src,),
    )
    store.connection.execute(
        "INSERT OR IGNORE INTO card(card_id, oracle_name, color_identity, source_id) "
        "VALUES ('c_forest', 'Forest', 'G', ?)",
        (src,),
    )
    cards = [
        RevisionCard("c_chulane", 1, "commander"),
        RevisionCard("c_sol_ring", 1, "main"),
        RevisionCard("c_forest", 35, "main"),
    ]
    return create_revision(store, deck_id=deck_id, name="Test Chulane Deck", cards=cards)


def test_wilson_score_interval_properties() -> None:
    # 0 games: 0.0, 0.0
    assert wilson_score_interval(0.0, 0) == (0.0, 0.0)

    # 0 wins out of 10: non-zero upper bound (reflects uncertainty!)
    lower, upper = wilson_score_interval(0.0, 10)
    assert lower == 0.0
    assert 0.20 <= upper <= 0.35

    # 10 wins out of 10: non-one lower bound
    lower, upper = wilson_score_interval(10.0, 10)
    assert 0.65 <= lower <= 0.80
    assert upper == 1.0

    # 10 wins out of 20 (50%): symmetric around 0.5
    lower, upper = wilson_score_interval(10.0, 20)
    assert 0.29 <= lower <= 0.35
    assert 0.65 <= upper <= 0.71
    assert abs((lower + upper) / 2.0 - 0.5) < 0.01


def test_extract_game_log_telemetry(tmp_path: Path) -> None:
    recorder = games.GameRecorder(tmp_path, "game-telemetry", {**HEADER, "seed": 42})
    dec1 = _mock_decision(
        turn=1, seat=0, hand=["Sol Ring", "Forest"], dc="play_land", chosen=["Forest"]
    )
    recorder.record(dec1, {"selected_option_ids": ["o2"]})
    dec2 = _mock_decision(turn=2, seat=0, hand=["Sol Ring"], dc="cast_spell", chosen=["Sol Ring"])
    recorder.record(dec2, {"selected_option_ids": ["o2"]})
    recorder.close({"status": "finished", "winner_seats": [0], "decision_count": 2})

    summary = extract_game_log_telemetry(tmp_path, "game-telemetry", candidate_seat=0)
    assert summary.game_id == "game-telemetry"
    assert summary.seed == 42
    assert summary.status == "finished"
    assert summary.candidate_won is True
    assert summary.winner_seats == [0]
    assert summary.rounds == 2
    assert "Sol Ring" in summary.observed_cards
    assert summary.observed_cards["Sol Ring"]["offered"] is True
    assert summary.observed_cards["Sol Ring"]["cast"] is True
    assert summary.observed_cards["Sol Ring"]["first_cast_round"] == 2
    assert "Forest" in summary.observed_cards
    assert summary.observed_cards["Forest"]["first_cast_round"] == 1


def test_aggregate_batch_results() -> None:
    g1 = GameSummary(
        game_id="g1",
        seed=1001,
        status="finished",
        winner_seats=[0],
        rounds=10,
        candidate_won=True,
        observed_cards={
            "Sol Ring": {"offered": True, "cast": True, "cast_count": 1, "first_cast_round": 1},
            "Forest": {"offered": True, "cast": True, "cast_count": 1, "first_cast_round": 1},
            "Counterspell": {
                "offered": True,
                "cast": False,
                "cast_count": 0,
                "first_cast_round": None,
            },
        },
    )
    g2 = GameSummary(
        game_id="g2",
        seed=1002,
        status="finished",
        winner_seats=[1],
        rounds=12,
        candidate_won=False,
        observed_cards={
            "Forest": {"offered": True, "cast": True, "cast_count": 2, "first_cast_round": 1},
            "Counterspell": {"offered": True, "cast": True, "cast_count": 1, "first_cast_round": 4},
        },
    )
    g3 = GameSummary(
        game_id="g3",
        seed=1003,
        status="failed",
        failure_class="EngineError",
    )

    summary = aggregate_batch_results([g1, g2, g3])
    assert summary["games_planned"] == 3
    assert summary["games_completed"] == 2
    assert summary["games_failed"] == 1
    assert summary["wins_fractional"] == 1.0
    assert summary["win_rate"] == 0.5
    assert summary["win_rate_percent"] == 50.0
    assert summary["mean_rounds"] == 11.0

    cards = {c["card_name"]: c for c in summary["cards"]}  # type: ignore[union-attr]
    assert cards["Sol Ring"]["games_completed"] == 2
    assert cards["Sol Ring"]["games_offered"] == 1
    assert cards["Sol Ring"]["games_cast_after_offer"] == 1
    assert cards["Sol Ring"]["games_rotted"] == 0

    assert cards["Counterspell"]["games_offered"] == 2
    assert cards["Counterspell"]["games_cast_after_offer"] == 1
    assert cards["Counterspell"]["games_rotted"] == 1
    assert cards["Counterspell"]["cast_count"] == 1
    assert cards["Counterspell"]["mean_first_cast_round"] == 4.0
    # the mean covers only the games in which the card was cast: n/N travels with it
    assert cards["Counterspell"]["first_cast_round_games_reached"] == 1
    assert cards["Counterspell"]["first_cast_round_games_not_reached"] == 1
    assert cards["Counterspell"]["first_cast_round_quartiles"] == {
        "q1": 4,
        "median": 4,
        "q3": None,
    }
    assert cards["Forest"]["first_cast_round_games_reached"] == 2
    # the denominator is every finished game, not the games in which the card was offered
    assert cards["Sol Ring"]["first_cast_round_games_reached"] == 1
    assert cards["Sol Ring"]["first_cast_round_games_not_reached"] == 1
    assert cards["Forest"]["first_cast_round_quartiles"] == {"q1": 1, "median": 1, "q3": 1}


def test_censored_round_quartiles_keep_not_reached_games_in_the_denominator() -> None:
    from commander_lab.studio.simulations import censored_round_quartiles

    # cast in 1 of 4 games: early in that game, but the median game never cast it
    assert censored_round_quartiles([3], 4) == {"q1": 3, "median": None, "q3": None}
    assert censored_round_quartiles([7, 2, 5], 3) == {"q1": 2, "median": 5, "q3": 7}
    assert censored_round_quartiles([], 0) == {"q1": None, "median": None, "q3": None}
    assert censored_round_quartiles([], 5) == {"q1": None, "median": None, "q3": None}


def test_save_batch_to_store(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path)
    try:
        rev_id = _seed_test_deck(store)
        mgr = SimulationBatchManager()

        # Dummy mock game executor
        def mock_executor(**kwargs: object) -> dict[str, object]:
            seed = int(kwargs.get("seed") or 0)
            return {
                "status": "finished",
                "winner_seats": [0] if seed % 2 == 0 else [1],
                "decision_count": 50,
                "rounds": 10,
            }

        batch = mgr.start_batch(
            store,
            tmp_path,
            revision_id=rev_id,
            pod="precon",
            games_count=4,
            base_seed=100,
            game_executor=mock_executor,
        )

        # Wait for worker thread to finish
        deadline = time.monotonic() + 5.0
        while batch.status in {"pending", "running"} and time.monotonic() < deadline:
            time.sleep(0.05)

        assert batch.status == "completed"
        assert batch.run_id is not None

        # Verify saved in simulation_run
        run = store.connection.execute(
            "SELECT * FROM simulation_run WHERE run_id = ?", (batch.run_id,)
        ).fetchone()
        assert run is not None
        assert run["deck_id"] == "chulane"
        assert run["pod"] == "precon"
        assert run["games_completed"] == 4
        assert run["games_failed"] == 0
        assert json.loads(run["seeds"]) == [100, 101, 102, 103]
        assert run["wins_fractional"] == 2.0
        assert run["win_rate"] == 0.5
        assert run["mean_rounds"] == 10.0
        # #1657: the revision the series played; this 37-card test deck cannot be loaded as a
        # Commander deck, so its played deck state is unknown (NULL), never guessed
        assert run["revision_id"] == rev_id
        assert run["deck_hash"] is None

        # Verify list_simulations readback
        # the series is bound to the commander of the deck revision it played
        assert builder.list_simulations(store, ["Another Commander"]) == []
        sim_list = builder.list_simulations(store, ["Chulane, Teller of Tales"])
        assert len(sim_list) == 1
        assert sim_list[0]["run_id"] == batch.run_id
        assert sim_list[0]["pod"] == "precon"
    finally:
        store.close()


def test_batch_cancellation(tmp_path: Path) -> None:
    store = StudioStore.in_memory()
    try:
        rev_id = _seed_test_deck(store)
        mgr = SimulationBatchManager()

        def slow_executor(**kwargs: object) -> dict[str, object]:
            time.sleep(0.1)
            return {"status": "finished", "winner_seats": [0], "rounds": 8}

        batch = mgr.start_batch(
            store,
            tmp_path,
            revision_id=rev_id,
            pod="precon",
            games_count=20,
            base_seed=500,
            game_executor=slow_executor,
        )

        # Wait until first game starts, then cancel
        time.sleep(0.15)
        mgr.cancel_batch(batch.batch_id)

        deadline = time.monotonic() + 3.0
        while batch.status in {"pending", "running"} and time.monotonic() < deadline:
            time.sleep(0.05)

        assert batch.status == "cancelled"
        assert batch.current_index < 20
        assert len(batch._games) < 20
    finally:
        store.close()


def test_simulation_web_endpoints(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path)
    try:
        rev_id = _seed_test_deck(store)
    finally:
        store.close()

    app = create_app(tmp_path)
    client = TestClient(app)

    # List empty batches initially
    res = client.get("/api/simulations/batches", headers={"X-Studio": "1"})
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    # Start a batch via API (fails 409 if engine not installed without mock, which confirms preflight check!)
    res = client.post(
        "/api/simulations/batch",
        headers={"X-Studio": "1"},
        json={"revision_id": rev_id, "pod": "precon", "games_count": 5, "base_seed": 100},
    )
    # Since Java/XMage JAR might not be in tmp_path, it properly raises 409 or starts
    assert res.status_code in {200, 409}

    # If 409, message explains missing engine
    if res.status_code == 409:
        assert "Engine" in res.json()["detail"] or "Java" in res.json()["detail"]


def test_batch_series_rejects_five_and_six_seats_via_api_and_manager(tmp_path: Path) -> None:
    from commander_lab.studio.web import BatchSimulationBody

    assert "allow_unreleased_seats" not in BatchSimulationBody.model_fields

    store = StudioStore.open(tmp_path)
    try:
        rev_id = _seed_test_deck(store)
    finally:
        store.close()

    app = create_app(tmp_path)
    client = TestClient(app)

    for opp_count in (4, 5):
        seats = 1 + opp_count
        opps = [f"precon/d{i}" for i in range(opp_count)]
        res = client.post(
            "/api/simulations/batch",
            headers={"X-Studio": "1"},
            json={
                "revision_id": rev_id,
                "opponent_ids": opps,
                "games_count": 2,
                "base_seed": 100,
            },
        )
        assert res.status_code == 422
        assert f"tables of {seats} seats are locked" in res.json()["detail"]


def test_batch_never_seats_a_stand_in_opponent_and_refuses_seed_step(tmp_path: Path) -> None:
    """B2 (#1658): an unknown opponent or pod is an error, never another precon in its seat;
    the preset seats exactly its three named decks; ``seed_step`` is no longer accepted."""
    from commander_lab.studio import launch

    store = StudioStore.open(tmp_path)
    try:
        rev_id = _seed_test_deck(store)
        mgr = SimulationBatchManager()

        def executor(**kwargs: object) -> dict[str, object]:
            return {"status": "finished", "winner_seats": [0], "decision_count": 5, "rounds": 3}

        for pod, opponents, message in (
            ("precon", ["precon/does-not-exist"], "Unbekanntes Gegner-Deck"),
            ("precon", ["lorehold"], "Unbekanntes Gegner-Deck"),  # no substring match
            ("no-such-pod", None, "Unbekannter Gegnertisch"),
        ):
            with pytest.raises(ValueError, match=message):
                mgr.start_batch(
                    store,
                    tmp_path,
                    revision_id=rev_id,
                    pod=pod,
                    opponent_ids=opponents,
                    games_count=1,
                    game_executor=executor,
                )
        batch = mgr.start_batch(
            store, tmp_path, revision_id=rev_id, pod="precon", games_count=1, game_executor=executor
        )
        _wait(batch)
        by_id = {deck_id: path for deck_id, *_r, path in launch._precons()}
        assert batch.opponent_paths == [by_id[oid] for oid in launch.POD_PRESETS["precon"]]
        assert batch.seeds == [1000]
        # the record names its table, so a resume plays exactly this table again
        assert batch.to_dict()["opponent_ids"] == list(launch.POD_PRESETS["precon"])
    finally:
        store.close()

    client = TestClient(create_app(tmp_path))
    res = client.post(
        "/api/simulations/batch",
        headers={"X-Studio": "1"},
        json={"revision_id": rev_id, "games_count": 2, "base_seed": 100, "seed_step": 4},
    )
    assert res.status_code == 422
    assert "seed_step" in res.text


def test_paired_series_rejects_five_and_six_seats_via_api_and_manager(tmp_path: Path) -> None:
    from commander_lab.studio.paired_series import PairedSeriesManager
    from commander_lab.studio.web import PairedSeriesBody

    assert "allow_unreleased_seats" not in PairedSeriesBody.model_fields

    store = StudioStore.open(tmp_path)
    try:
        rev_id = _seed_test_deck(store)
        app = create_app(tmp_path)
        client = TestClient(app)

        for opp_count in (4, 5):
            seats = 1 + opp_count
            opps = [f"precon/d{i}" for i in range(opp_count)]
            res = client.post(
                "/api/simulations/paired",
                headers={"X-Studio": "1"},
                json={
                    "base_revision_id": rev_id,
                    "variant_revision_id": "rev@other",
                    "opponent_ids": opps,
                },
            )
            assert res.status_code == 422
            assert f"tables of {seats} seats are locked" in res.json()["detail"]

        mgr = PairedSeriesManager()
        with pytest.raises(ValueError, match="tables of 5 seats are locked"):
            mgr.start_series(
                store,
                tmp_path,
                base_revision_id=rev_id,
                variant_revision_id="rev@other",
                opponent_ids=["a", "b", "c", "d"],
            )
    finally:
        store.close()


def test_compare_decks_cli_rejects_five_and_six_seats_by_default(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from commander_lab.studio.__main__ import main as studio_main

    for opp_count in (4, 5):
        seats = 1 + opp_count
        argv = [
            "--data",
            str(tmp_path),
            "compare-decks",
            "--base-deck",
            str(tmp_path / "base.json"),
            "--variant-deck",
            str(tmp_path / "var.json"),
        ]
        for idx in range(opp_count):
            argv.extend(["--opponent", str(tmp_path / f"opp{idx}.json")])
        rc = studio_main(argv)
        captured = capsys.readouterr()
        assert rc != 0
        assert f"tables of {seats} seats are locked" in captured.err

    # Explicit opt-in flag passes the seat check (fails later when reading missing deck files)
    argv_opt = [
        "--data",
        str(tmp_path),
        "compare-decks",
        "--base-deck",
        str(tmp_path / "missing_base.json"),
        "--variant-deck",
        str(tmp_path / "missing_var.json"),
        "--allow-unreleased-seats",
    ]
    for idx in range(4):
        argv_opt.extend(["--opponent", str(tmp_path / f"opp{idx}.json")])
    with pytest.raises(FileNotFoundError):
        studio_main(argv_opt)


# --- deck state of a series (#1657) ------------------------------------------------------


def _wait(batch: object) -> None:
    deadline = time.monotonic() + 5.0
    while batch.status in {"pending", "running"} and time.monotonic() < deadline:
        time.sleep(0.05)


def test_save_batch_to_store_records_the_revision_and_deck_state(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path)
    try:
        _seed_test_deck(store)
        rev_id = create_revision(
            store,
            deck_id="chulane",
            name="Test Chulane Deck",
            cards=[
                RevisionCard("c_chulane", 1, "commander"),
                RevisionCard("c_sol_ring", 1, "main"),
                RevisionCard("c_forest", 98, "main"),
            ],
        )

        def executor(**kwargs: object) -> dict[str, object]:
            return {"status": "finished", "winner_seats": [0], "decision_count": 5, "rounds": 3}

        batch = SimulationBatchManager().start_batch(
            store,
            tmp_path,
            revision_id=rev_id,
            pod="precon",
            games_count=2,
            base_seed=7,
            game_executor=executor,
        )
        _wait(batch)
        assert batch.status == "completed" and batch.run_id is not None
        run = store.connection.execute(
            "SELECT revision_id, deck_hash FROM simulation_run WHERE run_id = ?", (batch.run_id,)
        ).fetchone()
        own = games.games_folder(tmp_path) / "decks" / (rev_id.replace("@", "-") + ".json")
        assert run["revision_id"] == rev_id
        # the hash the game log headers name for this snapshot (``play.load_decks``)
        assert re.fullmatch(r"[0-9a-f]{64}", str(run["deck_hash"]))
        assert run["deck_hash"] == play.snapshot_deck_hash(own)
    finally:
        store.close()


def test_schema_21_store_without_state_columns_gains_them_and_stays_21(tmp_path: Path) -> None:
    """A schema-21 store of before #1657: the columns are added, old rows stay NULL."""
    path = tmp_path / store_module.DATABASE_NAME
    raw = sqlite3.connect(path)
    raw.executescript(store_module._SCHEMA)
    columns = {row[1] for row in raw.execute("PRAGMA table_info(simulation_run)")}
    table_columns = {"opponent_ids", "opponent_set_hash", "table_size"}
    assert not columns & {"revision_id", "deck_hash", *table_columns}  # the old layout
    raw.execute("INSERT INTO meta(key, value) VALUES ('schema_version', '21')")
    raw.execute(
        "INSERT INTO source(source_id, data_class, title, sha256, imported_at) "
        "VALUES ('src:old', 'SIMULATED_RESULT', 'old', ?, '2026-01-01T00:00:00Z')",
        ("0" * 64,),
    )
    raw.execute(
        "INSERT INTO simulation_run(run_id, deck_id, pod, engine_pin, pilot_policy, seeds, "
        "games_planned, games_completed, games_failed, wins_fractional, hand_dwell_status, "
        "source_id) VALUES ('old-run', 'chulane', 'precon', 'pin', 'p', '[]', 1, 1, 0, 1.0, "
        "'NOT_MEASURED', 'src:old')"
    )
    raw.commit()
    raw.close()
    assert store_module.SCHEMA_VERSION == 21
    for _ in range(2):  # the second open finds the columns and changes nothing
        store = StudioStore.open(tmp_path)
        try:
            columns = [
                str(row["name"])
                for row in store.connection.execute("PRAGMA table_info(simulation_run)")
            ]
            assert columns.count("revision_id") == 1 and columns.count("deck_hash") == 1
            # #1688: the table the series played, added the same way, old rows NULL
            assert all(columns.count(name) == 1 for name in table_columns)
            types = {
                str(row["name"]): str(row["type"])
                for row in store.connection.execute("PRAGMA table_info(simulation_run)")
            }
            assert types["table_size"] == "INTEGER" and types["opponent_ids"] == "TEXT"
            unknown = store.connection.execute(
                "SELECT opponent_ids, opponent_set_hash, table_size FROM simulation_run "
                "WHERE run_id = 'old-run'"
            ).fetchone()
            assert tuple(unknown) == (None, None, None)  # "Gegnersatz unbekannt", no backfill
            version = store.connection.execute(
                "SELECT value FROM meta WHERE key = 'schema_version'"
            ).fetchone()
            assert version["value"] == "21"
            old = store.connection.execute(
                "SELECT revision_id, deck_hash FROM simulation_run WHERE run_id = 'old-run'"
            ).fetchone()
            assert (old["revision_id"], old["deck_hash"]) == (None, None)
        finally:
            store.close()


def test_a_column_added_by_another_process_between_check_and_alter_is_no_error() -> None:
    """Two processes opening one store for the first time: the second ALTER finds the column."""
    store = StudioStore.in_memory()
    try:

        class StalePragma:
            def __init__(self, inner: sqlite3.Connection) -> None:
                self.inner = inner

            def execute(self, sql: str, *args: object) -> object:
                if sql.startswith("PRAGMA table_info"):
                    return []  # what the other process saw before its own ALTER
                return self.inner.execute(sql, *args)

        store_module._ensure_simulation_run_state_columns(StalePragma(store.connection))  # type: ignore[arg-type]
        columns = [
            str(row["name"])
            for row in store.connection.execute("PRAGMA table_info(simulation_run)")
        ]
        assert columns.count("revision_id") == 1 and columns.count("deck_hash") == 1
        assert columns.count("opponent_set_hash") == 1 and columns.count("table_size") == 1
    finally:
        store.close()


# --- #1688: the opponent set is a feature of the series, the evidence never adds two up ------

PRESET_IDS = list(POD_PRESETS["precon"])


def _cards_runner(seeds: Sequence[int]) -> Iterator[GameSummary]:
    for seed in seeds:
        yield GameSummary(
            game_id=f"g-{seed}",
            seed=seed,
            status="finished",
            winner_seats=[0],
            rounds=5,
            observed_cards={
                "Forest": {"offered": True, "cast": seed % 2 == 0, "cast_count": seed % 2},
            },
        )


def _next_second() -> None:
    # the batch id carries the start second; two series in one second would share a run id
    start = int(time.time())
    while int(time.time()) == start:
        time.sleep(0.02)


def test_opponent_table_keeps_the_seat_order_and_knows_unknown() -> None:
    encoded, set_hash, size = opponent_table(PRESET_IDS)
    assert json.loads(str(encoded)) == PRESET_IDS and size == 4
    assert re.fullmatch(r"[0-9a-f]{64}", str(set_hash))
    assert opponent_table(list(reversed(PRESET_IDS)))[1] != set_hash  # another seat order
    assert opponent_table(PRESET_IDS[:2])[2] == 3
    assert opponent_table(None) == (None, None, None)


def test_two_series_under_one_pod_name_with_different_tables_stay_apart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Saved series carry their opponent set; evidence and pod matrix never add two tables up,
    and the remembered evidence answer is renewed by the declared series write."""
    from commander_lab.studio import cache
    from tests.unit.test_studio_builder import _deck, _fill

    monkeypatch.setattr(cache, "CHECK", True)  # an undeclared write fails the series
    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    client = TestClient(create_app(tmp_path / "studio"))
    commander = {"commander": "Test Commander"}
    try:
        rev_id = create_revision(store, deck_id="test", name="Test Deck", cards=_deck())
        before = client.get("/api/evidence", params=commander).json()  # remembered answer
        sol = next(c for c in before["cards"] if c["name"] == "Forest")
        assert sol["layers"]["simulated_result"]["groups"] == []
        manager = SimulationBatchManager()
        for opponents, base in ((None, 10), (list(reversed(PRESET_IDS)), 20)):
            _next_second()
            batch = manager.start_batch(
                store,
                tmp_path,
                revision_id=rev_id,
                pod="precon",
                opponent_ids=opponents,
                games_count=4,
                base_seed=base,
                chunk_runner=_cards_runner,
            )
            _wait(batch)
            assert batch.status == "completed" and batch.run_id is not None
        rows = store.connection.execute(
            "SELECT pod, opponent_ids, opponent_set_hash, table_size FROM simulation_run "
            "ORDER BY run_id"
        ).fetchall()
        assert [r["pod"] for r in rows] == ["precon", "precon"]
        assert [json.loads(r["opponent_ids"]) for r in rows] == [
            PRESET_IDS,
            list(reversed(PRESET_IDS)),
        ]
        assert [r["opponent_set_hash"] for r in rows] == [
            opponent_table(PRESET_IDS)[1],
            opponent_table(list(reversed(PRESET_IDS)))[1],
        ]
        assert [r["table_size"] for r in rows] == [4, 4]

        after = client.get("/api/evidence", params=commander).json()
        sol = next(c for c in after["cards"] if c["name"] == "Forest")
        groups = sol["layers"]["simulated_result"]["groups"]
        assert len(groups) == 2  # one pod name, two tables
        assert [(g["runs"], g["games_offered"], g["games_cast_after_offer"]) for g in groups] == [
            (1, 4, 2),
            (1, 4, 2),
        ]
        assert {tuple(g["opponent_ids"]) for g in groups} == {
            tuple(PRESET_IDS),
            tuple(reversed(PRESET_IDS)),
        }

        matrix = builder.pod_matchup_matrix(store, ["Test Commander"])
        assert matrix["schema"] == "studio-pod-matrix-2"
        pods = matrix["pods"]
        assert isinstance(pods, list) and len(pods) == 2
        assert [(p["pod"], p["runs_count"], p["games_completed"]) for p in pods] == [
            ("precon", 1, 4),
            ("precon", 1, 4),
        ]
        assert all(p["opponent_set_known"] and p["table_size"] == 4 for p in pods)
        listed = builder.list_simulations(store, ["Test Commander"])
        assert sorted(tuple(run["opponent_ids"]) for run in listed) == sorted(
            [tuple(PRESET_IDS), tuple(reversed(PRESET_IDS))]
        )
    finally:
        store.close()


# --- #1707: two series in one second never share a run id ------------------------------------

FROZEN_SECOND = 1_800_000_000.0


def _freeze_second(monkeypatch: pytest.MonkeyPatch) -> None:
    """The batch id carries the start second: hold the clock still, as a fast double start does."""
    monkeypatch.setattr(
        simulations_module, "time", types.SimpleNamespace(time=lambda: FROZEN_SECOND)
    )


def _start(
    manager: SimulationBatchManager, store: StudioStore, folder: Path, rev_id: str, base: int
) -> BatchSimulation:
    return manager.start_batch(
        store,
        folder,
        revision_id=rev_id,
        pod="precon",
        games_count=4,
        base_seed=base,
        chunk_runner=_cards_runner,
    )


def test_two_series_started_in_one_second_keep_two_run_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Before #1707 the second start took the first one's id: one run row, one record survived."""
    from commander_lab.studio import cache

    monkeypatch.setattr(cache, "CHECK", True)  # an undeclared write fails the series
    _freeze_second(monkeypatch)
    store = StudioStore.open(tmp_path)
    try:
        rev_id = _seed_test_deck(store)
        manager = SimulationBatchManager()
        first = _start(manager, store, tmp_path, rev_id, 10)
        second = _start(manager, store, tmp_path, rev_id, 20)  # same second, same deck slug
        _wait(first)
        _wait(second)
        assert first.status == "completed" and second.status == "completed"
        # the first id of a second keeps its old form, the later one only gains a suffix
        assert first.batch_id == "batch-1800000000-chulane"
        assert second.batch_id == "batch-1800000000-chulane-2"
        assert first.run_id != second.run_id and first.run_id and second.run_id
        rows = store.connection.execute(
            "SELECT run_id, seeds FROM simulation_run ORDER BY run_id"
        ).fetchall()
        assert {r["run_id"]: json.loads(r["seeds"]) for r in rows} == {
            first.run_id: [10, 11, 12, 13],
            second.run_id: [20, 21, 22, 23],
        }
        assert (
            store.connection.execute("SELECT COUNT(*) FROM simulation_card").fetchone()[0] == 2
        )  # Forest, one row per series
        records = sorted(p.name for p in games.games_folder(tmp_path).glob("*.series.json"))
        assert records == sorted(
            [f"{first.batch_id}.series.json", f"{second.batch_id}.series.json"]
        )
        stored = json.loads(
            (games.games_folder(tmp_path) / f"{second.batch_id}.series.json").read_text("utf-8")
        )
        assert stored["seeds"] == [20, 21, 22, 23] and stored["run_id"] == second.run_id
        assert [b["batch_id"] for b in manager.list_batches()] == [
            second.batch_id,
            first.batch_id,
        ]
    finally:
        store.close()


def _wait_for_record(folder: Path, batch: BatchSimulation) -> Path:
    """The series record of an ended batch, once written: it is written after the status flips."""
    path = games.games_folder(folder) / f"{batch.batch_id}.series.json"
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        with contextlib.suppress(OSError, ValueError):
            if json.loads(path.read_text("utf-8")).get("status") == batch.status:
                return path
        time.sleep(0.05)
    raise AssertionError(f"series record of {batch.batch_id} not written")


def _unlink_when_free(path: Path) -> None:
    """Windows refuses to delete a file another thread still holds open (WinError 32)."""
    deadline = time.monotonic() + 5.0
    while True:
        try:
            path.unlink()
            return
        except PermissionError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.05)


def test_a_saved_series_of_the_same_second_is_never_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After a restart the manager is empty: the saved run row and record still hold the id."""
    _freeze_second(monkeypatch)
    store = StudioStore.open(tmp_path)
    try:
        rev_id = _seed_test_deck(store)
        first = _start(SimulationBatchManager(), store, tmp_path, rev_id, 10)
        _wait(first)
        before = store.connection.execute("SELECT * FROM simulation_run").fetchall()
        record = _wait_for_record(tmp_path, first)
        record_before = record.read_text("utf-8")

        later = _start(SimulationBatchManager(), store, tmp_path, rev_id, 20)  # fresh manager
        _wait(later)
        _wait_for_record(tmp_path, later)
        assert later.batch_id == f"{first.batch_id}-2"
        assert record.read_text("utf-8") == record_before
        old_row = store.connection.execute(
            "SELECT * FROM simulation_run WHERE run_id = ?", (first.run_id,)
        ).fetchone()
        assert tuple(old_row) == tuple(before[0])  # untouched: no rename, no rewrite

        # only the series record exists (the run row was lost): the id is still taken
        store.connection.execute("DELETE FROM simulation_card WHERE run_id = ?", (first.run_id,))
        store.connection.execute("DELETE FROM simulation_run WHERE run_id = ?", (first.run_id,))
        store.connection.commit()
        again = _start(SimulationBatchManager(), store, tmp_path, rev_id, 30)
        _wait(again)
        assert again.batch_id == f"{first.batch_id}-3"

        # only the run row exists (the record file was lost): the id is still taken
        _unlink_when_free(_wait_for_record(tmp_path, again))
        row_only = _start(SimulationBatchManager(), store, tmp_path, rev_id, 40)
        _wait(row_only)
        assert row_only.batch_id == f"{first.batch_id}-4"
    finally:
        store.close()


def test_a_taken_batch_id_is_refused_and_nothing_is_changed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _freeze_second(monkeypatch)
    monkeypatch.setattr(simulations_module, "BATCH_ID_ATTEMPTS", 2)
    store = StudioStore.open(tmp_path)
    try:
        rev_id = _seed_test_deck(store)
        manager = SimulationBatchManager()
        for base in (10, 20):
            _wait(_start(manager, store, tmp_path, rev_id, base))
        records = {
            p.name: p.read_text("utf-8") for p in games.games_folder(tmp_path).glob("*.series.json")
        }
        rows = [tuple(r) for r in store.connection.execute("SELECT * FROM simulation_run")]
        with pytest.raises(RuntimeError, match="no series was started"):
            _start(manager, store, tmp_path, rev_id, 30)
        assert len(manager.list_batches()) == 2  # the refused start left no batch behind
        assert records == {
            p.name: p.read_text("utf-8") for p in games.games_folder(tmp_path).glob("*.series.json")
        }
        assert rows == [tuple(r) for r in store.connection.execute("SELECT * FROM simulation_run")]
    finally:
        store.close()


def test_a_new_second_keeps_the_plain_id_and_resume_reads_the_stored_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Equivalence: ids of other seconds are unchanged; resume takes the saved id, never a new one."""
    store = StudioStore.open(tmp_path)
    try:
        rev_id = _seed_test_deck(store)
        manager = SimulationBatchManager()
        clock = {"now": FROZEN_SECOND}
        monkeypatch.setattr(
            simulations_module, "time", types.SimpleNamespace(time=lambda: clock["now"])
        )
        first = _start(manager, store, tmp_path, rev_id, 10)
        clock["now"] += 1
        second = _start(manager, store, tmp_path, rev_id, 20)
        _wait(first)
        _wait(second)
        assert (first.batch_id, second.batch_id) == (
            "batch-1800000000-chulane",
            "batch-1800000001-chulane",
        )
        # a series that collided in its second keeps its suffixed id when read back from disk
        clock["now"] = FROZEN_SECOND
        third = _start(manager, store, tmp_path, rev_id, 30)
        _wait(third)
        assert third.batch_id == "batch-1800000000-chulane-2"
        resumed = BatchSimulation.from_saved_series(
            tmp_path, third.batch_id, chunk_runner=_cards_runner
        )
        assert resumed.batch_id == third.batch_id and resumed.seeds == [30, 31, 32, 33]
    finally:
        store.close()


def test_parallel_starts_in_one_second_all_get_their_own_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _freeze_second(monkeypatch)
    in_use = simulations_module.batch_id_in_use

    def slow_in_use(store: StudioStore, folder: Path, batch_id: str) -> bool:
        taken = in_use(store, folder, batch_id)
        time.sleep(0.02)  # widen the window between choosing an id and registering it
        return taken

    monkeypatch.setattr(simulations_module, "batch_id_in_use", slow_in_use)
    store = StudioStore.open(tmp_path)
    try:
        rev_id = _seed_test_deck(store)
        manager = SimulationBatchManager()
        ids: list[str] = []
        errors: list[str] = []
        gate = threading.Barrier(8)

        def go(base: int) -> None:
            gate.wait()
            own_store = StudioStore.open(
                tmp_path
            )  # one store per request thread, as the route does
            try:
                ids.append(_start(manager, own_store, tmp_path, rev_id, base).batch_id)
            except Exception as exc:  # reported below, never swallowed
                errors.append(repr(exc))
            finally:
                own_store.close()

        threads = [threading.Thread(target=go, args=(100 * i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(10)
        assert errors == []
        assert len(ids) == 8 and len(set(ids)) == 8
        for batch in manager.list_batches():
            deadline = time.monotonic() + 10
            while batch["status"] in {"pending", "running"} and time.monotonic() < deadline:
                time.sleep(0.05)
                batch = next(
                    b for b in manager.list_batches() if b["batch_id"] == batch["batch_id"]
                )
    finally:
        store.close()


# --- #1707 (rest): the id is also unique across processes -----------------------------------


def _hold_runner(release: threading.Event) -> object:
    """A chunk runner that keeps its series running until ``release`` is set."""

    def run(seeds: Sequence[int]) -> Iterator[GameSummary]:
        assert release.wait(10), "the series was never released"
        yield from _cards_runner(seeds)

    return run


def _start_held(
    manager: SimulationBatchManager,
    store: StudioStore,
    folder: Path,
    rev_id: str,
    base: int,
    release: threading.Event,
) -> BatchSimulation:
    return manager.start_batch(
        store,
        folder,
        revision_id=rev_id,
        pod="precon",
        games_count=4,
        base_seed=base,
        chunk_runner=_hold_runner(release),  # type: ignore[arg-type]
    )


def _reservations(folder: Path) -> list[str]:
    return sorted(p.name for p in games.games_folder(folder).glob("*.reserve"))


def test_two_managers_in_one_second_while_the_first_still_runs_get_two_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A CLI ``simulate`` has its own manager: a running series has no run row and no record yet."""
    _freeze_second(monkeypatch)
    release = threading.Event()
    store = StudioStore.open(tmp_path)
    try:
        rev_id = _seed_test_deck(store)
        server = _start_held(SimulationBatchManager(), store, tmp_path, rev_id, 10, release)
        assert server.status in {"pending", "running"}  # no run row, no record: only in memory
        assert store.connection.execute("SELECT COUNT(*) FROM simulation_run").fetchone()[0] == 0
        assert _reservations(tmp_path) == [f"{server.batch_id}.reserve"]
        cli = _start_held(SimulationBatchManager(), store, tmp_path, rev_id, 20, release)
        assert (server.batch_id, cli.batch_id) == (
            "batch-1800000000-chulane",
            "batch-1800000000-chulane-2",
        )
        release.set()
        _wait(server)
        _wait(cli)
        _wait_for_record(tmp_path, server)
        _wait_for_record(tmp_path, cli)
        assert server.status == "completed" and cli.status == "completed"
        rows = store.connection.execute(
            "SELECT run_id, seeds FROM simulation_run ORDER BY run_id"
        ).fetchall()
        assert {r["run_id"]: json.loads(r["seeds"]) for r in rows} == {
            server.run_id: [10, 11, 12, 13],
            cli.run_id: [20, 21, 22, 23],
        }
        assert _reservations(tmp_path) == []  # released when the series ended
    finally:
        release.set()
        store.close()


def test_a_reservation_of_another_process_is_never_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The claim file of a running series elsewhere holds its id; a start walks on to the next."""
    from commander_lab.studio import series_reservation

    _freeze_second(monkeypatch)
    folder = games.games_folder(tmp_path)
    plain = "batch-1800000000-chulane"
    assert series_reservation.try_reserve(folder, plain)  # "the other process"
    held = (folder / f"{plain}.reserve").read_text("utf-8")
    store = StudioStore.open(tmp_path)
    try:
        rev_id = _seed_test_deck(store)
        batch = _start(SimulationBatchManager(), store, tmp_path, rev_id, 10)
        _wait(batch)
        _wait_for_record(tmp_path, batch)
        assert batch.batch_id == f"{plain}-2"
        assert (folder / f"{plain}.reserve").read_text("utf-8") == held  # untouched
        assert _reservations(tmp_path) == [f"{plain}.reserve"]  # only the other one's remains
    finally:
        store.close()


def test_a_stale_reservation_is_reaped_and_a_fresh_one_is_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from commander_lab.studio import series_reservation

    folder = games.games_folder(tmp_path)
    old, fresh = folder / "batch-1-old.reserve", folder / "batch-2-fresh.reserve"
    for path in (old, fresh):
        path.write_text("{}", encoding="utf-8")
    now = time.time()
    os.utime(old, (now - series_reservation.STALE_AFTER_SECONDS - 60,) * 2)
    os.utime(fresh, (now - series_reservation.STALE_AFTER_SECONDS + 600,) * 2)
    assert series_reservation.reap_stale(folder) == ["batch-1-old"]
    assert not old.exists() and fresh.exists()
    # a reservation that is not reaped yet still refuses; the reaped id can be claimed again
    assert not series_reservation.try_reserve(folder, "batch-2-fresh")
    assert series_reservation.try_reserve(folder, "batch-1-old")
    series_reservation.release(folder, "batch-1-old")
    series_reservation.release(folder, "batch-1-old")  # twice is fine


def test_start_batch_reaps_a_stale_reservation_of_a_killed_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _freeze_second(monkeypatch)
    folder = games.games_folder(tmp_path)
    leftover = folder / "batch-1-killed.reserve"
    leftover.write_text("{}", encoding="utf-8")
    os.utime(leftover, (1.0, 1.0))
    store = StudioStore.open(tmp_path)
    try:
        batch = _start(SimulationBatchManager(), store, tmp_path, _seed_test_deck(store), 10)
        _wait(batch)
        assert not leftover.exists()
    finally:
        store.close()


def test_a_start_that_fails_after_the_claim_gives_the_claim_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _freeze_second(monkeypatch)
    store = StudioStore.open(tmp_path)
    try:
        rev_id = _seed_test_deck(store)

        def broken_thread(*_args: object, **_kwargs: object) -> object:
            raise RuntimeError("no thread")

        monkeypatch.setattr(simulations_module.threading, "Thread", broken_thread)
        manager = SimulationBatchManager()
        with pytest.raises(RuntimeError, match="no thread"):
            _start(manager, store, tmp_path, rev_id, 10)
        assert _reservations(tmp_path) == []
        assert manager.list_batches() == []
    finally:
        store.close()


def test_a_start_that_fails_while_building_the_batch_gives_the_claim_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _freeze_second(monkeypatch)
    store = StudioStore.open(tmp_path)
    try:
        rev_id = _seed_test_deck(store)

        def broken_batch(*_args: object, **_kwargs: object) -> object:
            raise ValueError("cannot build")

        monkeypatch.setattr(simulations_module, "BatchSimulation", broken_batch)
        manager = SimulationBatchManager()
        with pytest.raises(ValueError, match="cannot build"):
            _start(manager, store, tmp_path, rev_id, 10)
        assert _reservations(tmp_path) == [] and manager.list_batches() == []
    finally:
        store.close()


def test_a_denied_create_is_a_taken_id_only_when_the_file_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Windows answers an exclusive create on an existing (or delete-pending) file with a denial."""
    from commander_lab.studio import series_reservation

    def denied(*_args: object, **_kwargs: object) -> int:
        raise PermissionError("denied")

    monkeypatch.setattr(series_reservation.os, "open", denied)
    (tmp_path / "there.reserve").write_text("{}", encoding="utf-8")
    assert series_reservation.try_reserve(tmp_path, "there") is False
    with pytest.raises(PermissionError):  # a real permission problem is not hidden as "taken"
        series_reservation.try_reserve(tmp_path, "absent")


def test_a_failed_and_a_cancelled_series_release_their_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _freeze_second(monkeypatch)
    store = StudioStore.open(tmp_path)
    try:
        rev_id = _seed_test_deck(store)

        def failing(seeds: Sequence[int]) -> Iterator[GameSummary]:
            raise ValueError("engine down")
            yield  # pragma: no cover

        manager = SimulationBatchManager()
        failed = manager.start_batch(
            store, tmp_path, revision_id=rev_id, games_count=2, chunk_runner=failing
        )
        _wait(failed)
        deadline = time.monotonic() + 5
        while _reservations(tmp_path) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert _reservations(tmp_path) == []
    finally:
        store.close()


def test_the_id_choice_and_the_batch_entry_share_one_lock_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The check, the claim and the entry in ``_batches`` run under the manager lock (#1707)."""
    from commander_lab.studio import series_reservation

    _freeze_second(monkeypatch)
    manager = SimulationBatchManager()
    seen: list[tuple[str, bool]] = []
    in_use = simulations_module.batch_id_in_use
    reserve = series_reservation.try_reserve

    def spy_in_use(store: StudioStore, folder: Path, batch_id: str) -> bool:
        seen.append(("check", manager._lock.locked()))
        return in_use(store, folder, batch_id)

    def spy_reserve(folder: Path, series_id: str, **kwargs: object) -> bool:
        seen.append(("claim", manager._lock.locked()))
        return reserve(folder, series_id, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(simulations_module, "batch_id_in_use", spy_in_use)
    monkeypatch.setattr(series_reservation, "try_reserve", spy_reserve)
    store = StudioStore.open(tmp_path)
    try:
        batch = _start(manager, store, tmp_path, _seed_test_deck(store), 10)
        _wait(batch)
        assert seen == [("check", True), ("claim", True), ("check", True)]  # re-check after claim
        assert manager._batches[batch.batch_id] is batch
    finally:
        store.close()


_PROBE = r"""
import sys, time, types, json
from pathlib import Path
from commander_lab.studio import simulations
from commander_lab.studio.simulations import GameSummary, SimulationBatchManager
from commander_lab.studio.store import StudioStore

folder, rev_id, name, other = Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
simulations.time = types.SimpleNamespace(time=lambda: 1_800_000_000.0)  # the same second
(folder / f"{name}.ready").write_text("1")
deadline = time.monotonic() + 30
while not (folder / "go").exists():  # start together
    assert time.monotonic() < deadline
    time.sleep(0.01)

def runner(seeds):
    # keep this series running until the other process has started its own: no row, no record yet
    deadline = time.monotonic() + 30
    while not (folder / f"{other}.started").exists():
        assert time.monotonic() < deadline
        time.sleep(0.01)
    for seed in seeds:
        yield GameSummary(game_id=f"{name}-{seed}", seed=seed, status="finished",
                          winner_seats=[0], rounds=5)

store = StudioStore.open(folder)
batch = SimulationBatchManager().start_batch(
    store, folder, revision_id=rev_id, games_count=2,
    base_seed=100 if name == "a" else 200, chunk_runner=runner)
(folder / f"{name}.started").write_text(batch.batch_id)
deadline = time.monotonic() + 30
while batch.status in {"pending", "running"} and time.monotonic() < deadline:
    time.sleep(0.02)
deadline = time.monotonic() + 30
while batch.run_id is None and time.monotonic() < deadline:
    time.sleep(0.02)
# the status flips before the record is written and the id claim is given back: wait for the thread
done = batch.worker_done.wait(30)
store.close()
print(json.dumps({"batch_id": batch.batch_id, "status": batch.status, "done": done}))
"""


def test_two_processes_in_one_second_with_one_deck_get_two_run_rows(
    tmp_path: Path, subprocess_env: dict[str, str]
) -> None:
    """The real probe: two interpreters, one data folder, one frozen second, one deck slug."""
    folder = tmp_path / "data"
    store = StudioStore.open(folder)
    try:
        rev_id = _seed_test_deck(store)
    finally:
        store.close()
    games.games_folder(folder)
    processes = {
        name: subprocess.Popen(
            [sys.executable, "-c", _PROBE, str(folder), rev_id, name, other],
            env=subprocess_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for name, other in (("a", "b"), ("b", "a"))
    }
    try:
        deadline = time.monotonic() + 30
        while not all((folder / f"{n}.ready").exists() for n in processes):
            assert time.monotonic() < deadline, "the probe processes did not come up"
            time.sleep(0.02)
        (folder / "go").write_text("1")
        results = {}
        for name, process in processes.items():
            out, err = process.communicate(timeout=60)
            assert process.returncode == 0, err
            results[name] = json.loads(out)
    finally:
        for process in processes.values():
            if process.poll() is None:
                process.kill()
    assert {r["status"] for r in results.values()} == {"completed"}
    assert all(r["done"] for r in results.values())
    ids = {r["batch_id"] for r in results.values()}
    assert len(ids) == 2  # n=2 processes, n=2 distinct ids
    assert ids == {"batch-1800000000-chulane", "batch-1800000000-chulane-2"}
    reread = StudioStore.open(folder)
    try:
        rows = reread.connection.execute("SELECT run_id, seeds FROM simulation_run").fetchall()
    finally:
        reread.close()
    assert sorted(json.loads(r["seeds"])[0] for r in rows) == [100, 200]  # two rows, none lost
    assert sorted(r["run_id"] for r in rows) == sorted(f"batch-{i}" for i in ids)
    deadline = time.monotonic() + 10.0  # the release may trail the process exit on a slow runner
    while _reservations(folder) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert _reservations(folder) == []


# --- CLI: exhausted ids end in a clear German message, never a traceback ---------------------


def _simulate_argv(folder: Path, rev_id: str) -> list[str]:
    return ["--data", str(folder), "simulate", "--revision", rev_id, "--count", "2"]


def test_simulate_cli_reports_exhausted_ids_in_german_without_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from commander_lab.studio.__main__ import main as studio_main

    _freeze_second(monkeypatch)
    monkeypatch.setattr(simulations_module, "BATCH_ID_ATTEMPTS", 2)
    store = StudioStore.open(tmp_path)
    try:
        rev_id = _seed_test_deck(store)
        manager = SimulationBatchManager()
        for base in (10, 20):
            batch = _start(manager, store, tmp_path, rev_id, base)
            _wait(batch)
            _wait_for_record(tmp_path, batch)
    finally:
        store.close()
    rows_before = StudioStore.open(tmp_path)
    try:
        count = rows_before.connection.execute("SELECT COUNT(*) FROM simulation_run").fetchone()[0]
    finally:
        rows_before.close()
    # the CLI asks for an engine before it picks an id: a stand-in that never plays a game
    stand_in = SeriesEngine(
        command=("engine",), jvm_flags=(), games_per_jvm=1, serial_gc=False, appcds=False
    )
    monkeypatch.setattr(simulations_module, "series_engine", lambda *_a, **_k: stand_in)
    rc = studio_main(_simulate_argv(tmp_path, rev_id))
    captured = capsys.readouterr()
    assert rc == 2
    assert "Keine freie Serien-Kennung" in captured.err
    assert "batch-1800000000-chulane" in captured.err  # names the id that was asked for
    assert "nichts überschrieben" in captured.err
    assert "Traceback" not in captured.err and captured.out == ""
    after = StudioStore.open(tmp_path)
    try:
        assert (
            after.connection.execute("SELECT COUNT(*) FROM simulation_run").fetchone()[0] == count
        )
    finally:
        after.close()
    assert _reservations(tmp_path) == []


# --- cmp-<second> of compare-decks (#1707) ---------------------------------------------------


def test_compare_decks_ids_of_one_second_are_claimed_and_never_shared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two compare-decks in one second shared ``cmp-<second>`` and so the same game log names."""
    from commander_lab.studio import __main__ as studio_main
    from commander_lab.studio import series_reservation

    folder = games.games_folder(tmp_path)
    first = studio_main._claim_compare_id(tmp_path, "cmp-1800000000")
    second = studio_main._claim_compare_id(tmp_path, "cmp-1800000000")  # first still running
    assert (first, second) == ("cmp-1800000000", "cmp-1800000000-2")
    series_reservation.release(folder, first)
    series_reservation.release(folder, second)
    # recorded game logs and a series folder hold their id as well, claim or no claim
    (folder / "cmp-1800000000-base-s1000-t0.jsonl").write_text("{}\n", encoding="utf-8")
    (folder / "series" / "cmp-1800000000-2").mkdir(parents=True)
    assert studio_main._claim_compare_id(tmp_path, "cmp-1800000000") == "cmp-1800000000-3"
    series_reservation.release(folder, "cmp-1800000000-3")
    # an explicit --series-id is the caller's choice and is not touched here
    assert _reservations(tmp_path) == []


def _stub_compare(
    monkeypatch: pytest.MonkeyPatch,
    runs: list[str],
    *,
    fail: bool = False,
    claimed: bool = True,
) -> list[str]:
    """Replace the engine side of compare-decks; ``runs`` collects the series id of each run."""
    from commander_lab.engine.rules import project
    from commander_lab.studio import __main__ as studio_main
    from commander_lab.studio import paired_comparison

    def snapshot(path: Path) -> object:
        return types.SimpleNamespace(deck_id=Path(path).stem)

    def run(**kwargs: object) -> dict[str, object]:
        execution = kwargs["execution"]
        assert isinstance(execution, dict)
        runs.append(str(execution["series_id"]))
        held = [f"{runs[-1]}.reserve"] if claimed else []
        assert _reservations(Path(str(execution["games_dir"])).parent) == held
        if fail:
            raise ValueError("stand-in failure")
        return {}

    monkeypatch.setattr(project, "load_rules_deck_snapshot", snapshot)
    monkeypatch.setattr(studio_main, "series_engine", lambda *_a, **_k: None)
    monkeypatch.setattr(paired_comparison, "recorded_game_player", lambda *_a, **_k: None)
    monkeypatch.setattr(paired_comparison, "run_comparison_series", run)
    monkeypatch.setattr(paired_comparison, "format_comparison", lambda _result: "ok")
    monkeypatch.setattr(time, "time", lambda: FROZEN_SECOND)
    return runs


def _compare_argv(folder: Path) -> list[str]:
    argv = ["--data", str(folder), "compare-decks", "--base-deck", "base", "--variant-deck", "var"]
    for index in range(3):
        argv += ["--opponent", f"opp{index}"]
    return argv


def test_compare_decks_holds_its_id_while_it_runs_and_releases_it_at_the_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from commander_lab.studio.__main__ import main as studio_main

    runs: list[str] = []
    _stub_compare(monkeypatch, runs)
    assert studio_main(_compare_argv(tmp_path)) == 0
    assert runs == ["cmp-1800000000"]  # the stand-in asserted the claim file exists while running
    assert _reservations(tmp_path) == []
    capsys.readouterr()


def test_compare_decks_with_an_explicit_series_id_makes_no_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from commander_lab.studio.__main__ import main as studio_main

    runs: list[str] = []
    _stub_compare(monkeypatch, runs, claimed=False)  # the stand-in checks: no claim file
    assert studio_main([*_compare_argv(tmp_path), "--series-id", "mine"]) == 0
    assert runs == ["mine"] and _reservations(tmp_path) == []


def test_compare_decks_releases_its_id_when_the_run_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from commander_lab.studio.__main__ import main as studio_main

    runs: list[str] = []
    _stub_compare(monkeypatch, runs, fail=True)
    assert studio_main(_compare_argv(tmp_path)) == 2
    assert "refused: stand-in failure" in capsys.readouterr().err
    assert _reservations(tmp_path) == []


def test_compare_decks_reports_exhausted_ids_in_german(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from commander_lab.studio import series_reservation
    from commander_lab.studio.__main__ import main as studio_main

    runs: list[str] = []
    _stub_compare(monkeypatch, runs)
    monkeypatch.setattr(simulations_module, "BATCH_ID_ATTEMPTS", 2)
    folder = games.games_folder(tmp_path)
    for taken in ("cmp-1800000000", "cmp-1800000000-2"):
        assert series_reservation.try_reserve(folder, taken)  # held by other processes
    assert studio_main(_compare_argv(tmp_path)) == 2
    err = capsys.readouterr().err
    assert "Keine freie Serien-Kennung" in err and "Traceback" not in err
    assert "cmp-1800000000" in err  # names the id that was asked for
    assert runs == []
    assert _reservations(tmp_path) == ["cmp-1800000000-2.reserve", "cmp-1800000000.reserve"]


# --- review round of #1730: re-check after the claim, worker end, vanishing files -------------


def test_the_stale_age_of_a_reservation_is_24_hours() -> None:
    from commander_lab.studio import series_reservation

    assert series_reservation.STALE_AFTER_SECONDS == 24 * 3600.0


def test_a_create_denied_for_a_vanishing_file_is_asked_once_more(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Windows denies a create while another process deletes the file; a moment later it is free."""
    from commander_lab.studio import series_reservation

    real_open = os.open
    calls: list[int] = []

    def flaky(*args: object, **kwargs: object) -> int:
        calls.append(1)
        if len(calls) == 1:
            raise PermissionError("delete pending")
        return real_open(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(series_reservation.os, "open", flaky)
    assert series_reservation.try_reserve(tmp_path, "vanishing") is True
    assert len(calls) == 2 and (tmp_path / "vanishing.reserve").is_file()


def test_a_series_that_ends_between_check_and_claim_keeps_its_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other process wrote its record and gave its claim back after our check: id is taken."""
    _freeze_second(monkeypatch)
    plain = "batch-1800000000-chulane"
    in_use = simulations_module.batch_id_in_use
    calls: list[str] = []

    def finishing(store: StudioStore, folder: Path, batch_id: str) -> bool:
        taken = in_use(store, folder, batch_id)
        calls.append(batch_id)
        if len(calls) == 1:  # the other series ends right after this answer ("not taken")
            (games.games_folder(folder) / f"{batch_id}.series.json").write_text("{}", "utf-8")
        return taken

    monkeypatch.setattr(simulations_module, "batch_id_in_use", finishing)
    store = StudioStore.open(tmp_path)
    try:
        batch = _start(SimulationBatchManager(), store, tmp_path, _seed_test_deck(store), 10)
        _wait(batch)
        _wait_for_record(tmp_path, batch)
        assert calls[:3] == [plain, plain, f"{plain}-2"]  # check, re-check after claim, next id
        assert batch.batch_id == f"{plain}-2"
        assert (games.games_folder(tmp_path) / f"{plain}.series.json").read_text("utf-8") == "{}"
        assert _reservations(tmp_path) == []  # the claim on the taken id was given back
    finally:
        store.close()


def test_compare_decks_id_that_gets_a_log_between_check_and_claim_is_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from commander_lab.studio import __main__ as studio_main
    from commander_lab.studio import series_reservation

    folder = games.games_folder(tmp_path)
    real = os.open
    first = []

    def other_finished_first(*args: object, **kwargs: object) -> int:
        if not first:  # the other run's logs appear and its claim is gone just before our claim
            first.append(1)
            (folder / "cmp-1800000000-base-s1000-t0.jsonl").write_text("{}\n", encoding="utf-8")
        return real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(series_reservation.os, "open", other_finished_first)
    assert studio_main._claim_compare_id(tmp_path, "cmp-1800000000") == "cmp-1800000000-2"
    assert _reservations(tmp_path) == ["cmp-1800000000-2.reserve"]  # nothing left on the base id


def test_compare_decks_reaps_a_stale_reservation_of_a_killed_run(tmp_path: Path) -> None:
    from commander_lab.studio import __main__ as studio_main

    folder = games.games_folder(tmp_path)
    leftover = folder / "cmp-1-killed.reserve"
    leftover.write_text("{}", encoding="utf-8")
    os.utime(leftover, (1.0, 1.0))
    claimed = studio_main._claim_compare_id(tmp_path, "cmp-1800000000")
    assert not leftover.exists() and claimed == "cmp-1800000000"


def test_a_failure_before_the_games_start_still_releases_the_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The deck hash is read at the top of the worker: its failure ends the series, not the claim."""
    _freeze_second(monkeypatch)

    def broken(_path: Path) -> str:
        raise OSError("deck file vanished")

    monkeypatch.setattr(play, "snapshot_deck_hash", broken)
    store = StudioStore.open(tmp_path)
    try:
        batch = _start(SimulationBatchManager(), store, tmp_path, _seed_test_deck(store), 10)
        assert batch.worker_done.wait(10)
        assert batch.status == "failed" and "deck file vanished" in str(batch.error)
        assert _reservations(tmp_path) == []
    finally:
        store.close()


def test_the_worker_is_done_only_after_the_record_is_written_and_the_claim_is_gone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A CLI that ends its process on status alone would leave a claim and no record behind."""
    from commander_lab.studio import series_reservation

    _freeze_second(monkeypatch)
    manager = SimulationBatchManager()
    done_at_release: list[bool] = []
    release = series_reservation.release

    def spy(folder: Path, series_id: str) -> None:
        done_at_release.append(manager._batches[series_id].worker_done.is_set())
        release(folder, series_id)

    monkeypatch.setattr(series_reservation, "release", spy)
    store = StudioStore.open(tmp_path)
    try:
        batch = _start(manager, store, tmp_path, _seed_test_deck(store), 10)
        assert batch.worker_done.wait(10)
        assert done_at_release == [False]  # the claim went before "done", not after
        assert (games.games_folder(tmp_path) / f"{batch.batch_id}.series.json").is_file()
        assert _reservations(tmp_path) == []
    finally:
        store.close()


def test_resuming_a_series_with_nothing_left_is_done_at_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No worker thread runs then; a CLI waiting for the worker must not wait for nothing."""
    _freeze_second(monkeypatch)
    store = StudioStore.open(tmp_path)
    try:
        first = _start(SimulationBatchManager(), store, tmp_path, _seed_test_deck(store), 10)
        assert first.worker_done.wait(10)
        for seed in first.seeds:  # every game of the series has a finished log
            (games.games_folder(tmp_path) / f"batch-{first.batch_id}-s{seed}.jsonl").write_text(
                "{}"
            )

        def finished(_folder: Path, game_id: str, **_kwargs: object) -> GameSummary:
            return GameSummary(
                game_id=game_id, seed=int(game_id.rsplit("-s", 1)[1]), status="finished"
            )

        monkeypatch.setattr(simulations_module, "extract_game_log_telemetry", finished)
        resumed = SimulationBatchManager().resume_batch(
            store, tmp_path, batch_id=first.batch_id, chunk_runner=_cards_runner
        )
        assert resumed.status == "completed" and resumed.worker_done.is_set()
    finally:
        store.close()


def test_simulate_cli_waits_for_the_worker_thread_before_it_returns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The status flips before the record and the claim: the CLI must not exit on the status."""
    from commander_lab.studio.__main__ import main as studio_main

    order: list[str] = []

    class SlowEnd:
        status = "completed"  # visible while the thread still writes its record
        worker_done = threading.Event()

        def to_dict(self) -> dict[str, object]:
            order.append("printed")
            return {"status": self.status, "worker_done": self.worker_done.is_set()}

    def finish() -> None:
        time.sleep(0.3)
        order.append("worker finished")
        SlowEnd.worker_done.set()

    def fake_start(*_args: object, **_kwargs: object) -> SlowEnd:
        threading.Thread(target=finish, daemon=True).start()
        return SlowEnd()

    monkeypatch.setattr(SimulationBatchManager, "start_batch", fake_start)
    assert studio_main(_simulate_argv(tmp_path, "rev")) == 0
    assert order == ["worker finished", "printed"]
    assert json.loads(capsys.readouterr().out)["worker_done"] is True
