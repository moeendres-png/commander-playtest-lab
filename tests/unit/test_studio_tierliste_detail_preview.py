"""Tests for Tierliste row-click card detail, hover preview, Oracle text, and scroll preservation."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[2] / "src" / "commander_lab" / "studio" / "static"


def _tierliste_slice(start_marker: str, end_marker: str) -> str:
    src = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    start = src.index(start_marker)
    end = src.index(end_marker, start)
    return src[start:end]


def test_tierliste_static_markup_and_styles_for_row_preview_and_oracle() -> None:
    html = (STATIC / "tierliste.html").read_text(encoding="utf-8")
    css = (STATIC / "tierliste.css").read_text(encoding="utf-8")
    js = (STATIC / "tierliste.js").read_text(encoding="utf-8")

    assert '<div id="preview" class="tier-preview" hidden></div>' in html
    assert "#preview.tier-preview{position:fixed;" in css
    assert "pointer-events:none;" in css
    assert ".modal-oracle{" in css
    assert "tbody tr.card-row{cursor:pointer}" in css
    assert '"data-card-id": card.card_id, title: card.name, onclick: () => openCard(card)' in js
    assert 'id: "modal-oracle"' in js
    assert "preventScroll: true" in js
    assert "state.lastScrollTop" in js


def test_tierliste_row_click_preview_and_scroll_preservation_in_node() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")

    helpers_src = _tierliste_slice("function previewTierSummary(", "function cardsTable(")
    modal_src = _tierliste_slice("function closeModal(", "// ---------- deck universe ----------")

    script = f"""
const assert = require("assert");

const elements = new Map();
function makeEl(tag, props, kids) {{
  const el = {{
    tagName: String(tag || "").toUpperCase(),
    attributes: {{}},
    classList: {{
      _set: new Set(),
      add(c) {{ this._set.add(c); }},
      remove(c) {{ this._set.delete(c); }},
      contains(c) {{ return this._set.has(c); }},
    }},
    style: {{}},
    children: [],
    listeners: {{}},
    hidden: false,
    isConnected: true,
    scrollTop: 0,
    scrollLeft: 0,
    offsetWidth: 300,
    offsetHeight: 220,
    focusOpts: null,
    textContent: "",
    setAttribute(k, v) {{ this.attributes[k] = String(v); }},
    getAttribute(k) {{ return this.attributes[k] ?? null; }},
    addEventListener(type, fn) {{ (this.listeners[type] = this.listeners[type] || []).push(fn); }},
    replaceChildren(...nodes) {{
      this.children = nodes.flat().filter((n) => n !== null && n !== undefined);
      this.textContent = this.children.map((n) => (typeof n === "string" ? n : n.textContent || "")).join("");
    }},
    append(...nodes) {{
      const flat = nodes.flat().filter((n) => n !== null && n !== undefined);
      this.children.push(...flat);
      this.textContent += flat.map((n) => (typeof n === "string" ? n : n.textContent || "")).join("");
    }},
    contains(other) {{
      if (other === this) return true;
      return this.children.some((c) => c && typeof c === "object" && c.contains && c.contains(other));
    }},
    focus(opts) {{
      this.focusOpts = opts || null;
      document.activeElement = this;
    }},
    querySelectorAll() {{ return []; }},
  }};
  for (const [k, v] of Object.entries(props || {{}})) {{
    if (v === null || v === undefined) continue;
    if (k === "id") {{ el.id = v; elements.set(v, el); }}
    else if (k === "class") {{ String(v).split(/\\s+/).filter(Boolean).forEach((c) => el.classList.add(c)); }}
    else if (k.startsWith("on") && typeof v === "function") {{ el[k] = v; }}
    else el.setAttribute(k, v);
  }}
  const appendKids = (arr) => {{
    for (const item of arr) {{
      if (Array.isArray(item)) appendKids(item);
      else if (item !== null && item !== undefined) {{
        el.children.push(item);
        el.textContent += typeof item === "string" ? item : item.textContent || "";
      }}
    }}
  }};
  appendKids(kids);
  return el;
}}

const preview = makeEl("div", {{ id: "preview" }}, []);
preview.hidden = true;
const modal = makeEl("div", {{ id: "modal" }}, []);
modal.hidden = true;
const modalBox = makeEl("div", {{ id: "modal-box" }}, []);
const poolBody = makeEl("div", {{ id: "pool-body" }}, []);
poolBody.scrollTop = 315;
poolBody.scrollLeft = 12;

