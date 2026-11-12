"""Unit tests for scripts/count_corpus_cooccurrence.py.

Tests co-occurrence pair counting against a deterministic mini-corpus.
"""

from __future__ import annotations

import sqlite3

from scripts.count_corpus_cooccurrence import (
    count_cooccurrences,
    format_top_pairs_table,
    load_card_names,
    load_deck_cards,
)


def _create_mini_corpus_db() -> sqlite3.Connection:
    """Create in-memory SQLite database with mini-corpus (3 decks of 4 cards)."""
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE corpus_deck_card ("
        "deck_id TEXT NOT NULL, "
        "card_name TEXT NOT NULL, "
        "oracle_id TEXT, "
        "quantity INTEGER NOT NULL, "
        "section TEXT NOT NULL, "
        "normalization_status TEXT NOT NULL, "
        "PRIMARY KEY (deck_id, card_name, section)"
        ")"
    )
    conn.execute("CREATE TABLE scryfall_card (oracle_id TEXT PRIMARY KEY, name TEXT NOT NULL)")

    # Cards:
    # OID_A = Sol Ring
    # OID_B = Arcane Signet
    # OID_C = Birds of Paradise
    # OID_D = Llanowar Elves
    # OID_E = Counterspell
    # OID_F = Swords to Plowshares
    cards = [
        ("oid-a", "Sol Ring"),
        ("oid-b", "Arcane Signet"),
        ("oid-c", "Birds of Paradise"),
        ("oid-d", "Llanowar Elves"),
        ("oid-e", "Counterspell"),
        ("oid-f", "Swords to Plowshares"),
    ]
    for oid, name in cards:
        conn.execute("INSERT INTO scryfall_card(oracle_id, name) VALUES (?, ?)", (oid, name))

    # Deck 1: A, B, C, D (4 cards)
    # Deck 2: A, B, C, E (4 cards)
    # Deck 3: A, B, D, F (4 cards)
    deck_rows = [
        ("d1", "Sol Ring", "oid-a", 1, "mainboard", "NORMALIZED"),
        ("d1", "Arcane Signet", "oid-b", 1, "mainboard", "NORMALIZED"),
        ("d1", "Birds of Paradise", "oid-c", 1, "mainboard", "NORMALIZED"),
        ("d1", "Llanowar Elves", "oid-d", 1, "mainboard", "NORMALIZED"),
        ("d2", "Sol Ring", "oid-a", 1, "mainboard", "NORMALIZED"),
        ("d2", "Arcane Signet", "oid-b", 1, "mainboard", "NORMALIZED"),
        ("d2", "Birds of Paradise", "oid-c", 1, "mainboard", "NORMALIZED"),
        ("d2", "Counterspell", "oid-e", 1, "mainboard", "NORMALIZED"),
        ("d3", "Sol Ring", "oid-a", 1, "mainboard", "NORMALIZED"),
        ("d3", "Arcane Signet", "oid-b", 1, "mainboard", "NORMALIZED"),
        ("d3", "Llanowar Elves", "oid-d", 1, "mainboard", "NORMALIZED"),
        ("d3", "Swords to Plowshares", "oid-f", 1, "mainboard", "NORMALIZED"),
        # Add a commander card to ensure it is excluded
        ("d1", "Chulane, Teller of Tales", "oid-cmd", 1, "commander", "NORMALIZED"),
    ]
    conn.executemany(
        "INSERT INTO corpus_deck_card VALUES (?, ?, ?, ?, ?, ?)",
        deck_rows,
    )
    conn.commit()
    return conn


