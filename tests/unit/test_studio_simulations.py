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

import json
import re
import sqlite3
import time
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from commander_lab.studio import builder, games, play
from commander_lab.studio import store as store_module
from commander_lab.studio.decks import RevisionCard, create_revision
from commander_lab.studio.launch import POD_PRESETS
from commander_lab.studio.simulations import (
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
