#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

CARDS = (
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
    "Boseiju Reaches Skyward",
)


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--xmage-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    root = Path(args.xmage_root).resolve()
    cards_root = root / "Mage.Sets" / "src" / "mage" / "cards"
    if not cards_root.is_dir():
        raise SystemExit(f"XMage card source root missing: {cards_root}")

    matches: dict[str, list[str]] = {card: [] for card in CARDS}
    for path in sorted(cards_root.rglob("*.java")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if "class " not in text or " extends " not in text:
            continue
        relative = path.relative_to(root).as_posix()
        for card in CARDS:
            if card in text:
                matches[card].append(relative)

    rows = [
        {
            "oracle_name": card,
            "implementation_present": bool(matches[card]),
            "matching_java_sources": matches[card],
            "evidence_class": "CODE_DERIVED",
        }
        for card in CARDS
    ]
    missing = [row["oracle_name"] for row in rows if not row["implementation_present"]]
    payload = {
        "schema_version": "ws18-xmage-29-card-crosswalk/1.0.0",
        "candidate": "XMage",
        "source_commit": git(root, "rev-parse", "HEAD"),
        "source_tree": git(root, "rev-parse", "HEAD^{tree}"),
        "denominator_count": len(CARDS),
        "implementation_present_count": len(CARDS) - len(missing),
        "static_crosswalk_verdict": "PASS" if not missing else "FAIL",
        "static_crosswalk_evidence_class": "CODE_DERIVED",
        "runtime_semantics_verdict": "NOT_RUN",
        "runtime_semantics_pass_count": 0,
        "runtime_semantics_required_count": len(CARDS),
        "missing_cards": missing,
        "rows": rows,
        "qualification_note": (
            "Implementation presence is CODE_DERIVED only. It does not prove import, castability, "
            "resolution, triggers, replacement effects, Commander semantics, or interaction behavior."
        ),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "static_crosswalk_verdict": payload["static_crosswalk_verdict"],
        "implementation_present_count": payload["implementation_present_count"],
        "runtime_semantics_verdict": payload["runtime_semantics_verdict"],
    }, sort_keys=True))
    if missing:
        raise SystemExit("Missing XMage implementations: " + ", ".join(missing))


if __name__ == "__main__":
    main()
