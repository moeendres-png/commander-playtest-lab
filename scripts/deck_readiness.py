#!/usr/bin/env python3
"""Check that every card of a deck is known to the simulator (#834).

A deck variant often adds cards outside the current card data; without this
check a variant comparison can silently measure "unknown card" instead of the
card. Prints the cards the simulator cannot play well yet and how to fix them:

    python scripts/deck_readiness.py --deck data/decks/rogshai_current.json
    python scripts/deck_readiness.py --deck a.json --deck b.json --json

Exit code 0 when every deck is ready, 1 when any deck is not ready.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from commander_lab.deck_readiness import (
    CardReadinessStatus,
    DeckReadiness,
    check_deck,
    format_deck_report,
)
from commander_lab.engine.rules.project import load_rules_deck_snapshot


def _json_report(path: Path, report: DeckReadiness) -> dict[str, object]:
    return {
        "path": str(path),
        "deck_id": report.deck_id,
        "ready": report.ready,
        "counts": {status.value: report.counts[status] for status in CardReadinessStatus},
        "cards": [{"name": card.name, "status": card.status.value} for card in report.cards],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--deck", type=Path, action="append", required=True)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    reports: list[tuple[Path, DeckReadiness]] = []
    for path in args.deck:
        try:
            deck = load_rules_deck_snapshot(path)
        except (OSError, ValueError) as exc:
            print(f"{path}: cannot load deck: {exc}", file=sys.stderr)
            return 2
        reports.append((path, check_deck(deck)))

    if args.json:
        payload = {
            "ready": all(report.ready for _, report in reports),
            "decks": [_json_report(path, report) for path, report in reports],
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("\n\n".join(format_deck_report(str(path), report) for path, report in reports))
    return 0 if all(report.ready for _, report in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
