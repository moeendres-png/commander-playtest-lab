#!/usr/bin/env python3
"""Extra pilot checks: anchor errors, blindness keyword scan, literal quotes, pattern verdicts.

  python3 extra.py --batches <dir>     (<dir> = the --out of make_batches.py, run v2)

The quote check needs the rendered batch prompts (<dir>/batches/*.md, <dir>/batches_manifest.json).
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import statistics
from pathlib import Path

from pilot_ratings import ROOT, load_rows

RATERS = ("H1", "H2", "S1", "S2")
KEYWORDS = re.compile(
    r"popular|staple|edhrec|commonly played|price|budget|cedh|played in|decks? (run|play)|meta\b"
    r"|tier list",
    re.IGNORECASE,
)


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def fixed_anchor_values() -> dict[str, dict[str, float]]:
    anchors = json.loads((ROOT / "anchors.json").read_text(encoding="utf-8"))
    fixed: dict[str, dict[str, float]] = {}
    for part in ("spell", "land"):
        for crit, rows in anchors[part].items():
            for a in rows:
                if a["kind"] == "v1_fixed":
                    fixed.setdefault(a["card"], {})[crit] = a["value"]
    return fixed


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batches", required=True, help="output directory of make_batches.py")
    args = ap.parse_args()
    batch_root = Path(args.batches)

    pilot = json.loads((ROOT / "pilot_sample.json").read_text(encoding="utf-8"))
    anc = [c["name"] for c in pilot["cards"] if c["v1_is_anchor"]]
    fixed = fixed_anchor_values()
    rat: dict[str, dict[str, dict]] = {}
    for row in load_rows(version="v2"):
        if not row["retest"]:
            rat.setdefault(row["card"], {})[row["rater"]] = row

    print("== Anker H: fix vs Rater (H1,H2,S1,S2) ==")
    for c in anc:
        vals = [rat[c][r]["scores"]["H"] for r in RATERS]
        err = round(abs(statistics.fmean(vals) - fixed[c]["H"]), 1)
        print(f"{c:24s} fix {fixed[c].get('H')}  ", vals, "mean-err", err)
    mae = statistics.fmean(
        abs(statistics.fmean(rat[c][r]["scores"]["H"] for r in RATERS) - fixed[c]["H"]) for c in anc
    )
    print("Anker-MAE H (Mittel der 4 Rater):", round(mae, 1))
    mae_s = statistics.fmean(
        abs(statistics.fmean(rat[c][r]["scores"]["H"] for r in ("S1", "S2")) - fixed[c]["H"])
        for c in anc
    )
    print("Anker-MAE H (Mittel S-Stufe):", round(mae_s, 1))

    # blindness keyword scan
    hits = []
    total = 0
    for by_rater in rat.values():
        for rater, x in by_rater.items():
            total += 1
            claims = [
                c.get("claim", "") + c.get("interaction", "") for c in x.get("rule_claims", [])
            ]
            text = " ".join(
                [
                    x.get("reason", ""),
                    x.get("uncertainty", ""),
                    *x.get("notes", {}).values(),
                    *claims,
                ]
            )
            m = KEYWORDS.search(text)
            if m:
                hits.append(
                    (x["card"], rater, m.group(0), text[max(0, m.start() - 60) : m.end() + 60])
                )
    print(f"\n== Blindheits-Scan: {len(hits)} Treffer in {total} Bewertungen ==")
    for h in hits[:20]:
        print(h)

    # literal quote check against the rendered card blocks
    manifest = json.loads((batch_root / "batches_manifest.json").read_text(encoding="utf-8"))
    blocks: dict[tuple[str, str], str] = {}
    for m in manifest:
        text = (batch_root / "batches" / f"{m['batch']}.md").read_text(encoding="utf-8")
        parts = re.split(r"## Card \d+ of \d+\n\n", text)[1:]
        for name, part in zip(m["cards"], parts, strict=True):
            blocks[(m["rater"], name)] = part
    quotes = ok = 0
    bad = []
    for card, by_rater in rat.items():
        for rater, x in by_rater.items():
            block = norm(blocks[(rater, card)])
            for rc in x.get("rule_claims", []):
                quotes += 1
                q = norm(rc.get("quote", ""))
                if q and q in block:
                    ok += 1
                else:
                    bad.append((card, rater, rc.get("quote", "")[:90]))
    print(f"\n== rule_claims quote wörtlich im Kartenblock: {ok}/{quotes} ==")
    for b in bad[:8]:
        print(b)
    basis = collections.Counter(
        rc.get("basis") for r in rat.values() for x in r.values() for rc in x.get("rule_claims", [])
    )
    print("basis:", dict(basis))
    verdicts: collections.Counter[str] = collections.Counter()
    for by_rater in rat.values():
        for x in by_rater.values():
            for p in x.get("pattern_check", []):
                verdicts[p.get("verdict")] += 1
    print("pattern_check:", dict(verdicts))


if __name__ == "__main__":
    main()
