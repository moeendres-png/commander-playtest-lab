from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import date
from pathlib import Path

from commander_lab.analysis import DeckValidator, validate_collection_quantities
from commander_lab.cards.catalog import CardCatalog
from commander_lab.importers import DeckImportOptions, PlaintextDeckImporter
from commander_lab.models import CardIdentity, Collection, DataQuality
from commander_lab.storage import compute_data_snapshot_hash, compute_deck_hash, save_model

DECK_SPECS = {
    "rogshai/current": {
        "filename": "rogshai_current.txt",
        "json_filename": "rogshai_current.json",
        "name": "Ishai + Rograkh — Provisional Final / Simulator Optimization Baseline",
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
    overlay_path = deck_dir / "rogshai_current_card_catalog_overrides.json"
    overlay_payload = json.loads(overlay_path.read_text(encoding="utf-8"))
    for row in overlay_payload.get("cards", []):
        catalog.add(CardIdentity.model_validate(row))
    importer = PlaintextDeckImporter(catalog)
    validator = DeckValidator(catalog)

    decks = {}
    validations = {}
    for deck_id, spec in DECK_SPECS.items():
        source_file = deck_dir / str(spec["filename"])
        source_path = source_file.relative_to(root_path).as_posix()
        raw_commanders = spec["commanders"]
        if not isinstance(raw_commanders, Iterable) or isinstance(raw_commanders, (str, bytes)):
            raise TypeError(f"invalid commanders for {deck_id}")
        commander_names = tuple(str(name) for name in raw_commanders)
        deck = importer.import_text(
            source_file.read_text(encoding="utf-8-sig"),
            DeckImportOptions(
                deck_id=deck_id,
                name=str(spec["name"]),
                commander_names=commander_names,
                uses_partner=bool(spec["uses_partner"]),
                data_as_of="2026-08-11",
            ),
            source_path=source_path,
        )
        if deck.source is None:
            raise ValueError(f"imported deck {deck_id} is missing source provenance")
        deck = deck.model_copy(
            update={
                "source": deck.source.model_copy(
                    update={
                        "source_type": "direct_user_decision",
                        "source_name": "RogShai provisional final fresh rebuild 2026-08-11",
                        "source_path": source_path,
                        "quality": DataQuality.PROJECT_VERIFIED,
                        "notes": (
                            "Current provisional final baseline for continued simulator optimization; "
                            "supersedes all older own RogShai/Korvold deck snapshots in the operational current set."
                        ),
                    }
                ),
                "tags": {
                    "rogshai_only_active_own_deck",
                    "simulator_optimization_baseline",
                    "provisional_final",
                    "current",
                },
                "notes": (
                    "This is the current provisional final RogShai list and the sole own-deck "
                    "baseline for further simulator optimization. It is not frozen final; "
                    "simulator-supported improvements may replace cards later."
                ),
            }
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
        deck_dir / "rogshai_current_card_catalog_overrides.json",
        deck_dir / "rogshai_current_structural_overrides.json",
        collection_path,
        deck_dir / "rogshai_current.txt",
        deck_dir / "rogshai_current.json",
    ]
    data_hash = compute_data_snapshot_hash(snapshot_files, root=root_path)
    manifest = {
        "schema_version": "0.3.0",
        "data_as_of": date(2026, 8, 11).isoformat(),
        "generated_from_local_files_only": True,
        "google_drive_modified": False,
        "authoritative_oracle_snapshot": False,
        "data_snapshot_hash": data_hash,
        "status": "current_provisional_final_for_simulator_optimization",
        "active_own_decks": ["rogshai/current"],
        "supersedes_all_prior_operational_own_deck_snapshots": True,
        "decks": {
            deck_id: {
                "deck_hash": deck.deck_hash,
                "total_cards": deck.total_cards,
                "library_cards": deck.library_cards,
                "commanders": list(deck.commander.commanders),
                "source_file": str(DECK_SPECS[deck_id]["filename"]),
                "normalized_file": str(DECK_SPECS[deck_id]["json_filename"]),
                "status": "provisional_final_current_for_simulator_optimization",
                "validation": validations[deck_id],
            }
            for deck_id, deck in decks.items()
        },
        "allocation_validation": allocation.model_dump(mode="json"),
        "removed_operational_decks": ["korvold/current"],
        "notes": (
            "Only RogShai is an active/current own deck. Old Korvold and superseded "
            "RogShai deck snapshots are not part of the current simulator baseline."
        ),
    }
    (deck_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return manifest
