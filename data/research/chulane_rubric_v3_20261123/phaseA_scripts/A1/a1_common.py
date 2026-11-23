"""Gemeinsame Lader für die A1-Forensik (nur Standardbibliothek + numpy; deterministisch).

Pfade: REPO = Repo-Wurzel (Umgebungsvariable A1_REPO, Standard: die Wurzel des Checkouts, in dem
dieses Skript liegt). WORK = Ausgabeordner (A1_OUT, Standard ./work_a1 im aktuellen Verzeichnis;
bitte außerhalb des Repos wählen).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

REPO = Path(os.environ.get("A1_REPO", Path(__file__).resolve().parents[5]))
WORK = Path(os.environ.get("A1_OUT", "work_a1")).resolve()
RUB = REPO / "data/research/chulane_rubric_v2_20261118"
W1 = RUB / "second_run_20261122"
W2 = RUB / "second_run_full_20261122"
CRIT = ["E", "F", "T", "R", "K", "D"]
ALL = CRIT + ["H"]  # noqa: RUF005


def jl(p: Path) -> list[dict]:
    return [json.loads(x) for x in Path(p).read_text(encoding="utf-8").splitlines() if x.strip()]


def load_f1() -> dict[str, dict]:
    return {r["oracle_id"]: r for r in jl(RUB / "fullrun_ratings.jsonl")}


def load_r2() -> dict[str, dict]:
    """R2 = Welle 1 (rr_output_1..3) + Welle 2 (rr2_output_1..7); Retest-Charge 8 getrennt.

    Jede Zeile bekommt: wave, chunk, seq, n_chunk, card_block (Eingabe).
    """
    out: dict[str, dict] = {}
    for f in (1, 2, 3):
        inp = jl(W1 / f"rr_input_{f}.jsonl")
        o = jl(W1 / f"rr_output_{f}.jsonl")
        assert len(inp) == len(o)
        for i, r in zip(inp, o, strict=False):
            assert i["oracle_id"] == r["oracle_id"]
            r.update(
                wave=1, chunk=f"w1:{f}", seq=i["seq"], n_chunk=len(inp), card_block=i["card_block"]
            )
            out[r["oracle_id"]] = r
    for c in range(1, 8):
        inp = jl(W2 / "rater" / f"rr2_input_{c}.jsonl")
        o = jl(W2 / "rater" / f"rr2_output_{c}.jsonl")
        assert len(inp) == len(o)
        for i, r in zip(inp, o, strict=False):
            assert i["oracle_id"] == r["oracle_id"]
            r.update(
                wave=2, chunk=f"w2:{c}", seq=i["seq"], n_chunk=len(inp), card_block=i["card_block"]
            )
            assert r["oracle_id"] not in out
            out[r["oracle_id"]] = r
    return out


def load_retest() -> dict[str, dict]:
    inp = jl(W2 / "rater" / "rr2_input_8.jsonl")
    o = jl(W2 / "rater" / "rr2_output_8.jsonl")
    return {r["oracle_id"]: r for i, r in zip(inp, o, strict=False)}


def load_facts() -> dict[str, dict]:
    return {r["oracle_id"]: r for r in jl(RUB / "data/facts.jsonl")}


def load_pooled() -> dict[str, dict]:
    return {r["oracle_id"]: r for r in jl(W2 / "pooled.jsonl")}


def manifest_w2() -> dict:
    return json.loads((W2 / "rr2_manifest.json").read_text(encoding="utf-8"))


def manifest_w1() -> dict:
    return json.loads((W1 / "rr_sample_manifest.json").read_text(encoding="utf-8"))


def anchors() -> dict:
    return json.loads((RUB / "anchors.json").read_text(encoding="utf-8"))
