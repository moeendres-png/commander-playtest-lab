"""Unit tests and static/authority checks for #1822 (always-visible phase bar, waiting seat,
3 response profiles with fail-safe interrupt table) and #1823 (unified decision bar,
"Nichts mehr zu tun" state, configurable Hold-to-Confirm on critical passes).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = REPO_ROOT / "src" / "commander_lab" / "studio" / "static"
TURN_BAR_JS = STATIC_DIR / "turn_bar.js"
PARTIE_HTML = STATIC_DIR / "partie.html"
PARTIE_JS = STATIC_DIR / "partie.js"
PARTIE_CSS = STATIC_DIR / "partie.css"


def _run_node(script: str) -> dict[str, object]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node binary unavailable")
    src = "\n".join([TURN_BAR_JS.read_text(encoding="utf-8"), script])
    proc = subprocess.run([node, "-e", src], check=False, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    return json.loads(lines[-1]) if lines else {}


def test_phase_timeline_and_waiting_seat_projection() -> None:
    """Phase timeline highlights active step and waiting seat matches pending/frame."""
    data = _run_node(
        """
const assert = require("assert");
const frameCombat = {
  turn: 4,
  phase: "combat",
  step: "declare_blockers",
  active_seat: 1,
  seat: 0,
  players: [
    { seat: 0, player_id: "p0" },
    { seat: 1, player_id: "p1" }
  ]
};
const tl = StudioTurnBar.buildPhaseTimeline(frameCombat);
assert.strictEqual(tl.turn, 4);
assert.strictEqual(tl.phaseKey, "combat");
assert.strictEqual(tl.stepKey, "declare_blockers");
assert.strictEqual(tl.activeStepLabel, "Blocker");
const byKey = Object.fromEntries(tl.phases.map((p) => [p.key, p.state]));
assert.strictEqual(byKey.beginning, "done");
assert.strictEqual(byKey.precombat_main, "done");
assert.strictEqual(byKey.combat, "active");
assert.strictEqual(byKey.postcombat_main, "upcoming");
assert.strictEqual(byKey.end, "upcoming");

const waitHuman = StudioTurnBar.buildWaitingInfo(frameCombat, {
  decision_id: "d1",
  seat: 0,
  decision_class: "declare_blocker",
  pilot_state: { active_player_id: "p1", players: frameCombat.players }
}, { humanSeats: [0], running: true, interactive: true });
assert.strictEqual(waitHuman.waitingSeat, 0);
assert.strictEqual(waitHuman.isHumanWaiting, true);
assert.ok(waitHuman.bannerText.includes("Sitz 1"));

const waitOpp = StudioTurnBar.buildWaitingInfo({ ...frameCombat, seat: 2 }, null, {
  humanSeats: [0], running: true, interactive: true
});
assert.strictEqual(waitOpp.waitingSeat, 2);
assert.strictEqual(waitOpp.isHumanWaiting, false);
assert.ok(waitOpp.badgeLabel.includes("Sitz 3"));
console.log(JSON.stringify({ ok: true }));
"""
    )
    assert data["ok"] is True


def test_three_response_profiles_and_fail_safe_interrupt_holds() -> None:
    """Auto-pass never skips configured halt events (triggers on stack, combat, playable options)
    or unknown steps; Full Control never auto-passes; Big Moments vs Auto-Pass differ cleanly.
    """
    data = _run_node(
        """
const assert = require("assert");
const players = [
  { seat: 0, player_id: "p0" },
  { seat: 1, player_id: "p1" }
];
const basePriority = (step, stack = [], extraOpts = []) => ({
  decision_id: "d_prio",
  seat: 0,
  decision_class: "priority",
  legal_options: [
    { option_id: "opt_pass", option_type: "pass_priority", label: "Pass Priority" },
    ...extraOpts
  ],
  pilot_state: { active_player_id: "p1", step, players, stack }
});

// 1. Trigger event on stack MUST halt even under auto_pass when haltStackNonEmpty is enabled!
const trigPriority = basePriority("upkeep", [{ object_id: "s1", name: "Rhystic Study Trigger", face_down: false }]);
const autoOnTrigger = StudioTurnBar.evaluateResponseProfile(
  trigPriority,
  "auto_pass",
  { haltStackNonEmpty: true, haltCombat: true, haltOwnMain: true, haltOpponentEndStep: false, haltPlayableOptions: true }
);
assert.strictEqual(autoOnTrigger.action, "stop");
assert.ok(autoOnTrigger.reason.includes("Rhystic Study Trigger"));

// 2. Empty opponent upkeep stops in full_control, stops in big_moments? No: big_moments only holds big moments!
const routineUpkeep = basePriority("upkeep", []);
assert.strictEqual(StudioTurnBar.evaluateResponseProfile(routineUpkeep, "full_control").action, "stop");
assert.strictEqual(StudioTurnBar.evaluateResponseProfile(routineUpkeep, "big_moments").action, "pass");
assert.strictEqual(StudioTurnBar.evaluateResponseProfile(routineUpkeep, "auto_pass").action, "pass");

