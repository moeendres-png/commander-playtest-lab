#!/usr/bin/env python3
"""Build the M2 proof copies: per deck and set (Satz 1..3), every missing
mainboard card is replaced by one verified candidate.

Assignment is greedy and unique within a set (singleton): slots are served in
measurement order; a slot takes its candidate of rank k (1-based) if that name
is still unused in the set, otherwise the next-ranked unused candidate.
2026_multiverse_reforged additionally misses its commander; for the import
proof ONLY, the commander is replaced by a scaffold commander (an engine-known
commander from an importable precon whose color identity covers WUBR). The
scaffold is a proof device, NOT a candidate proposal (scope point 4: commander
decks get no slot exchange). It is recorded in the manifest.

Usage: build_proof_copies.py <scaffold-commander-name>
Writes copies/<deck>_satz<k>/<deck>.json and copies/manifest.json.
"""
import json
import sys
from pathlib import Path

BASE = Path("/home/hatch/workspace/tmp/m2")
PRECONS = Path("/home/hatch/workspace/github/wt-m1-sweep/data/decks/precons")
COPIES = BASE / "copies"


def main() -> int:
    scaffold = sys.argv[1]
    draft = json.loads((BASE / "kandidaten_draft.json").read_text())
    by_deck: dict[str, list[dict]] = {}
    for s in draft["slots"]:
        by_deck.setdefault(s["deck"], []).append(s)
    manifest = {"scaffold_commander": scaffold,
                "scaffold_note": "Nur Import-Geruest fuer 2026_multiverse_reforged, kein Vorschlag.",
                "sets": []}
    for deck, slots in sorted(by_deck.items()):
        original = json.loads((PRECONS / f"{deck}.json").read_text())
        for k in (1, 2, 3):
            used: set[str] = set()
            assignment = {}
            for s in slots:
                cands = [c["name"] for c in s["candidates"]]
                pick = None
                order = list(range(k - 1, len(cands))) + list(range(0, k - 1))
                for idx in order:
                    if cands[idx] not in used:
                        pick = cands[idx]
                        break
                if pick is None:
                    raise SystemExit(f"no unique candidate left: {deck} satz{k} slot {s['card']}")
                used.add(pick)
                assignment[s["card"]] = pick
            copy = json.loads(json.dumps(original))
            for entry in copy["cards"]:
                nm = entry.get("oracle_name") or entry.get("name")
                if nm in assignment and (entry.get("zone") in ("main", "mainboard")):
                    entry["oracle_name"] = assignment[nm]
                    entry["physical_copy_ids"] = []
            if deck == "2026_multiverse_reforged":
                for entry in copy["cards"]:
                    if entry.get("zone") == "commander":
                        entry["oracle_name"] = scaffold
                        entry["physical_copy_ids"] = []
                copy["commander"]["commanders"] = [scaffold]
            outdir = COPIES / f"{deck}_satz{k}"
            outdir.mkdir(parents=True, exist_ok=True)
            (outdir / f"{deck}.json").write_text(
                json.dumps(copy, indent=1, ensure_ascii=False), encoding="utf-8")
            manifest["sets"].append({"deck": deck, "satz": k,
                                     "dir": str(outdir), "assignment": assignment})
            print(deck, "satz", k, assignment)
    (COPIES / "manifest.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    print("sets built:", len(manifest["sets"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
