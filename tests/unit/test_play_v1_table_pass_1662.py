"""Issue #1662 Part 3: PLAY v1 own revisions as opponents, table memory, rematch, pass shortcuts."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, create_revision, games, launch
from commander_lab.studio.web import create_app
from tests.unit.test_studio_builder import _deck, _fill

STATIC = Path(__file__).resolve().parents[2] / "src" / "commander_lab" / "studio" / "static"
HEADER = {"seed": 7, "engine_commit": "a" * 40, "seats": [{"seat": 0}, {"seat": 1}]}


def _node(script: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    done = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, check=False, cwd=STATIC
    )
    assert done.returncode == 0, done.stderr[-1500:]
    return json.loads(done.stdout)


def _studio_with_two_decks(tmp_path: Path) -> tuple[Path, str, str]:
    folder = tmp_path / "studio"
    store = StudioStore.open(folder)
    try:
        _fill(store, tmp_path)
        rev_a = create_revision(store, deck_id="deck-a", name="Deck A", cards=_deck())
        rev_b = create_revision(store, deck_id="deck-b", name="Deck B", cards=_deck())
    finally:
        store.close()
    return folder, rev_a, rev_b


def test_prepare_table_deck_paths_accepts_own_revisions_as_opponents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder, rev_a, rev_b = _studio_with_two_decks(tmp_path)
    monkeypatch.setenv(launch.ENGINE_COMMAND_ENV, "java -jar bridge.jar full-game")
    monkeypatch.setattr(launch, "cards_unknown_to_pilots", lambda snapshot: [])
    monkeypatch.setattr(launch, "cards_unsupported_by_engine", lambda snapshot: [])

    store = StudioStore.open(folder)
    try:
        game_id, deck_paths = launch.prepare_table_deck_paths(
            store, folder, revision_id=rev_a, opponent_ids=[rev_b], seed=19, play=True
        )
        assert game_id == "deck-a-2p-seed19"
        assert len(deck_paths) == 2
        decks_dir = games.games_folder(folder) / "decks"
        assert deck_paths[0].parent == decks_dir
        assert deck_paths[1].parent == decks_dir
        assert deck_paths[1].name.startswith("opp-")
        own_snap = json.loads(deck_paths[0].read_text(encoding="utf-8"))
        opp_snap = json.loads(deck_paths[1].read_text(encoding="utf-8"))
        assert own_snap["studio_revision_id"] == rev_a
        assert opp_snap["studio_revision_id"] == rev_b

        precon_id = launch.opponent_decks()[0]["deck_id"]
        _, mixed_paths = launch.prepare_table_deck_paths(
            store,
            folder,
            revision_id=rev_a,
            opponent_ids=[str(precon_id), rev_b],
            seed=21,
            play=True,
        )
        assert len(mixed_paths) == 3

        with pytest.raises(KeyError):
            launch.prepare_table_deck_paths(
                store,
                folder,
                revision_id=rev_a,
                opponent_ids=["rev@unknown/main/1"],
                seed=22,
                play=True,
            )

        with pytest.raises(ValueError, match="every seat needs its own deck"):
            launch.prepare_table_deck_paths(
                store, folder, revision_id=rev_a, opponent_ids=[rev_b, rev_b], seed=23, play=True
            )

        bad_rev = create_revision(store, deck_id="bad-opp", name="Bad Opp", cards=_deck()[:20])
        with pytest.raises(ValueError, match="Ungültiges Commander-Deck"):
            launch.prepare_table_deck_paths(
                store, folder, revision_id=rev_a, opponent_ids=[bad_rev], seed=24, play=True
            )

        precon_ids = [str(deck["deck_id"]) for deck in launch.opponent_decks()[:6]]
        assert len(precon_ids) == 6
        with pytest.raises(ValueError, match="PLAY"):
            launch.prepare_table_deck_paths(
                store, folder, revision_id=rev_a, opponent_ids=precon_ids, seed=25, play=True
            )
    finally:
        store.close()


def test_post_api_games_starts_two_own_revisions_and_rejects_unknown_or_over_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder, rev_a, rev_b = _studio_with_two_decks(tmp_path)
    monkeypatch.setenv(launch.ENGINE_COMMAND_ENV, "java -jar bridge.jar full-game")
    monkeypatch.setattr(launch, "cards_unknown_to_pilots", lambda snapshot: [])
    monkeypatch.setattr(launch, "cards_unsupported_by_engine", lambda snapshot: [])

    started_commands: list[list[str]] = []

    class _FakePopen:
        def __init__(self, command: list[str], **_: object) -> None:
            started_commands.append(command)
            game_id = command[command.index("--game-id") + 1]
            games.GameRecorder(folder, game_id, HEADER).close({"status": "finished"})

        def poll(self) -> int:
            return 0

    monkeypatch.setattr(launch.subprocess, "Popen", _FakePopen)

    marker = {"X-Studio": "1"}
    with TestClient(create_app(folder)) as client:
        res_ai = client.post(
            "/api/games",
            json={"revision_id": rev_a, "opponent_ids": [rev_b], "seed": 42},
            headers=marker,
        )
        assert res_ai.status_code == 200, res_ai.text
        assert res_ai.json()["game_id"] == "deck-a-2p-seed42"
        cmd = started_commands[0]
        deck_args = [cmd[i + 1] for i, part in enumerate(cmd) if part == "--deck"]
        assert len(deck_args) == 2
        assert (
            json.loads(Path(deck_args[0]).read_text(encoding="utf-8"))["studio_revision_id"]
            == rev_a
        )
        assert (
            json.loads(Path(deck_args[1]).read_text(encoding="utf-8"))["studio_revision_id"]
            == rev_b
        )

        play_calls: list[dict[str, object]] = []

        def _fake_play_start(
            data_folder: Path,
            deck_paths: list[Path],
            *,
            seed: int,
            human_seats: list[int],
            decision_timeout_seconds: int,
            ai_delay_ms: int,
            game_id: str,
            style: float | None = None,
            seat_styles: dict[int, float] | None = None,
        ) -> dict[str, object]:
            play_calls.append(
                {
                    "game_id": game_id,
                    "deck_paths": [str(p) for p in deck_paths],
                    "human_seats": list(human_seats),
                    "seed": seed,
                }
            )
            return {"game_id": game_id, "interactive": True}

        monkeypatch.setattr(client.app.state.play_manager, "start_game", _fake_play_start)
        res_play = client.post(
            "/api/games",
            json={
                "revision_id": rev_a,
                "opponent_ids": [rev_b],
                "seed": 43,
                "human_seats": [0],
                "decision_timeout_seconds": 0,
            },
            headers=marker,
        )
        assert res_play.status_code == 200, res_play.text
        assert len(play_calls) == 1
        assert play_calls[0]["human_seats"] == [0]
        played_paths = play_calls[0]["deck_paths"]
        assert isinstance(played_paths, list) and len(played_paths) == 2
        assert (
            json.loads(Path(played_paths[1]).read_text(encoding="utf-8"))["studio_revision_id"]
            == rev_b
        )

        res_unknown = client.post(
            "/api/games",
            json={"revision_id": rev_a, "opponent_ids": ["rev@unknown/main/1"], "seed": 44},
            headers=marker,
        )
        assert res_unknown.status_code == 404

        six_opponents = [str(deck["deck_id"]) for deck in launch.opponent_decks()[:6]]
        res_over_lock = client.post(
            "/api/games",
            json={
                "revision_id": rev_a,
                "opponent_ids": six_opponents,
                "seed": 45,
                "human_seats": [0],
            },
            headers=marker,
        )
        assert res_over_lock.status_code == 422


def test_vorspulen_shortcut_action_and_verdict_pass_priority_invariant_with_mutation_probe() -> (
    None
):
    out = _node(
        r"""
