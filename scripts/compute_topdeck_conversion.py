"""Compute TopDeck card conversion per commander (#1205).

Applies the normative conversion definitions from docs/TOPDECK.md §6
(moeendres-png/deckbuild-studio):
  - Top-Cut-Conversion: Share of decks with this card that reached Top Cut.
  - Denominator: Decks with this card in tournaments with topCut > 0
    AND known bracket record (winsBracket is not None or lossesBracket is not None).
  - Numerator: Decks with this card where winsBracket + lossesBracket > 0.
  - Minimum sample size (Mindest-n): At least 10 decks with known bracket record.
    Below 10, conversion_rate remains NULL.
  - Fail-closed: Tournaments without top cut and decks with unknown bracket record
    stay out of the denominator (never silently counted).

Pure file calculation: operates on CSV files (and optional tournament metadata)
without requiring an API key.
"""

from __future__ import annotations

import argparse
import csv
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger("topdeck_conversion")

CONVERSION_MIN_DECKS = 10


@dataclass(frozen=True)
class TournamentDeck:
    """A single tournament deck entry."""

    tournament_name: str
    date_str: str
    player_name: str
    wins: int
    draws: int
    losses: int
    commander_name: str
    card_names: frozenset[str]
    top_cut: int | None = None
    wins_bracket: int | None = None
    losses_bracket: int | None = None

    @property
    def bracket_known(self) -> bool:
        """True if bracket record is known from source data."""
        return self.wins_bracket is not None or self.losses_bracket is not None

    def top_cut_reached(self) -> bool | None:
        """Evaluate if top cut was reached per docs/TOPDECK.md §6.

        Returns True/False when bracket record decides it, None when the
        tournament has no top cut or the bracket record is unknown.
        NEVER derived from standings order or swiss wins alone.
        """
        if not self.top_cut or self.top_cut <= 0:
            return None
        if not self.bracket_known:
            return None
        played = (self.wins_bracket or 0) + (self.losses_bracket or 0)
        return played > 0


@dataclass(frozen=True)
class CardConversionStat:
    """Computed conversion statistics for a card under a specific commander."""

    commander: str
    card_name: str
    appearances: int
    conversions: int
    conversion_rate: float | None
    sample_size_base: int

    def to_row(self) -> list[str]:
        rate_str = f"{self.conversion_rate:.6f}" if self.conversion_rate is not None else "NULL"
        return [
            self.commander,
            self.card_name,
            str(self.appearances),
            str(self.conversions),
            rate_str,
            str(self.sample_size_base),
        ]


