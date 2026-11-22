"""Owner decision of 2026-11-22 (#1404, comment 7085569723; register E19): the tier list and the
card window show the mean of the two ratings of H (H_pooled) instead of H_F1.

Guards: the pooled values the Studio reads are the committed evaluation output, bound to its
SHA-256 and recomputed here from the raw ratings of both runs (F1: ``fullrun_ratings.jsonl``; R2:
``rr_output_*.jsonl`` of wave 1 and ``rater/rr2_output_*.jsonl`` of wave 2, mapped by
``quelle_R2``). The display always names the number of ratings and both raw values with their
run; a card with |ΔH| >= 15 carries the mark with both values; without a usable pooled value the
card shows H_F1 marked "nur Lauf 1" (never 0, never a partial mean); the correction K1 is never
read; the spread floor ±8 (E17) is unchanged and the pooled standard error is named only with its
condition (independent errors, not shown, A3). The audit doubts stay placed on H_F1 (the auditor
saw that value). Store data is synthetic or uses invented card ids for the real oracle ids.
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from commander_lab.studio import card_understanding, number_contract, understanding_field
from commander_lab.studio.web import create_app
from tests.unit.studio_synth import add_card, add_signal, make_store
from tests.unit.test_studio_static_guards import STATIC, _node_json
from tests.unit.test_studio_tierliste_spread_floor import _shown_spreads
from tests.unit.test_studio_tierliste_wp6 import (
    CHULANE,
    FIELD,
    _detail_script,
    _real_store_and_answer,
    _row,
    _tierliste_prelude,
)

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "data" / "research" / "chulane_rubric_v2_20261118"
FULL = RESEARCH / "second_run_full_20261122"
POOLED = FULL / "pooled.jsonl"
REPORT = ROOT / "docs" / "analysis-reports" / "rating_full_second_run_20261122.md"
REGISTER = ROOT / "docs" / "OWNER_DECISIONS_STUDIO_20261118.md"
CMD = "Test Commander"
NAMES = [f"Card {index:02d}" for index in range(4)]


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _raw_r2() -> dict[tuple[str, str, str], float]:
    """H of the second rating by (wave, file number, oracle_id), from the committed raw output."""
    found: dict[tuple[str, str, str], float] = {}
    for number in (1, 2, 3):
        for row in _jsonl(RESEARCH / "second_run_20261122" / f"rr_output_{number}.jsonl"):
            found[("welle1", str(number), str(row["oracle_id"]))] = float(row["scores"]["H"])  # type: ignore[index]
    for number in range(1, 9):
        for row in _jsonl(FULL / "rater" / f"rr2_output_{number}.jsonl"):
            found[("welle2", str(number), str(row["oracle_id"]))] = float(row["scores"]["H"])  # type: ignore[index]
    return found


# ---------- the data the Studio reads ----------


def test_the_pooled_file_is_the_sealed_output_and_matches_the_raw_ratings() -> None:
    digest = hashlib.sha256(POOLED.read_bytes()).hexdigest()
    sums = (FULL / "results_sha256.txt").read_text(encoding="utf-8")
    assert f"{digest}  pooled.jsonl" in sums
    assert digest.startswith("3e6d82d0")  # posted in #1404, comment 7085556215
    rows = _jsonl(POOLED)
    full = {str(r["oracle_id"]): r for r in _jsonl(RESEARCH / "fullrun_ratings.jsonl")}
    dataset = card_understanding.load()
    raw = _raw_r2()
    assert len(rows) == len(full) == len(dataset) == 922
    for row in rows:
        oracle_id = str(row["oracle_id"])
        h_f1 = float(full[oracle_id]["scores"]["H"])  # type: ignore[index]
        assert row["H_F1"] == h_f1 == dataset[oracle_id]["scores"]["H"]
        wave, number = str(row["quelle_R2"]).split(":")
        assert row["H_R2"] == raw[(wave, number, oracle_id)]
        assert row["H_pooled"] == (h_f1 + float(row["H_R2"])) / 2  # type: ignore[arg-type]
    # the retest batch 8 of wave 2 (50 wave-1 cards) never enters the mean (plan §4)
    retest = {key[2] for key in raw if key[:2] == ("welle2", "8")}
    assert len(retest) == 50 and all(str(r["quelle_R2"]) != "welle2:8" for r in rows)
    assert all(str(r["quelle_R2"]).startswith("welle1:") for r in rows if r["oracle_id"] in retest)
    # "unrounded" holds because the values lie on the grid of the data: raw scores in steps of 5,
    # the mean in steps of 2.5 (the display keeps one decimal, so nothing is rounded away)
    assert all(float(r["H_F1"]) % 5 == 0 and float(r["H_R2"]) % 5 == 0 for r in rows)  # type: ignore[arg-type]
    assert all(float(r["H_pooled"]) % 2.5 == 0 for r in rows)  # type: ignore[arg-type]
    loaded = card_understanding.load_pooled()
    assert len(loaded) == 922 and all(r["n_bewertungen"] == 2 for r in loaded.values())
    gaps = [abs(r["h_r2"] - r["h_f1"]) for r in loaded.values() if r["h_r2"] is not None]
    assert sum(1 for g in gaps if g >= 15) == 266 and sum(1 for g in gaps if g >= 30) == 22
    assert sum(1 for g in gaps if g == 15) > 0  # the boundary is in the real data (>= 15, not > 15)


def test_the_new_spread_source_and_the_standard_error_are_recomputed() -> None:
    rows = card_understanding.load_pooled().values()
    diffs = [r["h_r2"] - r["h_f1"] for r in rows if r["h_r2"] is not None]
    sd = statistics.stdev(diffs)
    rms = math.sqrt(sum(d * d for d in diffs) / len(diffs))
    assert (round(sd / 2, 2), round(sd / math.sqrt(2), 2)) == (5.50, 7.77)
    assert round(rms / math.sqrt(2), 2) == 8.46 and round(statistics.mean(diffs), 2) == -4.73
    source = next(
        q
        for q in understanding_field.SPREAD["quellen"]  # type: ignore[attr-defined]
        if str(q["name"]).startswith("Zweite Bewertung aller Karten")
    )
    assert (source["n"], source["N"], source["gemessen"]) == (922, 922, True)
    kennzahl = str(source["kennzahl"])
    assert "7,77 [7,38; 8,16]" in kennzahl and "8,46" in kennzahl and "5,50" in kennzahl
    assert "nur bei unabhängigen Fehlern (nicht belegt, A3)" in kennzahl
    assert "Familie ungeprüft, A3" in str(source["name"])
    # the floor stays the floor: the smaller pooled error does not lower it (E17)
    assert understanding_field.SPREAD_FLOOR == understanding_field.NOISE_GATE == 8
    assert min(_shown_spreads(kennzahl)) >= 8 and "±5" not in kennzahl
    note = understanding_field.STANDARD_ERROR_NOTE
    assert "5,50" in note and "nicht belegt (A3)" in note and "mindestens ±8" in note
    report = REPORT.read_text(encoding="utf-8")
    assert "SD(d)/2 = **5,50**" in report and "7,77 [7,38; 8,16]" in report


# ---------- the field of the strength answer ----------


def test_the_real_field_shows_the_pooled_h_with_both_runs_and_the_marks() -> None:
    store, answer = _real_store_and_answer()
    field = understanding_field.with_understanding(store, answer)[FIELD]
    pooled = card_understanding.load_pooled()
    oracle = dict(store.connection.execute("SELECT card_id, oracle_id FROM card").fetchall())
    ratings = field["bewertungen"]
    assert ratings["verfuegbar"] is True and ratings["grund"] is None
    assert (ratings["n_mittel"], ratings["N"], ratings["n_nur_lauf_1"]) == (922, 922, 0)
    assert ratings["n_abweichung"] == 266 and ratings["abweichung_datensatz"]["n"] == 266
    assert [(r["lauf"], r["n"], r["N"]) for r in ratings["laeufe"]] == [
        ("Lauf 1 (F1)", 922, 922),
        ("Lauf 2 (R2)", 922, 922),
    ]
    assert "K1 nicht angewendet" in ratings["text"] and "A3" in ratings["text"]
    marked = 0
    for figure in field["zahlen"]:
        assert number_contract.check(figure) == [] and figure["intervall"] is None
        card_id = figure["id"].removeprefix(understanding_field.ID_PREFIX)
        row = pooled[oracle[card_id]]
        assert figure["wert"] == row["h_pooled"]  # unrounded mean, never K1
        rating = ratings["karten"][card_id]
        assert rating["n_bewertungen"] == 2 and rating["kurz"] == "Mittel aus 2 Bewertungen"
        assert (rating["h_f1"], rating["h_r2"]) == (row["h_f1"], row["h_r2"])
        assert any(note.startswith("Mittel aus 2 Bewertungen: H ") for note in figure["hinweise"])
        far = abs(row["h_r2"] - row["h_f1"]) >= 15  # type: ignore[operator]
        assert rating["abweichung"] is far and ("abweichung_ge15" in row["marken"]) is far
        if far:
            marked += 1
            assert rating["marke"] in figure["hinweise"]
            assert "Lauf 1 (F1)" in rating["marke"] and "Lauf 2 (R2)" in rating["marke"]
    assert marked == 266
    # one origin per kind of value: the head line lists it once, not per card
    assert len({figure["quelle"] for figure in field["zahlen"]}) <= 2
    assert all("Stufe unbekannt" in figure["quelle"] for figure in field["zahlen"])
    # the audit was made on H_F1 and stays placed there; the land counts stay as they were
    doubt = field["pruefer_zweifel"]
    assert (doubt["n_markiert"], doubt["n_zugeordnet"], doubt["n_unter_rauschgate"]) == (35, 35, 0)
    assert all("aus Lauf 1 (F1)" in entry["text"] for entry in doubt["karten"].values())
    assert (field["laender_skala"]["n_laender"], field["laender_skala"]["n_t_null"]) == (65, 58)


def test_the_audit_doubts_stay_on_run_1_and_their_overlap_with_the_mean_is_counted() -> None:
    """The auditor judged H_F1, so the doubts stay placed on H_F1 (not silently re-gated on the
    mean). For 18 of the 33 H doubts the shown mean already lies inside the reviewer's span; the
    register (E19) and the pull request list that open point."""
    rows, pooled = card_understanding.load(), card_understanding.load_pooled()
    match = card_understanding.match_audit(rows, card_understanding.load_audit())
    inside = outside = 0
    for oracle_id, flag in match["flags"].items():
        low, high = flag["proposed_H_low"], flag["proposed_H_high"]
        if not flag["kind"].startswith("H ") or low is None or high is None:
            continue
        assert flag["rater_H"] == pooled[oracle_id]["h_f1"]
        if low <= pooled[oracle_id]["h_pooled"] <= high:
            inside += 1
        else:
            outside += 1
    assert (inside, outside) == (18, 15)
    store, answer = _real_store_and_answer()
    doubts = understanding_field.with_understanding(store, answer)[FIELD]["pruefer_zweifel"]
    labels = [entry["kurz"] for entry in doubts["karten"].values()]
    h_labels = [label for label in labels if "Begründung" not in label]
    assert len(h_labels) == 33 and all(label.endswith("(zu H aus Lauf 1)") for label in h_labels)
    assert "Bei 18 von 33 H-Zweifeln" in REGISTER.read_text(encoding="utf-8")


def test_k1_is_never_read() -> None:
    raw = {str(r["oracle_id"]): r for r in _jsonl(POOLED)}
    store, answer = _real_store_and_answer()
    field = understanding_field.with_understanding(store, answer)[FIELD]
    oracle = dict(store.connection.execute("SELECT card_id, oracle_id FROM card").fetchall())
    differs = 0
    for figure in field["zahlen"]:
        line = raw[oracle[figure["id"].removeprefix(understanding_field.ID_PREFIX)]]
        if line["H_pooled_K1_vorschlag"] != line["H_pooled"]:
            differs += 1
            assert figure["wert"] != line["H_pooled_K1_vorschlag"]
    assert differs > 800  # K1 would move every spell; none of it reaches the display
    assert "K1_vorschlag" not in (
        Path(understanding_field.__file__).read_text(encoding="utf-8")
        + (STATIC / "tierliste.js").read_text(encoding="utf-8")
        + (STATIC / "kartenverstaendnis.js").read_text(encoding="utf-8")
    )


def test_a_missing_or_broken_pooled_file_falls_back_to_run_1_never_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    store, answer = _real_store_and_answer()
    dataset = card_understanding.load()
    oracle = dict(store.connection.execute("SELECT card_id, oracle_id FROM card").fetchall())
    broken = tmp_path / "broken.jsonl"
    lines = POOLED.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["H_pooled"] = first["H_pooled"] + 2.5  # one wrong mean breaks the whole file
    broken.write_text("\n".join([json.dumps(first), *lines[1:]]) + "\n", encoding="utf-8")
    for path, words in ((tmp_path / "missing.jsonl", "nicht gefunden"), (broken, "nicht lesbar")):
        monkeypatch.setattr(card_understanding, "POOLED_PATH", path)
        field = understanding_field.with_understanding(store, answer)[FIELD]
        ratings = field["bewertungen"]
        assert ratings["verfuegbar"] is False and words in ratings["grund"]
        assert ratings["laeufe"][1]["n"] is None  # the second run is unknown, not 0
        assert ratings["abweichung_datensatz"]["n"] is None and ratings["n_nur_lauf_1"] == 922
        for figure in field["zahlen"]:
            card_id = figure["id"].removeprefix(understanding_field.ID_PREFIX)
            assert figure["wert"] == dataset[oracle[card_id]]["scores"]["H"]
            rating = ratings["karten"][card_id]
            assert rating["kurz"] == "nur Lauf 1" and rating["n_bewertungen"] == 1
            assert rating["h_r2"] is None and rating["abweichung"] is False
            assert figure["quelle"].endswith("Lauf 1 (F1)")


def test_single_ratings_mismatches_and_unrated_cards() -> None:
    """A line with one rating shows "1 Bewertung, nur erste"; a pooled H_F1 that is not the data
    set's H falls back for that card only; a card the data set lacks has no figure at all."""
    store = make_store()
    add_card(store, CMD, type_line="Legendary Creature — Test")
    for index, name in enumerate(NAMES):
        add_card(store, name)
        add_signal(store, CMD, "edhrec_commander_inclusion", name, 80 - 10 * index, 100)
        store.connection.execute(
            "UPDATE card SET oracle_id = ? WHERE oracle_name = ?", (f"o-{name}", name)
        )
    data = card_understanding.parse_lines(
        [json.dumps(_row(f"o-{name}", name, H=40)) for name in NAMES[:3]]
    )
    pooled = {
        "o-Card 00": card_understanding.parse_pooled_row(_pooled_line("o-Card 00", 40, 55)),
        "o-Card 01": card_understanding.parse_pooled_row(_pooled_line("o-Card 01", 40, None)),
        "o-Card 02": card_understanding.parse_pooled_row(_pooled_line("o-Card 02", 35, 45)),
    }
    cards = [
        {"card_id": card_id, "is_land": False}
        for (card_id,) in store.connection.execute("SELECT card_id FROM card")
    ]
    answer = {"commander": CHULANE, "settings": {"bracket": "upgraded"}, "cards": cards}
    field = understanding_field.with_understanding(
        store, answer, dataset=data, audit=[], pooled=pooled
    )[FIELD]
    by_name = {
        name: card_id
        for card_id, name in store.connection.execute("SELECT card_id, oracle_name FROM card")
    }
    ratings = field["bewertungen"]["karten"]
    values = {
        f["id"].removeprefix(understanding_field.ID_PREFIX): f["wert"] for f in field["zahlen"]
    }
    both = ratings[by_name["Card 00"]]
    assert values[by_name["Card 00"]] == 47.5 and both["kurz"] == "Mittel aus 2 Bewertungen"
    assert both["abweichung"] is True and both["marke"] == (
        "Bewertungen weichen stark ab (Δ 15: Lauf 1 (F1) 40, Lauf 2 (R2) 55)"
    )
    single = ratings[by_name["Card 01"]]
    assert values[by_name["Card 01"]] == 40 and single["kurz"] == "1 Bewertung, nur erste"
    assert single["grund"] == "fehlt" and single["n_bewertungen"] == 1
    stale = ratings[by_name["Card 02"]]
    assert values[by_name["Card 02"]] == 40 and stale["kurz"] == "nur Lauf 1"
    assert "passt nicht zum Datensatz (H_F1 35 statt 40)" in stale["grund"]
    assert by_name["Card 03"] not in values and by_name["Card 03"] not in ratings
    counts = field["bewertungen"]
    assert (counts["n_mittel"], counts["n_nur_erstbewertung"], counts["n_nur_lauf_1"]) == (1, 1, 1)
    assert counts["N"] == 3 and counts["n_abweichung"] == 1


