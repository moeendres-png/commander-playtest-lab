"""The Tam view of the builder (#1404, WP-8): data banner, import hint, pool denominators and the
deck that a commander choice creates.

Found with a Studio on a store that holds the collection and the Chulane source decks but no Tam
deck: the banner was open and filled the whole window (the pool and the deck panel were squeezed to
nothing behind it), "Gezählt für Tam" stood over the 10,551 source decks of the whole store, the
import hint named ``import-all --decklists`` for the Tam decks, the Bauplan and the state page
counted different pools, and choosing the commander created a saved deck without a word.

The page cases run in node against the REAL ``ui.js`` and ``commander.js`` (only ``document`` is a
small stand-in); without node they are skipped, which is NOT_RUN, not a pass. The real layout is
checked in a browser (screenshots in the pull request), here the CSS rules that produce it are
pinned.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import StudioStore, import_all
from commander_lab.studio.tam_import import TAM_COMMANDER_NAME
from commander_lab.studio.web import create_app
from tests.unit import test_studio_builder as builder_tests
from tests.unit.test_studio_builder import _fill
from tests.unit.test_studio_store import _card, _synthetic_cards
from tests.unit.test_studio_ui_exports import _run_node

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "src" / "commander_lab" / "studio" / "static"
CHULANE = "Chulane, Teller of Tales"
OTHER = "Test Commander"  # the commander the fixture binds its three source decks to


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """A store with the collection, card facts and three source decks bound to Test Commander;
    Tam is in the collection (so its pool exists) and has no deck."""
    cards = [*_synthetic_cards(), _card(900, "Tam, the Possibility", "WUBRG", "Legendary Creature")]
    monkeypatch.setattr(builder_tests, "_synthetic_cards", lambda: cards)
    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    store.close()
    return TestClient(create_app(tmp_path / "studio"), headers={"x-studio": "1"})


# --- the import hint: Tam decks come from the Drive files, not from import-all --decklists -----


def test_the_tam_deck_and_view_layers_name_the_drive_importer() -> None:
    hint = import_all.import_command
    assert hint("decklists", TAM_COMMANDER_NAME) == (
        'python scripts/import_tam_drive.py --tam91-dir "<Ordner>"'
    )
    assert hint("corpus", TAM_COMMANDER_NAME) == (
        'python scripts/import_tam_drive.py --tam91-dir "<Ordner>"'
    )
    assert hint("observations", TAM_COMMANDER_NAME) == (
        'python scripts/import_tam_drive.py --edhrec78-dir "<Ordner>"'
    )
    assert (ROOT / "scripts" / "import_tam_drive.py").is_file()  # the named script exists


def test_every_other_layer_and_every_other_commander_keeps_the_import_all_call() -> None:
    tam_rest = {
        key: import_all.import_command(key, TAM_COMMANDER_NAME)
        for key in ("inventory", "scryfall", "roles", "rulings", "playgroup", "signal:x", "marks")
    }
    assert all(
        call.startswith("python -m commander_lab.studio import-all") for call in tam_rest.values()
    )
    assert import_all.import_command("decklists", CHULANE) == (
        f'python -m commander_lab.studio import-all --commander "{CHULANE}" '
        '--inventory "<Sammlung.xlsx>" --decklists "<Ordner>"'
    )
    assert "import_tam_drive" not in import_all.import_command("observations", CHULANE)


def test_layers_answer_says_what_each_layer_counts(client: TestClient) -> None:
    body = client.get("/api/layers", params={"commander": "Test Commander"}).json()
    scope = {item["key"]: item["rows_scope"] for item in body["layers"]}
    assert scope["decklists"] == "commander"  # bound to this commander
    assert scope["edhrec_combo_decks"] == "commander"  # a signal the commander owns
    # rows AND coverage include the decks and observations of every other commander
    assert scope["corpus"] == scope["observations"] == "all_commanders"
    # facts about cards: rows over the store, coverage over this commander's pool
    facts = ("inventory", "scryfall", "roles", "rulings", "playgroup", "marks", "edhrec_salt")
    assert all(scope[key] == "card_facts" for key in facts)
    assert set(scope.values()) == {"commander", "all_commanders", "card_facts"}  # nothing unnamed
    tam = client.get("/api/layers", params={"commander": TAM_COMMANDER_NAME}).json()
    commands = {item["key"]: item["command"] for item in tam["layers"]}
    assert commands["decklists"].startswith("python scripts/import_tam_drive.py ")
    assert commands["observations"].startswith("python scripts/import_tam_drive.py ")
    assert commands["roles"].startswith("python -m commander_lab.studio import-all ")


# --- the banner (ui.js dataState), real ui.js + real commander.js in node ----------------------

_BANNER = """
const answers = __ANSWERS__;
globalThis.__answers = answers;
load("commander.js", ["StudioCommander"]);
const run = async (commander, tweak, options) => {
  const layers = JSON.parse(JSON.stringify(answers["/api/layers?commander=" + encodeURIComponent(commander)]));
  if (tweak) tweak(layers);
  globalThis.__answers = { ...answers, ["/api/layers?commander=" + encodeURIComponent(commander)]: layers };
  UI.clearSharedCache();
  const host = new FakeNode("div");
  await UI.dataState(host, commander, options);
  const details = host.children[0];
  return {
    open: Boolean(details && details.open), text: textOf(host),
    tables: count(host, "TABLE"), summary: textOf(details.children[0]),
  };
};
(async () => {
  const out = {
    tam: await run("__TAM__"),
    tam_essential: await run("__TAM__", (l) => { l.layers.find((x) => x.key === "inventory").status = "MISSING"; }),
    chulane: await run("__CHU__"),
    tier_list: await run("__TAM__", null, { only: ["inventory", "scryfall", "decklists"] }),
  };
  console.log(JSON.stringify(out));
})().catch((e) => { console.error(String(e && e.stack || e)); process.exit(1); });
"""


def _status(source_decks: int) -> dict[str, object]:
    return {
        "source_decks": source_decks,
        "freshness": {
            "total_sources": 10,
            "with_snapshot_date": 9,
            "with_identifier": 0,
            "oldest_snapshot": "2024-11-13",
            "newest_snapshot": "2026-11-15",
        },
        "source_layers": [
            {
                "layer": "Quelldecks",
                "sources": 10551,
                "dated": 10551,
                "with_identifier": 0,
                "oldest": "2024-11-13",
                "newest": "2026-11-15",
                "undated_note": None,
            }
        ],
    }


def _banner(client: TestClient) -> dict[str, dict[str, object]]:
    answers = {"/api/status": _status(10551)}
    for name in (TAM_COMMANDER_NAME, OTHER):
        body = client.get("/api/layers", params={"commander": name}).json()
        answers["/api/layers?commander=" + name.replace(" ", "%20").replace(",", "%2C")] = body
    script = (
        _BANNER.replace("__ANSWERS__", json.dumps(answers))
        .replace("__TAM__", TAM_COMMANDER_NAME)
        .replace("__CHU__", OTHER)
    )
    result = _run_node(script)
    assert isinstance(result, dict)
    return result  # type: ignore[return-value]


def test_banner_is_closed_unless_nothing_to_build_with_is_there(client: TestClient) -> None:
    out = _banner(client)
    # Tam has no decks: that is a layer note, not a stop. The fixture has collection and card facts.
    assert out["tam"]["open"] is False
    assert out["chulane"]["open"] is False
    # no collection: the one case that opens it (the person must import first)
    assert out["tam_essential"]["open"] is True
    assert "Es fehlen Daten" in str(out["tam"]["summary"])
    # the tier list asks for the layers of its index only and keeps the deck lists among them:
    # without deck lists there is no index, so its banner stays open as before
    assert out["tier_list"]["open"] is True


def test_banner_counts_for_the_commander_and_names_what_is_store_wide(client: TestClient) -> None:
    text = str(_banner(client)["tam"]["text"])
    assert "Pool und Abdeckung gezählt für Tam." in text
    assert "Gezählt für Tam." not in text  # the old sentence over store-wide figures
    assert (
        "Quellenstand: gezählt im ganzen Store, alle Commander zusammen (nicht nur für Tam)."
        in text
    )
    assert "Quellschicht (ganzer Store)" in text
    # the source decks of the store (all commanders) next to the ones bound to Tam
    assert (
        "Quelldecks im Store (alle Commander zusammen, mit Duplikaten): 10.551 "
        "· an Tam gebunden (ohne Duplikate): 0." in text
    )
    flat = re.sub(r"\s+", " ", text)
    assert "Gezählt über" in text and "Pool von Tam abgedeckt" in text
    # per layer: what rows AND coverage count (corpus and EDHREC views mix every commander)
    assert "Korpus (Decks, alle) 4 alle Commander (Zeilen und Abdeckung)" in flat
    assert "Sammlung (Bestand)" in flat and "Kartenfakten: Zeilen im Store" in flat
    assert "Quelldecks (Decklisten) 0 Tam" in flat  # bound rows: this commander only
    # the hint for the Tam decks and the sentence why it is not import-all
    assert 'python scripts/import_tam_drive.py --tam91-dir "<Ordner>"' in text
    assert (
        'import-all --commander "Tam, the Possibility" --inventory "<Sammlung.xlsx>" --decklists'
        not in text
    )
    assert "nicht aus import-all" in text
    assert (
        'COMMANDER_LAB_STUDIO_DATA (oder COMMANDER_LAB_OWNER_DATA) kommt --db "<Datenordner>"'
        in text
    )


def test_banner_of_another_commander_has_no_tam_drive_hint(client: TestClient) -> None:
    text = str(_banner(client)["chulane"]["text"])
    assert "import_tam_drive" not in text
    assert "Pool und Abdeckung gezählt für Test Commander." in text
    assert "an Test Commander gebunden (ohne Duplikate): 3." in text


# --- Bauplan and state page: different pools say so ---------------------------------------------

_POOLS = """
load("commander.js", ["StudioCommander"]);
const plan = {
  cohort: "all", cohort_decks: 0, small_sample: false, small_denominator: 30,
  pool_tagged: 1408, pool_total: 1654, steps: [], role_coverage: [{ role: "ramp", deck_count: 0, pool_tagged: 1, pool_total: 1654, span: null }],
};
const deps = {
  h: UI.h, api: async () => plan, entries: () => [], fail: () => "", roleName: (r) => r, openCard() {}, add() {},
  poolCardById: () => null, cohort: () => "all", cohortName: () => "alle Quelldecks", commander: "x",
  token: () => 1, isCurrent: () => true,
};
(async () => {
  vm.runInContext(require("fs").readFileSync("packages.js", "utf8") + "\\nglobalThis.renderBuildPlanTab = renderBuildPlanTab;", ctx);
  const body = new FakeNode("div");
  await ctx.renderBuildPlanTab(body, deps);
  console.log(JSON.stringify({ plan: textOf(body) }));
})().catch((e) => { console.error(String(e && e.stack || e)); process.exit(1); });
"""


def test_bauplan_names_its_pool_as_the_collection_only() -> None:
    result = _run_node(_POOLS)
    assert isinstance(result, dict)
    text = str(result["plan"])
    assert (
        "Pool (nur Sammlung, ohne die fehlenden Karten des Schalters) mit bekannter Tagger-Rolle: 1.408/1.654"
        in text
    )
    assert (
        "Rollen-Belegung im Pool (nur Sammlung, ohne die fehlenden Karten des Schalters: 1.408/1.654 Karten belegt)"
        in text
    )


_STATE = """
load("commander.js", ["StudioCommander"]);
vm.runInContext(require("fs").readFileSync("overview.js", "utf8") + "\\nglobalThis.buildOverview = _buildOverviewNodes;", ctx);
const card = (i, roles) => ({ card_id: "c" + i, roles, group: "Spell" });
const pool = [card(1, ["ramp"]), card(2, ["ramp"]), card(3, []), card(4, ["removal"])];
const nodes = (includeUnowned) => {
  const data = {
    shape: null, reference: {}, deckCards: [], commanderCards: [], deckRoles: {}, pool, small: 30, cohort: "all",
    combos: null, issues: [], dirty: false, landData: null, castData: null, factsData: null, layersData: null,
    deckTotal: 1, qty: () => 0, bars: () => [],
  };
  const deps = { h: UI.h, cohortName: () => "alle Quelldecks", roleName: (r) => r, includeUnowned };
  return textOf({ nodeType: 1, children: ctx.buildOverview(data, deps, {}) });
};
console.log(JSON.stringify({ off: nodes(false), on: nodes(true) }));
"""


def test_state_page_names_the_pool_it_counts_with_the_buy_switch() -> None:
    result = _run_node(_STATE)
    assert isinstance(result, dict)
    on, off = str(result["on"]), str(result["off"])
    assert "Pool (Sammlung + fehlende Karten, Schalter an): 3 / 4 Karten mit Rolle belegt." in on
    assert "Pool (Sammlung): 3 / 4 Karten mit Rolle belegt." in off
    assert "Schalter" not in off  # no word about the switch when it is off


def test_bauplan_and_state_page_get_their_pool_flag_from_the_page() -> None:
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "includeUnowned: Boolean(state.includeUnowned)," in app  # state page deps


# --- the layout: an opened banner scrolls inside itself, the builder keeps its room -------------


def _rule(css: str, selector: str) -> str:
    found = re.search(r"(?:^|\n)" + re.escape(selector) + r"\{([^}]*)\}", css)
    assert found is not None, f"no CSS rule for {selector}"
    return found.group(1)


def test_an_opened_banner_cannot_squeeze_the_pool_and_the_deck_panel() -> None:
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    banner = _rule(css, "#data-state")
    assert "max-height:40vh" in banner and "overflow:auto" in banner and "flex:none" in banner
    squeezed = _rule(css, "body:has(#data-state details.datastate[open]) main")
    assert "min-height:540px" in squeezed
    assert "details.datastate{" in css  # the banner box itself is still styled


# --- the deck a commander choice creates ---------------------------------------------------------

_AUTO = """
load("commander.js", ["StudioCommander"]);
const src = require("fs").readFileSync("app.js", "utf8");
const slice = (from, to) => src.slice(src.indexOf(from), src.indexOf(to, src.indexOf(from)));
const code = slice("async function loadDecks() {", "function renderDeckSelects() {")
  + slice("function renderAutoDeckNote() {", "// The Partien page takes the saved revision");