// 3. Opponent end step differs between big_moments (halt) and auto_pass default (pass)!
const oppEndStep = basePriority("end_turn", []);
assert.strictEqual(StudioTurnBar.evaluateResponseProfile(oppEndStep, "big_moments").action, "stop");
assert.strictEqual(StudioTurnBar.evaluateResponseProfile(oppEndStep, "auto_pass").action, "pass");

// 4. Unknown step MUST fail-safe halt under ALL modes including auto_pass!
const unknownStep = basePriority("mystery_step", []);
assert.strictEqual(StudioTurnBar.evaluateResponseProfile(unknownStep, "auto_pass").action, "stop");
assert.ok(StudioTurnBar.evaluateResponseProfile(unknownStep, "auto_pass").reason.includes("fail-safe"));

// 5. Non-priority decision and missing activeSeat MUST fail-safe halt!
assert.strictEqual(
  StudioTurnBar.evaluateResponseProfile({ decision_class: "target", legal_options: [] }, "auto_pass").action,
  "stop"
);
const missingActive = basePriority("precombat_main", []);
missingActive.pilot_state = { step: "precombat_main", players, stack: [] };
assert.strictEqual(StudioTurnBar.evaluateResponseProfile(missingActive, "big_moments").action, "stop");
console.log(JSON.stringify({ ok: true }));
"""
    )
    assert data["ok"] is True


def test_primary_decision_bar_nothing_left_and_hold_to_confirm() -> None:
    """Primary Decision Bar surfaces plain German verb, "Nichts mehr zu tun" on pass-only windows,
    and Hold-to-Confirm on critical pass windows while toggleable off.
    """
    data = _run_node(
        """
const assert = require("assert");
const passOnly = {
  decision_id: "d_empty",
  seat: 0,
  decision_class: "priority",
  legal_options: [{ option_id: "opt_pass", option_type: "pass_priority", label: "Pass Priority" }],
  pilot_state: { active_player_id: "p0", step: "precombat_main", stack: [], players: [{ seat: 0, player_id: "p0" }] }
};
const actEmpty = StudioTurnBar.buildPrimaryAction(passOnly, [], null, { holdToConfirm: true });
assert.strictEqual(actEmpty.nothingLeft, true);
assert.strictEqual(actEmpty.requireHold, false);
assert.ok(actEmpty.label.includes("Nichts mehr zu tun"));

// Critical window: opponent cast on stack -> requires Hold-to-Confirm when toggle active!
const criticalStack = {
  decision_id: "d_crit",
  seat: 0,
  decision_class: "priority",
  legal_options: [{ option_id: "opt_pass", option_type: "pass_priority", label: "Pass Priority" }],
  pilot_state: { active_player_id: "p1", step: "precombat_main", stack: [{ object_id: "sp1", name: "Cyclonic Rift" }], players: [{ seat: 0, player_id: "p0" }, { seat: 1, player_id: "p1" }] }
};
const actHold = StudioTurnBar.buildPrimaryAction(criticalStack, [], null, { holdToConfirm: true });
assert.strictEqual(actHold.critical, true);
assert.strictEqual(actHold.requireHold, true);

// When user disables Hold-to-Confirm setting, single-click is restored immediately:
const actNoHold = StudioTurnBar.buildPrimaryAction(criticalStack, [], null, { holdToConfirm: false });
assert.strictEqual(actNoHold.requireHold, false);

// Blockers decision primary verb
const blockAct = StudioTurnBar.buildPrimaryAction({ decision_id: "db", seat: 0, decision_class: "declare_blocker", legal_options: [] }, [], null, {});
assert.strictEqual(blockAct.label, "Nicht blocken (Weiter)");
const blockPicked = StudioTurnBar.buildPrimaryAction({ decision_id: "db", seat: 0, decision_class: "declare_blocker", legal_options: [] }, ["att1"], null, {});
assert.strictEqual(blockPicked.label, "Blocker ansagen (1)");

// trigger_order single-selection (1-of-1) must NOT produce confirm_order; numeric must focus_panel
const singleTrig = StudioTurnBar.buildPrimaryAction({ decision_id: "to1", seat: 0, decision_class: "trigger_order", minimum_selections: 1, maximum_selections: 1, legal_options: [{ option_id: "o1" }] }, [], null, {});
assert.strictEqual(singleTrig.kind, "option");
const numAct = StudioTurnBar.buildPrimaryAction({ decision_id: "nx1", seat: 0, decision_class: "announce_x", minimum_selections: 0, maximum_selections: 0, legal_options: [], context: { numeric_min: 0, numeric_max: 5 } }, [], null, {});
assert.strictEqual(numAct.kind, "focus_panel");
console.log(JSON.stringify({ ok: true }));
"""
    )
    assert data["ok"] is True


def test_board_bar_hold_predicate_should_require_hold_to_confirm() -> None:
    """The board bar's pass button asks StudioTurnBar.shouldRequireHoldToConfirm before it
    binds a plain click (#1822 audit finding: the function was called in partie.js but defined
    nowhere, so the board bar never required the hold). The predicate must exist and must
    agree with the decision bar's requireHold for the same windows.
    """
    data = _run_node(
        """
