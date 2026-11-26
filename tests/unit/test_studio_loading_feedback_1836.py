"""Tests for Issue #1836 cross-cutting Studio loading & progress feedback."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "src" / "commander_lab" / "studio" / "static"


def test_create_busy_view_timer_cleanup_and_ref_counted_controls_in_node() -> None:
    node = shutil.which("node")
    assert node is not None
    script = f"""
const fs = require('fs');
const path = require('path');
const staticDir = {json.dumps(str(STATIC))};
const windowObj = {{}};
const storage = new Map();
global.window = windowObj;
global.localStorage = {{ getItem: (k) => storage.get(k) ?? null, setItem: (k, v) => storage.set(k, v) }};

const intervals = [];
const cleared = [];
let nextId = 1;
global.setInterval = (fn, ms) => {{
  const id = nextId++;
  intervals.push({{ id, fn, ms }});
  return id;
}};
global.clearInterval = (id) => cleared.push(id);

function mkNode(tag) {{
  const classes = new Set();
  const attrs = {{}};
  const node = {{
    tag,
    nodeType: 1,
    tagName: String(tag).toUpperCase(),
    children: [],
    attrs,
    disabled: false,
    isConnected: false,
    _text: '',
    classList: {{
      add: (c) => classes.add(c),
      remove: (c) => classes.delete(c),
      has: (c) => classes.has(c),
    }},
    hasAttribute: (k) => k in attrs,
    setAttribute: (k, v) => {{ attrs[k] = String(v); }},
    removeAttribute: (k) => {{ delete attrs[k]; }},
    getAttribute: (k) => attrs[k] ?? null,
    addEventListener: () => {{}},
    append(...args) {{
      for (const a of args) {{
        if (Array.isArray(a)) this.children.push(...a);
        else if (a !== null && a !== undefined && a !== false) this.children.push(a);
      }}
    }},
    get textContent() {{
      if (this._text) return this._text;
      return this.children.map((c) => typeof c === 'string' ? c : (c.textContent || '')).join('');
    }},
    set textContent(v) {{
      this._text = String(v);
      this.children = [];
    }},
  }};
  return node;
}}

global.document = {{
  documentElement: {{ dataset: {{}}, setAttribute: () => {{}} }},
  addEventListener: () => {{}},
  getElementById: () => null,
  createTextNode: (t) => String(t),
  createElement: mkNode,
}};

const uiCode = fs.readFileSync(path.join(staticDir, 'ui.js'), 'utf8');
const StudioUI = new Function('window', 'document', 'localStorage', uiCode + '; return StudioUI;')(windowObj, global.document, global.localStorage);

// 1. Ref-counted locking + unpaired false safety
const ctrlEnabled = Object.assign(mkNode('button'), {{ disabled: false }});
const ctrlAlreadyDisabled = Object.assign(mkNode('button'), {{ disabled: true }});
StudioUI.setControlsBusy([ctrlAlreadyDisabled], false); // unpaired false must not unlock
const afterUnpaired = ctrlAlreadyDisabled.disabled;

StudioUI.setControlsBusy([ctrlEnabled, ctrlAlreadyDisabled], true);
StudioUI.setControlsBusy([ctrlEnabled], true); // second overlapping lock
StudioUI.setControlsBusy([ctrlEnabled], false); // only 1 released -> still locked!
const stillLockedDuringOverlap = [ctrlEnabled.disabled, ctrlEnabled.getAttribute('aria-busy')];
StudioUI.setControlsBusy([ctrlEnabled, ctrlAlreadyDisabled], false); // final release
const afterOverlap = [ctrlEnabled.disabled, ctrlAlreadyDisabled.disabled, ctrlEnabled.getAttribute('aria-busy')];

// 2. Normal attached createBusyView + 1s ticks + disconnect cleanup
const busy = StudioUI.createBusyView({{
  title: 'Test-Laden',
  stages: [
    {{ afterSec: 0, text: 'Schritt eins' }},
    {{ afterSec: 2, text: 'Schritt zwei' }},
  ],
  lines: 2,
}});
busy.el.isConnected = true;
const t0 = busy.el.textContent;
intervals[0].fn();
intervals[0].fn();
const t2 = busy.el.textContent;
busy.el.isConnected = false;
intervals[0].fn();