const fs = require('fs');
const assert = require('assert');
const FF = require('./vorspulen.js');

assert.deepStrictEqual(FF.shortcutAction(' ', false), { kind: 'pass_once' });
assert.deepStrictEqual(FF.shortcutAction('Enter', false), {
  kind: 'fast_forward',
  stopOnOpponentStack: true,
  label: 'Continue',
});
assert.deepStrictEqual(FF.shortcutAction('Enter', true), {
  kind: 'fast_forward',
  stopOnOpponentStack: false,
  label: 'To my turn',
});
assert.strictEqual(FF.shortcutAction('Escape', false), null);
assert.strictEqual(FF.shortcutAction('a', true), null);

function assertVerdictOnlyPassesPriority(verdict, pending) {
  if (verdict.action === 'stop') return;
  assert.strictEqual(verdict.action, 'pass', 'unexpected action: ' + verdict.action);
  const match = (pending.legal_options || []).find((o) => o.option_id === verdict.optionId);
  assert.ok(match, 'verdict optionId must exist in legal_options');
  assert.strictEqual(match.option_type, 'pass_priority', 'verdict must only return pass_priority');
}

const pendingPriority = {
  decision_id: 'd1',
  decision_class: 'priority',
  actor_id: 'p0',
  seat: 0,
  legal_options: [
    { option_id: 'cast-1', option_type: 'cast_spell', label: 'Cast Sol Ring' },
    { option_id: 'land-1', option_type: 'play_land', label: 'Play Forest' },
    { option_id: 'pass-1', option_type: 'pass_priority', label: 'Pass priority' },
  ],
  pilot_state: {
    active_player_id: 'p1',
    turn_number: 2,
    players: [
      { player_id: 'p0', seat: 0 },
      { player_id: 'p1', seat: 1 },
    ],
    stack: [{ object_id: 's1', name: 'Arcane Signet', controller_id: 'p0' }],
  },
};

