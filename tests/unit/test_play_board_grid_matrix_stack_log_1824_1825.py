"""Tests for #1824 (PLAY responsive 2-6 seat grid, Focus/Grid toggle, Commander-Damage matrix,
danger frames, casting spotlight, non-negative eliminated life) and #1825 (ordered clickable
Stack rail, Icon-Tile Log collapsing >=5 identical triggers, log search, card zoom).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "src" / "commander_lab" / "studio" / "static"


def _run_node(script: str) -> dict:
    proc = subprocess.run(
        ["node", "-"],
        input=script,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"node failed ({proc.returncode}):\n{proc.stderr}"
    return json.loads(proc.stdout)


def test_board_ux_life_matrix_spotlight_stack_and_log() -> None:
    board_js = (STATIC / "board_ux.js").read_text(encoding="utf-8")
    play_p1a_js = (STATIC / "play_p1a.js").read_text(encoding="utf-8")
    out = _run_node(
        f"""
{play_p1a_js}
{board_js}
const seatName = (s) => `Sitz ${{s + 1}}`;

// 1. Grid mode classes for 2..6 seats + focus toggle
const grid6 = StudioBoardUX.gridModeClass(6, null);
const focus2 = StudioBoardUX.gridModeClass(6, 2);

// 2. Life status: negative life on eliminated seat must show 0, never negative
const elimNeg = StudioBoardUX.lifeStatus({{ seat: 3, life: -17, lost: true }});
const critical = StudioBoardUX.lifeStatus({{ seat: 1, life: 5, lost: false }});
const warn = StudioBoardUX.lifeStatus({{ seat: 2, life: 10, lost: false }});
const ok = StudioBoardUX.lifeStatus({{ seat: 0, life: 40, lost: false }});

// 3. Pairwise Commander-Damage matrix (15 warn, 21 lethal, never summed across commanders)
const matrixFrame = {{
  commanders: {{
    0: {{
      commanders: [{{ name: "Chulane, Teller of Tales", casts: 1 }}],
      received: [
        {{ fromSeat: 1, fromName: "Krenko, Mob Boss", total: 14 }},
        {{ fromSeat: 2, fromName: "Atraxa, Praetors' Voice", total: 15 }},
        {{ fromSeat: 3, fromName: "Yuriko, the Tiger's Shadow", total: 21 }}
      ]
    }}
  }}
}};
const matrix = StudioBoardUX.buildCommanderMatrix(matrixFrame, 0, seatName);

// 4. Casting spotlight on stack controller or active casting decision
const castFromStack = StudioBoardUX.detectCastingSeat(
  {{ seat: 0, decision_class: "priority", stack: ["Sol Ring"], stack_controllers: [2] }},
  null
);
const castFromDecision = StudioBoardUX.detectCastingSeat(
  {{ seat: 1, decision_class: "pay_mana", source: "Rhystic Study", stack: [] }},
  {{ seat: 1, decision_class: "pay_mana" }}
);

// 5. Ordered numbered Stack rail with 3 objects (source + published targets)
const pilotState = {{
  players: [
    {{ seat: 0, player_id: "p0", battlefield: [] }},
    {{ seat: 1, player_id: "p1", battlefield: [{{ object_id: "obj-sol", name: "Sol Ring" }}] }},
    {{ seat: 2, player_id: "p2", battlefield: [] }}
  ],
  stack: [
    {{ object_id: "st1", name: "Counterspell", controller_id: "p1", target_names: ["Cultivate"] }},
    {{ object_id: "st2", name: "stack ability (Rhystic Study: Whenever an opponent casts a spell)", controller_id: "p2", target_ids: ["p0"] }},
    {{ object_id: "st3", name: "Cultivate", controller_id: "p0", targets: [] }}
  ]
}};
const rawRail = StudioPlayP1a.buildStackRail(pilotState, seatName);
const stackRail = StudioBoardUX.annotateStackRail(rawRail, {{ "Rhystic Study": {{ type_line: "Enchantment" }} }});

