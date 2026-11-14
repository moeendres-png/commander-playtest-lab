"""The grouped co-occurrence count equals the old per-card-fact join on a mixed corpus.

All data here is synthetic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from commander_lab.studio import StudioStore, builder
from tests.unit.test_studio_builder import _fill

COMMANDER = "Test Commander"
TARGET = "card:project:0007"  # Swarm Rat, oracle id "oracle-swarm-rat"


@pytest.fixture
def corpus(tmp_path: Path) -> StudioStore:
    store = StudioStore.open(tmp_path / "studio")
    _fill(store, tmp_path)
    return store


def _oracle_ids(store: StudioStore) -> dict[str, str]:
    return {
        str(r["oracle_name"]): str(r["oracle_id"])
        for r in store.connection.execute(
            "SELECT oracle_name, oracle_id FROM card_fact WHERE oracle_name LIKE 'Filler 0%'"
        )
    }


def _add_decks(store: StudioStore) -> None:
    """Six more decks around the card Swarm Rat; a card is listed by oracle id in some decks
    and by name only (oracle_id NULL) in others."""
    ids = _oracle_ids(store)
    rat = "oracle-swarm-rat"
    forest = "oracle-forest"
    # (deck_id, duplicate_of, commander, rows of (name, oracle_id or None, section))
    decks: list[tuple[str, str | None, str, list[tuple[str, str | None, str]]]] = [
        (
            "d5",
            None,
            COMMANDER,
            [
                ("Swarm Rat", None, "mainboard"),  # by name only
                ("Forest", None, "mainboard"),
                ("Filler 00", ids["Filler 00"], "mainboard"),
            ],
        ),
        (
            "d6",
            None,
            COMMANDER,
            [
                ("Swarm Rat", rat, "mainboard"),
                # one deck holding both spellings of the same card in two sections
                ("Filler 01", ids["Filler 01"], "mainboard"),
                ("Filler 01", None, "commander"),
                # only in the sideboard: must not count
                ("Forest", forest, "sideboard"),
                ("Filler 04", None, "sideboard"),
            ],
        ),
        (
            "d7",
            None,
            COMMANDER,
            [
                # the chosen card sits only in the sideboard: the deck is not in the cohort
                ("Swarm Rat", rat, "sideboard"),
                ("Filler 00", ids["Filler 00"], "mainboard"),
                ("Filler 05", None, "mainboard"),
            ],
        ),
        (
            "d8",
            "d1",  # a duplicate deck: must not count
            COMMANDER,
            [
                ("Swarm Rat", rat, "mainboard"),
                ("Filler 00", ids["Filler 00"], "mainboard"),
                ("Filler 02", ids["Filler 02"], "mainboard"),
            ],
        ),
        (
            "d9",
            None,
            COMMANDER,
            [
                ("Swarm Rat", None, "mainboard"),
                ("Filler 02", None, "mainboard"),
                ("Filler 01", ids["Filler 01"], "mainboard"),
                ("Forest", forest, "mainboard"),
                ("Forest", None, "maybeboard"),  # both spellings, same deck
            ],
        ),
        (
            "d10",
            None,
            "Other Commander",  # bound to another commander: must not count
            [("Swarm Rat", rat, "mainboard"), ("Filler 03", ids["Filler 03"], "mainboard")],
        ),
    ]
    with store.connection as db:
        for deck_id, duplicate_of, commander, rows in decks:
            db.execute(
                "INSERT INTO corpus_deck(deck_id, cohort, url, platform, play_group, deck_date, "
                "tags, fingerprint, duplicate_of, legality_audit, source_id) "
                "SELECT ?, cohort, url, platform, play_group, deck_date, tags, ?, ?, "
                "legality_audit, source_id FROM corpus_deck WHERE deck_id = 'd1'",
                (deck_id, f"fp-{deck_id}", duplicate_of),
            )
            db.execute(
                "INSERT INTO commander_binding(kind, key, commander_name, basis) "
                "VALUES ('corpus_deck', ?, ?, 'IMPORT_DECLARED')",
                (deck_id, commander),
            )
            db.executemany(
                "INSERT INTO corpus_deck_card(deck_id, card_name, oracle_id, quantity, section, "
                "normalization_status) VALUES (?, ?, ?, 1, ?, 'exact')",
                [(deck_id, name, oid, section) for name, oid, section in rows],
            )


def _reference(store: StudioStore, card_id: str) -> tuple[int, dict[str, int]]:
    """The old implementation: every commander-legal card fact joined to the deck rows."""
    db = store.connection
    target = db.execute(
        "SELECT oracle_id, oracle_name FROM card_fact WHERE card_id = ?", (card_id,)
    ).fetchone()
    cohort = (
        "SELECT DISTINCT k.deck_id FROM corpus_deck_card k JOIN corpus_deck d USING (deck_id) "
        "WHERE d.duplicate_of IS NULL AND k.section != 'sideboard' "
        "AND (k.oracle_id = ? OR k.card_name = ?) "
        "AND EXISTS (SELECT 1 FROM commander_binding cb WHERE cb.kind = 'corpus_deck' "
        "AND cb.key = d.deck_id AND cb.commander_name = ?) "
        "AND (SELECT COUNT(*) FROM commander_binding cb WHERE cb.kind = 'corpus_deck' "
        "AND cb.key = d.deck_id) = 1"
    )
    deck_ids = [
        str(r[0])
        for r in db.execute(cohort, (target["oracle_id"], target["oracle_name"], COMMANDER))
    ]
    counts: dict[str, int] = {}
    for fact in db.execute(
        "SELECT card_id, oracle_id, oracle_name FROM card_fact "
        "WHERE card_id != ? AND commander_legal = 1",
        (card_id,),
    ):
        marks = ",".join("?" for _ in deck_ids)
        n = db.execute(
            "SELECT COUNT(DISTINCT k.deck_id) FROM corpus_deck_card k "
            f"WHERE k.deck_id IN ({marks}) AND k.section != 'sideboard' "
            "AND (k.oracle_id = ? OR (k.oracle_id IS NULL AND k.card_name = ?))",
            [*deck_ids, fact["oracle_id"], fact["oracle_name"]],
        ).fetchone()[0]
        if n:
            counts[str(fact["card_id"])] = int(n)
    return len(deck_ids), counts


def test_cooccurrence_equals_the_reference_join_on_a_mixed_corpus(corpus: StudioStore) -> None:
    _add_decks(corpus)
    expected_decks, expected = _reference(corpus, TARGET)
    result = builder.card_cooccurrence(corpus, TARGET, [COMMANDER], limit=1000)
    cards = result["cards"]
    assert isinstance(cards, list)

    # decks d1, d3, d5, d6, d9 hold the card outside the sideboard (d4/d8 duplicates, d7 sideboard,
    # d10 another commander)
    assert expected_decks == 5
    assert result["card_decks"] == expected_decks
    assert {c["card_id"]: c["both_hits"] for c in cards} == expected
    assert all(c["card_decks"] == expected_decks for c in cards)

    by_name = {c["name"]: c["both_hits"] for c in cards}
    assert by_name["Forest"] == 3  # d1 by id, d5 by name, d9 by both spellings (once)
    assert by_name["Filler 00"] == 1  # d5 only: d7 lacks the card, d8 is a duplicate
    assert by_name["Filler 01"] == 2  # d6 holds both spellings (once), d9 by id
    assert by_name["Filler 02"] == 1  # d9 by name; the duplicate d8 does not count
    assert "Filler 03" not in by_name  # only the other commander's deck
    assert "Filler 04" not in by_name  # sideboard only

    keys = [(-int(c["both_hits"]), str(c["name"])) for c in cards]
    assert keys == sorted(keys)
