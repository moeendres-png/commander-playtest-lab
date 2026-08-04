from __future__ import annotations

import json
from pathlib import Path

import typer

from commander_lab.analysis import DeckValidator
from commander_lab.cards.catalog import CardCatalog
from commander_lab.importers import DeckImportOptions, PlaintextDeckImporter
from commander_lab.storage import compute_deck_hash
from commander_lab.tools.local_snapshots import build_local_snapshots

app = typer.Typer(no_args_is_help=True, help="Commander Playtest Lab data utilities")


@app.command("validate-local")
def validate_local(
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Rebuild and validate the two immutable local current-deck snapshots."""
    manifest = build_local_snapshots(root)
    typer.echo(json.dumps(manifest, indent=2, ensure_ascii=False))


@app.command("inspect-deck")
def inspect_deck(
    deck_file: Path = typer.Argument(..., exists=True, dir_okay=False),
    catalog_file: Path = typer.Option(
        Path("data/cards/oracle_subset.json"), exists=True, dir_okay=False
    ),
    deck_id: str = typer.Option("adhoc/deck"),
    deck_name: str = typer.Option("Ad hoc deck"),
    commander: list[str] = typer.Option(..., "--commander"),
    partner: bool = typer.Option(False),
) -> None:
    """Import and validate a plaintext deck without modifying its source file."""
    catalog = CardCatalog.from_json(catalog_file)
    deck = PlaintextDeckImporter(catalog).import_file(
        deck_file,
        DeckImportOptions(
            deck_id=deck_id,
            name=deck_name,
            commander_names=tuple(commander),
            uses_partner=partner,
        ),
    )
    deck.deck_hash = compute_deck_hash(deck)
    report = DeckValidator(catalog).validate(deck)
    typer.echo(
        json.dumps(
            {"deck": deck.model_dump(mode="json"), "validation": report.model_dump(mode="json")},
            indent=2,
            ensure_ascii=False,
        )
    )
    if not report.valid:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
