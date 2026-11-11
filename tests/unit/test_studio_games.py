"""Studio game logs: what the recorder writes and what the viewer reads.

All data here is synthetic. No engine runs in these tests.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, create_revision, games, launch
from commander_lab.studio.images import cached_image_by_name, public_card
from commander_lab.studio.web import create_app
from tests.unit.test_studio_builder import _deck, _fill

HEADER = {"seed": 7, "engine_commit": "a" * 40, "seats": [{"seat": 0}, {"seat": 1}]}


def _decision(seat: int = 0, *, turn: int = 1, label: str = "Forest — Play Forest") -> dict:
    return {
        "decision_class": "priority",
        "seat": seat,
        "actor_id": f"p{seat}",
        "prompt": "<div style='font-size:11pt'>Choose &amp; act</div>",
        "legal_options": [
            {"option_id": "o1", "label": label},
            {"option_id": "o2", "label": "Pass priority"},
        ],
        "source_object": {"name": "Forest"},
        "pilot_state": {
            "turn_number": turn,
            "phase": "precombat_main",
            "step": "precombat_main",
            "active_player_id": "p0",
            "players": [
                {
                    "player_id": "p0",
                    "seat": 0,
                    "life": 40,
                    "poison_counters": 0,
                    "hand_count": 1,
                    "library_count": 90,
                    "is_actor": seat == 0,
                    "has_lost": False,
                    "has_won": False,
                    "hand": [{"name": "Forest"}],
                    "mana_pool": {"green": 1, "blue": 0},
                    "battlefield": [
                        {
                            "name": "Test Bear",
                            "tapped": True,
                            "power": 2,
                            "toughness": 2,
                            "damage": 0,
                            "abilities": ["long text"],
                            "counters": [{"type": "+1/+1", "count": 2}],
                        },
                        {"name": "Secret", "face_down": True, "tapped": False},
                    ],
                    "graveyard": [{"name": "Old Spell"}],
                    "command": [{"name": "Test Commander"}],
                    "exile_count": 3,
                },
                {
                    "player_id": "opponent-1",
                    "seat": 1,
                    "life": 38,
                    "hand_count": 7,
                    "library_count": 92,
                    "battlefield": [],
                    "graveyard": [],
                    "command": [],
                },
            ],
            "stack": [{"name": "<font color='red'>Bolt</font>"}],
        },
    }


def test_a_frame_keeps_the_published_board_and_the_answer() -> None:
    frame = games.frame_of(5, _decision(), {"selected_option_ids": ["o1"], "numeric_choice": 3})
    assert frame["n"] == 5
    assert (frame["turn"], frame["phase"], frame["active_seat"], frame["seat"]) == (
        1, "precombat_main", 0, 0,
    )  # fmt: skip
    assert frame["prompt"] == "Choose & act"  # the client markup is gone, the words stay
    assert frame["chosen"] == ["Forest — Play Forest"]
    assert frame["options"] == 2
    assert frame["numeric_choice"] == 3
    assert frame["stack"] == ["Bolt"]
    assert frame["source"] == "Forest"
    own, other = frame["players"]
    assert own["hand"] == ["Forest"]
    assert own["mana_pool"] == {"green": 1}
    assert own["battlefield"][0] == {
        "name": "Test Bear",
        "tapped": True,
        "power": 2,
        "toughness": 2,
        "damage": 0,
        "counters": {"+1/+1": 2},
    }
    assert own["battlefield"][1]["name"] == "(verdeckt)"  # a face-down card is never named
    assert own["graveyard"] == ["Old Spell"]
    assert own["command"] == ["Test Commander"]
    assert own["exile_count"] == 3
    assert "hand" not in other  # the engine publishes only the actor's hand
    assert other["hand_count"] == 7


def test_recorder_writes_a_log_that_can_be_read_in_pages(tmp_path: Path) -> None:
    recorder = games.GameRecorder(tmp_path, "g1", HEADER)
    policy = games.RecordingPolicy(_Fixed({"selected_option_ids": ["o2"]}), recorder)
    for turn in range(1, 6):
        assert policy.decide(_decision(turn=turn)) == {"selected_option_ids": ["o2"]}

    running = games.read_game(tmp_path, "g1")
    assert running["running"] is True
    assert running["result"] is None
    assert running["total"] == 5

    packed = recorder.close({"status": "finished", "winner_seats": [1]})
    assert packed.name == "g1.jsonl.gz"
    assert not (tmp_path / "games" / "g1.jsonl").exists()

    page = games.read_game(tmp_path, "g1", start=3, count=10)
    assert [frame["n"] for frame in page["frames"]] == [4, 5]
    assert page["total"] == 5
    assert page["running"] is False
    assert page["result"]["winner_seats"] == [1]
    assert page["header"]["data_class"] == "SIMULATED_RESULT"
    assert page["header"]["rules_authority"] == "xmage"
    assert page["frames"][0]["chosen"] == ["Pass priority"]

    listed = games.list_games(tmp_path)
    assert [(game["game_id"], game["frames"], game["running"]) for game in listed] == [
        ("g1", 5, False)
    ]


class _Fixed:
    def __init__(self, response: dict[str, object]) -> None:
        self.response = response

    def decide(self, decision: dict[str, object]) -> dict[str, object]:
        return self.response


def test_a_half_written_entry_is_not_read_and_a_dead_game_is_not_running(tmp_path: Path) -> None:
    recorder = games.GameRecorder(tmp_path, "live", HEADER)
    recorder.record(_decision(), {"selected_option_ids": ["o1"]})
    with recorder.path.open("a", encoding="utf-8") as handle:
        handle.write('{"kind":"frame","n":2')  # the writer is in the middle of an entry
    assert games.read_game(tmp_path, "live")["total"] == 1

    old = recorder.path.stat().st_mtime - games.STALE_SECONDS - 5
    os.utime(recorder.path, (old, old))
    stale = games.read_game(tmp_path, "live")
    assert stale["running"] is False
    assert stale["result"]["status"] == "failed"


def test_game_ids_are_checked_and_made_free(tmp_path: Path) -> None:
    assert games.free_game_id(tmp_path, "Custom/Chulane 4p") == "custom-chulane-4p"
    games.GameRecorder(tmp_path, "custom-chulane-4p", HEADER).close({"status": "finished"})
    assert games.free_game_id(tmp_path, "Custom/Chulane 4p") == "custom-chulane-4p-2"
    with pytest.raises(ValueError):
        games.GameRecorder(tmp_path, "../outside", HEADER)
    with pytest.raises(ValueError):
        games.read_game(tmp_path, "../outside")
    with pytest.raises(KeyError):
        games.read_game(tmp_path, "missing")
    (tmp_path / "games" / "other.jsonl").write_text('{"kind":"header","schema":"x"}\n')
    assert [game["game_id"] for game in games.list_games(tmp_path)] == ["custom-chulane-4p"]


@pytest.fixture
def studio_folder(tmp_path: Path) -> Path:
    folder = tmp_path / "studio"
    store = StudioStore.open(folder)
    _fill(store, tmp_path)
    create_revision(store, deck_id="test", name="Test", cards=_deck())
    store.close()
    return folder


def test_public_card_by_name_and_image_cache(studio_folder: Path) -> None:
    store = StudioStore.open(studio_folder)
    try:
        assert public_card(store, "Forest")["type_line"] == "Basic Land — Forest"
        # the engine names a two-faced card by its front face
        assert public_card(store, "Filler 00")["name"] == "Filler 00 // Hidden Back"
        assert public_card(store, "No Such Card") is None
        assert cached_image_by_name(store, "Forest", fetch=False) is None
        (studio_folder / "images" / "oracle-forest-front.jpg").write_bytes(b"jpg")
        assert cached_image_by_name(store, "Forest", fetch=False) is not None
    finally:
        store.close()


def test_web_application_serves_games(studio_folder: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(launch.ENGINE_COMMAND_ENV, raising=False)
    recorder = games.GameRecorder(studio_folder, "g1", HEADER)
    recorder.record(_decision(), {"selected_option_ids": ["o1"]})
    recorder.close({"status": "finished", "winner_seats": [0]})
    marker = {"X-Studio": "1"}
    with TestClient(create_app(studio_folder)) as client:
        listed = client.get("/api/games").json()
        assert [game["game_id"] for game in listed] == ["g1"]
        game = client.get("/api/games/g1?start=0&count=10").json()
        assert game["total"] == 1
        assert game["frames"][0]["chosen"] == ["Forest — Play Forest"]
        assert client.get("/api/games/nope").status_code == 404
        assert client.get("/api/games/..%2Fx").status_code == 404

        facts = client.post(
            "/api/public-cards", json={"names": ["Forest", "No Such Card"]}, headers=marker
        ).json()
        assert list(facts) == ["Forest"]
        assert "image_front" not in facts["Forest"]
        assert client.get("/img-name?name=No%20Such%20Card").status_code == 404
        assert client.get("/partie.html").status_code == 200

        table = client.get("/api/table").json()
        assert table["engine"]["ready"] is False
        assert table["decks"][0]["deck_id"] == "test"
        assert len(table["opponents"]) > 100
        assert set(table["pods"]) == {"precon", "mixed", "optimized"}
        opp_ids = {d["deck_id"] for d in table["opponents"]}
        for pod_ids in table["pods"].values():
            assert set(pod_ids).issubset(opp_ids)
        body = {
            "revision_id": table["decks"][0]["branches"][0]["revision_id"],
            "opponent_ids": [table["opponents"][0]["deck_id"]],
            "seed": 1,
        }
        assert client.post("/api/games", json=body).status_code == 403  # no request marker
        assert client.post("/api/games", json=body, headers=marker).status_code == 409


def test_engine_command_comes_from_the_environment_or_the_data_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(launch.ENGINE_COMMAND_ENV, raising=False)
    assert launch.engine_command(tmp_path) is None
    assert "Engine-Datei" in str(launch.engine_state(tmp_path)["reason"])
    jar = tmp_path / launch.ENGINE_JAR
    jar.parent.mkdir()
    jar.write_bytes(b"jar")
    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.delenv("JAVA_HOME", raising=False)
    assert launch.engine_command(tmp_path) is None
    assert "Java" in str(launch.engine_state(tmp_path)["reason"])
    monkeypatch.setattr(launch.shutil, "which", lambda name: "/usr/bin/java")
    assert launch.engine_command(tmp_path) == (
        "/usr/bin/java", "-Xmx3g", "-jar", str(jar), "full-game",
    )  # fmt: skip
    monkeypatch.setenv(launch.ENGINE_COMMAND_ENV, "java -jar 'my bridge.jar' full-game")
    assert launch.engine_command(tmp_path) == ("java", "-jar", "my bridge.jar", "full-game")


def test_starting_a_game_checks_its_seats_before_any_process_starts(
    studio_folder: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(launch.ENGINE_COMMAND_ENV, "java -jar bridge.jar full-game")
    started: list[list[str]] = []

    class _Process:
        def __init__(self, command: list[str], **_: object) -> None:
            started.append(command)
            recorder = games.GameRecorder(
                studio_folder, command[command.index("--game-id") + 1], HEADER
            )
            recorder.close({"status": "finished"})

        def poll(self) -> int:
            return 0

    monkeypatch.setattr(launch.subprocess, "Popen", _Process)
    monkeypatch.setattr(launch, "cards_unknown_to_pilots", lambda snapshot: [])
    opponents = [deck["deck_id"] for deck in launch.opponent_decks()[:2]]
    store = StudioStore.open(studio_folder)
    try:
        revision = store.connection.execute("SELECT revision_id FROM deck_branch").fetchone()[0]
        with pytest.raises(ValueError):
            launch.start_game(store, studio_folder, revision_id=revision, opponent_ids=[], seed=1)
        with pytest.raises(ValueError):
            launch.start_game(
                store, studio_folder, revision_id=revision, opponent_ids=opponents[:1] * 2, seed=1
            )
        with pytest.raises(KeyError):
            launch.start_game(
                store, studio_folder, revision_id=revision, opponent_ids=["nope"], seed=1
            )
        with pytest.raises(KeyError):
            launch.start_game(
                store, studio_folder, revision_id="nope@0", opponent_ids=opponents, seed=1
            )
        assert started == []

        game_id = launch.start_game(
            store, studio_folder, revision_id=revision, opponent_ids=opponents, seed=11
        )
        assert game_id == "test-3p-seed11"
        command = started[0]
        assert command[command.index("--seed") + 1] == "11"
        decks = [command[i + 1] for i, part in enumerate(command) if part == "--deck"]
        assert len(decks) == 3
        own = json.loads(Path(decks[0]).read_text(encoding="utf-8"))
        assert own["studio_revision_id"] == revision
        assert Path(decks[0]).is_relative_to(studio_folder)  # the own deck stays in the data folder

        monkeypatch.setattr(launch, "cards_unknown_to_pilots", lambda snapshot: ["Odd Card"])
        with pytest.raises(ValueError, match="Odd Card"):
            launch.start_game(
                store, studio_folder, revision_id=revision, opponent_ids=opponents, seed=12
            )
    finally:
        store.close()


def test_public_card_token_mapping(studio_folder: Path) -> None:
    store = StudioStore.open(studio_folder)
    try:
        source_id = store.connection.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0]
        # Insert a synthetic card and test token fallback
        store.connection.execute(
            "INSERT INTO scryfall_card (oracle_id, scryfall_id, name, front_name, layout, "
            "mana_cost, mana_value, type_line, oracle_text, color_identity, commander_legality, "
            "keywords, produced_mana, source_id, image_front) "
            "VALUES ('o-food', 's-food', 'Food', 'Food', 'token', '', 0, 'Artifact — Food', "
            "'Sacrifice: Gain 3 life', '', 'not_legal', '[]', '', ?, 'https://cards.scryfall.io/food.jpg')",
            (source_id,),
        )
        store.connection.commit()

        # Querying "Food Token" should find "Food"
        card = public_card(store, "Food Token")
        assert card is not None
        assert card["name"] == "Food"
        assert card["image_front"] == "https://cards.scryfall.io/food.jpg"

        # Querying "Food" finds "Food" directly
        card_direct = public_card(store, "Food")
        assert card_direct is not None
        assert card_direct["oracle_id"] == "o-food"
    finally:
        store.close()


def test_combat_and_target_tracking_in_frames(tmp_path: Path) -> None:
    recorder = games.GameRecorder(tmp_path, "combat-test", HEADER)

    # Turn 2, combat phase: declare attacker
    atk_decision = {
        "decision_class": "declare_attacker",
        "seat": 0,
        "pilot_state": {
            "turn_number": 2,
            "phase": "combat",
            "step": "declare_attackers",
            "active_player_id": "p0",
            "players": [{"seat": 0, "battlefield": [{"name": "Grizzly Bears"}]}],
        },
        "legal_options": [
            {"option_id": "o1", "label": "Grizzly Bears attacks Full Game Seat 1"},
            {"option_id": "o2", "label": "Hold Grizzly Bears"},
        ],
    }
    recorder.record(atk_decision, {"selected_option_ids": ["o1"]})

    # declare blocker
    blk_decision = {
        "decision_class": "declare_blocker",
        "seat": 1,
        "pilot_state": {
            "turn_number": 2,
            "phase": "combat",
            "step": "declare_blockers",
            "active_player_id": "p0",
            "players": [{"seat": 1, "battlefield": [{"name": "Giant Spider"}]}],
        },
        "legal_options": [
            {"option_id": "b1", "label": "Giant Spider blocks Grizzly Bears"},
        ],
    }
    recorder.record(blk_decision, {"selected_option_ids": ["b1"]})

    # spell target
    tgt_decision = {
        "decision_class": "target",
        "seat": 0,
        "pilot_state": {
            "turn_number": 2,
            "phase": "postcombat_main",
            "step": "postcombat_main",
            "players": [],
        },
        "legal_options": [
            {"option_id": "t1", "label": "Grizzly Bears"},
        ],
    }
    recorder.record(tgt_decision, {"selected_option_ids": ["t1"]})

    recorder.close({"status": "finished"})

    game = games.read_game(tmp_path, "combat-test")
    frames = game["frames"]
    assert len(frames) == 3

    # Frame 1: attack
    assert frames[0]["combat"]["attacks"] == [
        {"attacker": "Grizzly Bears", "target": "Full Game Seat 1"}
    ]
    # Frame 2: accumulated combat carries attack + block
    assert frames[1]["combat"]["attacks"] == [
        {"attacker": "Grizzly Bears", "target": "Full Game Seat 1"}
    ]
    assert frames[1]["combat"]["blocks"] == [
        {"blocker": "Giant Spider", "attacker": "Grizzly Bears"}
    ]

    # Frame 3: target decision recorded in targets, combat reset
    assert frames[2]["targets"] == ["Grizzly Bears"]
    assert "combat" not in frames[2]


def test_exile_list_in_player() -> None:
    raw_player = {
        "seat": 0,
        "life": 40,
        "exile": [
            {"name": "Path to Exile"},
            {"name": "Hidden Threat", "face_down": True},
        ],
    }
    parsed = games._player(raw_player)
    assert parsed["exile_count"] == 2
    assert parsed["exile"] == ["Path to Exile", "(verdeckt)"]


def test_delete_game_and_orphaned_out(tmp_path: Path) -> None:
    folder = games.games_folder(tmp_path)

    # 1. Normal game deletion
    rec = games.GameRecorder(tmp_path, "del-me", HEADER)
    rec.record(_decision(), {"selected_option_ids": ["o1"]})
    gz_path = rec.close({"status": "finished"})
    out_path = folder / "del-me.out"
    out_path.write_text("process output\n", encoding="utf-8")

    assert gz_path.is_file()
    assert out_path.is_file()
    assert games.delete_game(tmp_path, "del-me") is True
    assert not gz_path.exists()
    assert not out_path.exists()

    with pytest.raises(KeyError):
        games.delete_game(tmp_path, "del-me")

    # 2. Orphaned .out file (process crashed before writing .jsonl)
    orphaned_out = folder / "crashed-start.out"
    orphaned_out.write_text(
        "Exception in thread main: java.lang.OutOfMemoryError\n", encoding="utf-8"
    )

    listed = games.list_games(tmp_path)
    assert any(g["game_id"] == "crashed-start" for g in listed)

    crashed = games.read_game(tmp_path, "crashed-start")
    assert crashed["running"] is False
    assert crashed["result"]["status"] == "failed"
    assert crashed["result"]["failure_class"] == "start_failed"
    assert "OutOfMemoryError" in crashed["result"]["failure_message"]
    assert "OutOfMemoryError" in crashed["result"]["stdout"]

    # Delete the orphaned game
    assert games.delete_game(tmp_path, "crashed-start") is True
    assert not orphaned_out.exists()


def test_web_api_delete_game(studio_folder: Path) -> None:
    rec = games.GameRecorder(studio_folder, "api-del", HEADER)
    rec.record(_decision(), {"selected_option_ids": ["o1"]})
    rec.close({"status": "finished"})

    marker = {"X-Studio": "1"}
    with TestClient(create_app(studio_folder)) as client:
        # Without marker -> 403
        assert client.delete("/api/games/api-del").status_code == 403
        # With marker -> 200
        res = client.delete("/api/games/api-del", headers=marker)
        assert res.status_code == 200
        assert res.json() == {"deleted": True, "game_id": "api-del"}
        # Second time -> 404
        assert client.delete("/api/games/api-del", headers=marker).status_code == 404


def test_engine_command_with_java_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(launch.ENGINE_COMMAND_ENV, raising=False)
    jar = tmp_path / launch.ENGINE_JAR
    jar.parent.mkdir()
    jar.write_bytes(b"jar")

    fake_java_home = tmp_path / "jdk"
    java_bin = fake_java_home / "bin"
    java_bin.mkdir(parents=True)
    fake_java = java_bin / ("java.exe" if os.name == "nt" else "java")
    fake_java.write_bytes(b"")

    monkeypatch.setattr(shutil, "which", lambda name: None)
    monkeypatch.setenv("JAVA_HOME", str(fake_java_home))

    cmd = launch.engine_command(tmp_path)
    assert cmd is not None
    assert cmd[0] == str(fake_java)