def test_mini_corpus_pair_counts_and_thresholds() -> None:
    conn = _create_mini_corpus_db()
    try:
        names = load_card_names(conn)
        deck_cards = load_deck_cards(conn, section="mainboard")

        assert len(deck_cards) == 3
        # Each deck has exactly 4 mainboard cards (commander excluded)
        assert len(deck_cards["d1"]) == 4
        assert len(deck_cards["d2"]) == 4
        assert len(deck_cards["d3"]) == 4

        # Test min_decks = 1 (all pairs)
        pairs_all = count_cooccurrences(deck_cards, names, min_decks=1)
        # Combinations per deck: C(4,2) = 6
        # D1 has: AB, AC, AD, BC, BD, CD
        # D2 has: AB, AC, AE, BC, BE, CE
        # D3 has: AB, AD, AF, BD, BF, DF
        # Total distinct pairs = 12
        assert len(pairs_all) == 12

        # Pair AB (Sol Ring + Arcane Signet) in all 3 decks
        top_pair = pairs_all[0]
        assert top_pair.oracle_id_a == "oid-a"
        assert top_pair.oracle_id_b == "oid-b"
        assert top_pair.card_name_a == "Sol Ring"
        assert top_pair.card_name_b == "Arcane Signet"
        assert top_pair.deck_count == 3
        assert top_pair.share == 1.0

        # Test min_decks = 2 (pairs present in >= 2 decks)
        # Present in 2 decks: AC (2), BC (2), AD (2), BD (2) plus AB (3) -> 5 pairs
        pairs_2 = count_cooccurrences(deck_cards, names, min_decks=2)
        assert len(pairs_2) == 5
        counts = {f"{p.card_name_a} + {p.card_name_b}": p.deck_count for p in pairs_2}
        assert counts["Sol Ring + Arcane Signet"] == 3
        assert counts["Sol Ring + Birds of Paradise"] == 2
        assert counts["Arcane Signet + Birds of Paradise"] == 2
        assert counts["Sol Ring + Llanowar Elves"] == 2
        assert counts["Arcane Signet + Llanowar Elves"] == 2

        # Test min_decks = 3 (pairs present in all 3 decks)
        pairs_3 = count_cooccurrences(deck_cards, names, min_decks=3)
        assert len(pairs_3) == 1
        assert pairs_3[0].card_name_a == "Sol Ring"
        assert pairs_3[0].card_name_b == "Arcane Signet"
    finally:
        conn.close()


def test_duplicate_cards_and_null_oracle_ids() -> None:
    """Ensure duplicate cards (e.g. basics) and null oracle IDs don't cause self-pairs."""
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE corpus_deck_card ("
        "deck_id TEXT NOT NULL, "
        "card_name TEXT NOT NULL, "
        "oracle_id TEXT, "
        "quantity INTEGER NOT NULL, "
        "section TEXT NOT NULL, "
        "normalization_status TEXT NOT NULL, "
        "PRIMARY KEY (deck_id, card_name, section)"
        ")"
    )
    # Deck with duplicate Forest entries or multiple quantities
    conn.executemany(
        "INSERT INTO corpus_deck_card VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("d1", "Forest", "oid-forest", 10, "mainboard", "NORMALIZED"),
            ("d1", "Island", "oid-island", 8, "mainboard", "NORMALIZED"),
            ("d1", "Unknown Card", None, 1, "mainboard", "AMBIGUOUS"),
        ],
    )
    conn.commit()
    try:
        deck_cards = load_deck_cards(conn, section="mainboard")
        assert len(deck_cards["d1"]) == 2  # Forest and Island, None excluded

        pairs = count_cooccurrences(deck_cards, {}, min_decks=1)
        assert len(pairs) == 1
        assert pairs[0].oracle_id_a == "oid-forest"
        assert pairs[0].oracle_id_b == "oid-island"
        assert pairs[0].deck_count == 1
    finally:
        conn.close()


def test_table_formatting() -> None:
    conn = _create_mini_corpus_db()
    try:
        names = load_card_names(conn)
        deck_cards = load_deck_cards(conn, section="mainboard")
        pairs = count_cooccurrences(deck_cards, names, min_decks=2)
        table = format_top_pairs_table(pairs, total_decks=len(deck_cards), top_n=3)

        lines = table.strip().split("\n")
        assert len(lines) == 5  # header + separator + 3 rows
        assert "Sol Ring" in lines[2]
        assert "Arcane Signet" in lines[2]
        assert "100.0 %" in lines[2]
    finally:
        conn.close()
