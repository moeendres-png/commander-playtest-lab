"""Unit tests for #1401: bridge jar SHA-256 provenance and BRIDGE_AHEAD_OF_QUALIFICATION."""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import sqlite3
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab import technical_truth
from commander_lab.bridge_qualification import (
    BRIDGE_AHEAD,
    BRIDGE_ALIGNED,
    BRIDGE_UNKNOWN,
    bridge_qualification,
)
from commander_lab.engine.rules.full_game import FullGameConformanceResult
from commander_lab.models import RulesDeckInput
from commander_lab.studio import (
    __main__ as studio_cli,
)
from commander_lab.studio import (
    builder,
    card_outcomes,
    data_report,
    engine_check,
    importers,
    launch,
    paired_comparison,
    play,
    simulations,
)
from commander_lab.studio.games import GameRecorder
from commander_lab.studio.store import SCHEMA_VERSION, StudioStore
from commander_lab.studio.web import create_app


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _init_bridge_repo(tmp_path: Path, *, freeze_eligible: bool = True) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    (repo / "config").mkdir(parents=True)
    (repo / "engine-bridge" / "src").mkdir(parents=True)
    (repo / "engine-bridge" / "src" / "Main.java").write_text("// bridge v1\n", encoding="utf-8")

    pin = "e" * 40
    config = {
        "primary_engine": {"commit": pin},
        "architecture_freeze": {
            "engine_commit": pin,
            "current_qualification": {
                "evidence_epoch": "test-epoch-1",
                "lab_commit": "0" * 40,
                "engine_commit": pin,
                "freeze_eligible": freeze_eligible,
            },
        },
    }
    (repo / "config" / "rules_engines.json").write_text(json.dumps(config), encoding="utf-8")
    _git(repo, "init")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "sealed")
    sealed_sha = _git(repo, "rev-parse", "HEAD")

    config["architecture_freeze"]["current_qualification"]["lab_commit"] = sealed_sha
    (repo / "config" / "rules_engines.json").write_text(json.dumps(config), encoding="utf-8")
    _git(repo, "add", "config/rules_engines.json")
    _git(repo, "commit", "-m", "record sealed lab commit")
    return repo, sealed_sha


def _make_deck(deck_id: str, commander: str) -> RulesDeckInput:
    cards = [commander] + [f"Forest #{i}" for i in range(99)]
    return RulesDeckInput(
        deck_id=deck_id,
        name=deck_id,
        deck_hash="a" * 64,
        commander_names=(commander,),
        mainboard=tuple(cards[1:]),
        sideboard=(),
    )


def _write_outcome_log(
    folder: Path,
    game_id: str,
    *,
    decks: list[str],
    winners: list[int],
    seed: int,
    hand_cards: list[str],
    bridge_sha: str | None,
    qual_state: str | None,
    covered: bool,
    commit: str = "f" * 40,
    with_deck_hash: bool = True,
) -> Path:
    path = folder / f"{game_id}.jsonl.gz"
    header: dict[str, object] = {
        "kind": "header",
        "schema": "studio-game-log-1",
        "game_id": game_id,
        "seed": seed,
        "engine_commit": commit,
        "pilot": "GenericCommanderPilot 1.0.0",
        "decision_policy": "xmage-full-game-policy-1.0.0",
        # each seat names its deck state, as every log since #1657 does; with_deck_hash=False
        # writes a log of before #1657 ("Stand unbekannt")
        "seats": [
            {"seat": i, "deck_id": d, "deck_hash": hashlib.sha256(d.encode()).hexdigest()}
            if with_deck_hash
            else {"seat": i, "deck_id": d}
            for i, d in enumerate(decks)
        ],
    }
    if bridge_sha is not None:
        header["bridge_jar_sha256"] = bridge_sha
    if qual_state is not None:
        header["bridge_qualification_state"] = qual_state
    header["covered_by_sealed_epoch"] = covered

    frame = {
        "kind": "frame",
        "n": 1,
        "seat": 0,
        "turn": 1,
        "decision_class": "mulligan",
        "players": [
            {"seat": i, "hand": list(hand_cards) if i == 0 else []} for i in range(len(decks))
        ],
    }
    result: dict[str, object] = {
        "kind": "result",
        "status": "finished",
        "winner_seats": winners,
        "frames": 1,
    }
    if bridge_sha is not None:
        result["bridge_jar_sha256"] = bridge_sha
    if qual_state is not None:
        result["bridge_qualification_state"] = qual_state
    result["covered_by_sealed_epoch"] = covered

    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for entry in (header, frame, result):
            handle.write(json.dumps(entry) + "\n")
    return path


