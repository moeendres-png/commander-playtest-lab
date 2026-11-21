"""WP-6 of the builder audit (#1404): the tier list honest and readable (T1 to T5).

T1 the spread of one rating H with its sources and n, the origin once above the column; T2 the
single ratings E, F, T, R, K, D, H with reason and rules claims in the card window (route
``/api/cards/{id}/understanding``); T3 the audit mark "vom Prüfer bezweifelt"; T4 rank bands
instead of a seeming rank in ties; T5 the land scale. Nothing of it changes the index, the
tiers, the cuts or the ranking. Store data is synthetic; the data set, the audit file and the
research reports are the repository's own files.
"""

from __future__ import annotations

import copy
import json
import math
import re
import statistics
from collections.abc import Mapping
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import (
    StudioStore,
    card_understanding,
    number_contract,
    strength_view,
    understanding_field,
)
from commander_lab.studio.strength import StrengthSettings
from commander_lab.studio.web import create_app
from tests.unit.studio_synth import add_card, add_signal, make_store
from tests.unit.test_studio_static_guards import STATIC, _node_json, _ui_helpers_prelude

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "data" / "research" / "chulane_rubric_v2_20261118"
CHULANE = card_understanding.DATASET_COMMANDER
TAM = "Tam, Mindful First-Year"
FIELD = understanding_field.FIELD


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _facts() -> dict[str, dict[str, object]]:
    return {str(row["oracle_id"]): row for row in _jsonl(RESEARCH / "data" / "facts.jsonl")}


# ---------- T1: the spread figures come from the raw research files ----------


def _half_rms(
    first: Mapping[str, dict], second: Mapping[str, dict]
) -> tuple[int, float, float, int]:
    cards = sorted(set(first) & set(second))
    diffs = [float(second[c]["scores"]["H"]) - float(first[c]["scores"]["H"]) for c in cards]
    mean_abs = statistics.fmean(abs(d) for d in diffs)
    rms = math.sqrt(statistics.fmean(d * d for d in diffs))
    return len(cards), mean_abs, rms / math.sqrt(2), sum(1 for d in diffs if abs(d) >= 15)


def test_the_spread_constants_are_recomputed_from_the_raw_research_files() -> None:
    """``SPREAD`` names 5 to 8 points (1 sigma, one run): 5 is the repeat spread of the drift test
    (49 cards rated twice by the same rater tier: RMS / sqrt 2), the other model family (70 cards)
    gives about 7.3, and the audit's combined estimate is "7 bis 8" (text of AUDIT_A). The test
    recomputes the figures from the raw files, so the constants cannot drift from their sources."""
    by_card = lambda path: {str(r["card"]): r for r in _jsonl(path)}  # noqa: E731
    full = by_card(RESEARCH / "fullrun_ratings.jsonl")
    drift = _half_rms(full, by_card(RESEARCH / "fulldrift_ratings.jsonl"))
    other = _half_rms(full, by_card(RESEARCH / "audit" / "independent_rater_ratings.jsonl"))
    assert drift[0] == 49 and round(drift[1], 2) == 5.10 and round(drift[2]) == 5
    assert other[0] == 70 and round(other[1], 1) == 7.9 and other[3] == 13
    assert round(other[2], 1) == 7.3
    audit = (RESEARCH / "audit" / "AUDIT_A_ratings.md").read_text(encoding="utf-8")
    assert "±7 bis 8 Punkte (1\u03c3)" in audit and "1\u03c3 etwa 7\u20138 Punkte" in audit
    spread = understanding_field.SPREAD
    assert (spread["unten"], spread["oben"], spread["laeufe_je_karte"]) == (5, 8, 1)
    assert spread["kurz"] == "±5\u20138" and "1\u03c3" in str(spread["text"])
    sources = spread["quellen"]
    assert isinstance(sources, list) and [q["n"] for q in sources] == [49, 70, 230]
    assert all(q["N"] == 922 for q in sources)
    assert "5,10" in sources[0]["kennzahl"] and "13 von 70" in sources[1]["kennzahl"]
    assert "7,9" in sources[1]["kennzahl"] and "7 bis 8" in sources[2]["kennzahl"]
    report = (RESEARCH / "PILOT_REPORT.md").read_text(encoding="utf-8")
    assert "**5,10**" in report and "13 von 70 = 18,6 %" in report
    # no source names a model, only the rater tier or "another model family"
    assert not re.search(r"(?i)claude|gpt|gemini|opus|sonnet|haiku", json.dumps(spread))


# ---------- T3 / T5 on the real data set ----------


