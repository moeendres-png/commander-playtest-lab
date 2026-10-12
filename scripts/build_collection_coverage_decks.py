#!/usr/bin/env python3
"""Build disjoint Commander coverage decks from the owner's card collection.

The decks exist to exercise as many distinct collection cards as possible in real
XMage full games. They are test inputs, not tuned decks and not own-deck snapshots.

Card facts come from the pinned XMage card repository, exported once with H2:

    java -cp h2-1.4.197.jar org.h2.tools.Shell -url jdbc:h2:file:<dir>/cards.h2 \
      -user "" -password "" -sql "CALL CSVWRITE('<out>.csv', 'SELECT NAME, MIN(TYPES) T, \
      MIN(SUBTYPES) ST, MIN(SUPERTYPES) SP, MIN(MANACOSTS) MC, MIN(MANAVALUE) MV, MIN(RULES) R, \
      MAX(SECONDSIDENAME) SSN FROM CARD WHERE NAME IS NOT NULL GROUP BY NAME')"

Color identity is derived from mana symbols in cost and rules text (both faces). The
XMage Commander validator remains the legality oracle: every deck must import through
the bridge, which fails closed on identity, singleton or banned-card errors.

Allocation: every non-basic card goes to at most one deck. Colored non-basic lands go
to the widest identities first, colorless lands round robin, then nonland cards are
picked round robin by a role-quota score (ramp, draw, removal, creatures).
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import re
from pathlib import Path

DECKS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("lyra", ("Lyra Dawnbringer",)),
    ("arcanis", ("Arcanis the Omnipotent",)),
    ("braids", ("Braids, Arisen Nightmare",)),
    ("lathliss", ("Lathliss, Dragon Queen",)),
    ("titania", ("Titania, Protector of Argoth",)),
    ("lavinia", ("Lavinia, Azorius Renegade",)),
    ("ayli", ("Ayli, Eternal Pilgrim",)),
    ("agrus", ("Agrus Kos, Wojek Veteran",)),
    ("selvala", ("Selvala, Explorer Returned",)),
    ("juri", ("Juri, Master of the Revue",)),
    ("gitrog", ("The Gitrog Monster",)),
    ("omnath", ("Omnath, Locus of Rage",)),
    ("veyran", ("Veyran, Voice of Duality",)),
    ("zegana", ("Prime Speaker Zegana",)),
    ("korvold", ("Korvold, Fae-Cursed King",)),
    ("chulane", ("Chulane, Teller of Tales",)),
    ("kykar", ("Kykar, Wind's Fury",)),
    ("ramos", ("Ramos, Dragon Engine",)),
)
# Cards the XMage Commander validator rejects as banned.
EXCLUDED = frozenset({"Crusade"})
BASIC = {"W": "Plains", "U": "Island", "B": "Swamp", "R": "Mountain", "G": "Forest"}
QUOTA = {"ramp": 10, "draw": 9, "removal": 9, "creature": 24}
NONLAND = 62


def color_identity(row: dict[str, str]) -> str:
    colors = set()
    for symbol in re.findall(r"\{([^}]+)\}", f"{row['MC'] or ''} {row['R'] or ''}"):
        colors.update(part for part in symbol.upper().split("/") if part in "WUBRG")
    return "".join(c for c in "WUBRG" if c in colors)


def load_cards(collection: Path, export: Path) -> dict[str, dict]:
    csv.field_size_limit(10**8)
    rows = {r["NAME"].lower(): r for r in csv.DictReader(export.open(encoding="utf-8"))}
    cards: dict[str, dict] = {}
    for name in (line.strip() for line in collection.read_text(encoding="utf-8").splitlines()):
        if not name or name == "oracle_name":
            continue
        row = rows.get(name.lower())
        if row is None and " // " in name:
            # XMage names double-faced and adventure cards by their front face.
            name = name.split(" // ")[0]
            row = rows.get(name.lower())
        if row is None:
            continue  # not implemented in the pinned XMage card repository
        ci = color_identity(row)
        back = rows.get((row["SSN"] or "").lower()) if row["SSN"] else None
        if back is not None:
            ci = "".join(c for c in "WUBRG" if c in ci + color_identity(back))
        cards[name] = {
            "ci": ci,
            "types": row["T"] or "",
            "sup": row["SP"] or "",
            "mv": int(row["MV"] or 0),
            "mc": row["MC"] or "",
            "rules": (row["R"] or "").lower(),
        }
    return cards


def roles(card: dict) -> set[str]:
    text = card["rules"]
    found = set()
    if "LAND" not in card["types"] and (
        re.search(r"add \{|add one mana|add two mana|add three mana|mana of any", text)
        or ("search your library for" in text and "land" in text)
    ):
        found.add("ramp")
    if "draw" in text:
        found.add("draw")
    if re.search(
        r"(destroy|exile) target|deals? \d+ damage to (any target|target creature)|counter target"
        r"|destroy all|exile all|return target (creature|nonland|permanent)",
        text,
    ):
        found.add("removal")
    if "CREATURE" in card["types"]:
        found.add("creature")
    return found


def build(cards: dict[str, dict]) -> list[dict]:
    is_land = lambda n: "LAND" in cards[n]["types"]  # noqa: E731
    commanders = {name for _, names in DECKS for name in names}
    ident = {slug: set("".join(cards[n]["ci"] for n in names)) for slug, names in DECKS}
    pool = sorted(
        n
        for n, v in cards.items()
        if n not in commanders and n not in EXCLUDED and "BASIC" not in v["sup"]
    )
    used: set[str] = set()
    widest_first = [slug for slug, _ in sorted(DECKS, key=lambda d: -len(ident[d[0]]))]

    lands: dict[str, list[str]] = {slug: [] for slug, _ in DECKS}
    for slug in widest_first:
        candidates = sorted(
            (
                n
                for n in pool
                if n not in used
                and is_land(n)
                and cards[n]["ci"]
                and set(cards[n]["ci"]) <= ident[slug]
            ),
            key=lambda n: (-len(cards[n]["ci"]), n),
        )
        take = candidates[: {1: 3, 2: 8}.get(len(ident[slug]), 14)]
        used.update(take)
        lands[slug] += take
    colorless = [n for n in pool if n not in used and is_land(n) and not cards[n]["ci"]]
    for index, name in enumerate(colorless[: len(widest_first) * 3]):
        lands[widest_first[index % len(widest_first)]].append(name)
        used.add(name)

    picked: dict[str, list[str]] = {slug: [] for slug, _ in DECKS}
    role_count = {slug: collections.Counter() for slug, _ in DECKS}
    big = collections.Counter()

    def score(slug: str, name: str) -> int:
        card = cards[name]
        card_roles = roles(card)
        value = sum(10 for r in card_roles if role_count[slug][r] < QUOTA[r])
        value += 6 * len(card["ci"])
        if "ramp" in card_roles and not card["ci"]:
            value += 3 * len(ident[slug])
        if card["mv"] >= 7:
            value -= 8 if big[slug] >= 3 else 2
        if card["mv"] <= 3:
            value += 2
        if not card_roles:
            value += 1
        return value

    active = [slug for slug, _ in DECKS]
    while active:
        for slug in list(active):
            if len(picked[slug]) >= NONLAND:
                active.remove(slug)
                continue
            options = [
                n
                for n in pool
                if n not in used and not is_land(n) and set(cards[n]["ci"]) <= ident[slug]
            ]
            if not options:
                active.remove(slug)
                continue
            best = min(options, key=lambda n: (-score(slug, n), n))
            used.add(best)
            picked[slug].append(best)
            role_count[slug].update(roles(cards[best]))
            if cards[best]["mv"] >= 7:
                big[slug] += 1

    decks = []
    for slug, names in DECKS:
        nonland = picked[slug]
        basics = 100 - len(names) - len(nonland) - len(lands[slug])
        pips = collections.Counter(
            ch for n in nonland for ch in re.findall(r"\{([WUBRG])\}", cards[n]["mc"])
        )
        colors = [c for c in "WUBRG" if c in ident[slug]]
        total = sum(pips[c] for c in colors) or 1
        alloc = {c: max(1, round(basics * pips[c] / total)) for c in colors}
        while sum(alloc.values()) > basics:
            alloc[max(alloc, key=alloc.get)] -= 1
        while sum(alloc.values()) < basics:
            alloc[max(colors, key=lambda c: pips[c])] += 1

        def entry(name: str, zone: str, quantity: int = 1) -> dict:
            return {
                "oracle_name": name,
                "quantity": quantity,
                "zone": zone,
                "physical_copy_ids": [],
                "notes": None,
            }

        entries = [entry(n, "commander") for n in names]
        entries += [entry(BASIC[c], "main", q) for c, q in alloc.items() if q > 0]
        entries += [entry(n, "main") for n in lands[slug] + nonland]
        decks.append(
            {
                "deck_id": f"collection/{slug}",
                "name": f"{names[0]} — Collection Coverage Build",
                "commander": {
                    "commanders": list(names),
                    "uses_partner": len(names) > 1,
                    "commander_identity_override": None,
                },
                "cards": entries,
            }
        )
    return decks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--collection", type=Path, default=Path("data/collections/owner_collection_2026-10-12.txt")
    )
    parser.add_argument("--card-export", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("data/coverage_decks/collection"))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for deck in build(load_cards(args.collection, args.card_export)):
        path = args.out / (deck["deck_id"].split("/")[1] + ".json")
        path.write_text(json.dumps(deck, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