// 3. Detach before first 1s tick (isConnected stays false from start) must self-stop with 0 leaks
const ephemeral = StudioUI.createBusyView({{ title: 'Kurz-Laden' }});
intervals[1].fn(); // tick #1 while never connected

console.log(JSON.stringify({{
  afterUnpaired,
  stillLockedDuringOverlap,
  afterOverlap,
  t0,
  t2,
  clearedIds: cleared,
  ariaBusyAfterStop: busy.el.getAttribute('aria-busy'),
  ephemeralAriaBusy: ephemeral.el.getAttribute('aria-busy'),
}}));
"""
    raw = subprocess.check_output([node, "-e", script], text=True)
    out = json.loads(raw)
    assert out["afterUnpaired"] is True
    assert out["stillLockedDuringOverlap"] == [True, "true"]
    assert out["afterOverlap"] == [False, True, None]
    assert (
        "Test-Laden" in out["t0"] and "Schritt eins" in out["t0"] and "Läuft seit 0 s" in out["t0"]
    )
    assert "Läuft seit 2 s" in out["t2"] and "Schritt zwei" in out["t2"]
    assert out["clearedIds"] == [1, 2]
    assert out["ariaBusyAfterStop"] is None
    assert out["ephemeralAriaBusy"] is None


def test_sync_engine_start_and_daten_error_cleanup_behavior_in_node() -> None:
    node = shutil.which("node")
    assert node is not None
    script = f"""
const fs = require('fs');
const path = require('path');
const staticDir = {json.dumps(str(STATIC))};
const windowObj = {{}};
const storage = new Map();
global.window = windowObj;
global.localStorage = {{ getItem: (k) => storage.get(k) ?? null, setItem: (k, v) => storage.set(k, v) }};
let nextId = 1;
const intervals = [];
const cleared = [];
global.setInterval = (fn) => {{ const id = nextId++; intervals.push(id); return id; }};
global.clearInterval = (id) => cleared.push(id);

function mkNode(tag) {{
  const attrs = {{}};
  const classes = new Set();
  return {{
    tag, nodeType: 1, tagName: String(tag).toUpperCase(), children: [], attrs, disabled: false, isConnected: false,
    classList: {{ add: (c) => classes.add(c), remove: (c) => classes.delete(c) }},
    hasAttribute: (k) => k in attrs,
    setAttribute: (k, v) => {{ attrs[k] = String(v); }},
    removeAttribute: (k) => {{ delete attrs[k]; }},
    getAttribute: (k) => attrs[k] ?? null,
    addEventListener: () => {{}},
    replaceChildren(...args) {{ this.children = args; }},
    append(...args) {{ this.children.push(...args); }},
  }};
}}
const els = new Map();
const getEl = (id) => {{ if (!els.has(id)) els.set(id, mkNode('div')); return els.get(id); }};
global.document = {{ documentElement: {{ dataset: {{}}, setAttribute: () => {{}} }}, addEventListener: () => {{}}, getElementById: getEl, createTextNode: (t) => String(t), createElement: mkNode }};

const uiCode = fs.readFileSync(path.join(staticDir, 'ui.js'), 'utf8');
const StudioUI = new Function('window', 'document', 'localStorage', uiCode + '; return StudioUI;')(windowObj, global.document, global.localStorage);

// Test partie.js syncEngineStartBusy with #ff-btn, #speed, #ff-mode
const partieCode = fs.readFileSync(path.join(staticDir, 'partie.js'), 'utf8');
const startIdx = partieCode.indexOf('let engineStartBusy = null;');
const endIdx = partieCode.indexOf('function renderView()');
const syncCode = partieCode.slice(startIdx, endIdx);
const ffBtn = Object.assign(getEl('ff-btn'), {{ disabled: false }});
const speedSel = Object.assign(getEl('speed'), {{ disabled: false }});
const ffMode = Object.assign(getEl('ff-mode'), {{ disabled: false }});
const syncFn = new Function('StudioUI', '$', syncCode + '; return syncEngineStartBusy;')(StudioUI, getEl);

syncFn(false); // unpaired call before waiting must not touch anything
const ctrlBefore = ffBtn.disabled;
const busyObj = syncFn(true);
const lockedDuringWait = [speedSel.disabled, ffMode.disabled, ffBtn.disabled];
syncFn(false);
const unlockedAfterWait = [speedSel.disabled, ffMode.disabled, ffBtn.disabled];

