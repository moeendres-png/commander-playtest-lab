"""Unit tests for Pool and Tierlist search syntax (#1451) in static/search.js."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = REPO_ROOT / "src" / "commander_lab" / "studio" / "static"


def _node(script: str) -> str:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed")
    done = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        text=True,
        check=True,
        cwd=STATIC_DIR,
    )
    return done.stdout.strip()


SAMPLE_CARDS_JS = """
const cards = [
  {
    name: "Birds of Paradise",
    type_line: "Creature — Bird",
    group: "Creature",
    text: "Flying. {T}: Add one mana of any color.",
    mana_value: 1,
    colors: "G",
    roles: ["ramp", "fixing"],
    labels: ["dork", "core"],
    available: 2,
    favorite: true,
    excluded: false,
    is_basic_land: false,
    game_changer: false
  },
  {
    name: "Coiling Oracle",
    type_line: "Creature — Snake Elf Druid",
    group: "Creature",
    text: "When Coiling Oracle enters, reveal the top card of your library. If it's a land card, put it onto the battlefield. Otherwise, put that card into your hand.",
    mana_value: 2,
    colors: "GU",
    roles: ["draw", "ramp"],
    labels: ["etb", "bounce-target"],
    available: 1,
    favorite: false,
    excluded: false,
    is_basic_land: false,
    game_changer: false
  },
  {
    name: "Swords to Plowshares",
    type_line: "Instant",
    group: "Instant",
    text: "Exile target creature. Its controller gains life equal to its power.",
    mana_value: 1,
    colors: "W",
    roles: [{ role: "removal" }],
    labels: [],
    available: 1,
    favorite: true,
    excluded: false,
    is_basic_land: false,
    game_changer: false
  },
  {
    name: "Sol Ring",
    type_line: "Artifact",
    group: "Artifact",
    text: "{T}: Add {C}{C}.",
    mana_value: 1,
    colors: "",
    roles: ["ramp"],
    labels: ["core"],
    available: 0,
    favorite: false,
    excluded: false,
    is_basic_land: false,
    game_changer: false
  },
  {
    name: "Rhystic Study",
    type_line: "Enchantment",
    group: "Enchantment",
    text: "Whenever an opponent casts a spell, you may draw a card unless that player pays {1}.",
    mana_value: 3,
    colors: "U",
    roles: ["draw"],
    labels: [],
    available: 1,
    favorite: false,
    excluded: false,
    is_basic_land: false,
    game_changer: true
  },
  {
    name: "Chulane, Teller of Tales",
    type_line: "Legendary Creature — Human Druid",
    group: "Creature",
    text: "Vigilance. Whenever you cast a creature spell, draw a card, then you may put a land card from your hand onto the battlefield.",
    mana_value: 5,
    colors: "GWU",
    roles: [],
    labels: ["commander"],
    available: 1,
    favorite: true,
    excluded: false,
    is_basic_land: false,
    game_changer: false
  },
  {
    name: "Forest",
    type_line: "Basic Land — Forest",
    group: "Land",
    text: "({T}: Add {G}.)",
    mana_value: 0,
    colors: "",
    roles: [],
    labels: [],
    available: 20,
    favorite: false,
    excluded: false,
    is_basic_land: true,
    game_changer: false
  }
];
"""


def test_plain_freetext_and_standalone_phrase_queries() -> None:
    script = (
        """
const S = require('./search.js');
"""
        + SAMPLE_CARDS_JS
        + """
const plain = S.parseQuery('Sol Ring');
const phrase = S.parseQuery('"draw a card"');
const exactPhraseName = S.parseQuery('"Sol Ring"');
const negatedPhrase = S.parseQuery('t:creature -"draw a card"');
console.log(JSON.stringify({
  plainIsFreetext: plain.isPlainFreetext,
  plainMatches: S.sortByRank(cards, 'Sol Ring').map(c => c.name),
  phraseErrors: phrase.errors,
  phraseMatches: S.sortByRank(cards, '"draw a card"').map(c => c.name),
  exactPhraseNameMatches: S.sortByRank(cards, '"Sol Ring"').map(c => c.name),
  negatedPhraseMatches: S.sortByRank(cards, negatedPhrase).map(c => c.name),
}));
"""
    )
    res = json.loads(_node(script))
    assert res["plainIsFreetext"] is True
    assert res["plainMatches"] == ["Sol Ring"]
    assert res["phraseErrors"] == []
    # Standalone phrase must NEVER return a silent empty list when matching cards exist (B9 guard)
    assert res["phraseMatches"] == ["Chulane, Teller of Tales", "Rhystic Study"]
    assert res["exactPhraseNameMatches"] == ["Sol Ring"]
    assert res["negatedPhraseMatches"] == ["Birds of Paradise", "Coiling Oracle"]


def test_field_and_operator_queries() -> None:
    script = (
        """
