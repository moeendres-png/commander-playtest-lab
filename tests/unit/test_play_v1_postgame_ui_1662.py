"""Issue #1662 Part 4 UI tests: postgame sheet in partie.html/partie.js and play notes + replace entry in app.js."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[2] / "src" / "commander_lab" / "studio" / "static"


def _node(script: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    done = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, check=False, cwd=STATIC
    )
    assert done.returncode == 0, done.stderr[-2500:]
    return json.loads(done.stdout)


def test_postgame_ui_static_guards_and_html_wiring() -> None:
    partie_html = (STATIC / "partie.html").read_text(encoding="utf-8")
    partie_js = (STATIC / "partie.js").read_text(encoding="utf-8")
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")

    assert (
        '<section id="postgame-sheet" class="postgame-sheet" role="region" aria-label="Nachspiel-Blatt" hidden></section>'
        in partie_html
    )

    assert "function buildReplaceCardHref(" in partie_js
    assert "function renderPostgameSheet(" in partie_js
    assert "async function loadPostgameSheet(" in partie_js
    assert "/postgame" in partie_js
    assert "/notes" in partie_js
    assert "Diese Karte ersetzen →" in partie_js

    assert "/play-notes" in app_js
    assert "Notizen aus gespielten Partien (PLAYED_GAME)" in app_js
    assert "applyReplaceUrlParams" in app_js

    style_attr_re = re.compile(r"setAttribute\(\s*['\"]style['\"]|style\s*=")
    for name, text in (("partie.html", partie_html), ("partie.js", partie_js), ("app.js", app_js)):
        assert "innerHTML" not in text, name
        assert "outerHTML" not in text, name
        assert "insertAdjacentHTML" not in text, name
        assert "eval(" not in text, name
        assert not style_attr_re.search(text), name
        assert " style=" not in text, name
        assert ".toFixed(" not in text, name


def test_partie_postgame_sheet_helpers_via_node() -> None:
    out = _node(
        r"""
const fs = require('fs');
const assert = require('assert');

class ClassList {
  constructor(el) { this.el = el; this.set = new Set(); }
  add(...names) { names.forEach((n) => n && this.set.add(n)); this.el._className = [...this.set].join(' '); }
  remove(...names) { names.forEach((n) => this.set.delete(n)); this.el._className = [...this.set].join(' '); }
  toggle(name, force) {
    if (force === undefined) force = !this.set.has(name);
    if (force) this.set.add(name); else this.set.delete(name);
    this.el._className = [...this.set].join(' ');
  }
  contains(name) { return this.set.has(name); }
}

class El {
  constructor(tag, id = '') {
    this.tagName = String(tag || 'DIV').toUpperCase();
    this.nodeType = 1;
    this.id = id;
    this.children = [];
    this.attrs = {};
    this.dataset = {};
    this.listeners = {};
    this.hidden = false;
    this.disabled = false;
    this._value = '';
    this.checked = false;
    this._text = '';
    this._className = '';
    this.classList = new ClassList(this);
    this.style = {};
    this.options = [];
  }
  set className(v) {
    this._className = String(v || '');
    this.classList.set = new Set(this._className.split(/\s+/).filter(Boolean));
  }
  get className() { return this._className; }
  set textContent(v) { this._text = v == null ? '' : String(v); this.children = []; }
  get textContent() {
    if (!this.children.length) return this._text;
    return this._text + this.children.map((c) => (typeof c === 'string' ? c : c.textContent)).join('');
  }
  set value(v) { this._value = v == null ? '' : String(v); }
  get value() {
    if (this.tagName === 'SELECT' && !this._value) {
      const opt = this.all().find((n) => n.tagName === 'OPTION');
      if (opt) return opt.value;
    }
    return this._value;
  }
  setAttribute(k, v) {
    this.attrs[k] = String(v);
    if (k === 'id') this.id = String(v);
    if (k === 'class') this.className = String(v);
  }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  append(...nodes) {
    for (const n of nodes) {
      if (n == null) continue;
      if (typeof n === 'string' || n.nodeType === 3) {
        this.children.push(typeof n === 'string' ? n : n.textContent);
      } else {
        this.children.push(n);
        if (this.tagName === 'SELECT' && n.tagName === 'OPTION') this.options.push(n);
      }
    }
  }
  replaceChildren(...nodes) { this.children = []; this.options = []; this._text = ''; this.append(...nodes); }
  replaceWith() {}
  remove() {}
  addEventListener(k, f) { (this.listeners[k] ||= []).push(f); }
  removeEventListener() {}
  all() {
    const out = [this];
    for (const c of this.children) {
      if (c && typeof c !== 'string' && c.all) out.push(...c.all());
    }
    return out;
  }
  querySelectorAll(sel) {
    const nodes = this.all();
    if (sel.startsWith('.')) return nodes.filter((n) => n.classList.contains(sel.slice(1)));
    return nodes.filter((n) => n.tagName === sel.toUpperCase());
  }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
  closest() { return null; }
  focus() {}
  getBoundingClientRect() { return { left: 0, right: 0, top: 0, bottom: 0, width: 0, height: 0 }; }
}