for (const stopOnOpponentStack of [false]) {
  const v = FF.verdict(pendingPriority, { startTurn: 2, stopOnOpponentStack });
  assertVerdictOnlyPassesPriority(v, pendingPriority);
  assert.strictEqual(v.action, 'pass');
  assert.strictEqual(v.optionId, 'pass-1');
}

// Mutation probe: if verdict() returned a non-pass option, assertVerdictOnlyPassesPriority MUST fail.
const raw = fs.readFileSync('./vorspulen.js', 'utf8');
const mutatedSrc = raw.replace(
  'option.option_type === "pass_priority"',
  'option.option_type === "cast_spell"'
);
assert.notStrictEqual(mutatedSrc, raw, 'mutation must change source');
const MutatedFF = new Function('module', mutatedSrc + '\nreturn StudioFastForward;')({ exports: {} });
const mutatedVerdict = MutatedFF.verdict(pendingPriority, { startTurn: 2, stopOnOpponentStack: false });
assert.strictEqual(mutatedVerdict.optionId, 'cast-1');
assert.throws(
  () => assertVerdictOnlyPassesPriority(mutatedVerdict, pendingPriority),
  /pass_priority/,
  'mutation probe must fail invariant check when verdict returns non-pass option'
);

console.log(JSON.stringify({ ok: true }));
"""
    )
    assert out == {"ok": True}


def test_partie_ui_table_memory_own_opponents_rematch_and_shortcuts() -> None:
    html = (STATIC / "partie.html").read_text(encoding="utf-8")
    js = (STATIC / "partie.js").read_text(encoding="utf-8")

    for req_id in (
        'id="pass-element"',
        'id="pass-once"',
        'id="pass-continue"',
        'id="pass-to-my-turn"',
        'id="ff-status"',
        'id="hold-confirm-toggle"',
        'id="rematch-btn"',
    ):
        assert req_id in html, req_id
    assert "etwa 20 Sekunden" not in js
    assert "Die Engine startet (gemessen ca. 6\u201310 Sekunden)." in js

    out = _node(
        r"""
