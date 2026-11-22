"""Second, independent rater run of the card understanding score H (Chulane, rubric v2.1)
compared with the full run F1, following a plan fixed before the run (Refs #1404).

The thresholds, strata and metrics M1 to M8, V1 to V4, the flagged-card test, the rule-claim
sample, the blindness scan, the fatigue check and the stop rules A1 to A8 come from the plan;
this script does not change them. It compares absolute scores of the same card from two runs;
it never compares two cards with each other.

Inputs (paths as arguments, nothing is fetched):
  --rr-dir     folder with ``rr_sample_manifest.json``, ``rr_input_1..3.jsonl`` (card blocks),
               ``rr_output_1..3.jsonl`` (second run), ``rr_guide_v2_1_rendered.md`` (Chulane text);
               inputs, outputs and guide may also sit in a subfolder ``rater/``
  --old        ``fullrun_ratings.jsonl`` (F1, 922 cards)
  --flagged    ``audit/audit_A_flagged.jsonl`` (35 flagged cards, joined by name)
  --verdicts   optional JSON {claim_id: verdict} of the hand-checked rule claims
  --out        result JSON

Standard library only, deterministic: bootstrap ``random.Random(20261122)``, 5000 draws within
strata; rule-claim sample ``random.Random(20261123)``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import statistics
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

CRITERIA = ("E", "F", "T", "R", "K", "D", "H")
SUB = ("E", "F", "T", "R", "K", "D")
SCHEMA = "rubric-v2-card-rating-1"
SEED_BOOT = 20261122
SEED_CLAIMS = 20261123
DRAWS = 5000
CLAIM_SAMPLE = 100
GUIDE_NAME = "rr_guide_v2_1_rendered.md"  # Chulane Oracle text for the quote check
FILES = (1, 2, 3)
STRATUM_MAP = {
    "flagged": "flagged",
    "top20": "top20",
    "rest": "rest",
    "rest_fill": "rest",
    "land": "land",
}
PRIMARY = ("top20", "rest", "land")
POOL_N = {"top20": 132, "rest": 663, "land": 50}
G1_ICC = {"E": 0.87, "F": 0.94, "T": 0.82, "R": 0.92, "K": 0.92, "D": 0.91}
BANDS = ((95, "95-100"), (72, "72-94"), (50, "50-71"), (28, "28-49"), (5, "5-27"), (0, "0-4"))
PREFERRED_INTERACTIONS = frozenset(
    {
        "chulane_cast_trigger",
        "chulane_bounce_replay",
        "etb_reuse",
        "landfall",
        "land_drop",
        "symmetry",
        "timing",
    }
)
INTERACTIONS = frozenset(
    PREFERRED_INTERACTIONS
    | {"mana", "wrath_exposure", "self_damage", "targeting", "combo_loop", "other"}
)
BASES = frozenset({"card_text", "ruling_shown", "inferred_from_text"})
POPULARITY = re.compile(
    r"popular|staple|edhrec|commonly played|budget|cedh|played in (most|many)", re.I
)
EARLIER = re.compile(r"earlier rating|previous|\bv1\b|\bF1\b|audit|tier ?list", re.I)
TOP_KEYS = {
    "schema", "oracle_id", "card", "judged_as", "scores", "notes", "reason",
    "confidence", "uncertainty", "rule_claims", "pattern_check",
}  # fmt: skip

# Thresholds of the plan (section 5, 6, 7, 8): (green test, red test); between both is yellow.
GRADES: dict[str, tuple[Callable[[float], bool], Callable[[float], bool]]] = {
    "M1": (lambda v: v <= 8.0, lambda v: v > 11.0),
    "M2": (lambda v: v <= 10.5, lambda v: v > 14.0),
    "M3": (lambda v: v <= 0.20, lambda v: v >= 0.30),
    "M4": (lambda v: v >= 0.88, lambda v: v < 0.80),
    "M5": (lambda v: 0.80 <= v <= 1.10, lambda v: v < 0.65 or v > 1.25),
    "M6": (lambda v: abs(v) <= 5.0, lambda v: abs(v) > 8.0),
    "M7": (lambda v: v >= 0.65, lambda v: v < 0.55),
    "M8": (lambda v: v >= 0.88, lambda v: v < 0.80),
    "V1": (lambda v: v >= 297, lambda v: v < 270),
    "V2": (lambda v: v >= 1.0, lambda v: v < 0.95),
    "V3": (lambda v: v >= 0.99, lambda v: v < 0.95),
    "V4": (lambda v: v >= 0.98, lambda v: v < 0.90),
    "K": (lambda v: v <= 3, lambda v: v >= 8),
    "L": (lambda v: v <= 6, lambda v: v > 15),
}


def grade(metric: str, value: float | None) -> str:
    """green / yellow / red for a plan metric; ``unbekannt`` when the value is missing."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "unbekannt"
    green, red = GRADES[metric]
    if green(value):
        return "gruen"
    return "rot" if red(value) else "gelb"