const registry = {};
for (const id of [
  'theme-toggle', 'game-select', 'sim-pill', 'game-info', 'concede-btn', 'delete-game',
  'rematch-btn', 'new-game', 'bridge-status', 'conn-status', 'sr-announce', 'replay-controls',
  'first', 'prev-turn', 'back', 'play', 'next', 'next-turn', 'turn-jump', 'skip', 'position',
  'replay-note', 'speed',
  'hold-confirm-wrap', 'hold-confirm-toggle',
  'pass-element', 'pass-once', 'pass-continue', 'pass-to-my-turn', 'pass-rule', 'where',
  'ff-status', 'replay-timeline', 'phase-bar', 'table-mode-bar', 'board-bar', 'table',
  'side', 'spectator-status', 'human-decision', 'combat-preview', 'now', 'own-combat',
  'postgame-sheet', 'stack-count', 'stack', 'log-search', 'log', 'decision-bar',
  'hand-dock', 'mana-stage-bar', 'hand-title', 'hand-summary', 'hand', 'preview',
  'board-menu', 'drag-ghost', 'board-links', 'modal', 'modal-box', 'toast',
]) {
  registry[id] = new El(id === 'postgame-sheet' ? 'section' : 'div', id);
}
registry['postgame-sheet'].hidden = true;
for (const id of ['speed', 'game-select', 'turn-jump']) {
  registry[id] = new El('select', id);
}
for (const id of ['skip', 'hold-confirm-toggle']) {
  registry[id] = new El('input', id);
}
registry['skip'].checked = true;
registry['hold-confirm-toggle'].checked = true;

const document = {
  getElementById: (id) => registry[id] || null,
  createElement: (tag) => new El(tag),
  createTextNode: (text) => ({ nodeType: 3, textContent: String(text) }),
  addEventListener() {},
  querySelectorAll: () => [],
  querySelector: () => null,
  body: new El('body'),
  documentElement: new El('html'),
  activeElement: null,
};

const memStore = new Map();
const localStorage = {
  getItem: (k) => (memStore.has(k) ? memStore.get(k) : null),
  setItem: (k, v) => { memStore.set(k, String(v)); },
  removeItem: (k) => { memStore.delete(k); },
};
const window = { localStorage, addEventListener() {}, matchMedia: () => ({ matches: false, addEventListener() {} }), location: { search: '', pathname: '/partie.html' }, innerWidth: 1280 };

const calls = [];
let notesStore = [
  {
    note_id: 1,
    game_id: 'played-1',
    deck_id: 'chulane',
    revision_id: 'chulane@rev1',
    card_name: 'Llanowar Elves',
    note_text: 'Kam zu spaet',
    action_hint: 'replace',
    created_at: '2026-11-27T18:06:00Z',
  },
];

