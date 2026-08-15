from __future__ import annotations

import json
from pathlib import Path

import typer

from commander_lab.storage import atomic_write_json
from commander_lab.whole_deck.optimizer_runtime import (
    build_optimizer_manifest_from_project,
    load_optimizer_manifest,
    run_optimizer_search,
    verify_optimizer_preflight,
)

app = typer.Typer(no_args_is_help=True, help="Manifest-bound RogShai Optimizer v2 runner")


@app.command("manifest")
def freeze_manifest(
    output: Path = typer.Option(..., dir_okay=False),
    run_id: str = typer.Option(...),
    seed: int = typer.Option(..., min=0),
    exploratory_games: int = typer.Option(256, min=1),
    confirmatory_games: int = typer.Option(512, min=1),
    holdout_games: int = typer.Option(512, min=1),
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Freeze current software/data identities and three disjoint evidence partitions."""

    manifest = build_optimizer_manifest_from_project(
        root,
        run_id=run_id,
        search_seed=seed,
        exploratory_games=exploratory_games,
        confirmatory_games=confirmatory_games,
        holdout_games=holdout_games,
    )
    atomic_write_json(output, manifest.model_dump(mode="json"))
    typer.echo(
        json.dumps(
            {"manifest": str(output), "manifest_hash": manifest.manifest_hash},
            indent=2,
            sort_keys=True,
        )
    )


@app.command("preflight")
def preflight(
    manifest: Path = typer.Option(..., exists=True, dir_okay=False),
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Fail closed on software, deck/pool, opponent or knowledge identity mismatch."""

    frozen = load_optimizer_manifest(manifest)
    typer.echo(json.dumps(verify_optimizer_preflight(root, frozen), indent=2, sort_keys=True))


@app.command("run")
def run(
    manifest: Path = typer.Option(..., exists=True, dir_okay=False),
    output_dir: Path = typer.Option(..., file_okay=False),
    workers: int = typer.Option(1, min=1, max=64),
    max_turns: int = typer.Option(35, min=1, max=500),
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Run only the adaptive exploratory lane; confirmatory and holdout remain sealed."""

    frozen = load_optimizer_manifest(manifest)
    payload = run_optimizer_search(
        root,
        frozen,
        run_directory=output_dir,
        workers=workers,
        max_turns=max_turns,
    )
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    app()
