#!/usr/bin/env python3
"""Count card co-occurrences in the canonical corpus mainboards.

Reads corpus_deck_card from the StudioStore SQLite database, counts all unordered pairs
(oracle_id_a < oracle_id_b) occurring within mainboards (excluding commander zone),
and reports pairs with frequency >= min_decks (default: 5).

Usage:
    python3 scripts/count_corpus_cooccurrence.py [--data PATH] [--min-decks 5] [--top 50] [--output PATH]
"""

from __future__ import annotations

import argparse
import itertools
import json
import sqlite3
import sys
from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class CooccurrencePair:
    oracle_id_a: str
    oracle_id_b: str
    card_name_a: str
    card_name_b: str
    deck_count: int
    share: float


def load_card_names(db: sqlite3.Connection) -> dict[str, str]:
    """Build a mapping of oracle_id -> card_name from scryfall_card and card tables."""
    names: dict[str, str] = {}
    # 1. From scryfall_card (primary source for canonical oracle names)
    try:
        for row in db.execute("SELECT oracle_id, name FROM scryfall_card").fetchall():
            if row[0]:
                names[str(row[0])] = str(row[1])
    except sqlite3.OperationalError:
        pass

    # 2. Fallback / supplement from card table
    try:
        for row in db.execute("SELECT oracle_id, oracle_name FROM card").fetchall():
            if row[0] and str(row[0]) not in names:
                names[str(row[0])] = str(row[1])
    except sqlite3.OperationalError:
        pass

    return names


def load_deck_cards(
    db: sqlite3.Connection,
    section: str = "mainboard",
) -> dict[str, set[str]]:
    """Load distinct oracle_ids per deck for the specified section."""
    cursor = db.execute(
        "SELECT deck_id, oracle_id FROM corpus_deck_card "
        "WHERE section = ? AND oracle_id IS NOT NULL AND oracle_id != ''",
        (section,),
    )
    deck_cards: dict[str, set[str]] = {}
    for deck_id, oracle_id in cursor.fetchall():
        d_id = str(deck_id)
        o_id = str(oracle_id)
        if d_id not in deck_cards:
            deck_cards[d_id] = set()
        deck_cards[d_id].add(o_id)
    return deck_cards


def count_cooccurrences(
    deck_cards: dict[str, set[str]],
    names: dict[str, str],
    *,
    min_decks: int = 5,
) -> list[CooccurrencePair]:
    """Calculate pair co-occurrences and return sorted list (descending by deck_count)."""
    total_decks = len(deck_cards)
    if total_decks == 0:
        return []

    pair_counts: Counter[tuple[str, str]] = Counter()
    for oids in deck_cards.values():
        if len(oids) < 2:
            continue
        sorted_oids = sorted(oids)
        for a, b in itertools.combinations(sorted_oids, 2):
            pair_counts[(a, b)] += 1

    pairs: list[CooccurrencePair] = []
    for (a, b), count in pair_counts.items():
        if count >= min_decks:
            name_a = names.get(a, a)
            name_b = names.get(b, b)
            share = count / total_decks
            pairs.append(
                CooccurrencePair(
                    oracle_id_a=a,
                    oracle_id_b=b,
                    card_name_a=name_a,
                    card_name_b=name_b,
                    deck_count=count,
                    share=round(share, 4),
                )
            )

    # Sort primarily by deck_count descending, then card names for determinism
    pairs.sort(key=lambda p: (-p.deck_count, p.card_name_a, p.card_name_b))
    return pairs


def format_top_pairs_table(
    pairs: Iterable[CooccurrencePair],
    total_decks: int,
    top_n: int = 50,
) -> str:
    """Format top N pairs as a markdown table."""
    lines: list[str] = [
        f"| Rang | Karte A | Karte B | Decks | Anteil ({total_decks} Decks) |",
        "|---|---|---|---|---|",
    ]
    for rank, p in enumerate(itertools.islice(pairs, top_n), start=1):
        pct = f"{p.share * 100:.1f} %"
        lines.append(f"| {rank} | {p.card_name_a} | {p.card_name_b} | {p.deck_count} | {pct} |")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        "-d",
        type=Path,
        default=Path.home() / ".local/share/commander-studio",
        help="Path to Studio data dir or studio.sqlite3",
    )
    parser.add_argument(
        "--min-decks",
        "-m",
        type=int,
        default=5,
        help="Minimum number of decks for a pair to be included (default: 5)",
    )
    parser.add_argument(
        "--top",
        "-t",
        type=int,
        default=50,
        help="Number of top pairs to display (default: 50)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Optional path to export pairs as JSON",
    )
    args = parser.parse_args()

    db_path = args.data / "studio.sqlite3" if args.data.is_dir() else args.data
    if not db_path.is_file():
        print(f"Error: Database not found at {db_path}", file=sys.stderr)
        return 1

    with sqlite3.connect(db_path) as conn:
        names = load_card_names(conn)
        deck_cards = load_deck_cards(conn, section="mainboard")

    total_decks = len(deck_cards)
    print(f"Analysiere {total_decks} Decks aus dem kanonischen Korpus...")
    pairs = count_cooccurrences(deck_cards, names, min_decks=args.min_decks)
    print(f"Gefundene Paare mit >= {args.min_decks} Decks: {len(pairs)}")

    table = format_top_pairs_table(pairs, total_decks, top_n=args.top)
    print("\n" + table + "\n")

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "total_decks": total_decks,
            "min_decks_threshold": args.min_decks,
            "total_pairs_above_threshold": len(pairs),
            "top_pairs": [asdict(p) for p in pairs[: args.top]],
        }
        args.output.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Exportiert nach {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