// 6. Log classification & concise shortText without verbose rule-text dumps
const longAbilityLog = StudioBoardUX.classifyLogEntry(
  {{ seat: 2, decision_class: "trigger_order", source: "Rhystic Study", prompt: "Reihenfolge der ausgelösten Fähigkeiten wählen" }},
  "Fähigkeit: Rhystic Study: Whenever an opponent casts a spell, you may draw a card unless that player pays {{1}}.",
  {{ "Rhystic Study": {{ type_line: "Enchantment" }} }}
);
const hiddenLog = StudioBoardUX.classifyLogEntry(
  {{ seat: 1, decision_class: "choose_object", private_selection: true, source: "(verdeckt)" }},
  "wählt verdeckt (bis zum Spielende nicht sichtbar)",
  {{ "Secret Card": {{ type_line: "Instant" }} }}
);

console.log(JSON.stringify({{
  grid6, focus2, elimNeg, critical, warn, ok, matrix,
  castFromStack, castFromDecision, stackRail, longAbilityLog, hiddenLog
}}));
"""
    )

    assert out["grid6"] == ["seats-6"]
    assert out["focus2"] == ["seats-6", "focus-mode"]
    assert out["elimNeg"]["displayLife"] == 0
    assert out["elimNeg"]["dangerLevel"] == "eliminated"
    assert out["critical"]["dangerLevel"] == "critical"
    assert out["warn"]["dangerLevel"] == "warn"
    assert out["ok"]["dangerLevel"] == "ok"

    rows = out["matrix"]["rows"]
    assert [r["level"] for r in rows] == ["lethal", "warn", "normal"]
    assert "Tödlich" in rows[0]["badgeText"]
    assert "15+" in rows[1]["badgeText"]
    assert rows[2]["total"] == 14 and rows[2]["badgeText"] == ""

    assert out["castFromStack"]["seat"] == 2 and "Sol Ring" in out["castFromStack"]["label"]
    assert (
        out["castFromDecision"]["seat"] == 1 and "Rhystic Study" in out["castFromDecision"]["label"]
    )

    rail = out["stackRail"]
    assert len(rail) == 3
    assert rail[0]["orderLabel"].startswith("#1") and "löst zuerst auf" in rail[0]["orderLabel"]
    assert rail[1]["orderLabel"] == "#2" and rail[1]["zoomCardName"] == "Rhystic Study"
    assert rail[2]["orderLabel"] == "#3" and "Cultivate" in rail[2]["zoomCardName"]
    assert rail[0]["targetSummary"] == "Cultivate"
    assert rail[1]["targetSummary"] == "Sitz 1"

    assert out["longAbilityLog"]["icon"] == "⚡"
    assert out["longAbilityLog"]["kind"] == "trigger"
    assert out["longAbilityLog"]["cardName"] == "Rhystic Study"
    assert "draw a card" not in out["longAbilityLog"]["shortText"]
    assert "draw a card" in out["longAbilityLog"]["fullText"]
    assert out["longAbilityLog"]["hasExtraDetail"] is True
    assert out["longAbilityLog"]["collapseKey"] is not None

    assert out["hiddenLog"]["cardName"] is None


def test_partie_js_6_seat_matrix_focus_stack_and_50_event_collapsed_log() -> None:
    html = (STATIC / "partie.html").read_text(encoding="utf-8")
    css = (STATIC / "partie.css").read_text(encoding="utf-8")
    board_js = (STATIC / "board_ux.js").read_text(encoding="utf-8")
    prompts_js = (STATIC / "prompts.js").read_text(encoding="utf-8")
    hand_js = (STATIC / "hand_ux.js").read_text(encoding="utf-8")
    turn_bar_js = (STATIC / "turn_bar.js").read_text(encoding="utf-8")
    vorspulen_js = (STATIC / "vorspulen.js").read_text(encoding="utf-8")
    boardclick_js = (STATIC / "boardclick.js").read_text(encoding="utf-8")
    replay_js = (STATIC / "replay.js").read_text(encoding="utf-8")
    play_p1a_js = (STATIC / "play_p1a.js").read_text(encoding="utf-8")
    follow_js = (STATIC / "follow.js").read_text(encoding="utf-8")
    cohort_js = (STATIC / "cohort.js").read_text(encoding="utf-8")
    partie_js = (STATIC / "partie.js").read_text(encoding="utf-8")

    assert html.index('src="board_ux.js"') < html.index('src="partie.js"')
    assert 'id="table-mode-bar"' in html
    assert 'id="log-search"' in html
    assert "#table.seats-5,#table.seats-6{grid-template-columns:repeat(3,minmax(0,1fr))" in css
    assert ".seat.life-critical{" in css and ".cmd-dmg-chip.lethal{" in css

    # Verify static guards on board_ux.js
    for forbidden in ("innerHTML", "outerHTML", "style=", 'setAttribute("style"', ".toFixed("):
        assert forbidden not in board_js, f"board_ux.js must not contain {forbidden}"
    for sink in ("document.", "window.", "fetch(", "eval("):
        assert sink not in board_js, f"board_ux.js must remain pure without {sink}"

    # Boot partie.js in a rich lightweight DOM in Node and test 6 seats, Focus/Grid toggle,
    # Commander matrix, eliminated seat non-negative life, stack order, 55 log events + 5 triggers
    script = f"""
