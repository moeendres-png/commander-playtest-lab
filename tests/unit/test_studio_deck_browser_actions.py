"""API and UI tests for Deck-Browser detail actions (#1835)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, cache, similar_decks
from commander_lab.studio.web import create_app

REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = REPO_ROOT / "src" / "commander_lab" / "studio" / "static"


def _seed_source_deck_store(tmp_path: Path) -> tuple[StudioStore, list[tuple[str, str, int]]]:
    """Seed a studio store with a corpus deck holding owned, unowned Scryfall, and 1 unresolved card."""
    from tests.unit.test_studio_builder import _fill

    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    db = store.connection
    source_id = str(db.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0])

    with db:
        # Clean pre-seeded corpus decks so assertions remain exact
        db.execute("DELETE FROM corpus_deck_role")
        db.execute("DELETE FROM corpus_deck_stat")
        db.execute("DELETE FROM corpus_deck_part")
        db.execute("DELETE FROM corpus_cohort")
        db.execute("DELETE FROM corpus_deck_card")
        db.execute("DELETE FROM commander_binding WHERE kind = 'corpus_deck'")
        db.execute("DELETE FROM corpus_deck")

        # Add an unowned Commander-legal green/white/blue Scryfall card (not in inventory)
        db.execute(
            "INSERT INTO scryfall_card("
            "oracle_id, scryfall_id, name, front_name, layout, color_identity, mana_cost, "
            "mana_value, type_line, oracle_text, keywords, produced_mana, commander_legality, "
            "source_id"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "oid-unowned-browser-test",
                "scry-unowned-browser-test",
                "Ajani Unowned Ally",
                "Ajani Unowned Ally",
                "normal",
                "W",
                "{2}{W}",
                3.0,
                "Legendary Planeswalker — Ajani",
                "+1: Draw a card.",
                '["Proliferate"]',
                "",
                "legal",
                source_id,
            ),
        )

        # Pick 10 owned pool cards + Forest (qty 10) + 1 unowned card = 22 cards cleanly
        owned_rows = db.execute(
            "SELECT c.oracle_name FROM card_fact c JOIN inventory i USING (card_id) "
            "WHERE c.commander_legal = 1 AND c.oracle_name != 'Test Commander' "
            "AND c.is_basic_land = 0 ORDER BY c.oracle_name LIMIT 8"
        ).fetchall()
        basic_row = db.execute(
            "SELECT c.oracle_name FROM card_fact c JOIN inventory i USING (card_id) "
            "WHERE c.is_basic_land = 1 ORDER BY c.oracle_name LIMIT 1"
        ).fetchone()
        assert basic_row is not None

        db.execute(
            "INSERT INTO corpus_deck("
            "deck_id, source_id, url, platform, cohort, play_group, deck_date, tags, "
            "fingerprint, legality_audit"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "cd_browser_01",
                source_id,
                "https://example.invalid/cd_browser_01",
                "moxfield",
                "community",
                "",
                "2026-10-01",
                '["blink"]',
                "fp-cd-browser-01",
                "checked",
            ),
        )
        db.execute(
            "INSERT INTO commander_binding(kind, key, commander_name, basis) VALUES (?, ?, ?, ?)",
            ("corpus_deck", "cd_browser_01", "Test Commander", "COMMANDER_ROW"),
        )
        entries: list[tuple[str, str, int]] = [("Test Commander", "commander", 1)]
        for row in owned_rows:
            entries.append((str(row["oracle_name"]), "main", 1))
        entries.append((str(basic_row["oracle_name"]), "main", 10))
        entries.append(("Ajani Unowned Ally", "main", 1))
        for card_name, section, qty in entries:
            db.execute(
                "INSERT INTO corpus_deck_card("
                "deck_id, card_name, quantity, section, normalization_status"
                ") VALUES (?, ?, ?, ?, ?)",
                ("cd_browser_01", card_name, qty, section, "RESOLVED_EXACT"),
            )
    return store, entries


def test_copy_browser_deck_creates_independent_copy_preserving_unowned_and_corpus(
    tmp_path: Path,
) -> None:
    store, _entries = _seed_source_deck_store(tmp_path)
    db = store.connection
    before_corpus = [
        tuple(r)
        for r in db.execute(
            "SELECT deck_id, card_name, quantity, section FROM corpus_deck_card ORDER BY deck_id, section, card_name"
        )
    ]
    before_inventory = [
        tuple(r)
        for r in db.execute(
            "SELECT card_id, owned_lower_bound, available_lower_bound FROM inventory ORDER BY card_id"
        )
    ]
    store.close()
    cache.invalidate()

    app = create_app(tmp_path / "studio")
    client = TestClient(app, headers={"X-Studio": "1"})

    res = client.post("/api/deck-browser/copy", json={"item_id": "source:cd_browser_01"})
    assert res.status_code == 200, res.text
    copied = res.json()

    assert copied["source_item_id"] == "source:cd_browser_01"
    assert copied["commanders"] == ["Test Commander"]
    assert copied["commander_in_collection"] is True
    assert copied["source_total_cards"] == 20
    assert copied["copied_total_cards"] == 20
    assert copied["owned_cards"] == 19
    assert copied["unowned_cards"] == 1
    assert copied["unresolved_cards"] == []

    # 1. Corpus & inventory are untouched
    check_store = StudioStore.open(tmp_path / "studio")
    try:
        cdb = check_store.connection
        after_corpus = [
            tuple(r)
            for r in cdb.execute(
                "SELECT deck_id, card_name, quantity, section FROM corpus_deck_card ORDER BY deck_id, section, card_name"
            )
        ]
        after_inventory = [
            tuple(r)
            for r in cdb.execute(
                "SELECT card_id, owned_lower_bound, available_lower_bound FROM inventory ORDER BY card_id"
            )
        ]
        assert after_corpus == before_corpus
        assert after_inventory == before_inventory
    finally:
        check_store.close()

    # 2. Builder /api/decks + /api/revisions + /api/pool?include_unowned=true reflect exact copy & unowned flag
    decks = client.get("/api/decks").json()
    matching = [d for d in decks if d["deck_id"] == copied["deck_id"]]
    assert len(matching) == 1
    assert matching[0]["branches"][0]["cards"] == 20
    assert matching[0]["branches"][0]["revision_id"] == copied["revision_id"]

    rev = client.get(f"/api/revisions/{copied['revision_id']}").json()
    rev_qty = sum(c["quantity"] for c in rev["cards"])
    assert rev_qty == 20
    unowned_rev = [c for c in rev["cards"] if c["card_id"] == "scryfall:oid-unowned-browser-test"]
    assert len(unowned_rev) == 1
    assert unowned_rev[0] == {
        "card_id": "scryfall:oid-unowned-browser-test",
        "quantity": 1,
        "zone": "main",
    }
    assert any(i["code"] == "not_owned" for i in rev["issues"])

    pool = client.get(
        "/api/pool", params={"commander": "Test Commander", "include_unowned": True}
    ).json()
    pool_by_id = {c["card_id"]: c for c in pool["cards"]}
    ajani = pool_by_id["scryfall:oid-unowned-browser-test"]
    assert ajani["in_collection"] is False
    assert ajani["owned"] == 0
    assert "in_saved_deck" in (ajani.get("selected_by") or [])

    # 3. GET /api/deck-browser/saved:<id>:main returns all 20 cards including unowned (LEFT JOIN inventory)
    det_saved = client.get(f"/api/deck-browser/saved:{copied['deck_id']}:main")
    assert det_saved.status_code == 200
    det_data = det_saved.json()
    assert det_data["deck_id"] == copied["deck_id"]
    assert det_data["revision_id"] == copied["revision_id"]
    saved_cards = {c["name"]: c for c in det_data["cards"]}
    assert "Ajani Unowned Ally" in saved_cards
    assert saved_cards["Ajani Unowned Ally"]["in_collection"] is False
    assert saved_cards["Ajani Unowned Ally"]["owned"] == 0

    # 4. Play /api/table lists the new revision so partie.html?neu=1&revision=... preselects it
    table = client.get("/api/table").json()
    rev_ids = {b["revision_id"] for d in table["decks"] for b in d["branches"]}
    assert copied["revision_id"] in rev_ids


def test_copy_browser_deck_reports_unresolved_cards_and_404_on_unknown(tmp_path: Path) -> None:
    store, _ = _seed_source_deck_store(tmp_path)
    with store.connection as db:
        db.execute(
            "INSERT INTO corpus_deck_card("
            "deck_id, card_name, quantity, section, normalization_status"
            ") VALUES (?, ?, ?, ?, ?)",
            ("cd_browser_01", "Nonexistent Promo Card 999", 2, "main", "UNRESOLVED"),
        )
    # Direct copy call verifies named discrepancy in unresolved_cards instead of silent drop
    res = similar_decks.copy_browser_deck(store, "source:cd_browser_01", name="Eigene Test-Kopie")
    assert res["name"] == "Eigene Test-Kopie"
    assert res["source_total_cards"] == 22
    assert res["copied_total_cards"] == 20
    assert res["unresolved_cards"] == [
        {"name": "Nonexistent Promo Card 999", "quantity": 2, "section": "main"}
    ]
    store.close()
    cache.invalidate()

    app = create_app(tmp_path / "studio")
    client = TestClient(app, headers={"X-Studio": "1"})
    missing = client.post("/api/deck-browser/copy", json={"item_id": "source:does_not_exist"})
    assert missing.status_code == 404


def test_decks_builder_and_partie_js_wiring_for_browser_actions() -> None:
    decks_js = (STATIC_DIR / "decks.js").read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    partie_js = (STATIC_DIR / "partie.js").read_text(encoding="utf-8")

    for marker in (
        "/api/deck-browser/copy",
        "deck-detail-copy-builder",
        "deck-detail-start-game",
        "Als Kopie im Deckbau öffnen",
        "Partie mit diesem Deck starten",
        "studio.pendingToast",
        "index.html?commander=",
        "partie.html?neu=1&revision=",
    ):
        assert marker in decks_js

    assert 'urlParams.get("deck")' in app_js
    assert 'sessionStorage.getItem("studio.pendingToast")' in app_js
    assert 'sessionStorage.getItem("studio.pendingToast")' in partie_js

    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    # Exercise decks.js modal detail rendering and button actions with minimal DOM stubs
    script = """
