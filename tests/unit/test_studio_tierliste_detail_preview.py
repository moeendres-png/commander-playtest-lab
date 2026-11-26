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
    assert "box-shadow:var(--shadow);" in css
    assert ".modal-oracle{white-space:pre-line;background:var(--panel2);" in css
    assert (
        "tbody tr.card-row:hover td{background:color-mix(in srgb,var(--panel) 92%,var(--accent))}"
        in css
    )
    assert "#0d131d" not in css and "#182132" not in css
    assert '"data-card-id": card.card_id, title: card.name, onclick: () => openCard(card)' in js
    assert 'tabindex: "-1", "data-card-id": card.card_id' in js
    assert 'id: "modal-oracle"' in js
    assert "preventScroll: true" in js
    assert "state.lastScrollTop" in js
    assert 'window.addEventListener("scroll", hideRowPreview' in js


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
    rect: {{ left: 40, top: 120, bottom: 148, width: 500 }},
    getBoundingClientRect() {{ return this.rect; }},
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
  querySelector: (sel) => {{
    if (sel.includes("c-two")) return rowTwo;
    return null;
  }},
}};
const $ = (id) => elements.get(id) || null;
const COMMANDER = "Chulane, Teller of Tales";
const OUTCOME_HEADING = "Ergebnis";
const REASON_SHORT = {{ TOO_LITTLE_DATA: "zu wenig Daten", NO_COMMANDER_SIGNAL: "kein Commander-Signal" }};
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
const layer = (c) => ({{ items: c._globalRank ? [{{ kind: "edhrec_rank_global", rank: c._globalRank }}] : [] }});
const cardImageUrl = (c, f) => `/api/card-image?name=${{encodeURIComponent(c.name)}}&face=${{f}}`;
const whyBox = (c) => h("div", {{ class: "why" }}, `Begründung für ${{c.name}}`);
const strengthBox = () => h("div", {{}}, "Stärkebox");
const markButtons = () => [];
const drawer = () => [];
let resolveSlowApi = null;
let slowNext = false;
const api = async (url) => {{
  const id = url.includes("c-two") ? "c-two" : url.includes("c-empty") ? "c-empty" : "c-sol";
  const byId = {{
    "c-sol": {{ card_id: "c-sol", name: "Sol Ring", type_line: "Artifact", text: "Tap: Add two colorless mana.", has_image: true, has_back: false }},
    "c-two": {{ card_id: "c-two", name: "Cultivate", type_line: "Sorcery", text: "Search your library for up to two basic land cards.", has_image: true, has_back: false }},
    "c-empty": {{ card_id: "c-empty", name: "Wastes", type_line: "Basic Land", text: "", has_image: false, has_back: false }},
  }};
  if (slowNext) {{
    slowNext = false;
    await new Promise((r) => {{ resolveSlowApi = r; }});
  }}
  return {{ card: byId[id] }};
}};
const universeBox = async () => h("div", {{}}, "Uni");
const alternativesBox = async () => h("div", {{}}, "Alt");

const state = {{
  view: "commander",
  strength: {{
    status: "ready",
    map: new Map([
      ["c-sol", {{ tier: "S", index: 92.4, counts: {{ n: 60, N: 100 }} }}],
      ["c-u", {{ tier: "U", reason: "TOO_LITTLE_DATA", counts: {{ n: 1, N: 100 }} }}],
      ["c-n", {{ tier: "N", note: "Standardland" }}],
    ]),
  }},
  lastFocus: null,
  lastFocusCard: "",
  lastScrollTop: null,
  lastScrollLeft: null,
  modalTicket: 0,
  suppressFocusPreview: false,
}};

{helpers_src}
{modal_src}

const card = {{ card_id: "c-sol", name: "Sol Ring", type_line: "Artifact", text: "Tap: Add two colorless mana.", has_image: true }};
const cardTwo = {{ card_id: "c-two", name: "Cultivate", type_line: "Sorcery", text: "Search lands.", has_image: true }};
const cardEmpty = {{ card_id: "c-empty", name: "Wastes", type_line: "Basic Land", text: "", has_image: false }};
const rowTwo = h("tr", cardRowProps(cardTwo), []);