const playedSummary = () => ({
  game_id: 'played-1',
  data_class: 'PLAYED_GAME',
  status: 'finished',
  finished: true,
  outcome: 'won',
  winner_seats: [0],
  seed: 42,
  deck_id: 'chulane',
  revision_id: 'chulane@rev1',
  bridge_jar_sha256: 'b'.repeat(64),
  bridge_qualification_state: 'ALIGNED',
  cards_drawn: ['Forest', 'Sol Ring', 'Llanowar Elves'],
  cards_cast: ['Forest', 'Sol Ring'],
  cards_left_in_hand: ['Llanowar Elves'],
  human_clicks: 3,
  duration_seconds: 125.0,
  total_turns: 4,
  notes: [...notesStore],
});

const fetchStub = async (path, options = {}) => {
  calls.push({ path, method: options.method || 'GET', body: options.body ? JSON.parse(options.body) : null });
  if (path === '/api/games') {
    return {
      ok: true,
      json: async () => [{
        game_id: 'played-1',
        running: false,
        status: 'finished',
        cohort: 'PLAYED_GAME',
        played_seats: [0],
        table_size: 2,
        frames: 1,
        header: { seed: 42, human_seats: [0], seats: [{ seat: 0, deck_id: 'chulane' }, { seat: 1, deck_id: 'opp' }] },
        result: { status: 'finished', winner_seats: [0] },
      }],
    };
  }
  if (path.startsWith('/api/games/played-1?') || path.startsWith('/api/play/played-1?')) {
    return {
      ok: true,
      json: async () => ({
        game_id: 'played-1',
        running: false,
        interactive: true,
        cohort: 'PLAYED_GAME',
        played_seats: [0],
        table_size: 2,
        start: 0,
        total: 1,
        header: { seed: 42, human_seats: [0], bridge_jar_sha256: 'b'.repeat(64), seats: [{ seat: 0, deck_id: 'chulane' }, { seat: 1, deck_id: 'opp' }] },
        frames: [{ n: 1, turn: 1, phase: 'precombat_main', step: 'precombat_main', active_seat: 0, seat: 0, decision_class: 'mulligan', chosen: ['Keep hand'], prompt: 'Keep?', options: 2, players: [{ seat: 0, life: 40, hand: ['Forest'], battlefield: [] }, { seat: 1, life: 40, hand_count: 7, battlefield: [] }], stack: [] }],
        result: { status: 'finished', winner_seats: [0] },
      }),
    };
  }
  if (path === '/api/games/played-1/postgame') {
    return { ok: true, json: async () => playedSummary() };
  }
  if (path === '/api/games/played-1/notes' && options.method === 'POST') {
    const body = JSON.parse(options.body);
    const created = {
      note_id: notesStore.length + 1,
      game_id: 'played-1',
      deck_id: 'chulane',
      revision_id: 'chulane@rev1',
      card_name: body.card_name || null,
      note_text: body.note_text,
      action_hint: body.action_hint || null,
      created_at: '2026-11-27T18:10:00Z',
    };
    notesStore = [created, ...notesStore];
    return { ok: true, json: async () => created };
  }
  if (path === '/api/games/running-1/postgame') {
    return { ok: true, json: async () => ({ ...playedSummary(), game_id: 'running-1', finished: false, status: 'running', outcome: 'incomplete' }) };
  }
  return { ok: true, json: async () => ({}) };
};

const files = ['ui.js', 'commander.js', 'turn_bar.js', 'vorspulen.js', 'boardclick.js', 'replay.js', 'play_p1a.js', 'follow.js', 'cohort.js', 'partie.js'];
let src = files.map((f) => fs.readFileSync(f, 'utf8')).join('\n;\n');
src = src.replace(/\nstart\(\);\s*$/, '\n');
const make = new Function(
  'document', 'window', 'location', 'history', 'fetch', 'localStorage', 'sessionStorage', 'setTimeout', 'clearTimeout', 'requestAnimationFrame',
  src + '\n;return { state, buildReplaceCardHref, renderPostgameSheet, loadPostgameSheet, openGame, start };'
);
const page = make(document, window, window.location, { replaceState() {} }, fetchStub, localStorage, { getItem: () => null, removeItem() {} }, () => 0, () => {}, () => 0);