def parse_deck_csv(
    csv_path: Path,
    metadata_lookup: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> tuple[str, list[TournamentDeck]]:
    """Parse one commander deck CSV into TournamentDeck records.

    Matches schema:
    tournament,date,player,wins,draws,losses,card_name,quantity,section
    (with optional bracket/topcut columns if present).
    """
    metadata_lookup = metadata_lookup or {}
    decks_map: dict[tuple[str, str, str], dict[str, Any]] = {}
    detected_commander: str | None = None

    with csv_path.open(encoding="utf-8", newline="") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            t_name = str(row.get("tournament") or "").strip()
            d_str = str(row.get("date") or "").strip()
            p_name = str(row.get("player") or "").strip()
            card = str(row.get("card_name") or "").strip()
            section = str(row.get("section") or "").strip().lower()

            if section == "commander" and not detected_commander:
                detected_commander = card

            key = (t_name, p_name, d_str)
            if key not in decks_map:
                wins = int(row.get("wins") or 0)
                draws = int(row.get("draws") or 0)
                losses = int(row.get("losses") or 0)

                # Check row columns first, then fallback to metadata_lookup
                wb_val = row.get("winsBracket") or row.get("wins_bracket")
                lb_val = row.get("lossesBracket") or row.get("losses_bracket")
                tc_val = row.get("topCut") or row.get("top_cut")

                wb = int(wb_val) if wb_val is not None and str(wb_val).strip() != "" else None
                lb = int(lb_val) if lb_val is not None and str(lb_val).strip() != "" else None
                tc = int(tc_val) if tc_val is not None and str(tc_val).strip() != "" else None

                meta = metadata_lookup.get((t_name, p_name))
                if meta:
                    if tc is None and "top_cut" in meta:
                        tc = meta["top_cut"]
                    if wb is None and "wins_bracket" in meta:
                        wb = meta["wins_bracket"]
                    if lb is None and "losses_bracket" in meta:
                        lb = meta["losses_bracket"]

                decks_map[key] = {
                    "tournament": t_name,
                    "date": d_str,
                    "player": p_name,
                    "wins": wins,
                    "draws": draws,
                    "losses": losses,
                    "top_cut": tc,
                    "wins_bracket": wb,
                    "losses_bracket": lb,
                    "cards": set(),
                }

            if card:
                decks_map[key]["cards"].add(card)

    if not detected_commander:
        # Fallback to file name stem if no commander row
        stem = csv_path.stem.replace("topdeck_", "").replace("_decks", "")
        detected_commander = stem.replace("_", " ").title()

    results: list[TournamentDeck] = []
    for d in decks_map.values():
        results.append(
            TournamentDeck(
                tournament_name=d["tournament"],
                date_str=d["date"],
                player_name=d["player"],
                wins=d["wins"],
                draws=d["draws"],
                losses=d["losses"],
                commander_name=detected_commander,
                card_names=frozenset(d["cards"]),
                top_cut=d["top_cut"],
                wins_bracket=d["wins_bracket"],
                losses_bracket=d["losses_bracket"],
            )
        )

    return detected_commander, results


def compute_conversions_for_decks(
    commander_name: str,
    decks: list[TournamentDeck],
    min_sample: int = CONVERSION_MIN_DECKS,
) -> list[CardConversionStat]:
    """Compute per-card conversion statistics for a set of commander decks."""
    all_cards: set[str] = set()
    for d in decks:
        all_cards.update(d.card_names)

    stats: list[CardConversionStat] = []
    for card in sorted(all_cards):
        appearances = 0
        cut_known = 0
        cut_hits = 0

        for d in decks:
            if card in d.card_names:
                appearances += 1
                reached = d.top_cut_reached()
                if reached is not None:
                    cut_known += 1
                    if reached:
                        cut_hits += 1

        rate = (cut_hits / cut_known) if cut_known >= min_sample else None

        stats.append(
            CardConversionStat(
                commander=commander_name,
                card_name=card,
                appearances=appearances,
                conversions=cut_hits,
                conversion_rate=rate,
                sample_size_base=cut_known,
            )
        )

    return stats


def export_conversions_csv(
    stats: list[CardConversionStat],
    output_path: Path,
) -> None:
    """Export conversion records to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(
            [
                "commander",
                "card_name",
                "appearances",
                "conversions",
                "conversion_rate",
                "sample_size_base",
            ]
        )
        for s in stats:
            writer.writerow(s.to_row())
    logger.info("Wrote %d rows to %s", len(stats), output_path)


def main() -> None:
    """CLI entrypoint for standalone conversion calculation."""
    parser = argparse.ArgumentParser(
        description="Compute TopDeck card conversions per commander (Refs #1205)"
    )
    parser.add_argument(
        "--decks-dir",
        type=Path,
        default=Path("data/research/topdeck_20261112"),
        help="Directory containing per-commander deck CSVs",
    )
    parser.add_argument(
        "--chulane-csv",
        type=Path,
        default=Path("data/research/deckbuilder_1655/topdeck_chulane_decks.csv"),
        help="Path to Chulane deck CSV",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/research/topdeck_20261112/topdeck_card_conversions.csv"),
        help="Path for output conversion CSV",
    )
    parser.add_argument(
        "--min-sample",
        type=int,
        default=CONVERSION_MIN_DECKS,
        help="Minimum sample size for conversion rate calculation (default: 10)",
    )
    args = parser.parse_args()

    # Find all CSV files
    csv_files: list[Path] = []
    if args.decks_dir.is_dir():
        for p in sorted(args.decks_dir.glob("topdeck_*_decks.csv")):
            csv_files.append(p)

    if args.chulane_csv.is_file() and args.chulane_csv not in csv_files:
        csv_files.append(args.chulane_csv)

    print(f"Found {len(csv_files)} deck CSV files.")

    total_decks = 0
    total_card_rows = 0
    all_stats: list[CardConversionStat] = []

    for f in csv_files:
        cname, decks = parse_deck_csv(f)
        total_decks += len(decks)
        card_rows = sum(len(d.card_names) for d in decks)
        total_card_rows += card_rows

        c_stats = compute_conversions_for_decks(cname, decks, min_sample=args.min_sample)
        all_stats.extend(c_stats)
        print(f"Commander: {cname:35s} | Decks: {len(decks):3d} | Unique cards: {len(c_stats):3d}")

    print(f"\nTotals: {len(csv_files)} commanders, {total_decks} decks, {total_card_rows} card instances")
    export_conversions_csv(all_stats, args.output)
    print(f"Saved {len(all_stats)} conversion rows to {args.output}")


if __name__ == "__main__":
    main()
