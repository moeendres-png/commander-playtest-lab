"""Frage 5: die 30 größten |d| (R2 - F1) mit beiden Begründungen; Sortierung |d| absteigend, dann Name.

python3 a1_top30.py   (nach a1_decomp.py) -> $A1_OUT/top30.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a1_common as C

WORK = C.WORK
P = [json.loads(x) for x in (WORK / "pairs.jsonl").read_text().splitlines()]
P.sort(key=lambda p: (-abs(p["d_H"]), p["card"]))
top = P[:30]
cut = abs(top[-1]["d_H"])
tied = sum(1 for p in P if abs(p["d_H"]) == cut)
out = []
for p in top:
    m1 = np.mean([p[f"F1_{k}"] for k in "EFTRKD"])
    m2 = np.mean([p[f"R2_{k}"] for k in "EFTRKD"])
    out.append(
        {
            k: p[k]
            for k in (
                "card",
                "chunk",
                "seq",
                "F1_H",
                "R2_H",
                "d_H",
                "F1_reason",
                "R2_reason",
                "F1_noteH",
                "R2_noteH",
                "F1_conf",
                "R2_conf",
                "type_group",
            )
        }
        | {
            "F1_crit": {k: p[f"F1_{k}"] for k in "EFTRKD"},
            "R2_crit": {k: p[f"R2_{k}"] for k in "EFTRKD"},
            "F1_gap": round(p["F1_H"] - m1, 1),
            "R2_gap": round(p["R2_H"] - m2, 1),
        }
    )
(WORK / "top30.json").write_text(
    json.dumps(
        {"cut_abs_d": cut, "n_at_cut_total": tied, "rows": out}, indent=1, ensure_ascii=False
    )
    + "\n"
)
print(
    "cut",
    cut,
    "cards with |d| == cut:",
    tied,
    "; |d| >= cut:",
    sum(1 for p in P if abs(p["d_H"]) >= cut),
)
for i, r in enumerate(out, 1):
    print(
        f"\n#{i} {r['card']} [{r['chunk']} seq {r['seq']}, {r['type_group']}] F1 {r['F1_H']} R2 {r['R2_H']} d {r['d_H']} | F1 {r['F1_crit']} gap {r['F1_gap']} | R2 {r['R2_crit']} gap {r['R2_gap']}"
    )
    print("  F1:", r["F1_reason"], "| H:", r["F1_noteH"])
    print("  R2:", r["R2_reason"], "| H:", r["R2_noteH"])