global.window = {{ innerWidth: 1280, innerHeight: 800 }};
global.CSS = {{ escape: (s) => s }};
global.document = {{
  activeElement: null,
  body: {{ classList: makeEl("div", {{}}, []).classList }},
  getElementById: (id) => elements.get(id) || null,
  querySelector: () => null,
}};
const $ = (id) => elements.get(id) || null;
const COMMANDER = "Chulane, Teller of Tales";
const OUTCOME_HEADING = "Ergebnis";
const REASON_SHORT = {{ TOO_LITTLE_DATA: "zu wenig Daten" }};
const codeLabel = (x) => x;
const nf = (v) => String(v);
const StudioUI = {{
  num: (v, d) => Number(v).toFixed(d).replace(".", ","),
  pct: (r, d) => `${{(Number(r) * 100).toFixed(d).replace(".", ",")}} %`,
  germanError: (e) => String(e),
}};
const StudioKartenverstaendnis = {{ fill() {{}} }};
const understandingShown = () => false;
const h = (tag, props, ...children) => makeEl(tag, props, children);
const strengthItem = (c) => state.strength.map.get(c.card_id) || null;
const deckCounts = (item) => item && item.counts ? item.counts : null;
const layer = () => ({{ items: [] }});
const cardImageUrl = (c, f) => `/api/card-image?name=${{encodeURIComponent(c.name)}}&face=${{f}}`;
const whyBox = () => h("div", {{ class: "why" }}, "Begründung: 60/100 Quelldecks");
const strengthBox = () => h("div", {{}}, "Stärkebox");
const markButtons = () => [];
const drawer = () => [];
const universeBox = async () => h("div", {{}}, "Uni");
const alternativesBox = async () => h("div", {{}}, "Alt");
const api = async () => ({{
  card: {{
    card_id: "c-sol",
    name: "Sol Ring",
    type_line: "Artifact",
    text: "Tap: Add two colorless mana.",
    has_image: true,
    has_back: false,
  }},
}});

const state = {{
  view: "commander",
  strength: {{
    status: "ready",
    map: new Map([["c-sol", {{ tier: "S", index: 92.4, counts: {{ n: 60, N: 100 }} }}]]),
  }},
  lastFocus: null,
  lastFocusCard: "",
  lastScrollTop: null,
  lastScrollLeft: null,
}};

{helpers_src}
{modal_src}

const card = {{
  card_id: "c-sol",
  name: "Sol Ring",
  type_line: "Artifact",
  text: "Tap: Add two colorless mana.",
  has_image: true,
}};

async function run() {{
  const rowProps = cardRowProps(card);
  const tr = h("tr", rowProps, []);
  tr.focus();

  // Hover shows fixed preview with image, Oracle text, and tier/denominator context
  rowProps.onmouseenter({{ clientX: 200, clientY: 180 }});
  assert.strictEqual(preview.hidden, false);
  assert.ok(preview.textContent.includes("Sol Ring"));
  assert.ok(preview.textContent.includes("Tap: Add two colorless mana."));
  assert.ok(preview.textContent.includes("Stufe S"));
  assert.ok(preview.textContent.includes("60/100 Quelldecks"));

  // Clicking an interactive button inside the row must NOT open the card modal
  const favBtn = {{ closest: (sel) => (sel.includes("button") ? {{}} : null) }};
  rowProps.onclick({{ target: favBtn }});
  assert.strictEqual(modal.hidden, true);

  // Clicking a non-button, non-name cell triggers row onclick -> opens modal and hides preview
  const tierCell = {{ closest: () => null }};
  document.activeElement = tr;
  rowProps.onclick({{ target: tierCell }});
  await new Promise((resolve) => setTimeout(resolve, 10));
  assert.strictEqual(preview.hidden, true);
  assert.strictEqual(modal.hidden, false);
  assert.ok(modalBox.textContent.includes("Tap: Add two colorless mana."));
  assert.ok(modalBox.textContent.includes("Begründung: 60/100 Quelldecks"));

  // Escape preserves #pool-body scroll position and uses preventScroll focus restore
  trapModalFocus({{ key: "Escape" }});
  assert.strictEqual(modal.hidden, true);
  assert.strictEqual(poolBody.scrollTop, 315);
  assert.strictEqual(poolBody.scrollLeft, 12);
  assert.deepStrictEqual(tr.focusOpts, {{ preventScroll: true }});

  // Keyboard Enter on focused row also opens modal
  await rowProps.onkeydown({{ key: "Enter", target: tr, currentTarget: tr, preventDefault() {{}} }});
  assert.strictEqual(modal.hidden, false);
  closeModal();
  assert.strictEqual(poolBody.scrollTop, 315);
}}

run().then(() => console.log(JSON.stringify({{ ok: true }}))).catch((err) => {{
  console.error(err);
  process.exit(1);
}});
"""
    res = subprocess.run([node, "-e", script], check=False, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr or res.stdout
    assert json.loads(res.stdout.strip()) == {"ok": True}
    assert re.search(
        r"function\s+openCard\b", (STATIC / "tierliste.js").read_text(encoding="utf-8")
    )
