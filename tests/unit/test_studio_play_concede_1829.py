"""Tests for #1829: PLAY concede immediate feedback, pending/spectator state, and confirmation modal."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from commander_lab.engine.rules.full_game import (
    FULL_GAME_DECISION_PROTOCOL_VERSION,
    FULL_GAME_EVIDENCE_CLASS,
    FULL_GAME_LANE,
    FullGameConformanceError,
)
from commander_lab.models import RulesDeckInput
from commander_lab.qualification.current_boundary.bridge_launcher import canonical_xmage_engine_pin
from commander_lab.studio import play
from commander_lab.studio.web import STATIC


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


def _pilot_state(*, seat: int, turn: int, active_player_id: str) -> dict[str, object]:
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
                "hand_count": 1,
                "library_count": 90,
                "hand": [{"name": "Forest"}],
                "battlefield": [],
                "graveyard": [],
                "command": [{"name": "Chulane, Teller of Tales"}],
                "exile": [],
            },
            {
                "seat": 1,
                "player_id": "p1",
                "life": 40,
                "hand_count": 1,
                "library_count": 90,
                "hand": [{"name": "Secret Opp Card"}],
                "battlefield": [],
                "graveyard": [],
                "command": [{"name": "Kinnan, Bonder Prodigy"}],
                "exile": [],
            },
        ],
        "stack": [],
    }


def _actor_view(status: dict[str, object]) -> dict[str, object]:
    decision = status.get("decision")
    pstate = decision.get("pilot_state") if isinstance(decision, dict) else None
    if not isinstance(decision, dict) or not isinstance(pstate, dict):
        return status
    actor_seat = decision.get("seat")
    players = pstate.get("players")
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


class _ConcedeFakeClient:
    """Fake bridge client exercising immediate vs. pending-decision concede behavior."""

    shutdown_disposition: str | None = None
    transport_failure: str | None = None
    exited = False
    killed = False

    def __init__(self, *, pending_after_concede: bool, fail_on_concede: bool = False) -> None:
        self.pending_after_concede = pending_after_concede
        self.fail_on_concede = fail_on_concede
        self.conceded = False
        self.answered_final = False
        self.submitted_responses: list[dict[str, object]] = []

    def __enter__(self) -> _ConcedeFakeClient:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def start(self) -> None:
        return None

    def close(self) -> str:
        return "graceful_shutdown"

    def process_exited(self) -> bool:
        return self.exited

    def kill(self) -> None:
        self.killed = True

    def _human_decision(self) -> dict[str, object]:
        return {
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
                {"option_id": "pass-1", "option_type": "pass_priority", "label": "Pass priority"},
            ],
            "pilot_state": _pilot_state(seat=0, turn=1, active_player_id="p0"),
        }

    def _status(self) -> dict[str, object]:
        if not self.conceded:
            return _actor_view(
                {
                    "terminal": False,
                    "outcomes": [
                        {"seat": 0, "player_id": "p0", "life": 40, "can_concede": True},
                        {"seat": 1, "player_id": "p1", "life": 40, "can_concede": True},
                    ],
                    "decision": self._human_decision(),
                }
            )
        if self.pending_after_concede and not self.answered_final:
            return _actor_view(
                {
                    "terminal": False,
                    "outcomes": [
                        {"seat": 0, "player_id": "p0", "life": 40, "can_concede": False},
                        {"seat": 1, "player_id": "p1", "life": 40, "can_concede": True},
                    ],
                    "decision": self._human_decision(),
                }
            )
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
                    "conceded": True,
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
            return {
                "player_count": len(payload["deck_handles"]),  # type: ignore[arg-type]
                "seed": payload["seed"],
                "evidence_class": FULL_GAME_EVIDENCE_CLASS,
                "holdout_consumed": False,
            }
        if method == "start_full_game":
            return self._status()
        if method == "get_concede_offer":
            return {"concede_available": not self.conceded}
        if method == "submit_concede":
            if self.fail_on_concede:
                return {"terminal": False, "failure": {"message": "boom"}, "decision": None}
            self.conceded = True
            # When immediate elimination returns decision=None, terminal=False transiently,
            # play.py must probe next_decision once so state updates immediately.
            if not self.pending_after_concede:
                return {"terminal": False, "decision": None, "outcomes": []}
            return self._status()
        if method == "get_full_game_decision":
            return self._status()
        if method == "submit_full_game_decision":
            response = payload.get("response")
            assert isinstance(response, dict)
            self.submitted_responses.append(dict(response))
            self.answered_final = True
            return self._status()
        if method == "export_event_log":
            offset = int(payload.get("after_offset", 0))  # type: ignore[call-overload]
            events = [{"turn": 1, "text": "Game started"}]
            return {"events": events[offset:], "latest_offset": len(events)}
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
                "turn_number": 1,
                "decision_count": len(self.submitted_responses),
                "terminal": True,
                "transcript": [],
                "outcomes": [
                    {"seat": 0, "life": 40, "won": False, "lost": True, "left": True},
                    {"seat": 1, "life": 40, "won": True, "lost": False, "left": False},
                ],
            }
        raise AssertionError(f"unexpected bridge method: {method}")


def _wait_ready_decision(session: play.InteractiveGameSession, decision_id: str) -> None:
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        snap = session.snapshot()
        pending = snap.get("pending_decision")
        if isinstance(pending, dict) and pending.get("decision_id") == decision_id:
            return
        assert snap.get("running") is True, snap
        time.sleep(0.01)
    raise AssertionError("timed out waiting for pending_decision")


def test_interactive_concede_immediate_vs_pending_decision_and_duplicate_guard(
    tmp_path: Path,
) -> None:
    decks = (
        _make_deck("own", "Chulane, Teller of Tales"),
        _make_deck("opp", "Kinnan, Bonder Prodigy"),
    )

    # 1. Immediate elimination path (probes next_decision when engine returns decision=None)
    client_imm = _ConcedeFakeClient(pending_after_concede=False)
    prep1 = play.prepare_game(
        decks,
        seed=42,
        game_id="g-imm",
        human_seats=[0],
        decision_timeout_seconds=0,
        jar_sha256="abc",
    )
    sess1 = play.InteractiveGameSession(
        tmp_path / "s1",
        prep1,
        human_seats=[0],
        decision_timeout_seconds=0,
        ai_delay_ms=0,
        command=["fake"],
        client_factory=lambda *a, **k: client_imm,
    )
    sess1.start()
    try:
        _wait_ready_decision(sess1, "dec-h-1")
        res1 = sess1.concede(0)
        assert res1 == {
            "conceded": True,
            "seat": 0,
            "concede_pending_decision": False,
            "eliminated": True,
        }
        assert client_imm.submitted_responses == []  # never fabricated a fake decision!
        snap1 = sess1.snapshot()
        assert snap1["can_concede"] is False
        assert snap1["conceded_seats"] == [0]
        assert snap1["eliminated_seats"] == [0]
        assert snap1["concede_pending_decision"] is False
    finally:
        sess1.shutdown()

    # 2. Pending decision remains: do NOT fabricate response; report pending cleanly until answered
    client_pend = _ConcedeFakeClient(pending_after_concede=True)
    prep2 = play.prepare_game(
        decks,
        seed=42,
        game_id="g-pend",
        human_seats=[0],
        decision_timeout_seconds=0,
        jar_sha256="abc",
    )
    sess2 = play.InteractiveGameSession(
        tmp_path / "s2",
        prep2,
        human_seats=[0],
        decision_timeout_seconds=0,
        ai_delay_ms=0,
        command=["fake"],
        client_factory=lambda *a, **k: client_pend,
    )
    sess2.start()
    try:
        _wait_ready_decision(sess2, "dec-h-1")
        res2 = sess2.concede(0)
        assert res2 == {
            "conceded": True,
            "seat": 0,
            "concede_pending_decision": True,
            "eliminated": False,
        }
        assert client_pend.submitted_responses == []
        snap2 = sess2.snapshot()
        assert snap2["can_concede"] is False
        assert snap2["conceded_seats"] == [0]
        assert snap2["eliminated_seats"] == []
        assert snap2["concede_pending_decision"] is True

        # Duplicate concede stays rejected cleanly (422-mapped ValueError)
        with pytest.raises(ValueError, match="Aufgeben"):
            sess2.concede(0)

        # Answering the final open decision completes elimination cleanly
        accepted = sess2.submit_decision(
            {"decision_id": "dec-h-1", "selected_option_ids": ["pass-1"], "ordering": []}
        )
        assert accepted["accepted"] is True
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and sess2.is_running:
            time.sleep(0.01)
        snap2_end = sess2.snapshot()
        assert snap2_end["eliminated_seats"] == [0]
        assert snap2_end["concede_pending_decision"] is False
    finally:
        sess2.shutdown()

    # 3. Bridge failure payload on submit_concede fails closed without recording conceded: True
    client_fail = _ConcedeFakeClient(pending_after_concede=False, fail_on_concede=True)
    prep3 = play.prepare_game(
        decks,
        seed=42,
        game_id="g-fail",
        human_seats=[0],
        decision_timeout_seconds=0,
        jar_sha256="abc",
    )
    sess3 = play.InteractiveGameSession(
        tmp_path / "s3",
        prep3,
        human_seats=[0],
        decision_timeout_seconds=0,
        ai_delay_ms=0,
        command=["fake"],
        client_factory=lambda *a, **k: client_fail,
    )
    sess3.start()
    try:
        _wait_ready_decision(sess3, "dec-h-1")
        with pytest.raises(FullGameConformanceError):
            sess3.concede(0)
        assert sess3.snapshot()["conceded_seats"] == []
    finally:
        sess3.shutdown()


def test_partie_frontend_replaces_native_confirm_and_shows_concede_feedback() -> None:
    html = (STATIC / "partie.html").read_text(encoding="utf-8")
    css = (STATIC / "partie.css").read_text(encoding="utf-8")
    js = (STATIC / "partie.js").read_text(encoding="utf-8")

    assert '<div id="spectator-status" class="spectator-status"' in html
    assert "confirm(" not in js
    assert "formatPlayError" in js
    assert "openConfirmModal" in js
    assert ".spectator-status.pending" in css
    assert ".spectator-status.eliminated" in css
    assert ".concede-pending-note" in css
    assert ".confirm-dialog" in css
    assert "#0d131d" not in css

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")

    format_slice = js[js.index("function toast(") : js.index("const seatName =")]
    ff_slice = js[
        js.index("function renderFastForwardButton()") : js.index("async function setAiDelay(")
    ]
    show_list_slice = js[js.index("function showList(") : js.index("function showZone(")]
    human_slice = js[
        js.index("function isHumanSpectator()") : js.index("function renderBridgeBanner()")
    ]
    modal_slice = js[
        js.index("let activeConfirmResolve = null;") : js.index("async function listGames(")
    ]

    script = f"""
