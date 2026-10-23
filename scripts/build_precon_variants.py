"""Build the SYNTHETIC proxy decks of the 9 precons the engine cannot import.

At the engine pin 13 precons contained card names the engine did not know, so they did not
import (docs/PRECON_VALIDATION.md). Owner decision 2026-10-23: each of them gets a proxy deck in
which every engine-unknown card is replaced by a real card the engine knows; four decks whose
commander was unknown also got a proxy commander. Since the pin 90f5c4d3f8 (repin v13, #979) the
engine knows the cards of four of them (2024_death_toll, 2024_family_matters,
2024_miracle_worker, 2026_multiverse_reforged); their proxies are retired and the real decks
count. The originals in ``data/decks/precons/`` stay untouched, so the pool stays at 195 decks:
186 real and 9 SYNTHETIC.

A proxy is evidence class SYNTHETIC. It is not the printed precon, says nothing about how the
original plays, and must not appear in qualification evidence or be ranked next to real decks
without the label. The marks (all generated here, ``--check`` verifies them): the ``SYNTHETIC``
deck tag, ``precon-synthetic/`` deck ids, a name suffix, a note on every replaced entry, and the
list ``data/decks/precon_synthetic_proxies.json``. The sweep and the import measurement read the
tag and report real and SYNTHETIC decks separately.

A later fork rebuild of the remaining missing cards (#979) replaces the other proxies; until
then the proxies carry the 9 decks.

    python scripts/build_precon_variants.py          # write the decks and the list
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
MANIFEST = ROOT / "data/decks/precon_synthetic_proxies.json"

SYNTHETIC_TAG = "SYNTHETIC"
PROXY_ID_PREFIX = "precon-synthetic/"
NAME_SUFFIX = "(SYNTHETIC proxy)"
# Muse M2 replacement-card template, set 1 of each deck (decision template of 2026-10-20).
TEMPLATE_SOURCE = {
    "repository": "moeendres-png/commander-playtest-lab",
    "branch": "muse/claude-handover",
    "commit": "5138666f6184ca6ea185509519639c273b1e370f",
    "folder": "handover/2026-10-20/ersatzkarten-vorlage/",
    "set": 1,
}

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

COMMANDER_PROXY_RULE = (
    "A legendary creature with exactly the original commander's colour identity, legal as a "
    "commander, known to the engine at the pin (import proof) and not already in the deck. "
    "Among those: cards that are no other precon's commander first, then the nearest mana "
    "value, then the nearest power plus toughness, then the name. The four decks whose commander "
    "the engine did not know have real decks again since repin v13, so no proxy commander is "
    "in use."
)

# deck stem -> proxy commander, for decks whose commander the engine does not know (rule above;
# a choice of this repository, not of the M2 template). Empty since repin v13: the four decks
# that needed one (2024_death_toll, 2024_family_matters, 2024_miracle_worker,
# 2026_multiverse_reforged) import with their real commanders. Changing an entry and rebuilding
# changes only that deck.
COMMANDER_PROXIES: dict[str, str] = {}


def build_variant(
    original: dict[str, Any], mapping: dict[str, str], commander: str | None = None
) -> dict[str, Any]:
    """The SYNTHETIC proxy of one precon: same deck, replacements marked, named as a proxy."""
    variant = json.loads(json.dumps(original))
    variant["deck_id"] = str(original["deck_id"]).replace("precon/", PROXY_ID_PREFIX, 1)
    variant["name"] = f"{original['name']} {NAME_SUFFIX}"
    variant["tags"] = sorted({*variant.get("tags", []), SYNTHETIC_TAG, "precon-proxy"})
    variant["notes"] = (
        f"SYNTHETIC proxy of {original['deck_id']}: cards the engine does not know at the pin are "
        "replaced by real engine cards. Not the printed precon: no rules evidence, no "
        "qualification evidence, never ranked next to real decks without the label "
        "(data/decks/precon_synthetic_proxies.json)."
    )
    replaced: set[str] = set()
    for entry in variant["cards"]:
        name = entry["oracle_name"]
        if name in mapping and entry["zone"] == "main":
            entry["oracle_name"] = mapping[name]
            entry["physical_copy_ids"] = []
            entry["notes"] = (
                f"SYNTHETIC: replaces {name}, which the engine does not know at the pin. "
                "Not the printed card."
            )
            replaced.add(name)
    missing = set(mapping) - replaced
    if missing:
        raise ValueError(f"{original['deck_id']}: not a main-deck card: {sorted(missing)}")
    if commander is not None:
        (old,) = original["commander"]["commanders"]
        if commander in {e["oracle_name"] for e in original["cards"]}:
            raise ValueError(f"{original['deck_id']}: {commander} is already in the deck")
        variant["commander"]["commanders"] = [commander]
        for entry in variant["cards"]:
            if entry["zone"] == "commander":
                entry["oracle_name"] = commander
                entry["physical_copy_ids"] = []
                entry["notes"] = (
                    f"SYNTHETIC: stands in for the commander {old}, which the engine does not "
                    "know at the pin. Not the printed commander."
                )
    return variant


def render(deck: dict[str, Any]) -> str:
    return json.dumps(deck, indent=2, ensure_ascii=False) + "\n"


def manifest(originals: dict[str, dict[str, Any]], pool_total: int) -> dict[str, Any]:
    """The list of proxies: what stands in for what, and the real/SYNTHETIC split of the pool."""
    decks: dict[str, Any] = {}
    for stem, mapping in SUBSTITUTIONS.items():
        original = originals[stem]
        entry: dict[str, Any] = {
            "original_deck_id": original["deck_id"],
            "proxy_deck_id": str(original["deck_id"]).replace("precon/", PROXY_ID_PREFIX, 1),
            "proxy_file": f"data/decks/precon_variants/{stem}.json",
            "main_deck_replacements": [
                {"original": old, "proxy": new} for old, new in mapping.items()
            ],
            "commander_replacement": None,
        }
        if stem in COMMANDER_PROXIES:
            (old,) = original["commander"]["commanders"]
            entry["commander_replacement"] = {"original": old, "proxy": COMMANDER_PROXIES[stem]}
        decks[stem] = entry
    return {
        "schema": "commander-lab.synthetic-precon-proxies/1",
        "evidence_class": SYNTHETIC_TAG,
        "statement": (
            "Each proxy deck replaces cards the engine does not know at the pin by real engine "
            "cards. It is a test deck, not the printed precon; it is not rules evidence and not "
            "qualification evidence, and results on it are reported apart from the real decks."
        ),
        "decision": (
            "Owner, 2026-10-23: proxies now (#920), real rebuild of the cards in the fork "
            "later (#979)"
        ),
        "replacement_source": TEMPLATE_SOURCE,
        "commander_rule": COMMANDER_PROXY_RULE,
        "pool": {
            "decks": pool_total,
            "real": pool_total - len(decks),
            "synthetic": len(decks),
        },
        "decks": decks,
    }


def expected_files() -> dict[str, str]:
    files: dict[str, str] = {}
    originals: dict[str, dict[str, Any]] = {}
    for stem, mapping in SUBSTITUTIONS.items():
        original = json.loads((PRECON_DIR / f"{stem}.json").read_text(encoding="utf-8"))
        originals[stem] = original
        files[f"{stem}.json"] = render(
            build_variant(original, mapping, COMMANDER_PROXIES.get(stem))
        )
    pool_total = sum(1 for _ in PRECON_DIR.glob("*.json"))
    files[str(MANIFEST.relative_to(ROOT))] = render(manifest(originals, pool_total))
    return files


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail when a file is out of date")
    args = parser.parse_args(argv)
    files = expected_files()
    paths = {
        name: (ROOT / name if name.startswith("data/") else VARIANT_DIR / name) for name in files
    }
    if args.check:
        present = {p.name for p in VARIANT_DIR.glob("*.json")}
        stale = sorted(
            name
            for name, text in files.items()
            if not paths[name].is_file() or paths[name].read_text(encoding="utf-8") != text
        )
        extra = sorted(present - {Path(name).name for name in files})
        for name in stale + extra:
            print(f"out of date: {name}", file=sys.stderr)
        return 1 if stale or extra else 0
    VARIANT_DIR.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        paths[name].write_text(text, encoding="utf-8")
    print(f"wrote {len(files) - 1} proxy decks and the proxy list")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
