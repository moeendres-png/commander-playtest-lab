#!/usr/bin/env python3
"""Evaluation of wave 2 of the second rating run of H and the pooled H (Chulane, rubric v2.1,
Refs #1404), following the plan fixed before any wave-2 output existed:
``docs/analysis-reports/rating_full_second_run_plan_20261122.md`` (sections 3 to 9).

The script changes no threshold, class, set or formula of the plan (A8). It compares only two
absolute scores of the SAME card (first rating F1, second rating R2); it never compares two cards.

Two stages, in this order (plan section 9, steps 3, 5 and 6):

  hits   Stage 1. Prints ONLY the hits of the fixed reference list (``EARLIER`` of the wave-1
         script) in the rater's own output fields (all seven ``notes``, ``reason``,
         ``uncertainty``, ``rule_claims[].claim``, never ``quote``) and in the rater's final reply
         when given; with chunk, seq, card, field and sentence. No score, no F1 value, no
         difference is read or written. The Co-Lead classifies every hit by hand (counts / does
         not count + letter a to c, doubt counts) and posts the list in #1404.
  eval   Stage 2. Refuses to run without that classification file, whose ``hits_sha256`` must
         equal the SHA-256 of the exact ``hits`` output and whose hit ids must equal the
         recomputed hits. Then sections 3 to 8: validity, A1 to A11, pooled H, spread, chunk
         effect, spells bias test (cluster bootstrap), wave effect, B1 to B3, report template.

Freeze guard (both stages): every ``rr2_output_k.jsonl`` present in the rater folder must be
listed with its SHA-256 in the checksum list (plain ``sha256sum`` format, several hashes per
file name allowed for A2 repeats); a listed file that is missing, a present file that is not
listed or a hash that differs stops the script before any output line is parsed. Inputs and
guides must match the SHA-256 in ``rr2_manifest.json``; the three wave-1 outputs must match the
SHA-256 published in the wave-1 report (#1758).

Run-log input (``--run-log``, JSON, the repository form of the Co-Lead's run log, without model
names). Every key is optional; a missing key takes the STRICT consequence named here:

  {"laufprotokoll_vorhanden": bool,           # missing/false -> A3
   "dateizugriff_protokolliert": bool,        # missing/false -> A3
   "familie_R2_gegen_F1": "gleich"|"andere"|"unbekannt",   # missing -> "unbekannt"
   "familie_R2_gegen_G1": "gleich"|"andere"|"unbekannt",   # B2 decides only with "andere"
   "gleiche_modell_id_und_stufe_wie_welle1": "ja"|"nein"|"unbekannt",  # not "ja" -> A3w
   "retest_charge_8_gelaufen": bool,          # missing/false -> B3 not computed
   "skript_vor_oeffnen_committet": bool,      # missing/false -> A10 (explorativ)
   "hashes_vor_oeffnen_gepostet": bool,       # missing/false -> A10 (explorativ)
   "a8_abweichungen": [str],                  # non-empty -> "nicht nach Plan" (A8)
   "chargen": {"k": {"blindheitsverstoss_protokoll": bool,   # missing -> false (A2 also via hits)
                     "a2_verstoesse_frueher": int,           # earlier moved-away violations
                     "abbrueche_a7": int, "nachlauf_a1": bool}}}

Classification input (``--classification``, JSON):
  {"hits_sha256": "<sha256 of the hits output file>", "github_kommentar": "<#1404 comment>",
   "einstufung": {"<hit id>": {"zaehlt": bool, "buchstabe": "a"|"b"|"c"|null}}}
``zaehlt: false`` needs a letter a to c; ``zaehlt: true`` has none.

Optional ``--tier-rule`` (JSON {"datei", "commit", "stufen": [{"name", "min_h"}]}): without it
tier changes are reported as "unbekannt" (no tier rule for H exists in the product today).
Optional ``--final-replies`` (JSON {"k": "<final reply of rater k>"}).

Standard library only, deterministic (two runs give byte-identical files): every interval uses a
fresh ``random.Random(20261124)`` and 5000 draws; no time stamps, only file base names.

Usage:
  python3 scripts/analysis/rating_second_run_full_eval.py hits --manifest M --rater-dir R \\
      --checksums SUMS [--final-replies F] --out hits.json
  python3 scripts/analysis/rating_second_run_full_eval.py eval --manifest M --rater-dir R \\
      --checksums SUMS --classification C --hits hits.json [--run-log L] [--final-replies F] \\
      --wave1-dir W1 --f1 F1 --g1 G1 --f2 F2 [--tier-rule T] \\
      --out result.json --report report.md --pooled-out pooled.jsonl
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
import statistics
import sys
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import second_run_compare as w1  # wave-1 script: same validity, regexes, statistics

SCHEMA_HITS = "rr2-verweis-treffer-1"
SCHEMA_RESULT = "rr2-auswertung-1"
SEED = 20261124
DRAWS = 5000
N_POOL = 922
N_WAVE1 = 300
N_WAVE2 = 622
POOL_CHUNKS = (1, 2, 3, 4, 5, 6, 7)
RETEST_CHUNK = 8
ALL_CHUNKS = (*POOL_CHUNKS, RETEST_CHUNK)
WAVE1_FILES = (1, 2, 3)
CRITERIA = w1.CRITERIA
SUB = w1.SUB
EARLIER = w1.EARLIER
POPULARITY = w1.POPULARITY
# SHA-256 of the wave-1 outputs as published in docs/analysis-reports/rating_second_run_20261122.md
WAVE1_OUTPUT_SHA256 = {
    "rr_output_1.jsonl": "7d55f195be2e02dbaecc549e7d4d225f1f7d5228a9068ce40d494fa50a8a815c",
    "rr_output_2.jsonl": "156cb4fd0a1ec80ae8172a5fef49fab503a955b607bad4db9d403ed02568fe0a",
    "rr_output_3.jsonl": "4d09a087521abc5c04bb3c42e305fff8aaea6015b3b9cdf47a28e3151fdce8f4",
}
WAVE1_STRATUM = {"flagged": "flagged", "top20": "top20", "rest": "rest", "rest_fill": "rest", "land": "land"}  # fmt: skip
NON_ANCHOR_SPELL_STRATA = ("top20", "rest")

# Thresholds and rules of the plan, fixed (A8). None of them is a command-line option.
A1_VALID_SHARE = 0.90  # A1: fewer than 90 % valid lines in a chunk
A1G_SHARE = 0.90  # A1g: fewer than 90 % of the 922 cards (830) with two ratings
A4_SD_RATIO = 0.6  # A4: SD(H_R2) < 0.6 x SD(H_F1)
A4_MODE_SHARE = 0.40  # A4: more than 40 % with the same H_R2
A5_FORMAT_SHARE = 0.05  # A5: more than 5 % lines with format errors
A6_CHUNK_GAP = 4.0  # A6: chunk mean d more than 4 points from the other chunks
A9_WAVE_GAP = 3.0  # A9: wave difference more than 3 points
SPELL_BIAS_THRESHOLD = -3.0  # section 6: b_W2 <= -3.0
MIN_VALID_CHUNKS = 6  # section 6 / A11: m >= 6
FLAG_GE15 = 15
FLAG_GE30 = 30
FATIGUE_GAP = 3.0
FATIGUE_RHO = 0.2
POPULARITY_SHARE = 0.05
FORMAT_GAP_H = 25  # instruction: H more than 25 from the mean of E..D needs a reason
BANDS = w1.BANDS

UNKNOWN = "unbekannt"


class RefusedError(RuntimeError):
    """The script refuses to read or evaluate (freeze guard, missing classification, ...)."""


# ---------------------------------------------------------------- small helpers


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_jsonl(path: Path) -> list[Any]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def clean(value: Any) -> Any:
    """NaN and infinities become None (never 0); tuples become lists; dict keys become strings."""
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, Mapping):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [clean(v) for v in value]
    return value


def dumps(value: Any) -> str:
    return json.dumps(clean(value), indent=1, ensure_ascii=False, sort_keys=True) + "\n"


def interval(values: Sequence[float]) -> list[float | None]:
    lo, hi = w1.percentile_interval(values)
    return [None if math.isnan(lo) else lo, None if math.isnan(hi) else hi]


# ---------------------------------------------------------------- freeze guard


def parse_checksums(text: str) -> dict[str, set[str]]:
    """``sha256sum`` lines (``<hex>  <name>`` or ``<hex> *<name>``); several hashes per name allowed."""
    out: dict[str, set[str]] = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        m = re.fullmatch(r"([0-9a-fA-F]{64}) [ *](.+)", line.strip())
        if not m:
            raise RefusedError(f"checksum line not in sha256sum format: {line!r}")
        out.setdefault(Path(m.group(2).strip()).name, set()).add(m.group(1).lower())
    return out


def output_path(rater_dir: Path, k: int) -> Path:
    return rater_dir / f"rr2_output_{k}.jsonl"


def freeze_guard(rater_dir: Path, checksums: Mapping[str, set[str]]) -> dict[int, str]:
    """SHA-256 of every present wave-2 output, each checked against the frozen list (plan section 9,
    steps 3 and 5). Raises before any output line is parsed."""
    frozen: dict[int, str] = {}
    problems: list[str] = []
    for k in ALL_CHUNKS:
        path = output_path(rater_dir, k)
        listed = checksums.get(path.name)
        if not path.exists():
            if listed:
                problems.append(f"{path.name}: listed as frozen but missing")
            continue
        digest = sha256_file(path)
        if not listed:
            problems.append(f"{path.name}: present but not frozen (not in the checksum list)")
        elif digest not in listed:
            problems.append(f"{path.name}: SHA-256 {digest} differs from the frozen list")
        else:
            frozen[k] = digest
    unknown = sorted(set(checksums) - {output_path(rater_dir, k).name for k in ALL_CHUNKS})
    if unknown:
        problems.append(f"checksum list names files that are no wave-2 output: {unknown}")
    if problems:
        raise RefusedError("freeze guard: " + "; ".join(problems))
    return frozen


def verify_rater_inputs(manifest: Mapping[str, Any], rater_dir: Path) -> dict[str, str]:
    """Inputs and guides byte-identical to the manifest (plan section 2)."""
    hashes: dict[str, str] = {}
    problems = []
    for k in ALL_CHUNKS:
        per = manifest["meta"]["per_chunk"][str(k)]
        for name, key in (
            (f"rr2_input_{k}.jsonl", "input_sha256"),
            (f"rr2_guide_{k}.md", "guide_sha256"),
        ):
            path = rater_dir / name
            digest = sha256_file(path) if path.exists() else "missing"
            hashes[name] = digest
            if digest != per[key]:
                problems.append(f"{name}: {digest} != manifest {per[key]}")
    if problems:
        raise RefusedError("rater inputs differ from the manifest: " + "; ".join(problems))
    return hashes


def verify_wave1_outputs(wave1_dir: Path) -> dict[str, str]:
    out = {}
    for name, expected in WAVE1_OUTPUT_SHA256.items():
        path = wave1_dir / name
        digest = sha256_file(path) if path.exists() else "missing"
        if digest != expected:
            raise RefusedError(f"wave-1 output {name}: {digest} != published {expected}")
        out[name] = digest
    return out


# ---------------------------------------------------------------- loading rows


def load_chunk(
    rater_dir: Path, k: int, cards: Sequence[Mapping[str, Any]], frozen: Mapping[int, str]
) -> dict[str, Any]:
    """Rows of chunk k by position. A chunk without a frozen output has no rows (all missing)."""
    inputs = load_jsonl(rater_dir / f"rr2_input_{k}.jsonl")
    man = sorted(cards, key=lambda c: c["seq"])
    if [c["oracle_id"] for c in man] != [i["oracle_id"] for i in inputs]:
        raise RefusedError(f"chunk {k}: manifest and input order differ")
    raw: list[str] = []
    present = k in frozen
    if present:
        raw = output_path(rater_dir, k).read_text(encoding="utf-8").splitlines()
    rows = []
    for pos, (m, inp) in enumerate(zip(man, inputs, strict=True), start=1):
        line = raw[pos - 1] if pos <= len(raw) else None
        row: Any = None
        parsed = False
        if line is not None:
            try:
                row = json.loads(line)
                parsed = True
            except json.JSONDecodeError:
                row = None
        if line is None:
            problems = ["missing"]
        elif not parsed:
            problems = ["not JSON"]
        else:
            problems = w1.plan_problems(row, inp)
        rows.append(
            {
                "chunk": k, "seq": pos, "oracle_id": inp["oracle_id"], "name": inp["card"],
                "stratum": m["stratum"], "is_land": bool(m["is_land"]),
                "is_anchor": bool(m["is_anchor_card"]), "block": inp["card_block"],
                "line": line, "row": row if isinstance(row, dict) else None, "problems": problems,
            }
        )  # fmt: skip
    return {
        "k": k,
        "present": present,
        "rows": rows,
        "n_lines": len(raw),
        "extra_lines": max(0, len(raw) - len(man)),
    }


# ---------------------------------------------------------------- stage 1: reference hits

_SENTENCE_END = re.compile(r"[.!?](?:\s+|$)")
_SCORE_JSON = re.compile(r'"(scores|[EFTRKDH])"\s*:\s*(\{[^}]*\}|-?\d+(?:\.\d+)?)')


def sentence_at(text: str, pos: int) -> str:
    """The sentence of ``text`` that contains character ``pos``."""
    start = 0
    for m in _SENTENCE_END.finditer(text):
        if m.end() <= pos:
            start = m.end()
        else:
            break
    end_m = _SENTENCE_END.search(text, pos)
    end = end_m.end() if end_m else len(text)
    return text[start:end].strip()


def rater_fields(row: Mapping[str, Any]) -> list[tuple[str, str]]:
    """Only the rater's own output fields (plan section 9): notes, reason, uncertainty, claim."""
    out: list[tuple[str, str]] = []
    notes = row.get("notes")
    if isinstance(notes, Mapping):
        out += [(f"notes.{k}", str(v)) for k, v in sorted(notes.items(), key=lambda kv: str(kv[0]))]
    for key in ("reason", "uncertainty"):
        if key in row:
            out.append((key, str(row[key])))
    claims = row.get("rule_claims")
    if isinstance(claims, list):
        for i, c in enumerate(claims):
            if isinstance(c, Mapping) and "claim" in c:
                out.append((f"rule_claims[{i}].claim", str(c["claim"])))
    return out