def test_bridge_qualification_states(tmp_path: Path) -> None:
    repo, _sealed = _init_bridge_repo(tmp_path)
    aligned = bridge_qualification(repo)
    assert aligned["status"] == BRIDGE_ALIGNED
    assert aligned["ahead_of_sealed_epoch"] is False
    assert aligned["covered_by_sealed_epoch"] is True
    assert aligned["bridge_dirty"] is False

    # Untracked source file under engine-bridge/ -> ahead, fail-closed:
    # a jar built from this tree would contain it, so it must not read as sealed.
    extra = repo / "engine-bridge" / "src" / "Extra.java"
    extra.write_text("// new bridge source, not yet committed\n", encoding="utf-8")
    untracked = bridge_qualification(repo)
    assert untracked["status"] == BRIDGE_AHEAD
    assert untracked["ahead_of_sealed_epoch"] is True
    assert untracked["covered_by_sealed_epoch"] is False
    assert untracked["bridge_dirty"] is True
    extra.unlink()

    # Ignored build output under engine-bridge/target/ stays invisible.
    exclude = repo / ".git" / "info" / "exclude"
    exclude.write_text(
        exclude.read_text(encoding="utf-8") + "engine-bridge/target/\n", encoding="utf-8"
    )
    target = repo / "engine-bridge" / "target"
    target.mkdir()
    (target / "bridge.jar").write_bytes(b"jar")
    still_aligned = bridge_qualification(repo)
    assert still_aligned["status"] == BRIDGE_ALIGNED
    assert still_aligned["bridge_dirty"] is False

    # Uncommitted tracked change under engine-bridge/ -> ahead, fail-closed
    java_file = repo / "engine-bridge" / "src" / "Main.java"
    java_file.write_text("// dirty bridge edit\n", encoding="utf-8")
    dirty = bridge_qualification(repo)
    assert dirty["status"] == BRIDGE_AHEAD
    assert dirty["ahead_of_sealed_epoch"] is True
    assert dirty["covered_by_sealed_epoch"] is False
    assert dirty["bridge_dirty"] is True

    # Committed change under engine-bridge/ -> ahead even when working tree clean
    _git(repo, "add", "engine-bridge/src/Main.java")
    _git(repo, "commit", "-m", "advance bridge")
    ahead = bridge_qualification(repo)
    assert ahead["status"] == BRIDGE_AHEAD
    assert ahead["ahead_of_sealed_epoch"] is True
    assert ahead["covered_by_sealed_epoch"] is False
    assert ahead["bridge_dirty"] is False
    assert ahead["sealed_bridge_tree"] != ahead["head_bridge_tree"]

    # Non-git directory -> fail-closed UNKNOWN
    plain = tmp_path / "non_git"
    plain.mkdir()
    unknown = bridge_qualification(plain)
    assert unknown["status"] == BRIDGE_UNKNOWN
    assert unknown["covered_by_sealed_epoch"] is False

    # Current repo itself should match sealed epoch before bridge edits land
    live = bridge_qualification()
    assert live["status"] in {BRIDGE_ALIGNED, BRIDGE_AHEAD}
    assert live["covered_by_sealed_epoch"] is (live["status"] == BRIDGE_ALIGNED)