const assert = require("assert");
assert.strictEqual(typeof StudioTurnBar.shouldRequireHoldToConfirm, "function");

const passOnly = {
  decision_id: "d_empty",
  seat: 0,
  decision_class: "priority",
  legal_options: [{ option_id: "opt_pass", option_type: "pass_priority", label: "Pass Priority" }],
  pilot_state: { active_player_id: "p0", step: "precombat_main", stack: [], players: [{ seat: 0, player_id: "p0" }] }
};
const criticalStack = {
  decision_id: "d_crit",
  seat: 0,
  decision_class: "priority",
  legal_options: [{ option_id: "opt_pass", option_type: "pass_priority", label: "Pass Priority" }],
  pilot_state: { active_player_id: "p1", step: "precombat_main", stack: [{ object_id: "sp1", name: "Cyclonic Rift" }], players: [{ seat: 0, player_id: "p0" }, { seat: 1, player_id: "p1" }] }
};
const combatStep = {
  decision_id: "d_combat",
  seat: 0,
  decision_class: "priority",
  legal_options: [{ option_id: "opt_pass", option_type: "pass_priority", label: "Pass Priority" }],
  pilot_state: { active_player_id: "p1", step: "declare_blockers", stack: [], players: [{ seat: 0, player_id: "p0" }, { seat: 1, player_id: "p1" }] }
};
const withOtherOption = {
  decision_id: "d_other",
  seat: 0,
  decision_class: "priority",
  legal_options: [
    { option_id: "opt_pass", option_type: "pass_priority", label: "Pass Priority" },
    { option_id: "opt_bolt", option_type: "cast_spell", label: "Lightning Bolt" }
  ],
  pilot_state: { active_player_id: "p0", step: "precombat_main", stack: [], players: [{ seat: 0, player_id: "p0" }] }
};

// the board bar calls it exactly like this: (pending, null, { holdToConfirm })
assert.strictEqual(StudioTurnBar.shouldRequireHoldToConfirm(criticalStack, null, { holdToConfirm: true }), true);
assert.strictEqual(StudioTurnBar.shouldRequireHoldToConfirm(combatStep, null, { holdToConfirm: true }), true);
assert.strictEqual(StudioTurnBar.shouldRequireHoldToConfirm(withOtherOption, null, { holdToConfirm: true }), true);
assert.strictEqual(StudioTurnBar.shouldRequireHoldToConfirm(passOnly, null, { holdToConfirm: true }), false);
// the setting wins over the window: switched off, a plain click passes even in a critical window
assert.strictEqual(StudioTurnBar.shouldRequireHoldToConfirm(criticalStack, null, { holdToConfirm: false }), false);
// no priority decision, no hold
assert.strictEqual(StudioTurnBar.shouldRequireHoldToConfirm({ decision_class: "declare_blocker", legal_options: [] }, null, { holdToConfirm: true }), false);
assert.strictEqual(StudioTurnBar.shouldRequireHoldToConfirm(null, null, { holdToConfirm: true }), false);

// and it must never drift from the decision bar's own rule for the same window
for (const pending of [passOnly, criticalStack, combatStep, withOtherOption]) {
  for (const holdToConfirm of [true, false]) {
    const viaBar = StudioTurnBar.buildPrimaryAction(pending, [], null, { holdToConfirm }).requireHold;
    assert.strictEqual(StudioTurnBar.shouldRequireHoldToConfirm(pending, null, { holdToConfirm }), viaBar);
  }
}
console.log(JSON.stringify({ ok: true }));
"""
    )
    assert data["ok"] is True
    # the call site in the board bar must stay: if it goes, this test stops covering the path
    partie_js = PARTIE_JS.read_text(encoding="utf-8")
    assert "StudioTurnBar.shouldRequireHoldToConfirm(pending, null" in partie_js


def test_turn_bar_static_guards_and_vorspulen_compat() -> None:
    """Zero inline style=, tabindex, or undo in JS/HTML; #1662 vorspulen controls preserved."""
    html = PARTIE_HTML.read_text(encoding="utf-8")
    js = PARTIE_JS.read_text(encoding="utf-8")
    tb_js = TURN_BAR_JS.read_text(encoding="utf-8")
    css = PARTIE_CSS.read_text(encoding="utf-8")

    for tok in (
        'id="phase-bar"',
        'id="decision-bar"',
        'id="response-mode"',
        'id="hold-confirm-toggle"',
        'id="auto-pass-human"',
        'id="ff-btn"',
        'id="ff-mode"',
        'src="turn_bar.js"',
    ):
        assert tok in html, tok
    assert "style=" not in html
    assert "style=" not in tb_js
    assert "style=" not in js
    assert "tabindex" not in js
    assert "undo" not in js.lower()
    for sym in ("renderPhaseBar", "renderDecisionBar", "bindHoldToConfirmButton"):
        assert sym in js, sym
    for rule in (
        ".phase-bar",
        ".decision-bar",
        ".decision-primary-btn.nothing-left",
        ".hold-confirm-btn.holding",
        ".seat.waiting-decision",
    ):
        assert rule in css, rule
