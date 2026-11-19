"""Read-only corpus audit (Refs #1549). All data here is synthetic."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from commander_lab.studio import StudioStore
from commander_lab.studio.corpus_audit import audit_decks, corpus_audit
from commander_lab.studio.data_report import data_report

TODAY = date(2026, 11, 19)
CHULANE = "o-chulane"


def _store(tmp_path: Path) -> StudioStore:
    store = StudioStore.open(tmp_path / "studio")
    db = store.connection
    db.execute(
        "INSERT INTO source VALUES ('src:s', 'scryfall', 't', 'x', ?, NULL, '2026-11-16')",
        ("2026-11-10",),
    )
    cards = [
        (CHULANE, "Chulane, Teller of Tales", "WUG", "legal"),
        ("o-ok", "Fine Card", "G", "legal"),
        ("o-banned", "Banned Card", "G", "banned"),
        ("o-red", "Red Card", "R", "legal"),
        ("o-odd", "Odd Card", "G", "unknown"),
    ]
    for oid, name, colours, legality in cards:
        db.execute(
            "INSERT INTO scryfall_card(oracle_id, scryfall_id, name, front_name, layout, "
            "color_identity, commander_legality, keywords, produced_mana, source_id) "
            "VALUES (?, ?, ?, ?, 'normal', ?, ?, '[]', '[]', 'src:s')",
            (oid, oid, name, name, colours, legality),
        )
    return store


def _deck(
    store: StudioStore,
    deck_id: str,
    tags: list[str],
    main: list[tuple[str, int]],
    commander: str | None = CHULANE,
    duplicate_of: str | None = None,
) -> None:
    db = store.connection
    db.execute(
        "INSERT INTO corpus_deck VALUES (?, 'chulane', '', 'edhrec', 'community', NULL, '[]', ?, "
        "?, 'not_audited', 'src:s')",
        (deck_id, deck_id, duplicate_of),
    )
    for tag in tags:
        db.execute("INSERT INTO corpus_cohort VALUES (?, ?)", (tag, deck_id))
    rows = [("commander", commander, 1)] if commander else []
    rows += [("main", oid, qty) for oid, qty in main]
    for section, oid, qty in rows:
        db.execute(
            "INSERT INTO corpus_deck_card VALUES (?, ?, ?, ?, ?, 'ok')",
            (deck_id, f"n-{oid}", oid, qty, section),
        )


def _build(store: StudioStore) -> None:
    _deck(store, "legal", ["bracket:3", "source:edhrec"], [("o-ok", 99)])
    _deck(store, "banned", ["bracket:3", "source:edhrec"], [("o-ok", 98), ("o-banned", 1)])
    _deck(store, "colour", ["bracket:2", "source:edhrec"], [("o-ok", 98), ("o-red", 1)])
    _deck(store, "short", ["source:archidekt"], [("o-ok", 98)])
    _deck(store, "nocmd", ["bracket:2"], [("o-ok", 99)], commander="o-ok")
    _deck(store, "odd", ["bracket:2"], [("o-ok", 98), ("o-odd", 1)])
    _deck(store, "dupe", ["bracket:2"], [("o-ok", 99)], duplicate_of="legal")


def test_four_constructed_decks_and_unknown(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _build(store)
    result = audit_decks(store.connection)
    assert "dupe" not in result
    assert result["legal"].status == "ohne_befund"
    assert result["banned"].reasons == ["card_not_legal"]
    assert result["colour"].reasons == ["outside_identity"]
    assert result["short"].reasons == ["card_count_not_100"]
    assert result["nocmd"].reasons == ["commander_not_chulane"]
    assert result["odd"].status == "unbekannt"
    assert result["odd"].unmeasured == ["card_not_legal"]


def test_counts_cohorts_and_no_writes(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _build(store)
    db = store.connection
    before = db.execute("SELECT deck_id, legality_audit FROM corpus_deck ORDER BY 1").fetchall()
    section = corpus_audit(db, today=TODAY)
    assert section["decks_counted"] == {"count": 6, "of": 7}
    assert section["status"] == {"befund": 4, "unbekannt": 1, "ohne_befund": 1, "of": 6}
    by_reason = section["by_reason"]
    assert by_reason["card_not_legal"] == {"count": 1, "of": 6, "not_measurable": 1}  # type: ignore[index]
    dims = section["by_cohort_dimension"]
    assert dims["bracket"]["3"] == {"decks": 2, "befund": 1, "unbekannt": 0, "ohne_befund": 1}  # type: ignore[index]
    assert dims["bracket"]["unbekannt"]["decks"] == 1  # type: ignore[index]
    assert dims["source"]["unbekannt"]["decks"] == 2  # type: ignore[index]
    assert section["card_facts_snapshot_date"] == "2026-11-10"
    assert section["card_facts_age_days"] == 9
    assert (
        db.execute("SELECT deck_id, legality_audit FROM corpus_deck ORDER BY 1").fetchall()
        == before
    )
    assert data_report(store, today=TODAY)["corpus_audit"] == section


def test_unknown_instead_of_zero_without_facts(tmp_path: Path) -> None:
    store = StudioStore.open(tmp_path / "studio")
    section = corpus_audit(store.connection, today=TODAY)
    assert section["decks_counted"] == {"count": 0, "of": 0}
    assert section["card_facts_snapshot_date"] == "unbekannt"
