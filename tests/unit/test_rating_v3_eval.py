"""Tests of the v3 evaluation script (Refs #1404) with synthetic data only.

No real rater output is read: every run folder is built in ``tmp_path``. The synthetic pilot has
the plan's shape: 6 chunks of 15 non-anchor cards plus 4 hidden anchor places (19 cards), 90
non-anchor cards (51 creatures, 27 non-creature spells, 12 lands), 10 anchor cards placed 2 or 3
times, raters A/B/C with their own order. Rater values are the true values plus small noise, so
the clean run meets every criterion; each test changes one thing. Expected values are hand
calculations next to the assertions.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import random
import statistics
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "analysis" / "rating_v3_eval.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("rating_v3_eval", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["rating_v3_eval"] = module
    spec.loader.exec_module(module)
    return module


ev = _load()
RATERS = ("A", "B", "C")
CRIT = ("E", "F", "T", "R", "K", "N")
SENTINEL = "SENTINEL-MODEL-XYZ-0"
DRAWS = 200


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def clip5(v: int) -> int:
    return max(0, min(100, v))


class Lab:
    """A synthetic pilot (or full run) on disk."""

    def __init__(self, root: Path, monkeypatch: pytest.MonkeyPatch, phase: str = "pilot") -> None:
        self.root, self.mp, self.phase = root, monkeypatch, phase
        self.inputs = root / "inputs"
        self.rater = root / "rater"
        self.inputs.mkdir()
        self.rater.mkdir()
        rng = random.Random(7)
        self.plain = [f"n{i:02d}" for i in range(90)]
        self.anchors = [f"a{i}" for i in range(10)]
        kinds = ["kreatur"] * 51 + ["nicht_kreatur"] * 27 + ["land"] * 12
        self.cards: dict[str, dict[str, Any]] = {}
        self.true: dict[str, dict[str, int]] = {}
        for o, kd in zip(self.plain, kinds, strict=True):
            self.cards[o] = {"card": f"Card {o}", "art": kd, "schicht": "x", "anker": None}
        for i, o in enumerate(self.anchors):
            self.cards[o] = {"card": f"Anchor {o}", "art": "land" if i >= 8 else "nicht_kreatur",
                             "schicht": "anker", "anker": None}  # fmt: skip
        for o in sorted(self.cards):
            t = {c: 5 * rng.randint(2, 18) for c in ("E", "F", "T", "R", "K")}
            t["N"] = 5 * rng.randint(0, 10)
            self.true[o] = t
        for i, o in enumerate(self.anchors):
            self.cards[o]["anker"] = {"satz": "alt" if i < 5 else "neu",
                                      "zeilen": {"E": self.true[o]["E"], "R": self.true[o]["R"]}}  # fmt: skip
        self.chunks: list[dict[str, Any]] = []
        for k in range(1, 7):
            ids = self.plain[(k - 1) * 15 : k * 15] + [
                self.anchors[((k - 1) * 4 + j) % 10] for j in range(4)
            ]
            order = {}
            for x, r in enumerate(RATERS):
                o = list(ids)
                random.Random(20261127 + x).shuffle(o)
                order[r] = o
            self.chunks.append(
                {"k": k, "tranche": 1 if k <= 3 else 2, "karten": ids, "reihenfolge": order}
            )
        self.values: dict[tuple[str, str, int], dict[str, int]] = {}
        noise = random.Random(11)
        for ch in self.chunks:
            for o in ch["karten"]:
                for r in RATERS:
                    v = {c: clip5(self.true[o][c] + 5 * noise.choice((-1, 0, 0, 1))) for c in CRIT}
                    v["H"] = clip5(5 * round(ev.h_ref({c: float(x) for c, x in v.items()}) / 5))
                    self.values[(r, o, ch["k"])] = v
        self.line_hook: dict[tuple[str, int], Callable[[list[str]], list[str]]] = {}
        self.card_extra: dict[tuple[str, str, int], dict[str, Any]] = {}
        self.note: dict[tuple[str, str, int], str] = {}
        self.skip_files: set[str] = set()
        self.tool_calls_extra: list[dict[str, Any]] = []
        self.counting: set[str] = set()
        self.pilot_runde = 1
        self.run_log_override: dict[str, Any] = {}

    # ---------------------------------------------------------------- writing
    def build(self) -> None:
        files: dict[str, str] = {}
        for name, text in (
            ("output_schema_v3.json", "{}\n"),
            ("v3_rater_instructions.md", "Rate.\n"),
        ):
            (self.inputs / name).write_text(text, encoding="utf-8")
            files[name] = _sha(self.inputs / name)
        for ch in self.chunks:
            k = ch["k"]
            guide = self.inputs / f"v3_guide_{k}.md"
            guide.write_text(f"Guide chunk {k}\n", encoding="utf-8")
            files[guide.name] = _sha(guide)
            ch["eingabe"] = {}
            for r in RATERS:
                p = self.inputs / f"v3_input_{k}_{r}.jsonl"
                p.write_text("".join(json.dumps({"seq": i, "oracle_id": o, "card": self.cards[o]["card"],
                                                 "card_block": f"Name: {self.cards[o]['card']}\nOracle text: draw a card"}) + "\n"
                                     for i, o in enumerate(ch["reihenfolge"][r], 1)), encoding="utf-8")  # fmt: skip
                files[p.name] = _sha(p)
                ch["eingabe"][r] = p.name
                self.write_output(r, k, ch["reihenfolge"][r])
        man = {"schema": "rating-v3-manifest-1", "phase": self.phase, "dateien": files,
               "karten": self.cards, "chargen": self.chunks}  # fmt: skip
        if self.phase == "pilot":
            man["pilot_runde"] = self.pilot_runde
        self.manifest = self.root / "manifest.json"
        self.manifest.write_text(json.dumps(man, sort_keys=True), encoding="utf-8")
        self.mp.setitem(ev.PINNED_MANIFEST_SHA256, self.phase, _sha(self.manifest))
        sums = []
        for p in sorted(self.rater.iterdir()):
            sums.append(f"{_sha(p)}  {p.name}\n")
        self.sums = self.root / "SHA256SUMS"
        self.sums.write_text("".join(sums), encoding="utf-8")
        self.replies = {
            f"{r}:{ch['k']}": "Done; read only my folder." for ch in self.chunks for r in RATERS
        }

    def write_output(self, r: str, k: int, order: list[str]) -> None:
        lines = []
        for o in order:
            row = {"oracle_id": o, "reason": "Plain text about the card.", "confidence": "high",
                   "uncertainty": "", "rule_claims": [{"quote": "draw a card", "interaction": "other",
                                                       "claim": f"draws a card ({o})", "basis": "card_text"}],
                   "pattern_check": []}  # fmt: skip
            row.update(self.card_extra.get((r, o, k), {}))
            lines.append(json.dumps(row))
            v = self.values[(r, o, k)]
            for c in (*CRIT, "H"):
                lines.append(
                    json.dumps(
                        {"criterion": c, "note": self.note.get((r, o, k), "fits"), "value": v[c]}
                    )
                )
        hook = self.line_hook.get((r, k))
        if hook:
            lines = hook(lines)
        for name, text in (
            (f"v3_output_{r}_{k}.jsonl", "".join(x + "\n" for x in lines)),
            (f"v3_transcript_{r}_{k}.jsonl", json.dumps({"t": f"transcript {r} {k}"}) + "\n"),
            (f"v3_meta_{r}_{k}.json", json.dumps({"model": SENTINEL, "effort": "high"}) + "\n"),
        ):
            if name not in self.skip_files:
                (self.rater / name).write_text(text, encoding="utf-8")

    def run_log(self) -> dict[str, Any]:
        inst = {}
        for ch in self.chunks:
            for r in RATERS:
                k = ch["k"]
                meta = self.rater / f"v3_meta_{r}_{k}.json"
                tr = self.rater / f"v3_transcript_{r}_{k}.jsonl"
                inst[f"{r}:{k}"] = {"modell_id": SENTINEL, "stufe": "groß", "version": SENTINEL + "-v1",
                                    "aufwand": "high", "agent_id": f"agent-{r}-{k}",
                                    "meta_sha256": _sha(meta) if meta.exists() else "",
                                    "transkript_sha256": _sha(tr) if tr.exists() else "",
                                    "a2_verstoesse_frueher": 0, "abbrueche_a7": 0}  # fmt: skip
        log = {"laufprotokoll_vorhanden": True, "hash_kommentar": "https://example.invalid/1404#1",
               "skript_vor_oeffnen_committet": True, "hashes_vor_oeffnen_gepostet": True, "instanzen": inst}  # fmt: skip
        log.update(self.run_log_override)
        return log

    def tool_calls(self) -> dict[str, Any]:
        folders = {
            f"{r}:{ch['k']}": f"/scratch/raters/{r}_{ch['k']}" for ch in self.chunks for r in RATERS
        }
        calls = []
        for key, f in sorted(folders.items()):
            calls.append(
                {"instanz": key, "werkzeug": "Read", "pfad": f + "/v3_rater_instructions.md"}
            )
            calls.append(
                {
                    "instanz": key,
                    "werkzeug": "Write",
                    "pfad": f + "/out.jsonl",
                    "content": "SECRET-WRITE",
                }
            )
        return {"ordner": folders, "aufrufe": calls + self.tool_calls_extra}

    # ---------------------------------------------------------------- running
    def hits(self) -> tuple[bytes, list[dict[str, Any]]]:
        data, hits, _ = ev.run_hits(self.manifest, self.inputs, self.rater, self.sums, self.replies)
        return data, hits

    def classification(self) -> bytes:
        data, hits = self.hits()
        cls = {"hits_sha256": hashlib.sha256(data).hexdigest(), "github_kommentar": "https://example.invalid/c",
               "einstufung": {h["id"]: ({"zaehlt": True, "buchstabe": None} if h["id"] in self.counting
                                        else {"zaehlt": False, "buchstabe": "a"}) for h in hits}}  # fmt: skip
        return json.dumps(cls, sort_keys=True).encode()

    def eval(self, **kw: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        data, _ = self.hits()
        cb = kw.pop("classification_bytes", None) or self.classification()
        args: dict[str, Any] = {
            "manifest_path": self.manifest, "inputs_dir": self.inputs, "rater_dir": self.rater,
            "checksums_path": self.sums, "hits_file_bytes": data, "classification_bytes": cb,
            "classification_sha256": hashlib.sha256(cb).hexdigest(), "final_replies": self.replies,
            "run_log": self.run_log(), "tool_calls": self.tool_calls(), "draws": DRAWS,
        }  # fmt: skip
        args.update(kw)
        return ev.analyse(**args)  # type: ignore[no-any-return]


@pytest.fixture
def lab(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Lab:
    return Lab(tmp_path, monkeypatch)


def first_chunk(lab: Lab, o: str) -> int:
    return next(ch["k"] for ch in lab.chunks if o in ch["karten"])


# ---------------------------------------------------------------- formula, aggregation (I2, I5)


def test_formula_v3b_v3c_and_corridor_by_hand() -> None:
    c = {"E": 80.0, "F": 60.0, "T": 40.0, "R": 50.0, "K": 20.0, "N": 50.0}
    # 0.3*80 + 0.3*60 + 0.2*50 + 0.1*40 + 0.1*20 = 24 + 18 + 10 + 4 + 2 = 58; minus 0.2*50 = 48
    assert ev.h_ref(c) == pytest.approx(48.0)
    assert ev.h_v3c(c) == pytest.approx(58.0)
    # V3c has no N: changing N changes V3b by -0.2 * dN and leaves V3c unchanged
    c2 = {**c, "N": 100.0}
    assert ev.h_v3c(c2) == pytest.approx(58.0)
    assert ev.h_ref(c2) == pytest.approx(38.0)
    # bounded to 0..100
    assert ev.h_ref({"E": 0.0, "F": 0.0, "T": 0.0, "R": 0.0, "K": 0.0, "N": 100.0}) == 0.0
    # corridor +/- 10
    assert ev.clamp_corridor(80.0, 48.0) == 58.0
    assert ev.clamp_corridor(30.0, 48.0) == 38.0
    assert ev.clamp_corridor(50.0, 48.0) == 50.0


def test_median_not_mean_and_median_before_formula() -> None:
    base = {"F": 50.0, "T": 50.0, "R": 50.0, "K": 50.0, "N": 0.0, "H": 50.0}
    per = {"A": {**base, "E": 10.0}, "B": {**base, "E": 20.0}, "C": {**base, "E": 90.0}}
    a = ev.aggregate(per)
    assert a["kriterien"]["E"] == 20.0  # median, the mean would be 40
    # median per criterion first: E 20, F/R/T/K 50 -> 6 + 15 + 10 + 5 + 5 = 41
    assert a["V3b"] == pytest.approx(41.0)
    # the other order (formula per rater, then median) differs on a crafted case
    per3 = {
        "A": {**base, "E": 90.0, "F": 0.0},
        "B": {**base, "E": 0.0, "F": 40.0},
        "C": {**base, "E": 40.0, "F": 90.0},
    }
    a3 = ev.aggregate(per3)
    # medians E 40, F 40 -> 12 + 12 + 10 + 5 + 5 = 44; per rater: 47, 32, 59 -> median 47
    assert a3["V3b"] == pytest.approx(44.0)
    assert statistics.median(ev.h_ref(v) for v in per3.values()) == pytest.approx(47.0)


def test_v3a_is_median_of_the_clamped_rater_values() -> None:
    base = {"E": 50.0, "F": 50.0, "T": 50.0, "R": 50.0, "K": 50.0, "N": 0.0}  # H_ref 50
    per = {"A": {**base, "H": 95.0}, "B": {**base, "H": 30.0}, "C": {**base, "H": 55.0}}
    a = ev.aggregate(per)
    assert a["V3a"] == 55.0  # clamped 60, 40, 55 -> median 55
    assert ev.aggregate({"A": per["A"], "B": per["B"]})["V3a"] == 50.0  # n_rater 2: mean of 60, 40


def test_n_rater_two_is_the_mean_and_one_is_no_value() -> None:
    base = {"E": 50.0, "F": 50.0, "T": 50.0, "R": 50.0, "K": 50.0, "N": 0.0, "H": 50.0}
    two = ev.aggregate({"A": {**base, "E": 40.0}, "B": {**base, "E": 70.0}})
    assert two["n_rater"] == 2 and two["kriterien"]["E"] == 55.0
    one = ev.aggregate({"A": base})
    assert one["n_rater"] == 1 and one["V3b"] is None and one["V3a"] is None and one["V3c"] is None


def test_icc_k_matches_the_wave2_icc_at_two_raters() -> None:
    rng = random.Random(3)
    pairs = [(float(rng.randint(0, 100)), 0.0) for _ in range(40)]
    pairs = [(a, a + rng.gauss(0, 8)) for a, _ in pairs]
    assert ev.icc21_k([list(p) for p in pairs]) == pytest.approx(
        ev.ev2.icc_set(pairs)["icc21"], abs=1e-12
    )


# ---------------------------------------------------------------- thresholds flip under mutation


def _icc_rows(n: int, sd_true: float, sd_err: float, seed: int) -> list[list[float]]:
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        t = rng.gauss(40, sd_true)
        out.append([t + rng.gauss(0, sd_err) for _ in range(3)])
    return out


def test_s1_point_threshold_flips(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = _icc_rows(600, 15.0, 6.3, 1)
    point = ev.icc21_k(rows)
    assert 0.80 < point < 0.87  # independent check: the synthetic ICC lies between both thresholds
    res = ev.s1(rows, DRAWS, blocked=False)
    assert res["ci95"][0] >= 0.80 and res["status"] == "verfehlt"
    monkeypatch.setattr(ev, "S1_POINT_MIN", 0.80)
    assert ev.s1(rows, DRAWS, blocked=False)["status"] == "erfuellt"


def test_s1_lower_bound_threshold_flips(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = _icc_rows(25, 15.0, 4.0, 5)
    res = ev.s1(rows, DRAWS, blocked=False)
    assert res["icc21"] >= 0.87 and res["ci95"][0] < 0.80 and res["status"] == "verfehlt"
    monkeypatch.setattr(ev, "S1_LOWER_MIN", res["ci95"][0] - 0.01)
    assert ev.s1(rows, DRAWS, blocked=False)["status"] == "erfuellt"


def test_s1_is_no_conclusion_when_a_rater_dropped_out() -> None:
    assert ev.s1(_icc_rows(90, 15, 2, 2), DRAWS, blocked=True)["status"] == "unbekannt"


def test_s2_threshold_flips(monkeypatch: pytest.MonkeyPatch) -> None:
    rows = [[10.0, 20.0, 30.0], [50.0, 50.0, 50.0], [90.0, 80.0, 70.0]]
    # mean |delta|: A-B (10+0+10)/3, A-C (20+0+20)/3, B-C (10+0+10)/3 -> (80/3) / 3 = 8.889; SD (pop.) of 9 values
    sd = statistics.pstdev([v for r in rows for v in r])
    res = ev.s2(rows)
    assert res["wert"] == pytest.approx((80 / 9) / sd)
    assert res["soll"] is True
    want = "erfuellt" if (80 / 9) / sd <= 0.39 else "verfehlt"
    assert res["status"] == want
    monkeypatch.setattr(ev, "S2_MAX", (80 / 9) / sd - 0.001)
    assert ev.s2(rows)["status"] == "verfehlt"


def _s3_rows(
    shift: float, land_shift: float = 0.0, seed: int = 5, noise: float = 3.0
) -> tuple[list[list[float]], list[str]]:
    rng = random.Random(seed)
    rows, kinds = [], []
    for i in range(90):
        kd = "kreatur" if i < 51 else ("nicht_kreatur" if i < 78 else "land")
        t = rng.gauss(40, 16)
        a = (
            t
            + rng.gauss(0, noise)
            + (shift if kd == "kreatur" else 0)
            + (land_shift if kd == "land" else 0)
        )
        rows.append([a, t + rng.gauss(0, noise), t + rng.gauss(0, noise)])
        kinds.append(kd)
    return rows, kinds


def _s3_z(rows: list[list[float]], kinds: list[str]) -> tuple[float, float]:
    d = [r[0] - r[1] for r in rows]
    ga = [x for x, k in zip(d, kinds, strict=True) if k == "kreatur"]
    gb = [x for x, k in zip(d, kinds, strict=True) if k == "nicht_kreatur"]
    c = statistics.fmean(ga) - statistics.fmean(gb)
    se = math.sqrt(statistics.variance(ga) / len(ga) + statistics.variance(gb) / len(gb))
    sd = statistics.pstdev([v for r in rows for v in r])
    return c / sd, abs(c) / se


def test_s3_sd_threshold_and_bonferroni_value_flip(monkeypatch: pytest.MonkeyPatch) -> None:
    rows, kinds = _s3_rows(shift=4.0, seed=46, noise=5.0)
    in_sd, z = _s3_z(rows, kinds)
    assert 1.96 < z < 2.50 and abs(in_sd) > 0.15  # significant without Bonferroni, not with it
    assert ev.s3(rows, kinds)["status"] == "erfuellt"
    monkeypatch.setattr(ev, "S3_CRIT", 1.96)
    assert ev.s3(rows, kinds)["status"] == "verfehlt"
    rows2, kinds2 = _s3_rows(shift=6.0)
    in_sd2, z2 = _s3_z(rows2, kinds2)
    assert z2 > 2.50 and abs(in_sd2) > 0.15
    monkeypatch.setattr(ev, "S3_CRIT", 2.50)
    assert ev.s3(rows2, kinds2)["status"] == "verfehlt"
    monkeypatch.setattr(ev, "S3_SD_MAX", abs(in_sd2) + 0.01)
    assert ev.s3(rows2, kinds2)["status"] == "erfuellt"


def test_s3_decides_only_on_creature_against_noncreature() -> None:
    rows, kinds = _s3_rows(shift=0.0, land_shift=15.0)
    res = ev.s3(rows, kinds)
    # a large land offset only shows in S3c (reported); with all 9 contrasts it would fail
    assert res["status"] == "erfuellt"
    assert res["paare"]["A-B"]["S3c_nur_berichtet"]["kreatur_gegen_land"]["auffaellig"] is True


def test_s4_share_threshold_and_corridor_breaks(monkeypatch: pytest.MonkeyPatch) -> None:
    # 20 cards per rater; rater A has 1 gross break (5 % -> ok), rater B has 2 (10 % -> failed)
    base = [(50.0, 50.0)] * 19
    recs = {
        "A": [*base, (70.0, 50.0)],
        "B": [*base[:18], (66.0, 50.0), (34.0, 50.0)],
        "C": [*base, (62.0, 50.0)],
    }
    res = ev.s4(recs)
    assert res["je_rater"]["A"]["status"] == "erfuellt"  # 1/20 = 5 % <= 5 %
    assert res["je_rater"]["B"]["status"] == "verfehlt"
    assert res["je_rater"]["C"]["grob_gt15"] == 0 and res["je_rater"]["C"]["bruch_gt10"] == 1
    assert res["status"] == "verfehlt"
    monkeypatch.setattr(ev, "S4_SHARE_MAX", 0.10)
    assert ev.s4(recs)["status"] == "erfuellt"
    monkeypatch.setattr(ev, "S4_SHARE_MAX", 0.05)
    monkeypatch.setattr(ev, "CORRIDOR_GROSS", 20.0)
    assert ev.s4(recs)["status"] == "erfuellt"


def test_s5_rule_example_from_the_plan_and_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    # Kor Skyfisher: anchor lines E 75 and R 75; medians E 70 and R 80 -> two terms with error 5
    terms = [
        {
            "aggregat": 70.0,
            "ankerwert": 75.0,
            "satz": "alt",
            "werte": {"A": 70.0, "B": 70.0, "C": 65.0},
        },
        {
            "aggregat": 80.0,
            "ankerwert": 75.0,
            "satz": "alt",
            "werte": {"A": 80.0, "B": 85.0, "C": 80.0},
        },
    ]
    res = ev.s5(terms)
    assert res["mae"] == 5.0 and res["n_terme"] == 2 and res["status"] == "erfuellt"
    monkeypatch.setattr(ev, "S5_MAE_MAX", 4.9)
    assert ev.s5(terms)["status"] == "verfehlt"


def _s6_rows(target_t: float, slope10: float) -> tuple[list[list[float]], list[list[float]]]:
    x = [float(i % 19 + 1) for i in range(90)]
    mx = statistics.fmean(x)
    u = [(-1.0) ** i * (1 + (i % 7)) for i in range(90)]
    for basis in ([1.0] * 90, [a - mx for a in x]):  # orthogonalise against constant and position
        bb = sum(b * b for b in basis)
        proj = sum(a * b for a, b in zip(u, basis, strict=True)) / bb
        u = [a - proj * b for a, b in zip(u, basis, strict=True)]
    b = slope10 / 10
    sxx = sum((a - mx) ** 2 for a in x)
    ssr = b * b * sxx * 88 / (target_t**2)
    scale = math.sqrt(ssr / sum(a * a for a in u))
    e = [b * (a - mx) + scale * w for a, w in zip(x, u, strict=True)]
    rows = [[50.0 + ei, 50.0, 50.0] for ei in e]  # median of (50 + e, 50, 50) is 50
    return rows, [[a, a, a] for a in x]


def test_s6_t_quantile_and_bonferroni(monkeypatch: pytest.MonkeyPatch) -> None:
    rows, pos = _s6_rows(target_t=2.42, slope10=2.0)
    res = ev.s6(rows, pos)
    assert res["je_rater"]["A"]["t"] == pytest.approx(2.42, abs=1e-6)
    assert res["je_rater"]["A"]["steigung_je_10"] == pytest.approx(2.0, abs=1e-9)
    # 2.42 is above the normal quantile 2.394 but below the t quantile 2.44: not failed
    assert res["status"] == "erfuellt"
    monkeypatch.setattr(ev, "S6_CRIT", 2.394)
    assert ev.s6(rows, pos)["status"] == "verfehlt"


def test_s6_slope_threshold_flips(monkeypatch: pytest.MonkeyPatch) -> None:
    rows, pos = _s6_rows(target_t=5.0, slope10=1.4)
    assert ev.s6(rows, pos)["status"] == "erfuellt"  # strongly significant but below 1.5 per 10
    monkeypatch.setattr(ev, "S6_SLOPE_MAX", 1.3)
    assert ev.s6(rows, pos)["status"] == "verfehlt"


def test_s7_thresholds_flip_and_missing_usage_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    rng = random.Random(9)
    pairs = []
    for _ in range(300):
        y = rng.gauss(0, 1)
        pairs.append((y + rng.gauss(0, 1.2), y + rng.gauss(0, 1.0), y))
    res = ev.s7(pairs, DRAWS, None, must=True)
    assert res["differenz"] is not None and res["ci95"][0] is not None
    assert res["status"] == (
        "erfuellt" if res["differenz"] >= -0.05 and res["ci95"][0] >= -0.15 else "verfehlt"
    )
    monkeypatch.setattr(ev, "S7_POINT_MIN", res["differenz"] + 0.001)
    assert ev.s7(pairs, DRAWS, None, must=True)["status"] == "verfehlt"
    monkeypatch.setattr(ev, "S7_POINT_MIN", -1.0)
    monkeypatch.setattr(ev, "S7_LOWER_MIN", res["ci95"][0] + 0.001)
    assert ev.s7(pairs, DRAWS, None, must=True)["status"] == "verfehlt"
    monkeypatch.setattr(ev, "S7_LOWER_MIN", res["ci95"][0] - 0.001)
    assert ev.s7(pairs, DRAWS, None, must=True)["status"] == "erfuellt"
    unk = ev.s7([], DRAWS, "usage_holdout.jsonl nicht angegeben", must=True)
    assert unk["status"] == "unbekannt" and unk["differenz"] is None and unk["n"] == 0


def test_s9_threshold_flips(monkeypatch: pytest.MonkeyPatch) -> None:
    rng = random.Random(2)
    table = []
    for _ in range(60):
        e = float(rng.randint(0, 100))
        table.append({"E": e, "F": e + rng.gauss(0, 8), "T": float(rng.randint(0, 100)), "R": float(rng.randint(0, 100)),
                      "K": float(rng.randint(0, 100)), "N": float(rng.randint(0, 100))})  # fmt: skip
    res = ev.s9(table, {})
    assert res["paar"] == "EF" and abs(res["max_r"]) >= 0.90 and res["status"] == "verfehlt"
    monkeypatch.setattr(ev, "S9_R_MAX", abs(res["max_r"]) + 0.001)
    assert ev.s9(table, {})["status"] == "erfuellt"


def test_s8_and_display_thresholds_flip_in_the_pipeline(
    lab: Lab, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab.note[("B", "n05", 1)] = "As in the previous rating."
    lab.build()
    _data, hits = lab.hits()
    assert len(hits) == 7  # one per criterion line note
    lab.counting = {hits[0]["id"]}
    res, _ = lab.eval()
    assert res["kriterien"]["V3b"]["S8"]["status"] == "verfehlt"
    assert res["kriterien"]["V3b"]["S8"]["zaehlende_treffer"] == 1
    monkeypatch.setattr(ev, "S8_MAX", 1)
    res2, _ = lab.eval()
    assert res2["kriterien"]["V3b"]["S8"]["status"] == "erfuellt"


# ---------------------------------------------------------------- pipeline: clean pilot and decision


def test_clean_pilot_meets_every_criterion_and_goes_to_the_full_run(lab: Lab) -> None:
    lab.build()
    res, rows = lab.eval()
    d = res["entscheidung"]
    assert d["muss"] == {s: "erfuellt" for s in ("S1", "S3", "S5", "S6", "S8", "S9")}
    assert d["ergebnis"] == "Vollauf"
    assert res["karten"]["nicht_anker_mit_drei_ratern"] == 90 and res["karten"]["N"] == 100
    # S7 without usage is unknown, never 0, and only an early warning in the pilot
    assert (
        res["kriterien"]["V3b"]["S7"]["status"] == "unbekannt"
        and res["kriterien"]["V3b"]["S7"]["differenz"] is None
    )
    assert d["fruehwarnung"]["V3b"]["S7"] == "unbekannt"
    assert len(rows) == 100 and all(r["n_rater"] == 3 for r in rows)
    assert (
        res["kriterien"]["V3a"]["S4"]["status"] == "erfuellt"
        and "S4" not in res["kriterien"]["V3b"]
    )


def test_pilot_decision_all_outcomes() -> None:
    def var(**st: str) -> dict[str, Any]:
        base = {
            s: {"status": "erfuellt"}
            for s in ("S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9")
        }
        base["anzeige_bedingung"] = {"status": "unbekannt"}
        for k, v in st.items():
            base[k] = {"status": v}
        return base

    ok = {v: var() for v in ("V3b", "V3a", "V3c")}
    assert ev.decide("pilot", 1, ok, [])["ergebnis"] == "Vollauf"
    # V3a and V3c never decide the pilot; S2 and S7 are early warnings only
    mixed = {
        "V3b": var(S2="verfehlt", S7="verfehlt"),
        "V3a": var(S1="verfehlt"),
        "V3c": var(S3="verfehlt"),
    }
    assert ev.decide("pilot", 1, mixed, [])["ergebnis"] == "Vollauf"
    bad = {**ok, "V3b": var(S6="verfehlt")}
    assert ev.decide("pilot", 1, bad, [])["ergebnis"].startswith("Anpassungsrunde")
    assert ev.decide("pilot", 2, bad, [])["ergebnis"] == "nicht erfuellt"
    unk = {**ok, "V3b": var(S5="unbekannt")}
    assert ev.decide("pilot", 1, unk, [])["ergebnis"] == "kein Schluss"
    assert ev.decide("pilot", 1, ok, ["A11"])["ergebnis"] == "kein Schluss"


def test_variant_choice_rank_order_and_display_condition() -> None:
    def var(**st: str) -> dict[str, Any]:
        base = {
            s: {"status": "erfuellt"}
            for s in ("S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "anzeige_bedingung")
        }
        for k, v in st.items():
            base[k] = {"status": v}
        return base

    assert (
        ev.decide("vollauf", None, {"V3b": var(), "V3a": var(), "V3c": var()}, [])["vorschlag"]
        == "V3b"
    )
    # V3b misses the display condition -> V3a; S4 decides only for V3a
    r = ev.decide(
        "vollauf",
        None,
        {"V3b": var(anzeige_bedingung="verfehlt", S4="verfehlt"), "V3a": var(), "V3c": var()},
        [],
    )
    assert r["vorschlag"] == "V3a"
    r = ev.decide(
        "vollauf",
        None,
        {"V3b": var(S7="verfehlt"), "V3a": var(S4="verfehlt"), "V3c": var(S4="verfehlt")},
        [],
    )
    assert r["vorschlag"] == "V3c"
    r = ev.decide(
        "vollauf",
        None,
        {
            "V3b": var(S1="verfehlt"),
            "V3a": var(S9="verfehlt"),
            "V3c": var(anzeige_bedingung="verfehlt"),
        },
        [],
    )
    assert r["vorschlag"] is None and r["ergebnis"] == "im Vollauf nicht bestaetigt"
    # S2 is never a Muss criterion
    assert (
        ev.decide("vollauf", None, {"V3b": var(S2="verfehlt"), "V3a": var(), "V3c": var()}, [])[
            "vorschlag"
        ]
        == "V3b"
    )
    r = ev.decide("vollauf", None, {"V3b": var(S7="unbekannt"), "V3a": var(), "V3c": var()}, [])
    assert r["vorschlag"] is None and r["ergebnis"].startswith("kein Schluss")
    assert (
        ev.decide("vollauf", None, {"V3b": var(), "V3a": var(), "V3c": var()}, ["A10"])["vorschlag"]
        is None
    )


def test_display_condition_threshold_in_the_pipeline(
    lab: Lab, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab.build()
    usage = lab.root / "usage.jsonl"
    pooled = lab.root / "pooled.jsonl"
    usage.write_text("".join(json.dumps({"oracle_id": o, "deck_list_count": i * 3 % 17}) + "\n"
                             for i, o in enumerate(sorted(lab.cards))), encoding="utf-8")  # fmt: skip
    pooled.write_text("".join(json.dumps({"oracle_id": o, "H_pooled": ev.h_ref({c: float(x) for c, x in lab.true[o].items()})}) + "\n"
                              for o in sorted(lab.cards)), encoding="utf-8")  # fmt: skip
    monkeypatch.setattr(ev, "USAGE_SHA256_PREFIX", _sha(usage)[:8])
    monkeypatch.setattr(ev, "POOLED_SHA256", _sha(pooled))
    res, _ = lab.eval(usage_path=usage, pooled_path=pooled)
    an = res["kriterien"]["V3b"]["anzeige_bedingung"]
    assert an["n"] == 100 and an["differenz"] is not None
    want = "erfuellt" if an["differenz"] >= -0.10 else "verfehlt"
    assert an["status"] == want
    monkeypatch.setattr(ev, "DISPLAY_LOSS_MIN", an["differenz"] + 0.001)
    res2, _ = lab.eval(usage_path=usage, pooled_path=pooled)
    assert res2["kriterien"]["V3b"]["anzeige_bedingung"]["status"] == "verfehlt"
    # S7 stays unknown without the old runs, never 0
    assert res2["kriterien"]["V3b"]["S7"]["status"] == "unbekannt"


def test_s7_uses_the_old_runs_under_the_same_definition(
    lab: Lab, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab.build()
    usage = lab.root / "usage.jsonl"
    old = lab.root / "pairs.jsonl"
    usage.write_text("".join(json.dumps({"oracle_id": o, "deck_list_count": lab.true[o]["E"]}) + "\n"
                             for o in sorted(lab.cards)), encoding="utf-8")  # fmt: skip
    rows = []
    for o in sorted(lab.cards):
        t = lab.true[o]
        row: dict[str, Any] = {"oracle_id": o}
        for run in ("F1", "R2"):
            row.update({f"{run}_{c}": t[c] for c in ("E", "F", "T", "R", "K")})
            row[f"{run}_D"] = 100 - t["N"]
            row[f"{run}_H"] = 30
        rows.append(row)
    old.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    monkeypatch.setattr(ev, "USAGE_SHA256_PREFIX", _sha(usage)[:8])
    monkeypatch.setattr(ev, "OLD_RUNS_SHA256_PREFIX", _sha(old)[:8])
    res, _ = lab.eval(usage_path=usage, old_runs_path=old)
    s7 = res["kriterien"]["V3b"]["S7"]
    assert s7["n"] == 90 and s7["muss"] is False
    # old runs equal the true criteria: V3b of new raters is close -> small difference
    assert abs(s7["differenz"]) < 0.05
    assert ev.old_same(rows[0], "V3a") == pytest.approx(
        ev.clamp_corridor(
            30.0, ev.h_ref({c: float(x) for c, x in lab.true[rows[0]["oracle_id"]].items()})
        )
    )
    bad = lab.root / "other.jsonl"
    bad.write_text("x\n", encoding="utf-8")
    with pytest.raises(ev.RefusedError, match="does not match the pin"):
        lab.eval(usage_path=bad, old_runs_path=old)


# ---------------------------------------------------------------- anchors


def test_s5_uses_only_the_first_placement(lab: Lab) -> None:
    o = "a0"
    ks = [ch["k"] for ch in lab.chunks if o in ch["karten"]]
    assert len(ks) >= 2
    for r in RATERS:  # the repeat placement is far off; the first one stays exact
        lab.values[(r, o, ks[1])]["E"] = clip5(
            lab.true[o]["E"] + 60 if lab.true[o]["E"] < 40 else lab.true[o]["E"] - 60
        )
    lab.build()
    res, _ = lab.eval()
    assert res["kriterien"]["V3b"]["S5"]["status"] == "erfuellt"
    assert res["anker"]["retest_wiederholungen"]["mae"] > 0


def test_s5_fails_when_the_first_placement_is_off(lab: Lab) -> None:
    for o in lab.anchors:
        k = first_chunk(lab, o)
        for r in RATERS:
            lab.values[(r, o, k)]["E"] = clip5(
                lab.true[o]["E"] + 25 if lab.true[o]["E"] < 50 else lab.true[o]["E"] - 25
            )
    lab.build()
    res, _ = lab.eval()
    assert res["kriterien"]["V3b"]["S5"]["status"] == "verfehlt"
    assert res["entscheidung"]["ergebnis"].startswith("Anpassungsrunde")


def test_anchor_strike_each_arm_separately() -> None:
    def term(vals: dict[str, float | None]) -> dict[str, Any]:
        return {
            "oracle_id": "x",
            "card": "X",
            "kriterium": "E",
            "satz": "alt",
            "ankerwert": 50.0,
            "werte": vals,
        }

    # arm 1 only: mean 61.67 > 10 away, but 2 of 3 within +/- 10 (60, 60)
    s = ev.anchor_strike([term({"A": 60.0, "B": 60.0, "C": 65.0})])[0]
    assert s["streichen"] and s["grund"] == ["mittel_gt10"] and s["rater_innerhalb_10"] == 2
    # arm 2 only: mean 50 but only 1 of 3 within +/- 10 (50); 30 and 70 are outside
    s = ev.anchor_strike([term({"A": 30.0, "B": 50.0, "C": 70.0})])[0]
    assert s["streichen"] and s["grund"] == ["weniger_als_2_von_3"]
    s = ev.anchor_strike([term({"A": 55.0, "B": 45.0, "C": 70.0})])[0]
    assert not s["streichen"] and s["grund"] == []
    # a missing rater counts as not within: 2 values, only 1 within
    s = ev.anchor_strike([term({"A": 50.0, "B": 65.0, "C": None})])[0]
    assert s["streichen"] and "weniger_als_2_von_3" in s["grund"]


# ---------------------------------------------------------------- validity, A-rules


def test_a4_only_marks_and_all_valid_rows_stay_in_the_criteria(lab: Lab) -> None:
    for o in lab.chunks[0]["karten"]:
        lab.values[("C", o, 1)] = {
            **lab.values[("C", o, 1)],
            "E": 50,
            "F": 50,
            "T": 50,
            "R": 50,
            "K": 50,
            "N": 0,
            "H": 50,
        }
    lab.build()
    res, rows = lab.eval()
    assert res["A4_skalenstauchung_nur_markiert"]["C:1"]["V3b"]["ausgeloest"] is True
    assert res["chargen"]["C:1"]["ausgeschlossen"] is False
    assert res["kriterien"]["V3b"]["S1"]["n"] == 90  # no result-dependent exclusion
    assert any("skalenstauchung" in r["marken"] for r in rows if r["charge"] == 1)


def test_invalid_card_and_rounding_and_n_rater_marks(lab: Lab) -> None:
    def drop_value(lines: list[str]) -> list[str]:
        obj = json.loads(lines[1])
        obj["value"] = "high"
        return [lines[0], json.dumps(obj), *lines[2:]]

    lab.line_hook[("A", 1)] = drop_value
    o_first = lab.chunks[0]["reihenfolge"]["A"][0]
    o_b = lab.chunks[0]["reihenfolge"]["B"][1]
    lab.values[("B", o_b, 1)]["E"] = (
        52  # not a multiple of 5 -> rounded half up to 50, counted (A5)
    )
    lab.build()
    res, rows = lab.eval()
    assert res["chargen"]["A:1"]["V_gueltig"] == [18, 19]
    assert res["chargen"]["A:1"]["nicht_gueltig"]["1"] == ["E: value"]
    assert res["chargen"]["B:1"]["nicht_vielfache_5_werte"] == 1
    row = next(r for r in rows if r["oracle_id"] == o_first)
    assert row["n_rater"] == 2 and "n_rater_2" in row["marken"]


def test_a11_and_a2_violation_in_two_chunks_drop_a_rater(lab: Lab) -> None:
    lab.tool_calls_extra = [
        {
            "instanz": "A:1",
            "werkzeug": "Read",
            "pfad": "/scratch/raters/A_10/out.jsonl",
        },  # neighbour folder
        {"instanz": "A:2", "werkzeug": "Bash", "pfad": "/scratch/raters/A_2/x"},  # tool not allowed
    ]
    lab.build()
    res, _ = lab.eval()
    assert res["A2"]["rater_ausgefallen"] == ["A"]
    assert res["kriterien"]["V3b"]["S1"]["status"] == "unbekannt"
    assert res["kriterien"]["V3b"]["S8"]["status"] == "verfehlt"
    assert res["A11"]["kein_schluss"] is True and res["entscheidung"]["ergebnis"] == "kein Schluss"
    scan = res["transkript_scan"]["instanzen"]
    assert scan["A:1"]["verstoesse"][0]["grund"] == "pfad_ausserhalb"
    assert scan["A:2"]["verstoesse"][0]["grund"] == "werkzeug"


def test_missing_transcript_invalidates_the_chunk_and_missing_scan_is_unknown(lab: Lab) -> None:
    lab.skip_files = {"v3_transcript_B_3.jsonl"}
    lab.build()
    res, _ = lab.eval()
    assert res["A2"]["je_instanz"]["B:3"]["transkript_fehlt"] is True
    assert res["chargen"]["B:3"]["ausgeschlossen"] is True
    assert res["kriterien"]["V3b"]["S8"]["status"] == "unbekannt"
    assert res["laufprotokoll"]["A3"] is True
    res2, _ = lab.eval(tool_calls=None)
    assert res2["kriterien"]["V3b"]["S8"]["status"] == "unbekannt"
    assert res2["kriterien"]["V3b"]["S8"]["werkzeug_verstoesse"] == 0


def test_path_check_uses_a_trailing_separator() -> None:
    assert ev.path_inside("/x/A_1/guide.md", "/x/A_1")
    assert not ev.path_inside("/x/A_10/guide.md", "/x/A_1")
    assert not ev.path_inside("../A_2/out.jsonl", "/x/A_1")
    assert ev.path_inside("sub/../guide.md", "/x/A_1")


def test_a3_without_run_log_and_a10_label(lab: Lab) -> None:
    lab.run_log_override = {"hashes_vor_oeffnen_gepostet": False}
    lab.build()
    res, _ = lab.eval()
    assert "explorativ, nicht nach Plan (A10)" in res["kennzeichnung"]
    assert res["entscheidung"]["ergebnis"] == "kein Schluss"
    res2, _ = lab.eval(run_log=None)
    assert res2["laufprotokoll"]["A3"] is True and "Stufen ungeprueft (A3)" in res2["kennzeichnung"]


# ---------------------------------------------------------------- hits, transcript scan, model ids


def test_hits_print_no_rating_even_from_an_invalid_raw_line(lab: Lab) -> None:
    def broken(lines: list[str]) -> list[str]:
        return [
            lines[0],
            '{"criterion": "E", "value": 73, "note": "previous run said 73"',
            *lines[2:],
        ]

    lab.line_hook[("C", 2)] = broken
    lab.note[("A", "n20", 2)] = "In the previous rating it was 85 points."
    lab.card_extra[("B", "n33", 3)] = {"reason": "The tier list puts it at 90."}
    lab.build()
    _data, hits = lab.hits()
    text = json.dumps(hits)
    assert {h["feld"] for h in hits} >= {"E.note", "reason"}
    assert any(h["feld"].startswith("rohzeile") for h in hits)
    for number in ("73", "85", "90"):
        assert number not in text
    assert '"value"' not in text
    assert "#" in next(h["satz"] for h in hits if h["feld"] == "reason")


def test_transcript_scan_never_prints_the_write_content(lab: Lab) -> None:
    lab.build()
    res, _ = lab.eval()
    assert "SECRET-WRITE" not in json.dumps(res)
    assert res["kriterien"]["V3b"]["S8"]["status"] == "erfuellt"


def test_no_model_id_in_any_output(lab: Lab) -> None:
    lab.build()
    out = lab.root / "out"
    out.mkdir()
    data, _ = lab.hits()
    (out / "hits.json").write_bytes(data)
    cb = lab.classification()
    (out / "cls.json").write_bytes(cb)
    (out / "replies.json").write_text(json.dumps(lab.replies), encoding="utf-8")
    (out / "log.json").write_text(json.dumps(lab.run_log()), encoding="utf-8")
    (out / "tools.json").write_text(json.dumps(lab.tool_calls()), encoding="utf-8")
    base = ["--manifest", str(lab.manifest), "--inputs-dir", str(lab.inputs), "--rater-dir", str(lab.rater),
            "--checksums", str(lab.sums)]  # fmt: skip
    gate = ["--final-replies", str(out / "replies.json"), "--hits", str(out / "hits.json"),
            "--classification", str(out / "cls.json"), "--classification-sha256", hashlib.sha256(cb).hexdigest()]  # fmt: skip
    assert (
        ev.main(
            [
                "hits",
                *base,
                "--final-replies",
                str(out / "replies.json"),
                "--out",
                str(out / "h2.json"),
            ]
        )
        == 0
    )
    assert (
        ev.main(["claims", *base, "--out", str(out / "c.json"), "--key-out", str(out / "ck.json")])
        == 0
    )
    assert (
        ev.main(
            [
                "adjudicate",
                *base,
                *gate,
                "--out",
                str(out / "a.json"),
                "--key-out",
                str(out / "ak.json"),
            ]
        )
        == 0
    )
    lab.mp.setattr(ev, "DRAWS", 50)
    assert ev.main(["eval", *base, *gate, "--run-log", str(out / "log.json"), "--tool-calls", str(out / "tools.json"),
                    "--out", str(out / "r.json"), "--report", str(out / "r.md"), "--h-out", str(out / "h.jsonl"),
                    "--sums-out", str(out / "S")]) == 0  # fmt: skip
    produced = [
        "h2.json",
        "c.json",
        "ck.json",
        "a.json",
        "ak.json",
        "r.json",
        "r.md",
        "h.jsonl",
        "S",
    ]
    assert all((out / n).exists() for n in produced)
    assert not [n for n in produced if SENTINEL in (out / n).read_text(encoding="utf-8")]


# ---------------------------------------------------------------- freeze guard and refusals


def test_freeze_guard_refusals(lab: Lab) -> None:
    lab.build()
    extra = lab.rater / "v3_output_A_9.jsonl"
    extra.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ev.RefusedError, match="no output, transcript or meta file"):
        lab.hits()
    extra.unlink()
    out = lab.rater / "v3_output_B_2.jsonl"
    keep = out.read_bytes()
    out.write_bytes(keep + b"\n")
    with pytest.raises(ev.RefusedError, match="differs from the last frozen hash"):
        lab.hits()
    out.unlink()
    with pytest.raises(ev.RefusedError, match="listed as frozen but missing"):
        lab.hits()
    out.write_bytes(keep)
    sums = lab.sums.read_text(encoding="utf-8")
    lab.sums.write_text(
        "".join(x + "\n" for x in sums.splitlines() if "v3_output_B_2" not in x), encoding="utf-8"
    )
    with pytest.raises(ev.RefusedError, match="present but not frozen"):
        lab.hits()
    lab.sums.write_text(sums, encoding="utf-8")
    (lab.inputs / "v3_guide_3.md").write_text("changed\n", encoding="utf-8")
    with pytest.raises(ev.RefusedError, match="inputs differ from the manifest"):
        lab.hits()


def test_manifest_must_be_pinned(lab: Lab) -> None:
    lab.build()
    lab.mp.delitem(ev.PINNED_MANIFEST_SHA256, "pilot")
    with pytest.raises(ev.RefusedError, match="no pinned manifest"):
        lab.hits()
    lab.mp.setitem(ev.PINNED_MANIFEST_SHA256, "pilot", "0" * 64)
    with pytest.raises(ev.RefusedError, match="!= pinned"):
        lab.hits()


def test_eval_refuses_without_the_posted_classification(lab: Lab) -> None:
    lab.build()
    cb = lab.classification()
    with pytest.raises(ev.RefusedError, match="posted in #1404"):
        lab.eval(classification_bytes=cb, classification_sha256="0" * 64)
    with pytest.raises(ev.RefusedError, match="hits file differs"):
        lab.eval(hits_file_bytes=b"{}")
    wrong = json.dumps(
        {"hits_sha256": "0" * 64, "github_kommentar": "x", "einstufung": {}}
    ).encode()
    with pytest.raises(ev.RefusedError, match="hits_sha256"):
        lab.eval(classification_bytes=wrong)
    replies = dict(lab.replies)
    replies.pop("C:6")
    short, _, _ = ev.run_hits(lab.manifest, lab.inputs, lab.rater, lab.sums, replies)
    with pytest.raises(ev.RefusedError, match="no final reply"):
        lab.eval(final_replies=replies, hits_file_bytes=short)


def test_cli_refuses_without_classification_file(
    lab: Lab, capsys: pytest.CaptureFixture[str]
) -> None:
    lab.build()
    rc = ev.main(["eval", "--manifest", str(lab.manifest), "--inputs-dir", str(lab.inputs), "--rater-dir", str(lab.rater),
                  "--checksums", str(lab.sums), "--hits", str(lab.root / "h.json"), "--classification", str(lab.root / "none.json"),
                  "--classification-sha256", "0" * 64, "--out", str(lab.root / "r.json"), "--report", str(lab.root / "r.md"),
                  "--h-out", str(lab.root / "h.jsonl"), "--sums-out", str(lab.root / "S")])  # fmt: skip
    assert rc == 2 and "classification file missing" in capsys.readouterr().err


def test_repeat_freeze_needs_prior_violations_in_the_run_log(lab: Lab) -> None:
    lab.build()
    name = "v3_output_A_1.jsonl"
    lab.sums.write_text(
        f"{'1' * 64}  {name}\n" + lab.sums.read_text(encoding="utf-8"), encoding="utf-8"
    )
    log = lab.run_log()
    del log["instanzen"]["A:1"]["a2_verstoesse_frueher"]
    with pytest.raises(ev.RefusedError, match="frozen more than once"):
        lab.eval(run_log=log)


# ---------------------------------------------------------------- adjudication (I6)


def _spread_card(lab: Lab) -> str:
    o = "n10"
    lab.values[("A", o, 1)] = {**lab.values[("A", o, 1)], "E": 100, "F": 100, "R": 100}
    lab.values[("C", o, 1)] = {**lab.values[("C", o, 1)], "E": 0, "F": 0, "R": 0}
    return o


def test_adjudication_after_the_criteria_and_marks(lab: Lab) -> None:
    o = _spread_card(lab)
    lab.build()
    base, _ = lab.eval()
    _, _, (man, _, _, data) = ev.run_hits(
        lab.manifest, lab.inputs, lab.rater, lab.sums, lab.replies
    )
    items, key = ev.adjudication_list(
        man, data, ev.card_ratings(man, data, {r: set() for r in RATERS})
    )
    assert [i["oracle_id"] for i in items] == [o]
    assert "rater" not in json.dumps(items)  # no rater identity in the blind list
    nr_a = next(nr for nr, r in key[o].items() if r == "A")
    kb = ev.dumps({"schema": "rating-v3-adjudikation-schluessel-1", "schluessel": key}).encode()
    verdicts = {o: {nr_a: {"objektiver_fehler": True, "zitat": "Oracle text: draw a card"}}}
    res, rows = lab.eval(adjudication_key_bytes=kb, adjudication_verdicts=verdicts)
    # S criteria are computed before the adjudication: identical with and without it
    assert res["kriterien"] == base["kriterien"]
    row = next(r for r in rows if r["oracle_id"] == o)
    assert (
        "adjudiziert" in row["marken"] and "abstand_ge15" in row["marken"] and row["n_rater"] == 2
    )
    assert row["H_v3b"] != row["H_v3b_vor_adjudikation"]
    assert res["adjudikation"]["befund_stufe_rater_A_ueber_rater_A"] == 1
    with pytest.raises(ev.RefusedError, match="verbatim quote"):
        lab.eval(
            adjudication_key_bytes=kb,
            adjudication_verdicts={o: {nr_a: {"objektiver_fehler": True, "zitat": " "}}},
        )
    with pytest.raises(ev.RefusedError, match="key differs"):
        lab.eval(adjudication_key_bytes=b"{}", adjudication_verdicts=verdicts)


def test_rule_claim_sample_is_one_per_card_and_blind(lab: Lab) -> None:
    lab.build()
    blind_b, key_b = ev.run_claims(lab.manifest, lab.inputs, lab.rater, lab.sums)
    blind, key = json.loads(blind_b), json.loads(key_b)
    assert len(blind["claims"]) == 60
    assert Counter_of([k["rater"] for k in key["schluessel"]]) == {"A": 20, "B": 20, "C": 20}
    assert len({k["oracle_id"] for k in key["schluessel"]}) == 60
    assert "rater" not in json.dumps(blind)
    verdicts = {
        str(k["nr"]): ("falsch" if k["rater"] == "B" and k["nr"] % 2 else "korrekt")
        for k in key["schluessel"]
    }
    g = ev.grade_claims(key["schluessel"], verdicts)
    assert (
        g["A"]["stufe"] == "gruen"
        and g["B"]["stufe"] == "rot"
        and g["B"]["sensitivitaet_leave_one_rater_out"]
    )


def Counter_of(xs: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for x in xs:
        out[x] = out.get(x, 0) + 1
    return out


# ---------------------------------------------------------------- full run, determinism


def test_full_run_chunks_and_version_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = Lab(tmp_path, monkeypatch, phase="vollauf")
    lab.build()
    log = lab.run_log()
    log["instanzen"]["B:5"]["version"] = SENTINEL + "-v2"
    res, _ = lab.eval(run_log=log)
    assert res["laufprotokoll"]["A9_versionswechsel"]["B"] is True
    assert res["entscheidung"]["phase"] == "vollauf"
    assert res["entscheidung"]["ergebnis"].startswith("kein Schluss")  # S7 unknown without usage
    assert res["kriterien"]["V3b"]["S7"]["muss"] is True
    assert set(res["A9"]["tranchen"]["A"]) == {"1", "2"}


def test_two_runs_are_byte_identical(lab: Lab) -> None:
    lab.build()
    out = lab.root / "o"
    out.mkdir()
    data, _ = lab.hits()
    (out / "hits.json").write_bytes(data)
    cb = lab.classification()
    (out / "cls.json").write_bytes(cb)
    (out / "replies.json").write_text(json.dumps(lab.replies), encoding="utf-8")
    (out / "log.json").write_text(json.dumps(lab.run_log()), encoding="utf-8")
    (out / "tools.json").write_text(json.dumps(lab.tool_calls()), encoding="utf-8")
    lab.mp.setattr(ev, "DRAWS", 60)
    blobs = []
    for i in (1, 2):
        args = ["eval", "--manifest", str(lab.manifest), "--inputs-dir", str(lab.inputs), "--rater-dir", str(lab.rater),
                "--checksums", str(lab.sums), "--final-replies", str(out / "replies.json"), "--hits", str(out / "hits.json"),
                "--classification", str(out / "cls.json"), "--classification-sha256", hashlib.sha256(cb).hexdigest(),
                "--run-log", str(out / "log.json"), "--tool-calls", str(out / "tools.json"),
                "--out", str(out / f"r{i}.json"), "--report", str(out / f"r{i}.md"), "--h-out", str(out / f"h{i}.jsonl"),
                "--sums-out", str(out / f"S{i}")]  # fmt: skip
        assert ev.main(args) == 0
        blobs.append(
            tuple(
                (out / f"{n}{i}{e}").read_bytes()
                for n, e in (("r", ".json"), ("r", ".md"), ("h", ".jsonl"))
            )
        )
    assert blobs[0] == blobs[1]
    assert len(blobs[0][0]) > 1000