def test_launch_and_play_record_bridge_sha_and_qualification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    jar_dir = tmp_path / "engine"
    jar_dir.mkdir()
    jar = jar_dir / "bridge.jar"
    jar_bytes = b"simulated-bridge-jar-content"
    jar.write_bytes(jar_bytes)
    expected_sha = hashlib.sha256(jar_bytes).hexdigest()

    cmd = ("/usr/bin/java", "-jar", str(jar), "full-game")
    assert launch.jar_path_for_command(cmd) == jar
    assert launch.bridge_jar_sha256(tmp_path, cmd) == expected_sha
    assert launch.bridge_jar_sha256(tmp_path, ("/usr/bin/python", "-m", "other")) is None

    monkeypatch.setattr(
        "commander_lab.bridge_qualification.bridge_qualification",
        lambda: {
            "status": BRIDGE_AHEAD,
            "ahead_of_sealed_epoch": True,
            "covered_by_sealed_epoch": False,
            "sealed_epoch": "test-epoch",
        },
    )
    monkeypatch.setenv(launch.ENGINE_COMMAND_ENV, launch.command_text(cmd))
    monkeypatch.setattr(launch, "_java_major", lambda _java: 17)
    state = launch.engine_state(tmp_path)
    assert state["bridge_jar_sha256"] == expected_sha
    assert state["bridge_qualification"]["status"] == BRIDGE_AHEAD  # type: ignore[index]

    decks = (
        _make_deck("d1", "Chulane, Teller of Tales"),
        _make_deck("d2", "Solphim, Mayhem Dominus"),
    )
    prepared = play.prepare_game(
        decks,
        seed=42,
        game_id="game-sha-test",
        command=cmd,
        data_folder=tmp_path,
        qualification={
            "status": BRIDGE_AHEAD,
            "covered_by_sealed_epoch": False,
            "sealed_epoch": "test-epoch",
        },
    )
    assert prepared.header["bridge_jar_sha256"] == expected_sha
    assert prepared.header["bridge_qualification_state"] == BRIDGE_AHEAD
    assert prepared.header["covered_by_sealed_epoch"] is False

    recorder = GameRecorder(tmp_path, "game-sha-test", prepared.header)
    summary = play.close_recorded_game(
        recorder,
        FullGameConformanceResult(
            scenario=prepared.scenario,
            engine_version="1.0",
            xmage_commit=prepared.scenario.xmage_commit,
            decision_protocol_version="1.0",
            decision_count=3,
            terminal=True,
            winner_seats=(1,),
            result_payload={"ok": True},
            semantic_transcript_sha256="b" * 64,
            raw_result_sha256="c" * 64,
            shutdown_disposition="graceful_shutdown",
        ),
    )
    assert summary["bridge_jar_sha256"] == expected_sha
    assert summary["bridge_qualification_state"] == BRIDGE_AHEAD
    assert summary["covered_by_sealed_epoch"] is False


