"""Static-contract and node unit tests for the BUILD-Werkbank (work modes, split, identity theme,
tab rail, command mode of the quick search)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[2] / "src" / "commander_lab" / "studio" / "static"


def _node_json(script: str) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    done = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, check=True, cwd=STATIC
    )
    return json.loads(done.stdout)


def _html() -> str:
    return (STATIC / "index.html").read_text(encoding="utf-8")


def test_index_loads_workbench_between_cockpit_and_page_script() -> None:
    html = _html()
    assert html.index('href="build.css"') < html.index('href="workbench.css"')
    assert (
        html.index('<script src="deckhud.js"></script>')
        < html.index('<script src="workbench.js"></script>')
        < html.index('<script src="app.js"></script>')
    )


def test_command_bar_keeps_every_control_the_page_script_wires() -> None:
    html = _html()
    top = html[
        html.index('<header id="top">') : html.index("</header>", html.index('<header id="top">'))
    ]
    for ident in (
        "deck-select", "new-deck", "import-text", "branch-select", "new-branch",
        "quick-add-open", "counter", "check-pill", "save-state", "save", "deck-labels",
        "history", "export", "wb-identity", "wb-modes", "wb-commands", "wb-help-open",
    ):  # fmt: skip
        assert f'id="{ident}"' in top, ident
    modes = re.findall(r'data-mode="([a-z]+)"', top)
    assert modes == ["collect", "build", "analyze"]
    # the default (before the script runs) is the familiar split view
    assert re.search(r'data-mode="build" class="on" aria-pressed="true"', top)
    for ident in ("pool", "deck", "deck-hud", "deck-tabs", "deck-body", "play-row"):
        assert f'id="{ident}"' in html, ident


def test_workbench_css_is_strictly_scoped_to_build_studio() -> None:
    css = (STATIC / "workbench.css").read_text(encoding="utf-8")
    stripped = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    stripped = re.sub(r"@media[^{]+\{", "", stripped)
    selectors = re.findall(r"([^{}]+)\{[^{}]*\}", stripped)
    assert len(selectors) > 40
    for raw in selectors:
        for part in raw.split(","):
            sel = part.strip()
            if sel:
                assert sel.startswith("body.build-studio"), f"unscoped selector: {sel}"


def test_workbench_layout_places_pool_splitter_and_deck_explicitly() -> None:
    css = (STATIC / "workbench.css").read_text(encoding="utf-8")
    # explicit columns, so hiding the pool in "Analysieren" never shifts the deck into column 1
    assert "body.build-studio main > #pool { grid-column: 1;" in css
    assert "body.build-studio main > #wb-splitter { grid-column: 2;" in css
    assert "body.build-studio main > #deck { grid-column: 3;" in css
    assert "var(--wb-deck-w, var(--wb-deck-default))" in css
    assert "body.build-studio.wb-mode-collect main" in css
    assert "body.build-studio.wb-mode-analyze main" in css
    # small windows: one column, no splitter, in every mode
    small = css[css.index("@media (max-width: 900px)") :]
    assert "body.build-studio.wb-mode-analyze main" in small
    assert "#wb-splitter" in small


def test_identity_helpers_follow_wubrg_order_and_colourless_fallback() -> None:
    data = _node_json(
        """
const W = require('./workbench.js');
console.log(JSON.stringify({
  wug: W.identityLetters('GUW'),
  lower: W.identityLetters('wb'),
  none: W.identityLetters(''),
  nul: W.identityLetters(null),
  hex: W.identityHex('UG'),
  grad: W.identityGradient('WUG'),
  mono: W.identityGradient('R'),
  label: W.identityLabel('GUW'),
}));
"""
    )
    assert isinstance(data, dict)
    assert data["wug"] == ["W", "U", "G"]
    assert data["lower"] == ["W", "B"]
    assert data["none"] == ["C"] and data["nul"] == ["C"]
    assert data["hex"] == ["#3f8fe0", "#3aa568"]
    assert data["grad"] == "linear-gradient(90deg, #e9d9a6 0%, #3f8fe0 50%, #3aa568 100%)"
    assert data["mono"] == "linear-gradient(90deg, #e2553f, #e2553f)"
    assert data["label"] == "Weiß, Blau, Grün"


def test_modes_and_deck_width_are_clamped() -> None:
    data = _node_json(
        """
