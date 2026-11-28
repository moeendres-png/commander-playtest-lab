"""Unit tests for #1662 part 4: PLAY v1 postgame sheet, play_session, and play_note."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, card_outcomes, games, postgame
from commander_lab.studio.store import SCHEMA_VERSION, DataClass
from commander_lab.studio.web import create_app

_DECK_HASH = "a" * 64
_BRIDGE_SHA = "b" * 64
_HEADERS = {"X-Studio": "1"}


def _write_log(
    data_folder: Path,
    game_id: str,
    *,
    header: dict[str, object],
    frames: list[dict[str, object]],
    result: dict[str, object] | None,
    gzipped: bool = True,
) -> Path:
    folder = games.games_folder(data_folder)
    lines = [
        json.dumps(
            {
                "kind": "header",
                "schema": games.LOG_SCHEMA,
                "game_id": game_id,
                "rules_authority": "xmage",
                **header,
            }
        ),
        *[json.dumps({"kind": "frame", **frame}) for frame in frames],
    ]
    if result is not None:
        lines.append(json.dumps({"kind": "result", **result}))
    payload = "\n".join(lines) + "\n"
    if gzipped:
        path = folder / f"{game_id}.jsonl.gz"
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            handle.write(payload)
        return path
    path = folder / f"{game_id}.jsonl"
    path.write_text(payload, encoding="utf-8")
    return path


def _played_header(
    *,
    deck_id: str = "chulane",
    revision_id: str = "chulane@rev1",
    human_seats: list[int] | None = None,
    started_at: str = "2026-11-27T18:00:00Z",
) -> dict[str, object]:
    seats_human = [0] if human_seats is None else human_seats
    return {
        "data_class": "PLAYED_GAME" if seats_human else "SIMULATED_RESULT",
        "seed": 42,
        "engine_commit": "c" * 40,
        "bridge_jar_sha256": _BRIDGE_SHA,
        "bridge_qualification_state": "ALIGNED",
        "pilot": "GenericCommanderPilot 1.0.0",
        "pilot_fingerprint": "f" * 64,
        "decision_policy": "xmage-full-game-policy-1.0.0",
        "started_at": started_at,
        **({"human_seats": seats_human} if seats_human else {}),
        "seats": [
            {
                "seat": 0,
                "deck_id": deck_id,
                "studio_revision_id": revision_id,
                "deck_hash": _DECK_HASH,
                "commanders": ["Chulane, Teller of Tales"],
                "pilot": "Mensch" if 0 in seats_human else "KI",
            },
            {
                "seat": 1,
                "deck_id": "precon-opp",
                "deck_hash": "d" * 64,
                "commanders": ["Kinnan, Bonder Prodigy"],
                "pilot": "KI",
            },
        ],
    }


def _sample_played_frames() -> list[dict[str, object]]:
    return [
        {
            "n": 1,
            "turn": 1,
            "phase": "precombat_main",
            "step": "precombat_main",
            "active_seat": 0,
            "seat": 0,
            "decision_class": "mulligan",
            "chosen": ["Keep hand"],
            "players": [
                {
                    "seat": 0,
                    "life": 40,
                    "hand_count": 2,
                    "hand": ["Forest", "Sol Ring"],
                    "battlefield": [],
                },
                {"seat": 1, "life": 40, "hand_count": 2},
            ],
            "stack": [],
        },
        {
            "n": 2,
            "turn": 1,
            "phase": "precombat_main",
            "step": "precombat_main",
            "active_seat": 0,
            "seat": 0,
            "decision_class": "priority",
            "chosen": ["Sol Ring — Cast Sol Ring"],
            "players": [
                {
                    "seat": 0,
                    "life": 40,
                    "hand_count": 3,
                    "hand": ["Forest", "Sol Ring", "Llanowar Elves"],
                    "battlefield": [],
                },
                {"seat": 1, "life": 40, "hand_count": 2},
            ],
            "stack": [],
        },
        {
            "n": 3,
            "turn": 1,
            "phase": "precombat_main",
            "step": "precombat_main",
            "active_seat": 0,
            "seat": 1,
            "decision_class": "priority",
            "chosen": ["Pass priority"],
            "players": [
                {
                    "seat": 0,
                    "life": 40,
                    "hand_count": 2,
                    "hand": ["Forest", "Llanowar Elves"],
                    "battlefield": [],
                },
                {"seat": 1, "life": 40, "hand_count": 2, "hand": ["Island", "Opt"]},
            ],
            "stack": ["Sol Ring"],
        },
        {
            "n": 4,
            "turn": 2,
            "phase": "precombat_main",
            "step": "precombat_main",
            "active_seat": 0,
            "seat": 0,
            "decision_class": "priority",
            "chosen": ["Pass priority"],
            "players": [
                {
                    "seat": 0,
                    "life": 40,
                    "hand_count": 1,
                    "hand": ["Llanowar Elves"],
                    "battlefield": [{"name": "Forest"}, {"name": "Sol Ring"}],
                },
                {"seat": 1, "life": 0, "lost": True, "hand_count": 1},
            ],
            "stack": [],
        },
    ]


def test_schema_version_is_22_and_postgame_tables_exist(tmp_path: Path) -> None:
    # Schema 22a: the version moves 21 -> 22 (Owner decision 2026-11-28, #1703/#1856)
    assert SCHEMA_VERSION == 22
    store = StudioStore.open(tmp_path / "studio")
    try:
        version = store.connection.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()[0]
        assert version == "22"
        tables = {
            str(row[0])
            for row in store.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert {"play_session", "play_note"} <= tables
        assert store.count("play_session") == 0
        assert store.count("play_note") == 0
    finally:
        store.close()


def test_postgame_endpoint_summarizes_played_game_and_records_session_idempotently(
    tmp_path: Path,
) -> None:
    studio_dir = tmp_path / "studio"
    StudioStore.open(studio_dir).close()
    _write_log(
        studio_dir,
        "played-1",
        header=_played_header(),
        frames=_sample_played_frames(),
        result={
            "status": "finished",
            "winner_seats": [0],
            "ended_at": "2026-11-27T18:05:30Z",
            "bridge_jar_sha256": _BRIDGE_SHA,
            "bridge_qualification_state": "ALIGNED",
            "event_log": [
                {
                    "sequence": 1,
                    "type": "SPELL_CAST",
                    "turn": 1,
                    "step": "PRECOMBAT_MAIN",
                    "player_player": "P1",
                    "source_name": "Sol Ring",
                },
                {
                    "sequence": 2,
                    "type": "SPELL_CAST",
                    "turn": 1,
                    "step": "POSTCOMBAT_MAIN",
                    "player_player": "P2",
                    "source_name": "Opt",
                },
            ],
        },
    )

    with TestClient(create_app(studio_dir)) as client:
        resp = client.get("/api/games/played-1/postgame")
        assert resp.status_code == 200
        data = resp.json()
        assert data["game_id"] == "played-1"
        assert data["data_class"] == DataClass.PLAYED_GAME.value
        assert data["status"] == "finished"
        assert data["finished"] is True
        assert data["outcome"] == "won"
        assert data["winner_seats"] == [0]
        assert data["seed"] == 42
        assert data["deck_id"] == "chulane"
        assert data["revision_id"] == "chulane@rev1"
        assert data["deck_hash"] == _DECK_HASH
        assert data["human_seat"] == 0
        assert data["bridge_jar_sha256"] == _BRIDGE_SHA
        assert data["bridge_qualification_state"] == "ALIGNED"
        assert data["cards_drawn"] == ["Forest", "Sol Ring", "Llanowar Elves"]
        assert "Sol Ring" in data["cards_cast"]
        assert "Forest" in data["cards_cast"]
        assert "Opt" not in data["cards_cast"]
        assert data["cards_left_in_hand"] == ["Llanowar Elves"]
        assert data["human_clicks"] == 3
        assert data["duration_seconds"] == pytest.approx(330.0)
        assert data["total_turns"] == 2
        assert data["notes"] == []

        # Second call stays idempotent in play_session
        again = client.get("/api/games/played-1/postgame")
        assert again.status_code == 200
        assert client.get("/api/games/no-such-game/postgame").status_code == 404

    store = StudioStore.open(studio_dir)
    try:
        rows = store.connection.execute("SELECT * FROM play_session").fetchall()
        assert len(rows) == 1
        row = dict(rows[0])
        assert row["game_id"] == "played-1"
        assert row["data_class"] == "PLAYED_GAME"
        assert row["outcome"] == "won"
        assert row["human_seat"] == 0
        assert row["human_clicks"] == 3
        assert row["bridge_jar_sha256"] == _BRIDGE_SHA
        assert len(json.loads(row["table_json"])) == 2
    finally:
        store.close()


def test_notes_roundtrip_validation_and_revision_filtering(tmp_path: Path) -> None:
    studio_dir = tmp_path / "studio"
    StudioStore.open(studio_dir).close()
    _write_log(
        studio_dir,
        "played-r1",
        header=_played_header(deck_id="chulane", revision_id="chulane@rev1"),
        frames=_sample_played_frames(),
        result={"status": "finished", "winner_seats": [1], "ended_at": "2026-11-27T18:02:00Z"},
    )
    _write_log(
        studio_dir,
        "played-r2",
        header=_played_header(deck_id="chulane", revision_id="chulane@rev2"),
        frames=_sample_played_frames(),
        result={"status": "finished", "winner_seats": [0], "ended_at": "2026-11-27T18:10:00Z"},
    )

    with TestClient(create_app(studio_dir)) as client:
        # Empty/whitespace text -> 422
        assert (
            client.post(
                "/api/games/played-r1/notes",
                json={"note_text": "   ", "card_name": "Llanowar Elves"},
                headers=_HEADERS,
            ).status_code
            == 422
        )
        # Unknown game -> 404
        assert (
            client.post(
                "/api/games/does-not-exist/notes",
                json={"note_text": "Gute Karte"},
                headers=_HEADERS,
            ).status_code
            == 404
        )

        # Create notes without passing deck_id/revision_id -> derived from game log
        created1 = client.post(
            "/api/games/played-r1/notes",
            json={
                "note_text": "Kam zu spät, lieber ersetzen",
                "card_name": "Llanowar Elves",
                "action_hint": "replace",
            },
            headers=_HEADERS,
        )
        assert created1.status_code == 200
        note1 = created1.json()
        assert note1["deck_id"] == "chulane"
        assert note1["revision_id"] == "chulane@rev1"
        assert note1["card_name"] == "Llanowar Elves"
        assert note1["action_hint"] == "replace"

        created2 = client.post(
            "/api/games/played-r2/notes",
            json={"note_text": "Sol Ring stark auf Turn 1", "card_name": "Sol Ring"},
            headers=_HEADERS,
        )
        assert created2.status_code == 200
        assert created2.json()["revision_id"] == "chulane@rev2"

        # Postgame includes game notes
        pg1 = client.get("/api/games/played-r1/postgame").json()
        assert pg1["outcome"] == "lost"
        assert [n["note_text"] for n in pg1["notes"]] == ["Kam zu spät, lieber ersetzen"]

        # Deck endpoint filters by revision_id when given, or returns all notes for deck
        rev1_notes = client.get("/api/decks/chulane/play-notes?revision_id=chulane@rev1").json()
        assert rev1_notes["deck_id"] == "chulane"
        assert rev1_notes["revision_id"] == "chulane@rev1"
        assert len(rev1_notes["notes"]) == 1
        assert rev1_notes["notes"][0]["action_hint"] == "replace"
        assert rev1_notes["notes"][0]["card_name"] == "Llanowar Elves"

        all_deck_notes = client.get("/api/decks/chulane/play-notes").json()
        assert len(all_deck_notes["notes"]) == 2


def test_negative_control_played_sessions_and_notes_never_touch_card_outcomes(
    tmp_path: Path,
) -> None:
    studio_dir = tmp_path / "studio"
    StudioStore.open(studio_dir).close()

    # One simulated game for chulane
    _write_log(
        studio_dir,
        "sim-1",
        header=_played_header(human_seats=[]),
        frames=[
            {
                "n": 1,
                "turn": 1,
                "phase": "precombat_main",
                "step": "precombat_main",
                "active_seat": 0,
                "seat": 0,
                "decision_class": "mulligan",
                "chosen": ["Keep hand"],
                "players": [
                    {"seat": 0, "hand": ["Forest", "Sol Ring"], "battlefield": []},
                    {"seat": 1, "hand_count": 7, "battlefield": []},
                ],
                "stack": [],
            }
        ],
        result={"status": "finished", "winner_seats": [0], "ended_at": "2026-11-27T18:01:00Z"},
    )
    baseline = card_outcomes.outcomes_for_folder(
        games.games_folder(studio_dir), deck_id="chulane", min_exposed=1
    )

    # Add a PLAYED_GAME, persist play_session and play_note
    _write_log(
        studio_dir,
        "played-only",
        header=_played_header(human_seats=[0]),
        frames=_sample_played_frames(),
        result={"status": "finished", "winner_seats": [1], "ended_at": "2026-11-27T18:03:00Z"},
    )
    with TestClient(create_app(studio_dir)) as client:
        pg_played = client.get("/api/games/played-only/postgame").json()
        assert pg_played["data_class"] == "PLAYED_GAME"
        pg_sim = client.get("/api/games/sim-1/postgame").json()
        assert pg_sim["data_class"] == "SIMULATED_RESULT"
        assert pg_sim["human_seat"] is None
        assert pg_sim["human_clicks"] is None
        client.post(
            "/api/games/played-only/notes",
            json={"note_text": "Notiz beeinflusst Simulationen nicht", "action_hint": "cut"},
            headers=_HEADERS,
        )

    after = card_outcomes.outcomes_for_folder(
        games.games_folder(studio_dir), deck_id="chulane", min_exposed=1
    )
    assert after["games_total"] == baseline["games_total"] == 1
    assert after["cards"] == baseline["cards"]
    assert after["played_cohort"]["games"] == 1
    assert after["played_cohort"]["games_finished"] == 1


def test_postgame_handles_running_and_draw_and_empty_note_error(tmp_path: Path) -> None:
    studio_dir = tmp_path / "studio"
    store = StudioStore.open(studio_dir)
    try:
        with pytest.raises(ValueError, match="note_text"):
            postgame.add_play_note(store, game_id="g", note_text="  ")

        _write_log(
            studio_dir,
            "running-1",
            header=_played_header(),
            frames=_sample_played_frames()[:1],
            result=None,
            gzipped=False,
        )
        with TestClient(create_app(studio_dir)) as client:
            running = client.get("/api/games/running-1/postgame").json()
            assert running["finished"] is False
            assert running["status"] == "running"
            assert running["outcome"] == "incomplete"
            assert running["duration_seconds"] is None
        # Running games are not recorded into play_session
        assert store.count("play_session") == 0

        _write_log(
            studio_dir,
            "draw-1",
            header=_played_header(),
            frames=[],
            result={"status": "finished", "winner_seats": [0, 1]},
        )
        draw_summary = postgame.summarize_game_for_postgame(studio_dir, "draw-1")
        assert draw_summary["outcome"] == "draw"
        assert draw_summary["human_clicks"] is None
        assert draw_summary["total_turns"] is None
        assert draw_summary["duration_seconds"] is None
    finally:
        store.close()
