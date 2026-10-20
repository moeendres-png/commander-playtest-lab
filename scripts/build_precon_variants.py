"""Build the precon variant decks: precons with engine-unknown cards swapped for real ones.

At the engine pin 13 precons contain card names the engine does not know, so they do not
import (docs/PRECON_VALIDATION.md). For the decks that only lack main-deck cards this script
writes a clearly named VARIANT copy in which each unknown card is replaced by a card the
engine does know. The originals in ``data/decks/precons/`` stay untouched.

The four decks whose commander is unknown (2024_death_toll, 2024_family_matters,
2024_miracle_worker, 2026_multiverse_reforged) get no variant: a different commander would
be a different deck.

A variant is a test deck, not the printed precon. It says nothing about how the original
plays, and it must not appear in qualification evidence or rankings.

    python scripts/build_precon_variants.py          # write data/decks/precon_variants/
    python scripts/build_precon_variants.py --check  # exit 1 when a file is out of date
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PRECON_DIR = ROOT / "data/decks/precons"
VARIANT_DIR = ROOT / "data/decks/precon_variants"

# deck stem -> {card unknown to the engine: replacement}. Every replacement was imported by
# the engine at the pin, is Commander-legal, inside the deck's colour identity and not yet in
# the deck (Muse M2, 2026-10-20, rechecked against Scryfall and the deck files).
SUBSTITUTIONS: dict[str, dict[str, str]] = {
    "2023_blast_from_the_past": {
        "Susan Foreman": "Sakura-Tribe Elder",
    },
    "2023_masters_of_evil": {
        "Missy": "Steel Hellkite",
        "Cyber Conversion": "Arcane Denial",
        "Doomsday Confluence": "Faithless Looting",
        "Death in Heaven": "Kang Dynasty",
        "Rassilon, the War President": "Mulldrifter",
        "The Cyber-Controller": "Burnished Hart",
        "Cybership": "N'Yami-Class Mother Ship",
        "Don't Blink": "Terminate",
    },
    "2023_paradox_power": {
        "The Foretold Soldier": "Solemn Simulacrum",
        "River Song's Diary": "Commander's Sphere",
        "Psychic Paper": "Swiftfoot Boots",
    },
    "2023_timey_wimey": {
        "The Pandorica": "Commander's Sphere",
        "The War Doctor": "Solemn Simulacrum",
        "The Moment": "Swiftfoot Boots",
        "Psychic Paper": "Hero's Blade",
    },
    "2024_blame_game": {
        "Feather, Radiant Arbiter": "Burnished Hart",
        "Immortal Obligation": "Abrade",
    },
    "2024_revenant_recon": {
        "Eye of Duskmantle": "Meteor Golem",
    },
    "2024_tricky_terrain": {
        "Desert Warfare": "Reconnaissance Mission",
    },
    "2024_tricky_terrain_collector_s_edition": {
        "Desert Warfare": "Reconnaissance Mission",
    },
    "2026_odds_and_ends": {
        "Exchange of Words": "Propaganda",
        "Space Beleren": "Tezzeret, Betrayer of Flesh",
    },
}


def build_variant(original: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    """The variant of one precon: same deck, the mapped cards replaced, named as a variant."""
    variant = json.loads(json.dumps(original))
    variant["deck_id"] = str(original["deck_id"]).replace("precon/", "precon-variant/", 1)
    variant["name"] = f"{original['name']} (variant, replacement cards)"
    replaced: set[str] = set()
    for entry in variant["cards"]:
        name = entry["oracle_name"]
        if name in mapping and entry["zone"] == "main":
            entry["oracle_name"] = mapping[name]
            entry["physical_copy_ids"] = []
            entry["notes"] = (
                f"VARIANT: replaces {name}, which the engine does not know at the pin. "
                "Not the printed card."
            )
            replaced.add(name)
    missing = set(mapping) - replaced
    if missing:
        raise ValueError(f"{original['deck_id']}: not a main-deck card: {sorted(missing)}")
    return variant


def render(deck: dict[str, Any]) -> str:
    return json.dumps(deck, indent=2, ensure_ascii=False) + "\n"


def expected_files() -> dict[str, str]:
    files: dict[str, str] = {}
    for stem, mapping in SUBSTITUTIONS.items():
        original = json.loads((PRECON_DIR / f"{stem}.json").read_text(encoding="utf-8"))
        files[f"{stem}.json"] = render(build_variant(original, mapping))
    return files


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail when a file is out of date")
    args = parser.parse_args(argv)
    files = expected_files()
    if args.check:
        present = {p.name for p in VARIANT_DIR.glob("*.json")}
        stale = sorted(
            name
            for name, text in files.items()
            if not (VARIANT_DIR / name).is_file()
            or (VARIANT_DIR / name).read_text(encoding="utf-8") != text
        )
        extra = sorted(present - set(files))
        for name in stale + extra:
            print(f"out of date: {name}", file=sys.stderr)
        return 1 if stale or extra else 0
    VARIANT_DIR.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (VARIANT_DIR / name).write_text(text, encoding="utf-8")
    print(f"wrote {len(files)} variant decks to {VARIANT_DIR.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
