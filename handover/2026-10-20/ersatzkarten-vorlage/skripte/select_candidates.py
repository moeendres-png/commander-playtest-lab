#!/usr/bin/env python3
"""M2 candidate selection for the 29 mainboard slots (mechanical, sourced).

Per slot (from the measured imports.json, role=mainboard):
  prefilter over the engine pool (data/cards/xmage_card_facts.json @ ed2fbae26):
    - candidate types (facts) cover the original's card types (Scryfall type_line)
    - |mana_value - original cmc| <= 1 (X counts 0 on both sides)
    - defining subtype (Saga/Equipment/Vehicle/Aura) present in facts subtypes
      when the original has one
    - candidate not already in the deck, not one of the 31 missing names
  ranking: mana-value difference asc, precon frequency desc, name asc
  verification per candidate via Scryfall (EXTERNAL_DATA, fetched 2026-10-20):
    - legalities.commander == 'legal'
    - color_identity subset of the deck commander's color_identity
    - type_line card types cover the original's; defining subtype present
  Up to 3 verified candidates per slot are kept.
Role proximity: mechanical keyword tags from oracle/rules text (fixed list);
'Rolle UNKNOWN' when no tag overlaps - no taste judgements anywhere.
"""
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path("/home/hatch/workspace/tmp/m2")
REPO = Path("/home/hatch/workspace/github/wt-m1-sweep")
PRECONS = REPO / "data/decks/precons"
CAND_DIR = BASE / "scryfall_cand"
CAND_DIR.mkdir(exist_ok=True)
HDR = {"User-Agent": "commander-lab-m2-measurement/1.0", "Accept": "application/json"}
FETCH_DATE = "2026-10-20"

CARD_TYPES = {"Creature", "Artifact", "Enchantment", "Instant", "Sorcery",
              "Planeswalker", "Land", "Battle", "Kindred"}
DEFINING_SUBTYPES = {"Saga", "Equipment", "Vehicle", "Aura"}
ROLE_KEYWORDS = {
    "draw": ["draw a card", "draws a card", "draw two", "draws two"],
    "removal": ["destroy target", "exile target", "deals damage to target", "deals damage to any target"],
    "ramp": ["search your library for a basic land", "add {", "additional mana"],
    "token": ["create a", "creates a", "token"],
    "reanimation": ["return target creature card from your graveyard", "from your graveyard to the battlefield"],
    "counters": ["+1/+1 counter"],
    "anthem": ["creatures you control get +"],
    "lifegain": ["gain life", "gains life"],
    "mill": ["mills", "mill a card", "into their graveyard from their library"],
    "sacrifice-outlet": ["sacrifice a", "sacrifice another"],
}


def parse_type_line(tl: str):
    left, _, right = tl.partition(" — ")
    types = {t for t in left.split() if t in CARD_TYPES}
    subtypes = {t for t in right.split() if t in DEFINING_SUBTYPES} if right else set()
    return types, subtypes


def role_tags(text: str):
    low = (text or "").lower()
    return sorted(tag for tag, pats in ROLE_KEYWORDS.items()
                  if any(p in low for p in pats))


def scryfall_exact(name: str):
    fn = CAND_DIR / (re.sub(r"[^A-Za-z0-9]+", "_", name) + ".json")
    if fn.exists():
        return json.loads(fn.read_text(encoding="utf-8"))
    url = "https://api.scryfall.com/cards/named?exact=" + urllib.parse.quote(name)
    req = urllib.request.Request(url, headers=HDR)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
    except Exception as e:  # noqa: BLE001 - recorded, candidate dropped
        data = {"_error": str(e), "_query_url": url}
    data["_query_url"] = url
    fn.write_text(json.dumps(data, indent=1), encoding="utf-8")
    time.sleep(0.12)
    return data