def test_the_real_audit_places_35_of_35_doubts_on_the_current_scores() -> None:
    rows = card_understanding.load()
    flags = card_understanding.load_audit()
    assert len(flags) == 35
    found = card_understanding.match_audit(rows, flags)
    assert (found["n_flagged"], found["n_matched"]) == (35, 35)
    assert found["unmatched"] == [] and found["outdated"] == []


def _real_store_and_answer() -> tuple[StudioStore, dict[str, object]]:
    """A store with the 922 rated cards (real oracle ids, invented card ids) and an answer whose
    land marks follow the type line of the research facts."""
    rows = card_understanding.load()
    facts = _facts()
    store = make_store()
    cards: list[dict[str, object]] = []
    for index, (oracle_id, row) in enumerate(sorted(rows.items())):
        card_id = f"card:wp6:{index:04d}"
        store.connection.execute(
            "INSERT INTO card(card_id, oracle_id, oracle_name, color_identity, type_line, "
            "is_basic_land, commander_legal, source_id) VALUES (?, ?, ?, '', ?, 0, 1, ?)",
            (card_id, oracle_id, row["card"], facts[oracle_id]["type_line"], "src:synth"),
        )
        cards.append({"card_id": card_id, "is_land": bool(facts[oracle_id]["is_land_front"])})
    answer = {"commander": CHULANE, "settings": {"bracket": "upgraded"}, "cards": cards}
    return store, answer


def test_the_field_marks_35_of_35_doubts_and_65_lands_on_their_own_scale() -> None:
    store, answer = _real_store_and_answer()
    field = understanding_field.with_understanding(store, answer)[FIELD]
    assert field["n_bewertet"] == field["n_gesamt"] == 922
    figures = field["zahlen"]
    assert len(figures) == 922
    for figure in figures:
        assert number_contract.check(figure) == [] and figure["klasse"] == "URTEIL"
        assert figure["intervall"] is None  # a typical spread is no measured per-card interval
    doubt = field["pruefer_zweifel"]
    assert doubt["verfuegbar"] is True
    assert (doubt["n_markiert"], doubt["n_zugeordnet"], doubt["n_im_pool"]) == (35, 35, 35)
    assert len(doubt["karten"]) == 35
    by_id = {f["id"].removeprefix(understanding_field.ID_PREFIX): f for f in figures}
    marked = [
        i for i, f in by_id.items() if any("vom Prüfer bezweifelt" in n for n in f["hinweise"])
    ]
    assert sorted(marked) == sorted(doubt["karten"])
    first = doubt["karten"][marked[0]]
    assert first["art"] in card_understanding.AUDIT_KINDS and first["grund"]
    lands = field["laender_skala"]
    assert (lands["n_laender"], lands["n_t_null"]) == (65, 58)  # Gutachten C §4: 65, T = 0 at 58
    assert "Gutachten C §4" in lands["quelle"] and len(lands["karten"]) == 65
    land_marked = [
        i for i, f in by_id.items() if understanding_field.LAND_SCALE_TEXT in f["hinweise"]
    ]
    assert sorted(land_marked) == sorted(lands["karten"])
    coverage = field["abdeckung"]
    assert list(coverage) == list(card_understanding.CRITERIA)
    assert all((c["n"], c["N"]) == (922, 922) and c["bezug"] for c in coverage.values())
    assert field["streuung"] == understanding_field.SPREAD


def test_a_missing_audit_file_is_not_available_never_zero_doubts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    store, answer = _real_store_and_answer()
    monkeypatch.setattr(card_understanding, "AUDIT_PATH", tmp_path / "missing.jsonl")
    field = understanding_field.with_understanding(store, answer)[FIELD]
    doubt = field["pruefer_zweifel"]
    assert doubt["verfuegbar"] is False and "nicht gefunden" in doubt["grund"]
    assert doubt["n_markiert"] is None and doubt["n_zugeordnet"] is None
    assert doubt["karten"] == {}
    assert field["zahlen"] and not any(
        "bezweifelt" in note for f in field["zahlen"] for note in f["hinweise"]
    )


def _flag(card: str, rater_h: float, **changes: object) -> card_understanding.AuditFlag:
    raw: dict[str, object] = {
        "card": card,
        "rater_H": rater_h,
        "proposed_H_low": 30,
        "proposed_H_high": 45,
        "kind": "H zu hoch",
        "reason": "synthetic",
        "sample": "top100",
    }
    return card_understanding.parse_audit_row(raw | changes)


