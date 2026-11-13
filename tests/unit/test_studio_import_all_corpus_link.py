"""Source-deck cards get their oracle ids, whatever the order of the imports.

All data here is synthetic. No network.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from commander_lab.studio import StudioStore, catalog, decklist_import

COMMANDER = "Test Commander"


def _oracle_file(path: Path) -> Path:
    def card(name: str, type_line: str, mana_value: float, **extra: object) -> dict[str, object]:
        slug = name.casefold().replace(" ", "-").replace("/", "")
        base: dict[str, object] = {
            "id": f"print-{slug}",
            "oracle_id": f"oracle-{slug}",
            "name": name,
            "layout": "normal",
            "cmc": mana_value,
            "type_line": type_line,
            "color_identity": ["G"],
            "legalities": {"commander": "legal"},
        }
        base.update(extra)
        return base

    cards = [
        card(COMMANDER, "Legendary Creature — Elf", 3.0),
        card("Forest", "Basic Land — Forest", 0.0),
        card("Grizzly Bears", "Creature — Bear", 2.0),
        card("Fire // Ice", "Instant // Instant", 4.0, layout="split"),
    ]
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write("\n".join(json.dumps(item) for item in cards) + "\n")
    return path


def _decks(folder: Path) -> Path:
    folder.mkdir()
    cards = [
        {"name": COMMANDER, "quantity": 1},
        {"name": "Forest", "quantity": 10},
        {"name": "Grizzly Bears", "quantity": 2},
        {"name": "Fire", "quantity": 1},  # front face only
        {"name": "Mystery Card", "quantity": 1},
    ]
    payload = {
        "urlhash": "aaa",
        "variante": "upgraded",
        "bracket": 3,
        "savedate": "2026-10-01",
        "commanders": [COMMANDER],
        "cards": cards,
        "karten_summe": 15,
    }
    (folder / "aaa.json").write_text(json.dumps(payload), encoding="utf-8")
    return folder


def _stats(store: StudioStore) -> tuple[int, int, int, int]:
    row = store.connection.execute(
        "SELECT cards, resolved, lands, creatures FROM corpus_deck_stat"
    ).fetchone()
    return (row[0], row[1], row[2], row[3])


def test_decklists_first_then_scryfall_resolves_stats(tmp_path: Path) -> None:
    store = StudioStore.in_memory()
    result = decklist_import.import_decklists(store, _decks(tmp_path / "d"), format="edhrec")
    assert result["corpus_relink_status"] == "NO_CARD_DATA"
    assert result["corpus_cards_unresolved"] == 5
    assert (
        store.connection.execute(
            "SELECT COUNT(*) FROM corpus_deck_card WHERE oracle_id IS NOT NULL"
        ).fetchone()[0]
        == 0
    )
    report = catalog.import_scryfall_oracle(store, _oracle_file(tmp_path / "o.jsonl.gz"))
    assert report["corpus_cards_linked"] == 4
    assert report["corpus_unresolved_names"] == ["Mystery Card"]
    # 15 cards, 14 found (the front face "Fire" resolves the split card), 10 lands, 3 creatures
    assert _stats(store) == (15, 14, 10, 3)


def test_scryfall_first_then_decklists_resolves_at_once(tmp_path: Path) -> None:
    store = StudioStore.in_memory()
    catalog.import_scryfall_oracle(store, _oracle_file(tmp_path / "o.jsonl.gz"))
    result = decklist_import.import_decklists(store, _decks(tmp_path / "d"), format="edhrec")
    assert result["corpus_relink_status"] == "OK"
    assert result["corpus_cards_linked"] == 4
    assert result["corpus_cards_unresolved"] == 1
    assert result["corpus_unresolved_names"] == ["Mystery Card"]
    assert _stats(store) == (15, 14, 10, 3)


def test_relink_is_idempotent_and_keeps_given_oracle_ids(tmp_path: Path) -> None:
    store = StudioStore.in_memory()
    decklist_import.import_decklists(store, _decks(tmp_path / "d"), format="edhrec")
    store.connection.execute(
        "UPDATE corpus_deck_card SET oracle_id = 'given' WHERE card_name = 'Forest'"
    )
    catalog.import_scryfall_oracle(store, _oracle_file(tmp_path / "o.jsonl.gz"))
    again = catalog.relink_corpus(store)
    assert again["corpus_cards_linked"] == 0
    kept = store.connection.execute(
        "SELECT oracle_id FROM corpus_deck_card WHERE card_name = 'Forest'"
    ).fetchone()[0]
    assert kept == "given"
