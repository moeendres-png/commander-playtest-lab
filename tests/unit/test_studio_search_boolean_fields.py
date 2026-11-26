"""Unit and integration tests for boolean search syntax and kw/subtype/super/otag fields (#1834)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from commander_lab.studio import answer_models, builder, evidence
from commander_lab.studio.store import StudioStore

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
    name: "Sol Ring",
    type_line: "Artifact",
    group: "Artifact",
    text: "{T}: Add {C}{C}.",
    keywords: [],
    mana_value: 1,
    colors: "",
    roles: ["ramp"],
    labels: ["core"],
    available: 1,
    favorite: false,
    excluded: false
  },
  {
    name: "Mana Crypt",
    type_line: "Artifact",
    group: "Artifact",
    text: "At the beginning of your upkeep, flip a coin. {T}: Add {C}{C}.",
    keywords: [],
    mana_value: 0,
    colors: "",
    roles: ["ramp"],
    labels: [],
    available: 1,
    favorite: false,
    excluded: false
  },
  {
    name: "Worn Powerstone",
    type_line: "Artifact",
    group: "Artifact",
    text: "Worn Powerstone enters the battlefield tapped. {T}: Add {C}{C}.",
    keywords: [],
    mana_value: 3,
    colors: "",
    roles: ["ramp"],
    labels: [],
    available: 1,
    favorite: false,
    excluded: false
  },
  {
    name: "Birds of Paradise",
    type_line: "Creature — Bird",
    group: "Creature",
    text: "Flying. {T}: Add one mana of any color.",
    keywords: ["Flying"],
    mana_value: 1,
    colors: "G",
    roles: ["ramp", "mana_dork"],
    labels: ["dork"],
    available: 2,
    favorite: true,
    excluded: false
  },
  {
    name: "Plummet",
    type_line: "Instant",
    group: "Instant",
    text: "Destroy target creature with flying.",
    keywords: [],
    mana_value: 2,
    colors: "G",
    roles: ["removal"],
    labels: [],
    available: 1,
    favorite: false,
    excluded: false
  },
  {
    name: "Coiling Oracle",
    type_line: "Creature — Snake Elf Druid",
    group: "Creature",
    text: "When Coiling Oracle enters, reveal the top card of your library.",
    keywords: [],
    mana_value: 2,
    colors: "GU",
    roles: ["card_draw", "ramp"],
    labels: [],
    available: 1,
    favorite: false,
    excluded: false
  },
  {
    name: "Chulane, Teller of Tales",
    type_line: "Legendary Creature — Human Druid",
    group: "Creature",
    text: "Vigilance. Whenever you cast a creature spell, draw a card.",
    keywords: ["Vigilance"],
    mana_value: 5,
    colors: "GWU",
    roles: [],
    layers: { fact: { roles: [{ role: "card_draw", original_tag: "draw-engine" }] } },
    labels: ["commander"],
    available: 1,
    favorite: true,
    excluded: false
  },
  {
    name: "Forest",
    type_line: "Basic Land — Forest",
    group: "Land",
    text: "({T}: Add {G}.)",
    keywords: [],
    mana_value: 0,
    colors: "",
    roles: [],
    labels: [],
    available: 20,
    favorite: false,
    excluded: false,
    is_basic_land: true
  }
];
"""