// Test daten.js error cleanup removes all 6 busy cards from sections
const datenCode = fs.readFileSync(path.join(staticDir, 'daten.js'), 'utf8');
const dStart = datenCode.indexOf('let loadTicket = 0;');
const dEnd = datenCode.indexOf('async function init()');
const loadAllCode = datenCode.slice(dStart, dEnd);
['data-summary', 'data-bridge', 'data-sources', 'data-collection', 'data-roles', 'data-corpus', 'data-layers'].forEach((id) => getEl(id));
const cmdSel = Object.assign(getEl('commander-select'), {{ value: 'Chulane', disabled: false }});
const refBtn = Object.assign(getEl('data-refresh'), {{ disabled: false }});
let failedMsg = null;
const fakeUI = Object.assign({{}}, StudioUI, {{
  request: async () => {{ throw new Error('offline'); }},
  fail: (m) => {{ failedMsg = m; }},
  germanError: () => 'Offline',
}});
const loadAllFn = new Function('StudioUI', 'StudioCommander', '$', 'h', 'nf', 'renderBridge', 'renderSources', 'renderCollection', 'renderRoles', 'renderCorpus', 'renderLayersAndRecipes', loadAllCode + '; return loadAll;')(
  fakeUI, {{ current: 'Chulane', shortName: () => 'Chulane' }}, getEl, StudioUI.el, String,
  () => {{}}, () => {{}}, () => {{}}, () => {{}}, () => {{}}, () => getEl('data-layers').replaceChildren(StudioUI.el('p', {{ class: 'warn' }}, 'offline'))
);
(async () => {{
  await loadAllFn();
  const stuckBusyAttrs = ['data-bridge', 'data-sources', 'data-collection', 'data-roles', 'data-corpus', 'data-layers']
    .map((id) => getEl(id).children[0]?.className || '');
  console.log(JSON.stringify({{
    ctrlBefore,
    hasBusyEl: Boolean(busyObj && busyObj.el),
    lockedDuringWait,
    unlockedAfterWait,
    stuckBusyAttrs,
    failedMsg,
    datenCmdDisabledAfter: cmdSel.disabled,
    datenRefreshDisabledAfter: refBtn.disabled,
    summaryTag: getEl('data-summary').textContent,
  }}));
}})();
"""
    raw = subprocess.check_output([node, "-e", script], text=True)
    out = json.loads(raw)
    assert out["ctrlBefore"] is False
    assert out["hasBusyEl"] is True
    assert out["lockedDuringWait"] == [True, True, True]
    assert out["unlockedAfterWait"] == [False, False, False]
    assert out["stuckBusyAttrs"] == ["warn"] * 6
    assert out["failedMsg"] == "Offline"
    assert out["datenCmdDisabledAfter"] is False and out["datenRefreshDisabledAfter"] is False


def test_all_seven_surfaces_wire_create_busy_view() -> None:
    expected = {
        "ui.js": ("createBusyView", "setControlsBusy"),
        "app.js": ("Deck-Kennzahlen werden berechnet", "Kartenpool und Deckdaten werden geladen"),
        "castability.js": ("Farben auf Kurve werden berechnet",),
        "cardduel.js": ("createBusyView", "setControlsBusy"),
        "packages.js": ("6-Schritte-Bauplan", "Pakete & Upgrade-Pfad"),
        "commander.js": ("setControlsBusy", "data-main"),
        "partie.js": ("syncEngineStartBusy", "XMage-Engine startet", "ff-btn"),
        "tierliste.js": (
            "Tierliste wird berechnet",
            "Stärke-Index wird neu berechnet",
            "loadSavedProfile",
        ),
        "daten.js": (
            "Datenlage wird aktualisiert",
            "setControlsBusy",
            "Abschnitt konnte nicht geladen werden.",
        ),
    }
    assert len(expected) == 9
    checked = 0
    for filename, markers in expected.items():
        text = (STATIC / filename).read_text(encoding="utf-8")
        assert len(markers) >= 1
        for marker in markers:
            assert marker in text, f"{filename} missing {marker}"
        checked += 1
    assert checked == 9