def _pooled_line(oracle_id: str, h_f1: float, h_r2: float | None) -> dict[str, object]:
    marks: list[str] = []
    if h_r2 is None:
        marks.append("nur_erstbewertung")
    else:
        marks += ["abweichung_ge15"] if abs(h_r2 - h_f1) >= 15 else []
        marks += ["abweichung_ge30"] if abs(h_r2 - h_f1) >= 30 else []
    return {
        "oracle_id": oracle_id,
        "card": oracle_id.removeprefix("o-"),
        "H_F1": h_f1,
        "H_R2": h_r2,
        "H_pooled": h_f1 if h_r2 is None else (h_f1 + h_r2) / 2,
        "n_bewertungen": 1 if h_r2 is None else 2,
        "marken": marks,
        "grund_nur_erstbewertung": "fehlt" if h_r2 is None else None,
        "quelle_R2": None if h_r2 is None else "welle2:1",
        "H_pooled_K1_vorschlag": 99.0,
    }


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"H_pooled": 50.0}, "not the mean"),
        ({"marken": []}, "abweichung_ge15"),
        ({"marken": ["abweichung_ge15", "abweichung_ge30"]}, "abweichung_ge30"),
        ({"n_bewertungen": 3}, "1 or 2"),
        ({"H_R2": 120.0}, "0..100"),
        ({"quelle_R2": ""}, "quelle_R2"),
        ({"extra": 1}, "unknown pooled fields"),
    ],
)
def test_a_pooled_line_that_disagrees_with_its_raw_values_is_refused(
    change: dict[str, object], message: str
) -> None:
    good = _pooled_line("o-X", 40, 55)  # gap exactly 15: the mark is required
    card_understanding.parse_pooled_row(good)
    with pytest.raises(card_understanding.UnderstandingDataError, match=message):
        card_understanding.parse_pooled_row(good | change)
    single = _pooled_line("o-Y", 40, None)
    with pytest.raises(card_understanding.UnderstandingDataError, match="no H_R2"):
        card_understanding.parse_pooled_row(single | {"H_R2": 50.0})
    with pytest.raises(card_understanding.UnderstandingDataError, match="H_pooled = H_F1"):
        card_understanding.parse_pooled_row(single | {"H_pooled": 45.0})