const vm = require('vm');
const fs = require('fs');
function makeEl(tag) {
  return {
    tagName: tag.toUpperCase(),
    children: [],
    listeners: {},
    attributes: {},
    hidden: false,
    disabled: false,
    value: '',
    textContent: '',
    className: '',
    style: {},
    dataset: {},
    append(...args) { this.children.push(...args); },
    replaceChildren(...args) { this.children = args; },
    addEventListener(ev, fn) { (this.listeners[ev] ||= []).push(fn); },
    setAttribute(k, v) { this.attributes[k] = String(v); },
    hasAttribute(k) { return k in this.attributes; },
    querySelectorAll() { return []; },
  };
}
const elements = {};
for (const id of [
  'commander-select','data-state','db-q','db-origin','db-cohort','db-label',
  'db-must-in','db-must-out','db-unowned','db-apply','db-reset','db-summary',
  'db-decks','db-cooccurrence','modal','modal-box','toast'
]) {
  elements[id] = makeEl('div');
  elements[id].id = id;
}
const toasts = [];
let navigated = null;
const sessionMap = new Map();
const sandbox = {
  document: {
    getElementById: (id) => elements[id] || makeEl('div'),
    createElement: makeEl,
    createTextNode: (t) => String(t),
    addEventListener() {},
  },
  location: { search: '', href: '' },
  sessionStorage: {
    setItem(k, v) { sessionMap.set(k, v); },
    getItem(k) { return sessionMap.get(k) || null; },
    removeItem(k) { sessionMap.delete(k); },
  },
  StudioCommander: {
    current: 'Test Commander',
    fill: async () => {},
  },
  StudioUI: {
    h: (tag, props, ...children) => {
      const node = makeEl(tag);
      for (const [k, v] of Object.entries(props || {})) {
        if (k === 'onclick' && typeof v === 'function') node.addEventListener('click', v);
        else if (k === 'class') node.className = v;
        else if (v !== null && v !== undefined && v !== false) node[k] = v;
      }
      node.children = children.flat(Infinity).filter(Boolean);
      return node;
    },
    kids: (...x) => x.filter(Boolean),
    loading: (m) => makeEl('p'),
    dataState: async () => {},
    num: (n) => String(n),
    germanError: (e) => String(e),
    toast: (msg) => { toasts.push(msg); },
    api: async (url, method, body) => {
      if (url === '/api/deck-browser/copy') {
        return {
          deck_id: 'kopie-test',
          name: 'Kopie: Test Deck',
          branch: 'main',
          revision_id: 'kopie-test@1234',
          commanders: ['Test Commander'],
          commander_in_collection: true,
          source_total_cards: 100,
          copied_total_cards: 100,
          owned_cards: 40,
          unowned_cards: 60,
          unresolved_cards: [],
        };
      }
      if (url.startsWith('/api/deck-browser/source:')) {
        return {
          id: 'source:cd_01',
          origin: 'source',
          name: 'Test Deck',
          platform: 'moxfield',
          url: '',
          commanders: ['Test Commander'],
          cards: [
            { name: 'Test Commander', section: 'commander', quantity: 1, in_collection: true, owned: 1, available: 1 },
            { name: 'Ajani Ally', section: 'main', quantity: 1, in_collection: false, owned: 0, available: 0 },
          ],
        };
      }
      return { total_decks: 0, decks: [], cooccurrence: [] };
    },
  },
  console,
  URLSearchParams,
};
Object.defineProperty(sandbox.location, 'href', {
  get() { return navigated || ''; },
  set(v) { navigated = v; },
});
vm.runInNewContext(fs.readFileSync('decks.js', 'utf8'), sandbox);
(async () => {
  await new Promise((r) => setTimeout(r, 15));
  await sandbox.openDeckDetail({ id: 'source:cd_01', name: 'Test Deck' });
  const flat = [];
  const walk = (n) => {
    if (!n || typeof n !== 'object') return;
    flat.push(n);
    for (const c of n.children || []) walk(c);
  };
  walk(elements['modal-box']);
  const copyBtn = flat.find((n) => n.id === 'deck-detail-copy-builder');
  const playBtn = flat.find((n) => n.id === 'deck-detail-start-game');
  if (!copyBtn || !playBtn) throw new Error('missing modal action buttons');
  await copyBtn.listeners.click[0]();
  const afterCopyHref = navigated;
  await playBtn.listeners.click[0]();
  const afterPlayHref = navigated;
  console.log(JSON.stringify({
    afterCopyHref,
    afterPlayHref,
    toastCount: toasts.length,
    pendingToast: sessionMap.get('studio.pendingToast'),
  }));
})();
"""
    done = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        text=True,
        check=True,
        cwd=STATIC_DIR,
    )
    out = json.loads(done.stdout.strip())
    assert (
        out["afterCopyHref"] == "index.html?commander=Test%20Commander&deck=kopie-test&branch=main"
    )
    assert out["afterPlayHref"] == "partie.html?neu=1&revision=kopie-test%401234"
    assert out["toastCount"] == 2
    assert "100/100" in out["pendingToast"]