const elements = new Map();
function makeEl(tag, id) {{
  const listeners = new Map();
  const el = {{
    nodeType: 1,
    tagName: String(tag || "div").toUpperCase(),
    id: id || "",
    className: "",
    dataset: {{}},
    children: [],
    hidden: false,
    disabled: false,
    checked: false,
    value: "",
    options: [],
    title: "",
    style: {{}},
    parentNode: null,
    _text: "",
    classList: {{
      _set: new Set(),
      add(...cs) {{ cs.forEach(c => this._set.add(c)); el.className = [...this._set].join(" "); }},
      remove(...cs) {{ cs.forEach(c => this._set.delete(c)); el.className = [...this._set].join(" "); }},
      toggle(c, f) {{ if (f === undefined ? !this._set.has(c) : f) this._set.add(c); else this._set.delete(c); el.className = [...this._set].join(" "); }},
      contains(c) {{ return this._set.has(c); }}
    }},
    get textContent() {{
      return this._text + this.children.map(c => c.textContent || "").join(" ");
    }},
    set textContent(v) {{
      this._text = String(v ?? "");
      this.children = [];
    }},
    setAttribute(k, v) {{ this[k] = String(v); }},
    getAttribute(k) {{ return this[k] ?? null; }},
    append(...kids) {{
      for (const k of kids.flat()) {{
        if (k === null || k === undefined || k === false) continue;
        if (typeof k === "string" || typeof k === "number") {{
          this._text += String(k);
        }} else {{
          k.parentNode = this;
          this.children.push(k);
        }}
      }}
    }},
    replaceChildren(...kids) {{ this._text = ""; this.children = []; this.append(...kids); }},
    replaceWith(other) {{
      if (!this.parentNode) return;
      const idx = this.parentNode.children.indexOf(this);
      if (idx >= 0) {{ other.parentNode = this.parentNode; this.parentNode.children[idx] = other; }}
    }},
    remove() {{
      if (!this.parentNode) return;
      this.parentNode.children = this.parentNode.children.filter(c => c !== this);
    }},
    addEventListener(type, fn) {{
      if (!listeners.has(type)) listeners.set(type, []);
      listeners.get(type).push(fn);
    }},
    dispatch(type, ev) {{
      for (const fn of listeners.get(type) || []) fn(ev || {{ target: this, currentTarget: this, stopPropagation() {{}}, preventDefault() {{}} }});
    }},
    click() {{ this.dispatch("click"); }},
    closest() {{ return null; }},
    scrollIntoView() {{}},
    focus() {{}},
    querySelectorAll(sel) {{
      const out = [];
      const walk = (node) => {{
        for (const c of node.children || []) {{
          if (sel === "button:not([disabled])" && c.tagName === "BUTTON" && !c.disabled) out.push(c);
          if (sel === "input:not([disabled]), button:not([disabled])" && (c.tagName === "INPUT" || c.tagName === "BUTTON") && !c.disabled) out.push(c);
          walk(c);
        }}
      }};
      walk(this);
      return out;
    }},
    querySelector(sel) {{ return this.querySelectorAll(sel)[0] || null; }}
  }};
  return el;
}}
for (const id of [
  "brand", "top", "game-select", "sim-pill", "game-info", "concede-btn", "delete-game", "new-game",
  "bridge-status", "conn-status", "sr-announce", "controls", "replay-controls", "first", "prev-turn",
  "back", "play", "next", "next-turn", "turn-jump", "skip", "position", "replay-note", "speed",
  "response-mode-wrap", "response-mode", "halt-config-wrap", "halt-stack", "halt-combat", "halt-own-main",
  "halt-opp-end", "halt-playable", "hold-confirm-wrap", "hold-confirm-toggle", "auto-pass-wrap", "auto-pass-human",
  "ff-wrap", "ff-btn", "ff-mode", "ff-stack", "ff-stack-hint", "where", "ff-status",
  "phase-bar", "table-mode-bar", "board-bar", "table", "spectator-status", "human-decision", "now",
  "own-combat", "stack", "stack-count", "log-search", "log", "decision-bar", "hand-dock", "mana-stage-bar",
  "hand-title", "hand-summary", "hand", "preview", "preview-info", "board-menu", "board-links", "modal",
  "modal-box", "toast"
]) elements.set(id, makeEl(id === "log-search" ? "input" : "div", id));
elements.get("hold-confirm-toggle").checked = true;
elements.get("skip").checked = false;
elements.get("ff-stack").checked = true;

