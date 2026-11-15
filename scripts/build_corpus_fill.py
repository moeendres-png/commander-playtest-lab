"""Build the corpus-fill decklist-inclusion file (#1387) from a built Studio store.

Counts the commander's canonical corpus (``universe_choice.local_spec`` over the
store's corpus decks, deduplicated by ``universe.resolve_universe``) once per
universe — the whole corpus (bracket label ``1-5``) and each bracket cohort
(``1`` .. ``5``, resolved with the cohort spec exactly as ``corpus_signals``
counts its cohorts) — and writes the counted deck-list file the production
signal import (``signals.import_signals``) reads: one row per card and universe
with ``decks_with_card`` over ``universe_decks``, in counted sections
(``store.COUNTED_SECTIONS``), grouped by oracle id (the corpus rows without an
oracle id keep their listed name). The stored signal of such a file is
``decklist_universe:corpus:<bracket>`` — a counted local universe, never an
EDHREC signal; the EDHREC files and rows are not touched by this script.

Bracket denominators do not sum to the whole-corpus denominator: a few
duplicate twins carry different stated brackets, so a cohort resolution keeps a
twin the whole-corpus resolution deduplicates into another cohort (cohorts are
never added — AGENTS.md §1).

The count is complete: a card of the universe without a row is a counted zero
of ``universe_decks`` (the decklist semantics), not unknown. The commander's own
card must count in every deck of every universe; the script aborts otherwise
(the import would refuse such a universe).

Usage:
    python scripts/build_corpus_fill.py --data <store folder> \
        [--commander "Chulane, Teller of Tales"] \
        [--out-dir data/research/corpus_fill_20261115] [--date 20261115]
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from commander_lab.studio import universe, universe_choice
from commander_lab.studio.store import COUNTED_SECTIONS, StudioStore

SOURCE = "corpus"
ALL_BRACKET = "1-5"
BRACKETS = ("1", "2", "3", "4", "5")


def _counts(store: StudioStore, deck_ids: list[str]) -> tuple[dict[str, int], dict[str, str], int]:
    """Decks per counted card over ``deck_ids``: key is the oracle id when the corpus
    row carries one, else the listed card name. Returns (hits by key, display name
    per key, corpus rows without an oracle id)."""
    db = store.connection
    marks = ", ".join("?" for _ in deck_ids)
    sections = ", ".join("?" for _ in COUNTED_SECTIONS)
    hits: dict[str, int] = {}
    for key, decks in db.execute(
        f"SELECT COALESCE(c.oracle_id, 'name:' || c.card_name), COUNT(DISTINCT c.deck_id) "
        f"FROM corpus_deck_card c WHERE c.deck_id IN ({marks}) "
        f"AND c.section IN ({sections}) AND c.quantity > 0 GROUP BY 1",
        [*deck_ids, *COUNTED_SECTIONS],
    ):
        hits[str(key)] = int(decks)
    without_oracle = int(
        db.execute(
            f"SELECT COUNT(*) FROM corpus_deck_card c WHERE c.deck_id IN ({marks}) "
            f"AND c.section IN ({sections}) AND c.quantity > 0 AND c.oracle_id IS NULL",
            [*deck_ids, *COUNTED_SECTIONS],
        ).fetchone()[0]
    )
    names: dict[str, str] = {}
    for oid, name in db.execute(
        "SELECT oracle_id, name FROM scryfall_card WHERE oracle_id IS NOT NULL"
    ):
        names.setdefault(str(oid), str(name))
    display: dict[str, str] = {}
    for key in hits:
        display[key] = key.removeprefix("name:") if key.startswith("name:") else names.get(key, key)
    return hits, display, without_oracle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, help="Studio data folder (built store)")
    parser.add_argument("--commander", default="Chulane, Teller of Tales")
    parser.add_argument(
        "--out-dir", default="data/research/corpus_fill_20261115", help="dataset folder"
    )
    parser.add_argument("--date", default="20261115", help="date stamp of the file name")
    args = parser.parse_args()

    store = StudioStore.open(args.data)
    base_spec = universe_choice.local_spec(store, args.commander)
    deck_ids = universe.resolve_universe(store, base_spec)
    if not deck_ids:
        print("no decks in the canonical corpus", file=sys.stderr)
        return 1
    db = store.connection
    commander_oid = db.execute(
        "SELECT oracle_id FROM scryfall_card WHERE name = ?", (args.commander,)
    ).fetchone()
    if commander_oid is None:
        print(f"commander not in the catalog: {args.commander}", file=sys.stderr)
        return 1
    commander_key = str(commander_oid[0])

    universes: list[tuple[str, list[str], dict[str, object]]] = [(ALL_BRACKET, deck_ids, base_spec)]
    for bracket in BRACKETS:
        spec = {**base_spec, "cohorts": [f"bracket:{bracket}"]}
        universes.append((bracket, universe.resolve_universe(store, spec), spec))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = args.commander.split(",", 1)[0].strip().lower().replace(" ", "_")
    path = out_dir / f"{slug}_corpus_decklist_inclusion_{args.date}.csv"
    rows_written = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "card_name",
                "source",
                "bracket",
                "decks_with_card",
                "universe_decks",
                "share",
                "universe_snapshot",
            ]
        )
        for bracket, sub, spec in universes:
            if not sub:
                continue
            snapshot = universe.snapshot_id(store, spec=spec, commander_names=[args.commander])
            hits, display, without_oracle = _counts(store, sub)
            if hits.get(commander_key) != len(sub):
                print(
                    f"universe {bracket}: commander counts {hits.get(commander_key)} "
                    f"of {len(sub)} decks — aborting",
                    file=sys.stderr,
                )
                return 1
            for key in sorted(hits, key=lambda item: display[item]):
                decks = hits[key]
                writer.writerow(
                    [
                        display[key],
                        SOURCE,
                        bracket,
                        decks,
                        len(sub),
                        f"{decks / len(sub):.4f}",
                        snapshot,
                    ]
                )
                rows_written += 1
            print(
                f"universe corpus:{bracket}: {len(sub)} decks, {len(hits)} cards, "
                f"snapshot {snapshot}, rows without oracle id: {without_oracle}"
            )
    print(f"wrote {rows_written} rows to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
