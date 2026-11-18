"""Unit tests for M4 human seat interactive play and hidden-information redaction (#1169)."""

from __future__ import annotations

import itertools
import json
import re
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.engine.rules.failure_privacy import redacted_summary
from commander_lab.engine.rules.full_game import (
    FULL_GAME_DECISION_PROTOCOL_VERSION,
    FULL_GAME_EVIDENCE_CLASS,
    FULL_GAME_LANE,
    FullGameProtocolError,
)
from commander_lab.models import RulesDeckInput
from commander_lab.qualification.current_boundary.bridge_launcher import canonical_xmage_engine_pin
from commander_lab.studio import games, play
from commander_lab.studio.web import STATIC, create_app


def _make_deck(deck_id: str, commander: str) -> RulesDeckInput:
    mainboard = ["Forest"] * 49 + ["Island"] * 50
    return play._with_hash(
        RulesDeckInput(
            deck_id=deck_id,
            name=deck_id,
            deck_hash=None,
            commander_names=(commander,),
            mainboard=tuple(mainboard),
            sideboard=(),
        )
    )


def _pilot_state(
    *, seat: int, turn: int, active_player_id: str, secret_opp_card: str
) -> dict[str, object]:
    return {
        "seat": seat,
        "turn_number": turn,
        "phase": "precombat_main",
        "step": "precombat_main",
        "active_player_id": active_player_id,
        "players": [
            {
                "seat": 0,
                "player_id": "p0",
                "life": 40,
                "hand_count": 2,
                "library_count": 90,
                "hand": [{"name": "Forest"}, {"name": "Llanowar Elves"}],
                "battlefield": [],
                "graveyard": [],
                "command": [{"name": "Chulane, Teller of Tales"}],
                "exile": [],
            },
            {
                "seat": 1,
                "player_id": "p1",
                "life": 40,
                "hand_count": 2,
                "library_count": 90,
                "hand": [{"name": secret_opp_card}, {"name": "Island"}],
                "battlefield": [],
                "graveyard": [],
                "command": [{"name": "Kinnan, Bonder Prodigy"}],
                "exile": [],
            },
        ],
        "stack": [],
    }


