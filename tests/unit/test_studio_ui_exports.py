"""The shared ``StudioUI`` object of ``static/ui.js`` and the pages that use it (#1404, WP-1).

A page that calls ``StudioUI.<name>`` for something ``ui.js`` does not export fails only in the
browser (``TypeError: ... undefined``): tests that stub ``StudioUI`` themselves cannot see it.
``kartenauswertung.js`` used ``StudioUI.kids``, which did not exist, and the tab "Simulation" →
"Karten-Auswertung aus Partien" stayed at "lädt …" while 18 tests stayed green. Here:

* every ``StudioUI.<name>`` (also ``const { name } = StudioUI``) in ``static/*.js`` is exported by
  ``ui.js`` (read from its ``return`` line and, with node, from the real object);
* the card evaluation renders in all three answer paths (table, "zu wenig Daten", error) against
  the REAL ``ui.js`` in a node VM, only ``document`` is a small stand-in.

The node cases are skipped without node (``NOT_RUN``, not a pass).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from commander_lab.studio import card_outcomes
from tests.unit.test_studio_card_outcomes import (
    DECK,
    STATE_A,
    _acceptance_1694,
    _block,
    _stated,
)

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "src" / "commander_lab" / "studio" / "static"
UI = STATIC / "ui.js"

_USE = re.compile(r"\b(?:(?:window|globalThis)\s*\??\.\s*)?StudioUI\s*\??\.\s*([A-Za-z_$][\w$]*)")
_BRACKET = re.compile(
    r"\b(?:(?:window|globalThis)\s*\??\.\s*)?StudioUI\s*(?:\?\.\s*)?\["
    r"|\b(?:window|globalThis)\s*\[\s*[\"']StudioUI[\"']\s*\]"
)
_DESTRUCTURE = re.compile(r"\{([^{}]*)\}\s*=\s*(?:(?:window|globalThis)\s*\??\.\s*)?StudioUI\b")
_ALIAS = re.compile(
    r"\b[A-Za-z_$][\w$]*\s*=(?!=)\s*(?:(?:window|globalThis)\s*\??\.\s*)?StudioUI\b(?!\s*\??\.)"
)


def _exports_from_source() -> set[str]:
    """Keys of the object that ``ui.js`` returns from its IIFE (``a, b: c, d``)."""
    text = UI.read_text(encoding="utf-8")
    found = re.search(r"^  return \{(?P<keys>[^\n]*)\};\s*\n\}\)\(\);", text, re.MULTILINE)
    assert found is not None, "ui.js no longer ends with a one-line return of its exports"
    names = {part.split(":")[0].strip() for part in found.group("keys").split(",") if part.strip()}
    assert len(names) > 15  # the whole object was read, not a fragment
    return names


def _scan_code(code: str, filename: str) -> set[str]:
    """Names read from ``StudioUI`` in one JS snippet (comments cut out)."""
    stripped = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    stripped = re.sub(r"^\s*//.*$", "", stripped, flags=re.MULTILINE)
    names = set(_USE.findall(stripped))
    for group in _DESTRUCTURE.findall(stripped):
        names |= {p.split(":")[0].strip() for p in group.split(",") if p.strip()}
    assert not _BRACKET.search(stripped), f"{filename}: StudioUI[...] hides a use from this guard"
    assert not _ALIAS.search(stripped), f"{filename}: aliasing StudioUI hides uses from this guard"
    return names


def _uses() -> dict[str, set[str]]:
    """File -> names it reads from ``StudioUI`` (comments cut out)."""
    result: dict[str, set[str]] = {}
    for path in sorted(STATIC.glob("*.js")):
        if path == UI:
            continue
        names = _scan_code(path.read_text(encoding="utf-8"), path.name)
        if names:
            result[path.name] = names
    return result


def test_every_studioui_name_used_by_a_page_is_exported_by_ui_js() -> None:
    exports = _exports_from_source()
    uses = _uses()
    assert "kartenauswertung.js" in uses and "num" in uses["kartenauswertung.js"]  # scan reached it
    missing = {name: sorted(names - exports) for name, names in uses.items() if names - exports}
    assert missing == {}, (
        f"StudioUI.<name> without an export in ui.js (TypeError in the browser): {missing}"
    )
    assert "kids" in exports  # the case that was missing


def test_the_page_scan_sees_a_missing_export() -> None:
    """The check above is not vacuous: a use that ui.js does not export is reported, including
    optional chaining, window/globalThis prefixes, renamed destructuring, bracket access and
    aliasing."""
    code = (
        "const x = StudioUI.nope(1); "
        "const y = StudioUI?.optNope(2); "
        "const z = window.StudioUI.winNope(3); "
        "const g = globalThis?.StudioUI?.globNope(4); "
        "const { num: fmt, alsoNope: renamed } = StudioUI; "
        "const { kids, winDestr } = window.StudioUI;"
    )
    names = _scan_code(code, "<snippet>")
    assert names - _exports_from_source() == {
        "nope",
        "optNope",
        "winNope",
        "globNope",
        "alsoNope",
        "winDestr",
    }
    assert {"num", "kids"} <= names
    for hidden in (
        'StudioUI["kids"]',
        'window["StudioUI"]',
        "globalThis['StudioUI']",
        "window.StudioUI['kids']",
    ):
        with pytest.raises(AssertionError, match="hides a use"):
            _scan_code(f"const x = {hidden};", "<bracket>")
    for aliased in (
        "const U = StudioUI;",
        "let U = window.StudioUI;",
        "var U = globalThis?.StudioUI;",
    ):
        with pytest.raises(AssertionError, match="aliasing StudioUI"):
            _scan_code(aliased, "<alias>")


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed: real-ui.js tests NOT_RUN, not a pass")
    return node


# The real ui.js in a node VM. Only the browser objects are small stand-ins; StudioUI is not.
_VM = """
const vm = require("vm");
class FakeNode {
  constructor(tag) { this.tagName = tag.toUpperCase(); this.children = []; this.className = ""; this.attrs = {}; this.open = false; this.hidden = false; }
  get nodeType() { return 1; }
  setAttribute(k, v) { this.attrs[k] = v; }
  hasAttribute(k) { return k in this.attrs; }
  addEventListener() {}
  append(...n) { this.children.push(...n); }
  replaceChildren(...n) { this.children = n; }
}
const text = (value) => ({ nodeType: 3, data: String(value) });
const textOf = (node) => (node.nodeType === 3 ? node.data : node.children.map(textOf).join(" "));
const count = (node, tag) => (node.nodeType === 3 ? 0 : (node.tagName === tag ? 1 : 0)
  + node.children.reduce((n, c) => n + count(c, tag), 0));
