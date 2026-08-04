from __future__ import annotations

import json
from pathlib import Path

import typer

from commander_lab.analysis import DeckValidator
from commander_lab.cards.catalog import CardCatalog
from commander_lab.engine.structural import (
    generate_project_profiles,
    load_project_structural_decks,
    run_phase3_validation,
    run_structural_batch,
)
from commander_lab.importers import DeckImportOptions, PlaintextDeckImporter
from commander_lab.models import StructuralAbortLimits, StructuralBatchConfig
from commander_lab.storage import compute_deck_hash
from commander_lab.tools.local_snapshots import build_local_snapshots

app = typer.Typer(no_args_is_help=True, help="Commander Playtest Lab utilities")


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


@app.command("generate-structural-profiles")
def generate_structural_profiles(
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Regenerate the validated structural role-profile snapshot."""
    output = generate_project_profiles(root)
    typer.echo(str(output))


@app.command("run-structural-batch")
def run_structural_batch_command(
    deck: list[str] = typer.Option(..., "--deck", help="Deck ID; repeat for each pod seat."),
    iterations: int = typer.Option(100, min=1),
    seed: int = typer.Option(20260804, min=0),
    workers: int = typer.Option(1, min=1, max=64),
    max_turns: int = typer.Option(35, min=1),
    output: Path = typer.Option(Path("data/runs/adhoc_structural")),
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Run a local structural_model_estimates batch."""
    decks = load_project_structural_decks(root, include_synthetic_fixtures=True)
    config = StructuralBatchConfig(
        run_id="adhoc-structural",
        seed=seed,
        iterations=iterations,
        deck_ids=tuple(deck),
        workers=workers,
        output_directory=str(root / output),
        limits=StructuralAbortLimits(max_turns=max_turns),
    )
    result = run_structural_batch(config, decks)
    typer.echo(json.dumps(result.aggregate, indent=2, ensure_ascii=False, sort_keys=True))


@app.command("validate-structural")
def validate_structural(
    iterations: int = typer.Option(24, min=1),
    workers: int = typer.Option(1, min=1, max=64),
    seed: int = typer.Option(20260804, min=0),
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Run Goldfish plus three-, four-, and five-player structural validation batches."""
    summary = run_phase3_validation(root, iterations=iterations, workers=workers, seed=seed)
    typer.echo(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    app()