def test_or_union_precedence_and_group_negation() -> None:
    script = (
        """
const S = require('./search.js');
"""
        + SAMPLE_CARDS_JS
        + """
const q = (str) => S.sortByRank(cards, str).map(c => c.name);
const orParsed = S.parseQuery('sol ring or mana crypt');
console.log(JSON.stringify({
  orErrors: orParsed.errors,
  orTextQuery: orParsed.textQuery,
  orIsPlain: orParsed.isPlainFreetext,
  orUnion: q('sol ring or mana crypt'),
  orUpper: q('Sol Ring OR Mana Crypt'),
  noParensPrecedence: q('t:artifact or t:creature mv<=1'),
  withParensPrecedence: q('(t:artifact or t:creature) mv<=1'),
  groupNegation: q('-(t:land or mv>=3)'),
  nestedGroupNegation: q('t:creature -(subtype:elf or kw:flying)'),
  quotedLiteralOr: S.sortByRank([
    { name: 'Choice', type_line: 'Sorcery', text: 'Draw a card or gain 2 life.', keywords: [] },
    { name: 'Single', type_line: 'Sorcery', text: 'Draw a card.', keywords: [] },
  ], '"a card or"').map(c => c.name),
}));
"""
    )
    res = json.loads(_node(script))
    assert res["orErrors"] == []
    assert res["orIsPlain"] is False
    assert bool(res["orTextQuery"]) is True
    assert res["orUnion"] == ["Mana Crypt", "Sol Ring"]
    assert res["orUpper"] == ["Mana Crypt", "Sol Ring"]
    # Precedence: () > AND > or -> unparenthesized matches ALL artifacts (including MV 3 Worn Powerstone) OR MV<=1 creatures
    assert res["noParensPrecedence"] == [
        "Birds of Paradise",
        "Mana Crypt",
        "Sol Ring",
        "Worn Powerstone",
    ]
    # Parenthesized requires mv<=1 on BOTH branches, excluding MV 3 Worn Powerstone and MV 2/5 creatures
    assert res["withParensPrecedence"] == [
        "Birds of Paradise",
        "Mana Crypt",
        "Sol Ring",
    ]
    # -(t:land or mv>=3) excludes Forest, Worn Powerstone (mv 3), Chulane (mv 5)
    assert res["groupNegation"] == [
        "Birds of Paradise",
        "Coiling Oracle",
        "Mana Crypt",
        "Plummet",
        "Sol Ring",
    ]
    # Only Chulane is Creature without Elf subtype and without Flying keyword
    assert res["nestedGroupNegation"] == ["Chulane, Teller of Tales"]
    assert res["quotedLiteralOr"] == ["Choice"]


def test_new_field_operators_kw_subtype_super_and_otag() -> None:
    script = (
        """
const S = require('./search.js');
"""
        + SAMPLE_CARDS_JS
        + """
const q = (str) => S.sortByRank(cards, str).map(c => c.name);
console.log(JSON.stringify({
  kwFlying: q('kw:flying'),
  kwVigilance: q('keyword:vigilance'),
  kwNoneCount: q('kw:none').length,
  subtypeElf: q('subtype:elf'),
  subtypeGermanDruide: q('sub:druide'),
  subtypeNone: q('subtype:none'),
  superLegendary: q('super:legendary'),
  superBasic: q('supertype:basic'),
  superCreatureRejectedAsSupertype: q('super:creature'),
  otagRamp: q('otag:ramp'),
  catDrawEngineFromLayer: q('cat:draw-engine'),
  otagCardDrawDashTolerance: q('otag:card-draw'),
}));
"""
    )
    res = json.loads(_node(script))
    # Plummet mentions "flying" in oracle text but has keywords: [] -> MUST NOT match kw:flying
    assert res["kwFlying"] == ["Birds of Paradise"]
    assert res["kwVigilance"] == ["Chulane, Teller of Tales"]
    assert res["kwNoneCount"] == 6
    assert res["subtypeElf"] == ["Coiling Oracle"]
    assert res["subtypeGermanDruide"] == ["Chulane, Teller of Tales", "Coiling Oracle"]
    assert res["subtypeNone"] == ["Mana Crypt", "Plummet", "Sol Ring", "Worn Powerstone"]
    assert res["superLegendary"] == ["Chulane, Teller of Tales"]
    assert res["superBasic"] == ["Forest"]
    # Creature is a card type, not a supertype
    assert res["superCreatureRejectedAsSupertype"] == []
    assert res["otagRamp"] == [
        "Birds of Paradise",
        "Coiling Oracle",
        "Mana Crypt",
        "Sol Ring",
        "Worn Powerstone",
    ]
    assert res["catDrawEngineFromLayer"] == ["Chulane, Teller of Tales"]
    assert res["otagCardDrawDashTolerance"] == ["Coiling Oracle"]


