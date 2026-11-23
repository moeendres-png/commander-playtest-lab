"""Owner decision option B (#1404, comment 7081544721; register E17): the spread of the model
judgement H is shown as a floor of ±8, and no mark of the tier list shows a difference of H below
that floor as a difference in rank.

Guards: the floor and the noise gate are one constant, bound to the single-rating spread the
second rater run measured (recomputed here from the raw files: 265 of 300 cards, 8.1); no shown
spread, band, cell, head line or card window names less than ±8; an H doubt of the audit closer to
the score than the gate gets no warning mark (a wrong reason is no H doubt and is not gated). The
raw scores are never touched: the gate acts on display and marks only.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

from commander_lab.studio import card_understanding, understanding_field
from tests.unit.test_studio_static_guards import _node_json
from tests.unit.test_studio_tierliste_wp6 import _detail_script, _tierliste_prelude

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "data" / "research" / "chulane_rubric_v2_20261118"
SECOND_RUN = RESEARCH / "second_run_20261122"
REPORT = ROOT / "docs" / "analysis-reports" / "rating_second_run_20261122.md"

# a shown spread: "±8", "± 10", "-15/+8" (the upper side of an asymmetric band), or textual
# approximations such as "etwa 5", "rund 5", "ca. 5"
_SHOWN_SPREAD = re.compile(
    r"±\s*(\d+(?:,\d+)?)|/\+(\d+(?:,\d+)?)|\b(?:etwa|rund|ca\.)\s*(\d+(?:,\d+)?)",
    re.IGNORECASE,
)


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _shown_spreads(text: str) -> list[float]:
    return [float((a or b or c).replace(",", ".")) for a, b, c in _SHOWN_SPREAD.findall(text)]


def _second_run_spread() -> tuple[int, int, float]:
    """n, N and the single-rating spread RMS / sqrt 2 of the second run against the full run,
    without the reviewer-flagged cards (the report's primary set)."""
    manifest = json.loads((SECOND_RUN / "rr_sample_manifest.json").read_text(encoding="utf-8"))
    old = {str(r["oracle_id"]): r for r in _jsonl(RESEARCH / "fullrun_ratings.jsonl")}
    new: dict[str, dict[str, object]] = {}
    for number in (1, 2, 3):
        new.update(
            {str(r["oracle_id"]): r for r in _jsonl(SECOND_RUN / f"rr_output_{number}.jsonl")}
        )
    cards = manifest["cards"]
    diffs = [
        float(new[c["oracle_id"]]["scores"]["H"]) - float(old[c["oracle_id"]]["scores"]["H"])  # type: ignore[index]
        for c in cards
        if c["stratum"] != "flagged"
    ]
    rms = math.sqrt(sum(d * d for d in diffs) / len(diffs))
    return len(diffs), len(cards), rms / math.sqrt(2)


def test_floor_and_noise_gate_are_bound_to_the_measured_spread() -> None:
    n, total, spread = _second_run_spread()
    assert (n, total) == (265, 300)
    assert round(spread, 1) == 8.1
    # one constant: the gate can never be finer than the shown spread, and the floor is the
    # measured spread rounded to whole points (never the older, smaller "5 to 8")
    assert understanding_field.NOISE_GATE == understanding_field.SPREAD_FLOOR == round(spread)
    assert understanding_field.SPREAD["mindestens"] == understanding_field.SPREAD_FLOOR
    assert understanding_field.NOISE_GATE_FIELD["punkte"] == understanding_field.NOISE_GATE
    source = next(
        q
        for q in understanding_field.SPREAD["quellen"]  # type: ignore[attr-defined]
        if str(q["name"]).startswith("Zweiter Rater-Lauf")
    )
    assert (source["n"], source["N"]) == (n, total) and "Familie ungeprüft, A3" in source["name"]
    report = REPORT.read_text(encoding="utf-8")
    assert "Einzelwert-Streuung RMS/√2 = **8,1**" in report and "n = 265" in report
    assert "8,1 [7,3; 8,9]" in report and "Familie ungeprüft (A3)" in report


def test_no_shown_spread_of_the_field_is_below_the_floor() -> None:
    spread = understanding_field.SPREAD
    floor = understanding_field.SPREAD_FLOOR
    shown = [
        str(spread["kurz"]),
        str(spread["text"]),
        str(understanding_field.NOISE_GATE_FIELD["text"]),
    ]
    for band in spread["baender"]:  # type: ignore[attr-defined]
        shown += [band["kurz"], band["text"]]
    found = [value for text in shown for value in _shown_spreads(text)]
    assert found and min(found) >= floor, shown
    assert _shown_spreads("±5, \u221215/+5, etwa 5, rund 6 und ca. 7,5") == [
        5.0,
        5.0,
        5.0,
        6.0,
        7.5,
    ]  # the pattern sees the old marks and textual approximations


def test_the_rendered_tier_list_never_names_less_than_the_floor() -> None:
    """Cells for every H value in steps of 5, their tooltips and the head line."""
    script = (
        _tierliste_prelude()
        + """
const values = Array.from({length: 21}, (_, i) => i * 5);
const cards = values.map((v) => item('C' + v, 'S', 50));
const field = (extra) => ({verfuegbar: true, grund: null, name: 'Kartenverständnis (Modellurteil)', kriterium: 'H', n_bewertet: 21, n_gesamt: 21,
  herkunft: {version: 'v2.1'}, zahlen: values.map((v) => figure('C' + v, v)), streuung: SPREAD, rauschgate: GATE, abdeckung: {},
  regelclaim_befunde: {karten: {}}, pruefer_zweifel: {verfuegbar: true, n_markiert: 2, n_zugeordnet: 2, n_im_pool: 2, rauschgate: 8, n_unter_rauschgate: 1,
    karten: {C50: {art: 'H zu niedrig', spanne: [55, 60], kurz: 'Prüfer-Modell: Spanne innerhalb der Streuung (unter 8 Punkten) (zu H aus Lauf 1)', text: 't', grund: 'g', unter_rauschgate: true},
      C70: {art: 'H zu hoch', spanne: [30, 45], kurz: 'Prüfer-Modell bezweifelt H: zu hoch', text: 't', grund: 'g', unter_rauschgate: false}}},
  laender_skala: null, ...extra});
const allTitles = (n, out = []) => { if (n && typeof n === 'object') { if (n.props && n.props.title) out.push(n.props.title); n.kids.forEach((k) => allTitles(k, out)); } return out; };
const warnOf = (n) => { let found = null; const walk = (x) => { if (x && typeof x === 'object') { const cls = (x.props.class || '').split(' ');
  if (cls.includes('pruefer-zweifel')) found = cls.includes('warn'); x.kids.forEach(walk); } }; walk(n); return found; };
setup(cards, field({}));
const cells = cards.map((c) => understandingCell(c));
const out = {cells: cells.map(text), titles: cells.flatMap((c) => allTitles(c)), hint: understandingHint().map(text).join(' '),
  hintTitles: understandingHint().flatMap((n) => allTitles(n)), warn50: warnOf(cells[10]), warn70: warnOf(cells[14])};
setup(cards, field({rauschgate: {...GATE, punkte: 12, text: 'Unterschiede von H unter 12 Punkten sind kein Rangunterschied'}}));
out.otherGate = understandingHint().map(text).join(' ');
setup(cards, field({rauschgate: undefined})); out.noGate = understandingHint().map(text).join(' ');
console.log(JSON.stringify(out));
"""
    )
    result = _node_json(script)
    assert isinstance(result, dict)
    floor = understanding_field.SPREAD_FLOOR
    # Strip the raw historical source citations ("Drift-Test: ...") from tooltips before checking
    # that no shown spread or band names less than the floor (matching the card window test below).
    shown = [
        *result["cells"],
        *(t.split(" · Drift-Test:", 1)[0] for t in result["titles"]),
        result["hint"],
        *(t.split(" · Drift-Test:", 1)[0] for t in result["hintTitles"]),
    ]
    found = [value for text in shown for value in _shown_spreads(text)]
    assert len(found) >= 21 and min(found) >= floor
    assert all("±8" in cell or "±10" in cell or "/+8" in cell for cell in result["cells"])
    assert "mindestens ±8 Punkte" in result["hint"] and "n/N = 265/300" in result["hint"]
    # the doubt inside the spread has no warning mark; the one outside keeps it
    assert result["warn50"] is False and result["warn70"] is True
    # the gate text comes from the answer, not from the page script
    assert "unter 12 Punkten sind kein Rangunterschied" in result["otherGate"]
    assert "kein Rangunterschied" not in result["noGate"]


def test_the_card_window_never_names_less_than_the_floor() -> None:
    detail = {
        "verfuegbar": True,
        "anzeigen": True,
        "name": understanding_field.NAME,
        "card_id": "c",
        "karte": "Synth",
        "kohorte": "Chulane · Bracket 3",
        "hinweis": understanding_field.NOT_STRENGTH,
        "streuung": understanding_field.SPREAD,
        "rauschgate": understanding_field.NOISE_GATE_FIELD,
        "bewertet": False,
        "herkunft": {},
        "kriterien": [],
        "regelclaims": [],
        "pruefer_zweifel": {
            "art": "H zu niedrig",
            "spanne": [55, 60],
            "kurz": "Prüfer-Modell: Spanne innerhalb der Streuung (unter 8 Punkten) (zu H aus Lauf 1)",
            "text": "t",
            "grund": "g",
            "unter_rauschgate": True,
        },
        "abdeckung": {},
    }
    script = f"""
const node = StudioKartenverstaendnis.box(h, {json.dumps(detail, ensure_ascii=False)});
console.log(JSON.stringify({{text: text(node), warn: hasCls(node, 'warn'), doubt: hasCls(node, 'pruefer-zweifel')}}));
"""
    result = _detail_script(script)
    assert isinstance(result, dict)
    text = result["text"]
    band_part = text.split("H 0 bis 10", 1)[1].split("Drift-Test", 1)[0]
    found = _shown_spreads(band_part) + _shown_spreads(text.split("Streuung von H", 1)[1][:200])
    assert found and min(found) >= understanding_field.SPREAD_FLOOR
    assert "Unterschiede von H unter 8 Punkten sind kein Rangunterschied" in text
    assert result["doubt"] and not result["warn"]


def _flag(
    kind: str, score: float, low: float | None, high: float | None
) -> card_understanding.AuditFlag:
    return {
        "card": "Synth",
        "rater_H": score,
        "proposed_H_low": low,
        "proposed_H_high": high,
        "kind": kind,
        "reason": "r",
        "sample": "s",
    }


def test_an_h_doubt_inside_the_noise_gate_is_no_warning_mark() -> None:
    near = _flag("H zu niedrig", 50, 55, 60)  # 5 points below the span
    edge = _flag("H zu niedrig", 50, 58, 65)  # exactly the gate: a difference at the spread
    high = _flag("H zu hoch", 70, 45, 65)  # 5 points above the span
    reason = _flag("Begründung faktisch falsch", 65, 60, 65)  # no doubt about H
    assert understanding_field.doubt_distance(near) == 5 and understanding_field.doubt_below_gate(
        near
    )
    assert understanding_field.doubt_distance(
        edge
    ) == 8 and not understanding_field.doubt_below_gate(edge)
    assert understanding_field.doubt_below_gate(high)
    assert understanding_field.doubt_distance(
        reason
    ) is None and not understanding_field.doubt_below_gate(reason)
    assert understanding_field.doubt_distance(_flag("H zu hoch", 70, None, None)) is None
    entry = understanding_field._doubt_entry(near)
    assert entry["unter_rauschgate"] is True and entry["kurz"] == (
        "Prüfer-Modell: Spanne innerhalb der Streuung (unter 8 Punkten) (zu H aus Lauf 1)"
    )
    assert "bezweifelt" not in str(entry["kurz"])
    assert (
        understanding_field._doubt_entry(edge)["kurz"]
        == "Prüfer-Modell bezweifelt H: zu niedrig (zu H aus Lauf 1)"
    )
    assert (
        understanding_field._doubt_entry(reason)["kurz"]
        == "Prüfer-Modell: Begründung faktisch falsch"
    )
    # the raw scores are not touched: the entry still names the score the reviewer saw
    assert entry["h_gesehen"] == 50 and entry["spanne"] == [55, 60]


def test_no_real_audit_doubt_lies_inside_the_noise_gate_today() -> None:
    """The gate changes no visible mark of the real data set today (0 of 33 H doubts)."""
    flags = card_understanding.load_audit()
    h_doubts = [f for f in flags if f["kind"].startswith("H ")]
    assert (len(flags), len(h_doubts)) == (35, 33)
    assert [f["card"] for f in h_doubts if understanding_field.doubt_below_gate(f)] == []
