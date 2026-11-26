"""Tests for Issue #1836 cross-cutting Studio loading & progress feedback."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "src" / "commander_lab" / "studio" / "static"


def test_create_busy_view_and_set_controls_busy_in_node() -> None:
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
    isConnected: true,
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

const ctrlEnabled = Object.assign(mkNode('button'), {{ disabled: false }});
const ctrlAlreadyDisabled = Object.assign(mkNode('button'), {{ disabled: true }});
StudioUI.setControlsBusy([ctrlEnabled, ctrlAlreadyDisabled], true);
const duringDisabled = [ctrlEnabled.disabled, ctrlAlreadyDisabled.disabled, ctrlEnabled.getAttribute('aria-busy')];
StudioUI.setControlsBusy([ctrlEnabled, ctrlAlreadyDisabled], false);
const afterDisabled = [ctrlEnabled.disabled, ctrlAlreadyDisabled.disabled, ctrlEnabled.getAttribute('aria-busy')];

const busy = StudioUI.createBusyView({{
  title: 'Test-Laden',
  stages: [
    {{ afterSec: 0, text: 'Schritt eins' }},
    {{ afterSec: 2, text: 'Schritt zwei' }},
  ],
  lines: 2,
}});
const t0 = busy.el.textContent;
intervals[0].fn();
intervals[0].fn();
const t2 = busy.el.textContent;
busy.el.isConnected = false;
intervals[0].fn();
const autoCleared = cleared.length;

console.log(JSON.stringify({{ duringDisabled, afterDisabled, t0, t2, autoCleared, ariaBusyAfterStop: busy.el.getAttribute('aria-busy') }}));
"""
    raw = subprocess.check_output([node, "-e", script], text=True)
    out = json.loads(raw)
    assert out["duringDisabled"] == [True, True, "true"]
    assert out["afterDisabled"] == [False, True, None]
    assert (
        "Test-Laden" in out["t0"] and "Schritt eins" in out["t0"] and "Läuft seit 0 s" in out["t0"]
    )
    assert "Läuft seit 2 s" in out["t2"] and "Schritt zwei" in out["t2"]
    assert out["autoCleared"] == 1
    assert out["ariaBusyAfterStop"] is None


def test_all_seven_surfaces_wire_create_busy_view() -> None:
    expected = {
        "ui.js": ("createBusyView", "setControlsBusy"),
        "app.js": ("Deck-Kennzahlen werden berechnet", "Kartenpool und Deckdaten werden geladen"),
        "castability.js": ("Farben auf Kurve werden berechnet",),
        "cardduel.js": ("createBusyView", "setControlsBusy"),
        "packages.js": ("6-Schritte-Bauplan", "Pakete & Upgrade-Pfad"),
        "commander.js": ("setControlsBusy", "createBusyView"),
        "partie.js": ("syncEngineStartBusy", "XMage-Engine startet"),
        "tierliste.js": ("Tierliste wird berechnet", "Stärke-Index wird neu berechnet"),
        "daten.js": ("Datenlage wird aktualisiert", "setControlsBusy"),
    }
    for filename, markers in expected.items():
        text = (STATIC / filename).read_text(encoding="utf-8")
        for marker in markers:
            assert marker in text, f"{filename} missing {marker}"