class _FakeInteractiveClient:
    """Simulated XMage bridge client driving one interactive human-vs-AI game."""

    SECRET_CARD = "Secret Opponent Force of Will"

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self.created_payload: dict[str, object] | None = None
        self.phase = 0
        self.conceded = False
        self.decision_count = 0
        self.submitted_responses: list[dict[str, object]] = []

    def __enter__(self) -> _FakeInteractiveClient:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def _status(self) -> dict[str, object]:
        if self.conceded:
            return {
                "terminal": True,
                "decision": None,
                "outcomes": [
                    {
                        "seat": 0,
                        "player_id": "p0",
                        "life": 40,
                        "won": False,
                        "lost": True,
                        "left": True,
                        "can_concede": False,
                    },
                    {
                        "seat": 1,
                        "player_id": "p1",
                        "life": 40,
                        "won": True,
                        "lost": False,
                        "left": False,
                        "can_concede": False,
                    },
                ],
            }
        if self.phase == 0:
            return {
                "terminal": False,
                "outcomes": [
                    {"seat": 0, "player_id": "p0", "life": 40, "can_concede": True},
                    {"seat": 1, "player_id": "p1", "life": 40, "can_concede": True},
                ],
                "decision": {
                    "decision_id": "dec-h-1",
                    "decision_offset": 1,
                    "actor_id": "p0",
                    "seat": 0,
                    "acting_for_seat": 0,
                    "decision_class": "priority",
                    "prompt": "Play spells or pass priority",
                    "minimum_selections": 1,
                    "maximum_selections": 1,
                    "legal_options": [
                        {
                            "option_id": "pass-1",
                            "option_type": "pass_priority",
                            "label": "Pass priority",
                        },
                        {"option_id": "land-1", "option_type": "play_land", "label": "Play Forest"},
                    ],
                    "pilot_state": _pilot_state(
                        seat=0, turn=1, active_player_id="p0", secret_opp_card=self.SECRET_CARD
                    ),
                },
            }
        if self.phase == 1:
            return {
                "terminal": False,
                "outcomes": [
                    {"seat": 0, "player_id": "p0", "life": 40, "can_concede": True},
                    {"seat": 1, "player_id": "p1", "life": 40, "can_concede": True},
                ],
                "decision": {
                    "decision_id": "dec-ai-1",
                    "decision_offset": 2,
                    "actor_id": "p1",
                    "seat": 1,
                    "acting_for_seat": 1,
                    "decision_class": "priority",
                    "prompt": "Play spells or pass priority",
                    "minimum_selections": 1,
                    "maximum_selections": 1,
                    "legal_options": [
                        {
                            "option_id": "pass-ai",
                            "option_type": "pass_priority",
                            "label": "Pass priority",
                        },
                    ],
                    "pilot_state": _pilot_state(
                        seat=1, turn=2, active_player_id="p1", secret_opp_card=self.SECRET_CARD
                    ),
                },
            }
        return {
            "terminal": False,
            "outcomes": [
                {"seat": 0, "player_id": "p0", "life": 40, "can_concede": True},
                {"seat": 1, "player_id": "p1", "life": 40, "can_concede": True},
            ],
            "decision": {
                "decision_id": "dec-h-2",
                "decision_offset": 3,
                "actor_id": "p0",
                "seat": 0,
                "acting_for_seat": 0,
                "decision_class": "target",
                "prompt": "Choose up to 1 target",
                "minimum_selections": 0,
                "maximum_selections": 1,
                "legal_options": [
                    {"option_id": "tgt-1", "option_type": "target", "label": "Llanowar Elves"},
                ],
                "pilot_state": _pilot_state(
                    seat=0, turn=2, active_player_id="p1", secret_opp_card=self.SECRET_CARD
                ),
            },
        }

    def request(self, method: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        payload = payload or {}
        if method == "start_engine":
            return {"lane": FULL_GAME_LANE}
        if method == "get_provider_version":
            return {
                "engine": "xmage",
                "engine_commit": canonical_xmage_engine_pin(),
                "engine_version": "test-xmage",
            }
        if method == "get_capabilities":
            return {
                "full_game_lane": {
                    "lane": FULL_GAME_LANE,
                    "decision_protocol_version": FULL_GAME_DECISION_PROTOCOL_VERSION,
                    "min_players": 2,
                    "max_players": 6,
                    "evidence_class": FULL_GAME_EVIDENCE_CLASS,
                    "generic_capability_promotion": False,
                    "one_game_per_process": True,
                    "bit_exact_replay_validated": False,
                },
                "capabilities": {
                    "commander_supported": True,
                    "partner_supported": True,
                    "multiplayer_supported": True,
                    "headless_supported": True,
                    "seed_supported": True,
                    "deck_import_supported": True,
                    "target_selection_supported": True,
                    "mode_selection_supported": True,
                    "trigger_order_supported": True,
                    "mulligan_supported": True,
                },
            }
        if method == "import_deck":
            return {"deck_handle": {"handle_id": "handle-1"}}
        if method == "create_full_game":
            self.created_payload = dict(payload)
            return {
                "evidence_class": FULL_GAME_EVIDENCE_CLASS,
                "holdout_consumed": False,
            }
        if method == "start_full_game":
            return self._status()
        if method == "get_full_game_decision":
            return self._status()
        if method == "get_concede_offer":
            return {"concede_available": not self.conceded}
        if method == "submit_concede":
            self.conceded = True
            return self._status()
        if method == "submit_full_game_decision":
            response = payload.get("response")
            assert isinstance(response, dict)
            selected = response.get("selected_option_ids")
            if self.phase == 0 and selected == ["land-1"]:
                raise FullGameProtocolError("timing forbidden by bridge", code="BRIDGE_ERROR")
            self.submitted_responses.append(dict(response))
            self.decision_count += 1
            self.phase += 1
            return self._status()
        if method == "export_event_log":
            return {"events": [{"turn": 1, "text": "Game started"}]}
        if method == "get_full_game_result":
            return {
                "evidence_class": FULL_GAME_EVIDENCE_CLASS,
                "consumed_gameplay_evidence": False,
                "holdout_consumed": False,
                "official_campaign_eligible": False,
                "rules_authority": "xmage",
                "decision_policy_authority": "commander_lab_external_pilot",
                "bit_exact_replay_validated": False,
                "seed": 42,
                "turn_number": 2,
                "decision_count": self.decision_count,
                "terminal": True,
                "transcript": [],
                "outcomes": [
                    {"seat": 0, "life": 40, "won": False, "lost": True, "left": True},
                    {"seat": 1, "life": 40, "won": True, "lost": False, "left": False},
                ],
            }
        raise AssertionError(f"unexpected bridge method: {method}")


def _wait_for_pending(client: TestClient, game_id: str, decision_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 5.0
    last_snap: dict[str, object] = {}
    while time.monotonic() < deadline:
        last_snap = client.get(f"/api/play/{game_id}").json()
        pending = last_snap.get("pending_decision")
        if isinstance(pending, dict) and pending.get("decision_id") == decision_id:
            return last_snap
        if not last_snap.get("running", True):
            raise AssertionError(f"session stopped unexpectedly: {last_snap.get('result')}")
        time.sleep(0.02)
    raise AssertionError(f"timed out waiting for decision_id={decision_id}; last={last_snap}")


def test_prepare_game_human_seat_and_timeout_validation() -> None:
    decks = (
        _make_deck("own", "Chulane, Teller of Tales"),
        _make_deck("opp", "Kinnan, Bonder Prodigy"),
    )
    default_prep = play.prepare_game(decks, seed=7, game_id="g-ai", jar_sha256="abc123")
    assert "human_seats" not in default_prep.header
    assert default_prep.header["seats"][0]["pilot"] == "KI"  # type: ignore[index]

    human_prep = play.prepare_game(
        decks,
        seed=7,
        game_id="g-human",
        human_seats=[0],
        decision_timeout_seconds=0,
        jar_sha256="abc123",
    )
    assert human_prep.header["human_seats"] == [0]
    assert human_prep.header["decision_timeout_seconds"] == 0
    assert human_prep.header["seats"][0]["pilot"] == "Mensch"  # type: ignore[index]
    assert human_prep.header["seats"][1]["pilot"] == "KI"  # type: ignore[index]

    with pytest.raises(ValueError, match="out of range"):
        play.prepare_game(decks, seed=7, game_id="g-bad-seat", human_seats=[2])
    with pytest.raises(ValueError, match="out of range"):
        play.prepare_game(decks, seed=7, game_id="g-neg-seat", human_seats=[-1])
    with pytest.raises(ValueError, match="decision_timeout_seconds"):
        play.prepare_game(
            decks, seed=7, game_id="g-bad-to", human_seats=[0], decision_timeout_seconds=-1
        )
    with pytest.raises(ValueError, match="decision_timeout_seconds"):
        play.prepare_game(
            decks, seed=7, game_id="g-max-to", human_seats=[0], decision_timeout_seconds=86_401
        )


def test_read_game_redacts_opponent_hands_while_running_for_human_seat(tmp_path: Path) -> None:
    decks = (
        _make_deck("own", "Chulane, Teller of Tales"),
        _make_deck("opp", "Kinnan, Bonder Prodigy"),
    )
    prep = play.prepare_game(
        decks, seed=1, game_id="g-redact", human_seats=[0], decision_timeout_seconds=0
    )
    recorder = games.GameRecorder(tmp_path, "g-redact", prep.header)
    recorder.record(
        {
            "seat": 1,
            "decision_class": "priority",
            "prompt": "Act",
            "legal_options": [{"option_id": "p", "label": "Pass priority"}],
            "pilot_state": _pilot_state(
                seat=1, turn=1, active_player_id="p1", secret_opp_card="Secret Opponent Card"
            ),
        },
        {"selected_option_ids": ["p"]},
    )

    running_view = games.read_game(tmp_path, "g-redact")
    assert running_view["running"] is True
    raw_running = json.dumps(running_view)
    assert "Secret Opponent Card" not in raw_running
    assert running_view["frames"][0]["players"][0]["hand"] == ["Forest", "Llanowar Elves"]
    assert "hand" not in running_view["frames"][0]["players"][1]

    recorder.close(
        {
            "status": "finished",
            "winner_seats": [0],
            "decision_count": 1,
            "engine_version": "test",
        }
    )
    # Owner decision 2026-11-17: running = hidden, finished = revealed.
    finished_view = games.read_game(tmp_path, "g-redact")
    assert finished_view["running"] is False
    assert "Secret Opponent Card" in json.dumps(finished_view)
    assert finished_view["frames"][0]["players"][1]["hand"][0] == "Secret Opponent Card"
    revealed = play.InteractivePlayManager().snapshot(tmp_path, "g-redact")
    assert revealed["hands_revealed"] is True
    assert "Secret Opponent Card" in json.dumps(revealed["frames"])


def test_ai_pick_from_a_hidden_zone_stays_hidden_while_running(tmp_path: Path) -> None:
    decks = (
        _make_deck("own", "Chulane, Teller of Tales"),
        _make_deck("opp", "Kinnan, Bonder Prodigy"),
    )
    prep = play.prepare_game(
        decks, seed=6, game_id="g-hand-pick", human_seats=[0], decision_timeout_seconds=0
    )
    recorder = games.GameRecorder(tmp_path, "g-hand-pick", prep.header)
    state = _pilot_state(seat=1, turn=3, active_player_id="p1", secret_opp_card="Hand Secret")

    def pick(option_id: str, label: str, metadata: dict[str, object] | None) -> None:
        option: dict[str, object] = {"option_id": option_id, "label": label}
        if metadata is not None:
            option["metadata"] = metadata
        recorder.record(
            {
                "seat": 1,
                "decision_class": "choose_object",
                "prompt": "Choose a card",
                "legal_options": [option],
                "pilot_state": state,
            },
            {"selected_option_ids": [option_id]},
        )

    pick("o-hand", "Hand Secret", {"zone": "hand"})
    pick("o-lib", "Tutored Secret", {"zone": "library"})  # a tutor
    pick("o-none", "Unknown Zone Secret", None)  # zone not named: hidden to be safe
    pick("o-gy", "Public Graveyard Card", {"zone": "graveyard"})
    pick("o-bf", "Public Permanent", {"zone": "battlefield"})
    pick("o-ex", "Public Exiled Card", {"zone": "exiled"})  # the engine names the zone "exiled"
    running = games.read_game(tmp_path, "g-hand-pick")
    assert len(running["frames"]) == 6 and running["running"] is True
    blob = json.dumps(running)
    for secret in ("Hand Secret", "Tutored Secret", "Unknown Zone Secret"):
        assert secret not in blob
    hidden = [f["chosen"] for f in running["frames"][:3]]
    assert hidden == [[], [], []]
    assert all(f["private_selection"] for f in running["frames"][:3])
    assert [f["chosen"] for f in running["frames"][3:]] == [
        ["Public Graveyard Card"],
        ["Public Permanent"],
        ["Public Exiled Card"],
    ]
    assert not any("private_selection" in f for f in running["frames"][3:])
    recorder.close({"status": "finished", "winner_seats": [0], "decision_count": 5})
    after = games.read_game(tmp_path, "g-hand-pick")
    assert [f["chosen"][0] for f in after["frames"][:3]] == [
        "Hand Secret",
        "Tutored Secret",
        "Unknown Zone Secret",
    ]


def test_ai_bottom_pick_stays_hidden_while_running_and_shows_after_the_game(
    tmp_path: Path,
) -> None:
    decks = (
        _make_deck("own", "Chulane, Teller of Tales"),
        _make_deck("opp", "Kinnan, Bonder Prodigy"),
    )
    prep = play.prepare_game(
        decks, seed=2, game_id="g-bottom", human_seats=[0], decision_timeout_seconds=0
    )
    recorder = games.GameRecorder(tmp_path, "g-bottom", prep.header)
    recorder.record(
        {
            "seat": 1,
            "decision_class": "choose_object",
            "prompt": "Put a card on the bottom",
            "context": {"bottom_of_library_selection": True},
            "legal_options": [{"option_id": "c1", "label": "Hidden Bottom Card"}],
            "pilot_state": _pilot_state(
                seat=1, turn=0, active_player_id="p1", secret_opp_card="Hidden Bottom Card"
            ),
        },
        {"selected_option_ids": ["c1"]},
    )
    running = games.read_game(tmp_path, "g-bottom")
    assert running["frames"] and running["running"] is True
    assert "Hidden Bottom Card" not in json.dumps(running)
    assert running["frames"][0]["private_selection"] is True
    recorder.close({"status": "finished", "winner_seats": [0], "decision_count": 1})
    after = games.read_game(tmp_path, "g-bottom")
    assert after["frames"][0]["chosen"] == ["Hidden Bottom Card"]


def test_interactive_session_routes_redaction_validation_speed_and_concede(
    tmp_path: Path,
) -> None:
    app = create_app(tmp_path)
    decks = (
        _make_deck("own", "Chulane, Teller of Tales"),
        _make_deck("opp", "Kinnan, Bonder Prodigy"),
    )
    prepared = play.prepare_game(
        decks,
        seed=42,
        game_id="interactive-1",
        human_seats=[0],
        decision_timeout_seconds=0,
        jar_sha256="deadbeef" * 8,
        qualification={"status": "BRIDGE_AHEAD_OF_QUALIFICATION", "covered_by_sealed_epoch": False},
    )
    fake_client = _FakeInteractiveClient()
    session = play.InteractiveGameSession(
        tmp_path,
        prepared,
        human_seats=[0],
        decision_timeout_seconds=0,
        ai_delay_ms=10,
        command=("fake-bridge",),
        client_factory=lambda *_a, **_kw: fake_client,
    )
    with app.state.play_manager._lock:
        app.state.play_manager._sessions["interactive-1"] = session
    session.start()

    client = TestClient(app, headers={"X-Studio": "1"})
    try:
        snap = _wait_for_pending(client, "interactive-1", "dec-h-1")
        assert fake_client.created_payload is not None
        assert fake_client.created_payload["human_seats"] == [0]
        assert fake_client.created_payload["decision_timeout_seconds"] == 0
        assert snap["interactive"] is True
        assert snap["hands_revealed"] is False
        assert snap["can_concede"] is True
        # Hidden information (§5): opponent secret hand cards must not leak in live play or log view.
        assert _FakeInteractiveClient.SECRET_CARD not in json.dumps(snap)
        players = snap["pending_decision"]["pilot_state"]["players"]
        assert players[0]["hand"] == [{"name": "Forest"}, {"name": "Llanowar Elves"}]
        assert "hand" not in players[1]
        assert "hand_cards" not in players[1]

        # Reject stale decision_id and fabricated option_id with 422 without breaking session.
        stale = client.post(
            "/api/play/interactive-1/decision",
            json={"decision_id": "wrong-id", "selected_option_ids": ["pass-1"], "ordering": []},
        )
        assert stale.status_code == 422
        fabricated = client.post(
            "/api/play/interactive-1/decision",
            json={"decision_id": "dec-h-1", "selected_option_ids": ["forged-opt"], "ordering": []},
        )
        assert fabricated.status_code == 422

        # Bridge-level validation failure (BRIDGE_ERROR) surfaces as 422 and keeps waiting.
        bridge_reject = client.post(
            "/api/play/interactive-1/decision",
            json={"decision_id": "dec-h-1", "selected_option_ids": ["land-1"], "ordering": []},
        )
        assert bridge_reject.status_code == 422

        # Legal pass advances past human 1 and AI turn 1 (recording frames), stopping at human 2.
        accepted = client.post(
            "/api/play/interactive-1/decision",
            json={"decision_id": "dec-h-1", "selected_option_ids": ["pass-1"], "ordering": []},
        )
        assert accepted.status_code == 200
        snap2 = _wait_for_pending(client, "interactive-1", "dec-h-2")
        assert _FakeInteractiveClient.SECRET_CARD not in json.dumps(snap2)
        assert snap2["total"] == 2
        games_snap = client.get("/api/games/interactive-1").json()
        assert games_snap["running"] is True
        assert _FakeInteractiveClient.SECRET_CARD not in json.dumps(games_snap)

        # Speed control clamps & updates live session.
        speed_resp = client.post("/api/play/interactive-1/speed", json={"ai_delay_ms": 500})
        assert speed_resp.status_code == 200
        assert speed_resp.json()["ai_delay_ms"] == 500

        # Rule-conformant concede ends the game with seat 1 as winner.
        concede_resp = client.post("/api/play/interactive-1/concede", json={})
        assert concede_resp.status_code == 200
        assert concede_resp.json()["conceded"] is True

        deadline = time.monotonic() + 5.0
        final_snap = client.get("/api/play/interactive-1").json()
        while final_snap["running"] and time.monotonic() < deadline:
            time.sleep(0.02)
            final_snap = client.get("/api/play/interactive-1").json()
        assert final_snap["running"] is False
        assert final_snap["result"]["status"] == "finished"
        assert final_snap["result"]["winner_seats"] == [1]
        # Owner decision 2026-11-17: after the game the AI hands are revealed (play route and
        # game route alike); while it ran they never appeared in any response above.
        assert final_snap["hands_revealed"] is True
        assert final_snap["total"] == 2
        assert _FakeInteractiveClient.SECRET_CARD in json.dumps(final_snap["frames"])
        assert _FakeInteractiveClient.SECRET_CARD in json.dumps(
            client.get("/api/games/interactive-1").json()["frames"]
        )

        # Delete cleans up both manager and recorded files.
        deleted = client.delete("/api/games/interactive-1")
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] is True
        assert client.get("/api/play/interactive-1").status_code == 404
    finally:
        app.state.play_manager.shutdown_all()


def test_partie_ui_covers_human_seat_controls_without_client_rules() -> None:
    html_text = (STATIC / "partie.html").read_text(encoding="utf-8")
    css_text = (STATIC / "partie.css").read_text(encoding="utf-8")
    js_text = (STATIC / "partie.js").read_text(encoding="utf-8")

    for elem_id in (
        "concede-btn",
        "bridge-status",
        "auto-pass-wrap",
        "auto-pass-human",
        "human-decision",
    ):
        assert f'id="{elem_id}"' in html_text
    assert ".legal-target" in css_text
    assert ".human-decision" in css_text

    assert "Sitz 1 selbst spielen (Mensch)" in js_text
    assert "BRIDGE_AHEAD_OF_QUALIFICATION" in js_text
    assert "/api/play/" in js_text
    assert "/decision" in js_text
    assert "/concede" in js_text
    assert "/speed" in js_text
    # P1 #2 / P2 #3 / P3 #9: trigger_order single selection, multi_amount legs vector, live counter & counters
    assert "numeric_legs" in js_text
    assert "numeric_total_min" in js_text
    assert (
        '(dc === "trigger_order" || dc === "order") && !(minSel === 1 && maxSel === 1)' in js_text
    )
    assert "(Live)" in js_text
    assert "rawCounters" in js_text
    # REQ-02/04/06/08/10: no client-side undo / legality reconstruction
    assert "undo" not in js_text.lower()


def test_concede_available_and_failed_concede_stays_on_decision(tmp_path: Path) -> None:
    class _DenyConcedeClient(_FakeInteractiveClient):
        def _status(self) -> dict[str, object]:
            payload = super()._status()
            if self.phase == 0:
                payload["outcomes"] = [{"seat": 0, "player_id": "p0", "life": 40}]
            return payload

        def request(
            self, method: str, payload: dict[str, object] | None = None
        ) -> dict[str, object]:
            if method == "get_concede_offer":
                return {"concede_available": False}
            return super().request(method, payload)

    app = create_app(tmp_path)
    decks = (
        _make_deck("own", "Chulane, Teller of Tales"),
        _make_deck("opp", "Kinnan, Bonder Prodigy"),
    )
    prepared = play.prepare_game(
        decks,
        seed=9,
        game_id="concede-stay",
        human_seats=[0],
        decision_timeout_seconds=0,
        jar_sha256="deadbeef" * 8,
    )
    fake_client = _DenyConcedeClient()
    session = play.InteractiveGameSession(
        tmp_path,
        prepared,
        human_seats=[0],
        decision_timeout_seconds=0,
        ai_delay_ms=10,
        command=("fake-bridge",),
        client_factory=lambda *_a, **_kw: fake_client,
    )
    with app.state.play_manager._lock:
        app.state.play_manager._sessions["concede-stay"] = session
    session.start()
    client = TestClient(app, headers={"X-Studio": "1"})
    try:
        snap = _wait_for_pending(client, "concede-stay", "dec-h-1")
        assert snap["can_concede"] is False
        denied = client.post("/api/play/concede-stay/concede", json={})
        assert denied.status_code == 422
        # Session stays parked on the exact same decision without incrementing decision_count.
        snap_after = _wait_for_pending(client, "concede-stay", "dec-h-1")
        assert snap_after["pending_decision"]["decision_id"] == "dec-h-1"
        assert fake_client.decision_count == 0
    finally:
        app.state.play_manager.shutdown_all()


def test_live_game_not_marked_stale_after_600s(tmp_path: Path) -> None:
    import os

    decks = (
        _make_deck("own", "Chulane, Teller of Tales"),
        _make_deck("opp", "Kinnan, Bonder Prodigy"),
    )
    prep = play.prepare_game(
        decks, seed=3, game_id="long-think", human_seats=[0], decision_timeout_seconds=0
    )
    recorder = games.GameRecorder(tmp_path, "long-think", prep.header)
    stale_time = time.time() - (games.STALE_SECONDS + 300.0)
    os.utime(recorder.path, (stale_time, stale_time))

    try:
        assert games.read_game(tmp_path, "long-think")["running"] is False
        live = games.read_game(tmp_path, "long-think", live_game_ids=frozenset({"long-think"}))
        assert live["running"] is True
        assert live["result"] is None
        listed = games.list_games(tmp_path, live_game_ids=frozenset({"long-think"}))
        assert listed[0]["running"] is True
    finally:
        recorder.discard()


def test_interactive_record_decision_keeps_cumulative_combat(tmp_path: Path) -> None:
    decks = (
        _make_deck("own", "Chulane, Teller of Tales"),
        _make_deck("opp", "Kinnan, Bonder Prodigy"),
    )
    prep = play.prepare_game(
        decks, seed=4, game_id="combat-frame", human_seats=[0], decision_timeout_seconds=0
    )
    session = play.InteractiveGameSession(
        tmp_path,
        prep,
        human_seats=[0],
        decision_timeout_seconds=0,
        command=("fake-bridge",),
    )
    try:
        atk_decision = {
            "seat": 0,
            "decision_class": "declare_attacker",
            "prompt": "Declare attackers",
            "legal_options": [
                {"option_id": "atk-1", "label": "Isamaru, Hound of Konda attacks Full Game Seat 1"}
            ],
            "pilot_state": _pilot_state(
                seat=0, turn=3, active_player_id="p0", secret_opp_card="Hidden"
            )
            | {"phase": "combat", "step": "declare_attackers"},
        }
        session._record_decision(atk_decision, {"selected_option_ids": ["atk-1"]})
        followup = {
            "seat": 1,
            "decision_class": "priority",
            "prompt": "Act",
            "legal_options": [{"option_id": "pass", "label": "Pass priority"}],
            "pilot_state": _pilot_state(
                seat=1, turn=3, active_player_id="p0", secret_opp_card="Hidden"
            )
            | {"phase": "combat", "step": "declare_attackers"},
        }
        session._record_decision(followup, {"selected_option_ids": ["pass"]})
        snap = session.snapshot()
        assert snap["frames"][1]["combat"] == {
            "attacks": [{"attacker": "Isamaru, Hound of Konda", "target": "Full Game Seat 1"}]
        }
        assert "Hidden" not in json.dumps(snap["frames"])
    finally:
        session._recorder.discard()


def test_delete_during_slow_startup_discards_without_orphan_gz(tmp_path: Path) -> None:
    import threading

    started_gate = threading.Event()
    release_gate = threading.Event()

    class _SlowStartupClient(_FakeInteractiveClient):
        def request(
            self, method: str, payload: dict[str, object] | None = None
        ) -> dict[str, object]:
            if method == "start_engine":
                started_gate.set()
                release_gate.wait(timeout=2.0)
            return super().request(method, payload)

    app = create_app(tmp_path)
    decks = (
        _make_deck("own", "Chulane, Teller of Tales"),
        _make_deck("opp", "Kinnan, Bonder Prodigy"),
    )
    prepared = play.prepare_game(
        decks,
        seed=5,
        game_id="slow-delete",
        human_seats=[0],
        decision_timeout_seconds=0,
    )
    session = play.InteractiveGameSession(
        tmp_path,
        prepared,
        human_seats=[0],
        decision_timeout_seconds=0,
        command=("fake-bridge",),
        client_factory=lambda *_a, **_kw: _SlowStartupClient(),
    )
    with app.state.play_manager._lock:
        app.state.play_manager._sessions["slow-delete"] = session
    session._thread.start()
    assert started_gate.wait(timeout=2.0)

    client = TestClient(app, headers={"X-Studio": "1"})
    try:
        deleted = client.delete("/api/games/slow-delete")
        release_gate.set()
        session._thread.join(timeout=2.0)
        assert deleted.status_code == 200
        assert not (games.games_folder(tmp_path) / "slow-delete.jsonl").exists()
        assert not (games.games_folder(tmp_path) / "slow-delete.jsonl.gz").exists()
    finally:
        release_gate.set()
        app.state.play_manager.shutdown_all()


def _start_fake_session(
    tmp_path: Path,
    game_id: str,
    fake_client: _FakeInteractiveClient,
    *,
    ai_delay_ms: int = 10,
) -> tuple[object, TestClient]:
    app = create_app(tmp_path)
    decks = (
        _make_deck("own", "Chulane, Teller of Tales"),
        _make_deck("opp", "Kinnan, Bonder Prodigy"),
    )
    prepared = play.prepare_game(
        decks, seed=11, game_id=game_id, human_seats=[0], decision_timeout_seconds=0
    )
    session = play.InteractiveGameSession(
        tmp_path,
        prepared,
        human_seats=[0],
        decision_timeout_seconds=0,
        ai_delay_ms=ai_delay_ms,
        command=("fake-bridge",),
        client_factory=lambda *_a, **_kw: fake_client,
    )
    with app.state.play_manager._lock:
        app.state.play_manager._sessions[game_id] = session
    session.start()
    return app, TestClient(app, headers={"X-Studio": "1"})


def _wait_finished(client: TestClient, game_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 5.0
    snap = client.get(f"/api/play/{game_id}").json()
    while snap["running"] and time.monotonic() < deadline:
        time.sleep(0.02)
        snap = client.get(f"/api/play/{game_id}").json()
    assert snap["running"] is False
    return snap


def test_no_time_limit_for_a_human_seat_on_every_start_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    decks = (
        _make_deck("own", "Chulane, Teller of Tales"),
        _make_deck("opp", "Kinnan, Bonder Prodigy"),
    )
    # Owner decision 2026-11-17: a human waits without limit. The bridge falls back to 120 s
    # when it gets no value, so every path hands it the explicit 0.
    for bad in (1, 120, 600):
        with pytest.raises(ValueError, match="Zeitlimit"):
            play.prepare_game(
                decks, seed=1, game_id="g", human_seats=[0], decision_timeout_seconds=bad
            )
        with pytest.raises(ValueError, match="Zeitlimit"):
            play.InteractiveGameSession(
                tmp_path,
                play.prepare_game(decks, seed=1, game_id="g"),
                human_seats=[0],
                decision_timeout_seconds=bad,
            )
        with pytest.raises(ValueError, match="Zeitlimit"):
            play.InteractivePlayManager().start_game(
                tmp_path, [], seed=1, human_seats=[0], decision_timeout_seconds=bad
            )
    # An AI-only game keeps its own default; nothing changes for it.
    ai_only = play.prepare_game(decks, seed=1, game_id="g-ai")
    assert "decision_timeout_seconds" not in ai_only.header

    monkeypatch.setattr(play, "load_decks", lambda _paths: decks)
    monkeypatch.setattr(play, "engine_command", lambda _folder: ("fake-bridge",))
    monkeypatch.setattr(play, "bridge_jar_sha256", lambda *_a, **_k: "ab" * 32)
    fake = _FakeInteractiveClient()
    manager = play.InteractivePlayManager()
    started = manager.start_game(
        tmp_path,
        [Path("a.json"), Path("b.json")],
        seed=5,
        human_seats=[0],
        game_id="default-timeout",
        client_factory=lambda *_a, **_kw: fake,
    )
    try:
        assert started["decision_timeout_seconds"] == 0
        deadline = time.monotonic() + 5.0
        while fake.created_payload is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert fake.created_payload is not None
        assert fake.created_payload["decision_timeout_seconds"] == 0
        session = manager.get("default-timeout")
        assert session is not None
        assert session.prepared.header["decision_timeout_seconds"] == 0
    finally:
        manager.shutdown_all()


def test_web_refuses_a_time_limit_for_a_human_seat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from commander_lab.studio import launch

    monkeypatch.setattr(
        launch,
        "prepare_table_deck_paths",
        lambda *_a, **_k: ("g", [Path("a.json"), Path("b.json")]),
    )
    client = TestClient(create_app(tmp_path), headers={"X-Studio": "1"})
    refused = client.post(
        "/api/games",
        json={
            "revision_id": "r",
            "opponent_ids": ["o"],
            "seed": 1,
            "human_seats": [0],
            "decision_timeout_seconds": 120,
        },
    )
    assert refused.status_code == 422
    assert "Zeitlimit" in refused.text


def test_server_refuses_five_and_six_seat_tables_with_a_clear_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AGENTS.md: two to four seats are active; five and six stay locked until a qualification and
    an explicit Owner decision. The Studio start refuses them, with and without a human seat."""
    from commander_lab.studio import launch

    assert (launch.MIN_SEATS, launch.MAX_RELEASED_SEATS) == (2, 4)
    client = TestClient(create_app(tmp_path), headers={"X-Studio": "1"})
    for others in (4, 5):
        for human in (None, [0]):
            body: dict[str, object] = {
                "revision_id": "r",
                "opponent_ids": [f"o{n}" for n in range(others)],
                "seed": 1,
            }
            if human:
                body["human_seats"] = human
            refused = client.post("/api/games", json=body)
            assert refused.status_code == 422, (others, human)
            assert "locked" in refused.text and "Owner decision" in refused.text
            assert f"{others + 1} seats" in refused.text
    # a four-seat table passes the seat rule (it then needs the engine, which this folder lacks)
    monkeypatch.setattr(launch, "engine_command", lambda _folder: None)
    store = launch.StudioStore.open(tmp_path)
    try:
        with pytest.raises(RuntimeError):
            launch.prepare_table_deck_paths(
                store, tmp_path, revision_id="r", opponent_ids=["a", "b", "c"], seed=1
            )
    finally:
        store.close()


# ---- the real engine: a scripted human seat plays a whole game through the PLAY routes ----------

ENGINE_ENV = "COMMANDER_LAB_XMAGE_FULL_GAME_BRIDGE_CMD"
SCRIPTED_TURN_LIMIT = 40  # safety net: after this turn the script concedes, and the test then fails


def _scripted_human_answer(pending: dict[str, object]) -> dict[str, object]:
    """A fixed, deterministic script for a seat that keeps, plays lands and passes.

    It is a test script, not a pilot and not a strength claim. It picks an option by its engine
    type (keep, play-land, pass, hold, cancel); where it must choose among options of one kind, or
    must answer a required choice or a number, it takes the smallest label or the stated minimum.
    That tie-break is deterministic, not "the first option" and not random (no ratchet violation:
    tests/unit/test_first_option_ratchet.py). Every id it sends is one the engine offered, and the
    route refuses any other; it works out no rule itself.
    """
    options = [o for o in pending["legal_options"] if isinstance(o, dict)]  # type: ignore[attr-defined]
    cls = pending["decision_class"]
    minimum = int(pending.get("minimum_selections") or 0)  # type: ignore[call-overload]

    def of_type(*types: str) -> list[dict[str, object]]:
        return sorted(
            (o for o in options if o["option_type"] in types), key=lambda o: str(o["label"])
        )

    body: dict[str, object] = {"decision_id": pending["decision_id"], "selected_option_ids": []}
    chosen: list[dict[str, object]] = []
    if cls == "mulligan":
        chosen = of_type("keep")[:1]
    elif cls == "priority":
        land = [
            o
            for o in of_type("play_land_ability", "activated_ability")
            if (o.get("metadata") or {}).get("ability_type") == "play_land"
        ]  # type: ignore[attr-defined]
        chosen = (land or of_type("pass_priority"))[:1]
    elif cls == "declare_attacker":
        chosen = of_type("hold_attacker")[:1]
    elif cls == "mana_payment":
        chosen = of_type("cancel_mana_payment")[:1]
    elif minimum:
        chosen = sorted(options, key=lambda o: str(o["label"]))[:minimum]
    body["selected_option_ids"] = [o["option_id"] for o in chosen]
    context = pending.get("context") or {}
    if isinstance(context, dict) and context.get("numeric_min") is not None:
        body["numeric_choice"] = int(context["numeric_min"])
    return body


@pytest.mark.external
def test_real_engine_human_seat_plays_a_game_to_its_end_through_the_play_routes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Needs the pinned XMage bridge (Java 21). Without it this test is SKIPPED, which is not a pass.

    AGENTS.md section 10 (paths the reference set does not reach): the human seat, driven only by
    ``/api/play/{id}/decision``, plays a two-seat game against the engine's own AI until the engine
    reports the end.
    """
    from commander_lab.studio import launch

    command = launch.engine_command(tmp_path)
    if command is None:
        pytest.skip(
            f"NOT RUN (not a pass): no rules engine here; set {ENGINE_ENV} to the pinned bridge "
            "command (java -Xmx3g -jar <xmage-engine-bridge.jar> full-game) with Java 21"
        )
    jar = next((Path(a) for prev, a in itertools.pairwise(command) if prev == "-jar"), None)
    if jar is None or not jar.is_file():
        pytest.skip(
            f"NOT RUN (not a pass): the bridge jar named by {ENGINE_ENV or 'the data folder'} is missing"
        )
    precons = {deck_id: path for deck_id, _n, _c, _y, path in launch._precons()}
    decks = [precons["precon/2026/lorehold_spirit"], precons["precon/2024/animated_army"]]
    monkeypatch.setattr(
        launch, "prepare_table_deck_paths", lambda *_a, **_k: ("real-engine-human", decks)
    )
    client = TestClient(create_app(tmp_path), headers={"X-Studio": "1"})
    started = client.post(
        "/api/games",
        json={
            "revision_id": "r",
            "opponent_ids": ["o"],
            "seed": 11,
            "human_seats": [0],
            "ai_delay_ms": 0,
        },
    )
    assert started.status_code == 200, started.text
    game_id = started.json()["game_id"]
    answered: dict[str, int] = {}
    conceded = False
    deadline = time.monotonic() + 900
    state: dict[str, object] = {}
    try:
        while time.monotonic() < deadline:
            state = client.get(f"/api/play/{game_id}?count=0").json()
            pending = state.get("pending_decision")
            if not pending:
                if not state.get("running"):
                    break
                time.sleep(0.2)
                continue
            assert isinstance(pending, dict)
            turn = (pending.get("pilot_state") or {}).get("turn_number", 1)
            if not conceded and isinstance(turn, int) and turn >= SCRIPTED_TURN_LIMIT:
                assert client.post(f"/api/play/{game_id}/concede").status_code == 200
                conceded = True
                continue
            body = _scripted_human_answer(pending)
            cls = str(pending["decision_class"])
            answered[cls] = answered.get(cls, 0) + 1
            reply = client.post(f"/api/play/{game_id}/decision", json=body)
            assert reply.status_code == 200, (cls, body, reply.text)
        else:
            pytest.fail(f"the game did not end within the time box; answered so far: {answered}")
    finally:
        client.app.state.play_manager.shutdown_all()  # type: ignore[attr-defined]
    result = state.get("result") or {}
    assert isinstance(result, dict)
    assert state.get("running") is False and result.get("status") == "finished", result
    # a regular end reported by the engine: the script did not have to concede, and someone won
    assert conceded is False, "the game was cut off by the script's concede at the turn limit"
    assert result.get("winner_seats"), result
    assert answered.get("mulligan", 0) >= 1 and answered.get("priority", 0) >= 10, answered
    # the engine's end is recorded, and the hands of the AI seat open up only now
    assert state.get("hands_revealed") is True
    print("real-engine human game ended:", result, "answered:", answered, "conceded:", conceded)


def test_terminal_bridge_error_ends_the_game_instead_of_waiting_on(tmp_path: Path) -> None:
    class _TimedOutClient(_FakeInteractiveClient):
        """After the bridge's own timeout the next answer is rejected as a STALE_DECISION (no
        pending decision any more); only the status read names DECISION_TIMEOUT."""

        timed_out = False

        def request(
            self, method: str, payload: dict[str, object] | None = None
        ) -> dict[str, object]:
            if method == "submit_full_game_decision":
                self.timed_out = True
                raw = ("external_pilot_decision_rejected", "STALE_DECISION: no pending decision")
                raise FullGameProtocolError(
                    "submit_full_game_decision failed: " + redacted_summary("BRIDGE_ERROR", raw),
                    code="BRIDGE_ERROR",
                    diagnostics=raw,
                )
            if method == "get_full_game_decision" and self.timed_out:
                return {
                    "terminal": False,
                    "decision": None,
                    "failure": {
                        "type": "DecisionException",
                        "message": "DECISION_TIMEOUT: dec-h-1",
                    },
                }
            return super().request(method, payload)

    app, client = _start_fake_session(tmp_path, "timed-out", _TimedOutClient())
    try:
        _wait_for_pending(client, "timed-out", "dec-h-1")
        answered = client.post(
            "/api/play/timed-out/decision",
            json={"decision_id": "dec-h-1", "selected_option_ids": ["pass-1"], "ordering": []},
        )
        assert answered.status_code == 409  # not a retryable 422
        final = _wait_finished(client, "timed-out")
        assert final["result"]["status"] == "failed"  # type: ignore[index]
        assert "DECISION_TIMEOUT" in str(final["result"]["failure_message"])  # type: ignore[index]
        assert final["pending_decision"] is None
    finally:
        app.state.play_manager.shutdown_all()  # type: ignore[attr-defined]


def test_rejected_answer_with_the_same_decision_open_stays_retryable(tmp_path: Path) -> None:
    class _RejectingClient(_FakeInteractiveClient):
        rejections = 0

        def request(
            self, method: str, payload: dict[str, object] | None = None
        ) -> dict[str, object]:
            if method == "submit_full_game_decision" and self.rejections == 0:
                self.rejections += 1
                raw = ("external_pilot_decision_rejected", "ILLEGAL_ACTION: option not offered")
                raise FullGameProtocolError(
                    "submit_full_game_decision failed: " + redacted_summary("BRIDGE_ERROR", raw),
                    code="BRIDGE_ERROR",
                    diagnostics=raw,
                )
            return super().request(method, payload)

    fake = _RejectingClient()
    app, client = _start_fake_session(tmp_path, "retry", fake)
    try:
        _wait_for_pending(client, "retry", "dec-h-1")
        body = {"decision_id": "dec-h-1", "selected_option_ids": ["pass-1"], "ordering": []}
        assert client.post("/api/play/retry/decision", json=body).status_code == 422
        assert client.get("/api/play/retry").json()["running"] is True
        assert client.post("/api/play/retry/decision", json=body).status_code == 200
        _wait_for_pending(client, "retry", "dec-h-2")
    finally:
        app.state.play_manager.shutdown_all()  # type: ignore[attr-defined]


def test_dead_bridge_while_the_human_thinks_fails_the_game(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _Process:
        exited = False

        def poll(self) -> int | None:
            return 1 if self.exited else None

    process = _Process()
    fake = _FakeInteractiveClient()
    fake._process = process  # type: ignore[attr-defined]
    monkeypatch.setattr(play, "_PARK_POLL_SECONDS", 0.02)
    app, client = _start_fake_session(tmp_path, "dead-bridge", fake)
    try:
        _wait_for_pending(client, "dead-bridge", "dec-h-1")
        process.exited = True
        final = _wait_finished(client, "dead-bridge")
        assert final["result"]["status"] == "failed"  # type: ignore[index]
        assert "BRIDGE_EXITED" in str(final["result"]["failure_message"])  # type: ignore[index]
    finally:
        app.state.play_manager.shutdown_all()  # type: ignore[attr-defined]


def test_speed_zero_hurries_the_ai_but_never_answers_the_human(tmp_path: Path) -> None:
    fake = _FakeInteractiveClient()
    app, client = _start_fake_session(tmp_path, "hurry", fake, ai_delay_ms=5_000)
    try:
        _wait_for_pending(client, "hurry", "dec-h-1")
        accepted = client.post(
            "/api/play/hurry/decision",
            json={"decision_id": "dec-h-1", "selected_option_ids": ["pass-1"], "ordering": []},
        )
        assert accepted.status_code == 200
        time.sleep(0.2)
        # the AI is still inside its 5 s pause: only the human's own answer has gone out
        assert [r["decision_id"] for r in fake.submitted_responses] == ["dec-h-1"]
        started = time.monotonic()
        assert client.post("/api/play/hurry/speed", json={"ai_delay_ms": 0}).status_code == 200
        _wait_for_pending(client, "hurry", "dec-h-2")
        assert time.monotonic() - started < 2.0  # the running pause was cut short too
        time.sleep(0.3)
        # the second human decision stays open: nothing answered it, the game still runs
        snap = client.get("/api/play/hurry").json()
        assert snap["running"] is True
        assert snap["pending_decision"]["decision_id"] == "dec-h-2"
        assert [r["decision_id"] for r in fake.submitted_responses] == ["dec-h-1", "dec-ai-1"]
    finally:
        app.state.play_manager.shutdown_all()  # type: ignore[attr-defined]


def _node_json(script: str) -> object:
    import shutil
    import subprocess

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    done = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, check=True, cwd=STATIC
    )
    return json.loads(done.stdout)


_FF_PRELUDE = """
const FF = require('./vorspulen.js');
const pass = {option_id: 'pass-1', option_type: 'pass_priority', label: 'Pass priority'};
const others = [
  {option_id: 'land-1', option_type: 'play_land', label: 'Play Forest'},
  {option_id: 'cast-1', option_type: 'cast_spell', label: 'Cast Counterspell'},
];
const players = [{seat: 0, player_id: 'p0'}, {seat: 1, player_id: 'op-1'}];
function pending(over, state) {
  return Object.assign({decision_id: 'd', actor_id: 'p0', seat: 0, decision_class: 'priority',
    legal_options: [others[0], pass, others[1]],
    pilot_state: Object.assign({players, active_player_id: 'op-1', turn_number: 4, stack: []}, state || {})}, over || {});
}
const ctx = (over) => Object.assign({startTurn: 3, stopOnOpponentStack: true}, over || {});
"""


def test_fast_forward_sends_only_the_engine_pass_option_on_priority() -> None:
    # (a) with many offered options only the pass option is ever chosen
    script = (
        _FF_PRELUDE
        + """
const out = [];
for (const stack of [[], [{name: 'Mine', controller_id: 'p0'}]]) {
  for (const opts of [[pass], [others[0], pass], [others[0], others[1], pass], [pass, others[1]]]) {
    out.push(FF.verdict(pending({legal_options: opts}, {stack}), ctx()));
  }
}
console.log(JSON.stringify(out));
"""
    )
    verdicts = _node_json(script)
    assert isinstance(verdicts, list) and len(verdicts) == 8
    for verdict in verdicts:
        assert verdict == {"action": "pass", "optionId": "pass-1"}
    # without a pass option offered by the engine nothing is sent at all
    none_offered = _node_json(
        _FF_PRELUDE
        + "console.log(JSON.stringify(FF.verdict(pending({legal_options: others}), ctx())));"
    )
    assert isinstance(none_offered, dict) and none_offered["action"] == "stop"


def test_fast_forward_stops_at_every_non_priority_decision() -> None:
    java = (
        Path(__file__).resolve().parents[2]
        / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGameDecisionController.java"
    ).read_text(encoding="utf-8")
    declared = java.split("DECISION_CLASSES = Set.of(", 1)[1].split(");", 1)[0]
    java_classes = re.findall(r'"([a-z_]+)"', declared)
    assert "priority" in java_classes and len(java_classes) >= 17
    # every class the bridge declares, except priority, plus the page's own "order" class
    classes = [name for name in java_classes if name != "priority"] + ["order"]
    for real in (
        "replacement_effect", "pile", "target_amount", "amount", "choice", "mulligan",
        "declare_attacker", "declare_blocker",
    ):  # fmt: skip
        assert real in classes
    script = (
        _FF_PRELUDE
        + f"""
const out = {json.dumps(classes)}.map((cls) =>
  FF.verdict(pending({{decision_class: cls, legal_options: [others[0], pass]}}), ctx()));
console.log(JSON.stringify(out));
"""
    )
    verdicts = _node_json(script)
    assert isinstance(verdicts, list) and len(verdicts) == len(classes)
    for verdict in verdicts:
        assert verdict["action"] == "stop" and "selbst" in verdict["reason"]
        assert "optionId" not in verdict


def test_fast_forward_stops_when_the_own_turn_begins() -> None:
    script = (
        _FF_PRELUDE
        + """
const own = (turn) => pending({}, {active_player_id: 'p0', turn_number: turn});
console.log(JSON.stringify([
  FF.verdict(own(4), ctx()),                       // my next turn: stop
  FF.verdict(own(3), ctx()),                       // the turn it was switched on in: keep passing
  FF.verdict(own(3), ctx({startTurn: null})),      // start turn unknown: stop to be safe
  FF.verdict(pending({}, {active_player_id: null}), ctx()),  // unknown turn owner: stop
  FF.verdict(pending({}, {}), ctx()),              // opponent's turn: pass
]));
"""
    )
    result = _node_json(script)
    assert isinstance(result, list)
    own_next, own_same, unknown_start, unknown_owner, opponent = result
    assert own_next == {"action": "stop", "reason": "dein Zug beginnt"}
    assert own_same["action"] == "pass"
    assert unknown_start["action"] == "stop"
    assert unknown_owner["action"] == "stop"
    assert opponent["action"] == "pass"


def test_fast_forward_stops_on_an_opponent_stack_object_when_enabled() -> None:
    script = (
        _FF_PRELUDE
        + """
const theirs = {name: 'Counterspell', controller_id: 'op-1'};
const mine = {name: 'Sol Ring', controller_id: 'p0'};
console.log(JSON.stringify([
  FF.verdict(pending({}, {stack: [theirs]}), ctx()),
  FF.verdict(pending({}, {stack: [mine, theirs]}), ctx()),
  FF.verdict(pending({}, {stack: [{name: 'No owner'}]}), ctx()),
  FF.verdict(pending({}, {stack: [mine]}), ctx()),
  FF.verdict(pending({}, {stack: [theirs]}), ctx({stopOnOpponentStack: false})),
]));
"""
    )
    result = _node_json(script)
    assert isinstance(result, list)
    with_theirs, mixed, no_owner, only_mine, switched_off = result
    assert with_theirs["action"] == "stop" and "Counterspell" in with_theirs["reason"]
    assert mixed["action"] == "stop"
    assert no_owner["action"] == "stop"  # an object of unknown owner counts as not mine
    assert only_mine == {"action": "pass", "optionId": "pass-1"}
    assert switched_off == {"action": "pass", "optionId": "pass-1"}


def test_fast_forward_page_code_answers_nothing_but_the_verdict_pass() -> None:
    js_text = (STATIC / "partie.js").read_text(encoding="utf-8")
    html_text = (STATIC / "partie.html").read_text(encoding="utf-8")
    for elem_id in ("ff-btn", "ff-stack", "ff-rule", "ff-status"):
        assert f'id="{elem_id}"' in html_text
    assert 'src="vorspulen.js"' in html_text
    assert "selected_option_ids: [verdict.optionId]" in js_text
    # the fast-forward switch itself never submits; only the verdict path above does
    for name in ("startFastForward", "endFastForward", "setAiDelay"):
        body = js_text.split(f"function {name}(", 1)[1].split("\nfunction ", 1)[0]
        assert "submitHumanChoice(" not in body, name
    vorspulen = (STATIC / "vorspulen.js").read_text(encoding="utf-8")
    assert 'pending.decision_class !== "priority"' in vorspulen
    assert "innerHTML" not in vorspulen and "style=" not in vorspulen


# ---- board clicks (static/boardclick.js): mapping engine options to cards and player fields -----

BOARDCLICK_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "boardclick_payloads.json"
_BC_PRELUDE = f"""
const BC = require('./boardclick.js');
const FX = JSON.parse(require('fs').readFileSync({json.dumps(BOARDCLICK_FIXTURES.as_posix())}, 'utf8'));
const offered = (p) => p.legal_options.map((o) => String(o.option_id));
const view = (name) => {{ const p = FX[name].pending_decision; return {{p, m: BC.build(p)}}; }};
const optionOfCard = (p, id) => p.legal_options.filter((o) => (o.metadata || {{}}).source_object_id === id);
"""


def test_boardclick_fixtures_are_real_engine_payloads_without_hidden_cards() -> None:
    fixtures = json.loads(BOARDCLICK_FIXTURES.read_text(encoding="utf-8"))
    assert len(fixtures) >= 8
    for name, entry in fixtures.items():
        pending = entry["pending_decision"]
        assert entry["note"].startswith("Real engine payload"), name
        actor = pending["actor_id"]
        players = pending["pilot_state"]["players"]
        assert players, name
        for player in players:
            # only the human's own hand is in a payload; an AI hand never is
            assert ("hand" in player) <= (player["player_id"] == actor), name
        assert set(pending) >= {"decision_id", "legal_options", "pilot_state"}, name


def test_boardclick_maps_real_payloads_to_the_offered_options_only() -> None:
    out = _node_json(
        _BC_PRELUDE
        + """
const out = {};
for (const name of Object.keys(FX)) {
  const {p, m} = view(name);
  const ok = new Set(offered(p));
  const emitted = BC.emittable(m);
  out[name] = {kind: m.kind, mode: m.mode, offeredOnly: emitted.every((id) => ok.has(id)),
    emitted: emitted.length, objects: Object.keys(m.objects).length, seats: Object.keys(m.seats).length,
    listOnly: m.listOnly.length, loose: m.loose.length, options: p.legal_options.length,
    accounted: offered(p).every((id) => emitted.includes(id) || m.listOnly.includes(id))};
}
console.log(JSON.stringify(out));
"""
    )
    assert isinstance(out, dict) and len(out) >= 8
    for name, row in out.items():
        assert row["offeredOnly"] is True, name
        # every offered option is somewhere: on a card or player, a loose button, or the list only
        if row["kind"] != "none":
            assert row["accounted"] is True, name
    # a mulligan has nothing on the board: nothing is clickable
    mulligan = out["mulligan"]
    assert (mulligan["kind"], mulligan["objects"], mulligan["seats"], mulligan["emitted"]) == (
        "none",
        0,
        0,
        0,
    )
    # a scry choice offers one card of the library: not on the board, so only the list answers it
    scry = out["target_library_scry"]
    assert (scry["kind"], scry["objects"], scry["emitted"], scry["listOnly"]) == ("target", 0, 0, 1)
    assert out["priority_lands_spells"]["kind"] == "priority"
    assert out["priority_lands_spells"]["loose"] == 1  # the pass option


def test_boardclick_priority_click_sends_the_engine_option_of_that_card() -> None:
    out = _node_json(
        _BC_PRELUDE
        + """
const {p, m} = view('priority_lands_spells');
const res = [];
for (const id of Object.keys(m.objects)) {
  const own = optionOfCard(p, id).map((o) => String(o.option_id));
  const r = BC.resolve(p, m, {type: 'object', id});
  res.push({id, own, action: r.action, optionId: r.optionId || null, menu: (r.options || []).map((o) => o.optionId)});
}
const pass = p.legal_options.find((o) => o.option_type === 'pass_priority');
console.log(JSON.stringify({res, loose: m.loose, pass: String(pass.option_id), mode: m.mode}));
"""
    )
    assert isinstance(out, dict) and out["mode"] == "immediate"
    assert len(out["res"]) >= 3
    for row in out["res"]:
        assert len(row["own"]) == 1 and row["action"] == "send"
        assert row["optionId"] == row["own"][0]  # exactly the engine's option_id of that card
    assert out["loose"] == [out["pass"]]  # passing stays a button, never a card


def test_boardclick_one_card_with_two_abilities_opens_a_menu_not_a_guess() -> None:
    out = _node_json(
        _BC_PRELUDE
        + """
const {p, m} = view('priority_temple_two_abilities');
const multi = Object.keys(m.objects).filter((id) => optionOfCard(p, id).length > 1);
const r = BC.resolve(p, m, {type: 'object', id: multi[0]});
console.log(JSON.stringify({multi: multi.length, action: r.action, sent: r.optionId || null,
  menu: (r.options || []).map((o) => o.optionId), own: optionOfCard(p, multi[0]).map((o) => String(o.option_id)),
  labels: (r.options || []).map((o) => o.label)}));
"""
    )
    assert isinstance(out, dict) and out["multi"] == 1
    assert out["action"] == "menu" and out["sent"] is None
    assert out["menu"] == out["own"] and len(out["menu"]) == 2
    assert all("Temple" in label for label in out["labels"])  # the engine's own wording


def test_boardclick_mana_payment_and_discard_use_the_cards_the_engine_named() -> None:
    out = _node_json(
        _BC_PRELUDE
        + """
const pay = view('mana_payment');
const disc = view('discard_from_hand');
const sends = (v) => Object.keys(v.m.objects).map((id) => [id, BC.resolve(v.p, v.m, {type: 'object', id})]);
console.log(JSON.stringify({
  pay: {kind: pay.m.kind, loose: pay.m.loose.length, rows: sends(pay).map(([id, r]) => [r.action, optionOfCard(pay.p, id).map((o) => String(o.option_id)), r.optionId || null])},
  disc: {kind: disc.m.kind, mode: disc.m.mode, rows: sends(disc).map(([id, r]) => [r.action, id === r.optionId, disc.m.objects[id].zone])},
}));
"""
    )
    assert isinstance(out, dict)
    assert (
        out["pay"]["kind"] == "mana_payment" and out["pay"]["loose"] >= 1
    )  # cancel stays a button
    assert len(out["pay"]["rows"]) >= 1
    for action, own, sent in out["pay"]["rows"]:
        assert action == "send" and own == [sent]
    assert out["disc"]["kind"] == "target" and out["disc"]["mode"] == "immediate"
    assert len(out["disc"]["rows"]) == 8
    for action, equal, zone in out["disc"]["rows"]:
        assert (action, equal, zone) == ("send", True, "hand")  # the card's id is its option id


def test_boardclick_never_answers_with_an_option_that_was_not_offered() -> None:
    out = _node_json(
        _BC_PRELUDE
        + """
const probes = [{type: 'object', id: 'no-such-object'}, {type: 'object', id: '__proto__'}, {type: 'object', id: 'constructor'},
  {type: 'seat', seat: 9}, {type: 'seat', seat: 'x'}, {type: 'other'}, null, {type: 'object'}];
const rows = [];
for (const name of Object.keys(FX)) {
  const {p, m} = view(name);
  const ok = new Set(offered(p));
  const targets = probes.map((t) => ({t, probe: true}));
  for (const id of Object.keys(m.objects)) targets.push({t: {type: 'object', id}, probe: false});
  for (const seat of Object.keys(m.seats)) targets.push({t: {type: 'seat', seat: Number(seat)}, probe: false});
  for (const {t, probe} of targets) {
    const r = BC.resolve(p, m, t);
    const ids = r.action === 'menu' ? r.options.map((o) => o.optionId) : (r.optionId ? [r.optionId] : []);
    rows.push({name, probe, action: r.action, fine: ids.every((id) => ok.has(id))});
  }
  // the model of another decision: even when every option id is offered again, no click answers
  const later = Object.assign({}, p, {decision_id: 'a-later-decision'});
  for (const id of Object.keys(m.objects)) rows.push({name: name + '/other-decision', action: BC.resolve(later, m, {type: 'object', id}).action, fine: true});
  for (const seat of Object.keys(m.seats)) rows.push({name: name + '/other-decision', action: BC.resolve(later, m, {type: 'seat', seat: Number(seat)}).action, fine: true});
  // a stale model: the engine has since withdrawn every option, so no click may answer
  const stale = Object.assign({}, p, {legal_options: []});
  for (const id of Object.keys(m.objects)) rows.push({name: name + '/stale', probe: false, action: BC.resolve(stale, m, {type: 'object', id}).action, fine: true});
}
console.log(JSON.stringify(rows));
"""
    )
    assert isinstance(out, list) and len(out) > 60
    assert all(row["fine"] for row in out)
    stale = [row for row in out if row["name"].endswith("/stale")]
    assert len(stale) >= 8 and {row["action"] for row in stale} == {"none"}
    other = [row for row in out if row["name"].endswith("/other-decision")]
    assert len(other) >= 20 and {row["action"] for row in other} == {"none"}
    # the junk probes (unknown ids, "__proto__", bad seats, null) never produce an action
    probes = [row for row in out if row.get("probe") is True]
    assert len(probes) >= 8 * 8 and {row["action"] for row in probes} == {"none"}


def test_boardclick_decisions_with_numbers_or_choices_have_no_board_mapping() -> None:
    out = _node_json(
        _BC_PRELUDE
        + """
const base = FX.discard_from_hand.pending_decision;
const withNumbers = Object.assign({}, base, {context: Object.assign({}, base.context, {numeric_max: 3})});
const asModes = Object.assign({}, base, {decision_class: 'mode'});
console.log(JSON.stringify([BC.build(withNumbers).kind, BC.build(asModes).kind, BC.build(null).kind, BC.build({}).kind,
  BC.build(Object.assign({}, base, {legal_options: []})).kind]));
"""
    )
    assert out == ["none", "none", "none", "none", "none"]


def test_boardclick_attack_click_names_the_opponent_the_engine_labelled() -> None:
    out = _node_json(
        _BC_PRELUDE
        + """
const {p, m} = view('declare_attacker');
const hold = p.legal_options.find((o) => o.option_type === 'hold_attacker');
const asked = Object.keys(m.objects)[0];
// the oracle reads the engine's own label "... attacks Full Game Seat N" and takes seat index N-1. That rule is
// the same one boardclick.js uses, so this is a consistency check, not an independent proof: the rule itself
// is derived from the Java creation order (checked against the source text below), not from engine output.
const expected = (seat) => p.legal_options.filter((o) => o.option_type === 'declare_attacker'
  && o.label.endsWith('Full Game Seat ' + (seat + 1))).map((o) => String(o.option_id));
const seatRows = Object.keys(m.seats).map((s) => {
  const r = BC.resolve(p, m, {type: 'seat', seat: Number(s)});
  return {seat: Number(s), action: r.action, sent: r.optionId || null, want: expected(Number(s))};
});
// the same oracle against a model whose seats were swapped: it must notice
const swapped = JSON.parse(JSON.stringify(m));
const [a, b] = ['1', '2'];
[swapped.seats[a].optionIds, swapped.seats[b].optionIds] = [m.seats[b].optionIds, m.seats[a].optionIds];
const wrong = Object.keys(swapped.seats).filter((s) => {
  const r = BC.resolve(p, swapped, {type: 'seat', seat: Number(s)});
  return JSON.stringify([r.optionId]) !== JSON.stringify(expected(Number(s)));
});
const own = BC.resolve(p, m, {type: 'seat', seat: 0});
const creature = BC.resolve(p, m, {type: 'object', id: asked});
console.log(JSON.stringify({kind: m.kind, mode: m.mode, seats: seatRows, wrong, own: own.action,
  hold: String(hold.option_id), loose: m.loose, creature: creature.action,
  menu: (creature.options || []).map((o) => o.optionId), all: offered(p)}));
"""
    )
    assert isinstance(out, dict) and (out["kind"], out["mode"]) == ("attacker", "immediate")
    assert [row["seat"] for row in out["seats"]] == [1, 2, 3]  # never the human's own seat
    for row in out["seats"]:
        assert row["action"] == "send" and len(row["want"]) == 1
        assert row["sent"] == row["want"][0]  # the click names the opponent the engine labelled
    assert out["wrong"] == ["1", "2"]  # a wrong seat mapping is caught by the same check
    java = (
        Path(__file__).resolve().parents[2]
        / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGameSession.java"
    ).read_text(encoding="utf-8")
    assert '"Full Game Seat " + (index + 1)' in java  # seat index = N - 1 (creation order)
    assert out["own"] == "none"
    assert out["loose"] == [out["hold"]]  # "do not attack" stays a button
    assert out["creature"] == "menu" and sorted(out["menu"]) == sorted(out["all"])


def test_boardclick_target_on_the_battlefield_sends_the_object_id_of_that_card() -> None:
    out = _node_json(
        _BC_PRELUDE
        + """
const {p, m} = view('target_battlefield_land');
const ids = Object.keys(m.objects);
const r = BC.resolve(p, m, {type: 'object', id: ids[0]});
// a click on a battlefield card the engine did not offer finds no entry at all
const other = FX.declare_attacker.pending_decision.pilot_state.players[1].battlefield[0].object_id;
const miss = BC.resolve(p, m, {type: 'object', id: other});
const sole = p.legal_options[0];
// mutation probe: an option whose id is not the object's id must never become a click on that card
const later = BC.resolve(Object.assign({}, p, {decision_id: 'a-later-decision'}), m, {type: 'object', id: ids[0]}).action;
const bent = JSON.parse(JSON.stringify(p));
bent.legal_options[0].option_id = 'not-the-object-id';
const bm = BC.build(bent);
console.log(JSON.stringify({kind: m.kind, mode: m.mode, ids, r, miss: miss.action, option: String(sole.option_id),
  object: sole.metadata.object_id, zone: m.objects[ids[0]].zone, later,
  bent: {objects: Object.keys(bm.objects).length, listOnly: bm.listOnly, click: BC.resolve(bent, bm, {type: 'object', id: ids[0]}).action}}));
"""
    )
    assert isinstance(out, dict) and (out["kind"], out["mode"], out["zone"]) == (
        "target",
        "immediate",
        "battlefield",
    )
    assert out["ids"] == [out["object"]] and out["r"] == {
        "action": "send",
        "optionId": out["option"],
    }
    assert out["option"] == out["object"] and out["miss"] == "none"
    # the model belongs to its decision: a later decision offering the same id gets no answer from it
    assert out["later"] == "none" and out["r"]["action"] == "send"
    # an option id that is not its object's id stays in the list: no click sends it
    assert out["bent"] == {"objects": 0, "listOnly": ["not-the-object-id"], "click": "none"}


def test_boardclick_blocker_click_toggles_the_attacker_the_engine_offered() -> None:
    out = _node_json(
        _BC_PRELUDE
        + """
const {p, m} = view('blocker_one_attacker');
const rows = Object.entries(m.objects).map(([id, e]) => [e.role, BC.resolve(p, m, {type: 'object', id})]);
console.log(JSON.stringify({kind: m.kind, mode: m.mode, asked: m.asked, rows, loose: m.loose,
  attacker: String(p.legal_options[0].option_id), min: p.minimum_selections, max: p.maximum_selections}));
"""
    )
    assert isinstance(out, dict) and (out["kind"], out["mode"]) == ("blocker", "staged")
    assert (out["min"], out["max"]) == (
        0,
        1,
    )  # not blocking is allowed: the page confirms an empty choice
    roles = {role: result for role, result in out["rows"]}
    assert roles["block-target"] == {"action": "toggle", "optionId": out["attacker"]}
    assert roles["asked"] == {"action": "none"}  # the blocker itself only shows who blocks