const document = {{
  getElementById: (id) => elements.get(id) || null,
  createElement: (tag) => makeEl(tag, ""),
  createTextNode: (t) => ({{ nodeType: 3, textContent: String(t) }}),
  addEventListener() {{}},
  querySelectorAll() {{ return []; }},
  querySelector() {{ return null; }},
  activeElement: null
}};
const window = {{ addEventListener() {{}}, location: {{ search: "" }}, innerWidth: 1280 }};
const location = window.location;
const history = {{ replaceState() {{}} }};
const sessionStorage = {{ getItem() {{ return null; }}, removeItem() {{}} }};
const StudioUI = {{
  germanError: (e) => String(e),
  classifyError: () => ({{ title: "F", sentence: "S", actions: [] }}),
  renderErrorCard: () => makeEl("div"),
  sanitizeTechnicalText: (s) => s,
  kids: (...a) => a.flat().filter(Boolean),
  setControlsBusy() {{}},
  createBusyView: () => null
}};

const players6 = Array.from({{ length: 6 }}, (_, s) => ({{
  seat: s,
  life: s === 1 ? 4 : s === 2 ? 9 : s === 3 ? -17 : 40,
  poison: 0,
  hand_count: 4,
  library_count: 80,
  lost: s === 3,
  won: false,
  battlefield: s === 0 ? [{{ object_id: "b1", name: "Sol Ring", tapped: false }}] : [],
  graveyard: [],
  command: ["Chulane, Teller of Tales"],
  command_ids: [`cmd-${{s}}`],
  exile_count: 0,
  exile: []
}}));

const frames = [];
// 45 distinct minor-free cast/action frames + 6 identical Rhystic Study triggers + 4 more events = 55 events
for (let i = 0; i < 45; i++) {{
  frames.push({{
    n: i + 1,
    turn: Math.floor(i / 4) + 1,
    phase: "precombat_main",
    step: "precombat_main",
    active_seat: i % 6,
    seat: i % 6,
    decision_class: "priority",
    prompt: "Priorität: wähle eine Aktion",
    options: 2,
    chosen: [`Sol Ring — Activate: {{T}}: Add {{C}}{{C}}.`],
    source: "Sol Ring",
    players: players6,
    stack: i === 44 ? ["Counterspell", "Sol Ring", "Cultivate"] : [],
    stack_ids: i === 44 ? ["s1", "s2", "s3"] : [],
    stack_controllers: i === 44 ? [2, 0, 1] : [],
    commanders: {{
      0: {{
        commanders: [{{ name: "Chulane, Teller of Tales", casts: 1 }}],
        received: [{{ fromSeat: 1, fromName: "Krenko", total: 16 }}, {{ fromSeat: 2, fromName: "Atraxa", total: 21 }}]
      }}
    }}
  }});
}}
for (let t = 0; t < 6; t++) {{
  frames.push({{
    n: 46 + t,
    turn: 12,
    phase: "precombat_main",
    step: "precombat_main",
    active_seat: 0,
    seat: 2,
    decision_class: "trigger_order",
    prompt: "Auslöser sortieren",
    options: 2,
    chosen: ["Fähigkeit: Rhystic Study: Whenever an opponent casts a spell, draw a card."],
    source: "Rhystic Study",
    players: players6,
    stack: ["Counterspell", "Sol Ring", "Cultivate"],
    stack_controllers: [2, 0, 1],
    commanders: frames[0].commanders
  }});
}}
for (let k = 0; k < 4; k++) {{
  frames.push({{
    n: 52 + k,
    turn: 12,
    phase: "combat",
    step: "declare_attackers",
    active_seat: 0,
    seat: 0,
    decision_class: "declare_attacker",
    prompt: "Angreifer bestimmen",
    options: 1,
    chosen: ["Chulane attacks Seat 2"],
    source: "Chulane, Teller of Tales",
    players: players6,
    stack: [],
    commanders: frames[0].commanders
  }});
}}

