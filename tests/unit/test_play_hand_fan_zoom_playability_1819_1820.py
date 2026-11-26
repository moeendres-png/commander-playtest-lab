"""Unit tests and static/authority checks for #1819 (fanned hand, hover, unified card zoom)
and #1820 (engine-derived hand playability, 4 German block-reason classes, mana preview & Undo).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = REPO_ROOT / "src" / "commander_lab" / "studio" / "static"
HAND_UX_JS = STATIC_DIR / "hand_ux.js"
PROMPTS_JS = STATIC_DIR / "prompts.js"
PARTIE_JS = STATIC_DIR / "partie.js"
PARTIE_HTML = STATIC_DIR / "partie.html"
PARTIE_CSS = STATIC_DIR / "partie.css"


def _run_node(script: str) -> dict[str, object]:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node binary unavailable")
    src = "\n".join(
        [
            PROMPTS_JS.read_text(encoding="utf-8"),
            HAND_UX_JS.read_text(encoding="utf-8"),
            script,
        ]
    )
    proc = subprocess.run([node, "-e", src], check=False, capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    return json.loads(lines[-1]) if lines else {}


def test_engine_authority_negative_control_and_four_block_reason_classes() -> None:
    """Frontend NEVER marks a hand card playable unless XMage offered it in legal_options.
    And blocked cards explicitly distinguish mana, phase, land_drop, and target_or_condition.
    """
    data = _run_node(
        """
const assert = require("assert");
const facts = {
  "Forest": { name: "Forest", type_line: "Basic Land — Forest", mana_cost: "", oracle_text: "" },
  "Island": { name: "Island", type_line: "Basic Land — Island", mana_cost: "", oracle_text: "" },
  "Sol Ring": { name: "Sol Ring", type_line: "Artifact", mana_cost: "{1}", oracle_text: "{T}: Add {C}{C}." },
  "Counterspell": { name: "Counterspell", type_line: "Instant", mana_cost: "{U}{U}", oracle_text: "Counter target spell." },
  "Cultivate": { name: "Cultivate", type_line: "Sorcery", mana_cost: "{2}{G}", oracle_text: "Search your library..." },
  "Swords to Plowshares": { name: "Swords to Plowshares", type_line: "Instant", mana_cost: "{W}", oracle_text: "Exile target creature." }
};

const player0 = {
  seat: 0,
  mana_pool: {},
  battlefield: [
    { object_id: "obj_plains", name: "Plains", tapped: false },
    { object_id: "obj_forest", name: "Forest", tapped: false }
  ]
};
facts["Plains"] = { name: "Plains", type_line: "Basic Land — Plains", mana_cost: "", oracle_text: "" };

const mainFrame = {
  turn: 3,
  phase: "precombat_main",
  step: "precombat_main",
  active_seat: 0,
  seat: 0,
  stack: [],
  players: [player0]
};

// Case 1: Only Sol Ring is offered by XMage; Forest (land already played), Counterspell (needs {U}{U}),
// Cultivate (needs {2}{G}, only {W}{G} untapped), and Swords (has {W}, no legal creature target!)
// are NOT in legal_options. Negative control proves frontend marks ONLY Sol Ring playable.
const hand = ["Sol Ring", "Forest", "Counterspell", "Cultivate", "Swords to Plowshares"];
const handIds = ["h_sol", "h_forest", "h_counter", "h_cultivate", "h_swords"];
const decisionMain = {
  decision_id: "dec_1",
  seat: 0,
  decision_class: "priority",
  legal_options: [
    { option_id: "opt_sol", option_type: "cast_spell", source_object_id: "h_sol", label: "Sol Ring — Cast Sol Ring" },
    { option_id: "opt_pass", option_type: "pass_priority", label: "Pass Priority" }
  ]
};

const classifiedMain = StudioHandUX.classifyHandCards(hand, handIds, {
  pendingDecision: decisionMain,
  frame: mainFrame,
  handSeat: 0,
  humanSeats: [0],
  facts,
  lastOwnPriority: null
});