# ---------------------------------------------------------------- statistics


def round5(value: float) -> int:
    """Half up to the next multiple of 5 (as import_card_understanding.py)."""
    return math.floor(value / 5 + 0.5) * 5


def midranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def pearson(x: Sequence[float], y: Sequence[float]) -> float:
    n = len(x)
    if n < 2:
        return float("nan")
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y, strict=True))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    return sxy / math.sqrt(sxx * syy) if sxx > 0 and syy > 0 else float("nan")


def spearman(x: Sequence[float], y: Sequence[float]) -> float:
    """Pearson correlation of mid-ranks (ties share the average rank)."""
    return pearson(midranks(x), midranks(y))


def ols_slope(x: Sequence[float], y: Sequence[float]) -> float:
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    return (
        sum((a - mx) * (b - my) for a, b in zip(x, y, strict=True)) / sxx if sxx else float("nan")
    )


def icc21(pairs: Sequence[tuple[float, float]]) -> float:
    """ICC(2,1), two-way random, absolute agreement (Shrout & Fleiss); as drift_eval.py."""
    n = len(pairs)
    if n < 2:
        return float("nan")
    grand = sum(a + b for a, b in pairs) / (2 * n)
    row_means = [(a + b) / 2 for a, b in pairs]
    col_means = [sum(p[j] for p in pairs) / n for j in (0, 1)]
    msr = 2 * sum((m - grand) ** 2 for m in row_means) / (n - 1)
    msc = n * sum((m - grand) ** 2 for m in col_means)
    sse = sum(
        (p[j] - row_means[i] - col_means[j] + grand) ** 2
        for i, p in enumerate(pairs)
        for j in (0, 1)
    )
    mse = sse / (n - 1)
    denom = msr + mse + 2 * (msc - mse) / n
    return (msr - mse) / denom if denom else float("nan")


def band(h: float) -> str:
    """Guide band of H (95-100, 72-94, 50-71, 28-49, 5-27, 0-4)."""
    for low, label in BANDS:
        if h >= low:
            return label
    return BANDS[-1][1]


def delta_stats(pairs: Sequence[tuple[float, float]]) -> dict[str, Any]:
    """pairs = (old, new). Delta = new - old."""
    d = [b - a for a, b in pairs]
    n = len(d)
    if not n:
        return {"n": 0}
    absd = [abs(x) for x in d]
    return {
        "n": n,
        "bias": sum(d) / n,
        "sd": statistics.stdev(d) if n > 1 else float("nan"),
        "median": statistics.median(d),
        "mean_abs": sum(absd) / n,
        "rms": math.sqrt(sum(x * x for x in d) / n),
        "ge15": sum(x >= 15 for x in absd),
        "share_ge15": sum(x >= 15 for x in absd) / n,
        "max_abs": max(absd),
        "spearman": spearman([a for a, _ in pairs], [b for _, b in pairs])
        if n > 2
        else float("nan"),
        "slope": ols_slope([a for a, _ in pairs], [b for _, b in pairs]) if n > 2 else float("nan"),
        "same_band": sum(band(a) == band(b) for a, b in pairs),
        "same_side50": sum((a >= 50) == (b >= 50) for a, b in pairs),
        "sd_new": statistics.pstdev([b for _, b in pairs]),
        "sd_old": statistics.pstdev([a for a, _ in pairs]),
    }


def weighted_stats(
    groups: Mapping[str, Sequence[tuple[float, float]]], pool_n: Mapping[str, int]
) -> dict[str, float]:
    """Weight N_h / n_h per stratum (plan section 6); a supplement, not the primary number."""
    tot = s_abs = s_d = s_sq = s_15 = 0.0
    for name, pairs in groups.items():
        if not pairs:
            continue
        w = pool_n[name] / len(pairs)
        for a, b in pairs:
            d = b - a
            tot += w
            s_abs += w * abs(d)
            s_d += w * d
            s_sq += w * d * d
            s_15 += w * (abs(d) >= 15)
    return {
        "mean_abs": s_abs / tot,
        "bias": s_d / tot,
        "rms": math.sqrt(s_sq / tot),
        "share_ge15": s_15 / tot,
    }


