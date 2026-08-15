from __future__ import annotations

import json
from pathlib import Path

import typer

from commander_lab.storage import atomic_write_json
from commander_lab.whole_deck.optimizer_v2_release import (
    build_release_manifest_from_project,
    load_release_manifest,
    run_release_confirmatory,
    run_release_holdout,
    run_release_search,
    verify_release_preflight,
)

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Manifest-bound adaptive RogShai Optimizer v2 runner.",
)


@app.command("manifest")
def manifest_command(
    output: Path = typer.Option(..., "--output"),
    run_id: str = typer.Option("rogshai-optimizer-v2", "--run-id"),
    seed: int = typer.Option(2026081507, "--seed", min=0),
    exploratory_games: int = typer.Option(256, "--exploratory-games", min=1),
    calibration_games: int = typer.Option(128, "--calibration-games", min=1),
    confirmatory_games: int = typer.Option(512, "--confirmatory-games", min=1),
    holdout_games: int = typer.Option(512, "--holdout-games", min=1),
    root: Path = typer.Option(Path("."), "--root"),
) -> None:
    frozen = build_release_manifest_from_project(
        root,
        run_id=run_id,
        search_seed=seed,
        exploratory_games=exploratory_games,
        calibration_games=calibration_games,
        confirmatory_games=confirmatory_games,
        holdout_games=holdout_games,
    )
    atomic_write_json(output, frozen.model_dump(mode="json"))
    typer.echo(
        json.dumps(
            {
                "status": "frozen",
                "manifest_hash": frozen.manifest_hash,
                "output": str(output),
                "partitions": {
                    "exploratory": frozen.exploratory.identity,
                    "calibration": frozen.calibration_partition.identity,
                    "confirmatory": frozen.confirmatory.identity,
                    "sealed_holdout": frozen.sealed_holdout.identity,
                },
            },
            indent=2,
            sort_keys=True,
        )
    )


@app.command("preflight")
def preflight_command(
    manifest: Path = typer.Option(..., "--manifest", exists=True, dir_okay=False),
    root: Path = typer.Option(Path("."), "--root"),
) -> None:
    frozen = load_release_manifest(manifest)
    typer.echo(json.dumps(verify_release_preflight(root, frozen), indent=2, sort_keys=True))


@app.command("run")
def run_command(
    manifest: Path = typer.Option(..., "--manifest", exists=True, dir_okay=False),
    output_dir: Path = typer.Option(Path(".runtime/optimizer-v2"), "--output-dir"),
    workers: int = typer.Option(1, "--workers", min=1),
    max_turns: int = typer.Option(35, "--max-turns", min=1),
    root: Path = typer.Option(Path("."), "--root"),
) -> None:
    frozen = load_release_manifest(manifest)
    result = run_release_search(
        root,
        frozen,
        run_directory=output_dir,
        workers=workers,
        max_turns=max_turns,
    )
    typer.echo(json.dumps(result, indent=2, sort_keys=True))


@app.command("confirm")
def confirm_command(
    manifest: Path = typer.Option(..., "--manifest", exists=True, dir_okay=False),
    frontier: Path = typer.Option(..., "--frontier", exists=True, dir_okay=False),
    output_dir: Path = typer.Option(Path(".runtime/optimizer-v2"), "--output-dir"),
    workers: int = typer.Option(1, "--workers", min=1),
    max_turns: int = typer.Option(35, "--max-turns", min=1),
    budget: int | None = typer.Option(None, "--budget", min=1),
    root: Path = typer.Option(Path("."), "--root"),
) -> None:
    frozen = load_release_manifest(manifest)
    result = run_release_confirmatory(
        root,
        frozen,
        frontier_path=frontier,
        run_directory=output_dir,
        workers=workers,
        max_turns=max_turns,
        budget=budget,
    )
    typer.echo(json.dumps(result, indent=2, sort_keys=True))


@app.command("holdout")
def holdout_command(
    manifest: Path = typer.Option(..., "--manifest", exists=True, dir_okay=False),
    confirmatory: Path = typer.Option(..., "--confirmatory", exists=True, dir_okay=False),
    output_dir: Path = typer.Option(Path(".runtime/optimizer-v2"), "--output-dir"),
    authorize_holdout: bool = typer.Option(False, "--authorize-holdout"),
    workers: int = typer.Option(1, "--workers", min=1),
    max_turns: int = typer.Option(35, "--max-turns", min=1),
    budget: int | None = typer.Option(None, "--budget", min=1),
    root: Path = typer.Option(Path("."), "--root"),
) -> None:
    frozen = load_release_manifest(manifest)
    result = run_release_holdout(
        root,
        frozen,
        confirmatory_path=confirmatory,
        run_directory=output_dir,
        authorize_holdout=authorize_holdout,
        workers=workers,
        max_turns=max_turns,
        budget=budget,
    )
    typer.echo(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    app()