const byName = Object.fromEntries(classifiedMain.map((c) => [c.name, c]));
assert.strictEqual(byName["Sol Ring"].status, "playable");
assert.strictEqual(byName["Sol Ring"].primaryOptionId, "opt_sol");
assert.strictEqual(byName["Forest"].status, "blocked");
assert.strictEqual(byName["Forest"].reasonClass, "land_drop");
assert.strictEqual(byName["Counterspell"].status, "blocked");
assert.strictEqual(byName["Counterspell"].reasonClass, "mana");
assert.ok(byName["Counterspell"].reasonText.includes("{U}"), byName["Counterspell"].reasonText);
assert.strictEqual(byName["Cultivate"].status, "blocked");
assert.strictEqual(byName["Cultivate"].reasonClass, "mana");
assert.strictEqual(byName["Swords to Plowshares"].status, "blocked");
assert.strictEqual(byName["Swords to Plowshares"].reasonClass, "target_or_condition");

// Negative control: even with abundant mana and main phase, if legal_options omits Cultivate,
// status MUST NOT be playable!
const richPlayer = {
  seat: 0,
  mana_pool: { green: 5 },
  battlefield: []
};
const richDecisionEmpty = { decision_id: "dec_empty", seat: 0, decision_class: "priority", legal_options: [{ option_id: "p", option_type: "pass_priority" }] };
const richClassified = StudioHandUX.classifyHandCards(["Cultivate"], ["h_cultivate"], {
  pendingDecision: richDecisionEmpty,
  frame: { ...mainFrame, players: [richPlayer] },
  handSeat: 0,
  humanSeats: [0],
  facts
});
assert.notStrictEqual(richClassified[0].status, "playable");

// Case 2: Phase block outside main phase / non-empty stack for sorcery/land
const combatFrame = { ...mainFrame, phase: "combat", step: "declare_attackers", stack: [] };
const classifiedCombat = StudioHandUX.classifyHandCards(["Cultivate", "Forest"], ["h_cultivate", "h_forest"], {
  pendingDecision: { decision_id: "dec_c", seat: 0, decision_class: "priority", legal_options: [{ option_id: "p", option_type: "pass_priority" }] },
  frame: combatFrame,
  handSeat: 0,
  humanSeats: [0],
  facts
});
assert.strictEqual(classifiedCombat[0].reasonClass, "phase");
assert.strictEqual(classifiedCombat[1].reasonClass, "phase");

// Case 3: Persistent playability indicator in own main phase outside active priority prompt (resting state)
const restingMain = StudioHandUX.classifyHandCards(["Sol Ring", "Counterspell"], ["h_sol", "h_counter"], {
  pendingDecision: null,
  frame: mainFrame,
  handSeat: 0,
  humanSeats: [0],
  facts,
  lastOwnPriority: { seat: 0, turn: 3, step: "precombat_main", legal_options: decisionMain.legal_options }
});
assert.strictEqual(restingMain[0].status, "playable");
assert.strictEqual(restingMain[1].status, "blocked");
assert.strictEqual(restingMain[1].reasonClass, "mana");

console.log(JSON.stringify({ ok: true }));
"""
    )
    assert data["ok"] is True


def test_mana_preview_auto_pay_and_undo_keep_stage() -> None:
    """Mana preview highlights matching untapped sources; Auto-Pay chooses ONLY from engine legal_options
    and fails closed when no offered source fits; Undo exposes cancel_mana_payment.
    """
    data = _run_node(
        """