const fetch = async (path) => {{
  const ok = (payload) => ({{ ok: true, status: 200, statusText: "OK", json: async () => payload }});
  if (path === "/api/games") return ok([{{ game_id: "g6", running: false, frames: frames.length, header: {{ seats: players6.map((_, i) => ({{ seat: i, deck_id: `d${{i}}`, commanders: [`Cmd ${{i+1}}`] }})) }} }}]);
  if (path.startsWith("/api/games/g6?")) return ok({{
    start: 0, total: frames.length, running: false, interactive: false, cohort: "played",
    header: {{ seed: 42, engine_commit: "abc", seats: players6.map((_, i) => ({{ seat: i, deck_id: `d${{i}}`, commanders: [`Cmd ${{i+1}}`] }})) }},
    result: {{ status: "finished", winner_seats: [0] }},
    frames
  }});
  if (path === "/api/public-cards") return ok({{ "Sol Ring": {{ type_line: "Artifact" }}, "Rhystic Study": {{ type_line: "Enchantment" }} }});
  return ok({{}});
}};

{prompts_js}
{hand_js}
{turn_bar_js}
{board_js}
{vorspulen_js}
{boardclick_js}
{replay_js}
{play_p1a_js}
{follow_js}
{cohort_js}
{partie_js.replace("start();", "window.__bootPromise = start();")}

(async () => {{
  await window.__bootPromise;
  go(44);
  const tableEl = elements.get("table");
  const seatPanels = tableEl.children.filter(c => (c.className || "").includes("seat"));
  const elimSeat = seatPanels[3];
  const elimText = elimSeat.textContent;
  const stackNodes = elements.get("stack").children;

  // Toggle Focus Mode on seat 0
  toggleFocusSeat(0);
  const focusClasses = tableEl.className;
  const modeBarHiddenWhenFocused = elements.get("table-mode-bar").hidden;
  toggleFocusSeat(null);
  const gridClasses = tableEl.className;

  const logChildren = elements.get("log").children;
  const groupedTriggers = logChildren.filter(c => (c.className || "").includes("log-group-tile"));

  // Filter log by Rhystic
  elements.get("log-search").value = "Rhystic";
  elements.get("log-search").dispatch("input");
  const visibleAfterFilter = logChildren.filter(c => !c.hidden).length;

  console.log(JSON.stringify({{
    seatCount: seatPanels.length,
    elimContainsNeg17: elimText.includes("-17"),
    elimTextSample: elimText.slice(0, 60),
    seat1Danger: seatPanels[1].className,
    seat2Spotlight: seatPanels[2].className,
    focusClasses,
    modeBarHiddenWhenFocused,
    gridClasses,
    stackItems: stackNodes.length,
    stackFirstText: stackNodes[0] ? stackNodes[0].textContent : "",
    logTotalDomNodes: logChildren.length,
    groupedTriggerCount: groupedTriggers.length,
    firstGroupBadge: groupedTriggers[0] ? groupedTriggers[0].dataset.collapseCount : null,
    visibleAfterFilter
  }}));
}})();
"""
    out = _run_node(script)
    assert out["seatCount"] == 6
    assert out["elimContainsNeg17"] is False
    assert "ausgeschieden" in out["elimTextSample"]
    assert "life-critical" in out["seat1Danger"]
    assert "casting-spotlight" in out["seat2Spotlight"]
    assert "focus-mode" in out["focusClasses"]
    assert out["modeBarHiddenWhenFocused"] is False
    assert out["gridClasses"] == "seats-6"
    assert out["stackItems"] == 3
    assert "#1" in out["stackFirstText"]
    assert out["groupedTriggerCount"] == 1
    assert out["firstGroupBadge"] == "6"
    assert out["visibleAfterFilter"] >= 1