def test_unsupported_or_broken_boolean_syntax_fails_closed() -> None:
    script = (
        """
const S = require('./search.js');
"""
        + SAMPLE_CARDS_JS
        + """
const invalid = [
  '()',
  '-()',
  '(t:creature',
  't:creature)',
  '-(t:land',
  'or t:creature',
  't:creature or',
  't:creature or or t:land',
  '(or t:creature)',
  '(t:creature or)',
  't:artifact || t:creature',
  't:creature && mv<=2',
  '!t:land',
  'kw:',
  'subtype:',
  'super:',
  'otag:',
];
const validTrailingBang = S.parseQuery('To Arms!');
const report = invalid.map((raw) => {
  const parsed = S.parseQuery(raw);
  return { raw, errors: parsed.errors, matches: S.sortByRank(cards, parsed).length };
});
console.log(JSON.stringify({ report, validTrailingBangErrors: validTrailingBang.errors }));
"""
    )
    res = json.loads(_node(script))
    assert res["validTrailingBangErrors"] == []
    for item in res["report"]:
        assert len(item["errors"]) >= 1, f"Expected explicit syntax error for {item['raw']!r}"
        assert item["matches"] == 0


def test_syntax_helper_and_docs_cover_new_operators() -> None:
    script = (
        f"const S = require({json.dumps(str(STATIC_DIR / 'search.js'))});\n"
        """
console.log(JSON.stringify({
  ops: S.SYNTAX_EXAMPLES.map(x => x.op),
  allValid: S.SYNTAX_EXAMPLES.every(x => S.parseQuery(x.op).errors.length === 0),
}));
"""
    )
    res = json.loads(_node(script))
    assert res["allValid"] is True
    for op in ("kw:flying", "subtype:elf", "super:legendary", "otag:ramp"):
        assert op in res["ops"]
    assert any(" or " in op for op in res["ops"])
    assert any(op.startswith("-(") for op in res["ops"])

    doc = (REPO_ROOT / "docs" / "SEARCH_SYNTAX.md").read_text(encoding="utf-8")
    for needle in ("`kw:`", "`subtype:`", "`super:`", "`otag:`", "`cat:`", "`or`", "`-(...)`"):
        assert needle in doc


def test_pool_and_evidence_expose_keywords_for_owned_and_unowned_cards(tmp_path: Path) -> None:
    from tests.unit.test_studio_builder import _fill

    store = StudioStore.open(tmp_path / "studio")
    try:
        _fill(store, tmp_path)
        db = store.connection
        filler = db.execute(
            "SELECT oracle_id FROM card_fact WHERE oracle_name = ?", ("Filler 00",)
        ).fetchone()
        assert filler is not None
        db.execute(
            "UPDATE scryfall_card SET keywords = ? WHERE oracle_id = ?",
            ('["Flying", "Vigilance"]', str(filler["oracle_id"])),
        )
        source_id = str(db.execute("SELECT source_id FROM source LIMIT 1").fetchone()[0])
        db.execute(
            "INSERT INTO scryfall_card("
            "oracle_id, scryfall_id, name, front_name, layout, color_identity, mana_cost, "
            "mana_value, type_line, oracle_text, keywords, produced_mana, commander_legality, "
            "source_id"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "oid-kw-unowned-pw",
                "scry-kw-unowned-pw",
                "Ajani Unowned Walker",
                "Ajani Unowned Walker",
                "normal",
                "W",
                "{3}{W}",
                4.0,
                "Legendary Planeswalker — Ajani",
                "+1: Flying until end of turn.",
                '["Proliferate"]',
                "",
                "legal",
                source_id,
            ),
        )
        db.commit()

        pool = builder.pool_cards(store, ["Test Commander"], include_unowned=True)
        model_pool = answer_models.PoolAnswer.model_validate(pool)
        by_name = {c.name: c for c in model_pool.cards}
        assert by_name["Filler 00"].keywords == ["Flying", "Vigilance"]
        assert by_name["Ajani Unowned Walker"].keywords == ["Proliferate"]

        ev = evidence.pool_evidence(store, ["Test Commander"])
        model_ev = answer_models.EvidenceAnswer.model_validate(ev)
        ev_by_name = {c.name: c for c in model_ev.cards}
        assert ev_by_name["Filler 00"].keywords == ["Flying", "Vigilance"]
    finally:
        store.close()