def test_unmatched_and_outdated_audit_lines_are_counted_not_shown() -> None:
    rows = card_understanding.parse_lines(
        [json.dumps(_row("o-a", "Alpha", H=65)), json.dumps(_row("o-b", "Beta", H=40))]
    )
    found = card_understanding.match_audit(
        rows, [_flag("Alpha", 65), _flag("Beta", 50), _flag("Gamma", 10)]
    )
    assert (found["n_flagged"], found["n_matched"]) == (3, 1)
    assert list(found["flags"]) == ["o-a"]
    assert found["unmatched"] == ["Gamma"] and found["outdated"] == ["Beta"]
    with pytest.raises(card_understanding.UnderstandingDataError):
        _flag("Alpha", 65, kind="H egal")
    with pytest.raises(card_understanding.UnderstandingDataError):
        _flag("Alpha", 65, proposed_H_low=50, proposed_H_high=40)


# ---------- the ranking stays byte for byte ----------

CMD = "Cmd A"
NAMES = [f"Card {index:02d}" for index in range(8)]


def _row(oracle_id: str, card: str, H: float = 65, **changes: object) -> dict[str, object]:
    scores = {"E": 60, "F": 70, "T": 0, "R": 50, "K": 20, "D": 80, "H": H}
    row: dict[str, object] = {
        "oracle_id": oracle_id,
        "card": card,
        "scores": scores,
        "confidence": "medium",
        "reason": "It does one small thing.",
        "notes": {"E": "cheap", "F": "triggers", "T": "none", "R": "ok", "K": "no", "D": "safe"},
        "rule_claims": [
            {"quote": "Draw a card.", "interaction": "cast", "claim": "draws", "basis": "text"}
        ],
        "version": "v2.1",
        "rater_tier": "large",
        "rubric": "chulane-rubric-v2.1",
    }
    return row | changes


