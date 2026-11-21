"""Unit tests for M4 human seat interactive play and hidden-information redaction (#1169)."""

from __future__ import annotations

import collections
import copy
import gzip
import itertools
import json
import re
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.engine.rules.failure_privacy import (
    public_full_game_exception_message,
    redacted_summary,
)
from commander_lab.engine.rules.full_game import (
    FULL_GAME_DECISION_PROTOCOL_VERSION,
    FULL_GAME_EVIDENCE_CLASS,
    FULL_GAME_LANE,
    FullGameConformanceError,
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


def _actor_view(status: dict[str, object]) -> dict[str, object]:
    """A fake status shaped like the bridge's actor view, so the match's audit passes.

    The actor row of the decision's state is marked ``is_actor``. In the human seat's (seat 0)
    frames the AI row keeps its hand, flagged ``private_state_visible`` (an engine-visible hand,
    e.g. a reveal effect): the Studio must still hide it until the game ends (Owner decision
    2026-11-17). In an AI seat's frames the other rows carry no private keys (actor-scoped)."""
    decision = status.get("decision")
    state = decision.get("pilot_state") if isinstance(decision, dict) else None
    if not isinstance(decision, dict) or not isinstance(state, dict):
        return status
    actor_seat = decision.get("seat")
    players = state.get("players")
    assert isinstance(players, list)
    for row in players:
        assert isinstance(row, dict)
        row["is_actor"] = row.get("seat") == actor_seat
        if row["is_actor"]:
            continue
        if actor_seat == 0:
            row["private_state_visible"] = True
        else:
            for key in ("hand", "hand_cards", "mana_pool", "land_plays_remaining"):
                row.pop(key, None)
    return status


class _BridgeLifecycle:
    """What a ``FullGameBridgeSession`` asks of its client besides ``request`` (fakes)."""

    shutdown_disposition: str | None = None
    transport_failure: str | None = None
    exited = False
    killed = False
    starts = 0
    closes = 0

    def start(self) -> None:
        self.starts += 1

    def close(self) -> str:
        self.closes += 1
        return "graceful_shutdown"

    def process_exited(self) -> bool:
        return self.exited

    def kill(self) -> None:
        self.killed = True


class _FakeInteractiveClient(_BridgeLifecycle):
    """Simulated XMage bridge client driving one interactive human-vs-AI game."""

    SECRET_CARD = "Secret Opponent Force of Will"

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self.created_payload: dict[str, object] | None = None
        self.phase = 0
        self.conceded = False
        self.decision_count = 0
        self.submitted_responses: list[dict[str, object]] = []
        self.requests: list[str] = []

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
        self.requests.append(method)
        return _actor_view(self._answer(method, payload or {}))

    def _answer(self, method: str, payload: dict[str, object]) -> dict[str, object]:
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
                "player_count": len(payload["deck_handles"]),  # type: ignore[arg-type]
                "seed": payload["seed"],
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
            return _event_page([{"turn": 1, "text": "Game started"}], payload)
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


def _event_page(events: list[dict[str, object]], payload: dict[str, object]) -> dict[str, object]:
    """``export_event_log`` as the bridge answers it: the events after ``after_offset``."""
    offset = int(payload.get("after_offset", 0))  # type: ignore[call-overload]
    return {"events": events[offset:], "latest_offset": len(events)}


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
    # #1662: the writer's human label is the one the cohort reader recognises, so a header
    # written without ``human_seats`` is still a PLAYED_GAME by its seat pilot
    from commander_lab.studio.games import HUMAN_PILOT_LABEL, game_cohort

    assert human_prep.header["seats"][0]["pilot"] == HUMAN_PILOT_LABEL  # type: ignore[index]
    assert game_cohort(human_prep.header) == "PLAYED_GAME"
    without = {k: v for k, v in human_prep.header.items() if k != "human_seats"}
    assert game_cohort(without) == "PLAYED_GAME"
    assert game_cohort(default_prep.header) == "SIMULATED_RESULT"

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
        def __init__(self) -> None:
            super().__init__()
            self.methods: list[str] = []

        def request(
            self, method: str, payload: dict[str, object] | None = None
        ) -> dict[str, object]:
            self.methods.append(method)
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
        client_factory=lambda *_a, **_kw: slow,
    )
    slow = _SlowStartupClient()
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
        # the stop is seen between the deck imports: no deck is imported, no game is created
        assert "import_deck" not in slow.methods and "create_full_game" not in slow.methods
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


def test_snapshot_names_the_forced_ai_passes_the_engine_answered_or_unknown(
    tmp_path: Path,
) -> None:
    """#1591: with the pass skipping on, the AI passes the engine answers never reach Python as
    frames. The live snapshot carries the engine's own count; before the engine has reported one
    it is unknown (None), never 0."""
    decks = (
        _make_deck("own", "Chulane, Teller of Tales"),
        _make_deck("opp", "Kinnan, Bonder Prodigy"),
    )
    prepared = play.prepare_game(
        decks, seed=1, game_id="g-live", human_seats=[0], decision_timeout_seconds=0
    )
    session = play.InteractiveGameSession(
        tmp_path, prepared, human_seats=[0], decision_timeout_seconds=0
    )
    assert session.snapshot()["forced_passes_answered_by_engine"] is None
    session._publish_status({"terminal": False, "decision": None}, object())
    assert session.snapshot()["forced_passes_answered_by_engine"] is None
    for bad in ("7", 7.0, True, -1, None):
        session._publish_status({"forced_decisions_skipped": bad}, object())
        assert session.snapshot()["forced_passes_answered_by_engine"] is None
    session._publish_status({"forced_decisions_skipped": 7}, object())
    assert session.snapshot()["forced_passes_answered_by_engine"] == 7
    session._publish_status({"terminal": False, "decision": None}, object())
    assert session.snapshot()["forced_passes_answered_by_engine"] == 7


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
    # #1591: interactive games start the bridge with the pass skipping on, so the engine answered
    # the forced AI passes itself; the closing entry counts them (a run without the switch says 0)
    skipped = result.get("forced_decisions_skipped")
    assert isinstance(skipped, int) and skipped > 0, result
    assert state.get("forced_passes_answered_by_engine") == skipped
    print(
        "real-engine human game ended:",
        result,
        "answered:",
        answered,
        "forced AI passes answered by the engine:",
        skipped,
        "conceded:",
        conceded,
    )


class _ActiveScript:
    """A deterministic test script for a human seat that really plays: it takes two mulligans
    (to reach the London bottom choice; the first one is free with four seats), plays a land, casts the cheapest spell it can pay for once
    per turn, pays with the sources the engine offers, attacks on even turns and holds on odd ones,
    blocks when asked, and otherwise answers with the smallest label or the stated minimum.

    Not a pilot and not a strength claim; no first-option and no random choice. Every id it sends
    was offered by the engine for that very decision, and the route refuses any other.
    """

    def __init__(self, mulligans: int = 2, illegal_amount_once: bool = False) -> None:
        self.illegal_amount_once = illegal_amount_once  # first damage split deliberately off by one
        self.sent_illegal = False
        self.mulligans = 0
        self.take = mulligans
        self.pay_streak = 0
        self.last_cast = ""
        self.tried: set[tuple[str, int]] = set()

    @staticmethod
    def _label(option: dict[str, object]) -> str:
        return str(option["label"])

    @staticmethod
    def _meta(option: dict[str, object]) -> dict[str, object]:
        meta = option.get("metadata")
        return meta if isinstance(meta, dict) else {}

    def _cost(self, option: dict[str, object]) -> int:
        return sum(
            v
            for k, v in self._meta(option).items()
            if k.startswith("mana_cost") and isinstance(v, int)
        )

    def answer(self, pending: dict[str, object]) -> dict[str, object]:
        options = [o for o in pending["legal_options"] if isinstance(o, dict)]  # type: ignore[attr-defined]
        cls = str(pending["decision_class"])
        minimum = int(pending.get("minimum_selections") or 0)  # type: ignore[call-overload]
        maximum = int(pending.get("maximum_selections") or 0)  # type: ignore[call-overload]
        context = pending.get("context")
        context = context if isinstance(context, dict) else {}
        state = pending.get("pilot_state")
        state = state if isinstance(state, dict) else {}
        turn = int(state.get("turn_number") or 1)
        by_label = sorted(options, key=self._label)
        chosen: list[dict[str, object]] = []
        body: dict[str, object] = {"decision_id": pending["decision_id"], "selected_option_ids": []}
        if cls != "mana_payment":
            self.pay_streak = 0
        if cls == "mulligan":
            if self.mulligans < self.take:
                self.mulligans += 1
                chosen = [o for o in by_label if o["option_type"] == "mulligan"]
            else:
                chosen = [o for o in by_label if o["option_type"] == "keep"]
        elif cls == "priority":
            sources = {
                self._meta(o).get("source_object_id")
                for o in options
                if o["option_type"] == "mana_ability"
            }
            lands = [o for o in by_label if self._meta(o).get("ability_type") == "play_land"]
            spells = sorted(
                (
                    o
                    for o in options
                    if self._meta(o).get("ability_type") == "spell"
                    and self._cost(o) <= len(sources)
                    and (str(self._meta(o).get("source_name")), turn) not in self.tried
                ),
                key=lambda o: (self._cost(o), self._label(o)),
            )
            own_main = state.get("phase") in ("precombat_main", "postcombat_main") and state.get(
                "active_player_id"
            ) == pending.get("actor_id")
            if lands:
                chosen = lands
            elif spells and own_main:
                self.last_cast = str(self._meta(spells[0]).get("source_name"))
                self.tried.add((self.last_cast, turn))
                chosen = spells
            else:
                chosen = [o for o in by_label if o["option_type"] == "pass_priority"]
        elif cls == "mana_payment":
            self.pay_streak += 1
            needed = set(re.findall(r"\{([WUBRG])\}", str(context.get("unpaid_mana", ""))))

            def produces(option: dict[str, object]) -> str | None:
                found = re.search(r"Add \{([WUBRGC])\}", self._label(option))
                return found.group(1) if found else None

            pool = [
                o
                for o in by_label
                if o["option_type"] == "mana_pool" and self._meta(o).get("advances_payment")
            ]
            mana = [o for o in by_label if o["option_type"] == "mana_ability"]
            cancel = [o for o in by_label if o["option_type"] == "cancel_mana_payment"]
            fitting = [o for o in mana if produces(o) in needed] or [
                o for o in mana if produces(o) == "C"
            ]
            chosen = (
                cancel if self.pay_streak > 8 and cancel else (pool or fitting or mana or cancel)
            )
        elif cls == "declare_attacker":
            attacks = [o for o in by_label if o["option_type"] == "declare_attacker"]
            holds = [o for o in by_label if o["option_type"] == "hold_attacker"]
            chosen = attacks[-1:] if turn % 2 == 0 and attacks else (holds or attacks)
        elif cls == "declare_blocker":
            chosen = by_label if maximum else []
        elif cls == "multi_amount":
            legs = [leg for leg in context.get("numeric_legs", []) if isinstance(leg, dict)]
            total = context.get("numeric_total_max")
            values = [int(leg["min"]) for leg in legs]
            room = (
                int(total) if total is not None else sum(int(leg["max"]) for leg in legs)
            ) - sum(values)
            for at, leg in enumerate(legs):
                step = min(room, int(leg["max"]) - values[at])
                values[at] += step
                room -= step
            if self.illegal_amount_once and not self.sent_illegal:
                self.sent_illegal = True
                values[0] += 1
            body["numeric_choices"] = values
        elif cls in ("announce_x", "amount") or context.get("numeric_min") is not None:
            body["numeric_choice"] = int(context.get("numeric_min") or 0)
        else:
            chosen = by_label
        if cls in ("declare_blocker",):
            chosen = chosen[:1]
        elif cls not in ("multi_amount", "announce_x", "amount"):
            chosen = chosen[: max(minimum, 1 if maximum else 0, 1 if cls == "priority" else 0)]
        body["selected_option_ids"] = [o["option_id"] for o in chosen]
        return body


# Decks and seeds of the scripted real-engine games (all precon decks of the repository).
_OPPONENTS = (
    "precon/2026/lorehold_spirit",
    "precon/2024/animated_army",
    "precon/2022/token_triumph",
)
_ACTIVE_GAMES = {  # name: (seed, human deck, mulligans the script takes, first split illegal)
    "open_hostility": (21, "precon/2016/open_hostility", 2, False),
    "open_hostility_one_mulligan": (21, "precon/2016/open_hostility", 1, True),
    "power_hungry": (22, "precon/2013/power_hungry", 2, False),
    "draconic_domination": (23, "precon/2017/draconic_domination", 2, False),
}


def _engine_or_skip(tmp_path: Path) -> None:
    from commander_lab.studio import launch

    command = launch.engine_command(tmp_path)
    if command is None:
        pytest.skip(
            f"NOT RUN (not a pass): no rules engine here; set {ENGINE_ENV} to the pinned bridge "
            "command (java -Xmx3g -jar <xmage-engine-bridge.jar> full-game) with Java 21"
        )
    jar = next((Path(a) for prev, a in itertools.pairwise(command) if prev == "-jar"), None)
    if jar is None or not jar.is_file():
        pytest.skip(f"NOT RUN (not a pass): the bridge jar named by {ENGINE_ENV} is missing")


def _play_scripted_game(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    seed: int,
    human_deck: str,
    turn_limit: int,
    mulligans: int,
    illegal_amount_once: bool,
) -> dict[str, object]:
    from commander_lab.studio import launch

    precons = {deck_id: path for deck_id, _n, _c, _y, path in launch._precons()}
    decks = [precons[human_deck], *(precons[o] for o in _OPPONENTS)]
    monkeypatch.setattr(
        launch, "prepare_table_deck_paths", lambda *_a, **_k: (f"active-{seed}", decks)
    )
    client = TestClient(create_app(tmp_path), headers={"X-Studio": "1"})
    started = client.post(
        "/api/games",
        json={
            "revision_id": "r",
            "opponent_ids": ["a", "b", "c"],
            "seed": seed,
            "human_seats": [0],
            "ai_delay_ms": 0,
        },
    )
    assert started.status_code == 200, started.text
    game_id = started.json()["game_id"]
    script = _ActiveScript(mulligans, illegal_amount_once)
    answered: collections.Counter[str] = collections.Counter()
    refused: list[tuple[str, int, str]] = []
    expected_refusals: list[tuple[str, int, str]] = []
    illegal_id = ""
    recovered_same_id = False
    conceded = False
    began = time.monotonic()
    state: dict[str, object] = {}
    try:
        while time.monotonic() - began < 900:
            state = client.get(f"/api/play/{game_id}?count=0").json()
            pending = state.get("pending_decision")
            if not pending:
                if not state.get("running"):
                    break
                time.sleep(0.15)
                continue
            assert isinstance(pending, dict)
            turn = (pending.get("pilot_state") or {}).get("turn_number", 1)
            if not conceded and isinstance(turn, int) and turn >= turn_limit:
                assert client.post(f"/api/play/{game_id}/concede").status_code == 200
                conceded = True
                continue
            cls = str(pending["decision_class"])
            was_illegal = script.sent_illegal
            body = script.answer(pending)
            if script.sent_illegal and not was_illegal:
                illegal_id = str(pending["decision_id"])  # this very answer is the illegal one
            reply = client.post(f"/api/play/{game_id}/decision", json=body)
            answered[cls] += 1
            if (
                reply.status_code == 200
                and expected_refusals
                and not recovered_same_id
                and str(pending["decision_id"]) == illegal_id
            ):
                recovered_same_id = True  # the next legal answer to the SAME decision was accepted
            if reply.status_code != 200:
                if (
                    illegal_id
                    and str(pending["decision_id"]) == illegal_id
                    and not expected_refusals
                ):
                    expected_refusals.append((cls, reply.status_code, reply.text[:200]))
                    continue  # the engine keeps the same decision open
                refused.append((cls, reply.status_code, reply.text[:200]))
                break
        else:
            pytest.fail(f"the game did not end within the time box; answered so far: {answered}")
    finally:
        client.app.state.play_manager.shutdown_all()  # type: ignore[attr-defined]
    result = state.get("result")
    assert isinstance(result, dict)
    return {
        "result": result,
        "answered": answered,
        "refused": refused,
        "expected_refusals": expected_refusals,
        "recovered_same_id": recovered_same_id,
        "conceded": conceded,
        "seconds": round(time.monotonic() - began, 1),
    }


