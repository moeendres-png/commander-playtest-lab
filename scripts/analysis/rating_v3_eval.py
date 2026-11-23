#!/usr/bin/env python3
"""Evaluation of the rating run v3 of H (Chulane, three raters A/B/C, Refs #1404), following the
plan fixed before any v3 output existed: ``docs/analysis-reports/rating_v3_plan_20261123.md``
(I2, I5, I6, sections 3, 4, 5 and 6). The script changes no threshold, set, formula or rule of
the plan (A8): every threshold is a named constant below and none is a command-line option.

Every rating is an absolute value per card; the script never compares two cards.

Commands (all behind the freeze guard; plan section 5, order of steps 4 to 6):

  hits        Stage 1. Prints ONLY the hits of the fixed reference list (``EARLIER`` of the
              wave-1 script) in the raters' own text fields (card line ``reason``,
              ``uncertainty``, ``rule_claims[].claim``, ``pattern_check[].why``, every unknown
              key; ``note`` of each criterion line; raw text of every line that is no valid
              part of a card, with values blanked; the final reply). Digits outside the matched
              word are blanked in every printed sentence, so no value is printed. No value, no
              aggregate, no difference is read into the output.
  claims      Rule-claim sample (plan section 5): 60 claims, 20 per rater, at most one per card,
              ``random.Random(20261131)``; a blind list (no rater, no value) and a separate key.
  adjudicate  I6: after the classification, the cards whose rater spread on H_v3b is >= 15, in
              groups of at most 10 per instance; per card the card block and the ratings with
              reasons, WITHOUT rater identity, plus a separate key (rating number -> rater).
  eval        Stage 2. Refuses without the classification of exactly the recomputed hits (and
              its SHA-256 as posted in #1404). Then validity and chunk rules A1-A11, I5
              aggregation (median per criterion over A/B/C, then H per V3a/V3b/V3c), S1-S9 per
              variant BEFORE adjudication, anchor strike list, decision rule (pilot: only V3b;
              full run: variant choice V3b, V3a, V3c with the display condition), I6 result,
              sensitivities, report template (JSON + Markdown), derived H file, SHA-256 list.

Freeze guard: every ``v3_output_<R>_<k>.jsonl``, ``v3_transcript_<R>_<k>.jsonl`` and
``v3_meta_<R>_<k>.json`` in the analyst folder must be in the checksum list (``sha256sum``
format; the last hash of a name counts); a listed file that is missing, an unlisted present file,
an unknown name or a differing hash stops the script before any output line is parsed. The
manifest must match the SHA-256 pinned in ``PINNED_MANIFEST_SHA256`` (empty until the Guide-v3
PR commits it: the script refuses until then), and every input, guide, schema and instruction
file named in the manifest must match its SHA-256 there. ``pooled.jsonl`` is pinned in full;
``usage_holdout.jsonl`` and A1 ``pairs.jsonl`` (not in the repository) only by the SHA-256 prefix
published in report A1 (weak pin, see the PR text).

Transcripts are never parsed: only their SHA-256 enters the freeze. The blindness scan of S8
reads ``--tool-calls``, a list the Co-Lead extracts from the harness transcripts:
  {"ordner": {"A:1": "<absolute folder of instance A, chunk 1>", ...},
   "aufrufe": [{"instanz": "A:1", "werkzeug": "Read", "pfad": "<path>"}, ...]}
Only ``Read`` and ``Write`` inside the instance's own folder are allowed. Any other key of an
entry (for example a write content) is ignored and never printed.

Manifest (``rating-v3-manifest-1``, written by the Guide-v3 PR; this script defines the contract):
  {"schema": "rating-v3-manifest-1", "phase": "pilot" | "vollauf", "pilot_runde": 1 | 2,
   "dateien": {"<file name>": "<sha256>"},
   "karten": {"<oracle_id>": {"card": str, "art": "kreatur" | "nicht_kreatur" | "land",
              "schicht": str, "anker": null | {"satz": "alt" | "neu", "zeilen": {"E": 75, ...}}}},
   "chargen": [{"k": 1, "tranche": 1, "karten": [oracle_id, ...],
                "reihenfolge": {"A": [oracle_id, ...], "B": [...], "C": [...]},
                "eingabe": {"A": "<input file name>", "B": ..., "C": ...}}]}
An input file is JSON Lines ``{"seq", "oracle_id", "card", "card_block"}`` in the rater's order.

Output contract (plan I3, one value per line): per card first a card line (an object WITHOUT
``criterion``: ``oracle_id``, ``reason``, ``confidence``, ``uncertainty``, ``rule_claims``,
``pattern_check``), then one line per criterion in the fixed order E, F, T, R, K, N and last the
H line (V3a): ``{"criterion", "note", "value"}``. Lines are assembled by position: each card line
opens the next card of the rater's order. A card is valid (A1) with its card line, all six
criterion lines and the H line in this order, every value an integer 0-100 and ``oracle_id``
matching. Values that are no multiple of 5 are rounded half up and counted (A5).

Run log (``--run-log``, the Co-Lead's scratchpad form; it may hold model IDs, which are never
written to any output): {"laufprotokoll_vorhanden": bool, "hash_kommentar": str,
"skript_vor_oeffnen_committet": bool, "hashes_vor_oeffnen_gepostet": bool,
"a8_abweichungen": [str], "instanzen": {"A:1": {"modell_id", "stufe", "version", "aufwand",
"agent_id", "meta_sha256", "transkript_sha256": str, "a2_verstoesse_frueher": int,
"abbrueche_a7": int, "nachlauf_a1": bool}}}. A missing key takes the strict consequence (A3,
"unbekannt", or refusal where the freeze list shows a repeat).

Standard library only, deterministic (two runs give byte-identical files): every interval uses a
fresh ``random.Random(20261127)`` and 2000 draws (95 % percentile); no time stamps, base names.

Usage:
  python3 scripts/analysis/rating_v3_eval.py hits --manifest M --inputs-dir I --rater-dir R \\
      --checksums SUMS --final-replies F --out hits.json
  python3 scripts/analysis/rating_v3_eval.py claims --manifest M --inputs-dir I --rater-dir R \\
      --checksums SUMS --out claims_blind.json --key-out claims_key.json
  python3 scripts/analysis/rating_v3_eval.py adjudicate <hits args> --hits hits.json \\
      --classification C --classification-sha256 X --out adj_blind.json --key-out adj_key.json
  python3 scripts/analysis/rating_v3_eval.py eval <hits args> --hits hits.json \\
      --classification C --classification-sha256 X --tool-calls T --run-log L \\
      [--usage U] [--old-runs P] [--pooled POOLED] [--claim-verdicts V] \\
      [--adjudication-key K --adjudication-verdicts AV] \\
      --out result.json --report report.md --h-out h_v3.jsonl --sums-out SHA256SUMS
"""

from __future__ import annotations

import argparse
import json
import math
import posixpath
import random
import re
import statistics
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, TypeGuard

sys.path.insert(0, str(Path(__file__).resolve().parent))

import rating_second_run_full_eval as ev2  # wave-2 chain: freeze, hits, classification, bootstrap
import second_run_compare as w1  # wave-1 script: regexes, ranks, percentile interval

SCHEMA_MANIFEST = "rating-v3-manifest-1"
SCHEMA_HITS = "rating-v3-verweis-treffer-1"
SCHEMA_RESULT = "rating-v3-auswertung-1"
RATERS = ("A", "B", "C")
CRITERIA = ("E", "F", "T", "R", "K", "N")
LINE_ORDER = (*CRITERIA, "H")
KINDS = ("kreatur", "nicht_kreatur", "land")
VARIANTS = ("V3b", "V3a", "V3c")  # rank order of the variant choice (plan section 4)
RATER_PAIRS = (("A", "B"), ("A", "C"), ("B", "C"))
CARD_KEYS = ("oracle_id", "reason", "confidence", "uncertainty", "rule_claims", "pattern_check")
CRIT_KEYS = ("criterion", "note", "value")

# Seeds and draws (plan sections 3 and 5). None is a command-line option.
SEED_BOOT = 20261127
DRAWS = 2000
SEED_CLAIMS = 20261131

# Formula (plan I2): H_ref = 0.3 E + 0.3 F + 0.2 R + 0.1 T + 0.1 K - 0.2 N, bounded to 0..100.
WEIGHTS = {"E": 0.3, "F": 0.3, "R": 0.2, "T": 0.1, "K": 0.1}
WEIGHTS_EQUAL = {"E": 0.2, "F": 0.2, "R": 0.2, "T": 0.2, "K": 0.2}  # sensitivity only
N_WEIGHT = 0.2
CORRIDOR = 10.0  # V3a: H_raw clamped to H_ref +/- 10; a break is |H_raw - H_ref| > 10
CORRIDOR_GROSS = 15.0  # S4: gross corridor break |H_raw - H_ref| > 15

# Success criteria (plan section 3). Comparison operators are part of the rule.
S1_POINT_MIN = 0.87  # S1: ICC(2,1) >= 0.87
S1_LOWER_MIN = 0.80  # S1: lower 95 % bound >= 0.80
S2_MAX = 0.39  # S2 (Soll, reported): mean pairwise |delta| / pooled SD <= 0.39
S3_SD_MAX = 0.15  # S3: failed when |contrast| / SD > 0.15 ...
S3_CRIT = 2.50  # ... and |contrast| / Welch SE > 2.50 (Bonferroni over 3 rater pairs)
S3C_CRIT = 2.75  # S3c (reported only): land contrasts, Bonferroni over 6 (v3_baselines.py)
S4_SHARE_MAX = 0.05  # S4 (V3a): share of gross corridor breaks <= 5 % per rater
S5_MAE_MAX = 6.0  # S5: MAE of the hidden anchors (first placement) <= 6
S6_SLOPE_MAX = 1.5  # S6: failed when |slope x 10| > 1.5 ...
S6_CRIT = 2.44  # ... and |slope| / SE > 2.44 (t quantile 1 - 0.05/6, 88 df; Bonferroni over 3)
S6_PER_POSITIONS = 10.0
S7_POINT_MIN = -0.05  # S7: Spearman difference >= -0.05 ...
S7_LOWER_MIN = -0.15  # ... and lower 95 % bound >= -0.15
S8_MAX = 0  # S8: counting reference hits and transcript violations
S9_R_MAX = 0.90  # S9: highest |r| of two criteria < 0.90
DISPLAY_LOSS_MIN = -0.10  # section 6: Spearman(H_v3) - Spearman(H_pooled) >= -0.10
FLAG_SPREAD = 15.0  # I6: rater spread on H_v3b >= 15 -> mark and adjudication
ADJ_GROUP = 10  # I6 / section 4: at most 10 cards per adjudication instance
ANCHOR_STRIKE_GAP = 10.0  # I2 no. 10: rater mean more than 10 from the anchor value, or ...
ANCHOR_HIT_WINDOW = 10.0  # ... fewer than 2 of 3 raters within +/- 10
ANCHOR_MIN_HITS = 2
OFFSET_CORRECTION_GAP = 2.0  # I5: offset per card kind on the anchors > 2 with CI without 0

# Chunk and validity rules (plan section 5, A1-A11).
MAX_CHUNK_CARDS = 20
PILOT_CHUNKS = 6
A1_VALID_SHARE = 0.90
A4_SD_RATIO = 0.6
A4_MODE_SHARE = 0.40
A5_FORMAT_SHARE = 0.05
A6_CHUNK_GAP = 4.0
A9_TRANCHE_GAP = 3.0
A11_MIN_VALID_CHUNKS = 5
CLAIMS_PER_RATER = 20
CLAIM_GREEN_MAX = 1  # green: at most 1 of 20 obviously wrong
CLAIM_RED_MIN = 3  # red: at least 3 of 20
ALLOWED_TOOLS = frozenset({"Read", "Write"})
RUN_LOG_INSTANCE_FIELDS = (
    "modell_id", "stufe", "version", "aufwand", "agent_id", "meta_sha256", "transkript_sha256",
)  # fmt: skip

PILOT_MUST = ("S1", "S3", "S5", "S6", "S8", "S9")
FULL_MUST = ("S1", "S3", "S5", "S6", "S7", "S8", "S9")
FULL_MUST_V3A_EXTRA = ("S4",)

# Pins. The manifest is committed by the Guide-v3 PR; its SHA-256 must be entered here (by phase)
# before any v3 output is opened. Until then every command refuses.
PINNED_MANIFEST_SHA256: dict[str, str] = {}
POOLED_SHA256 = "3e6d82d0d7c4d3e46bc069ce000ac45d1c96cca994036f434ca449f35ff2b8c3"
USAGE_SHA256_PREFIX = "c3d1f693"  # report A1 section 7 (prefix only)
OLD_RUNS_SHA256_PREFIX = "89f85818"  # A1 pairs.jsonl, report A1 section 7 (prefix only)

UNKNOWN = "unbekannt"
OK = "erfuellt"
FAIL = "verfehlt"
EARLIER = w1.EARLIER

RefusedError = ev2.RefusedError
sha256_bytes = ev2.sha256_bytes
sha256_file = ev2.sha256_file
load_jsonl = ev2.load_jsonl
clean = ev2.clean
dumps = ev2.dumps
parse_checksums = ev2.parse_checksums