const assert = require("assert");
const facts = {
  "Forest": { type_line: "Basic Land — Forest", mana_cost: "", oracle_text: "" },
  "Island": { type_line: "Basic Land — Island", mana_cost: "", oracle_text: "" },
  "Cultivate": { type_line: "Sorcery", mana_cost: "{2}{G}", oracle_text: "" }
};
const player = {
  seat: 0,
  mana_pool: { colorless: 1 },
  battlefield: [
    { object_id: "b_forest", name: "Forest", tapped: false },
    { object_id: "b_island", name: "Island", tapped: false },
    { object_id: "b_tapped", name: "Forest", tapped: true }
  ]
};
const preview = StudioHandUX.buildManaPreview("Cultivate", facts["Cultivate"], player, null, facts);
assert.strictEqual(preview.canCoverApprox, true);
assert.deepStrictEqual(preview.sourceObjectIds, ["b_forest", "b_island"]);
assert.ok(preview.poolSummary.includes("{C}"), preview.poolSummary);

const manaDecision = {
  decision_id: "mp_1",
  decision_class: "mana_payment",
  legal_options: [
    { option_id: "opt_pool", option_type: "spend_pool_mana", label: "Spend colorless mana from pool" },
    { option_id: "opt_forest", option_type: "mana_ability", source_object_id: "b_forest", label: "Tap Forest" },
    { option_id: "opt_cancel", option_type: "cancel_mana_payment", label: "Cancel" }
  ]
};
assert.strictEqual(StudioHandUX.nextAutoPayOptionId(manaDecision, preview.sourceObjectIds), "opt_pool");

const noPoolDecision = {
  decision_id: "mp_2",
  decision_class: "mana_payment",
  legal_options: [
    { option_id: "opt_forest", option_type: "mana_ability", source_object_id: "b_forest", label: "Tap Forest" },
    { option_id: "opt_cancel", option_type: "cancel_mana_payment", label: "Cancel" }
  ]
};
assert.strictEqual(StudioHandUX.nextAutoPayOptionId(noPoolDecision, preview.sourceObjectIds), "opt_forest");

// Fail-closed: if planned sources don't match any offered mana_ability, returns null instead of guessing!
assert.strictEqual(StudioHandUX.nextAutoPayOptionId(noPoolDecision, ["b_other"]), null);

const cancelOpt = StudioHandUX.findCancelManaOption(manaDecision);
assert.ok(cancelOpt && cancelOpt.option_id === "opt_cancel");
console.log(JSON.stringify({ ok: true }));
"""
    )
    assert data["ok"] is True


def test_fan_density_compression_and_static_guards_for_1819_1820() -> None:
    """Fan density scales across 12+ cards without inline styles; unified Card Zoom is wired across surfaces."""
    data = _run_node(
        """
const assert = require("assert");
assert.strictEqual(StudioHandUX.fanDensityClass(4), "fan-sparse");
assert.strictEqual(StudioHandUX.fanDensityClass(7), "fan-normal");
assert.strictEqual(StudioHandUX.fanDensityClass(10), "fan-compact");
assert.strictEqual(StudioHandUX.fanDensityClass(12), "fan-dense");
assert.strictEqual(StudioHandUX.fanDensityClass(15), "fan-ultra");
console.log(JSON.stringify({ ok: true }));
"""
    )
    assert data["ok"] is True

    html = PARTIE_HTML.read_text(encoding="utf-8")
    js = PARTIE_JS.read_text(encoding="utf-8")
    hand_js = HAND_UX_JS.read_text(encoding="utf-8")
    css = PARTIE_CSS.read_text(encoding="utf-8")

    assert 'id="hand-dock"' in html
    assert 'id="mana-stage-bar"' in html
    assert 'src="hand_ux.js"' in html
    assert 'id="preview-info"' in html
    assert "style=" not in html
    assert "style=" not in hand_js
    assert "style=" not in js

    # Unified zoom wired across Hand, Board, Stack, Log
    for fn_call in (
        "showCardZoom",
        "bindCardZoom",
        "handCardTile",
        "renderHandDock",
        "triggerCancelManaPayment",
    ):
        assert fn_call in js, fn_call
    for rule in (
        ".hand-dock",
        ".cards.hand-fan",
        ".hand-card",
        ".fan-dense",
        ".card-zoom-modal",
        ".mana-stage-bar",
    ):
        assert rule in css, rule
