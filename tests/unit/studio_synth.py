"""Tiny synthetic Studio stores for counting tests. Every name here is invented."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

from commander_lab.studio import StudioStore

SOURCE = "src:synth"


def make_store(folder: Path | None = None) -> StudioStore:
    store = StudioStore.in_memory() if folder is None else StudioStore.open(folder)
    store.connection.execute(
        "INSERT INTO source(source_id, data_class, title, sha256, imported_at) "
        "VALUES (?, 'NORMALIZED_SOURCE', 'synthetic.csv', 'x', '2026-11-01T00:00:00Z')",
        (SOURCE,),
    )
    return store


def add_card(
    store: StudioStore,
    name: str,
    *,
    type_line: str = "Artifact",
    identity: str = "",
    basic: bool = False,
) -> str:
    card_id = f"card:synth:{name.casefold().replace(' ', '-').replace(',', '')}"
    db = store.connection
    db.execute(
        "INSERT INTO card(card_id, oracle_id, oracle_name, color_identity, type_line, "
        "is_basic_land, commander_legal, source_id) VALUES (?, NULL, ?, ?, ?, ?, 1, ?)",
        (card_id, name, identity, type_line, 1 if basic else 0, SOURCE),
    )
    db.execute(
        "INSERT INTO inventory(card_id, observed, owned_lower_bound, reserved, "
        "available_lower_bound, quantity_exact, lots, last_verified_at, source_id) "
        "VALUES (?, 1, 1, 0, 1, 1, 1, NULL, ?)",
        (card_id, SOURCE),
    )
    return card_id


def add_deck(
    store: StudioStore,
    deck_id: str,
    cards: Iterable[str],
    *,
    commanders: Sequence[str] = ("Cmd A",),
    cohorts: Sequence[str] = (),
    platform: str = "edhrec",
    section: str = "main",
    other_sections: dict[str, Sequence[str]] | None = None,
    deck_date: str = "2026-10-01",
    bind: bool = True,
) -> None:
    db = store.connection
    db.execute(
        "INSERT INTO corpus_deck(deck_id, cohort, url, platform, play_group, deck_date, tags, "
        "fingerprint, duplicate_of, legality_audit, source_id) "
        "VALUES (?, 'c', '', ?, 'g', ?, '[]', ?, NULL, 'not_audited', ?)",
        (deck_id, platform, deck_date, f"fp-{deck_id}", SOURCE),
    )
    rows = [(deck_id, name, section) for name in cards]
    rows += [(deck_id, name, "commander") for name in commanders]
    for other, names in (other_sections or {}).items():
        rows += [(deck_id, name, other) for name in names]
    db.executemany(
        "INSERT INTO corpus_deck_card(deck_id, card_name, section, oracle_id, quantity, "
        "normalization_status) VALUES (?, ?, ?, NULL, 1, 'source_name')",
        rows,
    )
    for cohort in cohorts:
        db.execute("INSERT INTO corpus_cohort(cohort, deck_id) VALUES (?, ?)", (cohort, deck_id))
    if bind:
        for commander in commanders:
            db.execute(
                "INSERT INTO commander_binding(kind, key, commander_name, basis) "
                "VALUES ('corpus_deck', ?, ?, 'TEST')",
                (deck_id, commander),
            )


def add_signal(
    store: StudioStore,
    commander: str,
    signal: str,
    card: str,
    numerator: int | None,
    denominator: int | None,
    value: float | None = None,
) -> None:
    if value is None and numerator is not None and denominator:
        value = numerator / denominator
    store.connection.execute(
        "INSERT OR REPLACE INTO card_signal(commander_name, signal, card_name, value, numerator, "
        "denominator, source_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (commander, signal, card, value, numerator, denominator, SOURCE),
    )
