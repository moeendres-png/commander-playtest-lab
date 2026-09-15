"""WS219 bounded probe: Argentum frozen-29 cardDef census (read-only).

Scans /home/moeen/code/ws219-ref-argentum-3f46367d/mtg-sets for card("Name")
definitions and snapshot entries, plus Partner gate and OVERLOAD keyword.
No builds, no writes to reference root. Import/readback is not behavior.
"""
import pathlib
import re

REF = pathlib.Path("/home/moeen/code/ws219-ref-argentum-3f46367d")
SETS = REF / "mtg-sets"

FROZEN_29 = [
    "Ishai, Ojutai Dragonspeaker",
    "Rograkh, Son of Rohgahh",
    "Esior, Wardwing Familiar",
    "Kediss, Emberclaw Familiar",
    "Veyran, Voice of Duality",
    "Harmonic Prodigy",
    "Narset, Parter of Veils",
    "Jeska, Thrice Reborn",
    "Magma Opus",
    "Wash Away",
    "Wear // Tear",
    "Dig Through Time",
    "Flare of Duplication",
    "Vandalblast",
    "Finale of Revelation",
    "Psychosis Crawler",
    "Kaervek the Merciless",
    "Shriekmaw",
    "Butcher of Malakir",
    "Syphon Mind",
    "Gratuitous Violence",
    "Bolt Bend",
    "Makeshift Mannequin",
    "Warstorm Surge",
    "Basilisk Collar",
    "Burn Down the House",
    "Path of Ancestry",
    "Find // Finality",
    "Boseiju Reaches Skyward // Branch of Boseiju",
]

CARD_RE = re.compile(r'card\(\s*"([^"]+)"')


def collect_card_defs() -> dict:
    found: dict[str, list[str]] = {}
    for path in SETS.rglob("*.kt"):
        # Only scan main card definition sources; skip build outputs implicitly
        # by staying under mtg-sets source tree (tests included for coverage check).
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in CARD_RE.finditer(text):
            name = match.group(1).strip()
            found.setdefault(name.lower(), []).append(str(path.relative_to(REF)))
            if len(found[name.lower()]) > 3:
                continue
    return found


def main() -> None:
    assert REF.exists(), f"reference root missing: {REF}"
    defs = collect_card_defs()
    print(f"distinct_card_names={len(defs)}")
    # Partner gate + overload keyword (structural blockers)
    gi = REF / "rules-engine/src/main/kotlin/argentum/rules/core/GameInitializer.kt"
    kw = REF / "mtg-sdk/src/main/kotlin/argentum/sdk/core/Keyword.kt"
    print(f"game_initializer_exists={gi.exists()} keyword_file_exists={kw.exists()}")
    if gi.exists():
        text = gi.read_text(encoding="utf-8", errors="ignore")
        for needle in ["single commander", "partner", "Partner", "Phase 4", "Phase 1"]:
            hits = [line.strip()[:160] for line in text.splitlines() if needle.lower() in line.lower()]
            for hit in hits[:3]:
                print(f"GATE | {needle} | {hit}")
    if kw.exists():
        text = kw.read_text(encoding="utf-8", errors="ignore")
        print(f"keyword_overload_present={'OVERLOAD' in text} keyword_partner_present={'PARTNER' in text}")
    for name in FROZEN_29:
        key = name.lower()
        hits = defs.get(key, [])
        # Split-face fallback: match front face only
        if not hits and "//" in name:
            front = name.split("//")[0].strip().lower()
            hits = defs.get(front, [])
        # Kaervek disambiguation: Punisher is a different card
        print(f"CARD | {name} | defs={len(hits)} | {'; '.join(hits[:2]) if hits else 'MISSING'}")


if __name__ == "__main__":
    main()
