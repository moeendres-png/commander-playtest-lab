"""Tests of the second-run comparison script (Refs #1404) with synthetic mini data.

Every expected value is a hand calculation written next to the assertion. No repository data:
the end-to-end test builds a tiny run folder (3 files, 4 cards each) in ``tmp_path``.
"""

from __future__ import annotations

import importlib.util
import json
import math
import statistics
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "analysis" / "second_run_compare.py"
V3_BASELINES = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "research"
    / "chulane_rubric_v3_20261123"
    / "phaseA_scripts"
    / "v3_baselines.py"
)


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


# ---------- phaseA_scripts/v3_baselines.py (Refs #1768) ----------


class _MiniArray:
    """Minimal 1D/2D array shim used only when numpy is absent from the test venv."""

    def __init__(self, data: list[object]) -> None:
        self._data = data
        self._is2d = bool(data) and isinstance(data[0], list)

    @property
    def shape(self) -> tuple[int, ...]:
        if self._is2d:
            first = self._data[0]
            return (len(self._data), len(first) if isinstance(first, list) else 0)
        return (len(self._data),)

    def __len__(self) -> int:
        return len(self._data)

    def astype(self, typ: type) -> _MiniArray:
        if self._is2d:
            return _MiniArray([[typ(v) for v in row] for row in self._data])  # type: ignore[union-attr]
        return _MiniArray([typ(v) for v in self._data])

    def copy(self) -> _MiniArray:
        if self._is2d:
            return _MiniArray([list(row) for row in self._data])  # type: ignore[arg-type]
        return _MiniArray(list(self._data))

    def _broadcast_op(self, other: object, fn: object) -> _MiniArray:
        op = fn  # type: ignore[assignment]
        if isinstance(other, (int, float)):
            if self._is2d:
                return _MiniArray([[op(v, other) for v in row] for row in self._data])  # type: ignore[union-attr]
            return _MiniArray([op(v, other) for v in self._data])
        if isinstance(other, _MiniArray):
            if not self._is2d and not other._is2d:
                return _MiniArray([op(a, b) for a, b in zip(self._data, other._data, strict=True)])
            if self._is2d and other._is2d:
                sr, sc = self.shape
                or_, oc = other.shape
                rows = max(sr, or_)
                cols = max(sc, oc)
                return _MiniArray(
                    [
                        [
                            op(
                                self._data[r % sr][c % sc],  # type: ignore[index]
                                other._data[r % or_][c % oc],  # type: ignore[index]
                            )
                            for c in range(cols)
                        ]
                        for r in range(rows)
                    ]
                )
        raise TypeError(f"unsupported operand types: _MiniArray and {type(other)}")

    def __add__(self, other: object) -> _MiniArray:
        return self._broadcast_op(other, lambda a, b: a + b)

    def __radd__(self, other: object) -> _MiniArray:
        return self._broadcast_op(other, lambda a, b: b + a)

    def __sub__(self, other: object) -> _MiniArray:
        return self._broadcast_op(other, lambda a, b: a - b)

    def __rsub__(self, other: object) -> _MiniArray:
        return self._broadcast_op(other, lambda a, b: b - a)

    def __mul__(self, other: object) -> _MiniArray:
        return self._broadcast_op(other, lambda a, b: a * b)

    def __rmul__(self, other: object) -> _MiniArray:
        return self._broadcast_op(other, lambda a, b: b * a)

    def __pow__(self, other: object) -> _MiniArray:
        return self._broadcast_op(other, lambda a, b: a**b)

    def __eq__(self, other: object) -> object:
        if isinstance(other, (str, int, float)) and not self._is2d:
            return _MiniArray([v == other for v in self._data])
        return NotImplemented

    def __getitem__(self, key: object) -> object:
        if isinstance(key, tuple) and len(key) == 2 and self._is2d:
            r, c = key
            if isinstance(r, slice) and isinstance(c, int):
                return _MiniArray([row[c] for row in self._data[r]])  # type: ignore[index]
            if isinstance(r, int) and isinstance(c, int):
                return self._data[r][c]  # type: ignore[index]
            if isinstance(r, _MiniArray) and isinstance(c, int):
                return _MiniArray(
                    [
                        row[c]  # type: ignore[index]
                        for row, keep in zip(self._data, r._data, strict=True)
                        if keep
                    ]
                )
        if isinstance(key, _MiniArray) and not self._is2d:
            if key._data and isinstance(key._data[0], bool):
                return _MiniArray(
                    [v for v, keep in zip(self._data, key._data, strict=True) if keep]
                )
            return _MiniArray([self._data[int(i)] for i in key._data])  # type: ignore[arg-type]
        if isinstance(key, slice):
            return _MiniArray(self._data[key])
        if isinstance(key, int):
            return self._data[key]
        raise TypeError(f"unsupported index {key!r}")

    def __setitem__(self, key: object, value: object) -> None:
        if isinstance(key, tuple) and len(key) == 2 and self._is2d:
            r, c = key
            if isinstance(r, _MiniArray) and isinstance(c, int):
                vals = value._data if isinstance(value, _MiniArray) else None
                vi = 0
                for row, keep in zip(self._data, r._data, strict=True):
                    if keep:
                        row[c] = vals[vi] if vals is not None else value  # type: ignore[index]
                        vi += 1
                return
        if isinstance(key, _MiniArray) and not self._is2d:
            if isinstance(value, _MiniArray):
                for idx, v in zip(key._data, value._data, strict=True):
                    self._data[int(idx)] = v  # type: ignore[arg-type]
            else:
                for idx in key._data:
                    self._data[int(idx)] = value  # type: ignore[arg-type]
            return
        raise TypeError(f"unsupported item assignment {key!r}")

    def sum(self) -> float:
        if self._is2d:
            return float(sum(float(v) for row in self._data for v in row))  # type: ignore[union-attr]
        return float(sum(float(v) for v in self._data))  # type: ignore[arg-type]

    def mean(self, axis: int | None = None, keepdims: bool = False) -> object:
        if axis is None:
            if self._is2d:
                flat = [float(v) for row in self._data for v in row]  # type: ignore[union-attr]
                return sum(flat) / len(flat)
            return sum(float(v) for v in self._data) / len(self._data)  # type: ignore[arg-type]
        if axis == 1:
            means = [sum(float(v) for v in row) / len(row) for row in self._data]  # type: ignore[union-attr]
            return _MiniArray([[m] for m in means]) if keepdims else _MiniArray(means)
        if axis == 0:
            n, k = self.shape
            means = [sum(float(self._data[r][c]) for r in range(n)) / n for c in range(k)]  # type: ignore[index]
            return _MiniArray([means]) if keepdims else _MiniArray(means)
        raise ValueError(f"unsupported axis {axis}")

    def var(self, ddof: int = 0) -> float:
        vals = [float(v) for v in self._data]  # type: ignore[arg-type]
        m = sum(vals) / len(vals)
        return sum((v - m) ** 2 for v in vals) / (len(vals) - ddof)