def percentile_interval(values: Sequence[float], level: float = 0.95) -> tuple[float, float]:
    vals = sorted(v for v in values if not math.isnan(v))
    if not vals:
        return (float("nan"), float("nan"))
    lo_i = math.floor((1 - level) / 2 * (len(vals) - 1))
    hi_i = math.ceil((1 + level) / 2 * (len(vals) - 1))
    return (vals[lo_i], vals[hi_i])


def bootstrap(
    groups: Sequence[Sequence[Any]],
    stats: Mapping[str, Callable[[list[Any]], float]],
    draws: int = DRAWS,
    seed: int = SEED_BOOT,
) -> dict[str, tuple[float, float]]:
    """Resample cards within each group (stratum), pool the groups, compute every statistic."""
    rng = random.Random(seed)
    acc: dict[str, list[float]] = {k: [] for k in stats}
    for _ in range(draws):
        sample: list[Any] = []
        for g in groups:
            sample.extend(rng.choices(g, k=len(g)))
        for k, fn in stats.items():
            acc[k].append(fn(sample))
    return {k: percentile_interval(v) for k, v in acc.items()}


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def _bias(p: list[tuple[float, float]]) -> float:
    return _mean([b - a for a, b in p])


def _mean_abs(p: list[tuple[float, float]]) -> float:
    return sum(abs(b - a) for a, b in p) / len(p)


def _rms(p: list[tuple[float, float]]) -> float:
    return math.sqrt(sum((b - a) ** 2 for a, b in p) / len(p))


def _share15(p: list[tuple[float, float]]) -> float:
    return sum(abs(b - a) >= 15 for a, b in p) / len(p)


def _rho(p: list[tuple[float, float]]) -> float:
    return spearman([a for a, _ in p], [b for _, b in p])


def _slope(p: list[tuple[float, float]]) -> float:
    return ols_slope([a for a, _ in p], [b for _, b in p])


BOOT_STATS: dict[str, Callable[[list[Any]], float]] = {
    "bias": _bias, "mean_abs": _mean_abs, "rms": _rms, "share_ge15": _share15, "spearman": _rho, "slope": _slope,
}  # fmt: skip


# ---------------------------------------------------------------- validity, quotes, scans


def norm_ws(text: str) -> str:
    return " ".join(text.lower().split())


def chulane_text(guide: str) -> str:
    """The quoted commander block of the guide (lines starting with '>')."""
    lines = guide.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("The commander (exact Oracle"))
    block: list[str] = []
    for ln in lines[start + 1 :]:
        if ln.startswith(">"):
            block.append(ln[1:].strip())
        elif block:
            break
    return " ".join(block)


def pattern_hits(card_block: str) -> list[str]:
    """rule_ids listed under 'Pattern hits' in the card block ([] for 'Pattern hits: none')."""
    lines = card_block.splitlines()
    out: list[str] = []
    for i, ln in enumerate(lines):
        if ln.startswith("Pattern hits"):
            for nxt in lines[i + 1 :]:
                m = re.match(r"\s+- ([A-Za-z0-9_]+):", nxt)
                if not m:
                    break
                out.append(m.group(1))
            break
    return out


def type_line(card_block: str) -> str:
    for ln in card_block.splitlines():
        if ln.startswith("Type line:"):
            return ln.split(":", 1)[1].split("|")[0].strip()
    return ""


def is_type_line_claim(quote: str, card_block: str) -> bool:
    """Quote is only (part of) the type line, not of the rules text."""
    tl = norm_ws(type_line(card_block))
    q = norm_ws(quote)
    oracle = card_block.split("Oracle text:", 1)[-1]
    return bool(q) and bool(tl) and q in tl and q not in norm_ws(oracle.split("Roles", 1)[0])