(async () => {
  assert.strictEqual(
    page.buildReplaceCardHref('Sol Ring', 'chulane@rev1'),
    'index.html?replace=Sol%20Ring&revision=chulane%40rev1'
  );
  assert.strictEqual(
    page.buildReplaceCardHref('Sol Ring', null),
    'index.html?replace=Sol%20Ring&revision='
  );

  const sheet = registry['postgame-sheet'];
  assert.strictEqual(sheet.hidden, true);

  // Running game stays hidden
  page.state.gameId = 'running-1';
  page.state.running = true;
  await page.loadPostgameSheet('running-1');
  assert.strictEqual(sheet.hidden, true);

  // Finished game opens and loads postgame sheet automatically
  await page.start();
  for (let i = 0; i < 10; i += 1) await Promise.resolve();
  assert.strictEqual(sheet.hidden, false);
  const text = sheet.textContent;
  assert.ok(text.includes('Nachspiel-Blatt'));
  assert.ok(text.includes('PLAYED_GAME'));
  assert.ok(!text.includes('SIMULATED_RESULT'));
  assert.ok(text.includes('won'));
  assert.ok(text.includes('bbbbbbbbbbbb'));
  assert.ok(text.includes('ALIGNED'));
  assert.ok(text.includes('Gezogen'));
  assert.ok(text.includes('Gewirkt'));
  assert.ok(text.includes('Auf der Hand geblieben'));
  assert.ok(text.includes('Kam zu spaet'));

  const links = sheet.querySelectorAll('a');
  assert.ok(links.length >= 6);
  assert.ok(links.every((a) => a.textContent === 'Diese Karte ersetzen →'));
  assert.ok(links.some((a) => (a.href || a.getAttribute('href')) === 'index.html?replace=Sol%20Ring&revision=chulane%40rev1'));

  // Submit note form -> POST /api/games/played-1/notes + reload
  const sel = sheet.querySelector('select');
  const ta = sheet.querySelector('textarea');
  const form = sheet.querySelector('form');
  sel.value = 'Sol Ring';
  ta.value = 'Stark im Startzug';
  for (const fn of form.listeners.submit) await fn({ preventDefault() {} });

  const postCall = calls.find((c) => c.path === '/api/games/played-1/notes' && c.method === 'POST');
  assert.ok(postCall);
  assert.deepStrictEqual(postCall.body, { note_text: 'Stark im Startzug', card_name: 'Sol Ring' });
  assert.ok(sheet.textContent.includes('Stark im Startzug'));

  // Simulated game shows SIMULATED_RESULT badge and "unbekannt" for human_clicks: null
  const simBox = new El('section', 'sim-sheet');
  page.renderPostgameSheet({
    ...playedSummary(),
    game_id: 'sim-1',
    data_class: 'SIMULATED_RESULT',
    human_clicks: null,
    outcome: 'lost',
    notes: [],
  }, simBox);
  assert.ok(simBox.textContent.includes('SIMULATED_RESULT'));
  assert.ok(!simBox.textContent.includes('PLAYED_GAME'));
  assert.ok(simBox.textContent.includes('unbekannt'));
  assert.ok(simBox.textContent.includes('lost'));

  console.log(JSON.stringify({ ok: true }));
})();
"""
    )
    assert out == {"ok": True}


def test_app_js_play_notes_and_replace_param_via_node() -> None:
    out = _node(
        r"""
const fs = require('fs');
const assert = require('assert');

