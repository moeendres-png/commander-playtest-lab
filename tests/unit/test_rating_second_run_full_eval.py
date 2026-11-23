"""Tests of the wave-2 evaluation script (Refs #1404) with synthetic data only.

No real rater output is read: every run folder is built in ``tmp_path`` (7 pool chunks of 6 cards,
retest chunk 8 of 4 cards, wave 1 of 3 files x 4 cards; 54 cards). Expected values are hand
calculations next to the assertions. The tests cover the mandatory red/green tests of plan
section 9 step 4 and one test per rule A1 to A11.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import random
import statistics
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2] / "scripts" / "analysis" / "rating_second_run_full_eval.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("rating_second_run_full_eval", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["rating_second_run_full_eval"] = module
    spec.loader.exec_module(module)
    return module


ev = _load()
CRIT = ("E", "F", "T", "R", "K", "D", "H")
GUIDE = (
    "# Guide\n\nThe commander (exact Oracle text):\n> Whenever you cast a creature spell, draw a card.\n\n"
    "Anchors.\n"
)
CHUNK_STRATA = ("top20", "rest", "rest", "rest", "anchor_spell", "anchor_land")
W1_STRATA = ("top20", "rest", "land", "flagged")
N_SYN = 7 * 6 + 3 * 4


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def oid(prefix: str, i: int, j: int) -> str:
    return f"{prefix}-{i}-{j}"


def out_row(o: str, name: str, h: int, *, text: str = "Plain text about the card.", sub: int | None = None,
            claim: str = "draws a card", quote: str = "draw a card") -> dict[str, Any]:  # fmt: skip
    s = sub if sub is not None else h
    return {
        "schema": "rubric-v2-card-rating-1", "oracle_id": o, "card": name, "judged_as": "spell",
        "scores": {"E": s, "F": s, "T": s, "R": s, "K": s, "D": s, "H": h},
        "notes": {k: text for k in CRIT}, "reason": text, "confidence": "high", "uncertainty": "",
        "rule_claims": [{"quote": quote, "interaction": "other", "claim": claim, "basis": "card_text"}],
        "pattern_check": [],
    }  # fmt: skip


class Lab:
    """A synthetic run: F1 H of every card, R2 H per card (None = no output line)."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.rater = root / "rater"
        self.w1dir = root / "wave1"
        self.rater.mkdir()
        self.w1dir.mkdir()
        self.cards: dict[str, dict[str, Any]] = {}
        for k in range(1, 8):
            for j, st in enumerate(CHUNK_STRATA, 1):
                o = oid("c", k, j)
                self.cards[o] = {"name": f"Card {k}-{j}", "chunk": k, "seq": j, "stratum": st,
                                 "is_land": st == "anchor_land", "is_anchor": st.startswith("anchor"), "wave": 2}  # fmt: skip
        for f in (1, 2, 3):
            for j, st in enumerate(W1_STRATA, 1):
                o = oid("w", f, j)
                self.cards[o] = {"name": f"Old {f}-{j}", "file": f, "seq": j, "stratum": st,
                                 "is_land": st == "land", "is_anchor": False, "wave": 1}  # fmt: skip
        self.f1 = {o: 20 + 10 * (c["seq"] - 1) for o, c in self.cards.items()}  # 20 .. 70
        self.r2: dict[str, int | None] = {o: h - 5 for o, h in self.f1.items()}  # d = -5 everywhere
        self.retest: dict[str, int | None] = {
            o: self.f1[o] - 5
            for o in (oid("w", 1, 1), oid("w", 2, 1), oid("w", 3, 1), oid("w", 1, 2))
        }
        self.overrides: dict[str, dict[str, Any]] = {}
        self.raw_lines: dict[tuple[int, int], str] = {}
        self.write_chunk8 = True
        self.final_replies: dict[str, str] = {
            str(k): "Done; read only the allowed files." for k in range(1, 9)
        }
        self.run_log: dict[str, Any] = {
            "laufprotokoll_vorhanden": True, "dateizugriff_protokolliert": True,
            "familie_R2_gegen_F1": "andere", "familie_R2_gegen_G1": "andere",
            "gleiche_modell_id_und_stufe_wie_welle1": "ja", "retest_charge_8_gelaufen": True,
            "skript_vor_oeffnen_committet": True, "hashes_vor_oeffnen_gepostet": True,
        }  # fmt: skip
        self.g1_ids = [oid("c", k, 1) for k in range(1, 8)] + [oid("w", 1, 1)]
        self.f2_ids = [oid("c", 1, 2)]
        self.g1: dict[str, int] = {}  # G1 H per card; default = F1

    def row_for(self, o: str, h: int | None) -> str | None:
        if h is None:
            return None
        c = self.cards[o]
        row = out_row(o, c["name"], h)
        row.update(self.overrides.get(o, {}))
        return json.dumps(row)

    def build(self) -> None:
        man_cards = []
        per_chunk = {}
        for k in range(1, 9):
            if k < 8:
                ids = sorted(
                    (o for o, c in self.cards.items() if c.get("chunk") == k),
                    key=lambda o: self.cards[o]["seq"],
                )
            else:
                ids = list(self.retest)
            inp = self.rater / f"rr2_input_{k}.jsonl"
            inp.write_text("".join(json.dumps({"seq": i, "oracle_id": o, "card": self.cards[o]["name"],
                                               "card_block": f"Name: {self.cards[o]['name']}\nOracle text: draw a card"}) + "\n"
                                   for i, o in enumerate(ids, 1)), encoding="utf-8")  # fmt: skip
            guide = self.rater / f"rr2_guide_{k}.md"
            guide.write_text(GUIDE, encoding="utf-8")
            per_chunk[str(k)] = {"input_sha256": _sha(inp), "guide_sha256": _sha(guide)}
            lines = []
            for i, o in enumerate(ids, 1):
                if (k, i) in self.raw_lines:
                    lines.append(self.raw_lines[(k, i)])
                    continue
                line = self.row_for(o, self.r2[o] if k < 8 else self.retest[o])
                if line is not None:
                    lines.append(line)
            if k < 8 or self.write_chunk8:
                (self.rater / f"rr2_output_{k}.jsonl").write_text(
                    "".join(x + "\n" for x in lines), encoding="utf-8"
                )
            for i, o in enumerate(ids, 1):
                c = self.cards[o]
                man_cards.append({"oracle_id": o, "name": c["name"], "stratum": c["stratum"] if k < 8 else "rest",
                                  "chunk": k, "seq": i, "is_land": c["is_land"], "is_anchor_card": c["is_anchor"]})  # fmt: skip
        self.manifest = self.root / "rr2_manifest.json"
        self.manifest.write_text(
            json.dumps({"meta": {"per_chunk": per_chunk}, "cards": man_cards}), encoding="utf-8"
        )
        w1cards = []
        for f in (1, 2, 3):
            ids = [oid("w", f, j) for j in range(1, 5)]
            (self.w1dir / f"rr_input_{f}.jsonl").write_text("".join(
                json.dumps({"seq": i, "oracle_id": o, "card": self.cards[o]["name"], "card_block": "x"}) + "\n"
                for i, o in enumerate(ids, 1)), encoding="utf-8")  # fmt: skip
            (self.w1dir / f"rr_output_{f}.jsonl").write_text("".join(
                (self.row_for(o, self.r2[o]) or "") + "\n" for o in ids), encoding="utf-8")  # fmt: skip
            for i, o in enumerate(ids, 1):
                c = self.cards[o]
                w1cards.append({"oracle_id": o, "name": c["name"], "stratum": c["stratum"], "input_file": f, "seq": i,
                                "is_land": c["is_land"], "is_anchor_card": False})  # fmt: skip
        (self.w1dir / "rr_sample_manifest.json").write_text(
            json.dumps({"cards": w1cards}), encoding="utf-8"
        )
        self.w1_hashes = {
            f"rr_output_{f}.jsonl": _sha(self.w1dir / f"rr_output_{f}.jsonl") for f in (1, 2, 3)
        }

        def ratings(path: Path, hs: dict[str, int]) -> Path:
            path.write_text("".join(json.dumps({"oracle_id": o, "card": self.cards[o]["name"], "reason": "old reason",
                                                "scores": {k: h for k in CRIT},
                                                "rule_claims": [{"quote": "draw a card", "interaction": "other",
                                                                 "claim": f"first-run claim for {o}", "basis": "card_text"}]})
                                    + "\n" for o, h in sorted(hs.items())), encoding="utf-8")  # fmt: skip
            return path

        self.f1_path = ratings(self.root / "f1.jsonl", self.f1)
        self.g1_path = ratings(
            self.root / "g1.jsonl", {o: self.g1.get(o, self.f1[o]) for o in self.g1_ids}
        )
        self.f2_path = ratings(self.root / "f2.jsonl", {o: self.f1[o] for o in self.f2_ids})
        self.refs = {
            "manifest": _sha(self.manifest), "f1": _sha(self.f1_path), "g1": _sha(self.g1_path),
            "f2": _sha(self.f2_path), "wave1_manifest": _sha(self.w1dir / "rr_sample_manifest.json"),
            **{f"wave1_input_{f}": _sha(self.w1dir / f"rr_input_{f}.jsonl") for f in (1, 2, 3)},
        }  # fmt: skip
        self.sums = self.root / "sums.txt"
        self.sums.write_text(
            "".join(
                f"{_sha(p)}  {p.name}\n" for p in sorted(self.rater.glob("rr2_output_*.jsonl"))
            ),
            encoding="utf-8",
        )

    def hits(self) -> tuple[bytes, list[dict[str, Any]]]:
        data, hits, _, _ = ev.run_hits(self.manifest, self.rater, self.sums, self.final_replies)
        return data, hits

    def classification(self, counting: set[str] | None = None) -> dict[str, Any]:
        data, hits = self.hits()
        counting = counting or set()
        return {"hits_sha256": hashlib.sha256(data).hexdigest(), "github_kommentar": "#1404 comment 1",
                "einstufung": {h["id"]: ({"zaehlt": True, "buchstabe": None} if h["id"] in counting
                                         else {"zaehlt": False, "buchstabe": "a"}) for h in hits}}  # fmt: skip

    def run(
        self,
        draws: int = 40,
        counting: set[str] | None = None,
        cls: Any = None,
        tier: Any = None,
        cls_sha: str | None = None,
        verdicts: Any = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        data, _ = self.hits()
        raw = json.dumps(cls if cls is not None else self.classification(counting)).encode()
        return ev.analyse(  # type: ignore[no-any-return]
            manifest_path=self.manifest, rater_dir=self.rater, checksums_path=self.sums,
            classification_bytes=raw, classification_sha256=cls_sha or hashlib.sha256(raw).hexdigest(),
            hits_file_bytes=data, run_log=self.run_log, final_replies=self.final_replies, wave1_dir=self.w1dir,
            f1_path=self.f1_path, g1_path=self.g1_path, f2_path=self.f2_path, tier_rule=tier,
            claim_verdicts=verdicts, draws=draws,
        )  # fmt: skip


@pytest.fixture
def lab(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Lab:
    lab = Lab(tmp_path)
    monkeypatch.setattr(ev, "N_POOL", N_SYN)
    orig_build = lab.build

    def build() -> None:
        orig_build()
        monkeypatch.setattr(ev, "WAVE1_OUTPUT_SHA256", lab.w1_hashes)
        monkeypatch.setattr(ev, "REFERENCE_SHA256", lab.refs)

    lab.build = build  # type: ignore[method-assign]
    return lab


def by_id(pooled: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {p["oracle_id"]: p for p in pooled}


# ---------------------------------------------------------------- mandatory test (a): one rating


def test_pool_card_means_only_with_two_ratings() -> None:
    assert ev.pool_card(40, 35) == (37.5, 2)
    assert ev.pool_card(40, None) == (40.0, 1)


def test_card_with_only_one_valid_rating_keeps_f1_count_one_and_mark(lab: Lab) -> None:
    bad = oid("c", 2, 2)
    lab.overrides[bad] = {"oracle_id": "wrong-id"}  # invalid line (plan section 3)
    lab.r2[oid("c", 3, 2)] = None  # missing line: the chunk then has 5 lines
    lab.raw_lines[(3, 2)] = "{not json"
    lab.build()
    _, pooled = lab.run()
    p = by_id(pooled)[bad]
    # F1 = 30, R2 = 25 would mean 27.5; a single valid rating keeps F1
    assert p["H_pooled"] == 30.0 and p["n_bewertungen"] == 1 and p["H_R2"] is None
    assert p["marken"][0] == "nur_erstbewertung" and p["grund_nur_erstbewertung"] == "ungueltig"
    q = by_id(pooled)[oid("c", 3, 2)]
    assert q["H_pooled"] == 30.0 and q["n_bewertungen"] == 1 and "nur_erstbewertung" in q["marken"]
    ok = by_id(pooled)[oid("c", 2, 1)]
    assert ok["H_pooled"] == 17.5 and ok["n_bewertungen"] == 2 and ok["quelle_R2"] == "welle2:2"


# ---------------------------------------------------------------- mandatory test (b): -3.0 threshold


def _tight(b: float, n: int = 30) -> list[float]:
    # values b-1, b, b+1 repeated: mean b, tiny spread, so the interval sits well below 0 for b < -1
    return [b + (i % 3) - 1 for i in range(n)]


def test_spells_threshold_minus_three_on_b_minus_two() -> None:
    clusters = {k: _tight(-2.0) for k in range(1, 8)}
    res = ev.spells_test(clusters, [], draws=300)
    assert res["b_W2"] == pytest.approx(-2.0)
    assert res["ci95_cluster"][1] < 0
    # -3.0 < b = -2: "kleiner bestaetigt" (a mutant with -1.0 would say "bestaetigt")
    assert res["verdict"] == "kleiner bestaetigt"
    assert (
        ev.spells_test({k: _tight(-4.0) for k in range(1, 8)}, [], draws=300)["verdict"]
        == "bestaetigt"
    )
    assert ev.spells_verdict(-3.0, -0.5, 7, 7, []) == "bestaetigt"  # b <= -3.0 includes -3.0


def test_spells_test_m_minus_one_of_m_and_no_conclusion_below_six() -> None:
    base = {k: _tight(-6.0) for k in range(1, 8)}
    one_pos = {**base, 7: _tight(+2.0)}
    two_pos = {**base, 6: _tight(+2.0), 7: _tight(+2.0)}
    r7 = ev.spells_test(one_pos, [], draws=300)
    assert (r7["m"], r7["chunks_negative"], r7["needed_negative"]) == (7, 6, 6)
    assert r7["verdict"] == "bestaetigt"  # 6 of 7 is enough (a mutant needing 7 of 7 fails)
    assert ev.spells_test(two_pos, [], draws=300)["verdict"] == "nicht bestaetigt"  # 5 of 7
    six = {k: v for k, v in one_pos.items() if k != 1}
    r6 = ev.spells_test(six, [], draws=300)
    assert (r6["m"], r6["chunks_negative"]) == (6, 5) and r6["verdict"] == "bestaetigt"
    five = {k: base[k] for k in range(1, 6)}
    r5 = ev.spells_test(five, [], draws=300)
    assert r5["m"] == 5 and r5["verdict"] == "kein Schluss" and "A11" in r5["blockers"]


def test_cluster_bootstrap_resamples_chunks_not_only_cards() -> None:
    # chunk means -10, -9, -8, -7, +5, +6, +7 (mean -2.29), each chunk tight (sd < 1)
    means = [-10, -9, -8, -7, 5, 6, 7]
    clusters = [[mu + (i % 3) - 1 for i in range(40)] for mu in means]
    flat = [x for c in clusters for x in c]
    cl = ev.cluster_bootstrap(clusters, draws=500)
    card = ev.card_bootstrap_mean(flat, draws=500)
    assert card[1] < 0  # a card bootstrap says "below 0"
    assert cl[0] < 0 < cl[1]  # the cluster interval includes 0
    res = ev.spells_test(dict(enumerate(clusters, 1)), [], draws=500)
    assert res["verdict"] == "nicht bestaetigt"
    # b <= -3 and 6 of 7 chunks below 0, but one chunk carries the bias: the cluster interval
    # reaches above 0 ("nicht bestaetigt"); a card bootstrap would wrongly say "bestaetigt"
    carried = {
        k: [mu + (i % 3) - 1 for i in range(39)]
        for k, mu in enumerate([-25, -1, -1, -1, -1, -1, 5], 1)
    }
    r = ev.spells_test(carried, [], draws=500)
    assert r["b_W2"] == pytest.approx(-25 / 7) and r["chunks_negative"] == 6
    assert r["ci95_card_descriptive"][1] < 0 <= r["ci95_cluster"][1]
    assert r["verdict"] == "nicht bestaetigt"


def test_cluster_bootstrap_is_deterministic() -> None:
    clusters = [[1.0, 2.0, 3.0], [-1.0, 0.0], [4.0]]
    assert ev.cluster_bootstrap(clusters, draws=200) == ev.cluster_bootstrap(clusters, draws=200)


# ---------------------------------------------------------------- freeze guard


def test_freeze_guard_refuses_unlisted_changed_or_missing_outputs(tmp_path: Path) -> None:
    out = tmp_path / "rr2_output_1.jsonl"
    out.write_text("x\n", encoding="utf-8")
    good = hashlib.sha256(b"x\n").hexdigest()
    assert ev.freeze_guard(tmp_path, {"rr2_output_1.jsonl": [good]}) == {1: good}
    # several hashes for one name (A2 repeat, A1 resume) are allowed; only the LAST one counts
    assert ev.freeze_guard(tmp_path, {"rr2_output_1.jsonl": ["0" * 64, good]}) == {1: good}
    with pytest.raises(ev.RefusedError, match="last frozen"):
        ev.freeze_guard(tmp_path, {"rr2_output_1.jsonl": [good, "0" * 64]})
    with pytest.raises(ev.RefusedError, match="not frozen"):
        ev.freeze_guard(tmp_path, {})
    with pytest.raises(ev.RefusedError, match="differs"):
        ev.freeze_guard(tmp_path, {"rr2_output_1.jsonl": ["0" * 64]})
    with pytest.raises(ev.RefusedError, match="missing"):
        ev.freeze_guard(tmp_path, {"rr2_output_1.jsonl": [good], "rr2_output_2.jsonl": [good]})
    with pytest.raises(ev.RefusedError, match="no wave-2 output"):
        ev.freeze_guard(tmp_path, {"rr2_output_1.jsonl": [good], "other.jsonl": [good]})
    (tmp_path / "rr2_output_9.jsonl").write_text("extra\n", encoding="utf-8")
    with pytest.raises(ev.RefusedError, match=r"rr2_output_9\.jsonl"):
        ev.freeze_guard(tmp_path, {"rr2_output_1.jsonl": [good]})


def test_eval_cli_refuses_unlisted_output_file_in_rater_dir(lab: Lab) -> None:
    """An extra rr2_output_*.jsonl file (such as rr2_output_9.jsonl) in rater_dir must fail
    freeze_guard and exit with rc != 0 (Refs #1765)."""
    lab.build()
    (lab.rater / "rr2_output_9.jsonl").write_text("extra\n", encoding="utf-8")
    with pytest.raises(ev.RefusedError, match=r"rr2_output_9\.jsonl"):
        lab.hits()
    rc = ev.main(
        [
            "hits",
            "--manifest",
            str(lab.root / "manifest.json"),
            "--rater-dir",
            str(lab.rater),
            "--checksums",
            str(lab.root / "checksums.txt"),
            "--out",
            str(lab.root / "hits.json"),
        ]
    )
    assert rc != 0


def test_parse_checksums_reads_sha256sum_format() -> None:
    text = f"{'a' * 64}  rr2_output_1.jsonl\n{'b' * 64} *dir/rr2_output_1.jsonl\n\n"
    assert ev.parse_checksums(text) == {"rr2_output_1.jsonl": ["a" * 64, "b" * 64]}
    with pytest.raises(ev.RefusedError):
        ev.parse_checksums("abc rr2_output_1.jsonl")


def test_hits_and_eval_refuse_a_changed_output(lab: Lab) -> None:
    lab.build()
    cls = lab.classification()
    data, _ = lab.hits()
    (lab.rater / "rr2_output_3.jsonl").write_text("changed\n", encoding="utf-8")
    with pytest.raises(ev.RefusedError, match="freeze guard"):
        lab.hits()
    with pytest.raises(ev.RefusedError, match="freeze guard"):
        lab.run(cls=cls)
    assert data


def test_eval_refuses_changed_wave1_output_and_changed_inputs(lab: Lab) -> None:
    lab.build()
    (lab.w1dir / "rr_output_2.jsonl").write_text("x\n", encoding="utf-8")
    with pytest.raises(ev.RefusedError, match="wave-1 output"):
        lab.run()
    (lab.rater / "rr2_input_4.jsonl").write_text("x\n", encoding="utf-8")
    with pytest.raises(ev.RefusedError, match="manifest"):
        lab.hits()


# ---------------------------------------------------------------- stage 1: hits


def test_hits_list_only_reference_hits_without_scores(lab: Lab) -> None:
    target = oid("c", 4, 3)
    lab.overrides[target] = {
        "reason": "Strong card. My previous rating was higher. It draws.",
        "rule_claims": [{"quote": "the previous turn", "interaction": "other", "claim": "see the tier list", "basis": "card_text"}],
    }  # fmt: skip
    lab.r2[target] = 85
    lab.final_replies = {"5": "Done, no audit files read."}
    lab.build()
    data, hits = lab.hits()
    text = data.decode()
    assert [(h["charge"], h["seq"], h["feld"], h["treffer"]) for h in hits] == [
        (4, 3, "reason", "previous"),
        (4, 3, "rule_claims[0].claim", "tier list"),
        (5, 0, "schlussantwort", "audit"),
    ]
    assert hits[0]["satz"] == "My previous rating was higher."
    assert hits[0]["card"] == "Card 4-3" and hits[0]["id"] == "4:3:reason:16"
    # never a score, never F1, never the quote field (header hashes may contain any digits)
    assert '"scores"' not in text and '"H"' not in text and "the previous turn" not in text
    assert "85" not in json.dumps(hits) and "H_F1" not in text and '"d"' not in text


def test_hits_scan_unparsable_line_with_scores_blanked(lab: Lab) -> None:
    lab.raw_lines[(2, 2)] = '{"scores": {"H": 85}, "H": 85, "reason": "per the earlier rating" '
    lab.build()
    _, hits = lab.hits()
    assert [(h["feld"], h["treffer"]) for h in hits] == [("rohzeile", "earlier rating")]
    assert "85" not in json.dumps(hits)


def test_reference_regex_is_the_plan_list() -> None:
    assert ev.EARLIER.pattern == r"earlier rating|previous|\bv1\b|\bF1\b|audit|tier ?list"
    assert ev.EARLIER.flags & 2  # re.IGNORECASE


def test_sentence_at_finds_the_sentence() -> None:
    t = "One. Two has v1 inside! Three?"
    assert ev.sentence_at(t, t.index("v1")) == "Two has v1 inside!"
    assert ev.sentence_at("no end v1", 7) == "no end v1"


# ---------------------------------------------------------------- classification gate


def test_eval_requires_a_matching_classification(lab: Lab) -> None:
    lab.overrides[oid("c", 1, 2)] = {"reason": "Unlike the previous version, fine."}
    lab.build()
    good = lab.classification()
    with pytest.raises(ev.RefusedError, match="hits_sha256"):
        lab.run(cls={**good, "hits_sha256": "0" * 64})
    with pytest.raises(ev.RefusedError, match="ids differ"):
        lab.run(cls={**good, "einstufung": {}})
    hid = next(iter(good["einstufung"]))
    with pytest.raises(ev.RefusedError, match="letter"):
        lab.run(cls={**good, "einstufung": {hid: {"zaehlt": False, "buchstabe": None}}})
    with pytest.raises(ev.RefusedError, match="comment"):
        lab.run(cls={**good, "github_kommentar": ""})
    lab.run(cls=good)


def test_main_refuses_without_classification_file(
    lab: Lab, capsys: pytest.CaptureFixture[str]
) -> None:
    lab.build()
    hits_path = lab.root / "hits.json"
    common = [
        "--manifest",
        str(lab.manifest),
        "--rater-dir",
        str(lab.rater),
        "--checksums",
        str(lab.sums),
    ]
    assert ev.main(["hits", *common, "--out", str(hits_path)]) == 0
    rc = ev.main(["eval", *common, "--out", str(lab.root / "r.json"), "--classification", str(lab.root / "none.json"),
                  "--classification-sha256", "0" * 64,
                  "--hits", str(hits_path), "--wave1-dir", str(lab.w1dir), "--f1", str(lab.f1_path),
                  "--g1", str(lab.g1_path), "--f2", str(lab.f2_path), "--report", str(lab.root / "r.txt"),
                  "--pooled-out", str(lab.root / "p.jsonl")])  # fmt: skip
    assert rc == 2 and "VERWEIGERT" in capsys.readouterr().err
    assert not (lab.root / "r.json").exists()


# ---------------------------------------------------------------- A1 to A11


def test_a1_chunk_below_90_percent_flags_and_pools_the_valid_lines(lab: Lab) -> None:
    lab.r2[oid("c", 5, 6)] = None  # 5 of 6 lines = 83 % < 90 %
    lab.build()
    res, pooled = lab.run()
    assert res["chargen"]["5"]["A1_unter_90_prozent"] is True
    assert res["chargen"]["5"]["V1_gueltig"] == [5, 6]
    assert res["chargen"]["4"]["A1_unter_90_prozent"] is False
    assert by_id(pooled)[oid("c", 5, 1)]["n_bewertungen"] == 2
    assert by_id(pooled)[oid("c", 5, 6)]["grund_nur_erstbewertung"] == "fehlt"


def test_a1g_threshold_is_830_of_922_and_blocks_conclusions(lab: Lab) -> None:
    assert ev.a1g_threshold(922) == 830
    for k in (1, 2, 3, 4, 5, 6):  # 6 missing lines of 54 -> 48 pairs < ceil(0.9 * 54) = 49
        lab.r2[oid("c", k, 6)] = None
    lab.build()
    res, _ = lab.run()
    assert (
        res["paare"]["n"] == 48 and res["paare"]["schwelle"] == 49 and res["paare"]["A1g"] is True
    )
    assert (
        res["spells_test"]["verdict"] == "kein Schluss" and "A1g" in res["spells_test"]["blockers"]
    )
    assert res["B1"]["urteil"].startswith("kein Schluss")
    assert res["B2_G1"]["urteil"] == "kein Schluss (A1g)"
    assert res["vorschlag"]["anzeige_vorschlag_erlaubt"] is False


def test_a2_counting_hit_excludes_the_chunk(lab: Lab) -> None:
    lab.overrides[oid("c", 3, 2)] = {"reason": "Uses the earlier rating of this card as a start."}
    lab.build()
    _, hits = lab.hits()
    res, pooled = lab.run(counting={hits[0]["id"]})
    assert res["gueltige_chargen"]["ausgeschlossen"] == {"3": "A2_verstoss"}
    assert res["gueltige_chargen"]["m"] == 6 and res["A2"]["abbruch"] is False
    for j in range(1, 7):
        p = by_id(pooled)[oid("c", 3, j)]
        assert (
            p["n_bewertungen"] == 1
            and p["grund_nur_erstbewertung"] == "charge_ausgeschlossen:A2_verstoss"
        )
    # a non-counting classification of the same hit keeps the chunk
    res2, _ = lab.run()
    assert res2["gueltige_chargen"]["m"] == 7


def test_a2_violations_in_two_chunks_abort_wave2(lab: Lab) -> None:
    lab.run_log["chargen"] = {"6": {"a2_verstoesse_frueher": 1}}  # earlier, moved-away violation
    lab.overrides[oid("c", 3, 2)] = {"reason": "Same as the F1 value."}
    lab.build()
    _, hits = lab.hits()
    res, pooled = lab.run(counting={hits[0]["id"]})
    assert res["A2"] == {"verstoss_chargen": [3, 6], "abbruch": True}
    assert res["gueltige_chargen"]["m"] == 0
    assert all(p["n_bewertungen"] == 1 for p in pooled if p["quelle_R2"].startswith("welle2"))
    assert res["spells_test"]["verdict"] == "kein Schluss"


def test_a2_second_violation_in_the_same_chunk(lab: Lab) -> None:
    lab.run_log["chargen"] = {
        "3": {"a2_verstoesse_frueher": 1, "blindheitsverstoss_protokoll": True}
    }
    lab.build()
    res, _ = lab.run()
    assert res["gueltige_chargen"]["ausgeschlossen"] == {"3": "A2_zweiter_verstoss"}
    assert res["A2"]["abbruch"] is False  # only one chunk


def test_a3_missing_run_log_is_strict(lab: Lab) -> None:
    lab.run_log = {}
    lab.build()
    res, pooled = lab.run()
    assert res["laufprotokoll"]["A3"] is True and res["laufprotokoll"]["A10"] is True
    assert res["B2_G1"]["urteil"].startswith("unbelegt")
    assert any("A3" in x for x in res["kennzeichnung"])
    assert any(p["n_bewertungen"] == 2 for p in pooled)  # pooling stays allowed


def test_a3w_unknown_model_id_reports_per_wave(lab: Lab) -> None:
    lab.run_log["gleiche_modell_id_und_stufe_wie_welle1"] = "unbekannt"
    lab.build()
    res, _ = lab.run()
    assert res["laufprotokoll"]["A3w"] is True and any("A3w" in x for x in res["kennzeichnung"])
    assert res["streuung"]["welle1"]["n"] == 12 and res["streuung"]["welle2"]["n"] == 42
    assert res["B1"]["welle1"]["n"] == 12 and res["B1"]["welle2"]["n"] == 42


def test_a4_scale_compression() -> None:
    f1 = [10.0, 30.0, 50.0, 70.0, 90.0]
    # population SD of f1 = 28.28; 0.6 x = 16.97
    ok = ev.scale_compression(f1, [5.0, 25.0, 50.0, 75.0, 95.0])
    assert ok["triggered"] is False
    squeezed = ev.scale_compression(f1, [30.0, 40.0, 50.0, 60.0, 70.0])  # SD 14.14 < 16.97
    assert squeezed["sd_r2"] == pytest.approx(statistics.pstdev([30, 40, 50, 60, 70]))
    assert squeezed["triggered"] is True
    # 2 of 5 = 40 % equal values is not more than 40 %; 3 of 5 is
    assert ev.scale_compression(f1, [5.0, 5.0, 50.0, 75.0, 95.0])["triggered"] is False
    assert ev.scale_compression(f1, [5.0, 5.0, 5.0, 75.0, 95.0])["triggered"] is True


def test_a4_excluded_chunk_is_not_pooled(lab: Lab) -> None:
    for j in range(1, 7):
        lab.f1[oid("c", 2, j)] = 10 * j
        lab.r2[oid("c", 2, j)] = 40  # all equal: 100 % same H_R2
    lab.build()
    res, pooled = lab.run()
    assert res["gueltige_chargen"]["ausgeschlossen"] == {"2": "A4_skalenstauchung"}
    assert (
        by_id(pooled)[oid("c", 2, 1)]["grund_nur_erstbewertung"]
        == "charge_ausgeschlossen:A4_skalenstauchung"
    )


def test_a5_format_errors_and_half_up_rounding(lab: Lab) -> None:
    lab.overrides[oid("c", 6, 1)] = {
        "scores": {"E": 37, "F": 40, "T": 40, "R": 40, "K": 40, "D": 40, "H": 37}
    }
    lab.build()
    res, pooled = lab.run()
    # 1 of 6 lines = 16.7 % > 5 %
    assert (
        res["chargen"]["6"]["A5_formatfehler"] == [1, 6]
        and res["chargen"]["6"]["A5_ausgeloest"] is True
    )
    assert res["chargen"]["6"]["V3_vielfache_von_5"] == [5, 6]
    p = by_id(pooled)[oid("c", 6, 1)]
    assert p["H_R2"] == 35.0 and p["H_pooled"] == 27.5  # 37 -> 35 (F1 20); half up: 37.5 -> 40
    assert ev.w1.round5(37.5) == 40


def test_a6_chunk_effect_over_four_points() -> None:
    base = {k: [-5.0, -5.0] for k in range(1, 7)}
    eff = ev.chunk_effect({**base, 7: [-9.0, -9.0]})  # gap exactly 4: not more than 4
    assert eff["7"]["gap_means"] == pytest.approx(-4.0) and eff["7"]["auffaellig"] is False
    eff2 = ev.chunk_effect({**base, 7: [-9.5, -9.5]})
    assert eff2["7"]["auffaellig"] is True and eff2["1"]["auffaellig"] is False


def test_a6_flagged_chunk_stays_pooled_with_mark(lab: Lab) -> None:
    for j in range(1, 7):
        lab.r2[oid("c", 7, j)] = lab.f1[oid("c", 7, j)] - 15  # d = -15 against -5 elsewhere
    lab.build()
    res, pooled = lab.run()
    assert res["A6_auffaellige_chargen"] == [7]
    p = by_id(pooled)[oid("c", 7, 1)]
    assert p["n_bewertungen"] == 2 and "charge_auffaellig" in p["marken"]


def test_a7_interruptions_are_reported_and_a1_still_applies(lab: Lab) -> None:
    lab.run_log["chargen"] = {"4": {"abbrueche_a7": 2, "nachlauf_a1": True}}
    lab.r2[oid("c", 4, 6)] = None
    lab.build()
    res, _ = lab.run()
    assert (
        res["chargen"]["4"]["A7_abbrueche"] == 2
        and res["chargen"]["4"]["A1_nachlauf_protokolliert"] is True
    )
    assert res["chargen"]["4"]["A1_unter_90_prozent"] is True


def test_a8_thresholds_are_fixed_constants_and_not_options() -> None:
    assert (
        ev.A1_VALID_SHARE,
        ev.A1G_SHARE,
        ev.A4_SD_RATIO,
        ev.A4_MODE_SHARE,
        ev.A5_FORMAT_SHARE,
    ) == (0.9, 0.9, 0.6, 0.4, 0.05)
    assert (ev.A6_CHUNK_GAP, ev.A9_WAVE_GAP, ev.SPELL_BIAS_THRESHOLD, ev.MIN_VALID_CHUNKS) == (
        4.0,
        3.0,
        -3.0,
        6,
    )
    assert (ev.FLAG_GE15, ev.FLAG_GE30, ev.SEED, ev.DRAWS) == (15, 30, 20261124, 5000)
    assert (ev.SEED_CLAIMS, ev.CLAIMS_PER_ORIGIN, ev.CLAIM_GREEN_MAX, ev.CLAIM_RED_MIN) == (
        20261125,
        50,
        2,
        5,
    )
    sub = next(a for a in ev.build_parser()._actions if a.dest == "cmd")
    for name in ("hits", "eval"):
        opts = {o for act in sub.choices[name]._actions for o in act.option_strings}
        assert not {
            o for o in opts if any(w in o for w in ("draw", "seed", "thresh", "schwelle", "min"))
        }, opts


def test_a8_listed_deviation_labels_and_blocks_k1(lab: Lab) -> None:
    lab.run_log["a8_abweichungen"] = ["Menge geaendert"]
    lab.build()
    res, _ = lab.run()
    assert any("A8" in x for x in res["kennzeichnung"])
    assert any("A8" in x for x in res["vorschlag"]["K1_gruende_dagegen"])


def test_a9_wave_effect() -> None:
    w1d = [-5.0 + (i % 3) - 1 for i in range(60)]
    eff = ev.wave_effect(w1d, [-1.0 + (i % 3) - 1 for i in range(60)], draws=300)
    assert eff["diff"] == pytest.approx(4.0) and eff["welleneffekt"] is True
    small = ev.wave_effect(w1d, [-3.0 + (i % 3) - 1 for i in range(60)], draws=300)
    assert small["diff"] == pytest.approx(2.0) and small["welleneffekt"] is False


def test_a10_unconfirmed_order_marks_explorative_and_blocks_k1(lab: Lab) -> None:
    lab.run_log.pop("hashes_vor_oeffnen_gepostet")
    for o, c in lab.cards.items():
        if c["wave"] == 2 and not c["is_land"]:
            lab.r2[o] = lab.f1[o] - 10  # d = -10 on every wave-2 spell -> "bestaetigt"
    lab.build()
    res, _ = lab.run(draws=200)
    assert res["spells_test"]["verdict"] == "bestaetigt"
    assert any("A10" in x for x in res["kennzeichnung"])
    assert (
        res["vorschlag"]["K1_vorschlag_erlaubt"] is False
        and "A10" in res["vorschlag"]["K1_gruende_dagegen"]
    )


def test_a11_fewer_than_six_valid_chunks(lab: Lab) -> None:
    for k in (1, 2):
        for j in range(1, 7):
            lab.r2[oid("c", k, j)] = 40  # all equal -> A4 excludes chunks 1 and 2
            lab.f1[oid("c", k, j)] = 10 * j
    lab.build()
    res, _ = lab.run()
    assert res["gueltige_chargen"]["m"] == 5
    assert (
        res["spells_test"]["verdict"] == "kein Schluss" and "A11" in res["spells_test"]["blockers"]
    )
    assert res["streuung"]["charge"]["3"]["n"] == 6  # other figures over the valid chunks


# ---------------------------------------------------------------- further plan rules


def test_deviation_marks_flag_and_never_delete(lab: Lab) -> None:
    assert ev.deviation_marks(14.9) == [] and ev.deviation_marks(-15) == ["abweichung_ge15"]
    assert ev.deviation_marks(30) == ["abweichung_ge15", "abweichung_ge30"]
    lab.r2[oid("c", 1, 2)] = 60  # F1 30, d = +30
    lab.build()
    res, pooled = lab.run()
    p = by_id(pooled)[oid("c", 1, 2)]
    assert p["H_pooled"] == 45.0 and p["H_F1"] == 30.0 and p["H_R2"] == 60.0
    assert "abweichung_ge30" in p["marken"] and len(pooled) == N_SYN
    listed = res["abweichungen_ge15"]
    assert [x["card"] for x in listed] == ["Card 1-2"] and listed[0][
        "begruendung_F1"
    ] == "old reason"


def test_retest_chunk_8_is_never_pooled(lab: Lab) -> None:
    lab.retest[oid("w", 1, 1)] = 90
    lab.build()
    res, pooled = lab.run()
    p = by_id(pooled)[oid("w", 1, 1)]
    assert p["quelle_R2"] == "welle1:1" and p["H_R2"] == 15.0 and p["H_pooled"] == 17.5
    b3 = res["B3_retest"]
    assert b3["berechnet"] is True and b3["n"] == 4
    assert b3["urteil"].startswith("nur beschreibend")


def test_b3_not_computed_when_retest_did_not_run(lab: Lab) -> None:
    lab.write_chunk8 = False
    lab.run_log["retest_charge_8_gelaufen"] = False
    lab.build()
    res, _ = lab.run()
    assert res["B3_retest"]["berechnet"] is False


def test_b2_decides_only_with_another_family(lab: Lab) -> None:
    lab.build()
    res, _ = lab.run(draws=200)
    # G1 = F1 on 8 cards, pooled = F1 - 2.5 -> Delta = 0 - 2.5 = -2.5, interval [-2.5, -2.5]
    assert (
        res["B2_G1"]["delta_K0"] == pytest.approx(-2.5) and res["B2_G1"]["urteil"] == "schlechter"
    )
    lab.run_log["familie_R2_gegen_G1"] = "gleich"
    res2, _ = lab.run(draws=200)
    assert res2["B2_G1"]["urteil"] == "unbelegt (Uebereinstimmung mit einem Lauf derselben Familie)"
    assert res2["F2_beschreibend"]["urteil"] == "nur beschreibend"


def test_spread_formulas() -> None:
    ds = [-10.0, 0.0, 10.0]
    st = ev.d_stats(ds)
    sd = statistics.stdev(ds)  # 10
    assert st["sigma1"] == pytest.approx(sd / math.sqrt(2)) and st["se_pooled"] == pytest.approx(
        sd / 2
    )
    assert st["rms"] == pytest.approx(math.sqrt(200 / 3)) and st["sigma1_rms"] == pytest.approx(
        math.sqrt(200 / 3) / math.sqrt(2)
    )
    assert st["n_ge15"] == 0 and st["max_abs"] == 10


def test_chunk_variance_component() -> None:
    # means -5 and -1 (Var of means = 8); within: Var(-6,-4)=2, /2 = 1; Var(-2,0)=2, /2 = 1 -> 8 - 1 = 7
    assert ev.chunk_variance({1: [-6.0, -4.0], 2: [-2.0, 0.0]}) == pytest.approx(7.0)
    assert ev.chunk_variance({1: [-5.0, -5.0], 2: [-5.0, -5.0]}) == 0.0
    assert ev.chunk_variance({1: [1.0, 2.0]}) is None


def test_icc_set_matches_wave1_icc_and_spearman_brown() -> None:
    rng = random.Random(1)
    pairs = [(float(a), float(a + rng.choice((-10, -5, 0, 5)))) for a in range(0, 100, 5)]
    s = ev.icc_set(pairs)
    assert s["icc21"] == pytest.approx(ev.w1.icc21(pairs))
    # for k = 2, ICC(2,2) is the Spearman-Brown step-up of ICC(2,1)
    assert s["icc22"] == pytest.approx(s["spearman_brown"])
    assert s["icc31"] >= s["icc21"] - 1e-9


def test_format_gaps_are_only_counted(lab: Lab) -> None:
    lab.overrides[oid("c", 1, 1)] = {
        "scores": {"E": 80, "F": 80, "T": 80, "R": 80, "K": 80, "D": 80, "H": 15}
    }
    lab.overrides[oid("c", 1, 2)] = {
        "scores": {"E": 5, "F": 5, "T": 5, "R": 5, "K": 5, "D": 5, "H": 35}
    }
    lab.overrides[oid("c", 1, 3)] = {
        "scores": {"E": 65, "F": 65, "T": 65, "R": 65, "K": 65, "D": 65, "H": 40}
    }
    lab.overrides[oid("c", 1, 4)] = {
        "scores": {"E": 20, "F": 20, "T": 20, "R": 20, "K": 20, "D": 20, "H": 45}
    }  # 45 - 20 = 25 above the mean: not more than 25
    lab.build()
    res, pooled = lab.run()
    fl = res["chargen"]["1"]["formatluecken_H_gt25_vom_mittel"]
    # 80 - 15 = 65 > 25 (below), 35 - 5 = 30 > 25 (above), 65 - 40 = 25 is not more than 25;
    # H_R2 15, 35, 40, 45, 55, 65 are distinct, so A4 does not exclude the chunk
    assert (fl["H_ueber_mittel"], fl["H_unter_mittel"], fl["N_gueltig"]) == (1, 1, 6)
    assert by_id(pooled)[oid("c", 1, 1)]["n_bewertungen"] == 2  # not a validity criterion


def test_unknown_is_never_zero(lab: Lab) -> None:
    lab.build()
    res, _ = lab.run()
    assert res["K0_aenderungen"]["stufe_wechsel"] == "unbekannt"
    assert ev.fmt(None) == "unbekannt" and ev.fmt(0.0) == "0,00"
    assert ev.clean(float("nan")) is None
    text = ev.report(res)
    assert "unbekannt" in text and "NaN" not in text


def test_tier_rule_changes_are_counted(lab: Lab) -> None:
    lab.build()
    rule = {
        "datei": "rule.json",
        "commit": "abc",
        "stufen": [{"name": "A", "min_h": 40}, {"name": "B", "min_h": 0}],
    }
    res, _ = lab.run(tier=rule)
    # pooled = F1 - 2.5: the 10 cards with F1 40 (seq 3 in 7 chunks and 3 files) drop from A to B
    ch = res["K0_aenderungen"]
    assert ch["stufe_wechsel"]["tiefer"] == 10 and ch["stufe_wechsel"]["hoeher"] == 0
    # band: F1 30 -> 27.5 (28-49 -> 5-27) and F1 50 -> 47.5 (50-71 -> 28-49): 10 + 10
    assert ch["band_tiefer"] == 20 and ch["band_hoeher"] == 0
    assert ch["seite50_nach_unten"] == 10 and ch["seite50_nach_oben"] == 0
    assert res["K0_aenderungen"]["stufe_wechsel"]["regel_commit"] == "abc"


def test_main_is_byte_identical_over_two_runs(lab: Lab, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        ev, "DRAWS", 300
    )  # speed only; the plan value 5000 is checked in the A8 test
    lab.r2[oid("c", 2, 3)] = 60
    lab.build()
    hits_path = lab.root / "hits.json"
    common = [
        "--manifest",
        str(lab.manifest),
        "--rater-dir",
        str(lab.rater),
        "--checksums",
        str(lab.sums),
    ]
    replies = lab.root / "replies.json"
    replies.write_text(json.dumps(lab.final_replies), encoding="utf-8")
    common += ["--final-replies", str(replies)]
    assert ev.main(["hits", *common, "--out", str(hits_path)]) == 0
    cls_path = lab.root / "cls.json"
    cls_path.write_text(json.dumps(lab.classification()), encoding="utf-8")
    cls_sha = _sha(cls_path)
    log_path = lab.root / "log.json"
    log_path.write_text(json.dumps(lab.run_log), encoding="utf-8")
    outs = []
    for i in (1, 2):
        files = [lab.root / f"r{i}.json", lab.root / f"r{i}.txt", lab.root / f"p{i}.jsonl"]
        rc = ev.main(["eval", *common, "--out", str(files[0]), "--classification", str(cls_path), "--hits", str(hits_path),
                      "--classification-sha256", cls_sha,
                      "--run-log", str(log_path), "--wave1-dir", str(lab.w1dir), "--f1", str(lab.f1_path),
                      "--g1", str(lab.g1_path), "--f2", str(lab.f2_path), "--report", str(files[1]),
                      "--pooled-out", str(files[2])])  # fmt: skip
        assert rc == 0
        outs.append([f.read_bytes() for f in files])
    assert outs[0] == outs[1]
    result = json.loads(outs[0][0])
    assert result["herkunft"]["draws"] == 300 and result["herkunft"]["seed"] == 20261124
    assert str(lab.root) not in outs[0][0].decode()  # base names only
    pooled = [json.loads(x) for x in outs[0][2].decode().splitlines()]
    assert len(pooled) == N_SYN and {p["n_bewertungen"] for p in pooled} == {2}


def test_bootstrap_multi_draws_like_the_wave1_bootstrap() -> None:
    groups = [[1.0, 2.0, 7.0], [-3.0, 4.0]]
    ours = ev.bootstrap_multi(groups, lambda s: {"m": sum(s) / len(s)}, ("m",), draws=200)
    theirs = ev.w1.bootstrap(groups, {"m": lambda s: sum(s) / len(s)}, draws=200, seed=ev.SEED)
    assert ours["m"] == list(theirs["m"])


# ---------------------------------------------------------------- review round 1 (#1763)


def test_hits_scan_fields_in_unexpected_form(lab: Lab) -> None:
    lab.overrides[oid("c", 2, 1)] = {
        "notes": "Copied from the earlier rating and the F1 tier list."
    }
    lab.overrides[oid("c", 2, 3)] = {"rule_claims": ["earlier rating said high"]}
    lab.overrides[oid("c", 2, 4)] = {"comment": "see audit"}  # key outside the schema
    lab.build()
    _, hits = lab.hits()
    got = {(h["seq"], h["feld"], h["treffer"]) for h in hits if h["charge"] == 2}
    assert (1, "notes", "earlier rating") in got and (1, "notes", "F1") in got
    assert (1, "notes", "tier list") in got
    assert (3, "rule_claims[0]", "earlier rating") in got
    assert (4, "zusatzfeld.comment", "audit") in got
    # an invalid line (notes not an object) is also scanned as raw text; seq 3 stays valid (plan
    # section 3 does not check rule_claims), its claim string is scanned as a field
    assert (1, "rohzeile", "earlier rating") in got and (3, "rohzeile", "earlier rating") not in got


def test_eval_refuses_without_final_reply_of_a_present_chunk(lab: Lab) -> None:
    lab.final_replies.pop("4")
    lab.build()
    data, _ = lab.hits()
    assert json.loads(data)["schlussantwort_gescannt"]["4"] is False
    with pytest.raises(ev.RefusedError, match="final reply"):
        lab.run()


def test_refrozen_output_needs_the_earlier_a2_count(lab: Lab) -> None:
    lab.build()
    old = "f" * 64
    lab.sums.write_text(
        f"{old}  rr2_output_3.jsonl\n" + lab.sums.read_text(encoding="utf-8"), encoding="utf-8"
    )
    with pytest.raises(ev.RefusedError, match="a2_verstoesse_frueher"):
        lab.run()
    lab.run_log["chargen"] = {"3": {"a2_verstoesse_frueher": 1}}
    lab.overrides[oid("c", 5, 2)] = {"reason": "Same as the earlier rating."}
    lab.build()
    lab.sums.write_text(
        f"{old}  rr2_output_3.jsonl\n" + lab.sums.read_text(encoding="utf-8"), encoding="utf-8"
    )
    _, hits = lab.hits()
    res, _ = lab.run(counting={hits[0]["id"]})
    assert res["A2"] == {"verstoss_chargen": [3, 5], "abbruch": True}
    assert res["spells_test"]["verdict"] == "kein Schluss"


def test_missing_a7_count_is_unknown_not_zero(lab: Lab) -> None:
    lab.build()
    res, _ = lab.run()
    assert res["chargen"]["4"]["A7_abbrueche"] == "unbekannt"


def test_moved_away_output_cannot_be_put_back(lab: Lab) -> None:
    lab.build()
    path = lab.rater / "rr2_output_3.jsonl"
    old_bytes = path.read_bytes()
    old = _sha(path)
    path.write_text(
        path.read_text(encoding="utf-8").replace("Plain text", "Other text"), encoding="utf-8"
    )
    lab.sums.write_text(
        lab.sums.read_text(encoding="utf-8") + f"{_sha(path)}  rr2_output_3.jsonl\n",
        encoding="utf-8",
    )
    assert old in lab.sums.read_text(encoding="utf-8")
    lab.hits()  # the re-run (last hash) passes
    path.write_bytes(old_bytes)  # putting the earlier frozen version back
    with pytest.raises(ev.RefusedError, match="last frozen"):
        lab.hits()


def test_reference_inputs_are_pinned(lab: Lab) -> None:
    lab.build()
    lab.f1_path.write_text(
        lab.f1_path.read_text(encoding="utf-8").replace('"H": 40', '"H": 0'), encoding="utf-8"
    )
    with pytest.raises(ev.RefusedError, match="f1"):
        lab.run()
    assert set(ev.REFERENCE_SHA256) == {
        "manifest", "f1", "g1", "f2", "wave1_manifest", "wave1_input_1", "wave1_input_2", "wave1_input_3",
    }  # fmt: skip


def test_pinned_hashes_are_the_published_ones() -> None:
    src = _load()  # fresh module, not monkeypatched
    assert src.REFERENCE_SHA256["f1"].startswith("eb81d9c3")  # wave-1 report, section 8
    assert src.REFERENCE_SHA256["wave1_manifest"].startswith("c6b22bdc")
    assert src.WAVE1_OUTPUT_SHA256["rr_output_1.jsonl"].startswith("7d55f195")
    sys.modules["rating_second_run_full_eval"] = ev


def test_eval_runs_only_with_the_posted_classification_sha(lab: Lab) -> None:
    lab.build()
    with pytest.raises(ev.RefusedError, match="posted"):
        lab.run(cls_sha="0" * 64)
    res, _ = lab.run()
    assert len(res["herkunft"]["eingaben_sha256"]["klassifikation.json"]) == 64


def test_b2_never_better_with_unknown_family(lab: Lab) -> None:
    for o in lab.g1_ids:
        lab.g1[o] = lab.f1[o] - 5  # G1 = R2: pooled is closer to G1 than F1
    lab.build()
    res, _ = lab.run(draws=200)
    assert (
        res["B2_G1"]["delta_K0"] == pytest.approx(2.5) and res["B2_G1"]["urteil"] == "besser belegt"
    )
    lab.run_log["familie_R2_gegen_G1"] = "unbekannt"
    res2, _ = lab.run(draws=200)
    assert res2["B2_G1"]["urteil"].startswith("unbelegt")
    lab.run_log.pop("familie_R2_gegen_G1")
    res3, _ = lab.run(draws=200)
    assert res3["B2_G1"]["urteil"].startswith("unbelegt")


def test_a4_sd_criterion_excludes_with_distinct_values(lab: Lab) -> None:
    # F1 20..70 (pop. SD 17.1); R2 35, 40, 45, 50, 55, 60 distinct (no mode share), SD 8.5 < 0.6 x 17.1
    for j in range(1, 7):
        lab.r2[oid("c", 4, j)] = 30 + 5 * j
    lab.build()
    res, _ = lab.run()
    a4 = res["chargen"]["4"]["A4"]
    assert a4["mode_share"] == pytest.approx(1 / 6) and a4["triggered"] is True
    assert res["gueltige_chargen"]["ausgeschlossen"] == {"4": "A4_skalenstauchung"}


def test_a2_violation_in_retest_chunk_counts_for_two_chunks(lab: Lab) -> None:
    lab.overrides[oid("c", 3, 2)] = {"reason": "Same as the earlier rating."}
    lab.overrides[oid("w", 1, 2)] = {"reason": "As in the previous run."}
    lab.build()
    _, hits = lab.hits()
    ids = {h["id"] for h in hits if h["feld"] == "reason"}
    assert {h["charge"] for h in hits if h["id"] in ids} == {3, 8}
    res, _ = lab.run(counting=ids)
    assert res["A2"] == {"verstoss_chargen": [3, 8], "abbruch": True}
    assert res["B3_retest"]["berechnet"] is False


def test_k1_only_on_confirmed(lab: Lab) -> None:
    for o, c in lab.cards.items():
        if c["wave"] == 2 and not c["is_land"]:
            lab.r2[o] = lab.f1[o] - 10  # b = -10: "bestaetigt"
    lab.build()
    res, pooled = lab.run(draws=200)
    assert res["spells_test"]["verdict"] == "bestaetigt" and res["K1"]["berechnet"] is True
    p = by_id(pooled)[oid("c", 1, 1)]  # F1 20, R2 10, b_W2 -10 -> (20 + 10 + 10) / 2 = 20
    assert p["H_pooled_K1_vorschlag"] == pytest.approx(20.0) and p["H_pooled"] == 15.0
    for o, c in lab.cards.items():
        if c["wave"] == 2 and not c["is_land"]:
            lab.r2[o] = lab.f1[o] + (5 if c["chunk"] in (1, 2) else -5)  # 5 of 7 chunks below 0
    lab.build()
    res2, pooled2 = lab.run(draws=200)
    assert res2["spells_test"]["verdict"] != "bestaetigt" and res2["K1"]["berechnet"] is False
    assert "H_pooled_K1_vorschlag" not in by_id(pooled2)[oid("c", 1, 1)]


def test_a6_flags_when_either_reading_exceeds_four() -> None:
    # others: chunk 2 one card at 0, chunk 3 ten cards at -10 -> mean of means -5, pooled -9.09
    ds = {1: [-4.5, -4.5], 2: [0.0], 3: [-10.0] * 10}
    eff = ev.chunk_effect(ds)["1"]
    assert eff["gap_means"] == pytest.approx(0.5) and eff["gap_pooled"] == pytest.approx(
        -4.5 + 100 / 11
    )
    assert eff["auffaellig"] is True  # only the pooled reading is above 4
    ds2 = {1: [-0.5, -0.5], 2: [0.0] * 10, 3: [-10.0]}
    eff2 = ev.chunk_effect(ds2)["1"]  # mean of means -5 (gap 4.5), pooled -0.91 (gap 0.41)
    assert eff2["gap_pooled"] == pytest.approx(-0.5 + 10 / 11) and eff2["auffaellig"] is True


def test_chunk_without_valid_spells_counts_in_m() -> None:
    clusters = {k: _tight(-6.0) for k in range(1, 7)} | {7: []}
    res = ev.spells_test(clusters, [], draws=300)
    assert res["m"] == 7 and res["chunks_negative"] == 6 and res["verdict"] == "bestaetigt"
    clusters[6] = []
    assert ev.spells_test(clusters, [], draws=300)["verdict"] == "nicht bestaetigt"  # 5 of 7


def test_claim_sample_is_blind_deterministic_and_one_per_card(lab: Lab, tmp_path: Path) -> None:
    lab.build()
    blind1, key1 = ev.run_claims(lab.manifest, lab.rater, lab.sums, lab.f1_path)
    blind2, key2 = ev.run_claims(lab.manifest, lab.rater, lab.sums, lab.f1_path)
    assert (blind1, key1) == (blind2, key2)
    b = json.loads(blind1)["claims"]
    k = json.loads(key1)["schluessel"]
    # 42 wave-2 lines, each with one claim: all 42 drawn from wave 2 (< 50); F1 has no other card left
    assert len(b) == 42 and {x["herkunft"] for x in k} == {"welle2"}
    assert len({x["oracle_id"] for x in b}) == len(b)
    text = blind1.decode()
    assert "herkunft" not in text and '"scores"' not in text and "welle2" not in text


def test_claim_sample_draws_f1_claims_for_other_wave2_cards(lab: Lab) -> None:
    for o, c in lab.cards.items():
        if c["wave"] == 2 and c["seq"] >= 4:
            lab.overrides[o] = {"rule_claims": []}  # 21 wave-2 lines without claims
    lab.build()
    blind, key = ev.run_claims(lab.manifest, lab.rater, lab.sums, lab.f1_path)
    k = json.loads(key)["schluessel"]
    w2 = {x["oracle_id"] for x in k if x["herkunft"] == "welle2"}
    f1 = {x["oracle_id"] for x in k if x["herkunft"] == "F1"}
    assert len(w2) == 21 and len(f1) == 21 and not (w2 & f1)
    claims = {x["oracle_id"]: x["claim"] for x in json.loads(blind)["claims"]}
    assert all(claims[o] == f"first-run claim for {o}" for o in f1)


def test_claims_are_graded_per_origin(lab: Lab) -> None:
    key = [{"nr": i, "herkunft": "welle2" if i <= 50 else "F1"} for i in range(1, 101)]
    blind = [{"nr": i} for i in range(1, 101)]
    vd = {str(i): "korrekt" for i in range(1, 101)} | {"1": "falsch", "2": "falsch", "51": "falsch"}
    vd |= {str(i): "falsch" for i in range(52, 56)}  # F1: 5 wrong
    g = ev.grade_claims(blind, key, vd)
    assert g["welle2"]["stufe"] == "gruen" and g["F1"]["stufe"] == "rot"
    vd.pop("3")
    assert ev.grade_claims(blind, key, vd)["welle2"]["stufe"] == "unbekannt"
    assert ev.grade_claims(blind, key, None)["F1"]["stufe"] == "unbekannt"


def test_cluster_bootstrap_draws_empty_chunks_too() -> None:
    # an empty chunk is one of the m clusters drawn (k = m = 3, not 2); dropping it changes the draws
    full = [[-9.0, -8.0, -7.0], [1.0, 2.0, 3.0]]
    with_empty = ev.cluster_bootstrap([*full, []], draws=400)
    assert with_empty != ev.cluster_bootstrap(full, draws=400)
    assert ev.cluster_bootstrap([[], []], draws=10) == [None, None]