def interval(values: Sequence[float]) -> list[float | None]:
    return ev2.interval(values)


def inst(r: str, k: int) -> str:
    return f"{r}:{k}"


# ---------------------------------------------------------------- formula and aggregation (I2, I5)


def clamp01(x: float) -> float:
    return min(100.0, max(0.0, x))


def h_ref(c: Mapping[str, float], weights: Mapping[str, float] = WEIGHTS) -> float:
    """H_ref = 0.3 E + 0.3 F + 0.2 R + 0.1 T + 0.1 K - 0.2 N, bounded to 0..100, unrounded."""
    return clamp01(sum(w * c[x] for x, w in weights.items()) - N_WEIGHT * c["N"])


def h_v3c(c: Mapping[str, float]) -> float:
    """V3c: the set weights without N, bounded to 0..100."""
    return clamp01(sum(w * c[x] for x, w in WEIGHTS.items()))


def clamp_corridor(h_raw: float, ref: float) -> float:
    """V3a: H_raw clamped to H_ref +/- 10."""
    return min(ref + CORRIDOR, max(ref - CORRIDOR, h_raw))


def rater_variants(vals: Mapping[str, float]) -> dict[str, float]:
    """The three H values of ONE rater from his own criteria (V3a uses his H_raw)."""
    ref = h_ref(vals)
    return {"V3b": ref, "V3a": clamp_corridor(vals["H"], ref), "V3c": h_v3c(vals)}


def combine(values: Sequence[float]) -> float | None:
    """I5: median of three; mean of two (``n_rater = 2``); one or none: no value."""
    if len(values) >= 3:
        return float(statistics.median(values))
    if len(values) == 2:
        return (values[0] + values[1]) / 2
    return None


def aggregate(per_rater: Mapping[str, Mapping[str, float]]) -> dict[str, Any]:
    """I5 for one card. ``per_rater``: rater -> values E..N and H (valid ratings only).
    Median per criterion FIRST, then the formula (V3b, V3c); V3a is the median of the clamped
    H of each rater."""
    rs = sorted(per_rater)
    n = len(rs)
    out: dict[str, Any] = {"n_rater": n, "rater": rs}
    if n < 2:
        out.update({"kriterien": None, "V3b": None, "V3a": None, "V3c": None})
        return out
    med = {c: combine([float(per_rater[r][c]) for r in rs]) for c in CRITERIA}
    crit = {c: float(v) for c, v in med.items() if v is not None}
    rv = {r: rater_variants(per_rater[r]) for r in rs}
    out["kriterien"] = crit
    out["V3b"] = h_ref(crit)
    out["V3c"] = h_v3c(crit)
    out["V3a"] = combine([rv[r]["V3a"] for r in rs])
    out["V3b_gleiche_gewichte"] = h_ref(crit, WEIGHTS_EQUAL)
    return out


def aggregate_mean(per_rater: Mapping[str, Mapping[str, float]]) -> float | None:
    """Sensitivity: mean instead of median per criterion, then V3b."""
    rs = sorted(per_rater)
    if len(rs) < 2:
        return None
    return h_ref({c: sum(float(per_rater[r][c]) for r in rs) / len(rs) for c in CRITERIA})


# ---------------------------------------------------------------- statistics


def icc21_k(rows: Sequence[Sequence[float]]) -> float:
    """ICC(2,1), two-way random, absolute agreement, single rater; n cards x k raters."""
    n = len(rows)
    if n < 3:
        return float("nan")
    k = len(rows[0])
    grand = sum(sum(r) for r in rows) / (n * k)
    rm = [sum(r) / k for r in rows]
    cm = [sum(r[j] for r in rows) / n for j in range(k)]
    msr = k * sum((m - grand) ** 2 for m in rm) / (n - 1)
    msc = n * sum((m - grand) ** 2 for m in cm) / (k - 1)
    sse = sum((rows[i][j] - rm[i] - cm[j] + grand) ** 2 for i in range(n) for j in range(k))
    mse = sse / ((n - 1) * (k - 1))
    den = msr + (k - 1) * mse + k * (msc - mse) / n
    return (msr - mse) / den if den else float("nan")


def boot_ci(
    items: Sequence[Any], fn: Callable[[list[Any]], float], draws: int
) -> list[float | None]:
    """Bootstrap over cards, fresh ``random.Random(20261127)``, 95 % percentile interval."""
    if not items:
        return [None, None]
    rng = random.Random(SEED_BOOT)
    vals = list(items)
    return interval([fn(rng.choices(vals, k=len(vals))) for _ in range(draws)])


def pstd(values: Sequence[float]) -> float:
    return statistics.pstdev(values) if len(values) > 1 else float("nan")


def nan_none(x: float) -> float | None:
    return None if math.isnan(x) or math.isinf(x) else x


def status(ok: bool | None) -> str:
    return UNKNOWN if ok is None else (OK if ok else FAIL)


def s1(rows: Sequence[Sequence[float]], draws: int, blocked: bool) -> dict[str, Any]:
    """S1: ICC(2,1) between A, B, C; point >= 0.87 and lower bound >= 0.80 (Muss)."""
    point = icc21_k(rows) if len(rows) >= 3 else float("nan")
    ci = boot_ci(rows, icc21_k, draws) if len(rows) >= 3 else [None, None]
    ok: bool | None = None
    if not blocked and not math.isnan(point) and ci[0] is not None:
        ok = point >= S1_POINT_MIN and ci[0] >= S1_LOWER_MIN
    return {"n": len(rows), "icc21": nan_none(point), "ci95": ci, "status": status(ok),
            "schwelle": {"punkt_min": S1_POINT_MIN, "untere_grenze_min": S1_LOWER_MIN},
            "kein_schluss_rater_ausgefallen": blocked}  # fmt: skip


def s2(rows: Sequence[Sequence[float]]) -> dict[str, Any]:
    """S2 (Soll, reported): mean pairwise |delta| over the three pairs / pooled SD (population SD
    of all 3 x n values, as v3_baselines.py)."""
    if len(rows) < 2:
        return {"n": len(rows), "wert": None, "punkte": None, "status": UNKNOWN, "soll": True}
    pts = statistics.fmean(
        statistics.fmean(abs(r[a] - r[b]) for r in rows) for a, b in ((0, 1), (0, 2), (1, 2))
    )
    sd = pstd([v for r in rows for v in r])
    val = pts / sd if sd and not math.isnan(sd) else float("nan")
    ok = None if math.isnan(val) else val <= S2_MAX
    return {"n": len(rows), "wert": nan_none(val), "punkte": pts, "sd_gepoolt": nan_none(sd),
            "status": status(ok), "soll": True, "schwelle_max": S2_MAX}  # fmt: skip


def welch(ga: Sequence[float], gb: Sequence[float]) -> tuple[float, float]:
    """Contrast mean(ga) - mean(gb) and its Welch standard error (ddof = 1)."""
    c = statistics.fmean(ga) - statistics.fmean(gb)
    se = math.sqrt(statistics.variance(ga) / len(ga) + statistics.variance(gb) / len(gb))
    return c, se


def contrast_flag(c: float, se: float, sd: float, crit: float) -> tuple[float, float, bool]:
    in_sd = c / sd
    z = abs(c) / se if se > 0 else (math.inf if c != 0 else 0.0)
    return in_sd, z, abs(in_sd) > S3_SD_MAX and z > crit


def s3(rows: Sequence[Sequence[float]], kinds: Sequence[str]) -> dict[str, Any]:
    """S3: per rater pair the differential offset creature minus non-creature spell, in pooled SD;
    failed when for one pair |.| > 0.15 SD AND |.| / Welch SE > 2.50. S3c (land contrasts) and
    S3b (even offset per pair) are reported only and never decide."""
    sd = pstd([v for r in rows for v in r])
    out: dict[str, Any] = {"n": len(rows), "sd_gepoolt": nan_none(sd), "paare": {},
                           "schwelle": {"sd_max": S3_SD_MAX, "kritischer_wert": S3_CRIT}}  # fmt: skip
    idx = {r: i for i, r in enumerate(RATERS)}
    fails: list[bool] = []
    known = len(rows) >= 2 and sd > 0 and not math.isnan(sd)
    for a, b in RATER_PAIRS:
        d = [r[idx[a]] - r[idx[b]] for r in rows]
        groups = {kd: [x for x, k in zip(d, kinds, strict=True) if k == kd] for kd in KINDS}
        entry: dict[str, Any] = {"n_je_art": {kd: len(v) for kd, v in groups.items()}}
        entry["S3b_gleichmaessig_in_sd"] = statistics.fmean(d) / sd if known and d else None
        if known and len(groups["kreatur"]) >= 2 and len(groups["nicht_kreatur"]) >= 2:
            c, se = welch(groups["kreatur"], groups["nicht_kreatur"])
            in_sd, z, flag = contrast_flag(c, se, sd, S3_CRIT)
            entry.update({"kontrast_punkte": c, "kontrast_in_sd": in_sd, "z": z, "verfehlt": flag})
            fails.append(flag)
        else:
            entry["verfehlt"] = None
            known = False
        s3c: dict[str, Any] = {}
        for x, y in (("kreatur", "land"), ("nicht_kreatur", "land")):
            if known and len(groups[x]) >= 2 and len(groups[y]) >= 2:
                c, se = welch(groups[x], groups[y])
                in_sd, z, flag = contrast_flag(c, se, sd, S3C_CRIT)
                s3c[f"{x}_gegen_{y}"] = {"kontrast_in_sd": in_sd, "z": z, "auffaellig": flag}
            else:
                s3c[f"{x}_gegen_{y}"] = UNKNOWN
        entry["S3c_nur_berichtet"] = s3c
        out["paare"][f"{a}-{b}"] = entry
    ok: bool | None = None
    if any(fails):
        ok = False
    elif known and len(fails) == len(RATER_PAIRS):
        ok = True
    out["status"] = status(ok)
    return out


def s4(records: Mapping[str, Sequence[tuple[float, float]]]) -> dict[str, Any]:
    """S4 (V3a only): per rater the share of cards with |H_raw - H_ref| > 15 must be <= 5 %;
    corridor breaks (> 10) are reported. ``records``: rater -> [(H_raw, H_ref)]."""
    out: dict[str, Any] = {"je_rater": {}, "schwelle_anteil_max": S4_SHARE_MAX}
    oks: list[bool] = []
    for r in RATERS:
        rows = records.get(r, [])
        n = len(rows)
        gross = sum(abs(h - ref) > CORRIDOR_GROSS for h, ref in rows)
        brk = sum(abs(h - ref) > CORRIDOR for h, ref in rows)
        # integer arithmetic: gross / n <= 0.05  <=>  100 * gross <= 5 * n
        ok = None if n == 0 else 100 * gross <= round(100 * S4_SHARE_MAX) * n
        out["je_rater"][r] = {"n": n, "grob_gt15": gross, "bruch_gt10": brk,
                              "anteil_grob": gross / n if n else None, "status": status(ok)}  # fmt: skip
        if ok is not None:
            oks.append(ok)
    out["status"] = status(False if not all(oks) else (True if len(oks) == len(RATERS) else None))
    return out


