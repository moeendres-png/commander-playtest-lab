"""Check 173 precons, two precon opponents, Kaervek and Chulane (no collections).

python scripts/deckbau_pool_readiness.py --json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from commander_lab.deck_readiness import CardReadinessStatus, check_deck, format_deck_report
from commander_lab.engine.rules.project import load_rules_deck_snapshot

ROOT = Path(__file__).resolve().parents[1]
OTHER_DECKS = (
    Path("data/opponents/hosts_of_mordor_precon.json"),
    Path("data/opponents/lorehold_spirit_precon.json"),
    Path("data/decks/opponents/kaervek/current/deck.json"),
    Path("data/decks/deckbau/chulane_current.json"),
)
EXPECTED_PRECONS = 173
EXPECTED_TOTAL = 177


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    precons = sorted((ROOT / "data/decks/precons").glob("*.json"))
    if len(precons) != EXPECTED_PRECONS:
        parser.error(f"precon inventory changed: expected {EXPECTED_PRECONS}, found {len(precons)}")
    paths = (*precons, *(ROOT / name for name in OTHER_DECKS))
    if len(paths) != EXPECTED_TOTAL:
        parser.error(f"reference inventory changed: expected {EXPECTED_TOTAL}, found {len(paths)}")
    reports = []
    for path in paths:
        deck = load_rules_deck_snapshot(path)
        result = check_deck(deck)
        reports.append((path, result))
    ready = sum(report.ready for _, report in reports)
    payload = {
        "total": len(reports),
        "ready": ready,
        "not_ready": len(reports) - ready,
        "no_card_facts": sum(
            report.counts[CardReadinessStatus.NO_CARD_FACTS] for _, report in reports
        ),
        "failed_decks": [
            {"path": str(path.relative_to(ROOT)), "report": format_deck_report(str(path), report)}
            for path, report in reports
            if not report.ready
        ],
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"Reference deck readiness: {ready}/{len(reports)} READY; "
            f"{payload['no_card_facts']} NO_CARD_FACTS"
        )
        for entry in payload["failed_decks"]:
            print(entry["report"])
    return 0 if ready == EXPECTED_TOTAL and payload["no_card_facts"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
