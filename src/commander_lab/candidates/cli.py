from __future__ import annotations

import json
from pathlib import Path

import typer

from .io import load_candidate_set, write_json
from .normalization import normalize_candidate_set
from .pipeline import build_simulation_queue
from .validation import load_hard_validation_context, validate_candidate_set

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Lossless external deck-candidate validation and gameplay-queue preparation.",
)


@app.command("normalize")
def normalize_command(
    input_path: Path = typer.Argument(..., exists=True, dir_okay=False),
    output: Path = typer.Option(..., "--output"),
) -> None:
    normalized = normalize_candidate_set(load_candidate_set(input_path))
    write_json(output, normalized)
    typer.echo(
        json.dumps(
            {"status": "pass", "candidate_count": normalized.candidate_count, "output": str(output)},
            sort_keys=True,
        )
    )


@app.command("validate")
def validate_command(
    input_path: Path = typer.Argument(..., exists=True, dir_okay=False),
    output: Path = typer.Option(Path("CANDIDATE_VALIDATION_REPORT.json"), "--output"),
    root: Path = typer.Option(Path("."), "--root"),
    target_deck_id: str | None = typer.Option(None, "--target-deck-id"),
) -> None:
    candidate_set = load_candidate_set(input_path)
    target = target_deck_id or candidate_set.source_identity.target_deck_id
    context = load_hard_validation_context(root, target_deck_id=target)
    _normalized, report = validate_candidate_set(candidate_set, context)
    write_json(output, report)
    typer.echo(
        json.dumps(
            {
                "status": "pass",
                "hard_valid_unique_count": report.hard_valid_unique_count,
                "output": str(output),
            },
            sort_keys=True,
        )
    )


@app.command("prepare-simulation")
def prepare_simulation_command(
    input_path: Path = typer.Argument(..., exists=True, dir_okay=False),
    output_dir: Path = typer.Option(Path(".runtime/candidates"), "--output-dir"),
    root: Path = typer.Option(Path("."), "--root"),
    target_deck_id: str | None = typer.Option(None, "--target-deck-id"),
) -> None:
    candidate_set = load_candidate_set(input_path)
    target = target_deck_id or candidate_set.source_identity.target_deck_id
    context = load_hard_validation_context(root, target_deck_id=target)
    normalized, report = validate_candidate_set(candidate_set, context)
    queue, invariant = build_simulation_queue(normalized, report)
    write_json(output_dir / "DECK_CANDIDATE_SET.normalized.json", normalized)
    write_json(output_dir / "CANDIDATE_VALIDATION_REPORT.json", report)
    write_json(output_dir / "SIMULATION_CANDIDATE_QUEUE.json", queue)
    write_json(output_dir / "PRE_SIMULATION_INVARIANT_REPORT.json", invariant)
    typer.echo(
        json.dumps(
            {
                "status": "pass",
                "input_hard_valid_unique_count": queue.input_hard_valid_unique_count,
                "output_simulation_queue_count": queue.output_simulation_queue_count,
                "lossless_handoff": queue.lossless_handoff,
                "output_dir": str(output_dir),
            },
            sort_keys=True,
        )
    )


__all__ = ["app"]