def test_schema_17_to_18_migration_and_fail_closed_simulation_readback(tmp_path: Path) -> None:
    folder = tmp_path / "studio"
    folder.mkdir()
    db_path = folder / "studio.sqlite3"
    base = StudioStore.in_memory()
    ddl = base.connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='meta'"
    ).fetchone()
    assert ddl is not None
    base.close()

    # Build a minimal schema-17 store whose simulation_run lacks the new columns.
    raw = sqlite3.connect(db_path)
    raw.executescript(
        """
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO meta(key, value) VALUES ('schema_version', '17');
        CREATE TABLE source (
            source_id TEXT PRIMARY KEY, data_class TEXT NOT NULL, title TEXT NOT NULL,
            sha256 TEXT NOT NULL, snapshot_date TEXT, url TEXT, imported_at TEXT NOT NULL
        );
        INSERT INTO source VALUES ('src1', 'SIMULATED_RESULT', 'test', '00', NULL, NULL, '2026-01-01T00:00:00Z');
        CREATE TABLE simulation_run (
            run_id TEXT PRIMARY KEY, deck_id TEXT NOT NULL, pod TEXT NOT NULL,
            engine_pin TEXT NOT NULL, pilot_policy TEXT NOT NULL, seeds TEXT NOT NULL,
            games_planned INTEGER NOT NULL, games_completed INTEGER NOT NULL, games_failed INTEGER NOT NULL,
            wins_fractional REAL NOT NULL, win_rate REAL, mean_rounds REAL,
            hand_dwell_status TEXT NOT NULL, source_id TEXT NOT NULL REFERENCES source(source_id)
        );
        INSERT INTO simulation_run VALUES (
            'old-run', 'chulane', 'precon', 'pin', 'pilot', '[1]', 1, 1, 0, 1.0, 1.0, 8.0,
            'NOT_MEASURED', 'src1'
        );
        """
    )
    raw.commit()
    raw.close()

    store = StudioStore.open(folder)
    try:
        cols = [r["name"] for r in store.connection.execute("PRAGMA table_info(simulation_run)")]
        assert "bridge_jar_sha256" in cols
        assert "bridge_qualification_state" in cols
        ver = store.connection.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()[0]
        assert ver == str(SCHEMA_VERSION) == "21"

        # Register commander + simulated file importing fail-closed
        store.connection.execute(
            "INSERT INTO card(card_id, oracle_id, oracle_name, color_identity, is_basic_land, source_id) "
            "VALUES ('c-sol', 'o-sol', 'Sol Ring', '', 0, 'src1')"
        )
        store.connection.execute(
            "INSERT INTO commander_binding(kind, key, commander_name, basis) "
            "VALUES ('simulation_run', 'old-run', 'Chulane, Teller of Tales', 'TEST')"
        )
        store.connection.commit()

        # Import simulation claiming ALIGNED_WITH_SEALED_EPOCH without SHA -> must downgrade to UNKNOWN!
        sim_file = tmp_path / "sim_no_sha.json"
        sim_file.write_text(
            json.dumps(
                {
                    "plan": {
                        "deck_id": "chulane",
                        "pod": "precon",
                        "seeds": [1, 2],
                        "games_planned": 2,
                        "bridge_qualification_state": BRIDGE_ALIGNED,
                    },
                    "summary": {
                        "games_completed": 2,
                        "games_failed": 0,
                        "wins_fractional": 1.0,
                        "win_rate_completed_games": 0.5,
                        "mean_rounds": 9.0,
                        "hand_residence_turns": {
                            "status": "MEASURED",
                            "castable_but_uncast": [],
                            "per_card_cast_opportunities": [],
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        importers.import_simulation_report(
            store,
            sim_file,
            engine_pin="f" * 40,
            pilot_policy="GenericCommanderPilot 1.0.0",
        )

        sim_ahead = tmp_path / "sim_ahead.json"
        sim_ahead.write_text(
            json.dumps(
                {
                    "plan": {
                        "deck_id": "chulane",
                        "pod": "precon",
                        "seeds": [1, 2],
                        "games_planned": 2,
                        "bridge_jar_sha256": "c" * 64,
                        "bridge_qualification_state": BRIDGE_AHEAD,
                    },
                    "summary": {
                        "games_completed": 2,
                        "games_failed": 0,
                        "wins_fractional": 2.0,
                        "win_rate_completed_games": 1.0,
                        "mean_rounds": 8.5,
                        "hand_residence_turns": {
                            "status": "MEASURED",
                            "castable_but_uncast": [],
                            "per_card_cast_opportunities": [
                                {
                                    "card": "Sol Ring",
                                    "games_offered": 1,
                                    "games_cast_after_offer": 1,
                                    "offered_castable": 1,
                                    "cast": 1,
                                    "mean_first_cast_round": 1.0,
                                }
                            ],
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        importers.import_simulation_report(
            store,
            sim_ahead,
            engine_pin="f" * 40,
            pilot_policy="GenericCommanderPilot 1.0.0",
        )
        store.connection.executemany(
            "INSERT INTO commander_binding(kind, key, commander_name, basis) VALUES (?, ?, ?, ?)",
            [
                (
                    "simulation_run",
                    "chulane:precon:sim_no_sha",
                    "Chulane, Teller of Tales",
                    "TEST",
                ),
                (
                    "simulation_run",
                    "chulane:precon:sim_ahead",
                    "Chulane, Teller of Tales",
                    "TEST",
                ),
            ],
        )
        store.connection.commit()

        listed = {
            r["run_id"]: r for r in builder.list_simulations(store, ["Chulane, Teller of Tales"])
        }
        assert listed["old-run"]["bridge_qualification_state"] == BRIDGE_UNKNOWN
        assert listed["old-run"]["covered_by_sealed_epoch"] is False
        no_sha = listed["chulane:precon:sim_no_sha"]
        assert no_sha["bridge_qualification_state"] == BRIDGE_UNKNOWN
        assert no_sha["covered_by_sealed_epoch"] is False
        ahead_run = listed["chulane:precon:sim_ahead"]
        assert ahead_run["bridge_jar_sha256"] == "c" * 64
        assert ahead_run["bridge_qualification_state"] == BRIDGE_AHEAD
        assert ahead_run["covered_by_sealed_epoch"] is False

        per_card = builder.card_simulations(store, "c-sol", ["Chulane, Teller of Tales"])
        assert len(per_card) == 1
        assert per_card[0]["bridge_jar_sha256"] == "c" * 64
        assert per_card[0]["bridge_qualification_state"] == BRIDGE_AHEAD
        assert per_card[0]["covered_by_sealed_epoch"] is False
    finally:
        store.close()


def test_outcomes_and_paired_comparison_reject_mixed_bridge_jars_and_flag_ahead(
    tmp_path: Path,
) -> None:
    decks_sealed = ["base", "o1", "o2"]
    decks_var = ["var", "o1", "o2"]
    sha_a = "a" * 64
    sha_b = "b" * 64

    _write_outcome_log(
        tmp_path,
        "g1",
        decks=decks_sealed,
        winners=[0],
        seed=1,
        hand_cards=["Sol Ring"],
        bridge_sha=sha_a,
        qual_state=BRIDGE_ALIGNED,
        covered=True,
    )
    _write_outcome_log(
        tmp_path,
        "g2",
        decks=decks_sealed,
        winners=[1],
        seed=2,
        hand_cards=["Forest"],
        bridge_sha=sha_b,
        qual_state=BRIDGE_AHEAD,
        covered=False,
    )
    with pytest.raises(ValueError, match="mixed bridge jar SHA-256"):
        card_outcomes.outcomes_for_folder(tmp_path, deck_id="base")

    mixed_outcomes = card_outcomes.outcomes_for_folder(tmp_path, deck_id="base", allow_mixed=True)
    assert mixed_outcomes["covered_by_sealed_epoch"] is False
    assert set(mixed_outcomes["bridge_jar_sha256s"]) == {sha_a, sha_b}
    assert BRIDGE_AHEAD in mixed_outcomes["bridge_qualification_states"]
    assert any("BRIDGE_AHEAD_OF_QUALIFICATION" in w for w in mixed_outcomes["warnings"])

    # Paired comparison rejects mixed jars by default
    _write_outcome_log(
        tmp_path,
        "v1",
        decks=decks_var,
        winners=[0],
        seed=1,
        hand_cards=["Sol Ring"],
        bridge_sha=sha_b,
        qual_state=BRIDGE_AHEAD,
        covered=False,
    )
    with pytest.raises(ValueError, match="mixed bridge jar hashes"):
        paired_comparison.compare_logs(tmp_path, base_deck_id="base", variant_deck_id="var")

    # Ahead comparison on matching bridge SHA is not sealed
    ahead_dir = tmp_path / "ahead"
    ahead_dir.mkdir()
    for name, deck_list, winner in (
        ("b1", decks_sealed, [1]),
        ("v1", decks_var, [0]),
        ("b2", decks_sealed, [1]),
        ("v2", decks_var, [0]),
    ):
        _write_outcome_log(
            ahead_dir,
            name,
            decks=deck_list,
            winners=winner,
            seed=10 if name.endswith("1") else 11,
            hand_cards=["Sol Ring"],
            bridge_sha=sha_b,
            qual_state=BRIDGE_AHEAD,
            covered=False,
        )
    ahead_cmp = paired_comparison.compare_logs(
        ahead_dir, base_deck_id="base", variant_deck_id="var"
    )
    assert ahead_cmp["bridge_jar_sha256s"] == [sha_b]
    assert ahead_cmp["bridge_qualification_states"] == [BRIDGE_AHEAD]
    assert ahead_cmp["covered_by_sealed_epoch"] is False
    assert any("BRIDGE_AHEAD_OF_QUALIFICATION" in w for w in ahead_cmp["warnings"])
    rendered = paired_comparison.format_comparison(ahead_cmp)
    assert "bridge_jar bbbbbbbbbbbb" in rendered
    assert "sealed no" in rendered


def test_reporters_surface_bridge_ahead_of_qualification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ahead_payload = {
        "status": BRIDGE_AHEAD,
        "ahead_of_sealed_epoch": True,
        "covered_by_sealed_epoch": False,
        "sealed_epoch": "epoch-1",
        "sealed_lab_commit": "1" * 40,
        "sealed_engine_commit": "2" * 40,
        "live_engine_commit": "2" * 40,
        "sealed_bridge_tree": "3" * 40,
        "head_bridge_tree": "4" * 40,
        "bridge_dirty": False,
        "reason": "engine-bridge/ tree differs from sealed",
    }
    monkeypatch.setattr(
        "commander_lab.bridge_qualification.bridge_qualification",
        lambda *_args, **_kwargs: ahead_payload,
    )
    truth = technical_truth.build_technical_truth(Path(__file__).resolve().parents[2])
    eng_status = truth["external_engine_status"]
    assert isinstance(eng_status, dict)
    assert eng_status["covered_by_sealed_epoch"] is False
    assert eng_status["bridge_qualification"]["status"] == BRIDGE_AHEAD
    assert "bridge_ahead_of_qualification" in truth["documented_limitations"]

    # claude_handoff.pin_lines prints BRIDGE_AHEAD_OF_QUALIFICATION when bridge is ahead
    handoff_path = Path(__file__).resolve().parents[2] / "scripts" / "claude_handoff.py"
    spec = importlib.util.spec_from_file_location("claude_handoff_test", handoff_path)
    assert spec is not None and spec.loader is not None
    handoff = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(handoff)
    repo, _ = _init_bridge_repo(tmp_path)
    (repo / "engine-bridge" / "src" / "Main.java").write_text("// dirty\n", encoding="utf-8")
    lines = handoff.pin_lines(repo)
    assert any(BRIDGE_AHEAD in line for line in lines)

    # Studio API & CLI status + data_report + engine_check
    studio_dir = tmp_path / "studio"
    StudioStore.open(studio_dir).close()

    store = StudioStore.open(studio_dir)
    try:
        rep = data_report.data_report(store)
        assert rep["bridge_qualification"]["status"] == BRIDGE_AHEAD  # type: ignore[index]
    finally:
        store.close()

    client = TestClient(create_app(studio_dir))
    api_status = client.get("/api/status")
    assert api_status.status_code == 200
    assert api_status.json()["bridge_qualification"]["status"] == BRIDGE_AHEAD

    cli_buf: list[str] = []
    monkeypatch.setattr("builtins.print", cli_buf.append)
    assert studio_cli.main(["--data", str(studio_dir), "status"]) == 0
    assert json.loads(cli_buf[-1])["bridge_qualification"]["status"] == BRIDGE_AHEAD

    # engine_check includes bridge_qualification
    store = StudioStore.open(studio_dir)
    try:
        chk = engine_check.check_rows([], studio_dir)
        assert chk["bridge_qualification"]["status"] == BRIDGE_AHEAD  # type: ignore[index]
    finally:
        store.close()

    # BatchSimulation tracks bridge SHA and qualification through to_dict and store
    mgr = simulations.SimulationBatchManager()
    batch = simulations.BatchSimulation(
        batch_id="b1",
        data_folder=studio_dir,
        deck_id="chulane",
        revision_id="rev@chulane/main/current",
        pod_name="precon",
        opponent_paths=[],
        seeds=[1],
        bridge_jar_sha256="d" * 64,
        qualification=ahead_payload,
    )
    d = batch.to_dict()
    assert d["bridge_jar_sha256"] == "d" * 64
    assert d["covered_by_sealed_epoch"] is False
    store = StudioStore.open(studio_dir)
    try:
        store.connection.execute(
            "INSERT INTO deck VALUES ('chulane', 'Chulane', '2026-01-01T00:00:00Z')"
        )
        store.connection.execute(
            "INSERT INTO deck_revision VALUES ('rev@chulane/main/current', 'chulane', NULL, 'h', '', NULL, '2026-01-01T00:00:00Z')"
        )
        run_id = simulations.save_batch_to_store(
            store,
            batch,
            {
                "games_planned": 1,
                "games_completed": 1,
                "games_failed": 0,
                "wins_fractional": 1.0,
                "win_rate": 1.0,
                "mean_rounds": 9.0,
                "bridge_jar_sha256s": ["d" * 64],
                "bridge_qualification_states": [BRIDGE_AHEAD],
                "covered_by_sealed_epoch": False,
                "cards": [],
            },
        )
        saved = store.connection.execute(
            "SELECT bridge_jar_sha256, bridge_qualification_state FROM simulation_run WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        assert saved is not None
        assert saved["bridge_jar_sha256"] == "d" * 64
        assert saved["bridge_qualification_state"] == BRIDGE_AHEAD
    finally:
        store.close()
    assert isinstance(mgr, simulations.SimulationBatchManager)


def test_studio_static_ui_bridge_provenance_and_csp_clean() -> None:
    static_dir = Path(__file__).resolve().parents[2] / "src" / "commander_lab" / "studio" / "static"
    ui_js = (static_dir / "ui.js").read_text(encoding="utf-8")
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    partie_js = (static_dir / "partie.js").read_text(encoding="utf-8")
    decks_js = (static_dir / "decks.js").read_text(encoding="utf-8")

    # decks.js uses StudioUI.h and StudioUI.api
    assert "StudioUI.h" in decks_js and "StudioUI.api" in decks_js
    assert "h: el" in ui_js and "api: request" in ui_js
    assert "bridge-qualification-pill" in ui_js
    assert BRIDGE_AHEAD in ui_js

    assert "bridge_jar_sha256" in app_js
    assert BRIDGE_AHEAD in app_js
    assert "bridge_jar_sha256" in partie_js
    assert "covered_by_sealed_epoch" in partie_js
    # No style: "display:..." inline style properties remain in partie.js
    assert 'style: "' not in partie_js


def test_fail_closed_bridge_qualification_and_missing_sha_regressions(tmp_path: Path) -> None:
    # P2-4: missing or non-40-hex engine commit -> BRIDGE_UNKNOWN
    repo, _sealed = _init_bridge_repo(tmp_path / "r1")
    cfg_path = repo / "config" / "rules_engines.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg["primary_engine"]["commit"] = ""
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    missing_live = bridge_qualification(repo)
    assert missing_live["status"] == BRIDGE_UNKNOWN
    assert missing_live["covered_by_sealed_epoch"] is False

    # P2-2: explicit command with missing/absent -jar must never fall back to data_folder/ENGINE_JAR
    data_dir = tmp_path / "studio_data"
    (data_dir / "engine").mkdir(parents=True)
    stale_jar = data_dir / launch.ENGINE_JAR
    stale_jar.write_bytes(b"stale-jar-bytes")
    assert launch.bridge_jar_sha256(data_dir, ("/usr/bin/python", "-m", "other")) is None
    assert (
        launch.bridge_jar_sha256(data_dir, ("/usr/bin/java", "-jar", str(tmp_path / "missing.jar")))
        is None
    )

    # P2-1: covered_by_sealed_epoch must stay False whenever bridge_jar_sha256 is missing
    decks = (
        _make_deck("d1", "Chulane, Teller of Tales"),
        _make_deck("d2", "Solphim, Mayhem Dominus"),
    )
    prepared = play.prepare_game(
        decks,
        seed=7,
        game_id="game-no-jar-sha",
        command=("/usr/bin/python", "-m", "other"),
        data_folder=data_dir,
        qualification={
            "status": BRIDGE_ALIGNED,
            "covered_by_sealed_epoch": True,
            "sealed_epoch": "test-epoch",
        },
    )
    assert prepared.header["bridge_jar_sha256"] is None
    assert prepared.header["covered_by_sealed_epoch"] is False

    recorder = GameRecorder(
        data_dir, "game-no-jar-sha", {**prepared.header, "covered_by_sealed_epoch": True}
    )
    closed = play.close_recorded_game(recorder, RuntimeError("boom"))
    assert closed["covered_by_sealed_epoch"] is False

    # P2-3: outcomes_for_folder emits missing-SHA warning even when ALL logs lack bridge_jar_sha256
    no_sha_dir = tmp_path / "no_sha_logs"
    no_sha_dir.mkdir()
    _write_outcome_log(
        no_sha_dir,
        "g_no_sha",
        decks=["base", "o1", "o2"],
        winners=[0],
        seed=5,
        hand_cards=["Sol Ring"],
        bridge_sha=None,
        qual_state=None,
        covered=False,
    )
    res_no_sha = card_outcomes.outcomes_for_folder(no_sha_dir, deck_id="base")
    assert res_no_sha["covered_by_sealed_epoch"] is False
    assert any("no bridge jar SHA-256" in w for w in res_no_sha["warnings"])


def test_logs_without_deck_hash_keep_bridge_provenance_and_warnings(tmp_path: Path) -> None:
    """#1657 review P1: the stand "Stand unbekannt" (logs of before #1657) is refused when its
    jars are mixed, names jar, qualification and BRIDGE_AHEAD, and warns on a missing SHA."""
    decks = ["base", "o1", "o2"]
    for game_id, seed, sha, state, covered in (
        ("g1", 1, "a" * 64, BRIDGE_ALIGNED, True),
        ("g2", 2, "b" * 64, BRIDGE_AHEAD, False),
    ):
        _write_outcome_log(
            tmp_path,
            game_id,
            decks=decks,
            winners=[seed - 1],
            seed=seed,
            hand_cards=["Sol Ring"] if seed == 1 else ["Forest"],
            bridge_sha=sha,
            qual_state=state,
            covered=covered,
            with_deck_hash=False,
        )
    with pytest.raises(ValueError, match="mixed bridge jar SHA-256"):
        card_outcomes.outcomes_for_folder(tmp_path, deck_id="base")
    mixed = card_outcomes.outcomes_for_folder(tmp_path, deck_id="base", allow_mixed=True)
    unknown = mixed["unknown_stand"]
    assert unknown is not None and unknown["games_total"] == 2
    assert set(unknown["bridge_jar_sha256s"]) == {"a" * 64, "b" * 64}
    assert BRIDGE_AHEAD in unknown["bridge_qualification_states"]
    assert unknown["covered_by_sealed_epoch"] is False
    assert any("BRIDGE_AHEAD_OF_QUALIFICATION" in w for w in unknown["warnings"])
    assert any(w.startswith("Stand unbekannt: BRIDGE_AHEAD") for w in mixed["warnings"])

    no_sha = tmp_path / "no_sha"
    no_sha.mkdir()
    _write_outcome_log(
        no_sha,
        "g3",
        decks=decks,
        winners=[0],
        seed=3,
        hand_cards=["Sol Ring"],
        bridge_sha=None,
        qual_state=None,
        covered=False,
        with_deck_hash=False,
    )
    res = card_outcomes.outcomes_for_folder(no_sha, deck_id="base")
    assert any(
        "Stand unbekannt: some games carry no bridge jar SHA-256" in w for w in res["warnings"]
    )
