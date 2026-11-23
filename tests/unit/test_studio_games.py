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
from commander_lab.studio.images import cached_image_by_name, public_card, web_image_url_by_name
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
        assert (
            web_image_url_by_name(store, "Forest")
            == "https://cards.scryfall.io/normal/front/a/b/forest.jpg"
        )
        assert not (studio_folder / "images").exists()
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
        assert client.get("/img/by-name?name=No%20Such%20Card").status_code == 404
        redir1 = client.get("/img-name?name=Forest", follow_redirects=False)
        assert redir1.status_code == 302
        assert redir1.headers["location"] == "https://cards.scryfall.io/normal/front/a/b/forest.jpg"
        redir2 = client.get("/img/by-name?name=Forest", follow_redirects=False)
        assert redir2.status_code == 302
        assert redir2.headers["location"] == "https://cards.scryfall.io/normal/front/a/b/forest.jpg"
        assert not (studio_folder / "images").exists()
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
    # a Java that is known to be too old is named instead of failing inside the engine
    monkeypatch.setattr(launch, "_java_major", lambda java: 8)
    assert launch.engine_command(tmp_path) is None
    old = launch.engine_state(tmp_path)
    assert old["ready"] is False and old["java_version"] == 8
    assert "zu alt" in str(old["reason"]) and "17" in str(old["reason"])
    # an unreadable version does not block: the engine process decides
    monkeypatch.setattr(launch, "_java_major", lambda java: None)
    assert launch.engine_state(tmp_path)["ready"] is True
    monkeypatch.setattr(launch, "_java_major", lambda java: 21)
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
    monkeypatch.setattr(launch, "cards_unsupported_by_engine", lambda snapshot: [])
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

        monkeypatch.setattr(launch, "cards_unknown_to_pilots", lambda snapshot: [])
        monkeypatch.setattr(
            launch, "cards_unsupported_by_engine", lambda snapshot: ["Unknown Engine Card"]
        )
        with pytest.raises(ValueError, match="Unknown Engine Card"):
            launch.start_game(
                store, studio_folder, revision_id=revision, opponent_ids=opponents, seed=13
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


def test_java_major_version_is_read_from_both_version_formats() -> None:
    assert launch._parse_java_major('openjdk version "17.0.9" 2023-10-17') == 17
    assert launch._parse_java_major('java version "1.8.0_392"') == 8
    assert launch._parse_java_major('openjdk version "21" 2023-09-19') == 21
    assert launch._parse_java_major("keine Versionsangabe") is None
    assert launch._java_major("/nonexistent/java-binary") is None


def test_canonicalize_event_log_orders_simultaneous_events_stably_across_permutations() -> None:
    import random

    before_combat: list[dict[str, object]] = [
        {
            "sequence": 1,
            "type": "BEGIN_TURN",
            "turn": 5,
            "step": "UNTAP",
            "player_player": "seat_1",
        },
        {
            "sequence": 2,
            "type": "DECLARED_ATTACKERS",
            "turn": 5,
            "step": "DECLARE_ATTACKERS",
            "player_player": "seat_1",
        },
    ]
    simultaneous: list[dict[str, object]] = [
        {
            "sequence": 3,
            "type": "DAMAGED_PERMANENT",
            "turn": 5,
            "step": "COMBAT_DAMAGE",
            "combat": True,
            "amount": 3,
            "source_name": "Llanowar Elves",
            "target_name": "Runeclaw Bear",
        },
        {
            "sequence": 4,
            "type": "DAMAGED_PERMANENT",
            "turn": 5,
            "step": "COMBAT_DAMAGE",
            "combat": True,
            "amount": 2,
            "source_name": "Runeclaw Bear",
            "target_name": "Llanowar Elves",
        },
        {
            "sequence": 5,
            "type": "DAMAGED_PLAYER",
            "turn": 5,
            "step": "COMBAT_DAMAGE",
            "combat": True,
            "amount": 4,
            "source_name": "Questing Beast",
            "target_player": "seat_2",
        },
    ]
    after_combat: list[dict[str, object]] = [
        {
            "sequence": 6,
            "type": "SPELL_CAST",
            "turn": 5,
            "step": "POSTCOMBAT_MAIN",
            "source_name": "Cultivate",
        },
        {
            "sequence": 7,
            "type": "BEGIN_TURN",
            "turn": 6,
            "step": "UNTAP",
            "player_player": "seat_2",
        },
    ]

    rng = random.Random(1595)
    canonical_runs: list[list[dict[str, object]]] = []
    hashes: set[str] = set()
    for _ in range(10):
        shuffled = [dict(ev) for ev in simultaneous]
        rng.shuffle(shuffled)
        combined = [dict(ev) for ev in before_combat] + shuffled + [dict(ev) for ev in after_combat]
        for idx, ev in enumerate(combined, start=1):
            ev["sequence"] = idx
        canon = games.canonicalize_event_log(combined)
        canonical_runs.append(canon)
        hashes.add(games.event_log_sha256(combined))

    assert len(hashes) == 1
    first = canonical_runs[0]
    for run in canonical_runs[1:]:
        assert run == first
    # Idempotence & preserved chronological step boundaries
    assert games.canonicalize_event_log(first) == first
    assert [ev["sequence"] for ev in first] == list(range(1, len(first) + 1))
    assert [ev["step"] for ev in first] == [
        "UNTAP",
        "DECLARE_ATTACKERS",
        "COMBAT_DAMAGE",
        "COMBAT_DAMAGE",
        "COMBAT_DAMAGE",
        "POSTCOMBAT_MAIN",
        "UNTAP",
    ]
    assert [ev["turn"] for ev in first] == [5, 5, 5, 5, 5, 5, 6]

    # Negative control: an actual semantic change changes the digest
    altered = [dict(ev) for ev in first]
    altered[2] = {**altered[2], "amount": 99}
    assert games.event_log_sha256(altered) != next(iter(hashes))


def test_recorder_and_read_game_canonicalize_event_log_including_legacy_logs(
    tmp_path: Path,
) -> None:
    import gzip
    import json

    ev_a: dict[str, object] = {
        "sequence": 1,
        "type": "DAMAGED_PERMANENT",
        "turn": 4,
        "step": "COMBAT_DAMAGE",
        "amount": 2,
        "target_name": "Alpha",
    }
    ev_b: dict[str, object] = {
        "sequence": 2,
        "type": "DAMAGED_PERMANENT",
        "turn": 4,
        "step": "COMBAT_DAMAGE",
        "amount": 2,
        "target_name": "Beta",
    }

    rec1 = games.GameRecorder(tmp_path, "run-a", HEADER)
    rec1.save_event_log([ev_a, ev_b])
    rec1.close({"status": "finished"})

    rec2 = games.GameRecorder(tmp_path, "run-b", HEADER)
    rec2.save_event_log([{**ev_b, "sequence": 1}, {**ev_a, "sequence": 2}])
    rec2.close({"status": "finished"})

    g1 = games.read_game(tmp_path, "run-a")
    g2 = games.read_game(tmp_path, "run-b")
    assert g1["result"]["event_log"] == g2["result"]["event_log"]
    assert games.event_log_sha256(g1["result"]["event_log"]) == games.event_log_sha256(
        g2["result"]["event_log"]
    )

    # Legacy log written in swapped order on disk must also be canonicalized on read
    legacy_path = tmp_path / "games" / "legacy-swapped.jsonl.gz"
    with gzip.open(legacy_path, "wt", encoding="utf-8") as fh:
        fh.write(json.dumps({"kind": "header", "schema": games.LOG_SCHEMA, **HEADER}) + "\n")
        fh.write(
            json.dumps(
                {
                    "kind": "result",
                    "status": "finished",
                    "event_log": [{**ev_b, "sequence": 1}, {**ev_a, "sequence": 2}],
                }
            )
            + "\n"
        )
    legacy = games.read_game(tmp_path, "legacy-swapped")
    assert legacy["result"]["event_log"] == g1["result"]["event_log"]


def test_buffered_fast_gzip_recorder_matches_flushed_level9_byte_for_byte(tmp_path: Path) -> None:
    """#1579: buffered series recording (flush_each_frame=False, gzip_compresslevel=1) produces
    byte-identical decompressed frames to interactive recording (flush_each_frame=True, level 9),
    keeps live-frame visibility for interactive mode, and fails closed on invalid compress levels."""
    import gzip

    from commander_lab.studio.play_batch import BatchRecordingRunner

    d_priority = _decision(turn=1, label="<b>Cast</b> Sol Ring")
    d_attack = _decision(turn=2, label="Attack — Grizzly Bears attacks Seat 2")
    d_attack["decision_class"] = "declare_attacker"
    d_attack["pilot_state"]["phase"] = "combat"
    d_attack["pilot_state"]["step"] = "declare_attackers"
    d_block = _decision(turn=2, label="Block — Llanowar Elves blocks Grizzly Bears")
    d_block["decision_class"] = "declare_blocker"
    d_block["pilot_state"]["phase"] = "combat"
    d_block["pilot_state"]["step"] = "declare_blockers"
    sample_decisions = [
        (d_priority, {"selected_option_ids": ["o1"]}),
        (d_attack, {"selected_option_ids": ["o1"]}),
        (d_block, {"selected_option_ids": ["o1"]}),
    ]

    interactive = games.GameRecorder(
        tmp_path, "rec-interactive", HEADER, flush_each_frame=True, gzip_compresslevel=9
    )
    interactive.record(*sample_decisions[0])
    # Live PLAY must flush immediately so a spectator reading the open .jsonl sees the frame.
    live_view = games.read_game(tmp_path, "rec-interactive")
    assert len(live_view["frames"]) == 1
    for dec, resp in sample_decisions[1:]:
        interactive.record(dec, resp)
    p_interactive = interactive.close({"status": "finished", "winner_seat": 1})

    series = games.GameRecorder(
        tmp_path, "rec-series", HEADER, flush_each_frame=False, gzip_compresslevel=1
    )
    for dec, resp in sample_decisions:
        series.record(dec, resp)
    p_series = series.close({"status": "finished", "winner_seat": 1})

    lines_interactive = gzip.decompress(p_interactive.read_bytes()).decode("utf-8").splitlines()
    lines_series = gzip.decompress(p_series.read_bytes()).decode("utf-8").splitlines()
    assert lines_interactive[1:-1] == lines_series[1:-1]

    read_i = games.read_game(tmp_path, "rec-interactive")
    read_s = games.read_game(tmp_path, "rec-series")
    assert read_i["frames"] == read_s["frames"]
    assert read_s["frames"][1]["combat"] == {
        "attacks": [{"attacker": "Grizzly Bears", "target": "Seat 2"}]
    }
    assert read_s["frames"][2]["combat"] == {
        "attacks": [{"attacker": "Grizzly Bears", "target": "Seat 2"}],
        "blocks": [{"blocker": "Llanowar Elves", "attacker": "Grizzly Bears"}],
    }

    with pytest.raises(ValueError, match="gzip_compresslevel"):
        games.GameRecorder(tmp_path, "bad-level", HEADER, gzip_compresslevel=0)

    runner = BatchRecordingRunner(tmp_path, {"s1": ("batch-g1", dict(HEADER))}, command=None)
    batch_rec = runner.begin_game("s1")
    try:
        assert batch_rec.flush_each_frame is False
        assert batch_rec.gzip_compresslevel == 1
    finally:
        batch_rec.discard()


def test_face_down_target_and_blank_uuid_option_resolve_without_leaking_uuid_or_secret() -> None:
    """#1651: targeting a face-down permanent (XMage name '') must not emit a raw UUID in chosen
    or targets and must never expose private_identity."""
    target_uuid = "28380eaa-653b-40c1-9513-c81053483489"
    face_up_uuid = "11111111-2222-4333-8444-555555555555"
    unlisted_uuid = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"

    decision = _decision()
    decision["decision_class"] = "target"
    decision["prompt"] = "Select a creature you control"
    decision["legal_options"] = [
        {
            "option_id": target_uuid,
            "label": "",
            "option_type": "target",
            "metadata": {"object_id": target_uuid, "name": "", "zone": "battlefield"},
        },
        {
            "option_id": face_up_uuid,
            "label": face_up_uuid,
            "option_type": "target",
            "metadata": {"object_id": face_up_uuid, "name": "", "zone": "battlefield"},
        },
        {
            "option_id": unlisted_uuid,
            "label": "",
            "option_type": "target",
            "metadata": {"object_id": unlisted_uuid, "name": "", "zone": "battlefield"},
        },
    ]
    players = decision["pilot_state"]["players"]
    assert isinstance(players, list)
    players[0]["battlefield"] = [
        {
            "object_id": target_uuid,
            "name": "",
            "face_down": True,
            "private_identity": "Den Protector",
            "tapped": False,
            "power": 2,
            "toughness": 2,
            "damage": 0,
        },
        {
            "object_id": face_up_uuid,
            "name": "Grizzly Bears",
            "face_down": False,
            "tapped": False,
            "power": 2,
            "toughness": 2,
            "damage": 0,
        },
    ]

    frame_face_down = games.frame_of(602, decision, {"selected_option_ids": [target_uuid]})
    assert frame_face_down["chosen"] == ["(verdeckt)"]
    assert frame_face_down["targets"] == ["(verdeckt)"]
    assert "Den Protector" not in str(frame_face_down)
    assert target_uuid not in str(frame_face_down)

    frame_face_up = games.frame_of(603, decision, {"selected_option_ids": [face_up_uuid]})
    assert frame_face_up["chosen"] == ["Grizzly Bears"]
    assert frame_face_up["targets"] == ["Grizzly Bears"]

    frame_unknown = games.frame_of(604, decision, {"selected_option_ids": [unlisted_uuid]})
    assert frame_unknown["chosen"] == ["?"]
    assert unlisted_uuid not in str(frame_unknown)

    # Non-UUID synthetic option IDs keep existing fallback behavior.
    non_uuid_decision = _decision()
    non_uuid_decision["legal_options"] = [{"option_id": "keep", "label": ""}]
    assert games.frame_of(1, non_uuid_decision, {"selected_option_ids": ["keep"]})["chosen"] == [
        "keep"
    ]


def test_games_carry_the_cohort_the_pages_show_instead_of_guessing(tmp_path: Path) -> None:
    """#1662: ``cohort`` and ``played_seats`` come from the game log header (read_game and
    list_games); an unreadable header and a made-up orphan header are UNKNOWN, never a simulation."""
    folder = games.games_folder(tmp_path)

    def write(game_id: str, header: dict[str, object]) -> None:
        recorder = games.GameRecorder(tmp_path, game_id, header)
        recorder.record(_decision(), {"selected_option_ids": ["o1"]})
        recorder.close({"status": "finished", "winner_seats": [0]})

    write("g-sim", HEADER)
    write("g-human", {**HEADER, "human_seats": [1]})
    write("g-empty-humans", {**HEADER, "human_seats": []})
    # an old log: written before #1662, it still says SIMULATED_RESULT although a human sat there
    old = folder / "g-old.jsonl"
    old.write_text(
        json.dumps(
            {
                "kind": "header",
                "schema": games.LOG_SCHEMA,
                "game_id": "g-old",
                "data_class": "SIMULATED_RESULT",
                "seats": [{"seat": 0, "pilot": "KI"}, {"seat": 2, "pilot": "Mensch"}],
            }
        )
        + "\n"
        + json.dumps({"kind": "result", "status": "finished", "winner_seats": [2]})
        + "\n",
        encoding="utf-8",
    )
    write("g-garbled", {**HEADER, "human_seats": "yes"})
    (folder / "g-lost.out").write_text("Exception: start failed\n", encoding="utf-8")

    expected = {
        "g-sim": ("SIMULATED_RESULT", []),
        "g-human": ("PLAYED_GAME", [1]),
        "g-empty-humans": ("SIMULATED_RESULT", []),
        "g-old": ("PLAYED_GAME", [2]),
        "g-garbled": ("UNKNOWN", []),
        "g-lost": ("UNKNOWN", []),
    }
    listed = {g["game_id"]: g for g in games.list_games(tmp_path)}
    assert set(listed) == set(expected)
    for game_id, (cohort, seats) in expected.items():
        assert (listed[game_id]["cohort"], listed[game_id]["played_seats"]) == (cohort, seats)
        read = games.read_game(tmp_path, game_id)
        assert (read["cohort"], read["played_seats"]) == (cohort, seats), game_id
    # the made-up header of an orphaned .out says the same as the cohort: unknown
    lost = games.read_game(tmp_path, "g-lost")
    assert lost["header"]["data_class"] == "UNKNOWN"  # type: ignore[index]
    assert games.game_cohort(lost["header"]) == "UNKNOWN"
    # the helpers read nothing but the header: a seat row without a seat number names no seat
    assert games.played_seats({"seats": [{"pilot": "Mensch"}]}) == []
    assert games.cohort_fields({"seats": [{"pilot": "Mensch"}]}) == {
        "cohort": "PLAYED_GAME",
        "played_seats": [],
        "table_size": None,  # a seat row without a seat number names no table size (#1661)
    }
    assert games.cohort_fields("no header") == {
        "cohort": "UNKNOWN",
        "played_seats": [],
        "table_size": None,
    }


def test_the_state_routes_carry_the_cohort_of_a_recorded_game(studio_folder: Path) -> None:
    """The Partie page reads the cohort from the same answers it already asks for (#1662)."""
    for game_id, header in (("r-sim", HEADER), ("r-human", {**HEADER, "human_seats": [0]})):
        recorder = games.GameRecorder(studio_folder, game_id, header)
        recorder.record(_decision(), {"selected_option_ids": ["o1"]})
        recorder.close({"status": "finished", "winner_seats": [0]})
    with TestClient(create_app(studio_folder), headers={"X-Studio": "1"}) as client:
        listed = {g["game_id"]: g for g in client.get("/api/games").json()}
        assert listed["r-sim"]["cohort"] == "SIMULATED_RESULT"
        assert (listed["r-human"]["cohort"], listed["r-human"]["played_seats"]) == (
            "PLAYED_GAME",
            [0],
        )
        for game_id, cohort in (("r-sim", "SIMULATED_RESULT"), ("r-human", "PLAYED_GAME")):
            assert client.get(f"/api/games/{game_id}").json()["cohort"] == cohort
            # a finished human game is also served by the interactive route
            assert client.get(f"/api/play/{game_id}").json()["cohort"] == cohort
        played = client.get("/api/play/r-human").json()
        assert played["played_seats"] == [0] and played["human_seats"] == [0]


def test_list_games_forwards_only_allowlisted_unclean_shutdown_summary(tmp_path: Path) -> None:
    """list_games surfaces game_reached_engine_end and shutdown_disposition strictly from the
    audited 3-item allowlist (#1734)."""
    for game_id, closing in (
        ("g-ok", {"status": "finished", "winner_seats": [0]}),
        ("g-fail", {"status": "failed", "failure_class": "RuntimeError"}),
        (
            "g-forced",
            {
                "status": "failed",
                "game_reached_engine_end": True,
                "shutdown_disposition": "forced_kill",
                "result_credited": False,
                "uncredited_winner_seats": [1],
            },
        ),
        (
            "g-bogus",
            {
                "status": "failed",
                "game_reached_engine_end": True,
                "shutdown_disposition": "not_allowed",
            },
        ),
    ):
        recorder = games.GameRecorder(tmp_path, game_id, HEADER)
        recorder.close(closing)

    listed = {g["game_id"]: g for g in games.list_games(tmp_path)}
    assert (listed["g-ok"]["game_reached_engine_end"], listed["g-ok"]["shutdown_disposition"]) == (
        False,
        None,
    )
    assert (
        listed["g-fail"]["game_reached_engine_end"],
        listed["g-fail"]["shutdown_disposition"],
    ) == (False, None)
    assert (
        listed["g-forced"]["game_reached_engine_end"],
        listed["g-forced"]["shutdown_disposition"],
    ) == (True, "forced_kill")
    assert (
        listed["g-bogus"]["game_reached_engine_end"],
        listed["g-bogus"]["shutdown_disposition"],
    ) == (False, None)
