from __future__ import annotations

import hashlib
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
        "name": "Ishai + Rograkh — Current Physical Photo-Verified Build",
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
    land_counts = {}
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
                data_as_of="2026-08-15",
            ),
            source_path=source_path,
        )
        if deck.source is None:
            raise ValueError(f"imported deck {deck_id} is missing source provenance")
        deck = deck.model_copy(
            update={
                "source": deck.source.model_copy(
                    update={
                        "source_type": "direct_user_photo_verification",
                        "source_name": "RogShai physical deck photos 2026-08-15",
                        "source_path": source_path,
                        "quality": DataQuality.PROJECT_VERIFIED,
                        "notes": (
                            "The photographed physical 100-card deck supersedes the 2026-08-11 "
                            "provisional simulator baseline as current RogShai truth. Exact printing "
                            "identities are stored in rogshai_current_physical_printings.json."
                        ),
                    }
                ),
                "tags": {
                    "photo_verified",
                    "physical",
                    "rogshai",
                    "current",
                },
                "notes": (
                    "Current physical RogShai list. Set codes and collector numbers remain in the "
                    "separate physical-printings projection; this normalized runtime file contains "
                    "only fields accepted by the strict Deck schema."
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
        land_counts[deck_id] = sum(
            entry.quantity
            for entry in deck.cards
            if "land" in catalog.resolve(entry.oracle_name).type_line.casefold()
        )

    collection = Collection.model_validate_json(collection_path.read_text(encoding="utf-8"))
    allocation = validate_collection_quantities(collection, decks.values())
    if not allocation.valid:
        raise ValueError(f"local allocation snapshot failed: {allocation.model_dump()}")

    snapshot_files = [
        catalog_path,
        deck_dir / "rogshai_current_card_catalog_overrides.json",
        deck_dir / "rogshai_current_structural_overrides.json",
        deck_dir / "rogshai_photo_verified_structural_overrides.json",
        deck_dir / "rogshai_current_physical_printings.json",
        root_path / "data/cards/structural_role_profiles.json",
        collection_path,
        deck_dir / "rogshai_current.txt",
        deck_dir / "rogshai_current.json",
    ]
    data_hash = compute_data_snapshot_hash(snapshot_files, root=root_path)
    manifest = {
        "schema_version": "0.3.0",
        "data_as_of": date(2026, 8, 15).isoformat(),
        "generated_from_local_files_only": True,
        "google_drive_modified": False,
        "authoritative_oracle_snapshot": False,
        "data_snapshot_hash": data_hash,
        "status": "current_physical_photo_verified",
        "global_active_own_decks": ["korvold/current", "rogshai/current"],
        "current_optimization_target": "rogshai/current",
        "runtime_loaded_decks": ["rogshai/current"],
        "frozen_opponent_decks": ["kaervek/current"],
        "active_own_decks": ["rogshai/current"],
        "active_own_decks_semantics": "legacy_runtime_loaded_decks_compatibility_alias",
        "supersedes_all_prior_operational_own_deck_snapshots": True,
        "decks": {
            deck_id: {
                "deck_hash": deck.deck_hash,
                "deck_hash_method": "canonical_json_v1_normalized_deck_identity",
                "source_file_sha256": hashlib.sha256(
                    (deck_dir / str(DECK_SPECS[deck_id]["filename"])).read_bytes()
                ).hexdigest(),
                "source_hash_method": "sha256_exact_utf8_source_file_lf_trailing_newline",
                "total_cards": deck.total_cards,
                "library_cards": deck.library_cards,
                "land_count": land_counts[deck_id],
                "commanders": list(deck.commander.commanders),
                "source_file": str(DECK_SPECS[deck_id]["filename"]),
                "normalized_file": str(DECK_SPECS[deck_id]["json_filename"]),
                "physical_printings_file": "rogshai_current_physical_printings.json",
                "status": "current_physical_photo_verified",
                "validation": validations[deck_id],
            }
            for deck_id, deck in decks.items()
        },
        "allocation_validation": {
            **allocation.model_dump(mode="json"),
            "scope": "runtime_loaded_decks_only",
        },
        "removed_operational_decks": ["korvold/current"],
        "removed_operational_decks_semantics": "removed_from_runtime_loaded_decks_not_global_ownership",
        "notes": (
            "Korvold and RogShai are globally active own decks. This runtime snapshot loads only "
            "RogShai as the current optimization target; Korvold is not deleted or globally inactive. "
            "Kaervek remains a frozen opponent."
        ),
    }
    (deck_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest
