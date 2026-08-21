from __future__ import annotations

import json
from pathlib import Path

import typer

from commander_lab.storage import atomic_write_json
from commander_lab.whole_deck.mechanics_fidelity import (
    STRUCTURAL_SEMANTIC_MODEL_VERSION,
    assess_frontier_mechanics,
    run_critical_diagnostics_guarded,
    run_decision_confirmatory_guarded,
    run_decision_holdout_guarded,
)
from commander_lab.whole_deck.optimizer_v2_decision_runtime import (
    build_decision_manifest_from_project,
    load_decision_manifest,
    run_decision_search,
    verify_decision_preflight,
)

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Manifest-bound RogShai Optimizer v2 runner with frozen 1E/2F and mechanics-fidelity gates.",
)


@app.command("manifest")
def manifest_command(
    output: Path = typer.Option(..., "--output"),
    run_id: str = typer.Option("rogshai-optimizer-v2", "--run-id"),
    seed: int = typer.Option(2026082001, "--seed", min=0),
    exploratory_games: int = typer.Option(256, "--exploratory-games", min=1),
    calibration_games: int = typer.Option(128, "--calibration-games", min=1),
    confirmatory_games: int = typer.Option(2048, "--confirmatory-games", min=1),
    diagnostics_games: int = typer.Option(512, "--diagnostics-games", min=1),
    holdout_games: int = typer.Option(2048, "--holdout-games", min=1),
    root: Path = typer.Option(Path("."), "--root"),
) -> None:
    frozen = build_decision_manifest_from_project(
        root,
        run_id=run_id,
        search_seed=seed,
        exploratory_games=exploratory_games,
        calibration_games=calibration_games,
        confirmatory_games=confirmatory_games,
        diagnostics_games=diagnostics_games,
        holdout_games=holdout_games,
    )
    atomic_write_json(output, frozen.model_dump(mode="json"))
    typer.echo(
        json.dumps(
            {
                "status": "frozen",
                "manifest_hash": frozen.manifest_hash,
                "decision_runtime_version": frozen.decision_runtime_version,
                "structural_semantic_model_version": STRUCTURAL_SEMANTIC_MODEL_VERSION,
                "output": str(output),
                "operational_pod_size": frozen.operational_pod_size,
                "rogshai_candidate_count": frozen.rogshai_candidate_count,
                "partitions": {
                    "exploratory": frozen.exploratory.identity,
                    "calibration": frozen.calibration_partition.identity,
                    "confirmatory": frozen.confirmatory.identity,
                    "critical_diagnostics": frozen.critical_diagnostics.identity,
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
    frozen = load_decision_manifest(manifest)
    report = dict(verify_decision_preflight(root, frozen))
    report["structural_semantic_model_version"] = STRUCTURAL_SEMANTIC_MODEL_VERSION
    report["mechanics_fidelity_policy"] = (
        "exploratory_screening_allowed; confirmatory decisions require decision-safe variant deltas"
    )
    typer.echo(json.dumps(report, indent=2, sort_keys=True))


@app.command("fidelity")
def fidelity_command(
    frontier: Path = typer.Option(..., "--frontier", exists=True, dir_okay=False),
    root: Path = typer.Option(Path("."), "--root"),
) -> None:
    """Report the question-specific mechanics gate for a frozen frontier."""

    typer.echo(json.dumps(assess_frontier_mechanics(root, frontier), indent=2, sort_keys=True))


@app.command("run")
def run_command(
    manifest: Path = typer.Option(..., "--manifest", exists=True, dir_okay=False),
    output_dir: Path = typer.Option(Path(".runtime/optimizer-v2"), "--output-dir"),
    workers: int = typer.Option(1, "--workers", min=1),
    max_turns: int = typer.Option(35, "--max-turns", min=1),
    root: Path = typer.Option(Path("."), "--root"),
) -> None:
    frozen = load_decision_manifest(manifest)
    result = run_decision_search(
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
    root: Path = typer.Option(Path("."), "--root"),
) -> None:
    frozen = load_decision_manifest(manifest)
    result = run_decision_confirmatory_guarded(
        root,
        frozen,
        frontier_path=frontier,
        run_directory=output_dir,
        workers=workers,
        max_turns=max_turns,
    )
    typer.echo(json.dumps(result, indent=2, sort_keys=True))


@app.command("diagnose")
def diagnose_command(
    manifest: Path = typer.Option(..., "--manifest", exists=True, dir_okay=False),
    confirmatory: Path = typer.Option(..., "--confirmatory", exists=True, dir_okay=False),
    output_dir: Path = typer.Option(Path(".runtime/optimizer-v2"), "--output-dir"),
    workers: int = typer.Option(1, "--workers", min=1),
    max_turns: int = typer.Option(35, "--max-turns", min=1),
    root: Path = typer.Option(Path("."), "--root"),
) -> None:
    frozen = load_decision_manifest(manifest)
    result = run_critical_diagnostics_guarded(
        root,
        frozen,
        confirmatory_path=confirmatory,
        run_directory=output_dir,
        workers=workers,
        max_turns=max_turns,
    )
    typer.echo(json.dumps(result, indent=2, sort_keys=True))


@app.command("holdout")
def holdout_command(
    manifest: Path = typer.Option(..., "--manifest", exists=True, dir_okay=False),
    confirmatory: Path = typer.Option(..., "--confirmatory", exists=True, dir_okay=False),
    diagnostics: Path = typer.Option(..., "--diagnostics", exists=True, dir_okay=False),
    output_dir: Path = typer.Option(Path(".runtime/optimizer-v2"), "--output-dir"),
    authorize_holdout: bool = typer.Option(False, "--authorize-holdout"),
    workers: int = typer.Option(1, "--workers", min=1),
    max_turns: int = typer.Option(35, "--max-turns", min=1),
    root: Path = typer.Option(Path("."), "--root"),
) -> None:
    frozen = load_decision_manifest(manifest)
    result = run_decision_holdout_guarded(
        root,
        frozen,
        confirmatory_path=confirmatory,
        diagnostics_path=diagnostics,
        run_directory=output_dir,
        authorize_holdout=authorize_holdout,
        workers=workers,
        max_turns=max_turns,
    )
    typer.echo(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    app()