def plan_problems(row: Any, inp: Mapping[str, Any]) -> list[str]:
    """Validity per plan section 5 (card counts as valid when this list is empty)."""
    if not isinstance(row, dict):
        return ["not an object"]
    p: list[str] = []
    if row.get("oracle_id") != inp["oracle_id"]:
        p.append("oracle_id")
    if row.get("card") != inp["card"]:
        p.append("card")
    scores = row.get("scores")
    if not isinstance(scores, dict) or set(scores) != set(CRITERIA):
        p.append("scores keys")
    elif not all(
        isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 100 for v in scores.values()
    ):
        p.append("scores range")
    notes = row.get("notes")
    if not isinstance(notes, dict) or set(notes) != set(CRITERIA):
        p.append("notes keys")
    for key in ("reason", "confidence", "uncertainty"):
        if not isinstance(row.get(key), str):
            p.append(key)
    if (
        isinstance(row.get("uncertainty"), str)
        and row.get("confidence") != "high"
        and not row["uncertainty"]
    ):
        p.append("uncertainty empty though not high")
    return p


def schema_problems(row: Mapping[str, Any], card_block: str) -> list[str]:
    """Stricter check against the full output schema plus pattern_check coverage (reported only)."""
    p: list[str] = []
    if set(row) != TOP_KEYS:
        p.append("top-level keys")
    if row.get("schema") != SCHEMA:
        p.append("schema")
    if row.get("judged_as") not in ("spell", "land"):
        p.append("judged_as")
    if any(not isinstance(v, int) or v % 5 for v in row.get("scores", {}).values()):
        p.append("scores not multiple of 5")
    if any(not 3 <= len(str(v)) <= 160 for v in row.get("notes", {}).values()):
        p.append("notes length")
    if not 60 <= len(str(row.get("reason", ""))) <= 900:
        p.append("reason length")
    if row.get("confidence") not in ("high", "medium", "low"):
        p.append("confidence")
    unc = str(row.get("uncertainty", ""))
    if len(unc) > 400 or (row.get("confidence") != "high" and len(unc) < 10):
        p.append("uncertainty length")
    claims = row.get("rule_claims", [])
    if not isinstance(claims, list) or len(claims) > 6:
        p.append("rule_claims count")
    else:
        for c in claims:
            if set(c) != {"quote", "interaction", "claim", "basis"}:
                p.append("rule_claims keys")
            elif c["interaction"] not in INTERACTIONS or c["basis"] not in BASES:
                p.append("rule_claims enum")
            elif not 3 <= len(c["quote"]) <= 300 or not 5 <= len(c["claim"]) <= 300:
                p.append("rule_claims length")
    pc = row.get("pattern_check", [])
    if not isinstance(pc, list) or any(
        set(x) - {"rule_id", "verdict", "why"}
        or x.get("verdict") not in ("correct", "wrong", "irrelevant")
        for x in pc
    ):
        p.append("pattern_check entries")
    elif sorted(x["rule_id"] for x in pc) != sorted(pattern_hits(card_block)):
        p.append("pattern_check coverage")
    return sorted(set(p))


def scan_texts(row: Mapping[str, Any]) -> list[tuple[str, str]]:
    fields = [(f"notes.{k}", str(v)) for k, v in row.get("notes", {}).items()]
    fields += [
        ("reason", str(row.get("reason", ""))),
        ("uncertainty", str(row.get("uncertainty", ""))),
    ]
    fields += [
        (f"claim{i}", str(c.get("claim", ""))) for i, c in enumerate(row.get("rule_claims", []))
    ]
    return fields


def blindness_hits(rows: Mapping[str, Mapping[str, Any]]) -> list[dict[str, str]]:
    """Keyword hits (popularity list of full_qa.py, references to earlier numbers); read each by hand."""
    hits = []
    for cid, row in rows.items():
        for field, text in scan_texts(row):
            for label, rx in (("popularity", POPULARITY), ("earlier", EARLIER)):
                m = rx.search(text)
                if m:
                    hits.append(
                        {
                            "id": cid,
                            "field": field,
                            "kind": label,
                            "text": text[max(0, m.start() - 60) : m.end() + 60],
                        }
                    )
    return hits


# ---------------------------------------------------------------- rule-claim sample