def find_hits(
    chunks: Mapping[int, Mapping[str, Any]], final_replies: Mapping[str, str]
) -> list[dict[str, Any]]:
    """Every match of the reference list, one hit per match. A line that does not parse is scanned
    as raw text with score fields blanked out (field ``rohzeile``)."""
    hits: list[dict[str, Any]] = []

    def add(k: int, seq: int, card: str, oid: str, field: str, text: str) -> None:
        for m in EARLIER.finditer(text):
            hits.append(
                {
                    "id": f"{k}:{seq}:{field}:{m.start()}", "charge": k, "seq": seq, "card": card,
                    "oracle_id": oid, "feld": field, "treffer": m.group(0),
                    "satz": sentence_at(text, m.start()),
                }
            )  # fmt: skip

    for k in sorted(chunks):
        for r in chunks[k]["rows"]:
            if r["row"] is not None:
                for field, text in rater_fields(r["row"]):
                    add(k, r["seq"], r["name"], r["oracle_id"], field, text)
            elif r["line"] is not None:
                add(
                    k,
                    r["seq"],
                    r["name"],
                    r["oracle_id"],
                    "rohzeile",
                    _SCORE_JSON.sub(r'"\1": "-"', r["line"]),
                )
        reply = final_replies.get(str(k))
        if reply:
            add(k, 0, "", "", "schlussantwort", str(reply))
    return hits


def render_hits(hits: Sequence[Mapping[str, Any]], frozen: Mapping[int, str]) -> bytes:
    per_chunk = Counter(h["charge"] for h in hits)
    doc = {
        "schema": SCHEMA_HITS,
        "regex": EARLIER.pattern,
        "felder": "notes (alle sieben), reason, uncertainty, rule_claims[].claim, Schlussantwort; nie quote",
        "eingefrorene_ausgaben_sha256": {
            f"rr2_output_{k}.jsonl": v for k, v in sorted(frozen.items())
        },
        "n_treffer": len(hits),
        "treffer_je_charge": {str(k): per_chunk.get(k, 0) for k in ALL_CHUNKS},
        "treffer": list(hits),
        "hinweis": (
            "Nur Verweis-Treffer; keine Bewertung, keine Differenz. Jeder Treffer wird von Hand "
            "eingestuft (zaehlt / zaehlt nicht + a-c, Zweifel zaehlt) und in #1404 gepostet."
        ),
    }
    return dumps(doc).encode("utf-8")


def check_classification(
    cls: Any, hits: Sequence[Mapping[str, Any]], hits_bytes: bytes
) -> dict[str, dict[str, Any]]:
    """The hand classification must belong to exactly these hits (plan section 9, step 6)."""
    if not isinstance(cls, Mapping):
        raise RefusedError("classification is not a JSON object")
    if cls.get("hits_sha256") != sha256_bytes(hits_bytes):
        raise RefusedError("classification hits_sha256 does not match the recomputed hits output")
    if not str(cls.get("github_kommentar", "")).strip():
        raise RefusedError("classification names no #1404 comment with the posted list")
    entries = cls.get("einstufung")
    if not isinstance(entries, Mapping):
        raise RefusedError("classification has no 'einstufung' object")
    ids = {h["id"] for h in hits}
    missing, extra = sorted(ids - set(entries)), sorted(set(entries) - ids)
    if missing or extra:
        raise RefusedError(f"classification ids differ: missing {missing}, extra {extra}")
    out: dict[str, dict[str, Any]] = {}
    for hid, e in entries.items():
        if not isinstance(e, Mapping) or not isinstance(e.get("zaehlt"), bool):
            raise RefusedError(f"hit {hid}: 'zaehlt' must be true or false")
        letter = e.get("buchstabe")
        if e["zaehlt"] and letter is not None:
            raise RefusedError(f"hit {hid}: a counting hit has no letter")
        if not e["zaehlt"] and letter not in ("a", "b", "c"):
            raise RefusedError(f"hit {hid}: a non-counting hit needs letter a, b or c")
        out[str(hid)] = {"zaehlt": e["zaehlt"], "buchstabe": letter}
    return out


