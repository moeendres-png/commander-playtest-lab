"""Standalone ``engine-verify`` command: start, handshake and stop an external engine.

Run as ``python -m commander_lab.engine.verify_cli [--root DIR]``. The command prints the
engine process state as JSON and exits 1 unless the engine reports ``healthy``; tactical
fallback does not pass.
"""

from __future__ import annotations

from pathlib import Path

import typer

from commander_lab.engine.process_manager import (
    EngineProcessManager,
    load_engine_runtime_config,
)


def engine_verify(
    root: Path = typer.Option(Path.cwd(), exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Start, handshake and stop an external engine; tactical does not pass."""
    manager = EngineProcessManager(load_engine_runtime_config(), root=root)
    state = manager.start()
    typer.echo(state.model_dump_json(indent=2))
    manager.stop()
    if state.status.value != "healthy":
        raise typer.Exit(code=1)


def main() -> None:
    typer.run(engine_verify)


if __name__ == "__main__":
    main()