def _mini_numpy() -> ModuleType:
    mod = ModuleType("numpy")

    def _to_list(x: object) -> list[object]:
        if isinstance(x, _MiniArray):
            return x.copy()._data
        return list(x)  # type: ignore[call-overload]

    def array(data: object, dtype: type | None = None) -> _MiniArray:
        arr = _MiniArray(_to_list(data))
        return arr.astype(dtype) if dtype is not None else arr

    def column_stack(cols: list[object]) -> _MiniArray:
        lists = [_to_list(c) for c in cols]
        n = len(lists[0])
        return _MiniArray([[col[i] for col in lists] for i in range(n)])

    def argsort(v: _MiniArray, kind: str = "mergesort") -> _MiniArray:
        _ = kind
        return _MiniArray(sorted(range(len(v)), key=lambda i: v._data[i]))  # type: ignore[arg-type,return-value]

    def empty(n: int) -> _MiniArray:
        return _MiniArray([0.0] * n)

    def arange(start: float, stop: float | None = None, dtype: type | None = None) -> _MiniArray:
        if stop is None:
            vals: list[object] = list(range(int(start)))
        else:
            vals = [float(i) for i in range(int(start), int(stop))]
        arr = _MiniArray(vals)
        return arr.astype(dtype) if dtype is not None else arr

    def full(n: int, value: float) -> _MiniArray:
        return _MiniArray([value] * n)

    def tile(a: _MiniArray, reps: int) -> _MiniArray:
        return _MiniArray(a._data * reps)

    def corrcoef(a: _MiniArray, b: _MiniArray) -> _MiniArray:
        xs = [float(v) for v in a._data]  # type: ignore[arg-type]
        ys = [float(v) for v in b._data]  # type: ignore[arg-type]
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
        den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
        r = num / den
        return _MiniArray([[1.0, r], [r, 1.0]])

    def median(x: _MiniArray, axis: int = 1) -> _MiniArray:
        if axis != 1 or not x._is2d:
            raise ValueError("only axis=1 on 2D arrays is supported")
        return _MiniArray([float(statistics.median(row)) for row in x._data])  # type: ignore[arg-type]

    mod.array = array  # type: ignore[attr-defined]
    mod.asarray = array  # type: ignore[attr-defined]
    mod.column_stack = column_stack  # type: ignore[attr-defined]
    mod.argsort = argsort  # type: ignore[attr-defined]
    mod.empty = empty  # type: ignore[attr-defined]
    mod.arange = arange  # type: ignore[attr-defined]
    mod.full = full  # type: ignore[attr-defined]
    mod.tile = tile  # type: ignore[attr-defined]
    mod.corrcoef = corrcoef  # type: ignore[attr-defined]
    mod.median = median  # type: ignore[attr-defined]
    mod.sqrt = math.sqrt  # type: ignore[attr-defined]
    return mod


