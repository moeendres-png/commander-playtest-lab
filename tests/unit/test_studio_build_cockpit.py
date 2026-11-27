"""Unit and static-contract tests for the BUILD-Studio Deck-Cockpit redesign."""

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
        [node, "-e", script],
        capture_output=True,
        text=True,
        check=True,
        cwd=STATIC,
    )
    return json.loads(done.stdout)


def test_index_html_loads_cockpit_assets_and_markers() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert '<body class="build-studio">' in html
    assert 'id="deck-hud"' in html
    assert 'id="quick-add-open"' in html
    assert html.index('href="app.css"') < html.index('href="build.css"')
    assert html.index('<script src="deckhud.js"></script>') < html.index(
        '<script src="app.js"></script>'
    )


def test_build_css_is_strictly_scoped_to_build_studio() -> None:
    css = (STATIC / "build.css").read_text(encoding="utf-8")
    stripped = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    # Remove @keyframes blocks and unwrap @media blocks so every selector can be checked.
    stripped = re.sub(r"@keyframes\s+[^{]+\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", stripped)
    stripped = re.sub(r"@media[^{]+\{", "", stripped)
    selectors = re.findall(r"([^{}]+)\{[^{}]*\}", stripped)
    assert selectors, "expected CSS rules in build.css"
    for raw in selectors:
        for part in raw.split(","):
            sel = part.strip()
            if not sel:
                continue
            assert sel.startswith("body.build-studio"), f"unscoped selector in build.css: {sel}"


def test_deckhud_summarize_curve_pips_and_lands() -> None:
    script = """
const H = require('./deckhud.js');
const cards = [
  { card_id: 'a', name: 'Forest', group: 'Land', mana_value: 0, mana_cost: '' },
  { card_id: 'b', name: 'Llanowar Elves', group: 'Creature', mana_value: 1, mana_cost: '{G}' },
  { card_id: 'c', name: 'Coiling Oracle', group: 'Creature', mana_value: 2, mana_cost: '{G}{U}' },
  { card_id: 'd', name: 'Hybrid Bear', group: 'Creature', mana_value: 2, mana_cost: '{G/U}{W/P}' },
  { card_id: 'e', name: 'Apex Devastator', group: 'Creature', mana_value: 10, mana_cost: '{8}{G}{G}' },
];
const qty = { a: 4, b: 2, c: 1, d: 1, e: 1 };
const out = H.summarize(cards, (id) => qty[id] || 0);
const empty = H.summarize([{ card_id: 'a', group: 'Land', mana_value: 0, mana_cost: '' }], () => 3);
console.log(JSON.stringify({ out, empty }));
"""
    data = _node_json(script)
    assert isinstance(data, dict)
    out = data["out"]
    assert out["total"] == 9
    assert out["lands"] == 4
    assert out["nonLands"] == 5
    # 2x MV1, 2x MV2, 1x MV10 (bucket 7+)
    assert out["curve"] == [0, 2, 2, 0, 0, 0, 0, 1]
    assert out["avgMv"] == pytest.approx(16 / 5)
    assert out["types"] == {"Land": 4, "Creature": 5}
    assert out["pips"] == {"W": 1, "U": 2, "B": 0, "R": 0, "G": 6, "C": 0}
    assert data["empty"]["avgMv"] is None


def test_deckhud_rank_matches_ordering_limit_and_exclusions() -> None:
    script = """
const H = require('./deckhud.js');
const pool = [
  { card_id: 'cmd', name: 'Sol Commander' },
  { card_id: 'sub', name: 'Absorb' },
  { card_id: 'word', name: 'Dark Solitude' },
  { card_id: 'pref1', name: 'Sol Ring' },
  { card_id: 'pref2', name: 'Sol Talisman' },
  { card_id: 'other', name: 'Llanowar Elves' },
];
const res = H.rankMatches(pool, 'sol', 3, ['cmd']);
console.log(JSON.stringify(res.map((c) => c.card_id)));
"""
    ids = _node_json(script)
    assert ids == ["pref1", "pref2", "word"]


def test_deckhud_and_build_css_have_no_forbidden_wording() -> None:
    forbidden = re.compile(r"\b(zuk[aä]u[fe]\w*|preis\w*|kaufen|price\w*|buy)\b|€", re.IGNORECASE)
    for name in ("deckhud.js", "build.css"):
        text = (STATIC / name).read_text(encoding="utf-8")
        assert not forbidden.search(text), name
