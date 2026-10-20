#!/usr/bin/env python3
"""Build the M2 slot table: every missing-card entry of the 13 affected decks.

Reference list of missing names per deck: docs/PRECON_VALIDATION.md (Pin 043579bb),
cross-checked later against the measured imports.json (calibration run).
Zone and quantity come from the deck files themselves (cards[].zone / .quantity);
a name that only appears in commander.commanders counts as zone=commander, qty=1.
Share = quantity / 100 (deck size), as defined by the assignment.
Also emits the precon frequency table (in how many of the 195 precons a card appears),
used later to rank replacement candidates.
"""
import json
from collections import Counter
from pathlib import Path

REPO = Path("/home/hatch/workspace/github/wt-m1-sweep")
PRECONS = REPO / "data/decks/precons"

MISSING = {
    "2023_blast_from_the_past": ["Susan Foreman"],
    "2023_masters_of_evil": ["Missy", "Cyber Conversion", "Doomsday Confluence",
                             "Death in Heaven", "Rassilon, the War President",
                             "The Cyber-Controller", "Cybership", "Don't Blink"],
    "2023_paradox_power": ["The Foretold Soldier", "River Song's Diary", "Psychic Paper"],
    "2023_timey_wimey": ["The Pandorica", "The War Doctor", "The Moment", "Psychic Paper"],
    "2024_blame_game": ["Feather, Radiant Arbiter", "Immortal Obligation"],
    "2024_death_toll": ["Winter, Cynical Opportunist"],
    "2024_family_matters": ["Zinnia, Valley's Voice"],
    "2024_miracle_worker": ["Aminatou, Veil Piercer"],
    "2024_revenant_recon": ["Eye of Duskmantle"],
    "2024_tricky_terrain": ["Desert Warfare"],
    "2024_tricky_terrain_collector_s_edition": ["Desert Warfare"],
    "2026_multiverse_reforged": ["Dack Fayden, Helping Hand", "Teferi's Reproach",
                                 "Jhoira, Weatherlight Corsair", "Venser, Fervent Forger",
                                 "Tamiyo, Upriser Crowned", "The Ur-Sphinx",
                                 "Jace, Multiverse Architect"],
    "2026_odds_and_ends": ["Exchange of Words", "Space Beleren"],
}


def main() -> int:
    slots = []
    for stem, names in MISSING.items():
        deck = json.loads((PRECONS / f"{stem}.json").read_text(encoding="utf-8"))
        entries = deck.get("cards", [])
        commanders = deck.get("commander", {}).get("commanders", [])
        deck_total = sum(int(e.get("quantity", 1)) for e in entries)
        for name in names:
            hits = [e for e in entries if (e.get("oracle_name") or e.get("name")) == name]
            if hits:
                for e in hits:
                    qty = int(e.get("quantity", 1))
                    slots.append({
                        "deck": stem,
                        "card": name,
                        "zone": e.get("zone") or ("commander" if name in commanders else "mainboard"),
                        "quantity": qty,
                        "deck_cards_total": deck_total,
                        "share_of_deck": round(qty / 100, 4),
                        "found_in": "cards[]",
                    })
            elif name in commanders:
                slots.append({
                    "deck": stem, "card": name, "zone": "commander", "quantity": 1,
                    "deck_cards_total": deck_total, "share_of_deck": 0.01,
                    "found_in": "commander.commanders",
                })
            else:
                slots.append({
                    "deck": stem, "card": name, "zone": "UNKNOWN", "quantity": 0,
                    "deck_cards_total": deck_total, "share_of_deck": 0.0,
                    "found_in": "NOT_FOUND_IN_DECK_FILE",
                })
    freq: Counter[str] = Counter()
    for path in sorted(PRECONS.glob("*.json")):
        deck = json.loads(path.read_text(encoding="utf-8"))
        names_in_deck = {(e.get("oracle_name") or e.get("name")) for e in deck.get("cards", [])}
        for n in names_in_deck:
            if n:
                freq[n] += 1
    out = {
        "reference": "docs/PRECON_VALIDATION.md @ ed2fbae26 (Pin 043579bb); Kalibrierungs-Abgleich ausstehend",
        "slots": slots,
        "slot_count": len(slots),
        "distinct_cards": len({s["card"] for s in slots}),
        "decks": len(MISSING),
    }
    Path("/home/hatch/workspace/tmp/m2/slots_draft.json").write_text(
        json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    Path("/home/hatch/workspace/tmp/m2/precon_frequencies.json").write_text(
        json.dumps(dict(freq.most_common()), indent=0, ensure_ascii=False), encoding="utf-8")
    print(f"slots: {len(slots)} | distinct: {out['distinct_cards']} | decks: {len(MISSING)}")
    for s in slots:
        if s["found_in"].startswith("NOT") or s["zone"] == "UNKNOWN":
            print("PROBLEM:", s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