async function run() {{
  const rowProps = cardRowProps(card);
  const tr = h("tr", rowProps, []);
  tr.focus();

  // previewTierSummary checks (S, U without duplicate wording, N, global, missing Oracle text)
  assert.ok(!previewTierSummary({{ card_id: "c-u" }}).includes("(zu wenig Daten)"));
  assert.strictEqual(previewTierSummary({{ card_id: "c-u" }}), "Zu wenig Daten · 1/100 Quelldecks (1,0 %)");
  assert.strictEqual(previewTierSummary({{ card_id: "c-n" }}), "Standardland (nicht bewertet)");
  state.view = "global";
  assert.strictEqual(previewTierSummary({{ card_id: "g", _globalRank: 42 }}), "Globaler EDHREC-Rang 42 (ohne Commander-Stufe)");
  state.view = "commander";

  // Hover shows fixed preview; mouseleave & blur hide it
  rowProps.onmouseenter({{ clientX: 200, clientY: 180, currentTarget: tr }});
  assert.strictEqual(preview.hidden, false);
  assert.ok(preview.textContent.includes("Sol Ring"));
  assert.ok(preview.textContent.includes("Tap: Add two colorless mana."));
  assert.ok(preview.textContent.includes("Stufe S"));
  assert.ok(preview.textContent.includes("60/100 Quelldecks"));

  // Viewport clamping when clientX exceeds viewport width
  rowProps.onmousemove({{ clientX: 5000, clientY: 5000, currentTarget: tr }});
  const clampedLeft = parseInt(preview.style.left, 10);
  const clampedTop = parseInt(preview.style.top, 10);
  assert.ok(clampedLeft >= 8 && clampedLeft <= 1280 - 300 - 8, preview.style.left);
  assert.ok(clampedTop >= 8 && clampedTop <= 800 - 220 - 8, preview.style.top);

  rowProps.onmouseleave();
  assert.strictEqual(preview.hidden, true);

  // Keyboard focus shows preview via rect fallback; blur hides it; empty text falls back cleanly
  const emptyProps = cardRowProps(cardEmpty);
  emptyProps.onfocus({{ target: tr, currentTarget: tr }});
  assert.strictEqual(preview.hidden, false);
  assert.ok(preview.textContent.includes("Kein Regeltext."));
  emptyProps.onblur();
  assert.strictEqual(preview.hidden, true);

  // Interactive button, disabled button in td.acts, and td.name are ignored by tr.onclick
  for (const selHit of ["button", "a", "input", "td.acts", "td.name"]) {{
    const fakeTarget = {{ closest: (sel) => (sel.includes(selHit) ? {{}} : null) }};
    rowProps.onclick({{ target: fakeTarget }});
    assert.strictEqual(modal.hidden, true, selHit);
  }}

  // Clicking a non-button, non-name cell opens modal and hides preview
  const tierCell = {{ closest: () => null }};
  document.activeElement = tr;
  rowProps.onclick({{ target: tierCell }});
  await new Promise((r) => setTimeout(r, 10));
  assert.strictEqual(preview.hidden, true);
  assert.strictEqual(modal.hidden, false);
  assert.ok(modalBox.textContent.includes("Tap: Add two colorless mana."));
  assert.ok(modalBox.textContent.includes("Begründung für Sol Ring"));

  // Escape preserves #pool-body scroll position and uses preventScroll focus restore without spurious preview
  trapModalFocus({{ key: "Escape" }});
  assert.strictEqual(modal.hidden, true);
  assert.strictEqual(preview.hidden, true);
  assert.strictEqual(poolBody.scrollTop, 315);
  assert.strictEqual(poolBody.scrollLeft, 12);
  assert.deepStrictEqual(tr.focusOpts, {{ preventScroll: true }});

  // Verify suppressFocusPreview stays respected when target.focus fires synchronous onfocus handler
  tr.focus = (opts) => {{
    tr.focusOpts = opts || null;
    document.activeElement = tr;
    if (tr.onfocus) tr.onfocus({{ target: tr, currentTarget: tr }});
  }};
  rowTwo.focus = (opts) => {{
    rowTwo.focusOpts = opts || null;
    document.activeElement = rowTwo;
    if (rowTwo.onfocus) rowTwo.onfocus({{ target: rowTwo, currentTarget: rowTwo }});
  }};
  await openCard(cardTwo);
  closeModal();
  assert.strictEqual(preview.hidden, true);

  // Space opens modal; child keydown is ignored
  let preventCalled = false;
  await rowProps.onkeydown({{ key: " ", target: tr, currentTarget: tr, preventDefault() {{ preventCalled = true; }} }});
  assert.strictEqual(preventCalled, true);
  assert.strictEqual(modal.hidden, false);
  closeModal();

  await rowProps.onkeydown({{ key: "Enter", target: {{}}, currentTarget: tr, preventDefault() {{ throw new Error("should not fire"); }} }});
  assert.strictEqual(modal.hidden, true);

  // Stale-async race: open Card 1 slowly, immediately Escape -> late resolve must NOT reopen/overwrite modal
  slowNext = true;
  const slowOpen = openCard(card);
  assert.strictEqual(modal.hidden, false);
  trapModalFocus({{ key: "Escape" }});
  assert.strictEqual(modal.hidden, true);
  resolveSlowApi();
  await slowOpen;
  assert.strictEqual(modal.hidden, true);
  assert.ok(!modalBox.textContent.includes("Begründung für Sol Ring"));

  // Switching directly from Card 1 to Card 2 updates lastFocusCard to Card 2 cleanly
  await openCard(card);
  await openCard(cardTwo);
  closeModal();
  assert.strictEqual(document.activeElement, rowTwo);
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
    src = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    assert re.search(r"function\s+openCard\b", src)
    assert 'return h("tr", cardRowProps(card)' in src or 'h("tr", cardRowProps(card)' in src