class ClassList {
  constructor(el) { this.el = el; this.set = new Set(); }
  add(...names) { names.forEach((n) => n && this.set.add(n)); this.el._className = [...this.set].join(' '); }
  remove(...names) { names.forEach((n) => this.set.delete(n)); this.el._className = [...this.set].join(' '); }
  toggle(name, force) {
    if (force === undefined) force = !this.set.has(name);
    if (force) this.set.add(name); else this.set.delete(name);
    this.el._className = [...this.set].join(' ');
  }
  contains(name) { return this.set.has(name); }
}

class El {
  constructor(tag, id = '') {
    this.tagName = String(tag || 'DIV').toUpperCase();
    this.nodeType = 1;
    this.id = id;
    this.children = [];
    this.attrs = {};
    this.dataset = {};
    this.listeners = {};
    this.hidden = false;
    this.disabled = false;
    this._value = '';
    this.checked = false;
    this._text = '';
    this._className = '';
    this.classList = new ClassList(this);
    this.style = {};
    this.options = [];
  }
  set className(v) {
    this._className = String(v || '');
    this.classList.set = new Set(this._className.split(/\s+/).filter(Boolean));
  }
  get className() { return this._className; }
  set textContent(v) { this._text = v == null ? '' : String(v); this.children = []; }
  get textContent() {
    if (!this.children.length) return this._text;
    return this._text + this.children.map((c) => (typeof c === 'string' ? c : c.textContent)).join('');
  }
  set value(v) { this._value = v == null ? '' : String(v); }
  get value() { return this._value; }
  setAttribute(k, v) {
    this.attrs[k] = String(v);
    if (k === 'id') this.id = String(v);
    if (k === 'class') this.className = String(v);
  }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  append(...nodes) {
    for (const n of nodes) {
      if (n == null) continue;
      if (typeof n === 'string' || n.nodeType === 3) {
        this.children.push(typeof n === 'string' ? n : n.textContent);
      } else {
        this.children.push(n);
        if (this.tagName === 'SELECT' && n.tagName === 'OPTION') this.options.push(n);
      }
    }
  }
  replaceChildren(...nodes) { this.children = []; this.options = []; this._text = ''; this.append(...nodes); }
  appendChild(node) { this.append(node); return node; }
  insertBefore(node) { this.append(node); return node; }
  removeChild() {}
  insertAdjacentElement() {}
  prepend(...nodes) { this.children = [...nodes.filter((n) => n != null), ...this.children]; }
  removeAttribute(k) { delete this.attrs[k]; }
  contains(node) { return this.all().includes(node); }
  addEventListener(k, f) { (this.listeners[k] ||= []).push(f); }
  removeEventListener() {}
  all() {
    const out = [this];
    for (const c of this.children) {
      if (c && typeof c !== 'string' && c.all) out.push(...c.all());
    }
    return out;
  }
  querySelectorAll(sel) {
    const nodes = this.all();
    if (sel.startsWith('.')) return nodes.filter((n) => n.classList.contains(sel.slice(1)));
    return nodes.filter((n) => n.tagName === sel.toUpperCase());
  }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
  closest() { return null; }
  focus() {}
}

const registry = {};
for (const id of [
  'commander-select', 'theme-toggle', 'deck-select', 'new-deck', 'import-text',
  'branch-select', 'new-branch', 'counter', 'check-pill', 'save-state', 'save',
  'deck-labels', 'history', 'export', 'data-state', 'auto-deck-note', 'q',
  'color-filter', 'filter-toggle', 'filter-count', 'filters-more', 'type-filter',
  'role-filter', 'label-filter', 'mv-min', 'mv-max', 'f-free', 'f-notin', 'f-fav',
  'f-excl', 'f-tier', 'f-sim-label', 'f-sim', 'f-sim-text', 'f-unowned', 'cohort',
  'bracket-bar', 'gc-band-bar', 'universe', 'universe-info', 'sort',
  'quick-filter-presets', 'view-toggle', 'columns', 'pool-count', 'column-menu',
  'pool-body', 'play-row', 'play-state', 'deck-tabs', 'deck-body', 'preview',
  'modal', 'modal-box', 'toast',
]) {
  registry[id] = new El(id.includes('select') || ['universe', 'sort', 'cohort', 'type-filter', 'role-filter', 'label-filter'].includes(id) ? 'select' : 'div', id);
}
registry['f-free'].checked = true;
registry['f-tier'].checked = true;
registry['preview'].append(new El('img'));

