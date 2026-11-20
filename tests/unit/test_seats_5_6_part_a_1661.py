"""Five and six seats, part A (#1661): what can be shown without the real engine.

The release itself is not here: ``launch.MAX_RELEASED_SEATS`` stays 4 and the page offers two to
four players. These tests show that (a) a running game never hands a hidden card of another seat
to the human at five or six seats, wherever the human sits (F4), (b) the Studio side of the eight
rule points of ``docs/research/SEATS_5_6_QUALIFICATION_PLAN.md`` section 2 carries five and six
seats (F5: interface only; the rules themselves are XMage's and need real games, part B), (c) the
paired series plans a full seat rotation at five and six seats and censors failed games loudly
(F8 planning), and (d) the play page draws five and six seats once the lock is lifted, and the
lock is the only hurdle on the play route.

Since #1702 the file also holds the SIMULATE way for five and six seats behind the same lock:
pod presets per table size (an error, never a fill), the series route with ``table_seats``
(refused without the switch; with the lock raised in memory it plans and plays the full rotation
through a recording ``play_override`` in place of the bridge), the resume at the stored size, the
table-size stratum of the card evaluation, and the series dialog (``paired.js``) under node with a
DOM stand-in.

All data is synthetic; the bridge is a scripted test bridge. Report:
``docs/analysis-reports/seats_5_6_part_a_report.md``.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import subprocess
import time
from collections import Counter
from collections.abc import Callable, Iterable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.engine.rules.full_game import (
    FULL_GAME_DECISION_PROTOCOL_VERSION,
    FULL_GAME_EVIDENCE_CLASS,
    FULL_GAME_LANE,
)
from commander_lab.engine.rules.full_game_comparison import pod_decks
from commander_lab.models import RulesDeckInput
from commander_lab.qualification.current_boundary.bridge_launcher import canonical_xmage_engine_pin
from commander_lab.studio import games, launch, play
from commander_lab.studio.card_outcomes import game_exposures
from commander_lab.studio.paired_comparison import PlayedGame, run_comparison_series
from commander_lab.studio.web import STATIC, create_app

ROOT = Path(__file__).resolve().parents[2]
COMMANDERS = (
    "Chulane, Teller of Tales",
    "Kinnan, Bonder Prodigy",
    "Atraxa, Praetors' Voice",
    "Tatyova, Benthic Druid",
    "Muldrotha, the Gravetide",
    "Aesi, Tyrant of Gyre Strait",
)
#: seed 9 starts the game at seat 9 % 5 = 4 (Sitz 5) and 9 % 6 = 3 (Sitz 4): not at seat 0
SEED = 9


def _secret(seat: int) -> str:
    """The hidden hand card of one seat, named after the seat a person reads (Sitz = seat + 1)."""
    return f"SECRET-HAND-SITZ-{seat + 1}"


def _context_secret(seat: int) -> str:
    return f"SECRET-CONTEXT-SITZ-{seat + 1}"


def _deck(seat: int) -> RulesDeckInput:
    return play._with_hash(
        RulesDeckInput(
            deck_id=f"deck-sitz-{seat + 1}",
            name=f"deck-sitz-{seat + 1}",
            deck_hash=None,
            commander_names=(COMMANDERS[seat],),
            mainboard=tuple(["Forest"] * 49 + ["Island"] * 50),
            sideboard=(),
        )
    )


def _decks(count: int) -> tuple[RulesDeckInput, ...]:
    return tuple(_deck(seat) for seat in range(count))


def _pilot_state(
    count: int, *, actor: int, active: int, turn: int, out: frozenset[int] = frozenset()
) -> dict[str, object]:
    """What the engine publishes at a decision: every seat's hand, hidden or not, as the bridge
    hands it to Python (the redaction is the Studio's job)."""
    players: list[dict[str, object]] = []
    for seat in range(count):
        players.append(
            {
                "seat": seat,
                "player_id": f"p{seat}",
                "life": 0 if seat in out else 40,
                "has_lost": seat in out,
                "hand_count": 2,
                "library_count": 90,
                "hand": [{"name": _secret(seat)}, {"name": "Forest"}],
                "hand_cards": [{"name": _secret(seat)}],
                "battlefield": [],
                "graveyard": [],
                "command": [{"name": COMMANDERS[seat]}],
                "exile": [],
            }
        )
    return {
        "seat": actor,
        "turn_number": turn,
        "phase": "precombat_main",
        "step": "precombat_main",
        "active_player_id": f"p{active}",
        "players": players,
        "stack": [],
    }


class SeatBridge:
    """A scripted bridge for one interactive game of ``count`` seats (2 to 6).

    After ``create_full_game`` it walks ``rounds`` rounds of priority in seat order from the
    starting seat the Studio asked for. The human seat gets two options (pass and casting its own
    hidden card), an AI seat only the pass, so the real pilot cannot choose anything else. Every
    published state carries every seat's hidden hand. ``eliminate`` lists seats that leave after
    the first round (the engine's decision, reported in outcomes and states). The game ends with
    ``winner`` as the only winner, or when the human concedes.
    """

    def __init__(
        self,
        count: int,
        human: int,
        *,
        rounds: int = 2,
        winner: int | None = None,
        eliminate: Iterable[int] = (),
        human_class: str = "priority",
    ) -> None:
        self.count = count
        self.human = human
        self.rounds = rounds
        self.winner = winner if winner is not None else (human + 1) % count
        self.eliminate = frozenset(eliminate)
        self.human_class = human_class
        self.created_payload: dict[str, object] | None = None
        self.imported = 0
        self.steps: list[tuple[int, int]] = []  # (seat, turn)
        self.index = 0
        self.conceded_by: list[str] = []
        self.submitted: list[dict[str, object]] = []

    def __enter__(self) -> SeatBridge:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def _plan(self, start: int) -> None:
        steps: list[tuple[int, int]] = []
        for round_number in range(self.rounds):
            for offset in range(self.count):
                seat = (start + offset) % self.count
                if round_number > 0 and seat in self.eliminate:
                    continue  # the engine removed this seat: it gets no more decisions
                steps.append((seat, round_number * self.count + offset + 1))
        self.steps = steps

    def _out(self) -> frozenset[int]:
        start_of_round_two = sum(1 for _seat, turn in self.steps if turn <= self.count)
        return self.eliminate if self.index >= start_of_round_two else frozenset()

    def _outcomes(self, *, terminal: bool) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        out = self._out()
        for seat in range(self.count):
            row: dict[str, object] = {"seat": seat, "player_id": f"p{seat}", "life": 40}
            if terminal:
                won = not self.conceded_by and seat == self.winner
                if self.conceded_by and seat != self.human:
                    won = seat == self.winner
                row.update(
                    won=won,
                    lost=not won,
                    left=seat in out or (seat == self.human and bool(self.conceded_by)),
                    can_concede=False,
                )
            else:
                row.update(lost=seat in out, left=seat in out, can_concede=seat not in out)
            rows.append(row)
        return rows

    def _decision(self, seat: int, turn: int) -> dict[str, object]:
        state = _pilot_state(
            self.count, actor=seat, active=self.steps[0][0], turn=turn, out=self._out()
        )
        human = seat == self.human
        options: list[dict[str, object]] = [
            {"option_id": f"pass-{self.index}", "option_type": "pass_priority", "label": "Pass"}
        ]
        decision_class = "priority"
        if human:
            decision_class = self.human_class
            if self.human_class == "trigger_order":
                options = [
                    {
                        "option_id": f"trig-{self.index}-{k}",
                        "option_type": "trigger_order",
                        "label": f"Trigger of {COMMANDERS[k]}",
                    }
                    for k in range(self.count)
                ]
            else:
                options.append(
                    {
                        "option_id": f"cast-{self.index}",
                        "option_type": "cast_spell",
                        "label": f"Cast {_secret(seat)}",
                    }
                )
        return {
            "decision_id": f"dec-{self.index}",
            "decision_offset": self.index + 1,
            "actor_id": f"p{seat}",
            "seat": seat,
            "acting_for_seat": seat,
            "decision_class": decision_class,
            "prompt": "Choose an action",
            "minimum_selections": len(options) if decision_class == "trigger_order" else 1,
            "maximum_selections": len(options) if decision_class == "trigger_order" else 1,
            "legal_options": options,
            "context": {"engine_note": _context_secret(seat)},
            "pilot_state": state,
        }

    def _status(self) -> dict[str, object]:
        if self.conceded_by or self.index >= len(self.steps):
            return {"terminal": True, "decision": None, "outcomes": self._outcomes(terminal=True)}
        seat, turn = self.steps[self.index]
        return {
            "terminal": False,
            "outcomes": self._outcomes(terminal=False),
            "decision": self._decision(seat, turn),
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
            self.imported += 1
            return {"deck_handle": {"handle_id": f"handle-{self.imported}"}}
        if method == "create_full_game":
            self.created_payload = dict(payload)
            self._plan(int(str(payload["starting_player_seat"])))
            return {"evidence_class": FULL_GAME_EVIDENCE_CLASS, "holdout_consumed": False}
        if method in {"start_full_game", "get_full_game_decision"}:
            return self._status()
        if method == "get_concede_offer":
            return {"concede_available": not self.conceded_by}
        if method == "submit_concede":
            proposal = payload.get("proposal")
            who = proposal.get("player_id") if isinstance(proposal, dict) else None
            self.conceded_by.append(str(who))
            return self._status()
        if method == "submit_full_game_decision":
            response = payload.get("response")
            if not isinstance(response, dict):
                raise TypeError("response must be a dict")
            self.submitted.append(dict(response))
            self.index += 1
            return self._status()
        if method == "export_event_log":
            return {"events": [{"turn": 1, "text": "Game started"}]}
        if method == "get_full_game_result":
            created = self.created_payload or {}
            return {
                "evidence_class": FULL_GAME_EVIDENCE_CLASS,
                "consumed_gameplay_evidence": False,
                "holdout_consumed": False,
                "official_campaign_eligible": False,
                "rules_authority": "xmage",
                "decision_policy_authority": "commander_lab_external_pilot",
                "bit_exact_replay_validated": False,
                "seed": created.get("seed"),
                "turn_number": max([turn for _seat, turn in self.steps] or [1]),
                "decision_count": len(self.submitted),
                "terminal": True,
                "transcript": [],
                "outcomes": self._outcomes(terminal=True),
            }
        raise AssertionError(f"unexpected bridge method: {method}")


def _leaked(blob: str, count: int, human: int) -> list[str]:
    """The hidden things of other seats found in ``blob`` (an empty list is the PASS)."""
    found: list[str] = []
    for seat in range(count):
        if seat == human:
            continue
        for secret in (_secret(seat), _context_secret(seat)):
            if secret in blob:
                found.append(secret)
    return found


def _start(
    tmp_path: Path, bridge: SeatBridge, game_id: str
) -> tuple[play.InteractivePlayManager, TestClient]:
    app = create_app(tmp_path)
    prepared = play.prepare_game(
        _decks(bridge.count),
        seed=SEED,
        game_id=game_id,
        human_seats=[bridge.human],
        decision_timeout_seconds=0,
        jar_sha256="ab" * 32,
        qualification={"status": "BRIDGE_AHEAD_OF_QUALIFICATION", "covered_by_sealed_epoch": False},
    )
    session = play.InteractiveGameSession(
        tmp_path,
        prepared,
        human_seats=[bridge.human],
        decision_timeout_seconds=0,
        ai_delay_ms=0,
        command=("fake-bridge",),
        client_factory=lambda *_a, **_kw: bridge,
    )
    manager: play.InteractivePlayManager = app.state.play_manager
    with manager._lock:
        manager._sessions[game_id] = session
    session.start()
    return manager, TestClient(app, headers={"X-Studio": "1"})


def _next_state(client: TestClient, game_id: str, seen: set[str]) -> dict[str, object]:
    """The next live state with a new pending decision of the human, or the finished state."""
    deadline = time.monotonic() + 10.0
    snap: dict[str, object] = {}
    while time.monotonic() < deadline:
        snap = client.get(f"/api/play/{game_id}").json()
        pending = snap.get("pending_decision")
        if isinstance(pending, dict) and pending.get("decision_id") not in seen:
            return snap
        if not snap.get("running", True):
            return snap
        time.sleep(0.01)
    raise AssertionError(f"no new state: {snap}")


def play_through(
    tmp_path: Path, bridge: SeatBridge, game_id: str, *, concede_at: int | None = None
) -> tuple[list[str], dict[str, object], list[dict[str, object]]]:
    """Plays the human's decisions through the PLAY routes until the game ends.

    Returns every response body read while the game ran (state, held state, game route, the
    state carried by the answer), the final state, and the human's pending decisions."""
    manager, client = _start(tmp_path, bridge, game_id)
    running_bodies: list[str] = []
    pendings: list[dict[str, object]] = []
    seen: set[str] = set()
    try:
        while True:
            snap = _next_state(client, game_id, seen)
            if not snap.get("running"):
                final = snap
                break
            pending = snap["pending_decision"]
            assert isinstance(pending, dict)
            pendings.append(pending)
            decision_id = str(pending["decision_id"])
            seen.add(decision_id)
            running_bodies.append(json.dumps(snap))
            revision = snap.get("revision")
            held_query = "start=0&wait_ms=0" + (
                f"&since={revision}" if type(revision) is int else ""
            )
            running_bodies.append(client.get(f"/api/play/{game_id}?{held_query}").text)
            running_bodies.append(client.get(f"/api/games/{game_id}").text)
            if concede_at is not None and len(pendings) == concede_at:
                conceded = client.post(f"/api/play/{game_id}/concede", json={})
                assert conceded.status_code == 200, conceded.text
                running_bodies.append(conceded.text)
                continue
            options = pending["legal_options"]
            assert isinstance(options, list)
            ids = [str(option["option_id"]) for option in options]
            body: dict[str, object] = {"decision_id": decision_id, "start": 0}
            if pending.get("decision_class") == "trigger_order":
                body.update(selected_option_ids=[], ordering=list(reversed(ids)))
            else:
                body.update(selected_option_ids=[ids[0]], ordering=[])
            answer = client.post(f"/api/play/{game_id}/decision", json=body)
            assert answer.status_code == 200, answer.text
            carried = answer.json().get("state")
            if isinstance(carried, dict) and carried.get("running") is True:
                running_bodies.append(answer.text)  # the closing state may show all hands
        return running_bodies, final, pendings
    finally:
        manager.shutdown_all()


# ---- F4: hidden information at five and six seats, wherever the human sits ---------------------


@pytest.mark.parametrize(
    ("count", "human"),
    [(5, 0), (5, 4), (6, 0), (6, 4), (6, 5)],
    ids=["5p-sitz1", "5p-sitz5", "6p-sitz1", "6p-sitz5", "6p-sitz6"],
)
def test_f4_no_running_response_carries_a_hidden_card_of_another_seat(
    tmp_path: Path, count: int, human: int
) -> None:
    """AGENTS.md section 5 at five and six seats: while the game runs, no response the page reads
    (state, held state, game route, the state an answer carries) holds a hidden hand card or an
    engine note of another seat. The human's own hand is there (positive control), and after the
    game all hands are shown (Owner decision 2026-11-17), so the secrets were there to leak."""
    bridge = SeatBridge(count, human, rounds=2)
    bodies, final, pendings = play_through(tmp_path, bridge, f"f4-{count}-{human}")

    assert len(pendings) == 2  # two rounds: the human decided twice
    assert len(bodies) >= 3 * len(pendings)
    for body in bodies:
        assert _leaked(body, count, human) == [], body[:400]
    # positive control: the human's own hidden card is shown to the human while the game runs
    own = pendings[0]["pilot_state"]
    assert isinstance(own, dict)
    own_row = next(p for p in own["players"] if p["seat"] == human)
    assert own_row["hand"][0]["name"] == _secret(human)
    for row in own["players"]:
        if row["seat"] != human:
            assert "hand" not in row and "hand_cards" not in row, row
    assert any(_secret(human) in body for body in bodies)
    # every seat played: frames of all five or six seats were recorded while the game ran
    assert sorted({seat for seat, _turn in bridge.steps}) == list(range(count))
    assert final["running"] is False and final["hands_revealed"] is True
    revealed = json.dumps(final["frames"])
    for seat in range(count):
        assert _secret(seat) in revealed, seat
    assert final["result"]["status"] == "finished"


@pytest.mark.parametrize("count", [5, 6])
def test_f4_hidden_pick_of_ai_seat_five_or_six_stays_hidden_while_running(
    tmp_path: Path, count: int
) -> None:
    """A card an AI seat at Sitz 5 or Sitz 6 takes from a hidden zone (a bottom pick, a tutor)
    keeps its name hidden from the human until the game has ended."""
    prep = play.prepare_game(
        _decks(count), seed=SEED, game_id="f4-pick", human_seats=[0], decision_timeout_seconds=0
    )
    recorder = games.GameRecorder(tmp_path, "f4-pick", prep.header)
    for seat in range(1, count):
        recorder.record(
            {
                "seat": seat,
                "decision_class": "choose_object",
                "prompt": "Put a card on the bottom",
                "context": {"bottom_of_library_selection": True},
                "legal_options": [{"option_id": f"c{seat}", "label": _secret(seat)}],
                "pilot_state": _pilot_state(count, actor=seat, active=seat, turn=1),
            },
            {"selected_option_ids": [f"c{seat}"]},
        )
    running = games.read_game(tmp_path, "f4-pick")
    assert running["running"] is True and len(running["frames"]) == count - 1
    assert _leaked(json.dumps(running), count, 0) == []
    assert all(frame["private_selection"] is True for frame in running["frames"])
    recorder.close({"status": "finished", "winner_seats": [0], "decision_count": count - 1})
    after = games.read_game(tmp_path, "f4-pick")
    assert [frame["chosen"] for frame in after["frames"]] == [
        [_secret(seat)] for seat in range(1, count)
    ]


# ---- the lock is the only hurdle on the play route -------------------------------------------


def _patch_play_route(
    monkeypatch: pytest.MonkeyPatch, bridge_of: Callable[[int], SeatBridge]
) -> dict[str, SeatBridge]:
    """Everything the play route needs besides the lock, with synthetic decks and a test bridge."""
    made: dict[str, SeatBridge] = {}
    monkeypatch.setattr(launch, "engine_command", lambda _folder: ("fake-bridge",))
    monkeypatch.setattr(
        launch, "lab_snapshot", lambda _store, _rev: {"deck_id": "own-deck", "cards": []}
    )
    monkeypatch.setattr(launch, "cards_unsupported_by_engine", lambda _snapshot: [])
    monkeypatch.setattr(launch, "cards_unknown_to_pilots", lambda _snapshot: [])
    monkeypatch.setattr(play, "load_decks", lambda paths: _decks(len(paths)))
    monkeypatch.setattr(play, "engine_command", lambda _folder: ("fake-bridge",))
    monkeypatch.setattr(play, "bridge_jar_sha256", lambda *_a, **_k: "ab" * 32)

    def factory(*_args: object, **_kwargs: object) -> SeatBridge:
        bridge = bridge_of(len(made))
        made[str(len(made))] = bridge
        return bridge

    monkeypatch.setattr(play, "_RawFullGameClient", factory)
    return made


def _precon_ids(count: int) -> list[str]:
    ids = [str(deck["deck_id"]) for deck in launch.opponent_decks()]
    assert len(ids) >= count
    return ids[:count]


@pytest.mark.parametrize(("count", "human"), [(5, 0), (6, 0), (6, 5)])
def test_release_constant_is_the_only_seat_hurdle_on_the_play_route(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, count: int, human: int
) -> None:
    """With the lock as it is (4), five and six seats are refused; with only the constant raised
    (simulated in memory, the file stays at 4), the same request plays a whole game on the test
    bridge through the real route: seat validation, deck paths, game setup, live play, end."""
    assert launch.MAX_RELEASED_SEATS == 4
    made = _patch_play_route(monkeypatch, lambda _n: SeatBridge(count, human, rounds=1))
    client = TestClient(create_app(tmp_path), headers={"X-Studio": "1"})
    body = {
        "revision_id": "rev@own",
        "opponent_ids": _precon_ids(count - 1),
        "seed": SEED,
        "human_seats": [human],
        "decision_timeout_seconds": 0,
        "ai_delay_ms": 0,
    }
    refused = client.post("/api/games", json=body)
    assert refused.status_code == 422 and "locked" in refused.text and not made

    monkeypatch.setattr(launch, "MAX_RELEASED_SEATS", 6)
    started = client.post("/api/games", json=body)
    assert started.status_code == 200, started.text
    game_id = started.json()["game_id"]
    assert f"-{count}p-seed{SEED}" in game_id
    try:
        seen: set[str] = set()
        while True:
            snap = _next_state(client, game_id, seen)
            if not snap["running"]:
                break
            pending = snap["pending_decision"]
            seen.add(pending["decision_id"])
            assert _leaked(json.dumps(snap), count, human) == []
            answer = client.post(
                f"/api/play/{game_id}/decision",
                json={
                    "decision_id": pending["decision_id"],
                    "selected_option_ids": [pending["legal_options"][0]["option_id"]],
                    "ordering": [],
                },
            )
            assert answer.status_code == 200, answer.text
    finally:
        client.app.state.play_manager.shutdown_all()  # type: ignore[attr-defined]
    bridge = made["0"]
    created = bridge.created_payload
    assert created is not None
    assert len(created["deck_handles"]) == count  # type: ignore[arg-type]
    assert created["starting_player_seat"] == SEED % count
    assert created["human_seats"] == [human]
    assert snap["result"]["status"] == "finished"
    assert snap["result"]["winner_seats"] == [bridge.winner]
    assert [row["seat"] for row in snap["header"]["seats"]] == list(range(count))


def test_studio_refuses_five_and_six_seats_at_the_seat_rule_and_the_play_route(
    tmp_path: Path,
) -> None:
    """Issue #1661 acceptance: without the Owner's release five (and six) seats stay refused, at
    the seat rule itself and on the play route; the CLI switch exists only for measurement."""
    assert launch.MAX_RELEASED_SEATS == 4
    for opponents in (4, 5):
        with pytest.raises(ValueError, match=f"tables of {opponents + 1} seats are locked"):
            launch.validate_released_seat_count(opponents)
        assert (
            launch.validate_released_seat_count(opponents, allow_unreleased_seats=True)
            == opponents + 1
        )
    client = TestClient(create_app(tmp_path), headers={"X-Studio": "1"})
    refused = client.post(
        "/api/games", json={"revision_id": "r", "opponent_ids": ["a", "b", "c", "d"], "seed": 1}
    )
    assert refused.status_code == 422 and "tables of 5 seats are locked" in refused.text
    # the engine limit stays 6: seven seats are refused even with the switch
    with pytest.raises(ValueError, match="1 to 5 opponents"):
        launch.validate_released_seat_count(6, allow_unreleased_seats=True)


# ---- F5: the eight rule points at the Studio/bridge interface ---------------------------------
# Each test checks what the Studio does with what the engine publishes. Whether XMage plays the
# rule right at five or six seats is not checked here (NOT_RUN, part B / UNKNOWN).


@pytest.mark.parametrize("count", [5, 6])
def test_f5_1_apnap_trigger_order_at_seat_five_or_six_passes_only_engine_options(
    tmp_path: Path, count: int
) -> None:
    """Point 1 (APNAP), interface: a trigger-order decision of the human at the last seat reaches
    the page with the engine's options unchanged and goes back as an ordering of those ids only;
    a forged id is refused. The order of triggers between players is XMage's (not checked)."""
    human = count - 1
    bridge = SeatBridge(count, human, rounds=1, human_class="trigger_order")
    manager, client = _start(tmp_path, bridge, f"f5-apnap-{count}")
    try:
        snap = _next_state(client, f"f5-apnap-{count}", set())
        pending = snap["pending_decision"]
        assert pending["decision_class"] == "trigger_order"
        ids = [option["option_id"] for option in pending["legal_options"]]
        assert len(ids) == count
        forged = client.post(
            f"/api/play/f5-apnap-{count}/decision",
            json={"decision_id": pending["decision_id"], "ordering": [*ids[:-1], "forged"]},
        )
        assert forged.status_code == 422
        good = client.post(
            f"/api/play/f5-apnap-{count}/decision",
            json={"decision_id": pending["decision_id"], "ordering": list(reversed(ids))},
        )
        assert good.status_code == 200, good.text
    finally:
        manager.shutdown_all()
    human_answers = [r for r in bridge.submitted if r.get("ordering")]
    assert len(human_answers) == 1
    assert human_answers[0]["ordering"] == list(reversed(ids))
    assert human_answers[0]["selected_option_ids"] == []


@pytest.mark.parametrize(("count", "out"), [(5, (2,)), (6, (1, 4))])
def test_f5_2_a_seat_leaving_mid_game_keeps_the_game_running_for_the_others(
    tmp_path: Path, count: int, out: tuple[int, ...]
) -> None:
    """Point 2 (leaving mid game), interface: when the engine removes seats, the page keeps
    following the remaining seats, the left seats are shown as lost, hidden cards stay hidden and
    the closing result names the engine's winner. Leaving with objects on the stack or in combat
    is the engine's rule (not checked)."""
    bridge = SeatBridge(count, 0, rounds=2, eliminate=out, winner=count - 1)
    bodies, final, pendings = play_through(tmp_path, bridge, f"f5-out-{count}")
    assert len(pendings) == 2
    for body in bodies:
        assert _leaked(body, count, 0) == []
    later = pendings[1]["pilot_state"]
    assert [row["seat"] for row in later["players"] if row.get("has_lost")] == list(out)
    frames = final["frames"]
    last = frames[-1]
    assert [row["seat"] for row in last["players"] if row["lost"]] == list(out)
    assert {frame["seat"] for frame in frames[count:]} == set(range(count)) - set(out)
    assert final["result"]["winner_seats"] == [count - 1]


def test_f5_3_commander_damage_for_all_ordered_pairs_at_six_seats_is_shown_as_published() -> None:
    """Point 3 (commander damage per pair), interface: with six seats the engine publishes up to
    30 ordered (attacker, defender) totals; the page files each under its defender and attacker
    seat, adds nothing up and drops nothing. The 21-damage rule is XMage's (not checked)."""
    pairs = [(a, d) for a in range(6) for d in range(6) if a != d]
    assert len(pairs) == 30
    status = [
        {
            "owner_id": f"p{a}",
            "name": COMMANDERS[a],
            "casts_from_command": a,
            "commander_damage_to_player": [
                {"player_id": f"p{d}", "total": 10 * a + d} for d in range(6) if d != a
            ],
        }
        for a in range(6)
    ]
    state = {
        "players": [{"seat": s, "player_id": f"p{s}"} for s in range(6)],
        "commander_status": status,
    }
    out = _page_function("commanderRows", state)
    assert isinstance(out, dict) and sorted(out) == [str(s) for s in range(6)]
    filed = sorted(
        (row["fromSeat"], int(defender), row["total"])
        for defender, entry in out.items()
        for row in entry["received"]
    )
    assert filed == sorted((a, d, 10 * a + d) for a, d in pairs)
    assert [out[str(s)]["commanders"][0]["casts"] for s in range(6)] == list(range(6))


def test_f5_4_bridge_keeps_range_all_and_attack_multiple_for_every_table_size() -> None:
    """Point 4 (range of influence ALL), Festlegung: the bridge sets range ALL and attack option
    MULTIPLE for every table, duel and free-for-all alike, with no five- or six-seat branch (read
    only; changing it is an Owner decision, F1). What a seat sees at five or six seats is the F4
    tests above."""
    source = (
        ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageCommanderGames.java"
    ).read_text(encoding="utf-8")
    assert source.count("RangeOfInfluence.ALL") >= 2
    assert source.count("MultiplayerAttackOption.MULTIPLE") >= 2
    for narrower in ("RangeOfInfluence.ONE", "RangeOfInfluence.TWO", "playerCount == 5", "== 6"):
        assert narrower not in source, narrower
    session = (
        ROOT / "engine-bridge/src/main/java/org/commanderlab/xmage/XmageFullGameSession.java"
    ).read_text(encoding="utf-8")
    assert "MAX_PLAYERS = 6" in session
    assert '"Full Game Seat " + (index + 1)' in session  # the engine's seat names count from 1


@pytest.mark.parametrize("count", [5, 6])
def test_f5_5_attacks_on_several_defenders_mark_exactly_those_seats(count: int) -> None:
    """Point 5 (several defenders), interface: one combat with attacks on two defenders, among
    them the last seat, marks exactly those seats as attacked on the board; the engine names a
    player "Full Game Seat N" with N = seat + 1 (XmageFullGameSession.java)."""
    defenders = (1, count - 1)
    frame = _board_frame(
        count,
        combat={
            "attacks": [
                {"attacker": f"Bear {k}", "target": f"Full Game Seat {seat + 1}"}
                for k, seat in enumerate(defenders)
            ]
        },
    )
    panels = _render_board(count, frame)["panels"]
    assert isinstance(panels, list)
    attacked = [index for index, panel in enumerate(panels) if "attacked" in panel["classes"]]
    assert attacked == list(defenders)


@pytest.mark.parametrize("count", [5, 6])
def test_f5_6_human_concedes_at_five_or_six_seats_and_only_then_hands_are_shown(
    tmp_path: Path, count: int
) -> None:
    """Point 6 (concede and terminal paths), interface: the human at the last seat concedes; the
    game ends with the engine's result, no response before the end shows another seat's hand,
    the closing state shows them all. Several concedes and "last player standing" inside XMage
    are the engine's rules (part B)."""
    human = count - 1
    bridge = SeatBridge(count, human, rounds=2, winner=0)
    bodies, final, pendings = play_through(tmp_path, bridge, f"f5-concede-{count}", concede_at=2)
    assert len(pendings) == 2 and bridge.conceded_by == [f"p{human}"]
    assert len(final["frames"]) >= count  # a whole round was recorded before the concede
    for body in bodies:
        assert _leaked(body, count, human) == []
    assert final["result"]["status"] == "finished"
    assert final["result"]["winner_seats"] == [0]
    assert final["hands_revealed"] is True
    assert all(_secret(seat) in json.dumps(final["frames"]) for seat in range(count - 1))


@pytest.mark.parametrize("count", [5, 6])
def test_f5_7_seat_and_turn_order_cover_seats_five_and_six(tmp_path: Path, count: int) -> None:
    """Point 7 (seat and turn order): the game setup seats all decks in order with seats 0..N-1,
    the engine is asked to start at seat ``seed % N`` (all N starting seats over N consecutive
    seeds), and the recorded frames follow the engine's order from that seat."""
    prep = play.prepare_game(_decks(count), seed=SEED, game_id="order", jar_sha256="ab" * 32)
    assert prep.scenario.player_count == count
    assert [row["seat"] for row in prep.header["seats"]] == list(range(count))
    assert [p.seat for p in prep.pilots] == list(range(1, count + 1))
    assert sorted(seed % count for seed in range(SEED, SEED + count)) == list(range(count))
    bridge = SeatBridge(count, 0, rounds=1)
    _bodies, final, _pendings = play_through(tmp_path, bridge, f"f5-order-{count}")
    created = bridge.created_payload
    assert created is not None and created["starting_player_seat"] == SEED % count
    assert len(created["deck_handles"]) == count
    order = [frame["seat"] for frame in final["frames"]]
    assert order == [(SEED % count + k) % count for k in range(count)]
    # watched games and series go through the runner, which asks for the same starting seat
    runner = (ROOT / "src/commander_lab/engine/rules/full_game.py").read_text(encoding="utf-8")
    assert '"starting_player_seat": scenario.seed % player_count' in runner


def test_f5_8_replay_tape_takes_five_seats_and_refuses_six() -> None:
    """Point 8 (replay asymmetry): the semantic replay tape describes up to five seats; a
    six-seat manifest or principal is refused, so a six-seat game can never earn a replay PASS.
    The Studio's own replay (stepping through recorded frames) does not use the tape."""
    from pydantic import ValidationError

    from commander_lab.semantic_replay.tape import TapeSeatPrincipal

    def principal(seat: int) -> dict[str, object]:
        return {
            "seat": seat,
            "deck_id": f"d{seat}",
            "pilot_identity": "p",
            "pilot_version": "1",
            "decision_policy_version": "1",
        }

    assert TapeSeatPrincipal(**principal(5)).seat == 5  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        TapeSeatPrincipal(**principal(6))  # type: ignore[arg-type]
    tape_source = (ROOT / "src/commander_lab/semantic_replay/tape.py").read_text(encoding="utf-8")
    assert tape_source.count("le=5") == 3  # manifest player_count, seat principal, actor
    studio = ROOT / "src/commander_lab/studio"
    users = sorted(
        path.name
        for path in [*studio.glob("*.py"), *studio.glob("static/*.js")]
        if "semantic_replay" in path.read_text(encoding="utf-8")
    )
    assert users == []


# ---- F8 planning: paired series with a full seat rotation at five and six seats ---------------

BASE, VARIANT = "deck/base", "deck/variant"


def _opponents(count: int) -> list[str]:
    return [f"deck/opp{k}" for k in range(1, count)]


@pytest.mark.parametrize(("count", "games"), [(5, 25), (6, 36)])
def test_f8_rotation_plan_is_complete_at_five_and_six_seats(count: int, games: int) -> None:
    """A block of N consecutive seeds times N tested seats (25 or 36 games per arm) is a full
    Latin square: every (starting seat = seed % N, tested seat) combination once, every relative
    position of the contender to the starting seat N times, every deck in every seat N times."""
    seeds = list(range(1000, 1000 + count))
    units = [(seed, seat) for seed in seeds for seat in range(count)]
    assert len(units) == games
    starts = Counter((seed % count, seat) for seed, seat in units)
    assert len(starts) == games and set(starts.values()) == {1}
    relative = Counter((seat - seed % count) % count for seed, seat in units)
    assert relative == Counter(dict.fromkeys(range(count), count))
    contender = _deck(0)
    opponents = [_deck(k) for k in range(1, count)]
    visits: Counter[tuple[str, int]] = Counter()
    for _seed, seat in units:
        table = pod_decks(contender, opponents, seat + 1)
        assert table[seat].deck_id == contender.deck_id
        assert sorted(d.deck_id for d in table) == sorted(d.deck_id for d in _decks(count))
        visits.update((deck.deck_id, index) for index, deck in enumerate(table))
    assert set(visits.values()) == {count} and len(visits) == count * count


def _write_log(folder: Path, game_id: str, decks: list[str], winner: int, seed: int) -> Path:
    header = {
        "kind": "header",
        "schema": "studio-game-log-1",
        "game_id": game_id,
        "seed": seed,
        "engine_commit": "a" * 40,
        "pilot": "Pilot 1.0.0",
        "decision_policy": "policy-1",
        "seats": [
            {"seat": seat, "deck_id": deck, "commanders": [f"Cmd {seat}"]}
            for seat, deck in enumerate(decks)
        ],
    }
    result = {"kind": "result", "status": "finished", "winner_seats": [winner]}
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{game_id}.jsonl"
    path.write_text(json.dumps(header) + "\n" + json.dumps(result) + "\n", encoding="utf-8")
    return path


class _Player:
    """A PairPlayer at N seats: the contender rotates like ``pod_decks``; ``fail`` names games
    that fail (no exposure) and ``misseat`` games that seat the wrong deck."""

    def __init__(
        self,
        folder: Path,
        count: int,
        *,
        fail: frozenset[tuple[str, int, int]] = frozenset(),
        misseat: frozenset[tuple[str, int, int]] = frozenset(),
    ) -> None:
        self.folder, self.count, self.fail, self.misseat = folder, count, fail, misseat
        self.calls: list[tuple[str, int, int]] = []

    def __call__(self, arm: str, seed: int, seat: int) -> PlayedGame:
        self.calls.append((arm, seed, seat))
        if (arm, seed, seat) in self.fail:
            return {"exposure": None, "failure_class": "EngineTimeout"}
        order = [BASE if arm == "base" else VARIANT, *_opponents(self.count)]
        decks = [order[(index - seat) % self.count] for index in range(self.count)]
        if (arm, seed, seat) in self.misseat:
            decks = decks[1:] + decks[:1]
        path = _write_log(self.folder, f"{arm}-s{seed}-t{seat}", decks, seed % self.count, seed)
        return {"exposure": game_exposures(path), "failure_class": None}


@pytest.mark.parametrize(("count", "games"), [(5, 25), (6, 36)])
def test_f8_series_plays_every_planned_unit_and_names_every_failure(
    tmp_path: Path, count: int, games: int
) -> None:
    """The paired series at five and six seats plays all 25 or 36 units per arm in plan order;
    a failed game and a misseated game at the tested seats five and six censor their pairs and
    are counted by class: no silent drop, never a loss."""
    seeds = list(range(1000, 1000 + count))
    fail = frozenset({("variant", seeds[1], 4)})
    misseat = frozenset({("base", seeds[2], count - 1)})
    player = _Player(tmp_path, count, fail=fail, misseat=misseat)
    result = run_comparison_series(
        base_deck_id=BASE,
        variant_deck_id=VARIANT,
        seeds=seeds,
        tested_seats=list(range(count)),
        budget_pairs=games,
        look_every_pairs=games,  # one look at the end: the whole block is played
        max_censored_share=1.0,
        play=player,
    )
    expected = [
        (arm, seed, seat) for seed in seeds for seat in range(count) for arm in ("base", "variant")
    ]
    assert player.calls == expected and len(expected) == 2 * games
    assert result["pairs_played"] == games
    assert result["pairs_censored"] == 2
    assert result["pairs_completed"] == games - 2
    assert result["games_failed_variant"] == 1 and result["games_failed_base"] == 1
    assert result["failure_classes"] == {
        "base": {"Misseated": 1},
        "variant": {"EngineTimeout": 1},
    }
    assert any("did not seat the compared deck" in w for w in result["warnings"])
    assert sorted({pair["seat"] for pair in result["pairs"]}) == list(range(count))


def test_f8_default_censoring_limit_stops_a_decision_on_one_failed_pair() -> None:
    """With the default limit (5 % censored pairs) one failed pair of 25 (4 %) passes and two
    (8 %) block a decision: at five seats a block of 25 tolerates one failed pair, at six seats a
    block of 36 one as well (2 of 36 = 5.6 %)."""
    from commander_lab.studio.paired_comparison import (
        DEFAULT_MAX_CENSORED_SHARE,
        _censoring_issues,
    )

    def blocked(censored: int, played: int) -> bool:
        reason, _warnings = _censoring_issues(
            censored=censored,
            played=played,
            failed_base=censored,
            failed_variant=censored,
            max_censored_share=DEFAULT_MAX_CENSORED_SHARE,
        )
        return reason is not None

    assert DEFAULT_MAX_CENSORED_SHARE == 0.05
    assert (blocked(1, 25), blocked(2, 25)) == (False, True)
    assert (blocked(1, 36), blocked(2, 36)) == (False, True)


@pytest.mark.parametrize("count", [5, 6])
def test_f8_series_manager_plans_seeds_for_whole_rotations(
    tmp_path: Path, count: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The series start (``start_series``) seats ``1 + opponents`` players, rotates the tested
    seat through all of them and plans ceil(budget / N) consecutive seeds, so a budget of 25 or
    36 is exactly one rotation block; the plan and the duration floor use N seats per seed."""
    from commander_lab.studio import paired_series

    budget = count * count
    tested_seats = list(range(count))
    needed = -(-budget // len(tested_seats))
    assert needed == count
    plan = paired_series.planned_detectable_difference_pp(budget, count)
    assert plan["assumptions"]["seats_per_seed"] == count  # type: ignore[index]
    assert plan["assumptions"]["degrees_of_freedom"] == count - 1  # type: ignore[index]
    floor = paired_series.estimate_series_duration(budget, seats_per_seed=count)
    assert floor["max_games"] == 2 * budget and floor["minimum_is_lower_bound"] is True
    source = (ROOT / "src/commander_lab/studio/paired_series.py").read_text(encoding="utf-8")
    assert "tested_seats = list(range(table_size)) if rotate_seats else [0]" in source
    assert "needed_seeds = -(-budget_pairs // len(tested_seats))" in source
    assert "seats_per_seed=len(tested_seats)" in source


# ---- the play page at five and six seats (DOM stand-in, release simulated in memory) ----------

_DOM = r"""
const fs = require('fs');
class El {
  constructor(tag, id) {
    this.tagName = String(tag).toUpperCase(); this.id = id || ''; this.children = []; this.className = '';
    this.dataset = {}; this.attrs = {}; this.hidden = false; this.value = ''; this.disabled = false;
    this.checked = false; this.listeners = {}; this.nodeType = 1; this.style = {}; this._text = '';
    const self = this;
    this.classList = {
      add: (...c) => { const s = new Set(self.className.split(' ').filter(Boolean)); c.forEach((x) => s.add(x)); self.className = [...s].join(' '); },
      remove: (...c) => { self.className = self.className.split(' ').filter((x) => x && !c.includes(x)).join(' '); },
      toggle: (c, on) => { const want = on === undefined ? !self.classList.contains(c) : on; if (want) self.classList.add(c); else self.classList.remove(c); return want; },
      contains: (c) => self.className.split(' ').includes(c),
    };
  }
  get textContent() { return this._text + this.children.map((c) => (c.nodeType === 3 ? c.text : c.textContent)).join(''); }
  set textContent(v) { this.children = []; this._text = String(v); }
  append(...xs) { for (const x of xs) { if (x && x.parent) x.parent.children = x.parent.children.filter((c) => c !== x); x.parent = this; this.children.push(x); } }
  appendChild(x) { this.append(x); return x; }
  prepend(...xs) { for (const x of xs.reverse()) { x.parent = this; this.children.unshift(x); } }
  replaceWith(x) { const p = this.parent; if (!p) return; x.parent = p; p.children[p.children.indexOf(this)] = x; }
  replaceChildren(...xs) { this.children = []; this._text = ''; this.append(...xs); }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter((c) => c !== this); }
  addEventListener(k, f) { (this.listeners[k] ||= []).push(f); }
  removeEventListener() {}
  fire(k) { for (const f of this.listeners[k] || []) f({ target: this, preventDefault() {}, stopPropagation() {} }); }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  removeAttribute(k) { delete this.attrs[k]; }
  hasAttribute(k) { return k in this.attrs; }
  all() { const out = []; const walk = (n) => { for (const c of n.children) if (c.nodeType === 1) { out.push(c); walk(c); } }; walk(this); return out; }
  matches(sel) { if (sel.startsWith('.')) return sel.slice(1).split('.').every((c) => this.classList.contains(c)); return this.tagName === sel.toUpperCase(); }
  querySelectorAll(sel) { const parts = sel.split(',').map((s) => s.trim()); return this.all().filter((n) => parts.some((p) => n.matches(p))); }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
  closest() { return null; }
  focus() {} blur() {} scrollIntoView() {}
  getBoundingClientRect() { return { left: 0, top: 0, right: 0, bottom: 0, width: 0, height: 0 }; }
}
const registry = {};
const document = {
  createElement: (t) => new El(t), createElementNS: (_n, t) => new El(t), createTextNode: (t) => ({ nodeType: 3, text: String(t) }),
  getElementById: (id) => (registry[id] ||= new El('div', id)), addEventListener() {}, querySelectorAll: () => [], querySelector: () => null,
  body: new El('body'), documentElement: new El('html'), activeElement: null,
};
const storage = { getItem: () => null, setItem() {} };
const window = { localStorage: storage, addEventListener() {}, matchMedia: () => ({ matches: false, addEventListener() {} }) };
function loadPage(release) {
  const files = ['ui.js', 'commander.js', 'vorspulen.js', 'boardclick.js', 'replay.js', 'play_p1a.js', 'follow.js', 'partie.js'];
  let src = files.map((f) => fs.readFileSync(f, 'utf8')).join('\n;\n');
  if (!/\nstart\(\);\s*$/.test(src)) throw new Error('partie.js no longer ends with start();');
  src = src.replace(/\nstart\(\);\s*$/, '\n');
  if (release) {
    const locked = 'const OPPONENT_COUNTS = [1, 2, 3];';
    if (!src.includes(locked)) throw new Error('lock line changed');
    src = src.replace(locked, 'const OPPONENT_COUNTS = [1, 2, 3, 4, 5];');
  }
  const posted = [];
  const fetchStub = async (path, options) => {
    if (options && options.method === 'POST') { posted.push(JSON.parse(options.body)); return { ok: true, json: async () => ({ game_id: 'g', interactive: false }) }; }
    if (path === '/api/table') return { ok: true, json: async () => TABLE };
    if (path === '/api/games') return { ok: true, json: async () => [] };
    return { ok: true, json: async () => ({}) };
  };
  const make = new Function('document', 'window', 'location', 'history', 'fetch', 'localStorage', 'setTimeout', 'clearTimeout', 'requestAnimationFrame',
    src + '\n;return {state, renderView, newGame, commanderRows, OPPONENT_COUNTS};');
  const page = make(document, window, { search: '' }, { replaceState() {} }, fetchStub, storage, () => 0, () => {}, () => 0);
  return { page, posted };
}
const TABLE = {
  engine: { ready: true, pin: 'f4d12f6e80' },
  decks: [{ name: 'Own', branches: [{ revision_id: 'rev@own', branch: 'main', cards: 100 }] }],
  opponents: Array.from({ length: 8 }, (_, k) => ({ deck_id: 'precon/d' + k, name: 'Precon ' + k, year: '2024', commanders: ['Cmd ' + k] })),
  pods: null,
};
function board() {
  const panels = registry.table.children.filter((c) => c.classList && c.classList.contains('seat')).map((c) => ({ classes: c.className.split(' '), text: c.textContent }));
  const handText = registry.hand.all().map((n) => [n.textContent, ...Object.values(n.attrs)].join(' ')).join(' ') + ' ' + registry.hand.textContent;
  return { panels, hand: { title: registry['hand-title'].textContent, text: handText } };
}
"""


def _node(script: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")  # NOT_RUN, never PASS
    done = subprocess.run(
        [node, "-e", _DOM + script], capture_output=True, text=True, check=True, cwd=STATIC
    )
    return json.loads(done.stdout)


def _page_function(name: str, argument: object) -> object:
    return _node(
        f"const {{page}} = loadPage(false);"
        f"console.log(JSON.stringify(page.{name}({json.dumps(argument)})));"
    )


def _board_frame(count: int, **extra: object) -> dict[str, object]:
    players = [
        {
            "seat": seat,
            "life": 40 - seat,
            "poison": 0,
            "hand_count": 2,
            "library_count": 90,
            "lost": False,
            "won": False,
            "battlefield": [],
            "graveyard": [],
            "command": [COMMANDERS[seat]],
            "exile_count": 0,
            "exile": [],
            **({"hand": [_secret(0)]} if seat == 0 else {}),
        }
        for seat in range(count)
    ]
    frame: dict[str, object] = {
        "kind": "frame",
        "n": 1,
        "turn": 3,
        "phase": "combat",
        "step": "declare_attackers",
        "active_seat": 0,
        "seat": 0,
        "decision_class": "declare_attacker",
        "prompt": "Attack",
        "options": 2,
        "chosen": [],
        "players": players,
        "stack": [],
    }
    frame.update(extra)
    return frame


def _render_board(count: int, frame: dict[str, object]) -> dict[str, object]:
    header = {
        "seats": [
            {"seat": s, "deck_id": f"deck-sitz-{s + 1}", "commanders": [COMMANDERS[s]]}
            for s in range(count)
        ]
    }
    out = _node(
        "const {page} = loadPage(true);"
        f"Object.assign(page.state, {{gameId: 'g', header: {json.dumps(header)}, "
        f"frames: [{json.dumps(frame)}], index: 0, running: true}});"
        "page.renderView(); console.log(JSON.stringify(board()));"
    )
    assert isinstance(out, dict)
    return out


@pytest.mark.parametrize("count", [5, 6])
def test_play_board_draws_five_and_six_seats_with_their_names_and_colors(count: int) -> None:
    """The board draws one panel per published seat, named Sitz 1 to Sitz N with the commander of
    each seat, and shows a hand only where the frame has one; the seat colors for Sitz 5 and 6
    exist and the table grid has no fixed seat count."""
    board = _render_board(count, _board_frame(count))
    panels = board["panels"]
    assert isinstance(panels, list) and len(panels) == count
    for seat, panel in enumerate(panels):
        assert f"Sitz {seat + 1}" in str(panel["text"]) and COMMANDERS[seat] in str(panel["text"])
    hand = board["hand"]
    assert isinstance(hand, dict)
    assert hand["title"] == "Hand von Sitz 1" and _secret(0) in str(hand["text"])
    css = (STATIC / "partie.css").read_text(encoding="utf-8")
    assert ".s4{" in css and ".s5{" in css
    assert "#table{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))" in css


def test_new_game_dialog_offers_five_and_six_players_only_once_the_lock_line_changes() -> None:
    """Today the dialog offers 2 to 4 players. With only the lock line changed (in memory), it
    offers 2 to 6, fills five AI seats Sitz 2 to Sitz 6 with five different decks and sends five
    opponents and six seat styles to the server."""
    out = _node(
        """
(async () => {
  const result = {};
  for (const release of [false, true]) {
    const { page, posted } = loadPage(release);
    await page.newGame('rev@own');
    const box = registry['modal-box'];
    const selects = box.all().filter((n) => n.tagName === 'SELECT');
    const count = selects.find((s) => s.children.some((o) => /Spieler$/.test(o.textContent)));
    const offered = count.children.map((o) => o.textContent);
    let seats = null, body = null;
    if (release) {
      count.value = '5'; count.fire('change');
      const picks = box.querySelectorAll('.opp-deck');
      seats = box.all().filter((n) => n.tagName === 'LABEL' && /\\(KI\\)/.test(n.textContent)).map((n) => n.textContent.split(' (KI)')[0]);
      for (const [i, p] of picks.entries()) p.value = 'precon/d' + i;
      const go = box.all().find((n) => n.tagName === 'BUTTON' && n.textContent === 'Partie starten');
      for (const f of go.listeners.click) await f({});
      body = posted[0] || null;
    }
    result[release ? 'released' : 'locked'] = { offered, seats, body };
  }
  console.log(JSON.stringify(result));
})();
"""
    )
    assert isinstance(out, dict)
    assert out["locked"]["offered"] == ["2 Spieler", "3 Spieler", "4 Spieler"]
    released = out["released"]
    assert released["offered"] == [f"{n} Spieler" for n in range(2, 7)]
    assert released["seats"] == [f"Sitz {n}" for n in range(2, 7)]
    body = released["body"]
    assert body["opponent_ids"] == [f"precon/d{i}" for i in range(5)]
    assert len(body["seat_styles"]) == 6 and "human_seats" not in body


# ---- part B helper: the identity digest of one game log (F3), checked here on synthetic logs ---

_VOLATILE_RESULT_KEYS = frozenset(
    {"ended_at", "log", "jvm_life_id", "position_in_jvm", "game_id", "bridge_jar_sha256"}
)


def identity_row(log_path: str | Path) -> dict[str, object]:
    """What must be equal for one seed across runs (F3): the engine's semantic transcript hash
    (primary, as in the four-seat bridge gate), winner, decision count, frame count, a digest of
    all frames and of the result without run-specific fields (time, ids, JVM position, file
    path). Part B runs it on real logs played with the same command and the same game ids."""
    path = Path(log_path)
    opener = gzip.open if path.suffix == ".gz" else open
    header: dict[str, object] = {}
    result: dict[str, object] = {}
    frames: list[dict[str, object]] = []
    with opener(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            entry = json.loads(line)
            if entry.get("kind") == "header":
                header = entry
            elif entry.get("kind") == "frame":
                frames.append(entry)
            elif entry.get("kind") == "result":
                result = entry

    def digest(value: object) -> str:
        text = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    stable_result = {k: v for k, v in result.items() if k not in _VOLATILE_RESULT_KEYS}
    seats = header.get("seats")
    return {
        "seed": header.get("seed"),
        "seats": len(seats) if isinstance(seats, list) else None,
        "status": result.get("status"),
        # primary check, as in the four-seat bridge gate; the digests show where runs diverge
        "semantic_transcript_sha256": result.get("semantic_transcript_sha256"),
        "winner_seats": result.get("winner_seats"),
        "decision_count": result.get("decision_count"),
        "frames": len(frames),
        "frame_digest": digest(frames),
        "result_digest": digest(stable_result),
    }


def test_identity_row_ignores_run_fields_and_catches_one_changed_frame(tmp_path: Path) -> None:
    def write(name: str, *, chosen: str, ended: str, jvm: str) -> Path:
        lines = [
            {
                "kind": "header",
                "game_id": name,
                "seed": 7,
                "seats": [{"seat": s} for s in range(6)],
            },
            {"kind": "frame", "n": 1, "seat": 3, "chosen": [chosen]},
            {
                "kind": "result",
                "status": "finished",
                "winner_seats": [3],
                "decision_count": 1,
                "semantic_transcript_sha256": "c" * 64,
                "ended_at": ended,
                "game_id": name,
                "jvm_life_id": jvm,
                "position_in_jvm": 4 if jvm == "b" else 1,
                "log": f"/tmp/{name}.jsonl.gz",
            },
        ]
        path = tmp_path / f"{name}.jsonl.gz"
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            handle.write("".join(json.dumps(line) + "\n" for line in lines))
        return path

    one = identity_row(write("one", chosen="Pass", ended="t1", jvm="a"))
    two = identity_row(write("two", chosen="Pass", ended="t2", jvm="b"))
    other = identity_row(write("three", chosen="Cast X", ended="t1", jvm="a"))
    assert one == two
    assert one["seats"] == 6 and one["winner_seats"] == [3] and one["frames"] == 1
    assert one["semantic_transcript_sha256"] == "c" * 64
    assert other["frame_digest"] != one["frame_digest"]


# ---- #1702: the SIMULATE way for five and six seats, built behind the lock ----------------------
# The release is not here either: ``launch.MAX_RELEASED_SEATS`` stays 4. The series route refuses
# five and six seats without a switch; with the lock raised in memory it plans and plays them
# (``play_override`` stands in for the bridge: no engine, no real game).


def test_pod_presets_name_exactly_the_opponents_of_each_table_size() -> None:
    """Every preset names exactly ``seats - 1`` different, known decks; the four-seat presets
    are ``POD_PRESETS`` itself. A size or pod without a preset, and a wrong number of given
    opponents, are errors: nothing is cut off, filled up or taken from another size."""
    by_id = {deck_id: path for deck_id, *_rest, path in launch._precons()}
    assert launch.POD_PRESETS_BY_SEATS[4] == launch.POD_PRESETS
    assert sorted(launch.POD_PRESETS_BY_SEATS) == list(
        range(launch.MIN_SEATS, launch.MAX_SEATS + 1)
    )
    for seats, presets in launch.POD_PRESETS_BY_SEATS.items():
        assert set(presets) == set(launch.POD_PRESETS)
        for pod in presets:
            opponents = launch.pod_preset(pod, seats)
            assert len(opponents) == seats - 1 == len(set(opponents))
            paths = launch.resolve_opponent_paths(
                pod, None, table_seats=seats, allow_unreleased_seats=True
            )
            assert paths == [by_id[oid] for oid in opponents]
    for pod, seats, message in (
        ("no-such-pod", 5, "Unbekannter Gegnertisch"),
        ("precon", 7, "hat für 7 Sitze kein Preset"),
    ):
        with pytest.raises(ValueError, match=message):
            launch.pod_preset(pod, seats)
    four = list(launch.POD_PRESETS["precon"])
    with pytest.raises(ValueError, match="braucht 4 Gegner, angegeben sind 3"):
        launch.resolve_opponent_paths("precon", four, table_seats=5, allow_unreleased_seats=True)
    with pytest.raises(ValueError, match="braucht 3 Gegner, angegeben sind 4"):
        launch.resolve_opponent_paths(
            "precon", [*four, "precon/2023/veloci_ramp_tor"], table_seats=4
        )


def test_a_size_without_its_preset_is_an_error_not_a_fill(monkeypatch: pytest.MonkeyPatch) -> None:
    """With the five-seat presets missing, a five-seat series is refused by name; the four-seat
    preset is never padded with a fifth deck (no "first option" stand-in)."""
    monkeypatch.setattr(launch, "MAX_RELEASED_SEATS", 6)
    monkeypatch.setitem(launch.POD_PRESETS_BY_SEATS, 5, {})
    with pytest.raises(ValueError, match="hat für 5 Sitze kein Preset"):
        launch.resolve_opponent_paths("precon", None, table_seats=5)
    options = launch.paired_table_options()
    five = next(size for size in options["sizes"] if size["seats"] == 5)  # type: ignore[union-attr]
    assert five["pods"] == {}  # type: ignore[index]


def test_paired_tables_route_reads_the_lock_at_request_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The series dialog learns the sizes from the server: today 2 to 4 released, 5 and 6 locked;
    with only the constant raised (in memory) the same route offers 2 to 6."""
    client = TestClient(create_app(tmp_path / "studio"))
    locked = client.get("/api/simulations/paired-tables").json()
    assert locked["released_max_seats"] == 4 and locked["default_seats"] == 4
    assert [(s["seats"], s["released"]) for s in locked["sizes"]] == [
        (2, True), (3, True), (4, True), (5, False), (6, False),
    ]  # fmt: skip
    for size in locked["sizes"]:
        for pod, decks in size["pods"].items():
            assert [d["deck_id"] for d in decks] == list(launch.pod_preset(pod, size["seats"]))
            assert all(d["name"] for d in decks)
    monkeypatch.setattr(launch, "MAX_RELEASED_SEATS", 6)
    released = client.get("/api/simulations/paired-tables").json()
    assert released["released_max_seats"] == 6
    assert all(s["released"] for s in released["sizes"])


@pytest.fixture
def series_lab(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Two deck revisions in a real store; the series start gets a recording ``play_override``
    in place of the bridge, every other step (route, plan, presets, lock) is the real one."""
    from commander_lab.studio import paired_series
    from commander_lab.studio.store import StudioStore
    from tests.unit.test_studio_experiments import HEADERS, _cards, _player, _seed

    store = StudioStore.open(tmp_path)
    try:
        _seed(store)
    finally:
        store.close()
    monkeypatch.setattr(paired_series, "_preflight_snapshot_cards", lambda *a, **k: None)
    manager = paired_series.paired_series_manager
    original = manager.start_series
    calls: list[tuple[str, int, int]] = []

    def start(*args: object, **kwargs: object) -> paired_series.PairedSeriesJob:
        base = str(kwargs["base_revision_id"]).split("@", 1)[0]
        play = _player(f"{base}--base", f"{base}--variant")

        def recording(arm: str, seed: int, seat: int) -> PlayedGame:
            calls.append((arm, seed, seat))
            return play(arm, seed, seat)

        kwargs["play_override"] = recording
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(manager, "start_series", start)
    client = TestClient(create_app(tmp_path))
    revs: dict[str, str] = {}
    for name, forests, parent in (("base", 40, None), ("variant", 38, "base")):
        res = client.post(
            "/api/decks/chulane-b2/revisions",
            headers=HEADERS,
            json={
                "cards": _cards(forests),
                "note": name,
                "branch": "main" if parent is None else name,
                **({"parent_revision_id": revs[parent]} if parent else {}),
            },
        )
        assert res.status_code == 200, res.text
        revs[name] = res.json()["revision_id"]
    return {"client": client, "folder": tmp_path, "revs": revs, "calls": calls}


def _series_body(lab: dict[str, object], **extra: object) -> dict[str, object]:
    revs = lab["revs"]
    assert isinstance(revs, dict)
    return {
        "base_revision_id": revs["base"],
        "variant_revision_id": revs["variant"],
        "look_every_pairs": 100,
        "base_seed": 3000,
        **extra,
    }


@pytest.mark.parametrize("seats", [5, 6])
def test_series_route_refuses_five_and_six_seats_without_the_switch(
    series_lab: dict[str, object], seats: int
) -> None:
    """Acceptance #1702: the series route has no unlock switch and answers 422 "locked" for a
    table of five or six, by preset and by named opponents; nothing is played."""
    from commander_lab.studio.web import PairedSeriesBody

    assert "allow_unreleased_seats" not in PairedSeriesBody.model_fields
    assert launch.MAX_RELEASED_SEATS == 4
    client = series_lab["client"]
    assert isinstance(client, TestClient)
    for extra in (
        {"pod": "precon", "table_seats": seats, "budget_pairs": seats * seats},
        {
            "opponent_ids": list(launch.POD_PRESETS_BY_SEATS[seats]["precon"]),
            "table_seats": seats,
            "budget_pairs": seats * seats,
        },
        {"opponent_ids": list(launch.POD_PRESETS_BY_SEATS[seats]["precon"]), "budget_pairs": 20},
    ):
        res = client.post(
            "/api/simulations/paired",
            headers={"X-Studio": "1"},
            json=_series_body(series_lab, **extra),
        )
        assert res.status_code == 422, (extra, res.text)
        assert f"tables of {seats} seats are locked" in res.json()["detail"]
    assert series_lab["calls"] == []


@pytest.mark.parametrize("seats", [5, 6])
def test_series_route_plans_and_plays_five_and_six_seats_once_the_lock_is_raised(
    series_lab: dict[str, object], seats: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With only the constant raised (in memory) the real route seats the preset of that size,
    plans N consecutive seeds for a budget of N^2 pairs and plays every (seed, seat) unit of the
    full rotation once per arm, in plan order; the record names the table size."""
    from tests.unit.test_studio_experiments import _wait

    monkeypatch.setattr(launch, "MAX_RELEASED_SEATS", 6)
    client = series_lab["client"]
    assert isinstance(client, TestClient)
    budget = seats * seats
    res = client.post(
        "/api/simulations/paired",
        headers={"X-Studio": "1"},
        json=_series_body(series_lab, pod="precon", table_seats=seats, budget_pairs=budget),
    )
    assert res.status_code == 200, res.text
    started = res.json()
    record = _wait(Path(str(series_lab["folder"])), started["series_id"])
    assert record["opponent_deck_ids"] == list(launch.pod_preset("precon", seats))
    plan = record["seed_plan"]
    assert plan["player_count"] == seats and plan["seeds_planned"] == seats
    assert plan["first_seed"] == 3000
    expected = [
        (arm, 3000 + k, seat)
        for k in range(seats)
        for seat in range(seats)
        for arm in ("base", "variant")
    ]
    assert series_lab["calls"] == expected and len(expected) == 2 * budget
    units = Counter(((seed % seats), seat) for _arm, seed, seat in expected)
    assert len(units) == budget and set(units.values()) == {2}  # every unit once per arm
    assert record["result"]["pairs_played"] == budget


def test_a_five_seat_preset_series_resumes_at_five_seats(
    series_lab: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A preset series stores no opponent ids; its resume takes the table size from the stored
    opponents (five seats), not the default four, and the lock applies again on resume."""
    from commander_lab.studio import paired_series
    from tests.unit.test_studio_experiments import _wait

    monkeypatch.setattr(launch, "MAX_RELEASED_SEATS", 6)
    client = series_lab["client"]
    assert isinstance(client, TestClient)
    res = client.post(
        "/api/simulations/paired",
        headers={"X-Studio": "1"},
        json=_series_body(series_lab, pod="precon", table_seats=5, budget_pairs=25),
    )
    assert res.status_code == 200, res.text
    folder = Path(str(series_lab["folder"]))
    series_id = res.json()["series_id"]
    _wait(folder, series_id)
    path = folder / "games" / f"{series_id}.paired.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["opponent_ids"] is None
    raw["status"] = "interrupted"
    path.write_text(json.dumps(raw), encoding="utf-8")
    noop = lambda *_a: {"exposure": None, "failure_class": None}  # noqa: E731
    job = paired_series.paired_series_manager.resume_series(folder, series_id, play_override=noop)
    assert [d.deck_id for d in job.opponents] == list(launch.pod_preset("precon", 5))
    monkeypatch.setattr(launch, "MAX_RELEASED_SEATS", 4)
    _wait(folder, series_id)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["status"] = "interrupted"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="tables of 5 seats are locked"):
        paired_series.paired_series_manager.resume_series(folder, series_id, play_override=noop)


def test_experiment_plan_carries_its_seat_count_into_the_series() -> None:
    """``TableSpec.seats`` reaches the series start as ``table_seats``: the series checks the
    count against the lock and the opponents itself, not only the plan model."""
    source = (ROOT / "src/commander_lab/studio/experiments.py").read_text(encoding="utf-8")
    assert "table_seats=plan.table.seats," in source


def _series_log(
    folder: Path, game_id: str, seats: int, tested_seat: int, hand: list[str], won: bool
) -> None:
    """A finished game as a paired series writes it at ``seats`` seats: one deck state per
    seat, a pilot fingerprint and a known bridge jar, the tested deck on ``tested_seat``."""
    deck_ids = [f"deck/opp{k}" for k in range(1, seats)]
    deck_ids.insert(tested_seat, "deck/a")
    header = {
        "kind": "header",
        "schema": "studio-game-log-1",
        "game_id": game_id,
        "seed": int(game_id.rsplit("-s", 1)[1].split("-")[0]),
        "engine_commit": "a" * 40,
        "pilot": "Pilot 1.0.0",
        "decision_policy": "policy-1",
        "pilot_fingerprint": "f" * 64,
        "bridge_jar_sha256": "d" * 64,
        "seats": [
            {
                "seat": seat,
                "deck_id": deck,
                "deck_hash": hashlib.sha256(deck.encode()).hexdigest(),
                "commanders": [f"Cmd {seat}"],
            }
            for seat, deck in enumerate(deck_ids)
        ],
    }
    frame = {
        "kind": "frame",
        "n": 1,
        "turn": 1,
        "active_seat": None,
        "seat": tested_seat,
        "decision_class": "mulligan",
        "chosen": ["Keep opening hand"],
        "players": [
            {"seat": s, "life": 40, **({"hand": hand} if s == tested_seat else {})}
            for s in range(seats)
        ],
    }
    winner = tested_seat if won else (tested_seat + 1) % seats
    result = {"kind": "result", "status": "finished", "winner_seats": [winner]}
    folder.mkdir(parents=True, exist_ok=True)
    with gzip.open(folder / f"{game_id}.jsonl.gz", "wt", encoding="utf-8") as handle:
        handle.write("".join(json.dumps(line) + "\n" for line in (header, frame, result)))


def test_five_and_six_seat_series_are_their_own_table_size_strata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#1693/#1700 for #1702: games of a series at four, five and six seats of one deck state are
    three strata of the card evaluation, each with its own n, never counted together."""
    from commander_lab.studio import cache

    monkeypatch.setenv("COMMANDER_LAB_CACHE_CHECK", "1")
    monkeypatch.setattr(cache, "CHECK", True)
    games_dir = tmp_path / "games"
    counts = {4: 8, 5: 10, 6: 12}
    for seats, total in counts.items():
        for k in range(total):
            seed, seat = 3000 + k // seats, k % seats
            _series_log(
                games_dir,
                f"s1702-{seats}-base-s{seed}-t{seat}",
                seats,
                seat,
                ["Sol Ring"] if k % 2 == 0 else ["Forest"],
                won=k % 3 == 0,
            )
    with TestClient(create_app(tmp_path)) as client:
        response = client.get("/api/outcomes", params={"deck_id": "deck/a", "min_exposed": 1})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["strata"] == 3 and body["status"] == "NOT_POOLED" and body["cards"] == []
    assert body["pooling"]["differing_axes"] == [{"field": "table_size", "values": [4, 5, 6]}]
    cohorts = {c["table_size"]: c for c in body["cohorts"]}
    assert {k: c["games_total"] for k, c in cohorts.items()} == counts
    for size, cohort in cohorts.items():
        assert {s["table_size"] for s in cohort["stands"]} == {size}
    assert body["games_total"] == sum(counts.values())
    assert body["unknown_strata"] == []


# ---- #1702: the series dialog (paired.js) with a DOM stand-in ------------------------------------

_PAIRED_DOM = r"""
// A select reads its value from the selected option, else the first enabled one (as a browser).
class Sel extends El {
  constructor(tag, id) { super(tag, id); delete this.value; this._value = null; }
  get value() {
    const opts = this.children.filter((c) => c.tagName === 'OPTION');
    if (this._value !== null && opts.some((o) => String(o.value) === this._value)) return this._value;
    const sel = opts.find((o) => o.selected === true || 'selected' in o.attrs);
    if (sel) return String(sel.value);
    const first = opts.find((o) => !o.disabled);
    return first ? String(first.value) : '';
  }
  set value(v) { this._value = String(v); }
  replaceChildren(...xs) { this._value = null; super.replaceChildren(...xs); }
}
const baseCreate = document.createElement;
document.createElement = (t) => (String(t).toLowerCase() === 'select' ? new Sel(t) : baseCreate(t));
function h(tag, props, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'class') el.className = value;
    else if (key.startsWith('on')) el.addEventListener(key.slice(2), value);
    else if (key === 'dataset') Object.assign(el.dataset, value);
    else if (key in el && key !== 'list') el[key] = value;
    else el.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return el;
}
const StudioUI = { num: (v, d = 0) => Number(v).toLocaleString('de-DE', { minimumFractionDigits: d, maximumFractionDigits: d }), simStatusLabel: (s) => s };
eval(fs.readFileSync('paired.js', 'utf8') + '\n;globalThis.renderPairedComparisonSection = renderPairedComparisonSection;');
const tick = () => new Promise((r) => setTimeout(r, 0));
async function dialog(tables) {
  const plans = [], posted = [], toasts = [];
  const api = async (url, method, body) => {
    if (url === '/api/simulations/paired-tables') { if (tables === null) throw new Error('down'); return tables; }
    if (url.startsWith('/api/simulations/paired-plan?')) { plans.push(url); return { budget_pairs: 1, detectable_pp_low: null, assumptions: {} }; }
    if (url.startsWith('/api/diff-baselines')) return { baselines: [{ revision_id: 'repo:base', label: 'Basis' }] };
    if (method === 'POST' && url === '/api/simulations/paired') { posted.push(body); return { series_id: 'p1', status: 'running' }; }
    return {};
  };
  const deps = {
    h, api, commanderQuery: 'c=x', decks: () => [{ name: 'D', branches: [{ revision_id: 'rev@var', branch: 'main', cards: 100 }] }], currentDeckId: () => null, currentRevision: () => 'rev@var',
    token: () => 1, isCurrent: () => true, activePaired: () => null, pairedHistory: () => [], readinessAudit: () => null,
    setActivePaired() {}, pollPaired() {}, toast: (t) => toasts.push(t), fail: (e) => String(e), entries: () => [], commander: 'x',
  };
  const body = new El('div');
  renderPairedComparisonSection(body, deps);
  for (let i = 0; i < 6; i++) await tick();
  const all = body.all();
  const byId = (id) => all.find((n) => n.id === id);
  const form = all.find((n) => n.tagName === 'FORM');
  const view = () => ({
    sizes: byId('paired-table-select').children.map((o) => [o.textContent, Boolean(o.disabled)]),
    seats: byId('paired-table-select').value,
    note: byId('paired-table-note').textContent,
    block: byId('paired-block').textContent,
    estimate: byId('paired-estimate').textContent,
    budgets: byId('paired-budget-select').children.map((o) => Number(o.value)),
    budget: byId('paired-budget-select').value,
    pods: byId('paired-pod-select').children.map((o) => o.textContent),
    podDisabled: Boolean(byId('paired-pod-select').disabled),
    startDisabled: Boolean(byId('paired-start-btn').disabled),
    rotate: byId('paired-rotate-text').textContent,
    plan: plans[plans.length - 1] || null,
  });
  const choose = async (id, value) => { const el = byId(id); el.value = String(value); el.fire('change'); await tick(); };
  const toggle = async () => { const el = byId('paired-rotate-check'); el.checked = !el.checked; el.fire('change'); await tick(); };
  const submit = async () => { for (const f of form.listeners.submit) await f({ preventDefault() {} }); return posted[posted.length - 1] || null; };
  return { view, choose, toggle, submit, toasts };
}
"""


def _paired_dialog(script: str) -> dict[str, object]:
    out = _node(_PAIRED_DOM + "(async () => {" + script + "})();")
    assert isinstance(out, dict)
    return out


def _tables_json(monkeypatch: pytest.MonkeyPatch, released: int) -> str:
    monkeypatch.setattr(launch, "MAX_RELEASED_SEATS", released)
    return json.dumps(launch.paired_table_options())


def test_series_dialog_offers_the_table_size_and_greys_out_five_and_six_while_locked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Today: sizes 2 to 4 selectable, 5 and 6 shown as "nicht freigegeben" and disabled, the note
    names the lock, four seats is the default and the plan asks for four seats per seed. Without
    the server's answer only four seats are offered. A size without a preset cannot start."""
    tables = _tables_json(monkeypatch, 4)
    out = _paired_dialog(
        f"const locked = await dialog({tables}); const a = locked.view();"
        "await locked.choose('paired-table-select', 3); const three = locked.view();"
        "const body3 = await locked.submit();"
        "const down = (await dialog(null)).view();"
        f"const t = {tables}; t.sizes[1].pods = {{}};"
        "const nopreset = await dialog(t); await nopreset.choose('paired-table-select', 3);"
        "const np = nopreset.view(); const npBody = await nopreset.submit();"
        "console.log(JSON.stringify({a, three, body3, down, np, npBody, npToasts: nopreset.toasts}));"
    )
    a = out["a"]
    assert isinstance(a, dict)
    assert a["sizes"] == [
        ["2 Sitze", False], ["3 Sitze", False], ["4 Sitze", False],
        ["5 Sitze (nicht freigegeben)", True], ["6 Sitze (nicht freigegeben)", True],
    ]  # fmt: skip
    assert a["seats"] == "4" and a["rotate"] == "Sitze 1\u20134 rotieren"
    assert a["note"].startswith("5 und 6 Sitze sind nicht freigegeben")
    assert "nie zusammengezählt" in a["note"]
    assert a["plan"].endswith("seats_per_seed=4")
    assert a["budgets"] == [20, 40, 60, 100, 200] and a["budget"] == "40"  # unchanged at four
    assert a["pods"][0] == "Precon (Lorehold Spirit, Animated Army, Token Triumph)"
    assert a["estimate"].startswith("Dauer: mindestens ~8,9 min für bis zu 80 Partien")
    assert "Rotationsblock bei 4 Sitzen: 4 Seeds \u00d7 4 Sitze = 16 Paare je Arm" in a["block"]
    assert "kein Vielfaches von 16" in a["block"]
    three = out["three"]
    assert isinstance(three, dict)
    assert (
        three["plan"].endswith("seats_per_seed=3") and three["rotate"] == "Sitze 1\u20133 rotieren"
    )
    assert three["budgets"] == [27, 45, 63, 108, 207] and three["budget"] == "45"
    assert three["estimate"].startswith("Dauer: unbekannt (UNKNOWN) für bis zu 90 Partien")
    assert three["pods"][0] == "Precon (Lorehold Spirit, Animated Army)"
    body3 = out["body3"]
    assert isinstance(body3, dict)
    assert body3["table_seats"] == 3 and body3["pod"] == "precon" and body3["budget_pairs"] == 45
    down = out["down"]
    assert isinstance(down, dict)
    assert down["sizes"] == [["4 Sitze", False]] and down["seats"] == "4"
    assert down["note"] == "Tischgrößen nicht geladen: angeboten sind nur 4 Sitze."
    np = out["np"]
    assert isinstance(np, dict)
    assert np["pods"] == ["kein Preset für 3 Sitze"] and np["podDisabled"] and np["startDisabled"]
    assert out["npBody"] is None and out["npToasts"] == ["Für 3 Sitze gibt es keinen Gegnertisch."]


def test_series_dialog_plans_five_and_six_seats_once_the_server_releases_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With the constant raised (in memory, the server's answer changes, the page does not): five
    and six seats are selectable, the plan asks for N seats per seed, budgets are whole rotation
    blocks (25 or 36 pairs per arm), the duration is a floor with the throughput UNKNOWN, the
    preset of that size is offered and the start sends ``table_seats``."""
    tables = _tables_json(monkeypatch, 6)
    out = _paired_dialog(
        f"const d = await dialog({tables}); const r = {{}};"
        "for (const n of [5, 6]) { await d.choose('paired-table-select', n); r[n] = d.view(); r[n].body = await d.submit(); }"
        "await d.toggle(); r.off = d.view();"
        "console.log(JSON.stringify(r));"
    )
    for seats, budgets, budget, deck in (
        (5, [25, 50, 75, 100, 200], "50", "Veloci-Ramp-Tor"),
        (6, [36, 72, 108, 216], "72", "Blood Rites"),
    ):
        view = out[str(seats)]
        assert isinstance(view, dict)
        assert [s for s, disabled in view["sizes"] if disabled] == []
        assert view["plan"].endswith(f"seats_per_seed={seats}")
        assert view["budgets"] == budgets and view["budget"] == budget
        block = seats * seats
        assert f"{seats} Seeds \u00d7 {seats} Sitze = {block} Paare je Arm" in view["block"]
        assert "volle Blöcke" in view["block"] and "unvollständig" not in view["block"]
        assert f"Bei {seats} Sitzen ist der Durchsatz ungemessen (UNKNOWN)" in view["estimate"]
        assert "n = 1" in view["estimate"] and view["estimate"].startswith("Dauer: mindestens")
        assert view["rotate"] == f"Sitze 1\u2013{seats} rotieren"
        assert deck in view["pods"][0] and view["pods"][0].count(",") == seats - 2
        assert view["note"].startswith("Die Tischgröße ist eine eigene Schicht")
        body = view["body"]
        assert body["table_seats"] == seats and body["budget_pairs"] == int(budget)
        assert body["pod"] == "precon" and body["rotate_seats"] is True
    off = out["off"]
    assert isinstance(off, dict)
    assert off["plan"].endswith("seats_per_seed=1")
    assert off["block"].startswith("Ohne Rotation sitzt das getestete Deck immer auf Sitz 1")
    assert off["budgets"] == [20, 40, 60, 100, 200]