def run_hits(
    manifest_path: Path, rater_dir: Path, checksums_path: Path, final_replies: Mapping[str, str]
) -> tuple[bytes, list[dict[str, Any]], dict[int, dict[str, Any]], dict[int, str]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    verify_rater_inputs(manifest, rater_dir)
    frozen = freeze_guard(rater_dir, parse_checksums(checksums_path.read_text(encoding="utf-8")))
    chunks = {
        k: load_chunk(rater_dir, k, [c for c in manifest["cards"] if c["chunk"] == k], frozen)
        for k in ALL_CHUNKS
    }
    hits = find_hits(chunks, final_replies)
    return render_hits(hits, frozen), hits, chunks, frozen


# ---------------------------------------------------------------- statistics


def d_stats(ds: Sequence[float]) -> dict[str, Any]:
    """Section 5 on differences d = H_R2 - H_F1."""
    n = len(ds)
    if n == 0:
        return {"n": 0}
    absd = [abs(x) for x in ds]
    sd = statistics.stdev(ds) if n > 1 else None
    rms = math.sqrt(sum(x * x for x in ds) / n)
    return {
        "n": n,
        "b": sum(ds) / n,
        "sd": sd,
        "rms": rms,
        "mean_abs": sum(absd) / n,
        "n_ge15": sum(x >= FLAG_GE15 for x in absd),
        "share_ge15": sum(x >= FLAG_GE15 for x in absd) / n,
        "max_abs": max(absd),
        "sigma1": sd / math.sqrt(2) if sd is not None else None,
        "sigma1_rms": rms / math.sqrt(2),
        "se_pooled": sd / 2 if sd is not None else None,
    }


D_KEYS = ("b", "sd", "rms", "mean_abs", "share_ge15", "sigma1", "sigma1_rms", "se_pooled")
ICC_KEYS = ("icc21", "icc22", "icc31", "spearman_brown", "spearman")


def bootstrap_multi(
    groups: Sequence[Sequence[Any]],
    fn: Callable[[list[Any]], Mapping[str, Any]],
    keys: Sequence[str],
    draws: int,
    seed: int = SEED,
) -> dict[str, list[float | None]]:
    """Same resampling as the wave-1 ``bootstrap`` (cards within each group, fresh seeded generator),
    but every statistic of one draw comes from one call of ``fn``."""
    rng = random.Random(seed)
    acc: dict[str, list[float]] = {k: [] for k in keys}
    for _ in range(draws):
        sample: list[Any] = []
        for g in groups:
            sample.extend(rng.choices(g, k=len(g)))
        res = fn(sample)
        for k in keys:
            v = res.get(k)
            acc[k].append(float("nan") if v is None else float(v))
    return {k: interval(v) for k, v in acc.items()}


def stratified_d(groups: Sequence[Sequence[float]], draws: int) -> dict[str, Any]:
    """d statistics with a card bootstrap within strata (wave x stratum), fresh seeded generator."""
    flat = [x for g in groups for x in g]
    out = d_stats(flat)
    if len(flat) > 1:
        out["ci95"] = bootstrap_multi([list(g) for g in groups if g], d_stats, D_KEYS, draws)
    return out


def anova2(pairs: Sequence[tuple[float, float]]) -> tuple[float, float, float]:
    """MSR, MSC, MSE of a two-way layout with k = 2 raters."""
    n = len(pairs)
    grand = sum(a + b for a, b in pairs) / (2 * n)
    rows = [(a + b) / 2 for a, b in pairs]
    cols = [sum(p[j] for p in pairs) / n for j in (0, 1)]
    msr = 2 * sum((m - grand) ** 2 for m in rows) / (n - 1)
    msc = n * sum((m - grand) ** 2 for m in cols)
    sse = sum((p[j] - rows[i] - cols[j] + grand) ** 2 for i, p in enumerate(pairs) for j in (0, 1))
    return msr, msc, sse / (n - 1)


def icc_set(pairs: Sequence[tuple[float, float]]) -> dict[str, float]:
    """ICC(2,1), ICC(2,2), ICC(3,1), Spearman-Brown of ICC(2,1), Spearman rho (plan B1)."""
    nan = float("nan")
    n = len(pairs)
    if n < 3:
        return {"icc21": nan, "icc22": nan, "icc31": nan, "spearman_brown": nan, "spearman": nan}
    msr, msc, mse = anova2(pairs)
    d21 = msr + mse + 2 * (msc - mse) / n
    d22 = msr + (msc - mse) / n
    icc21 = (msr - mse) / d21 if d21 else nan
    return {
        "icc21": icc21,
        "icc22": (msr - mse) / d22 if d22 else nan,
        "icc31": (msr - mse) / (msr + mse) if (msr + mse) else nan,
        "spearman_brown": 2 * icc21 / (1 + icc21) if not math.isnan(icc21) and icc21 != -1 else nan,
        "spearman": w1.spearman([a for a, _ in pairs], [b for _, b in pairs]),
    }


def icc_block(groups: Sequence[Sequence[tuple[float, float]]], draws: int) -> dict[str, Any]:
    flat = [p for g in groups for p in g]
    out: dict[str, Any] = {"n": len(flat), **icc_set(flat)}
    if len(flat) >= 3:
        out["ci95"] = bootstrap_multi([list(g) for g in groups if g], icc_set, ICC_KEYS, draws)
    return out


def cluster_bootstrap(
    clusters: Sequence[Sequence[float]], draws: int, seed: int = SEED
) -> list[float | None]:
    """Two-stage bootstrap (plan section 6): draw m clusters with replacement from the m valid
    chunks, then each drawn chunk's cards with replacement; b* = mean over all drawn cards."""
    usable = [list(c) for c in clusters if c]
    if not usable:
        return [None, None]
    rng = random.Random(seed)
    stats = []
    m = len(usable)
    for _ in range(draws):
        sample: list[float] = []
        for c in rng.choices(usable, k=m):
            sample.extend(rng.choices(c, k=len(c)))
        stats.append(sum(sample) / len(sample))
    return interval(stats)


def card_bootstrap_mean(
    values: Sequence[float], draws: int, seed: int = SEED
) -> list[float | None]:
    if not values:
        return [None, None]
    rng = random.Random(seed)
    vals = list(values)
    return interval([sum(rng.choices(vals, k=len(vals))) / len(vals) for _ in range(draws)])


def spells_verdict(
    b: float | None, ci_hi: float | None, n_negative: int, m: int, blockers: Sequence[str]
) -> str:
    """Section 6 table. ``blockers`` (A2 abort, A1g, A11) force 'kein Schluss'."""
    if blockers or m < MIN_VALID_CHUNKS or b is None or ci_hi is None:
        return "kein Schluss"
    ci_ok = ci_hi < 0
    chunks_ok = n_negative >= m - 1
    if b <= SPELL_BIAS_THRESHOLD and ci_ok and chunks_ok:
        return "bestaetigt"
    if ci_ok and chunks_ok:
        return "kleiner bestaetigt"
    return "nicht bestaetigt"


def spells_test(
    clusters: Mapping[int, Sequence[float]], blockers: Sequence[str], draws: int
) -> dict[str, Any]:
    """Bias confirmation on the non-anchor spells of the m valid wave-2 chunks."""
    ks = sorted(clusters)
    m = len(ks)
    flat = [x for k in ks for x in clusters[k]]
    per_chunk = {str(k): {"n": len(clusters[k]), "b": mean(list(clusters[k]))} for k in ks}
    n_negative = sum(1 for k in ks if clusters[k] and sum(clusters[k]) / len(clusters[k]) < 0)
    b = mean(flat)
    ci = cluster_bootstrap([clusters[k] for k in ks], draws)
    blk = list(blockers)
    if m < MIN_VALID_CHUNKS and "A11" not in blk:
        blk.append("A11")
    return {
        "m": m,
        "chunks": ks,
        "n": len(flat),
        "b_W2": b,
        "ci95_cluster": ci,
        "ci95_card_descriptive": card_bootstrap_mean(flat, draws),
        "per_chunk": per_chunk,
        "chunks_negative": n_negative,
        "needed_negative": max(m - 1, 0),
        "threshold": SPELL_BIAS_THRESHOLD,
        "blockers": blk,
        "verdict": spells_verdict(b, ci[1], n_negative, m, blk),
    }


def wave_effect(w1_d: Sequence[float], w2_d: Sequence[float], draws: int) -> dict[str, Any]:
    """A9: rest spells without anchors, wave 2 minus wave 1; card bootstrap in each wave."""
    if not w1_d or not w2_d:
        return {
            "n_w1": len(w1_d),
            "n_w2": len(w2_d),
            "diff": None,
            "ci95": [None, None],
            "welleneffekt": UNKNOWN,
        }
    rng = random.Random(SEED)
    a, b = list(w1_d), list(w2_d)
    diffs = []
    for _ in range(draws):
        sa = rng.choices(a, k=len(a))
        sb = rng.choices(b, k=len(b))
        diffs.append(sum(sb) / len(sb) - sum(sa) / len(sa))
    diff = sum(b) / len(b) - sum(a) / len(a)
    ci = interval(diffs)
    excl0 = ci[0] is not None and ci[1] is not None and (ci[0] > 0 or ci[1] < 0)
    return {
        "n_w1": len(a), "n_w2": len(b), "b_w1": sum(a) / len(a), "b_w2": sum(b) / len(b),
        "diff": diff, "ci95": ci, "welleneffekt": abs(diff) > A9_WAVE_GAP and excl0,
    }  # fmt: skip


def chunk_variance(chunk_ds: Mapping[int, Sequence[float]]) -> float | None:
    """sigma^2_Charge = max(0, Var(chunk means) - mean(Var_k / n_k)) (plan section 5)."""
    usable = {k: list(v) for k, v in chunk_ds.items() if len(v) > 1}
    if len(usable) < 2:
        return None
    means = [sum(v) / len(v) for v in usable.values()]
    within = [statistics.variance(v) / len(v) for v in usable.values()]
    return max(0.0, statistics.variance(means) - sum(within) / len(within))


def chunk_effect(chunk_ds: Mapping[int, Sequence[float]]) -> dict[str, Any]:
    """A6: a chunk's mean d against the other valid chunks (mean of their means and, as the stricter
    second reading, the pooled mean of their cards; either above 4 flags)."""
    out: dict[str, Any] = {}
    ks = sorted(k for k, v in chunk_ds.items() if v)
    for k in ks:
        own = sum(chunk_ds[k]) / len(chunk_ds[k])
        others = [j for j in ks if j != k]
        if not others:
            out[str(k)] = {
                "mean_d": own,
                "gap_means": None,
                "gap_pooled": None,
                "auffaellig": UNKNOWN,
            }
            continue
        om = sum(sum(chunk_ds[j]) / len(chunk_ds[j]) for j in others) / len(others)
        pooled = [x for j in others for x in chunk_ds[j]]
        op = sum(pooled) / len(pooled)
        out[str(k)] = {
            "mean_d": own, "n": len(chunk_ds[k]), "gap_means": own - om, "gap_pooled": own - op,
            "auffaellig": abs(own - om) > A6_CHUNK_GAP or abs(own - op) > A6_CHUNK_GAP,
        }  # fmt: skip
    return out


def scale_compression(f1: Sequence[float], r2: Sequence[float]) -> dict[str, Any]:
    """A4 on the same cards: SD(H_R2) < 0.6 x SD(H_F1) or > 40 % with the same H_R2 (population SD
    as in the wave-1 script)."""
    if len(r2) < 2:
        return {"n": len(r2), "triggered": False, "reason": "zu wenige gueltige Zeilen"}
    sd_new, sd_old = statistics.pstdev(r2), statistics.pstdev(f1)
    mode_val, mode_n = Counter(r2).most_common(1)[0]
    return {
        "n": len(r2), "sd_r2": sd_new, "sd_f1": sd_old, "mode": mode_val, "mode_n": mode_n,
        "mode_share": mode_n / len(r2),
        "triggered": sd_new < A4_SD_RATIO * sd_old or mode_n > A4_MODE_SHARE * len(r2),
    }  # fmt: skip


def a1g_threshold(n_pool: int) -> int:
    """A1g: at least 90 % of the pool with two ratings (830 of 922)."""
    return math.ceil(A1G_SHARE * n_pool - 1e-9)


def pool_card(h_f1: float, h_r2: float | None) -> tuple[float, int]:
    """Section 4: mean of F1 and R2 only with two valid ratings; otherwise F1 and n = 1."""
    if h_r2 is None:
        return float(h_f1), 1
    return (h_f1 + h_r2) / 2, 2


def deviation_marks(d: float | None) -> list[str]:
    if d is None:
        return []
    marks = []
    if abs(d) >= FLAG_GE15:
        marks.append("abweichung_ge15")
    if abs(d) >= FLAG_GE30:
        marks.append("abweichung_ge30")
    return marks


def band_index(h: float) -> int:
    for i, (low, _) in enumerate(BANDS):
        if h >= low:
            return i
    return len(BANDS) - 1


def tier_of(h: float, rule: Mapping[str, Any]) -> str:
    for st in sorted(rule["stufen"], key=lambda s: -float(s["min_h"])):
        if h >= float(st["min_h"]):
            return str(st["name"])
    return "unterhalb"


def change_counts(
    cards: Sequence[Mapping[str, Any]], key: str, tier_rule: Mapping[str, Any] | None
) -> dict[str, Any]:
    """Cards whose guide band, side of H >= 50 and tier change against H_F1, per direction."""
    n = len(cards)
    band_up = sum(band_index(c[key]) < band_index(c["H_F1"]) for c in cards)
    band_down = sum(band_index(c[key]) > band_index(c["H_F1"]) for c in cards)
    side_up = sum(c["H_F1"] < 50 <= c[key] for c in cards)
    side_down = sum(c[key] < 50 <= c["H_F1"] for c in cards)
    out: dict[str, Any] = {
        "N": n,
        "band_hoeher": band_up, "band_tiefer": band_down,
        "seite50_nach_oben": side_up, "seite50_nach_unten": side_down,
    }  # fmt: skip
    if tier_rule is None:
        out["stufe_wechsel"] = UNKNOWN
    else:
        ranks = {str(s["name"]): float(s["min_h"]) for s in tier_rule["stufen"]}
        ranks["unterhalb"] = -1.0
        up = sum(
            ranks[tier_of(c[key], tier_rule)] > ranks[tier_of(c["H_F1"], tier_rule)] for c in cards
        )
        down = sum(
            ranks[tier_of(c[key], tier_rule)] < ranks[tier_of(c["H_F1"], tier_rule)] for c in cards
        )
        out["stufe_wechsel"] = {
            "hoeher": up,
            "tiefer": down,
            "regel_datei": tier_rule.get("datei"),
            "regel_commit": tier_rule.get("commit"),
        }
    return out


def fatigue(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Section 9: mean |d| first against second half of positions, Spearman(position, d)."""
    pts = sorted((r["seq"], r["d"]) for r in rows if r.get("d") is not None)
    if len(pts) < 3:
        return {"n": len(pts), "auffaellig": UNKNOWN}
    c = max(r["seq"] for r in rows)
    half = c // 2
    first = [abs(d) for s, d in pts if s <= half]
    second = [abs(d) for s, d in pts if s > half]
    rho = w1.spearman([float(s) for s, _ in pts], [float(d) for _, d in pts])
    m1, m2 = mean(first), mean(second)
    gap = abs(m1 - m2) if m1 is not None and m2 is not None else None
    flag: Any = (
        UNKNOWN if gap is None or math.isnan(rho) else (gap > FATIGUE_GAP or abs(rho) > FATIGUE_RHO)
    )
    return {
        "n": len(pts),
        "mean_abs_first": m1,
        "mean_abs_second": m2,
        "rho_pos_d": rho,
        "auffaellig": flag,
    }


# ---------------------------------------------------------------- run log


def run_log_view(log: Mapping[str, Any] | None) -> dict[str, Any]:
    """Strict defaults for every missing key (docstring)."""
    lg = dict(log or {})

    def tri(key: str, allowed: tuple[str, ...]) -> str:
        v = lg.get(key)
        return v if v in allowed else UNKNOWN

    present = lg.get("laufprotokoll_vorhanden") is True
    access = lg.get("dateizugriff_protokolliert") is True
    view: dict[str, Any] = {
        "vorhanden": present,
        "dateizugriff_protokolliert": access,
        "familie_R2_gegen_F1": tri("familie_R2_gegen_F1", ("gleich", "andere")),
        "familie_R2_gegen_G1": tri("familie_R2_gegen_G1", ("gleich", "andere")),
        "gleiche_modell_id_und_stufe_wie_welle1": tri(
            "gleiche_modell_id_und_stufe_wie_welle1", ("ja", "nein")
        ),
        "retest_charge_8_gelaufen": lg.get("retest_charge_8_gelaufen") is True,
        "skript_vor_oeffnen_committet": lg.get("skript_vor_oeffnen_committet") is True,
        "hashes_vor_oeffnen_gepostet": lg.get("hashes_vor_oeffnen_gepostet") is True,
        "a8_abweichungen": [str(x) for x in lg.get("a8_abweichungen", []) or []],
        "chargen": {},
    }
    raw = lg.get("chargen") if isinstance(lg.get("chargen"), Mapping) else {}
    assert isinstance(raw, Mapping)
    for k in ALL_CHUNKS:
        c = raw.get(str(k), {}) if isinstance(raw.get(str(k), {}), Mapping) else {}
        prior = c.get("a2_verstoesse_frueher", 0)
        view["chargen"][str(k)] = {
            "blindheitsverstoss_protokoll": c.get("blindheitsverstoss_protokoll") is True,
            "a2_verstoesse_frueher": prior if isinstance(prior, int) and prior >= 0 else 0,
            "abbrueche_a7": c.get("abbrueche_a7", 0)
            if isinstance(c.get("abbrueche_a7", 0), int)
            else 0,
            "nachlauf_a1": c.get("nachlauf_a1") is True,
        }
    view["A3"] = not (present and access)
    view["A3w"] = view["gleiche_modell_id_und_stufe_wie_welle1"] != "ja"
    view["A10"] = not (view["skript_vor_oeffnen_committet"] and view["hashes_vor_oeffnen_gepostet"])
    view["A8"] = bool(view["a8_abweichungen"])
    return view


# ---------------------------------------------------------------- stage 2: evaluation


def _score(row: Mapping[str, Any], k: str) -> int:
    return int(w1.round5(row["scores"][k]))


def analyse(
    *,
    manifest_path: Path,
    rater_dir: Path,
    checksums_path: Path,
    classification: Any,
    hits_file_bytes: bytes,
    run_log: Mapping[str, Any] | None,
    final_replies: Mapping[str, str],
    wave1_dir: Path,
    f1_path: Path,
    g1_path: Path,
    f2_path: Path,
    tier_rule: Mapping[str, Any] | None,
    draws: int | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Stage 2. ``draws`` is only for tests; the command line always uses the plan's 5000."""
    draws = DRAWS if draws is None else draws
    # ---- stage-1 gate: hits recomputed and classified before any difference
    hits_bytes, hits, chunks, frozen = run_hits(
        manifest_path, rater_dir, checksums_path, final_replies
    )
    if hits_file_bytes != hits_bytes:
        raise RefusedError("the given hits file differs from the recomputed hits output")
    cls = check_classification(classification, hits, hits_bytes)
    wave1_hashes = verify_wave1_outputs(wave1_dir)
    log = run_log_view(run_log)
    # ---- A2 per chunk
    counting = Counter(h["charge"] for h in hits if cls[h["id"]]["zaehlt"])
    a2: dict[int, dict[str, Any]] = {}
    for k in ALL_CHUNKS:
        lc = log["chargen"][str(k)]
        current = counting.get(k, 0) > 0 or lc["blindheitsverstoss_protokoll"]
        total = lc["a2_verstoesse_frueher"] + int(current)
        a2[k] = {
            "zaehlende_treffer": counting.get(k, 0), "verstoss_protokoll": lc["blindheitsverstoss_protokoll"],
            "verstoesse_frueher": lc["a2_verstoesse_frueher"], "verstoss_aktuell": current,
            "verstoesse_gesamt": total, "ausgeschlossen": current,
            "grund": ("A2_zweiter_verstoss" if total >= 2 else "A2_verstoss") if current else None,
        }  # fmt: skip
    violation_chunks = sorted(k for k in ALL_CHUNKS if a2[k]["verstoesse_gesamt"] >= 1)
    a2_abort = len(violation_chunks) >= 2

    # ---- F1, wave 1
    f1 = {r["oracle_id"]: r for r in load_jsonl(f1_path)}
    if len(f1) != N_POOL:
        raise RefusedError(f"F1 has {len(f1)} cards, expected {N_POOL}")
    w1_manifest = json.loads((wave1_dir / "rr_sample_manifest.json").read_text(encoding="utf-8"))
    cards: dict[str, dict[str, Any]] = {}
    for f in WAVE1_FILES:
        inputs = load_jsonl(wave1_dir / f"rr_input_{f}.jsonl")
        raw = (wave1_dir / f"rr_output_{f}.jsonl").read_text(encoding="utf-8").splitlines()
        man = sorted(
            (c for c in w1_manifest["cards"] if c["input_file"] == f), key=lambda c: c["seq"]
        )
        for pos, (m, inp) in enumerate(zip(man, inputs, strict=True), start=1):
            row: Any = None
            if pos <= len(raw):
                try:
                    row = json.loads(raw[pos - 1])
                except json.JSONDecodeError:
                    row = None
            problems = w1.plan_problems(row, inp) if row is not None else ["missing"]
            cards[inp["oracle_id"]] = {
                "oracle_id": inp["oracle_id"], "name": inp["card"], "wave": 1, "source": f"welle1:{f}",
                "chunk": None, "seq": pos, "stratum": WAVE1_STRATUM[m["stratum"]], "is_land": bool(m["is_land"]),
                "is_anchor": bool(m["is_anchor_card"]), "row": row if not problems else None, "problems": problems,
            }  # fmt: skip

    # ---- wave 2 chunks 1..7: validity, A1, A5, V1-V4, A4
    chunk_info: dict[str, Any] = {}
    excluded: dict[int, str] = {}
    for k in POOL_CHUNKS:
        ch = chunks[k]
        rows = ch["rows"]
        c_n = len(rows)
        valid = [r for r in rows if not r["problems"]]
        non5 = [r for r in valid if any(v % 5 for v in r["row"]["scores"].values())]
        fmt_err = {
            r["seq"] for r in rows
            if r["row"] is not None and (
                "oracle_id" in r["problems"] or "scores keys" in r["problems"]
                or (isinstance(r["row"].get("scores"), dict) and any(isinstance(v, int) and v % 5 for v in r["row"]["scores"].values()))
            )
        }  # fmt: skip
        guide = (rater_dir / f"rr2_guide_{k}.md").read_text(encoding="utf-8")
        try:
            chulane = w1.norm_ws(w1.chulane_text(guide))
        except StopIteration:
            chulane = ""
        n_claims = n_lit = 0
        for r in valid:
            block = w1.norm_ws(r["block"])
            for rc in r["row"].get("rule_claims", []) or []:
                if isinstance(rc, Mapping):
                    n_claims += 1
                    q = w1.norm_ws(str(rc.get("quote", "")))
                    n_lit += bool(q) and (q in block or q in chulane)
        gaps_hi = gaps_lo = 0
        for r in valid:
            sc = {x: _score(r["row"], x) for x in CRITERIA}
            mu = sum(sc[x] for x in SUB) / len(SUB)
            if sc["H"] - mu > FORMAT_GAP_H:
                gaps_hi += 1
            elif mu - sc["H"] > FORMAT_GAP_H:
                gaps_lo += 1
        pop_cards = sorted({
            r["seq"] for r in rows if r["row"] is not None
            for _, text in rater_fields(r["row"]) if POPULARITY.search(text)
        })  # fmt: skip
        info: dict[str, Any] = {
            "C": c_n, "ausgabe_vorhanden": ch["present"], "zeilen": ch["n_lines"], "zusatzzeilen": ch["extra_lines"],
            "V1_gueltig": [len(valid), c_n],
            "V2_alle_7_werte": [sum(1 for r in rows if r["row"] is not None and "scores keys" not in r["problems"]), c_n],
            "V3_vielfache_von_5": [len(valid) - len(non5), len(valid)],
            "V4_zitate_woertlich": [n_lit, n_claims],
            "A1_unter_90_prozent": len(valid) < A1_VALID_SHARE * c_n,
            "A5_formatfehler": [len(fmt_err), c_n], "A5_ausgeloest": len(fmt_err) > A5_FORMAT_SHARE * c_n,
            "formatluecken_H_gt25_vom_mittel": {"H_ueber_mittel": gaps_hi, "H_unter_mittel": gaps_lo, "N_gueltig": len(valid),
                                                "hinweis": "nur gezaehlt; ob die Begruendung fehlt, wird von Hand gelesen"},
            "beliebtheit_stichwort_karten": [len(pop_cards), c_n],
            "beliebtheit_von_hand_pruefen": len(pop_cards) > POPULARITY_SHARE * c_n,
            "nicht_gueltig": {str(r["seq"]): r["problems"] for r in rows if r["problems"]},
            "A2": a2[k], "A7_abbrueche": log["chargen"][str(k)]["abbrueche_a7"],
            "A1_nachlauf_protokolliert": log["chargen"][str(k)]["nachlauf_a1"],
        }  # fmt: skip
        if a2_abort:
            excluded[k] = "A2_abbruch_welle2"
        elif a2[k]["ausgeschlossen"]:
            excluded[k] = str(a2[k]["grund"])
        if k not in excluded:
            # A4 needs F1 values; computed only after A2 (classification in place)
            info["A4"] = scale_compression(
                [float(f1[r["oracle_id"]]["scores"]["H"]) for r in valid],
                [float(_score(r["row"], "H")) for r in valid],
            )
            if info["A4"]["triggered"]:
                excluded[k] = "A4_skalenstauchung"
        info["ausgeschlossen"] = excluded.get(k)
        chunk_info[str(k)] = info
        for r in rows:
            cards[r["oracle_id"]] = {
                "oracle_id": r["oracle_id"], "name": r["name"], "wave": 2, "source": f"welle2:{k}", "chunk": k,
                "seq": r["seq"], "stratum": r["stratum"], "is_land": r["is_land"], "is_anchor": r["is_anchor"],
                "row": r["row"] if not r["problems"] else None, "problems": r["problems"],
            }  # fmt: skip
    if set(cards) != set(f1):
        raise RefusedError("wave 1 and wave 2 do not cover the 922 F1 cards exactly")
    valid_chunks = [k for k in POOL_CHUNKS if k not in excluded]
    m = len(valid_chunks)

    # ---- pooling (section 4)
    pooled: list[dict[str, Any]] = []
    for oid in sorted(cards):
        c = cards[oid]
        fr = f1[oid]
        h_f1 = float(fr["scores"]["H"])
        reason = None
        r2row = c["row"]
        if r2row is None:
            reason = "fehlt" if c["problems"] == ["missing"] else "ungueltig"
        elif c["chunk"] is not None and c["chunk"] in excluded:
            reason = f"charge_ausgeschlossen:{excluded[c['chunk']]}"
            r2row = None
        h_r2 = float(_score(r2row, "H")) if r2row is not None else None
        h_pool, n_b = pool_card(h_f1, h_r2)
        d = h_r2 - h_f1 if h_r2 is not None else None
        marks = deviation_marks(d)
        if n_b == 1:
            marks.insert(0, "nur_erstbewertung")
        sub = {
            x: (float(fr["scores"][x]) + _score(r2row, x)) / 2
            if r2row is not None
            else float(fr["scores"][x])
            for x in SUB
        }
        c.update({"H_F1": h_f1, "H_R2": h_r2, "H_pooled": h_pool, "d": d, "n_bewertungen": n_b})
        pooled.append({
            "oracle_id": oid, "card": c["name"], "H_pooled": h_pool, "n_bewertungen": n_b, "H_F1": h_f1, "H_R2": h_r2,
            "quelle_R2": c["source"], "marken": marks, "grund_nur_erstbewertung": reason,
            "teilkriterien_gepoolt": sub,
        })  # fmt: skip
    pairs_all = [c for c in cards.values() if c["d"] is not None]
    n_pairs = len(pairs_all)
    a1g_min = a1g_threshold(N_POOL)
    a1g = n_pairs < a1g_min

    # ---- A6 chunk effect, sigma^2_Charge, fatigue
    chunk_ds = {k: [c["d"] for c in pairs_all if c["chunk"] == k] for k in valid_chunks}
    a6 = chunk_effect(chunk_ds)
    a6_no_anchor = chunk_effect(
        {
            k: [c["d"] for c in pairs_all if c["chunk"] == k and not c["is_anchor"]]
            for k in valid_chunks
        }
    )
    flagged_chunks = sorted(int(k) for k, v in a6.items() if v["auffaellig"] is True)
    for p in pooled:
        c = cards[p["oracle_id"]]
        if c["chunk"] in flagged_chunks and p["n_bewertungen"] == 2:
            p["marken"].append("charge_auffaellig")
    fat = {str(k): fatigue([c for c in pairs_all if c["chunk"] == k]) for k in valid_chunks}

    # ---- spread (section 5)
    def cells(sel: Iterable[dict[str, Any]]) -> list[list[float]]:
        g: dict[tuple[int, str], list[float]] = {}
        for c in sorted(sel, key=lambda c: (c["wave"], c["stratum"], c["oracle_id"])):
            g.setdefault((c["wave"], c["stratum"]), []).append(c["d"])
        return [g[key] for key in sorted(g)]

    def group(sel_fn: Callable[[dict[str, Any]], bool]) -> dict[str, Any]:
        sel = [c for c in pairs_all if sel_fn(c)]
        out = stratified_d(cells(sel), draws)
        out["N"] = sum(1 for c in cards.values() if sel_fn(c))
        return out

    spread: dict[str, Any] = {"gesamt": group(lambda c: True), "welle1": group(lambda c: c["wave"] == 1),
                              "welle2": group(lambda c: c["wave"] == 2)}  # fmt: skip

    def is_cell(w: int, s: str) -> Callable[[dict[str, Any]], bool]:
        return lambda c: bool(c["wave"] == w and c["stratum"] == s)

    def is_chunk(k: int) -> Callable[[dict[str, Any]], bool]:
        return lambda c: bool(c["chunk"] == k)

    def is_file(f: int) -> Callable[[dict[str, Any]], bool]:
        return lambda c: bool(c["source"] == f"welle1:{f}")

    def is_band(lab: str) -> Callable[[dict[str, Any]], bool]:
        return lambda c: bool(w1.band(c["H_F1"]) == lab)

    spread["schicht"] = {
        f"welle{w}:{s}": group(is_cell(w, s))
        for w, s in sorted({(c["wave"], c["stratum"]) for c in cards.values()})
    }
    spread["kartenart"] = {
        "spell": group(lambda c: not c["is_land"]),
        "land": group(lambda c: c["is_land"]),
    }
    spread["charge"] = {str(k): group(is_chunk(k)) for k in POOL_CHUNKS}
    spread["datei_welle1"] = {str(f): group(is_file(f)) for f in WAVE1_FILES}
    spread["band_H_F1"] = {lab: group(is_band(lab)) for _, lab in BANDS}
    spread["sigma2_charge"] = chunk_variance(chunk_ds)
    spread["anteil_ge15_je_klasse"] = {
        "spell": spread["kartenart"]["spell"].get("share_ge15"), "land": spread["kartenart"]["land"].get("share_ge15"),
    }  # fmt: skip

    # ---- spells bias test (section 6), wave effect (A9), lands
    blockers = []
    if a2_abort:
        blockers.append("A2_abbruch")
    if a1g:
        blockers.append("A1g")
    clusters = {
        k: [c["d"] for c in sorted(pairs_all, key=lambda c: (c["chunk"] or 0, c["seq"]))
            if c["chunk"] == k and not c["is_anchor"] and not c["is_land"] and c["stratum"] in NON_ANCHOR_SPELL_STRATA]
        for k in valid_chunks
    }  # fmt: skip
    spells = spells_test(clusters, blockers, draws)
    anchor_spells = d_stats(
        [c["d"] for c in pairs_all if c["wave"] == 2 and c["is_anchor"] and not c["is_land"]]
    )
    w1_rest = [c["d"] for c in sorted(pairs_all, key=lambda c: c["oracle_id"])
               if c["wave"] == 1 and c["stratum"] == "rest" and not c["is_land"] and not c["is_anchor"]]  # fmt: skip
    w2_rest = [c["d"] for c in sorted(pairs_all, key=lambda c: c["oracle_id"])
               if c["wave"] == 2 and c["stratum"] == "rest" and not c["is_anchor"]]  # fmt: skip
    a9 = wave_effect(w1_rest, w2_rest, draws)
    lands = d_stats([c["d"] for c in pairs_all if c["is_land"]])
    lands["N"] = sum(1 for c in cards.values() if c["is_land"])
    lands["urteil"] = "kein Schluss (nur 12 Laender in Welle 2; explorativ)"

    # ---- K0 / K1
    b_w2 = spells["b_W2"]
    k1_allowed_reasons = []
    if spells["verdict"] != "bestaetigt":
        k1_allowed_reasons.append(f"Spells-Test: {spells['verdict']}")
    if log["A10"]:
        k1_allowed_reasons.append("A10")
    if a9["welleneffekt"] is True:
        k1_allowed_reasons.append("A9 Welleneffekt: Korrektur je Welle, kein gemeinsamer Wert")
    if a1g:
        k1_allowed_reasons.append("A1g")
    if log["A8"]:
        k1_allowed_reasons.append("A8 nicht nach Plan")
    pool_view = [{**cards[p["oracle_id"]], "H_pooled": p["H_pooled"]} for p in pooled]
    k0_changes = change_counts(pool_view, "H_pooled", tier_rule)
    k1: dict[str, Any] = {
        "berechnet": False,
        "grund": "nur bei Urteil 'bestaetigt' (Plan section 6)",
    }
    if spells["verdict"] == "bestaetigt" and b_w2 is not None:
        for c in pool_view:
            if c["n_bewertungen"] == 2 and not c["is_land"]:
                c["H_pooled_K1"] = (c["H_F1"] + c["H_R2"] - b_w2) / 2
            else:
                c["H_pooled_K1"] = c["H_pooled"]
        k1 = {
            "berechnet": True,
            "b_W2": b_w2,
            "aenderungen": change_counts(pool_view, "H_pooled_K1", tier_rule),
        }
        if a9["welleneffekt"] is True:
            b_w1 = mean(
                [
                    c["d"]
                    for c in pairs_all
                    if c["wave"] == 1
                    and not c["is_land"]
                    and c["stratum"] in NON_ANCHOR_SPELL_STRATA
                ]
            )
            k1["je_welle"] = {"b_W1_explorativ": b_w1, "b_W2": b_w2}
        for p, c in zip(pooled, pool_view, strict=True):
            p["H_pooled_K1_vorschlag"] = c["H_pooled_K1"]

    # ---- B1, B2, B3
    def icc_groups(sel: Iterable[dict[str, Any]]) -> list[list[tuple[float, float]]]:
        g: dict[tuple[int, str], list[tuple[float, float]]] = {}
        for c in sorted(sel, key=lambda c: (c["wave"], c["stratum"], c["oracle_id"])):
            g.setdefault((c["wave"], c["stratum"]), []).append((c["H_F1"], c["H_R2"]))
        return [g[key] for key in sorted(g)]

    b1 = {
        "gesamt": icc_block(icc_groups(pairs_all), draws),
        "welle1": icc_block(icc_groups(c for c in pairs_all if c["wave"] == 1), draws),
        "welle2": icc_block(icc_groups(c for c in pairs_all if c["wave"] == 2), draws),
        "urteil": "kein Schluss (A1g)" if a1g else "nur berichtet (Annahmen section 5)",
    }

    def third_run(path: Path, label: str, decisive: bool) -> dict[str, Any]:
        ref = {r["oracle_id"]: r for r in load_jsonl(path)}
        ids = sorted(o for o in ref if o in cards)
        rows3 = [
            (cards[o]["H_F1"], cards[o]["H_pooled"], float(ref[o]["scores"]["H"]), cards[o])
            for o in ids
        ]
        out: dict[str, Any] = {
            "lauf": label,
            "n": len(rows3),
            "n_mit_zwei_bewertungen": sum(r[3]["n_bewertungen"] == 2 for r in rows3),
        }
        if not rows3:
            out["urteil"] = UNKNOWN
            return out

        def delta(sample: list[Any]) -> float:
            first = sum(abs(a - g) for a, _, g, _ in sample) / len(sample)
            pooled_err = sum(abs(p - g) for _, p, g, _ in sample) / len(sample)
            return float(first - pooled_err)

        rng = random.Random(SEED)
        boots = [delta(rng.choices(rows3, k=len(rows3))) for _ in range(draws)]
        out["delta_K0"] = delta(rows3)
        out["ci95_K0"] = interval(boots)
        out["spearman_F1_ref"] = w1.spearman([r[0] for r in rows3], [r[2] for r in rows3])
        out["spearman_pooled_ref"] = w1.spearman([r[1] for r in rows3], [r[2] for r in rows3])
        if k1["berechnet"]:
            k1rows = [
                (
                    a,
                    next(c["H_pooled_K1"] for c in pool_view if c["oracle_id"] == r3["oracle_id"]),
                    g,
                    r3,
                )
                for a, _, g, r3 in rows3
            ]
            rng = random.Random(SEED)
            out["delta_K1"] = delta(k1rows)
            out["ci95_K1"] = interval(
                [delta(rng.choices(k1rows, k=len(k1rows))) for _ in range(draws)]
            )
        lo, hi = out["ci95_K0"]
        if not decisive:
            out["urteil"] = "nur beschreibend"
        elif a1g:
            out["urteil"] = "kein Schluss (A1g)"
        elif log["A3"] or log["familie_R2_gegen_G1"] != "andere":
            fam = log["familie_R2_gegen_G1"]
            out["urteil"] = (
                "unbelegt (Uebereinstimmung mit einem Lauf derselben Familie)"
                if fam == "gleich"
                else "unbelegt (Familie R2 gegen G1 unbekannt oder A3)"
            )
        elif lo is not None and lo > 0:
            out["urteil"] = "besser belegt"
        elif hi is not None and hi < 0:
            out["urteil"] = "schlechter"
        else:
            out["urteil"] = "kein Schluss"
        return out

    b2 = third_run(g1_path, "G1", decisive=True)
    f2 = third_run(f2_path, "F2 (F1-Familie, zieht zu F1 hin)", decisive=False)

    b3: dict[str, Any] = {"berechnet": False}
    if not log["retest_charge_8_gelaufen"]:
        b3["grund"] = "Charge 8 laut Laufprotokoll nicht gelaufen oder unbekannt"
    elif not chunks[RETEST_CHUNK]["present"]:
        b3["grund"] = "keine eingefrorene Ausgabe der Charge 8"
    elif a2[RETEST_CHUNK]["ausgeschlossen"]:
        b3["grund"] = f"Charge 8 ungueltig ({a2[RETEST_CHUNK]['grund']})"
    else:
        rt = []
        for r in chunks[RETEST_CHUNK]["rows"]:
            cw = cards.get(r["oracle_id"])
            if r["problems"] or cw is None or cw["wave"] != 1 or cw["H_R2"] is None:
                continue
            rt.append((cw["H_R2"], float(_score(r["row"], "H")), cw["H_F1"]))
        d_rt = [b - a for a, b, _ in rt]
        st = d_stats(d_rt)
        same = d_stats([a - f for a, _, f in rt])
        b3 = {
            "berechnet": True, "n": len(rt), "N": len(chunks[RETEST_CHUNK]["rows"]),
            "verzerrung": st.get("b"), "sd_rt_durch_wurzel2": st.get("sigma1"),
            "icc21": w1.icc21([(a, b) for a, b, _ in rt]), "sigma1_F1_R2_gleiche_karten": same.get("sigma1"),
            "urteil": "nur beschreibend, nie ein Beleg fuer 'besser'",
        }  # fmt: skip

    # ---- labels, provenance
    labels = []
    if log["A10"]:
        labels.append("explorativ, nicht nach Plan (A10)")
    if log["A8"]:
        labels.append("nicht nach Plan (A8): " + "; ".join(log["a8_abweichungen"]))
    if log["A3"]:
        labels.append("zwei Bewertungen, Unabhaengigkeit ungeprueft (A3)")
    if log["A3w"]:
        labels.append("Kennzahlen je Welle getrennt; nie 'ein Rater R2' (A3w)")
    if a2_abort:
        labels.append("Abbruch Welle 2, kein Schluss (A2: Verstoesse in zwei Chargen)")
    anzeige_block = [x for x, on in (("A1g", a1g), ("A2_abbruch", a2_abort)) if on]

    list_ge15 = []
    for p in pooled:
        if "abweichung_ge15" in p["marken"]:
            c = cards[p["oracle_id"]]
            list_ge15.append({
                "card": p["card"], "oracle_id": p["oracle_id"], "quelle_R2": p["quelle_R2"], "H_F1": p["H_F1"],
                "H_R2": p["H_R2"], "d": c["d"], "ge30": "abweichung_ge30" in p["marken"],
                "begruendung_R2": c["row"].get("reason", "") if c["row"] else "", "begruendung_F1": f1[p["oracle_id"]].get("reason", ""),
            })  # fmt: skip
    list_ge15.sort(key=lambda x: (-abs(x["d"]), x["card"]))

    provenance = {
        "skript_sha256": sha256_file(Path(__file__)),
        "seed": SEED, "draws": draws, "N_pool": N_POOL,
        "eingaben_sha256": {
            manifest_path.name: sha256_file(manifest_path), f1_path.name: sha256_file(f1_path),
            g1_path.name: sha256_file(g1_path), f2_path.name: sha256_file(f2_path),
            checksums_path.name: sha256_file(checksums_path),
            "hits.json": sha256_bytes(hits_bytes), "rr_sample_manifest.json": sha256_file(wave1_dir / "rr_sample_manifest.json"),
            **{f"rr2_output_{k}.jsonl": v for k, v in sorted(frozen.items())}, **wave1_hashes,
        },
        "klassifikation_kommentar": str(classification.get("github_kommentar")),
        "tierregel": {"datei": tier_rule.get("datei"), "commit": tier_rule.get("commit")} if tier_rule else UNKNOWN,
    }  # fmt: skip
    result = {
        "schema": SCHEMA_RESULT,
        "kennzeichnung": labels,
        "laufprotokoll": log,
        "herkunft": provenance,
        "verweis_treffer": {"n": len(hits), "zaehlend_je_charge": {str(k): counting.get(k, 0) for k in ALL_CHUNKS},
                            "einstufung": [{**h, **cls[h["id"]]} for h in hits]},
        "A2": {"verstoss_chargen": violation_chunks, "abbruch": a2_abort},
        "chargen": chunk_info,
        "gueltige_chargen": {"m": m, "chargen": valid_chunks, "ausgeschlossen": {str(k): v for k, v in sorted(excluded.items())}},
        "paare": {"n": n_pairs, "N": N_POOL, "A1g": a1g, "schwelle": a1g_min},
        "streuung": spread,
        "A6_chargeneffekt": a6, "A6_ohne_anker_beschreibend": a6_no_anchor, "A6_auffaellige_chargen": flagged_chunks,
        "ermuedung": fat,
        "spells_test": spells,
        "anker_spells_welle2": anchor_spells,
        "A9_welleneffekt": a9,
        "laender": lands,
        "K0_aenderungen": k0_changes,
        "K1": k1,
        "vorschlag": {
            "K1_vorschlag_erlaubt": not k1_allowed_reasons, "K1_gruende_dagegen": k1_allowed_reasons,
            "anzeige_vorschlag_erlaubt": not anzeige_block, "anzeige_gruende_dagegen": anzeige_block,
            "hinweis": "Owner entscheidet; nichts wird angewendet.",
        },
        "B1": b1, "B2_G1": b2, "F2_beschreibend": f2, "B3_retest": b3,
        "abweichungen_ge15": list_ge15,
        "nicht_umgesetzt": ["Regelclaim-Stichprobe section 9 (Seed 20261125, blind zur Herkunft): nicht Teil dieses Skripts"],
    }  # fmt: skip
    return clean(result), pooled


# ---------------------------------------------------------------- report template


def fmt(v: Any, digits: int = 2) -> str:
    if v is None:
        return UNKNOWN
    if isinstance(v, bool):
        return "ja" if v else "nein"
    if isinstance(v, float):
        return f"{v:.{digits}f}".replace(".", ",")
    return str(v)


def fmt_ci(ci: Any) -> str:
    if not isinstance(ci, list) or len(ci) != 2:
        return UNKNOWN
    return f"[{fmt(ci[0])}; {fmt(ci[1])}]"


def report(result: Mapping[str, Any]) -> str:
    """Markdown template with every number, n/N and its source; the Co-Lead adds the reading."""
    s = result["streuung"]
    lines = [
        "# Kartenverstaendnis H: Auswertung Welle 2 und gepooltes H (Vorlage, Refs #1404)",
        "",
        "Erzeugt von `scripts/analysis/rating_second_run_full_eval.py` (SHA-256 "
        f"`{result['herkunft']['skript_sha256']}`), Seed {result['herkunft']['seed']}, "
        f"{result['herkunft']['draws']} Ziehungen. Plan: `docs/analysis-reports/rating_full_second_run_plan_20261122.md`.",
        "",
        "## Kennzeichnung",
        "",
        *([f"- {x}" for x in result["kennzeichnung"]] or ["- keine"]),
        "",
        "## Gueltigkeit je Charge (section 3, A1, A2, A4, A5)",
        "",
        "| Charge | V1 gueltig | V2 | V3 | V4 | A1 < 90 % | A5 | A2 zaehlend | A4 | ausgeschlossen | Formatluecken H>25 (ueber/unter) |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for k, c in sorted(result["chargen"].items()):
        a4 = c.get("A4", {}).get("triggered") if isinstance(c.get("A4"), dict) else None
        fl = c["formatluecken_H_gt25_vom_mittel"]
        lines.append(
            f"| {k} | {c['V1_gueltig'][0]} von {c['V1_gueltig'][1]} | {c['V2_alle_7_werte'][0]} von {c['V2_alle_7_werte'][1]} "
            f"| {c['V3_vielfache_von_5'][0]} von {c['V3_vielfache_von_5'][1]} | {c['V4_zitate_woertlich'][0]} von {c['V4_zitate_woertlich'][1]} "
            f"| {fmt(c['A1_unter_90_prozent'])} | {c['A5_formatfehler'][0]} von {c['A5_formatfehler'][1]} "
            f"| {c['A2']['zaehlende_treffer']} | {fmt(a4)} | {fmt(c['ausgeschlossen']) if c['ausgeschlossen'] else 'nein'} "
            f"| {fl['H_ueber_mittel']} / {fl['H_unter_mittel']} von {fl['N_gueltig']} |"
        )
    g = result["gueltige_chargen"]
    p = result["paare"]
    lines += [
        "",
        f"Gueltige Chargen m = {g['m']} von 7 ({g['chargen']}). Karten mit zwei Bewertungen: {p['n']} von {p['N']} "
        f"(A1g bei < {p['schwelle']}: {fmt(p['A1g'])}).",
        "",
        "## Streuung aus den Paardifferenzen (section 5, d = H_R2 - H_F1)",
        "",
        "| Menge | n/N | b [95 %] | SD(d) | RMS | mittl. abs(d) | Anteil >= 15 | sigma1 = SD/sqrt2 [95 %] | RMS/sqrt2 | SE gepoolt = SD/2 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]

    def row(label: str, st: Mapping[str, Any]) -> str:
        ci = st.get("ci95", {})
        return (
            f"| {label} | {st.get('n', 0)}/{st.get('N', UNKNOWN)} | {fmt(st.get('b'))} {fmt_ci(ci.get('b'))} | {fmt(st.get('sd'))} "
            f"| {fmt(st.get('rms'))} | {fmt(st.get('mean_abs'))} | {fmt(st.get('n_ge15'))} von {st.get('n', 0)} "
            f"| {fmt(st.get('sigma1'))} {fmt_ci(ci.get('sigma1'))} | {fmt(st.get('sigma1_rms'))} | {fmt(st.get('se_pooled'))} |"
        )

    lines += [row("gesamt", s["gesamt"]), row("Welle 1", s["welle1"]), row("Welle 2", s["welle2"])]
    lines += [row(f"Schicht {k}", v) for k, v in sorted(s["schicht"].items())]
    lines += [row(f"Kartenart {k}", v) for k, v in sorted(s["kartenart"].items())]
    lines += [row(f"Charge {k}", v) for k, v in sorted(s["charge"].items())]
    lines += [row(f"Welle-1-Datei {k}", v) for k, v in sorted(s["datei_welle1"].items())]
    lines += [row(f"Band H_F1 {k}", v) for k, v in s["band_H_F1"].items()]
    lines += [
        "",
        f"sigma2_Charge (gueltige Chargen) = {fmt(s['sigma2_charge'])}; auffaellige Chargen (A6): {result['A6_auffaellige_chargen'] or 'keine'}.",
        "",
    ]
    sp = result["spells_test"]
    a9 = result["A9_welleneffekt"]
    lines += [
        "## Spells-Bias (section 6, Bestaetigungsmenge: Nicht-Anker-Spells der m gueltigen Chargen)",
        "",
        f"- b_W2 = {fmt(sp['b_W2'])} (n = {sp['n']}), Cluster-Intervall {fmt_ci(sp['ci95_cluster'])}, "
        f"Karten-Intervall (nur beschreibend) {fmt_ci(sp['ci95_card_descriptive'])}.",
        f"- Chargen mit b < 0: {sp['chunks_negative']} von {sp['m']} (noetig {sp['needed_negative']}); Schwelle {fmt(sp['threshold'], 1)}.",
        f"- Urteil: **{sp['verdict']}**; Sperren: {sp['blockers'] or 'keine'}.",
        f"- Anker-Spells Welle 2 (getrennt): b = {fmt(result['anker_spells_welle2'].get('b'))}, n = {result['anker_spells_welle2'].get('n', 0)}.",
        f"- Welleneffekt A9 (Rest-Spells ohne Anker): Welle 2 - Welle 1 = {fmt(a9.get('diff'))} {fmt_ci(a9.get('ci95'))}, "
        f"n = {a9.get('n_w1')} / {a9.get('n_w2')}: {fmt(a9.get('welleneffekt'))}.",
        f"- Laender: {result['laender']['urteil']}; b = {fmt(result['laender'].get('b'))}, n = {result['laender'].get('n', 0)} von {result['laender']['N']}.",
        "",
        "## K0 / K1 (nur Vorschlag, nichts angewendet)",
        "",
        f"- K0 Aenderungen gegen H_F1: {json.dumps(result['K0_aenderungen'], ensure_ascii=False, sort_keys=True)}",
        f"- K1: {json.dumps(result['K1'], ensure_ascii=False, sort_keys=True)}",
        f"- K1-Vorschlag erlaubt: {fmt(result['vorschlag']['K1_vorschlag_erlaubt'])} ({result['vorschlag']['K1_gruende_dagegen'] or 'keine Gruende dagegen'}); "
        f"Anzeige-Vorschlag erlaubt: {fmt(result['vorschlag']['anzeige_vorschlag_erlaubt'])}.",
        "",
        '## Was "besser" heisst (section 7)',
        "",
    ]
    b1 = result["B1"]["gesamt"]
    ci1 = b1.get("ci95", {})
    b2 = result["B2_G1"]
    lines += [
        f"- B1 (n = {b1['n']}): ICC(2,1) {fmt(b1.get('icc21'))} {fmt_ci(ci1.get('icc21'))}, Spearman-Brown {fmt(b1.get('spearman_brown'))}, "
        f"ICC(2,2) {fmt(b1.get('icc22'))}, ICC(3,1) {fmt(b1.get('icc31'))}, Spearman {fmt(b1.get('spearman'))}; {result['B1']['urteil']}.",
        f"- B2 G1 (n = {b2['n']}, davon {b2.get('n_mit_zwei_bewertungen', 0)} mit zwei Bewertungen): Delta_G1 K0 {fmt(b2.get('delta_K0'))} "
        f"{fmt_ci(b2.get('ci95_K0'))}; Urteil **{b2['urteil']}**.",
        f"- F2 beschreibend: Delta {fmt(result['F2_beschreibend'].get('delta_K0'))}, n = {result['F2_beschreibend']['n']}.",
        f"- B3 Retest: {json.dumps(result['B3_retest'], ensure_ascii=False, sort_keys=True)}",
        "",
        f"## Abweichungen >= 15 (markiert, nie geloescht): {len(result['abweichungen_ge15'])} Karten",
        "",
        "| Karte | Quelle R2 | H_F1 | H_R2 | ab 30 |",
        "|---|---|---|---|---|",
        *[
            f"| {x['card']} | {x['quelle_R2']} | {fmt(x['H_F1'], 1)} | {fmt(x['H_R2'], 1)} | {fmt(x['ge30'])} |"
            for x in result["abweichungen_ge15"]
        ],
        "",
        "Beide Begruendungen je Karte stehen im Ergebnis-JSON (`abweichungen_ge15`).",
        "",
        "## Lesart (Co-Lead, von Hand)",
        "",
        "<!-- Hier Lesart, Owner-Vorschlag (Anzeige H_pooled, K0/K1) und Grenzen eintragen. -->",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------- CLI


def _json_or_none(path: Path | None) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path else None


def _final_replies(path: Path | None) -> dict[str, str]:
    data = _json_or_none(path) or {}
    if not isinstance(data, Mapping):
        raise RefusedError("final replies must be a JSON object {chunk: text}")
    return {str(k): str(v) for k, v in data.items()}


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("hits", "eval"):
        p = sub.add_parser(name)
        p.add_argument("--manifest", type=Path, required=True)
        p.add_argument("--rater-dir", type=Path, required=True)
        p.add_argument("--checksums", type=Path, required=True)
        p.add_argument("--final-replies", type=Path)
        p.add_argument("--out", type=Path, required=True)
    pe = sub.choices["eval"]
    pe.add_argument("--classification", type=Path, required=True)
    pe.add_argument("--hits", type=Path, required=True)
    pe.add_argument("--run-log", type=Path)
    pe.add_argument("--wave1-dir", type=Path, required=True)
    pe.add_argument("--f1", type=Path, required=True)
    pe.add_argument("--g1", type=Path, required=True)
    pe.add_argument("--f2", type=Path, required=True)
    pe.add_argument("--tier-rule", type=Path)
    pe.add_argument("--report", type=Path, required=True)
    pe.add_argument("--pooled-out", type=Path, required=True)
    a = ap.parse_args(argv)
    try:
        replies = _final_replies(a.final_replies)
        if a.cmd == "hits":
            data, hits, _, _ = run_hits(a.manifest, a.rater_dir, a.checksums, replies)
            a.out.write_bytes(data)
            print(f"{len(hits)} Verweis-Treffer; SHA-256 der Treffer-Datei {sha256_bytes(data)}")
            return 0
        if not a.classification.exists():
            raise RefusedError(
                "classification file missing: classify the hits first (plan section 9, step 6)"
            )
        result, pooled = analyse(
            manifest_path=a.manifest, rater_dir=a.rater_dir, checksums_path=a.checksums,
            classification=_json_or_none(a.classification), hits_file_bytes=a.hits.read_bytes(),
            run_log=_json_or_none(a.run_log), final_replies=replies, wave1_dir=a.wave1_dir,
            f1_path=a.f1, g1_path=a.g1, f2_path=a.f2, tier_rule=_json_or_none(a.tier_rule),
        )  # fmt: skip
    except RefusedError as exc:
        print(f"VERWEIGERT: {exc}", file=sys.stderr)
        return 2
    a.out.write_text(dumps(result), encoding="utf-8")
    a.report.write_text(report(result), encoding="utf-8")
    a.pooled_out.write_text(
        "".join(json.dumps(clean(p), ensure_ascii=False, sort_keys=True) + "\n" for p in pooled),
        encoding="utf-8",
    )
    print(
        f"m = {result['gueltige_chargen']['m']}, Paare {result['paare']['n']}/{N_POOL}, Spells: {result['spells_test']['verdict']}, B2: {result['B2_G1']['urteil']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