def select_claims(
    cards: Sequence[tuple[str, list[dict[str, Any]]]],
    k: int = CLAIM_SAMPLE,
    seed: int = SEED_CLAIMS,
) -> list[tuple[str, int]]:
    """At most one claim per card: per card (in the given order) one claim drawn with the seeded
    generator, from the preferred interactions (Chulane trigger, bounce, ETB reuse, landfall,
    land drop, symmetry, timing) when the card has any, else from all; then ``k`` cards drawn.
    Returns (card id, claim index), sorted by card id order."""
    rng = random.Random(seed)
    chosen: list[tuple[str, int]] = []
    for cid, claims in cards:
        if not claims:
            continue
        pref = [i for i, c in enumerate(claims) if c.get("interaction") in PREFERRED_INTERACTIONS]
        chosen.append((cid, rng.choice(pref or list(range(len(claims))))))
    if len(chosen) <= k:
        return chosen
    picked = set(rng.sample(range(len(chosen)), k))
    return [c for i, c in enumerate(chosen) if i in picked]


# ---------------------------------------------------------------- flagged cards


def proximity(h: float, low: float, high: float) -> float:
    return max(low - h, 0.0, h - high)


def flagged_metrics(rows: Sequence[Mapping[str, Any]], top20_bias: float) -> dict[str, Any]:
    """rows: card, kind, low, high, h_old, h_new (plan section 7)."""
    inside = sum(r["low"] <= r["h_new"] <= r["high"] for r in rows)
    inside_old = sum(r["low"] <= r["h_old"] <= r["high"] for r in rows)
    closer = sum(
        proximity(r["h_new"], r["low"], r["high"]) < proximity(r["h_old"], r["low"], r["high"])
        for r in rows
    )
    by_kind: dict[str, list[float]] = {}
    for r in rows:
        by_kind.setdefault(r["kind"], []).append(r["h_new"] - r["h_old"])
    too_high = by_kind.get("H zu hoch", [])
    d = (sum(too_high) / len(too_high) - top20_bias) if too_high else float("nan")
    if inside >= 14 and d <= -5:
        verdict = "stuetzt"
    elif inside <= 7 and closer <= 17:
        verdict = "stuetzt nicht"
    else:
        verdict = "teilweise"
    return {
        "n": len(rows),
        "a_inside": inside,
        "a_inside_old": inside_old,
        "b_closer": closer,
        "c_mean_delta": {k: {"n": len(v), "mean": sum(v) / len(v)} for k, v in by_kind.items()},
        "d_too_high_minus_top20": d,
        "verdict": verdict,
    }


# ---------------------------------------------------------------- overall verdict


def overall_verdict(grades: Mapping[str, str], stops: Sequence[str]) -> str:
    """Plan section 9; 'kein Schluss' when a stop rule blocks the pooled verdict."""
    if stops:
        return "kein Schluss"
    core = [grades[m] for m in ("M1", "M2", "M3", "M4", "M5")]
    if "rot" in core:
        return "nicht bestaetigt"
    others_red = any(grades[m] == "rot" for m in ("M6", "M7", "M8"))
    gate_green = all(grades[m] == "gruen" for m in ("V1", "V2", "V3", "V4"))
    if (
        all(g == "gruen" for g in core)
        and not others_red
        and gate_green
        and grades["K"] != "rot"
        and grades["L"] != "rot"
    ):
        return "bestaetigt"
    return "teilweise bestaetigt"


# ---------------------------------------------------------------- main analysis


def load_jsonl(path: Path) -> list[Any]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _find(rr: Path, name: str) -> Path:
    return rr / name if (rr / name).exists() else rr / "rater" / name


