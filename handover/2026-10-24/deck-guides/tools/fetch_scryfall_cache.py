#!/usr/bin/env python3
"""Fetch Scryfall oracle data for every card used by the deck-guide corpus.

Cache layers:
  1. The repo's own pilot_card_knowledge.json (Scryfall-sourced, 2026-10-15).
  2. Scryfall collection API (POST /cards/collection, batches of 75 names),
     via curl (urllib gets HTTP 400 in this environment), 0.15s spacing.

Output: stageDeckGuides/scryfall_cache.json with the same field shape as
pilot_card_knowledge.json entries, plus "_source" per card.
Cards Scryfall does not know land in "_not_found" (evidence UNKNOWN downstream).
"""
import glob
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DECK_GLOBS = [
    "/home/hatch/workspace/github/commander-playtest-lab/data/decks/precons/*.json",
    "/home/hatch/workspace/github/wt-978/data/decks/precon_variants/*.json",
    "/home/hatch/workspace/tmp/m4/rogshai.json",
    "/home/hatch/workspace/tmp/m4/chulane.json",
]
REPO_KNOWLEDGE = "/home/hatch/workspace/github/wt-m4/data/cards/pilot_card_knowledge.json"
OUT = ROOT / "scryfall_cache.json"


def deck_names() -> set[str]:
    names: set[str] = set()
    for pattern in DECK_GLOBS:
        for path in glob.glob(pattern):
            deck = json.loads(Path(path).read_text(encoding="utf-8"))
            for card in deck["cards"]:
                names.add(card["oracle_name"])
    return names


def flatten(card: dict) -> dict:
    faces = card.get("card_faces")
    if faces and card.get("layout") not in ("art_series",):
        oracle = "\n//\n".join(f.get("oracle_text", "") for f in faces if f.get("oracle_text"))
        type_line = " // ".join(f.get("type_line", "") for f in faces)
        power = faces[0].get("power")
        toughness = faces[0].get("toughness")
        mana_cost = " // ".join(f.get("mana_cost", "") for f in faces if f.get("mana_cost"))
    else:
        oracle = card.get("oracle_text", "")
        type_line = card.get("type_line", "")
        power = card.get("power")
        toughness = card.get("toughness")
        mana_cost = card.get("mana_cost", "")
    def num(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None
    return {
        "name": card["name"],
        "mana_cost": mana_cost,
        "mana_value": float(card.get("cmc") or 0.0),
        "colors": card.get("colors") or [],
        "color_identity": card.get("color_identity") or [],
        "keywords": card.get("keywords") or [],
        "type_line": type_line,
        "oracle_text": oracle,
        "power": num(power),
        "toughness": num(toughness),
        "produced_mana": card.get("produced_mana") or [],
        "layout": card.get("layout", "normal"),
        "loyalty": card.get("loyalty"),
    }


def main() -> int:
    wanted = deck_names()
    cache: dict[str, dict] = {}
    repo = json.loads(Path(REPO_KNOWLEDGE).read_text(encoding="utf-8"))["cards"]
    for name, entry in repo.items():
        if name in wanted:
            e = dict(entry)
            e["_source"] = "repo:pilot_card_knowledge.json"
            cache[name] = e
    missing = sorted(wanted - set(cache))
    print(f"unique deck cards: {len(wanted)}; repo cache hits: {len(cache)}; to fetch: {len(missing)}")
    not_found: list[str] = []
    batches = [missing[i:i + 75] for i in range(0, len(missing), 75)]
    for idx, batch in enumerate(batches):
        payload = json.dumps({"identifiers": [{"name": n} for n in batch]})
        proc = subprocess.run(
            ["curl", "-s", "-X", "POST", "https://api.scryfall.com/cards/collection",
             "-H", "Content-Type: application/json", "-H", "Accept: application/json",
             "-H", "User-Agent: commander-lab-deck-guides/1.0", "-d", payload],
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode != 0 or not proc.stdout.strip().startswith("{"):
            print(f"batch {idx}: curl failed rc={proc.returncode}", file=sys.stderr)
            return 1
        resp = json.loads(proc.stdout)
        got = {c["name"]: flatten(c) for c in resp.get("data", [])}
        for name in batch:
            if name in got:
                e = got[name]; e["_source"] = "scryfall:collection"
                cache[name] = e
            else:
                # retry via front face for split/DFC naming drift
                front = name.split(" // ")[0]
                hit = next((v for k, v in got.items() if k.split(" // ")[0] == front), None)
                if hit:
                    e = dict(hit); e["_source"] = "scryfall:collection(front-face match)"
                    cache[name] = e
                else:
                    not_found.append(name)
        print(f"batch {idx + 1}/{len(batches)} done; cache={len(cache)} not_found={len(not_found)}")
        time.sleep(0.15)
    out = {"schema": "deck-guides-scryfall-cache/1", "cards": cache, "_not_found": sorted(set(not_found))}
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT}: {len(cache)} cards, not_found={len(set(not_found))}: {sorted(set(not_found))[:20]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