const assert = require("assert");
const elements = new Map();
function makeEl(tag, id) {{
  const el = {{
    tagName: String(tag || "").toUpperCase(),
    id: id || "",
    className: "",
    textContent: "",
    hidden: false,
    disabled: false,
    dataset: {{}},
    attributes: {{}},
    children: [],
    listeners: {{}},
    isConnected: true,
    focusCalled: false,
    classList: {{
      _s: new Set(),
      add(c) {{ this._s.add(c); }},
      remove(c) {{ this._s.delete(c); }},
    }},
    setAttribute(k, v) {{ this.attributes[k] = String(v); }},
    append(...nodes) {{
      const flat = nodes.flat().filter((n) => n !== null && n !== undefined);
      this.children.push(...flat);
      this.textContent += flat.map((n) => (typeof n === "string" ? n : n.textContent || "")).join("");
    }},
    focus() {{ this.focusCalled = true; document.activeElement = this; }},
    querySelectorAll() {{ return []; }},
  }};
  if (el.id) elements.set(el.id, el);
  return el;
}}
for (const id of ["toast", "modal", "modal-box", "spectator-status", "human-decision", "concede-btn", "auto-pass-wrap", "ff-btn", "ff-wrap"]) {{
  const el = makeEl("div", id);
  if (id === "modal" || id === "spectator-status" || id === "human-decision") el.hidden = true;
}}
global.document = {{ activeElement: elements.get("concede-btn") }};
const $ = (id) => elements.get(id) || null;
const h = (tag, props, ...children) => {{
  const el = makeEl(tag, props && props.id);
  for (const [k, v] of Object.entries(props || {{}})) {{
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el[k] = v;
    else if (k in el) el[k] = v;
    else el.setAttribute(k, v);
  }}
  el.append(...children);
  return el;
}};
let toastTimer = 0;
const state = {{
  interactive: true,
  running: true,
  humanSeats: [0],
  pendingDecision: {{
    decision_id: "dec-h-1",
    seat: 0,
    decision_class: "priority",
    prompt: "Pass?",
    minimum_selections: 1,
    maximum_selections: 1,
    legal_options: [{{ option_id: "pass-1", option_type: "pass_priority", label: "Pass priority" }}],
  }},
  pendingDecisionId: null,
  selectedOptions: [],
  orderList: [],
  submitting: false,
  canConcede: true,
  concededSeats: [],
  eliminatedSeats: [],
  concedePendingDecision: false,
  conceding: false,
  frames: [],
  click: null,
  ff: {{ on: false }},
}};
const CLASSES = {{ priority: "Aktion" }};
const OPTION_TYPES = {{ pass_priority: "Passen" }};
const seatName = (s) => `Sitz ${{s + 1}}`;
const localizeActionText = (t) => String(t);
const maybeAutoPassHuman = () => false;
const closeBoardMenu = () => {{}};
const renderBoardBar = () => {{}};
const announceDecision = () => {{}};
const StudioBoardClick = {{ build: () => ({{}}) }};

