#!/usr/bin/env python3
"""Cross-check the global_inclusion component against the MTGJSON EDHREC rank (#1367).

MTGJSON is a data quality check only: nothing here feeds the strength index, and no module
under src/commander_lab/studio reads MTGJSON (a unit test guards that).

Usage (from a worktree, PYTHONPATH=src):

    python scripts/mtgjson_global_inclusion_check.py STORE_DIR AtomicCards.json.gz OUT.json \
        [--commander NAME] [--threshold 0.25]

The Studio store is only read. The MTGJSON file is parsed with ``json`` and treated as untrusted
data. OUT.json holds aggregate numbers and pool card names only (no collection quantities).
Percentiles are mean-rank percentiles (rank / (n - 1)) inside the matched cards of the same
group (spells, lands, all); ``edhrecRank`` is negated so that a high percentile means popular.
``edhrecSaltiness`` is copied for display and is never used as a signal.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

DEFAULT_COMMANDER = "Chulane, Teller of Tales"
DEFAULT_THRESHOLD = 0.25
LAND_GROUP = "Länder"  # strength.GROUP_LANDS (spells are "Zauber")


def average_ranks(values: Sequence[float]) -> list[float]:
    """1-based ranks, ties share the mean rank."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        mean = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = mean
        i = j + 1
    return ranks


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Spearman rank correlation (Pearson on mean ranks); None below 3 pairs or no spread."""
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    rx, ry = average_ranks(xs), average_ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    sxx = sum((a - mx) ** 2 for a in rx)
    syy = sum((b - my) ** 2 for b in ry)
    if sxx == 0 or syy == 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def percentiles(values: Sequence[float]) -> list[float]:
    ranks = average_ranks(values)
    n = len(values)
    return [0.5 if n == 1 else (r - 1) / (n - 1) for r in ranks]


def mtgjson_index(atomic: Mapping[str, object]) -> dict[str, tuple[int, float | None]]:
    """Name (full name and every face name) -> (edhrecRank, edhrecSaltiness)."""
    data = atomic.get("data")
    if not isinstance(data, dict):
        raise ValueError("AtomicCards: no data object")
    index: dict[str, tuple[int, float | None]] = {}
    for key, faces in data.items():
        if not isinstance(faces, list):
            continue
        ranks = [f["edhrecRank"] for f in faces if isinstance(f, dict) and f.get("edhrecRank")]
        if not ranks:
            continue
        salts = [f.get("edhrecSaltiness") for f in faces if isinstance(f, dict)]
        salt = next((s for s in salts if isinstance(s, int | float)), None)
        entry = (int(min(ranks)), float(salt) if salt is not None else None)
        index.setdefault(key.casefold(), entry)
        for face in faces:
            name = face.get("faceName") if isinstance(face, dict) else None
            if isinstance(name, str):
                index.setdefault(name.casefold(), entry)
    return index


def pool_rows(store_dir: Path, commander: str) -> list[dict[str, object]]:
    """Ranked cards with the global_inclusion share, its counts and group (read-only)."""
    from commander_lab.studio import StudioStore, strength, strength_view

    store = StudioStore.open(store_dir)
    result = strength_view.compute(store, commander, strength.PRESETS["Ausgewogen"])
    rows: list[dict[str, object]] = []
    for card in result["cards"]:
        if card["tier"] in ("N", "U"):
            continue
        for comp in card["components"]:
            if comp["component"] == strength.GLOBAL_INCLUSION and comp["value"] is not None:
                rows.append(
                    {
                        "name": card["name"],
                        "share": comp["value"],
                        "numerator": comp["numerator"],
                        "denominator": comp["denominator"],
                        "group": comp["group"],
                    }
                )
    return rows


def analyse(
    rows: Sequence[Mapping[str, object]],
    index: Mapping[str, tuple[int, float | None]],
    threshold: float,
) -> dict[str, object]:
    matched: list[dict[str, object]] = []
    unmatched: list[str] = []
    for row in rows:
        name = str(row["name"])
        hit = index.get(name.casefold()) or index.get(name.split(" // ")[0].casefold())
        if hit is None:
            unmatched.append(name)
            continue
        matched.append({**row, "rank": hit[0], "saltiness": hit[1]})

    def subset(group: str) -> list[dict[str, object]]:
        if group == "all":
            return matched
        want_land = group == "lands"
        return [m for m in matched if (m["group"] == LAND_GROUP) == want_land]

    stats: dict[str, object] = {}
    deviations: list[dict[str, object]] = []
    for group in ("all", "spells", "lands"):
        sub = subset(group)
        pop = [-float(m["rank"]) for m in sub]  # type: ignore[arg-type]
        share = [float(m["share"]) for m in sub]  # type: ignore[arg-type]
        stats[group] = {"n": len(sub), "spearman": spearman(pop, share)}
        if len(sub) < 3:
            continue
        pp, sp = percentiles(pop), percentiles(share)
        if group == "all":
            continue  # the table uses the within-group percentiles (lands scale separately)
        for m, a, b in zip(sub, pp, sp, strict=True):
            if abs(a - b) > threshold:
                deviations.append(
                    {
                        "name": m["name"],
                        "group": group,
                        "edhrec_rank": m["rank"],
                        "saltiness": m["saltiness"],
                        "mtgjson_percentile": round(a, 3),
                        "share_percentile": round(b, 3),
                        "delta": round(b - a, 3),
                        "numerator": m["numerator"],
                        "denominator": m["denominator"],
                    }
                )
    deviations.sort(key=lambda d: -abs(float(d["delta"])))  # type: ignore[arg-type]
    return {
        "ranked_cards": len(rows),
        "matched": len(matched),
        "unmatched": sorted(unmatched),
        "threshold": threshold,
        "stats": stats,
        "deviations": deviations,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("store", type=Path)
    parser.add_argument("atomic_cards", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--commander", default=DEFAULT_COMMANDER)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    args = parser.parse_args(argv)
    with gzip.open(args.atomic_cards, "rt", encoding="utf-8") as handle:
        atomic = json.load(handle)
    report = analyse(pool_rows(args.store, args.commander), mtgjson_index(atomic), args.threshold)
    args.out.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    stats = report["stats"]
    print(f"matched {report['matched']}/{report['ranked_cards']}; {stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