const fs = require('fs');
const assert = require('assert');

class El {
  constructor(tag, id) {
    this.tagName = String(tag).toUpperCase();
    this.id = id || '';
    this.children = [];
    this.className = '';
    this.dataset = {};
    this.attrs = {};
    this.hidden = false;
    this.value = '';
    this.disabled = false;
    this.checked = false;
    this.listeners = {};
    this.nodeType = 1;
    this.style = {};
    this._text = '';
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
  append(...xs) {
    for (const x of xs) {
      if (x && x.parent) x.parent.children = x.parent.children.filter((c) => c !== x);
      if (x) x.parent = this;
      this.children.push(x);
      if (this.tagName === 'SELECT' && x && x.nodeType === 1) {
        const opts = x.tagName === 'OPTION' ? [x] : x.all().filter((o) => o.tagName === 'OPTION');
        for (const o of opts) {
          if (o.selected || !this.value) this.value = o.value;
        }
      }
    }
  }
  appendChild(x) { this.append(x); return x; }
  prepend(...xs) { for (const x of xs.reverse()) { if (x) x.parent = this; this.children.unshift(x); } }
  replaceWith(x) { const p = this.parent; if (!p) return; x.parent = p; p.children[p.children.indexOf(this)] = x; }
  replaceChildren(...xs) { this.children = []; this._text = ''; this.append(...xs); }
  remove() { if (this.parent) this.parent.children = this.parent.children.filter((c) => c !== this); }
  addEventListener(k, f) { (this.listeners[k] ||= []).push(f); }
  removeEventListener() {}
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
for (const id of ['rematch-btn', 'new-game', 'modal', 'modal-box', 'speed', 'pass-element', 'pass-once', 'pass-continue', 'pass-to-my-turn', 'ff-status', 'table']) {
  registry[id] = new El(id === 'rematch-btn' || id === 'new-game' || id.startsWith('pass-') && id !== 'pass-element' ? 'button' : 'div', id);
}
registry['rematch-btn'].hidden = true;
registry['modal'].hidden = true;
registry['speed'].value = '250';

const docListeners = {};
const document = {
  createElement: (t) => new El(t),
  createElementNS: (_n, t) => new El(t),
  createTextNode: (t) => ({ nodeType: 3, text: String(t) }),
  getElementById: (id) => (registry[id] ||= new El('div', id)),
  addEventListener(k, f) { (docListeners[k] ||= []).push(f); },
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

const TABLE = {
  engine: { ready: true, pin: 'f4d12f6e80' },
  decks: [
    { name: 'Chulane', branches: [{ revision_id: 'rev@a/main/1', branch: 'main', cards: 100 }] },
    { name: 'Kinnan', branches: [{ revision_id: 'rev@b/main/1', branch: 'main', cards: 100 }] },
  ],
  opponents: [
    { deck_id: 'precon/1', name: 'Precon One', year: '2024', commanders: ['Cmd 1'] },
    { deck_id: 'precon/2', name: 'Precon Two', year: '2024', commanders: ['Cmd 2'] },
    { deck_id: 'precon/3', name: 'Precon Three', year: '2024', commanders: ['Cmd 3'] },
  ],
  pods: null,
};

const posted = [];
const fetchStub = async (path, options) => {
  if (path === '/api/table') return { ok: true, json: async () => TABLE };
  if (path === '/api/games' && options && options.method === 'POST') {
    posted.push(JSON.parse(options.body));
    return { ok: true, json: async () => ({ game_id: 'g-' + posted.length, interactive: Boolean(posted[posted.length - 1].human_seats) }) };
  }
  if (path.endsWith('/decision') && options && options.method === 'POST') {
    posted.push({ decisionPost: JSON.parse(options.body) });
    return { ok: true, json: async () => ({ ok: true }) };
  }
  if (path === '/api/games') return { ok: true, json: async () => [] };
  return { ok: true, json: async () => ({}) };
};

const files = ['ui.js', 'commander.js', 'turn_bar.js', 'vorspulen.js', 'boardclick.js', 'replay.js', 'play_p1a.js', 'follow.js', 'cohort.js', 'partie.js'];
let src = files.map((f) => fs.readFileSync(f, 'utf8')).join('\n;\n');
src = src.replace(/\nstart\(\);\s*$/, '\n');
const make = new Function(
  'document', 'window', 'location', 'history', 'fetch', 'localStorage', 'sessionStorage', 'setTimeout', 'clearTimeout', 'requestAnimationFrame',
  src + '\n;return { state, newGame, start, rematchLastTable, syncRematchButton, endFastForward };'
);
const page = make(document, window, window.location, { replaceState() {} }, fetchStub, localStorage, { getItem: () => null, removeItem() {} }, () => 0, () => {}, () => 0);

(async () => {
  await page.start();
  assert.strictEqual(registry['rematch-btn'].hidden, true, 'rematch hidden before any saved table');

  await page.newGame();
  const box = registry['modal-box'];
  const oppSelects = box.querySelectorAll('.opp-deck');
  assert.ok(oppSelects.length >= 1);
  const groupLabels = oppSelects[0].children.filter((c) => c.tagName === 'OPTGROUP').map((g) => g.attrs.label || g.label);
  assert.deepStrictEqual(groupLabels, ['Precons', 'Eigene Deck-Stände']);
  const ownOptValues = oppSelects[0].children.find((g) => (g.attrs.label || g.label) === 'Eigene Deck-Stände').children.map((o) => o.value);
  assert.deepStrictEqual(ownOptValues, ['rev@a/main/1', 'rev@b/main/1']);

  const countSel = box.all().filter((n) => n.tagName === 'SELECT').find((s) => s.children.some((o) => /Spieler$/.test(o.textContent)));
  countSel.value = '2';
  for (const fn of countSel.listeners.change) fn({});
  const humanCb = box.all().find((n) => n.tagName === 'INPUT' && n.attrs.type === 'checkbox');
  humanCb.checked = true;
  for (const fn of humanCb.listeners.change) fn({});
  const twoOpps = box.querySelectorAll('.opp-deck');
  assert.strictEqual(twoOpps.length, 2);
  twoOpps[0].value = 'rev@b/main/1';
  twoOpps[1].value = 'precon/2';
  const oppStyleSelects = box.querySelectorAll('.opp-style');
  oppStyleSelects[0].value = '0.25';
  oppStyleSelects[1].value = '1.0';

  const startBtn = box.all().find((n) => n.tagName === 'BUTTON' && n.textContent === 'Partie starten');
  for (const fn of startBtn.listeners.click) await fn({});

  assert.strictEqual(posted.length, 1);
  assert.deepStrictEqual(posted[0].opponent_ids, ['rev@b/main/1', 'precon/2']);
  const saved = JSON.parse(localStorage.getItem('studio.play.lastTable'));
  assert.strictEqual(saved.revision_id, 'rev@a/main/1');
  assert.strictEqual(saved.human, true);
  assert.strictEqual(saved.count, 2);
  assert.deepStrictEqual(saved.opponents, ['rev@b/main/1', 'precon/2']);
  assert.deepStrictEqual(saved.oppStyles, [0.25, 1]);
  assert.strictEqual(registry['rematch-btn'].hidden, false, 'rematch shown after saved table');

  // Reopen newGame(): restores saved table
  await page.newGame();
  const restoredCount = box.all().filter((n) => n.tagName === 'SELECT').find((s) => s.children.some((o) => /Spieler$/.test(o.textContent)));
  assert.strictEqual(restoredCount.value, '2');
  const restoredHuman = box.all().find((n) => n.tagName === 'INPUT' && n.attrs.type === 'checkbox');
  assert.strictEqual(restoredHuman.checked, true);
  assert.deepStrictEqual(box.querySelectorAll('.opp-deck').map((e) => e.value), ['rev@b/main/1', 'precon/2']);
  assert.deepStrictEqual(box.querySelectorAll('.opp-style').map((e) => e.value), ['0.25', '1.0']);

  // wantedRevision overrides Seat 1 only
  await page.newGame('rev@b/main/1');
  const seat1Sel = box.all().filter((n) => n.tagName === 'SELECT').find((s) => s.children.some((o) => o.value === 'rev@a/main/1') && !s.classList.contains('opp-deck'));
  assert.strictEqual(seat1Sel.value, 'rev@b/main/1');
  registry['modal'].hidden = true;

  // Rematch starts immediately with saved table and a seed
  for (const fn of registry['rematch-btn'].listeners.click) await fn({});
  assert.strictEqual(posted.length, 2);
  assert.strictEqual(posted[1].revision_id, 'rev@a/main/1');
  assert.deepStrictEqual(posted[1].opponent_ids, ['rev@b/main/1', 'precon/2']);
  assert.deepStrictEqual(posted[1].human_seats, [0]);

  // If engine is not ready, rematch opens the dialog
  TABLE.engine.ready = false;
  await page.rematchLastTable();
  assert.strictEqual(registry['modal'].hidden, false);
  registry['modal'].hidden = true;
  TABLE.engine.ready = true;

  // Live keyboard shortcuts: Enter, Shift+Enter, Space
  const keyHandler = docListeners.keydown[docListeners.keydown.length - 1];
  page.state.gameId = 'g-live';
  page.state.interactive = true;
  page.state.running = true;
  page.state.result = null;
  page.state.submitting = false;
  page.state.humanSeats = [0];
  page.state.concededSeats = [];
  page.state.eliminatedSeats = [];
  page.state.pendingDecision = {
    decision_id: 'dec-live',
    decision_class: 'priority',
    actor_id: 'p0',
    seat: 0,
    legal_options: [{ option_id: 'pass-opt', option_type: 'pass_priority', label: 'Pass priority' }],
    pilot_state: {
      active_player_id: 'p1',
      turn_number: 3,
      players: [{ player_id: 'p0', seat: 0 }, { player_id: 'p1', seat: 1 }],
      stack: [],
    },
  };
  page.state.ff = { on: false, label: '', startTurn: null, stopOnOpponentStack: true };

  const targetPlain = { closest: () => null };
  // Space submits pass_priority
  keyHandler({ key: ' ', shiftKey: false, ctrlKey: false, metaKey: false, altKey: false, target: targetPlain, preventDefault() {} });
  await Promise.resolve();
  await Promise.resolve();
  assert.ok(posted.some((p) => p.decisionPost && p.decisionPost.selected_option_ids[0] === 'pass-opt'));

  // Enter starts fast-forward with stopOnOpponentStack=true
  page.state.submitting = false;
  page.state.pendingDecision = null;
  keyHandler({ key: 'Enter', shiftKey: false, ctrlKey: false, metaKey: false, altKey: false, target: targetPlain, preventDefault() {} });
  assert.strictEqual(page.state.ff.on, true);
  assert.strictEqual(page.state.ff.stopOnOpponentStack, true);
  page.endFastForward('test');

  // Shift+Enter starts fast-forward with stopOnOpponentStack=false
  keyHandler({ key: 'Enter', shiftKey: true, ctrlKey: false, metaKey: false, altKey: false, target: targetPlain, preventDefault() {} });
  assert.strictEqual(page.state.ff.on, true);
  assert.strictEqual(page.state.ff.stopOnOpponentStack, false);
  page.endFastForward('test');

  // Interactive target or open modal blocks shortcut
  registry['modal'].hidden = false;
  keyHandler({ key: 'Enter', shiftKey: false, ctrlKey: false, metaKey: false, altKey: false, target: targetPlain, preventDefault() {} });
  assert.strictEqual(page.state.ff.on, false);
  registry['modal'].hidden = true;
  keyHandler({ key: 'Enter', shiftKey: false, ctrlKey: false, metaKey: false, altKey: false, target: { closest: (sel) => (sel.includes('button') ? {} : null) }, preventDefault() {} });
  assert.strictEqual(page.state.ff.on, false);

  console.log(JSON.stringify({ ok: true }));
})();
"""
    )
    assert out == {"ok": True}


def test_vorspulen_node_test_file_runs() -> None:
    """Runs tests/js/vorspulen.test.mjs (node:test). No node: skipped, which is NOT_RUN, not a pass."""
    import shutil
    import subprocess

    node = shutil.which("node")
    if node is None:
        pytest.skip("NOT_RUN: node is not installed, tests/js/vorspulen.test.mjs did not run")
    repo = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [node, "--test", "--test-reporter=tap", str(repo / "tests" / "js" / "vorspulen.test.mjs")],
        capture_output=True,
        text=True,
        cwd=repo,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    # TAP reporter regardless of TTY (the default reporter differs between a terminal and CI)
    assert "# fail 0" in result.stdout and "# pass 0" not in result.stdout


def test_pass_element_replaces_the_old_controls_and_speed_has_three_steps() -> None:
    import re

    html = (STATIC / "partie.html").read_text(encoding="utf-8")
    js = (STATIC / "partie.js").read_text(encoding="utf-8")
    removed = (
        "response-mode-wrap", "response-mode", "halt-config-wrap", "halt-stack", "halt-combat",
        "halt-own-main", "halt-opp-end", "halt-playable", "auto-pass-wrap", "auto-pass-human",
        "ff-wrap", "ff-btn", "ff-mode", "ff-stack", "ff-stack-hint", "ff-rule",
    )  # fmt: skip
    for removed_id in removed:
        assert f'id="{removed_id}"' not in html, removed_id
        assert f'"{removed_id}"' not in js and f"'{removed_id}'" not in js, removed_id
    for kept in ("pass-element", "pass-once", "pass-continue", "pass-to-my-turn",
                 "ff-status", "hold-confirm-wrap"):  # fmt: skip
        assert f'id="{kept}"' in html, kept
    # buttons and keys take one path
    assert "runPassAction(key, shiftKey, true)" in js and "runPassAction(event.key, event.shiftKey)" in js
    # fast-forward never touches the speed control or the session delay
    for name in ("startFastForward", "endFastForward", "maybeAutoPassHuman"):
        body = js.split(f"function {name}(", 1)[1].split("\nfunction ", 1)[0]
        assert "setAiDelay" not in body and '$("speed")' not in body, name
    m = re.search(r"const SPEEDS = (\[.*?\]);", js)
    assert m is not None
    delays = sorted(entry[0] for entry in json.loads(m.group(1)))
    assert delays == [0, 250, 1000]


def test_a_click_on_the_pass_element_respects_hold_to_confirm_and_escape_stops_a_run() -> None:
    """Review of PR #1893 (P2): a click on the pass element must not bypass "hold to confirm" in a
    critical window; Escape ends a running Continue; a held key does not toggle the run."""
    js = (STATIC / "partie.js").read_text(encoding="utf-8")
    assert "runPassAction(key, shiftKey, true)" in js  # clicks are marked as clicks
    guard = js[js.index("function clickNeedsHold()") : js.index("function runPassAction(")]
    assert "shouldRequireHoldToConfirm" in guard and "state.holdToConfirm" in guard
    body = js[js.index("function runPassAction(") : js.index("async function setAiDelay(")]
    assert "fromClick && clickNeedsHold()" in body
    assert body.index("fromClick && clickNeedsHold()") < body.index("passOnce()")
    assert 'if (state.ff && state.ff.on) { endFastForward("stopped by you"); return; }' in js
    assert "event.repeat &&" in js