const document = {
  getElementById: (id) => registry[id] || null,
  createElement: (tag) => new El(tag),
  createTextNode: (text) => ({ nodeType: 3, textContent: String(text) }),
  addEventListener() {},
  querySelectorAll: () => [],
  querySelector: () => null,
  body: new El('body'),
  documentElement: new El('html'),
  activeElement: null,
};

const memStore = new Map();
const localStorage = {
  getItem: (k) => (memStore.has(k) ? memStore.get(k) : null),
  setItem: (k, v) => { memStore.set(k, String(v)); },
  removeItem: (k) => { memStore.delete(k); },
};
const location = { search: '?replace=Sol%20Ring&revision=chulane%40rev1', pathname: '/index.html' };
const window = { localStorage, addEventListener() {}, matchMedia: () => ({ matches: false, addEventListener() {} }), location, innerWidth: 1280, innerHeight: 800 };

const requestedPaths = [];
const fetchStub = async (path) => {
  requestedPaths.push(path);
  if (path.startsWith('/api/commanders')) {
    return { ok: true, json: async () => [{ name: 'Chulane, Teller of Tales', short: 'Chulane', has_data: true, in_collection: true, source_decks: 10 }] };
  }
  if (path.startsWith('/api/pool?')) {
    return {
      ok: true,
      json: async () => ({
        commander_ids: ['cmd-chulane'],
        cohorts: { all: 10 },
        small_denominator: 30,
        roles: ['ramp'],
        cards: [
          { card_id: 'cmd-chulane', name: 'Chulane, Teller of Tales', group: 'Creature', mana_cost: '{2}{G}{W}{U}', mana_value: 5, colors: 'GUW', owned: 1, available: 1, reserved: 0, basic: false, roles: [], labels: [], text: '', type_line: 'Legendary Creature', has_image: false, decks: { all: 10 }, decks_known: true },
          { card_id: 'c-sol', name: 'Sol Ring', group: 'Artifact', mana_cost: '{1}', mana_value: 1, colors: '', owned: 1, available: 1, reserved: 0, basic: false, roles: ['ramp'], labels: [], text: '{T}: Add {C}{C}.', type_line: 'Artifact', has_image: false, decks: { all: 10 }, decks_known: true },
        ],
      }),
    };
  }
  if (path.startsWith('/api/decks/') && path.includes('/play-notes')) {
    return {
      ok: true,
      json: async () => ({
        deck_id: 'chulane',
        revision_id: 'chulane@rev1',
        notes: [
          { note_id: 1, game_id: 'played-1', deck_id: 'chulane', revision_id: 'chulane@rev1', card_name: 'Sol Ring', note_text: 'Immer stark auf T1', action_hint: 'keep', created_at: '2026-11-27T18:06:00Z' },
        ],
      }),
    };
  }
  if (path === '/api/decks') {
    return {
      ok: true,
      json: async () => [{
        deck_id: 'chulane',
        name: 'Chulane',
        commanders: ['Chulane, Teller of Tales'],
        labels: [],
        branches: [{ branch: 'main', revision_id: 'chulane@rev1', cards: 2, has_draft: false }],
      }],
    };
  }
  if (path === '/api/revisions/chulane%40rev1') {
    return {
      ok: true,
      json: async () => ({
        revision_id: 'chulane@rev1',
        cards: [
          { card_id: 'cmd-chulane', quantity: 1, zone: 'commander' },
          { card_id: 'c-sol', quantity: 1, zone: 'main' },
        ],
        issues: [],
        shape: { lands: 0, types: {}, curve: {} },
        roles: { ramp: 1 },
        combos: null,
      }),
    };
  }
  if (path === '/api/decks/chulane/branches/main/draft') {
    return { ok: true, json: async () => ({ draft: null }) };
  }
  if (path.startsWith('/api/cohorts') || path.startsWith('/api/simulations') || path === '/api/games' || path.startsWith('/api/universe') || path.startsWith('/api/layers')) {
    return { ok: true, json: async () => (path.includes('gc-bands') ? null : []) };
  }
  if (path === '/api/check') {
    return { ok: true, json: async () => ({ issues: [], shape: { lands: 0, types: {}, curve: {} }, roles: { ramp: 1 }, combos: null }) };
  }
  if (path.startsWith('/api/allocation')) return { ok: true, json: async () => ({ cards: {} }) };
  if (path === '/api/swap') return { ok: true, json: async () => ({ roles: ['ramp'], candidates: [], source_label: 'all', of: 10, lift_min_n: 5 }) };
  if (path.startsWith('/api/cards/')) return { ok: true, json: async () => ({ used_in: [], edhrec_lines: [] }) };
  if (path === '/api/data-state') return { ok: true, json: async () => ({}) };
  return { ok: true, json: async () => ({}) };
};