def test_a_removed_pooled_file_changes_the_remembered_strength_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = tmp_path / "studio"
    store = make_store(folder)
    add_card(store, CMD, type_line="Legendary Creature — Test")
    for index, name in enumerate(NAMES):
        add_card(store, name)
        add_signal(store, CMD, "edhrec_commander_inclusion", name, 80 - 10 * index, 100)
        store.connection.execute(
            "UPDATE card SET oracle_id = ? WHERE oracle_name = ?", (f"o-{name}", name)
        )
    store.connection.commit()
    store.close()
    data = tmp_path / "cu.jsonl"
    data.write_text(
        "\n".join(json.dumps(_row(f"o-{name}", name, H=40)) for name in NAMES) + "\n",
        encoding="utf-8",
    )
    pooled = tmp_path / "pooled.jsonl"
    pooled.write_text(
        "\n".join(json.dumps(_pooled_line(f"o-{name}", 40, 50)) for name in NAMES) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(card_understanding, "DATASET_PATH", data)
    monkeypatch.setattr(card_understanding, "AUDIT_PATH", tmp_path / "no-audit.jsonl")
    monkeypatch.setattr(card_understanding, "POOLED_PATH", pooled)
    monkeypatch.setattr(card_understanding, "DATASET_COMMANDER", CMD)
    head = {"X-Studio": "1"}
    with TestClient(create_app(folder)) as client:
        first = client.post("/api/strength", json={"commander": CMD}, headers=head).json()
        pooled.unlink()
        second = client.post("/api/strength", json={"commander": CMD}, headers=head).json()
    assert {f["wert"] for f in first[FIELD]["zahlen"]} == {45.0}
    assert first[FIELD]["bewertungen"]["verfuegbar"] is True
    assert {f["wert"] for f in second[FIELD]["zahlen"]} == {40.0}
    assert second[FIELD]["bewertungen"]["n_nur_lauf_1"] == len(NAMES)


# ---------- the card window ----------


def _real_detail(name: str) -> dict[str, object]:
    store, _answer = _real_store_and_answer()
    oracle_id = next(o for o, r in card_understanding.load().items() if r["card"] == name)
    card_id = store.connection.execute(
        "SELECT card_id FROM card WHERE oracle_id = ?", (oracle_id,)
    ).fetchone()[0]
    return understanding_field.card_detail(store, card_id, CHULANE)


def test_the_card_detail_names_both_runs_and_keeps_the_other_criteria_on_run_1() -> None:
    detail = _real_detail("Veil of Summer")
    row = next(r for r in card_understanding.load().values() if r["card"] == "Veil of Summer")
    criteria = {c["kriterium"]: c["zahl"] for c in detail["kriterien"]}
    assert criteria["H"]["wert"] == 40.0  # (20 + 60) / 2
    for name in "EFTRKD":
        assert criteria[name]["wert"] == row["scores"][name]  # only H is averaged
    ratings = detail["bewertungen"]
    card = ratings["karte"]
    assert (card["h_f1"], card["h_r2"], card["n_bewertungen"]) == (20.0, 60.0, 2)
    assert card["abweichung"] is True and card["quelle_r2"] == "welle2:2"
    assert [(r["n"], r["N"]) for r in ratings["laeufe"]] == [(922, 922), (922, 922)]
    assert "gemittelt wird nur H" in ratings["andere_kriterien"]
    assert detail["streuung"] == understanding_field.SPREAD


def test_the_card_detail_falls_back_to_run_1_without_the_pooled_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(card_understanding, "POOLED_PATH", tmp_path / "missing.jsonl")
    detail = _real_detail("Veil of Summer")
    criteria = {c["kriterium"]: c["zahl"] for c in detail["kriterien"]}
    assert criteria["H"]["wert"] == 20.0  # H_F1, never 0 and never a stale mean
    ratings = detail["bewertungen"]
    assert ratings["verfuegbar"] is False and "nicht gefunden" in ratings["grund"]
    assert ratings["text"].startswith("nur Lauf 1: H aus Lauf 1 (F1)")
    assert "Mittel der zwei" not in ratings["text"]
    assert ratings["karte"]["kurz"] == "nur Lauf 1" and ratings["laeufe"][1]["n"] is None


def test_the_card_window_shows_the_count_both_raw_values_and_the_mark() -> None:
    veil = _real_detail("Veil of Summer")
    calm = _real_detail("Solemn Simulacrum")  # 70 and 70: no mark
    fallback = json.loads(json.dumps(veil))
    fallback["bewertungen"] |= {"verfuegbar": False, "grund": "Datei fehlt"}
    fallback["bewertungen"]["karte"] |= {
        "art": "nur_lauf_1",
        "kurz": "nur Lauf 1",
        "wert": 20.0,
        "h_r2": None,
        "abweichung": False,
        "marke": None,
        "grund": "Datei fehlt",
        "quelle_r2": None,
    }
    fallback["bewertungen"]["laeufe"][1]["n"] = None
    answers = {"veil": veil, "calm": calm, "fallback": fallback}
    script = f"""
const answers = {json.dumps(answers)};
const out = {{}};
for (const [key, detail] of Object.entries(answers)) {{ const node = StudioKartenverstaendnis.box(h, detail);
  out[key] = {{text: text(node), rows: rowsOf(node), mark: hasCls(node, 'bewertungen-abweichung')}}; }}
console.log(JSON.stringify(out));
"""
    result = _detail_script(script)
    assert isinstance(result, dict)
    veil_text = result["veil"]["text"]
    assert "H angezeigt: 40" in veil_text and "Mittel aus 2 Bewertungen" in veil_text
    assert "Lauf 1 (F1): H 20 · n/N 922 / 922" in veil_text
    assert "Lauf 2 (R2): H 60 · n/N 922 / 922 · Quelle welle2:2" in veil_text
    assert result["veil"]["mark"] and "Bewertungen weichen stark ab (Δ 40)" in veil_text
    assert "gemittelt wird nur H" in veil_text and "nicht belegt (A3)" in veil_text
    assert "40" in dict(result["veil"]["rows"])["H"]
    assert not result["calm"]["mark"] and "Lauf 2 (R2): H 70" in result["calm"]["text"]
    fb = result["fallback"]["text"]
    assert "H angezeigt: 20" in fb and "nur Lauf 1" in fb
    assert "Lauf 2 (R2): H unbekannt (nicht gelesen) · n/N unbekannt / 922" in fb
    assert "Mittel der zwei Bewertungen nicht verfügbar: Datei fehlt" in fb
    assert not result["fallback"]["mark"]
    for view in result.values():
        assert min(_shown_spreads(view["text"])) >= 8


# ---------- the tier list cell and head line ----------


def test_the_cell_names_the_count_the_mark_and_unrounded_values() -> None:
    flag: card_understanding.AuditFlag = {
        "card": "A",
        "rater_H": 40.0,
        "proposed_H_low": 55.0,
        "proposed_H_high": 70.0,
        "kind": "H zu niedrig",
        "reason": "unterschätzt",
        "sample": "boundary70",
    }
    doubt = json.dumps(understanding_field._doubt_entry(flag), ensure_ascii=False)
    script = (
        _tierliste_prelude()
        + f"const DOUBT = {doubt};\n"
        + """
const cards = [item('A', 'S', 70), item('B', 'S', 60), item('C', 'D', 1), item('D', 'D', 1), item('E', 'D', 1)];
const rating = (art, wert, f1, r2, far) => ({art, wert, h_f1: f1, h_r2: r2, abweichung: far, n_bewertungen: art === 'mittel' ? 2 : 1,
  kurz: art, text: `text ${art}`, marke: far ? `Bewertungen weichen stark ab (Δ ${Math.abs(r2 - f1)}: Lauf 1 (F1) ${f1}, Lauf 2 (R2) ${r2})` : null});
const field = {verfuegbar: true, grund: null, name: 'Kartenverständnis (Modellurteil)', kriterium: 'H', n_bewertet: 4, n_gesamt: 5,
  herkunft: {}, zahlen: [figure('A', 42.5), figure('B', 47.5), figure('C', 40), figure('D', 30)],
  streuung: SPREAD, rauschgate: GATE, abdeckung: {}, regelclaim_befunde: {karten: {}}, pruefer_zweifel: {verfuegbar: true, karten: {A: DOUBT}}, laender_skala: null,
  bewertungen: {verfuegbar: true, grund: null, quelle: 'pooled.jsonl', text: 'H = Mittel der zwei Bewertungen, K1 nicht angewendet',
    laeufe: [{lauf: 'Lauf 1 (F1)', n: 922, N: 922}, {lauf: 'Lauf 2 (R2)', n: 922, N: 922}], n_mittel: 2, n_nur_erstbewertung: 1, n_nur_lauf_1: 1,
    N: 4, schwelle_abweichung: 15, n_abweichung: 1, abweichung_datensatz: {n: 266, N: 922},
    standardfehler_hinweis: 'Gepoolter Standardfehler 5,50 gilt nur, wenn die Fehler beider Bewertungen unabhängig sind; nicht belegt (A3)',
    karten: {A: rating('mittel', 42.5, 40, 45, false), B: rating('mittel', 47.5, 40, 55, true), C: rating('nur_erstbewertung', 40, 40, null, false),
      D: rating('nur_lauf_1', 30, 30, null, false)}}};
setup(cards, field);
const out = {cells: cards.map((c) => { const cell = understandingCell(c); return {text: text(cell), mark: has(cell, 'bewertungen-abweichung')}; }),
  hint: understandingHint().map(text).join(' '), title: understandingHint()[0].props.title};
setup(cards, {...field, bewertungen: {verfuegbar: false, grund: 'Datei der gepoolten Werte nicht gefunden: pooled.jsonl', karten: {}}});
out.fallbackHint = understandingHint().map(text).join(' ');
out.noRating = text(understandingCell(cards[0]));
console.log(JSON.stringify(out));
"""
    )
    result = _node_json(script)
    assert isinstance(result, dict)
    a, b, c, d, e = result["cells"]
    assert a["text"].startswith("42,5") and "2 Bewertungen" in a["text"] and not a["mark"]
    # the doubt was made on H_F1: the visible label says so beside the mean
    assert "Prüfer-Modell bezweifelt H: zu niedrig (zu H aus Lauf 1)" in a["text"]
    assert b["text"].startswith("47,5") and b["mark"]
    assert "Bewertungen weichen stark ab (Δ 15: F1 40, R2 55)" in b["text"]
    assert c["text"].startswith("40 ") and "1 Bewertung, nur erste" in c["text"]
    assert "40,0" not in c["text"] and d["text"].startswith("30") and "nur Lauf 1" in d["text"]
    assert e["text"] == "unbekannt"  # no figure: unknown, never 0
    for cell in (a, b, c, d):
        assert min(_shown_spreads(cell["text"])) >= 8
    hint = result["hint"]
    assert "H = Mittel aus 2 Bewertungen bei 2 von 4 Karten" in hint
    assert "1 Bewertung (nur erste) bei 1, nur Lauf 1 bei 1" in hint
    assert "Lauf 1 (F1) n/N = 922/922, Lauf 2 (R2) n/N = 922/922; ohne Zusatzkorrektur" in hint
    assert "Bewertungen weichen stark ab (|ΔH| ≥ 15): 1 von 4 (Datensatz 266 von 922)" in hint
    assert "mindestens ±8" in hint and min(_shown_spreads(hint)) >= 8
    assert "nur, wenn die Fehler beider Bewertungen unabhängig sind" in result["title"]
    assert (
        "H nur Lauf 1 (F1), Mittel nicht verfügbar: Datei der gepoolten Werte"
        in (result["fallbackHint"])
    )
    assert "Bewertungen unbekannt" in result["noRating"]


def test_h_stays_without_sort_key_tier_or_filter() -> None:
    """H had no rank, sort key or filter before (E15 Q1); the pooled H gets none either."""
    js = (STATIC / "tierliste.js").read_text(encoding="utf-8")
    sorts = js[js.index("const SORTS = [") : js.index("];", js.index("const SORTS = ["))]
    assert "kartenverstaendnis" not in sorts.casefold() and "understanding" not in sorts
    sort_value = js[js.index("function sortValue(card, key)") : js.index("function sortBy(key)")]
    assert "understanding" not in sort_value and "bewertungen" not in sort_value
    start = js.index("// ---------- filters and sorting")
    filters = js[start : js.index("// The filters that are on, in words", start)]
    assert "understanding" not in filters and "bewertungen" not in filters
    assert "plainHead(UNDERSTANDING_NAME" in js  # a plain head, not a sort button


def test_the_register_records_the_owner_words() -> None:
    text = REGISTER.read_text(encoding="utf-8")
    entry = text[text.index("### E19") :]
    entry = entry[: entry.index("\n## ") if "\n## " in entry else len(entry)]
    assert "„Mittelwert beider anzeigen (Empfehlung)“" in entry
    assert "7085569723" in entry and "sinngemäß" in entry and "K1" in entry