const W = require('./workbench.js');
console.log(JSON.stringify({
  modes: ['collect', 'build', 'analyze', 'x', '', null].map(W.normalizeMode),
  narrow: W.clampDeckWidth(100, 1400),
  wide: W.clampDeckWidth(5000, 1400),
  mid: W.clampDeckWidth(612.4, 1400),
  tiny: W.clampDeckWidth(500, 500),
  bad: W.clampDeckWidth('abc', 1400),
}));
"""
    )
    assert isinstance(data, dict)
    assert data["modes"] == ["collect", "build", "analyze", "build", "build", "build"]
    assert data["narrow"] == 320
    assert data["wide"] == 1400 - 360
    assert data["mid"] == 612
    assert data["tiny"] == 320  # the deck never gets narrower than its minimum
    assert data["bad"] is None


def test_rank_actions_matches_every_word_and_prefers_label_starts() -> None:
    data = _node_json(
        """
const W = require('./workbench.js');
const acts = [
  { id: 'a', label: 'Ansicht: Simulation', hint: 'Simulationsserien', group: 'Ansicht' },
  { id: 'b', label: 'Als Stand speichern', hint: 'Entwurf sichern', group: 'Deck' },
  { id: 'c', label: 'Simulation starten', hint: '', group: 'Deck' },
  { id: 'd', label: 'Export', hint: 'Deckliste ausgeben', group: 'Deck' },
  { id: 'e', hint: 'no label' },
];
const ids = (q) => W.rankActions(acts, q).map((x) => x.id);
console.log(JSON.stringify({
  all: ids('>'), sim: ids('>sim'), two: ids('> deck liste'), none: ids('>zzz'), plain: ids('spei'),
}));
"""
    )
    assert isinstance(data, dict)
    assert data["all"] == ["a", "b", "c", "d"]
    assert data["sim"] == ["c", "a"]
    assert data["two"] == ["d"]
    assert data["none"] == []
    assert data["plain"] == ["b"]


def test_every_deck_tab_has_an_icon_and_purpose_line() -> None:
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    block = app[app.index("function renderDeck()") : app.index("const workTabs")]
    keys = re.findall(r'\["([a-z]+)", "[^"]+"\]', block)
    assert len(keys) >= 16
    data = _node_json(
        "console.log(JSON.stringify(Object.keys(require('./workbench.js').TAB_INFO)))"
    )
    assert isinstance(data, list)
    assert sorted(keys) == sorted(data)


def test_page_script_hooks_the_workbench_without_owning_it() -> None:
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "dataset: { tab: key }" in app
    assert 'StudioWorkbench.decorateTabs($("deck-tabs"))' in app
    assert "StudioWorkbench.applyIdentity(" in app
    assert "StudioWorkbench.setup({ h, toast, currentTab: () => state.tab, setTab:" in app
    # every hook is guarded, so the builder still runs without the workbench script
    assert app.count('typeof StudioWorkbench !== "undefined"') == 3


def test_quick_search_has_a_command_mode_fed_by_the_workbench() -> None:
    hud = (STATIC / "deckhud.js").read_text(encoding="utf-8")
    assert "setActionProvider, open: openPalette, close: closePalette" in hud
    assert 'q.trimStart().startsWith(">")' in hud
    assert "StudioWorkbench.rankActions(all, q)" in hud
    bench = (STATIC / "workbench.js").read_text(encoding="utf-8")
    assert "StudioDeckHud.setActionProvider(actions)" in bench
    assert 'StudioDeckHud.open(">")' in bench
    # actions reuse the page's own buttons, so their guards (disabled save, dirty draft) hold
    for ident in ("save", "play-state", "history", "export", "new-branch", "import-text"):
        assert f'clickButton("{ident}")' in bench, ident


def test_workbench_text_is_never_set_as_html() -> None:
    bench = (STATIC / "workbench.js").read_text(encoding="utf-8")
    assert "innerHTML" not in bench and "insertAdjacentHTML" not in bench
    assert "localStorage" not in bench  # remembered view settings go through StudioUI only