def analyse(
    rr: Path, old_path: Path, flagged_path: Path, verdicts: Mapping[str, str] | None
) -> dict[str, Any]:
    manifest = json.loads((rr / "rr_sample_manifest.json").read_text(encoding="utf-8"))
    guide = _find(rr, GUIDE_NAME).read_text(encoding="utf-8")
    chulane = norm_ws(chulane_text(guide))
    old = {r["oracle_id"]: r for r in load_jsonl(old_path)}
    flagged = {r["card"]: r for r in load_jsonl(flagged_path)}
    inputs_paths = {f: _find(rr, f"rr_input_{f}.jsonl") for f in FILES}
    output_paths = {f: _find(rr, f"rr_output_{f}.jsonl") for f in FILES}
    hashes = {
        p.name: sha256(p)
        for p in [rr / "rr_sample_manifest.json", *inputs_paths.values(), *output_paths.values()]
    }
    hashes[old_path.name] = sha256(old_path)
    hashes[flagged_path.name] = sha256(flagged_path)

    cards: list[dict[str, Any]] = []
    parse_errors: list[str] = []
    duplicates: list[str] = []
    seen: set[str] = set()
    for f in FILES:
        inputs = load_jsonl(inputs_paths[f])
        raw_lines = output_paths[f].read_text(encoding="utf-8").splitlines()
        man = sorted((c for c in manifest["cards"] if c["input_file"] == f), key=lambda c: c["seq"])
        for pos, (m, inp) in enumerate(zip(man, inputs, strict=True), start=1):
            cid = f"{f}:{pos}"
            assert m["oracle_id"] == inp["oracle_id"] and inp["seq"] == pos, cid
            row: Any = None
            if pos <= len(raw_lines):
                try:
                    row = json.loads(raw_lines[pos - 1])
                except json.JSONDecodeError:
                    parse_errors.append(cid)
            problems = plan_problems(row, inp) if row is not None else ["missing"]
            if isinstance(row, dict):
                if row.get("oracle_id") in seen:
                    duplicates.append(cid)
                seen.add(str(row.get("oracle_id")))
            cards.append({
                "id": cid, "file": f, "pos": pos, "oracle_id": inp["oracle_id"], "name": inp["card"],
                "stratum": STRATUM_MAP[m["stratum"]], "raw_stratum": m["stratum"], "is_land": m["is_land"],
                "block": inp["card_block"], "row": row, "problems": problems,
                "schema_problems": schema_problems(row, inp["card_block"]) if isinstance(row, dict) else ["missing"],
                "old": old[inp["oracle_id"]],
            })  # fmt: skip
        if len(raw_lines) > len(man):
            parse_errors.append(f"{f}: {len(raw_lines) - len(man)} extra lines")

    valid = [c for c in cards if not c["problems"]]
    non5 = [c["id"] for c in valid if any(v % 5 for v in c["row"]["scores"].values())]

    def score(c: dict[str, Any], k: str) -> int:
        return round5(c["row"]["scores"][k])

    for c in valid:
        c["h_old"], c["h_new"] = c["old"]["scores"]["H"], score(c, "H")
        c["dh"] = c["h_new"] - c["h_old"]

    # quotes (V4), claim counts
    n_claims = n_lit = 0
    for c in valid:
        block = norm_ws(c["block"])
        for rc in c["row"].get("rule_claims", []):
            n_claims += 1
            q = norm_ws(str(rc.get("quote", "")))
            n_lit += bool(q) and (q in block or q in chulane)

    by_stratum: dict[str, list[tuple[float, float]]] = {s: [] for s in ("flagged", *PRIMARY)}
    for c in valid:
        by_stratum[c["stratum"]].append((c["h_old"], c["h_new"]))
    primary = [p for s in PRIMARY for p in by_stratum[s]]
    rest_land = by_stratum["rest"] + by_stratum["land"]

    strata_out: dict[str, Any] = {}
    for s, pairs in by_stratum.items():
        st = delta_stats(pairs)
        st["ci"] = bootstrap([pairs], BOOT_STATS)
        strata_out[s] = st
    prim = delta_stats(primary)
    prim["ci"] = bootstrap([by_stratum[s] for s in PRIMARY], BOOT_STATS)
    all300 = delta_stats([p for pairs in by_stratum.values() for p in pairs])
    rl = delta_stats(rest_land)
    rl["ci"] = bootstrap([by_stratum["rest"], by_stratum["land"]], {"bias": _bias})
    weighted = weighted_stats({s: by_stratum[s] for s in PRIMARY}, POOL_N)

    metrics = {
        "M1": prim["mean_abs"], "M2": prim["rms"], "M3": prim["share_ge15"], "M4": prim["spearman"],
        "M5": prim["slope"], "M6": rl["bias"], "M7": prim["same_band"] / prim["n"], "M8": prim["same_side50"] / prim["n"],
    }  # fmt: skip

    # sub-criteria (primary)
    prim_cards = [c for c in valid if c["stratum"] in PRIMARY]
    sub: dict[str, Any] = {}
    for k in CRITERIA:
        pairs = [(float(c["old"]["scores"][k]), float(score(c, k))) for c in prim_cards]
        sub[k] = {
            "mean_abs": _mean_abs(pairs), "bias": _bias(pairs), "spearman": _rho(pairs), "icc21": icc21(pairs),
        }  # fmt: skip
    icc_green = all(sub[k]["icc21"] >= G1_ICC[k] - 0.05 for k in SUB)
    icc_red = any(sub[k]["icc21"] < G1_ICC[k] - 0.15 for k in SUB)
    sub_grade = "gruen" if icc_green else ("rot" if icc_red else "gelb")

    # lands separately (all criteria)
    land_cards = [c for c in valid if c["stratum"] == "land"]
    lands = {
        k: {"bias": _bias([(c["old"]["scores"][k], score(c, k)) for c in land_cards]),
            "zero_new": sum(score(c, k) == 0 for c in land_cards), "zero_old": sum(c["old"]["scores"][k] == 0 for c in land_cards)}
        for k in CRITERIA
    }  # fmt: skip

    # flagged
    frows = []
    for c in valid:
        if c["stratum"] == "flagged":
            fl = flagged[c["name"]]
            frows.append({"card": c["name"], "kind": fl["kind"], "low": fl["proposed_H_low"], "high": fl["proposed_H_high"],
                          "h_old": c["h_old"], "h_new": c["h_new"], "rater_H_matches_F1": fl["rater_H"] == c["h_old"]})  # fmt: skip
    flag = flagged_metrics(frows, strata_out["top20"]["bias"])
    flag["rater_H_matches_F1"] = sum(r["rater_H_matches_F1"] for r in frows)

    # fatigue and file effect
    fatigue: dict[str, Any] = {}
    for f in FILES:
        fc = sorted((c for c in valid if c["file"] == f), key=lambda c: c["pos"])
        first = [abs(c["dh"]) for c in fc if c["pos"] <= 50]
        second = [abs(c["dh"]) for c in fc if c["pos"] > 50]
        prim_f = [abs(c["dh"]) for c in fc if c["stratum"] in PRIMARY]
        spells = [c for c in fc if not c["is_land"]]
        fatigue[str(f)] = {
            "n": len(fc), "mean_abs_1_50": _mean(first), "mean_abs_51_100": _mean(second),
            "rho_pos_dh": spearman([c["pos"] for c in fc], [c["dh"] for c in fc]) if len(fc) > 2 else float("nan"),
            "mean_abs_all": _mean([abs(c["dh"]) for c in fc]), "mean_abs_primary": _mean(prim_f),
            "n_primary": len(prim_f), "bias_all": _mean([c["dh"] for c in fc]),
            "t_zero_spells_1_50": [sum(score(c, "T") == 0 for c in spells if c["pos"] <= 50), sum(c["pos"] <= 50 for c in spells)],
            "t_zero_spells_51_100": [sum(score(c, "T") == 0 for c in spells if c["pos"] > 50), sum(c["pos"] > 50 for c in spells)],
            "t_bias_spells_1_50": _bias([(c["old"]["scores"]["T"], score(c, "T")) for c in spells if c["pos"] <= 50]),
            "t_bias_spells_51_100": _bias([(c["old"]["scores"]["T"], score(c, "T")) for c in spells if c["pos"] > 50]),
        }  # fmt: skip
        fatigue[str(f)]["flag"] = (
            abs(fatigue[str(f)]["mean_abs_1_50"] - fatigue[str(f)]["mean_abs_51_100"]) > 3
            or abs(fatigue[str(f)]["rho_pos_dh"]) > 0.2
        )
    file_gap_primary = max(v["mean_abs_primary"] for v in fatigue.values()) - min(
        v["mean_abs_primary"] for v in fatigue.values()
    )
    file_gap_all = max(v["mean_abs_all"] for v in fatigue.values()) - min(
        v["mean_abs_all"] for v in fatigue.values()
    )

    # scale (A4, N)
    new_prim = [b for _, b in primary]
    mode_val, mode_n = Counter(new_prim).most_common(1)[0]
    scale = {"sd_new": statistics.pstdev(new_prim), "sd_old": statistics.pstdev([a for a, _ in primary]),
             "mean_new": sum(new_prim) / len(new_prim), "mean_old": sum(a for a, _ in primary) / len(primary),
             "mode": mode_val, "mode_n": mode_n, "n": len(new_prim)}  # fmt: skip

    # blindness, claim sample
    rows = {c["id"]: c["row"] for c in valid}
    blind = blindness_hits(rows)
    sample = select_claims([(c["id"], c["row"].get("rule_claims", [])) for c in valid])
    by_id = {c["id"]: c for c in valid}
    claim_sample = []
    for cid, i in sample:
        rc = by_id[cid]["row"]["rule_claims"][i]
        q = norm_ws(rc["quote"])
        claim_sample.append({
            "claim_id": f"{cid}:{i}", "card": by_id[cid]["name"], "interaction": rc["interaction"], "basis": rc["basis"],
            "quote": rc["quote"], "claim": rc["claim"], "quote_literal": q in norm_ws(by_id[cid]["block"]) or q in chulane,
            "type_line_only": is_type_line_claim(rc["quote"], by_id[cid]["block"]),
            "verdict": (verdicts or {}).get(f"{cid}:{i}"),
        })  # fmt: skip
    verdict_counts = Counter(x["verdict"] for x in claim_sample) if verdicts else None
    n_false = verdict_counts.get("falsch", 0) if verdict_counts is not None else None

    # the 10 largest deviations per stratum with both reasons (plan section 6, reading aid only)
    top_out: dict[str, list[dict[str, Any]]] = {}
    for stratum in by_stratum:
        top = sorted(
            (c for c in valid if c["stratum"] == stratum), key=lambda c: (-abs(c["dh"]), c["id"])
        )[:10]
        top_out[stratum] = [{"id": c["id"], "card": c["name"], "h_old": c["h_old"], "h_new": c["h_new"],
                             "reason_new": c["row"]["reason"], "reason_old": c["old"].get("reason", "")} for c in top]  # fmt: skip

    n_valid = len(valid)
    per_stratum_valid = {
        s: [sum(1 for c in valid if c["stratum"] == s), sum(1 for c in cards if c["stratum"] == s)]
        for s in by_stratum
    }
    form_break = len({c["id"] for c in cards if c["problems"]} | set(non5))
    grades = {m: grade(m, v) for m, v in metrics.items()}
    grades.update({
        "V1": grade("V1", n_valid), "V2": grade("V2", n_valid / len(cards)), "V3": grade("V3", 1 - len(non5) / max(n_valid, 1)),
        "V4": grade("V4", n_lit / n_claims if n_claims else None), "K": grade("K", n_false), "L": "nach Handlesung",
    })  # fmt: skip
    stops: list[str] = []
    if n_valid < 270 or any(v[0] < 0.7 * v[1] for v in per_stratum_valid.values()):
        stops.append("A1")
    if scale["sd_new"] < 0.6 * scale["sd_old"] or mode_n > 0.4 * len(new_prim):
        stops.append("A4")
    if form_break > 0.05 * len(cards):
        stops.append("A5")
    if file_gap_primary > 4:
        stops.append("A6")
    return {
        "hashes": hashes, "n_cards": len(cards), "n_valid": n_valid, "per_stratum_valid": per_stratum_valid,
        "parse_errors": parse_errors, "duplicates": duplicates, "non_multiple_5": non5,
        "plan_problems": {c["id"]: c["problems"] for c in cards if c["problems"]},
        "schema_problems": {c["id"]: c["schema_problems"] for c in cards if c["schema_problems"]},
        "claims_total": n_claims, "quotes_literal": n_lit, "strata": strata_out, "primary": prim, "all300": all300,
        "rest_land": rl, "weighted_primary": weighted, "metrics": metrics, "grades": grades, "sub": sub,
        "sub_grade": sub_grade, "lands": lands, "flagged": flag, "flagged_rows": frows, "fatigue": fatigue,
        "file_gap_primary": file_gap_primary, "file_gap_all": file_gap_all, "scale": scale, "blindness_hits": blind,
        "claim_sample": claim_sample, "claim_verdicts": dict(verdict_counts) if verdict_counts is not None else None,
        "per_card_spread": prim["rms"] / math.sqrt(2), "stops": stops, "top_deviations": top_out,
        "verdict_if_blindness_not_red": overall_verdict({**grades, "L": "gruen"}, stops),
    }  # fmt: skip


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rr-dir", type=Path, required=True)
    ap.add_argument("--old", type=Path, required=True)
    ap.add_argument("--flagged", type=Path, required=True)
    ap.add_argument("--verdicts", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    verdicts = json.loads(args.verdicts.read_text(encoding="utf-8")) if args.verdicts else None
    result = analyse(args.rr_dir, args.old, args.flagged, verdicts)
    args.out.write_text(
        json.dumps(result, indent=1, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    m, g = result["metrics"], result["grades"]
    for k in sorted(m):
        print(f"{k} {m[k]:.3f} {g[k]}")
    print(
        "stops:",
        result["stops"] or "none",
        "| verdict (blindness not red):",
        result["verdict_if_blindness_not_red"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
