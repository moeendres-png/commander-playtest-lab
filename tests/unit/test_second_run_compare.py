"""Tests of the second-run comparison script (Refs #1404) with synthetic mini data.

Every expected value is a hand calculation written next to the assertion. No repository data:
the end-to-end test builds a tiny run folder (3 files, 4 cards each) in ``tmp_path``.
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "analysis" / "second_run_compare.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("second_run_compare", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["second_run_compare"] = module
    spec.loader.exec_module(module)
    return module


s = _load()


def test_midranks_and_spearman_use_average_ranks_for_ties() -> None:
    # sorted 5 -> 1, 10 -> 2, the two 20 share ranks 3 and 4 -> 3.5
    assert s.midranks([10, 20, 20, 5]) == [2.0, 3.5, 3.5, 1.0]
    assert s.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert s.spearman([1, 2, 3, 4], [40, 30, 20, 10]) == pytest.approx(-1.0)
    # ranks x 1,2,3 ; y 1.5,1.5,3 -> Pearson of (1,2,3) and (1.5,1.5,3) = 0.75 / sqrt(2 * 1.5) = 0.866
    assert s.spearman([1, 2, 3], [5, 5, 9]) == pytest.approx(math.sqrt(3) / 2)


def test_ols_slope_and_icc() -> None:
    # y = 2x + 1 -> slope 2
    assert s.ols_slope([0, 1, 2], [1, 3, 5]) == pytest.approx(2.0)
    # identical ratings -> ICC 1
    assert s.icc21([(10, 10), (20, 20), (40, 40)]) == pytest.approx(1.0)
    # pairs (0,10),(10,20),(20,30): grand 15, row means 5/15/25 -> MSR = 2*200/2 = 200;
    # column means 10/20 -> MSC = 3*50 = 150; residuals 0 -> MSE 0;
    # ICC = 200 / (200 + 0 + 2*150/3) = 200/300
    assert s.icc21([(0, 10), (10, 20), (20, 30)]) == pytest.approx(2 / 3)


def test_round5_band_and_side_of_fifty() -> None:
    assert [s.round5(x) for x in (27, 28, 32, 33, 45)] == [25, 30, 30, 35, 45]
    assert [s.band(h) for h in (100, 95, 90, 72, 70, 50, 45, 28, 25, 5, 4, 0)] == [
        "95-100", "95-100", "72-94", "72-94", "50-71", "50-71",
        "28-49", "28-49", "5-27", "5-27", "0-4", "0-4",
    ]  # fmt: skip


def test_delta_stats_by_hand() -> None:
    # deltas new - old: +10, -20, 0, +5
    st = s.delta_stats([(50, 60), (60, 40), (30, 30), (10, 15)])
    assert st["n"] == 4
    assert st["bias"] == pytest.approx(-5 / 4)
    assert st["mean_abs"] == pytest.approx(35 / 4)
    assert st["rms"] == pytest.approx(math.sqrt((100 + 400 + 0 + 25) / 4))
    assert st["ge15"] == 1 and st["share_ge15"] == pytest.approx(0.25) and st["max_abs"] == 20
    # bands: 50-71 vs 50-71 same; 50-71 vs 28-49 not; 28-49 same; 5-27 same -> 3
    assert st["same_band"] == 3
    # side of 50: (50,60) same, (60,40) differs, rest below on both -> 3
    assert st["same_side50"] == 3


def test_weighted_stats_use_pool_over_sample_weights() -> None:
    # stratum a: N/n = 10/1, delta +10; stratum b: N/n = 30/3, deltas 0, 0, -20 (weight 10 each)
    w = s.weighted_stats({"a": [(0, 10)], "b": [(5, 5), (5, 5), (40, 20)]}, {"a": 10, "b": 30})
    assert w["bias"] == pytest.approx((100 - 200) / 40)
    assert w["mean_abs"] == pytest.approx((100 + 200) / 40)
    assert w["share_ge15"] == pytest.approx(10 / 40)
    assert w["rms"] == pytest.approx(math.sqrt((10 * 100 + 10 * 400) / 40))


@pytest.mark.parametrize(
    ("metric", "value", "expected"),
    [
        ("M1", 8.0, "gruen"), ("M1", 8.01, "gelb"), ("M1", 11.0, "gelb"), ("M1", 11.01, "rot"),
        ("M2", 10.5, "gruen"), ("M2", 14.0, "gelb"), ("M2", 14.1, "rot"),
        ("M3", 0.20, "gruen"), ("M3", 0.29, "gelb"), ("M3", 0.30, "rot"),
        ("M4", 0.88, "gruen"), ("M4", 0.80, "gelb"), ("M4", 0.79, "rot"),
        ("M5", 1.10, "gruen"), ("M5", 0.70, "gelb"), ("M5", 1.30, "rot"), ("M5", 0.6, "rot"),
        ("M6", -5.0, "gruen"), ("M6", 7.9, "gelb"), ("M6", -8.5, "rot"),
        ("M7", 0.65, "gruen"), ("M7", 0.55, "gelb"), ("M7", 0.54, "rot"),
        ("M8", 0.88, "gruen"), ("M8", 0.80, "gelb"), ("M8", 0.79, "rot"),
        ("V1", 297, "gruen"), ("V1", 280, "gelb"), ("V1", 269, "rot"),
        ("K", 3, "gruen"), ("K", 7, "gelb"), ("K", 8, "rot"),
        ("L", 6, "gruen"), ("L", 15, "gelb"), ("L", 16, "rot"),
    ],
)  # fmt: skip
def test_grades_follow_the_plan_thresholds(metric: str, value: float, expected: str) -> None:
    assert s.grade(metric, value) == expected


def test_unknown_value_is_never_graded() -> None:
    assert s.grade("K", None) == "unbekannt"
    assert s.grade("M4", float("nan")) == "unbekannt"


def test_bootstrap_is_deterministic_and_resamples_within_groups() -> None:
    groups = [[(0, 10)] * 5, [(0, -10)] * 5]
    a = s.bootstrap(groups, {"bias": s._bias}, draws=200, seed=7)
    b = s.bootstrap(groups, {"bias": s._bias}, draws=200, seed=7)
    assert a == b
    # each group keeps its size, so the pooled bias is always (5*10 - 5*10)/10 = 0
    assert a["bias"] == (0.0, 0.0)
    assert s.percentile_interval([float(i) for i in range(101)]) == (2.0, 98.0)


BLOCK = (
    "CARD: Testling\nType line: Creature — Elf | Group: Creature\nOracle text:\n"
    "  When this creature enters, draw a card.\nRoles (labels): card_draw\n"
    "Pattern hits (rule-based hints; '~' stands for this card; check each in pattern_check):\n"
    '  - etb_own: "when ~ enters, draw a card."\n  - etb_own_draw: "draw a card"\n'
)


def test_pattern_hits_type_line_and_chulane_text() -> None:
    assert s.pattern_hits(BLOCK) == ["etb_own", "etb_own_draw"]
    assert s.pattern_hits("Oracle text:\n  x\nPattern hits: none\n") == []
    assert s.is_type_line_claim("Creature — Elf", BLOCK)
    assert not s.is_type_line_claim("draw a card", BLOCK)
    guide = (
        "intro\nThe commander (exact Oracle text):\n\n> Chulane line one.\n> line two.\n\nafter\n"
    )
    assert s.chulane_text(guide) == "Chulane line one. line two."


def _row(**over: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "schema": "rubric-v2-card-rating-1",
        "oracle_id": "id-1",
        "card": "Testling",
        "judged_as": "spell",
        "scores": dict.fromkeys(s.CRITERIA, 50),
        "notes": dict.fromkeys(s.CRITERIA, "short note"),
        "reason": "According to the card text it draws a card when it enters, so a recast repeats it.",
        "confidence": "high",
        "uncertainty": "",
        "rule_claims": [
            {
                "quote": "draw a card",
                "interaction": "etb_reuse",
                "claim": "each entry draws",
                "basis": "card_text",
            }
        ],
        "pattern_check": [
            {"rule_id": "etb_own", "verdict": "correct"},
            {"rule_id": "etb_own_draw", "verdict": "correct"},
        ],
    }
    row.update(over)
    return row


def test_plan_and_schema_problems() -> None:
    inp = {"oracle_id": "id-1", "card": "Testling"}
    assert s.plan_problems(_row(), inp) == []
    assert s.schema_problems(_row(), BLOCK) == []
    assert s.plan_problems(_row(oracle_id="id-x"), inp) == ["oracle_id"]
    assert "scores keys" in s.plan_problems(_row(scores={"E": 5}), inp)
    assert s.plan_problems(_row(confidence="low", uncertainty=""), inp) == [
        "uncertainty empty though not high"
    ]
    assert s.schema_problems(_row(pattern_check=[]), BLOCK) == ["pattern_check coverage"]
    scores = dict.fromkeys(s.CRITERIA, 50) | {"H": 52}
    assert s.schema_problems(_row(scores=scores), BLOCK) == ["scores not multiple of 5"]


def test_blindness_scan_finds_popularity_and_earlier_numbers() -> None:
    clean = _row()
    pop = _row(
        reason="A staple in many lists, according to the card text it draws a card on entry."
    )
    earlier = _row(uncertainty="The F1 value was higher.", confidence="low")
    hits = s.blindness_hits({"1:1": clean, "1:2": pop, "1:3": earlier})
    assert [(h["id"], h["kind"]) for h in hits] == [("1:2", "popularity"), ("1:3", "earlier")]


def test_select_claims_one_per_card_preferred_interactions_and_deterministic() -> None:
    cards = [
        (
            f"1:{i}",
            [
                {"interaction": "mana"},
                {"interaction": "chulane_cast_trigger"},
                {"interaction": "other"},
            ],
        )
        for i in range(1, 9)
    ]
    cards.append(("1:9", []))
    first = s.select_claims(cards, k=5, seed=3)
    assert first == s.select_claims(cards, k=5, seed=3)
    assert len(first) == 5 and len({cid for cid, _ in first}) == 5
    # only index 1 carries a preferred interaction
    assert all(idx == 1 for _, idx in first)
    # fewer eligible cards than k: every card with a claim, card 1:9 has none
    assert len(s.select_claims(cards, k=50, seed=3)) == 8


def test_flagged_metrics_and_verdict_branches() -> None:
    rows = [
        {"card": "a", "kind": "H zu hoch", "low": 30, "high": 40, "h_old": 60, "h_new": 35},
        {"card": "b", "kind": "H zu hoch", "low": 30, "high": 40, "h_old": 60, "h_new": 55},
        {"card": "c", "kind": "H zu niedrig", "low": 50, "high": 60, "h_old": 30, "h_new": 20},
    ]
    m = s.flagged_metrics(rows, top20_bias=-5.0)
    assert m["a_inside"] == 1 and m["a_inside_old"] == 0
    # distances: a 20 -> 0 closer, b 20 -> 15 closer, c 20 -> 30 not
    assert m["b_closer"] == 2
    assert m["c_mean_delta"]["H zu hoch"] == {"n": 2, "mean": -15.0}
    assert m["d_too_high_minus_top20"] == pytest.approx(-10.0)
    # 1 of 3 inside (<= 7) and closer 2 (<= 17) -> "stuetzt nicht"
    assert m["verdict"] == "stuetzt nicht"
    many = [
        {"card": str(i), "kind": "H zu hoch", "low": 30, "high": 40, "h_old": 60, "h_new": 35}
        for i in range(14)
    ]
    assert s.flagged_metrics(many, top20_bias=-5.0)["verdict"] == "stuetzt"
    # 14 inside but (d) = -25 - (-22) = -3 > -5 -> "teilweise"
    assert s.flagged_metrics(many, top20_bias=-22.0)["verdict"] == "teilweise"


def test_overall_verdict_branches() -> None:
    green = dict.fromkeys(
        ("M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "V1", "V2", "V3", "V4", "K", "L"), "gruen"
    )
    assert s.overall_verdict(green, []) == "bestaetigt"
    # plan section 9: "bestaetigt" allows yellow (not red) in M6 to M8
    assert s.overall_verdict(green | {"M8": "gelb"}, []) == "bestaetigt"
    assert s.overall_verdict(green | {"M1": "gelb", "M8": "gelb"}, []) == "teilweise bestaetigt"
    assert s.overall_verdict(green | {"M6": "rot"}, []) == "teilweise bestaetigt"
    assert s.overall_verdict(green | {"V4": "gelb"}, []) == "teilweise bestaetigt"
    assert s.overall_verdict(green | {"M2": "rot"}, []) == "nicht bestaetigt"
    assert s.overall_verdict(green, ["A6"]) == "kein Schluss"
    # rule claims without hand verdicts, or blindness not graded: never "bestaetigt"
    assert s.overall_verdict(green | {"K": "unbekannt"}, []) == "teilweise bestaetigt"
    assert s.overall_verdict(green | {"L": "unbekannt"}, []) == "teilweise bestaetigt"
    assert s.overall_verdict(green | {"K": "gelb"}, []) == "bestaetigt"


@pytest.mark.parametrize(
    ("metric", "value", "expected"),
    [
        ("M1", 6.5, "gruen"), ("M1", 8.0, "gelb"), ("M1", 8.38, "rot"),
        ("M2", 11.45, "rot"), ("M3", 0.245, "rot"), ("M4", 0.881, "gelb"),
        ("M6", -3.3, "gelb"), ("M7", 0.679, "rot"), ("M8", 0.853, "rot"), ("M8", 0.93, "gruen"),
    ],
)  # fmt: skip
def test_same_family_thresholds_of_plan_branch_2a(metric: str, value: float, expected: str) -> None:
    assert s.grade(metric, value, s.GRADES_SAME_FAMILY) == expected


def _write_run(root: Path) -> tuple[Path, Path, Path]:
    rr = root / "rr"
    rater = rr / "rater"
    rater.mkdir(parents=True)
    strata = ["flagged", "top20", "rest", "land"]
    old_h = {"flagged": 60, "top20": 50, "rest": 20, "land": 30}
    shift = {1: 0, 2: -5, 3: -10}
    manifest: list[dict[str, Any]] = []
    old_rows, flagged = [], []
    for f in (1, 2, 3):
        inputs, outputs = [], []
        for seq, st in enumerate(strata, start=1):
            oid, name = f"id-{f}-{seq}", f"Card {f}-{seq}"
            manifest.append(
                {
                    "oracle_id": oid,
                    "name": name,
                    "stratum": st,
                    "input_file": f,
                    "seq": seq,
                    "is_land": st == "land",
                }
            )
            block = f"CARD: {name}\nType line: Creature | Group: Creature\nOracle text:\n  Draw a card.\nPattern hits: none\n"
            inputs.append({"seq": seq, "oracle_id": oid, "card": name, "card_block": block})
            scores = dict.fromkeys(s.CRITERIA, 40) | {"H": old_h[st] + shift[f]}
            outputs.append(_row(oracle_id=oid, card=name, scores=scores, pattern_check=[]))
            old_rows.append(
                {
                    "oracle_id": oid,
                    "card": name,
                    "scores": dict.fromkeys(s.CRITERIA, 40) | {"H": old_h[st]},
                    "reason": "old",
                }
            )
            if st == "flagged":
                flagged.append(
                    {
                        "card": name,
                        "rater_H": 60,
                        "proposed_H_low": 45,
                        "proposed_H_high": 55,
                        "kind": "H zu hoch",
                    }
                )
        (rater / f"rr_input_{f}.jsonl").write_text(
            "".join(json.dumps(x) + "\n" for x in inputs), encoding="utf-8"
        )
        (rater / f"rr_output_{f}.jsonl").write_text(
            "".join(json.dumps(x) + "\n" for x in outputs), encoding="utf-8"
        )
    (rr / "rr_sample_manifest.json").write_text(
        json.dumps({"meta": {}, "cards": manifest}), encoding="utf-8"
    )
    (rater / s.GUIDE_NAME).write_text(
        "The commander (exact Oracle text):\n> Chulane text.\n", encoding="utf-8"
    )
    old_path, flagged_path = root / "old.jsonl", root / "flagged.jsonl"
    old_path.write_text("".join(json.dumps(x) + "\n" for x in old_rows), encoding="utf-8")
    flagged_path.write_text("".join(json.dumps(x) + "\n" for x in flagged), encoding="utf-8")
    return rr, old_path, flagged_path


def test_end_to_end_on_a_tiny_run(tmp_path: Path) -> None:
    rr, old_path, flagged_path = _write_run(tmp_path)
    out = tmp_path / "result.json"
    assert (
        s.main(
            [
                "--rr-dir",
                str(rr),
                "--old",
                str(old_path),
                "--flagged",
                str(flagged_path),
                "--out",
                str(out),
            ]
        )
        == 0
    )
    r = json.loads(out.read_text(encoding="utf-8"))
    assert r["n_cards"] == 12 and r["n_valid"] == 12 and not r["schema_problems"]
    # primary = 9 cards with deltas 0,0,0 / -5,-5,-5 / -10,-10,-10 -> mean |dH| 5, bias -5
    assert r["metrics"]["M1"] == pytest.approx(5.0)
    assert r["primary"]["bias"] == pytest.approx(-5.0)
    # rest + land: 6 cards, deltas 0,0,-5,-5,-10,-10 -> bias -5
    assert r["metrics"]["M6"] == pytest.approx(-5.0)
    # flagged H_new 60, 55, 50 in the span 45..55 -> 2 of 3 inside; F1 60 inside 0 of 3
    assert r["flagged"]["a_inside"] == 2 and r["flagged"]["a_inside_old"] == 0
    assert r["flagged"]["rater_H_matches_F1"] == 3
    # every quote "draw a card" is literal in the block
    assert r["quotes_literal"] == r["claims_total"] == 12
    # 12 valid cards < 270 -> stop rule A1 -> no pooled verdict
    assert "A1" in r["stops"] and r["verdict"] == "kein Schluss"
    # file 3 primary mean |dH| 10 against file 1 0 -> gap 10 > 4 -> A6
    assert r["file_gap_primary"] == pytest.approx(10.0) and "A6" in r["stops"]
    # no hand verdicts -> K unknown; no keyword hits -> L green
    assert r["grades"]["K"] == "unbekannt" and r["grades"]["L"] == "gruen"