const files = [
  'ui.js', 'commander.js', 'search.js', 'cardduel.js', 'cutlab.js', 'allocation.js',
  'buildlist.js', 'exportformats.js', 'zahl.js', 'kartenverstaendnis.js', 'diffimpact.js',
  'deckfacts.js', 'deckevidence.js', 'castability.js', 'packages.js', 'paired.js',
  'deckseries.js', 'experiments.js', 'corpusaudit.js', 'kartenauswertung.js', 'cardtrend.js',
  'overview.js', 'gcband.js', 'wishlist.js', 'cohort.js', 'app.js',
];
let src = files.map((f) => fs.readFileSync(f, 'utf8')).join('\n;\n');
src = src.replace(/\nstart\(\);\s*$/, '\n');
const make = new Function(
  'document', 'window', 'location', 'history', 'fetch', 'localStorage', 'sessionStorage', 'setTimeout', 'clearTimeout', 'requestAnimationFrame',
  src + '\n;return { state, start, renderDeck };'
);
const page = make(document, window, location, { replaceState() {} }, fetchStub, localStorage, { getItem: () => null, removeItem() {} }, () => 0, () => {}, () => 0);

(async () => {
  await page.start();

  const playNotesCall = requestedPaths.find((p) => p.includes('/api/decks/chulane/play-notes'));
  assert.ok(playNotesCall && playNotesCall.includes('revision_id=chulane%40rev1'));
  assert.strictEqual(page.state.playNotes.length, 1);
  assert.strictEqual(page.state.playNotes[0].card_name, 'Sol Ring');

  const deckBodyText = registry['deck-body'].textContent;
  assert.ok(deckBodyText.includes('Notizen aus gespielten Partien (PLAYED_GAME)'));
  assert.ok(deckBodyText.includes('Immer stark auf T1'));
  assert.ok(deckBodyText.includes('Hinweis: keep'));
  assert.ok(deckBodyText.includes('2026-11-27 18:06'));

  // ?replace=Sol Ring&revision=chulane@rev1 opens card modal + renders hint
  assert.ok(page.state.replaceCardHint && page.state.replaceCardHint.cardName === 'Sol Ring');
  assert.ok(deckBodyText.includes('Karte ersetzen (Nachspiel-Blatt): Sol Ring'));
  assert.strictEqual(page.state.modalCardId, 'c-sol');
  assert.strictEqual(registry['modal'].hidden, false);

  console.log(JSON.stringify({ ok: true }));
})();
"""
    )
    assert out == {"ok": True}