def s5(terms: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """S5: MAE of the median aggregate against the anchor value over the FIRST placement of every
    hidden anchor card x all its criteria with an anchor line; <= 6."""
    errs = [abs(t["aggregat"] - t["ankerwert"]) for t in terms if t["aggregat"] is not None]
    n_all = len(terms)
    mae = statistics.fmean(errs) if errs else None
    ok = None if mae is None or len(errs) < n_all else mae <= S5_MAE_MAX
    out: dict[str, Any] = {"n_terme": len(errs), "N_terme": n_all, "mae": mae,
                           "status": status(ok), "schwelle_max": S5_MAE_MAX}  # fmt: skip
    for satz in ("alt", "neu"):
        e = [abs(t["aggregat"] - t["ankerwert"]) for t in terms
             if t["aggregat"] is not None and t["satz"] == satz]  # fmt: skip
        out[f"mae_{satz}"] = {"n": len(e), "mae": statistics.fmean(e) if e else None}
    for r in RATERS:
        e = [abs(t["werte"][r] - t["ankerwert"]) for t in terms if t["werte"].get(r) is not None]
        out[f"mae_rater_{r}"] = {"n": len(e), "mae": statistics.fmean(e) if e else None}
    return out


def ols_slope_se(x: Sequence[float], y: Sequence[float]) -> tuple[float, float]:
    n = len(x)
    mx, my = statistics.fmean(x), statistics.fmean(y)
    sxx = sum((a - mx) ** 2 for a in x)
    if sxx == 0 or n < 3:
        return float("nan"), float("nan")
    slope = sum((a - mx) * (b - my) for a, b in zip(x, y, strict=True)) / sxx
    resid = [(b - my) - slope * (a - mx) for a, b in zip(x, y, strict=True)]
    se = math.sqrt(sum(e * e for e in resid) / (n - 2) / sxx)
    return slope, se


def s6(rows: Sequence[Sequence[float]], positions: Sequence[Sequence[float]]) -> dict[str, Any]:
    """S6: per rater the OLS slope of (rater value - median of the three) on the position, x 10;
    failed when for one rater |.| > 1.5 AND |slope| / SE > 2.44 (t quantile, Bonferroni over 3)."""
    out: dict[str, Any] = {"n": len(rows), "je_rater": {},
                           "schwelle": {"punkte_je_10_max": S6_SLOPE_MAX, "kritischer_wert": S6_CRIT}}  # fmt: skip
    oks: list[bool] = []
    for j, r in enumerate(RATERS):
        e = [row[j] - statistics.median(row) for row in rows]
        pos = [p[j] for p in positions]
        slope, se = ols_slope_se(pos, e) if len(rows) >= 3 else (float("nan"), float("nan"))
        if math.isnan(slope):
            out["je_rater"][r] = {"steigung_je_10": None, "t": None, "verfehlt": None}
            continue
        t = abs(slope) / se if se > 0 else (math.inf if slope != 0 else 0.0)
        flag = abs(S6_PER_POSITIONS * slope) > S6_SLOPE_MAX and t > S6_CRIT
        out["je_rater"][r] = {"steigung_je_10": S6_PER_POSITIONS * slope, "t": nan_none(t),
                              "verfehlt": flag}  # fmt: skip
        oks.append(not flag)
    out["status"] = status(False if not all(oks) else (True if len(oks) == len(RATERS) else None))
    return out


def spearman_diff(
    pairs: Sequence[tuple[float, float, float]], draws: int
) -> tuple[float | None, list[float | None]]:
    """Spearman(x, y) - Spearman(z, y) on the same cards; paired bootstrap over cards.
    ``pairs``: (new value x, reference value z, usage y)."""
    if len(pairs) < 3:
        return None, [None, None]

    def diff(s: Sequence[tuple[float, float, float]]) -> float:
        ys = [p[2] for p in s]
        return w1.spearman([p[0] for p in s], ys) - w1.spearman([p[1] for p in s], ys)

    return nan_none(diff(pairs)), boot_ci(pairs, diff, draws)


def s7(pairs: Sequence[tuple[float, float, float]], draws: int, reason: str | None,
       must: bool) -> dict[str, Any]:  # fmt: skip
    """S7: Spearman(H_v3, source decks) - Spearman(H_old,same, source decks); point >= -0.05 and
    lower bound >= -0.15. Without the usage file or the old runs: 'unbekannt', never 0."""
    if reason is not None:
        return {"n": 0, "differenz": None, "ci95": [None, None], "status": UNKNOWN,
                "grund": reason, "muss": must}  # fmt: skip
    point, ci = spearman_diff(pairs, draws)
    ok = None
    if point is not None and ci[0] is not None:
        ok = point >= S7_POINT_MIN and ci[0] >= S7_LOWER_MIN
    return {"n": len(pairs), "differenz": point, "ci95": ci, "status": status(ok), "muss": must,
            "schwelle": {"punkt_min": S7_POINT_MIN, "untere_grenze_min": S7_LOWER_MIN}}  # fmt: skip


def max_abs_corr(table: Sequence[Mapping[str, float]]) -> tuple[float | None, str | None]:
    best: tuple[float | None, str | None] = (None, None)
    for i, a in enumerate(CRITERIA):
        for b in CRITERIA[i + 1 :]:
            r = w1.pearson([t[a] for t in table], [t[b] for t in table])
            if not math.isnan(r) and (best[0] is None or abs(r) > abs(best[0])):
                best = (r, a + b)
    return best


def s9(agg: Sequence[Mapping[str, float]], per_rater: Mapping[str, Sequence[Mapping[str, float]]]
       ) -> dict[str, Any]:  # fmt: skip
    """S9: highest |r| of two criteria over the median aggregates < 0.90; per rater reported."""
    r, pair = max_abs_corr(agg) if len(agg) >= 3 else (None, None)
    out: dict[str, Any] = {"n": len(agg), "max_r": r, "paar": pair, "schwelle_max": S9_R_MAX,
                           "status": status(None if r is None else abs(r) < S9_R_MAX)}  # fmt: skip
    out["je_rater"] = {
        x: dict(
            zip(("max_r", "paar"), max_abs_corr(v) if len(v) >= 3 else (None, None), strict=True)
        )
        for x, v in sorted(per_rater.items())
    }
    return out


def anchor_strike(terms: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """I2 no. 10: an anchor line (card x criterion) is proposed for striking when, at the first
    placement, the RATER MEAN deviates more than 10 from the anchor value OR fewer than 2 of 3
    raters are within +/- 10 (a missing rater counts as not within)."""
    out = []
    for t in terms:
        vals = [float(v) for v in t["werte"].values() if v is not None]
        mean_v = statistics.fmean(vals) if vals else None
        hits = sum(abs(v - t["ankerwert"]) <= ANCHOR_HIT_WINDOW for v in vals)
        arm_mean = mean_v is None or abs(mean_v - t["ankerwert"]) > ANCHOR_STRIKE_GAP
        arm_hits = hits < ANCHOR_MIN_HITS
        out.append({
            "oracle_id": t["oracle_id"], "card": t["card"], "kriterium": t["kriterium"], "satz": t["satz"],
            "ankerwert": t["ankerwert"], "n_rater": len(vals), "rater_mittel": mean_v,
            "rater_innerhalb_10": hits, "streichen": arm_mean or arm_hits,
            "grund": [g for g, on in (("mittel_gt10", arm_mean), ("weniger_als_2_von_3", arm_hits)) if on],
        })  # fmt: skip
    return out


# ---------------------------------------------------------------- manifest, freeze guard


def output_name(r: str, k: int) -> str:
    return f"v3_output_{r}_{k}.jsonl"


def transcript_name(r: str, k: int) -> str:
    return f"v3_transcript_{r}_{k}.jsonl"


def meta_name(r: str, k: int) -> str:
    return f"v3_meta_{r}_{k}.json"


def load_manifest(path: Path) -> dict[str, Any]:
    digest = sha256_file(path) if path.exists() else "missing"
    try:
        man = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RefusedError(f"manifest unreadable: {exc}") from exc
    if not isinstance(man, dict) or man.get("schema") != SCHEMA_MANIFEST:
        raise RefusedError(f"manifest schema is not {SCHEMA_MANIFEST}")
    phase = man.get("phase")
    if phase not in ("pilot", "vollauf"):
        raise RefusedError("manifest phase must be 'pilot' or 'vollauf'")
    pinned = PINNED_MANIFEST_SHA256.get(str(phase))
    if not pinned:
        raise RefusedError(
            f"no pinned manifest SHA-256 for phase {phase}: commit it in PINNED_MANIFEST_SHA256 "
            "before any v3 output is opened"
        )
    if digest != pinned:
        raise RefusedError(f"manifest {path.name}: {digest} != pinned {pinned}")
    if phase == "pilot" and man.get("pilot_runde") not in (1, 2):
        raise RefusedError("pilot manifest needs pilot_runde 1 or 2")
    cards = man.get("karten")
    chunks = man.get("chargen")
    if not isinstance(cards, dict) or not isinstance(chunks, list) or not chunks:
        raise RefusedError("manifest needs 'karten' and 'chargen'")
    if phase == "pilot" and len(chunks) != PILOT_CHUNKS:
        raise RefusedError(f"pilot manifest must have {PILOT_CHUNKS} chunks")
    seen_plain: Counter[str] = Counter()
    ks = []
    for ch in chunks:
        k = ch.get("k")
        ks.append(k)
        ids = ch.get("karten")
        if not isinstance(k, int) or not isinstance(ids, list) or not ids:
            raise RefusedError("each chunk needs an integer k and a card list")
        if len(ids) > MAX_CHUNK_CARDS or len(set(ids)) != len(ids):
            raise RefusedError(f"chunk {k}: more than {MAX_CHUNK_CARDS} cards or a card twice")
        if phase == "vollauf" and not isinstance(ch.get("tranche"), int):
            raise RefusedError(f"chunk {k}: full-run chunks need a tranche")
        for r in RATERS:
            order = ch.get("reihenfolge", {}).get(r)
            if not isinstance(order, list) or sorted(order) != sorted(ids):
                raise RefusedError(f"chunk {k}: order of rater {r} is no permutation of its cards")
            if not isinstance(ch.get("eingabe", {}).get(r), str):
                raise RefusedError(f"chunk {k}: no input file for rater {r}")
        for o in ids:
            c = cards.get(o)
            if not isinstance(c, dict) or c.get("art") not in KINDS:
                raise RefusedError(f"card {o}: missing or without art in {KINDS}")
            anchor = c.get("anker")
            if anchor is None:
                seen_plain[o] += 1
                continue
            rows = anchor.get("zeilen") if isinstance(anchor, dict) else None
            if (
                not isinstance(rows, dict) or not rows or anchor.get("satz") not in ("alt", "neu")
                or any(x not in CRITERIA or not isinstance(v, int) or isinstance(v, bool)
                       for x, v in rows.items())
            ):  # fmt: skip
                raise RefusedError(f"anchor {o}: needs satz alt/neu and integer lines E..N")
    if ks != sorted(set(ks)):
        raise RefusedError("chunk numbers must be unique and ascending")
    twice = sorted(o for o, n in seen_plain.items() if n > 1)
    if twice:
        raise RefusedError(f"non-anchor cards in more than one chunk: {twice}")
    man["_sha256"] = digest
    return man


def verify_inputs(man: Mapping[str, Any], inputs_dir: Path) -> dict[str, str]:
    """Every file named in the manifest (inputs, guides, schema, instructions) byte-identical."""
    files = man.get("dateien")
    if not isinstance(files, dict) or not files:
        raise RefusedError("manifest names no input files ('dateien')")
    named = {str(ch["eingabe"][r]) for ch in man["chargen"] for r in RATERS}
    missing_pin = sorted(named - set(files))
    if missing_pin:
        raise RefusedError(f"input files without SHA-256 in the manifest: {missing_pin}")
    out, problems = {}, []
    for name, expected in sorted(files.items()):
        p = inputs_dir / name
        digest = sha256_file(p) if p.exists() else "missing"
        out[name] = digest
        if digest != expected:
            problems.append(f"{name}: {digest} != manifest {expected}")
    if problems:
        raise RefusedError("inputs differ from the manifest: " + "; ".join(problems))
    return out


def freeze_guard(
    man: Mapping[str, Any], rater_dir: Path, checksums: Mapping[str, Sequence[str]]
) -> dict[str, str]:
    """SHA-256 of every present output, transcript and meta file against the frozen list."""
    expected = {
        fn(r, ch["k"]) for ch in man["chargen"] for r in RATERS
        for fn in (output_name, transcript_name, meta_name)
    }  # fmt: skip
    present = {p.name for p in rater_dir.iterdir() if p.is_file() and p.name.startswith("v3_")}
    problems = []
    frozen: dict[str, str] = {}
    for name in sorted(expected | present):
        listed = checksums.get(name)
        path = rater_dir / name
        if name not in expected:
            problems.append(f"{name}: no output, transcript or meta file of this manifest")
            continue
        if not path.exists():
            if listed:
                problems.append(f"{name}: listed as frozen but missing")
            continue
        digest = sha256_file(path)
        if not listed:
            problems.append(f"{name}: present but not frozen (not in the checksum list)")
        elif digest != listed[-1]:
            problems.append(f"{name}: SHA-256 {digest} differs from the last frozen hash")
        else:
            frozen[name] = digest
    unknown = sorted(set(checksums) - expected)
    if unknown:
        problems.append(f"checksum list names files outside this manifest: {unknown}")
    if problems:
        raise RefusedError("freeze guard: " + "; ".join(problems))
    return frozen


def verify_pinned(path: Path, role: str, *, full: str | None = None,
                  prefix: str | None = None) -> str:  # fmt: skip
    digest = sha256_file(path) if path.exists() else "missing"
    if (full is not None and digest != full) or (
        prefix is not None and not digest.startswith(prefix)
    ):
        raise RefusedError(f"{role} {path.name}: SHA-256 {digest} does not match the pin")
    return digest


# ---------------------------------------------------------------- loading outputs (I3 contract)


def _int_value(v: Any) -> TypeGuard[int]:
    return isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 100


def parse_output(lines: Sequence[str], order: Sequence[str]) -> dict[str, Any]:
    """Assemble the one-value lines per card by position (module docstring)."""
    cards: list[dict[str, Any]] = [
        {"oracle_id": o, "pos": i, "card_row": None, "lines": [], "raw": []}
        for i, o in enumerate(order, 1)
    ]
    cur = -1
    orphans: list[str] = []
    extra_cards = 0
    for line in lines:
        if not line.strip():
            continue
        try:
            obj: Any = json.loads(line)
        except json.JSONDecodeError:
            obj = None
        is_card = isinstance(obj, dict) and "criterion" not in obj
        if is_card:
            cur += 1
            if cur >= len(cards):
                extra_cards += 1
                orphans.append(line)
                continue
            cards[cur]["card_row"] = obj
            cards[cur]["raw"].append(line)
            continue
        if 0 <= cur < len(cards):
            cards[cur]["lines"].append(obj)
            cards[cur]["raw"].append(line)
        else:
            orphans.append(line)
    for c in cards:
        problems: list[str] = []
        vals: dict[str, float] = {}
        notes: dict[str, str] = {}
        non5 = 0
        row = c["card_row"]
        if row is None:
            problems.append("missing")
        else:
            if row.get("oracle_id") != c["oracle_id"]:
                problems.append("oracle_id")
            lines_ok = len(c["lines"]) == len(LINE_ORDER)
            for i, crit in enumerate(LINE_ORDER):
                obj = c["lines"][i] if i < len(c["lines"]) else None
                if not isinstance(obj, dict):
                    problems.append(f"{crit}: missing or not JSON")
                    continue
                if obj.get("criterion") != crit:
                    problems.append(f"{crit}: order")
                    continue
                v = obj.get("value")
                if not _int_value(v):
                    problems.append(f"{crit}: value")
                    continue
                if v % 5:
                    non5 += 1
                vals[crit] = float(w1.round5(v))
                notes[crit] = str(obj.get("note", ""))
            if not lines_ok:
                problems.append(f"lines: {len(c['lines'])} != {len(LINE_ORDER)}")
        schema = sorted(k for k in CARD_KEYS if row is not None and k not in row)
        c.update({"problems": sorted(set(problems)), "valid": not problems, "werte": vals,
                  "notizen": notes, "nicht_vielfache_5": non5, "schema_maengel": schema})  # fmt: skip
    return {"cards": cards, "orphans": orphans, "extra_cards": extra_cards}


def load_all(
    man: Mapping[str, Any], inputs_dir: Path, rater_dir: Path, frozen: Mapping[str, str]
) -> dict[str, dict[int, dict[str, Any]]]:
    """Per rater and chunk: parsed output (or all cards missing without a frozen output) plus the
    rater's input rows (card blocks), checked against the manifest order."""
    out: dict[str, dict[int, dict[str, Any]]] = {r: {} for r in RATERS}
    for ch in man["chargen"]:
        k = ch["k"]
        for r in RATERS:
            order = [str(o) for o in ch["reihenfolge"][r]]
            inputs = load_jsonl(inputs_dir / ch["eingabe"][r])
            if [i.get("oracle_id") for i in inputs] != order:
                raise RefusedError(f"chunk {k}, rater {r}: input order differs from the manifest")
            name = output_name(r, k)
            present = name in frozen
            lines = (rater_dir / name).read_text(encoding="utf-8").splitlines() if present else []
            parsed = parse_output(lines, order)
            parsed.update({"present": present, "n_lines": len(lines),
                           "blocks": {str(i["oracle_id"]): str(i.get("card_block", "")) for i in inputs}})  # fmt: skip
            out[r][k] = parsed
    return out


# ---------------------------------------------------------------- stage 1: reference hits

_VALUE_JSON = re.compile(r'"(value|[EFTRKNH])"\s*:\s*-?\d+(?:\.\d+)?')
_DIGITS = re.compile(r"\d+")


def blank_digits(text: str, keep: tuple[int, int] | None = None) -> str:
    """Digits blanked as '#', except inside the matched span ``keep`` (e.g. 'v1', 'F1')."""

    def rep(m: re.Match[str]) -> str:
        if keep and m.start() >= keep[0] and m.end() <= keep[1]:
            return m.group(0)
        return "#"

    return _DIGITS.sub(rep, text)


def card_fields(row: Mapping[str, Any]) -> list[tuple[str, str]]:
    """The rater's own text fields of a card line; never ``rule_claims[].quote``."""
    out: list[tuple[str, str]] = []
    for key in ("reason", "uncertainty"):
        if key in row:
            out.append((key, str(row[key])))
    claims = row.get("rule_claims")
    if isinstance(claims, list):
        for i, c in enumerate(claims):
            if isinstance(c, Mapping):
                if "claim" in c:
                    out.append((f"rule_claims[{i}].claim", str(c["claim"])))
                for extra in sorted(
                    str(x) for x in c if x not in ("quote", "claim", "interaction", "basis")
                ):
                    out.append((f"rule_claims[{i}].{extra}", str(c[extra])))
            else:
                out.append((f"rule_claims[{i}]", str(c)))
    elif "rule_claims" in row:
        out.append(("rule_claims", str(claims)))
    pc = row.get("pattern_check")
    if isinstance(pc, list):
        for i, c in enumerate(pc):
            if isinstance(c, Mapping):
                if "why" in c:
                    out.append((f"pattern_check[{i}].why", str(c["why"])))
            else:
                out.append((f"pattern_check[{i}]", str(c)))
    elif "pattern_check" in row:
        out.append(("pattern_check", str(pc)))
    for extra in sorted(str(x) for x in row if x not in CARD_KEYS and x != "card"):
        out.append((f"zusatzfeld.{extra}", str(row[extra])))
    return out


def find_hits(
    data: Mapping[str, Mapping[int, Mapping[str, Any]]], final_replies: Mapping[str, str]
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []

    def add(r: str, k: int, pos: int, oid: str, field: str, text: str) -> None:
        for m in EARLIER.finditer(text):
            sent = ev2.sentence_at(text, m.start())
            off = text.find(sent)
            keep = (m.start() - off, m.end() - off) if off >= 0 else None
            hits.append({
                "id": f"{r}:{k}:{pos}:{field}:{m.start()}", "rater": r, "charge": k, "pos": pos,
                "oracle_id": oid, "feld": field, "treffer": m.group(0), "satz": blank_digits(sent, keep),
            })  # fmt: skip

    for r in RATERS:
        for k in sorted(data[r]):
            ch = data[r][k]
            for c in ch["cards"]:
                row = c["card_row"]
                if isinstance(row, Mapping):
                    for field, text in card_fields(row):
                        add(r, k, c["pos"], c["oracle_id"], field, text)
                for obj in c["lines"]:
                    if isinstance(obj, Mapping):
                        crit = str(obj.get("criterion", "?"))
                        if "note" in obj:
                            add(r, k, c["pos"], c["oracle_id"], f"{crit}.note", str(obj["note"]))
                        for extra in sorted(
                            str(x) for x in obj if x not in CRIT_KEYS and x != "oracle_id"
                        ):
                            add(r, k, c["pos"], c["oracle_id"], f"{crit}.{extra}", str(obj[extra]))
                if not c["valid"]:
                    for i, line in enumerate(c["raw"]):
                        add(
                            r,
                            k,
                            c["pos"],
                            c["oracle_id"],
                            f"rohzeile[{i}]",
                            _VALUE_JSON.sub(r'"\1": "-"', line),
                        )
            for i, line in enumerate(ch["orphans"]):
                add(r, k, 0, "", f"ohne_karte[{i}]", _VALUE_JSON.sub(r'"\1": "-"', line))
            reply = final_replies.get(inst(r, k))
            if reply:
                add(r, k, 0, "", "schlussantwort", str(reply))
    return hits


def render_hits(hits: Sequence[Mapping[str, Any]], frozen: Mapping[str, str],
                final_replies: Mapping[str, str]) -> bytes:  # fmt: skip
    outputs = {n: v for n, v in sorted(frozen.items()) if n.startswith("v3_output_")}
    scanned = {}
    for n in outputs:
        m = re.fullmatch(r"v3_output_([ABC])_(\d+)\.jsonl", n)
        assert m
        key = inst(m.group(1), int(m.group(2)))
        scanned[key] = bool(final_replies.get(key, "").strip())
    doc = {
        "schema": SCHEMA_HITS, "regex": EARLIER.pattern,
        "felder": "Kartenzeile reason, uncertainty, rule_claims[].claim, pattern_check[].why, unbekannte Felder; "
                  "note je Kriterienzeile; Rohzeilen ungueltiger Karten (Werte geschwaerzt); Schlussantwort; nie quote",
        "eingefrorene_ausgaben_sha256": outputs, "schlussantwort_gescannt": scanned,
        "n_treffer": len(hits), "treffer": list(hits),
        "hinweis": "Nur Verweis-Treffer; Ziffern ausserhalb des Treffers geschwaerzt; keine Bewertung. "
                   "Jeder Treffer wird von Hand eingestuft (zaehlt / zaehlt nicht + a-c, Zweifel zaehlt) "
                   "und in #1404 gepostet.",
    }  # fmt: skip
    return dumps(doc).encode("utf-8")


def stage_inputs(
    manifest_path: Path, inputs_dir: Path, rater_dir: Path, checksums_path: Path
) -> tuple[dict[str, Any], dict[str, str], dict[str, str], dict[str, dict[int, dict[str, Any]]]]:
    man = load_manifest(manifest_path)
    in_hashes = verify_inputs(man, inputs_dir)
    frozen = freeze_guard(
        man, rater_dir, parse_checksums(checksums_path.read_text(encoding="utf-8"))
    )
    data = load_all(man, inputs_dir, rater_dir, frozen)
    return man, in_hashes, frozen, data


def run_hits(manifest_path: Path, inputs_dir: Path, rater_dir: Path, checksums_path: Path,
             final_replies: Mapping[str, str]) -> tuple[bytes, list[dict[str, Any]], Any]:  # fmt: skip
    man, in_hashes, frozen, data = stage_inputs(
        manifest_path, inputs_dir, rater_dir, checksums_path
    )
    hits = find_hits(data, final_replies)
    return render_hits(hits, frozen, final_replies), hits, (man, in_hashes, frozen, data)


def gate_classification(
    hits_bytes: bytes, hits: Sequence[Mapping[str, Any]], hits_file_bytes: bytes,
    classification_bytes: bytes, classification_sha256: str,
    frozen: Mapping[str, str], final_replies: Mapping[str, str],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:  # fmt: skip
    """The posted hand classification of exactly these hits (plan section 5, step 5)."""
    if hits_file_bytes != hits_bytes:
        raise RefusedError("the given hits file differs from the recomputed hits output")
    no_reply = sorted(
        n for n in frozen if n.startswith("v3_output_")
        and not final_replies.get(inst(n.split("_")[2], int(n.split("_")[3].split(".")[0])), "").strip()
    )  # fmt: skip
    if no_reply:
        raise RefusedError(f"no final reply scanned for {no_reply}")
    if sha256_bytes(classification_bytes) != classification_sha256.strip().lower():
        raise RefusedError("classification file differs from the SHA-256 posted in #1404")
    try:
        classification = json.loads(classification_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RefusedError(f"classification is not JSON: {exc}") from exc
    return ev2.check_classification(classification, hits, hits_bytes), classification


# ---------------------------------------------------------------- rule-claim sample


def claim_sample(
    man: Mapping[str, Any], data: Mapping[str, Mapping[int, Mapping[str, Any]]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """60 claims, 20 per rater (A, B, C in this order, one shared generator), at most one per
    card over all raters, ``random.Random(20261131)``; mixed; blind to the rater."""
    rng = random.Random(SEED_CLAIMS)
    used: set[str] = set()
    items: list[tuple[str, int, str, int]] = []
    for r in RATERS:
        cand = []
        for k in sorted(data[r]):
            for c in data[r][k]["cards"]:
                if c["valid"] and c["oracle_id"] not in used:
                    cand.append(
                        (f"{k}|{c['oracle_id']}", (c["card_row"] or {}).get("rule_claims") or [])
                    )
        picked = ev2.pick_claims(cand, CLAIMS_PER_RATER, rng)
        for key, i in picked:
            k_s, o = key.split("|", 1)
            used.add(o)
            items.append((r, int(k_s), o, i))
    rng.shuffle(items)
    blind, key_out = [], []
    for nr, (r, k, o, i) in enumerate(items, 1):
        ch = data[r][k]
        c = next(x for x in ch["cards"] if x["oracle_id"] == o)
        blind.append({"nr": nr, "charge": k, "card": man["karten"][o].get("card", ""), "oracle_id": o,
                      "feld": f"rule_claims[{i}].claim", "claim": str(c["card_row"]["rule_claims"][i]["claim"]),
                      "card_block": ch["blocks"].get(o, "")})  # fmt: skip
        key_out.append({"nr": nr, "rater": r, "oracle_id": o, "claim_index": i})
    return blind, key_out


def grade_claims(key: Sequence[Mapping[str, Any]], verdicts: Any) -> dict[str, Any]:
    """Per rater: green <= 1 of 20 obviously wrong, red >= 3; 'unbekannt' until all are judged."""
    vd = {str(k): str(v) for k, v in verdicts.items()} if isinstance(verdicts, Mapping) else {}
    out: dict[str, Any] = {"n": len(key), "seed": SEED_CLAIMS}
    for r in RATERS:
        nrs = [str(x["nr"]) for x in key if x["rater"] == r]
        judged = [n for n in nrs if n in vd]
        wrong = sum(vd[n] == "falsch" for n in judged)
        if not nrs or len(judged) < len(nrs):
            st = UNKNOWN
        elif wrong <= CLAIM_GREEN_MAX:
            st = "gruen"
        elif wrong >= CLAIM_RED_MIN:
            st = "rot"
        else:
            st = "gelb"
        out[r] = {"N": len(nrs), "beurteilt": len(judged),
                  "offensichtlich_falsch": wrong if judged else None, "stufe": st,
                  "sensitivitaet_leave_one_rater_out": st == "rot"}  # fmt: skip
    return out


def run_claims(manifest_path: Path, inputs_dir: Path, rater_dir: Path, checksums_path: Path
               ) -> tuple[bytes, bytes]:  # fmt: skip
    man, _, frozen, data = stage_inputs(manifest_path, inputs_dir, rater_dir, checksums_path)
    blind, key = claim_sample(man, data)
    head = {n: v for n, v in sorted(frozen.items()) if n.startswith("v3_output_")}
    b = {"schema": "rating-v3-regelclaims-blind-1", "seed": SEED_CLAIMS, "eingefrorene_ausgaben_sha256": head,
         "hinweis": "Nur Kartenblock und Claim; Rater verdeckt. Je Nr: falsch / korrekt / unscharf.", "claims": blind}  # fmt: skip
    kd = {"schema": "rating-v3-regelclaims-schluessel-1", "seed": SEED_CLAIMS, "schluessel": key}
    return dumps(b).encode("utf-8"), dumps(kd).encode("utf-8")


# ---------------------------------------------------------------- run log, transcripts (A2, A3, S8)


def run_log_view(log: Mapping[str, Any] | None, man: Mapping[str, Any], rater_dir: Path,
                 frozen: Mapping[str, str], checksums: Mapping[str, Sequence[str]]) -> dict[str, Any]:  # fmt: skip
    """Strict view of the run log. Model IDs, tiers and versions are compared, never returned."""
    lg = dict(log or {})
    present = lg.get("laufprotokoll_vorhanden") is True and bool(
        str(lg.get("hash_kommentar", "")).strip()
    )
    raw_inst = lg.get("instanzen") if isinstance(lg.get("instanzen"), Mapping) else {}
    assert isinstance(raw_inst, Mapping)
    view: dict[str, Any] = {
        "vorhanden": present,
        "skript_vor_oeffnen_committet": lg.get("skript_vor_oeffnen_committet") is True,
        "hashes_vor_oeffnen_gepostet": lg.get("hashes_vor_oeffnen_gepostet") is True,
        "a8_abweichungen": [str(x) for x in lg.get("a8_abweichungen", []) or []],
        "instanzen": {},
    }
    versions: dict[str, set[str]] = {r: set() for r in RATERS}  # (model, version) per rater
    complete = True
    for ch in man["chargen"]:
        k = ch["k"]
        for r in RATERS:
            key = inst(r, k)
            e = raw_inst.get(key) if isinstance(raw_inst.get(key), Mapping) else {}
            assert isinstance(e, Mapping)
            has_out = output_name(r, k) in frozen
            fields_ok = all(str(e.get(f, "")).strip() for f in RUN_LOG_INSTANCE_FIELDS)
            meta_ok = False
            mname = meta_name(r, k)
            if mname in frozen and fields_ok:
                text = (rater_dir / mname).read_text(encoding="utf-8", errors="replace")
                meta_ok = (frozen[mname] == str(e.get("meta_sha256")).lower()
                           and str(e["modell_id"]) in text and str(e["aufwand"]) in text)  # fmt: skip
            tname = transcript_name(r, k)
            transcript_ok = (
                tname in frozen and str(e.get("transkript_sha256", "")).lower() == frozen[tname]
            )
            prior = e.get("a2_verstoesse_frueher")
            a7 = e.get("abbrueche_a7")
            prior_v = (
                prior
                if isinstance(prior, int) and not isinstance(prior, bool) and prior >= 0
                else None
            )
            if prior_v is None and len(checksums.get(output_name(r, k), [])) > 1:
                raise RefusedError(
                    f"{key} was frozen more than once: the run log must state 'a2_verstoesse_frueher'"
                )
            if has_out:
                complete = complete and fields_ok and meta_ok and transcript_ok
                if fields_ok:
                    versions[r].add(sha256_bytes(f"{e['modell_id']}|{e['version']}".encode()))
            view["instanzen"][key] = {
                "ausgabe_eingefroren": has_out, "pflichtfelder_vollstaendig": fields_ok,
                "meta_passt": meta_ok, "transkript_eingefroren_und_protokolliert": transcript_ok,
                "transkript_sha256": frozen.get(tname), "meta_sha256": frozen.get(mname),
                "a2_verstoesse_frueher": prior_v if prior_v is not None else 0,
                "abbrueche_a7": a7 if isinstance(a7, int) and not isinstance(a7, bool) and a7 >= 0 else UNKNOWN,
                "nachlauf_a1": e.get("nachlauf_a1") is True,
            }  # fmt: skip
    view["A3"] = not (present and complete)
    view["A9_versionswechsel"] = {r: len(v) > 1 for r, v in versions.items()}
    view["A10"] = not (view["skript_vor_oeffnen_committet"] and view["hashes_vor_oeffnen_gepostet"])
    view["A8"] = bool(view["a8_abweichungen"])
    return view


def path_inside(path: str, folder: str) -> bool:
    """True when ``path`` (absolute, or relative to ``folder``) lies inside ``folder``; the
    comparison uses a trailing separator, so ``/x/A_1`` does not contain ``/x/A_10``."""
    base = posixpath.normpath(folder.replace("\\", "/"))
    p = path.replace("\\", "/")
    full = posixpath.normpath(p if p.startswith("/") else posixpath.join(base, p))
    return full == base or full.startswith(base.rstrip("/") + "/")


def scan_tool_calls(tool_calls: Any, man: Mapping[str, Any], frozen: Mapping[str, str]
                    ) -> dict[str, Any]:  # fmt: skip
    """S8 transcript part: per instance with a frozen output, every call must use an allowed tool
    on a path inside the instance's own folder. Only tool name, path and instance are read and
    printed; every other key (for example a write content) is ignored."""
    out: dict[str, Any] = {"vorhanden": isinstance(tool_calls, Mapping), "instanzen": {}}
    folders = tool_calls.get("ordner", {}) if isinstance(tool_calls, Mapping) else {}
    calls = tool_calls.get("aufrufe", []) if isinstance(tool_calls, Mapping) else []
    if not isinstance(folders, Mapping) or not isinstance(calls, list):
        folders, calls = {}, []
        out["vorhanden"] = False
    by_inst: dict[str, list[tuple[str, str]]] = {}
    for c in calls:
        if isinstance(c, Mapping):
            by_inst.setdefault(str(c.get("instanz", "")), []).append(
                (str(c.get("werkzeug", "")), str(c.get("pfad", "")))
            )
    for ch in man["chargen"]:
        for r in RATERS:
            key = inst(r, ch["k"])
            if output_name(r, ch["k"]) not in frozen:
                continue
            folder = folders.get(key)
            if not out["vorhanden"] or not isinstance(folder, str) or not folder.strip():
                out["instanzen"][key] = {"gescannt": False, "verstoesse": [], "n_aufrufe": 0}
                continue
            bad = [
                {"werkzeug": t, "pfad": p,
                 "grund": "werkzeug" if t not in ALLOWED_TOOLS else "pfad_ausserhalb"}
                for t, p in by_inst.get(key, [])
                if t not in ALLOWED_TOOLS or not path_inside(p, folder)
            ]  # fmt: skip
            out["instanzen"][key] = {
                "gescannt": True,
                "verstoesse": bad,
                "n_aufrufe": len(by_inst.get(key, [])),
            }
    return out


# ---------------------------------------------------------------- adjudication (I6)


def card_ratings(man: Mapping[str, Any], data: Mapping[str, Mapping[int, Mapping[str, Any]]],
                 excluded: Mapping[str, set[int]]) -> dict[str, dict[str, Any]]:  # fmt: skip
    """Per card: the counting placement (non-anchor: its chunk; anchor: FIRST placement in the
    manifest's chunk order) and the valid ratings of non-excluded raters there."""
    out: dict[str, dict[str, Any]] = {}
    for ch in man["chargen"]:
        k = ch["k"]
        for o in ch["karten"]:
            if o in out:
                continue  # a later placement of an anchor is a retest only
            recs: dict[str, dict[str, Any]] = {}
            for r in RATERS:
                c = next(x for x in data[r][k]["cards"] if x["oracle_id"] == o)
                recs[r] = c
            out[o] = {"charge": k, "tranche": ch.get("tranche"), "records": recs,
                      "gueltig": {r: c for r, c in recs.items() if c["valid"] and k not in excluded[r]}}  # fmt: skip
    return out


def adjudication_list(man: Mapping[str, Any], data: Mapping[str, Mapping[int, Mapping[str, Any]]],
                      placed: Mapping[str, Mapping[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]]]:  # fmt: skip
    """Cards with rater spread on H_v3b >= 15 (I6), in groups of at most 10; ratings in an order
    fixed by SHA-256 of (oracle_id, rater), without rater identity."""
    items = []
    key: dict[str, dict[str, str]] = {}
    for o in sorted(placed, key=lambda x: (placed[x]["charge"], x)):
        g = placed[o]["gueltig"]
        if len(g) < 2:
            continue
        v3b = [h_ref(g[r]["werte"]) for r in g]
        if max(v3b) - min(v3b) < FLAG_SPREAD:
            continue
        order = sorted(g, key=lambda r: sha256_bytes(f"{o}|{r}".encode()))
        k = placed[o]["charge"]
        bew = []
        key[o] = {}
        for nr, r in enumerate(order, 1):
            c = g[r]
            row = c["card_row"] or {}
            key[o][str(nr)] = r
            bew.append({"nr": nr, "werte": {x: c["werte"][x] for x in LINE_ORDER},
                        "notizen": c["notizen"], "reason": row.get("reason", ""),
                        "rule_claims": row.get("rule_claims", [])})  # fmt: skip
        items.append({"oracle_id": o, "card": man["karten"][o].get("card", ""), "charge": k,
                      "card_block": data[order[0]][k]["blocks"].get(o, ""), "bewertungen": bew})  # fmt: skip
    for i, it in enumerate(items):
        it["gruppe"] = i // ADJ_GROUP + 1
    return items, key


def apply_adjudication(key: Mapping[str, Mapping[str, str]], verdicts: Any) -> dict[str, set[str]]:
    """Ratings with a documented objective error (non-empty verbatim quote) per card."""
    if not isinstance(verdicts, Mapping):
        raise RefusedError("adjudication verdicts must be a JSON object")
    out: dict[str, set[str]] = {}
    for o, per in verdicts.items():
        if o not in key or not isinstance(per, Mapping):
            raise RefusedError(f"adjudication verdict for unknown card {o}")
        for nr, v in per.items():
            if (
                str(nr) not in key[o]
                or not isinstance(v, Mapping)
                or not isinstance(v.get("objektiver_fehler"), bool)
            ):
                raise RefusedError(
                    f"adjudication {o}/{nr}: needs a known number and 'objektiver_fehler'"
                )
            if v["objektiver_fehler"]:
                if not str(v.get("zitat", "")).strip():
                    raise RefusedError(f"adjudication {o}/{nr}: a finding needs a verbatim quote")
                out.setdefault(str(o), set()).add(key[o][str(nr)])
    return out


# ---------------------------------------------------------------- stage 2: evaluation


def _pinned_rows(path: Path | None, role: str, full: str | None, prefix: str | None
                 ) -> tuple[dict[str, dict[str, Any]] | None, str | None]:  # fmt: skip
    if path is None:
        return None, None
    digest = verify_pinned(path, role, full=full, prefix=prefix)
    return {str(r["oracle_id"]): r for r in load_jsonl(path)}, digest


def old_same(p: Mapping[str, Any], variant: str) -> float:
    """H_old,same (S7): mean of F1 and R2 under the SAME H definition, N = 100 - D."""
    vals = []
    for run in ("F1", "R2"):
        c = {x: float(p[f"{run}_{x}"]) for x in ("E", "F", "T", "R", "K")}
        c["N"] = 100.0 - float(p[f"{run}_D"])
        ref = h_ref(c)
        vals.append(
            {"V3b": ref, "V3c": h_v3c(c), "V3a": clamp_corridor(float(p[f"{run}_H"]), ref)}[variant]
        )
    return (vals[0] + vals[1]) / 2


def analyse(
    *, manifest_path: Path, inputs_dir: Path, rater_dir: Path, checksums_path: Path,
    hits_file_bytes: bytes, classification_bytes: bytes, classification_sha256: str,
    final_replies: Mapping[str, str], run_log: Mapping[str, Any] | None, tool_calls: Any,
    usage_path: Path | None = None, old_runs_path: Path | None = None, pooled_path: Path | None = None,
    claim_verdicts: Any = None, adjudication_key_bytes: bytes | None = None,
    adjudication_verdicts: Any = None, draws: int | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:  # fmt: skip
    """Stage 2. ``draws`` is only for tests; the command line always uses the plan's 2000."""
    draws = DRAWS if draws is None else draws
    hits_bytes, hits, (man, in_hashes, frozen, data) = run_hits(
        manifest_path, inputs_dir, rater_dir, checksums_path, final_replies
    )
    cls, classification = gate_classification(
        hits_bytes, hits, hits_file_bytes, classification_bytes, classification_sha256, frozen, final_replies
    )  # fmt: skip
    checksums = parse_checksums(checksums_path.read_text(encoding="utf-8"))
    log = run_log_view(run_log, man, rater_dir, frozen, checksums)
    scan = scan_tool_calls(tool_calls, man, frozen)
    phase = str(man["phase"])
    chunk_ks = [ch["k"] for ch in man["chargen"]]

    # ---- A2 per rater and chunk: counting hits, transcript violations, missing transcript
    counting = Counter((h["rater"], h["charge"]) for h in hits if cls[h["id"]]["zaehlt"])
    a2: dict[str, dict[str, Any]] = {}
    excluded: dict[str, set[int]] = {r: set() for r in RATERS}
    viol_chunks: dict[str, list[int]] = {r: [] for r in RATERS}
    for k in chunk_ks:
        for r in RATERS:
            key = inst(r, k)
            if output_name(r, k) not in frozen:
                continue
            sc = scan["instanzen"].get(key, {"gescannt": False, "verstoesse": []})
            no_transcript = transcript_name(r, k) not in frozen
            current = counting.get((r, k), 0) > 0 or bool(sc["verstoesse"]) or no_transcript
            prior = log["instanzen"][key]["a2_verstoesse_frueher"]
            total = prior + int(current)
            if current:
                excluded[r].add(k)
            if total >= 1:
                viol_chunks[r].append(k)
            a2[key] = {"zaehlende_treffer": counting.get((r, k), 0), "werkzeug_verstoesse": len(sc["verstoesse"]),
                       "transkript_fehlt": no_transcript, "transkript_gescannt": sc["gescannt"],
                       "verstoesse_frueher": prior, "verstoss_aktuell": current, "verstoesse_gesamt": total,
                       "ausgeschlossen": current,
                       "grund": ("A2_zweiter_verstoss" if total >= 2 else "A2_verstoss") if current else None}  # fmt: skip
    dropped = sorted(r for r in RATERS if len(viol_chunks[r]) >= 2)
    for r in dropped:
        excluded[r] = set(chunk_ks)

    # ---- validity per rater and chunk (A1, A5), A11
    chunk_info: dict[str, Any] = {}
    for k in chunk_ks:
        for r in RATERS:
            ch = data[r][k]
            cards = ch["cards"]
            n = len(cards)
            valid = [c for c in cards if c["valid"]]
            fmt_err = [
                c
                for c in cards
                if c["nicht_vielfache_5"]
                or any("missing" in p or "lines" in p for p in c["problems"])
            ]
            chunk_info[inst(r, k)] = {
                "C": n, "ausgabe_vorhanden": ch["present"], "zeilen": ch["n_lines"],
                "zusatzkarten": ch["extra_cards"], "zeilen_ohne_karte": len(ch["orphans"]),
                "V_gueltig": [len(valid), n], "A1_unter_90_prozent": len(valid) < A1_VALID_SHARE * n,
                "A5_formatfehler": [len(fmt_err), n], "A5_ausgeloest": len(fmt_err) > A5_FORMAT_SHARE * n,
                "nicht_vielfache_5_werte": sum(c["nicht_vielfache_5"] for c in cards),
                "schema_maengel_karten": sum(1 for c in cards if c["schema_maengel"]),
                "nicht_gueltig": {str(c["pos"]): c["problems"] for c in cards if c["problems"]},
                "A2": a2.get(inst(r, k)), "A7_abbrueche": log["instanzen"][inst(r, k)]["abbrueche_a7"],
                "A1_nachlauf_protokolliert": log["instanzen"][inst(r, k)]["nachlauf_a1"],
                "ausgeschlossen": k in excluded[r],
            }  # fmt: skip
    full_valid_chunks = [
        k for k in chunk_ks
        if all(k not in excluded[r] and not chunk_info[inst(r, k)]["A1_unter_90_prozent"] for r in RATERS)
    ]  # fmt: skip
    a11 = phase == "pilot" and len(full_valid_chunks) < A11_MIN_VALID_CHUNKS

    # ---- placement and I5 aggregation (before adjudication)
    placed = card_ratings(man, data, excluded)
    karten = man["karten"]

    def per_rater_vals(o: str, drop: set[str] | None = None) -> dict[str, dict[str, float]]:
        g = placed[o]["gueltig"]
        return {r: g[r]["werte"] for r in g if not drop or r not in drop}

    agg = {o: aggregate(per_rater_vals(o)) for o in placed}
    is_anchor = {o: karten[o].get("anker") is not None for o in placed}
    plain = sorted(o for o in placed if not is_anchor[o])

    # ---- S1-S9 per variant on the non-anchor cards, BEFORE adjudication
    complete = [o for o in plain if agg[o]["n_rater"] == 3]
    kinds = [str(karten[o]["art"]) for o in complete]
    pos_rows = [[float(placed[o]["records"][r]["pos"]) for r in RATERS] for o in complete]
    rv = {
        o: {r: rater_variants(placed[o]["gueltig"][r]["werte"]) for r in placed[o]["gueltig"]}
        for o in placed
    }

    usage, usage_sha = _pinned_rows(usage_path, "usage", None, USAGE_SHA256_PREFIX)
    old, old_sha = _pinned_rows(old_runs_path, "old_runs", None, OLD_RUNS_SHA256_PREFIX)
    pooled, pooled_sha = _pinned_rows(pooled_path, "pooled", POOLED_SHA256, None)

    terms: list[dict[str, Any]] = []
    for o in sorted(o for o in placed if is_anchor[o]):
        anc = karten[o]["anker"]
        for crit, val in sorted(anc["zeilen"].items()):
            werte = {
                r: placed[o]["gueltig"][r]["werte"][crit] if r in placed[o]["gueltig"] else None
                for r in RATERS
            }
            a = agg[o]["kriterien"]
            terms.append({"oracle_id": o, "card": karten[o].get("card", ""), "kriterium": crit,
                          "satz": anc["satz"], "ankerwert": float(val), "werte": werte,
                          "aggregat": a[crit] if a else None, "art": karten[o]["art"]})  # fmt: skip
    s5_res = s5(terms)
    # a missing transcript or an unscanned instance leaves S8 unknown (never 0)
    s8_known = (
        scan["vorhanden"]
        and all(v["gescannt"] for v in scan["instanzen"].values())
        and not any(x["transkript_fehlt"] for x in a2.values())
    )
    s8_count = sum(counting.values()) + sum(
        len(v["verstoesse"]) for v in scan["instanzen"].values()
    )
    s8_res = {"zaehlende_treffer": sum(counting.values()),
              "werkzeug_verstoesse": sum(len(v["verstoesse"]) for v in scan["instanzen"].values()),
              "transkript_scan_vollstaendig": s8_known, "schwelle_max": S8_MAX,
              "status": FAIL if s8_count > S8_MAX else (OK if s8_known else UNKNOWN)}  # fmt: skip
    agg_crit = [agg[o]["kriterien"] for o in plain if agg[o]["kriterien"]]
    per_rater_crit = {
        r: [placed[o]["gueltig"][r]["werte"] for o in plain if r in placed[o]["gueltig"]]
        for r in RATERS
    }
    s9_res = s9(agg_crit, per_rater_crit)

    s7_reason = None
    if usage is None:
        s7_reason = "usage_holdout.jsonl nicht angegeben"
    elif old is None:
        s7_reason = "alte Laeufe (A1 pairs.jsonl) nicht angegeben"

    variants: dict[str, dict[str, Any]] = {}
    for v in VARIANTS:
        rows = [[rv[o][r][v] for r in RATERS] for o in complete]
        res: dict[str, Any] = {
            "S1": s1(rows, draws, blocked=bool(dropped)),
            "S2": s2(rows),
            "S3": s3(rows, kinds),
            "S5": s5_res,
            "S6": s6(rows, pos_rows),
            "S8": s8_res,
            "S9": s9_res,
        }
        if v == "V3a":
            res["S4"] = s4({r: [(placed[o]["gueltig"][r]["werte"]["H"], rv[o][r]["V3b"])
                                for o in plain if r in placed[o]["gueltig"]] for r in RATERS})  # fmt: skip
        s7_pairs: list[tuple[float, float, float]] = []
        if s7_reason is None and usage is not None and old is not None:
            for o in plain:
                if agg[o][v] is not None and o in old and o in usage:
                    s7_pairs.append(
                        (agg[o][v], old_same(old[o], v), float(usage[o]["deck_list_count"]))
                    )
        res["S7"] = s7(s7_pairs, draws, s7_reason, must=phase == "vollauf")
        disp_pairs: list[tuple[float, float, float]] = []
        if usage is not None and pooled is not None:
            for o in sorted(placed):
                if agg[o][v] is not None and o in pooled and o in usage:
                    disp_pairs.append(
                        (
                            agg[o][v],
                            float(pooled[o]["H_pooled"]),
                            float(usage[o]["deck_list_count"]),
                        )
                    )
        if usage is None or pooled is None:
            res["anzeige_bedingung"] = {"status": UNKNOWN, "differenz": None, "ci95": [None, None], "n": 0,
                                        "grund": "usage oder pooled.jsonl nicht angegeben"}  # fmt: skip
        else:
            point, ci = spearman_diff(disp_pairs, draws)
            res["anzeige_bedingung"] = {"n": len(disp_pairs), "differenz": point, "ci95": ci,
                                        "schwelle_min": DISPLAY_LOSS_MIN,
                                        "status": status(None if point is None else point >= DISPLAY_LOSS_MIN)}  # fmt: skip
        res["n_nicht_anker"] = [len(complete), len(plain)]
        variants[v] = res

    # ---- decision rule (plan sections 3 and 4)
    labels: list[str] = []
    if log["A10"]:
        labels.append("explorativ, nicht nach Plan (A10)")
    if log["A8"]:
        labels.append("nicht nach Plan (A8): " + "; ".join(log["a8_abweichungen"]))
    if log["A3"]:
        labels.append("Stufen ungeprueft (A3)")
    if any(log["A9_versionswechsel"].values()):
        labels.append(
            "Modellversion gewechselt (A9): Kennzahlen je Version getrennt, nie 'ein Rater'"
        )
    if dropped:
        labels.append(
            f"Rater ausgefallen (A2: Verstoesse in zwei Chargen): {dropped}; kein Schluss fuer S1"
        )
    decision = decide(phase, man.get("pilot_runde"), variants, blockers=[
        x for x, on in (("A10", log["A10"]), ("A8", log["A8"]), ("A11", a11), ("A2_rater_ausgefallen", bool(dropped))) if on
    ])  # fmt: skip

    # ---- chunk effects (A4, A6, A9), marks
    def e_by(v: str, sel: Callable[[str], bool]) -> dict[str, list[float]]:
        out: dict[str, list[float]] = {r: [] for r in RATERS}
        for o in placed:
            if agg[o]["n_rater"] == 3 and sel(o):
                med = statistics.median([rv[o][r][v] for r in RATERS])
                for r in RATERS:
                    out[r].append(rv[o][r][v] - med)
        return out

    a6: dict[str, Any] = {}
    flagged_chunks: set[tuple[str, int]] = set()
    for v in VARIANTS:
        per = {k: e_by(v, lambda o, k=k: placed[o]["charge"] == k) for k in chunk_ks}  # type: ignore[misc]
        a6[v] = {}
        for r in RATERS:
            eff = ev2.chunk_effect({k: per[k][r] for k in chunk_ks})
            a6[v][r] = eff
            flagged_chunks |= {(r, int(k)) for k, x in eff.items() if x.get("auffaellig") is True}
    a4: dict[str, Any] = {}
    compressed: set[tuple[str, int]] = set()
    for k in chunk_ks:
        ids = [o for o in placed if placed[o]["charge"] == k and agg[o]["n_rater"] == 3]
        for r in RATERS:
            entry = {}
            for v in ("V3b", "V3a"):
                own = [rv[o][r][v] for o in ids]
                others = [rv[o][x][v] for o in ids for x in RATERS if x != r]
                if len(own) < 2:
                    entry[v] = {"n": len(own), "ausgeloest": False, "grund": "zu wenige Karten"}
                    continue
                mode_n = Counter(own).most_common(1)[0][1]
                trig = pstd(own) < A4_SD_RATIO * pstd(others) or mode_n > A4_MODE_SHARE * len(own)
                entry[v] = {"n": len(own), "sd": pstd(own), "sd_andere": pstd(others),
                            "modus_anteil": mode_n / len(own), "ausgeloest": trig}  # fmt: skip
                if trig:
                    compressed.add((r, k))
            a4[inst(r, k)] = entry
    a9: dict[str, Any] = {"versionswechsel": log["A9_versionswechsel"], "tranchen": UNKNOWN}
    if phase == "vollauf":
        tr = sorted({int(ch["tranche"]) for ch in man["chargen"]})
        per_t = {t: e_by("V3b", lambda o, t=t: placed[o]["tranche"] == t) for t in tr}  # type: ignore[misc]
        a9["tranchen"] = {}
        for r in RATERS:
            m = {t: statistics.fmean(per_t[t][r]) for t in tr if per_t[t][r]}
            a9["tranchen"][r] = {
                str(t): {"mittel_e": m[t], "abstand": (m[t] - statistics.fmean([m[u] for u in m if u != t])) if len(m) > 1 else None,
                         "auffaellig": len(m) > 1 and abs(m[t] - statistics.fmean([m[u] for u in m if u != t])) > A9_TRANCHE_GAP}
                for t in m
            }  # fmt: skip

    # ---- I6 adjudication (after the S criteria)
    # same material as the ``adjudicate`` command (every valid rating; A2 exclusions apply in the
    # aggregation anyway), so the key written there is the key checked here
    adj_items, adj_key = adjudication_list(
        man, data, card_ratings(man, data, {r: set() for r in RATERS})
    )
    adj: dict[str, Any] = {"karten_abstand_ge15": len(adj_items), "angewendet": False}
    dropped_ratings: dict[str, set[str]] = {}
    if adjudication_key_bytes is not None or adjudication_verdicts is not None:
        if adjudication_key_bytes is None or adjudication_verdicts is None:
            raise RefusedError("adjudication needs both the key and the verdicts")
        if adjudication_key_bytes != dumps(
            {"schema": "rating-v3-adjudikation-schluessel-1", "schluessel": adj_key}
        ).encode("utf-8"):
            raise RefusedError("adjudication key differs from the recomputed key")
        dropped_ratings = apply_adjudication(adj_key, adjudication_verdicts)
        per_r = Counter(r for s in dropped_ratings.values() for r in s)
        adj.update({"angewendet": True, "karten_mit_befund": len(dropped_ratings),
                    "verworfene_bewertungen_je_rater": {r: per_r.get(r, 0) for r in RATERS},
                    "befund_stufe_rater_A_ueber_rater_A": per_r.get("A", 0)})  # fmt: skip
    final = {
        o: aggregate(per_rater_vals(o, dropped_ratings.get(o))) if o in dropped_ratings else agg[o]
        for o in placed
    }

    # ---- per-card file
    h_rows: list[dict[str, Any]] = []
    for o in sorted(placed):
        g = placed[o]["gueltig"]
        f = final[o]
        spread = {}
        for v in VARIANTS:
            vals = [rv[o][r][v] for r in g]
            spread[v] = max(vals) - min(vals) if len(vals) >= 2 else None
        raw = [g[r]["werte"]["H"] for r in g]
        spread["V3a_roh"] = max(raw) - min(raw) if len(raw) >= 2 else None
        for c in CRITERIA:
            vals = [g[r]["werte"][c] for r in g]
            spread[c] = max(vals) - min(vals) if len(vals) >= 2 else None
        marks = []
        if spread["V3b"] is not None and spread["V3b"] >= FLAG_SPREAD:
            marks.append("abstand_ge15")
        if f["n_rater"] < 3:
            marks.append(f"n_rater_{f['n_rater']}")
        if o in dropped_ratings:
            marks.append("adjudiziert")
        k = placed[o]["charge"]
        if any((r, k) in compressed for r in g):
            marks.append("skalenstauchung")
        if any((r, k) in flagged_chunks for r in g):
            marks.append("charge_auffaellig")
        h_rows.append({
            "oracle_id": o, "card": karten[o].get("card", ""), "art": karten[o]["art"], "anker": is_anchor[o],
            "charge": k, "n_rater": f["n_rater"], "H_v3b": f["V3b"], "H_v3a": f["V3a"], "H_v3c": f["V3c"],
            "H_v3b_vor_adjudikation": agg[o]["V3b"], "kriterien_median": f["kriterien"],
            "spannweite": spread, "marken": marks,
        })  # fmt: skip

    # ---- I5 offset check on the anchors, anchor retest, sensitivities
    offsets: dict[str, Any] = {}
    for kd in KINDS:
        per_card = []
        for o in sorted(o for o in placed if is_anchor[o] and karten[o]["art"] == kd):
            ts = [t for t in terms if t["oracle_id"] == o and t["aggregat"] is not None]
            if ts:
                per_card.append(statistics.fmean(t["aggregat"] - t["ankerwert"] for t in ts))
        mean_off = statistics.fmean(per_card) if per_card else None
        ci = boot_ci(per_card, statistics.fmean, draws) if len(per_card) >= 2 else [None, None]
        excl0 = ci[0] is not None and ci[1] is not None and (ci[0] > 0 or ci[1] < 0)
        offsets[kd] = {"n_karten": len(per_card), "versatz": mean_off, "ci95": ci,
                       "korrektur_vorschlagen": mean_off is not None and abs(mean_off) > OFFSET_CORRECTION_GAP and excl0}  # fmt: skip
    retest = []
    for ch in man["chargen"]:
        for o in ch["karten"]:
            if is_anchor[o] and placed[o]["charge"] != ch["k"]:
                for crit, val in sorted(karten[o]["anker"]["zeilen"].items()):
                    for r in RATERS:
                        c = next(x for x in data[r][ch["k"]]["cards"] if x["oracle_id"] == o)
                        if c["valid"] and ch["k"] not in excluded[r]:
                            retest.append(abs(c["werte"][crit] - val))
    sens = sensitivities(placed, plain, rv, agg, final, draws)

    _, ckey = claim_sample(man, data)
    claims_result = grade_claims(ckey, claim_verdicts)

    strike = anchor_strike(terms)
    provenance = {
        "skript_sha256": sha256_file(Path(__file__)), "seed": SEED_BOOT, "draws": draws, "phase": phase,
        "pilot_runde": man.get("pilot_runde"),
        "manifest_sha256": man["_sha256"], "eingaben_sha256": in_hashes,
        "eingefroren_sha256": dict(sorted(frozen.items())),
        "checksummen_sha256": sha256_file(checksums_path), "hits_sha256": sha256_bytes(hits_bytes),
        "klassifikation_sha256": sha256_bytes(classification_bytes),
        "klassifikation_kommentar": str(classification.get("github_kommentar")),
        "laufprotokoll_sha256": sha256_bytes(json.dumps(run_log, sort_keys=True).encode()) if run_log else UNKNOWN,
        "usage_sha256": usage_sha or UNKNOWN, "alte_laeufe_sha256": old_sha or UNKNOWN,
        "pooled_sha256": pooled_sha or UNKNOWN,
    }  # fmt: skip
    result = {
        "schema": SCHEMA_RESULT, "kennzeichnung": labels, "herkunft": provenance,
        "laufprotokoll": {k: v for k, v in log.items()},
        "transkript_scan": scan,
        "verweis_treffer": {"n": len(hits), "zaehlend": {inst(r, k): n for (r, k), n in sorted(counting.items())},
                            "einstufung": [{**h, **cls[h["id"]]} for h in hits]},
        "A2": {"je_instanz": a2, "rater_ausgefallen": dropped},
        "chargen": chunk_info,
        "A11": {"chargen_alle_drei_gueltig": full_valid_chunks, "n": len(full_valid_chunks),
                "N": len(chunk_ks), "kein_schluss": a11},
        "A4_skalenstauchung_nur_markiert": a4, "A6_chargeneffekt": a6, "A9": a9,
        "karten": {"N": len(placed), "nicht_anker": len(plain), "nicht_anker_mit_drei_ratern": len(complete),
                   "n_rater": dict(sorted(Counter(str(agg[o]["n_rater"]) for o in placed).items()))},
        "kriterien": variants,
        "entscheidung": decision,
        "anker": {"terme": terms, "streichliste": strike, "n_streichen": sum(s["streichen"] for s in strike),
                  "versatz_je_art_I5": offsets,
                  "retest_wiederholungen": {"n": len(retest), "mae": statistics.fmean(retest) if retest else None}},
        "adjudikation": adj, "sensitivitaet": sens, "regelclaims": claims_result,
        "abstand_ge15": [
            {"card": x["card"], "oracle_id": x["oracle_id"], "charge": x["charge"],
             "spannweite_V3b": x["spannweite"]["V3b"], "spannweite_V3a_roh": x["spannweite"]["V3a_roh"]}
            for x in h_rows if "abstand_ge15" in x["marken"]
        ],
        "retest_pilot_im_vollauf": "nicht berechnet: Pilot-Bewertungen sind keine Eingabe dieses Laufs",
    }  # fmt: skip
    return clean(result), h_rows


def decide(phase: str, runde: Any, variants: Mapping[str, Mapping[str, Any]],
           blockers: Sequence[str]) -> dict[str, Any]:  # fmt: skip
    """Pilot: only V3b and its Muss criteria S1, S3, S5, S6, S8, S9. Full run: the first variant in
    the order V3b, V3a, V3c that meets every Muss criterion (V3a also S4) AND the display
    condition; an 'unbekannt' stops the choice ('kein Schluss'), a failure moves to the next."""
    if phase == "pilot":
        st = {s: variants["V3b"][s]["status"] for s in PILOT_MUST}
        out: dict[str, Any] = {
            "phase": phase,
            "variante": "V3b",
            "muss": st,
            "sperren": list(blockers),
        }
        if blockers:
            out["ergebnis"] = "kein Schluss"
        elif any(x == FAIL for x in st.values()):
            out["ergebnis"] = (
                "Anpassungsrunde (Plan-Nachtrag zuerst)" if runde == 1 else "nicht erfuellt"
            )
        elif any(x == UNKNOWN for x in st.values()):
            out["ergebnis"] = "kein Schluss"
        else:
            out["ergebnis"] = "Vollauf"
        out["fruehwarnung"] = {v: {"S2": variants[v]["S2"]["status"], "S7": variants[v]["S7"]["status"],
                                   "anzeige_bedingung": variants[v]["anzeige_bedingung"]["status"]} for v in VARIANTS}  # fmt: skip
        return out
    out = {"phase": phase, "geprueft": {}, "sperren": list(blockers), "vorschlag": None}
    if blockers:
        out["ergebnis"] = "kein Vorschlag (Sperre)"
        return out
    for v in VARIANTS:
        musts = FULL_MUST + (FULL_MUST_V3A_EXTRA if v == "V3a" else ())
        st = {s: variants[v][s]["status"] for s in musts}
        st["anzeige_bedingung"] = variants[v]["anzeige_bedingung"]["status"]
        out["geprueft"][v] = st
        if any(x == FAIL for x in st.values()):
            continue
        if any(x == UNKNOWN for x in st.values()):
            out["ergebnis"] = f"kein Schluss (unbekannt bei {v})"
            return out
        out["vorschlag"] = v
        out["ergebnis"] = f"Vorschlag {v} (nur nach Owner-Go angewendet)"
        return out
    out["ergebnis"] = "im Vollauf nicht bestaetigt"
    return out


def sensitivities(placed: Mapping[str, Any], plain: Sequence[str], rv: Mapping[str, Any],
                  agg: Mapping[str, Any], final: Mapping[str, Any], draws: int) -> dict[str, Any]:  # fmt: skip
    """Reported only (plan section 5): leave-one-rater-out, equal weights, mean instead of median,
    with and without adjudication."""
    complete = [o for o in plain if agg[o]["n_rater"] == 3]
    loro = {}
    for a, b in RATER_PAIRS:
        loro[f"{a}-{b}"] = {
            v: nan_none(icc21_k([[rv[o][a][v], rv[o][b][v]] for o in complete])) for v in VARIANTS
        }
    eq_rows = [
        [h_ref(placed[o]["gueltig"][r]["werte"], WEIGHTS_EQUAL) for r in RATERS] for o in complete
    ]
    eq = {
        "icc21": nan_none(icc21_k(eq_rows)),
        "ci95": boot_ci(eq_rows, icc21_k, draws) if len(eq_rows) >= 3 else [None, None],
    }
    med, mea = [], []
    for o in plain:
        m = aggregate_mean({r: placed[o]["gueltig"][r]["werte"] for r in placed[o]["gueltig"]})
        if agg[o]["V3b"] is not None and m is not None:
            med.append(agg[o]["V3b"])
            mea.append(m)
    changed = [
        abs((final[o]["V3b"] or 0) - (agg[o]["V3b"] or 0))
        for o in placed
        if final[o] is not agg[o] and final[o]["V3b"] is not None and agg[o]["V3b"] is not None
    ]
    return {
        "leave_one_rater_out_icc21": loro, "gleiche_gewichte_V3b_icc21": eq,
        "mittel_statt_median_V3b": {"n": len(med), "mittl_abs_diff": statistics.fmean(abs(a - b) for a, b in zip(med, mea, strict=True)) if med else None,
                                    "spearman": nan_none(w1.spearman(med, mea)) if len(med) > 2 else None},
        "adjudikation_V3b": {"n_geaendert": len(changed), "mittl_abs_aenderung": statistics.fmean(changed) if changed else None},
    }  # fmt: skip


# ---------------------------------------------------------------- report template


def fmt(v: Any, digits: int = 3) -> str:
    return ev2.fmt(v, digits)


def report(result: Mapping[str, Any]) -> str:
    """Markdown template with every number, n/N and its source; the Co-Lead adds the reading."""
    h = result["herkunft"]
    d = result["entscheidung"]
    lines = [
        f"# Kartenverstaendnis H: Auswertung Bewertung v3, {h['phase']} (Vorlage, Refs #1404)",
        "",
        f"Erzeugt von `scripts/analysis/rating_v3_eval.py` (SHA-256 `{h['skript_sha256']}`), Seed {h['seed']}, "
        f"{h['draws']} Ziehungen, Manifest `{h['manifest_sha256']}`. Plan: `docs/analysis-reports/rating_v3_plan_20261123.md`. "
        "S1 bis S9 vor der Adjudikation; 'unbekannt' ist nie 0.",
        "",
        "## Kennzeichnung",
        "",
        *([f"- {x}" for x in result["kennzeichnung"]] or ["- keine"]),
        "",
        "## Entscheidung",
        "",
        f"- Ergebnis: **{d['ergebnis']}**; Sperren: {d['sperren'] or 'keine'}.",
    ]
    if d["phase"] == "pilot":
        lines.append(
            f"- Muss (nur V3b): {json.dumps(d['muss'], ensure_ascii=False, sort_keys=True)}"
        )
        lines.append(
            f"- Fruehwarnung: {json.dumps(d['fruehwarnung'], ensure_ascii=False, sort_keys=True)}"
        )
    else:
        lines.append(
            f"- Geprueft (Rangfolge V3b, V3a, V3c): {json.dumps(d['geprueft'], ensure_ascii=False, sort_keys=True)}"
        )
    k = result["karten"]
    lines += [
        "",
        f"## Kriterien je Variante (Nicht-Anker-Karten mit drei Ratern: {k['nicht_anker_mit_drei_ratern']} von {k['nicht_anker']})",
        "",
        "| Variante | S1 ICC(2,1) [95 %] | S2 (Soll) | S3 | S4 (V3a) | S5 MAE (n/N) | S6 | S7 [95 %] | S8 | S9 max r | Anzeige [95 %] |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for v, r in result["kriterien"].items():
        s1_, s7_, an = r["S1"], r["S7"], r["anzeige_bedingung"]
        s4_ = r.get("S4", {}).get("status", "-")
        lines.append(
            f"| {v} | {fmt(s1_['icc21'])} {ev2.fmt_ci(s1_['ci95'])} n = {s1_['n']}: {s1_['status']} "
            f"| {fmt(r['S2']['wert'])}: {r['S2']['status']} | {r['S3']['status']} | {s4_} "
            f"| {fmt(r['S5']['mae'])} ({r['S5']['n_terme']}/{r['S5']['N_terme']}): {r['S5']['status']} "
            f"| {r['S6']['status']} | {fmt(s7_['differenz'])} {ev2.fmt_ci(s7_['ci95'])} n = {s7_['n']}: {s7_['status']} "
            f"| {r['S8']['status']} | {fmt(r['S9']['max_r'])} ({r['S9']['paar'] or UNKNOWN}): {r['S9']['status']} "
            f"| {fmt(an['differenz'])} {ev2.fmt_ci(an['ci95'])} n = {an['n']}: {an['status']} |"
        )
    lines += [
        "",
        "Einzelwerte (S3 je Raterpaar mit S3b/S3c, S4 und S6 je Rater, S5 je Rater und alt/neu) stehen im Ergebnis-JSON (`kriterien`).",
        "",
        "## Gueltigkeit je Rater und Charge (A1, A2, A5)",
        "",
        "| Instanz | gueltig | A1 < 90 % | A5 | A2 zaehlend / Werkzeug | Transkript | ausgeschlossen |",
        "|---|---|---|---|---|---|---|",
    ]
    for key, c in sorted(result["chargen"].items()):
        a2 = c["A2"] or {}
        lines.append(
            f"| {key} | {c['V_gueltig'][0]} von {c['V_gueltig'][1]} | {fmt(c['A1_unter_90_prozent'])} "
            f"| {c['A5_formatfehler'][0]} von {c['A5_formatfehler'][1]} | {a2.get('zaehlende_treffer', UNKNOWN)} / "
            f"{a2.get('werkzeug_verstoesse', UNKNOWN)} | {'fehlt' if a2.get('transkript_fehlt') else ('gescannt' if a2.get('transkript_gescannt') else UNKNOWN)} "
            f"| {fmt(c['ausgeschlossen'])} |"
        )
    a11 = result["A11"]
    an = result["anker"]
    adj = result["adjudikation"]
    lines += [
        "",
        f"A11: Chargen mit allen drei Ratern gueltig {a11['n']} von {a11['N']} ({a11['chargen_alle_drei_gueltig']}); kein Schluss: {fmt(a11['kein_schluss'])}. "
        f"Rater ausgefallen: {result['A2']['rater_ausgefallen'] or 'keiner'}. n_rater je Karte: {json.dumps(k['n_rater'], sort_keys=True)}.",
        "",
        "## Anker (erste Platzierung)",
        "",
        f"- Streichliste (I2 Nr. 10, nur Vorschlag fuer einen Nachtrag): {an['n_streichen']} von {len(an['streichliste'])} Ankerzeilen.",
        *[f"  - {s['card']} {s['kriterium']} (Anker {fmt(s['ankerwert'], 0)}, {s['satz']}): Rater-Mittel {fmt(s['rater_mittel'], 1)}, "
          f"innerhalb 10: {s['rater_innerhalb_10']} von 3; {', '.join(s['grund'])}" for s in an["streichliste"] if s["streichen"]],
        f"- Versatz je Kartenart (I5): {json.dumps(an['versatz_je_art_I5'], ensure_ascii=False, sort_keys=True)}",
        f"- Anker-Retest (Wiederholungen): MAE {fmt(an['retest_wiederholungen']['mae'])}, n = {an['retest_wiederholungen']['n']}.",
        "",
        "## Adjudikation (I6, nach S1 bis S9)",
        "",
        f"- Karten mit Rater-Abstand >= 15 auf H_v3b: {adj['karten_abstand_ge15']}; angewendet: {fmt(adj['angewendet'])}.",
        f"- Verworfene Bewertungen je Rater: {json.dumps(adj.get('verworfene_bewertungen_je_rater', UNKNOWN), sort_keys=True)}; "
        f"Befund der Stufe von Rater A ueber Rater A: {adj.get('befund_stufe_rater_A_ueber_rater_A', UNKNOWN)}.",
        "",
        f"## Marken: Rater-Abstand >= 15 ({len(result['abstand_ge15'])} Karten, nie geloescht)",
        "",
        "| Karte | Charge | Spannweite V3b | Spannweite V3a roh |",
        "|---|---|---|---|",
        *[f"| {x['card']} | {x['charge']} | {fmt(x['spannweite_V3b'], 1)} | {fmt(x['spannweite_V3a_roh'], 1)} |" for x in result["abstand_ge15"]],
        "",
        "## Sensitivitaet und Regelclaims (nur berichtet)",
        "",
        f"- {json.dumps(result['sensitivitaet'], ensure_ascii=False, sort_keys=True)}",
        f"- Regelclaims (Seed {result['regelclaims']['seed']}, n = {result['regelclaims']['n']}): "
        + ", ".join(f"Rater {r} {result['regelclaims'][r]['stufe']} ({fmt(result['regelclaims'][r]['offensichtlich_falsch'])} von {result['regelclaims'][r]['N']})" for r in RATERS),
        "",
        "## Lesart (Co-Lead, von Hand)",
        "",
        "<!-- Lesart, Fehlalarmrate des Pilots (Plan section 3) und Owner-Vorschlag hier eintragen. -->",
        "",
    ]  # fmt: skip
    return "\n".join(lines)


# ---------------------------------------------------------------- CLI


def _json_or_none(path: Path | None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path else None


def _final_replies(path: Path | None) -> dict[str, str]:
    data = _json_or_none(path) or {}
    if not isinstance(data, Mapping):
        raise RefusedError('final replies must be a JSON object {"A:1": text}')
    return {str(k): str(v) for k, v in data.items()}


def build_parser() -> argparse.ArgumentParser:
    """Paths only: no threshold, seed or draw count is an option (A8)."""
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("hits", "claims", "adjudicate", "eval"):
        p = sub.add_parser(name)
        p.add_argument("--manifest", type=Path, required=True)
        p.add_argument("--inputs-dir", type=Path, required=True)
        p.add_argument("--rater-dir", type=Path, required=True)
        p.add_argument("--checksums", type=Path, required=True)
        p.add_argument("--out", type=Path, required=True)
        if name != "claims":
            p.add_argument("--final-replies", type=Path)
        if name in ("claims", "adjudicate"):
            p.add_argument("--key-out", type=Path, required=True)
        if name in ("adjudicate", "eval"):
            p.add_argument("--hits", type=Path, required=True)
            p.add_argument("--classification", type=Path, required=True)
            p.add_argument(
                "--classification-sha256", required=True, help="the SHA-256 posted in #1404"
            )
    pe = sub.choices["eval"]
    pe.add_argument("--tool-calls", type=Path)
    pe.add_argument("--run-log", type=Path)
    pe.add_argument(
        "--usage",
        type=Path,
        help="usage_holdout.jsonl (not in the repository); without it S7 is unbekannt",
    )
    pe.add_argument(
        "--old-runs",
        type=Path,
        help="A1 pairs.jsonl (F1 and R2 per card); without it S7 is unbekannt",
    )
    pe.add_argument(
        "--pooled", type=Path, help="second_run_full_20261122/pooled.jsonl (display condition)"
    )
    pe.add_argument("--claim-verdicts", type=Path)
    pe.add_argument("--adjudication-key", type=Path)
    pe.add_argument("--adjudication-verdicts", type=Path)
    pe.add_argument("--report", type=Path, required=True)
    pe.add_argument("--h-out", type=Path, required=True)
    pe.add_argument("--sums-out", type=Path, required=True)
    return ap


def main(argv: Sequence[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    try:
        if a.cmd == "claims":
            blind, key = run_claims(a.manifest, a.inputs_dir, a.rater_dir, a.checksums)
            a.out.write_bytes(blind)
            a.key_out.write_bytes(key)
            print(
                f"Regelclaim-Stichprobe: SHA-256 blind {sha256_bytes(blind)}, Schluessel {sha256_bytes(key)}"
            )
            return 0
        replies = _final_replies(a.final_replies)
        if a.cmd == "hits":
            data, hits, _ = run_hits(a.manifest, a.inputs_dir, a.rater_dir, a.checksums, replies)
            a.out.write_bytes(data)
            print(f"{len(hits)} Verweis-Treffer; SHA-256 der Treffer-Datei {sha256_bytes(data)}")
            return 0
        if not a.classification.exists():
            raise RefusedError(
                "classification file missing: classify the hits first (plan section 5, step 5)"
            )
        if a.cmd == "adjudicate":
            hb, hits, (man, _, frozen, data) = run_hits(
                a.manifest, a.inputs_dir, a.rater_dir, a.checksums, replies
            )
            gate_classification(hb, hits, a.hits.read_bytes(), a.classification.read_bytes(),
                                a.classification_sha256, frozen, replies)  # fmt: skip
            # A2 exclusions need the scan of eval; the list covers every valid rating (stricter).
            placed = card_ratings(man, data, {r: set() for r in RATERS})
            items, adj_key = adjudication_list(man, data, placed)
            a.out.write_bytes(
                dumps(
                    {
                        "schema": "rating-v3-adjudikation-blind-1",
                        "gruppen_max": ADJ_GROUP,
                        "karten": items,
                    }
                ).encode("utf-8")
            )
            a.key_out.write_bytes(
                dumps(
                    {"schema": "rating-v3-adjudikation-schluessel-1", "schluessel": adj_key}
                ).encode("utf-8")
            )
            print(f"{len(items)} Karten mit Rater-Abstand >= 15 auf H_v3b")
            return 0
        result, h_rows = analyse(
            manifest_path=a.manifest, inputs_dir=a.inputs_dir, rater_dir=a.rater_dir, checksums_path=a.checksums,
            hits_file_bytes=a.hits.read_bytes(), classification_bytes=a.classification.read_bytes(),
            classification_sha256=a.classification_sha256, final_replies=replies,
            run_log=_json_or_none(a.run_log), tool_calls=_json_or_none(a.tool_calls),
            usage_path=a.usage, old_runs_path=a.old_runs, pooled_path=a.pooled,
            claim_verdicts=_json_or_none(a.claim_verdicts),
            adjudication_key_bytes=a.adjudication_key.read_bytes() if a.adjudication_key else None,
            adjudication_verdicts=_json_or_none(a.adjudication_verdicts),
        )  # fmt: skip
    except RefusedError as exc:
        print(f"VERWEIGERT: {exc}", file=sys.stderr)
        return 2
    outs = {
        a.out: dumps(result).encode("utf-8"),
        a.report: report(result).encode("utf-8"),
        a.h_out: "".join(json.dumps(clean(x), ensure_ascii=False, sort_keys=True) + "\n" for x in h_rows).encode("utf-8"),
    }  # fmt: skip
    for path, data in outs.items():
        path.write_bytes(data)
    a.sums_out.write_text(
        "".join(f"{sha256_bytes(d)}  {p.name}\n" for p, d in outs.items()), encoding="utf-8"
    )
    print(f"Entscheidung: {result['entscheidung']['ergebnis']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