{format_slice}
{ff_slice}
{show_list_slice}
{modal_slice}
{human_slice}

async function run() {{
  // 1. Cancel confirmation modal resolves false and restores focus
  const pCancel = openConfirmModal({{ title: "Aufgeben?", message: "Sicher?", confirmLabel: "Aufgeben", danger: true }});
  assert.strictEqual(elements.get("modal").hidden, false);
  elements.get("confirm-cancel").onclick();
  assert.strictEqual(await pCancel, false);
  assert.strictEqual(elements.get("modal").hidden, true);
  assert.strictEqual(document.activeElement, elements.get("concede-btn"));

  // 2. Backdrop/Escape cancels modal cleanly; showList resolves pending modal false
  const pEsc = openConfirmModal({{ title: "Löschen?", message: "Wirklich?" }});
  closeActiveModal(false);
  assert.strictEqual(await pEsc, false);
  const pHijack = openConfirmModal({{ title: "Offen?", message: "Test" }});
  showList("Friedhof", [], [], "0:graveyard");
  assert.strictEqual(await pHijack, false);
  elements.get("modal").hidden = true;

  // 3. Confirm resolves true
  const pOk = openConfirmModal({{ title: "Aufgeben?", message: "Ja", danger: true }});
  elements.get("confirm-ok").onclick();
  assert.strictEqual(await pOk, true);

  // 4. Concede pending decision state shows warning in BOTH #spectator-status and #human-decision
  state.concededSeats = [0];
  state.concedePendingDecision = true;
  state.canConcede = false;
  renderHumanDecision();
  assert.strictEqual(elements.get("spectator-status").hidden, false);
  assert.ok(elements.get("spectator-status").textContent.includes("Aufgabe vorgemerkt"));
  assert.ok(elements.get("human-decision").textContent.includes("Aufgabe vorgemerkt"));
  assert.strictEqual(elements.get("concede-btn").hidden, true);

  // 5. After elimination, #spectator-status switches to Zuschauer-Modus and #ff-wrap hides
  state.concedePendingDecision = false;
  state.eliminatedSeats = [0];
  state.pendingDecision = null;
  renderHumanDecision();
  assert.strictEqual(elements.get("spectator-status").hidden, false);
  assert.ok(elements.get("spectator-status").textContent.includes("Zuschauer-Modus"));
  assert.strictEqual(elements.get("concede-btn").hidden, true);
  assert.strictEqual(elements.get("ff-wrap").hidden, true);

  // 6. Ended game distinguishes natural loss vs. conceded seat in spectator banner
  state.running = false;
  state.concededSeats = [];
  renderSpectatorStatus();
  assert.ok(elements.get("spectator-status").textContent.includes("Du bist ausgeschieden — Partie beendet"));
  state.concededSeats = [0];
  renderSpectatorStatus();
  assert.ok(elements.get("spectator-status").textContent.includes("Du hast aufgegeben — Partie beendet"));

  // 7. formatPlayError maps network errors cleanly without English raw message
  assert.strictEqual(formatPlayError(new Error("Failed to fetch")), "Server nicht erreichbar.");
}}

run().then(() => console.log(JSON.stringify({{ ok: true }}))).catch((e) => {{ console.error(e); process.exit(1); }});
"""
    res = subprocess.run([node, "-e", script], check=False, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr or res.stdout
    assert json.loads(res.stdout.strip()) == {"ok": True}
    assert re.search(r"async\s+function\s+start\b", js)