const S = require('./search.js');
"""
        + SAMPLE_CARDS_JS
        + """
const q = (str) => S.sortByRank(cards, str).map(c => c.name);
console.log(JSON.stringify({
  typeCreatureMvLe2: q('t:creature mv<=2'),
  typeGermanAlias: q('t:kreatur c:gu'),
  colorExactGu: q('c=gu'),
  colorColorless: q('c:c -t:land'),
  identitySubsetGu: q('id:gu -t:land'),
  roleRampFree: q('r:ramp is:free'),
  roleRemovalTierlistShape: q('r:removal'),
  roleNone: q('r:none'),
  labelBounce: q('l:bounce-target'),
  mvEven: q('mv:even -t:land'),
  mvOdd: q('mv:odd is:gamechanger'),
  isLegendary: q('is:legendary'),
  isBasic: q('is:basic'),
  combinedWithFreetext: q('t:creature r:ramp Oracle'),
}));
"""
    )
    res = json.loads(_node(script))
    assert res["typeCreatureMvLe2"] == ["Birds of Paradise", "Coiling Oracle"]
    assert res["typeGermanAlias"] == ["Chulane, Teller of Tales", "Coiling Oracle"]
    assert res["colorExactGu"] == ["Coiling Oracle"]
    assert res["colorColorless"] == ["Sol Ring"]
    assert res["identitySubsetGu"] == [
        "Birds of Paradise",
        "Coiling Oracle",
        "Rhystic Study",
        "Sol Ring",
    ]
    assert res["roleRampFree"] == ["Birds of Paradise", "Coiling Oracle"]
    assert res["roleRemovalTierlistShape"] == ["Swords to Plowshares"]
    assert res["roleNone"] == ["Chulane, Teller of Tales", "Forest"]
    assert res["labelBounce"] == ["Coiling Oracle"]
    assert res["mvEven"] == ["Coiling Oracle"]
    assert res["mvOdd"] == ["Rhystic Study"]
    assert res["isLegendary"] == ["Chulane, Teller of Tales"]
    assert res["isBasic"] == ["Forest"]
    assert res["combinedWithFreetext"] == ["Coiling Oracle"]


def test_syntax_errors_produce_visible_messages_and_never_silent_pass() -> None:
    script = (
        """
const S = require('./search.js');
"""
        + SAMPLE_CARDS_JS
        + """
const badQueries = [
  'foo:bar',
  't:',
  'mv>=',
  't>creature',
  'mv>abc',
  'c:xyz',
  'is:unknownflag',
  ':creature',
  '""',
  '-""',
  '-',
  '"unclosed phrase',
];
const report = badQueries.map((raw) => {
  const parsed = S.parseQuery(raw);
  return {
    raw,
    errors: parsed.errors,
    matches: S.sortByRank(cards, parsed).length,
  };
});
console.log(JSON.stringify(report));
"""
    )
    report = json.loads(_node(script))
    assert len(report) == 12
    for item in report:
        assert len(item["errors"]) >= 1, f"Expected visible syntax error for {item['raw']!r}"
        assert item["matches"] == 0


def test_ui_and_docs_wiring_for_search_syntax() -> None:
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    tierliste_js = (STATIC_DIR / "tierliste.js").read_text(encoding="utf-8")
    tierliste_html = (STATIC_DIR / "tierliste.html").read_text(encoding="utf-8")
    doc_path = REPO_ROOT / "docs" / "SEARCH_SYNTAX.md"

    assert "StudioSearch.parseQuery" in app_js
    assert "search-syntax-error" in app_js
    assert 'src="search.js"' in tierliste_html
    assert "StudioSearch.parseQuery" in tierliste_js
    assert "search-syntax-error" in tierliste_js
    assert doc_path.is_file()
    doc_text = doc_path.read_text(encoding="utf-8")
    for token in ("t:", "o:", "r:", "c:", "id:", "mv", "is:", "search-syntax-error"):
        assert token in doc_text