const note = new FakeNode("div");
const run = async (existing) => {
  note.hidden = true; note.children = [];
  const calls = [];
  const state = { decks: [], deckId: "", branch: "", commanderIds: ["cmd"], autoDeck: null, list: new Map() };
  const api = async (url, method) => {
    calls.push(method || "GET");
    if (url === "/api/decks" && method === "POST") return { deck_id: "d1" };
    return existing || calls.includes("POST")
      ? [{ deck_id: "d1", name: "Tam", commanders: ["Tam, the Possibility"], branches: [{ branch: "main", cards: 1 }] }] : [];
  };
  const deckTotal = () => state.commanderIds.length + [...state.list.values()].reduce((a, b) => a + b, 0);
  const f = new Function("state", "api", "StudioUI", "StudioCommander", "COMMANDER", "loadAllocation", "renderPool",
    "renderDeckLabels", "variantKey", "renderDeckSelects", "$", "h", "deckTotal",
    code + "\\nreturn { loadDecks, renderAutoDeckNote };")(
    state, api, UI, ctx.StudioCommander, "Tam, the Possibility", async () => {}, () => {}, () => {},
    (p) => p, () => {}, () => note, UI.h, deckTotal);
  await f.loadDecks();
  f.renderAutoDeckNote();
  const shown = !note.hidden, text = textOf(note);
  state.list.set("x", 3); // a card was added
  f.renderAutoDeckNote();
  return { posts: calls.filter((c) => c === "POST").length, shown, text, hiddenAfterCard: note.hidden };
};
(async () => {
  console.log(JSON.stringify({ created: await run(false), existing: await run(true) }));
})().catch((e) => { console.error(String(e && e.stack || e)); process.exit(1); });
"""


def test_a_deck_created_by_choosing_the_commander_is_announced() -> None:
    result = _run_node(_AUTO)
    assert isinstance(result, dict)
    created, existing = result["created"], result["existing"]
    assert created["posts"] == 1 and created["shown"] is True
    assert (
        "Automatisch angelegt, nicht von dir: Für Tam gab es noch kein Deck, darum ist „Tam“ jetzt "
        "gespeichert (nur der Commander, 1 / 100)."
    ) in created["text"]
    assert "Verstanden" in created["text"]
    assert created["hiddenAfterCard"] is True  # gone with the first card
    # a commander that already has a deck gets no note and no new deck
    assert existing["posts"] == 0 and existing["shown"] is False


def test_the_note_has_its_place_in_the_page_and_stays_hidden_until_needed() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert '<div id="auto-deck-note" class="auto-deck-note" role="status" hidden></div>' in html
    assert html.index('id="data-state"') < html.index('id="auto-deck-note"') < html.index("<main>")
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    assert "display:none" in _rule(css, ".auto-deck-note[hidden]")  # display:flex must not win
