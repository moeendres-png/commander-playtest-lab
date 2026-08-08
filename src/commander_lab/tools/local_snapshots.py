from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from commander_lab.analysis import DeckValidator, validate_collection_quantities
from commander_lab.cards.catalog import CardCatalog
from commander_lab.importers import DeckImportOptions, PlaintextDeckImporter
from commander_lab.models import Collection
from commander_lab.storage import compute_data_snapshot_hash, compute_deck_hash, save_model


DECK_SPECS = {
    "korvold/current": {
        "filename": "korvold_current.txt",
        "json_filename": "korvold_current.json",
        "name": "Korvold, Fae-Cursed King — Current",
        "commanders": ("Korvold, Fae-Cursed King",),
        "uses_partner": False,
    },
    "rogshai/current": {
        "filename": "rogshai_current.txt",
        "json_filename": "rogshai_current.json",
        "name": "Ishai + Rograkh — Current",
        "commanders": ("Ishai, Ojutai Dragonspeaker", "Rograkh, Son of Rohgahh"),
        "uses_partner": True,
    },
}


def build_local_snapshots(root: str | Path) -> dict[str, object]:
    root_path = Path(root)
    catalog_path = root_path / "data/cards/oracle_subset.json"
    collection_path = root_path / "data/collections/current_deck_allocations.json"
    deck_dir = root_path / "data/decks"

    catalog = CardCatalog.from_json(catalog_path)
    importer = PlaintextDeckImporter(catalog)
    validator = DeckValidator(catalog)

    decks = {}
    validations = {}
    for deck_id, spec in DECK_SPECS.items():
        source_file = deck_dir / str(spec["filename"])
        source_path = source_file.relative_to(root_path).as_posix()
        deck = importer.import_text(
            source_file.read_text(encoding="utf-8-sig"),
            DeckImportOptions(
                deck_id=deck_id,
                name=str(spec["name"]),
                commander_names=tuple(spec["commanders"]),
                uses_partner=bool(spec["uses_partner"]),
                data_as_of="2026-08-07",
            ),
            source_path=source_path,
        )
        deck.deck_hash = compute_deck_hash(deck)
        report = validator.validate(deck)
        if not report.valid:
            raise ValueError(f"local snapshot {deck_id} failed validation: {report.model_dump()}")
        save_model(deck_dir / str(spec["json_filename"]), deck)
        decks[deck_id] = deck
        validations[deck_id] = report.model_dump(mode="json")

    collection = Collection.model_validate_json(collection_path.read_text(encoding="utf-8"))
    allocation = validate_collection_quantities(collection, decks.values())
    if not allocation.valid:
        raise ValueError(f"local allocation snapshot failed: {allocation.model_dump()}")

    snapshot_files = [
        catalog_path,
        collection_path,
        deck_dir / "korvold_current.txt",
        deck_dir / "rogshai_current.txt",
        deck_dir / "korvold_current.json",
        deck_dir / "rogshai_current.json",
    ]
    data_hash = compute_data_snapshot_hash(snapshot_files, root=root_path)
    manifest = {
        "schema_version": "0.2.0",
        "data_as_of": date(2026, 8, 7).isoformat(),
        "generated_from_local_files_only": True,
        "google_drive_modified": False,
        "authoritative_oracle_snapshot": False,
        "data_snapshot_hash": data_hash,
        "decks": {
            deck_id: {
                "deck_hash": deck.deck_hash,
                "total_cards": deck.total_cards,
                "library_cards": deck.library_cards,
                "commanders": list(deck.commander.commanders),
                "source_file": str(DECK_SPECS[deck_id]["filename"]),
                "normalized_file": str(DECK_SPECS[deck_id]["json_filename"]),
                "validation": validations[deck_id],
            }
            for deck_id, deck in decks.items()
        },
        "allocation_validation": allocation.model_dump(mode="json"),
    }
    (deck_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return manifest
