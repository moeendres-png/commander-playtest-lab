#!/usr/bin/env python3
"""Sub-archetype analysis of the canonical Chulane corpus (issue #1368).

Tags the decks of the counted universe (the decks ``universe.resolve_universe``
selects for the commander — 2,823 on the store this was developed against) rule-based
from their composition (``commander_lab.studio.subarchetypes``), recomputes the corpus
signals of the tier-list plan per archetype and correlates the signal vectors between
the archetypes (Spearman). Analysis only: nothing here writes to the store or feeds
the strength index.

    python scripts/subarchetype_analysis.py --data "<Studio-Datenordner>" \
        --out subarchetypes_1368.json

The store must hold the repository data (``import-all --from-repo``): corpus,
Scryfall card facts, role claims and the signal files (for ``edhrec_global_inclusion``).
Thresholds are the module constants below; the JSON carries the share distribution and
the deck counts at neighbouring thresholds next to every tag, so each line is auditable.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from commander_lab.studio import combos, queries, universe
from commander_lab.studio import subarchetypes as sa
from commander_lab.studio.store import StudioStore

COMMANDER = "Chulane, Teller of Tales"

# The disclosed tag lines. Each share threshold sits near the 80th-90th percentile of
# its measured share distribution over the canonical decks (see the report): a tag
# marks a deck whose theme is a defining share of its nonland cards, not a splash.
THRESHOLDS = sa.TagThresholds(
    landfall_min_share=0.10,
    blink_bounce_min_share=0.04,
    big_mana_min_share=0.12,
    big_mana_min_value=6.0,
    clue_artifact_min_share=0.15,
)
SENSITIVITY: dict[str, tuple[float, ...]] = {
    sa.TAG_LANDFALL: (0.08, 0.10, 0.12, 0.15),
    sa.TAG_BLINK_BOUNCE: (0.03, 0.04, 0.05, 0.08),
    sa.TAG_BIG_MANA: (0.10, 0.12, 0.15),
    sa.TAG_CLUE_ARTIFACT: (0.12, 0.15, 0.20),
}

_CLUE = re.compile(r"investigate\b|create[^.\n]*\bclue\b", re.IGNORECASE)
_EXTRA_LAND = re.compile(r"play (?:an|two|three|four|\d+) additional lands?\b", re.IGNORECASE)


def _card_infos(store: StudioStore) -> dict[str, sa.CardInfo]:
    roles: dict[str, set[str]] = {}
    for oracle_id, role in store.connection.execute("SELECT oracle_id, role FROM card_role"):
        roles.setdefault(str(oracle_id), set()).add(str(role))
    infos: dict[str, sa.CardInfo] = {}
    for oracle_id, name, type_line, oracle_text, mana_value in store.connection.execute(
        "SELECT oracle_id, name, type_line, oracle_text, mana_value FROM scryfall_card"
    ):
        text = str(oracle_text or "")
        types = str(type_line or "")
        infos[str(oracle_id)] = sa.CardInfo(
            oracle_id=str(oracle_id),
            name=str(name),
            roles=frozenset(roles.get(str(oracle_id), ())),
            mana_value=float(mana_value) if mana_value is not None else None,
            is_land="Land" in types,
            is_artifact="Artifact" in types,
            makes_clue=bool(_CLUE.search(text)),
            extra_land=bool(_EXTRA_LAND.search(text)),
        )
    return infos


def _decks(store: StudioStore, deck_ids: list[str]) -> list[sa.DeckInput]:
    bracket: dict[str, int] = {}
    for deck_id, cohort in store.connection.execute(
        "SELECT deck_id, cohort FROM corpus_cohort WHERE cohort LIKE 'bracket:%'"
    ):
        bracket[str(deck_id)] = int(str(cohort).split(":", 1)[1])
    wanted = set(deck_ids)
    cards_of: dict[str, set[str]] = {deck_id: set() for deck_id in deck_ids}
    names_of: dict[str, set[str]] = {deck_id: set() for deck_id in deck_ids}
    for deck_id, oracle_id, card_name in store.connection.execute(
        "SELECT deck_id, oracle_id, card_name FROM corpus_deck_card "
        "WHERE section IN ('main', 'mainboard') AND quantity > 0"
    ):
        deck_id = str(deck_id)
        if deck_id not in wanted:
            continue
        cards_of[deck_id].add(str(oracle_id) if oracle_id else f"name:{card_name}")
        full = str(card_name).strip().casefold()
        names_of[deck_id].add(full)
        if " // " in full:
            names_of[deck_id].add(full.split(" // ")[0].strip())
    return [
        sa.DeckInput(
            deck_id=deck_id,
            bracket=bracket.get(deck_id),
            oracle_ids=frozenset(cards_of[deck_id]),
            names=frozenset(names_of[deck_id]),
        )
        for deck_id in deck_ids
    ]


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(fraction * len(ordered)))]


def _signal_vectors(
    decks: list[sa.DeckInput],
    pool: list[str],
    global_inclusion: dict[str, float | None],
) -> dict[str, dict[str, float | None]]:
    """The four corpus signals of one deck set, per pool card (oracle id)."""
    shares = sa.inclusion_shares(decks)
    tuned_decks = [deck for deck in decks if deck.bracket in (4, 5)]
    low_decks = [deck for deck in decks if deck.bracket == 2]
    tuned = sa.inclusion_shares(tuned_decks)
    low = sa.inclusion_shares(low_decks)
    vectors: dict[str, dict[str, float | None]] = {signal: {} for signal in sa.SIGNALS}
    for oracle_id in pool:
        share = shares.get(oracle_id, 0.0)
        vectors[sa.SIGNAL_DECK_UNIVERSE][oracle_id] = share
        vectors[sa.SIGNAL_LOG_LIFT][oracle_id] = sa.log_lift(share, global_inclusion[oracle_id])
        if tuned_decks and low_decks:
            vectors[sa.SIGNAL_TUNED][oracle_id] = tuned.get(oracle_id, 0.0)
            vectors[sa.SIGNAL_BRACKET_SLOPE][oracle_id] = sa.bracket_slope(tuned, low, oracle_id)
        else:
            vectors[sa.SIGNAL_TUNED][oracle_id] = None
            vectors[sa.SIGNAL_BRACKET_SLOPE][oracle_id] = None
    return vectors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, help="Studio data folder (the store)")
    parser.add_argument("--out", required=True, help="where the JSON result is written")
    parser.add_argument("--commander", default=COMMANDER)
    args = parser.parse_args()

    store = StudioStore.open(args.data)
    db = store.connection
    deck_ids = universe.resolve_universe(store, {"commanders": [args.commander]})
    decks = _decks(store, deck_ids)
    infos = _card_infos(store)
    stored = combos.stored_combos(store, args.commander)
    combo_sets = [frozenset(name.strip().casefold() for name in cards) for cards, _ in stored]
    tagged = [(deck, sa.tag_deck(deck, infos, combo_sets, THRESHOLDS)) for deck in decks]

    pool_rows = queries.legal_pool(store, [args.commander])
    name_of_id: dict[str, str] = {}
    for oracle_id, oracle_name in db.execute(
        "SELECT oracle_id, oracle_name FROM card_fact WHERE oracle_id IS NOT NULL"
    ):
        name_of_id[str(oracle_id)] = str(oracle_name)
    pool: list[str] = []
    pool_names: dict[str, str] = {}
    id_of_name = {name: oracle_id for oracle_id, name in name_of_id.items()}
    for row in pool_rows:
        oracle_id = id_of_name.get(str(row["oracle_name"]))
        if oracle_id is not None:
            pool.append(oracle_id)
            pool_names[oracle_id] = str(row["oracle_name"])
    global_by_name: dict[str, float | None] = {
        str(name): (float(value) if value is not None else None)
        for name, value in db.execute(
            "SELECT card_name, value FROM card_signal "
            "WHERE signal = 'edhrec_global_inclusion' AND commander_name = ''"
        )
    }

    def _global_of(name: str) -> float | None:
        # The repo's name discipline (combos._keys, universe.deck_sets): a two-part
        # card also answers to its front face, under which the global file lists it.
        if name in global_by_name:
            return global_by_name[name]
        return global_by_name.get(name.split(" // ")[0])

    global_inclusion = {oracle_id: _global_of(pool_names[oracle_id]) for oracle_id in pool}

    sets: dict[str, list[sa.DeckInput]] = {"corpus": decks}
    for tag in sa.ALL_TAGS:
        sets[tag] = [deck for deck, result in tagged if result.tags[tag]]
    vectors = {
        name: _signal_vectors(members, pool, global_inclusion) for name, members in sets.items()
    }

    spearman: dict[str, dict[str, dict[str, float | None]]] = {}
    for signal in sa.SIGNALS:
        spearman[signal] = {}
        for left in sets:
            spearman[signal][left] = {}
            for right in sets:
                spearman[signal][left][right] = sa.spearman(
                    vectors[left][signal], vectors[right][signal]
                )

    corpus_shares = sa.inclusion_shares(decks)
    archetypes: dict[str, object] = {}
    for tag in sa.ALL_TAGS:
        members = sets[tag]
        shares = sa.inclusion_shares(members)
        distribution = [shares.get(oracle_id, 0.0) for oracle_id in pool]
        top = sorted(
            pool,
            key=lambda oid: (
                -(shares.get(oid, 0.0) - corpus_shares.get(oid, 0.0)),
                pool_names[oid],
            ),
        )[:10]
        archetypes[tag] = {
            "decks": len(members),
            "brackets": dict(
                sorted(Counter(deck.bracket for deck in members if deck.bracket).items())
            ),
            "pool_inclusion_percentiles": {
                "p50": _percentile(distribution, 0.5),
                "p75": _percentile(distribution, 0.75),
                "p90": _percentile(distribution, 0.9),
                "max": max(distribution) if distribution else None,
            },
            "pool_cards_at_half_or_more": sum(1 for value in distribution if value >= 0.5),
            "top_cards_over_corpus": [
                {
                    "card": pool_names[oid],
                    "share_in_archetype": shares.get(oid, 0.0),
                    "share_in_corpus": corpus_shares.get(oid, 0.0),
                }
                for oid in top
            ],
        }

    overlaps: dict[str, dict[str, int]] = {}
    for left in sa.ALL_TAGS:
        overlaps[left] = {
            right: len(
                {deck.deck_id for deck in sets[left]} & {deck.deck_id for deck in sets[right]}
            )
            for right in sa.ALL_TAGS
        }
    tag_counts = Counter(sum(1 for tag in sa.ALL_TAGS if result.tags[tag]) for _, result in tagged)
    share_distributions: dict[str, object] = {}
    for tag in sa.SHARE_TAGS:
        values = [result.shares[tag] for _, result in tagged if result.shares[tag] is not None]
        share_distributions[tag] = {
            "percentiles": {
                "p25": _percentile(values, 0.25),  # type: ignore[arg-type]
                "p50": _percentile(values, 0.5),  # type: ignore[arg-type]
                "p75": _percentile(values, 0.75),  # type: ignore[arg-type]
                "p90": _percentile(values, 0.9),  # type: ignore[arg-type]
            },
            "decks_at_thresholds": {
                str(threshold): sum(1 for value in values if value >= threshold)
                for threshold in SENSITIVITY[tag]
            },
        }
    combo_histogram = Counter(result.complete_two_card for _, result in tagged)
    corpus_cards = {oid for deck in decks for oid in deck.oracle_ids}
    result: dict[str, object] = {
        "commander": args.commander,
        "canonical_decks": len(decks),
        "brackets": dict(sorted(Counter(deck.bracket for deck in decks if deck.bracket).items())),
        "decks_without_nonland_cards": sum(
            1 for _, result_ in tagged if result_.shares[sa.TAG_LANDFALL] is None
        ),
        "distinct_corpus_cards": len(corpus_cards),
        "corpus_cards_with_role": sum(
            1 for oid in corpus_cards if oid in infos and infos[oid].roles
        ),
        "role_cards": {
            role: sum(1 for oid in corpus_cards if oid in infos and role in infos[oid].roles)
            for role in ("landfall", "flicker", "bounce")
        },
        "extra_land_cards": sum(
            1 for oid in corpus_cards if oid in infos and infos[oid].extra_land
        ),
        "clue_maker_cards": sum(
            1 for oid in corpus_cards if oid in infos and infos[oid].makes_clue
        ),
        "pool_cards": len(pool),
        "pool_cards_with_global_inclusion": sum(
            1 for value in global_inclusion.values() if value is not None
        ),
        "combos_listed": len(stored),
        "combos_two_card": sum(1 for cards, _ in stored if len(cards) == 2),
        "thresholds": {
            "landfall_min_share": THRESHOLDS.landfall_min_share,
            "blink_bounce_min_share": THRESHOLDS.blink_bounce_min_share,
            "big_mana_min_share": THRESHOLDS.big_mana_min_share,
            "big_mana_min_value": THRESHOLDS.big_mana_min_value,
            "clue_artifact_min_share": THRESHOLDS.clue_artifact_min_share,
        },
        "share_distributions": share_distributions,
        "combo_histogram": {str(key): combo_histogram[key] for key in sorted(combo_histogram)},
        "decks_by_tag_count": {str(key): tag_counts[key] for key in sorted(tag_counts)},
        "archetypes": archetypes,
        "overlaps": overlaps,
        "spearman": spearman,
    }
    Path(args.out).write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"canonical decks: {len(decks)}; pool cards: {len(pool)}")
    for tag in sa.ALL_TAGS:
        print(f"{tag}: {len(sets[tag])} decks")
    print(f"JSON: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