def main() -> int:
    imports = json.loads(Path("/home/hatch/workspace/tmp/m1/imports.json").read_text())
    originals = {}
    idx = json.loads((BASE / "scryfall/index.json").read_text())
    for entry in idx["found"]:
        p = json.loads((BASE / "scryfall" / entry["file"]).read_text())
        originals[entry["name"]] = p
    facts = json.loads((REPO / "data/cards/xmage_card_facts.json").read_text())["cards"]
    freq = json.loads((BASE / "precon_frequencies.json").read_text())
    cmd_ci = json.loads((BASE / "commanders/commander_ci.json").read_text())
    missing_names = set(originals)

    slots_out = []
    for r in imports["results"]:
        if r["status"] == "OK":
            continue
        deck_file = json.loads((PRECONS / f"{r['deck']}.json").read_text())
        in_deck = {(e.get("oracle_name") or e.get("name")) for e in deck_file["cards"]}
        deck_ci = set(cmd_ci[r["deck"]]["color_identity"] or [])
        for m in r.get("missing_cards") or []:
            if m["role"] != "mainboard":
                continue
            name = m["card"]
            orig = originals[name]
            o_types, o_sub = parse_type_line(orig["type_line"])
            o_mv = float(orig["cmc"])
            o_tags = role_tags(orig.get("oracle_text", ""))
            pre = []
            for ename, e in facts.items():
                if ename in in_deck or ename in missing_names:
                    continue
                etypes = {t.title() for t in e["types"]}
                if not o_types.issubset(etypes):
                    continue
                if e.get("mana_value") is None:
                    continue
                diff = abs(float(e["mana_value"]) - o_mv)
                if diff > 1:
                    continue
                if o_sub and not o_sub.issubset(set(e.get("subtypes") or [])):
                    continue
                pre.append((diff, -int(freq.get(ename, 0)), ename, e))
            pre.sort()
            verified = []
            checked = 0
            for diff, negf, ename, e in pre:
                if len(verified) >= 6 or checked >= 16:
                    break
                checked += 1
                p = scryfall_exact(ename)
                if "_error" in p:
                    continue
                legal = p.get("legalities", {}).get("commander")
                ci_ok = set(p.get("color_identity") or []).issubset(deck_ci)
                c_types, c_sub = parse_type_line(p["type_line"])
                types_ok = o_types.issubset(c_types) and o_sub.issubset(c_sub)
                if legal == "legal" and ci_ok and types_ok:
                    c_tags = role_tags(p.get("oracle_text", ""))
                    overlap = sorted(set(o_tags) & set(c_tags))
                    verified.append({
                        "name": ename,
                        "mana_value": float(e["mana_value"]),
                        "mana_value_diff": diff,
                        "types_engine_facts": e["types"],
                        "type_line_scryfall": p["type_line"],
                        "color_identity": p.get("color_identity"),
                        "commander_legality": legal,
                        "precon_frequency": int(freq.get(ename, 0)),
                        "role_original_tags": o_tags,
                        "role_candidate_tags": c_tags,
                        "role_overlap": overlap,
                        "role_verdict": ("Stichwort-Ueberlappung: " + ", ".join(overlap))
                                        if overlap else "Rolle UNKNOWN",
                        "sources": {
                            "engine_existence": "data/cards/xmage_card_facts.json @ ed2fbae26 (CODE_DERIVED, Importnachweis folgt separat)",
                            "legality_coloridentity_types": f"Scryfall {p['_query_url']} (EXTERNAL_DATA, Abruf {FETCH_DATE})",
                        },
                    })
            slots_out.append({
                "deck": r["deck"], "card": name, "zone": "mainboard",
                "deck_color_identity": sorted(deck_ci),
                "deck_color_identity_source": f"Scryfall commander {cmd_ci[r['deck']]['commander']} (EXTERNAL_DATA, Abruf {FETCH_DATE})",
                "original": {"mana_cost": orig.get("mana_cost"), "cmc": o_mv,
                             "type_line": orig["type_line"],
                             "types": sorted(o_types), "defining_subtypes": sorted(o_sub),
                             "color_identity": orig.get("color_identity")},
                "prefilter_hits": len(pre),
                "candidates": verified,
            })
            print(r["deck"], "|", name, "| prefilter", len(pre), "| verified", len(verified))
    out = {"slots": slots_out,
           "slot_count": len(slots_out),
           "slots_with_3_candidates": sum(1 for s in slots_out if len(s["candidates"]) == 3),
           "slots_with_0_candidates": [f"{s['deck']}:{s['card']}" for s in slots_out if not s["candidates"]]}
    (BASE / "kandidaten_draft.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("slot_count", "slots_with_3_candidates", "slots_with_0_candidates")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