def _store() -> StudioStore:
    store = make_store()
    add_card(store, CMD, type_line="Legendary Creature — Test")
    add_card(store, "Grove", type_line="Land")
    for name in NAMES:
        add_card(store, name)
    for index, name in enumerate([*NAMES, "Grove"]):
        add_signal(store, CMD, "edhrec_commander_inclusion", name, 80 - 10 * (index // 2), 100)
        store.connection.execute(
            "UPDATE card SET oracle_id = ? WHERE oracle_name = ?", (f"o-{name}", name)
        )
    return store


def test_the_understanding_layer_leaves_the_ranking_answer_byte_identical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Index, tiers, cuts, role ranks and every other field of the strength answer are the same
    bytes with and without the layer; the layer only adds the field ``kartenverstaendnis``."""
    store = _store()
    answer = strength_view.compute(store, CMD, StrengthSettings())
    before = json.dumps(answer, sort_keys=True, ensure_ascii=False)
    kept = copy.deepcopy(answer)
    data = card_understanding.parse_lines(
        [json.dumps(_row(f"o-{name}", name, H=5 * i)) for i, name in enumerate([*NAMES, "Grove"])]
    )
    monkeypatch.setattr(card_understanding, "DATASET_COMMANDER", CMD)
    after = understanding_field.with_understanding(store, answer, dataset=data, audit=[])
    assert answer == kept  # the given answer is not modified
    assert set(after) - set(answer) == {FIELD}
    rest = {key: value for key, value in after.items() if key != FIELD}
    assert json.dumps(rest, sort_keys=True, ensure_ascii=False) == before
    tiers = [card["tier"] for card in answer["cards"]]
    assert tiers.count("U") < len(tiers)  # the synthetic answer has real tiers to compare
    field = after[FIELD]
    assert field["laender_skala"]["n_laender"] == 1 and field["laender_skala"]["n_t_null"] == 1
    assert field["pruefer_zweifel"]["n_markiert"] == 0  # an empty audit is a real 0, not missing


# ---------- T2: the card detail ----------


def _detail_store(
    folder: Path | None = None,
) -> tuple[StudioStore, dict[str, card_understanding.UnderstandingRow]]:
    store = make_store(folder)
    add_card(store, CHULANE, type_line="Legendary Creature — Human Druid")
    add_card(store, "Alpha")
    add_card(store, "Grove", type_line="Land — Forest")
    add_card(store, "Nobody")
    for name in ("Alpha", "Grove", "Nobody"):
        store.connection.execute(
            "UPDATE card SET oracle_id = ? WHERE oracle_name = ?", (f"o-{name}", name)
        )
    alpha = _row("o-Alpha", "Alpha", H=65)
    alpha["notes"] = {"E": "cheap"}  # most notes missing: "unbekannt", never invented
    data = card_understanding.parse_lines(
        [json.dumps(alpha), json.dumps(_row("o-Grove", "Grove", H=30, rule_claims=[]))]
    )
    return store, data


def test_the_card_detail_gives_all_seven_criteria_with_reason_and_claims() -> None:
    store, data = _detail_store()
    detail = understanding_field.card_detail(
        store, "card:synth:alpha", CHULANE, dataset=data, audit=[_flag("Alpha", 65)]
    )
    assert detail["verfuegbar"] is True and detail["anzeigen"] is True and detail["bewertet"]
    criteria = detail["kriterien"]
    assert [c["kriterium"] for c in criteria] == list(card_understanding.CRITERIA)
    for entry in criteria:
        figure = entry["zahl"]
        assert number_contract.check(figure) == [] and figure["klasse"] == "URTEIL"
        assert figure["wert"] == data["o-Alpha"]["scores"][entry["kriterium"]]
        assert entry["name"] == understanding_field.CRITERIA_NAMES[entry["kriterium"]]
    assert len({c["zahl"]["id"] for c in criteria}) == 7
    notes = {c["kriterium"]: c["notiz"] for c in criteria}
    assert notes["E"] == "cheap" and notes["H"] is None and notes["T"] is None
    assert detail["begruendung"] == "It does one small thing." and detail["vertrauen"] == "medium"
    assert detail["regelclaims"] == [
        {"quote": "Draw a card.", "interaction": "cast", "claim": "draws", "basis": "text"}
    ]
    coverage = detail["abdeckung"]
    assert list(coverage) == list(card_understanding.CRITERIA)
    assert all((c["n"], c["N"]) == (2, 2) for c in coverage.values())
    doubt = detail["pruefer_zweifel"]
    assert doubt["art"] == "H zu hoch" and doubt["spanne"] == [30.0, 45.0]
    h_figure = criteria[-1]["zahl"]
    assert any("vom Prüfer bezweifelt" in note for note in h_figure["hinweise"])
    assert detail["laender_skala"] is None
    assert "Bracket 3" in detail["kohorte"] and "keine Spielstärke" in detail["hinweis"]
    assert detail["streuung"] == understanding_field.SPREAD


def test_an_unrated_card_is_unknown_in_all_criteria_never_zero() -> None:
    store, data = _detail_store()
    detail = understanding_field.card_detail(
        store, "card:synth:nobody", CHULANE, dataset=data, audit=[]
    )
    assert detail["anzeigen"] is True and detail["bewertet"] is False
    assert len(detail["kriterien"]) == 7
    assert all(c["zahl"] is None and c["notiz"] is None for c in detail["kriterien"])
    assert detail["begruendung"] is None and detail["regelclaims"] == []
    land = understanding_field.card_detail(
        store, "card:synth:grove", CHULANE, dataset=data, audit=[]
    )
    assert land["laender_skala"]["text"] == understanding_field.LAND_SCALE_TEXT
    assert land["regelclaims"] == []


def test_another_commander_gets_nothing_to_show() -> None:
    store, data = _detail_store()
    detail = understanding_field.card_detail(store, "card:synth:alpha", TAM, dataset=data)
    assert detail["anzeigen"] is False and detail["verfuegbar"] is False
    assert "kriterien" not in detail and "zahlen" not in detail
    assert "nur für Chulane" in detail["grund"]


def test_the_route_serves_the_detail_and_refuses_unknown_cards(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, data = _detail_store(tmp_path / "studio")
    store.connection.commit()
    store.close()
    monkeypatch.setattr(card_understanding, "load_cached", lambda: data)
    app = create_app(tmp_path / "studio")
    client = TestClient(app)
    found = client.get("/api/cards/card:synth:alpha/understanding", params={"commander": CHULANE})
    assert found.status_code == 200
    body = found.json()
    assert body["bewertet"] is True and len(body["kriterien"]) == 7
    other = client.get("/api/cards/card:synth:alpha/understanding", params={"commander": TAM})
    assert other.status_code == 200 and other.json()["anzeigen"] is False
    missing = client.get("/api/cards/card:nope/understanding", params={"commander": CHULANE})
    assert missing.status_code == 404
    assert client.get("/api/cards/card:synth:alpha/understanding").status_code == 422


# ---------- T1, T3, T4, T5 in the page (node, real zahl.js and the real blocks) ----------


def _tierliste_prelude() -> str:
    js = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    zahl = (STATIC / "zahl.js").read_text(encoding="utf-8")
    lines = js.splitlines()
    nf_line = next(line for line in lines if line.startswith("const nf = "))
    head_line = next(line for line in lines if line.startswith("const plainHead = "))
    constants = js[js.index("const UNDERSTANDING_NAME") : js.index("const SORTS = [")]
    cells = js[js.index("function strengthItem(card)") : js.index("function datenlageCell(card)")]
    block = js[js.index("// ---------- rank bands (WP-6") : js.index("// ---------- pool view")]
    sort = js[js.index("function sortValue(card, key)") : js.index("function sortBy(key)")]
    stub = """
const h = (tag, props, ...kids) => { const node = {tag, props: props || {}, kids: [],
  append(...more) { this.kids.push(...more.flat(Infinity).filter((k) => k !== null && k !== undefined && k !== false)); }};
  node.append(...kids); return node; };
const text = (n) => (n === null || n === undefined ? '' : typeof n === 'object' ? n.kids.map(text).join('') : String(n));
const has = (n, cls) => Boolean(n && typeof n === 'object' && ((n.props.class || '').split(' ').includes(cls) || n.kids.some((k) => has(k, cls))));
const titleOf = (n) => (n && typeof n === 'object' ? (n.props && n.props.title) || n.kids.map(titleOf).find(Boolean) || '' : '');
const REASON_SHORT = {}, CONF_WORDS = {}, CONFIDENCE_NAMES = {}, CONFIDENCE_TEXT = '', PERCENTILE_SORT = 'pct:';
const roleName = (r) => r, codeLabel = (c) => c, $ = () => null;
const unknown = (t = 'unbekannt') => h('span', {class: 'unknown'}, t);
const spreadKnown = () => false, presentCount = () => 0, corpusAll = () => null, widest = () => null, textfitOf = () => null;
const SPREAD = {kriterium: 'H', text: '± rund 5 bis 8 Punkte (1\u03c3), ein Lauf je Karte', kurz: '±5\u20138', unten: 5, oben: 8, laeufe_je_karte: 1,
  art: 'typische Streuung', quellen: [{name: 'Drift', n: 49, N: 922, bezug: 'Karten', kennzahl: 'mittlere |ΔH| 5,10', datei: 'PILOT_REPORT.md'}]};
const item = (id, tier, index, roles = {}) => ({card_id: id, tier, index, components: [], role_ranks: roles, confidence: null, reason: 'X', note: 'n'});
const figure = (id, wert, notes = []) => ({id: 'kartenverstaendnis:' + id, bezeichnung: 'H Gesamtwert (0 bis 100)', wert, einheit: 'Punkte',
  n: null, N: null, bezug: null, intervall: null, klasse: 'URTEIL', kohorte: 'Chulane, Teller of Tales · Bracket 3 (Annahme der Rater)',
  quelle: 'Rubrik v2.1 (chulane-rubric-v2.1), Modell-Rater Stufe large, 1 Bewerter', stand_datum: null,
  hinweise: ['Rater-Vertrauen medium (Selbstauskunft)', 'nicht gegen Spielergebnisse validiert', ...notes]});
const setup = (cards, field) => {
  const result = {cards, kartenverstaendnis: field};
  globalThis.state = {view: 'commander', strength: {status: 'ready', result, map: new Map(cards.map((c) => [c.card_id, c]))}};
};
"""
    return (
        _ui_helpers_prelude()
        + zahl
        + "\n"
        + nf_line
        + "\n"
        + head_line
        + "\n"
        + constants
        + "\n"
        + cells
        + "\n"
        + block
        + "\n"
        + sort
        + "\n"
        + stub
    )


def test_ties_get_a_band_of_places_and_tier_d_shows_the_band_not_the_decimal() -> None:
    """T4: a tie group shares the band of its places among all cards with a tier (U and N are
    not counted); tier D shows the band instead of the decimal, a tied S to C card keeps the
    index and gets the band, an untied S to C card shows only its index. The sort value stays
    the index, so the order of the list does not change."""
    script = (
        _tierliste_prelude()
        + """
const cards = [item('a', 'S', 80.6, {ramp: {rank: 1, total: 4}}), item('b', 'S', 80.6, {ramp: {rank: 1, total: 4}}),
  item('c', 'A', 50), item('d', 'D', 3, {ramp: {rank: 3, total: 4}}), item('e', 'D', 3), item('f', 'D', 3, {ramp: {rank: 3, total: 4}}),
  item('g', 'D', 1), {...item('u', 'U', 2), tier: 'U'}, {...item('n', 'N', null), tier: 'N'}];
setup(cards, null);
const bands = rankBandsOf(cards).bands;
const out = {bands: Object.fromEntries([...bands].map(([k, v]) => [k, [v.from, v.to, v.k, v.total]]))};
out.cells = Object.fromEntries(cards.slice(0, 7).map((c) => { const cell = strengthCell({card_id: c.card_id}); return [c.card_id, {text: text(cell), band: has(cell, 'rank-band'), title: titleOf(cell)}]; }));
out.role = roleRankText(cards[3], 'ramp', cards[3].role_ranks.ramp);
out.roleSingle = roleRankText(cards[2], 'ramp', {rank: 2, total: 4});
out.sort = cards.slice(0, 7).map((c) => sortValue({card_id: c.card_id}, 'strength'));
const tiered = cards.filter((c) => RANKED_TIERS.has(c.tier));
const groups = new Map(); for (const c of tiered) groups.set(c.index, (groups.get(c.index) || 0) + 1);
out.seeming = tiered.filter((c) => groups.get(c.index) > 1 && !has(strengthCell({card_id: c.card_id}), 'rank-band')).length;
console.log(JSON.stringify(out));
"""
    )
    result = _node_json(script)
    assert isinstance(result, dict)
    assert result["bands"] == {
        "a": [1, 2, 2, 7],
        "b": [1, 2, 2, 7],
        "c": [3, 3, 1, 7],
        "d": [4, 6, 3, 7],
        "e": [4, 6, 3, 7],
        "f": [4, 6, 3, 7],
        "g": [7, 7, 1, 7],
    }
    cells = result["cells"]
    assert (
        "80,6" in cells["a"]["text"]
        and "Rang 1\u20132" in cells["a"]["text"]
        and cells["a"]["band"]
    )
    assert "Gleichstand mit 1 weiteren Karten (Plätze 1\u20132 von 7)" in cells["a"]["title"]
    assert (
        "50,0" in cells["c"]["text"] and not cells["c"]["band"] and "Rang" not in cells["c"]["text"]
    )
    for tied in ("d", "e", "f"):
        assert "Rang 4\u20136" in cells[tied]["text"] and cells[tied]["band"], tied
        assert "3,0" not in cells[tied]["text"], tied  # no decimal in tier D
        assert "Index 3,0" in cells[tied]["title"], tied  # the index stays in the tooltip
    assert "Rang 7" in cells["g"]["text"] and "1,0" not in cells["g"]["text"]
    assert result["role"] == "Rang 3\u20134 von 4 (2 gleichauf)"
    assert result["roleSingle"] == "Rang 2 von 4"
    assert result["sort"] == [80.6, 80.6, 50, 3, 3, 3, 1]
    assert result["seeming"] == 0


def test_the_judgement_cell_shows_spread_confidence_doubt_and_land_scale() -> None:
    """T1, T3, T5: every H figure carries the short spread band (sources in the tooltip), the
    rater's confidence, and where it applies "vom Prüfer bezweifelt" and "Länder-Skala"; the
    origin is visible once in the head line with spread, n, audit counts and land counts, and
    each cell keeps its full origin in the tooltip. Without a figure: "unbekannt", never 0."""
    script = (
        _tierliste_prelude()
        + """
const cards = [item('A', 'S', 70), item('B', 'S', 60), item('L', 'D', 1), item('X', 'D', 1)];
const field = (extra) => ({verfuegbar: true, grund: null, name: 'Kartenverständnis (Modellurteil)', kriterium: 'H', n_bewertet: 3, n_gesamt: 4,
  herkunft: {version: 'v2.1', rubric: 'chulane-rubric-v2.1'},
  zahlen: [figure('A', 90, ['vom Prüfer bezweifelt: H zu hoch; Prüfer-Spanne 30 bis 45 (Rating-Audit A)']), figure('B', 0), figure('L', 30, ['Länder-Skala: x'])],
  streuung: SPREAD, abdeckung: {},
  pruefer_zweifel: {verfuegbar: true, quelle: 'Rating-Audit A', n_markiert: 35, n_zugeordnet: 35, n_im_pool: 1,
    karten: {A: {art: 'H zu hoch', spanne: [30, 45], text: 'vom Prüfer bezweifelt: H zu hoch; Prüfer-Spanne 30 bis 45 (Rating-Audit A)', grund: 'Einmal-Effekt'}}},
  laender_skala: {text: 'Länder-Skala: eigene Skala', quelle: 'Gutachten C §4', n_laender: 1, n_t_null: 1, karten: ['L']}, ...extra});
const show = () => ({cells: cards.map((c) => { const cell = understandingCell(c); return {text: text(cell), title: titleOf(cell),
  doubt: has(cell, 'pruefer-zweifel'), land: has(cell, 'laender-skala'), band: has(cell, 'zahl-band')}; }),
  hint: understandingHint().map(text).join(' ')});
setup(cards, field({})); const out = {full: show()};
setup(cards, field({streuung: null, pruefer_zweifel: {verfuegbar: false, grund: 'Audit-Datei nicht gefunden', n_markiert: null, karten: {}}})); out.missing = show();
console.log(JSON.stringify(out));
"""
    )
    result = _node_json(script)
    assert isinstance(result, dict)
    a, b, land, unrated = result["full"]["cells"]
    assert a["text"].startswith("90") and "±5\u20138" in a["text"] and "mittel" in a["text"]
    assert "Modellurteil" in a["text"] and a["band"] and a["doubt"] and not a["land"]
    assert "Quelle: Rubrik v2.1" not in a["text"]  # the origin is in the head line, not per row
    assert "Quelle: Rubrik v2.1" in a["title"] and "Kohorte: Chulane" in a["title"]
    assert b["text"].startswith("0") and b["band"] and not b["doubt"]  # a real 0 stays 0
    assert land["land"] and "Länder-Skala" in land["text"] and not land["doubt"]
    assert unrated["text"] == "unbekannt" and not unrated["band"]
    hint = result["full"]["hint"]
    assert "Quelle: Rubrik v2.1 (chulane-rubric-v2.1)" in hint and "Kohorte: Chulane" in hint
    assert "Streuung ±5\u20138 (1\u03c3, 1 Lauf je Karte; n = 49)" in hint
    assert "vom Prüfer bezweifelt: 35 von 35 zugeordnet, 1 im Pool" in hint
    assert "Länder-Skala: 1 Länder, T = 0 bei 1" in hint and "3 von 4 Karten bewertet" in hint
    assert "nicht gegen Spielergebnisse validiert" in hint and "keine Spielstärke" in hint
    missing = result["missing"]
    assert "± unbekannt" in missing["cells"][0]["text"] and "Streuung unbekannt" in missing["hint"]
    assert "Prüfer-Audit nicht verfügbar: Audit-Datei nicht gefunden" in missing["hint"]
    assert not missing["cells"][0]["doubt"]


def _detail_script(body: str) -> object:
    zahl = (STATIC / "zahl.js").read_text(encoding="utf-8")
    box = (STATIC / "kartenverstaendnis.js").read_text(encoding="utf-8")
    stub = """
const h = (tag, props, ...kids) => { const node = {tag, props: props || {}, kids: [],
  append(...more) { this.kids.push(...more.flat(Infinity).filter((k) => k !== null && k !== undefined && k !== false)); }};
  node.append(...kids); return node; };
const text = (n) => (n === null || n === undefined ? '' : typeof n === 'object' ? n.kids.map(text).join(' ') : String(n));
const rowsOf = (n, out = []) => { if (n && typeof n === 'object') { if (n.tag === 'tr' && n.props['data-kriterium']) out.push([n.props['data-kriterium'], text(n)]); n.kids.forEach((k) => rowsOf(k, out)); } return out; };
"""
    return _node_json(_ui_helpers_prelude() + zahl + "\n" + box + "\n" + stub + body)


def test_the_card_window_shows_seven_criteria_reason_claims_and_marks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T2 in the page: the real kartenverstaendnis.js renders the real server answer of a rated
    card (seven URTEIL rows with note and coverage, reason, claims, doubt), of an unrated card
    (seven times "unbekannt", never 0) and of another commander (nothing at all)."""
    store, data = _detail_store()
    rated = understanding_field.card_detail(
        store, "card:synth:alpha", CHULANE, dataset=data, audit=[_flag("Alpha", 65)]
    )
    unrated = understanding_field.card_detail(
        store, "card:synth:nobody", CHULANE, dataset=data, audit=[]
    )
    land = understanding_field.card_detail(
        store, "card:synth:grove", CHULANE, dataset=data, audit=[]
    )
    other = understanding_field.card_detail(store, "card:synth:alpha", TAM, dataset=data)
    script = f"""
const answers = {json.dumps({"rated": rated, "unrated": unrated, "land": land, "other": other})};
const out = {{}};
for (const [key, detail] of Object.entries(answers)) {{ const node = StudioKartenverstaendnis.box(h, detail);
  out[key] = node === null ? null : {{text: text(node), rows: rowsOf(node)}}; }}
console.log(JSON.stringify(out));
"""
    result = _detail_script(script)
    assert isinstance(result, dict)
    assert result["other"] is None  # TAM and every other commander: nothing shown
    rated_view = result["rated"]
    assert [row[0] for row in rated_view["rows"]] == list(card_understanding.CRITERIA)
    rows = dict(rated_view["rows"])
    assert rows["E"].startswith("E Effizienz") and "60" in rows["E"] and "cheap" in rows["E"]
    assert "Modellurteil" in rows["H"] and "65" in rows["H"] and "unbekannt" in rows["H"]
    assert "2 / 2 Zeilen des Datensatzes" in rows["K"]
    text = rated_view["text"]
    assert "It does one small thing." in text and "Draw a card." in text
    assert "vom Prüfer bezweifelt" in text and "Prüfer-Spanne 30 bis 45" in text
    assert "keine Spielstärke" in text and "Streuung von H: ± rund 5 bis 8 Punkte" in text
    assert "Kohorte: Chulane, Teller of Tales · Bracket 3" in text
    unrated_rows = dict(result["unrated"]["rows"])
    assert len(unrated_rows) == 7
    for name, row in unrated_rows.items():
        assert "unbekannt" in row and not re.search(r"\b0\b(?! /)", row.split(" ", 2)[-1]), name
    assert "alle sieben Kriterien sind unbekannt, nicht 0" in result["unrated"]["text"]
    assert "Länder-Skala" in result["land"]["text"]
    assert "Keine Regelclaims im Datensatz" in result["land"]["text"]


def test_compact_zahl_cells_keep_class_and_origin_and_refuse_invalid_figures() -> None:
    zahl = (STATIC / "zahl.js").read_text(encoding="utf-8")
    script = (
        _ui_helpers_prelude()
        + zahl
        + """
const h = (tag, props, ...kids) => ({tag, props: props || {}, kids: kids.flat(Infinity).filter((k) => k !== null && k !== undefined && k !== false)});
const text = (n) => (n === null || n === undefined ? '' : typeof n === 'object' ? n.kids.map(text).join('') : String(n));
const fig = {id: 'x', bezeichnung: 'H', wert: 70, einheit: 'Punkte', n: null, N: null, bezug: null, intervall: null, klasse: 'URTEIL',
  kohorte: 'K', quelle: 'Q', stand_datum: null, hinweise: ['note']};
const compact = StudioZahl.zelle(h, fig, 'URTEIL', {}, {kompakt: true, zusatz: [h('span', {class: 'extra'}, ' ±5\u20138')]});
const plain = StudioZahl.zelle(h, fig, 'URTEIL', {});
const bad = StudioZahl.zelle(h, {...fig, quelle: ''}, 'URTEIL', {}, {kompakt: true});
const wrong = StudioZahl.zelle(h, {...fig, klasse: 'GEZÄHLT', n: 1, N: 2, bezug: 'b'}, 'URTEIL', {}, {kompakt: true});
console.log(JSON.stringify({compact: text(compact), title: compact.kids[0].props.title, plain: text(plain), bad: text(bad), wrong: text(wrong),
  none: text(StudioZahl.zelle(h, null, 'URTEIL', {}, {kompakt: true}))}));
"""
    )
    result = _node_json(script)
    assert isinstance(result, dict)
    assert (
        result["compact"] == "70 ±5\u20138 Modellurteil"
        and result["title"] == "Quelle: Q · Kohorte: K · Hinweise: note"
    )
    assert (
        result["plain"] == "70 ModellurteilQuelle: Q · Kohorte: KHinweise: note"
    )  # default unchanged
    assert result["bad"] == "ungültige Zahl" and result["wrong"] == "Klasse passt nicht zur Spalte"
    assert result["none"] == "unbekannt"


def test_the_page_scripts_load_the_card_window_part_after_zahl_js() -> None:
    for page in ("tierliste.html", "index.html"):
        html = (STATIC / page).read_text(encoding="utf-8")
        assert html.index('<script src="zahl.js">') < html.index(
            '<script src="kartenverstaendnis.js">'
        )
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    tier = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    assert "StudioKartenverstaendnis.fill(understandingBox, h, api, card.card_id, COMMANDER)" in app
    assert "if (understandingShown()) StudioKartenverstaendnis.fill(" in tier
    css = (STATIC / "tierliste.css").read_text(encoding="utf-8")
    assert "#tier-table td{padding-top:2px;padding-bottom:2px;white-space:nowrap" in css