def _human_frames(log: str) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    frames = []
    with gzip.open(log, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row.get("kind") == "frame":
                frames.append(row)
    return frames, [f for f in frames if f["seat"] == 0]


def _bare(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", text)).strip()


# What each scripted game must have shown the human (decision class, start of its prompt).
_REQUIRED = {
    "open_hostility": {
        ("mulligan", "Keep or mulligan"),
        ("target", "Select a card"),  # the London bottom: "(N more) to put on the bottom"
        ("priority", "Choose priority action"),
        ("mana_payment", ""),
        ("declare_attacker", "Choose attack for"),
        ("declare_blocker", "Choose creatures blocked by"),
    },
    "open_hostility_one_mulligan": {
        ("mulligan", "Keep or mulligan"),
        ("mana_payment", ""),
        ("declare_attacker", "Choose attack for"),
        ("declare_blocker", "Choose creatures blocked by"),
        ("multi_amount", "Assign amounts"),  # the human's attacker blocked by several creatures
    },
    "power_hungry": {
        ("mulligan", "Keep or mulligan"),
        ("target", "Select a card"),
        ("target", "Select an opponent"),  # a player as the target of a decision
        ("trigger_order", "Choose next triggered ability"),
        ("choose_use", ""),
        ("replacement_effect", "Choose replacement effect"),
        ("declare_attacker", "Choose attack for"),
        ("declare_blocker", "Choose creatures blocked by"),
    },
    "draconic_domination": {
        ("mulligan", "Keep or mulligan"),
        ("choice", ""),
        ("mode", ""),
        ("priority", "Choose priority action"),
    },
}


@pytest.mark.external
@pytest.mark.parametrize("name", sorted(_ACTIVE_GAMES))
def test_real_engine_scripted_human_covers_decision_classes_through_the_play_routes(
    name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Needs the pinned XMage bridge (Java 21); without it SKIPPED, which is not a pass.

    A four-seat game (human seat 0, three engine AI seats) driven only through
    ``/api/play/{id}/decision`` by a deterministic script (see ``_ActiveScript``). The engine must
    accept every answer (no refusal, no hang), the game must end, and the log of the human's own
    frames must show the decision classes this game is known to reach. Classes it did not reach are
    UNKNOWN, not passed. The Seat-N to seat N-1 rule is checked against the engine's own report:
    the engine's start-player answer "Full Game Seat K" must be followed by seat K-1 acting first.
    """
    _engine_or_skip(tmp_path)
    seed, deck, mulligans, illegal = _ACTIVE_GAMES[name]
    game = _play_scripted_game(tmp_path, monkeypatch, seed, deck, 60, mulligans, illegal)
    result = game["result"]
    assert isinstance(result, dict) and result.get("status") == "finished", result
    assert game["refused"] == [], game["refused"]
    # a regular end reported by the engine: the script did not have to concede, and someone won
    assert game["conceded"] is False, (
        "the game was cut off by the script's concede at the turn limit"
    )
    assert result.get("winner_seats"), result
    if illegal:
        # an illegal damage split is refused by the engine (PILOT_RESPONSE_INVALID, HTTP 422), the same
        # decision stays open, and the next legal answer is accepted: no hang
        expected = game["expected_refusals"]
        assert isinstance(expected, list) and len(expected) == 1
        assert expected[0][1] == 422 and "PILOT_RESPONSE_INVALID" in expected[0][2], expected
        assert (
            game["recovered_same_id"] is True
        )  # the next legal answer to that same decision_id: 200
    frames, human = _human_frames(str(result["log"]))
    seen = {(str(f["decision_class"]), _bare(str(f["prompt"]))) for f in human}
    missing = {
        need
        for need in _REQUIRED[name]
        if not any(cls == need[0] and prompt.startswith(need[1]) for cls, prompt in seen)
    }
    assert missing == set(), (missing, sorted(seen)[:40])
    # the mulligans taken, then keep; after the second one the London bottom choice is asked and accepted
    assert sum(f["decision_class"] == "mulligan" for f in human) == mulligans + 1
    assert any("put on the bottom" in _bare(str(f["prompt"])) for f in human) == (mulligans >= 2)
    # seat rule: the engine's own start-player choice against the seat that then acts first
    chosen = next(f for f in frames if "starting player" in str(f["prompt"]))
    picked = re.search(r"Full Game Seat (\d+)", str(chosen["chosen"][0]))  # type: ignore[index]
    assert picked is not None
    first_active = next(f["active_seat"] for f in frames if f["active_seat"] is not None)
    assert int(picked.group(1)) - 1 == first_active
    answered = game["answered"]
    assert isinstance(answered, collections.Counter)
    print(
        f"scripted human game {name}: seed {seed}, {sum(answered.values())} human decisions, "
        f"{len(frames)} frames, {game['seconds']} s, conceded {game['conceded']}, "
        f"result {result.get('winner_seats')}, answered {dict(answered)}"
    )


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
    fake = _FakeInteractiveClient()
    monkeypatch.setattr(play, "_PARK_POLL_SECONDS", 0.02)
    app, client = _start_fake_session(tmp_path, "dead-bridge", fake)
    try:
        _wait_for_pending(client, "dead-bridge", "dec-h-1")
        fake.exited = True  # the session asks the client's public process_exited()
        final = _wait_finished(client, "dead-bridge")
        assert final["result"]["status"] == "failed"  # type: ignore[index]
        assert "BRIDGE_EXITED" in str(final["result"]["failure_message"])  # type: ignore[index]
    finally:
        app.state.play_manager.shutdown_all()  # type: ignore[attr-defined]


LEAKED_CARD = "Leaked Hidden Card"


class _LeakingClient(_FakeInteractiveClient):
    """Puts a hidden hand of a non-actor seat into one decision frame, without the engine's
    ``private_state_visible`` flag: a bridge that broke the actor-scoped contract."""

    def __init__(self, leak_decision: str) -> None:
        super().__init__()
        self.leak_decision = leak_decision

    def request(self, method: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        status = super().request(method, payload)
        decision = status.get("decision")
        if isinstance(decision, dict) and decision.get("decision_id") == self.leak_decision:
            state = decision["pilot_state"]
            assert isinstance(state, dict)
            for row in state["players"]:  # type: ignore[union-attr]
                if not row["is_actor"]:
                    row.pop("private_state_visible", None)
                    row["hand"] = [{"name": LEAKED_CARD}]
        return status


@pytest.mark.parametrize(
    ("leak_decision", "human_answer_status"),
    [
        ("dec-h-1", None),  # the first frame (start of play)
        ("dec-ai-1", 409),  # the frame after the human's answer
        ("dec-h-2", 200),  # the frame after the AI's answer, the human's next decision
    ],
)
def test_a_leaking_frame_never_reaches_the_human_and_ends_the_game(
    tmp_path: Path, leak_decision: str, human_answer_status: int | None
) -> None:
    """Leak test of the PLAY path (#1663): every engine frame passes the match's actor-scoped
    audit before it is published or recorded; a frame that carries another seat's hidden
    information ends the game as failed (fail closed) and no snapshot, answer or log shows it."""
    fake = _LeakingClient(leak_decision)
    game_id = f"leak-{leak_decision}"
    app, client = _start_fake_session(tmp_path, game_id, fake, ai_delay_ms=0)
    seen: list[str] = []
    try:
        if human_answer_status is not None:
            seen.append(json.dumps(_wait_for_pending(client, game_id, "dec-h-1")))
            answered = client.post(
                f"/api/play/{game_id}/decision",
                json={"decision_id": "dec-h-1", "selected_option_ids": ["pass-1"], "ordering": []},
            )
            seen.append(answered.text)
            assert answered.status_code == human_answer_status, answered.text
        final = _wait_finished(client, game_id)
        seen.append(json.dumps(final))
        result = final["result"]
        assert isinstance(result, dict) and result["status"] == "failed", result
        assert final["pending_decision"] is None
        # the leaking frame was neither answered nor recorded
        assert leak_decision not in [r["decision_id"] for r in fake.submitted_responses]
        assert fake.closes == 1
    finally:
        app.state.play_manager.shutdown_all()  # type: ignore[attr-defined]
    log = Path(str(result["log"]))
    seen.append(gzip.decompress(log.read_bytes()).decode("utf-8"))
    assert all(LEAKED_CARD not in text for text in seen)


def _leak_into(status: dict[str, object]) -> dict[str, object]:
    """``status`` with a hidden AI hand in its decision frame, without the engine's flag."""
    decision = status["decision"]
    assert isinstance(decision, dict)
    for row in decision["pilot_state"]["players"]:  # type: ignore[index]
        if not row["is_actor"]:
            row.pop("private_state_visible", None)
            row["hand"] = [{"name": LEAKED_CARD}]
    return status


class _LeakAfterConcedeClient(_FakeInteractiveClient):
    """The engine answers the concede with another open decision that leaks."""

    def request(self, method: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        if method == "submit_concede":
            self.phase = 2
            return _leak_into(super().request("get_full_game_decision"))
        return super().request(method, payload)


class _LeakAfterRejectionClient(_FakeInteractiveClient):
    """The engine rejects the answer, and its status read then shows a moved, leaking frame."""

    rejected = False

    def request(self, method: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        if method == "submit_full_game_decision" and not self.rejected:
            self.rejected = True
            raw = ("external_pilot_decision_rejected", "ILLEGAL_ACTION: option not offered")
            raise FullGameProtocolError(
                "submit_full_game_decision failed: " + redacted_summary("BRIDGE_ERROR", raw),
                code="BRIDGE_ERROR",
                diagnostics=raw,
            )
        if method == "get_full_game_decision" and self.rejected:
            self.phase = 2
            return _leak_into(super().request(method, payload))
        return super().request(method, payload)


@pytest.mark.parametrize("route", ["concede", "decision"])
def test_a_leaking_frame_after_a_concede_or_a_rejected_answer_ends_the_game(
    tmp_path: Path, route: str
) -> None:
    """The two status reads outside the answer step (concede, the probe after a rejected
    answer) pass the same audit: the request is refused, the game fails, nothing leaks."""
    fake: _FakeInteractiveClient = (
        _LeakAfterConcedeClient() if route == "concede" else _LeakAfterRejectionClient()
    )
    game_id = f"leak-{route}"
    app, client = _start_fake_session(tmp_path, game_id, fake, ai_delay_ms=0)
    try:
        seen = [json.dumps(_wait_for_pending(client, game_id, "dec-h-1"))]
        body = {"decision_id": "dec-h-1", "selected_option_ids": ["pass-1"], "ordering": []}
        posted = client.post(
            f"/api/play/{game_id}/{route}", json={} if route == "concede" else body
        )
        seen.append(posted.text)
        assert posted.status_code == 409, posted.text
        final = _wait_finished(client, game_id)
        seen.append(json.dumps(final))
        result = final["result"]
        assert isinstance(result, dict) and result["status"] == "failed", result
    finally:
        app.state.play_manager.shutdown_all()  # type: ignore[attr-defined]
    seen.append(gzip.decompress(Path(str(result["log"])).read_bytes()).decode("utf-8"))
    assert all(LEAKED_CARD not in text for text in seen)


class _PrivateKeyLeakClient(_FakeInteractiveClient):
    """Puts a private key the Studio redaction does not remove (``mana_pool``,
    ``land_plays_remaining``) or an unlisted row key into the AI row of the human's frame."""

    def __init__(self, key: str) -> None:
        super().__init__()
        self.key = key

    def request(self, method: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        status = super().request(method, payload)
        decision = status.get("decision")
        if isinstance(decision, dict) and decision.get("decision_id") == "dec-h-2":
            for row in decision["pilot_state"]["players"]:  # type: ignore[index]
                if not row["is_actor"]:
                    row.pop("private_state_visible", None)
                    row[self.key] = [{"name": LEAKED_CARD}]
        return status


@pytest.mark.parametrize("key", ["mana_pool", "land_plays_remaining", "secret_zone"])
def test_a_private_key_the_redaction_keeps_never_reaches_a_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, key: str
) -> None:
    """The audit runs before a status is published (#1663 review P2-1): a hidden key that the
    Studio's hand redaction would let through is never in a published pending decision, a
    long-poll snapshot, an answer or the log; the game ends as failed."""
    published: list[str] = []
    original = play.InteractiveGameSession._publish_status

    def spying(self: play.InteractiveGameSession, status: object, match: object) -> None:
        original(self, status, match)  # type: ignore[arg-type]
        with self._lock:
            published.append(json.dumps(self._pending_decision))

    monkeypatch.setattr(play.InteractiveGameSession, "_publish_status", spying)
    fake = _PrivateKeyLeakClient(key)
    game_id = f"leak-key-{key}"
    app, client = _start_fake_session(tmp_path, game_id, fake, ai_delay_ms=0)
    seen: list[str] = []
    try:
        snap = _wait_for_pending(client, game_id, "dec-h-1")
        seen.append(json.dumps(snap))
        answered = client.post(
            f"/api/play/{game_id}/decision",
            json={"decision_id": "dec-h-1", "selected_option_ids": ["pass-1"], "ordering": []},
        )
        seen.append(answered.text)
        revision = snap["revision"]
        while True:
            held = client.get(f"/api/play/{game_id}?since={revision}&wait_ms=2000").json()
            seen.append(json.dumps(held))
            if not held["running"]:
                break
            revision = held["revision"]
        result = held["result"]
        assert isinstance(result, dict) and result["status"] == "failed", result
        assert "dec-h-2" not in [r["decision_id"] for r in fake.submitted_responses]
    finally:
        app.state.play_manager.shutdown_all()  # type: ignore[attr-defined]
    seen.append(gzip.decompress(Path(str(result["log"])).read_bytes()).decode("utf-8"))
    assert published, "the spy saw no publication"
    assert all(LEAKED_CARD not in text and key not in text for text in published)
    assert all(LEAKED_CARD not in text for text in seen)


def test_a_human_who_thinks_longer_than_the_park_poll_keeps_the_game_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No time limit in PLAY (review P2-2): many park polls pass while the human thinks; the
    game keeps waiting and goes on with the answer."""
    monkeypatch.setattr(play, "_PARK_POLL_SECONDS", 0.01)
    fake = _FakeInteractiveClient()
    app, client = _start_fake_session(tmp_path, "long-park", fake, ai_delay_ms=0)
    try:
        _wait_for_pending(client, "long-park", "dec-h-1")
        time.sleep(0.3)  # about 30 park polls
        snap = client.get("/api/play/long-park").json()
        assert snap["running"] is True and snap["pending_decision"]["decision_id"] == "dec-h-1"
        answered = client.post(
            "/api/play/long-park/decision",
            json={"decision_id": "dec-h-1", "selected_option_ids": ["pass-1"], "ordering": []},
        )
        assert answered.status_code == 200, answered.text
        _wait_for_pending(client, "long-park", "dec-h-2")
        assert fake.killed is False and fake.closes == 0
    finally:
        app.state.play_manager.shutdown_all()  # type: ignore[attr-defined]


class _HangingClient(_FakeInteractiveClient):
    """The AI's answer hangs in the bridge until the process is killed (review P2-3)."""

    def __init__(self) -> None:
        super().__init__()
        self.released = threading.Event()

    def request(self, method: str, payload: dict[str, object] | None = None) -> dict[str, object]:
        if method == "submit_full_game_decision" and self.phase == 1:
            self.released.wait(timeout=20.0)
            raise FullGameProtocolError("bridge killed", code="BRIDGE_EXITED")
        return super().request(method, payload)

    def kill(self) -> None:
        super().kill()
        self.released.set()


def test_stop_kills_a_bridge_stuck_in_a_request_and_lets_go_of_it(tmp_path: Path) -> None:
    fake = _HangingClient()
    app, client = _start_fake_session(tmp_path, "hang-stop", fake, ai_delay_ms=0)
    _wait_for_pending(client, "hang-stop", "dec-h-1")
    answered = client.post(
        "/api/play/hang-stop/decision",
        json={"decision_id": "dec-h-1", "selected_option_ids": ["pass-1"], "ordering": []},
    )
    assert answered.status_code == 200
    session = app.state.play_manager.get("hang-stop")  # type: ignore[attr-defined]
    session.shutdown(discard=True)  # the stop command cannot be served: the thread is stuck
    session._thread.join(timeout=5.0)
    assert fake.killed is True
    assert not session._thread.is_alive()
    assert session._active_bridge is None
    assert fake.closes == 1


def test_concede_ends_the_game_and_closes_the_bridge_once(tmp_path: Path) -> None:
    """Concede and end clean up (#1663): the engine thread ends, the bridge session is closed
    exactly once (graceful), and the session holds no bridge any more."""
    fake = _FakeInteractiveClient()
    app, client = _start_fake_session(tmp_path, "clean-concede", fake)
    try:
        _wait_for_pending(client, "clean-concede", "dec-h-1")
        assert client.post("/api/play/clean-concede/concede", json={}).status_code == 200
        final = _wait_finished(client, "clean-concede")
        session = app.state.play_manager.get("clean-concede")  # type: ignore[attr-defined]
        session._thread.join(timeout=5.0)
        assert not session._thread.is_alive()
        assert session._active_bridge is None
        assert (fake.starts, fake.closes, fake.killed) == (1, 1, False)
        assert fake.shutdown_disposition == "graceful_shutdown"
        assert final["result"]["status"] in {"finished", "failed"}  # type: ignore[index]
    finally:
        app.state.play_manager.shutdown_all()  # type: ignore[attr-defined]


def test_shutdown_while_the_human_thinks_closes_the_bridge_once(tmp_path: Path) -> None:
    fake = _FakeInteractiveClient()
    app, client = _start_fake_session(tmp_path, "clean-stop", fake)
    _wait_for_pending(client, "clean-stop", "dec-h-1")
    session = app.state.play_manager.get("clean-stop")  # type: ignore[attr-defined]
    app.state.play_manager.shutdown_game("clean-stop")  # type: ignore[attr-defined]
    assert not session._thread.is_alive()
    assert session._active_bridge is None
    assert (fake.starts, fake.closes, fake.killed) == (1, 1, False)
    # a stopped game reads no result: it ends as stopped by the user, as before
    assert "get_full_game_result" not in fake.requests
    stopped = public_full_game_exception_message(
        FullGameConformanceError("Spiel durch Benutzer beendet")
    )
    result = session.snapshot()["result"]
    assert result["status"] == "failed" and result["failure_message"] == stopped


def test_speed_zero_hurries_the_ai_but_never_answers_the_human(tmp_path: Path) -> None:
    class _VisibleAiClient(_FakeInteractiveClient):
        def _status(self) -> dict[str, object]:
            payload = super()._status()
            if self.phase == 1:
                decision = payload["decision"]
                assert isinstance(decision, dict)
                decision["decision_class"] = "choose_use"
                decision["prompt"] = "Use optional trigger?"
                pilot_state = decision["pilot_state"]
                assert isinstance(pilot_state, dict)
                pilot_state["actor_id"] = "p1"
                decision["legal_options"] = [
                    {
                        "option_id": "yes-ai",
                        "option_type": "yes",
                        "label": "Yes",
                        "metadata": {"value": True},
                    },
                    {
                        "option_id": "no-ai",
                        "option_type": "no",
                        "label": "No",
                        "metadata": {"value": False},
                    },
                ]
            return payload

    fake = _VisibleAiClient()
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


# ---- partie.js: the functions that send or select, run for real with the page's own source --------

_PAGE_PRELUDE = (
    _BC_PRELUDE
    + f"""
const SRC = require('fs').readFileSync({json.dumps((STATIC / "partie.js").as_posix())}, 'utf8');
const grab = (name) => {{
  const start = SRC.indexOf('function ' + name + '(');
  if (start < 0) throw new Error('missing ' + name);
  let depth = 0, i = SRC.indexOf('{{', start);
  for (; i < SRC.length; i += 1) {{ if (SRC[i] === '{{') depth += 1; else if (SRC[i] === '}}' && --depth === 0) break; }}
  return SRC.slice(start, i + 1);
}};
const NAMES = ['offeredOption', 'boardDecision', 'toggleOption', 'toggleBoardOption', 'sendBoardOption',
  'confirmSelection', 'adoptPendingDecision'];
function page(pending, click, selected) {{
  const calls = {{submitted: [], toasts: 0, menuClosed: 0, renders: 0}};
  const state = {{pendingDecision: pending, click, selectedOptions: selected || [], submitting: false, clickActive: true}};
  const body = NAMES.map(grab).join('\\n');
  const make = new Function('state', 'calls', 'toast', 'render', 'closeBoardMenu', 'submitHumanChoice', '$',
    body + '; return {{' + NAMES.join(',') + '}};');
  const fns = make(state, calls, () => {{ calls.toasts += 1; }}, () => {{ calls.renders += 1; }},
    () => {{ calls.menuClosed += 1; }}, (payload) => calls.submitted.push(payload), () => ({{hidden: false}}));
  return {{state, calls, fns}};
}}
const later = (p) => Object.assign({{}}, p, {{decision_id: 'a-later-decision'}});
"""
)


def test_page_list_toggle_works_for_decisions_with_numbers_and_options() -> None:
    out = _node_json(
        _PAGE_PRELUDE
        + """
const base = FX.discard_from_hand.pending_decision;
const p = Object.assign({}, base, {minimum_selections: 1, maximum_selections: 2,
  context: Object.assign({}, base.context, {numeric_max: 3})});
const m = BC.build(p);  // a number in the context: no board mapping at all
const first = String(p.legal_options[0].option_id);
const rows = [];
for (const click of [m, null]) {
  const {state, fns} = page(p, click);
  fns.toggleOption(first);
  rows.push(state.selectedOptions.slice());
}
// the board path stays shut for such a decision
const board = page(p, m); board.fns.toggleBoardOption(first);
console.log(JSON.stringify({kind: m.kind, rows, first}));
"""
    )
    assert isinstance(out, dict) and out["kind"] == "none"
    assert out["rows"] == [[out["first"]], [out["first"]]]  # the list still selects


def test_page_board_answers_only_bind_to_the_decision_the_model_was_built_for() -> None:
    out = _node_json(
        _PAGE_PRELUDE
        + """
const A = FX.target_battlefield_land.pending_decision;
const B = later(A);                      // the same options, offered again by a newer decision
const id = String(A.legal_options[0].option_id);
const modelA = BC.build(A);
const stale = page(B, modelA);           // the poll already delivered B, the board still shows A
stale.fns.sendBoardOption(id); stale.fns.confirmSelection(); stale.fns.toggleBoardOption(id);
const live = page(A, modelA);
live.fns.sendBoardOption(id);
const liveStaged = page(A, modelA, [id]); liveStaged.fns.confirmSelection();
const notOffered = page(A, modelA, ['not-offered']); notOffered.fns.confirmSelection();
const toggled = page(A, modelA); toggled.fns.toggleBoardOption(id);
console.log(JSON.stringify({id, stale: {sent: stale.calls.submitted, picked: stale.state.selectedOptions},
  live: live.calls.submitted, liveStaged: liveStaged.calls.submitted,
  notOffered: {sent: notOffered.calls.submitted, toasts: notOffered.calls.toasts}, toggled: toggled.state.selectedOptions,
  decision: A.decision_id}));
"""
    )
    assert isinstance(out, dict)
    assert out["stale"] == {"sent": [], "picked": []}  # nothing leaves for the newer decision
    assert out["live"] == [
        {"decision_id": out["decision"], "selected_option_ids": [out["id"]], "ordering": []}
    ]
    assert [row["decision_id"] for row in out["liveStaged"]] == [out["decision"]]
    assert out["notOffered"] == {
        "sent": [],
        "toasts": 1,
    }  # an id the engine does not offer is refused
    assert out["toggled"] == [out["id"]]


def test_page_drops_the_picks_and_the_model_when_the_decision_changes() -> None:
    out = _node_json(
        _PAGE_PRELUDE
        + """
const A = FX.target_battlefield_land.pending_decision;
const id = String(A.legal_options[0].option_id);
const run = (next) => {
  const {state, calls, fns} = page(A, BC.build(A), [id]);
  fns.adoptPendingDecision(next);
  return {picked: state.selectedOptions, click: state.click, active: state.clickActive, closed: calls.menuClosed,
    pending: state.pendingDecision && state.pendingDecision.decision_id};
};
console.log(JSON.stringify({changed: run(later(A)), none: run(null), same: run(Object.assign({}, A)), A: A.decision_id}));
"""
    )
    assert isinstance(out, dict)
    for key in ("changed", "none"):
        assert (out[key]["picked"], out[key]["click"], out[key]["active"]) == ([], None, False), key
        assert out[key]["closed"] == 1, key
    assert out["changed"]["pending"] == "a-later-decision" and out["none"]["pending"] is None
    # the same decision delivered again (every poll): the picks and the model stay
    assert out["same"]["picked"] and out["same"]["click"] is not None and out["same"]["closed"] == 0


def test_page_shows_commander_facts_only_as_the_engine_published_them() -> None:
    out = _node_json(
        _PAGE_PRELUDE
        + """
const rows = new Function(grab('commanderRows') + '; return commanderRows;')();
const ps = FX.declare_attacker.pending_decision.pilot_state;
const real = rows(ps);
const odd = rows({players: ps.players, commander_status: [
  {owner_id: 'op-1', name: 'No casts reported', commander_damage_to_player: [{player_id: 'op-9', total: 3}, {player_id: 'op-2', total: 'x'}], casts_from_command: null},
  {owner_id: 'nobody', name: 'Unknown owner', commander_damage_to_player: [], casts_from_command: 4}]});
console.log(JSON.stringify({real, odd, empty: [rows(null), rows({}), rows({commander_status: []}), rows({commander_status: 'x'}), rows({commander_status: {}})], keys: Object.keys(ps.commander_status[0])}));
"""
    )
    assert isinstance(out, dict)
    real = out["real"]
    # the engine's seats and numbers, nothing added up: seat 1 took 6 from Bello (seat 2), seat 2 took 7 from Emmara (seat 3)
    assert real["1"]["received"] == [
        {"fromSeat": 2, "fromName": "Bello, Bard of the Brambles", "total": 6}
    ]
    assert real["2"]["received"] == [
        {"fromSeat": 3, "fromName": "Emmara, Soul of the Accord", "total": 7}
    ]
    assert real["0"]["received"] == [] and real["3"]["received"] == []
    assert real["3"]["commanders"] == [{"name": "Emmara, Soul of the Accord", "casts": 2}]
    assert real["0"]["commanders"][0]["casts"] == 0
    # unknown casts stay unknown (null), an unknown owner or player and a non-number are dropped
    assert out["odd"] == {
        "1": {"commanders": [{"name": "No casts reported", "casts": None}], "received": []}
    }
    assert out["empty"] == [None] * 5  # no list from the engine: unknown, no line (not "none")
    assert (
        "commander_tax" not in out["keys"]
    )  # the engine publishes no tax: the page shows "Steuer unbekannt"


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


def test_boardclick_player_target_and_london_bottom_use_real_engine_ids() -> None:
    out = _node_json(
        _BC_PRELUDE
        + """
const {p, m} = view('target_player_opponent');
const ids = new Set(p.players ? [] : p.pilot_state.players.map((pl) => pl.player_id));
const seats = Object.keys(m.seats).map((s) => {
  const r = BC.resolve(p, m, {type: 'seat', seat: Number(s)});
  const o = p.legal_options.find((x) => String(x.option_id) === r.optionId);
  return {seat: Number(s), action: r.action, label: o && o.label, uuid: o && o.option_id};
});
const bottom = view('target_london_bottom');
const own = bottom.p.pilot_state.players.find((pl) => pl.player_id === bottom.p.actor_id);
const rows = Object.keys(bottom.m.objects).map((id) => [BC.resolve(bottom.p, bottom.m, {type: 'object', id}).action, bottom.m.objects[id].zone, (own.hand || []).some((c) => c.object_id === id)]);
console.log(JSON.stringify({kind: m.kind, seats, pilotIds: [...ids], bottomKind: bottom.m.kind, rows, hand: (own.hand || []).length}));
"""
    )
    assert isinstance(out, dict) and out["kind"] == "target"
    # the option ids are the engine's player ids; pilot_state calls the opponents op-N, so they never match
    assert all(row["uuid"] not in out["pilotIds"] for row in out["seats"])
    assert {pid for pid in out["pilotIds"] if pid.startswith("op-")} == {"op-1", "op-2", "op-3"}
    # the page finds the seat only through the engine's own player name "Full Game Seat N" (seat N-1)
    for row in out["seats"]:
        assert row["action"] == "send" and row["label"] == f"Full Game Seat {row['seat'] + 1}"
    assert [row["seat"] for row in out["seats"]] == [1, 2, 3]
    # the London bottom choice sits on the cards of the own hand: every one is a click, nothing else
    assert out["bottomKind"] == "target" and len(out["rows"]) == out["hand"] == 7
    assert all(row == ["send", "hand", True] for row in out["rows"])


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


# ---- finished-game replay (static/replay.js & partie.html/partie.js, #1530) -------------------


def test_replay_module_steps_and_jumps_on_loaded_frames_only_when_finished() -> None:
    script = (STATIC / "replay.js").read_text(encoding="utf-8")
    for forbidden in (
        "document.",
        "window.",
        "fetch(",
        "/api/",
        "innerHTML",
        "outerHTML",
        "eval(",
        "style=",
        ".toFixed(",
    ):
        assert forbidden not in script, forbidden

    out = _node_json(
        """
const R = require('./replay.js');
const frames = [
  { n: 1, turn: null, decision_class: 'mulligan', chosen: ['Keep'] },
  { n: 2, turn: 1, decision_class: 'priority', chosen: ['Play Forest'] },
  { n: 3, turn: 1, decision_class: 'priority', chosen: ['Pass priority'] },
  { n: 4, turn: 1, decision_class: 'mana_payment', chosen: ['Tap Forest'] },
  { n: 5, turn: 2, decision_class: 'priority', chosen: ['Cast Sol Ring'] },
  { n: 6, turn: 2, decision_class: 'priority', chosen: ['Pass priority'] },
  { n: 7, turn: 4, decision_class: 'priority', chosen: ['Cast Chulane'] },
  { n: 8, turn: 4, decision_class: 'priority', chosen: ['Pass priority'] },
];
console.log(JSON.stringify({
  avail: {
    runningHuman: R.isReplayAvailable({ running: true, interactive: true, result: null, handsRevealed: false, frames }),
    runningHumanWithResult: R.isReplayAvailable({ running: true, interactive: true, result: { status: 'finished' }, handsRevealed: true, frames }),
    runningAi: R.isReplayAvailable({ running: true, interactive: false, result: null, frames }),
    runningAiNoFrames: R.isReplayAvailable({ running: true, interactive: false, result: null, frames: [] }),
    emptyFinished: R.isReplayAvailable({ running: false, interactive: false, result: { status: 'finished' }, frames: [] }),
    humanNoResult: R.isReplayAvailable({ running: false, interactive: true, result: null, handsRevealed: true, frames }),
    humanNotRevealed: R.isReplayAvailable({ running: false, interactive: true, result: { status: 'finished' }, handsRevealed: false, frames }),
    finishedHuman: R.isReplayAvailable({ running: false, interactive: true, result: { status: 'finished' }, handsRevealed: true, frames }),
    finishedAi: R.isReplayAvailable({ running: false, interactive: false, result: { status: 'finished' }, frames }),
    notRunningNoResultAi: R.isReplayAvailable({ running: false, interactive: false, result: null, frames }),
  },
  minor: [R.isPass(frames[2]), R.isMinor(frames[3]), R.isMinor(frames[1]), R.isPass(null)],
  turns: R.listTurns(frames),
  fwdRaw: [R.stepForward(frames, 1, false), R.stepForward(frames, 7, false)],
  fwdSkip: [R.stepForward(frames, 1, true), R.stepForward(frames, 4, true), R.stepForward(frames, 6, true)],
  backRaw: [R.stepBackward(frames, 4, false), R.stepBackward(frames, 0, false)],
  backSkip: [R.stepBackward(frames, 4, true), R.stepBackward(frames, 6, true), R.stepBackward(frames, 1, true)],
  jump: {
    t1: R.jumpToTurn(frames, 1),
    t2: R.jumpToTurn(frames, 2),
    t4: R.jumpToTurn(frames, 4),
    below: R.jumpToTurn(frames, 0),
    gap: R.jumpToTurn(frames, 3),
    above: R.jumpToTurn(frames, 99),
  },
  nextTurn: [R.nextTurn(frames, 0), R.nextTurn(frames, 1), R.nextTurn(frames, 3), R.nextTurn(frames, 4), R.nextTurn(frames, 6)],
  prevTurn: [R.prevTurn(frames, 7), R.prevTurn(frames, 6), R.prevTurn(frames, 5), R.prevTurn(frames, 4), R.prevTurn(frames, 2), R.prevTurn(frames, 0)],
}));
"""
    )
    assert isinstance(out, dict)
    assert out["avail"] == {
        "runningHuman": False,
        "runningHumanWithResult": False,
        "runningAi": True,
        "runningAiNoFrames": False,
        "emptyFinished": False,
        "humanNoResult": False,
        "humanNotRevealed": False,
        "finishedHuman": True,
        "finishedAi": True,
        "notRunningNoResultAi": False,
    }
    assert out["minor"] == [True, True, False, False]
    assert out["turns"] == [
        {"turn": 1, "index": 1},
        {"turn": 2, "index": 4},
        {"turn": 4, "index": 6},
    ]
    assert out["fwdRaw"] == [2, 7]
    assert out["fwdSkip"] == [4, 6, 7]
    assert out["backRaw"] == [3, 0]
    assert out["backSkip"] == [1, 4, 0]
    assert out["jump"] == {"t1": 1, "t2": 4, "t4": 6, "below": 1, "gap": 4, "above": 6}
    assert out["nextTurn"] == [1, 4, 4, 6, 7]
    assert out["prevTurn"] == [4, 4, 1, 1, 0, 0]


def test_partie_replay_controls_contract_and_no_extra_api_routes() -> None:
    html = (STATIC / "partie.html").read_text(encoding="utf-8")
    js = (STATIC / "partie.js").read_text(encoding="utf-8")
    css = (STATIC / "partie.css").read_text(encoding="utf-8")

    # replay.js is loaded before partie.js and #replay-controls starts hidden with all controls
    assert html.index('src="replay.js"') < html.index('src="partie.js"')
    assert 'id="replay-controls"' in html and 'id="prev-turn"' in html and 'id="turn-jump"' in html
    assert 'aria-label="Zu Zug springen"' in html
    assert ".replay-controls" in css and "#replay-controls button:focus-visible" in css

    # One definition of isPass/isMinor (replay.js), the hint for revealed AI hands exists
    assert "const { isPass, isMinor } = StudioReplay;" in js
    assert "const isPass" not in js.replace("const { isPass", "")
    assert 'id="replay-note"' in html and "KI-Hände aufgedeckt" in html

    # No new/additional server route in partie.js (only the existing Studio endpoints)
    api_paths = sorted(set(re.findall(r"/api/[a-z0-9_/${}()?=&.-]+", js, re.IGNORECASE)))
    allowed_prefixes = (
        "/api/games",
        "/api/play/",
        "/api/public-cards",
        "/api/table",
    )
    assert api_paths and all(p.startswith(allowed_prefixes) for p in api_paths), api_paths
    assert not any("replay" in p.lower() or "turn" in p.lower() for p in api_paths), api_paths

    # Real renderReplayControls() from partie.js hides and disables all controls while running,
    # and reveals + populates #turn-jump once the game is finished.
    fn_src = js[js.index("function renderReplayControls() {") : js.index("function go(index)")]
    dom_out = _node_json(
        f"""
const StudioReplay = require('./replay.js');
const els = new Map();
const makeEl = (id) => ({{ id, hidden: false, disabled: false, value: '', dataset: {{}}, children: [], textContent: '',
  append(...kids) {{ this.children.push(...kids); }} }});
const $ = (id) => {{ if (!els.has(id)) els.set(id, makeEl(id)); return els.get(id); }};
const h = (tag, props, ...kids) => ({{ tag, props: props || {{}}, text: kids.join('') }});
const frames = [
  {{ n: 1, turn: 1, decision_class: 'priority', chosen: ['Play Forest'] }},
  {{ n: 2, turn: 2, decision_class: 'priority', chosen: ['Cast Sol Ring'] }},
  {{ n: 3, turn: 3, decision_class: 'priority', chosen: ['Cast Chulane'] }},
];
let stopped = 0;
const setPlaying = (on) => {{ if (!on) {{ state.playing = false; stopped += 1; }} }};
const state = {{ running: true, interactive: true, result: null, handsRevealed: false, frames, index: 2, playing: true }};
eval({json.dumps(fn_src)} + '\\nglobalThis.renderReplayControls = renderReplayControls;');
renderReplayControls();
const ids = ['first', 'prev-turn', 'back', 'play', 'next', 'next-turn', 'turn-jump', 'skip', 'position'];
const whileRunning = {{
  hidden: $('replay-controls').hidden,
  allDisabled: ids.every((id) => $(id).disabled === true),
  stopped,
}};
state.running = false;
state.result = {{ status: 'finished', winner_seats: [0] }};
state.handsRevealed = true;
state.index = 0;
renderReplayControls();
const atStart = {{
  hidden: $('replay-controls').hidden,
  options: $('turn-jump').children.map((o) => [o.props.value, o.text]),
  selected: $('turn-jump').value,
  firstDis: $('first').disabled,
  prevTurnDis: $('prev-turn').disabled,
  backDis: $('back').disabled,
  nextDis: $('next').disabled,
  nextTurnDis: $('next-turn').disabled,
  note: $('replay-note').hidden,
}};
state.index = 2;
renderReplayControls();
const atEnd = {{
  selected: $('turn-jump').value,
  prevTurnDis: $('prev-turn').disabled,
  nextDis: $('next').disabled,
  nextTurnDis: $('next-turn').disabled,
}};
state.running = true; state.interactive = false; state.result = null; state.handsRevealed = false;
state.playing = true;
renderReplayControls();
const runningAi = {{
  hidden: $('replay-controls').hidden,
  playDisabled: $('play').disabled,
  speedUntouched: true,
  note: $('replay-note').hidden,
  stillPlaying: state.playing,
}};
console.log(JSON.stringify({{ whileRunning, atStart, atEnd, runningAi }}));
"""
    )
    assert isinstance(dom_out, dict)
    assert dom_out["whileRunning"] == {"hidden": True, "allDisabled": True, "stopped": 1}
    assert dom_out["atStart"] == {
        "hidden": False,
        "options": [["1", "Zug 1"], ["2", "Zug 2"], ["3", "Zug 3"]],
        "selected": "1",
        "firstDis": True,
        "prevTurnDis": True,
        "backDis": True,
        "nextDis": False,
        "nextTurnDis": False,
        "note": False,
    }
    assert dom_out["runningAi"] == {
        "hidden": False,
        "playDisabled": False,
        "speedUntouched": True,
        "note": True,
        "stillPlaying": True,
    }
    assert dom_out["atEnd"] == {
        "selected": "3",
        "prevTurnDis": False,
        "nextDis": True,
        "nextTurnDis": True,
    }


def test_replay_keyboard_and_tick_behaviour_per_game_kind() -> None:
    js = (STATIC / "partie.js").read_text(encoding="utf-8")
    key_src = js[
        js.index('document.addEventListener("keydown", (event) => {') : js.index(
            '$("new-game").addEventListener("click"'
        )
    ]
    tick_src = js[js.index("function step(direction) {") : js.index("// ---- loading")]
    out = _node_json(
        f"""
const StudioReplay = require('./replay.js');
const frames = [
  {{ turn: 1, decision_class: 'priority', chosen: ['Play Forest'] }},
  {{ turn: 1, decision_class: 'priority', chosen: ['Pass priority'] }},
  {{ turn: 2, decision_class: 'priority', chosen: ['Cast Sol Ring'] }},
  {{ turn: 3, decision_class: 'priority', chosen: ['Cast Chulane'] }},
];
const state = {{ running: false, interactive: false, result: {{ status: 'finished' }}, handsRevealed: false, frames, index: 0, playing: false, timer: 0 }};
const calls = [];
const els = {{ skip: {{ checked: false }}, speed: {{ value: '5' }}, play: {{ textContent: '' }} }};
const $ = (id) => els[id] || (els[id] = {{}});
const go = (i) => {{ state.index = i; calls.push('go' + i); }};
let handler = null;
const document = {{ addEventListener: (name, fn) => {{ if (name === 'keydown') handler = fn; }} }};
const closeBoardMenu = () => false;
eval({json.dumps(tick_src)});
function isInteractive() {{ return false; }}
eval({json.dumps(key_src)});
const press = (key, extra, at) => {{
  calls.length = 0;
  state.index = at === undefined ? 0 : at;
  const ev = Object.assign({{ key, target: {{ closest: () => null }}, preventDefault() {{ calls.push('pd'); }} }}, extra || {{}});
  handler(ev);
  return calls.slice();
}};
const res = {{}};
state.index = 0;
res.finishedRight = press('ArrowRight');
res.finishedShiftRight = press('ArrowRight', {{ shiftKey: true }}, 0);
res.finishedLeft = press('ArrowLeft', {{}}, 3);
state.running = true; state.interactive = true; state.result = null; state.index = 0;
res.runningHumanRight = press('ArrowRight');
res.runningHumanSpace = press(' ');
state.interactive = false; state.index = 0;
res.runningAiRight = press('ArrowRight');
// tick at the live tail of a running AI game keeps waiting; a finished game stops
state.index = 3; state.playing = true;
setPlaying(true);
res.runningAiTailKeepsPlaying = state.playing;
clearTimeout(state.timer);
state.running = false; state.result = {{ status: 'finished' }}; state.playing = true;
setPlaying(true);
res.finishedTailStops = state.playing;
clearTimeout(state.timer);
console.log(JSON.stringify(res));
"""
    )
    assert isinstance(out, dict)
    assert out["finishedRight"] == ["pd", "go1"]
    assert out["finishedShiftRight"] == ["pd", "go2"]  # next turn start
    assert out["finishedLeft"] == ["pd", "go2"]
    assert out["runningHumanRight"] == []
    assert out["runningHumanSpace"] == []
    assert out["runningAiRight"] == ["pd", "go1"]
    assert out["runningAiTailKeepsPlaying"] is True
    assert out["finishedTailStops"] is False


# ---- Play P1a (#1529): yield modes, mana_payment land click, stack rail, own combat ledger ------


def test_yield_modes_only_send_pass_priority_and_stop_on_every_non_priority_class() -> None:
    non_priority = [
        "mulligan",
        "declare_attacker",
        "declare_blocker",
        "target",
        "mana_payment",
        "choose_use",
        "mode",
        "announce_x",
        "order",
        "trigger_order",
        "choice",
        "amount",
    ]
    script = (
        _FF_PRELUDE
        + f"""
const modes = ['until_my_turn', 'until_end_of_turn', 'until_stack_resolves'];
const nonPriority = {json.dumps(non_priority)};
const stoppedNonPriority = [];
for (const mode of modes) {{
  for (const cls of nonPriority) {{
    const v = FF.verdict(
      pending({{decision_class: cls, legal_options: [others[0], pass]}}, {{turn_number: 3, stack: [{{object_id: 's1', name: 'Bolt', controller_id: 'op-1'}}]}}),
      ctx({{mode, startTurn: 3, watchStackObjectId: 's1', stopOnOpponentStack: false}})
    );
    stoppedNonPriority.push({{mode, cls, action: v.action, hasOptionId: 'optionId' in v}});
  }}
}}
const eotSameTurn = FF.verdict(pending({{}}, {{active_player_id: 'p0', turn_number: 3}}), ctx({{mode: 'until_end_of_turn', startTurn: 3}}));
const eotNextTurn = FF.verdict(pending({{}}, {{active_player_id: 'op-1', turn_number: 4}}), ctx({{mode: 'until_end_of_turn', startTurn: 3}}));
const eotUnknownTurn = FF.verdict(pending({{}}, {{active_player_id: 'p0', turn_number: 3}}), ctx({{mode: 'until_end_of_turn', startTurn: null}}));
const eotOppStack = FF.verdict(pending({{}}, {{active_player_id: 'p0', turn_number: 3, stack: [{{object_id: 's1', name: 'Counterspell', controller_id: 'op-1'}}]}}), ctx({{mode: 'until_end_of_turn', startTurn: 3, stopOnOpponentStack: true}}));

const sWatch = {{object_id: 's-1', name: 'Sol Ring', controller_id: 'op-1'}};
const sResp = {{object_id: 's-2', name: 'Counterspell', controller_id: 'op-1'}};
const sOld = {{object_id: 's-0', name: 'Arcane Signet', controller_id: 'p0'}};
const stackPass = FF.verdict(pending({{}}, {{stack: [sWatch]}}), ctx({{mode: 'until_stack_resolves', watchStackObjectId: 's-1'}}));
const stackEmpty = FF.verdict(pending({{}}, {{stack: []}}), ctx({{mode: 'until_stack_resolves', watchStackObjectId: 's-1'}}));
const stackResolved = FF.verdict(pending({{}}, {{stack: [sOld]}}), ctx({{mode: 'until_stack_resolves', watchStackObjectId: 's-1'}}));
const stackNewOpp = FF.verdict(pending({{}}, {{stack: [sResp, sWatch]}}), ctx({{mode: 'until_stack_resolves', watchStackObjectId: 's-1'}}));
const badMode = FF.verdict(pending({{}}, {{}}), ctx({{mode: 'unknown_mode'}}));

console.log(JSON.stringify({{
  stoppedNonPriority,
  eotSameTurn, eotNextTurn, eotUnknownTurn, eotOppStack,
  stackPass, stackEmpty, stackResolved, stackNewOpp, badMode,
  modes: Object.keys(FF.MODES),
}}));
"""
    )
    out = _node_json(script)
    assert isinstance(out, dict)
    assert set(out["modes"]) == {"until_my_turn", "until_end_of_turn", "until_stack_resolves"}
    assert len(out["stoppedNonPriority"]) == 3 * len(non_priority)
    for row in out["stoppedNonPriority"]:
        assert row["action"] == "stop" and row["hasOptionId"] is False, row
    assert out["eotSameTurn"] == {"action": "pass", "optionId": "pass-1"}
    assert out["eotNextTurn"]["action"] == "stop" and "Zug" in out["eotNextTurn"]["reason"]
    assert out["eotUnknownTurn"]["action"] == "stop"
    assert out["eotOppStack"]["action"] == "stop" and "Counterspell" in out["eotOppStack"]["reason"]
    assert out["stackPass"] == {"action": "pass", "optionId": "pass-1"}
    assert out["stackEmpty"]["action"] == "stop" and "leer" in out["stackEmpty"]["reason"]
    assert (
        out["stackResolved"]["action"] == "stop" and "aufgelöst" in out["stackResolved"]["reason"]
    )
    assert out["stackNewOpp"]["action"] == "stop" and "Counterspell" in out["stackNewOpp"]["reason"]
    assert out["badMode"]["action"] == "stop"


def test_boardclick_mana_payment_land_click_emits_only_offered_option_id() -> None:
    script = (
        _BC_PRELUDE
        + """
const base = JSON.parse(JSON.stringify(FX.mana_payment.pending_decision));
const bf = base.pilot_state.players[0].battlefield;
const landA = bf[0].object_id;
const landB = bf[1].object_id;
const custom = Object.assign({}, base, {
  decision_id: 'mana-p1a-test',
  legal_options: [
    {option_id: 'cancel-1', option_type: 'cancel_mana_payment', label: 'Cancel mana payment', metadata: {}},
    {option_id: 'tap-a-green', option_type: 'mana_ability', label: 'Forest — {T}: Add {G}.', metadata: {source_object_id: landA}},
    {option_id: 'tap-b-white', option_type: 'mana_ability', label: 'Dual — {T}: Add {W}.', metadata: {source_object_id: landB}},
    {option_id: 'tap-b-blue', option_type: 'mana_ability', label: 'Dual — {T}: Add {U}.', metadata: {source_object_id: landB}},
  ],
});
const m = BC.build(custom);
const clickA = BC.resolve(custom, m, {type: 'object', id: landA});
const clickB = BC.resolve(custom, m, {type: 'object', id: landB});
const clickMissing = BC.resolve(custom, m, {type: 'object', id: 'unoffered-land'});
const okIds = new Set(custom.legal_options.map((o) => o.option_id));
const emitted = BC.emittable(m);
console.log(JSON.stringify({
  kind: m.kind,
  mode: m.mode,
  clickA,
  clickB,
  clickMissing,
  loose: m.loose,
  emittedOnlyOffered: emitted.every((id) => okIds.has(id)),
}));
"""
    )
    out = _node_json(script)
    assert isinstance(out, dict)
    assert (out["kind"], out["mode"]) == ("mana_payment", "immediate")
    assert out["clickA"] == {"action": "send", "optionId": "tap-a-green"}
    assert out["clickB"]["action"] == "menu"
    assert [opt["optionId"] for opt in out["clickB"]["options"]] == [
        "tap-b-white",
        "tap-b-blue",
    ]
    assert out["clickMissing"] == {"action": "none"}
    assert out["loose"] == ["cancel-1"]
    assert out["emittedOnlyOffered"] is True


def test_play_p1a_stack_rail_and_own_combat_ledger_project_published_state_only() -> None:
    script = """
const P1a = require('./play_p1a.js');
const pilotState = {
  turn_number: 5,
  step: 'declare_attackers',
  players: [
    {seat: 0, player_id: 'p0', battlefield: [{object_id: 'cre-1', name: 'Llanowar Elves'}]},
    {seat: 1, player_id: 'op-1', battlefield: [{object_id: 'cre-2', name: 'Hidden Morph', face_down: true}]},
  ],
  stack: [
    {object_id: 'st-top', name: 'Swords to Plowshares', controller_id: 'op-1', target_ids: ['cre-1']},
    {object_id: 'st-mid', name: 'Secret Spell', face_down: true, controller_id: 'op-1'},
    {object_id: 'st-bot', name: 'stack ability (Draw a card.)', controller_id: 'p0', targets: [{object_id: 'cre-2', face_down: true}, {player_id: 'p0'}]},
  ],
};
const rail = P1a.buildStackRail(pilotState, (s) => 'Sitz ' + (s + 1));

let ledger = P1a.emptyCombatLedger();
const atkDec = {
  decision_id: 'atk-1',
  decision_class: 'declare_attacker',
  legal_options: [
    {option_id: 'opt-atk', option_type: 'declare_attacker', label: 'Chulane attacks Full Game Seat 2'},
    {option_id: 'opt-hold', option_type: 'hold_attacker', label: 'Do not attack with Chulane'},
  ],
  pilot_state: {turn_number: 5, step: 'declare_attackers'},
};
ledger = P1a.recordOwnCombatAnswer(ledger, atkDec, ['opt-atk', 'forged-id']);
// Non-combat decision must not add an entry
ledger = P1a.recordOwnCombatAnswer(ledger, {decision_id: 'pri-1', decision_class: 'priority', legal_options: [{option_id: 'p', label: 'Pass'}], pilot_state: {turn_number: 5, step: 'declare_attackers'}}, ['p']);
const blkDec = {
  decision_id: 'blk-1',
  decision_class: 'declare_blocker',
  prompt: 'Block with Llanowar Elves',
  legal_options: [{option_id: 'att-9', option_type: 'blocker', label: 'Llanowar Elves blocks Grizzly Bears'}],
  pilot_state: {turn_number: 5, step: 'declare_blockers'},
};
const afterBlk = P1a.recordOwnCombatAnswer(ledger, blkDec, []);
const clearedStep = P1a.clearOwnCombatLedger(afterBlk, 5, 'postcombat_main');
const clearedTurn = P1a.clearOwnCombatLedger(afterBlk, 6, 'declare_attackers');

console.log(JSON.stringify({rail, ledger, afterBlk, clearedStep, clearedTurn}));
"""
    out = _node_json(script)
    assert isinstance(out, dict)
    rail = out["rail"]
    assert len(rail) == 3
    assert rail[0]["isTop"] is True and rail[0]["name"] == "Swords to Plowshares"
    assert rail[0]["controllerLabel"] == "Sitz 2"
    assert rail[0]["targets"] == ["Llanowar Elves"] and rail[0]["targetsPublished"] is True
    assert rail[1]["isTop"] is False and rail[1]["name"] == "verdeckt"
    assert rail[1]["targets"] == [] and rail[1]["targetsPublished"] is False
    assert "Secret Spell" not in json.dumps(rail)
    assert rail[2]["isAbility"] is True and rail[2]["displayName"] == "Fähigkeit: Draw a card."
    assert rail[2]["controllerLabel"] == "Sitz 1"
    assert rail[2]["targets"] == ["verdeckt", "Sitz 1"]

    ledger = out["ledger"]
    assert "eigene Angaben" in ledger["label"]
    assert len(ledger["entries"]) == 1
    assert ledger["entries"][0]["optionId"] == "opt-atk"
    assert len(out["afterBlk"]["entries"]) == 2
    assert out["afterBlk"]["entries"][1]["kind"] == "no_block"
    assert out["clearedStep"]["entries"] == []
    assert out["clearedTurn"]["entries"] == []


_P1A_IO_PRELUDE = """
const P1a = require('./play_p1a.js');
const atk = {decision_id: 'atk-1', decision_class: 'declare_attacker',
  legal_options: [{option_id: 'opt-atk', option_type: 'declare_attacker', label: 'Chulane attacks Seat 2'}],
  pilot_state: {turn_number: 5, step: 'declare_attackers'}};
const nextPending = {decision_id: 'pri-9', decision_class: 'priority',
  legal_options: [{option_id: 'p9', option_type: 'pass_priority', label: 'Pass priority'}],
  pilot_state: {turn_number: 5, step: 'declare_attackers'}};
function makeIo(post) {
  const calls = [];
  const io = {
    pending: atk,
    ledger: P1a.emptyCombatLedger(),
    log: [],
    getPendingDecision() { return io.pending; },
    async post(payload) { calls.push('post'); return post(io, payload); },
    getLedger() { return io.ledger; },
    setLedger(l) { calls.push('ledger'); io.ledger = l; },
    logAutoPass(line) { calls.push('log'); io.log.push(line); },
  };
  return {io, calls};
}
"""


def test_play_p1a_submit_answer_books_the_sent_decision_and_logs_only_accepted_passes() -> None:
    script = (
        _P1A_IO_PRELUDE
        + """
(async () => {
  // (a) a poll replaces the pending decision while the post is in flight: the answer still belongs
  // to the decision that was sent, not to the new one
  const a = makeIo(async (io) => { io.pending = nextPending; return {ok: true}; });
  const sentA = await P1a.submitAnswer(a.io, {decision_id: 'atk-1', selected_option_ids: ['opt-atk']}, {});
  // (b) accepted automatic pass: exactly one log line, written after the post
  const b = makeIo(async () => ({ok: true}));
  b.io.pending = nextPending;
  await P1a.submitAnswer(b.io, {decision_id: 'pri-9', selected_option_ids: ['p9']}, {autoPassReason: 'Bis Zugende'});
  // (c) refused answer (post rejects): the rejection propagates, no ledger entry, no log line
  const c = makeIo(async () => { throw new Error('422 refused'); });
  c.io.pending = nextPending;
  let rejected = null;
  try { await P1a.submitAnswer(c.io, {decision_id: 'pri-9', selected_option_ids: ['p9']}, {autoPassReason: 'Bis Zugende'}); }
  catch (error) { rejected = String(error.message); }
  const c2 = makeIo(async () => { throw new Error('409 stale'); });
  let rejected2 = null;
  try { await P1a.submitAnswer(c2.io, {decision_id: 'atk-1', selected_option_ids: ['opt-atk']}, {}); }
  catch (error) { rejected2 = String(error.message); }
  // (d) a manual answer writes no auto-pass line; (e) nothing pending sends nothing
  const d = makeIo(async () => ({ok: true}));
  await P1a.submitAnswer(d.io, {decision_id: 'atk-1', selected_option_ids: ['opt-atk']});
  const e = makeIo(async () => ({ok: true}));
  e.io.pending = null;
  const sentE = await P1a.submitAnswer(e.io, {decision_id: 'x', selected_option_ids: []}, {autoPassReason: 'x'});
  console.log(JSON.stringify({
    a: {sent: sentA.decision_id, entries: a.io.ledger.entries, calls: a.calls, log: a.io.log},
    b: {calls: b.calls, log: b.io.log, entries: b.io.ledger.entries},
    c: {rejected, calls: c.calls, log: c.io.log, entries: c.io.ledger.entries},
    c2: {rejected: rejected2, calls: c2.calls, entries: c2.io.ledger.entries},
    d: {calls: d.calls, log: d.io.log, entries: d.io.ledger.entries},
    e: {sent: sentE, calls: e.calls},
    lineManual: P1a.autoPassLine({seat: 0}, 'Auto-Pass bis eigene Aktion'),
  }));
})();
"""
    )
    out = _node_json(script)
    assert isinstance(out, dict)
    a = out["a"]
    assert a["sent"] == "atk-1" and a["calls"] == ["post", "ledger"] and a["log"] == []
    assert [(e["kind"], e["decisionId"], e["optionId"]) for e in a["entries"]] == [
        ("attacker", "atk-1", "opt-atk")
    ]
    b = out["b"]
    assert b["calls"] == ["post", "ledger", "log"]  # the line comes after the accepted post
    assert b["log"] == [
        {"seat": 0, "tag": "S1", "text": "Auto-Pass (Bis Zugende): Priorität abgegeben"}
    ]
    assert b["entries"] == []  # a priority pass is no combat answer
    for key in ("c", "c2"):
        assert out[key]["entries"] == [] and out[key]["calls"] == ["post"], key
    assert "422" in out["c"]["rejected"] and out["c"]["log"] == []
    assert "409" in out["c2"]["rejected"]
    assert out["d"]["log"] == [] and out["d"]["calls"] == ["post", "ledger"]
    assert len(out["d"]["entries"]) == 1
    assert out["e"] == {"sent": None, "calls": []}
    assert out["lineManual"]["text"].startswith("Auto-Pass (Auto-Pass bis eigene Aktion)")


def test_play_p1a_own_combat_survives_rewind_and_is_cleaned_up_only_at_the_live_end() -> None:
    script = """
const P1a = require('./play_p1a.js');
const dec = {decision_id: 'atk-1', decision_class: 'declare_attacker',
  legal_options: [{option_id: 'opt-atk', option_type: 'declare_attacker', label: 'Chulane attacks Seat 2'}],
  pilot_state: {turn_number: 5, step: 'declare_attackers'}};
const ledger = P1a.recordOwnCombatAnswer(P1a.emptyCombatLedger(), dec, ['opt-atk'], dec.pilot_state);
const live = {turn: 5, step: 'declare_attackers'};
// rewind to an earlier turn, to a frame outside of combat, and back to the live end
const rewoundTurn = P1a.ownCombatView(ledger, {turn: 3, step: 'upkeep'}, false, true);
const rewoundStep = P1a.ownCombatView(rewoundTurn.ledger, {turn: 5, step: 'precombat_main'}, false, true);
const backLive = P1a.ownCombatView(rewoundStep.ledger, live, true, true);
const liveNonInteractive = P1a.ownCombatView(ledger, live, true, false);
// the live end is the only place where the interim state is cleaned up
const liveOtherStep = P1a.ownCombatView(ledger, {turn: 5, step: 'postcombat_main'}, true, true);
const liveNextTurn = P1a.ownCombatView(ledger, {turn: 6, step: 'declare_attackers'}, true, true);
// XMage publishes PhaseStep.BEGIN_COMBAT lower-cased: begin_combat is a combat step
const liveBegin = P1a.ownCombatView(ledger, {turn: 5, step: 'begin_combat'}, true, true);
const liveOldName = P1a.ownCombatView(ledger, {turn: 5, step: 'beginning_combat'}, true, true);
console.log(JSON.stringify({
  ledger, rewoundTurn, rewoundStep, backLive, liveNonInteractive, liveOtherStep, liveNextTurn,
  liveBegin, liveOldName, steps: P1a.COMBAT_STEPS,
}));
"""
    out = _node_json(script)
    assert isinstance(out, dict)
    kept = out["ledger"]["entries"]
    assert len(kept) == 1
    for key in ("rewoundTurn", "rewoundStep"):
        assert out[key]["visible"] is False and out[key]["ledger"]["entries"] == kept, key
    assert out["backLive"]["visible"] is True and out["backLive"]["ledger"]["entries"] == kept
    assert out["liveNonInteractive"]["visible"] is False
    assert out["liveOtherStep"]["ledger"]["entries"] == []
    assert out["liveNextTurn"]["ledger"]["entries"] == []
    assert out["liveBegin"]["ledger"]["entries"] == kept and out["liveBegin"]["visible"] is True
    assert out["liveOldName"]["ledger"]["entries"] == []
    assert "begin_combat" in out["steps"] and "beginning_combat" not in out["steps"]


def test_fast_forward_stack_checkbox_is_disabled_with_a_hint_and_mode_switch_retargets() -> None:
    script = (
        _FF_PRELUDE
        + """
const boxStack = FF.stackCheckboxState('until_stack_resolves');
const boxMy = FF.stackCheckboxState('until_my_turn');
const boxEot = FF.stackCheckboxState('until_end_of_turn');
const opp = {object_id: 's-1', name: 'Counterspell', controller_id: 'op-1'};
// no entry to watch and the checkbox off: the opponent object stops the run anyway (not ignored)
const noWatchOpp = FF.verdict(pending({}, {stack: [opp]}), ctx({mode: 'until_stack_resolves', stopOnOpponentStack: false}));
const base = {on: true, boosted: true, mode: 'until_my_turn', startTurn: 3, stopOnOpponentStack: true, watchStackObjectId: null};
const toStack = FF.retarget(base, 'until_stack_resolves', {topStackObjectId: 's-7', currentTurn: 4});
const toEot = FF.retarget(toStack, 'until_end_of_turn', {topStackObjectId: 's-7', currentTurn: 4});
const toMy = FF.retarget(toEot, 'until_my_turn', {topStackObjectId: null, currentTurn: 4});
const toStackEmpty = FF.retarget(base, 'until_stack_resolves', {topStackObjectId: null, currentTurn: 4});
console.log(JSON.stringify({boxStack, boxMy, boxEot, noWatchOpp, toStack, toEot, toMy, toStackEmpty, base}));
"""
    )
    out = _node_json(script)
    assert isinstance(out, dict)
    assert out["boxStack"]["disabled"] is True and "Gegner" in out["boxStack"]["hint"]
    assert out["boxMy"] == out["boxEot"] == {"disabled": False, "hint": ""}
    assert out["noWatchOpp"]["action"] == "stop" and "Counterspell" in out["noWatchOpp"]["reason"]
    assert out["toStack"]["mode"] == "until_stack_resolves"
    assert out["toStack"]["watchStackObjectId"] == "s-7" and out["toStack"]["startTurn"] == 3
    assert out["toEot"]["watchStackObjectId"] is None and out["toEot"]["startTurn"] == 4
    assert out["toMy"]["mode"] == "until_my_turn" and out["toMy"]["watchStackObjectId"] is None
    assert out["toStackEmpty"]["watchStackObjectId"] is None
    assert out["base"]["watchStackObjectId"] is None and out["base"]["mode"] == "until_my_turn"


def test_should_pause_for_ai_step_distinguishes_visible_and_invisible_steps() -> None:
    pass_opt = {"option_id": "pass-1", "option_type": "pass_priority", "label": "Pass priority"}
    cast_opt = {"option_id": "cast-1", "option_type": "cast_spell", "label": "Cast Sol Ring"}
    land_opt = {"option_id": "land-1", "option_type": "play_land", "label": "Play Forest"}
    act_opt = {
        "option_id": "act-1",
        "option_type": "activated_ability",
        "label": "Activate: Draw a card",
    }

    # Forced decisions (at most 1 legal option): never pause.
    assert (
        play.should_pause_for_ai_step(
            {"decision_class": "priority", "legal_options": [pass_opt]},
            {"selected_option_ids": ["pass-1"]},
        )
        is False
    )
    assert (
        play.should_pause_for_ai_step(
            {
                "decision_class": "mana_payment",
                "legal_options": [
                    {"option_id": "m1", "option_type": "mana_payment", "label": "Tap Forest"}
                ],
            },
            {"selected_option_ids": ["m1"]},
        )
        is False
    )
    assert (
        play.should_pause_for_ai_step(
            {
                "decision_class": "target",
                "legal_options": [
                    {"option_id": "t1", "option_type": "target", "label": "Llanowar Elves"}
                ],
            },
            {"selected_option_ids": ["t1"]},
        )
        is False
    )
    assert play.should_pause_for_ai_step({"decision_class": "choice", "legal_options": []}) is False

    # Priority pass without an action (even with multiple legal options): never pause.
    assert (
        play.should_pause_for_ai_step(
            {"decision_class": "priority", "legal_options": [pass_opt, cast_opt]},
            {"selected_option_ids": ["pass-1"]},
        )
        is False
    )
    assert (
        play.should_pause_for_ai_step(
            {
                "decision_class": "priority",
                "legal_options": [
                    {"option_id": "p-label", "label": "Pass priority"},
                    cast_opt,
                ],
            },
            {"selected_option_ids": ["p-label"]},
        )
        is False
    )

    # Visible priority actions: pause.
    for chosen in (cast_opt, land_opt, act_opt):
        assert (
            play.should_pause_for_ai_step(
                {"decision_class": "priority", "legal_options": [pass_opt, chosen]},
                {"selected_option_ids": [chosen["option_id"]]},
            )
            is True
        )

    # Combat, targets, multi-option mana payment, and other 2+-option choices: pause.
    for dc in (
        "declare_attacker",
        "declare_blocker",
        "target",
        "mana_payment",
        "mode",
        "choose_use",
        "choice",
        "choose_object",
        "mulligan",
        "order",
        "trigger_order",
    ):
        assert (
            play.should_pause_for_ai_step(
                {
                    "decision_class": dc,
                    "legal_options": [
                        {"option_id": "o1", "label": "Option A"},
                        {"option_id": "o2", "label": "Option B"},
                    ],
                },
                {"selected_option_ids": ["o1"]},
            )
            is True
        ), dc

    # Numeric choices: pause when a real range exists, skip when forced (min == max).
    assert (
        play.should_pause_for_ai_step(
            {
                "decision_class": "announce_x",
                "legal_options": [],
                "context": {"numeric_min": 0, "numeric_max": 4},
            },
            {"selected_option_ids": [], "numeric_choice": 2},
        )
        is True
    )
    assert (
        play.should_pause_for_ai_step(
            {
                "decision_class": "announce_x",
                "legal_options": [],
                "context": {"numeric_min": 0, "numeric_max": 0},
            },
            {"selected_option_ids": [], "numeric_choice": 0},
        )
        is False
    )
    assert (
        play.should_pause_for_ai_step(
            {
                "decision_class": "multi_amount",
                "legal_options": [],
                "context": {"numeric_legs": [{"min": 0, "max": 3}, {"min": 0, "max": 3}]},
            },
            {"selected_option_ids": [], "numeric_choices": [2, 1]},
        )
        is True
    )
    assert (
        play.should_pause_for_ai_step(
            {
                "decision_class": "multi_amount",
                "legal_options": [],
                "context": {"numeric_legs": [{"min": 1, "max": 1}, {"min": 2, "max": 2}]},
            },
            {"selected_option_ids": [], "numeric_choices": [1, 2]},
        )
        is False
    )


def test_ai_tempo_default_250_and_zero_no_pause_server_and_ui(tmp_path: Path) -> None:
    assert play.DEFAULT_AI_DELAY_MS == 250

    decks = (
        _make_deck("own", "Chulane, Teller of Tales"),
        _make_deck("opp", "Kinnan, Bonder Prodigy"),
    )
    prep = play.prepare_game(
        decks, seed=11, game_id="tempo-default", human_seats=[0], decision_timeout_seconds=0
    )
    session = play.InteractiveGameSession(
        tmp_path,
        prep,
        human_seats=[0],
        decision_timeout_seconds=0,
        command=("fake-bridge",),
    )
    try:
        assert session.ai_delay_ms == 250
        assert session.set_speed(0) == 0
        assert session.ai_delay_ms == 0
        assert session.set_speed(-50) == 0
        assert session.set_speed(9_999) == 5_000
    finally:
        session._recorder.discard()

    js_text = (STATIC / "partie.js").read_text(encoding="utf-8")
    m_default = re.search(r"const DEFAULT_AI_DELAY_MS = (\d+);", js_text)
    assert m_default is not None and int(m_default.group(1)) == 250
    m_speeds = re.search(r"const SPEEDS = (\[.*?\]);", js_text)
    assert m_speeds is not None
    speeds = json.loads(m_speeds.group(1))
    delays = [entry[0] for entry in speeds]
    assert delays == [2000, 1000, 500, 250, 120, 50, 0]
    labels_by_delay = {entry[0]: entry[1] for entry in speeds}
    assert "ohne Pause" in labels_by_delay[0]
    assert "250 ms" in labels_by_delay[250]
    assert '$("speed").value = String(DEFAULT_AI_DELAY_MS);' in js_text


def test_ai_tempo_visible_only_pause_and_delay_equivalence(tmp_path: Path) -> None:
    class _TempoEquivalenceClient(_FakeInteractiveClient):
        def _status(self) -> dict[str, object]:
            base_outcomes = [
                {"seat": 0, "player_id": "p0", "life": 40, "can_concede": True},
                {"seat": 1, "player_id": "p1", "life": 40, "can_concede": True},
            ]
            if self.phase == 0:
                return super()._status()
            if 1 <= self.phase <= 6:
                # 6 forced 1-option AI priority passes: 0 ms pause
                return {
                    "terminal": False,
                    "outcomes": base_outcomes,
                    "decision": {
                        "decision_id": f"dec-ai-forced-{self.phase}",
                        "decision_offset": self.phase + 1,
                        "actor_id": "p1",
                        "seat": 1,
                        "acting_for_seat": 1,
                        "decision_class": "priority",
                        "prompt": "Pass priority",
                        "minimum_selections": 1,
                        "maximum_selections": 1,
                        "legal_options": [
                            {
                                "option_id": f"forced-{self.phase}",
                                "option_type": "pass_priority",
                                "label": "Pass priority",
                            }
                        ],
                        "pilot_state": _pilot_state(
                            seat=1, turn=2, active_player_id="p1", secret_opp_card=self.SECRET_CARD
                        ),
                    },
                }
            if self.phase == 7:
                # 1 visible AI step (2-option choose_use): observes ai_delay_ms
                return {
                    "terminal": False,
                    "outcomes": base_outcomes,
                    "decision": {
                        "decision_id": "dec-ai-visible-1",
                        "decision_offset": 8,
                        "actor_id": "p1",
                        "seat": 1,
                        "acting_for_seat": 1,
                        "decision_class": "choose_use",
                        "prompt": "Use optional trigger?",
                        "minimum_selections": 1,
                        "maximum_selections": 1,
                        "legal_options": [
                            {
                                "option_id": "vis-yes",
                                "option_type": "yes",
                                "label": "Yes",
                                "metadata": {"value": True},
                            },
                            {
                                "option_id": "vis-no",
                                "option_type": "no",
                                "label": "No",
                                "metadata": {"value": False},
                            },
                        ],
                        "pilot_state": _pilot_state(
                            seat=1, turn=2, active_player_id="p1", secret_opp_card=self.SECRET_CARD
                        )
                        | {"actor_id": "p1"},
                    },
                }
            return {
                "terminal": False,
                "outcomes": base_outcomes,
                "decision": {
                    "decision_id": "dec-h-2",
                    "decision_offset": 9,
                    "actor_id": "p0",
                    "seat": 0,
                    "acting_for_seat": 0,
                    "decision_class": "target",
                    "prompt": "Choose up to 1 target",
                    "minimum_selections": 0,
                    "maximum_selections": 1,
                    "legal_options": [
                        {"option_id": "tgt-1", "option_type": "target", "label": "Llanowar Elves"}
                    ],
                    "pilot_state": _pilot_state(
                        seat=0, turn=2, active_player_id="p1", secret_opp_card=self.SECRET_CARD
                    ),
                },
            }

    def _run_with_delay(
        delay_ms: int, subdir: str
    ) -> tuple[list[dict[str, object]], list[object], float]:
        folder = tmp_path / subdir
        folder.mkdir(parents=True, exist_ok=True)
        fake = _TempoEquivalenceClient()
        app, client = _start_fake_session(folder, f"eq-{delay_ms}", fake, ai_delay_ms=delay_ms)
        try:
            _wait_for_pending(client, f"eq-{delay_ms}", "dec-h-1")
            t0 = time.monotonic()
            resp = client.post(
                f"/api/play/eq-{delay_ms}/decision",
                json={"decision_id": "dec-h-1", "selected_option_ids": ["pass-1"], "ordering": []},
            )
            assert resp.status_code == 200
            snap = _wait_for_pending(client, f"eq-{delay_ms}", "dec-h-2")
            elapsed = time.monotonic() - t0
            frames = snap["frames"]
            assert isinstance(frames, list)
            return list(fake.submitted_responses), list(frames), elapsed
        finally:
            app.state.play_manager.shutdown_all()  # type: ignore[attr-defined]

    responses_0, frames_0, elapsed_0 = _run_with_delay(0, "d0")
    responses_250, frames_250, elapsed_250 = _run_with_delay(250, "d250")

    # Pause must never alter the decision sequence or the recorded frames.
    assert responses_0 == responses_250
    assert frames_0 == frames_250
    assert len(responses_0) == 8  # 1 human + 6 forced AI + 1 visible AI
    # With 6 forced + 1 visible step at 250 ms, only the 1 visible step pauses (~0.25 s, not 1.75 s).
    assert elapsed_250 >= 0.20
    assert elapsed_250 < 1.25
    assert elapsed_0 < 1.0


# ---- new decisions are reported at once, not at a fixed interval (#1593) ---------------------------


def _held_get(
    client: TestClient, game_id: str, *, start: int, since: int | None, wait_ms: int
) -> tuple[dict[str, object], float]:
    query = f"start={start}&wait_ms={wait_ms}" + ("" if since is None else f"&since={since}")
    began = time.monotonic()
    response = client.get(f"/api/play/{game_id}?{query}")
    assert response.status_code == 200
    return response.json(), time.monotonic() - began


def test_a_held_state_request_returns_with_the_next_decision_and_hides_nothing(
    tmp_path: Path,
) -> None:
    app, client = _start_fake_session(tmp_path, "held-1", _FakeInteractiveClient())
    try:
        first = _wait_for_pending(client, "held-1", "dec-h-1")
        revision = first["revision"]
        assert type(revision) is int
        answered: dict[str, object] = {}

        def hold() -> None:
            other = TestClient(app, headers={"X-Studio": "1"})
            page, took = _held_get(other, "held-1", start=0, since=revision, wait_ms=6000)
            answered.update(page=page, took=took)

        waiter = threading.Thread(target=hold)
        waiter.start()
        time.sleep(0.3)
        assert not answered, "nothing changed yet: the request must still be held"
        sent = time.monotonic()
        post = client.post(
            "/api/play/held-1/decision",
            json={"decision_id": "dec-h-1", "selected_option_ids": ["pass-1"], "ordering": []},
        )
        assert post.status_code == 200
        waiter.join(timeout=5.0)
        assert answered, "the held request must end when the decision was answered"
        page = answered["page"]
        assert isinstance(page, dict)
        assert page["revision"] != revision
        assert time.monotonic() - sent < 3.0 and float(answered["took"]) < 5.0  # type: ignore[arg-type]
        assert _FakeInteractiveClient.SECRET_CARD not in json.dumps(
            page
        )  # hidden info (AGENTS.md section 5)
        # Follow the game the way the page does: ask again with the last revision until the next
        # decision of the human is there, always from the number of frames already held.
        held = list(page["frames"])  # type: ignore[arg-type]
        last = page
        for _ in range(20):
            pending = last.get("pending_decision")
            if isinstance(pending, dict) and pending.get("decision_id") == "dec-h-2":
                break
            last, _took = _held_get(
                client,
                "held-1",
                start=len(held),
                since=int(last["revision"]),
                wait_ms=2000,  # type: ignore[call-overload]
            )
            held.extend(last["frames"])  # type: ignore[arg-type]
        assert isinstance(last["pending_decision"], dict)
        assert last["pending_decision"]["decision_id"] == "dec-h-2"
        assert _FakeInteractiveClient.SECRET_CARD not in json.dumps(last)
        # No frame lost or doubled by the held requests.
        full = client.get("/api/play/held-1").json()
        assert held == full["frames"]
    finally:
        app.state.play_manager.shutdown_all()  # type: ignore[attr-defined]


def test_a_held_state_request_without_change_times_out_with_the_same_state(
    tmp_path: Path,
) -> None:
    app, client = _start_fake_session(tmp_path, "held-2", _FakeInteractiveClient())
    try:
        first = _wait_for_pending(client, "held-2", "dec-h-1")
        page, took = _held_get(
            client,
            "held-2",
            start=0,
            since=int(first["revision"]),
            wait_ms=300,  # type: ignore[call-overload]
        )
        assert 0.25 <= took < 2.0
        assert page["revision"] == first["revision"]
        assert page["pending_decision"] == first["pending_decision"]
        # A stale revision, no revision, and an unknown game never wait.
        stale, took = _held_get(client, "held-2", start=0, since=0, wait_ms=6000)
        assert took < 1.0 and stale["revision"] == first["revision"]
        plain, took = _held_get(client, "held-2", start=0, since=None, wait_ms=6000)
        assert took < 1.0 and "revision" in plain
        assert client.get("/api/play/held-2?since=-1&wait_ms=10").status_code == 422
        assert client.get("/api/play/nope?since=1&wait_ms=10").status_code == 404
    finally:
        app.state.play_manager.shutdown_all()  # type: ignore[attr-defined]


def test_a_held_state_request_is_capped_and_never_waits_on_a_finished_game(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(play, "MAX_LONG_POLL_SECONDS", 0.2)
    app, client = _start_fake_session(tmp_path, "held-3", _FakeInteractiveClient())
    try:
        first = _wait_for_pending(client, "held-3", "dec-h-1")
        _page, took = _held_get(
            client,
            "held-3",
            start=0,
            since=int(first["revision"]),
            wait_ms=60_000,  # type: ignore[call-overload]
        )
        assert 0.15 <= took < 2.0  # the server cap, not the 60 s asked for
        assert client.post("/api/play/held-3/concede", json={}).status_code == 200
        done = _wait_finished(client, "held-3")
        again, took = _held_get(
            client, "held-3", start=0, since=int(done["revision"]), wait_ms=6000
        )  # type: ignore[call-overload]
        assert took < 1.0 and again["running"] is False
    finally:
        app.state.play_manager.shutdown_all()  # type: ignore[attr-defined]


def test_revision_moves_with_every_visible_change_and_only_then(tmp_path: Path) -> None:
    app, client = _start_fake_session(tmp_path, "rev-1", _FakeInteractiveClient())
    try:
        first = _wait_for_pending(client, "rev-1", "dec-h-1")
        same = client.get("/api/play/rev-1").json()
        assert same["revision"] == first["revision"]  # reading and speed changes are no change
        assert client.post("/api/play/rev-1/speed", json={"ai_delay_ms": 0}).status_code == 200
        assert client.get("/api/play/rev-1").json()["revision"] == first["revision"]
        client.post(
            "/api/play/rev-1/decision",
            json={"decision_id": "dec-h-1", "selected_option_ids": ["pass-1"], "ordering": []},
        )
        second = _wait_for_pending(client, "rev-1", "dec-h-2")
        assert int(second["revision"]) > int(first["revision"])  # type: ignore[call-overload]
    finally:
        app.state.play_manager.shutdown_all()  # type: ignore[attr-defined]


_FOLLOW_PRELUDE = "const F = require('./follow.js');"


def test_follow_module_holds_requests_and_falls_back_to_the_fixed_intervals() -> None:
    script = (
        _FOLLOW_PRELUDE
        + """
const base = {interactive: true, fastForward: false, hasPendingDecision: false, revision: 5,
  failed: false, held: true, changed: true, elapsedMs: 3000};
const delay = (over) => F.nextDelayMs(Object.assign({}, base, over));
console.log(JSON.stringify({
  heldChanged: delay({}),
  heldTimedOut: delay({changed: false, elapsedMs: 8000}),
  rateLimited: delay({elapsedMs: 5}),
  instantUnchanged: delay({changed: false, elapsedMs: 3}),
  instantUnchangedFf: delay({changed: false, elapsedMs: 3, fastForward: true}),
  instantUnchangedPending: delay({changed: false, elapsedMs: 3, hasPendingDecision: true}),
  firstAsk: delay({held: false, elapsedMs: 0}),
  failedPlain: delay({failed: true}),
  failedPending: delay({failed: true, hasPendingDecision: true}),
  failedFf: delay({failed: true, fastForward: true}),
  noRevision: delay({revision: null, held: false}),
  watching: delay({interactive: false}),
  path: F.statePath('g 1', 7, true, 5, true),
  pathNoHold: F.statePath('g 1', 7, true, 5, false),
  pathNoRevision: F.statePath('g 1', 7, true, null, true),
  pathWatching: F.statePath('g1', 0, false, 5, true),
  revisions: [F.parseRevision({revision: 0}), F.parseRevision({revision: 4}), F.parseRevision({}),
    F.parseRevision({revision: '4'}), F.parseRevision({revision: -1}), F.parseRevision(null)]
}));
"""
    )
    out = _node_json(script)
    assert isinstance(out, dict)
    assert out["heldChanged"] == 0 and out["heldTimedOut"] == 0
    assert out["rateLimited"] == 35  # at most about 25 held requests a second while the AI plays
    # the fixed intervals of before (400 ms, 1.5 s with an open decision, 150 ms fast-forward)
    assert out["instantUnchanged"] == 400 and out["instantUnchangedPending"] == 1500
    assert out["instantUnchangedFf"] == 150
    assert out["failedPlain"] == 400 and out["failedPending"] == 1500 and out["failedFf"] == 150
    assert out["firstAsk"] == 0 and out["noRevision"] == 400 and out["watching"] == 2000
    assert out["path"] == "/api/play/g%201?start=7&count=1000&since=5&wait_ms=8000"
    assert out["pathNoHold"] == "/api/play/g%201?start=7&count=1000"
    assert out["pathNoRevision"] == "/api/play/g%201?start=7&count=1000"
    assert out["pathWatching"] == "/api/games/g1?start=0&count=1000"
    assert out["revisions"] == [0, 4, None, None, None, None]


def test_partie_page_follows_with_held_requests_and_no_second_loop() -> None:
    html = (STATIC / "partie.html").read_text(encoding="utf-8")
    js = (STATIC / "partie.js").read_text(encoding="utf-8")
    follow_js = (STATIC / "follow.js").read_text(encoding="utf-8")
    assert html.index('src="follow.js"') < html.index('src="partie.js"')
    # the fixed 400/1500/150 ms intervals live in one place (follow.js), not in the page
    for interval in ("? 1500 : 400", "? 150 :"):
        assert interval not in js
    assert "StudioFollow.nextDelayMs(" in js and "StudioFollow.statePath(" in js
    # one follow loop at a time: a newer loop ends the older one and its held request
    assert "state.followGen += 1" in js and "generation !== state.followGen" in js
    assert "abortHeldRequest()" in js and "new AbortController()" in js
    # a failed request keeps the banner and the fixed intervals; frames are asked from what is held
    assert "showConnectionLost(state.pollFailures, error.message)" in js
    assert "start=${start}" in follow_js
    for forbidden in (
        "innerHTML",
        "outerHTML",
        "style=",
        "document.",
        "window.",
        "fetch(",
        "eval(",
    ):
        assert forbidden not in follow_js, forbidden
    paths = sorted(set(re.findall(r"/api/[a-z0-9_/${}()?=&.-]+", follow_js, re.IGNORECASE)))
    assert paths and all(p.startswith(("/api/games/", "/api/play/")) for p in paths), paths


# ---- snapshot() copies nothing and redacts nothing a second time (#1578) -----------------------


def _snapshot_as_before(
    session: play.InteractiveGameSession, start: int, count: int
) -> dict[str, object]:
    """The answer the snapshot gave before #1578: deep copies and a second redaction."""
    with session._lock:
        revealed = not session._running and session._result is not None
        source = session._raw_frames if revealed else session._frames
        pending = copy.deepcopy(session._pending_decision)
        if isinstance(pending, dict):
            raw_state = pending.get("pilot_state")
            if isinstance(raw_state, dict):
                pending["pilot_state"] = games.redact_pilot_state_for_human_seats(
                    raw_state, session.human_seats
                )
        return {
            "game_id": session.game_id,
            "interactive": True,
            "running": session._running,
            "revision": session._revision,
            "header": copy.deepcopy(session.prepared.header),
            "human_seats": sorted(session.human_seats),
            "decision_timeout_seconds": session.decision_timeout_seconds,
            "ai_delay_ms": session.ai_delay_ms,
            "can_concede": any(
                session._can_concede_by_seat.get(s, False) for s in session.human_seats
            )
            and session._running,
            "pending_decision": pending,
            "frames": [copy.deepcopy(f) for f in source[start : start + count]],
            "start": start,
            "total": len(session._frames),
            "hands_revealed": revealed,
            "forced_passes_answered_by_engine": session._forced_passes_answered,
            "result": copy.deepcopy(session._result),
        }


def _dump(value: object) -> str:
    return json.dumps(value, sort_keys=True)


def _answer_pass(client: TestClient, game_id: str, decision_id: str) -> None:
    posted = client.post(
        f"/api/play/{game_id}/decision",
        json={"decision_id": decision_id, "selected_option_ids": ["pass-1"], "ordering": []},
    )
    assert posted.status_code == 200


def test_snapshot_gives_the_same_answer_with_no_copy_and_no_second_redaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, client = _start_fake_session(tmp_path, "snap-1", _FakeInteractiveClient())
    session = app.state.play_manager.get("snap-1")  # type: ignore[attr-defined]
    try:
        _wait_for_pending(client, "snap-1", "dec-h-1")
        _answer_pass(client, "snap-1", "dec-h-1")
        _wait_for_pending(client, "snap-1", "dec-h-2")
        # The game waits for the human now: nothing else touches the state while this runs.
        calls = {"copy": 0, "redact": 0}
        real_redact = games.redact_pilot_state_for_human_seats

        def counting_copy(value: object, *args: object, **kwargs: object) -> object:
            calls["copy"] += 1
            return copy.deepcopy(value, *args, **kwargs)  # type: ignore[arg-type]

        def counting_redact(*args: object, **kwargs: object) -> dict[str, object]:
            calls["redact"] += 1
            return real_redact(*args, **kwargs)  # type: ignore[arg-type]

        fake_copy = type("FakeCopyModule", (), {"deepcopy": staticmethod(counting_copy)})
        monkeypatch.setattr(play, "copy", fake_copy)
        monkeypatch.setattr(play, "redact_pilot_state_for_human_seats", counting_redact)
        views = [session.snapshot(start=0, count=200) for _ in range(5)]
        views.append(session.snapshot(start=1, count=1))
        monkeypatch.undo()
        assert calls == {"copy": 0, "redact": 0}, calls
        # Same answer as before the change, for the whole range and for a slice.
        assert _dump(views[0]) == _dump(_snapshot_as_before(session, 0, 200))
        assert _dump(views[-1]) == _dump(_snapshot_as_before(session, 1, 1))
        pending = views[0]["pending_decision"]
        assert isinstance(pending, dict) and pending["decision_id"] == "dec-h-2"
        assert views[0]["frames"], "the answered decision is a frame"
        assert _FakeInteractiveClient.SECRET_CARD not in _dump(views[0])  # hidden info (section 5)
        # The route answer is the same too.
        routed = client.get("/api/play/snap-1").json()
        assert _dump(routed) == _dump(_snapshot_as_before(session, 0, 200))
    finally:
        app.state.play_manager.shutdown_all()  # type: ignore[attr-defined]


def test_snapshot_taken_earlier_stays_as_it_was_when_the_game_moves_on(tmp_path: Path) -> None:
    """Without copies the answers share the state: nothing may change under a held answer."""
    app, client = _start_fake_session(tmp_path, "snap-2", _FakeInteractiveClient())
    session = app.state.play_manager.get("snap-2")  # type: ignore[attr-defined]
    try:
        _wait_for_pending(client, "snap-2", "dec-h-1")
        early = session.snapshot()
        early_text = _dump(early)
        _answer_pass(client, "snap-2", "dec-h-1")
        _wait_for_pending(client, "snap-2", "dec-h-2")
        assert _dump(early) == early_text
        mid = session.snapshot()
        mid_text = _dump(mid)
        assert mid["frames"], "the held answer must carry frames for this check"
        # One more decision is recorded (review of #1644): the frames delivered earlier must not
        # change under the held answer. The fake offers ``dec-h-2`` again after this answer, so the
        # wait is on the frame count, not on the decision id.
        answered = client.post(
            "/api/play/snap-2/decision",
            json={"decision_id": "dec-h-2", "selected_option_ids": ["tgt-1"], "ordering": []},
        )
        assert answered.status_code == 200
        deadline = time.monotonic() + 5.0
        while session.snapshot()["total"] < 3 and time.monotonic() < deadline:
            time.sleep(0.02)
        assert session.snapshot()["total"] == 3
        assert _dump(mid) == mid_text and _dump(early) == early_text
        assert client.post("/api/play/snap-2/concede", json={}).status_code == 200
        done = _wait_finished(client, "snap-2")
        assert _dump(mid) == mid_text and _dump(early) == early_text
        # After the game the hands of the AI seats are shown, as before (Owner decision 2026-11-17).
        assert done["hands_revealed"] is True
        assert _dump(session.snapshot()) == _dump(_snapshot_as_before(session, 0, 200))
    finally:
        app.state.play_manager.shutdown_all()  # type: ignore[attr-defined]


# ---- POST /decision carries the state, the page draws only what changed (#1578 P-B) -------------


class _EndingFakeClient(_FakeInteractiveClient):
    """The second answer of the human ends the game (the engine reports it as terminal)."""

    def _status(self) -> dict[str, object]:
        if self.phase >= 3:
            self.conceded = True
        return super()._status()


def _post_answer(
    client: TestClient, game_id: str, decision_id: str, option: str, start: int | None
) -> dict[str, object]:
    body: dict[str, object] = {
        "decision_id": decision_id,
        "selected_option_ids": [option],
        "ordering": [],
    }
    if start is not None:
        body["start"] = start
    posted = client.post(f"/api/play/{game_id}/decision", json=body)
    assert posted.status_code == 200, posted.text
    answer = posted.json()
    assert isinstance(answer, dict)
    return answer


def test_post_decision_with_start_carries_the_get_state_and_no_hidden_card(tmp_path: Path) -> None:
    app, client = _start_fake_session(tmp_path, "post-1", _FakeInteractiveClient())
    try:
        _wait_for_pending(client, "post-1", "dec-h-1")
        # Without ``start`` the answer is the one of before: only the acceptance.
        plain_app, plain_client = _start_fake_session(
            tmp_path / "plain", "post-plain", _FakeInteractiveClient()
        )
        try:
            _wait_for_pending(plain_client, "post-plain", "dec-h-1")
            assert _post_answer(plain_client, "post-plain", "dec-h-1", "pass-1", None) == {
                "accepted": True
            }
        finally:
            plain_app.state.play_manager.shutdown_all()  # type: ignore[attr-defined]

        first = _post_answer(client, "post-1", "dec-h-1", "pass-1", 0)
        assert first["accepted"] is True
        state = first["state"]
        assert isinstance(state, dict)
        assert state["game_id"] == "post-1" and state["start"] == 0
        assert state["hands_revealed"] is False and state["running"] is True
        assert type(state["revision"]) is int
        # Hidden information (AGENTS.md section 5): the hand of the AI seat appears nowhere in the
        # answer of a running game, neither in the frames nor in an open decision.
        assert _FakeInteractiveClient.SECRET_CARD not in json.dumps(first)
        parked = _wait_for_pending(client, "post-1", "dec-h-2")
        held = int(parked["total"])  # type: ignore[call-overload]
        assert held == 2

        # The game waits for the human again after this answer (the fake offers dec-h-2 once
        # more), so the state sent with the answer and a GET right after must be byte-equal.
        second = _post_answer(client, "post-1", "dec-h-2", "tgt-1", held)
        get = client.get(f"/api/play/post-1?start={held}&count=1000").json()
        assert _dump(second["state"]) == _dump(get)
        sent = second["state"]
        assert isinstance(sent, dict)
        assert sent["start"] == held and sent["total"] == 3 and len(sent["frames"]) == 1
        assert sent["revision"] > state["revision"]
        assert _FakeInteractiveClient.SECRET_CARD not in json.dumps(second)
        pending = sent["pending_decision"]
        assert isinstance(pending, dict) and pending["decision_id"] == "dec-h-2"
        assert "hand" not in pending["pilot_state"]["players"][1]
        # A refused answer sends no state at all.
        refused = client.post(
            "/api/play/post-1/decision",
            json={"decision_id": "stale", "selected_option_ids": ["tgt-1"], "start": 0},
        )
        assert refused.status_code == 422 and "state" not in refused.json()
        bad_start = client.post(
            "/api/play/post-1/decision",
            json={"decision_id": "dec-h-2", "selected_option_ids": ["tgt-1"], "start": -1},
        )
        assert bad_start.status_code == 422
    finally:
        app.state.play_manager.shutdown_all()  # type: ignore[attr-defined]


def test_post_decision_that_ends_the_game_reveals_only_with_the_closing_result(
    tmp_path: Path,
) -> None:
    app, client = _start_fake_session(tmp_path, "post-end", _EndingFakeClient())
    try:
        _wait_for_pending(client, "post-end", "dec-h-1")
        _post_answer(client, "post-end", "dec-h-1", "pass-1", 0)
        _wait_for_pending(client, "post-end", "dec-h-2")
        last = _post_answer(client, "post-end", "dec-h-2", "tgt-1", 0)
        state = last["state"]
        assert isinstance(state, dict)
        # Owner decision 2026-11-17: the AI hands are shown once the game has its closing result,
        # never before. The answer follows the same rule as the GET.
        revealed = state["running"] is False and state["result"] is not None
        assert state["hands_revealed"] is revealed
        if not revealed:
            assert _FakeInteractiveClient.SECRET_CARD not in json.dumps(last)
        assert state["pending_decision"] is None
        done = _wait_finished(client, "post-end")
        assert done["hands_revealed"] is True
        assert _FakeInteractiveClient.SECRET_CARD in json.dumps(done["frames"])
    finally:
        app.state.play_manager.shutdown_all()  # type: ignore[attr-defined]


def test_follow_module_view_key_and_prefetched_state() -> None:
    script = (
        _FOLLOW_PRELUDE
        + """
const view = {gameId: 'g', revision: 4, frames: 10, index: 9, running: true, interactive: true,
  pendingDecisionId: 'd1', handsRevealed: false, canConcede: true, resultStatus: null,
  fastForward: false, autoPassAttempt: null, submitting: false, playing: false};
const key = F.viewKey(view);
const changes = {revision: 5, frames: 11, index: 3, running: false, interactive: false,
  pendingDecisionId: 'd2', handsRevealed: true, canConcede: false, resultStatus: 'finished',
  fastForward: true, autoPassAttempt: 'd1', submitting: true, playing: true, gameId: 'h'};
const differs = {};
for (const [field, value] of Object.entries(changes)) {
  differs[field] = F.viewKey(Object.assign({}, view, {[field]: value})) !== key;
}
const page = {game_id: 'g', start: 10, frames: [], revision: 7};
const use = (over, gameId, held, revision) => F.usableAnswerState(Object.assign({}, page, over), gameId, held, revision);
console.log(JSON.stringify({
  same: F.viewKey(Object.assign({}, view)) === key,
  differs,
  prefetch: {
    ok: use({}, 'g', 10, 7), newer: use({}, 'g', 10, 6), unknownHeld: use({}, 'g', 10, null),
    otherGame: use({}, 'h', 10, 7), otherStart: use({}, 'g', 9, 7), older: use({}, 'g', 10, 8),
    noRevision: use({revision: undefined}, 'g', 10, null), noFrames: use({frames: undefined}, 'g', 10, 7),
    none: F.usableAnswerState(null, 'g', 10, 7), missing: F.usableAnswerState(undefined, 'g', 10, 7)
  }
}));
"""
    )
    out = _node_json(script)
    assert isinstance(out, dict)
    assert out["same"] is True
    assert out["differs"] == {field: True for field in out["differs"]} and len(out["differs"]) == 14
    assert out["prefetch"] == {
        "ok": True,
        "newer": True,
        "unknownHeld": True,
        "otherGame": False,
        "otherStart": False,
        "older": False,
        "noRevision": False,
        "noFrames": False,
        "none": False,
        "missing": False,
    }


_SUBMIT_PRELUDE = f"""
const F = require('./follow.js');
const P1a = require('./play_p1a.js');
const SRC = require('fs').readFileSync({json.dumps((STATIC / "partie.js").as_posix())}, 'utf8');
const grab = (name) => {{
  const start = SRC.indexOf('function ' + name + '(');
  if (start < 0) throw new Error('missing ' + name);
  let depth = 0, i = SRC.indexOf('{{', start);
  for (; i < SRC.length; i += 1) {{ if (SRC[i] === '{{') depth += 1; else if (SRC[i] === '}}' && --depth === 0) break; }}
  const head = SRC.lastIndexOf('async ', start) === start - 6 ? 'async ' : '';
  return head + SRC.slice(start, i + 1);
}};
const NAMES = ['submitHumanChoice', 'loadMore', 'abortHeldRequest', 'loadMoreOnce', 'render', 'viewState',
  'followTick'];
const pending = (id) => ({{decision_id: id, seat: 0, decision_class: 'priority',
  legal_options: [{{option_id: 'pass-' + id, option_type: 'pass_priority', label: 'Pass'}}],
  pilot_state: {{turn_number: 3, players: []}}}});
const frame = (n) => ({{n, seat: 1, players: []}});
// reply(body) builds what the server answers the POST; gets(path) what a state request returns
async function run(opts) {{
  const calls = {{requests: [], renders: 0, follows: 0, toasts: [], followWhileSending: []}};
  const state = {{gameId: 'g', interactive: true, running: true, revision: 4, frames: [frame(1), frame(2)],
    index: 1, pendingDecision: pending('d1'), selectedOptions: [], orderList: [], submitting: false,
    ff: {{on: false}}, autoPassAttempt: null, foreground: 0, pollAbort: null, followGen: 0, poll: 0,
    pollFailures: 0, playing: false, handsRevealed: false, canConcede: true, result: null, renderedKey: null,
    ownCombat: P1a.emptyCombatLedger(), humanSeats: [0], header: {{}}}};
  const api = async (path, method, body) => {{
    calls.requests.push({{method, path, body: body || null}});
    if (method === 'POST') return opts.reply(body, state);
    return opts.get(path, state);
  }};
  const body = 'let loadTail = Promise.resolve();\\n' + NAMES.map(grab).join('\\n');
  const make = new Function('state', 'api', 'StudioPlayP1a', 'StudioFollow', 'calls', '$', 'ffStatus',
    'renderHumanDecision', 'appendAutoPassLog', 'toast', 'endFastForward', 'go', 'follow', 'renderView',
    'adoptPendingDecision', 'loadFacts', 'appendLog', 'resetFrames', 'armFollow', 'showConnectionLost',
    'refreshTitles', 'performance',
    body + '; return {{' + NAMES.join(',') + '}};');
  const fns = make(state, api, P1a, F, calls, () => ({{max: '0'}}), () => {{}}, () => {{}}, () => {{}},
    (text) => calls.toasts.push(text), () => {{}}, (i) => {{ state.index = i; fns.render(); }},
    () => {{ calls.follows += 1; calls.followWhileSending.push(state.submitting); }},
    () => {{ calls.renders += 1; if (opts.onRender) opts.onRender(state, fns); }},
    (next) => {{ state.pendingDecision = next; }}, async () => {{}}, () => {{}}, () => {{}}, () => {{}},
    () => {{}}, () => {{}}, {{now: () => 0}});
  return {{state, calls, fns}};
}}
const parked = (state, start, extra) => Object.assign({{game_id: 'g', interactive: true, running: true,
  revision: 6, header: {{}}, human_seats: [0], pending_decision: pending('d2'), can_concede: true,
  hands_revealed: false, result: null, frames: [frame(3)], start, total: 3}}, extra || {{}});
"""


def test_page_answer_takes_the_state_from_the_post_and_asks_again_only_when_unusable() -> None:
    script = (
        _SUBMIT_PRELUDE
        + """
(async () => {
  const rows = {};
  const variants = {
    usable: (body, state) => ({accepted: true, state: parked(state, body.start)}),
    noState: () => ({accepted: true}),
    otherGame: (body, state) => ({accepted: true, state: parked(state, body.start, {game_id: 'other'})}),
    otherStart: (body, state) => ({accepted: true, state: parked(state, body.start + 1)}),
    older: (body, state) => ({accepted: true, state: parked(state, body.start, {revision: 3})}),
  };
  for (const [name, reply] of Object.entries(variants)) {
    const page = await run({reply, get: (path, state) => parked(state, state.frames.length)});
    await page.fns.submitHumanChoice({decision_id: 'd1', selected_option_ids: ['pass-d1'], ordering: []}, {});
    rows[name] = {
      requests: page.calls.requests.map((r) => r.method + ' ' + r.path),
      body: page.calls.requests[0].body,
      frames: page.state.frames.map((f) => f.n), pending: page.state.pendingDecision.decision_id,
      revision: page.state.revision, follows: page.calls.follows, submitting: page.state.submitting,
      followGen: page.state.followGen
    };
  }
  // a refused answer: no state, one plain reload, the follow loop starts again
  const refused = await run({reply: () => { const e = new Error('stale'); e.status = 422; throw e; },
    get: (path, state) => parked(state, state.frames.length)});
  await refused.fns.submitHumanChoice({decision_id: 'd1', selected_option_ids: ['pass-d1'], ordering: []}, {});
  rows.refused = {requests: refused.calls.requests.map((r) => r.method + ' ' + r.path),
    follows: refused.calls.follows, toasts: refused.calls.toasts.length};
  console.log(JSON.stringify(rows));
})();
"""
    )
    out = _node_json(script)
    assert isinstance(out, dict)
    post = "POST /api/play/g/decision"
    plain = "GET /api/play/g?start=2&count=1000"
    usable = out["usable"]
    # one request per answer: the state came with the acceptance, no state request follows
    assert usable["requests"] == [post]
    assert usable["body"] == {
        "decision_id": "d1",
        "selected_option_ids": ["pass-d1"],
        "ordering": [],
        "start": 2,
    }
    assert usable["frames"] == [1, 2, 3] and usable["pending"] == "d2" and usable["revision"] == 6
    assert usable["follows"] == 1 and usable["submitting"] is False
    assert usable["followGen"] == 1  # the follow loop was stopped before the post
    # every unusable state: exactly one plain request, as before, with the same result
    for name in ("noState", "otherGame", "otherStart", "older"):
        row = out[name]
        assert row["requests"] == [post, plain], name
        assert row["frames"] == [1, 2, 3] and row["pending"] == "d2", name
        assert row["follows"] == 1, name
    refused = out["refused"]
    assert refused["requests"] == [post, plain] and refused["follows"] == 1
    assert refused["toasts"] == 1


def test_follow_tick_draws_only_when_the_view_changed() -> None:
    script = (
        _SUBMIT_PRELUDE
        + """
(async () => {
  const rows = {};
  const tick = async (name, get, prepare, drawn) => {
    const page = await run({reply: () => ({}), get});
    page.state.index = 0;            // the viewer looks at an earlier frame (no jump to the end)
    if (drawn) drawn(page.state);
    page.fns.render();               // the drawing the page holds
    if (prepare) prepare(page.state);
    const before = page.calls.renders;
    await page.fns.followTick(page.state.followGen);
    rows[name] = page.calls.renders - before;
  };
  const same = (path, state) => parked(state, state.frames.length,
    {revision: state.revision, frames: [], total: state.frames.length, pending_decision: state.pendingDecision});
  await tick('unchanged', same);
  await tick('revision', (path, state) => Object.assign(same(path, state), {revision: state.revision + 1}));
  await tick('decision', (path, state) => Object.assign(same(path, state), {pending_decision: pending('d9')}));
  await tick('ended', (path, state) => Object.assign(same(path, state), {running: false}));
  await tick('frames', (path, state) => parked(state, state.frames.length, {revision: state.revision}));
  // fast-forward stopped and its pass attempt cleared since the last drawing: draw again
  await tick('ffStopped', same, (state) => { state.autoPassAttempt = null; state.ff = {on: false}; },
    (state) => { state.autoPassAttempt = 'd1'; state.ff = {on: true}; });
  // only fast-forward was switched off (no pass attempt pending): draw again as well
  await tick('ffOnly', same, (state) => { state.ff = {on: false}; }, (state) => { state.ff = {on: true}; });
  // only the pass attempt was cleared (fast-forward was already off): draw again as well
  await tick('passCleared', same, (state) => { state.autoPassAttempt = null; },
    (state) => { state.autoPassAttempt = 'd1'; });
  console.log(JSON.stringify(rows));
})();
"""
    )
    out = _node_json(script)
    assert out == {
        "unchanged": 0,
        "revision": 1,
        "decision": 1,
        "ended": 1,
        "frames": 1,
        "ffStopped": 1,
        "passCleared": 1,
        "ffOnly": 1,
    }


def test_fast_forward_chain_sends_one_request_per_pass_and_follows_only_at_its_end() -> None:
    script = (
        _SUBMIT_PRELUDE
        + """
(async () => {
  // fast-forward: the drawing after an accepted pass sends the next pass at once (as
  // maybeAutoPassHuman does); the follow loop must stay off until the last answer is done
  let nested = null;
  const replies = {d1: 'd2', d2: 'd3'};
  const page = await run({
    reply: (body, state) => ({accepted: true, state: Object.assign(parked(state, body.start), {
      pending_decision: pending(replies[body.decision_id]), revision: state.revision + 1,
      total: state.frames.length + 1, frames: [frame(state.frames.length + 1)]})}),
    get: (path, state) => parked(state, state.frames.length),
    onRender: (state, fns) => {
      if (!state.submitting && !nested && state.pendingDecision.decision_id === 'd2') {
        nested = fns.submitHumanChoice({decision_id: 'd2', selected_option_ids: ['pass-d2'], ordering: []}, {});
      }
    }
  });
  await page.fns.submitHumanChoice({decision_id: 'd1', selected_option_ids: ['pass-d1'], ordering: []}, {});
  await nested;
  console.log(JSON.stringify({
    requests: page.calls.requests.map((r) => r.method + ' ' + r.path),
    starts: page.calls.requests.map((r) => r.body && r.body.start),
    follows: page.calls.follows, whileSending: page.calls.followWhileSending,
    frames: page.state.frames.map((f) => f.n), pending: page.state.pendingDecision.decision_id
  }));
})();
"""
    )
    out = _node_json(script)
    assert isinstance(out, dict)
    post = "POST /api/play/g/decision"
    assert out["requests"] == [post, post]  # two passes, two requests, no state request between
    assert out["starts"] == [2, 3]
    assert out["follows"] == 1 and out["whileSending"] == [False]
    assert out["frames"] == [1, 2, 3, 4] and out["pending"] == "d3"