const ctx = {
  console, Promise, Map, Set, Error, Number, Math, Array, Object, String, Boolean, JSON, encodeURIComponent, Intl,
  URL, URLSearchParams,
  localStorage: { getItem: () => null, setItem() {} },
  location: { pathname: "/index.html", search: "", href: "http://127.0.0.1/index.html" },
  window: { matchMedia: () => ({ matches: false }) },
  document: { documentElement: { dataset: {} }, addEventListener() {}, querySelectorAll: () => [], getElementById: () => null,
    createElement: (t) => new FakeNode(t), createTextNode: text },
  fetch: async (path) => {
    if (globalThis.__answers && globalThis.__answers[path]) {
      return { ok: true, status: 200, statusText: "OK", json: async () => globalThis.__answers[path] };
    }
    throw new Error("no network in this test: " + path);
  },
};
// Scripts of the page, run in the same context as ui.js (their top-level names are shared).
const load = (file, names) => vm.runInContext(
  require("fs").readFileSync(file, "utf8") + names.map((n) => `\\nglobalThis.${n} = ${n};`).join(""), ctx);
vm.createContext(ctx);
vm.runInContext(__UI__ + "\\nglobalThis.StudioUI = StudioUI;", ctx);
const UI = ctx.StudioUI;
"""


def _run_node(body: str) -> object:
    script = _VM.replace("__UI__", json.dumps(UI.read_text(encoding="utf-8"))) + body
    done = subprocess.run(
        [_node(), "-e", script], capture_output=True, text=True, check=False, cwd=STATIC
    )
    assert done.returncode == 0, done.stdout + done.stderr
    return json.loads(done.stdout)


def test_real_ui_js_exports_the_names_the_pages_use() -> None:
    """The source reading above agrees with the object the browser really gets."""
    script = "console.log(JSON.stringify(Object.keys(UI).sort()));"
    runtime = _run_node(script)
    assert isinstance(runtime, list)
    assert set(runtime) == _exports_from_source()
    used = set().union(*_uses().values())
    assert used - set(runtime) == set()
    assert typeof_kids_is_function()


def typeof_kids_is_function() -> bool:
    out = _run_node(
        "console.log(JSON.stringify(typeof UI.kids === 'function' && "
        "UI.kids(null, 'a', false, undefined, 'b').length === 2));"
    )
    return out is True


def test_card_evaluation_renders_in_every_answer_path_with_the_real_ui_js() -> None:
    """Regression of #1404 WP-1: the table (one stratum, status OK), the sections of strata that
    are not pooled (NOT_POOLED), "zu wenig Daten" (NO_GAMES) and the error render and never stay
    at "lädt …" or throw. ``h`` is the real ``StudioUI.h``; the answers are the server's own."""
    one = _stated(_block("A", 10, 6) + _block("F", 10, 4), STATE_A, prefix="a")
    table = card_outcomes.stand_tables(one, deck_id=DECK, min_exposed=1)
    sections = card_outcomes.stand_tables(_acceptance_1694(), deck_id=DECK, min_exposed=1)
    empty = card_outcomes.stand_tables([], deck_id=DECK, min_exposed=1)
    # each answer takes the path of kartenauswertung.js it is named for (lines 450, 460, 470)
    assert (table["status"], sections["status"], empty["status"]) == (
        "OK",
        "NOT_POOLED",
        "NO_GAMES",
    )
    assert table["cards"]  # the plain table has rows
    script = f"""
const mod = (() => {{
  const src = require("fs").readFileSync("kartenauswertung.js", "utf8");
  const m = {{ exports: {{}} }};
  new Function("module", "StudioUI", src)(m, UI);
  return m.exports;
}})();
const run = async (api) => {{
  const slot = new FakeNode("div");
  await mod.renderCardOutcomes(slot, {{
    h: UI.h, deckId: "deck/a", baseRevision: "deck/a@aaaa", dirty: false, api,
  }});
  return {{ text: textOf(slot), tables: count(slot, "TABLE") }};
}};
(async () => {{
  const answer = (payload) => async (url) => (url === "/api/outcomes/decks" ? {{ decks: [] }} : payload);
  const out = {{
    table: await run(answer({json.dumps(table)})),
    sections: await run(answer({json.dumps(sections)})),
    empty: await run(answer({json.dumps(empty)})),
    error: await run(async (url) => {{
      if (url === "/api/outcomes/decks") return {{ decks: [] }};
      throw {{ detail: "Server nicht erreichbar" }};
    }}),
  }};
  console.log(JSON.stringify(out));
}})().catch((error) => {{ console.error(String(error && error.stack || error)); process.exit(1); }});
"""
    result = _run_node(script)
    assert isinstance(result, dict)
    for name, rendered in result.items():
        assert "lädt …" not in rendered["text"], name
        assert "Karten-Auswertung aus Partien" in rendered["text"], name
    assert result["table"]["tables"] == 1  # the one table of the one stratum
    assert "Karten-Auswertung aus simulierten Partien" in result["table"]["text"]
    assert result["sections"]["tables"] >= 1
    assert (
        "Verschiedene Werte von Tischgröße und Pilot-Fingerabdruck werden nie zusammengeführt"
        in (result["sections"]["text"])
    )
    assert "zu wenig Daten" in result["empty"]["text"]
    assert result["empty"]["tables"] == 0
    assert (
        "konnte nicht geladen werden (unbekannt, nicht 0): Server nicht erreichbar."
        in (result["error"]["text"])
    )