def _load_v3_baselines() -> tuple[ModuleType, ModuleType]:
    try:
        import numpy as np  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        np = _mini_numpy()
    injected = "numpy" not in sys.modules
    if injected:
        sys.modules["numpy"] = np
    try:
        spec = importlib.util.spec_from_file_location("v3_baselines", V3_BASELINES)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules["v3_baselines"] = module
        spec.loader.exec_module(module)
    finally:
        if injected:
            sys.modules.pop("numpy", None)
    return module, np


def test_v3_baselines_icc21_spearman_and_icc_k_by_hand() -> None:
    v3, np = _load_v3_baselines()
    a = np.array([0.0, 10.0, 20.0])
    b = np.array([10.0, 20.0, 30.0])
    assert v3.icc21(a, a) == pytest.approx(1.0)
    # MSR = 200, MSC = 150, MSE = 0 -> ICC(2,1) = 200 / (200 + 2*150/3) = 2/3
    assert v3.icc21(a, b) == pytest.approx(2 / 3)
    assert v3.icc_k(np.column_stack([a, b])) == pytest.approx(2 / 3)
    # 3 raters [[0,0,10],[10,10,20],[20,20,30]]: MSR = 300, MSC = 100, MSE = 0 -> 300 / 400 = 0.75
    x3 = np.array([[0.0, 0.0, 10.0], [10.0, 10.0, 20.0], [20.0, 20.0, 30.0]])
    assert v3.icc_k(x3) == pytest.approx(0.75)
    assert v3.spearman(np.array([1, 2, 3, 4]), np.array([10, 20, 30, 40])) == pytest.approx(1.0)
    assert v3.spearman(np.array([1, 2, 3, 4]), np.array([40, 30, 20, 10])) == pytest.approx(-1.0)
    # ties: ranks [0, 1, 2] vs [0.5, 0.5, 2.0] -> sqrt(3) / 2
    assert v3.spearman(np.array([1, 2, 3]), np.array([5, 5, 9])) == pytest.approx(math.sqrt(3) / 2)


def test_v3_baselines_s3_flags_s6_flag_and_clamp_h() -> None:
    v3, np = _load_v3_baselines()
    # s3_flags: 15 cards (5 K, 5 N, 5 L), small within-group variance so SE > 0
    kinds = np.array(["K"] * 5 + ["N"] * 5 + ["L"] * 5)
    base = np.tile(np.array([20.0, 30.0, 40.0, 50.0, 60.0]), 3)
    noise = np.array([0.5, -0.5, 0.5, -0.5, 0.0] * 3)
    x_clean = np.column_stack([base + noise, base, base])
    assert v3.s3_flags(x_clean, kinds, sd_pool=15.0) == {"s3": False, "s3c": False}
    # Shift only L on rater 0 by +12 -> S3c triggers, S3 (K vs N) stays False
    x_land = x_clean.copy()
    x_land[kinds == "L", 0] = x_land[kinds == "L", 0] + 12.0
    assert v3.s3_flags(x_land, kinds, sd_pool=15.0) == {"s3": False, "s3c": True}
    # Shift K on rater 0 by +12 -> S3 (K vs N) and S3c (K vs L) both trigger
    x_creature = x_clean.copy()
    x_creature[kinds == "K", 0] = x_creature[kinds == "K", 0] + 12.0
    assert v3.s3_flags(x_creature, kinds, sd_pool=15.0) == {"s3": True, "s3c": True}

    # s6_flag: 10 cards, positions 1..10; symmetric orthogonal noise -> slope 0 -> False
    pos = np.column_stack([np.arange(1.0, 11.0)] * 3)
    # e symmetric around midpoint 5.5 -> sum((p - 5.5) * e) = 0 exactly, SE > 0
    sym_noise = np.array([1.0, -1.0, 1.0, -1.0, 0.0, 0.0, -1.0, 1.0, -1.0, 1.0])
    x_no_drift = np.column_stack([50.0 + sym_noise, np.full(10, 50.0), np.full(10, 50.0)])
    assert v3.s6_flag(x_no_drift, pos, thr=1.5) is False
    # Linear drift +0.5 per position on rater 0 (10 * slope = 5.0 > 1.5, tiny noise) -> True
    x_drift = np.column_stack(
        [50.0 + 0.5 * pos[:, 0] + 0.05 * sym_noise, np.full(10, 50.0), np.full(10, 50.0)]
    )
    assert v3.s6_flag(x_drift, pos, thr=1.5) is True

    # clamp_h: ref = 0.3*60 + 0.3*60 + 0.2*50 + 0.1*50 + 0.1*50 - 0.2*(100 - 80) = 52.0
    row = {"F1_E": 60, "F1_F": 60, "F1_R": 50, "F1_T": 50, "F1_K": 50, "F1_D": 80}
    assert v3.v3b_set(row, "F1") == pytest.approx(52.0)
    assert v3.clamp_h(row | {"F1_H": 55}, "F1") == pytest.approx(55.0)
    assert v3.clamp_h(row | {"F1_H": 80}, "F1") == pytest.approx(62.0)
    assert v3.clamp_h(row | {"F1_H": 20}, "F1") == pytest.approx(42.0)
